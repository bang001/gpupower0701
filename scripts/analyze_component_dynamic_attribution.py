#!/usr/bin/env python3
"""Analyze matched-ITER completion, MI-ATC, and joint traffic/time models."""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_REVISION = "component_dynamic_attribution_v3"
MIN_POSITIVE_FRACTION = 0.8
SUPPORTED_PROTOCOL_REVISIONS = {
    "component_dynamic_attribution_v1",
    "component_dynamic_attribution_v2",
    PROTOCOL_REVISION,
}
ACCEPTED_NCU_QUIESCENCE_STATUSES = {
    "strict_passed",
    "counter_scope_passed",
}

COMPONENT_CONFIG = {
    "tensor": {
        "treatment_mode": "reg_mma",
        "control_mode": "reg_operand_only",
        "expected_column": "FLOP",
        "actual_column": "tensor_fp16_f32_ops",
        "ncu_denominator_unit": "FLOP",
        "unit": "pJ/FLOP",
    },
    "shared": {
        "treatment_mode": "shared_scalar_load_only",
        "control_mode": "shared_scalar_addr_only",
        "expected_column": "expected_shared_bytes",
        "actual_column": "shared_read_bytes",
        "ncu_denominator_unit": "byte",
        "unit": "pJ/bit",
    },
    "l1": {
        "treatment_mode": "global_l1_load_only",
        "control_mode": "global_addr_only",
        "expected_column": "expected_l1_bytes",
        "actual_column": "l1_request_bytes",
        "ncu_denominator_unit": "byte",
        "unit": "pJ/bit",
    },
    "l2": {
        "treatment_mode": "l2_cg_load_only",
        "control_mode": "global_l1_load_only",
        "expected_column": "expected_l2_bytes",
        "actual_column": "l2_read_bytes",
        "ncu_denominator_unit": "byte",
        "unit": "pJ/bit",
    },
    "external": {
        "treatment_mode": "dram_cg_load_only",
        "control_mode": "l2_cg_load_only",
        "expected_column": "expected_dram_bytes",
        "actual_column": "dram_read_bytes",
        "ncu_denominator_unit": "byte",
        "unit": "pJ/bit",
    },
}


DETAIL_FIELDS = [
    "protocol_revision",
    "profile",
    "component",
    "coordinate_id",
    "pair_id",
    "repeat",
    "factor_kind",
    "factor_value",
    "calibration_policy",
    "grid_anchor_factor",
    "grid_anchor_blocks_per_sm",
    "grid_work_units",
    "target_duration_s",
    "execution_order",
    "blocks_per_SM",
    "active_SM",
    "quiescence_status",
    "cooldown_wait_seconds",
    "pre_pair_temp_C",
    "pre_pair_power_W",
    "pre_pair_gpu_util_pct",
    "pre_pair_memory_util_pct",
    "treatment_mode",
    "control_mode",
    "treatment_W_SM_KiB",
    "control_W_SM_KiB",
    "reuse_factor",
    "load_repeat",
    "treatment_ITER",
    "control_ITER",
    "energy_binary_sha256",
    "treatment_elapsed_s",
    "control_elapsed_s",
    "delta_t_s",
    "treatment_net_E_J",
    "control_net_E_J",
    "delta_E_completion_J",
    "baseline_before_power_W",
    "baseline_after_power_W",
    "baseline_pair_power_W",
    "baseline_power_drift_pct",
    "baseline_before_gap_ms",
    "baseline_after_gap_ms",
    "pair_transition_gap_ms",
    "delta_E_MI_ATC_J",
    "control_active_power_W",
    "treatment_active_power_W",
    "delta_active_power_W",
    "delta_E_control_rate_ATC_J",
    "expected_denominator",
    "ncu_treatment_denominator_observed",
    "ncu_control_denominator_observed",
    "ncu_incremental_denominator_observed",
    "ncu_denominator_observed_unit",
    "ncu_denominator_scale",
    "denominator",
    "denominator_source",
    "coefficient_unit",
    "completion_coefficient",
    "mi_atc_coefficient",
    "control_rate_atc_coefficient",
    "completion_signal_fraction",
    "mi_atc_signal_fraction",
    "control_rate_atc_signal_fraction",
    "treatment_ncu_label",
    "control_ncu_label",
    "treatment_ncu_acceptance",
    "control_ncu_acceptance",
    "treatment_ncu_binary_sha256",
    "control_ncu_binary_sha256",
    "treatment_ncu_binary_hash_capture",
    "control_ncu_binary_hash_capture",
    "treatment_ncu_quiescence_status",
    "control_ncu_quiescence_status",
    "treatment_tensor_hmma_inst",
    "treatment_tensor_fp16_f32_ops",
    "treatment_shared_accesses",
    "treatment_shared_read_bytes",
    "treatment_l1_accesses",
    "treatment_l1_request_bytes",
    "treatment_l1_path_hit_rate_pct",
    "treatment_l2_accesses",
    "treatment_l2_read_bytes",
    "treatment_l2_path_hit_rate_pct",
    "treatment_l2_logical_read_hit_rate_pct",
    "treatment_dram_accesses",
    "treatment_dram_read_bytes",
    "treatment_stall_long_scoreboard_pct",
    "control_stall_long_scoreboard_pct",
    "measurement_valid",
    "pair_valid",
    "mi_atc_valid",
    "control_rate_atc_valid",
    "regression_valid",
    "completion_diagnostic",
    "mi_atc_diagnostic",
    "control_rate_atc_diagnostic",
    "regression_diagnostic",
    "diagnostic",
]


SUMMARY_FIELDS = [
    "component",
    "estimate_method",
    "coefficient_unit",
    "measurement_valid_rows",
    "positive_rows",
    "total_rows",
    "positive_fraction",
    "min",
    "median",
    "mean",
    "max",
    "stdev",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "status",
    "invalid_reasons",
]


SUBGROUP_FIELDS = [
    "component",
    "blocks_per_SM",
    "estimate_method",
    "coefficient_unit",
    "measurement_valid_rows",
    "positive_rows",
    "total_rows",
    "positive_fraction",
    "min",
    "median",
    "mean",
    "max",
    "stdev",
    "status",
    "invalid_reasons",
]


REGRESSION_FIELDS = [
    "component",
    "model",
    "coefficient_unit",
    "valid_rows",
    "unique_factor_values",
    "unique_blocks_per_sm_values",
    "unique_durations",
    "unique_execution_orders",
    "unique_repeats",
    "fixed_effect_columns",
    "predictor_correlation",
    "standardized_condition_number",
    "intercept_J",
    "component_coefficient",
    "component_coefficient_ci_low",
    "component_coefficient_ci_high",
    "time_coefficient_W",
    "r_squared",
    "residual_std_J",
    "status",
    "diagnostic",
]


NCU_EVIDENCE_FIELDS = [
    "component",
    "role",
    "label",
    "mode",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "acceptance",
    "acceptance_reason",
    "ncu_binary_sha256",
    "ncu_binary_path",
    "ncu_binary_hash_capture",
    "ncu_quiescence_status",
    "tensor_hmma_inst",
    "tensor_fp16_f32_ops",
    "sass_inst_executed",
    "registers_per_thread",
    "spill_zero_verified",
    "shared_accesses",
    "shared_read_bytes",
    "shared_bank_conflicts",
    "l1_accesses",
    "l1_request_bytes",
    "l1_path_hit_rate_pct",
    "l2_accesses",
    "l2_read_bytes",
    "l2_path_hit_rate_pct",
    "l2_native_read_hit_rate_pct",
    "l2_logical_read_hit_rate_pct",
    "dram_accesses",
    "dram_read_bytes",
    "dram_read_bandwidth_GBps",
    "stall_long_scoreboard_pct",
]


NCU_BY_BLOCKS_FIELDS = [
    "component",
    "blocks_per_SM",
    "accepted_treatment_rows",
    "operation_or_access_metric",
    "operation_or_access_median",
    "bytes_metric",
    "bytes_median",
    "path_hit_rate_median_pct",
    "long_scoreboard_median_pct",
]


TENSOR_RF_TREND_FIELDS = [
    "profile",
    "blocks_per_SM",
    "reuse_factor",
    "target_duration_s",
    "measurement_valid_rows",
    "total_rows",
    "treatment_active_power_median_W",
    "control_active_power_median_W",
    "delta_active_power_median_W",
    "treatment_throughput_median_TFLOP_per_s",
    "matched_iter_completion_median_pJ_per_FLOP",
    "clocked_mi_atc_median_pJ_per_FLOP",
    "operand_rate_atc_median_pJ_per_FLOP",
    "operand_rate_positive_fraction",
    "interpretation_status",
]


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def as_float(
    row: dict[str, Any], key: str, default: float = float("nan")
) -> float:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def as_int(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = as_float(row, key, float(default))
    return int(value) if math.isfinite(value) else default


def finite(values: Iterable[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def median(values: Iterable[float]) -> float:
    usable = finite(values)
    return statistics.median(usable) if usable else float("nan")


def percentile(values: list[float], quantile: float) -> float:
    usable = sorted(finite(values))
    if not usable:
        return float("nan")
    position = (len(usable) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return usable[lower]
    weight = position - lower
    return usable[lower] * (1.0 - weight) + usable[upper] * weight


def bootstrap_median_ci(
    values: list[float],
    *,
    clusters: list[str] | None = None,
    samples: int = 2000,
    seed: int = 20260719,
) -> tuple[float, float]:
    usable = finite(values)
    if not usable:
        return float("nan"), float("nan")
    if len(usable) == 1:
        return usable[0], usable[0]
    rng = random.Random(seed)
    if clusters is None:
        medians = [
            statistics.median(rng.choices(usable, k=len(usable)))
            for _ in range(samples)
        ]
    else:
        if len(clusters) != len(values):
            raise ValueError("cluster labels must match median values")
        grouped: dict[str, list[float]] = defaultdict(list)
        for value, cluster in zip(values, clusters):
            if math.isfinite(value):
                grouped[cluster].append(value)
        cluster_names = sorted(grouped)
        medians = []
        for _ in range(samples):
            sampled_names = rng.choices(cluster_names, k=len(cluster_names))
            sample = [value for name in sampled_names for value in grouped[name]]
            medians.append(statistics.median(sample))
    return percentile(medians, 0.025), percentile(medians, 0.975)


def coordinate_clusters(rows: list[dict[str, Any]]) -> list[str]:
    return [
        str(row.get("coordinate_id", "")).strip() or f"row_{index}"
        for index, row in enumerate(rows)
    ]


def ncu_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("mode", "")),
        str(row.get("W_SM_KiB", "")),
        str(row.get("blocks_per_SM", "")),
        str(row.get("active_SM", "")),
        str(row.get("reuse_factor", "1") or "1"),
        str(row.get("load_repeat", "1") or "1"),
    )


def manifest_ncu_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return ncu_key(row)


def accepted_ncu_map(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str, str, str, str, str], dict[str, str]]:
    output: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}

    def profile_priority(row: dict[str, str]) -> int:
        mode = row.get("mode", "")
        profile = row.get("ncu_metric_profile", "")
        preferred = (
            "l2_path_minimal"
            if mode in {"l2_cg_load_only", "dram_cg_load_only"}
            else "full"
        )
        if profile == preferred:
            return 2
        # Older/synthetic evidence without a recorded profile remains usable,
        # but can never override an explicitly preferred profile.
        if not profile:
            return 1
        return 0

    for row in rows:
        if row.get("status") != "ok" or row.get("acceptance") != "accepted":
            continue
        priority = profile_priority(row)
        if priority == 0:
            continue
        key = ncu_key(row)
        previous = output.get(key)
        if previous is not None:
            previous_priority = profile_priority(previous)
            if priority < previous_priority:
                continue
            if priority == previous_priority and previous.get("label") != row.get("label"):
                raise ValueError(
                    f"duplicate accepted exact NCU coordinate in the same metric profile: {key}"
                )
        output[key] = row
    return output


