#!/usr/bin/env python3
"""Write a platform-specific component-energy experiment command plan.

The generated commands follow the acceptance-first flow:

1. Run architecture/GPU preflight.
2. Run duration-calibrated energy sweeps without NCU attached.
3. Run a separate NCU sidecar validation.
4. Classify NCU path acceptance.
5. Analyze matched-control energy with NCU byte-denominator scaling.
6. Build and audit a strict component summary package.
7. Audit the returned platform result package against the power/NCU gates.

The script does not execute experiments. It writes a shell script and a short
markdown plan so platform runs can be reviewed before submission to a node.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shlex
from pathlib import Path
from typing import Any


PROFILES: dict[str, dict[str, Any]] = {
    "rtx3090": {
        "cuda_arch": "86",
        "active_sm": 82,
        "blocks": "8,16",
        "shared_w": "32,64",
        "l1_w": "8,16",
        "l2_w": "64",
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "ga102",
        "tensor_threshold": "2e8",
        "register_threshold": "2e8",
        "memory_energy_load_repeats": "4,8,16",
        "power_semantics": "one_sec_average",
        "note": "RTX 3090 / GA102 path. Use total-energy rows for final coefficients; GetPowerUsage fallback has one-second-average semantics.",
    },
    "v100": {
        "cuda_arch": "70",
        "active_sm": 80,
        "blocks": "16,32",
        "shared_w": "32,64",
        "l1_w": "8,16",
        "l2_w": "64",
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "gv100",
        "tensor_threshold": "2e8",
        "register_threshold": "2e8",
        "memory_energy_load_repeats": "4,8,16",
        "power_semantics": "instant",
        "note": "Volta path. Use an NCU toolchain whose --list-chips includes gv100.",
    },
    "a100": {
        "cuda_arch": "80",
        "active_sm": 108,
        "blocks": "16,32",
        "shared_w": "64,128",
        "l1_w": "16,32",
        "l2_w": "64,128",
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "ga100",
        "tensor_threshold": "3e8",
        "register_threshold": "3e8",
        "memory_energy_load_repeats": "4,8,16",
        "power_semantics": "instant",
        "note": "GA100 40 MiB L2 path. Final L2 coefficient uses ld.global.cg with a 6.75 MiB first-point working set; l2_load_only is diagnostic-only and excluded from the strict path.",
    },
    "h100": {
        "cuda_arch": "90",
        "active_sm": 132,
        "blocks": "16,32",
        "shared_w": "64,128",
        "l1_w": "16,32",
        "l2_w": "64,128",
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "gh100",
        "tensor_threshold": "4e8",
        "register_threshold": "4e8",
        "memory_energy_load_repeats": "4,8,16",
        "power_semantics": "one_sec_average",
        "note": "Current kernel uses WMMA compatibility path, not Hopper WGMMA/TMA. Final L2 coefficient uses ld.global.cg; l2_load_only remains diagnostic-only.",
    },
}


DEFAULT_BINARY_BY_PROFILE = {
    "rtx3090": "./build/a100_fp16_energy_v2",
    "v100": "./build-v100/a100_fp16_energy_v2",
    "a100": "./build-a100/a100_fp16_energy_v2",
    "h100": "./build-h100/a100_fp16_energy_v2",
}


def q(value: str | Path) -> str:
    return shlex.quote(str(value))


def line(parts: list[str]) -> str:
    return " ".join(parts)


def run_component_command(
    *,
    binary: str,
    profile: str,
    gpu_ids: str,
    active_sm: int,
    seconds: float,
    repeats: int,
    modes: str,
    w_values: str,
    blocks: str,
    reuse_factors: str,
    load_repeats: str,
    output: str,
    matrix: str,
) -> str:
    return line(
        [
            "python3",
            "scripts/run_component_regression_sweep.py",
            "--execute",
            "--binary",
            q(binary),
            "--target-profile",
            q(profile),
            "--gpu-ids",
            q(gpu_ids),
            "--max-active-gpus",
            "1",
            "--modes",
            q(modes),
            "--w-sm-kib-values",
            q(w_values),
            "--blocks-per-sm-values",
            q(blocks),
            "--active-sm-values",
            q(str(active_sm)),
            "--reuse-factors",
            q(reuse_factors),
            "--load-repeats",
            q(load_repeats),
            "--store-repeats",
            "1",
            "--seconds",
            q(str(seconds)),
            "--repeats",
            q(str(repeats)),
            "--output",
            q(output),
            "--matrix-csv",
            q(matrix),
        ]
    )


def write_shell(args: argparse.Namespace, profile: dict[str, Any], path: Path) -> None:
    tag = args.tag
    active_sm = args.active_sm or profile["active_sm"]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    binary = args.binary
    ncu = args.ncu
    # l2_load_only follows the normal global-load policy and therefore cannot
    # prove an L2-only path. Keep it out of strict packages; only CG loads are
    # eligible L2-path evidence.
    include_l2_capacity_ncu = "0"

    raw_prefix = f"results/raw/{args.target_profile}_component_finalplan_{tag}"
    summary_prefix = f"results/summary/{args.target_profile}_component_finalplan_{tag}"
    ncu_dir = f"results/ncu/{args.target_profile}_component_finalplan_ncu_factor_{tag}"
    ncu_raw = f"results/raw/{args.target_profile}_component_finalplan_ncu_factor_{tag}.csv"
    ncu_summary = f"{ncu_dir}/ncu_cache_validation_summary.csv"
    acceptance_csv = f"{summary_prefix}_ncu_acceptance.csv"
    acceptance_md = f"{summary_prefix}_ncu_acceptance.md"
    power_audit_csv = f"{summary_prefix}_power_api_audit.csv"
    power_audit_md = f"{summary_prefix}_power_api_audit.md"
    power_state_audit_csv = f"{summary_prefix}_power_state_audit.csv"
    power_state_audit_md = f"{summary_prefix}_power_state_audit.md"
    schema_smoke_csv = f"{raw_prefix}_schema_smoke.csv"
    schema_smoke_audit_csv = f"{summary_prefix}_schema_smoke_power_api_audit.csv"
    schema_smoke_audit_md = f"{summary_prefix}_schema_smoke_power_api_audit.md"
    matched_summary = f"{summary_prefix}_matched_control_summary.csv"
    matched_detail = f"{summary_prefix}_matched_control_detail.csv"
    matched_md = f"{summary_prefix}_matched_control_report.md"
    reliability_csv = f"{summary_prefix}_component_reliability_audit.csv"
    reliability_md = f"{summary_prefix}_component_reliability_audit.md"
    instability_csv = f"{summary_prefix}_matched_control_instability_audit.csv"
    instability_md = f"{summary_prefix}_matched_control_instability_audit.md"
    strict_summary_csv = (
        f"results/summary/{args.target_profile}_strict_scope_fresh_ncu_"
        f"component_coefficients_{tag}.csv"
    )
    strict_summary_md = (
        f"results/summary/{args.target_profile}_strict_scope_fresh_ncu_"
        f"component_coefficients_{tag}.md"
    )
    strict_audit_csv = (
        f"results/summary/{args.target_profile}_strict_scope_fresh_ncu_"
        f"component_summary_audit_{tag}.csv"
    )
    strict_audit_md = (
        f"results/summary/{args.target_profile}_strict_scope_fresh_ncu_"
        f"component_summary_audit_{tag}.md"
    )
    package_audit_csv = (
        f"results/summary/{args.target_profile}_platform_result_package_audit_"
        f"{tag}.csv"
    )
    package_audit_md = (
        f"results/summary/{args.target_profile}_platform_result_package_audit_"
        f"{tag}.md"
    )
    result_manifest_csv = f"{summary_prefix}_result_manifest.csv"
    result_manifest_md = f"{summary_prefix}_result_manifest.md"
    gap_report_csv = (
        f"results/summary/{args.target_profile}_platform_result_package_gaps_"
        f"{tag}.csv"
    )
    gap_report_md = (
        f"results/summary/{args.target_profile}_platform_result_package_gaps_"
        f"{tag}.md"
    )
    dashboard_csv = f"results/summary/platform_component_intake_dashboard_{tag}.csv"
    dashboard_md = f"results/summary/platform_component_intake_dashboard_{tag}.md"
    goal_readiness_csv = f"results/summary/component_energy_goal_readiness_audit_{tag}.csv"
    goal_readiness_md = f"results/summary/component_energy_goal_readiness_audit_{tag}.md"

    energy_csvs = [
        f"{raw_prefix}_tensor.csv",
        f"{raw_prefix}_shared.csv",
        f"{raw_prefix}_l1.csv",
        f"{raw_prefix}_l2.csv",
        f"{raw_prefix}_dram.csv",
    ]
    matrix_csvs = [
        f"{raw_prefix}_tensor_matrix.csv",
        f"{raw_prefix}_shared_matrix.csv",
        f"{raw_prefix}_l1_matrix.csv",
        f"{raw_prefix}_l2_matrix.csv",
        f"{raw_prefix}_dram_matrix.csv",
    ]
    stale_paths = [
        schema_smoke_csv,
        schema_smoke_audit_csv,
        schema_smoke_audit_md,
        *energy_csvs,
        *matrix_csvs,
        ncu_raw,
        acceptance_csv,
        acceptance_md,
        power_audit_csv,
        power_audit_md,
        power_state_audit_csv,
        power_state_audit_md,
        matched_summary,
        matched_detail,
        matched_md,
        reliability_csv,
        reliability_md,
        instability_csv,
        instability_md,
        strict_summary_csv,
        strict_summary_md,
        strict_audit_csv,
        strict_audit_md,
        result_manifest_csv,
        result_manifest_md,
        package_audit_csv,
        package_audit_md,
        gap_report_csv,
        gap_report_md,
    ]

    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# Generated for {args.target_profile} on {dt.date.today().isoformat()}.",
        f"# {profile['note']}",
        "mkdir -p results/raw results/summary results/ncu",
        "",
        "# NCU wrapper. If NCU fails with ERR_NVGPUCTRPERM, rerun this script with:",
        "#   NCU_USE_SUDO=1 bash \"$0\"",
        f"NCU_BIN_DEFAULT={q(ncu)}",
        "NCU_BIN=\"${NCU_BIN:-${NCU_BIN_DEFAULT}}\"",
        "NCU_USE_SUDO=\"${NCU_USE_SUDO:-0}\"",
        "NCU_SUDO=\"${NCU_SUDO:-sudo -E}\"",
        "if [[ \"${NCU_USE_SUDO}\" == \"1\" ]]; then",
        "  NCU_COMMAND=\"${NCU_SUDO} ${NCU_BIN}\"",
        "else",
        "  NCU_COMMAND=\"${NCU_BIN}\"",
        "fi",
        "echo \"Using NCU command: ${NCU_COMMAND}\"",
        "",
        "# 1. Preflight",
        line(
            [
                "python3",
                "scripts/preflight_gpu_support.py",
                "--gpu",
                q(args.gpu_ids.split(",")[0]),
                "--target-profile",
                q(args.target_profile),
                "--strict",
                "--active-sm",
                q(str(active_sm)),
                "--binary",
                q(binary),
                "--ncu",
                "\"${NCU_COMMAND}\"",
                "--out",
                q(f"{summary_prefix}_preflight.md"),
            ]
        ),
        "",
        "# 2. Power API policy self-test. Fail early if the gate is broken.",
        line(["python3", "scripts/audit_power_api_measurements.py", "--self-test"]),
        line(["python3", "scripts/build_strict_component_summary.py", "--self-test"]),
        line(["python3", "scripts/audit_strict_component_summary.py", "--self-test"]),
        "",
        "# 3. Move stale generated outputs aside before writing new CSV schemas.",
        "RUN_STAMP=$(date +%Y%m%d_%H%M%S)",
        f"STALE_DIR=results/archive/{args.target_profile}_component_finalplan_{tag}_stale_${{RUN_STAMP}}",
        "STALE_PATHS=(",
        *(f"  {q(path)}" for path in stale_paths),
        ")",
        "for path in \"${STALE_PATHS[@]}\"; do",
        "  if [[ -e \"${path}\" ]]; then",
        "    mkdir -p \"${STALE_DIR}/$(dirname \"${path}\")\"",
        "    mv \"${path}\" \"${STALE_DIR}/${path}\"",
        "  fi",
        "done",
        f"if [[ -e {q(ncu_dir)} ]]; then",
        f"  mkdir -p \"${{STALE_DIR}}/$(dirname {q(ncu_dir)})\"",
        f"  mv {q(ncu_dir)} \"${{STALE_DIR}}/{ncu_dir}\"",
        "fi",
        "",
        "# 4. One-row schema smoke test. This catches old binaries before the full sweep.",
        line(
            [
                q(binary),
                "--gpu-list",
                q(args.gpu_ids.split(",")[0]),
                "--mode",
                "clocked_empty",
                "--w-sm-kib",
                "1",
                "--blocks-per-sm",
                "1",
                "--target-profile",
                q(args.target_profile),
                "--active-sm",
                "1",
                "--seconds",
                "0.2",
                "--iters",
                "1",
                "--repeats",
                "1",
                "--reuse-factor",
                "1",
                "--load-repeat",
                "1",
                "--store-repeat",
                "1",
                "--output",
                q(schema_smoke_csv),
                "--verify-smid",
                "0",
            ]
        ),
        line(
            [
                "python3",
                "scripts/audit_power_api_measurements.py",
                q(schema_smoke_csv),
                "--target-profile",
                q(args.target_profile),
                "--out-csv",
                q(schema_smoke_audit_csv),
                "--out-md",
                q(schema_smoke_audit_md),
                "--fail-on-reject",
                "--fail-on-provisional",
                "--require-explicit-measurement-scope",
            ]
        ),
        "",
        "# 5. Energy sweeps. Keep NCU detached from these runs.",
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="reg_operand_only,reg_mma",
            w_values="2048",
            blocks=blocks,
            reuse_factors="1,2,4,8,16",
            load_repeats="1",
            output=energy_csvs[0],
            matrix=matrix_csvs[0],
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="clocked_empty,shared_scalar_load_only",
            w_values=profile["shared_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats=profile["memory_energy_load_repeats"],
            output=energy_csvs[1],
            matrix=matrix_csvs[1],
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="global_addr_only,global_l1_load_only",
            w_values=profile["l1_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats=profile["memory_energy_load_repeats"],
            output=energy_csvs[2],
            matrix=matrix_csvs[2],
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes=profile["l2_modes"],
            w_values=profile["l2_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats=profile["memory_energy_load_repeats"],
            output=energy_csvs[3],
            matrix=matrix_csvs[3],
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="global_addr_only,dram_cg_load_only",
            w_values=profile["dram_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats=profile["memory_energy_load_repeats"],
            output=energy_csvs[4],
            matrix=matrix_csvs[4],
        ),
        "",
        "# 6. Power API audit before spending time on NCU.",
        line(
            [
                "python3",
                "scripts/audit_power_api_measurements.py",
                *(q(path) for path in energy_csvs),
                "--target-profile",
                q(args.target_profile),
                "--out-csv",
                q(power_audit_csv),
                "--out-md",
                q(power_audit_md),
                "--fail-on-reject",
                "--fail-on-provisional",
                "--require-explicit-measurement-scope",
            ]
        ),
        "",
        "# 7. Power-state row-quality audit. This does not replace the power API gate.",
        line(
            [
                "python3",
                "scripts/audit_power_state_stability.py",
                *(q(path) for path in energy_csvs),
                "--out-csv",
                q(power_state_audit_csv),
                "--out-md",
                q(power_state_audit_md),
            ]
        ),
        "",
        "# 8. NCU sidecar validation. These profiler runs are not energy rows.",
        line(
            [
                f"NCU_EXPLICIT_METRICS_ONLY=1",
                "NCU=\"${NCU_COMMAND}\"",
                f"BIN={q(binary)}",
                f"OUTDIR={q(ncu_dir)}",
                f"RAW_OUT={q(ncu_raw)}",
                f"TARGET_PROFILE={q(args.target_profile)}",
                f"GPU={q(args.gpu_ids.split(',')[0])}",
                f"ACTIVE_SM={active_sm}",
                f"BLOCKS_PER_SM={blocks.split(',')[0]}",
                f"REG_BLOCKS_PER_SM={blocks.split(',')[0]}",
                "REG_PRESSURE_PAYLOAD_BYTES=256",
                "REG_W_SM_KIB=2048",
                f"L1_W_SM_KIB={profile['l1_w'].split(',')[0]}",
                f"SHARED_W_SM_KIB={profile['shared_w'].split(',')[-1]}",
                f"L2_W_SM_KIB={profile['l2_w'].split(',')[0]}",
                f"DRAM_W_SM_KIB_OVERRIDE={profile['dram_w']}",
                f"INCLUDE_L2_CAPACITY_NCU={include_l2_capacity_ncu}",
                "INCLUDE_DIAGNOSTIC_NCU=0",
                "REUSE_FACTOR=1",
                "LOAD_REPEAT=1",
                "TENSOR_REUSE_FACTORS=1,2,4,8,16",
                "MEMORY_LOAD_REPEATS=1,2,4,8,16",
                "DRAM_LOAD_REPEATS=1,4,8,16",
                "bash",
                "scripts/run_ncu_validation.sh",
            ]
        ),
        "",
        "# 9. Path acceptance.",
        line(
            [
                "python3",
                "scripts/analyze_ncu_path_acceptance.py",
                q(ncu_summary),
                "--target-profile",
                q(args.target_profile),
                "--out-csv",
                q(acceptance_csv),
                "--out-md",
                q(acceptance_md),
                "--tensor-memory-bytes-max",
                profile["tensor_threshold"],
                "--register-memory-bytes-max",
                profile["register_threshold"],
                "--tensor-memory-bytes-per-hmma-max",
                "1.0",
                "--register-memory-bytes-per-op-max",
                "1.0",
            ]
        ),
        "",
        "# 10. Matched-control analysis with NCU byte-denominator scaling.",
        line(
            [
                "python3",
                "scripts/analyze_matched_control_energy.py",
                *(q(path) for path in energy_csvs),
                "--acceptance-csv",
                q(acceptance_csv),
                "--ncu-summary-csv",
                q(ncu_summary),
                "--power-state-audit-csv",
                q(power_state_audit_csv),
                "--exclude-power-state-rejects",
                "--require-ncu-denominator",
                "--require-total-energy",
                "--expected-power-semantics",
                q(profile["power_semantics"]),
                "--min-elapsed-s",
                q(str(max(1.0, args.seconds * 0.8))),
                "--max-elapsed-ratio",
                "1.35",
                "--pairing",
                "nearest-control",
                "--min-delta-j",
                q(str(max(2.0, args.seconds))),
                "--min-delta-fraction",
                "0.005",
                "--out-summary-csv",
                q(matched_summary),
                "--out-detail-csv",
                q(matched_detail),
                "--out-md",
                q(matched_md),
            ]
        ),
        "",
        "# 11. Component reliability audit.",
        "set +e",
        line(
            [
                "python3",
                "scripts/audit_component_reliability.py",
                "--power-audit-csv",
                q(power_audit_csv),
                "--ncu-acceptance-csv",
                q(acceptance_csv),
                "--matched-summary-csv",
                q(matched_summary),
                "--matched-detail-csv",
                q(matched_detail),
                "--expected-power-semantics",
                q(profile["power_semantics"]),
                "--out-csv",
                q(reliability_csv),
                "--out-md",
                q(reliability_md),
                "--fail-on-reject",
            ]
        ),
        "RELIABILITY_AUDIT_RC=$?",
        "set -e",
        "",
        "# 12. Matched-control instability/root-cause audit.",
        line(
            [
                "python3",
                "scripts/audit_matched_control_instability.py",
                q(matched_detail),
                "--out-csv",
                q(instability_csv),
                "--out-md",
                q(instability_md),
            ]
        ),
        "",
        "# 13. Build strict component summary package from accepted evidence.",
        "set +e",
        line(
            [
                "python3",
                "scripts/build_strict_component_summary.py",
                "--target-profile",
                q(args.target_profile),
                "--gpu-label",
                q(args.target_profile.upper()),
                "--matched-summary-csv",
                q(matched_summary),
                "--matched-detail-csv",
                q(matched_detail),
                "--power-api-audit-csv",
                q(power_audit_csv),
                "--power-state-audit-csv",
                q(power_state_audit_csv),
                "--reliability-csv",
                q(reliability_csv),
                "--ncu-acceptance-csv",
                q(acceptance_csv),
                "--ncu-summary-csv",
                q(ncu_summary),
                "--instability-artifact",
                q(instability_csv),
                "--out-csv",
                q(strict_summary_csv),
                "--out-md",
                q(strict_summary_md),
            ]
        ),
        "STRICT_BUILD_RC=$?",
        "set -e",
        "",
        "# 14. Audit strict component summary against reliability/detail artifacts.",
        "set +e",
        line(
            [
                "python3",
                "scripts/audit_strict_component_summary.py",
                "--summary-csv",
                q(strict_summary_csv),
                "--expected-power-semantics",
                q(profile["power_semantics"]),
                "--out-csv",
                q(strict_audit_csv),
                "--out-md",
                q(strict_audit_md),
                "--fail-on-fail",
            ]
        ),
        "STRICT_AUDIT_RC=$?",
        "set -e",
        "",
        "# 15. Write the expected result manifest for copy-back and gap triage.",
        line(
            [
                "python3",
                "scripts/write_platform_result_manifest.py",
                "--target-profile",
                q(args.target_profile),
                "--tag",
                q(tag),
                "--expected-active-sm",
                q(str(active_sm)),
                "--out-csv",
                q(result_manifest_csv),
                "--out-md",
                q(result_manifest_md),
            ]
        ),
        "",
        "# 16. Audit the full platform result package before publishing or copying back.",
        "set +e",
        line(
            [
                "python3",
                "scripts/audit_platform_result_package.py",
                "--target-profile",
                q(args.target_profile),
                "--tag",
                q(tag),
                "--expected-active-sm",
                q(str(active_sm)),
                "--out-csv",
                q(package_audit_csv),
                "--out-md",
                q(package_audit_md),
                "--fail-on-incomplete",
            ]
        ),
        "PACKAGE_AUDIT_RC=$?",
        "set -e",
        "",
        "# 17. Always write triage/goal-readiness/dashboard artifacts.",
        line(
            [
                "python3",
                "scripts/summarize_platform_package_gaps.py",
                "--target-profile",
                q(args.target_profile),
                "--tag",
                q(tag),
                "--audit-csv",
                q(package_audit_csv),
                "--manifest-csv",
                q(result_manifest_csv),
                "--out-csv",
                q(gap_report_csv),
                "--out-md",
                q(gap_report_md),
            ]
        ),
        line(["python3", "scripts/audit_component_goal_readiness.py", "--self-test"]),
        line(
            [
                "python3",
                "scripts/audit_component_goal_readiness.py",
                "--ncu",
                "\"${NCU_COMMAND}\"",
                "--out-csv",
                q(goal_readiness_csv),
                "--out-md",
                q(goal_readiness_md),
            ]
        ),
        line(
            [
                "python3",
                "scripts/build_platform_intake_dashboard.py",
                "--tag",
                q(tag),
                "--out-csv",
                q(dashboard_csv),
                "--out-md",
                q(dashboard_md),
            ]
        ),
        "",
        "echo 'Done. Review:'",
        f"echo '  {strict_summary_md}'",
        f"echo '  {strict_audit_md}'",
        f"echo '  {package_audit_md}'",
        f"echo '  {gap_report_md}'",
        f"echo '  {dashboard_md}'",
        f"echo '  {goal_readiness_md}'",
        f"echo '  {reliability_md}'",
        f"echo '  {instability_md}'",
        f"echo '  {power_state_audit_md}'",
        f"echo '  {power_audit_md}'",
        f"echo '  {matched_md}'",
        f"echo '  {acceptance_md}'",
        "FINAL_RC=${PACKAGE_AUDIT_RC}",
        "if [[ \"${FINAL_RC}\" -eq 0 && \"${RELIABILITY_AUDIT_RC}\" -ne 0 ]]; then FINAL_RC=${RELIABILITY_AUDIT_RC}; fi",
        "if [[ \"${FINAL_RC}\" -eq 0 && \"${STRICT_BUILD_RC}\" -ne 0 ]]; then FINAL_RC=${STRICT_BUILD_RC}; fi",
        "if [[ \"${FINAL_RC}\" -eq 0 && \"${STRICT_AUDIT_RC}\" -ne 0 ]]; then FINAL_RC=${STRICT_AUDIT_RC}; fi",
        "if [[ \"${FINAL_RC}\" -ne 0 ]]; then",
        "  echo 'Strict evidence package is incomplete. Inspect the package audit and gap report above.'",
        "  exit \"${FINAL_RC}\"",
        "fi",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(commands) + "\n")
    path.chmod(0o755)


def write_markdown(args: argparse.Namespace, profile: dict[str, Any], path: Path) -> None:
    active_sm = args.active_sm or profile["active_sm"]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    out_sh = args.out_sh
    build_dir = str(Path(args.binary).parent)
    text = f"""# {args.target_profile.upper()} Component Finalplan Command Plan

