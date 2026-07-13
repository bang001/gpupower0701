#!/usr/bin/env python3
"""Build a cross-platform intake dashboard from package audits and gap reports.

The dashboard is intentionally a summary layer. It does not approve component
coefficients; `audit_platform_result_package.py`, strict summary audits, and the
goal readiness audit remain the gates. This script makes the current state easy
to inspect across RTX 3090, V100, A100, and H100.
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

DEFAULT_PROFILES = ("rtx3090", "v100", "a100", "h100")

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
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def severity_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        severity = row.get("severity", "")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def count_value(rows: list[dict[str, str]], column: str, value: str) -> int:
    return sum(1 for row in rows if row.get(column, "") == value)


def strict_summary_path(profile: str, tag: str) -> Path:
    return Path(f"results/summary/{profile}_strict_scope_fresh_ncu_component_coefficients_{tag}.csv")


def strict_audit_path(profile: str, tag: str) -> Path:
    return Path(
        f"results/summary/{profile}_strict_scope_fresh_ncu_component_summary_audit_{tag}.csv"
    )


def package_audit_path(profile: str, tag: str) -> Path:
    return Path(f"results/summary/{profile}_platform_result_package_audit_{tag}.csv")


def gap_report_path(profile: str, tag: str) -> Path:
    return Path(f"results/summary/{profile}_platform_result_package_gaps_{tag}.csv")


def manifest_path(profile: str, tag: str) -> Path:
    return Path(f"results/summary/{profile}_component_finalplan_{tag}_result_manifest.csv")


def command_plan_path(profile: str, tag: str) -> Path:
    return Path(f"results/summary/{profile}_component_finalplan_{tag}_command_plan.md")


def goal_readiness_path(tag: str) -> Path:
    return Path(f"results/summary/component_energy_goal_readiness_audit_{tag}.csv")


def goal_readiness_status(repo: Path, path: Path) -> dict[str, str]:
    resolved_path = path if path.is_absolute() else repo / path
    rows = read_csv(resolved_path)
    counts = status_counts(rows)
    if not resolved_path.exists():
        status = "missing_audit"
    elif counts.get("fail", 0):
        status = "fail"
    elif counts.get("missing", 0):
        status = "incomplete"
    elif counts.get("warning", 0):
        status = "warning"
    else:
        status = "pass"
    return {
        "goal_readiness_audit": str(path),
        "goal_readiness_status": status,
        "goal_readiness_pass": str(counts.get("pass", 0)),
        "goal_readiness_missing": str(counts.get("missing", 0)),
        "goal_readiness_fail": str(counts.get("fail", 0)),
        "goal_readiness_warning": str(counts.get("warning", 0)),
    }


def package_status(counts: dict[str, int], exists: bool) -> str:
    if not exists:
        return "missing_audit"
    if counts.get("fail", 0):
        return "fail"
    if counts.get("missing", 0):
        return "missing_artifacts"
    if counts.get("warning", 0):
        return "warning"
    return "pass"


def strict_status(summary_rows: list[dict[str, str]], audit_rows: list[dict[str, str]]) -> str:
    if not summary_rows:
        return "missing_summary"
    if not audit_rows:
        return "missing_audit"
    counts = status_counts(audit_rows)
    if counts.get("fail", 0):
        return "audit_fail"
    if counts.get("warning", 0):
        return "audit_warning"
    return "pass"


def accepted_component_count(summary_rows: list[dict[str, str]]) -> int:
    return sum(
        1
        for row in summary_rows
        if row.get("reliability_status", "") == "accepted"
        and row.get("energy_source", "") == "nvml_total_energy"
        and row.get("energy_integration_method", "") == "total_energy_mj_delta"
        and row.get("measurement_scope", "") == "gpu_device_total_energy_counter"
    )


def first_open_gap(gap_rows: list[dict[str, str]]) -> dict[str, str]:
    if not gap_rows:
        return {}
    severity_order = {"blocker": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        gap_rows,
        key=lambda row: (
            severity_order.get(row.get("severity", ""), 99),
            STAGE_ORDER.get(row.get("stage", ""), 999),
            row.get("check", ""),
        ),
    )[0]


def build_rows(
    repo: Path,
    profiles: list[str],
    tag: str,
    *,
    goal_readiness_csv: Path | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    goal_status = goal_readiness_status(
        repo,
        goal_readiness_csv or goal_readiness_path(tag),
    )
    for profile in profiles:
        package_path = repo / package_audit_path(profile, tag)
        gaps_path = repo / gap_report_path(profile, tag)
        summary_path = repo / strict_summary_path(profile, tag)
        summary_audit_path = repo / strict_audit_path(profile, tag)
        package_rows = read_csv(package_path)
        gap_rows = read_csv(gaps_path)
        summary_rows = read_csv(summary_path)
        summary_audit_rows = read_csv(summary_audit_path)
        package_counts = status_counts(package_rows)
        gap_counts = severity_counts(gap_rows)
        first_gap = first_open_gap(gap_rows)
        summary_status = strict_status(summary_rows, summary_audit_rows)
        pstatus = package_status(package_counts, package_path.exists())
        if profile == "rtx3090" and pstatus == "missing_audit" and summary_status == "pass":
            pstatus = "historical_local_evidence"
            summary_status = "historical_pass"
        row = {
            "profile": profile,
            "tag": tag,
            "expected_power_semantics": PROFILE_POWER_SEMANTICS[profile],
            "final_numerator_policy": FINAL_NUMERATOR_POLICY,
            "command_plan": str(command_plan_path(profile, tag)),
            "manifest": str(manifest_path(profile, tag)),
            "package_audit": str(package_audit_path(profile, tag)),
            "package_status": pstatus,
            "package_pass": str(package_counts.get("pass", 0)),
            "package_missing": str(package_counts.get("missing", 0)),
            "package_fail": str(package_counts.get("fail", 0)),
            "package_warning": str(package_counts.get("warning", 0)),
            "gap_report": str(gap_report_path(profile, tag)),
            "gap_blocker": str(gap_counts.get("blocker", 0)),
            "gap_high": str(gap_counts.get("high", 0)),
            "gap_medium": str(gap_counts.get("medium", 0)),
            "first_open_stage": first_gap.get("stage", ""),
            "first_open_issue": first_gap.get("issue", ""),
            "first_corrective_action": first_gap.get("corrective_action", ""),
            "first_next_command": first_gap.get("next_command", ""),
            "strict_summary": str(strict_summary_path(profile, tag)),
            "strict_summary_status": summary_status,
            "accepted_component_rows": str(accepted_component_count(summary_rows)),
            "strict_audit_fail": str(count_value(summary_audit_rows, "status", "fail")),
            "strict_audit_warning": str(
                count_value(summary_audit_rows, "status", "warning")
            ),
        }
        row.update(goal_status)
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile",
        "tag",
        "expected_power_semantics",
        "final_numerator_policy",
        "command_plan",
        "manifest",
        "package_audit",
        "package_status",
        "package_pass",
        "package_missing",
        "package_fail",
        "package_warning",
        "gap_report",
        "gap_blocker",
        "gap_high",
        "gap_medium",
        "first_open_stage",
        "first_open_issue",
        "first_corrective_action",
        "first_next_command",
        "strict_summary",
        "strict_summary_status",
        "accepted_component_rows",
        "strict_audit_fail",
        "strict_audit_warning",
        "goal_readiness_audit",
        "goal_readiness_status",
        "goal_readiness_pass",
        "goal_readiness_missing",
        "goal_readiness_fail",
        "goal_readiness_warning",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def row_is_complete(row: dict[str, str]) -> bool:
    return (
        row["package_status"] == "pass"
        and row["strict_summary_status"] == "pass"
    )


def write_md(path: Path, rows: list[dict[str, str]], *, tag: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    complete = [
        row
        for row in rows
        if row_is_complete(row)
    ]
    with path.open("w", encoding="utf-8") as f:
        f.write("# Platform Component Result Intake Dashboard\n\n")
        f.write(
            "This dashboard summarizes package audits and gap reports. It does not "
            "replace package audits, strict summary audits, or the goal readiness audit.\n\n"
        )
        f.write("| item | value |\n|---|---|\n")
        f.write(f"| tag | `{tag}` |\n")
        f.write(f"| final numerator policy | `{FINAL_NUMERATOR_POLICY}` |\n")
        f.write(f"| profiles passing package + strict summary | `{len(complete)}/{len(rows)}` |\n")
        if rows:
            row = rows[0]
            f.write(
                f"| goal readiness audit | `{row['goal_readiness_audit']}` |\n"
            )
            f.write(
                "| goal readiness status | "
                f"`{row['goal_readiness_status']}` "
                f"(pass={row['goal_readiness_pass']}, "
                f"missing={row['goal_readiness_missing']}, "
                f"fail={row['goal_readiness_fail']}, "
                f"warning={row['goal_readiness_warning']}) |\n"
            )
        f.write("\n")
        f.write("## Platform Status\n\n")
        f.write(
            "| profile | power semantics | package status | package pass/missing/fail | "
            "gap blockers | first open stage | strict summary | accepted components |\n"
            "|---|---|---|---:|---:|---|---|---:|\n"
        )
        for row in rows:
            f.write(
                f"| `{row['profile']}` | `{row['expected_power_semantics']}` | "
                f"`{row['package_status']}` | "
                f"{row['package_pass']}/{row['package_missing']}/{row['package_fail']} | "
                f"{row['gap_blocker']} | {row['first_open_stage'] or '-'} | "
                f"`{row['strict_summary_status']}` | {row['accepted_component_rows']} |\n"
            )
        f.write("\n## First Corrective Actions\n\n")
        f.write("| profile | first issue | corrective action | next command | gap report |\n")
        f.write("|---|---|---|---|---|\n")
        for row in rows:
            issue = row["first_open_issue"] or "none"
            action = row["first_corrective_action"] or "none"
            next_command = row["first_next_command"] or "none"
            f.write(
                f"| `{row['profile']}` | {issue} | {action} | `{next_command}` | "
                f"`{row['gap_report']}` |\n"
            )
        f.write("\n## Interpretation\n\n")
        f.write(
            "A platform is not final merely because the command package exists. External "
            "platforms need a clean package audit, a strict component summary, and a strict "
            "summary audit. RTX 3090 evidence without a current package audit is shown as "
            "`historical_local_evidence`/`historical_pass`; it is context only and never "
            "counts as a current completed platform. "
            "Power-related rows must satisfy the power measurement matrix policy: "
            f"`{FINAL_NUMERATOR_POLICY}` plus the profile-specific "
            "`nvml_power_usage_semantics`.\n"
        )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "results/summary").mkdir(parents=True)
        audit = root / package_audit_path("a100", "test")
        gaps = root / gap_report_path("a100", "test")
        summary = root / strict_summary_path("a100", "test")
        strict_audit = root / strict_audit_path("a100", "test")
        goal = root / goal_readiness_path("test")
        with audit.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["area", "check", "status", "expected", "actual", "evidence", "action"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "area": "files",
                    "check": "raw_present",
                    "status": "missing",
                    "expected": "",
                    "actual": "missing=raw.csv",
                    "evidence": "raw.csv",
                    "action": "copy raw",
                }
            )
        with gaps.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
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
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "profile": "a100",
                    "stage": "raw energy",
                    "severity": "blocker",
                    "status": "missing",
                    "check": "raw_present",
                    "issue": "missing=raw.csv",
                    "evidence": "raw.csv",
                    "likely_cause": "missing",
                    "corrective_action": "copy raw",
                    "next_command": "bash results/summary/a100_component_finalplan_test_commands.sh",
                    "power_matrix_relevance": "direct",
                }
            )
        with summary.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "component",
                    "reliability_status",
                    "energy_source",
                    "energy_integration_method",
                    "measurement_scope",
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "component": "Tensor MMA incremental",
                    "reliability_status": "accepted",
                    "energy_source": "nvml_total_energy",
                    "energy_integration_method": "total_energy_mj_delta",
                    "measurement_scope": "gpu_device_total_energy_counter",
                }
            )
        with strict_audit.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["status"], lineterminator="\n")
            writer.writeheader()
            writer.writerow({"status": "pass"})
        with goal.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["status"], lineterminator="\n")
            writer.writeheader()
            writer.writerow({"status": "pass"})
            writer.writerow({"status": "missing"})
        rows = build_rows(root, ["a100"], "test")
        assert rows[0]["package_status"] == "missing_artifacts", rows
        assert rows[0]["gap_blocker"] == "1", rows
        assert rows[0]["strict_summary_status"] == "pass", rows
        assert rows[0]["accepted_component_rows"] == "1", rows
        assert "a100_component_finalplan_test_commands.sh" in rows[0]["first_next_command"], rows
        assert rows[0]["goal_readiness_status"] == "incomplete", rows
        assert rows[0]["goal_readiness_missing"] == "1", rows

        rtx_summary = root / strict_summary_path("rtx3090", "test")
        rtx_audit = root / strict_audit_path("rtx3090", "test")
        rtx_summary.write_text(summary.read_text(encoding="utf-8"), encoding="utf-8")
        rtx_audit.write_text(strict_audit.read_text(encoding="utf-8"), encoding="utf-8")
        historical_rows = build_rows(
            root,
            ["rtx3090"],
            "test",
            goal_readiness_csv=goal_readiness_path("test"),
        )
        assert historical_rows[0]["package_status"] == "historical_local_evidence", historical_rows
        assert historical_rows[0]["strict_summary_status"] == "historical_pass", historical_rows
        assert not row_is_complete(historical_rows[0]), historical_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--tag", required=False, default="20260708")
    parser.add_argument("--profiles", default=",".join(DEFAULT_PROFILES))
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument(
        "--goal-readiness-csv",
        help=(
            "readiness audit to summarize; defaults to the package tag, but callers with "
            "a separate readiness date must pass that current file explicitly"
        ),
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("platform intake dashboard self-test passed")
        return 0

    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    unknown = sorted(set(profiles) - set(PROFILE_POWER_SEMANTICS))
    if unknown:
        parser.error("unknown profiles: " + ",".join(unknown))
    repo = Path(args.repo)
    rows = build_rows(
        repo,
        profiles,
        args.tag,
        goal_readiness_csv=(
            Path(args.goal_readiness_csv) if args.goal_readiness_csv else None
        ),
    )
    out_csv = Path(
        args.out_csv
        or f"results/summary/platform_component_intake_dashboard_{args.tag}.csv"
    )
    out_md = Path(
        args.out_md
        or f"results/summary/platform_component_intake_dashboard_{args.tag}.md"
    )
    write_csv(repo / out_csv, rows)
    write_md(repo / out_md, rows, tag=args.tag)
    complete = [
        row
        for row in rows
        if row_is_complete(row)
    ]
    print(f"platform dashboard profiles={len(rows)} complete={len(complete)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
