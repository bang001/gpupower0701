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
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Iterable


SECTOR_BYTES = 32.0
BYTE_UNIT_SCALE = {
    "byte": 1.0,
    "kbyte": 1.0e3,
    "mbyte": 1.0e6,
    "gbyte": 1.0e9,
    "tbyte": 1.0e12,
}
TIME_UNIT_SCALE_SECONDS = {
    "ns": 1.0e-9,
    "nsecond": 1.0e-9,
    "us": 1.0e-6,
    "usecond": 1.0e-6,
    "ms": 1.0e-3,
    "msecond": 1.0e-3,
    "s": 1.0,
    "second": 1.0,
}


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
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


def convert_value(value: float, unit: str) -> float:
    # NCU launch metrics use units such as Kbyte/block. The denominator suffix
    # describes the launch object, not a different byte scale.
    unit_key = unit.strip().lower().split("/", 1)[0]
    scale = BYTE_UNIT_SCALE.get(unit_key)
    if scale is not None:
        return value * scale
    time_scale = TIME_UNIT_SCALE_SECONDS.get(unit_key)
    return value * time_scale if time_scale is not None else value


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
                wide_metric_found = False
                for name, value in row.items():
                    if "__" not in name:
                        continue
                    parsed = parse_float(value)
                    if parsed is None:
                        if value:
                            self.units[name] = value.strip()
                        continue
                    self.values[name].append(convert_value(parsed, self.units.get(name, "")))
                    wide_metric_found = True
                if wide_metric_found:
                    continue
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
                    self.values[name][-1] = convert_value(self.values[name][-1], unit)

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

    def sum_names(self, names: Iterable[str]) -> float | None:
        total = 0.0
        found = False
        for name in names:
            values = self.values.get(name, [])
            if values:
                total += sum(values)
                found = True
        return total if found else None

    def first_names(self, names: Iterable[str]) -> float | None:
        for name in names:
            values = self.values.get(name, [])
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


