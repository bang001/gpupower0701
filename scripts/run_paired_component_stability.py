#!/usr/bin/env python3
"""Run control-treatment-control stability sequences for one component path.

This runner is intentionally narrower than run_component_regression_sweep.py.
It is for drift-sensitive follow-up runs where the key question is whether a
treatment row remains stable when bracketed by nearby control rows.
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import time
from pathlib import Path

from run_sweep import parse_gpu_ids


FINAL_CONTROL_BY_TREATMENT = {
    "shared_scalar_load_only": "shared_scalar_addr_only",
    "global_l1_load_only": "global_addr_only",
    "l2_cg_load_only": "global_addr_only",
    "dram_cg_load_only": "global_addr_only",
}


def build_command(
    args: argparse.Namespace,
    *,
    mode: str,
    output: str,
    seconds: float,
) -> list[str]:
    cmd = [
        args.binary,
        "--gpu-list",
        args.gpu_ids,
        "--mode",
        mode,
        "--w-sm-kib",
        str(args.w_sm_kib),
        "--blocks-per-sm",
        str(args.blocks_per_sm),
        "--target-profile",
        args.target_profile,
        "--active-sm",
        str(args.active_sm),
        "--seconds",
        str(seconds),
        "--repeats",
        "1",
        "--reuse-factor",
        str(args.reuse_factor),
        "--load-repeat",
        str(args.load_repeat),
        "--store-repeat",
        str(args.store_repeat),
        "--output",
        output,
        "--verify-smid",
        str(args.verify_smid),
    ]
    if args.iters:
        cmd.extend(["--iters", str(args.iters)])
    return cmd


def write_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "phase",
        "repeat",
        "sequence_index",
        "role",
        "mode",
        "target_profile",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "seconds",
        "command",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sequence_rows(
    args: argparse.Namespace,
    *,
    phase: str,
    repeats: int,
    output: str,
    seconds: float,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sequence = [
        ("control_before", args.control_mode),
        ("treatment", args.treatment_mode),
        ("control_after", args.control_mode),
    ]
    index = 0
    for repeat in range(repeats):
        for role, mode in sequence:
            index += 1
            cmd = build_command(args, mode=mode, output=output, seconds=seconds)
            rows.append(
                {
                    "phase": phase,
                    "repeat": str(repeat),
                    "sequence_index": str(index),
                    "role": role,
                    "mode": mode,
                    "target_profile": args.target_profile,
                    "W_SM_KiB": str(args.w_sm_kib),
                    "blocks_per_SM": str(args.blocks_per_sm),
                    "active_SM": str(args.active_sm),
                    "reuse_factor": str(args.reuse_factor),
                    "load_repeat": str(args.load_repeat),
                    "store_repeat": str(args.store_repeat),
                    "seconds": str(seconds),
                    "command": shlex.join(cmd),
                }
            )
    return rows


def run_rows(rows: list[dict[str, str]], sleep_s: float) -> None:
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        print(
            f"[{idx}/{total}] phase={row['phase']} repeat={row['repeat']} "
            f"role={row['role']} mode={row['mode']}",
            flush=True,
        )
        subprocess.run(shlex.split(row["command"]), check=True)
        if sleep_s > 0 and idx < total:
            time.sleep(sleep_s)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--output", required=True)
    parser.add_argument("--matrix-csv", required=True)
    parser.add_argument("--warmup-output", default="")
    parser.add_argument("--target-profile", default="rtx3090")
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--active-sm", type=int, required=True)
    parser.add_argument("--control-mode", required=True)
    parser.add_argument("--treatment-mode", required=True)
    parser.add_argument("--w-sm-kib", type=int, required=True)
    parser.add_argument("--blocks-per-sm", type=int, required=True)
    parser.add_argument("--reuse-factor", type=int, default=1)
    parser.add_argument("--load-repeat", type=int, default=1)
    parser.add_argument("--store-repeat", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--warmup-seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--warmup-repeats", type=int, default=0)
    parser.add_argument("--sleep-between-commands-s", type=float, default=0.0)
    parser.add_argument("--iters", type=int, default=0)
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    args.gpu_ids = ",".join(str(value) for value in parse_gpu_ids(args.gpu_ids))

    if args.repeats <= 0:
        raise ValueError("--repeats must be positive")
    if args.warmup_repeats < 0:
        raise ValueError("--warmup-repeats must be non-negative")
    expected_control = FINAL_CONTROL_BY_TREATMENT.get(args.treatment_mode)
    if expected_control and args.control_mode != expected_control:
        raise ValueError(
            f"{args.treatment_mode} current protocol requires "
            f"--control-mode {expected_control}, got {args.control_mode}"
        )
    if args.treatment_mode == "reg_mma":
        raise ValueError(
            "reg_mma requires pair-locked ITER; use run_component_regression_sweep.py "
            "with --tensor-pair-lock-iters"
        )

    warmup_output = args.warmup_output
    if not warmup_output:
        out = Path(args.output)
        warmup_output = str(out.with_name(out.stem + "_warmup" + out.suffix))

    warmup_rows = sequence_rows(
        args,
        phase="warmup",
        repeats=args.warmup_repeats,
        output=warmup_output,
        seconds=args.warmup_seconds,
    )
    measure_rows = sequence_rows(
        args,
        phase="measure",
        repeats=args.repeats,
        output=args.output,
        seconds=args.seconds,
    )
    rows = warmup_rows + measure_rows
    write_matrix(Path(args.matrix_csv), rows)

    print(f"wrote matrix: {args.matrix_csv}")
    print(f"warmup commands: {len(warmup_rows)} -> {warmup_output}")
    print(f"measurement commands: {len(measure_rows)} -> {args.output}")
    if not args.execute:
        print("dry run only; pass --execute to run the sequence")
        return 0

    if warmup_rows:
        print("running warmup sequence")
        run_rows(warmup_rows, args.sleep_between_commands_s)
    print("running measurement sequence")
    run_rows(measure_rows, args.sleep_between_commands_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