Generated: {dt.date.today().isoformat()}

| item | value |
|---|---|
| target profile | `{args.target_profile}` |
| CUDA arch | `sm_{profile['cuda_arch']}` |
| active_SM (SMs) | `{active_sm}` |
| blocks/SM | `{blocks}` |
| expected power semantics | `{profile['power_semantics']}` |
| seconds (s) | `{args.seconds}` |
| repeats | `{args.repeats}` |
| binary | `{args.binary}` |
| NCU | `{args.ncu}` |
| NCU sudo fallback | `NCU_USE_SUDO=1 bash {out_sh}` |
| generated shell | `{out_sh}` |

## Platform Note

{profile['note']}

## Build Requirement

Build the benchmark for `sm_{profile['cuda_arch']}` before running the generated
shell. The preflight dry-run rejects a binary built for the wrong compute
capability, but using a profile-specific build directory avoids wasting the
target node allocation.

```bash
cmake -S . -B {build_dir} -DCMAKE_CUDA_ARCHITECTURES={profile['cuda_arch']}
cmake --build {build_dir} --clean-first -j
```

Use a clean rebuild after every `git pull` that changes `src/`, `include/`, or
`CMakeLists.txt`. In particular, raw CSVs for final runs must be produced by a
binary whose CSV header includes `measurement_scope`.

