#!/usr/bin/env python3
"""Write a platform-specific component-energy experiment command plan.

The generated commands follow the acceptance-first flow:

1. Run architecture/GPU preflight.
2. Run memory paths with duration calibration and Tensor pairs with shared ITER,
   without NCU attached.
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
        "ncu_blocks": 8,
        "shared_w": "32,64",
        "shared_ncu_w": 64,
        "l1_w": "8,16",
        "l1_ncu_w": 8,
        "l2_w": "64",
        "l2_ncu_w": 64,
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "shared_capacity_kib": 100,
        "l2_mib": 6,
        "ncu_chip": "ga102",
        "filter_unavailable_ncu_metrics": 1,
        "tensor_threshold": "2e8",
        "register_threshold": "2e8",
        "memory_energy_load_repeats": "4,8,16",
        "min_device_memory_mib": 0,
        "power_semantics": "one_sec_average",
        "note": "RTX 3090 / GA102 path. Use total-energy rows for final coefficients; GetPowerUsage fallback has one-second-average semantics.",
    },
    "v100": {
        "cuda_arch": "70",
        "active_sm": 80,
        "blocks": "1,2,4,8,16,32",
        "ncu_blocks": 32,
        "shared_w": "32,64",
        "shared_ncu_w": 32,
        "l1_w": "8,16,32",
        "l1_ncu_w": 32,
        "l2_w": "32,64",
        "l2_ncu_w": 32,
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "shared_capacity_kib": 96,
        "l2_mib": 6,
        "ncu_chip": "gv100",
        "filter_unavailable_ncu_metrics": 1,
        "tensor_threshold": "2e8",
        "register_threshold": "2e8",
        "memory_energy_load_repeats": "4,8,16",
        "min_device_memory_mib": 30000,
        "power_semantics": "instant",
        "note": "Volta path. Use nvcc with compute_70 support (CUDA 12.x recommended; CUDA 13 removed Volta offline compilation). Nsight Compute 2024.3 is confirmed for GV100; always require --list-chips and --query-metrics support for gv100 because newer releases can remove Volta.",
    },
    "a100": {
        "cuda_arch": "80",
        "active_sm": 108,
        "blocks": "16,32",
        "ncu_blocks": 16,
        "shared_w": "64,128",
        "shared_ncu_w": 128,
        "l1_w": "16,32",
        "l1_ncu_w": 16,
        "l2_w": "16,32,64,128",
        "l2_ncu_w": 16,
        "l2_ncu_w_values": "16,32,64,128",
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "shared_capacity_kib": 164,
        "l2_mib": 40,
        "ncu_chip": "ga100",
        "filter_unavailable_ncu_metrics": 1,
        "tensor_threshold": "3e8",
        "register_threshold": "3e8",
        "memory_energy_load_repeats": "4,8,16",
        "min_device_memory_mib": 0,
        "power_semantics": "instant",
        "note": "GA100 40 MiB L2 path. Final L2 candidates sweep ld.global.cg at W_SM=16,32,64,128 KiB and require path-specific L1 hit bytes plus L2 read hit/miss evidence; l2_load_only is diagnostic-only.",
    },
    "h100": {
        "cuda_arch": "90",
        "active_sm": 132,
        "blocks": "16,32",
        "ncu_blocks": 16,
        "shared_w": "64,128",
        "shared_ncu_w": 128,
        "l1_w": "16,32",
        "l1_ncu_w": 16,
        "l2_w": "64,128",
        "l2_ncu_w": 64,
        "l2_modes": "global_addr_only,l2_cg_load_only",
        "dram_w": "8192",
        "shared_capacity_kib": 228,
        "l2_mib": 50,
        "ncu_chip": "gh100",
        "filter_unavailable_ncu_metrics": 1,
        "tensor_threshold": "4e8",
        "register_threshold": "4e8",
        "memory_energy_load_repeats": "4,8,16",
        "min_device_memory_mib": 0,
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


def validate_ncu_coordinates(
    profile_name: str,
    profile: dict[str, Any],
    *,
    active_sm: int,
    energy_blocks: str,
    ncu_blocks: int,
) -> None:
    block_values = {int(value) for value in energy_blocks.split(",") if value}
    if ncu_blocks not in block_values:
        raise ValueError(
            f"{profile_name}: strict NCU blocks/SM {ncu_blocks} is not in energy sweep {energy_blocks}"
        )

    coordinates = {
        "shared": int(profile["shared_ncu_w"]),
        "global_l1": int(profile["l1_ncu_w"]),
        "l2": int(profile["l2_ncu_w"]),
    }
    for component, w_sm_kib in coordinates.items():
        if w_sm_kib < ncu_blocks:
            raise ValueError(
                f"{profile_name}: {component} strict coordinate W_SM={w_sm_kib} KiB "
                f"cannot provide the required 1 KiB tile to {ncu_blocks} blocks/SM"
            )

    shared_total_kib = coordinates["shared"] + ncu_blocks
    if shared_total_kib > int(profile["shared_capacity_kib"]):
        raise ValueError(
            f"{profile_name}: shared strict coordinate requires {shared_total_kib} KiB/SM, "
            f"above the {profile['shared_capacity_kib']} KiB profile capacity"
        )

    l2_mib = float(profile["l2_mib"])
    for component in ("global_l1", "l2"):
        full_working_set_mib = active_sm * coordinates[component] / 1024.0
        if full_working_set_mib > l2_mib:
            raise ValueError(
                f"{profile_name}: {component} strict coordinate uses "
                f"{full_working_set_mib:g} MiB, above nominal L2 {l2_mib:g} MiB"
            )

    dram_working_set_mib = active_sm * int(profile["dram_w"]) / 1024.0
    if dram_working_set_mib <= l2_mib:
        raise ValueError(
            f"{profile_name}: DRAM sanity working set {dram_working_set_mib:g} MiB "
            f"does not exceed nominal L2 {l2_mib:g} MiB"
        )


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
    extra_args: list[str] | None = None,
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
            *(extra_args or []),
        ]
    )


def write_shell(args: argparse.Namespace, profile: dict[str, Any], path: Path) -> None:
    tag = args.tag
    active_sm = args.active_sm or profile["active_sm"]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    ncu_blocks = args.ncu_blocks_per_sm
    binary = args.binary
    ncu = args.ncu
    tensor_control_calibration_min_seconds = max(1.0, args.seconds * 0.1)
    # l2_load_only follows the normal global-load policy and therefore cannot
    # prove an L2-only path. Keep it out of strict packages; only CG loads are
    # eligible L2-path evidence.
    include_l2_capacity_ncu = "0"

    raw_prefix = f"results/raw/{args.target_profile}_component_finalplan_{tag}"
    summary_prefix = f"results/summary/{args.target_profile}_component_finalplan_{tag}"
    ncu_dir = f"results/ncu/{args.target_profile}_component_finalplan_ncu_factor_{tag}"
    ncu_raw = f"results/raw/{args.target_profile}_component_finalplan_ncu_factor_{tag}.csv"
    ncu_summary = f"{ncu_dir}/ncu_cache_validation_summary.csv"
    tensor_pair_calibration_csv = f"{raw_prefix}_tensor_pair_calibration.csv"
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
        tensor_pair_calibration_csv,
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
        "NVCC_COMMAND=\"${NVCC:-nvcc}\"",
        "if [[ \"${NCU_USE_SUDO}\" == \"1\" ]]; then",
        "  NCU_COMMAND=\"${NCU_SUDO} ${NCU_BIN}\"",
        "else",
        "  NCU_COMMAND=\"${NCU_BIN}\"",
        "fi",
        "echo \"Using NCU command: ${NCU_COMMAND}\"",
        "echo \"Using CUDA compiler: ${NVCC_COMMAND}\"",
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
                *(
                    [
                        "--min-device-memory-mib",
                        q(str(args.min_device_memory_mib)),
                    ]
                    if args.min_device_memory_mib > 0
                    else []
                ),
                "--active-sm",
                q(str(active_sm)),
                "--binary",
                q(binary),
                "--ncu",
                "\"${NCU_COMMAND}\"",
                "--nvcc",
                "\"${NVCC_COMMAND}\"",
                "--out",
                q(f"{summary_prefix}_preflight.md"),
            ]
        ),
        "",
        "# 2. Pipeline policy self-tests. Fail early if a gate is broken.",
        line(["python3", "scripts/run_component_regression_sweep.py", "--self-test"]),
        line(["python3", "scripts/summarize_ncu_cache_metrics.py", "--self-test"]),
        line(["python3", "scripts/analyze_ncu_path_acceptance.py", "--self-test"]),
        line(["python3", "scripts/analyze_matched_control_energy.py", "--self-test"]),
        line(["python3", "scripts/audit_power_api_measurements.py", "--self-test"]),
        line(["python3", "scripts/audit_a100_tensor_l2_remediation.py", "--self-test"]),
        line(["python3", "scripts/build_strict_component_summary.py", "--self-test"]),
        line(["python3", "scripts/audit_strict_component_summary.py", "--self-test"]),
        line(["python3", "scripts/write_platform_result_manifest.py", "--self-test"]),
        line(["python3", "scripts/selftest_platform_package_gates.py"]),
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
        "# 4. Three-row schema/revision smoke test. Catch stale binaries before the full sweep.",
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
                q(binary),
                "--gpu-list",
                q(args.gpu_ids.split(",")[0]),
                "--mode",
                "reg_operand_only",
                "--w-sm-kib",
                "2048",
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
                q(binary),
                "--gpu-list",
                q(args.gpu_ids.split(",")[0]),
                "--mode",
                "l2_cg_load_only",
                "--w-sm-kib",
                q(str(profile["l2_ncu_w"])),
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
                "--require-mode-notes-marker",
                "reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1",
                "--require-mode-notes-marker",
                "reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1",
                "--require-mode-notes-marker",
                "l2_cg_load_only=global_warmup_policy=ld_global_cg",
                "--require-mode-notes-marker",
                "dram_cg_load_only=global_warmup_policy=ld_global_cg",
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
            extra_args=[
                "--tensor-pair-lock-iters",
                "--tensor-pair-control-min-seconds",
                q(str(tensor_control_calibration_min_seconds)),
                "--pair-calibration-csv",
                q(tensor_pair_calibration_csv),
            ],
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
                "--require-mode-notes-marker",
                "reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1",
                "--require-mode-notes-marker",
                "reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1",
                "--require-mode-notes-marker",
                "l2_cg_load_only=global_warmup_policy=ld_global_cg",
                "--require-mode-notes-marker",
                "dram_cg_load_only=global_warmup_policy=ld_global_cg",
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
                f"NCU_CHIP={q(profile['ncu_chip'])}",
                f"NCU_FILTER_UNAVAILABLE_METRICS={int(profile.get('filter_unavailable_ncu_metrics', 0))}",
                f"GPU={q(args.gpu_ids.split(',')[0])}",
                f"ACTIVE_SM={active_sm}",
                f"BLOCKS_PER_SM={ncu_blocks}",
                f"REG_BLOCKS_PER_SM={ncu_blocks}",
                "REG_PRESSURE_PAYLOAD_BYTES=256",
                "REG_W_SM_KIB=2048",
                f"L1_W_SM_KIB={profile['l1_ncu_w']}",
                f"SHARED_W_SM_KIB={profile['shared_ncu_w']}",
                f"L2_W_SM_KIB={profile['l2_ncu_w']}",
                f"L2_W_SM_KIB_VALUES={profile.get('l2_ncu_w_values', profile['l2_ncu_w'])}",
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
                "--tensor-control-min-elapsed-s",
                q(str(0.8 * tensor_control_calibration_min_seconds)),
                "--max-elapsed-ratio",
                "1.35",
                "--pairing",
                "nearest-control",
                "--tensor-pair-policy",
                "matched-iters",
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
                "--require-path-specific-cache-evidence",
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
    ncu_blocks = args.ncu_blocks_per_sm
    tensor_control_min_seconds = max(1.0, args.seconds * 0.1)
    out_sh = args.out_sh
    build_dir = str(Path(args.binary).parent)
    block_values = [int(value) for value in blocks.split(",") if value]
    l1_w_values = [int(value) for value in profile["l1_w"].split(",") if value]
    l1_valid_coordinates = [
        f"W{w}/B{b}" for w in l1_w_values for b in block_values if w >= b
    ]
    l1_skipped_coordinates = [
        f"W{w}/B{b}" for w in l1_w_values for b in block_values if w < b
    ]
    memory_gate_note = ""
    build_commands = (
        f"cmake -S . -B {build_dir} "
        f"-DCMAKE_CUDA_ARCHITECTURES={profile['cuda_arch']}\n"
        f"cmake --build {build_dir} --clean-first -j"
    )
    if args.target_profile == "v100":
        if args.min_device_memory_mib > 0:
            memory_gate_note = f"""
