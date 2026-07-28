#!/usr/bin/env python3
"""Acquire the fixed RTX 3090 whole-Softmax stage ATC experiment.

This is a new acquisition path.  It deliberately does not call or modify the
historical EX2 Operand-rate runners.

The fixed design is:

* one coordinate: RTX 3090, S=1024, grid=41 (q50), 256 threads/CTA,
  two rows/CTA;
* stages: ``exp``, ``reduction``, and ``normalization``;
* policies: ``fp32``, ``fp16_scalar``, and ``fp16x2``;
* three fresh CUDA processes/contexts for every stage;
* policy orders ABC, BCA, and CAB across those three sessions; and
* within every stage/policy cell, C-T-C followed by T-C-T.

One binary invocation owns one complete stage/session.  It must keep one CUDA
context alive while it executes all 18 measured roles (three policies times
six roles).  A runner that launches one process per role would not satisfy the
design.

Required binary batch interface::

    a100_fp16_softmax_whole_stage_atc
      --stage exp
      --policy-schedule fp32,fp16_scalar,fp16x2
      --calibration-policy-schedule fp32,fp16_scalar,fp16x2
      --bracket-schedule ctc,tct
      --session-order ABC
      --softmax-cols 1024 --grid-blocks 41
      --threads-per-block 256 --rows-per-block 2 --seconds 13
      --preheat-seconds 5 --preheat-mode common_fp32_whole_softmax_v1
      --idle-seconds 1
      --logit-scale 4.0 --seed 5573589319906701683
      --energy-trace-sample-ms 250 --energy-trace-min-updates 16
      --session-id ...
      --schema-version softmax_whole_stage_atc_raw_v1
      --trace-schema-version softmax_whole_stage_atc_trace_v1
      --experiment-kind softmax_whole_stage_operand_rate_atc
      --protocol-revision softmax_whole_stage_operand_rate_atc_v2
      --output ... --energy-trace-output ...
      --binary-sha256 ...

``--describe`` must print a JSON contract.  The runner checks that the binary
advertises persistent arbitrary policy schedules, the exact raw/trace schema
versions, C-T-C plus T-C-T, two rows/CTA, common preheat, output equivalence,
same-symbol control/treatment roles, and NVML total-energy tracing.

The primary analyzer is expected to form a treatment-minus-interpolated-control
power contrast and divide by the treatment logical-output rate.  Idle telemetry
is collected only as a diagnostic and must not enter that ATC numerator.

Before the one common preheat, the binary must calibrate the treatment variant
separately for every stage/policy cell.  It then freezes that cell's calibrated
ITER for all six C/T roles.  A single global ITER is intentionally prohibited:
the three stages and policies have materially different runtimes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TARGET_BINARY = "a100_fp16_softmax_whole_stage_atc"

MANIFEST_SCHEMA = "softmax_whole_stage_atc_manifest_v1"
BINARY_CONTRACT_SCHEMA = "softmax_whole_stage_atc_binary_contract_v2"
NCU_AUDIT_SCHEMA = "softmax_whole_stage_atc_ncu_audit_v1"
RAW_SCHEMA = "softmax_whole_stage_atc_raw_v1"
TRACE_SCHEMA = "softmax_whole_stage_atc_trace_v1"
EXPERIMENT_KIND = "softmax_whole_stage_operand_rate_atc"
PROTOCOL_REVISION = "softmax_whole_stage_operand_rate_atc_v2"
DESIGN_ID = "rtx3090_s1024_q50_stage_atc_3x3x3_v2"
KERNEL_CONTRACT = "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"

PROFILE = "rtx3090"
GPU_ID = 0
RUNTIME_SM_COUNT = 82
SOFTMAX_COLS = 1024
GRID_BLOCKS = 41
SM_COVERAGE = 0.50
THREADS_PER_BLOCK = 256
ROWS_PER_BLOCK = 2
ROLE_TARGET_SECONDS = 13.0
INPUT_LOGIT_SCALE = 4.0
INPUT_SEED = 5573589319906701683

PREHEAT_SECONDS = 5.0
PREHEAT_ACTUAL_GATE = (3.75, 6.25)
PREHEAT_MODE = "common_fp32_whole_softmax_v1"
IDLE_SECONDS = 1.0
TRACE_SAMPLE_MS = 250.0
TRACE_MIN_UPDATES = 16
TRACE_MEDIAN_INTERVAL_GATE_S = (0.125, 0.500)

STAGES = ("exp", "reduction", "normalization")
POLICIES = ("fp32", "fp16_scalar", "fp16x2")
POLICY_ORDERS: dict[str, tuple[str, ...]] = {
    "ABC": POLICIES,
    "BCA": (POLICIES[1], POLICIES[2], POLICIES[0]),
    "CAB": (POLICIES[2], POLICIES[0], POLICIES[1]),
}
SESSION_ORDERS = tuple(POLICY_ORDERS)
STAGE_ORDERS: dict[str, tuple[str, ...]] = {
    "ABC": STAGES,
    "BCA": (STAGES[1], STAGES[2], STAGES[0]),
    "CAB": (STAGES[2], STAGES[0], STAGES[1]),
}

BRACKETS: tuple[dict[str, Any], ...] = (
    {
        "bracket_index": 0,
        "orientation": "forward",
        "bracket_schedule": "C-T-C",
        "roles": (
            ("control", "control_before"),
            ("treatment", "treatment_middle"),
            ("control", "control_after"),
        ),
    },
    {
        "bracket_index": 1,
        "orientation": "reverse",
        "bracket_schedule": "T-C-T",
        "roles": (
            ("treatment", "treatment_before"),
            ("control", "control_middle"),
            ("treatment", "treatment_after"),
        ),
    },
)

RAW_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_kind",
        "protocol_revision",
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
        "run_id",
        "gpu_id",
        "target_profile",
        "cuda_pci_bus_id",
        "cuda_binary_arch",
        "gpu_name",
        "softmax_cols",
        "grid_blocks",
        "threads_per_block",
        "rows_per_block",
        "input_dtype",
        "output_dtype",
        "input_logit_scale",
        "input_seed",
        "block_shared_bytes",
        "registers_per_thread",
        "runtime_sm_count",
        "occupancy_max_blocks_per_sm",
        "static_single_wave_capacity_blocks",
        "static_single_wave_capacity_gate_pass",
        "smid_total_blocks",
        "smid_unique",
        "smid_max_blocks_on_sm",
        "smid_histogram_ok",
        "iters",
        "logical_output_elements",
        "calibration_mode",
        "calibration_reference_variant",
        "calibration_elapsed_s",
        "calibration_iters",
        "calibration_before_preheat",
        "role_target_seconds",
        "kernel_symbol",
        "same_kernel_symbol_status",
        "numerical_check_id",
        "control_treatment_output_bit_identical",
        "output_equivalence_status",
        "output_digest",
        "sink_digest",
        "preheat_requested_s",
        "preheat_actual_s",
        "idle_elapsed_s",
        "idle_delta_E_J",
        "idle_power_W",
        "elapsed_s",
        "measurement_start_epoch_ms",
        "measurement_end_epoch_ms",
        "E_before_mJ",
        "E_after_mJ",
        "endpoint_delta_E_J",
        "delta_E_J",
        "energy_trace_sample_count",
        "energy_trace_update_count",
        "energy_trace_fit_point_count",
        "energy_trace_power_W",
        "energy_trace_r2",
        "energy_trace_status",
        "clock_sm_before_mhz",
        "clock_sm_after_mhz",
        "clock_mem_before_mhz",
        "clock_mem_after_mhz",
        "temp_before_C",
        "temp_after_C",
        "energy_source",
        "energy_integration_method",
        "binary_sha256",
    }
)

TRACE_REQUIRED_FIELDS = frozenset(
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_provenance() -> dict[str, Any]:
    def run_git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
            )
        return completed.stdout.strip()

    status = run_git("status", "--porcelain=v1", "--untracked-files=all")
    return {
        "commit": run_git("rev-parse", "HEAD"),
        "branch": run_git("rev-parse", "--abbrev-ref", "HEAD"),
        "describe": run_git("describe", "--always", "--dirty", "--tags"),
        "worktree_dirty": bool(status),
        "status_porcelain": status.splitlines(),
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
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


def freeze(source: Path, destination: Path) -> dict[str, str]:
    if not source.is_file():
        raise RuntimeError(f"required file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if os.access(source, os.X_OK):
        destination.chmod(destination.stat().st_mode | 0o111)
    return {"path": repo_path(destination), "sha256": sha256_file(destination)}


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as error:
        raise RuntimeError(f"cannot read CSV {path}: {error}") from error


def truth(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "pass"}


def number(row: dict[str, str], field: str, label: str) -> float:
    try:
        value = float(row.get(field, ""))
    except ValueError as error:
        raise RuntimeError(f"{label}: {field} is not numeric") from error
    if not math.isfinite(value):
        raise RuntimeError(f"{label}: {field} is not finite")
    return value


def integer(row: dict[str, str], field: str, label: str) -> int:
    value = number(row, field, label)
    result = int(value)
    if value != result:
        raise RuntimeError(f"{label}: {field} is not integral")
    return result


def require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise RuntimeError(f"{label}: observed {observed!r}, expected {expected!r}")


def expected_logical_output_elements(iters: int) -> int:
    if iters <= 0:
        raise ValueError("iters must be positive")
    return GRID_BLOCKS * iters * ROWS_PER_BLOCK * SOFTMAX_COLS


def build_execution_schedule(
    *, stage: str, session_id: str, policy_schedule: tuple[str, ...]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    for policy_position, policy in enumerate(policy_schedule):
        cell_id = f"{session_id}_{stage}_{policy}"
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
        for bracket in BRACKETS:
            bracket_index = int(bracket["bracket_index"])
            for role_index, (variant, role_position) in enumerate(bracket["roles"]):
                role_id = (
                    f"{cell_id}_b{bracket_index}_r{role_index}_{variant}"
                )
                roles.append(
                    {
                        "session_role_index": len(roles),
                        "stage": stage,
                        "policy_position": policy_position,
                        "policy": policy,
                        "cell_id": cell_id,
                        "bracket_index": bracket_index,
                        "orientation": bracket["orientation"],
                        "role_index": role_index,
                        "role_id": role_id,
                        "role_position": role_position,
                        "role": variant,
                        "variant": variant,
                    }
                )
    return cells, roles


def build_command(
    *,
    binary: Path,
    binary_sha256: str,
    stage: str,
    policy_schedule: tuple[str, ...],
    session_order: str,
    session_index: int,
    session_id: str,
    raw_csv: Path,
    trace_csv: Path,
) -> list[str]:
    return [
        str(binary),
        "--gpu-id", str(GPU_ID),
        "--target-profile", PROFILE,
        "--stage", stage,
        "--policy-schedule", ",".join(policy_schedule),
        "--calibration-policy-schedule", ",".join(POLICIES),
        "--bracket-schedule", "ctc,tct",
        "--session-order", session_order,
        "--session-index", str(session_index),
        "--softmax-cols", str(SOFTMAX_COLS),
        "--grid-blocks", str(GRID_BLOCKS),
        "--threads-per-block", str(THREADS_PER_BLOCK),
        "--rows-per-block", str(ROWS_PER_BLOCK),
        "--seconds", f"{ROLE_TARGET_SECONDS:.1f}",
        "--preheat-seconds", f"{PREHEAT_SECONDS:.1f}",
        "--preheat-mode", PREHEAT_MODE,
        "--idle-seconds", f"{IDLE_SECONDS:.1f}",
        "--logit-scale", f"{INPUT_LOGIT_SCALE:.1f}",
        "--seed", str(INPUT_SEED),
        "--energy-trace-sample-ms", f"{TRACE_SAMPLE_MS:.1f}",
        "--energy-trace-min-updates", str(TRACE_MIN_UPDATES),
        "--session-id", session_id,
        "--schema-version", RAW_SCHEMA,
        "--trace-schema-version", TRACE_SCHEMA,
        "--experiment-kind", EXPERIMENT_KIND,
        "--protocol-revision", PROTOCOL_REVISION,
        "--output", str(raw_csv),
        "--energy-trace-output", str(trace_csv),
        "--binary-sha256", binary_sha256,
    ]


def build_sessions(
    *, run_root: Path, tag: str, binary: Path, binary_sha256: str
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for session_index, session_order in enumerate(SESSION_ORDERS, start=1):
        policy_schedule = POLICY_ORDERS[session_order]
        for stage in STAGE_ORDERS[session_order]:
            prefix = f"{stage}_session{session_index:02d}_{session_order}"
            session_id = f"{tag}_{prefix}"
            raw_csv = run_root / f"{prefix}_raw.csv"
            trace_csv = run_root / f"{prefix}_energy_trace.csv"
            cells, execution_schedule = build_execution_schedule(
                stage=stage,
                session_id=session_id,
                policy_schedule=policy_schedule,
            )
            command = build_command(
                binary=binary,
                binary_sha256=binary_sha256,
                stage=stage,
                policy_schedule=policy_schedule,
                session_order=session_order,
                session_index=session_index,
                session_id=session_id,
                raw_csv=raw_csv,
                trace_csv=trace_csv,
            )
            sessions.append(
                {
                    "global_session_index": len(sessions) + 1,
                    "session_id": session_id,
                    "session_index": session_index,
                    "session_order": session_order,
                    "stage": stage,
                    "fresh_cuda_process": True,
                    "persistent_cuda_context": True,
                    "role_target_seconds": ROLE_TARGET_SECONDS,
                    "calibration": {
                        "mode": "per_stage_policy_treatment_before_common_preheat",
                        "reference_variant": "treatment",
                        "scope": "one calibrated ITER frozen across all six roles in each cell",
                    },
                    "policy_schedule": list(policy_schedule),
                    "expected_cells": 3,
                    "expected_roles": 18,
                    "cells": cells,
                    "execution_schedule": execution_schedule,
                    "raw_csv": repo_path(raw_csv),
                    "energy_trace_csv": repo_path(trace_csv),
                    "command": command,
                    "command_shell": shlex.join(command),
                    "status": "planned",
                    "returncode": None,
                    "started_at": None,
                    "finished_at": None,
                }
            )
    return sessions


def inspect_binary_contract(binary: Path) -> dict[str, Any]:
    if not binary.is_file():
        raise RuntimeError(f"stage ATC binary is missing: {binary}")
    if not os.access(binary, os.X_OK):
        raise RuntimeError(f"stage ATC binary is not executable: {binary}")
    completed = subprocess.run(
        [str(binary), "--describe"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{binary} --describe failed with return code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    try:
        description = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("binary --describe must emit one JSON object") from error
    if not isinstance(description, dict):
        raise RuntimeError("binary --describe did not emit a JSON object")
    expected = {
        "schema_version": BINARY_CONTRACT_SCHEMA,
        "raw_schema_version": RAW_SCHEMA,
        "trace_schema_version": TRACE_SCHEMA,
        "persistent_policy_schedule": True,
        "persistent_cuda_context": True,
        "arbitrary_policy_order": True,
        "bracket_schedule": "ctc,tct",
        "rows_per_block": ROWS_PER_BLOCK,
        "per_cell_treatment_calibration": True,
        "calibration_before_preheat": True,
        "calibration_policy_order": list(POLICIES),
        "common_preheat_supported": True,
        "same_kernel_symbol_control_treatment": True,
        "output_equivalence_validation": True,
        "treatment_invariant_sink": True,
        "symmetric_opaque_stage_inputs": True,
        "nvml_total_energy_trace": True,
    }
    for field, value in expected.items():
        require_equal(description.get(field), value, f"binary contract {field}")
    require_equal(tuple(description.get("stages", [])), STAGES, "binary contract stages")
    require_equal(
        tuple(description.get("policies", [])), POLICIES, "binary contract policies"
    )
    require_equal(
        description.get("kernel_contract"),
        KERNEL_CONTRACT,
        "binary contract kernel_contract",
    )
    return description


def validate_raw_and_trace(
    *,
    session: dict[str, Any],
    raw_path: Path,
    trace_path: Path,
    binary_sha256: str,
) -> dict[str, Any]:
    raw = read_csv(raw_path)
    trace = read_csv(trace_path)
    if len(raw) != int(session["expected_roles"]):
        raise RuntimeError(
            f"{session['session_id']}: raw row count {len(raw)} != "
            f"{session['expected_roles']}"
        )
    if not trace:
        raise RuntimeError(f"{session['session_id']}: empty energy trace")
    if not RAW_REQUIRED_FIELDS.issubset(raw[0]):
        missing = sorted(RAW_REQUIRED_FIELDS - set(raw[0]))
        raise RuntimeError(f"{session['session_id']}: raw fields missing: {missing}")
    if not TRACE_REQUIRED_FIELDS.issubset(trace[0]):
        missing = sorted(TRACE_REQUIRED_FIELDS - set(trace[0]))
        raise RuntimeError(f"{session['session_id']}: trace fields missing: {missing}")

    expected_schedule = session.get("execution_schedule")
    if not isinstance(expected_schedule, list):
        raise RuntimeError(f"{session['session_id']}: manifest schedule is invalid")
    expected_by_role = {str(item["role_id"]): item for item in expected_schedule}
    if len(expected_by_role) != len(expected_schedule):
        raise RuntimeError(f"{session['session_id']}: duplicate expected role IDs")
    observed_role_ids = [row.get("role_id", "") for row in raw]
    require_equal(
        observed_role_ids,
        [str(item["role_id"]) for item in expected_schedule],
        f"{session['session_id']}: raw execution order",
    )
    if any(not row.get("run_id", "") for row in raw) or len(
        set(row.get("run_id", "") for row in raw)
    ) != len(raw):
        raise RuntimeError(f"{session['session_id']}: run_id is empty or not unique")

    raw_by_role: dict[str, dict[str, str]] = {}
    kernel_symbols: dict[str, set[str]] = {}
    output_digests: dict[str, set[str]] = {}
    sink_digests: dict[str, set[str]] = {}
    resource_envelopes: dict[str, set[tuple[str, str, int, int]]] = {}
    cell_iters: dict[str, set[int]] = {}
    preheat_values: set[float] = set()
    cuda_pci_bus_ids: set[str] = set()
    gpu_names: set[str] = set()
    for row in raw:
        role_id = row["role_id"]
        label = f"{session['session_id']}:{role_id}"
        expected = expected_by_role.get(role_id)
        if expected is None:
            raise RuntimeError(f"{label}: role not declared by manifest")
        raw_by_role[role_id] = row
        for field in (
            "stage",
            "policy",
            "cell_id",
            "orientation",
            "role_position",
            "role",
            "variant",
        ):
            require_equal(row.get(field), str(expected[field]), f"{label}:{field}")
        for field in (
            "session_role_index",
            "policy_position",
            "bracket_index",
            "role_index",
        ):
            require_equal(integer(row, field, label), int(expected[field]), f"{label}:{field}")
        require_equal(row["schema_version"], RAW_SCHEMA, f"{label}:schema")
        require_equal(row["experiment_kind"], EXPERIMENT_KIND, f"{label}:kind")
        require_equal(
            row["protocol_revision"], PROTOCOL_REVISION, f"{label}:protocol"
        )
        require_equal(row["session_id"], session["session_id"], f"{label}:session")
        require_equal(
            integer(row, "session_index", label),
            int(session["session_index"]),
            f"{label}:session_index",
        )
        require_equal(row["session_order"], session["session_order"], f"{label}:order")
        require_equal(row["target_profile"], PROFILE, f"{label}:profile")
        require_equal(integer(row, "gpu_id", label), GPU_ID, f"{label}:gpu")
        require_equal(
            integer(row, "cuda_binary_arch", label), 86, f"{label}:native cubin"
        )
        cuda_pci_bus_id = row["cuda_pci_bus_id"].strip()
        gpu_name = row["gpu_name"].strip()
        if not cuda_pci_bus_id:
            raise RuntimeError(f"{label}: CUDA PCI bus ID is empty")
        if "RTX 3090" not in gpu_name:
            raise RuntimeError(f"{label}: unexpected GPU name {gpu_name!r}")
        cuda_pci_bus_ids.add(cuda_pci_bus_id)
        gpu_names.add(gpu_name)
        require_equal(
            integer(row, "softmax_cols", label), SOFTMAX_COLS, f"{label}:S"
        )
        require_equal(
            integer(row, "grid_blocks", label), GRID_BLOCKS, f"{label}:grid"
        )
        require_equal(
            integer(row, "threads_per_block", label),
            THREADS_PER_BLOCK,
            f"{label}:threads",
        )
        require_equal(
            integer(row, "rows_per_block", label),
            ROWS_PER_BLOCK,
            f"{label}:rows",
        )
        require_equal(
            number(row, "input_logit_scale", label),
            INPUT_LOGIT_SCALE,
            f"{label}:input logit scale",
        )
        require_equal(
            integer(row, "input_seed", label),
            INPUT_SEED,
            f"{label}:input seed",
        )
        input_dtype = row["input_dtype"].strip()
        output_dtype = row["output_dtype"].strip()
        if not input_dtype or not output_dtype:
            raise RuntimeError(f"{label}: input/output dtype is empty")
        block_shared_bytes = integer(row, "block_shared_bytes", label)
        registers_per_thread = integer(row, "registers_per_thread", label)
        if block_shared_bytes < 0:
            raise RuntimeError(f"{label}: shared-memory size is negative")
        if registers_per_thread <= 0:
            raise RuntimeError(f"{label}: register count is not positive")
        resource_envelopes.setdefault(row["cell_id"], set()).add(
            (
                input_dtype,
                output_dtype,
                block_shared_bytes,
                registers_per_thread,
            )
        )
        runtime_sm_count = integer(row, "runtime_sm_count", label)
        require_equal(runtime_sm_count, RUNTIME_SM_COUNT, f"{label}:runtime SM count")
        occupancy_max_blocks_per_sm = integer(
            row, "occupancy_max_blocks_per_sm", label
        )
        if occupancy_max_blocks_per_sm <= 0:
            raise RuntimeError(f"{label}: occupancy capacity is not positive")
        static_single_wave_capacity_blocks = integer(
            row, "static_single_wave_capacity_blocks", label
        )
        require_equal(
            static_single_wave_capacity_blocks,
            runtime_sm_count * occupancy_max_blocks_per_sm,
            f"{label}:single-wave capacity",
        )
        if not truth(row["static_single_wave_capacity_gate_pass"]):
            raise RuntimeError(f"{label}: static single-wave capacity gate failed")
        if GRID_BLOCKS > static_single_wave_capacity_blocks:
            raise RuntimeError(f"{label}: grid exceeds static single-wave capacity")
        require_equal(
            integer(row, "smid_total_blocks", label),
            GRID_BLOCKS,
            f"{label}:observed SMID blocks",
        )
        require_equal(
            integer(row, "smid_unique", label),
            GRID_BLOCKS,
            f"{label}:unique SMIDs",
        )
        require_equal(
            integer(row, "smid_max_blocks_on_sm", label),
            1,
            f"{label}:maximum blocks assigned to one SM",
        )
        if not truth(row["smid_histogram_ok"]):
            raise RuntimeError(f"{label}: SMID histogram gate failed")
        observed_iters = integer(row, "iters", label)
        if observed_iters <= 0:
            raise RuntimeError(f"{label}: calibrated iters is not positive")
        cell_iters.setdefault(row["cell_id"], set()).add(observed_iters)
        require_equal(
            integer(row, "logical_output_elements", label),
            expected_logical_output_elements(observed_iters),
            f"{label}:denominator",
        )
        require_equal(
            row["calibration_mode"],
            "per_stage_policy_treatment_before_common_preheat",
            f"{label}:calibration mode",
        )
        require_equal(
            row["calibration_reference_variant"],
            "treatment",
            f"{label}:calibration reference",
        )
        calibration_elapsed = number(row, "calibration_elapsed_s", label)
        if not (
            ROLE_TARGET_SECONDS * 0.90
            <= calibration_elapsed
            <= ROLE_TARGET_SECONDS * 1.30
        ):
            raise RuntimeError(
                f"{label}: calibration elapsed time is outside "
                "the 0.90x-1.30x target gate"
            )
        require_equal(
            integer(row, "calibration_iters", label),
            observed_iters,
            f"{label}:calibrated iters",
        )
        if not truth(row["calibration_before_preheat"]):
            raise RuntimeError(f"{label}: calibration did not precede preheat")
        require_equal(
            number(row, "role_target_seconds", label),
            ROLE_TARGET_SECONDS,
            f"{label}:role target",
        )
        require_equal(row["binary_sha256"], binary_sha256, f"{label}:binary hash")
        if not row["kernel_symbol"]:
            raise RuntimeError(f"{label}: empty kernel_symbol")
        if row["same_kernel_symbol_status"] != "pass":
            raise RuntimeError(f"{label}: same-kernel-symbol gate failed")
        if not row["numerical_check_id"]:
            raise RuntimeError(f"{label}: numerical_check_id is empty")
        if not truth(row["control_treatment_output_bit_identical"]):
            raise RuntimeError(f"{label}: control/treatment output differs")
        if row["output_equivalence_status"] != "pass":
            raise RuntimeError(f"{label}: output equivalence gate failed")
        if not row["output_digest"]:
            raise RuntimeError(f"{label}: output_digest is empty")
        if not row["sink_digest"]:
            raise RuntimeError(f"{label}: sink_digest is empty")
        require_equal(
            number(row, "preheat_requested_s", label),
            PREHEAT_SECONDS,
            f"{label}:preheat request",
        )
        actual_preheat = number(row, "preheat_actual_s", label)
        if not PREHEAT_ACTUAL_GATE[0] <= actual_preheat <= PREHEAT_ACTUAL_GATE[1]:
            raise RuntimeError(f"{label}: actual preheat is outside the 5 s gate")
        preheat_values.add(actual_preheat)
        if number(row, "idle_elapsed_s", label) <= 0.0:
            raise RuntimeError(f"{label}: idle diagnostic duration is invalid")
        if number(row, "idle_power_W", label) <= 0.0:
            raise RuntimeError(f"{label}: idle diagnostic power is invalid")
        if number(row, "elapsed_s", label) <= 0.0:
            raise RuntimeError(f"{label}: elapsed time is invalid")
        if integer(row, "energy_trace_fit_point_count", label) < TRACE_MIN_UPDATES:
            raise RuntimeError(f"{label}: too few qualified trace fit points")
        if row["energy_trace_status"] != "pass":
            raise RuntimeError(f"{label}: energy trace gate failed")
        if row["energy_source"] != "nvml_total_energy":
            raise RuntimeError(f"{label}: non-NVML energy source")
        if "theil" not in row["energy_integration_method"].lower():
            raise RuntimeError(f"{label}: trace integration is not Theil-Sen")
        kernel_symbols.setdefault(row["cell_id"], set()).add(row["kernel_symbol"])
        output_digests.setdefault(row["cell_id"], set()).add(row["output_digest"])
        sink_digests.setdefault(row["cell_id"], set()).add(
            row["sink_digest"]
        )

    if len(preheat_values) != 1:
        raise RuntimeError(
            f"{session['session_id']}: preheat was not session-once/common"
        )
    if len(cuda_pci_bus_ids) != 1 or len(gpu_names) != 1:
        raise RuntimeError(f"{session['session_id']}: GPU identity changed within session")
    for cell_id, symbols in kernel_symbols.items():
        if len(symbols) != 1:
            raise RuntimeError(f"{cell_id}: control/treatment kernel symbols differ")
    for cell_id, digests in output_digests.items():
        if len(digests) != 1:
            raise RuntimeError(f"{cell_id}: control/treatment output digests differ")
    for cell_id, envelopes in resource_envelopes.items():
        if len(envelopes) != 1:
            raise RuntimeError(f"{cell_id}: control/treatment resource envelope differs")
    for cell_id, digests in sink_digests.items():
        if len(digests) != 1 or "" in digests:
            raise RuntimeError(
                f"{cell_id}: sink must be stable and treatment-invariant; "
                "stage survival is proved by the SASS audit, not a tag-dependent digest"
            )
    for cell_id, observed in cell_iters.items():
        if len(observed) != 1:
            raise RuntimeError(
                f"{cell_id}: control/treatment roles did not freeze one calibrated ITER"
            )

    trace_by_role: dict[str, list[dict[str, str]]] = {}
    for row in trace:
        role_id = row.get("role_id", "")
        label = f"{session['session_id']}:trace:{role_id}"
        if role_id not in expected_by_role:
            raise RuntimeError(f"{label}: role not declared by manifest")
        raw_row = raw_by_role[role_id]
        for field in (
            "session_id",
            "stage",
            "policy",
            "cell_id",
            "role",
            "variant",
            "run_id",
        ):
            require_equal(row.get(field), raw_row.get(field), f"{label}:{field}")
        for field in ("bracket_index", "role_index"):
            require_equal(
                integer(row, field, label),
                integer(raw_row, field, label),
                f"{label}:{field}",
            )
        require_equal(row["schema_version"], TRACE_SCHEMA, f"{label}:schema")
        require_equal(row["experiment_kind"], EXPERIMENT_KIND, f"{label}:kind")
        require_equal(
            row["protocol_revision"], PROTOCOL_REVISION, f"{label}:protocol"
        )
        require_equal(row["binary_sha256"], binary_sha256, f"{label}:binary hash")
        number(row, "query_midpoint_s", label)
        number(row, "relative_to_kernel_start_s", label)
        number(row, "energy_mJ", label)
        trace_by_role.setdefault(role_id, []).append(row)

    require_equal(
        set(trace_by_role), set(expected_by_role), f"{session['session_id']}:trace coverage"
    )
    for role_id, rows in trace_by_role.items():
        rows.sort(key=lambda row: integer(row, "sample_index", role_id))
        sample_indices = [integer(row, "sample_index", role_id) for row in rows]
        require_equal(
            sample_indices,
            list(range(len(rows))),
            f"{session['session_id']}:{role_id}:sample indices",
        )
        energies = [number(row, "energy_mJ", role_id) for row in rows]
        if any(right < left for left, right in zip(energies, energies[1:])):
            raise RuntimeError(
                f"{session['session_id']}:{role_id}: non-monotonic energy counter"
            )
        raw_row = raw_by_role[role_id]
        require_equal(
            integer(raw_row, "energy_trace_sample_count", role_id),
            len(rows),
            f"{session['session_id']}:{role_id}:trace sample count",
        )
        require_equal(
            integer(raw_row, "energy_trace_update_count", role_id),
            sum(truth(row["changed_from_previous"]) for row in rows),
            f"{session['session_id']}:{role_id}:trace update count",
        )
        require_equal(
            integer(raw_row, "energy_trace_fit_point_count", role_id),
            sum(
                truth(row["in_fit_window"])
                and (
                    index == 0
                    or truth(row["changed_from_previous"])
                )
                for index, row in enumerate(rows)
            ),
            f"{session['session_id']}:{role_id}:trace fit-point count",
        )
        midpoints = [number(row, "query_midpoint_s", role_id) for row in rows]
        intervals = [
            right - left for left, right in zip(midpoints, midpoints[1:])
        ]
        if not intervals or any(interval <= 0.0 for interval in intervals):
            raise RuntimeError(
                f"{session['session_id']}:{role_id}: invalid trace sample timing"
            )
        ordered_intervals = sorted(intervals)
        middle = len(ordered_intervals) // 2
        median_interval = (
            ordered_intervals[middle]
            if len(ordered_intervals) % 2
            else (
                ordered_intervals[middle - 1] + ordered_intervals[middle]
            )
            / 2.0
        )
        if not (
            TRACE_MEDIAN_INTERVAL_GATE_S[0]
            <= median_interval
            <= TRACE_MEDIAN_INTERVAL_GATE_S[1]
        ):
            raise RuntimeError(
                f"{session['session_id']}:{role_id}: median trace interval "
                f"{median_interval:.6f} s does not match the 250 ms contract"
            )

    return {
        "raw_rows": len(raw),
        "trace_rows": len(trace),
        "trace_roles": len(trace_by_role),
        "preheat_actual_s": next(iter(preheat_values)),
        "cuda_pci_bus_id": next(iter(cuda_pci_bus_ids)),
        "gpu_name": next(iter(gpu_names)),
        "calibrated_iters_by_cell": {
            cell_id: next(iter(values))
            for cell_id, values in sorted(cell_iters.items())
        },
        "same_kernel_symbol_cells": len(kernel_symbols),
        "output_equivalent_cells": len(output_digests),
    }


def plan_run(args: argparse.Namespace) -> Path:
    binary = (
        Path(args.binary)
        if args.binary
        else Path(args.build_dir) / TARGET_BINARY
    ).resolve()
    if not binary.is_file():
        raise RuntimeError(f"stage ATC binary is missing: {binary}")

    tag = args.session_tag or datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_root = (
        Path(args.output_dir) / f"rtx3090_softmax_whole_stage_atc_{tag}"
    ).resolve()
    if run_root.exists():
        raise RuntimeError(f"run directory already exists: {run_root}")

    frozen_binary_path = run_root / "frozen" / binary.name
    frozen_binary = freeze(binary, frozen_binary_path)
    frozen_runner = freeze(
        Path(__file__).resolve(), run_root / "frozen" / Path(__file__).name
    )
    binary_contract = inspect_binary_contract(frozen_binary_path)
    sessions = build_sessions(
        run_root=run_root,
        tag=tag,
        binary=frozen_binary_path,
        binary_sha256=frozen_binary["sha256"],
    )
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "created_at": timestamp(),
        "status": "planned",
        "experiment_kind": EXPERIMENT_KIND,
        "protocol_revision": PROTOCOL_REVISION,
        "design_id": DESIGN_ID,
        "profile": {
            "name": PROFILE,
            "gpu_id": GPU_ID,
            "runtime_sm_count": RUNTIME_SM_COUNT,
            "compute_capability": "8.6",
            "cuda_arch": "sm_86",
        },
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "requested_sm_coverage": SM_COVERAGE,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
            "role_target_seconds": ROLE_TARGET_SECONDS,
            "iters": "calibrated_per_stage_policy_and_observed_in_raw",
            "logical_output_elements_per_role": (
                "grid_blocks*observed_iters*rows_per_block*softmax_cols"
            ),
        },
        "input_generation": {
            "distribution": "deterministic_symmetric_uniform",
            "logit_scale": INPUT_LOGIT_SCALE,
            "seed": INPUT_SEED,
            "explicit_in_session_command": True,
            "recorded_in_every_raw_role": True,
        },
        "design": {
            "stages": list(STAGES),
            "policies": list(POLICIES),
            "session_orders": list(SESSION_ORDERS),
            "global_stage_orders": {
                order: list(STAGE_ORDERS[order]) for order in SESSION_ORDERS
            },
            "bracket_schedule": ["C-T-C", "T-C-T"],
            "fresh_sessions_per_stage": 3,
            "total_cells": 27,
            "total_process_sessions": 9,
            "measured_roles_per_cell": 6,
            "total_measured_roles": 162,
            "process_scope": (
                "one fresh process/context per stage/session; three policies "
                "and 18 roles remain in that context"
            ),
            "calibration": {
                "mode": "per_stage_policy_treatment_before_common_preheat",
                "reference_variant": "treatment",
                "policy_order": list(POLICIES),
                "target_seconds": ROLE_TARGET_SECONDS,
                "freeze_scope": "one cell ITER reused by its six C/T roles",
                "global_fixed_iters": "prohibited",
            },
            "static_audit_required_for_headline": True,
            "ncu_audit_required_for_headline": True,
            "observer_sink": (
                "same materialization/store/data bits in control and treatment; "
                "added-stage survival is a SASS dataflow gate"
            ),
        },
        "placement_contract": {
            "runtime_sm_count": RUNTIME_SM_COUNT,
            "underfilled_grid": True,
            "capacity_formula": (
                "runtime_sm_count*occupancy_max_blocks_per_sm"
            ),
            "capacity_gate": (
                "grid_blocks<=static_single_wave_capacity_blocks"
            ),
            "smid_total_blocks": GRID_BLOCKS,
            "smid_unique": GRID_BLOCKS,
            "smid_max_blocks_on_sm": 1,
            "smid_histogram_ok": True,
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
        "thermal_contract": {
            "preheat_requested_s": PREHEAT_SECONDS,
            "preheat_actual_gate_s": list(PREHEAT_ACTUAL_GATE),
            "preheat_mode": PREHEAT_MODE,
            "preheat_scope": "once_per_stage_session_before_any_measured_role",
            "temperature": "recorded context; not a rejection gate",
        },
        "energy_contract": {
            "source": "nvml_total_energy",
            "trace_sample_ms": TRACE_SAMPLE_MS,
            "trace_min_updates": TRACE_MIN_UPDATES,
            "integration": "guarded_interior_theil_sen",
            "idle_seconds": IDLE_SECONDS,
            "idle_is_diagnostic_only": True,
        },
        "schemas": {
            "binary_contract": BINARY_CONTRACT_SCHEMA,
            "ncu_audit": NCU_AUDIT_SCHEMA,
            "raw": RAW_SCHEMA,
            "trace": TRACE_SCHEMA,
            "raw_required_fields": sorted(RAW_REQUIRED_FIELDS),
            "trace_required_fields": sorted(TRACE_REQUIRED_FIELDS),
        },
        "binary": {
            **frozen_binary,
            "contract": binary_contract,
        },
        "runner": frozen_runner,
        "source_provenance": {
            "repo_root": str(ROOT.resolve()),
            "python": sys.version,
            "runner_argv": sys.argv,
            "working_directory": str(Path.cwd().resolve()),
            "git": git_provenance(),
        },
        "sessions": sessions,
    }
    atomic_json(run_root / "manifest.json", manifest)
    print(f"planned_run_dir={run_root}")
    print("planned_process_sessions=9 planned_cells=27 planned_roles=162")
    for session in sessions:
        print(
            f"[{session['global_session_index']:02d}] "
            f"{session['stage']} session{session['session_index']:02d} "
            f"{session['session_order']}: {session['command_shell']}"
        )
    return run_root


def load_manifest(run_root: Path) -> dict[str, Any]:
    path = run_root / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read manifest: {error}") from error
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise RuntimeError("manifest schema does not match the stage ATC runner")
    return payload


def execute_run(run_root: Path) -> None:
    manifest_path = run_root / "manifest.json"
    manifest = load_manifest(run_root)
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 9:
        raise RuntimeError("manifest must contain exactly nine stage/session processes")
    if any(session.get("status") != "planned" for session in sessions):
        raise RuntimeError(
            "execution requires a wholly planned manifest; selective retry/resume is prohibited"
        )
    binary_meta = manifest.get("binary")
    runner_meta = manifest.get("runner")
    coordinate = manifest.get("coordinate")
    if not all(isinstance(item, dict) for item in (binary_meta, runner_meta, coordinate)):
        raise RuntimeError("manifest provenance/configuration is malformed")
    binary_path = resolve_path(str(binary_meta["path"]))
    runner_path = resolve_path(str(runner_meta["path"]))
    require_equal(
        sha256_file(binary_path), binary_meta["sha256"], "frozen binary hash"
    )
    require_equal(
        sha256_file(runner_path), runner_meta["sha256"], "frozen runner hash"
    )
    for session in sessions:
        command = session.get("command")
        if not isinstance(command, list) or not all(
            isinstance(item, str) for item in command
        ):
            raise RuntimeError("manifest session command is invalid")
        session["started_at"] = timestamp()
        session["status"] = "running"
        manifest["status"] = "running"
        atomic_json(manifest_path, manifest)
        print(
            f"running_process_session={session['global_session_index']} "
            f"stage={session['stage']} order={session['session_order']}",
            flush=True,
        )
        try:
            completed = subprocess.run(command, cwd=ROOT, check=True)
        except subprocess.CalledProcessError as error:
            session["returncode"] = error.returncode
            session["finished_at"] = timestamp()
            session["status"] = "failed"
            manifest["status"] = "failed"
            manifest["failure"] = (
                f"binary command failed for {session['session_id']} "
                f"with return code {error.returncode}"
            )
            atomic_json(manifest_path, manifest)
            raise RuntimeError(manifest["failure"]) from error
        session["returncode"] = completed.returncode
        raw_path = resolve_path(str(session["raw_csv"]))
        trace_path = resolve_path(str(session["energy_trace_csv"]))
        if not raw_path.is_file() or not trace_path.is_file():
            session["status"] = "failed"
            session["finished_at"] = timestamp()
            manifest["status"] = "failed"
            manifest["failure"] = (
                f"{session['session_id']}: binary returned success without raw and trace CSVs"
            )
            atomic_json(manifest_path, manifest)
            raise RuntimeError(manifest["failure"])
        try:
            validation = validate_raw_and_trace(
                session=session,
                raw_path=raw_path,
                trace_path=trace_path,
                binary_sha256=str(binary_meta["sha256"]),
            )
        except Exception as error:
            session["status"] = "failed"
            session["finished_at"] = timestamp()
            manifest["status"] = "failed"
            manifest["failure"] = f"{session['session_id']}: {error}"
            atomic_json(manifest_path, manifest)
            raise
        session["raw_sha256"] = sha256_file(raw_path)
        session["energy_trace_sha256"] = sha256_file(trace_path)
        session["validation"] = validation
        session["finished_at"] = timestamp()
        session["status"] = "complete"
        atomic_json(manifest_path, manifest)

    gpu_identities = {
        (
            session["validation"]["cuda_pci_bus_id"],
            session["validation"]["gpu_name"],
        )
        for session in sessions
    }
    if len(gpu_identities) != 1:
        manifest["status"] = "failed"
        manifest["failure"] = "GPU identity changed across fresh process sessions"
        atomic_json(manifest_path, manifest)
        raise RuntimeError(manifest["failure"])
    cuda_pci_bus_id, gpu_name = next(iter(gpu_identities))
    manifest["observed_gpu_identity"] = {
        "cuda_pci_bus_id": cuda_pci_bus_id,
        "gpu_name": gpu_name,
        "cuda_binary_arch": 86,
    }
    manifest["status"] = "complete"
    manifest["finished_at"] = timestamp()
    manifest["manifest_content_hash_note"] = (
        "Hash this completed manifest externally; it cannot contain its own stable hash."
    )
    atomic_json(manifest_path, manifest)
    print("run_status=complete process_sessions=9 cells=27 roles=162")


def self_test() -> None:
    assert GRID_BLOCKS == math.ceil(RUNTIME_SM_COUNT * SM_COVERAGE)
    assert expected_logical_output_elements(1) == 41 * 2 * 1024
    assert TRACE_SAMPLE_MS == 250.0
    assert TRACE_MIN_UPDATES == 16
    assert TRACE_MEDIAN_INTERVAL_GATE_S == (0.125, 0.500)
    assert INPUT_LOGIT_SCALE == 4.0
    assert INPUT_SEED == 5573589319906701683
    assert tuple(POLICY_ORDERS) == ("ABC", "BCA", "CAB")
    assert POLICY_ORDERS["ABC"] == ("fp32", "fp16_scalar", "fp16x2")
    assert POLICY_ORDERS["BCA"] == ("fp16_scalar", "fp16x2", "fp32")
    assert POLICY_ORDERS["CAB"] == ("fp16x2", "fp32", "fp16_scalar")
    assert STAGE_ORDERS == {
        "ABC": ("exp", "reduction", "normalization"),
        "BCA": ("reduction", "normalization", "exp"),
        "CAB": ("normalization", "exp", "reduction"),
    }
    assert NCU_AUDIT_SCHEMA == "softmax_whole_stage_atc_ncu_audit_v1"
    sessions = build_sessions(
        run_root=Path("/tmp/stage_atc_self_test"),
        tag="selftest",
        binary=Path("/tmp/fake_stage_atc"),
        binary_sha256="0" * 64,
    )
    assert len(sessions) == 9
    assert sum(int(session["expected_cells"]) for session in sessions) == 27
    assert sum(int(session["expected_roles"]) for session in sessions) == 162
    keys = {
        (session["stage"], int(session["session_index"])) for session in sessions
    }
    assert keys == {(stage, index) for stage in STAGES for index in (1, 2, 3)}
    assert [session["stage"] for session in sessions] == [
        "exp",
        "reduction",
        "normalization",
        "reduction",
        "normalization",
        "exp",
        "normalization",
        "exp",
        "reduction",
    ]
    role_ids: set[str] = set()
    for session in sessions:
        command = session["command"]
        assert command[command.index("--logit-scale") + 1] == "4.0"
        assert command[command.index("--seed") + 1] == str(INPUT_SEED)
        schedule = session["execution_schedule"]
        assert len(schedule) == 18
        assert [item["session_role_index"] for item in schedule] == list(range(18))
        assert [item["variant"] for item in schedule[:6]] == [
            "control",
            "treatment",
            "control",
            "treatment",
            "control",
            "treatment",
        ]
        assert [item["bracket_index"] for item in schedule[:6]] == [0, 0, 0, 1, 1, 1]
        assert not role_ids.intersection(item["role_id"] for item in schedule)
        role_ids.update(item["role_id"] for item in schedule)
    assert len(role_ids) == 162
    print("softmax_whole_stage_atc_runner_self_test=pass")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", default="build-whole-stage-atc")
    parser.add_argument("--binary", help="override stage ATC executable path")
    parser.add_argument("--output-dir", default="results/raw")
    parser.add_argument("--session-tag")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="execute all nine fresh processes after writing the manifest",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    run_root = plan_run(args)
    if args.execute:
        execute_run(run_root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as error:  # pragma: no cover - command-line boundary
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