def expected_ncu_bytes(row: dict[str, str], component: str) -> float:
    active_sm = as_float(row, "active_SM")
    blocks = as_float(row, "blocks_per_SM")
    iters = as_float(row, "ITER")
    load_repeat = as_float(row, "load_repeat", 1.0)
    if component == "tensor":
        return as_float(row, "expected_logical_flop")
    return active_sm * blocks * iters * load_repeat * 1024.0


def ncu_denominator_scale(
    component: str,
    treatment_ncu_row: dict[str, str] | None,
    control_ncu_row: dict[str, str] | None,
) -> tuple[float, str, float, float, float]:
    config = COMPONENT_CONFIG[component]
    if treatment_ncu_row is None or control_ncu_row is None:
        return (
            float("nan"),
            "missing_exact_ncu",
            float("nan"),
            float("nan"),
            float("nan"),
        )
    expected = expected_ncu_bytes(treatment_ncu_row, component)
    actual_column = str(config["actual_column"])
    treatment_actual = as_float(treatment_ncu_row, actual_column)
    control_actual = as_float(control_ncu_row, actual_column, 0.0)
    incremental_actual = treatment_actual - control_actual
    if expected <= 0.0 or incremental_actual <= 0.0:
        return (
            float("nan"),
            "invalid_incremental_exact_ncu_denominator",
            treatment_actual,
            control_actual,
            incremental_actual,
        )
    return (
        incremental_actual / expected,
        "ncu_incremental_actual_exact_coordinate",
        treatment_actual,
        control_actual,
        incremental_actual,
    )


def time_gap_ms(first: dict[str, str], second: dict[str, str]) -> float:
    first_start = as_float(first, "measurement_start_epoch_ms")
    first_end = as_float(first, "measurement_end_epoch_ms")
    second_start = as_float(second, "measurement_start_epoch_ms")
    second_end = as_float(second, "measurement_end_epoch_ms")
    if second_start >= first_end:
        return second_start - first_end
    if first_start >= second_end:
        return first_start - second_end
    return 0.0


def coefficient(energy_j: float, denominator: float, component: str) -> float:
    if denominator <= 0.0 or not math.isfinite(energy_j):
        return float("nan")
    # Tensor denominators are FLOP and memory denominators are converted to
    # bits in build_detail_rows. Both therefore map directly to pJ/unit.
    return energy_j * 1.0e12 / denominator


def build_detail_rows(
    manifest_rows: list[dict[str, str]],
    ncu_rows: list[dict[str, str]],
    *,
    max_pair_gap_ms: float,
    max_baseline_gap_ms: float,
    max_baseline_drift_pct: float,
    min_control_elapsed_s: float,
    min_treatment_elapsed_s: float,
    require_ncu: bool,
    require_quiescence: bool,
) -> list[dict[str, Any]]:
    ncu = accepted_ncu_map(ncu_rows)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest_rows:
        grouped[row.get("pair_id", "")].append(row)

    output: list[dict[str, Any]] = []
    required_roles = {"baseline_before", "control", "treatment", "baseline_after"}
    for pair_id, rows in sorted(grouped.items()):
        if not pair_id:
            continue
        by_role = {row.get("role", ""): row for row in rows}
        reasons: list[str] = []
        if len(rows) != 4 or set(by_role) != required_roles:
            first = rows[0] if rows else {}
            output.append(
                {
                    "protocol_revision": first.get("protocol_revision", ""),
                    "profile": first.get("profile", ""),
                    "component": first.get("component", ""),
                    "coordinate_id": first.get("coordinate_id", ""),
                    "pair_id": pair_id,
                    "repeat": first.get("repeat", ""),
                    "blocks_per_SM": first.get("blocks_per_SM", ""),
                    "coefficient_unit": COMPONENT_CONFIG.get(
                        first.get("component", ""), {}
                    ).get("unit", ""),
                    "measurement_valid": False,
                    "pair_valid": False,
                    "mi_atc_valid": False,
                    "control_rate_atc_valid": False,
                    "regression_valid": False,
                    "completion_diagnostic": "missing_or_duplicate_pair_roles",
                    "mi_atc_diagnostic": "missing_or_duplicate_pair_roles",
                    "control_rate_atc_diagnostic": "missing_or_duplicate_pair_roles",
                    "regression_diagnostic": "missing_or_duplicate_pair_roles",
                    "diagnostic": "missing_or_duplicate_pair_roles",
                }
            )
            continue
        treatment = by_role["treatment"]
        control = by_role["control"]
        before = by_role["baseline_before"]
        after = by_role["baseline_after"]
        component = treatment.get("component", "")
        config = COMPONENT_CONFIG.get(component)
        if config is None:
            reasons.append("unknown_component")
            config = COMPONENT_CONFIG["tensor"]
        revisions = {row.get("protocol_revision", "") for row in rows}
        if len(revisions) != 1 or not revisions.issubset(SUPPORTED_PROTOCOL_REVISIONS):
            reasons.append("protocol_revision_mismatch")
        if treatment.get("mode") != config["treatment_mode"]:
            reasons.append("treatment_mode_mismatch")
        if control.get("mode") != config["control_mode"]:
            reasons.append("control_mode_mismatch")
        if treatment.get("ITER") != control.get("ITER"):
            reasons.append("iter_mismatch")
        if treatment.get("gpu_id") != control.get("gpu_id"):
            reasons.append("physical_gpu_mismatch")
        if any(row.get("smid_histogram_ok", "").lower() != "true" for row in rows):
            reasons.append("smid_histogram_not_ok")
        if len({row.get("binary_sha256", "") for row in rows}) != 1:
            reasons.append("binary_hash_mismatch")
        if require_quiescence and any(
            row.get("quiescence_status") != "strict_passed" for row in rows
        ):
            reasons.append("gpu_quiescence_not_verified")
        if any(row.get("energy_source") != "nvml_total_energy" for row in rows):
            reasons.append("non_total_energy_source")
        if any(
            row.get("measurement_scope") != "gpu_device_total_energy_counter"
            for row in rows
        ):
            reasons.append("measurement_scope_mismatch")

        before_elapsed = as_float(before, "elapsed_s")
        after_elapsed = as_float(after, "elapsed_s")
        before_power = as_float(before, "net_E_J") / before_elapsed if before_elapsed > 0 else float("nan")
        after_power = as_float(after, "net_E_J") / after_elapsed if after_elapsed > 0 else float("nan")
        baseline_power = median([before_power, after_power])
        baseline_drift = (
            abs(after_power - before_power) / baseline_power * 100.0
            if baseline_power > 0.0
            else float("nan")
        )
        pair_gap = time_gap_ms(treatment, control)
        first_pair = min(
            [treatment, control], key=lambda row: as_float(row, "measurement_start_epoch_ms")
        )
        last_pair = max(
            [treatment, control], key=lambda row: as_float(row, "measurement_end_epoch_ms")
        )
        before_gap = time_gap_ms(before, first_pair)
        after_gap = time_gap_ms(last_pair, after)
        if pair_gap > max_pair_gap_ms:
            reasons.append("pair_transition_gap_too_large")
        if before_gap > max_baseline_gap_ms or after_gap > max_baseline_gap_ms:
            reasons.append("active_baseline_not_contemporaneous")
        if not math.isfinite(baseline_drift) or baseline_drift > max_baseline_drift_pct:
            reasons.append("active_baseline_drift_too_high")

        treatment_ncu = ncu.get(manifest_ncu_key(treatment))
        control_ncu = ncu.get(manifest_ncu_key(control))
        if require_ncu and treatment_ncu is None:
            reasons.append("missing_treatment_exact_ncu_acceptance")
        if require_ncu and control_ncu is None:
            reasons.append("missing_control_exact_ncu_acceptance")
        energy_binary_hash = treatment.get("binary_sha256", "").strip()
        if require_ncu and not energy_binary_hash:
            reasons.append("missing_energy_binary_sha256")
        if require_ncu and treatment_ncu is not None and control_ncu is not None:
            for role, ncu_row in (
                ("treatment", treatment_ncu),
                ("control", control_ncu),
            ):
                ncu_binary_hash = ncu_row.get("ncu_binary_sha256", "").strip()
                if not ncu_binary_hash:
                    reasons.append(f"missing_{role}_ncu_binary_sha256")
                elif ncu_binary_hash != energy_binary_hash:
                    reasons.append(f"{role}_ncu_binary_hash_mismatch")
                if (
                    ncu_row.get("ncu_binary_hash_capture", "").strip()
                    != "pre_post_collection_verified"
                ):
                    reasons.append(f"{role}_ncu_binary_provenance_not_verified")
                if require_quiescence and (
                    ncu_row.get("ncu_quiescence_status", "").strip()
                    not in ACCEPTED_NCU_QUIESCENCE_STATUSES
                ):
                    reasons.append(f"{role}_ncu_quiescence_not_verified")
        if (treatment_ncu is None or control_ncu is None) and not require_ncu:
            scale, denominator_source = 1.0, "logical_expected_unvalidated"
            ncu_treatment_denominator_observed = float("nan")
            ncu_control_denominator_observed = float("nan")
            ncu_incremental_denominator_observed = float("nan")
        else:
            (
                scale,
                denominator_source,
                ncu_treatment_denominator_observed,
                ncu_control_denominator_observed,
                ncu_incremental_denominator_observed,
            ) = ncu_denominator_scale(component, treatment_ncu, control_ncu)
        expected_denominator = as_float(treatment, str(config["expected_column"]))
        if component != "tensor":
            expected_denominator *= 8.0
        denominator = expected_denominator * scale
        if not math.isfinite(denominator) or denominator <= 0.0:
            reasons.append("invalid_denominator")

        treatment_energy = as_float(treatment, "net_E_J")
        control_energy = as_float(control, "net_E_J")
        treatment_elapsed = as_float(treatment, "elapsed_s")
        control_elapsed = as_float(control, "elapsed_s")
        if not math.isfinite(control_elapsed) or control_elapsed < min_control_elapsed_s:
            reasons.append("control_elapsed_below_minimum")
        if not math.isfinite(treatment_elapsed) or treatment_elapsed < min_treatment_elapsed_s:
            reasons.append("treatment_elapsed_below_minimum")
        completion_delta = treatment_energy - control_energy
        delta_t = treatment_elapsed - control_elapsed
        mi_atc_delta = completion_delta - baseline_power * delta_t
        control_active_power = (
            control_energy / control_elapsed
            if control_elapsed > 0.0 and math.isfinite(control_energy)
            else float("nan")
        )
        treatment_active_power = (
            treatment_energy / treatment_elapsed
            if treatment_elapsed > 0.0 and math.isfinite(treatment_energy)
            else float("nan")
        )
        delta_active_power = treatment_active_power - control_active_power
        control_rate_atc_delta = (
            treatment_energy - control_active_power * treatment_elapsed
            if math.isfinite(control_active_power)
            and math.isfinite(treatment_elapsed)
            else float("nan")
        )
        measurement_reasons = list(reasons)
        completion_reasons = list(measurement_reasons)
        if completion_delta <= 0.0:
            completion_reasons.append("nonpositive_completion_delta")
        mi_atc_reasons = list(measurement_reasons)
        if not math.isfinite(mi_atc_delta) or mi_atc_delta <= 0.0:
            mi_atc_reasons.append("nonpositive_mi_atc_delta")
        control_rate_atc_reasons = list(measurement_reasons)
        if not math.isfinite(control_rate_atc_delta) or control_rate_atc_delta <= 0.0:
            control_rate_atc_reasons.append("nonpositive_control_rate_atc_delta")
        measurement_valid = not measurement_reasons
        pair_valid = not completion_reasons
        mi_atc_valid = not mi_atc_reasons
        control_rate_atc_valid = not control_rate_atc_reasons
        regression_valid = measurement_valid

        completion_coefficient = coefficient(completion_delta, denominator, component)
        mi_atc_coefficient = coefficient(mi_atc_delta, denominator, component)
        control_rate_atc_coefficient = coefficient(
            control_rate_atc_delta, denominator, component
        )
        t_ncu = treatment_ncu or {}
        c_ncu = control_ncu or {}
        output.append(
            {
                "protocol_revision": treatment.get("protocol_revision", ""),
                "profile": treatment.get("profile", ""),
                "component": component,
                "coordinate_id": treatment.get("coordinate_id", ""),
                "pair_id": pair_id,
                "repeat": treatment.get("repeat", ""),
                "factor_kind": treatment.get("factor_kind", ""),
                "factor_value": treatment.get("factor_value", ""),
                "calibration_policy": treatment.get("calibration_policy", ""),
                "grid_anchor_factor": treatment.get("grid_anchor_factor", ""),
                "grid_anchor_blocks_per_sm": treatment.get(
                    "grid_anchor_blocks_per_sm", ""
                ),
                "grid_work_units": treatment.get("grid_work_units", ""),
                "target_duration_s": treatment.get("target_duration_s", ""),
                "execution_order": treatment.get("execution_order", ""),
                "blocks_per_SM": treatment.get("blocks_per_SM", ""),
                "active_SM": treatment.get("active_SM", ""),
                "quiescence_status": treatment.get("quiescence_status", ""),
                "cooldown_wait_seconds": treatment.get(
                    "cooldown_wait_seconds", ""
                ),
                "pre_pair_temp_C": treatment.get("pre_pair_temp_C", ""),
                "pre_pair_power_W": treatment.get("pre_pair_power_W", ""),
                "pre_pair_gpu_util_pct": treatment.get(
                    "pre_pair_gpu_util_pct", ""
                ),
                "pre_pair_memory_util_pct": treatment.get(
                    "pre_pair_memory_util_pct", ""
                ),
                "treatment_mode": treatment.get("mode", ""),
                "control_mode": control.get("mode", ""),
                "treatment_W_SM_KiB": treatment.get("W_SM_KiB", ""),
                "control_W_SM_KiB": control.get("W_SM_KiB", ""),
                "reuse_factor": treatment.get("reuse_factor", ""),
                "load_repeat": treatment.get("load_repeat", ""),
                "treatment_ITER": treatment.get("ITER", ""),
                "control_ITER": control.get("ITER", ""),
                "energy_binary_sha256": energy_binary_hash,
                "treatment_elapsed_s": treatment_elapsed,
                "control_elapsed_s": control_elapsed,
                "delta_t_s": delta_t,
                "treatment_net_E_J": treatment_energy,
                "control_net_E_J": control_energy,
                "delta_E_completion_J": completion_delta,
                "baseline_before_power_W": before_power,
                "baseline_after_power_W": after_power,
                "baseline_pair_power_W": baseline_power,
                "baseline_power_drift_pct": baseline_drift,
                "baseline_before_gap_ms": before_gap,
                "baseline_after_gap_ms": after_gap,
                "pair_transition_gap_ms": pair_gap,
                "delta_E_MI_ATC_J": mi_atc_delta,
                "control_active_power_W": control_active_power,
                "treatment_active_power_W": treatment_active_power,
                "delta_active_power_W": delta_active_power,
                "delta_E_control_rate_ATC_J": control_rate_atc_delta,
                "expected_denominator": expected_denominator,
                "ncu_treatment_denominator_observed": ncu_treatment_denominator_observed,
                "ncu_control_denominator_observed": ncu_control_denominator_observed,
                "ncu_incremental_denominator_observed": ncu_incremental_denominator_observed,
                "ncu_denominator_observed_unit": config["ncu_denominator_unit"],
                "ncu_denominator_scale": scale,
                "denominator": denominator,
                "denominator_source": denominator_source,
                "coefficient_unit": config["unit"],
                "completion_coefficient": completion_coefficient,
                "mi_atc_coefficient": mi_atc_coefficient,
                "control_rate_atc_coefficient": control_rate_atc_coefficient,
                "completion_signal_fraction": (
                    completion_delta / treatment_energy if treatment_energy > 0 else float("nan")
                ),
                "mi_atc_signal_fraction": (
                    mi_atc_delta / treatment_energy if treatment_energy > 0 else float("nan")
                ),
                "control_rate_atc_signal_fraction": (
                    control_rate_atc_delta / treatment_energy
                    if treatment_energy > 0
                    else float("nan")
                ),
                "treatment_ncu_label": t_ncu.get("label", ""),
                "control_ncu_label": c_ncu.get("label", ""),
                "treatment_ncu_acceptance": t_ncu.get("acceptance", "missing"),
                "control_ncu_acceptance": c_ncu.get("acceptance", "missing"),
                "treatment_ncu_binary_sha256": t_ncu.get("ncu_binary_sha256", ""),
                "control_ncu_binary_sha256": c_ncu.get("ncu_binary_sha256", ""),
                "treatment_ncu_binary_hash_capture": t_ncu.get(
                    "ncu_binary_hash_capture", ""
                ),
                "control_ncu_binary_hash_capture": c_ncu.get(
                    "ncu_binary_hash_capture", ""
                ),
                "treatment_ncu_quiescence_status": t_ncu.get(
                    "ncu_quiescence_status", ""
                ),
                "control_ncu_quiescence_status": c_ncu.get(
                    "ncu_quiescence_status", ""
                ),
                "treatment_tensor_hmma_inst": t_ncu.get("tensor_hmma_inst", ""),
                "treatment_tensor_fp16_f32_ops": t_ncu.get("tensor_fp16_f32_ops", ""),
                "treatment_shared_accesses": t_ncu.get("shared_accesses", ""),
                "treatment_shared_read_bytes": t_ncu.get("shared_read_bytes", ""),
                "treatment_l1_accesses": t_ncu.get("l1_accesses", ""),
                "treatment_l1_request_bytes": t_ncu.get("l1_request_bytes", ""),
                "treatment_l1_path_hit_rate_pct": t_ncu.get("l1_path_hit_rate_pct", ""),
                "treatment_l2_accesses": t_ncu.get("l2_accesses", ""),
                "treatment_l2_read_bytes": t_ncu.get("l2_read_bytes", ""),
                "treatment_l2_path_hit_rate_pct": t_ncu.get("l2_path_hit_rate_pct", ""),
                "treatment_l2_logical_read_hit_rate_pct": t_ncu.get("l2_logical_read_hit_rate_pct", ""),
                "treatment_dram_accesses": t_ncu.get("dram_accesses", ""),
                "treatment_dram_read_bytes": t_ncu.get("dram_read_bytes", ""),
                "treatment_stall_long_scoreboard_pct": t_ncu.get("stall_long_scoreboard_pct", ""),
                "control_stall_long_scoreboard_pct": c_ncu.get("stall_long_scoreboard_pct", ""),
                "measurement_valid": measurement_valid,
                "pair_valid": pair_valid,
                "mi_atc_valid": mi_atc_valid,
                "control_rate_atc_valid": control_rate_atc_valid,
                "regression_valid": regression_valid,
                "completion_diagnostic": ";".join(completion_reasons),
                "mi_atc_diagnostic": ";".join(mi_atc_reasons),
                "control_rate_atc_diagnostic": ";".join(
                    control_rate_atc_reasons
                ),
                "regression_diagnostic": ";".join(measurement_reasons),
                "diagnostic": ";".join(
                    sorted(
                        set(
                            completion_reasons
                            + mi_atc_reasons
                            + control_rate_atc_reasons
                        )
                    )
                ),
            }
        )
    return output


