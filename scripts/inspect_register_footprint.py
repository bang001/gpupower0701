#!/usr/bin/env python3
"""Compile kernels.cu and extract ptxas register-footprint metadata."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
from pathlib import Path

from run_sweep import DEFAULT_PROFILE, PROFILES


REGS_PER_SM_32BIT = 65536
THREADS_PER_BLOCK = 32


def cuda_arch_for_profile(profile: str) -> int:
    return {
        "v100": 70,
        "rtx3090": 86,
        "a100": 80,
        "h100": 90,
    }[profile]


def demangle(name: str) -> str:
    cxxfilt = shutil.which("c++filt")
    if not cxxfilt:
        return name
    proc = subprocess.run([cxxfilt, name], text=True, capture_output=True)
    if proc.returncode != 0:
        return name
    return proc.stdout.strip() or name


def payload_regs_from_name(name: str) -> int | None:
    match = re.search(r"reg_pressure_kernel<([0-9]+)>", name)
    if match:
        return int(match.group(1))
    match = re.search(r"reg_pressure_kernelILi([0-9]+)EE", name)
    if match:
        return int(match.group(1))
    return None


def parse_ptxas(text: str, profile: str) -> list[dict[str, object]]:
    profile_info = PROFILES[profile]
    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in text.splitlines():
        entry = re.search(r"Compiling entry function '([^']+)'", line)
        if entry:
            mangled = entry.group(1)
            demangled = demangle(mangled)
            current = {
                "profile_name": profile,
                "kernel_mangled": mangled,
                "kernel_demangled": demangled,
                "payload_regs_per_thread": payload_regs_from_name(demangled)
                or payload_regs_from_name(mangled)
                or "",
                "stack_frame_bytes": 0,
                "spill_stores_bytes": 0,
                "spill_loads_bytes": 0,
                "ptxas_registers_per_thread": "",
            }
            continue

        if current is None:
            continue

        props = re.search(
            r"([0-9]+) bytes stack frame, ([0-9]+) bytes spill stores, ([0-9]+) bytes spill loads",
            line,
        )
        if props:
            current["stack_frame_bytes"] = int(props.group(1))
            current["spill_stores_bytes"] = int(props.group(2))
            current["spill_loads_bytes"] = int(props.group(3))
            continue

        used = re.search(r"Used ([0-9]+) registers", line)
        if used:
            regs = int(used.group(1))
            current["ptxas_registers_per_thread"] = regs
            payload = current["payload_regs_per_thread"]
            payload_int = int(payload) if payload != "" else 0
            target_b = payload_int * THREADS_PER_BLOCK * 4
            compiler_b = regs * THREADS_PER_BLOCK * 4
            reg_limited_blocks = REGS_PER_SM_32BIT // (regs * THREADS_PER_BLOCK)
            max_by_warps = profile_info["max_warps_per_sm"]
            max_by_threads = profile_info["max_threads_per_sm"] // THREADS_PER_BLOCK
            max_blocks = min(
                profile_info["max_blocks_per_sm"],
                max_by_warps,
                max_by_threads,
                reg_limited_blocks,
            )
            current.update(
                {
                    "target_payload_bytes_per_block": target_b,
                    "compiler_footprint_bytes_per_block": compiler_b,
                    "compiler_footprint_kib_per_block": compiler_b / 1024.0,
                    "max_resident_blocks_per_sm_est": max_blocks,
                    "spill_free": (
                        int(current["stack_frame_bytes"]) == 0
                        and int(current["spill_stores_bytes"]) == 0
                        and int(current["spill_loads_bytes"]) == 0
                    ),
                    "registers_per_sm_32bit_assumed": REGS_PER_SM_32BIT,
                    "threads_per_block": THREADS_PER_BLOCK,
                }
            )
            rows.append(current)
            current = None

    wanted = []
    for row in rows:
        name = str(row["kernel_demangled"])
        if "reg_pressure_kernel" in name or "reg_mma_kernel" in name or "reg_operand_only_kernel" in name or "empty_kernel" in name:
            wanted.append(row)
    return wanted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    parser.add_argument("--nvcc", default="")
    parser.add_argument("--out-csv", default="results/summary/register_footprint_ptxas.csv")
    parser.add_argument("--object", default="/tmp/gpupower_register_footprint.o")
    args = parser.parse_args()

    nvcc = args.nvcc or shutil.which("nvcc") or "/home/bang001/miniforge3/envs/ssc21env/bin/nvcc"
    arch = cuda_arch_for_profile(args.target_profile)
    cmd = [
        nvcc,
        "-std=c++17",
        "-Iinclude",
        f"-arch=sm_{arch}",
        "-Xptxas=-v",
        "-c",
        "src/kernels.cu",
        "-o",
        args.object,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    rows = parse_ptxas(proc.stdout + "\n" + proc.stderr, args.target_profile)
    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile_name",
        "kernel_demangled",
        "payload_regs_per_thread",
        "target_payload_bytes_per_block",
        "ptxas_registers_per_thread",
        "compiler_footprint_bytes_per_block",
        "compiler_footprint_kib_per_block",
        "max_resident_blocks_per_sm_est",
        "stack_frame_bytes",
        "spill_stores_bytes",
        "spill_loads_bytes",
        "spill_free",
        "registers_per_sm_32bit_assumed",
        "threads_per_block",
        "kernel_mangled",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