For the V100 reference package, `{args.min_device_memory_mib:,} MiB` is a strict lower bound for a
32 GB HBM2 device visible to the process. This distinguishes the intended 32 GB
SKU from a 16 GB board or a smaller vGPU partition; it does not change the
L1/shared/L2 hierarchy coordinates. Override this threshold only when running a
separately labelled non-32 GB V100 experiment.
"""
        build_commands = f"""NVCC="${{NVCC:-/path/to/cuda-12/bin/nvcc}}"
"${{NVCC}}" --list-gpu-arch | grep -Fx compute_70
cmake -S . -B {build_dir} \\
  -DCMAKE_CUDA_COMPILER="${{NVCC}}" \\
  -DCMAKE_CUDA_ARCHITECTURES={profile['cuda_arch']}
cmake --build {build_dir} --clean-first -j"""

    architecture_ncu_notes = {
        "rtx3090": f"""RTX 3090 uses `NCU_CHIP=ga102` and `l2_cg_load_only` at
W_SM={profile['l2_w']} KiB as the strict L2 path. The generated strict anchor is
B{ncu_blocks}; the existing accepted RTX 3090 reporting package uses separate
B16 targeted/stability evidence and must not be confused with this generated plan.""",
        "v100": f"""V100 uses `NCU_CHIP=gv100` and `l2_cg_load_only` as the L2
