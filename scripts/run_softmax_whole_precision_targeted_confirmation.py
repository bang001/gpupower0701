#!/usr/bin/env python3
"""Plan and run the bounded fresh AB/BA whole-Softmax confirmation.

This is intentionally separate from ``run_softmax_whole_precision_stage_isolation``.
It does not pool the exploratory 27-role stage-isolation result.  Instead it
repeats only two exploratory-selected contrasts at the fixed RTX 3090
coordinate:

* FP16-I/O + FP32-stage baseline vs packed FP16 exponent, and
* FP16-I/O + FP32-stage baseline vs scalar FP16 max+sum reduction.

For each contrast, three AB and three BA fresh CUDA-process sessions are
scheduled.  The confirmation executable enforces canonical preparation before
a 5-second common baseline conditioner and disables unrecorded policy warm-up.
The runner freezes the exact executable and itself into the run directory
before any measurement, then records every raw/trace SHA-256 in an immutable
manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_BINARY = "a100_fp16_softmax_whole_precision_confirmation_energy"
TARGET_PROFILE = "rtx3090"

MANIFEST_SCHEMA = "softmax_whole_precision_targeted_confirmation_manifest_v1"
MANIFEST_PROTOCOL = "rtx3090_softmax_whole_precision_targeted_confirmation_v1"
RAW_SCHEMA = "softmax_whole_precision_v3"
RAW_PROTOCOL = "whole_softmax_precision_canonical_common_v1"
DESIGN_ID = "targeted_confirmation_abba_v1"
CONDITIONING_MODE = "canonical_common_v1"

BASELINE = "fp16_io_fp32_all"
SOFTMAX_COLS = 512
GRID_BLOCKS = 16
ROWS_PER_BLOCK = 2
SECONDS = 13.0
# A single common conditioner is applied once per fresh AB/BA session.  Five
# seconds is the current operational setting; prior 20-second results remain
# historical and must not be pooled with new runs.
PREHEAT_SECONDS = 5.0
IDLE_SECONDS = 1.0
TRACE_SAMPLE_MS = 500.0
TRACE_MIN_UPDATES = 16
LOGIT_SCALE = 4.0
SEED = 5573589319906701683

EXPLORATORY_RUN_DIR = (
    REPO_ROOT
    / "results/raw/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1"
)
EXPLORATORY_MANIFEST = EXPLORATORY_RUN_DIR / "manifest.json"
EXPLORATORY_ANALYSIS = EXPLORATORY_RUN_DIR / "analysis/analysis.json"


@dataclass(frozen=True)
class Candidate:
    identifier: str
    stage: str
    treatment: str
    description: str
    selection_context: str


CANDIDATES: dict[str, Candidate] = {
    "exp_packed": Candidate(
        identifier="exp_packed",
        stage="exp",
        treatment="exp_fp16x2",
        description="packed FP16 exponent only; max/sum and normalization remain FP32",
        selection_context="exploratory stage-isolation exp packed contrast had the most negative paired mean",
    ),
    "reduction_scalar": Candidate(
        identifier="reduction_scalar",
        stage="reduction",
        treatment="reduction_fp16_scalar",
        description="scalar FP16 max+sum reduction only; exponent and normalization remain FP32",
        selection_context="exploratory stage-isolation reduction scalar contrast had the most positive paired mean",
    ),
}

# Candidate order is intentionally interleaved across the full run rather than
# measuring one candidate only early and the other only late.  Every candidate
# receives exactly three AB and three BA fresh sessions.
SESSION_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_manifest_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


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


def order_schedule(candidate: Candidate, order: str) -> tuple[str, str]:
    if order == "AB":
        return (BASELINE, candidate.treatment)
    if order == "BA":
        return (candidate.treatment, BASELINE)
    raise ValueError(f"unsupported AB/BA order: {order}")


def freeze_exploratory_origin(run_root: Path) -> dict[str, Any]:
    """Freeze the selection evidence before any confirmation acquisition.

    The confirmation never pools this evidence, but it does record why the two
    contrasts were selected.  Keeping an in-run hash-bound copy prevents a
    later edit or relocation of the exploratory run from making a completed
    confirmation non-reproducible.
    """
    for path in (EXPLORATORY_MANIFEST, EXPLORATORY_ANALYSIS):
        if not path.is_file():
            raise RuntimeError(f"required exploratory selection artifact is missing: {path}")
    frozen_dir = run_root / "frozen" / "exploratory_selection"
    frozen_manifest, manifest_sha256 = freeze_file(
        EXPLORATORY_MANIFEST, frozen_dir / "stage_isolation_manifest.json"
    )
    frozen_analysis, analysis_sha256 = freeze_file(
        EXPLORATORY_ANALYSIS, frozen_dir / "stage_isolation_analysis.json"
    )
    return {
        "manifest_path": relative_or_absolute(frozen_manifest),
        "manifest_sha256": manifest_sha256,
        "analysis_path": relative_or_absolute(frozen_analysis),
        "analysis_sha256": analysis_sha256,
        "source_manifest_path": relative_or_absolute(EXPLORATORY_MANIFEST),
        "source_manifest_sha256": sha256_file(EXPLORATORY_MANIFEST),
        "source_analysis_path": relative_or_absolute(EXPLORATORY_ANALYSIS),
        "source_analysis_sha256": sha256_file(EXPLORATORY_ANALYSIS),
        "frozen_before_execution": True,
        "selection_hashes_recorded_before_execution": True,
        "pooling_prohibited": "true",
    }


def freeze_file(source: Path, destination: Path) -> tuple[Path, str]:
    if not source.is_file():
        raise RuntimeError(f"required source file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if not os.access(destination, os.X_OK) and os.access(source, os.X_OK):
        destination.chmod(destination.stat().st_mode | 0o111)
    return destination, sha256_file(destination)


def build_command(
    *,
    binary: Path,
    binary_sha256: str,
    gpu_id: int,
    candidate: Candidate,
    session_id: str,
    order: str,
    schedule: tuple[str, str],
    raw_csv: Path,
    trace_csv: Path,
) -> list[str]:
    return [
        str(binary),
        "--gpu-id",
        str(gpu_id),
        "--target-profile",
        TARGET_PROFILE,
        "--confirmation-pair",
        candidate.identifier,
        "--conditioning-mode",
        CONDITIONING_MODE,
        "--schema-version",
        RAW_SCHEMA,
        "--experiment-kind",
        "whole_softmax_targeted_confirmation",
        "--protocol-revision",
        RAW_PROTOCOL,
        "--design-id",
        DESIGN_ID,
        "--stage-group",
        candidate.identifier,
        "--session-order",
        order,
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
        "--seed",
        str(SEED),
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
    binary: Path,
    binary_sha256: str,
    gpu_id: int,
) -> list[dict[str, Any]]:
    per_candidate_count = {identifier: 0 for identifier in CANDIDATES}
    sessions: list[dict[str, Any]] = []
    for global_index, (candidate_id, order) in enumerate(SESSION_SEQUENCE, start=1):
        candidate = CANDIDATES[candidate_id]
        per_candidate_count[candidate_id] += 1
        candidate_index = per_candidate_count[candidate_id]
        schedule = order_schedule(candidate, order)
        session_id = f"{session_tag}_{candidate_id}_session{candidate_index:02d}_{order}"
        prefix = f"{candidate_id}_session{candidate_index:02d}_{order}"
        raw_csv = run_root / f"{prefix}_raw.csv"
        trace_csv = run_root / f"{prefix}_energy_trace.csv"
        command = build_command(
            binary=binary,
            binary_sha256=binary_sha256,
            gpu_id=gpu_id,
            candidate=candidate,
            session_id=session_id,
            order=order,
            schedule=schedule,
            raw_csv=raw_csv,
            trace_csv=trace_csv,
        )
        sessions.append(
            {
                "global_session_index": global_index,
                "candidate_id": candidate_id,
                "stage": candidate.stage,
                "candidate_description": candidate.description,
                "selection_context": candidate.selection_context,
                "session_index_within_candidate": candidate_index,
                "session_order": order,
                "session_id": session_id,
                "schedule_label": ",".join(schedule),
                "policy_schedule": list(schedule),
                "expected_measured_roles": 2,
                "raw_csv": relative_or_absolute(raw_csv),
                "energy_trace_csv": relative_or_absolute(trace_csv),
                "command": command,
                "command_shell": shlex.join(command),
                "status": "planned",
                "returncode": None,
            }
        )
    return sessions


def expected_artifacts(sessions: Iterable[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for session in sessions:
        paths.extend(
            [
                resolve_manifest_path(str(session["raw_csv"])),
                resolve_manifest_path(str(session["energy_trace_csv"])),
            ]
        )
    return paths


def immutable_manifest_view(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "protocol_revision",
            "run_tag",
            "binary",
            "runner",
            "exploratory_origin",
            "design",
            "sessions",
        )
    }


def prepare_manifest(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        atomic_write_json(path, manifest)
        return manifest
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot reuse invalid manifest: {path}") from error
    if immutable_manifest_view(existing) != immutable_manifest_view(manifest):
        raise RuntimeError(
            "existing manifest differs from this requested confirmation; choose a "
            "new --session-tag rather than mixing evidence"
        )
    return existing


def assert_frozen_provenance(manifest: dict[str, Any]) -> None:
    for label in ("binary", "runner"):
        section = manifest.get(label)
        if not isinstance(section, dict):
            raise RuntimeError(f"manifest.{label} is invalid")
        path = resolve_manifest_path(str(section.get("path", "")))
        expected = str(section.get("sha256", ""))
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"frozen {label} provenance does not match manifest: {path}")


def verify_empty_session_outputs(manifest: dict[str, Any]) -> None:
    present = [path for path in expected_artifacts(manifest["sessions"]) if path.exists()]
    if present:
        rendered = ", ".join(str(path) for path in present[:6])
        if len(present) > 6:
            rendered += f", ... ({len(present)} total)"
        raise RuntimeError("refusing to overwrite existing measured artifacts: " + rendered)


def print_plan(manifest: dict[str, Any]) -> None:
    design = manifest["design"]
    print(
        "whole_precision_design=targeted_confirmation; "
        f"candidates={','.join(design['candidate_ids'])}; "
        f"sessions={len(manifest['sessions'])}; "
        f"measured_roles={design['expected_measured_roles']}; "
        "order=ABx3_BAx3_per_candidate",
        flush=True,
    )
    print(f"manifest={manifest['manifest_path']}", flush=True)
    for session in manifest["sessions"]:
        print(
            f"session={session['global_session_index']:02d} "
            f"candidate={session['candidate_id']} "
            f"candidate_session={session['session_index_within_candidate']:02d} "
            f"order={session['session_order']} "
            f"schedule={session['schedule_label']}",
            flush=True,
        )
        print("+ " + session["command_shell"], flush=True)


def execute_sessions(manifest_path: Path, manifest: dict[str, Any]) -> int:
    assert_frozen_provenance(manifest)
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
            manifest["execution"].update({"finished_at": timestamp(), "status": "failed"})
            atomic_write_json(manifest_path, manifest)
            print(
                f"failed_session={session['session_id']} returncode={result.returncode}",
                file=sys.stderr,
            )
            return result.returncode or 1
        raw = resolve_manifest_path(str(session["raw_csv"]))
        trace = resolve_manifest_path(str(session["energy_trace_csv"]))
        missing = [path for path in (raw, trace) if not path.is_file() or path.stat().st_size == 0]
        if missing:
            session["status"] = "failed_missing_artifact"
            session["missing_artifacts"] = [str(path) for path in missing]
            manifest["execution"].update({"finished_at": timestamp(), "status": "failed"})
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
    manifest["execution"].update(
        {"finished_at": timestamp(), "status": "complete_unanalyzed"}
    )
    atomic_write_json(manifest_path, manifest)
    print("execution_status=complete_unanalyzed", flush=True)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path("build-whole-precision-confirmation-rtx3090"),
        help="directory containing the separate confirmation executable",
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
    parser.add_argument("--gpu-id", type=int, default=0, help="CUDA/NVML GPU index")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write/reuse the immutable plan and print commands without measuring",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="start all 12 energy-measurement sessions; absent by default",
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute are mutually exclusive")
    if args.gpu_id < 0:
        parser.error("--gpu-id must be non-negative")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_base = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    run_root = (
        output_base
        / f"rtx3090_softmax_whole_precision_targeted_confirmation_{args.session_tag}"
    ).resolve()
    manifest_path = run_root / "manifest.json"
    frozen_binary = run_root / "frozen" / TARGET_BINARY
    frozen_runner = run_root / "frozen" / Path(__file__).name

    if not manifest_path.exists():
        if run_root.exists() and any(run_root.iterdir()):
            raise SystemExit(
                "run directory exists without this manifest and is not empty: "
                + str(run_root)
                + "; choose a new --session-tag"
            )
        source_binary = (REPO_ROOT / args.build_dir / TARGET_BINARY).resolve()
        if not source_binary.is_file() or not os.access(source_binary, os.X_OK):
            raise SystemExit(
                "confirmation binary is missing or not executable: " + str(source_binary) + "\n"
                "Build the dedicated target first, for example:\n"
                "  cmake --build " + str(args.build_dir) + " --target " + TARGET_BINARY
            )
        run_root.mkdir(parents=True, exist_ok=True)
        frozen_binary, binary_sha256 = freeze_file(source_binary, frozen_binary)
        frozen_runner, runner_sha256 = freeze_file(Path(__file__).resolve(), frozen_runner)
        source_binary_path = relative_or_absolute(source_binary)
        source_binary_sha256 = sha256_file(source_binary)
        origin = freeze_exploratory_origin(run_root)
    else:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        binary_section = existing.get("binary", {})
        runner_section = existing.get("runner", {})
        frozen_binary = resolve_manifest_path(str(binary_section.get("path", "")))
        frozen_runner = resolve_manifest_path(str(runner_section.get("path", "")))
        binary_sha256 = str(binary_section.get("sha256", ""))
        runner_sha256 = str(runner_section.get("sha256", ""))
        source_binary_path = str(existing.get("source_binary", {}).get("path", ""))
        source_binary_sha256 = str(existing.get("source_binary", {}).get("sha256", ""))
        origin = existing.get("exploratory_origin")
        if not isinstance(origin, dict):
            raise SystemExit("existing manifest exploratory_origin is invalid")
    sessions = build_sessions(
        run_root=run_root,
        session_tag=args.session_tag,
        binary=frozen_binary,
        binary_sha256=binary_sha256,
        gpu_id=args.gpu_id,
    )
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "protocol_revision": MANIFEST_PROTOCOL,
        "run_tag": args.session_tag,
        "created_at": timestamp(),
        "manifest_path": relative_or_absolute(manifest_path),
        "binary": {
            "path": relative_or_absolute(frozen_binary),
            "sha256": binary_sha256,
            "frozen_before_execution": True,
        },
        "runner": {
            "path": relative_or_absolute(frozen_runner),
            "sha256": runner_sha256,
            "frozen_before_execution": True,
        },
        "source_binary": {"path": source_binary_path, "sha256": source_binary_sha256},
        "exploratory_origin": origin,
        "design": {
            "experiment_kind": "whole_softmax_targeted_confirmation",
            "target_profile": TARGET_PROFILE,
            "gpu_id": args.gpu_id,
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "rows_per_block": ROWS_PER_BLOCK,
            "seconds_per_policy": SECONDS,
            "preheat_seconds": PREHEAT_SECONDS,
            "idle_seconds": IDLE_SECONDS,
            "energy_trace_sample_ms": TRACE_SAMPLE_MS,
            "energy_trace_min_updates": TRACE_MIN_UPDATES,
            "logit_scale": LOGIT_SCALE,
            "seed": SEED,
            "baseline_policy": BASELINE,
            "candidate_ids": list(CANDIDATES),
            "candidate_treatments": {
                candidate.identifier: candidate.treatment for candidate in CANDIDATES.values()
            },
            "order_algorithm": "interleaved_AB3_BA3_per_candidate_v1",
            "fresh_binary_process_per_session": True,
            "single_two_role_schedule_per_process": True,
            "conditioning_mode": CONDITIONING_MODE,
            "preparation_order": "canonical_policy_enum_ascending",
            "calibration_before_conditioning": True,
            "conditioning_policy": BASELINE,
            "premeasurement_schedule_warmup": "none",
            "expected_sessions": len(SESSION_SEQUENCE),
            "expected_measured_roles": len(SESSION_SEQUENCE) * 2,
            "primary_metric": "net_pJ_per_logical_output_element",
            "temperature_hard_gate": False,
            "exploratory_pooling_prohibited": True,
            "ex2_operand_rate_atc_compatible": False,
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
    manifest = prepare_manifest(manifest_path, manifest)
    assert_frozen_provenance(manifest)
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
