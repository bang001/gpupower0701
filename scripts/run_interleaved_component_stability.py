#!/usr/bin/env python3
"""Run interleaved control-treatment-control sequences across factor values.

This is a follow-up runner for drift-sensitive component paths.  The existing
single-factor paired runner is useful for one LR/RF value at a time, but it
cannot separate factor sensitivity from run-order or thermal drift.  This
runner executes a C-T-C bracket for each factor inside the same cycle:

    cycle 0: C LR4, T LR4, C LR4, C LR8, T LR8, C LR8, ...
    cycle 1: ...

For memory paths the factor is usually load_repeat.  For tensor/register paths
it can be reuse_factor.  The binary still writes the raw CSV; this script writes
the command matrix and optionally executes it.
"""

from __future__ import annotations

import argparse
import csv
import random
import shlex
import subprocess
import time
from pathlib import Path


def parse_int_list(text: str) -> list[int]:
    values = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("factor list must not be empty")
    return values


def factor_value(args: argparse.Namespace, factor: int, name: str) -> str:
    if name == "reuse_factor":
        return str(factor)
    if name == "load_repeat":
        return str(factor)
    if name == "store_repeat":
        return str(factor)
    raise ValueError(f"unsupported factor name: {name}")


def build_command(
    args: argparse.Namespace,
    *,
    role: str,
    mode: str,
    output: str,
    seconds: float,
    factor: int,
) -> list[str]:
    reuse_factor = args.reuse_factor
    load_repeat = args.load_repeat
    store_repeat = args.store_repeat
    if args.factor_name == "reuse_factor":
        reuse_factor = factor
    elif args.factor_name == "load_repeat":
        load_repeat = factor
    elif args.factor_name == "store_repeat":
        store_repeat = factor
    else:
        raise ValueError(f"unsupported factor name: {args.factor_name}")

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
    iters = args.iters
    if role.startswith("control") and args.control_iters:
        iters = args.control_iters
    elif role == "treatment" and args.treatment_iters:
        iters = args.treatment_iters
    if iters:
        cmd.extend(["--iters", str(iters)])
    return cmd


def role_iters(args: argparse.Namespace, role: str) -> int:
    if role.startswith("control") and args.control_iters:
        return args.control_iters
    if role == "treatment" and args.treatment_iters:
        return args.treatment_iters
    return args.iters


def factor_order(
    factors: list[int],
    *,
    cycle: int,
    order: str,
    rng: random.Random,
) -> list[int]:
    out = list(factors)
    if order == "fixed":
        return out
    if order == "rotate":
        shift = cycle % len(out)
        return out[shift:] + out[:shift]
    if order == "random":
        rng.shuffle(out)
        return out
    raise ValueError(f"unsupported order: {order}")


def sequence_rows(
    args: argparse.Namespace,
    *,
    phase: str,
    cycles: int,
    output: str,
    seconds: float,
    factors: list[int],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sequence = [
        ("control_before", args.control_mode),
        ("treatment", args.treatment_mode),
        ("control_after", args.control_mode),
    ]
    rng = random.Random(args.seed)
    index = 0
    for cycle in range(cycles):
        for factor in factor_order(factors, cycle=cycle, order=args.order, rng=rng):
            for role, mode in sequence:
                index += 1
                cmd = build_command(
                    args,
                    role=role,
                    mode=mode,
                    output=output,
                    seconds=seconds,
                    factor=factor,
                )
                rows.append(
                    {
                        "phase": phase,
                        "cycle": str(cycle),
                        "sequence_index": str(index),
                        "role": role,
                        "mode": mode,
                        "factor_name": args.factor_name,
                        "factor_value": str(factor),
                        "target_profile": args.target_profile,
                        "W_SM_KiB": str(args.w_sm_kib),
                        "blocks_per_SM": str(args.blocks_per_sm),
                        "active_SM": str(args.active_sm),
                        "reuse_factor": factor_value(args, factor, "reuse_factor")
                        if args.factor_name == "reuse_factor"
                        else str(args.reuse_factor),
                        "load_repeat": factor_value(args, factor, "load_repeat")
                        if args.factor_name == "load_repeat"
                        else str(args.load_repeat),
                        "store_repeat": factor_value(args, factor, "store_repeat")
                        if args.factor_name == "store_repeat"
                        else str(args.store_repeat),
                        "seconds": str(seconds),
                        "iters": str(role_iters(args, role)),
                        "command": shlex.join(cmd),
                    }
                )
    return rows


def write_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "phase",
        "cycle",
        "sequence_index",
        "role",
        "mode",
        "factor_name",
        "factor_value",
        "target_profile",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "seconds",
        "iters",
        "command",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_rows(rows: list[dict[str, str]], sleep_s: float) -> None:
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        print(
            f"[{idx}/{total}] phase={row['phase']} cycle={row['cycle']} "
            f"factor={row['factor_name']}={row['factor_value']} "
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
    parser.add_argument("--control-mode", default="clocked_empty")
    parser.add_argument("--treatment-mode", required=True)
    parser.add_argument(
        "--factor-name",
        choices=["reuse_factor", "load_repeat", "store_repeat"],
        default="load_repeat",
    )
    parser.add_argument("--factor-values", required=True)
    parser.add_argument("--order", choices=["fixed", "rotate", "random"], default="rotate")
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--w-sm-kib", type=int, required=True)
    parser.add_argument("--blocks-per-sm", type=int, required=True)
    parser.add_argument("--reuse-factor", type=int, default=1)
    parser.add_argument("--load-repeat", type=int, default=1)
    parser.add_argument("--store-repeat", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--warmup-seconds", type=float, default=10.0)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--warmup-cycles", type=int, default=0)
    parser.add_argument("--sleep-between-commands-s", type=float, default=0.0)
    parser.add_argument("--iters", type=int, default=0)
    parser.add_argument(
        "--control-iters",
        type=int,
        default=0,
        help="Optional ITER override for control_before/control_after rows.",
    )
    parser.add_argument(
        "--treatment-iters",
        type=int,
        default=0,
        help="Optional ITER override for treatment rows.",
    )
    parser.add_argument("--verify-smid", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.cycles <= 0:
        raise ValueError("--cycles must be positive")
    if args.warmup_cycles < 0:
        raise ValueError("--warmup-cycles must be non-negative")
    factors = parse_int_list(args.factor_values)

    warmup_output = args.warmup_output
    if not warmup_output:
        out = Path(args.output)
        warmup_output = str(out.with_name(out.stem + "_warmup" + out.suffix))

    warmup_rows = sequence_rows(
        args,
        phase="warmup",
        cycles=args.warmup_cycles,
        output=warmup_output,
        seconds=args.warmup_seconds,
        factors=factors,
    )
    measure_rows = sequence_rows(
        args,
        phase="measure",
        cycles=args.cycles,
        output=args.output,
        seconds=args.seconds,
        factors=factors,
    )
    rows = warmup_rows + measure_rows
    write_matrix(Path(args.matrix_csv), rows)

    print(f"wrote matrix: {args.matrix_csv}")
    print(f"factor: {args.factor_name}={','.join(str(v) for v in factors)}")
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
