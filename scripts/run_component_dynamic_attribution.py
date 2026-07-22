#!/usr/bin/env python3
"""Run interleaved component-energy attribution pairs.

The runner preserves a directly observed matched-ITER completion delta and
brackets every treatment/control pair with contemporaneous ``clocked_empty``
measurements. The explicit manifest is the only supported pairing source for
MI-ATC and bytes/time regression analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from run_component_regression_sweep import parse_calibration_result
from run_sweep import PROFILES, classify, mode_allowed


PROTOCOL_REVISION = "component_dynamic_attribution_v3"


@dataclass(frozen=True)
class GpuState:
    temperature_c: float
    power_w: float
    gpu_util_pct: float
    memory_util_pct: float


def query_gpu_state(args: argparse.Namespace) -> GpuState:
    command = [
        args.nvidia_smi,
        "-i",
        str(args.gpu_id),
        "--query-gpu=temperature.gpu,power.draw,utilization.gpu,utilization.memory",
        "--format=csv,noheader,nounits",
    ]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"GPU cooldown query failed rc={proc.returncode}: {' '.join(command)}\n"
            f"{proc.stderr.strip()}"
        )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(
            f"expected one nvidia-smi row, got {len(lines)}: {proc.stdout}"
        )
    values = [value.strip() for value in next(csv.reader([lines[0]]))]
    if len(values) != 4:
        raise RuntimeError(f"unexpected nvidia-smi cooldown row: {lines[0]}")
    try:
        return GpuState(*(float(value) for value in values))
    except ValueError as exc:
        raise RuntimeError(f"non-numeric nvidia-smi cooldown row: {lines[0]}") from exc


def wait_for_gpu_cooldown(args: argparse.Namespace) -> tuple[GpuState, float]:
    started = time.monotonic()
    deadline = started + args.max_cooldown_seconds
    consecutive = 0
    last: GpuState | None = None
    while True:
        last = query_gpu_state(args)
        ready = (
            last.temperature_c <= args.cooldown_max_temperature_c
            and last.power_w <= args.cooldown_max_power_w
            and last.gpu_util_pct <= args.cooldown_max_gpu_util_pct
            and last.memory_util_pct <= args.cooldown_max_memory_util_pct
        )
        consecutive = consecutive + 1 if ready else 0
        if consecutive >= args.cooldown_consecutive_samples:
            return last, time.monotonic() - started
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "GPU did not return to the pre-run state within the cooldown limit: "
                f"temp={last.temperature_c:.1f}C power={last.power_w:.1f}W "
                f"gpu_util={last.gpu_util_pct:.1f}% "
                f"memory_util={last.memory_util_pct:.1f}% "
                f"limit={args.max_cooldown_seconds:.1f}s"
            )
        time.sleep(args.cooldown_poll_seconds)

RAW_REQUIRED_FIELDS = {
    "run_id",
    "gpu_id",
    "n_gpu_active",
    "mode",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "ITER",
    "elapsed_s",
    "net_E_J",
    "measurement_start_epoch_ms",
    "measurement_end_epoch_ms",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "smid_histogram_ok",
    "notes",
}

PROFILE_DEFAULTS: dict[str, dict[str, int]] = {
    "rtx3090": {
        "blocks_per_sm": 8,
        "shared_w_sm_kib": 64,
        "l1_w_sm_kib": 16,
        "l2_control_w_sm_kib": 32,
        "external_w_sm_kib": 256,
    },
    "v100": {
        "blocks_per_sm": 32,
        "shared_w_sm_kib": 32,
        "l1_w_sm_kib": 32,
        "l2_control_w_sm_kib": 32,
        "external_w_sm_kib": 256,
    },
    "a100": {
        "blocks_per_sm": 16,
        "shared_w_sm_kib": 128,
        "l1_w_sm_kib": 32,
        "l2_control_w_sm_kib": 128,
        "external_w_sm_kib": 2048,
    },
    "h100": {
        "blocks_per_sm": 16,
        "shared_w_sm_kib": 128,
        "l1_w_sm_kib": 32,
        "l2_control_w_sm_kib": 128,
        "external_w_sm_kib": 2048,
    },
}

PROFILE_BLOCKS_PER_SM_VALUES: dict[str, tuple[int, ...]] = {
    "rtx3090": (4, 8, 16),
    "v100": (4, 16, 32),
    "a100": (4, 16, 32),
    "h100": (4, 16, 32),
}


@dataclass(frozen=True)
class ComponentDefinition:
    key: str
    control_mode: str
    treatment_mode: str
    factor_kind: str
    denominator_kind: str


COMPONENTS: dict[str, ComponentDefinition] = {
    "tensor": ComponentDefinition(
        "tensor", "reg_operand_only", "reg_mma", "reuse_factor", "FLOP"
    ),
    "shared": ComponentDefinition(
        "shared",
        "shared_scalar_addr_only",
        "shared_scalar_load_only",
        "load_repeat",
        "shared_read_bytes",
    ),
    "l1": ComponentDefinition(
        "l1",
        "global_addr_only",
        "global_l1_load_only",
        "load_repeat",
        "l1_request_bytes",
    ),
    "l2": ComponentDefinition(
        "l2",
        "global_l1_load_only",
        "l2_cg_load_only",
        "load_repeat",
        "l2_read_bytes",
    ),
    "external": ComponentDefinition(
        "external",
        "l2_cg_load_only",
        "dram_cg_load_only",
        "load_repeat",
        "external_read_bytes",
    ),
}


@dataclass(frozen=True)
class Coordinate:
    component: str
    factor_kind: str
    factor_value: int
    target_duration_s: float
    control_mode: str
    control_w_sm_kib: int
    treatment_mode: str
    treatment_w_sm_kib: int
    blocks_per_sm: int
    reuse_factor: int
    load_repeat: int

    @property
    def coordinate_id(self) -> str:
        duration_token = str(self.target_duration_s).replace(".", "p")
        factor_token = "RF" if self.factor_kind == "reuse_factor" else "LR"
        return (
            f"{self.component}_{factor_token}{self.factor_value}_"
            f"D{duration_token}_B{self.blocks_per_sm}"
        )


@dataclass(frozen=True)
class CalibratedPair:
    coordinate: Coordinate
    resolved_iters: int
    treatment_calibrated_iters: int
    control_min_calibrated_iters: int
    predicted_treatment_s: float
    predicted_control_s: float
    calibration_policy: str
    grid_anchor_factor: int
    grid_anchor_blocks_per_sm: int
    grid_work_units: int


MANIFEST_FIELDS = [
    "protocol_revision",
    "record_type",
    "profile",
    "component",
    "coordinate_id",
    "pair_id",
    "pair_attempt",
    "repeat",
    "role",
    "sequence_index",
    "execution_order",
    "target_duration_s",
    "factor_kind",
    "factor_value",
    "calibration_policy",
    "grid_anchor_factor",
    "grid_anchor_blocks_per_sm",
    "grid_work_units",
    "mode",
    "W_SM_KiB",
    "blocks_per_SM",
    "active_SM",
    "reuse_factor",
    "load_repeat",
    "ITER",
    "binary_sha256",
    "quiescence_status",
    "cooldown_wait_seconds",
    "pre_pair_temp_C",
    "pre_pair_power_W",
    "pre_pair_gpu_util_pct",
    "pre_pair_memory_util_pct",
    "run_id",
    "gpu_id",
    "smid_histogram_ok",
    "measurement_start_epoch_ms",
    "measurement_end_epoch_ms",
    "elapsed_s",
    "net_E_J",
    "FLOP",
    "N_MMA",
    "expected_shared_bytes",
    "expected_l1_bytes",
    "expected_l2_bytes",
    "expected_dram_bytes",
    "expected_addr_ops",
    "energy_source",
    "energy_integration_method",
    "measurement_scope",
    "clock_sm_mhz",
    "clock_mem_mhz",
    "temp_C",
    "power_before_mw",
    "power_after_mw",
    "command_start_epoch_ms",
    "command_end_epoch_ms",
]


CALIBRATION_FIELDS = [
    "protocol_revision",
    "record_type",
    "profile",
    "component",
    "coordinate_id",
    "factor_kind",
    "factor_value",
    "calibration_policy",
    "grid_anchor_factor",
    "grid_anchor_blocks_per_sm",
    "grid_work_units",
    "binary_sha256",
    "target_duration_s",
    "blocks_per_SM",
    "control_mode",
    "control_W_SM_KiB",
    "treatment_mode",
    "treatment_W_SM_KiB",
    "treatment_trial_iters",
    "treatment_trial_elapsed_s",
    "treatment_calibrated_iters",
    "control_trial_iters",
    "control_trial_elapsed_s",
    "control_min_calibrated_iters",
    "resolved_iters",
    "predicted_treatment_s",
    "predicted_control_s",
    "treatment_stretch",
    "status",
    "treatment_calibration_command",
    "control_calibration_command",
]


DESIGN_FIELDS = [
    "protocol_revision",
    "profile",
    "component",
    "coordinate_id",
    "factor_kind",
    "factor_value",
    "calibration_policy",
    "target_duration_s",
    "blocks_per_SM",
    "active_SM",
    "control_mode",
    "control_W_SM_KiB",
    "treatment_mode",
    "treatment_W_SM_KiB",
    "denominator_kind",
    "control_regime",
    "treatment_regime",
    "valid",
    "reason",
]


def parse_positive_ints(value: str) -> list[int]:
    values = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not values or any(item <= 0 for item in values):
        raise ValueError("integer lists must contain positive values")
    if len(set(values)) != len(values):
        raise ValueError("integer lists must not contain duplicates")
    return values


def parse_positive_floats(value: str) -> list[float]:
    values = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not values or any(item <= 0.0 for item in values):
        raise ValueError("duration lists must contain positive values")
    if len(set(values)) != len(values):
        raise ValueError("duration lists must not contain duplicates")
    return values


def parse_components(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise ValueError("at least one component is required")
    unknown = sorted(set(values) - set(COMPONENTS))
    if unknown:
        raise ValueError(f"unknown components: {','.join(unknown)}")
    if len(set(values)) != len(values):
        raise ValueError("components must not contain duplicates")
    return values


def component_working_sets(
    component: str, defaults: dict[str, int]
) -> tuple[int, int]:
    if component == "tensor":
        return 1, 1
    if component == "shared":
        value = defaults["shared_w_sm_kib"]
        return value, value
    if component == "l1":
        value = defaults["l1_w_sm_kib"]
        return value, value
    if component == "l2":
        value = defaults["l1_w_sm_kib"]
        return value, value
    if component == "external":
        return (
            defaults["l2_control_w_sm_kib"],
            defaults["external_w_sm_kib"],
        )
    raise ValueError(f"unsupported component {component}")


def build_coordinates(
    *,
    profile_name: str,
    active_sm: int,
    blocks_per_sm_values: list[int],
    components: list[str],
    reuse_factors: list[int],
    load_repeats: list[int],
    durations: list[float],
    defaults: dict[str, int],
) -> tuple[list[Coordinate], list[dict[str, Any]]]:
    profile = PROFILES[profile_name]
    coordinates: list[Coordinate] = []
    design_rows: list[dict[str, Any]] = []
    for component in components:
        definition = COMPONENTS[component]
        factors = reuse_factors if component == "tensor" else load_repeats
        control_w, treatment_w = component_working_sets(component, defaults)
        for blocks_per_sm in blocks_per_sm_values:
            control_info = classify(
                control_w, blocks_per_sm, profile, active_sm=active_sm
            )
            treatment_info = classify(
                treatment_w, blocks_per_sm, profile, active_sm=active_sm
            )
            valid = mode_allowed(
                definition.control_mode, control_info
            ) and mode_allowed(definition.treatment_mode, treatment_info)
            reasons: list[str] = []
            if not mode_allowed(definition.control_mode, control_info):
                reasons.append(f"control:{control_info['reason']}")
            if not mode_allowed(definition.treatment_mode, treatment_info):
                reasons.append(f"treatment:{treatment_info['reason']}")
            for factor in factors:
                for duration in durations:
                    coordinate = Coordinate(
                        component=component,
                        factor_kind=definition.factor_kind,
                        factor_value=factor,
                        target_duration_s=duration,
                        control_mode=definition.control_mode,
                        control_w_sm_kib=control_w,
                        treatment_mode=definition.treatment_mode,
                        treatment_w_sm_kib=treatment_w,
                        blocks_per_sm=blocks_per_sm,
                        reuse_factor=factor if component == "tensor" else 1,
                        load_repeat=1 if component == "tensor" else factor,
                    )
                    coordinates.append(coordinate)
                    design_rows.append(
                        {
                            "protocol_revision": PROTOCOL_REVISION,
                            "profile": profile_name,
                            "component": component,
                            "coordinate_id": coordinate.coordinate_id,
                            "factor_kind": definition.factor_kind,
                            "factor_value": factor,
                            "target_duration_s": duration,
                            "blocks_per_SM": blocks_per_sm,
                            "active_SM": active_sm,
                            "control_mode": definition.control_mode,
                            "control_W_SM_KiB": control_w,
                            "treatment_mode": definition.treatment_mode,
                            "treatment_W_SM_KiB": treatment_w,
                            "denominator_kind": definition.denominator_kind,
                            "control_regime": control_info["regime"],
                            "treatment_regime": treatment_info["regime"],
                            "valid": valid,
                            "reason": ";".join(reasons),
                        }
                    )
    return coordinates, design_rows


def command_for(
    args: argparse.Namespace,
    *,
    mode: str,
    w_sm_kib: int,
    blocks_per_sm: int,
    reuse_factor: int,
    load_repeat: int,
    seconds: float,
    iters: int = 0,
    calibrate_only: bool = False,
) -> list[str]:
    command = [
        args.binary,
        "--gpu-list",
        str(args.gpu_id),
        "--mode",
        mode,
        "--w-sm-kib",
        str(w_sm_kib),
        "--blocks-per-sm",
        str(blocks_per_sm),
        "--target-profile",
        args.target_profile,
        "--active-sm",
        str(args.active_sm),
        "--seconds",
        str(seconds),
        "--repeats",
        "1",
        "--reuse-factor",
        str(reuse_factor),
        "--load-repeat",
        str(load_repeat),
        "--store-repeat",
        "1",
        "--global-warmup-passes",
        str(args.global_warmup_passes),
        "--idle-settle-seconds",
        str(args.idle_settle_seconds),
        "--idle-measure-seconds",
        str(args.idle_measure_seconds),
        "--idle-ready-max-power-w",
        str(args.idle_ready_max_power_w),
        "--idle-ready-consecutive-samples",
        str(args.idle_ready_consecutive_samples),
        "--idle-ready-poll-seconds",
        str(args.idle_ready_poll_seconds),
        "--idle-ready-timeout-seconds",
        str(args.idle_ready_timeout_seconds),
        "--l2-residency-policy",
        "normal",
        "--l2-address-layout",
        "contiguous",
        "--output",
        args.output,
        "--verify-smid",
        "1",
    ]
    if iters > 0:
        command.extend(["--iters", str(iters)])
    if calibrate_only:
        command.append("--calibrate-only")
    return command


def calibrate_mode(
    args: argparse.Namespace,
    *,
    mode: str,
    w_sm_kib: int,
    blocks_per_sm: int,
    reuse_factor: int,
    load_repeat: int,
    seconds: float,
) -> tuple[Any, list[str]]:
    command = command_for(
        args,
        mode=mode,
        w_sm_kib=w_sm_kib,
        blocks_per_sm=blocks_per_sm,
        reuse_factor=reuse_factor,
        load_repeat=load_repeat,
        seconds=seconds,
        calibrate_only=True,
    )
    proc = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=args.max_command_wall_seconds,
    )
    combined = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(
            f"calibration failed for {mode} W={w_sm_kib} B={blocks_per_sm}: "
            f"rc={proc.returncode}\n{combined}"
        )
    return parse_calibration_result(combined), command


def calibrate_pair(
    args: argparse.Namespace, coordinate: Coordinate
) -> CalibratedPair:
    treatment, treatment_command = calibrate_mode(
        args,
        mode=coordinate.treatment_mode,
        w_sm_kib=coordinate.treatment_w_sm_kib,
        blocks_per_sm=coordinate.blocks_per_sm,
        reuse_factor=coordinate.reuse_factor,
        load_repeat=coordinate.load_repeat,
        seconds=coordinate.target_duration_s,
    )
    control, control_command = calibrate_mode(
        args,
        mode=coordinate.control_mode,
        w_sm_kib=coordinate.control_w_sm_kib,
        blocks_per_sm=coordinate.blocks_per_sm,
        reuse_factor=coordinate.reuse_factor,
        load_repeat=coordinate.load_repeat,
        seconds=args.control_min_seconds,
    )
    resolved = max(treatment.target_iters, control.target_iters)
    predicted_treatment = treatment.trial_elapsed_s * resolved / treatment.trial_iters
    predicted_control = control.trial_elapsed_s * resolved / control.trial_iters
    stretch = predicted_treatment / coordinate.target_duration_s
    status = "accepted"
    if stretch > args.max_treatment_stretch:
        status = "reject_treatment_stretch"
    if predicted_treatment > args.max_predicted_treatment_seconds:
        status = "reject_treatment_wall_time"
    append_csv(
        Path(args.calibration_csv),
        CALIBRATION_FIELDS,
        {
            "protocol_revision": PROTOCOL_REVISION,
            "record_type": "independent_mode_calibration",
            "profile": args.target_profile,
            "component": coordinate.component,
            "coordinate_id": coordinate.coordinate_id,
            "factor_kind": coordinate.factor_kind,
            "factor_value": coordinate.factor_value,
            "calibration_policy": "independent_duration",
            "grid_anchor_factor": "",
            "grid_anchor_blocks_per_sm": "",
            "grid_work_units": "",
            "binary_sha256": args.binary_sha256,
            "target_duration_s": coordinate.target_duration_s,
            "blocks_per_SM": coordinate.blocks_per_sm,
            "control_mode": coordinate.control_mode,
            "control_W_SM_KiB": coordinate.control_w_sm_kib,
            "treatment_mode": coordinate.treatment_mode,
            "treatment_W_SM_KiB": coordinate.treatment_w_sm_kib,
            "treatment_trial_iters": treatment.trial_iters,
            "treatment_trial_elapsed_s": treatment.trial_elapsed_s,
            "treatment_calibrated_iters": treatment.target_iters,
            "control_trial_iters": control.trial_iters,
            "control_trial_elapsed_s": control.trial_elapsed_s,
            "control_min_calibrated_iters": control.target_iters,
            "resolved_iters": resolved,
            "predicted_treatment_s": predicted_treatment,
            "predicted_control_s": predicted_control,
            "treatment_stretch": stretch,
            "status": status,
            "treatment_calibration_command": " ".join(treatment_command),
            "control_calibration_command": " ".join(control_command),
        },
    )
    if status != "accepted":
        raise RuntimeError(
            f"{coordinate.coordinate_id}: calibration {status}; treatment="
            f"{predicted_treatment:.3f}s control={predicted_control:.3f}s "
            f"resolved_ITER={resolved}"
        )
    return CalibratedPair(
        coordinate=coordinate,
        resolved_iters=resolved,
        treatment_calibrated_iters=treatment.target_iters,
        control_min_calibrated_iters=control.target_iters,
        predicted_treatment_s=predicted_treatment,
        predicted_control_s=predicted_control,
        calibration_policy="independent_duration",
        grid_anchor_factor=0,
        grid_anchor_blocks_per_sm=0,
        grid_work_units=0,
    )


def apply_calibration_policy(
    args: argparse.Namespace, calibrated: list[CalibratedPair]
) -> list[CalibratedPair]:
    if args.calibration_policy == "independent_duration":
        return calibrated

    grouped: dict[tuple[Any, ...], list[CalibratedPair]] = {}
    for pair in calibrated:
        key: tuple[Any, ...] = (
            pair.coordinate.component,
            pair.coordinate.target_duration_s,
        )
        if args.calibration_policy == "traffic_grid":
            key += (pair.coordinate.blocks_per_sm,)
        grouped.setdefault(key, []).append(pair)

    adjusted_by_coordinate: dict[str, CalibratedPair] = {}
    for _key, pairs in grouped.items():
        factor_values = sorted({pair.coordinate.factor_value for pair in pairs})
        block_values = sorted({pair.coordinate.blocks_per_sm for pair in pairs})
        anchor_factor = factor_values[len(factor_values) // 2]
        anchor_blocks = block_values[len(block_values) // 2]
        anchor = next(
            pair
            for pair in pairs
            if pair.coordinate.factor_value == anchor_factor
            and pair.coordinate.blocks_per_sm == anchor_blocks
        )

        def work_multiplier(pair: CalibratedPair) -> int:
            multiplier = pair.coordinate.factor_value
            if args.calibration_policy == "factorial_grid":
                multiplier *= pair.coordinate.blocks_per_sm
            return multiplier

        work_units = anchor.resolved_iters * work_multiplier(anchor)
        # Every same-ITER control must remain long enough to be observed. Raise
        # the common work level instead of silently allowing a launch-only row.
        work_units = max(
            work_units,
            max(
                pair.control_min_calibrated_iters * work_multiplier(pair)
                for pair in pairs
            ),
        )
        for pair in pairs:
            factor = pair.coordinate.factor_value
            resolved_iters = max(1, math.ceil(work_units / work_multiplier(pair)))
            predicted_treatment = (
                pair.predicted_treatment_s * resolved_iters / pair.resolved_iters
            )
            predicted_control = (
                pair.predicted_control_s * resolved_iters / pair.resolved_iters
            )
            status = "accepted"
            if resolved_iters < pair.control_min_calibrated_iters:
                status = "reject_control_below_minimum"
            if predicted_treatment > args.max_predicted_treatment_seconds:
                status = "reject_treatment_wall_time"
            if status != "accepted":
                raise RuntimeError(
                    f"{pair.coordinate.coordinate_id}: {args.calibration_policy} calibration "
                    f"{status}; anchor_factor={anchor_factor} work_units={work_units} "
                    f"anchor_B={anchor_blocks} "
                    f"ITER={resolved_iters} treatment={predicted_treatment:.3f}s "
                    f"control={predicted_control:.3f}s"
                )
            adjusted = CalibratedPair(
                coordinate=pair.coordinate,
                resolved_iters=resolved_iters,
                treatment_calibrated_iters=pair.treatment_calibrated_iters,
                control_min_calibrated_iters=pair.control_min_calibrated_iters,
                predicted_treatment_s=predicted_treatment,
                predicted_control_s=predicted_control,
                calibration_policy=args.calibration_policy,
                grid_anchor_factor=anchor_factor,
                grid_anchor_blocks_per_sm=anchor_blocks,
                grid_work_units=work_units,
            )
            adjusted_by_coordinate[pair.coordinate.coordinate_id] = adjusted
            append_csv(
                Path(args.calibration_csv),
                CALIBRATION_FIELDS,
                {
                    "protocol_revision": PROTOCOL_REVISION,
                    "record_type": f"{args.calibration_policy}_adjustment",
                    "profile": args.target_profile,
                    "component": pair.coordinate.component,
                    "coordinate_id": pair.coordinate.coordinate_id,
                    "factor_kind": pair.coordinate.factor_kind,
                    "factor_value": factor,
                    "calibration_policy": args.calibration_policy,
                    "grid_anchor_factor": anchor_factor,
                    "grid_anchor_blocks_per_sm": anchor_blocks,
                    "grid_work_units": work_units,
                    "binary_sha256": args.binary_sha256,
                    "target_duration_s": pair.coordinate.target_duration_s,
                    "blocks_per_SM": pair.coordinate.blocks_per_sm,
                    "control_mode": pair.coordinate.control_mode,
                    "control_W_SM_KiB": pair.coordinate.control_w_sm_kib,
                    "treatment_mode": pair.coordinate.treatment_mode,
                    "treatment_W_SM_KiB": pair.coordinate.treatment_w_sm_kib,
                    "treatment_calibrated_iters": pair.treatment_calibrated_iters,
                    "control_min_calibrated_iters": pair.control_min_calibrated_iters,
                    "resolved_iters": resolved_iters,
                    "predicted_treatment_s": predicted_treatment,
                    "predicted_control_s": predicted_control,
                    "treatment_stretch": (
                        predicted_treatment / pair.coordinate.target_duration_s
                    ),
                    "status": status,
                },
            )
    return [adjusted_by_coordinate[pair.coordinate.coordinate_id] for pair in calibrated]


def append_csv(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in fieldnames})


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows({name: row.get(name, "") for name in fieldnames} for row in rows)


def assert_csv_header(path: Path, expected: list[str]) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="", encoding="utf-8") as handle:
        actual = next(csv.reader(handle), [])
    if actual != expected:
        raise ValueError(
            f"CSV schema mismatch for resume: {path}; use a new tag or --overwrite"
        )


def assert_raw_resume_schema(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="", encoding="utf-8") as handle:
        actual = set(next(csv.reader(handle), []))
    missing = sorted(RAW_REQUIRED_FIELDS - actual)
    if missing:
        raise ValueError(
            f"raw CSV schema mismatch for resume: {path}; missing={','.join(missing)}; "
            "use a new tag or --overwrite"
        )


def design_signature(rows: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    return sorted(
        tuple(str(row.get(field, "")) for field in DESIGN_FIELDS) for row in rows
    )


def validate_or_write_design(
    path: Path, rows: list[dict[str, Any]], *, resume: bool
) -> None:
    if resume and path.exists() and path.stat().st_size > 0:
        assert_csv_header(path, DESIGN_FIELDS)
        if design_signature(read_raw(path)) != design_signature(rows):
            raise ValueError(
                f"design mismatch for resume: {path}; use a new tag or --overwrite"
            )
        return
    write_csv(path, DESIGN_FIELDS, rows)


def load_completed_pairs(
    path: Path, *, binary_hash: str
) -> tuple[set[tuple[str, int]], dict[tuple[str, int], int]]:
    grouped: dict[tuple[str, int, str], list[dict[str, str]]] = {}
    max_attempt: dict[tuple[str, int], int] = {}
    for row in read_raw(path):
        if row.get("protocol_revision") != PROTOCOL_REVISION:
            continue
        coordinate_id = row.get("coordinate_id", "")
        try:
            repeat = int(row.get("repeat", ""))
            attempt = int(row.get("pair_attempt", "0") or "0")
        except ValueError:
            continue
        identity = (coordinate_id, repeat)
        max_attempt[identity] = max(max_attempt.get(identity, -1), attempt)
        grouped.setdefault((coordinate_id, repeat, row.get("pair_id", "")), []).append(
            row
        )

    required_roles = {"baseline_before", "control", "treatment", "baseline_after"}
    completed: set[tuple[str, int]] = set()
    for (coordinate_id, repeat, _pair_id), rows in grouped.items():
        roles = [row.get("role", "") for row in rows]
        hashes = {row.get("binary_sha256", "") for row in rows}
        if (
            len(rows) == 4
            and set(roles) == required_roles
            and len(roles) == len(set(roles))
            and hashes == {binary_hash}
        ):
            completed.add((coordinate_id, repeat))
    return completed, max_attempt


def load_complete_calibration(
    args: argparse.Namespace,
    coordinates: list[Coordinate],
    blocks_per_sm_values: list[int],
) -> tuple[dict[int, int], list[CalibratedPair]] | None:
    rows = read_raw(Path(args.calibration_csv))
    if not rows:
        return None
    matching = [
        row
        for row in rows
        if row.get("protocol_revision") == PROTOCOL_REVISION
        and row.get("binary_sha256") == args.binary_sha256
        and row.get("status") == "accepted"
    ]
    baselines: dict[int, int] = {}
    for row in matching:
        if row.get("record_type") != "baseline_calibration":
            continue
        try:
            baselines[int(row["blocks_per_SM"])] = int(row["resolved_iters"])
        except (KeyError, ValueError):
            continue
    if set(baselines) != set(blocks_per_sm_values):
        return None

    expected_record = (
        "independent_mode_calibration"
        if args.calibration_policy == "independent_duration"
        else f"{args.calibration_policy}_adjustment"
    )
    latest: dict[str, dict[str, str]] = {}
    for row in matching:
        if (
            row.get("record_type") == expected_record
            and row.get("calibration_policy") == args.calibration_policy
        ):
            latest[row.get("coordinate_id", "")] = row
    if set(latest) != {coordinate.coordinate_id for coordinate in coordinates}:
        return None

    calibrated: list[CalibratedPair] = []
    by_id = {coordinate.coordinate_id: coordinate for coordinate in coordinates}
    try:
        for coordinate_id, coordinate in by_id.items():
            row = latest[coordinate_id]
            calibrated.append(
                CalibratedPair(
                    coordinate=coordinate,
                    resolved_iters=int(row["resolved_iters"]),
                    treatment_calibrated_iters=int(row["treatment_calibrated_iters"]),
                    control_min_calibrated_iters=int(row["control_min_calibrated_iters"]),
                    predicted_treatment_s=float(row["predicted_treatment_s"]),
                    predicted_control_s=float(row["predicted_control_s"]),
                    calibration_policy=args.calibration_policy,
                    grid_anchor_factor=int(row.get("grid_anchor_factor", "0") or "0"),
                    grid_anchor_blocks_per_sm=int(
                        row.get("grid_anchor_blocks_per_sm", "0") or "0"
                    ),
                    grid_work_units=int(row.get("grid_work_units", "0") or "0"),
                )
            )
    except (KeyError, ValueError):
        return None
    return baselines, calibrated


def read_raw(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def newly_appended_active_row(
    path: Path, previous_count: int, gpu_id: int
) -> dict[str, str]:
    rows = read_raw(path)[previous_count:]
    active = [
        row
        for row in rows
        if row.get("gpu_id") == str(gpu_id)
        and (
            "gpu_active=1" in row.get("notes", "")
            or row.get("n_gpu_active") == "1"
        )
    ]
    if len(active) != 1:
        raise RuntimeError(
            "expected one newly appended active physical-GPU row; "
            f"gpu_id={gpu_id} new_rows={len(rows)} active_rows={len(active)}"
        )
    return active[0]


def execute_one(
    args: argparse.Namespace,
    *,
    coordinate: Coordinate,
    pair_id: str,
    pair_attempt: int,
    repeat: int,
    role: str,
    sequence_index: int,
    execution_order: str,
    mode: str,
    w_sm_kib: int,
    reuse_factor: int,
    load_repeat: int,
    iters: int,
    binary_sha256: str,
    calibration_policy: str,
    grid_anchor_factor: int,
    grid_anchor_blocks_per_sm: int,
    grid_work_units: int,
    pre_pair_state: GpuState | None,
    cooldown_wait_seconds: float,
) -> None:
    raw_path = Path(args.output)
    previous_count = len(read_raw(raw_path))
    command = command_for(
        args,
        mode=mode,
        w_sm_kib=w_sm_kib,
        blocks_per_sm=coordinate.blocks_per_sm,
        reuse_factor=reuse_factor,
        load_repeat=load_repeat,
        seconds=coordinate.target_duration_s,
        iters=iters,
    )
    start_ms = int(time.time() * 1000)
    proc = subprocess.run(
        command,
        check=False,
        timeout=args.max_command_wall_seconds,
    )
    end_ms = int(time.time() * 1000)
    if proc.returncode != 0:
        raise RuntimeError(
            f"energy command failed rc={proc.returncode}: {' '.join(command)}"
        )
    raw = newly_appended_active_row(raw_path, previous_count, args.gpu_id)
    append_csv(
        Path(args.manifest),
        MANIFEST_FIELDS,
        {
            "protocol_revision": PROTOCOL_REVISION,
            "record_type": "active_baseline" if role.startswith("baseline_") else "pair_run",
            "profile": args.target_profile,
            "component": coordinate.component,
            "coordinate_id": coordinate.coordinate_id,
            "pair_id": pair_id,
            "pair_attempt": pair_attempt,
            "repeat": repeat,
            "role": role,
            "sequence_index": sequence_index,
            "execution_order": execution_order,
            "target_duration_s": coordinate.target_duration_s,
            "factor_kind": coordinate.factor_kind,
            "factor_value": coordinate.factor_value,
            "calibration_policy": calibration_policy,
            "grid_anchor_factor": grid_anchor_factor,
            "grid_anchor_blocks_per_sm": grid_anchor_blocks_per_sm,
            "grid_work_units": grid_work_units,
            "mode": mode,
            "W_SM_KiB": w_sm_kib,
            "blocks_per_SM": coordinate.blocks_per_sm,
            "active_SM": args.active_sm,
            "reuse_factor": reuse_factor,
            "load_repeat": load_repeat,
            "ITER": iters,
            "binary_sha256": binary_sha256,
            "quiescence_status": (
                "skipped" if args.skip_quiescence else "strict_passed"
            ),
            "cooldown_wait_seconds": cooldown_wait_seconds,
            "pre_pair_temp_C": (
                pre_pair_state.temperature_c if pre_pair_state is not None else ""
            ),
            "pre_pair_power_W": (
                pre_pair_state.power_w if pre_pair_state is not None else ""
            ),
            "pre_pair_gpu_util_pct": (
                pre_pair_state.gpu_util_pct if pre_pair_state is not None else ""
            ),
            "pre_pair_memory_util_pct": (
                pre_pair_state.memory_util_pct if pre_pair_state is not None else ""
            ),
            "run_id": raw.get("run_id", ""),
            "gpu_id": raw.get("gpu_id", ""),
            "smid_histogram_ok": raw.get("smid_histogram_ok", ""),
            "measurement_start_epoch_ms": raw.get("measurement_start_epoch_ms", ""),
            "measurement_end_epoch_ms": raw.get("measurement_end_epoch_ms", ""),
            "elapsed_s": raw.get("elapsed_s", ""),
            "net_E_J": raw.get("net_E_J", ""),
            "FLOP": raw.get("FLOP", ""),
            "N_MMA": raw.get("N_MMA", ""),
            "expected_shared_bytes": raw.get("expected_shared_bytes", ""),
            "expected_l1_bytes": raw.get("expected_l1_bytes", ""),
            "expected_l2_bytes": raw.get("expected_l2_bytes", ""),
            "expected_dram_bytes": raw.get("expected_dram_bytes", ""),
            "expected_addr_ops": raw.get("expected_addr_ops", ""),
            "energy_source": raw.get("energy_source", ""),
            "energy_integration_method": raw.get("energy_integration_method", ""),
            "measurement_scope": raw.get("measurement_scope", ""),
            "clock_sm_mhz": raw.get("clock_sm_mhz", ""),
            "clock_mem_mhz": raw.get("clock_mem_mhz", ""),
            "temp_C": raw.get("temp_C", ""),
            "power_before_mw": raw.get("power_before_mw", ""),
            "power_after_mw": raw.get("power_after_mw", ""),
            "command_start_epoch_ms": start_ms,
            "command_end_epoch_ms": end_ms,
        },
    )


def run_quiescence(args: argparse.Namespace, stage: str) -> None:
    if args.skip_quiescence:
        return
    base = Path(args.manifest).with_suffix("")
    command = [
        sys.executable,
        "scripts/audit_gpu_quiescence.py",
        "--gpu",
        str(args.gpu_id),
        "--samples",
        str(args.quiescence_samples),
        "--interval-ms",
        str(args.quiescence_interval_ms),
        "--out-csv",
        f"{base}_{stage}_quiescence.csv",
        "--out-md",
        f"{base}_{stage}_quiescence.md",
        "--strict",
    ]
    subprocess.run(command, check=True, timeout=args.max_command_wall_seconds)


def binary_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_order(repeat: int, coordinate_index: int) -> tuple[list[str], str]:
    if (repeat + coordinate_index) % 2 == 0:
        return ["control", "treatment"], "control_then_treatment"
    return ["treatment", "control"], "treatment_then_control"


def self_test() -> None:
    for profile_name, defaults in PROFILE_DEFAULTS.items():
        coordinates, rows = build_coordinates(
            profile_name=profile_name,
            active_sm=int(PROFILES[profile_name]["full_sm"]),
            blocks_per_sm_values=list(PROFILE_BLOCKS_PER_SM_VALUES[profile_name]),
            components=list(COMPONENTS),
            reuse_factors=[1, 4, 16],
            load_repeats=[4, 8, 16],
            durations=[4.0, 7.0, 10.0],
            defaults=defaults,
        )
        assert len(coordinates) == 135
        assert len(rows) == 135
        invalid = [row for row in rows if not row["valid"]]
        assert not invalid, (profile_name, invalid)
        external = [row for row in rows if row["component"] == "external"]
        assert all(
            row["control_regime"] in {"shared_resident", "l2_candidate"}
            for row in external
        )
        assert all(row["treatment_regime"] == "dram_mixed_streaming" for row in external)
    assert pair_order(0, 0)[1] == "control_then_treatment"
    assert pair_order(1, 0)[1] == "treatment_then_control"
    try:
        parse_components("tensor,unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown component was accepted")
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        manifest_path = temporary_root / "manifest.csv"
        hash_value = "a" * 64
        complete_rows = [
            {
                "protocol_revision": PROTOCOL_REVISION,
                "coordinate_id": "tensor_RF4_D15p0_B16",
                "pair_id": "tensor_RF4_D15p0_B16_repeat0",
                "pair_attempt": 0,
                "repeat": 0,
                "role": role,
                "binary_sha256": hash_value,
            }
            for role in ("baseline_before", "control", "treatment", "baseline_after")
        ]
        complete_rows.append(
            {
                "protocol_revision": PROTOCOL_REVISION,
                "coordinate_id": "tensor_RF16_D15p0_B16",
                "pair_id": "tensor_RF16_D15p0_B16_repeat0_attempt1",
                "pair_attempt": 1,
                "repeat": 0,
                "role": "baseline_before",
                "binary_sha256": hash_value,
            }
        )
        write_csv(manifest_path, MANIFEST_FIELDS, complete_rows)
        completed, max_attempt = load_completed_pairs(
            manifest_path, binary_hash=hash_value
        )
        assert completed == {("tensor_RF4_D15p0_B16", 0)}
        assert max_attempt[("tensor_RF16_D15p0_B16", 0)] == 1

        design_path = temporary_root / "design.csv"
        design_row = {field: "" for field in DESIGN_FIELDS}
        design_row.update(
            {
                "protocol_revision": PROTOCOL_REVISION,
                "profile": "rtx3090",
                "component": "tensor",
                "coordinate_id": "tensor_RF4_D15p0_B16",
                "valid": True,
            }
        )
        validate_or_write_design(design_path, [design_row], resume=False)
        validate_or_write_design(design_path, [design_row], resume=True)
        changed_row = dict(design_row)
        changed_row["coordinate_id"] = "tensor_RF16_D15p0_B16"
        try:
            validate_or_write_design(design_path, [changed_row], resume=True)
        except ValueError:
            pass
        else:
            raise AssertionError("resume accepted a changed design")

        raw_path = temporary_root / "legacy_raw.csv"
        raw_path.write_text("run_id,gpu_id,net_E_J\n", encoding="utf-8")
        try:
            assert_raw_resume_schema(raw_path)
        except ValueError as exc:
            assert "measurement_scope" in str(exc)
        else:
            raise AssertionError("resume accepted a legacy raw CSV schema")
    print("component dynamic-attribution runner self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--target-profile", choices=sorted(PROFILES), default="rtx3090")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--active-sm", type=int, default=0)
    parser.add_argument("--blocks-per-sm", type=int, default=0)
    parser.add_argument(
        "--blocks-per-sm-values",
        default="",
        help="comma-separated factorial occupancy sweep; mutually exclusive with --blocks-per-sm",
    )
    parser.add_argument("--components", default="tensor,shared,l1,l2,external")
    parser.add_argument("--reuse-factors", default="1,2,4,8,16")
    parser.add_argument("--load-repeats", default="4,8,16")
    parser.add_argument("--durations", default="5,15,30")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--baseline-seconds", type=float, default=3.0)
    parser.add_argument(
        "--control-min-seconds",
        type=float,
        default=0.25,
        help="minimum calibrated control runtime; row-level elapsed time is gated by the analyzer",
    )
    parser.add_argument(
        "--calibration-policy",
        choices=["factorial_grid", "traffic_grid", "independent_duration"],
        default="factorial_grid",
    )
    parser.add_argument("--global-warmup-passes", type=int, default=4)
    parser.add_argument("--idle-settle-seconds", type=float, default=5.0)
    parser.add_argument("--idle-measure-seconds", type=float, default=10.0)
    parser.add_argument("--idle-ready-max-power-w", type=float, default=0.0)
    parser.add_argument("--idle-ready-consecutive-samples", type=int, default=3)
    parser.add_argument("--idle-ready-poll-seconds", type=float, default=0.5)
    parser.add_argument("--idle-ready-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--inter-command-delay-seconds", type=float, default=0.5)
    parser.add_argument("--pre-energy-cooldown-seconds", type=float, default=10.0)
    parser.add_argument("--max-command-wall-seconds", type=float, default=180.0)
    parser.add_argument("--max-predicted-treatment-seconds", type=float, default=60.0)
    parser.add_argument("--max-treatment-stretch", type=float, default=2.0)
    parser.add_argument("--quiescence-samples", type=int, default=12)
    parser.add_argument("--quiescence-interval-ms", type=int, default=1000)
    parser.add_argument("--skip-quiescence", action="store_true")
    parser.add_argument(
        "--pair-cooldown",
        action="store_true",
        help="wait for a common pre-pair state before baseline/control/treatment collection",
    )
    parser.add_argument("--nvidia-smi", default="nvidia-smi")
    parser.add_argument("--cooldown-max-temperature-c", type=float, default=65.0)
    parser.add_argument(
        "--cooldown-max-power-w",
        type=float,
        default=1000000.0,
        help="profile/site-specific power ceiling; the large default disables power gating",
    )
    parser.add_argument("--cooldown-max-gpu-util-pct", type=float, default=1.0)
    parser.add_argument("--cooldown-max-memory-util-pct", type=float, default=5.0)
    parser.add_argument("--cooldown-consecutive-samples", type=int, default=3)
    parser.add_argument("--cooldown-poll-seconds", type=float, default=1.0)
    parser.add_argument("--max-cooldown-seconds", type=float, default=180.0)
    parser.add_argument("--tag", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--output", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--calibration-csv", default="")
    parser.add_argument("--design-csv", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    defaults = dict(PROFILE_DEFAULTS[args.target_profile])
    if args.active_sm <= 0:
        args.active_sm = int(PROFILES[args.target_profile]["full_sm"])
    if not args.output:
        args.output = (
            f"results/raw/{args.target_profile}_component_dynamic_attribution_"
            f"{args.tag}.csv"
        )
    if not args.manifest:
        args.manifest = (
            f"results/summary/{args.target_profile}_component_dynamic_attribution_"
            f"{args.tag}_manifest.csv"
        )
    if not args.calibration_csv:
        args.calibration_csv = (
            f"results/raw/{args.target_profile}_component_dynamic_attribution_"
            f"{args.tag}_calibration.csv"
        )
    if not args.design_csv:
        args.design_csv = (
            f"results/summary/{args.target_profile}_component_dynamic_attribution_"
            f"{args.tag}_design.csv"
        )

    if args.gpu_id < 0 or args.active_sm <= 0:
        parser.error("GPU id and active SM must be valid positive coordinates")
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    if args.blocks_per_sm > int(PROFILES[args.target_profile]["max_blocks_per_sm"]):
        parser.error("blocks/SM exceeds profile capacity")
    if args.repeats <= 0 or args.baseline_seconds <= 0.0:
        parser.error("repeats and baseline duration must be positive")
    if args.control_min_seconds <= 0.0:
        parser.error("control minimum duration must be positive")
    if args.idle_measure_seconds <= 0.0 or args.idle_settle_seconds < 0.0:
        parser.error("idle measurement must be positive and settle non-negative")
    if args.cooldown_consecutive_samples <= 0 or args.max_cooldown_seconds <= 0.0:
        parser.error("cooldown sample count and timeout must be positive")

    try:
        component_values = parse_components(args.components)
        reuse_factors = parse_positive_ints(args.reuse_factors)
        load_repeats = parse_positive_ints(args.load_repeats)
        durations = parse_positive_floats(args.durations)
        if args.blocks_per_sm_values and args.blocks_per_sm > 0:
            raise ValueError(
                "--blocks-per-sm and --blocks-per-sm-values are mutually exclusive"
            )
        if args.blocks_per_sm_values:
            blocks_per_sm_values = parse_positive_ints(args.blocks_per_sm_values)
        elif args.blocks_per_sm > 0:
            blocks_per_sm_values = [args.blocks_per_sm]
        else:
            blocks_per_sm_values = list(
                PROFILE_BLOCKS_PER_SM_VALUES[args.target_profile]
            )
    except ValueError as exc:
        parser.error(str(exc))

    profile_max_blocks = int(PROFILES[args.target_profile]["max_blocks_per_sm"])
    invalid_blocks = [
        value
        for value in blocks_per_sm_values
        if value not in {1, 2, 4, 8, 16, 32} or value > profile_max_blocks
    ]
    if invalid_blocks:
        parser.error(
            "blocks/SM values exceed the profile or supported coordinate set: "
            + ",".join(str(value) for value in invalid_blocks)
        )

    coordinates, design_rows = build_coordinates(
        profile_name=args.target_profile,
        active_sm=args.active_sm,
        blocks_per_sm_values=blocks_per_sm_values,
        components=component_values,
        reuse_factors=reuse_factors,
        load_repeats=load_repeats,
        durations=durations,
        defaults=defaults,
    )
    for row in design_rows:
        row["calibration_policy"] = args.calibration_policy
    invalid = [row for row in design_rows if not row["valid"]]
    if invalid:
        parser.error(
            "invalid design coordinates: "
            + "; ".join(f"{row['coordinate_id']}={row['reason']}" for row in invalid)
        )

    output_paths = [
        Path(args.output),
        Path(args.manifest),
        Path(args.calibration_csv),
        Path(args.design_csv),
    ]
    existing = [path for path in output_paths if path.exists()]
    if existing and not (args.overwrite or args.resume):
        parser.error(
            "refusing to overwrite an existing package; use --resume or --overwrite: "
            + ", ".join(str(path) for path in existing)
        )
    if args.overwrite:
        for path in existing:
            path.unlink()
    if args.resume:
        try:
            assert_raw_resume_schema(Path(args.output))
            assert_csv_header(Path(args.manifest), MANIFEST_FIELDS)
            assert_csv_header(Path(args.calibration_csv), CALIBRATION_FIELDS)
        except ValueError as exc:
            parser.error(str(exc))
    try:
        validate_or_write_design(
            Path(args.design_csv), design_rows, resume=args.resume
        )
    except ValueError as exc:
        parser.error(str(exc))

    command_count = len(coordinates) * args.repeats * 4
    print(
        f"protocol={PROTOCOL_REVISION} profile={args.target_profile} "
        f"active_SM={args.active_sm} B={','.join(map(str, blocks_per_sm_values))} "
        f"coordinates={len(coordinates)} repeats={args.repeats} "
        f"energy_commands={command_count}",
        flush=True,
    )
    print(f"wrote design: {args.design_csv}", flush=True)
    if not args.execute:
        print("dry run only; pass --execute to calibrate and measure", flush=True)
        return 0
    if not Path(args.binary).is_file():
        parser.error(f"binary does not exist: {args.binary}")

    binary_hash = binary_sha256(args.binary)
    args.binary_sha256 = binary_hash
    run_quiescence(args, "pre_calibration")

    resumed_calibration = (
        load_complete_calibration(args, coordinates, blocks_per_sm_values)
        if args.resume
        else None
    )
    if resumed_calibration is not None:
        baseline_iters_by_blocks, calibrated = resumed_calibration
        print(
            f"resume: reused calibration for {len(calibrated)} coordinates",
            flush=True,
        )
    else:
        baseline_iters_by_blocks = {}
        for blocks_per_sm in blocks_per_sm_values:
            baseline_calibration, baseline_command = calibrate_mode(
                args,
                mode="clocked_empty",
                w_sm_kib=64,
                blocks_per_sm=blocks_per_sm,
                reuse_factor=1,
                load_repeat=1,
                seconds=args.baseline_seconds,
            )
            baseline_iters_by_blocks[blocks_per_sm] = baseline_calibration.target_iters
            append_csv(
                Path(args.calibration_csv),
                CALIBRATION_FIELDS,
                {
                    "protocol_revision": PROTOCOL_REVISION,
                    "record_type": "baseline_calibration",
                    "profile": args.target_profile,
                    "component": "baseline",
                    "coordinate_id": f"baseline_B{blocks_per_sm}",
                    "calibration_policy": args.calibration_policy,
                    "binary_sha256": binary_hash,
                    "target_duration_s": args.baseline_seconds,
                    "blocks_per_SM": blocks_per_sm,
                    "treatment_mode": "clocked_empty",
                    "treatment_W_SM_KiB": 64,
                    "treatment_trial_iters": baseline_calibration.trial_iters,
                    "treatment_trial_elapsed_s": baseline_calibration.trial_elapsed_s,
                    "treatment_calibrated_iters": baseline_calibration.target_iters,
                    "control_min_calibrated_iters": baseline_calibration.target_iters,
                    "resolved_iters": baseline_calibration.target_iters,
                    "predicted_treatment_s": args.baseline_seconds,
                    "predicted_control_s": args.baseline_seconds,
                    "treatment_stretch": 1.0,
                    "status": "accepted",
                    "treatment_calibration_command": " ".join(baseline_command),
                },
            )
        calibrated = []
        for index, coordinate in enumerate(coordinates, start=1):
            print(
                f"calibrate [{index}/{len(coordinates)}] {coordinate.coordinate_id}",
                flush=True,
            )
            calibrated.append(calibrate_pair(args, coordinate))
        calibrated = apply_calibration_policy(args, calibrated)

    if args.pre_energy_cooldown_seconds > 0.0:
        time.sleep(args.pre_energy_cooldown_seconds)
    run_quiescence(args, "pre_energy")

    completed_identities, max_attempt_by_identity = (
        load_completed_pairs(Path(args.manifest), binary_hash=binary_hash)
        if args.resume
        else (set(), {})
    )
    total_pairs = len(calibrated) * args.repeats
    completed_pairs = 0
    for repeat in range(args.repeats):
        offset = repeat % len(calibrated)
        ordered = calibrated[offset:] + calibrated[:offset]
        for ordered_index, pair in enumerate(ordered):
            original_index = (offset + ordered_index) % len(calibrated)
            coordinate = pair.coordinate
            identity = (coordinate.coordinate_id, repeat)
            if identity in completed_identities:
                completed_pairs += 1
                print(
                    f"pair [{completed_pairs}/{total_pairs}] "
                    f"{coordinate.coordinate_id}_repeat{repeat} resume=complete_skip",
                    flush=True,
                )
                continue
            roles, execution_order = pair_order(repeat, original_index)
            pair_attempt = max_attempt_by_identity.get(identity, -1) + 1
            pair_base = f"{coordinate.coordinate_id}_repeat{repeat}"
            pair_id = (
                pair_base if pair_attempt == 0 else f"{pair_base}_attempt{pair_attempt}"
            )
            completed_pairs += 1
            print(
                f"pair [{completed_pairs}/{total_pairs}] {pair_id} "
                f"order={execution_order}",
                flush=True,
            )
            pre_pair_state: GpuState | None = None
            cooldown_wait_seconds = 0.0
            if args.pair_cooldown:
                pre_pair_state, cooldown_wait_seconds = wait_for_gpu_cooldown(args)
                print(
                    f"  pre-pair cooldown={cooldown_wait_seconds:.1f}s "
                    f"temp={pre_pair_state.temperature_c:.1f}C "
                    f"power={pre_pair_state.power_w:.1f}W "
                    f"gpu_util={pre_pair_state.gpu_util_pct:.1f}% "
                    f"memory_util={pre_pair_state.memory_util_pct:.1f}%",
                    flush=True,
                )
            execute_one(
                args,
                coordinate=coordinate,
                pair_id=pair_id,
                pair_attempt=pair_attempt,
                repeat=repeat,
                role="baseline_before",
                sequence_index=0,
                execution_order=execution_order,
                mode="clocked_empty",
                w_sm_kib=64,
                reuse_factor=1,
                load_repeat=1,
                iters=baseline_iters_by_blocks[coordinate.blocks_per_sm],
                binary_sha256=binary_hash,
                calibration_policy=pair.calibration_policy,
                grid_anchor_factor=pair.grid_anchor_factor,
                grid_anchor_blocks_per_sm=pair.grid_anchor_blocks_per_sm,
                grid_work_units=pair.grid_work_units,
                pre_pair_state=pre_pair_state,
                cooldown_wait_seconds=cooldown_wait_seconds,
            )
            if args.inter_command_delay_seconds > 0.0:
                time.sleep(args.inter_command_delay_seconds)
            for sequence_offset, role in enumerate(roles, start=1):
                if role == "control":
                    mode = coordinate.control_mode
                    w_sm_kib = coordinate.control_w_sm_kib
                else:
                    mode = coordinate.treatment_mode
                    w_sm_kib = coordinate.treatment_w_sm_kib
                execute_one(
                    args,
                    coordinate=coordinate,
                    pair_id=pair_id,
                    pair_attempt=pair_attempt,
                    repeat=repeat,
                    role=role,
                    sequence_index=sequence_offset,
                    execution_order=execution_order,
                    mode=mode,
                    w_sm_kib=w_sm_kib,
                    reuse_factor=coordinate.reuse_factor,
                    load_repeat=coordinate.load_repeat,
                    iters=pair.resolved_iters,
                    binary_sha256=binary_hash,
                    calibration_policy=pair.calibration_policy,
                    grid_anchor_factor=pair.grid_anchor_factor,
                    grid_anchor_blocks_per_sm=pair.grid_anchor_blocks_per_sm,
                    grid_work_units=pair.grid_work_units,
                    pre_pair_state=pre_pair_state,
                    cooldown_wait_seconds=cooldown_wait_seconds,
                )
                if args.inter_command_delay_seconds > 0.0:
                    time.sleep(args.inter_command_delay_seconds)
            execute_one(
                args,
                coordinate=coordinate,
                pair_id=pair_id,
                pair_attempt=pair_attempt,
                repeat=repeat,
                role="baseline_after",
                sequence_index=3,
                execution_order=execution_order,
                mode="clocked_empty",
                w_sm_kib=64,
                reuse_factor=1,
                load_repeat=1,
                iters=baseline_iters_by_blocks[coordinate.blocks_per_sm],
                binary_sha256=binary_hash,
                calibration_policy=pair.calibration_policy,
                grid_anchor_factor=pair.grid_anchor_factor,
                grid_anchor_blocks_per_sm=pair.grid_anchor_blocks_per_sm,
                grid_work_units=pair.grid_work_units,
                pre_pair_state=pre_pair_state,
                cooldown_wait_seconds=cooldown_wait_seconds,
            )
            if args.inter_command_delay_seconds > 0.0:
                time.sleep(args.inter_command_delay_seconds)

    print(f"wrote raw energy: {args.output}")
    print(f"wrote explicit MI-ATC manifest: {args.manifest}")
    print(f"wrote calibration evidence: {args.calibration_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
