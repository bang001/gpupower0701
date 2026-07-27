#!/usr/bin/env python3
"""Fail-closed analysis for the RTX 3090 whole-Softmax stage experiment.

This is not an EX2 operand-rate ATC analyzer.  It verifies complete Softmax
policy measurements whose primary unit is net pJ per logical output element.
Every raw and trace artifact is bound to the run manifest before statistics
are calculated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_SCHEMA = "softmax_whole_precision_stage_isolation_manifest_v1"
MANIFEST_PROTOCOL = "rtx3090_softmax_whole_precision_stage_isolation_v1"
RAW_SCHEMA = "softmax_whole_precision_v2"
RAW_PROTOCOL = "whole_softmax_precision_stage_isolation_v1"
DESIGN_ID = "stage_isolation_v1"
BASELINE = "fp16_io_fp32_all"

SOFTMAX_COLS = 512
GRID_BLOCKS = 16
ROWS_PER_BLOCK = 2
LOGIT_SCALE = 4.0
PREHEAT_REQUESTED_S = 20.0
PREHEAT_MIN_S = 16.0
PREHEAT_MAX_S = 25.0
TRACE_MIN_UPDATES = 16
TRACE_MIN_R2 = 0.98

STAGES = ("exp", "reduction", "normalization")
STAGE_POLICIES: dict[str, tuple[str, str, str]] = {
    "exp": (BASELINE, "exp_fp16_scalar", "exp_fp16x2"),
    "reduction": (BASELINE, "reduction_fp16_scalar", "reduction_fp16x2"),
    "normalization": (
        BASELINE,
        "normalization_fp16_scalar",
        "normalization_fp16x2",
    ),
}
ORDER_INDEXES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("ABC", (0, 1, 2)),
    ("CAB", (2, 0, 1)),
    ("BCA", (1, 2, 0)),
)

POLICY_CONTRACT: dict[str, dict[str, str]] = {
    BASELINE: {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp32",
        "reduction_stage": "fp32",
        "normalization_stage": "fp32",
    },
    "exp_fp16_scalar": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp16_scalar",
        "reduction_stage": "fp32",
        "normalization_stage": "fp32",
    },
    "exp_fp16x2": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp16x2_packed",
        "reduction_stage": "fp32",
        "normalization_stage": "fp32",
    },
    "reduction_fp16_scalar": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp32",
        "reduction_stage": "fp16_scalar",
        "normalization_stage": "fp32",
    },
    "reduction_fp16x2": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp32",
        "reduction_stage": "fp16x2_packed",
        "normalization_stage": "fp32",
    },
    "normalization_fp16_scalar": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp32",
        "reduction_stage": "fp32",
        "normalization_stage": "fp16_scalar",
    },
    "normalization_fp16x2": {
        "input_dtype": "fp16",
        "output_dtype": "fp16",
        "exp_stage": "fp32",
        "reduction_stage": "fp32",
        "normalization_stage": "fp16x2_packed",
    },
}

RAW_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_kind",
        "protocol_revision",
        "design_id",
        "stage_group",
        "session_order",
        "run_id",
        "session_id",
        "schedule_id",
        "schedule_block",
        "sequence_index",
        "policy",
        "role",
        "input_dtype",
        "output_dtype",
        "exp_stage",
        "reduction_stage",
        "normalization_stage",
        "gpu_id",
        "gpu_name",
        "compute_capability",
        "cuda_pci_bus_id",
        "cuda_binary_arch",
        "runtime_sm_count",
        "smid_unique",
        "smid_total_blocks",
        "smid_max_blocks_on_sm",
        "smid_histogram_ok",
        "grid_blocks",
        "rows_per_block",
        "softmax_cols",
        "logit_scale",
        "seed",
        "iters",
        "logical_input_elements",
        "logical_output_elements",
        "physical_input_bytes",
        "physical_output_bytes",
        "elapsed_s",
        "delta_E_J",
        "net_E_J",
        "gross_pJ_per_output_element",
        "net_pJ_per_output_element",
        "preheat_requested_s",
        "preheat_actual_s",
        "preheat_policy",
        "energy_trace_sample_count",
        "energy_trace_update_count",
        "energy_trace_fit_point_count",
        "energy_trace_r2",
        "energy_trace_status",
        "energy_source",
        "measurement_scope",
        "temp_before_C",
        "temp_after_C",
        "validation_id",
        "validation_max_abs_error",
        "validation_max_row_sum_error",
        "validation_max_abs_gate",
        "validation_max_row_sum_gate",
        "validation_pass",
        "validation_nonfinite_count",
        "binary_sha256",
    }
)
TRACE_FIELDS = frozenset(
    {
        "run_id",
        "policy",
        "schedule_block",
        "sequence_index",
        "sample_index",
        "query_start_s",
        "query_end_s",
        "query_midpoint_s",
        "query_latency_s",
        "relative_to_kernel_start_s",
        "energy_mJ",
    }
)


class EvidenceError(RuntimeError):
    """A required evidence contract was not satisfied."""


@dataclass(frozen=True)
class SessionPlan:
    stage: str
    session_index: int
    session_order: str
    session_id: str
    schedule: tuple[str, str, str]
    raw_path: Path
    trace_path: Path
    raw_sha256: str
    trace_sha256: str


@dataclass(frozen=True)
class Cell:
    stage: str
    session_id: str
    session_index: int
    session_order: str
    sequence_index: int
    policy: str
    run_id: str
    seed: int
    pci_bus_id: str
    iters: int
    logical_output_elements: int
    elapsed_s: float
    net_energy_j: float
    net_pj: float
    gross_pj: float
    validation_abs_error: float
    validation_row_sum_error: float
    preheat_actual_s: float
    trace_samples: int
    trace_updates: int
    trace_fit_points: int
    trace_r2: float
    temp_before_c: int
    temp_after_c: int
    raw_path: Path
    trace_path: Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_path(value: str, run_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    repository_path = REPO_ROOT / path
    return repository_path if repository_path.exists() else run_dir / path


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"manifest is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read manifest {path}: {error}") from error
    require(isinstance(value, dict), f"manifest must contain a JSON object: {path}")
    return value


def read_csv_strict(path: Path, required: frozenset[str], label: str) -> list[dict[str, str]]:
    require(path.is_file(), f"{label} is missing: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            require(fields is not None and bool(fields), f"{label} has no header: {path}")
            require(len(fields) == len(set(fields)), f"{label} has duplicate fields: {path}")
            missing = sorted(required - set(fields))
            require(not missing, f"{label} is missing fields {missing}: {path}")
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise EvidenceError(f"cannot read {label} {path}: {error}") from error
    require(bool(rows), f"{label} has no rows: {path}")
    for row_number, row in enumerate(rows, start=1):
        require(None not in row, f"{label} row {row_number} has excess CSV columns: {path}")
    return rows


def row_text(row: Mapping[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    require(isinstance(value, str) and value != "", f"{label}.{field} must be non-empty text")
    return value


def row_int(row: Mapping[str, Any], field: str, label: str, minimum: int | None = None) -> int:
    raw = row.get(field)
    try:
        value = int(str(raw))
    except (TypeError, ValueError) as error:
        raise EvidenceError(f"{label}.{field} is not an integer: {raw!r}") from error
    require(str(value) == str(raw).strip(), f"{label}.{field} is not canonical integer text: {raw!r}")
    if minimum is not None:
        require(value >= minimum, f"{label}.{field} must be >= {minimum}, got {value}")
    return value


def row_number(row: Mapping[str, Any], field: str, label: str) -> float:
    raw = row.get(field)
    try:
        value = float(str(raw))
    except (TypeError, ValueError) as error:
        raise EvidenceError(f"{label}.{field} is not numeric: {raw!r}") from error
    require(math.isfinite(value), f"{label}.{field} is not finite: {raw!r}")
    return value


def row_bool(row: Mapping[str, Any], field: str, label: str) -> bool:
    value = str(row.get(field, "")).strip().lower()
    require(value in {"true", "false"}, f"{label}.{field} must be true/false, got {value!r}")
    return value == "true"


def close(actual: float, expected: float, label: str, *, rel: float = 1.0e-8, abs_: float = 1.0e-8) -> None:
    require(math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_),
            f"{label}: expected {expected}, got {actual}")


def manifest_int(value: Mapping[str, Any], field: str, label: str) -> int:
    raw = value.get(field)
    require(type(raw) is int, f"{label}.{field} must be a JSON integer")
    return raw


def expected_schedule(stage: str, session_index: int) -> tuple[str, str, str]:
    policies = STAGE_POLICIES[stage]
    _order, indexes = ORDER_INDEXES[session_index - 1]
    return tuple(policies[index] for index in indexes)


def validate_manifest(manifest: dict[str, Any], run_dir: Path, allow_partial: bool) -> list[SessionPlan]:
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "manifest schema version is not supported")
    require(manifest.get("protocol_revision") == MANIFEST_PROTOCOL, "manifest protocol revision is not supported")
    require(isinstance(manifest.get("run_tag"), str) and bool(manifest["run_tag"]), "manifest run_tag is missing")
    binary = manifest.get("binary")
    runner = manifest.get("runner")
    design = manifest.get("design")
    execution = manifest.get("execution")
    require(isinstance(binary, dict), "manifest.binary must be an object")
    require(isinstance(runner, dict), "manifest.runner must be an object")
    require(isinstance(design, dict), "manifest.design must be an object")
    require(isinstance(execution, dict), "manifest.execution must be an object")
    binary_sha = row_text(binary, "sha256", "manifest.binary")
    runner_sha = row_text(runner, "sha256", "manifest.runner")
    require(is_sha256(binary_sha), "manifest binary SHA-256 is malformed")
    require(is_sha256(runner_sha), "manifest runner SHA-256 is malformed")
    binary_path = resolve_path(row_text(binary, "path", "manifest.binary"), run_dir)
    runner_path = resolve_path(row_text(runner, "path", "manifest.runner"), run_dir)
    require(binary_path.is_file(), f"manifest binary is missing: {binary_path}")
    require(runner_path.is_file(), f"manifest runner is missing: {runner_path}")
    require(sha256_file(binary_path) == binary_sha, "manifest binary SHA-256 no longer matches the binary")
    require(sha256_file(runner_path) == runner_sha, "manifest runner SHA-256 no longer matches the runner")
    require(design.get("target_profile") == "rtx3090", "manifest target profile must be rtx3090")
    require(design.get("baseline_policy") == BASELINE, "manifest baseline policy drifted")
    require(design.get("order_algorithm") == "cyclic_ABC_CAB_BCA_v1", "manifest order algorithm drifted")
    require(design.get("fresh_binary_process_per_schedule") is True,
            "manifest does not assert a fresh process per schedule")
    require(manifest_int(design, "softmax_cols", "manifest.design") == SOFTMAX_COLS,
            "manifest softmax_cols must be 512")
    require(manifest_int(design, "grid_blocks", "manifest.design") == GRID_BLOCKS,
            "manifest grid_blocks must be 16")
    close(row_number(design, "logit_scale", "manifest.design"), LOGIT_SCALE,
          "manifest logit scale")
    close(row_number(design, "preheat_seconds", "manifest.design"), PREHEAT_REQUESTED_S,
          "manifest preheat request")
    require(manifest_int(design, "energy_trace_min_updates", "manifest.design") == TRACE_MIN_UPDATES,
            "manifest trace update gate drifted")
    require(execution.get("requested") is True, "manifest execution was not requested")
    require(execution.get("status") in {"complete", "complete_unanalyzed"},
            "manifest execution is not complete")

    groups = design.get("stage_groups")
    require(isinstance(groups, list) and all(isinstance(group, str) for group in groups),
            "manifest stage_groups must be a list of strings")
    require(bool(groups), "manifest has no stage groups")
    require(len(groups) == len(set(groups)), "manifest has duplicate stage groups")
    require(all(group in STAGE_POLICIES for group in groups), "manifest contains an unknown stage group")
    selected_canonical = [stage for stage in STAGES if stage in groups]
    require(groups == selected_canonical, "manifest stage groups are not in canonical order")
    if not allow_partial:
        require(groups == list(STAGES), "full analysis requires all three stages; use --allow-partial for a completed subset")

    expected_sessions = len(groups) * 3
    expected_roles = expected_sessions * 3
    require(manifest_int(design, "expected_sessions", "manifest.design") == expected_sessions,
            "manifest expected session count disagrees with stage plan")
    require(manifest_int(design, "expected_measured_roles", "manifest.design") == expected_roles,
            "manifest expected role count disagrees with stage plan")
    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and len(sessions) == expected_sessions,
            "manifest session list does not match stage plan")

    plans: list[SessionPlan] = []
    seen_session_ids: set[str] = set()
    seen_stage_indices: set[tuple[str, int]] = set()
    for position, session in enumerate(sessions, start=1):
        label = f"manifest.sessions[{position - 1}]"
        require(isinstance(session, dict), f"{label} must be an object")
        require(manifest_int(session, "global_session_index", label) == position,
                f"{label}.global_session_index is not contiguous")
        stage = row_text(session, "stage_group", label)
        require(stage in groups, f"{label} stage is not selected")
        session_index = manifest_int(session, "session_index_within_stage", label)
        require(session_index in {1, 2, 3}, f"{label} session index must be 1, 2, or 3")
        require((stage, session_index) not in seen_stage_indices,
                f"duplicate stage/session identity: {stage}/{session_index}")
        seen_stage_indices.add((stage, session_index))
        expected_order, _indexes = ORDER_INDEXES[session_index - 1]
        require(row_text(session, "session_order", label) == expected_order,
                f"{label} session order does not match cyclic contract")
        session_id = row_text(session, "session_id", label)
        require(session_id not in seen_session_ids, f"duplicate session_id: {session_id}")
        seen_session_ids.add(session_id)
        schedule = session.get("policy_schedule")
        require(isinstance(schedule, list) and len(schedule) == 3 and all(isinstance(item, str) for item in schedule),
                f"{label}.policy_schedule must contain three policies")
        expected = expected_schedule(stage, session_index)
        require(tuple(schedule) == expected, f"{label}.policy_schedule violates its stage/order contract")
        require(row_text(session, "schedule_label", label) == ",".join(expected),
                f"{label}.schedule_label mismatch")
        require(manifest_int(session, "expected_measured_roles", label) == 3,
                f"{label} does not plan exactly three roles")
        require(session.get("status") in {"complete", "complete_unanalyzed"},
                f"{label} is not complete")
        require(manifest_int(session, "returncode", label) == 0, f"{label} has a nonzero return code")
        raw_sha = row_text(session, "raw_csv_sha256", label)
        trace_sha = row_text(session, "energy_trace_csv_sha256", label)
        require(is_sha256(raw_sha), f"{label} raw SHA-256 is malformed")
        require(is_sha256(trace_sha), f"{label} trace SHA-256 is malformed")
        raw_path = resolve_path(row_text(session, "raw_csv", label), run_dir)
        trace_path = resolve_path(row_text(session, "energy_trace_csv", label), run_dir)
        require(raw_path.is_file(), f"{label} raw artifact is missing: {raw_path}")
        require(trace_path.is_file(), f"{label} trace artifact is missing: {trace_path}")
        require(sha256_file(raw_path) == raw_sha, f"{label} raw SHA-256 mismatch")
        require(sha256_file(trace_path) == trace_sha, f"{label} trace SHA-256 mismatch")
        plans.append(SessionPlan(stage, session_index, expected_order, session_id,
                                 expected, raw_path, trace_path, raw_sha, trace_sha))
    for stage in groups:
        require({(stage, 1), (stage, 2), (stage, 3)} <= seen_stage_indices,
                f"manifest is missing a cyclic session for stage {stage}")
    return plans


def validate_raw_row(
    row: Mapping[str, str],
    *,
    plan: SessionPlan,
    expected_policy: str,
    expected_sequence: int,
    binary_sha256: str,
    gpu_id: int,
    label: str,
) -> Cell:
    require(row.get("schema_version") == RAW_SCHEMA, f"{label} is not C++ v2 schema")
    require(row.get("experiment_kind") == "whole_softmax_precision", f"{label} experiment kind drifted")
    require(row.get("protocol_revision") == RAW_PROTOCOL, f"{label} raw protocol revision drifted")
    require(row.get("design_id") == DESIGN_ID, f"{label} design ID drifted")
    require(row.get("stage_group") == plan.stage, f"{label} stage group mismatch")
    require(row.get("session_order") == plan.session_order, f"{label} session order mismatch")
    require(row.get("session_id") == plan.session_id, f"{label} session ID mismatch")
    require(row.get("schedule_id") == ",".join(plan.schedule), f"{label} schedule ID mismatch")
    require(row_int(row, "schedule_block", label, 0) == 0,
            f"{label} must contain one schedule block per process")
    require(row_int(row, "sequence_index", label, 0) == expected_sequence,
            f"{label} sequence index mismatch")
    require(row.get("policy") == expected_policy, f"{label} policy mismatch")
    require(row.get("role") == "whole_softmax", f"{label} is not a whole_softmax role")
    for field, expected in POLICY_CONTRACT[expected_policy].items():
        require(row.get(field) == expected,
                f"{label} {field} expected {expected!r}, got {row.get(field)!r}")

    require(row_int(row, "gpu_id", label, 0) == gpu_id, f"{label} GPU identity mismatch")
    require(row.get("compute_capability") == "8.6", f"{label} does not report compute capability 8.6")
    require(row_int(row, "cuda_binary_arch", label, 1) == 86, f"{label} is not sm_86 code")
    require(row_int(row, "runtime_sm_count", label, 1) == 82, f"{label} is not a full 82-SM RTX 3090")
    require("rtx 3090" in row.get("gpu_name", "").lower(), f"{label} GPU name is not RTX 3090")
    pci_bus_id = row_text(row, "cuda_pci_bus_id", label)

    require(row_int(row, "grid_blocks", label, 1) == GRID_BLOCKS, f"{label} grid_blocks drifted")
    require(row_int(row, "rows_per_block", label, 1) == ROWS_PER_BLOCK, f"{label} rows_per_block drifted")
    require(row_int(row, "softmax_cols", label, 1) == SOFTMAX_COLS, f"{label} softmax_cols drifted")
    close(row_number(row, "logit_scale", label), LOGIT_SCALE, f"{label} logit scale")
    seed = row_int(row, "seed", label, 0)
    iters = row_int(row, "iters", label, 1)
    expected_elements = GRID_BLOCKS * ROWS_PER_BLOCK * SOFTMAX_COLS * iters
    logical_input = row_int(row, "logical_input_elements", label, 1)
    logical_output = row_int(row, "logical_output_elements", label, 1)
    require(logical_input == expected_elements, f"{label} logical input denominator mismatch")
    require(logical_output == expected_elements, f"{label} logical output denominator mismatch")
    require(row_int(row, "physical_input_bytes", label, 1) == logical_input * 2,
            f"{label} physical FP16 input bytes mismatch")
    require(row_int(row, "physical_output_bytes", label, 1) == logical_output * 2,
            f"{label} physical FP16 output bytes mismatch")

    elapsed = row_number(row, "elapsed_s", label)
    require(elapsed > 0.0, f"{label} elapsed time is not positive")
    delta_energy = row_number(row, "delta_E_J", label)
    net_energy = row_number(row, "net_E_J", label)
    gross_pj = row_number(row, "gross_pJ_per_output_element", label)
    net_pj = row_number(row, "net_pJ_per_output_element", label)
    close(gross_pj, delta_energy * 1.0e12 / logical_output,
          f"{label} gross pJ denominator", rel=1.0e-7, abs_=1.0e-6)
    close(net_pj, net_energy * 1.0e12 / logical_output,
          f"{label} net pJ denominator", rel=1.0e-7, abs_=1.0e-6)

    close(row_number(row, "preheat_requested_s", label), PREHEAT_REQUESTED_S,
          f"{label} preheat request")
    preheat_actual = row_number(row, "preheat_actual_s", label)
    require(PREHEAT_MIN_S <= preheat_actual <= PREHEAT_MAX_S,
            f"{label} preheat actual is outside {PREHEAT_MIN_S:g}-{PREHEAT_MAX_S:g} s")
    require(row.get("preheat_policy") == BASELINE,
            f"{label} preheat policy must be the shared baseline")

    require(row.get("energy_trace_status") == "pass", f"{label} trace status is not pass")
    require(row.get("energy_source") == "nvml_total_energy_trace_theil_sen",
            f"{label} does not use the qualified trace energy source")
    require(row.get("measurement_scope") == "complete_softmax_forward",
            f"{label} measurement scope drifted")
    trace_samples = row_int(row, "energy_trace_sample_count", label, 1)
    trace_updates = row_int(row, "energy_trace_update_count", label, 0)
    trace_fit_points = row_int(row, "energy_trace_fit_point_count", label, 0)
    trace_r2 = row_number(row, "energy_trace_r2", label)
    require(trace_updates >= TRACE_MIN_UPDATES,
            f"{label} trace updates below {TRACE_MIN_UPDATES}")
    require(trace_fit_points >= TRACE_MIN_UPDATES,
            f"{label} trace fit points below {TRACE_MIN_UPDATES}")
    require(trace_samples >= trace_updates + 1,
            f"{label} trace sample/update counts are inconsistent")
    require(trace_r2 >= TRACE_MIN_R2, f"{label} trace R2 below {TRACE_MIN_R2}")

    require(row_bool(row, "smid_histogram_ok", label), f"{label} SMID gate failed")
    require(row_int(row, "smid_total_blocks", label, 1) == GRID_BLOCKS,
            f"{label} SMID block total mismatch")
    require(row_int(row, "smid_unique", label, 1) <= 82, f"{label} invalid SMID unique count")
    require(row_int(row, "smid_max_blocks_on_sm", label, 1) <= GRID_BLOCKS,
            f"{label} invalid SMID maximum blocks")

    require(row.get("validation_id") == "whole_precision_fp64_semantic_input_v1_pass",
            f"{label} numerical validation ID drifted")
    require(row_bool(row, "validation_pass", label), f"{label} numerical validation did not pass")
    validation_abs_error = row_number(row, "validation_max_abs_error", label)
    validation_sum_error = row_number(row, "validation_max_row_sum_error", label)
    validation_abs_gate = row_number(row, "validation_max_abs_gate", label)
    validation_sum_gate = row_number(row, "validation_max_row_sum_gate", label)
    require(validation_abs_gate > 0.0 and validation_sum_gate > 0.0,
            f"{label} numerical validation gates are invalid")
    require(validation_abs_error <= validation_abs_gate,
            f"{label} max absolute validation error exceeds its gate")
    require(validation_sum_error <= validation_sum_gate,
            f"{label} max row-sum validation error exceeds its gate")
    require(row_int(row, "validation_nonfinite_count", label, 0) == 0,
            f"{label} validation found non-finite output")
    require(row.get("binary_sha256") == binary_sha256, f"{label} raw binary SHA-256 mismatch")

    return Cell(
        stage=plan.stage,
        session_id=plan.session_id,
        session_index=plan.session_index,
        session_order=plan.session_order,
        sequence_index=expected_sequence,
        policy=expected_policy,
        run_id=row_text(row, "run_id", label),
        seed=seed,
        pci_bus_id=pci_bus_id,
        iters=iters,
        logical_output_elements=logical_output,
        elapsed_s=elapsed,
        net_energy_j=net_energy,
        net_pj=net_pj,
        gross_pj=gross_pj,
        validation_abs_error=validation_abs_error,
        validation_row_sum_error=validation_sum_error,
        preheat_actual_s=preheat_actual,
        trace_samples=trace_samples,
        trace_updates=trace_updates,
        trace_fit_points=trace_fit_points,
        trace_r2=trace_r2,
        temp_before_c=row_int(row, "temp_before_C", label, 0),
        temp_after_c=row_int(row, "temp_after_C", label, 0),
        raw_path=plan.raw_path,
        trace_path=plan.trace_path,
    )


def validate_trace(trace_rows: list[dict[str, str]], cells: list[Cell], trace_path: Path) -> None:
    by_run_id = {cell.run_id: cell for cell in cells}
    require(len(by_run_id) == len(cells), f"duplicate raw run IDs in {trace_path}")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trace_row_index, row in enumerate(trace_rows, start=1):
        label = f"trace {trace_path} row {trace_row_index}"
        run_id = row_text(row, "run_id", label)
        require(run_id in by_run_id, f"{label} references unknown raw run_id")
        grouped[run_id].append(row)
    require(set(grouped) == set(by_run_id), f"trace {trace_path} does not cover every raw run")
    for run_id, cell in by_run_id.items():
        rows = grouped[run_id]
        label = f"trace {trace_path} run_id={run_id}"
        require(len(rows) == cell.trace_samples,
                f"{label} sample count does not match raw metadata")
        previous_midpoint = -math.inf
        previous_energy = -math.inf
        sample_indexes: list[int] = []
        for position, row in enumerate(rows):
            row_label = f"{label} sample {position}"
            require(row.get("policy") == cell.policy, f"{row_label} policy mismatch")
            require(row_int(row, "schedule_block", row_label, 0) == 0,
                    f"{row_label} schedule block mismatch")
            require(row_int(row, "sequence_index", row_label, 0) == cell.sequence_index,
                    f"{row_label} sequence index mismatch")
            sample_indexes.append(row_int(row, "sample_index", row_label, 0))
            query_start = row_number(row, "query_start_s", row_label)
            query_end = row_number(row, "query_end_s", row_label)
            midpoint = row_number(row, "query_midpoint_s", row_label)
            latency = row_number(row, "query_latency_s", row_label)
            row_number(row, "relative_to_kernel_start_s", row_label)
            energy = row_number(row, "energy_mJ", row_label)
            require(query_end >= query_start, f"{row_label} query end precedes start")
            require(latency >= 0.0, f"{row_label} has negative query latency")
            require(midpoint >= previous_midpoint, f"{row_label} timestamps are non-monotonic")
            require(energy >= previous_energy, f"{row_label} energy counter is non-monotonic")
            previous_midpoint = midpoint
            previous_energy = energy
        require(sample_indexes == list(range(len(rows))), f"{label} sample indexes are not contiguous")


def validate_artifacts(manifest: dict[str, Any], plans: list[SessionPlan]) -> list[Cell]:
    binary_sha = str(manifest["binary"]["sha256"])
    gpu_id = manifest_int(manifest["design"], "gpu_id", "manifest.design")
    all_cells: list[Cell] = []
    for plan in plans:
        raw_rows = read_csv_strict(plan.raw_path, RAW_FIELDS, "raw CSV")
        require(len(raw_rows) == 3, f"raw CSV must contain exactly three roles: {plan.raw_path}")
        cells: list[Cell] = []
        for sequence_index, (row, policy) in enumerate(zip(raw_rows, plan.schedule)):
            cells.append(validate_raw_row(
                row,
                plan=plan,
                expected_policy=policy,
                expected_sequence=sequence_index,
                binary_sha256=binary_sha,
                gpu_id=gpu_id,
                label=f"raw {plan.raw_path} row {sequence_index + 1}",
            ))
        require(len({cell.run_id for cell in cells}) == 3,
                f"raw CSV has duplicate run_id values: {plan.raw_path}")
        require(len({cell.preheat_actual_s for cell in cells}) == 1,
                f"raw CSV does not retain one common baseline preheat: {plan.raw_path}")
        trace_rows = read_csv_strict(plan.trace_path, TRACE_FIELDS, "energy trace CSV")
        validate_trace(trace_rows, cells, plan.trace_path)
        all_cells.extend(cells)
    require(len({cell.run_id for cell in all_cells}) == len(all_cells),
            "run_id is duplicated across session artifacts")
    require(len({cell.seed for cell in all_cells}) == 1,
            "canonical input seed differs across sessions")
    require(len({cell.pci_bus_id for cell in all_cells}) == 1,
            "CUDA PCI identity differs across sessions")
    return all_cells


SUMMARY_FIELDS = (
    "stage_group",
    "summary_kind",
    "policy",
    "baseline_policy",
    "session_count",
    "mean_net_pJ_per_logical_output_element",
    "sample_std_net_pJ_per_logical_output_element",
    "median_net_pJ_per_logical_output_element",
    "min_net_pJ_per_logical_output_element",
    "max_net_pJ_per_logical_output_element",
    "session_ids",
)
CELL_FIELDS = (
    "stage_group",
    "session_id",
    "session_index_within_stage",
    "session_order",
    "sequence_index",
    "policy",
    "run_id",
    "iters",
    "logical_output_elements",
    "elapsed_s",
    "net_E_J",
    "net_pJ_per_logical_output_element",
    "gross_pJ_per_logical_output_element",
    "validation_max_abs_error",
    "validation_max_row_sum_error",
    "preheat_actual_s",
    "energy_trace_sample_count",
    "energy_trace_update_count",
    "energy_trace_fit_point_count",
    "energy_trace_r2",
    "temperature_start_C",
    "temperature_end_C",
    "raw_csv",
    "trace_csv",
)


def stats(values: list[float]) -> dict[str, float | int]:
    require(bool(values), "cannot summarize an empty value vector")
    return {
        "session_count": len(values),
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def summary_row(
    *,
    stage: str,
    kind: str,
    policy: str,
    baseline: str,
    values: list[float],
    session_ids: list[str],
) -> dict[str, Any]:
    result = stats(values)
    return {
        "stage_group": stage,
        "summary_kind": kind,
        "policy": policy,
        "baseline_policy": baseline,
        "session_count": result["session_count"],
        "mean_net_pJ_per_logical_output_element": result["mean"],
        "sample_std_net_pJ_per_logical_output_element": result["sample_std"],
        "median_net_pJ_per_logical_output_element": result["median"],
        "min_net_pJ_per_logical_output_element": result["minimum"],
        "max_net_pJ_per_logical_output_element": result["maximum"],
        "session_ids": ";".join(session_ids),
    }


def summarize(cells: list[Cell]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_stage_policy: dict[tuple[str, str], list[Cell]] = defaultdict(list)
    by_stage_session: dict[tuple[str, str], dict[str, Cell]] = defaultdict(dict)
    for cell in cells:
        by_stage_policy[(cell.stage, cell.policy)].append(cell)
        session_cells = by_stage_session[(cell.stage, cell.session_id)]
        require(cell.policy not in session_cells,
                f"duplicate policy in stage/session: {cell.stage}/{cell.session_id}/{cell.policy}")
        session_cells[cell.policy] = cell

    absolute: list[dict[str, Any]] = []
    paired: list[dict[str, Any]] = []
    observed_stages = [stage for stage in STAGES if any(cell.stage == stage for cell in cells)]
    for stage in observed_stages:
        policies = STAGE_POLICIES[stage]
        expected_session_ids: list[str] | None = None
        for policy in policies:
            policy_cells = sorted(by_stage_policy[(stage, policy)], key=lambda cell: cell.session_index)
            require(len(policy_cells) == 3, f"{stage}/{policy} does not have three session cells")
            session_ids = [cell.session_id for cell in policy_cells]
            if expected_session_ids is None:
                expected_session_ids = session_ids
            else:
                require(session_ids == expected_session_ids,
                        f"{stage} policies do not share the same session identities")
            absolute.append(summary_row(
                stage=stage,
                kind="absolute",
                policy=policy,
                baseline="",
                values=[cell.net_pj for cell in policy_cells],
                session_ids=session_ids,
            ))
        stage_session_ids = sorted(
            (session_id for current_stage, session_id in by_stage_session if current_stage == stage),
            key=lambda session_id: by_stage_session[(stage, session_id)][BASELINE].session_index,
        )
        require(len(stage_session_ids) == 3, f"{stage} does not contain three paired sessions")
        for policy in policies[1:]:
            deltas: list[float] = []
            for session_id in stage_session_ids:
                session_cells = by_stage_session[(stage, session_id)]
                require(set(session_cells) == set(policies),
                        f"{stage}/{session_id} is missing a policy for paired analysis")
                deltas.append(session_cells[policy].net_pj - session_cells[BASELINE].net_pj)
            paired.append(summary_row(
                stage=stage,
                kind="paired_delta_vs_baseline",
                policy=policy,
                baseline=BASELINE,
                values=deltas,
                session_ids=stage_session_ids,
            ))
    return absolute, paired


def cell_row(cell: Cell) -> dict[str, Any]:
    return {
        "stage_group": cell.stage,
        "session_id": cell.session_id,
        "session_index_within_stage": cell.session_index,
        "session_order": cell.session_order,
        "sequence_index": cell.sequence_index,
        "policy": cell.policy,
        "run_id": cell.run_id,
        "iters": cell.iters,
        "logical_output_elements": cell.logical_output_elements,
        "elapsed_s": cell.elapsed_s,
        "net_E_J": cell.net_energy_j,
        "net_pJ_per_logical_output_element": cell.net_pj,
        "gross_pJ_per_logical_output_element": cell.gross_pj,
        "validation_max_abs_error": cell.validation_abs_error,
        "validation_max_row_sum_error": cell.validation_row_sum_error,
        "preheat_actual_s": cell.preheat_actual_s,
        "energy_trace_sample_count": cell.trace_samples,
        "energy_trace_update_count": cell.trace_updates,
        "energy_trace_fit_point_count": cell.trace_fit_points,
        "energy_trace_r2": cell.trace_r2,
        "temperature_start_C": cell.temp_before_c,
        "temperature_end_C": cell.temp_after_c,
        "raw_csv": display_path(cell.raw_path),
        "trace_csv": display_path(cell.trace_path),
    }


def atomic_write_csv(path: Path, fields: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(fields), extrasaction="raise", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def display_metric(value: Any) -> str:
    return f"{float(value):.6f}"


def build_markdown(
    manifest_path: Path,
    allow_partial: bool,
    absolute: list[dict[str, Any]],
    paired: list[dict[str, Any]],
) -> str:
    lines = [
        "# RTX 3090 Whole-Softmax precision stage-isolation summary",
        "",
        "All manifest, SHA-256, raw-schema, numerical-validation, preheat, trace, SMID, and denominator gates passed.",
        "",
        f"- Manifest: `{display_path(manifest_path)}`",
        "- Primary unit: net pJ / logical Softmax output element",
        "- Scope: " + ("complete selected-stage subset" if allow_partial else "full exp + reduction + normalization design"),
        "- Temperature is recorded but not used as a hard rejection gate.",
        "",
    ]
    for stage in STAGES:
        stage_absolute = [row for row in absolute if row["stage_group"] == stage]
        if not stage_absolute:
            continue
        lines.extend([
            f"## {stage}",
            "",
            "### Absolute policy result",
            "",
            "| policy | n | mean | sample std | median | min | max |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in stage_absolute:
            lines.append(
                "| {policy} | {count} | {mean} | {std} | {median} | {minimum} | {maximum} |".format(
                    policy=row["policy"],
                    count=row["session_count"],
                    mean=display_metric(row["mean_net_pJ_per_logical_output_element"]),
                    std=display_metric(row["sample_std_net_pJ_per_logical_output_element"]),
                    median=display_metric(row["median_net_pJ_per_logical_output_element"]),
                    minimum=display_metric(row["min_net_pJ_per_logical_output_element"]),
                    maximum=display_metric(row["max_net_pJ_per_logical_output_element"]),
                )
            )
        lines.extend([
            "",
            f"### Paired delta vs `{BASELINE}`",
            "",
            "Positive delta means that policy consumed more net pJ/output element than the common baseline in the same session.",
            "",
            "| policy | n | mean delta | sample std | median delta | min | max |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in (entry for entry in paired if entry["stage_group"] == stage):
            lines.append(
                "| {policy} | {count} | {mean} | {std} | {median} | {minimum} | {maximum} |".format(
                    policy=row["policy"],
                    count=row["session_count"],
                    mean=display_metric(row["mean_net_pJ_per_logical_output_element"]),
                    std=display_metric(row["sample_std_net_pJ_per_logical_output_element"]),
                    median=display_metric(row["median_net_pJ_per_logical_output_element"]),
                    minimum=display_metric(row["min_net_pJ_per_logical_output_element"]),
                    maximum=display_metric(row["max_net_pJ_per_logical_output_element"]),
                )
            )
        lines.append("")
    lines.extend([
        "## Interpretation boundary",
        "",
        "These are complete-Softmax implementation-path measurements. They are not EX2 operand-rate ATC values, pure SFU/MUFU circuit energy, or an additive decomposition across stages. Packed reduction uses half2 lanes across two rows before its block tree.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed analyzer for RTX 3090 whole-Softmax stage isolation."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="directory containing manifest.json, or a direct manifest.json path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="output directory (default: <run-dir>/analysis)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="allow a complete selected-stage subset, never missing rows within a selected stage",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_argument = args.run_dir.resolve()
    manifest_path = run_argument if run_argument.is_file() else run_argument / "manifest.json"
    run_dir = manifest_path.parent
    manifest = read_json(manifest_path)
    plans = validate_manifest(manifest, run_dir, args.allow_partial)
    cells = validate_artifacts(manifest, plans)
    require(len(cells) == len(plans) * 3, "validated row count differs from session plan")
    if not args.allow_partial:
        require(len(cells) == 27, "full stage-isolation analysis requires exactly 27 rows")

    absolute, paired = summarize(cells)
    if args.output_dir is None:
        output_dir = run_dir / "analysis"
    elif args.output_dir.is_absolute():
        output_dir = args.output_dir
    else:
        output_dir = run_dir / args.output_dir
    output_dir = output_dir.resolve()
    summary_csv = output_dir / "summary.csv"
    cells_csv = output_dir / "validated_cells.csv"
    analysis_json = output_dir / "analysis.json"
    summary_md = output_dir / "summary.md"
    atomic_write_csv(summary_csv, SUMMARY_FIELDS, absolute + paired)
    atomic_write_csv(cells_csv, CELL_FIELDS, [cell_row(cell) for cell in cells])
    artifacts = [
        {
            "stage_group": plan.stage,
            "session_id": plan.session_id,
            "session_index_within_stage": plan.session_index,
            "session_order": plan.session_order,
            "raw_csv": display_path(plan.raw_path),
            "raw_csv_sha256": plan.raw_sha256,
            "energy_trace_csv": display_path(plan.trace_path),
            "energy_trace_csv_sha256": plan.trace_sha256,
        }
        for plan in plans
    ]
    atomic_write_json(analysis_json, {
        "schema_version": "softmax_whole_precision_stage_isolation_analysis_v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass",
        "allow_partial": args.allow_partial,
        "manifest": {
            "path": display_path(manifest_path),
            "sha256": sha256_file(manifest_path),
            "run_tag": manifest["run_tag"],
            "protocol_revision": manifest["protocol_revision"],
        },
        "primary_metric": "net_pJ_per_logical_output_element",
        "validated_cell_count": len(cells),
        "artifacts": artifacts,
        "absolute_policy_summary": absolute,
        "paired_delta_summary": paired,
        "validated_cells": [cell_row(cell) for cell in cells],
        "interpretation_boundary": "complete Softmax policy comparison, not EX2 operand-rate ATC or pure SFU/MUFU energy",
    })
    atomic_write_text(summary_md, build_markdown(manifest_path, args.allow_partial, absolute, paired))
    print("analysis_status=pass")
    print(f"summary_csv={display_path(summary_csv)}")
    print(f"analysis_json={display_path(analysis_json)}")
    print(f"summary_md={display_path(summary_md)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