def first_metric_sum(metrics: Metrics, names: Iterable[str]) -> float | None:
    """Return the first available metric sum without adding alias metrics."""

    for name in names:
        value = metrics.sum_names([name])
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

    l1_global_load_hit_sectors = first_metric_sum(
        metrics,
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit.sum",
            "l1tex__t_sectors_lookup_hit.sum",
        ],
    )
    l1_global_load_miss_sectors = first_metric_sum(
        metrics,
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_miss.sum",
            "l1tex__t_sectors_lookup_miss.sum",
        ],
    )
    l1_global_load_hit_bytes_counter = first_metric_sum(
        metrics,
        [
            "l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_hit.sum",
            "l1tex__t_bytes_lookup_hit.sum",
        ],
    )
    l1_global_load_miss_bytes_counter = first_metric_sum(
        metrics,
        [
            "l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_miss.sum",
            "l1tex__t_bytes_lookup_miss.sum",
        ],
    )
    l1_hit_bytes = first_non_none(
        l1_global_load_hit_bytes_counter,
        l1_global_load_hit_sectors * SECTOR_BYTES
        if l1_global_load_hit_sectors is not None
        else None,
    )
    l1_miss_bytes = first_non_none(
        l1_global_load_miss_bytes_counter,
        l1_global_load_miss_sectors * SECTOR_BYTES
        if l1_global_load_miss_sectors is not None
        else None,
    )
    l1_path_hit_rate = first_non_none(
        percent_from_hit_miss(
            l1_global_load_hit_sectors, l1_global_load_miss_sectors
        ),
        percent_from_hit_miss(
            l1_global_load_hit_bytes_counter, l1_global_load_miss_bytes_counter
        ),
    )
    l1_aggregate_hit_rate = metrics.first_names(
        [
            "l1tex__t_sector_hit_rate.pct",
            "l1tex__t_sectors_hit_rate.pct",
            "l1tex__t_bytes_hit_rate.pct",
        ]
    )
    l1_hit_rate = first_non_none(l1_path_hit_rate, l1_aggregate_hit_rate)
    l1_hit_rate_source = (
        "global_load_lookup_hit_miss"
        if l1_path_hit_rate is not None
        else "aggregate_fallback"
        if l1_aggregate_hit_rate is not None
        else ""
    )

    l2_device_read_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_aperture_device_op_read.sum",
        ],
    )
    l2_device_read_hit_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_hit.sum",
        ],
    )
    l2_device_read_miss_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_miss.sum",
        ],
    )
    l2_device_path_hit_rate = percent_from_hit_miss(
        l2_device_read_hit_sectors, l2_device_read_miss_sectors
    )
    l2_read_hit_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_op_read_lookup_hit.sum",
            "lts__t_sectors_srcunit_tex_lookup_hit.sum",
            "lts__t_sectors_lookup_hit.sum",
            "lts__t_tag_requests_hit.sum",
        ],
    )
    l2_read_miss_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_op_read_lookup_miss.sum",
            "lts__t_sectors_srcunit_tex_lookup_miss.sum",
            "lts__t_sectors_lookup_miss.sum",
            "lts__t_tag_requests_miss.sum",
        ],
    )
    l2_fabric_device_read_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read.sum",
        ],
    )
    l2_fabric_device_read_hit_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_hit.sum",
        ],
    )
    l2_fabric_device_read_miss_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_miss.sum",
        ],
    )
    l2_fabric_all_read_sectors = first_metric_sum(
        metrics,
        ["lts__t_sectors_srcunit_ltcfabric_op_read.sum"],
    )
    l2_fabric_all_read_hit_sectors = first_metric_sum(
        metrics,
        ["lts__t_sectors_srcunit_ltcfabric_op_read_lookup_hit.sum"],
    )
    l2_fabric_all_read_miss_sectors = first_metric_sum(
        metrics,
        ["lts__t_sectors_srcunit_ltcfabric_op_read_lookup_miss.sum"],
    )
    # Device-aperture traffic is the exact cudaMalloc path. Fall back to all
    # LTC-fabric reads only when the aperture-specific events are unavailable.
    l2_fabric_read_sectors = first_non_none(
        l2_fabric_device_read_sectors, l2_fabric_all_read_sectors
    )
    l2_fabric_read_hit_sectors = first_non_none(
        l2_fabric_device_read_hit_sectors, l2_fabric_all_read_hit_sectors
    )
    l2_fabric_read_miss_sectors = first_non_none(
        l2_fabric_device_read_miss_sectors, l2_fabric_all_read_miss_sectors
    )
    l2_fabric_hit_rate = percent_from_hit_miss(
        l2_fabric_read_hit_sectors, l2_fabric_read_miss_sectors
    )
    l2_fabric_metric_source = (
        "srcunit_ltcfabric_device_read"
        if l2_fabric_device_read_sectors is not None
        else "srcunit_ltcfabric_read"
        if l2_fabric_all_read_sectors is not None
        else ""
    )
    l2_fabric_metrics_present = float(
        l2_fabric_read_sectors is not None
        and l2_fabric_read_hit_sectors is not None
        and l2_fabric_read_miss_sectors is not None
    )
    l2_tex_path_hit_rate = percent_from_hit_miss(
        l2_read_hit_sectors, l2_read_miss_sectors
    )
    # Device-aperture TEX traffic is the exact path for cudaMalloc input. Fall
    # back to all TEX read traffic only on architectures/tool versions where
    # the aperture-specific events are unavailable.
    l2_path_hit_rate = first_non_none(
        l2_device_path_hit_rate, l2_tex_path_hit_rate
    )
    l2_native_read_hit_rate = metrics.first_names(
        [
            "lts__t_sector_op_read_hit_rate.pct",
            "lts__t_sectors_op_read_hit_rate.pct",
        ]
    )
    l2_aggregate_hit_rate = metrics.first_names(
        [
            "lts__t_sector_hit_rate.pct",
            "lts__t_sectors_hit_rate.pct",
            "lts__t_tag_hit_rate.pct",
        ]
    )
    l2_hit_rate = first_non_none(l2_path_hit_rate, l2_aggregate_hit_rate)
    l2_hit_rate_source = (
        "srcunit_tex_device_read_lookup_hit_miss"
        if l2_device_path_hit_rate is not None
        else "srcunit_tex_read_lookup_hit_miss"
        if l2_tex_path_hit_rate is not None
        else "aggregate_fallback"
        if l2_aggregate_hit_rate is not None
        else ""
    )

    l2_evict_first_read_sectors = first_metric_sum(
        metrics, ["lts__t_sectors_srcunit_tex_op_read_evict_first.sum"]
    )
    l2_evict_normal_read_sectors = first_metric_sum(
        metrics, ["lts__t_sectors_srcunit_tex_op_read_evict_normal.sum"]
    )
    l2_evict_last_read_sectors = first_metric_sum(
        metrics, ["lts__t_sectors_srcunit_tex_op_read_evict_last.sum"]
    )
    l2_policy_read_total = sum_non_none(
        l2_evict_first_read_sectors,
        l2_evict_normal_read_sectors,
        l2_evict_last_read_sectors,
    )
    l2_evict_first_read_pct = (
        100.0 * l2_evict_first_read_sectors / l2_policy_read_total
        if l2_evict_first_read_sectors is not None and l2_policy_read_total
        else None
    )
    l2_evict_normal_read_pct = (
        100.0 * l2_evict_normal_read_sectors / l2_policy_read_total
        if l2_evict_normal_read_sectors is not None and l2_policy_read_total
        else None
    )
    l2_evict_last_read_pct = (
        100.0 * l2_evict_last_read_sectors / l2_policy_read_total
        if l2_evict_last_read_sectors is not None and l2_policy_read_total
        else None
    )

    l1_read_requests = metrics.sum_names(
        [
            "l1tex__t_requests_pipe_lsu_mem_global_op_ld.sum",
            "l1tex__t_requests_pipe_lsu_mem_local_op_ld.sum",
        ]
    )
    l1_write_requests = metrics.sum_names(
        [
            "l1tex__t_requests_pipe_lsu_mem_global_op_st.sum",
            "l1tex__t_requests_pipe_lsu_mem_local_op_st.sum",
        ]
    )
    l1_requests = first_non_none(
        sum_non_none(l1_read_requests, l1_write_requests),
        metrics.sum_names(["l1tex__t_requests_pipe_lsu.sum", "l1tex__t_requests.sum"]),
    )
    l1_access_unit = "requests" if l1_requests is not None else "sectors"

    l1_read_sectors = metrics.sum_names(
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum",
            "l1tex__t_sectors_pipe_lsu_mem_local_op_ld.sum",
            "l1tex__m_xbar2l1tex_read_sectors_mem_lg_op_ld.sum",
        ]
    )
    l1_write_sectors = metrics.sum_names(
        [
            "l1tex__t_sectors_pipe_lsu_mem_global_op_st.sum",
            "l1tex__t_sectors_pipe_lsu_mem_local_op_st.sum",
            "l1tex__m_l1tex2xbar_write_sectors_mem_lg_op_st.sum",
        ]
    )
    l1_sectors = first_non_none(
        sum_non_none(l1_read_sectors, l1_write_sectors),
        metrics.sum_names(["l1tex__t_sectors_pipe_lsu.sum", "l1tex__t_sectors.sum"]),
    )
    l1_accesses = l1_requests if l1_requests is not None else l1_sectors
    l1_read_accesses = l1_read_requests if l1_requests is not None else l1_read_sectors
    l1_write_accesses = l1_write_requests if l1_requests is not None else l1_write_sectors
    l1_bytes = first_non_none(
        metrics.sum_names(
            [
                "l1tex__t_bytes_pipe_lsu_mem_global_op_ld.sum",
                "l1tex__t_bytes_pipe_lsu_mem_global_op_st.sum",
                "l1tex__t_bytes_pipe_lsu_mem_local_op_ld.sum",
                "l1tex__t_bytes_pipe_lsu_mem_local_op_st.sum",
            ]
        ),
        metrics.sum_names(["l1tex__t_bytes_pipe_lsu.sum", "l1tex__t_bytes.sum"]),
        l1_sectors * SECTOR_BYTES if l1_sectors is not None else None,
    )
    l1_request_bytes = first_non_none(
        first_metric_sum(
            metrics,
            ["l1tex__t_bytes_pipe_lsu_mem_global_op_ld.sum"],
        ),
        l1_read_sectors * SECTOR_BYTES if l1_read_sectors is not None else None,
        sum_non_none(l1_hit_bytes, l1_miss_bytes),
    )

    shared_read_accesses = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
                "smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ldsm.sum",
            ]
        ),
        metrics.sum_names(
            [
                "sm__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
                "sm__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ldsm.sum",
            ]
        ),
        metrics.sum_names(
            [
                "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
                "l1tex__t_requests_pipe_lsu_mem_shared_op_ld.sum",
                "l1tex__t_sectors_pipe_lsu_mem_shared_op_ld.sum",
            ]
        ),
    )
    shared_write_accesses = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
            ]
        ),
        metrics.sum_names(
            [
                "sm__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
            ]
        ),
        metrics.sum_names(
            [
                "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
                "l1tex__t_requests_pipe_lsu_mem_shared_op_st.sum",
                "l1tex__t_sectors_pipe_lsu_mem_shared_op_st.sum",
            ]
        ),
    )
    shared_accesses = sum_non_none(shared_read_accesses, shared_write_accesses)
    legacy_shared_read_accesses = metrics.sum_names(
        [
            "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
            "l1tex__t_requests_pipe_lsu_mem_shared_op_ld.sum",
            "l1tex__t_sectors_pipe_lsu_mem_shared_op_ld.sum",
        ]
    )
    legacy_shared_write_accesses = metrics.sum_names(
        [
            "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
            "l1tex__t_requests_pipe_lsu_mem_shared_op_st.sum",
            "l1tex__t_sectors_pipe_lsu_mem_shared_op_st.sum",
        ]
    )
    shared_sectors = metrics.sum_names(
        [
            "l1tex__t_sectors_pipe_lsu_mem_shared_op_ld.sum",
            "l1tex__t_sectors_pipe_lsu_mem_shared_op_st.sum",
        ]
    )
    shared_read_bytes_sass = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_data_bytes_mem_shared_op_ld.sum",
                "smsp__sass_data_bytes_mem_shared_op_ldsm.sum",
            ]
        ),
        metrics.sum_names(
            [
                "sm__sass_data_bytes_mem_shared_op_ld.sum",
                "sm__sass_data_bytes_mem_shared_op_ldsm.sum",
            ]
        ),
    )
    shared_write_bytes_sass = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_data_bytes_mem_shared_op_st.sum",
            ]
        ),
        metrics.sum_names(
            [
                "sm__sass_data_bytes_mem_shared_op_st.sum",
            ]
        ),
    )
    shared_bytes_sass = first_non_none(
        sum_non_none(shared_read_bytes_sass, shared_write_bytes_sass),
        metrics.sum_names(
            [
                "smsp__sass_data_bytes_mem_shared.sum",
                "sm__sass_data_bytes_mem_shared.sum",
            ]
        ),
    )
    shared_read_bytes_l1tex = first_non_none(
        metrics.sum_names(["l1tex__t_bytes_pipe_lsu_mem_shared_op_ld.sum"]),
    )
    shared_write_bytes_l1tex = first_non_none(
        metrics.sum_names(["l1tex__t_bytes_pipe_lsu_mem_shared_op_st.sum"]),
    )
    shared_bytes_l1tex = first_non_none(
        metrics.sum_names(
            [
                "l1tex__t_bytes_pipe_lsu_mem_shared_op_ld.sum",
                "l1tex__t_bytes_pipe_lsu_mem_shared_op_st.sum",
            ]
        ),
        shared_sectors * SECTOR_BYTES if shared_sectors is not None else None,
    )
    shared_bytes = first_non_none(shared_bytes_sass, shared_bytes_l1tex)
    shared_read_bytes = first_non_none(
        shared_read_bytes_sass, shared_read_bytes_l1tex
    )
    shared_write_bytes = first_non_none(
        shared_write_bytes_sass, shared_write_bytes_l1tex
    )
    shared_bytes_source = (
        "sass"
        if shared_bytes_sass is not None
        else "l1tex_or_sector"
        if shared_bytes_l1tex is not None
        else ""
    )
    shared_bank_conflicts = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_ldsm.sum",
                "smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_st.sum",
            ]
        ),
        metrics.sum_names(
            [
                "sm__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_ldsm.sum",
                "sm__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_st.sum",
            ]
        ),
        metrics.sum_names(
            [
                "l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_ld.sum",
                "l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_st.sum",
            ]
        ),
    )
    shared_inst = first_non_none(
        metrics.sum_names(
            [
                "smsp__sass_inst_executed_op_shared_ld.sum",
                "smsp__sass_inst_executed_op_shared_st.sum",
            ]
        ),
        metrics.sum_names(["smsp__sass_inst_executed_op_shared.sum"]),
        metrics.sum_names(
            [
                "sm__sass_inst_executed_op_shared_ld.sum",
                "sm__sass_inst_executed_op_shared_st.sum",
            ]
        ),
        metrics.sum_names(["sm__sass_inst_executed_op_shared.sum"]),
    )

    l2_read_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_op_read.sum",
            "lts__t_sectors_op_read.sum",
        ],
    )
    l2_write_sectors = first_metric_sum(
        metrics,
        [
            "lts__t_sectors_srcunit_tex_op_write.sum",
            "lts__t_sectors_op_write.sum",
        ],
    )
    l2_sectors = first_non_none(
        sum_non_none(l2_read_sectors, l2_write_sectors),
        metrics.sum_names(["lts__t_sectors_srcunit_tex.sum", "lts__t_sectors.sum"]),
    )
    l2_bytes = first_non_none(
        metrics.sum_names(["lts__t_bytes.sum"]),
        metrics.sum_names(["lts__t_bytes_srcunit_tex.sum"]),
        l2_sectors * SECTOR_BYTES if l2_sectors is not None else None,
    )
    l2_read_bytes = (
        l2_read_sectors * SECTOR_BYTES if l2_read_sectors is not None else None
    )
    l2_tex_read_sector_conservation_ratio = None
    if l2_read_sectors is not None and l2_read_sectors > 0.0:
        hit_miss_sectors = sum_non_none(
            l2_read_hit_sectors, l2_read_miss_sectors
        )
        if hit_miss_sectors is not None:
            l2_tex_read_sector_conservation_ratio = hit_miss_sectors / l2_read_sectors
    l2_device_read_sector_conservation_ratio = None
    if l2_device_read_sectors is not None and l2_device_read_sectors > 0.0:
        device_hit_miss_sectors = sum_non_none(
            l2_device_read_hit_sectors, l2_device_read_miss_sectors
        )
        if device_hit_miss_sectors is not None:
            l2_device_read_sector_conservation_ratio = (
                device_hit_miss_sectors / l2_device_read_sectors
            )
    if l2_device_path_hit_rate is not None:
        l2_read_sector_conservation_ratio = (
            l2_device_read_sector_conservation_ratio
        )
        l2_path_read_sectors = l2_device_read_sectors
        l2_path_read_hit_sectors = l2_device_read_hit_sectors
        l2_path_read_miss_sectors = l2_device_read_miss_sectors
    else:
        l2_read_sector_conservation_ratio = l2_tex_read_sector_conservation_ratio
        l2_path_read_sectors = l2_read_sectors
        l2_path_read_hit_sectors = l2_read_hit_sectors
        l2_path_read_miss_sectors = l2_read_miss_sectors
    l2_path_counter_coherent = (
        float(0.98 <= l2_read_sector_conservation_ratio <= 1.02)
        if l2_read_sector_conservation_ratio is not None
        else None
    )
    l2_read_miss_bytes = (
        l2_path_read_miss_sectors * SECTOR_BYTES
        if l2_path_read_miss_sectors is not None
        else None
    )

    l2_fabric_read_sector_conservation_ratio = None
    if l2_fabric_metrics_present == 1.0:
        if l2_fabric_read_sectors and l2_fabric_read_sectors > 0.0:
            l2_fabric_read_sector_conservation_ratio = (
                (l2_fabric_read_hit_sectors + l2_fabric_read_miss_sectors)
                / l2_fabric_read_sectors
            )
        elif (
            l2_fabric_read_sectors == 0.0
            and l2_fabric_read_hit_sectors == 0.0
            and l2_fabric_read_miss_sectors == 0.0
        ):
            l2_fabric_read_sector_conservation_ratio = 1.0
    l2_fabric_counter_coherent = (
        float(0.98 <= l2_fabric_read_sector_conservation_ratio <= 1.02)
        if l2_fabric_read_sector_conservation_ratio is not None
        else None
    )

    l2_fabric_read_to_source_miss_ratio = None
    l2_fabric_hit_to_source_miss_ratio = None
    l2_fabric_read_fraction = None
    l2_logical_read_hit_sectors = None
    l2_logical_read_miss_sectors = None
    l2_logical_read_hit_rate = None
    l2_fabric_model_native_hit_rate = None
    l2_native_vs_fabric_model_hit_delta_pct = None
    l2_fabric_model_coherent = None
    if (
        l2_path_read_sectors is not None
        and l2_path_read_sectors > 0.0
        and l2_path_read_hit_sectors is not None
        and l2_path_read_miss_sectors is not None
        and l2_fabric_metrics_present == 1.0
    ):
        if l2_path_read_miss_sectors > 0.0:
            l2_fabric_read_to_source_miss_ratio = (
                l2_fabric_read_sectors / l2_path_read_miss_sectors
            )
            l2_fabric_hit_to_source_miss_ratio = (
                l2_fabric_read_hit_sectors / l2_path_read_miss_sectors
            )
        elif l2_fabric_read_sectors == 0.0:
            l2_fabric_read_to_source_miss_ratio = 0.0
            l2_fabric_hit_to_source_miss_ratio = 0.0
        total_l2_lookup_sectors = (
            l2_path_read_sectors + l2_fabric_read_sectors
        )
        l2_fabric_read_fraction = (
            l2_fabric_read_sectors / total_l2_lookup_sectors
            if total_l2_lookup_sectors > 0.0
            else None
        )
        l2_logical_read_hit_sectors = (
            l2_path_read_hit_sectors + l2_fabric_read_hit_sectors
        )
        l2_logical_read_miss_sectors = (
            l2_path_read_sectors - l2_logical_read_hit_sectors
        )
        l2_logical_read_hit_rate = (
            100.0 * l2_logical_read_hit_sectors / l2_path_read_sectors
        )
        native_model_denominator = total_l2_lookup_sectors
        if native_model_denominator > 0.0:
            l2_fabric_model_native_hit_rate = (
                100.0
                * l2_logical_read_hit_sectors
                / native_model_denominator
            )
        if (
            l2_native_read_hit_rate is not None
            and l2_fabric_model_native_hit_rate is not None
        ):
            l2_native_vs_fabric_model_hit_delta_pct = abs(
                l2_native_read_hit_rate - l2_fabric_model_native_hit_rate
            )
        routing_is_coherent = (
            l2_fabric_read_to_source_miss_ratio is not None
            and 0.0 <= l2_fabric_read_to_source_miss_ratio <= 1.05
            and l2_fabric_hit_to_source_miss_ratio is not None
            and 0.0 <= l2_fabric_hit_to_source_miss_ratio <= 1.05
            and -0.005
            <= l2_logical_read_miss_sectors / l2_path_read_sectors
            <= 1.0
        )
        l2_fabric_model_coherent = float(
            l2_path_counter_coherent == 1.0
            and l2_fabric_counter_coherent == 1.0
            and routing_is_coherent
        )
    l2_logical_read_miss_bytes = (
        l2_logical_read_miss_sectors * SECTOR_BYTES
        if l2_logical_read_miss_sectors is not None
        else None
    )
    l2_native_vs_derived_hit_delta_pct = None
    if l2_native_read_hit_rate is not None and l2_path_hit_rate is not None:
        l2_native_vs_derived_hit_delta_pct = abs(
            l2_native_read_hit_rate - l2_path_hit_rate
        )

    dram_read_sectors = metrics.sum_names(["dram__sectors_read.sum"])
    dram_write_sectors = metrics.sum_names(["dram__sectors_write.sum"])
    dram_sectors = first_non_none(
        sum_non_none(dram_read_sectors, dram_write_sectors),
        metrics.sum_names(["dram__sectors.sum"]),
    )
    direct_dram_read_bytes = metrics.sum_names(["dram__bytes_read.sum"])
    direct_dram_write_bytes = metrics.sum_names(["dram__bytes_write.sum"])
    dram_bytes = first_non_none(
        metrics.sum_names(["dram__bytes.sum"]),
        sum_non_none(
            direct_dram_read_bytes,
            direct_dram_write_bytes,
        ),
        dram_sectors * SECTOR_BYTES if dram_sectors is not None else None,
    )
    dram_read_bytes = first_non_none(
        direct_dram_read_bytes,
        dram_read_sectors * SECTOR_BYTES if dram_read_sectors is not None else None,
    )
    dram_read_bytes_source = (
        "dram__bytes_read.sum"
        if direct_dram_read_bytes is not None
        else (
            "dram__sectors_read.sum*32"
            if dram_read_sectors is not None
            else ""
        )
    )
    dram_write_bytes = first_non_none(
        direct_dram_write_bytes,
        dram_write_sectors * SECTOR_BYTES if dram_write_sectors is not None else None,
        (
            max(0.0, dram_bytes - dram_read_bytes)
            if dram_bytes is not None and dram_read_bytes is not None
            else None
        ),
    )
    dram_write_bytes_source = (
        "dram__bytes_write.sum"
        if direct_dram_write_bytes is not None
        else (
            "dram__sectors_write.sum*32"
            if dram_write_sectors is not None
            else (
                "dram__bytes.sum-dram_read_bytes"
                if dram_bytes is not None and dram_read_bytes is not None
                else ""
            )
        )
    )
    dram_write_to_read_ratio = None
    if dram_read_bytes is not None and dram_read_bytes > 0.0:
        if dram_write_bytes is not None:
            dram_write_to_read_ratio = dram_write_bytes / dram_read_bytes
    gpu_duration_s = metrics.sum_names(["gpu__time_duration.sum"])
    dram_read_bandwidth_gbps = None
    if (
        dram_read_bytes is not None
        and gpu_duration_s is not None
        and gpu_duration_s > 0.0
    ):
        dram_read_bandwidth_gbps = dram_read_bytes / gpu_duration_s / 1.0e9
    dram_read_to_l2_miss_bytes_ratio = None
    if l2_read_miss_bytes is not None and l2_read_miss_bytes > 0.0:
        if dram_read_bytes is not None:
            dram_read_to_l2_miss_bytes_ratio = dram_read_bytes / l2_read_miss_bytes
    dram_read_to_l2_read_bytes_ratio = None
    if l2_read_bytes is not None and l2_read_bytes > 0.0:
        if dram_read_bytes is not None:
            dram_read_to_l2_read_bytes_ratio = dram_read_bytes / l2_read_bytes
    dram_read_to_l2_logical_miss_bytes_ratio = None
    if (
        l2_logical_read_miss_bytes is not None
        and l2_logical_read_miss_bytes > 0.0
        and dram_read_bytes is not None
    ):
        dram_read_to_l2_logical_miss_bytes_ratio = (
            dram_read_bytes / l2_logical_read_miss_bytes
        )

    expected_global_read_bytes = None
    expected_l2_read_bytes = None
    l2_read_to_expected_ratio = None
    dram_read_to_expected_ratio = None
    if manifest.get("mode", "") in {"l2_cg_load_only", "dram_cg_load_only"}:
        geometry = [
            parse_float(manifest.get(name, ""))
            for name in ("active_SM", "blocks_per_SM", "ITER", "load_repeat")
        ]
        if all(value is not None and value > 0.0 for value in geometry):
            expected_global_read_bytes = (
                math.prod(value for value in geometry if value is not None) * 1024.0
            )
            if manifest.get("mode", "") == "l2_cg_load_only":
                expected_l2_read_bytes = expected_global_read_bytes
            if l2_read_bytes is not None and expected_global_read_bytes > 0.0:
                l2_read_to_expected_ratio = l2_read_bytes / expected_global_read_bytes
            if dram_read_bytes is not None and expected_global_read_bytes > 0.0:
                dram_read_to_expected_ratio = (
                    dram_read_bytes / expected_global_read_bytes
                )

    tensor_hmma_inst = metrics.sum_names(["sm__inst_executed_pipe_tensor_op_hmma.sum"])
    tensor_fp16_f32_ops = metrics.sum_names(
        ["sm__ops_path_tensor_src_fp16_dst_fp32.sum"]
    )
    fp16_pipe_inst = metrics.sum_names(
        ["sm__inst_executed_pipe_fma_type_fp16.sum"]
    )
    sass_ffma_thread_inst = metrics.sum_names(
        ["smsp__sass_thread_inst_executed_op_ffma_pred_on.sum"]
    )
    sass_fp16_thread_inst = metrics.sum_names(
        ["smsp__sass_thread_inst_executed_op_fp16_pred_on.sum"]
    )
    sass_fp32_thread_inst = metrics.sum_names(
        ["smsp__sass_thread_inst_executed_op_fp32_pred_on.sum"]
    )
    sass_integer_thread_inst = metrics.sum_names(
        ["smsp__sass_thread_inst_executed_op_integer_pred_on.sum"]
    )
    sass_inst_executed = metrics.sum_names(["smsp__sass_inst_executed.sum"])
    tensor_pipe_active_pct = metrics.first_names(
        ["sm__pipe_tensor_cycles_active.avg.pct_of_peak_sustained_active"]
    )
    alu_pipe_active_pct = metrics.first_names(
        ["sm__pipe_alu_cycles_active.avg.pct_of_peak_sustained_active"]
    )
    fma_pipe_active_pct = metrics.first_names(
        ["sm__pipe_fma_cycles_active.avg.pct_of_peak_sustained_active"]
    )
    issue_active_pct = metrics.first_names(
        ["sm__issue_active.avg.pct_of_peak_sustained_active"]
    )
    expected_logical_mma = None
    expected_logical_flop = None
    expected_register_ops = None
    sass_inst_per_expected_reg_op = None
    tensor_hmma_per_logical_mma = None
    tensor_ops_to_expected_flop = None
    if manifest.get("mode", "") in {
        "reg_mma",
        "reg_operand_only",
        "reg_resident_stall_no_mma",
        "reg_issue_dependency_no_mma",
        "reg_scheduler_matched_no_mma",
        "reg_fragment_only",
        "reg_pressure",
    }:
        geometry = [
            parse_float(manifest.get(name, ""))
            for name in ("active_SM", "blocks_per_SM", "ITER", "reuse_factor")
        ]
        if all(value is not None and value > 0.0 for value in geometry):
            expected_register_ops = math.prod(
                value for value in geometry if value is not None
            )
            if sass_inst_executed is not None and expected_register_ops > 0.0:
                sass_inst_per_expected_reg_op = (
                    sass_inst_executed / expected_register_ops
                )
    if manifest.get("mode", "") == "reg_mma":
        geometry = [
            parse_float(manifest.get(name, ""))
            for name in ("active_SM", "blocks_per_SM", "ITER", "reuse_factor")
        ]
        if all(value is not None and value > 0.0 for value in geometry):
            expected_logical_mma = math.prod(value for value in geometry if value is not None)
            expected_logical_flop = expected_logical_mma * 8192.0
            if tensor_hmma_inst is not None and expected_logical_mma > 0.0:
                tensor_hmma_per_logical_mma = tensor_hmma_inst / expected_logical_mma
            if tensor_fp16_f32_ops is not None and expected_logical_flop > 0.0:
                tensor_ops_to_expected_flop = (
                    tensor_fp16_f32_ops / expected_logical_flop
                )
    local_read_bytes = metrics.sum_names(
        ["l1tex__t_bytes_pipe_lsu_mem_local_op_ld.sum"]
    )
    local_write_bytes = metrics.sum_names(
        ["l1tex__t_bytes_pipe_lsu_mem_local_op_st.sum"]
    )
    spill_local_read_inst = metrics.sum_names(
        ["sass__inst_executed_register_spilling_mem_local_op_read.sum"]
    )
    spill_local_write_inst = metrics.sum_names(
        ["sass__inst_executed_register_spilling_mem_local_op_write.sum"]
    )
    spill_evidence_source = "sass_register_spill_instructions"
    if spill_local_read_inst is None and local_read_bytes == 0.0:
        spill_local_read_inst = 0.0
        spill_evidence_source = "local_memory_bytes_zero_inference"
    if spill_local_write_inst is None and local_write_bytes == 0.0:
        spill_local_write_inst = 0.0
        spill_evidence_source = "local_memory_bytes_zero_inference"
    if (
        spill_local_read_inst is None
        or spill_local_write_inst is None
    ) and (local_read_bytes is not None or local_write_bytes is not None):
        spill_evidence_source = "local_memory_bytes_nonzero_or_partial"
    spill_zero_verified = None
    if (local_read_bytes or 0.0) > 0.0 or (local_write_bytes or 0.0) > 0.0:
        spill_zero_verified = 0.0
    elif spill_local_read_inst is not None and spill_local_write_inst is not None:
        spill_zero_verified = float(
            spill_local_read_inst == 0.0 and spill_local_write_inst == 0.0
        )
    elif local_read_bytes is not None and local_write_bytes is not None:
        spill_zero_verified = float(
            local_read_bytes == 0.0 and local_write_bytes == 0.0
        )
    stall_long_scoreboard_pct = metrics.first_names(
        ["smsp__average_warps_issue_stalled_long_scoreboard_per_issue_active.pct"]
    )
    stall_short_scoreboard_pct = metrics.first_names(
        ["smsp__average_warps_issue_stalled_short_scoreboard_per_issue_active.pct"]
    )
    stall_wait_pct = metrics.first_names(
        ["smsp__average_warps_issue_stalled_wait_per_issue_active.pct"]
    )
    stall_not_selected_pct = metrics.first_names(
        ["smsp__average_warps_issue_stalled_not_selected_per_issue_active.pct"]
    )
    stall_sleeping_pct = metrics.first_names(
        ["smsp__warp_issue_stalled_sleeping_per_warp_active.pct"]
    )
    sleeping_latency_cycles_per_warp = metrics.first_names(
        ["smsp__average_warp_latency_issue_stalled_sleeping.ratio"]
    )
    achieved_occupancy_pct = metrics.first_names(
        ["sm__warps_active.avg.pct_of_peak_sustained_active"]
    )
    launch_warp_capacity_pct = metrics.first_names(
        ["sm__maximum_warps_per_active_cycle_pct"]
    )
    launch_warps_per_scheduler = metrics.first_names(
        ["smsp__maximum_warps_avg_per_active_cycle"]
    )
    registers_per_thread = metrics.first_names(
        [
            "launch__registers_per_thread",
            "tpc__average_registers_per_thread",
        ]
    )
    shared_mem_per_block_static = metrics.first_names(
        ["launch__shared_mem_per_block_static"]
    )
    shared_mem_per_block_dynamic = metrics.first_names(
        ["launch__shared_mem_per_block_dynamic"]
    )
    launch_persisting_l2_cache_size_bytes = metrics.first_names(
        ["launch__persisting_l2_cache_size"]
    )

    missing = []
    mode = manifest.get("mode", "")
    # A zero-traffic address/register/shared control has no meaningful cache
    # hit-rate denominator. Do not turn that intentional zero into a missing-
    # metric failure; the acceptance layer validates its zero traffic instead.
    if mode in {"global_l1_load_only", "l2_cg_load_only", "dram_cg_load_only"}:
        if l1_hit_rate is None:
            missing.append("l1_hit_rate_pct")
    if mode in {"l2_cg_load_only", "dram_cg_load_only"}:
        if l2_hit_rate is None:
            missing.append("l2_hit_rate_pct")
    if l1_accesses is None:
        missing.append("l1_accesses")
    if manifest.get("mode", "").startswith("shared_") and shared_accesses is None:
        missing.append("shared_accesses")
    if manifest.get("mode", "").startswith("shared_") and shared_bytes is None:
        missing.append("shared_bytes")
    if l2_sectors is None:
        missing.append("l2_accesses")
    if dram_sectors is None:
        missing.append("dram_accesses")
    if mode in {"global_l1_load_only", "l2_cg_load_only", "dram_cg_load_only"}:
        if l1_request_bytes is None:
            missing.append("l1_request_bytes")
        if l1_path_hit_rate is None:
            missing.append("l1_path_hit_rate_pct")
    if mode == "l2_cg_load_only":
        if l1_hit_bytes is None:
            missing.append("l1_hit_bytes")
        if l2_path_hit_rate is None:
            missing.append("l2_path_hit_rate_pct")
        if l2_read_bytes is None:
            missing.append("l2_read_bytes")

    optional_missing = []
    if tensor_hmma_inst is None:
        optional_missing.append("tensor_hmma_inst")
    if tensor_fp16_f32_ops is None and mode == "reg_mma":
        optional_missing.append("tensor_fp16_f32_ops")
    if spill_local_read_inst is None:
        optional_missing.append("spill_local_read_inst")
    if spill_local_write_inst is None:
        optional_missing.append("spill_local_write_inst")
    if stall_long_scoreboard_pct is None:
        optional_missing.append("stall_long_scoreboard_pct")
    if stall_short_scoreboard_pct is None:
        optional_missing.append("stall_short_scoreboard_pct")
    if stall_wait_pct is None:
        optional_missing.append("stall_wait_pct")
    if stall_not_selected_pct is None:
        optional_missing.append("stall_not_selected_pct")
    if stall_sleeping_pct is None:
        optional_missing.append("stall_sleeping_pct")
    if issue_active_pct is None:
        optional_missing.append("issue_active_pct")
    if achieved_occupancy_pct is None:
        optional_missing.append("achieved_occupancy_pct")
    if tensor_pipe_active_pct is None and mode == "reg_mma":
        optional_missing.append("tensor_pipe_active_pct")
    if registers_per_thread is None:
        optional_missing.append("registers_per_thread")
    if l2_native_read_hit_rate is None:
        optional_missing.append("l2_native_read_hit_rate_pct")
    if launch_persisting_l2_cache_size_bytes is None:
        optional_missing.append("launch_persisting_l2_cache_size_bytes")

    validation_notes = []
    for name, value, upper_bound in [
        ("l1_hit_rate_pct", l1_hit_rate, 100.01),
        ("l2_hit_rate_pct", l2_hit_rate, 100.01),
        ("l2_native_read_hit_rate_pct", l2_native_read_hit_rate, 100.01),
        # Source and fabric events can be aggregated with a small counter skew.
        # Keep this bound aligned with the downstream GA100 acceptance gate.
        ("l2_logical_read_hit_rate_pct", l2_logical_read_hit_rate, 100.5),
    ]:
        if value is not None and (value < -0.01 or value > upper_bound):
            validation_notes.append(f"{name}_out_of_range")
    if (
        l2_native_vs_derived_hit_delta_pct is not None
        and l2_native_vs_derived_hit_delta_pct > 2.0
    ):
        if (
            l2_native_vs_fabric_model_hit_delta_pct is not None
            and l2_native_vs_fabric_model_hit_delta_pct <= 2.0
        ):
            validation_notes.append("l2_native_direct_delta_explained_by_fabric")
        else:
            validation_notes.append("l2_native_derived_hit_rate_disagree")
    if (
        l2_read_sector_conservation_ratio is not None
        and not 0.98 <= l2_read_sector_conservation_ratio <= 1.02
    ):
        validation_notes.append("l2_read_sector_conservation_failed")
    if l2_fabric_metrics_present == 1.0 and l2_fabric_model_coherent != 1.0:
        validation_notes.append("l2_fabric_model_incoherent")

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
        "reuse_factor": manifest.get("reuse_factor", ""),
        "issue_match_steps": manifest.get("issue_match_steps", ""),
        "issue_match_extra_period": manifest.get(
            "issue_match_extra_period", ""
        ),
        "latency_match_ns": manifest.get("latency_match_ns", ""),
        "latency_match_period": manifest.get("latency_match_period", ""),
        "scheduler_match_steps": manifest.get("scheduler_match_steps", ""),
        "load_repeat": manifest.get("load_repeat", ""),
        "store_repeat": manifest.get("store_repeat", ""),
        "ncu_replay_mode": manifest.get("ncu_replay_mode", ""),
        "ncu_cache_control": manifest.get("ncu_cache_control", ""),
        "ncu_metric_profile": manifest.get("ncu_metric_profile", "full"),
        "global_warmup_passes": manifest.get("global_warmup_passes", ""),
        "l2_residency_policy": manifest.get("l2_residency_policy", ""),
        "l2_address_layout": manifest.get("l2_address_layout", "contiguous"),
        "status": status,
        "shared_accesses": fmt(shared_accesses),
        "shared_bytes": fmt(shared_bytes),
        "shared_read_bytes": fmt(shared_read_bytes),
        "shared_write_bytes": fmt(shared_write_bytes),
        "shared_bytes_source": shared_bytes_source,
        "shared_bank_conflicts": fmt(shared_bank_conflicts),
        "shared_inst": fmt(shared_inst),
        "legacy_shared_read_accesses": fmt(legacy_shared_read_accesses),
        "legacy_shared_write_accesses": fmt(legacy_shared_write_accesses),
        "l1_hit_rate_pct": fmt(l1_hit_rate),
        "l1_path_hit_rate_pct": fmt(l1_path_hit_rate),
        "l1_aggregate_hit_rate_pct": fmt(l1_aggregate_hit_rate),
        "l1_hit_rate_source": l1_hit_rate_source,
        "l2_hit_rate_pct": fmt(l2_hit_rate),
        "l2_path_hit_rate_pct": fmt(l2_path_hit_rate),
        "l2_tex_path_hit_rate_pct": fmt(l2_tex_path_hit_rate),
        "l2_device_path_hit_rate_pct": fmt(l2_device_path_hit_rate),
        "l2_native_read_hit_rate_pct": fmt(l2_native_read_hit_rate),
        "l2_native_vs_derived_hit_delta_pct": fmt(
            l2_native_vs_derived_hit_delta_pct
        ),
        "l2_logical_read_hit_rate_pct": fmt(l2_logical_read_hit_rate),
        "l2_fabric_hit_rate_pct": fmt(l2_fabric_hit_rate),
        "l2_fabric_model_native_hit_rate_pct": fmt(
            l2_fabric_model_native_hit_rate
        ),
        "l2_native_vs_fabric_model_hit_delta_pct": fmt(
            l2_native_vs_fabric_model_hit_delta_pct
        ),
        "l2_aggregate_hit_rate_pct": fmt(l2_aggregate_hit_rate),
        "l2_hit_rate_source": l2_hit_rate_source,
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
        "shared_read_accesses": fmt(shared_read_accesses),
        "shared_write_accesses": fmt(shared_write_accesses),
        "l1_bytes": fmt(l1_bytes),
        "l1_request_bytes": fmt(l1_request_bytes),
        "l1_hit_bytes": fmt(l1_hit_bytes),
        "l1_miss_bytes": fmt(l1_miss_bytes),
        "l2_bytes": fmt(l2_bytes),
        "l2_read_bytes": fmt(l2_read_bytes),
        "expected_global_read_bytes": fmt(expected_global_read_bytes),
        "expected_l2_read_bytes": fmt(expected_l2_read_bytes),
        "l2_read_to_expected_ratio": fmt(l2_read_to_expected_ratio),
        "l2_read_hit_sectors": fmt(l2_read_hit_sectors),
        "l2_read_miss_sectors": fmt(l2_read_miss_sectors),
        "l2_device_read_sectors": fmt(l2_device_read_sectors),
        "l2_device_read_hit_sectors": fmt(l2_device_read_hit_sectors),
        "l2_device_read_miss_sectors": fmt(l2_device_read_miss_sectors),
        "l2_fabric_read_sectors": fmt(l2_fabric_read_sectors),
        "l2_fabric_read_hit_sectors": fmt(l2_fabric_read_hit_sectors),
        "l2_fabric_read_miss_sectors": fmt(l2_fabric_read_miss_sectors),
        "l2_fabric_metric_source": l2_fabric_metric_source,
        "l2_fabric_metrics_present": fmt(l2_fabric_metrics_present),
        "l2_fabric_read_sector_conservation_ratio": fmt(
            l2_fabric_read_sector_conservation_ratio
        ),
        "l2_fabric_counter_coherent": fmt(l2_fabric_counter_coherent),
        "l2_fabric_read_to_source_miss_ratio": fmt(
            l2_fabric_read_to_source_miss_ratio
        ),
        "l2_fabric_hit_to_source_miss_ratio": fmt(
            l2_fabric_hit_to_source_miss_ratio
        ),
        "l2_fabric_read_fraction": fmt(l2_fabric_read_fraction),
        "l2_logical_read_hit_sectors": fmt(l2_logical_read_hit_sectors),
        "l2_logical_read_miss_sectors": fmt(l2_logical_read_miss_sectors),
        "l2_logical_read_miss_bytes": fmt(l2_logical_read_miss_bytes),
        "l2_fabric_model_coherent": fmt(l2_fabric_model_coherent),
        "l2_evict_first_read_sectors": fmt(l2_evict_first_read_sectors),
        "l2_evict_normal_read_sectors": fmt(l2_evict_normal_read_sectors),
        "l2_evict_last_read_sectors": fmt(l2_evict_last_read_sectors),
        "l2_evict_first_read_pct": fmt(l2_evict_first_read_pct),
        "l2_evict_normal_read_pct": fmt(l2_evict_normal_read_pct),
        "l2_evict_last_read_pct": fmt(l2_evict_last_read_pct),
        "l2_read_miss_bytes": fmt(l2_read_miss_bytes),
        "l2_read_sector_conservation_ratio": fmt(
            l2_read_sector_conservation_ratio
        ),
        "l2_tex_read_sector_conservation_ratio": fmt(
            l2_tex_read_sector_conservation_ratio
        ),
        "l2_device_read_sector_conservation_ratio": fmt(
            l2_device_read_sector_conservation_ratio
        ),
        "l2_path_counter_coherent": fmt(l2_path_counter_coherent),
        "dram_bytes": fmt(dram_bytes),
        "dram_read_sectors": fmt(dram_read_sectors),
        "dram_write_sectors": fmt(dram_write_sectors),
        "dram_read_bytes": fmt(dram_read_bytes),
        "dram_read_bytes_source": dram_read_bytes_source,
        "dram_write_bytes": fmt(dram_write_bytes),
        "dram_write_bytes_source": dram_write_bytes_source,
        "dram_read_to_expected_ratio": fmt(dram_read_to_expected_ratio),
        "dram_write_to_read_ratio": fmt(dram_write_to_read_ratio),
        "gpu_duration_s": fmt(gpu_duration_s),
        "dram_read_bandwidth_GBps": fmt(dram_read_bandwidth_gbps),
        "dram_read_to_l2_miss_bytes_ratio": fmt(
            dram_read_to_l2_miss_bytes_ratio
        ),
        "dram_read_to_l2_read_bytes_ratio": fmt(
            dram_read_to_l2_read_bytes_ratio
        ),
        "dram_read_to_l2_logical_miss_bytes_ratio": fmt(
            dram_read_to_l2_logical_miss_bytes_ratio
        ),
        "tensor_hmma_inst": fmt(tensor_hmma_inst),
        "tensor_fp16_f32_ops": fmt(tensor_fp16_f32_ops),
        "fp16_pipe_inst": fmt(fp16_pipe_inst),
        "sass_ffma_thread_inst": fmt(sass_ffma_thread_inst),
        "sass_fp16_thread_inst": fmt(sass_fp16_thread_inst),
        "sass_fp32_thread_inst": fmt(sass_fp32_thread_inst),
        "sass_integer_thread_inst": fmt(sass_integer_thread_inst),
        "sass_inst_executed": fmt(sass_inst_executed),
        "expected_register_ops": fmt(expected_register_ops),
        "sass_inst_per_expected_reg_op": fmt(sass_inst_per_expected_reg_op),
        "expected_logical_mma": fmt(expected_logical_mma),
        "expected_logical_flop": fmt(expected_logical_flop),
        "tensor_hmma_per_logical_mma": fmt(tensor_hmma_per_logical_mma),
        "tensor_ops_to_expected_flop": fmt(tensor_ops_to_expected_flop),
        "tensor_pipe_active_pct": fmt(tensor_pipe_active_pct),
        "alu_pipe_active_pct": fmt(alu_pipe_active_pct),
        "fma_pipe_active_pct": fmt(fma_pipe_active_pct),
        "issue_active_pct": fmt(issue_active_pct),
        "local_read_bytes": fmt(local_read_bytes),
        "local_write_bytes": fmt(local_write_bytes),
        "spill_local_read_inst": fmt(spill_local_read_inst),
        "spill_local_write_inst": fmt(spill_local_write_inst),
        "spill_zero_verified": fmt(spill_zero_verified),
        "spill_evidence_source": spill_evidence_source,
        "stall_long_scoreboard_pct": fmt(stall_long_scoreboard_pct),
        "stall_short_scoreboard_pct": fmt(stall_short_scoreboard_pct),
        "stall_wait_pct": fmt(stall_wait_pct),
        "stall_not_selected_pct": fmt(stall_not_selected_pct),
        "stall_sleeping_pct": fmt(stall_sleeping_pct),
        "sleeping_latency_cycles_per_warp": fmt(
            sleeping_latency_cycles_per_warp
        ),
        "achieved_occupancy_pct": fmt(achieved_occupancy_pct),
        "launch_warp_capacity_pct": fmt(launch_warp_capacity_pct),
        "launch_warps_per_scheduler": fmt(launch_warps_per_scheduler),
        "registers_per_thread": fmt(registers_per_thread),
        "shared_mem_per_block_static": fmt(shared_mem_per_block_static),
        "shared_mem_per_block_dynamic": fmt(shared_mem_per_block_dynamic),
        "launch_persisting_l2_cache_size_bytes": fmt(
            launch_persisting_l2_cache_size_bytes
        ),
        "missing_metrics": ";".join(missing),
        "optional_missing_metrics": ";".join(optional_missing),
        "validation_notes": ";".join(validation_notes),
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
    return grouped


