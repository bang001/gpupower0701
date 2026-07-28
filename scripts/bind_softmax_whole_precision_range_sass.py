#!/usr/bin/env python3
"""Bind a passing static SASS/PTX audit to a completed range measurement.

The range runner freezes both its executable and runner before the first CUDA
process starts.  This post-execution utility verifies those frozen artifacts,
every completed raw/trace hash, and the exact (S, endpoint-policy) capture
set before it adds one immutable ``sass_audit`` binding to ``manifest.json``.
The audit itself must live at ``<run-dir>/sass_audit.json``; an unrelated
audit, a rebuilt binary, or a later replacement cannot silently become range
evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from softmax_platform_profiles import PLATFORM_PROFILES


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_SCHEMA = "softmax_whole_precision_range_manifest_v1"
AUDIT_SCHEMA = "softmax_whole_precision_range_static_audit_v1"

# These are the only policies instantiated by the range executable.  The
# numeric values are the stable C++ ``whole_precision::Policy`` enum values,
# and are deliberately recorded in the static-audit capture keys.
POLICY_IDS = {
    "fp32_io_fp32_all": 0,
    "fp16_scalar_all": 8,
    "fp16x2_all": 9,
}
POLICY_NAMES_BY_ID = {value: key for key, value in POLICY_IDS.items()}
SUPPORTED_SOFTMAX_COLS = frozenset((512, 1024, 2048, 4096))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve(value: object, run_dir: Path) -> Path:
    require(isinstance(value, str) and bool(value), "artifact path is missing")
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    # Runner manifests normally contain a repository-relative path.  The
    # run-local fallback keeps a moved result package usable when paths were
    # stored relative to the run directory instead.
    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (run_dir / candidate).resolve()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {label}: {error}") from error
    require(isinstance(payload, dict), f"{label} root is not an object")
    return payload


def read_csv(path: Path, label: str) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise SystemExit(f"cannot read {label}: {error}") from error
    require(bool(rows) and all(None not in row for row in rows), f"{label} is empty or malformed")
    return rows


def require_frozen_artifact(
    manifest: Mapping[str, Any], key: str, run_dir: Path
) -> tuple[Path, str]:
    record = manifest.get(key)
    require(isinstance(record, dict), f"manifest.{key} is invalid")
    expected_sha = record.get("sha256")
    require(is_sha256(expected_sha), f"manifest.{key}.sha256 is malformed")
    path = resolve(record.get("path"), run_dir)
    require(path.is_file(), f"manifest frozen {key} is missing: {path}")
    require(is_within(path, run_dir / "frozen"),
            f"manifest {key} is not a run-local frozen artifact: {path}")
    require(sha256_file(path) == expected_sha,
            f"manifest frozen {key} does not match its recorded SHA-256")
    return path, expected_sha


def policy_names_for_profile(profile_name: str) -> tuple[str, ...]:
    # Do not turn V100's lack of native f16 EX2 into a substitute endpoint.
    return ("fp32_io_fp32_all",) if profile_name == "v100" else tuple(POLICY_IDS)


def require_completed_measurement(
    manifest: Mapping[str, Any], run_dir: Path, profile_name: str,
    binary_sha: str, native_arch: int,
) -> tuple[list[int], list[int], list[str]]:
    """Validate hashes and return the exact measured S/policy coverage.

    CSV contents are checked against the manifest schedule as well as their
    recorded hash.  This prevents a hand-edited manifest from changing the
    static audit's required capture set after a successful acquisition.
    """

    require(manifest.get("status") == "complete",
            "measurement run is not complete; refusing to bind during acquisition")
    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and sessions,
            "manifest has no completed measurement sessions")
    expected_policy_names = set(policy_names_for_profile(profile_name))
    measured_cols: set[int] = set()
    measured_policy_names: set[str] = set()

    for index, session in enumerate(sessions, start=1):
        label = f"manifest session {index}"
        require(isinstance(session, dict), f"{label} is invalid")
        require(session.get("status") == "complete", f"{label} is not complete")
        require(session.get("returncode") == 0, f"{label} did not exit successfully")
        schedule = session.get("policy_schedule")
        require(isinstance(schedule, list) and schedule and
                all(isinstance(policy, str) and policy in POLICY_IDS for policy in schedule),
                f"{label} has an invalid endpoint policy schedule")
        require(len(schedule) == len(set(schedule)),
                f"{label} repeats an endpoint policy in one fresh process")
        require(set(schedule).issubset(expected_policy_names),
                f"{label} schedules a policy unsupported by {profile_name}")
        try:
            softmax_cols = int(session.get("softmax_cols"))
        except (TypeError, ValueError) as error:
            raise SystemExit(f"{label} softmax_cols is invalid") from error
        require(softmax_cols in SUPPORTED_SOFTMAX_COLS,
                f"{label} softmax_cols is outside the range-kernel contract")

        artifacts: dict[str, Path] = {}
        for path_key, hash_key in (
            ("raw_csv", "raw_sha256"),
            ("energy_trace_csv", "energy_trace_sha256"),
        ):
            expected_hash = session.get(hash_key)
            require(is_sha256(expected_hash), f"{label} lacks a valid {hash_key}")
            artifact = resolve(session.get(path_key), run_dir)
            require(artifact.is_file() and sha256_file(artifact) == expected_hash,
                    f"{label} {path_key} does not match its recorded SHA-256")
            artifacts[path_key] = artifact

        rows = read_csv(artifacts["raw_csv"], f"{label} raw CSV")
        require(len(rows) == len(schedule),
                f"{label} raw role count differs from its policy schedule")
        raw_run_policies: dict[str, str] = {}
        for sequence, (row, policy) in enumerate(zip(rows, schedule)):
            row_label = f"{label} raw row {sequence}"
            require(row.get("policy") == policy,
                    f"{row_label} policy does not match its schedule")
            require(row.get("binary_sha256") == binary_sha,
                    f"{row_label} was not produced by the frozen measurement binary")
            try:
                row_arch = int(str(row.get("cuda_binary_arch", "")))
            except ValueError as error:
                raise SystemExit(f"{row_label} cuda_binary_arch is invalid") from error
            require(row_arch == native_arch,
                    f"{row_label} loaded a native architecture outside the target profile")
            try:
                row_cols = int(str(row.get("softmax_cols", "")))
            except ValueError as error:
                raise SystemExit(f"{row_label} softmax_cols is invalid") from error
            require(row_cols == softmax_cols,
                    f"{row_label} softmax_cols does not match its session")
            run_id = row.get("run_id")
            require(isinstance(run_id, str) and bool(run_id) and run_id not in raw_run_policies,
                    f"{row_label} has an invalid or duplicate run_id")
            raw_run_policies[run_id] = policy
            measured_cols.add(row_cols)
            measured_policy_names.add(policy)

        # A hash makes the trace immutable evidence.  It must be a parseable
        # CSV as well, rather than a correctly hashed empty placeholder.
        trace_rows = read_csv(artifacts["energy_trace_csv"], f"{label} energy trace")
        trace_run_ids: set[str] = set()
        for trace_index, trace in enumerate(trace_rows):
            trace_label = f"{label} trace row {trace_index}"
            run_id = trace.get("run_id")
            require(isinstance(run_id, str) and run_id in raw_run_policies,
                    f"{trace_label} has no matching raw run_id")
            require(trace.get("policy") == raw_run_policies[run_id],
                    f"{trace_label} policy does not match its raw role")
            trace_run_ids.add(run_id)
        require(trace_run_ids == set(raw_run_policies),
                f"{label} energy trace does not cover every measured endpoint role")

    require(measured_policy_names == expected_policy_names,
            "completed measurement does not contain exactly the profile's required endpoints")
    policy_ids = sorted(POLICY_IDS[name] for name in measured_policy_names)
    policy_names = [POLICY_NAMES_BY_ID[policy_id] for policy_id in policy_ids]
    return sorted(measured_cols), policy_ids, policy_names


def require_capture(
    captures: Mapping[str, Any], *, softmax_cols: int, policy_id: int,
    policy_name: str, native_arch: int, range_kernel_symbol: str,
) -> None:
    width_key = f"s{softmax_cols}"
    capture_key = f"policy_{policy_id}"
    width_captures = captures.get(width_key)
    require(isinstance(width_captures, dict), f"SASS audit lacks captures.{width_key}")
    capture = width_captures.get(capture_key)
    require(isinstance(capture, dict),
            f"SASS audit lacks captures.{width_key}.{capture_key}")
    require(capture.get("policy_id") == policy_id and capture.get("policy") == policy_name,
            f"SASS audit capture identity drifted for S={softmax_cols}/{policy_name}")
    require(capture.get("pass") is True,
            f"SASS audit capture failed for S={softmax_cols}/{policy_name}")
    ptx_entries = capture.get("ptx_entries")
    sass_entries = capture.get("sass_entries")
    require(isinstance(ptx_entries, list) and len(ptx_entries) == 1 and
            all(isinstance(entry, str) and range_kernel_symbol in entry for entry in ptx_entries),
            f"SASS audit PTX capture is not one range-kernel entry for S={softmax_cols}/{policy_name}")
    require(isinstance(sass_entries, list) and len(sass_entries) == 1 and
            all(isinstance(entry, str) and range_kernel_symbol in entry for entry in sass_entries),
            f"SASS audit SASS capture is not one range-kernel entry for S={softmax_cols}/{policy_name}")
    ptx_checks = capture.get("ptx_checks")
    require(isinstance(ptx_checks, list) and ptx_checks and
            all(isinstance(check, dict) and check.get("pass") is True for check in ptx_checks),
            f"SASS audit PTX checks do not pass for S={softmax_cols}/{policy_name}")
    provenance = capture.get("sass_provenance")
    require(isinstance(provenance, dict),
            f"SASS audit lacks SASS provenance for S={softmax_cols}/{policy_name}")
    require(provenance.get("native_arch_header_present") is True and
            provenance.get("target_native_only") is True,
            f"SASS audit native-only provenance is missing for S={softmax_cols}/{policy_name}")
    header = provenance.get("native_arch_header")
    require(isinstance(header, str) and f"sm_{native_arch}" in header,
            f"SASS audit native architecture header drifted for S={softmax_cols}/{policy_name}")


def require_v100_unsupported_evidence(contract: Mapping[str, Any]) -> None:
    unsupported = contract.get("unsupported_policies")
    require(isinstance(unsupported, dict),
            "V100 audit lacks unsupported native-f16 endpoint evidence")
    for policy_id in (8, 9):
        key = f"policy_{policy_id}"
        item = unsupported.get(key)
        require(isinstance(item, dict), f"V100 audit lacks {key} unsupported evidence")
        require(item.get("policy_id") == policy_id and
                item.get("policy") == POLICY_NAMES_BY_ID[policy_id] and
                item.get("pass") is True and
                item.get("status") == "unsupported_native_fp16_ex2_sm70" and
                item.get("min_native_cuda_arch") == 75 and
                item.get("target_native_cuda_arch") == 70,
                f"V100 audit unsupported evidence drifted for {key}")


def require_range_audit(
    audit: Mapping[str, Any], *, binary_sha: str, profile_name: str,
    native_arch: int, required_cols: list[int], required_policy_ids: list[int],
    required_policy_names: list[str],
) -> None:
    require(audit.get("schema_version") == AUDIT_SCHEMA,
            "SASS audit schema is not the whole-Softmax range static-audit schema")
    overall = audit.get("overall")
    require(isinstance(overall, dict) and overall.get("pass") is True and
            overall.get("fail_on_unexpected") is True and
            overall.get("unexpected_check_ids") == [],
            "SASS audit does not pass with --fail-on-unexpected")
    binary = audit.get("binary")
    require(isinstance(binary, dict) and binary.get("sha256") == binary_sha,
            "SASS audit binary SHA-256 does not match the frozen measurement binary")
    require(binary.get("native_architectures") == [native_arch],
            "SASS audit native cubin architecture does not match the target profile")
    require(binary.get("embedded_ptx_architectures") == [native_arch],
            "SASS audit embedded PTX architecture does not match the target profile")

    contract = audit.get("contract")
    require(isinstance(contract, dict), "SASS audit contract is invalid")
    require(contract.get("target_profile") == profile_name,
            "SASS audit target profile does not match the measurement manifest")
    require(contract.get("native_cuda_arch") == native_arch,
            "SASS audit native CUDA architecture does not match the measurement manifest")
    require(contract.get("required_softmax_cols") == required_cols,
            "SASS audit required S set does not match completed measurements")
    require(contract.get("required_policy_ids") == required_policy_ids,
            "SASS audit required policy IDs do not match completed measurements")
    require(contract.get("required_policy_names") == required_policy_names,
            "SASS audit required policy names do not match completed measurements")
    range_kernel_symbol = contract.get("range_kernel_symbol")
    require(isinstance(range_kernel_symbol, str) and bool(range_kernel_symbol),
            "SASS audit range kernel symbol is missing")

    captures = audit.get("captures")
    require(isinstance(captures, dict), "SASS audit captures are invalid")
    for softmax_cols in required_cols:
        for policy_id, policy_name in zip(required_policy_ids, required_policy_names):
            require_capture(captures, softmax_cols=softmax_cols, policy_id=policy_id,
                            policy_name=policy_name, native_arch=native_arch,
                            range_kernel_symbol=range_kernel_symbol)
    if profile_name == "v100":
        require_v100_unsupported_evidence(contract)


def require_run_local_audit_artifacts(
    audit: Mapping[str, Any], run_dir: Path, frozen_binary: Path, binary_sha: str
) -> None:
    """Keep the human-inspectable cuobjdump evidence in the bound run package."""

    binary = audit.get("binary")
    require(isinstance(binary, dict), "SASS audit binary record is invalid")
    audit_binary = resolve(binary.get("path"), run_dir)
    require(audit_binary == frozen_binary.resolve() and sha256_file(audit_binary) == binary_sha,
            "SASS audit binary path is not the frozen measurement executable")
    raw_captures = audit.get("cuobjdump_captures")
    require(isinstance(raw_captures, dict), "SASS audit raw cuobjdump captures are missing")
    for name in ("list_elf", "list_ptx", "dump_ptx", "dump_sass"):
        item = raw_captures.get(name)
        require(isinstance(item, dict), f"SASS audit raw capture {name} is invalid")
        expected_sha = item.get("sha256")
        require(is_sha256(expected_sha), f"SASS audit raw capture {name} SHA-256 is invalid")
        capture = resolve(item.get("path"), run_dir)
        require(capture.is_file() and not capture.is_symlink() and is_within(capture, run_dir),
                f"SASS audit raw capture {name} is not a regular run-local artifact")
        require(sha256_file(capture) == expected_sha,
                f"SASS audit raw capture {name} SHA-256 mismatch")


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--sass-audit", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    require(manifest_path.is_file(), f"manifest is missing: {manifest_path}")
    manifest = read_json(manifest_path, "manifest")
    require(manifest.get("schema_version") == MANIFEST_SCHEMA,
            "manifest is not a whole-Softmax range manifest")
    profile = manifest.get("profile")
    require(isinstance(profile, dict) and isinstance(profile.get("name"), str),
            "manifest profile is invalid")
    profile_name = profile["name"]
    require(profile_name in PLATFORM_PROFILES, "manifest target profile is unsupported")
    expected_profile = PLATFORM_PROFILES[profile_name]
    native_arch = expected_profile.cuda_arch
    require(profile.get("cuda_arch") == native_arch,
            "manifest profile CUDA architecture drifted from the platform contract")

    frozen_binary, binary_sha = require_frozen_artifact(manifest, "binary", run_dir)
    _, runner_sha = require_frozen_artifact(manifest, "runner", run_dir)
    required_cols, required_policy_ids, required_policy_names = require_completed_measurement(
        manifest, run_dir, profile_name, binary_sha, native_arch
    )

    expected_audit_path = run_dir / "sass_audit.json"
    require(expected_audit_path.is_file() and not expected_audit_path.is_symlink(),
            "SASS audit must be a regular file at <run-dir>/sass_audit.json")
    audit_path = args.sass_audit.resolve()
    require(audit_path == expected_audit_path.resolve(),
            "SASS audit must be stored at <run-dir>/sass_audit.json for a portable bound run")
    audit = read_json(audit_path, "SASS audit")
    require_range_audit(
        audit, binary_sha=binary_sha, profile_name=profile_name, native_arch=native_arch,
        required_cols=required_cols, required_policy_ids=required_policy_ids,
        required_policy_names=required_policy_names,
    )
    require_run_local_audit_artifacts(audit, run_dir, frozen_binary, binary_sha)
    audit_sha = sha256_file(audit_path)
    captures = [
        {"softmax_cols": softmax_cols, "policy_id": policy_id,
         "policy": POLICY_NAMES_BY_ID[policy_id]}
        for softmax_cols in required_cols for policy_id in required_policy_ids
    ]
    binding = {
        "path": repo_path(audit_path),
        "sha256": audit_sha,
        "binary_sha256": binary_sha,
        "runner_sha256": runner_sha,
        "target_profile": profile_name,
        "native_cuda_arch": native_arch,
        "required_softmax_cols": required_cols,
        "required_policy_ids": required_policy_ids,
        "required_policy_names": required_policy_names,
        "required_captures": captures,
        "evidence_generation": "post_execution_static_audit_v1",
        "generated_after_execution": True,
        "bound_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "binder": {
            "path": repo_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
    }
    existing = manifest.get("sass_audit")
    if existing is not None:
        require(isinstance(existing, dict), "manifest sass_audit binding is invalid")
        keys = (
            "path", "sha256", "binary_sha256", "runner_sha256", "target_profile",
            "native_cuda_arch", "required_softmax_cols", "required_policy_ids",
            "required_policy_names", "required_captures",
        )
        if {key: existing.get(key) for key in keys} != {key: binding.get(key) for key in keys}:
            raise SystemExit("manifest already binds a different SASS audit; refusing replacement")
        print("sass_binding_status=already_bound")
        return 0
    manifest["sass_audit"] = binding
    atomic_write_json(manifest_path, manifest)
    print("sass_binding_status=bound")
    print(f"manifest={repo_path(manifest_path)}")
    print(f"sass_audit={binding['path']}")
    print(f"sass_audit_sha256={audit_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
