#!/usr/bin/env python3
"""Run the preregistered 60-cell RTX 3090 Softmax EX2 matrix.

The matrix is fixed at:

* exp implementation: fp32, ptx_f16, ptx_f16x2
* explicit CTA grid: 16, 32, 48, 64
* Softmax columns: 128, 256, 512, 1024, 2048

Twenty unique ``(S, CTA)`` macroblocks are placed in a deterministic
SHA-256-ranked pseudorandom order.  Every macroblock contains all three
implementations.  A deterministic finite backtracking design assigns the six
possible implementation permutations so permutation counts and implementation
positions are balanced globally and inside every S and CTA stratum.

The script deliberately wraps ``run_softmax_operand_rate_atc.py`` instead of
reimplementing its CUDA, quiescence, calibration, bracket, or trace logic.
Every cell receives a fresh tag and a separate raw/manifest/trace/preheat
bundle.  A cell is complete only after the bound analyzer succeeds and this
wrapper independently verifies the evidence bundle fail-closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_REVISION = "rtx3090_softmax_ex2_factorial_matrix_v1"
STATE_REVISION = "rtx3090_softmax_ex2_factorial_matrix_state_v1"
ORDER_ALGORITHM = (
    "sha256_ranked_macroblocks_stratified_balanced_impl_permutations_v2"
)

EXP_IMPLS = ("fp32", "ptx_f16", "ptx_f16x2")
CTA_GRIDS = (16, 32, 48, 64)
SOFTMAX_COLS = (128, 256, 512, 1024, 2048)
EXP_CANONICAL = {
    "fp32": "fp32_fast___expf",
    "ptx_f16": "ptx_ex2_approx_f16",
    "ptx_f16x2": "ptx_ex2_approx_f16x2",
}
EXP_NUMERICAL_CHECK = {
    "fp32": "fp16_softmax_cpu_fp64_v1_pass",
    "ptx_f16": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
    "ptx_f16x2": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
}

TARGET_PROFILE = "rtx3090"
CONTROL_MODE = "probe"
CACHE_CONDITION = "cache_reuse_candidate"
CACHE_POLICY = "default"
LOGIT_SCALE = 4.0
BLOCKS_PER_SM = 2
ROLE_TARGET_SECONDS = 13.0
IDLE_MEASURE_SECONDS = 1.0
PAIRS = 6
BRACKET_WARMUP_PAIRS = 1
BRACKET_ORDER = "counterbalanced6"
BRACKET_IDLE_POLICY = "batch_once"
ENERGY_TRACE_SAMPLE_MS = 500.0
ENERGY_TRACE_MIN_FIT_POINTS = 16
PREHEAT_NOMINAL_SECONDS = 20.0
# The wrapped runner scales a calibrated ITER count rather than enforcing a
# wall-clock sleep.  Historical target-60 runs were about 86% of nominal.
# Preserve target/actual honesty: 20 s is the nominal request, while 16 s is
# the preregistered minimum acceptable observed kernel duration.
PREHEAT_ACTUAL_MIN_SECONDS = 16.0
PREHEAT_ACTUAL_MAX_SECONDS = 30.0

EXPECTED_RAW_ROWS = 3 * PAIRS
EXPECTED_TRIPLET_ROWS = PAIRS
EXPECTED_MATCHED_ROWS = PAIRS // 2

REPO_ROOT = Path(__file__).resolve().parent.parent
CELL_RUNNER = Path("scripts/run_softmax_operand_rate_atc.py")
CELL_ANALYZER = Path("scripts/analyze_softmax_probe_counterbalanced.py")
ANALYZER_HELPER = Path("scripts/analyze_softmax_operand_rate_atc.py")

PLAN_FIELDS = (
    "protocol_revision",
    "matrix_tag",
    "order_algorithm",
    "order_seed",
    "order_index",
    "macroblock_index",
    "macroblock_id",
    "within_macroblock_index",
    "implementation_permutation",
    "cell_id",
    "cell_tag",
    "exp_impl",
    "exp_impl_canonical",
    "grid_blocks",
    "cta_grid_blocks",
    "softmax_cols",
    "target_profile",
    "control_mode",
    "blocks_per_sm",
    "logit_scale",
    "cache_condition",
    "cache_policy",
    "role_target_seconds",
    "idle_measure_seconds",
    "pairs",
    "bracket_warmup_pairs",
    "bracket_order",
    "bracket_idle_policy",
    "energy_trace_sample_ms",
    "energy_trace_min_fit_points",
    "preheat_requested_seconds",
    "preheat_actual_min_seconds",
    "preheat_actual_max_seconds",
    "binary",
    "binary_sha256",
    "cell_runner",
    "cell_runner_sha256",
    "cell_analyzer",
    "cell_analyzer_sha256",
    "analyzer_helper",
    "analyzer_helper_sha256",
    "orchestrator",
    "orchestrator_sha256",
    "raw_csv",
    "manifest_csv",
    "trace_csv",
    "preheat_csv",
    "triplets_csv",
    "matched_csv",
    "summary_csv",
    "analysis_report_md",
    "log_path",
    "runner_command_sha256",
    "runner_command",
    "analyzer_command_sha256",
    "analyzer_command",
)

STATE_FIELDS = (
    "state_revision",
    "protocol_revision",
    "matrix_tag",
    "cell_id",
    "cell_tag",
    "order_index",
    "macroblock_index",
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_sha(row: dict[str, Any]) -> str:
    return sha256_text(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    )


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def repository_path(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def display_path(path: Path | str) -> str:
    candidate = repository_path(path).resolve()
    try:
        return candidate.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(candidate)


def read_csv_strict(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ValueError(f"CSV has an empty or duplicate header: {path}")
        return [dict(row) for row in reader]


def write_csv_atomic(
    path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]
) -> None:
    rows = list(rows)
    fields = list(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="raise", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def hash_rank(seed: int, namespace: str, value: str) -> str:
    return sha256_text(f"{PROTOCOL_REVISION}|{seed}|{namespace}|{value}")


def validate_stratified_implementation_assignment(
    assignments: dict[tuple[int, int], tuple[str, ...]],
    macroblock_order: list[tuple[int, int]] | None = None,
) -> None:
    """Validate the exact v2 permutation constraints independently of search."""
    expected_macroblocks = set(itertools.product(SOFTMAX_COLS, CTA_GRIDS))
    if set(assignments) != expected_macroblocks:
        raise ValueError(
            "implementation assignment does not cover the exact 5x4 macroblock grid"
        )
    allowed_permutations = set(itertools.permutations(EXP_IMPLS))
    if any(
        permutation not in allowed_permutations
        for permutation in assignments.values()
    ):
        raise ValueError("implementation assignment contains a non-permutation")

    permutation_counts = Counter(assignments.values())
    if (
        set(permutation_counts) != allowed_permutations
        or sorted(permutation_counts.values()) != [3, 3, 3, 3, 4, 4]
    ):
        raise ValueError(
            "six implementation permutations must each occur three or four times"
        )

    def position_counts(
        selected: list[tuple[str, ...]], implementation: str
    ) -> list[int]:
        return [
            sum(permutation[position] == implementation for permutation in selected)
            for position in range(len(EXP_IMPLS))
        ]

    for softmax_cols in SOFTMAX_COLS:
        selected = [
            assignments[(softmax_cols, grid_blocks)]
            for grid_blocks in CTA_GRIDS
        ]
        for implementation in EXP_IMPLS:
            counts = position_counts(selected, implementation)
            if sorted(counts) != [1, 1, 2]:
                raise ValueError(
                    f"S={softmax_cols}/{implementation} position counts "
                    f"{counts} do not sort to [1,1,2]"
                )
    for grid_blocks in CTA_GRIDS:
        selected = [
            assignments[(softmax_cols, grid_blocks)]
            for softmax_cols in SOFTMAX_COLS
        ]
        for implementation in EXP_IMPLS:
            counts = position_counts(selected, implementation)
            if sorted(counts) != [1, 2, 2]:
                raise ValueError(
                    f"CTA={grid_blocks}/{implementation} position counts "
                    f"{counts} do not sort to [1,2,2]"
                )
    selected = list(assignments.values())
    for implementation in EXP_IMPLS:
        counts = position_counts(selected, implementation)
        if sorted(counts) != [6, 7, 7]:
            raise ValueError(
                f"global/{implementation} position counts {counts} "
                "do not sort to [6,7,7]"
            )
    if macroblock_order is not None:
        if (
            len(macroblock_order) != 20
            or set(macroblock_order) != expected_macroblocks
        ):
            raise ValueError(
                "chronological macroblock order does not cover the exact grid"
            )
        chronological = [
            assignments[macroblock] for macroblock in macroblock_order
        ]
        for index, (previous, current) in enumerate(
            zip(chronological, chronological[1:]), start=2
        ):
            if previous == current:
                raise ValueError(
                    f"adjacent macroblocks {index - 1}/{index} repeat "
                    "the exact implementation permutation"
                )
            if previous[0] == current[0]:
                raise ValueError(
                    f"adjacent macroblocks {index - 1}/{index} repeat "
                    f"the first implementation {current[0]}"
                )


def stratified_implementation_assignment(
    macroblocks: list[tuple[int, int]], seed: int
) -> dict[tuple[int, int], tuple[str, ...]]:
    """Assign permutations with exact S, CTA, global, and usage balance.

    Candidate order is SHA-256-ranked with the fixed seed.  The first
    macroblock's first ranked permutation is fixed as a symmetry break: all
    constraints are invariant to a global relabeling of implementation/order
    positions, so this does not remove a feasible equivalence class.  The
    remaining finite search uses only deterministic stdlib data structures.
    """
    if len(macroblocks) != 20 or set(macroblocks) != set(
        itertools.product(SOFTMAX_COLS, CTA_GRIDS)
    ):
        raise ValueError("stratified assignment requires the exact 5x4 grid")

    permutations = tuple(itertools.permutations(EXP_IMPLS))
    permutation_positions = tuple(
        {
            implementation: permutation.index(implementation)
            for implementation in EXP_IMPLS
        }
        for permutation in permutations
    )
    candidates = {
        macroblock: tuple(
            sorted(
                range(len(permutations)),
                key=lambda permutation_index: hash_rank(
                    seed,
                    "stratified-implementation-permutation-v2",
                    (
                        f"S{macroblock[0]}|g{macroblock[1]}|"
                        + ">".join(permutations[permutation_index])
                    ),
                ),
            )
        )
        for macroblock in macroblocks
    }

    by_s = {
        softmax_cols: {
            implementation: [0, 0, 0] for implementation in EXP_IMPLS
        }
        for softmax_cols in SOFTMAX_COLS
    }
    by_cta = {
        grid_blocks: {
            implementation: [0, 0, 0] for implementation in EXP_IMPLS
        }
        for grid_blocks in CTA_GRIDS
    }
    global_counts = {
        implementation: [0, 0, 0] for implementation in EXP_IMPLS
    }
    assigned_by_s = Counter({value: 0 for value in SOFTMAX_COLS})
    assigned_by_cta = Counter({value: 0 for value in CTA_GRIDS})
    permutation_counts = [0] * len(permutations)
    assignment_indices: dict[tuple[int, int], int] = {}
    search_nodes = 0
    max_search_nodes = 1_000_000

    def possible_group(
        counts: dict[str, list[int]],
        remaining: int,
        final_sorted_counts: tuple[int, int, int],
    ) -> bool:
        lower = min(final_sorted_counts)
        upper = max(final_sorted_counts)
        for implementation in EXP_IMPLS:
            observed = counts[implementation]
            if any(value > upper for value in observed):
                return False
            if any(value + remaining < lower for value in observed):
                return False
            if remaining == 0 and sorted(observed) != list(
                final_sorted_counts
            ):
                return False
        return True

    def feasible(depth: int) -> bool:
        for softmax_cols in SOFTMAX_COLS:
            if not possible_group(
                by_s[softmax_cols],
                len(CTA_GRIDS) - assigned_by_s[softmax_cols],
                (1, 1, 2),
            ):
                return False
        for grid_blocks in CTA_GRIDS:
            if not possible_group(
                by_cta[grid_blocks],
                len(SOFTMAX_COLS) - assigned_by_cta[grid_blocks],
                (1, 2, 2),
            ):
                return False
        remaining = len(macroblocks) - depth
        if not possible_group(global_counts, remaining, (6, 7, 7)):
            return False
        if any(
            count > 4 or count + remaining < 3
            for count in permutation_counts
        ):
            return False
        if remaining == 0 and sorted(permutation_counts) != [
            3,
            3,
            3,
            3,
            4,
            4,
        ]:
            return False
        return True

    def update(
        macroblock: tuple[int, int], permutation_index: int, delta: int
    ) -> None:
        softmax_cols, grid_blocks = macroblock
        for implementation, position in permutation_positions[
            permutation_index
        ].items():
            by_s[softmax_cols][implementation][position] += delta
            by_cta[grid_blocks][implementation][position] += delta
            global_counts[implementation][position] += delta
        assigned_by_s[softmax_cols] += delta
        assigned_by_cta[grid_blocks] += delta
        permutation_counts[permutation_index] += delta

    def search(depth: int) -> bool:
        nonlocal search_nodes
        search_nodes += 1
        if search_nodes > max_search_nodes:
            raise RuntimeError(
                "stratified implementation assignment exceeded its finite "
                f"search cap ({max_search_nodes} nodes)"
            )
        if depth == len(macroblocks):
            return feasible(depth)
        macroblock = macroblocks[depth]
        candidate_indices = candidates[macroblock]
        if depth == 0:
            candidate_indices = candidate_indices[:1]
        for permutation_index in candidate_indices:
            if depth > 0:
                previous_index = assignment_indices[macroblocks[depth - 1]]
                if permutation_index == previous_index:
                    continue
                if (
                    permutations[permutation_index][0]
                    == permutations[previous_index][0]
                ):
                    continue
            assignment_indices[macroblock] = permutation_index
            update(macroblock, permutation_index, +1)
            if feasible(depth + 1) and search(depth + 1):
                return True
            update(macroblock, permutation_index, -1)
            del assignment_indices[macroblock]
        return False

    if not search(0):
        raise RuntimeError(
            "no stratified implementation assignment satisfies the v2 constraints"
        )
    assignments = {
        macroblock: permutations[assignment_indices[macroblock]]
        for macroblock in macroblocks
    }
    validate_stratified_implementation_assignment(assignments, macroblocks)
    return assignments


def ordered_macroblocks(seed: int) -> list[tuple[int, int]]:
    macroblocks = list(itertools.product(SOFTMAX_COLS, CTA_GRIDS))
    macroblocks.sort(
        key=lambda item: hash_rank(
            seed, "softmax-cta-macroblock", f"S{item[0]}|g{item[1]}"
        )
    )
    if len(macroblocks) != 20 or len(set(macroblocks)) != 20:
        raise AssertionError("matrix must contain exactly 20 unique macroblocks")
    return macroblocks


def exp_output_suffix(exp_impl: str) -> str:
    return "" if exp_impl == "fp32" else f"_{exp_impl}"


def expected_operand_protocol(exp_impl: str) -> str:
    if exp_impl == "fp32":
        return "fp16_softmax_operand_rate_atc_v5_a100_xu_persistent_probe"
    return (
        "fp16_softmax_operand_rate_atc_v6_native_ex2_"
        f"persistent_probe_{exp_impl}"
    )


def command_sha(command: list[str]) -> tuple[str, str]:
    text = shlex.join(command)
    return sha256_text(text), text


def build_plan(
    *,
    matrix_tag: str,
    order_seed: int,
    binary: Path,
    gpu_id: int,
    raw_dir: Path = Path("results/raw"),
    summary_dir: Path = Path("results/summary"),
    report_dir: Path = Path("docs/results"),
    log_dir: Path = Path("results/logs"),
) -> list[dict[str, str]]:
    binary_display = display_path(binary)
    binary_real = repository_path(binary_display)
    runner_display = display_path(CELL_RUNNER)
    analyzer_display = display_path(CELL_ANALYZER)
    analyzer_helper_display = display_path(ANALYZER_HELPER)
    orchestrator_display = display_path(Path(__file__))
    binary_sha = sha256_file(binary_real)
    runner_sha = sha256_file(repository_path(runner_display))
    analyzer_sha = sha256_file(repository_path(analyzer_display))
    analyzer_helper_sha = sha256_file(
        repository_path(analyzer_helper_display)
    )
    orchestrator_sha = sha256_file(repository_path(orchestrator_display))

    rows: list[dict[str, str]] = []
    macroblocks = ordered_macroblocks(order_seed)
    implementation_assignments = stratified_implementation_assignment(
        macroblocks, order_seed
    )
    order_index = 0
    for macroblock_index, (softmax_cols, grid_blocks) in enumerate(
        macroblocks, start=1
    ):
        permutation = implementation_assignments[
            (softmax_cols, grid_blocks)
        ]
        macroblock_id = f"mb{macroblock_index:02d}_g{grid_blocks}_s{softmax_cols}"
        permutation_label = ">".join(permutation)
        for within_index, exp_impl in enumerate(permutation, start=1):
            order_index += 1
            cell_id = (
                f"c{order_index:03d}_mb{macroblock_index:02d}_"
                f"{exp_impl}_g{grid_blocks}_s{softmax_cols}"
            )
            cell_tag = (
                f"{matrix_tag}_mb{macroblock_index:02d}_o{order_index:03d}_"
                f"{exp_impl}_g{grid_blocks}_s{softmax_cols}"
            )
            output_prefix = (
                f"rtx3090_fp16_softmax_operand_rate_atc_{cell_tag}"
                f"{exp_output_suffix(exp_impl)}"
            )
            raw_csv = raw_dir / f"{output_prefix}_raw.csv"
            manifest_csv = raw_dir / f"{output_prefix}_manifest.csv"
            trace_csv = raw_dir / f"{output_prefix}_raw_energy_trace.csv"
            preheat_csv = raw_dir / (
                f"{output_prefix}_{CACHE_CONDITION}_g{grid_blocks}_preheat.csv"
            )
            analysis_prefix = (
                summary_dir
                / f"rtx3090_softmax_ex2_matrix_{matrix_tag}_{cell_id}"
            )
            triplets_csv = Path(f"{analysis_prefix}_triplets.csv")
            matched_csv = Path(f"{analysis_prefix}_matched.csv")
            summary_csv = Path(f"{analysis_prefix}_summary.csv")
            analysis_report = report_dir / (
                f"rtx3090_softmax_ex2_matrix_{matrix_tag}_{cell_id}_ko.md"
            )
            log_path = log_dir / (
                f"rtx3090_softmax_ex2_matrix_{matrix_tag}_{cell_id}.log"
            )

            runner_command = [
                "python3",
                runner_display,
                "--binary",
                binary_display,
                "--gpu-id",
                str(gpu_id),
                "--target-profile",
                TARGET_PROFILE,
                "--exp-impl",
                exp_impl,
                "--softmax-cols",
                str(softmax_cols),
                "--blocks-per-sm",
                str(BLOCKS_PER_SM),
                "--grid-blocks-list",
                str(grid_blocks),
                "--control-mode",
                CONTROL_MODE,
                "--logit-scale",
                str(LOGIT_SCALE),
                "--seconds",
                str(ROLE_TARGET_SECONDS),
                "--idle-measure-seconds",
                str(IDLE_MEASURE_SECONDS),
                "--pairs",
                str(PAIRS),
                "--bracket-warmup-pairs",
                str(BRACKET_WARMUP_PAIRS),
                "--execution-mode",
                "persistent_bracket",
                "--bracket-idle-policy",
                BRACKET_IDLE_POLICY,
                "--bracket-order",
                BRACKET_ORDER,
                "--preheat-seconds",
                str(PREHEAT_NOMINAL_SECONDS),
                "--preheat-actual-min-seconds",
                str(PREHEAT_ACTUAL_MIN_SECONDS),
                "--preheat-actual-max-seconds",
                str(PREHEAT_ACTUAL_MAX_SECONDS),
                "--conditions",
                CACHE_CONDITION,
                "--cache-policy",
                CACHE_POLICY,
                "--energy-trace",
                "1",
                "--energy-trace-sample-ms",
                str(ENERGY_TRACE_SAMPLE_MS),
                "--energy-trace-min-updates",
                str(ENERGY_TRACE_MIN_FIT_POINTS),
                "--tag",
                cell_tag,
                "--out-dir",
                display_path(raw_dir),
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
                display_path(raw_csv),
                "--energy-trace-input",
                display_path(trace_csv),
                "--manifest",
                display_path(manifest_csv),
                "--exp-impl",
                exp_impl,
                "--grid-blocks",
                str(grid_blocks),
                "--triplet-out",
                display_path(triplets_csv),
                "--matched-out",
                display_path(matched_csv),
                "--summary-out",
                display_path(summary_csv),
                "--report-out",
                display_path(analysis_report),
                "--decision-stage",
                "pilot",
                "--energy-trace-min-fit-points",
                str(ENERGY_TRACE_MIN_FIT_POINTS),
                "--bootstrap-samples",
                "4000",
                "--seed",
                str(order_seed + order_index * 1009),
            ]
            runner_command_sha, runner_command_text = command_sha(runner_command)
            analyzer_command_sha, analyzer_command_text = command_sha(
                analyzer_command
            )
            rows.append(
                {
                    "protocol_revision": PROTOCOL_REVISION,
                    "matrix_tag": matrix_tag,
                    "order_algorithm": ORDER_ALGORITHM,
                    "order_seed": str(order_seed),
                    "order_index": str(order_index),
                    "macroblock_index": str(macroblock_index),
                    "macroblock_id": macroblock_id,
                    "within_macroblock_index": str(within_index),
                    "implementation_permutation": permutation_label,
                    "cell_id": cell_id,
                    "cell_tag": cell_tag,
                    "exp_impl": exp_impl,
                    "exp_impl_canonical": EXP_CANONICAL[exp_impl],
                    "grid_blocks": str(grid_blocks),
                    "cta_grid_blocks": str(grid_blocks),
                    "softmax_cols": str(softmax_cols),
                    "target_profile": TARGET_PROFILE,
                    "control_mode": CONTROL_MODE,
                    "blocks_per_sm": str(BLOCKS_PER_SM),
                    "logit_scale": str(LOGIT_SCALE),
                    "cache_condition": CACHE_CONDITION,
                    "cache_policy": CACHE_POLICY,
                    "role_target_seconds": str(ROLE_TARGET_SECONDS),
                    "idle_measure_seconds": str(IDLE_MEASURE_SECONDS),
                    "pairs": str(PAIRS),
                    "bracket_warmup_pairs": str(BRACKET_WARMUP_PAIRS),
                    "bracket_order": BRACKET_ORDER,
                    "bracket_idle_policy": BRACKET_IDLE_POLICY,
                    "energy_trace_sample_ms": str(ENERGY_TRACE_SAMPLE_MS),
                    "energy_trace_min_fit_points": str(
                        ENERGY_TRACE_MIN_FIT_POINTS
                    ),
                    "preheat_requested_seconds": str(
                        PREHEAT_NOMINAL_SECONDS
                    ),
                    "preheat_actual_min_seconds": str(
                        PREHEAT_ACTUAL_MIN_SECONDS
                    ),
                    "preheat_actual_max_seconds": str(
                        PREHEAT_ACTUAL_MAX_SECONDS
                    ),
                    "binary": binary_display,
                    "binary_sha256": binary_sha,
                    "cell_runner": runner_display,
                    "cell_runner_sha256": runner_sha,
                    "cell_analyzer": analyzer_display,
                    "cell_analyzer_sha256": analyzer_sha,
                    "analyzer_helper": analyzer_helper_display,
                    "analyzer_helper_sha256": analyzer_helper_sha,
                    "orchestrator": orchestrator_display,
                    "orchestrator_sha256": orchestrator_sha,
                    "raw_csv": display_path(raw_csv),
                    "manifest_csv": display_path(manifest_csv),
                    "trace_csv": display_path(trace_csv),
                    "preheat_csv": display_path(preheat_csv),
                    "triplets_csv": display_path(triplets_csv),
                    "matched_csv": display_path(matched_csv),
                    "summary_csv": display_path(summary_csv),
                    "analysis_report_md": display_path(analysis_report),
                    "log_path": display_path(log_path),
                    "runner_command_sha256": runner_command_sha,
                    "runner_command": runner_command_text,
                    "analyzer_command_sha256": analyzer_command_sha,
                    "analyzer_command": analyzer_command_text,
                }
            )
    validate_plan_shape(rows)
    return rows


def validate_plan_shape(rows: list[dict[str, str]]) -> None:
    if len(rows) != 60:
        raise ValueError(f"matrix plan must contain 60 cells, got {len(rows)}")
    if [int(row["order_index"]) for row in rows] != list(range(1, 61)):
        raise ValueError("matrix order_index must be exactly 1..60")
    if len({row["cell_id"] for row in rows}) != 60:
        raise ValueError("matrix cell_id values are not unique")
    if len({row["cell_tag"] for row in rows}) != 60:
        raise ValueError("matrix cell_tag values are not fresh/unique")
    factors = {
        (
            row["exp_impl"],
            int(row["grid_blocks"]),
            int(row["softmax_cols"]),
        )
        for row in rows
    }
    expected = set(itertools.product(EXP_IMPLS, CTA_GRIDS, SOFTMAX_COLS))
    if factors != expected:
        raise ValueError("matrix does not contain the exact 3x4x5 factor space")
    if {row.get("order_algorithm", "") for row in rows} != {
        ORDER_ALGORITHM
    }:
        raise ValueError("matrix order algorithm does not match v2")
    stratified_assignments: dict[tuple[int, int], tuple[str, ...]] = {}
    chronological_macroblocks: list[tuple[int, int]] = []
    for macroblock_index in range(1, 21):
        block = sorted(
            (
                row
                for row in rows
                if int(row["macroblock_index"]) == macroblock_index
            ),
            key=lambda row: int(row["within_macroblock_index"]),
        )
        if len(block) != 3 or {row["exp_impl"] for row in block} != set(
            EXP_IMPLS
        ):
            raise ValueError(
                f"macroblock {macroblock_index} does not contain all implementations"
            )
        if len({row["grid_blocks"] for row in block}) != 1 or len(
            {row["softmax_cols"] for row in block}
        ) != 1:
            raise ValueError(
                f"macroblock {macroblock_index} changes S or CTA internally"
            )
        permutation = ">".join(row["exp_impl"] for row in block)
        if {row["implementation_permutation"] for row in block} != {
            permutation
        }:
            raise ValueError(
                f"macroblock {macroblock_index} permutation metadata mismatch"
            )
        coordinate = (
            int(block[0]["softmax_cols"]),
            int(block[0]["grid_blocks"]),
        )
        if coordinate in stratified_assignments:
            raise ValueError(f"duplicate macroblock coordinate {coordinate}")
        stratified_assignments[coordinate] = tuple(
            row["exp_impl"] for row in block
        )
        chronological_macroblocks.append(coordinate)
    validate_stratified_implementation_assignment(
        stratified_assignments, chronological_macroblocks
    )
    all_paths = [
        row[field]
        for row in rows
        for field in (
            "raw_csv",
            "manifest_csv",
            "trace_csv",
            "preheat_csv",
            "triplets_csv",
            "matched_csv",
            "summary_csv",
            "analysis_report_md",
            "log_path",
        )
    ]
    if len(all_paths) != len(set(all_paths)):
        raise ValueError("two matrix cells share an output path")


def compare_plan(
    observed: list[dict[str, str]], expected: list[dict[str, str]]
) -> None:
    if observed == expected:
        return
    if len(observed) != len(expected):
        raise SystemExit(
            f"existing plan row count changed: {len(observed)} != {len(expected)}"
        )
    for row_index, (left, right) in enumerate(zip(observed, expected), start=1):
        keys = set(left) | set(right)
        for key in sorted(keys):
            if left.get(key) != right.get(key):
                raise SystemExit(
                    "existing matrix plan does not match the requested/frozen "
                    f"configuration at row {row_index}, field {key}: "
                    f"{left.get(key)!r} != {right.get(key)!r}; use a fresh "
                    "--matrix-tag after any binary, script, seed, or protocol change"
                )
    raise SystemExit("existing matrix plan differs from expected configuration")


def read_one_row(path: Path, label: str) -> dict[str, str]:
    rows = read_csv_strict(path)
    if len(rows) != 1:
        raise ValueError(f"{label} must contain exactly one row, got {len(rows)}")
    return rows[0]


def uniform(
    rows: list[dict[str, str]], field: str, expected: str, reasons: list[str]
) -> None:
    observed = {row.get(field, "") for row in rows}
    if observed != {expected}:
        reasons.append(
            f"{field}_mismatch({','.join(sorted(observed)) or '<missing>'}!={expected})"
        )


def verify_cell(row: dict[str, str]) -> tuple[bool, list[str], dict[str, str]]:
    """Verify one complete raw+analysis bundle against its immutable plan row."""
    reasons: list[str] = []
    metadata = {
        "actual_binary_sha256": "",
        "preheat_requested_seconds": "",
        "preheat_elapsed_s": "",
        "quality_status": "",
        "verdict": "",
        "artifact_bundle_sha256": "",
    }
    evidence_fields = (
        "raw_csv",
        "manifest_csv",
        "trace_csv",
        "preheat_csv",
        "triplets_csv",
        "matched_csv",
        "summary_csv",
        "analysis_report_md",
        "log_path",
    )
    paths = {field: repository_path(row[field]) for field in evidence_fields}
    for field, path in paths.items():
        if not path.is_file() or path.stat().st_size <= 0:
            reasons.append(f"missing_or_empty_{field}")
    if reasons:
        return False, reasons, metadata

    try:
        raw = read_csv_strict(paths["raw_csv"])
        manifest = read_csv_strict(paths["manifest_csv"])
        trace = read_csv_strict(paths["trace_csv"])
        preheat = read_csv_strict(paths["preheat_csv"])
        triplets = read_csv_strict(paths["triplets_csv"])
        matched = read_csv_strict(paths["matched_csv"])
        summary = read_one_row(paths["summary_csv"], "summary")
    except (OSError, ValueError, csv.Error) as error:
        reasons.append(f"csv_read_error({error})")
        return False, reasons, metadata

    if len(raw) != EXPECTED_RAW_ROWS:
        reasons.append(f"raw_row_count({len(raw)}!={EXPECTED_RAW_ROWS})")
    if len(manifest) != EXPECTED_RAW_ROWS:
        reasons.append(
            f"manifest_row_count({len(manifest)}!={EXPECTED_RAW_ROWS})"
        )
    if not trace:
        reasons.append("trace_has_no_rows")
    if len(preheat) != 1:
        reasons.append(f"preheat_row_count({len(preheat)}!=1)")
    if len(triplets) != EXPECTED_TRIPLET_ROWS:
        reasons.append(
            f"triplet_row_count({len(triplets)}!={EXPECTED_TRIPLET_ROWS})"
        )
    if len(matched) != EXPECTED_MATCHED_ROWS:
        reasons.append(
            f"matched_row_count({len(matched)}!={EXPECTED_MATCHED_ROWS})"
        )

    binary_sha = row["binary_sha256"]
    metadata["actual_binary_sha256"] = binary_sha
    uniform(raw, "binary_sha256", binary_sha, reasons)
    uniform(manifest, "binary_sha256", binary_sha, reasons)
    uniform(raw, "exp_impl", row["exp_impl_canonical"], reasons)
    uniform(manifest, "exp_impl", row["exp_impl_canonical"], reasons)
    uniform(raw, "grid_blocks", row["grid_blocks"], reasons)
    uniform(manifest, "grid_blocks_requested", row["grid_blocks"], reasons)
    uniform(raw, "softmax_cols", row["softmax_cols"], reasons)
    uniform(manifest, "softmax_cols", row["softmax_cols"], reasons)
    uniform(raw, "profile_name", TARGET_PROFILE, reasons)
    uniform(manifest, "target_profile", TARGET_PROFILE, reasons)
    uniform(raw, "cache_condition", CACHE_CONDITION, reasons)
    uniform(manifest, "cache_condition", CACHE_CONDITION, reasons)
    uniform(raw, "cache_policy", CACHE_POLICY, reasons)
    uniform(manifest, "cache_policy", CACHE_POLICY, reasons)
    uniform(
        raw,
        "execution_model",
        "persistent_cuda_context_bracket_v3_counterbalanced6",
        reasons,
    )
    uniform(manifest, "execution_mode", "persistent_bracket", reasons)
    uniform(manifest, "bracket_order", BRACKET_ORDER, reasons)
    # The wrapped runner records the CLI bracket-idle policy under the
    # role-facing raw/manifest field ``idle_baseline_scope``.
    uniform(manifest, "idle_baseline_scope", BRACKET_IDLE_POLICY, reasons)
    uniform(manifest, "energy_trace_enabled", "1", reasons)
    uniform(
        manifest,
        "energy_trace_min_updates",
        str(ENERGY_TRACE_MIN_FIT_POINTS),
        reasons,
    )
    uniform(
        manifest,
        "energy_trace_sample_ms",
        str(ENERGY_TRACE_SAMPLE_MS),
        reasons,
    )
    uniform(manifest, "quiescence_status", "pass", reasons)
    uniform(
        manifest,
        "protocol_revision",
        expected_operand_protocol(row["exp_impl"]),
        reasons,
    )
    uniform(
        manifest,
        "numerical_check_id",
        EXP_NUMERICAL_CHECK[row["exp_impl"]],
        reasons,
    )
    uniform(
        manifest,
        "preheat_requested_seconds",
        f"{PREHEAT_NOMINAL_SECONDS:.6f}",
        reasons,
    )
    uniform(
        manifest,
        "preheat_actual_min_seconds",
        f"{PREHEAT_ACTUAL_MIN_SECONDS:.6f}",
        reasons,
    )
    uniform(
        manifest,
        "preheat_actual_max_seconds",
        f"{PREHEAT_ACTUAL_MAX_SECONDS:.6f}",
        reasons,
    )
    uniform(manifest, "preheat_actual_gate_status", "pass", reasons)
    uniform(manifest, "preheat_role", "preheat", reasons)
    uniform(manifest, "preheat_binary_sha256", binary_sha, reasons)
    uniform(manifest, "preheat_output", row["preheat_csv"], reasons)
    uniform(manifest, "energy_trace_output", row["trace_csv"], reasons)

    raw_keys = {
        (raw_row.get("pair_id", ""), raw_row.get("role", "")) for raw_row in raw
    }
    manifest_keys = {
        (
            manifest_row.get("pair_id", ""),
            manifest_row.get("role", ""),
        )
        for manifest_row in manifest
    }
    trace_keys = {
        (trace_row.get("pair_id", ""), trace_row.get("role", ""))
        for trace_row in trace
    }
    if (
        len(raw_keys) != EXPECTED_RAW_ROWS
        or raw_keys != manifest_keys
        or raw_keys != trace_keys
    ):
        reasons.append("raw_manifest_trace_role_key_mismatch")
    contexts = {raw_row.get("bracket_context_id", "") for raw_row in raw}
    if len(contexts) != 1 or "" in contexts:
        reasons.append("persistent_context_identity_mismatch")
    if {raw_row.get("energy_trace_status", "") for raw_row in raw} != {"pass"}:
        reasons.append("raw_energy_trace_status_not_pass")

    if len(preheat) == 1:
        preheat_row = preheat[0]
        expected_preheat = {
            "role": "preheat",
            "binary_sha256": binary_sha,
            "exp_impl": row["exp_impl_canonical"],
            "grid_blocks": row["grid_blocks"],
            "softmax_cols": row["softmax_cols"],
            "profile_name": TARGET_PROFILE,
        }
        for field, expected in expected_preheat.items():
            if preheat_row.get(field, "") != expected:
                reasons.append(
                    f"preheat_{field}_mismatch"
                )
        elapsed_values = {
            manifest_row.get("preheat_elapsed_s", "") for manifest_row in manifest
        }
        if len(elapsed_values) != 1:
            reasons.append("manifest_preheat_elapsed_not_uniform")
        else:
            elapsed_text = next(iter(elapsed_values))
            metadata["preheat_elapsed_s"] = elapsed_text
            try:
                elapsed = float(elapsed_text)
                preheat_row_elapsed = float(preheat_row.get("elapsed_s", "nan"))
            except ValueError:
                reasons.append("preheat_elapsed_not_numeric")
            else:
                if (
                    not math.isfinite(elapsed)
                    or elapsed < PREHEAT_ACTUAL_MIN_SECONDS
                    or elapsed > PREHEAT_ACTUAL_MAX_SECONDS
                ):
                    reasons.append(
                        "preheat_elapsed_outside_preregistered_range"
                    )
                if (
                    not math.isfinite(preheat_row_elapsed)
                    or not math.isclose(
                        elapsed, preheat_row_elapsed, rel_tol=1e-9, abs_tol=1e-6
                    )
                ):
                    reasons.append("preheat_elapsed_manifest_row_mismatch")
    metadata["preheat_requested_seconds"] = (
        f"{PREHEAT_NOMINAL_SECONDS:.6f}"
    )

    expected_summary = {
        "exp_impl": row["exp_impl_canonical"],
        "grid_blocks": row["grid_blocks"],
        "measured_triplets": str(EXPECTED_TRIPLET_ROWS),
        "matched_orientation_blocks": str(EXPECTED_MATCHED_ROWS),
        "decision_stage": "pilot",
        "configured_energy_trace_min_fit_points": str(
            ENERGY_TRACE_MIN_FIT_POINTS
        ),
        "quality_status": "pass",
    }
    for field, expected in expected_summary.items():
        if summary.get(field, "") != expected:
            reasons.append(f"summary_{field}_mismatch")
    metadata["quality_status"] = summary.get("quality_status", "")
    metadata["verdict"] = summary.get("verdict", "")
    if not metadata["verdict"]:
        reasons.append("summary_verdict_missing")

    if not reasons:
        bundle_manifest = [
            f"{field}:{sha256_file(paths[field])}" for field in evidence_fields
        ]
        metadata["artifact_bundle_sha256"] = sha256_text(
            "\n".join(bundle_manifest) + "\n"
        )
    return not reasons, reasons, metadata


def artifact_paths(row: dict[str, str], include_log: bool = True) -> list[Path]:
    fields = [
        "raw_csv",
        "manifest_csv",
        "trace_csv",
        "preheat_csv",
        "triplets_csv",
        "matched_csv",
        "summary_csv",
        "analysis_report_md",
    ]
    if include_log:
        fields.append("log_path")
    return [repository_path(row[field]) for field in fields]


def archive_incomplete_outputs(
    row: dict[str, str], archive_root: Path, attempt: int
) -> Path | None:
    existing = [
        path
        for path in artifact_paths(row)
        if path.exists() and (path.is_file() or path.is_dir())
    ]
    if not existing:
        return None
    archive = archive_root / row["cell_id"] / (
        f"attempt{attempt:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    archive.mkdir(parents=True, exist_ok=False)
    for source in existing:
        destination = archive / source.name
        shutil.move(str(source), str(destination))
    return archive


def load_state(
    path: Path, plan: list[dict[str, str]]
) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    if not plan:
        raise SystemExit("cannot validate state against an empty plan")
    plan_by_id = {row["cell_id"]: row for row in plan}
    matrix_tag = plan[0]["matrix_tag"]
    rows = read_csv_strict(path)
    state: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get("state_revision") != STATE_REVISION:
            raise SystemExit("matrix state revision mismatch")
        if row.get("matrix_tag") != matrix_tag:
            raise SystemExit("matrix state tag mismatch")
        cell_id = row.get("cell_id", "")
        if not cell_id or cell_id in state:
            raise SystemExit("matrix state contains an empty or duplicate cell_id")
        if cell_id not in plan_by_id:
            raise SystemExit(
                f"matrix state contains unknown cell_id not present in plan: {cell_id}"
            )
        plan_row = plan_by_id[cell_id]
        expected_identity = {
            "protocol_revision": PROTOCOL_REVISION,
            "matrix_tag": plan_row["matrix_tag"],
            "cell_id": plan_row["cell_id"],
            "cell_tag": plan_row["cell_tag"],
            "order_index": plan_row["order_index"],
            "macroblock_index": plan_row["macroblock_index"],
            "exp_impl": plan_row["exp_impl"],
            "grid_blocks": plan_row["grid_blocks"],
            "softmax_cols": plan_row["softmax_cols"],
            "plan_row_sha256": canonical_json_sha(plan_row),
            "log_path": plan_row["log_path"],
        }
        mismatches = [
            field
            for field, expected in expected_identity.items()
            if row.get(field, "") != expected
        ]
        if mismatches:
            raise SystemExit(
                f"matrix state/plan identity mismatch for {cell_id}: "
                + ",".join(mismatches)
            )
        if row.get("status", "") not in {"running", "failed", "complete"}:
            raise SystemExit(
                f"matrix state has invalid status for {cell_id}: "
                f"{row.get('status', '')!r}"
            )
        try:
            attempt = int(row.get("attempt", ""))
        except ValueError as error:
            raise SystemExit(
                f"matrix state has invalid attempt for {cell_id}"
            ) from error
        if attempt < 1:
            raise SystemExit(
                f"matrix state has non-positive attempt for {cell_id}"
            )
        state[cell_id] = row
    return state


def save_state(path: Path, state: dict[str, dict[str, str]]) -> None:
    ordered = sorted(state.values(), key=lambda row: int(row["order_index"]))
    write_csv_atomic(path, ordered, STATE_FIELDS)


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
        "matrix_tag": plan_row["matrix_tag"],
        "cell_id": plan_row["cell_id"],
        "cell_tag": plan_row["cell_tag"],
        "order_index": plan_row["order_index"],
        "macroblock_index": plan_row["macroblock_index"],
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
        "preheat_requested_seconds": metadata.get(
            "preheat_requested_seconds", ""
        ),
        "preheat_elapsed_s": metadata.get("preheat_elapsed_s", ""),
        "quality_status": metadata.get("quality_status", ""),
        "verdict": metadata.get("verdict", ""),
        "artifact_bundle_sha256": metadata.get(
            "artifact_bundle_sha256", ""
        ),
        "plan_row_sha256": canonical_json_sha(plan_row),
        "log_path": plan_row["log_path"],
    }


def assert_bound_inputs(plan: list[dict[str, str]]) -> None:
    if not plan:
        raise SystemExit("empty matrix plan")
    first = plan[0]
    bindings = (
        ("binary", "binary_sha256"),
        ("cell_runner", "cell_runner_sha256"),
        ("cell_analyzer", "cell_analyzer_sha256"),
        ("analyzer_helper", "analyzer_helper_sha256"),
        ("orchestrator", "orchestrator_sha256"),
    )
    for path_field, sha_field in bindings:
        path = repository_path(first[path_field])
        if not path.is_file():
            raise SystemExit(f"bound input is missing: {path}")
        observed = sha256_file(path)
        expected = first[sha_field]
        if observed != expected:
            raise SystemExit(
                f"bound input changed for {path_field}: {observed} != {expected}; "
                "use a fresh matrix tag/plan after rebuilding or editing"
            )
    for row in plan:
        for _path_field, sha_field in bindings:
            if row[sha_field] != first[sha_field]:
                raise SystemExit(f"plan has more than one {sha_field}")


def run_logged(command: list[str], log_path: Path, label: str) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        raise RuntimeError(f"refusing to append to existing cell log: {log_path}")
    print(f"+ {shlex.join(command)}", flush=True)
    with log_path.open("x", encoding="utf-8") as log:
        log.write(f"label={label}\n")
        log.write(f"started_at={timestamp()}\n")
        log.write(f"command={shlex.join(command)}\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
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


def append_log(log_path: Path, text: str) -> None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def plan_paths(
    matrix_tag: str, plan_out: Path | None, state_out: Path | None
) -> tuple[Path, Path]:
    default_prefix = (
        f"rtx3090_softmax_ex2_factorial_matrix_{matrix_tag}"
    )
    plan_path = plan_out or Path(
        f"results/summary/{default_prefix}_plan.csv"
    )
    state_path = state_out or Path(
        f"results/summary/{default_prefix}_state.csv"
    )
    return repository_path(plan_path), repository_path(state_path)


def load_or_create_plan(
    plan_path: Path, expected: list[dict[str, str]]
) -> tuple[list[dict[str, str]], bool]:
    if plan_path.exists():
        observed = read_csv_strict(plan_path)
        compare_plan(observed, expected)
        validate_plan_shape(observed)
        return observed, False
    write_csv_atomic(plan_path, expected, PLAN_FIELDS)
    return expected, True


def execute_matrix(
    plan: list[dict[str, str]],
    state_path: Path,
    *,
    resume: bool,
    archive_incomplete: bool,
    max_new_cells: int,
) -> int:
    state = load_state(state_path, plan)
    if state and not resume:
        raise SystemExit(
            f"state already exists at {state_path}; use --resume after checking it"
        )
    assert_bound_inputs(plan)
    archive_root = repository_path(
        Path("results/archive")
        / f"rtx3090_softmax_ex2_matrix_{plan[0]['matrix_tag']}_incomplete"
    )

    new_cells = 0
    for row in plan:
        cell_id = row["cell_id"]
        previous = state.get(cell_id)
        verified, reasons, metadata = verify_cell(row)
        if verified:
            attempt = int(previous["attempt"]) if previous else 1
            if previous and previous.get("status") == "complete":
                immutable_checks = {
                    "verification_status": "pass",
                    "plan_row_sha256": canonical_json_sha(row),
                    "artifact_bundle_sha256": metadata[
                        "artifact_bundle_sha256"
                    ],
                    "actual_binary_sha256": metadata[
                        "actual_binary_sha256"
                    ],
                    "preheat_elapsed_s": metadata["preheat_elapsed_s"],
                    "quality_status": metadata["quality_status"],
                    "verdict": metadata["verdict"],
                }
                mismatches = [
                    field
                    for field, expected in immutable_checks.items()
                    if previous.get(field, "") != expected
                ]
                if mismatches:
                    raise SystemExit(
                        f"complete state/evidence mutation for {cell_id}: "
                        + ",".join(mismatches)
                    )
            state[cell_id] = state_row(
                row,
                status="complete",
                attempt=attempt,
                started_at=previous.get("started_at", "") if previous else "",
                finished_at=previous.get("finished_at", "") if previous else "",
                runner_returncode=(
                    previous.get("runner_returncode", "0") if previous else "0"
                ),
                analyzer_returncode=(
                    previous.get("analyzer_returncode", "0")
                    if previous
                    else "0"
                ),
                verification_status="pass",
                metadata=metadata,
            )
            save_state(state_path, state)
            print(
                f"skip verified complete cell {row['order_index']}/60 "
                f"{cell_id}",
                flush=True,
            )
            continue

        existing = [path for path in artifact_paths(row) if path.exists()]
        if previous and previous.get("status") == "complete":
            raise SystemExit(
                f"previously complete cell no longer verifies: {cell_id}: "
                + ";".join(reasons)
            )
        attempt = int(previous["attempt"]) + 1 if previous else 1
        if existing:
            if not (resume and archive_incomplete):
                raise SystemExit(
                    f"incomplete/corrupt outputs exist for {cell_id}: "
                    + ", ".join(str(path) for path in existing)
                    + "; inspect them, then resume with --archive-incomplete "
                    "to move only this cell bundle to results/archive"
                )
            archived = archive_incomplete_outputs(
                row, archive_root, attempt - 1 if attempt > 1 else 1
            )
            print(f"archived incomplete cell bundle to {archived}", flush=True)

        if max_new_cells > 0 and new_cells >= max_new_cells:
            print(
                f"max-new-cells={max_new_cells} reached; state remains resumable",
                flush=True,
            )
            break
        started_at = timestamp()
        state[cell_id] = state_row(
            row, status="running", attempt=attempt, started_at=started_at
        )
        save_state(state_path, state)
        log_path = repository_path(row["log_path"])
        runner_command = shlex.split(row["runner_command"])
        analyzer_command = shlex.split(row["analyzer_command"])
        runner_returncode = run_logged(
            runner_command, log_path, f"{cell_id}:runner"
        )
        if runner_returncode != 0:
            state[cell_id] = state_row(
                row,
                status="failed",
                attempt=attempt,
                started_at=started_at,
                finished_at=timestamp(),
                runner_returncode=str(runner_returncode),
                verification_status="fail",
                verification_reasons="runner_nonzero",
            )
            save_state(state_path, state)
            raise SystemExit(
                f"cell runner failed for {cell_id} with {runner_returncode}"
            )
        append_log(
            log_path,
            f"\nanalyzer_command={shlex.join(analyzer_command)}\n",
        )
        # Append analyzer output to the same fresh cell log while still
        # streaming it to the operator.
        print(f"+ {shlex.join(analyzer_command)}", flush=True)
        with log_path.open("a", encoding="utf-8") as log:
            analyzer_process = subprocess.Popen(
                analyzer_command,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert analyzer_process.stdout is not None
            try:
                for line in analyzer_process.stdout:
                    print(line, end="")
                    log.write(line)
            except BaseException:
                analyzer_process.terminate()
                analyzer_process.wait(timeout=10)
                raise
            analyzer_returncode = analyzer_process.wait()
        if analyzer_returncode != 0:
            state[cell_id] = state_row(
                row,
                status="failed",
                attempt=attempt,
                started_at=started_at,
                finished_at=timestamp(),
                runner_returncode="0",
                analyzer_returncode=str(analyzer_returncode),
                verification_status="fail",
                verification_reasons="analyzer_nonzero",
            )
            save_state(state_path, state)
            raise SystemExit(
                f"cell analyzer failed for {cell_id} with {analyzer_returncode}"
            )
        verified, reasons, metadata = verify_cell(row)
        if not verified:
            state[cell_id] = state_row(
                row,
                status="failed",
                attempt=attempt,
                started_at=started_at,
                finished_at=timestamp(),
                runner_returncode="0",
                analyzer_returncode="0",
                verification_status="fail",
                verification_reasons=";".join(reasons),
                metadata=metadata,
            )
            save_state(state_path, state)
            raise SystemExit(
                f"cell evidence verification failed for {cell_id}: "
                + ";".join(reasons)
            )
        state[cell_id] = state_row(
            row,
            status="complete",
            attempt=attempt,
            started_at=started_at,
            finished_at=timestamp(),
            runner_returncode="0",
            analyzer_returncode="0",
            verification_status="pass",
            metadata=metadata,
        )
        save_state(state_path, state)
        new_cells += 1
        print(
            f"completed cell {row['order_index']}/60 {cell_id}; "
            f"preheat_actual={metadata['preheat_elapsed_s']}s "
            f"quality={metadata['quality_status']} verdict={metadata['verdict']}",
            flush=True,
        )

    completed = sum(
        state.get(plan_row["cell_id"], {}).get("status") == "complete"
        and state.get(plan_row["cell_id"], {}).get(
            "verification_status"
        )
        == "pass"
        for plan_row in plan
    )
    print(f"matrix_completed_cells={completed}")
    print(f"matrix_total_cells={len(plan)}")
    print(f"matrix_state={display_path(state_path)}")
    return 0 if completed == len(plan) else 3


def verify_matrix(
    plan: list[dict[str, str]], state_path: Path
) -> int:
    assert_bound_inputs(plan)
    state = load_state(state_path, plan)
    failures: list[str] = []
    refreshed = dict(state)
    for row in plan:
        verified, reasons, metadata = verify_cell(row)
        previous = state.get(row["cell_id"])
        if not verified:
            failures.append(f"{row['cell_id']}:{';'.join(reasons)}")
            continue
        if previous and previous.get("status") == "complete":
            immutable_checks = {
                "verification_status": "pass",
                "plan_row_sha256": canonical_json_sha(row),
                "artifact_bundle_sha256": metadata[
                    "artifact_bundle_sha256"
                ],
                "actual_binary_sha256": metadata["actual_binary_sha256"],
                "preheat_elapsed_s": metadata["preheat_elapsed_s"],
                "quality_status": metadata["quality_status"],
                "verdict": metadata["verdict"],
            }
            mismatches = [
                field
                for field, expected in immutable_checks.items()
                if previous.get(field, "") != expected
            ]
            if mismatches:
                failures.append(
                    f"{row['cell_id']}:complete_state_evidence_mutation("
                    + ",".join(mismatches)
                    + ")"
                )
                continue
        attempt = int(previous["attempt"]) if previous else 1
        refreshed[row["cell_id"]] = state_row(
            row,
            status="complete",
            attempt=attempt,
            started_at=previous.get("started_at", "") if previous else "",
            finished_at=previous.get("finished_at", "") if previous else "",
            runner_returncode=(
                previous.get("runner_returncode", "0") if previous else "0"
            ),
            analyzer_returncode=(
                previous.get("analyzer_returncode", "0") if previous else "0"
            ),
            verification_status="pass",
            metadata=metadata,
        )
    if refreshed:
        save_state(state_path, refreshed)
    print(f"verified_cells={len(plan) - len(failures)}")
    print(f"failed_cells={len(failures)}")
    for failure in failures[:20]:
        print(f"failure={failure}")
    if len(failures) > 20:
        print(f"failure_more={len(failures) - 20}")
    return 0 if not failures else 4


def dry_run_plan(plan: list[dict[str, str]], plan_path: Path) -> int:
    assert_bound_inputs(plan)
    print(f"matrix_plan={display_path(plan_path)}")
    print(f"matrix_cells={len(plan)}")
    print(f"matrix_macroblocks=20")
    print(f"matrix_order_seed={plan[0]['order_seed']}")
    print(f"binary_sha256={plan[0]['binary_sha256']}")
    print(
        "preheat_contract="
        f"nominal_{PREHEAT_NOMINAL_SECONDS:.1f}s_"
        f"actual_{PREHEAT_ACTUAL_MIN_SECONDS:.1f}-"
        f"{PREHEAT_ACTUAL_MAX_SECONDS:.1f}s"
    )
    for row in plan:
        print(
            f"order={int(row['order_index']):03d} "
            f"macroblock={int(row['macroblock_index']):02d} "
            f"position={row['within_macroblock_index']} "
            f"impl={row['exp_impl']} g={row['grid_blocks']} "
            f"S={row['softmax_cols']}"
        )
        print(f"+ {row['runner_command']}")
        print(f"+ {row['analyzer_command']}")
    return 0


def self_test() -> None:
    with tempfile.TemporaryDirectory(
        prefix="softmax_ex2_factorial_matrix_selftest_"
    ) as directory:
        root = Path(directory)
        binary = root / "fake_binary"
        binary.write_bytes(b"softmax-matrix-self-test-binary\n")
        raw_dir = root / "raw"
        summary_dir = root / "summary"
        report_dir = root / "reports"
        log_dir = root / "logs"
        plan = build_plan(
            matrix_tag="selftest_v1",
            order_seed=20260723,
            binary=binary,
            gpu_id=0,
            raw_dir=raw_dir,
            summary_dir=summary_dir,
            report_dir=report_dir,
            log_dir=log_dir,
        )
        assert len(plan) == 60
        assert len(
            {
                (
                    row["exp_impl"],
                    row["grid_blocks"],
                    row["softmax_cols"],
                )
                for row in plan
            }
        ) == 60
        assignments: dict[tuple[int, int], tuple[str, ...]] = {}
        chronological_macroblocks: list[tuple[int, int]] = []
        for macroblock_index in range(1, 21):
            block = sorted(
                (
                    row
                    for row in plan
                    if int(row["macroblock_index"]) == macroblock_index
                ),
                key=lambda row: int(row["within_macroblock_index"]),
            )
            coordinate = (
                int(block[0]["softmax_cols"]),
                int(block[0]["grid_blocks"]),
            )
            assignments[coordinate] = tuple(
                row["exp_impl"] for row in block
            )
            chronological_macroblocks.append(coordinate)
        validate_stratified_implementation_assignment(
            assignments, chronological_macroblocks
        )
        permutation_counts = Counter(assignments.values())
        assert sorted(permutation_counts.values()) == [3, 3, 3, 3, 4, 4]
        for softmax_cols in SOFTMAX_COLS:
            for implementation in EXP_IMPLS:
                counts = [
                    sum(
                        assignments[(softmax_cols, grid_blocks)][position]
                        == implementation
                        for grid_blocks in CTA_GRIDS
                    )
                    for position in range(3)
                ]
                assert sorted(counts) == [1, 1, 2]
        for grid_blocks in CTA_GRIDS:
            for implementation in EXP_IMPLS:
                counts = [
                    sum(
                        assignments[(softmax_cols, grid_blocks)][position]
                        == implementation
                        for softmax_cols in SOFTMAX_COLS
                    )
                    for position in range(3)
                ]
                assert sorted(counts) == [1, 2, 2]
        for implementation in EXP_IMPLS:
            counts = [
                sum(
                    permutation[position] == implementation
                    for permutation in assignments.values()
                )
                for position in range(3)
            ]
            assert sorted(counts) == [6, 7, 7]
        chronological = [
            assignments[coordinate] for coordinate in chronological_macroblocks
        ]
        assert all(
            previous != current
            and previous[0] != current[0]
            for previous, current in zip(
                chronological, chronological[1:]
            )
        )
        mutated_plan = [dict(row) for row in plan]
        mutated_plan[0]["order_algorithm"] = (
            "sha256_ranked_macroblocks_balanced_impl_permutations_v1"
        )
        try:
            compare_plan(mutated_plan, plan)
        except SystemExit:
            pass
        else:
            raise AssertionError("plan mutation was not rejected")
        assert all("--pairs 6" in row["runner_command"] for row in plan)
        assert all(
            "--bracket-order counterbalanced6" in row["runner_command"]
            for row in plan
        )
        assert all("--seconds 13.0" in row["runner_command"] for row in plan)
        assert all(
            "--energy-trace-sample-ms 500.0" in row["runner_command"]
            for row in plan
        )
        assert all(
            "--energy-trace-min-updates 16" in row["runner_command"]
            for row in plan
        )
        assert all(
            "--preheat-seconds 20.0" in row["runner_command"] for row in plan
        )
        assert all(
            "--preheat-actual-min-seconds 16.0"
            in row["runner_command"]
            for row in plan
        )
        assert all(
            "--preheat-actual-max-seconds 30.0"
            in row["runner_command"]
            for row in plan
        )
        assert {
            row["analyzer_helper"] for row in plan
        } == {display_path(ANALYZER_HELPER)}
        assert len({row["analyzer_helper_sha256"] for row in plan}) == 1

        test_row = dict(plan[0])
        raw_rows: list[dict[str, str]] = []
        manifest_rows: list[dict[str, str]] = []
        trace_rows: list[dict[str, str]] = []
        for pair in range(PAIRS):
            for sequence, role in enumerate(
                ("probe_before", "full", "probe_after")
            ):
                pair_id = f"selftest_p{pair:02d}"
                raw_rows.append(
                    {
                        "pair_id": pair_id,
                        "role": role,
                        "binary_sha256": test_row["binary_sha256"],
                        "exp_impl": test_row["exp_impl_canonical"],
                        "grid_blocks": test_row["grid_blocks"],
                        "softmax_cols": test_row["softmax_cols"],
                        "profile_name": TARGET_PROFILE,
                        "cache_condition": CACHE_CONDITION,
                        "cache_policy": CACHE_POLICY,
                        "execution_model": (
                            "persistent_cuda_context_bracket_v3_counterbalanced6"
                        ),
                        "bracket_context_id": "selftest_context",
                        "energy_trace_status": "pass",
                    }
                )
                manifest_rows.append(
                    {
                        "pair_id": pair_id,
                        "role": role,
                        "binary_sha256": test_row["binary_sha256"],
                        "exp_impl": test_row["exp_impl_canonical"],
                        "grid_blocks_requested": test_row["grid_blocks"],
                        "softmax_cols": test_row["softmax_cols"],
                        "target_profile": TARGET_PROFILE,
                        "cache_condition": CACHE_CONDITION,
                        "cache_policy": CACHE_POLICY,
                        "execution_mode": "persistent_bracket",
                        "bracket_order": BRACKET_ORDER,
                        "idle_baseline_scope": BRACKET_IDLE_POLICY,
                        "energy_trace_enabled": "1",
                        "energy_trace_min_updates": str(
                            ENERGY_TRACE_MIN_FIT_POINTS
                        ),
                        "energy_trace_sample_ms": str(
                            ENERGY_TRACE_SAMPLE_MS
                        ),
                        "quiescence_status": "pass",
                        "protocol_revision": expected_operand_protocol(
                            test_row["exp_impl"]
                        ),
                        "numerical_check_id": EXP_NUMERICAL_CHECK[
                            test_row["exp_impl"]
                        ],
                        "preheat_requested_seconds": (
                            f"{PREHEAT_NOMINAL_SECONDS:.6f}"
                        ),
                        "preheat_elapsed_s": "17.25",
                        "preheat_actual_min_seconds": (
                            f"{PREHEAT_ACTUAL_MIN_SECONDS:.6f}"
                        ),
                        "preheat_actual_max_seconds": (
                            f"{PREHEAT_ACTUAL_MAX_SECONDS:.6f}"
                        ),
                        "preheat_actual_gate_status": "pass",
                        "preheat_role": "preheat",
                        "preheat_binary_sha256": test_row["binary_sha256"],
                        "preheat_output": test_row["preheat_csv"],
                        "energy_trace_output": test_row["trace_csv"],
                    }
                )
                trace_rows.append(
                    {
                        "pair_id": pair_id,
                        "role": role,
                        "sample_index": str(sequence),
                    }
                )
        preheat_rows = [
            {
                "role": "preheat",
                "binary_sha256": test_row["binary_sha256"],
                "exp_impl": test_row["exp_impl_canonical"],
                "grid_blocks": test_row["grid_blocks"],
                "softmax_cols": test_row["softmax_cols"],
                "profile_name": TARGET_PROFILE,
                "elapsed_s": "17.25",
            }
        ]
        triplet_rows = [{"pair_index": str(index)} for index in range(PAIRS)]
        matched_rows = [
            {"matched_block": str(index)} for index in range(PAIRS // 2)
        ]
        summary_rows = [
            {
                "exp_impl": test_row["exp_impl_canonical"],
                "grid_blocks": test_row["grid_blocks"],
                "measured_triplets": str(EXPECTED_TRIPLET_ROWS),
                "matched_orientation_blocks": str(EXPECTED_MATCHED_ROWS),
                "decision_stage": "pilot",
                "configured_energy_trace_min_fit_points": str(
                    ENERGY_TRACE_MIN_FIT_POINTS
                ),
                "quality_status": "pass",
                "verdict": "not_identified",
            }
        ]
        write_csv_atomic(
            repository_path(test_row["raw_csv"]),
            raw_rows,
            raw_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["manifest_csv"]),
            manifest_rows,
            manifest_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["trace_csv"]),
            trace_rows,
            trace_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["preheat_csv"]),
            preheat_rows,
            preheat_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["triplets_csv"]),
            triplet_rows,
            triplet_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["matched_csv"]),
            matched_rows,
            matched_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["summary_csv"]),
            summary_rows,
            summary_rows[0].keys(),
        )
        repository_path(test_row["analysis_report_md"]).parent.mkdir(
            parents=True, exist_ok=True
        )
        repository_path(test_row["analysis_report_md"]).write_text(
            "# self-test report\n", encoding="utf-8"
        )
        repository_path(test_row["log_path"]).parent.mkdir(
            parents=True, exist_ok=True
        )
        repository_path(test_row["log_path"]).write_text(
            "self-test non-empty execution log\n", encoding="utf-8"
        )
        verified, reasons, metadata = verify_cell(test_row)
        assert verified, reasons
        assert metadata["preheat_elapsed_s"] == "17.25"

        repository_path(test_row["log_path"]).unlink()
        verified, reasons, _metadata = verify_cell(test_row)
        assert not verified and "missing_or_empty_log_path" in reasons
        repository_path(test_row["log_path"]).write_text(
            "self-test non-empty execution log\n", encoding="utf-8"
        )
        state_path = root / "state.csv"
        valid_state = state_row(
            test_row,
            status="complete",
            attempt=1,
            started_at="2026-07-23T00:00:00+09:00",
            finished_at="2026-07-23T00:01:00+09:00",
            runner_returncode="0",
            analyzer_returncode="0",
            verification_status="pass",
            metadata=metadata,
        )
        write_csv_atomic(state_path, [valid_state], STATE_FIELDS)
        assert set(load_state(state_path, plan)) == {test_row["cell_id"]}
        unknown_state = dict(valid_state)
        unknown_state["cell_id"] = "unknown_cell"
        write_csv_atomic(state_path, [unknown_state], STATE_FIELDS)
        try:
            load_state(state_path, plan)
        except SystemExit:
            pass
        else:
            raise AssertionError("unknown state cell_id was not rejected")
        mutated_state = dict(valid_state)
        mutated_state["order_index"] = "999"
        write_csv_atomic(state_path, [mutated_state], STATE_FIELDS)
        try:
            load_state(state_path, plan)
        except SystemExit:
            pass
        else:
            raise AssertionError("state/plan identity mutation was not rejected")

        manifest_rows[0]["binary_sha256"] = "0" * 64
        write_csv_atomic(
            repository_path(test_row["manifest_csv"]),
            manifest_rows,
            manifest_rows[0].keys(),
        )
        verified, reasons, _metadata = verify_cell(test_row)
        assert not verified and any(
            reason.startswith("binary_sha256_mismatch") for reason in reasons
        )
        manifest_rows[0]["binary_sha256"] = test_row["binary_sha256"]
        for manifest_row in manifest_rows:
            manifest_row["preheat_elapsed_s"] = "15.99"
        preheat_rows[0]["elapsed_s"] = "15.99"
        write_csv_atomic(
            repository_path(test_row["manifest_csv"]),
            manifest_rows,
            manifest_rows[0].keys(),
        )
        write_csv_atomic(
            repository_path(test_row["preheat_csv"]),
            preheat_rows,
            preheat_rows[0].keys(),
        )
        verified, reasons, _metadata = verify_cell(test_row)
        assert not verified and (
            "preheat_elapsed_outside_preregistered_range" in reasons
        )
    print(
        "softmax EX2 factorial matrix self-test passed: "
        "60-cell balance, command freeze, evidence verification, "
        "binary-SHA mutation, and preheat-floor mutation"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--matrix-tag")
    result.add_argument(
        "--binary",
        type=Path,
        default=Path("build-softmax/a100_fp16_softmax_energy"),
    )
    result.add_argument("--gpu-id", type=int, default=0)
    result.add_argument("--order-seed", type=int, default=20260723)
    result.add_argument("--plan-out", type=Path)
    result.add_argument("--state-out", type=Path)
    result.add_argument(
        "--dry-run",
        action="store_true",
        help="create/validate the immutable plan and print all commands; do not use the GPU",
    )
    result.add_argument(
        "--verify-only",
        action="store_true",
        help="verify all 60 evidence bundles and refresh state; do not run cells",
    )
    result.add_argument(
        "--resume",
        action="store_true",
        help="skip only cells whose full evidence bundle still verifies",
    )
    result.add_argument(
        "--archive-incomplete",
        action="store_true",
        help=(
            "with --resume, move only the current incomplete cell bundle to "
            "results/archive before a fresh retry"
        ),
    )
    result.add_argument(
        "--max-new-cells",
        type=int,
        default=0,
        help="bounded operational checkpoint; 0 runs every remaining planned cell",
    )
    result.add_argument("--self-test", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.matrix_tag:
        raise SystemExit("--matrix-tag is required unless --self-test is used")
    if re.fullmatch(r"[A-Za-z0-9_]+", args.matrix_tag) is None:
        raise SystemExit(
            "--matrix-tag may contain only ASCII letters, digits, and underscores"
        )
    if args.gpu_id < 0 or args.order_seed < 0 or args.max_new_cells < 0:
        raise SystemExit("gpu-id/order-seed/max-new-cells must be non-negative")
    if args.archive_incomplete and not args.resume:
        raise SystemExit("--archive-incomplete requires --resume")
    if args.dry_run and args.verify_only:
        raise SystemExit("--dry-run and --verify-only are mutually exclusive")
    binary = repository_path(args.binary)
    if not binary.is_file():
        raise SystemExit(f"binary does not exist: {binary}")
    plan_path, state_path = plan_paths(
        args.matrix_tag, args.plan_out, args.state_out
    )
    expected = build_plan(
        matrix_tag=args.matrix_tag,
        order_seed=args.order_seed,
        binary=binary,
        gpu_id=args.gpu_id,
    )
    plan, created = load_or_create_plan(plan_path, expected)
    print(
        f"matrix_plan_status={'created' if created else 'verified_existing'}"
    )
    print(f"matrix_plan={display_path(plan_path)}")
    if args.dry_run:
        return dry_run_plan(plan, plan_path)
    if args.verify_only:
        return verify_matrix(plan, state_path)
    return execute_matrix(
        plan,
        state_path,
        resume=args.resume,
        archive_incomplete=args.archive_incomplete,
        max_new_cells=args.max_new_cells,
    )


if __name__ == "__main__":
    raise SystemExit(main())