def write_markdown(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# NCU Cache Validation Summary\n\n")
        f.write(
            "| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | "
            "Shared bytes source | Shared bank conflicts | Shared inst | "
            "L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | "
            "DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | "
            "DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | "
            "Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | "
            "Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |\n"
        )
        f.write("|---|---|" + "---:|" * 3 + "---|" + "---:|" * 20 + "---|---|\n")
        for row in rows:
            l1_accesses = row["l1_accesses"]
            if l1_accesses and row["l1_access_unit"]:
                l1_accesses = f"{l1_accesses} {row['l1_access_unit']}"
            notes = row.get("validation_notes", "")
            f.write(
                f"| {row['label']} | {row['mode']} | {row['W_SM_KiB']} | "
                f"{row['blocks_per_SM']} | {row['shared_accesses']} | "
                f"{row['shared_bytes_source']} | "
                f"{row['shared_bank_conflicts']} | "
                f"{row['shared_inst']} | "
                f"{row['l1_hit_rate_pct']} | "
                f"{row['l2_hit_rate_pct']} | {l1_accesses} | "
                f"{row['l2_accesses']} | {row['dram_accesses']} | "
                f"{row['shared_bytes']} | {row['l1_bytes']} | "
                f"{row['l2_bytes']} | {row['dram_bytes']} | "
                f"{row['tensor_hmma_inst']} | "
                f"{row['stall_long_scoreboard_pct']} | "
                f"{row['stall_short_scoreboard_pct']} | "
                f"{row['stall_wait_pct']} | "
                f"{row['stall_not_selected_pct']} | "
                f"{row['achieved_occupancy_pct']} | "
                f"{row['registers_per_thread']} | "
                f"{row['shared_mem_per_block_static']} | "
                f"{row['shared_mem_per_block_dynamic']} | "
                f"{row['status']} | {notes} |\n"
            )
        f.write("\n")
        f.write("## L1/L2 Path-Specific Evidence\n\n")
        f.write(
            "`L1 request bytes` are bytes presented to L1TEX; they are not L1 "
            "cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit "
            "bytes/hit rate should remain near zero. L2 acceptance uses the "
            "device-aperture srcunit-TEX read hit/miss sectors when available, "
            "then falls back to all srcunit-TEX reads. The native op-read ratio "
            "aggregates a broader L2 read population and is a cross-check, not a "
            "replacement for the path-specific ratio. On GA100, a first-partition "
            "TEX miss can be recovered by an LTC-fabric hit in the other partition; "
            "the logical hit and native fabric-model columns preserve that distinction.\n\n"
        )
        f.write(
            "| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | "
            "L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | "
            "L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | "
            "L2 hit source | L2 read hit sectors | L2 read miss sectors | "
            "L2 read sectors conservation | L2 miss bytes | DRAM read bytes | "
            "DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | "
            "observed/expected |\n"
        )
        f.write(
            "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|"
            "---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        )
        for row in rows:
            f.write(
                f"| {row['label']} | {row['mode']} | "
                f"{row['l1_path_hit_rate_pct']} | {row['l1_aggregate_hit_rate_pct']} | "
                f"{row['l1_hit_rate_source']} | {row['l1_request_bytes']} | "
                f"{row['l1_hit_bytes']} | {row['l1_miss_bytes']} | "
                f"{row['l2_path_hit_rate_pct']} | "
                f"{row['l2_native_read_hit_rate_pct']} | "
                f"{row['l2_native_vs_derived_hit_delta_pct']} | "
                f"{row['l2_aggregate_hit_rate_pct']} | {row['l2_hit_rate_source']} | "
                f"{row['l2_read_hit_sectors']} | {row['l2_read_miss_sectors']} | "
                f"{row['l2_read_sector_conservation_ratio']} | "
                f"{row['l2_read_miss_bytes']} | {row['dram_read_bytes']} | "
                f"{row['dram_read_to_l2_miss_bytes_ratio']} | "
                f"{row['l2_read_bytes']} | {row['expected_l2_read_bytes']} | "
                f"{row['l2_read_to_expected_ratio']} |\n"
            )
        f.write("\n")
        f.write("## External-Memory Read Evidence\n\n")
        f.write(
            "These counters validate traffic, not physical HBM/GDDR energy. "
            "Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes "
            "are never the read-path denominator.\n\n"
        )
        f.write(
            "| label | mode | expected global read bytes | L2/source read bytes | "
            "source/expected | DRAM read bytes | read source | read/expected | "
            "DRAM write bytes | write source | write/read | DRAM read GB/s |\n"
        )
        f.write(
            "|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|\n"
        )
        for row in rows:
            f.write(
                f"| {row['label']} | {row['mode']} | "
                f"{row['expected_global_read_bytes']} | {row['l2_read_bytes']} | "
                f"{row['l2_read_to_expected_ratio']} | {row['dram_read_bytes']} | "
                f"{row['dram_read_bytes_source']} | "
                f"{row['dram_read_to_expected_ratio']} | {row['dram_write_bytes']} | "
                f"{row['dram_write_bytes_source']} | "
                f"{row['dram_write_to_read_ratio']} | "
                f"{row['dram_read_bandwidth_GBps']} |\n"
            )
        f.write("\n")
        f.write("## L2 Scope And Eviction Diagnostics\n\n")
        f.write(
            "For GA100, `device-path hit` is the first partition lookup, while "
            "`logical hit` adds a matching LTC-fabric hit from the other partition. "
            "A direct/native disagreement is acceptable only when the explicit "
            "fabric counters reproduce the native ratio and DRAM read leakage remains "
            "low. This is a transaction model, not permission to relabel arbitrary "
            "L2 misses as hits.\n\n"
        )
        f.write(
            "| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | "
            "logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | "
            "device read/hit/miss sectors | fabric read/hit/miss sectors | "
            "fabric/source-miss | fabric fraction | source/fabric/model coherent | "
            "DRAM-read/L2-read | eviction F/N/L (%) |\n"
        )
        f.write("|---|" + "---:|" * 14 + "\n")
        for row in rows:
            f.write(
                f"| {row['label']} | {row['l2_device_path_hit_rate_pct']} | "
                f"{row['l2_tex_path_hit_rate_pct']} | "
                f"{row['l2_native_read_hit_rate_pct']} | "
                f"{row['l2_logical_read_hit_rate_pct']} | "
                f"{row['l2_fabric_hit_rate_pct']} | "
                f"{row['l2_fabric_model_native_hit_rate_pct']} | "
                f"{row['l2_native_vs_fabric_model_hit_delta_pct']} | "
                f"{row['l2_device_read_sectors']}/"
                f"{row['l2_device_read_hit_sectors']}/"
                f"{row['l2_device_read_miss_sectors']} | "
                f"{row['l2_fabric_read_sectors']}/"
                f"{row['l2_fabric_read_hit_sectors']}/"
                f"{row['l2_fabric_read_miss_sectors']} | "
                f"{row['l2_fabric_read_to_source_miss_ratio']} | "
                f"{row['l2_fabric_read_fraction']} | "
                f"{row['l2_path_counter_coherent']}/"
                f"{row['l2_fabric_counter_coherent']}/"
                f"{row['l2_fabric_model_coherent']} | "
                f"{row['dram_read_to_l2_read_bytes_ratio']} | "
                f"{row['l2_evict_first_read_pct']}/"
                f"{row['l2_evict_normal_read_pct']}/"
                f"{row['l2_evict_last_read_pct']} |\n"
            )
        f.write("\n")
        f.write("## Shared Read/Write Diagnostics\n\n")
        f.write("| label | mode | shared read bytes | shared write bytes |\n")
        f.write("|---|---|---:|---:|\n")
        for row in rows:
            f.write(
                f"| {row['label']} | {row['mode']} | "
                f"{row['shared_read_bytes']} | {row['shared_write_bytes']} |\n"
            )
        f.write("\n")
        f.write("## NCU Replay And Residency Policy\n\n")
        f.write(
            "Application replay with cache-control none reruns the program warm-up "
            "before each metric pass. Persisting L2 rows additionally require an "
            "explicit CUDA access-policy window.\n\n"
        )
        f.write(
            "| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | "
            "persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | "
            "FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | "
            "Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |\n"
        )
        f.write("|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            f.write(
                f"| {row['label']} | {row['mode']} | {row['ncu_replay_mode']} | "
                f"{row['ncu_cache_control']} | {row['ncu_metric_profile']} | "
                f"{row['global_warmup_passes']} | "
                f"{row['l2_residency_policy']} | "
                f"{row['l2_address_layout']} | "
                f"{row['launch_persisting_l2_cache_size_bytes']} | "
                f"{row['sass_inst_executed']} | "
                f"{row['expected_register_ops']} | "
                f"{row['sass_inst_per_expected_reg_op']} | "
                f"{row['tensor_hmma_inst']} | "
                f"{row['expected_logical_mma']} | "
                f"{row['tensor_hmma_per_logical_mma']} | "
                f"{row['tensor_fp16_f32_ops']} | "
                f"{row['expected_logical_flop']} | "
                f"{row['tensor_ops_to_expected_flop']} | "
                f"{row['tensor_pipe_active_pct']} | "
                f"{row['achieved_occupancy_pct']} | "
                f"{row['launch_warp_capacity_pct']} | "
                f"{row['registers_per_thread']} |\n"
            )
        f.write("\n")
        f.write("## Spill And Local-Memory Evidence\n\n")
        f.write(
            "Dedicated spill-instruction metrics are not available on every NCU/chip "
            "combination. `spill_zero_verified=1` means either the dedicated counters "
            "are zero or, for kernels with no intentional local-memory path, both "
            "local load/store byte counters are zero.\n\n"
        )
        f.write(
            "| label | mode | local read bytes | local write bytes | spill read inst | "
            "spill write inst | spill zero verified | evidence source |\n"
        )
        f.write("|---|---|---:|---:|---:|---:|---:|---|\n")
        for row in rows:
            f.write(
                f"| {row['label']} | {row['mode']} | {row['local_read_bytes']} | "
                f"{row['local_write_bytes']} | {row['spill_local_read_inst']} | "
                f"{row['spill_local_write_inst']} | {row['spill_zero_verified']} | "
                f"{row['spill_evidence_source']} |\n"
            )
        f.write("\n")
        f.write("Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.\n")


def run_self_test() -> None:
    metrics = Metrics()
    metrics.values["path_specific.sum"] = [10.0, 20.0]
    metrics.values["aggregate_alias.sum"] = [1000.0]
    assert first_metric_sum(
        metrics, ["path_specific.sum", "aggregate_alias.sum"]
    ) == 30.0
    assert percent_from_hit_miss(95.0, 5.0) == 95.0
    assert percent_from_hit_miss(0.0, 100.0) == 0.0
    assert first_non_none(0.0, 1.0) == 0.0
    assert convert_value(8.192, "Kbyte/block") == 8192.0
    assert convert_value(26.0, "register/thread") == 26.0
    assert math.isclose(convert_value(4.8, "us"), 4.8e-6)
    assert math.isclose(convert_value(12.5, "ms"), 0.0125)
    with tempfile.TemporaryDirectory() as temp_dir:
        raw = Path(temp_dir) / "ga100_raw_metrics.csv"
        native_model = 100.0 * (550.0 + 445.0) / (1000.0 + 450.0)
        raw.write_text(
            "Metric Name,Metric Unit,Metric Value\n"
            "lts__t_sectors_srcunit_tex_aperture_device_op_read.sum,sector,1000\n"
            "lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_hit.sum,sector,550\n"
            "lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_miss.sum,sector,450\n"
            "lts__t_sectors_srcunit_tex_op_read.sum,sector,1000\n"
            "lts__t_sectors_srcunit_tex_op_read_lookup_hit.sum,sector,550\n"
            "lts__t_sectors_srcunit_tex_op_read_lookup_miss.sum,sector,450\n"
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read.sum,sector,450\n"
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_hit.sum,sector,445\n"
            "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_miss.sum,sector,5\n"
            f"lts__t_sector_op_read_hit_rate.pct,%,{native_model}\n"
            "dram__sectors_read.sum,sector,5\n"
            "dram__bytes_read.sum,byte,160\n"
            "dram__bytes_write.sum,byte,0\n",
            encoding="utf-8",
        )
        row = summarize_case(
            "ga100",
            [raw],
            {
                "mode": "l2_cg_load_only",
                "active_SM": "1",
                "blocks_per_SM": "1",
                "ITER": "1",
                "load_repeat": "1",
            },
        )
        assert abs(float(row["l2_path_hit_rate_pct"]) - 55.0) < 1.0e-6
        assert abs(float(row["l2_logical_read_hit_rate_pct"]) - 99.5) < 1.0e-6
        assert abs(float(row["l2_fabric_read_to_source_miss_ratio"]) - 1.0) < 1.0e-6
        assert (
            abs(float(row["l2_fabric_read_fraction"]) - (450.0 / 1450.0))
            < 1.0e-6
        )
        assert float(row["l2_fabric_model_coherent"]) == 1.0
        assert float(row["l2_native_vs_fabric_model_hit_delta_pct"]) < 1.0e-4
        assert row["dram_read_bytes_source"] == "dram__bytes_read.sum"
        assert row["dram_write_bytes_source"] == "dram__bytes_write.sum"
    print("NCU cache path-specific metric self-test passed")


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
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

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
        "reuse_factor",
        "issue_match_steps",
        "issue_match_extra_period",
        "latency_match_ns",
        "latency_match_period",
        "scheduler_match_steps",
        "load_repeat",
        "store_repeat",
        "ncu_replay_mode",
        "ncu_cache_control",
        "ncu_metric_profile",
        "global_warmup_passes",
        "l2_residency_policy",
        "l2_address_layout",
        "status",
        "shared_accesses",
        "shared_bytes",
        "shared_read_bytes",
        "shared_write_bytes",
        "shared_bytes_source",
        "shared_bank_conflicts",
        "shared_inst",
        "legacy_shared_read_accesses",
        "legacy_shared_write_accesses",
        "l1_hit_rate_pct",
        "l1_path_hit_rate_pct",
        "l1_aggregate_hit_rate_pct",
        "l1_hit_rate_source",
        "l2_hit_rate_pct",
        "l2_path_hit_rate_pct",
        "l2_tex_path_hit_rate_pct",
        "l2_device_path_hit_rate_pct",
        "l2_native_read_hit_rate_pct",
        "l2_native_vs_derived_hit_delta_pct",
        "l2_logical_read_hit_rate_pct",
        "l2_fabric_hit_rate_pct",
        "l2_fabric_model_native_hit_rate_pct",
        "l2_native_vs_fabric_model_hit_delta_pct",
        "l2_aggregate_hit_rate_pct",
        "l2_hit_rate_source",
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
        "shared_read_accesses",
        "shared_write_accesses",
        "l1_bytes",
        "l1_request_bytes",
        "l1_hit_bytes",
        "l1_miss_bytes",
        "l2_bytes",
        "l2_read_bytes",
        "expected_global_read_bytes",
        "expected_l2_read_bytes",
        "l2_read_to_expected_ratio",
        "l2_read_hit_sectors",
        "l2_read_miss_sectors",
        "l2_device_read_sectors",
        "l2_device_read_hit_sectors",
        "l2_device_read_miss_sectors",
        "l2_fabric_read_sectors",
        "l2_fabric_read_hit_sectors",
        "l2_fabric_read_miss_sectors",
        "l2_fabric_metric_source",
        "l2_fabric_metrics_present",
        "l2_fabric_read_sector_conservation_ratio",
        "l2_fabric_counter_coherent",
        "l2_fabric_read_to_source_miss_ratio",
        "l2_fabric_hit_to_source_miss_ratio",
        "l2_fabric_read_fraction",
        "l2_logical_read_hit_sectors",
        "l2_logical_read_miss_sectors",
        "l2_logical_read_miss_bytes",
        "l2_fabric_model_coherent",
        "l2_evict_first_read_sectors",
        "l2_evict_normal_read_sectors",
        "l2_evict_last_read_sectors",
        "l2_evict_first_read_pct",
        "l2_evict_normal_read_pct",
        "l2_evict_last_read_pct",
        "l2_read_miss_bytes",
        "l2_read_sector_conservation_ratio",
        "l2_tex_read_sector_conservation_ratio",
        "l2_device_read_sector_conservation_ratio",
        "l2_path_counter_coherent",
        "dram_bytes",
        "dram_read_sectors",
        "dram_write_sectors",
        "dram_read_bytes",
        "dram_read_bytes_source",
        "dram_write_bytes",
        "dram_write_bytes_source",
        "dram_read_to_expected_ratio",
        "dram_write_to_read_ratio",
        "gpu_duration_s",
        "dram_read_bandwidth_GBps",
        "dram_read_to_l2_miss_bytes_ratio",
        "dram_read_to_l2_read_bytes_ratio",
        "dram_read_to_l2_logical_miss_bytes_ratio",
        "tensor_hmma_inst",
        "tensor_fp16_f32_ops",
        "fp16_pipe_inst",
        "sass_ffma_thread_inst",
        "sass_fp16_thread_inst",
        "sass_fp32_thread_inst",
        "sass_integer_thread_inst",
        "sass_inst_executed",
        "expected_register_ops",
        "sass_inst_per_expected_reg_op",
        "expected_logical_mma",
        "expected_logical_flop",
        "tensor_hmma_per_logical_mma",
        "tensor_ops_to_expected_flop",
        "tensor_pipe_active_pct",
        "alu_pipe_active_pct",
        "fma_pipe_active_pct",
        "issue_active_pct",
        "local_read_bytes",
        "local_write_bytes",
        "spill_local_read_inst",
        "spill_local_write_inst",
        "spill_zero_verified",
        "spill_evidence_source",
        "stall_long_scoreboard_pct",
        "stall_short_scoreboard_pct",
        "stall_wait_pct",
        "stall_not_selected_pct",
        "stall_sleeping_pct",
        "sleeping_latency_cycles_per_warp",
        "achieved_occupancy_pct",
        "launch_warp_capacity_pct",
        "launch_warps_per_scheduler",
        "registers_per_thread",
        "shared_mem_per_block_static",
        "shared_mem_per_block_dynamic",
        "launch_persisting_l2_cache_size_bytes",
        "missing_metrics",
        "optional_missing_metrics",
        "validation_notes",
        "source_files",
    ]
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    write_markdown(rows, Path(args.out_md))
    print(f"wrote csv: {out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"cases: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
