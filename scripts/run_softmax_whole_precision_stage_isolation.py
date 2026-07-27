#!/usr/bin/env python3
"""Plan and run the bounded RTX 3090 whole-Softmax precision experiment.

This is deliberately a new execution path.  The older Softmax EX2 scripts
measure a same-kernel *extra exponent* probe and report pJ per added logical
EX2 result; those artifacts are not compatible with a complete-Softmax
precision comparison.  Here every measured role executes one complete
Softmax and the C++ binary reports pJ per logical output element.

The initial design fixes S=512 and CTA grid_blocks=16.  For each stage group
we compare a common FP16-I/O/FP32-stage baseline with scalar and packed FP16
variants in three cyclic orders:

    A,B,C ; C,A,B ; B,C,A

Each order is launched as its own binary process/CUDA context.  That gives
three position-balanced sessions per stage group, or 27 measured policy roles
across exp, max/sum reduction, and normalization.  This script only creates
the plan/manifest by default; ``--execute`` is deliberately required to start
energy measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_REVISION = "rtx3090_softmax_whole_precision_stage_isolation_v1"
MANIFEST_SCHEMA = "softmax_whole_precision_stage_isolation_manifest_v1"
TARGET_PROFILE = "rtx3090"
TARGET_BINARY = "a100_fp16_softmax_whole_precision_energy"

# The C++ whole-precision implementation intentionally fixes these values.
SOFTMAX_COLS = 512
GRID_BLOCKS = 16
SECONDS = 13.0
PREHEAT_SECONDS = 20.0
IDLE_SECONDS = 1.0
TRACE_SAMPLE_MS = 500.0
TRACE_MIN_UPDATES = 16
LOGIT_SCALE = 4.0

BASELINE_POLICY = "fp16_io_fp32_all"


@dataclass(frozen=True)
class StageGroup:
    """One one-stage-at-a-time precision comparison."""

    name: str
    scalar_policy: str
    packed_policy: str
    description: str

    @property
    def policies(self) -> tuple[str, str, str]:
        return (BASELINE_POLICY, self.scalar_policy, self.packed_policy)


STAGE_GROUPS: tuple[StageGroup, ...] = (
    StageGroup(
        "exp",
        "exp_fp16_scalar",
        "exp_fp16x2",
        "FP16 scalar/packed exponent only; max/sum and normalization remain FP32",
    ),
    StageGroup(
        "reduction",
        "reduction_fp16_scalar",
        "reduction_fp16x2",
        "FP16 scalar/packed max and sum reduction only; exponent and normalization remain FP32",
    ),
    StageGroup(
        "normalization",
        "normalization_fp16_scalar",
        "normalization_fp16x2",
        "FP16 scalar/packed probability multiply with FP16-rounded reciprocal; exponent and max/sum remain FP32",
    ),
)
STAGE_BY_NAME = {group.name: group for group in STAGE_GROUPS}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative_or_absolute(path: Path) -> str:
    """Use repository-relative paths where that does not lose information."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def validate_session_tag(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise argparse.ArgumentTypeError(
            "--session-tag must contain only letters, digits, '.', '_' or '-' "
            "and must not begin with punctuation"
        )
    return value


def default_session_tag() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def cyclic_orders(group: StageGroup) -> tuple[tuple[str, str, str], ...]:
    """Return exactly ABC, CAB, BCA for a three-policy stage group."""

    baseline, scalar, packed = group.policies
    return (
        (baseline, scalar, packed),
        (packed, baseline, scalar),
        (scalar, packed, baseline),
    )


def selected_stage_groups(only_stage: Iterable[str] | None) -> tuple[StageGroup, ...]:
    if not only_stage:
        return STAGE_GROUPS
    names = tuple(only_stage)
    selected = tuple(STAGE_BY_NAME[name] for name in names)
    # argparse permits a repeated option; preserve canonical stage ordering and
    # reject accidental duplicate requests instead of measuring a group twice.
    if len(set(names)) != len(names):
        raise ValueError("--only-stage may not name the same stage more than once")
    return tuple(group for group in STAGE_GROUPS if group in selected)


