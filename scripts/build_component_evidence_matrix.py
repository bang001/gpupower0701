#!/usr/bin/env python3
"""Build an evidence matrix for current component-energy reporting values."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

NCU_REQUIREMENTS = {
    "tensor_mma_increment": ["tensor_increment_candidate", "register_control_candidate"],
    "shared_l1_scalar_path": ["shared_memory_path"],
    "global_l1_hit_path": ["global_l1_hit_path"],
    "l2_hit_cg_path": ["l2_hit_path"],
    "dram_cg_stream_path": ["dram_sanity_path"],
}

COMPONENT_POWER_STATE_MODES = {
    "tensor_mma_increment": {"reg_mma", "reg_operand_only"},
    "shared_l1_scalar_path": {"shared_scalar_load_only", "clocked_empty"},
    "global_l1_hit_path": {"global_l1_load_only", "clocked_empty"},
    "l2_hit_cg_path": {"l2_cg_load_only", "clocked_empty"},
    "dram_cg_stream_path": {"dram_cg_load_only", "clocked_empty"},
}

CONFIDENCE_ORDER = {
    "": 0,
    "low": 1,
    "medium": 2,
    "medium-high": 3,
    "high": 4,
}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "component",
        "path",
        "median",
        "unit",
        "ci",
        "rows",
        "confidence",
        "reporting_status",
        "evidence_level",
        "power_final_rows",
        "power_provisional_rows",
        "power_reject_rows",
        "measurement_scopes",
        "power_state_status_counts",
        "ncu_required",
        "ncu_accepted_rows",
        "ncu_denominator_rows",
        "reliability_status",
        "reliability_cautions",
        "reliability_reasons",
        "risks",
        "next_action",
        "source_artifact",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def base_component(component: str) -> str:
    if component.startswith("tensor_mma_increment"):
        return "tensor_mma_increment"
    if component.startswith("shared_l1_scalar_path"):
        return "shared_l1_scalar_path"
    if component.startswith("global_l1_hit_path"):
        return "global_l1_hit_path"
    if component.startswith("l2_hit_cg_path"):
        return "l2_hit_cg_path"
    return component


def artifact_family(source_artifact: str) -> str:
    if "tensor_rf16_duration_scaling" in source_artifact:
        return "tensor_rf16_duration_scaling"
    if "tensor_rf8_duration_scaling" in source_artifact:
        return "tensor_rf8_duration_scaling"
    if "tensor_targeted_rf8_rf16" in source_artifact:
        return "tensor_targeted_rf8_rf16"
    if "tensor_fixed_iter_rf8_rf16" in source_artifact:
        return "tensor_fixed_iter_rf8_rf16"
    if "finalplan_stability_factor_exactncu" in source_artifact:
        return "finalplan_stability"
    if "shared_paired_lr4_30s_stability" in source_artifact:
        return "shared_paired_lr4_30s_stability"
    if "shared_paired_lr8_30s_combined" in source_artifact:
        return "shared_paired_lr8_30s_combined"
    if "shared_paired_lr8_30s_stability" in source_artifact:
        return "shared_paired_lr8_30s_stability"
    if "shared_paired_lr16_30s_combined" in source_artifact:
        return "shared_paired_lr16_30s_combined"
    if "shared_paired_lr16_60s_stability" in source_artifact:
        return "shared_paired_lr16_60s_stability"
    if "shared_interleaved_lr4_lr8_lr16_30s" in source_artifact:
        return "shared_interleaved_lr4_lr8_lr16_30s"
    if "shared_fixediter_lr4_lr8_lr16" in source_artifact:
        return "shared_fixediter_lr4_lr8_lr16"
    if "shared_fixediter_lr16_focus" in source_artifact:
        return "shared_fixediter_lr16_focus"
    if "shared_fixediter_lr4_lr8_focus" in source_artifact:
        return "shared_fixediter_lr4_lr8_focus"
    if "shared_paired_lr16_30s_stability" in source_artifact:
        return "shared_paired_lr16_30s_stability"
    if "targeted_shared_l1_powerstate_filtered" in source_artifact:
        return "targeted_shared_l1_powerstate_filtered"
    if "targeted_shared_l1" in source_artifact:
        return "targeted_shared_l1"
    if "targeted_l2_powerstate_filtered" in source_artifact:
        return "targeted_l2_powerstate_filtered"
    if "targeted_l2" in source_artifact:
        return "targeted_l2"
    if "l2_paired_lr4_lr8_30s_combined" in source_artifact:
        return "l2_paired_lr4_lr8_30s_combined"
    if "l2_paired_lr8_30s_stability" in source_artifact:
        return "l2_paired_lr8_30s_stability"
    if "l2_paired_lr4_30s_stability" in source_artifact:
        return "l2_paired_lr4_30s_stability"
    if "l1_duration_scaling_powerstate_filtered" in source_artifact:
        return "l1_duration_scaling_powerstate_filtered"
    if "l1_60s_stability_powerstate_filtered" in source_artifact:
        return "l1_60s_stability_powerstate_filtered"
    if "l1_60s_stability" in source_artifact:
        return "l1_60s_stability"
    if "l1_paired_30s_combined" in source_artifact:
        return "l1_paired_30s_combined"
    if "l1_paired_lr8_30s_stability" in source_artifact:
        return "l1_paired_lr8_30s_stability"
    if "l1_paired_30s_stability" in source_artifact:
        return "l1_paired_30s_stability"
    if "l1_duration_scaling" in source_artifact:
        return "l1_duration_scaling"
    if "shared_l2_30s_stability" in source_artifact:
        return "shared_l2_30s_stability"
    return "unknown"


def default_artifacts(family: str) -> dict[str, Path]:
    prefix = ROOT / "results" / "summary"
    if family == "tensor_rf16_duration_scaling":
        base = prefix / "rtx3090_tensor_rf16_duration_scaling"
    elif family == "tensor_rf8_duration_scaling":
        base = prefix / "rtx3090_tensor_rf8_duration_scaling"
    elif family == "tensor_targeted_rf8_rf16":
        base = prefix / "rtx3090_tensor_targeted_rf8_rf16"
    elif family == "tensor_fixed_iter_rf8_rf16":
        base = prefix / "rtx3090_tensor_fixed_iter_rf8_rf16"
    elif family == "shared_paired_lr4_30s_stability":
        base = prefix / "rtx3090_shared_paired_lr4_30s_stability"
    elif family == "shared_paired_lr8_30s_combined":
        base = prefix / "rtx3090_shared_paired_lr8_30s_combined"
    elif family == "shared_paired_lr8_30s_stability":
        base = prefix / "rtx3090_shared_paired_lr8_30s_stability"
    elif family == "shared_paired_lr16_30s_combined":
        base = prefix / "rtx3090_shared_paired_lr16_30s_combined"
    elif family == "shared_paired_lr16_60s_stability":
        base = prefix / "rtx3090_shared_paired_lr16_60s_stability"
    elif family == "shared_interleaved_lr4_lr8_lr16_30s":
        base = prefix / "rtx3090_shared_interleaved_lr4_lr8_lr16_30s"
    elif family == "shared_fixediter_lr4_lr8_lr16":
        base = prefix / "rtx3090_shared_fixediter_lr4_lr8_lr16"
    elif family == "shared_fixediter_lr16_focus":
        base = prefix / "rtx3090_shared_fixediter_lr16_focus"
    elif family == "shared_fixediter_lr4_lr8_focus":
        base = prefix / "rtx3090_shared_fixediter_lr4_lr8_focus"
    elif family == "shared_paired_lr16_30s_stability":
        base = prefix / "rtx3090_shared_paired_lr16_30s_stability"
    elif family == "targeted_shared_l1_powerstate_filtered":
        base = prefix / "rtx3090_targeted_shared_l1"
        return {
            "power": Path(f"{base}_power_api_audit_20260708.csv"),
            "power_state": Path(f"{base}_power_state_audit_20260708.csv"),
            "reliability": prefix
            / "rtx3090_targeted_shared_l1_powerstate_filtered_component_reliability_audit_20260708.csv",
        }
    elif family == "targeted_shared_l1":
        base = prefix / "rtx3090_targeted_shared_l1"
    elif family == "targeted_l2_powerstate_filtered":
        base = prefix / "rtx3090_targeted_l2"
        return {
            "power": Path(f"{base}_power_api_audit_20260708.csv"),
            "power_state": Path(f"{base}_power_state_audit_20260708.csv"),
            "reliability": prefix
            / "rtx3090_targeted_l2_powerstate_filtered_component_reliability_audit_20260708.csv",
        }
    elif family == "targeted_l2":
        base = prefix / "rtx3090_targeted_l2"
    elif family == "l2_paired_lr4_lr8_30s_combined":
        base = prefix / "rtx3090_l2_paired_lr4_lr8_30s_combined"
    elif family == "l2_paired_lr8_30s_stability":
        base = prefix / "rtx3090_l2_paired_lr8_30s_stability"
    elif family == "l2_paired_lr4_30s_stability":
        base = prefix / "rtx3090_l2_paired_lr4_30s_stability"
    elif family == "l1_60s_stability_powerstate_filtered":
        base = prefix / "rtx3090_l1_60s_stability"
        return {
            "power": Path(f"{base}_power_api_audit_20260708.csv"),
            "power_state": Path(f"{base}_power_state_audit_20260708.csv"),
            "reliability": prefix
            / "rtx3090_l1_60s_stability_powerstate_filtered_component_reliability_audit_20260708.csv",
        }
    elif family == "l1_60s_stability":
        base = prefix / "rtx3090_l1_60s_stability"
    elif family == "l1_paired_30s_combined":
        base = prefix / "rtx3090_l1_paired_30s_combined"
    elif family == "l1_paired_lr8_30s_stability":
        base = prefix / "rtx3090_l1_paired_lr8_30s_stability"
    elif family == "l1_paired_30s_stability":
        base = prefix / "rtx3090_l1_paired_30s_stability"
    elif family == "l1_duration_scaling_powerstate_filtered":
        base = prefix / "rtx3090_l1_duration_scaling"
        return {
            "power": Path(f"{base}_power_api_audit_20260708.csv"),
            "power_state": Path(f"{base}_power_state_audit_20260708.csv"),
            "reliability": prefix
            / "rtx3090_l1_duration_scaling_powerstate_filtered_component_reliability_audit_20260708.csv",
        }
    elif family == "l1_duration_scaling":
        base = prefix / "rtx3090_l1_duration_scaling"
    elif family == "shared_l2_30s_stability":
        base = prefix / "rtx3090_shared_l2_30s_stability"
    elif family == "finalplan_stability":
        return {
            "power": prefix / "rtx3090_finalplan_stability_power_api_audit_20260708.csv",
            "power_state": prefix / "rtx3090_finalplan_stability_power_state_audit_20260708.csv",
            "reliability": prefix / "rtx3090_finalplan_stability_component_reliability_audit_20260708.csv",
        }
    else:
        return {}
    return {
        "power": Path(f"{base}_power_api_audit_20260708.csv"),
        "power_state": Path(f"{base}_power_state_audit_20260708.csv"),
        "reliability": Path(f"{base}_component_reliability_audit_20260708.csv"),
    }


def count_column(rows: list[dict[str, str]], key: str) -> Counter[str]:
    return Counter(row.get(key, "") for row in rows)


def filter_power_state_rows(
    rows: list[dict[str, str]], component: str
) -> list[dict[str, str]]:
    modes = COMPONENT_POWER_STATE_MODES.get(base_component(component))
    if not modes or not rows or "mode" not in rows[0]:
        return rows
    return [row for row in rows if row.get("mode") in modes]


def compact_counts(counts: Counter[str]) -> str:
    if not counts:
        return ""
    return ";".join(f"{key or '(empty)'}={counts[key]}" for key in sorted(counts))


def reliability_for(path: Path | None, component: str) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    base = base_component(component)
    for row in read_csv(path):
        if row.get("component") in {component, base}:
            return row
    return {}


def source_summary_row(source_artifact: str, component: str) -> dict[str, str]:
    path = ROOT / source_artifact
    if not path.exists():
        return {}
    rows = read_csv(path)
    for row in rows:
        if row.get("component") == component:
            return row
    base = base_component(component)
    for row in rows:
        if row.get("component") == base:
            return row
    return rows[0] if len(rows) == 1 else {}


def ncu_acceptance_counts(path: Path, required: list[str]) -> tuple[int, dict[str, int]]:
    if not path.exists():
        return 0, {name: 0 for name in required}
    counts: Counter[str] = Counter()
    for row in read_csv(path):
        if row.get("acceptance") == "accepted":
            counts[row.get("component_candidate", "")] += 1
    return sum(counts[name] for name in required), {name: counts[name] for name in required}


def confidence_ok(confidence: str, minimum: str = "medium") -> bool:
    return CONFIDENCE_ORDER.get(confidence, 0) >= CONFIDENCE_ORDER[minimum]


def classify(
    *,
    reporting_status: str,
    confidence: str,
    power_counts: Counter[str],
    scopes: Counter[str],
    power_state_counts: Counter[str],
    reliability: dict[str, str],
    ncu_required: list[str],
    ncu_accepted_by_component: dict[str, int],
    ncu_denominator_rows: int,
    component: str,
) -> tuple[str, list[str], str]:
    risks: list[str] = []

    if power_counts.get("reject", 0):
        risks.append("power_api_reject_rows")
    if power_counts.get("provisional", 0):
        risks.append("power_api_provisional_rows")
    if power_counts.get("final_candidate", 0) <= 0:
        risks.append("no_power_final_rows")
    if "gpu_device_total_energy_counter" not in scopes:
        risks.append("missing_gpu_device_total_energy_scope")
    if power_state_counts.get("reject", 0):
        risks.append(f"power_state_reject_rows:{power_state_counts['reject']}")
    elif power_state_counts.get("caution", 0):
        risks.append(f"power_state_caution_rows:{power_state_counts['caution']}")

    missing_ncu = [
        name for name in ncu_required if ncu_accepted_by_component.get(name, 0) <= 0
    ]
    if missing_ncu:
        risks.append("missing_ncu_acceptance:" + ",".join(missing_ncu))
    if component != "tensor_mma_increment" and ncu_denominator_rows <= 0:
        risks.append("missing_ncu_denominator_rows")

    reliability_status = reliability.get("status", "")
    reliability_cautions = reliability.get("cautions", "")
    reliability_reasons = reliability.get("reasons", "")
    if reliability_reasons:
        risks.append("reliability_reject_reason:" + reliability_reasons)
    if reliability_status in {"accepted_with_caution", "accepted_low_stability"}:
        risks.append("reliability_" + reliability_status)
    if reliability_cautions:
        risks.append("reliability_cautions:" + reliability_cautions)
    if not reliability_status:
        risks.append("missing_reliability_audit")

    if not confidence_ok(confidence):
        risks.append("low_or_missing_confidence")

    if component == "dram_cg_stream_path":
        risks.append("dram_sanity_not_physical_device_energy")

    is_auxiliary = "auxiliary" in reporting_status
    if is_auxiliary:
        risks.append("auxiliary_not_primary")

    if any(risk.startswith("power_api_reject") for risk in risks):
        level = "reject"
        next_action = "rerun_energy_with_valid_power_api"
    elif component == "dram_cg_stream_path":
        level = "sanity_only"
        next_action = "report_only_as_hierarchy_sanity"
    elif is_auxiliary:
        level = "auxiliary_support"
        next_action = "use_to_bound_method_sensitivity_not_as_single_final"
    elif risks:
        level = "accepted_with_caution"
        next_action = "targeted_rerun_or_report_cautions"
    elif base_component(component) == "tensor_mma_increment":
        level = "strong_candidate"
        next_action = "use_with_auxiliary_range_not_as_single_final"
    else:
        level = "strong_candidate"
        next_action = "keep_as_current_primary_candidate"

    return level, risks, next_action


def build_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    current_rows = read_csv(args.current_csv)
    ncu_path = ROOT / args.ncu_acceptance_csv
    out_rows: list[dict[str, str]] = []

    for row in current_rows:
        component = base_component(row["component"])
        family = artifact_family(row["source_artifact"])
        artifacts = default_artifacts(family)
        power_path = artifacts.get("power")
        power_rows = read_csv(power_path) if power_path and power_path.exists() else []
        power_counts = count_column(power_rows, "status")
        scopes = count_column(power_rows, "measurement_scope")
        power_state_path = artifacts.get("power_state")
        power_state_rows = read_csv(power_state_path) if power_state_path and power_state_path.exists() else []
        power_state_rows = filter_power_state_rows(power_state_rows, component)
        power_state_counts = count_column(power_state_rows, "status")
        reliability = reliability_for(artifacts.get("reliability"), component)
        source_summary = source_summary_row(row["source_artifact"], component)
        ncu_required = NCU_REQUIREMENTS.get(component, [])
        ncu_accepted_rows, ncu_by_component = ncu_acceptance_counts(ncu_path, ncu_required)
        ncu_denominator_rows = int(float(source_summary.get("ncu_denominator_rows", "0") or 0))

        evidence_level, risks, next_action = classify(
            reporting_status=row["status"],
            confidence=row["confidence"],
            power_counts=power_counts,
            scopes=scopes,
            power_state_counts=power_state_counts,
            reliability=reliability,
            ncu_required=ncu_required,
            ncu_accepted_by_component=ncu_by_component,
            ncu_denominator_rows=ncu_denominator_rows,
            component=component,
        )

        out_rows.append(
            {
                "component": row["component"],
                "path": row["path"],
                "median": row["median"],
                "unit": row["unit"],
                "ci": f"{row.get('ci_low', '')}-{row.get('ci_high', '')}",
                "rows": row["rows"],
                "confidence": row["confidence"],
                "reporting_status": row["status"],
                "evidence_level": evidence_level,
                "power_final_rows": str(power_counts.get("final_candidate", 0)),
                "power_provisional_rows": str(power_counts.get("provisional", 0)),
                "power_reject_rows": str(power_counts.get("reject", 0)),
                "measurement_scopes": compact_counts(scopes),
                "power_state_status_counts": compact_counts(power_state_counts),
                "ncu_required": ",".join(ncu_required),
                "ncu_accepted_rows": str(ncu_accepted_rows),
                "ncu_denominator_rows": str(ncu_denominator_rows),
                "reliability_status": reliability.get("status", ""),
                "reliability_cautions": reliability.get("cautions", ""),
                "reliability_reasons": reliability.get("reasons", ""),
                "risks": ";".join(risks),
                "next_action": next_action,
                "source_artifact": row["source_artifact"],
            }
        )
    return out_rows


def write_markdown(path: str | Path, rows: list[dict[str, str]], args: argparse.Namespace) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# RTX 3090 Component Evidence Matrix\n\n")
        f.write(
            "이 문서는 current reporting coefficient가 어떤 증거를 통과했는지 "
            "한 표로 묶은 감사 기록이다. Power API 해석은 "
            "`docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다.\n\n"
        )
        f.write("| input | path |\n|---|---|\n")
        f.write(f"| current reporting CSV | `{args.current_csv}` |\n")
        f.write(f"| NCU acceptance CSV | `{args.ncu_acceptance_csv}` |\n\n")

        f.write("## Evidence Summary\n\n")
        f.write(
            "| component | median | unit | evidence level | power final/prov/reject | "
            "scope | NCU accepted | NCU denom rows | reliability | risks |\n"
        )
        f.write("|---|---:|---|---|---:|---|---:|---:|---|---|\n")
        for row in rows:
            power = (
                f"{row['power_final_rows']}/"
                f"{row['power_provisional_rows']}/"
                f"{row['power_reject_rows']}"
            )
            f.write(
                f"| `{row['component']}` | {row['median']} | {row['unit']} | "
                f"`{row['evidence_level']}` | {power} | `{row['measurement_scopes']}` | "
                f"{row['ncu_accepted_rows']} | {row['ncu_denominator_rows']} | "
                f"`{row['reliability_status'] or 'missing'}` | "
                f"{row['risks'] or '-'} |\n"
            )

        f.write("\n## Interpretation\n\n")
        f.write(
            "- `strong_candidate`: power API, NCU path, reliability, positivity, "
            "and confidence gates are all clean for the current artifact.\n"
        )
        f.write(
            "- `accepted_with_caution`: core gates pass, but invalid detail rows, "
            "medium confidence, or other cautions remain.\n"
        )
        f.write(
            "- `auxiliary_support`: useful to bound method sensitivity, but not a "
            "standalone primary coefficient.\n"
        )
        f.write(
            "- `sanity_only`: hierarchy sanity result. Do not report as physical "
            "DRAM/HBM device energy.\n\n"
        )

        f.write("## Required Follow-up\n\n")
        f.write("| component | next action |\n|---|---|\n")
        for row in rows:
            f.write(f"| `{row['component']}` | {row['next_action']} |\n")

        f.write("\n## Scope Notes\n\n")
        f.write(
            "- All rows here must use GPU/device total energy counter scope for "
            "final reporting. Hopper module power and GPU memory power are "
            "preflight metadata only.\n"
        )
        f.write(
            "- A100/V100/H100 are not validated by this RTX 3090 evidence matrix; "
            "they require platform-specific reruns with their own power API and "
            "NCU evidence.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--current-csv",
        default="results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv",
    )
    parser.add_argument(
        "--ncu-acceptance-csv",
        default="results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv",
    )
    parser.add_argument(
        "--out-csv",
        default="results/summary/rtx3090_current_reporting_evidence_matrix_20260708.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/rtx3090_current_reporting_evidence_matrix_20260708.md",
    )
    args = parser.parse_args()

    rows = build_rows(args)
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args)
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    levels = Counter(row["evidence_level"] for row in rows)
    print("evidence levels:", ", ".join(f"{k}={levels[k]}" for k in sorted(levels)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