final path. Its energy sweep covers blocks/SM={blocks}; the generated strict
anchor is B{ncu_blocks}, L2 W_SM={profile['l2_ncu_w']} KiB. L2
W_SM={profile['l2_w'].split(',')[-1]} KiB is retained as a capacity-stress point.
The NCU binary must explicitly support GV100.""",
        "a100": f"""A100 uses `NCU_CHIP=ga100`; its L2 candidates are below the
{profile['l2_mib']} MiB L2 capacity and use `ld.global.cg` to avoid global-L1
cache hits. The sidecar sweeps W_SM={profile.get('l2_ncu_w_values', profile['l2_ncu_w'])}
KiB and keeps only coordinates where path-specific L1 hit bytes are near zero
and path-specific L2 read hit rate passes. L1TEX request bytes are expected for
`.cg` and are not treated as L1 cache-hit evidence.""",
        "h100": f"""H100 uses `NCU_CHIP=gh100` and `l2_cg_load_only` at
W_SM={profile['l2_w']} KiB for the L2 candidate sweep. The current kernels use
the WMMA FP16 compatibility path, so this evidence does not validate Hopper-native
WGMMA, TMA, or FP8 execution.""",
    }
    architecture_ncu_note = architecture_ncu_notes[args.target_profile]

    text = f"""# {args.target_profile.upper()} Component Finalplan Command Plan