## Component Coordinates

| component/path | modes | W_SM (KiB) | factor |
|---|---|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | {profile['shared_w']} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| Global L1 | `global_addr_only,global_l1_load_only` | {profile['l1_w']} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| L2 | `{profile['l2_modes']}` | {profile['l2_w']} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | {profile['dram_w']} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU checks 1,4,8,16 |

## Architecture-Specific NCU Evidence

The generated package is not valid from hit rate alone. Every V100/A100/H100
run must keep the architecture-specific NCU sidecar and acceptance report with
both cache-hit direction and traffic magnitude:

| evidence | required columns | unit / meaning |
|---|---|---|
| L1 hit direction | `l1_hit_rate_pct` | percent |
| L2 hit direction | `l2_hit_rate_pct` | percent |
| access magnitude | `l1_accesses`, `l2_accesses`, `dram_accesses` | L1 requests when available, otherwise sectors; L2/DRAM sectors |
| byte magnitude | `shared_bytes`, `l1_bytes`, `l2_bytes`, `dram_bytes` | bytes, preferred denominator for memory pJ/byte or pJ/bit |
| stall context | `stall_long_scoreboard_pct` | percent-like NCU stall signal |

V100 uses `NCU_CHIP=gv100` and uses `l2_cg_load_only` as the L2 final path.
A100 uses `NCU_CHIP=ga100`; its final L2 point is intentionally below the 40 MiB
L2 capacity and uses `ld.global.cg` to bypass global L1. `l2_load_only` follows
the normal global-load policy, can hit L1, and is therefore diagnostic-only rather
than strict L2 evidence. H100 uses `NCU_CHIP=gh100`; the current kernels are WMMA
compatibility kernels, so the NCU evidence validates the executed compatibility
path, not Hopper-native WGMMA/TMA/FP8 paths.

