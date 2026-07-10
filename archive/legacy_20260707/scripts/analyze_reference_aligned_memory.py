#!/usr/bin/env python3
"""Reference-aligned memory path analysis from energy rows joined with NCU.

The goal is deliberately narrower than a pure component model. It reports
path-normalized board-level effective coefficients only for rows that pass
NCU hit-rate and traffic-shape checks. Static expected bytes are not used as a
final denominator.
"""

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
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
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


def classify_row(row: dict[str, str], args: argparse.Namespace) -> tuple[str, str]:
    mode = row.get("mode", "")
    include_blocks = {
        item.strip()
        for item in args.include_blocks_per_sm.split(",")
        if item.strip()
    }
    if include_blocks and row.get("blocks_per_SM", "") not in include_blocks:
        return "reject", "blocks_per_sm_not_selected"

    l1_hit = as_float(row, "ncu_l1_hit_rate_pct", -1.0)
    l2_hit = as_float(row, "ncu_l2_hit_rate_pct", -1.0)
    l1_bytes = as_float(row, "ncu_l1_bytes")
    l2_bytes = as_float(row, "ncu_l2_bytes")
    dram_bytes = as_float(row, "ncu_dram_bytes")
    shared_accesses = as_float(row, "ncu_shared_accesses")

    if not is_active(row):
        return "reject", "inactive_gpu"
    if row.get("smid_histogram_ok", "").lower() != "true":
        return "reject", "smid_histogram_failed"
    if as_float(row, "elapsed_s") <= 0.0:
        return "reject", "nonpositive_elapsed"
    if as_float(row, "net_E_J") <= 0.0:
        return "reject", "nonpositive_net_energy"
    if not ncu_joined(row):
        return "reject", "missing_ncu_join"
    if row.get("ncu_status") not in {"", "ok"}:
        return "reject", f"ncu_status_{row.get('ncu_status')}"

    if mode == "global_l1_load_only":
        if l1_hit < args.l1_hit_min_pct:
            return "reject", "l1_hit_below_threshold"
        if not finite_positive(l1_bytes):
            return "reject", "missing_l1_bytes"
        if l2_bytes / l1_bytes > args.l1_l2_byte_ratio_max:
            return "reject", "l2_traffic_too_high_for_l1"
        return "global_l1_path", "accepted"

    if mode == "l2_load_only":
        if l2_hit < args.l2_hit_min_pct:
            return "reject", "l2_hit_below_threshold"
        if not finite_positive(l2_bytes):
            return "reject", "missing_l2_bytes"
        if l1_bytes > 0.0 and l2_bytes / l1_bytes < args.l2_l1_byte_ratio_min:
            return "reject", "l1_dominated_not_l2"
        if l2_bytes > 0.0 and dram_bytes / l2_bytes > args.l2_dram_byte_ratio_max:
            return "reject", "dram_traffic_too_high_for_l2"
        return "l2_hit_path", "accepted"

    if mode == "dram_load_only":
        if l2_hit > args.dram_l2_hit_max_pct:
            return "reject", "l2_hit_too_high_for_dram"
        if not finite_positive(dram_bytes):
            return "reject", "missing_dram_bytes"
        if l2_bytes > 0.0 and dram_bytes / l2_bytes < args.dram_l2_byte_ratio_min:
            return "reject", "dram_bytes_not_dominant"
        return "dram_streaming_path", "accepted"

    if mode == "shared_load_only":
        if not finite_positive(shared_accesses):
            return "reject", "missing_shared_accesses"
        return "shared_path_traffic_verified", "accepted_no_shared_byte_denominator"

    return "reject", "mode_not_in_memory_path_set"


def denominator_bytes(row: dict[str, str], component: str) -> float:
    if component == "global_l1_path":
        return as_float(row, "ncu_l1_bytes")
    if component == "l2_hit_path":
        return as_float(row, "ncu_l2_bytes")
    if component == "dram_streaming_path":
        return as_float(row, "ncu_dram_bytes")
    return 0.0


def path_pj_per_bit(row: dict[str, str], component: str) -> float:
    denom = denominator_bytes(row, component)
    if denom <= 0.0:
        return math.nan
    return as_float(row, "net_E_J") * 1.0e12 / (denom * 8.0)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else math.nan


