#!/usr/bin/env python3
"""Run duration-calibrated component regression sweeps.

Unlike the archived legacy pair runner, this runner does not reuse a reference
ITER across modes. Each command omits --iters so the benchmark binary calibrates
that mode toward the requested --seconds. The output is intended for
elapsed-aware finalplan sweeps, not simple paired differences.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
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
        help="Use fixed ITER for every command; 0 keeps per-mode duration calibration.",
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run commands. Without this flag only the matrix CSV is written.",
    )
    args = parser.parse_args()

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
                                                else "per_mode_duration_calibrated"
                                            ),
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

    index = 0
    total = len(commands) * args.repeats
    for repeat in range(args.repeats):
        for item in rotated(commands, repeat):
            index += 1
            print(f"[{index}/{total}] {' '.join(item['cmd'])}", flush=True)
            subprocess.run(item["cmd"], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
