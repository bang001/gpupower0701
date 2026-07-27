#!/usr/bin/env python3
"""Bind a passing SASS audit to one completed confirmation manifest.

The measurement runner freezes and records the executable before first use.
This narrow post-run utility records the static audit only after checking that
the audit inspected that exact frozen executable.  It refuses to replace an
existing different binding, so a report/analyzer can fail closed on both the
manifest and the audit SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_SCHEMA = "softmax_whole_precision_targeted_confirmation_manifest_v1"
AUDIT_SCHEMA = "softmax_whole_precision_sass_audit_v1"
EXPECTED_ARCH = 86
EXPECTED_SCOPE = "whole_softmax_precision_kernel"
EXPECTED_SOFTMAX_COLS = 512
EXPECTED_ROWS_PER_BLOCK = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve(value: str, run_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = REPO_ROOT / path
    return candidate if candidate.exists() else run_dir / path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def require_completed_measurement(manifest: dict[str, Any], run_dir: Path) -> None:
    """Refuse to race the runner or bind an incomplete acquisition."""
    execution = manifest.get("execution")
    require(isinstance(execution, dict), "manifest.execution is invalid")
    require(execution.get("requested") is True, "measurement execution was not requested")
    require(execution.get("status") in {"complete", "complete_unanalyzed"},
            "measurement execution is not complete; refusing to bind during acquisition")
    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and sessions,
            "manifest has no completed measurement sessions")
    for index, session in enumerate(sessions, start=1):
        require(isinstance(session, dict), f"manifest session {index} is invalid")
        require(session.get("status") in {"complete", "complete_unanalyzed"},
                f"manifest session {index} is not complete")
        require(session.get("returncode") == 0,
                f"manifest session {index} did not exit successfully")
        for path_key, hash_key in (
            ("raw_csv", "raw_csv_sha256"),
            ("energy_trace_csv", "energy_trace_csv_sha256"),
        ):
            expected_hash = session.get(hash_key)
            require(isinstance(expected_hash, str) and len(expected_hash) == 64,
                    f"manifest session {index} lacks {hash_key}")
            artifact = resolve(str(session.get(path_key, "")), run_dir)
            require(artifact.is_file() and sha256_file(artifact) == expected_hash,
                    f"manifest session {index} {path_key} does not match its recorded SHA-256")


def require_confirmation_audit(audit: dict[str, Any], binary_sha: str) -> None:
    require(audit.get("schema_version") == AUDIT_SCHEMA,
            "SASS audit schema is not the whole-Softmax audit schema")
    require(audit.get("overall", {}).get("pass") is True,
            "SASS audit does not pass")
    require(audit.get("overall", {}).get("fail_on_unexpected") is True,
            "SASS audit was not generated with --fail-on-unexpected")
    require(audit.get("overall", {}).get("unexpected_check_ids") == [],
            "SASS audit has unexpected failed checks")
    require(audit.get("binary", {}).get("sha256") == binary_sha,
            "SASS audit binary SHA-256 does not match frozen measurement binary")
    contract = audit.get("contract")
    require(isinstance(contract, dict), "SASS audit contract is invalid")
    require(contract.get("expected_cuda_arch") == EXPECTED_ARCH,
            "SASS audit architecture is not sm86")
    require(contract.get("scope") == EXPECTED_SCOPE,
            "SASS audit scope is not the whole-Softmax precision kernel")
    require(contract.get("softmax_cols") == EXPECTED_SOFTMAX_COLS,
            "SASS audit softmax width does not match the confirmation")
    require(contract.get("rows_per_block") == EXPECTED_ROWS_PER_BLOCK,
            "SASS audit rows-per-block does not match the confirmation")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--sass-audit", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise SystemExit("manifest is not a targeted-confirmation manifest")
    require_completed_measurement(manifest, run_dir)
    binary = manifest.get("binary", {})
    binary_path = resolve(str(binary.get("path", "")), run_dir)
    binary_sha = str(binary.get("sha256", ""))
    if not binary_path.is_file() or sha256_file(binary_path) != binary_sha:
        raise SystemExit("manifest frozen binary does not match its recorded SHA-256")
    audit_path = args.sass_audit.resolve()
    if not audit_path.is_file():
        raise SystemExit(f"SASS audit is missing: {audit_path}")
    expected_audit_path = (run_dir / "sass_audit.json").resolve()
    require(audit_path == expected_audit_path,
            "SASS audit must be stored at <run-dir>/sass_audit.json for a portable bound run")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    require_confirmation_audit(audit, binary_sha)
    binding = {
        "path": repo_path(audit_path),
        "sha256": sha256_file(audit_path),
        "binary_sha256": binary_sha,
        "evidence_generation": "post_execution_static_audit_v1",
        "generated_after_execution": True,
        "bound_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "binder": {"path": repo_path(Path(__file__)), "sha256": sha256_file(Path(__file__))},
    }
    existing = manifest.get("sass_audit")
    if existing is not None:
        comparable = {key: existing.get(key) for key in ("path", "sha256", "binary_sha256")}
        proposed = {key: binding.get(key) for key in ("path", "sha256", "binary_sha256")}
        if comparable != proposed:
            raise SystemExit("manifest already binds a different SASS audit; refusing replacement")
        print("sass_binding_status=already_bound")
        return 0
    manifest["sass_audit"] = binding
    atomic_write_json(manifest_path, manifest)
    print("sass_binding_status=bound")
    print(f"manifest={repo_path(manifest_path)}")
    print(f"sass_audit={binding['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