def summarize(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["accepted"] == "true":
            grouped[row["component"]].append(row)

    out: list[dict[str, Any]] = []
    for component in [
        "global_l1_path",
        "l2_hit_path",
        "dram_streaming_path",
        "shared_path_traffic_verified",
    ]:
        items = grouped.get(component, [])
        values = [
            as_float(row, "path_pj_per_bit", math.nan)
            for row in items
            if finite_positive(as_float(row, "path_pj_per_bit", math.nan))
        ]
        out.append(
            {
                "component": component,
                "accepted_rows": len(items),
                "estimate_pj_per_bit": median(values),
                "estimate_pj_per_byte": median(values) * 8.0 if values else math.nan,
                "min_pj_per_bit": min(values) if values else math.nan,
                "max_pj_per_bit": max(values) if values else math.nan,
                "method": (
                    "net_E_J / NCU_actual_path_bits"
                    if component != "shared_path_traffic_verified"
                    else "traffic_verified_only_no_ncu_shared_byte_denominator"
                ),
            }
        )

    by_component = {row["component"]: row for row in out}
    l1 = by_component["global_l1_path"]["estimate_pj_per_bit"]
    l2 = by_component["l2_hit_path"]["estimate_pj_per_bit"]
    dram = by_component["dram_streaming_path"]["estimate_pj_per_bit"]
    if finite_positive(l1) and finite_positive(l2):
        out.append(
            {
                "component": "l2_minus_l1_path_delta",
                "accepted_rows": "",
                "estimate_pj_per_bit": l2 - l1,
                "estimate_pj_per_byte": (l2 - l1) * 8.0,
                "min_pj_per_bit": "",
                "max_pj_per_bit": "",
                "method": "diagnostic_delta_not_pure_component",
            }
        )
    if finite_positive(l2) and finite_positive(dram):
        out.append(
            {
                "component": "dram_minus_l2_path_delta",
                "accepted_rows": "",
                "estimate_pj_per_bit": dram - l2,
                "estimate_pj_per_byte": (dram - l2) * 8.0,
                "min_pj_per_bit": "",
                "max_pj_per_bit": "",
                "method": "diagnostic_delta_not_pure_component",
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.6g}"
    return str(value)


def write_markdown(
    path: Path,
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, str]],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rejected = [row for row in detail_rows if row["accepted"] == "false"]
    accepted = [row for row in detail_rows if row["accepted"] == "true"]
    with path.open("w") as f:
        f.write("# Reference-Aligned Memory Energy Analysis\n\n")
        f.write("## Acceptance Rules\n\n")
        f.write("| rule | value |\n")
        f.write("|---|---:|\n")
        f.write(f"| L1 hit min (%) | {args.l1_hit_min_pct:g} |\n")
        f.write(f"| L1 row max L2/L1 byte ratio | {args.l1_l2_byte_ratio_max:g} |\n")
        f.write(f"| L2 hit min (%) | {args.l2_hit_min_pct:g} |\n")
        f.write(f"| L2 row min L2/L1 byte ratio | {args.l2_l1_byte_ratio_min:g} |\n")
        f.write(f"| L2 row max DRAM/L2 byte ratio | {args.l2_dram_byte_ratio_max:g} |\n")
        f.write(f"| DRAM row max L2 hit (%) | {args.dram_l2_hit_max_pct:g} |\n")
        f.write("\n## Component/Path Estimates\n\n")
        f.write("| component/path | accepted rows | estimate | unit | min | max | method |\n")
        f.write("|---|---:|---:|---|---:|---:|---|\n")
        for row in summary_rows:
            f.write(
                f"| {row['component']} | {row['accepted_rows']} | "
                f"{fmt(row['estimate_pj_per_bit'])} | pJ/bit | "
                f"{fmt(row['min_pj_per_bit'])} | {fmt(row['max_pj_per_bit'])} | "
                f"{row['method']} |\n"
            )
        f.write("\n## Important Interpretation\n\n")
        f.write(
            "The path estimates above use NVML board net energy divided by NCU "
            "actual path traffic. They are reference-aligned effective path "
            "coefficients, not SRAM/HBM bitcell energy. Diagnostic deltas are "
            "shown only to test ordering; they are not pure isolated component "
            "energy.\n"
        )
        f.write("\n## Row QA\n\n")
        f.write("| item | count |\n")
        f.write("|---|---:|\n")
        f.write(f"| accepted rows | {len(accepted)} |\n")
        f.write(f"| rejected rows | {len(rejected)} |\n")
        f.write("\n### Accepted Rows\n\n")
        f.write("| mode | W_SM (KiB) | blocks/SM | component | pJ/bit | L1 hit (%) | L2 hit (%) | reason |\n")
        f.write("|---|---:|---:|---|---:|---:|---:|---|\n")
        for row in accepted:
            f.write(
                f"| {row['mode']} | {row['W_SM_KiB']} | {row['blocks_per_SM']} | "
                f"{row['component']} | {row['path_pj_per_bit']} | "
                f"{row['ncu_l1_hit_rate_pct']} | {row['ncu_l2_hit_rate_pct']} | "
                f"{row['reason']} |\n"
            )
        f.write("\n### Rejection Reasons\n\n")
        counts: dict[str, int] = defaultdict(int)
        for row in rejected:
            counts[row["reason"]] += 1
        f.write("| reason | rows |\n")
        f.write("|---|---:|\n")
        for reason, count in sorted(counts.items()):
            f.write(f"| {reason} | {count} |\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("joined_energy_csv")
    parser.add_argument("--out-summary-csv", required=True)
    parser.add_argument("--out-detail-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--l1-hit-min-pct", type=float, default=95.0)
    parser.add_argument("--l1-l2-byte-ratio-max", type=float, default=0.01)
    parser.add_argument("--l2-hit-min-pct", type=float, default=80.0)
    parser.add_argument("--l2-l1-byte-ratio-min", type=float, default=0.02)
    parser.add_argument("--l2-dram-byte-ratio-max", type=float, default=0.02)
    parser.add_argument("--dram-l2-hit-max-pct", type=float, default=5.0)
    parser.add_argument("--dram-l2-byte-ratio-min", type=float, default=0.5)
    parser.add_argument(
        "--include-blocks-per-sm",
        default="",
        help="Optional comma-separated blocks/SM allow-list for representative subsets.",
    )
    args = parser.parse_args()

    rows = read_rows(Path(args.joined_energy_csv))
    detail_rows: list[dict[str, str]] = []
    for row in rows:
        component, reason = classify_row(row, args)
        accepted = component != "reject"
        pj_bit = path_pj_per_bit(row, component) if accepted else math.nan
        detail_rows.append(
            {
                "mode": row.get("mode", ""),
                "W_SM_KiB": row.get("W_SM_KiB", ""),
                "blocks_per_SM": row.get("blocks_per_SM", ""),
                "active_SM": row.get("active_SM", ""),
                "load_repeat": row.get("load_repeat", ""),
                "ITER": row.get("ITER", ""),
                "elapsed_s": row.get("elapsed_s", ""),
                "net_E_J": row.get("net_E_J", ""),
                "component": component,
                "accepted": "true" if accepted else "false",
                "reason": reason,
                "path_pj_per_bit": fmt(pj_bit),
                "denominator_bytes": fmt(denominator_bytes(row, component)),
                "ncu_l1_hit_rate_pct": row.get("ncu_l1_hit_rate_pct", ""),
                "ncu_l2_hit_rate_pct": row.get("ncu_l2_hit_rate_pct", ""),
                "ncu_l1_bytes": row.get("ncu_l1_bytes", ""),
                "ncu_l2_bytes": row.get("ncu_l2_bytes", ""),
                "ncu_dram_bytes": row.get("ncu_dram_bytes", ""),
                "ncu_shared_accesses": row.get("ncu_shared_accesses", ""),
                "ncu_stall_long_scoreboard_pct": row.get(
                    "ncu_stall_long_scoreboard_pct", ""
                ),
                "notes": row.get("notes", ""),
            }
        )

    summary_rows = summarize(detail_rows)
    write_csv(Path(args.out_detail_csv), detail_rows)
    write_csv(Path(args.out_summary_csv), summary_rows)
    write_markdown(Path(args.out_md), summary_rows, detail_rows, args)
    print(f"wrote summary csv: {args.out_summary_csv}")
    print(f"wrote detail csv: {args.out_detail_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(
        "accepted rows: "
        f"{sum(1 for row in detail_rows if row['accepted'] == 'true')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
