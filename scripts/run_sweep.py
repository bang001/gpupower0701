#!/usr/bin/env python3
"""Run or materialize the FP16 energy v2 design matrix."""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path
from typing import Any


PROFILES: dict[str, dict[str, Any]] = {
    "v100": {
        "full_sm": 80,
        "l2_mib": 6,
        "max_blocks_per_sm": 32,
        "shared_capacity_per_sm_kib": 96,
        "max_shared_per_block_kib": 96,
        "active_sm": [1, 2, 4, 8, 16, 32, 64, 80],
    },
    "rtx3090": {
        "full_sm": 82,
        "l2_mib": 6,
        "max_blocks_per_sm": 16,
        "shared_capacity_per_sm_kib": 100,
        "max_shared_per_block_kib": 99,
        "active_sm": [1, 2, 4, 8, 16, 32, 64, 82],
    },
    "a100": {
        "full_sm": 108,
        "l2_mib": 40,
        "max_blocks_per_sm": 32,
        "shared_capacity_per_sm_kib": 164,
        "max_shared_per_block_kib": 163,
        "active_sm": [1, 2, 4, 8, 16, 32, 64, 108],
    },
    "h100": {
        "full_sm": 132,
        "l2_mib": 50,
        "max_blocks_per_sm": 32,
        "shared_capacity_per_sm_kib": 228,
        "max_shared_per_block_kib": 227,
        "active_sm": [1, 2, 4, 8, 16, 32, 64, 132],
    },
}
DEFAULT_PROFILE = "rtx3090"
BLOCKS_PER_SM = [1, 2, 4, 8, 16, 32]
W_SM_KIB = [
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
]
MODES = ["empty", "reg_mma", "shared_mma", "l2_mma", "dram_mma", "store_path"]


def classify(w_sm_kib: int, blocks_per_sm: int, profile: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "valid": False,
        "regime": "invalid",
        "reason": "",
        "shared_resident": False,
        "l2_candidate": False,
        "dram_candidate": False,
    }
    if blocks_per_sm not in BLOCKS_PER_SM or blocks_per_sm > profile["max_blocks_per_sm"]:
        out["regime"] = "invalid_blocks_per_sm"
        out["reason"] = (
            f"blocks_per_SM exceeds resident block limit {profile['max_blocks_per_sm']}"
        )
        return out
    if w_sm_kib not in W_SM_KIB:
        out["regime"] = "invalid_w_sm"
        out["reason"] = "unsupported W_SM_KiB"
        return out
    if w_sm_kib < blocks_per_sm:
        out["regime"] = "invalid_min_tile"
        out["reason"] = "W_SM_KiB < blocks_per_SM"
        return out

    full_gpu_mib = profile["full_sm"] * w_sm_kib / 1024.0
    shared_resident = (
        w_sm_kib + blocks_per_sm <= profile["shared_capacity_per_sm_kib"]
        and (w_sm_kib / blocks_per_sm) <= profile["max_shared_per_block_kib"]
    )
    l2_candidate = full_gpu_mib <= profile["l2_mib"]

    out["valid"] = True
    out["shared_resident"] = shared_resident
    out["l2_candidate"] = l2_candidate
    out["dram_candidate"] = not l2_candidate
    if shared_resident:
        out["regime"] = "shared_resident"
        out["reason"] = "fits shared memory"
    elif l2_candidate:
        out["regime"] = "l2_candidate"
        out["reason"] = "full-GPU working set fits nominal L2"
    else:
        out["regime"] = "dram_mixed_streaming"
        out["reason"] = "full-GPU working set exceeds nominal L2"
    return out


def mode_allowed(mode: str, info: dict[str, Any]) -> bool:
    if not info["valid"]:
        return False
    if mode == "shared_mma":
        return bool(info["shared_resident"])
    if mode == "l2_mma":
        return bool(info["l2_candidate"])
    if mode == "dram_mma":
        return bool(info["dram_candidate"])
    return True


def parse_int_list(value: str, default: list[int]) -> list[int]:
    if not value:
        return default
    return [int(item) for item in value.split(",") if item]


def parse_str_list(value: str, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item for item in value.split(",") if item]