## How To Run

```bash
bash {out_sh}
```

If Nsight Compute fails with `ERR_NVGPUCTRPERM`, the account does not have GPU
performance-counter permission. The preferred fix is administrator-side access
to non-admin GPU performance counters. For a temporary target-node run, rerun
only the NCU wrapper path through sudo:

```bash
NCU_USE_SUDO=1 bash {out_sh}
```

If `sudo` does not preserve the CUDA/Nsight Compute environment, make the NCU
binary explicit and preserve the environment:

```bash
NCU_BIN="$(command -v ncu)" NCU_USE_SUDO=1 NCU_SUDO="sudo -E" bash {out_sh}
```

The generated shell keeps NVML energy sweeps detached from NCU. The sudo
fallback is only for the NCU sidecar/preflight/goal-readiness commands; failed
NCU evidence must not be replaced with unvalidated denominators in final
component coefficients.

The generated NCU sidecar profiles primary finalplan modes at every energy
`reuse_factor`/`load_repeat` coordinate and includes 1,2 as lower-signal
diagnostic points. This lets `analyze_matched_control_energy.py` prefer
`ncu_actual_exact` denominators instead of representative same-working-set
scaling. The global-memory pairs use `global_addr_only` as a matched address
control; NCU verifies global-load L1 bytes are zero and treats SMID atomic L2
sectors as control bookkeeping rather than input traffic. Legacy diagnostic
modes such as `l2_load_only`, `shared_mma`, `l2_mma`, and `dram_mma` are not
profiled unless `INCLUDE_DIAGNOSTIC_NCU=1` is set manually.