Generated: {dt.date.today().isoformat()}

| item | value |
|---|---|
| target profile | `{args.target_profile}` |
| CUDA arch | `sm_{profile['cuda_arch']}` |
| active_SM (SMs) | `{active_sm}` |
| energy sweep blocks/SM | `{blocks}` |
| strict NCU blocks/SM | `{ncu_blocks}` |
| expected power semantics | `{profile['power_semantics']}` |
| minimum visible device memory (MiB) | `{args.min_device_memory_mib}` |
| seconds (s) | `{args.seconds}` |
| repeats | `{args.repeats}` |
| Tensor control calibration floor (s) | `{tensor_control_min_seconds}` |
| binary | `{args.binary}` |
| NCU | `{args.ncu}` |
| NCU sudo fallback | `NCU_USE_SUDO=1 bash {out_sh}` |
| generated shell | `{out_sh}` |

## Platform Note

{profile['note']}

{memory_gate_note}

## Build Requirement

Build the benchmark for `sm_{profile['cuda_arch']}` before running the generated
shell. The preflight dry-run rejects a binary built for the wrong compute
capability, but using a profile-specific build directory avoids wasting the
target node allocation.

```bash
{build_commands}
```

Use a clean rebuild after every `git pull` that changes `src/`, `include/`, or
`CMakeLists.txt`. In particular, raw CSVs for final runs must be produced by a
binary whose CSV header includes `measurement_scope`.

