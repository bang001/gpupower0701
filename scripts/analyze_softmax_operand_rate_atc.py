#!/usr/bin/env python3
"""Analyze bracketed FP16 Softmax operand-rate ATC pairs.

The primary contrast is an operand-rate projection rather than a same-ITER
completion difference.  For a bracketed control ``C -> Full -> C``:

    E'_r = delta_E_r - median(P_idle,pair) * t_r
    P_C(t_full_mid) = linear interpolation of bracket control active rates
    E_OR(Full <- C) = E'_full - P_C(t_full_mid) * t_full

The ``probe`` control is a same-kernel 0/1/0 additional-exp contrast and uses
one treatment operand per processed element.  When a raw sparse energy trace
is supplied, guarded changed counter points are fit independently by role and
residual moving-block bootstrapped with the same Theil--Sen estimator.  A
triplet interval is diagnostic only; identification is decided from a
direction-balanced aggregate, not by rejecting each noisy triplet.  Signed
values are retained.  A negative value is not a negative physical operation
energy; it means this control did not identify a positive increment.  The
optional thermal-tolerant mode removes *only* the temperature-span hard gate
and labels every resulting positive value exploratory.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CONTROL_SPECS = {
    "io": {
        "roles": ("io_before", "full", "io_after"),
        "before": "io_before",
        "after": "io_after",
        "modes": {
            "io_before": "softmax_io_control_f16io",
            "full": "softmax_full_f16io_f32acc",
            "io_after": "softmax_io_control_f16io",
        },
    },
    "linear": {
        "roles": ("linear_before", "full", "linear_after"),
        "before": "linear_before",
        "after": "linear_after",
        "modes": {
            "linear_before": "softmax_linear_control_f16io_f32acc",
            "full": "softmax_full_f16io_f32acc",
            "linear_after": "softmax_linear_control_f16io_f32acc",
        },
    },
    "probe": {
        "roles": ("probe_before", "full", "probe_after"),
        "before": "probe_before",
        "after": "probe_after",
        "modes": {
            "probe_before": "softmax_full_f16io_f32acc",
            "full": "softmax_full_f16io_f32acc",
            "probe_after": "softmax_full_f16io_f32acc",
        },
        "extra_exp_probe": {
            "probe_before": 0,
            "full": 1,
            "probe_after": 0,
        },
    },
}
PERSISTENT_EXECUTION_MODELS = {
    "persistent_cuda_context_bracket_v1",
    "persistent_cuda_context_bracket_v2",
    "persistent_cuda_context_bracket_v3_counterbalanced6",
}
TRACE_TIMESTAMP_FIELDS = (
    "query_midpoint_s",
    "timestamp_s",
    "steady_timestamp_s",
    "timestamp_steady_s",
)
TRACE_ENERGY_FIELDS = ("energy_mJ", "energy_mj", "total_energy_mj", "energy_counter_mj")
IDENTITY_FIELDS = (
    "gpu_id",
    "profile_name",
    "cuda_pci_bus_id",
    "cuda_binary_arch",
    "softmax_cols",
    "blocks_per_sm",
    "grid_blocks",
    "grid_blocks_source",
    "ITER",
    "cache_condition",
    "cache_policy",
    "row_tiles_per_block",
    "tile_stride",
    "n_elements",
    "exp_input_dtype",
    "special_function_path",
    "xu_documented_results_per_sm_cycle",
    "expected_control_xu_thread_ops_per_cta_iter",
    "expected_treatment_xu_thread_ops_per_cta_iter",
    "expected_probe_xu_thread_ops_per_cta_iter",
    "binary_sha256",
)
DETAIL_FIELDS = (
    "pair_id",
    "repeat",
    "control_mode",
    "gpu_id",
    "profile_name",
    "cuda_pci_bus_id",
    "cuda_binary_arch",
    "cache_condition",
    "cache_policy",
    "softmax_cols",
    "blocks_per_sm",
    "grid_nominal_ctas_per_sm",
    "grid_blocks",
    "grid_blocks_source",
    "grid_experiment_purpose",
    "runtime_sm_count",
    "smid_unique",
    "smid_coverage_fraction",
    "smid_assignment_max_blocks_per_sm",
    "smid_set",
    "smid_histogram",
    "ITER",
    "n_elements",
    "operand_delta_per_element",
    "operand_treatment_count",
    "exp_input_dtype",
    "special_function_path",
    "xu_documented_results_per_sm_cycle",
    "expected_control_xu_thread_ops_per_cta_iter",
    "expected_treatment_xu_thread_ops_per_cta_iter",
    "expected_probe_xu_thread_ops_per_cta_iter",
    "expected_control_xu_warp_instructions_per_cta_iter",
    "expected_treatment_xu_warp_instructions_per_cta_iter",
    "expected_probe_xu_warp_instructions_per_cta_iter",
    "ideal_control_xu_cycles_per_cta_iter",
    "ideal_treatment_xu_cycles_per_cta_iter",
    "ideal_probe_xu_cycles_per_cta_iter",
    "sfu_regime_evidence_status",
    "execution_model",
    "bracket_context_id",
    "idle_baseline_scope",
    "persistent_bracket_status",
    "persistent_batch_context_status",
    "max_inter_role_gap_s",
    "pair_common_idle_power_W",
    "idle_power_spread_fraction",
    "idle_spread_status",
    "pair_temperature_start_C",
    "pair_temperature_end_C",
    "pair_temperature_span_C",
    "thermal_status",
    "full_sm_clock_before_mhz",
    "full_sm_clock_after_mhz",
    "pair_sm_clock_span_fraction",
    "clock_status",
    "control_before_elapsed_s",
    "control_after_elapsed_s",
    "control_elapsed_bracket_mean_s",
    "full_elapsed_s",
    "full_to_control_elapsed_ratio",
    "control_active_power_before_W",
    "control_active_power_after_W",
    "control_active_power_bracket_mean_W",
    "control_active_power_at_full_midpoint_W",
    "control_rate_interpolation_weight",
    "control_rate_estimation",
    "control_active_power_drift_fraction",
    "raw_control_active_power_drift_fraction",
    "full_active_power_W",
    "energy_trace_status",
    "energy_trace_integration_method_status",
    "energy_trace_fit_point_count_status",
    "energy_trace_integration_methods",
    "control_before_energy_trace_status",
    "full_energy_trace_status",
    "control_after_energy_trace_status",
    "control_before_energy_trace_power_W",
    "full_energy_trace_power_W",
    "control_after_energy_trace_power_W",
    "energy_trace_min_sample_count",
    "energy_trace_min_update_count",
    "energy_trace_min_fit_point_count",
    "energy_trace_max_update_interval_p99_s",
    "energy_trace_max_guard_s",
    "energy_trace_min_fit_span_s",
    "energy_trace_min_r2",
    "energy_trace_max_rmse_mJ",
    "energy_trace_max_query_latency_s",
    "energy_trace_input_status",
    "energy_trace_input_control_before_power_W",
    "energy_trace_input_full_power_W",
    "energy_trace_input_control_after_power_W",
    "energy_trace_input_min_fit_points",
    "energy_trace_input_min_fit_updates",
    "energy_trace_input_max_query_latency_s",
    "energy_trace_ATC_delta_E_J",
    "energy_trace_ATC_pJ_per_operand",
    "energy_trace_ATC_ci_low_pJ_per_operand",
    "energy_trace_ATC_ci_high_pJ_per_operand",
    "energy_trace_ATC_ci_excludes_zero",
    "energy_trace_ATC_ci_status",
    "full_net_E_J",
    "control_net_E_bracket_mean_J",
    "same_ITER_completion_delta_E_J",
    "operand_rate_ATC_delta_E_J",
    "ATC_time_correction_J",
    "raw_board_rate_ATC_delta_E_J",
    "raw_board_rate_ATC_pJ_per_element",
    "raw_endpoint_ATC_min_pJ_per_element",
    "raw_endpoint_ATC_max_pJ_per_element",
    "idle_cancellation_residual_J",
    "full_net_pJ_per_element",
    "operand_rate_ATC_pJ_per_element",
    "measurement_status",
    "thermal_tolerant_measurement_status",
    "environment_status",
    "rate_status",
    "raw_rate_status",
    "protocol_status",
    "thermal_tolerant_protocol_status",
    "ramp_conditioned_raw_rate_protocol_status",
    "sass_status",
    "ncu_status",
    "verdict",
    "reasons",
)
SUMMARY_FIELDS = (
    "control_mode",
    "cache_condition",
    "cache_policy",
    "softmax_cols",
    "blocks_per_sm",
    "grid_blocks",
    "grid_blocks_source",
    "summary_estimator",
    "summary_unit",
    "total_pairs",
    "strict_protocol_valid_pairs",
    "thermal_tolerant_protocol_valid_pairs",
    "ramp_conditioned_raw_rate_valid_pairs",
    "strict_positive_atc_pairs",
    "thermal_tolerant_positive_atc_pairs",
    "ramp_conditioned_raw_rate_positive_atc_pairs",
    "exploratory_signed_min_pJ_per_element",
    "exploratory_signed_median_pJ_per_element",
    "exploratory_signed_mean_pJ_per_element",
    "exploratory_signed_max_pJ_per_element",
    "exploratory_signed_iqr_pJ_per_element",
    "strict_protocol_signed_median_pJ_per_element",
    "thermal_tolerant_signed_median_pJ_per_element",
    "ramp_conditioned_raw_rate_signed_median_pJ_per_element",
    "thermal_tolerant_bootstrap_median_ci_low_pJ_per_element",
    "thermal_tolerant_bootstrap_median_ci_high_pJ_per_element",
    "median_full_to_control_elapsed_ratio",
    "median_control_rate_drift_fraction",
    "median_raw_control_rate_drift_fraction",
    "median_pair_sm_clock_span_fraction",
    "persistent_bracket_valid_pairs",
    "verdict",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, fields: Iterable[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in writer.fieldnames} for row in rows)


def num(row: dict[str, Any], field: str) -> float:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError):
        return math.nan
    return value if math.isfinite(value) else math.nan


def integer(row: dict[str, Any], field: str) -> int | None:
    try:
        value = int(str(row.get(field, "")))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "pass"}


def binary_value(value: str) -> int | None:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return 1
    if normalized in {"0", "false", "no"}:
        return 0
    return None


def relative_spread(values: Iterable[float]) -> float:
    values = list(values)
    if not values or any(not math.isfinite(value) for value in values):
        return math.inf
    center = statistics.median(values)
    if center <= 0.0:
        return math.inf
    return (max(values) - min(values)) / center


def safe_div(numerator: float, denominator: float) -> float:
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator == 0.0:
        return math.nan
    return numerator / denominator


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    location = (len(ordered) - 1) * fraction
    lower = int(math.floor(location))
    upper = int(math.ceil(location))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (location - lower)


def bootstrap_median_ci(values: list[float], seed: int = 20260722) -> tuple[float, float]:
    if len(values) < 2:
        return math.nan, math.nan
    generator = random.Random(seed)
    samples = [
        statistics.median([generator.choice(values) for _ in values])
        for _ in range(10_000)
    ]
    return percentile(samples, 0.025), percentile(samples, 0.975)


def first_num(row: dict[str, Any], fields: Iterable[str]) -> float:
    for field in fields:
        value = num(row, field)
        if math.isfinite(value):
            return value
    return math.nan


def is_robust_trace_integration_method(value: str) -> bool:
    """Accept named guarded update-event slope estimators, not endpoint deltas."""
    normalized = value.strip().lower().replace("-", "_")
    guarded = "guard" in normalized
    interior = "interior" in normalized
    trace_or_events = "trace" in normalized or (
        "update" in normalized and "event" in normalized
    )
    robust_slope = any(token in normalized for token in ("theil", "robust", "slope"))
    return (guarded and trace_or_events and robust_slope) or (
        interior and "theil" in normalized
    )


def read_energy_trace(path: Path | None) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    if path is None:
        return output
    for row in read_csv(path):
        pair_id = row.get("pair_id", "")
        role = row.get("role", "")
        if pair_id and role:
            output[(pair_id, role)].append(row)
    return output


def trace_kernel_midpoint_s(rows: list[dict[str, str]], elapsed_s: float) -> float:
    """Recover a kernel midpoint on the steady-clock trace timebase.

    WSL wall clock can step while a batch is running, so
    ``measurement_*_epoch_ms`` is provenance only when raw trace timestamps
    are available.  Every trace row records both an absolute steady query
    midpoint and its offset from the kernel start; their difference recovers
    the common steady kernel start.
    """
    starts: list[float] = []
    for row in rows:
        query_midpoint = first_num(row, TRACE_TIMESTAMP_FIELDS)
        relative = num(row, "relative_to_kernel_start_s")
        if math.isfinite(query_midpoint) and math.isfinite(relative):
            starts.append(query_midpoint - relative)
    if not starts or not math.isfinite(elapsed_s) or elapsed_s <= 0.0:
        return math.nan
    return statistics.median(starts) + elapsed_s / 2.0


def theil_sen_slope_w(points: list[tuple[float, float]]) -> float:
    slopes: list[float] = []
    for left in range(len(points)):
        for right in range(left + 1, len(points)):
            dt = points[right][0] - points[left][0]
            if dt > 0.0:
                slopes.append((points[right][1] - points[left][1]) / dt / 1000.0)
    return statistics.median(slopes) if slopes else math.nan


def trace_fit_r2(points: list[tuple[float, float]], slope_w: float) -> float:
    if len(points) < 2 or not math.isfinite(slope_w):
        return math.nan
    origin = points[0][0]
    slope_mj_s = slope_w * 1000.0
    intercept = statistics.median(
        energy_mj - slope_mj_s * (timestamp_s - origin)
        for timestamp_s, energy_mj in points
    )
    mean_energy = statistics.fmean(energy_mj for _, energy_mj in points)
    residual = sum(
        (energy_mj - (intercept + slope_mj_s * (timestamp_s - origin))) ** 2
        for timestamp_s, energy_mj in points
    )
    total = sum((energy_mj - mean_energy) ** 2 for _, energy_mj in points)
    return 1.0 - residual / total if total > 0.0 else math.nan


def block_bootstrap_trace_slopes(
    points: list[tuple[float, float]], samples: int, requested_block: int, seed: int
) -> list[float]:
    """Residual moving-block bootstrap of the exact Theil--Sen estimator.

    Earlier revisions resampled update increments and returned a ratio of
    sums.  That bootstrap statistic was not the Theil--Sen point estimator and
    could therefore produce an interval centered hundreds of pJ away from the
    reported estimate.  Here timestamps and the fitted cumulative-energy
    trajectory stay fixed, correlated residual blocks are resampled, and the
    Theil--Sen slope is recomputed for every draw.
    """
    count = len(points)
    point_slope_w = theil_sen_slope_w(points)
    if count < 3 or samples <= 0 or not math.isfinite(point_slope_w):
        return []
    block = requested_block if requested_block > 0 else max(2, int(round(math.sqrt(count))))
    block = min(block, count)
    origin = points[0][0]
    slope_mj_s = point_slope_w * 1000.0
    intercept = statistics.median(
        energy_mj - slope_mj_s * (timestamp_s - origin)
        for timestamp_s, energy_mj in points
    )
    fitted = [
        intercept + slope_mj_s * (timestamp_s - origin)
        for timestamp_s, _ in points
    ]
    residuals = [
        energy_mj - fit for (_, energy_mj), fit in zip(points, fitted)
    ]
    generator = random.Random(seed)
    output: list[float] = []
    for _ in range(samples):
        selected: list[float] = []
        while len(selected) < count:
            start = generator.randrange(count)
            selected.extend(
                residuals[(start + offset) % count] for offset in range(block)
            )
        selected = selected[:count]
        bootstrap_points = [
            (points[index][0], fitted[index] + selected[index])
            for index in range(count)
        ]
        output.append(theil_sen_slope_w(bootstrap_points))
    return output


def analyze_trace_role(
    rows: list[dict[str, str]], args: argparse.Namespace, seed: int
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "missing",
        "reason": "energy_trace_role_missing",
        "power_W": math.nan,
        "fit_updates": 0,
        "fit_points": 0,
        "fit_span_s": math.nan,
        "r2": math.nan,
        "max_query_latency_s": math.nan,
        "bootstrap_power_W": [],
    }
    if not rows:
        return result

    parsed: list[tuple[float, float, dict[str, str]]] = []
    for row in rows:
        timestamp = first_num(row, TRACE_TIMESTAMP_FIELDS)
        energy_mj = first_num(row, TRACE_ENERGY_FIELDS)
        if not math.isfinite(timestamp) or not math.isfinite(energy_mj):
            result.update(status="fail", reason="energy_trace_point_invalid")
            return result
        parsed.append((timestamp, energy_mj, row))
    parsed.sort(key=lambda item: item[0])
    if any(parsed[index][1] < parsed[index - 1][1] for index in range(1, len(parsed))):
        result.update(status="fail", reason="energy_trace_counter_nonmonotonic")
        return result

    has_fit_flags = any(row.get("in_fit_window", "") != "" for _, _, row in parsed)
    selected = [
        (timestamp, energy_mj, row)
        for timestamp, energy_mj, row in parsed
        if not has_fit_flags or truthy(row.get("in_fit_window", ""))
    ]
    changes: list[tuple[float, float]] = []
    for timestamp, energy_mj, _ in selected:
        if not changes or energy_mj > changes[-1][1]:
            changes.append((timestamp, energy_mj))
    fit_points = len(changes)
    fit_updates = max(0, fit_points - 1)
    result["fit_points"] = fit_points
    result["fit_updates"] = fit_updates
    if fit_points < args.energy_trace_min_fit_points:
        result.update(status="fail", reason="energy_trace_guarded_fit_points_below_gate")
        return result

    fit_span = changes[-1][0] - changes[0][0]
    slope_w = theil_sen_slope_w(changes)
    query_latencies = [
        num(row, "query_latency_s") for _, _, row in parsed
        if math.isfinite(num(row, "query_latency_s"))
    ]
    bootstrap = block_bootstrap_trace_slopes(
        changes,
        args.energy_trace_bootstrap_samples,
        args.energy_trace_block_updates,
        seed,
    )
    result.update(
        power_W=slope_w,
        fit_span_s=fit_span,
        r2=trace_fit_r2(changes, slope_w),
        max_query_latency_s=max(query_latencies) if query_latencies else math.nan,
        bootstrap_power_W=bootstrap,
    )
    if not math.isfinite(slope_w) or slope_w <= 0.0:
        result.update(status="fail", reason="energy_trace_slope_invalid")
    elif len(bootstrap) != args.energy_trace_bootstrap_samples:
        result.update(status="fail", reason="energy_trace_bootstrap_incomplete")
    else:
        result.update(status="pass", reason="")
    return result


def summarize_row_trace_quality(
    by_role: dict[str, dict[str, str]], roles: tuple[str, ...], args: argparse.Namespace
) -> tuple[dict[str, Any], list[str]]:
    rows = [by_role.get(role, {}) for role in roles]
    statuses = [row.get("energy_trace_status", "") for row in rows]
    methods = [row.get("energy_integration_method", "") for row in rows]
    role_statuses_pass = all(status == "pass" for status in statuses)
    fit_point_counts = [integer(row, "energy_trace_fit_point_count") for row in rows]
    fit_points_pass = all(
        count is not None and count >= args.energy_trace_min_fit_points
        for count in fit_point_counts
    )
    all_pass = role_statuses_pass and fit_points_pass
    methods_pass = all(is_robust_trace_integration_method(method) for method in methods)
    if all_pass:
        pair_status = "pass"
    elif all(not status for status in statuses):
        pair_status = "not_recorded"
    else:
        pair_status = "fail"
    if methods_pass:
        method_status = "pass"
    elif all(not method for method in methods):
        method_status = "not_recorded"
    else:
        method_status = "fail"

    def finite_values(field: str) -> list[float]:
        return [value for row in rows if math.isfinite(value := num(row, field))]

    def aggregate(field: str, operation: str) -> float:
        values = finite_values(field)
        if not values:
            return math.nan
        return min(values) if operation == "min" else max(values)

    quality = {
        "energy_trace_status": pair_status,
        "energy_trace_integration_method_status": method_status,
        "energy_trace_fit_point_count_status": "pass" if fit_points_pass else "fail",
        "energy_trace_integration_methods": ";".join(sorted(set(methods) - {""})),
        "control_before_energy_trace_status": statuses[0],
        "full_energy_trace_status": statuses[1],
        "control_after_energy_trace_status": statuses[2],
        "control_before_energy_trace_power_W": num(rows[0], "energy_trace_power_W"),
        "full_energy_trace_power_W": num(rows[1], "energy_trace_power_W"),
        "control_after_energy_trace_power_W": num(rows[2], "energy_trace_power_W"),
        "energy_trace_min_sample_count": aggregate("energy_trace_sample_count", "min"),
        "energy_trace_min_update_count": aggregate("energy_trace_update_count", "min"),
        "energy_trace_min_fit_point_count": aggregate("energy_trace_fit_point_count", "min"),
        "energy_trace_max_update_interval_p99_s": aggregate(
            "energy_trace_update_interval_p99_s", "max"
        ),
        "energy_trace_max_guard_s": aggregate("energy_trace_guard_s", "max"),
        "energy_trace_min_fit_span_s": aggregate("energy_trace_fit_span_s", "min"),
        "energy_trace_min_r2": aggregate("energy_trace_r2", "min"),
        "energy_trace_max_rmse_mJ": aggregate("energy_trace_rmse_mJ", "max"),
        "energy_trace_max_query_latency_s": aggregate(
            "energy_trace_max_query_latency_s", "max"
        ),
    }
    reasons: list[str] = []
    if args.require_energy_trace:
        if not role_statuses_pass:
            reasons.append("energy_trace_role_status_not_pass")
        if not fit_points_pass:
            reasons.append("energy_trace_fit_points_below_gate")
        if not methods_pass:
            reasons.append("energy_trace_integration_method_not_robust")
    return quality, reasons


def analyze_pair_trace_input(
    pair_id: str,
    roles: tuple[str, ...],
    trace_rows: dict[tuple[str, str], list[dict[str, str]]],
    interpolation_weight: float,
    full_elapsed_s: float,
    operand_treatment_count: float,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    output: dict[str, Any] = {
        "energy_trace_input_status": "not_run",
        "energy_trace_input_control_before_power_W": math.nan,
        "energy_trace_input_full_power_W": math.nan,
        "energy_trace_input_control_after_power_W": math.nan,
        "energy_trace_input_min_fit_points": math.nan,
        "energy_trace_input_min_fit_updates": math.nan,
        "energy_trace_input_max_query_latency_s": math.nan,
        "energy_trace_ATC_delta_E_J": math.nan,
        "energy_trace_ATC_pJ_per_operand": math.nan,
        "energy_trace_ATC_ci_low_pJ_per_operand": math.nan,
        "energy_trace_ATC_ci_high_pJ_per_operand": math.nan,
        "energy_trace_ATC_ci_excludes_zero": "not_run",
        "energy_trace_ATC_ci_status": "not_run",
    }
    if args.energy_trace_input is None:
        return output, []

    analyses = [
        analyze_trace_role(
            trace_rows.get((pair_id, role), []),
            args,
            20260722 + role_index * 1009 + sum(ord(character) for character in pair_id),
        )
        for role_index, role in enumerate(roles)
    ]
    output.update(
        energy_trace_input_control_before_power_W=analyses[0]["power_W"],
        energy_trace_input_full_power_W=analyses[1]["power_W"],
        energy_trace_input_control_after_power_W=analyses[2]["power_W"],
        energy_trace_input_min_fit_points=min(
            int(analysis["fit_points"]) for analysis in analyses
        ),
        energy_trace_input_min_fit_updates=min(
            int(analysis["fit_updates"]) for analysis in analyses
        ),
    )
    latencies = [
        float(analysis["max_query_latency_s"])
        for analysis in analyses
        if math.isfinite(float(analysis["max_query_latency_s"]))
    ]
    output["energy_trace_input_max_query_latency_s"] = (
        max(latencies) if latencies else math.nan
    )
    failed = [analysis["reason"] for analysis in analyses if analysis["status"] != "pass"]
    if failed:
        output["energy_trace_input_status"] = "fail"
        return output, [f"energy_trace_input_{reason}" for reason in dict.fromkeys(failed)]
    if not (0.0 <= interpolation_weight <= 1.0):
        output["energy_trace_input_status"] = "fail"
        return output, ["energy_trace_input_interpolation_weight_invalid"]
    if not math.isfinite(operand_treatment_count) or operand_treatment_count <= 0.0:
        output["energy_trace_input_status"] = "fail"
        return output, ["energy_trace_input_operand_denominator_invalid"]

    before_power = float(analyses[0]["power_W"])
    full_power = float(analyses[1]["power_W"])
    after_power = float(analyses[2]["power_W"])
    control_power = before_power + interpolation_weight * (after_power - before_power)
    atc_delta_j = (full_power - control_power) * full_elapsed_s
    atc_pj = atc_delta_j * 1.0e12 / operand_treatment_count
    bootstrap_count = min(len(analysis["bootstrap_power_W"]) for analysis in analyses)
    samples: list[float] = []
    for index in range(bootstrap_count):
        before = analyses[0]["bootstrap_power_W"][index]
        full = analyses[1]["bootstrap_power_W"][index]
        after = analyses[2]["bootstrap_power_W"][index]
        control = before + interpolation_weight * (after - before)
        samples.append((full - control) * full_elapsed_s * 1.0e12 /
                       operand_treatment_count)
    ci_low = percentile(samples, 0.025)
    ci_high = percentile(samples, 0.975)
    if ci_low > 0.0:
        excludes_zero = "positive"
    elif ci_high < 0.0:
        excludes_zero = "negative"
    else:
        excludes_zero = "no"
    ci_status = (
        "diagnostic_excludes_zero"
        if excludes_zero != "no"
        else "diagnostic_includes_zero"
    )
    output.update(
        energy_trace_input_status="pass",
        energy_trace_ATC_delta_E_J=atc_delta_j,
        energy_trace_ATC_pJ_per_operand=atc_pj,
        energy_trace_ATC_ci_low_pJ_per_operand=ci_low,
        energy_trace_ATC_ci_high_pJ_per_operand=ci_high,
        energy_trace_ATC_ci_excludes_zero=excludes_zero,
        energy_trace_ATC_ci_status=ci_status,
    )
    return output, []


def manifest_status(path: Path | None) -> dict[tuple[str, str], str]:
    if path is None:
        return {}
    output: dict[tuple[str, str], str] = {}
    for row in read_csv(path):
        output[(row.get("pair_id", ""), row.get("role", ""))] = row.get(
            "quiescence_status", "missing"
        )
    return output


def sass_statuses(path: Path | None) -> dict[tuple[str, str], str]:
    """Return static SASS status keyed by (binary SHA, cache policy)."""
    if path is None:
        return {}
    rows = read_csv(path)
    output: dict[tuple[str, str], str] = {}
    keys = {(row.get("binary_sha256", ""), row.get("cache_policy", "")) for row in rows}
    required = {"full", "linear_control", "io_control"}
    for key in keys:
        binary_sha, cache_policy = key
        if not binary_sha or cache_policy not in {"default", "cg"}:
            continue
        selected = [
            row for row in rows
            if row.get("binary_sha256") == binary_sha
            and row.get("cache_policy") == cache_policy
        ]
        by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in selected:
            by_mode[row.get("mode", "")].append(row)
        output[key] = (
            "pass"
            if set(by_mode) == required
            and all(entries and all(row.get("verdict") == "pass" for row in entries)
                    for entries in by_mode.values())
            else "fail"
        )
    return output


def ncu_statuses(path: Path | None) -> dict[tuple[str, str, str, str, str, str], str]:
    """Return matching v3 dynamic-path status keyed by the energy coordinates."""
    if path is None:
        return {}
    rows = read_csv(path)
    output: dict[tuple[str, str, str, str, str, str], str] = {}
    keys = {
        (
            row.get("binary_sha256", ""),
            row.get("cache_condition", ""),
            row.get("cache_policy", ""),
            row.get("softmax_cols", ""),
            row.get("blocks_per_sm", ""),
            row.get("grid_blocks", ""),
        )
        for row in rows
    }
    for key in keys:
        selected = [
            row for row in rows
            if (
                row.get("binary_sha256", ""),
                row.get("cache_condition", ""),
                row.get("cache_policy", ""),
                row.get("softmax_cols", ""),
                row.get("blocks_per_sm", ""),
                row.get("grid_blocks", ""),
            ) == key
        ]
        by_mode = {row.get("mode", ""): row for row in selected}
        required = {"full", "linear_control"}
        output[key] = (
            "scoped_path_pass"
            if set(by_mode) == required
            and all(
                row.get("verdict") == "pass"
                and row.get("energy_usable") == "false"
                and row.get("common_global_ld_st_status") == "pass"
                for row in by_mode.values()
            )
            else "scoped_path_fail"
        )
    return output


def expected_n_elements(row: dict[str, str]) -> int | None:
    grid_blocks = integer(row, "grid_blocks")
    iters = integer(row, "ITER")
    cols = integer(row, "softmax_cols")
    if grid_blocks is None or iters is None or cols is None:
        return None
    return grid_blocks * iters * cols


def detect_control_spec(by_role: dict[str, dict[str, str]], requested: str) -> tuple[str, dict[str, Any]]:
    if requested != "auto":
        return requested, CONTROL_SPECS[requested]
    role_set = set(by_role)
    for name, spec in CONTROL_SPECS.items():
        if role_set == set(spec["roles"]):
            return name, spec
    return "unknown", CONTROL_SPECS["io"]


def midpoint_epoch_ms(row: dict[str, str]) -> float:
    start = num(row, "measurement_start_epoch_ms")
    end = num(row, "measurement_end_epoch_ms")
    if not math.isfinite(start) or not math.isfinite(end) or end < start:
        return math.nan
    return (start + end) / 2.0


def placement_reasons(rows: list[dict[str, str]]) -> list[str]:
    """Validate launch placement without claiming CUDA SM affinity/residency."""
    has_v2 = all("smid_all_blocks_observed" in row for row in rows)
    if has_v2:
        reasons: list[str] = []
        if any(not truthy(row.get("smid_all_blocks_observed", "")) for row in rows):
            reasons.append("smid_all_blocks_not_observed")
        if any(not truthy(row.get("static_single_wave_capacity_gate_pass", "")) for row in rows):
            reasons.append("static_single_wave_capacity_gate_failed")
        if any(not truthy(row.get("occupancy_gate_pass", "")) for row in rows):
            reasons.append("occupancy_gate_failed")
        has_smid_sets = all("smid_set" in row for row in rows)
        if has_smid_sets:
            smid_sets = {row.get("smid_set", "") for row in rows}
            if "" in smid_sets or "not_checked" in smid_sets:
                reasons.append("smid_set_missing")
            elif len(smid_sets) != 1:
                reasons.append("smid_set_mismatch_within_pair")
        if any(row.get("profile_name") == "a100" for row in rows):
            for row in rows:
                grid = integer(row, "grid_blocks")
                runtime_sms = integer(row, "runtime_sm_count")
                unique_sms = integer(row, "smid_unique")
                max_blocks = integer(row, "smid_assignment_max_blocks_per_sm")
                if grid is None or runtime_sms is None or unique_sms is None:
                    reasons.append("a100_smid_cardinality_missing")
                    break
                if grid <= runtime_sms and (
                    unique_sms != grid or max_blocks != 1
                ):
                    reasons.append("a100_underfill_not_one_distinct_cta_per_smid")
                    break
        return reasons
    reasons = []
    if any(not truthy(row.get("occupancy_gate_pass", "")) for row in rows):
        reasons.append("legacy_occupancy_gate_failed")
    if any(not truthy(row.get("smid_histogram_ok", "")) for row in rows):
        reasons.append("legacy_smid_histogram_failed")
    return reasons


def persistent_pair_metadata(
    rows: list[dict[str, str]], args: argparse.Namespace
) -> tuple[str, str, str, str, float, list[str]]:
    """Validate the context and no-cooling evidence recorded by persistent brackets.

    Legacy rows deliberately remain analyzable, but a caller can require this
    stronger v3 provenance for a new persistent batch.
    """
    has_metadata = all(
        field in row
        for row in rows
        for field in (
            "execution_model", "bracket_context_id", "idle_baseline_scope",
            "preceding_role_gap_s",
        )
    )
    if not has_metadata:
        reasons = ["persistent_bracket_metadata_missing"] if args.require_persistent_bracket else []
        return "legacy_not_recorded", "", "", "", math.nan, reasons
    execution_models = {row.get("execution_model", "") for row in rows}
    context_ids = {row.get("bracket_context_id", "") for row in rows}
    idle_scopes = {row.get("idle_baseline_scope", "") for row in rows}
    gaps = [
        num(row, "preceding_role_gap_s")
        for row in rows
        if integer(row, "sequence_index") not in (None, 0)
    ]
    max_gap = max(gaps) if gaps and all(math.isfinite(value) for value in gaps) else math.nan
    reasons: list[str] = []
    if (len(execution_models) != 1 or
            not all(model in PERSISTENT_EXECUTION_MODELS or
                    model.startswith("persistent_cuda_context_bracket_v2_")
                    for model in execution_models)):
        reasons.append("persistent_execution_model_mismatch")
    if len(context_ids) != 1 or not next(iter(context_ids), ""):
        reasons.append("persistent_context_id_mismatch")
    if (len(idle_scopes) != 1 or
            next(iter(idle_scopes), "") not in {"pair_once", "batch_once", "per_role"}):
        reasons.append("persistent_idle_scope_mismatch")
    if not math.isfinite(max_gap):
        reasons.append("persistent_inter_role_gap_missing")
    elif max_gap > args.max_persistent_inter_role_gap_s:
        reasons.append("persistent_inter_role_gap_too_high")
    status = "pass" if not reasons else "fail"
    if not args.require_persistent_bracket and status == "fail":
        # Metadata is an audit enrichment for legacy-compatible analysis unless
        # the caller explicitly requests a persistent bracket.
        return "metadata_invalid_not_required", next(iter(execution_models), ""), \
            next(iter(context_ids), ""), next(iter(idle_scopes), ""), max_gap, []
    return status, next(iter(execution_models), ""), next(iter(context_ids), ""), \
        next(iter(idle_scopes), ""), max_gap, reasons


def persistent_batch_context_status(
    rows: list[dict[str, str]], args: argparse.Namespace
) -> tuple[str, list[str]]:
    """Confirm each independently launched coordinate retained one context.

    A bounded grid sweep intentionally starts one persistent process per
    coordinate, so different grids have different context IDs.  Requiring a
    single ID for the entire input would incorrectly reject a valid sweep.
    """
    has_metadata = all(
        "execution_model" in row and "bracket_context_id" in row for row in rows
    )
    if not has_metadata:
        return (
            "legacy_not_recorded",
            ["persistent_batch_metadata_missing"] if args.require_persistent_bracket else [],
        )
    execution_models = {row.get("execution_model", "") for row in rows}
    contexts_by_coordinate: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in rows:
        coordinate = tuple(row.get(field, "") for field in IDENTITY_FIELDS)
        contexts_by_coordinate[coordinate].add(row.get("bracket_context_id", ""))
    reasons: list[str] = []
    if (len(execution_models) != 1 or
            not all(model in PERSISTENT_EXECUTION_MODELS or
                    model.startswith("persistent_cuda_context_bracket_v2_")
                    for model in execution_models)):
        reasons.append("persistent_batch_execution_model_mismatch")
    if not contexts_by_coordinate or any(
        len(context_ids) != 1 or not next(iter(context_ids), "")
        for context_ids in contexts_by_coordinate.values()
    ):
        reasons.append("persistent_batch_context_id_mismatch")
    status = "pass" if not reasons else "fail"
    return (status, reasons if args.require_persistent_bracket else [])


def analyze_pair(
    rows: list[dict[str, str]],
    manifest: dict[tuple[str, str], str],
    static_sass: dict[tuple[str, str], str],
    dynamic_ncu: dict[tuple[str, str, str, str, str, str], str],
    trace_rows: dict[tuple[str, str], list[dict[str, str]]],
    persistent_batch_status: str,
    persistent_batch_reasons: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    template = rows[0]
    pair_id = template.get("pair_id", "")
    by_role = {row.get("role", ""): row for row in rows}
    control_mode, spec = detect_control_spec(by_role, args.control_mode)
    roles = spec["roles"]
    before_role = spec["before"]
    after_role = spec["after"]
    reasons: list[str] = []

    if len(rows) != 3 or set(by_role) != set(roles):
        reasons.append("missing_or_duplicate_triplet_role")
    for sequence_index, role in enumerate(roles):
        row = by_role.get(role, {})
        if row.get("mode") != spec["modes"][role]:
            reasons.append(f"{role}_mode_mismatch")
        if integer(row, "sequence_index") != sequence_index:
            reasons.append(f"{role}_sequence_mismatch")
    if control_mode == "probe":
        for role in roles:
            expected_probe = spec["extra_exp_probe"][role]
            observed_probe = binary_value(
                by_role.get(role, {}).get("extra_exp_probe", "")
            )
            if observed_probe != expected_probe:
                reasons.append(f"{role}_extra_exp_probe_mismatch")
        treatment_operand_delta = num(by_role.get("full", {}), "operand_delta_per_element")
        if not math.isfinite(treatment_operand_delta) or treatment_operand_delta != 1.0:
            reasons.append("probe_operand_delta_per_element_mismatch")
        for role in (before_role, after_role):
            row = by_role.get(role, {})
            if row.get("operand_delta_per_element", ""):
                control_delta = num(row, "operand_delta_per_element")
                if not math.isfinite(control_delta) or control_delta != 0.0:
                    reasons.append(f"{role}_operand_delta_per_element_mismatch")
    else:
        treatment_operand_delta = 1.0
    for field in IDENTITY_FIELDS:
        if len({row.get(field, "") for row in rows}) != 1:
            reasons.append(f"identity_mismatch_{field}")
    for row in rows:
        expected = expected_n_elements(row)
        if expected is None or integer(row, "n_elements") != expected:
            reasons.append("n_elements_formula_mismatch")
            break
    if any(row.get("energy_source") != "nvml_total_energy" for row in rows):
        reasons.append("non_total_energy_source")
    if any(row.get("measurement_scope") != "gpu_device_total_energy_counter" for row in rows):
        reasons.append("measurement_scope_mismatch")
    if any(not truthy(row.get("nvml_total_energy_supported", "")) for row in rows):
        reasons.append("nvml_total_energy_not_supported")
    reasons.extend(placement_reasons(rows))
    if args.require_sfu_regime_evidence and any(
        row.get("sfu_regime_evidence_status") != "pass" for row in rows
    ):
        reasons.append("sfu_regime_evidence_not_pass")
    (
        persistent_status,
        execution_model,
        context_id,
        idle_scope,
        max_inter_role_gap,
        persistent_reasons,
    ) = persistent_pair_metadata(rows, args)
    reasons.extend(persistent_reasons)
    reasons.extend(persistent_batch_reasons)
    if any(row.get("numerical_check_id") != args.numerical_check_id for row in rows):
        reasons.append("numerical_check_not_matched")

    if template.get("cache_condition") == "streaming_large_ws":
        for row in rows:
            working_set = integer(row, "working_set_bytes")
            l2 = integer(row, "runtime_l2_bytes")
            if working_set is None or l2 is None or working_set < 4 * l2:
                reasons.append("streaming_working_set_below_4x_l2")
                break

    idle_powers = [num(row, "idle_power_W") for row in rows]
    idle_common = statistics.median(idle_powers) if all(math.isfinite(v) for v in idle_powers) else math.nan
    idle_spread = relative_spread(idle_powers)
    if idle_scope in {"pair_once", "batch_once"}:
        # This baseline is intentionally shared by all three roles; its zero
        # spread is not independent evidence of an idle-stability condition.
        if idle_spread > 1.0e-9:
            reasons.append("shared_pair_idle_baseline_mismatch")
        idle_spread_status = (
            "shared_pair_once_not_independent"
            if idle_scope == "pair_once"
            else "shared_batch_once_not_independent"
        )
    else:
        if idle_spread > args.max_idle_spread_fraction:
            reasons.append("pair_idle_power_spread_too_high")
        idle_spread_status = "pass" if idle_spread <= args.max_idle_spread_fraction else "fail"

    temperatures = [
        num(row, field)
        for row in rows
        for field in ("temp_before_C", "temp_after_C")
    ]
    temperature_span = max(temperatures) - min(temperatures) if all(
        math.isfinite(value) for value in temperatures
    ) else math.nan
    temperature_start = num(by_role.get(before_role, {}), "temp_before_C")
    temperature_end = num(by_role.get(after_role, {}), "temp_after_C")
    if not math.isfinite(temperature_span):
        reasons.append("temperature_metadata_missing")
        thermal_status = "missing"
    elif temperature_span > args.max_pair_temperature_span_c:
        reasons.append("pair_temperature_span_too_high")
        thermal_status = "ramp_conditioned"
    else:
        thermal_status = "within_gate"

    clock_values = [
        num(row, field)
        for row in rows
        for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
    ]
    clock_span = relative_spread(clock_values)
    if not math.isfinite(clock_span):
        reasons.append("clock_metadata_missing")
        clock_status = "missing"
    elif clock_span > args.max_pair_sm_clock_span_fraction:
        reasons.append("pair_sm_clock_span_too_high")
        clock_status = "ramp_conditioned"
    else:
        clock_status = "within_gate"

    trace_quality, trace_quality_reasons = summarize_row_trace_quality(by_role, roles, args)
    reasons.extend(trace_quality_reasons)

    elapsed = {role: num(by_role.get(role, {}), "elapsed_s") for role in roles}
    delta = {role: num(by_role.get(role, {}), "delta_E_J") for role in roles}
    if any(not math.isfinite(value) or value <= 0.0 for value in elapsed.values()):
        reasons.append("invalid_elapsed")
    if any(not math.isfinite(value) or value < 0.0 for value in delta.values()):
        reasons.append("invalid_delta_energy")
    net = {role: delta[role] - idle_common * elapsed[role] for role in roles}

    control_elapsed_mean = statistics.fmean((elapsed[before_role], elapsed[after_role]))
    control_net_mean = statistics.fmean((net[before_role], net[after_role]))
    control_power_before = safe_div(net[before_role], elapsed[before_role])
    control_power_after = safe_div(net[after_role], elapsed[after_role])
    control_power_mean = statistics.fmean((control_power_before, control_power_after))
    raw_control_power_before = safe_div(delta[before_role], elapsed[before_role])
    raw_control_power_after = safe_div(delta[after_role], elapsed[after_role])
    raw_control_power_mean = statistics.fmean((raw_control_power_before, raw_control_power_after))
    control_power_drift = relative_spread((control_power_before, control_power_after))
    raw_control_power_drift = relative_spread(
        (raw_control_power_before, raw_control_power_after)
    )
    full_power = safe_div(net["full"], elapsed["full"])
    elapsed_ratio = safe_div(elapsed["full"], control_elapsed_mean)

    before_mid = midpoint_epoch_ms(by_role.get(before_role, {}))
    full_mid = midpoint_epoch_ms(by_role.get("full", {}))
    after_mid = midpoint_epoch_ms(by_role.get(after_role, {}))
    midpoint_timebase = "wall_clock_epoch_ms"
    if args.energy_trace_input is not None:
        steady_midpoints = (
            trace_kernel_midpoint_s(
                trace_rows.get((pair_id, before_role), []), elapsed[before_role]
            ),
            trace_kernel_midpoint_s(
                trace_rows.get((pair_id, "full"), []), elapsed["full"]
            ),
            trace_kernel_midpoint_s(
                trace_rows.get((pair_id, after_role), []), elapsed[after_role]
            ),
        )
        if all(math.isfinite(value) for value in steady_midpoints):
            before_mid, full_mid, after_mid = steady_midpoints
            midpoint_timebase = "steady_energy_trace_s"
        else:
            reasons.append("energy_trace_kernel_midpoint_missing")
    interpolation_weight = math.nan
    interpolated_control_power = control_power_mean
    interpolated_raw_control_power = raw_control_power_mean
    rate_estimation = "bracket_mean_fallback"
    if all(math.isfinite(value) for value in (before_mid, full_mid, after_mid)):
        duration = after_mid - before_mid
        if duration > 0.0:
            interpolation_weight = (full_mid - before_mid) / duration
            if 0.0 <= interpolation_weight <= 1.0:
                interpolated_control_power = (
                    control_power_before
                    + interpolation_weight * (control_power_after - control_power_before)
                )
                interpolated_raw_control_power = (
                    raw_control_power_before
                    + interpolation_weight * (raw_control_power_after - raw_control_power_before)
                )
                rate_estimation = f"midpoint_linear_interpolation_{midpoint_timebase}"
            else:
                reasons.append("control_midpoint_outside_bracket")
        else:
            reasons.append("control_timestamp_order_invalid")
    else:
        reasons.append("control_timestamp_missing")

    direct_delta = net["full"] - control_net_mean
    atc_delta = net["full"] - interpolated_control_power * elapsed["full"]
    atc_correction = atc_delta - direct_delta
    raw_board_rate_atc_delta = (
        delta["full"] - interpolated_raw_control_power * elapsed["full"]
    )
    raw_endpoint_atc_values = (
        delta["full"] - raw_control_power_before * elapsed["full"],
        delta["full"] - raw_control_power_after * elapsed["full"],
    )
    idle_cancellation_residual = raw_board_rate_atc_delta - atc_delta
    n_elements = num(by_role.get("full", {}), "n_elements")
    if not math.isfinite(n_elements) or n_elements <= 0.0:
        reasons.append("invalid_element_denominator")
    operand_treatment_count = n_elements * treatment_operand_delta
    if (not math.isfinite(operand_treatment_count) or
            operand_treatment_count <= 0.0):
        reasons.append("invalid_operand_treatment_denominator")
    trace_input, trace_input_reasons = analyze_pair_trace_input(
        pair_id,
        roles,
        trace_rows,
        interpolation_weight,
        elapsed["full"],
        operand_treatment_count,
        args,
    )
    reasons.extend(trace_input_reasons)
    if control_elapsed_mean < args.min_control_elapsed_s:
        reasons.append("control_elapsed_below_gate")
    control_to_full = safe_div(control_elapsed_mean, elapsed["full"])
    if control_to_full < args.min_control_to_full_ratio:
        reasons.append("control_duration_ratio_below_gate")
    if control_power_drift > args.max_control_rate_drift_fraction:
        reasons.append("control_rate_drift_too_high")
    if raw_control_power_drift > args.max_control_rate_drift_fraction:
        reasons.append("raw_control_rate_drift_too_high")
    for role in roles:
        if manifest.get((pair_id, role), "pass") != "pass":
            reasons.append(f"quiescence_not_passed_{role}")

    common_rate_reasons = {
        "control_elapsed_below_gate",
        "control_duration_ratio_below_gate",
        "control_midpoint_outside_bracket",
        "control_timestamp_order_invalid",
        "control_timestamp_missing",
    }
    rate_reasons = common_rate_reasons | {"control_rate_drift_too_high"}
    raw_rate_reasons = common_rate_reasons | {"raw_control_rate_drift_too_high"}
    strict_measurement_reasons = [
        reason for reason in reasons
        if not reason.startswith("quiescence_")
        and reason not in rate_reasons
        and reason not in raw_rate_reasons
    ]
    thermal_tolerant_measurement_reasons = [
        reason for reason in strict_measurement_reasons
        if reason != "pair_temperature_span_too_high"
    ]
    ramp_conditioned_raw_rate_measurement_reasons = [
        reason for reason in strict_measurement_reasons
        if reason not in {
            "pair_temperature_span_too_high",
            "pair_idle_power_spread_too_high",
            "pair_sm_clock_span_too_high",
        }
    ]
    measurement_status = "pass" if not strict_measurement_reasons else "fail"
    thermal_tolerant_measurement_status = (
        "pass" if not thermal_tolerant_measurement_reasons else "fail"
    )
    ramp_conditioned_raw_rate_measurement_status = (
        "pass" if not ramp_conditioned_raw_rate_measurement_reasons else "fail"
    )
    environment_status = (
        "pass" if not any(reason.startswith("quiescence_") for reason in reasons) else "fail"
    )
    rate_status = "pass" if not any(reason in rate_reasons for reason in reasons) else "fail"
    raw_rate_status = (
        "pass" if not any(reason in raw_rate_reasons for reason in reasons) else "fail"
    )
    protocol_status = (
        "pass"
        if measurement_status == "pass" and environment_status == "pass" and rate_status == "pass"
        else "fail"
    )
    thermal_tolerant_protocol_status = (
        "pass"
        if thermal_tolerant_measurement_status == "pass"
        and environment_status == "pass"
        and rate_status == "pass"
        else "fail"
    )
    ramp_conditioned_raw_rate_protocol_status = (
        "pass"
        if ramp_conditioned_raw_rate_measurement_status == "pass"
        and environment_status == "pass" and raw_rate_status == "pass"
        else "fail"
    )
    sass_status = static_sass.get(
        (template.get("binary_sha256", ""), template.get("cache_policy", "")), "not_run"
    )
    ncu_key = (
        template.get("binary_sha256", ""),
        template.get("cache_condition", ""),
        template.get("cache_policy", ""),
        template.get("softmax_cols", ""),
        template.get("blocks_per_sm", ""),
        template.get("grid_blocks", ""),
    )
    ncu_status = dynamic_ncu.get(
        ncu_key,
        "scoped_path_pass"
        if args.ncu_cache_condition and template.get("cache_condition") == args.ncu_cache_condition
        else "not_run",
    )

    if args.ramp_conditioned_raw_rate:
        chosen_protocol = ramp_conditioned_raw_rate_protocol_status
        chosen_atc_delta = raw_board_rate_atc_delta
    elif args.thermal_tolerant:
        chosen_protocol = thermal_tolerant_protocol_status
        chosen_atc_delta = atc_delta
    else:
        chosen_protocol = protocol_status
        chosen_atc_delta = atc_delta
    if chosen_protocol != "pass":
        if args.ramp_conditioned_raw_rate:
            verdict = "not_identified_ramp_conditioned_raw_rate_protocol_gate"
        elif args.thermal_tolerant:
            verdict = "not_identified_thermal_tolerant_protocol_gate"
        else:
            verdict = "not_identified_protocol_gate"
    elif chosen_atc_delta <= 0.0:
        verdict = "not_identified_nonpositive_atc"
    elif control_mode == "probe":
        # Every legacy probe triplet is C-T-C, so treatment state is aliased
        # with middle position.  NCU can validate the path but cannot remove
        # this energy/order confound.
        verdict = "provisional_position_confounded"
    elif args.ramp_conditioned_raw_rate:
        verdict = (
            "exploratory_ramp_conditioned_raw_rate_static_sass"
            if sass_status == "pass"
            else "exploratory_ramp_conditioned_raw_rate_no_static_sass"
        )
    elif args.thermal_tolerant:
        verdict = (
            "exploratory_thermal_tolerant_static_sass"
            if sass_status == "pass"
            else "exploratory_thermal_tolerant_no_static_sass"
        )
    elif sass_status != "pass":
        verdict = "provisional_no_static_sass"
    elif ncu_status == "scoped_path_pass":
        verdict = "provisional_static_sass_and_scoped_ncu"
    else:
        verdict = "provisional_static_sass_no_ncu"

    return {
        "pair_id": pair_id,
        "repeat": template.get("repeat", ""),
        "control_mode": control_mode,
        "gpu_id": template.get("gpu_id", ""),
        "profile_name": template.get("profile_name", ""),
        "cuda_pci_bus_id": template.get("cuda_pci_bus_id", ""),
        "cuda_binary_arch": template.get("cuda_binary_arch", ""),
        "cache_condition": template.get("cache_condition", ""),
        "cache_policy": template.get("cache_policy", ""),
        "softmax_cols": template.get("softmax_cols", ""),
        "blocks_per_sm": template.get("blocks_per_sm", ""),
        "grid_nominal_ctas_per_sm": template.get("grid_nominal_ctas_per_sm", ""),
        "grid_blocks": template.get("grid_blocks", ""),
        "grid_blocks_source": template.get("grid_blocks_source", "legacy_derived"),
        "grid_experiment_purpose": template.get("grid_experiment_purpose", ""),
        "runtime_sm_count": template.get("runtime_sm_count", ""),
        "smid_unique": template.get("smid_unique", ""),
        "smid_coverage_fraction": template.get("smid_coverage_fraction", ""),
        "smid_assignment_max_blocks_per_sm": template.get(
            "smid_assignment_max_blocks_per_sm", template.get("smid_max_blocks_on_sm", "")
        ),
        "smid_set": template.get("smid_set", ""),
        "smid_histogram": template.get("smid_histogram", ""),
        "ITER": template.get("ITER", ""),
        "n_elements": template.get("n_elements", ""),
        "operand_delta_per_element": treatment_operand_delta,
        "operand_treatment_count": operand_treatment_count,
        "exp_input_dtype": template.get("exp_input_dtype", ""),
        "special_function_path": template.get("special_function_path", ""),
        "xu_documented_results_per_sm_cycle": template.get(
            "xu_documented_results_per_sm_cycle", ""
        ),
        "expected_control_xu_thread_ops_per_cta_iter": template.get(
            "expected_control_xu_thread_ops_per_cta_iter", ""
        ),
        "expected_treatment_xu_thread_ops_per_cta_iter": template.get(
            "expected_treatment_xu_thread_ops_per_cta_iter", ""
        ),
        "expected_probe_xu_thread_ops_per_cta_iter": template.get(
            "expected_probe_xu_thread_ops_per_cta_iter", ""
        ),
        "expected_control_xu_warp_instructions_per_cta_iter": template.get(
            "expected_control_xu_warp_instructions_per_cta_iter", ""
        ),
        "expected_treatment_xu_warp_instructions_per_cta_iter": template.get(
            "expected_treatment_xu_warp_instructions_per_cta_iter", ""
        ),
        "expected_probe_xu_warp_instructions_per_cta_iter": template.get(
            "expected_probe_xu_warp_instructions_per_cta_iter", ""
        ),
        "ideal_control_xu_cycles_per_cta_iter": template.get(
            "ideal_control_xu_cycles_per_cta_iter", ""
        ),
        "ideal_treatment_xu_cycles_per_cta_iter": template.get(
            "ideal_treatment_xu_cycles_per_cta_iter", ""
        ),
        "ideal_probe_xu_cycles_per_cta_iter": template.get(
            "ideal_probe_xu_cycles_per_cta_iter", ""
        ),
        "sfu_regime_evidence_status": template.get(
            "sfu_regime_evidence_status", ""
        ),
        "execution_model": execution_model,
        "bracket_context_id": context_id,
        "idle_baseline_scope": idle_scope,
        "persistent_bracket_status": persistent_status,
        "persistent_batch_context_status": persistent_batch_status,
        "max_inter_role_gap_s": max_inter_role_gap,
        "pair_common_idle_power_W": idle_common,
        "idle_power_spread_fraction": idle_spread,
        "idle_spread_status": idle_spread_status,
        "pair_temperature_start_C": temperature_start,
        "pair_temperature_end_C": temperature_end,
        "pair_temperature_span_C": temperature_span,
        "thermal_status": thermal_status,
        "full_sm_clock_before_mhz": by_role.get("full", {}).get("clock_sm_before_mhz", ""),
        "full_sm_clock_after_mhz": by_role.get("full", {}).get("clock_sm_after_mhz", ""),
        "pair_sm_clock_span_fraction": clock_span,
        "clock_status": clock_status,
        "control_before_elapsed_s": elapsed[before_role],
        "control_after_elapsed_s": elapsed[after_role],
        "control_elapsed_bracket_mean_s": control_elapsed_mean,
        "full_elapsed_s": elapsed["full"],
        "full_to_control_elapsed_ratio": elapsed_ratio,
        "control_active_power_before_W": control_power_before,
        "control_active_power_after_W": control_power_after,
        "control_active_power_bracket_mean_W": control_power_mean,
        "control_active_power_at_full_midpoint_W": interpolated_control_power,
        "control_rate_interpolation_weight": interpolation_weight,
        "control_rate_estimation": rate_estimation,
        "control_active_power_drift_fraction": control_power_drift,
        "raw_control_active_power_drift_fraction": raw_control_power_drift,
        "full_active_power_W": full_power,
        **trace_quality,
        **trace_input,
        "full_net_E_J": net["full"],
        "control_net_E_bracket_mean_J": control_net_mean,
        "same_ITER_completion_delta_E_J": direct_delta,
        "operand_rate_ATC_delta_E_J": atc_delta,
        "ATC_time_correction_J": atc_correction,
        "raw_board_rate_ATC_delta_E_J": raw_board_rate_atc_delta,
        "raw_board_rate_ATC_pJ_per_element": safe_div(
            raw_board_rate_atc_delta * 1.0e12, operand_treatment_count
        ),
        "raw_endpoint_ATC_min_pJ_per_element": (
            safe_div(min(raw_endpoint_atc_values) * 1.0e12,
                     operand_treatment_count)
        ),
        "raw_endpoint_ATC_max_pJ_per_element": (
            safe_div(max(raw_endpoint_atc_values) * 1.0e12,
                     operand_treatment_count)
        ),
        "idle_cancellation_residual_J": idle_cancellation_residual,
        "full_net_pJ_per_element": net["full"] * 1.0e12 / n_elements,
        "operand_rate_ATC_pJ_per_element": safe_div(
            atc_delta * 1.0e12, operand_treatment_count
        ),
        "measurement_status": measurement_status,
        "thermal_tolerant_measurement_status": thermal_tolerant_measurement_status,
        "environment_status": environment_status,
        "rate_status": rate_status,
        "raw_rate_status": raw_rate_status,
        "protocol_status": protocol_status,
        "thermal_tolerant_protocol_status": thermal_tolerant_protocol_status,
        "ramp_conditioned_raw_rate_protocol_status": ramp_conditioned_raw_rate_protocol_status,
        "sass_status": sass_status,
        "ncu_status": ncu_status,
        "verdict": verdict,
        "reasons": ";".join(dict.fromkeys(reasons)),
    }


def summarize(
    details: list[dict[str, Any]], thermal_tolerant: bool, ramp_conditioned_raw_rate: bool
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        grouped[(
            row["control_mode"], row["cache_condition"], row["cache_policy"],
            row["softmax_cols"], row["blocks_per_sm"], row["grid_blocks"],
            row["grid_blocks_source"],
        )].append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        trace_ready = all(
            row.get("energy_trace_status") == "pass"
            and math.isfinite(num(row, "energy_trace_ATC_pJ_per_operand"))
            for row in rows
        )
        canonical_atc_field = (
            "energy_trace_ATC_pJ_per_operand"
            if trace_ready
            else "operand_rate_ATC_pJ_per_element"
        )
        summary_estimator = (
            "guarded_interior_energy_trace_theil_sen"
            if trace_ready
            else "legacy_endpoint_energy_counter"
        )
        summary_unit = "pJ/operand" if trace_ready else "pJ/element"
        exploratory_values = [float(row[canonical_atc_field]) for row in rows]
        strict_values = [
            float(row[canonical_atc_field])
            for row in rows if row["protocol_status"] == "pass"
        ]
        tolerant_values = [
            float(row[canonical_atc_field])
            for row in rows if row["thermal_tolerant_protocol_status"] == "pass"
        ]
        raw_rate_values = [
            float(row["raw_board_rate_ATC_pJ_per_element"])
            for row in rows if row["ramp_conditioned_raw_rate_protocol_status"] == "pass"
        ]
        ci_low, ci_high = bootstrap_median_ci(tolerant_values)
        if ramp_conditioned_raw_rate:
            selected_values = raw_rate_values
        elif thermal_tolerant:
            selected_values = tolerant_values
        else:
            selected_values = strict_values
        if any(row["verdict"].startswith("exploratory_ramp_conditioned_raw_rate") for row in rows):
            verdict = "exploratory_ramp_conditioned_raw_rate_only"
        elif any(row["verdict"].startswith("exploratory_thermal_tolerant") for row in rows):
            verdict = "exploratory_thermal_tolerant_only"
        elif any(row["verdict"].startswith("provisional_") for row in rows):
            verdict = "provisional_only"
        elif selected_values:
            verdict = "not_identified_nonpositive_atc"
        else:
            verdict = "not_identified_protocol_gate"
        output.append(
            {
                "control_mode": key[0],
                "cache_condition": key[1],
                "cache_policy": key[2],
                "softmax_cols": key[3],
                "blocks_per_sm": key[4],
                "grid_blocks": key[5],
                "grid_blocks_source": key[6],
                "summary_estimator": summary_estimator,
                "summary_unit": summary_unit,
                "total_pairs": len(rows),
                "strict_protocol_valid_pairs": len(strict_values),
                "thermal_tolerant_protocol_valid_pairs": len(tolerant_values),
                "ramp_conditioned_raw_rate_valid_pairs": len(raw_rate_values),
                "strict_positive_atc_pairs": sum(value > 0.0 for value in strict_values),
                "thermal_tolerant_positive_atc_pairs": sum(value > 0.0 for value in tolerant_values),
                "ramp_conditioned_raw_rate_positive_atc_pairs": sum(
                    value > 0.0 for value in raw_rate_values
                ),
                "exploratory_signed_min_pJ_per_element": min(exploratory_values),
                "exploratory_signed_median_pJ_per_element": statistics.median(exploratory_values),
                "exploratory_signed_mean_pJ_per_element": statistics.mean(exploratory_values),
                "exploratory_signed_max_pJ_per_element": max(exploratory_values),
                "exploratory_signed_iqr_pJ_per_element": percentile(exploratory_values, 0.75)
                - percentile(exploratory_values, 0.25),
                "strict_protocol_signed_median_pJ_per_element": (
                    statistics.median(strict_values) if strict_values else math.nan
                ),
                "thermal_tolerant_signed_median_pJ_per_element": (
                    statistics.median(tolerant_values) if tolerant_values else math.nan
                ),
                "ramp_conditioned_raw_rate_signed_median_pJ_per_element": (
                    statistics.median(raw_rate_values) if raw_rate_values else math.nan
                ),
                "thermal_tolerant_bootstrap_median_ci_low_pJ_per_element": ci_low,
                "thermal_tolerant_bootstrap_median_ci_high_pJ_per_element": ci_high,
                "median_full_to_control_elapsed_ratio": statistics.median(
                    float(row["full_to_control_elapsed_ratio"]) for row in rows
                ),
                "median_control_rate_drift_fraction": statistics.median(
                    float(row["control_active_power_drift_fraction"]) for row in rows
                ),
                "median_raw_control_rate_drift_fraction": statistics.median(
                    float(row["raw_control_active_power_drift_fraction"]) for row in rows
                ),
                "median_pair_sm_clock_span_fraction": statistics.median(
                    float(row["pair_sm_clock_span_fraction"]) for row in rows
                ),
                "persistent_bracket_valid_pairs": sum(
                    row["persistent_bracket_status"] == "pass"
                    and row["persistent_batch_context_status"] == "pass"
                    for row in rows
                ),
                "verdict": verdict,
            }
        )
    return output


def display(value: float, digits: int = 6) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:.{digits}g}"


def write_markdown(
    path: Path,
    details: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    thermal_tolerant: bool,
    ramp_conditioned_raw_rate: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trace_estimator = bool(details) and all(
        row.get("energy_trace_status") == "pass"
        and math.isfinite(num(row, "energy_trace_ATC_pJ_per_operand"))
        for row in details
    )
    if ramp_conditioned_raw_rate:
        atc_field = "raw_board_rate_ATC_pJ_per_element"
        drift_field = "raw_control_active_power_drift_fraction"
        protocol_field = "ramp_conditioned_raw_rate_protocol_status"
        valid_field = "ramp_conditioned_raw_rate_valid_pairs"
        positive_field = "ramp_conditioned_raw_rate_positive_atc_pairs"
        median_field = "ramp_conditioned_raw_rate_signed_median_pJ_per_element"
        form_description = (
            "이 보고서는 raw-board-rate form을 사용한다. full 에너지에서 full 시점의 "
            "control active-rate를 시간 중점 선형 보간해 뺀다. pair-common idle-corrected "
            "form은 cancellation identity 확인용으로만 보존한다."
        )
        formula = "E_raw_OR(full <- control) = delta_E_full - P_control(t_full_mid) * t_full"
        valid_label = "raw-rate valid"
        positive_label = "raw-rate positive"
        median_label = "raw-rate median (pJ/element)"
        atc_label = "raw-board-rate ATC (pJ/element)"
        drift_label = "raw control-rate drift (%)"
        status_label = "raw-rate"
    elif thermal_tolerant:
        atc_field = (
            "energy_trace_ATC_pJ_per_operand"
            if trace_estimator
            else "operand_rate_ATC_pJ_per_element"
        )
        drift_field = "control_active_power_drift_fraction"
        protocol_field = "thermal_tolerant_protocol_status"
        valid_field = "thermal_tolerant_protocol_valid_pairs"
        positive_field = "thermal_tolerant_positive_atc_pairs"
        median_field = "thermal_tolerant_signed_median_pJ_per_element"
        form_description = (
            "이 보고서는 guarded/interior energy-trace Theil–Sen form을 사용한다."
            if trace_estimator
            else "이 보고서는 thermal-tolerant idle-corrected form을 사용한다."
        )
        formula = "E_OR(full <- control) = E'_full - P_control(t_full_mid) * t_full"
        valid_label = "thermal-tolerant valid"
        positive_label = "thermal-tolerant positive"
        median_label = f"signed median ({'pJ/operand' if trace_estimator else 'pJ/element'})"
        atc_label = f"ATC ({'pJ/operand' if trace_estimator else 'pJ/element'})"
        drift_label = "control rate drift (%)"
        status_label = "thermal-tolerant"
    else:
        atc_field = (
            "energy_trace_ATC_pJ_per_operand"
            if trace_estimator
            else "operand_rate_ATC_pJ_per_element"
        )
        drift_field = "control_active_power_drift_fraction"
        protocol_field = "protocol_status"
        valid_field = "strict_protocol_valid_pairs"
        positive_field = "strict_positive_atc_pairs"
        median_field = "strict_protocol_signed_median_pJ_per_element"
        form_description = (
            "이 보고서는 guarded/interior energy-trace Theil–Sen form을 사용한다."
            if trace_estimator
            else "이 보고서는 strict idle-corrected form을 사용한다."
        )
        formula = "E_OR(full <- control) = E'_full - P_control(t_full_mid) * t_full"
        valid_label = "strict valid"
        positive_label = "strict positive"
        median_label = f"signed median ({'pJ/operand' if trace_estimator else 'pJ/element'})"
        atc_label = f"ATC ({'pJ/operand' if trace_estimator else 'pJ/element'})"
        drift_label = "control rate drift (%)"
        status_label = "strict"
    lines = [
        "# FP16 Softmax Operand-rate ATC 결과",
        "",
        "## 기술 요약",
        "",
        form_description,
        "",
        "```text",
        formula,
        "```",
        "",
        "## CTA grid별 탐색값 — 최종 계수 아님",
        "",
        f"| control | grid CTAs | pairs | {valid_label} | {positive_label} | {median_label} | verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(
            "| {control_mode} | {grid_blocks} | {total_pairs} | {valid} | {positive} | {median} | {verdict} |".format(
                **row,
                valid=row[valid_field],
                positive=row[positive_field],
                median=display(float(row[median_field])),
            )
        )
    lines += [
        "",
        "## Pair detail",
        "",
        f"| pair | control | grid | observed SMs | {atc_label} | full/control time | {drift_label} | temp span (°C) | {status_label} | verdict |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in details:
        lines.append(
            "| {pair_id} | {control_mode} | {grid_blocks} | {smid_unique} | {atc} | {ratio:.3f} | {drift:.3f} | {temp:.3f} | {status} | {verdict} |".format(
                **row,
                atc=display(float(row[atc_field])),
                ratio=float(row["full_to_control_elapsed_ratio"]),
                drift=float(row[drift_field]) * 100.0,
                temp=float(row["pair_temperature_span_C"]),
                status=row[protocol_field],
            )
        )
    lines += [
        "",
        "## 해석 제약",
        "",
        "- explicit CTA grid는 물리 SM affinity가 아니다. `smid_unique`는 kernel entry에서 관측한 배치이며 동시 residency나 고정된 SM subset을 뜻하지 않는다.",
        "- supplied trace의 triplet CI는 noise diagnostic이며 개별 zero-inclusion을 final reject gate로 쓰지 않는다.",
        "- same-kernel probe의 C–T–C triplet은 treatment와 middle position이 alias되므로 `provisional_position_confounded`다. 최종 판정은 별도 counterbalanced analyzer의 matched F/R aggregate를 따른다.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--input", type=Path, required=True)
    result.add_argument("--manifest", type=Path)
    result.add_argument("--sass-audit", type=Path)
    result.add_argument(
        "--ncu-sidecar",
        type=Path,
        help="matching full/linear NCU replay sidecar; it is path evidence, never energy",
    )
    result.add_argument(
        "--ncu-cache-condition",
        choices=("cache_reuse_candidate", "streaming_large_ws"),
        help="condition covered by one scoped NCU path sidecar; it is not an energy source",
    )
    result.add_argument("--detail-out", type=Path, required=True)
    result.add_argument("--summary-out", type=Path, required=True)
    result.add_argument("--report-out", type=Path)
    result.add_argument("--control-mode", choices=("auto", *CONTROL_SPECS), default="auto")
    result.add_argument(
        "--thermal-tolerant",
        action="store_true",
        help="exclude only pair temperature span from final protocol selection; result remains exploratory",
    )
    result.add_argument(
        "--ramp-conditioned-raw-rate",
        action="store_true",
        help=(
            "use algebraically equivalent raw-board-rate ATC for exploratory selection; "
            "temperature and idle-spread remain recorded but are not hard gates"
        ),
    )
    result.add_argument("--numerical-check-id", default="fp16_softmax_cpu_fp64_v1_pass")
    result.add_argument("--max-idle-spread-fraction", type=float, default=0.10)
    result.add_argument("--max-pair-temperature-span-c", type=float, default=5.0)
    result.add_argument("--max-control-rate-drift-fraction", type=float, default=0.10)
    result.add_argument(
        "--max-pair-sm-clock-span-fraction",
        type=float,
        default=0.15,
        help="strict gate for the max-min SM-clock span divided by median clock",
    )
    result.add_argument(
        "--require-persistent-bracket",
        action="store_true",
        help="require same-context persistent v1/v2 C->F->C provenance and bounded inter-role gap",
    )
    result.add_argument(
        "--require-energy-trace",
        action="store_true",
        help=(
            "require every role to report energy_trace_status=pass and a robust "
            "guarded/interior trace slope integration method"
        ),
    )
    result.add_argument(
        "--require-sfu-regime-evidence",
        action="store_true",
        help=(
            "require a matching A100 resource/NCU sidecar to mark "
            "sfu_regime_evidence_status=pass; use only for a saturated-XU claim"
        ),
    )
    result.add_argument(
        "--energy-trace-input",
        type=Path,
        help=(
            "optional raw energy trace CSV; cumulative-energy residual blocks are "
            "bootstrapped with the same Theil--Sen estimator; triplet CI is diagnostic"
        ),
    )
    result.add_argument(
        "--energy-trace-bootstrap-samples",
        type=int,
        default=2000,
        help="block-bootstrap draws for a supplied raw energy trace (default 2000)",
    )
    result.add_argument(
        "--energy-trace-block-updates",
        type=int,
        default=0,
        help="moving block length in update events; 0 selects sqrt(event count)",
    )
    result.add_argument(
        "--energy-trace-min-fit-points",
        "--energy-trace-min-fit-updates",
        dest="energy_trace_min_fit_points",
        type=int,
        default=8,
        help=(
            "minimum guarded changed counter points per role (default 8); "
            "the legacy --energy-trace-min-fit-updates spelling is an alias"
        ),
    )
    result.add_argument(
        "--max-persistent-inter-role-gap-s",
        type=float,
        default=0.25,
        help="maximum measured gap from one role kernel end to the next role kernel start",
    )
    result.add_argument("--min-control-elapsed-s", type=float, default=0.5)
    result.add_argument("--min-control-to-full-ratio", type=float, default=0.20)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.energy_trace_bootstrap_samples < 100:
        raise SystemExit("--energy-trace-bootstrap-samples must be at least 100")
    if args.energy_trace_block_updates < 0 or args.energy_trace_min_fit_points < 3:
        raise SystemExit(
            "--energy-trace-block-updates must be non-negative and "
            "--energy-trace-min-fit-points at least 3"
        )
    rows = [row for row in read_csv(args.input) if row.get("pair_id")]
    if any(row.get("profile_name") == "a100" for row in rows) and args.manifest is None:
        raise SystemExit(
            "A100 analysis requires --manifest; environment and quiescence gates "
            "cannot be inferred from raw energy rows alone"
        )
    pairs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        pairs[row["pair_id"]].append(row)
    manifest = manifest_status(args.manifest)
    static_sass = sass_statuses(args.sass_audit)
    dynamic_ncu = ncu_statuses(args.ncu_sidecar)
    energy_trace = read_energy_trace(args.energy_trace_input)
    persistent_batch_status, persistent_batch_reasons = persistent_batch_context_status(rows, args)
    details = [
        analyze_pair(
            pair_rows, manifest, static_sass, dynamic_ncu, energy_trace,
            persistent_batch_status,
            persistent_batch_reasons, args,
        )
        for _, pair_rows in sorted(pairs.items())
    ]
    summaries = summarize(details, args.thermal_tolerant, args.ramp_conditioned_raw_rate)
    write_csv(args.detail_out, DETAIL_FIELDS, details)
    write_csv(args.summary_out, SUMMARY_FIELDS, summaries)
    if args.report_out:
        write_markdown(
            args.report_out,
            details,
            summaries,
            args.thermal_tolerant,
            args.ramp_conditioned_raw_rate,
        )
    print(f"detail_out={args.detail_out}")
    print(f"summary_out={args.summary_out}")
    if args.report_out:
        print(f"report_out={args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
