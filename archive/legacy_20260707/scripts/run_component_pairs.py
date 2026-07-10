#!/usr/bin/env python3
"""Run fixed-ITER component-decomposition pairs.

The normal sweep runner is mode-centric. This runner is pair-centric: it
calibrates a reference mode for each coordinate and reuses that ITER for the
paired control modes so paired differences have a stable denominator.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path
from typing import Any

from run_sweep import (
    DEFAULT_PROFILE,
    PROFILES,
    W_SM_KIB,
    classify,
    gpu_list_for_count,
    mode_allowed,
    parse_int_list,
    parse_str_list,
)


GROUPS: dict[str, dict[str, Any]] = {
    "register": {
        "reference": "reg_mma",
        "modes": ["empty", "reg_fragment_only", "reg_operand_only", "reg_mma"],
    },
    "shared": {
        "reference": "shared_mma",
        "modes": ["empty", "shared_load_only", "shared_mma"],
    },
    "l2": {
        "reference": "l2_mma",
        "modes": ["empty", "l2_load_only", "l2_mma"],
    },
    "dram": {
        "reference": "dram_mma",
        "modes": ["empty", "dram_load_only", "dram_mma"],
    },
    "store": {
        "reference": "store_only",
        "modes": ["empty", "store_only", "store_path"],
    },
}
DEFAULT_GROUPS = ["register", "shared", "l2", "dram", "store"]


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
    repeats: int,
    output: str,
    iters: int | None,
) -> list[str]:
    cmd = [
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
        str(repeats),
        "--reuse-factor",
        str(reuse_factor),
        "--load-repeat",
        str(load_repeat),
        "--store-repeat",
        str(store_repeat),
        "--output",
        output,
        "--verify-smid",
        str(args.verify_smid),
    ]
    if iters is not None and iters > 0:
        cmd.extend(["--iters", str(iters)])
    return cmd


def parse_iter(output: str) -> int:
    match = re.search(r"ITER=(\d+)", output)
    if not match:
        raise RuntimeError("failed to parse ITER from calibration output")
    return int(match.group(1))


def calibrate_iters(
    args: argparse.Namespace,
    *,
    reference_mode: str,
    gpu_list: str,
    w_sm_kib: int,
    blocks_per_sm: int,
    active_sm: int,
    reuse_factor: int,
    load_repeat: int,
    store_repeat: int,
) -> int:
    cmd = build_command(
        args,
        mode=reference_mode,
        gpu_list=gpu_list,
        w_sm_kib=w_sm_kib,
        blocks_per_sm=blocks_per_sm,
        active_sm=active_sm,
        reuse_factor=reuse_factor,
        load_repeat=load_repeat,
        store_repeat=store_repeat,
        repeats=1,
        output=args.calibration_output,
        iters=None,
    )
    print(f"[calibrate] {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="")
    return parse_iter(proc.stdout + "\n" + proc.stderr)


def rotated(values: list[str], offset: int) -> list[str]:
    if not values:
        return values
    offset %= len(values)
    return values[offset:] + values[:offset]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--output", default="results/raw/component_pairs_raw.csv")
    parser.add_argument(
        "--calibration-output",
        default="results/raw/component_pairs_calibration_raw.csv",
    )
    parser.add_argument(
        "--matrix-csv", default="results/raw/component_pairs_matrix.csv"
    )
    parser.add_argument("--target-profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--max-active-gpus", type=int, default=1)
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument("--w-sm-kib-values", default="")
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--active-sm-values", default="")
    parser.add_argument("--reuse-factors", default="1")
    parser.add_argument("--load-repeats", default="1")
    parser.add_argument("--store-repeats", default="1")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--iters",
        type=int,
        default=0,
        help="Use a fixed ITER for every group; 0 calibrates per reference mode.",
    )
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    gpu_ids = parse_int_list(args.gpu_ids, [0])
    groups = parse_str_list(args.groups, DEFAULT_GROUPS)
    unknown_groups = sorted(set(groups) - set(GROUPS))
    if unknown_groups:
        raise ValueError(f"unknown groups: {','.join(unknown_groups)}")
    w_values = parse_int_list(args.w_sm_kib_values, W_SM_KIB)
    b_default = [1, 2, 4, 8, 16, 32]
    b_default = [b for b in b_default if b <= profile["max_blocks_per_sm"]]
    b_values = parse_int_list(args.blocks_per_sm_values, b_default)
    active_sm_values = parse_int_list(args.active_sm_values, profile["active_sm"])
    reuse_factors = parse_uint64_list(args.reuse_factors, [1])
    load_repeats = parse_uint64_list(args.load_repeats, [1])
    store_repeats = parse_uint64_list(args.store_repeats, [1])
    n_gpu_values = list(range(1, min(args.max_active_gpus, len(gpu_ids)) + 1))

    matrix_path = Path(args.matrix_csv)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)

    coordinates: list[dict[str, Any]] = []
    command_count = 0
    with matrix_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "group",
                "reference_mode",
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
                "iters",
                "command",
            ],
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
                                    valid_groups: list[str] = []
                                    for group in groups:
                                        ref = GROUPS[group]["reference"]
                                        group_valid = mode_allowed(ref, info)
                                        if group_valid:
                                            valid_groups.append(group)
                                        for mode in GROUPS[group]["modes"]:
                                            valid = group_valid and mode_allowed(mode, info)
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
                                                repeats=1,
                                                output=args.output,
                                                iters=args.iters if args.iters else None,
                                            )
                                            if valid:
                                                command_count += args.repeats
                                            writer.writerow(
                                                {
                                                    "group": group,
                                                    "reference_mode": ref,
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
                                                    "iters": args.iters or "calibrated",
                                                    "command": " ".join(cmd),
                                                }
                                            )
                                    if valid_groups:
                                        coordinates.append(
                                            {
                                                "w_sm_kib": w_sm_kib,
                                                "blocks_per_sm": blocks_per_sm,
                                                "active_sm": active_sm,
                                                "gpu_list": gpu_list,
                                                "reuse_factor": reuse_factor,
                                                "load_repeat": load_repeat,
                                                "store_repeat": store_repeat,
                                                "groups": valid_groups,
                                                "info": info,
                                            }
                                        )

    print(f"wrote matrix: {matrix_path}")
    print(f"valid per-mode commands: {command_count}")
    if not args.execute:
        print("dry run only; pass --execute to run the commands")
        return 0

    index = 0
    for coord in coordinates:
        group_iters: dict[str, int] = {}
        for group in coord["groups"]:
            if args.iters:
                group_iters[group] = args.iters
            else:
                group_iters[group] = calibrate_iters(
                    args,
                    reference_mode=GROUPS[group]["reference"],
                    gpu_list=coord["gpu_list"],
                    w_sm_kib=coord["w_sm_kib"],
                    blocks_per_sm=coord["blocks_per_sm"],
                    active_sm=coord["active_sm"],
                    reuse_factor=coord["reuse_factor"],
                    load_repeat=coord["load_repeat"],
                    store_repeat=coord["store_repeat"],
                )

        for repeat in range(args.repeats):
            for group in rotated(coord["groups"], repeat):
                for mode in GROUPS[group]["modes"]:
                    cmd = build_command(
                        args,
                        mode=mode,
                        gpu_list=coord["gpu_list"],
                        w_sm_kib=coord["w_sm_kib"],
                        blocks_per_sm=coord["blocks_per_sm"],
                        active_sm=coord["active_sm"],
                        reuse_factor=coord["reuse_factor"],
                        load_repeat=coord["load_repeat"],
                        store_repeat=coord["store_repeat"],
                        repeats=1,
                        output=args.output,
                        iters=group_iters[group],
                    )
                    index += 1
                    print(f"[{index}/{command_count}] {' '.join(cmd)}", flush=True)
                    subprocess.run(cmd, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
