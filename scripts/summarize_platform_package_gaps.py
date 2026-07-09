#!/usr/bin/env python3
"""Summarize missing/failing external platform result package checks.

This is a human-facing intake helper. It reads the CSV produced by
`audit_platform_result_package.py` and turns fail/missing rows into a concise
gap report with likely cause and corrective action. It does not validate raw
measurements by itself; the package audit remains the authoritative gate.
"""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path


FINAL_NUMERATOR_POLICY = (
    "nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter"
)

PROFILE_POWER_SEMANTICS = {
    "rtx3090": "one_sec_average",
    "v100": "instant",
    "a100": "instant",
    "h100": "one_sec_average",
}

PROFILE_DEFAULT_ACTIVE_SM = {
    "rtx3090": 82,
    "v100": 80,
    "a100": 108,
    "h100": 132,
}

PROFILE_CUDA_ARCH = {
    "rtx3090": "86",
    "v100": "70",
    "a100": "80",
    "h100": "90",
}

PROFILE_DEFAULT_BINARY = {
    "rtx3090": "./build/a100_fp16_energy_v2",
    "v100": "./build-v100/a100_fp16_energy_v2",
    "a100": "./build-a100/a100_fp16_energy_v2",
    "h100": "./build-h100/a100_fp16_energy_v2",
}