def invalid_reason_counts(rows: list[dict[str, Any]], valid_key: str) -> str:
    counts: dict[str, int] = defaultdict(int)
    diagnostic_key = {
        "pair_valid": "completion_diagnostic",
        "mi_atc_valid": "mi_atc_diagnostic",
        "control_rate_atc_valid": "control_rate_atc_diagnostic",
        "regression_valid": "regression_diagnostic",
    }.get(valid_key, "diagnostic")
    for row in rows:
        if row.get(valid_key):
            continue
        for reason in str(row.get(diagnostic_key, "") or "unknown").split(";"):
            if reason:
                counts[reason] += 1
    return ";".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def summarize_detail(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_component[str(row.get("component", ""))].append(row)
    for component, component_rows in sorted(by_component.items()):
        for method, valid_key, value_key in [
            ("matched_iter_completion", "pair_valid", "completion_coefficient"),
            ("mi_atc", "mi_atc_valid", "mi_atc_coefficient"),
            (
                "control_rate_atc",
                "control_rate_atc_valid",
                "control_rate_atc_coefficient",
            ),
        ]:
            measurement_valid_rows = [
                row
                for row in component_rows
                if bool(row.get("measurement_valid"))
                and math.isfinite(as_float(row, value_key))
            ]
            values = [as_float(row, value_key) for row in measurement_valid_rows]
            positive_rows = sum(value > 0.0 for value in values)
            positive_fraction = positive_rows / len(values) if values else 0.0
            low, high = bootstrap_median_ci(
                values, clusters=coordinate_clusters(measurement_valid_rows)
            )
            status = "accepted"
            if not values:
                status = "rejected_no_measurement_valid_rows"
            elif len(values) < 3:
                status = "diagnostic_only_insufficient_rows"
            elif not math.isfinite(low) or low <= 0.0:
                status = "rejected_signed_ci_includes_zero"
            elif positive_fraction < MIN_POSITIVE_FRACTION:
                status = "rejected_sign_instability"
            elif len(values) < 12:
                status = "accepted_with_caution_low_sample"
            if status.startswith("accepted"):
                subgroup_status = blocks_per_sm_subgroup_gate(
                    component_rows, value_key
                )
                if subgroup_status:
                    status = subgroup_status
            if status.startswith("accepted") and any(
                row.get("quiescence_status") != "strict_passed"
                for row in measurement_valid_rows
            ):
                status = "diagnostic_only_quiescence_unverified"
            output.append(
                {
                    "component": component,
                    "estimate_method": method,
                    "coefficient_unit": component_rows[0].get("coefficient_unit", ""),
                    "measurement_valid_rows": len(values),
                    "positive_rows": positive_rows,
                    "total_rows": len(component_rows),
                    "positive_fraction": positive_fraction,
                    "min": min(values) if values else float("nan"),
                    "median": median(values),
                    "mean": statistics.mean(values) if values else float("nan"),
                    "max": max(values) if values else float("nan"),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "bootstrap_ci_low": low,
                    "bootstrap_ci_high": high,
                    "status": status,
                    "invalid_reasons": invalid_reason_counts(component_rows, valid_key),
                }
            )
    return output


def blocks_per_sm_subgroup_gate(
    rows: list[dict[str, Any]], value_key: str
) -> str:
    grouped: dict[int, list[float]] = defaultdict(list)
    all_blocks = {as_int(row, "blocks_per_SM") for row in rows}
    for row in rows:
        value = as_float(row, value_key)
        if bool(row.get("measurement_valid")) and math.isfinite(value):
            grouped[as_int(row, "blocks_per_SM")].append(value)
    for blocks_per_sm in all_blocks:
        values = grouped.get(blocks_per_sm, [])
        if len(values) < 3:
            return "rejected_blocks_per_sm_insufficient_rows"
        positive_fraction = sum(value > 0.0 for value in values) / len(values)
        if median(values) <= 0.0 or positive_fraction < MIN_POSITIVE_FRACTION:
            return "rejected_blocks_per_sm_instability"
    return ""


def summarize_by_blocks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("component", "")), as_int(row, "blocks_per_SM"))].append(row)
    for (component, blocks_per_sm), component_rows in sorted(grouped.items()):
        for method, valid_key, value_key in [
            ("matched_iter_completion", "pair_valid", "completion_coefficient"),
            ("mi_atc", "mi_atc_valid", "mi_atc_coefficient"),
            (
                "control_rate_atc",
                "control_rate_atc_valid",
                "control_rate_atc_coefficient",
            ),
        ]:
            measurement_valid_rows = [
                row
                for row in component_rows
                if bool(row.get("measurement_valid"))
                and math.isfinite(as_float(row, value_key))
            ]
            values = [as_float(row, value_key) for row in measurement_valid_rows]
            positive_rows = sum(value > 0.0 for value in values)
            positive_fraction = positive_rows / len(values) if values else 0.0
            status = "accepted"
            if not values:
                status = "rejected_no_measurement_valid_rows"
            elif len(values) < 3:
                status = "diagnostic_only_insufficient_rows"
            elif median(values) <= 0.0:
                status = "rejected_signed_median_nonpositive"
            elif positive_fraction < MIN_POSITIVE_FRACTION:
                status = "rejected_sign_instability"
            if status == "accepted" and any(
                row.get("quiescence_status") != "strict_passed"
                for row in measurement_valid_rows
            ):
                status = "diagnostic_only_quiescence_unverified"
            output.append(
                {
                    "component": component,
                    "blocks_per_SM": blocks_per_sm,
                    "estimate_method": method,
                    "coefficient_unit": component_rows[0].get("coefficient_unit", ""),
                    "measurement_valid_rows": len(values),
                    "positive_rows": positive_rows,
                    "total_rows": len(component_rows),
                    "positive_fraction": positive_fraction,
                    "min": min(values) if values else float("nan"),
                    "median": median(values),
                    "mean": statistics.mean(values) if values else float("nan"),
                    "max": max(values) if values else float("nan"),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "status": status,
                    "invalid_reasons": invalid_reason_counts(component_rows, valid_key),
                }
            )
    return output