def build_command(
    *,
    binary: Path,
    binary_sha256: str,
    gpu_id: int,
    session_id: str,
    stage_group: str,
    session_order: str,
    schedule: tuple[str, str, str],
    raw_csv: Path,
    trace_csv: Path,
) -> list[str]:
    """Build one complete, fresh-process three-policy session command."""

    return [
        str(binary),
        "--gpu-id",
        str(gpu_id),
        "--target-profile",
        TARGET_PROFILE,
        "--design-id",
        "stage_isolation_v1",
        "--stage-group",
        stage_group,
        "--session-order",
        session_order,
        "--policy-schedule",
        ",".join(schedule),
        "--grid-blocks",
        str(GRID_BLOCKS),
        "--seconds",
        f"{SECONDS:.1f}",
        "--preheat-seconds",
        f"{PREHEAT_SECONDS:.1f}",
        "--idle-seconds",
        f"{IDLE_SECONDS:.1f}",
        "--energy-trace-sample-ms",
        f"{TRACE_SAMPLE_MS:.1f}",
        "--energy-trace-min-updates",
        str(TRACE_MIN_UPDATES),
        "--logit-scale",
        f"{LOGIT_SCALE:.1f}",
        "--session-id",
        session_id,
        "--output",
        str(raw_csv),
        "--energy-trace-output",
        str(trace_csv),
        "--binary-sha256",
        binary_sha256,
    ]


def build_sessions(
    *,
    run_root: Path,
    session_tag: str,
    groups: tuple[StageGroup, ...],
    binary: Path,
    binary_sha256: str,
    gpu_id: int,
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    global_index = 0
    for group in groups:
        for session_index, schedule in enumerate(cyclic_orders(group), start=1):
            global_index += 1
            letter_by_policy = dict(zip(group.policies, "ABC"))
            session_order = "".join(letter_by_policy[policy] for policy in schedule)
            session_id = f"{session_tag}_{group.name}_session{session_index:02d}"
            prefix = f"{group.name}_session{session_index:02d}"
            raw_csv = run_root / f"{prefix}_raw.csv"
            trace_csv = run_root / f"{prefix}_energy_trace.csv"
            command = build_command(
                binary=binary,
                binary_sha256=binary_sha256,
                gpu_id=gpu_id,
                session_id=session_id,
                stage_group=group.name,
                session_order=session_order,
                schedule=schedule,
                raw_csv=raw_csv,
                trace_csv=trace_csv,
            )
            sessions.append(
                {
                    "global_session_index": global_index,
                    "stage_group": group.name,
                    "stage_description": group.description,
                    "session_index_within_stage": session_index,
                    "session_order": session_order,
                    "session_id": session_id,
                    "schedule_label": ",".join(schedule),
                    "policy_schedule": list(schedule),
                    "expected_measured_roles": len(schedule),
                    "raw_csv": relative_or_absolute(raw_csv),
                    "energy_trace_csv": relative_or_absolute(trace_csv),
                    "command": command,
                    "command_shell": shlex.join(command),
                    "status": "planned",
                    "returncode": None,
                }
            )
    return sessions


def immutable_manifest_view(manifest: dict[str, Any]) -> dict[str, Any]:
    """Fields that must match before a planned run directory is reused."""

    return {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "protocol_revision",
            "run_tag",
            "binary",
            "runner",
            "design",
            "sessions",
        )
    }


def expected_artifacts(sessions: Iterable[dict[str, Any]]) -> list[Path]:
    artifacts: list[Path] = []
    for session in sessions:
        artifacts.append(Path(str(session["raw_csv"])))
        artifacts.append(Path(str(session["energy_trace_csv"])))
    return artifacts


