#!/usr/bin/env python3
"""Run component regression sweeps with optional Tensor pair-locked ITER.

Memory paths retain per-mode duration calibration. Tensor finalplan runs can
calibrate reg_mma for the treatment target and reg_operand_only for a minimum
control duration, then apply the larger ITER to both modes. This keeps the work
count comparable without allowing a high-RF control to fall below the energy
counter/idle-subtraction noise floor.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_sweep import (
    DEFAULT_PROFILE,
    MODES,
    PROFILES,
    W_SM_KIB,
    classify,
    gpu_list_for_count,
    mode_allowed,
    parse_int_list,
    parse_str_list,
)


DEFAULT_MODES = [
    "empty",
    "clocked_empty",
    "addr_only",
    "reg_operand_only",
    "reg_mma",
    "global_l1_load_only",
    "global_addr_only",
    "shared_scalar_load_only",
    "shared_load_only",
    "shared_mma",
    "l2_load_only",
    "l2_cg_load_only",
    "l2_mma",
    "dram_load_only",
    "dram_cg_load_only",
    "dram_mma",
    "store_only",
]

TENSOR_PAIR_MODES = {"reg_operand_only", "reg_mma"}
ATOMIC_MODE_PAIRS = {
    frozenset({"reg_operand_only", "reg_mma"}): ("reg_operand_only", "reg_mma"),
    frozenset({"clocked_empty", "shared_scalar_load_only"}): (
        "clocked_empty",
        "shared_scalar_load_only",
    ),
    frozenset({"global_addr_only", "global_l1_load_only"}): (
        "global_addr_only",
        "global_l1_load_only",
    ),
    frozenset({"global_addr_only", "l2_cg_load_only"}): (
        "global_addr_only",
        "l2_cg_load_only",
    ),
    frozenset({"global_addr_only", "dram_cg_load_only"}): (
        "global_addr_only",
        "dram_cg_load_only",
    ),
}


def parse_uint64_list(value: str, default: list[int]) -> list[int]:
    if not value:
        return default
    out = [int(item) for item in value.split(",") if item]
    if any(item <= 0 for item in out):
        raise ValueError("factor values must be positive")
    return out


def build_command(
    args: argparse.Namespace,
    *,
    mode: str,
    gpu_list: str,
    w_sm_kib: int,
    blocks_per_sm: int,
    active_sm: int,
    reuse_factor: int,
    load_repeat: int,
    store_repeat: int,
) -> list[str]:
    command = [
        args.binary,
        "--gpu-list",
        gpu_list,
        "--mode",
        mode,
        "--w-sm-kib",
        str(w_sm_kib),
        "--blocks-per-sm",
        str(blocks_per_sm),
        "--target-profile",
        args.target_profile,
        "--active-sm",
        str(active_sm),
        "--seconds",
        str(args.seconds),
        "--repeats",
        "1",
        "--reuse-factor",
        str(reuse_factor),
        "--load-repeat",
        str(load_repeat),
        "--store-repeat",
        str(store_repeat),
        "--output",
        args.output,
        "--verify-smid",
        str(args.verify_smid),
    ]
    if args.iters:
        command.extend(["--iters", str(args.iters)])
    return command


def rotated(values: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    if not values:
        return values
    offset %= len(values)
    return values[offset:] + values[:offset]


def tensor_pair_key(item: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(item["target_profile"]),
        str(item["gpu_list"]),
        str(item["W_SM_KiB"]),
        str(item["blocks_per_SM"]),
        str(item["active_SM"]),
        str(item["reuse_factor"]),
        str(item["load_repeat"]),
        str(item["store_repeat"]),
    )


def atomic_pair_groups(
    commands: list[dict[str, Any]],
    *,
    control_mode: str,
    treatment_mode: str,
) -> list[list[dict[str, Any]]]:
    """Keep each known control immediately before its treatment.

    Rotating a flat command list by one item can split a pair across the two
    ends of a repeat. Rotate complete coordinate groups instead so thermal/run
    order changes across repeats without separating matched work.
    """

    expected_modes = {control_mode, treatment_mode}
    ordered_keys: list[tuple[str, ...]] = []
    grouped: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    for item in commands:
        if item["mode"] not in expected_modes:
            raise ValueError(
                "Atomic paired execution received an unexpected mode: "
                f"{item['mode']}"
            )
        key = tensor_pair_key(item)
        if key not in grouped:
            ordered_keys.append(key)
            grouped[key] = {}
        grouped[key][str(item["mode"])] = item

    pairs: list[list[dict[str, Any]]] = []
    for key in ordered_keys:
        by_mode = grouped[key]
        missing = sorted(expected_modes - set(by_mode))
        if missing:
            raise ValueError(
                "Atomic paired execution is missing modes "
                f"{','.join(missing)} for key={key}"
            )
        pairs.append([by_mode[control_mode], by_mode[treatment_mode]])
    return pairs


def tensor_pair_groups(
    commands: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    return atomic_pair_groups(
        commands,
        control_mode="reg_operand_only",
        treatment_mode="reg_mma",
    )


def parse_calibrated_iters(output: str) -> int:
    match = re.search(r"(?:^|\n)CALIBRATED_ITERS=(\d+)(?:\n|$)", output)
    if not match:
        raise ValueError("calibration output is missing CALIBRATED_ITERS=<int>")
    value = int(match.group(1))
    if value <= 0:
        raise ValueError("calibrated ITER must be positive")
    return value


def replace_command_option(command: list[str], option: str, value: str) -> list[str]:
    """Return a command with one existing `--option value` pair replaced."""

    updated = list(command)
    try:
        index = updated.index(option)
    except ValueError as exc:
        raise ValueError(f"calibration command is missing {option}") from exc
    if index + 1 >= len(updated):
        raise ValueError(f"calibration command has no value after {option}")
    updated[index + 1] = value
    return updated


def command_option_value(command: list[str], option: str) -> str:
    try:
        index = command.index(option)
    except ValueError:
        return ""
    return command[index + 1] if index + 1 < len(command) else ""


def write_pair_calibration_manifest(
    path: Path, rows: list[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_matrix_with_resolved_iters(
    matrix_path: Path, resolved: dict[tuple[str, ...], int]
) -> None:
    with matrix_path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if "resolved_iters" not in fieldnames:
        fieldnames.append("resolved_iters")
    for row in rows:
        if row.get("mode") not in TENSOR_PAIR_MODES or row.get("valid") != "True":
            continue
        key = tensor_pair_key(row)
        value = resolved.get(key)
        if value is None:
            continue
        row["resolved_iters"] = str(value)
        row["measurement_policy"] = "tensor_pair_locked_iters"
        row["command"] = f"{row['command']} --iters {value}"

    with matrix_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def resolve_tensor_pair_iters(
    commands: list[dict[str, Any]],
    manifest_path: Path,
    *,
    control_min_seconds: float = 0.0,
) -> tuple[int, dict[tuple[str, ...], int]]:
    groups: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    for item in commands:
        if item["mode"] not in TENSOR_PAIR_MODES:
            continue
        groups.setdefault(tensor_pair_key(item), {})[str(item["mode"])] = item

    rows: list[dict[str, Any]] = []
    resolved: dict[tuple[str, ...], int] = {}
    for key, by_mode in sorted(groups.items()):
        missing = sorted(TENSOR_PAIR_MODES - set(by_mode))
        if missing:
            print(
                "tensor pair-lock requires both reg_mma and reg_operand_only; "
                f"missing={','.join(missing)} key={key}",
                file=sys.stderr,
            )
            return 2, resolved

        treatment = by_mode["reg_mma"]
        control = by_mode["reg_operand_only"]
        treatment_calibration_command = [*treatment["cmd"], "--calibrate-only"]
        proc = subprocess.run(
            treatment_calibration_command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode != 0:
            print(
                "Tensor treatment calibration failed before energy collection: "
                f"key={key} return_code={proc.returncode}",
                file=sys.stderr,
            )
            if proc.stdout:
                print(proc.stdout.rstrip(), file=sys.stderr)
            return proc.returncode, resolved
        try:
            treatment_iters = parse_calibrated_iters(proc.stdout)
        except ValueError as exc:
            print(f"Tensor treatment calibration failed: {exc}; key={key}", file=sys.stderr)
            if proc.stdout:
                print(proc.stdout.rstrip(), file=sys.stderr)
            return 2, resolved

        control_iters = 0
        control_calibration_command: list[str] = []
        if control_min_seconds > 0.0:
            try:
                control_calibration_command = replace_command_option(
                    control["cmd"], "--seconds", str(control_min_seconds)
                )
            except ValueError as exc:
                print(f"Tensor control calibration failed: {exc}; key={key}", file=sys.stderr)
                return 2, resolved
            control_calibration_command.append("--calibrate-only")
            proc = subprocess.run(
                control_calibration_command,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if proc.returncode != 0:
                print(
                    "Tensor control-min calibration failed before energy collection: "
                    f"key={key} return_code={proc.returncode}",
                    file=sys.stderr,
                )
                if proc.stdout:
                    print(proc.stdout.rstrip(), file=sys.stderr)
                return proc.returncode, resolved
            try:
                control_iters = parse_calibrated_iters(proc.stdout)
            except ValueError as exc:
                print(f"Tensor control-min calibration failed: {exc}; key={key}", file=sys.stderr)
                if proc.stdout:
                    print(proc.stdout.rstrip(), file=sys.stderr)
                return 2, resolved

        iters = max(treatment_iters, control_iters)
        resolved[key] = iters
        for item in by_mode.values():
            item["cmd"].extend(["--iters", str(iters)])
            item["resolved_iters"] = iters
            item["measurement_policy"] = "tensor_pair_locked_iters"
        rows.append(
            {
                "target_profile": key[0],
                "gpu_list": key[1],
                "W_SM_KiB": key[2],
                "blocks_per_SM": key[3],
                "active_SM": key[4],
                "reuse_factor": key[5],
                "load_repeat": key[6],
                "store_repeat": key[7],
                "calibration_source_mode": "reg_mma",
                "treatment_target_seconds": command_option_value(
                    treatment["cmd"], "--seconds"
                ),
                "control_min_seconds": control_min_seconds,
                "treatment_calibrated_iters": treatment_iters,
                "control_min_calibrated_iters": control_iters if control_min_seconds > 0.0 else "",
                "resolved_iters": iters,
                "resolution_policy": (
                    "max_treatment_and_control_min_iters"
                    if control_min_seconds > 0.0
                    else "treatment_iters_only"
                ),
                "status": "pair_locked",
                "calibration_command": " ".join(treatment_calibration_command),
                "treatment_calibration_command": " ".join(
                    treatment_calibration_command
                ),
                "control_calibration_command": " ".join(
                    control_calibration_command
                ),
            }
        )
        print(
            "Tensor pair calibration: "
            f"W={key[2]}KiB B={key[3]} SM={key[4]} RF={key[5]} "
            f"treatment_ITER={treatment_iters} control_min_ITER={control_iters} "
            f"resolved_ITER={iters}",
            flush=True,
        )

    write_pair_calibration_manifest(manifest_path, rows)
    return 0, resolved


def run_self_test() -> None:
    import tempfile
    from unittest import mock

    a100 = PROFILES["a100"]
    below_tile = classify(16, 32, a100)
    assert below_tile["below_logical_tile"]
    assert not mode_allowed("global_addr_only", below_tile)
    assert not mode_allowed("global_l1_load_only", below_tile)
    assert mode_allowed("reg_operand_only", below_tile)

    valid_tile = classify(32, 32, a100)
    assert mode_allowed("global_addr_only", valid_tile)
    assert mode_allowed("global_l1_load_only", valid_tile)
    assert parse_calibrated_iters("ITER=7\nCALIBRATED_ITERS=123\n") == 123
    try:
        parse_calibrated_iters("ITER=123\n")
    except ValueError:
        pass
    else:
        raise AssertionError("missing CALIBRATED_ITERS marker was accepted")

    base = {
        "target_profile": "a100",
        "gpu_list": "0",
        "W_SM_KiB": 2048,
        "blocks_per_SM": 16,
        "active_SM": 108,
        "reuse_factor": 4,
        "load_repeat": 1,
        "store_repeat": 1,
    }
    pair_commands = [
        {**base, "mode": "reg_operand_only", "cmd": ["fake", "--mode", "reg_operand_only"]},
        {**base, "mode": "reg_mma", "cmd": ["fake", "--mode", "reg_mma"]},
    ]
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="ITER=456\nCALIBRATED_ITERS=456\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = Path(tmpdir) / "pair_calibration.csv"
        with mock.patch.object(subprocess, "run", return_value=completed) as run_mock:
            rc, resolved = resolve_tensor_pair_iters(pair_commands, manifest)
        assert rc == 0
        assert list(resolved.values()) == [456]
        assert manifest.exists()
        assert run_mock.call_count == 1
    assert all(item["cmd"][-2:] == ["--iters", "456"] for item in pair_commands)

    control_floor_commands = [
        {**base, "mode": "reg_operand_only", "cmd": ["fake", "--seconds", "20"]},
        {**base, "mode": "reg_mma", "cmd": ["fake", "--seconds", "20"]},
    ]
    treatment_completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="CALIBRATED_ITERS=456\n"
    )
    control_completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="CALIBRATED_ITERS=800\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = Path(tmpdir) / "pair_control_floor_calibration.csv"
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=[treatment_completed, control_completed],
        ) as run_mock:
            rc, resolved = resolve_tensor_pair_iters(
                control_floor_commands,
                manifest,
                control_min_seconds=2.0,
            )
        assert rc == 0
        assert list(resolved.values()) == [800]
        assert run_mock.call_count == 2
        with manifest.open(newline="") as f:
            manifest_rows = list(csv.DictReader(f))
        assert manifest_rows[0]["treatment_calibrated_iters"] == "456"
        assert manifest_rows[0]["control_min_calibrated_iters"] == "800"
        assert manifest_rows[0]["resolved_iters"] == "800"
        assert manifest_rows[0]["control_min_seconds"] == "2.0"
        assert (
            manifest_rows[0]["resolution_policy"]
            == "max_treatment_and_control_min_iters"
        )
    assert all(
        item["cmd"][-2:] == ["--iters", "800"]
        for item in control_floor_commands
    )

    second_key = {**base, "reuse_factor": 8}
    ordering_commands = [
        {**base, "mode": "reg_operand_only", "cmd": ["control-rf4"]},
        {**base, "mode": "reg_mma", "cmd": ["treatment-rf4"]},
        {**second_key, "mode": "reg_operand_only", "cmd": ["control-rf8"]},
        {**second_key, "mode": "reg_mma", "cmd": ["treatment-rf8"]},
    ]
    ordered_pairs = tensor_pair_groups(ordering_commands)
    assert [item["mode"] for item in ordered_pairs[0]] == [
        "reg_operand_only",
        "reg_mma",
    ]
    rotated_pairs = rotated(ordered_pairs, 1)
    flattened = [item["mode"] for pair in rotated_pairs for item in pair]
    assert flattened == [
        "reg_operand_only",
        "reg_mma",
        "reg_operand_only",
        "reg_mma",
    ]
    l2_commands = [
        {**base, "mode": "global_addr_only", "cmd": ["control-l2-rf4"]},
        {**base, "mode": "l2_cg_load_only", "cmd": ["treatment-l2-rf4"]},
        {**second_key, "mode": "global_addr_only", "cmd": ["control-l2-rf8"]},
        {**second_key, "mode": "l2_cg_load_only", "cmd": ["treatment-l2-rf8"]},
    ]
    l2_pairs = atomic_pair_groups(
        l2_commands,
        control_mode="global_addr_only",
        treatment_mode="l2_cg_load_only",
    )
    assert [item["mode"] for item in l2_pairs[0]] == [
        "global_addr_only",
        "l2_cg_load_only",
    ]
    print("component regression sweep feasibility self-test passed")


def binary_dry_run_preflight(commands: list[dict[str, Any]]) -> int:
    """Check every unique mode/W/B/SM/GPU coordinate before measuring energy."""

    seen: set[tuple[str, int, int, int, str]] = set()
    unique: list[dict[str, Any]] = []
    for item in commands:
        key = (
            str(item["mode"]),
            int(item["W_SM_KiB"]),
            int(item["blocks_per_SM"]),
            int(item["active_SM"]),
            str(item["gpu_list"]),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"binary dry-run preflight: {len(unique)} unique coordinates", flush=True)
    for item in unique:
        proc = subprocess.run(
            [*item["cmd"], "--dry-run"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode != 0:
            print(
                "binary dry-run rejected a matrix row before energy collection: "
                f"mode={item['mode']} W_SM_KiB={item['W_SM_KiB']} "
                f"blocks_per_SM={item['blocks_per_SM']} active_SM={item['active_SM']} "
                f"return_code={proc.returncode}",
                file=sys.stderr,
            )
            if proc.stdout:
                print(proc.stdout.rstrip(), file=sys.stderr)
            return proc.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument(
        "--output", default="results/raw/component_regression_raw.csv"
    )
    parser.add_argument(
        "--matrix-csv", default="results/raw/component_regression_matrix.csv"
    )
    parser.add_argument("--target-profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--max-active-gpus", type=int, default=1)
    parser.add_argument("--modes", default=",".join(DEFAULT_MODES))
    parser.add_argument("--w-sm-kib-values", default="")
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--active-sm-values", default="")
    parser.add_argument("--reuse-factors", default="1,2,4,8")
    parser.add_argument("--load-repeats", default="1,2,4,8")
    parser.add_argument("--store-repeats", default="1,2,4,8")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument(
        "--iters",
        type=int,
        default=0,
        help=(
            "Use fixed ITER for every command; 0 uses per-mode calibration unless "
            "--tensor-pair-lock-iters is enabled."
        ),
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument(
        "--tensor-pair-lock-iters",
        action="store_true",
        help=(
            "Calibrate reg_mma once per Tensor coordinate and run both Tensor "
            "treatment/control with the same ITER."
        ),
    )
    parser.add_argument(
        "--tensor-pair-control-min-seconds",
        type=float,
        default=0.0,
        help=(
            "When pair-locking Tensor ITER, also calibrate reg_operand_only for "
            "at least this duration and use max(treatment ITER, control-min ITER) "
            "for both modes. Use 2 s or longer for final energy runs."
        ),
    )
    parser.add_argument(
        "--pair-calibration-csv",
        default="",
        help="Tensor pair calibration manifest path; defaults beside --matrix-csv.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run commands. Without this flag only the matrix CSV is written.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Check that Python feasibility filtering matches binary memory-tile policy.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    if args.tensor_pair_control_min_seconds < 0.0:
        raise ValueError("--tensor-pair-control-min-seconds must be non-negative")
    if args.tensor_pair_control_min_seconds > 0.0 and not args.tensor_pair_lock_iters:
        raise ValueError(
            "--tensor-pair-control-min-seconds requires --tensor-pair-lock-iters"
        )

    profile = PROFILES[args.target_profile]
    gpu_ids = parse_int_list(args.gpu_ids, [0])
    modes = parse_str_list(args.modes, DEFAULT_MODES)
    unknown_modes = sorted(set(modes) - set(MODES))
    if unknown_modes:
        raise ValueError(f"unknown modes: {','.join(unknown_modes)}")

    w_values = parse_int_list(args.w_sm_kib_values, W_SM_KIB)
    b_default = [1, 2, 4, 8, 16, 32]
    b_default = [b for b in b_default if b <= profile["max_blocks_per_sm"]]
    b_values = parse_int_list(args.blocks_per_sm_values, b_default)
    active_sm_values = parse_int_list(args.active_sm_values, profile["active_sm"])
    reuse_factors = parse_uint64_list(args.reuse_factors, [1, 2, 4, 8])
    load_repeats = parse_uint64_list(args.load_repeats, [1, 2, 4, 8])
    store_repeats = parse_uint64_list(args.store_repeats, [1, 2, 4, 8])
    n_gpu_values = list(range(1, min(args.max_active_gpus, len(gpu_ids)) + 1))

    matrix_path = Path(args.matrix_csv)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)

    commands: list[dict[str, Any]] = []
    with matrix_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "mode",
                "target_profile",
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "reuse_factor",
                "load_repeat",
                "store_repeat",
                "n_gpu_active",
                "gpu_list",
                "valid",
                "regime",
                "reason",
                "measurement_policy",
                "resolved_iters",
                "command",
            ],
            lineterminator="\n",
        )
        writer.writeheader()

        for w_sm_kib in w_values:
            for blocks_per_sm in b_values:
                info = classify(w_sm_kib, blocks_per_sm, profile)
                for active_sm in active_sm_values:
                    for n_gpu in n_gpu_values:
                        gpu_list = gpu_list_for_count(gpu_ids, n_gpu)
                        for reuse_factor in reuse_factors:
                            for load_repeat in load_repeats:
                                for store_repeat in store_repeats:
                                    for mode in modes:
                                        valid = mode_allowed(mode, info)
                                        cmd = build_command(
                                            args,
                                            mode=mode,
                                            gpu_list=gpu_list,
                                            w_sm_kib=w_sm_kib,
                                            blocks_per_sm=blocks_per_sm,
                                            active_sm=active_sm,
                                            reuse_factor=reuse_factor,
                                            load_repeat=load_repeat,
                                            store_repeat=store_repeat,
                                        )
                                        row = {
                                            "mode": mode,
                                            "target_profile": args.target_profile,
                                            "W_SM_KiB": w_sm_kib,
                                            "blocks_per_SM": blocks_per_sm,
                                            "active_SM": active_sm,
                                            "reuse_factor": reuse_factor,
                                            "load_repeat": load_repeat,
                                            "store_repeat": store_repeat,
                                            "n_gpu_active": n_gpu,
                                            "gpu_list": gpu_list,
                                            "valid": valid,
                                            "regime": info["regime"],
                                            "reason": (
                                                info["reason"]
                                                if valid
                                                else f"skipped:{info['reason']}"
                                            ),
                                            "measurement_policy": (
                                                "fixed_iters_regression"
                                                if args.iters
                                                else "tensor_pair_locked_pending"
                                                if args.tensor_pair_lock_iters
                                                and mode in TENSOR_PAIR_MODES
                                                else "per_mode_duration_calibrated"
                                            ),
                                            "resolved_iters": str(args.iters) if args.iters else "",
                                            "command": " ".join(cmd),
                                        }
                                        writer.writerow(row)
                                        if valid:
                                            commands.append({"cmd": cmd, **row})

    print(f"wrote matrix: {matrix_path}")
    print(f"valid commands per repeat: {len(commands)}")
    print(f"total commands: {len(commands) * args.repeats}")
    if not args.execute:
        print("dry run only; pass --execute to run the commands")
        return 0

    if not commands:
        print(
            "no valid commands remain after feasibility filtering; inspect the matrix CSV",
            file=sys.stderr,
        )
        return 2

    preflight_rc = binary_dry_run_preflight(commands)
    if preflight_rc != 0:
        return preflight_rc

    if args.tensor_pair_lock_iters and not args.iters:
        calibration_path = (
            Path(args.pair_calibration_csv)
            if args.pair_calibration_csv
            else matrix_path.with_name(
                matrix_path.stem + "_tensor_pair_calibration.csv"
            )
        )
        calibration_rc, resolved = resolve_tensor_pair_iters(
            commands,
            calibration_path,
            control_min_seconds=args.tensor_pair_control_min_seconds,
        )
        if calibration_rc != 0:
            return calibration_rc
        update_matrix_with_resolved_iters(matrix_path, resolved)

    atomic_pairs: list[list[dict[str, Any]]] = []
    mode_pair = ATOMIC_MODE_PAIRS.get(frozenset(modes)) if len(modes) == 2 else None
    if mode_pair:
        try:
            atomic_pairs = atomic_pair_groups(
                commands,
                control_mode=mode_pair[0],
                treatment_mode=mode_pair[1],
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    index = 0
    total = len(commands) * args.repeats
    for repeat in range(args.repeats):
        if atomic_pairs:
            repeat_commands = [
                item for pair in rotated(atomic_pairs, repeat) for item in pair
            ]
        else:
            repeat_commands = rotated(commands, repeat)
        for item in repeat_commands:
            index += 1
            print(f"[{index}/{total}] {' '.join(item['cmd'])}", flush=True)
            proc = subprocess.run(item["cmd"], check=False)
            if proc.returncode != 0:
                print(
                    "energy command failed after binary dry-run preflight: "
                    f"mode={item['mode']} W_SM_KiB={item['W_SM_KiB']} "
                    f"blocks_per_SM={item['blocks_per_SM']} "
                    f"return_code={proc.returncode}",
                    file=sys.stderr,
                )
                return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