def summarize_tensor_rf_trends(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, int, float], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in rows:
        if row.get("component") != "tensor":
            continue
        grouped[
            (
                str(row.get("profile", "")),
                as_int(row, "blocks_per_SM"),
                as_int(row, "reuse_factor"),
                as_float(row, "target_duration_s"),
            )
        ].append(row)

    output: list[dict[str, Any]] = []
    for (profile, blocks, reuse, duration), group in sorted(grouped.items()):
        valid = [row for row in group if bool(row.get("measurement_valid"))]

        def values(field: str) -> list[float]:
            return finite(as_float(row, field) for row in valid)

        throughputs = [
            as_float(row, "denominator")
            / as_float(row, "treatment_elapsed_s")
            / 1.0e12
            for row in valid
            if as_float(row, "denominator") > 0.0
            and as_float(row, "treatment_elapsed_s") > 0.0
        ]
        operand = values("control_rate_atc_coefficient")
        positive_fraction = (
            sum(value > 0.0 for value in operand) / len(operand) if operand else 0.0
        )
        status = "accepted_for_trend"
        if len(valid) < 3:
            status = "diagnostic_low_sample"
        elif positive_fraction < MIN_POSITIVE_FRACTION:
            status = "reject_sign_instability"
        output.append(
            {
                "profile": profile,
                "blocks_per_SM": blocks,
                "reuse_factor": reuse,
                "target_duration_s": duration,
                "measurement_valid_rows": len(valid),
                "total_rows": len(group),
                "treatment_active_power_median_W": median(
                    values("treatment_active_power_W")
                ),
                "control_active_power_median_W": median(
                    values("control_active_power_W")
                ),
                "delta_active_power_median_W": median(
                    values("delta_active_power_W")
                ),
                "treatment_throughput_median_TFLOP_per_s": median(throughputs),
                "matched_iter_completion_median_pJ_per_FLOP": median(
                    values("completion_coefficient")
                ),
                "clocked_mi_atc_median_pJ_per_FLOP": median(
                    values("mi_atc_coefficient")
                ),
                "operand_rate_atc_median_pJ_per_FLOP": median(operand),
                "operand_rate_positive_fraction": positive_fraction,
                "interpretation_status": status,
            }
        )
    return output


def solve_least_squares(
    design: list[list[float]], target: list[float]
) -> list[float]:
    if not design or len(design) != len(target):
        raise ValueError("invalid fixed-effect design")
    width = len(design[0])
    if width == 0 or any(len(row) != width for row in design):
        raise ValueError("invalid fixed-effect design")
    normal = [
        [sum(row[i] * row[j] for row in design) for j in range(width)]
        + [sum(row[i] * value for row, value in zip(design, target))]
        for i in range(width)
    ]
    for column in range(width):
        pivot = max(range(column, width), key=lambda row: abs(normal[row][column]))
        if abs(normal[pivot][column]) <= 1.0e-12:
            raise ValueError("singular fixed-effect design")
        normal[column], normal[pivot] = normal[pivot], normal[column]
        scale = normal[column][column]
        normal[column] = [value / scale for value in normal[column]]
        for row in range(width):
            if row == column:
                continue
            factor = normal[row][column]
            if factor == 0.0:
                continue
            normal[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(normal[row], normal[column])
            ]
    return [normal[index][-1] for index in range(width)]


def fixed_effect_design(rows: list[dict[str, Any]]) -> list[list[float]]:
    def levels(field: str) -> list[str]:
        values = {str(row.get(field, "")) for row in rows}
        return sorted(
            values,
            key=lambda value: (
                0,
                float(value),
            )
            if value.replace(".", "", 1).isdigit()
            else (1, value),
        )

    categorical_fields = (
        "blocks_per_SM",
        "factor_value",
        "execution_order",
        "repeat",
    )
    field_levels = {field: levels(field) for field in categorical_fields}
    return [
        [1.0]
        + [
            float(str(row.get(field, "")) == value)
            for field in categorical_fields
            for value in field_levels[field][1:]
        ]
        for row in rows
    ]


def residualize(values: list[float], design: list[list[float]]) -> list[float]:
    coefficients = solve_least_squares(design, values)
    return [
        value - sum(weight * coefficient for weight, coefficient in zip(row, coefficients))
        for value, row in zip(values, design)
    ]


def fit_joint_model(rows: list[dict[str, Any]]) -> dict[str, float]:
    x = [as_float(row, "denominator") / 1.0e12 for row in rows]
    z = [as_float(row, "delta_t_s") for row in rows]
    y = [as_float(row, "delta_E_completion_J") for row in rows]
    if len(rows) < 3 or not all(math.isfinite(v) for v in x + z + y):
        raise ValueError("insufficient finite regression rows")
    fixed_design = fixed_effect_design(rows)
    dx = residualize(x, fixed_design)
    dz = residualize(z, fixed_design)
    dy = residualize(y, fixed_design)
    sxx = sum(value * value for value in dx)
    szz = sum(value * value for value in dz)
    sxz = sum(a * b for a, b in zip(dx, dz))
    sxy = sum(a * b for a, b in zip(dx, dy))
    szy = sum(a * b for a, b in zip(dz, dy))
    determinant = sxx * szz - sxz * sxz
    if sxx <= 0.0 or szz <= 0.0 or determinant <= 1.0e-18 * sxx * szz:
        raise ValueError("singular traffic/time predictors")
    beta_component = (sxy * szz - szy * sxz) / determinant
    beta_time = (szy * sxx - sxy * sxz) / determinant
    fixed_coefficients = solve_least_squares(
        fixed_design,
        [
            actual - beta_component * xv - beta_time * zv
            for actual, xv, zv in zip(y, x, z)
        ],
    )
    predictions = [
        sum(weight * coefficient for weight, coefficient in zip(row, fixed_coefficients))
        + beta_component * xv
        + beta_time * zv
        for row, xv, zv in zip(fixed_design, x, z)
    ]
    residuals = [actual - predicted for actual, predicted in zip(y, predictions)]
    ss_res = sum(value * value for value in residuals)
    my = statistics.mean(y)
    ss_tot = sum((value - my) ** 2 for value in y)
    correlation = sxz / math.sqrt(sxx * szz)
    if not math.isfinite(correlation) or abs(correlation) >= 1.0 - 1.0e-12:
        raise ValueError("singular traffic/time predictors")
    condition = (1.0 + abs(correlation)) / (1.0 - abs(correlation))
    degrees_of_freedom = len(rows) - len(fixed_design[0]) - 2
    return {
        "intercept": fixed_coefficients[0],
        "beta_component": beta_component,
        "beta_time": beta_time,
        "correlation": correlation,
        "condition": condition,
        "r_squared": 1.0 - ss_res / ss_tot if ss_tot > 0.0 else float("nan"),
        "residual_std": (
            math.sqrt(ss_res / degrees_of_freedom)
            if degrees_of_freedom > 0
            else float("nan")
        ),
        "fixed_effect_columns": float(len(fixed_design[0]) - 1),
    }


