#!/usr/bin/env python3
"""Run register-footprint experiments without using W_SM as the register axis."""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from run_sweep import DEFAULT_PROFILE, PROFILES, gpu_list_for_count, parse_int_list


DEFAULT_TARGET_BYTES = [256, 512, 1024, 2048, 4096, 8192, 16384]
DEFAULT_BLOCKS = [1, 2, 4, 8, 16, 32]


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    paths = [item for item in env.get("LD_LIBRARY_PATH", "").split(":") if item]
    for path in ["/usr/lib/wsl/lib"]:
        if Path(path).exists() and path not in paths:
            paths.append(path)
    if paths:
        env["LD_LIBRARY_PATH"] = ":".join(paths)
    return env


def parse_uint64_list(value: str, default: list[int]) -> list[int]:
    if not value:
        return default
    out = [int(item) for item in value.split(",") if item]
    if any(item <= 0 for item in out):
        raise ValueError("values must be positive")
    return out


def parse_iter(output: str) -> int:
    match = re.search(r"ITER=(\d+)", output)
    if not match:
        raise RuntimeError("failed to parse ITER from calibration output")
    return int(match.group(1))


def build_command(
    args: argparse.Namespace,
    *,
    mode: str,
    gpu_list: str,
    blocks_per_sm: int,
    active_sm: int,
    reuse_factor: int,
    reg_payload_bytes: int,
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
        "1",
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
        "1",
        "--store-repeat",
        "1",
        "--reg-payload-bytes",
        str(reg_payload_bytes),
        "--output",
        output,
        "--verify-smid",
        str(args.verify_smid),
    ]
    if iters is not None and iters > 0:
        cmd.extend(["--iters", str(iters)])
    return cmd


