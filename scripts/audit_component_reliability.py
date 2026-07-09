#!/usr/bin/env python3
"""Combine power, NCU, and coefficient gates into a component reliability audit."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


COMPONENT_TO_NCU = {
    "tensor_mma_increment": ["tensor_increment_candidate", "register_control_candidate"],
    "shared_l1_scalar_path": ["shared_memory_path"],
    "global_l1_hit_path": ["global_l1_hit_path"],
    "l2_hit_cg_path": ["l2_hit_path"],
    "dram_cg_stream_path": ["dram_sanity_path"],
}

MEMORY_COMPONENTS = {
    "shared_l1_scalar_path",
    "global_l1_hit_path",
    "l2_hit_cg_path",
    "dram_cg_stream_path",
}

CONFIDENCE_ORDER = {
    "high": 4,
    "medium-high": 3,
    "medium": 2,
    "low": 1,
    "": 0,
}


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        value = row.get(key, "")
        if value == "":
            return float("nan")
        return float(value)
    except ValueError:
        return float("nan")


def as_int(row: dict[str, str], key: str) -> int:
    try:
        value = row.get(key, "")
        if value == "":
            return 0
        return int(float(value))
    except ValueError:
        return 0


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def count_power_status(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row.get("status", "") for row in rows)


def ncu_counts(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        component = row.get("component_candidate", "")
        acceptance = row.get("acceptance", "")
        counts[component][acceptance] += 1
    return counts


def detail_counts(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        component = row.get("component", "")
        valid = truthy(row.get("valid_component_estimate", ""))
        counts[component]["valid" if valid else "invalid"] += 1
    return counts


def component_value(row: dict[str, str]) -> tuple[float, str]:
    unit = row.get("unit", "")
    if unit == "pJ/FLOP":
        return as_float(row, "median"), "pJ/FLOP"
    if row.get("median_pJ_per_bit", ""):
        return as_float(row, "median_pJ_per_bit"), "pJ/bit"
    return as_float(row, "median"), unit


def hierarchy_warnings(summary_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    values: dict[str, float] = {}
    for row in summary_rows:
        component = row.get("component", "")
        value, unit = component_value(row)
        if unit == "pJ/bit" and math.isfinite(value):
            values[component] = value

    warnings: dict[str, list[str]] = defaultdict(list)
    shared = values.get("shared_l1_scalar_path")
    l1 = values.get("global_l1_hit_path")
    l2 = values.get("l2_hit_cg_path")
    dram = values.get("dram_cg_stream_path")

    if l2 is not None:
        if shared is not None and l2 <= shared:
            warnings["l2_hit_cg_path"].append("hierarchy_l2_not_greater_than_shared")
            warnings["shared_l1_scalar_path"].append("hierarchy_l2_not_greater_than_shared")
        if l1 is not None and l2 <= l1:
            warnings["l2_hit_cg_path"].append("hierarchy_l2_not_greater_than_l1")
            warnings["global_l1_hit_path"].append("hierarchy_l2_not_greater_than_l1")
    if dram is not None and l2 is not None and dram <= l2:
        warnings["dram_cg_stream_path"].append("hierarchy_dram_not_greater_than_l2")
        warnings["l2_hit_cg_path"].append("hierarchy_dram_not_greater_than_l2")
    if shared is not None and l1 is not None:
        larger = max(shared, l1)
        smaller = max(min(shared, l1), 1.0e-30)
        if larger / smaller > 4.0:
            warnings["shared_l1_scalar_path"].append("shared_l1_global_l1_far_apart")
            warnings["global_l1_hit_path"].append("shared_l1_global_l1_far_apart")
    return warnings


def audit_component(
    row: dict[str, str],
    *,
    power_counts: Counter[str],
    power_scopes: Counter[str],
    ncu_by_component: dict[str, Counter[str]],
    detail_by_component: dict[str, Counter[str]],
    hierarchy_notes: dict[str, list[str]],
    expected_power_semantics: str,
    min_rows: int,
) -> dict[str, str]:
    component = row.get("component", "")
    reasons: list[str] = []
    cautions: list[str] = []

    if power_counts.get("reject", 0):
        reasons.append("power_audit_has_reject_rows")
    if power_counts.get("provisional", 0):
        reasons.append("power_audit_has_provisional_rows")
    if power_counts.get("final_candidate", 0) == 0:
        reasons.append("power_audit_has_no_final_rows")
    if power_scopes.get("gpu_device_total_energy_counter", 0) == 0:
        reasons.append("power_audit_has_no_gpu_device_total_energy_scope")
    bad_scopes = sorted(
        scope
        for scope, count in power_scopes.items()
        if count > 0 and scope != "gpu_device_total_energy_counter"
    )
    if bad_scopes:
        reasons.append("power_audit_has_nonfinal_scope:" + ",".join(bad_scopes))

    if row.get("energy_source", "") != "nvml_total_energy":
        reasons.append("summary_energy_source_not_total")
    if row.get("energy_integration_method", "") != "total_energy_mj_delta":
        reasons.append("summary_integration_not_total_delta")
    if (
        row.get("measurement_scope", "gpu_device_total_energy_counter")
        != "gpu_device_total_energy_counter"
    ):
        reasons.append("summary_measurement_scope_not_gpu_device_total_energy")
    if expected_power_semantics and row.get("power_semantics", "") != expected_power_semantics:
        reasons.append(f"summary_power_semantics_not_{expected_power_semantics}")

    rows = as_int(row, "rows")
    if rows < min_rows:
        cautions.append("few_valid_rows")

    value, value_unit = component_value(row)
    if not math.isfinite(value) or value <= 0.0:
        reasons.append("nonpositive_or_missing_median")

    ncu_required = COMPONENT_TO_NCU.get(component, [])
    accepted_ncu_rows = 0
    missing_ncu = []
    for ncu_component in ncu_required:
        accepted = ncu_by_component.get(ncu_component, Counter()).get("accepted", 0)
        accepted_ncu_rows += accepted
        if accepted <= 0:
            missing_ncu.append(ncu_component)
    if missing_ncu:
        reasons.append("missing_ncu_acceptance:" + ",".join(missing_ncu))

    ncu_denominator_rows = as_int(row, "ncu_denominator_rows")
    if component in MEMORY_COMPONENTS and ncu_denominator_rows <= 0:
        reasons.append("missing_ncu_denominator")

    confidence = row.get("confidence_class", "")
    if CONFIDENCE_ORDER.get(confidence, 0) <= 0:
        cautions.append("missing_confidence_class")
    elif confidence == "low":
        cautions.append("low_stability")

    invalid_detail = detail_by_component.get(component, Counter()).get("invalid", 0)
    valid_detail = detail_by_component.get(component, Counter()).get("valid", 0)
    if invalid_detail:
        cautions.append(f"invalid_detail_rows:{invalid_detail}")

    for warning in hierarchy_notes.get(component, []):
        cautions.append(warning)

    if component == "dram_cg_stream_path":
        cautions.append("dram_sanity_path_not_physical_dram_energy")

    if reasons:
        status = "reject"
    elif confidence == "low":
        status = "accepted_low_stability"
    elif component == "dram_cg_stream_path":
        status = "accepted_sanity"
    elif cautions:
        status = "accepted_with_caution"
    else:
        status = "accepted"

    return {
        "component": component,
        "status": status,
        "median": f"{value:.12g}" if math.isfinite(value) else "",
        "unit": value_unit,
        "rows": str(rows),
        "valid_detail_rows": str(valid_detail),
        "invalid_detail_rows": str(invalid_detail),
        "ncu_denominator_rows": str(ncu_denominator_rows),
        "ncu_accepted_rows": str(accepted_ncu_rows),
        "confidence_class": confidence,
        "energy_source": row.get("energy_source", ""),
        "energy_integration_method": row.get("energy_integration_method", ""),
        "measurement_scope": row.get("measurement_scope", ""),
        "power_semantics": row.get("power_semantics", ""),
        "reasons": ";".join(reasons),
        "cautions": ";".join(cautions),
    }


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "component",
        "status",
        "median",
        "unit",
        "rows",
        "valid_detail_rows",
        "invalid_detail_rows",
        "ncu_denominator_rows",
        "ncu_accepted_rows",
        "confidence_class",
        "energy_source",
        "energy_integration_method",
        "measurement_scope",
        "power_semantics",
        "reasons",
        "cautions",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: str,
    rows: list[dict[str, str]],
    *,
    power_audit_csv: str,
    ncu_acceptance_csv: str,
    matched_summary_csv: str,
    matched_detail_csv: str,
) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(row["status"] for row in rows)
    with out.open("w") as f:
        f.write("# Component Reliability Audit\n\n")
        f.write(
            "This report combines the power API audit, NCU path acceptance, "
            "and matched-control coefficient summary. It is a reliability gate "
            "for effective microbenchmark coefficients, not a proof of pure "
            "silicon-level component energy.\n\n"
        )
        f.write("| input | path |\n|---|---|\n")
        f.write(f"| power API audit | `{power_audit_csv}` |\n")
        f.write(f"| NCU acceptance | `{ncu_acceptance_csv}` |\n")
        f.write(f"| matched summary | `{matched_summary_csv}` |\n")
        f.write(f"| matched detail | `{matched_detail_csv}` |\n\n")

        f.write("## Status Counts\n\n")
        f.write("| status | components |\n|---|---:|\n")
        for status, count in sorted(status_counts.items(), key=lambda item: item[0]):
            f.write(f"| `{status}` | {count} |\n")
        f.write("\n")

        f.write("## Component Verdicts\n\n")
        f.write(
            "| component | status | median | unit | rows | NCU denominator rows | "
            "NCU accepted rows | measurement scope | confidence | cautions | reject reasons |\n"
        )
        f.write("|---|---|---:|---|---:|---:|---:|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['component']}` | `{row['status']}` | {row['median']} | "
                f"{row['unit']} | {row['rows']} | {row['ncu_denominator_rows']} | "
                f"{row['ncu_accepted_rows']} | `{row['measurement_scope']}` | "
                f"`{row['confidence_class']}` | "
                f"{row['cautions'] or '-'} | {row['reasons'] or '-'} |\n"
            )
        f.write("\n")

        f.write("## Interpretation\n\n")
        f.write(
            "- `accepted` means power, NCU path, denominator, positivity, and "
            "stability gates passed without extra cautions.\n"
        )
        f.write(
            "- `accepted_with_caution` means core gates passed but invalid rows, "
            "few rows, or hierarchy cautions remain.\n"
        )
        f.write(
            "- `accepted_low_stability` means the path is accepted but the "
            "coefficient distribution is still unstable. Report this separately.\n"
        )
        f.write(
            "- `accepted_sanity` is used for DRAM streaming sanity. It should not "
            "be described as physical DRAM device energy.\n"
        )
        f.write(
            "- `reject` means at least one required gate failed and the component "
            "must be excluded from final coefficient tables.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--power-audit-csv", required=True)
    parser.add_argument("--ncu-acceptance-csv", required=True)
    parser.add_argument("--matched-summary-csv", required=True)
    parser.add_argument("--matched-detail-csv", required=True)
    parser.add_argument("--expected-power-semantics", default="")
    parser.add_argument("--min-rows", type=int, default=3)
    parser.add_argument(
        "--out-csv",
        default="results/summary/component_reliability_audit.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/component_reliability_audit.md",
    )
    parser.add_argument("--fail-on-reject", action="store_true")
    args = parser.parse_args()

    power_rows = read_csv(args.power_audit_csv)
    acceptance_rows = read_csv(args.ncu_acceptance_csv)
    summary_rows = read_csv(args.matched_summary_csv)
    detail_rows = read_csv(args.matched_detail_csv)

    power_counts = count_power_status(power_rows)
    power_scopes = Counter(row.get("measurement_scope", "") for row in power_rows)
    ncu_by_component = ncu_counts(acceptance_rows)
    detail_by_component = detail_counts(detail_rows)
    hierarchy_notes = hierarchy_warnings(summary_rows)

    audit_rows = [
        audit_component(
            row,
            power_counts=power_counts,
            power_scopes=power_scopes,
            ncu_by_component=ncu_by_component,
            detail_by_component=detail_by_component,
            hierarchy_notes=hierarchy_notes,
            expected_power_semantics=args.expected_power_semantics,
            min_rows=args.min_rows,
        )
        for row in summary_rows
    ]

    write_csv(args.out_csv, audit_rows)
    write_markdown(
        args.out_md,
        audit_rows,
        power_audit_csv=args.power_audit_csv,
        ncu_acceptance_csv=args.ncu_acceptance_csv,
        matched_summary_csv=args.matched_summary_csv,
        matched_detail_csv=args.matched_detail_csv,
    )

    status_counts = Counter(row["status"] for row in audit_rows)
    print(
        "component reliability rows="
        f"{len(audit_rows)} "
        + " ".join(f"{key}={status_counts[key]}" for key in sorted(status_counts))
    )
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    if args.fail_on_reject and status_counts["reject"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
