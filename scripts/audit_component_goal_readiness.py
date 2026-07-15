#!/usr/bin/env python3
"""Audit end-to-end readiness for the component-energy experiment goal.

This is intentionally a higher-level gate than the per-step audits. It checks
whether the repository currently has enough evidence to claim the component
energy experiment is complete across the intended platform set, while keeping
power API semantics aligned with docs/platforms/power_measurement_api_matrix_ko.md.
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


PROFILES = {
    "rtx3090": "one_sec_average",
    "v100": "instant",
    "a100": "instant",
    "h100": "one_sec_average",
}
DEFAULT_BINARY_BY_PROFILE = {
    "rtx3090": "./build/a100_fp16_energy_v2",
    "v100": "./build-v100/a100_fp16_energy_v2",
    "a100": "./build-a100/a100_fp16_energy_v2",
    "h100": "./build-h100/a100_fp16_energy_v2",
}
DEFAULT_CUDA_ARCH_BY_PROFILE = {
    "rtx3090": "86",
    "v100": "70",
    "a100": "80",
    "h100": "90",
}
DEFAULT_BUILD_DIR_BY_PROFILE = {
    "rtx3090": "build",
    "v100": "build-v100",
    "a100": "build-a100",
    "h100": "build-h100",
}
COMMAND_PACKAGE_PROFILES = ("v100", "a100", "h100")
FABRIC_AWARE_L2_PROFILES = {"a100", "h100"}

POWER_MATRIX = Path("docs/platforms/power_measurement_api_matrix_ko.md")
PLATFORM_READINESS = Path("results/summary/platform_power_readiness_audit_20260715.csv")
STRICT_RTX3090_SUMMARY = Path(
    "results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.csv"
)
STRICT_RTX3090_AUDIT = Path(
    "results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260708.csv"
)
FRESH_NCU_RELIABILITY = Path(
    "results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.csv"
)
FRESH_NCU_ACCEPTANCE = Path(
    "results/summary/rtx3090_strict_scope_fresh_ncu_combined_acceptance_20260708.csv"
)
LOCAL_READINESS_RUNNER = Path("scripts/run_local_readiness_checks.sh")

POWER_MATRIX_TERMS = [
    "nvmlDeviceGetTotalEnergyConsumption",
    "nvmlDeviceGetPowerUsage",
    "nvmlDeviceGetPowerUsage_v2",
    "nvmlDeviceGetTotalEnergyConsumption_v2",
    "gpu_device_total_energy_counter",
    "gpu_device_power_usage_fallback",
    "module power",
    "GPU memory power",
    "silicon-level",
]

COMMAND_SHELL_TERMS = [
    "scripts/preflight_gpu_support.py",
    "--strict",
    "--active-sm",
    "scripts/audit_power_api_measurements.py --self-test",
    "scripts/audit_a100_tensor_l2_remediation.py --self-test",
    "scripts/write_platform_result_manifest.py --self-test",
    "scripts/selftest_platform_package_gates.py",
    "scripts/audit_power_api_measurements.py",
    "--fail-on-reject",
    "--fail-on-provisional",
    "--require-explicit-measurement-scope",
    "--require-mode-notes-marker",
    "reg_operand_only=tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6",
    "l2_cg_load_only=global_warmup_policy=ld_global_cg",
    "scripts/audit_power_state_stability.py",
    "scripts/run_ncu_validation.sh",
    "NCU_COMPONENTS=baseline,tensor,shared,l1",
    "NCU_COMPONENTS=l2",
    "NCU_COMPONENTS=dram",
    "NCU_METRIC_PROFILE=l2_path_minimal",
    "external_memory_minimal",
    "MEMORY_LOAD_REPEATS=4,8,16",
    "DRAM_LOAD_REPEATS=4,8,16",
    "scripts/merge_ncu_validation_summaries.py",
    "scripts/analyze_ncu_path_acceptance.py",
    "scripts/analyze_matched_control_energy.py",
    "--tensor-pair-lock-iters",
    "--tensor-pair-policy matched-iters",
    "--tensor-control-min-elapsed-s",
    "_tensor_pair_calibration.csv",
    "--memory-pair-lock-iters",
    "--l2-pair-policy matched-iters",
    "--l2-control-min-elapsed-s",
    "_l2_pair_calibration.csv",
    "--dram-pair-policy matched-iters",
    "--dram-control-min-elapsed-s",
    "_dram_pair_calibration.csv",
    "L2_W_SM_KIB_VALUES=",
    "--power-state-audit-csv",
    "--exclude-power-state-rejects",
    "--require-ncu-denominator",
    "--require-control-ncu-acceptance",
    "--require-total-energy",
    "--expected-power-semantics",
    "scripts/audit_component_reliability.py",
    "scripts/audit_matched_control_instability.py",
    "scripts/build_strict_component_summary.py",
    "scripts/build_strict_component_summary.py --self-test",
    "--power-api-audit-csv",
    "--power-state-audit-csv",
    "scripts/audit_strict_component_summary.py --self-test",
    "scripts/audit_strict_component_summary.py",
    "--require-path-specific-cache-evidence",
    "scripts/audit_platform_result_package.py",
    "--expected-active-sm",
    "--fail-on-incomplete",
    "scripts/write_platform_result_manifest.py",
    "scripts/summarize_platform_package_gaps.py",
    "scripts/build_platform_intake_dashboard.py",
    "--goal-readiness-csv",
    "scripts/audit_component_goal_readiness.py --self-test",
    "scripts/audit_component_goal_readiness.py",
    "PACKAGE_AUDIT_RC",
    "_platform_result_package_audit_",
    "_platform_result_package_gaps_",
    "platform_component_intake_dashboard_",
    "component_energy_goal_readiness_audit_",
]

COMMAND_PLAN_TERMS = [
    "Component Coordinates",
    "docs/platforms/power_measurement_api_matrix_ko.md",
    "audit_power_api_measurements.py --self-test",
    "build_strict_component_summary.py --self-test",
    "write_platform_result_manifest.py --self-test",
    "selftest_platform_package_gates.py",
    "pair-locked ITER",
    "complete control-treatment coordinate pairs",
    "path-specific L1 hit",
    "path-specific L2 read hit",
    "tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6",
    "global_warmup_policy=ld_global_cg",
    "spill_evidence_source=local_memory_bytes_zero_inference",
    "ncu_actual_exact",
    "build_strict_component_summary.py",
    "audit_strict_component_summary.py",
    "require-path-specific-cache-evidence",
    "audit_platform_result_package.py",
    "board-level effective coefficients",
    "L1/L2 hit rates",
    "L1/L2/DRAM access counts",
    "Global L1/L2/DRAM use `global_addr_only`",
    "reuse_factor` points",
    "load_repeat` points",
    "hard_plausibility_range",
    "l2_greater_than_shared",
    "write_platform_result_manifest.py",
    "summarize_platform_package_gaps.py",
    "build_platform_intake_dashboard.py",
    "audit_component_goal_readiness.py",
    "Build Requirement",
    "CMAKE_CUDA_ARCHITECTURES",
]

LOCAL_READINESS_RUNNER_TERMS = [
    'TAG="${TAG:-20260715}"',
    "scripts/write_platform_result_manifest.py",
    "--out-csv \"results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv\"",
    "--out-md \"results/summary/${profile}_component_finalplan_${TAG}_result_manifest.md\"",
    "scripts/audit_platform_result_package.py",
    "--target-profile \"${profile}\"",
    "--expected-active-sm \"${active_sm}\"",
    "scripts/summarize_platform_package_gaps.py",
    "--tag \"${TAG}\"",
    "--manifest-csv \"results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv\"",
    "scripts/build_strict_component_summary.py --self-test",
    "scripts/audit_strict_component_summary.py --self-test",
    "scripts/audit_strict_component_summary.py",
    "scripts/audit_component_goal_readiness.py",
    "scripts/build_platform_intake_dashboard.py",
    "A100_ACTIVE_SM:-108",
    "V100_ACTIVE_SM:-80",
    "H100_ACTIVE_SM:-132",
    "RUN_GIT_DIFF_CHECK:-1",
]

STRICT_COMPONENTS = {
    "Tensor MMA incremental": "pJ/FLOP",
    "Shared scalar path": "pJ/bit",
    "Global L1 hit path": "pJ/bit",
    "L2 CG hit path": "pJ/bit",
}

HARD_PLAUSIBILITY_RANGES = {
    "Tensor MMA incremental": (0.001, 10.0, "pJ/FLOP"),
    "Shared scalar path": (0.001, 10.0, "pJ/bit"),
    "Global L1 hit path": (0.001, 10.0, "pJ/bit"),
    "L2 CG hit path": (0.01, 30.0, "pJ/bit"),
}

STRICT_AUDIT_REQUIRED_CHECKS = {
    "hard_plausibility_range",
    "l2_greater_than_shared",
    "l2_greater_than_l1",
    "shared_l1_same_order",
    "ncu_summary_counter_schema",
    "ncu_summary_coordinate_alignment",
    "ncu_evidence_summary_fields",
}

REQUIRED_NCU_COMPONENT_CANDIDATES = {
    "tensor_increment_candidate",
    "register_control_candidate",
    "shared_memory_path",
    "global_l1_hit_path",
    "l2_hit_path",
}

NCU_ACCEPTANCE_BASE_REQUIRED_COLUMNS = {
    "mode",
    "status",
    "component_candidate",
    "acceptance",
    "acceptance_reason",
    "l1_hit_rate_pct",
    "l2_hit_rate_pct",
    "shared_accesses",
    "shared_bytes",
    "shared_inst",
    "l1_bytes",
    "l2_bytes",
    "dram_bytes",
    "tensor_hmma_inst",
    "stall_long_scoreboard_pct",
}

NCU_ACCEPTANCE_PATH_REQUIRED_COLUMNS = {
    "l1_path_hit_rate_pct",
    "l2_path_hit_rate_pct",
    "l1_request_bytes",
    "l1_hit_bytes",
    "l1_miss_bytes",
    "l2_read_bytes",
    "l2_read_hit_sectors",
    "l2_read_miss_sectors",
    "local_read_bytes",
    "local_write_bytes",
    "spill_zero_verified",
    "spill_evidence_source",
}

NCU_ACCEPTANCE_REQUIRED_COLUMNS = (
    NCU_ACCEPTANCE_BASE_REQUIRED_COLUMNS | NCU_ACCEPTANCE_PATH_REQUIRED_COLUMNS
)

FABRIC_L2_REQUIRED_COLUMNS = {
    "l2_logical_read_hit_rate_pct",
    "l2_fabric_metrics_present",
    "l2_fabric_counter_coherent",
    "l2_fabric_model_coherent",
    "l2_native_vs_fabric_model_hit_delta_pct",
    "dram_read_bytes",
}

NCU_L1_HIT_MIN_PCT = 95.0
NCU_L1_L2_RATIO_MAX = 0.01
NCU_L1_DRAM_RATIO_MAX = 0.01
NCU_L2_L1_BYTES_RATIO_MAX = 0.01
NCU_L2_L1_HIT_MAX_PCT = 1.0
NCU_L2_HIT_MIN_PCT = 95.0
NCU_L2_DRAM_RATIO_MAX = 0.02
NCU_SHARED_GLOBAL_RATIO_MAX = 0.02
NCU_TENSOR_MEMORY_BYTES_PER_HMMA_MAX = 1.0
NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX = 1.0
NCU_CONTROL_HMMA_PER_BLOCK_MAX = 1.0
NCU_CONTROL_HMMA_PER_REG_OP_MAX = 1.0e-5
PROFILE_L2_MIB = {"rtx3090": 6.0, "v100": 6.0, "a100": 40.0, "h100": 50.0}

SUMMARY_BASE_REQUIRED_COLUMNS = {
    "component",
    "median",
    "unit",
    "rows_used",
    "valid_detail_rows",
    "invalid_detail_rows",
    "ncu_denominator_rows",
    "ncu_accepted_rows",
    "reliability_status",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "power_semantics",
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
    "ncu_l2_hit_rate_pct_min_med_max",
    "ncu_l1_accesses_min_med_max",
    "ncu_l2_accesses_min_med_max",
    "ncu_dram_accesses_min_med_max",
    "ncu_l1_bytes_min_med_max",
    "ncu_l2_bytes_min_med_max",
    "ncu_dram_bytes_min_med_max",
    "ncu_tensor_hmma_inst_min_med_max",
    "ncu_stall_long_scoreboard_pct_min_med_max",
}

SUMMARY_PATH_REQUIRED_COLUMNS = {
    "ncu_l1_path_hit_rate_pct_min_med_max",
    "ncu_l2_path_hit_rate_pct_min_med_max",
    "ncu_l1_request_bytes_min_med_max",
    "ncu_l1_hit_bytes_min_med_max",
    "ncu_l1_miss_bytes_min_med_max",
    "ncu_l2_read_bytes_min_med_max",
    "ncu_l2_read_hit_sectors_min_med_max",
    "ncu_l2_read_miss_sectors_min_med_max",
    "ncu_local_read_bytes_min_med_max",
    "ncu_local_write_bytes_min_med_max",
    "ncu_spill_zero_verified_min_med_max",
}

SUMMARY_REQUIRED_COLUMNS = SUMMARY_BASE_REQUIRED_COLUMNS | SUMMARY_PATH_REQUIRED_COLUMNS

STRICT_SUMMARY_EVIDENCE_MODES = {
    "Tensor MMA incremental": {"reg_mma", "reg_operand_only"},
    "Shared scalar path": {
        "shared_scalar_load_only",
        "shared_scalar_addr_only",
    },
    "Global L1 hit path": {"global_l1_load_only", "global_addr_only"},
    "L2 CG hit path": {"l2_cg_load_only", "global_addr_only"},
}

STRICT_SUMMARY_METRIC_MODES = {
    "Tensor MMA incremental": {"reg_mma"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only"},
    "L2 CG hit path": {"l2_cg_load_only"},
}

STRICT_SUMMARY_BASE_REQUIRED_METRICS = {
    "Tensor MMA incremental": {"ncu_tensor_hmma_inst_min_med_max"},
    "Shared scalar path": {"ncu_shared_bytes_min_med_max"},
    "Global L1 hit path": {
        "ncu_l1_hit_rate_pct_min_med_max",
        "ncu_l1_accesses_min_med_max",
        "ncu_l1_bytes_min_med_max",
    },
    "L2 CG hit path": {
        "ncu_l2_hit_rate_pct_min_med_max",
        "ncu_l2_accesses_min_med_max",
        "ncu_l2_bytes_min_med_max",
    },
}

STRICT_SUMMARY_PATH_REQUIRED_METRICS = {
    "Tensor MMA incremental": {
        "ncu_tensor_hmma_inst_min_med_max",
        "ncu_spill_zero_verified_min_med_max",
    },
    "Shared scalar path": {"ncu_shared_bytes_min_med_max"},
    "Global L1 hit path": {
        "ncu_l1_path_hit_rate_pct_min_med_max",
        "ncu_l1_accesses_min_med_max",
        "ncu_l1_request_bytes_min_med_max",
        "ncu_l1_hit_bytes_min_med_max",
    },
    "L2 CG hit path": {
        "ncu_l1_path_hit_rate_pct_min_med_max",
        "ncu_l1_request_bytes_min_med_max",
        "ncu_l1_hit_bytes_min_med_max",
        "ncu_l2_path_hit_rate_pct_min_med_max",
        "ncu_l2_accesses_min_med_max",
        "ncu_l2_read_bytes_min_med_max",
        "ncu_l2_read_hit_sectors_min_med_max",
        "ncu_l2_read_miss_sectors_min_med_max",
    },
}

POWER_STATE_REQUIRED_COLUMNS = {
    "input_file",
    "row_index",
    "run_id",
    "mode",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "elapsed_s",
    "net_E_J",
    "average_power_W",
    "group_rows",
    "group_power_median_W",
    "temp_C",
    "clock_sm_mhz",
    "status",
    "coefficient_eligible",
    "reasons",
    "notes",
}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def command_ok(command: str) -> tuple[bool, str]:
    path = shutil.which(command)
    if not path:
        return False, "not found in PATH"
    return True, path


def run_command(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def add(
    rows: list[dict[str, str]],
    *,
    area: str,
    check: str,
    status: str,
    expected: str,
    actual: str,
    evidence: str,
    next_action: str,
) -> None:
    rows.append(
        {
            "area": area,
            "check": check,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "next_action": next_action,
        }
    )


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def command_tag_from_rows(rows: list[dict[str, str]], profile: str) -> str:
    prefix = f"{profile}_component_finalplan_"
    suffix = "_commands.sh"
    for row in rows:
        if row.get("area") != profile or row.get("check") != "platform_command_package":
            continue
        shell = row.get("evidence", "").split(";")[0]
        name = Path(shell).name
        if name.startswith(prefix) and name.endswith(suffix):
            return name[len(prefix) : -len(suffix)]
    return "YYYYMMDD"


def missing_external_profiles(rows: list[dict[str, str]]) -> list[str]:
    profiles: list[str] = []
    for row in rows:
        if (
            row.get("check") == "platform_component_summary"
            and row.get("status") == "missing"
            and row.get("area") in COMMAND_PACKAGE_PROFILES
        ):
            profiles.append(row["area"])
    return profiles


def expected_intake_artifacts(profile: str, tag: str) -> list[tuple[str, str, str]]:
    base = f"{profile}_component_finalplan_{tag}"
    strict = f"{profile}_strict_scope_fresh_ncu_component"
    return [
        (
            "preflight",
            f"results/summary/{base}_preflight.md",
            "profile, driver/NVML, power scope, NCU support, and dry-run success",
        ),
        (
            "raw energy CSVs",
            f"results/raw/{base}_tensor.csv, _shared.csv, _l1.csv, _l2.csv, _dram.csv",
            "NVML total-energy rows and explicit measurement scope",
        ),
        (
            "pair calibration manifests",
            f"results/raw/{base}_tensor_pair_calibration.csv, "
            "_l2_pair_calibration.csv, _dram_pair_calibration.csv",
            "resolved treatment/control ITER and identical-work policy evidence",
        ),
        (
            "power API audit",
            f"results/summary/{base}_power_api_audit.csv",
            "all final rows must be final_candidate total-energy GPU/device rows",
        ),
        (
            "power-state audit",
            f"results/summary/{base}_power_state_audit.csv",
            "reject and coefficient-ineligible rows must be absent or excluded before pairing",
        ),
        (
            "NCU sidecar summary",
            f"results/ncu/{profile}_component_finalplan_ncu_factor_{tag}/ncu_cache_validation_summary.csv",
            "fresh path counters, hit rates, bytes, stalls, and spills",
        ),
        (
            "NCU path acceptance",
            f"results/summary/{base}_ncu_acceptance.csv",
            "accepted tensor/control/shared/global-L1/L2 candidates",
        ),
        (
            "matched-control detail/summary",
            f"results/summary/{base}_matched_control_detail.csv, _matched_control_summary.csv",
            "delta_E and pJ/FLOP or pJ/bit coefficients with NCU denominators",
        ),
        (
            "component reliability",
            f"results/summary/{base}_component_reliability_audit.csv",
            "component-level accepted/reject verdicts",
        ),
        (
            "instability audit",
            f"results/summary/{base}_matched_control_instability_audit.csv",
            "weak-signal, negative, or noisy row root-cause summary",
        ),
        (
            "strict component summary",
            f"results/summary/{strict}_coefficients_{tag}.csv",
            "reporting table generated only from accepted reliability evidence",
        ),
        (
            "strict summary audit",
            f"results/summary/{strict}_summary_audit_{tag}.csv",
            "0 fail and 0 warning rows required before publication",
        ),
        (
            "platform package audit",
            f"results/summary/{profile}_platform_result_package_audit_{tag}.csv",
            "0 fail and 0 missing rows required before goal readiness",
        ),
    ]


def write_external_intake_section(f, rows: list[dict[str, str]]) -> None:
    profiles = missing_external_profiles(rows)
    if not profiles:
        return

    f.write("\n## External Platform Result Intake Checklist\n\n")
    f.write(
        "The remaining missing rows are external platform result packages. "
        "A command package being present only proves that the experiment can be "
        "run; it does not prove measured A100/V100/H100 coefficients. When a "
        "platform run finishes, bring back the artifacts below and rerun this "
        "goal readiness audit.\n\n"
    )
    for profile in profiles:
        semantics = PROFILES[profile]
        tag = command_tag_from_rows(rows, profile)
        shell = f"results/summary/{profile}_component_finalplan_{tag}_commands.sh"
        f.write(f"### {profile.upper()}\n\n")
        f.write(f"- expected power semantics: `{semantics}`\n")
        f.write(f"- command package: `{shell}`\n")
        f.write(
            "- final numerator gate: `energy_source=nvml_total_energy`, "
            "`energy_integration_method=total_energy_mj_delta`, "
            "`measurement_scope=gpu_device_total_energy_counter`\n"
        )
        f.write(
            "- NCU gate: tensor/control/shared/global-L1/L2 path candidates must "
            "be accepted with matching W_SM, blocks/SM, active SM, and factor rows\n\n"
        )
        f.write("| artifact group | expected path pattern | proves |\n")
        f.write("|---|---|---|\n")
        for group, pattern, meaning in expected_intake_artifacts(profile, tag):
            f.write(f"| {group} | `{pattern}` | {meaning} |\n")
        f.write("\n")


def latest_platform_summary(repo: Path, profile: str) -> Path | None:
    patterns = [
        f"results/summary/{profile}_strict_scope_fresh_ncu_component_coefficients_*.csv",
        f"results/summary/{profile}_strict_scope_component_coefficients_*.csv",
        f"results/summary/{profile}_component_coefficients_*.csv",
        f"results/summary/{profile}_current_reporting_component_coefficients_*.csv",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(repo.glob(pattern))
    return sorted(candidates)[-1] if candidates else None


def latest_artifact(repo: Path, patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(repo.glob(pattern))
    return sorted(candidates)[-1] if candidates else None


def referenced_artifacts(repo: Path, rows: list[dict[str, str]], column: str) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for row in rows:
        value = row.get(column, "")
        for item in value.split(";"):
            item = item.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            paths.append(repo / item)
    return paths


def parse_positive_float(value: str) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def parse_float(value: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def parse_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def ncu_value(row: dict[str, str], column: str, default: float = 0.0) -> float:
    value = parse_float(row.get(column, ""))
    return value if math.isfinite(value) else default


def ncu_ratio(num: float, den: float) -> float:
    return num / den if den > 0.0 else math.inf


def ncu_expected_ops(row: dict[str, str]) -> float:
    active_sm = ncu_value(row, "active_SM")
    blocks = ncu_value(row, "blocks_per_SM")
    iters = ncu_value(row, "ITER")
    reuse = ncu_value(row, "reuse_factor", 1.0)
    return active_sm * blocks * iters * reuse


def ncu_expected_l2_residency_hit_pct(row: dict[str, str], profile: str) -> float:
    working_set_mib = ncu_value(row, "active_SM") * ncu_value(row, "W_SM_KiB") / 1024.0
    l2_mib = PROFILE_L2_MIB.get(profile, 0.0)
    if working_set_mib <= 0.0 or l2_mib <= 0.0:
        return 0.0
    return min(100.0, 100.0 * l2_mib / working_set_mib)


def ncu_path_sanity_pass(
    row: dict[str, str],
    *,
    profile: str,
    require_path_specific_cache_evidence: bool,
) -> bool:
    mode = row.get("mode", "")
    if row.get("status") != "ok" or row.get("missing_metrics", "").strip():
        return False

    has_path_specific_cache_evidence = all(
        column in row for column in NCU_ACCEPTANCE_PATH_REQUIRED_COLUMNS
    )
    if require_path_specific_cache_evidence and not has_path_specific_cache_evidence:
        return False

    l1_hit = ncu_value(
        row,
        "l1_path_hit_rate_pct" if has_path_specific_cache_evidence else "l1_hit_rate_pct",
        -1.0,
    )
    l2_hit = ncu_value(
        row,
        "l2_path_hit_rate_pct" if has_path_specific_cache_evidence else "l2_hit_rate_pct",
        -1.0,
    )
    l1_bytes = ncu_value(row, "l1_bytes")
    l1_request_bytes = ncu_value(row, "l1_request_bytes")
    l1_hit_bytes = ncu_value(row, "l1_hit_bytes")
    l2_bytes = ncu_value(row, "l2_bytes")
    l2_read_bytes = ncu_value(row, "l2_read_bytes")
    l2_traffic_bytes = l2_read_bytes if has_path_specific_cache_evidence else l2_bytes
    dram_bytes = ncu_value(row, "dram_bytes")
    dram_read_bytes = ncu_value(row, "dram_read_bytes", math.nan)
    effective_dram_read_bytes = (
        dram_read_bytes
        if math.isfinite(dram_read_bytes)
        else (math.nan if profile in FABRIC_AWARE_L2_PROFILES else dram_bytes)
    )
    shared_bytes = ncu_value(row, "shared_bytes")
    shared_accesses = ncu_value(row, "shared_accesses")
    shared_inst = ncu_value(row, "shared_inst")
    tensor_hmma = ncu_value(row, "tensor_hmma_inst")
    local_read_bytes = ncu_value(row, "local_read_bytes")
    local_write_bytes = ncu_value(row, "local_write_bytes")
    spill_zero_verified = ncu_value(row, "spill_zero_verified", -1.0)

    if has_path_specific_cache_evidence and (
        local_read_bytes > 0.0
        or local_write_bytes > 0.0
        or spill_zero_verified != 1.0
    ):
        return False

    if mode == "global_l1_load_only":
        if not has_path_specific_cache_evidence:
            return (
                l1_hit >= NCU_L1_HIT_MIN_PCT
                and l1_bytes > 0.0
                and ncu_ratio(l2_bytes, l1_bytes) <= NCU_L1_L2_RATIO_MAX
                and ncu_ratio(dram_bytes, l1_bytes) <= NCU_L1_DRAM_RATIO_MAX
            )
        return (
            l1_hit >= NCU_L1_HIT_MIN_PCT
            and l1_request_bytes > 0.0
            and l1_hit_bytes > 0.0
            and ncu_ratio(l2_read_bytes, l1_request_bytes) <= NCU_L1_L2_RATIO_MAX
            and ncu_ratio(dram_bytes, l1_request_bytes) <= NCU_L1_DRAM_RATIO_MAX
        )
    if mode == "l2_cg_load_only":
        if not has_path_specific_cache_evidence:
            # Historical NCU exports did not distinguish request bytes from hit
            # bytes. For .cg, L1 request bytes are expected, so the old aggregate
            # L1/L2 byte ratio is not a valid bypass gate. Preserve only rows with
            # near-zero aggregate L1 hit, high L2 hit, and little DRAM traffic.
            return (
                l2_hit >= NCU_L2_HIT_MIN_PCT
                and l2_bytes > 0.0
                and 0.0 <= l1_hit <= NCU_L2_L1_HIT_MAX_PCT
                and ncu_ratio(dram_bytes, l2_bytes) <= NCU_L2_DRAM_RATIO_MAX
            )
        accepted_l2_hit = (
            ncu_value(row, "l2_logical_read_hit_rate_pct", -1.0)
            if profile in FABRIC_AWARE_L2_PROFILES
            else l2_hit
        )
        fabric_ok = True
        if profile in FABRIC_AWARE_L2_PROFILES:
            fabric_ok = (
                ncu_value(row, "l2_fabric_metrics_present", 0.0) == 1.0
                and ncu_value(row, "l2_fabric_counter_coherent", -1.0)
                == 1.0
                and ncu_value(row, "l2_fabric_model_coherent", -1.0) == 1.0
                and ncu_value(
                    row,
                    "l2_native_vs_fabric_model_hit_delta_pct",
                    math.inf,
                )
                <= 2.0
            )
        return (
            NCU_L2_HIT_MIN_PCT <= accepted_l2_hit <= 100.5
            and fabric_ok
            and l2_read_bytes > 0.0
            and l1_request_bytes > 0.0
            and l1_hit >= 0.0
            and l1_hit <= NCU_L2_L1_HIT_MAX_PCT
            and ncu_ratio(l1_hit_bytes, l1_request_bytes)
            <= NCU_L2_L1_BYTES_RATIO_MAX
            and math.isfinite(effective_dram_read_bytes)
            and ncu_ratio(effective_dram_read_bytes, l2_read_bytes)
            <= NCU_L2_DRAM_RATIO_MAX
        )
    if mode in {"shared_scalar_load_only", "shared_load_only"}:
        denominator = max(shared_bytes, 1.0)
        return (
            shared_accesses > 0.0
            and shared_bytes > 0.0
            and shared_inst > 0.0
            and ncu_ratio(l1_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
            and ncu_ratio(l2_traffic_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
            and ncu_ratio(dram_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
        )
    if mode == "reg_mma":
        if tensor_hmma <= 0.0:
            return False
        return (
            ncu_ratio(l2_traffic_bytes, tensor_hmma)
            <= NCU_TENSOR_MEMORY_BYTES_PER_HMMA_MAX
            and ncu_ratio(dram_bytes, tensor_hmma)
            <= NCU_TENSOR_MEMORY_BYTES_PER_HMMA_MAX
        )
    if mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}:
        expected_ops = ncu_expected_ops(row)
        if mode == "reg_operand_only" and tensor_hmma > 0.0:
            return False
        fixed_epilogue_limit = (
            ncu_value(row, "active_SM")
            * ncu_value(row, "blocks_per_SM")
            * NCU_CONTROL_HMMA_PER_BLOCK_MAX
        )
        if (
            tensor_hmma > fixed_epilogue_limit
            and ncu_ratio(tensor_hmma, expected_ops) > NCU_CONTROL_HMMA_PER_REG_OP_MAX
        ):
            return False
        if expected_ops <= 0.0:
            return True
        return (
            ncu_ratio(l2_traffic_bytes, expected_ops)
            <= NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX
            and ncu_ratio(dram_bytes, expected_ops)
            <= NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX
        )
    if mode == "clocked_empty":
        return True
    return False


def validate_component_summary(
    summary_rows: list[dict[str, str]],
    *,
    expected_semantics: str,
    require_path_specific_cache_evidence: bool,
) -> tuple[bool, str]:
    if not summary_rows:
        return False, "empty_summary"

    required_columns = set(SUMMARY_BASE_REQUIRED_COLUMNS)
    required_metrics = STRICT_SUMMARY_BASE_REQUIRED_METRICS
    if require_path_specific_cache_evidence:
        required_columns.update(SUMMARY_PATH_REQUIRED_COLUMNS)
        required_metrics = STRICT_SUMMARY_PATH_REQUIRED_METRICS
    missing_columns = sorted(
        column for column in required_columns if column not in summary_rows[0]
    )
    if missing_columns:
        return False, "missing_columns=" + ",".join(missing_columns)

    by_component = {row.get("component", ""): row for row in summary_rows}
    missing_components = sorted(set(STRICT_COMPONENTS) - set(by_component))
    unexpected_components = sorted(set(by_component) - set(STRICT_COMPONENTS))
    problems: list[str] = []
    if missing_components:
        problems.append("missing_components=" + ",".join(missing_components))
    if unexpected_components:
        problems.append("unexpected_components=" + ",".join(unexpected_components))

    for component, expected_unit in STRICT_COMPONENTS.items():
        row = by_component.get(component)
        if not row:
            continue

        if row.get("unit") != expected_unit:
            problems.append(f"{component}:unit={row.get('unit')}")
        median = parse_float(row.get("median", ""))
        if not (median > 0.0):
            problems.append(f"{component}:median_not_positive")
        lo, hi, range_unit = HARD_PLAUSIBILITY_RANGES[component]
        if row.get("unit") == range_unit and not (lo <= median <= hi):
            problems.append(f"{component}:plausibility={median:g}{range_unit}")
        if row.get("reliability_status") != "accepted":
            problems.append(f"{component}:reliability={row.get('reliability_status')}")
        if row.get("energy_source") != "nvml_total_energy":
            problems.append(f"{component}:energy_source={row.get('energy_source')}")
        if row.get("energy_integration_method") != "total_energy_mj_delta":
            problems.append(f"{component}:integration={row.get('energy_integration_method')}")
        if row.get("measurement_scope") != "gpu_device_total_energy_counter":
            problems.append(f"{component}:scope={row.get('measurement_scope')}")
        if row.get("power_semantics") != expected_semantics:
            problems.append(f"{component}:semantics={row.get('power_semantics')}")

        rows_used = parse_int(row.get("rows_used", ""))
        valid_rows = parse_int(row.get("valid_detail_rows", ""))
        invalid_rows = parse_int(row.get("invalid_detail_rows", ""))
        ncu_accepted_rows = parse_int(row.get("ncu_accepted_rows", ""))
        ncu_denominator_rows = parse_int(row.get("ncu_denominator_rows", ""))
        if rows_used is None or rows_used <= 0:
            problems.append(f"{component}:rows_used={row.get('rows_used')}")
        if valid_rows is None or valid_rows <= 0:
            problems.append(f"{component}:valid_detail_rows={row.get('valid_detail_rows')}")
        if invalid_rows is None or invalid_rows != 0:
            problems.append(f"{component}:invalid_detail_rows={row.get('invalid_detail_rows')}")
        if ncu_accepted_rows is None or ncu_accepted_rows <= 0:
            problems.append(f"{component}:ncu_accepted_rows={row.get('ncu_accepted_rows')}")
        if expected_unit == "pJ/bit" and (
            ncu_denominator_rows is None or ncu_denominator_rows <= 0
        ):
            problems.append(
                f"{component}:ncu_denominator_rows={row.get('ncu_denominator_rows')}"
            )
        coordinate_rows = parse_int(row.get("ncu_coordinate_rows", ""))
        metric_rows = parse_int(row.get("ncu_metric_rows", ""))
        if coordinate_rows is None or coordinate_rows <= 0:
            problems.append(f"{component}:ncu_coordinate_rows={row.get('ncu_coordinate_rows')}")
        if metric_rows is None or metric_rows <= 0:
            problems.append(f"{component}:ncu_metric_rows={row.get('ncu_metric_rows')}")
        evidence_modes = {
            item.strip()
            for item in row.get("ncu_evidence_modes", "").split(",")
            if item.strip()
        }
        missing_modes = sorted(STRICT_SUMMARY_EVIDENCE_MODES.get(component, set()) - evidence_modes)
        if missing_modes:
            problems.append(f"{component}:missing_evidence_modes={','.join(missing_modes)}")
        metric_modes = {
            item.strip()
            for item in row.get("ncu_metric_modes", "").split(",")
            if item.strip()
        }
        missing_metric_modes = sorted(
            STRICT_SUMMARY_METRIC_MODES.get(component, set()) - metric_modes
        )
        if missing_metric_modes:
            problems.append(
                f"{component}:missing_metric_modes={','.join(missing_metric_modes)}"
            )
        for evidence_column in ("ncu_evidence_coords", "ncu_path_evidence", "ncu_counter_caveat"):
            if not row.get(evidence_column, "").strip():
                problems.append(f"{component}:{evidence_column}=blank")
        for evidence_column in required_metrics.get(component, set()):
            if not row.get(evidence_column, "").strip():
                problems.append(f"{component}:{evidence_column}=blank")
        if expected_unit == "pJ/bit":
            denominator_source = row.get("denominator_source", "")
            if "ncu_actual_exact" not in denominator_source.split(","):
                problems.append(f"{component}:denominator_source={denominator_source}")
            if not row.get("ncu_denominator_bytes_representative_min_med_max", "").strip():
                problems.append(
                    f"{component}:ncu_denominator_bytes_representative_min_med_max=blank"
                )

    shared = parse_float(by_component.get("Shared scalar path", {}).get("median", ""))
    l1 = parse_float(by_component.get("Global L1 hit path", {}).get("median", ""))
    l2 = parse_float(by_component.get("L2 CG hit path", {}).get("median", ""))
    if math.isfinite(l2) and math.isfinite(shared) and not (l2 > shared):
        problems.append(f"hierarchy:l2_not_greater_than_shared:L2={l2:g},Shared={shared:g}")
    if math.isfinite(l2) and math.isfinite(l1) and not (l2 > l1):
        problems.append(f"hierarchy:l2_not_greater_than_l1:L2={l2:g},L1={l1:g}")
    if math.isfinite(shared) and math.isfinite(l1):
        ratio = max(shared, l1) / max(min(shared, l1), 1.0e-30)
        if ratio > 2.0:
            problems.append(f"hierarchy:shared_l1_ratio={ratio:g}")

    return not problems, "ok" if not problems else ";".join(problems)


def validate_reliability_artifacts(
    repo: Path,
    summary_rows: list[dict[str, str]],
    profile: str,
    expected_semantics: str,
) -> tuple[bool, str, str]:
    artifacts = referenced_artifacts(repo, summary_rows, "reliability_artifact")
    if not artifacts:
        latest = latest_artifact(
            repo,
            [
                f"results/summary/{profile}_strict_scope_fresh_ncu_component_reliability_audit_*.csv",
                f"results/summary/{profile}_strict_scope_component_reliability_audit_*.csv",
                f"results/summary/{profile}_component_reliability_audit_*.csv",
            ],
        )
        artifacts = [latest] if latest else []

    if not artifacts:
        return False, "missing_reliability_artifact", "results/summary"

    missing = [str(path) for path in artifacts if path and not path.exists()]
    if missing:
        return False, "missing_files=" + ";".join(missing), ";".join(str(p) for p in artifacts)

    problems: list[str] = []
    accepted_components: set[str] = set()
    for artifact in artifacts:
        for row in read_csv(artifact):
            component = row.get("component", "")
            status = row.get("status", "")
            if status == "reject":
                problems.append(f"{artifact}:{component}:reject")
            if status == "accepted":
                accepted_components.add(component)
            if row.get("energy_source", "") and row.get("energy_source") != "nvml_total_energy":
                problems.append(f"{artifact}:{component}:energy_source={row.get('energy_source')}")
            if row.get("energy_integration_method", "") and row.get(
                "energy_integration_method"
            ) != "total_energy_mj_delta":
                problems.append(
                    f"{artifact}:{component}:integration={row.get('energy_integration_method')}"
                )
            if row.get("measurement_scope", "") and row.get(
                "measurement_scope"
            ) != "gpu_device_total_energy_counter":
                problems.append(f"{artifact}:{component}:scope={row.get('measurement_scope')}")
            if row.get("power_semantics", "") and row.get("power_semantics") != expected_semantics:
                problems.append(f"{artifact}:{component}:semantics={row.get('power_semantics')}")

    if len(accepted_components) < 4:
        problems.append(f"accepted_component_count={len(accepted_components)}")
    return (
        not problems,
        "ok" if not problems else ";".join(problems),
        ";".join(str(path) for path in artifacts),
    )


def validate_ncu_acceptance_artifacts(
    repo: Path,
    summary_rows: list[dict[str, str]],
    profile: str,
    *,
    require_path_specific_cache_evidence: bool,
) -> tuple[bool, str, str]:
    artifacts = referenced_artifacts(repo, summary_rows, "ncu_acceptance_artifact")
    if not artifacts:
        latest = latest_artifact(
            repo,
            [
                f"results/summary/{profile}_strict_scope_fresh_ncu_combined_acceptance_*.csv",
                f"results/summary/{profile}_strict_scope_fresh_ncu_acceptance_*.csv",
                f"results/summary/{profile}_ncu_acceptance_*.csv",
            ],
        )
        artifacts = [latest] if latest else []

    if not artifacts:
        return False, "missing_ncu_acceptance_artifact", "results/summary"

    missing = [str(path) for path in artifacts if path and not path.exists()]
    if missing:
        return False, "missing_files=" + ";".join(missing), ";".join(str(p) for p in artifacts)

    accepted_candidates: set[str] = set()
    unexpected_rejects: list[str] = []
    problems: list[str] = []
    required_columns = set(NCU_ACCEPTANCE_BASE_REQUIRED_COLUMNS)
    if require_path_specific_cache_evidence:
        required_columns.update(NCU_ACCEPTANCE_PATH_REQUIRED_COLUMNS)
    if profile in FABRIC_AWARE_L2_PROFILES:
        required_columns.update(FABRIC_L2_REQUIRED_COLUMNS)
    for artifact in artifacts:
        with artifact.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = sorted(required_columns - fieldnames)
            if missing_columns:
                problems.append(
                    f"{artifact}:missing_columns=" + ",".join(missing_columns)
                )
            artifact_rows = list(reader)
        for row in artifact_rows:
            candidate = row.get("component_candidate", "")
            acceptance = row.get("acceptance", "")
            mode = row.get("mode", "")
            if acceptance == "accepted":
                accepted_candidates.add(candidate)
                if candidate in REQUIRED_NCU_COMPONENT_CANDIDATES:
                    if row.get("acceptance_reason") != "pass":
                        problems.append(
                            f"{artifact}:{mode}:{candidate}:reason="
                            f"{row.get('acceptance_reason')}"
                        )
                    if not ncu_path_sanity_pass(
                        row,
                        profile=profile,
                        require_path_specific_cache_evidence=(
                            require_path_specific_cache_evidence
                        ),
                    ):
                        problems.append(
                            f"{artifact}:{mode}:{candidate}:path_evidence_failed"
                        )
            elif acceptance == "rejected" and candidate != "not_selected":
                unexpected_rejects.append(f"{artifact}:{mode}:{candidate}")

    missing_candidates = sorted(REQUIRED_NCU_COMPONENT_CANDIDATES - accepted_candidates)
    if missing_candidates:
        problems.append("missing_candidates=" + ",".join(missing_candidates))
    if unexpected_rejects:
        problems.append("unexpected_rejects=" + ";".join(unexpected_rejects))
    return (
        not problems,
        "ok" if not problems else ";".join(problems),
        ";".join(str(path) for path in artifacts),
    )


def inferred_summary_audit_path(summary: Path) -> Path | None:
    name = summary.name
    if "_component_coefficients_" in name:
        return summary.with_name(
            name.replace("_component_coefficients_", "_component_summary_audit_")
        )
    return None


def validate_summary_audit_artifact(summary: Path) -> tuple[bool, str, str]:
    audit_path = inferred_summary_audit_path(summary)
    if audit_path is None:
        return False, "cannot_infer_summary_audit_path", str(summary)
    if not audit_path.exists():
        return False, "missing_summary_audit_artifact", str(audit_path)

    audit_rows = read_csv(audit_path)
    failures = [row for row in audit_rows if row.get("status", "") == "fail"]
    warnings = [row for row in audit_rows if row.get("status", "") == "warning"]
    seen_checks = {row.get("check", "") for row in audit_rows}
    missing_required_checks = sorted(STRICT_AUDIT_REQUIRED_CHECKS - seen_checks)
    if failures or warnings or missing_required_checks:
        return (
            False,
            (
                f"rows={len(audit_rows)}, failures={len(failures)}, "
                f"warnings={len(warnings)}"
                if not missing_required_checks
                else (
                    f"rows={len(audit_rows)}, failures={len(failures)}, "
                    f"warnings={len(warnings)}, missing_checks="
                    + ",".join(missing_required_checks)
                )
            ),
            str(audit_path),
        )
    return True, f"rows={len(audit_rows)}, failures=0, warnings=0", str(audit_path)


def validate_power_api_artifacts(
    repo: Path,
    summary_rows: list[dict[str, str]],
    profile: str,
    expected_semantics: str,
) -> tuple[bool, str, str]:
    artifacts = referenced_artifacts(repo, summary_rows, "power_api_audit_artifact")
    if not artifacts:
        latest = latest_artifact(
            repo,
            [
                f"results/summary/{profile}_strict_scope_fresh_ncu*_power_api_audit_*.csv",
                f"results/summary/{profile}_component_finalplan_*_power_api_audit.csv",
                f"results/summary/{profile}_*_power_api_audit_*.csv",
            ],
        )
        artifacts = [latest] if latest else []

    if not artifacts:
        return False, "missing_power_api_audit_artifact", "results/summary"

    missing = [str(path) for path in artifacts if path and not path.exists()]
    if missing:
        return False, "missing_files=" + ";".join(missing), ";".join(str(p) for p in artifacts)

    problems: list[str] = []
    row_count = 0
    for artifact in artifacts:
        for row in read_csv(artifact):
            row_count += 1
            if row.get("status", "") != "final_candidate":
                problems.append(f"{artifact}:status={row.get('status', '')}")
            if row.get("energy_source", "") != "nvml_total_energy":
                problems.append(f"{artifact}:energy_source={row.get('energy_source', '')}")
            if row.get("energy_integration_method", "") != "total_energy_mj_delta":
                problems.append(
                    f"{artifact}:integration={row.get('energy_integration_method', '')}"
                )
            if row.get("measurement_scope", "") != "gpu_device_total_energy_counter":
                problems.append(f"{artifact}:scope={row.get('measurement_scope', '')}")
            if row.get("actual_power_semantics", "") != expected_semantics:
                problems.append(f"{artifact}:semantics={row.get('actual_power_semantics', '')}")

    if row_count <= 0:
        problems.append("power_api_audit_empty")
    return (
        not problems,
        f"rows={row_count}" if not problems else ";".join(problems[:8]),
        ";".join(str(path) for path in artifacts),
    )


def validate_power_state_artifacts(
    repo: Path, summary_rows: list[dict[str, str]], profile: str
) -> tuple[bool, str, str]:
    artifacts = referenced_artifacts(repo, summary_rows, "power_state_audit_artifact")
    if not artifacts:
        latest = latest_artifact(
            repo,
            [
                f"results/summary/{profile}_strict_scope_fresh_ncu*_power_state_audit_*.csv",
                f"results/summary/{profile}_component_finalplan_*_power_state_audit.csv",
                f"results/summary/{profile}_*_power_state_audit_*.csv",
            ],
        )
        artifacts = [latest] if latest else []

    if not artifacts:
        return False, "missing_power_state_audit_artifact", "results/summary"

    missing = [str(path) for path in artifacts if path and not path.exists()]
    if missing:
        return False, "missing_files=" + ";".join(missing), ";".join(str(p) for p in artifacts)

    problems: list[str] = []
    row_count = 0
    reject_count = 0
    ineligible_count = 0
    for artifact in artifacts:
        with artifact.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = sorted(POWER_STATE_REQUIRED_COLUMNS - fieldnames)
            if missing_columns:
                problems.append(
                    f"{artifact}:missing_columns=" + ",".join(missing_columns)
                )
            artifact_rows = list(reader)
        for idx, row in enumerate(artifact_rows, start=2):
            row_count += 1
            status = row.get("status", "")
            eligible = row.get("coefficient_eligible", "")
            location = f"{artifact}:{idx}:{row.get('run_id', '')}"
            if not status:
                problems.append(f"{location}:missing_status")
            if eligible.lower() not in {"true", "false"}:
                problems.append(f"{location}:missing_eligibility")
            if status == "reject":
                reject_count += 1
                problems.append(f"{location}:reject")
            if eligible.lower() == "false":
                ineligible_count += 1
                problems.append(f"{location}:ineligible")
            for column in ("W_SM_KiB", "blocks_per_SM", "active_SM", "elapsed_s"):
                value = parse_float(row.get(column, ""))
                if not (value > 0.0):
                    problems.append(f"{location}:{column}={row.get(column, '')}")
            net_e = parse_float(row.get("net_E_J", ""))
            if not (net_e >= 0.0):
                problems.append(f"{location}:net_E_J={row.get('net_E_J', '')}")
            for column in ("average_power_W", "group_power_median_W", "clock_sm_mhz"):
                value = parse_float(row.get(column, ""))
                if not (value > 0.0):
                    problems.append(f"{location}:{column}={row.get(column, '')}")
            temp_c = parse_float(row.get("temp_C", ""))
            if not math.isfinite(temp_c):
                problems.append(f"{location}:temp_C={row.get('temp_C', '')}")

    if row_count <= 0:
        problems.append("power_state_audit_empty")
    return (
        not problems,
        (
            f"rows={row_count}, reject={reject_count}, ineligible={ineligible_count}"
            if not problems
            else ";".join(problems[:8])
        ),
        ";".join(str(path) for path in artifacts),
    )


def write_test_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def selftest_power_state_row(**overrides: str) -> dict[str, str]:
    row = {
        "input_file": "results/raw/selftest.csv",
        "row_index": "2",
        "run_id": "selftest",
        "mode": "global_l1_load_only",
        "W_SM_KiB": "16",
        "blocks_per_SM": "16",
        "active_SM": "82",
        "elapsed_s": "30.0",
        "net_E_J": "100.0",
        "average_power_W": "300.0",
        "group_rows": "6",
        "group_power_median_W": "299.0",
        "temp_C": "72",
        "clock_sm_mhz": "1905",
        "status": "ok",
        "coefficient_eligible": "true",
        "reasons": "",
        "notes": "",
    }
    row.update(overrides)
    return row


def selftest_ncu_row(
    *,
    mode: str,
    candidate: str,
    acceptance_reason: str = "pass",
    **overrides: str,
) -> dict[str, str]:
    row = {
        "mode": mode,
        "status": "ok",
        "component_candidate": candidate,
        "acceptance": "accepted",
        "acceptance_reason": acceptance_reason,
        "missing_metrics": "",
        "active_SM": "82",
        "blocks_per_SM": "16",
        "ITER": "1000",
        "reuse_factor": "1",
        "l1_hit_rate_pct": "0",
        "l1_path_hit_rate_pct": "0",
        "l2_hit_rate_pct": "0",
        "l2_path_hit_rate_pct": "0",
        "shared_accesses": "0",
        "shared_bytes": "0",
        "shared_inst": "0",
        "l1_bytes": "0",
        "l1_request_bytes": "0",
        "l1_hit_bytes": "0",
        "l1_miss_bytes": "0",
        "l2_bytes": "0",
        "l2_read_bytes": "0",
        "l2_read_hit_sectors": "0",
        "l2_read_miss_sectors": "0",
        "local_read_bytes": "0",
        "local_write_bytes": "0",
        "spill_zero_verified": "1",
        "spill_evidence_source": "local_memory_bytes_zero_inference",
        "dram_bytes": "0",
        "tensor_hmma_inst": "0",
        "stall_long_scoreboard_pct": "0",
    }
    if mode == "reg_mma":
        row.update({"tensor_hmma_inst": "1000"})
    elif mode == "reg_operand_only":
        row.update({"tensor_hmma_inst": "0"})
    elif mode == "shared_scalar_load_only":
        row.update(
            {
                "shared_accesses": "100",
                "shared_bytes": "100000",
                "shared_inst": "100",
                "l1_bytes": "100",
                "l2_bytes": "100",
                "dram_bytes": "100",
            }
        )
    elif mode == "global_l1_load_only":
        row.update(
            {
                "l1_hit_rate_pct": "99.5",
                "l1_path_hit_rate_pct": "99.5",
                "l1_bytes": "100000",
                "l1_request_bytes": "100000",
                "l1_hit_bytes": "99500",
                "l1_miss_bytes": "500",
                "l2_bytes": "500",
                "l2_read_bytes": "500",
                "dram_bytes": "500",
            }
        )
    elif mode == "l2_cg_load_only":
        row.update(
            {
                "l1_hit_rate_pct": "0.0",
                "l1_path_hit_rate_pct": "0.0",
                "l2_hit_rate_pct": "99.0",
                "l2_path_hit_rate_pct": "99.0",
                "l1_request_bytes": "100000",
                "l1_hit_bytes": "0",
                "l1_miss_bytes": "100000",
                "l2_bytes": "100000",
                "l2_read_bytes": "100000",
                "l2_read_hit_sectors": "3093.75",
                "l2_read_miss_sectors": "31.25",
                "dram_bytes": "1000",
            }
        )
    row.update(overrides)
    return row


def selftest_ncu_rows() -> list[dict[str, str]]:
    return [
        selftest_ncu_row(
            mode="reg_mma", candidate="tensor_increment_candidate"
        ),
        selftest_ncu_row(
            mode="reg_operand_only", candidate="register_control_candidate"
        ),
        selftest_ncu_row(
            mode="shared_scalar_load_only", candidate="shared_memory_path"
        ),
        selftest_ncu_row(
            mode="global_l1_load_only", candidate="global_l1_hit_path"
        ),
        selftest_ncu_row(
            mode="l2_cg_load_only", candidate="l2_hit_path"
        ),
    ]


def assert_selftest(condition: bool, name: str, detail: str) -> None:
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def self_test() -> None:
    power_state_columns = sorted(POWER_STATE_REQUIRED_COLUMNS)
    ncu_columns = sorted(
        NCU_ACCEPTANCE_REQUIRED_COLUMNS
        | {"missing_metrics", "active_SM", "blocks_per_SM", "ITER", "reuse_factor"}
    )

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        runner = repo / LOCAL_READINESS_RUNNER
        runner.parent.mkdir(parents=True, exist_ok=True)
        good_runner_text = """#!/usr/bin/env bash
