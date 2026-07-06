#!/usr/bin/env python3
"""Estimate component-level effective energy coefficients.

This analyzer intentionally avoids one global total-energy regression. It uses:

* matched reg_mma - reg_operand_only pairs for Tensor Core incremental pJ/FLOP,
* reg_operand_only power-vs-logical-register-op rate for register operand cost,
* an ordered shared <= L2 <= DRAM power-rate model for memory hierarchy paths.

The output coefficients are effective microbenchmark coefficients. They are not
physical bitcell energies without NCU traffic validation.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from fit_component_energy_model import (
    fit_scaled_active_set_nnls,
    median_nonzero_abs,
)


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


def read_rows(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                row = dict(row)
                row["_source_file"] = path
                rows.append(row)
    return rows


def usable(row: dict[str, str], *, allow_negative_net: bool = False) -> bool:
    if row.get("smid_histogram_ok", "").lower() != "true":
        return False
    if as_float(row, "elapsed_s") <= 0.0:
        return False
    if not allow_negative_net and as_float(row, "net_E_J") < 0.0:
        return False
    return True


def median_or_zero(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def linear_slope(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 0.0:
        raise ValueError("zero x variance")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    rmse = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    return intercept, slope, rmse


def estimate_tensor(rows: list[dict[str, str]]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        if row.get("mode") not in {"reg_operand_only", "reg_mma"}:
            continue
        if not usable(row):
            continue
        key = (
            row["_source_file"],
            row.get("W_SM_KiB", ""),
            row.get("blocks_per_SM", ""),
            row.get("active_SM", ""),
            row.get("reuse_factor", ""),
            row.get("load_repeat", ""),
            row.get("store_repeat", ""),
        )
        grouped[key][row["mode"]].append(row)

    energy_estimates: list[float] = []
    power_estimates: list[float] = []
    for modes in grouped.values():
        if "reg_operand_only" not in modes or "reg_mma" not in modes:
            continue
        reg_rows = modes["reg_operand_only"]
        mma_rows = modes["reg_mma"]
        reg_net = median_or_zero([as_float(r, "net_E_J") for r in reg_rows])
        mma_net = median_or_zero([as_float(r, "net_E_J") for r in mma_rows])
        reg_elapsed = median_or_zero([as_float(r, "elapsed_s") for r in reg_rows])
        mma_elapsed = median_or_zero([as_float(r, "elapsed_s") for r in mma_rows])
        flops = median_or_zero([as_float(r, "FLOP") for r in mma_rows])
        if flops <= 0.0 or reg_elapsed <= 0.0 or mma_elapsed <= 0.0:
            continue
        energy_estimates.append((mma_net - reg_net) * 1.0e12 / flops)
        mma_rate = flops / mma_elapsed
        delta_power = mma_net / mma_elapsed - reg_net / reg_elapsed
        power_estimates.append(delta_power * 1.0e12 / mma_rate)

    positive_power = [value for value in power_estimates if value > 0.0]
    return {
        "estimate_pj_per_flop": statistics.median(power_estimates),
        "positive_median_pj_per_flop": statistics.median(positive_power),
        "energy_median_pj_per_flop": statistics.median(energy_estimates),
        "pairs": len(power_estimates),
        "positive_pairs": len(positive_power),
    }


def estimate_register(rows: list[dict[str, str]]) -> dict[str, Any]:
    reg_rows = [
        row
        for row in rows
        if row.get("mode") == "reg_operand_only" and usable(row)
    ]
    xs = [
        as_float(row, "expected_reg_operand_ops") / as_float(row, "elapsed_s")
        for row in reg_rows
    ]
    ys = [as_float(row, "net_E_J") / as_float(row, "elapsed_s") for row in reg_rows]
    intercept, slope, rmse = linear_slope(xs, ys)
    mean_power = statistics.mean(ys)
    pj_per_reg_op = slope * 1.0e12
    return {
        "estimate_pj_per_reg_op": max(0.0, pj_per_reg_op),
        "estimate_pj_per_logical_operand_bit": max(0.0, pj_per_reg_op)
        / LOGICAL_OPERAND_BITS_PER_REG_OP,
        "intercept_w": intercept,
        "rmse_w": rmse,
        "relative_rmse_pct": 100.0 * rmse / mean_power if mean_power else 0.0,
        "rows": len(reg_rows),
    }


def estimate_memory_ordered(rows: list[dict[str, str]]) -> dict[str, Any]:
    mem_rows = [
        row
        for row in rows
        if row.get("mode")
        in {"shared_load_only", "l2_load_only", "dram_load_only"}
        and usable(row)
    ]
    y = [as_float(row, "net_E_J") / as_float(row, "elapsed_s") for row in mem_rows]
    shared = [
        as_float(row, "expected_shared_bytes") / as_float(row, "elapsed_s")
        for row in mem_rows
    ]
    l2 = [
        as_float(row, "expected_l2_bytes") / as_float(row, "elapsed_s")
        for row in mem_rows
    ]
    dram = [
        as_float(row, "expected_dram_bytes") / as_float(row, "elapsed_s")
        for row in mem_rows
    ]

    feature_specs = [
        (
            "ordered_shared_base",
            "pJ/byte",
            [s + l + d for s, l, d in zip(shared, l2, dram)],
        ),
        ("ordered_l2_increment", "pJ/byte", [l + d for l, d in zip(l2, dram)]),
        ("ordered_dram_increment", "pJ/byte", dram),
        (
            "baseline_l2_load_only",
            "W",
            [1.0 if row.get("mode") == "l2_load_only" else 0.0 for row in mem_rows],
        ),
        (
            "baseline_dram_load_only",
            "W",
            [
                1.0 if row.get("mode") == "dram_load_only" else 0.0
                for row in mem_rows
            ],
        ),
    ]
    features = [
        {
            "name": name,
            "unit": unit,
            "values": values,
            "scale": median_nonzero_abs(values),
        }
        for name, unit, values in feature_specs
    ]
    x_rows = [
        [1.0] + [feature["values"][i] / feature["scale"] for feature in features]
        for i in range(len(mem_rows))
    ]
    constrained = [False] + [feature["unit"] != "W" for feature in features]
    beta_scaled, iterations = fit_scaled_active_set_nnls(
        x_rows,
        y,
        1.0e-9,
        constrained,
        max_iter=1000,
        tolerance=1.0e-10,
    )
    beta = [beta_scaled[0]] + [
        coeff / feature["scale"]
        for coeff, feature in zip(beta_scaled[1:], features)
    ]
    predictions = [
        sum(
            beta[j] * ([1.0] + [feature["values"][i] for feature in features])[j]
            for j in range(len(beta))
        )
        for i in range(len(mem_rows))
    ]
    rmse = math.sqrt(sum((actual - pred) ** 2 for actual, pred in zip(y, predictions)) / len(y))
    mean_power = statistics.mean(y)

    shared_increment = beta[1] * 1.0e12
    l2_increment = beta[2] * 1.0e12
    dram_increment = beta[3] * 1.0e12
    shared_path = shared_increment
    l2_path = shared_increment + l2_increment
    dram_path = shared_increment + l2_increment + dram_increment
    return {
        "rows": len(mem_rows),
        "active_set_iterations": iterations,
        "rmse_w": rmse,
        "relative_rmse_pct": 100.0 * rmse / mean_power if mean_power else 0.0,
        "intercept_w": beta[0],
        "shared_increment_pj_per_byte": shared_increment,
        "l2_increment_pj_per_byte": l2_increment,
        "dram_increment_pj_per_byte": dram_increment,
        "shared_path_pj_per_byte": shared_path,
        "l2_path_pj_per_byte": l2_path,
        "dram_path_pj_per_byte": dram_path,
    }


def write_outputs(
    *,
    out_csv: Path,
    out_md: Path,
    tensor: dict[str, Any],
    register: dict[str, Any],
    memory: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "component": "tensor_core_increment",
            "estimate": tensor["estimate_pj_per_flop"],
            "unit": "pJ/FLOP",
            "secondary_estimate": "",
            "secondary_unit": "",
            "method": "matched reg_mma - reg_operand_only power-rate median",
            "rows_or_pairs": tensor["pairs"],
            "qa": f"positive_pairs={tensor['positive_pairs']}/{tensor['pairs']}",
        },
        {
            "component": "register_operand",
            "estimate": register["estimate_pj_per_reg_op"],
            "unit": "pJ/logical-reg-op",
            "secondary_estimate": register["estimate_pj_per_logical_operand_bit"],
            "secondary_unit": "pJ/logical-operand-bit",
            "method": "reg_operand_only power-vs-op-rate slope",
            "rows_or_pairs": register["rows"],
            "qa": f"relative_rmse_pct={register['relative_rmse_pct']:.3f}",
        },
        {
            "component": "shared_l1_increment",
            "estimate": memory["shared_increment_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["shared_increment_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "ordered shared<=L2<=DRAM power-rate model",
            "rows_or_pairs": memory["rows"],
            "qa": f"relative_rmse_pct={memory['relative_rmse_pct']:.3f}",
        },
        {
            "component": "l2_increment_over_shared",
            "estimate": memory["l2_increment_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["l2_increment_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "ordered shared<=L2<=DRAM power-rate model",
            "rows_or_pairs": memory["rows"],
            "qa": f"relative_rmse_pct={memory['relative_rmse_pct']:.3f}",
        },
        {
            "component": "dram_increment_over_l2",
            "estimate": memory["dram_increment_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["dram_increment_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "ordered shared<=L2<=DRAM power-rate model",
            "rows_or_pairs": memory["rows"],
            "qa": f"relative_rmse_pct={memory['relative_rmse_pct']:.3f}",
        },
        {
            "component": "shared_l1_cumulative_path",
            "estimate": memory["shared_path_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["shared_path_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "cumulative path from ordered model",
            "rows_or_pairs": memory["rows"],
            "qa": "",
        },
        {
            "component": "l2_hit_cumulative_path",
            "estimate": memory["l2_path_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["l2_path_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "cumulative path from ordered model",
            "rows_or_pairs": memory["rows"],
            "qa": "",
        },
        {
            "component": "dram_stream_cumulative_path",
            "estimate": memory["dram_path_pj_per_byte"],
            "unit": "pJ/byte",
            "secondary_estimate": memory["dram_path_pj_per_byte"] / 8.0,
            "secondary_unit": "pJ/bit",
            "method": "cumulative path from ordered model",
            "rows_or_pairs": memory["rows"],
            "qa": "",
        },
    ]
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "component",
                "estimate",
                "unit",
                "secondary_estimate",
                "secondary_unit",
                "method",
                "rows_or_pairs",
                "qa",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w") as f:
        f.write("# Component Energy Estimates\n\n")
        f.write("## Inputs\n\n")
        f.write("| role | files |\n")
        f.write("|---|---|\n")
        f.write(f"| tensor/register | `{', '.join(args.tensor_register_csvs)}` |\n")
        f.write(f"| memory hierarchy | `{', '.join(args.memory_csvs)}` |\n")
        f.write("\n## Recommended Component Table\n\n")
        f.write(
            "| component | estimate | unit | secondary | secondary unit | method | QA |\n"
        )
        f.write("|---|---:|---|---:|---|---|---|\n")
        for row in rows[:5]:
            f.write(
                f"| {row['component']} | {float(row['estimate']):.6g} | "
                f"{row['unit']} | "
                f"{float(row['secondary_estimate']):.6g}"
                if row["secondary_estimate"] != ""
                else f"| {row['component']} | {float(row['estimate']):.6g} | {row['unit']} | "
            )
            if row["secondary_estimate"] != "":
                f.write(
                    f" | {row['secondary_unit']} | {row['method']} | {row['qa']} |\n"
                )
            else:
                f.write(f" |  | {row['method']} | {row['qa']} |\n")
        f.write("\n## Cumulative Memory Paths\n\n")
        f.write("| path | estimate | unit | pJ/bit |\n")
        f.write("|---|---:|---|---:|\n")
        for row in rows[5:]:
            f.write(
                f"| {row['component']} | {float(row['estimate']):.6g} | "
                f"{row['unit']} | {float(row['secondary_estimate']):.6g} |\n"
            )
        f.write("\n## QA\n\n")
        f.write(
            f"- Tensor pairs: {tensor['positive_pairs']}/{tensor['pairs']} positive, "
            f"all-pair power median {tensor['estimate_pj_per_flop']:.6g} pJ/FLOP, "
            f"positive-pair median {tensor['positive_median_pj_per_flop']:.6g} pJ/FLOP.\n"
        )
        f.write(
            f"- Register fit: {register['rows']} rows, RMSE "
            f"{register['rmse_w']:.6g} W, relative RMSE "
            f"{register['relative_rmse_pct']:.3f}%.\n"
        )
        f.write(
            f"- Memory ordered fit: {memory['rows']} rows, RMSE "
            f"{memory['rmse_w']:.6g} W, relative RMSE "
            f"{memory['relative_rmse_pct']:.3f}%, active-set iterations "
            f"{memory['active_set_iterations']}.\n"
        )
        f.write("\n## Interpretation Limits\n\n")
        f.write(
            "These are effective microbenchmark coefficients based on NVML board "
            "energy and static expected traffic. The memory numbers include load "
            "instruction/control/stall effects and must not be described as pure "
            "SRAM/L2/DRAM bitcell energy until NCU actual L1/L2/DRAM traffic and "
            "stall counters are joined.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tensor-register-csvs",
        nargs="+",
        required=True,
        help="Raw CSVs used for Tensor/register estimates.",
    )
    parser.add_argument(
        "--memory-csvs",
        nargs="+",
        required=True,
        help="Raw CSVs used for ordered memory hierarchy estimates.",
    )
    parser.add_argument(
        "--out-csv",
        default="results/summary/component_energy_estimates.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/component_energy_estimates.md",
    )
    args = parser.parse_args()

    tensor_register_rows = read_rows(args.tensor_register_csvs)
    memory_rows = read_rows(args.memory_csvs)
    tensor = estimate_tensor(tensor_register_rows)
    register = estimate_register(tensor_register_rows)
    memory = estimate_memory_ordered(memory_rows)
    write_outputs(
        out_csv=Path(args.out_csv),
        out_md=Path(args.out_md),
        tensor=tensor,
        register=register,
        memory=memory,
        args=args,
    )
    print(f"wrote csv: {args.out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"tensor pJ/FLOP: {tensor['estimate_pj_per_flop']:.6g}")
    print(
        "register pJ/logical operand bit: "
        f"{register['estimate_pj_per_logical_operand_bit']:.6g}"
    )
    print(
        "memory pJ/bit increments: "
        f"shared={memory['shared_increment_pj_per_byte']/8.0:.6g}, "
        f"l2={memory['l2_increment_pj_per_byte']/8.0:.6g}, "
        f"dram={memory['dram_increment_pj_per_byte']/8.0:.6g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