def inspect_ptxas(args: argparse.Namespace) -> list[dict[str, str]]:
    cmd = [
        "python3",
        "scripts/inspect_register_footprint.py",
        "--target-profile",
        args.target_profile,
        "--out-csv",
        args.ptxas_csv,
    ]
    if args.nvcc:
        cmd.extend(["--nvcc", args.nvcc])
    print(f"[ptxas] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)
    with Path(args.ptxas_csv).open(newline="") as f:
        return list(csv.DictReader(f))


def pressure_row_by_target(rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for row in rows:
        if "reg_pressure_kernel" not in row["kernel_demangled"]:
            continue
        target = int(float(row["target_payload_bytes_per_block"]))
        out[target] = row
    return out


def calibrate_iters(
    args: argparse.Namespace,
    *,
    gpu_list: str,
    blocks_per_sm: int,
    active_sm: int,
    reuse_factor: int,
    reg_payload_bytes: int,
) -> int:
    cmd = build_command(
        args,
        mode="reg_pressure",
        gpu_list=gpu_list,
        blocks_per_sm=blocks_per_sm,
        active_sm=active_sm,
        reuse_factor=reuse_factor,
        reg_payload_bytes=reg_payload_bytes,
        repeats=1,
        output=args.calibration_output,
        iters=None,
    )
    print(f"[calibrate] {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True, env=subprocess_env())
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="")
    proc.check_returncode()
    return parse_iter(proc.stdout + "\n" + proc.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--output", default="results/raw/register_footprint_raw.csv")
    parser.add_argument(
        "--calibration-output",
        default="results/raw/register_footprint_calibration.csv",
    )
    parser.add_argument("--matrix-csv", default="results/raw/register_footprint_matrix.csv")
    parser.add_argument("--ptxas-csv", default="results/summary/register_footprint_ptxas.csv")
    parser.add_argument("--nvcc", default="")
    parser.add_argument("--target-profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--max-active-gpus", type=int, default=1)
    parser.add_argument("--reg-payload-bytes-values", default="")
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--active-sm-values", default="")
    parser.add_argument("--reuse-factors", default="1")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--iters", type=int, default=0)
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument("--allow-spills", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    gpu_ids = parse_int_list(args.gpu_ids, [0])
    payload_values = parse_uint64_list(args.reg_payload_bytes_values, DEFAULT_TARGET_BYTES)
    b_default = [b for b in DEFAULT_BLOCKS if b <= profile["max_blocks_per_sm"]]
    b_values = parse_uint64_list(args.blocks_per_sm_values, b_default)
    active_sm_values = parse_int_list(args.active_sm_values, profile["active_sm"])
    reuse_factors = parse_uint64_list(args.reuse_factors, [1])
    n_gpu_values = list(range(1, min(args.max_active_gpus, len(gpu_ids)) + 1))

    ptxas_rows = inspect_ptxas(args)
    ptxas_by_target = pressure_row_by_target(ptxas_rows)

    matrix_path = Path(args.matrix_csv)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    coordinates: list[dict[str, Any]] = []
    command_count = 0

    with matrix_path.open("w", newline="") as f:
        fieldnames = [
            "mode",
            "target_profile",
            "reg_payload_bytes_per_block",
            "payload_regs_per_thread",
            "ptxas_registers_per_thread",
            "compiler_footprint_bytes_per_block",
            "compiler_footprint_kib_per_block",
            "compiler_footprint_bytes_per_sm",
            "max_resident_blocks_per_sm_est",
            "spill_free",
            "blocks_per_SM",
            "active_SM",
            "reuse_factor",
            "n_gpu_active",
            "gpu_list",
            "valid",
            "reason",
            "iters",
            "command",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for payload in payload_values:
            ptxas = ptxas_by_target.get(payload)
            for blocks_per_sm in b_values:
                for active_sm in active_sm_values:
                    for reuse_factor in reuse_factors:
                        for n_gpu in n_gpu_values:
                            gpu_list = gpu_list_for_count(gpu_ids, n_gpu)
                            if not ptxas:
                                valid = False
                                reason = "unsupported_payload_or_missing_ptxas_row"
                                ptxas = {}
                            else:
                                spill_free = ptxas.get("spill_free", "") == "True"
                                max_blocks = int(float(ptxas["max_resident_blocks_per_sm_est"]))
                                valid = blocks_per_sm <= max_blocks and (
                                    spill_free or args.allow_spills
                                )
                                if blocks_per_sm > max_blocks:
                                    reason = f"blocks_per_SM exceeds ptxas-estimated resident limit {max_blocks}"
                                elif not spill_free and not args.allow_spills:
                                    reason = "ptxas reported stack frame or spills"
                                else:
                                    reason = "valid"

                            for mode in ["empty", "reg_pressure"]:
                                cmd = build_command(
                                    args,
                                    mode=mode,
                                    gpu_list=gpu_list,
                                    blocks_per_sm=blocks_per_sm,
                                    active_sm=active_sm,
                                    reuse_factor=reuse_factor,
                                    reg_payload_bytes=payload,
                                    repeats=1,
                                    output=args.output,
                                    iters=args.iters if args.iters else None,
                                )
                                if mode == "reg_pressure" and valid:
                                    command_count += args.repeats * 2
                                    coordinates.append(
                                        {
                                            "payload": payload,
                                            "blocks_per_sm": blocks_per_sm,
                                            "active_sm": active_sm,
                                            "reuse_factor": reuse_factor,
                                            "gpu_list": gpu_list,
                                        }
                                    )
                                compiler_block = int(float(ptxas.get("compiler_footprint_bytes_per_block", 0) or 0))
                                writer.writerow(
                                    {
                                        "mode": mode,
                                        "target_profile": args.target_profile,
                                        "reg_payload_bytes_per_block": payload,
                                        "payload_regs_per_thread": ptxas.get("payload_regs_per_thread", ""),
                                        "ptxas_registers_per_thread": ptxas.get("ptxas_registers_per_thread", ""),
                                        "compiler_footprint_bytes_per_block": compiler_block,
                                        "compiler_footprint_kib_per_block": ptxas.get("compiler_footprint_kib_per_block", ""),
                                        "compiler_footprint_bytes_per_sm": compiler_block * blocks_per_sm,
                                        "max_resident_blocks_per_sm_est": ptxas.get("max_resident_blocks_per_sm_est", ""),
                                        "spill_free": ptxas.get("spill_free", ""),
                                        "blocks_per_SM": blocks_per_sm,
                                        "active_SM": active_sm,
                                        "reuse_factor": reuse_factor,
                                        "n_gpu_active": n_gpu,
                                        "gpu_list": gpu_list,
                                        "valid": valid,
                                        "reason": reason,
                                        "iters": args.iters or "calibrated",
                                        "command": " ".join(cmd),
                                    }
                                )

    print(f"wrote matrix: {matrix_path}")
    print(f"valid measurement commands: {command_count}")
    if not args.execute:
        print("dry run only; pass --execute to run the commands")
        return 0

    index = 0
    for coord in coordinates:
        if args.iters:
            iters = args.iters
        else:
            iters = calibrate_iters(
                args,
                gpu_list=coord["gpu_list"],
                blocks_per_sm=coord["blocks_per_sm"],
                active_sm=coord["active_sm"],
                reuse_factor=coord["reuse_factor"],
                reg_payload_bytes=coord["payload"],
            )
        for _repeat in range(args.repeats):
            for mode in ["empty", "reg_pressure"]:
                cmd = build_command(
                    args,
                    mode=mode,
                    gpu_list=coord["gpu_list"],
                    blocks_per_sm=coord["blocks_per_sm"],
                    active_sm=coord["active_sm"],
                    reuse_factor=coord["reuse_factor"],
                    reg_payload_bytes=coord["payload"],
                    repeats=1,
                    output=args.output,
                    iters=iters,
                )
                index += 1
                print(f"[{index}/{command_count}] {' '.join(cmd)}", flush=True)
                subprocess.run(cmd, check=True, env=subprocess_env())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