def regression_bootstrap_ci(
    rows: list[dict[str, Any]], *, samples: int = 1000, seed: int = 20260719
) -> tuple[float, float]:
    rng = random.Random(seed)
    coefficients: list[float] = []
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        cluster = str(row.get("coordinate_id", "")).strip() or f"row_{index}"
        clusters[cluster].append(row)
    cluster_names = sorted(clusters)
    for _ in range(samples):
        sampled_clusters = rng.choices(cluster_names, k=len(cluster_names))
        sample = [row for name in sampled_clusters for row in clusters[name]]
        try:
            fit = fit_joint_model(sample)
        except ValueError:
            continue
        coefficients.append(fit["beta_component"])
    if len(coefficients) < max(100, samples // 4):
        return float("nan"), float("nan")
    return percentile(coefficients, 0.025), percentile(coefficients, 0.975)


def build_regression_rows(
    detail_rows: list[dict[str, Any]],
    *,
    min_rows: int,
    max_predictor_correlation: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    present_components = {
        str(row.get("component", ""))
        for row in detail_rows
        if str(row.get("component", "")) in COMPONENT_CONFIG
    }
    for row in detail_rows:
        if row.get("regression_valid"):
            grouped[str(row.get("component", ""))].append(row)
    output: list[dict[str, Any]] = []
    for component in COMPONENT_CONFIG:
        if component not in present_components:
            continue
        rows = grouped.get(component, [])
        factors = {str(row.get("factor_value", "")) for row in rows}
        blocks = {str(row.get("blocks_per_SM", "")) for row in rows}
        durations = {str(row.get("target_duration_s", "")) for row in rows}
        execution_orders = {str(row.get("execution_order", "")) for row in rows}
        repeats = {str(row.get("repeat", "")) for row in rows}
        calibration_policies = {
            str(row.get("calibration_policy", "")) for row in rows
        }
        reasons: list[str] = []
        fit: dict[str, float] = {}
        low = high = float("nan")
        if len(rows) < min_rows:
            reasons.append("insufficient_rows")
        if len(factors) < 3:
            reasons.append("insufficient_factor_levels")
        if len(blocks) < 3:
            reasons.append("insufficient_blocks_per_sm_levels")
        if len(durations) < 2:
            reasons.append("insufficient_duration_levels")
        if len(execution_orders) < 2:
            reasons.append("insufficient_execution_order_levels")
        if len(repeats) < 3:
            reasons.append("insufficient_repeat_levels")
        if calibration_policies != {"factorial_grid"}:
            reasons.append("nonfactorial_calibration_policy")
        try:
            fit = fit_joint_model(rows)
            low, high = regression_bootstrap_ci(rows)
        except ValueError as exc:
            reasons.append(str(exc).replace(" ", "_"))
        if fit:
            if abs(fit["correlation"]) > max_predictor_correlation:
                reasons.append("traffic_time_collinearity")
            if fit["beta_component"] <= 0.0:
                reasons.append("nonpositive_component_coefficient")
            if not math.isfinite(low) or low <= 0.0:
                reasons.append("component_ci_includes_zero")
        status = "accepted" if not reasons else "not_identified"
        if status == "accepted" and any(
            row.get("quiescence_status") != "strict_passed" for row in rows
        ):
            status = "diagnostic_only_quiescence_unverified"
        output.append(
            {
                "component": component,
                "model": (
                    "delta_E=beta_component*traffic_or_ops_T+beta_time*delta_t+"
                    "C(blocks_per_SM)+C(factor_value)+C(execution_order)+C(repeat)"
                ),
                "coefficient_unit": COMPONENT_CONFIG[component]["unit"],
                "valid_rows": len(rows),
                "unique_factor_values": len(factors),
                "unique_blocks_per_sm_values": len(blocks),
                "unique_durations": len(durations),
                "unique_execution_orders": len(execution_orders),
                "unique_repeats": len(repeats),
                "fixed_effect_columns": fit.get("fixed_effect_columns", float("nan")),
                "predictor_correlation": fit.get("correlation", float("nan")),
                "standardized_condition_number": fit.get("condition", float("nan")),
                "intercept_J": fit.get("intercept", float("nan")),
                "component_coefficient": fit.get("beta_component", float("nan")),
                "component_coefficient_ci_low": low,
                "component_coefficient_ci_high": high,
                "time_coefficient_W": fit.get("beta_time", float("nan")),
                "r_squared": fit.get("r_squared", float("nan")),
                "residual_std_J": fit.get("residual_std", float("nan")),
                "status": status,
                "diagnostic": ";".join(reasons),
            }
        )
    return output


def build_ncu_evidence_rows(
    detail_rows: list[dict[str, Any]], ncu_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    accepted = accepted_ncu_map(ncu_rows)
    wanted: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    for detail in detail_rows:
        component = str(detail.get("component", ""))
        for role in ("treatment", "control"):
            mode = str(detail.get(f"{role}_mode", ""))
            w = str(detail.get(f"{role}_W_SM_KiB", ""))
            key = (
                mode,
                w,
                str(detail.get("blocks_per_SM", "")),
                str(detail.get("active_SM", "")),
                str(detail.get("reuse_factor", "1")),
                str(detail.get("load_repeat", "1")),
            )
            ncu_row = accepted.get(key)
            if ncu_row is not None:
                wanted[(component, role, key)] = ncu_row
    output: list[dict[str, Any]] = []
    metric_fields = [field for field in NCU_EVIDENCE_FIELDS if field not in {"component", "role"}]
    for (component, role, _), row in sorted(wanted.items()):
        out = {"component": component, "role": role}
        for field in metric_fields:
            out[field] = row.get(field, "")
        output.append(out)
    return output


def summarize_ncu_by_blocks(
    evidence_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = {
        "tensor": ("tensor_fp16_f32_ops", "", ""),
        "shared": ("shared_accesses", "shared_read_bytes", ""),
        "l1": ("l1_accesses", "l1_request_bytes", "l1_path_hit_rate_pct"),
        "l2": ("l2_accesses", "l2_read_bytes", "l2_logical_read_hit_rate_pct"),
        "external": ("dram_accesses", "dram_read_bytes", "l2_logical_read_hit_rate_pct"),
    }
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        if row.get("role") != "treatment" or row.get("acceptance") != "accepted":
            continue
        grouped[(str(row.get("component", "")), as_int(row, "blocks_per_SM"))].append(row)
    output: list[dict[str, Any]] = []
    for (component, blocks_per_sm), rows in sorted(grouped.items()):
        access_metric, bytes_metric, hit_metric = metrics.get(component, ("", "", ""))
        access_values = finite(as_float(row, access_metric) for row in rows) if access_metric else []
        if component == "tensor" and not access_values:
            access_metric = "tensor_hmma_inst"
            access_values = finite(as_float(row, access_metric) for row in rows)
        bytes_values = finite(as_float(row, bytes_metric) for row in rows) if bytes_metric else []
        hit_values: list[float] = []
        if hit_metric:
            for row in rows:
                value = as_float(row, hit_metric)
                if (
                    not math.isfinite(value)
                    and hit_metric == "l2_logical_read_hit_rate_pct"
                ):
                    value = as_float(row, "l2_path_hit_rate_pct")
                if math.isfinite(value):
                    hit_values.append(value)
        stall_values = finite(
            as_float(row, "stall_long_scoreboard_pct") for row in rows
        )
        output.append(
            {
                "component": component,
                "blocks_per_SM": blocks_per_sm,
                "accepted_treatment_rows": len(rows),
                "operation_or_access_metric": access_metric,
                "operation_or_access_median": median(access_values),
                "bytes_metric": bytes_metric,
                "bytes_median": median(bytes_values),
                "path_hit_rate_median_pct": median(hit_values),
                "long_scoreboard_median_pct": median(stall_values),
            }
        )
    return output


def write_csv(path: str, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def fmt(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.6g}" if math.isfinite(number) else "-"


def write_report(
    path: str,
    detail_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    subgroup_rows: list[dict[str, Any]],
    regression_rows: list[dict[str, Any]],
    ncu_evidence_rows: list[dict[str, Any]],
    ncu_by_blocks_rows: list[dict[str, Any]],
    tensor_rf_trend_rows: list[dict[str, Any]],
    figure_prefix: str = "",
    figure_relative_dir: str = "../assets/component_energy_method",
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        profiles = sorted(
            {str(row.get("profile", "")) for row in detail_rows if row.get("profile")}
        )
        protocols = sorted(
            {
                str(row.get("protocol_revision", ""))
                for row in detail_rows
                if row.get("protocol_revision")
            }
        )
        profile_names = {
            "rtx3090": "RTX 3090",
            "v100": "V100",
            "a100": "A100",
            "h100": "H100",
        }
        profile_label = ", ".join(
            profile_names.get(profile, profile) for profile in profiles
        )
        title_prefix = f"{profile_label} " if profile_label else ""
        handle.write(f"# {title_prefix}Component 동적 에너지 귀속 결과\n\n")
        if profiles:
            handle.write(f"- profile: `{', '.join(profiles)}`\n")
        if protocols:
            handle.write(f"- protocol: `{', '.join(protocols)}`\n")
        if profiles or protocols:
            handle.write("\n")
        handle.write(
            "동일 ITER 완료는 직접 관측값이고 MI-ATC 및 공동회귀는 모델값이다. "
            "어느 값도 순수 silicon-level component energy가 아니다.\n\n"
        )
        energy_quiescence = {
            str(row.get("quiescence_status", "")) for row in detail_rows
        }
        ncu_quiescence_observed = {
            str(row.get("treatment_ncu_quiescence_status", ""))
            for row in detail_rows
            if row.get("treatment_ncu_quiescence_status")
        } | {
            str(row.get("control_ncu_quiescence_status", ""))
            for row in detail_rows
            if row.get("control_ncu_quiescence_status")
        }
        repeat_levels = {str(row.get("repeat", "")) for row in detail_rows}
        diagnostic_reasons: list[str] = []
        if energy_quiescence != {"strict_passed"}:
            diagnostic_reasons.append(
                "energy quiescence=" + ",".join(sorted(energy_quiescence))
            )
        if ncu_quiescence_observed and not ncu_quiescence_observed.issubset(
            ACCEPTED_NCU_QUIESCENCE_STATUSES
        ):
            diagnostic_reasons.append(
                "NCU quiescence=" + ",".join(sorted(ncu_quiescence_observed))
            )
        if len(repeat_levels) < 3:
            diagnostic_reasons.append(
                f"repeat levels={len(repeat_levels)} (required 3)"
            )
        if diagnostic_reasons:
            handle.write(
                "> **Overall status: diagnostic only.** "
                + "; ".join(diagnostic_reasons)
                + ". 이 package의 수치를 final coefficient로 승격하지 않는다.\n\n"
            )
        measurement_valid_count = sum(
            bool(row.get("measurement_valid")) for row in detail_rows
        )
        ncu_component_rows = [
            row
            for row in ncu_evidence_rows
            if str(row.get("role", "")) in {"control", "treatment"}
        ]
        ncu_accepted_count = sum(
            str(row.get("acceptance", "")) == "accepted"
            for row in ncu_component_rows
        )
        invalid_reason_counts: dict[str, int] = defaultdict(int)
        for row in detail_rows:
            if row.get("measurement_valid"):
                continue
            for reason in str(row.get("diagnostic", "")).split(";"):
                if reason:
                    invalid_reason_counts[reason] += 1
        accepted_outputs = sum(
            str(row.get("status", "")) == "accepted" for row in summary_rows
        ) + sum(
            str(row.get("status", "")) == "accepted" for row in regression_rows
        )
        invalid_reason_text = (
            ", ".join(
                f"{reason}:{count}"
                for reason, count in sorted(invalid_reason_counts.items())
            )
            or "none"
        )
        handle.write("## 실행 및 채택 판정\n\n")
        handle.write("| Gate | Result | Interpretation |\n")
        handle.write("|---|---:|---|\n")
        handle.write(
            f"| explicit treatment-control pairs | {len(detail_rows)}/{len(detail_rows)} | "
            "manifest pair 구조 완료 |\n"
        )
        handle.write(
            f"| energy measurement gate | {measurement_valid_count}/{len(detail_rows)} | "
            f"invalid: `{invalid_reason_text}` |\n"
        )
        handle.write(
            f"| NCU treatment/control path | {ncu_accepted_count}/{len(ncu_component_rows)} | "
            f"quiescence: `{','.join(sorted(ncu_quiescence_observed)) or 'not_available'}` |\n"
        )
        handle.write(
            f"| accepted final estimator | {accepted_outputs} | "
            "0이면 수치를 final coefficient로 인용하지 않음 |\n\n"
        )
        pair_state_specs = (
            ("cooldown wait", "cooldown_wait_seconds", "s"),
            ("temperature", "pre_pair_temp_C", "degC"),
            ("power", "pre_pair_power_W", "W"),
            ("GPU utilization", "pre_pair_gpu_util_pct", "%"),
            ("memory-controller utilization", "pre_pair_memory_util_pct", "%"),
        )
        pair_state_rows: list[tuple[str, str, list[float]]] = []
        for label, field, unit in pair_state_specs:
            values = finite(as_float(row, field) for row in detail_rows)
            if values:
                pair_state_rows.append((label, unit, values))
        if pair_state_rows:
            handle.write("## Pair 시작 상태\n\n")
            handle.write(
                "각 treatment-control pair 직전에 runner가 관찰한 값이다. "
                "이 표는 pre-run quiescence audit을 대체하지 않으며, "
                "`quiescence_status=skipped`이면 final acceptance 증거가 아니다.\n\n"
            )
            handle.write("| Metric | Min | Median | Max | Unit |\n")
            handle.write("|---|---:|---:|---:|---|\n")
            for label, unit, values in pair_state_rows:
                handle.write(
                    f"| {label} | {fmt(min(values))} | {fmt(median(values))} | "
                    f"{fmt(max(values))} | {unit} |\n"
                )
            handle.write("\n")
        if figure_prefix:
            figure_root = figure_relative_dir.rstrip("/")
            handle.write("## 결과 시각화\n\n")
            handle.write(
                f"![계수 방법 비교]({figure_root}/{figure_prefix}_coefficient_methods.png)\n\n"
            )
            sweep_alt = (
                "Tensor RF 및 blocks/SM sweep"
                if {str(row.get("component", "")) for row in detail_rows}
                == {"tensor"}
                else "RF/LR 및 blocks/SM sweep"
            )
            handle.write(
                f"![{sweep_alt}]({figure_root}/{figure_prefix}_parameter_sweep.png)\n\n"
            )
            if tensor_rf_trend_rows:
                handle.write(
                    f"![Tensor RF-duration 민감도]({figure_root}/{figure_prefix}_tensor_rf_duration.png)\n\n"
                )
            evidence_components = {
                str(row.get("component", "")) for row in ncu_evidence_rows
            }
            if "tensor" in evidence_components:
                handle.write(
                    f"![Tensor NCU 검증]({figure_root}/{figure_prefix}_tensor_ncu_evidence.png)\n\n"
                )
            if evidence_components & {"shared", "l1", "l2", "external"}:
                handle.write(
                    f"![Memory-path NCU 검증]({figure_root}/{figure_prefix}_ncu_path_evidence.png)\n\n"
                )
        handle.write("## Parameter sweep과 선택 좌표\n\n")
        handle.write(
            "| Component | Treatment - control | Calibration | blocks/SM [blocks/SM] | "
            "W control -> treatment [KiB/SM] | Sweep factor [count] | "
            "Target duration [s] | Repeats [count] |\n"
        )
        handle.write("|---|---|---|---:|---:|---|---|---:|\n")
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in detail_rows:
            grouped[str(row.get("component", ""))].append(row)
        for component in COMPONENT_CONFIG:
            rows = grouped.get(component, [])
            if not rows:
                continue
            first = rows[0]

            def numeric_values(field: str) -> str:
                values = sorted(
                    {as_float(row, field) for row in rows if math.isfinite(as_float(row, field))}
                )
                return ", ".join(fmt(value) for value in values)

            factor_kind = str(first.get("factor_kind", ""))
            factor_label = "RF" if factor_kind == "reuse_factor" else "LR"
            handle.write(
                f"| `{component}` | `{first.get('treatment_mode', '')}` - "
                f"`{first.get('control_mode', '')}` | "
                f"`{first.get('calibration_policy', '') or 'unrecorded'}` | "
                f"{numeric_values('blocks_per_SM')} | "
                f"{first.get('control_W_SM_KiB', '')} -> "
                f"{first.get('treatment_W_SM_KiB', '')} | "
                f"{factor_label}={numeric_values('factor_value')} | "
                f"{numeric_values('target_duration_s')} | "
                f"{len({str(row.get('repeat', '')) for row in rows})} |\n"
            )
        handle.write("\n")
        handle.write("## 직접 차분과 활성시간 보정\n\n")
        handle.write(
            "`control_rate_atc`는 Tensor에서 operand-rate ATC와 같은 식이다. "
            "control의 단위시간당 net energy를 treatment 시간까지 확장해 제거하므로 "
            "control 상태가 treatment의 no-component 반사실을 잘 근사할 때만 유효하다.\n\n"
        )
        handle.write(
            "| Component | Method | measurement-valid/total | positive/measurement-valid | "
            "Signed median | 95% bootstrap CI | Unit | Status |\n"
        )
        handle.write("|---|---|---:|---:|---:|---:|---|---|\n")
        for row in summary_rows:
            handle.write(
                f"| `{row['component']}` | `{row['estimate_method']}` | "
                f"{row['measurement_valid_rows']}/{row['total_rows']} | "
                f"{row['positive_rows']}/{row['measurement_valid_rows']} | "
                f"{fmt(row['median'])} | "
                f"{fmt(row['bootstrap_ci_low'])}-{fmt(row['bootstrap_ci_high'])} | "
                f"{row['coefficient_unit']} | `{row['status']}` |\n"
            )
        handle.write("\n## blocks/SM별 분포\n\n")
        handle.write(
            "| Component | B [blocks/SM] | Method | measurement-valid/total | "
            "positive/measurement-valid | Signed min | Signed median | Signed mean | "
            "Signed max | Unit | Status |\n"
        )
        handle.write("|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|\n")
        for row in subgroup_rows:
            handle.write(
                f"| `{row['component']}` | {row['blocks_per_SM']} | "
                f"`{row['estimate_method']}` | "
                f"{row['measurement_valid_rows']}/{row['total_rows']} | "
                f"{row['positive_rows']}/{row['measurement_valid_rows']} | "
                f"{fmt(row['min'])} | {fmt(row['median'])} | {fmt(row['mean'])} | "
                f"{fmt(row['max'])} | {row['coefficient_unit']} | `{row['status']}` |\n"
            )
        if tensor_rf_trend_rows:
            handle.write("\n## Tensor RF-duration 원인 분해\n\n")
            handle.write(
                "RF가 커져도 pJ/FLOP이 반드시 감소하지 않는다. 장시간 steady loop에서는 "
                "초기 fragment 준비 비용이 이미 충분히 상각되고, 아래 계수는 주로 "
                "treatment-control 전력 차와 실효 처리율의 비로 결정된다.\n\n"
            )
            handle.write(
                "| B [blocks/SM] | RF [count] | duration [s] | valid/total | "
                "treatment/control/delta power [W] | throughput [TFLOP/s] | "
                "Direct | Clocked MI-ATC | Operand-rate ATC [pJ/FLOP] | Status |\n"
            )
            handle.write("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
            for row in tensor_rf_trend_rows:
                handle.write(
                    f"| {row['blocks_per_SM']} | {row['reuse_factor']} | "
                    f"{fmt(row['target_duration_s'])} | "
                    f"{row['measurement_valid_rows']}/{row['total_rows']} | "
                    f"{fmt(row['treatment_active_power_median_W'])}/"
                    f"{fmt(row['control_active_power_median_W'])}/"
                    f"{fmt(row['delta_active_power_median_W'])} | "
                    f"{fmt(row['treatment_throughput_median_TFLOP_per_s'])} | "
                    f"{fmt(row['matched_iter_completion_median_pJ_per_FLOP'])} | "
                    f"{fmt(row['clocked_mi_atc_median_pJ_per_FLOP'])} | "
                    f"{fmt(row['operand_rate_atc_median_pJ_per_FLOP'])} | "
                    f"`{row['interpretation_status']}` |\n"
                )
        handle.write("\n## Bytes/FLOP-time 공동회귀\n\n")
        handle.write(
            "| Component | Rows | Factor/B/duration/order/repeat levels | Coefficient | 95% CI | "
            "time beta (W) | corr | R2 | Status |\n"
        )
        handle.write("|---|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for row in regression_rows:
            identified = row["status"] in {
                "accepted",
                "diagnostic_only_quiescence_unverified",
            }
            coefficient_text = (
                f"{fmt(row['component_coefficient'])} {row['coefficient_unit']}"
                if identified
                else "not identified"
            )
            ci_text = (
                f"{fmt(row['component_coefficient_ci_low'])}-"
                f"{fmt(row['component_coefficient_ci_high'])}"
                if identified
                else "-"
            )
            handle.write(
                f"| `{row['component']}` | {row['valid_rows']} | "
                f"{row['unique_factor_values']}/"
                f"{row['unique_blocks_per_sm_values']}/"
                f"{row['unique_durations']}/"
                f"{row['unique_execution_orders']}/"
                f"{row['unique_repeats']} | "
                f"{coefficient_text} | {ci_text} | "
                f"{fmt(row['time_coefficient_W'])} | "
                f"{fmt(row['predictor_correlation'])} | {fmt(row['r_squared'])} | "
                f"`{row['status']}` |\n"
            )
        energy_hashes = sorted(
            {
                str(row.get("energy_binary_sha256", ""))
                for row in detail_rows
                if row.get("energy_binary_sha256")
            }
        )
        ncu_hashes = sorted(
            {
                str(row.get("treatment_ncu_binary_sha256", ""))
                for row in detail_rows
                if row.get("treatment_ncu_binary_sha256")
            }
            | {
                str(row.get("control_ncu_binary_sha256", ""))
                for row in detail_rows
                if row.get("control_ncu_binary_sha256")
            }
        )
        ncu_captures = sorted(
            {
                str(row.get("treatment_ncu_binary_hash_capture", ""))
                for row in detail_rows
                if row.get("treatment_ncu_binary_hash_capture")
            }
            | {
                str(row.get("control_ncu_binary_hash_capture", ""))
                for row in detail_rows
                if row.get("control_ncu_binary_hash_capture")
            }
        )
        ncu_quiescence = sorted(
            {
                str(row.get("treatment_ncu_quiescence_status", ""))
                for row in detail_rows
                if row.get("treatment_ncu_quiescence_status")
            }
            | {
                str(row.get("control_ncu_quiescence_status", ""))
                for row in detail_rows
                if row.get("control_ncu_quiescence_status")
            }
        )
        binary_identity_status = (
            "verified"
            if len(energy_hashes) == 1
            and energy_hashes == ncu_hashes
            and ncu_captures == ["pre_post_collection_verified"]
            else "not_verified"
        )
        handle.write("\n## Binary provenance\n\n")
        handle.write("| Evidence | Value |\n|---|---|\n")
        handle.write(f"| energy SHA-256 | `{', '.join(energy_hashes)}` |\n")
        handle.write(f"| NCU SHA-256 | `{', '.join(ncu_hashes)}` |\n")
        handle.write(f"| NCU hash capture | `{', '.join(ncu_captures)}` |\n")
        handle.write(f"| NCU quiescence | `{', '.join(ncu_quiescence)}` |\n")
        handle.write(f"| energy/NCU binary identity | `{binary_identity_status}` |\n")
        handle.write("\n## blocks/SM별 NCU 경로 요약\n\n")
        handle.write(
            "| Component | B [blocks/SM] | Rows | Operation/access median | "
            "Bytes median [B] | Path hit [%] | Long scoreboard |\n"
        )
        handle.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for row in ncu_by_blocks_rows:
            access = (
                f"{row['operation_or_access_metric']}={fmt(row['operation_or_access_median'])}"
                if row.get("operation_or_access_metric")
                else "-"
            )
            handle.write(
                f"| `{row['component']}` | {row['blocks_per_SM']} | "
                f"{row['accepted_treatment_rows']} | {access} | "
                f"{fmt(row['bytes_median'])} | {fmt(row['path_hit_rate_median_pct'])} | "
                f"{fmt(row['long_scoreboard_median_pct'])} |\n"
            )
        handle.write("\n## NCU 경로와 분모 원본 증거\n\n")
        handle.write(
            "| Component | Role/mode | NCU status | Ops | Shared access/bytes | L1 access/bytes/hit | "
            "L2 access/bytes/hit | External access/bytes | Long scoreboard |\n"
        )
        handle.write("|---|---|---|---:|---:|---:|---:|---:|---:|\n")
        for row in ncu_evidence_rows:
            ops = row.get("tensor_fp16_f32_ops") or row.get("tensor_hmma_inst", "")
            handle.write(
                f"| `{row['component']}` | {row['role']}/`{row['mode']}` | "
                f"`{row.get('acceptance', '')}` | {ops} | "
                f"{row.get('shared_accesses', '')}/{row.get('shared_read_bytes', '')} | "
                f"{row.get('l1_accesses', '')}/{row.get('l1_request_bytes', '')}/"
                f"{row.get('l1_path_hit_rate_pct', '')}% | "
                f"{row.get('l2_accesses', '')}/{row.get('l2_read_bytes', '')}/"
                f"{row.get('l2_logical_read_hit_rate_pct') or row.get('l2_path_hit_rate_pct', '')}% | "
                f"{row.get('dram_accesses', '')}/{row.get('dram_read_bytes', '')} | "
                f"{row.get('stall_long_scoreboard_pct', '')} |\n"
            )
        handle.write("\n## 해석 규칙\n\n")
        handle.write(
            "- Direct/MI-ATC/control-rate ATC min/median/mean/max/CI는 measurement gate를 통과한 signed row "
            "전체를 사용한다. CI는 coordinate 단위 cluster bootstrap이며 음수 row를 "
            "제외한 양수 조건부 coefficient를 보고하지 않는다.\n"
            "- `positive/measurement-valid < 0.8`이면 부호 불안정으로 reject하고 "
            "음수를 0으로 잘라내지 않는다. 전체가 통과해도 각 blocks/SM subgroup이 "
            "같은 부호 gate를 통과하지 못하면 단일 전체값을 reject한다.\n"
            "- 공동회귀는 blocks/SM, RF/LR, execution order, repeat 고정효과와 "
            "coordinate-cluster bootstrap을 사용한다.\n"
            "- Tensor MI-ATC는 동적 MMA 경로의 surrogate이며 RF/scheduler switching이 남는다.\n"
            "- Tensor control-rate ATC는 operand-rate ATC다. RF별 control power와 treatment "
            "throughput이 함께 변하므로 RF ordering을 silicon Tensor energy ordering으로 "
            "직접 해석하지 않는다.\n"
            "- Shared/Global L1은 직접 차분과 MI-ATC를 유지하고 공동회귀가 식별될 때만 "
            "회귀 계수를 추가 채택한다.\n"
            "- L2와 External은 address-only가 아니라 각각 Global-L1과 L2의 인접 계층 "
            "control을 사용한다.\n"
            "- External 결과는 memory controller와 PHY/link를 포함하며 physical DRAM-only "
            "energy가 아니다.\n"
            "- `stall_long_scoreboard_pct`는 전체 실행시간 중 stall 비율이 아니라 "
            "issue-active 기준 stalled warp 정규화값이다. 여러 warp가 동시에 대기하면 "
            "100%를 넘을 수 있으므로 단순 시간 비율로 읽지 않는다.\n"
        )


def self_test() -> None:
    manifest: list[dict[str, str]] = []
    common = {
        "protocol_revision": PROTOCOL_REVISION,
        "profile": "rtx3090",
        "component": "tensor",
        "coordinate_id": "tensor_RF4_D4_B8",
        "pair_id": "pair0",
        "repeat": "0",
        "execution_order": "control_then_treatment",
        "target_duration_s": "4",
        "factor_kind": "reuse_factor",
        "factor_value": "4",
        "calibration_policy": "factorial_grid",
        "grid_anchor_factor": "4",
        "grid_anchor_blocks_per_sm": "8",
        "grid_work_units": "40",
        "blocks_per_SM": "8",
        "active_SM": "82",
        "reuse_factor": "4",
        "load_repeat": "1",
        "binary_sha256": "abc",
        "quiescence_status": "strict_passed",
        "gpu_id": "0",
        "smid_histogram_ok": "true",
        "energy_source": "nvml_total_energy",
        "measurement_scope": "gpu_device_total_energy_counter",
        "FLOP": "10000000000000",
    }
    role_rows = [
        ("baseline_before", "clocked_empty", "64", "1", 0, 2000, 2, 100),
        ("control", "reg_operand_only", "1", "10", 2100, 4100, 2, 100),
        ("treatment", "reg_mma", "1", "10", 4200, 8200, 4, 220),
        ("baseline_after", "clocked_empty", "64", "1", 8300, 10300, 2, 100),
    ]
    for index, (role, mode, w, iters, start, end, elapsed, energy) in enumerate(role_rows):
        manifest.append(
            {
                **common,
                "role": role,
                "mode": mode,
                "W_SM_KiB": w,
                "ITER": iters,
                "measurement_start_epoch_ms": str(start),
                "measurement_end_epoch_ms": str(end),
                "elapsed_s": str(elapsed),
                "net_E_J": str(energy),
                "sequence_index": str(index),
            }
        )
    ncu = [
        {
            "label": "control",
            "mode": "reg_operand_only",
            "W_SM_KiB": "1",
            "blocks_per_SM": "8",
            "active_SM": "82",
            "reuse_factor": "4",
            "load_repeat": "1",
            "status": "ok",
            "acceptance": "accepted",
            "ncu_binary_sha256": "abc",
            "ncu_binary_hash_capture": "pre_post_collection_verified",
            "ncu_quiescence_status": "strict_passed",
            "tensor_fp16_f32_ops": "0",
        },
        {
            "label": "treatment",
            "mode": "reg_mma",
            "W_SM_KiB": "1",
            "blocks_per_SM": "8",
            "active_SM": "82",
            "reuse_factor": "4",
            "load_repeat": "1",
            "status": "ok",
            "acceptance": "accepted",
            "ncu_binary_sha256": "abc",
            "ncu_binary_hash_capture": "pre_post_collection_verified",
            "ncu_quiescence_status": "strict_passed",
            "tensor_hmma_inst": "1000",
            "tensor_fp16_f32_ops": "10000000000000",
            "expected_logical_flop": "10000000000000",
        },
    ]
    detail = build_detail_rows(
        manifest,
        ncu,
        max_pair_gap_ms=30000,
        max_baseline_gap_ms=45000,
        max_baseline_drift_pct=10,
        min_control_elapsed_s=0.1,
        min_treatment_elapsed_s=1.0,
        require_ncu=True,
        require_quiescence=True,
    )
    assert len(detail) == 1
    assert (
        detail[0]["pair_valid"]
        and detail[0]["mi_atc_valid"]
        and detail[0]["control_rate_atc_valid"]
    )
    assert detail[0]["ncu_denominator_observed_unit"] == "FLOP"
    assert math.isclose(detail[0]["ncu_incremental_denominator_observed"], 1.0e13)
    assert detail[0]["denominator_source"] == "ncu_incremental_actual_exact_coordinate"
    bad_hash_ncu = [dict(row) for row in ncu]
    bad_hash_ncu[1]["ncu_binary_sha256"] = "different"
    bad_hash_detail = build_detail_rows(
        manifest,
        bad_hash_ncu,
        max_pair_gap_ms=30000,
        max_baseline_gap_ms=45000,
        max_baseline_drift_pct=10,
        min_control_elapsed_s=0.1,
        min_treatment_elapsed_s=1.0,
        require_ncu=True,
        require_quiescence=True,
    )
    assert not bad_hash_detail[0]["measurement_valid"]
    assert "treatment_ncu_binary_hash_mismatch" in bad_hash_detail[0]["diagnostic"]
    skipped_quiescence_ncu = [dict(row) for row in ncu]
    skipped_quiescence_ncu[0]["ncu_quiescence_status"] = "skipped"
    skipped_quiescence_detail = build_detail_rows(
        manifest,
        skipped_quiescence_ncu,
        max_pair_gap_ms=30000,
        max_baseline_gap_ms=45000,
        max_baseline_drift_pct=10,
        min_control_elapsed_s=0.1,
        min_treatment_elapsed_s=1.0,
        require_ncu=True,
        require_quiescence=True,
    )
    assert not skipped_quiescence_detail[0]["measurement_valid"]
    assert "control_ncu_quiescence_not_verified" in skipped_quiescence_detail[0]["diagnostic"]
    diagnostic_quiescence_detail = build_detail_rows(
        manifest,
        skipped_quiescence_ncu,
        max_pair_gap_ms=30000,
        max_baseline_gap_ms=45000,
        max_baseline_drift_pct=10,
        min_control_elapsed_s=0.1,
        min_treatment_elapsed_s=1.0,
        require_ncu=True,
        require_quiescence=False,
    )
    assert diagnostic_quiescence_detail[0]["measurement_valid"]
    counter_scope_ncu = [dict(row) for row in ncu]
    for row in counter_scope_ncu:
        row["ncu_quiescence_status"] = "counter_scope_passed"
    counter_scope_detail = build_detail_rows(
        manifest,
        counter_scope_ncu,
        max_pair_gap_ms=30000,
        max_baseline_gap_ms=45000,
        max_baseline_drift_pct=10,
        min_control_elapsed_s=0.1,
        min_treatment_elapsed_s=1.0,
        require_ncu=True,
        require_quiescence=True,
    )
    assert counter_scope_detail[0]["measurement_valid"]
    assert math.isclose(detail[0]["completion_coefficient"], 12.0)
    assert math.isclose(detail[0]["mi_atc_coefficient"], 2.0)
    assert math.isclose(detail[0]["control_rate_atc_coefficient"], 2.0)
    single_summary = summarize_detail(detail)
    assert all(
        row["status"] == "diagnostic_only_insufficient_rows"
        for row in single_summary
    )
    assert math.isclose(coefficient(8.0, 8.0e12, "shared"), 1.0)
    subgroup = summarize_by_blocks(detail)
    assert len(subgroup) == 3
    assert all(row["blocks_per_SM"] == 8 for row in subgroup)
    tensor_only_regression = build_regression_rows(
        detail,
        min_rows=12,
        max_predictor_correlation=0.98,
    )
    assert [row["component"] for row in tensor_only_regression] == ["tensor"]
    signed_probe: list[dict[str, Any]] = []
    for value in (-4.0, -3.0, 1.0, 2.0):
        positive = value > 0.0
        signed_probe.append(
            {
                "component": "tensor",
                "coefficient_unit": "pJ/FLOP",
                "blocks_per_SM": 8,
                "quiescence_status": "strict_passed",
                "measurement_valid": True,
                "pair_valid": positive,
                "mi_atc_valid": positive,
                "control_rate_atc_valid": positive,
                "completion_coefficient": value,
                "mi_atc_coefficient": value,
                "control_rate_atc_coefficient": value,
                "completion_diagnostic": "" if positive else "nonpositive_completion_delta",
                "mi_atc_diagnostic": "" if positive else "nonpositive_mi_atc_delta",
                "control_rate_atc_diagnostic": (
                    "" if positive else "nonpositive_control_rate_atc_delta"
                ),
            }
        )
    signed_summary = summarize_detail(signed_probe)
    assert all(row["measurement_valid_rows"] == 4 for row in signed_summary)
    assert all(row["positive_rows"] == 2 for row in signed_summary)
    assert all(math.isclose(row["median"], -1.0) for row in signed_summary)
    assert all(row["status"].startswith("rejected_signed") for row in signed_summary)
    subgroup_probe: list[dict[str, Any]] = []
    subgroup_values = (
        (4, tuple(1.0 + 0.01 * index for index in range(12))),
        (16, (-0.2, -0.1, 0.1)),
    )
    for blocks_per_sm, values in subgroup_values:
        for value in values:
            subgroup_probe.append(
                {
                    "component": "tensor",
                    "coefficient_unit": "pJ/FLOP",
                    "blocks_per_SM": blocks_per_sm,
                    "quiescence_status": "strict_passed",
                    "measurement_valid": True,
                    "pair_valid": value > 0.0,
                    "mi_atc_valid": value > 0.0,
                    "control_rate_atc_valid": value > 0.0,
                    "completion_coefficient": value,
                    "mi_atc_coefficient": value,
                    "control_rate_atc_coefficient": value,
                    "completion_diagnostic": "",
                    "mi_atc_diagnostic": "",
                }
            )
    subgroup_summary = summarize_detail(subgroup_probe)
    assert all(
        row["status"] == "rejected_blocks_per_sm_instability"
        for row in subgroup_summary
    )
    expected_ncu = 82 * 8 * 100 * 4 * 1024
    denominator_probe = {
        "active_SM": "82",
        "blocks_per_SM": "8",
        "ITER": "100",
        "load_repeat": "4",
        "l2_read_bytes": str(expected_ncu * 0.99),
    }
    denominator_control = {
        **denominator_probe,
        "l2_read_bytes": str(expected_ncu * 0.01),
    }
    scale, source, _, _, incremental = ncu_denominator_scale(
        "l2", denominator_probe, denominator_control
    )
    assert math.isclose(scale, 0.98)
    assert source == "ncu_incremental_actual_exact_coordinate"
    assert math.isclose(incremental, expected_ncu * 0.98)
    duplicate_profiles = [
        {
            "label": "minimal_duplicate",
            "mode": "global_addr_only",
            "W_SM_KiB": "16",
            "blocks_per_SM": "8",
            "active_SM": "82",
            "reuse_factor": "1",
            "load_repeat": "4",
            "status": "ok",
            "acceptance": "accepted",
            "ncu_metric_profile": "l2_path_minimal",
        },
        {
            "label": "full_preferred",
            "mode": "global_addr_only",
            "W_SM_KiB": "16",
            "blocks_per_SM": "8",
            "active_SM": "82",
            "reuse_factor": "1",
            "load_repeat": "4",
            "status": "ok",
            "acceptance": "accepted",
            "ncu_metric_profile": "full",
        },
    ]
    selected = accepted_ncu_map(duplicate_profiles)
    assert next(iter(selected.values()))["label"] == "full_preferred"
    ncu_group = summarize_ncu_by_blocks(
        [
            {
                "component": "l2",
                "role": "treatment",
                "acceptance": "accepted",
                "blocks_per_SM": "8",
                "l2_accesses": "4",
                "l2_read_bytes": "128",
                "l2_logical_read_hit_rate_pct": "99",
                "stall_long_scoreboard_pct": "10",
            },
            {
                "component": "l2",
                "role": "treatment",
                "acceptance": "accepted",
                "blocks_per_SM": "8",
                "l2_accesses": "6",
                "l2_read_bytes": "192",
                "l2_logical_read_hit_rate_pct": "100",
                "stall_long_scoreboard_pct": "12",
            },
        ]
    )
    assert len(ncu_group) == 1
    assert math.isclose(ncu_group[0]["operation_or_access_median"], 5.0)
    assert math.isclose(ncu_group[0]["bytes_median"], 160.0)
    synthetic = []
    for index in range(12):
        x = 1.0 + index * 0.3
        z = 0.2 + (index % 3) * 0.4
        synthetic.append(
            {
                "denominator": x * 1.0e12,
                "delta_t_s": z,
                "delta_E_completion_J": 1.0 + 2.0 * x + 3.0 * z,
            }
        )
    fit = fit_joint_model(synthetic)
    assert math.isclose(fit["beta_component"], 2.0, rel_tol=1e-9)
    assert math.isclose(fit["beta_time"], 3.0, rel_tol=1e-9)
    fixed_effect_probe: list[dict[str, Any]] = []
    for block_index, blocks in enumerate((4, 8, 16)):
        for factor_index, factor in enumerate((1, 4, 16)):
            for duration in (1.0, 2.0, 3.0):
                for repeat in range(3):
                    for order_index, execution_order in enumerate(
                        ("control_then_treatment", "treatment_then_control")
                    ):
                        work = duration
                        delta_t = (
                            duration * (0.5 + 0.2 * block_index)
                            + 0.1 * factor_index
                            + 0.03 * repeat
                            + 0.05 * order_index
                        )
                        fixed_effect_probe.append(
                            {
                                "blocks_per_SM": blocks,
                                "factor_value": factor,
                                "execution_order": execution_order,
                                "repeat": repeat,
                                "denominator": work * 1.0e12,
                                "delta_t_s": delta_t,
                                "delta_E_completion_J": (
                                    100.0 * block_index
                                    + 10.0 * factor_index
                                    + 7.0 * order_index
                                    + 5.0 * repeat
                                    + 2.0 * work
                                    + 3.0 * delta_t
                                ),
                            }
                        )
    fixed_effect_fit = fit_joint_model(fixed_effect_probe)
    assert math.isclose(fixed_effect_fit["beta_component"], 2.0, rel_tol=1e-9)
    assert math.isclose(fixed_effect_fit["beta_time"], 3.0, rel_tol=1e-9)
    assert fixed_effect_fit["fixed_effect_columns"] == 7.0
    collinear = [
        {
            "denominator": float(index + 1) * 1.0e12,
            "delta_t_s": float(index + 1),
            "delta_E_completion_J": float(index + 1),
        }
        for index in range(4)
    ]
    try:
        fit_joint_model(collinear)
    except ValueError:
        pass
    else:
        raise AssertionError("collinear traffic/time predictors were accepted")
    print("component dynamic-attribution analyzer self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        help="manifest CSV; repeat the option to combine disjoint component pilots",
    )
    parser.add_argument("--ncu-acceptance", default="")
    parser.add_argument("--allow-missing-ncu", action="store_true")
    parser.add_argument("--allow-unverified-quiescence", action="store_true")
    parser.add_argument("--max-pair-gap-ms", type=float, default=30000.0)
    parser.add_argument("--max-baseline-gap-ms", type=float, default=45000.0)
    parser.add_argument("--max-baseline-drift-pct", type=float, default=10.0)
    parser.add_argument("--min-control-elapsed-s", type=float, default=0.1)
    parser.add_argument("--min-treatment-elapsed-s", type=float, default=1.0)
    parser.add_argument("--min-regression-rows", type=int, default=12)
    parser.add_argument("--max-predictor-correlation", type=float, default=0.98)
    parser.add_argument("--out-detail", default="results/summary/component_dynamic_attribution_detail.csv")
    parser.add_argument("--out-summary", default="results/summary/component_dynamic_attribution_summary.csv")
    parser.add_argument("--out-subgroups", default="results/summary/component_dynamic_attribution_by_blocks.csv")
    parser.add_argument("--out-regression", default="results/summary/component_dynamic_attribution_regression.csv")
    parser.add_argument("--out-ncu-evidence", default="results/summary/component_dynamic_attribution_ncu_evidence.csv")
    parser.add_argument("--out-ncu-by-blocks", default="results/summary/component_dynamic_attribution_ncu_by_blocks.csv")
    parser.add_argument(
        "--out-tensor-rf-trends",
        default="results/summary/component_dynamic_attribution_tensor_rf_trends.csv",
    )
    parser.add_argument("--out-report", default="results/summary/component_dynamic_attribution_report.md")
    parser.add_argument(
        "--figure-prefix",
        default="",
        help="embed plot links in the Markdown report using this filename prefix",
    )
    parser.add_argument(
        "--figure-relative-dir",
        default="../assets/component_energy_method",
        help="report-relative directory containing generated figures",
    )
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.manifest:
        parser.error("--manifest is required")
    if not args.ncu_acceptance and not args.allow_missing_ncu:
        parser.error("--ncu-acceptance is required unless --allow-missing-ncu is set")
    manifest_rows: list[dict[str, str]] = []
    for manifest_path in args.manifest:
        manifest_rows.extend(read_csv(manifest_path))
    ncu_rows = read_csv(args.ncu_acceptance) if args.ncu_acceptance else []
    detail_rows = build_detail_rows(
        manifest_rows,
        ncu_rows,
        max_pair_gap_ms=args.max_pair_gap_ms,
        max_baseline_gap_ms=args.max_baseline_gap_ms,
        max_baseline_drift_pct=args.max_baseline_drift_pct,
        min_control_elapsed_s=args.min_control_elapsed_s,
        min_treatment_elapsed_s=args.min_treatment_elapsed_s,
        require_ncu=not args.allow_missing_ncu,
        require_quiescence=not args.allow_unverified_quiescence,
    )
    summary_rows = summarize_detail(detail_rows)
    subgroup_rows = summarize_by_blocks(detail_rows)
    regression_rows = build_regression_rows(
        detail_rows,
        min_rows=args.min_regression_rows,
        max_predictor_correlation=args.max_predictor_correlation,
    )
    evidence_rows = build_ncu_evidence_rows(detail_rows, ncu_rows)
    ncu_by_blocks_rows = summarize_ncu_by_blocks(evidence_rows)
    tensor_rf_trend_rows = summarize_tensor_rf_trends(detail_rows)
    write_csv(args.out_detail, DETAIL_FIELDS, detail_rows)
    write_csv(args.out_summary, SUMMARY_FIELDS, summary_rows)
    write_csv(args.out_subgroups, SUBGROUP_FIELDS, subgroup_rows)
    write_csv(args.out_regression, REGRESSION_FIELDS, regression_rows)
    write_csv(args.out_ncu_evidence, NCU_EVIDENCE_FIELDS, evidence_rows)
    write_csv(args.out_ncu_by_blocks, NCU_BY_BLOCKS_FIELDS, ncu_by_blocks_rows)
    write_csv(
        args.out_tensor_rf_trends,
        TENSOR_RF_TREND_FIELDS,
        tensor_rf_trend_rows,
    )
    write_report(
        args.out_report,
        detail_rows,
        summary_rows,
        subgroup_rows,
        regression_rows,
        evidence_rows,
        ncu_by_blocks_rows,
        tensor_rf_trend_rows,
        args.figure_prefix,
        args.figure_relative_dir,
    )
    print(f"wrote detail: {args.out_detail}")
    print(f"wrote summary: {args.out_summary}")
    print(f"wrote blocks/SM subgroups: {args.out_subgroups}")
    print(f"wrote regression: {args.out_regression}")
    print(f"wrote NCU evidence: {args.out_ncu_evidence}")
    print(f"wrote NCU blocks/SM summary: {args.out_ncu_by_blocks}")
    print(f"wrote Tensor RF trends: {args.out_tensor_rf_trends}")
    print(f"wrote report: {args.out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
