#!/usr/bin/env python3
"""Confirm the CTA=48, S=1024 Softmax EX2 result without a new full sweep.

This protocol deliberately uses only the disputed coordinate and three fresh,
independent CUDA-context sessions.  Within each session every implementation
is measured once; the three cyclic implementation orders place every
implementation in every chronological position exactly once:

    session 1: fp32 -> ptx_f16 -> ptx_f16x2
    session 2: ptx_f16x2 -> fp32 -> ptx_f16
    session 3: ptx_f16 -> ptx_f16x2 -> fp32

Each cell retains the exact 20 s nominal / 16--30 s actual preheat contract,
six persistent counterbalanced probe brackets, 13 s role target, 500 ms
energy trace, and evidence verification used by the 60-cell runs.  This file
wraps the frozen cell runner and analyzer rather than duplicating CUDA or
energy-accounting logic.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import run_softmax_ex2_factorial_matrix as base


PROTOCOL_REVISION = "rtx3090_softmax_ex2_targeted_confirmation_v1"
STATE_REVISION = "rtx3090_softmax_ex2_targeted_confirmation_state_v1"
ORDER_ALGORITHM = "three_session_cyclic_latin_impl_order_v1"
TARGET_GRID_BLOCKS = 48
TARGET_SOFTMAX_COLS = 1024
SESSION_ORDERS: tuple[tuple[str, ...], ...] = (
    ("fp32", "ptx_f16", "ptx_f16x2"),
    ("ptx_f16x2", "fp32", "ptx_f16"),
    ("ptx_f16", "ptx_f16x2", "fp32"),
)

PLAN_FIELDS = (
    "session_id",
    "session_index",
    "session_order",
    "implementation_position",
    *base.PLAN_FIELDS,
)
STATE_FIELDS = (
    "state_revision",
    "protocol_revision",
    "target_tag",
    "cell_id",
    "cell_tag",
    "order_index",
    "session_index",
    "implementation_position",
    "exp_impl",
    "grid_blocks",
    "softmax_cols",
    "status",
    "attempt",
    "started_at",
    "finished_at",
    "runner_returncode",
    "analyzer_returncode",
    "verification_status",
    "verification_reasons",
    "actual_binary_sha256",
    "preheat_requested_seconds",
    "preheat_elapsed_s",
    "quality_status",
    "verdict",
    "artifact_bundle_sha256",
    "plan_row_sha256",
    "log_path",
)


def command_sha(command: list[str]) -> tuple[str, str]:
    text = shlex.join(command)
    return base.sha256_text(text), text


def plan_paths(
    target_tag: str, plan_out: Path | None, state_out: Path | None
) -> tuple[Path, Path]:
    prefix = f"rtx3090_softmax_ex2_targeted_confirmation_{target_tag}"
    return (
        base.repository_path(
            plan_out or Path(f"results/summary/{prefix}_plan.csv")
        ),
        base.repository_path(
            state_out or Path(f"results/summary/{prefix}_state.csv")
        ),
    )


def build_plan(
    *,
    target_tag: str,
    order_seed: int,
    binary: Path,
    gpu_id: int,
    raw_dir: Path = Path("results/raw"),
    summary_dir: Path = Path("results/summary"),
    report_dir: Path = Path("docs/results"),
    log_dir: Path = Path("results/logs"),
) -> list[dict[str, str]]:
    """Build the immutable nine-cell, three-session confirmation plan."""
    binary_display = base.display_path(binary)
    binary_sha = base.sha256_file(base.repository_path(binary_display))
    runner_display = base.display_path(base.CELL_RUNNER)
    analyzer_display = base.display_path(base.CELL_ANALYZER)
    helper_display = base.display_path(base.ANALYZER_HELPER)
    orchestrator_display = base.display_path(Path(__file__))
    runner_sha = base.sha256_file(base.repository_path(runner_display))
    analyzer_sha = base.sha256_file(base.repository_path(analyzer_display))
    helper_sha = base.sha256_file(base.repository_path(helper_display))
    orchestrator_sha = base.sha256_file(base.repository_path(orchestrator_display))

    rows: list[dict[str, str]] = []
    order_index = 0
    for session_index, implementation_order in enumerate(SESSION_ORDERS, start=1):
        session_id = f"session{session_index:02d}_g{TARGET_GRID_BLOCKS}_s{TARGET_SOFTMAX_COLS}"
        session_order = ">".join(implementation_order)
        for position, exp_impl in enumerate(implementation_order, start=1):
            order_index += 1
            cell_id = (
                f"sess{session_index:02d}_pos{position}_{exp_impl}_"
                f"g{TARGET_GRID_BLOCKS}_s{TARGET_SOFTMAX_COLS}"
            )
            cell_tag = (
                f"{target_tag}_sess{session_index:02d}_pos{position}_"
                f"{exp_impl}_g{TARGET_GRID_BLOCKS}_s{TARGET_SOFTMAX_COLS}"
            )
            output_prefix = (
                f"rtx3090_fp16_softmax_operand_rate_atc_{cell_tag}"
                f"{base.exp_output_suffix(exp_impl)}"
            )
            raw_csv = raw_dir / f"{output_prefix}_raw.csv"
            manifest_csv = raw_dir / f"{output_prefix}_manifest.csv"
            trace_csv = raw_dir / f"{output_prefix}_raw_energy_trace.csv"
            preheat_csv = raw_dir / (
                f"{output_prefix}_{base.CACHE_CONDITION}_g{TARGET_GRID_BLOCKS}_preheat.csv"
            )
            analysis_prefix = summary_dir / (
                f"rtx3090_softmax_ex2_targeted_{target_tag}_{cell_id}"
            )
            triplets_csv = Path(f"{analysis_prefix}_triplets.csv")
            matched_csv = Path(f"{analysis_prefix}_matched.csv")
            summary_csv = Path(f"{analysis_prefix}_summary.csv")
            analysis_report = report_dir / (
                f"rtx3090_softmax_ex2_targeted_{target_tag}_{cell_id}_ko.md"
            )
            log_path = log_dir / (
                f"rtx3090_softmax_ex2_targeted_{target_tag}_{cell_id}.log"
            )
            runner_command = [
                "python3",
                runner_display,
                "--binary",
                binary_display,
                "--gpu-id",
                str(gpu_id),
                "--target-profile",
                base.TARGET_PROFILE,
                "--exp-impl",
                exp_impl,
                "--softmax-cols",
                str(TARGET_SOFTMAX_COLS),
                "--blocks-per-sm",
                str(base.BLOCKS_PER_SM),
                "--grid-blocks-list",
                str(TARGET_GRID_BLOCKS),
                "--control-mode",
                base.CONTROL_MODE,
                "--logit-scale",
                str(base.LOGIT_SCALE),
                "--seconds",
                str(base.ROLE_TARGET_SECONDS),
                "--idle-measure-seconds",
                str(base.IDLE_MEASURE_SECONDS),
                "--pairs",
                str(base.PAIRS),
                "--bracket-warmup-pairs",
                str(base.BRACKET_WARMUP_PAIRS),
                "--execution-mode",
                "persistent_bracket",
                "--bracket-idle-policy",
                base.BRACKET_IDLE_POLICY,
                "--bracket-order",
                base.BRACKET_ORDER,
                "--preheat-seconds",
                str(base.PREHEAT_NOMINAL_SECONDS),
                "--preheat-actual-min-seconds",
                str(base.PREHEAT_ACTUAL_MIN_SECONDS),
                "--preheat-actual-max-seconds",
                str(base.PREHEAT_ACTUAL_MAX_SECONDS),
                "--conditions",
                base.CACHE_CONDITION,
                "--cache-policy",
                base.CACHE_POLICY,
                "--energy-trace",
                "1",
                "--energy-trace-sample-ms",
                str(base.ENERGY_TRACE_SAMPLE_MS),
                "--energy-trace-min-updates",
                str(base.ENERGY_TRACE_MIN_FIT_POINTS),
                "--tag",
                cell_tag,
                "--out-dir",
                base.display_path(raw_dir),
                "--max-gpu-util-pct",
                "10.0",
                "--max-memory-util-pct",
                "15.0",
                "--quiescence-timeout-s",
                "60.0",
                "--quiescence-poll-s",
                "1.0",
                "--quiescence-consecutive-samples",
                "2",
            ]
            analyzer_command = [
                "python3",
                analyzer_display,
                "--input",
                base.display_path(raw_csv),
                "--energy-trace-input",
                base.display_path(trace_csv),
                "--manifest",
                base.display_path(manifest_csv),
                "--exp-impl",
                exp_impl,
                "--grid-blocks",
                str(TARGET_GRID_BLOCKS),
                "--triplet-out",
                base.display_path(triplets_csv),
                "--matched-out",
                base.display_path(matched_csv),
                "--summary-out",
                base.display_path(summary_csv),
                "--report-out",
                base.display_path(analysis_report),
                "--decision-stage",
                "pilot",
                "--energy-trace-min-fit-points",
                str(base.ENERGY_TRACE_MIN_FIT_POINTS),
                "--bootstrap-samples",
                "4000",
                "--seed",
                str(order_seed + order_index * 1009),
            ]
            runner_command_sha, runner_command_text = command_sha(runner_command)
            analyzer_command_sha, analyzer_command_text = command_sha(analyzer_command)
            rows.append(
                {
                    "session_id": session_id,
                    "session_index": str(session_index),
                    "session_order": session_order,
                    "implementation_position": str(position),
                    "protocol_revision": PROTOCOL_REVISION,
                    "matrix_tag": target_tag,
                    "order_algorithm": ORDER_ALGORITHM,
                    "order_seed": str(order_seed),
                    "order_index": str(order_index),
                    "macroblock_index": str(session_index),
                    "macroblock_id": session_id,
                    "within_macroblock_index": str(position),
                    "implementation_permutation": session_order,
                    "cell_id": cell_id,
                    "cell_tag": cell_tag,
                    "exp_impl": exp_impl,
                    "exp_impl_canonical": base.EXP_CANONICAL[exp_impl],
                    "grid_blocks": str(TARGET_GRID_BLOCKS),
                    "cta_grid_blocks": str(TARGET_GRID_BLOCKS),
                    "softmax_cols": str(TARGET_SOFTMAX_COLS),
                    "target_profile": base.TARGET_PROFILE,
                    "control_mode": base.CONTROL_MODE,
                    "blocks_per_sm": str(base.BLOCKS_PER_SM),
                    "logit_scale": str(base.LOGIT_SCALE),
                    "cache_condition": base.CACHE_CONDITION,
                    "cache_policy": base.CACHE_POLICY,
                    "role_target_seconds": str(base.ROLE_TARGET_SECONDS),
                    "idle_measure_seconds": str(base.IDLE_MEASURE_SECONDS),
                    "pairs": str(base.PAIRS),
                    "bracket_warmup_pairs": str(base.BRACKET_WARMUP_PAIRS),
                    "bracket_order": base.BRACKET_ORDER,
                    "bracket_idle_policy": base.BRACKET_IDLE_POLICY,
                    "energy_trace_sample_ms": str(base.ENERGY_TRACE_SAMPLE_MS),
                    "energy_trace_min_fit_points": str(base.ENERGY_TRACE_MIN_FIT_POINTS),
                    "preheat_requested_seconds": str(base.PREHEAT_NOMINAL_SECONDS),
                    "preheat_actual_min_seconds": str(base.PREHEAT_ACTUAL_MIN_SECONDS),
                    "preheat_actual_max_seconds": str(base.PREHEAT_ACTUAL_MAX_SECONDS),
                    "binary": binary_display,
                    "binary_sha256": binary_sha,
                    "cell_runner": runner_display,
                    "cell_runner_sha256": runner_sha,
                    "cell_analyzer": analyzer_display,
                    "cell_analyzer_sha256": analyzer_sha,
                    "analyzer_helper": helper_display,
                    "analyzer_helper_sha256": helper_sha,
                    "orchestrator": orchestrator_display,
                    "orchestrator_sha256": orchestrator_sha,
                    "raw_csv": base.display_path(raw_csv),
                    "manifest_csv": base.display_path(manifest_csv),
                    "trace_csv": base.display_path(trace_csv),
                    "preheat_csv": base.display_path(preheat_csv),
                    "triplets_csv": base.display_path(triplets_csv),
                    "matched_csv": base.display_path(matched_csv),
                    "summary_csv": base.display_path(summary_csv),
                    "analysis_report_md": base.display_path(analysis_report),
                    "log_path": base.display_path(log_path),
                    "runner_command_sha256": runner_command_sha,
                    "runner_command": runner_command_text,
                    "analyzer_command_sha256": analyzer_command_sha,
                    "analyzer_command": analyzer_command_text,
                }
            )
    validate_plan_shape(rows)
    return rows


def validate_plan_shape(rows: list[dict[str, str]]) -> None:
    if len(rows) != 9:
        raise ValueError(f"targeted plan must contain nine cells, got {len(rows)}")
    if [int(row["order_index"]) for row in rows] != list(range(1, 10)):
        raise ValueError("targeted order_index must be exactly 1..9")
    if len({row["cell_id"] for row in rows}) != 9 or len({row["cell_tag"] for row in rows}) != 9:
        raise ValueError("targeted cell identities must be unique")
    if {(row["grid_blocks"], row["softmax_cols"]) for row in rows} != {
        (str(TARGET_GRID_BLOCKS), str(TARGET_SOFTMAX_COLS))
    }:
        raise ValueError("targeted plan escaped the fixed CTA=48, S=1024 coordinate")
    if {row["protocol_revision"] for row in rows} != {PROTOCOL_REVISION}:
        raise ValueError("unexpected targeted protocol revision")
    if {row["order_algorithm"] for row in rows} != {ORDER_ALGORITHM}:
        raise ValueError("unexpected targeted implementation-order algorithm")
    if {row["exp_impl"] for row in rows} != set(base.EXP_IMPLS):
        raise ValueError("targeted plan does not include all three implementations")
    for implementation in base.EXP_IMPLS:
        selected = [row for row in rows if row["exp_impl"] == implementation]
        if len(selected) != 3:
            raise ValueError(f"{implementation} must occur in three independent sessions")
        if sorted(int(row["implementation_position"]) for row in selected) != [1, 2, 3]:
            raise ValueError(f"{implementation} must occupy every position once")
    for session_index, expected_order in enumerate(SESSION_ORDERS, start=1):
        selected = sorted(
            (row for row in rows if int(row["session_index"]) == session_index),
            key=lambda row: int(row["implementation_position"]),
        )
        if len(selected) != 3:
            raise ValueError(f"session {session_index} does not contain three cells")
        if tuple(row["exp_impl"] for row in selected) != expected_order:
            raise ValueError(f"session {session_index} order does not match the preregistered cycle")
        if {row["session_order"] for row in selected} != {">".join(expected_order)}:
            raise ValueError(f"session {session_index} order label is inconsistent")
    if any("--pairs 6" not in row["runner_command"] for row in rows):
        raise ValueError("targeted plan lost the six-pair bracket contract")
    if any("--preheat-seconds 20.0" not in row["runner_command"] for row in rows):
        raise ValueError("targeted plan lost the 20 s preheat request")


def load_or_create_plan(
    plan_path: Path, expected: list[dict[str, str]]
) -> tuple[list[dict[str, str]], bool]:
    if plan_path.exists():
        observed = base.read_csv_strict(plan_path)
        base.compare_plan(observed, expected)
        validate_plan_shape(observed)
        return observed, False
    base.write_csv_atomic(plan_path, expected, PLAN_FIELDS)
    return expected, True


def assert_bound_inputs(plan: list[dict[str, str]]) -> None:
    if not plan:
        raise SystemExit("empty targeted plan")
    first = plan[0]
    bindings = (
        ("binary", "binary_sha256"),
        ("cell_runner", "cell_runner_sha256"),
        ("cell_analyzer", "cell_analyzer_sha256"),
        ("analyzer_helper", "analyzer_helper_sha256"),
        ("orchestrator", "orchestrator_sha256"),
    )
    for path_field, sha_field in bindings:
        path = base.repository_path(first[path_field])
        if not path.is_file():
            raise SystemExit(f"bound input is missing: {path}")
        observed = base.sha256_file(path)
        if observed != first[sha_field]:
            raise SystemExit(
                f"bound input changed for {path_field}: {observed} != {first[sha_field]}; "
                "use a fresh target tag/plan after rebuilding or editing"
            )
    for row in plan:
        for _path, sha_field in bindings:
            if row[sha_field] != first[sha_field]:
                raise SystemExit(f"plan has more than one {sha_field}")


def state_row(
    plan_row: dict[str, str],
    *,
    status: str,
    attempt: int,
    started_at: str = "",
    finished_at: str = "",
    runner_returncode: str = "",
    analyzer_returncode: str = "",
    verification_status: str = "",
    verification_reasons: str = "",
    metadata: dict[str, str] | None = None,
) -> dict[str, str]:
    metadata = metadata or {}
    return {
        "state_revision": STATE_REVISION,
        "protocol_revision": PROTOCOL_REVISION,
        "target_tag": plan_row["matrix_tag"],
        "cell_id": plan_row["cell_id"],
        "cell_tag": plan_row["cell_tag"],
        "order_index": plan_row["order_index"],
        "session_index": plan_row["session_index"],
        "implementation_position": plan_row["implementation_position"],
        "exp_impl": plan_row["exp_impl"],
        "grid_blocks": plan_row["grid_blocks"],
        "softmax_cols": plan_row["softmax_cols"],
        "status": status,
        "attempt": str(attempt),
        "started_at": started_at,
        "finished_at": finished_at,
        "runner_returncode": runner_returncode,
        "analyzer_returncode": analyzer_returncode,
        "verification_status": verification_status,
        "verification_reasons": verification_reasons,
        "actual_binary_sha256": metadata.get("actual_binary_sha256", ""),
        "preheat_requested_seconds": metadata.get("preheat_requested_seconds", ""),
        "preheat_elapsed_s": metadata.get("preheat_elapsed_s", ""),
        "quality_status": metadata.get("quality_status", ""),
        "verdict": metadata.get("verdict", ""),
        "artifact_bundle_sha256": metadata.get("artifact_bundle_sha256", ""),
        "plan_row_sha256": base.canonical_json_sha(plan_row),
        "log_path": plan_row["log_path"],
    }


def load_state(path: Path, plan: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    plan_by_id = {row["cell_id"]: row for row in plan}
    state: dict[str, dict[str, str]] = {}
    for row in base.read_csv_strict(path):
        cell_id = row.get("cell_id", "")
        if not cell_id or cell_id in state or cell_id not in plan_by_id:
            raise SystemExit("targeted state has an empty, duplicate, or unknown cell_id")
        plan_row = plan_by_id[cell_id]
        expected = {
            "state_revision": STATE_REVISION,
            "protocol_revision": PROTOCOL_REVISION,
            "target_tag": plan_row["matrix_tag"],
            "cell_id": plan_row["cell_id"],
            "cell_tag": plan_row["cell_tag"],
            "order_index": plan_row["order_index"],
            "session_index": plan_row["session_index"],
            "implementation_position": plan_row["implementation_position"],
            "exp_impl": plan_row["exp_impl"],
            "grid_blocks": plan_row["grid_blocks"],
            "softmax_cols": plan_row["softmax_cols"],
            "plan_row_sha256": base.canonical_json_sha(plan_row),
            "log_path": plan_row["log_path"],
        }
        mismatch = [field for field, value in expected.items() if row.get(field, "") != value]
        if mismatch:
            raise SystemExit(
                f"targeted state/plan identity mismatch for {cell_id}: {','.join(mismatch)}"
            )
        if row.get("status") not in {"running", "failed", "complete"}:
            raise SystemExit(f"targeted state has invalid status for {cell_id}")
        try:
            if int(row.get("attempt", "0")) < 1:
                raise ValueError
        except ValueError as error:
            raise SystemExit(f"targeted state has invalid attempt for {cell_id}") from error
        state[cell_id] = row
    return state


def save_state(path: Path, state: dict[str, dict[str, str]]) -> None:
    rows = sorted(state.values(), key=lambda row: int(row["order_index"]))
    base.write_csv_atomic(path, rows, STATE_FIELDS)


def archive_incomplete_outputs(
    row: dict[str, str], archive_root: Path, attempt: int
) -> Path | None:
    existing = [path for path in base.artifact_paths(row) if path.exists()]
    if not existing:
        return None
    archive = archive_root / row["cell_id"] / (
        f"attempt{attempt:02d}_{base.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    archive.mkdir(parents=True, exist_ok=False)
    for source in existing:
        source.replace(archive / source.name)
    return archive


def run_analyzer_logged(command: list[str], log_path: Path) -> int:
    base.append_log(log_path, f"\nanalyzer_command={shlex.join(command)}\n")
    print(f"+ {shlex.join(command)}", flush=True)
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=base.REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="")
                log.write(line)
        except BaseException:
            process.terminate()
            process.wait(timeout=10)
            raise
        return process.wait()


def execute(
    plan: list[dict[str, str]],
    state_path: Path,
    *,
    resume: bool,
    archive_incomplete: bool,
    max_new_cells: int,
) -> int:
    state = load_state(state_path, plan)
    if state and not resume:
        raise SystemExit(f"state already exists at {state_path}; use --resume after checking it")
    assert_bound_inputs(plan)
    archive_root = base.repository_path(
        Path("results/archive") / f"rtx3090_softmax_ex2_targeted_{plan[0]['matrix_tag']}_incomplete"
    )
    new_cells = 0
    for row in plan:
        cell_id = row["cell_id"]
        previous = state.get(cell_id)
        verified, reasons, metadata = base.verify_cell(row)
        if verified:
            if previous and previous.get("status") == "complete":
                immutable = {
                    "verification_status": "pass",
                    "plan_row_sha256": base.canonical_json_sha(row),
                    "artifact_bundle_sha256": metadata["artifact_bundle_sha256"],
                    "actual_binary_sha256": metadata["actual_binary_sha256"],
                    "preheat_elapsed_s": metadata["preheat_elapsed_s"],
                    "quality_status": metadata["quality_status"],
                    "verdict": metadata["verdict"],
                }
                mismatch = [field for field, value in immutable.items() if previous.get(field, "") != value]
                if mismatch:
                    raise SystemExit(
                        f"complete state/evidence mutation for {cell_id}: {','.join(mismatch)}"
                    )
            state[cell_id] = state_row(
                row,
                status="complete",
                attempt=int(previous["attempt"]) if previous else 1,
                started_at=previous.get("started_at", "") if previous else "",
                finished_at=previous.get("finished_at", "") if previous else "",
                runner_returncode=previous.get("runner_returncode", "0") if previous else "0",
                analyzer_returncode=previous.get("analyzer_returncode", "0") if previous else "0",
                verification_status="pass",
                metadata=metadata,
            )
            save_state(state_path, state)
            print(f"skip verified complete {cell_id}", flush=True)
            continue
        if previous and previous.get("status") == "complete":
            raise SystemExit(f"previously complete cell no longer verifies: {cell_id}: {';'.join(reasons)}")
        attempt = int(previous["attempt"]) + 1 if previous else 1
        existing = [path for path in base.artifact_paths(row) if path.exists()]
        if existing:
            if not (resume and archive_incomplete):
                raise SystemExit(
                    f"incomplete/corrupt outputs exist for {cell_id}; inspect them, then use --resume --archive-incomplete"
                )
            archive = archive_incomplete_outputs(row, archive_root, attempt - 1)
            print(f"archived incomplete bundle to {archive}", flush=True)
        if max_new_cells > 0 and new_cells >= max_new_cells:
            print(f"max-new-cells={max_new_cells} reached; state remains resumable")
            break
        started_at = base.timestamp()
        state[cell_id] = state_row(row, status="running", attempt=attempt, started_at=started_at)
        save_state(state_path, state)
        log_path = base.repository_path(row["log_path"])
        runner_code = base.run_logged(shlex.split(row["runner_command"]), log_path, f"{cell_id}:runner")
        if runner_code != 0:
            state[cell_id] = state_row(
                row, status="failed", attempt=attempt, started_at=started_at,
                finished_at=base.timestamp(), runner_returncode=str(runner_code),
                verification_status="fail", verification_reasons="runner_nonzero"
            )
            save_state(state_path, state)
            raise SystemExit(f"cell runner failed for {cell_id} with {runner_code}")
        analyzer_code = run_analyzer_logged(shlex.split(row["analyzer_command"]), log_path)
        if analyzer_code != 0:
            state[cell_id] = state_row(
                row, status="failed", attempt=attempt, started_at=started_at,
                finished_at=base.timestamp(), runner_returncode="0",
                analyzer_returncode=str(analyzer_code), verification_status="fail",
                verification_reasons="analyzer_nonzero"
            )
            save_state(state_path, state)
            raise SystemExit(f"cell analyzer failed for {cell_id} with {analyzer_code}")
        verified, reasons, metadata = base.verify_cell(row)
        if not verified:
            state[cell_id] = state_row(
                row, status="failed", attempt=attempt, started_at=started_at,
                finished_at=base.timestamp(), runner_returncode="0", analyzer_returncode="0",
                verification_status="fail", verification_reasons=";".join(reasons), metadata=metadata
            )
            save_state(state_path, state)
            raise SystemExit(f"cell evidence verification failed for {cell_id}: {';'.join(reasons)}")
        state[cell_id] = state_row(
            row, status="complete", attempt=attempt, started_at=started_at,
            finished_at=base.timestamp(), runner_returncode="0", analyzer_returncode="0",
            verification_status="pass", metadata=metadata
        )
        save_state(state_path, state)
        new_cells += 1
        print(
            f"completed {row['order_index']}/9 {cell_id}; preheat_actual={metadata['preheat_elapsed_s']}s "
            f"quality={metadata['quality_status']} verdict={metadata['verdict']}",
            flush=True,
        )
    complete = sum(
        state.get(row["cell_id"], {}).get("status") == "complete"
        and state.get(row["cell_id"], {}).get("verification_status") == "pass"
        for row in plan
    )
    print(f"targeted_completed_cells={complete}")
    print(f"targeted_total_cells={len(plan)}")
    print(f"targeted_state={base.display_path(state_path)}")
    return 0 if complete == len(plan) else 3


def verify(plan: list[dict[str, str]], state_path: Path) -> int:
    assert_bound_inputs(plan)
    state = load_state(state_path, plan)
    failures: list[str] = []
    refreshed = dict(state)
    for row in plan:
        valid, reasons, metadata = base.verify_cell(row)
        if not valid:
            failures.append(f"{row['cell_id']}:{';'.join(reasons)}")
            continue
        previous = state.get(row["cell_id"])
        refreshed[row["cell_id"]] = state_row(
            row, status="complete", attempt=int(previous["attempt"]) if previous else 1,
            started_at=previous.get("started_at", "") if previous else "",
            finished_at=previous.get("finished_at", "") if previous else "",
            runner_returncode=previous.get("runner_returncode", "0") if previous else "0",
            analyzer_returncode=previous.get("analyzer_returncode", "0") if previous else "0",
            verification_status="pass", metadata=metadata
        )
    if refreshed:
        save_state(state_path, refreshed)
    print(f"verified_cells={len(plan) - len(failures)}")
    print(f"failed_cells={len(failures)}")
    for failure in failures:
        print(f"failure={failure}")
    return 0 if not failures else 4


def dry_run(plan: list[dict[str, str]], plan_path: Path) -> int:
    assert_bound_inputs(plan)
    print(f"targeted_plan={base.display_path(plan_path)}")
    print(f"targeted_cells={len(plan)}")
    print("target_coordinate=CTA48,S1024")
    print("targeted_sessions=3")
    print(f"binary_sha256={plan[0]['binary_sha256']}")
    for row in plan:
        print(
            f"order={int(row['order_index']):02d} session={row['session_index']} "
            f"position={row['implementation_position']} impl={row['exp_impl']}"
        )
        print(f"+ {row['runner_command']}")
        print(f"+ {row['analyzer_command']}")
    return 0


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="softmax_ex2_targeted_selftest_") as directory:
        binary = Path(directory) / "fake_binary"
        binary.write_bytes(b"targeted confirmation self-test\n")
        plan = build_plan(
            target_tag="selftest_v1", order_seed=20260725, binary=binary, gpu_id=0,
            raw_dir=Path(directory) / "raw", summary_dir=Path(directory) / "summary",
            report_dir=Path(directory) / "report", log_dir=Path(directory) / "logs",
        )
        validate_plan_shape(plan)
        assert len(plan) == 9
        assert [row["exp_impl"] for row in plan] == [
            "fp32", "ptx_f16", "ptx_f16x2", "ptx_f16x2", "fp32", "ptx_f16",
            "ptx_f16", "ptx_f16x2", "fp32",
        ]
        for implementation in base.EXP_IMPLS:
            assert sorted(
                int(row["implementation_position"])
                for row in plan if row["exp_impl"] == implementation
            ) == [1, 2, 3]
        mutated = [dict(row) for row in plan]
        mutated[0]["softmax_cols"] = "512"
        try:
            validate_plan_shape(mutated)
        except ValueError:
            pass
        else:
            raise AssertionError("coordinate mutation was not rejected")
        mutated = [dict(row) for row in plan]
        mutated[0]["exp_impl"] = "ptx_f16"
        try:
            validate_plan_shape(mutated)
        except ValueError:
            pass
        else:
            raise AssertionError("Latin position mutation was not rejected")
    print("softmax targeted confirmation self-test passed")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--target-tag")
    result.add_argument("--binary", type=Path, default=Path("build-softmax/a100_fp16_softmax_energy"))
    result.add_argument("--gpu-id", type=int, default=0)
    result.add_argument("--order-seed", type=int, default=20260725)
    result.add_argument("--plan-out", type=Path)
    result.add_argument("--state-out", type=Path)
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--verify-only", action="store_true")
    result.add_argument("--resume", action="store_true")
    result.add_argument("--archive-incomplete", action="store_true")
    result.add_argument("--max-new-cells", type=int, default=0)
    result.add_argument("--self-test", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.target_tag or re.fullmatch(r"[A-Za-z0-9_]+", args.target_tag) is None:
        raise SystemExit("--target-tag is required and may contain only ASCII letters, digits, and underscores")
    if args.gpu_id < 0 or args.order_seed < 0 or args.max_new_cells < 0:
        raise SystemExit("gpu-id/order-seed/max-new-cells must be non-negative")
    if args.dry_run and args.verify_only:
        raise SystemExit("--dry-run and --verify-only are mutually exclusive")
    if args.archive_incomplete and not args.resume:
        raise SystemExit("--archive-incomplete requires --resume")
    binary = base.repository_path(args.binary)
    if not binary.is_file():
        raise SystemExit(f"binary does not exist: {binary}")
    plan_path, state_path = plan_paths(args.target_tag, args.plan_out, args.state_out)
    expected = build_plan(
        target_tag=args.target_tag, order_seed=args.order_seed, binary=binary, gpu_id=args.gpu_id
    )
    plan, created = load_or_create_plan(plan_path, expected)
    print(f"targeted_plan_status={'created' if created else 'verified_existing'}")
    print(f"targeted_plan={base.display_path(plan_path)}")
    if args.dry_run:
        return dry_run(plan, plan_path)
    if args.verify_only:
        return verify(plan, state_path)
    return execute(
        plan, state_path, resume=args.resume, archive_incomplete=args.archive_incomplete,
        max_new_cells=args.max_new_cells
    )


if __name__ == "__main__":
    raise SystemExit(main())
