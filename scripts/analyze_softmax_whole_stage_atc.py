#!/usr/bin/env python3
"""Fail-closed analysis for whole-Softmax stage Operand-rate ATC runs.

The analyzer consumes one runner manifest and the manifest-bound raw/trace
files.  It never uses idle power in the primary estimator.  Each
``(stage, implementation, fresh session)`` cell contains two brackets:

* ``C-T-C``: interpolate active-control power at the treatment midpoint.
* ``T-C-T``: interpolate treatment power *and treatment result rate* at the
  control midpoint.

The two signed treatment-minus-control effects are averaged within the fresh
session.  The primary denominator is always one logical Softmax output
element for one added stage pass:

    N_added = grid_blocks * 2 rows/block * iters * softmax_cols

This is an incremental active-control contrast, not idle-subtracted complete
Softmax energy and not a pure opcode coefficient.

The analyzer also emits a clearly named, non-primary same-ITER gross
board-energy contrast from the same qualified trace:

    (E_treatment - E_control) / N_added

It uses the same midpoint interpolation as the primary brackets.  It is a
runtime-sensitive interpretation diagnostic, not a replacement for
Operand-rate ATC, and it does not use idle power.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_SCHEMA = "softmax_whole_stage_atc_manifest_v1"
RAW_SCHEMA = "softmax_whole_stage_atc_raw_v1"
TRACE_SCHEMA = "softmax_whole_stage_atc_trace_v1"
BINARY_CONTRACT_SCHEMA = "softmax_whole_stage_atc_binary_contract_v2"
NCU_AUDIT_SCHEMA = "softmax_whole_stage_atc_ncu_audit_v1"
EXPERIMENT_KIND = "softmax_whole_stage_operand_rate_atc"
PROTOCOL_REVISION = "softmax_whole_stage_operand_rate_atc_v2"

STAGES = ("exp", "reduction", "normalization")
POLICIES = ("fp32", "fp16_scalar", "fp16x2")
SESSION_ORDERS: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("ABC", POLICIES),
    2: ("BCA", ("fp16_scalar", "fp16x2", "fp32")),
    3: ("CAB", ("fp16x2", "fp32", "fp16_scalar")),
}
STAGE_ORDERS: dict[int, tuple[str, ...]] = {
    1: STAGES,
    2: (STAGES[1], STAGES[2], STAGES[0]),
    3: (STAGES[2], STAGES[0], STAGES[1]),
}
GLOBAL_SESSION_INDEX = {
    (stage, session_index): global_index
    for global_index, (session_index, stage) in enumerate(
        (
            (session_index, stage)
            for session_index in range(1, 4)
            for stage in STAGE_ORDERS[session_index]
        ),
        start=1,
    )
}
BRACKETS: dict[int, tuple[str, str, tuple[tuple[str, str], ...]]] = {
    0: (
        "forward",
        "C-T-C",
        (
            ("control_before", "control"),
            ("treatment_middle", "treatment"),
            ("control_after", "control"),
        ),
    ),
    1: (
        "reverse",
        "T-C-T",
        (
            ("treatment_before", "treatment"),
            ("control_middle", "control"),
            ("treatment_after", "treatment"),
        ),
    ),
}

ROWS_PER_BLOCK = 2
SOFTMAX_COLS = 1024
GRID_BLOCKS = 41
THREADS_PER_BLOCK = 256
NCU_LAUNCH_COUNT = 18
NCU_PAIR_COUNT = 9
NCU_CAPTURE_NAMES = ("raw_csv", "ncu_report", "target_stdout", "target_stderr")
TRACE_MIN_FIT_POINTS = 16
TRACE_MIN_R2 = 0.98
PREHEAT_REQUESTED_S = 5.0
PREHEAT_MIN_S = 3.75
PREHEAT_MAX_S = 6.25
ROLE_TARGET_SECONDS = 13.0
T95_DF2 = 4.302652729911275

RAW_REQUIRED = frozenset(
    {
        "schema_version",
        "experiment_kind",
        "protocol_revision",
        "run_id",
        "session_id",
        "session_index",
        "session_order",
        "session_role_index",
        "stage",
        "policy_position",
        "policy",
        "cell_id",
        "bracket_index",
        "orientation",
        "role_index",
        "role_id",
        "role_position",
        "role",
        "variant",
        "kernel_symbol",
        "same_kernel_symbol_status",
        "input_dtype",
        "output_dtype",
        "block_shared_bytes",
        "registers_per_thread",
        "sink_digest",
        "softmax_cols",
        "grid_blocks",
        "rows_per_block",
        "threads_per_block",
        "iters",
        "logical_output_elements",
        "calibration_mode",
        "calibration_reference_variant",
        "calibration_elapsed_s",
        "calibration_iters",
        "calibration_before_preheat",
        "role_target_seconds",
        "elapsed_s",
        "energy_trace_power_W",
        "energy_trace_status",
        "energy_trace_fit_point_count",
        "energy_trace_r2",
        "endpoint_delta_E_J",
        "delta_E_J",
        "idle_power_W",
        "idle_elapsed_s",
        "preheat_requested_s",
        "preheat_actual_s",
        "gpu_name",
        "gpu_id",
        "target_profile",
        "cuda_binary_arch",
        "cuda_pci_bus_id",
        "runtime_sm_count",
        "occupancy_max_blocks_per_sm",
        "static_single_wave_capacity_blocks",
        "static_single_wave_capacity_gate_pass",
        "smid_total_blocks",
        "smid_unique",
        "smid_max_blocks_on_sm",
        "smid_histogram_ok",
        "binary_sha256",
        "numerical_check_id",
        "control_treatment_output_bit_identical",
        "output_digest",
        "output_equivalence_status",
        "energy_trace_sample_count",
        "energy_trace_update_count",
        "energy_source",
        "energy_integration_method",
    }
)

TRACE_REQUIRED = frozenset(
    {
        "schema_version",
        "experiment_kind",
        "protocol_revision",
        "session_id",
        "stage",
        "policy",
        "cell_id",
        "bracket_index",
        "role_index",
        "role_id",
        "role",
        "variant",
        "run_id",
        "sample_index",
        "query_start_s",
        "query_end_s",
        "query_midpoint_s",
        "query_latency_s",
        "relative_to_kernel_start_s",
        "energy_mJ",
        "changed_from_previous",
        "in_fit_window",
        "binary_sha256",
    }
)

OPTIONAL_IDENTITY_FIELDS = (
    "input_dtype",
    "output_dtype",
    "block_shared_bytes",
    "registers_per_thread",
    "occupancy_max_blocks_per_sm",
    "static_single_wave_capacity_blocks",
)

OPTIONAL_GATE_FIELDS = (
    "validation_pass",
    "static_single_wave_capacity_gate_pass",
    "occupancy_gate_pass",
    "smid_histogram_ok",
    "smid_all_blocks_observed",
)


class AnalysisError(ValueError):
    """Raised when fail-closed evidence validation rejects a run."""


@dataclass(frozen=True)
class TraceFit:
    power_w: float
    r2: float
    fit_points: int
    fit_updates: int
    fit_span_s: float
    guard_s: float
    independently_reconstructed_window_difference_count: int
    kernel_midpoint_s: float
    max_query_latency_s: float


@dataclass(frozen=True)
class RoleEvidence:
    row: dict[str, str]
    fit: TraceFit
    logical_elements: int
    elapsed_s: float
    result_rate_per_s: float


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AnalysisError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"{path}: invalid JSON: {error}") from error
    require(isinstance(payload, dict), f"{path}: JSON root must be an object")
    return payload


def read_csv_strict(
    path: Path, required_fields: frozenset[str], label: str
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            require(bool(fields), f"{label}: CSV header is missing")
            require(len(fields) == len(set(fields)), f"{label}: duplicate CSV header")
            missing = sorted(required_fields - set(fields))
            require(not missing, f"{label}: missing fields: {','.join(missing)}")
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise AnalysisError(f"{label}: cannot read {path}: {error}") from error
    require(bool(rows), f"{label}: CSV has no rows")
    return rows, fields


def row_text(row: Mapping[str, Any], field: str, label: str) -> str:
    value = str(row.get(field, "")).strip()
    require(bool(value), f"{label}: {field} is empty")
    return value


def row_int(
    row: Mapping[str, Any], field: str, label: str, minimum: int | None = None
) -> int:
    try:
        value = int(str(row.get(field, "")))
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"{label}: {field} is not an integer") from error
    if minimum is not None:
        require(value >= minimum, f"{label}: {field} must be >= {minimum}")
    return value


def row_number(
    row: Mapping[str, Any], field: str, label: str, minimum: float | None = None
) -> float:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"{label}: {field} is not numeric") from error
    require(math.isfinite(value), f"{label}: {field} is non-finite")
    if minimum is not None:
        require(value >= minimum, f"{label}: {field} must be >= {minimum}")
    return value


def parse_bool(value: Any, label: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "pass"}:
        return True
    if normalized in {"0", "false", "no", "fail"}:
        return False
    raise AnalysisError(f"{label}: invalid boolean {value!r}")


def close(
    actual: float,
    expected: float,
    label: str,
    *,
    rel: float = 1.0e-6,
    abs_: float = 1.0e-9,
) -> None:
    require(
        math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_),
        f"{label}: {actual!r} != {expected!r}",
    )


def resolve_artifact_path(value: str, run_dir: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    local = (run_dir / candidate).resolve()
    if local.exists():
        return local
    return (REPO_ROOT / candidate).resolve()


def resolve_audit_artifact_path(value: Any, audit_path: Path) -> Path:
    candidate = Path(str(value))
    require(
        not candidate.is_absolute(),
        "ncu_audit artifact paths must be relative to audit.json",
    )
    return (audit_path.parent / candidate).resolve()


def verify_ncu_hashed_artifact(
    metadata: Any, *, audit_path: Path, label: str
) -> tuple[Path, str, int]:
    require(isinstance(metadata, dict), f"{label}: metadata is missing")
    assert isinstance(metadata, dict)
    path_value = str(metadata.get("path", "")).strip()
    digest = str(metadata.get("sha256", "")).strip()
    require(bool(path_value), f"{label}: path is missing")
    require(is_sha256(digest), f"{label}: SHA-256 invalid")
    path = resolve_audit_artifact_path(path_value, audit_path)
    require(path.is_file(), f"{label}: file is missing: {path}")
    require(sha256_file(path) == digest, f"{label}: SHA-256 mismatch")
    try:
        recorded_bytes = int(metadata.get("bytes", -1))
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"{label}: byte count is not an integer") from error
    require(
        recorded_bytes == path.stat().st_size,
        f"{label}: byte count mismatch",
    )
    return path, digest, recorded_bytes


def validate_bound_ncu_audit(
    manifest: Mapping[str, Any], run_dir: Path
) -> dict[str, Any]:
    """Revalidate the immutable dynamic-instruction audit and every capture."""

    binding = manifest.get("ncu_audit")
    require(
        isinstance(binding, dict),
        "real run requires a manifest-bound ncu_audit",
    )
    assert isinstance(binding, dict)
    require(
        binding.get("schema_version") == NCU_AUDIT_SCHEMA
        and binding.get("status") == "pass"
        and binding.get("target_profile") == "rtx3090"
        and binding.get("energy_usable") is False
        and binding.get("launch_count") == NCU_LAUNCH_COUNT
        and binding.get("pair_count") == NCU_PAIR_COUNT
        and binding.get("coordinate")
        == {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
        },
        "ncu_audit manifest binding contract mismatch",
    )
    binary = manifest.get("binary")
    require(isinstance(binary, dict), "manifest binary binding missing")
    assert isinstance(binary, dict)
    binary_hash = str(binary.get("sha256", ""))
    require(
        binding.get("binary_sha256") == binary_hash,
        "ncu_audit binary hash mismatch",
    )
    audit_path = resolve_artifact_path(str(binding.get("path", "")), run_dir)
    audit_hash = str(binding.get("sha256", ""))
    require(audit_path.is_file(), f"ncu_audit path missing: {audit_path}")
    require(is_sha256(audit_hash), "ncu_audit SHA-256 invalid")
    require(sha256_file(audit_path) == audit_hash, "ncu_audit SHA-256 mismatch")
    audit = read_json(audit_path)

    coordinate = audit.get("coordinate")
    audit_binary = audit.get("binary")
    require(
        audit.get("schema_version") == NCU_AUDIT_SCHEMA
        and audit.get("status") == "pass"
        and audit.get("artifact_path_base") == "audit_json_parent"
        and audit.get("target_profile") == "rtx3090"
        and isinstance(coordinate, dict)
        and coordinate.get("softmax_cols") == SOFTMAX_COLS
        and coordinate.get("grid_blocks") == GRID_BLOCKS
        and coordinate.get("threads_per_block") == THREADS_PER_BLOCK
        and coordinate.get("rows_per_block") == ROWS_PER_BLOCK
        and isinstance(audit_binary, dict)
        and audit_binary.get("sha256") == binary_hash
        and audit.get("launch_count") == NCU_LAUNCH_COUNT
        and audit.get("pair_count") == NCU_PAIR_COUNT
        and audit.get("energy_usable") is False,
        "ncu_audit content contract mismatch",
    )
    assert isinstance(audit_binary, dict)
    binary_contract = audit_binary.get("contract")
    require(
        isinstance(binary_contract, dict)
        and binary_contract.get("schema_version") == BINARY_CONTRACT_SCHEMA
        and binary_contract.get("kernel_contract")
        == "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"
        and binary_contract.get("same_kernel_symbol_control_treatment") is True
        and binary_contract.get("treatment_invariant_sink") is True,
        "ncu_audit binary contract mismatch",
    )

    provenance_hash = str(audit.get("provenance_payload_sha256", ""))
    require(is_sha256(provenance_hash), "ncu_audit provenance hash invalid")
    canonical_payload = dict(audit)
    canonical_payload.pop("provenance_payload_sha256", None)
    canonical_bytes = (
        json.dumps(
            canonical_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    require(
        hashlib.sha256(canonical_bytes).hexdigest() == provenance_hash,
        "ncu_audit provenance payload hash mismatch",
    )

    pairs = audit.get("pairs")
    launches = audit.get("launches")
    require(
        isinstance(pairs, list) and len(pairs) == NCU_PAIR_COUNT,
        "ncu_audit must contain exactly nine stage-policy pairs",
    )
    require(
        isinstance(launches, list) and len(launches) == NCU_LAUNCH_COUNT,
        "ncu_audit must contain exactly 18 target launches",
    )
    expected_pairs = {(stage, policy) for stage in STAGES for policy in POLICIES}
    observed_pairs: set[tuple[str, str]] = set()
    symbols_by_pair: dict[tuple[str, str], str] = {}
    for pair in pairs:
        require(isinstance(pair, dict), "ncu_audit pair entry is malformed")
        assert isinstance(pair, dict)
        key = (str(pair.get("stage", "")), str(pair.get("policy", "")))
        require(
            key in expected_pairs and key not in observed_pairs,
            f"ncu_audit duplicate or unexpected pair: {key}",
        )
        observed_pairs.add(key)
        checks = pair.get("checks")
        require(
            pair.get("status") == "pass"
            and pair.get("failure_reasons") == []
            and isinstance(checks, dict)
            and bool(checks)
            and all(value is True for value in checks.values()),
            f"ncu_audit pair checks failed: {key}",
        )
        control_symbol = str(pair.get("control_kernel_name", "")).strip()
        treatment_symbol = str(pair.get("treatment_kernel_name", "")).strip()
        require(
            bool(control_symbol)
            and control_symbol == treatment_symbol
            and checks.get("same_demangled_kernel_symbol") is True,
            f"ncu_audit same-symbol gate failed: {key}",
        )
        require(
            pair.get("grid_blocks") == GRID_BLOCKS
            and pair.get("threads_per_block") == THREADS_PER_BLOCK,
            f"ncu_audit launch coordinate mismatch: {key}",
        )
        symbols_by_pair[key] = control_symbol
    require(observed_pairs == expected_pairs, "ncu_audit stage-policy matrix incomplete")

    capture_payload = audit.get("captures")
    capture_binding = binding.get("captures")
    require(
        isinstance(capture_payload, dict)
        and set(capture_payload) == set(STAGES)
        and isinstance(capture_binding, dict)
        and set(capture_binding) == set(STAGES),
        "ncu_audit stage capture bindings are incomplete",
    )
    assert isinstance(capture_payload, dict)
    assert isinstance(capture_binding, dict)
    verified_captures: dict[str, dict[str, dict[str, Any]]] = {}
    for stage in STAGES:
        stage_payload = capture_payload[stage]
        stage_binding = capture_binding[stage]
        require(
            isinstance(stage_payload, dict)
            and stage_payload.get("stage") == stage
            and isinstance(stage_binding, dict),
            f"ncu_audit {stage} capture is malformed",
        )
        assert isinstance(stage_payload, dict)
        assert isinstance(stage_binding, dict)
        verified_captures[stage] = {}
        for name in NCU_CAPTURE_NAMES:
            path, digest, byte_count = verify_ncu_hashed_artifact(
                stage_payload.get(name),
                audit_path=audit_path,
                label=f"ncu_audit {stage}/{name}",
            )
            bound = stage_binding.get(name)
            require(
                isinstance(bound, dict)
                and bound.get("sha256") == digest
                and int(bound.get("bytes", -1)) == byte_count
                and resolve_artifact_path(str(bound.get("path", "")), run_dir)
                == path,
                f"manifest ncu_audit {stage}/{name} binding mismatch",
            )
            verified_captures[stage][name] = {
                "path": str(path),
                "sha256": digest,
                "bytes": byte_count,
            }

    summary_path, summary_hash, summary_bytes = verify_ncu_hashed_artifact(
        audit.get("summary_csv"),
        audit_path=audit_path,
        label="ncu_audit summary_csv",
    )
    summary_binding = binding.get("summary_csv")
    require(
        isinstance(summary_binding, dict)
        and summary_binding.get("sha256") == summary_hash
        and int(summary_binding.get("bytes", -1)) == summary_bytes
        and resolve_artifact_path(str(summary_binding.get("path", "")), run_dir)
        == summary_path,
        "manifest ncu_audit summary_csv binding mismatch",
    )
    summary_rows, _ = read_csv_strict(
        summary_path,
        frozenset(
            {
                "schema_version",
                "stage",
                "policy",
                "same_demangled_kernel_symbol",
                "grid_blocks",
                "threads_per_block",
                "control_kernel_name",
                "treatment_kernel_name",
                "global_store_equal",
                "status",
                "failure_reasons",
                "binary_sha256",
                "raw_ncu_csv_sha256",
                "ncu_report_sha256",
                "energy_usable",
            }
        ),
        "ncu_audit summary_csv",
    )
    require(len(summary_rows) == NCU_PAIR_COUNT, "ncu_audit summary row count mismatch")
    summary_pairs: set[tuple[str, str]] = set()
    for row in summary_rows:
        key = (row_text(row, "stage", "ncu summary"), row_text(row, "policy", "ncu summary"))
        require(
            key in expected_pairs and key not in summary_pairs,
            f"ncu_audit summary duplicate or unexpected pair: {key}",
        )
        summary_pairs.add(key)
        require(
            row.get("schema_version") == NCU_AUDIT_SCHEMA
            and row.get("status") == "pass"
            and row.get("failure_reasons", "") == ""
            and row.get("binary_sha256") == binary_hash
            and parse_bool(row.get("same_demangled_kernel_symbol"), "ncu summary symbol")
            and parse_bool(row.get("global_store_equal"), "ncu summary global store")
            and not parse_bool(row.get("energy_usable"), "ncu summary energy"),
            f"ncu_audit summary gate failed: {key}",
        )
        require(
            row_int(row, "grid_blocks", "ncu summary") == GRID_BLOCKS
            and row_int(row, "threads_per_block", "ncu summary")
            == THREADS_PER_BLOCK
            and row.get("control_kernel_name") == symbols_by_pair[key]
            and row.get("treatment_kernel_name") == symbols_by_pair[key]
            and row.get("raw_ncu_csv_sha256")
            == verified_captures[key[0]]["raw_csv"]["sha256"]
            and row.get("ncu_report_sha256")
            == verified_captures[key[0]]["ncu_report"]["sha256"],
            f"ncu_audit summary evidence mismatch: {key}",
        )
    require(summary_pairs == expected_pairs, "ncu_audit summary matrix incomplete")
    return {
        "path": str(audit_path),
        "sha256": audit_hash,
        "binary_sha256": binary_hash,
        "launch_count": NCU_LAUNCH_COUNT,
        "pair_count": NCU_PAIR_COUNT,
        "energy_usable": False,
    }


def manifest_hash(
    row: Mapping[str, Any], keys: Sequence[str], label: str
) -> str:
    observed = [str(row.get(key, "")).strip() for key in keys if str(row.get(key, "")).strip()]
    require(len(observed) == 1, f"{label}: expected exactly one SHA-256 field among {keys}")
    require(is_sha256(observed[0]), f"{label}: invalid SHA-256")
    return observed[0]


def theil_sen_slope_w(points: list[tuple[float, float]]) -> float:
    slopes: list[float] = []
    for left in range(len(points)):
        for right in range(left + 1, len(points)):
            delta_t = points[right][0] - points[left][0]
            if delta_t > 0.0:
                slopes.append((points[right][1] - points[left][1]) / delta_t / 1000.0)
    require(bool(slopes), "trace: insufficient distinct timestamps for Theil-Sen slope")
    return statistics.median(slopes)


def trace_r2(points: list[tuple[float, float]], slope_w: float) -> float:
    origin = points[0][0]
    slope_mj_per_s = slope_w * 1000.0
    intercept = statistics.median(
        energy_mj - slope_mj_per_s * (timestamp - origin)
        for timestamp, energy_mj in points
    )
    mean_energy = statistics.fmean(energy_mj for _, energy_mj in points)
    residual = sum(
        (
            energy_mj
            - (intercept + slope_mj_per_s * (timestamp - origin))
        )
        ** 2
        for timestamp, energy_mj in points
    )
    total = sum((energy_mj - mean_energy) ** 2 for _, energy_mj in points)
    return 1.0 - residual / total if total > 0.0 else math.nan


def linear_percentile(values: Sequence[float], quantile: float) -> float:
    require(bool(values), "percentile requires at least one value")
    require(0.0 <= quantile <= 1.0, "percentile quantile is outside [0,1]")
    ordered = sorted(values)
    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (
        position - lower
    )


def fit_trace(
    rows: list[dict[str, str]],
    raw: Mapping[str, str],
    label: str,
    minimum_fit_points: int,
) -> TraceFit:
    require(bool(rows), f"{label}: trace role is missing")
    parsed: list[tuple[float, float, float, float, float, bool, bool, int]] = []
    for trace_row in rows:
        trace_label = f"{label}/sample={trace_row.get('sample_index', '?')}"
        index = row_int(trace_row, "sample_index", trace_label, 0)
        start = row_number(trace_row, "query_start_s", trace_label)
        end = row_number(trace_row, "query_end_s", trace_label)
        midpoint = row_number(trace_row, "query_midpoint_s", trace_label)
        latency = row_number(trace_row, "query_latency_s", trace_label, 0.0)
        relative = row_number(trace_row, "relative_to_kernel_start_s", trace_label)
        energy = row_number(trace_row, "energy_mJ", trace_label, 0.0)
        changed = parse_bool(
            trace_row.get("changed_from_previous", ""),
            f"{trace_label}: changed_from_previous",
        )
        in_fit = parse_bool(
            trace_row.get("in_fit_window", ""), f"{trace_label}: in_fit_window"
        )
        require(start <= midpoint <= end, f"{trace_label}: query midpoint outside query")
        close(end - start, latency, f"{trace_label}: query latency", rel=1.0e-4, abs_=1.0e-6)
        parsed.append((midpoint, energy, relative, latency, start, changed, in_fit, index))
    parsed.sort(key=lambda item: item[7])
    require(
        [item[7] for item in parsed] == list(range(len(parsed))),
        f"{label}: sample_index must be contiguous from zero",
    )
    require(
        all(parsed[index][0] > parsed[index - 1][0] for index in range(1, len(parsed))),
        f"{label}: query midpoints are not strictly increasing",
    )
    require(
        all(parsed[index][1] >= parsed[index - 1][1] for index in range(1, len(parsed))),
        f"{label}: NVML energy counter is non-monotonic",
    )
    for index in range(1, len(parsed)):
        expected_changed = parsed[index][1] > parsed[index - 1][1]
        require(
            parsed[index][5] == expected_changed,
            f"{label}: changed_from_previous mismatch at sample {index}",
        )
    require(
        parsed[0][5] is False,
        f"{label}: first trace sample must not claim a previous counter update",
    )
    changed_indices = [0] + [
        index
        for index in range(1, len(parsed))
        if parsed[index][1] > parsed[index - 1][1]
    ]
    update_intervals = [
        parsed[right][0] - parsed[left][0]
        for left, right in zip(changed_indices, changed_indices[1:])
    ]
    require(
        bool(update_intervals) and all(value > 0.0 for value in update_intervals),
        f"{label}: cannot reconstruct positive NVML counter-update intervals",
    )
    guard_s = 2.0 * linear_percentile(update_intervals, 0.99)
    kernel_starts = [midpoint - relative for midpoint, _, relative, *_ in parsed]
    kernel_start = statistics.median(kernel_starts)
    require(
        max(kernel_starts) - min(kernel_starts) <= 0.05,
        f"{label}: inconsistent trace kernel-start reconstruction",
    )
    elapsed = row_number(raw, "elapsed_s", label, 1.0e-12)
    reconstructed_window = [
        kernel_start + guard_s <= item[0] <= kernel_start + elapsed - guard_s
        for item in parsed
    ]
    recorded_window = [item[6] for item in parsed]
    recorded_indices = [
        index for index, included in enumerate(recorded_window) if included
    ]
    reconstructed_indices = [
        index for index, included in enumerate(reconstructed_window) if included
    ]
    require(
        bool(recorded_indices) and bool(reconstructed_indices),
        f"{label}: fit window reconstruction is empty",
    )
    require(
        recorded_indices
        == list(range(recorded_indices[0], recorded_indices[-1] + 1)),
        f"{label}: recorded fit window is not contiguous",
    )
    require(
        reconstructed_indices
        == list(
            range(reconstructed_indices[0], reconstructed_indices[-1] + 1)
        ),
        f"{label}: reconstructed fit window is not contiguous",
    )
    window_differences = [
        index
        for index, (recorded, reconstructed) in enumerate(
            zip(recorded_window, reconstructed_window)
        )
        if recorded != reconstructed
    ]
    # The producer gates against host_start/host_end while the portable raw
    # artifact records CUDA-event elapsed time.  Those clocks may place one
    # final polling sample on opposite sides of the end boundary.  The start
    # boundary must match exactly and at most that one terminal sample may
    # differ.
    require(
        recorded_indices[0] == reconstructed_indices[0]
        and len(window_differences) <= 1
        and (
            not window_differences
            or window_differences[0]
            == max(recorded_indices[-1], reconstructed_indices[-1])
        ),
        f"{label}: recorded fit window disagrees with independent guard reconstruction",
    )
    guarded: list[tuple[float, float]] = []
    for midpoint, energy, _, _, _, changed, in_fit, index in parsed:
        if in_fit and (index == 0 or changed):
            if not guarded or energy > guarded[-1][1]:
                guarded.append((midpoint, energy))
    require(
        len(guarded) >= minimum_fit_points,
        f"{label}: guarded trace has {len(guarded)} fit points; "
        f"requires {minimum_fit_points}",
    )
    slope = theil_sen_slope_w(guarded)
    require(math.isfinite(slope) and slope > 0.0, f"{label}: invalid trace slope")
    r2 = trace_r2(guarded, slope)
    require(math.isfinite(r2) and r2 >= TRACE_MIN_R2, f"{label}: trace R2 below gate")
    raw_status = row_text(raw, "energy_trace_status", label)
    require(raw_status == "pass", f"{label}: raw trace status is not pass")
    raw_fit_points = row_int(raw, "energy_trace_fit_point_count", label, minimum_fit_points)
    require(
        raw_fit_points == len(guarded),
        f"{label}: raw/trace guarded fit-point count mismatch "
        f"({raw_fit_points} != {len(guarded)})",
    )
    raw_power = row_number(raw, "energy_trace_power_W", label, 0.0)
    close(raw_power, slope, f"{label}: raw/trace power", rel=2.0e-3, abs_=1.0e-3)
    raw_r2 = row_number(raw, "energy_trace_r2", label)
    require(raw_r2 >= TRACE_MIN_R2, f"{label}: raw trace R2 below gate")
    close(raw_r2, r2, f"{label}: raw/trace R2", rel=2.0e-3, abs_=1.0e-4)
    require(
        row_int(raw, "energy_trace_sample_count", label, 1) == len(parsed),
        f"{label}: raw/trace sample-count mismatch",
    )
    require(
        row_int(raw, "energy_trace_update_count", label, minimum_fit_points)
        >= minimum_fit_points,
        f"{label}: raw trace update count below gate",
    )

    return TraceFit(
        power_w=slope,
        r2=r2,
        fit_points=len(guarded),
        fit_updates=max(0, len(guarded) - 1),
        fit_span_s=guarded[-1][0] - guarded[0][0],
        guard_s=guard_s,
        independently_reconstructed_window_difference_count=len(
            window_differences
        ),
        kernel_midpoint_s=kernel_start + elapsed / 2.0,
        max_query_latency_s=max(item[3] for item in parsed),
    )


def lerp(before: float, after: float, weight: float) -> float:
    return before + weight * (after - before)


def interpolation_weight(
    before_midpoint: float, middle_midpoint: float, after_midpoint: float, label: str
) -> float:
    require(after_midpoint > before_midpoint, f"{label}: outer midpoint order invalid")
    weight = (middle_midpoint - before_midpoint) / (
        after_midpoint - before_midpoint
    )
    require(0.0 <= weight <= 1.0, f"{label}: interpolation weight outside [0,1]")
    return weight


def optional_numeric_metadata(
    rows: Sequence[Mapping[str, str]], fields: Sequence[str], label: str
) -> dict[str, float | str]:
    output: dict[str, float | str] = {}
    headers = set(rows[0]) if rows else set()
    for field in fields:
        if field not in headers:
            output[f"{field}_status"] = "not_recorded"
            continue
        values = [row_number(row, field, label) for row in rows]
        if field.startswith("temp_"):
            require(
                all(-100.0 < value < 200.0 for value in values),
                f"{label}: invalid temperature metadata",
            )
        if "clock" in field:
            require(all(value > 0.0 for value in values), f"{label}: invalid clock metadata")
        output[f"{field}_status"] = "recorded"
        output[f"{field}_min"] = min(values)
        output[f"{field}_max"] = max(values)
    return output


def validate_manifest(
    manifest: dict[str, Any], run_dir: Path
) -> tuple[
    list[dict[str, Any]], int, frozenset[str], frozenset[str]
]:
    require(
        manifest.get("schema_version") == MANIFEST_SCHEMA,
        "manifest schema_version mismatch",
    )
    require(
        manifest.get("experiment_kind") == EXPERIMENT_KIND,
        "manifest experiment_kind mismatch",
    )
    require(
        manifest.get("protocol_revision") == PROTOCOL_REVISION,
        "manifest protocol_revision mismatch",
    )
    require(manifest.get("status") == "complete", "manifest status must be complete")

    require(
        manifest.get("design_id") == "rtx3090_s1024_q50_stage_atc_3x3x3_v2",
        "manifest design_id mismatch",
    )
    profile = manifest.get("profile")
    coordinate = manifest.get("coordinate")
    design = manifest.get("design")
    metric = manifest.get("metric")
    placement = manifest.get("placement_contract")
    thermal = manifest.get("thermal_contract")
    energy = manifest.get("energy_contract")
    schemas = manifest.get("schemas")
    for value, label in (
        (profile, "profile"),
        (coordinate, "coordinate"),
        (design, "design"),
        (metric, "metric"),
        (placement, "placement_contract"),
        (thermal, "thermal_contract"),
        (energy, "energy_contract"),
        (schemas, "schemas"),
    ):
        require(isinstance(value, dict), f"manifest {label} is missing")
    assert isinstance(profile, dict)
    assert isinstance(coordinate, dict)
    assert isinstance(design, dict)
    assert isinstance(metric, dict)
    assert isinstance(placement, dict)
    assert isinstance(thermal, dict)
    assert isinstance(energy, dict)
    assert isinstance(schemas, dict)
    require(profile.get("name") == "rtx3090", "manifest profile mismatch")
    require(int(profile.get("runtime_sm_count", -1)) == 82, "runtime SM mismatch")
    require(profile.get("compute_capability") == "8.6", "compute capability mismatch")
    require(profile.get("cuda_arch") == "sm_86", "native architecture mismatch")
    require(design.get("stages") == list(STAGES), "manifest stage list mismatch")
    require(design.get("policies") == list(POLICIES), "manifest policy list mismatch")
    require(
        design.get("session_orders") == ["ABC", "BCA", "CAB"],
        "manifest session-order list mismatch",
    )
    require(
        design.get("global_stage_orders")
        == {
            "ABC": ["exp", "reduction", "normalization"],
            "BCA": ["reduction", "normalization", "exp"],
            "CAB": ["normalization", "exp", "reduction"],
        },
        "manifest global stage-order balance mismatch",
    )
    require(
        design.get("bracket_schedule") == ["C-T-C", "T-C-T"],
        "manifest bracket schedule mismatch",
    )
    require(
        design.get("static_audit_required_for_headline") is True
        and design.get("ncu_audit_required_for_headline") is True,
        "manifest headline audit requirements are incomplete",
    )
    require(int(design.get("fresh_sessions_per_stage", -1)) == 3, "session count mismatch")
    require(int(design.get("total_cells", -1)) == 27, "cell count mismatch")
    require(
        int(design.get("total_process_sessions", -1)) == 9,
        "process-session count mismatch",
    )
    require(
        int(design.get("measured_roles_per_cell", -1)) == 6,
        "roles/cell mismatch",
    )
    require(
        int(design.get("total_measured_roles", -1)) == 162,
        "total role count mismatch",
    )
    require(int(coordinate.get("rows_per_block", -1)) == ROWS_PER_BLOCK, "rows/block mismatch")
    require(int(coordinate.get("softmax_cols", -1)) == SOFTMAX_COLS, "S mismatch")
    require(int(coordinate.get("grid_blocks", -1)) == GRID_BLOCKS, "grid mismatch")
    require(
        int(coordinate.get("threads_per_block", -1)) == THREADS_PER_BLOCK,
        "threads/block mismatch",
    )
    require(
        coordinate.get("iters") == "calibrated_per_stage_policy_and_observed_in_raw"
        and coordinate.get("logical_output_elements_per_role")
        == "grid_blocks*observed_iters*rows_per_block*softmax_cols",
        "manifest per-cell ITER/denominator contract mismatch",
    )
    require(
        math.isclose(float(coordinate.get("role_target_seconds", math.nan)), ROLE_TARGET_SECONDS),
        "manifest role target mismatch",
    )
    calibration = design.get("calibration")
    require(isinstance(calibration, dict), "manifest calibration design is missing")
    assert isinstance(calibration, dict)
    require(
        calibration.get("mode")
        == "per_stage_policy_treatment_before_common_preheat"
        and calibration.get("reference_variant") == "treatment"
        and math.isclose(
            float(calibration.get("target_seconds", math.nan)),
            ROLE_TARGET_SECONDS,
        )
        and calibration.get("freeze_scope")
        == "one cell ITER reused by its six C/T roles"
        and calibration.get("global_fixed_iters") == "prohibited",
        "manifest per-cell calibration contract mismatch",
    )
    require(
        metric.get("name") == "stage_ATC_pJ_per_logical_output_element",
        "manifest primary metric mismatch",
    )
    require(
        placement.get("runtime_sm_count") == 82
        and placement.get("underfilled_grid") is True
        and placement.get("capacity_formula")
        == "runtime_sm_count*occupancy_max_blocks_per_sm"
        and placement.get("capacity_gate")
        == "grid_blocks<=static_single_wave_capacity_blocks"
        and placement.get("smid_total_blocks") == GRID_BLOCKS
        and placement.get("smid_unique") == GRID_BLOCKS
        and placement.get("smid_max_blocks_on_sm") == 1
        and placement.get("smid_histogram_ok") is True,
        "manifest placement contract mismatch",
    )
    require(
        metric.get("primary_denominator") == "logical_softmax_output_element",
        "manifest primary denominator mismatch",
    )
    require(
        metric.get("idle_usage") == "diagnostic_only_excluded_from_ATC_numerator"
        and metric.get("sink_usage")
        == "treatment_invariant_observer_not_an_effect_source"
        and metric.get("not_total_softmax_energy") is True,
        "manifest metric scope/idle/sink contract mismatch",
    )
    preheat = float(thermal.get("preheat_requested_s", math.nan))
    require(
        math.isfinite(preheat) and math.isclose(preheat, PREHEAT_REQUESTED_S),
        "manifest preheat request mismatch",
    )
    require(
        thermal.get("preheat_actual_gate_s") == [PREHEAT_MIN_S, PREHEAT_MAX_S],
        "manifest preheat gate mismatch",
    )
    require(
        energy.get("source") == "nvml_total_energy"
        and energy.get("integration") == "guarded_interior_theil_sen",
        "manifest energy source/integration mismatch",
    )
    require(
        energy.get("idle_is_diagnostic_only") is True,
        "manifest must prohibit idle power in the primary estimator",
    )
    minimum_fit_points = int(energy.get("trace_min_updates", -1))
    require(
        minimum_fit_points >= TRACE_MIN_FIT_POINTS,
        "manifest trace fit-point gate is too weak",
    )
    require(
        schemas.get("binary_contract") == BINARY_CONTRACT_SCHEMA,
        "manifest binary-contract schema mismatch",
    )
    require(
        schemas.get("ncu_audit") == NCU_AUDIT_SCHEMA,
        "manifest NCU-audit schema mismatch",
    )
    require(schemas.get("raw") == RAW_SCHEMA, "manifest raw schema mismatch")
    require(schemas.get("trace") == TRACE_SCHEMA, "manifest trace schema mismatch")
    raw_required_fields = frozenset(str(field) for field in schemas.get("raw_required_fields", []))
    trace_required_fields = frozenset(
        str(field) for field in schemas.get("trace_required_fields", [])
    )
    require(
        RAW_REQUIRED <= raw_required_fields,
        "manifest raw required-field contract is incomplete",
    )
    require(
        TRACE_REQUIRED <= trace_required_fields,
        "manifest trace required-field contract is incomplete",
    )

    for artifact_name in ("binary", "runner"):
        artifact = manifest.get(artifact_name)
        require(isinstance(artifact, dict), f"manifest {artifact_name} binding missing")
        path = resolve_artifact_path(str(artifact.get("path", "")), run_dir)
        expected = str(artifact.get("sha256", ""))
        require(path.is_file(), f"manifest {artifact_name} path missing: {path}")
        require(is_sha256(expected), f"manifest {artifact_name} SHA-256 invalid")
        require(
            sha256_file(path) == expected,
            f"manifest {artifact_name} SHA-256 mismatch",
        )
    if manifest.get("analysis_test_fixture") is not True:
        static_audit = manifest.get("static_audit")
        require(
            isinstance(static_audit, dict),
            "real run requires a manifest-bound static_audit",
        )
        assert isinstance(static_audit, dict)
        require(
            static_audit.get("status") == "pass",
            "static_audit status must be pass",
        )
        require(
            static_audit.get("binary_sha256") == manifest["binary"]["sha256"],
            "static_audit binary hash mismatch",
        )
        audit_path = resolve_artifact_path(str(static_audit.get("path", "")), run_dir)
        audit_hash = str(static_audit.get("sha256", ""))
        require(audit_path.is_file(), f"static_audit path missing: {audit_path}")
        require(is_sha256(audit_hash), "static_audit SHA-256 invalid")
        require(sha256_file(audit_path) == audit_hash, "static_audit SHA-256 mismatch")
        audit_payload = read_json(audit_path)
        require(
            audit_payload.get("schema_version")
            == "softmax_whole_stage_atc_static_audit_v2"
            and audit_payload.get("status") == "pass"
            and audit_payload.get("binary_sha256")
            == manifest["binary"]["sha256"]
            and audit_payload.get("target_profile") == "rtx3090"
            and str(audit_payload.get("cuda_arch")) == "86"
            and audit_payload.get("kernel_contract")
            == "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"
            and audit_payload.get("required_specialization_count") == 9
            and audit_payload.get("observed_specialization_count") == 9,
            "static_audit content contract mismatch",
        )
        checks = audit_payload.get("checks")
        require(
            isinstance(checks, dict)
            and bool(checks)
            and all(value == "pass" for value in checks.values()),
            "static_audit checks are missing or failed",
        )
        captures = audit_payload.get("captures")
        bound_captures = static_audit.get("captures")
        require(
            isinstance(captures, dict) and isinstance(bound_captures, dict),
            "static_audit capture bindings missing",
        )
        assert isinstance(captures, dict)
        assert isinstance(bound_captures, dict)
        for capture_name in ("ptx", "sass", "list_elf"):
            capture = captures.get(capture_name)
            bound_capture = bound_captures.get(capture_name)
            require(
                isinstance(capture, dict) and isinstance(bound_capture, dict),
                f"static_audit {capture_name} capture missing",
            )
            assert isinstance(capture, dict)
            assert isinstance(bound_capture, dict)
            capture_path = Path(str(capture.get("path", "")))
            if not capture_path.is_absolute():
                capture_path = (audit_path.parent / capture_path).resolve()
            capture_hash = str(capture.get("sha256", ""))
            require(
                capture_path.is_file()
                and is_sha256(capture_hash)
                and sha256_file(capture_path) == capture_hash,
                f"static_audit {capture_name} capture hash mismatch",
            )
            require(
                bound_capture.get("sha256") == capture_hash,
                f"manifest static_audit {capture_name} binding mismatch",
            )
        validate_bound_ncu_audit(manifest, run_dir)

    sessions = manifest.get("sessions")
    require(isinstance(sessions, list), "manifest sessions must be a list")
    require(len(sessions) == 9, f"manifest requires 9 stage sessions; got {len(sessions)}")
    expected_keys = {(stage, index) for stage in STAGES for index in range(1, 4)}
    observed_keys: set[tuple[str, int]] = set()
    identifiers: set[str] = set()
    for session in sessions:
        require(isinstance(session, dict), "manifest session entry must be an object")
        stage = str(session.get("stage", ""))
        index = int(session.get("session_index", -1))
        key = (stage, index)
        require(key in expected_keys, f"unexpected stage/session key {key}")
        require(key not in observed_keys, f"duplicate stage/session key {key}")
        observed_keys.add(key)
        expected_order, expected_schedule = SESSION_ORDERS[index]
        require(
            session.get("session_order") == expected_order,
            f"{stage}/session{index}: order mismatch",
        )
        require(
            session.get("policy_schedule") == list(expected_schedule),
            f"{stage}/session{index}: policy schedule mismatch",
        )
        require(
            int(session.get("expected_cells", -1)) == 3,
            f"{stage}/session{index}: expected_cells mismatch",
        )
        require(
            int(session.get("expected_roles", -1)) == 18,
            f"{stage}/session{index}: expected_roles mismatch",
        )
        require(
            session.get("status") == "complete",
            f"{stage}/session{index}: status must be complete",
        )
        require(
            session.get("fresh_cuda_process") is True
            and session.get("persistent_cuda_context") is True,
            f"{stage}/session{index}: process/context scope mismatch",
        )
        require(
            int(session.get("global_session_index", -1))
            == GLOBAL_SESSION_INDEX[(stage, index)],
            f"{stage}/session{index}: global session order mismatch",
        )
        require(
            int(session.get("returncode", -1)) == 0,
            f"{stage}/session{index}: process returncode mismatch",
        )
        session_id = str(session.get("session_id", "")).strip()
        require(session_id and session_id not in identifiers, "duplicate/empty session_id")
        identifiers.add(session_id)
        plan = session.get("cells")
        require(isinstance(plan, list) and len(plan) == 3, f"{session_id}: cells invalid")
        require(
            [str(item.get("policy", "")) for item in plan] == list(expected_schedule),
            f"{session_id}: cells policy order mismatch",
        )
        require(
            [int(item.get("policy_position", -1)) for item in plan] == [0, 1, 2],
            f"{session_id}: cells position mismatch",
        )
        require(
            all(str(item.get("stage", "")) == stage for item in plan),
            f"{session_id}: cells stage mismatch",
        )
        require(
            all(
                item.get("bracket_schedule") == ["C-T-C", "T-C-T"]
                and int(item.get("expected_roles", -1)) == 6
                for item in plan
            ),
            f"{session_id}: cells bracket/role contract mismatch",
        )
        execution = session.get("execution_schedule")
        require(
            isinstance(execution, list) and len(execution) == 18,
            f"{session_id}: execution_schedule invalid",
        )
        expected_execution: list[tuple[Any, ...]] = []
        for policy_position, policy in enumerate(expected_schedule):
            for bracket_index in sorted(BRACKETS):
                orientation, _, role_contract = BRACKETS[bracket_index]
                for role_index, (role_position, variant) in enumerate(role_contract):
                    expected_execution.append(
                        (
                            policy_position,
                            policy,
                            bracket_index,
                            orientation,
                            role_index,
                            role_position,
                            variant,
                            variant,
                        )
                    )
        observed_execution = [
            (
                int(item.get("policy_position", -1)),
                str(item.get("policy", "")),
                int(item.get("bracket_index", -1)),
                str(item.get("orientation", "")),
                int(item.get("role_index", -1)),
                str(item.get("role_position", "")),
                str(item.get("role", "")),
                str(item.get("variant", "")),
            )
            for item in execution
        ]
        require(
            observed_execution == expected_execution,
            f"{session_id}: expanded execution schedule mismatch",
        )
        require(
            [int(item.get("session_role_index", -1)) for item in execution]
            == list(range(18)),
            f"{session_id}: execution session_role_index mismatch",
        )
        validation = session.get("validation")
        require(isinstance(validation, dict), f"{session_id}: validation sidecar missing")
        require(
            int(validation.get("raw_rows", -1)) == 18
            and int(validation.get("trace_roles", -1)) == 18
            and int(validation.get("same_kernel_symbol_cells", -1)) == 3
            and int(validation.get("output_equivalent_cells", -1)) == 3,
            f"{session_id}: runner validation counts mismatch",
        )
    require(observed_keys == expected_keys, "manifest 3×3 stage/session schedule incomplete")
    return sessions, minimum_fit_points, raw_required_fields, trace_required_fields


def validate_raw_identity_and_gates(
    rows: list[dict[str, str]], label: str
) -> tuple[int, float]:
    required_equal = (
        "session_id",
        "session_index",
        "session_order",
        "stage",
        "policy_position",
        "policy",
        "cell_id",
        "kernel_symbol",
        "softmax_cols",
        "grid_blocks",
        "rows_per_block",
        "threads_per_block",
        "iters",
        "logical_output_elements",
        "gpu_name",
        "compute_capability",
        "cuda_binary_arch",
        "cuda_pci_bus_id",
        "binary_sha256",
        "numerical_check_id",
        "control_treatment_output_bit_identical",
        "output_digest",
        "output_equivalence_status",
        *OPTIONAL_IDENTITY_FIELDS,
    )
    for field in required_equal:
        if field in rows[0]:
            values = {row.get(field, "") for row in rows}
            mismatch_kind = (
                "denominator identity mismatch"
                if field == "logical_output_elements"
                else "identity mismatch"
            )
            require(
                len(values) == 1 and "" not in values,
                f"{label}: {mismatch_kind} {field}",
            )
    require(
        all(row.get("schema_version") == RAW_SCHEMA for row in rows),
        f"{label}: raw schema mismatch",
    )
    require(
        all(row.get("experiment_kind") == EXPERIMENT_KIND for row in rows),
        f"{label}: raw experiment_kind mismatch",
    )
    require(
        all(row.get("protocol_revision") == PROTOCOL_REVISION for row in rows),
        f"{label}: raw protocol mismatch",
    )
    require(
        all(row.get("same_kernel_symbol_status") == "pass" for row in rows),
        f"{label}: same-kernel-symbol gate failed",
    )
    require(
        all(
            row.get("calibration_mode")
            == "per_stage_policy_treatment_before_common_preheat"
            and row.get("calibration_reference_variant") == "treatment"
            and parse_bool(row.get("calibration_before_preheat", ""), label)
            for row in rows
        ),
        f"{label}: per-cell treatment calibration contract mismatch",
    )
    require(
        all(
            ROLE_TARGET_SECONDS * 0.90
            <= row_number(row, "calibration_elapsed_s", label)
            <= ROLE_TARGET_SECONDS * 1.30
            and row_number(row, "role_target_seconds", label)
            == ROLE_TARGET_SECONDS
            for row in rows
        ),
        f"{label}: treatment calibration duration is outside the 0.90x-1.30x target gate",
    )
    require(
        all(row.get("target_profile") == "rtx3090" for row in rows)
        and all(row_int(row, "gpu_id", label, 0) == 0 for row in rows)
        and all(row_int(row, "cuda_binary_arch", label, 0) == 86 for row in rows),
        f"{label}: GPU/profile/native-arch identity mismatch",
    )
    require(
        all(row.get("energy_source") == "nvml_total_energy" for row in rows)
        and all("theil" in row.get("energy_integration_method", "").lower() for row in rows),
        f"{label}: energy source/integration mismatch",
    )
    require(
        all(parse_bool(row.get("control_treatment_output_bit_identical", ""), label) for row in rows),
        f"{label}: control/treatment output is not bit-identical",
    )
    require(
        all(row.get("output_equivalence_status") == "pass" for row in rows),
        f"{label}: output equivalence gate failed",
    )
    require(
        len({row.get("output_digest", "") for row in rows}) == 1
        and bool(rows[0].get("output_digest", "")),
        f"{label}: output digest mismatch",
    )
    sink_digests = {row.get("sink_digest", "") for row in rows}
    require(
        len(sink_digests) == 1 and "" not in sink_digests,
        f"{label}: sink must be stable and treatment-invariant; "
        "the bound SASS audit proves the added-stage dataflow",
    )
    require(
        all(row.get("numerical_check_id", "").endswith("_pass") for row in rows),
        f"{label}: numerical validation ID is not a pass ID",
    )
    for field in OPTIONAL_GATE_FIELDS:
        if field in rows[0]:
            require(
                all(parse_bool(row.get(field, ""), f"{label}: {field}") for row in rows),
                f"{label}: {field} failed",
            )
    for row in rows:
        grid = row_int(row, "grid_blocks", label, 1)
        runtime_sms = row_int(row, "runtime_sm_count", label, 1)
        occupancy = row_int(row, "occupancy_max_blocks_per_sm", label, 1)
        capacity = row_int(row, "static_single_wave_capacity_blocks", label, 1)
        unique = row_int(row, "smid_unique", label, 1)
        total_blocks = row_int(row, "smid_total_blocks", label, 1)
        max_blocks = row_int(row, "smid_max_blocks_on_sm", label, 1)
        require(runtime_sms == 82, f"{label}: runtime SM count mismatch")
        require(
            capacity == runtime_sms * occupancy
            and parse_bool(row.get("static_single_wave_capacity_gate_pass", ""), label)
            and grid <= capacity,
            f"{label}: occupancy/static capacity gate failed",
        )
        require(
            total_blocks == grid
            and unique == grid
            and max_blocks == 1
            and parse_bool(row.get("smid_histogram_ok", ""), label),
            f"{label}: underfilled-grid SMID placement mismatch",
        )

    grid = row_int(rows[0], "grid_blocks", label, 1)
    rows_per_block = row_int(rows[0], "rows_per_block", label, 1)
    iters = row_int(rows[0], "iters", label, 1)
    softmax_cols = row_int(rows[0], "softmax_cols", label, 1)
    require(grid == GRID_BLOCKS, f"{label}: grid mismatch")
    require(rows_per_block == ROWS_PER_BLOCK, f"{label}: rows/block mismatch")
    require(softmax_cols == SOFTMAX_COLS, f"{label}: S mismatch")
    require(
        row_int(rows[0], "threads_per_block", label, 1) == THREADS_PER_BLOCK,
        f"{label}: threads/block mismatch",
    )
    denominator = grid * rows_per_block * iters * softmax_cols
    for row in rows:
        require(
            row_int(row, "calibration_iters", label, 1) == iters,
            f"{label}: cell ITER differs from calibrated treatment ITER",
        )
        require(
            row_number(row, "calibration_elapsed_s", label, 1.0e-12) > 0.0,
            f"{label}: calibration elapsed time invalid",
        )
        close(
            row_number(row, "role_target_seconds", label, 0.0),
            ROLE_TARGET_SECONDS,
            f"{label}: role target",
        )
        require(
            row_int(row, "logical_output_elements", label, 1) == denominator,
            f"{label}: denominator is not grid×2×ITER×S",
        )
        elapsed = row_number(row, "elapsed_s", label, 1.0e-12)
        idle_power = row_number(row, "idle_power_W", label, 0.0)
        idle_elapsed = row_number(row, "idle_elapsed_s", label, 1.0e-12)
        idle_delta = row_number(row, "idle_delta_E_J", label, 0.0)
        require(
            math.isfinite(idle_power * idle_elapsed),
            f"{label}: idle diagnostic is invalid",
        )
        close(
            idle_power,
            idle_delta / idle_elapsed,
            f"{label}: idle diagnostic power",
            rel=2.0e-3,
            abs_=1.0e-3,
        )
        row_number(row, "delta_E_J", label, 0.0)
        endpoint = row_number(row, "endpoint_delta_E_J", label, 0.0)
        energy_before = row_number(row, "E_before_mJ", label, 0.0)
        energy_after = row_number(row, "E_after_mJ", label, 0.0)
        require(energy_after >= energy_before, f"{label}: endpoint counter regressed")
        close(
            endpoint,
            (energy_after - energy_before) / 1000.0,
            f"{label}: endpoint energy calculation",
            rel=2.0e-3,
            abs_=1.0e-3,
        )
        measurement_start = row_number(row, "measurement_start_epoch_ms", label)
        measurement_end = row_number(row, "measurement_end_epoch_ms", label)
        require(
            measurement_end >= measurement_start,
            f"{label}: measurement epoch interval regressed",
        )
        if "preheat_actual_s" in row:
            close(
                row_number(row, "preheat_requested_s", label, 0.0),
                PREHEAT_REQUESTED_S,
                f"{label}: requested preheat",
            )
            preheat = row_number(row, "preheat_actual_s", label, 0.0)
            require(
                PREHEAT_MIN_S <= preheat <= PREHEAT_MAX_S,
                f"{label}: actual preheat outside gate",
            )
    optional_numeric_metadata(
        rows,
        (
            "temp_before_C",
            "temp_after_C",
            "clock_sm_before_mhz",
            "clock_sm_after_mhz",
            "clock_mem_before_mhz",
            "clock_mem_after_mhz",
        ),
        label,
    )
    return denominator, statistics.fmean(
        row_number(row, "idle_power_W", label, 0.0) for row in rows
    )


def analyze_cell(
    rows: list[dict[str, str]],
    trace_by_key: Mapping[tuple[str, str, str], list[dict[str, str]]],
    minimum_fit_points: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    require(len(rows) == 6, f"cell requires six roles; got {len(rows)}")
    cell_id = row_text(rows[0], "cell_id", "cell")
    label = f"cell={cell_id}"
    denominator, mean_idle_power = validate_raw_identity_and_gates(rows, label)
    by_bracket: dict[int, list[dict[str, str]]] = defaultdict(list)
    role_ids: set[str] = set()
    run_ids: set[str] = set()
    for row in rows:
        bracket = row_int(row, "bracket_index", label, 0)
        require(bracket in BRACKETS, f"{label}: invalid bracket_index")
        by_bracket[bracket].append(row)
        role_id = row_text(row, "role_id", label)
        require(role_id not in role_ids, f"{label}: duplicate role_id")
        role_ids.add(role_id)
        run_id = row_text(row, "run_id", label)
        require(run_id not in run_ids, f"{label}: duplicate run_id")
        run_ids.add(run_id)
    require(set(by_bracket) == set(BRACKETS), f"{label}: bracket set mismatch")

    effects: list[dict[str, Any]] = []
    role_diagnostics: list[dict[str, Any]] = []
    for bracket_index in sorted(BRACKETS):
        orientation, bracket_schedule, expected_roles = BRACKETS[bracket_index]
        bracket_rows = sorted(
            by_bracket[bracket_index],
            key=lambda row: row_int(row, "role_index", label, 0),
        )
        require(
            [row_int(row, "role_index", label, 0) for row in bracket_rows] == [0, 1, 2],
            f"{label}/{orientation}: role_index mismatch",
        )
        require(
            all(row.get("orientation") == orientation for row in bracket_rows),
            f"{label}/{orientation}: orientation mismatch",
        )
        require(
            [
                (
                    row.get("role_position", ""),
                    row.get("role", ""),
                    row.get("variant", ""),
                )
                for row in bracket_rows
            ]
            == [(position, variant, variant) for position, variant in expected_roles],
            f"{label}/{orientation}: role-position/role/variant sequence mismatch",
        )
        evidences: list[RoleEvidence] = []
        for raw in bracket_rows:
            key = (
                row_text(raw, "session_id", label),
                cell_id,
                row_text(raw, "role_id", label),
            )
            trace_rows = trace_by_key.get(key, [])
            fit = fit_trace(
                trace_rows,
                raw,
                f"{label}/{orientation}/{raw['role_position']}",
                minimum_fit_points,
            )
            logical = row_int(raw, "logical_output_elements", label, 1)
            elapsed = row_number(raw, "elapsed_s", label, 1.0e-12)
            evidence = RoleEvidence(
                row=raw,
                fit=fit,
                logical_elements=logical,
                elapsed_s=elapsed,
                result_rate_per_s=logical / elapsed,
            )
            evidences.append(evidence)
            role_diagnostics.append(
                {
                    "session_id": raw["session_id"],
                    "session_index": raw["session_index"],
                    "session_order": raw["session_order"],
                    "stage": raw["stage"],
                    "policy": raw["policy"],
                    "policy_position": raw["policy_position"],
                    "cell_id": cell_id,
                    "bracket_index": bracket_index,
                    "orientation": orientation,
                    "bracket_schedule": bracket_schedule,
                    "role_index": raw["role_index"],
                    "role_id": raw["role_id"],
                    "role_position": raw["role_position"],
                    "role": raw["role"],
                    "variant": raw["variant"],
                    "trace_power_W": fit.power_w,
                    "trace_r2": fit.r2,
                    "trace_fit_points": fit.fit_points,
                    "trace_fit_updates": fit.fit_updates,
                    "trace_fit_span_s": fit.fit_span_s,
                    "trace_guard_s": fit.guard_s,
                    "trace_independent_window_difference_count": (
                        fit.independently_reconstructed_window_difference_count
                    ),
                    "kernel_midpoint_s": fit.kernel_midpoint_s,
                    "result_rate_Gelement_per_s": evidence.result_rate_per_s / 1.0e9,
                    "logical_output_elements": logical,
                    "elapsed_s": elapsed,
                    "idle_power_W_diagnostic": row_number(raw, "idle_power_W", label, 0.0),
                    "primary_uses_idle": "false",
                }
            )

        before, middle, after = evidences
        weight = interpolation_weight(
            before.fit.kernel_midpoint_s,
            middle.fit.kernel_midpoint_s,
            after.fit.kernel_midpoint_s,
            f"{label}/{orientation}",
        )
        if bracket_schedule == "C-T-C":
            interpolated_control_power = lerp(
                before.fit.power_w, after.fit.power_w, weight
            )
            delta_power = middle.fit.power_w - interpolated_control_power
            treatment_rate = middle.result_rate_per_s
            interpolated_treatment_power = middle.fit.power_w
            control_power = interpolated_control_power
            treatment_elapsed = middle.elapsed_s
            control_elapsed = lerp(
                before.elapsed_s, after.elapsed_s, weight
            )
            treatment_energy = middle.fit.power_w * middle.elapsed_s
            control_energy = lerp(
                before.fit.power_w * before.elapsed_s,
                after.fit.power_w * after.elapsed_s,
                weight,
            )
            normalization_source = "middle_treatment_result_rate"
        else:
            interpolated_treatment_power = lerp(
                before.fit.power_w, after.fit.power_w, weight
            )
            treatment_rate = lerp(
                before.result_rate_per_s, after.result_rate_per_s, weight
            )
            require(
                math.isfinite(treatment_rate) and treatment_rate > 0.0,
                f"{label}/{orientation}: interpolated treatment result rate invalid",
            )
            control_power = middle.fit.power_w
            delta_power = interpolated_treatment_power - control_power
            treatment_elapsed = lerp(
                before.elapsed_s, after.elapsed_s, weight
            )
            control_elapsed = middle.elapsed_s
            treatment_energy = lerp(
                before.fit.power_w * before.elapsed_s,
                after.fit.power_w * after.elapsed_s,
                weight,
            )
            control_energy = middle.fit.power_w * middle.elapsed_s
            normalization_source = "interpolated_outer_treatment_result_rate"
        effect_pj = delta_power / treatment_rate * 1.0e12
        same_iter_energy_pj = (
            (treatment_energy - control_energy) / denominator * 1.0e12
        )
        require(math.isfinite(effect_pj), f"{label}/{orientation}: effect is non-finite")
        require(
            math.isfinite(same_iter_energy_pj),
            f"{label}/{orientation}: same-ITER energy diagnostic is non-finite",
        )
        require(
            treatment_elapsed > 0.0 and control_elapsed > 0.0,
            f"{label}/{orientation}: elapsed-time diagnostic is invalid",
        )
        bracket_temperatures = [
            row_number(row, field, f"{label}/{orientation}")
            for row in bracket_rows
            for field in ("temp_before_C", "temp_after_C")
            if field in row
        ]
        bracket_clocks = [
            row_number(row, field, f"{label}/{orientation}")
            for row in bracket_rows
            for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
            if field in row
        ]
        effects.append(
            {
                "session_id": rows[0]["session_id"],
                "session_index": row_int(rows[0], "session_index", label, 1),
                "session_order": rows[0]["session_order"],
                "stage": rows[0]["stage"],
                "policy": rows[0]["policy"],
                "policy_position": row_int(rows[0], "policy_position", label, 0),
                "cell_id": cell_id,
                "bracket_index": bracket_index,
                "orientation": orientation,
                "bracket_schedule": bracket_schedule,
                "interpolation_weight": weight,
                "treatment_power_at_contrast_W": interpolated_treatment_power,
                "control_power_at_contrast_W": control_power,
                "delta_power_W": delta_power,
                "bracket_delta_power_W": delta_power,
                "treatment_result_rate_Gelement_per_s": treatment_rate / 1.0e9,
                "normalization_source": normalization_source,
                "atc_delta_pJ_per_logical_output_element": effect_pj,
                "effect_pJ_per_logical_output": effect_pj,
                "same_iter_gross_board_energy_contrast_pJ_per_logical_output": same_iter_energy_pj,
                "treatment_elapsed_at_contrast_s": treatment_elapsed,
                "control_elapsed_at_contrast_s": control_elapsed,
                "treatment_over_control_elapsed_ratio": (
                    treatment_elapsed / control_elapsed
                ),
                "treatment_energy_at_contrast_J": treatment_energy,
                "control_energy_at_contrast_J": control_energy,
                "diagnostic_uses_idle": "false",
                "logical_output_elements_per_role": denominator,
                "minimum_trace_fit_points": min(
                    evidence.fit.fit_points for evidence in evidences
                ),
                "minimum_trace_r2": min(evidence.fit.r2 for evidence in evidences),
                "max_query_latency_s": max(
                    evidence.fit.max_query_latency_s for evidence in evidences
                ),
                "idle_power_W_diagnostic_mean": statistics.fmean(
                    row_number(evidence.row, "idle_power_W", label, 0.0)
                    for evidence in evidences
                ),
                "temperature_min_C": (
                    min(bracket_temperatures)
                    if bracket_temperatures
                    else "not_recorded"
                ),
                "temperature_max_C": (
                    max(bracket_temperatures)
                    if bracket_temperatures
                    else "not_recorded"
                ),
                "temperature_span_C": (
                    max(bracket_temperatures) - min(bracket_temperatures)
                    if bracket_temperatures
                    else "not_recorded"
                ),
                "sm_clock_min_mhz": (
                    min(bracket_clocks) if bracket_clocks else "not_recorded"
                ),
                "sm_clock_max_mhz": (
                    max(bracket_clocks) if bracket_clocks else "not_recorded"
                ),
                "sm_clock_span_fraction": (
                    (max(bracket_clocks) - min(bracket_clocks))
                    / statistics.median(bracket_clocks)
                    if bracket_clocks and statistics.median(bracket_clocks) > 0.0
                    else "not_recorded"
                ),
                "primary_uses_idle": "false",
                "quality_status": "pass",
            }
        )

    ctc = effects[0]["atc_delta_pJ_per_logical_output_element"]
    tct = effects[1]["atc_delta_pJ_per_logical_output_element"]
    session_effect = (ctc + tct) / 2.0
    ctc_same_iter = effects[0][
        "same_iter_gross_board_energy_contrast_pJ_per_logical_output"
    ]
    tct_same_iter = effects[1][
        "same_iter_gross_board_energy_contrast_pJ_per_logical_output"
    ]
    session_same_iter = (ctc_same_iter + tct_same_iter) / 2.0
    for effect in effects:
        effect["session_effect_pJ_per_logical_output"] = session_effect
        effect[
            "session_same_iter_gross_board_energy_contrast_pJ_per_logical_output"
        ] = session_same_iter
    all_temperatures = [
        row_number(row, field, label)
        for row in rows
        for field in ("temp_before_C", "temp_after_C")
        if field in row
    ]
    all_clocks = [
        row_number(row, field, label)
        for row in rows
        for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
        if field in row
    ]
    session_row: dict[str, Any] = {
        "session_id": rows[0]["session_id"],
        "session_index": row_int(rows[0], "session_index", label, 1),
        "session_order": rows[0]["session_order"],
        "stage": rows[0]["stage"],
        "policy": rows[0]["policy"],
        "policy_position": row_int(rows[0], "policy_position", label, 0),
        "cell_id": cell_id,
        "ctc_atc_delta_pJ_per_logical_output_element": ctc,
        "tct_atc_delta_pJ_per_logical_output_element": tct,
        "session_effect_pJ_per_logical_output": session_effect,
        "order_balanced_atc_delta_pJ_per_logical_output_element": session_effect,
        "ctc_same_iter_gross_board_energy_contrast_pJ_per_logical_output": ctc_same_iter,
        "tct_same_iter_gross_board_energy_contrast_pJ_per_logical_output": tct_same_iter,
        "order_balanced_same_iter_gross_board_energy_contrast_pJ_per_logical_output": session_same_iter,
        "mean_treatment_over_control_elapsed_ratio": statistics.fmean(
            float(effect["treatment_over_control_elapsed_ratio"])
            for effect in effects
        ),
        "mean_delta_power_W": statistics.fmean(
            float(effect["delta_power_W"]) for effect in effects
        ),
        "middle_position_bias_pJ_per_logical_output_element": (ctc - tct) / 2.0,
        "orientation_disagreement_abs_pJ_per_logical_output_element": abs(ctc - tct),
        "logical_output_elements_per_role": denominator,
        "mean_idle_power_W_diagnostic": mean_idle_power,
        "primary_uses_idle": "false",
        "min_trace_fit_points": min(
            int(effect["minimum_trace_fit_points"]) for effect in effects
        ),
        "min_trace_r2": min(float(effect["minimum_trace_r2"]) for effect in effects),
        "max_query_latency_s": max(
            float(effect["max_query_latency_s"]) for effect in effects
        ),
        "temperature_min_C": min(all_temperatures) if all_temperatures else "not_recorded",
        "temperature_max_C": max(all_temperatures) if all_temperatures else "not_recorded",
        "temperature_span_C": (
            max(all_temperatures) - min(all_temperatures)
            if all_temperatures
            else "not_recorded"
        ),
        "sm_clock_min_mhz": min(all_clocks) if all_clocks else "not_recorded",
        "sm_clock_max_mhz": max(all_clocks) if all_clocks else "not_recorded",
        "sm_clock_span_fraction": (
            (max(all_clocks) - min(all_clocks)) / statistics.median(all_clocks)
            if all_clocks and statistics.median(all_clocks) > 0.0
            else "not_recorded"
        ),
        "output_equivalence_status": "pass",
        "quality_status": "pass",
    }
    return effects, session_row, role_diagnostics


def summary_stats(values: list[float]) -> dict[str, float | int]:
    require(len(values) == 3, "implementation/stage summary requires three fresh sessions")
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half_width = T95_DF2 * sd / math.sqrt(3)
    return {
        "fresh_session_count": 3,
        "mean_pJ_per_logical_output": mean,
        "sd_pJ_per_logical_output": sd,
        "min_pJ_per_logical_output": min(values),
        "max_pJ_per_logical_output": max(values),
        "t95_low_pJ_per_logical_output": mean - half_width,
        "t95_high_pJ_per_logical_output": mean + half_width,
        "positive_count": sum(value > 0.0 for value in values),
        "mean_atc_delta_pJ_per_logical_output_element": mean,
        "median_atc_delta_pJ_per_logical_output_element": statistics.median(values),
        "sample_sd_atc_delta_pJ_per_logical_output_element": sd,
        "min_atc_delta_pJ_per_logical_output_element": min(values),
        "max_atc_delta_pJ_per_logical_output_element": max(values),
        "descriptive_t95_low_pJ_per_logical_output_element": mean - half_width,
        "descriptive_t95_high_pJ_per_logical_output_element": mean + half_width,
        "positive_session_count": sum(value > 0.0 for value in values),
    }


def same_iter_diagnostic_stats(values: list[float]) -> dict[str, float | int]:
    require(
        len(values) == 3,
        "same-ITER diagnostic summary requires three fresh sessions",
    )
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half_width = T95_DF2 * sd / math.sqrt(3)
    return {
        "mean_same_iter_gross_board_energy_contrast_pJ_per_logical_output": mean,
        "sample_sd_same_iter_gross_board_energy_contrast_pJ_per_logical_output": sd,
        "min_same_iter_gross_board_energy_contrast_pJ_per_logical_output": min(
            values
        ),
        "max_same_iter_gross_board_energy_contrast_pJ_per_logical_output": max(
            values
        ),
        "descriptive_t95_low_same_iter_gross_board_energy_contrast_pJ_per_logical_output": (
            mean - half_width
        ),
        "descriptive_t95_high_same_iter_gross_board_energy_contrast_pJ_per_logical_output": (
            mean + half_width
        ),
        "positive_same_iter_session_count": sum(value > 0.0 for value in values),
    }


def analyze_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    require(manifest_path.is_file(), f"run manifest missing: {manifest_path}")
    manifest = read_json(manifest_path)
    (
        sessions,
        minimum_fit_points,
        manifest_raw_fields,
        manifest_trace_fields,
    ) = validate_manifest(manifest, run_dir)
    binary_hash = str(manifest["binary"]["sha256"])

    all_raw: list[dict[str, str]] = []
    trace_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    seen_trace_keys: set[tuple[str, str, str, int]] = set()
    for session in sessions:
        session_id = str(session["session_id"])
        raw_path = resolve_artifact_path(str(session.get("raw_csv", "")), run_dir)
        trace_path = resolve_artifact_path(str(session.get("energy_trace_csv", "")), run_dir)
        require(raw_path.is_file(), f"{session_id}: raw CSV missing")
        require(trace_path.is_file(), f"{session_id}: trace CSV missing")
        raw_hash = manifest_hash(
            session, ("raw_sha256", "raw_csv_sha256"), f"{session_id}: raw"
        )
        trace_hash = manifest_hash(
            session,
            ("energy_trace_sha256", "energy_trace_csv_sha256"),
            f"{session_id}: trace",
        )
        require(sha256_file(raw_path) == raw_hash, f"{session_id}: raw SHA-256 mismatch")
        require(
            sha256_file(trace_path) == trace_hash,
            f"{session_id}: trace SHA-256 mismatch",
        )
        raw_rows, _ = read_csv_strict(
            raw_path, manifest_raw_fields, f"{session_id}: raw"
        )
        trace_rows, _ = read_csv_strict(
            trace_path, manifest_trace_fields, f"{session_id}: trace"
        )
        require(len(raw_rows) == 18, f"{session_id}: raw role count must be 18")
        require(
            all(row.get("session_id") == session_id for row in raw_rows),
            f"{session_id}: raw session identity mismatch",
        )
        require(
            all(row.get("binary_sha256") == binary_hash for row in raw_rows),
            f"{session_id}: raw binary hash mismatch",
        )
        expected_execution = session["execution_schedule"]
        require(
            [row.get("role_id", "") for row in raw_rows]
            == [str(item["role_id"]) for item in expected_execution],
            f"{session_id}: raw execution order differs from manifest",
        )
        for raw_row, expected_role in zip(raw_rows, expected_execution):
            for field in (
                "stage",
                "policy",
                "cell_id",
                "orientation",
                "role_position",
                "role",
                "variant",
            ):
                require(
                    raw_row.get(field) == str(expected_role[field]),
                    f"{session_id}: raw/manifest {field} mismatch",
                )
            for field in (
                "session_role_index",
                "policy_position",
                "bracket_index",
                "role_index",
            ):
                require(
                    row_int(raw_row, field, session_id, 0)
                    == int(expected_role[field]),
                    f"{session_id}: raw/manifest {field} mismatch",
                )
        raw_by_role_id = {row["role_id"]: row for row in raw_rows}
        require(
            len(raw_by_role_id) == 18,
            f"{session_id}: raw role_id is empty or duplicated",
        )
        for trace_row in trace_rows:
            require(
                trace_row.get("schema_version") == TRACE_SCHEMA,
                f"{session_id}: trace schema mismatch",
            )
            require(
                trace_row.get("experiment_kind") == EXPERIMENT_KIND
                and trace_row.get("protocol_revision") == PROTOCOL_REVISION,
                f"{session_id}: trace experiment/protocol mismatch",
            )
            require(
                trace_row.get("session_id") == session_id,
                f"{session_id}: trace session identity mismatch",
            )
            require(
                trace_row.get("binary_sha256") == binary_hash,
                f"{session_id}: trace binary hash mismatch",
            )
            raw_role = raw_by_role_id.get(trace_row.get("role_id", ""))
            require(raw_role is not None, f"{session_id}: trace role not in raw")
            assert raw_role is not None
            for field in (
                "session_id",
                "stage",
                "policy",
                "cell_id",
                "role",
                "variant",
                "run_id",
            ):
                require(
                    trace_row.get(field) == raw_role.get(field),
                    f"{session_id}: trace/raw {field} mismatch",
                )
            for field in ("bracket_index", "role_index"):
                require(
                    row_int(trace_row, field, session_id, 0)
                    == row_int(raw_role, field, session_id, 0),
                    f"{session_id}: trace/raw {field} mismatch",
                )
            key = (
                trace_row.get("session_id", ""),
                trace_row.get("cell_id", ""),
                trace_row.get("role_id", ""),
            )
            sample = row_int(trace_row, "sample_index", f"{session_id}: trace", 0)
            sample_key = (*key, sample)
            require(sample_key not in seen_trace_keys, f"{session_id}: duplicate trace sample")
            seen_trace_keys.add(sample_key)
            trace_by_key[key].append(trace_row)
        all_raw.extend(raw_rows)

    require(len(all_raw) == 162, f"run requires 162 raw roles; got {len(all_raw)}")
    raw_role_keys = {
        (row["session_id"], row["cell_id"], row["role_id"]) for row in all_raw
    }
    require(
        set(trace_by_key) == raw_role_keys,
        "trace/raw role-key set mismatch",
    )

    by_cell: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in all_raw:
        by_cell[(row["session_id"], row["cell_id"])].append(row)
    require(len(by_cell) == 27, f"run requires 27 cells; got {len(by_cell)}")

    orientation_effects: list[dict[str, Any]] = []
    session_effects: list[dict[str, Any]] = []
    role_diagnostics: list[dict[str, Any]] = []
    for key in sorted(by_cell):
        effects, session_row, roles = analyze_cell(
            by_cell[key], trace_by_key, minimum_fit_points
        )
        orientation_effects.extend(effects)
        session_effects.append(session_row)
        role_diagnostics.extend(roles)

    observed_matrix = {
        (row["stage"], row["policy"], int(row["session_index"]))
        for row in session_effects
    }
    expected_matrix = {
        (stage, policy, session)
        for stage in STAGES
        for policy in POLICIES
        for session in range(1, 4)
    }
    require(observed_matrix == expected_matrix, "3×3×3 result matrix mismatch")

    summary_rows: list[dict[str, Any]] = []
    for stage in STAGES:
        for policy in POLICIES:
            selected = sorted(
                (
                    row
                    for row in session_effects
                    if row["stage"] == stage and row["policy"] == policy
                ),
                key=lambda row: int(row["session_index"]),
            )
            require(
                [int(row["session_index"]) for row in selected] == [1, 2, 3],
                f"{stage}/{policy}: fresh-session set mismatch",
            )
            values = [
                float(
                    row[
                        "order_balanced_atc_delta_pJ_per_logical_output_element"
                    ]
                )
                for row in selected
            ]
            same_iter_values = [
                float(
                    row[
                        "order_balanced_same_iter_gross_board_energy_contrast_pJ_per_logical_output"
                    ]
                )
                for row in selected
            ]
            summary_rows.append(
                {
                    "stage": stage,
                    "policy": policy,
                    "primary_estimand": (
                        "active-control Operand-rate ATC delta pJ per logical "
                        f"Softmax output element for one added {stage} pass"
                    ),
                    **summary_stats(values),
                    **same_iter_diagnostic_stats(same_iter_values),
                    "mean_treatment_over_control_elapsed_ratio": statistics.fmean(
                        float(
                            row[
                                "mean_treatment_over_control_elapsed_ratio"
                            ]
                        )
                        for row in selected
                    ),
                    "mean_delta_power_W": statistics.fmean(
                        float(row["mean_delta_power_W"]) for row in selected
                    ),
                    "mean_middle_position_bias_pJ_per_logical_output_element": statistics.fmean(
                        float(row["middle_position_bias_pJ_per_logical_output_element"])
                        for row in selected
                    ),
                    "mean_orientation_disagreement_abs_pJ_per_logical_output_element": statistics.fmean(
                        float(
                            row[
                                "orientation_disagreement_abs_pJ_per_logical_output_element"
                            ]
                        )
                        for row in selected
                    ),
                    "quality_status": "pass",
                    "verdict": (
                        "positive_in_all_fresh_sessions"
                        if all(value > 0.0 for value in values)
                        else "signed_result_reported_not_hard_rejected"
                    ),
                }
            )

    return {
        "schema_version": "softmax_whole_stage_atc_analysis_v1",
        "status": "pass",
        "run_dir": str(run_dir),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "binary_sha256": binary_hash,
        "primary_metric": (
            "active_control_atc_delta_pJ_per_logical_softmax_output_element"
        ),
        "primary_uses_idle": False,
        "non_primary_diagnostic": {
            "name": (
                "same_iter_gross_board_energy_contrast_pJ_per_logical_output"
            ),
            "formula": (
                "(interpolated treatment role energy - interpolated "
                "active-control role energy) * 1e12 / same-ITER logical "
                "output count, where each role energy is qualified trace "
                "power * role elapsed"
            ),
            "uses_idle": False,
            "replaces_primary": False,
            "interpretation": (
                "runtime-sensitive gross board-energy contrast from the same "
                "qualified trace; reported separately from Operand-rate ATC"
            ),
        },
        "denominator_formula": "grid_blocks * 2 * iters * softmax_cols",
        "role_count": len(all_raw),
        "cell_count": len(session_effects),
        "orientation_effect_count": len(orientation_effects),
        "summary_count": len(summary_rows),
        "quality_gates": {
            "exact_3x3x3_schedule": "pass",
            "six_roles_per_cell": "pass",
            "same_symbol_geometry_iters": "pass",
            "per_cell_treatment_calibration": "pass",
            "treatment_calibration_duration": "pass",
            "resource_and_smid_placement": "pass",
            "raw_trace_manifest_hashes": "pass",
            "static_audit_binding": (
                "test_fixture_bypass"
                if manifest.get("analysis_test_fixture") is True
                else "pass"
            ),
            **(
                {}
                if manifest.get("analysis_test_fixture") is True
                else {"ncu_dynamic_instruction_audit_binding": "pass"}
            ),
            "guarded_trace_slopes": "pass",
            "independent_trace_fit_window_reconstruction": "pass",
            "logical_output_denominator": "pass",
            "output_equivalence": "pass",
            "treatment_invariant_live_sink_dataflow": "pass",
            "idle_primary_exclusion": "pass",
            "same_iter_diagnostic_separate_from_primary": "pass",
        },
        "orientation_effects": orientation_effects,
        "session_effects": sorted(
            session_effects,
            key=lambda row: (
                STAGES.index(str(row["stage"])),
                POLICIES.index(str(row["policy"])),
                int(row["session_index"]),
            ),
        ),
        "implementation_stage_summary": summary_rows,
        "role_diagnostics": role_diagnostics,
    }


def atomic_write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    require(bool(rows), f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                require(
                    set(row) == set(fields),
                    f"{path}: output row schema drifted",
                )
                writer.writerow(row)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def quality_gate_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": "run",
            "stage": "",
            "policy": "",
            "session_id": "",
            "gate": gate,
            "status": status,
            "detail": "",
        }
        for gate, status in analysis["quality_gates"].items()
    ]
    rows.extend(
        {
            "scope": "fresh_session_cell",
            "stage": row["stage"],
            "policy": row["policy"],
            "session_id": row["session_id"],
            "gate": "cell_all_fail_closed_gates",
            "status": row["quality_status"],
            "detail": (
                f"min_trace_r2={row['min_trace_r2']};"
                f"min_fit_points={row['min_trace_fit_points']}"
            ),
        }
        for row in analysis["session_effects"]
    )
    return rows


def summary_markdown(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# Whole-Softmax stage Operand-rate ATC analysis",
        "",
        f"- status: `{analysis['status']}`",
        f"- measured roles / cells / bracket effects: "
        f"{analysis['role_count']} / {analysis['cell_count']} / "
        f"{analysis['orientation_effect_count']}",
        "- primary: active-control ATC ΔpJ/logical Softmax output element "
        "for one added stage pass",
        "- idle power: diagnostic only; excluded from every primary numerator",
        "- non-primary diagnostic: same-ITER gross board-energy contrast "
        "(idle excluded; never substituted for primary ATC)",
        "",
        "| stage | policy | mean ATC ΔpJ/output | SD | descriptive t95 | "
        "same-ITER gross ΔE/N | T/C elapsed |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["implementation_stage_summary"]:
        lines.append(
            f"| {row['stage']} | {row['policy']} | "
            f"{float(row['mean_pJ_per_logical_output']):.6f} | "
            f"{float(row['sd_pJ_per_logical_output']):.6f} | "
            f"[{float(row['t95_low_pJ_per_logical_output']):.6f}, "
            f"{float(row['t95_high_pJ_per_logical_output']):.6f}] | "
            f"{float(row['mean_same_iter_gross_board_energy_contrast_pJ_per_logical_output']):.6f} | "
            f"{float(row['mean_treatment_over_control_elapsed_ratio']):.6f} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(analysis: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(out_dir / "matched_effects.csv", analysis["orientation_effects"])
    atomic_write_csv(out_dir / "session_summary.csv", analysis["session_effects"])
    atomic_write_csv(
        out_dir / "cell_summary.csv",
        analysis["implementation_stage_summary"],
    )
    atomic_write_csv(out_dir / "quality_gates.csv", quality_gate_rows(analysis))
    atomic_write_json(out_dir / "analysis.json", analysis)
    atomic_write_text(out_dir / "summary.md", summary_markdown(analysis))


def write_fixture_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_synthetic_fixture(
    root: Path,
    *,
    denominator_fault: bool = False,
    digest_fault: bool = False,
    sink_fault: bool = False,
) -> tuple[Path, dict[tuple[str, str], float]]:
    run_dir = root / "synthetic_stage_atc"
    run_dir.mkdir(parents=True)
    binary_path = run_dir / "frozen_binary"
    runner_path = run_dir / "frozen_runner.py"
    binary_path.write_bytes(b"synthetic-stage-atc-binary")
    runner_path.write_text("# synthetic stage ATC runner\n", encoding="utf-8")
    expected: dict[tuple[str, str], float] = {}
    sessions: list[dict[str, Any]] = []
    raw_fields = list(RAW_REQUIRED) + [
        "sink_digest",
        "temp_before_C",
        "temp_after_C",
        "clock_sm_before_mhz",
        "clock_sm_after_mhz",
        "clock_mem_before_mhz",
        "clock_mem_after_mhz",
        "preheat_actual_s",
        "idle_delta_E_J",
        "measurement_start_epoch_ms",
        "measurement_end_epoch_ms",
        "E_before_mJ",
        "E_after_mJ",
        "compute_capability",
        "runtime_sm_count",
        "occupancy_max_blocks_per_sm",
        "static_single_wave_capacity_blocks",
        "smid_total_blocks",
        "smid_unique",
        "smid_max_blocks_on_sm",
        "validation_pass",
        "static_single_wave_capacity_gate_pass",
        "occupancy_gate_pass",
        "smid_histogram_ok",
        "smid_all_blocks_observed",
    ]
    # frozenset order is arbitrary but stable for each fixture invocation.
    raw_fields = list(dict.fromkeys(raw_fields))
    trace_fields = list(TRACE_REQUIRED)
    for stage_index, stage in enumerate(STAGES):
        for session_index in range(1, 4):
            session_order, schedule = SESSION_ORDERS[session_index]
            session_id = f"synthetic_{stage}_session{session_index:02d}_{session_order}"
            raw_path = run_dir / f"{stage}_session{session_index:02d}_raw.csv"
            trace_path = run_dir / f"{stage}_session{session_index:02d}_trace.csv"
            raw_rows: list[dict[str, Any]] = []
            trace_rows: list[dict[str, Any]] = []
            absolute_start = 1000.0 + stage_index * 100.0 + session_index * 20.0
            execution_schedule: list[dict[str, Any]] = []
            cells: list[dict[str, Any]] = []
            for policy_position, policy in enumerate(schedule):
                policy_index = POLICIES.index(policy)
                effect_pj = 20.0 + stage_index * 7.0 + policy_index * 3.0 + session_index
                expected.setdefault((stage, policy), 0.0)
                expected[(stage, policy)] += effect_pj / 3.0
                cell_id = f"{session_id}_{policy}"
                cells.append(
                    {
                        "cell_id": cell_id,
                        "stage": stage,
                        "policy_position": policy_position,
                        "policy": policy,
                        "bracket_schedule": ["C-T-C", "T-C-T"],
                        "expected_roles": 6,
                    }
                )
                digest = hashlib.sha256(cell_id.encode()).hexdigest()
                iters = 10_000_000 + stage_index * 1000 + policy_index * 100
                logical = GRID_BLOCKS * ROWS_PER_BLOCK * iters * SOFTMAX_COLS
                elapsed = 1.0
                treatment_rate = logical / elapsed
                delta_power = effect_pj * 1.0e-12 * treatment_rate
                role_number = 0
                for bracket_index, (
                    orientation,
                    _bracket_schedule,
                    role_contract,
                ) in BRACKETS.items():
                    for role_index, (role_position, variant) in enumerate(role_contract):
                        role_id = (
                            f"{cell_id}_b{bracket_index}_r{role_index}_{variant}"
                        )
                        run_id = f"{cell_id}_{role_id}"
                        power = 120.0 + 0.1 * role_number
                        if variant == "treatment":
                            power += delta_power
                        role_start = absolute_start + policy_position * 8.0 + role_number * 1.3
                        output_digest = (
                            hashlib.sha256((digest + "fault").encode()).hexdigest()
                            if digest_fault
                            and stage_index == 0
                            and session_index == 1
                            and policy_position == 0
                            and role_number == 1
                            else digest
                        )
                        schedule_role = {
                            "session_role_index": len(execution_schedule),
                            "stage": stage,
                            "policy_position": policy_position,
                            "policy": policy,
                            "cell_id": cell_id,
                            "bracket_index": bracket_index,
                            "orientation": orientation,
                            "role_index": role_index,
                            "role_id": role_id,
                            "role_position": role_position,
                            "role": variant,
                            "variant": variant,
                        }
                        execution_schedule.append(schedule_role)
                        raw_rows.append(
                            {
                                "schema_version": RAW_SCHEMA,
                                "experiment_kind": EXPERIMENT_KIND,
                                "protocol_revision": PROTOCOL_REVISION,
                                "run_id": run_id,
                                "session_id": session_id,
                                "session_index": session_index,
                                "session_order": session_order,
                                "session_role_index": schedule_role[
                                    "session_role_index"
                                ],
                                "stage": stage,
                                "policy_position": policy_position,
                                "policy": policy,
                                "cell_id": cell_id,
                                "bracket_index": bracket_index,
                                "orientation": orientation,
                                "role_index": role_index,
                                "role_id": role_id,
                                "role_position": role_position,
                                "role": variant,
                                "variant": variant,
                                "kernel_symbol": f"whole_stage_atc_{stage}_{policy}",
                                "same_kernel_symbol_status": "pass",
                                "input_dtype": (
                                    "fp32" if policy == "fp32" else "fp16"
                                ),
                                "output_dtype": (
                                    "fp32" if policy == "fp32" else "fp16"
                                ),
                                "block_shared_bytes": 2048,
                                "registers_per_thread": 32,
                                "softmax_cols": SOFTMAX_COLS,
                                "grid_blocks": GRID_BLOCKS,
                                "rows_per_block": ROWS_PER_BLOCK,
                                "threads_per_block": THREADS_PER_BLOCK,
                                "iters": iters,
                                "logical_output_elements": (
                                    logical + 1
                                    if denominator_fault
                                    and stage_index == 0
                                    and session_index == 1
                                    and policy_position == 0
                                    and role_number == 0
                                    else logical
                                ),
                                "elapsed_s": elapsed,
                                "calibration_mode": (
                                    "per_stage_policy_treatment_before_common_preheat"
                                ),
                                "calibration_reference_variant": "treatment",
                                "calibration_elapsed_s": ROLE_TARGET_SECONDS,
                                "calibration_iters": iters,
                                "calibration_before_preheat": "true",
                                "role_target_seconds": ROLE_TARGET_SECONDS,
                                "energy_trace_power_W": power,
                                "energy_trace_status": "pass",
                                "energy_trace_sample_count": 20,
                                "energy_trace_update_count": 19,
                                "energy_trace_fit_point_count": 16,
                                "energy_trace_r2": 1.0,
                                "endpoint_delta_E_J": power * elapsed,
                                "delta_E_J": power * elapsed,
                                "idle_power_W": 35.0,
                                "idle_elapsed_s": 1.0,
                                "idle_delta_E_J": 35.0,
                                "measurement_start_epoch_ms": 1_000_000,
                                "measurement_end_epoch_ms": 1_001_000,
                                "E_before_mJ": 1_000_000,
                                "E_after_mJ": 1_000_000 + power * 1000.0,
                                "gpu_name": "Synthetic RTX 3090",
                                "gpu_id": 0,
                                "target_profile": "rtx3090",
                                "compute_capability": "8.6",
                                "cuda_binary_arch": 86,
                                "cuda_pci_bus_id": "0000:01:00.0",
                                "binary_sha256": sha256_file(binary_path),
                                "numerical_check_id": "whole_stage_atc_synthetic_v1_pass",
                                "control_treatment_output_bit_identical": "true",
                                "output_digest": output_digest,
                                "output_equivalence_status": "pass",
                                "sink_digest": hashlib.sha256(
                                    (
                                        f"{cell_id}:tag-contaminated-treatment"
                                        if sink_fault
                                        and stage_index == 0
                                        and session_index == 1
                                        and policy_position == 0
                                        and variant == "treatment"
                                        else f"{cell_id}:invariant-sink"
                                    ).encode()
                                ).hexdigest(),
                                "temp_before_C": 50 + role_number,
                                "temp_after_C": 51 + role_number,
                                "clock_sm_before_mhz": 1695,
                                "clock_sm_after_mhz": 1695,
                                "clock_mem_before_mhz": 9751,
                                "clock_mem_after_mhz": 9751,
                                "preheat_requested_s": PREHEAT_REQUESTED_S,
                                "preheat_actual_s": 5.0,
                                "energy_source": "nvml_total_energy",
                                "energy_integration_method": (
                                    "guarded_interior_theil_sen"
                                ),
                                "runtime_sm_count": 82,
                                "occupancy_max_blocks_per_sm": 6,
                                "static_single_wave_capacity_blocks": 492,
                                "smid_total_blocks": 41,
                                "smid_unique": 41,
                                "smid_max_blocks_on_sm": 1,
                                "validation_pass": "true",
                                "static_single_wave_capacity_gate_pass": "true",
                                "occupancy_gate_pass": "true",
                                "smid_histogram_ok": "true",
                                "smid_all_blocks_observed": "true",
                            }
                        )
                        for sample_index in range(20):
                            relative = 0.02 + sample_index * (0.96 / 19.0)
                            midpoint = role_start + relative
                            query_latency = 0.0002
                            trace_rows.append(
                                {
                                    "schema_version": TRACE_SCHEMA,
                                    "experiment_kind": EXPERIMENT_KIND,
                                    "protocol_revision": PROTOCOL_REVISION,
                                    "session_id": session_id,
                                    "stage": stage,
                                    "policy": policy,
                                    "cell_id": cell_id,
                                    "bracket_index": bracket_index,
                                    "role_index": role_index,
                                    "role_id": role_id,
                                    "role": variant,
                                    "variant": variant,
                                    "run_id": run_id,
                                    "sample_index": sample_index,
                                    "query_start_s": midpoint - query_latency / 2.0,
                                    "query_end_s": midpoint + query_latency / 2.0,
                                    "query_midpoint_s": midpoint,
                                    "query_latency_s": query_latency,
                                    "relative_to_kernel_start_s": relative,
                                    "energy_mJ": (
                                        1_000_000.0 + power * 1000.0 * relative
                                    ),
                                    "changed_from_previous": (
                                        "false" if sample_index == 0 else "true"
                                    ),
                                    "in_fit_window": (
                                        "true"
                                        if 2 <= sample_index <= 17
                                        else "false"
                                    ),
                                    "binary_sha256": sha256_file(binary_path),
                                }
                            )
                        role_number += 1
            write_fixture_csv(raw_path, raw_fields, raw_rows)
            write_fixture_csv(trace_path, trace_fields, trace_rows)
            sessions.append(
                {
                    "stage": stage,
                    "session_index": session_index,
                    "session_id": session_id,
                    "session_order": session_order,
                    "policy_schedule": list(schedule),
                    "expected_cells": 3,
                    "expected_roles": 18,
                    "cells": cells,
                    "execution_schedule": execution_schedule,
                    "raw_csv": raw_path.name,
                    "raw_sha256": sha256_file(raw_path),
                    "energy_trace_csv": trace_path.name,
                    "energy_trace_sha256": sha256_file(trace_path),
                    "status": "complete",
                    "returncode": 0,
                    "global_session_index": GLOBAL_SESSION_INDEX[
                        (stage, session_index)
                    ],
                    "fresh_cuda_process": True,
                    "persistent_cuda_context": True,
                    "validation": {
                        "raw_rows": 18,
                        "trace_rows": len(trace_rows),
                        "trace_roles": 18,
                        "preheat_actual_s": PREHEAT_REQUESTED_S,
                        "logical_output_elements_per_role": "per_cell",
                        "same_kernel_symbol_cells": 3,
                        "output_equivalent_cells": 3,
                    },
                }
            )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "experiment_kind": EXPERIMENT_KIND,
        "protocol_revision": PROTOCOL_REVISION,
        "design_id": "rtx3090_s1024_q50_stage_atc_3x3x3_v2",
        "status": "complete",
        "analysis_test_fixture": True,
        "binary": {"path": binary_path.name, "sha256": sha256_file(binary_path)},
        "runner": {"path": runner_path.name, "sha256": sha256_file(runner_path)},
        "profile": {
            "name": "rtx3090",
            "gpu_id": 0,
            "runtime_sm_count": 82,
            "compute_capability": "8.6",
            "cuda_arch": "sm_86",
        },
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "requested_sm_coverage": 0.5,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
            "role_target_seconds": ROLE_TARGET_SECONDS,
            "iters": "calibrated_per_stage_policy_and_observed_in_raw",
            "logical_output_elements_per_role": (
                "grid_blocks*observed_iters*rows_per_block*softmax_cols"
            ),
        },
        "design": {
            "stages": list(STAGES),
            "policies": list(POLICIES),
            "session_orders": ["ABC", "BCA", "CAB"],
            "global_stage_orders": {
                "ABC": ["exp", "reduction", "normalization"],
                "BCA": ["reduction", "normalization", "exp"],
                "CAB": ["normalization", "exp", "reduction"],
            },
            "bracket_schedule": ["C-T-C", "T-C-T"],
            "fresh_sessions_per_stage": 3,
            "total_cells": 27,
            "total_process_sessions": 9,
            "measured_roles_per_cell": 6,
            "total_measured_roles": 162,
            "calibration": {
                "mode": "per_stage_policy_treatment_before_common_preheat",
                "reference_variant": "treatment",
                "target_seconds": ROLE_TARGET_SECONDS,
                "freeze_scope": "one cell ITER reused by its six C/T roles",
                "global_fixed_iters": "prohibited",
            },
            "static_audit_required_for_headline": True,
            "ncu_audit_required_for_headline": True,
        },
        "metric": {
            "name": "stage_ATC_pJ_per_logical_output_element",
            "formula": (
                "balanced treatment-minus-interpolated-control trace power "
                "divided by treatment logical-output rate"
            ),
            "primary_denominator": "logical_softmax_output_element",
            "idle_usage": "diagnostic_only_excluded_from_ATC_numerator",
            "sink_usage": "treatment_invariant_observer_not_an_effect_source",
            "not_total_softmax_energy": True,
        },
        "placement_contract": {
            "runtime_sm_count": 82,
            "underfilled_grid": True,
            "capacity_formula": "runtime_sm_count*occupancy_max_blocks_per_sm",
            "capacity_gate": "grid_blocks<=static_single_wave_capacity_blocks",
            "smid_total_blocks": GRID_BLOCKS,
            "smid_unique": GRID_BLOCKS,
            "smid_max_blocks_on_sm": 1,
            "smid_histogram_ok": True,
        },
        "thermal_contract": {
            "preheat_requested_s": PREHEAT_REQUESTED_S,
            "preheat_actual_gate_s": [PREHEAT_MIN_S, PREHEAT_MAX_S],
            "preheat_mode": "common_fp32_whole_softmax_v1",
        },
        "energy_contract": {
            "source": "nvml_total_energy",
            "trace_sample_ms": 250.0,
            "trace_min_updates": TRACE_MIN_FIT_POINTS,
            "integration": "guarded_interior_theil_sen",
            "idle_seconds": 1.0,
            "idle_is_diagnostic_only": True,
        },
        "schemas": {
            "binary_contract": BINARY_CONTRACT_SCHEMA,
            "ncu_audit": NCU_AUDIT_SCHEMA,
            "raw": RAW_SCHEMA,
            "trace": TRACE_SCHEMA,
            "raw_required_fields": sorted(RAW_REQUIRED),
            "trace_required_fields": sorted(TRACE_REQUIRED),
        },
        "sessions": sessions,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return run_dir, expected


def build_ncu_binding_fixture(root: Path) -> tuple[dict[str, Any], Path]:
    """Create minimal valid dynamic-audit evidence for negative gate tests."""

    root.mkdir(parents=True)
    binary_path = root / "binary"
    binary_path.write_bytes(b"binary")
    binary_hash = sha256_file(binary_path)

    capture_payload: dict[str, dict[str, Any]] = {}
    capture_binding: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        capture_payload[stage] = {"stage": stage}
        capture_binding[stage] = {}
        for name in NCU_CAPTURE_NAMES:
            path = root / f"{stage}.{name}"
            path.write_bytes(f"{stage}:{name}".encode("utf-8"))
            metadata = {
                "path": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            capture_payload[stage][name] = metadata
            capture_binding[stage][name] = {
                **metadata,
                "path": str(path),
            }

    pairs: list[dict[str, Any]] = []
    launches: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for stage in STAGES:
        for policy in POLICIES:
            symbol = f"whole_softmax_stage_atc_kernel<{stage},{policy}>"
            pairs.append(
                {
                    "stage": stage,
                    "policy": policy,
                    "status": "pass",
                    "failure_reasons": [],
                    "checks": {
                        "same_demangled_kernel_symbol": True,
                        "exact_instruction_delta": True,
                        "global_store_equal": True,
                    },
                    "control_kernel_name": symbol,
                    "treatment_kernel_name": symbol,
                    "grid_blocks": GRID_BLOCKS,
                    "threads_per_block": THREADS_PER_BLOCK,
                }
            )
            launches.extend(
                (
                    {"stage": stage, "policy": policy, "role": "control"},
                    {"stage": stage, "policy": policy, "role": "treatment"},
                )
            )
            summary_rows.append(
                {
                    "schema_version": NCU_AUDIT_SCHEMA,
                    "stage": stage,
                    "policy": policy,
                    "same_demangled_kernel_symbol": "true",
                    "grid_blocks": GRID_BLOCKS,
                    "threads_per_block": THREADS_PER_BLOCK,
                    "control_kernel_name": symbol,
                    "treatment_kernel_name": symbol,
                    "global_store_equal": "true",
                    "status": "pass",
                    "failure_reasons": "",
                    "binary_sha256": binary_hash,
                    "raw_ncu_csv_sha256": capture_payload[stage]["raw_csv"]["sha256"],
                    "ncu_report_sha256": capture_payload[stage]["ncu_report"]["sha256"],
                    "energy_usable": "false",
                }
            )
    summary_path = root / "audit.csv"
    write_fixture_csv(summary_path, tuple(summary_rows[0]), summary_rows)
    summary_metadata = {
        "path": summary_path.name,
        "sha256": sha256_file(summary_path),
        "bytes": summary_path.stat().st_size,
    }
    audit: dict[str, Any] = {
        "schema_version": NCU_AUDIT_SCHEMA,
        "status": "pass",
        "artifact_path_base": "audit_json_parent",
        "target_profile": "rtx3090",
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
        },
        "binary": {
            "sha256": binary_hash,
            "contract": {
                "schema_version": BINARY_CONTRACT_SCHEMA,
                "kernel_contract": "whole_softmax_stage_atc_same_symbol_runtime_flag_v2",
                "same_kernel_symbol_control_treatment": True,
                "treatment_invariant_sink": True,
            },
        },
        "launch_count": NCU_LAUNCH_COUNT,
        "pair_count": NCU_PAIR_COUNT,
        "launches": launches,
        "pairs": pairs,
        "captures": capture_payload,
        "summary_csv": summary_metadata,
        "energy_usable": False,
    }
    canonical = (
        json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    audit["provenance_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    audit_path = root / "audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "binary": {"path": str(binary_path), "sha256": binary_hash},
        "ncu_audit": {
            "schema_version": NCU_AUDIT_SCHEMA,
            "status": "pass",
            "path": str(audit_path),
            "sha256": sha256_file(audit_path),
            "binary_sha256": binary_hash,
            "target_profile": "rtx3090",
            "coordinate": audit["coordinate"],
            "launch_count": NCU_LAUNCH_COUNT,
            "pair_count": NCU_PAIR_COUNT,
            "energy_usable": False,
            "summary_csv": {
                **summary_metadata,
                "path": str(summary_path),
            },
            "captures": capture_binding,
        },
    }
    return manifest, root / capture_payload["exp"]["raw_csv"]["path"]


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="softmax_stage_atc_test_") as temporary:
        root = Path(temporary)
        valid_run, expected = build_synthetic_fixture(root / "valid")
        analysis = analyze_run(valid_run)
        require(analysis["role_count"] == 162, "self-test role count")
        require(analysis["cell_count"] == 27, "self-test cell count")
        require(analysis["orientation_effect_count"] == 54, "self-test effect count")
        for row in analysis["implementation_stage_summary"]:
            close(
                float(row["mean_atc_delta_pJ_per_logical_output_element"]),
                expected[(str(row["stage"]), str(row["policy"]))],
                "self-test recovered effect",
                rel=1.0e-8,
                abs_=1.0e-6,
            )
            close(
                float(
                    row[
                        "mean_same_iter_gross_board_energy_contrast_pJ_per_logical_output"
                    ]
                ),
                expected[(str(row["stage"]), str(row["policy"]))],
                "self-test recovered same-ITER diagnostic for equal durations",
                rel=1.0e-8,
                abs_=1.0e-6,
            )
            close(
                float(row["mean_treatment_over_control_elapsed_ratio"]),
                1.0,
                "self-test recovered equal treatment/control elapsed ratio",
                rel=1.0e-12,
                abs_=1.0e-12,
            )
        synthetic_out = valid_run / "analysis"
        write_outputs(analysis, synthetic_out)
        expected_outputs = {
            "matched_effects.csv",
            "session_summary.csv",
            "cell_summary.csv",
            "quality_gates.csv",
            "analysis.json",
            "summary.md",
        }
        require(
            {path.name for path in synthetic_out.iterdir()} == expected_outputs,
            "self-test standardized output set mismatch",
        )
        require(
            len(read_csv_strict(
                synthetic_out / "matched_effects.csv",
                frozenset({"stage", "policy", "orientation", "effect_pJ_per_logical_output"}),
                "self-test matched effects",
            )[0])
            == 54,
            "self-test matched-effect output count",
        )

        invalid_denominator, _ = build_synthetic_fixture(
            root / "denominator_fault", denominator_fault=True
        )
        try:
            analyze_run(invalid_denominator)
        except AnalysisError as error:
            require("denominator" in str(error), "self-test denominator rejection reason")
        else:
            raise AnalysisError("self-test failed to reject denominator corruption")

        invalid_digest, _ = build_synthetic_fixture(
            root / "digest_fault", digest_fault=True
        )
        try:
            analyze_run(invalid_digest)
        except AnalysisError as error:
            require("digest" in str(error), "self-test digest rejection reason")
        else:
            raise AnalysisError("self-test failed to reject output mismatch")

        invalid_sink, _ = build_synthetic_fixture(
            root / "sink_fault", sink_fault=True
        )
        try:
            analyze_run(invalid_sink)
        except AnalysisError as error:
            require("sink" in str(error), "self-test sink rejection reason")
        else:
            raise AnalysisError(
                "self-test failed to reject treatment-dependent sink switching"
            )
        missing_audit, _ = build_synthetic_fixture(root / "missing_static_audit")
        missing_audit_manifest_path = missing_audit / "manifest.json"
        missing_audit_manifest = read_json(missing_audit_manifest_path)
        missing_audit_manifest.pop("analysis_test_fixture", None)
        missing_audit_manifest_path.write_text(
            json.dumps(missing_audit_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            analyze_run(missing_audit)
        except AnalysisError as error:
            require(
                "static_audit" in str(error),
                "self-test missing-static-audit rejection reason",
            )
        else:
            raise AnalysisError("self-test failed to reject unbound real run")

        ncu_manifest, ncu_capture = build_ncu_binding_fixture(root / "ncu_binding")
        validate_bound_ncu_audit(ncu_manifest, root / "ncu_binding")
        missing_ncu_manifest = {"binary": dict(ncu_manifest["binary"])}
        try:
            validate_bound_ncu_audit(missing_ncu_manifest, root / "ncu_binding")
        except AnalysisError as error:
            require(
                "ncu_audit" in str(error),
                "self-test missing-NCU rejection reason",
            )
        else:
            raise AnalysisError("self-test failed to reject a missing NCU binding")
        ncu_capture.write_bytes(ncu_capture.read_bytes() + b"tamper")
        try:
            validate_bound_ncu_audit(ncu_manifest, root / "ncu_binding")
        except AnalysisError as error:
            require(
                "SHA-256 mismatch" in str(error),
                "self-test tampered-NCU rejection reason",
            )
        else:
            raise AnalysisError("self-test failed to reject tampered NCU evidence")
    print(
        "self_test=pass "
        "scenarios=valid_end_to_end_outputs,denominator_rejection,"
        "output_digest_rejection,treatment_invariant_sink_rejection,"
        "missing_static_audit_rejection,missing_ncu_audit_rejection,"
        "tampered_ncu_capture_rejection"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.run_dir is None:
        raise SystemExit("--run-dir is required unless --self-test is used")
    analysis = analyze_run(args.run_dir)
    out_dir = args.out_dir or args.run_dir / "analysis"
    write_outputs(analysis, out_dir)
    print(f"analysis_status={analysis['status']}")
    print(f"roles={analysis['role_count']}")
    print(f"cells={analysis['cell_count']}")
    print(f"orientation_effects={analysis['orientation_effect_count']}")
    print(f"summary_rows={analysis['summary_count']}")
    print(f"analysis_json={out_dir / 'analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
