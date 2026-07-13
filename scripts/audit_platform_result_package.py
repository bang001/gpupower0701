#!/usr/bin/env python3
"""Audit a returned A100/V100/H100/RTX3090 platform result package.

This is an intake gate for results copied back from another GPU node. It checks
that the expected raw files and downstream audit artifacts exist, and that their
power numerator semantics match docs/platforms/power_measurement_api_matrix_ko.md.
It does not run kernels or Nsight Compute.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


PROFILE_POWER_SEMANTICS = {
    "rtx3090": "one_sec_average",
    "v100": "instant",
    "a100": "instant",
    "h100": "one_sec_average",
}

PROFILE_METADATA = {
    "rtx3090": {
        "profile_name": "rtx3090",
        "architecture_family": "ampere_ga10x",
        "chip": "ga102",
        "compute_capability": "8.6",
        "full_sm": 82,
        "l2_mib": 6,
        "unified_l1_shared_kib_per_sm": 128,
        "shared_kib_per_sm": 100,
    },
    "v100": {
        "profile_name": "v100",
        "architecture_family": "volta",
        "chip": "gv100",
        "compute_capability": "7.0",
        "full_sm": 80,
        "l2_mib": 6,
        "unified_l1_shared_kib_per_sm": 128,
        "shared_kib_per_sm": 96,
    },
    "a100": {
        "profile_name": "a100",
        "architecture_family": "ampere_ga100",
        "chip": "ga100",
        "compute_capability": "8.0",
        "full_sm": 108,
        "l2_mib": 40,
        "unified_l1_shared_kib_per_sm": 192,
        "shared_kib_per_sm": 164,
    },
    "h100": {
        "profile_name": "h100",
        "architecture_family": "hopper_gh100",
        "chip": "gh100",
        "compute_capability": "9.0",
        "full_sm": 132,
        "l2_mib": 50,
        "unified_l1_shared_kib_per_sm": 256,
        "shared_kib_per_sm": 228,
    },
}

EXPECTED_COMPONENTS = {
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

STRICT_SUMMARY_NCU_EVIDENCE_COLUMNS = {
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
    "ncu_stall_long_scoreboard_pct_min_med_max",
}

STRICT_SUMMARY_EVIDENCE_MODES = {
    "Tensor MMA incremental": {"reg_mma", "reg_operand_only"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only", "global_addr_only"},
    "L2 CG hit path": {"l2_cg_load_only", "global_addr_only"},
}

STRICT_SUMMARY_METRIC_MODES = {
    "Tensor MMA incremental": {"reg_mma"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only"},
    "L2 CG hit path": {"l2_cg_load_only"},
}

STRICT_SUMMARY_REQUIRED_METRICS = {
    "Tensor MMA incremental": {"ncu_tensor_hmma_inst_min_med_max"},
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

EXPECTED_RELIABILITY_COMPONENTS = {
    "tensor_mma_increment",
    "shared_l1_scalar_path",
    "global_l1_hit_path",
    "l2_hit_cg_path",
}

EXPECTED_RELIABILITY_UNITS = {
    "tensor_mma_increment": "pJ/FLOP",
    "shared_l1_scalar_path": "pJ/bit",
    "global_l1_hit_path": "pJ/bit",
    "l2_hit_cg_path": "pJ/bit",
}

RELIABILITY_REQUIRED_COLUMNS = {
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
}

EXPECTED_MATCHED_SUMMARY_COMPONENTS = {
    "tensor_mma_increment": "pJ/FLOP",
    "shared_l1_scalar_path": "pJ/byte",
    "global_l1_hit_path": "pJ/byte",
    "l2_hit_cg_path": "pJ/byte",
}

MATCHED_MEMORY_COMPONENTS = {
    "shared_l1_scalar_path",
    "global_l1_hit_path",
    "l2_hit_cg_path",
}

MATCHED_SUMMARY_REQUIRED_COLUMNS = {
    "component",
    "rows",
    "ncu_denominator_rows",
    "unit",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "power_semantics",
    "median",
    "confidence_class",
}

REQUIRED_NCU_CANDIDATES = {
    "tensor_increment_candidate",
    "register_control_candidate",
    "shared_memory_path",
    "global_l1_hit_path",
    "l2_hit_path",
    "global_address_control",
}

NCU_ACCEPTANCE_REQUIRED_COLUMNS = {
    "mode",
    "status",
    "component_candidate",
    "acceptance",
    "acceptance_reason",
    "l1_hit_rate_pct",
    "l1_path_hit_rate_pct",
    "l2_hit_rate_pct",
    "l2_path_hit_rate_pct",
    "shared_accesses",
    "shared_bytes",
    "shared_inst",
    "l1_bytes",
    "l1_request_bytes",
    "l1_hit_bytes",
    "l1_miss_bytes",
    "l2_bytes",
    "l2_read_bytes",
    "l2_read_hit_sectors",
    "l2_read_miss_sectors",
    "local_read_bytes",
    "local_write_bytes",
    "spill_zero_verified",
    "spill_evidence_source",
    "dram_bytes",
    "tensor_hmma_inst",
    "stall_long_scoreboard_pct",
}

RAW_SUFFIXES = ("tensor", "shared", "l1", "l2", "dram")

RAW_REQUIRED_MEASUREMENT_COLUMNS = {
    "mode",
    "elapsed_s",
    "measurement_start_epoch_ms",
    "measurement_end_epoch_ms",
    "E_before_mJ",
    "E_after_mJ",
    "delta_E_J",
    "idle_baseline_J",
    "net_E_J",
    "ITER",
    "notes",
}

TENSOR_PAIR_CALIBRATION_REQUIRED_COLUMNS = {
    "target_profile",
    "gpu_list",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "store_repeat",
    "calibration_source_mode",
    "treatment_target_seconds",
    "control_min_seconds",
    "treatment_calibrated_iters",
    "control_min_calibrated_iters",
    "resolved_iters",
    "resolution_policy",
    "status",
    "calibration_command",
    "treatment_calibration_command",
    "control_calibration_command",
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

NCU_REQUIRED_COLUMNS = {
    "label",
    "mode",
    "status",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "ITER",
    "reuse_factor",
    "load_repeat",
    "l1_hit_rate_pct",
    "l1_path_hit_rate_pct",
    "l2_hit_rate_pct",
    "l2_path_hit_rate_pct",
    "l1_accesses",
    "l1_access_unit",
    "l2_accesses",
    "l2_access_unit",
    "dram_accesses",
    "dram_access_unit",
    "l1_bytes",
    "l1_request_bytes",
    "l1_hit_bytes",
    "l1_miss_bytes",
    "l2_bytes",
    "l2_read_bytes",
    "l2_read_hit_sectors",
    "l2_read_miss_sectors",
    "dram_bytes",
    "shared_accesses",
    "shared_bytes",
    "shared_inst",
    "tensor_hmma_inst",
    "local_read_bytes",
    "local_write_bytes",
    "spill_zero_verified",
    "spill_evidence_source",
    "stall_long_scoreboard_pct",
    "missing_metrics",
}

NCU_COMMON_NUMERIC_COLUMNS = {
    "l1_hit_rate_pct",
    "l2_hit_rate_pct",
    "l1_accesses",
    "l2_accesses",
    "dram_accesses",
    "l1_bytes",
    "l2_bytes",
    "dram_bytes",
    "stall_long_scoreboard_pct",
}

NCU_REQUIRED_MODES = {
    "clocked_empty",
    "reg_operand_only",
    "reg_mma",
    "shared_scalar_load_only",
    "global_addr_only",
    "global_l1_load_only",
    "l2_cg_load_only",
    "dram_cg_load_only",
}

PROFILE_EXTRA_NCU_REQUIRED_MODES: dict[str, set[str]] = {}

NCU_MIN_FACTOR_POINTS = 3

NCU_REUSE_SWEEP_MODES = {"reg_operand_only", "reg_mma"}

NCU_LOAD_REPEAT_SWEEP_MODES = {
    "shared_scalar_load_only",
    "global_l1_load_only",
    "l2_cg_load_only",
    "dram_cg_load_only",
}

NCU_POSITIVE_BY_MODE = {
    "shared_scalar_load_only": ("shared_accesses", "shared_bytes", "shared_inst"),
    "shared_load_only": ("shared_accesses", "shared_bytes", "shared_inst"),
    "global_l1_load_only": ("l1_accesses", "l1_request_bytes", "l1_hit_bytes"),
    "l2_cg_load_only": (
        "l1_request_bytes",
        "l2_accesses",
        "l2_read_bytes",
        "l2_read_hit_sectors",
    ),
    "dram_cg_load_only": ("dram_accesses", "dram_bytes"),
    "dram_load_only": ("dram_accesses", "dram_bytes"),
    "reg_mma": ("tensor_hmma_inst",),
}

NCU_L1_HIT_MIN_PCT = 95.0
NCU_L1_L2_RATIO_MAX = 0.01
NCU_L1_DRAM_RATIO_MAX = 0.01
NCU_L2_L1_BYTES_RATIO_MAX = 0.01
NCU_L2_L1_HIT_MAX_PCT = 1.0
NCU_L2_HIT_MIN_PCT = 95.0
NCU_L2_DRAM_RATIO_MAX = 0.02
NCU_SHARED_GLOBAL_RATIO_MAX = 0.02
NCU_DRAM_L1_HIT_MAX_PCT = 1.0
NCU_DRAM_L2_HIT_MAX_PCT = 5.0
NCU_DRAM_L2_EXPECTED_MULTIPLIER = 2.0
NCU_DRAM_L2_EXPECTED_SLACK_PCT = 2.0
NCU_CONTROL_HMMA_PER_BLOCK_MAX = 1.0
NCU_CONTROL_HMMA_PER_REG_OP_MAX = 1.0e-5
NCU_GLOBAL_ADDRESS_CONTROL_DRAM_RATIO_MAX = 1.0e-3
NCU_DRAM_L2_RATIO_MIN = 0.5
NCU_TENSOR_MEMORY_BYTES_PER_HMMA_MAX = 1.0
NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX = 1.0
TENSOR_CONTROL_MIN_ELAPSED_S = 0.8
L2_CONTROL_MIN_ELAPSED_S = 0.8
DRAM_CONTROL_MIN_ELAPSED_S = 0.8
CONTROL_NCU_REQUIRED_COMPONENTS = {
    "tensor_mma_increment",
    "global_l1_hit_path",
    "l2_hit_cg_path",
    "dram_cg_stream_path",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: str) -> int | None:
    try:
        return int(float(value.strip()))
    except (AttributeError, ValueError):
        return None


def parse_float(value: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return out if math.isfinite(out) else float("nan")


def same_int(value: str, expected: int) -> bool:
    actual = parse_int(value)
    return actual is not None and actual == expected


def add(
    rows: list[dict[str, str]],
    *,
    area: str,
    check: str,
    status: str,
    expected: str,
    actual: str,
    evidence: str,
    action: str,
) -> None:
    rows.append(
        {
            "area": area,
            "check": check,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "action": action,
        }
    )


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def expected_paths(profile: str, tag: str) -> dict[str, Path | list[Path]]:
    base = f"{profile}_component_finalplan_{tag}"
    paths: dict[str, Path | list[Path]] = {
        "command_shell": Path(f"results/summary/{base}_commands.sh"),
        "command_plan": Path(f"results/summary/{base}_command_plan.md"),
        "preflight": Path(f"results/summary/{base}_preflight.md"),
        "raw": [Path(f"results/raw/{base}_{suffix}.csv") for suffix in RAW_SUFFIXES],
        "tensor_pair_calibration": Path(
            f"results/raw/{base}_tensor_pair_calibration.csv"
        ),
        "l2_pair_calibration": Path(
            f"results/raw/{base}_l2_pair_calibration.csv"
        ),
        "dram_pair_calibration": Path(
            f"results/raw/{base}_dram_pair_calibration.csv"
        ),
        "power_api": Path(f"results/summary/{base}_power_api_audit.csv"),
        "power_state": Path(f"results/summary/{base}_power_state_audit.csv"),
        "ncu_summary": Path(
            f"results/ncu/{profile}_component_finalplan_ncu_factor_{tag}/"
            "ncu_cache_validation_summary.csv"
        ),
        "ncu_acceptance": Path(f"results/summary/{base}_ncu_acceptance.csv"),
        "matched_summary": Path(f"results/summary/{base}_matched_control_summary.csv"),
        "matched_detail": Path(f"results/summary/{base}_matched_control_detail.csv"),
        "reliability": Path(f"results/summary/{base}_component_reliability_audit.csv"),
        "instability": Path(
            f"results/summary/{base}_matched_control_instability_audit.csv"
        ),
        "strict_summary": Path(
            f"results/summary/{profile}_strict_scope_fresh_ncu_component_coefficients_{tag}.csv"
        ),
        "strict_audit": Path(
            f"results/summary/{profile}_strict_scope_fresh_ncu_component_summary_audit_{tag}.csv"
        ),
    }
    if profile in {"a100", "v100"}:
        paths["l2_path_selection"] = Path(
            f"results/summary/{base}_l2_path_selection.csv"
        )
    return paths


def rel(repo: Path, path: Path) -> Path:
    return repo / path


def audit_file_presence(
    repo: Path, rows: list[dict[str, str]], paths: dict[str, Path | list[Path]]
) -> None:
    for name, value in paths.items():
        if isinstance(value, list):
            missing = [str(path) for path in value if not rel(repo, path).exists()]
            add(
                rows,
                area="files",
                check=f"{name}_present",
                status="pass" if not missing else "missing",
                expected="all expected files exist",
                actual="ok" if not missing else "missing=" + ";".join(missing),
                evidence=";".join(str(path) for path in value),
                action="copy the missing platform result files back from the target node",
            )
        else:
            exists = rel(repo, value).exists()
            add(
                rows,
                area="files",
                check=f"{name}_present",
                status="pass" if exists else "missing",
                expected="file exists",
                actual="exists" if exists else "missing",
                evidence=str(value),
                action="run the generated command package or copy the artifact from the node",
            )


def audit_l2_path_selection(
    repo: Path,
    rows: list[dict[str, str]],
    path: Path,
    *,
    profile: str,
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    selection_rows = read_csv(full)
    required = {
        "policy",
        "layout",
        "blocks_per_SM",
        "W_SM_KiB",
        "l1_path_hit_rate_pct",
        "l2_path_hit_rate_pct",
        "l2_native_read_hit_rate_pct",
        "native_l2_gate",
        "l2_read_sector_conservation_ratio",
        "l2_read_bytes_to_expected",
        "dram_read_to_l2_read_ratio",
        "selected_candidate",
        "status",
        "reason",
    }
    columns = set(selection_rows[0]) if selection_rows else set()
    missing = sorted(required - columns)
    add(
        rows,
        area="l2_selection",
        check="l2_path_selection_schema",
        status="pass" if selection_rows and not missing else "fail",
        expected="NCU-first L2 selector fields are complete",
        actual=(
            f"rows={len(selection_rows)}"
            if selection_rows and not missing
            else "missing=" + ",".join(missing or ["rows"])
        ),
        evidence=str(path),
        action="rerun the generated L2 precheck with the current selector",
    )
    if not selection_rows or missing:
        return

    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in selection_rows:
        key = (row.get("policy", ""), row.get("layout", ""), row.get("blocks_per_SM", ""))
        grouped.setdefault(key, []).append(row)
    expected_w = {16, 128} if profile == "a100" else {32, 64}
    accepted = []
    selected = []
    for key, candidate_rows in grouped.items():
        observed_w = {
            value
            for value in (parse_int(row.get("W_SM_KiB", "")) for row in candidate_rows)
            if value is not None
        }
        if observed_w == expected_w and all(
            row.get("status") == "pass" for row in candidate_rows
        ):
            accepted.append(key)
        if all(row.get("selected_candidate") == "yes" for row in candidate_rows):
            selected.append(key)
        elif any(row.get("selected_candidate") == "yes" for row in candidate_rows):
            selected.append((key[0], key[1], f"{key[2]}:partial_selection"))
    policy_valid = not (
        profile == "v100"
        and any(row.get("policy") == "persisting" for row in selection_rows)
    )
    native_gate_valid = all(
        row.get("native_l2_gate") == "required"
        if profile == "a100"
        else row.get("native_l2_gate")
        in {"optional_unavailable", "optional_present_cross_checked"}
        for row in selection_rows
    )
    passed = (
        len(selected) == 1
        and selected[0] in accepted
        and policy_valid
        and native_gate_valid
    )
    add(
        rows,
        area="l2_selection",
        check="l2_path_selected_before_energy",
        status="pass" if passed else "fail",
        expected=(
            f"exactly one selected candidate passes W_SM={','.join(str(v) for v in sorted(expected_w))} KiB/SM; "
            + ("V100 policy must be normal" if profile == "v100" else "A100 policy may be normal or persisting")
        ),
        actual=(
            "selected="
            + (";".join("/".join(key) for key in selected) if selected else "none")
            + ";fully_passing="
            + (";".join("/".join(key) for key in accepted) if accepted else "none")
            + f";native_gate_valid={str(native_gate_valid).lower()}"
        ),
        evidence=str(path),
        action=(
            "do not report an L2 coefficient; inspect candidate raw metrics and NCU stderr"
        ),
    )


def audit_preflight(
    repo: Path,
    rows: list[dict[str, str]],
    path: Path,
    *,
    profile: str,
    expected_semantics: str,
    expected_active_sm: int | None,
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    text = full.read_text(encoding="utf-8")
    metadata = PROFILE_METADATA[profile]
    required_terms = [
        "# GPU Support Preflight",
        "## Preflight Verdict",
        f"- Requested profile: `{profile}`",
        "- `strict`: true",
        "- `profile_gate`: pass",
        "- `cuda_compiler_gate`: pass",
        "- `ncu_gate`: pass",
        "- `dry_run_gate`: pass",
        "- `overall`: pass",
        "- `errors`: none",
        "## GPU",
        "## Power Scope",
        "## Selected Harness Profile",
        "## CUDA Compiler",
        f"- `target`: compute_{metadata['compute_capability'].replace('.', '')}",
        "- `target_supported`: true",
        "## Nsight Compute",
        "## Binary Dry Run",
        "do not mix module or memory power into component coefficients",
        "- `uuid`:",
        "- `driver_version`:",
        "- `power_query_fields`:",
        "- `module_power_query_rc`:",
        "- `power_detail_query_rc`:",
        f"- `power_usage_semantics`: {expected_semantics}",
        "- `version_rc`: 0",
        "- `list_chips_rc`: 0",
        "- `chip_supported`: true",
        "- `query_metrics_ok`: true",
        "- `return_code`: 0",
        "- `dry_run_gpu`:",
        f"target_profile={profile}",
        f"chip={metadata['chip']}",
        f"compute_capability={metadata['compute_capability']}",
        f"target_l2_MiB={metadata['l2_mib']}",
        "target_unified_L1_shared_KiB_per_SM="
        f"{metadata['unified_l1_shared_kib_per_sm']}",
        f"target_shared_KiB_per_SM={metadata['shared_kib_per_sm']}",
    ]
    if expected_active_sm is not None:
        required_terms.extend(
            [
                f"- `dry_run_active_sm`: {expected_active_sm}",
                f"active_SM={expected_active_sm}",
            ]
        )
    profile_terms = [
        f"- Detected profile: `{profile}`",
        f"target_profile={profile}",
    ]
    missing = [term for term in required_terms if term not in text]
    if not any(term in text for term in profile_terms):
        missing.append(f"profile_not_{profile}")
    add(
        rows,
        area="preflight",
        check="preflight_power_scope_policy",
        status="pass" if not missing else "fail",
        expected=(
            "preflight records profile, power scope, NCU metric support, "
            "driver/UUID, module/memory power metadata, power semantics, "
            "target architecture metadata, active SM, and binary dry-run success"
        ),
        actual="ok" if not missing else "missing=" + ";".join(missing[:12]),
        evidence=str(path),
        action=(
            "rerun scripts/preflight_gpu_support.py on the target node and keep "
            "the generated markdown with the result package"
        ),
    )


def audit_raw_energy(
    repo: Path,
    rows: list[dict[str, str]],
    raw_paths: list[Path],
    *,
    profile: str,
    expected_semantics: str,
    expected_active_sm: int | None,
    expected_sm_count: int | None,
) -> None:
    problems: list[str] = []
    total_rows = 0
    metadata = PROFILE_METADATA[profile]
    exact_columns = {
        "profile_name": metadata["profile_name"],
        "architecture_family": metadata["architecture_family"],
        "chip": metadata["chip"],
        "compute_capability": metadata["compute_capability"],
    }
    int_columns = {
        "l2_mib": int(metadata["l2_mib"]),
        "unified_l1_shared_kib_per_sm": int(
            metadata["unified_l1_shared_kib_per_sm"]
        ),
        "shared_kib_per_sm": int(metadata["shared_kib_per_sm"]),
    }
    for path in raw_paths:
        full = rel(repo, path)
        if not full.exists():
            continue
        csv_rows = read_csv(full)
        total_rows += len(csv_rows)
        for idx, row in enumerate(csv_rows, start=2):
            prefix = f"{path}:{idx}"
            for column, expected in exact_columns.items():
                if row.get(column) != expected:
                    problems.append(f"{prefix}:{column}={row.get(column)}")
            for column, expected in int_columns.items():
                if not same_int(row.get(column, ""), expected):
                    problems.append(f"{prefix}:{column}={row.get(column)}")
            if expected_active_sm is not None and not same_int(
                row.get("active_SM", ""), expected_active_sm
            ):
                problems.append(f"{prefix}:active_SM={row.get('active_SM')}")
            row_sm_count = parse_int(row.get("sm_count", ""))
            if expected_sm_count is not None:
                if row_sm_count != expected_sm_count:
                    problems.append(f"{prefix}:sm_count={row.get('sm_count')}")
            elif expected_active_sm is not None:
                if row_sm_count is None:
                    problems.append(f"{prefix}:sm_count={row.get('sm_count')}")
                elif row_sm_count < expected_active_sm:
                    problems.append(
                        f"{prefix}:sm_count_lt_active={row.get('sm_count')}"
                    )
            if row.get("energy_source") != "nvml_total_energy":
                problems.append(f"{prefix}:energy_source={row.get('energy_source')}")
            if row.get("energy_integration_method") != "total_energy_mj_delta":
                problems.append(
                    f"{prefix}:integration={row.get('energy_integration_method')}"
                )
            if row.get("measurement_scope") != "gpu_device_total_energy_counter":
                problems.append(f"{prefix}:scope={row.get('measurement_scope')}")
            if not truthy(row.get("nvml_total_energy_supported", "")):
                problems.append(f"{prefix}:total_energy_supported=false")
            if row.get("nvml_power_usage_semantics") != expected_semantics:
                problems.append(
                    f"{prefix}:semantics={row.get('nvml_power_usage_semantics')}"
                )
            mode = row.get("mode", "")
            notes = row.get("notes", "")
            if mode in {"reg_mma", "reg_operand_only"} and (
                "tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2"
                not in notes
            ):
                problems.append(f"{prefix}:missing_tensor_kernel_revision")
            if mode in {"l2_cg_load_only", "dram_cg_load_only"} and (
                "global_warmup_policy=ld_global_cg" not in notes
            ):
                problems.append(f"{prefix}:missing_cg_warmup_policy")
            missing_measurement = sorted(
                column for column in RAW_REQUIRED_MEASUREMENT_COLUMNS if column not in row
            )
            if missing_measurement:
                problems.append(
                    f"{prefix}:missing_measurement_columns="
                    + ",".join(missing_measurement)
                )
            elapsed_s = parse_float(row.get("elapsed_s", ""))
            measurement_start_ms = parse_float(
                row.get("measurement_start_epoch_ms", "")
            )
            measurement_end_ms = parse_float(
                row.get("measurement_end_epoch_ms", "")
            )
            e_before = parse_float(row.get("E_before_mJ", ""))
            e_after = parse_float(row.get("E_after_mJ", ""))
            delta_j = parse_float(row.get("delta_E_J", ""))
            idle_j = parse_float(row.get("idle_baseline_J", ""))
            net_j = parse_float(row.get("net_E_J", ""))
            iter_count = parse_float(row.get("ITER", ""))
            if elapsed_s is None or elapsed_s <= 0.0:
                problems.append(f"{prefix}:elapsed_s={row.get('elapsed_s', '')}")
            if measurement_start_ms is None or measurement_start_ms <= 0.0:
                problems.append(
                    f"{prefix}:measurement_start_epoch_ms="
                    f"{row.get('measurement_start_epoch_ms', '')}"
                )
            if (
                measurement_end_ms is None
                or measurement_start_ms is None
                or measurement_end_ms < measurement_start_ms
            ):
                problems.append(
                    f"{prefix}:measurement_end_epoch_ms="
                    f"{row.get('measurement_end_epoch_ms', '')}"
                )
            if (
                elapsed_s is not None
                and elapsed_s > 0.0
                and measurement_start_ms is not None
                and measurement_end_ms is not None
                and measurement_end_ms >= measurement_start_ms
            ):
                interval_ms = measurement_end_ms - measurement_start_ms
                expected_ms = elapsed_s * 1000.0
                if abs(interval_ms - expected_ms) > max(5.0, expected_ms * 0.01):
                    problems.append(
                        f"{prefix}:measurement_interval_elapsed_mismatch="
                        f"{interval_ms:g}/{expected_ms:g}ms"
                    )
            if e_before is None or e_before <= 0.0:
                problems.append(f"{prefix}:E_before_mJ={row.get('E_before_mJ', '')}")
            if e_after is None or e_after <= 0.0:
                problems.append(f"{prefix}:E_after_mJ={row.get('E_after_mJ', '')}")
            if (
                e_before is not None
                and e_after is not None
                and e_after <= e_before
            ):
                problems.append(f"{prefix}:E_after_not_greater_than_E_before")
            if delta_j is None or delta_j <= 0.0:
                problems.append(f"{prefix}:delta_E_J={row.get('delta_E_J', '')}")
            if (
                e_before is not None
                and e_after is not None
                and delta_j is not None
                and abs(delta_j - ((e_after - e_before) / 1000.0))
                > max(1.0e-6, abs(delta_j) * 1.0e-6)
            ):
                problems.append(f"{prefix}:delta_E_J_counter_mismatch")
            if idle_j is None or idle_j < 0.0:
                problems.append(f"{prefix}:idle_baseline_J={row.get('idle_baseline_J', '')}")
            if net_j is None or net_j < 0.0:
                problems.append(f"{prefix}:net_E_J={row.get('net_E_J', '')}")
            if iter_count is None or iter_count <= 0.0:
                problems.append(f"{prefix}:ITER={row.get('ITER', '')}")
    no_rows = total_rows <= 0
    if no_rows:
        problems.append("no_raw_rows_read")
    add(
        rows,
        area="raw",
        check="raw_energy_power_policy",
        status="pass" if not problems else "missing" if no_rows else "fail",
        expected=(
            "raw rows use target profile metadata, target active SM, total-energy "
            "delta, GPU/device scope, exact timed-kernel epoch interval, explicit "
            "measurement_scope, profile "
            "power semantics, positive counter delta, elapsed time, and iteration "
            "count; Tensor rows carry the matched-add/scalar-epilogue revision and "
            "CG rows carry the ld.global.cg warm-up policy"
        ),
        actual=f"rows={total_rows}" if not problems else ";".join(problems[:12]),
        evidence=";".join(str(path) for path in raw_paths),
        action=(
            "copy raw energy CSVs from the target node"
            if no_rows
            else "rerun energy sweep with the correct target profile and NVML policy"
        ),
    )


def tensor_pair_coord(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        row.get(column, "").strip()
        for column in (
            "W_SM_KiB",
            "blocks_per_SM",
            "active_SM",
            "reuse_factor",
            "load_repeat",
            "store_repeat",
        )
    )


def audit_tensor_pair_calibration(
    repo: Path,
    rows: list[dict[str, str]],
    calibration_path: Path,
    tensor_raw_path: Path,
    *,
    profile: str,
) -> None:
    calibration_full = rel(repo, calibration_path)
    tensor_full = rel(repo, tensor_raw_path)
    if not calibration_full.exists() or not tensor_full.exists():
        return

    with calibration_full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        calibration_fields = set(reader.fieldnames or [])
        calibration_rows = list(reader)
    with tensor_full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        tensor_fields = set(reader.fieldnames or [])
        tensor_rows = list(reader)

    problems: list[str] = []
    missing_calibration = sorted(
        TENSOR_PAIR_CALIBRATION_REQUIRED_COLUMNS - calibration_fields
    )
    required_raw = {
        "mode",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "ITER",
    }
    missing_raw = sorted(required_raw - tensor_fields)
    if missing_calibration:
        problems.append("calibration_missing_columns=" + ",".join(missing_calibration))
    if missing_raw:
        problems.append("tensor_raw_missing_columns=" + ",".join(missing_raw))

    calibration_by_coord: dict[tuple[str, ...], int] = {}
    if not missing_calibration:
        for idx, row in enumerate(calibration_rows, start=2):
            coord = tensor_pair_coord(row)
            resolved = parse_int(row.get("resolved_iters", ""))
            treatment_candidate = parse_int(
                row.get("treatment_calibrated_iters", "")
            )
            control_candidate = parse_int(
                row.get("control_min_calibrated_iters", "")
            )
            treatment_target_seconds = parse_float(
                row.get("treatment_target_seconds", "")
            )
            control_min_seconds = parse_float(row.get("control_min_seconds", ""))
            if row.get("target_profile", "") != profile:
                problems.append(
                    f"calibration:{idx}:profile={row.get('target_profile', '')}"
                )
            if row.get("calibration_source_mode", "") != "reg_mma":
                problems.append(
                    f"calibration:{idx}:source={row.get('calibration_source_mode', '')}"
                )
            if row.get("status", "") != "pair_locked":
                problems.append(f"calibration:{idx}:status={row.get('status', '')}")
            if row.get("resolution_policy", "") != "max_treatment_and_control_min_iters":
                problems.append(
                    f"calibration:{idx}:resolution_policy="
                    f"{row.get('resolution_policy', '')}"
                )
            if treatment_target_seconds is None or treatment_target_seconds <= 0.0:
                problems.append(
                    f"calibration:{idx}:treatment_target_seconds="
                    f"{row.get('treatment_target_seconds', '')}"
                )
            if control_min_seconds is None or control_min_seconds <= 0.0:
                problems.append(
                    f"calibration:{idx}:control_min_seconds="
                    f"{row.get('control_min_seconds', '')}"
                )
            treatment_command = row.get("treatment_calibration_command", "")
            control_command = row.get("control_calibration_command", "")
            if not (
                "--mode reg_mma" in treatment_command
                and "--calibrate-only" in treatment_command
            ):
                problems.append(
                    f"calibration:{idx}:bad_treatment_calibration_command"
                )
            if not (
                "--mode reg_operand_only" in control_command
                and "--calibrate-only" in control_command
                and "--seconds" in control_command
            ):
                problems.append(f"calibration:{idx}:bad_control_calibration_command")
            if treatment_candidate is None or treatment_candidate <= 0:
                problems.append(
                    f"calibration:{idx}:treatment_calibrated_iters="
                    f"{row.get('treatment_calibrated_iters', '')}"
                )
            if control_candidate is None or control_candidate <= 0:
                problems.append(
                    f"calibration:{idx}:control_min_calibrated_iters="
                    f"{row.get('control_min_calibrated_iters', '')}"
                )
            if resolved is None or resolved <= 0:
                problems.append(
                    f"calibration:{idx}:resolved_iters={row.get('resolved_iters', '')}"
                )
                continue
            if (
                treatment_candidate is not None
                and treatment_candidate > 0
                and control_candidate is not None
                and control_candidate > 0
                and resolved != max(treatment_candidate, control_candidate)
            ):
                problems.append(
                    f"calibration:{idx}:resolved_not_candidate_max="
                    f"{resolved}!={max(treatment_candidate, control_candidate)}"
                )
            if coord in calibration_by_coord and calibration_by_coord[coord] != resolved:
                problems.append(f"calibration:{idx}:duplicate_conflict={coord}")
            calibration_by_coord[coord] = resolved

    raw_iters: dict[tuple[str, ...], dict[str, set[int]]] = {}
    if not missing_raw:
        for idx, row in enumerate(tensor_rows, start=2):
            mode = row.get("mode", "")
            if mode not in {"reg_mma", "reg_operand_only"}:
                continue
            coord = tensor_pair_coord(row)
            iters = parse_int(row.get("ITER", ""))
            if iters is None or iters <= 0:
                problems.append(f"tensor_raw:{idx}:ITER={row.get('ITER', '')}")
                continue
            raw_iters.setdefault(coord, {}).setdefault(mode, set()).add(iters)

    for coord, by_mode in sorted(raw_iters.items()):
        missing_modes = {"reg_mma", "reg_operand_only"} - set(by_mode)
        if missing_modes:
            problems.append(
                f"tensor_raw:{coord}:missing_modes={','.join(sorted(missing_modes))}"
            )
            continue
        combined = by_mode["reg_mma"] | by_mode["reg_operand_only"]
        if len(combined) != 1:
            problems.append(
                f"tensor_raw:{coord}:ITER_sets="
                f"{sorted(by_mode['reg_mma'])}/{sorted(by_mode['reg_operand_only'])}"
            )
            continue
        actual = next(iter(combined))
        resolved = calibration_by_coord.get(coord)
        if resolved is None:
            problems.append(f"tensor_raw:{coord}:missing_calibration")
        elif resolved != actual:
            problems.append(f"tensor_raw:{coord}:resolved={resolved}:actual={actual}")

    extra_calibration = sorted(set(calibration_by_coord) - set(raw_iters))
    if extra_calibration:
        problems.append(f"calibration_without_raw={extra_calibration[:3]}")
    if not raw_iters:
        problems.append("no_tensor_pair_rows")

    add(
        rows,
        area="analysis",
        check="tensor_pair_calibration_policy",
        status="pass" if not problems else "fail",
        expected=(
            "one treatment/control-floor dual calibration per Tensor coordinate, "
            "resolved ITER=max(candidate ITERs), pair_locked manifest, and identical "
            "positive ITER in reg_mma/reg_operand_only raw rows"
        ),
        actual=(
            f"coordinates={len(raw_iters)}, calibrations={len(calibration_by_coord)}"
            if not problems
            else ";".join(problems[:12])
        ),
        evidence=f"{calibration_path};{tensor_raw_path}",
        action=(
            "rerun the Tensor sweep with --tensor-pair-lock-iters and do not append "
            "to raw rows from a duration-calibrated run"
        ),
    )


def audit_memory_pair_calibration(
    repo: Path,
    rows: list[dict[str, str]],
    calibration_path: Path,
    raw_path: Path,
    *,
    profile: str,
    treatment_mode: str,
    pair_label: str,
) -> None:
    calibration_full = rel(repo, calibration_path)
    raw_full = rel(repo, raw_path)
    if not calibration_full.exists() or not raw_full.exists():
        return

    with calibration_full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        calibration_fields = set(reader.fieldnames or [])
        calibration_rows = list(reader)
    with raw_full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_fields = set(reader.fieldnames or [])
        raw_rows = list(reader)

    required_raw = {
        "mode",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "ITER",
    }
    problems: list[str] = []
    missing_calibration = sorted(
        TENSOR_PAIR_CALIBRATION_REQUIRED_COLUMNS - calibration_fields
    )
    missing_raw = sorted(required_raw - raw_fields)
    if missing_calibration:
        problems.append("calibration_missing_columns=" + ",".join(missing_calibration))
    if missing_raw:
        problems.append(f"{pair_label}_raw_missing_columns=" + ",".join(missing_raw))

    calibration_by_coord: dict[tuple[str, ...], int] = {}
    if not missing_calibration:
        for idx, row in enumerate(calibration_rows, start=2):
            coord = tensor_pair_coord(row)
            treatment_candidate = parse_int(row.get("treatment_calibrated_iters", ""))
            control_candidate = parse_int(row.get("control_min_calibrated_iters", ""))
            resolved = parse_int(row.get("resolved_iters", ""))
            treatment_target_seconds = parse_float(
                row.get("treatment_target_seconds", "")
            )
            control_min_seconds = parse_float(row.get("control_min_seconds", ""))
            if row.get("target_profile", "") != profile:
                problems.append(f"calibration:{idx}:profile={row.get('target_profile', '')}")
            if row.get("calibration_source_mode", "") != treatment_mode:
                problems.append(f"calibration:{idx}:source={row.get('calibration_source_mode', '')}")
            if row.get("status", "") != "pair_locked":
                problems.append(f"calibration:{idx}:status={row.get('status', '')}")
            if row.get("resolution_policy", "") != "max_treatment_and_control_min_iters":
                problems.append(
                    f"calibration:{idx}:resolution_policy={row.get('resolution_policy', '')}"
                )
            if treatment_target_seconds is None or treatment_target_seconds <= 0.0:
                problems.append(
                    f"calibration:{idx}:treatment_target_seconds="
                    f"{row.get('treatment_target_seconds', '')}"
                )
            if control_min_seconds is None or control_min_seconds <= 0.0:
                problems.append(
                    f"calibration:{idx}:control_min_seconds="
                    f"{row.get('control_min_seconds', '')}"
                )
            treatment_command = row.get("treatment_calibration_command", "")
            control_command = row.get("control_calibration_command", "")
            if not (
                f"--mode {treatment_mode}" in treatment_command
                and "--calibrate-only" in treatment_command
            ):
                problems.append(f"calibration:{idx}:bad_treatment_calibration_command")
            if not (
                "--mode global_addr_only" in control_command
                and "--calibrate-only" in control_command
            ):
                problems.append(f"calibration:{idx}:bad_control_calibration_command")
            candidates_ok = (
                treatment_candidate is not None
                and treatment_candidate > 0
                and control_candidate is not None
                and control_candidate > 0
            )
            if not candidates_ok:
                problems.append(f"calibration:{idx}:invalid_candidate_iters")
            if resolved is None or resolved <= 0:
                problems.append(f"calibration:{idx}:resolved_iters={row.get('resolved_iters', '')}")
                continue
            if candidates_ok and resolved != max(treatment_candidate, control_candidate):
                problems.append(f"calibration:{idx}:resolved_not_candidate_max")
            calibration_by_coord[coord] = resolved

    raw_iters: dict[tuple[str, ...], dict[str, set[int]]] = {}
    if not missing_raw:
        for idx, row in enumerate(raw_rows, start=2):
            mode = row.get("mode", "")
            if mode not in {"global_addr_only", treatment_mode}:
                continue
            coord = tensor_pair_coord(row)
            iters = parse_int(row.get("ITER", ""))
            if iters is None or iters <= 0:
                problems.append(f"{pair_label}_raw:{idx}:ITER={row.get('ITER', '')}")
                continue
            raw_iters.setdefault(coord, {}).setdefault(mode, set()).add(iters)

    for coord, by_mode in sorted(raw_iters.items()):
        missing_modes = {"global_addr_only", treatment_mode} - set(by_mode)
        if missing_modes:
            problems.append(
                f"{pair_label}_raw:{coord}:missing_modes={','.join(sorted(missing_modes))}"
            )
            continue
        combined = by_mode["global_addr_only"] | by_mode[treatment_mode]
        if len(combined) != 1:
            problems.append(f"{pair_label}_raw:{coord}:ITER_sets={sorted(combined)}")
            continue
        actual = next(iter(combined))
        resolved = calibration_by_coord.get(coord)
        if resolved is None:
            problems.append(f"{pair_label}_raw:{coord}:missing_calibration")
        elif resolved != actual:
            problems.append(
                f"{pair_label}_raw:{coord}:resolved={resolved}:actual={actual}"
            )
    extra_calibration = sorted(set(calibration_by_coord) - set(raw_iters))
    if extra_calibration:
        problems.append(f"calibration_without_raw={extra_calibration[:3]}")
    if not raw_iters:
        problems.append(f"no_{pair_label}_pair_rows")

    add(
        rows,
        area="analysis",
        check=f"{pair_label}_pair_calibration_policy",
        status="pass" if not problems else "fail",
        expected=(
            f"one dual calibration per {pair_label.upper()} coordinate, resolved "
            f"ITER=max(candidate ITERs), and identical positive ITER in "
            f"{treatment_mode}/global_addr_only"
        ),
        actual=(
            f"coordinates={len(raw_iters)}, calibrations={len(calibration_by_coord)}"
            if not problems
            else ";".join(problems[:12])
        ),
        evidence=f"{calibration_path};{raw_path}",
        action=(
            f"rerun the {pair_label.upper()} sweep with --memory-pair-lock-iters "
            f"and do not append duration-calibrated {pair_label.upper()} rows"
        ),
    )


def audit_dram_pair_calibration(
    repo: Path,
    rows: list[dict[str, str]],
    calibration_path: Path,
    dram_raw_path: Path,
    *,
    profile: str,
) -> None:
    """Backward-compatible wrapper for the DRAM pair package gate."""

    audit_memory_pair_calibration(
        repo,
        rows,
        calibration_path,
        dram_raw_path,
        profile=profile,
        treatment_mode="dram_cg_load_only",
        pair_label="dram",
    )


def audit_power_api(
    repo: Path,
    rows: list[dict[str, str]],
    path: Path,
    *,
    expected_semantics: str,
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    problems: list[str] = []
    csv_rows = read_csv(full)
    for idx, row in enumerate(csv_rows, start=2):
        prefix = f"{path}:{idx}"
        if row.get("status") != "final_candidate":
            problems.append(f"{prefix}:status={row.get('status')}")
        if row.get("energy_source") != "nvml_total_energy":
            problems.append(f"{prefix}:energy_source={row.get('energy_source')}")
        if row.get("energy_integration_method") != "total_energy_mj_delta":
            problems.append(f"{prefix}:integration={row.get('energy_integration_method')}")
        if row.get("measurement_scope") != "gpu_device_total_energy_counter":
            problems.append(f"{prefix}:scope={row.get('measurement_scope')}")
        if row.get("actual_power_semantics") != expected_semantics:
            problems.append(f"{prefix}:semantics={row.get('actual_power_semantics')}")
    if not csv_rows:
        problems.append("empty_power_api_audit")
    add(
        rows,
        area="power",
        check="power_api_audit_policy",
        status="pass" if not problems else "fail",
        expected="all rows final_candidate with total-energy GPU/device scope",
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action="rerun scripts/audit_power_api_measurements.py with --fail-on-provisional",
    )


def audit_power_state(repo: Path, rows: list[dict[str, str]], path: Path) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    problems: list[str] = []
    with full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        csv_rows = list(reader)
    missing_columns = sorted(POWER_STATE_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns))
    for idx, row in enumerate(csv_rows, start=2):
        status = row.get("status", "")
        eligible = row.get("coefficient_eligible", "").lower()
        if not status:
            problems.append(f"{path}:{idx}:missing_status")
        if eligible not in {"true", "false"}:
            problems.append(f"{path}:{idx}:missing_eligibility")
        if status == "reject":
            problems.append(f"{path}:{idx}:reject")
        if eligible == "false":
            problems.append(f"{path}:{idx}:coefficient_ineligible")
        for column in ("W_SM_KiB", "blocks_per_SM", "active_SM", "elapsed_s"):
            value = parse_float(row.get(column, ""))
            if value is None or value <= 0.0:
                problems.append(f"{path}:{idx}:{column}={row.get(column, '')}")
        net_e = parse_float(row.get("net_E_J", ""))
        if net_e is None or net_e < 0.0:
            problems.append(f"{path}:{idx}:net_E_J={row.get('net_E_J', '')}")
        for column in ("average_power_W", "group_power_median_W", "clock_sm_mhz"):
            value = parse_float(row.get(column, ""))
            if value is None or value <= 0.0:
                problems.append(f"{path}:{idx}:{column}={row.get(column, '')}")
        temp_c = parse_float(row.get("temp_C", ""))
        if temp_c is None:
            problems.append(f"{path}:{idx}:temp_C={row.get('temp_C', '')}")
    if not csv_rows:
        problems.append("empty_power_state_audit")
    add(
        rows,
        area="power",
        check="power_state_audit_policy",
        status="pass" if not problems else "fail",
        expected=(
            "no reject or coefficient-ineligible rows, plus power-state evidence "
            "columns for average power, run coordinates, temperature, and SM clock"
        ),
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action="exclude rejected rows before pairing or rerun unstable conditions",
    )


def audit_ncu_acceptance(
    repo: Path, rows: list[dict[str, str]], path: Path, *, profile: str
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    with full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        csv_rows = list(reader)
    accepted = {
        row.get("component_candidate", "")
        for row in csv_rows
        if row.get("acceptance") == "accepted"
    }
    missing = sorted(REQUIRED_NCU_CANDIDATES - accepted)
    rejected = [
        f"{row.get('mode')}:{row.get('component_candidate')}"
        for row in csv_rows
        if row.get("acceptance") == "rejected"
        and row.get("component_candidate") != "not_selected"
    ]
    problems = []
    missing_columns = sorted(NCU_ACCEPTANCE_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns))
    if missing:
        problems.append("missing=" + ",".join(missing))
    if rejected:
        problems.append("rejected=" + ";".join(rejected[:8]))
    for row in csv_rows:
        if row.get("acceptance") != "accepted":
            continue
        candidate = row.get("component_candidate", "")
        if candidate not in REQUIRED_NCU_CANDIDATES:
            continue
        if row.get("acceptance_reason") != "pass":
            problems.append(
                f"{row.get('mode')}:{candidate}:reason={row.get('acceptance_reason')}"
            )
        if not ncu_path_sanity_pass(row, profile=profile):
            problems.append(f"{row.get('mode')}:{candidate}:path_evidence_failed")
    if not csv_rows:
        problems.append("empty_ncu_acceptance")
    add(
        rows,
        area="ncu",
        check="ncu_path_acceptance",
        status="pass" if not problems else "fail",
        expected="accepted tensor/control/shared/global-L1/L2 path candidates",
        actual=f"accepted={len(accepted)}" if not problems else ";".join(problems),
        evidence=str(path),
        action="rerun NCU sidecar with matching W_SM, blocks/SM, active SM, and factors",
    )


def parse_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def ncu_value(row: dict[str, str], column: str, default: float = 0.0) -> float:
    value = parse_float(row.get(column, ""))
    return default if value is None else value


def ncu_ratio(num: float, den: float) -> float:
    return num / den if den > 0.0 else math.inf


def ncu_expected_ops(row: dict[str, str]) -> float:
    active_sm = ncu_value(row, "active_SM")
    blocks = ncu_value(row, "blocks_per_SM")
    iters = ncu_value(row, "ITER")
    reuse = ncu_value(row, "reuse_factor", 1.0)
    return active_sm * blocks * iters * reuse


def ncu_expected_input_bytes(row: dict[str, str]) -> float:
    return (
        ncu_value(row, "active_SM")
        * ncu_value(row, "blocks_per_SM")
        * ncu_value(row, "ITER")
        * ncu_value(row, "load_repeat", 1.0)
        * 1024.0
    )


def ncu_expected_l2_residency_hit_pct(row: dict[str, str], profile: str) -> float:
    metadata = PROFILE_METADATA.get(profile, {})
    l2_mib = float(metadata.get("l2_mib", 0.0))
    working_set_mib = (
        ncu_value(row, "active_SM") * ncu_value(row, "W_SM_KiB") / 1024.0
    )
    if l2_mib <= 0.0 or working_set_mib <= 0.0:
        return 0.0
    return min(100.0, 100.0 * l2_mib / working_set_mib)


def ncu_path_sanity_pass(row: dict[str, str], *, profile: str) -> bool:
    mode = row.get("mode", "")
    if row.get("status") != "ok" or row.get("missing_metrics", "").strip():
        return False

    l1_hit = ncu_value(row, "l1_path_hit_rate_pct", -1.0)
    l2_hit = ncu_value(row, "l2_path_hit_rate_pct", -1.0)
    l1_bytes = ncu_value(row, "l1_bytes")
    l1_request_bytes = ncu_value(row, "l1_request_bytes")
    l1_hit_bytes = ncu_value(row, "l1_hit_bytes")
    l2_bytes = ncu_value(row, "l2_bytes")
    l2_read_bytes = ncu_value(row, "l2_read_bytes")
    dram_bytes = ncu_value(row, "dram_bytes")
    shared_bytes = ncu_value(row, "shared_bytes")
    shared_accesses = ncu_value(row, "shared_accesses")
    shared_inst = ncu_value(row, "shared_inst")
    tensor_hmma = ncu_value(row, "tensor_hmma_inst")
    local_read_bytes = ncu_value(row, "local_read_bytes")
    local_write_bytes = ncu_value(row, "local_write_bytes")
    spill_zero_verified = ncu_value(row, "spill_zero_verified", -1.0)

    if (
        local_read_bytes > 0.0
        or local_write_bytes > 0.0
        or spill_zero_verified != 1.0
    ):
        return False

    if mode == "global_l1_load_only":
        return (
            l1_hit >= NCU_L1_HIT_MIN_PCT
            and l1_request_bytes > 0.0
            and l1_hit_bytes > 0.0
            and ncu_ratio(l2_read_bytes, l1_request_bytes) <= NCU_L1_L2_RATIO_MAX
            and ncu_ratio(dram_bytes, l1_request_bytes) <= NCU_L1_DRAM_RATIO_MAX
        )
    if mode == "global_addr_only":
        return (
            l1_request_bytes == 0.0
            and ncu_ratio(dram_bytes, ncu_expected_input_bytes(row))
            <= NCU_GLOBAL_ADDRESS_CONTROL_DRAM_RATIO_MAX
        )
    if mode == "l2_cg_load_only":
        return (
            l2_hit >= NCU_L2_HIT_MIN_PCT
            and l2_read_bytes > 0.0
            and l1_request_bytes > 0.0
            and l1_hit >= 0.0
            and l1_hit <= NCU_L2_L1_HIT_MAX_PCT
            and ncu_ratio(l1_hit_bytes, l1_request_bytes)
            <= NCU_L2_L1_BYTES_RATIO_MAX
            and ncu_ratio(dram_bytes, l2_read_bytes) <= NCU_L2_DRAM_RATIO_MAX
        )
    if mode in {"shared_scalar_load_only", "shared_load_only"}:
        denominator = max(shared_bytes, 1.0)
        return (
            shared_accesses > 0.0
            and shared_bytes > 0.0
            and shared_inst > 0.0
            and ncu_ratio(l1_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
            and ncu_ratio(l2_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
            and ncu_ratio(dram_bytes, denominator) <= NCU_SHARED_GLOBAL_RATIO_MAX
        )
    if mode == "dram_cg_load_only":
        l2_limit = max(
            NCU_DRAM_L2_HIT_MAX_PCT,
            ncu_expected_l2_residency_hit_pct(row, profile)
            * NCU_DRAM_L2_EXPECTED_MULTIPLIER
            + NCU_DRAM_L2_EXPECTED_SLACK_PCT,
        )
        return (
            l1_hit <= NCU_DRAM_L1_HIT_MAX_PCT
            and l2_hit <= l2_limit
            and dram_bytes > 0.0
            and ncu_ratio(dram_bytes, l2_bytes) >= NCU_DRAM_L2_RATIO_MIN
        )
    if mode == "reg_mma":
        if tensor_hmma <= 0.0:
            return False
        return (
            ncu_ratio(l2_read_bytes, tensor_hmma)
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
            ncu_ratio(l2_read_bytes, expected_ops)
            <= NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX
            and ncu_ratio(dram_bytes, expected_ops)
            <= NCU_REGISTER_MEMORY_BYTES_PER_OP_MAX
        )
    if mode == "clocked_empty":
        return True
    return False


def audit_ncu_summary_quality(
    repo: Path,
    rows: list[dict[str, str]],
    path: Path,
    *,
    profile: str,
    expected_active_sm: int | None,
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    with full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        csv_rows = list(reader)

    problems: list[str] = []
    missing_columns = sorted(NCU_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns))

    required_modes = NCU_REQUIRED_MODES | PROFILE_EXTRA_NCU_REQUIRED_MODES.get(
        profile, set()
    )
    modes_present = {row.get("mode", "") for row in csv_rows}
    missing_modes = sorted(required_modes - modes_present)
    if missing_modes:
        problems.append("missing_modes=" + ",".join(missing_modes))

    reuse_by_mode: dict[str, set[str]] = {}
    load_by_mode: dict[str, set[str]] = {}
    for row in csv_rows:
        mode = row.get("mode", "")
        if row.get("reuse_factor", "").strip():
            reuse_by_mode.setdefault(mode, set()).add(row["reuse_factor"].strip())
        if row.get("load_repeat", "").strip():
            load_by_mode.setdefault(mode, set()).add(row["load_repeat"].strip())
    for mode in sorted(NCU_REUSE_SWEEP_MODES & modes_present):
        count = len(reuse_by_mode.get(mode, set()))
        if count < NCU_MIN_FACTOR_POINTS:
            problems.append(f"{mode}:reuse_factor_points={count}")
    for mode in sorted(NCU_LOAD_REPEAT_SWEEP_MODES & modes_present):
        count = len(load_by_mode.get(mode, set()))
        if count < NCU_MIN_FACTOR_POINTS:
            problems.append(f"{mode}:load_repeat_points={count}")

    path_sanity_modes = {
        "reg_operand_only",
        "reg_mma",
        "shared_scalar_load_only",
        "global_addr_only",
        "global_l1_load_only",
        "l2_cg_load_only",
        "dram_cg_load_only",
    } | PROFILE_EXTRA_NCU_REQUIRED_MODES.get(profile, set())
    for mode in sorted(path_sanity_modes & modes_present):
        if not any(
            ncu_path_sanity_pass(row, profile=profile)
            for row in csv_rows
            if row.get("mode") == mode
        ):
            problems.append(f"{mode}:no_path_sanity_pass")

    for idx, row in enumerate(csv_rows, start=2):
        prefix = f"{path}:{idx}:{row.get('mode', '') or row.get('label', '')}"
        if row.get("status") != "ok":
            problems.append(f"{prefix}:status={row.get('status')}")
        if row.get("missing_metrics", "").strip():
            problems.append(f"{prefix}:missing_metrics={row.get('missing_metrics')}")
        for column in ("W_SM_KiB", "blocks_per_SM", "active_SM", "ITER"):
            value = parse_float(row.get(column, ""))
            if value is None or value <= 0.0:
                problems.append(f"{prefix}:{column}={row.get(column, '')}")
        if expected_active_sm is not None:
            active_sm = parse_int(row.get("active_SM", ""))
            if active_sm != expected_active_sm:
                problems.append(f"{prefix}:active_SM={row.get('active_SM', '')}")
        for column in NCU_COMMON_NUMERIC_COLUMNS:
            value = parse_float(row.get(column, ""))
            if value is None or value < 0.0:
                problems.append(f"{prefix}:{column}={row.get(column, '')}")
        for column in ("l1_access_unit", "l2_access_unit", "dram_access_unit"):
            if not row.get(column, "").strip():
                problems.append(f"{prefix}:{column}=blank")
        for column in NCU_POSITIVE_BY_MODE.get(row.get("mode", ""), ()):
            value = parse_float(row.get(column, ""))
            if value is None or value <= 0.0:
                problems.append(f"{prefix}:{column}={row.get(column, '')}")

    if not csv_rows:
        problems.append("empty_ncu_summary")
    add(
        rows,
        area="ncu",
        check="ncu_cache_counter_schema",
        status="pass" if not problems else "fail",
        expected=(
            "NCU summary exposes L1/L2 hit rates, L1/L2/DRAM access counts, "
            "bytes, stall counters, run coordinates, required finalplan modes, "
            "and profile-specific mode coverage, factor sweeps, and mode-specific "
            "positive path counters plus at least one mode-level path-sanity "
            "row matching the final NCU acceptance thresholds"
        ),
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action=(
            "rerun scripts/run_ncu_validation.sh and "
            "scripts/summarize_ncu_cache_metrics.py with explicit cache/access metrics"
        ),
    )


def audit_matched_control(
    repo: Path, rows: list[dict[str, str]], path: Path, *, expected_semantics: str
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    csv_rows = read_csv(full)
    problems: list[str] = []
    valid_pair_orders: dict[str, set[str]] = {}
    seen_components: set[str] = set()
    for idx, row in enumerate(csv_rows, start=2):
        valid = row.get("valid_component_estimate", row.get("valid_for_summary", "")).lower()
        component = row.get("component", "")
        seen_components.add(component)
        pair_execution_order = row.get("pair_execution_order", "")
        if valid == "true":
            if pair_execution_order not in {
                "control_then_treatment",
                "treatment_then_control",
            }:
                problems.append(
                    f"{path}:{idx}:valid_pair_execution_order={pair_execution_order}"
                )
            else:
                valid_pair_orders.setdefault(component, set()).add(
                    pair_execution_order
                )
        pair_transition_gap_ms = parse_float(row.get("pair_transition_gap_ms", ""))
        pair_transition_gap_limit_ms = parse_float(
            row.get("pair_transition_gap_limit_ms", "")
        )
        if pair_transition_gap_ms is None or pair_transition_gap_ms < 0.0:
            problems.append(
                f"{path}:{idx}:pair_transition_gap_ms="
                f"{row.get('pair_transition_gap_ms', '')}"
            )
        if (
            pair_transition_gap_limit_ms is None
            or pair_transition_gap_limit_ms <= 0.0
        ):
            problems.append(
                f"{path}:{idx}:pair_transition_gap_limit_ms="
                f"{row.get('pair_transition_gap_limit_ms', '')}"
            )
        elif (
            valid == "true"
            and pair_transition_gap_ms is not None
            and pair_transition_gap_ms > pair_transition_gap_limit_ms
        ):
            problems.append(
                f"{path}:{idx}:valid_pair_transition_gap_ms="
                f"{pair_transition_gap_ms:g}>{pair_transition_gap_limit_ms:g}"
            )
        if not row.get("pair_timing_source", "").strip():
            problems.append(f"{path}:{idx}:pair_timing_source=blank")
        elif valid == "true" and row.get("pair_timing_source") != "exact_epoch_interval":
            problems.append(
                f"{path}:{idx}:valid_pair_timing_source="
                f"{row.get('pair_timing_source', '')}"
            )
        if component in CONTROL_NCU_REQUIRED_COMPONENTS:
            if not truthy(row.get("ncu_control_acceptance_required", "")):
                problems.append(
                    f"{path}:{idx}:ncu_control_acceptance_required="
                    f"{row.get('ncu_control_acceptance_required', '')}"
                )
            if not truthy(row.get("ncu_control_acceptance_exact", "")):
                problems.append(
                    f"{path}:{idx}:ncu_control_acceptance_exact="
                    f"{row.get('ncu_control_acceptance_exact', '')}"
                )
        if component != "tensor_mma_increment":
            if row.get("denominator_source") != "ncu_actual_exact":
                problems.append(f"{path}:{idx}:denominator={row.get('denominator_source')}")
        if component in {
            "tensor_mma_increment",
            "l2_hit_cg_path",
            "dram_cg_stream_path",
        }:
            component_label = {
                "tensor_mma_increment": "tensor",
                "l2_hit_cg_path": "l2",
                "dram_cg_stream_path": "dram",
            }[component]
            if row.get("pair_energy_basis", "") != "matched_iters_net_energy":
                problems.append(
                    f"{path}:{idx}:pair_energy_basis={row.get('pair_energy_basis', '')}"
                )
            numerator_iters = parse_float(row.get("numerator_ITER", ""))
            control_iters = parse_float(row.get("control_ITER", ""))
            iter_ratio = parse_float(row.get("iter_ratio", ""))
            if (
                numerator_iters is None
                or control_iters is None
                or numerator_iters <= 0.0
                or control_iters <= 0.0
                or int(numerator_iters) != int(control_iters)
            ):
                problems.append(
                    f"{path}:{idx}:{component_label}_iters="
                    f"{row.get('numerator_ITER', '')}/{row.get('control_ITER', '')}"
                )
            if iter_ratio is None or not math.isclose(iter_ratio, 1.0, rel_tol=1.0e-9):
                problems.append(f"{path}:{idx}:iter_ratio={row.get('iter_ratio', '')}")
            numerator_elapsed = parse_float(row.get("numerator_elapsed_s", ""))
            control_elapsed = parse_float(row.get("control_elapsed_s", ""))
            numerator_net = parse_float(row.get("numerator_net_E_J", ""))
            control_net = parse_float(row.get("control_net_E_J", ""))
            if numerator_elapsed is None or numerator_elapsed <= 0.0:
                problems.append(
                    f"{path}:{idx}:numerator_elapsed_s={row.get('numerator_elapsed_s', '')}"
                )
            if (
                control_elapsed is None
                or control_elapsed
                < (
                    TENSOR_CONTROL_MIN_ELAPSED_S
                    if component == "tensor_mma_increment"
                    else L2_CONTROL_MIN_ELAPSED_S
                    if component == "l2_hit_cg_path"
                    else DRAM_CONTROL_MIN_ELAPSED_S
                )
            ):
                problems.append(
                    f"{path}:{idx}:control_elapsed_s={row.get('control_elapsed_s', '')}"
                )
            if numerator_net is None or numerator_net <= 0.0:
                problems.append(
                    f"{path}:{idx}:numerator_net_E_J={row.get('numerator_net_E_J', '')}"
                )
            if control_net is None or control_net <= 0.0:
                problems.append(
                    f"{path}:{idx}:control_net_E_J={row.get('control_net_E_J', '')}"
                )
        delta_j = parse_float(row.get("delta_E_J", ""))
        if valid == "true" and (delta_j is None or delta_j <= 0.0):
            problems.append(f"{path}:{idx}:non_positive_valid_delta")
        expected_pairs = {
            "numerator_energy_source": "nvml_total_energy",
            "control_energy_source": "nvml_total_energy",
            "numerator_energy_integration_method": "total_energy_mj_delta",
            "control_energy_integration_method": "total_energy_mj_delta",
            "numerator_measurement_scope": "gpu_device_total_energy_counter",
            "control_measurement_scope": "gpu_device_total_energy_counter",
            "numerator_power_semantics": expected_semantics,
            "control_power_semantics": expected_semantics,
        }
        for column, expected in expected_pairs.items():
            if row.get(column, "") != expected:
                problems.append(f"{path}:{idx}:{column}={row.get(column, '')}")
    required_orders = {"control_then_treatment", "treatment_then_control"}
    for component in sorted(EXPECTED_RELIABILITY_COMPONENTS & seen_components):
        observed_orders = valid_pair_orders.get(component, set())
        if observed_orders != required_orders:
            problems.append(
                f"{component}:valid_pair_orders="
                f"{','.join(sorted(observed_orders)) or 'none'}"
            )
    if not csv_rows:
        problems.append("empty_matched_detail")
    add(
        rows,
        area="analysis",
        check="matched_control_detail_policy",
        status="pass" if not problems else "fail",
        expected=(
            "Tensor, L2, and DRAM rows use matched_iters_net_energy with identical "
            "positive ITER; Tensor/global-memory controls have exact-coordinate "
            "NCU acceptance; memory paths use exact NCU denominators; valid "
            "deltas are positive; pair adjacency uses benchmark transition gap; "
            "strict components retain valid rows in both execution orders"
        ),
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action=(
            "rerun Tensor sweeps with --tensor-pair-lock-iters and L2/DRAM sweeps "
            "with --memory-pair-lock-iters; analyze with matched-iters pair policies and "
            "--require-control-ncu-acceptance; retain exact NCU denominators, "
            "total-energy scope, expected power semantics, and the current pair "
            "timing fields and alternating pair execution orders"
        ),
    )


def audit_matched_summary(
    repo: Path, rows: list[dict[str, str]], path: Path, *, expected_semantics: str
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    with full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        csv_rows = list(reader)

    problems: list[str] = []
    missing_columns = sorted(MATCHED_SUMMARY_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns))

    by_component = {row.get("component", ""): row for row in csv_rows}
    for component, expected_unit in EXPECTED_MATCHED_SUMMARY_COMPONENTS.items():
        row = by_component.get(component)
        if row is None:
            problems.append(f"{component}:missing")
            continue
        if row.get("unit") != expected_unit:
            problems.append(f"{component}:unit={row.get('unit')}")
        row_count = parse_int(row.get("rows", ""))
        if row_count is None or row_count <= 0:
            problems.append(f"{component}:rows={row.get('rows', '')}")
        median = parse_float(row.get("median", ""))
        if median is None or median <= 0.0:
            problems.append(f"{component}:median={row.get('median', '')}")
        if row.get("energy_source") != "nvml_total_energy":
            problems.append(f"{component}:energy_source={row.get('energy_source')}")
        if row.get("energy_integration_method") != "total_energy_mj_delta":
            problems.append(f"{component}:integration={row.get('energy_integration_method')}")
        if row.get("measurement_scope") != "gpu_device_total_energy_counter":
            problems.append(f"{component}:scope={row.get('measurement_scope')}")
        if row.get("power_semantics") != expected_semantics:
            problems.append(f"{component}:semantics={row.get('power_semantics')}")
        if not row.get("confidence_class", "").strip():
            problems.append(f"{component}:confidence_class=blank")
        if component in MATCHED_MEMORY_COMPONENTS:
            ncu_rows = parse_int(row.get("ncu_denominator_rows", ""))
            if ncu_rows is None or ncu_rows <= 0:
                problems.append(
                    f"{component}:ncu_denominator_rows={row.get('ncu_denominator_rows', '')}"
                )
            pbit = parse_float(row.get("median_pJ_per_bit", ""))
            if pbit is None or pbit <= 0.0:
                problems.append(
                    f"{component}:median_pJ_per_bit={row.get('median_pJ_per_bit', '')}"
                )

    if not csv_rows:
        problems.append("empty_matched_summary")
    add(
        rows,
        area="analysis",
        check="matched_control_summary_policy",
        status="pass" if not problems else "fail",
        expected=(
            "Tensor, Shared, Global L1, and L2 matched-control summary rows "
            "with positive median, total-energy GPU/device scope, matching power "
            "semantics, and NCU denominator rows for memory components"
        ),
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action=(
            "rerun matched-control summary generation after power, NCU, and "
            "matched-control detail gates pass"
        ),
    )


def audit_reliability(
    repo: Path, rows: list[dict[str, str]], path: Path, *, expected_semantics: str
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    with full.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        csv_rows = list(reader)
    accepted_components = {
        row.get("component", "")
        for row in csv_rows
        if row.get("status") == "accepted"
    }
    rejected = [row.get("component", "") for row in csv_rows if row.get("status") == "reject"]
    missing = sorted(EXPECTED_RELIABILITY_COMPONENTS - accepted_components)
    problems: list[str] = []
    missing_columns = sorted(RELIABILITY_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns))
    if missing:
        problems.append("missing_accepted=" + ",".join(missing))
    if rejected:
        problems.append("rejected=" + ",".join(rejected))
    by_component = {row.get("component", ""): row for row in csv_rows}
    for component, expected_unit in EXPECTED_RELIABILITY_UNITS.items():
        row = by_component.get(component)
        if row is None:
            continue
        if row.get("status") != "accepted":
            problems.append(f"{component}:status={row.get('status')}")
        if row.get("unit") != expected_unit:
            problems.append(f"{component}:unit={row.get('unit')}")
        median = parse_float(row.get("median", ""))
        if median is None or median <= 0.0:
            problems.append(f"{component}:median={row.get('median', '')}")
        row_count = parse_int(row.get("rows", ""))
        valid_rows = parse_int(row.get("valid_detail_rows", ""))
        invalid_rows = parse_int(row.get("invalid_detail_rows", ""))
        if row_count is None or row_count <= 0:
            problems.append(f"{component}:rows={row.get('rows', '')}")
        if valid_rows is None or valid_rows <= 0:
            problems.append(f"{component}:valid_detail_rows={row.get('valid_detail_rows', '')}")
        if invalid_rows is None or invalid_rows != 0:
            problems.append(f"{component}:invalid_detail_rows={row.get('invalid_detail_rows', '')}")
        if component in MATCHED_MEMORY_COMPONENTS:
            ncu_rows = parse_int(row.get("ncu_denominator_rows", ""))
            if ncu_rows is None or ncu_rows <= 0:
                problems.append(
                    f"{component}:ncu_denominator_rows={row.get('ncu_denominator_rows', '')}"
                )
        ncu_accepted = parse_int(row.get("ncu_accepted_rows", ""))
        if ncu_accepted is None or ncu_accepted <= 0:
            problems.append(f"{component}:ncu_accepted_rows={row.get('ncu_accepted_rows', '')}")
        if not row.get("confidence_class", "").strip():
            problems.append(f"{component}:confidence_class=blank")
        if row.get("energy_source") != "nvml_total_energy":
            problems.append(f"{component}:energy_source={row.get('energy_source')}")
        if row.get("energy_integration_method") != "total_energy_mj_delta":
            problems.append(f"{component}:integration={row.get('energy_integration_method')}")
        if row.get("measurement_scope") != "gpu_device_total_energy_counter":
            problems.append(f"{component}:scope={row.get('measurement_scope')}")
        if row.get("power_semantics") != expected_semantics:
            problems.append(f"{component}:semantics={row.get('power_semantics')}")
        if row.get("reasons", "").strip():
            problems.append(f"{component}:reasons={row.get('reasons')}")
        if row.get("cautions", "").strip():
            problems.append(f"{component}:cautions={row.get('cautions')}")
    if not csv_rows:
        problems.append("empty_reliability")
    add(
        rows,
        area="analysis",
        check="component_reliability",
        status="pass" if not problems else "fail",
        expected="Tensor, Shared, Global L1, and L2 accepted with no rejects",
        actual=f"accepted={len(accepted_components)}" if not problems else ";".join(problems),
        evidence=str(path),
        action="rerun targeted conditions or keep weak components out of the strict summary",
    )


def audit_strict_summary(
    repo: Path,
    rows: list[dict[str, str]],
    path: Path,
    *,
    expected_semantics: str,
) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    csv_rows = read_csv(full)
    by_component = {row.get("component", ""): row for row in csv_rows}
    problems: list[str] = []
    fieldnames = set(csv_rows[0].keys()) if csv_rows else set()
    missing_evidence_columns = sorted(STRICT_SUMMARY_NCU_EVIDENCE_COLUMNS - fieldnames)
    if missing_evidence_columns:
        problems.append("missing_evidence_columns=" + ",".join(missing_evidence_columns[:8]))
    unexpected_components = sorted(set(by_component) - set(EXPECTED_COMPONENTS))
    if unexpected_components:
        problems.append("unexpected_components=" + ",".join(unexpected_components))
    for component, unit in EXPECTED_COMPONENTS.items():
        row = by_component.get(component)
        if not row:
            problems.append(f"{component}:missing")
            continue
        if row.get("unit") != unit:
            problems.append(f"{component}:unit={row.get('unit')}")
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
        try:
            median = float(row.get("median", "nan"))
        except ValueError:
            median = float("nan")
        if not median > 0.0:
            problems.append(f"{component}:median={row.get('median')}")
        lo, hi, range_unit = HARD_PLAUSIBILITY_RANGES[component]
        if row.get("unit") == range_unit and not (lo <= median <= hi):
            problems.append(f"{component}:plausibility={median:g}{range_unit}")
        if not missing_evidence_columns:
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
            missing_modes = sorted(
                STRICT_SUMMARY_EVIDENCE_MODES.get(component, set()) - evidence_modes
            )
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
                problems.append(f"{component}:missing_metric_modes={','.join(missing_metric_modes)}")
            for evidence_column in ("ncu_evidence_coords", "ncu_path_evidence", "ncu_counter_caveat"):
                if not row.get(evidence_column, "").strip():
                    problems.append(f"{component}:{evidence_column}=blank")
            for evidence_column in STRICT_SUMMARY_REQUIRED_METRICS.get(component, set()):
                if not row.get(evidence_column, "").strip():
                    problems.append(f"{component}:{evidence_column}=blank")
            if unit == "pJ/bit":
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
    add(
        rows,
        area="summary",
        check="strict_summary_policy",
        status="pass" if not problems else "fail",
        expected=(
            "all reported components accepted, positive, total-energy scoped, "
            "hierarchy-consistent, within broad plausibility ranges, exposing "
            "same-coordinate NCU evidence, and limited to Tensor/Shared/L1/L2 "
            "strict components"
        ),
        actual=f"rows={len(csv_rows)}" if not problems else ";".join(problems[:12]),
        evidence=str(path),
        action="rebuild strict summary from accepted evidence only",
    )


def audit_strict_audit(repo: Path, rows: list[dict[str, str]], path: Path) -> None:
    full = rel(repo, path)
    if not full.exists():
        return
    csv_rows = read_csv(full)
    failures = [row for row in csv_rows if row.get("status") == "fail"]
    warnings = [row for row in csv_rows if row.get("status") == "warning"]
    seen_checks = {row.get("check", "") for row in csv_rows}
    missing_required_checks = sorted(STRICT_AUDIT_REQUIRED_CHECKS - seen_checks)
    add(
        rows,
        area="summary",
        check="strict_summary_audit_clean",
        status="pass" if not failures and not warnings and not missing_required_checks else "fail",
        expected="0 fail/warning rows and required hierarchy/plausibility checks present",
        actual=(
            f"rows={len(csv_rows)}, failures={len(failures)}, warnings={len(warnings)}"
            if not missing_required_checks
            else (
                f"rows={len(csv_rows)}, failures={len(failures)}, warnings={len(warnings)}, "
                "missing_checks=" + ",".join(missing_required_checks)
            )
        ),
        evidence=str(path),
        action="fix strict summary audit failures before publication",
    )


def audit_package(
    repo: Path,
    profile: str,
    tag: str,
    *,
    expected_active_sm: int | None,
    expected_sm_count: int | None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    semantics = PROFILE_POWER_SEMANTICS[profile]
    paths = expected_paths(profile, tag)
    audit_file_presence(repo, rows, paths)
    if "l2_path_selection" in paths:
        audit_l2_path_selection(
            repo,
            rows,
            paths["l2_path_selection"],  # type: ignore[arg-type]
            profile=profile,
        )
    audit_preflight(
        repo,
        rows,
        paths["preflight"],  # type: ignore[arg-type]
        profile=profile,
        expected_semantics=semantics,
        expected_active_sm=expected_active_sm,
    )
    audit_raw_energy(
        repo,
        rows,
        paths["raw"],
        profile=profile,
        expected_semantics=semantics,
        expected_active_sm=expected_active_sm,
        expected_sm_count=expected_sm_count,
    )  # type: ignore[arg-type]
    raw_paths = paths["raw"]
    if isinstance(raw_paths, list) and raw_paths:
        audit_tensor_pair_calibration(
            repo,
            rows,
            paths["tensor_pair_calibration"],  # type: ignore[arg-type]
            raw_paths[0],
            profile=profile,
        )
        audit_memory_pair_calibration(
            repo,
            rows,
            paths["l2_pair_calibration"],  # type: ignore[arg-type]
            raw_paths[3],
            profile=profile,
            treatment_mode="l2_cg_load_only",
            pair_label="l2",
        )
        audit_dram_pair_calibration(
            repo,
            rows,
            paths["dram_pair_calibration"],  # type: ignore[arg-type]
            raw_paths[-1],
            profile=profile,
        )
    audit_power_api(repo, rows, paths["power_api"], expected_semantics=semantics)  # type: ignore[arg-type]
    audit_power_state(repo, rows, paths["power_state"])  # type: ignore[arg-type]
    audit_ncu_summary_quality(
        repo,
        rows,
        paths["ncu_summary"],  # type: ignore[arg-type]
        profile=profile,
        expected_active_sm=expected_active_sm,
    )
    audit_ncu_acceptance(
        repo, rows, paths["ncu_acceptance"], profile=profile
    )  # type: ignore[arg-type]
    audit_matched_summary(
        repo, rows, paths["matched_summary"], expected_semantics=semantics  # type: ignore[arg-type]
    )
    audit_matched_control(
        repo, rows, paths["matched_detail"], expected_semantics=semantics  # type: ignore[arg-type]
    )
    audit_reliability(
        repo, rows, paths["reliability"], expected_semantics=semantics  # type: ignore[arg-type]
    )
    audit_strict_summary(repo, rows, paths["strict_summary"], expected_semantics=semantics)  # type: ignore[arg-type]
    audit_strict_audit(repo, rows, paths["strict_audit"])  # type: ignore[arg-type]
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["area", "check", "status", "expected", "actual", "evidence", "action"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(
    path: Path,
    rows: list[dict[str, str]],
    *,
    profile: str,
    tag: str,
    expected_active_sm: int | None,
    expected_sm_count: int | None,
) -> None:
    counts = status_counts(rows)
    incomplete = counts.get("fail", 0) + counts.get("missing", 0)
    metadata = PROFILE_METADATA[profile]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {profile.upper()} Platform Result Package Audit\n\n")
        f.write(f"| item | value |\n|---|---|\n")
        f.write(f"| target profile | `{profile}` |\n")
        f.write(f"| tag | `{tag}` |\n")
        f.write(f"| expected chip | `{metadata['chip']}` |\n")
        f.write(f"| expected compute capability | `{metadata['compute_capability']}` |\n")
        f.write(f"| expected L2 | `{metadata['l2_mib']} MiB` |\n")
        f.write(
            "| expected unified L1/shared per SM | "
            f"`{metadata['unified_l1_shared_kib_per_sm']} KiB` |\n"
        )
        f.write(
            f"| expected shared per SM | `{metadata['shared_kib_per_sm']} KiB` |\n"
        )
        f.write(
            "| expected active SM | "
            f"`{expected_active_sm if expected_active_sm is not None else 'not checked'}` |\n"
        )
        f.write(
            "| expected runtime SM count | "
            f"`{expected_sm_count if expected_sm_count is not None else 'not exact-checked'}` |\n"
        )
        f.write(f"| expected power semantics | `{PROFILE_POWER_SEMANTICS[profile]}` |\n")
        f.write(
            "| final numerator policy | `nvml_total_energy` + "
            "`total_energy_mj_delta` + `gpu_device_total_energy_counter` |\n\n"
        )
        f.write("## Verdict\n\n")
        if incomplete:
            f.write(
                "This package is not yet publishable as final component evidence. "
                "Fix missing/fail rows below, then rerun this audit and the goal readiness audit.\n\n"
            )
        else:
            f.write(
                "This package passes the intake checks. It is eligible for the broader "
                "goal readiness audit and report review.\n\n"
            )
        f.write("## Status Counts\n\n")
        f.write("| status | checks |\n|---|---:|\n")
        for status in sorted(counts):
            f.write(f"| `{status}` | {counts[status]} |\n")
        f.write("\n## Checks\n\n")
        f.write("| area | check | status | expected | actual | evidence | action |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['area']}` | `{row['check']}` | `{row['status']}` | "
                f"{row['expected']} | {row['actual']} | `{row['evidence']}` | "
                f"{row['action']} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--target-profile", choices=sorted(PROFILE_POWER_SEMANTICS), required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--expected-active-sm",
        type=int,
        default=0,
        help=(
            "Expected active_SM in raw rows. Defaults to the full profile SM count; "
            "pass the runtime/preflight value for MIG or SKU-specific plans."
        ),
    )
    parser.add_argument(
        "--expected-sm-count",
        type=int,
        default=0,
        help=(
            "Optional exact runtime sm_count check. If omitted, the audit only "
            "requires sm_count >= expected active SM."
        ),
    )
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--fail-on-incomplete", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo)
    expected_active_sm = args.expected_active_sm or int(
        PROFILE_METADATA[args.target_profile]["full_sm"]
    )
    expected_sm_count = args.expected_sm_count or None
    rows = audit_package(
        repo,
        args.target_profile,
        args.tag,
        expected_active_sm=expected_active_sm,
        expected_sm_count=expected_sm_count,
    )
    out_csv = Path(
        args.out_csv
        or f"results/summary/{args.target_profile}_platform_result_package_audit_{args.tag}.csv"
    )
    out_md = Path(
        args.out_md
        or f"results/summary/{args.target_profile}_platform_result_package_audit_{args.tag}.md"
    )
    write_csv(repo / out_csv, rows)
    write_md(
        repo / out_md,
        rows,
        profile=args.target_profile,
        tag=args.tag,
        expected_active_sm=expected_active_sm,
        expected_sm_count=expected_sm_count,
    )

    counts = status_counts(rows)
    print(
        f"{args.target_profile} package checks={len(rows)} "
        f"failures={counts.get('fail', 0)} missing={counts.get('missing', 0)} "
        f"warnings={counts.get('warning', 0)}"
    )
    print(f"wrote {out_csv}")
    print(f"wrote {out_md}")
    if args.fail_on_incomplete and (counts.get("fail", 0) or counts.get("missing", 0)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
