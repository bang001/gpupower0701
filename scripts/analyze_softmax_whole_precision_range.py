#!/usr/bin/env python3
"""Fail-closed analysis for complete-Softmax precision range runs.

This analyzer reports an *observed, predeclared-envelope* range rather than a
universal hardware constant.  It keeps the three complete endpoint policies
separate, fixes S=1024/q50 as the selection-free representative coordinate,
and emits a small adaptive follow-up plan instead of expanding a factorial
CTA/S sweep.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from softmax_platform_profiles import PLATFORM_PROFILES


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "softmax_whole_precision_range_manifest_v1"
ANALYSIS_SCHEMA = "softmax_whole_precision_range_analysis_v1"
RAW_SCHEMA = "softmax_whole_precision_range_v1"
EXPERIMENT_KIND = "whole_softmax_precision_range"
PROTOCOL_REVISION = "whole_softmax_precision_range_common_v1"
DESIGN_ID = "whole_precision_range_v1"
METRIC = "net_pJ_per_logical_output_element"
# The shared C++ result writer predates this range protocol and serializes the
# numerator-normalized value under the shorter ``...per_output_element`` name.
# The range analyzer proves that the denominator is exactly
# ``logical_output_elements`` before promoting it to the explicit primary
# metric above; do not require a fictitious second raw column.
RAW_METRIC_FIELD = "net_pJ_per_output_element"
PREHEAT_REQUESTED_S = 5.0
PREHEAT_MIN_S = 3.75
PREHEAT_MAX_S = 6.25
TRACE_MIN_UPDATES = 16
TRACE_MIN_R2 = 0.98
PRACTICAL_DIFFERENCE = 0.10
T95_N3 = 4.302652729911275

POLICIES = (
    "fp32_io_fp32_all",
    "fp16_scalar_all",
    "fp16x2_all",
)
POLICY_CONTRACT = {
    "fp32_io_fp32_all": ("fp32", "fp32", "fp32", "fp32", "fp32"),
    "fp16_scalar_all": ("fp16", "fp16", "fp16_scalar", "fp16_scalar", "fp16_scalar"),
    "fp16x2_all": ("fp16", "fp16", "fp16x2_packed", "fp16x2_packed", "fp16x2_packed"),
}
POLICY_IDS = {
    "fp32_io_fp32_all": 0,
    "fp16_scalar_all": 8,
    "fp16x2_all": 9,
}
SASS_AUDIT_SCHEMA = "softmax_whole_precision_range_static_audit_v1"

# Keep the acquisition envelope in the verifier as well as the runner.  The
# manifest is evidence, not authority to redefine the predeclared screen: an
# edited coordinate label must not silently change the S/q point it denotes.
COORDINATE_CONTRACT: dict[str, tuple[int, float]] = {
    "s512_q50": (512, 0.50),
    "s1024_q50": (1024, 0.50),
    "s4096_q50": (4096, 0.50),
    "s1024_q25": (1024, 0.25),
    "s2048_q50": (2048, 0.50),
    "s512_q25": (512, 0.25),
    "s4096_q25": (4096, 0.25),
}
SCREEN_COORDINATES = ("s512_q50", "s1024_q50", "s4096_q50", "s1024_q25")
FOLLOWUP_COORDINATES = frozenset(COORDINATE_CONTRACT) - frozenset(SCREEN_COORDINATES)
REPETITIONS = 3


class EvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Cell:
    profile: str
    coordinate_id: str
    policy: str
    session_id: str
    session_index: int
    session_order: str
    run_id: str
    softmax_cols: int
    grid_blocks: int
    runtime_sm_count: int
    requested_sm_coverage: float
    grid_sm_coverage: float
    occupancy: int
    static_capacity: int
    logical_elements: int
    net_pj: float
    gross_pj: float
    elapsed_s: float
    preheat_s: float
    trace_r2: float
    trace_updates: int
    temp_before_c: int
    temp_after_c: int
    validation_abs_error: float
    validation_row_sum_error: float


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"JSON root must be an object: {path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise EvidenceError(f"cannot read CSV {path}: {error}") from error
    require(bool(rows), f"CSV has no rows: {path}")
    require(all(None not in row for row in rows), f"CSV is malformed: {path}")
    return rows


def number(row: Mapping[str, Any], field: str, label: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError(f"{label}: {field} is not numeric") from error
    require(math.isfinite(value), f"{label}: {field} is not finite")
    return value


def integer(row: Mapping[str, Any], field: str, label: str) -> int:
    try:
        value = int(str(row[field]))
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError(f"{label}: {field} is not an integer") from error
    return value


def boolean(row: Mapping[str, Any], field: str, label: str) -> bool:
    value = str(row.get(field, "")).lower()
    require(value in {"true", "false"}, f"{label}: {field} is not boolean")
    return value == "true"


def close(left: float, right: float, label: str, tolerance: float = 1e-6) -> None:
    require(math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance),
            f"{label}: {left} != {right}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), f"refusing to write empty CSV: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def policy_contract_ok(row: Mapping[str, str], policy: str, label: str) -> None:
    expected = POLICY_CONTRACT[policy]
    actual = tuple(row.get(field, "") for field in (
        "input_dtype", "output_dtype", "exp_stage", "reduction_stage", "normalization_stage"
    ))
    require(actual == expected, f"{label}: endpoint policy contract drifted: {actual} != {expected}")


def validate_trace(trace_rows: list[dict[str, str]], run_id: str, expected_count: int, label: str) -> None:
    selected = [row for row in trace_rows if row.get("run_id") == run_id]
    require(len(selected) == expected_count,
            f"{label}: trace sample count {len(selected)} != raw metadata {expected_count}")
    for row in selected:
        require(math.isfinite(number(row, "energy_mJ", label)), f"{label}: invalid trace energy")


def required_policies(profile_name: str) -> tuple[str, ...]:
    return ("fp32_io_fp32_all",) if profile_name == "v100" else POLICIES


def expected_policy_schedule(session_order: str, profile_name: str) -> tuple[str, ...]:
    """Return the sole legal persistent schedule for one fresh process."""

    if profile_name == "v100":
        require(session_order == "A", "V100 session order must be A")
        return ("fp32_io_fp32_all",)
    schedules = {
        "ABC": POLICIES,
        "BCA": (POLICIES[1], POLICIES[2], POLICIES[0]),
        "CAB": (POLICIES[2], POLICIES[0], POLICIES[1]),
    }
    require(session_order in schedules,
            f"three-endpoint session order is invalid: {session_order}")
    return schedules[session_order]


def grid_blocks_for_coverage(runtime_sm_count: int, coverage: float) -> int:
    require(runtime_sm_count > 0 and 0.0 < coverage <= 1.0,
            "invalid planned runtime SM count or coverage")
    return max(1, math.ceil(runtime_sm_count * coverage))


def validate_coordinate_plan(
    manifest: Mapping[str, Any], profile_name: str
) -> dict[str, tuple[int, float]]:
    """Fail closed on phase, coordinate, and order-plan drift.

    The runner intentionally allows a human-readable manifest, but the
    analysis must not let that artifact grow the experimental envelope after
    results are visible.  This validation also makes q a real, predefined
    coverage coordinate rather than a free-form CSV field.
    """

    phase = manifest.get("phase")
    require(phase in {"screen", "followup", "confirmation"},
            "manifest phase is invalid")
    coordinates = manifest.get("coordinates")
    require(isinstance(coordinates, list) and coordinates,
            "manifest coordinates are missing")
    identifiers: list[str] = []
    result: dict[str, tuple[int, float]] = {}
    for index, item in enumerate(coordinates):
        require(isinstance(item, dict), f"coordinate {index}: invalid object")
        identifier = item.get("identifier")
        require(isinstance(identifier, str) and identifier in COORDINATE_CONTRACT,
                f"coordinate {index}: unknown coordinate identifier")
        require(identifier not in result,
                f"coordinate {identifier}: repeated in manifest")
        try:
            softmax_cols = int(item.get("softmax_cols"))
        except (TypeError, ValueError) as error:
            raise EvidenceError(f"coordinate {identifier}: softmax_cols is invalid") from error
        coverage = number(item, "sm_coverage", f"coordinate {identifier}")
        expected_cols, expected_coverage = COORDINATE_CONTRACT[identifier]
        require(softmax_cols == expected_cols,
                f"coordinate {identifier}: softmax_cols differs from the fixed range contract")
        close(coverage, expected_coverage,
              f"coordinate {identifier}: SM coverage differs from the fixed range contract")
        identifiers.append(identifier)
        result[identifier] = (softmax_cols, coverage)

    if phase == "screen":
        require(tuple(identifiers) == SCREEN_COORDINATES,
                "initial screen coordinates/order differ from the predeclared four-coordinate design")
    elif phase == "followup":
        require(set(identifiers).issubset(FOLLOWUP_COORDINATES),
                "followup contains an initial-screen or undeclared coordinate")

    profile = manifest.get("profile")
    require(isinstance(profile, dict), "manifest profile is invalid")
    runtime_sm_planned = profile.get("runtime_sm_count_planned")
    try:
        runtime_sm_planned = int(runtime_sm_planned)
    except (TypeError, ValueError) as error:
        raise EvidenceError("manifest planned runtime SM count is invalid") from error
    expected_profile = PLATFORM_PROFILES[profile_name]
    require(runtime_sm_planned in expected_profile.full_sm_counts,
            "manifest planned SM count is not a complete-device value for the profile")

    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and sessions,
            "manifest sessions are missing")
    require(len(sessions) == len(result) * REPETITIONS,
            "manifest session count does not equal three fresh sessions per coordinate")
    global_indices: list[int] = []
    by_coordinate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for position, session in enumerate(sessions, start=1):
        require(isinstance(session, dict), f"manifest session {position}: invalid object")
        identifier = session.get("coordinate_id")
        require(isinstance(identifier, str) and identifier in result,
                f"manifest session {position}: coordinate is not declared")
        by_coordinate[identifier].append(session)
        try:
            global_index = int(session.get("global_session_index"))
            session_index = int(session.get("session_index_within_coordinate"))
            runtime_sm = int(session.get("runtime_sm_count"))
            softmax_cols = int(session.get("softmax_cols"))
            grid_blocks = int(session.get("grid_blocks"))
        except (TypeError, ValueError) as error:
            raise EvidenceError(f"manifest session {position}: integer plan metadata is invalid") from error
        global_indices.append(global_index)
        expected_cols, expected_coverage = result[identifier]
        require(softmax_cols == expected_cols,
                f"manifest session {position}: S differs from coordinate contract")
        close(number(session, "requested_sm_coverage", f"manifest session {position}"),
              expected_coverage,
              f"manifest session {position}: q differs from coordinate contract")
        require(runtime_sm == runtime_sm_planned,
                f"manifest session {position}: runtime SM count differs from planned profile value")
        require(grid_blocks == grid_blocks_for_coverage(runtime_sm, expected_coverage),
                f"manifest session {position}: grid does not match the q coverage rule")
        schedule = session.get("policy_schedule")
        require(isinstance(schedule, list) and all(isinstance(item, str) for item in schedule),
                f"manifest session {position}: policy schedule is invalid")
        expected_schedule = expected_policy_schedule(str(session.get("session_order")), profile_name)
        require(tuple(schedule) == expected_schedule,
                f"manifest session {position}: policy schedule/order contract drifted")
        require(session_index in {1, 2, 3},
                f"manifest session {position}: per-coordinate session index is invalid")
    require(sorted(global_indices) == list(range(1, len(sessions) + 1)),
            "manifest global session indices are not a contiguous unique sequence")
    for identifier, group in by_coordinate.items():
        require(len(group) == REPETITIONS,
                f"manifest coordinate {identifier}: not exactly three fresh sessions")
        require(sorted(int(session["session_index_within_coordinate"]) for session in group) == [1, 2, 3],
                f"manifest coordinate {identifier}: session indices are incomplete")
        expected_orders = ["A", "A", "A"] if profile_name == "v100" else ["ABC", "BCA", "CAB"]
        require(sorted(str(session.get("session_order")) for session in group) == expected_orders,
                f"manifest coordinate {identifier}: persistent-order balance failed")
    return result


def validate_declared_parent_binding(manifest: Mapping[str, Any]) -> None:
    """Validate a standalone child before permitting supplemental analysis."""

    phase = manifest.get("phase")
    binding = manifest.get("parent")
    if phase == "screen":
        require(binding is None, "initial screen must not declare a parent run")
        return
    require(isinstance(binding, dict), "followup/confirmation manifest has no parent binding")
    parent_path = resolve_path(str(binding.get("run_dir", ""))).resolve()
    parent_manifest_path = parent_path / "manifest.json"
    require(parent_manifest_path.is_file(), "bound parent manifest is missing")
    require(binding.get("manifest_sha256") == sha256_file(parent_manifest_path),
            "declared parent manifest SHA no longer matches")
    parent_manifest = read_json(parent_manifest_path)
    require(parent_manifest.get("schema_version") == MANIFEST_SCHEMA and
            parent_manifest.get("phase") == "screen",
            "declared parent is not an initial range screen")


def validate_static_audit(
    manifest: Mapping[str, Any], profile_name: str, binary_sha: str, runner_sha: str
) -> dict[str, Any]:
    """Verify the post-execution PTX/SASS binding before using energy rows.

    The bound audit intentionally inspects the run-local frozen executable.
    PTX type/count contracts establish the endpoint semantics, while the SASS
    section proves target-native provenance without imposing an sm86 lowering
    rule on any other architecture.
    """

    binding = manifest.get("sass_audit")
    require(isinstance(binding, dict), "manifest has no bound range SASS audit")
    require(binding.get("binary_sha256") == binary_sha and
            binding.get("runner_sha256") == runner_sha,
            "bound SASS audit does not match frozen binary/runner")
    require(binding.get("target_profile") == profile_name,
            "bound SASS audit profile mismatch")
    expected_profile = PLATFORM_PROFILES[profile_name]
    expected_arch = expected_profile.cuda_arch
    require(binding.get("native_cuda_arch") == expected_arch,
            "bound SASS audit native architecture mismatch")
    audit_path = resolve_path(str(binding.get("path", "")))
    require(audit_path.is_file(), "bound SASS audit file is missing")
    require(sha256_file(audit_path) == binding.get("sha256"),
            "bound SASS audit SHA mismatch")
    audit = read_json(audit_path)
    require(audit.get("schema_version") == SASS_AUDIT_SCHEMA,
            "bound SASS audit schema mismatch")
    overall = audit.get("overall")
    require(isinstance(overall, dict) and overall.get("pass") is True and
            overall.get("fail_on_unexpected") is True and
            overall.get("unexpected_check_ids") == [],
            "bound SASS audit did not pass fail-on-unexpected")
    audit_binary = audit.get("binary")
    require(isinstance(audit_binary, dict) and audit_binary.get("sha256") == binary_sha,
            "SASS audit inspected a different binary")
    require(audit_binary.get("native_architectures") == [expected_arch] and
            audit_binary.get("embedded_ptx_architectures") == [expected_arch],
            "SASS audit native/PTX architecture set mismatch")
    contract = audit.get("contract")
    require(isinstance(contract, dict) and contract.get("target_profile") == profile_name and
            contract.get("native_cuda_arch") == expected_arch,
            "SASS audit contract profile/architecture mismatch")
    coordinates = manifest.get("coordinates")
    require(isinstance(coordinates, list) and coordinates,
            "manifest coordinates missing for SASS audit cross-check")
    measured_cols = sorted({int(item["softmax_cols"]) for item in coordinates
                            if isinstance(item, dict) and "softmax_cols" in item})
    policies = required_policies(profile_name)
    policy_ids = [POLICY_IDS[policy] for policy in policies]
    require(contract.get("required_softmax_cols") == measured_cols and
            contract.get("required_policy_ids") == policy_ids and
            contract.get("required_policy_names") == list(policies),
            "SASS audit required S/policy set differs from manifest")
    require(binding.get("required_softmax_cols") == measured_cols and
            binding.get("required_policy_ids") == policy_ids and
            binding.get("required_policy_names") == list(policies),
            "manifest SASS binding required S/policy set differs from manifest")
    captures = audit.get("captures")
    require(isinstance(captures, dict), "SASS audit captures missing")
    for softmax_cols in measured_cols:
        width = captures.get(f"s{softmax_cols}")
        require(isinstance(width, dict), f"SASS audit missing S={softmax_cols} captures")
        for policy, policy_id in zip(policies, policy_ids):
            capture = width.get(f"policy_{policy_id}")
            require(isinstance(capture, dict) and capture.get("pass") is True,
                    f"SASS audit failed S={softmax_cols}/{policy}")
            require(capture.get("policy") == policy and
                    capture.get("policy_id") == policy_id and
                    capture.get("softmax_cols") == softmax_cols,
                    f"SASS audit capture identity mismatch S={softmax_cols}/{policy}")
            ptx_checks = capture.get("ptx_checks")
            require(isinstance(ptx_checks, list) and ptx_checks and
                    all(isinstance(check, dict) and check.get("pass") is True
                        for check in ptx_checks),
                    f"SASS audit PTX contract failed S={softmax_cols}/{policy}")
            provenance = capture.get("sass_provenance")
            require(isinstance(provenance, dict) and
                    provenance.get("native_arch_header_present") is True and
                    provenance.get("target_native_only") is True,
                    f"SASS audit native provenance missing S={softmax_cols}/{policy}")
    # Preserve the raw cuobjdump captures as inspectable evidence, and reject
    # a rewritten capture even if its JSON summary was copied unchanged.
    raw_captures = audit.get("cuobjdump_captures")
    require(isinstance(raw_captures, dict), "SASS audit raw captures missing")
    for name in ("list_elf", "list_ptx", "dump_ptx", "dump_sass"):
        item = raw_captures.get(name)
        require(isinstance(item, dict) and isinstance(item.get("path"), str),
                f"SASS audit capture {name} metadata missing")
        capture_path = resolve_path(str(item["path"]))
        require(is_within(capture_path, audit_path.parent),
                f"SASS audit capture {name} is not retained under the bound run directory")
        require(capture_path.is_file() and sha256_file(capture_path) == item.get("sha256"),
                f"SASS audit capture {name} SHA mismatch or file missing")
    if profile_name == "v100":
        unsupported = contract.get("unsupported_policies")
        require(isinstance(unsupported, dict), "V100 SASS audit unsupported endpoint evidence missing")
        for policy_id in (8, 9):
            item = unsupported.get(f"policy_{policy_id}")
            require(isinstance(item, dict) and item.get("pass") is True and
                    item.get("status") == "unsupported_native_fp16_ex2_sm70",
                    "V100 SASS audit native-FP16 skip evidence mismatch")
    return {"path": str(audit_path), "sha256": str(binding["sha256"])}


def validate_session(
    session: Mapping[str, Any], manifest: Mapping[str, Any], profile_name: str
) -> list[Cell]:
    label = f"session {session.get('global_session_index')}"
    require(session.get("status") == "complete", f"{label}: not complete")
    raw_path = resolve_path(str(session.get("raw_csv", "")))
    trace_path = resolve_path(str(session.get("energy_trace_csv", "")))
    require(raw_path.is_file() and trace_path.is_file(), f"{label}: raw/trace artifact missing")
    require(sha256_file(raw_path) == session.get("raw_sha256"), f"{label}: raw SHA-256 mismatch")
    require(sha256_file(trace_path) == session.get("energy_trace_sha256"), f"{label}: trace SHA-256 mismatch")
    rows = read_csv(raw_path)
    trace_rows = read_csv(trace_path)
    schedule = session.get("policy_schedule")
    require(isinstance(schedule, list) and all(isinstance(item, str) for item in schedule),
            f"{label}: invalid policy schedule")
    require(len(rows) == len(schedule), f"{label}: raw role count differs from schedule")
    expected_order = str(session.get("session_order"))
    expected_profile = PLATFORM_PROFILES[profile_name]
    cells: list[Cell] = []
    for sequence, (row, policy) in enumerate(zip(rows, schedule)):
        row_label = f"{label}/{policy}"
        required = (
            "schema_version", "experiment_kind", "protocol_revision", "design_id", "policy",
            "stage_group", "session_id", "session_order", "coordinate_id", "range_phase", "softmax_cols",
            "threads_per_block", "elements_per_thread", "grid_blocks", "runtime_sm_count",
            "rows_per_block", "iters", "logical_input_elements", "net_E_J",
            "packed_elementwise_mapping",
            "occupancy_max_blocks_per_sm", "static_single_wave_capacity_blocks",
            "grid_nominal_ctas_per_sm", "grid_sm_coverage",
            "static_single_wave_capacity_gate_pass", "requested_sm_coverage",
            "preheat_requested_s", "preheat_actual_s", "energy_trace_status",
            "energy_trace_update_count", "energy_trace_r2", "energy_trace_sample_count",
            "energy_source", "measurement_scope", "validation_pass", "validation_id",
            "logical_output_elements", "delta_E_J", "idle_power_W", "energy_trace_power_W",
            "gross_pJ_per_output_element", RAW_METRIC_FIELD,
            "conditioning_mode", "conditioning_policy", "conditioning_requested_s",
            "conditioning_actual_s", "preheat_policy", "validation_before_conditioning",
            "calibration_before_conditioning", "premeasurement_schedule_warmup",
            "smid_unique", "smid_total_blocks", "smid_max_blocks_on_sm", "smid_histogram_ok",
        )
        require(all(field in row for field in required), f"{row_label}: range CSV schema incomplete")
        require(row["schema_version"] == RAW_SCHEMA, f"{row_label}: raw schema mismatch")
        require(row["experiment_kind"] == EXPERIMENT_KIND, f"{row_label}: experiment kind mismatch")
        require(row["protocol_revision"] == PROTOCOL_REVISION, f"{row_label}: protocol mismatch")
        require(row["design_id"] == DESIGN_ID, f"{row_label}: design mismatch")
        require(row["stage_group"] == "endpoint_range", f"{row_label}: stage group mismatch")
        require(row["policy"] == policy, f"{row_label}: policy/schedule mismatch")
        require(row["session_id"] == session.get("session_id"), f"{row_label}: session ID mismatch")
        require(row["session_order"] == expected_order, f"{row_label}: session order mismatch")
        require(integer(row, "sequence_index", row_label) == sequence,
                f"{row_label}: sequence index mismatch")
        require(row["coordinate_id"] == session.get("coordinate_id"), f"{row_label}: coordinate mismatch")
        require(row["range_phase"] == manifest.get("phase"), f"{row_label}: phase mismatch")
        require(integer(row, "softmax_cols", row_label) == int(session["softmax_cols"]),
                f"{row_label}: S mismatch")
        require(integer(row, "threads_per_block", row_label) == 256,
                f"{row_label}: kThreadsPerBlock changed")
        require(integer(row, "elements_per_thread", row_label) == int(session["softmax_cols"]) // 256,
                f"{row_label}: elements/thread mismatch")
        require(row["packed_elementwise_mapping"] == "adjacent_within_row_contiguous_thread_chunk",
                f"{row_label}: packed elementwise mapping is not the contiguous adjacent-pair contract")
        require(integer(row, "grid_blocks", row_label) == int(session["grid_blocks"]),
                f"{row_label}: grid mismatch")
        runtime_sm = integer(row, "runtime_sm_count", row_label)
        require(runtime_sm == int(session["runtime_sm_count"]),
                f"{row_label}: runtime SM count differs from plan")
        require(row.get("compute_capability") == expected_profile.compute_capability,
                f"{row_label}: compute capability/profile mismatch")
        require(integer(row, "cuda_binary_arch", row_label) == expected_profile.cuda_arch,
                f"{row_label}: loaded binary architecture mismatch")
        occupancy = integer(row, "occupancy_max_blocks_per_sm", row_label)
        capacity = integer(row, "static_single_wave_capacity_blocks", row_label)
        require(occupancy > 0 and capacity == runtime_sm * occupancy,
                f"{row_label}: static single-wave capacity mismatch")
        require(boolean(row, "static_single_wave_capacity_gate_pass", row_label),
                f"{row_label}: static capacity gate failed")
        require(int(session["grid_blocks"]) <= capacity,
                f"{row_label}: grid exceeds static single-wave capacity")
        expected_distinct_smid = min(int(session["grid_blocks"]), runtime_sm)
        require(integer(row, "smid_total_blocks", row_label) == int(session["grid_blocks"]),
                f"{row_label}: SMID block count mismatch")
        require(integer(row, "smid_unique", row_label) == expected_distinct_smid and
                integer(row, "smid_max_blocks_on_sm", row_label) == 1,
                f"{row_label}: planned q coverage was not observed as one CTA per distinct SM")
        close(number(row, "grid_nominal_ctas_per_sm", row_label),
              math.ceil(int(session["grid_blocks"]) / runtime_sm),
              f"{row_label}: nominal CTAs/SM")
        actual_coverage = number(row, "grid_sm_coverage", row_label)
        close(actual_coverage, int(session["grid_blocks"]) / runtime_sm,
              f"{row_label}: actual SM coverage")
        requested_coverage = number(row, "requested_sm_coverage", row_label)
        close(requested_coverage, float(session["requested_sm_coverage"]),
              f"{row_label}: requested coverage")
        require(abs(actual_coverage - requested_coverage) <= 1.0 / runtime_sm + 1e-9,
                f"{row_label}: coverage rounding exceeds one CTA")
        close(number(row, "preheat_requested_s", row_label), PREHEAT_REQUESTED_S,
              f"{row_label}: preheat request")
        preheat = number(row, "preheat_actual_s", row_label)
        require(PREHEAT_MIN_S <= preheat <= PREHEAT_MAX_S,
                f"{row_label}: preheat actual outside 5 s contract")
        require(row["conditioning_mode"] == "endpoint_range_common_v1" and
                row["conditioning_policy"] == "fp32_io_fp32_all" and
                row["preheat_policy"] == "fp32_io_fp32_all",
                f"{row_label}: common endpoint-range conditioning contract drifted")
        close(number(row, "conditioning_requested_s", row_label), PREHEAT_REQUESTED_S,
              f"{row_label}: conditioning request")
        close(number(row, "conditioning_actual_s", row_label), preheat,
              f"{row_label}: conditioning actual")
        require(boolean(row, "validation_before_conditioning", row_label) and
                boolean(row, "calibration_before_conditioning", row_label) and
                row["premeasurement_schedule_warmup"] == "none",
                f"{row_label}: premeasurement preparation contract drifted")
        require(row["energy_trace_status"] == "pass", f"{row_label}: trace is not qualified")
        require(integer(row, "energy_trace_update_count", row_label) >= TRACE_MIN_UPDATES,
                f"{row_label}: insufficient energy-counter updates")
        trace_r2 = number(row, "energy_trace_r2", row_label)
        require(trace_r2 >= TRACE_MIN_R2, f"{row_label}: trace R² below gate")
        require(row["energy_source"] == "nvml_total_energy_trace_theil_sen",
                f"{row_label}: endpoint fallback is not qualified")
        require(row["measurement_scope"] == "complete_softmax_forward",
                f"{row_label}: measurement scope drifted")
        rows_per_block = integer(row, "rows_per_block", row_label)
        iters = integer(row, "iters", row_label)
        require(rows_per_block == 2 and iters > 0,
                f"{row_label}: rows-per-block or calibrated iterations invalid")
        expected_logical_elements = (
            int(session["grid_blocks"]) * rows_per_block * iters * int(session["softmax_cols"])
        )
        logical_input = integer(row, "logical_input_elements", row_label)
        logical_output = integer(row, "logical_output_elements", row_label)
        require(logical_input == expected_logical_elements and logical_output == expected_logical_elements,
                f"{row_label}: logical output-element denominator mismatch")
        require(boolean(row, "validation_pass", row_label), f"{row_label}: numerical validation failed")
        require(row["validation_id"] == "whole_precision_fp64_semantic_input_v1_pass",
                f"{row_label}: numerical validation ID drifted")
        require(boolean(row, "smid_histogram_ok", row_label), f"{row_label}: SMID gate failed")
        policy_contract_ok(row, policy, row_label)
        if profile_name == "v100":
            require(policy == "fp32_io_fp32_all", f"{row_label}: V100 must skip native FP16 EX2 endpoints")
        expected_trace_count = integer(row, "energy_trace_sample_count", row_label)
        validate_trace(trace_rows, str(row["run_id"]), expected_trace_count, row_label)
        elapsed = number(row, "elapsed_s", row_label)
        trace_power = number(row, "energy_trace_power_W", row_label)
        delta_energy = number(row, "delta_E_J", row_label)
        idle_power = number(row, "idle_power_W", row_label)
        net_energy = number(row, "net_E_J", row_label)
        require(elapsed > 0.0 and trace_power > 0.0 and delta_energy > 0.0 and
                idle_power >= 0.0 and net_energy > 0.0,
                f"{row_label}: non-positive qualified energy term")
        close(delta_energy, trace_power * elapsed,
              f"{row_label}: trace-derived gross energy calculation")
        close(net_energy, delta_energy - idle_power * elapsed,
              f"{row_label}: idle-subtracted net energy calculation")
        gross_pj = number(row, "gross_pJ_per_output_element", row_label)
        close(gross_pj, delta_energy * 1.0e12 / logical_output,
              f"{row_label}: gross pJ/output denominator calculation")
        net_pj = number(row, RAW_METRIC_FIELD, row_label)
        require(net_pj > 0.0, f"{row_label}: net pJ/output must be positive")
        close(net_pj, net_energy * 1.0e12 / logical_output,
              f"{row_label}: net pJ/output denominator calculation")
        cells.append(Cell(
            profile=profile_name,
            coordinate_id=str(session["coordinate_id"]),
            policy=policy,
            session_id=str(session["session_id"]),
            session_index=int(session["session_index_within_coordinate"]),
            session_order=expected_order,
            run_id=str(row["run_id"]),
            softmax_cols=integer(row, "softmax_cols", row_label),
            grid_blocks=integer(row, "grid_blocks", row_label),
            runtime_sm_count=runtime_sm,
            requested_sm_coverage=requested_coverage,
            grid_sm_coverage=actual_coverage,
            occupancy=occupancy,
            static_capacity=capacity,
            logical_elements=integer(row, "logical_output_elements", row_label),
            net_pj=net_pj,
            gross_pj=gross_pj,
            elapsed_s=elapsed,
            preheat_s=preheat,
            trace_r2=trace_r2,
            trace_updates=integer(row, "energy_trace_update_count", row_label),
            temp_before_c=integer(row, "temp_before_C", row_label),
            temp_after_c=integer(row, "temp_after_C", row_label),
            validation_abs_error=number(row, "validation_max_abs_error", row_label),
            validation_row_sum_error=number(row, "validation_max_row_sum_error", row_label),
        ))
    return cells


def stats(values: list[float]) -> dict[str, float]:
    require(bool(values), "cannot summarize no values")
    average = statistics.fmean(values)
    median = statistics.median(values)
    sample_std = statistics.stdev(values) if len(values) > 1 else 0.0
    t95 = T95_N3 * sample_std / math.sqrt(len(values)) if len(values) == 3 else math.nan
    return {
        "n": len(values), "mean_net_pj": average, "median_net_pj": median,
        "sample_std_net_pj": sample_std, "min_session_net_pj": min(values),
        "max_session_net_pj": max(values),
        "t95_low_net_pj": average - t95 if math.isfinite(t95) else math.nan,
        "t95_high_net_pj": average + t95 if math.isfinite(t95) else math.nan,
    }


def coordinate_summary(cells: list[Cell]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Cell]] = defaultdict(list)
    for cell in cells:
        grouped[(cell.policy, cell.coordinate_id)].append(cell)
    rows: list[dict[str, Any]] = []
    for (policy, coordinate), group in sorted(grouped.items()):
        require(len(group) == 3, f"{policy}/{coordinate}: expected exactly 3 fresh sessions")
        session_indices = sorted(cell.session_index for cell in group)
        require(session_indices == [1, 2, 3], f"{policy}/{coordinate}: session indices incomplete")
        if policy == "fp32_io_fp32_all" and all(cell.session_order == "A" for cell in group):
            pass
        elif policy != "fp32_io_fp32_all" or any(cell.session_order != "A" for cell in group):
            require(sorted(cell.session_order for cell in group) == ["ABC", "BCA", "CAB"],
                    f"{policy}/{coordinate}: ABC/BCA/CAB balance failed")
        result = stats([cell.net_pj for cell in group])
        first = group[0]
        rows.append({
            "profile": first.profile,
            "policy": policy,
            "coordinate_id": coordinate,
            "softmax_cols": first.softmax_cols,
            "grid_blocks": first.grid_blocks,
            "runtime_sm_count": first.runtime_sm_count,
            "requested_sm_coverage": first.requested_sm_coverage,
            "actual_grid_sm_coverage": first.grid_sm_coverage,
            "occupancy_max_blocks_per_sm": first.occupancy,
            "static_single_wave_capacity_blocks": first.static_capacity,
            "representative_coordinate": coordinate == "s1024_q50",
            **result,
        })
    return rows


def tie_set(rows: list[dict[str, Any]], *, best: bool) -> list[str]:
    ordered = sorted(rows, key=lambda row: float(row["median_net_pj"]), reverse=not best)
    reference = float(ordered[0]["median_net_pj"])
    if best:
        return [str(row["coordinate_id"]) for row in ordered
                if float(row["median_net_pj"]) <= reference * (1.0 + PRACTICAL_DIFFERENCE)]
    return [str(row["coordinate_id"]) for row in ordered
            if float(row["median_net_pj"]) >= reference * (1.0 - PRACTICAL_DIFFERENCE)]


def range_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["policy"])].append(row)
    result: list[dict[str, Any]] = []
    for policy, group in sorted(grouped.items()):
        representative = [row for row in group if row["coordinate_id"] == "s1024_q50"]
        best_row = min(group, key=lambda row: float(row["median_net_pj"]))
        worst_row = max(group, key=lambda row: float(row["median_net_pj"]))
        # A supplemental run intentionally carries only new coordinates.  It
        # must remain analyzable, but may not silently select a new
        # representative after observing the follow-up data.
        representative_row = representative[0] if len(representative) == 1 else None
        result.append({
            "profile": group[0]["profile"],
            "policy": policy,
            "range_status": (
                "screened_observed_range_not_fresh_extrema_confirmed"
                if representative_row is not None
                else "supplemental_coordinate_run_not_combined_with_parent"
            ),
            "best_coordinate_set_within_10pct": ";".join(tie_set(group, best=True)),
            "best_coordinate_primary": best_row["coordinate_id"],
            "best_median_net_pj": best_row["median_net_pj"],
            "worst_coordinate_set_within_10pct": ";".join(tie_set(group, best=False)),
            "worst_coordinate_primary": worst_row["coordinate_id"],
            "worst_median_net_pj": worst_row["median_net_pj"],
            "representative_coordinate": (
                representative_row["coordinate_id"] if representative_row else ""
            ),
            "representative_median_net_pj": (
                representative_row["median_net_pj"] if representative_row else ""
            ),
            "representative_mean_net_pj": (
                representative_row["mean_net_pj"] if representative_row else ""
            ),
            "representative_t95_low_net_pj": (
                representative_row["t95_low_net_pj"] if representative_row else ""
            ),
            "representative_t95_high_net_pj": (
                representative_row["t95_high_net_pj"] if representative_row else ""
            ),
        })
    return result


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / ((abs(left) + abs(right)) / 2.0)


def followup_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_policy_coordinate = {(str(row["policy"]), str(row["coordinate_id"])): row for row in rows}
    policies = sorted({str(row["policy"]) for row in rows})
    required = ("s1024_q50", "s4096_q50", "s1024_q25")
    if any((policy, coordinate) not in by_policy_coordinate for policy in policies for coordinate in required):
        return {"status": "not_applicable", "reason": "initial screen coordinates are incomplete"}
    plateau: list[dict[str, Any]] = []
    load: list[dict[str, Any]] = []
    add_2048 = False
    add_q25_extremes = False
    for policy in policies:
        representative = float(by_policy_coordinate[(policy, "s1024_q50")]["median_net_pj"])
        wide = float(by_policy_coordinate[(policy, "s4096_q50")]["median_net_pj"])
        low_coverage = float(by_policy_coordinate[(policy, "s1024_q25")]["median_net_pj"])
        plateau_difference = relative_difference(representative, wide)
        load_difference = relative_difference(representative, low_coverage)
        plateau.append({"policy": policy, "relative_difference": plateau_difference,
                        "triggered": plateau_difference > PRACTICAL_DIFFERENCE})
        load.append({"policy": policy, "relative_difference": load_difference,
                     "triggered": load_difference > PRACTICAL_DIFFERENCE})
        add_2048 = add_2048 or plateau_difference > PRACTICAL_DIFFERENCE
        add_q25_extremes = add_q25_extremes or load_difference > PRACTICAL_DIFFERENCE
    coordinates: list[str] = []
    if add_2048:
        coordinates.append("s2048_q50")
    if add_q25_extremes:
        coordinates.extend(("s512_q25", "s4096_q25"))
    return {
        "status": "followup_required" if coordinates else "stop_after_screen",
        "practical_difference_fraction": PRACTICAL_DIFFERENCE,
        "plateau_gate": plateau,
        "load_gate": load,
        "coordinates": coordinates,
        "rationale": "Only gate-triggered midpoint or low-coverage extremes are added; no full factorial sweep.",
    }


def cell_rows(cells: list[Cell]) -> list[dict[str, Any]]:
    return [cell.__dict__ for cell in sorted(cells, key=lambda cell: (cell.policy, cell.coordinate_id, cell.session_index))]


def quality_rows(cells: list[Cell], manifest_paths: list[Path],
                 static_audits: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    temperatures = [value for cell in cells for value in (cell.temp_before_c, cell.temp_after_c)]
    return [
        {"check": "evidence binding", "result": "pass",
         "detail": f"{len(cells)} raw roles are SHA-256 bound across "
                   f"{', '.join(path.name for path in manifest_paths)}"},
        {"check": "target-native PTX/SASS binding", "result": "pass",
         "detail": "; ".join(
             f"{Path(audit['path']).name} SHA-256 {audit['sha256']}"
             for audit in static_audits)},
        {"check": "5 s common conditioning", "result": "pass",
         "detail": f"actual preheat {min(cell.preheat_s for cell in cells):.3f}-{max(cell.preheat_s for cell in cells):.3f} s"},
        {"check": "trace/numerical/capacity", "result": "pass",
         "detail": f"trace R² {min(cell.trace_r2 for cell in cells):.6f}-{max(cell.trace_r2 for cell in cells):.6f}; all static single-wave gates pass"},
        {"check": "thermal context", "result": "recorded_not_adjusted",
         "detail": f"{min(temperatures)}-{max(temperatures)} C; temperature is not a rejection or causal correction"},
    ]


def summary_markdown(ranges: list[dict[str, Any]], followup: Mapping[str, Any]) -> str:
    lines = [
        "# Whole-Softmax precision range analysis",
        "",
        "이 값은 complete Softmax forward의 `net pJ/element`다. 여기서 element는 logical Softmax output element 하나이며 packed FP16x2도 두 scalar element를 이미 분모에 포함한다. 기존 EX2 Operand-rate ATC의 pJ/logical exponent result와 합산하거나 비교하지 않는다.",
        "",
        "대표값은 사전 고정한 `S=1024, q=50%`이고, best/worst는 screen에서 선택된 관측 범위라 fresh extrema confirmation 전까지 확정값이 아니다.",
        "",
        "| policy | best (screened, pJ/element) | representative S1024/q50 (pJ/element) | worst (screened, pJ/element) |",
        "|---|---:|---:|---:|",
    ]
    for row in ranges:
        representative = row["representative_median_net_pj"]
        representative_text = (
            f"{float(representative):.3f}" if representative != "" else "not in this run"
        )
        lines.append(
            f"| `{row['policy']}` | {float(row['best_median_net_pj']):.3f} ({row['best_coordinate_primary']}) | "
            f"{representative_text} | "
            f"{float(row['worst_median_net_pj']):.3f} ({row['worst_coordinate_primary']}) |"
        )
    lines.extend([
        "",
        "## Adaptive decision",
        "",
        f"status: `{followup.get('status')}`",
        "",
        f"follow-up coordinates: `{', '.join(followup.get('coordinates', [])) or 'none'}`",
        "",
        "온도는 기록 context만이며, 플랫폼 사이의 값은 pool하거나 하나의 순위로 만들지 않는다.",
        "",
    ])
    return "\n".join(lines)


def analyze(run_dir: Path, parent_run: Path | None = None) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "manifest schema mismatch")
    require(manifest.get("status") == "complete", "run is not complete")
    profile = manifest.get("profile")
    require(isinstance(profile, dict) and isinstance(profile.get("name"), str), "profile metadata missing")
    profile_name = str(profile["name"])
    require(profile_name in PLATFORM_PROFILES, "unknown profile")
    validate_coordinate_plan(manifest, profile_name)
    validate_declared_parent_binding(manifest)
    binary = manifest.get("binary")
    runner = manifest.get("runner")
    require(isinstance(binary, dict) and isinstance(runner, dict), "frozen binary/runner metadata missing")
    for label, item in (("binary", binary), ("runner", runner)):
        path = resolve_path(str(item.get("path", "")))
        require(path.is_file(), f"frozen {label} is missing")
        require(sha256_file(path) == item.get("sha256"), f"frozen {label} SHA mismatch")
    static_audit = validate_static_audit(
        manifest, profile_name, str(binary["sha256"]), str(runner["sha256"])
    )
    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and sessions, "manifest sessions missing")
    cells: list[Cell] = []
    for session in sessions:
        require(isinstance(session, dict), "invalid session object")
        cells.extend(validate_session(session, manifest, profile_name))
    require(len({cell.run_id for cell in cells}) == len(cells), "duplicate run_id")
    require(len({cell.session_id for cell in cells}) == len(sessions), "duplicate session ID")
    evidence_runs: list[dict[str, Any]] = [{
        "run_dir": str(run_dir), "manifest_sha256": sha256_file(manifest_path),
        "role_count": len(cells), "static_audit": static_audit,
    }]
    static_audits: list[Mapping[str, str]] = [static_audit]
    manifest_paths = [manifest_path]
    if parent_run is not None:
        require(manifest.get("phase") == "followup",
                "--parent-run may only combine a followup run with its screen parent")
        parent_path = parent_run.resolve()
        parent_manifest_path = parent_path / "manifest.json"
        parent_manifest = read_json(parent_manifest_path)
        parent_binding = manifest.get("parent")
        require(isinstance(parent_binding, dict) and
                resolve_path(str(parent_binding.get("run_dir", ""))).resolve() == parent_path and
                parent_binding.get("manifest_sha256") == sha256_file(parent_manifest_path),
                "followup manifest is not hash-bound to the supplied parent")
        require(parent_manifest.get("phase") == "screen",
                "--parent-run must be an initial screen manifest")
        parent_result = analyze(parent_path)
        parent_profile = parent_manifest.get("profile")
        require(isinstance(parent_profile, dict) and parent_profile.get("name") == profile_name,
                "parent/child profile mismatch")
        parent_binary = parent_manifest.get("binary")
        require(isinstance(parent_binary, dict) and parent_binary.get("sha256") == binary.get("sha256"),
                "parent/child frozen binary mismatch; range coordinates cannot be pooled")
        parent_cells_raw = parent_result.get("validated_cells")
        require(isinstance(parent_cells_raw, list) and
                all(isinstance(row, dict) for row in parent_cells_raw),
                "parent analysis validated cells missing")
        parent_cells = [Cell(**row) for row in parent_cells_raw]
        parent_coordinates = {cell.coordinate_id for cell in parent_cells}
        child_coordinates = {cell.coordinate_id for cell in cells}
        require(parent_coordinates.isdisjoint(child_coordinates),
                "followup coordinate overlaps parent; analyze confirmation separately")
        parent_followup = parent_result.get("followup_plan")
        require(isinstance(parent_followup, dict) and
                parent_followup.get("status") == "followup_required",
                "parent screen did not require an adaptive followup")
        planned_coordinates = parent_followup.get("coordinates")
        require(isinstance(planned_coordinates, list) and
                all(isinstance(item, str) for item in planned_coordinates) and
                child_coordinates == set(planned_coordinates),
                "followup coordinates do not exactly match the parent gate-triggered plan")
        cells = parent_cells + cells
        require(len({cell.run_id for cell in cells}) == len(cells),
                "parent/child run IDs collide")
        parent_static = parent_result.get("static_audit")
        require(isinstance(parent_static, dict), "parent static audit metadata missing")
        static_audits = [parent_static, static_audit]
        manifest_paths = [parent_manifest_path, manifest_path]
        evidence_runs.insert(0, {
            "run_dir": str(parent_path),
            "manifest_sha256": sha256_file(parent_manifest_path),
            "role_count": len(parent_cells),
            "static_audit": parent_static,
        })
    summaries = coordinate_summary(cells)
    ranges = range_summary(summaries)
    followup = followup_plan(summaries)
    if parent_run is not None and followup.get("status") == "followup_required":
        completed_coordinates = {str(row["coordinate_id"]) for row in summaries}
        requested_coordinates = list(followup.get("coordinates", []))
        if set(requested_coordinates).issubset(completed_coordinates):
            followup = {
                **followup,
                "status": "followup_complete_screened_range_not_fresh_extrema_confirmed",
                "triggered_coordinates": requested_coordinates,
                "coordinates": [],
                "rationale": (
                    "Every gate-triggered coordinate is present in the hash-bound followup; "
                    "screened extrema still require an independent extrema confirmation before "
                    "being named a confirmed observed range."
                ),
            }
    if followup.get("status") == "followup_complete_screened_range_not_fresh_extrema_confirmed":
        # The per-policy table is consumed directly by the report.  Do not
        # leave its status at the parent-screen-only label after every
        # gate-triggered coordinate has been hash-bound and combined.
        for row in ranges:
            row["range_status"] = "followup_complete_screened_range_not_fresh_extrema_confirmed"
    quality = quality_rows(cells, manifest_paths, static_audits)
    analysis_dir = run_dir / "analysis"
    write_csv(analysis_dir / "validated_cells.csv", cell_rows(cells))
    write_csv(analysis_dir / "coordinate_summary.csv", summaries)
    write_csv(analysis_dir / "range_summary.csv", ranges)
    write_csv(analysis_dir / "quality_gates.csv", quality)
    write_json(analysis_dir / "followup_plan.json", followup)
    (analysis_dir / "summary.md").write_text(summary_markdown(ranges, followup), encoding="utf-8")
    payload = {
        "schema_version": ANALYSIS_SCHEMA,
        "status": "pass",
        "analyzed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest": {"path": str(manifest_path), "sha256": sha256_file(manifest_path)},
        "evidence_runs": evidence_runs,
        "primary_metric": METRIC,
        "practical_difference_fraction": PRACTICAL_DIFFERENCE,
        "validated_cell_count": len(cells),
        "validated_cells": cell_rows(cells),
        "coordinate_summary": summaries,
        "range_summary": ranges,
        "followup_plan": followup,
        "quality_gates": quality,
        "static_audit": static_audit,
    }
    write_json(analysis_dir / "analysis.json", payload)
    return payload


def self_test() -> None:
    assert math.isclose(relative_difference(100.0, 110.0), 2.0 / 21.0)
    example = [
        {"policy": "fp32_io_fp32_all", "coordinate_id": "s1024_q50", "median_net_pj": 10.0},
        {"policy": "fp32_io_fp32_all", "coordinate_id": "s4096_q50", "median_net_pj": 10.8},
        {"policy": "fp32_io_fp32_all", "coordinate_id": "s1024_q25", "median_net_pj": 9.8},
    ]
    assert followup_plan(example)["status"] == "stop_after_screen"
    example[1]["median_net_pj"] = 12.0
    assert "s2048_q50" in followup_plan(example)["coordinates"]
    assert POLICY_CONTRACT["fp16x2_all"][2] == "fp16x2_packed"
    print("softmax_whole_precision_range_analyzer_self_test=pass")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=False)
    parser.add_argument("--parent-run",
                        help="hash-bound initial screen to combine with a followup run")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not args.run_dir:
        raise ValueError("--run-dir is required unless --self-test is used")
    if args.parent_run and not args.run_dir:
        raise ValueError("--parent-run requires --run-dir")
    result = analyze(
        resolve_path(args.run_dir),
        resolve_path(args.parent_run) if args.parent_run else None,
    )
    print(f"analysis_status={result['status']} validated_cells={result['validated_cell_count']}")
    print(f"followup_status={result['followup_plan']['status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as error:  # pragma: no cover - command-line boundary
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