## Component Coordinates

| component/path | modes | energy W_SM (KiB) | strict NCU W_SM/B | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 2048/{ncu_blocks} | reuse 1,2,4,8,16; treatment/control-floor dual-calibrated pair-locked ITER |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | {profile['shared_w']} | {profile['shared_ncu_w']}/{ncu_blocks} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| Global L1 | `global_addr_only,global_l1_load_only` | {profile['l1_w']} | {profile['l1_ncu_w']}/{ncu_blocks} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| L2 | `{profile['l2_modes']}` | {profile['l2_w']} | {profile.get('l2_ncu_w_values', profile['l2_ncu_w'])}/{ncu_blocks} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU also checks 1,2 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | {profile['dram_w']} | {profile['dram_w']}/{ncu_blocks} | energy load_repeat {profile['memory_energy_load_repeats']}; NCU checks 1,4,8,16 |

The energy runner applies the same 1 KiB/block feasibility rule to treatment and
matched control. Global L1 valid coordinates are
`{','.join(l1_valid_coordinates)}`. Coordinates omitted before execution because
`W_SM < blocks/SM` are `{','.join(l1_skipped_coordinates) or 'none'}`. The
generated matrix retains rejected rows with `valid=false`, but no rejected row
is sent to the binary. Before collecting energy, every unique valid coordinate
is also checked with the binary's `--dry-run` mode.

## Architecture-Specific NCU Evidence

The generated package is not valid from hit rate alone. Every target-profile
run must keep the architecture-specific NCU sidecar and acceptance report with
both cache-hit direction and traffic magnitude:

| evidence | required columns | unit / meaning |
|---|---|---|
| L1 hit direction | `l1_path_hit_rate_pct`, `l1_hit_bytes` | percent, bytes; global-load lookup hit/miss path |
| L2 hit direction | `l2_path_hit_rate_pct`, `l2_read_hit_sectors`, `l2_read_miss_sectors` | percent, sectors; srcunit-TEX read path |
| access magnitude | `l1_accesses`, `l2_accesses`, `dram_accesses` | L1 requests when available, otherwise sectors; L2/DRAM sectors |
| byte magnitude | `shared_bytes`, `l1_request_bytes`, `l1_hit_bytes`, `l2_read_bytes`, `dram_bytes` | bytes; L1 request bytes are not L1 hit bytes; L2 pJ/bit uses L2 read bytes |
| spill/local traffic | `local_read_bytes`, `local_write_bytes`, `spill_local_read_inst`, `spill_local_write_inst`, `spill_evidence_source` | bytes/instructions; unsupported dedicated spill counters fall back to zero local-memory bytes only |
| stall context | `stall_long_scoreboard_pct` | percent-like NCU stall signal |
| launch/resource context | `achieved_occupancy_pct`, `registers_per_thread`, `shared_mem_per_block_static`, `shared_mem_per_block_dynamic` | requested B value가 실제 residency로 이어졌는지 해석하는 보조 evidence |

