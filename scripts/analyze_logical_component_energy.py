#!/usr/bin/env python3
"""Analyze logically separated effective component energy coefficients.

This script is intentionally conservative. It reports:

* path slopes from NCU-validated traffic,
* hierarchical residual slopes for L1 -> L2 -> DRAM separation, and
* an optional non-negative multivariate fit with mode-specific intercepts.

Negative residuals are not hidden. They are reported as "not identified"
because a board-level NVML experiment can couple memory stalls, instruction
issue, clocks, and cache traffic in ways that invalidate a pure subtractive
component interpretation.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fit_component_energy_model import fit_scaled_active_set_nnls, median_nonzero_abs


REFERENCE_PJ_PER_BIT = {
    "gpujoule_shared_to_rf_k40": 5.32,
    "gpujoule_l1_to_rf_k40": 5.85,
    "gpujoule_l2_to_l1_k40": 15.48,
    "gpujoule_dram_to_l2_gddr5_k40": 30.55,
    "multimodule_hbm_dram_to_l2": 21.10,
    "fine_grained_hbm2_device_access": 3.95,
}


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    return int(round(as_float(row, key, float(default))))


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def is_active(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=0" in notes:
        return False
    if "gpu_active=1" in notes:
        return True
    return as_float(row, "n_gpu_active") > 0.0


def ncu_joined(row: dict[str, str]) -> bool:
    return "ncu_join_status=joined" in row.get("notes", "")


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def median(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    return statistics.median(values) if values else math.nan


def mad(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return math.nan
    center = statistics.median(values)
    return statistics.median([abs(value - center) for value in values])


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float]:
    if len(xs) != len(ys) or len(xs) < 3:
        return {
            "intercept": math.nan,
            "slope": math.nan,
            "r2": math.nan,
            "rmse": math.nan,
        }
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    x_var = sum((x - x_mean) ** 2 for x in xs)
    if x_var <= 0.0:
        return {
            "intercept": math.nan,
            "slope": math.nan,
            "r2": math.nan,
            "rmse": math.nan,
        }
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / x_var
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in residuals)
    sst = sum((y - y_mean) ** 2 for y in ys)
    r2 = 1.0 - sse / sst if sst > 0.0 else math.nan
    rmse = math.sqrt(sse / len(xs))
    return {
        "intercept": intercept,
        "slope": slope,
        "r2": r2,
        "rmse": rmse,
    }


def bits(row: dict[str, str], byte_col: str) -> float:
    return as_float(row, byte_col) * 8.0


def classify_memory_row(
    row: dict[str, str],
    args: argparse.Namespace,
) -> tuple[str, str]:
    mode = row.get("mode", "")
    w = row.get("W_SM_KiB", "")
    b = row.get("blocks_per_SM", "")
    active_sm = row.get("active_SM", "")

    if b != str(args.blocks_per_sm):
        return "reject", "blocks_per_sm_not_selected"
    if active_sm != str(args.active_sm):
        return "reject", "active_sm_not_selected"
    if not is_active(row):
        return "reject", "inactive_gpu"
    if row.get("smid_histogram_ok", "").lower() != "true":
        return "reject", "smid_histogram_failed"
    if as_float(row, "elapsed_s") < args.min_elapsed_s:
        return "reject", "elapsed_too_short"
    if as_float(row, "net_E_J") <= 0.0:
        return "reject", "nonpositive_net_energy"
    if not ncu_joined(row):
        return "reject", "missing_ncu_join"
    if row.get("ncu_status") not in {"", "ok"}:
        return "reject", f"ncu_status_{row.get('ncu_status')}"

    l1_hit = as_float(row, "ncu_l1_hit_rate_pct", -1.0)
    l2_hit = as_float(row, "ncu_l2_hit_rate_pct", -1.0)
    l1_bytes = as_float(row, "ncu_l1_bytes")
    l2_bytes = as_float(row, "ncu_l2_bytes")
    dram_bytes = as_float(row, "ncu_dram_bytes")
    shared_accesses = as_float(row, "ncu_shared_accesses")
    expected_shared = as_float(row, "expected_shared_bytes")

    if mode == "global_l1_load_only" and w == str(args.l1_w_sm_kib):
        if l1_hit < args.l1_hit_min_pct:
            return "reject", "l1_hit_below_threshold"
        if not finite_positive(l1_bytes):
            return "reject", "missing_l1_bytes"
        if l2_bytes / l1_bytes > args.l1_l2_ratio_max:
            return "reject", "l2_traffic_too_high_for_l1"
        if dram_bytes / l1_bytes > args.l1_dram_ratio_max:
            return "reject", "dram_traffic_too_high_for_l1"
        return "global_l1_path", "accepted"

    if mode == "shared_load_only" and w == str(args.shared_w_sm_kib):
        if not finite_positive(expected_shared):
            return "reject", "missing_expected_shared_bytes"
        if not finite_positive(shared_accesses):
            return "reject", "missing_shared_accesses"
        if l2_bytes > 0.0 and l2_bytes / expected_shared > args.shared_l2_ratio_max:
            return "reject", "global_traffic_too_high_for_shared"
        return "shared_l1_path", "accepted_expected_byte_denominator"

    if mode == args.l2_mode and w == str(args.l2_w_sm_kib):
        if l2_hit < args.l2_hit_min_pct:
            return "reject", "l2_hit_below_threshold"
        if not finite_positive(l2_bytes):
            return "reject", "missing_l2_bytes"
        if l2_bytes / max(l1_bytes, 1.0) < args.l2_l1_ratio_min:
            return "reject", "l2_traffic_too_low_relative_to_l1"
        if dram_bytes / l2_bytes > args.l2_dram_ratio_max:
            return "reject", "dram_traffic_too_high_for_l2"
        return "l2_hit_path", "accepted"

    if mode == args.dram_mode and w == str(args.dram_w_sm_kib):
        if l2_hit > args.dram_l2_hit_max_pct:
            return "reject", "l2_hit_too_high_for_dram"
        if not finite_positive(dram_bytes):
            return "reject", "missing_dram_bytes"
        if dram_bytes / max(l2_bytes, 1.0) < args.dram_l2_ratio_min:
            return "reject", "dram_bytes_not_dominant"
        return "dram_streaming_path", "accepted"

    return "reject", "mode_or_w_not_selected"


def path_denominator_bits(row: dict[str, str], component: str) -> float:
    if component == "global_l1_path":
        return bits(row, "ncu_l1_bytes")
    if component == "shared_l1_path":
        return bits(row, "expected_shared_bytes")
    if component == "l2_hit_path":
        return bits(row, "ncu_l2_bytes")
    if component == "dram_streaming_path":
        return bits(row, "ncu_dram_bytes")
    return 0.0


def summarize_path(component: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    xs = [path_denominator_bits(row, component) for row in rows]
    ys = [as_float(row, "net_E_J") for row in rows]
    fit = linear_fit(xs, ys)
    pjs = [
        as_float(row, "net_E_J") * 1.0e12 / x
        for row, x in zip(rows, xs)
        if x > 0.0
    ]
    lrs = sorted({as_int(row, "load_repeat") for row in rows})
    median_l1_hit = median([as_float(row, "ncu_l1_hit_rate_pct") for row in rows])
    median_l2_hit = median([as_float(row, "ncu_l2_hit_rate_pct") for row in rows])
    median_long_scoreboard = median(
        [as_float(row, "ncu_stall_long_scoreboard_pct") for row in rows]
    )
    status = "ok" if fit["slope"] > 0.0 and fit["r2"] >= 0.5 else "diagnostic_only"
    notes = ""
    if component == "l2_hit_path" and median_l1_hit > 50.0:
        status = "diagnostic_only"
        notes = (
            "L2-hit candidate is L1-dominated; RTX3090 has no clean "
            "capacity-only L1-miss/L2-hit W_SM window at this blocks/SM"
        )
    return {
        "estimate_kind": "path_slope",
        "component": component,
        "estimate": fit["slope"] * 1.0e12,
        "unit": "pJ/bit",
        "rows": len(rows),
        "load_repeat_values": ",".join(str(v) for v in lrs),
        "r2": fit["r2"],
        "rmse_J": fit["rmse"],
        "intercept_J": fit["intercept"],
        "median_direct_pj_per_bit": median(pjs),
        "mad_direct_pj_per_bit": mad(pjs),
        "denominator_min_bits": min(xs) if xs else math.nan,
        "denominator_max_bits": max(xs) if xs else math.nan,
        "median_l1_hit_pct": median_l1_hit,
        "median_l2_hit_pct": median_l2_hit,
        "median_long_scoreboard_pct": median_long_scoreboard,
        "status": status,
        "notes": notes,
    }


def residual_component(
    component: str,
    rows: list[dict[str, str]],
    target_bit_col: str,
    fixed_coeffs_j_per_bit: dict[str, float],
) -> dict[str, Any]:
    xs = [bits(row, target_bit_col) for row in rows]
    ys = []
    for row in rows:
        residual = as_float(row, "net_E_J")
        for bit_col, coeff in fixed_coeffs_j_per_bit.items():
            residual -= bits(row, bit_col) * coeff
        ys.append(residual)
    fit = linear_fit(xs, ys)
    status = "ok" if fit["slope"] > 0.0 and fit["r2"] >= 0.3 else "not_identified"
    median_l1_hit = median([as_float(row, "ncu_l1_hit_rate_pct") for row in rows])
    median_l2_hit = median([as_float(row, "ncu_l2_hit_rate_pct") for row in rows])
    median_long_scoreboard = median(
        [as_float(row, "ncu_stall_long_scoreboard_pct") for row in rows]
    )
    if fit["slope"] <= 0.0:
        note = "negative residual slope; lower-level subtraction exceeds measured variation"
    elif fit["r2"] < 0.3:
        note = "low R2; traffic axis does not explain residual energy"
    else:
        note = ""
    if component == "l2_increment_residual" and median_l1_hit > 50.0:
        status = "not_identified"
        note = (
            "L2 residual is L1-dominated because L1 hit rate remains high; "
            "need L1-bypass/CG loads or a GPU/profile with a real L1-miss/L2-hit "
            "capacity window"
        )
    if component == "l2_increment_residual" and fit["slope"] * 1.0e12 < 5.0:
        status = "not_identified"
        note = (note + "; " if note else "") + "below reference-plausible L2 transaction range"
    return {
        "estimate_kind": "hierarchical_residual",
        "component": component,
        "estimate": fit["slope"] * 1.0e12,
        "unit": "pJ/bit",
        "rows": len(rows),
        "load_repeat_values": ",".join(
            str(v) for v in sorted({as_int(row, "load_repeat") for row in rows})
        ),
        "r2": fit["r2"],
        "rmse_J": fit["rmse"],
        "intercept_J": fit["intercept"],
        "median_direct_pj_per_bit": math.nan,
        "mad_direct_pj_per_bit": math.nan,
        "denominator_min_bits": min(xs) if xs else math.nan,
        "denominator_max_bits": max(xs) if xs else math.nan,
        "median_l1_hit_pct": median_l1_hit,
        "median_l2_hit_pct": median_l2_hit,
        "median_long_scoreboard_pct": median_long_scoreboard,
        "status": status,
        "notes": note,
    }


def nnls_memory_fit(rows_by_component: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    rows = (
        rows_by_component.get("global_l1_path", [])
        + rows_by_component.get("l2_hit_path", [])
        + rows_by_component.get("dram_streaming_path", [])
    )
    if len(rows) < 6:
        return []
    modes = sorted({row["component"] for row in rows})
    feature_names = [f"intercept_{mode}" for mode in modes] + [
        "global_l1_component_nnls",
        "l2_increment_nnls",
        "dram_increment_nnls",
    ]
    feature_units = ["J"] * len(modes) + ["pJ/bit", "pJ/bit", "pJ/bit"]
    raw_features: list[list[float]] = []
    for row in rows:
        mode_features = [1.0 if row["component"] == mode else 0.0 for mode in modes]
        raw_features.append(
            mode_features
            + [
                bits(row, "ncu_l1_bytes"),
                bits(row, "ncu_l2_bytes"),
                bits(row, "ncu_dram_bytes"),
            ]
        )

    scales = [median_nonzero_abs([raw[i] for raw in raw_features]) for i in range(len(feature_names))]
    x_rows = [
        [value / scale for value, scale in zip(raw, scales)]
        for raw in raw_features
    ]
    y = [as_float(row, "net_E_J") for row in rows]
    constrained = [False] * len(modes) + [True, True, True]
    beta_scaled, iterations = fit_scaled_active_set_nnls(
        x_rows,
        y,
        ridge_lambda=1.0e-9,
        constrained_nonnegative=constrained,
        max_iter=1000,
        tolerance=1.0e-10,
    )
    beta = [coef / scale for coef, scale in zip(beta_scaled, scales)]
    pred = [sum(x * b for x, b in zip(raw, beta)) for raw in raw_features]
    residuals = [actual - fitted for actual, fitted in zip(y, pred)]
    y_mean = statistics.mean(y)
    sse = sum(r * r for r in residuals)
    sst = sum((actual - y_mean) ** 2 for actual in y)
    r2 = 1.0 - sse / sst if sst > 0.0 else math.nan
    rmse = math.sqrt(sse / len(y))

    out: list[dict[str, Any]] = []
    for name, unit, coef in zip(feature_names, feature_units, beta):
        if not name.endswith("_nnls"):
            continue
        value = coef * 1.0e12
        status = "ok" if value > 0.0 else "zero_bound_or_not_identified"
        note = f"active_set_iterations={iterations}"
        if name == "l2_increment_nnls" and value < 5.0:
            status = "reference_mismatch"
            note += "; below reference-plausible L2 transaction range"
        out.append(
            {
                "estimate_kind": "nnls_mode_intercept",
                "component": name,
                "estimate": value,
                "unit": unit,
                "rows": len(rows),
                "load_repeat_values": "",
                "r2": r2,
                "rmse_J": rmse,
                "intercept_J": math.nan,
                "median_direct_pj_per_bit": math.nan,
                "mad_direct_pj_per_bit": math.nan,
                "denominator_min_bits": math.nan,
                "denominator_max_bits": math.nan,
                "median_l1_hit_pct": math.nan,
                "median_l2_hit_pct": math.nan,
                "median_long_scoreboard_pct": math.nan,
                "status": status,
                "notes": note,
            }
        )
    return out


def register_rows(summary_csv: str, tensor_pairs_csv: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if summary_csv:
        rows = read_rows(summary_csv)
        stable = [
            row
            for row in rows
            if row.get("spill_free", "").lower() == "true"
            and as_int(row, "reg_payload_bytes_per_block") >= 4096
            and as_float(row, "pJ_per_reg_update") > 0.0
        ]
        values = [as_float(row, "pJ_per_reg_update") for row in stable]
        out.append(
            {
                "estimate_kind": "register_scalar_control",
                "component": "scalar_register_pressure",
                "estimate": median(values),
                "unit": "pJ/reg-update",
                "rows": len(stable),
                "load_repeat_values": "",
                "r2": math.nan,
                "rmse_J": math.nan,
                "intercept_J": math.nan,
                "median_direct_pj_per_bit": math.nan,
                "mad_direct_pj_per_bit": mad(values),
                "denominator_min_bits": math.nan,
                "denominator_max_bits": math.nan,
                "median_l1_hit_pct": math.nan,
                "median_l2_hit_pct": math.nan,
                "median_long_scoreboard_pct": math.nan,
                "status": "diagnostic_only",
                "notes": "reg_pressure-empty; not pure register-file pJ/bit",
            }
        )
    if tensor_pairs_csv:
        rows = read_rows(tensor_pairs_csv)
        tensor = [
            as_float(row, "coefficient")
            for row in rows
            if row.get("pair") == "reg_mma_minus_reg_operand"
            and row.get("coefficient_unit") == "pJ/FLOP"
            and as_float(row, "coefficient") > 0.0
        ]
        out.append(
            {
                "estimate_kind": "tensor_register_pair",
                "component": "wmma_tensor_register_increment",
                "estimate": median(tensor),
                "unit": "pJ/FLOP",
                "rows": len(tensor),
                "load_repeat_values": "",
                "r2": math.nan,
                "rmse_J": math.nan,
                "intercept_J": math.nan,
                "median_direct_pj_per_bit": math.nan,
                "mad_direct_pj_per_bit": mad(tensor),
                "denominator_min_bits": math.nan,
                "denominator_max_bits": math.nan,
                "median_l1_hit_pct": math.nan,
                "median_l2_hit_pct": math.nan,
                "median_long_scoreboard_pct": math.nan,
                "status": "diagnostic_only",
                "notes": "reg_mma-reg_operand_only; effective Tensor+register, not pure Tensor Core",
            }
        )
    return out


def fmt(value: Any, digits: int = 6) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.{digits}g}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "estimate_kind",
        "component",
        "estimate",
        "unit",
        "rows",
        "load_repeat_values",
        "r2",
        "rmse_J",
        "intercept_J",
        "median_direct_pj_per_bit",
        "mad_direct_pj_per_bit",
        "denominator_min_bits",
        "denominator_max_bits",
        "median_l1_hit_pct",
        "median_l2_hit_pct",
        "median_long_scoreboard_pct",
        "status",
        "notes",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_detail_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "mode",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "load_repeat",
        "component",
        "accepted",
        "reason",
        "net_E_J",
        "elapsed_s",
        "ncu_l1_hit_rate_pct",
        "ncu_l2_hit_rate_pct",
        "ncu_l1_bytes",
        "ncu_l2_bytes",
        "ncu_dram_bytes",
        "expected_shared_bytes",
        "ncu_shared_accesses",
        "ncu_stall_long_scoreboard_pct",
        "ncu_stall_short_scoreboard_pct",
        "ncu_stall_wait_pct",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    detail_rows: list[dict[str, str]],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    accepted = [row for row in detail_rows if row["accepted"] == "true"]
    rejected = [row for row in detail_rows if row["accepted"] == "false"]
    accepted_by_component = Counter(row["component"] for row in accepted)
    rejected_by_reason = Counter(row["reason"] for row in rejected)

    row_by_name = {row["component"]: row for row in rows}
    l2 = row_by_name.get("l2_increment_residual", {})
    dram = row_by_name.get("dram_increment_residual", {})
    l2_value = l2.get("estimate", math.nan)
    dram_value = dram.get("estimate", math.nan)
    residual_order_ok = (
        isinstance(l2_value, float)
        and isinstance(dram_value, float)
        and math.isfinite(l2_value)
        and math.isfinite(dram_value)
        and 0.0 < l2_value < dram_value
        and l2.get("status") == "ok"
        and dram.get("status") == "ok"
    )

    with path.open("w") as f:
        f.write("# RTX 3090 Logical Component Energy Analysis\n\n")
        f.write("## 결론\n\n")
        if residual_order_ok:
            f.write(
                "고정 ITER + NCU traffic sweep에서 hierarchical residual 기준 "
                "`L2 < DRAM` 순서가 성립했다. 단, 이 값은 NVML board-level "
                "effective coefficient이며 물리 bitcell energy가 아니다.\n\n"
            )
        else:
            f.write(
                "이번 데이터에서는 hierarchical residual 기준의 `L2 < DRAM` "
                "분리가 안정적으로 성립하지 않았다. 따라서 L2와 DRAM 값을 "
                "억지로 reference 순서에 맞춰 보정하지 않고, 현재 커널/측정 "
                "구조에서는 해당 component 증가분이 `not_identified`임을 "
                "명시한다.\n\n"
            )
        f.write(
            f"핵심 주의점은 NVML energy가 board 전체 전력이고, `{args.l2_mode}`와 "
            f"`{args.dram_mode}`의 long-scoreboard stall 및 active power가 "
            "traffic 증가와 함께 변하기 때문이다. 즉 같은 byte 수라도 SM issue "
            "rate와 memory stall이 다르면 단순 `J/bit`가 component energy만 "
            "나타내지 않는다.\n\n"
        )
        if args.l2_mode == "l2_cg_load_only":
            f.write(
                "RTX 3090에서는 `L2/SM = 6 MiB / 82 SM ≈ 74.9 KiB/SM`이고, "
                "`blocks/SM=16`에서 shared/L1-resident 상한은 대략 "
                "`100 KiB - 16 KiB = 84 KiB/SM`이다. 그래서 `W_SM`만으로는 "
                "`L1에는 안 맞지만 L2에는 맞는` 구간이 없다. 이 보고서는 그 한계를 "
                "`ld.global.cg` 기반 `l2_cg_load_only`로 보완해 L1 hit를 거의 0%로 "
                "낮춘 뒤 L2 hit path를 따로 측정한 결과다.\n\n"
            )
        else:
            f.write(
                "RTX 3090에서는 `L2/SM = 6 MiB / 82 SM ≈ 74.9 KiB/SM`이고, "
                "`blocks/SM=16`에서 shared/L1-resident 상한은 대략 "
                "`100 KiB - 16 KiB = 84 KiB/SM`이다. 따라서 `W_SM`만으로는 "
                "`L1에는 안 맞지만 L2에는 맞는` 구간이 없다. 현재 L2 후보는 "
                "L2 hit rate가 높더라도 L1 hit rate도 높아 L1-dominated로 봐야 한다.\n\n"
            )

        f.write("## 입력 데이터\n\n")
        f.write("| 항목 | 값 |\n")
        f.write("|---|---|\n")
        f.write(f"| joined energy+NCU CSV | `{args.joined_csv}` |\n")
        f.write(f"| register summary CSV | `{args.register_summary_csv or ''}` |\n")
        f.write(f"| tensor/register pairs CSV | `{args.tensor_pairs_csv or ''}` |\n")
        f.write(f"| selected blocks/SM | {args.blocks_per_sm} |\n")
        f.write(f"| selected active_SM (SMs) | {args.active_sm} |\n")
        f.write(f"| L1 W_SM (KiB) | {args.l1_w_sm_kib} |\n")
        f.write(f"| shared W_SM (KiB) | {args.shared_w_sm_kib} |\n")
        f.write(f"| L2 W_SM (KiB) | {args.l2_w_sm_kib} |\n")
        f.write(f"| DRAM W_SM (KiB) | {args.dram_w_sm_kib} |\n\n")

        f.write("## NCU Acceptance Summary\n\n")
        f.write("| 항목 | 값 | 단위 |\n")
        f.write("|---|---:|---|\n")
        f.write(f"| detail rows | {len(detail_rows)} | rows |\n")
        f.write(f"| accepted rows | {len(accepted)} | rows |\n")
        f.write(f"| rejected rows | {len(rejected)} | rows |\n")
        for component, count in accepted_by_component.items():
            f.write(f"| accepted `{component}` | {count} | rows |\n")
        f.write("\n")
        if rejected_by_reason:
            f.write("| rejection reason | rows |\n")
            f.write("|---|---:|\n")
            for reason, count in rejected_by_reason.most_common(10):
                f.write(f"| {reason} | {count} |\n")
            f.write("\n")

        f.write("## Mode Meaning\n\n")
        f.write("| mode | selected W_SM | interpretation | denominator |\n")
        f.write("|---|---:|---|---|\n")
        f.write(
            f"| `global_l1_load_only` | {args.l1_w_sm_kib} KiB | "
            "L1-hit global load path | NCU L1 bytes |\n"
        )
        f.write(
            f"| `shared_load_only` | {args.shared_w_sm_kib} KiB | "
            "shared-memory operand load path | expected shared bytes, NCU shared accesses for validation |\n"
        )
        f.write(
            f"| `{args.l2_mode}` | {args.l2_w_sm_kib} KiB | "
            "L2-hit global load path | NCU L2 bytes |\n"
        )
        f.write(
            f"| `{args.dram_mode}` | {args.dram_w_sm_kib} KiB | "
            "DRAM streaming global load path | NCU DRAM bytes |\n\n"
        )

        f.write("## Component Estimates\n\n")
        f.write(
            "| kind | component | estimate | unit | rows | LR values | R2 | RMSE (J) | "
            "L1 hit (%) | L2 hit (%) | long scoreboard (%) | status | notes |\n"
        )
        f.write("|---|---|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['estimate_kind']} | {row['component']} | "
                f"{fmt(row['estimate'])} | {row['unit']} | {row['rows']} | "
                f"{row['load_repeat_values']} | {fmt(row['r2'])} | "
                f"{fmt(row['rmse_J'])} | {fmt(row['median_l1_hit_pct'])} | "
                f"{fmt(row['median_l2_hit_pct'])} | "
                f"{fmt(row['median_long_scoreboard_pct'])} | "
                f"{row['status']} | {row['notes']} |\n"
            )
        f.write("\n")

        f.write("## Reference Check\n\n")
        f.write("| reference path | pJ/bit | interpretation |\n")
        f.write("|---|---:|---|\n")
        f.write(
            f"| GPUJoule K40 shared->RF | {REFERENCE_PJ_PER_BIT['gpujoule_shared_to_rf_k40']} | "
            "GPU transaction path |\n"
        )
        f.write(
            f"| GPUJoule K40 L1->RF | {REFERENCE_PJ_PER_BIT['gpujoule_l1_to_rf_k40']} | "
            "GPU transaction path |\n"
        )
        f.write(
            f"| GPUJoule K40 L2->L1 | {REFERENCE_PJ_PER_BIT['gpujoule_l2_to_l1_k40']} | "
            "GPU transaction path |\n"
        )
        f.write(
            f"| GPUJoule K40 DRAM->L2 | {REFERENCE_PJ_PER_BIT['gpujoule_dram_to_l2_gddr5_k40']} | "
            "external DRAM transaction path |\n"
        )
        f.write(
            f"| HBM system DRAM->L2 assumption | {REFERENCE_PJ_PER_BIT['multimodule_hbm_dram_to_l2']} | "
            "HBM-based system path assumption |\n"
        )
        f.write(
            f"| HBM2 device access | {REFERENCE_PJ_PER_BIT['fine_grained_hbm2_device_access']} | "
            "HBM device/access only, not SM-to-register path |\n\n"
        )
        f.write(
            "따라서 `L2 increment`와 `DRAM increment`가 비슷하게 나오면 "
            "reference 관점에서 물리 component energy로 받아들이면 안 된다. "
            "그 경우는 stall, elapsed coupling, cache-counter denominator, "
            "또는 커널 구조가 분리를 못 만든 것으로 해석해야 한다.\n\n"
        )

        if residual_order_ok:
            f.write("## Remaining Checks\n\n")
            f.write(
                "1. 현재 CG 분석은 LR=1과 LR=16 NCU spot-check를 반영했고, "
                "중간 LR=2/4/8은 NCU traffic scaling으로 결합했다. 최종 제출용 "
                "표에는 전체 LR별 NCU를 추가하면 가장 엄밀하다.\n"
            )
            f.write(
                "2. `ld.global.cg` mode는 Tensor/WMMA operand path가 아니라 data-movement "
                "calibration path다. Tensor 포함 결과와는 별도 표로 유지한다.\n"
            )
            f.write(
                "3. long-scoreboard stall이 크므로 pJ/bit는 physical SRAM/HBM bitcell 값이 "
                "아니라 effective board-level coefficient로 표기한다.\n"
            )
        else:
            f.write("## Required Next Design If Not Identified\n\n")
            f.write(
                "1. `ITER` 고정은 유지하되 LR=1의 실행 시간이 너무 짧으면 제외하거나 "
                "mode별 `ITER`를 따로 정해 denominator range와 runtime을 동시에 확보한다.\n"
            )
            f.write(
                "2. L2/DRAM load-only kernel은 long-scoreboard stall이 너무 커서 "
                "active power가 낮아질 수 있으므로 independent load streams와 작은 "
                "compute filler를 추가한 variant를 만든다.\n"
            )
            f.write(
                "3. `addr_only`는 64-bit integer address hash/control 비용이 커서 "
                "subtract baseline으로 쓰지 않는다.\n"
            )
            f.write(
                "4. 최종 논문 표에는 path slope와 residual component를 분리하고, "
                "`not_identified`를 0 또는 reference 보정값으로 바꾸지 않는다.\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("joined_csv")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-detail-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--register-summary-csv", default="")
    parser.add_argument("--tensor-pairs-csv", default="")
    parser.add_argument("--blocks-per-sm", type=int, default=16)
    parser.add_argument("--active-sm", type=int, default=82)
    parser.add_argument("--l1-w-sm-kib", type=int, default=16)
    parser.add_argument("--shared-w-sm-kib", type=int, default=64)
    parser.add_argument("--l2-w-sm-kib", type=int, default=64)
    parser.add_argument("--dram-w-sm-kib", type=int, default=8192)
    parser.add_argument("--l2-mode", default="l2_load_only")
    parser.add_argument("--dram-mode", default="dram_load_only")
    parser.add_argument("--min-elapsed-s", type=float, default=0.2)
    parser.add_argument("--l1-hit-min-pct", type=float, default=99.0)
    parser.add_argument("--l1-l2-ratio-max", type=float, default=0.02)
    parser.add_argument("--l1-dram-ratio-max", type=float, default=0.02)
    parser.add_argument("--shared-l2-ratio-max", type=float, default=0.02)
    parser.add_argument("--l2-hit-min-pct", type=float, default=98.0)
    parser.add_argument("--l2-l1-ratio-min", type=float, default=0.03)
    parser.add_argument("--l2-dram-ratio-max", type=float, default=0.02)
    parser.add_argument("--dram-l2-hit-max-pct", type=float, default=5.0)
    parser.add_argument("--dram-l2-ratio-min", type=float, default=0.90)
    args = parser.parse_args()

    input_rows = read_rows(args.joined_csv)
    detail_rows: list[dict[str, str]] = []
    rows_by_component: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        component, reason = classify_memory_row(row, args)
        accepted = component != "reject"
        detail = dict(row)
        detail["component"] = component
        detail["accepted"] = "true" if accepted else "false"
        detail["reason"] = reason
        detail_rows.append(detail)
        if accepted:
            row = dict(row)
            row["component"] = component
            rows_by_component[component].append(row)

    summary_rows: list[dict[str, Any]] = []
    summary_rows.extend(register_rows(args.register_summary_csv, args.tensor_pairs_csv))

    for component in [
        "shared_l1_path",
        "global_l1_path",
        "l2_hit_path",
        "dram_streaming_path",
    ]:
        if rows_by_component.get(component):
            summary_rows.append(summarize_path(component, rows_by_component[component]))

    l1_row = next(
        (
            row
            for row in summary_rows
            if row["estimate_kind"] == "path_slope"
            and row["component"] == "global_l1_path"
            and row["estimate"] > 0.0
        ),
        None,
    )
    l2_residual_row = None
    if l1_row and rows_by_component.get("l2_hit_path"):
        l1_coeff = l1_row["estimate"] / 1.0e12
        l2_residual_row = residual_component(
            "l2_increment_residual",
            rows_by_component["l2_hit_path"],
            "ncu_l2_bytes",
            {"ncu_l1_bytes": l1_coeff},
        )
        summary_rows.append(l2_residual_row)

    if l1_row and l2_residual_row and rows_by_component.get("dram_streaming_path"):
        l1_coeff = l1_row["estimate"] / 1.0e12
        l2_coeff = l2_residual_row["estimate"] / 1.0e12
        if l2_residual_row["status"] != "ok":
            l2_coeff = 0.0
        summary_rows.append(
            residual_component(
                "dram_increment_residual",
                rows_by_component["dram_streaming_path"],
                "ncu_dram_bytes",
                {"ncu_l1_bytes": l1_coeff, "ncu_l2_bytes": l2_coeff},
            )
        )

    summary_rows.extend(nnls_memory_fit(rows_by_component))

    write_csv(Path(args.out_csv), summary_rows)
    write_detail_csv(Path(args.out_detail_csv), detail_rows)
    write_markdown(Path(args.out_md), summary_rows, detail_rows, args)
    print(f"wrote csv: {args.out_csv}")
    print(f"wrote detail csv: {args.out_detail_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"summary rows: {len(summary_rows)}")
    print(
        "accepted rows: "
        + ", ".join(
            f"{component}={len(rows)}"
            for component, rows in sorted(rows_by_component.items())
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
