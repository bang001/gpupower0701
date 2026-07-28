#!/usr/bin/env python3
"""Fail-closed analysis for the RTX 3090 fresh AB/BA confirmation.

The independent repeat is a fresh CUDA-process *pair session*, not either
individual role.  This analyzer never combines these six-pair candidate
summaries with the exploratory stage-isolation data that selected the two
contrasts.  It first binds manifest, frozen binary, runner, SASS audit, raw
CSV, and energy traces, then calculates descriptive paired summaries only.
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

MANIFEST_SCHEMA = "softmax_whole_precision_targeted_confirmation_manifest_v1"
MANIFEST_PROTOCOL = "rtx3090_softmax_whole_precision_targeted_confirmation_v1"
RAW_SCHEMA = "softmax_whole_precision_v3"
RAW_PROTOCOL = "whole_softmax_precision_canonical_common_v1"
DESIGN_ID = "targeted_confirmation_abba_v1"

BASELINE = "fp16_io_fp32_all"
SOFTMAX_COLS = 512
GRID_BLOCKS = 16
ROWS_PER_BLOCK = 2
LOGIT_SCALE = 4.0
# Match the duration-relative C++ conditioner gate for the new 5 s protocol:
# max(0.75, 25% of request) gives [3.75, 6.25] seconds. Historical 20 s
# artifacts stay immutable and are not inputs to this fresh-run analyzer.
PREHEAT_REQUESTED_S = 5.0
PREHEAT_MIN_S = 3.75
PREHEAT_MAX_S = 6.25
TRACE_MIN_UPDATES = 16
TRACE_MIN_R2 = 0.98
T95_N6 = 2.570581835636314
SASS_AUDIT_SCHEMA = "softmax_whole_precision_sass_audit_v1"
SASS_EXPECTED_ARCH = 86
SASS_EXPECTED_SCOPE = "whole_softmax_precision_kernel"


@dataclass(frozen=True)
class CandidateContract:
    identifier: str
    stage: str
    treatment: str
    treatment_contract: Mapping[str, str]


BASELINE_CONTRACT = {
    "input_dtype": "fp16",
    "output_dtype": "fp16",
    "exp_stage": "fp32",
    "reduction_stage": "fp32",
    "normalization_stage": "fp32",
}

CANDIDATES: dict[str, CandidateContract] = {
    "exp_packed": CandidateContract(
        "exp_packed",
        "exp",
        "exp_fp16x2",
        {
            "input_dtype": "fp16",
            "output_dtype": "fp16",
            "exp_stage": "fp16x2_packed",
            "reduction_stage": "fp32",
            "normalization_stage": "fp32",
        },
    ),
    "reduction_scalar": CandidateContract(
        "reduction_scalar",
        "reduction",
        "reduction_fp16_scalar",
        {
            "input_dtype": "fp16",
            "output_dtype": "fp16",
            "exp_stage": "fp32",
            "reduction_stage": "fp16_scalar",
            "normalization_stage": "fp32",
        },
    ),
}

EXPECTED_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "AB"),
    ("reduction_scalar", "BA"),
    ("exp_packed", "BA"),
    ("reduction_scalar", "AB"),
)

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
        "conditioning_mode",
        "conditioning_policy",
        "conditioning_requested_s",
        "conditioning_actual_s",
        "preparation_order",
        "preparation_policy_order",
        "validation_before_conditioning",
        "calibration_before_conditioning",
        "conditioning_calibration",
        "premeasurement_schedule_warmup",
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
    global_index: int
    candidate_id: str
    candidate_session_index: int
    order: str
    session_id: str
    schedule: tuple[str, str]
    raw_path: Path
    trace_path: Path
    raw_sha256: str
    trace_sha256: str


@dataclass(frozen=True)
class Cell:
    candidate_id: str
    stage: str
    session_id: str
    candidate_session_index: int
    global_session_index: int
    order: str
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


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower()
    )


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_path(value: str, run_dir: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists() or run_dir is None:
        return repo_path
    return run_dir / path


def read_json(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read {label} {path}: {error}") from error
    require(isinstance(payload, dict), f"{label} must contain a JSON object: {path}")
    return payload


def read_csv_strict(path: Path, fields_required: frozenset[str], label: str) -> list[dict[str, str]]:
    require(path.is_file(), f"{label} is missing: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            require(fields is not None and bool(fields), f"{label} has no header: {path}")
            require(len(fields) == len(set(fields)), f"{label} has duplicate fields: {path}")
            missing = sorted(fields_required - set(fields))
            require(not missing, f"{label} is missing fields {missing}: {path}")
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise EvidenceError(f"cannot read {label} {path}: {error}") from error
    require(bool(rows), f"{label} has no rows: {path}")
    for index, row in enumerate(rows, start=1):
        require(None not in row, f"{label} row {index} has excess CSV columns: {path}")
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


def manifest_int(value: Mapping[str, Any], field: str, label: str) -> int:
    raw = value.get(field)
    require(type(raw) is int, f"{label}.{field} must be a JSON integer")
    return raw


def close(actual: float, expected: float, label: str, *, rel: float = 1.0e-8, abs_: float = 1.0e-8) -> None:
    require(math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_),
            f"{label}: expected {expected}, got {actual}")


def expected_schedule(candidate: CandidateContract, order: str) -> tuple[str, str]:
    if order == "AB":
        return (BASELINE, candidate.treatment)
    if order == "BA":
        return (candidate.treatment, BASELINE)
    raise EvidenceError(f"unknown AB/BA order: {order}")


def require_file_hash(path_value: object, hash_value: object, label: str, run_dir: Path) -> Path:
    require(isinstance(path_value, str) and bool(path_value), f"{label}.path is missing")
    require(is_sha256(hash_value), f"{label}.sha256 is malformed")
    path = resolve_path(path_value, run_dir)
    require(path.is_file(), f"{label} is missing: {path}")
    require(sha256_file(path) == hash_value, f"{label} SHA-256 mismatch: {path}")
    return path


def validate_sass_audit(manifest: Mapping[str, Any], path: Path, binary_sha256: str) -> dict[str, Any]:
    binding = manifest.get("sass_audit")
    require(isinstance(binding, dict), "manifest has no bound SASS audit evidence")
    require(binding.get("path") == display_path(path),
            "selected SASS audit path does not match manifest binding")
    require(binding.get("sha256") == sha256_file(path),
            "selected SASS audit SHA-256 does not match manifest binding")
    require(binding.get("binary_sha256") == binary_sha256,
            "manifest SASS binding does not match frozen measurement binary")
    require(binding.get("evidence_generation") == "post_execution_static_audit_v1",
            "manifest SASS binding has an unsupported evidence-generation mode")
    require(binding.get("generated_after_execution") is True,
            "manifest SASS binding does not truthfully identify post-execution static evidence")
    audit = read_json(path, "SASS audit")
    require(audit.get("schema_version") == SASS_AUDIT_SCHEMA,
            "SASS audit schema is not the whole-Softmax audit schema")
    require(audit.get("overall", {}).get("pass") is True, "SASS audit did not pass")
    require(audit.get("overall", {}).get("fail_on_unexpected") is True,
            "SASS audit did not use --fail-on-unexpected")
    require(audit.get("overall", {}).get("unexpected_check_ids") == [],
            "SASS audit records unexpected failed checks")
    audit_binary = audit.get("binary", {})
    require(isinstance(audit_binary, dict), "SASS audit binary section is invalid")
    require(audit_binary.get("sha256") == binary_sha256,
            "SASS audit binary SHA-256 does not match the frozen measurement binary")
    contract = audit.get("contract", {})
    require(isinstance(contract, dict), "SASS audit contract is invalid")
    require(contract.get("expected_cuda_arch") == SASS_EXPECTED_ARCH,
            "SASS audit architecture is not sm86")
    require(contract.get("scope") == SASS_EXPECTED_SCOPE,
            "SASS audit scope is not the whole-Softmax precision kernel")
    require(contract.get("softmax_cols") == SOFTMAX_COLS,
            "SASS audit softmax width differs from the measured workload")
    require(contract.get("rows_per_block") == ROWS_PER_BLOCK,
            "SASS audit rows-per-block differs from the measured workload")
    return audit


def validate_manifest(manifest: dict[str, Any], run_dir: Path) -> list[SessionPlan]:
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "unsupported confirmation manifest schema")
    require(manifest.get("protocol_revision") == MANIFEST_PROTOCOL, "unsupported confirmation manifest protocol")
    require(isinstance(manifest.get("run_tag"), str) and bool(manifest["run_tag"]), "manifest run_tag is missing")
    binary = manifest.get("binary")
    runner = manifest.get("runner")
    source_binary = manifest.get("source_binary")
    design = manifest.get("design")
    execution = manifest.get("execution")
    origin = manifest.get("exploratory_origin")
    require(isinstance(binary, dict), "manifest.binary must be an object")
    require(isinstance(runner, dict), "manifest.runner must be an object")
    require(isinstance(source_binary, dict), "manifest.source_binary must be an object")
    require(isinstance(design, dict), "manifest.design must be an object")
    require(isinstance(execution, dict), "manifest.execution must be an object")
    require(isinstance(origin, dict), "manifest.exploratory_origin must be an object")
    require(binary.get("frozen_before_execution") is True, "measurement binary was not frozen")
    require(runner.get("frozen_before_execution") is True, "runner was not frozen")
    binary_path = require_file_hash(binary.get("path"), binary.get("sha256"), "manifest.binary", run_dir)
    require_file_hash(runner.get("path"), runner.get("sha256"), "manifest.runner", run_dir)
    require(is_sha256(source_binary.get("sha256")), "manifest source-binary SHA is malformed")
    require(binary_path.name == "a100_fp16_softmax_whole_precision_confirmation_energy",
            "manifest does not use the dedicated confirmation executable")

    origin_files: dict[str, Path] = {}
    for key in ("manifest_path", "analysis_path"):
        path_key = "manifest_path" if key == "manifest_path" else "analysis_path"
        hash_key = "manifest_sha256" if key == "manifest_path" else "analysis_sha256"
        origin_files[key] = require_file_hash(
            origin.get(path_key), origin.get(hash_key), f"exploratory_origin.{key}", run_dir
        )
    # New runs freeze the exploratory selection files before acquisition.  The
    # narrow legacy allowance keeps already-acquired v1 evidence analyzable
    # when it recorded hash-bound source paths before this hardening existed.
    if "frozen_before_execution" in origin:
        require(origin.get("frozen_before_execution") is True,
                "exploratory origin was not frozen before execution")
        require(origin.get("selection_hashes_recorded_before_execution") is True,
                "exploratory origin hashes were not recorded before execution")
        for label, path in origin_files.items():
            try:
                path.relative_to(run_dir)
            except ValueError as error:
                raise EvidenceError(
                    f"exploratory_origin.{label} is not frozen inside the run directory: {path}"
                ) from error
        require(origin.get("source_manifest_sha256") == origin.get("manifest_sha256"),
                "frozen exploratory manifest differs from its recorded source hash")
        require(origin.get("source_analysis_sha256") == origin.get("analysis_sha256"),
                "frozen exploratory analysis differs from its recorded source hash")
    require(origin.get("pooling_prohibited") == "true", "manifest does not prohibit exploratory pooling")

    require(design.get("experiment_kind") == "whole_softmax_targeted_confirmation",
            "manifest experiment kind drifted")
    require(design.get("target_profile") == "rtx3090", "manifest target profile drifted")
    require(design.get("baseline_policy") == BASELINE, "manifest baseline drifted")
    require(design.get("candidate_ids") == list(CANDIDATES), "manifest candidate order drifted")
    require(design.get("candidate_treatments") == {key: value.treatment for key, value in CANDIDATES.items()},
            "manifest candidate treatment contract drifted")
    require(design.get("order_algorithm") == "interleaved_AB3_BA3_per_candidate_v1",
            "manifest order algorithm drifted")
    require(design.get("fresh_binary_process_per_session") is True,
            "manifest lacks fresh process assertion")
    require(design.get("single_two_role_schedule_per_process") is True,
            "manifest lacks single pair assertion")
    require(design.get("conditioning_mode") == "canonical_common_v1",
            "manifest conditioning mode drifted")
    require(design.get("preparation_order") == "canonical_policy_enum_ascending",
            "manifest preparation order drifted")
    require(design.get("calibration_before_conditioning") is True,
            "manifest calibration phase drifted")
    require(design.get("conditioning_policy") == BASELINE,
            "manifest conditioning policy drifted")
    require(design.get("premeasurement_schedule_warmup") == "none",
            "manifest retains an unrecorded policy warm-up")
    require(design.get("exploratory_pooling_prohibited") is True,
            "manifest permits exploratory pooling")
    require(design.get("ex2_operand_rate_atc_compatible") is False,
            "manifest mislabels whole Softmax as EX2-compatible")
    require(manifest_int(design, "softmax_cols", "manifest.design") == SOFTMAX_COLS,
            "manifest softmax_cols drifted")
    require(manifest_int(design, "grid_blocks", "manifest.design") == GRID_BLOCKS,
            "manifest grid_blocks drifted")
    require(manifest_int(design, "rows_per_block", "manifest.design") == ROWS_PER_BLOCK,
            "manifest rows_per_block drifted")
    require(manifest_int(design, "seed", "manifest.design") > 0, "manifest seed is invalid")
    close(row_number(design, "logit_scale", "manifest.design"), LOGIT_SCALE, "manifest logit scale")
    close(row_number(design, "preheat_seconds", "manifest.design"), PREHEAT_REQUESTED_S,
          "manifest preheat")
    require(manifest_int(design, "energy_trace_min_updates", "manifest.design") == TRACE_MIN_UPDATES,
            "manifest trace gate drifted")
    require(manifest_int(design, "expected_sessions", "manifest.design") == len(EXPECTED_SEQUENCE),
            "manifest expected session count drifted")
    require(manifest_int(design, "expected_measured_roles", "manifest.design") == len(EXPECTED_SEQUENCE) * 2,
            "manifest expected role count drifted")
    require(execution.get("requested") is True, "manifest execution was not requested")
    require(execution.get("status") in {"complete", "complete_unanalyzed"},
            "manifest execution is not complete")

    sessions = manifest.get("sessions")
    require(isinstance(sessions, list) and len(sessions) == len(EXPECTED_SEQUENCE),
            "manifest session list does not match AB/BA plan")
    plans: list[SessionPlan] = []
    candidate_counts: dict[str, list[str]] = defaultdict(list)
    seen_ids: set[str] = set()
    seen_candidate_indices: set[tuple[str, int]] = set()
    for position, (session, expected) in enumerate(zip(sessions, EXPECTED_SEQUENCE), start=1):
        label = f"manifest.sessions[{position - 1}]"
        require(isinstance(session, dict), f"{label} must be an object")
        require(manifest_int(session, "global_session_index", label) == position,
                f"{label}.global_session_index is not contiguous")
        candidate_id, order = expected
        candidate = CANDIDATES[candidate_id]
        require(row_text(session, "candidate_id", label) == candidate_id,
                f"{label} candidate does not follow the interleaved plan")
        require(row_text(session, "stage", label) == candidate.stage, f"{label} stage drifted")
        require(row_text(session, "session_order", label) == order, f"{label} AB/BA order drifted")
        candidate_index = manifest_int(session, "session_index_within_candidate", label)
        require(1 <= candidate_index <= 6, f"{label} candidate session index is invalid")
        require((candidate_id, candidate_index) not in seen_candidate_indices,
                f"duplicate candidate/session identity: {candidate_id}/{candidate_index}")
        seen_candidate_indices.add((candidate_id, candidate_index))
        session_id = row_text(session, "session_id", label)
        require(session_id not in seen_ids, f"duplicate session ID: {session_id}")
        seen_ids.add(session_id)
        expected_pair = expected_schedule(candidate, order)
        schedule = session.get("policy_schedule")
        require(isinstance(schedule, list) and all(isinstance(item, str) for item in schedule),
                f"{label}.policy_schedule is invalid")
        require(tuple(schedule) == expected_pair, f"{label} schedule does not match AB/BA contract")
        require(row_text(session, "schedule_label", label) == ",".join(expected_pair),
                f"{label} schedule label mismatch")
        require(manifest_int(session, "expected_measured_roles", label) == 2,
                f"{label} does not plan exactly two roles")
        require(session.get("status") in {"complete", "complete_unanalyzed"},
                f"{label} is not complete")
        require(manifest_int(session, "returncode", label) == 0, f"{label} has a nonzero return code")
        raw_path = require_file_hash(session.get("raw_csv"), session.get("raw_csv_sha256"),
                                     f"{label}.raw_csv", run_dir)
        trace_path = require_file_hash(session.get("energy_trace_csv"), session.get("energy_trace_csv_sha256"),
                                       f"{label}.energy_trace_csv", run_dir)
        raw_sha = str(session["raw_csv_sha256"])
        trace_sha = str(session["energy_trace_csv_sha256"])
        plans.append(SessionPlan(position, candidate_id, candidate_index, order, session_id,
                                 expected_pair, raw_path, trace_path, raw_sha, trace_sha))
        candidate_counts[candidate_id].append(order)
    for candidate_id, orders in candidate_counts.items():
        require(len(orders) == 6 and orders.count("AB") == 3 and orders.count("BA") == 3,
                f"{candidate_id} does not have exact AB=3 / BA=3 balance")
    for candidate_id in CANDIDATES:
        require({index for current, index in seen_candidate_indices if current == candidate_id} == set(range(1, 7)),
                f"{candidate_id} lacks a complete six-session sequence")
    return plans


def validate_raw_row(
    row: Mapping[str, str],
    *,
    plan: SessionPlan,
    expected_policy: str,
    expected_sequence: int,
    binary_sha256: str,
    gpu_id: int,
    seed: int,
    label: str,
) -> Cell:
    candidate = CANDIDATES[plan.candidate_id]
    policy_contract = BASELINE_CONTRACT if expected_policy == BASELINE else candidate.treatment_contract
    require(row.get("schema_version") == RAW_SCHEMA, f"{label} raw schema drifted")
    require(row.get("experiment_kind") == "whole_softmax_targeted_confirmation",
            f"{label} experiment kind drifted")
    require(row.get("protocol_revision") == RAW_PROTOCOL, f"{label} raw protocol drifted")
    require(row.get("design_id") == DESIGN_ID, f"{label} design ID drifted")
    require(row.get("stage_group") == plan.candidate_id, f"{label} candidate ID mismatch")
    require(row.get("session_order") == plan.order, f"{label} AB/BA order mismatch")
    require(row.get("session_id") == plan.session_id, f"{label} session ID mismatch")
    require(row.get("schedule_id") == ",".join(plan.schedule), f"{label} schedule ID mismatch")
    require(row_int(row, "schedule_block", label, 0) == 0, f"{label} must have one schedule block")
    require(row_int(row, "sequence_index", label, 0) == expected_sequence,
            f"{label} sequence index mismatch")
    require(row.get("policy") == expected_policy, f"{label} policy mismatch")
    require(row.get("role") == "whole_softmax", f"{label} is not a whole Softmax role")
    for field, expected in policy_contract.items():
        require(row.get(field) == expected, f"{label} {field} expected {expected!r}, got {row.get(field)!r}")

    require(row_int(row, "gpu_id", label, 0) == gpu_id, f"{label} GPU index mismatch")
    require(row.get("compute_capability") == "8.6", f"{label} is not sm86 runtime")
    require(row_int(row, "cuda_binary_arch", label, 1) == 86, f"{label} does not load sm86 code")
    require(row_int(row, "runtime_sm_count", label, 1) == 82, f"{label} is not full 82-SM RTX 3090")
    require("rtx 3090" in row.get("gpu_name", "").lower(), f"{label} GPU name is not RTX 3090")
    pci_bus_id = row_text(row, "cuda_pci_bus_id", label)
    require(row_int(row, "grid_blocks", label, 1) == GRID_BLOCKS, f"{label} CTA grid drifted")
    require(row_int(row, "rows_per_block", label, 1) == ROWS_PER_BLOCK, f"{label} rows/CTA drifted")
    require(row_int(row, "softmax_cols", label, 1) == SOFTMAX_COLS, f"{label} S drifted")
    close(row_number(row, "logit_scale", label), LOGIT_SCALE, f"{label} logit scale")
    observed_seed = row_int(row, "seed", label, 1)
    require(observed_seed == seed, f"{label} input seed drifted")
    iters = row_int(row, "iters", label, 1)
    expected_elements = GRID_BLOCKS * ROWS_PER_BLOCK * SOFTMAX_COLS * iters
    logical_input = row_int(row, "logical_input_elements", label, 1)
    logical_output = row_int(row, "logical_output_elements", label, 1)
    require(logical_input == expected_elements, f"{label} logical input denominator mismatch")
    require(logical_output == expected_elements, f"{label} logical output denominator mismatch")
    require(row_int(row, "physical_input_bytes", label, 1) == logical_input * 2,
            f"{label} FP16 input byte contract failed")
    require(row_int(row, "physical_output_bytes", label, 1) == logical_output * 2,
            f"{label} FP16 output byte contract failed")

    elapsed = row_number(row, "elapsed_s", label)
    require(elapsed > 0.0, f"{label} elapsed time is not positive")
    delta_energy = row_number(row, "delta_E_J", label)
    net_energy = row_number(row, "net_E_J", label)
    gross_pj = row_number(row, "gross_pJ_per_output_element", label)
    net_pj = row_number(row, "net_pJ_per_output_element", label)
    close(gross_pj, delta_energy * 1.0e12 / logical_output, f"{label} gross pJ denominator",
          rel=1.0e-7, abs_=1.0e-6)
    close(net_pj, net_energy * 1.0e12 / logical_output, f"{label} net pJ denominator",
          rel=1.0e-7, abs_=1.0e-6)

    close(row_number(row, "preheat_requested_s", label), PREHEAT_REQUESTED_S, f"{label} preheat request")
    preheat_actual = row_number(row, "preheat_actual_s", label)
    require(PREHEAT_MIN_S <= preheat_actual <= PREHEAT_MAX_S,
            f"{label} preheat actual outside {PREHEAT_MIN_S:g}-{PREHEAT_MAX_S:g} seconds")
    require(row.get("preheat_policy") == BASELINE, f"{label} baseline preheat policy drifted")
    require(row.get("conditioning_mode") == "canonical_common_v1", f"{label} conditioning mode drifted")
    require(row.get("conditioning_policy") == BASELINE, f"{label} conditioning policy drifted")
    close(row_number(row, "conditioning_requested_s", label), PREHEAT_REQUESTED_S,
          f"{label} conditioning request")
    close(row_number(row, "conditioning_actual_s", label), preheat_actual,
          f"{label} condition/preheat actual agreement")
    require(row.get("preparation_order") == "canonical_policy_enum_ascending",
            f"{label} preparation order drifted")
    require(row.get("preparation_policy_order") == f"{BASELINE},{candidate.treatment}",
            f"{label} canonical preparation policy order drifted")
    require(row_bool(row, "validation_before_conditioning", label),
            f"{label} validation phase was not before conditioning")
    require(row_bool(row, "calibration_before_conditioning", label),
            f"{label} calibration phase was not before conditioning")
    require(row.get("conditioning_calibration") ==
            "one_second_and_role_iters_precomputed_before_conditioning",
            f"{label} conditioner calibration timing drifted")
    require(row.get("premeasurement_schedule_warmup") == "none",
            f"{label} contains an unrecorded policy warm-up")

    require(row.get("energy_trace_status") == "pass", f"{label} trace status is not pass")
    require(row.get("energy_source") == "nvml_total_energy_trace_theil_sen",
            f"{label} does not use qualified trace energy")
    require(row.get("measurement_scope") == "complete_softmax_forward",
            f"{label} measurement scope drifted")
    trace_samples = row_int(row, "energy_trace_sample_count", label, 1)
    trace_updates = row_int(row, "energy_trace_update_count", label, 0)
    trace_fit_points = row_int(row, "energy_trace_fit_point_count", label, 0)
    trace_r2 = row_number(row, "energy_trace_r2", label)
    require(trace_updates >= TRACE_MIN_UPDATES, f"{label} trace updates below gate")
    require(trace_fit_points >= TRACE_MIN_UPDATES, f"{label} trace fit points below gate")
    require(trace_samples >= trace_updates + 1, f"{label} trace sample/update counts inconsistent")
    require(trace_r2 >= TRACE_MIN_R2, f"{label} trace R2 below gate")

    require(row_bool(row, "smid_histogram_ok", label), f"{label} SMID placement gate failed")
    require(row_int(row, "smid_total_blocks", label, 1) == GRID_BLOCKS,
            f"{label} SMID CTA count drifted")
    require(row_int(row, "smid_unique", label, 1) <= 82, f"{label} invalid SMID count")
    require(row_int(row, "smid_max_blocks_on_sm", label, 1) <= GRID_BLOCKS,
            f"{label} invalid SMID maximum")

    require(row.get("validation_id") == "whole_precision_fp64_semantic_input_v1_pass",
            f"{label} numerical validation ID drifted")
    require(row_bool(row, "validation_pass", label), f"{label} numerical validation failed")
    validation_abs = row_number(row, "validation_max_abs_error", label)
    validation_sum = row_number(row, "validation_max_row_sum_error", label)
    validation_abs_gate = row_number(row, "validation_max_abs_gate", label)
    validation_sum_gate = row_number(row, "validation_max_row_sum_gate", label)
    require(validation_abs <= validation_abs_gate and validation_sum <= validation_sum_gate,
            f"{label} numerical error exceeds gate")
    require(row_int(row, "validation_nonfinite_count", label, 0) == 0,
            f"{label} validation contains nonfinite outputs")
    require(row.get("binary_sha256") == binary_sha256, f"{label} raw binary SHA mismatch")

    return Cell(
        candidate_id=plan.candidate_id,
        stage=candidate.stage,
        session_id=plan.session_id,
        candidate_session_index=plan.candidate_session_index,
        global_session_index=plan.global_index,
        order=plan.order,
        sequence_index=expected_sequence,
        policy=expected_policy,
        run_id=row_text(row, "run_id", label),
        seed=observed_seed,
        pci_bus_id=pci_bus_id,
        iters=iters,
        logical_output_elements=logical_output,
        elapsed_s=elapsed,
        net_energy_j=net_energy,
        net_pj=net_pj,
        gross_pj=gross_pj,
        validation_abs_error=validation_abs,
        validation_row_sum_error=validation_sum,
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
    by_run = {cell.run_id: cell for cell in cells}
    require(len(by_run) == len(cells), f"duplicate raw run IDs in {trace_path}")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for index, row in enumerate(trace_rows, start=1):
        label = f"trace {trace_path} row {index}"
        run_id = row_text(row, "run_id", label)
        require(run_id in by_run, f"{label} references unknown raw run")
        grouped[run_id].append(row)
    require(set(grouped) == set(by_run), f"trace {trace_path} does not cover each raw role")
    for run_id, cell in by_run.items():
        rows = grouped[run_id]
        label = f"trace {trace_path} run_id={run_id}"
        require(len(rows) == cell.trace_samples, f"{label} sample count mismatch")
        previous_time = -math.inf
        previous_energy = -math.inf
        sample_indexes: list[int] = []
        for position, row in enumerate(rows):
            item = f"{label} sample {position}"
            require(row.get("policy") == cell.policy, f"{item} policy mismatch")
            require(row_int(row, "schedule_block", item, 0) == 0, f"{item} block mismatch")
            require(row_int(row, "sequence_index", item, 0) == cell.sequence_index,
                    f"{item} sequence mismatch")
            sample_indexes.append(row_int(row, "sample_index", item, 0))
            start = row_number(row, "query_start_s", item)
            end = row_number(row, "query_end_s", item)
            midpoint = row_number(row, "query_midpoint_s", item)
            latency = row_number(row, "query_latency_s", item)
            row_number(row, "relative_to_kernel_start_s", item)
            energy = row_number(row, "energy_mJ", item)
            require(end >= start and latency >= 0.0, f"{item} query timing is invalid")
            require(midpoint >= previous_time and energy >= previous_energy,
                    f"{item} time or energy is non-monotonic")
            previous_time = midpoint
            previous_energy = energy
        require(sample_indexes == list(range(len(rows))), f"{label} sample indexes are not contiguous")


def validate_artifacts(manifest: dict[str, Any], plans: list[SessionPlan]) -> list[Cell]:
    binary_sha = str(manifest["binary"]["sha256"])
    design = manifest["design"]
    gpu_id = manifest_int(design, "gpu_id", "manifest.design")
    seed = manifest_int(design, "seed", "manifest.design")
    all_cells: list[Cell] = []
    for plan in plans:
        raw_rows = read_csv_strict(plan.raw_path, RAW_FIELDS, "raw CSV")
        require(len(raw_rows) == 2, f"raw CSV must contain exactly two pair roles: {plan.raw_path}")
        cells = [
            validate_raw_row(
                row,
                plan=plan,
                expected_policy=policy,
                expected_sequence=index,
                binary_sha256=binary_sha,
                gpu_id=gpu_id,
                seed=seed,
                label=f"raw {plan.raw_path} row {index + 1}",
            )
            for index, (row, policy) in enumerate(zip(raw_rows, plan.schedule))
        ]
        require(len({cell.run_id for cell in cells}) == 2, f"duplicate run ID within {plan.raw_path}")
        require(len({cell.preheat_actual_s for cell in cells}) == 1,
                f"pair does not share one common conditioning duration: {plan.raw_path}")
        trace_rows = read_csv_strict(plan.trace_path, TRACE_FIELDS, "energy trace CSV")
        validate_trace(trace_rows, cells, plan.trace_path)
        all_cells.extend(cells)
    require(len(all_cells) == len(plans) * 2, "validated cell count differs from plan")
    require(len({cell.run_id for cell in all_cells}) == len(all_cells), "run IDs duplicate across pairs")
    require(len({cell.seed for cell in all_cells}) == 1, "input seed differs across sessions")
    require(len({cell.pci_bus_id for cell in all_cells}) == 1, "PCI identity differs across sessions")
    return all_cells


def stats(values: list[float]) -> dict[str, float | int]:
    require(bool(values), "cannot summarize empty values")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def t95(mean: float, sample_std: float, count: int) -> tuple[float, float]:
    require(count == 6, "confirmation interval requires six fresh pair sessions")
    half_width = T95_N6 * sample_std / math.sqrt(count)
    return mean - half_width, mean + half_width


def cell_row(cell: Cell) -> dict[str, Any]:
    return {
        "candidate_id": cell.candidate_id,
        "stage": cell.stage,
        "global_session_index": cell.global_session_index,
        "session_id": cell.session_id,
        "session_index_within_candidate": cell.candidate_session_index,
        "session_order": cell.order,
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


PAIR_FIELDS = (
    "candidate_id", "stage", "global_session_index", "session_id", "session_index_within_candidate",
    "session_order", "baseline_policy", "treatment_policy", "baseline_net_pJ_per_logical_output_element",
    "treatment_net_pJ_per_logical_output_element", "delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
    "baseline_run_id", "treatment_run_id", "preheat_actual_s", "baseline_trace_r2", "treatment_trace_r2",
    "temperature_min_C", "temperature_max_C",
)
SUMMARY_FIELDS = (
    "candidate_id", "stage", "baseline_policy", "treatment_policy", "fresh_pair_session_count",
    "ab_session_count", "ba_session_count", "baseline_mean_net_pJ_per_logical_output_element",
    "treatment_mean_net_pJ_per_logical_output_element", "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
    "sample_std_delta_net_pJ_per_logical_output_element", "median_delta_net_pJ_per_logical_output_element",
    "min_delta_net_pJ_per_logical_output_element", "max_delta_net_pJ_per_logical_output_element",
    "t95_low_delta_net_pJ_per_logical_output_element", "t95_high_delta_net_pJ_per_logical_output_element",
    "negative_delta_session_count", "positive_delta_session_count", "zero_delta_session_count",
    "zero_excluded_by_descriptive_t95", "all_session_directions_same", "interpretation",
)
ORIENTATION_FIELDS = (
    "candidate_id", "session_order", "fresh_pair_session_count",
    "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
    "sample_std_delta_net_pJ_per_logical_output_element", "median_delta_net_pJ_per_logical_output_element",
)
QUALITY_FIELDS = ("check", "coverage", "result", "meaning")
CELL_FIELDS = tuple(cell_row.__annotations__) if False else (
    "candidate_id", "stage", "global_session_index", "session_id", "session_index_within_candidate",
    "session_order", "sequence_index", "policy", "run_id", "iters", "logical_output_elements", "elapsed_s",
    "net_E_J", "net_pJ_per_logical_output_element", "gross_pJ_per_logical_output_element",
    "validation_max_abs_error", "validation_max_row_sum_error", "preheat_actual_s",
    "energy_trace_sample_count", "energy_trace_update_count", "energy_trace_fit_point_count", "energy_trace_r2",
    "temperature_start_C", "temperature_end_C", "raw_csv", "trace_csv",
)


def summarize(cells: list[Cell]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_candidate_session: dict[tuple[str, str], dict[str, Cell]] = defaultdict(dict)
    for cell in cells:
        group = by_candidate_session[(cell.candidate_id, cell.session_id)]
        require(cell.policy not in group, f"duplicate policy within pair {cell.candidate_id}/{cell.session_id}")
        group[cell.policy] = cell
    pairs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    orientations: list[dict[str, Any]] = []
    for candidate_id, candidate in CANDIDATES.items():
        candidate_pairs: list[dict[str, Any]] = []
        for (current_candidate, session_id), values in by_candidate_session.items():
            if current_candidate != candidate_id:
                continue
            require(set(values) == {BASELINE, candidate.treatment},
                    f"pair lacks exact baseline/treatment: {candidate_id}/{session_id}")
            baseline = values[BASELINE]
            treatment = values[candidate.treatment]
            require(baseline.order == treatment.order, f"pair order mismatch: {candidate_id}/{session_id}")
            require(baseline.candidate_session_index == treatment.candidate_session_index,
                    f"pair session index mismatch: {candidate_id}/{session_id}")
            require(baseline.global_session_index == treatment.global_session_index,
                    f"pair global index mismatch: {candidate_id}/{session_id}")
            require(math.isclose(baseline.preheat_actual_s, treatment.preheat_actual_s,
                                 rel_tol=1.0e-12, abs_tol=1.0e-12),
                    f"pair conditioning duration mismatch: {candidate_id}/{session_id}")
            candidate_pairs.append(
                {
                    "candidate_id": candidate_id,
                    "stage": candidate.stage,
                    "global_session_index": baseline.global_session_index,
                    "session_id": session_id,
                    "session_index_within_candidate": baseline.candidate_session_index,
                    "session_order": baseline.order,
                    "baseline_policy": BASELINE,
                    "treatment_policy": candidate.treatment,
                    "baseline_net_pJ_per_logical_output_element": baseline.net_pj,
                    "treatment_net_pJ_per_logical_output_element": treatment.net_pj,
                    "delta_treatment_minus_baseline_net_pJ_per_logical_output_element": treatment.net_pj - baseline.net_pj,
                    "baseline_run_id": baseline.run_id,
                    "treatment_run_id": treatment.run_id,
                    "preheat_actual_s": baseline.preheat_actual_s,
                    "baseline_trace_r2": baseline.trace_r2,
                    "treatment_trace_r2": treatment.trace_r2,
                    "temperature_min_C": min(baseline.temp_before_c, baseline.temp_after_c,
                                             treatment.temp_before_c, treatment.temp_after_c),
                    "temperature_max_C": max(baseline.temp_before_c, baseline.temp_after_c,
                                             treatment.temp_before_c, treatment.temp_after_c),
                }
            )
        candidate_pairs.sort(key=lambda item: item["global_session_index"])
        require(len(candidate_pairs) == 6, f"{candidate_id} does not contain six paired sessions")
        require(sum(item["session_order"] == "AB" for item in candidate_pairs) == 3,
                f"{candidate_id} AB count is not three")
        require(sum(item["session_order"] == "BA" for item in candidate_pairs) == 3,
                f"{candidate_id} BA count is not three")
        deltas = [float(item["delta_treatment_minus_baseline_net_pJ_per_logical_output_element"])
                  for item in candidate_pairs]
        baseline_values = [float(item["baseline_net_pJ_per_logical_output_element"])
                           for item in candidate_pairs]
        treatment_values = [float(item["treatment_net_pJ_per_logical_output_element"])
                            for item in candidate_pairs]
        delta_stats = stats(deltas)
        low, high = t95(float(delta_stats["mean"]), float(delta_stats["sample_std"]), int(delta_stats["count"]))
        negative = sum(value < 0.0 for value in deltas)
        positive = sum(value > 0.0 for value in deltas)
        zero = len(deltas) - negative - positive
        summaries.append(
            {
                "candidate_id": candidate_id,
                "stage": candidate.stage,
                "baseline_policy": BASELINE,
                "treatment_policy": candidate.treatment,
                "fresh_pair_session_count": len(candidate_pairs),
                "ab_session_count": 3,
                "ba_session_count": 3,
                "baseline_mean_net_pJ_per_logical_output_element": statistics.fmean(baseline_values),
                "treatment_mean_net_pJ_per_logical_output_element": statistics.fmean(treatment_values),
                "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element": delta_stats["mean"],
                "sample_std_delta_net_pJ_per_logical_output_element": delta_stats["sample_std"],
                "median_delta_net_pJ_per_logical_output_element": delta_stats["median"],
                "min_delta_net_pJ_per_logical_output_element": delta_stats["minimum"],
                "max_delta_net_pJ_per_logical_output_element": delta_stats["maximum"],
                "t95_low_delta_net_pJ_per_logical_output_element": low,
                "t95_high_delta_net_pJ_per_logical_output_element": high,
                "negative_delta_session_count": negative,
                "positive_delta_session_count": positive,
                "zero_delta_session_count": zero,
                "zero_excluded_by_descriptive_t95": low > 0.0 or high < 0.0,
                "all_session_directions_same": negative == len(deltas) or positive == len(deltas),
                "interpretation": "descriptive targeted replication; no pooling with exploratory selection data",
            }
        )
        for order in ("AB", "BA"):
            ordered_deltas = [
                float(item["delta_treatment_minus_baseline_net_pJ_per_logical_output_element"])
                for item in candidate_pairs if item["session_order"] == order
            ]
            result = stats(ordered_deltas)
            orientations.append(
                {
                    "candidate_id": candidate_id,
                    "session_order": order,
                    "fresh_pair_session_count": result["count"],
                    "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element": result["mean"],
                    "sample_std_delta_net_pJ_per_logical_output_element": result["sample_std"],
                    "median_delta_net_pJ_per_logical_output_element": result["median"],
                }
            )
        pairs.extend(candidate_pairs)
    return pairs, summaries, orientations


def quality_rows(cells: list[Cell], plans: list[SessionPlan], sass_path: Path, sass: dict[str, Any]) -> list[dict[str, Any]]:
    temperatures = [value for cell in cells for value in (cell.temp_before_c, cell.temp_after_c)]
    preheat = [cell.preheat_actual_s for cell in cells]
    trace_r2 = [cell.trace_r2 for cell in cells]
    return [
        {
            "check": "evidence binding",
            "coverage": "12 fresh processes / 24 measured roles",
            "result": "pass",
            "meaning": "manifest, frozen binary/runner, all raw/trace SHA-256 values and exact AB/BA plan passed",
        },
        {
            "check": "AB/BA and conditioning",
            "coverage": "exp packed: AB=3 BA=3; reduction scalar: AB=3 BA=3",
            "result": "pass",
            "meaning": "canonical validation/calibration precede the 5 s common baseline conditioner; no unrecorded policy warm-up",
        },
        {
            "check": "trace, placement and numerics",
            "coverage": f"preheat {min(preheat):.3f}-{max(preheat):.3f} s; R² {min(trace_r2):.9f}-{max(trace_r2):.9f}; 24/24 roles",
            "result": "pass",
            "meaning": "qualified Theil-Sen trace, SMID placement, complete-Softmax denominator and FP64-reference numerical gates passed",
        },
        {
            "check": "recorded thermal context",
            "coverage": f"{min(temperatures)}-{max(temperatures)} °C",
            "result": "recorded",
            "meaning": "temperature is recorded context only, not a hard rejection gate or causal adjustment",
        },
        {
            "check": "sm86 compiled path",
            "coverage": f"{sass['binary']['sha256'][:12]} ({display_path(sass_path)})",
            "result": "pass",
            "meaning": "the frozen confirmation binary passed the whole-Softmax scalar/packed PTX/SASS audit",
        },
    ]


def atomic_write_csv(path: Path, fields: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise", lineterminator="\n")
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def fmt(value: object, digits: int = 3) -> str:
    return f"{float(value):,.{digits}f}"


def build_markdown(manifest_path: Path, summary: list[dict[str, Any]], quality: list[dict[str, Any]]) -> str:
    lines = [
        "# RTX 3090 Whole-Softmax targeted AB/BA confirmation summary",
        "",
        "All manifest, frozen-provenance, raw-schema, conditioning, trace, SMID, numerical, denominator, and SASS gates passed.",
        "",
        f"- Manifest: `{display_path(manifest_path)}`",
        "- Primary unit: net pJ / logical Softmax output element",
        "- Scope: two exploratory-selected implementation-path contrasts at fixed RTX 3090 sm86, S=512, grid CTA=16.",
        "- Independent unit: a fresh CUDA-process pair session (n=6 per candidate), not an individual role.",
        "- The exploratory stage-isolation result and this confirmation are not pooled.",
        "",
        "## Candidate summaries",
        "",
        "Positive Δ means the treatment used more observed net pJ/output than the same-session FP16-I/O + FP32-stage baseline.",
        "",
        "| candidate | treatment | n | AB / BA | mean Δ | SD | descriptive t95 | negative / positive |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            "| {candidate} | {treatment} | {n} | {ab} / {ba} | {mean} | {std} | [{low}, {high}] | {negative} / {positive} |".format(
                candidate=row["candidate_id"], treatment=row["treatment_policy"],
                n=row["fresh_pair_session_count"], ab=row["ab_session_count"], ba=row["ba_session_count"],
                mean=fmt(row["mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element"]),
                std=fmt(row["sample_std_delta_net_pJ_per_logical_output_element"]),
                low=fmt(row["t95_low_delta_net_pJ_per_logical_output_element"]),
                high=fmt(row["t95_high_delta_net_pJ_per_logical_output_element"]),
                negative=row["negative_delta_session_count"], positive=row["positive_delta_session_count"],
            )
        )
    lines.extend([
        "",
        "## Interpretation boundary",
        "",
        "This is a fresh targeted replication of two contrasts selected from an earlier exploratory run. It is not a broad all-stage confirmation, a pure SFU/MUFU or ALU energy measurement, an additive stage decomposition, or an EX2 operand-rate ATC result. Packed reduction still means half2 lanes across two independent CTA rows; normalization is outside this confirmation.",
        "",
        "The t95 intervals are descriptive n=6 paired summaries. Candidate selection was informed by the prior exploratory evidence, so the report does not claim population-wide or cross-platform superiority. AB/BA balances pair position and direct predecessor direction, but does not turn temperature or board state into a causal adjustment.",
        "",
        "## Quality gates",
        "",
        "| check | coverage | result |",
        "|---|---|---|",
    ])
    for row in quality:
        lines.append(f"| {row['check']} | {row['coverage']} | {row['result']} |")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="directory containing the confirmation manifest.json")
    parser.add_argument("--sass-audit", type=Path, default=None,
                        help="passing SASS audit for the frozen confirmation binary (default: <run-dir>/sass_audit.json)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="output directory (default: <run-dir>/analysis)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_argument = args.run_dir.resolve()
    manifest_path = run_argument if run_argument.is_file() else run_argument / "manifest.json"
    run_dir = manifest_path.parent
    manifest = read_json(manifest_path, "manifest")
    plans = validate_manifest(manifest, run_dir)
    sass_path = (args.sass_audit or (run_dir / "sass_audit.json")).resolve()
    sass = validate_sass_audit(manifest, sass_path, str(manifest["binary"]["sha256"]))
    cells = validate_artifacts(manifest, plans)
    require(len(cells) == 24, "confirmation requires exactly 24 validated role rows")
    pairs, summary, orientations = summarize(cells)
    require(len(pairs) == 12 and len(summary) == 2 and len(orientations) == 4,
            "unexpected confirmation summary cardinality")
    quality = quality_rows(cells, plans, sass_path, sass)

    if args.output_dir is None:
        output_dir = run_dir / "analysis"
    elif args.output_dir.is_absolute():
        output_dir = args.output_dir
    else:
        output_dir = run_dir / args.output_dir
    output_dir = output_dir.resolve()
    pair_csv = output_dir / "validated_pairs.csv"
    summary_csv = output_dir / "candidate_summary.csv"
    orientation_csv = output_dir / "orientation_diagnostics.csv"
    quality_csv = output_dir / "quality_gates.csv"
    cells_csv = output_dir / "validated_cells.csv"
    analysis_json = output_dir / "analysis.json"
    summary_md = output_dir / "summary.md"
    atomic_write_csv(pair_csv, PAIR_FIELDS, pairs)
    atomic_write_csv(summary_csv, SUMMARY_FIELDS, summary)
    atomic_write_csv(orientation_csv, ORIENTATION_FIELDS, orientations)
    atomic_write_csv(quality_csv, QUALITY_FIELDS, quality)
    atomic_write_csv(cells_csv, CELL_FIELDS, [cell_row(cell) for cell in cells])
    artifacts = [
        {
            "global_session_index": plan.global_index,
            "candidate_id": plan.candidate_id,
            "session_id": plan.session_id,
            "session_order": plan.order,
            "raw_csv": display_path(plan.raw_path),
            "raw_csv_sha256": plan.raw_sha256,
            "energy_trace_csv": display_path(plan.trace_path),
            "energy_trace_csv_sha256": plan.trace_sha256,
        }
        for plan in plans
    ]
    analysis = {
        "schema_version": "softmax_whole_precision_targeted_confirmation_analysis_v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass",
        "manifest": {
            "path": display_path(manifest_path),
            "sha256": sha256_file(manifest_path),
            "run_tag": manifest["run_tag"],
            "protocol_revision": manifest["protocol_revision"],
        },
        "sass_audit": {"path": display_path(sass_path), "sha256": sha256_file(sass_path),
                       "binary_sha256": sass["binary"]["sha256"]},
        "primary_metric": "net_pJ_per_logical_output_element",
        "validated_cell_count": len(cells),
        "validated_pair_count": len(pairs),
        "exploratory_pooling_prohibited": True,
        "artifacts": artifacts,
        "candidate_summary": summary,
        "validated_pairs": pairs,
        "orientation_diagnostics": orientations,
        "quality_gates": quality,
        "validated_cells": [cell_row(cell) for cell in cells],
        "interpretation_boundary": (
            "fresh targeted AB/BA replication of two exploratory-selected complete-Softmax "
            "contrasts; not pooled with exploratory data, not EX2 operand-rate ATC or pure unit energy"
        ),
    }
    atomic_write_json(analysis_json, analysis)
    atomic_write_text(summary_md, build_markdown(manifest_path, summary, quality))
    print("analysis_status=pass")
    print(f"candidate_summary_csv={display_path(summary_csv)}")
    print(f"analysis_json={display_path(analysis_json)}")
    print(f"summary_md={display_path(summary_md)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