{architecture_ncu_note}

CG measurement paths also use an `ld.global.cg` warm-up kernel so the harness
does not pre-populate L1 with a normal cached-load warm-up.
Some NCU metric catalogs, including the reviewed GA100 catalog, may omit the dedicated
`sass__inst_executed_register_spilling_*` metrics. The sidecar also requests
local-memory load/store bytes; because these kernels have no intentional local
memory path, zero local bytes plus ptxas spill zero is recorded as
`spill_zero_verified=1` with
`spill_evidence_source=local_memory_bytes_zero_inference`. Architectures with
dedicated spill instruction counters can also produce `spill_zero_verified=1`.
Any positive local bytes or spill instructions reject the path.
`l2_load_only` follows the normal global-load policy, can hit L1, and is therefore
diagnostic-only rather than strict L2 evidence.

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
control; NCU verifies global-load L1 request bytes are zero and treats SMID atomic L2
sectors as control bookkeeping rather than input traffic. Legacy diagnostic
modes such as `l2_load_only`, `shared_mma`, `l2_mma`, and `dram_mma` are not
profiled unless `INCLUDE_DIAGNOSTIC_NCU=1` is set manually.

For a quick profiler preflight only, override the sidecar lists manually, for
example `TENSOR_REUSE_FACTORS=4 MEMORY_LOAD_REPEATS=4 DRAM_LOAD_REPEATS=4`.

Before the energy sweeps, the generated shell moves stale generated artifacts
for this profile/tag into `results/archive/..._stale_<timestamp>`. This avoids
appending new rows to an old CSV schema. It then runs a three-row schema and
implementation-revision smoke test (`clocked_empty`, `reg_operand_only`, and
`l2_cg_load_only`). The audit requires an explicit `measurement_scope` plus the
exact Tensor pair and `.cg` warm-up revision markers in raw `notes`. If the
binary is stale, the script stops there instead of producing hundreds or
thousands of unusable rows.

Before the schema smoke and energy sweeps, the generated shell runs Tensor pair
calibration, NCU path-counter, matched-control policy, power API, and strict
summary self-tests. In particular,
`scripts/run_component_regression_sweep.py --self-test`,
`scripts/summarize_ncu_cache_metrics.py --self-test`,
`scripts/analyze_ncu_path_acceptance.py --self-test`,
`scripts/analyze_matched_control_energy.py --self-test`,
`scripts/audit_power_api_measurements.py --self-test`, and
`scripts/audit_a100_tensor_l2_remediation.py --self-test`,
`scripts/build_strict_component_summary.py --self-test`,
`scripts/audit_strict_component_summary.py --self-test`,
`scripts/write_platform_result_manifest.py --self-test`, and
`scripts/selftest_platform_package_gates.py` so Tensor pair-lock, A100 path-specific
L2 semantics,
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

