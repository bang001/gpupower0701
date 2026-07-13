#!/usr/bin/env python3
"""Analyze component runs with matched treatment/control rows.

Shared/Global-L1 paths can use elapsed-aware control-power scaling. Tensor, L2,
and DRAM finalplan rows can instead require pair-locked ITER and directly
subtract the two net energies, so different calibrated work counts cannot
masquerade as component energy.

The output is an effective microbenchmark energy estimate. It is not a pure
physical SRAM/register/DRAM bitcell energy.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


PAIR_SPECS = [
    {
        "component": "register_operand_control",
        "pair": "reg_operand_only_minus_clocked_empty",
        "numerator_mode": "reg_operand_only",
        "control_mode": "clocked_empty",
        "denominator_column": "expected_reg_operand_ops",
        "unit": "pJ/reg-op",
    },
    {
        "component": "tensor_mma_increment",
        "pair": "reg_mma_minus_reg_operand_only",
        "numerator_mode": "reg_mma",
        "control_mode": "reg_operand_only",
        "denominator_column": "FLOP",
        "unit": "pJ/FLOP",
    },
    {
        "component": "tensor_register_path",
        "pair": "reg_mma_minus_clocked_empty",
        "numerator_mode": "reg_mma",
        "control_mode": "clocked_empty",
        "denominator_column": "FLOP",
        "unit": "pJ/FLOP",
    },
    {
        "component": "shared_l1_scalar_path",
        "pair": "shared_scalar_load_only_minus_clocked_empty",
        "numerator_mode": "shared_scalar_load_only",
        "control_mode": "clocked_empty",
        "denominator_column": "expected_shared_bytes",
        "unit": "pJ/byte",
    },
    {
        "component": "global_l1_hit_path",
        "pair": "global_l1_load_only_minus_global_addr_only",
        "numerator_mode": "global_l1_load_only",
        "control_mode": "global_addr_only",
        "denominator_column": "expected_l1_bytes",
        "unit": "pJ/byte",
    },
    {
        "component": "l2_hit_cg_path",
        "pair": "l2_cg_load_only_minus_global_addr_only",
        "numerator_mode": "l2_cg_load_only",
        "control_mode": "global_addr_only",
        "denominator_column": "expected_l2_bytes",
        "unit": "pJ/byte",
    },
    {
        "component": "dram_cg_stream_path",
        "pair": "dram_cg_load_only_minus_global_addr_only",
        "numerator_mode": "dram_cg_load_only",
        "control_mode": "global_addr_only",
        "denominator_column": "expected_dram_bytes",
        "unit": "pJ/byte",
    },
]

MEMORY_PATH_MODES = {
    "shared_scalar_load_only",
    "shared_load_only",
    "global_l1_load_only",
    "global_addr_only",
    "l2_cg_load_only",
    "l2_load_only",
    "dram_cg_load_only",
    "dram_load_only",
}

TENSOR_REGISTER_MODES = {
    "reg_mma",
    "reg_operand_only",
    "reg_fragment_only",
    "reg_pressure",
}


CONTROL_MODES = {"clocked_empty"}
NCU_VALIDATED_CONTROL_MODES = {"reg_operand_only", "global_addr_only"}
LOGICAL_OPERAND_BITS_PER_REG_OP = 8192.0


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def is_active_row(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=1" in notes:
        return True
    if "gpu_active=0" in notes:
        return False
    return as_float(row, "n_gpu_active") > 0.0


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def safe_stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def quantile(values: list[float], q: float) -> float:
    finite = sorted(v for v in values if math.isfinite(v))
    if not finite:
        return float("nan")
    if len(finite) == 1:
        return finite[0]
    pos = (len(finite) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return finite[lo]
    weight = pos - lo
    return finite[lo] * (1.0 - weight) + finite[hi] * weight


def median_abs_deviation(values: list[float]) -> float:
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return float("nan")
    med = statistics.median(finite)
    return statistics.median([abs(v - med) for v in finite])


def bootstrap_median_ci(
    values: list[float],
    *,
    iterations: int = 2000,
    seed: int = 20260708,
) -> tuple[float, float]:
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return float("nan"), float("nan")
    if len(finite) == 1:
        return finite[0], finite[0]
    rng = random.Random(seed)
    n = len(finite)
    medians = []
    for _ in range(iterations):
        sample = [finite[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    return quantile(medians, 0.025), quantile(medians, 0.975)


def relative_width(low: float, high: float, center: float) -> float:
    if center == 0.0 or not all(math.isfinite(v) for v in [low, high, center]):
        return float("nan")
    return abs(high - low) / abs(center)


def confidence_class(n: int, rel_iqr: float, rel_ci: float) -> str:
    if n >= 9 and rel_iqr <= 0.5 and rel_ci <= 0.75:
        return "medium-high"
    if n >= 6 and rel_iqr <= 1.0 and rel_ci <= 1.5:
        return "medium"
    return "low"


def config_key(row: dict[str, str]) -> tuple[str, ...]:
    """Pairing key; ITER is validated separately for pair-locked components."""

    return (
        row.get("profile_name") or row.get("target_profile") or "",
        row.get("gpu_id", ""),
        row.get("n_gpu_active", ""),
        row.get("W_SM_KiB", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
        row.get("reuse_factor", "1"),
        row.get("load_repeat", "1"),
        row.get("store_repeat", "1"),
    )


def read_rows(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    row_index = 0
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                row = dict(row)
                row["_source_file"] = path
                row["_row_index"] = str(row_index)
                row["_run_order"] = str(run_order(row, row_index))
                rows.append(row)
                row_index += 1
    return rows


def run_order(row: dict[str, str], default: int | None = None) -> int:
    run_id = row.get("run_id", "")
    try:
        return int(run_id.rsplit("_", 2)[-2])
    except (IndexError, ValueError):
        if default is not None:
            return default
        return int(as_float(row, "_row_index", 0.0))


def measurement_interval_ms(row: dict[str, str]) -> tuple[float, float, str]:
    """Return the benchmark interval, with a legacy best-effort fallback.

    Current binaries write exact epoch timestamps around the timed kernel. Old
    CSVs only have a run_id timestamp emitted after measurement, so their start
    is estimated by subtracting elapsed_s. The fallback intentionally remains
    available so already-collected A100/V100 rows can be reanalyzed.
    """

    start = as_float(row, "measurement_start_epoch_ms", float("nan"))
    end = as_float(row, "measurement_end_epoch_ms", float("nan"))
    if math.isfinite(start) and math.isfinite(end) and start > 0.0 and end >= start:
        return start, end, "exact_epoch_interval"

    completion = float(run_order(row))
    elapsed_ms = max(0.0, as_float(row, "elapsed_s") * 1000.0)
    return completion - elapsed_ms, completion, "legacy_run_id_elapsed_inferred"


def pair_timing_ms(
    numerator: dict[str, str], control: dict[str, str]
) -> tuple[float, float, str, str]:
    """Return completion distance, transition gap, timing source, and pair order."""

    numerator_start, numerator_end, numerator_source = measurement_interval_ms(
        numerator
    )
    control_start, control_end, control_source = measurement_interval_ms(control)
    if numerator_start >= control_end:
        transition_gap = numerator_start - control_end
        execution_order = "control_then_treatment"
    elif control_start >= numerator_end:
        transition_gap = control_start - numerator_end
        execution_order = "treatment_then_control"
    else:
        transition_gap = 0.0
        execution_order = "overlapping_intervals"
    timing_source = (
        numerator_source
        if numerator_source == control_source
        else f"mixed:{numerator_source}+{control_source}"
    )
    return (
        abs(float(run_order(numerator)) - float(run_order(control))),
        transition_gap,
        timing_source,
        execution_order,
    )


def normalized_key_value(value: str, default: str = "") -> str:
    if value == "":
        return default
    try:
        parsed = float(value)
    except ValueError:
        return value
    if not math.isfinite(parsed):
        return default
    rounded = round(parsed)
    if abs(parsed - rounded) < 1.0e-9:
        return str(int(rounded))
    return f"{parsed:g}"


def exact_config_key(row: dict[str, str]) -> tuple[str, ...]:
    mode = row.get("mode", "")
    reuse_factor = normalized_key_value(row.get("reuse_factor", "1"), "1")
    load_repeat = normalized_key_value(row.get("load_repeat", "1"), "1")
    store_repeat = normalized_key_value(row.get("store_repeat", "1"), "1")

    if mode in MEMORY_PATH_MODES:
        reuse_factor = "*"
        store_repeat = "*"
    elif mode in TENSOR_REGISTER_MODES:
        load_repeat = "*"
        store_repeat = "*"

    return (
        mode,
        normalized_key_value(row.get("W_SM_KiB", "")),
        normalized_key_value(row.get("blocks_per_SM", "")),
        normalized_key_value(row.get("active_SM", "")),
        reuse_factor,
        load_repeat,
        store_repeat,
    )


def working_set_config_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("mode", ""),
        normalized_key_value(row.get("W_SM_KiB", "")),
        normalized_key_value(row.get("blocks_per_SM", "")),
        normalized_key_value(row.get("active_SM", "")),
    )


def read_acceptance(
    paths: list[str],
) -> tuple[set[str], dict[str, set[tuple[str, ...]]]]:
    if not paths:
        return set(), {}
    accepted: set[str] = set()
    accepted_keys_by_mode: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                if row.get("acceptance") == "accepted":
                    mode = row.get("mode", "")
                    accepted.add(mode)
                    accepted_keys_by_mode[mode].add(exact_config_key(row))
    return accepted, accepted_keys_by_mode


def read_power_state_audit(paths: list[str]) -> dict[str, dict[str, str]]:
    """Read power-state row quality by run_id.

    The power-state audit is generated from the same raw rows. `run_id` is more
    stable than CSV line number when one analyzer reads multiple input files.
    """

    by_run_id: dict[str, dict[str, str]] = {}
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                run_id = row.get("run_id", "")
                if not run_id:
                    continue
                by_run_id[run_id] = {
                    "status": row.get("status", ""),
                    "coefficient_eligible": row.get("coefficient_eligible", ""),
                    "reasons": row.get("reasons", ""),
                    "notes": row.get("notes", ""),
                    "audit_file": path,
                }
    return by_run_id


def attach_power_state_audit(
    rows: list[dict[str, str]], audit_by_run_id: dict[str, dict[str, str]]
) -> None:
    for row in rows:
        audit = audit_by_run_id.get(row.get("run_id", ""))
        if not audit:
            continue
        row["_power_state_status"] = audit.get("status", "")
        row["_power_state_coefficient_eligible"] = audit.get(
            "coefficient_eligible", ""
        )
        row["_power_state_reasons"] = audit.get("reasons", "")
        row["_power_state_notes"] = audit.get("notes", "")
        row["_power_state_audit_file"] = audit.get("audit_file", "")


def ncu_expected_bytes(row: dict[str, str]) -> float:
    return (
        as_float(row, "active_SM")
        * as_float(row, "blocks_per_SM")
        * as_float(row, "ITER")
        * as_float(row, "load_repeat", 1.0)
        * 1024.0
    )


def read_ncu_denominator_scales(
    paths: list[str],
) -> tuple[dict[tuple[str, ...], tuple[float, float]], dict[tuple[str, ...], tuple[float, float]]]:
    exact: dict[tuple[str, ...], tuple[float, float]] = {}
    same_working_set: dict[tuple[str, ...], tuple[float, float]] = {}
    actual_columns_by_mode = {
        "shared_scalar_load_only": ["shared_bytes"],
        "shared_load_only": ["shared_bytes"],
        "global_l1_load_only": ["l1_request_bytes", "l1_bytes"],
        "l2_cg_load_only": ["l2_read_bytes", "l2_bytes"],
        "l2_load_only": ["l2_read_bytes", "l2_bytes"],
        "dram_cg_load_only": ["dram_bytes"],
        "dram_load_only": ["dram_bytes"],
    }
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                mode = row.get("mode", "")
                actual_columns = actual_columns_by_mode.get(mode)
                if not actual_columns or row.get("status") != "ok":
                    continue
                expected = ncu_expected_bytes(row)
                actual = 0.0
                for actual_column in actual_columns:
                    actual = as_float(row, actual_column)
                    if actual > 0.0:
                        break
                if expected <= 0.0 or actual <= 0.0:
                    continue
                scale = actual / expected
                exact[exact_config_key(row)] = (scale, actual)
                same_working_set[working_set_config_key(row)] = (scale, actual)
    return exact, same_working_set


def ncu_scale_for_row(
    row: dict[str, str],
    *,
    exact_scales: dict[tuple[str, ...], tuple[float, float]],
    same_working_set_scales: dict[tuple[str, ...], tuple[float, float]],
) -> tuple[float, str, float]:
    mode = row.get("mode", "")
    exact_key = exact_config_key(row)
    if exact_key in exact_scales:
        scale, actual = exact_scales[exact_key]
        return scale, "ncu_actual_exact", actual
    working_set_key = working_set_config_key(row)
    if working_set_key in same_working_set_scales:
        scale, actual = same_working_set_scales[working_set_key]
        return scale, "ncu_actual_same_working_set", actual
    return 1.0, "expected_no_ncu_match", 0.0


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def measurement_scope(row: dict[str, str]) -> str:
    raw_scope = row.get("measurement_scope", "")
    if raw_scope:
        return raw_scope
    if (
        row.get("energy_source", "") == "nvml_total_energy"
        and row.get("energy_integration_method", "") == "total_energy_mj_delta"
    ):
        return "gpu_device_total_energy_counter"
    if (
        row.get("energy_source", "") == "legacy_get_power_usage_integral"
        or row.get("energy_integration_method", "") == "endpoint_power_trapezoid"
    ):
        return "gpu_device_power_usage_fallback"
    return ""


def row_ok(
    row: dict[str, str],
    *,
    min_elapsed_s: float,
    require_total_energy: bool,
    expected_power_semantics: str,
    exclude_power_state_rejects: bool,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if not is_active_row(row):
        reasons.append("inactive_gpu")
    if row.get("smid_histogram_ok", "").lower() != "true":
        reasons.append("smid_histogram_not_ok")
    if as_float(row, "elapsed_s") < min_elapsed_s:
        reasons.append("elapsed_too_short")
    if as_float(row, "net_E_J") <= 0.0:
        reasons.append("nonpositive_net_energy")
    energy_source = row.get("energy_source", "")
    integration = row.get("energy_integration_method", "")
    if require_total_energy:
        if not truthy(row.get("nvml_total_energy_supported", "")):
            reasons.append("nvml_total_energy_not_supported")
        if energy_source != "nvml_total_energy":
            reasons.append("energy_source_not_total_energy")
        if integration != "total_energy_mj_delta":
            reasons.append("integration_not_total_energy_delta")
        scope = measurement_scope(row)
        if scope != "gpu_device_total_energy_counter":
            reasons.append("measurement_scope_not_gpu_device_total_energy_counter")
    elif energy_source == "legacy_get_power_usage_integral":
        reasons.append("power_usage_fallback_provisional")
    if expected_power_semantics:
        semantics = row.get("nvml_power_usage_semantics", "")
        if semantics and semantics != expected_power_semantics:
            reasons.append(f"power_semantics_not_{expected_power_semantics}")
    if exclude_power_state_rejects and row.get("_power_state_status", ""):
        power_state_status = row.get("_power_state_status", "")
        coefficient_eligible = row.get("_power_state_coefficient_eligible", "")
        if power_state_status == "reject" or (
            coefficient_eligible and not truthy(coefficient_eligible)
        ):
            reasons.append("power_state_reject")
    return (not reasons, ";".join(reasons))


def coefficient(delta_j: float, denominator: float, unit: str) -> float:
    if denominator <= 0.0:
        return float("nan")
    if unit.startswith("pJ/"):
        return delta_j * 1.0e12 / denominator
    return delta_j / denominator


def summarize_coefficients(values: list[float]) -> dict[str, float]:
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return {
            "n": 0.0,
            "min": float("nan"),
            "median": float("nan"),
            "mean": float("nan"),
            "max": float("nan"),
            "stdev": float("nan"),
        }
    return {
        "n": float(len(finite)),
        "min": min(finite),
        "median": statistics.median(finite),
        "mean": statistics.mean(finite),
        "max": max(finite),
        "stdev": safe_stdev(finite),
    }


def make_detail_rows(
    rows: list[dict[str, str]],
    *,
    accepted_modes: set[str],
    accepted_keys_by_mode: dict[str, set[tuple[str, ...]]],
    exact_ncu_scales: dict[tuple[str, ...], tuple[float, float]],
    same_working_set_ncu_scales: dict[tuple[str, ...], tuple[float, float]],
    min_elapsed_s: float,
    tensor_control_min_elapsed_s: float,
    l2_control_min_elapsed_s: float,
    dram_control_min_elapsed_s: float,
    max_elapsed_ratio: float,
    max_pair_transition_gap_ms: float,
    min_delta_j: float,
    min_delta_fraction: float,
    require_ncu_denominator: bool,
    require_total_energy: bool,
    expected_power_semantics: str,
    exclude_power_state_rejects: bool,
    pairing: str,
    tensor_pair_policy: str,
    l2_pair_policy: str,
    dram_pair_policy: str,
    require_control_ncu_acceptance: bool,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        grouped[config_key(row)][row.get("mode", "")].append(row)

    detail_rows: list[dict[str, Any]] = []
    for key, by_mode in grouped.items():
        for spec in PAIR_SPECS:
            numerator_mode = spec["numerator_mode"]
            control_mode = spec["control_mode"]
            if accepted_modes and numerator_mode not in accepted_modes:
                continue
            if control_mode not in by_mode or numerator_mode not in by_mode:
                continue

            numerator_rows = by_mode[numerator_mode]
            control_rows = by_mode[control_mode]
            num_ok_rows = []
            ctl_ok_rows = []
            for row in numerator_rows:
                ok, _ = row_ok(
                    row,
                    min_elapsed_s=min_elapsed_s,
                    require_total_energy=require_total_energy,
                    expected_power_semantics=expected_power_semantics,
                    exclude_power_state_rejects=exclude_power_state_rejects,
                )
                if ok:
                    num_ok_rows.append(row)
            for row in control_rows:
                control_min_elapsed = (
                    tensor_control_min_elapsed_s
                    if spec["component"] == "tensor_mma_increment"
                    and tensor_pair_policy == "matched-iters"
                    else l2_control_min_elapsed_s
                    if spec["component"] == "l2_hit_cg_path"
                    and l2_pair_policy == "matched-iters"
                    else dram_control_min_elapsed_s
                    if spec["component"] == "dram_cg_stream_path"
                    and dram_pair_policy == "matched-iters"
                    else min_elapsed_s
                )
                ok, _ = row_ok(
                    row,
                    min_elapsed_s=control_min_elapsed,
                    require_total_energy=require_total_energy,
                    expected_power_semantics=expected_power_semantics,
                    exclude_power_state_rejects=exclude_power_state_rejects,
                )
                if ok:
                    ctl_ok_rows.append(row)
            if not num_ok_rows or not ctl_ok_rows:
                continue

            accepted_keys = accepted_keys_by_mode.get(numerator_mode, set())
            if accepted_keys:
                num_ok_rows = [
                    row for row in num_ok_rows if exact_config_key(row) in accepted_keys
                ]
                if not num_ok_rows:
                    continue

            control_acceptance_required = (
                require_control_ncu_acceptance
                and control_mode in NCU_VALIDATED_CONTROL_MODES
            )
            control_accepted_keys = accepted_keys_by_mode.get(control_mode, set())
            if control_acceptance_required:
                ctl_ok_rows = [
                    row
                    for row in ctl_ok_rows
                    if exact_config_key(row) in control_accepted_keys
                ]
                if not ctl_ok_rows:
                    continue

            if pairing == "nearest-control":
                row_pairs = [
                    (
                        numerator,
                        min(
                            ctl_ok_rows,
                            key=lambda row: abs(
                                run_order(row) - run_order(numerator)
                            ),
                        ),
                    )
                    for numerator in num_ok_rows
                ]
            else:
                numerator = sorted(num_ok_rows, key=lambda r: as_float(r, "net_E_J"))[
                    len(num_ok_rows) // 2
                ]
                control = sorted(ctl_ok_rows, key=lambda r: as_float(r, "net_E_J"))[
                    len(ctl_ok_rows) // 2
                ]
                row_pairs = [(numerator, control)]

            for numerator, control in row_pairs:
                numerator_elapsed = as_float(numerator, "elapsed_s")
                control_elapsed = as_float(control, "elapsed_s")
                numerator_energy = as_float(numerator, "net_E_J")
                control_energy = as_float(control, "net_E_J")
                numerator_iters = as_float(numerator, "ITER")
                control_iters = as_float(control, "ITER")
                control_power = (
                    control_energy / control_elapsed if control_elapsed > 0.0 else 0.0
                )
                pair_energy_basis = "duration_scaled_control_power"
                matched_iter_component = (
                    spec["component"] == "tensor_mma_increment"
                    and tensor_pair_policy == "matched-iters"
                ) or (
                    spec["component"] == "l2_hit_cg_path"
                    and l2_pair_policy == "matched-iters"
                ) or (
                    spec["component"] == "dram_cg_stream_path"
                    and dram_pair_policy == "matched-iters"
                )
                if matched_iter_component:
                    pair_energy_basis = "matched_iters_net_energy"
                    control_energy_scaled = control_energy
                else:
                    control_energy_scaled = control_power * numerator_elapsed
                delta_j = numerator_energy - control_energy_scaled
                signal_reference_j = max(numerator_energy, control_energy_scaled)
                delta_fraction = (
                    delta_j / signal_reference_j if signal_reference_j > 0.0 else 0.0
                )
                denominator = as_float(numerator, spec["denominator_column"])
                denominator_scale = 1.0
                denominator_source = "logical_or_expected"
                ncu_denominator_bytes = 0.0
                if spec["unit"] == "pJ/byte":
                    (
                        denominator_scale,
                        denominator_source,
                        ncu_denominator_bytes,
                    ) = ncu_scale_for_row(
                        numerator,
                        exact_scales=exact_ncu_scales,
                        same_working_set_scales=same_working_set_ncu_scales,
                    )
                    denominator *= denominator_scale
                coeff = coefficient(delta_j, denominator, spec["unit"])
                elapsed_ratio = (
                    max(numerator_elapsed, control_elapsed)
                    / min(numerator_elapsed, control_elapsed)
                    if min(numerator_elapsed, control_elapsed) > 0.0
                    else float("inf")
                )
                (
                    pair_completion_distance_ms,
                    pair_transition_gap_ms,
                    pair_timing_source,
                    pair_execution_order,
                ) = pair_timing_ms(numerator, control)
                # Compatibility field for older consumers. This is a completion
                # timestamp distance and was historically misnamed as a start
                # distance; it is no longer used as the adjacency gate.
                pair_start_distance_ms = pair_completion_distance_ms

                numerator_start_ms, numerator_end_ms, _ = measurement_interval_ms(
                    numerator
                )
                control_start_ms, control_end_ms, _ = measurement_interval_ms(
                    control
                )

                reasons: list[str] = []
                if pair_execution_order == "overlapping_intervals":
                    reasons.append("pair_measurement_intervals_overlap")
                if (
                    pairing == "nearest-control"
                    and max_pair_transition_gap_ms > 0.0
                    and pair_transition_gap_ms > max_pair_transition_gap_ms
                ):
                    reasons.append(
                        "pair_transition_gap_ms>"
                        f"{max_pair_transition_gap_ms:g}"
                    )
                if (
                    pair_energy_basis == "duration_scaled_control_power"
                    and elapsed_ratio > max_elapsed_ratio
                ):
                    reasons.append(f"elapsed_ratio>{max_elapsed_ratio:g}")
                if pair_energy_basis == "matched_iters_net_energy":
                    if (
                        not math.isfinite(numerator_iters)
                        or not math.isfinite(control_iters)
                        or numerator_iters <= 0.0
                        or control_iters <= 0.0
                    ):
                        reasons.append("missing_pair_locked_iters")
                    elif int(numerator_iters) != int(control_iters):
                        mismatch_reason = {
                            "tensor_mma_increment": "tensor_iter_mismatch",
                            "l2_hit_cg_path": "l2_iter_mismatch",
                            "dram_cg_stream_path": "dram_iter_mismatch",
                        }[spec["component"]]
                        reasons.append(mismatch_reason)
                if numerator.get("energy_source", "") != control.get("energy_source", ""):
                    reasons.append("energy_source_mismatch")
                if numerator.get("energy_integration_method", "") != control.get(
                    "energy_integration_method", ""
                ):
                    reasons.append("energy_integration_method_mismatch")
                if numerator.get("nvml_power_usage_semantics", "") != control.get(
                    "nvml_power_usage_semantics", ""
                ):
                    reasons.append("power_semantics_mismatch")
                if measurement_scope(numerator) != measurement_scope(control):
                    reasons.append("measurement_scope_mismatch")
                if denominator <= 0.0:
                    reasons.append("nonpositive_denominator")
                if (
                    require_ncu_denominator
                    and spec["unit"] == "pJ/byte"
                    and denominator_source == "expected_no_ncu_match"
                ):
                    reasons.append("missing_ncu_denominator")
                if min_delta_j > 0.0 and abs(delta_j) < min_delta_j:
                    reasons.append(f"delta_E<{min_delta_j:g}J")
                if (
                    min_delta_fraction > 0.0
                    and abs(delta_fraction) < min_delta_fraction
                ):
                    reasons.append(f"delta_fraction<{min_delta_fraction:g}")
                if not math.isfinite(coeff):
                    reasons.append("nonfinite_coefficient")
                elif coeff < 0.0:
                    reasons.append("negative_coefficient")

                (
                    profile_name,
                    gpu_id,
                    n_gpu_active,
                    w_sm_kib,
                    blocks_per_sm,
                    active_sm,
                    reuse_factor,
                    load_repeat,
                    store_repeat,
                ) = key
                pj_per_bit: float | str = ""
                if spec["unit"] == "pJ/byte":
                    pj_per_bit = coeff / 8.0
                elif spec["unit"] == "pJ/reg-op":
                    pj_per_bit = coeff / LOGICAL_OPERAND_BITS_PER_REG_OP
                detail_rows.append(
                    {
                        "profile_name": profile_name,
                        "gpu_id": gpu_id,
                        "n_gpu_active": n_gpu_active,
                        "W_SM_KiB": w_sm_kib,
                        "blocks_per_SM": blocks_per_sm,
                        "active_SM": active_sm,
                        "reuse_factor": reuse_factor,
                        "load_repeat": load_repeat,
                        "store_repeat": store_repeat,
                        "component": spec["component"],
                        "pair": spec["pair"],
                        "pairing": pairing,
                        "pair_energy_basis": pair_energy_basis,
                        "ncu_control_acceptance_required": control_acceptance_required,
                        "ncu_control_acceptance_exact": (
                            exact_config_key(control) in control_accepted_keys
                            if control_acceptance_required
                            else ""
                        ),
                        "numerator_mode": numerator_mode,
                        "control_mode": control_mode,
                        "numerator_run_id": numerator.get("run_id", ""),
                        "control_run_id": control.get("run_id", ""),
                        "run_order_distance": abs(
                            run_order(numerator) - run_order(control)
                        ),
                        "pair_start_distance_ms": pair_start_distance_ms,
                        "pair_completion_distance_ms": pair_completion_distance_ms,
                        "pair_transition_gap_ms": pair_transition_gap_ms,
                        "pair_transition_gap_limit_ms": max_pair_transition_gap_ms,
                        "pair_timing_source": pair_timing_source,
                        "pair_execution_order": pair_execution_order,
                        "numerator_measurement_start_epoch_ms": numerator_start_ms,
                        "numerator_measurement_end_epoch_ms": numerator_end_ms,
                        "control_measurement_start_epoch_ms": control_start_ms,
                        "control_measurement_end_epoch_ms": control_end_ms,
                        "numerator_elapsed_s": numerator_elapsed,
                        "control_elapsed_s": control_elapsed,
                        "elapsed_ratio": elapsed_ratio,
                        "numerator_ITER": (
                            int(numerator_iters) if math.isfinite(numerator_iters) else ""
                        ),
                        "control_ITER": (
                            int(control_iters) if math.isfinite(control_iters) else ""
                        ),
                        "iter_ratio": (
                            numerator_iters / control_iters
                            if control_iters > 0.0
                            else float("inf")
                        ),
                        "numerator_net_E_J": numerator_energy,
                        "control_net_E_J": control_energy,
                        "control_power_W": control_power,
                        "control_energy_scaled_J": control_energy_scaled,
                        "delta_E_J": delta_j,
                        "delta_signal_fraction": delta_fraction,
                        "denominator_column": spec["denominator_column"],
                        "denominator": denominator,
                        "denominator_scale": denominator_scale,
                        "denominator_source": denominator_source,
                        "ncu_denominator_bytes_representative": ncu_denominator_bytes,
                        "numerator_energy_source": numerator.get("energy_source", ""),
                        "control_energy_source": control.get("energy_source", ""),
                        "numerator_energy_integration_method": numerator.get(
                            "energy_integration_method", ""
                        ),
                        "control_energy_integration_method": control.get(
                            "energy_integration_method", ""
                        ),
                        "numerator_measurement_scope": measurement_scope(numerator),
                        "control_measurement_scope": measurement_scope(control),
                        "numerator_nvml_total_energy_supported": numerator.get(
                            "nvml_total_energy_supported", ""
                        ),
                        "control_nvml_total_energy_supported": control.get(
                            "nvml_total_energy_supported", ""
                        ),
                        "numerator_power_semantics": numerator.get(
                            "nvml_power_usage_semantics", ""
                        ),
                        "control_power_semantics": control.get(
                            "nvml_power_usage_semantics", ""
                        ),
                        "numerator_power_sample_period_ms": numerator.get(
                            "power_sample_period_ms", ""
                        ),
                        "control_power_sample_period_ms": control.get(
                            "power_sample_period_ms", ""
                        ),
                        "numerator_power_state_status": numerator.get(
                            "_power_state_status", ""
                        ),
                        "control_power_state_status": control.get(
                            "_power_state_status", ""
                        ),
                        "numerator_power_state_reasons": numerator.get(
                            "_power_state_reasons", ""
                        ),
                        "control_power_state_reasons": control.get(
                            "_power_state_reasons", ""
                        ),
                        "coefficient": coeff,
                        "coefficient_unit": spec["unit"],
                        "coefficient_pJ_per_bit": pj_per_bit,
                        "valid_component_estimate": not reasons,
                        "diagnostic": ";".join(reasons),
                        "source_file": numerator.get("_source_file", ""),
                    }
                )

    detail_rows.sort(
        key=lambda row: (
            row["component"],
            int(row["W_SM_KiB"] or 0),
            int(row["blocks_per_SM"] or 0),
            int(row["active_SM"] or 0),
            int(row["reuse_factor"] or 0),
            int(row["load_repeat"] or 0),
            int(row["store_repeat"] or 0),
        )
    )
    return detail_rows


def make_summary_rows(detail_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        if row["valid_component_estimate"]:
            by_component[row["component"]].append(row)

    summary_rows: list[dict[str, Any]] = []
    for component, rows in sorted(by_component.items()):
        coeffs = [float(row["coefficient"]) for row in rows]
        stats = summarize_coefficients(coeffs)
        unit = rows[0]["coefficient_unit"] if rows else ""
        coeff_q1 = quantile(coeffs, 0.25)
        coeff_q3 = quantile(coeffs, 0.75)
        coeff_iqr = coeff_q3 - coeff_q1
        coeff_mad = median_abs_deviation(coeffs)
        coeff_ci_low, coeff_ci_high = bootstrap_median_ci(
            coeffs, seed=20260708 + sum(ord(c) for c in component)
        )
        median_value = stats["median"]
        coeff_cv = (
            stats["stdev"] / median_value
            if median_value and math.isfinite(stats["stdev"])
            else float("nan")
        )
        coeff_rel_iqr = (
            coeff_iqr / abs(median_value)
            if median_value and math.isfinite(coeff_iqr)
            else float("nan")
        )
        coeff_ci_rel_width = relative_width(
            coeff_ci_low, coeff_ci_high, median_value
        )
        pbit_values = [
            float(row["coefficient_pJ_per_bit"])
            for row in rows
            if row["coefficient_pJ_per_bit"] != ""
        ]
        pbit_stats = summarize_coefficients(pbit_values)
        pbit_ci_low: float | str = ""
        pbit_ci_high: float | str = ""
        pbit_ci_rel_width: float | str = ""
        if int(pbit_stats["n"]) > 0:
            pbit_ci_low, pbit_ci_high = bootstrap_median_ci(
                pbit_values, seed=20260708 + sum(ord(c) for c in component) + 17
            )
            pbit_ci_rel_width = relative_width(
                pbit_ci_low, pbit_ci_high, pbit_stats["median"]
            )
        summary_rows.append(
            {
                "component": component,
                "rows": int(stats["n"]),
                "ncu_denominator_rows": sum(
                    1
                    for row in rows
                    if str(row.get("denominator_source", "")).startswith("ncu_actual")
                ),
                "expected_denominator_rows": sum(
                    1
                    for row in rows
                    if row.get("denominator_source", "") == "expected_no_ncu_match"
                ),
                "unit": unit,
                "energy_source": ",".join(
                    sorted({str(row.get("numerator_energy_source", "")) for row in rows})
                ),
                "energy_integration_method": ",".join(
                    sorted(
                        {
                            str(row.get("numerator_energy_integration_method", ""))
                            for row in rows
                        }
                    )
                ),
                "power_semantics": ",".join(
                    sorted({str(row.get("numerator_power_semantics", "")) for row in rows})
                ),
                "measurement_scope": ",".join(
                    sorted({str(row.get("numerator_measurement_scope", "")) for row in rows})
                ),
                "min": stats["min"],
                "median": stats["median"],
                "mean": stats["mean"],
                "max": stats["max"],
                "stdev": stats["stdev"],
                "q1": coeff_q1,
                "q3": coeff_q3,
                "iqr": coeff_iqr,
                "mad": coeff_mad,
                "cv": coeff_cv,
                "relative_iqr": coeff_rel_iqr,
                "median_ci_low": coeff_ci_low,
                "median_ci_high": coeff_ci_high,
                "median_ci_relative_width": coeff_ci_rel_width,
                "confidence_class": confidence_class(
                    int(stats["n"]), coeff_rel_iqr, coeff_ci_rel_width
                ),
                "median_pJ_per_bit": (
                    pbit_stats["median"] if int(pbit_stats["n"]) > 0 else ""
                ),
                "min_pJ_per_bit": (
                    pbit_stats["min"] if int(pbit_stats["n"]) > 0 else ""
                ),
                "max_pJ_per_bit": (
                    pbit_stats["max"] if int(pbit_stats["n"]) > 0 else ""
                ),
                "median_pJ_per_bit_ci_low": pbit_ci_low,
                "median_pJ_per_bit_ci_high": pbit_ci_high,
                "median_pJ_per_bit_ci_relative_width": pbit_ci_rel_width,
            }
        )
    return summary_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if value == "":
        return ""
    if isinstance(value, bool):
        return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "nan"
    return f"{number:.6g}"


def write_markdown(
    path: Path,
    *,
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    invalid = [row for row in detail_rows if not row["valid_component_estimate"]]
    with path.open("w") as f:
        f.write("# Matched-Control Component Energy\n\n")
        f.write("## Method\n\n")
        f.write(
            "Default rows use `delta_E_J = E_mode_J - "
            "(E_control_J / t_control_s) * t_mode_s`. Tensor, L2 CG, and DRAM rows use "
            "direct net-energy subtraction only when their pair policy is "
            "`matched-iters` and both ITER values match.\n\n"
        )
        f.write(
            "Only rows passing elapsed, net-energy, SMID, and optional NCU "
            "acceptance filters are summarized. Values are effective "
            "microbenchmark coefficients, not pure physical component energies.\n\n"
        )
        f.write("## Inputs\n\n")
        f.write("| item | value |\n")
        f.write("|---|---|\n")
        f.write(f"| raw CSVs | `{', '.join(args.csv_paths)}` |\n")
        f.write(f"| acceptance CSVs | `{', '.join(args.acceptance_csv)}` |\n")
        f.write(f"| NCU summary CSVs | `{', '.join(args.ncu_summary_csv)}` |\n")
        f.write(
            f"| power-state audit CSVs | `{', '.join(args.power_state_audit_csv)}` |\n"
        )
        f.write(f"| min elapsed (s) | {args.min_elapsed_s:g} |\n")
        f.write(
            "| Tensor control min elapsed (s) | "
            f"{args.tensor_control_min_elapsed_s:g} |\n"
        )
        f.write(
            "| L2 control min elapsed (s) | "
            f"{args.l2_control_min_elapsed_s:g} |\n"
        )
        f.write(
            "| DRAM control min elapsed (s) | "
            f"{args.dram_control_min_elapsed_s:g} |\n"
        )
        f.write(f"| DRAM pair policy | {args.dram_pair_policy} |\n")
        f.write(f"| L2 pair policy | {args.l2_pair_policy} |\n")
        f.write(
            "| require exact control NCU acceptance | "
            f"{args.require_control_ncu_acceptance} |\n"
        )
        f.write(f"| max elapsed ratio | {args.max_elapsed_ratio:g} |\n")
        f.write(
            "| max pair transition gap (ms) | "
            f"{args.max_pair_transition_gap_ms:g} |\n"
        )
        f.write(
            "| pair timing semantics | exact benchmark intervals when present; "
            "legacy run_id minus elapsed fallback otherwise |\n"
        )
        f.write(f"| pairing | `{args.pairing}` |\n")
        f.write(f"| Tensor pair policy | `{args.tensor_pair_policy}` |\n")
        f.write(f"| min delta_E (J) | {args.min_delta_j:g} |\n")
        f.write(f"| min delta fraction | {args.min_delta_fraction:g} |\n")
        f.write(f"| require NCU denominator | {args.require_ncu_denominator} |\n")
        f.write(f"| require total energy counter | {args.require_total_energy} |\n")
        f.write(f"| expected power semantics | `{args.expected_power_semantics}` |\n")
        f.write(
            f"| exclude power-state rejects | {args.exclude_power_state_rejects} |\n"
        )
        f.write("\n## Component Summary\n\n")
        f.write(
            "| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |\n"
        )
        f.write("|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|\n")
        for row in summary_rows:
            pbit_range = ""
            if row["median_pJ_per_bit"] != "":
                pbit_range = (
                    f"{fmt(row['min_pJ_per_bit'])} - {fmt(row['max_pJ_per_bit'])}"
                )
            median_ci = (
                f"{fmt(row['median_ci_low'])} - {fmt(row['median_ci_high'])}"
            )
            pbit_ci = ""
            if row["median_pJ_per_bit_ci_low"] != "":
                pbit_ci = (
                    f"{fmt(row['median_pJ_per_bit_ci_low'])} - "
                    f"{fmt(row['median_pJ_per_bit_ci_high'])}"
                )
            f.write(
                f"| {row['component']} | {row['rows']} | "
                f"{row['confidence_class']} | "
                f"{row['ncu_denominator_rows']} | "
                f"{row['expected_denominator_rows']} | "
                f"{row['energy_source']} | "
                f"{row['energy_integration_method']} | "
                f"{row['measurement_scope']} | "
                f"{row['power_semantics']} | {row['unit']} | "
                f"{fmt(row['min'])} | {fmt(row['median'])} | "
                f"{fmt(row['mean'])} | {fmt(row['max'])} | "
                f"{fmt(row['stdev'])} | {fmt(row['iqr'])} | "
                f"{fmt(row['cv'])} | {median_ci} | "
                f"{fmt(row['median_pJ_per_bit'])} | {pbit_range} | "
                f"{pbit_ci} |\n"
            )
        f.write("\n## Detail Rows\n\n")
        f.write(
            "| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | execution order | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |\n"
        )
        f.write(
            "|---|---:|---:|---:|---:|---|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|\n"
        )
        for row in detail_rows:
            f.write(
                f"| {row['component']} | {row['W_SM_KiB']} | "
                f"{row['blocks_per_SM']} | {row['reuse_factor']} | "
                f"{row['load_repeat']} | "
                f"{row['pair']} | {row['pairing']} | "
                f"{row['pair_execution_order']} | "
                f"{fmt(row['delta_E_J'])} | "
                f"{fmt(row['delta_signal_fraction'])} | "
                f"{fmt(row['denominator'])} | {row['denominator_source']} | "
                f"{row['numerator_energy_source']} | "
                f"{row['numerator_energy_integration_method']} | "
                f"{row['numerator_measurement_scope']} | "
                f"{row['numerator_power_semantics']} | "
                f"{fmt(row['coefficient'])} | "
                f"{row['coefficient_unit']} | "
                f"{fmt(row['coefficient_pJ_per_bit'])} | "
                f"{fmt(row['elapsed_ratio'])} | "
                f"{row['valid_component_estimate']} | {row['diagnostic']} |\n"
            )
        f.write("\n## QA\n\n")
        f.write(f"- Detail rows: {len(detail_rows)}\n")
        f.write(f"- Invalid detail rows: {len(invalid)}\n")
        if invalid:
            reasons: dict[str, int] = defaultdict(int)
            for row in invalid:
                for reason in str(row["diagnostic"]).split(";"):
                    if reason:
                        reasons[reason] += 1
            for reason, count in sorted(reasons.items()):
                f.write(f"- {reason}: {count}\n")
        f.write("\n## Interpretation Limits\n\n")
        f.write(
            "- `register_operand_control` is a no-MMA register-fragment/control "
            "proxy, not a pure register-file bitcell value.\n"
        )
        f.write(
            "- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical "
            "input bits per warp-level m16n16k16 op; it is not a measured "
            "physical register-file bit energy.\n"
        )
        f.write(
            "- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is "
            "the effective MMA incremental cost under this kernel, not a pure "
            "Tensor Core transistor-level energy.\n"
        )
        f.write(
            "- Byte-path values are accepted only when the corresponding NCU "
            "path validation confirms hit rate/access behavior for that mode.\n"
        )
        f.write(
            "- `delta_signal_fraction` is `delta_E_J / max(treatment_E, "
            "scaled_control_E)`. Rows below the configured signal gate are "
            "reported but excluded from component summaries.\n"
        )
        f.write(
            "- `confidence_class` is a stability label from row count, relative "
            "IQR, and bootstrap median CI width. It is a reporting aid, not a "
            "claim of physical component isolation.\n"
        )
        f.write(
            "- Rows using `legacy_get_power_usage_integral` are fallback power "
            "estimates. For final coefficients, prefer `nvml_total_energy` "
            "with `total_energy_mj_delta` and report "
            "`nvml_power_usage_semantics` beside the result.\n"
        )
        f.write(
            "- When `--exclude-power-state-rejects` is used, rows marked "
            "`status=reject` or `coefficient_eligible=false` by the "
            "power-state audit are removed before treatment/control pairing. "
            "This keeps power-state drops from becoming negative component "
            "coefficients.\n"
        )


def run_self_test() -> None:
    common = {
        "profile_name": "a100",
        "gpu_id": "0",
        "n_gpu_active": "1",
        "W_SM_KiB": "2048",
        "blocks_per_SM": "16",
        "active_SM": "108",
        "reuse_factor": "4",
        "load_repeat": "1",
        "store_repeat": "1",
        "ITER": "100",
        "smid_histogram_ok": "true",
        "energy_source": "nvml_total_energy",
        "energy_integration_method": "total_energy_mj_delta",
        "measurement_scope": "gpu_device_total_energy_counter",
        "nvml_total_energy_supported": "true",
        "nvml_power_usage_semantics": "instant",
    }
    treatment = {
        **common,
        "mode": "reg_mma",
        "run_id": "reg_mma_20000_r0",
        "elapsed_s": "10",
        "net_E_J": "30",
        "FLOP": "1415577600",
    }
    control = {
        **common,
        "mode": "reg_operand_only",
        "run_id": "reg_operand_only_9000_r0",
        "elapsed_s": "5",
        "net_E_J": "10",
        "FLOP": "0",
    }
    kwargs = dict(
        accepted_modes=set(),
        accepted_keys_by_mode={},
        exact_ncu_scales={},
        same_working_set_ncu_scales={},
        min_elapsed_s=1.0,
        tensor_control_min_elapsed_s=0.05,
        l2_control_min_elapsed_s=0.05,
        dram_control_min_elapsed_s=0.05,
        max_elapsed_ratio=3.0,
        max_pair_transition_gap_ms=30000.0,
        min_delta_j=0.0,
        min_delta_fraction=0.0,
        require_ncu_denominator=False,
        require_total_energy=True,
        expected_power_semantics="instant",
        exclude_power_state_rejects=False,
        pairing="nearest-control",
        l2_pair_policy="duration-scaled",
        dram_pair_policy="duration-scaled",
        require_control_ncu_acceptance=False,
    )
    matched = make_detail_rows(
        [treatment, control], tensor_pair_policy="matched-iters", **kwargs
    )
    assert len(matched) == 1
    assert matched[0]["pair_energy_basis"] == "matched_iters_net_energy"
    assert abs(float(matched[0]["delta_E_J"]) - 20.0) < 1.0e-9
    assert float(matched[0]["pair_transition_gap_ms"]) == 1000.0
    assert matched[0]["pair_timing_source"] == "legacy_run_id_elapsed_inferred"
    assert matched[0]["pair_execution_order"] == "control_then_treatment"
    assert matched[0]["valid_component_estimate"]

    adjacent_after_long_kernel = {
        **control,
        "run_id": "reg_operand_only_51000_r0",
        "elapsed_s": "10",
    }
    adjacent = make_detail_rows(
        [treatment, adjacent_after_long_kernel],
        tensor_pair_policy="matched-iters",
        **kwargs,
    )
    assert adjacent[0]["pair_completion_distance_ms"] == 31000.0
    assert adjacent[0]["pair_transition_gap_ms"] == 21000.0
    assert adjacent[0]["valid_component_estimate"]

    exact_treatment = {
        **treatment,
        "measurement_start_epoch_ms": "100000",
        "measurement_end_epoch_ms": "110000",
    }
    exact_control = {
        **control,
        "measurement_start_epoch_ms": "70000",
        "measurement_end_epoch_ms": "90000",
    }
    exact = make_detail_rows(
        [exact_treatment, exact_control],
        tensor_pair_policy="matched-iters",
        **kwargs,
    )
    assert exact[0]["pair_transition_gap_ms"] == 10000.0
    assert exact[0]["pair_timing_source"] == "exact_epoch_interval"
    assert exact[0]["pair_execution_order"] == "control_then_treatment"
    assert exact[0]["valid_component_estimate"]

    reverse_exact_treatment = {
        **treatment,
        "measurement_start_epoch_ms": "70000",
        "measurement_end_epoch_ms": "80000",
    }
    reverse_exact_control = {
        **control,
        "measurement_start_epoch_ms": "90000",
        "measurement_end_epoch_ms": "110000",
    }
    reverse_exact = make_detail_rows(
        [reverse_exact_treatment, reverse_exact_control],
        tensor_pair_policy="matched-iters",
        **kwargs,
    )
    assert reverse_exact[0]["pair_transition_gap_ms"] == 10000.0
    assert reverse_exact[0]["pair_execution_order"] == "treatment_then_control"
    assert reverse_exact[0]["valid_component_estimate"]

    distant_control = {
        **control,
        "run_id": "reg_operand_only_100000_r0",
    }
    distant = make_detail_rows(
        [treatment, distant_control], tensor_pair_policy="matched-iters", **kwargs
    )
    assert not distant[0]["valid_component_estimate"]
    assert "pair_transition_gap_ms>30000" in distant[0]["diagnostic"]

    duration_scaled = make_detail_rows(
        [treatment, control], tensor_pair_policy="duration-scaled", **kwargs
    )
    assert abs(float(duration_scaled[0]["delta_E_J"]) - 10.0) < 1.0e-9

    short_control = {**control, "elapsed_s": "0.1", "net_E_J": "1"}
    matched_short = make_detail_rows(
        [treatment, short_control], tensor_pair_policy="matched-iters", **kwargs
    )
    assert len(matched_short) == 1
    assert abs(float(matched_short[0]["delta_E_J"]) - 29.0) < 1.0e-9
    duration_short = make_detail_rows(
        [treatment, short_control], tensor_pair_policy="duration-scaled", **kwargs
    )
    assert not duration_short

    mismatched_control = {**control, "ITER": "99"}
    mismatched = make_detail_rows(
        [treatment, mismatched_control],
        tensor_pair_policy="matched-iters",
        **kwargs,
    )
    assert not mismatched[0]["valid_component_estimate"]
    assert "tensor_iter_mismatch" in mismatched[0]["diagnostic"]

    l2_common = {
        **common,
        "W_SM_KiB": "32",
        "load_repeat": "4",
        "ITER": "400",
    }
    l2_treatment = {
        **l2_common,
        "mode": "l2_cg_load_only",
        "run_id": "l2_cg_load_only_40000_r0",
        "elapsed_s": "10",
        "net_E_J": "50",
        "expected_l2_bytes": "1000000",
    }
    l2_control = {
        **l2_common,
        "mode": "global_addr_only",
        "run_id": "global_addr_only_29000_r0",
        "elapsed_s": "4",
        "net_E_J": "15",
        "expected_l2_bytes": "0",
    }
    l2_matched = make_detail_rows(
        [l2_treatment, l2_control],
        tensor_pair_policy="duration-scaled",
        l2_pair_policy="matched-iters",
        **{k: v for k, v in kwargs.items() if k != "l2_pair_policy"},
    )
    assert len(l2_matched) == 1
    assert l2_matched[0]["pair_energy_basis"] == "matched_iters_net_energy"
    assert abs(float(l2_matched[0]["delta_E_J"]) - 35.0) < 1.0e-9
    assert l2_matched[0]["valid_component_estimate"]
    l2_mismatch = make_detail_rows(
        [l2_treatment, {**l2_control, "ITER": "800"}],
        tensor_pair_policy="duration-scaled",
        l2_pair_policy="matched-iters",
        **{k: v for k, v in kwargs.items() if k != "l2_pair_policy"},
    )
    assert not l2_mismatch[0]["valid_component_estimate"]
    assert "l2_iter_mismatch" in l2_mismatch[0]["diagnostic"]

    dram_common = {
        **common,
        "W_SM_KiB": "8192",
        "load_repeat": "4",
        "ITER": "200",
    }
    dram_treatment = {
        **dram_common,
        "mode": "dram_cg_load_only",
        "run_id": "dram_cg_load_only_60000_r0",
        "elapsed_s": "10",
        "net_E_J": "80",
        "expected_dram_bytes": "1000000",
    }
    dram_control = {
        **dram_common,
        "mode": "global_addr_only",
        "run_id": "global_addr_only_49000_r0",
        "elapsed_s": "3",
        "net_E_J": "20",
        "expected_dram_bytes": "0",
    }
    dram_matched = make_detail_rows(
        [dram_treatment, dram_control],
        tensor_pair_policy="duration-scaled",
        dram_pair_policy="matched-iters",
        **{k: v for k, v in kwargs.items() if k != "dram_pair_policy"},
    )
    assert len(dram_matched) == 1
    assert dram_matched[0]["pair_energy_basis"] == "matched_iters_net_energy"
    assert abs(float(dram_matched[0]["delta_E_J"]) - 60.0) < 1.0e-9
    assert dram_matched[0]["valid_component_estimate"]
    dram_mismatch = make_detail_rows(
        [dram_treatment, {**dram_control, "ITER": "199"}],
        tensor_pair_policy="duration-scaled",
        dram_pair_policy="matched-iters",
        **{k: v for k, v in kwargs.items() if k != "dram_pair_policy"},
    )
    assert not dram_mismatch[0]["valid_component_estimate"]
    assert "dram_iter_mismatch" in dram_mismatch[0]["diagnostic"]

    control_acceptance_kwargs = {
        **kwargs,
        "accepted_modes": {"reg_mma", "reg_operand_only"},
        "accepted_keys_by_mode": {
            "reg_mma": {exact_config_key(treatment)},
            "reg_operand_only": {exact_config_key(control)},
        },
        "require_control_ncu_acceptance": True,
    }
    control_accepted = make_detail_rows(
        [treatment, control],
        tensor_pair_policy="matched-iters",
        **control_acceptance_kwargs,
    )
    assert len(control_accepted) == 1
    assert control_accepted[0]["ncu_control_acceptance_required"]
    assert control_accepted[0]["ncu_control_acceptance_exact"]
    control_rejected = make_detail_rows(
        [treatment, control],
        tensor_pair_policy="matched-iters",
        **{
            **control_acceptance_kwargs,
            "accepted_keys_by_mode": {
                "reg_mma": {exact_config_key(treatment)},
                "reg_operand_only": set(),
            },
        },
    )
    assert control_rejected == []
    print("matched-control Tensor/L2/DRAM pair-policy self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_paths", nargs="*")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--acceptance-csv",
        nargs="*",
        default=[],
        help="Optional NCU acceptance CSV(s). Accepted numerator modes are kept.",
    )
    parser.add_argument(
        "--ncu-summary-csv",
        nargs="*",
        default=[],
        help="Optional NCU summary CSVs used to scale byte denominators by actual traffic.",
    )
    parser.add_argument(
        "--power-state-audit-csv",
        nargs="*",
        default=[],
        help="Optional power-state audit CSV(s) used to exclude unstable raw rows.",
    )
    parser.add_argument(
        "--require-ncu-denominator",
        action="store_true",
        help="Reject byte-path rows without a matching NCU denominator scale.",
    )
    parser.add_argument(
        "--require-total-energy",
        action="store_true",
        help="Reject rows that do not use nvmlDeviceGetTotalEnergyConsumption deltas.",
    )
    parser.add_argument(
        "--expected-power-semantics",
        default="",
        help="Optional expected nvmlDeviceGetPowerUsage semantics from the target profile.",
    )
    parser.add_argument(
        "--exclude-power-state-rejects",
        action="store_true",
        help=(
            "Reject rows marked status=reject or coefficient_eligible=false in "
            "--power-state-audit-csv before treatment/control pairing."
        ),
    )
    parser.add_argument(
        "--out-summary-csv",
        default="results/summary/matched_control_component_energy_summary.csv",
    )
    parser.add_argument(
        "--out-detail-csv",
        default="results/summary/matched_control_component_energy_detail.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/matched_control_component_energy.md",
    )
    parser.add_argument("--min-elapsed-s", type=float, default=1.0)
    parser.add_argument(
        "--tensor-control-min-elapsed-s",
        type=float,
        default=0.05,
        help=(
            "Minimum elapsed time for a matched-ITER reg_operand_only control. "
            "It is intentionally lower than --min-elapsed-s because the no-MMA "
            "control completes the same ITER much faster than reg_mma."
        ),
    )
    parser.add_argument(
        "--l2-control-min-elapsed-s",
        type=float,
        default=0.5,
        help=(
            "Minimum elapsed time for a matched-ITER global_addr_only L2 control."
        ),
    )
    parser.add_argument(
        "--dram-control-min-elapsed-s",
        type=float,
        default=0.5,
        help=(
            "Minimum elapsed time for a matched-ITER global_addr_only DRAM "
            "control."
        ),
    )
    parser.add_argument("--max-elapsed-ratio", type=float, default=1.35)
    parser.add_argument(
        "--max-pair-transition-gap-ms",
        type=float,
        default=None,
        help=(
            "Reject nearest-control pairs whose timed benchmark intervals are "
            "separated by more than this limit. Exact epoch fields are preferred; "
            "legacy CSVs infer each interval from run_id and elapsed_s. Defaults "
            "to 30000 ms. Set to 0 to disable the gate."
        ),
    )
    parser.add_argument(
        "--max-pair-start-distance-ms",
        type=float,
        default=None,
        help=(
            "Deprecated alias for --max-pair-transition-gap-ms. It no longer "
            "gates the legacy completion-to-completion distance."
        ),
    )
    parser.add_argument("--min-delta-j", type=float, default=0.0)
    parser.add_argument("--min-delta-fraction", type=float, default=0.0)
    parser.add_argument(
        "--pairing",
        choices=["median-control", "nearest-control"],
        default="median-control",
        help=(
            "median-control emits one median treatment/control row per config; "
            "nearest-control emits one row per treatment matched to the closest "
            "control run order."
        ),
    )
    parser.add_argument(
        "--tensor-pair-policy",
        choices=["duration-scaled", "matched-iters"],
        default="duration-scaled",
        help=(
            "Use matched-iters for Tensor finalplan rows. It requires equal ITER "
            "and subtracts net energies directly instead of scaling control power."
        ),
    )
    parser.add_argument(
        "--l2-pair-policy",
        choices=["duration-scaled", "matched-iters"],
        default="matched-iters",
        help=(
            "L2 final rows require equal ITER and directly subtract net energies. "
            "duration-scaled is retained only for explicit legacy diagnostics."
        ),
    )
    parser.add_argument(
        "--dram-pair-policy",
        choices=["duration-scaled", "matched-iters"],
        default="duration-scaled",
        help=(
            "Use matched-iters for dram_cg_load_only/global_addr_only rows. "
            "It requires equal ITER and directly subtracts net energies."
        ),
    )
    parser.add_argument(
        "--require-control-ncu-acceptance",
        action="store_true",
        help=(
            "Require exact-coordinate accepted NCU rows for reg_operand_only and "
            "global_addr_only controls. Final component packages must enable this."
        ),
    )
    args = parser.parse_args()

    if args.max_pair_transition_gap_ms is None:
        args.max_pair_transition_gap_ms = (
            args.max_pair_start_distance_ms
            if args.max_pair_start_distance_ms is not None
            else 30000.0
        )
    elif (
        args.max_pair_start_distance_ms is not None
        and args.max_pair_start_distance_ms != args.max_pair_transition_gap_ms
    ):
        parser.error(
            "--max-pair-transition-gap-ms and deprecated "
            "--max-pair-start-distance-ms disagree"
        )

    if args.self_test:
        run_self_test()
        return 0
    if not args.csv_paths:
        parser.error("at least one raw CSV path is required")

    rows = read_rows(args.csv_paths)
    power_state_audit = read_power_state_audit(args.power_state_audit_csv)
    attach_power_state_audit(rows, power_state_audit)
    accepted_modes, accepted_keys_by_mode = read_acceptance(args.acceptance_csv)
    exact_ncu_scales, same_working_set_ncu_scales = read_ncu_denominator_scales(
        args.ncu_summary_csv
    )
    detail_rows = make_detail_rows(
        rows,
        accepted_modes=accepted_modes,
        accepted_keys_by_mode=accepted_keys_by_mode,
        exact_ncu_scales=exact_ncu_scales,
        same_working_set_ncu_scales=same_working_set_ncu_scales,
        min_elapsed_s=args.min_elapsed_s,
        tensor_control_min_elapsed_s=args.tensor_control_min_elapsed_s,
        l2_control_min_elapsed_s=args.l2_control_min_elapsed_s,
        dram_control_min_elapsed_s=args.dram_control_min_elapsed_s,
        max_elapsed_ratio=args.max_elapsed_ratio,
        max_pair_transition_gap_ms=args.max_pair_transition_gap_ms,
        min_delta_j=args.min_delta_j,
        min_delta_fraction=args.min_delta_fraction,
        require_ncu_denominator=args.require_ncu_denominator,
        require_total_energy=args.require_total_energy,
        expected_power_semantics=args.expected_power_semantics,
        exclude_power_state_rejects=args.exclude_power_state_rejects,
        pairing=args.pairing,
        tensor_pair_policy=args.tensor_pair_policy,
        l2_pair_policy=args.l2_pair_policy,
        dram_pair_policy=args.dram_pair_policy,
        require_control_ncu_acceptance=args.require_control_ncu_acceptance,
    )
    summary_rows = make_summary_rows(detail_rows)

    detail_fields = [
        "profile_name",
        "gpu_id",
        "n_gpu_active",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "component",
        "pair",
        "pairing",
        "pair_energy_basis",
        "ncu_control_acceptance_required",
        "ncu_control_acceptance_exact",
        "numerator_mode",
        "control_mode",
        "numerator_run_id",
        "control_run_id",
        "run_order_distance",
        "pair_start_distance_ms",
        "pair_completion_distance_ms",
        "pair_transition_gap_ms",
        "pair_transition_gap_limit_ms",
        "pair_timing_source",
        "pair_execution_order",
        "numerator_measurement_start_epoch_ms",
        "numerator_measurement_end_epoch_ms",
        "control_measurement_start_epoch_ms",
        "control_measurement_end_epoch_ms",
        "numerator_elapsed_s",
        "control_elapsed_s",
        "elapsed_ratio",
        "numerator_ITER",
        "control_ITER",
        "iter_ratio",
        "numerator_net_E_J",
        "control_net_E_J",
        "control_power_W",
        "control_energy_scaled_J",
        "delta_E_J",
        "delta_signal_fraction",
        "denominator_column",
        "denominator",
        "denominator_scale",
        "denominator_source",
        "ncu_denominator_bytes_representative",
        "numerator_energy_source",
        "control_energy_source",
        "numerator_energy_integration_method",
        "control_energy_integration_method",
        "numerator_measurement_scope",
        "control_measurement_scope",
        "numerator_nvml_total_energy_supported",
        "control_nvml_total_energy_supported",
        "numerator_power_semantics",
        "control_power_semantics",
        "numerator_power_sample_period_ms",
        "control_power_sample_period_ms",
        "numerator_power_state_status",
        "control_power_state_status",
        "numerator_power_state_reasons",
        "control_power_state_reasons",
        "coefficient",
        "coefficient_unit",
        "coefficient_pJ_per_bit",
        "valid_component_estimate",
        "diagnostic",
        "source_file",
    ]
    summary_fields = [
        "component",
        "rows",
        "ncu_denominator_rows",
        "expected_denominator_rows",
        "unit",
        "energy_source",
        "energy_integration_method",
        "measurement_scope",
        "power_semantics",
        "min",
        "median",
        "mean",
        "max",
        "stdev",
        "q1",
        "q3",
        "iqr",
        "mad",
        "cv",
        "relative_iqr",
        "median_ci_low",
        "median_ci_high",
        "median_ci_relative_width",
        "confidence_class",
        "median_pJ_per_bit",
        "min_pJ_per_bit",
        "max_pJ_per_bit",
        "median_pJ_per_bit_ci_low",
        "median_pJ_per_bit_ci_high",
        "median_pJ_per_bit_ci_relative_width",
    ]
    write_csv(Path(args.out_detail_csv), detail_rows, detail_fields)
    write_csv(Path(args.out_summary_csv), summary_rows, summary_fields)
    write_markdown(
        Path(args.out_md),
        summary_rows=summary_rows,
        detail_rows=detail_rows,
        args=args,
    )
    print(f"wrote summary csv: {args.out_summary_csv}")
    print(f"wrote detail csv: {args.out_detail_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"detail rows: {len(detail_rows)}")
    print(f"summary rows: {len(summary_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
