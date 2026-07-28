#!/usr/bin/env python3
"""Plan or acquire the minimal whole-Softmax precision range experiment.

The experiment answers a deliberately narrow question: within a predeclared
compute/cache-reuse envelope, which complete Softmax endpoint is observed as
best, representative, and worst in net pJ per *element* (one logical Softmax
output element)?  It
does not pool the older EX2 Operand-rate ATC data or the fixed-S=512
stage-isolation data.

The initial screen has four coordinates only:

* S=512 at 50% of runtime SMs (natural two-elements/thread anchor),
* S=1024 at 50% (predeclared representative / plateau-entry hypothesis),
* S=4096 at 50% (large-width resource boundary), and
* S=1024 at 25% (concurrency sensitivity).

Each three-way platform uses three fresh CUDA processes per coordinate in the
ABC/BCA/CAB rotations.  V100 deliberately runs FP32 only: the two FP16
endpoints use native f16 EX2 instructions that require sm_75 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from softmax_platform_profiles import PLATFORM_PROFILES, profile_for


ROOT = Path(__file__).resolve().parents[1]
TARGET_BINARY = "a100_fp16_softmax_whole_precision_range_energy"
MANIFEST_SCHEMA = "softmax_whole_precision_range_manifest_v1"
RAW_SCHEMA = "softmax_whole_precision_range_v1"
EXPERIMENT_KIND = "whole_softmax_precision_range"
PROTOCOL_REVISION = "whole_softmax_precision_range_common_v1"
DESIGN_ID = "whole_precision_range_v1"
CONDITIONING_MODE = "endpoint_range_common_v1"

POLICIES = (
    "fp32_io_fp32_all",
    "fp16_scalar_all",
    "fp16x2_all",
)
POLICY_ORDERS = {
    "ABC": POLICIES,
    "BCA": (POLICIES[1], POLICIES[2], POLICIES[0]),
    "CAB": (POLICIES[2], POLICIES[0], POLICIES[1]),
}
ORDER_CYCLE = tuple(POLICY_ORDERS)

SECONDS = 13.0
PREHEAT_SECONDS = 5.0
IDLE_SECONDS = 1.0
TRACE_SAMPLE_MS = 500.0
TRACE_MIN_UPDATES = 16
LOGIT_SCALE = 4.0
SEED = 5573589319906701683
REPETITIONS = 3


@dataclass(frozen=True)
class Coordinate:
    identifier: str
    softmax_cols: int
    sm_coverage: float
    purpose: str


COORDINATES: dict[str, Coordinate] = {
    "s512_q50": Coordinate(
        "s512_q50", 512, 0.50,
        "natural two-elements-per-thread anchor",
    ),
    "s1024_q50": Coordinate(
        "s1024_q50", 1024, 0.50,
        "predeclared representative and plateau-entry hypothesis",
    ),
    "s4096_q50": Coordinate(
        "s4096_q50", 4096, 0.50,
        "large-width resource and occupancy boundary",
    ),
    "s1024_q25": Coordinate(
        "s1024_q25", 1024, 0.25,
        "concurrency-sensitivity anchor",
    ),
    "s2048_q50": Coordinate(
        "s2048_q50", 2048, 0.50,
        "adaptive midpoint; run only when the plateau gate fails",
    ),
    "s512_q25": Coordinate(
        "s512_q25", 512, 0.25,
        "adaptive low-coverage short-width follow-up",
    ),
    "s4096_q25": Coordinate(
        "s4096_q25", 4096, 0.25,
        "adaptive low-coverage large-width follow-up",
    ),
}
SCREEN_COORDINATES = ("s512_q50", "s1024_q50", "s4096_q50", "s1024_q25")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
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


def default_binary(build_dir: Path) -> Path:
    return build_dir / TARGET_BINARY


def grid_blocks(runtime_sm_count: int, coverage: float) -> int:
    if runtime_sm_count <= 0 or not (0.0 < coverage <= 1.0):
        raise ValueError("invalid SM count or coverage")
    return max(1, math.ceil(runtime_sm_count * coverage))


def runnable_policies(profile_name: str) -> tuple[str, ...]:
    # Do not substitute an emulation on V100.  The FP32 endpoint still has a
    # useful standalone range, but it is not a three-way comparison.
    return (POLICIES[0],) if profile_name == "v100" else POLICIES


def selected_coordinates(phase: str, value: str | None) -> tuple[Coordinate, ...]:
    if value is None:
        if phase != "screen":
            raise ValueError("--coordinates is required for followup or confirmation")
        names = SCREEN_COORDINATES
    else:
        names = tuple(item.strip() for item in value.split(",") if item.strip())
        if not names:
            raise ValueError("--coordinates must name at least one coordinate")
    unknown = [name for name in names if name not in COORDINATES]
    if unknown:
        raise ValueError("unknown range coordinate(s): " + ", ".join(unknown))
    if len(set(names)) != len(names):
        raise ValueError("--coordinates must not repeat a coordinate")
    if phase == "screen" and names != SCREEN_COORDINATES:
        raise ValueError(
            "the initial screen is the fixed four-coordinate design; "
            "use a followup/confirmation phase for any other declared coordinate"
        )
    return tuple(COORDINATES[name] for name in names)


def freeze(source: Path, destination: Path) -> dict[str, str]:
    if not source.is_file():
        raise RuntimeError(f"required file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if os.access(source, os.X_OK):
        destination.chmod(destination.stat().st_mode | 0o111)
    return {"path": repo_path(destination), "sha256": sha256_file(destination)}


def build_command(
    *,
    binary: Path,
    binary_sha256: str,
    profile_name: str,
    gpu_id: int,
    coordinate: Coordinate,
    runtime_sm_count: int,
    policies: tuple[str, ...],
    session_order: str,
    phase: str,
    session_id: str,
    raw_csv: Path,
    trace_csv: Path,
) -> list[str]:
    return [
        str(binary),
        "--gpu-id", str(gpu_id),
        "--target-profile", profile_name,
        "--conditioning-mode", CONDITIONING_MODE,
        "--schema-version", RAW_SCHEMA,
        "--experiment-kind", EXPERIMENT_KIND,
        "--protocol-revision", PROTOCOL_REVISION,
        "--design-id", DESIGN_ID,
        "--stage-group", "endpoint_range",
        "--session-order", session_order,
        "--policy-schedule", ",".join(policies),
        "--grid-blocks", str(grid_blocks(runtime_sm_count, coordinate.sm_coverage)),
        "--softmax-cols", str(coordinate.softmax_cols),
        "--seconds", f"{SECONDS:.1f}",
        "--preheat-seconds", f"{PREHEAT_SECONDS:.1f}",
        "--idle-seconds", f"{IDLE_SECONDS:.1f}",
        "--energy-trace-sample-ms", f"{TRACE_SAMPLE_MS:.1f}",
        "--energy-trace-min-updates", str(TRACE_MIN_UPDATES),
        "--logit-scale", f"{LOGIT_SCALE:.1f}",
        "--seed", str(SEED),
        "--range-phase", phase,
        "--coordinate-id", coordinate.identifier,
        "--requested-sm-coverage", f"{coordinate.sm_coverage:.6f}",
        "--session-id", session_id,
        "--output", str(raw_csv),
        "--energy-trace-output", str(trace_csv),
        "--binary-sha256", binary_sha256,
    ]


def build_sessions(
    *,
    root: Path,
    tag: str,
    phase: str,
    profile_name: str,
    gpu_id: int,
    binary: Path,
    binary_sha256: str,
    runtime_sm_count: int,
    coordinates: tuple[Coordinate, ...],
) -> list[dict[str, Any]]:
    policies = runnable_policies(profile_name)
    sessions: list[dict[str, Any]] = []
    # Interleave coordinates by repetition.  Each coordinate receives the
    # three fixed policy rotations but does not occupy one thermal time block.
    for repetition in range(REPETITIONS):
        rotated = coordinates[repetition:] + coordinates[:repetition]
        for coordinate in rotated:
            order = "A" if len(policies) == 1 else ORDER_CYCLE[repetition]
            schedule = (POLICIES[0],) if order == "A" else POLICY_ORDERS[order]
            grid = grid_blocks(runtime_sm_count, coordinate.sm_coverage)
            prefix = f"{coordinate.identifier}_session{repetition + 1:02d}_{order}"
            session_id = f"{tag}_{prefix}"
            raw_csv = root / f"{prefix}_raw.csv"
            trace_csv = root / f"{prefix}_energy_trace.csv"
            command = build_command(
                binary=binary,
                binary_sha256=binary_sha256,
                profile_name=profile_name,
                gpu_id=gpu_id,
                coordinate=coordinate,
                runtime_sm_count=runtime_sm_count,
                policies=schedule,
                session_order=order,
                phase=phase,
                session_id=session_id,
                raw_csv=raw_csv,
                trace_csv=trace_csv,
            )
            sessions.append(
                {
                    "global_session_index": len(sessions) + 1,
                    "coordinate_id": coordinate.identifier,
                    "softmax_cols": coordinate.softmax_cols,
                    "requested_sm_coverage": coordinate.sm_coverage,
                    "purpose": coordinate.purpose,
                    "runtime_sm_count": runtime_sm_count,
                    "grid_blocks": grid,
                    "session_index_within_coordinate": repetition + 1,
                    "session_order": order,
                    "policy_schedule": list(schedule),
                    "expected_measured_roles": len(schedule),
                    "session_id": session_id,
                    "raw_csv": repo_path(raw_csv),
                    "energy_trace_csv": repo_path(trace_csv),
                    "command": command,
                    "command_shell": shlex.join(command),
                    "status": "planned",
                    "returncode": None,
                    "started_at": None,
                    "finished_at": None,
                }
            )
    return sessions


def parent_binding(parent: str | None, *, phase: str, profile_name: str) -> dict[str, Any] | None:
    if parent is None:
        return None
    if phase not in {"followup", "confirmation"}:
        raise RuntimeError("only a followup or confirmation run may declare --continue-from")
    root = resolve_path(parent)
    manifest = root / "manifest.json"
    if not manifest.is_file():
        raise RuntimeError(f"--continue-from has no manifest: {manifest}")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"--continue-from manifest is unreadable: {error}") from error
    if payload.get("schema_version") != MANIFEST_SCHEMA or payload.get("status") != "complete":
        raise RuntimeError("--continue-from must name a completed range manifest")
    if payload.get("phase") != "screen":
        raise RuntimeError("--continue-from must name an initial screen, not another child run")
    parent_profile = payload.get("profile")
    if not isinstance(parent_profile, dict) or parent_profile.get("name") != profile_name:
        raise RuntimeError("--continue-from profile differs from the requested child profile")
    if not isinstance(payload.get("sass_audit"), dict):
        raise RuntimeError(
            "--continue-from must already have its post-execution SASS/PTX binding before a child run"
        )
    return {"run_dir": repo_path(root), "manifest_sha256": sha256_file(manifest)}


def plan_run(args: argparse.Namespace) -> Path:
    profile = profile_for(args.target_profile)
    coordinates = selected_coordinates(args.phase, args.coordinates)
    if args.runtime_sm_count is None:
        if len(profile.full_sm_counts) != 1:
            raise ValueError(
                f"{args.target_profile} has multiple complete-device SM counts; "
                "pass --runtime-sm-count explicitly so q is not planned against the wrong SKU"
            )
        runtime_sm_count = profile.full_sm_counts[0]
    else:
        runtime_sm_count = args.runtime_sm_count
        if runtime_sm_count not in profile.full_sm_counts:
            raise ValueError(
                f"--runtime-sm-count {runtime_sm_count} is not a complete-device value for "
                f"{args.target_profile}: {profile.full_sm_counts}"
            )
    binary = (Path(args.binary) if args.binary else default_binary(Path(args.build_dir))).resolve()
    if not binary.is_file():
        raise RuntimeError(f"range binary is missing: {binary}")
    parent = parent_binding(
        args.continue_from, phase=args.phase, profile_name=args.target_profile
    )
    tag = args.session_tag or datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_root = (Path(args.output_dir) /
                f"{args.target_profile}_softmax_whole_precision_range_{tag}_{args.phase}").resolve()
    if run_root.exists():
        raise RuntimeError(f"run directory already exists: {run_root}")
    frozen_binary_path = run_root / "frozen" / binary.name
    frozen_binary = freeze(binary, frozen_binary_path)
    frozen_runner = freeze(Path(__file__).resolve(), run_root / "frozen" / Path(__file__).name)
    sessions = build_sessions(
        root=run_root,
        tag=tag,
        phase=args.phase,
        profile_name=args.target_profile,
        gpu_id=args.gpu_id,
        binary=frozen_binary_path,
        binary_sha256=frozen_binary["sha256"],
        runtime_sm_count=runtime_sm_count,
        coordinates=coordinates,
    )
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "created_at": timestamp(),
        "status": "planned",
        "protocol_revision": PROTOCOL_REVISION,
        "design_id": DESIGN_ID,
        "phase": args.phase,
        "profile": {
            "name": args.target_profile,
            "cuda_arch": profile.cuda_arch,
            "compute_capability": profile.compute_capability,
            "full_sm_counts": list(profile.full_sm_counts),
            "native_fp16_ex2_supported": profile.native_ex2_supported,
            "runtime_sm_count_planned": runtime_sm_count,
        },
        "metric": {
            "name": "net_pJ_per_logical_output_element",
            "formula": "(qualified trace energy - idle power * elapsed) * 1e12 / logical output elements",
            "scope": "complete_softmax_forward",
            "not_comparable_to": "EX2 Operand-rate ATC pJ/logical exponent result",
        },
        "thermal_contract": {
            "preheat_requested_s": PREHEAT_SECONDS,
            "preheat_actual_gate_s": [3.75, 6.25],
            "temperature": "recorded context only; do not pool with historical 20 s-preheat artifacts",
            "unrecorded_policy_warmup": "prohibited",
            "conditioner_policy": "fp32_io_fp32_all",
        },
        "selection_rule": {
            "representative_coordinate": "s1024_q50",
            "practical_difference_fraction": 0.10,
            "initial_coordinates": list(SCREEN_COORDINATES),
            "stop_rule": "S2048 only if S1024/S4096 differs by >10%; q25 extremes only if S1024 q25/q50 differs by >10%",
        },
        "binary": frozen_binary,
        "runner": frozen_runner,
        "parent": parent,
        "coordinates": [coordinate.__dict__ for coordinate in coordinates],
        "sessions": sessions,
    }
    atomic_json(run_root / "manifest.json", manifest)
    print(f"planned_run_dir={run_root}")
    print(f"planned_sessions={len(sessions)} planned_roles={sum(s['expected_measured_roles'] for s in sessions)}")
    for session in sessions:
        print(f"[{session['global_session_index']:02d}] {session['command_shell']}")
    return run_root


def load_manifest(run_root: Path) -> dict[str, Any]:
    path = run_root / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read manifest: {error}") from error
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise RuntimeError("manifest schema does not match the range runner")
    return payload


def execute_run(run_root: Path, max_sessions: int | None) -> None:
    manifest = load_manifest(run_root)
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list):
        raise RuntimeError("manifest sessions are invalid")
    runnable = [session for session in sessions if session.get("status") == "planned"]
    if max_sessions is not None:
        runnable = runnable[:max_sessions]
    for session in runnable:
        command = session.get("command")
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise RuntimeError("manifest command is invalid")
        session["started_at"] = timestamp()
        session["status"] = "running"
        manifest["status"] = "running"
        atomic_json(run_root / "manifest.json", manifest)
        print(f"running_session={session['global_session_index']} {session['coordinate_id']} {session['session_order']}", flush=True)
        completed = subprocess.run(command, cwd=ROOT, check=False)
        session["returncode"] = completed.returncode
        session["finished_at"] = timestamp()
        session["status"] = "complete" if completed.returncode == 0 else "failed"
        if completed.returncode != 0:
            manifest["status"] = "failed"
            atomic_json(run_root / "manifest.json", manifest)
            raise RuntimeError(f"measurement failed for session {session['global_session_index']}")
        raw_path = resolve_path(str(session["raw_csv"]))
        trace_path = resolve_path(str(session["energy_trace_csv"]))
        if not raw_path.is_file() or not trace_path.is_file():
            manifest["status"] = "failed"
            atomic_json(run_root / "manifest.json", manifest)
            raise RuntimeError("measurement returned success without both raw and trace artifacts")
        session["raw_sha256"] = sha256_file(raw_path)
        session["energy_trace_sha256"] = sha256_file(trace_path)
        atomic_json(run_root / "manifest.json", manifest)
    statuses = [str(session.get("status")) for session in sessions]
    manifest["status"] = "complete" if statuses and all(status == "complete" for status in statuses) else "partial"
    manifest["finished_at"] = timestamp()
    atomic_json(run_root / "manifest.json", manifest)
    print(f"run_status={manifest['status']}")


def self_test() -> None:
    assert grid_blocks(82, 0.25) == 21
    assert grid_blocks(82, 0.50) == 41
    assert grid_blocks(108, 0.25) == 27
    assert grid_blocks(108, 0.50) == 54
    assert grid_blocks(132, 0.25) == 33
    assert grid_blocks(132, 0.50) == 66
    assert runnable_policies("v100") == ("fp32_io_fp32_all",)
    assert runnable_policies("rtx3090") == POLICIES
    assert tuple(POLICY_ORDERS["ABC"]) == POLICIES
    assert tuple(POLICY_ORDERS["BCA"]) == (POLICIES[1], POLICIES[2], POLICIES[0])
    assert [item.identifier for item in selected_coordinates("screen", None)] == list(SCREEN_COORDINATES)
    print("softmax_whole_precision_range_runner_self_test=pass")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-profile", choices=tuple(PLATFORM_PROFILES), default="rtx3090")
    parser.add_argument("--build-dir", default="build-whole-precision-range")
    parser.add_argument("--binary", help="override range executable path")
    parser.add_argument("--output-dir", default="results/raw")
    parser.add_argument("--session-tag")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--runtime-sm-count", type=int,
                        help="explicit complete-device SM count; retain it in the manifest")
    parser.add_argument("--phase", choices=("screen", "followup", "confirmation"), default="screen")
    parser.add_argument("--coordinates",
                        help="comma-separated coordinate IDs; required outside screen")
    parser.add_argument("--continue-from",
                        help="parent range run; hash-bound in a new followup/confirmation manifest")
    parser.add_argument("--execute", action="store_true", help="run fresh CUDA processes after planning")
    parser.add_argument("--max-sessions", type=int,
                        help="execute only this many planned sessions (smoke/resume aid)")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.gpu_id < 0:
        raise ValueError("--gpu-id must be non-negative")
    if args.runtime_sm_count is not None and args.runtime_sm_count <= 0:
        raise ValueError("--runtime-sm-count must be positive")
    if args.max_sessions is not None and args.max_sessions <= 0:
        raise ValueError("--max-sessions must be positive")
    if args.phase == "screen" and args.continue_from is not None:
        raise ValueError("--continue-from is for a followup or confirmation phase")
    if args.phase != "screen" and args.continue_from is None:
        raise ValueError("followup/confirmation requires --continue-from")
    run_root = plan_run(args)
    if args.execute:
        execute_run(run_root, args.max_sessions)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as error:  # pragma: no cover - command-line boundary
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