STAGE_ORDER = {
    "command package": 10,
    "preflight": 20,
    "raw energy": 30,
    "power API": 40,
    "power state": 50,
    "NCU summary": 60,
    "NCU path acceptance": 70,
    "matched-control": 80,
    "component reliability": 90,
    "instability diagnosis": 95,
    "strict summary": 100,
    "strict summary audit": 110,
    "other": 999,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile",
        "stage",
        "severity",
        "status",
        "check",
        "issue",
        "evidence",
        "likely_cause",
        "corrective_action",
        "power_matrix_relevance",
        "next_command",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(
    path: Path,
    rows: list[dict[str, str]],
    *,
    profile: str,
    audit_csv: Path,
    manifest_csv: Path | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["severity"]] = counts.get(row["severity"], 0) + 1

    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {profile.upper()} Platform Package Gap Report\n\n")
        f.write("This report explains open rows from `audit_platform_result_package.py`.\n")
        f.write("It is not a replacement for the package audit; it is a debugging guide.\n\n")
        f.write("| item | value |\n|---|---|\n")
        f.write(f"| package audit CSV | `{audit_csv}` |\n")
        f.write(
            f"| result manifest CSV | `{manifest_csv if manifest_csv else 'not provided'}` |\n"
        )
        f.write(f"| expected power semantics | `{PROFILE_POWER_SEMANTICS[profile]}` |\n")
        f.write(f"| final numerator policy | `{FINAL_NUMERATOR_POLICY}` |\n")
        f.write(f"| open gaps | `{len(rows)}` |\n\n")

        f.write("## Severity Counts\n\n")
        f.write("| severity | gaps |\n|---|---:|\n")
        for severity in ("blocker", "high", "medium", "low"):
            if counts.get(severity, 0):
                f.write(f"| `{severity}` | {counts[severity]} |\n")
        if not rows:
            f.write("| `none` | 0 |\n")
        f.write("\n")

        if rows:
            f.write("## Next Actions\n\n")
            f.write(
                "| stage | severity | status | issue | evidence | corrective action | next command |\n"
                "|---|---|---|---|---|---|---|\n"
            )
            for row in rows:
                f.write(
                    f"| {row['stage']} | `{row['severity']}` | `{row['status']}` | "
                    f"{row['issue']} | `{row['evidence']}` | {row['corrective_action']} | "
                    f"`{row['next_command']}` |\n"
                )
            f.write("\n")

        f.write("## Power API Interpretation\n\n")
        f.write(
            "A package can only produce final component coefficients when the energy "
            "rows satisfy the power measurement matrix policy: "
            f"`{FINAL_NUMERATOR_POLICY}` and the profile-specific "
            f"`nvml_power_usage_semantics={PROFILE_POWER_SEMANTICS[profile]}`. "
            "`GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power "
            "remain metadata or fallback/provisional evidence.\n\n"
        )
        f.write("## Re-run Intake\n\n")
        f.write("```bash\n")
        f.write(
            "python3 scripts/audit_platform_result_package.py \\\n"
            f"  --target-profile {profile} \\\n"
            "  --tag <YYYYMMDD> \\\n"
            f"  --expected-active-sm {PROFILE_DEFAULT_ACTIVE_SM[profile]} \\\n"
            f"  --out-csv results/summary/{profile}_platform_result_package_audit_<YYYYMMDD>.csv \\\n"
            f"  --out-md results/summary/{profile}_platform_result_package_audit_<YYYYMMDD>.md \\\n"
            "  --fail-on-incomplete\n"
        )
        f.write("```\n")


def manifest_lookup(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    rows = read_csv(path)
    return {row.get("expected_path", ""): row for row in rows}


def stage_for(row: dict[str, str]) -> str:
    area = row.get("area", "")
    check = row.get("check", "")
    if area == "files":
        if check.startswith("command_"):
            return "command package"
        if check.startswith("preflight"):
            return "preflight"
        if check.startswith("raw"):
            return "raw energy"
        if check.startswith("power_api"):
            return "power API"
        if check.startswith("power_state"):
            return "power state"
        if check.startswith("ncu_summary"):
            return "NCU summary"
        if check.startswith("ncu_acceptance"):
            return "NCU path acceptance"
        if check.startswith("matched_"):
            return "matched-control"
        if check.startswith("reliability"):
            return "component reliability"
        if check.startswith("instability"):
            return "instability diagnosis"
        if check.startswith("strict_summary"):
            return "strict summary"
        if check.startswith("strict_audit"):
            return "strict summary audit"
    if area == "preflight":
        return "preflight"
    if area == "raw":
        return "raw energy"
    if area == "power":
        return "power API" if "api" in check else "power state"
    if area == "ncu":
        return "NCU summary" if "schema" in check else "NCU path acceptance"
    if area == "analysis":
        return "component reliability" if "reliability" in check else "matched-control"
    if area == "summary":
        return "strict summary audit" if "audit" in check else "strict summary"
    return "other"


def severity_for(row: dict[str, str], stage: str) -> str:
    status = row.get("status", "")
    actual = row.get("actual", "")
    check = row.get("check", "")
    if status == "missing":
        return "blocker"
    if status == "fail":
        if (
            stage in {"raw energy", "power API", "matched-control", "strict summary"}
            or "energy_source" in actual
            or "scope=" in actual
            or "semantics=" in actual
            or check in {"strict_summary_audit_clean", "strict_summary_policy"}
        ):
            return "high"
        return "medium"
    if status == "warning":
        return "medium"
    return "low"


def likely_cause_for(row: dict[str, str], stage: str) -> str:
    actual = row.get("actual", "")
    if row.get("status") == "missing":
        if "missing=" in actual or actual == "missing":
            return "Required artifact has not been copied back or was not generated on the target node."
        if "no_raw_rows_read" in actual:
            return "Raw energy CSVs are absent or empty, so no measurement rows were available."
    if stage == "preflight":
        if "driver_version" in actual or "`uuid`" in actual or "power_query_fields" in actual:
            return (
                "Preflight is present, but it does not record basic GPU identity "
                "and driver metadata needed for cross-platform reproducibility."
            )
        if "module_power_query_rc" in actual or "power_detail_query_rc" in actual:
            return (
                "Preflight did not record power-scope metadata. This is especially "
                "important on H100/HGX where GPU, module, and memory power scopes "
                "can coexist."
            )
        if "chip_supported" in actual or "list_chips_rc" in actual or "query_metrics_ok" in actual:
            return (
                "Preflight does not prove that Nsight Compute supports the target "
                "GPU chip and can query the required metrics."
            )
        return "The target node preflight does not prove the expected GPU profile, NCU support, power scope, or dry-run metadata."
    if stage == "raw energy":
        if "active_SM" in actual or "sm_count" in actual:
            return "The run likely used the wrong active-SM setting or a MIG/SKU runtime SM count not reflected in the plan."
        if "energy_source" in actual or "integration" in actual or "scope=" in actual:
            return "The raw rows do not satisfy the final numerator policy from the power measurement matrix."
        if "semantics" in actual:
            return "The raw rows carry the wrong profile-specific GetPowerUsage semantics."
        if (
            "delta_E_J" in actual
            or "E_after_not_greater_than_E_before" in actual
            or "elapsed_s" in actual
            or "ITER=" in actual
        ):
            return (
                "The raw energy row has invalid row-level counter evidence: "
                "elapsed time, iteration count, or total-energy counter delta is "
                "missing, nonpositive, or internally inconsistent."
            )
        return "Raw rows do not match the target profile, architecture capacity, or power policy."
    if stage == "power API":
        return "Power API audit did not classify every row as final_candidate with total-energy GPU/device scope."
    if stage == "power state":
        return "Power-state audit found outliers or coefficient-ineligible rows."
    if stage == "NCU summary":
        if "no_path_sanity_pass" in actual:
            return (
                "NCU summary has the required columns, but no row for a representative "
                "mode proves the intended hit-rate/path behavior."
            )
        return "NCU summary is missing required cache hit/access/byte/stall counters, modes, or factor coverage."
    if stage == "NCU path acceptance":
        if "missing_columns" in actual:
            return (
                "NCU acceptance CSV is present, but it lacks counter evidence "
                "columns needed to trust accepted component candidates."
            )
        if "path_evidence_failed" in actual:
            return (
                "One or more rows are marked accepted, but their hit-rate/byte "
                "evidence does not prove the intended component path."
            )
        return "NCU did not accept one or more intended Tensor/shared/L1/L2 component paths."
    if stage == "matched-control":
        return "Treatment-control pairing lacks exact NCU denominators, positive delta_E, or matching power scope."
    if stage == "component reliability":
        return "The combined power/NCU/matched-control evidence did not accept all required components."
    if stage == "instability diagnosis":
        return "The weak-signal, negative-delta, or noisy-row root-cause artifact is missing or incomplete."
    if stage == "strict summary":
        return "The reporting summary includes unaccepted, nonpositive, out-of-range, or hierarchy-inconsistent coefficients."
    if stage == "strict summary audit":
        return "The strict audit is stale, missing required hierarchy/plausibility checks, or contains fail/warning rows."
    return "Inspect the package audit row for details."


def corrective_action_for(row: dict[str, str], stage: str, profile: str) -> str:
    semantics = PROFILE_POWER_SEMANTICS[profile]
    if row.get("status") == "missing":
        if stage == "command package":
            return "Regenerate the finalplan command package with `scripts/plan_platform_component_experiment.py`."
        if stage == "preflight":
            return (
                "Run strict preflight on the target node with the explicit profile, "
                "expected active SM count, binary path, and NCU path, then copy the "
                "markdown report back."
            )
        if stage == "raw energy":
            return "Run the generated command shell on the target GPU node and copy all tensor/shared/L1/L2/DRAM raw CSV files."
        if stage == "NCU summary":
            return "Run the NCU sidecar on the target GPU and summarize cache/path counters before copying results back."
        if stage == "strict summary audit":
            return "Run `scripts/audit_strict_component_summary.py --fail-on-fail` after building the strict summary."
        return "Generate or copy the missing artifact listed in the package audit and manifest."
    if stage == "preflight":
        actual = row.get("actual", "")
        if "driver_version" in actual or "`uuid`" in actual or "power_query_fields" in actual:
            return (
                "Rerun `scripts/preflight_gpu_support.py` on the target node and "
                "keep the GPU UUID, driver version, query field set, and dry-run "
                "profile output with the result package."
            )
        if "module_power_query_rc" in actual or "power_detail_query_rc" in actual:
            return (
                "Rerun preflight with `nvidia-smi` available and preserve the "
                "`## Power Scope` section; module/memory power remains metadata "
                "but must be documented."
            )
        if "chip_supported" in actual or "list_chips_rc" in actual or "query_metrics_ok" in actual:
            return (
                "Use an Nsight Compute CLI whose `--list-chips` and "
                "`--query-metrics --chips <chip>` succeed for the target profile."
            )
        return (
            "Rerun preflight with the intended explicit `--target-profile "
            f"{profile} --strict`, correct `--active-sm`, binary path, and NCU path."
        )
    if stage == "raw energy":
        if (
            "delta_E_J" in row.get("actual", "")
            or "E_after_not_greater_than_E_before" in row.get("actual", "")
            or "elapsed_s" in row.get("actual", "")
            or "ITER=" in row.get("actual", "")
        ):
            return (
                "Rerun the energy sweep and keep rows only when `elapsed_s > 0`, "
                "`ITER > 0`, `E_after_mJ > E_before_mJ`, and "
                "`delta_E_J == (E_after_mJ - E_before_mJ) / 1000`."
            )
        return (
            "Rerun energy sweep with the correct target profile and require "
            f"`nvml_power_usage_semantics={semantics}` plus explicit `measurement_scope`."
        )
    if stage == "power API":
        return (
            "Rerun `scripts/audit_power_api_measurements.py` with "
            "`--fail-on-reject --fail-on-provisional --require-explicit-measurement-scope`; "
            "if it still fails, rerun the energy measurement instead of using fallback power."
        )
    if stage == "power state":
        return "Exclude rejected rows before pairing or rerun the unstable conditions with longer seconds/repeats."
    if stage == "NCU summary":
        if "no_path_sanity_pass" in row.get("actual", ""):
            return (
                "Rerun NCU with platform-specific W_SM, blocks/SM, active SM, "
                "reuse_factor/load_repeat, then confirm L1 hit, L2 hit, and DRAM "
                "dominance before accepting the path."
            )
        return "Rerun `scripts/run_ncu_validation.sh` and `scripts/summarize_ncu_cache_metrics.py` with required factor sweeps and cache/access metrics."
    if stage == "NCU path acceptance":
        if "missing_columns" in row.get("actual", ""):
            return (
                "Regenerate the acceptance CSV with current "
                "`scripts/analyze_ncu_path_acceptance.py`, not by hand-editing "
                "accepted candidates."
            )
        if "path_evidence_failed" in row.get("actual", ""):
            return (
                "Rerun NCU and path acceptance for the failed modes; inspect L1 hit, "
                "L2 hit, shared/L1/L2/DRAM bytes, and Tensor HMMA counters before "
                "using the coefficient."
            )
        return "Rerun NCU for the rejected modes with platform-specific W_SM, blocks/SM, active SM, reuse_factor, and load_repeat."
    if stage == "matched-control":
        return "Rerun `scripts/analyze_matched_control_energy.py` with `--require-ncu-denominator --require-total-energy --expected-power-semantics`."
    if stage == "component reliability":
        return "Rerun targeted component conditions or keep weak/rejected components out of the strict summary."
    if stage == "instability diagnosis":
        return "Run `scripts/audit_matched_control_instability.py` after matched-control analysis and copy the artifact back."
    if stage == "strict summary":
        return "Rebuild `build_strict_component_summary.py` only from accepted reliability evidence, then rerun strict audit."
    if stage == "strict summary audit":
        return "Rerun the current `audit_strict_component_summary.py`; stale audits missing hierarchy/plausibility checks are invalid."
    return row.get("action", "Inspect the package audit and rerun the failed stage.")


def power_relevance_for(row: dict[str, str], stage: str) -> str:
    actual = row.get("actual", "")
    if stage in {"raw energy", "power API", "matched-control", "strict summary"}:
        return (
            "Directly affects final pJ numerator. Required policy: "
            + FINAL_NUMERATOR_POLICY
        )
    if "semantics" in actual or "scope" in actual or "energy_source" in actual:
        return "Power measurement matrix mismatch; coefficient must be rejected until fixed."
    if stage in {"NCU summary", "NCU path acceptance"}:
        return "Does not provide energy numerator, but validates FLOP/byte denominator and path attribution."
    return "Indirect quality or traceability gate."


def next_command_for(stage: str, profile: str, tag: str) -> str:
    binary = PROFILE_DEFAULT_BINARY[profile]
    if stage == "command package":
        return (
            "python3 scripts/plan_platform_component_experiment.py "
            f"--target-profile {profile} --tag {tag} --ncu \"$(command -v ncu || echo ncu)\""
        )
    if stage == "preflight":
        return (
            "python3 scripts/preflight_gpu_support.py "
            f"--gpu 0 --target-profile {profile} --strict "
            f"--active-sm {PROFILE_DEFAULT_ACTIVE_SM[profile]} "
            f"--binary {binary} --ncu \"$(command -v ncu || echo ncu)\" "
            f"--out results/summary/{profile}_component_finalplan_{tag}_preflight.md"
        )
    if stage == "raw energy":
        return f"bash results/summary/{profile}_component_finalplan_{tag}_commands.sh"
    if stage == "power API":
        return "python3 scripts/audit_power_api_measurements.py ... --fail-on-provisional --require-explicit-measurement-scope"
    if stage == "power state":
        return "python3 scripts/audit_power_state_stability.py ..."
    if stage == "NCU summary":
        return "bash scripts/run_ncu_validation.sh && python3 scripts/summarize_ncu_cache_metrics.py ..."
    if stage == "NCU path acceptance":
        return "python3 scripts/analyze_ncu_path_acceptance.py ..."
    if stage == "matched-control":
        return "python3 scripts/analyze_matched_control_energy.py ... --require-ncu-denominator --require-total-energy"
    if stage == "component reliability":
        return "python3 scripts/audit_component_reliability.py ..."
    if stage == "instability diagnosis":
        return "python3 scripts/audit_matched_control_instability.py ..."
    if stage == "strict summary":
        return "python3 scripts/build_strict_component_summary.py ..."
    if stage == "strict summary audit":
        return "python3 scripts/audit_strict_component_summary.py ... --fail-on-fail"
    return ""


def build_gap_rows(
    audit_rows: list[dict[str, str]],
    *,
    profile: str,
    tag: str,
    manifest: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for audit_row in audit_rows:
        if audit_row.get("status") == "pass":
            continue
        stage = stage_for(audit_row)
        evidence = audit_row.get("evidence", "")
        manifest_groups = []
        for path in evidence.split(";"):
            path = path.strip()
            if path and path in manifest:
                manifest_groups.append(manifest[path].get("artifact_group", ""))
        evidence_suffix = ""
        if manifest_groups:
            evidence_suffix = " (" + ",".join(sorted(set(manifest_groups))) + ")"
        rows.append(
            {
                "profile": profile,
                "stage": stage,
                "severity": severity_for(audit_row, stage),
                "status": audit_row.get("status", ""),
                "check": audit_row.get("check", ""),
                "issue": audit_row.get("actual", ""),
                "evidence": evidence + evidence_suffix,
                "likely_cause": likely_cause_for(audit_row, stage),
                "corrective_action": corrective_action_for(audit_row, stage, profile),
                "power_matrix_relevance": power_relevance_for(audit_row, stage),
                "next_command": next_command_for(stage, profile, tag),
            }
        )
    rows.sort(
        key=lambda row: (
            STAGE_ORDER.get(row["stage"], 999),
            {"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(row["severity"], 9),
            row["check"],
        )
    )
    return rows


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        audit = root / "audit.csv"
        manifest = root / "manifest.csv"
        write_csv = csv.DictWriter
        with audit.open("w", newline="", encoding="utf-8") as f:
            writer = write_csv(
                f,
                fieldnames=[
                    "area",
                    "check",
                    "status",
                    "expected",
                    "actual",
                    "evidence",
                    "action",
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "area": "files",
                    "check": "raw_present",
                    "status": "missing",
                    "expected": "all expected files exist",
                    "actual": "missing=results/raw/a100_component_finalplan_test_tensor.csv",
                    "evidence": "results/raw/a100_component_finalplan_test_tensor.csv",
                    "action": "copy missing files",
                }
            )
            writer.writerow(
                {
                    "area": "preflight",
                    "check": "preflight_power_scope_policy",
                    "status": "fail",
                    "expected": "driver and power metadata",
                    "actual": "missing=- `driver_version`:;- `module_power_query_rc`:",
                    "evidence": "results/summary/a100_component_finalplan_test_preflight.md",
                    "action": "rerun preflight",
                }
            )
            writer.writerow(
                {
                    "area": "power",
                    "check": "power_api_audit_policy",
                    "status": "fail",
                    "expected": "all rows final_candidate",
                    "actual": "row2:energy_source=legacy_get_power_usage_integral",
                    "evidence": "results/summary/a100_power_api.csv",
                    "action": "rerun power API audit",
                }
            )
            writer.writerow(
                {
                    "area": "raw",
                    "check": "raw_energy_power_policy",
                    "status": "fail",
                    "expected": "positive counter delta",
                    "actual": "results/raw/a100_component_finalplan_test_tensor.csv:2:delta_E_J=0",
                    "evidence": "results/raw/a100_component_finalplan_test_tensor.csv",
                    "action": "rerun raw energy sweep",
                }
            )
            writer.writerow(
                {
                    "area": "ncu",
                    "check": "ncu_cache_counter_schema",
                    "status": "fail",
                    "expected": "cache/path counters",
                    "actual": "global_l1_load_only:no_path_sanity_pass",
                    "evidence": "results/ncu/a100/ncu_cache_validation_summary.csv",
                    "action": "rerun NCU",
                }
            )
            writer.writerow(
                {
                    "area": "ncu",
                    "check": "ncu_path_acceptance",
                    "status": "fail",
                    "expected": "accepted candidates with evidence",
                    "actual": "global_l1_load_only:global_l1_hit_path:path_evidence_failed",
                    "evidence": "results/summary/a100_ncu_acceptance.csv",
                    "action": "rerun path acceptance",
                }
            )
        with manifest.open("w", newline="", encoding="utf-8") as f:
            writer = write_csv(
                f,
                fieldnames=["expected_path", "artifact_group"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "expected_path": "results/raw/a100_component_finalplan_test_tensor.csv",
                    "artifact_group": "raw energy CSVs",
                }
            )
        rows = build_gap_rows(
            read_csv(audit),
            profile="a100",
            tag="test",
            manifest=manifest_lookup(manifest),
        )
        assert len(rows) == 6, rows
        assert rows[0]["stage"] == "preflight", rows
        assert "driver metadata" in rows[0]["likely_cause"], rows
        assert "--target-profile a100 --strict" in rows[0]["next_command"], rows
        assert "--binary ./build-a100/a100_fp16_energy_v2" in rows[0]["next_command"], rows
        assert "a100_component_finalplan_test_preflight.md" in rows[0]["next_command"], rows
        assert rows[1]["stage"] == "raw energy", rows
        assert rows[1]["severity"] == "blocker", rows
        assert "a100_component_finalplan_test_commands.sh" in rows[1]["next_command"], rows
        assert rows[2]["stage"] == "raw energy", rows
        assert "row-level counter evidence" in rows[2]["likely_cause"], rows
        assert rows[3]["stage"] == "power API", rows
        assert rows[3]["severity"] == "high", rows
        assert FINAL_NUMERATOR_POLICY in rows[3]["power_matrix_relevance"]
        assert rows[4]["stage"] == "NCU summary", rows
        assert "hit-rate/path" in rows[4]["likely_cause"], rows
        assert rows[5]["stage"] == "NCU path acceptance", rows
        assert "marked accepted" in rows[5]["likely_cause"], rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-csv")
    parser.add_argument("--manifest-csv")
    parser.add_argument("--target-profile", choices=sorted(PROFILE_POWER_SEMANTICS))
    parser.add_argument("--tag", default="20260708")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--fail-on-open-gaps", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("platform package gap summarizer self-test passed")
        return 0

    if not args.audit_csv:
        parser.error("--audit-csv is required unless --self-test is used")
    if not args.target_profile:
        parser.error("--target-profile is required unless --self-test is used")

    audit_path = Path(args.audit_csv)
    manifest_path = Path(args.manifest_csv) if args.manifest_csv else None
    rows = build_gap_rows(
        read_csv(audit_path),
        profile=args.target_profile,
        tag=args.tag,
        manifest=manifest_lookup(manifest_path),
    )
    out_csv = Path(
        args.out_csv
        or audit_path.with_name(audit_path.stem.replace("_audit", "_gaps") + ".csv")
    )
    out_md = Path(
        args.out_md
        or audit_path.with_name(audit_path.stem.replace("_audit", "_gaps") + ".md")
    )
    write_csv(out_csv, rows)
    write_md(
        out_md,
        rows,
        profile=args.target_profile,
        audit_csv=audit_path,
        manifest_csv=manifest_path,
    )
    print(f"platform package gaps={len(rows)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_md}")
    if args.fail_on_open_gaps and rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
