#!/usr/bin/env python3
"""Self-test platform package gate failure modes.

This test does not run CUDA or Nsight Compute. It builds tiny mock result
packages and verifies that the intake audit catches stale strict-summary audits,
memory hierarchy inversions, out-of-range effective coefficients, and power
measurement matrix violations.
"""

from __future__ import annotations

import csv
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_PATH = SCRIPT_DIR / "audit_platform_result_package.py"

STRICT_SUMMARY_COLUMNS = [
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
    "ncu_local_read_bytes_min_med_max",
    "ncu_local_write_bytes_min_med_max",
    "ncu_spill_zero_verified_min_med_max",
    "ncu_stall_long_scoreboard_pct_min_med_max",
]

STRICT_AUDIT_COLUMNS = [
    "component",
    "check",
    "status",
    "expected",
    "actual",
    "interpretation",
]

RAW_COLUMNS = [
    "mode",
    "profile_name",
    "architecture_family",
    "chip",
    "compute_capability",
    "l2_mib",
    "unified_l1_shared_kib_per_sm",
    "shared_kib_per_sm",
    "active_SM",
    "sm_count",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "nvml_total_energy_supported",
    "nvml_power_usage_semantics",
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
]

POWER_API_COLUMNS = [
    "status",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "actual_power_semantics",
]

POWER_STATE_COLUMNS = [
    "input_file",
    "row_index",
    "run_id",
    "mode",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "store_repeat",
    "elapsed_s",
    "net_E_J",
    "average_power_W",
    "group_rows",
    "group_power_median_W",
    "group_power_mad_W",
    "average_power_delta_W",
    "endpoint_after_W",
    "group_endpoint_after_median_W",
    "endpoint_after_ratio",
    "temp_C",
    "group_temp_median_C",
    "clock_sm_mhz",
    "group_clock_sm_median_mhz",
    "status",
    "coefficient_eligible",
    "reasons",
    "notes",
]

MATCHED_SUMMARY_COLUMNS = [
    "component",
    "rows",
    "ncu_denominator_rows",
    "expected_denominator_rows",
    "unit",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "power_semantics",
    "median",
    "confidence_class",
    "median_pJ_per_bit",
]

MATCHED_DETAIL_COLUMNS = [
    "component",
    "valid_component_estimate",
    "pair_energy_basis",
    "ncu_control_acceptance_required",
    "ncu_control_acceptance_exact",
    "pair_transition_gap_ms",
    "pair_transition_gap_limit_ms",
    "pair_timing_source",
    "pair_execution_order",
    "numerator_ITER",
    "control_ITER",
    "iter_ratio",
    "numerator_elapsed_s",
    "control_elapsed_s",
    "numerator_net_E_J",
    "control_net_E_J",
    "delta_E_J",
    "denominator_source",
    "numerator_energy_source",
    "control_energy_source",
    "numerator_energy_integration_method",
    "control_energy_integration_method",
    "numerator_measurement_scope",
    "control_measurement_scope",
    "numerator_power_semantics",
    "control_power_semantics",
]

