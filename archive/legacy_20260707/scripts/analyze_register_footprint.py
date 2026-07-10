#!/usr/bin/env python3
"""Analyze register-footprint sweep results."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    return float(value)


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    return int(as_float(row, key, float(default)))


def is_active(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=1" in notes:
        return True
    if "gpu_active=0" in notes:
        return False
    return as_int(row, "n_gpu_active") > 0


def key_for(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        row.get("profile_name", ""),
        row.get("gpu_id", ""),
        row.get("n_gpu_active", ""),
        row.get("reg_payload_bytes_per_block", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
        row.get("ITER", ""),
        row.get("reuse_factor", "1"),
    )


def median(rows: list[dict[str, str]], key: str) -> float:
    vals = [as_float(row, key) for row in rows if row.get(key, "") != ""]
    return statistics.median(vals) if vals else 0.0


def linear_slope(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 0.0:
        raise ValueError("zero x variance")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    return intercept, slope, rmse


def load_matrix(path: str | None) -> dict[tuple[str, str], dict[str, str]]:
    if not path:
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            out[(row["reg_payload_bytes_per_block"], row["blocks_per_SM"])] = row
    return out


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Register Footprint Summary\n\n")
        f.write(
            "Direct pJ/reg-update values are effective scalar register-pressure "
            "coefficients. They are not pure register-file access energy.\n\n"
        )
        f.write(
            "| payload (B/block) | ptxas regs/thread | compiler footprint (B/block) | "
            "blocks/SM | active_SM (SMs) | reuse | delta_E_J (J) | "
            "updates | pressure power (W) | update rate (/s) | "
            "direct coefficient (pJ/reg-update) | rows |\n"
        )
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            f.write(
                f"| {row['reg_payload_bytes_per_block']} | "
                f"{row['ptxas_registers_per_thread']} | "
                f"{row['compiler_footprint_bytes_per_block']} | "
                f"{row['blocks_per_SM']} | {row['active_SM']} | "
                f"{row['reuse_factor']} | {row['delta_E_J']:.6g} | "
                f"{row['expected_reg_pressure_ops']:.6g} | "
                f"{row['pressure_power_W']:.6g} | "
                f"{row['update_rate_per_s']:.6g} | "
                f"{row['pJ_per_reg_update']:.6g} | "
                f"{row['pressure_rows']}/{row['empty_rows']} |\n"
            )
        slope_rows = [
            row
            for row in rows
            if row["update_rate_per_s"] > 0.0 and row["pressure_power_W"] > 0.0
        ]
        f.write("\n## Power-Rate Slope\n\n")
        if len(slope_rows) >= 2:
            xs = [row["update_rate_per_s"] for row in slope_rows]
            ys = [row["pressure_power_W"] for row in slope_rows]
            intercept, slope, rmse = linear_slope(xs, ys)
            mean_power = statistics.mean(ys)
            f.write("| item | value | unit |\n")
            f.write("|---|---:|---|\n")
            f.write(f"| rows | {len(slope_rows)} | rows |\n")
            f.write(f"| intercept | {intercept:.6g} | W |\n")
            f.write(f"| slope | {slope * 1.0e12:.6g} | pJ/reg-update |\n")
            f.write(f"| RMSE | {rmse:.6g} | W |\n")
            rel = 100.0 * rmse / mean_power if mean_power else 0.0
            f.write(f"| relative RMSE | {rel:.6g} | % |\n")
            f.write(
                "\nThe slope is a better proxy than direct division because the "
                "intercept absorbs fixed active/control power. It still includes "
                "integer ALU, scheduler, dependency, and issue effects.\n"
            )
        else:
            f.write("Not enough rows for a power-rate slope.\n")

        f.write("\n## Interpretation Limits\n\n")
        f.write(
            "- The same-ITER `empty` row can be much shorter than `reg_pressure`; "
            "direct delta therefore does not remove fixed active power.\n"
        )
        f.write(
            "- `reg_pressure` updates contain scalar integer operations and "
            "dependency chains, not isolated register-file reads/writes.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--matrix-csv", default="")
    parser.add_argument("--out-csv", default="results/summary/register_footprint_summary.csv")
    parser.add_argument("--out-md", default="results/summary/register_footprint_summary.md")
    parser.add_argument("--include-placement-failures", action="store_true")
    args = parser.parse_args()

    with Path(args.csv_path).open(newline="") as f:
        input_rows = list(csv.DictReader(f))
    matrix = load_matrix(args.matrix_csv)

    grouped: dict[tuple[Any, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in input_rows:
        if not is_active(row):
            continue
        if (
            not args.include_placement_failures
            and row.get("smid_histogram_ok", "").lower() == "false"
        ):
            continue
        if row.get("mode") not in {"empty", "reg_pressure"}:
            continue
        grouped[key_for(row)][row.get("mode", "")].append(row)

    output_rows: list[dict[str, Any]] = []
    for key, rows_by_mode in grouped.items():
        pressure = rows_by_mode.get("reg_pressure")
        empty = rows_by_mode.get("empty")
        if not pressure or not empty:
            continue
        (
            profile_name,
            gpu_id,
            n_gpu_active,
            payload,
            blocks_per_sm,
            active_sm,
            iters,
            reuse_factor,
        ) = key
        delta = median(pressure, "net_E_J") - median(empty, "net_E_J")
        denom = median(pressure, "expected_reg_pressure_ops")
        coeff = delta * 1.0e12 / denom if denom > 0 else 0.0
        pressure_elapsed = median(pressure, "elapsed_s")
        empty_elapsed = median(empty, "elapsed_s")
        pressure_power = (
            median(pressure, "net_E_J") / pressure_elapsed
            if pressure_elapsed > 0.0
            else 0.0
        )
        empty_power = (
            median(empty, "net_E_J") / empty_elapsed
            if empty_elapsed > 0.0
            else 0.0
        )
        update_rate = denom / pressure_elapsed if pressure_elapsed > 0.0 else 0.0
        matrix_row = matrix.get((payload, blocks_per_sm), {})
        output_rows.append(
            {
                "profile_name": profile_name,
                "gpu_id": gpu_id,
                "n_gpu_active": n_gpu_active,
                "reg_payload_bytes_per_block": int(float(payload or 0)),
                "blocks_per_SM": int(float(blocks_per_sm or 0)),
                "active_SM": int(float(active_sm or 0)),
                "ITER": int(float(iters or 0)),
                "reuse_factor": int(float(reuse_factor or 1)),
                "delta_E_J": delta,
                "expected_reg_pressure_ops": denom,
                "pJ_per_reg_update": coeff,
                "pressure_elapsed_s": pressure_elapsed,
                "empty_elapsed_s": empty_elapsed,
                "pressure_power_W": pressure_power,
                "empty_power_W": empty_power,
                "update_rate_per_s": update_rate,
                "pressure_rows": len(pressure),
                "empty_rows": len(empty),
                "ptxas_registers_per_thread": matrix_row.get(
                    "ptxas_registers_per_thread", ""
                ),
                "compiler_footprint_bytes_per_block": matrix_row.get(
                    "compiler_footprint_bytes_per_block", ""
                ),
                "compiler_footprint_bytes_per_sm": matrix_row.get(
                    "compiler_footprint_bytes_per_sm", ""
                ),
                "spill_free": matrix_row.get("spill_free", ""),
                "max_resident_blocks_per_sm_est": matrix_row.get(
                    "max_resident_blocks_per_sm_est", ""
                ),
            }
        )

    output_rows.sort(
        key=lambda row: (
            row["reg_payload_bytes_per_block"],
            row["blocks_per_SM"],
            row["reuse_factor"],
            row["active_SM"],
        )
    )
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile_name",
        "gpu_id",
        "n_gpu_active",
        "reg_payload_bytes_per_block",
        "ptxas_registers_per_thread",
        "compiler_footprint_bytes_per_block",
        "compiler_footprint_bytes_per_sm",
        "spill_free",
        "max_resident_blocks_per_sm_est",
        "blocks_per_SM",
        "active_SM",
        "ITER",
        "reuse_factor",
        "delta_E_J",
        "expected_reg_pressure_ops",
        "pJ_per_reg_update",
        "pressure_elapsed_s",
        "empty_elapsed_s",
        "pressure_power_W",
        "empty_power_W",
        "update_rate_per_s",
        "pressure_rows",
        "empty_rows",
    ]
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in output_rows:
            writer.writerow(row)
    write_markdown(output_rows, Path(args.out_md))
    print(f"wrote csv: {out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"paired rows: {len(output_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