Tensor energy rows use `--tensor-pair-lock-iters` together with
`--tensor-pair-control-min-seconds={tensor_control_min_seconds}`. Each RF coordinate
calibrates `reg_mma` for the treatment target and `reg_operand_only` for the
control-duration floor, records both candidate ITER values, and runs both modes
with their maximum. Matched-control
analysis then uses `--tensor-pair-policy matched-iters` and directly subtracts
the two idle-corrected net energies. An ITER mismatch is a hard-invalid Tensor
detail row; the analysis no longer rescales a differently calibrated Tensor
control by elapsed-time power.
The runner rotates complete control-treatment coordinate pairs between repeats;
it never rotates a flat list by one command and split a pair across repeat
boundaries. The same atomic pair ordering applies to the generated Shared,
Global L1, L2 CG, and DRAM CG treatment-control sweeps.
Both Tensor kernels execute the same dependent register integer add once per
RF iteration, so the liveness/control instruction cancels in the direct pair.
The control no longer performs the former RF-proportional FP32 FMA/checksum or
memory work. Both modes use the same per-thread eight-scalar-store epilogue
instead of a WMMA store intrinsic. The treatment stores all accumulator
fragment values to keep HMMA live; the control stores sink values with the same
address pattern while keeping its HMMA count at zero.
The raw Tensor rows must contain
`tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1` in `notes`.
CG rows must contain `global_warmup_policy=ld_global_cg`. The package audit
rejects either missing marker so a stale binary with the same CSV schema cannot
silently pass.
Because the no-MMA control completes the same ITER much faster, dual calibration
prevents it from falling below {tensor_control_min_seconds} s by construction. The
analyzer still uses a separate `--tensor-control-min-elapsed-s=0.05` hard schema
floor instead of the full treatment `--min-elapsed-s`; non-positive control net
energy remains rejected. The package audit cross-checks both candidate ITERs,
the max-resolution policy, the raw ITER,
matched-detail basis, ITER ratio, and control elapsed time.

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
Generated target-node packages invoke the audit with
`--require-path-specific-cache-evidence`; aggregate-only historical cache
counters cannot satisfy a new A100/V100/H100 result package.
The package intake audit then checks the raw energy CSVs, power API audit,
power-state audit, NCU acceptance, matched-control detail, reliability audit,
strict summary, and strict summary audit as one profile/tag package before the
result is copied back or published. It also checks that raw CSV rows carry the
target profile metadata (`chip`, `compute_capability`, L2 size, L1/shared
capacity) and the generated `active_SM` value. If a target node uses MIG,
partitioning, or an SKU with fewer visible SMs, regenerate this plan with
`--active-sm <runtime SM count>` after preflight and keep the same value in the
package audit.
The package audit also verifies that the NCU summary exposes aggregate and
path-specific L1/L2 hit rates, L1 request/hit/miss bytes, L2 read hit/miss
sectors and bytes, L1/L2/DRAM access counts, DRAM traffic, and long-scoreboard stall counters
before the result can be treated as final evidence. Hit rate alone is not enough:
accepted cache rows must also show path-relevant access/byte magnitude. The NCU
summary must include
`clocked_empty`, `reg_operand_only`, `reg_mma`, `shared_scalar_load_only`,
`global_l1_load_only`, `l2_cg_load_only`, and `dram_cg_load_only` coverage.
All generated platform packages use `l2_cg_load_only` as the strict L2 path;
`l2_load_only` is diagnostic-only and is not required. Tensor pair NCU rows need at least three
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
    parser.add_argument(
        "--ncu-blocks-per-sm",
        type=int,
        default=0,
        help=(
            "blocks/SM used by the strict NCU sidecar. Defaults to the profile "
            "coordinate and must also appear in --blocks-per-sm-values."
        ),
    )
    parser.add_argument(
        "--min-device-memory-mib",
        type=int,
        default=-1,
        help=(
            "Visible-memory lower bound passed to strict preflight. Defaults to "
            "the profile package value; pass 0 to disable for a separately labelled SKU."
        ),
    )
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--tag", default=today)
    parser.add_argument("--out-sh", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    if args.ncu_blocks_per_sm <= 0:
        args.ncu_blocks_per_sm = int(profile["ncu_blocks"])
    validate_ncu_coordinates(
        args.target_profile,
        profile,
        active_sm=args.active_sm or int(profile["active_sm"]),
        energy_blocks=blocks,
        ncu_blocks=args.ncu_blocks_per_sm,
    )
    if args.min_device_memory_mib < 0:
        args.min_device_memory_mib = int(profile.get("min_device_memory_mib", 0))
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
