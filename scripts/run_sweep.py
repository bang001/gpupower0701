#!/usr/bin/env python3
"""Run or materialize the A100 FP16 energy v2 design matrix."""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


A100_FULL_SM = 108
L2_MIB = 40
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
ACTIVE_SM = [1, 2, 4, 8, 16, 32, 64, 108]
MODES = ["empty", "reg_mma", "shared_mma", "l2_mma", "dram_mma", "store_path"]


def classify(w_sm_kib: int, blocks_per_sm: int) -> tuple[bool, str, str]:
    if blocks_per_sm not in BLOCKS_PER_SM:
        return False, "invalid_blocks_per_sm", "unsupported blocks/SM"
    if w_sm_kib not in W_SM_KIB:
        return False, "invalid_w_sm", "unsupported W_SM_KiB"
    if w_sm_kib < blocks_per_sm:
        return False, "invalid_min_tile", "W_SM_KiB < blocks_per_SM"
    if w_sm_kib + blocks_per_sm <= 164 and (w_sm_kib / blocks_per_sm) <= 163:
        return True, "shared_resident", "fits shared memory"
    full108_mib = A100_FULL_SM * w_sm_kib / 1024.0
    if full108_mib <= L2_MIB:
        return True, "l2_candidate", "full-108SM working set fits nominal L2"
    return True, "dram_mixed_streaming", "full-108SM working set exceeds nominal L2"


def mode_allowed(mode: str, valid: bool, regime: str) -> bool:
    if not valid:
        return False
    if mode == "shared_mma":
        return regime == "shared_resident"
    if mode == "l2_mma":
        return regime == "l2_candidate"
    if mode == "dram_mma":
        return regime == "dram_mixed_streaming"
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
    parser.add_argument("--matrix-csv", default="results/raw/a100_fp16_energy_v2_dry_run_matrix.csv")
    parser.add_argument("--gpu-ids", default="0,1,2")
    parser.add_argument("--max-active-gpus", type=int, default=3)
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

    gpu_ids = parse_int_list(args.gpu_ids, [0, 1, 2])
    modes = parse_str_list(args.modes, MODES)
    w_values = parse_int_list(args.w_sm_kib_values, W_SM_KIB)
    b_values = parse_int_list(args.blocks_per_sm_values, BLOCKS_PER_SM)
    active_sm_values = parse_int_list(args.active_sm_values, ACTIVE_SM)
    n_gpu_values = list(range(1, min(args.max_active_gpus, len(gpu_ids)) + 1))

    matrix_path = Path(args.matrix_csv)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    with matrix_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "mode",
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "n_gpu_active",
                "gpu_list",
                "valid",
                "regime",
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
                "--active-sm",
                "108",
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
                    "W_SM_KiB": 1,
                    "blocks_per_SM": 1,
                    "active_SM": 108,
                    "n_gpu_active": 0,
                    "gpu_list": "none",
                    "valid": True,
                    "regime": "idle",
                    "reason": "0 active GPU baseline",
                    "command": " ".join(cmd),
                }
            )

        for mode in modes:
            for w_sm_kib in w_values:
                for blocks_per_sm in b_values:
                    valid, regime, reason = classify(w_sm_kib, blocks_per_sm)
                    allowed = mode_allowed(mode, valid, regime)
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
                                    "W_SM_KiB": w_sm_kib,
                                    "blocks_per_SM": blocks_per_sm,
                                    "active_SM": active_sm,
                                    "n_gpu_active": n_gpu,
                                    "gpu_list": gpu_list,
                                    "valid": allowed,
                                    "regime": regime,
                                    "reason": reason if allowed else f"skipped_for_mode_or_invalid:{reason}",
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
