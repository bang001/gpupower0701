#!/usr/bin/env python3
"""Audit platform profile, power API, and generated finalplan consistency."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import subprocess
import tempfile
from pathlib import Path
from typing import Any


EXPECTED: dict[str, dict[str, Any]] = {
    "rtx3090": {
        "cuda_arch": "86",
        "active_sm": 82,
        "ncu_chip": "ga102",
        "power_semantics": "one_sec_average",
        "default_binary": "./build/a100_fp16_energy_v2",
        "guide": "README.md",
        "guide_terms": [
            "RTX 3090",
            "one_sec_average",
            "power_measurement_api_matrix_ko.md",
            "nvml_total_energy",
        ],
    },
    "v100": {
        "cuda_arch": "70",
        "active_sm": 80,
        "ncu_chip": "gv100",
        "blocks": "4,16,32",
        "ncu_blocks": 32,
        "shared_ncu_w": 32,
        "l1_ncu_w": 32,
        "l2_ncu_w": 32,
        "cuda_toolchain_term": "compute_70",
        "power_semantics": "instant",
        "default_binary": "./build-v100/a100_fp16_energy_v2",
        "guide": "docs/platforms/v100_node_experiment_guide_ko.md",
        "guide_terms": [
            "V100",
            "sm_70",
            "compute_70",
            "CUDA 12",
            "gv100",
            "instant",
            "power_measurement_api_matrix_ko.md",
            "nvml_total_energy",
        ],
    },
    "a100": {
        "cuda_arch": "80",
        "active_sm": 108,
        "ncu_chip": "ga100",
        "power_semantics": "instant",
        "default_binary": "./build-a100/a100_fp16_energy_v2",
        "guide": "docs/platforms/a100_node_experiment_guide_ko.md",
        "guide_terms": [
            "A100",
            "sm_80",
            "ga100",
            "MIG",
            "instant",
            "power_measurement_api_matrix_ko.md",
            "nvmlDeviceGetTotalEnergyConsumption",
        ],
    },
    "h100": {
        "cuda_arch": "90",
        "active_sm": 132,
        "ncu_chip": "gh100",
        "power_semantics": "one_sec_average",
        "default_binary": "./build-h100/a100_fp16_energy_v2",
        "guide": "docs/platforms/h100_node_experiment_guide_ko.md",
        "guide_terms": [
            "H100",
            "sm_90",
            "gh100",
            "one-second average",
            "module power",
            "GPU memory power",
            "WGMMA",
            "power_measurement_api_matrix_ko.md",
        ],
    },
}

MATRIX_TERMS = [
    "nvmlDeviceGetTotalEnergyConsumption",
    "nvmlDeviceGetPowerUsage",
    "nvmlDeviceGetPowerUsage_v2",
    "nvmlDeviceGetTotalEnergyConsumption_v2",
    "현재 harness",
    "power.draw.average",
    "power.draw.instant",
    "module power",
    "GPU memory power",
    "measurement_scope",
    "gpu_device_total_energy_counter",
    "final_candidate",
    "provisional",
    "reject",
]

PLAN_SHELL_TERMS = [
    "scripts/preflight_gpu_support.py",
    "--strict",
    "--active-sm",
    "NVCC_COMMAND=\"${NVCC:-nvcc}\"",
    "--nvcc \"${NVCC_COMMAND}\"",
    "scripts/run_component_regression_sweep.py --self-test",
    "scripts/audit_power_api_measurements.py --self-test",
    "scripts/audit_power_api_measurements.py",
    "scripts/build_strict_component_summary.py --self-test",
    "scripts/audit_strict_component_summary.py --self-test",
    "--fail-on-reject",
    "--fail-on-provisional",
    "--require-explicit-measurement-scope",
    "scripts/audit_power_state_stability.py",
    "scripts/run_ncu_validation.sh",
    "scripts/analyze_ncu_path_acceptance.py",
    "scripts/analyze_matched_control_energy.py",
    "--require-ncu-denominator",
    "--exclude-power-state-rejects",
    "--require-total-energy",
    "--expected-power-semantics",
    "scripts/audit_component_reliability.py",
    "scripts/audit_matched_control_instability.py",
    "scripts/build_strict_component_summary.py",
    "--power-api-audit-csv",
    "--power-state-audit-csv",
    "scripts/audit_strict_component_summary.py",
    "scripts/audit_platform_result_package.py",
    "--expected-active-sm",
    "--fail-on-incomplete",
    "scripts/write_platform_result_manifest.py",
    "scripts/summarize_platform_package_gaps.py",
    "scripts/build_platform_intake_dashboard.py",
    "scripts/audit_component_goal_readiness.py --self-test",
    "scripts/audit_component_goal_readiness.py",
    "PACKAGE_AUDIT_RC",
    "_strict_scope_fresh_ncu_component_coefficients_",
    "_strict_scope_fresh_ncu_component_summary_audit_",
    "_platform_result_package_audit_",
    "_platform_result_package_gaps_",
    "platform_component_intake_dashboard_",
    "component_energy_goal_readiness_audit_",
]

PLAN_MD_TERMS = [
    "power_measurement_api_matrix_ko.md",
    "audit_power_api_measurements.py --self-test",
    "final coefficients require",
    "measurement_scope=gpu_device_total_energy_counter",
    "Fallback",
    "board-level effective coefficients",
    "build_strict_component_summary.py",
    "audit_strict_component_summary.py",
    "audit_platform_result_package.py",
    "L1/L2 hit rates",
    "L1/L2/DRAM access counts",
    "l2_cg_load_only` as the strict L2 path",
    "reuse_factor` points",
    "load_repeat` points",
    "hard_plausibility_range",
    "l2_greater_than_shared",
    "ncu_summary_counter_schema",
    "ncu_summary_coordinate_alignment",
    "ncu_evidence_summary_fields",
    "path-relevant NCU evidence",
    "component-specific NCU artifact",
    "strict NCU coordinate-alignment",
    "write_platform_result_manifest.py",
    "summarize_platform_package_gaps.py",
    "build_platform_intake_dashboard.py",
    "audit_component_goal_readiness.py",
    "Build Requirement",
    "CMAKE_CUDA_ARCHITECTURES",
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_row(
    rows: list[dict[str, str]],
    *,
    profile: str,
    check: str,
    status: str,
    expected: str = "",
    actual: str = "",
    evidence: str = "",
) -> None:
    rows.append(
        {
            "profile": profile,
            "check": check,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
        }
    )


def status_for(condition: bool) -> str:
    return "pass" if condition else "fail"


def compare_value(
    rows: list[dict[str, str]],
    *,
    profile: str,
    check: str,
    expected: Any,
    actual: Any,
    evidence: str,
) -> None:
    add_row(
        rows,
        profile=profile,
        check=check,
        status=status_for(str(expected) == str(actual)),
        expected=str(expected),
        actual=str(actual),
        evidence=evidence,
    )


def text_contains_all(text: str, terms: list[str]) -> tuple[bool, str]:
    missing = [term for term in terms if term not in text]
    return not missing, ";".join(missing)


def run_plan(repo: Path, profile: str, tmpdir: Path) -> tuple[int, str, str, str]:
    out_sh = tmpdir / f"{profile}_plan.sh"
    out_md = tmpdir / f"{profile}_plan.md"
    cmd = [
        "python3",
        "scripts/plan_platform_component_experiment.py",
        "--target-profile",
        profile,
        "--ncu",
        "ncu",
        "--seconds",
        "10",
        "--repeats",
        "5",
        "--tag",
        "readiness_audit",
        "--out-sh",
        str(out_sh),
        "--out-md",
        str(out_md),
    ]
    proc = subprocess.run(
        cmd,
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    shell_text = out_sh.read_text(encoding="utf-8") if out_sh.exists() else ""
    md_text = out_md.read_text(encoding="utf-8") if out_md.exists() else ""
    return proc.returncode, proc.stdout, shell_text, md_text


def audit_profiles(repo: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    plan = load_module(repo / "scripts/plan_platform_component_experiment.py", "plan_profiles")
    preflight = load_module(repo / "scripts/preflight_gpu_support.py", "preflight_profiles")
    plan_profiles = plan.PROFILES
    preflight_profiles = preflight.PROFILES

    matrix_path = repo / "docs/platforms/power_measurement_api_matrix_ko.md"
    matrix_text = matrix_path.read_text(encoding="utf-8") if matrix_path.exists() else ""
    add_row(
        rows,
        profile="all",
        check="power_matrix_exists",
        status=status_for(matrix_path.exists()),
        expected="exists",
        actual=str(matrix_path.exists()),
        evidence=str(matrix_path),
    )
    ok, missing = text_contains_all(matrix_text, MATRIX_TERMS)
    add_row(
        rows,
        profile="all",
        check="power_matrix_core_terms",
        status=status_for(ok),
        expected="all core API/scope/gate terms",
        actual="ok" if ok else f"missing:{missing}",
        evidence=str(matrix_path),
    )

    ncu_wrapper_path = repo / "scripts" / "run_ncu_validation.sh"
    ncu_wrapper_text = ncu_wrapper_path.read_text(encoding="utf-8")
    ncu_wrapper_terms = [
        "NCU_AUTO_SUDO=\"${NCU_AUTO_SUDO:-1}\"",
        "ERR_NVGPUCTRPERM",
        "enable_sudo_ncu",
        "--target-processes all",
        "NCU_PERMISSION_PROBE_ONLY",
        "ncu_permission_mode.txt",
    ]
    ok, missing = text_contains_all(ncu_wrapper_text, ncu_wrapper_terms)
    add_row(
        rows,
        profile="all",
        check="ncu_permission_fallback_policy",
        status=status_for(ok),
        expected="counter probe, exact-error sudo retry, child-process coverage",
        actual="ok" if ok else f"missing:{missing}",
        evidence=str(ncu_wrapper_path),
    )

    with tempfile.TemporaryDirectory(prefix="platform_readiness_") as tmp:
        tmpdir = Path(tmp)
        for profile, expected in EXPECTED.items():
            plan_profile = plan_profiles.get(profile)
            preflight_profile = preflight_profiles.get(profile)
            add_row(
                rows,
                profile=profile,
                check="plan_profile_present",
                status=status_for(plan_profile is not None),
                expected="present",
                actual=str(plan_profile is not None),
                evidence="scripts/plan_platform_component_experiment.py",
            )
            add_row(
                rows,
                profile=profile,
                check="preflight_profile_present",
                status=status_for(preflight_profile is not None),
                expected="present",
                actual=str(preflight_profile is not None),
                evidence="scripts/preflight_gpu_support.py",
            )
            if plan_profile:
                compare_value(
                    rows,
                    profile=profile,
                    check="plan_cuda_arch",
                    expected=expected["cuda_arch"],
                    actual=plan_profile.get("cuda_arch"),
                    evidence="scripts/plan_platform_component_experiment.py",
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="plan_active_sm",
                    expected=expected["active_sm"],
                    actual=plan_profile.get("active_sm"),
                    evidence="scripts/plan_platform_component_experiment.py",
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="plan_ncu_chip",
                    expected=expected["ncu_chip"],
                    actual=plan_profile.get("ncu_chip"),
                    evidence="scripts/plan_platform_component_experiment.py",
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="plan_power_semantics",
                    expected=expected["power_semantics"],
                    actual=plan_profile.get("power_semantics"),
                    evidence="scripts/plan_platform_component_experiment.py",
                )
                for coordinate in (
                    "blocks",
                    "ncu_blocks",
                    "shared_ncu_w",
                    "l1_ncu_w",
                    "l2_ncu_w",
                ):
                    if coordinate in expected:
                        compare_value(
                            rows,
                            profile=profile,
                            check=f"plan_{coordinate}",
                            expected=expected[coordinate],
                            actual=plan_profile.get(coordinate),
                            evidence="scripts/plan_platform_component_experiment.py",
                        )
            if preflight_profile:
                compare_value(
                    rows,
                    profile=profile,
                    check="preflight_cuda_arch",
                    expected=expected["cuda_arch"],
                    actual=preflight_profile.get("cuda_arch"),
                    evidence="scripts/preflight_gpu_support.py",
                )
                if "cuda_toolchain_term" in expected:
                    policy = str(preflight_profile.get("cuda_toolchain_policy", ""))
                    term = str(expected["cuda_toolchain_term"])
                    add_row(
                        rows,
                        profile=profile,
                        check="preflight_cuda_toolchain_policy",
                        status=status_for(term in policy),
                        expected=f"contains:{term}",
                        actual=policy,
                        evidence="scripts/preflight_gpu_support.py",
                    )
                compare_value(
                    rows,
                    profile=profile,
                    check="preflight_active_sm",
                    expected=expected["active_sm"],
                    actual=preflight_profile.get("full_sm"),
                    evidence="scripts/preflight_gpu_support.py",
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="preflight_ncu_chip",
                    expected=expected["ncu_chip"],
                    actual=preflight_profile.get("ncu_chip"),
                    evidence="scripts/preflight_gpu_support.py",
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="preflight_power_semantics",
                    expected=expected["power_semantics"],
                    actual=preflight_profile.get("power_usage_semantics"),
                    evidence="scripts/preflight_gpu_support.py",
                )

            guide_path = repo / expected["guide"]
            guide_text = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
            add_row(
                rows,
                profile=profile,
                check="guide_exists",
                status=status_for(guide_path.exists()),
                expected="exists",
                actual=str(guide_path.exists()),
                evidence=str(guide_path),
            )
            ok, missing = text_contains_all(guide_text, expected["guide_terms"])
            add_row(
                rows,
                profile=profile,
                check="guide_power_and_platform_terms",
                status=status_for(ok),
                expected="all required guide terms",
                actual="ok" if ok else f"missing:{missing}",
                evidence=str(guide_path),
            )

            if plan_profile:
                rc, out, shell_text, md_text = run_plan(repo, profile, tmpdir)
                add_row(
                    rows,
                    profile=profile,
                    check="generated_plan_runs",
                    status=status_for(rc == 0),
                    expected="return code 0",
                    actual=str(rc),
                    evidence=out.strip().replace("\n", " | "),
                )
                shell_terms = [
                    *PLAN_SHELL_TERMS,
                    f"--target-profile {profile}",
                    f"--expected-power-semantics {expected['power_semantics']}",
                    f"TARGET_PROFILE={profile}",
                    "NCU_PERMISSION_PROBE_ONLY=1",
                    "NCU_AUTO_SUDO=\"${NCU_AUTO_SUDO:-1}\"",
                    "permission probe selected sudo for the remaining NCU stages",
                    "scripts/selftest_ncu_permission_fallback.sh",
                ]
                if profile == "v100":
                    shell_terms.extend(
                        [
                            "--blocks-per-sm-values 4,16,32",
                            "NCU_CHIP=gv100",
                            "NCU_FILTER_UNAVAILABLE_METRICS=1",
                            "BLOCKS_PER_SM=32",
                            "REG_BLOCKS_PER_SM=32",
                            "SHARED_W_SM_KIB=32",
                            "L1_W_SM_KIB=32",
                            "L2_W_SM_KIB=32",
                            "NVCC_COMMAND=\"${NVCC:-nvcc}\"",
                            "--nvcc \"${NVCC_COMMAND}\"",
                        ]
                    )
                ok, missing = text_contains_all(shell_text, shell_terms)
                add_row(
                    rows,
                    profile=profile,
                    check="generated_shell_final_gates",
                    status=status_for(ok),
                    expected="power/ncu/matched/reliability gates",
                    actual="ok" if ok else f"missing:{missing}",
                    evidence="plan_platform_component_experiment generated shell",
                )
                goal_pos = shell_text.find("scripts/audit_component_goal_readiness.py --ncu")
                dashboard_pos = shell_text.find("scripts/build_platform_intake_dashboard.py")
                order_ok = goal_pos >= 0 and dashboard_pos >= 0 and goal_pos < dashboard_pos
                add_row(
                    rows,
                    profile=profile,
                    check="generated_shell_goal_dashboard_order",
                    status=status_for(order_ok),
                    expected="goal readiness audit before dashboard refresh",
                    actual=(
                        "ok"
                        if order_ok
                        else f"goal_pos={goal_pos},dashboard_pos={dashboard_pos}"
                    ),
                    evidence="plan_platform_component_experiment generated shell",
                )
                gap_tag_term = (
                    "scripts/summarize_platform_package_gaps.py "
                    f"--target-profile {profile} --tag"
                )
                add_row(
                    rows,
                    profile=profile,
                    check="generated_gap_report_tagged",
                    status=status_for(gap_tag_term in shell_text),
                    expected="gap report command carries target profile and tag",
                    actual="ok" if gap_tag_term in shell_text else "missing_tagged_gap_command",
                    evidence="plan_platform_component_experiment generated shell",
                )
                binary = expected["default_binary"]
                binary_terms = [
                    f"--binary {binary}",
                    f"BIN={binary}",
                    f"| binary | `{binary}` |",
                ]
                missing_binary_terms = [
                    term
                    for term in binary_terms
                    if term not in (shell_text if term.startswith(("--binary", "BIN=")) else md_text)
                ]
                add_row(
                    rows,
                    profile=profile,
                    check="generated_default_binary_path",
                    status=status_for(not missing_binary_terms),
                    expected=f"profile-built binary path {binary}",
                    actual=(
                        "ok"
                        if not missing_binary_terms
                        else "missing:" + ",".join(missing_binary_terms)
                    ),
                    evidence="plan_platform_component_experiment generated shell/markdown",
                )
                ok, missing = text_contains_all(md_text, PLAN_MD_TERMS)
                add_row(
                    rows,
                    profile=profile,
                    check="generated_markdown_power_api_note",
                    status=status_for(ok),
                    expected="power matrix and effective-energy caveat",
                    actual="ok" if ok else f"missing:{missing}",
                    evidence="plan_platform_component_experiment generated markdown",
                )
                # Normal global loads can hit L1 on every target profile. The
                # strict plan therefore uses CG L2 evidence and keeps capacity
                # loads out of the NCU sidecar regardless of L2 size.
                expected_l2_capacity = "0"
                actual_l2_capacity = (
                    "1"
                    if "INCLUDE_L2_CAPACITY_NCU=1" in shell_text
                    else "0"
                    if "INCLUDE_L2_CAPACITY_NCU=0" in shell_text
                    else "missing"
                )
                compare_value(
                    rows,
                    profile=profile,
                    check="generated_l2_capacity_policy",
                    expected=expected_l2_capacity,
                    actual=actual_l2_capacity,
                    evidence="strict L2 policy: l2_cg_load_only; l2_load_only diagnostic-only",
                )

    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["profile", "check", "status", "expected", "actual", "evidence"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, str]], csv_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_profile: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_profile.setdefault(row["profile"], []).append(row)
    fail_rows = [row for row in rows if row["status"] != "pass"]
    with path.open("w", encoding="utf-8") as f:
        f.write("# Platform Power/Readiness Audit\n\n")
        f.write(
            "이 보고서는 RTX 3090, V100, A100, H100 profile의 power API 의미, "
            "preflight profile, finalplan 생성 스크립트, 플랫폼 문서가 서로 맞는지 "
            "정적으로 점검한다. 실제 GPU 측정 결과가 아니라, 새 노드에서 실험하기 전 "
            "RTX 3090 기준이 섞이지 않도록 확인하는 readiness gate다.\n\n"
        )
        f.write(f"- detail CSV: `{csv_path}`\n")
        f.write(f"- checks: {len(rows)}\n")
        f.write(f"- failures: {len(fail_rows)}\n\n")
        f.write("## Verdict\n\n")
        if fail_rows:
            f.write(
                "`fail` 항목이 있으므로 해당 profile은 실험 전에 코드/문서를 먼저 "
                "수정해야 한다.\n\n"
            )
        else:
            f.write(
                "정적 readiness check는 통과했다. 단, 이것은 A100/V100/H100에서 "
                "component coefficient가 검증되었다는 뜻이 아니다. 각 노드에서 "
                "power API audit, NCU path acceptance, matched-control/reliability "
                "audit을 새로 통과해야 final 후보가 된다.\n\n"
            )
        f.write("## Profile Summary\n\n")
        f.write("| profile | pass | fail |\n|---|---:|---:|\n")
        for profile in sorted(by_profile):
            profile_rows = by_profile[profile]
            passes = sum(1 for row in profile_rows if row["status"] == "pass")
            fails = len(profile_rows) - passes
            f.write(f"| `{profile}` | {passes} | {fails} |\n")
        f.write("\n")
        for profile in sorted(by_profile):
            f.write(f"## {profile}\n\n")
            f.write("| check | status | expected | actual |\n|---|---|---|---|\n")
            for row in by_profile[profile]:
                f.write(
                    f"| `{row['check']}` | `{row['status']}` | "
                    f"`{row['expected']}` | `{row['actual']}` |\n"
                )
            f.write("\n")
        f.write("## Interpretation\n\n")
        f.write(
            "- `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분이 final numerator의 "
            "우선 경로다.\n"
        )
        f.write(
            "- `nvmlDeviceGetPowerUsage`는 세대별 의미가 다르다. V100/A100은 "
            "`instant`, RTX 3090/H100은 `one_sec_average`로 기록한다.\n"
        )
        f.write(
            "- 최신 NVML의 `nvmlDeviceGetPowerUsage_v2`와 "
            "`nvmlDeviceGetTotalEnergyConsumption_v2`는 현재 harness가 아직 "
            "호출하지 않는다. v2를 도입하면 v1/v2 결과를 별도 metadata와 run class로 "
            "분리한다.\n"
        )
        f.write(
            "- H100/HGX의 module power와 GPU memory power는 preflight metadata로만 "
            "기록하고 component coefficient numerator로 섞지 않는다.\n"
        )
        f.write(
            "- final row는 `measurement_scope=gpu_device_total_energy_counter`여야 "
            "하며, fallback/module/memory scope는 별도 provisional 또는 reject로 "
            "분리한다.\n"
        )
        f.write(
            "- 이 readiness audit은 코드/문서 정합성만 확인한다. 실제 coefficient "
            "채택은 각 플랫폼의 raw CSV, NCU counter, reliability audit 결과로 "
            "판정한다.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--out-csv",
        default="results/summary/platform_power_readiness_audit_20260708.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/platform_power_readiness_audit_20260708.md",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    rows = audit_profiles(repo)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    write_csv(out_csv, rows)
    write_markdown(out_md, rows, out_csv)
    failures = [row for row in rows if row["status"] != "pass"]
    print(f"wrote {out_csv}")
    print(f"wrote {out_md}")
    if failures:
        print(f"failures: {len(failures)}")
        return 1
    print("all readiness checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
