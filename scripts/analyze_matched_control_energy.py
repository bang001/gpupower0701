#!/usr/bin/env python3
"""Analyze duration-calibrated component runs with matched controls.

The duration-calibrated runner intentionally lets each mode choose its own ITER.
That means same-ITER pair analyzers are not appropriate. This script matches
rows by configuration excluding ITER, converts the control row to a power rate,
and subtracts `control_power_W * numerator_elapsed_s` from the numerator energy.

The output is an effective microbenchmark energy estimate. It is not a pure
physical SRAM/register/DRAM bitcell energy.
"""

from __future__ import annotations

import argparse
import csv
import math
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
        "pair": "global_l1_load_only_minus_clocked_empty",
        "numerator_mode": "global_l1_load_only",
        "control_mode": "clocked_empty",
        "denominator_column": "expected_l1_bytes",
        "unit": "pJ/byte",
    },
    {
        "component": "l2_hit_cg_path",
        "pair": "l2_cg_load_only_minus_clocked_empty",
        "numerator_mode": "l2_cg_load_only",
        "control_mode": "clocked_empty",
        "denominator_column": "expected_l2_bytes",
        "unit": "pJ/byte",
    },
    {
        "component": "dram_cg_stream_path",
        "pair": "dram_cg_load_only_minus_clocked_empty",
        "numerator_mode": "dram_cg_load_only",
        "control_mode": "clocked_empty",
        "denominator_column": "expected_dram_bytes",
        "unit": "pJ/byte",
    },
]


CONTROL_MODES = {"clocked_empty"}
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


def config_key(row: dict[str, str]) -> tuple[str, ...]:
    """Key for duration-calibrated rows. ITER is intentionally excluded."""

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
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                row = dict(row)
                row["_source_file"] = path
                rows.append(row)
    return rows


def read_accepted_modes(path: str) -> set[str]:
    if not path:
        return set()
    accepted: set[str] = set()
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            if row.get("acceptance") == "accepted":
                accepted.add(row.get("mode", ""))
    return accepted


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
    actual_column_by_mode = {
        "shared_scalar_load_only": "shared_bytes",
        "shared_load_only": "shared_bytes",
        "global_l1_load_only": "l1_bytes",
        "l2_cg_load_only": "l2_bytes",
        "l2_load_only": "l2_bytes",
        "dram_cg_load_only": "dram_bytes",
        "dram_load_only": "dram_bytes",
    }
    for path in paths:
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f):
                mode = row.get("mode", "")
                actual_column = actual_column_by_mode.get(mode)
                if not actual_column or row.get("status") != "ok":
                    continue
                expected = ncu_expected_bytes(row)
                actual = as_float(row, actual_column)
                if expected <= 0.0 or actual <= 0.0:
                    continue
                scale = actual / expected
                exact_key = (
                    mode,
                    row.get("W_SM_KiB", ""),
                    row.get("blocks_per_SM", ""),
                    row.get("active_SM", ""),
                    row.get("reuse_factor", "1"),
                    row.get("load_repeat", "1"),
                    row.get("store_repeat", "1"),
                )
                working_set_key = (
                    mode,
                    row.get("W_SM_KiB", ""),
                    row.get("blocks_per_SM", ""),
                    row.get("active_SM", ""),
                )
                exact[exact_key] = (scale, actual)
                same_working_set[working_set_key] = (scale, actual)
    return exact, same_working_set