set -euo pipefail
TAG="${TAG:-20260715}"
A100_ACTIVE_SM="${A100_ACTIVE_SM:-108}"
V100_ACTIVE_SM="${V100_ACTIVE_SM:-80}"
H100_ACTIVE_SM="${H100_ACTIVE_SM:-132}"
echo "[readiness] external platform manifests, package audits, and gap reports"
for profile in a100 v100 h100; do
  active_sm="${A100_ACTIVE_SM:-108}"
  python3 scripts/write_platform_result_manifest.py \
    --target-profile "${profile}" \
    --tag "${TAG}" \
    --expected-active-sm "${active_sm}" \
    --out-csv "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv" \
    --out-md "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.md"
  python3 scripts/audit_platform_result_package.py \
    --target-profile "${profile}" \
    --expected-active-sm "${active_sm}"
  python3 scripts/summarize_platform_package_gaps.py \
    --target-profile "${profile}" \
    --tag "${TAG}" \
    --manifest-csv "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv"
done
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py
echo "[readiness] goal readiness"
python3 scripts/audit_component_goal_readiness.py
echo "[readiness] platform intake dashboard"
python3 scripts/build_platform_intake_dashboard.py
if [[ "${RUN_GIT_DIFF_CHECK:-1}" == "1" ]]; then
  git diff --check
