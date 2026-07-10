#!/usr/bin/env python3
"""Audit the strict measurement-scope component summary.

This is a report-level gate. It verifies that the curated strict component
summary still agrees with the underlying reliability artifacts and that every
reported component uses the power API policy in
docs/platforms/power_measurement_api_matrix_ko.md:

  nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter.

It does not prove pure silicon-level energy and it does not run NCU.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import tempfile
from pathlib import Path


EXPECTED_COMPONENTS = {
    "Tensor MMA incremental": {
        "component_key": "tensor_mma_increment",
        "unit": "pJ/FLOP",
        "requires_ncu_denominator": False,
        "requires_ncu_acceptance": True,
    },
    "Shared scalar path": {
        "component_key": "shared_l1_scalar_path",
        "unit": "pJ/bit",
        "requires_ncu_denominator": True,
        "requires_ncu_acceptance": True,
    },
    "Global L1 hit path": {
        "component_key": "global_l1_hit_path",
        "unit": "pJ/bit",
        "requires_ncu_denominator": True,
        "requires_ncu_acceptance": True,
    },
    "L2 CG hit path": {
        "component_key": "l2_hit_cg_path",
        "unit": "pJ/bit",
        "requires_ncu_denominator": True,
        "requires_ncu_acceptance": True,
    },
}

ALLOWED_RUN_CLASSES = {
    "strict_explicit_measurement_scope",
    "strict_explicit_measurement_scope_fresh_ncu",
}

# Hard, intentionally broad plausibility ranges for effective board-level
# microbenchmark coefficients. These are not literature targets and do not
# prove silicon-level energy; they catch order-of-magnitude failures such as
# L1/L2 coefficients in the tens of pJ/bit caused by bad denominators, wrong
# path attribution, or broken power/source pairing.
HARD_PLAUSIBILITY_RANGES = {
    "Tensor MMA incremental": (0.001, 10.0, "pJ/FLOP"),
    "Shared scalar path": (0.001, 10.0, "pJ/bit"),
    "Global L1 hit path": (0.001, 10.0, "pJ/bit"),
    "L2 CG hit path": (0.01, 30.0, "pJ/bit"),
}

NCU_SUMMARY_REQUIRED_COLUMNS = {
    "mode",
    "status",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "store_repeat",
    "l1_hit_rate_pct",
    "l2_hit_rate_pct",
    "l1_accesses",
    "l2_accesses",
    "dram_accesses",
    "l1_bytes",
    "l2_bytes",
    "dram_bytes",
    "tensor_hmma_inst",
    "stall_long_scoreboard_pct",
}

NCU_SUMMARY_REQUIRED_MODES = {
    "Tensor MMA incremental": {"reg_mma", "reg_operand_only"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only"},
    "L2 CG hit path": {"l2_cg_load_only"},
}

NCU_COORDINATE_COLUMNS = [
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "store_repeat",
]

NCU_EXACT_COORDINATE_MODES = {
    "Tensor MMA incremental": {"reg_mma", "reg_operand_only"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only"},
    "L2 CG hit path": {"l2_cg_load_only"},
}

NCU_METRIC_MODES = {
    "Tensor MMA incremental": {"reg_mma"},
    "Shared scalar path": {"shared_scalar_load_only"},
    "Global L1 hit path": {"global_l1_load_only"},
    "L2 CG hit path": {"l2_cg_load_only"},
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
    "ncu_l2_hit_rate_pct_min_med_max",
    "ncu_l1_accesses_min_med_max",
    "ncu_l2_accesses_min_med_max",
    "ncu_dram_accesses_min_med_max",
    "ncu_l1_bytes_min_med_max",
    "ncu_l2_bytes_min_med_max",
    "ncu_dram_bytes_min_med_max",
    "ncu_tensor_hmma_inst_min_med_max",
    "ncu_spill_local_read_inst_min_med_max",
    "ncu_spill_local_write_inst_min_med_max",
    "ncu_stall_long_scoreboard_pct_min_med_max",
}

REQUIRED_SUMMARY_METRICS = {
    "Tensor MMA incremental": ["ncu_tensor_hmma_inst_min_med_max"],
    "Shared scalar path": ["ncu_shared_bytes_min_med_max"],
    "Global L1 hit path": [
        "ncu_l1_hit_rate_pct_min_med_max",
        "ncu_l1_bytes_min_med_max",
    ],
    "L2 CG hit path": [
        "ncu_l2_hit_rate_pct_min_med_max",
        "ncu_l2_bytes_min_med_max",
    ],
}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def path_exists(path_text: str) -> bool:
    return bool(path_text) and Path(path_text).exists()


def close_enough(left: float, right: float, rel_tol: float = 1.0e-6) -> bool:
    if not (math.isfinite(left) and math.isfinite(right)):
        return False
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) <= rel_tol * scale


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def detail_path_from_summary(path_text: str) -> Path:
    path = Path(path_text)
    name = path.name
    if "matched_control_summary" in name:
        return path.with_name(name.replace("matched_control_summary", "matched_control_detail"))
    if name.endswith("_summary.csv"):
        return path.with_name(name[: -len("_summary.csv")] + "_detail.csv")
    return path.with_name(path.stem + "_detail" + path.suffix)


def component_key_for(row: dict[str, str]) -> str:
    if row.get("component_key", ""):
        return row["component_key"]
    spec = EXPECTED_COMPONENTS.get(row.get("component", ""), {})
    return spec.get("component_key", row.get("component", ""))


def matched_summary_artifact(row: dict[str, str]) -> str:
    return row.get("summary_artifact", "") or row.get("matched_summary_artifact", "")


def matched_detail_artifact(row: dict[str, str]) -> str:
    return row.get("matched_detail_artifact", "")


def split_artifact_paths(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def normalize_coord(value: str) -> str:
    text = (value or "").strip()
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if not math.isfinite(number):
        return text
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def coord_key(mode: str, row: dict[str, str]) -> tuple[str, ...]:
    return (mode,) + tuple(normalize_coord(row.get(column, "")) for column in NCU_COORDINATE_COLUMNS)


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


def check_basic_row(
    checks: list[dict[str, str]],
    row: dict[str, str],
    *,
    expected_power_semantics: str,
    min_valid_rows: int,
) -> None:
    component = row.get("component", "")
    spec = EXPECTED_COMPONENTS.get(component, {})

    expected_pairs = {
        "unit": spec.get("unit", ""),
        "reliability_status": "accepted",
        "energy_source": "nvml_total_energy",
        "energy_integration_method": "total_energy_mj_delta",
        "measurement_scope": "gpu_device_total_energy_counter",
        "power_semantics": expected_power_semantics,
    }
    for key, expected in expected_pairs.items():
        if not expected:
            continue
        actual = row.get(key, "")
        add_check(
            checks,
            component=component,
            check=key,
            status="pass" if actual == expected else "fail",
            expected=expected,
            actual=actual,
            interpretation="strict summary row must satisfy the final power/API reporting policy",
        )

    run_class = row.get("run_class", "")
    add_check(
        checks,
        component=component,
        check="run_class",
        status="pass" if run_class in ALLOWED_RUN_CLASSES else "fail",
        expected=" or ".join(sorted(ALLOWED_RUN_CLASSES)),
        actual=run_class,
        interpretation="strict summary row must use an accepted measurement-scope run class",
    )

    median = as_float(row, "median")
    add_check(
        checks,
        component=component,
        check="positive_median",
        status="pass" if median > 0.0 else "fail",
        expected="median > 0",
        actual=f"{median:g}",
        interpretation="negative or zero median indicates weak-signal/control drift",
    )

    valid_rows = as_int(row, "valid_detail_rows")
    invalid_rows = as_int(row, "invalid_detail_rows")
    rows_used = as_int(row, "rows_used")
    add_check(
        checks,
        component=component,
        check="valid_rows",
        status="pass" if valid_rows >= min_valid_rows and rows_used == valid_rows else "fail",
        expected=f"valid_detail_rows >= {min_valid_rows} and rows_used == valid_detail_rows",
        actual=f"rows_used={rows_used}, valid_detail_rows={valid_rows}",
        interpretation="strict representative rows need enough valid matched-control samples",
    )
    add_check(
        checks,
        component=component,
        check="invalid_rows",
        status="pass" if invalid_rows == 0 else "fail",
        expected="invalid_detail_rows == 0",
        actual=str(invalid_rows),
        interpretation="accepted strict representatives must not hide invalid matched-control rows",
    )

    ncu_denominator_rows = as_int(row, "ncu_denominator_rows")
    ncu_accepted_rows = as_int(row, "ncu_accepted_rows")
    if spec.get("requires_ncu_denominator"):
        add_check(
            checks,
            component=component,
            check="ncu_denominator_rows",
            status="pass" if ncu_denominator_rows > 0 else "fail",
            expected="ncu_denominator_rows > 0",
            actual=str(ncu_denominator_rows),
            interpretation="memory pJ/bit rows must use NCU actual traffic denominators",
        )
    if spec.get("requires_ncu_acceptance"):
        add_check(
            checks,
            component=component,
            check="ncu_accepted_rows",
            status="pass" if ncu_accepted_rows > 0 else "fail",
            expected="ncu_accepted_rows > 0",
            actual=str(ncu_accepted_rows),
            interpretation="component path must have accepted NCU validation evidence",
        )

    artifact_checks = {
        "matched_summary_artifact": matched_summary_artifact(row),
        "matched_detail_artifact": matched_detail_artifact(row)
        or str(detail_path_from_summary(matched_summary_artifact(row))),
        "power_api_audit_artifact": row.get("power_api_audit_artifact", ""),
        "reliability_artifact": row.get("reliability_artifact", ""),
        "ncu_acceptance_artifact": row.get("ncu_acceptance_artifact", ""),
        "ncu_summary_artifact": row.get("ncu_summary_artifact", ""),
    }
    power_state = row.get("power_state_audit_artifact", "")
    if power_state:
        artifact_checks["power_state_audit_artifact"] = power_state
    instability = row.get("instability_artifact", "")
    if instability:
        artifact_checks["instability_artifact"] = instability
    for key, value in artifact_checks.items():
        missing_paths = [path for path in split_artifact_paths(value) if not path_exists(path)]
        add_check(
            checks,
            component=component,
            check=f"{key}_exists",
            status="pass" if value and not missing_paths else "fail",
            expected="path exists",
            actual=("missing" if not value else ";".join(missing_paths) if missing_paths else value),
            interpretation="strict summary must point to inspectable evidence artifacts",
        )


def check_ncu_summary_artifact(checks: list[dict[str, str]], row: dict[str, str]) -> None:
    component = row.get("component", "")
    paths = split_artifact_paths(row.get("ncu_summary_artifact", ""))
    if not paths:
        add_check(
            checks,
            component=component,
            check="ncu_summary_counter_schema",
            status="fail",
            expected="ncu_summary_artifact path with cache/access/stall counters",
            actual="missing",
            interpretation=(
                "strict summary must preserve NCU L1/L2 hit, L1/L2/DRAM access, "
                "byte, Tensor, and stall evidence"
            ),
        )
        return

    problems: list[str] = []
    rows_seen = 0
    modes_seen: set[str] = set()
    missing_files: list[str] = []
    for path in paths:
        if not path_exists(path):
            missing_files.append(path)
            continue
        with Path(path).open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = sorted(NCU_SUMMARY_REQUIRED_COLUMNS - fieldnames)
            if missing_columns:
                problems.append(f"{path}:missing_columns=" + ",".join(missing_columns))
                continue
            for ncu_row in reader:
                rows_seen += 1
                if ncu_row.get("status") != "ok":
                    continue
                mode = ncu_row.get("mode", "")
                modes_seen.add(mode)
                for column in NCU_SUMMARY_REQUIRED_COLUMNS - {"mode", "status"}:
                    value = as_float(ncu_row, column)
                    if not math.isfinite(value) or value < 0.0:
                        problems.append(f"{path}:{mode}:{column}={ncu_row.get(column, '')}")
                        break
    if missing_files:
        problems.append("missing_files=" + ",".join(missing_files))

    required_modes = NCU_SUMMARY_REQUIRED_MODES.get(component, set())
    missing_modes = sorted(required_modes - modes_seen)
    if missing_modes:
        problems.append("missing_modes=" + ",".join(missing_modes))

    add_check(
        checks,
        component=component,
        check="ncu_summary_counter_schema",
        status="pass" if rows_seen > 0 and not problems else "fail",
        expected=(
            "NCU summary artifact has hit-rate/access/byte/stall columns and "
            "component-relevant ok mode rows"
        ),
        actual=f"rows={rows_seen}, modes={len(modes_seen)}" if not problems else ";".join(problems[:8]),
        interpretation=(
            "reported coefficients must remain traceable to NCU cache hit rate, "
            "access count, byte traffic, Tensor instruction, and stall evidence"
        ),
    )


def check_ncu_summary_coordinate_alignment(
    checks: list[dict[str, str]], row: dict[str, str]
) -> None:
    component = row.get("component", "")
    component_key = component_key_for(row)
    exact_modes = NCU_EXACT_COORDINATE_MODES.get(component, set())
    if not exact_modes:
        return

    detail_artifact = matched_detail_artifact(row)
    detail_path = Path(detail_artifact) if detail_artifact else detail_path_from_summary(matched_summary_artifact(row))
    if not detail_path.exists():
        add_check(
            checks,
            component=component,
            check="ncu_summary_coordinate_alignment",
            status="fail",
            expected="matched-control detail artifact with strict energy coordinates",
            actual=str(detail_path),
            interpretation=(
                "NCU cache evidence must be collected at the same W_SM, blocks/SM, "
                "active SM, and factor coordinates as the strict energy rows"
            ),
        )
        return

    expected_coords: set[tuple[str, ...]] = set()
    for detail in read_csv(detail_path):
        if detail.get("component", "") != component_key:
            continue
        if not truthy(detail.get("valid_component_estimate", "")):
            continue
        if component == "Tensor MMA incremental":
            # Tensor uses an exact treatment-control pair. Both reg_mma and
            # reg_operand_only must have matching NCU sidecar rows for every RF.
            modes = {detail.get("numerator_mode", ""), detail.get("control_mode", "")}
        else:
            # For memory paths the clocked_empty control carries negligible
            # traffic and may be shared across W_SM labels. The treatment path
            # coordinate is the cache-path evidence that must match exactly.
            modes = {detail.get("numerator_mode", "")}
        for mode in modes & exact_modes:
            expected_coords.add(coord_key(mode, detail))

    ncu_coords: set[tuple[str, ...]] = set()
    missing_files: list[str] = []
    for path in split_artifact_paths(row.get("ncu_summary_artifact", "")):
        if not path_exists(path):
            missing_files.append(path)
            continue
        for ncu_row in read_csv(path):
            if ncu_row.get("status", "") != "ok":
                continue
            mode = ncu_row.get("mode", "")
            if mode in exact_modes:
                ncu_coords.add(coord_key(mode, ncu_row))

    missing_coords = sorted(expected_coords - ncu_coords)
    unexpected_exact_coords = sorted(ncu_coords - expected_coords)
    ok = bool(expected_coords) and not missing_files and not missing_coords
    actual_parts = [
        f"expected={len(expected_coords)}",
        f"matched={len(expected_coords - set(missing_coords))}",
    ]
    if missing_files:
        actual_parts.append("missing_files=" + ",".join(missing_files[:4]))
    if missing_coords:
        actual_parts.append(
            "missing="
            + ",".join(
                [
                    ":".join(coord)
                    for coord in missing_coords[:6]
                ]
            )
        )
    if unexpected_exact_coords:
        actual_parts.append(
            "extra_ncu_coords="
            + ",".join(
                [
                    ":".join(coord)
                    for coord in unexpected_exact_coords[:4]
                ]
            )
        )
    add_check(
        checks,
        component=component,
        check="ncu_summary_coordinate_alignment",
        status="pass" if ok else "fail",
        expected=(
            "component-relevant NCU ok rows match strict detail coordinates: "
            "mode,W_SM_KiB,blocks_per_SM,active_SM,reuse_factor,load_repeat,store_repeat"
        ),
        actual=";".join(actual_parts),
        interpretation=(
            "mode-level NCU validation is insufficient if the sidecar was collected "
            "with different occupancy, working-set, active-SM, or factor settings"
        ),
    )


def check_ncu_evidence_summary_fields(checks: list[dict[str, str]], row: dict[str, str]) -> None:
    component = row.get("component", "")
    spec = EXPECTED_COMPONENTS.get(component, {})
    missing_columns = sorted(
        column for column in STRICT_SUMMARY_NCU_EVIDENCE_COLUMNS if column not in row
    )
    problems: list[str] = []
    if missing_columns:
        problems.append("missing_columns=" + ",".join(missing_columns[:10]))
    else:
        coordinate_rows = as_int(row, "ncu_coordinate_rows")
        metric_rows = as_int(row, "ncu_metric_rows")
        if coordinate_rows <= 0:
            problems.append(f"ncu_coordinate_rows={row.get('ncu_coordinate_rows', '')}")
        if metric_rows <= 0:
            problems.append(f"ncu_metric_rows={row.get('ncu_metric_rows', '')}")

        evidence_modes = {
            item.strip()
            for item in row.get("ncu_evidence_modes", "").split(",")
            if item.strip()
        }
        expected_evidence_modes = NCU_EXACT_COORDINATE_MODES.get(component, set())
        missing_evidence_modes = sorted(expected_evidence_modes - evidence_modes)
        if missing_evidence_modes:
            problems.append("missing_evidence_modes=" + ",".join(missing_evidence_modes))

        metric_modes = {
            item.strip()
            for item in row.get("ncu_metric_modes", "").split(",")
            if item.strip()
        }
        expected_metric_modes = NCU_METRIC_MODES.get(component, set())
        missing_metric_modes = sorted(expected_metric_modes - metric_modes)
        if missing_metric_modes:
            problems.append("missing_metric_modes=" + ",".join(missing_metric_modes))

        required_metrics = REQUIRED_SUMMARY_METRICS.get(component, [])
        blank_metrics = [column for column in required_metrics if not row.get(column, "").strip()]
        if blank_metrics:
            problems.append("blank_metrics=" + ",".join(blank_metrics))
        for column in ("ncu_path_evidence", "ncu_counter_caveat"):
            if not row.get(column, "").strip():
                problems.append(f"{column}=blank")

        if spec.get("requires_ncu_denominator"):
            denominator_source = row.get("denominator_source", "")
            if "ncu_actual_exact" not in denominator_source.split(","):
                problems.append(f"denominator_source={denominator_source!r}")
            if not row.get("ncu_denominator_bytes_representative_min_med_max", "").strip():
                problems.append("ncu_denominator_bytes_representative_min_med_max=blank")

    add_check(
        checks,
        component=component,
        check="ncu_evidence_summary_fields",
        status="pass" if not problems else "fail",
        expected=(
            "strict summary row exposes same-coordinate NCU evidence rows, treatment "
            "metric rows, component-relevant counter summaries, and ncu_actual_exact "
            "denominator source for memory pJ/bit components"
        ),
        actual=(
            f"coordinate_rows={row.get('ncu_coordinate_rows', '')},"
            f"metric_rows={row.get('ncu_metric_rows', '')},"
            f"modes={row.get('ncu_evidence_modes', '')}"
            if not problems
            else ";".join(problems[:8])
        ),
        interpretation=(
            "a passing artifact path is not enough; the report table itself must "
            "surface the NCU hit/access/byte/stall evidence used to interpret each coefficient"
        ),
    )


def check_reliability_artifact(
    checks: list[dict[str, str]], row: dict[str, str], *, expected_power_semantics: str
) -> None:
    component = row.get("component", "")
    component_key = component_key_for(row)
    artifact = row.get("reliability_artifact", "")
    if not path_exists(artifact):
        return
    artifact_rows = read_csv(artifact)
    matching_rows = [item for item in artifact_rows if item.get("component", "") == component_key]
    if len(matching_rows) != 1:
        add_check(
            checks,
            component=component,
            check="reliability_artifact_row_count",
            status="fail",
            expected=f"1 row for {component_key}",
            actual=str(len(matching_rows)),
            interpretation="each strict representative should map to one reliability verdict",
        )
        return
    reliability = matching_rows[0]
    cross_checks = {
        "reliability_status": ("status", "accepted"),
        "unit": ("unit", row.get("unit", "")),
        "energy_source": ("energy_source", "nvml_total_energy"),
        "energy_integration_method": ("energy_integration_method", "total_energy_mj_delta"),
        "measurement_scope": ("measurement_scope", "gpu_device_total_energy_counter"),
        "power_semantics": ("power_semantics", expected_power_semantics),
    }
    for summary_key, (artifact_key, expected) in cross_checks.items():
        summary_value = row.get(summary_key, "")
        artifact_value = reliability.get(artifact_key, "")
        ok = summary_value == artifact_value == expected
        add_check(
            checks,
            component=component,
            check=f"artifact_matches_{summary_key}",
            status="pass" if ok else "fail",
            expected=f"summary and artifact both {expected}",
            actual=f"summary={summary_value}, artifact={artifact_value}",
            interpretation="curated strict summary must agree with reliability audit output",
        )

    summary_median = as_float(row, "median")
    artifact_median = as_float(reliability, "median")
    add_check(
        checks,
        component=component,
        check="artifact_matches_median",
        status="pass" if close_enough(summary_median, artifact_median) else "fail",
        expected=f"{summary_median:.12g}",
        actual=f"{artifact_median:.12g}",
        interpretation="reported median must be copied from the accepted reliability artifact",
    )

    for key in ["rows", "valid_detail_rows", "invalid_detail_rows", "ncu_denominator_rows"]:
        summary_key = "rows_used" if key == "rows" else key
        summary_value = as_int(row, summary_key)
        artifact_value = as_int(reliability, key)
        add_check(
            checks,
            component=component,
            check=f"artifact_matches_{key}",
            status="pass" if summary_value == artifact_value else "fail",
            expected=str(summary_value),
            actual=str(artifact_value),
            interpretation="row counts in strict summary must agree with reliability audit",
        )


def check_detail_artifact(
    checks: list[dict[str, str]],
    row: dict[str, str],
    *,
    expected_power_semantics: str,
) -> None:
    component = row.get("component", "")
    component_key = component_key_for(row)
    spec = EXPECTED_COMPONENTS.get(component, {})
    detail_artifact = matched_detail_artifact(row)
    if detail_artifact:
        detail_path = Path(detail_artifact)
    else:
        summary_artifact = matched_summary_artifact(row)
        detail_path = detail_path_from_summary(summary_artifact)
    if not detail_path.exists():
        add_check(
            checks,
            component=component,
            check="detail_artifact_exists",
            status="fail",
            expected="matched-control detail path exists",
            actual=str(detail_path),
            interpretation="strict summary must point to inspectable matched-control detail rows",
        )
        return
    add_check(
        checks,
        component=component,
        check="detail_artifact_exists",
        status="pass",
        expected="matched-control detail path exists",
        actual=str(detail_path),
        interpretation="strict summary has inspectable matched-control detail rows",
    )

    detail_rows = [
        detail
        for detail in read_csv(detail_path)
        if detail.get("component", "") == component_key
    ]
    valid_rows = [detail for detail in detail_rows if truthy(detail.get("valid_component_estimate", ""))]
    invalid_rows = [detail for detail in detail_rows if not truthy(detail.get("valid_component_estimate", ""))]
    summary_valid = as_int(row, "valid_detail_rows")
    summary_invalid = as_int(row, "invalid_detail_rows")

    add_check(
        checks,
        component=component,
        check="detail_valid_row_count_matches_summary",
        status="pass" if len(valid_rows) == summary_valid else "fail",
        expected=str(summary_valid),
        actual=str(len(valid_rows)),
        interpretation="strict summary valid row count must match matched-control detail",
    )
    add_check(
        checks,
        component=component,
        check="detail_invalid_row_count_matches_summary",
        status="pass" if len(invalid_rows) == summary_invalid else "fail",
        expected=str(summary_invalid),
        actual=str(len(invalid_rows)),
        interpretation="strict summary invalid row count must match matched-control detail",
    )

    bad_scope_rows = [
        detail
        for detail in detail_rows
        if detail.get("numerator_measurement_scope", "") != "gpu_device_total_energy_counter"
        or detail.get("control_measurement_scope", "") != "gpu_device_total_energy_counter"
    ]
    add_check(
        checks,
        component=component,
        check="detail_measurement_scope",
        status="pass" if not bad_scope_rows else "fail",
        expected="all numerator/control scopes are gpu_device_total_energy_counter",
        actual=f"bad_rows={len(bad_scope_rows)}",
        interpretation="matched-control detail rows must use the strict GPU/device energy scope",
    )

    bad_energy_rows = [
        detail
        for detail in detail_rows
        if detail.get("numerator_energy_source", "") != "nvml_total_energy"
        or detail.get("control_energy_source", "") != "nvml_total_energy"
        or detail.get("numerator_energy_integration_method", "") != "total_energy_mj_delta"
        or detail.get("control_energy_integration_method", "") != "total_energy_mj_delta"
    ]
    add_check(
        checks,
        component=component,
        check="detail_energy_source_and_integration",
        status="pass" if not bad_energy_rows else "fail",
        expected="all numerator/control rows use nvml_total_energy + total_energy_mj_delta",
        actual=f"bad_rows={len(bad_energy_rows)}",
        interpretation="matched-control detail rows must use the final energy numerator policy",
    )

    bad_semantics_rows = [
        detail
        for detail in detail_rows
        if detail.get("numerator_power_semantics", "") != expected_power_semantics
        or detail.get("control_power_semantics", "") != expected_power_semantics
    ]
    add_check(
        checks,
        component=component,
        check="detail_power_semantics",
        status="pass" if not bad_semantics_rows else "fail",
        expected=f"all numerator/control rows have {expected_power_semantics}",
        actual=f"bad_rows={len(bad_semantics_rows)}",
        interpretation="matched-control detail rows must match the target profile power semantics",
    )

    reject_power_state_rows = [
        detail
        for detail in detail_rows
        if detail.get("numerator_power_state_status", "") == "reject"
        or detail.get("control_power_state_status", "") == "reject"
    ]
    power_state_statuses: dict[str, int] = {}
    for detail in detail_rows:
        for key in ["numerator_power_state_status", "control_power_state_status"]:
            status = detail.get(key, "")
            if status:
                power_state_statuses[status] = power_state_statuses.get(status, 0) + 1
    actual_power_state = ",".join(
        f"{status}:{count}" for status, count in sorted(power_state_statuses.items())
    )
    add_check(
        checks,
        component=component,
        check="detail_power_state_no_reject",
        status="pass" if not reject_power_state_rows else "fail",
        expected="no numerator/control power-state reject rows",
        actual=actual_power_state or "none",
        interpretation=(
            "power-state caution is traceability metadata; reject rows must not back "
            "strict representatives"
        ),
    )

    power_state_artifacts = split_artifact_paths(row.get("power_state_audit_artifact", ""))
    power_state_by_run_id: dict[str, dict[str, str]] = {}
    duplicate_power_state_run_ids: set[str] = set()
    missing_power_state_files: list[str] = []
    for artifact in power_state_artifacts:
        if not path_exists(artifact):
            missing_power_state_files.append(artifact)
            continue
        for audit_row in read_csv(artifact):
            run_id = audit_row.get("run_id", "")
            if not run_id:
                continue
            if run_id in power_state_by_run_id:
                duplicate_power_state_run_ids.add(run_id)
            power_state_by_run_id[run_id] = audit_row

    required_power_state_pairs: list[tuple[str, str]] = []
    for detail in detail_rows:
        required_power_state_pairs.append(
            (detail.get("numerator_run_id", ""), detail.get("numerator_power_state_status", ""))
        )
        required_power_state_pairs.append(
            (detail.get("control_run_id", ""), detail.get("control_power_state_status", ""))
        )
    missing_power_state_run_ids = sorted(
        {
            run_id
            for run_id, _ in required_power_state_pairs
            if run_id and run_id not in power_state_by_run_id
        }
    )
    mismatched_power_state_status = sorted(
        {
            f"{run_id}:{expected}!={power_state_by_run_id.get(run_id, {}).get('status', '')}"
            for run_id, expected in required_power_state_pairs
            if run_id
            and expected
            and run_id in power_state_by_run_id
            and power_state_by_run_id[run_id].get("status", "") != expected
        }
    )
    power_state_coverage_ok = (
        bool(power_state_artifacts)
        and not missing_power_state_files
        and not missing_power_state_run_ids
        and not mismatched_power_state_status
    )
    power_state_actual_parts = [
        f"artifacts={len(power_state_artifacts)}",
        f"covered_run_ids={len(power_state_by_run_id)}",
    ]
    if missing_power_state_files:
        power_state_actual_parts.append("missing_files=" + ",".join(missing_power_state_files[:4]))
    if missing_power_state_run_ids:
        power_state_actual_parts.append(
            "missing_run_ids=" + ",".join(missing_power_state_run_ids[:4])
        )
    if mismatched_power_state_status:
        power_state_actual_parts.append(
            "status_mismatch=" + ",".join(mismatched_power_state_status[:4])
        )
    if duplicate_power_state_run_ids:
        power_state_actual_parts.append(
            "duplicate_run_ids=" + ",".join(sorted(duplicate_power_state_run_ids)[:4])
        )
    add_check(
        checks,
        component=component,
        check="power_state_artifact_covers_detail_run_ids",
        status="pass" if power_state_coverage_ok else "fail",
        expected="power-state audit artifacts cover every numerator/control run_id in detail",
        actual=";".join(power_state_actual_parts),
        interpretation=(
            "strict package must trace each accepted matched-control row back to "
            "row-level power-state quality evidence"
        ),
    )

    missing_source_files = [
        detail
        for detail in detail_rows
        if not path_exists(detail.get("source_file", ""))
    ]
    add_check(
        checks,
        component=component,
        check="detail_source_files_exist",
        status="pass" if not missing_source_files else "fail",
        expected="all raw source files exist",
        actual=f"missing_rows={len(missing_source_files)}",
        interpretation="matched-control detail must remain traceable to raw energy CSVs",
    )

    if spec.get("requires_ncu_denominator"):
        bad_denominator_rows = [
            detail
            for detail in detail_rows
            if detail.get("denominator_source", "") != "ncu_actual_exact"
            or as_float(detail, "ncu_denominator_bytes_representative") <= 0.0
        ]
        add_check(
            checks,
            component=component,
            check="detail_ncu_denominator_exact",
            status="pass" if not bad_denominator_rows else "fail",
            expected="all memory detail rows use ncu_actual_exact with positive NCU bytes",
            actual=f"bad_rows={len(bad_denominator_rows)}",
            interpretation="memory pJ/bit denominators must come from exact NCU traffic matches",
        )
        detail_median = median(
            [as_float(detail, "coefficient_pJ_per_bit") for detail in valid_rows]
        )
    else:
        detail_median = median([as_float(detail, "coefficient") for detail in valid_rows])

    summary_median = as_float(row, "median")
    add_check(
        checks,
        component=component,
        check="detail_median_matches_summary",
        status="pass" if close_enough(summary_median, detail_median) else "fail",
        expected=f"{summary_median:.12g}",
        actual=f"{detail_median:.12g}",
        interpretation="strict median must match the median of valid matched-control detail rows",
    )


def check_power_api_artifact(
    checks: list[dict[str, str]],
    row: dict[str, str],
    *,
    expected_power_semantics: str,
) -> None:
    component = row.get("component", "")
    artifact_value = row.get("power_api_audit_artifact", "")
    paths = split_artifact_paths(artifact_value)
    if not paths:
        add_check(
            checks,
            component=component,
            check="power_api_audit_artifact_present",
            status="fail",
            expected="power API audit artifact path",
            actual="missing",
            interpretation="strict package must preserve the numerator policy audit artifact",
        )
        return

    problems: list[str] = []
    rows_seen = 0
    for path in paths:
        if not path_exists(path):
            problems.append(f"{path}:missing")
            continue
        for audit_row in read_csv(path):
            rows_seen += 1
            status = audit_row.get("status", "")
            if status != "final_candidate":
                problems.append(f"{path}:status={status}")
            if audit_row.get("energy_source", "") != "nvml_total_energy":
                problems.append(f"{path}:energy_source={audit_row.get('energy_source', '')}")
            if audit_row.get("energy_integration_method", "") != "total_energy_mj_delta":
                problems.append(
                    f"{path}:integration={audit_row.get('energy_integration_method', '')}"
                )
            if audit_row.get("measurement_scope", "") != "gpu_device_total_energy_counter":
                problems.append(f"{path}:scope={audit_row.get('measurement_scope', '')}")
            if audit_row.get("actual_power_semantics", "") != expected_power_semantics:
                problems.append(
                    f"{path}:semantics={audit_row.get('actual_power_semantics', '')}"
                )

    add_check(
        checks,
        component=component,
        check="power_api_audit_final_rows",
        status="pass" if rows_seen > 0 and not problems else "fail",
        expected=(
            "all power API audit rows are final_candidate with total-energy delta, "
            "GPU/device scope, and expected semantics"
        ),
        actual=f"rows={rows_seen}" if not problems else ";".join(problems[:8]),
        interpretation=(
            "strict package must keep the power measurement matrix gate traceable, "
            "not just the final copied coefficients"
        ),
    )


def check_hierarchy(checks: list[dict[str, str]], rows_by_component: dict[str, dict[str, str]]) -> None:
    values = {
        component: as_float(row, "median")
        for component, row in rows_by_component.items()
        if row.get("unit") == "pJ/bit"
    }
    shared = values.get("Shared scalar path")
    l1 = values.get("Global L1 hit path")
    l2 = values.get("L2 CG hit path")
    if math.isfinite(l2) and math.isfinite(shared):
        add_check(
            checks,
            component="hierarchy",
            check="l2_greater_than_shared",
            status="pass" if l2 > shared else "fail",
            expected="L2 median > Shared median",
            actual=f"L2={l2:g}, Shared={shared:g}",
            interpretation="strict results should preserve the broad hierarchy order",
        )
    if math.isfinite(l2) and math.isfinite(l1):
        add_check(
            checks,
            component="hierarchy",
            check="l2_greater_than_l1",
            status="pass" if l2 > l1 else "fail",
            expected="L2 median > L1 median",
            actual=f"L2={l2:g}, L1={l1:g}",
            interpretation="strict results should preserve the broad hierarchy order",
        )
    if math.isfinite(shared) and math.isfinite(l1):
        ratio = max(shared, l1) / max(min(shared, l1), 1.0e-30)
        add_check(
            checks,
            component="hierarchy",
            check="shared_l1_same_order",
            status="pass" if ratio <= 2.0 else "warning",
            expected="max(shared,L1)/min(shared,L1) <= 2",
            actual=f"{ratio:g}",
            interpretation="shared scalar and global L1 are different paths but should be same-order",
        )


def check_plausibility_ranges(
    checks: list[dict[str, str]], rows_by_component: dict[str, dict[str, str]]
) -> None:
    for component, (lo, hi, unit) in HARD_PLAUSIBILITY_RANGES.items():
        row = rows_by_component.get(component)
        if not row:
            continue
        median_value = as_float(row, "median")
        actual_unit = row.get("unit", "")
        ok = lo <= median_value <= hi and actual_unit == unit
        add_check(
            checks,
            component=component,
            check="hard_plausibility_range",
            status="pass" if ok else "fail",
            expected=f"{lo:g} <= median <= {hi:g} {unit}",
            actual=f"median={median_value:g} {actual_unit}",
            interpretation=(
                "broad order-of-magnitude gate for effective coefficients; "
                "failure usually means unit, NCU denominator, power source, or path attribution "
                "must be rechecked before reporting"
            ),
        )


def audit(
    summary_csv: str,
    *,
    expected_power_semantics: str,
    min_valid_rows: int,
) -> list[dict[str, str]]:
    if not Path(summary_csv).exists():
        return [
            {
                "component": "strict_summary_package",
                "check": "summary_artifact_exists",
                "status": "fail",
                "expected": "strict component summary CSV exists",
                "actual": summary_csv,
                "interpretation": (
                    "strict summary build did not produce an artifact; inspect the "
                    "reliability and NCU acceptance reports before treating any "
                    "component coefficient as final"
                ),
            }
        ]
    rows = read_csv(summary_csv)
    rows_by_component = {row.get("component", ""): row for row in rows}
    checks: list[dict[str, str]] = []

    for component in EXPECTED_COMPONENTS:
        if component not in rows_by_component:
            add_check(
                checks,
                component=component,
                check="required_component_present",
                status="fail",
                expected="row present",
                actual="missing",
                interpretation="strict summary is missing a required component",
            )
            continue
        add_check(
            checks,
            component=component,
            check="required_component_present",
            status="pass",
            expected="row present",
            actual="present",
            interpretation="strict summary includes the required component",
        )
        row = rows_by_component[component]
        check_basic_row(
            checks,
            row,
            expected_power_semantics=expected_power_semantics,
            min_valid_rows=min_valid_rows,
        )
        check_reliability_artifact(
            checks,
            row,
            expected_power_semantics=expected_power_semantics,
        )
        check_detail_artifact(
            checks,
            row,
            expected_power_semantics=expected_power_semantics,
        )
        check_power_api_artifact(
            checks,
            row,
            expected_power_semantics=expected_power_semantics,
        )
        check_ncu_summary_artifact(checks, row)
        check_ncu_summary_coordinate_alignment(checks, row)
        check_ncu_evidence_summary_fields(checks, row)

    unexpected = sorted(set(rows_by_component) - set(EXPECTED_COMPONENTS))
    for component in unexpected:
        add_check(
            checks,
            component=component,
            check="unexpected_component",
            status="fail",
            expected="only Tensor/Shared/L1/L2 strict components",
            actual=component,
            interpretation=(
                "strict reporting must not promote register, DRAM, or diagnostic "
                "rows to final component coefficients"
            ),
        )

    check_hierarchy(checks, rows_by_component)
    check_plausibility_ranges(checks, rows_by_component)
    return checks


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "component",
        "check",
        "status",
        "expected",
        "actual",
        "interpretation",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: str, rows: list[dict[str, str]], *, summary_csv: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    with out.open("w", encoding="utf-8") as f:
        f.write("# Strict Component Summary Audit\n\n")
        f.write(
            "This audit verifies the curated strict measurement-scope summary against "
            "its reliability artifacts. It is a reporting consistency gate, not a "
            "silicon-level energy proof and not a fresh NCU replay.\n\n"
        )
        f.write(f"- strict summary: `{summary_csv}`\n\n")
        f.write("## Status Counts\n\n")
        f.write("| status | checks |\n|---|---:|\n")
        for status in sorted(counts):
            f.write(f"| `{status}` | {counts[status]} |\n")
        f.write("\n## Checks\n\n")
        f.write("| component | check | status | expected | actual | interpretation |\n")
        f.write("|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                "| "
                + " | ".join(
                    [
                        row["component"],
                        row["check"],
                        f"`{row['status']}`",
                        row["expected"],
                        row["actual"],
                        row["interpretation"],
                    ]
                )
                + " |\n"
            )


def write_selftest_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_ncu_selftest_row(
    *,
    mode: str,
    w_sm_kib: str = "2048",
    blocks_per_sm: str = "16",
    active_sm: str = "82",
    reuse_factor: str = "8",
    load_repeat: str = "1",
    store_repeat: str = "1",
) -> dict[str, str]:
    row = {column: "0" for column in NCU_SUMMARY_REQUIRED_COLUMNS}
    row.update(
        {
            "mode": mode,
            "status": "ok",
            "W_SM_KiB": w_sm_kib,
            "blocks_per_SM": blocks_per_sm,
            "active_SM": active_sm,
            "reuse_factor": reuse_factor,
            "load_repeat": load_repeat,
            "store_repeat": store_repeat,
            "tensor_hmma_inst": "1024" if mode == "reg_mma" else "0",
            "l1_hit_rate_pct": "0",
            "l2_hit_rate_pct": "0",
            "l1_accesses": "1",
            "l2_accesses": "1",
            "dram_accesses": "0",
            "l1_bytes": "128",
            "l2_bytes": "128",
            "dram_bytes": "0",
            "stall_long_scoreboard_pct": "0",
        }
    )
    return row


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        detail = root / "matched_control_detail.csv"
        ncu_good = root / "ncu_good.csv"
        ncu_bad = root / "ncu_bad.csv"
        detail_fields = [
            "component",
            "valid_component_estimate",
            "numerator_mode",
            "control_mode",
            *NCU_COORDINATE_COLUMNS,
        ]
        write_selftest_csv(
            detail,
            detail_fields,
            [
                {
                    "component": "tensor_mma_increment",
                    "valid_component_estimate": "True",
                    "numerator_mode": "reg_mma",
                    "control_mode": "reg_operand_only",
                    "W_SM_KiB": "2048",
                    "blocks_per_SM": "16",
                    "active_SM": "82",
                    "reuse_factor": "8",
                    "load_repeat": "1",
                    "store_repeat": "1",
                }
            ],
        )
        ncu_fields = sorted(NCU_SUMMARY_REQUIRED_COLUMNS)
        write_selftest_csv(
            ncu_good,
            ncu_fields,
            [
                make_ncu_selftest_row(mode="reg_mma"),
                make_ncu_selftest_row(mode="reg_operand_only"),
                make_ncu_selftest_row(mode="reg_mma", blocks_per_sm="4"),
            ],
        )
        write_selftest_csv(
            ncu_bad,
            ncu_fields,
            [
                make_ncu_selftest_row(mode="reg_mma", blocks_per_sm="4"),
                make_ncu_selftest_row(mode="reg_operand_only", blocks_per_sm="4"),
            ],
        )
        row = {
            "component": "Tensor MMA incremental",
            "component_key": "tensor_mma_increment",
            "matched_detail_artifact": str(detail),
        }

        good_checks: list[dict[str, str]] = []
        check_ncu_summary_coordinate_alignment(
            good_checks, {**row, "ncu_summary_artifact": str(ncu_good)}
        )
        if len(good_checks) != 1 or good_checks[0]["status"] != "pass":
            raise AssertionError(f"expected coordinate pass, got {good_checks}")
        if "extra_ncu_coords=" not in good_checks[0]["actual"]:
            raise AssertionError("expected extra NCU coordinate to be reported without failing")

        bad_checks: list[dict[str, str]] = []
        check_ncu_summary_coordinate_alignment(
            bad_checks, {**row, "ncu_summary_artifact": str(ncu_bad)}
        )
        if len(bad_checks) != 1 or bad_checks[0]["status"] != "fail":
            raise AssertionError(f"expected coordinate fail, got {bad_checks}")
        if "missing=" not in bad_checks[0]["actual"]:
            raise AssertionError("expected missing strict coordinate evidence in failure output")
    print("strict component summary audit self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--summary-csv",
        default=(
            "results/summary/"
            "rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.csv"
        ),
    )
    parser.add_argument(
        "--expected-power-semantics",
        default="one_sec_average",
    )
    parser.add_argument("--min-valid-rows", type=int, default=6)
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--fail-on-fail", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    if not args.out_csv or not args.out_md:
        parser.error("--out-csv and --out-md are required unless --self-test is used")

    rows = audit(
        args.summary_csv,
        expected_power_semantics=args.expected_power_semantics,
        min_valid_rows=args.min_valid_rows,
    )
    write_csv(args.out_csv, rows)
    write_md(args.out_md, rows, summary_csv=args.summary_csv)
    failures = sum(1 for row in rows if row["status"] == "fail")
    warnings = sum(1 for row in rows if row["status"] == "warning")
    print(f"strict summary audit checks={len(rows)} failures={failures} warnings={warnings}")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    if args.fail_on_fail and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