def ncu_scale_for_row(
    row: dict[str, str],
    *,
    exact_scales: dict[tuple[str, ...], tuple[float, float]],
    same_working_set_scales: dict[tuple[str, ...], tuple[float, float]],
) -> tuple[float, str, float]:
    mode = row.get("mode", "")
    exact_key = (
        mode,
        row.get("W_SM_KiB", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
        row.get("reuse_factor", "1"),
        row.get("load_repeat", "1"),
        row.get("store_repeat", "1"),
    )
    if exact_key in exact_scales:
        scale, actual = exact_scales[exact_key]
        return scale, "ncu_actual_exact", actual
    working_set_key = (
        mode,
        row.get("W_SM_KiB", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
    )
    if working_set_key in same_working_set_scales:
        scale, actual = same_working_set_scales[working_set_key]
        return scale, "ncu_actual_same_working_set", actual
    return 1.0, "expected_no_ncu_match", 0.0


def row_ok(row: dict[str, str], *, min_elapsed_s: float) -> tuple[bool, str]:
    reasons: list[str] = []
    if not is_active_row(row):
        reasons.append("inactive_gpu")
    if row.get("smid_histogram_ok", "").lower() != "true":
        reasons.append("smid_histogram_not_ok")
    if as_float(row, "elapsed_s") < min_elapsed_s:
        reasons.append("elapsed_too_short")
    if as_float(row, "net_E_J") <= 0.0:
        reasons.append("nonpositive_net_energy")
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
    exact_ncu_scales: dict[tuple[str, ...], tuple[float, float]],
    same_working_set_ncu_scales: dict[tuple[str, ...], tuple[float, float]],
    min_elapsed_s: float,
    max_elapsed_ratio: float,
    require_ncu_denominator: bool,
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
                ok, _ = row_ok(row, min_elapsed_s=min_elapsed_s)
                if ok:
                    num_ok_rows.append(row)
            for row in control_rows:
                ok, _ = row_ok(row, min_elapsed_s=min_elapsed_s)
                if ok:
                    ctl_ok_rows.append(row)
            if not num_ok_rows or not ctl_ok_rows:
                continue

            numerator = sorted(num_ok_rows, key=lambda r: as_float(r, "net_E_J"))[
                len(num_ok_rows) // 2
            ]
            control = sorted(ctl_ok_rows, key=lambda r: as_float(r, "net_E_J"))[
                len(ctl_ok_rows) // 2
            ]

            numerator_elapsed = as_float(numerator, "elapsed_s")
            control_elapsed = as_float(control, "elapsed_s")
            numerator_energy = as_float(numerator, "net_E_J")
            control_energy = as_float(control, "net_E_J")
            control_power = control_energy / control_elapsed if control_elapsed > 0.0 else 0.0
            control_energy_scaled = control_power * numerator_elapsed
            delta_j = numerator_energy - control_energy_scaled
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

            reasons: list[str] = []
            if elapsed_ratio > max_elapsed_ratio:
                reasons.append(f"elapsed_ratio>{max_elapsed_ratio:g}")
            if denominator <= 0.0:
                reasons.append("nonpositive_denominator")
            if (
                require_ncu_denominator
                and spec["unit"] == "pJ/byte"
                and denominator_source == "expected_no_ncu_match"
            ):
                reasons.append("missing_ncu_denominator")
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
                    "numerator_mode": numerator_mode,
                    "control_mode": control_mode,
                    "numerator_elapsed_s": numerator_elapsed,
                    "control_elapsed_s": control_elapsed,
                    "elapsed_ratio": elapsed_ratio,
                    "numerator_net_E_J": numerator_energy,
                    "control_net_E_J": control_energy,
                    "control_power_W": control_power,
                    "control_energy_scaled_J": control_energy_scaled,
                    "delta_E_J": delta_j,
                    "denominator_column": spec["denominator_column"],
                    "denominator": denominator,
                    "denominator_scale": denominator_scale,
                    "denominator_source": denominator_source,
                    "ncu_denominator_bytes_representative": ncu_denominator_bytes,
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
        pbit_values = [
            float(row["coefficient_pJ_per_bit"])
            for row in rows
            if row["coefficient_pJ_per_bit"] != ""
        ]
        pbit_stats = summarize_coefficients(pbit_values)
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
                "min": stats["min"],
                "median": stats["median"],
                "mean": stats["mean"],
                "max": stats["max"],
                "stdev": stats["stdev"],
                "median_pJ_per_bit": (
                    pbit_stats["median"] if int(pbit_stats["n"]) > 0 else ""
                ),
                "min_pJ_per_bit": (
                    pbit_stats["min"] if int(pbit_stats["n"]) > 0 else ""
                ),
                "max_pJ_per_bit": (
                    pbit_stats["max"] if int(pbit_stats["n"]) > 0 else ""
                ),
            }
        )
    return summary_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
            "`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.\n\n"
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
        f.write(f"| acceptance CSV | `{args.acceptance_csv}` |\n")
        f.write(f"| NCU summary CSVs | `{', '.join(args.ncu_summary_csv)}` |\n")
        f.write(f"| min elapsed (s) | {args.min_elapsed_s:g} |\n")
        f.write(f"| max elapsed ratio | {args.max_elapsed_ratio:g} |\n")
        f.write(f"| require NCU denominator | {args.require_ncu_denominator} |\n")
        f.write("\n## Component Summary\n\n")
        f.write(
            "| component | rows | NCU denominator rows | expected denominator rows | estimate unit | min | median | mean | max | stdev | median pJ/bit | pJ/bit min-max |\n"
        )
        f.write("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|\n")
        for row in summary_rows:
            pbit_range = ""
            if row["median_pJ_per_bit"] != "":
                pbit_range = (
                    f"{fmt(row['min_pJ_per_bit'])} - {fmt(row['max_pJ_per_bit'])}"
                )
            f.write(
                f"| {row['component']} | {row['rows']} | "
                f"{row['ncu_denominator_rows']} | "
                f"{row['expected_denominator_rows']} | {row['unit']} | "
                f"{fmt(row['min'])} | {fmt(row['median'])} | "
                f"{fmt(row['mean'])} | {fmt(row['max'])} | "
                f"{fmt(row['stdev'])} | {fmt(row['median_pJ_per_bit'])} | "
                f"{pbit_range} |\n"
            )
        f.write("\n## Detail Rows\n\n")
        f.write(
            "| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | delta_E (J) | denominator | denominator source | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |\n"
        )
        f.write(
            "|---|---:|---:|---:|---:|---|---:|---:|---|---:|---|---:|---:|---|---|\n"
        )
        for row in detail_rows:
            f.write(
                f"| {row['component']} | {row['W_SM_KiB']} | "
                f"{row['blocks_per_SM']} | {row['reuse_factor']} | "
                f"{row['load_repeat']} | "
                f"{row['pair']} | {fmt(row['delta_E_J'])} | "
                f"{fmt(row['denominator'])} | {row['denominator_source']} | "
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_paths", nargs="+")
    parser.add_argument(
        "--acceptance-csv",
        default="",
        help="Optional NCU acceptance CSV. Accepted numerator modes are kept.",
    )
    parser.add_argument(
        "--ncu-summary-csv",
        nargs="*",
        default=[],
        help="Optional NCU summary CSVs used to scale byte denominators by actual traffic.",
    )
    parser.add_argument(
        "--require-ncu-denominator",
        action="store_true",
        help="Reject byte-path rows without a matching NCU denominator scale.",
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
    parser.add_argument("--max-elapsed-ratio", type=float, default=1.35)
    args = parser.parse_args()

    rows = read_rows(args.csv_paths)
    accepted_modes = read_accepted_modes(args.acceptance_csv)
    exact_ncu_scales, same_working_set_ncu_scales = read_ncu_denominator_scales(
        args.ncu_summary_csv
    )
    detail_rows = make_detail_rows(
        rows,
        accepted_modes=accepted_modes,
        exact_ncu_scales=exact_ncu_scales,
        same_working_set_ncu_scales=same_working_set_ncu_scales,
        min_elapsed_s=args.min_elapsed_s,
        max_elapsed_ratio=args.max_elapsed_ratio,
        require_ncu_denominator=args.require_ncu_denominator,
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
        "numerator_mode",
        "control_mode",
        "numerator_elapsed_s",
        "control_elapsed_s",
        "elapsed_ratio",
        "numerator_net_E_J",
        "control_net_E_J",
        "control_power_W",
        "control_energy_scaled_J",
        "delta_E_J",
        "denominator_column",
        "denominator",
        "denominator_scale",
        "denominator_source",
        "ncu_denominator_bytes_representative",
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
        "min",
        "median",
        "mean",
        "max",
        "stdev",
        "median_pJ_per_bit",
        "min_pJ_per_bit",
        "max_pJ_per_bit",
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
