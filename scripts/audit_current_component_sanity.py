#!/usr/bin/env python3
"""Audit current reporting coefficients against strict sanity gates.

This script does not prove pure silicon-level energy. It checks whether the
current effective microbenchmark coefficients are internally consistent enough
to report: final GPU/device total-energy scope, positive confidence intervals,
expected units, primary/auxiliary separation, and broad memory-hierarchy order.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


PRIMARY_COMPONENTS = {
    "tensor": "tensor_mma_increment_duration_targeted",
    "shared": "shared_l1_scalar_path",
    "global_l1": "global_l1_hit_path",
    "l2": "l2_hit_cg_path",
    "dram_sanity": "dram_cg_stream_path",
}

EXPLICIT_SCOPE_AUDIT = Path(
    "results/summary/rtx3090_current_explicit_scope_power_api_audit_20260708.csv"
)

EXPECTED_UNITS = {
    "tensor": "pJ/FLOP",
    "shared": "pJ/bit",
    "global_l1": "pJ/bit",
    "l2": "pJ/bit",
    "dram_sanity": "pJ/bit",
}

LOOSE_RANGE = {
    "tensor": (0.02, 0.30),
    "shared": (0.02, 0.50),
    "global_l1": (0.02, 0.50),
    "l2": (0.20, 5.00),
    "dram_sanity": (1.00, 20.00),
}

AUXILIARY_SENSITIVITY = {
    "tensor": {
        "component": "tensor_mma_increment_duration_targeted",
        "prefix": "tensor_mma_increment_",
        "ratio_max": 1.5,
        "expected": "auxiliary max/min <= 1.5 for single Tensor coefficient interpretation",
        "interpretation": (
            "Tensor primary can be reported, but RF/control-policy spread means it must be "
            "described as an RF-dependent effective coefficient"
        ),
    },
    "shared": {
        "component": "shared_l1_scalar_path",
        "prefix": "shared_l1_scalar_path_",
        "ratio_max": 2.0,
        "expected": "auxiliary max/min <= 2 for single Shared coefficient interpretation",
        "interpretation": (
            "Shared primary can be reported, but LR/control-policy spread means it must be "
            "described as a method-sensitive effective path coefficient"
        ),
    },
    "global_l1": {
        "component": "global_l1_hit_path",
        "prefix": "global_l1_hit_path_",
        "ratio_max": 2.0,
        "expected": "auxiliary max/min <= 2 for single Global L1 coefficient interpretation",
        "interpretation": (
            "Global L1 primary can be reported; auxiliary spread quantifies duration/load-repeat "
            "sensitivity rather than pure L1 bitcell energy"
        ),
    },
    "l2": {
        "component": "l2_hit_cg_path",
        "prefix": "l2_hit_cg_path_",
        "ratio_max": 2.0,
        "expected": "auxiliary max/min <= 2 for single L2 coefficient interpretation",
        "interpretation": (
            "L2 primary can be reported; auxiliary spread quantifies ordering/stall sensitivity "
            "rather than pure L2 SRAM energy"
        ),
    },
}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return default


def add_check(
    rows: list[dict[str, str]],
    *,
    component: str,
    check: str,
    status: str,
    expected: str,
    actual: str,
    interpretation: str,
) -> None:
    rows.append(
        {
            "component": component,
            "check": check,
            "status": status,
            "expected": expected,
            "actual": actual,
            "interpretation": interpretation,
        }
    )


def only_total_energy_scope(scope: str) -> bool:
    if not scope:
        return False
    parts = [part.strip() for part in scope.split(";") if part.strip()]
    return bool(parts) and all(part.startswith("gpu_device_total_energy_counter=") for part in parts)


def parse_ci(ci: str) -> tuple[float, float] | None:
    if not ci or "-" not in ci:
        return None
    left, right = ci.split("-", 1)
    try:
        return float(left), float(right)
    except ValueError:
        return None


def finite_positive_medians(rows: list[dict[str, str]]) -> list[float]:
    values = [as_float(row, "median") for row in rows]
    return [value for value in values if value > 0.0 and math.isfinite(value)]


def audit(coeff_rows: list[dict[str, str]], evidence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    coeff_by_component = {row["component"]: row for row in coeff_rows}
    evidence_by_component = {row["component"]: row for row in evidence_rows}
    primary: dict[str, dict[str, str]] = {}

    for group, component in PRIMARY_COMPONENTS.items():
        coeff = coeff_by_component.get(component)
        evidence = evidence_by_component.get(component)
        if not coeff:
            add_check(
                checks,
                component=component,
                check="primary_row_present",
                status="fail",
                expected="row exists",
                actual="missing",
                interpretation="current reporting table is missing a required primary/sanity row",
            )
            continue
        primary[group] = coeff
        add_check(
            checks,
            component=component,
            check="primary_row_present",
            status="pass",
            expected="row exists",
            actual="present",
            interpretation="required current reporting row exists",
        )

        expected_unit = EXPECTED_UNITS[group]
        actual_unit = coeff.get("unit", "")
        add_check(
            checks,
            component=component,
            check="unit",
            status="pass" if actual_unit == expected_unit else "fail",
            expected=expected_unit,
            actual=actual_unit,
            interpretation="unit must prevent pJ/FLOP and pJ/bit from being mixed",
        )

        median = as_float(coeff, "median")
        low = as_float(coeff, "ci_low")
        high = as_float(coeff, "ci_high")
        positive = median > 0 and low > 0 and high > 0
        add_check(
            checks,
            component=component,
            check="positive_median_and_ci",
            status="pass" if positive else "fail",
            expected="median, ci_low, ci_high > 0",
            actual=f"median={median:g}, ci_low={low:g}, ci_high={high:g}",
            interpretation="negative or zero intervals indicate weak-signal/control drift, not reportable coefficient",
        )

        lo, hi = LOOSE_RANGE[group]
        in_range = lo <= median <= hi
        add_check(
            checks,
            component=component,
            check="loose_reference_order_range",
            status="pass" if in_range else "warning",
            expected=f"{lo:g} <= median <= {hi:g}",
            actual=f"{median:g}",
            interpretation="broad order-of-magnitude screen only; not a literature fit or silicon-level bound",
        )

        if not evidence:
            add_check(
                checks,
                component=component,
                check="evidence_row_present",
                status="fail",
                expected="evidence row exists",
                actual="missing",
                interpretation="cannot verify power scope, NCU, and reliability gates",
            )
            continue

        final_rows = int(evidence.get("power_final_rows", "0") or 0)
        prov_rows = int(evidence.get("power_provisional_rows", "0") or 0)
        reject_rows = int(evidence.get("power_reject_rows", "0") or 0)
        scope = evidence.get("measurement_scopes", "")
        power_ok = final_rows > 0 and prov_rows == 0 and reject_rows == 0 and only_total_energy_scope(scope)
        add_check(
            checks,
            component=component,
            check="power_api_scope",
            status="pass" if power_ok else "fail",
            expected="final>0, provisional=0, reject=0, scope=gpu_device_total_energy_counter only",
            actual=f"final={final_rows}, provisional={prov_rows}, reject={reject_rows}, scope={scope}",
            interpretation="uses docs/platforms/power_measurement_api_matrix_ko.md final numerator policy",
        )

        reliability = evidence.get("reliability_status", "")
        evidence_level = evidence.get("evidence_level", "")
        if group == "dram_sanity":
            ok = reliability == "accepted_sanity" and evidence_level == "sanity_only"
            status = "pass" if ok else "fail"
            expected = "accepted_sanity + sanity_only"
            meaning = "DRAM row is allowed only as hierarchy sanity, not physical DRAM/HBM energy"
        elif group == "shared":
            ok = reliability in {"accepted", "accepted_with_caution"} and evidence_level in {
                "strong_candidate",
                "accepted_with_caution",
            }
            status = "pass" if ok and reliability == "accepted" else "warning" if ok else "fail"
            expected = "accepted or accepted_with_caution"
            meaning = "Shared primary evidence is clean; remaining method sensitivity is audited separately"
        else:
            ok = reliability == "accepted" and evidence_level == "strong_candidate"
            status = "pass" if ok else "warning"
            expected = "accepted + strong_candidate"
            meaning = "primary coefficient should have clean power, NCU, and reliability evidence"
        add_check(
            checks,
            component=component,
            check="evidence_level",
            status=status,
            expected=expected,
            actual=f"reliability={reliability}, evidence_level={evidence_level}",
            interpretation=meaning,
        )

    if {"shared", "global_l1", "l2", "dram_sanity"}.issubset(primary):
        shared = as_float(primary["shared"], "median")
        l1 = as_float(primary["global_l1"], "median")
        l2 = as_float(primary["l2"], "median")
        dram = as_float(primary["dram_sanity"], "median")
        add_check(
            checks,
            component="memory_hierarchy",
            check="l1_less_than_l2",
            status="pass" if l1 < l2 and shared < l2 else "fail",
            expected="shared and global L1 effective pJ/bit < L2 effective pJ/bit",
            actual=f"shared={shared:g}, global_l1={l1:g}, l2={l2:g}",
            interpretation="if L1/shared exceeds L2, path attribution or denominator is suspect",
        )
        add_check(
            checks,
            component="memory_hierarchy",
            check="l2_less_than_dram_sanity",
            status="pass" if l2 < dram else "fail",
            expected="L2 effective pJ/bit < DRAM streaming sanity pJ/bit",
            actual=f"l2={l2:g}, dram_sanity={dram:g}",
            interpretation="DRAM sanity is not physical device energy, but should be above L2 for hierarchy sanity",
        )
        ratio = shared / l1 if l1 else float("inf")
        add_check(
            checks,
            component="memory_hierarchy",
            check="shared_vs_global_l1_same_order",
            status="pass" if 0.5 <= ratio <= 2.0 else "warning",
            expected="0.5 <= shared/global_l1 <= 2.0",
            actual=f"{ratio:g}",
            interpretation="shared scalar and global L1 use different instruction/control paths but should be same-order",
        )

    for group, rule in AUXILIARY_SENSITIVITY.items():
        if group not in primary:
            continue
        primary_component = str(rule["component"])
        prefix = str(rule["prefix"])
        aux_rows = [
            row
            for row in coeff_rows
            if row.get("component", "").startswith(prefix)
            and row.get("component", "") != primary_component
            and "auxiliary" in row.get("status", "")
        ]
        aux_values = finite_positive_medians(aux_rows)
        if not aux_values:
            continue
        primary_value = as_float(primary[group], "median")
        all_values = aux_values + [primary_value]
        lo = min(all_values)
        hi = max(all_values)
        ratio = hi / lo if lo > 0.0 else float("inf")
        ratio_max = float(rule["ratio_max"])
        add_check(
            checks,
            component=primary_component,
            check="auxiliary_method_sensitivity",
            status="warning" if ratio > ratio_max else "pass",
            expected=str(rule["expected"]),
            actual=f"min={lo:g}, max={hi:g}, ratio={ratio:g}",
            interpretation=str(rule["interpretation"]),
        )

    if {"tensor", "shared", "global_l1", "l2"}.issubset(primary):
        add_check(
            checks,
            component="overall",
            check="final_reporting_language",
            status="warning",
            expected="report as effective microbenchmark coefficients",
            actual="not pure silicon-level energy",
            interpretation=(
                "even if all checks pass, report Tensor, Shared/L1, L1, L2 as workload-dependent "
                "effective coefficients with mode, factor, W_SM, blocks/SM, and units"
            ),
        )

    if EXPLICIT_SCOPE_AUDIT.exists():
        scope_rows = read_csv(EXPLICIT_SCOPE_AUDIT)
        total = len(scope_rows)
        final_rows = sum(1 for row in scope_rows if row.get("status") == "final_candidate")
        reject_rows = sum(1 for row in scope_rows if row.get("status") == "reject")
        missing_scope = sum(
            1
            for row in scope_rows
            if "missing_explicit_measurement_scope" in row.get("reasons", "")
        )
        add_check(
            checks,
            component="overall",
            check="explicit_measurement_scope_coverage",
            status="pass" if total > 0 and reject_rows == 0 else "warning",
            expected="new finalplan raw rows carry explicit measurement_scope",
            actual=(
                f"explicit-scope audit rows={total}, final={final_rows}, "
                f"reject={reject_rows}, missing_explicit_scope={missing_scope}"
            ),
            interpretation=(
                "current 2026-07-08 RTX 3090 component rows mostly predate the "
                "explicit measurement_scope CSV column; their GPU/device scope was "
                "inferred from nvml_total_energy + total_energy_mj_delta. New "
                "cross-platform final runs must be rerun with explicit measurement_scope."
            ),
        )
    else:
        add_check(
            checks,
            component="overall",
            check="explicit_measurement_scope_coverage",
            status="warning",
            expected=f"{EXPLICIT_SCOPE_AUDIT} exists",
            actual="missing",
            interpretation=(
                "run the explicit-scope power API audit before claiming strict "
                "compliance with docs/platforms/power_measurement_api_matrix_ko.md"
            ),
        )

    return checks


def write_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["component", "check", "status", "expected", "actual", "interpretation"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: str | Path, rows: list[dict[str, str]], coeff_csv: str, evidence_csv: str) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# Current Component Sanity Audit\n\n")
        f.write(
            "이 문서는 현재 보고용 coefficient 표가 power API matrix, NCU/evidence matrix, "
            "계층적 order-of-magnitude 기준을 동시에 만족하는지 점검한다. "
            "통과는 순수 회로 에너지를 증명하지 않고, 현재 microbenchmark 결과를 "
            "effective coefficient로 보고할 수 있는지의 최소 sanity gate다.\n\n"
        )
        f.write("| input | path |\n|---|---|\n")
        f.write(f"| coefficient CSV | `{coeff_csv}` |\n")
        f.write(f"| evidence matrix CSV | `{evidence_csv}` |\n\n")
        f.write("## Status Counts\n\n")
        f.write("| status | checks |\n|---|---:|\n")
        for key in sorted(counts):
            f.write(f"| `{key}` | {counts[key]} |\n")
        f.write("\n## Checks\n\n")
        f.write("| component | check | status | expected | actual | interpretation |\n")
        f.write("|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['component']}` | `{row['check']}` | `{row['status']}` | "
                f"{row['expected']} | {row['actual']} | {row['interpretation']} |\n"
            )
        f.write("\n## Interpretation\n\n")
        f.write(
            "- `fail`은 current reporting 표에서 제외하거나 원인을 고쳐야 한다.\n"
            "- `warning`은 보고 가능하지만 단일 순수 component 상수로 주장하면 안 된다.\n"
            "- `pass`여도 NVML numerator는 GPU/device total-energy telemetry이며, "
            "NCU counter는 denominator와 path validation에만 쓰인다.\n"
            "- DRAM row는 hierarchy sanity다. physical GDDR6X/HBM device pJ/bit가 아니다.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coeff-csv",
        default="results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv",
    )
    parser.add_argument(
        "--evidence-csv",
        default="results/summary/rtx3090_current_reporting_evidence_matrix_20260708.csv",
    )
    parser.add_argument(
        "--out-csv",
        default="results/summary/rtx3090_current_component_sanity_audit_20260708.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/rtx3090_current_component_sanity_audit_20260708.md",
    )
    parser.add_argument("--fail-on-fail", action="store_true")
    args = parser.parse_args()

    rows = audit(read_csv(args.coeff_csv), read_csv(args.evidence_csv))
    write_csv(args.out_csv, rows)
    write_md(args.out_md, rows, args.coeff_csv, args.evidence_csv)

    fail_count = sum(1 for row in rows if row["status"] == "fail")
    warning_count = sum(1 for row in rows if row["status"] == "warning")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    print(f"checks={len(rows)} failures={fail_count} warnings={warning_count}")
    return 1 if args.fail_on_fail and fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
