#!/usr/bin/env python3
"""Build a strict component coefficient summary from accepted evidence artifacts.

The output is a report/package artifact. It does not estimate new coefficients;
it copies accepted medians from the component reliability audit, attaches
matched-control and NCU evidence paths, and enforces the power measurement policy
from docs/platforms/power_measurement_api_matrix_ko.md:

  nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter.

The resulting rows are effective board-level microbenchmark coefficients, not
pure silicon-level component energy.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
import tempfile
from pathlib import Path


PROFILE_POWER_SEMANTICS = {
    "rtx3090": "one_sec_average",
    "v100": "instant",
    "a100": "instant",
    "h100": "one_sec_average",
}

COMPONENTS = [
    {
        "component_key": "tensor_mma_increment",
        "component": "Tensor MMA incremental",
        "mode_pair": "reg_mma - reg_operand_only",
        "unit": "pJ/FLOP",
        "ncu_candidates": ["tensor_increment_candidate", "register_control_candidate"],
    },
    {
        "component_key": "shared_l1_scalar_path",
        "component": "Shared scalar path",
        "mode_pair": "shared_scalar_load_only - clocked_empty",
        "unit": "pJ/bit",
        "ncu_candidates": ["shared_memory_path"],
    },
    {
        "component_key": "global_l1_hit_path",
        "component": "Global L1 hit path",
        "mode_pair": "global_l1_load_only - global_addr_only",
        "unit": "pJ/bit",
        "ncu_candidates": ["global_l1_hit_path", "global_address_control"],
    },
    {
        "component_key": "l2_hit_cg_path",
        "component": "L2 CG hit path",
        "mode_pair": "l2_cg_load_only - global_addr_only",
        "unit": "pJ/bit",
        "ncu_candidates": ["l2_hit_path", "global_address_control"],
    },
]

NCU_COORDINATE_COLUMNS = [
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "store_repeat",
]

NCU_EXACT_COORDINATE_MODES_BY_COMPONENT = {
    "tensor_mma_increment": {"reg_mma", "reg_operand_only"},
    "shared_l1_scalar_path": {"shared_scalar_load_only"},
    "global_l1_hit_path": {"global_l1_load_only", "global_addr_only"},
    "l2_hit_cg_path": {"l2_cg_load_only", "global_addr_only"},
}

NCU_METRIC_MODES_BY_COMPONENT = {
    "tensor_mma_increment": {"reg_mma"},
    "shared_l1_scalar_path": {"shared_scalar_load_only"},
    "global_l1_hit_path": {"global_l1_load_only"},
    "l2_hit_cg_path": {"l2_cg_load_only"},
}

NCU_METRIC_COLUMNS = [
    "shared_bytes",
    "l1_hit_rate_pct",
    "l1_path_hit_rate_pct",
    "l2_hit_rate_pct",
    "l2_path_hit_rate_pct",
    "l1_accesses",
    "l2_accesses",
    "dram_accesses",
    "l1_bytes",
    "l1_request_bytes",
    "l1_hit_bytes",
    "l1_miss_bytes",
    "l2_bytes",
    "l2_read_bytes",
    "l2_read_hit_sectors",
    "l2_read_miss_sectors",
    "dram_bytes",
    "tensor_hmma_inst",
    "local_read_bytes",
    "local_write_bytes",
    "spill_zero_verified",
    "spill_local_read_inst",
    "spill_local_write_inst",
    "stall_long_scoreboard_pct",
]

FIELDNAMES = [
    "gpu",
    "run_class",
    "component",
    "component_key",
    "mode_pair",
    "condition",
    "selection_note",
    "median",
    "unit",
    "median_ci",
    "rows_used",
    "valid_detail_rows",
    "invalid_detail_rows",
    "ncu_denominator_rows",
    "ncu_accepted_rows",
    "ncu_coordinate_rows",
    "ncu_metric_rows",
    "ncu_evidence_modes",
    "ncu_metric_modes",
    "ncu_evidence_coords",
    "ncu_path_evidence",
    "ncu_counter_caveat",
    "denominator_source",
    "denominator_scale_min_med_max",
    "ncu_denominator_bytes_representative_min_med_max",
    "ncu_shared_bytes_min_med_max",
    "ncu_l1_hit_rate_pct_min_med_max",
    "ncu_l1_path_hit_rate_pct_min_med_max",
    "ncu_l2_hit_rate_pct_min_med_max",
    "ncu_l2_path_hit_rate_pct_min_med_max",
    "ncu_l1_accesses_min_med_max",
    "ncu_l2_accesses_min_med_max",
    "ncu_dram_accesses_min_med_max",
    "ncu_l1_bytes_min_med_max",
    "ncu_l1_request_bytes_min_med_max",
    "ncu_l1_hit_bytes_min_med_max",
    "ncu_l1_miss_bytes_min_med_max",
    "ncu_l2_bytes_min_med_max",
    "ncu_l2_read_bytes_min_med_max",
    "ncu_l2_read_hit_sectors_min_med_max",
    "ncu_l2_read_miss_sectors_min_med_max",
    "ncu_dram_bytes_min_med_max",
    "ncu_tensor_hmma_inst_min_med_max",
    "ncu_local_read_bytes_min_med_max",
    "ncu_local_write_bytes_min_med_max",
    "ncu_spill_zero_verified_min_med_max",
    "ncu_spill_local_read_inst_min_med_max",
    "ncu_spill_local_write_inst_min_med_max",
    "ncu_stall_long_scoreboard_pct_min_med_max",
    "confidence",
    "reliability_status",
    "cautions",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "power_semantics",
    "matched_summary_artifact",
    "summary_artifact",
    "matched_detail_artifact",
    "power_api_audit_artifact",
    "power_state_audit_artifact",
    "reliability_artifact",
    "ncu_acceptance_artifact",
    "ncu_summary_artifact",
    "instability_artifact",
]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def normalize_coord(value: str) -> str:
    text = (value or "").strip()
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if not math.isfinite(number):
        return text
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def coord_key(mode: str, row: dict[str, str]) -> tuple[str, ...]:
    return (mode,) + tuple(normalize_coord(row.get(column, "")) for column in NCU_COORDINATE_COLUMNS)


def fmt_number(value: float) -> str:
    return f"{value:.12g}" if math.isfinite(value) else ""


def fmt_min_med_max(values: list[float]) -> str:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return ""
    if len(finite) == 1 or finite[0] == finite[-1]:
        return fmt_number(finite[len(finite) // 2])
    return "/".join(
        [
            fmt_number(finite[0]),
            fmt_number(statistics.median(finite)),
            fmt_number(finite[-1]),
        ]
    )


def fmt_values(values: list[str], suffix: str = "") -> str:
    clean = sorted({value for value in values if value != ""}, key=lambda item: float(item))
    if not clean:
        return "n/a"
    joined = ",".join(f"{value}{suffix}" for value in clean)
    return joined


def finite_median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def split_artifact_paths(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def reliability_rows_by_component(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("component", ""): row for row in rows}


def summary_rows_by_component(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("component", ""): row for row in rows}


def acceptance_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row.get("acceptance", "") != "accepted":
            continue
        candidate = row.get("component_candidate", "")
        counts[candidate] = counts.get(candidate, 0) + 1
    return counts


def detail_rows_for_component(
    rows: list[dict[str, str]], component_key: str
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("component", "") == component_key
        and truthy(row.get("valid_component_estimate", ""))
    ]


def expected_ncu_coords(component_key: str, details: list[dict[str, str]]) -> set[tuple[str, ...]]:
    exact_modes = NCU_EXACT_COORDINATE_MODES_BY_COMPONENT.get(component_key, set())
    expected: set[tuple[str, ...]] = set()
    for detail in details:
        modes = {detail.get("numerator_mode", ""), detail.get("control_mode", "")}
        for mode in modes & exact_modes:
            expected.add(coord_key(mode, detail))
    return expected


def ncu_coords_for_path(path: str, exact_modes: set[str]) -> set[tuple[str, ...]]:
    if not Path(path).exists():
        return set()
    coords: set[tuple[str, ...]] = set()
    for row in read_csv(path):
        if row.get("status", "") != "ok":
            continue
        mode = row.get("mode", "")
        if mode in exact_modes:
            coords.add(coord_key(mode, row))
    return coords


def ncu_rows_for_coords(
    artifact_paths: str,
    expected_coords: set[tuple[str, ...]],
    exact_modes: set[str],
) -> list[dict[str, str]]:
    if not expected_coords:
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for path in split_artifact_paths(artifact_paths):
        if not Path(path).exists():
            continue
        for row in read_csv(path):
            if row.get("status", "") != "ok":
                continue
            mode = row.get("mode", "")
            if mode not in exact_modes:
                continue
            key = coord_key(mode, row)
            if key not in expected_coords or key in seen:
                continue
            out.append(row)
            seen.add(key)
    return sorted(out, key=lambda row: coord_key(row.get("mode", ""), row))


def ncu_artifact_quality_score(
    component_key: str,
    path: str,
    expected_coords: set[tuple[str, ...]],
    exact_modes: set[str],
) -> float:
    rows = ncu_rows_for_coords(path, expected_coords, exact_modes)
    if not rows:
        return float("-inf")
    score = float(len(rows) * 1000)

    def mid(column: str) -> float:
        return finite_median([as_float(row, column) for row in rows])

    def log_metric(column: str) -> float:
        value = mid(column)
        if not math.isfinite(value) or value <= 0.0:
            return 0.0
        return math.log10(value)

    if component_key == "tensor_mma_increment":
        score += 100.0 if mid("tensor_hmma_inst") > 0.0 else -200.0
        score += 20.0 if mid("l1_bytes") == 0.0 else -20.0
        score += log_metric("tensor_hmma_inst")
    elif component_key == "shared_l1_scalar_path":
        score += 100.0 if mid("shared_bytes") > 0.0 else -200.0
        score += 20.0 if mid("l1_bytes") == 0.0 else -20.0
        score += log_metric("shared_bytes")
    elif component_key == "global_l1_hit_path":
        l1_hit = mid("l1_hit_rate_pct")
        l2_hit = mid("l2_hit_rate_pct")
        score += l1_hit if math.isfinite(l1_hit) else -100.0
        score += 20.0 if mid("l1_bytes") > 0.0 else -100.0
        score += log_metric("l1_bytes")
        if math.isfinite(l2_hit) and l2_hit > 100.0:
            score -= 100.0 + (l2_hit - 100.0) * 10.0
    elif component_key == "l2_hit_cg_path":
        l1_hit = mid("l1_hit_rate_pct")
        l2_hit = mid("l2_hit_rate_pct")
        score += l2_hit if math.isfinite(l2_hit) else -100.0
        score -= min(l1_hit, 100.0) if math.isfinite(l1_hit) else 50.0
        score += 20.0 if mid("l2_bytes") > 0.0 else -100.0
        score += log_metric("l2_bytes")
    return score


def coord_label(row: dict[str, str]) -> str:
    parts = [row.get("mode", "")]
    labels = ["W", "B", "SM", "RF", "LR", "SR"]
    for label, column in zip(labels, NCU_COORDINATE_COLUMNS):
        parts.append(f"{label}{normalize_coord(row.get(column, ''))}")
    return ":".join(parts)


def detail_denominator_summary(details: list[dict[str, str]]) -> dict[str, str]:
    sources = sorted(
        {
            row.get("denominator_source", "")
            for row in details
            if row.get("denominator_source", "")
        }
    )
    return {
        "denominator_source": ",".join(sources),
        "denominator_scale_min_med_max": fmt_min_med_max(
            [as_float(row, "denominator_scale") for row in details]
        ),
        "ncu_denominator_bytes_representative_min_med_max": fmt_min_med_max(
            [as_float(row, "ncu_denominator_bytes_representative") for row in details]
        ),
    }


def ncu_evidence_summary(
    component_key: str,
    details: list[dict[str, str]],
    ncu_summary_artifact: str,
) -> dict[str, str]:
    exact_modes = NCU_EXACT_COORDINATE_MODES_BY_COMPONENT.get(component_key, set())
    metric_modes = NCU_METRIC_MODES_BY_COMPONENT.get(component_key, set())
    expected = expected_ncu_coords(component_key, details)
    coord_rows = ncu_rows_for_coords(ncu_summary_artifact, expected, exact_modes)
    metric_rows = [row for row in coord_rows if row.get("mode", "") in metric_modes]

    out = {
        "ncu_coordinate_rows": str(len(coord_rows)),
        "ncu_metric_rows": str(len(metric_rows)),
        "ncu_evidence_modes": ",".join(sorted({row.get("mode", "") for row in coord_rows})),
        "ncu_metric_modes": ",".join(sorted({row.get("mode", "") for row in metric_rows})),
        "ncu_evidence_coords": ";".join(coord_label(row) for row in coord_rows),
    }
    for column in NCU_METRIC_COLUMNS:
        out[f"ncu_{column}_min_med_max"] = fmt_min_med_max(
            [as_float(row, column) for row in metric_rows]
        )
    out["ncu_path_evidence"] = path_evidence_text(component_key, out)
    out["ncu_counter_caveat"] = counter_caveat_text(component_key)
    return out


def summary_value(summary: dict[str, str], key: str, default: str = "not_reported") -> str:
    value = summary.get(key, "").strip()
    return value if value else default


def path_evidence_text(component_key: str, summary: dict[str, str]) -> str:
    if component_key == "tensor_mma_increment":
        return (
            "HMMA_inst="
            f"{summary_value(summary, 'ncu_tensor_hmma_inst_min_med_max')}; "
            "L1_bytes="
            f"{summary_value(summary, 'ncu_l1_bytes_min_med_max')}; "
            "local_read/write_bytes="
            f"{summary_value(summary, 'ncu_local_read_bytes_min_med_max')}/"
            f"{summary_value(summary, 'ncu_local_write_bytes_min_med_max')}; "
            "spill_zero_verified="
            f"{summary_value(summary, 'ncu_spill_zero_verified_min_med_max')}; "
            "spill_read/write="
            f"{summary_value(summary, 'ncu_spill_local_read_inst_min_med_max')}/"
            f"{summary_value(summary, 'ncu_spill_local_write_inst_min_med_max')}"
        )
    if component_key == "shared_l1_scalar_path":
        return (
            "shared_bytes="
            f"{summary.get('ncu_shared_bytes_min_med_max', '')}; "
            "global_L1_bytes="
            f"{summary.get('ncu_l1_bytes_min_med_max', '')}; "
            "DRAM_bytes="
            f"{summary.get('ncu_dram_bytes_min_med_max', '')}"
        )
    if component_key == "global_l1_hit_path":
        return (
            "L1_path_hit_pct="
            f"{summary.get('ncu_l1_path_hit_rate_pct_min_med_max', '')}; "
            "L1_accesses="
            f"{summary.get('ncu_l1_accesses_min_med_max', '')}; "
            "L1_request/hit_bytes="
            f"{summary.get('ncu_l1_request_bytes_min_med_max', '')}/"
            f"{summary.get('ncu_l1_hit_bytes_min_med_max', '')}; "
            "DRAM_bytes="
            f"{summary.get('ncu_dram_bytes_min_med_max', '')}"
        )
    if component_key == "l2_hit_cg_path":
        return (
            "L1_path_hit_pct="
            f"{summary.get('ncu_l1_path_hit_rate_pct_min_med_max', '')}; "
            "L1_request/hit_bytes="
            f"{summary.get('ncu_l1_request_bytes_min_med_max', '')}/"
            f"{summary.get('ncu_l1_hit_bytes_min_med_max', '')}; "
            "L2_read_hit_pct="
            f"{summary.get('ncu_l2_path_hit_rate_pct_min_med_max', '')}; "
            "L2_read_hit/miss_sectors="
            f"{summary.get('ncu_l2_read_hit_sectors_min_med_max', '')}/"
            f"{summary.get('ncu_l2_read_miss_sectors_min_med_max', '')}; "
            "L2_read_bytes="
            f"{summary.get('ncu_l2_read_bytes_min_med_max', '')}; "
            "DRAM_bytes="
            f"{summary.get('ncu_dram_bytes_min_med_max', '')}"
        )
    return ""


def counter_caveat_text(component_key: str) -> str:
    if component_key == "shared_l1_scalar_path":
        return (
            "Shared path validation uses shared-memory byte/access counters; "
            "global L1/L2 hit-rate fields are background context, not the shared hit rate."
        )
    if component_key == "tensor_mma_increment":
        return (
            "Tensor validation uses HMMA instruction evidence plus zero spill/local "
            "instructions. Cache traffic is contamination context, not a Tensor "
            "denominator; ptxas/register-footprint evidence is still required."
        )
    if component_key == "global_l1_hit_path":
        return (
            "Global-L1 validation uses path-specific global-load lookup hit/miss and "
            "request bytes. Aggregate L1 hit rate can include unrelated traffic."
        )
    if component_key == "l2_hit_cg_path":
        return (
            "An ld.global.cg request still traverses L1TEX, so L1 request bytes are "
            "expected. Bypass is shown by near-zero path-specific L1 hit bytes and a "
            "high path-specific L2 read hit rate; L2 read bytes are the denominator."
        )
    return "Cache hit/access/byte fields are path-relevant for this global-memory candidate."


def select_ncu_summary_artifacts(
    component_key: str,
    details: list[dict[str, str]],
    ncu_summary_csvs: list[str],
) -> str:
    if not ncu_summary_csvs:
        return ""
    exact_modes = NCU_EXACT_COORDINATE_MODES_BY_COMPONENT.get(component_key, set())
    expected = expected_ncu_coords(component_key, details)
    if not exact_modes or not expected:
        return ";".join(ncu_summary_csvs)

    coverages: list[tuple[str, set[tuple[str, ...]]]] = []
    for path in ncu_summary_csvs:
        coverage = expected & ncu_coords_for_path(path, exact_modes)
        if coverage:
            coverages.append((path, coverage))
    full_coverages = [(index, path, coverage) for index, (path, coverage) in enumerate(coverages) if coverage == expected]
    if full_coverages:
        _index, path, _coverage = max(
            full_coverages,
            key=lambda item: (
                ncu_artifact_quality_score(component_key, item[1], expected, exact_modes),
                -item[0],
            ),
        )
        return path

    selected: list[str] = []
    covered: set[tuple[str, ...]] = set()
    ranked = sorted(
        enumerate(coverages),
        key=lambda item: (
            ncu_artifact_quality_score(component_key, item[1][0], expected, exact_modes),
            -item[0],
        ),
        reverse=True,
    )
    for _index, (path, coverage) in ranked:
        new_coords = coverage - covered
        if not new_coords:
            continue
        selected.append(path)
        covered.update(new_coords)
        if covered == expected:
            return ";".join(selected)
    return ";".join(ncu_summary_csvs)


def ci_from_summary(summary_row: dict[str, str], unit: str) -> str:
    if unit == "pJ/bit":
        low = summary_row.get("median_pJ_per_bit_ci_low", "")
        high = summary_row.get("median_pJ_per_bit_ci_high", "")
    else:
        low = summary_row.get("median_ci_low", "")
        high = summary_row.get("median_ci_high", "")
    if low and high:
        return f"{fmt_number(float(low))}-{fmt_number(float(high))}"
    return ""


def condition_from_details(component_key: str, details: list[dict[str, str]]) -> str:
    if not details:
        return "condition unavailable; inspect matched-control detail artifact"

    w_sm = fmt_values([row.get("W_SM_KiB", "") for row in details], " KiB")
    blocks = fmt_values([row.get("blocks_per_SM", "") for row in details])
    active_sm = fmt_values([row.get("active_SM", "") for row in details])
    elapsed = finite_median([as_float(row, "numerator_elapsed_s") for row in details])

    if component_key == "tensor_mma_increment":
        factor = "RF=" + fmt_values([row.get("reuse_factor", "") for row in details])
    else:
        factor = "LR=" + fmt_values([row.get("load_repeat", "") for row in details])

    parts = [
        f"W_SM={w_sm}",
        f"blocks/SM={blocks}",
        f"active_SM={active_sm}",
        factor,
    ]
    if math.isfinite(elapsed):
        parts.append(f"median_elapsed={elapsed:.3f} s")
    return "; ".join(parts)


def validate_inputs(
    *,
    target_profile: str,
    expected_power_semantics: str,
    reliability_by_component: dict[str, dict[str, str]],
    summary_by_component: dict[str, dict[str, str]],
    accepted_ncu: dict[str, int],
) -> list[str]:
    problems: list[str] = []
    if expected_power_semantics != PROFILE_POWER_SEMANTICS.get(target_profile, ""):
        problems.append(
            f"expected power semantics {expected_power_semantics!r} does not match profile "
            f"{target_profile!r}"
        )

    for spec in COMPONENTS:
        key = spec["component_key"]
        rel = reliability_by_component.get(key)
        if not rel:
            problems.append(f"missing reliability row: {key}")
            continue
        if rel.get("status", "") != "accepted":
            problems.append(f"{key}: reliability status is {rel.get('status', '')!r}")
        if rel.get("unit", "") != spec["unit"]:
            problems.append(f"{key}: unit is {rel.get('unit', '')!r}, expected {spec['unit']}")
        if as_float(rel, "median") <= 0.0:
            problems.append(f"{key}: median is not positive")
        if rel.get("energy_source", "") != "nvml_total_energy":
            problems.append(f"{key}: energy_source={rel.get('energy_source', '')!r}")
        if rel.get("energy_integration_method", "") != "total_energy_mj_delta":
            problems.append(
                f"{key}: energy_integration_method={rel.get('energy_integration_method', '')!r}"
            )
        if rel.get("measurement_scope", "") != "gpu_device_total_energy_counter":
            problems.append(f"{key}: measurement_scope={rel.get('measurement_scope', '')!r}")
        if rel.get("power_semantics", "") != expected_power_semantics:
            problems.append(f"{key}: power_semantics={rel.get('power_semantics', '')!r}")
        if as_int(rel, "invalid_detail_rows") != 0:
            problems.append(f"{key}: invalid_detail_rows={rel.get('invalid_detail_rows', '')}")
        if as_int(rel, "valid_detail_rows") <= 0:
            problems.append(f"{key}: valid_detail_rows={rel.get('valid_detail_rows', '')}")
        if spec["unit"] == "pJ/bit" and as_int(rel, "ncu_denominator_rows") <= 0:
            problems.append(f"{key}: ncu_denominator_rows={rel.get('ncu_denominator_rows', '')}")
        if key not in summary_by_component:
            problems.append(f"missing matched-control summary row: {key}")
        for candidate in spec["ncu_candidates"]:
            if accepted_ncu.get(candidate, 0) <= 0:
                problems.append(f"{key}: missing accepted NCU candidate {candidate}")
    return problems


def build_rows(
    *,
    gpu_label: str,
    run_class: str,
    selection_note: str,
    matched_summary_csv: str,
    matched_detail_csv: str,
    power_api_audit_csv: str,
    power_state_audit_csvs: list[str],
    reliability_csv: str,
    ncu_acceptance_csv: str,
    ncu_summary_csvs: list[str],
    instability_artifact: str,
    reliability_by_component: dict[str, dict[str, str]],
    summary_by_component: dict[str, dict[str, str]],
    detail_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    power_state_audit_artifact = ";".join(power_state_audit_csvs)
    for spec in COMPONENTS:
        key = spec["component_key"]
        rel = reliability_by_component[key]
        summary = summary_by_component.get(key, {})
        details = detail_rows_for_component(detail_rows, key)
        ncu_summary_artifact = select_ncu_summary_artifacts(key, details, ncu_summary_csvs)
        denominator_summary = detail_denominator_summary(details)
        ncu_summary = ncu_evidence_summary(key, details, ncu_summary_artifact)
        rows.append(
            {
                "gpu": gpu_label,
                "run_class": run_class,
                "component": spec["component"],
                "component_key": key,
                "mode_pair": spec["mode_pair"],
                "condition": condition_from_details(key, details),
                "selection_note": selection_note,
                "median": fmt_number(as_float(rel, "median")),
                "unit": spec["unit"],
                "median_ci": ci_from_summary(summary, spec["unit"]),
                "rows_used": str(as_int(rel, "rows")),
                "valid_detail_rows": str(as_int(rel, "valid_detail_rows")),
                "invalid_detail_rows": str(as_int(rel, "invalid_detail_rows")),
                "ncu_denominator_rows": str(as_int(rel, "ncu_denominator_rows")),
                "ncu_accepted_rows": str(as_int(rel, "ncu_accepted_rows")),
                **ncu_summary,
                **denominator_summary,
                "confidence": rel.get("confidence_class", ""),
                "reliability_status": rel.get("status", ""),
                "cautions": rel.get("cautions", ""),
                "energy_source": rel.get("energy_source", ""),
                "energy_integration_method": rel.get("energy_integration_method", ""),
                "measurement_scope": rel.get("measurement_scope", ""),
                "power_semantics": rel.get("power_semantics", ""),
                "matched_summary_artifact": matched_summary_csv,
                "summary_artifact": matched_summary_csv,
                "matched_detail_artifact": matched_detail_csv,
                "power_api_audit_artifact": power_api_audit_csv,
                "power_state_audit_artifact": power_state_audit_artifact,
                "reliability_artifact": reliability_csv,
                "ncu_acceptance_artifact": ncu_acceptance_csv,
                "ncu_summary_artifact": ncu_summary_artifact,
                "instability_artifact": instability_artifact,
            }
        )
    return rows


def write_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_selftest_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def detail_selftest_row(
    *,
    component: str,
    numerator_mode: str,
    control_mode: str = "clocked_empty",
    w_sm_kib: str,
    blocks_per_sm: str = "16",
    active_sm: str = "82",
    reuse_factor: str = "1",
    load_repeat: str = "1",
    store_repeat: str = "1",
) -> dict[str, str]:
    return {
        "component": component,
        "valid_component_estimate": "True",
        "numerator_mode": numerator_mode,
        "control_mode": control_mode,
        "W_SM_KiB": w_sm_kib,
        "blocks_per_SM": blocks_per_sm,
        "active_SM": active_sm,
        "reuse_factor": reuse_factor,
        "load_repeat": load_repeat,
        "store_repeat": store_repeat,
    }


def ncu_selftest_row(
    *,
    mode: str,
    w_sm_kib: str,
    blocks_per_sm: str = "16",
    active_sm: str = "82",
    reuse_factor: str = "1",
    load_repeat: str = "1",
    store_repeat: str = "1",
    **metrics: str,
) -> dict[str, str]:
    row = {column: "0" for column in NCU_METRIC_COLUMNS}
    row.update({
        "mode": mode,
        "status": "ok",
        "W_SM_KiB": w_sm_kib,
        "blocks_per_SM": blocks_per_sm,
        "active_SM": active_sm,
        "reuse_factor": reuse_factor,
        "load_repeat": load_repeat,
        "store_repeat": store_repeat,
    })
    row.update(metrics)
    return row


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fields = ["mode", "status", *NCU_COORDINATE_COLUMNS, *NCU_METRIC_COLUMNS]
        tensor_old = root / "tensor_b4.csv"
        tensor_b16 = root / "tensor_b16.csv"
        memory = root / "memory.csv"
        write_selftest_csv(
            tensor_old,
            fields,
            [
                ncu_selftest_row(
                    mode="reg_mma",
                    w_sm_kib="2048",
                    blocks_per_sm="4",
                    reuse_factor="8",
                ),
                ncu_selftest_row(
                    mode="reg_operand_only",
                    w_sm_kib="2048",
                    blocks_per_sm="4",
                    reuse_factor="8",
                ),
            ],
        )
        write_selftest_csv(
            tensor_b16,
            fields,
            [
                ncu_selftest_row(mode="reg_mma", w_sm_kib="2048", reuse_factor="8"),
                ncu_selftest_row(mode="reg_operand_only", w_sm_kib="2048", reuse_factor="8"),
                ncu_selftest_row(mode="reg_mma", w_sm_kib="2048", reuse_factor="16"),
                ncu_selftest_row(mode="reg_operand_only", w_sm_kib="2048", reuse_factor="16"),
                ncu_selftest_row(
                    mode="global_l1_load_only",
                    w_sm_kib="16",
                    load_repeat="4",
                    l1_hit_rate_pct="99.9",
                    l1_path_hit_rate_pct="99.9",
                    l2_hit_rate_pct="101.5",
                    l1_bytes="1000000",
                    l1_request_bytes="1000000",
                    l1_hit_bytes="999000",
                    l1_miss_bytes="1000",
                ),
                ncu_selftest_row(
                    mode="l2_cg_load_only",
                    w_sm_kib="64",
                    load_repeat="4",
                    l1_hit_rate_pct="0.1",
                    l1_path_hit_rate_pct="0.1",
                    l2_hit_rate_pct="99.0",
                    l2_path_hit_rate_pct="99.0",
                    l1_request_bytes="1000000",
                    l1_hit_bytes="1000",
                    l1_miss_bytes="999000",
                    l2_bytes="1000000",
                    l2_read_bytes="1000000",
                    l2_read_hit_sectors="30938",
                    l2_read_miss_sectors="312",
                ),
            ],
        )
        write_selftest_csv(
            memory,
            fields,
            [
                ncu_selftest_row(
                    mode="shared_scalar_load_only",
                    w_sm_kib="64",
                    load_repeat="4",
                    shared_bytes="1000000",
                    l1_bytes="0",
                ),
                ncu_selftest_row(
                    mode="shared_scalar_load_only",
                    w_sm_kib="64",
                    load_repeat="8",
                    shared_bytes="2000000",
                    l1_bytes="0",
                ),
                ncu_selftest_row(
                    mode="global_l1_load_only",
                    w_sm_kib="16",
                    load_repeat="4",
                    l1_hit_rate_pct="99.999",
                    l1_path_hit_rate_pct="99.999",
                    l2_hit_rate_pct="90.0",
                    l1_bytes="2000000",
                    l1_request_bytes="2000000",
                    l1_hit_bytes="1999980",
                    l1_miss_bytes="20",
                ),
                ncu_selftest_row(
                    mode="global_addr_only",
                    w_sm_kib="16",
                    load_repeat="4",
                ),
                ncu_selftest_row(
                    mode="l2_cg_load_only",
                    w_sm_kib="64",
                    load_repeat="4",
                    l1_hit_rate_pct="0.00001",
                    l1_path_hit_rate_pct="0.00001",
                    l2_hit_rate_pct="99.98",
                    l2_path_hit_rate_pct="99.98",
                    l1_request_bytes="2000000",
                    l1_hit_bytes="0.2",
                    l1_miss_bytes="1999999.8",
                    l2_bytes="2000000",
                    l2_read_bytes="2000000",
                    l2_read_hit_sectors="62487.5",
                    l2_read_miss_sectors="12.5",
                ),
                ncu_selftest_row(
                    mode="global_addr_only",
                    w_sm_kib="64",
                    load_repeat="4",
                ),
                ncu_selftest_row(
                    mode="global_addr_only",
                    w_sm_kib="64",
                    load_repeat="8",
                ),
                ncu_selftest_row(
                    mode="l2_cg_load_only",
                    w_sm_kib="64",
                    load_repeat="8",
                    l1_hit_rate_pct="0.00001",
                    l1_path_hit_rate_pct="0.00001",
                    l2_hit_rate_pct="99.99",
                    l2_path_hit_rate_pct="99.99",
                    l1_request_bytes="4000000",
                    l1_hit_bytes="0.4",
                    l1_miss_bytes="3999999.6",
                    l2_bytes="4000000",
                    l2_read_bytes="4000000",
                    l2_read_hit_sectors="124987.5",
                    l2_read_miss_sectors="12.5",
                ),
            ],
        )
        tensor_details = [
            detail_selftest_row(
                component="tensor_mma_increment",
                numerator_mode="reg_mma",
                control_mode="reg_operand_only",
                w_sm_kib="2048",
                reuse_factor="8",
            ),
            detail_selftest_row(
                component="tensor_mma_increment",
                numerator_mode="reg_mma",
                control_mode="reg_operand_only",
                w_sm_kib="2048",
                reuse_factor="16",
            ),
        ]
        shared_details = [
            detail_selftest_row(
                component="shared_l1_scalar_path",
                numerator_mode="shared_scalar_load_only",
                w_sm_kib="64",
                load_repeat="8",
            )
        ]
        global_l1_details = [
            detail_selftest_row(
                component="global_l1_hit_path",
                numerator_mode="global_l1_load_only",
                control_mode="global_addr_only",
                w_sm_kib="16",
                load_repeat="4",
            )
        ]
        l2_details = [
            detail_selftest_row(
                component="l2_hit_cg_path",
                numerator_mode="l2_cg_load_only",
                control_mode="global_addr_only",
                w_sm_kib="64",
                load_repeat="4",
            ),
            detail_selftest_row(
                component="l2_hit_cg_path",
                numerator_mode="l2_cg_load_only",
                control_mode="global_addr_only",
                w_sm_kib="64",
                load_repeat="8",
            ),
        ]
        paths = [str(tensor_old), str(memory), str(tensor_b16)]
        tensor_selected = select_ncu_summary_artifacts(
            "tensor_mma_increment", tensor_details, paths
        )
        if tensor_selected != str(tensor_b16):
            raise AssertionError(f"expected tensor B16 artifact only, got {tensor_selected}")
        shared_selected = select_ncu_summary_artifacts(
            "shared_l1_scalar_path", shared_details, paths
        )
        if shared_selected != str(memory):
            raise AssertionError(f"expected shared memory artifact only, got {shared_selected}")
        global_l1_selected = select_ncu_summary_artifacts(
            "global_l1_hit_path", global_l1_details, paths
        )
        if global_l1_selected != str(memory):
            raise AssertionError(f"expected Global L1 memory artifact only, got {global_l1_selected}")
        l2_selected = select_ncu_summary_artifacts("l2_hit_cg_path", l2_details, paths)
        if l2_selected != str(memory):
            raise AssertionError(f"expected L2 memory artifact only, got {l2_selected}")
        l1_evidence = ncu_evidence_summary(
            "global_l1_hit_path", global_l1_details, global_l1_selected
        )
        if l1_evidence["ncu_l1_path_hit_rate_pct_min_med_max"] != "99.999":
            raise AssertionError(f"missing path-specific L1 evidence: {l1_evidence}")
        if l1_evidence["ncu_l1_request_bytes_min_med_max"] != "2000000":
            raise AssertionError(f"missing L1 request-byte evidence: {l1_evidence}")
        l2_evidence = ncu_evidence_summary("l2_hit_cg_path", l2_details, l2_selected)
        if l2_evidence["ncu_l2_path_hit_rate_pct_min_med_max"] != "99.98/99.985/99.99":
            raise AssertionError(f"missing path-specific L2 evidence: {l2_evidence}")
        if l2_evidence["ncu_l2_read_bytes_min_med_max"] != "2000000/3000000/4000000":
            raise AssertionError(f"missing L2 read-byte evidence: {l2_evidence}")
        if "L1_request/hit_bytes=" not in l2_evidence["ncu_path_evidence"]:
            raise AssertionError(f"L2 path evidence text is incomplete: {l2_evidence}")
    print("strict component summary builder self-test passed")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def unique_artifact_values(rows: list[dict[str, str]], key: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for value in split_artifact_paths(row.get(key, "")):
            if value in seen:
                continue
            out.append(value)
            seen.add(value)
    return out


def write_md(path: str | Path, rows: list[dict[str, str]], *, target_profile: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# Strict Scope + Fresh NCU Component Coefficients\n\n")
        f.write(
            "이 파일은 reliability audit에서 accepted로 판정된 component medians를 "
            "보고용 summary로 묶은 것이다. 새 계수를 다시 fitting하지 않으며, "
            "power measurement matrix 기준의 GPU/device total-energy delta와 NCU path "
            "validation 증거를 함께 기록한다.\n\n"
        )
        f.write(f"- target profile: `{target_profile}`\n")
        f.write("- interpretation: effective board-level microbenchmark coefficient\n")
        f.write("- not: pure transistor/silicon-level component energy\n\n")
        f.write("## Coefficients\n\n")
        f.write(
            "| component | median | unit | CI | rows | NCU rows | denominator | confidence | condition |\n"
        )
        f.write("|---|---:|---|---|---:|---:|---|---|---|\n")
        for row in rows:
            f.write(
                "| "
                + " | ".join(
                    [
                        md_escape(row["component"]),
                        row["median"],
                        row["unit"],
                        row["median_ci"],
                        row["rows_used"],
                        row["ncu_accepted_rows"],
                        row["denominator_source"] or "n/a",
                        row["confidence"],
                        md_escape(row["condition"]),
                    ]
                )
                + " |\n"
            )
        f.write("\n## Report-Ready Table\n\n")
        f.write(
            "이 표는 백서/발표에 바로 옮길 수 있도록 수치, 단위, 실험 pair, "
            "NCU 검증 근거, 해석 주의점을 한 줄에 묶은 것이다.\n\n"
        )
        f.write(
            "| component | report value | treatment-control pair | NCU validation evidence | interpretation caveat |\n"
        )
        f.write("|---|---:|---|---|---|\n")
        for row in rows:
            median = fmt_number(float(row["median"]))
            f.write(
                f"| {md_escape(row['component'])} | {median} {row['unit']} | "
                f"`{md_escape(row['mode_pair'])}` | "
                f"{md_escape(row['ncu_path_evidence'])} | "
                f"{md_escape(row['ncu_counter_caveat'])} |\n"
            )
        f.write("\n## NCU Evidence Summary\n\n")
        f.write(
            "각 값은 strict energy row와 같은 `mode,W_SM,blocks/SM,active_SM,"
            "reuse_factor,load_repeat,store_repeat` 좌표에서 수집한 treatment-path "
            "NCU row의 `min/median/max` 요약이다. 단일 값이면 하나만 표시한다. "
            "Shared scalar와 Tensor row의 global cache hit-rate counter는 path 판정의 "
            "주 증거가 아니라 background context이므로 `path evidence`와 함께 읽어야 한다.\n\n"
        )
        f.write("### Path-Relevant Evidence\n\n")
        f.write("| component | path evidence | caveat |\n|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {md_escape(row['component'])} | "
                f"{md_escape(row['ncu_path_evidence'])} | "
                f"{md_escape(row['ncu_counter_caveat'])} |\n"
            )
        f.write("\n### Raw Counter Context\n\n")
        f.write(
            "| component | coord rows | metric rows | metric modes | L1 path hit % | "
            "L2 read hit % | L1 accesses | L2 accesses | DRAM accesses | shared bytes | "
            "L1 request bytes | L1 hit bytes | L2 read bytes | DRAM bytes | HMMA inst | "
            "long scoreboard % |\n"
        )
        f.write(
            "|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
        for row in rows:
            f.write(
                "| "
                + " | ".join(
                    [
                        md_escape(row["component"]),
                        row["ncu_coordinate_rows"],
                        row["ncu_metric_rows"],
                        md_escape(row["ncu_metric_modes"]),
                        row["ncu_l1_path_hit_rate_pct_min_med_max"],
                        row["ncu_l2_path_hit_rate_pct_min_med_max"],
                        row["ncu_l1_accesses_min_med_max"],
                        row["ncu_l2_accesses_min_med_max"],
                        row["ncu_dram_accesses_min_med_max"],
                        row["ncu_shared_bytes_min_med_max"],
                        row["ncu_l1_request_bytes_min_med_max"],
                        row["ncu_l1_hit_bytes_min_med_max"],
                        row["ncu_l2_read_bytes_min_med_max"],
                        row["ncu_dram_bytes_min_med_max"],
                        row["ncu_tensor_hmma_inst_min_med_max"],
                        row["ncu_stall_long_scoreboard_pct_min_med_max"],
                    ]
                )
                + " |\n"
            )
        f.write("\n## NCU Coordinate Evidence\n\n")
        f.write("| component | exact NCU coordinates |\n|---|---|\n")
        for row in rows:
            f.write(
                f"| {md_escape(row['component'])} | "
                f"`{md_escape(row['ncu_evidence_coords'])}` |\n"
            )
        f.write("\n## Evidence Artifacts\n\n")
        f.write("| artifact type | path |\n|---|---|\n")
        for key in [
            "matched_summary_artifact",
            "matched_detail_artifact",
            "power_api_audit_artifact",
            "power_state_audit_artifact",
            "reliability_artifact",
            "ncu_acceptance_artifact",
            "ncu_summary_artifact",
            "instability_artifact",
        ]:
            for value in unique_artifact_values(rows, key):
                f.write(f"| `{key}` | `{value}` |\n")
        f.write("\n## Reporting Note\n\n")
        f.write(
            "These values are not direct silicon-level Tensor/L1/L2 circuit energy. "
            "They are workload-dependent effective coefficients from board-level "
            "energy deltas, matched-control subtraction, and NCU counter validation.\n"
        )


def main() -> int:
    if "--self-test" in sys.argv:
        run_self_test()
        return 0

    parser = argparse.ArgumentParser()
    parser.add_argument("--target-profile", required=True, choices=sorted(PROFILE_POWER_SEMANTICS))
    parser.add_argument("--gpu-label", required=True)
    parser.add_argument("--matched-summary-csv", required=True)
    parser.add_argument("--matched-detail-csv", required=True)
    parser.add_argument("--power-api-audit-csv", required=True)
    parser.add_argument("--power-state-audit-csv", action="append", default=[])
    parser.add_argument("--reliability-csv", required=True)
    parser.add_argument("--ncu-acceptance-csv", required=True)
    parser.add_argument("--ncu-summary-csv", action="append", default=[])
    parser.add_argument("--instability-artifact", default="")
    parser.add_argument(
        "--run-class",
        default="strict_explicit_measurement_scope_fresh_ncu",
    )
    parser.add_argument(
        "--selection-note",
        default=(
            "Fresh NCU replay accepted; numerator uses NVML total-energy mJ delta "
            "and GPU/device scope"
        ),
    )
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    input_paths = [
        args.matched_summary_csv,
        args.matched_detail_csv,
        args.power_api_audit_csv,
        args.reliability_csv,
        args.ncu_acceptance_csv,
        *args.ncu_summary_csv,
        *args.power_state_audit_csv,
    ]
    if args.instability_artifact:
        input_paths.append(args.instability_artifact)
    missing_inputs = [path for path in input_paths if not Path(path).exists()]
    if missing_inputs:
        for path in missing_inputs:
            print(f"ERROR: input artifact does not exist: {path}")
        return 1

    expected_power_semantics = PROFILE_POWER_SEMANTICS[args.target_profile]
    reliability_rows = read_csv(args.reliability_csv)
    summary_rows = read_csv(args.matched_summary_csv)
    detail_rows = read_csv(args.matched_detail_csv)
    ncu_acceptance_rows = read_csv(args.ncu_acceptance_csv)

    reliability_by_component = reliability_rows_by_component(reliability_rows)
    summary_by_component = summary_rows_by_component(summary_rows)
    accepted_ncu = acceptance_counts(ncu_acceptance_rows)
    problems = validate_inputs(
        target_profile=args.target_profile,
        expected_power_semantics=expected_power_semantics,
        reliability_by_component=reliability_by_component,
        summary_by_component=summary_by_component,
        accepted_ncu=accepted_ncu,
    )
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1

    rows = build_rows(
        gpu_label=args.gpu_label,
        run_class=args.run_class,
        selection_note=args.selection_note,
        matched_summary_csv=args.matched_summary_csv,
        matched_detail_csv=args.matched_detail_csv,
        power_api_audit_csv=args.power_api_audit_csv,
        power_state_audit_csvs=args.power_state_audit_csv,
        reliability_csv=args.reliability_csv,
        ncu_acceptance_csv=args.ncu_acceptance_csv,
        ncu_summary_csvs=args.ncu_summary_csv,
        instability_artifact=args.instability_artifact,
        reliability_by_component=reliability_by_component,
        summary_by_component=summary_by_component,
        detail_rows=detail_rows,
    )
    write_csv(args.out_csv, rows)
    write_md(args.out_md, rows, target_profile=args.target_profile)
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
