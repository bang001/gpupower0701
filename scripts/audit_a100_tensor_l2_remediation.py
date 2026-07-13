#!/usr/bin/env python3
"""Audit the targeted A100 Tensor/L2 remediation experiment.

This gate is intentionally narrower and stricter than the full platform package:
it proves that RF1-16 Tensor pairs use identical work and stay positive, and that
at least two A100 L2 working-set points form an NCU-validated coefficient plateau.
The coefficients remain workload-dependent board-level effective values.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


TENSOR_MARKER = "tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2"
CG_MARKER = "global_warmup_policy=ld_global_cg"
L2_REVISION_MARKER = "l2_residency_revision=topology_policy_warmup_v2"


@dataclass(frozen=True)
class AuditConfig:
    expected_rf: tuple[int, ...]
    expected_l2_w: tuple[int, ...]
    ncu_load_repeats: tuple[int, ...]
    energy_load_repeats: tuple[int, ...]
    blocks_per_sm: int
    l2_blocks_per_sm: int
    active_sm: int
    expected_repeats: int
    min_valid_repeats: int
    tensor_treatment_target_seconds: float
    tensor_control_calibration_min_seconds: float
    min_delta_j: float
    tensor_min_pj_per_flop: float
    tensor_max_pj_per_flop: float
    tensor_hmma_ratio_relative_spread_max: float
    tensor_coefficient_relative_spread_max: float
    max_pair_start_distance_ms: float
    ncu_replay_mode: str
    ncu_cache_control: str
    l2_residency_policy: str
    l2_address_layout: str
    global_warmup_passes: int
    l1_path_hit_max_pct: float
    l1_hit_bytes_ratio_max: float
    l2_path_hit_min_pct: float
    l2_native_derived_hit_delta_max_pct: float
    l2_sector_conservation_tolerance: float
    dram_to_l2_bytes_max: float
    address_control_dram_ratio_max: float
    plateau_relative_spread_max: float


def parse_ints(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values or any(item <= 0 for item in values):
        raise ValueError("integer lists must contain positive values")
    return values


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def as_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def as_int(row: dict[str, str], key: str, default: int = -1) -> int:
    value = as_float(row, key)
    return int(value) if math.isfinite(value) else default


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def median(values: Iterable[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def fmt(value: Any) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            return "missing"
        return f"{value:.6g}"
    return str(value)


def result(
    area: str,
    coordinate: str,
    check: str,
    passed: bool | None,
    expected: str,
    actual: str,
    evidence: str,
    next_action: str,
) -> dict[str, str]:
    status = "pass" if passed is True else "fail" if passed is False else "missing"
    return {
        "area": area,
        "coordinate": coordinate,
        "check": check,
        "status": status,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
        "next_action": next_action,
    }


def select(
    rows: list[dict[str, str]],
    *,
    mode: str | None = None,
    component: str | None = None,
    blocks_per_sm: int | None = None,
    active_sm: int | None = None,
    reuse_factor: int | None = None,
    load_repeat: int | None = None,
    w_sm_kib: int | None = None,
) -> list[dict[str, str]]:
    out = []
    for row in rows:
        if mode is not None and row.get("mode") != mode:
            continue
        if component is not None and row.get("component") != component:
            continue
        if blocks_per_sm is not None and as_int(row, "blocks_per_SM") != blocks_per_sm:
            continue
        if active_sm is not None and as_int(row, "active_SM") != active_sm:
            continue
        if reuse_factor is not None and as_int(row, "reuse_factor") != reuse_factor:
            continue
        if load_repeat is not None and as_int(row, "load_repeat") != load_repeat:
            continue
        if w_sm_kib is not None and as_int(row, "W_SM_KiB") != w_sm_kib:
            continue
        out.append(row)
    return out


def all_columns(rows: list[dict[str, str]], required: set[str]) -> bool:
    return bool(rows) and required.issubset(rows[0])


def expected_memory_path_bytes(row: dict[str, str]) -> float:
    return (
        as_float(row, "active_SM", 0.0)
        * as_float(row, "blocks_per_SM", 0.0)
        * as_float(row, "ITER", 0.0)
        * as_float(row, "load_repeat", 1.0)
        * 1024.0
    )


def audit_data(
    config: AuditConfig,
    *,
    tensor_raw: list[dict[str, str]],
    l2_raw: list[dict[str, str]],
    calibration: list[dict[str, str]],
    ncu_acceptance: list[dict[str, str]],
    matched_detail: list[dict[str, str]],
    evidence: dict[str, str],
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    schemas = {
        "tensor_raw": (
            tensor_raw,
            {"mode", "ITER", "reuse_factor", "blocks_per_SM", "active_SM", "notes"},
        ),
        "l2_raw": (
            l2_raw,
            {
                "mode",
                "load_repeat",
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "energy_source",
                "energy_integration_method",
                "measurement_scope",
                "notes",
            },
        ),
        "calibration": (
            calibration,
            {
                "resolved_iters",
                "reuse_factor",
                "blocks_per_SM",
                "active_SM",
                "status",
                "treatment_target_seconds",
                "control_min_seconds",
                "treatment_calibrated_iters",
                "control_min_calibrated_iters",
                "resolution_policy",
                "treatment_calibration_command",
                "control_calibration_command",
            },
        ),
        "ncu_acceptance": (
            ncu_acceptance,
            {
                "mode",
                "acceptance",
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "reuse_factor",
                "load_repeat",
                "ncu_replay_mode",
                "ncu_cache_control",
                "global_warmup_passes",
                "l2_residency_policy",
                "l2_address_layout",
                "tensor_hmma_inst",
                "expected_logical_mma",
                "tensor_hmma_per_logical_mma",
                "local_read_bytes",
                "local_write_bytes",
                "spill_local_read_inst",
                "spill_local_write_inst",
                "spill_zero_verified",
                "spill_evidence_source",
                "l1_path_hit_rate_pct",
                "l2_path_hit_rate_pct",
                "l2_native_read_hit_rate_pct",
                "l2_native_vs_derived_hit_delta_pct",
                "l2_read_sector_conservation_ratio",
                "l2_read_bytes_to_expected",
                "l1_request_bytes",
                "l1_hit_bytes",
                "l2_read_bytes",
                "l2_read_miss_bytes",
                "dram_read_bytes",
                "dram_bytes",
                "launch_persisting_l2_cache_size_bytes",
            },
        ),
        "matched_detail": (
            matched_detail,
            {
                "component",
                "blocks_per_SM",
                "active_SM",
                "reuse_factor",
                "load_repeat",
                "W_SM_KiB",
                "pair_energy_basis",
                "iter_ratio",
                "run_order_distance",
                "pair_start_distance_ms",
                "numerator_elapsed_s",
                "control_elapsed_s",
                "numerator_net_E_J",
                "control_net_E_J",
                "delta_E_J",
                "coefficient",
                "coefficient_pJ_per_bit",
                "valid_component_estimate",
            },
        ),
    }
    schema_ok = True
    for name, (rows, required) in schemas.items():
        missing = sorted(required - set(rows[0] if rows else {}))
        passed = bool(rows) and not missing
        schema_ok &= passed
        checks.append(
            result(
                "schema",
                name,
                "required_columns",
                passed if rows else None,
                "non-empty artifact with targeted audit columns",
                f"rows={len(rows)}; missing={','.join(missing) or 'none'}",
                evidence[name],
                "regenerate the targeted artifact with the current scripts and binary",
            )
        )
    if not schema_ok:
        checks.append(
            result(
                "overall",
                "a100_tensor_l2",
                "remediation_verdict",
                False,
                "all targeted evidence present",
                "schema/evidence incomplete",
                ";".join(evidence.values()),
                "fix missing artifacts or columns before interpreting coefficients",
            )
        )
        return checks

    tensor_ncu_pass_by_rf: dict[int, bool] = {}
    tensor_hmma_ratio_by_rf: dict[int, float] = {}
    tensor_coefficient_by_rf: dict[int, float] = {}
    for rf in config.expected_rf:
        coord = f"B{config.blocks_per_sm}/RF{rf}"
        cal_rows = select(
            calibration,
            blocks_per_sm=config.blocks_per_sm,
            active_sm=config.active_sm,
            reuse_factor=rf,
        )
        cal_iters = {
            as_int(row, "resolved_iters")
            for row in cal_rows
            if as_int(row, "resolved_iters") > 0
        }
        cal_row = cal_rows[0] if len(cal_rows) == 1 else {}
        treatment_calibrated_iters = as_int(cal_row, "treatment_calibrated_iters")
        control_min_calibrated_iters = as_int(cal_row, "control_min_calibrated_iters")
        resolved_candidate = max(
            treatment_calibrated_iters,
            control_min_calibrated_iters,
        )
        cal_ok = (
            len(cal_rows) == 1
            and len(cal_iters) == 1
            and cal_row.get("status") == "pair_locked"
            and cal_row.get("resolution_policy")
            == "max_treatment_and_control_min_iters"
            and treatment_calibrated_iters > 0
            and control_min_calibrated_iters > 0
            and next(iter(cal_iters), -1) == resolved_candidate
            and abs(
                as_float(cal_row, "treatment_target_seconds")
                - config.tensor_treatment_target_seconds
            )
            <= 1.0e-9
            and as_float(cal_row, "control_min_seconds")
            >= config.tensor_control_calibration_min_seconds
            and "--mode reg_mma"
            in cal_row.get("treatment_calibration_command", "")
            and "--calibrate-only"
            in cal_row.get("treatment_calibration_command", "")
            and "--mode reg_operand_only"
            in cal_row.get("control_calibration_command", "")
            and "--calibrate-only"
            in cal_row.get("control_calibration_command", "")
        )
        checks.append(
            result(
                "tensor",
                coord,
                "pair_calibration",
                cal_ok,
                (
                    "one dual-calibration row; resolved ITER=max(treatment,control-min); "
                    f"treatment target={config.tensor_treatment_target_seconds:g} s; "
                    f"control floor>={config.tensor_control_calibration_min_seconds:g} s"
                ),
                (
                    f"rows={len(cal_rows)}; treatment/control/resolved ITER="
                    f"{treatment_calibrated_iters}/{control_min_calibrated_iters}/"
                    f"{sorted(cal_iters)}; target/floor="
                    f"{fmt(as_float(cal_row, 'treatment_target_seconds'))}/"
                    f"{fmt(as_float(cal_row, 'control_min_seconds'))} s; "
                    f"policy={cal_row.get('resolution_policy', '')}"
                ),
                evidence["calibration"],
                "rerun Tensor calibration and do not combine partial manifests",
            )
        )
        resolved_iter = next(iter(cal_iters), -1)

        raw_by_mode = {
            mode: select(
                tensor_raw,
                mode=mode,
                blocks_per_sm=config.blocks_per_sm,
                active_sm=config.active_sm,
                reuse_factor=rf,
                w_sm_kib=2048,
            )
            for mode in ("reg_operand_only", "reg_mma")
        }
        raw_iters = {
            mode: {as_int(row, "ITER") for row in rows}
            for mode, rows in raw_by_mode.items()
        }
        raw_ok = all(len(rows) == config.expected_repeats for rows in raw_by_mode.values())
        raw_ok &= all(values == {resolved_iter} for values in raw_iters.values())
        raw_ok &= all(
            TENSOR_MARKER in row.get("notes", "")
            and row.get("energy_source") == "nvml_total_energy"
            and row.get("energy_integration_method") == "total_energy_mj_delta"
            and row.get("measurement_scope") == "gpu_device_total_energy_counter"
            for rows in raw_by_mode.values()
            for row in rows
        )
        checks.append(
            result(
                "tensor",
                coord,
                "raw_pair_work_and_revision",
                raw_ok,
                f"{config.expected_repeats} rows/mode, identical calibrated ITER, current marker, total-energy scope",
                f"counts={','.join(f'{m}:{len(v)}' for m, v in raw_by_mode.items())}; ITER={raw_iters}",
                evidence["tensor_raw"],
                "clean rebuild, archive stale CSVs, and rerun the pair-locked Tensor sweep",
            )
        )

        treatment_ncu = select(
            ncu_acceptance,
            mode="reg_mma",
            blocks_per_sm=config.blocks_per_sm,
            active_sm=config.active_sm,
            reuse_factor=rf,
            w_sm_kib=2048,
        )
        control_ncu = select(
            ncu_acceptance,
            mode="reg_operand_only",
            blocks_per_sm=config.blocks_per_sm,
            active_sm=config.active_sm,
            reuse_factor=rf,
            w_sm_kib=2048,
        )
        tensor_ncu_ok = len(treatment_ncu) == 1 and len(control_ncu) == 1
        if tensor_ncu_ok:
            treatment = treatment_ncu[0]
            control = control_ncu[0]
            logical_mma = as_float(treatment, "expected_logical_mma")
            hmma_per_logical_mma = as_float(
                treatment, "tensor_hmma_per_logical_mma"
            )
            reported_hmma = as_float(treatment, "tensor_hmma_inst", 0.0)
            ratio_consistent = (
                logical_mma > 0.0
                and hmma_per_logical_mma > 0.0
                and abs(
                    hmma_per_logical_mma - reported_hmma / logical_mma
                )
                <= max(1.0e-12, 1.0e-9 * hmma_per_logical_mma)
            )
            tensor_ncu_ok = (
                treatment.get("acceptance") == "accepted"
                and control.get("acceptance") == "accepted"
                and reported_hmma > 0.0
                and as_float(control, "tensor_hmma_inst", -1.0) == 0.0
                and ratio_consistent
                and all(
                    row.get("ncu_replay_mode") == config.ncu_replay_mode
                    and row.get("ncu_cache_control") == config.ncu_cache_control
                    for row in (treatment, control)
                )
                and all(
                    as_float(row, field, 0.0) == 0.0
                    for row in (treatment, control)
                    for field in (
                        "spill_local_read_inst",
                        "spill_local_write_inst",
                        "local_read_bytes",
                        "local_write_bytes",
                    )
                )
                and all(
                    row.get("spill_evidence_source")
                    in {
                        "sass_register_spill_instructions",
                        "local_memory_bytes_zero_inference",
                    }
                    for row in (treatment, control)
                )
                and all(
                    as_float(row, "spill_zero_verified", -1.0) == 1.0
                    for row in (treatment, control)
                )
            )
            if tensor_ncu_ok:
                tensor_hmma_ratio_by_rf[rf] = hmma_per_logical_mma
        tensor_ncu_pass_by_rf[rf] = tensor_ncu_ok
        checks.append(
            result(
                "tensor",
                coord,
                "ncu_hmma_and_spill",
                tensor_ncu_ok,
                (
                    "treatment accepted with HMMA>0 and a valid logical-MMA ratio; "
                    "control accepted with HMMA=0; both local-memory/spill=0; "
                    f"NCU={config.ncu_replay_mode}/{config.ncu_cache_control}"
                ),
                (
                    f"treatment_rows={len(treatment_ncu)}, control_rows={len(control_ncu)}, "
                    f"HMMA={fmt(as_float(treatment_ncu[0], 'tensor_hmma_inst')) if treatment_ncu else 'missing'}/"
                    f"{fmt(as_float(control_ncu[0], 'tensor_hmma_inst')) if control_ncu else 'missing'}; "
                    f"logical_MMA={fmt(as_float(treatment_ncu[0], 'expected_logical_mma')) if treatment_ncu else 'missing'}; "
                    f"HMMA/logical_MMA={fmt(as_float(treatment_ncu[0], 'tensor_hmma_per_logical_mma')) if treatment_ncu else 'missing'}"
                ),
                evidence["ncu_acceptance"],
                "inspect SASS/NCU, rebuild sm_80, and keep the RF out of the coefficient table",
            )
        )

        detail = select(
            matched_detail,
            component="tensor_mma_increment",
            blocks_per_sm=config.blocks_per_sm,
            active_sm=config.active_sm,
            reuse_factor=rf,
            w_sm_kib=2048,
        )
        valid = [row for row in detail if truthy(row.get("valid_component_estimate"))]
        deltas = [as_float(row, "delta_E_J") for row in detail]
        coefficients = [as_float(row, "coefficient") for row in valid]
        treatment_elapsed = [as_float(row, "numerator_elapsed_s") for row in detail]
        control_elapsed = [as_float(row, "control_elapsed_s") for row in detail]
        treatment_net_energy = [
            as_float(row, "numerator_net_E_J") for row in detail
        ]
        control_net_energy = [as_float(row, "control_net_E_J") for row in detail]
        treatment_tflops = [
            as_float(row, "denominator") / elapsed / 1.0e12
            for row, elapsed in zip(detail, treatment_elapsed)
            if elapsed > 0.0 and as_float(row, "denominator") > 0.0
        ]
        tensor_energy_ok = len(detail) == config.expected_repeats
        tensor_energy_ok &= len(valid) >= config.min_valid_repeats
        tensor_energy_ok &= all(
            row.get("pair_energy_basis") == "matched_iters_net_energy"
            and abs(as_float(row, "iter_ratio") - 1.0) <= 1.0e-12
            and as_float(row, "pair_start_distance_ms")
            <= config.max_pair_start_distance_ms
            for row in detail
        )
        tensor_energy_ok &= all(
            elapsed >= 0.8 * config.tensor_control_calibration_min_seconds
            for elapsed in control_elapsed
        )
        tensor_energy_ok &= all(
            elapsed >= 0.8 * config.tensor_treatment_target_seconds
            for elapsed in treatment_elapsed
        )
        tensor_energy_ok &= all(value > 0.0 for value in treatment_net_energy)
        tensor_energy_ok &= all(value > 0.0 for value in control_net_energy)
        tensor_energy_ok &= all(delta >= config.min_delta_j for delta in deltas)
        tensor_energy_ok &= all(value > 0.0 for value in coefficients)
        coefficient_median = median(coefficients)
        tensor_energy_ok &= (
            config.tensor_min_pj_per_flop
            <= coefficient_median
            <= config.tensor_max_pj_per_flop
        )
        if tensor_energy_ok and tensor_ncu_ok and math.isfinite(coefficient_median):
            tensor_coefficient_by_rf[rf] = coefficient_median
        checks.append(
            result(
                "tensor",
                coord,
                "positive_matched_energy",
                tensor_energy_ok,
                (
                    f"{config.expected_repeats} matched-ITER pairs with start distance <= "
                    f"{config.max_pair_start_distance_ms:g} ms; every delta_E >= "
                    f"{config.min_delta_j:g} J; control elapsed >= "
                    f"{0.8 * config.tensor_control_calibration_min_seconds:g} s; "
                    "median within plausibility range"
                ),
                (
                    f"rows={len(detail)}, valid={len(valid)}, delta_min/median="
                    f"{fmt(min(deltas, default=float('nan')))}/{fmt(median(deltas))} J, "
                    f"treatment_elapsed_min={fmt(min(treatment_elapsed, default=float('nan')))} s, "
                    f"control_elapsed_min={fmt(min(control_elapsed, default=float('nan')))} s, "
                    f"treatment/control_net_power_median="
                    f"{fmt(median(energy / elapsed for energy, elapsed in zip(treatment_net_energy, treatment_elapsed) if elapsed > 0.0))}/"
                    f"{fmt(median(energy / elapsed for energy, elapsed in zip(control_net_energy, control_elapsed) if elapsed > 0.0))} W, "
                    f"treatment_throughput_median={fmt(median(treatment_tflops))} TFLOP/s, "
                    f"coefficient_median={fmt(coefficient_median)} pJ/FLOP"
                ),
                evidence["matched_detail"],
                "do not relax the delta gate; rerun the affected RF after checking clocks and pair adjacency",
            )
        )

    hmma_ratios = list(tensor_hmma_ratio_by_rf.values())
    hmma_ratio_center = median(hmma_ratios)
    hmma_ratio_spread = (
        (max(hmma_ratios) - min(hmma_ratios)) / hmma_ratio_center
        if len(hmma_ratios) == len(config.expected_rf) and hmma_ratio_center > 0.0
        else float("inf")
    )
    hmma_linearity_ok = (
        len(hmma_ratios) == len(config.expected_rf)
        and hmma_ratio_spread <= config.tensor_hmma_ratio_relative_spread_max
    )
    checks.append(
        result(
            "tensor",
            "RF1-16",
            "hmma_logical_mma_linearity",
            hmma_linearity_ok,
            (
                "all RF points expose a positive HMMA/logical-MMA ratio with "
                f"relative spread <= {100 * config.tensor_hmma_ratio_relative_spread_max:g}%"
            ),
            (
                "ratios="
                + ",".join(
                    f"RF{rf}:{fmt(tensor_hmma_ratio_by_rf.get(rf, float('nan')))}"
                    for rf in config.expected_rf
                )
                + f"; relative_spread={fmt(100 * hmma_ratio_spread)}%"
            ),
            evidence["ncu_acceptance"],
            "reject the Tensor denominator or inspect architecture-specific WMMA-to-HMMA lowering",
        )
    )

    tensor_coefficients = list(tensor_coefficient_by_rf.values())
    tensor_coefficient_center = median(tensor_coefficients)
    tensor_coefficient_spread = (
        (max(tensor_coefficients) - min(tensor_coefficients))
        / tensor_coefficient_center
        if len(tensor_coefficients) == len(config.expected_rf)
        and tensor_coefficient_center > 0.0
        else float("inf")
    )
    tensor_stability_ok = (
        len(tensor_coefficients) == len(config.expected_rf)
        and tensor_coefficient_spread
        <= config.tensor_coefficient_relative_spread_max
    )
    checks.append(
        result(
            "tensor",
            "RF1-16",
            "effective_coefficient_rf_stability",
            tensor_stability_ok,
            (
                "all RF medians are positive and their relative range is <= "
                f"{100 * config.tensor_coefficient_relative_spread_max:g}%"
            ),
            (
                "medians="
                + ",".join(
                    f"RF{rf}:{fmt(tensor_coefficient_by_rf.get(rf, float('nan')))}pJ/FLOP"
                    for rf in config.expected_rf
                )
                + f"; relative_range={fmt(100 * tensor_coefficient_spread)}%"
            ),
            evidence["matched_detail"],
            "report RF dependence as a range and rerun unstable points; do not force an RTX 3090 match",
        )
    )

    l2_ncu_pass_by_w: dict[int, bool] = {}
    for w_sm_kib in config.expected_l2_w:
        coord = f"W{w_sm_kib}/B{config.l2_blocks_per_sm}"
        raw_by_mode_lr = {
            (mode, lr): select(
                l2_raw,
                mode=mode,
                blocks_per_sm=config.l2_blocks_per_sm,
                active_sm=config.active_sm,
                load_repeat=lr,
                w_sm_kib=w_sm_kib,
            )
            for mode in ("global_addr_only", "l2_cg_load_only")
            for lr in config.energy_load_repeats
        }
        raw_ok = all(
            len(items) == config.expected_repeats
            for items in raw_by_mode_lr.values()
        )
        raw_ok &= all(
            row.get("energy_source") == "nvml_total_energy"
            and row.get("energy_integration_method") == "total_energy_mj_delta"
            and row.get("measurement_scope") == "gpu_device_total_energy_counter"
            and f"global_warmup_passes={config.global_warmup_passes}" in row.get("notes", "")
            and f"l2_residency_policy={config.l2_residency_policy}" in row.get("notes", "")
            and f"l2_address_layout={config.l2_address_layout}" in row.get("notes", "")
            and (
                row.get("mode") != "l2_cg_load_only"
                or (
                    CG_MARKER in row.get("notes", "")
                    and L2_REVISION_MARKER in row.get("notes", "")
                )
            )
            for items in raw_by_mode_lr.values()
            for row in items
        )
        checks.append(
            result(
                "l2",
                coord,
                "raw_pair_scope_and_revision",
                raw_ok,
                (
                    f"{config.expected_repeats} rows/mode/LR with total-energy scope; "
                    "CG treatment carries the current warm-up/replay revision and "
                    f"all rows use {config.l2_residency_policy} residency with "
                    f"{config.global_warmup_passes} warm-up passes"
                ),
                "counts=" + ",".join(
                    f"{mode}/LR{lr}:{len(items)}"
                    for (mode, lr), items in raw_by_mode_lr.items()
                ),
                evidence["l2_raw"],
                "clean rebuild and rerun the L2 pair sweep without appending to stale CSVs",
            )
        )
        rows = select(
            ncu_acceptance,
            mode="l2_cg_load_only",
            blocks_per_sm=config.l2_blocks_per_sm,
            active_sm=config.active_sm,
            w_sm_kib=w_sm_kib,
        )
        control_rows = select(
            ncu_acceptance,
            mode="global_addr_only",
            blocks_per_sm=config.l2_blocks_per_sm,
            active_sm=config.active_sm,
            w_sm_kib=w_sm_kib,
        )
        by_lr = {lr: select(rows, load_repeat=lr) for lr in config.ncu_load_repeats}
        control_by_lr = {
            lr: select(control_rows, load_repeat=lr)
            for lr in config.ncu_load_repeats
        }
        path_ok = all(len(items) == 1 for items in by_lr.values())
        path_ok &= all(len(items) == 1 for items in control_by_lr.values())
        path_rates: list[float] = []
        native_path_rates: list[float] = []
        native_derived_deltas: list[float] = []
        sector_conservation_ratios: list[float] = []
        traffic_expected_ratios: list[float] = []
        persisting_sizes: list[float] = []
        l1_rates: list[float] = []
        hit_byte_ratios: list[float] = []
        dram_ratios: list[float] = []
        control_dram_ratios: list[float] = []
        for lr, items in by_lr.items():
            if len(items) != 1:
                continue
            row = items[0]
            l1_path = as_float(row, "l1_path_hit_rate_pct")
            l2_path = as_float(row, "l2_path_hit_rate_pct")
            l2_native_path = as_float(row, "l2_native_read_hit_rate_pct")
            native_derived_delta = as_float(
                row, "l2_native_vs_derived_hit_delta_pct"
            )
            sector_conservation = as_float(
                row, "l2_read_sector_conservation_ratio"
            )
            traffic_expected_ratio = as_float(row, "l2_read_bytes_to_expected")
            persisting_size = as_float(
                row, "launch_persisting_l2_cache_size_bytes", 0.0
            )
            l1_request = as_float(row, "l1_request_bytes", 0.0)
            l1_hit = as_float(row, "l1_hit_bytes", 0.0)
            l2_read = as_float(row, "l2_read_bytes", 0.0)
            dram = as_float(row, "dram_bytes", 0.0)
            hit_ratio = l1_hit / l1_request if l1_request > 0.0 else float("inf")
            dram_ratio = dram / l2_read if l2_read > 0.0 else float("inf")
            path_rates.append(l2_path)
            native_path_rates.append(l2_native_path)
            native_derived_deltas.append(native_derived_delta)
            sector_conservation_ratios.append(sector_conservation)
            traffic_expected_ratios.append(traffic_expected_ratio)
            persisting_sizes.append(persisting_size)
            l1_rates.append(l1_path)
            hit_byte_ratios.append(hit_ratio)
            dram_ratios.append(dram_ratio)
            path_ok &= (
                row.get("acceptance") == "accepted"
                and row.get("ncu_replay_mode") == config.ncu_replay_mode
                and row.get("ncu_cache_control") == config.ncu_cache_control
                and row.get("l2_residency_policy")
                == config.l2_residency_policy
                and row.get("l2_address_layout") == config.l2_address_layout
                and as_int(row, "global_warmup_passes")
                == config.global_warmup_passes
                and 0.0 <= l1_path <= config.l1_path_hit_max_pct
                and hit_ratio <= config.l1_hit_bytes_ratio_max
                and l2_path >= config.l2_path_hit_min_pct
                and l2_native_path >= config.l2_path_hit_min_pct
                and native_derived_delta
                <= config.l2_native_derived_hit_delta_max_pct
                and 1.0 - config.l2_sector_conservation_tolerance
                <= sector_conservation
                <= 1.0 + config.l2_sector_conservation_tolerance
                and 0.95 <= traffic_expected_ratio <= 1.05
                and dram_ratio <= config.dram_to_l2_bytes_max
                and (
                    config.l2_residency_policy != "persisting"
                    or persisting_size > 0.0
                )
            )
            controls = control_by_lr[lr]
            if len(controls) != 1:
                continue
            control = controls[0]
            control_expected = expected_memory_path_bytes(control)
            control_dram_ratio = (
                as_float(control, "dram_bytes", 0.0) / control_expected
                if control_expected > 0.0
                else float("inf")
            )
            control_dram_ratios.append(control_dram_ratio)
            path_ok &= (
                control.get("acceptance") == "accepted"
                and control.get("ncu_replay_mode") == config.ncu_replay_mode
                and control.get("ncu_cache_control") == config.ncu_cache_control
                and control.get("l2_residency_policy")
                == config.l2_residency_policy
                and control.get("l2_address_layout") == config.l2_address_layout
                and as_int(control, "global_warmup_passes")
                == config.global_warmup_passes
                and as_float(control, "l1_request_bytes", -1.0) == 0.0
                and control_dram_ratio <= config.address_control_dram_ratio_max
            )
        l2_ncu_pass_by_w[w_sm_kib] = path_ok
        checks.append(
            result(
                "l2",
                coord,
                "ncu_path_specific_hit",
                path_ok,
                (
                    f"treatment/control all LR accepted; control L1 request=0 and DRAM/expected <= "
                    f"{100 * config.address_control_dram_ratio_max:g}%; L1 path hit <= {config.l1_path_hit_max_pct:g}%; "
                    f"L1 hit/request <= {100 * config.l1_hit_bytes_ratio_max:g}%; "
                    f"derived/native L2 read hit >= {config.l2_path_hit_min_pct:g}%, "
                    f"delta <= {config.l2_native_derived_hit_delta_max_pct:g}pp, "
                    f"sector conservation=1+/-{100 * config.l2_sector_conservation_tolerance:g}%; "
                    f"NCU={config.ncu_replay_mode}/{config.ncu_cache_control}; "
                    f"residency={config.l2_residency_policy}; layout={config.l2_address_layout}; "
                    f"traffic/expected=1+/-5%; warm-up={config.global_warmup_passes}"
                ),
                (
                    f"treatment_LR_rows={','.join(f'{lr}:{len(items)}' for lr, items in by_lr.items())}; "
                    f"control_LR_rows={','.join(f'{lr}:{len(items)}' for lr, items in control_by_lr.items())}; "
                    f"control_DRAM/expected_max={fmt(100 * max(control_dram_ratios, default=float('nan')))}%; "
                    f"L1_path_max={fmt(max(l1_rates, default=float('nan')))}%; "
                    f"L1_hit/request_max={fmt(100 * max(hit_byte_ratios, default=float('nan')))}%; "
                    f"L2_path_min={fmt(min(path_rates, default=float('nan')))}%; "
                    f"L2_native_min={fmt(min(native_path_rates, default=float('nan')))}%; "
                    f"native_delta_max={fmt(max(native_derived_deltas, default=float('nan')))}pp; "
                    f"sector_conservation_min/max={fmt(min(sector_conservation_ratios, default=float('nan')))}/"
                    f"{fmt(max(sector_conservation_ratios, default=float('nan')))}; "
                    f"traffic/expected_min/max={fmt(min(traffic_expected_ratios, default=float('nan')))}/"
                    f"{fmt(max(traffic_expected_ratios, default=float('nan')))}; "
                    f"persisting_size_min={fmt(min(persisting_sizes, default=float('nan')))}B; "
                    f"DRAM/L2_max={fmt(100 * max(dram_ratios, default=float('nan')))}%"
                ),
                evidence["ncu_acceptance"],
                "reject this W point; inspect path-specific counters instead of aggregate L1 request traffic",
            )
        )

    l2_energy_candidates: dict[int, float] = {}
    for w_sm_kib in config.expected_l2_w:
        coord = f"W{w_sm_kib}/B{config.l2_blocks_per_sm}"
        rows = select(
            matched_detail,
            component="l2_hit_cg_path",
            blocks_per_sm=config.l2_blocks_per_sm,
            active_sm=config.active_sm,
            w_sm_kib=w_sm_kib,
        )
        by_lr = {lr: select(rows, load_repeat=lr) for lr in config.energy_load_repeats}
        valid_by_lr = {
            lr: [row for row in items if truthy(row.get("valid_component_estimate"))]
            for lr, items in by_lr.items()
        }
        expected_rows = config.expected_repeats * len(config.energy_load_repeats)
        deltas = [as_float(row, "delta_E_J") for row in rows]
        valid_rows = [
            row for row in rows if truthy(row.get("valid_component_estimate"))
        ]
        pbit = [as_float(row, "coefficient_pJ_per_bit") for row in valid_rows]
        energy_ok = len(rows) == expected_rows
        energy_ok &= all(
            len(valid_by_lr[lr]) >= config.min_valid_repeats
            for lr in config.energy_load_repeats
        )
        energy_ok &= all(delta >= config.min_delta_j for delta in deltas)
        energy_ok &= bool(pbit) and all(value > 0.0 for value in pbit)
        energy_ok &= all(
            row.get("denominator_source") == "ncu_actual_exact" for row in rows
        )
        pbit_median = median(pbit)
        if energy_ok and l2_ncu_pass_by_w.get(w_sm_kib, False):
            l2_energy_candidates[w_sm_kib] = pbit_median
        checks.append(
            result(
                "l2",
                coord,
                "positive_ncu_denominated_energy",
                energy_ok,
                (
                    f"{expected_rows} rows; >= {config.min_valid_repeats} valid/LR; "
                    f"every delta_E >= {config.min_delta_j:g} J; exact NCU denominator"
                ),
                (
                    f"rows={len(rows)}, valid_by_LR="
                    f"{','.join(f'{lr}:{len(items)}' for lr, items in valid_by_lr.items())}; "
                    f"delta_min/median={fmt(min(deltas, default=float('nan')))}/{fmt(median(deltas))} J; "
                    f"coefficient_median={fmt(pbit_median)} pJ/bit"
                ),
                evidence["matched_detail"],
                "rerun this W/LR coordinate or keep it out of L2 plateau selection",
            )
        )

    ordered_candidates = [
        (w_sm_kib, l2_energy_candidates[w_sm_kib])
        for w_sm_kib in config.expected_l2_w
        if w_sm_kib in l2_energy_candidates
    ]
    adjacent = []
    for w_a, w_b in zip(config.expected_l2_w, config.expected_l2_w[1:]):
        if w_a not in l2_energy_candidates or w_b not in l2_energy_candidates:
            continue
        coeff_a = l2_energy_candidates[w_a]
        coeff_b = l2_energy_candidates[w_b]
        center = (abs(coeff_a) + abs(coeff_b)) / 2.0
        spread = abs(coeff_a - coeff_b) / center if center > 0.0 else float("inf")
        adjacent.append((spread, w_a, w_b, coeff_a, coeff_b))
    best = min(adjacent, default=None)
    plateau_ok = best is not None and best[0] <= config.plateau_relative_spread_max
    checks.append(
        result(
            "l2",
            "plateau",
            "adjacent_working_set_plateau",
            plateau_ok,
            (
                "at least two adjacent W points pass NCU and energy gates with relative "
                f"coefficient spread <= {100 * config.plateau_relative_spread_max:g}%"
            ),
            (
                "candidates=" + ",".join(
                    f"W{w}:{fmt(value)}pJ/bit" for w, value in ordered_candidates
                )
                + (
                    f"; best=W{best[1]}-W{best[2]}:{100 * best[0]:.3g}%"
                    if best
                    else "; best=none"
                )
            ),
            evidence["matched_detail"] + ";" + evidence["ncu_acceptance"],
            "collect more repeats or reject W points whose path counters/coefficients do not form a plateau",
        )
    )

    prerequisite_checks = [row for row in checks if row["area"] != "overall"]
    failures = [row for row in prerequisite_checks if row["status"] != "pass"]
    overall_ok = not failures and all(tensor_ncu_pass_by_rf.values()) and plateau_ok
    checks.append(
        result(
            "overall",
            "a100_tensor_l2",
            "remediation_verdict",
            overall_ok,
            "all RF points pass and an adjacent L2 plateau is accepted",
            (
                f"failed_or_missing_checks={len(failures)}; accepted_L2_W="
                f"{','.join(str(w) for w in sorted(l2_energy_candidates)) or 'none'}"
            ),
            ";".join(evidence.values()),
            "do not publish A100 Tensor/L2 coefficients until this row is pass",
        )
    )
    return checks


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: str, rows: list[dict[str, str]], csv_path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    overall = next(row for row in rows if row["check"] == "remediation_verdict")
    with out.open("w", encoding="utf-8") as f:
        f.write("# A100 Tensor/L2 Remediation Audit\n\n")
        f.write(f"- verdict: **{overall['status']}**\n")
        f.write(f"- detail CSV: `{csv_path}`\n\n")
        f.write("| area | coordinate | check | status | expected | actual |\n")
        f.write("|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['area']}` | `{row['coordinate']}` | `{row['check']}` | "
                f"`{row['status']}` | {row['expected']} | {row['actual']} |\n"
            )
        f.write("\n## Interpretation\n\n")
        f.write(
            "- Tensor passes only when every RF records treatment/control-floor "
            "candidate ITERs, applies their maximum to both modes, meets the actual "
            "control-duration floor, keeps control/treatment adjacent, has an "
            "HMMA-free control and spill-free kernels, produces positive energy "
            "above the configured noise floor, and keeps HMMA/logical-MMA lowering "
            "linear across RF.\n"
        )
        f.write(
            "- The Tensor coefficient is checked for RF stability but is not forced "
            "to match a historical RTX 3090 number. Cross-architecture SASS lowering, "
            "clock/power behavior, and measurement protocol must be audited first.\n"
        )
        f.write(
            "- `.cg` requests still pass through L1TEX. Therefore L1 request bytes "
            "can be similar to L2 read bytes without being L1 cache hits. This audit "
            "uses global-load lookup hit bytes/rate, not aggregate L1 traffic.\n"
        )
        f.write(
            "- A single accepted L2 point is not enough. Two adjacent working-set "
            "points must pass path counters and produce a stable pJ/bit plateau.\n"
        )
        f.write(
            "- L2 evidence must use application replay, cache-control none, four "
            "in-application CG warm-up passes, and the residency policy selected by "
            "the precheck. Persisting results describe a residency-managed path, not "
            "universal default-cache behavior.\n"
        )
        f.write(
            "- These are NCU-validated, workload-dependent board-level effective "
            "coefficients, not direct Tensor Core or SRAM transistor-level energy.\n"
        )


def synthetic_data(config: AuditConfig) -> tuple[list[dict[str, str]], ...]:
    tensor_raw: list[dict[str, str]] = []
    l2_raw: list[dict[str, str]] = []
    calibration: list[dict[str, str]] = []
    ncu: list[dict[str, str]] = []
    detail: list[dict[str, str]] = []
    for rf in config.expected_rf:
        calibration.append(
            {
                "treatment_target_seconds": str(
                    config.tensor_treatment_target_seconds
                ),
                "control_min_seconds": str(
                    config.tensor_control_calibration_min_seconds
                ),
                "treatment_calibrated_iters": "900",
                "control_min_calibrated_iters": "1000",
                "resolved_iters": "1000",
                "resolution_policy": "max_treatment_and_control_min_iters",
                "treatment_calibration_command": (
                    "benchmark --mode reg_mma --seconds 20 --calibrate-only"
                ),
                "control_calibration_command": (
                    "benchmark --mode reg_operand_only --seconds 2 --calibrate-only"
                ),
                "reuse_factor": str(rf),
                "blocks_per_SM": str(config.blocks_per_sm),
                "active_SM": str(config.active_sm),
                "status": "pair_locked",
            }
        )
        for mode in ("reg_operand_only", "reg_mma"):
            for _ in range(config.expected_repeats):
                tensor_raw.append(
                    {
                        "mode": mode,
                        "ITER": "1000",
                        "reuse_factor": str(rf),
                        "blocks_per_SM": str(config.blocks_per_sm),
                        "active_SM": str(config.active_sm),
                        "W_SM_KiB": "2048",
                        "notes": TENSOR_MARKER,
                        "energy_source": "nvml_total_energy",
                        "energy_integration_method": "total_energy_mj_delta",
                        "measurement_scope": "gpu_device_total_energy_counter",
                    }
                )
            logical_mma = config.active_sm * config.blocks_per_sm * 100000 * rf
            ncu.append(
                {
                    "mode": mode,
                    "acceptance": "accepted",
                    "W_SM_KiB": "2048",
                    "blocks_per_SM": str(config.blocks_per_sm),
                    "active_SM": str(config.active_sm),
                    "reuse_factor": str(rf),
                    "load_repeat": "1",
                    "ncu_replay_mode": config.ncu_replay_mode,
                    "ncu_cache_control": config.ncu_cache_control,
                    "global_warmup_passes": str(config.global_warmup_passes),
                    "l2_residency_policy": "normal",
                    "l2_address_layout": "contiguous",
                    "tensor_hmma_inst": (
                        str(4 * logical_mma) if mode == "reg_mma" else "0"
                    ),
                    "expected_logical_mma": (
                        str(logical_mma) if mode == "reg_mma" else ""
                    ),
                    "tensor_hmma_per_logical_mma": (
                        "4" if mode == "reg_mma" else ""
                    ),
                    "local_read_bytes": "0",
                    "local_write_bytes": "0",
                    "spill_local_read_inst": "0",
                    "spill_local_write_inst": "0",
                    "spill_zero_verified": "1",
                    "spill_evidence_source": "local_memory_bytes_zero_inference",
                    "l1_path_hit_rate_pct": "0",
                    "l2_path_hit_rate_pct": "0",
                    "l2_native_read_hit_rate_pct": "",
                    "l2_native_vs_derived_hit_delta_pct": "",
                    "l2_read_sector_conservation_ratio": "",
                    "l2_read_bytes_to_expected": "",
                    "l1_request_bytes": "0",
                    "l1_hit_bytes": "0",
                    "l2_read_bytes": "0",
                    "l2_read_miss_bytes": "0",
                    "dram_read_bytes": "0",
                    "dram_bytes": "0",
                    "launch_persisting_l2_cache_size_bytes": "0",
                }
            )
        for _ in range(config.expected_repeats):
            detail.append(
                {
                    "component": "tensor_mma_increment",
                    "blocks_per_SM": str(config.blocks_per_sm),
                    "active_SM": str(config.active_sm),
                    "reuse_factor": str(rf),
                    "load_repeat": "1",
                    "W_SM_KiB": "2048",
                    "pair_energy_basis": "matched_iters_net_energy",
                    "iter_ratio": "1",
                    "run_order_distance": "1",
                    "pair_start_distance_ms": "1",
                    "control_elapsed_s": str(
                        config.tensor_control_calibration_min_seconds
                    ),
                    "numerator_elapsed_s": str(
                        config.tensor_treatment_target_seconds
                    ),
                    "numerator_net_E_J": "30",
                    "control_net_E_J": "10",
                    "delta_E_J": "20",
                    "coefficient": "0.2",
                    "coefficient_pJ_per_bit": "",
                    "denominator_source": "logical_or_expected",
                    "valid_component_estimate": "True",
                }
            )
    for index, w_sm_kib in enumerate(config.expected_l2_w):
        pbit = 0.8 * (1.0 + 0.05 * index)
        for lr in config.ncu_load_repeats:
            expected_bytes = (
                config.active_sm * config.l2_blocks_per_sm * 100000 * lr * 1024
            )
            ncu.append(
                {
                    "mode": "global_addr_only",
                    "acceptance": "accepted",
                    "W_SM_KiB": str(w_sm_kib),
                    "blocks_per_SM": str(config.l2_blocks_per_sm),
                    "active_SM": str(config.active_sm),
                    "ITER": "100000",
                    "reuse_factor": "1",
                    "load_repeat": str(lr),
                    "ncu_replay_mode": config.ncu_replay_mode,
                    "ncu_cache_control": config.ncu_cache_control,
                    "global_warmup_passes": str(config.global_warmup_passes),
                    "l2_residency_policy": config.l2_residency_policy,
                    "l2_address_layout": config.l2_address_layout,
                    "tensor_hmma_inst": "0",
                    "expected_logical_mma": "",
                    "tensor_hmma_per_logical_mma": "",
                    "local_read_bytes": "0",
                    "local_write_bytes": "0",
                    "spill_local_read_inst": "0",
                    "spill_local_write_inst": "0",
                    "spill_zero_verified": "1",
                    "spill_evidence_source": "local_memory_bytes_zero_inference",
                    "l1_path_hit_rate_pct": "0",
                    "l2_path_hit_rate_pct": "0",
                    "l2_native_read_hit_rate_pct": "0",
                    "l2_native_vs_derived_hit_delta_pct": "0",
                    "l2_read_sector_conservation_ratio": "1",
                    "l2_read_bytes_to_expected": "1",
                    "l1_request_bytes": "0",
                    "l1_hit_bytes": "0",
                    "l2_read_bytes": "0",
                    "l2_read_miss_bytes": "0",
                    "dram_read_bytes": str(expected_bytes * 0.0005),
                    "dram_bytes": str(expected_bytes * 0.0005),
                    "launch_persisting_l2_cache_size_bytes": "34603008",
                }
            )
            ncu.append(
                {
                    "mode": "l2_cg_load_only",
                    "acceptance": "accepted",
                    "W_SM_KiB": str(w_sm_kib),
                    "blocks_per_SM": str(config.l2_blocks_per_sm),
                    "active_SM": str(config.active_sm),
                    "ITER": "100000",
                    "reuse_factor": "1",
                    "load_repeat": str(lr),
                    "ncu_replay_mode": config.ncu_replay_mode,
                    "ncu_cache_control": config.ncu_cache_control,
                    "global_warmup_passes": str(config.global_warmup_passes),
                    "l2_residency_policy": config.l2_residency_policy,
                    "l2_address_layout": config.l2_address_layout,
                    "tensor_hmma_inst": "0",
                    "expected_logical_mma": "",
                    "tensor_hmma_per_logical_mma": "",
                    "local_read_bytes": "0",
                    "local_write_bytes": "0",
                    "spill_local_read_inst": "0",
                    "spill_local_write_inst": "0",
                    "spill_zero_verified": "1",
                    "spill_evidence_source": "local_memory_bytes_zero_inference",
                    "l1_path_hit_rate_pct": "0",
                    "l2_path_hit_rate_pct": "99",
                    "l2_native_read_hit_rate_pct": "99.2",
                    "l2_native_vs_derived_hit_delta_pct": "0.2",
                    "l2_read_sector_conservation_ratio": "1",
                    "l2_read_bytes_to_expected": "1",
                    "l1_request_bytes": "100000",
                    "l1_hit_bytes": "0",
                    "l2_read_bytes": "100000",
                    "l2_read_miss_bytes": "1000",
                    "dram_read_bytes": "1000",
                    "dram_bytes": "1000",
                    "launch_persisting_l2_cache_size_bytes": "34603008",
                }
            )
        for lr in config.energy_load_repeats:
            for _ in range(config.expected_repeats):
                for mode in ("global_addr_only", "l2_cg_load_only"):
                    l2_raw.append(
                        {
                            "mode": mode,
                            "load_repeat": str(lr),
                            "W_SM_KiB": str(w_sm_kib),
                            "blocks_per_SM": str(config.l2_blocks_per_sm),
                            "active_SM": str(config.active_sm),
                            "notes": (
                                f"global_warmup_passes={config.global_warmup_passes};"
                                f"l2_residency_policy={config.l2_residency_policy};"
                                f"l2_address_layout={config.l2_address_layout};"
                                + (
                                    f"{CG_MARKER};{L2_REVISION_MARKER};"
                                    if mode == "l2_cg_load_only"
                                    else ""
                                )
                            ),
                            "energy_source": "nvml_total_energy",
                            "energy_integration_method": "total_energy_mj_delta",
                            "measurement_scope": "gpu_device_total_energy_counter",
                        }
                    )
                detail.append(
                    {
                        "component": "l2_hit_cg_path",
                        "blocks_per_SM": str(config.l2_blocks_per_sm),
                        "active_SM": str(config.active_sm),
                        "reuse_factor": "1",
                        "load_repeat": str(lr),
                        "W_SM_KiB": str(w_sm_kib),
                        "pair_energy_basis": "duration_scaled_control_power",
                        "iter_ratio": "1",
                        "run_order_distance": "1",
                        "pair_start_distance_ms": "1",
                        "numerator_elapsed_s": "20",
                        "control_elapsed_s": "20",
                        "numerator_net_E_J": "30",
                        "control_net_E_J": "10",
                        "delta_E_J": "20",
                        "coefficient": str(pbit * 8.0),
                        "coefficient_pJ_per_bit": str(pbit),
                        "denominator_source": "ncu_actual_exact",
                        "valid_component_estimate": "True",
                    }
                )
    return tensor_raw, l2_raw, calibration, ncu, detail


def run_self_test() -> None:
    config = AuditConfig(
        expected_rf=(1, 4),
        expected_l2_w=(16, 32, 64),
        ncu_load_repeats=(1, 4, 16),
        energy_load_repeats=(4, 8, 16),
        blocks_per_sm=16,
        l2_blocks_per_sm=16,
        active_sm=108,
        expected_repeats=2,
        min_valid_repeats=2,
        tensor_treatment_target_seconds=20.0,
        tensor_control_calibration_min_seconds=2.0,
        min_delta_j=10.0,
        tensor_min_pj_per_flop=0.01,
        tensor_max_pj_per_flop=5.0,
        tensor_hmma_ratio_relative_spread_max=0.10,
        tensor_coefficient_relative_spread_max=0.75,
        max_pair_start_distance_ms=30000.0,
        ncu_replay_mode="application",
        ncu_cache_control="none",
        l2_residency_policy="persisting",
        l2_address_layout="sm_interleaved",
        global_warmup_passes=4,
        l1_path_hit_max_pct=1.0,
        l1_hit_bytes_ratio_max=0.01,
        l2_path_hit_min_pct=95.0,
        l2_native_derived_hit_delta_max_pct=2.0,
        l2_sector_conservation_tolerance=0.02,
        dram_to_l2_bytes_max=0.02,
        address_control_dram_ratio_max=0.001,
        plateau_relative_spread_max=0.35,
    )
    data = synthetic_data(config)
    evidence = {name: f"selftest_{name}.csv" for name in (
        "tensor_raw", "l2_raw", "calibration", "ncu_acceptance", "matched_detail"
    )}
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=data[3],
        matched_detail=data[4],
        evidence=evidence,
    )
    assert rows[-1]["status"] == "pass", rows[-1]

    bad_tensor = [dict(row) for row in data[4]]
    bad = next(row for row in bad_tensor if row["component"] == "tensor_mma_increment" and row["reuse_factor"] == "4")
    bad["delta_E_J"] = "-1"
    bad["coefficient"] = "-0.01"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=data[3],
        matched_detail=bad_tensor,
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "B16/RF4"
        and row["check"] == "positive_matched_energy"
        and row["status"] == "fail"
        for row in rows
    )

    nonlinear_ncu = [dict(row) for row in data[3]]
    nonlinear = next(
        row
        for row in nonlinear_ncu
        if row["mode"] == "reg_mma" and row["reuse_factor"] == "4"
    )
    nonlinear["tensor_hmma_inst"] = str(
        2 * as_int(nonlinear, "expected_logical_mma")
    )
    nonlinear["tensor_hmma_per_logical_mma"] = "2"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=nonlinear_ncu,
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["check"] == "hmma_logical_mma_linearity"
        and row["status"] == "fail"
        for row in rows
    )

    bad_calibration = [dict(row) for row in data[2]]
    bad = next(row for row in bad_calibration if row["reuse_factor"] == "4")
    bad["control_min_calibrated_iters"] = "1200"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=bad_calibration,
        ncu_acceptance=data[3],
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "B16/RF4"
        and row["check"] == "pair_calibration"
        and row["status"] == "fail"
        for row in rows
    )

    short_control = [dict(row) for row in data[4]]
    bad = next(
        row
        for row in short_control
        if row["component"] == "tensor_mma_increment"
        and row["reuse_factor"] == "4"
    )
    bad["control_elapsed_s"] = "0.5"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=data[3],
        matched_detail=short_control,
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "B16/RF4"
        and row["check"] == "positive_matched_energy"
        and row["status"] == "fail"
        for row in rows
    )

    bad_ncu = [dict(row) for row in data[3]]
    bad = next(row for row in bad_ncu if row["mode"] == "l2_cg_load_only" and row["W_SM_KiB"] == "32")
    bad["l2_path_hit_rate_pct"] = "72"
    bad["acceptance"] = "reject"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=bad_ncu,
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "W32/B16"
        and row["check"] == "ncu_path_specific_hit"
        and row["status"] == "fail"
        for row in rows
    )
    assert any(
        row["coordinate"] == "plateau"
        and row["check"] == "adjacent_working_set_plateau"
        and row["status"] == "fail"
        for row in rows
    )

    bad_crosscheck = [dict(row) for row in data[3]]
    bad = next(
        row
        for row in bad_crosscheck
        if row["mode"] == "l2_cg_load_only"
        and row["W_SM_KiB"] == "32"
        and row["load_repeat"] == "4"
    )
    bad["l2_native_vs_derived_hit_delta_pct"] = "5"
    bad["l2_read_sector_conservation_ratio"] = "0.8"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=bad_crosscheck,
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "W32/B16"
        and row["check"] == "ncu_path_specific_hit"
        and row["status"] == "fail"
        for row in rows
    )

    bad_control = [dict(row) for row in data[3]]
    bad = next(
        row
        for row in bad_control
        if row["mode"] == "global_addr_only"
        and row["W_SM_KiB"] == "16"
        and row["load_repeat"] == "1"
    )
    bad["l1_request_bytes"] = "32"
    bad["acceptance"] = "rejected"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=bad_control,
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "W16/B16"
        and row["check"] == "ncu_path_specific_hit"
        and row["status"] == "fail"
        for row in rows
    )

    bad_replay = [dict(row) for row in data[3]]
    bad = next(
        row
        for row in bad_replay
        if row["mode"] == "l2_cg_load_only" and row["W_SM_KiB"] == "16"
    )
    bad["ncu_replay_mode"] = "kernel"
    rows = audit_data(
        config,
        tensor_raw=data[0],
        l2_raw=data[1],
        calibration=data[2],
        ncu_acceptance=bad_replay,
        matched_detail=data[4],
        evidence=evidence,
    )
    assert any(
        row["coordinate"] == "W16/B16"
        and row["check"] == "ncu_path_specific_hit"
        and row["status"] == "fail"
        for row in rows
    )
    print("A100 Tensor/L2 remediation audit self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tensor-raw")
    parser.add_argument("--l2-raw")
    parser.add_argument("--pair-calibration")
    parser.add_argument("--ncu-acceptance")
    parser.add_argument("--matched-detail")
    parser.add_argument("--expected-rf", default="1,2,4,8,16")
    parser.add_argument("--expected-l2-w", default="16,32,64,128")
    parser.add_argument("--ncu-load-repeats", default="1,2,4,8,16")
    parser.add_argument("--energy-load-repeats", default="4,8,16")
    parser.add_argument("--blocks-per-sm", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--tensor-blocks-per-sm", type=int, default=16)
    parser.add_argument("--l2-blocks-per-sm", type=int, default=16)
    parser.add_argument("--active-sm", type=int, default=108)
    parser.add_argument("--expected-repeats", type=int, default=7)
    parser.add_argument("--min-valid-repeats", type=int, default=5)
    parser.add_argument("--tensor-treatment-target-seconds", type=float, default=20.0)
    parser.add_argument(
        "--tensor-control-calibration-min-seconds", type=float, default=2.0
    )
    parser.add_argument("--min-delta-j", type=float, default=10.0)
    parser.add_argument("--tensor-min-pj-per-flop", type=float, default=0.01)
    parser.add_argument("--tensor-max-pj-per-flop", type=float, default=5.0)
    parser.add_argument(
        "--tensor-hmma-ratio-relative-spread-max", type=float, default=0.10
    )
    parser.add_argument(
        "--tensor-coefficient-relative-spread-max", type=float, default=0.75
    )
    parser.add_argument("--max-pair-start-distance-ms", type=float, default=30000.0)
    parser.add_argument(
        "--ncu-replay-mode", choices=("application", "kernel"), default="application"
    )
    parser.add_argument(
        "--ncu-cache-control", choices=("none", "all"), default="none"
    )
    parser.add_argument(
        "--l2-residency-policy",
        choices=("normal", "persisting"),
        default="persisting",
    )
    parser.add_argument(
        "--l2-address-layout",
        choices=("contiguous", "sm_interleaved"),
        default="contiguous",
    )
    parser.add_argument("--global-warmup-passes", type=int, default=4)
    parser.add_argument("--l1-path-hit-max-pct", type=float, default=1.0)
    parser.add_argument("--l1-hit-bytes-ratio-max", type=float, default=0.01)
    parser.add_argument("--l2-path-hit-min-pct", type=float, default=95.0)
    parser.add_argument(
        "--l2-native-derived-hit-delta-max-pct", type=float, default=2.0
    )
    parser.add_argument(
        "--l2-sector-conservation-tolerance", type=float, default=0.02
    )
    parser.add_argument("--dram-to-l2-bytes-max", type=float, default=0.02)
    parser.add_argument("--address-control-dram-ratio-max", type=float, default=0.001)
    parser.add_argument("--plateau-relative-spread-max", type=float, default=0.35)
    parser.add_argument(
        "--out-csv",
        default="results/summary/a100_tensor_l2_remediation_audit.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/a100_tensor_l2_remediation_audit.md",
    )
    parser.add_argument("--fail-on-fail", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    required_paths = {
        "tensor_raw": args.tensor_raw,
        "l2_raw": args.l2_raw,
        "calibration": args.pair_calibration,
        "ncu_acceptance": args.ncu_acceptance,
        "matched_detail": args.matched_detail,
    }
    missing_args = [name for name, path in required_paths.items() if not path]
    if missing_args:
        parser.error("missing required artifact arguments: " + ",".join(missing_args))
    if args.min_valid_repeats > args.expected_repeats:
        parser.error("--min-valid-repeats cannot exceed --expected-repeats")
    if args.tensor_treatment_target_seconds <= 0.0:
        parser.error("--tensor-treatment-target-seconds must be positive")
    if args.tensor_control_calibration_min_seconds <= 0.0:
        parser.error("--tensor-control-calibration-min-seconds must be positive")
    if args.global_warmup_passes <= 0:
        parser.error("--global-warmup-passes must be positive")
    if args.l2_native_derived_hit_delta_max_pct < 0.0:
        parser.error("--l2-native-derived-hit-delta-max-pct cannot be negative")
    if not 0.0 <= args.l2_sector_conservation_tolerance < 1.0:
        parser.error("--l2-sector-conservation-tolerance must be in [0, 1)")

    config = AuditConfig(
        expected_rf=parse_ints(args.expected_rf),
        expected_l2_w=parse_ints(args.expected_l2_w),
        ncu_load_repeats=parse_ints(args.ncu_load_repeats),
        energy_load_repeats=parse_ints(args.energy_load_repeats),
        blocks_per_sm=(
            args.blocks_per_sm
            if args.blocks_per_sm is not None
            else args.tensor_blocks_per_sm
        ),
        l2_blocks_per_sm=(
            args.blocks_per_sm
            if args.blocks_per_sm is not None
            else args.l2_blocks_per_sm
        ),
        active_sm=args.active_sm,
        expected_repeats=args.expected_repeats,
        min_valid_repeats=args.min_valid_repeats,
        tensor_treatment_target_seconds=args.tensor_treatment_target_seconds,
        tensor_control_calibration_min_seconds=(
            args.tensor_control_calibration_min_seconds
        ),
        min_delta_j=args.min_delta_j,
        tensor_min_pj_per_flop=args.tensor_min_pj_per_flop,
        tensor_max_pj_per_flop=args.tensor_max_pj_per_flop,
        tensor_hmma_ratio_relative_spread_max=(
            args.tensor_hmma_ratio_relative_spread_max
        ),
        tensor_coefficient_relative_spread_max=(
            args.tensor_coefficient_relative_spread_max
        ),
        max_pair_start_distance_ms=args.max_pair_start_distance_ms,
        ncu_replay_mode=args.ncu_replay_mode,
        ncu_cache_control=args.ncu_cache_control,
        l2_residency_policy=args.l2_residency_policy,
        l2_address_layout=args.l2_address_layout,
        global_warmup_passes=args.global_warmup_passes,
        l1_path_hit_max_pct=args.l1_path_hit_max_pct,
        l1_hit_bytes_ratio_max=args.l1_hit_bytes_ratio_max,
        l2_path_hit_min_pct=args.l2_path_hit_min_pct,
        l2_native_derived_hit_delta_max_pct=(
            args.l2_native_derived_hit_delta_max_pct
        ),
        l2_sector_conservation_tolerance=(
            args.l2_sector_conservation_tolerance
        ),
        dram_to_l2_bytes_max=args.dram_to_l2_bytes_max,
        address_control_dram_ratio_max=args.address_control_dram_ratio_max,
        plateau_relative_spread_max=args.plateau_relative_spread_max,
    )
    rows = audit_data(
        config,
        tensor_raw=read_csv(args.tensor_raw),
        l2_raw=read_csv(args.l2_raw),
        calibration=read_csv(args.pair_calibration),
        ncu_acceptance=read_csv(args.ncu_acceptance),
        matched_detail=read_csv(args.matched_detail),
        evidence=required_paths,
    )
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args.out_csv)
    failures = sum(row["status"] != "pass" for row in rows)
    print(f"A100 Tensor/L2 remediation checks={len(rows)} nonpass={failures}")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    return 2 if args.fail_on_fail and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