def resolve_manifest_artifact(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def prepare_manifest(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Create a fresh plan or safely reuse an identical plan-only manifest."""

    if not manifest_path.exists():
        atomic_write_json(manifest_path, manifest)
        return manifest

    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot reuse invalid manifest: {manifest_path}") from error
    if immutable_manifest_view(existing) != immutable_manifest_view(manifest):
        raise RuntimeError(
            "existing manifest differs from this requested experiment; choose a new "
            "--session-tag rather than mixing evidence"
        )
    return existing


def verify_empty_session_outputs(manifest: dict[str, Any]) -> None:
    present = [
        path
        for path in expected_artifacts(manifest["sessions"])
        if resolve_manifest_artifact(path).exists()
    ]
    if present:
        rendered = ", ".join(str(path) for path in present[:6])
        if len(present) > 6:
            rendered += f", ... ({len(present)} total)"
        raise RuntimeError(
            "refusing to overwrite existing measured artifacts: " + rendered
        )


def print_plan(manifest: dict[str, Any]) -> None:
    print(
        "whole_precision_design="
        f"stage_isolation; stages={','.join(manifest['design']['stage_groups'])}; "
        f"sessions={len(manifest['sessions'])}; "
        f"measured_roles={manifest['design']['expected_measured_roles']}",
        flush=True,
    )
    print(f"manifest={manifest['manifest_path']}", flush=True)
    for session in manifest["sessions"]:
        print(
            f"session={session['global_session_index']:02d} "
            f"stage={session['stage_group']} "
            f"order={session['session_index_within_stage']} "
            f"schedule={session['schedule_label']}",
            flush=True,
        )
        print("+ " + session["command_shell"], flush=True)


def execute_sessions(manifest_path: Path, manifest: dict[str, Any]) -> int:
    """Run each schedule in a distinct binary process and update provenance."""

    verify_empty_session_outputs(manifest)
    manifest["execution"] = {
        "requested": True,
        "started_at": timestamp(),
        "finished_at": None,
        "status": "running",
    }
    atomic_write_json(manifest_path, manifest)

    for session in manifest["sessions"]:
        session["status"] = "running"
        session["started_at"] = timestamp()
        atomic_write_json(manifest_path, manifest)
        command = [str(value) for value in session["command"]]
        print("+ " + shlex.join(command), flush=True)
        result = subprocess.run(command, cwd=REPO_ROOT, check=False)
        session["returncode"] = result.returncode
        session["finished_at"] = timestamp()
        if result.returncode != 0:
            session["status"] = "failed"
            manifest["execution"].update(
                {"finished_at": timestamp(), "status": "failed"}
            )
            atomic_write_json(manifest_path, manifest)
            print(
                f"failed_session={session['session_id']} returncode={result.returncode}",
                file=sys.stderr,
            )
            return result.returncode or 1

        raw = resolve_manifest_artifact(Path(str(session["raw_csv"])))
        trace = resolve_manifest_artifact(Path(str(session["energy_trace_csv"])))
        missing = [path for path in (raw, trace) if not path.is_file() or path.stat().st_size == 0]
        if missing:
            session["status"] = "failed_missing_artifact"
            session["missing_artifacts"] = [str(path) for path in missing]
            manifest["execution"].update(
                {"finished_at": timestamp(), "status": "failed"}
            )
            atomic_write_json(manifest_path, manifest)
            print(
                f"failed_session={session['session_id']} missing_artifact="
                + ",".join(str(path) for path in missing),
                file=sys.stderr,
            )
            return 1
        session["raw_csv_sha256"] = sha256_file(raw)
        session["energy_trace_csv_sha256"] = sha256_file(trace)
        session["status"] = "complete_unanalyzed"
        atomic_write_json(manifest_path, manifest)

    manifest["execution"].update({"finished_at": timestamp(), "status": "complete_unanalyzed"})
    atomic_write_json(manifest_path, manifest)
    print("execution_status=complete_unanalyzed", flush=True)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or explicitly execute the bounded RTX 3090 whole-Softmax "
            "precision stage-isolation experiment."
        )
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path("build-whole-precision-rtx3090"),
        help=(
            "directory containing " + TARGET_BINARY + " "
            "(default: build-whole-precision-rtx3090)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/raw"),
        help="base directory; this runner creates one new run-tag subdirectory",
    )
    parser.add_argument(
        "--session-tag",
        type=validate_session_tag,
        default=default_session_tag(),
        help="immutable run tag used in the manifest, file names, and C++ session IDs",
    )
    parser.add_argument(
        "--only-stage",
        action="append",
        choices=tuple(STAGE_BY_NAME),
        help="run only this stage group; may be supplied once per selected group",
    )
    parser.add_argument("--gpu-id", type=int, default=0, help="CUDA/NVML GPU index")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write/reuse the immutable manifest and print every command without running it",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="start the energy measurements; absent by default to prevent accidental runs",
    )
    arguments = parser.parse_args(argv)
    if arguments.dry_run and arguments.execute:
        parser.error("--dry-run and --execute are mutually exclusive")
    if arguments.gpu_id < 0:
        parser.error("--gpu-id must be non-negative")
    if arguments.only_stage and len(set(arguments.only_stage)) != len(arguments.only_stage):
        parser.error("--only-stage may not name the same stage more than once")
    return arguments


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    groups = selected_stage_groups(args.only_stage)
    binary = (REPO_ROOT / args.build_dir / TARGET_BINARY).resolve()
    if not binary.is_file():
        raise SystemExit(
            "whole-precision binary is missing: " + str(binary) + "\n"
            "Build it first, for example:\n"
            "  cmake --build " + str(args.build_dir) + " --target " + TARGET_BINARY
        )
    if not os.access(binary, os.X_OK):
        raise SystemExit("whole-precision binary is not executable: " + str(binary))

    output_base = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    run_root = (output_base / f"rtx3090_softmax_whole_precision_stage_isolation_{args.session_tag}").resolve()
    manifest_path = run_root / "manifest.json"
    binary_sha256 = sha256_file(binary)
    runner_path = Path(__file__).resolve()
    runner_sha256 = sha256_file(runner_path)
    sessions = build_sessions(
        run_root=run_root,
        session_tag=args.session_tag,
        groups=groups,
        binary=binary,
        binary_sha256=binary_sha256,
        gpu_id=args.gpu_id,
    )
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "protocol_revision": PROTOCOL_REVISION,
        "run_tag": args.session_tag,
        "created_at": timestamp(),
        "manifest_path": relative_or_absolute(manifest_path),
        "binary": {
            "path": relative_or_absolute(binary),
            "sha256": binary_sha256,
        },
        "runner": {
            "path": relative_or_absolute(runner_path),
            "sha256": runner_sha256,
        },
        "design": {
            "target_profile": TARGET_PROFILE,
            "gpu_id": args.gpu_id,
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "seconds_per_policy": SECONDS,
            "preheat_seconds": PREHEAT_SECONDS,
            "idle_seconds": IDLE_SECONDS,
            "energy_trace_sample_ms": TRACE_SAMPLE_MS,
            "energy_trace_min_updates": TRACE_MIN_UPDATES,
            "logit_scale": LOGIT_SCALE,
            "baseline_policy": BASELINE_POLICY,
            "stage_groups": [group.name for group in groups],
            "order_algorithm": "cyclic_ABC_CAB_BCA_v1",
            "fresh_binary_process_per_schedule": True,
            "expected_sessions": len(sessions),
            "expected_measured_roles": len(sessions) * 3,
            "primary_metric": "net_pJ_per_logical_output_element",
            "ex2_operand_rate_atc_compatible": False,
            "temperature_hard_gate": False,
        },
        "sessions": sessions,
        "execution": {
            "requested": bool(args.execute),
            "dry_run": bool(args.dry_run),
            "status": "planned",
            "started_at": None,
            "finished_at": None,
        },
    }

    run_root.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists() and any(run_root.iterdir()):
        raise SystemExit(
            "run directory exists without this manifest and is not empty: "
            + str(run_root)
            + "; choose a new --session-tag"
        )
    manifest = prepare_manifest(manifest_path=manifest_path, manifest=manifest)
    print_plan(manifest)
    if not args.execute:
        print("execution_status=planned (use --execute to run)", flush=True)
        return 0
    return execute_sessions(manifest_path, manifest)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
