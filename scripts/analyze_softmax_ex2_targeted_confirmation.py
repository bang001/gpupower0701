#!/usr/bin/env python3
"""Analyze the focused CTA=48/S=1024 Softmax EX2 confirmation.

The primary independent unit is one fresh session (one counterbalanced cell
per implementation), not its three matched orientation blocks.  The script
therefore reports incremental pJ per input element at the session level while
retaining block-level diagnostics separately.  The legacy two 60-cell target
measurements are exported only as historical context and are never pooled
with the new confirmation aggregate.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ANALYSIS_REVISION = "rtx3090_softmax_ex2_targeted_confirmation_analysis_v1"
TARGET_GRID_BLOCKS = 48
TARGET_SOFTMAX_COLS = 1024
EXPECTED_IMPLS = ("fp32", "ptx_f16", "ptx_f16x2")
CANONICAL_IMPL = {
    "fp32": "fp32_fast___expf",
    "ptx_f16": "ptx_ex2_approx_f16",
    "ptx_f16x2": "ptx_ex2_approx_f16x2",
}
T95_DF2 = 4.302652729911275


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_path(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repository_root() / candidate


def display_path(path: Path | str) -> str:
    candidate = repo_path(path).resolve()
    try:
        return candidate.relative_to(repository_root()).as_posix()
    except ValueError:
        return str(candidate)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"invalid CSV header: {path}")
        return [dict(row) for row in reader]


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"refusing to write an empty evidence table: {path}")
    fields: list[str] = []
    for row in values:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)
    temporary.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def number(row: dict[str, str], field: str, source: Path) -> float:
    raw = row.get(field, "")
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{source}: non-numeric {field}={raw!r}") from error
    if not math.isfinite(value):
        raise ValueError(f"{source}: non-finite {field}={raw!r}")
    return value


def optional_number(row: dict[str, str], field: str, source: Path) -> float | None:
    """Read an optional numeric field; compiled FP32 PTX-op accounting is N/A."""
    raw = row.get(field, "").strip()
    if raw.lower() in {"", "nan", "n/a", "not_applicable"}:
        return None
    return number(row, field, source)


def integer(row: dict[str, str], field: str, source: Path) -> int:
    value = number(row, field, source)
    if value != int(value):
        raise ValueError(f"{source}: non-integral {field}={value}")
    return int(value)


def require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {observed!r}")


def require_close(observed: float, expected: float, label: str) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-10, abs_tol=1e-9):
        raise ValueError(f"{label}: expected {expected}, got {observed}")


def summary_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty value vector")
    count = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if count > 1 else 0.0
    result: dict[str, float | int] = {
        "session_count": count,
        "mean_incremental_pJ_per_element": mean,
        "median_incremental_pJ_per_element": statistics.median(values),
        "sample_sd_incremental_pJ_per_element": sd,
        "min_incremental_pJ_per_element": min(values),
        "max_incremental_pJ_per_element": max(values),
    }
    if count == 3:
        half_width = T95_DF2 * sd / math.sqrt(count)
        result["diagnostic_t95_low_incremental_pJ_per_element"] = mean - half_width
        result["diagnostic_t95_high_incremental_pJ_per_element"] = mean + half_width
    else:
        result["diagnostic_t95_low_incremental_pJ_per_element"] = float("nan")
        result["diagnostic_t95_high_incremental_pJ_per_element"] = float("nan")
    return result


def parse_validation_log(path: Path, impl: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing validation log: {path}")
    text = path.read_text(encoding="utf-8")
    numerical = re.search(
        r"^numerical_check_id=(?P<id>\S+) exp_impl=(?P<canonical>\S+) "
        r"max_abs_error=(?P<abs>\S+) max_row_sum_error=(?P<sum>\S+) "
        r"control_treatment_bit_identical=(?P<identical>\S+)",
        text,
        re.MULTILINE,
    )
    if numerical is None:
        raise ValueError(f"missing numerical validation record: {path}")
    require_equal(numerical.group("canonical"), CANONICAL_IMPL[impl], f"{path}: validation canonical impl")
    row: dict[str, Any] = {
        "implementation": impl,
        "canonical_implementation": numerical.group("canonical"),
        "validation_log": display_path(path),
        "numerical_check_id": numerical.group("id"),
        "max_abs_error": float(numerical.group("abs")),
        "max_row_sum_error": float(numerical.group("sum")),
        "control_treatment_bit_identical": numerical.group("identical"),
        "native_all_encoding_validation_id": "not_applicable",
        "packed_scalar_bit_mismatch_count": "not_applicable",
        "nan_classification_failure_count": "not_applicable",
        "max_normal_relative_error": "not_applicable",
        "documented_relative_error_bound": "not_applicable",
        "corner_cases_ok": "not_applicable",
        "verdict": "pass",
    }
    if impl != "fp32":
        native = re.search(
            r"^native_ex2_validation_id=(?P<id>\S+) "
            r"packed_scalar_bit_mismatch_count=(?P<mismatch>\d+) "
            r"nan_classification_failure_count=(?P<nan>\d+) .*?"
            r"max_normal_relative_error=(?P<error>\S+) "
            r"documented_relative_error_bound=(?P<bound>\S+) "
            r"corner_cases_ok=(?P<corner>\S+)",
            text,
            re.MULTILINE,
        )
        if native is None:
            raise ValueError(f"missing native all-encoding validation record: {path}")
        require_equal(native.group("mismatch"), "0", f"{path}: packed/scalar mismatch count")
        require_equal(native.group("nan"), "0", f"{path}: NaN classification failure count")
        require_equal(native.group("corner"), "true", f"{path}: native corner-case validation")
        row.update(
            {
                "native_all_encoding_validation_id": native.group("id"),
                "packed_scalar_bit_mismatch_count": int(native.group("mismatch")),
                "nan_classification_failure_count": int(native.group("nan")),
                "max_normal_relative_error": float(native.group("error")),
                "documented_relative_error_bound": float(native.group("bound")),
                "corner_cases_ok": native.group("corner"),
            }
        )
    return row


def historical_context(coordinates_path: Path) -> list[dict[str, Any]]:
    rows = [
        row
        for row in read_csv(coordinates_path)
        if row.get("grid_blocks") == str(TARGET_GRID_BLOCKS)
        and row.get("softmax_cols") == str(TARGET_SOFTMAX_COLS)
        and row.get("implementation") in EXPECTED_IMPLS
    ]
    if len(rows) != 3:
        raise ValueError(f"expected 3 historical target coordinate rows, found {len(rows)}")
    public: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda entry: EXPECTED_IMPLS.index(entry["implementation"])):
        for session, column, tag_column in (
            ("matrix60_original", "original_effect_pJ_per_logical_scalar_exponent_result", "original_matrix_tag"),
            ("matrix60_reproduction", "reproduction_effect_pJ_per_logical_scalar_exponent_result", "reproduction_matrix_tag"),
        ):
            public.append(
                {
                    "source_group": "historical_context_not_primary_pool",
                    "session_label": session,
                    "matrix_tag": row[tag_column],
                    "implementation": row["implementation"],
                    "grid_blocks": TARGET_GRID_BLOCKS,
                    "softmax_cols": TARGET_SOFTMAX_COLS,
                    "incremental_pJ_per_element": number(row, column, coordinates_path),
                    "standalone_verdict": row[
                        "original_standalone_verdict" if session == "matrix60_original" else "reproduction_standalone_verdict"
                    ],
                    "original_minus_reproduction_delta_pJ_per_element": number(
                        row, "signed_delta_pJ_per_logical_scalar_exponent_result", coordinates_path
                    ),
                    "coordinate_source": display_path(coordinates_path),
                }
            )
    return public


def historical_scalar_blocks(context_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = repository_root()
    public: list[dict[str, Any]] = []
    targets = [row for row in context_rows if row["implementation"] == "ptx_f16"]
    for target in targets:
        tag = str(target["matrix_tag"])
        plan_path = root / f"results/summary/rtx3090_softmax_ex2_factorial_matrix_{tag}_plan.csv"
        if not plan_path.is_file():
            raise ValueError(f"missing historical plan: {plan_path}")
        plan = [
            row for row in read_csv(plan_path)
            if row.get("exp_impl") == "ptx_f16"
            and row.get("grid_blocks") == str(TARGET_GRID_BLOCKS)
            and row.get("softmax_cols") == str(TARGET_SOFTMAX_COLS)
        ]
        if len(plan) != 1:
            raise ValueError(f"historical scalar target plan lookup failed: {plan_path}")
        matched_path = repo_path(plan[0]["matched_csv"])
        for matched in read_csv(matched_path):
            public.append(
                {
                    "source_group": "historical_context_not_primary_pool",
                    "session_label": target["session_label"],
                    "implementation": "ptx_f16",
                    "matched_block": integer(matched, "matched_block", matched_path),
                    "orientation_order": matched["chronological_orientation_order"],
                    "forward_incremental_pJ_per_element": number(
                        matched, "forward_pJ_per_logical_scalar_exponent_result", matched_path
                    ),
                    "reverse_incremental_pJ_per_element": number(
                        matched, "reverse_pJ_per_logical_scalar_exponent_result", matched_path
                    ),
                    "order_balanced_incremental_pJ_per_element": number(
                        matched, "order_balanced_effect_pJ_per_logical_scalar_exponent_result", matched_path
                    ),
                    "matched_source": display_path(matched_path),
                }
            )
    return public


def analyze(
    *,
    target_tag: str,
    plan_path: Path,
    state_path: Path,
    sass_path: Path,
    ncu_path: Path,
    validation_log_dir: Path,
    historical_coordinates_path: Path,
    out_prefix: Path,
    report_out: Path,
) -> dict[str, Path]:
    plan = read_csv(plan_path)
    state = read_csv(state_path)
    if len(plan) != 9 or len(state) != 9:
        raise ValueError("focused confirmation requires exactly nine plan and state rows")
    state_by_id = {row.get("cell_id", ""): row for row in state}
    if len(state_by_id) != 9:
        raise ValueError("targeted state has duplicate or missing cell identities")
    observed_impls = {row.get("exp_impl", "") for row in plan}
    require_equal(observed_impls, set(EXPECTED_IMPLS), "targeted plan implementation set")
    for impl in EXPECTED_IMPLS:
        positions = sorted(
            integer(row, "implementation_position", plan_path)
            for row in plan if row["exp_impl"] == impl
        )
        require_equal(positions, [1, 2, 3], f"{impl} session position balance")

    session_cells: list[dict[str, Any]] = []
    matched_blocks: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    binary_hashes: set[str] = set()
    for cell in sorted(plan, key=lambda row: int(row["order_index"])):
        cell_id = cell["cell_id"]
        state_row = state_by_id.get(cell_id)
        if state_row is None:
            raise ValueError(f"missing state row for {cell_id}")
        require_equal(state_row.get("status"), "complete", f"{cell_id}: state status")
        require_equal(state_row.get("verification_status"), "pass", f"{cell_id}: state verification")
        summary_path = repo_path(cell["summary_csv"])
        matched_path = repo_path(cell["matched_csv"])
        raw_path = repo_path(cell["raw_csv"])
        manifest_path = repo_path(cell["manifest_csv"])
        summary_rows = read_csv(summary_path)
        if len(summary_rows) != 1:
            raise ValueError(f"{summary_path}: expected one summary row")
        summary = summary_rows[0]
        matched = read_csv(matched_path)
        raw = read_csv(raw_path)
        manifest = read_csv(manifest_path)
        if len(matched) != 3 or len(raw) != 18 or len(manifest) != 18:
            raise ValueError(f"{cell_id}: incomplete cell evidence cardinality")
        require_equal(summary.get("quality_status"), "pass", f"{cell_id}: summary quality")
        require_equal(summary.get("exp_impl"), CANONICAL_IMPL[cell["exp_impl"]], f"{cell_id}: summary implementation")
        require_equal(summary.get("grid_blocks"), str(TARGET_GRID_BLOCKS), f"{cell_id}: summary CTA")
        require_equal(summary.get("matched_orientation_blocks"), "3", f"{cell_id}: matched-block count")
        require_equal({row.get("quality_status") for row in matched}, {"pass"}, f"{cell_id}: matched quality")
        require_equal({row.get("binary_sha256") for row in raw}, {cell["binary_sha256"]}, f"{cell_id}: raw binary hash")
        require_equal({row.get("binary_sha256") for row in manifest}, {cell["binary_sha256"]}, f"{cell_id}: manifest binary hash")
        require_equal({row.get("softmax_cols") for row in raw}, {str(TARGET_SOFTMAX_COLS)}, f"{cell_id}: raw S")
        require_equal({row.get("grid_blocks") for row in raw}, {str(TARGET_GRID_BLOCKS)}, f"{cell_id}: raw CTA")
        require_equal({row.get("operand_delta_per_element") for row in raw if row.get("extra_exp_probe") == "true"}, {"1"}, f"{cell_id}: treatment operand delta")
        binary_hashes.add(cell["binary_sha256"])

        denominator = integer(summary, "logical_scalar_exponent_results_per_treatment_role", summary_path)
        ptx_count_value = optional_number(summary, "ptx_ex2_instructions_per_treatment_role", summary_path)
        ptx_count = int(ptx_count_value) if ptx_count_value is not None else None
        treatment = [row for row in raw if row.get("extra_exp_probe") == "true"]
        if not treatment:
            raise ValueError(f"{cell_id}: missing treatment rows")
        n_elements = {integer(row, "n_elements", raw_path) for row in treatment}
        if len(n_elements) != 1:
            raise ValueError(f"{cell_id}: treatment denominator is not uniform")
        require_equal(denominator, next(iter(n_elements)), f"{cell_id}: logical result / element denominator")
        results_per_ptx = integer(summary, "exp_results_per_ptx_instruction", summary_path)
        if cell["exp_impl"] == "fp32":
            require_equal(ptx_count, None, f"{cell_id}: FP32 PTX-op denominator applicability")
        else:
            if ptx_count is None:
                raise ValueError(f"{cell_id}: native path missing PTX-op denominator")
            require_equal(ptx_count * results_per_ptx, denominator, f"{cell_id}: PTX-result denominator relation")
        summary_effect = number(summary, "order_balanced_mean_pJ_per_logical_scalar_exponent_result", summary_path)
        operand_effect = number(summary, "order_balanced_mean_pJ_per_operand", summary_path)
        require_close(summary_effect, operand_effect, f"{cell_id}: logical/operand equivalence")
        matched_effects = [
            number(row, "order_balanced_effect_pJ_per_logical_scalar_exponent_result", matched_path)
            for row in matched
        ]
        require_close(summary_effect, statistics.fmean(matched_effects), f"{cell_id}: summary/matched effect")

        temperatures = [
            number(row, field, raw_path)
            for row in raw for field in ("temp_before_C", "temp_after_C")
        ]
        sm_clocks = [
            number(row, field, raw_path)
            for row in raw for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
        ]
        r2_values = [number(row, "energy_trace_r2", raw_path) for row in raw]
        fit_points = [integer(row, "energy_trace_fit_point_count", raw_path) for row in raw]
        treatment_power = [number(row, "energy_trace_power_W", raw_path) for row in treatment]
        controls = [row for row in raw if row.get("extra_exp_probe") == "false"]
        control_power = [number(row, "energy_trace_power_W", raw_path) for row in controls]
        preheats = {number(row, "preheat_elapsed_s", manifest_path) for row in manifest}
        if len(preheats) != 1:
            raise ValueError(f"{cell_id}: preheat duration not uniform")
        session_row = {
            "target_tag": target_tag,
            "session_id": cell["session_id"],
            "session_index": integer(cell, "session_index", plan_path),
            "implementation_position": integer(cell, "implementation_position", plan_path),
            "session_order": cell["session_order"],
            "implementation": cell["exp_impl"],
            "canonical_implementation": CANONICAL_IMPL[cell["exp_impl"]],
            "grid_blocks": TARGET_GRID_BLOCKS,
            "softmax_cols": TARGET_SOFTMAX_COLS,
            "incremental_pJ_per_element": summary_effect,
            "incremental_pJ_per_logical_scalar_exponent_result": summary_effect,
            "incremental_pJ_per_ptx_ex2_instruction": optional_number(summary, "order_balanced_mean_pJ_per_ptx_ex2_instruction", summary_path) if cell["exp_impl"] != "fp32" else "not_applicable",
            "forward_incremental_pJ_per_element": number(summary, "forward_mean_pJ_per_logical_scalar_exponent_result", summary_path),
            "reverse_incremental_pJ_per_element": number(summary, "reverse_mean_pJ_per_logical_scalar_exponent_result", summary_path),
            "matched_block_sd_pJ_per_element": number(summary, "order_balanced_sd_pJ_per_operand", summary_path),
            "cell_pair_t95_low_pJ_per_element": number(summary, "pair_t95_ci_low_pJ_per_logical_scalar_exponent_result", summary_path),
            "cell_pair_t95_high_pJ_per_element": number(summary, "pair_t95_ci_high_pJ_per_logical_scalar_exponent_result", summary_path),
            "cell_bootstrap_low_pJ_per_element": number(summary, "hierarchical_residual_mbb_ci_low_pJ_per_logical_scalar_exponent_result", summary_path),
            "cell_bootstrap_high_pJ_per_element": number(summary, "hierarchical_residual_mbb_ci_high_pJ_per_logical_scalar_exponent_result", summary_path),
            "matched_positive_blocks": integer(summary, "matched_positive_blocks", summary_path),
            "cell_verdict": summary["verdict"],
            "quality_status": summary["quality_status"],
            "logical_added_results_equals_elements": "true",
            "logical_added_results": denominator,
            "added_ptx_ex2_instructions": ptx_count if ptx_count is not None else "not_applicable",
            "results_per_ptx_instruction": results_per_ptx,
            "temperature_min_C": min(temperatures),
            "temperature_max_C": max(temperatures),
            "temperature_span_C": max(temperatures) - min(temperatures),
            "sm_clock_min_mhz": min(sm_clocks),
            "sm_clock_max_mhz": max(sm_clocks),
            "sm_clock_span_mhz": max(sm_clocks) - min(sm_clocks),
            "trace_fit_r2_min": min(r2_values),
            "trace_fit_points_min": min(fit_points),
            "preheat_actual_s": next(iter(preheats)),
            "mean_treatment_trace_power_W": statistics.fmean(treatment_power),
            "mean_control_trace_power_W": statistics.fmean(control_power),
            "mean_trace_power_delta_W": statistics.fmean(treatment_power) - statistics.fmean(control_power),
            "summary_source": display_path(summary_path),
            "matched_source": display_path(matched_path),
            "raw_source": display_path(raw_path),
            "manifest_source": display_path(manifest_path),
        }
        session_cells.append(session_row)
        diagnostics.append({
            key: session_row[key]
            for key in (
                "session_id", "session_index", "implementation_position", "implementation",
                "incremental_pJ_per_element", "temperature_min_C", "temperature_max_C",
                "temperature_span_C", "sm_clock_min_mhz", "sm_clock_max_mhz",
                "sm_clock_span_mhz", "preheat_actual_s", "trace_fit_r2_min",
                "trace_fit_points_min", "mean_trace_power_delta_W", "cell_verdict", "quality_status",
            )
        })
        for row in matched:
            logical_effect = number(row, "order_balanced_effect_pJ_per_logical_scalar_exponent_result", matched_path)
            operand_value = number(row, "order_balanced_effect_pJ_per_operand", matched_path)
            require_close(logical_effect, operand_value, f"{cell_id}: matched logical/operand equivalence")
            matched_blocks.append(
                {
                    "target_tag": target_tag,
                    "session_id": cell["session_id"],
                    "session_index": integer(cell, "session_index", plan_path),
                    "implementation_position": integer(cell, "implementation_position", plan_path),
                    "implementation": cell["exp_impl"],
                    "matched_block": integer(row, "matched_block", matched_path),
                    "orientation_order": row["chronological_orientation_order"],
                    "forward_incremental_pJ_per_element": number(row, "forward_pJ_per_logical_scalar_exponent_result", matched_path),
                    "reverse_incremental_pJ_per_element": number(row, "reverse_pJ_per_logical_scalar_exponent_result", matched_path),
                    "order_balanced_incremental_pJ_per_element": logical_effect,
                    "middle_position_bias_pJ_per_element": number(row, "middle_position_bias_pJ_per_logical_scalar_exponent_result", matched_path),
                    "incremental_pJ_per_ptx_ex2_instruction": optional_number(row, "order_balanced_effect_pJ_per_ptx_ex2_instruction", matched_path) if cell["exp_impl"] != "fp32" else "not_applicable",
                    "logical_added_results_equals_elements": "true",
                    "logical_added_results": denominator,
                    "added_ptx_ex2_instructions": ptx_count if ptx_count is not None else "not_applicable",
                    "max_temperature_span_C": number(row, "max_temperature_span_C", matched_path),
                    "quality_status": row["quality_status"],
                    "matched_source": display_path(matched_path),
                }
            )
    require_equal(len(binary_hashes), 1, "frozen binary hash consistency")
    require_equal(binary_hashes.pop(), "eeda8c0a1df3628d04c5bf15a486ba3dd0fc43935fbc51a18505a1dffb409b66", "frozen binary hash")

    implementation_summary: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in session_cells:
        grouped[str(row["implementation"])].append(row)
    for impl in EXPECTED_IMPLS:
        values = [float(row["incremental_pJ_per_element"]) for row in grouped[impl]]
        record: dict[str, Any] = {
            "target_tag": target_tag,
            "implementation": impl,
            "canonical_implementation": CANONICAL_IMPL[impl],
            "grid_blocks": TARGET_GRID_BLOCKS,
            "softmax_cols": TARGET_SOFTMAX_COLS,
            "primary_experimental_unit": "fresh_session_mean_of_3_matched_blocks",
            "primary_metric": "incremental_pJ_per_element",
            "confidence_interval_interpretation": "diagnostic_t95_df2_descriptive_not_preregistered_decision_threshold",
            "positive_session_effect_count": sum(value > 0.0 for value in values),
            "positive_cell_verdict_count": sum(row["cell_verdict"] == "positive_identified_pilot" for row in grouped[impl]),
            "all_session_quality_pass": "true",
        }
        record.update(summary_stats(values))
        implementation_summary.append(record)

    contrasts: list[dict[str, Any]] = []
    by_session: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in session_cells:
        by_session[str(row["session_id"])][str(row["implementation"])] = row
    contrast_specs = (
        ("fp32_minus_ptx_f16", "fp32", "ptx_f16"),
        ("fp32_minus_ptx_f16x2", "fp32", "ptx_f16x2"),
        ("ptx_f16x2_minus_ptx_f16", "ptx_f16x2", "ptx_f16"),
    )
    for session_id, rows in sorted(by_session.items()):
        require_equal(set(rows), set(EXPECTED_IMPLS), f"{session_id}: implementation composition")
        for contrast_name, left, right in contrast_specs:
            contrasts.append(
                {
                    "session_id": session_id,
                    "session_index": rows[left]["session_index"],
                    "contrast": contrast_name,
                    "left_implementation": left,
                    "right_implementation": right,
                    "left_position": rows[left]["implementation_position"],
                    "right_position": rows[right]["implementation_position"],
                    "contrast_incremental_pJ_per_element": float(rows[left]["incremental_pJ_per_element"]) - float(rows[right]["incremental_pJ_per_element"]),
                    "interpretation": "within_session_complete_implementation_path_difference_not_pure_opcode_energy",
                }
            )
    contrast_summary: list[dict[str, Any]] = []
    for name, left, right in contrast_specs:
        values = [
            float(row["contrast_incremental_pJ_per_element"])
            for row in contrasts if row["contrast"] == name
        ]
        record = {
            "contrast": name,
            "left_implementation": left,
            "right_implementation": right,
            "interpretation": "within_session_complete_implementation_path_difference_not_pure_opcode_energy",
        }
        record.update(summary_stats(values))
        contrast_summary.append(record)

    validation_rows = [
        parse_validation_log(validation_log_dir / f"validate_{impl}_s1024.log", impl)
        for impl in EXPECTED_IMPLS
    ]
    sass_rows = read_csv(sass_path)
    sass_map = {
        "fp32_fast___expf": "fp32",
        "ptx_ex2_approx_f16": "ptx_f16",
        "ptx_ex2_approx_f16x2": "ptx_f16x2",
    }
    static_rows: list[dict[str, Any]] = []
    for row in sass_rows:
        if row.get("mode") == "full" and row.get("cache_policy") == "default" and row.get("exp_implementation") in sass_map:
            require_equal(row.get("verdict"), "pass", f"SASS audit {row.get('exp_implementation')}")
            static_rows.append(
                {
                    "implementation": sass_map[row["exp_implementation"]],
                    "canonical_implementation": row["exp_implementation"],
                    "ptx_f16_static_count": integer(row, "ptx_ex2_approx_f16_static_count", sass_path),
                    "ptx_f16x2_static_count": integer(row, "ptx_ex2_approx_f16x2_static_count", sass_path),
                    "sass_mufu_ex2_f16_static_count": integer(row, "sass_mufu_ex2_f16_static_count", sass_path),
                    "predicated_probe_mufu_ex2_f16_static_count": integer(row, "sass_predicated_mufu_ex2_f16_static_count", sass_path),
                    "prmt_static_count": integer(row, "sass_prmt_static_count", sass_path),
                    "registers_per_thread": row["resource_registers"],
                    "local_bytes": row["resource_local_bytes"],
                    "spill_local_gate_pass": row["spill_local_gate_pass"],
                    "ptx_opcode_gate_pass": row["ptx_opcode_count_gate_pass"],
                    "sass_opcode_gate_pass": row["sass_opcode_count_gate_pass"],
                    "predicated_probe_gate_pass": row["predicated_probe_count_gate_pass"],
                    "verdict": row["verdict"],
                    "sass_audit_source": display_path(sass_path),
                }
            )
    if {row["implementation"] for row in static_rows} != set(EXPECTED_IMPLS):
        raise ValueError("SASS audit does not contain all three full/default implementations")
    ncu_rows = read_csv(ncu_path)
    dynamic_rows: list[dict[str, Any]] = []
    for row in ncu_rows:
        impl = row.get("exp_impl_cli")
        if impl not in {"ptx_f16", "ptx_f16x2"}:
            continue
        require_equal(row.get("verdict"), "pass", f"NCU audit {impl}")
        require_equal(row.get("observed_xu_delta"), row.get("expected_xu_delta"), f"NCU exact delta {impl}")
        dynamic_rows.append(
            {
                "implementation": impl,
                "canonical_implementation": row["exp_impl"],
                "exp_ptx_instruction": row["exp_ptx_instruction"],
                "results_per_ptx_instruction": integer(row, "exp_results_per_ptx_instruction", ncu_path),
                "grid_blocks": integer(row, "grid_blocks", ncu_path),
                "softmax_cols": integer(row, "softmax_cols", ncu_path),
                "observed_xu_delta": integer(row, "observed_xu_delta", ncu_path),
                "expected_xu_delta": integer(row, "expected_xu_delta", ncu_path),
                "same_kernel_symbol_status": row["same_kernel_symbol_status"],
                "resource_match_status": row["resource_match_status"],
                "logical_traffic_match_status": row["logical_traffic_match_status"],
                "energy_usable": row["energy_usable"],
                "verdict": row["verdict"],
                "ncu_audit_source": display_path(ncu_path),
            }
        )
    if {row["implementation"] for row in dynamic_rows} != {"ptx_f16", "ptx_f16x2"}:
        raise ValueError("NCU audit does not contain the two native implementations")

    historical_rows = historical_context(historical_coordinates_path)
    historical_blocks = historical_scalar_blocks(historical_rows)
    output_paths = {
        "program": out_prefix.with_name(out_prefix.name + "_program.csv"),
        "session_cells": out_prefix.with_name(out_prefix.name + "_session_cells.csv"),
        "matched_blocks": out_prefix.with_name(out_prefix.name + "_matched_blocks.csv"),
        "implementation_summary": out_prefix.with_name(out_prefix.name + "_implementation_summary.csv"),
        "within_session_contrasts": out_prefix.with_name(out_prefix.name + "_within_session_contrasts.csv"),
        "contrast_summary": out_prefix.with_name(out_prefix.name + "_contrast_summary.csv"),
        "diagnostics": out_prefix.with_name(out_prefix.name + "_diagnostics.csv"),
        "numerical_validation": out_prefix.with_name(out_prefix.name + "_numerical_validation.csv"),
        "sass_audit": out_prefix.with_name(out_prefix.name + "_sass_audit.csv"),
        "ncu_audit": out_prefix.with_name(out_prefix.name + "_ncu_audit.csv"),
        "historical_context": out_prefix.with_name(out_prefix.name + "_historical_context.csv"),
        "historical_scalar_blocks": out_prefix.with_name(out_prefix.name + "_historical_scalar_blocks.csv"),
        "analysis_markdown": report_out,
    }
    program = [{
        "analysis_revision": ANALYSIS_REVISION,
        "target_tag": target_tag,
        "coordinate": "CTA=48,S=1024",
        "grid_blocks": TARGET_GRID_BLOCKS,
        "softmax_cols": TARGET_SOFTMAX_COLS,
        "implementations": "fp32|ptx_f16|ptx_f16x2",
        "new_sessions": 3,
        "new_cells": 9,
        "experimental_unit": "fresh_session_mean_of_three_matched_orientation_blocks",
        "primary_metric": "incremental_pJ_per_element",
        "primary_metric_definition": "treatment-control incremental board energy divided by CTA*ITER*S; exactly one added EX2 logical result per input element",
        "denominator_equivalence": "logical_added_exponent_results_equals_processed_elements; not total_softmax_energy_per_element",
        "historical_context_rule": "two prior 60-cell target sessions shown descriptively and excluded from primary new-session aggregate",
        "binary_sha256": "eeda8c0a1df3628d04c5bf15a486ba3dd0fc43935fbc51a18505a1dffb409b66",
        "plan_source": display_path(plan_path),
        "state_source": display_path(state_path),
        "status": "pass",
    }]
    write_csv(output_paths["program"], program)
    write_csv(output_paths["session_cells"], session_cells)
    write_csv(output_paths["matched_blocks"], matched_blocks)
    write_csv(output_paths["implementation_summary"], implementation_summary)
    write_csv(output_paths["within_session_contrasts"], contrasts)
    write_csv(output_paths["contrast_summary"], contrast_summary)
    write_csv(output_paths["diagnostics"], diagnostics)
    write_csv(output_paths["numerical_validation"], validation_rows)
    write_csv(output_paths["sass_audit"], static_rows)
    write_csv(output_paths["ncu_audit"], dynamic_rows)
    write_csv(output_paths["historical_context"], historical_rows)
    write_csv(output_paths["historical_scalar_blocks"], historical_blocks)

    summary_by_impl = {row["implementation"]: row for row in implementation_summary}
    lines = [
        "# CTA=48, S=1024 targeted Softmax EX2 confirmation",
        "",
        "## Result",
        "",
        "The three new cyclic-order sessions all passed raw/trace/manifest verification. "
        "The primary metric is incremental pJ per input element: one extra exponent result is added per element in treatment. "
        "It is not total Softmax pJ per element.",
        "",
        "| implementation | fresh-session mean ΔpJ/element | sample SD | diagnostic t95 (n=3) | positive session effects |",
        "|---|---:|---:|---:|---:|",
    ]
    for impl in EXPECTED_IMPLS:
        row = summary_by_impl[impl]
        lines.append(
            "| `{}` | {:.3f} | {:.3f} | [{:.3f}, {:.3f}] | {}/3 |".format(
                impl,
                float(row["mean_incremental_pJ_per_element"]),
                float(row["sample_sd_incremental_pJ_per_element"]),
                float(row["diagnostic_t95_low_incremental_pJ_per_element"]),
                float(row["diagnostic_t95_high_incremental_pJ_per_element"]),
                row["positive_session_effect_count"],
            )
        )
    lines.extend([
        "",
        "The t intervals are descriptive diagnostics with only three independent sessions, not a preregistered decision rule. "
        "The scalar FP16 target cell moved from historical 10.994 → 1.632 to a three-session mean of "
        f"{float(summary_by_impl['ptx_f16']['mean_incremental_pJ_per_element']):.3f} ΔpJ/element after implementation-position balancing.",
        "",
        "## Interpretation bounds",
        "",
        "- All three paths share FP16 I/O and FP32 max/sum/reduction/normalization. They differ in the exponent/probe path, so comparisons are complete implementation-path contrasts, not isolated functional-unit coefficients.",
        "- `ptx_f16x2` emits packed two-result PTX, but frozen sm_86 SASS lowers it to two scalar `MUFU.EX2.F16` instructions. Its pJ/element value must not be interpreted as half of scalar FP16 or as a physical two-lane-MUFU energy.",
        "- Exact CTA=48/S=1024 native NCU sidecar confirms one added scalar EX2 result per element for both native paths; profiler energy is explicitly excluded from the ATC numerator.",
        "",
        "## Evidence outputs",
        "",
    ])
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{display_path(path)}`")
    write_text(report_out, "\n".join(lines) + "\n")
    return output_paths


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--target-tag", required=True)
    result.add_argument("--plan", type=Path)
    result.add_argument("--state", type=Path)
    result.add_argument("--sass-audit", type=Path, default=Path("results/summary/rtx3090_softmax_targeted_g48s1024_sass_audit_20260725.csv"))
    result.add_argument("--ncu-audit", type=Path, default=Path("results/summary/rtx3090_softmax_targeted_g48s1024_ncu_audit_20260725.csv"))
    result.add_argument("--validation-log-dir", type=Path, default=Path("results/logs/rtx3090_softmax_targeted_g48s1024_20260725"))
    result.add_argument("--historical-coordinates", type=Path, default=Path("results/summary/rtx3090_softmax_ex2_factorial_reproduction_20260724_coordinates.csv"))
    result.add_argument("--out-prefix", type=Path)
    result.add_argument("--report-out", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if re.fullmatch(r"[A-Za-z0-9_]+", args.target_tag) is None:
        raise SystemExit("--target-tag may contain only ASCII letters, digits, and underscores")
    prefix = args.out_prefix or Path(
        f"results/summary/rtx3090_softmax_ex2_targeted_confirmation_{args.target_tag}"
    )
    plan = args.plan or Path(
        f"results/summary/rtx3090_softmax_ex2_targeted_confirmation_{args.target_tag}_plan.csv"
    )
    state = args.state or Path(
        f"results/summary/rtx3090_softmax_ex2_targeted_confirmation_{args.target_tag}_state.csv"
    )
    report_out = args.report_out or Path(
        f"docs/results/rtx3090_softmax_ex2_targeted_confirmation_{args.target_tag}_analysis_ko.md"
    )
    inputs = (plan, state, args.sass_audit, args.ncu_audit, args.validation_log_dir, args.historical_coordinates)
    for source in inputs:
        if not repo_path(source).exists():
            raise SystemExit(f"input does not exist: {source}")
    paths = analyze(
        target_tag=args.target_tag,
        plan_path=repo_path(plan),
        state_path=repo_path(state),
        sass_path=repo_path(args.sass_audit),
        ncu_path=repo_path(args.ncu_audit),
        validation_log_dir=repo_path(args.validation_log_dir),
        historical_coordinates_path=repo_path(args.historical_coordinates),
        out_prefix=repo_path(prefix),
        report_out=repo_path(report_out),
    )
    print("analysis_status=pass")
    for key, path in paths.items():
        print(f"{key}={display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