RELIABILITY_COLUMNS = [
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

NCU_ACCEPTANCE_COLUMNS = [
    "mode",
    "status",
    "active_SM",
    "blocks_per_SM",
    "ITER",
    "reuse_factor",
    "load_repeat",
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
    "dram_bytes",
    "tensor_hmma_inst",
    "local_read_bytes",
    "local_write_bytes",
    "spill_zero_verified",
    "spill_evidence_source",
    "stall_long_scoreboard_pct",
]

NCU_ACCEPTANCE_CANDIDATES = [
    ("reg_mma", "tensor_increment_candidate"),
    ("reg_operand_only", "register_control_candidate"),
    ("shared_scalar_load_only", "shared_memory_path"),
    ("global_l1_load_only", "global_l1_hit_path"),
    ("l2_cg_load_only", "l2_hit_path"),
    ("global_addr_only", "global_address_control"),
]

BASE_VALUES = {
    "Tensor MMA incremental": ("0.10", "pJ/FLOP", "0"),
    "Shared scalar path": ("0.20", "pJ/bit", "6"),
    "Global L1 hit path": ("0.30", "pJ/bit", "6"),
    "L2 CG hit path": ("1.00", "pJ/bit", "6"),
}

MATCHED_SUMMARY_COMPONENTS = {
    "tensor_mma_increment": ("0.10", "pJ/FLOP", "0", ""),
    "shared_l1_scalar_path": ("1.20", "pJ/byte", "6", "0.15"),
    "global_l1_hit_path": ("1.40", "pJ/byte", "6", "0.175"),
    "l2_hit_cg_path": ("9.00", "pJ/byte", "6", "1.125"),
    "dram_cg_stream_path": ("216.00", "pJ/byte", "6", "27.0"),
}

RELIABILITY_COMPONENTS = {
    "tensor_mma_increment": ("0.10", "pJ/FLOP", "0", "2"),
    "shared_l1_scalar_path": ("0.20", "pJ/bit", "6", "1"),
    "global_l1_hit_path": ("0.30", "pJ/bit", "6", "1"),
    "l2_hit_cg_path": ("1.00", "pJ/bit", "6", "1"),
}

PROFILE_POWER_SEMANTICS = {
    "rtx3090": "one_sec_average",
    "v100": "instant",
    "a100": "instant",
    "h100": "one_sec_average",
}

PROFILE_ACTIVE_SM = {
    "rtx3090": 82,
    "v100": 80,
    "a100": 108,
    "h100": 132,
}


def load_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location("audit_platform_result_package", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strict_summary_path(repo: Path, profile: str, tag: str) -> Path:
    return (
        repo
        / "results"
        / "summary"
        / f"{profile}_strict_scope_fresh_ncu_component_coefficients_{tag}.csv"
    )


def strict_audit_path(repo: Path, profile: str, tag: str) -> Path:
    return (
        repo
        / "results"
        / "summary"
        / f"{profile}_strict_scope_fresh_ncu_component_summary_audit_{tag}.csv"
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_preflight(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    omit_term: str | None = None,
    append_terms: list[str] | None = None,
) -> None:
    metadata = module.PROFILE_METADATA[profile]
    semantics = module.PROFILE_POWER_SEMANTICS[profile]
    path = repo / module.expected_paths(profile, tag)["preflight"]
    terms = [
        "# GPU Support Preflight",
        f"- Requested profile: `{profile}`",
        f"- Detected profile: `{profile}`",
        "## Preflight Verdict",
        "- `strict`: true",
        "- `profile_gate`: pass",
        "- `cuda_compiler_gate`: pass",
        "- `ncu_gate`: pass",
        "- `dry_run_gate`: pass",
        "- `overall`: pass",
        "- `errors`: none",
        "## GPU",
        "- `index`: 0",
        "- `name`: selftest",
        "- `uuid`: GPU-selftest",
        "- `driver_version`: 999.0",
        "- `compute_cap`: " + metadata["compute_capability"],
        "- `power_query_fields`: extended",
        "## Power Scope",
        "do not mix module or memory power into component coefficients",
        "- `module_power_query_rc`: 0",
        "- `power_detail_query_rc`: 0",
        "## Selected Harness Profile",
        f"- `power_usage_semantics`: {semantics}",
        f"- `dry_run_gpu`: 0",
        f"- `dry_run_active_sm`: {PROFILE_ACTIVE_SM[profile]}",
        "## CUDA Compiler",
        f"- `target`: compute_{metadata['compute_capability'].replace('.', '')}",
        "- `target_supported`: true",
        "## Nsight Compute",
        "- `version_rc`: 0",
        "- `list_chips_rc`: 0",
        "- `chip_supported`: true",
        "- `query_metrics_rc`: 0",
        "- `query_metrics_ok`: true",
        "## Binary Dry Run",
        "- `return_code`: 0",
        "target_profile=" + profile,
        "chip=" + metadata["chip"],
        "compute_capability=" + metadata["compute_capability"],
        f"target_l2_MiB={metadata['l2_mib']}",
        "target_unified_L1_shared_KiB_per_SM="
        + str(metadata["unified_l1_shared_kib_per_sm"]),
        f"target_shared_KiB_per_SM={metadata['shared_kib_per_sm']}",
        f"active_SM={PROFILE_ACTIVE_SM[profile]}",
    ]
    if omit_term is not None:
        terms = [term for term in terms if omit_term not in term]
    if append_terms is not None:
        terms.extend(append_terms)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(terms) + "\n", encoding="utf-8")


def write_summary(
    repo: Path,
    profile: str,
    tag: str,
    values: dict[str, tuple[str, str, str]],
    *,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
    omit_summary_column: str | None = None,
) -> None:
    rows: list[dict[str, str]] = []
    if power_semantics is None:
        power_semantics = PROFILE_POWER_SEMANTICS[profile]
    for component, (median, unit, ncu_denominator_rows) in values.items():
        rows.append(
            {
                "component": component,
                "median": median,
                "unit": unit,
                "rows_used": "6",
                "valid_detail_rows": "6",
                "invalid_detail_rows": "0",
                "ncu_denominator_rows": ncu_denominator_rows,
                "ncu_accepted_rows": "1",
                "reliability_status": "accepted",
                "energy_source": energy_source,
                "energy_integration_method": energy_integration_method,
                "measurement_scope": measurement_scope,
                "power_semantics": power_semantics,
                **summary_evidence_fields(component, unit),
            }
        )
    fieldnames = [
        column for column in STRICT_SUMMARY_COLUMNS if column != omit_summary_column
    ]
    if omit_summary_column is not None:
        for row in rows:
            row.pop(omit_summary_column, None)
    write_csv(strict_summary_path(repo, profile, tag), fieldnames, rows)


def summary_evidence_fields(component: str, unit: str) -> dict[str, str]:
    common = {
        "ncu_coordinate_rows": "2",
        "ncu_metric_rows": "1",
        "denominator_scale_min_med_max": "1",
        "ncu_stall_long_scoreboard_pct_min_med_max": "0.01",
    }
    if component == "Tensor MMA incremental":
        return {
            **common,
            "ncu_evidence_modes": "reg_mma,reg_operand_only",
            "ncu_metric_modes": "reg_mma",
            "ncu_evidence_coords": "reg_mma:W2048:B16:SM82:RF8:LR1:SR1",
            "ncu_path_evidence": "HMMA_inst=1000; L1_bytes=0",
            "ncu_counter_caveat": "tensor selftest evidence",
            "denominator_source": "logical_or_expected",
            "ncu_denominator_bytes_representative_min_med_max": "",
            "ncu_shared_bytes_min_med_max": "0",
            "ncu_l1_hit_rate_pct_min_med_max": "0",
            "ncu_l1_path_hit_rate_pct_min_med_max": "0",
            "ncu_l2_hit_rate_pct_min_med_max": "0",
            "ncu_l2_path_hit_rate_pct_min_med_max": "0",
            "ncu_l1_accesses_min_med_max": "0",
            "ncu_l2_accesses_min_med_max": "0",
            "ncu_dram_accesses_min_med_max": "0",
            "ncu_l1_bytes_min_med_max": "0",
            "ncu_l1_request_bytes_min_med_max": "0",
            "ncu_l1_hit_bytes_min_med_max": "0",
            "ncu_l1_miss_bytes_min_med_max": "0",
            "ncu_l2_bytes_min_med_max": "0",
            "ncu_l2_read_bytes_min_med_max": "0",
            "ncu_l2_read_hit_sectors_min_med_max": "0",
            "ncu_l2_read_miss_sectors_min_med_max": "0",
            "ncu_dram_bytes_min_med_max": "0",
            "ncu_tensor_hmma_inst_min_med_max": "1000",
            "ncu_local_read_bytes_min_med_max": "0",
            "ncu_local_write_bytes_min_med_max": "0",
            "ncu_spill_zero_verified_min_med_max": "1",
        }
    if component == "Shared scalar path":
        evidence = {
            "ncu_evidence_modes": "shared_scalar_load_only",
            "ncu_metric_modes": "shared_scalar_load_only",
            "ncu_evidence_coords": "shared_scalar_load_only:W64:B16:SM82:RF1:LR8:SR1",
            "ncu_path_evidence": "shared_bytes=1024",
            "ncu_counter_caveat": "shared selftest evidence",
            "ncu_shared_bytes_min_med_max": "1024",
        }
    elif component == "Global L1 hit path":
        evidence = {
            "ncu_evidence_modes": "global_addr_only,global_l1_load_only",
            "ncu_metric_modes": "global_l1_load_only",
            "ncu_evidence_coords": "global_l1_load_only:W16:B16:SM82:RF1:LR4:SR1",
            "ncu_path_evidence": "L1_path_hit_pct=99; L1_request/hit_bytes=1024/1014",
            "ncu_counter_caveat": "l1 selftest evidence",
            "ncu_l1_hit_rate_pct_min_med_max": "99",
            "ncu_l1_path_hit_rate_pct_min_med_max": "99",
            "ncu_l1_accesses_min_med_max": "32",
            "ncu_l1_bytes_min_med_max": "1024",
            "ncu_l1_request_bytes_min_med_max": "1024",
            "ncu_l1_hit_bytes_min_med_max": "1014",
            "ncu_l1_miss_bytes_min_med_max": "10",
        }
    else:
        evidence = {
            "ncu_evidence_modes": "global_addr_only,l2_cg_load_only",
            "ncu_metric_modes": "l2_cg_load_only",
            "ncu_evidence_coords": "l2_cg_load_only:W64:B16:SM82:RF1:LR4:SR1",
            "ncu_path_evidence": (
                "L1_path_hit_pct=0; L1_request/hit_bytes=2048/0; "
                "L2_read_hit_pct=99; L2_read_bytes=2048"
            ),
            "ncu_counter_caveat": "l2 selftest evidence",
            "ncu_l1_path_hit_rate_pct_min_med_max": "0",
            "ncu_l1_request_bytes_min_med_max": "2048",
            "ncu_l1_hit_bytes_min_med_max": "0",
            "ncu_l1_miss_bytes_min_med_max": "2048",
            "ncu_l2_hit_rate_pct_min_med_max": "99",
            "ncu_l2_path_hit_rate_pct_min_med_max": "99",
            "ncu_l2_accesses_min_med_max": "64",
            "ncu_l2_bytes_min_med_max": "2048",
            "ncu_l2_read_bytes_min_med_max": "2048",
            "ncu_l2_read_hit_sectors_min_med_max": "63.36",
            "ncu_l2_read_miss_sectors_min_med_max": "0.64",
        }
    defaults = {
        "denominator_source": "ncu_actual_exact" if unit == "pJ/bit" else "logical_or_expected",
        "ncu_denominator_bytes_representative_min_med_max": (
            "1024" if unit == "pJ/bit" else ""
        ),
        "ncu_shared_bytes_min_med_max": "0",
        "ncu_l1_hit_rate_pct_min_med_max": "0",
        "ncu_l1_path_hit_rate_pct_min_med_max": "0",
        "ncu_l2_hit_rate_pct_min_med_max": "0",
        "ncu_l2_path_hit_rate_pct_min_med_max": "0",
        "ncu_l1_accesses_min_med_max": "0",
        "ncu_l2_accesses_min_med_max": "0",
        "ncu_dram_accesses_min_med_max": "0",
        "ncu_l1_bytes_min_med_max": "0",
        "ncu_l1_request_bytes_min_med_max": "0",
        "ncu_l1_hit_bytes_min_med_max": "0",
        "ncu_l1_miss_bytes_min_med_max": "0",
        "ncu_l2_bytes_min_med_max": "0",
        "ncu_l2_read_bytes_min_med_max": "0",
        "ncu_l2_read_hit_sectors_min_med_max": "0",
        "ncu_l2_read_miss_sectors_min_med_max": "0",
        "ncu_dram_bytes_min_med_max": "0",
        "ncu_tensor_hmma_inst_min_med_max": "0",
    }
    return {**common, **defaults, **evidence}


def write_audit(
    repo: Path,
    profile: str,
    tag: str,
    *,
    stale: bool,
    failing: bool = False,
) -> None:
    if stale:
        rows = [
            {
                "component": "overall",
                "check": "old_check",
                "status": "pass",
                "expected": "old",
                "actual": "old",
                "interpretation": "stale audit with no hierarchy checks",
            }
        ]
        write_csv(strict_audit_path(repo, profile, tag), STRICT_AUDIT_COLUMNS, rows)
        return

    rows = [
        {
            "component": "Tensor MMA incremental",
            "check": "hard_plausibility_range",
            "status": "pass",
            "expected": "range",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "Shared scalar path",
            "check": "hard_plausibility_range",
            "status": "pass",
            "expected": "range",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "Global L1 hit path",
            "check": "hard_plausibility_range",
            "status": "fail" if failing else "pass",
            "expected": "range",
            "actual": "bad" if failing else "ok",
            "interpretation": "selftest",
        },
        {
            "component": "L2 CG hit path",
            "check": "hard_plausibility_range",
            "status": "fail" if failing else "pass",
            "expected": "range",
            "actual": "bad" if failing else "ok",
            "interpretation": "selftest",
        },
        {
            "component": "hierarchy",
            "check": "l2_greater_than_shared",
            "status": "pass",
            "expected": "L2 > shared",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "hierarchy",
            "check": "l2_greater_than_l1",
            "status": "pass",
            "expected": "L2 > L1",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "hierarchy",
            "check": "shared_l1_same_order",
            "status": "fail" if failing else "pass",
            "expected": "same order",
            "actual": "bad" if failing else "ok",
            "interpretation": "selftest",
        },
        {
            "component": "ncu",
            "check": "ncu_summary_counter_schema",
            "status": "pass",
            "expected": "counter schema",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "ncu",
            "check": "ncu_summary_coordinate_alignment",
            "status": "pass",
            "expected": "coordinate alignment",
            "actual": "ok",
            "interpretation": "selftest",
        },
        {
            "component": "ncu",
            "check": "ncu_evidence_summary_fields",
            "status": "pass",
            "expected": "summary evidence fields",
            "actual": "ok",
            "interpretation": "selftest",
        },
    ]
    write_csv(strict_audit_path(repo, profile, tag), STRICT_AUDIT_COLUMNS, rows)


def check_by_name(rows: list[dict[str, str]], name: str) -> dict[str, str]:
    matches = [row for row in rows if row.get("check") == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} row, got {len(matches)}")
    return matches[0]


def assert_status(
    rows: list[dict[str, str]],
    check: str,
    status: str,
    *,
    actual_contains: str | None = None,
) -> None:
    row = check_by_name(rows, check)
    if row.get("status") != status:
        raise AssertionError(f"{check}: expected {status}, got {row.get('status')}: {row}")
    if actual_contains is not None and actual_contains not in row.get("actual", ""):
        raise AssertionError(
            f"{check}: expected actual to contain {actual_contains!r}, got {row.get('actual')!r}"
        )


def write_raw_files(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    total_energy_supported: str = "true",
    power_semantics: str | None = None,
    elapsed_s: str = "10",
    e_before_mj: str = "1000",
    e_after_mj: str = "2000",
    delta_e_j: str = "1",
    idle_baseline_j: str = "0.1",
    net_e_j: str = "0.9",
    iter_count: str = "1000",
    omit_tensor_revision: bool = False,
    omit_cg_warmup_policy: bool = False,
) -> None:
    metadata = module.PROFILE_METADATA[profile]
    if power_semantics is None:
        power_semantics = module.PROFILE_POWER_SEMANTICS[profile]
    raw_paths = module.expected_paths(profile, tag)["raw"]
    for path in raw_paths:
        suffix = path.stem.rsplit("_", 1)[-1]
        mode_by_suffix = {
            "tensor": "reg_mma",
            "shared": "shared_scalar_load_only",
            "l1": "global_l1_load_only",
            "l2": "l2_cg_load_only",
            "dram": "dram_cg_load_only",
        }
        mode = mode_by_suffix[suffix]
        note_parts: list[str] = []
        if mode == "reg_mma" and not omit_tensor_revision:
            note_parts.append(
                "tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2"
            )
        if mode in {"l2_cg_load_only", "dram_cg_load_only"} and not omit_cg_warmup_policy:
            note_parts.append("global_warmup_policy=ld_global_cg")
        row = {
            "mode": mode,
            "profile_name": metadata["profile_name"],
            "architecture_family": metadata["architecture_family"],
            "chip": metadata["chip"],
            "compute_capability": metadata["compute_capability"],
            "l2_mib": str(metadata["l2_mib"]),
            "unified_l1_shared_kib_per_sm": str(
                metadata["unified_l1_shared_kib_per_sm"]
            ),
            "shared_kib_per_sm": str(metadata["shared_kib_per_sm"]),
            "active_SM": str(PROFILE_ACTIVE_SM[profile]),
            "sm_count": str(PROFILE_ACTIVE_SM[profile]),
            "energy_source": energy_source,
            "energy_integration_method": energy_integration_method,
            "measurement_scope": measurement_scope,
            "nvml_total_energy_supported": total_energy_supported,
            "nvml_power_usage_semantics": power_semantics,
            "elapsed_s": elapsed_s,
            "measurement_start_epoch_ms": "100000",
            "measurement_end_epoch_ms": str(
                100000 + int(round(float(elapsed_s) * 1000.0))
            ),
            "E_before_mJ": e_before_mj,
            "E_after_mJ": e_after_mj,
            "delta_E_J": delta_e_j,
            "idle_baseline_J": idle_baseline_j,
            "net_E_J": net_e_j,
            "ITER": iter_count,
            "notes": ";".join(note_parts) + (";" if note_parts else ""),
        }
        write_csv(repo / path, RAW_COLUMNS, [row])


def write_power_api_audit(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    status: str = "final_candidate",
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
) -> None:
    if power_semantics is None:
        power_semantics = module.PROFILE_POWER_SEMANTICS[profile]
    path = repo / module.expected_paths(profile, tag)["power_api"]
    row = {
        "status": status,
        "energy_source": energy_source,
        "energy_integration_method": energy_integration_method,
        "measurement_scope": measurement_scope,
        "actual_power_semantics": power_semantics,
    }
    write_csv(path, POWER_API_COLUMNS, [row])


def write_l2_path_selection_fixture(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    selected: bool = True,
    policy: str = "normal",
) -> None:
    path = repo / module.expected_paths(profile, tag)["l2_path_selection"]
    expected_w = (16, 128) if profile == "a100" else (32, 64)
    rows = []
    for w_sm_kib in expected_w:
        rows.append(
            {
                "policy": policy,
                "layout": "sm_interleaved",
                "blocks_per_SM": "8" if profile == "a100" else "16",
                "W_SM_KiB": str(w_sm_kib),
                "load_repeat": "4",
                "l1_path_hit_rate_pct": "0",
                "l2_path_hit_rate_pct": "99.5",
                "l2_native_read_hit_rate_pct": "99.4",
                "l2_native_vs_derived_hit_delta_pct": "0.1",
                "native_l2_gate": (
                    "required"
                    if profile == "a100"
                    else "optional_present_cross_checked"
                ),
                "l2_read_sector_conservation_ratio": "1",
                "l2_read_bytes_to_expected": "1",
                "dram_read_to_l2_read_ratio": "0.001",
                "launch_persisting_l2_cache_size_bytes": (
                    "1048576" if policy == "persisting" else "0"
                ),
                "selected_candidate": "yes" if selected else "no",
                "status": "pass",
                "reason": "pass",
            }
        )
    write_csv(path, list(rows[0]), rows)


def write_power_state_audit(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    missing_column: str | None = None,
    status: str = "ok",
    coefficient_eligible: str = "true",
    average_power_w: str = "100",
) -> None:
    path = repo / module.expected_paths(profile, tag)["power_state"]
    row = {
        "input_file": f"results/raw/{profile}_component_finalplan_selftest_tensor.csv",
        "row_index": "2",
        "run_id": "selftest",
        "mode": "reg_mma",
        "W_SM_KiB": "64",
        "blocks_per_SM": "16",
        "active_SM": str(PROFILE_ACTIVE_SM[profile]),
        "reuse_factor": "1",
        "load_repeat": "1",
        "store_repeat": "1",
        "elapsed_s": "10",
        "net_E_J": "1000",
        "average_power_W": average_power_w,
        "group_rows": "3",
        "group_power_median_W": "100",
        "group_power_mad_W": "1",
        "average_power_delta_W": "0",
        "endpoint_after_W": "100",
        "group_endpoint_after_median_W": "100",
        "endpoint_after_ratio": "1",
        "temp_C": "60",
        "group_temp_median_C": "60",
        "clock_sm_mhz": "1400",
        "group_clock_sm_median_mhz": "1400",
        "status": status,
        "coefficient_eligible": coefficient_eligible,
        "reasons": "selftest" if status == "reject" else "",
        "notes": "",
    }
    fieldnames = list(POWER_STATE_COLUMNS)
    if missing_column is not None:
        fieldnames = [name for name in fieldnames if name != missing_column]
    write_csv(path, fieldnames, [{key: row.get(key, "") for key in fieldnames}])


def write_matched_summary(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    missing_component: str | None = None,
    zero_ncu_component: str | None = None,
    nonpositive_median_component: str | None = None,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
    omit_summary_column: str | None = None,
) -> None:
    if power_semantics is None:
        power_semantics = module.PROFILE_POWER_SEMANTICS[profile]
    path = repo / module.expected_paths(profile, tag)["matched_summary"]
    rows = []
    for component, (median, unit, ncu_rows, pbit) in MATCHED_SUMMARY_COMPONENTS.items():
        if component == missing_component:
            continue
        rows.append(
            {
                "component": component,
                "rows": "6",
                "ncu_denominator_rows": (
                    "0" if component == zero_ncu_component else ncu_rows
                ),
                "expected_denominator_rows": "0",
                "unit": unit,
                "energy_source": energy_source,
                "energy_integration_method": energy_integration_method,
                "measurement_scope": measurement_scope,
                "power_semantics": power_semantics,
                "median": (
                    "0" if component == nonpositive_median_component else median
                ),
                "confidence_class": "medium",
                "median_pJ_per_bit": pbit,
            }
        )
    write_csv(path, MATCHED_SUMMARY_COLUMNS, rows)


def write_matched_detail(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    tensor_pair_energy_basis: str = "matched_iters_net_energy",
    tensor_control_iters: str = "1000",
    tensor_control_elapsed_s: str = "1.0",
    l2_pair_energy_basis: str = "matched_iters_net_energy",
    l2_control_iters: str = "1000",
    l2_control_elapsed_s: str = "1.0",
    dram_pair_energy_basis: str = "matched_iters_net_energy",
    dram_control_iters: str = "1000",
    dram_control_elapsed_s: str = "1.0",
    pair_timing_source: str = "exact_epoch_interval",
    include_reverse_order: bool = True,
    pair_transition_gap_ms: str = "1000",
    pair_transition_gap_limit_ms: str = "30000",
) -> None:
    semantics = module.PROFILE_POWER_SEMANTICS[profile]
    rows: list[dict[str, str]] = []
    for component in MATCHED_SUMMARY_COMPONENTS:
        tensor = component == "tensor_mma_increment"
        l2 = component == "l2_hit_cg_path"
        dram = component == "dram_cg_stream_path"
        base_row = {
                "component": component,
                "valid_component_estimate": "True",
                "pair_energy_basis": (
                    tensor_pair_energy_basis
                    if tensor
                    else l2_pair_energy_basis
                    if l2
                    else dram_pair_energy_basis
                    if dram
                    else "duration_scaled_control_power"
                ),
                "ncu_control_acceptance_required": (
                    "True"
                    if component
                    in {
                        "tensor_mma_increment",
                        "global_l1_hit_path",
                        "l2_hit_cg_path",
                        "dram_cg_stream_path",
                    }
                    else "False"
                ),
                "ncu_control_acceptance_exact": (
                    "True"
                    if component
                    in {
                        "tensor_mma_increment",
                        "global_l1_hit_path",
                        "l2_hit_cg_path",
                        "dram_cg_stream_path",
                    }
                    else ""
                ),
                "pair_transition_gap_ms": pair_transition_gap_ms,
                "pair_transition_gap_limit_ms": pair_transition_gap_limit_ms,
                "pair_timing_source": pair_timing_source,
                "pair_execution_order": "control_then_treatment",
                "numerator_ITER": "1000",
                "control_ITER": (
                    tensor_control_iters
                    if tensor
                    else l2_control_iters
                    if l2
                    else dram_control_iters
                    if dram
                    else "900"
                ),
                "iter_ratio": (
                    str(1000.0 / float(tensor_control_iters))
                    if tensor and float(tensor_control_iters) > 0.0
                    else str(1000.0 / float(l2_control_iters))
                    if l2 and float(l2_control_iters) > 0.0
                    else str(1000.0 / float(dram_control_iters))
                    if dram and float(dram_control_iters) > 0.0
                    else "1.111111111"
                ),
                "numerator_elapsed_s": "10",
                "control_elapsed_s": (
                    tensor_control_elapsed_s
                    if tensor
                    else l2_control_elapsed_s
                    if l2
                    else dram_control_elapsed_s
                    if dram
                    else "10"
                ),
                "numerator_net_E_J": "120",
                "control_net_E_J": "20",
                "delta_E_J": "20",
                "denominator_source": (
                    "logical_or_expected" if tensor else "ncu_actual_exact"
                ),
                "numerator_energy_source": "nvml_total_energy",
                "control_energy_source": "nvml_total_energy",
                "numerator_energy_integration_method": "total_energy_mj_delta",
                "control_energy_integration_method": "total_energy_mj_delta",
                "numerator_measurement_scope": "gpu_device_total_energy_counter",
                "control_measurement_scope": "gpu_device_total_energy_counter",
                "numerator_power_semantics": semantics,
                "control_power_semantics": semantics,
            }
        rows.append(base_row)
        if include_reverse_order:
            rows.append(
                {**base_row, "pair_execution_order": "treatment_then_control"}
            )
    write_csv(
        repo / module.expected_paths(profile, tag)["matched_detail"],
        MATCHED_DETAIL_COLUMNS,
        rows,
    )


def write_tensor_pair_calibration_fixture(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
    treatment_calibrated_iters: str = "900",
    control_min_calibrated_iters: str = "1000",
    resolution_policy: str = "max_treatment_and_control_min_iters",
) -> tuple[Path, Path]:
    paths = module.expected_paths(profile, tag)
    calibration_path = repo / paths["tensor_pair_calibration"]
    tensor_path = repo / paths["raw"][0]
    coord = {
        "W_SM_KiB": "2048",
        "blocks_per_SM": "16",
        "active_SM": str(PROFILE_ACTIVE_SM[profile]),
        "reuse_factor": "4",
        "load_repeat": "1",
        "store_repeat": "1",
    }
    calibration_row = {
        "target_profile": profile,
        "gpu_list": "0",
        **coord,
        "calibration_source_mode": "reg_mma",
        "treatment_target_seconds": "10",
        "control_min_seconds": "1",
        "treatment_calibrated_iters": treatment_calibrated_iters,
        "control_min_calibrated_iters": control_min_calibrated_iters,
        "resolved_iters": manifest_iters,
        "resolution_policy": resolution_policy,
        "status": "pair_locked",
        "calibration_command": "benchmark --mode reg_mma --calibrate-only",
        "treatment_calibration_command": (
            "benchmark --mode reg_mma --seconds 10 --calibrate-only"
        ),
        "control_calibration_command": (
            "benchmark --mode reg_operand_only --seconds 1 --calibrate-only"
        ),
    }
    write_csv(
        calibration_path,
        sorted(module.TENSOR_PAIR_CALIBRATION_REQUIRED_COLUMNS),
        [calibration_row],
    )
    tensor_fields = ["mode", *coord.keys(), "ITER"]
    write_csv(
        tensor_path,
        tensor_fields,
        [
            {"mode": "reg_mma", **coord, "ITER": "1000"},
            {"mode": "reg_operand_only", **coord, "ITER": control_iters},
        ],
    )
    return calibration_path, tensor_path


def write_memory_pair_calibration_fixture(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    treatment_mode: str,
    artifact_key: str,
    raw_index: int,
    w_sm_kib: str,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
) -> tuple[Path, Path]:
    paths = module.expected_paths(profile, tag)
    calibration_path = repo / paths[artifact_key]
    raw_path = repo / paths["raw"][raw_index]
    coord = {
        "W_SM_KiB": w_sm_kib,
        "blocks_per_SM": "16",
        "active_SM": str(PROFILE_ACTIVE_SM[profile]),
        "reuse_factor": "1",
        "load_repeat": "4",
        "store_repeat": "1",
    }
    calibration_row = {
        "target_profile": profile,
        "gpu_list": "0",
        **coord,
        "calibration_source_mode": treatment_mode,
        "treatment_target_seconds": "10",
        "control_min_seconds": "1",
        "treatment_calibrated_iters": "1000",
        "control_min_calibrated_iters": "300",
        "resolved_iters": manifest_iters,
        "resolution_policy": "max_treatment_and_control_min_iters",
        "status": "pair_locked",
        "calibration_command": f"benchmark --mode {treatment_mode} --calibrate-only",
        "treatment_calibration_command": (
            f"benchmark --mode {treatment_mode} --seconds 10 --calibrate-only"
        ),
        "control_calibration_command": (
            "benchmark --mode global_addr_only --seconds 1 --calibrate-only"
        ),
    }
    write_csv(
        calibration_path,
        sorted(module.TENSOR_PAIR_CALIBRATION_REQUIRED_COLUMNS),
        [calibration_row],
    )
    raw_fields = ["mode", *coord.keys(), "ITER"]
    write_csv(
        raw_path,
        raw_fields,
        [
            {"mode": treatment_mode, **coord, "ITER": "1000"},
            {"mode": "global_addr_only", **coord, "ITER": control_iters},
        ],
    )
    return calibration_path, raw_path


def write_dram_pair_calibration_fixture(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
) -> tuple[Path, Path]:
    return write_memory_pair_calibration_fixture(
        module,
        repo,
        profile,
        tag,
        treatment_mode="dram_cg_load_only",
        artifact_key="dram_pair_calibration",
        raw_index=-1,
        w_sm_kib="8192",
        control_iters=control_iters,
        manifest_iters=manifest_iters,
    )


def write_l2_pair_calibration_fixture(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
) -> tuple[Path, Path]:
    return write_memory_pair_calibration_fixture(
        module,
        repo,
        profile,
        tag,
        treatment_mode="l2_cg_load_only",
        artifact_key="l2_pair_calibration",
        raw_index=3,
        w_sm_kib="32",
        control_iters=control_iters,
        manifest_iters=manifest_iters,
    )


def write_reliability(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    missing_component: str | None = None,
    status_override_component: str | None = None,
    status_override: str = "accepted_with_caution",
    invalid_component: str | None = None,
    zero_ncu_component: str | None = None,
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
) -> None:
    if power_semantics is None:
        power_semantics = module.PROFILE_POWER_SEMANTICS[profile]
    path = repo / module.expected_paths(profile, tag)["reliability"]
    rows = []
    for component, (median, unit, ncu_rows, accepted_rows) in RELIABILITY_COMPONENTS.items():
        if component == missing_component:
            continue
        status = status_override if component == status_override_component else "accepted"
        rows.append(
            {
                "component": component,
                "status": status,
                "median": median,
                "unit": unit,
                "rows": "6",
                "valid_detail_rows": "6",
                "invalid_detail_rows": "1" if component == invalid_component else "0",
                "ncu_denominator_rows": (
                    "0" if component == zero_ncu_component else ncu_rows
                ),
                "ncu_accepted_rows": accepted_rows,
                "confidence_class": "medium",
                "energy_source": "nvml_total_energy",
                "energy_integration_method": "total_energy_mj_delta",
                "measurement_scope": measurement_scope,
                "power_semantics": power_semantics,
                "reasons": "",
                "cautions": "selftest_caution" if status != "accepted" else "",
            }
        )
    write_csv(path, RELIABILITY_COLUMNS, rows)


def base_ncu_row(
    mode: str,
    *,
    active_sm: str = "82",
    reuse_factor: str = "1",
    load_repeat: str = "1",
) -> dict[str, str]:
    row = {
        "label": mode,
        "mode": mode,
        "status": "ok",
        "W_SM_KiB": "64",
        "blocks_per_SM": "16",
        "active_SM": active_sm,
        "ITER": "1000",
        "reuse_factor": reuse_factor,
        "load_repeat": load_repeat,
        "l1_hit_rate_pct": "0",
        "l1_path_hit_rate_pct": "0",
        "l2_hit_rate_pct": "0",
        "l2_path_hit_rate_pct": "0",
        "l1_accesses": "0",
        "l1_access_unit": "requests",
        "l2_accesses": "0",
        "l2_access_unit": "requests",
        "dram_accesses": "0",
        "dram_access_unit": "requests",
        "l1_bytes": "0",
        "l1_request_bytes": "0",
        "l1_hit_bytes": "0",
        "l1_miss_bytes": "0",
        "l2_bytes": "0",
        "l2_read_bytes": "0",
        "l2_read_hit_sectors": "0",
        "l2_read_miss_sectors": "0",
        "dram_bytes": "0",
        "shared_accesses": "0",
        "shared_bytes": "0",
        "shared_inst": "0",
        "tensor_hmma_inst": "0",
        "local_read_bytes": "0",
        "local_write_bytes": "0",
        "spill_zero_verified": "1",
        "spill_evidence_source": "local_memory_bytes_zero_inference",
        "stall_long_scoreboard_pct": "0",
        "missing_metrics": "",
    }
    if mode in {"reg_mma", "reg_operand_only"}:
        row["W_SM_KiB"] = "2048"
    if mode == "dram_cg_load_only":
        row["W_SM_KiB"] = "8192"
    if mode == "reg_mma":
        row["tensor_hmma_inst"] = "100"
    elif mode == "shared_scalar_load_only":
        row["shared_accesses"] = "100"
        row["shared_bytes"] = "4096"
        row["shared_inst"] = "100"
    elif mode == "global_l1_load_only":
        row["l1_hit_rate_pct"] = "99"
        row["l1_path_hit_rate_pct"] = "99"
        row["l1_accesses"] = "100"
        row["l1_bytes"] = "4096"
        row["l1_request_bytes"] = "4096"
        row["l1_hit_bytes"] = "4055.04"
        row["l1_miss_bytes"] = "40.96"
    elif mode in {"l2_load_only", "l2_cg_load_only"}:
        row["l2_hit_rate_pct"] = "99"
        row["l2_path_hit_rate_pct"] = "99"
        row["l1_request_bytes"] = "4096"
        row["l1_miss_bytes"] = "4096"
        row["l2_accesses"] = "100"
        row["l2_bytes"] = "4096"
        row["l2_read_bytes"] = "4096"
        row["l2_read_hit_sectors"] = "99"
        row["l2_read_miss_sectors"] = "1"
    elif mode == "dram_cg_load_only":
        row["dram_accesses"] = "100"
        row["dram_bytes"] = "4096"
    return row


def good_ncu_rows(module: Any, profile: str) -> list[dict[str, str]]:
    active_sm = str(PROFILE_ACTIVE_SM[profile])
    rows = [base_ncu_row("clocked_empty", active_sm=active_sm)]
    for reuse_factor in ("1", "2", "4"):
        rows.append(
            base_ncu_row(
                "reg_operand_only",
                active_sm=active_sm,
                reuse_factor=reuse_factor,
            )
        )
        rows.append(
            base_ncu_row("reg_mma", active_sm=active_sm, reuse_factor=reuse_factor)
        )
    memory_modes = [
        "shared_scalar_load_only",
        "global_addr_only",
        "global_l1_load_only",
        "l2_cg_load_only",
        "dram_cg_load_only",
    ]
    if profile in module.PROFILE_EXTRA_NCU_REQUIRED_MODES:
        memory_modes.extend(sorted(module.PROFILE_EXTRA_NCU_REQUIRED_MODES[profile]))
    for mode in memory_modes:
        for load_repeat in ("1", "2", "4"):
            rows.append(base_ncu_row(mode, active_sm=active_sm, load_repeat=load_repeat))
    return rows


def write_ncu_summary(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    missing_column: str | None = None,
    zero_l2_bytes: bool = False,
    low_l1_hit: bool = False,
    l2_high_l1_traffic: bool = False,
    misleading_aggregate_l2: bool = False,
    low_l2_path_hit: bool = False,
    dram_high_l2_hit: bool = False,
    wrong_active_sm: bool = False,
    local_spill: bool = False,
) -> None:
    path = repo / module.expected_paths(profile, tag)["ncu_summary"]
    fieldnames = sorted(module.NCU_REQUIRED_COLUMNS)
    if missing_column is not None:
        fieldnames = [name for name in fieldnames if name != missing_column]
    rows = good_ncu_rows(module, profile)
    if zero_l2_bytes:
        for row in rows:
            if row["mode"] == "l2_cg_load_only":
                row["l2_bytes"] = "0"
                row["l2_read_bytes"] = "0"
    if low_l1_hit:
        for row in rows:
            if row["mode"] == "global_l1_load_only":
                row["l1_hit_rate_pct"] = "10"
                row["l1_path_hit_rate_pct"] = "10"
    if l2_high_l1_traffic:
        for row in rows:
            if row["mode"] == "l2_cg_load_only":
                row["l1_hit_rate_pct"] = "50"
                row["l1_path_hit_rate_pct"] = "50"
                row["l1_bytes"] = row["l2_bytes"]
                row["l1_hit_bytes"] = row["l1_request_bytes"]
    if misleading_aggregate_l2:
        for row in rows:
            if row["mode"] == "l2_cg_load_only":
                row["l1_hit_rate_pct"] = "71.5"
                row["l2_hit_rate_pct"] = "71.5"
                row["l1_bytes"] = row["l2_bytes"]
    if low_l2_path_hit:
        for row in rows:
            if row["mode"] == "l2_cg_load_only":
                row["l2_path_hit_rate_pct"] = "72"
    if dram_high_l2_hit:
        for row in rows:
            if row["mode"] == "dram_cg_load_only":
                row["l2_hit_rate_pct"] = "99"
                row["l2_path_hit_rate_pct"] = "99"
    if wrong_active_sm:
        for row in rows:
            row["active_SM"] = "82" if profile != "rtx3090" else "1"
    if local_spill:
        for row in rows:
            if row["mode"] == "reg_mma":
                row["local_read_bytes"] = "32"
                row["spill_zero_verified"] = "0"
    filtered = [{key: row.get(key, "") for key in fieldnames} for row in rows]
    write_csv(path, fieldnames, filtered)


def write_ncu_acceptance(
    module: Any,
    repo: Path,
    profile: str,
    tag: str,
    *,
    missing_candidate: str | None = None,
    rejected_candidate: str | None = None,
    missing_column: str | None = None,
    bad_l1_evidence: bool = False,
) -> None:
    path = repo / module.expected_paths(profile, tag)["ncu_acceptance"]
    rows = []
    for mode, candidate in NCU_ACCEPTANCE_CANDIDATES:
        if candidate == missing_candidate:
            continue
        row = {
            "mode": mode,
            "status": "ok",
            "active_SM": str(PROFILE_ACTIVE_SM[profile]),
            "blocks_per_SM": "16",
            "ITER": "1000",
            "reuse_factor": "1",
            "load_repeat": "1",
            "component_candidate": candidate,
            "acceptance": "rejected" if candidate == rejected_candidate else "accepted",
            "acceptance_reason": "selftest" if candidate == rejected_candidate else "pass",
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
            "dram_bytes": "0",
            "tensor_hmma_inst": "0",
            "local_read_bytes": "0",
            "local_write_bytes": "0",
            "spill_zero_verified": "1",
            "spill_evidence_source": "local_memory_bytes_zero_inference",
            "stall_long_scoreboard_pct": "0",
        }
        if mode == "reg_mma":
            row["tensor_hmma_inst"] = "100"
        elif mode == "shared_scalar_load_only":
            row["shared_accesses"] = "100"
            row["shared_bytes"] = "4096"
            row["shared_inst"] = "100"
        elif mode == "global_l1_load_only":
            row["l1_hit_rate_pct"] = "10" if bad_l1_evidence else "99"
            row["l1_path_hit_rate_pct"] = "10" if bad_l1_evidence else "99"
            row["l1_bytes"] = "4096"
            row["l1_request_bytes"] = "4096"
            row["l1_hit_bytes"] = "4055.04"
            row["l1_miss_bytes"] = "40.96"
        elif mode == "l2_cg_load_only":
            row["l2_hit_rate_pct"] = "99"
            row["l2_path_hit_rate_pct"] = "99"
            row["l1_request_bytes"] = "4096"
            row["l1_miss_bytes"] = "4096"
            row["l2_bytes"] = "4096"
            row["l2_read_bytes"] = "4096"
            row["l2_read_hit_sectors"] = "99"
            row["l2_read_miss_sectors"] = "1"
        rows.append(row)
    fieldnames = list(NCU_ACCEPTANCE_COLUMNS)
    if missing_column is not None:
        fieldnames = [name for name in fieldnames if name != missing_column]
    write_csv(path, fieldnames, [{key: row.get(key, "") for key in fieldnames} for row in rows])


def run_case(
    module: Any,
    *,
    name: str,
    values: dict[str, tuple[str, str, str]],
    profile: str = "rtx3090",
    stale_audit: bool,
    failing_audit: bool,
    expected_policy_status: str,
    expected_audit_status: str,
    expected_policy_text: str | None = None,
    expected_audit_text: str | None = None,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
    omit_summary_column: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(
            repo,
            profile,
            "selftest",
            values,
            energy_source=energy_source,
            energy_integration_method=energy_integration_method,
            measurement_scope=measurement_scope,
            power_semantics=power_semantics,
            omit_summary_column=omit_summary_column,
        )
        write_audit(repo, profile, "selftest", stale=stale_audit, failing=failing_audit)
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(
            rows,
            "strict_summary_policy",
            expected_policy_status,
            actual_contains=expected_policy_text,
        )
        assert_status(
            rows,
            "strict_summary_audit_clean",
            expected_audit_status,
            actual_contains=expected_audit_text,
        )
        print(f"{name}: ok")


def run_preflight_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    omit_term: str | None = None,
    append_terms: list[str] | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_preflight(
            module,
            repo,
            profile,
            "selftest",
            omit_term=omit_term,
            append_terms=append_terms,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "preflight_present", "pass")
        assert_status(
            rows,
            "preflight_power_scope_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_ncu_acceptance_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    missing_candidate: str | None = None,
    rejected_candidate: str | None = None,
    missing_column: str | None = None,
    bad_l1_evidence: bool = False,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_ncu_acceptance(
            module,
            repo,
            profile,
            "selftest",
            missing_candidate=missing_candidate,
            rejected_candidate=rejected_candidate,
            missing_column=missing_column,
            bad_l1_evidence=bad_l1_evidence,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(
            rows,
            "ncu_acceptance_present",
            "pass",
        )
        assert_status(
            rows,
            "ncu_path_acceptance",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_ncu_summary_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    missing_column: str | None = None,
    zero_l2_bytes: bool = False,
    low_l1_hit: bool = False,
    l2_high_l1_traffic: bool = False,
    misleading_aggregate_l2: bool = False,
    low_l2_path_hit: bool = False,
    dram_high_l2_hit: bool = False,
    wrong_active_sm: bool = False,
    local_spill: bool = False,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_ncu_summary(
            module,
            repo,
            profile,
            "selftest",
            missing_column=missing_column,
            zero_l2_bytes=zero_l2_bytes,
            low_l1_hit=low_l1_hit,
            l2_high_l1_traffic=l2_high_l1_traffic,
            misleading_aggregate_l2=misleading_aggregate_l2,
            low_l2_path_hit=low_l2_path_hit,
            dram_high_l2_hit=dram_high_l2_hit,
            wrong_active_sm=wrong_active_sm,
            local_spill=local_spill,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(
            rows,
            "ncu_summary_present",
            "pass",
        )
        assert_status(
            rows,
            "ncu_cache_counter_schema",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_matched_summary_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    missing_component: str | None = None,
    zero_ncu_component: str | None = None,
    nonpositive_median_component: str | None = None,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_matched_summary(
            module,
            repo,
            profile,
            "selftest",
            missing_component=missing_component,
            zero_ncu_component=zero_ncu_component,
            nonpositive_median_component=nonpositive_median_component,
            energy_source=energy_source,
            energy_integration_method=energy_integration_method,
            measurement_scope=measurement_scope,
            power_semantics=power_semantics,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "matched_summary_present", "pass")
        assert_status(
            rows,
            "matched_control_summary_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_l2_path_selection_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    selected: bool = True,
    policy: str = "normal",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_l2_path_selection_fixture(
            module,
            repo,
            profile,
            "selftest",
            selected=selected,
            policy=policy,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "l2_path_selection_present", "pass")
        assert_status(
            rows,
            "l2_path_selected_before_energy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_matched_detail_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    tensor_pair_energy_basis: str = "matched_iters_net_energy",
    tensor_control_iters: str = "1000",
    tensor_control_elapsed_s: str = "1.0",
    l2_pair_energy_basis: str = "matched_iters_net_energy",
    l2_control_iters: str = "1000",
    l2_control_elapsed_s: str = "1.0",
    dram_pair_energy_basis: str = "matched_iters_net_energy",
    dram_control_iters: str = "1000",
    dram_control_elapsed_s: str = "1.0",
    pair_timing_source: str = "exact_epoch_interval",
    include_reverse_order: bool = True,
    pair_transition_gap_ms: str = "1000",
    pair_transition_gap_limit_ms: str = "30000",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_matched_detail(
            module,
            repo,
            profile,
            "selftest",
            tensor_pair_energy_basis=tensor_pair_energy_basis,
            tensor_control_iters=tensor_control_iters,
            tensor_control_elapsed_s=tensor_control_elapsed_s,
            l2_pair_energy_basis=l2_pair_energy_basis,
            l2_control_iters=l2_control_iters,
            l2_control_elapsed_s=l2_control_elapsed_s,
            dram_pair_energy_basis=dram_pair_energy_basis,
            dram_control_iters=dram_control_iters,
            dram_control_elapsed_s=dram_control_elapsed_s,
            pair_timing_source=pair_timing_source,
            include_reverse_order=include_reverse_order,
            pair_transition_gap_ms=pair_transition_gap_ms,
            pair_transition_gap_limit_ms=pair_transition_gap_limit_ms,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "matched_detail_present", "pass")
        assert_status(
            rows,
            "matched_control_detail_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_tensor_pair_calibration_case(
    module: Any,
    *,
    name: str,
    expected_status: str,
    expected_text: str | None = None,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
    treatment_calibrated_iters: str = "900",
    control_min_calibrated_iters: str = "1000",
    resolution_policy: str = "max_treatment_and_control_min_iters",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        calibration_path, tensor_path = write_tensor_pair_calibration_fixture(
            module,
            repo,
            "a100",
            "selftest",
            control_iters=control_iters,
            manifest_iters=manifest_iters,
            treatment_calibrated_iters=treatment_calibrated_iters,
            control_min_calibrated_iters=control_min_calibrated_iters,
            resolution_policy=resolution_policy,
        )
        rows: list[dict[str, str]] = []
        module.audit_tensor_pair_calibration(
            repo,
            rows,
            calibration_path.relative_to(repo),
            tensor_path.relative_to(repo),
            profile="a100",
        )
        assert_status(
            rows,
            "tensor_pair_calibration_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_dram_pair_calibration_case(
    module: Any,
    *,
    name: str,
    expected_status: str,
    expected_text: str | None = None,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        calibration_path, dram_path = write_dram_pair_calibration_fixture(
            module,
            repo,
            "a100",
            "selftest",
            control_iters=control_iters,
            manifest_iters=manifest_iters,
        )
        rows: list[dict[str, str]] = []
        module.audit_dram_pair_calibration(
            repo,
            rows,
            calibration_path.relative_to(repo),
            dram_path.relative_to(repo),
            profile="a100",
        )
        assert_status(
            rows,
            "dram_pair_calibration_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_l2_pair_calibration_case(
    module: Any,
    *,
    name: str,
    expected_status: str,
    expected_text: str | None = None,
    control_iters: str = "1000",
    manifest_iters: str = "1000",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        calibration_path, l2_path = write_l2_pair_calibration_fixture(
            module,
            repo,
            "v100",
            "selftest",
            control_iters=control_iters,
            manifest_iters=manifest_iters,
        )
        rows: list[dict[str, str]] = []
        module.audit_memory_pair_calibration(
            repo,
            rows,
            calibration_path.relative_to(repo),
            l2_path.relative_to(repo),
            profile="v100",
            treatment_mode="l2_cg_load_only",
            pair_label="l2",
        )
        assert_status(
            rows,
            "l2_pair_calibration_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_power_state_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    missing_column: str | None = None,
    status: str = "ok",
    coefficient_eligible: str = "true",
    average_power_w: str = "100",
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_power_state_audit(
            module,
            repo,
            profile,
            "selftest",
            missing_column=missing_column,
            status=status,
            coefficient_eligible=coefficient_eligible,
            average_power_w=average_power_w,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "power_state_present", "pass")
        assert_status(
            rows,
            "power_state_audit_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_reliability_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    missing_component: str | None = None,
    status_override_component: str | None = None,
    invalid_component: str | None = None,
    zero_ncu_component: str | None = None,
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_reliability(
            module,
            repo,
            profile,
            "selftest",
            missing_component=missing_component,
            status_override_component=status_override_component,
            invalid_component=invalid_component,
            zero_ncu_component=zero_ncu_component,
            measurement_scope=measurement_scope,
            power_semantics=power_semantics,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "reliability_present", "pass")
        assert_status(
            rows,
            "component_reliability",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_power_api_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_status: str,
    expected_text: str | None = None,
    status: str = "final_candidate",
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    power_semantics: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_power_api_audit(
            module,
            repo,
            profile,
            "selftest",
            status=status,
            energy_source=energy_source,
            energy_integration_method=energy_integration_method,
            measurement_scope=measurement_scope,
            power_semantics=power_semantics,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(rows, "power_api_present", "pass")
        assert_status(
            rows,
            "power_api_audit_policy",
            expected_status,
            actual_contains=expected_text,
        )
        print(f"{name}: ok")


def run_raw_policy_case(
    module: Any,
    *,
    name: str,
    profile: str,
    expected_raw_text: str,
    energy_source: str = "nvml_total_energy",
    energy_integration_method: str = "total_energy_mj_delta",
    measurement_scope: str = "gpu_device_total_energy_counter",
    total_energy_supported: str = "true",
    power_semantics: str | None = None,
    elapsed_s: str = "10",
    e_before_mj: str = "1000",
    e_after_mj: str = "2000",
    delta_e_j: str = "1",
    idle_baseline_j: str = "0.1",
    net_e_j: str = "0.9",
    iter_count: str = "1000",
    omit_tensor_revision: bool = False,
    omit_cg_warmup_policy: bool = False,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as tmp:
        repo = Path(tmp)
        write_summary(repo, profile, "selftest", BASE_VALUES)
        write_audit(repo, profile, "selftest", stale=False, failing=False)
        write_raw_files(
            module,
            repo,
            profile,
            "selftest",
            energy_source=energy_source,
            energy_integration_method=energy_integration_method,
            measurement_scope=measurement_scope,
            total_energy_supported=total_energy_supported,
            power_semantics=power_semantics,
            elapsed_s=elapsed_s,
            e_before_mj=e_before_mj,
            e_after_mj=e_after_mj,
            delta_e_j=delta_e_j,
            idle_baseline_j=idle_baseline_j,
            net_e_j=net_e_j,
            iter_count=iter_count,
            omit_tensor_revision=omit_tensor_revision,
            omit_cg_warmup_policy=omit_cg_warmup_policy,
        )
        rows = module.audit_package(
            repo,
            profile,
            "selftest",
            expected_active_sm=PROFILE_ACTIVE_SM[profile],
            expected_sm_count=None,
        )
        assert_status(
            rows,
            "raw_present",
            "pass",
        )
        assert_status(
            rows,
            "raw_energy_power_policy",
            "fail",
            actual_contains=expected_raw_text,
        )
        print(f"{name}: ok")


def main() -> int:
    module = load_audit_module()
    run_case(
        module,
        name="good_minimal_strict_package",
        values=BASE_VALUES,
        stale_audit=False,
        failing_audit=False,
        expected_policy_status="pass",
        expected_audit_status="pass",
    )
    hierarchy_bad = dict(BASE_VALUES)
    hierarchy_bad["L2 CG hit path"] = ("0.10", "pJ/bit", "6")
    run_case(
        module,
        name="bad_hierarchy_and_stale_audit",
        values=hierarchy_bad,
        stale_audit=True,
        failing_audit=False,
        expected_policy_status="fail",
        expected_audit_status="fail",
        expected_policy_text="hierarchy:l2_not_greater_than_shared",
        expected_audit_text="missing_checks=",
    )
    plausibility_bad = dict(BASE_VALUES)
    plausibility_bad["Global L1 hit path"] = ("50", "pJ/bit", "6")
    plausibility_bad["L2 CG hit path"] = ("60", "pJ/bit", "6")
    run_case(
        module,
        name="bad_plausibility_and_failed_audit",
        values=plausibility_bad,
        stale_audit=False,
        failing_audit=True,
        expected_policy_status="fail",
        expected_audit_status="fail",
        expected_policy_text="plausibility",
        expected_audit_text="failures=3",
    )
    unexpected_component_bad = dict(BASE_VALUES)
    unexpected_component_bad["Register file direct"] = ("0.50", "pJ/bit", "0")
    run_case(
        module,
        name="bad_unexpected_strict_component",
        values=unexpected_component_bad,
        stale_audit=False,
        failing_audit=False,
        expected_policy_status="fail",
        expected_audit_status="pass",
        expected_policy_text="unexpected_components=Register file direct",
    )
    run_case(
        module,
        name="bad_strict_summary_missing_ncu_evidence",
        values=BASE_VALUES,
        stale_audit=False,
        failing_audit=False,
        expected_policy_status="fail",
        expected_audit_status="pass",
        expected_policy_text="missing_evidence_columns=ncu_path_evidence",
        omit_summary_column="ncu_path_evidence",
    )
    run_case(
        module,
        name="bad_a100_power_semantics",
        profile="a100",
        values=BASE_VALUES,
        stale_audit=False,
        failing_audit=False,
        expected_policy_status="fail",
        expected_audit_status="pass",
        expected_policy_text="semantics=one_sec_average",
        power_semantics="one_sec_average",
    )
    run_case(
        module,
        name="bad_fallback_energy_numerator",
        values=BASE_VALUES,
        stale_audit=False,
        failing_audit=False,
        expected_policy_status="fail",
        expected_audit_status="pass",
        expected_policy_text="energy_source=legacy_get_power_usage_integral",
        energy_source="legacy_get_power_usage_integral",
        energy_integration_method="endpoint_power_trapezoid",
        measurement_scope="gpu_device_power_usage_fallback",
    )
    run_preflight_case(
        module,
        name="good_preflight_metadata",
        profile="a100",
        expected_status="pass",
    )
    run_preflight_case(
        module,
        name="bad_preflight_missing_driver_version",
        profile="a100",
        omit_term="driver_version",
        expected_status="fail",
        expected_text="- `driver_version`:",
    )
    run_preflight_case(
        module,
        name="bad_preflight_missing_power_scope_query",
        profile="h100",
        omit_term="module_power_query_rc",
        expected_status="fail",
        expected_text="- `module_power_query_rc`:",
    )
    run_preflight_case(
        module,
        name="bad_preflight_missing_cuda_compiler_gate",
        profile="v100",
        omit_term="cuda_compiler_gate",
        expected_status="fail",
        expected_text="- `cuda_compiler_gate`: pass",
    )
    run_preflight_case(
        module,
        name="bad_preflight_not_strict",
        profile="a100",
        omit_term="- `strict`: true",
        append_terms=["- `strict`: false"],
        expected_status="fail",
        expected_text="- `strict`: true",
    )
    run_preflight_case(
        module,
        name="bad_preflight_overall_fail",
        profile="a100",
        omit_term="- `overall`: pass",
        append_terms=["- `overall`: fail"],
        expected_status="fail",
        expected_text="- `overall`: pass",
    )
    run_preflight_case(
        module,
        name="bad_preflight_errors_present",
        profile="a100",
        omit_term="- `errors`: none",
        append_terms=["- `errors`: profile_mismatch_requested_a100_detected_rtx3090"],
        expected_status="fail",
        expected_text="- `errors`: none",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_a100_power_semantics",
        profile="a100",
        power_semantics="one_sec_average",
        expected_raw_text="semantics=one_sec_average",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_fallback_energy_numerator",
        profile="rtx3090",
        energy_source="legacy_get_power_usage_integral",
        energy_integration_method="endpoint_power_trapezoid",
        measurement_scope="gpu_device_power_usage_fallback",
        total_energy_supported="false",
        expected_raw_text="energy_source=legacy_get_power_usage_integral",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_h100_module_scope",
        profile="h100",
        measurement_scope="module_power",
        expected_raw_text="scope=module_power",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_zero_delta_energy",
        profile="rtx3090",
        e_after_mj="1000",
        delta_e_j="0",
        net_e_j="0",
        expected_raw_text="delta_E_J=0",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_delta_counter_mismatch",
        profile="rtx3090",
        delta_e_j="2",
        expected_raw_text="delta_E_J_counter_mismatch",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_stale_tensor_kernel_revision",
        profile="a100",
        omit_tensor_revision=True,
        expected_raw_text="missing_tensor_kernel_revision",
    )
    run_raw_policy_case(
        module,
        name="bad_raw_missing_cg_warmup_policy",
        profile="a100",
        omit_cg_warmup_policy=True,
        expected_raw_text="missing_cg_warmup_policy",
    )
    run_power_api_case(
        module,
        name="good_power_api_final_candidate",
        profile="rtx3090",
        expected_status="pass",
    )
    run_power_api_case(
        module,
        name="bad_power_api_provisional_fallback",
        profile="rtx3090",
        status="provisional",
        energy_source="legacy_get_power_usage_integral",
        energy_integration_method="endpoint_power_trapezoid",
        measurement_scope="gpu_device_power_usage_fallback",
        expected_status="fail",
        expected_text="status=provisional",
    )
    run_power_api_case(
        module,
        name="bad_power_api_h100_module_scope",
        profile="h100",
        measurement_scope="module_power",
        expected_status="fail",
        expected_text="scope=module_power",
    )
    run_power_state_case(
        module,
        name="good_power_state_policy",
        profile="rtx3090",
        expected_status="pass",
    )
    run_power_state_case(
        module,
        name="bad_power_state_missing_average_power",
        profile="rtx3090",
        missing_column="average_power_W",
        expected_status="fail",
        expected_text="missing_columns=average_power_W",
    )
    run_power_state_case(
        module,
        name="bad_power_state_reject_row",
        profile="rtx3090",
        status="reject",
        coefficient_eligible="false",
        expected_status="fail",
        expected_text="reject",
    )
    run_power_state_case(
        module,
        name="bad_power_state_zero_average_power",
        profile="rtx3090",
        average_power_w="0",
        expected_status="fail",
        expected_text="average_power_W=0",
    )
    run_matched_summary_case(
        module,
        name="good_matched_summary_policy",
        profile="rtx3090",
        expected_status="pass",
    )
    run_matched_summary_case(
        module,
        name="bad_matched_summary_missing_l2",
        profile="rtx3090",
        missing_component="l2_hit_cg_path",
        expected_status="fail",
        expected_text="l2_hit_cg_path:missing",
    )
    run_matched_summary_case(
        module,
        name="bad_matched_summary_l1_without_ncu_rows",
        profile="rtx3090",
        zero_ncu_component="global_l1_hit_path",
        expected_status="fail",
        expected_text="global_l1_hit_path:ncu_denominator_rows=0",
    )
    run_matched_summary_case(
        module,
        name="bad_matched_summary_nonpositive_tensor",
        profile="rtx3090",
        nonpositive_median_component="tensor_mma_increment",
        expected_status="fail",
        expected_text="tensor_mma_increment:median=0",
    )
    run_l2_path_selection_case(
        module,
        name="good_a100_l2_path_selection",
        profile="a100",
        expected_status="pass",
        expected_text="selected=normal/sm_interleaved/8",
    )
    run_l2_path_selection_case(
        module,
        name="bad_a100_l2_path_not_selected",
        profile="a100",
        selected=False,
        expected_status="fail",
        expected_text="selected=none",
    )
    run_l2_path_selection_case(
        module,
        name="bad_v100_persisting_l2_selection",
        profile="v100",
        policy="persisting",
        expected_status="fail",
        expected_text="selected=persisting/sm_interleaved/16",
    )
    run_matched_detail_case(
        module,
        name="good_tensor_matched_iters_detail",
        profile="a100",
        expected_status="pass",
    )
    run_matched_detail_case(
        module,
        name="bad_legacy_inferred_pair_timing_detail",
        profile="a100",
        pair_timing_source="legacy_run_id_elapsed_inferred",
        expected_status="fail",
        expected_text="valid_pair_timing_source=legacy_run_id_elapsed_inferred",
    )
    run_matched_detail_case(
        module,
        name="bad_single_pair_execution_order_detail",
        profile="a100",
        include_reverse_order=False,
        expected_status="fail",
        expected_text="valid_pair_orders=control_then_treatment",
    )
    run_matched_detail_case(
        module,
        name="bad_pair_transition_gap_above_recorded_limit",
        profile="a100",
        pair_transition_gap_ms="35001",
        pair_transition_gap_limit_ms="35000",
        expected_status="fail",
        expected_text="valid_pair_transition_gap_ms=35001>35000",
    )
    run_matched_detail_case(
        module,
        name="bad_tensor_duration_scaled_detail",
        profile="a100",
        tensor_pair_energy_basis="duration_scaled_control_power",
        expected_status="fail",
        expected_text="pair_energy_basis=duration_scaled_control_power",
    )
    run_matched_detail_case(
        module,
        name="bad_tensor_iter_mismatch_detail",
        profile="a100",
        tensor_control_iters="900",
        expected_status="fail",
        expected_text="tensor_iters=1000/900",
    )
    run_matched_detail_case(
        module,
        name="bad_tensor_control_too_short_detail",
        profile="a100",
        tensor_control_elapsed_s="0.1",
        expected_status="fail",
        expected_text="control_elapsed_s=0.1",
    )
    run_matched_detail_case(
        module,
        name="bad_l2_duration_scaled_detail",
        profile="v100",
        l2_pair_energy_basis="duration_scaled_control_power",
        expected_status="fail",
        expected_text="pair_energy_basis=duration_scaled_control_power",
    )
    run_matched_detail_case(
        module,
        name="bad_l2_iter_mismatch_detail",
        profile="v100",
        l2_control_iters="2000",
        expected_status="fail",
        expected_text="l2_iters=1000/2000",
    )
    run_matched_detail_case(
        module,
        name="bad_dram_duration_scaled_detail",
        profile="a100",
        dram_pair_energy_basis="duration_scaled_control_power",
        expected_status="fail",
        expected_text="pair_energy_basis=duration_scaled_control_power",
    )
    run_matched_detail_case(
        module,
        name="bad_dram_iter_mismatch_detail",
        profile="a100",
        dram_control_iters="900",
        expected_status="fail",
        expected_text="dram_iters=1000/900",
    )
    run_tensor_pair_calibration_case(
        module,
        name="good_tensor_pair_calibration_manifest",
        expected_status="pass",
    )
    run_tensor_pair_calibration_case(
        module,
        name="bad_tensor_pair_raw_iter_mismatch",
        control_iters="900",
        expected_status="fail",
        expected_text="ITER_sets=[1000]/[900]",
    )
    run_tensor_pair_calibration_case(
        module,
        name="bad_tensor_pair_manifest_iter_mismatch",
        manifest_iters="900",
        expected_status="fail",
        expected_text="resolved=900:actual=1000",
    )
    run_tensor_pair_calibration_case(
        module,
        name="bad_tensor_pair_resolved_not_candidate_max",
        control_min_calibrated_iters="1200",
        expected_status="fail",
        expected_text="resolved_not_candidate_max=1000!=1200",
    )
    run_dram_pair_calibration_case(
        module,
        name="good_dram_pair_calibration_manifest",
        expected_status="pass",
    )
    run_dram_pair_calibration_case(
        module,
        name="bad_dram_pair_raw_iter_mismatch",
        control_iters="900",
        expected_status="fail",
        expected_text="ITER_sets=[900, 1000]",
    )
    run_l2_pair_calibration_case(
        module,
        name="good_l2_pair_calibration_manifest",
        expected_status="pass",
    )
    run_l2_pair_calibration_case(
        module,
        name="bad_l2_pair_raw_iter_mismatch",
        control_iters="2000",
        expected_status="fail",
        expected_text="ITER_sets=[1000, 2000]",
    )
    run_reliability_case(
        module,
        name="good_reliability_policy",
        profile="rtx3090",
        expected_status="pass",
    )
    run_reliability_case(
        module,
        name="bad_reliability_l1_with_caution",
        profile="rtx3090",
        status_override_component="global_l1_hit_path",
        expected_status="fail",
        expected_text="missing_accepted=global_l1_hit_path",
    )
    run_reliability_case(
        module,
        name="bad_reliability_invalid_detail_rows",
        profile="rtx3090",
        invalid_component="shared_l1_scalar_path",
        expected_status="fail",
        expected_text="shared_l1_scalar_path:invalid_detail_rows=1",
    )
    run_reliability_case(
        module,
        name="bad_reliability_l2_without_ncu_rows",
        profile="rtx3090",
        zero_ncu_component="l2_hit_cg_path",
        expected_status="fail",
        expected_text="l2_hit_cg_path:ncu_denominator_rows=0",
    )
    run_reliability_case(
        module,
        name="bad_reliability_h100_module_scope",
        profile="h100",
        measurement_scope="module_power",
        expected_status="fail",
        expected_text="scope=module_power",
    )
    run_ncu_summary_case(
        module,
        name="good_ncu_summary_schema",
        profile="rtx3090",
        expected_status="pass",
    )
    run_ncu_summary_case(
        module,
        name="good_a100_l2_path_specific_despite_aggregate_71pct",
        profile="a100",
        misleading_aggregate_l2=True,
        expected_status="pass",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_missing_l1_hit_rate",
        profile="rtx3090",
        missing_column="l1_hit_rate_pct",
        expected_status="fail",
        expected_text="missing_columns=l1_hit_rate_pct",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_zero_l2_path_bytes",
        profile="rtx3090",
        zero_l2_bytes=True,
        expected_status="fail",
        expected_text="l2_cg_load_only:l2_read_bytes=0",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_l1_low_hit_rate",
        profile="rtx3090",
        low_l1_hit=True,
        expected_status="fail",
        expected_text="global_l1_load_only:no_path_sanity_pass",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_l2_high_l1_traffic",
        profile="rtx3090",
        l2_high_l1_traffic=True,
        expected_status="fail",
        expected_text="l2_cg_load_only:no_path_sanity_pass",
    )
    run_ncu_summary_case(
        module,
        name="bad_a100_true_l2_path_hit_72pct",
        profile="a100",
        low_l2_path_hit=True,
        expected_status="fail",
        expected_text="l2_cg_load_only:no_path_sanity_pass",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_dram_high_l2_hit_rate",
        profile="rtx3090",
        dram_high_l2_hit=True,
        expected_status="fail",
        expected_text="dram_cg_load_only:no_path_sanity_pass",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_a100_wrong_active_sm",
        profile="a100",
        wrong_active_sm=True,
        expected_status="fail",
        expected_text="active_SM=82",
    )
    run_ncu_summary_case(
        module,
        name="bad_ncu_tensor_local_spill_bytes",
        profile="a100",
        local_spill=True,
        expected_status="fail",
        expected_text="reg_mma:no_path_sanity_pass",
    )
    run_ncu_acceptance_case(
        module,
        name="good_ncu_path_acceptance",
        profile="rtx3090",
        expected_status="pass",
    )
    run_ncu_acceptance_case(
        module,
        name="bad_ncu_missing_shared_candidate",
        profile="rtx3090",
        missing_candidate="shared_memory_path",
        expected_status="fail",
        expected_text="missing=shared_memory_path",
    )
    run_ncu_acceptance_case(
        module,
        name="bad_ncu_rejected_l2_candidate",
        profile="rtx3090",
        rejected_candidate="l2_hit_path",
        expected_status="fail",
        expected_text="rejected=l2_cg_load_only:l2_hit_path",
    )
    run_ncu_acceptance_case(
        module,
        name="bad_ncu_acceptance_missing_evidence_column",
        profile="rtx3090",
        missing_column="tensor_hmma_inst",
        expected_status="fail",
        expected_text="missing_columns=tensor_hmma_inst",
    )
    run_ncu_acceptance_case(
        module,
        name="bad_ncu_acceptance_l1_evidence_failure",
        profile="rtx3090",
        bad_l1_evidence=True,
        expected_status="fail",
        expected_text="global_l1_load_only:global_l1_hit_path:path_evidence_failed",
    )
    print("platform package gate self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