For a quick profiler preflight only, override the sidecar lists manually, for
example `TENSOR_REUSE_FACTORS=4 MEMORY_LOAD_REPEATS=4 DRAM_LOAD_REPEATS=4`.

Before the energy sweeps, the generated shell moves stale generated artifacts
for this profile/tag into `results/archive/..._stale_<timestamp>`. This avoids
appending new rows to an old CSV schema. It then runs a one-row schema smoke
test and audits that row with `--require-explicit-measurement-scope`. If the
binary is stale and the CSV header lacks `measurement_scope`, the script stops
there instead of producing thousands of unusable rows.

Before the schema smoke and energy sweeps, the generated shell runs
`scripts/audit_power_api_measurements.py --self-test` and
`scripts/build_strict_component_summary.py --self-test` and
`scripts/audit_strict_component_summary.py --self-test` so the A100 semantics,
fallback-numerator, explicit-scope, H100 module-scope, strict NCU artifact
selection, and strict NCU coordinate-alignment checks fail early if the gates
themselves regress. Before NCU, it then runs
`scripts/audit_power_api_measurements.py` on the raw energy CSVs. This applies
the rules in
`docs/platforms/power_measurement_api_matrix_ko.md`: final coefficients require
`energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`,
`measurement_scope=gpu_device_total_energy_counter`, and the expected profile
power semantics. The generated command also requires raw CSVs to contain an
explicit `measurement_scope` column/value; inferred scope is history/provisional
only. Fallback `GetPowerUsage` rows fail the generated finalplan script and
must be reported separately as provisional.