def gpu_list_for_count(gpu_ids: list[int], n_active: int) -> str:
    if n_active == 0:
        return "none"
    return ",".join(str(gpu) for gpu in gpu_ids[:n_active])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--output", default="results/raw/a100_fp16_energy_v2_raw.csv")
    parser.add_argument(
        "--matrix-csv", default="results/raw/a100_fp16_energy_v2_dry_run_matrix.csv"
    )
    parser.add_argument("--target-profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--max-active-gpus", type=int, default=1)
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--w-sm-kib-values", default="")
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--active-sm-values", default="")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--iters", type=int, default=0)
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--include-idle", action="store_true")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    gpu_ids = parse_int_list(args.gpu_ids, [0])
    modes = parse_str_list(args.modes, MODES)
    w_values = parse_int_list(args.w_sm_kib_values, W_SM_KIB)
    b_default = [b for b in BLOCKS_PER_SM if b <= profile["max_blocks_per_sm"]]
    b_values = parse_int_list(args.blocks_per_sm_values, b_default)
    active_sm_values = parse_int_list(args.active_sm_values, profile["active_sm"])
    n_gpu_values = list(range(1, min(args.max_active_gpus, len(gpu_ids)) + 1))

    matrix_path = Path(args.matrix_csv)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    with matrix_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "mode",
                "target_profile",
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "n_gpu_active",
                "gpu_list",
                "valid",
                "regime",
                "shared_resident",
                "l2_candidate",
                "dram_candidate",
                "reason",
                "command",
            ],
        )
        writer.writeheader()

        if args.include_idle:
            cmd = [
                args.binary,
                "--gpu-list",
                "none",
                "--mode",
                "idle",
                "--w-sm-kib",
                "1",
                "--blocks-per-sm",
                "1",
                "--target-profile",
                args.target_profile,
                "--active-sm",
                str(profile["full_sm"]),
                "--seconds",
                str(args.seconds),
                "--repeats",
                str(args.repeats),
                "--output",
                args.output,
            ]
            commands.append(cmd)
            writer.writerow(
                {
                    "mode": "idle",
                    "target_profile": args.target_profile,
                    "W_SM_KiB": 1,
                    "blocks_per_SM": 1,
                    "active_SM": profile["full_sm"],
                    "n_gpu_active": 0,
                    "gpu_list": "none",
                    "valid": True,
                    "regime": "idle",
                    "shared_resident": True,
                    "l2_candidate": True,
                    "dram_candidate": False,
                    "reason": "0 active GPU baseline",
                    "command": " ".join(cmd),
                }
            )

        for mode in modes:
            for w_sm_kib in w_values:
                for blocks_per_sm in b_values:
                    info = classify(w_sm_kib, blocks_per_sm, profile)
                    allowed = mode_allowed(mode, info)
                    for active_sm in active_sm_values:
                        for n_gpu in n_gpu_values:
                            gpu_list = gpu_list_for_count(gpu_ids, n_gpu)
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
                                str(args.repeats),
                                "--output",
                                args.output,
                                "--verify-smid",
                                str(args.verify_smid),
                            ]
                            if args.iters:
                                cmd.extend(["--iters", str(args.iters)])
                            if allowed:
                                commands.append(cmd)
                            writer.writerow(
                                {
                                    "mode": mode,
                                    "target_profile": args.target_profile,
                                    "W_SM_KiB": w_sm_kib,
                                    "blocks_per_SM": blocks_per_sm,
                                    "active_SM": active_sm,
                                    "n_gpu_active": n_gpu,
                                    "gpu_list": gpu_list,
                                    "valid": allowed,
                                    "regime": info["regime"],
                                    "shared_resident": info["shared_resident"],
                                    "l2_candidate": info["l2_candidate"],
                                    "dram_candidate": info["dram_candidate"],
                                    "reason": (
                                        info["reason"]
                                        if allowed
                                        else f"skipped_for_mode_or_invalid:{info['reason']}"
                                    ),
                                    "command": " ".join(cmd),
                                }
                            )

    print(f"wrote matrix: {matrix_path}")
    print(f"valid commands: {len(commands)}")
    if not args.execute:
        print("dry run only; pass --execute to run the commands")
        for cmd in commands[:20]:
            print(" ".join(cmd))
        if len(commands) > 20:
            print(f"... {len(commands) - 20} more")
        return 0

    for index, cmd in enumerate(commands, start=1):
        print(f"[{index}/{len(commands)}] {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
