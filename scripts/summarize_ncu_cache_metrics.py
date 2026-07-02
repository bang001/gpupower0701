#!/usr/bin/env python3
"""Summarize Nsight Compute cache hit-rate and access counters.

Nsight Compute metric names vary across GPU families and NCU versions. This
script accepts raw/details CSV exports and tries several known metric names for
L1TEX, L2/LTS, and DRAM. Missing fields are left blank and reported in notes so
the validation table is explicit about what NCU did or did not provide.
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Iterable


SECTOR_BYTES = 32.0


def parse_float(value: str) -> float | None:
    text = value.strip().replace(",", "")
    if not text or text.lower() in {"n/a", "nan", "inf", "-inf"}:
        return None
    text = text.rstrip("%")
    try:
        out = float(text)
    except ValueError:
        return None
    if not math.isfinite(out):
        return None
    return out


def find_column(row: dict[str, str], names: Iterable[str]) -> str:
    lowered = {key.strip().lower(): key for key in row}
    for name in names:
        key = lowered.get(name.lower())
        if key is not None:
            return row.get(key, "")
    return ""


def metric_name_from_row(row: dict[str, str]) -> str:
    value = find_column(
        row,
        [
            "Metric Name",
            "Metric",
            "Name",
            "metric_name",
            "MetricName",
        ],
    )
    if value:
        return value.strip()
    for value in row.values():
        if "__" in value:
            return value.strip()
    return ""


def metric_value_from_row(row: dict[str, str]) -> float | None:
    value = find_column(
        row,
        [
            "Metric Value",
            "Value",
            "Avg",
            "Average",
            "Sum",
            "metric_value",
            "MetricValue",
        ],
    )
    parsed = parse_float(value)
    if parsed is not None:
        return parsed
    for value in reversed(list(row.values())):
        parsed = parse_float(value)
        if parsed is not None:
            return parsed
    return None


def metric_unit_from_row(row: dict[str, str]) -> str:
    return find_column(row, ["Metric Unit", "Unit", "metric_unit", "MetricUnit"]).strip()


class Metrics:
    def __init__(self) -> None:
        self.values: dict[str, list[float]] = defaultdict(list)
        self.units: dict[str, str] = {}

    def add_file(self, path: Path) -> None:
        if not path.exists() or path.stat().st_size == 0:
            return
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = metric_name_from_row(row)
                if not name:
                    continue
                value = metric_value_from_row(row)
                if value is None:
                    continue
                self.values[name].append(value)
                unit = metric_unit_from_row(row)
                if unit:
                    self.units[name] = unit

    def values_for_base(self, base: str) -> list[float]:
        out: list[float] = []
        for name, values in self.values.items():
            if name == base or name.startswith(base + "."):
                out.extend(values)
        return out

    def sum_bases(self, bases: Iterable[str]) -> float | None:
        total = 0.0
        found = False
        for base in bases:
            values = self.values_for_base(base)
            if values:
                total += sum(values)
                found = True
        return total if found else None

    def first_bases(self, bases: Iterable[str]) -> float | None:
        for base in bases:
            values = self.values_for_base(base)
            if values:
                return median(values)
        return None

    def has_any(self, bases: Iterable[str]) -> bool:
        return any(self.values_for_base(base) for base in bases)


def percent_from_hit_miss(hit: float | None, miss: float | None) -> float | None:
    if hit is None or miss is None:
        return None
    denom = hit + miss
    if denom <= 0.0:
        return None
    return 100.0 * hit / denom


def first_non_none(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def sum_non_none(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def parse_case_label(path: Path) -> str:
    name = path.name
    for suffix in ["_raw_metrics.csv", "_details.csv"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def read_manifest(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row["label"]: row for row in csv.DictReader(f) if row.get("label")}


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}g}"


def summarize_case(label: str, files: list[Path], manifest: dict[str, str]) -> dict[str, str]:
    metrics = Metrics()
    for path in files:
        metrics.add_file(path)

    l1_hit_rate = first_non_none(
        metrics.first_bases(
            [
                "l1tex__t_sector_hit_rate",
                "l1tex__t_sectors_hit_rate",
                "l1tex__t_bytes_hit_rate",
            ]
        ),
        percent_from_hit_miss(
            metrics.sum_bases(
                [
                    "l1tex__t_sectors_lookup_hit",
                    "l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit",
                    "l1tex__t_bytes_lookup_hit",
                    "l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_hit",
                ]
            ),
            metrics.sum_bases(
                [
                    "l1tex__t_sectors_lookup_miss",
                    "l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_miss",
                    "l1tex__t_bytes_lookup_miss",
                    "l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_miss",
                ]
            ),
        ),
    )

    l2_hit_rate = first_non_none(
        metrics.first_bases(
            [
                "lts__t_sector_hit_rate",
                "lts__t_sectors_hit_rate",
                "lts__t_tag_hit_rate",
            ]
        ),
        percent_from_hit_miss(
            metrics.sum_bases(
                [
                    "lts__t_sectors_lookup_hit",
                    "lts__t_sectors_srcunit_tex_lookup_hit",
                    "lts__t_sectors_srcunit_tex_op_read_lookup_hit",
                    "lts__t_tag_requests_hit",
                ]
            ),
            metrics.sum_bases(
                [
                    "lts__t_sectors_lookup_miss",
                    "lts__t_sectors_srcunit_tex_lookup_miss",
                    "lts__t_sectors_srcunit_tex_op_read_lookup_miss",
                    "lts__t_tag_requests_miss",
                ]
            ),
        ),
    )

    l1_read_requests = metrics.sum_bases(
        [
            "l1tex__t_requests_pipe_lsu_mem_global_op_ld",
            "l1tex__t_requests_pipe_lsu_mem_local_op_ld",
        ]
    )
    l1_write_requests = metrics.sum_bases(
        [
            "l1tex__t_requests_pipe_lsu_mem_global_op_st",
            "l1tex__t_requests_pipe_lsu_mem_local_op_st",
        ]
    )
    l1_requests = first_non_none(
        sum_non_none(l1_read_requests, l1_write_requests),
        metrics.sum_bases(["l1tex__t_requests_pipe_lsu", "l1tex__t_requests"]),
    )
    l1_access_unit = "requests" if l1_requests is not None else "sectors"

    l1_read_sectors = metrics.sum_bases(
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_ld",
            "l1tex__t_sectors_pipe_lsu_mem_local_op_ld",
            "l1tex__m_xbar2l1tex_read_sectors_mem_lg_op_ld",
        ]
    )
    l1_write_sectors = metrics.sum_bases(
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_st",
            "l1tex__t_sectors_pipe_lsu_mem_local_op_st",
            "l1tex__m_l1tex2xbar_write_sectors_mem_lg_op_st",
        ]
    )
    l1_sectors = first_non_none(
        sum_non_none(l1_read_sectors, l1_write_sectors),
        metrics.sum_bases(["l1tex__t_sectors_pipe_lsu", "l1tex__t_sectors"]),
    )
    l1_accesses = l1_requests if l1_requests is not None else l1_sectors
    l1_read_accesses = l1_read_requests if l1_requests is not None else l1_read_sectors
    l1_write_accesses = l1_write_requests if l1_requests is not None else l1_write_sectors
    l1_bytes = first_non_none(
        metrics.sum_bases(
            [
                "l1tex__t_bytes_pipe_lsu_mem_global_op_ld",
                "l1tex__t_bytes_pipe_lsu_mem_global_op_st",
                "l1tex__t_bytes_pipe_lsu_mem_local_op_ld",
                "l1tex__t_bytes_pipe_lsu_mem_local_op_st",
            ]
        ),
        metrics.sum_bases(["l1tex__t_bytes_pipe_lsu", "l1tex__t_bytes"]),
        l1_sectors * SECTOR_BYTES if l1_sectors is not None else None,
    )

    l2_read_sectors = metrics.sum_bases(
        [
            "lts__t_sectors_op_read",
            "lts__t_sectors_srcunit_tex_op_read",
        ]
    )
    l2_write_sectors = metrics.sum_bases(
        [
            "lts__t_sectors_op_write",
            "lts__t_sectors_srcunit_tex_op_write",
        ]
    )
    l2_sectors = first_non_none(
        sum_non_none(l2_read_sectors, l2_write_sectors),
        metrics.sum_bases(["lts__t_sectors_srcunit_tex", "lts__t_sectors"]),
    )
    l2_bytes = first_non_none(
        metrics.sum_bases(["lts__t_bytes"]),
        metrics.sum_bases(["lts__t_bytes_srcunit_tex"]),
        l2_sectors * SECTOR_BYTES if l2_sectors is not None else None,
    )

    dram_read_sectors = metrics.sum_bases(["dram__sectors_read"])
    dram_write_sectors = metrics.sum_bases(["dram__sectors_write"])
    dram_sectors = first_non_none(
        sum_non_none(dram_read_sectors, dram_write_sectors),
        metrics.sum_bases(["dram__sectors"]),
    )
    dram_bytes = first_non_none(
        metrics.sum_bases(["dram__bytes"]),
        sum_non_none(
            metrics.sum_bases(["dram__bytes_read"]),
            metrics.sum_bases(["dram__bytes_write"]),
        ),
        dram_sectors * SECTOR_BYTES if dram_sectors is not None else None,
    )

    missing = []
    if l1_hit_rate is None:
        missing.append("l1_hit_rate_pct")
    if l2_hit_rate is None:
        missing.append("l2_hit_rate_pct")
    if l1_accesses is None:
        missing.append("l1_accesses")
    if l2_sectors is None:
        missing.append("l2_accesses")
    if dram_sectors is None:
        missing.append("dram_accesses")

    status = "ok" if not missing else "partial"
    if not metrics.values:
        status = "missing_metrics"

    row = {
        "label": label,
        "mode": manifest.get("mode", ""),
        "kernel_regex": manifest.get("kernel_regex", ""),
        "W_SM_KiB": manifest.get("W_SM_KiB", ""),
        "blocks_per_SM": manifest.get("blocks_per_SM", ""),
        "active_SM": manifest.get("active_SM", ""),
        "ITER": manifest.get("ITER", ""),
        "status": status,
        "l1_hit_rate_pct": fmt(l1_hit_rate),
        "l2_hit_rate_pct": fmt(l2_hit_rate),
        "l1_accesses": fmt(l1_accesses),
        "l1_access_unit": l1_access_unit,
        "l1_read_accesses": fmt(l1_read_accesses),
        "l1_write_accesses": fmt(l1_write_accesses),
        "l2_accesses": fmt(l2_sectors),
        "l2_access_unit": "sectors",
        "l2_read_accesses": fmt(l2_read_sectors),
        "l2_write_accesses": fmt(l2_write_sectors),
        "dram_accesses": fmt(dram_sectors),
        "dram_access_unit": "sectors",
        "dram_read_accesses": fmt(dram_read_sectors),
        "dram_write_accesses": fmt(dram_write_sectors),
        "l1_bytes": fmt(l1_bytes),
        "l2_bytes": fmt(l2_bytes),
        "dram_bytes": fmt(dram_bytes),
        "missing_metrics": ";".join(missing),
        "source_files": ";".join(str(path) for path in files),
    }
    return row


def collect_files(patterns: list[str]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for pattern in patterns:
        for match in glob.glob(pattern):
            path = Path(match)
            if not path.is_file():
                continue
            label = parse_case_label(path)
            grouped[label].append(path)
            if path.name.endswith("_raw_metrics.csv"):
                details = path.with_name(path.name.replace("_raw_metrics.csv", "_details.csv"))
                if details.exists():
                    grouped[label].append(details)
    return grouped


def write_markdown(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# NCU Cache Validation Summary\n\n")
        f.write(
            "| label | mode | W_SM (KiB) | blocks/SM | L1 hit (%) | L2 hit (%) | "
            "L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | "
            "L1 bytes | L2 bytes | DRAM bytes | status |\n"
        )
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for row in rows:
            l1_accesses = row["l1_accesses"]
            if l1_accesses and row["l1_access_unit"]:
                l1_accesses = f"{l1_accesses} {row['l1_access_unit']}"
            f.write(
                f"| {row['label']} | {row['mode']} | {row['W_SM_KiB']} | "
                f"{row['blocks_per_SM']} | {row['l1_hit_rate_pct']} | "
                f"{row['l2_hit_rate_pct']} | {l1_accesses} | "
                f"{row['l2_accesses']} | {row['dram_accesses']} | "
                f"{row['l1_bytes']} | {row['l2_bytes']} | {row['dram_bytes']} | "
                f"{row['status']} |\n"
            )
        f.write("\n")
        f.write("Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable.\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "patterns",
        nargs="*",
        help="Glob(s) for *_raw_metrics.csv or *_details.csv exports.",
    )
    parser.add_argument("--case-manifest", default="")
    parser.add_argument("--out-csv", default="results/summary/ncu_cache_validation_summary.csv")
    parser.add_argument("--out-md", default="results/summary/ncu_cache_validation_summary.md")
    args = parser.parse_args()

    patterns = args.patterns or ["results/ncu/**/*_raw_metrics.csv"]
    grouped = collect_files(patterns)
    manifest = read_manifest(Path(args.case_manifest) if args.case_manifest else None)

    rows = [
        summarize_case(label, sorted(set(files)), manifest.get(label, {}))
        for label, files in sorted(grouped.items())
    ]

    fieldnames = [
        "label",
        "mode",
        "kernel_regex",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "ITER",
        "status",
        "l1_hit_rate_pct",
        "l2_hit_rate_pct",
        "l1_accesses",
        "l1_access_unit",
        "l1_read_accesses",
        "l1_write_accesses",
        "l2_accesses",
        "l2_access_unit",
        "l2_read_accesses",
        "l2_write_accesses",
        "dram_accesses",
        "dram_access_unit",
        "dram_read_accesses",
        "dram_write_accesses",
        "l1_bytes",
        "l2_bytes",
        "dram_bytes",
        "missing_metrics",
        "source_files",
    ]
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    write_markdown(rows, Path(args.out_md))
    print(f"wrote csv: {out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"cases: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