After matched-control analysis, the generated shell runs
`scripts/audit_component_reliability.py`. This joins the power API audit, NCU
path acceptance, and matched-control summary/detail into component-level verdicts
such as `accepted`, `accepted_with_caution`, `accepted_low_stability`, and
`accepted_sanity`.

Matched-control consumes the generated power-state audit CSV with
`--exclude-power-state-rejects`, so rows flagged as `status=reject` or
`coefficient_eligible=false` are removed before treatment/control pairing. This
keeps power-state drops from appearing as negative component coefficients.

It also runs `scripts/audit_matched_control_instability.py` to explain weak
signal or negative matched-control rows and to suggest targeted follow-up runs.

Finally, the generated shell runs `scripts/build_strict_component_summary.py`,
`scripts/audit_strict_component_summary.py`, and
`scripts/audit_platform_result_package.py`. The builder copies accepted
reliability medians into
`results/summary/{args.target_profile}_strict_scope_fresh_ncu_component_coefficients_{args.tag}.csv`
and records matched-control, power API, power-state, NCU acceptance, NCU summary,
and instability artifacts. The audit verifies that the packaged summary still
matches the underlying evidence and the power measurement matrix. It also fails
hierarchy/order mistakes such as L2 <= shared/global L1 and broad
order-of-magnitude mistakes outside the strict plausibility ranges.
The package intake audit then checks the raw energy CSVs, power API audit,
power-state audit, NCU acceptance, matched-control detail, reliability audit,
strict summary, and strict summary audit as one profile/tag package before the
result is copied back or published. It also checks that raw CSV rows carry the
target profile metadata (`chip`, `compute_capability`, L2 size, L1/shared
capacity) and the generated `active_SM` value. If a target node uses MIG,
partitioning, or an SKU with fewer visible SMs, regenerate this plan with
`--active-sm <runtime SM count>` after preflight and keep the same value in the
package audit.
The package audit also verifies that the NCU summary exposes L1/L2 hit rates,
L1/L2/DRAM access counts, byte traffic, and long-scoreboard stall counters
before the result can be treated as final evidence. Hit rate alone is not enough:
accepted cache rows must also show path-relevant access/byte magnitude. The NCU
summary must include
`clocked_empty`, `reg_operand_only`, `reg_mma`, `shared_scalar_load_only`,
`global_l1_load_only`, `l2_cg_load_only`, and `dram_cg_load_only` coverage.
A100/H100 packages use `l2_cg_load_only` as the strict L2 path; `l2_load_only`
is diagnostic-only and is not required. Tensor pair NCU rows need at least three
`reuse_factor` points, and memory-path rows need at
least three `load_repeat` points.
The package audit requires the strict summary audit CSV to contain
`hard_plausibility_range`, `l2_greater_than_shared`, `l2_greater_than_l1`, and
`shared_l1_same_order`, so stale pre-plausibility audit artifacts do not pass.
It also requires `ncu_summary_counter_schema`,
`ncu_summary_coordinate_alignment`, and `ncu_evidence_summary_fields`: the strict
summary must point to NCU summary artifacts with cache hit-rate/access/byte/stall
columns, the accepted NCU mode rows must match the matched-control energy
coordinates, and the report row itself must expose path-relevant NCU evidence.
`build_strict_component_summary.py` uses component-specific NCU artifact
selection so, for example, a Tensor row cannot accidentally cite a sidecar
captured with different `blocks/SM` or `reuse_factor`. Shared scalar rows report
shared-memory byte/access evidence separately from background global L1/L2
hit-rate counters.
Before copying results back from the target node, use
`scripts/write_platform_result_manifest.py` to generate a transfer checklist for
all raw, power, NCU, matched-control, reliability, strict summary, and audit
artifacts expected by the package audit. The generated shell now writes this
manifest automatically before package intake.
If the package audit reports `missing` or `fail`, run
`scripts/summarize_platform_package_gaps.py` with the package audit CSV and
result manifest CSV using the same `--tag` as the platform package. The gap
report does not approve results; it maps each open row to the failed stage and
explains whether the issue is a missing artifact, a power measurement matrix
violation, an NCU path problem, or a strict summary/reliability problem.
The generated shell captures the package
audit exit code, still writes the gap report, and exits with the package audit
status after the diagnostic reports are written.
After multiple platform packages are copied back, run
`scripts/build_platform_intake_dashboard.py` to summarize RTX 3090, V100, A100,
and H100 package status, first open stage, and strict summary status in one
table. The generated shell first runs
`scripts/audit_component_goal_readiness.py --self-test` plus the full goal
readiness audit, then refreshes the dashboard so the target-node result bundle
records both validator health and the latest cross-platform intake status.

Review the NCU acceptance report before treating any coefficient as usable.
Values are board-level effective coefficients, not pure physical bitcell energy.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main() -> int:
    today = dt.date.today().strftime("%Y%m%d")
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-profile", required=True, choices=sorted(PROFILES))
    parser.add_argument(
        "--binary",
        default="",
        help=(
            "Path to profile-built benchmark binary. Defaults to ./build for "
            "rtx3090 and ./build-<profile> for V100/A100/H100."
        ),
    )
    parser.add_argument("--ncu", default="ncu")
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--active-sm", type=int, default=0)
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--tag", default=today)
    parser.add_argument("--out-sh", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    if not args.binary:
        args.binary = DEFAULT_BINARY_BY_PROFILE[args.target_profile]
    if not args.out_sh:
        args.out_sh = (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_commands.sh"
        )
    if not args.out_md:
        args.out_md = (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_command_plan.md"
        )

    write_shell(args, profile, Path(args.out_sh))
    write_markdown(args, profile, Path(args.out_md))
    print(f"wrote shell: {args.out_sh}")
    print(f"wrote markdown: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