fi
"""
        runner.write_text(good_runner_text, encoding="utf-8")
        ok, detail, _ = validate_local_readiness_runner(repo)
        assert_selftest(ok, "local_readiness_runner_good", detail)

        runner.write_text(
            good_runner_text.replace('--tag "${TAG}"', '--tag-missing "${TAG}"'),
            encoding="utf-8",
        )
        ok, detail, _ = validate_local_readiness_runner(repo)
        assert_selftest(
            (not ok) and "missing_terms=" in detail and '--tag "${TAG}"' in detail,
            "local_readiness_runner_missing_tag",
            detail,
        )

        power_good = Path("results/summary/power_state_good.csv")
        write_test_csv(
            repo / power_good,
            power_state_columns,
            [selftest_power_state_row()],
        )
        ok, detail, _ = validate_power_state_artifacts(
            repo, [{"power_state_audit_artifact": str(power_good)}], "rtx3090"
        )
        assert_selftest(ok, "power_state_good", detail)

        power_missing = Path("results/summary/power_state_missing_average.csv")
        missing_columns = [c for c in power_state_columns if c != "average_power_W"]
        write_test_csv(
            repo / power_missing,
            missing_columns,
            [selftest_power_state_row()],
        )
        ok, detail, _ = validate_power_state_artifacts(
            repo, [{"power_state_audit_artifact": str(power_missing)}], "rtx3090"
        )
        assert_selftest(
            (not ok) and "missing_columns=average_power_W" in detail,
            "power_state_missing_average",
            detail,
        )

        power_zero = Path("results/summary/power_state_zero_average.csv")
        write_test_csv(
            repo / power_zero,
            power_state_columns,
            [selftest_power_state_row(average_power_W="0")],
        )
        ok, detail, _ = validate_power_state_artifacts(
            repo, [{"power_state_audit_artifact": str(power_zero)}], "rtx3090"
        )
        assert_selftest(
            (not ok) and "average_power_W=0" in detail,
            "power_state_zero_average",
            detail,
        )

        ncu_good = Path("results/summary/ncu_acceptance_good.csv")
        write_test_csv(repo / ncu_good, ncu_columns, selftest_ncu_rows())
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_good)}],
            "rtx3090",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(ok, "ncu_acceptance_good", detail)

        fabric_ncu_columns = sorted(
            set(ncu_columns) | FABRIC_L2_REQUIRED_COLUMNS
        )
        fabric_rows = selftest_ncu_rows()
        for row in fabric_rows:
            if row["mode"] != "l2_cg_load_only":
                continue
            row.update(
                {
                    "l2_logical_read_hit_rate_pct": "99.5",
                    "l2_fabric_metrics_present": "1",
                    "l2_fabric_counter_coherent": "1",
                    "l2_fabric_model_coherent": "1",
                    "l2_native_vs_fabric_model_hit_delta_pct": "0",
                    "dram_read_bytes": "1000",
                }
            )
        ncu_h100 = Path("results/summary/ncu_acceptance_h100_fabric.csv")
        write_test_csv(repo / ncu_h100, fabric_ncu_columns, fabric_rows)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_h100)}],
            "h100",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(ok, "ncu_acceptance_h100_fabric_good", detail)

        for row in fabric_rows:
            if row["mode"] == "l2_cg_load_only":
                row["l2_fabric_metrics_present"] = "0"
        ncu_h100_bad = Path(
            "results/summary/ncu_acceptance_h100_missing_fabric.csv"
        )
        write_test_csv(repo / ncu_h100_bad, fabric_ncu_columns, fabric_rows)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_h100_bad)}],
            "h100",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(
            (not ok) and "path_evidence_failed" in detail,
            "ncu_acceptance_h100_missing_fabric",
            detail,
        )

        legacy_ncu_columns = sorted(
            NCU_ACCEPTANCE_BASE_REQUIRED_COLUMNS
            | {"missing_metrics", "active_SM", "blocks_per_SM", "ITER", "reuse_factor"}
        )
        legacy_ncu_rows = [
            {column: row.get(column, "") for column in legacy_ncu_columns}
            for row in selftest_ncu_rows()
        ]
        ncu_legacy = Path("results/summary/ncu_acceptance_legacy.csv")
        write_test_csv(repo / ncu_legacy, legacy_ncu_columns, legacy_ncu_rows)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_legacy)}],
            "rtx3090",
            require_path_specific_cache_evidence=False,
        )
        assert_selftest(ok, "ncu_acceptance_legacy_historical", detail)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_legacy)}],
            "a100",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(
            (not ok) and "missing_columns=" in detail,
            "ncu_acceptance_legacy_rejected_for_new_package",
            detail,
        )

        ncu_missing = Path("results/summary/ncu_acceptance_missing_hit.csv")
        ncu_missing_columns = [c for c in ncu_columns if c != "l1_hit_rate_pct"]
        write_test_csv(repo / ncu_missing, ncu_missing_columns, selftest_ncu_rows())
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_missing)}],
            "rtx3090",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(
            (not ok) and "missing_columns=l1_hit_rate_pct" in detail,
            "ncu_acceptance_missing_hit",
            detail,
        )

        ncu_bad_path = Path("results/summary/ncu_acceptance_bad_l1_path.csv")
        bad_rows = selftest_ncu_rows()
        for row in bad_rows:
            if row["component_candidate"] == "global_l1_hit_path":
                row["l1_hit_rate_pct"] = "10"
                row["l1_path_hit_rate_pct"] = "10"
        write_test_csv(repo / ncu_bad_path, ncu_columns, bad_rows)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_bad_path)}],
            "rtx3090",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(
            (not ok) and "path_evidence_failed" in detail,
            "ncu_acceptance_bad_l1_path",
            detail,
        )

        ncu_bad_reason = Path("results/summary/ncu_acceptance_bad_reason.csv")
        bad_reason_rows = selftest_ncu_rows()
        for row in bad_reason_rows:
            if row["component_candidate"] == "l2_hit_path":
                row["acceptance_reason"] = "manual_override"
        write_test_csv(repo / ncu_bad_reason, ncu_columns, bad_reason_rows)
        ok, detail, _ = validate_ncu_acceptance_artifacts(
            repo,
            [{"ncu_acceptance_artifact": str(ncu_bad_reason)}],
            "rtx3090",
            require_path_specific_cache_evidence=True,
        )
        assert_selftest(
            (not ok) and "reason=manual_override" in detail,
            "ncu_acceptance_bad_reason",
            detail,
        )


def latest_command_package(repo: Path, profile: str) -> tuple[Path | None, Path | None]:
    shell = latest_artifact(
        repo,
        [f"results/summary/{profile}_component_finalplan_*_commands.sh"],
    )
    if shell is None:
        return None, None
    plan = shell.with_name(shell.name.replace("_commands.sh", "_command_plan.md"))
    return shell, plan


def validate_command_package(
    repo: Path, profile: str, expected_semantics: str
) -> tuple[bool, str, str]:
    shell, plan = latest_command_package(repo, profile)
    if shell is None:
        return False, "missing_command_shell", "results/summary"
    if plan is None or not plan.exists():
        return False, "missing_command_plan", str(plan or shell)
    if not shell.exists():
        return False, "missing_command_shell", str(shell)

    shell_text = shell.read_text(encoding="utf-8")
    plan_text = plan.read_text(encoding="utf-8")
    missing_shell = [term for term in COMMAND_SHELL_TERMS if term not in shell_text]
    missing_plan = [term for term in COMMAND_PLAN_TERMS if term not in plan_text]
    problems: list[str] = []
    if missing_shell:
        problems.append("missing_shell_terms=" + ",".join(missing_shell))
    if missing_plan:
        problems.append("missing_plan_terms=" + ",".join(missing_plan))
    if f"--target-profile {profile}" not in shell_text:
        problems.append("shell_target_profile_mismatch")
    if f"--expected-power-semantics {expected_semantics}" not in shell_text:
        problems.append("shell_power_semantics_mismatch")
    if f"| target profile | `{profile}` |" not in plan_text:
        problems.append("plan_target_profile_mismatch")
    if f"| expected power semantics | `{expected_semantics}` |" not in plan_text:
        problems.append("plan_power_semantics_mismatch")
    goal_pos = shell_text.find("scripts/audit_component_goal_readiness.py --ncu")
    dashboard_pos = shell_text.find("scripts/build_platform_intake_dashboard.py")
    if goal_pos < 0 or dashboard_pos < 0 or dashboard_pos < goal_pos:
        problems.append("shell_dashboard_before_goal_readiness")
    if "--goal-readiness-csv" not in shell_text:
        problems.append("shell_dashboard_missing_goal_readiness_input")
    gap_tag_term = (
        "scripts/summarize_platform_package_gaps.py "
        f"--target-profile {profile} --tag"
    )
    if gap_tag_term not in shell_text:
        problems.append("shell_gap_report_missing_tag")
    binary = DEFAULT_BINARY_BY_PROFILE[profile]
    if f"--binary {binary}" not in shell_text:
        problems.append("shell_binary_path_mismatch")
    if f"BIN={binary}" not in shell_text:
        problems.append("shell_ncu_bin_path_mismatch")
    if f"| binary | `{binary}` |" not in plan_text:
        problems.append("plan_binary_path_mismatch")

    return (
        not problems,
        "ok" if not problems else ";".join(problems[:8]),
        f"{shell};{plan}",
    )


def validate_local_readiness_runner(repo: Path) -> tuple[bool, str, str]:
    path = repo / LOCAL_READINESS_RUNNER
    if not path.exists():
        return False, "missing_runner", str(path)
    text = path.read_text(encoding="utf-8")
    missing = [term for term in LOCAL_READINESS_RUNNER_TERMS if term not in text]
    problems: list[str] = []
    if missing:
        problems.append("missing_terms=" + ",".join(missing))

    external_stage = text.find("[readiness] external platform")
    manifest_pos = text.find("scripts/write_platform_result_manifest.py", external_stage)
    package_pos = text.find("scripts/audit_platform_result_package.py", manifest_pos)
    gap_pos = text.find("scripts/summarize_platform_package_gaps.py", package_pos)
    goal_pos = text.find("[readiness] goal readiness")
    dashboard_pos = text.find("[readiness] platform intake dashboard")
    if external_stage < 0 or manifest_pos < 0 or package_pos < 0 or gap_pos < 0:
        problems.append("missing_external_manifest_package_gap_stage")
    elif not (external_stage < manifest_pos < package_pos < gap_pos):
        problems.append(
            "bad_manifest_package_gap_order="
            f"external:{external_stage},manifest:{manifest_pos},"
            f"package:{package_pos},gap:{gap_pos}"
        )
    if goal_pos < 0 or dashboard_pos < 0 or dashboard_pos < goal_pos:
        problems.append(f"bad_goal_dashboard_order=goal:{goal_pos},dashboard:{dashboard_pos}")

    return (
        not problems,
        "ok" if not problems else ";".join(problems[:8]),
        str(path),
    )


def latest_package_audit(repo: Path, profile: str) -> Path | None:
    return latest_artifact(
        repo,
        [f"results/summary/{profile}_platform_result_package_audit_*.csv"],
    )


def validate_package_audit(repo: Path, profile: str) -> tuple[str, str, str]:
    audit_path = latest_package_audit(repo, profile)
    if audit_path is None or not audit_path.exists():
        return "missing", "missing_package_audit", "results/summary"

    audit_rows = read_csv(audit_path)
    failures = [row for row in audit_rows if row.get("status") == "fail"]
    missing = [row for row in audit_rows if row.get("status") == "missing"]
    warnings = [row for row in audit_rows if row.get("status") == "warning"]
    if failures:
        return (
            "fail",
            f"rows={len(audit_rows)}, failures={len(failures)}, "
            f"missing={len(missing)}, warnings={len(warnings)}",
            str(audit_path),
        )
    if missing:
        return (
            "missing",
            f"rows={len(audit_rows)}, failures=0, missing={len(missing)}, "
            f"warnings={len(warnings)}",
            str(audit_path),
        )
    if warnings:
        return (
            "warning",
            f"rows={len(audit_rows)}, failures=0, missing=0, warnings={len(warnings)}",
            str(audit_path),
        )
    return "pass", f"rows={len(audit_rows)}, failures=0, missing=0, warnings=0", str(audit_path)


def audit_command_packages(repo: Path, rows: list[dict[str, str]]) -> None:
    for profile in COMMAND_PACKAGE_PROFILES:
        ok, detail, evidence = validate_command_package(repo, profile, PROFILES[profile])
        add(
            rows,
            area=profile,
            check="platform_command_package",
            status="pass" if ok else "missing" if detail.startswith("missing") else "fail",
            expected=(
                "generated finalplan shell/markdown package with power API, "
                "power-state, NCU, reliability, and strict summary gates"
            ),
            actual=detail,
            evidence=evidence,
            next_action=(
                "run scripts/plan_platform_component_experiment.py for the target "
                "profile and inspect the generated shell before node execution"
            ),
        )


def audit_result_manifests(repo: Path, rows: list[dict[str, str]]) -> None:
    for profile in COMMAND_PACKAGE_PROFILES:
        tag = command_tag_from_rows(rows, profile)
        csv_path = repo / f"results/summary/{profile}_component_finalplan_{tag}_result_manifest.csv"
        md_path = repo / f"results/summary/{profile}_component_finalplan_{tag}_result_manifest.md"
        problems: list[str] = []
        malformed: list[str] = []
        binary = DEFAULT_BINARY_BY_PROFILE[profile]
        cuda_arch = DEFAULT_CUDA_ARCH_BY_PROFILE[profile]
        build_dir = DEFAULT_BUILD_DIR_BY_PROFILE[profile]
        if not csv_path.exists():
            problems.append("missing_csv")
        else:
            manifest_rows = read_csv(csv_path)
            if not manifest_rows:
                malformed.append("empty_csv")
            required_columns = {"cuda_arch", "build_dir", "binary"}
            fieldnames = set(manifest_rows[0].keys()) if manifest_rows else set()
            missing_columns = sorted(required_columns - fieldnames)
            if missing_columns:
                malformed.append("missing_csv_columns=" + ",".join(missing_columns))
            else:
                bad_rows = []
                for idx, row in enumerate(manifest_rows, start=2):
                    if row.get("cuda_arch") != cuda_arch:
                        bad_rows.append(f"line{idx}:cuda_arch={row.get('cuda_arch')}")
                    if row.get("build_dir") != build_dir:
                        bad_rows.append(f"line{idx}:build_dir={row.get('build_dir')}")
                    if row.get("binary") != binary:
                        bad_rows.append(f"line{idx}:binary={row.get('binary')}")
                if bad_rows:
                    malformed.append("bad_csv_metadata=" + ",".join(bad_rows[:4]))
        if not md_path.exists():
            problems.append("missing_md")
        if md_path.exists():
            text = md_path.read_text(encoding="utf-8")
            required_terms = [
                f"profile | `{profile}`",
                "Build Requirement",
                f"CUDA arch | `{cuda_arch}`",
                f"build directory | `{build_dir}`",
                f"binary | `{binary}`",
                f"CMAKE_CUDA_ARCHITECTURES={cuda_arch}",
                "transfer checklist",
                "final numerator policy",
                "strict component summary audit",
                "audit_platform_result_package.py",
            ]
            missing_terms = [term for term in required_terms if term not in text]
            if missing_terms:
                malformed.append("missing_terms=" + ",".join(missing_terms))
        status = "pass"
        if problems:
            status = "missing"
        elif malformed:
            status = "fail"
        add(
            rows,
            area=profile,
            check="platform_result_manifest",
            status=status,
            expected=(
                "CSV and Markdown transfer manifest exists with package audit instructions "
                "and profile-specific build/binary metadata"
            ),
            actual="ok" if status == "pass" else ";".join(problems + malformed),
            evidence=f"{csv_path};{md_path}",
            next_action=(
                "run scripts/write_platform_result_manifest.py for the target profile/tag "
                "before transferring external platform results"
            ),
        )


def audit_intake_dashboard(repo: Path, rows: list[dict[str, str]]) -> None:
    tag = command_tag_from_rows(rows, "a100")
    csv_path = repo / f"results/summary/platform_component_intake_dashboard_{tag}.csv"
    md_path = repo / f"results/summary/platform_component_intake_dashboard_{tag}.md"
    problems: list[str] = []
    if not csv_path.exists():
        problems.append("missing_csv")
    if not md_path.exists():
        problems.append("missing_md")
    if csv_path.exists():
        csv_rows = read_csv(csv_path)
        profiles = {row.get("profile", "") for row in csv_rows}
        required_profiles = {"rtx3090", "v100", "a100", "h100"}
        missing_profiles = sorted(required_profiles - profiles)
        if missing_profiles:
            problems.append("missing_profiles=" + ",".join(missing_profiles))
    if md_path.exists():
        text = md_path.read_text(encoding="utf-8")
        required_terms = [
            "Platform Component Result Intake Dashboard",
            "profiles passing package + strict summary",
            "historical_local_evidence",
            "nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter",
        ]
        missing_terms = [term for term in required_terms if term not in text]
        if missing_terms:
            problems.append("missing_terms=" + ",".join(missing_terms))
    add(
        rows,
        area="platforms",
        check="platform_intake_dashboard",
        status="pass" if not problems else "missing",
        expected="cross-platform intake dashboard exists with profile and power-policy summary",
        actual="ok" if not problems else ";".join(problems),
        evidence=f"{csv_path};{md_path}",
        next_action=(
            "run scripts/build_platform_intake_dashboard.py after package audits "
            "and gap reports are generated"
        ),
    )


def audit_package_audits(repo: Path, rows: list[dict[str, str]]) -> None:
    for profile in COMMAND_PACKAGE_PROFILES:
        status, detail, evidence = validate_package_audit(repo, profile)
        add(
            rows,
            area=profile,
            check="platform_result_package_audit",
            status=status,
            expected="package audit exists with 0 fail, 0 missing, and 0 warning rows",
            actual=detail,
            evidence=evidence,
            next_action=(
                "run scripts/audit_platform_result_package.py after copying back "
                "all raw, power, NCU, matched-control, reliability, and strict "
                "summary artifacts"
            ),
        )


def audit_gate_selftest(repo: Path, rows: list[dict[str, str]]) -> None:
    preflight_script = repo / "scripts" / "preflight_gpu_support.py"
    if not preflight_script.exists():
        add(
            rows,
            area="tooling",
            check="preflight_strict_selftest",
            status="missing",
            expected=str(preflight_script),
            actual="missing",
            evidence=str(preflight_script),
            next_action="restore scripts/preflight_gpu_support.py",
        )
    else:
        rc, output = run_command(["python3", str(preflight_script), "--self-test"], timeout=30)
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="preflight_strict_selftest",
            status="pass" if rc == 0 else "fail",
            expected=(
                "preflight strict gate self-test passes for profile mismatch, "
                "NCU support, and dry-run failure cases"
            ),
            actual=last_line or f"rc={rc}",
            evidence=str(preflight_script),
            next_action=(
                "fix strict preflight gate before running A100/V100/H100 command "
                "packages"
            ),
        )

    goal_script = repo / "scripts" / "audit_component_goal_readiness.py"
    if not goal_script.exists():
        add(
            rows,
            area="tooling",
            check="goal_readiness_selftest",
            status="missing",
            expected=str(goal_script),
            actual="missing",
            evidence=str(goal_script),
            next_action="restore scripts/audit_component_goal_readiness.py",
        )
    else:
        rc, output = run_command(["python3", str(goal_script), "--self-test"], timeout=30)
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="goal_readiness_selftest",
            status="pass" if rc == 0 else "fail",
            expected="goal readiness validator self-test passes",
            actual=last_line or f"rc={rc}",
            evidence=str(goal_script),
            next_action=(
                "fix goal-level NCU acceptance or power-state validator regressions "
                "before claiming completion"
            ),
        )

    power_api_script = repo / "scripts" / "audit_power_api_measurements.py"
    if not power_api_script.exists():
        add(
            rows,
            area="tooling",
            check="power_api_audit_selftest",
            status="missing",
            expected=str(power_api_script),
            actual="missing",
            evidence=str(power_api_script),
            next_action="restore scripts/audit_power_api_measurements.py",
        )
    else:
        rc, output = run_command(["python3", str(power_api_script), "--self-test"], timeout=30)
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="power_api_audit_selftest",
            status="pass" if rc == 0 else "fail",
            expected=(
                "power API audit self-test passes for A100 semantics, fallback "
                "numerator, explicit measurement scope, and H100 module scope"
            ),
            actual=last_line or f"rc={rc}",
            evidence=str(power_api_script),
            next_action=(
                "fix power API matrix enforcement before accepting A100/V100/H100 "
                "energy rows"
            ),
        )

    strict_builder_script = repo / "scripts" / "build_strict_component_summary.py"
    if not strict_builder_script.exists():
        add(
            rows,
            area="tooling",
            check="strict_summary_builder_selftest",
            status="missing",
            expected=str(strict_builder_script),
            actual="missing",
            evidence=str(strict_builder_script),
            next_action="restore scripts/build_strict_component_summary.py",
        )
    else:
        rc, output = run_command(
            ["python3", str(strict_builder_script), "--self-test"], timeout=30
        )
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="strict_summary_builder_selftest",
            status="pass" if rc == 0 else "fail",
            expected=(
                "strict summary builder self-test passes for component-specific "
                "NCU artifact selection"
            ),
            actual=last_line or f"rc={rc}",
            evidence=str(strict_builder_script),
            next_action=(
                "fix strict summary builder NCU artifact selection before "
                "building component summaries"
            ),
        )

    strict_summary_script = repo / "scripts" / "audit_strict_component_summary.py"
    if not strict_summary_script.exists():
        add(
            rows,
            area="tooling",
            check="strict_summary_audit_selftest",
            status="missing",
            expected=str(strict_summary_script),
            actual="missing",
            evidence=str(strict_summary_script),
            next_action="restore scripts/audit_strict_component_summary.py",
        )
    else:
        rc, output = run_command(
            ["python3", str(strict_summary_script), "--self-test"], timeout=30
        )
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="strict_summary_audit_selftest",
            status="pass" if rc == 0 else "fail",
            expected=(
                "strict summary audit self-test passes for NCU coordinate "
                "alignment and mismatch detection"
            ),
            actual=last_line or f"rc={rc}",
            evidence=str(strict_summary_script),
            next_action=(
                "fix strict summary audit coordinate-alignment checks before "
                "accepting NCU-backed component summaries"
            ),
        )

    package_script = repo / "scripts" / "selftest_platform_package_gates.py"
    if not package_script.exists():
        add(
            rows,
            area="tooling",
            check="platform_package_gate_selftest",
            status="missing",
            expected=str(package_script),
            actual="missing",
            evidence=str(package_script),
            next_action="restore scripts/selftest_platform_package_gates.py",
        )
    else:
        rc, output = run_command(["python3", str(package_script)], timeout=30)
        last_line = output.splitlines()[-1] if output else ""
        add(
            rows,
            area="tooling",
            check="platform_package_gate_selftest",
            status="pass" if rc == 0 else "fail",
            expected="mock package gate self-test passes",
            actual=last_line or f"rc={rc}",
            evidence=str(package_script),
            next_action=(
                "fix audit_platform_result_package.py before trusting returned "
                "A100/V100/H100 packages"
            ),
        )

    manifest_script = repo / "scripts" / "write_platform_result_manifest.py"
    if not manifest_script.exists():
        add(
            rows,
            area="tooling",
            check="platform_manifest_selftest",
            status="missing",
            expected=str(manifest_script),
            actual="missing",
            evidence=str(manifest_script),
            next_action="restore scripts/write_platform_result_manifest.py",
        )
        return
    rc, output = run_command(["python3", str(manifest_script), "--self-test"], timeout=30)
    last_line = output.splitlines()[-1] if output else ""
    add(
        rows,
        area="tooling",
        check="platform_manifest_selftest",
        status="pass" if rc == 0 else "fail",
        expected="manifest expected-path self-test passes",
        actual=last_line or f"rc={rc}",
        evidence=str(manifest_script),
        next_action="fix manifest generation before transferring external platform results",
    )

    gap_script = repo / "scripts" / "summarize_platform_package_gaps.py"
    if not gap_script.exists():
        add(
            rows,
            area="tooling",
            check="platform_gap_report_selftest",
            status="missing",
            expected=str(gap_script),
            actual="missing",
            evidence=str(gap_script),
            next_action="restore scripts/summarize_platform_package_gaps.py",
        )
        return
    rc, output = run_command(["python3", str(gap_script), "--self-test"], timeout=30)
    last_line = output.splitlines()[-1] if output else ""
    add(
        rows,
        area="tooling",
        check="platform_gap_report_selftest",
        status="pass" if rc == 0 else "fail",
        expected="package gap report self-test passes",
        actual=last_line or f"rc={rc}",
        evidence=str(gap_script),
        next_action="fix gap report generation before triaging returned platform packages",
    )

    dashboard_script = repo / "scripts" / "build_platform_intake_dashboard.py"
    if not dashboard_script.exists():
        add(
            rows,
            area="tooling",
            check="platform_dashboard_selftest",
            status="missing",
            expected=str(dashboard_script),
            actual="missing",
            evidence=str(dashboard_script),
            next_action="restore scripts/build_platform_intake_dashboard.py",
        )
        return
    rc, output = run_command(["python3", str(dashboard_script), "--self-test"], timeout=30)
    last_line = output.splitlines()[-1] if output else ""
    add(
        rows,
        area="tooling",
        check="platform_dashboard_selftest",
        status="pass" if rc == 0 else "fail",
        expected="platform intake dashboard self-test passes",
        actual=last_line or f"rc={rc}",
        evidence=str(dashboard_script),
        next_action="fix dashboard generation before cross-platform result triage",
    )


def audit_local_readiness_runner(repo: Path, rows: list[dict[str, str]]) -> None:
    ok, detail, evidence = validate_local_readiness_runner(repo)
    add(
        rows,
        area="tooling",
        check="local_readiness_runner_policy",
        status="pass" if ok else "fail",
        expected=(
            "local readiness runner refreshes A100/V100/H100 package audits, "
            "gap reports, goal readiness, and dashboard with tag and active-SM "
            "override support"
        ),
        actual=detail,
        evidence=evidence,
        next_action=(
            "fix scripts/run_local_readiness_checks.sh before using it to triage "
            "external platform result packages"
        ),
    )


def audit_power_matrix(repo: Path, rows: list[dict[str, str]]) -> None:
    path = repo / POWER_MATRIX
    exists = path.exists()
    add(
        rows,
        area="method",
        check="power_matrix_exists",
        status="pass" if exists else "fail",
        expected=str(POWER_MATRIX),
        actual="exists" if exists else "missing",
        evidence=str(path),
        next_action="restore or create the power API matrix before interpreting energy rows",
    )
    if not exists:
        return
    text = path.read_text(encoding="utf-8")
    missing = [term for term in POWER_MATRIX_TERMS if term not in text]
    add(
        rows,
        area="method",
        check="power_matrix_terms",
        status="pass" if not missing else "fail",
        expected="core power API/scope terms present",
        actual="ok" if not missing else "missing:" + ",".join(missing),
        evidence=str(path),
        next_action="update the matrix so final/provisional/reject semantics are explicit",
    )


def audit_platform_readiness(repo: Path, rows: list[dict[str, str]]) -> None:
    path = repo / PLATFORM_READINESS
    if not path.exists():
        add(
            rows,
            area="platforms",
            check="static_readiness_audit",
            status="missing",
            expected=str(PLATFORM_READINESS),
            actual="missing",
            evidence=str(path),
            next_action="run scripts/audit_platform_power_readiness.py",
        )
        return
    audit_rows = read_csv(path)
    failures = [row for row in audit_rows if row.get("status") == "fail"]
    add(
        rows,
        area="platforms",
        check="static_readiness_audit",
        status="pass" if not failures else "fail",
        expected="0 fail rows",
        actual=f"rows={len(audit_rows)}, failures={len(failures)}",
        evidence=str(path),
        next_action="fix profile/power/doc mismatches before new platform runs",
    )


def audit_tooling(repo: Path, rows: list[dict[str, str]], ncu: str) -> None:
    ok, detail = command_ok("nvidia-smi")
    status = "pass" if ok else "warning"
    add(
        rows,
        area="tooling",
        check="nvidia_smi_available",
        status=status,
        expected="nvidia-smi available",
        actual=detail,
        evidence=detail,
        next_action="without nvidia-smi, preflight power scope metadata cannot be collected",
    )
    if ok:
        rc, out = run_command(["nvidia-smi", "-L"])
        first_line = out.splitlines()[0] if out else ""
        add(
            rows,
            area="tooling",
            check="nvidia_smi_lists_gpu",
            status="pass" if rc == 0 and bool(first_line) else "warning",
            expected="nvidia-smi -L returns at least one GPU",
            actual=first_line or f"rc={rc}",
            evidence="nvidia-smi -L",
            next_action="run on a node with the target GPU before claiming platform results",
        )

    ncu_path = shutil.which(ncu) if ncu else None
    add(
        rows,
        area="tooling",
        check="ncu_available_for_fresh_replay",
        status="pass" if ncu_path else "missing",
        expected="ncu executable available for fresh replay",
        actual=ncu_path or "not found",
        evidence=ncu,
        next_action="install or expose Nsight Compute CLI to run fresh NCU sidecars",
    )

    binary = repo / "build/a100_fp16_energy_v2"
    add(
        rows,
        area="tooling",
        check="experiment_binary_exists",
        status="pass" if binary.exists() else "missing",
        expected=str(binary),
        actual="exists" if binary.exists() else "missing",
        evidence=str(binary),
        next_action="build the harness before energy or dry-run checks",
    )


def audit_rtx3090_strict(repo: Path, rows: list[dict[str, str]]) -> None:
    summary_path = latest_platform_summary(repo, "rtx3090") or (
        repo / STRICT_RTX3090_SUMMARY
    )
    audit_path = latest_artifact(
        repo,
        [
            "results/summary/"
            "rtx3090_strict_scope_fresh_ncu_component_summary_audit_*.csv"
        ],
    ) or (repo / STRICT_RTX3090_AUDIT)

    if not summary_path.exists():
        add(
            rows,
            area="rtx3090",
            check="strict_summary_present",
            status="missing",
            expected=str(STRICT_RTX3090_SUMMARY),
            actual="missing",
            evidence=str(summary_path),
            next_action="rerun or regenerate the RTX 3090 strict component summary",
        )
        return

    summary_rows = read_csv(summary_path)
    by_component = {row.get("component", ""): row for row in summary_rows}
    missing_components = sorted(set(STRICT_COMPONENTS) - set(by_component))
    add(
        rows,
        area="rtx3090",
        check="strict_required_components",
        status="pass" if not missing_components else "fail",
        expected="Tensor, Shared, Global L1, L2 strict rows",
        actual="ok" if not missing_components else "missing:" + ",".join(missing_components),
        evidence=str(summary_path),
        next_action="do not report a component table until all required strict rows exist",
    )

    bad_rows: list[str] = []
    for component, expected_unit in STRICT_COMPONENTS.items():
        row = by_component.get(component)
        if not row:
            continue
        if row.get("unit") != expected_unit:
            bad_rows.append(f"{component}:unit={row.get('unit')}")
        if row.get("energy_source") != "nvml_total_energy":
            bad_rows.append(f"{component}:energy_source={row.get('energy_source')}")
        if row.get("energy_integration_method") != "total_energy_mj_delta":
            bad_rows.append(f"{component}:integration={row.get('energy_integration_method')}")
        if row.get("measurement_scope") != "gpu_device_total_energy_counter":
            bad_rows.append(f"{component}:scope={row.get('measurement_scope')}")
        if row.get("power_semantics") != PROFILES["rtx3090"]:
            bad_rows.append(f"{component}:semantics={row.get('power_semantics')}")
        if row.get("reliability_status") != "accepted":
            bad_rows.append(f"{component}:reliability={row.get('reliability_status')}")
    add(
        rows,
        area="rtx3090",
        check="strict_power_policy",
        status="pass" if not bad_rows else "fail",
        expected="accepted rows use total-energy delta and GPU/device scope",
        actual="ok" if not bad_rows else ";".join(bad_rows),
        evidence=str(summary_path),
        next_action="recompute or remove rows that violate the power measurement matrix",
    )

    expected_pairs = {
        "Tensor MMA incremental": "reg_mma - reg_operand_only",
        "Shared scalar path": (
            "shared_scalar_load_only - shared_scalar_addr_only"
        ),
        "Global L1 hit path": "global_l1_load_only - global_addr_only",
        "L2 CG hit path": "l2_cg_load_only - global_addr_only",
    }
    bad_pairs = [
        f"{component}:{by_component.get(component, {}).get('mode_pair', '')}"
        for component, expected_pair in expected_pairs.items()
        if by_component.get(component, {}).get("mode_pair", "") != expected_pair
    ]
    add(
        rows,
        area="rtx3090",
        check="strict_control_protocol",
        status="pass" if not bad_pairs else "fail",
        expected="current Tensor/Shared/address-control treatment-control pairs",
        actual="ok" if not bad_pairs else ";".join(bad_pairs),
        evidence=str(summary_path),
        next_action=(
            "rerun the RTX 3090 20260712 command package; historical clocked_empty "
            "Global L1/L2 rows are not current strict evidence"
        ),
    )

    if audit_path.exists():
        audit_rows = read_csv(audit_path)
        failures = [row for row in audit_rows if row.get("status") == "fail"]
        warnings = [row for row in audit_rows if row.get("status") == "warning"]
        status = "pass" if not failures and not warnings else "warning" if not failures else "fail"
        add(
            rows,
            area="rtx3090",
            check="strict_summary_audit_clean",
            status=status,
            expected="0 fail and 0 warning rows",
            actual=f"rows={len(audit_rows)}, failures={len(failures)}, warnings={len(warnings)}",
            evidence=str(audit_path),
            next_action="inspect strict summary audit before treating RTX 3090 as accepted",
        )
    else:
        add(
            rows,
            area="rtx3090",
            check="strict_summary_audit_clean",
            status="missing",
            expected=str(STRICT_RTX3090_AUDIT),
            actual="missing",
            evidence=str(audit_path),
            next_action="run scripts/audit_strict_component_summary.py",
        )


def audit_rtx3090_fresh_ncu(repo: Path, rows: list[dict[str, str]]) -> None:
    reliability_path = latest_artifact(
        repo,
        [
            "results/summary/"
            "rtx3090_component_finalplan_*_component_reliability_audit.csv"
        ],
    ) or latest_artifact(
        repo,
        [
            "results/summary/"
            "rtx3090_strict_scope_fresh_ncu_component_reliability_audit_*.csv"
        ],
    ) or (repo / FRESH_NCU_RELIABILITY)
    acceptance_path = latest_artifact(
        repo,
        ["results/summary/rtx3090_component_finalplan_*_ncu_acceptance.csv"],
    ) or latest_artifact(
        repo,
        [
            "results/summary/"
            "rtx3090_strict_scope_fresh_ncu_combined_acceptance_*.csv"
        ],
    ) or (repo / FRESH_NCU_ACCEPTANCE)

    if not reliability_path.exists():
        add(
            rows,
            area="rtx3090",
            check="fresh_ncu_reliability",
            status="missing",
            expected=str(FRESH_NCU_RELIABILITY),
            actual="missing",
            evidence=str(reliability_path),
            next_action="run fresh NCU sidecar, path acceptance, matched-control, and reliability audit",
        )
        return

    reliability_rows = read_csv(reliability_path)
    rejected = [row for row in reliability_rows if row.get("status") == "reject"]
    accepted = [row for row in reliability_rows if row.get("status") == "accepted"]
    add(
        rows,
        area="rtx3090",
        check="fresh_ncu_reliability",
        status="pass" if len(accepted) >= 4 and not rejected else "fail",
        expected="Tensor, Shared, Global L1, and L2 accepted with fresh NCU",
        actual=f"accepted={len(accepted)}, rejected={len(rejected)}",
        evidence=str(reliability_path),
        next_action="inspect fresh NCU reliability before replacing or publishing strict coefficients",
    )

    if not acceptance_path.exists():
        add(
            rows,
            area="rtx3090",
            check="fresh_ncu_acceptance",
            status="missing",
            expected=str(FRESH_NCU_ACCEPTANCE),
            actual="missing",
            evidence=str(acceptance_path),
            next_action="combine fresh NCU acceptance CSVs for traceability",
        )
        return

    acceptance_rows = read_csv(acceptance_path)
    accepted_by_component: dict[str, int] = {}
    unexpected_rejects: list[str] = []
    for row in acceptance_rows:
        component = row.get("component_candidate", "")
        acceptance = row.get("acceptance", "")
        mode = row.get("mode", "")
        if acceptance == "accepted":
            accepted_by_component[component] = accepted_by_component.get(component, 0) + 1
        elif acceptance == "rejected" and component != "not_selected":
            unexpected_rejects.append(f"{mode}:{component}")

    required = {
        "tensor_increment_candidate",
        "register_control_candidate",
        "shared_memory_path",
        "global_l1_hit_path",
        "l2_hit_path",
        "global_address_control",
    }
    missing = sorted(component for component in required if accepted_by_component.get(component, 0) <= 0)
    add(
        rows,
        area="rtx3090",
        check="fresh_ncu_acceptance",
        status="pass" if not missing and not unexpected_rejects else "fail",
        expected="fresh accepted NCU rows for tensor/control/shared/L1/L2 paths",
        actual=(
            "ok"
            if not missing and not unexpected_rejects
            else f"missing={missing}; unexpected_rejects={unexpected_rejects}"
        ),
        evidence=str(acceptance_path),
        next_action="rerun failed NCU path cases with matching W_SM/blocks/SM/factors",
    )


def audit_cross_platform_results(repo: Path, rows: list[dict[str, str]]) -> None:
    for profile, semantics in PROFILES.items():
        summary = latest_platform_summary(repo, profile)
        if not summary:
            status = "missing" if profile != "rtx3090" else "warning"
            add(
                rows,
                area=profile,
                check="platform_component_summary",
                status=status,
                expected=f"{profile} component summary with semantics={semantics}",
                actual="missing",
                evidence="results/summary",
                next_action=(
                    "run the generated platform finalplan on the target node and then run "
                    "power, NCU, matched-control, reliability, and summary audits"
                ),
            )
            continue

        summary_rows = read_csv(summary)
        add(
            rows,
            area=profile,
            check="platform_component_summary",
            status="pass",
            expected=f"{profile} component summary with semantics={semantics}",
            actual=str(summary),
            evidence=str(summary),
            next_action="verify this summary with the strict/package audits before publication",
        )
        require_path_specific_cache_evidence = True
        ok, detail = validate_component_summary(
            summary_rows,
            expected_semantics=semantics,
            require_path_specific_cache_evidence=require_path_specific_cache_evidence,
        )
        add(
            rows,
            area=profile,
            check="platform_summary_policy",
            status="pass" if ok else "fail",
            expected=(
                "required components accepted with total-energy delta, "
                "GPU/device scope, matching power semantics, same-coordinate NCU rows, "
                + "and path-specific NCU evidence fields"
            ),
            actual=detail,
            evidence=str(summary),
            next_action=(
                "regenerate the platform summary from accepted reliability rows and "
                "the power measurement matrix with NCU evidence fields preserved"
            ),
        )

        audit_ok, audit_detail, audit_evidence = validate_summary_audit_artifact(summary)
        add(
            rows,
            area=profile,
            check="platform_summary_audit_artifact",
            status="pass" if audit_ok else "fail",
            expected="strict summary audit exists with 0 fail and 0 warning rows",
            actual=audit_detail,
            evidence=audit_evidence,
            next_action=(
                "run scripts/audit_strict_component_summary.py after building the "
                "platform strict component summary"
            ),
        )

        power_ok, power_detail, power_evidence = validate_power_api_artifacts(
            repo, summary_rows, profile, semantics
        )
        add(
            rows,
            area=profile,
            check="platform_power_api_artifacts",
            status="pass" if power_ok else "fail",
            expected=(
                "power API audit artifacts contain only final_candidate total-energy "
                "GPU/device rows with matching semantics"
            ),
            actual=power_detail,
            evidence=power_evidence,
            next_action=(
                "rerun scripts/audit_power_api_measurements.py and rebuild the strict "
                "component summary with --power-api-audit-csv"
            ),
        )

        power_state_ok, power_state_detail, power_state_evidence = validate_power_state_artifacts(
            repo, summary_rows, profile
        )
        add(
            rows,
            area=profile,
            check="platform_power_state_artifacts",
            status="pass" if power_state_ok else "fail",
            expected=(
                "power-state audit artifacts exist, contain no reject or "
                "coefficient-ineligible rows, and include positive average "
                "power, peer median power, SM clock, temperature, elapsed time, "
                "and run-coordinate evidence"
            ),
            actual=power_state_detail,
            evidence=power_state_evidence,
            next_action=(
                "rerun scripts/audit_power_state_stability.py, exclude reject rows "
                "before matched-control, and rebuild the strict component summary"
            ),
        )

        rel_ok, rel_detail, rel_evidence = validate_reliability_artifacts(
            repo, summary_rows, profile, semantics
        )
        add(
            rows,
            area=profile,
            check="platform_reliability_artifacts",
            status="pass" if rel_ok else "fail",
            expected="component reliability artifacts exist and contain accepted non-reject rows",
            actual=rel_detail,
            evidence=rel_evidence,
            next_action="run scripts/audit_component_reliability.py for the target platform",
        )

        ncu_ok, ncu_detail, ncu_evidence = validate_ncu_acceptance_artifacts(
            repo,
            summary_rows,
            profile,
            require_path_specific_cache_evidence=require_path_specific_cache_evidence,
        )
        add(
            rows,
            area=profile,
            check="platform_ncu_acceptance_artifacts",
            status="pass" if ncu_ok else "fail",
            expected=(
                "fresh NCU acceptance artifacts cover tensor/control/shared/L1/L2 "
                "paths with pass reasons and counter evidence that satisfies "
                + (
                    "path-specific hit-rate and traffic-ratio thresholds"
                    if require_path_specific_cache_evidence
                    else "the historical aggregate-compatible path thresholds"
                )
            ),
            actual=ncu_detail,
            evidence=ncu_evidence,
            next_action=(
                "run scripts/run_ncu_validation.sh and "
                "scripts/analyze_ncu_path_acceptance.py with matching platform settings"
            ),
        )


def write_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "area",
            "check",
            "status",
            "expected",
            "actual",
            "evidence",
            "next_action",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: str | Path, rows: list[dict[str, str]]) -> None:
    counts = status_counts(rows)
    incomplete = counts.get("fail", 0) + counts.get("missing", 0)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# Component Energy Goal Readiness Audit\n\n")
        f.write(
            "This audit checks whether the current repository evidence is enough to "
            "claim the component-energy experiment goal is complete. It uses the "
            "power API policy from `docs/platforms/power_measurement_api_matrix_ko.md` "
            "and intentionally separates accepted RTX 3090 evidence from missing "
            "external A100/V100/H100 execution.\n\n"
        )
        f.write("## Verdict\n\n")
        if incomplete:
            f.write(
                "Goal is not complete yet. Accepted RTX 3090 evidence exists, but "
                "one or more required tooling/platform evidence items are missing or "
                "failed.\n\n"
            )
        else:
            f.write(
                "No missing/fail rows were found by this audit. Confirm fresh NCU and "
                "platform-specific reports before marking the broader goal complete.\n\n"
            )
        f.write("## Status Counts\n\n")
        f.write("| status | checks |\n|---|---:|\n")
        for status in sorted(counts):
            f.write(f"| `{status}` | {counts[status]} |\n")
        f.write("\n## Checks\n\n")
        f.write("| area | check | status | expected | actual | evidence | next action |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['area']}` | `{row['check']}` | `{row['status']}` | "
                f"{row['expected']} | {row['actual']} | `{row['evidence']}` | "
                f"{row['next_action']} |\n"
            )
        write_external_intake_section(f, rows)
    out.write_text(
        out.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8"
    )


def audit(repo: Path, ncu: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    audit_power_matrix(repo, rows)
    audit_platform_readiness(repo, rows)
    audit_tooling(repo, rows, ncu)
    audit_gate_selftest(repo, rows)
    audit_local_readiness_runner(repo, rows)
    audit_rtx3090_strict(repo, rows)
    audit_rtx3090_fresh_ncu(repo, rows)
    audit_command_packages(repo, rows)
    audit_result_manifests(repo, rows)
    audit_intake_dashboard(repo, rows)
    audit_package_audits(repo, rows)
    audit_cross_platform_results(repo, rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--ncu", default="ncu")
    parser.add_argument(
        "--out-csv",
        default="results/summary/component_energy_goal_readiness_audit_20260714.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/component_energy_goal_readiness_audit_20260714.md",
    )
    parser.add_argument("--fail-on-fail", action="store_true")
    parser.add_argument("--fail-on-incomplete", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("component goal readiness self-test passed")
        return 0

    repo = Path(args.repo)
    rows = audit(repo, args.ncu)
    write_csv(repo / args.out_csv, rows)
    write_md(repo / args.out_md, rows)

    counts = status_counts(rows)
    print(
        "component goal readiness checks="
        f"{len(rows)} failures={counts.get('fail', 0)} "
        f"missing={counts.get('missing', 0)} warnings={counts.get('warning', 0)}"
    )
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    if args.fail_on_fail and counts.get("fail", 0):
        return 1
    if args.fail_on_incomplete and (
        counts.get("fail", 0) or counts.get("missing", 0)
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
