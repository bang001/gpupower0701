#!/usr/bin/env python3
"""Fail-closed Nsight Compute audit for whole-stage Operand-rate ATC.

This sidecar profiles the RTX 3090 v2 validation path at the frozen
``S=1024, grid=41, threads=256`` coordinate.  One application process is
profiled for each selected Softmax stage.  The validation path launches the
three policies in canonical order, and each policy launches control followed
by treatment through the same demangled kernel symbol.

The audit is deliberately about dynamic instruction attribution, not energy:
Nsight Compute replays kernels and therefore its timing and any concurrent
NVML samples are not valid Operand-rate ATC energy observations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "softmax_whole_stage_atc_ncu_audit_v1"
BINARY_CONTRACT = "softmax_whole_stage_atc_binary_contract_v2"
KERNEL_CONTRACT = "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"

TARGET_PROFILE = "rtx3090"
SOFTMAX_COLS = 1024
GRID_BLOCKS = 41
THREADS_PER_BLOCK = 256
ROWS_PER_BLOCK = 2

STAGES = (("exp", 0), ("reduction", 1), ("normalization", 2))
POLICIES = (("fp32", 0), ("fp16_scalar", 1), ("fp16x2", 2))
EXPECTED_LAUNCHES_PER_STAGE = len(POLICIES) * 2

KNOWN_ABORTED_BINARY = Path(
    "/tmp/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_final_aborted_cse"
    "/frozen/a100_fp16_softmax_whole_stage_atc"
)
KNOWN_ABORTED_BINARY_SHA256 = (
    "115ae86e2bc339fb6163e66c8f9b652adb2e42cc48cc112138616b3986b060bb"
)

METRICS = {
    "total_thread_instructions": (
        "smsp__sass_thread_inst_executed_pred_on.sum"
    ),
    "fmul_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_fmul_pred_on.sum"
    ),
    "hmul_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_hmul_pred_on.sum"
    ),
    "fadd_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_fadd_pred_on.sum"
    ),
    "hadd_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_hadd_pred_on.sum"
    ),
    "fp16_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_fp16_pred_on.sum"
    ),
    "fp32_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_fp32_pred_on.sum"
    ),
    "misc_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_misc_pred_on.sum"
    ),
    "conversion_thread_instructions": (
        "smsp__sass_thread_inst_executed_op_conversion_pred_on.sum"
    ),
    "global_store_warp_instructions": "smsp__inst_executed_op_global_st.sum",
}
NCU_METRICS = ",".join(METRICS.values())

# Exact C->T SASS-thread deltas per CTA for the frozen v2 semantic
# coordinate.  The values are cardinalities, not performance estimates.
# Unlisted metrics have an expected delta of zero.  Multiplication/addition
# counters identify the selected arithmetic, the FP16/FP32 class counters
# expose the corresponding max or special-function instructions, and the
# total counter also covers control-flow/observer instructions.
EXPECTED_NONZERO_DELTA_PER_BLOCK = {
    ("exp", "fp32"): {
        "total_thread_instructions": 4096,
        "fmul_thread_instructions": 2048,
        "fp32_thread_instructions": 4096,
    },
    ("exp", "fp16_scalar"): {
        "total_thread_instructions": 4096,
        "hmul_thread_instructions": 2048,
        "fp16_thread_instructions": 2048,
        "fp32_thread_instructions": 2048,
    },
    ("exp", "fp16x2"): {
        "total_thread_instructions": 4096,
        "hmul_thread_instructions": 1024,
        "fp16_thread_instructions": 1024,
        "fp32_thread_instructions": 2048,
    },
    ("reduction", "fp32"): {
        "total_thread_instructions": 20420,
        "fadd_thread_instructions": 2880,
        "fp32_thread_instructions": 5760,
        "misc_thread_instructions": 3584,
    },
    ("reduction", "fp16_scalar"): {
        "total_thread_instructions": 29168,
        "hadd_thread_instructions": 510,
        "fp16_thread_instructions": 1020,
        "misc_thread_instructions": 10240,
    },
    ("reduction", "fp16x2"): {
        "total_thread_instructions": 10232,
        "hadd_thread_instructions": 255,
        "fp16_thread_instructions": 510,
        "misc_thread_instructions": 5120,
    },
    ("normalization", "fp32"): {
        "total_thread_instructions": 2560,
        "fmul_thread_instructions": 2048,
        "fp32_thread_instructions": 2560,
    },
    ("normalization", "fp16_scalar"): {
        "total_thread_instructions": 6144,
        "hmul_thread_instructions": 2048,
        "hadd_thread_instructions": 512,
        "fp16_thread_instructions": 2560,
        "fp32_thread_instructions": 512,
        "conversion_thread_instructions": 512,
    },
    ("normalization", "fp16x2"): {
        "total_thread_instructions": 3072,
        "hmul_thread_instructions": 1024,
        "hadd_thread_instructions": 512,
        "fp16_thread_instructions": 1536,
        "fp32_thread_instructions": 512,
        "conversion_thread_instructions": 512,
    },
}

TARGET_KERNEL_TOKEN = "whole_softmax_stage_atc_kernel"
KERNEL_TEMPLATE_RE = re.compile(
    r"whole_softmax_stage_atc_kernel<\s*(?P<cols>\d+)\s*,"
    r"\s*(?P<stage>[^,>]+)\s*,\s*(?P<policy>[^,>]+)\s*>"
)
VALIDATION_LINE_RE = re.compile(
    r"^validation=pass stage=(?P<stage>exp|reduction|normalization) "
    r"cells=3 output_bit_identical=1 live_sink_written=1 "
    r"treatment_invariant_sink=1$",
    re.MULTILINE,
)


class AuditError(RuntimeError):
    """Raised whenever evidence is absent, ambiguous, or contradictory."""


@dataclass(frozen=True)
class CaptureArtifact:
    """Files and process metadata for one stage-level NCU capture."""

    stage: str
    command: tuple[str, ...]
    started_at: str
    ended_at: str
    csv_path: Path
    report_path: Path
    stdout_path: Path
    stderr_path: Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_text(path: Path, value: str) -> None:
    atomic_bytes(path, value.encode("utf-8"))


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_bytes(
        path,
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n",
    )


def executable_path(explicit: Path | None) -> Path:
    candidates: list[str] = []
    if explicit is not None:
        candidates.append(str(explicit.expanduser()))
    else:
        environment = os.environ.get("NCU")
        if environment:
            candidates.append(environment)
        candidates.extend(
            (
                "/home/bang001/.local/NVIDIA-Nsight-Compute-2026.2.1/ncu",
                "ncu",
            )
        )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
        discovered = shutil.which(candidate)
        if discovered:
            resolved = Path(discovered).resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return resolved
    raise AuditError("Nsight Compute CLI (ncu) was not found or is not executable")


def ncu_version(ncu: Path) -> str:
    completed = subprocess.run(
        [str(ncu), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    require(completed.returncode == 0, "ncu --version failed")
    combined = "\n".join((completed.stdout, completed.stderr))
    match = re.search(r"^Version\s+(.+?)\s*$", combined, re.MULTILINE)
    require(match is not None, "unable to parse ncu version")
    return match.group(1)


def reject_known_aborted_binary(binary: Path, binary_hash: str) -> None:
    resolved_aborted = KNOWN_ABORTED_BINARY.resolve(strict=False)
    require(
        binary.resolve(strict=False) != resolved_aborted,
        "known_aborted_cse_binary_rejected_by_path",
    )
    require(
        binary_hash != KNOWN_ABORTED_BINARY_SHA256,
        "known_aborted_cse_binary_rejected_by_sha256",
    )


def parse_describe_stdout(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    require(len(lines) == 1, "binary --describe must emit exactly one JSON line")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise AuditError("binary --describe did not emit valid JSON") from error
    require(isinstance(payload, dict), "binary --describe JSON must be an object")
    return payload


def validate_binary_contract(payload: dict[str, Any]) -> None:
    exact = {
        "schema_version": BINARY_CONTRACT,
        "kernel_contract": KERNEL_CONTRACT,
        "treatment_invariant_sink": True,
        "symmetric_opaque_stage_inputs": True,
        "same_kernel_symbol_control_treatment": True,
        "output_equivalence_validation": True,
        "persistent_cuda_context": True,
        "rows_per_block": ROWS_PER_BLOCK,
    }
    failures = [
        f"{field}={payload.get(field)!r}, expected {expected!r}"
        for field, expected in exact.items()
        if payload.get(field) != expected
    ]
    if payload.get("stages") != [stage for stage, _ in STAGES]:
        failures.append(f"unexpected stages={payload.get('stages')!r}")
    if payload.get("policies") != [policy for policy, _ in POLICIES]:
        failures.append(f"unexpected policies={payload.get('policies')!r}")
    require(not failures, "binary_contract_rejected: " + "; ".join(failures))


def inspect_binary(binary: Path, describe_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [str(binary), "--describe"],
        check=False,
        capture_output=True,
        text=True,
    )
    require(
        completed.returncode == 0,
        "binary --describe failed: "
        + (completed.stderr.strip() or completed.stdout.strip()),
    )
    payload = parse_describe_stdout(completed.stdout)
    validate_binary_contract(payload)
    atomic_text(describe_path, completed.stdout)
    return payload


def classify_ncu_failure(text: str) -> str:
    lowered = text.lower()
    if "err_nvgpuctrperm" in lowered or "permission" in lowered:
        return "ncu_counter_permission_denied"
    if (
        "unknown metric" in lowered
        or "cannot be found" in lowered
        or "not available" in lowered
        or "unsupported metric" in lowered
    ):
        return "ncu_metric_unavailable"
    if "no kernels were profiled" in lowered:
        return "ncu_target_kernel_not_captured"
    return "ncu_capture_failed"


def build_capture_command(
    *,
    ncu: Path,
    binary: Path,
    out_dir: Path,
    gpu_id: int,
    stage: str,
) -> tuple[list[str], Path, Path]:
    csv_path = out_dir / f"{stage}.ncu.csv"
    report_base = out_dir / stage
    report_path = out_dir / f"{stage}.ncu-rep"
    command = [
        str(ncu),
        "--target-processes",
        "all",
        "--csv",
        "--page",
        "raw",
        "--print-units",
        "base",
        "--print-fp",
        "--cache-control",
        "none",
        "--clock-control",
        "none",
        "--metrics",
        NCU_METRICS,
        "--kernel-name",
        f"regex:{TARGET_KERNEL_TOKEN}",
        "--kernel-name-base",
        "demangled",
        "--print-kernel-base",
        "demangled",
        "--export",
        str(report_base),
        "--force-overwrite",
        "--log-file",
        str(csv_path),
        str(binary),
        "--validate-only",
        "--gpu-id",
        str(gpu_id),
        "--target-profile",
        TARGET_PROFILE,
        "--stage",
        stage,
        "--policy-schedule",
        ",".join(policy for policy, _ in POLICIES),
        "--calibration-policy-schedule",
        ",".join(policy for policy, _ in POLICIES),
        "--bracket-schedule",
        "ctc,tct",
        "--session-order",
        "ABC",
        "--session-index",
        "1",
        "--session-id",
        f"ncu_dynamic_audit_{stage}",
        "--softmax-cols",
        str(SOFTMAX_COLS),
        "--grid-blocks",
        str(GRID_BLOCKS),
        "--threads-per-block",
        str(THREADS_PER_BLOCK),
        "--rows-per-block",
        str(ROWS_PER_BLOCK),
    ]
    return command, csv_path, report_path


def run_stage_capture(
    *,
    ncu: Path,
    binary: Path,
    out_dir: Path,
    gpu_id: int,
    stage: str,
) -> CaptureArtifact:
    command, csv_path, report_path = build_capture_command(
        ncu=ncu,
        binary=binary,
        out_dir=out_dir,
        gpu_id=gpu_id,
        stage=stage,
    )
    stdout_path = out_dir / f"{stage}.target.stdout.log"
    stderr_path = out_dir / f"{stage}.target.stderr.log"
    started_at = timestamp()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    ended_at = timestamp()
    atomic_text(stdout_path, completed.stdout)
    atomic_text(stderr_path, completed.stderr)
    if completed.returncode != 0:
        combined = "\n".join((completed.stdout, completed.stderr))
        category = classify_ncu_failure(combined)
        raise AuditError(
            f"{category}: stage={stage}, exit={completed.returncode}; "
            f"see {stdout_path} and {stderr_path}"
        )
    matches = [
        match.group("stage")
        for match in VALIDATION_LINE_RE.finditer(completed.stdout)
    ]
    require(
        matches == [stage],
        f"validate-only completion evidence mismatch for stage={stage}: {matches}",
    )
    require(
        csv_path.is_file() and csv_path.stat().st_size > 0,
        f"NCU CSV missing or empty for stage={stage}",
    )
    require(
        report_path.is_file() and report_path.stat().st_size > 0,
        f"NCU report missing or empty for stage={stage}",
    )
    return CaptureArtifact(
        stage=stage,
        command=tuple(command),
        started_at=started_at,
        ended_at=ended_at,
        csv_path=csv_path,
        report_path=report_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def ncu_csv_rows_from_text(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    try:
        header_index = next(
            index
            for index, line in enumerate(lines)
            if line.startswith('"ID",') or line.startswith("ID,")
        )
    except StopIteration as error:
        raise AuditError("NCU raw CSV header not found") from error
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[header_index:]))))
    kernels = [
        row
        for row in rows
        if TARGET_KERNEL_TOKEN in demangled_kernel_name(row)
    ]
    require(
        len(kernels) == EXPECTED_LAUNCHES_PER_STAGE,
        "expected exactly "
        f"{EXPECTED_LAUNCHES_PER_STAGE} target kernel rows, got {len(kernels)}",
    )
    return kernels


def read_ncu_csv(path: Path) -> list[dict[str, str]]:
    return ncu_csv_rows_from_text(path.read_text(encoding="utf-8"))


def demangled_kernel_name(row: dict[str, str]) -> str:
    return (
        row.get("Kernel Name", "")
        or row.get("launch__kernel_name", "")
    ).strip()


def decimal_value(
    row: dict[str, str],
    field: str,
    *,
    nonnegative: bool = True,
) -> Decimal:
    raw = (row.get(field) or "").replace(",", "").strip()
    require(
        raw.lower() not in {"", "n/a", "na", "--", "nan", "+nan", "-nan"},
        f"missing NCU field {field}",
    )
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise AuditError(f"NCU field {field} is not numeric: {raw!r}") from error
    require(value.is_finite(), f"NCU field {field} is not finite: {raw!r}")
    if nonnegative:
        require(value >= 0, f"NCU field {field} is negative: {raw!r}")
    return value


def integer_value(row: dict[str, str], field: str) -> int:
    value = decimal_value(row, field)
    integral = value.to_integral_value()
    require(value == integral, f"NCU field {field} is not integral: {value}")
    return int(integral)


def launch_size(row: dict[str, str], scalar: str, tuple_field: str) -> int:
    raw = (row.get(scalar) or "").replace(",", "").strip()
    if raw:
        value = Decimal(raw)
        require(
            value == value.to_integral_value() and value > 0,
            f"invalid launch field {scalar}={raw!r}",
        )
        return int(value)
    tuple_raw = (row.get(tuple_field) or "").strip("() ")
    try:
        parts = [int(part.strip()) for part in tuple_raw.split(",") if part.strip()]
    except ValueError as error:
        raise AuditError(f"invalid launch tuple {tuple_field}={tuple_raw!r}") from error
    require(bool(parts) and all(part > 0 for part in parts), "invalid launch tuple")
    return math.prod(parts)


def launch_id(row: dict[str, str]) -> int:
    return integer_value(row, "ID")


def enum_value(token: str, labels: Iterable[tuple[str, int]]) -> int:
    cleaned = token.strip()
    direct = re.fullmatch(r"-?\d+", cleaned)
    if direct:
        return int(cleaned)
    lowered = cleaned.lower()
    for label, value in labels:
        if lowered.endswith(f"::{label.lower()}") or lowered == label.lower():
            return value
    cast_number = re.search(r"\)?\s*(-?\d+)\s*$", cleaned)
    if cast_number:
        return int(cast_number.group(1))
    raise AuditError(f"unable to decode kernel template enum token: {token!r}")


def kernel_coordinate(name: str) -> tuple[int, int, int]:
    match = KERNEL_TEMPLATE_RE.search(name)
    require(match is not None, f"unable to parse demangled kernel symbol: {name}")
    return (
        int(match.group("cols")),
        enum_value(match.group("stage"), STAGES),
        enum_value(match.group("policy"), POLICIES),
    )


def row_metric_values(row: dict[str, str]) -> dict[str, Decimal]:
    return {
        label: decimal_value(row, metric)
        for label, metric in METRICS.items()
    }


def decimal_json(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def positive_integral_multiple(value: Decimal, divisor: int) -> bool:
    integral = value.to_integral_value()
    return (
        value > 0
        and value == integral
        and int(integral) % divisor == 0
    )


def expected_metric_deltas(stage: str, policy: str) -> dict[str, Decimal]:
    key = (stage, policy)
    require(
        key in EXPECTED_NONZERO_DELTA_PER_BLOCK,
        f"missing exact dynamic contract for stage={stage}, policy={policy}",
    )
    nonzero = EXPECTED_NONZERO_DELTA_PER_BLOCK[key]
    require(
        set(nonzero).issubset(METRICS),
        f"unknown metric in exact dynamic contract for {key}",
    )
    return {
        label: Decimal(nonzero.get(label, 0) * GRID_BLOCKS)
        for label in METRICS
    }


def derived_stage_signals(
    stage: str,
    policy: str,
    deltas: dict[str, Decimal],
) -> dict[str, Decimal]:
    if stage == "exp":
        multiply = (
            deltas["fmul_thread_instructions"]
            + deltas["hmul_thread_instructions"]
        )
        special = (
            deltas["fp32_thread_instructions"]
            - deltas["fmul_thread_instructions"]
            - deltas["fadd_thread_instructions"]
        )
        return {
            "exp_multiply_thread_instructions": multiply,
            "exp_special_function_thread_instructions": special,
        }
    if stage == "reduction":
        add = (
            deltas["fadd_thread_instructions"]
            + deltas["hadd_thread_instructions"]
        )
        precision_class = (
            deltas["fp32_thread_instructions"]
            if policy == "fp32"
            else deltas["fp16_thread_instructions"]
        )
        return {
            "reduction_sum_add_thread_instructions": add,
            "reduction_max_thread_instructions": precision_class - add,
        }
    multiply = (
        deltas["fmul_thread_instructions"]
        + deltas["hmul_thread_instructions"]
    )
    reciprocal = (
        deltas["fp32_thread_instructions"]
        - deltas["fmul_thread_instructions"]
        - deltas["fadd_thread_instructions"]
    )
    return {
        "normalization_multiply_thread_instructions": multiply,
        "normalization_reciprocal_thread_instructions": reciprocal,
    }


def artifact_provenance(artifact: CaptureArtifact) -> dict[str, Any]:
    # Every capture is created directly in the audit output directory.  Store
    # its basename so the committed audit remains valid after a clone or
    # checkout move; consumers resolve these paths against audit.json.
    return {
        "stage": artifact.stage,
        "command": list(artifact.command),
        "capture_started_at": artifact.started_at,
        "capture_ended_at": artifact.ended_at,
        "raw_csv": {
            "path": artifact.csv_path.name,
            "bytes": artifact.csv_path.stat().st_size,
            "sha256": sha256_file(artifact.csv_path),
        },
        "ncu_report": {
            "path": artifact.report_path.name,
            "bytes": artifact.report_path.stat().st_size,
            "sha256": sha256_file(artifact.report_path),
        },
        "target_stdout": {
            "path": artifact.stdout_path.name,
            "bytes": artifact.stdout_path.stat().st_size,
            "sha256": sha256_file(artifact.stdout_path),
        },
        "target_stderr": {
            "path": artifact.stderr_path.name,
            "bytes": artifact.stderr_path.stat().st_size,
            "sha256": sha256_file(artifact.stderr_path),
        },
    }


def device_name(row: dict[str, str]) -> str:
    return (
        row.get("device__attribute_display_name", "")
        or row.get("Device Name", "")
    ).strip()


def validate_stage_rows(
    *,
    stage: str,
    stage_index: int,
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(
        len(rows) == EXPECTED_LAUNCHES_PER_STAGE,
        f"stage={stage}: expected six target kernels",
    )
    ids = [launch_id(row) for row in rows]
    require(
        all(right > left for left, right in zip(ids, ids[1:])),
        f"stage={stage}: launch IDs are not strictly increasing: {ids}",
    )
    process_ids = {(row.get("Process ID") or "").strip() for row in rows}
    contexts = {(row.get("Context") or "").strip() for row in rows}
    require(
        len(process_ids) == 1 and "" not in process_ids,
        f"stage={stage}: launches are not from one process",
    )
    require(
        len(contexts) == 1 and "" not in contexts,
        f"stage={stage}: launches are not from one CUDA context",
    )

    launch_records: list[dict[str, Any]] = []
    pair_records: list[dict[str, Any]] = []
    symbols: list[str] = []

    for policy_position, (policy, policy_index) in enumerate(POLICIES):
        control = rows[policy_position * 2]
        treatment = rows[policy_position * 2 + 1]
        control_id = launch_id(control)
        treatment_id = launch_id(treatment)
        require(
            treatment_id > control_id,
            f"stage={stage}, policy={policy}: treatment must follow control",
        )

        control_name = demangled_kernel_name(control)
        treatment_name = demangled_kernel_name(treatment)
        same_symbol = bool(control_name) and control_name == treatment_name
        expected_coordinate = (SOFTMAX_COLS, stage_index, policy_index)
        control_coordinate = kernel_coordinate(control_name)
        treatment_coordinate = kernel_coordinate(treatment_name)

        control_metrics = row_metric_values(control)
        treatment_metrics = row_metric_values(treatment)
        deltas = {
            label: treatment_metrics[label] - control_metrics[label]
            for label in METRICS
        }
        expected_deltas = expected_metric_deltas(stage, policy)
        signals = derived_stage_signals(stage, policy, deltas)
        expected_signals = derived_stage_signals(
            stage, policy, expected_deltas
        )
        if stage == "reduction":
            selected_math_labels = (
                "fadd_thread_instructions",
                "hadd_thread_instructions",
            )
        else:
            selected_math_labels = (
                "fmul_thread_instructions",
                "hmul_thread_instructions",
            )
        control_math = sum(
            (control_metrics[label] for label in selected_math_labels),
            Decimal(0),
        )
        treatment_math = sum(
            (treatment_metrics[label] for label in selected_math_labels),
            Decimal(0),
        )
        math_delta = treatment_math - control_math

        control_grid = launch_size(
            control, "launch__grid_size", "Grid Size"
        )
        treatment_grid = launch_size(
            treatment, "launch__grid_size", "Grid Size"
        )
        control_block = launch_size(
            control, "launch__block_size", "Block Size"
        )
        treatment_block = launch_size(
            treatment, "launch__block_size", "Block Size"
        )
        control_cc = decimal_value(control, "CC")
        treatment_cc = decimal_value(treatment, "CC")
        control_device = device_name(control)
        treatment_device = device_name(treatment)

        resource_fields = (
            "launch__registers_per_thread",
            "launch__shared_mem_per_block_static",
        )
        resource_pairs = {
            field: (
                decimal_value(control, field),
                decimal_value(treatment, field),
            )
            for field in resource_fields
        }
        resources_equal = all(
            left == right for left, right in resource_pairs.values()
        )

        checks = {
            "control_precedes_treatment": treatment_id > control_id,
            "same_demangled_kernel_symbol": same_symbol,
            "control_kernel_coordinate": control_coordinate
            == expected_coordinate,
            "treatment_kernel_coordinate": treatment_coordinate
            == expected_coordinate,
            "grid_blocks_41": control_grid
            == treatment_grid
            == GRID_BLOCKS,
            "threads_per_block_256": control_block
            == treatment_block
            == THREADS_PER_BLOCK,
            "rtx3090_device": (
                "RTX 3090" in control_device
                and control_device == treatment_device
            ),
            "compute_capability_8_6": (
                control_cc == treatment_cc == Decimal("8.6")
            ),
            "same_launch_resources": resources_equal,
            "nonzero_global_store": (
                control_metrics["global_store_warp_instructions"] > 0
            ),
            "global_store_equal": (
                deltas["global_store_warp_instructions"] == 0
            ),
            "total_thread_instructions_increase": (
                deltas["total_thread_instructions"] > 0
            ),
            "total_thread_delta_exact_grid_multiple": (
                positive_integral_multiple(
                    deltas["total_thread_instructions"], GRID_BLOCKS
                )
            ),
            "selected_math_instructions_increase": math_delta > 0,
            "selected_math_delta_exact_grid_multiple": (
                positive_integral_multiple(math_delta, GRID_BLOCKS)
            ),
        }
        for label in METRICS:
            checks[f"exact_delta_{label}"] = (
                deltas[label] == expected_deltas[label]
            )
        for label, value in signals.items():
            checks[f"positive_{label}"] = value > 0
            checks[f"exact_{label}"] = value == expected_signals[label]
            checks[f"grid_multiple_{label}"] = (
                positive_integral_multiple(value, GRID_BLOCKS)
            )
        if stage == "reduction":
            checks["reduction_math_instructions_increase"] = math_delta > 0

        failed = [name for name, passed in checks.items() if not passed]
        pair_record: dict[str, Any] = {
            "stage": stage,
            "stage_index": stage_index,
            "policy": policy,
            "policy_index": policy_index,
            "control_launch_id": control_id,
            "treatment_launch_id": treatment_id,
            "control_kernel_name": control_name,
            "treatment_kernel_name": treatment_name,
            "control_kernel_coordinate": list(control_coordinate),
            "treatment_kernel_coordinate": list(treatment_coordinate),
            "grid_blocks": control_grid,
            "threads_per_block": control_block,
            "device_name": control_device,
            "compute_capability": str(control_cc),
            "control_metrics": {
                label: decimal_json(value)
                for label, value in control_metrics.items()
            },
            "treatment_metrics": {
                label: decimal_json(value)
                for label, value in treatment_metrics.items()
            },
            "delta_metrics": {
                label: decimal_json(value)
                for label, value in deltas.items()
            },
            "expected_delta_metrics": {
                label: decimal_json(value)
                for label, value in expected_deltas.items()
            },
            "derived_stage_signals": {
                label: decimal_json(value)
                for label, value in signals.items()
            },
            "expected_derived_stage_signals": {
                label: decimal_json(value)
                for label, value in expected_signals.items()
            },
            "selected_math_metric_labels": list(selected_math_labels),
            "control_selected_math_thread_instructions": decimal_json(
                control_math
            ),
            "treatment_selected_math_thread_instructions": decimal_json(
                treatment_math
            ),
            "delta_selected_math_thread_instructions": decimal_json(math_delta),
            "resource_pairs": {
                field: {
                    "control": decimal_json(left),
                    "treatment": decimal_json(right),
                }
                for field, (left, right) in resource_pairs.items()
            },
            "checks": checks,
            "status": "pass" if not failed else "fail",
            "failure_reasons": failed,
        }
        pair_records.append(pair_record)
        symbols.append(control_name)

        for role, row, values in (
            ("control", control, control_metrics),
            ("treatment", treatment, treatment_metrics),
        ):
            launch_records.append(
                {
                    "stage": stage,
                    "policy": policy,
                    "role": role,
                    "launch_id": launch_id(row),
                    "kernel_name": demangled_kernel_name(row),
                    "kernel_coordinate": list(
                        kernel_coordinate(demangled_kernel_name(row))
                    ),
                    "metrics": {
                        label: decimal_json(value)
                        for label, value in values.items()
                    },
                }
            )

    require(
        len(set(symbols)) == len(POLICIES),
        f"stage={stage}: policy specializations are not distinct",
    )
    return launch_records, pair_records


def summary_csv_rows(
    pair_records: list[dict[str, Any]],
    *,
    binary_hash: str,
    capture_provenance: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pair_records:
        stage_capture = capture_provenance[pair["stage"]]
        row: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "stage": pair["stage"],
            "policy": pair["policy"],
            "control_launch_id": pair["control_launch_id"],
            "treatment_launch_id": pair["treatment_launch_id"],
            "same_demangled_kernel_symbol": str(
                pair["checks"]["same_demangled_kernel_symbol"]
            ).lower(),
            "grid_blocks": pair["grid_blocks"],
            "threads_per_block": pair["threads_per_block"],
            "control_kernel_name": pair["control_kernel_name"],
            "treatment_kernel_name": pair["treatment_kernel_name"],
            "selected_math_metric_labels": ",".join(
                pair["selected_math_metric_labels"]
            ),
            "delta_selected_math_thread_instructions": pair[
                "delta_selected_math_thread_instructions"
            ],
            "global_store_equal": str(
                pair["checks"]["global_store_equal"]
            ).lower(),
            "status": pair["status"],
            "failure_reasons": ";".join(pair["failure_reasons"]),
            "binary_sha256": binary_hash,
            "raw_ncu_csv_sha256": stage_capture["raw_csv"]["sha256"],
            "ncu_report_sha256": stage_capture["ncu_report"]["sha256"],
            "energy_usable": "false",
        }
        for label in METRICS:
            row[f"control_{label}"] = pair["control_metrics"][label]
            row[f"treatment_{label}"] = pair["treatment_metrics"][label]
            row[f"delta_{label}"] = pair["delta_metrics"][label]
        rows.append(row)
    return rows


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), "refusing to write an empty summary CSV")
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, buffer.getvalue())


def failure_summary_csv(path: Path, reason: str, binary_hash: str) -> None:
    atomic_csv(
        path,
        [
            {
                "schema_version": SCHEMA_VERSION,
                "status": "fail",
                "failure_reasons": reason,
                "binary_sha256": binary_hash,
                "energy_usable": "false",
            }
        ],
    )


def successful_payload(
    *,
    binary: Path,
    binary_hash: str,
    binary_contract: dict[str, Any],
    describe_path: Path,
    ncu: Path,
    ncu_hash: str,
    version: str,
    artifacts: list[CaptureArtifact],
    launch_records: list[dict[str, Any]],
    pair_records: list[dict[str, Any]],
    summary_path: Path,
) -> dict[str, Any]:
    captures = {
        artifact.stage: artifact_provenance(artifact)
        for artifact in artifacts
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "pass"
            if all(pair["status"] == "pass" for pair in pair_records)
            else "fail"
        ),
        "created_at": timestamp(),
        "artifact_path_base": "audit_json_parent",
        "target_profile": TARGET_PROFILE,
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
        },
        "binary": {
            "path": os.path.relpath(binary.resolve(), summary_path.parent.resolve()),
            "bytes": binary.stat().st_size,
            "sha256": binary_hash,
            "contract": binary_contract,
            "describe_capture": {
                "path": describe_path.name,
                "bytes": describe_path.stat().st_size,
                "sha256": sha256_file(describe_path),
            },
            "known_aborted_binary_rejected": True,
            "known_aborted_binary_sha256": KNOWN_ABORTED_BINARY_SHA256,
        },
        "ncu": {
            "path": str(ncu),
            "bytes": ncu.stat().st_size,
            "sha256": ncu_hash,
            "version": version,
            "metrics": METRICS,
            "cache_control": "none",
            "clock_control": "none",
            "kernel_name_basis": "demangled",
        },
        "expected_launch_order_per_stage": [
            {"policy": policy, "role": role}
            for policy, _ in POLICIES
            for role in ("control", "treatment")
        ],
        "captures": captures,
        "launch_count": len(launch_records),
        "pair_count": len(pair_records),
        "launches": launch_records,
        "pairs": pair_records,
        "summary_csv": {
            "path": summary_path.name,
            "bytes": summary_path.stat().st_size,
            "sha256": sha256_file(summary_path),
        },
        "energy_usable": False,
        "energy_exclusion_reason": (
            "Nsight Compute kernel replay changes execution and timing; "
            "this audit is dynamic instruction evidence only"
        ),
    }
    payload["provenance_payload_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def failure_payload(
    *,
    reason: str,
    binary: Path | None,
    binary_hash: str,
    ncu: Path | None,
    ncu_hash: str,
    artifacts: list[CaptureArtifact],
    summary_path: Path | None,
) -> dict[str, Any]:
    captures: dict[str, Any] = {}
    for artifact in artifacts:
        if all(
            path.is_file()
            for path in (
                artifact.csv_path,
                artifact.report_path,
                artifact.stdout_path,
                artifact.stderr_path,
            )
        ):
            captures[artifact.stage] = artifact_provenance(artifact)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail",
        "created_at": timestamp(),
        "artifact_path_base": "audit_json_parent",
        "failure": reason,
        "target_profile": TARGET_PROFILE,
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
        },
        "binary": {
            "path": (
                os.path.relpath(
                    binary.resolve(),
                    (summary_path.parent if summary_path is not None else binary.parent).resolve(),
                )
                if binary is not None
                else ""
            ),
            "sha256": binary_hash,
        },
        "ncu": {
            "path": str(ncu) if ncu is not None else "",
            "sha256": ncu_hash,
            "metrics": METRICS,
        },
        "partial_captures": captures,
        "summary_csv": (
            {
                "path": summary_path.name,
                "sha256": sha256_file(summary_path),
            }
            if summary_path is not None and summary_path.is_file()
            else None
        ),
        "energy_usable": False,
        "energy_exclusion_reason": (
            "Nsight Compute kernel replay output is not ATC energy evidence"
        ),
    }
    payload["provenance_payload_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def synthetic_row(
    *,
    launch: int,
    stage: int,
    policy: int,
    metric_values: dict[str, int],
) -> dict[str, str]:
    name = (
        "void unnamed>::whole_softmax_stage_atc_kernel"
        f"<1024, {stage}, {policy}>(const __half *, float *)"
    )
    return {
        "ID": str(launch),
        "Process ID": "99",
        "Context": "1",
        "Kernel Name": name,
        "Grid Size": "(41, 1, 1)",
        "Block Size": "(256, 1, 1)",
        "launch__grid_size": "41.00",
        "launch__block_size": "256.00",
        "launch__registers_per_thread": "32.00",
        "launch__shared_mem_per_block_static": "1024.00",
        "device__attribute_display_name": "NVIDIA GeForce RTX 3090",
        "CC": "8.6",
        **{
            metric: str(metric_values[label])
            for label, metric in METRICS.items()
        },
    }


def synthetic_stage_rows(stage_index: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    stage = dict((index, label) for label, index in STAGES)[stage_index]
    for policy, policy_index in POLICIES:
        expected = expected_metric_deltas(stage, policy)
        control_values = {
            label: (
                3280
                if label == "global_store_warp_instructions"
                else 100000 + policy_index * 1000 + offset * 100
            )
            for offset, label in enumerate(METRICS)
        }
        treatment_values = {
            label: control_values[label] + int(expected[label])
            for label in METRICS
        }
        rows.append(
            synthetic_row(
                launch=policy_index * 2,
                stage=stage_index,
                policy=policy_index,
                metric_values=control_values,
            )
        )
        rows.append(
            synthetic_row(
                launch=policy_index * 2 + 1,
                stage=stage_index,
                policy=policy_index,
                metric_values=treatment_values,
            )
        )
    return rows


def run_self_test() -> int:
    contract = {
        "schema_version": BINARY_CONTRACT,
        "kernel_contract": KERNEL_CONTRACT,
        "treatment_invariant_sink": True,
        "symmetric_opaque_stage_inputs": True,
        "same_kernel_symbol_control_treatment": True,
        "output_equivalence_validation": True,
        "persistent_cuda_context": True,
        "rows_per_block": ROWS_PER_BLOCK,
        "stages": [stage for stage, _ in STAGES],
        "policies": [policy for policy, _ in POLICIES],
    }
    validate_binary_contract(contract)

    rejected = dict(contract)
    rejected["schema_version"] = "softmax_whole_stage_atc_binary_contract_v1"
    try:
        validate_binary_contract(rejected)
    except AuditError:
        pass
    else:
        raise AssertionError("v1 binary contract was not rejected")

    for stage, stage_index in STAGES:
        launches, pairs = validate_stage_rows(
            stage=stage,
            stage_index=stage_index,
            rows=synthetic_stage_rows(stage_index),
        )
        assert len(launches) == EXPECTED_LAUNCHES_PER_STAGE
        assert len(pairs) == len(POLICIES)
        assert all(pair["status"] == "pass" for pair in pairs)

    bad_store = synthetic_stage_rows(0)
    bad_store[1][METRICS["global_store_warp_instructions"]] = "3281"
    _, bad_store_pairs = validate_stage_rows(
        stage="exp", stage_index=0, rows=bad_store
    )
    assert bad_store_pairs[0]["status"] == "fail"
    assert "global_store_equal" in bad_store_pairs[0]["failure_reasons"]

    missing_reciprocal = synthetic_stage_rows(2)
    control_fp32 = int(
        missing_reciprocal[0][METRICS["fp32_thread_instructions"]]
    )
    fmul_delta = int(
        expected_metric_deltas("normalization", "fp32")[
            "fmul_thread_instructions"
        ]
    )
    missing_reciprocal[1][METRICS["fp32_thread_instructions"]] = str(
        control_fp32 + fmul_delta
    )
    _, missing_reciprocal_pairs = validate_stage_rows(
        stage="normalization", stage_index=2, rows=missing_reciprocal
    )
    assert missing_reciprocal_pairs[0]["status"] == "fail"
    assert (
        "positive_normalization_reciprocal_thread_instructions"
        in missing_reciprocal_pairs[0]["failure_reasons"]
    )

    no_reduction_math = synthetic_stage_rows(1)
    no_reduction_math[1][METRICS["fadd_thread_instructions"]] = (
        no_reduction_math[0][METRICS["fadd_thread_instructions"]]
    )
    no_reduction_math[1][METRICS["hadd_thread_instructions"]] = (
        no_reduction_math[0][METRICS["hadd_thread_instructions"]]
    )
    _, no_math_pairs = validate_stage_rows(
        stage="reduction", stage_index=1, rows=no_reduction_math
    )
    assert no_math_pairs[0]["status"] == "fail"
    assert (
        "selected_math_instructions_increase"
        in no_math_pairs[0]["failure_reasons"]
    )

    swapped = synthetic_stage_rows(0)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    try:
        validate_stage_rows(stage="exp", stage_index=0, rows=swapped)
    except AuditError:
        pass
    else:
        raise AssertionError("swapped control/treatment launch order was accepted")

    try:
        reject_known_aborted_binary(
            KNOWN_ABORTED_BINARY, KNOWN_ABORTED_BINARY_SHA256
        )
    except AuditError:
        pass
    else:
        raise AssertionError("known aborted binary was not rejected")

    print(
        "self_test=pass "
        "contract_v1_rejected=1 "
        "stage_policy_pairs=9 "
        "negative_gates=4 "
        "known_aborted_binary_rejected=1"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--self-test", action="store_true")
    result.add_argument("--binary", type=Path)
    result.add_argument("--out-dir", type=Path)
    result.add_argument("--ncu", type=Path)
    result.add_argument("--gpu-id", type=int, default=0)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        return run_self_test()
    if args.binary is None or args.out_dir is None:
        raise SystemExit("--binary and --out-dir are required outside --self-test")
    if args.gpu_id < 0:
        raise SystemExit("--gpu-id must be nonnegative")

    out_dir = args.out_dir.expanduser().resolve()
    if out_dir.exists():
        if not out_dir.is_dir():
            raise SystemExit(f"--out-dir is not a directory: {out_dir}")
        if any(out_dir.iterdir()):
            raise SystemExit(f"refusing non-empty output directory: {out_dir}")
    else:
        out_dir.mkdir(parents=True)

    output_json = out_dir / "audit.json"
    summary_path = out_dir / "audit.csv"
    describe_path = out_dir / "binary_describe.json"
    binary: Path | None = None
    ncu: Path | None = None
    binary_hash = ""
    ncu_hash = ""
    artifacts: list[CaptureArtifact] = []

    try:
        binary = args.binary.expanduser().resolve()
        require(
            binary.is_file() and os.access(binary, os.X_OK),
            f"binary is missing or not executable: {binary}",
        )
        binary_hash = sha256_file(binary)
        reject_known_aborted_binary(binary, binary_hash)
        binary_contract = inspect_binary(binary, describe_path)
        require(
            sha256_file(binary) == binary_hash,
            "binary_changed_during_describe",
        )

        ncu = executable_path(args.ncu)
        ncu_hash = sha256_file(ncu)
        version = ncu_version(ncu)

        all_launches: list[dict[str, Any]] = []
        all_pairs: list[dict[str, Any]] = []
        for stage, stage_index in STAGES:
            artifact = run_stage_capture(
                ncu=ncu,
                binary=binary,
                out_dir=out_dir,
                gpu_id=args.gpu_id,
                stage=stage,
            )
            artifacts.append(artifact)
            require(
                sha256_file(binary) == binary_hash,
                f"binary_changed_during_capture: stage={stage}",
            )
            require(
                sha256_file(ncu) == ncu_hash,
                f"ncu_changed_during_capture: stage={stage}",
            )
            launch_records, pair_records = validate_stage_rows(
                stage=stage,
                stage_index=stage_index,
                rows=read_ncu_csv(artifact.csv_path),
            )
            all_launches.extend(launch_records)
            all_pairs.extend(pair_records)

        require(len(artifacts) == len(STAGES), "incomplete stage captures")
        require(len(all_launches) == 18, "expected 18 total target launches")
        require(len(all_pairs) == 9, "expected nine control/treatment pairs")

        captures = {
            artifact.stage: artifact_provenance(artifact)
            for artifact in artifacts
        }
        rows = summary_csv_rows(
            all_pairs,
            binary_hash=binary_hash,
            capture_provenance=captures,
        )
        atomic_csv(summary_path, rows)
        payload = successful_payload(
            binary=binary,
            binary_hash=binary_hash,
            binary_contract=binary_contract,
            describe_path=describe_path,
            ncu=ncu,
            ncu_hash=ncu_hash,
            version=version,
            artifacts=artifacts,
            launch_records=all_launches,
            pair_records=all_pairs,
            summary_path=summary_path,
        )
        atomic_json(output_json, payload)
        verdict = payload["status"] == "pass"
        print(f"audit_json={output_json}")
        print(f"audit_csv={summary_path}")
        print(f"binary_sha256={binary_hash}")
        print(f"ncu_sha256={ncu_hash}")
        print(f"launch_count={len(all_launches)}")
        print(f"pair_count={len(all_pairs)}")
        print("energy_usable=false")
        print(f"overall={'pass' if verdict else 'fail'}")
        return 0 if verdict else 1
    except Exception as error:
        reason = str(error)
        try:
            failure_summary_csv(summary_path, reason, binary_hash)
            payload = failure_payload(
                reason=reason,
                binary=binary,
                binary_hash=binary_hash,
                ncu=ncu,
                ncu_hash=ncu_hash,
                artifacts=artifacts,
                summary_path=summary_path,
            )
            atomic_json(output_json, payload)
            print(f"audit_json={output_json}")
            print(f"audit_csv={summary_path}")
        except Exception as write_error:
            print(
                f"failed to write failure evidence: {write_error}",
                file=sys.stderr,
            )
        print(f"overall=fail\nfailure={reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
