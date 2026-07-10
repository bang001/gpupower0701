#!/usr/bin/env python3
"""Summarize component pair runs into paired-difference coefficients."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


PAIR_SPECS = [
    {
        "pair": "reg_mma_minus_empty",
        "numerator_mode": "reg_mma",
        "baseline_mode": "empty",
        "denominator_mode": "reg_mma",
        "denominator_column": "FLOP",
        "coefficient_unit": "pJ/FLOP",
    },
    {
        "pair": "reg_operand_minus_empty",
        "numerator_mode": "reg_operand_only",
        "baseline_mode": "empty",
        "denominator_mode": "reg_operand_only",
        "denominator_column": "expected_reg_operand_ops",
        "coefficient_unit": "pJ/reg-op",
    },
    {
        "pair": "reg_mma_minus_reg_operand",
        "numerator_mode": "reg_mma",
        "baseline_mode": "reg_operand_only",
        "denominator_mode": "reg_mma",
        "denominator_column": "FLOP",
        "coefficient_unit": "pJ/FLOP",
    },
    {
        "pair": "reg_fragment_minus_empty",
        "numerator_mode": "reg_fragment_only",
        "baseline_mode": "empty",
        "denominator_mode": "reg_fragment_only",
        "denominator_column": "",
        "coefficient_unit": "J",
    },
    {
        "pair": "shared_load_minus_empty",
        "numerator_mode": "shared_load_only",
        "baseline_mode": "empty",
        "denominator_mode": "shared_load_only",
        "denominator_column": "expected_shared_bytes",
        "coefficient_unit": "pJ/byte",
    },
    {
        "pair": "shared_mma_minus_shared_load",
        "numerator_mode": "shared_mma",
        "baseline_mode": "shared_load_only",
        "denominator_mode": "shared_mma",
        "denominator_column": "FLOP",
        "coefficient_unit": "pJ/FLOP",
    },
    {
        "pair": "l2_load_minus_empty",
        "numerator_mode": "l2_load_only",
        "baseline_mode": "empty",
        "denominator_mode": "l2_load_only",
        "denominator_column": "expected_l2_bytes",
        "coefficient_unit": "pJ/byte",
    },
    {
        "pair": "l2_mma_minus_l2_load",
        "numerator_mode": "l2_mma",
        "baseline_mode": "l2_load_only",
        "denominator_mode": "l2_mma",
        "denominator_column": "FLOP",
        "coefficient_unit": "pJ/FLOP",
    },
    {
        "pair": "dram_load_minus_empty",
        "numerator_mode": "dram_load_only",
        "baseline_mode": "empty",
        "denominator_mode": "dram_load_only",
        "denominator_column": "expected_dram_bytes",
        "coefficient_unit": "pJ/byte",
    },
    {
        "pair": "dram_mma_minus_dram_load",
        "numerator_mode": "dram_mma",
        "baseline_mode": "dram_load_only",
        "denominator_mode": "dram_mma",
        "denominator_column": "FLOP",
        "coefficient_unit": "pJ/FLOP",
    },
    {
        "pair": "store_only_minus_empty",
        "numerator_mode": "store_only",
        "baseline_mode": "empty",
        "denominator_mode": "store_only",
        "denominator_column": "expected_store_bytes",
        "coefficient_unit": "pJ/byte",
    },
    {
        "pair": "store_path_minus_store_only",
        "numerator_mode": "store_path",
        "baseline_mode": "store_only",
        "denominator_mode": "store_path",
        "denominator_column": "expected_store_bytes",
        "coefficient_unit": "pJ/byte",
    },
]


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value == "":
        return default
    return int(float(value))


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    return float(value)


def is_active_row(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=1" in notes:
        return True
    if "gpu_active=0" in notes:
        return False
    return as_int(row, "n_gpu_active") > 0


def key_for(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        row.get("profile_name") or row.get("target_profile") or "",
        row.get("gpu_id", ""),
        row.get("n_gpu_active", ""),
        row.get("W_SM_KiB", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
        row.get("ITER", ""),
        row.get("reuse_factor", "1"),
        row.get("load_repeat", "1"),
        row.get("store_repeat", "1"),
    )


def summarize_mode(rows: list[dict[str, str]]) -> dict[str, float]:
    numeric_columns = [
        "net_E_J",
        "elapsed_s",
        "FLOP",
        "N_MMA",
        "expected_shared_bytes",
        "expected_l2_bytes",
        "expected_dram_bytes",
        "expected_store_bytes",
        "expected_reg_operand_ops",
    ]
    out: dict[str, float] = {"row_count": float(len(rows))}
    for column in numeric_columns:
        values = [as_float(row, column) for row in rows if row.get(column, "") != ""]
        out[column] = statistics.median(values) if values else 0.0
    return out


def coefficient(delta_j: float, denominator: float, unit: str) -> float:
    if unit == "J" or denominator <= 0.0:
        return delta_j
    return delta_j * 1.0e12 / denominator


def diagnostic_for_pair(
    *,
    coefficient_value: float,
    coefficient_unit: str,
    numerator_elapsed: float,
    baseline_elapsed: float,
    max_elapsed_ratio: float,
) -> tuple[bool, str, float]:
    elapsed_min = min(numerator_elapsed, baseline_elapsed)
    elapsed_max = max(numerator_elapsed, baseline_elapsed)
    elapsed_ratio = elapsed_max / elapsed_min if elapsed_min > 0.0 else float("inf")
    reasons: list[str] = []
    if elapsed_ratio > max_elapsed_ratio:
        reasons.append(f"elapsed_ratio>{max_elapsed_ratio:g}")
    if coefficient_unit != "J" and coefficient_value < 0.0:
        reasons.append("negative_coefficient")
    return (not reasons, ";".join(reasons), elapsed_ratio)


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Component Pair Summary\n\n")
        f.write(
            "| profile | GPU | W_SM (KiB) | blocks/SM | active_SM (SMs) | "
            "ITER | factors | pair | delta_E_J (J) | denominator | coefficient | "
            "elapsed ratio | valid | diagnostic |\n"
        )
        f.write(
            "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|\n"
        )
        for row in rows:
            factors = (
                f"reuse={row['reuse_factor']}, "
                f"load={row['load_repeat']}, store={row['store_repeat']}"
            )
            coefficient_text = (
                f"{row['coefficient']:.6g} {row['coefficient_unit']}"
            )
            f.write(
                f"| {row['profile_name']} | {row['gpu_id']} | "
                f"{row['W_SM_KiB']} | {row['blocks_per_SM']} | "
                f"{row['active_SM']} | {row['ITER']} | {factors} | "
                f"{row['pair']} | {row['delta_E_J']:.6g} | "
                f"{row['denominator']:.6g} | {coefficient_text} | "
                f"{row['elapsed_ratio']:.6g} | "
                f"{row['valid_component_estimate']} | {row['diagnostic']} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument(
        "--out-csv", default="results/summary/component_pair_summary.csv"
    )
    parser.add_argument(
        "--out-md", default="results/summary/component_pair_summary.md"
    )
    parser.add_argument(
        "--include-placement-failures",
        action="store_true",
        help="Include rows where smid_histogram_ok is false.",
    )
    parser.add_argument(
        "--max-elapsed-ratio",
        type=float,
        default=1.25,
        help="Mark pair invalid when numerator/baseline elapsed ratio exceeds this.",
    )
    args = parser.parse_args()

    with Path(args.csv_path).open(newline="") as f:
        input_rows = list(csv.DictReader(f))

    grouped: dict[tuple[Any, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in input_rows:
        if not is_active_row(row):
            continue
        if (
            not args.include_placement_failures
            and row.get("smid_histogram_ok", "").lower() == "false"
        ):
            continue
        grouped[key_for(row)][row.get("mode", "")].append(row)

    output_rows: list[dict[str, Any]] = []
    for key, rows_by_mode in grouped.items():
        summaries = {
            mode: summarize_mode(rows) for mode, rows in rows_by_mode.items() if rows
        }
        for spec in PAIR_SPECS:
            numerator = summaries.get(spec["numerator_mode"])
            baseline = summaries.get(spec["baseline_mode"])
            denom_source = summaries.get(spec["denominator_mode"])
            if not numerator or not baseline or not denom_source:
                continue
            delta_j = numerator["net_E_J"] - baseline["net_E_J"]
            denominator_column = spec["denominator_column"]
            denominator = (
                denom_source.get(denominator_column, 0.0)
                if denominator_column
                else 0.0
            )
            coeff = coefficient(delta_j, denominator, spec["coefficient_unit"])
            numerator_elapsed = numerator.get("elapsed_s", 0.0)
            baseline_elapsed = baseline.get("elapsed_s", 0.0)
            valid_component_estimate, diagnostic, elapsed_ratio = diagnostic_for_pair(
                coefficient_value=coeff,
                coefficient_unit=spec["coefficient_unit"],
                numerator_elapsed=numerator_elapsed,
                baseline_elapsed=baseline_elapsed,
                max_elapsed_ratio=args.max_elapsed_ratio,
            )
            (
                profile_name,
                gpu_id,
                n_gpu_active,
                w_sm_kib,
                blocks_per_sm,
                active_sm,
                iters,
                reuse_factor,
                load_repeat,
                store_repeat,
            ) = key
            output_rows.append(
                {
                    "profile_name": profile_name,
                    "gpu_id": gpu_id,
                    "n_gpu_active": n_gpu_active,
                    "W_SM_KiB": w_sm_kib,
                    "blocks_per_SM": blocks_per_sm,
                    "active_SM": active_sm,
                    "ITER": iters,
                    "reuse_factor": reuse_factor,
                    "load_repeat": load_repeat,
                    "store_repeat": store_repeat,
                    "pair": spec["pair"],
                    "numerator_mode": spec["numerator_mode"],
                    "baseline_mode": spec["baseline_mode"],
                    "numerator_elapsed_s": numerator_elapsed,
                    "baseline_elapsed_s": baseline_elapsed,
                    "elapsed_ratio": elapsed_ratio,
                    "delta_E_J": delta_j,
                    "denominator": denominator,
                    "denominator_column": denominator_column,
                    "coefficient": coeff,
                    "coefficient_unit": spec["coefficient_unit"],
                    "numerator_rows": numerator["row_count"],
                    "baseline_rows": baseline["row_count"],
                    "valid_component_estimate": valid_component_estimate,
                    "diagnostic": diagnostic,
                }
            )

    output_rows.sort(
        key=lambda row: (
            row["profile_name"],
            int(row["gpu_id"]),
            int(row["W_SM_KiB"]),
            int(row["blocks_per_SM"]),
            int(row["active_SM"]),
            int(row["ITER"]),
            row["pair"],
        )
    )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        fieldnames = [
            "profile_name",
            "gpu_id",
            "n_gpu_active",
            "W_SM_KiB",
            "blocks_per_SM",
            "active_SM",
            "ITER",
            "reuse_factor",
            "load_repeat",
            "store_repeat",
            "pair",
            "numerator_mode",
            "baseline_mode",
            "numerator_elapsed_s",
            "baseline_elapsed_s",
            "elapsed_ratio",
            "delta_E_J",
            "denominator",
            "denominator_column",
            "coefficient",
            "coefficient_unit",
            "numerator_rows",
            "baseline_rows",
            "valid_component_estimate",
            "diagnostic",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    write_markdown(output_rows, Path(args.out_md))
    print(f"wrote csv: {out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"paired rows: {len(output_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
