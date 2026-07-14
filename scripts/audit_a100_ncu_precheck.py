#!/usr/bin/env python3
"""Fail-fast A100 Tensor/L2 NCU gate before the long energy sweep."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path


def as_float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def as_int(row: dict[str, str], key: str, default: int = -1) -> int:
    value = as_float(row, key)
    return int(value) if math.isfinite(value) else default


def parse_ints(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values or any(item <= 0 for item in values):
        raise ValueError("expected a comma-separated list of positive integers")
    return values


def select(
    rows: list[dict[str, str]],
    *,
    mode: str,
    blocks_per_sm: int,
    active_sm: int,
    reuse_factor: int | None = None,
    load_repeat: int | None = None,
    w_sm_kib: int | None = None,
) -> list[dict[str, str]]:
    selected = []
    for row in rows:
        if row.get("mode") != mode:
            continue
        if as_int(row, "blocks_per_SM") != blocks_per_sm:
            continue
        if as_int(row, "active_SM") != active_sm:
            continue
        if reuse_factor is not None and as_int(row, "reuse_factor") != reuse_factor:
            continue
        if load_repeat is not None and as_int(row, "load_repeat") != load_repeat:
            continue
        if w_sm_kib is not None and as_int(row, "W_SM_KiB") != w_sm_kib:
            continue
        selected.append(row)
    return selected


def policy_ok(
    row: dict[str, str],
    *,
    replay_mode: str,
    cache_control: str,
    warmup_passes: int,
    residency_policy: str,
    address_layout: str,
) -> bool:
    return (
        row.get("acceptance") == "accepted"
        and row.get("ncu_replay_mode") == replay_mode
        and row.get("ncu_cache_control") == cache_control
        and as_int(row, "global_warmup_passes") == warmup_passes
        and row.get("l2_residency_policy") == residency_policy
        and row.get("l2_address_layout", "contiguous") == address_layout
    )


def check_row(
    area: str,
    coordinate: str,
    passed: bool,
    expected: str,
    actual: str,
) -> dict[str, str]:
    return {
        "area": area,
        "coordinate": coordinate,
        "status": "pass" if passed else "fail",
        "expected": expected,
        "actual": actual,
    }


def audit_rows(
    rows: list[dict[str, str]],
    *,
    expected_rf: tuple[int, ...],
    expected_w: tuple[int, ...],
    expected_lr: tuple[int, ...],
    tensor_blocks_per_sm: int,
    l2_blocks_per_sm: int,
    active_sm: int,
    replay_mode: str,
    cache_control: str,
    warmup_passes: int,
    l2_residency_policy: str,
    l2_address_layout: str,
    hmma_ratio_spread_max: float,
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    hmma_ratios: list[float] = []

    for rf in expected_rf:
        treatment_rows = select(
            rows,
            mode="reg_mma",
            blocks_per_sm=tensor_blocks_per_sm,
            active_sm=active_sm,
            reuse_factor=rf,
            w_sm_kib=2048,
        )
        control_rows = select(
            rows,
            mode="reg_operand_only",
            blocks_per_sm=tensor_blocks_per_sm,
            active_sm=active_sm,
            reuse_factor=rf,
            w_sm_kib=2048,
        )
        treatment = treatment_rows[0] if len(treatment_rows) == 1 else {}
        control = control_rows[0] if len(control_rows) == 1 else {}
        logical_mma = as_float(treatment, "expected_logical_mma")
        hmma = as_float(treatment, "tensor_hmma_inst", 0.0)
        hmma_ratio = as_float(treatment, "tensor_hmma_per_logical_mma")
        expected_logical_mma = (
            active_sm
            * tensor_blocks_per_sm
            * as_int(treatment, "ITER", 0)
            * rf
        )
        passed = (
            len(treatment_rows) == 1
            and len(control_rows) == 1
            and policy_ok(
                treatment,
                replay_mode=replay_mode,
                cache_control=cache_control,
                warmup_passes=warmup_passes,
                residency_policy="normal",
                address_layout="contiguous",
            )
            and policy_ok(
                control,
                replay_mode=replay_mode,
                cache_control=cache_control,
                warmup_passes=warmup_passes,
                residency_policy="normal",
                address_layout="contiguous",
            )
            and hmma > 0.0
            and logical_mma == expected_logical_mma
            and hmma_ratio > 0.0
            and abs(hmma_ratio - hmma / logical_mma)
            <= max(1.0e-12, 1.0e-9 * hmma_ratio)
            and as_float(control, "tensor_hmma_inst", -1.0) == 0.0
            and all(
                as_float(row, field, -1.0) == 0.0
                for row in (treatment, control)
                for field in ("local_read_bytes", "local_write_bytes")
            )
        )
        if passed:
            hmma_ratios.append(hmma_ratio)
        checks.append(
            check_row(
                "tensor",
                f"B{tensor_blocks_per_sm}/RF{rf}",
                passed,
                "one accepted treatment/control row, control HMMA=0, spill/local=0, valid logical-MMA ratio",
                (
                    f"rows={len(treatment_rows)}/{len(control_rows)}; HMMA={hmma:g}; "
                    f"logical_MMA={logical_mma:g}; ratio={hmma_ratio:g}"
                ),
            )
        )

    ratio_center = statistics.median(hmma_ratios) if hmma_ratios else math.nan
    ratio_spread = (
        (max(hmma_ratios) - min(hmma_ratios)) / ratio_center
        if len(hmma_ratios) == len(expected_rf) and ratio_center > 0.0
        else math.inf
    )
    checks.append(
        check_row(
            "tensor",
            "RF-scaling",
            len(hmma_ratios) == len(expected_rf)
            and ratio_spread <= hmma_ratio_spread_max,
            f"HMMA/logical-MMA relative spread <= {100 * hmma_ratio_spread_max:g}%",
            f"ratios={','.join(f'{value:g}' for value in hmma_ratios)}; spread={100 * ratio_spread:g}%",
        )
    )

    for w_sm_kib in expected_w:
        for load_repeat in expected_lr:
            treatment_rows = select(
                rows,
                mode="l2_cg_load_only",
                blocks_per_sm=l2_blocks_per_sm,
                active_sm=active_sm,
                load_repeat=load_repeat,
                w_sm_kib=w_sm_kib,
            )
            control_rows = select(
                rows,
                mode="global_addr_only",
                blocks_per_sm=l2_blocks_per_sm,
                active_sm=active_sm,
                load_repeat=load_repeat,
                w_sm_kib=w_sm_kib,
            )
            treatment = treatment_rows[0] if len(treatment_rows) == 1 else {}
            control = control_rows[0] if len(control_rows) == 1 else {}
            l1_request = as_float(treatment, "l1_request_bytes", 0.0)
            l1_hit = as_float(treatment, "l1_hit_bytes", math.inf)
            l2_read = as_float(treatment, "l2_read_bytes", 0.0)
            dram_read = as_float(treatment, "dram_read_bytes", math.inf)
            direct_l2_hit = as_float(treatment, "l2_path_hit_rate_pct")
            logical_l2_hit = as_float(
                treatment, "l2_logical_read_hit_rate_pct"
            )
            native_l2_hit = as_float(
                treatment, "l2_native_read_hit_rate_pct"
            )
            native_model_delta = as_float(
                treatment, "l2_native_vs_fabric_model_hit_delta_pct"
            )
            fabric_metrics_present = as_float(
                treatment, "l2_fabric_metrics_present", 0.0
            )
            fabric_counter_coherent = as_float(
                treatment, "l2_fabric_counter_coherent", 0.0
            )
            fabric_model_coherent = as_float(
                treatment, "l2_fabric_model_coherent", 0.0
            )
            fabric_fraction = as_float(
                treatment, "l2_fabric_read_fraction"
            )
            sector_conservation = as_float(
                treatment, "l2_read_sector_conservation_ratio"
            )
            traffic_ratio = as_float(treatment, "l2_read_bytes_to_expected")
            persisting_size = as_float(
                treatment, "launch_persisting_l2_cache_size_bytes", 0.0
            )
            control_expected = (
                active_sm
                * l2_blocks_per_sm
                * as_int(control, "ITER", 0)
                * load_repeat
                * 1024
            )
            control_dram_read_ratio = (
                as_float(control, "dram_read_bytes", math.inf) / control_expected
                if control_expected > 0
                else math.inf
            )
            passed = (
                len(treatment_rows) == 1
                and len(control_rows) == 1
                and policy_ok(
                    treatment,
                    replay_mode=replay_mode,
                    cache_control=cache_control,
                    warmup_passes=warmup_passes,
                    residency_policy=l2_residency_policy,
                    address_layout=l2_address_layout,
                )
                and policy_ok(
                    control,
                    replay_mode=replay_mode,
                    cache_control=cache_control,
                    warmup_passes=warmup_passes,
                    residency_policy=l2_residency_policy,
                    address_layout=l2_address_layout,
                )
                and 0.0 <= as_float(treatment, "l1_path_hit_rate_pct") <= 1.0
                and l1_request > 0.0
                and l1_hit / l1_request <= 0.01
                and fabric_metrics_present == 1.0
                and fabric_counter_coherent == 1.0
                and fabric_model_coherent == 1.0
                and 95.0 <= logical_l2_hit <= 100.5
                and math.isfinite(native_l2_hit)
                and native_model_delta <= 2.0
                and 0.98 <= sector_conservation <= 1.02
                and 0.95 <= traffic_ratio <= 1.05
                and l2_read > 0.0
                and dram_read / l2_read <= 0.02
                and (
                    l2_residency_policy != "persisting"
                    or persisting_size > 0.0
                )
                and as_float(control, "l1_request_bytes", -1.0) == 0.0
                and control_dram_read_ratio <= 0.001
            )
            checks.append(
                check_row(
                    "l2",
                    f"W{w_sm_kib}/B{l2_blocks_per_sm}/LR{load_repeat}",
                    passed,
                    "accepted treatment/control, L1 path<=1%, GA100 source+LTC-fabric logical L2 hit=95-100.5%, coherent fabric/native model (<=2pp), sector conservation=1+/-2%, traffic/expected=1+/-5%, DRAM-read/L2<=2%",
                    (
                        f"rows={len(treatment_rows)}/{len(control_rows)}; "
                        f"L1={as_float(treatment, 'l1_path_hit_rate_pct'):g}%; "
                        f"L2-direct={direct_l2_hit:g}%/logical={logical_l2_hit:g}%/"
                        f"native={native_l2_hit:g}%; native-model-delta={native_model_delta:g}pp; "
                        f"fabric_fraction={fabric_fraction:g}; "
                        f"fabric_coherent={fabric_counter_coherent:g}/{fabric_model_coherent:g}; "
                        f"sector_conservation={sector_conservation:g}; "
                        f"traffic/expected={traffic_ratio:g}; "
                        f"DRAM-read/L2={100 * dram_read / l2_read if l2_read > 0.0 else math.inf:g}%; "
                        f"persisting_size={persisting_size:g}B"
                    ),
                )
            )

    failures = sum(row["status"] != "pass" for row in checks)
    checks.append(
        check_row(
            "overall",
            "a100-ncu-precheck",
            failures == 0,
            "all Tensor RF and L2 W/LR rows pass before energy measurement",
            f"failed_checks={failures}",
        )
    )
    return checks


def write_outputs(rows: list[dict[str, str]], csv_path: Path, md_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write("# A100 Tensor/L2 NCU Precheck\n\n")
        handle.write("| area | coordinate | status | expected | actual |\n")
        handle.write("|---|---|---|---|---|\n")
        for row in rows:
            handle.write(
                f"| {row['area']} | `{row['coordinate']}` | {row['status']} | "
                f"{row['expected']} | {row['actual']} |\n"
            )


def self_test() -> None:
    rows: list[dict[str, str]] = []
    for rf in (1, 16):
        logical = 108 * 16 * 100000 * rf
        for mode in ("reg_operand_only", "reg_mma"):
            rows.append(
                {
                    "mode": mode,
                    "acceptance": "accepted",
                    "W_SM_KiB": "2048",
                    "blocks_per_SM": "16",
                    "active_SM": "108",
                    "ITER": "100000",
                    "reuse_factor": str(rf),
                    "load_repeat": "1",
                    "ncu_replay_mode": "application",
                    "ncu_cache_control": "none",
                    "global_warmup_passes": "4",
                    "l2_residency_policy": "normal",
                    "l2_address_layout": "contiguous",
                    "tensor_hmma_inst": str(2 * logical if mode == "reg_mma" else 0),
                    "expected_logical_mma": str(logical if mode == "reg_mma" else ""),
                    "tensor_hmma_per_logical_mma": "2" if mode == "reg_mma" else "",
                    "local_read_bytes": "0",
                    "local_write_bytes": "0",
                }
            )
    for w_sm_kib in (16, 128):
        for mode in ("global_addr_only", "l2_cg_load_only"):
            rows.append(
                {
                    "mode": mode,
                    "acceptance": "accepted",
                    "W_SM_KiB": str(w_sm_kib),
                    "blocks_per_SM": "16",
                    "active_SM": "108",
                    "ITER": "100000",
                    "reuse_factor": "1",
                    "load_repeat": "4",
                    "ncu_replay_mode": "application",
                    "ncu_cache_control": "none",
                    "global_warmup_passes": "4",
                    "l2_residency_policy": "persisting",
                    "l2_address_layout": "sm_interleaved",
                    "l1_path_hit_rate_pct": "0",
                    "l2_path_hit_rate_pct": "55",
                    "l2_logical_read_hit_rate_pct": "99.5",
                    "l2_native_read_hit_rate_pct": "68.62",
                    "l2_native_vs_fabric_model_hit_delta_pct": "0.01",
                    "l2_fabric_metrics_present": "1",
                    "l2_fabric_counter_coherent": "1",
                    "l2_fabric_model_coherent": "1",
                    "l2_fabric_read_fraction": "0.310345",
                    "l2_read_sector_conservation_ratio": "1",
                    "l2_read_bytes_to_expected": "1",
                    "launch_persisting_l2_cache_size_bytes": "34603008",
                    "l1_request_bytes": "100000" if mode == "l2_cg_load_only" else "0",
                    "l1_hit_bytes": "0",
                    "l2_read_bytes": "100000" if mode == "l2_cg_load_only" else "0",
                    "dram_read_bytes": "100" if mode == "l2_cg_load_only" else "1000",
                    "dram_bytes": "100" if mode == "l2_cg_load_only" else "1000",
                }
            )
    checks = audit_rows(
        rows,
        expected_rf=(1, 16),
        expected_w=(16, 128),
        expected_lr=(4,),
        tensor_blocks_per_sm=16,
        l2_blocks_per_sm=16,
        active_sm=108,
        replay_mode="application",
        cache_control="none",
        warmup_passes=4,
        l2_residency_policy="persisting",
        l2_address_layout="sm_interleaved",
        hmma_ratio_spread_max=0.10,
    )
    assert checks[-1]["status"] == "pass", checks[-1]
    bad = [dict(row) for row in rows]
    next(
        row
        for row in bad
        if row["mode"] == "l2_cg_load_only" and row["W_SM_KiB"] == "128"
    )["l2_logical_read_hit_rate_pct"] = "60"
    checks = audit_rows(
        bad,
        expected_rf=(1, 16),
        expected_w=(16, 128),
        expected_lr=(4,),
        tensor_blocks_per_sm=16,
        l2_blocks_per_sm=16,
        active_sm=108,
        replay_mode="application",
        cache_control="none",
        warmup_passes=4,
        l2_residency_policy="persisting",
        l2_address_layout="sm_interleaved",
        hmma_ratio_spread_max=0.10,
    )
    assert checks[-1]["status"] == "fail", checks[-1]
    print("A100 Tensor/L2 NCU precheck self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("acceptance_csv", nargs="?")
    parser.add_argument("--expected-rf", default="1,2,4,8,16")
    parser.add_argument("--expected-w", default="16,32,64,128")
    parser.add_argument("--expected-lr", default="1,2,4,8,16")
    parser.add_argument("--blocks-per-sm", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--tensor-blocks-per-sm", type=int, default=16)
    parser.add_argument("--l2-blocks-per-sm", type=int, default=16)
    parser.add_argument("--active-sm", type=int, default=108)
    parser.add_argument("--ncu-replay-mode", default="application")
    parser.add_argument("--ncu-cache-control", default="none")
    parser.add_argument("--global-warmup-passes", type=int, default=4)
    parser.add_argument(
        "--l2-residency-policy", choices=("normal", "persisting"), required=False
    )
    parser.add_argument(
        "--l2-address-layout",
        choices=("contiguous", "sm_interleaved"),
        default="contiguous",
    )
    parser.add_argument("--hmma-ratio-spread-max", type=float, default=0.10)
    parser.add_argument("--out-csv", default="results/summary/a100_ncu_precheck.csv")
    parser.add_argument("--out-md", default="results/summary/a100_ncu_precheck.md")
    parser.add_argument("--fail-on-fail", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.acceptance_csv or not args.l2_residency_policy:
        parser.error("acceptance_csv and --l2-residency-policy are required")
    with Path(args.acceptance_csv).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    checks = audit_rows(
        rows,
        expected_rf=parse_ints(args.expected_rf),
        expected_w=parse_ints(args.expected_w),
        expected_lr=parse_ints(args.expected_lr),
        tensor_blocks_per_sm=(
            args.blocks_per_sm
            if args.blocks_per_sm is not None
            else args.tensor_blocks_per_sm
        ),
        l2_blocks_per_sm=(
            args.blocks_per_sm
            if args.blocks_per_sm is not None
            else args.l2_blocks_per_sm
        ),
        active_sm=args.active_sm,
        replay_mode=args.ncu_replay_mode,
        cache_control=args.ncu_cache_control,
        warmup_passes=args.global_warmup_passes,
        l2_residency_policy=args.l2_residency_policy,
        l2_address_layout=args.l2_address_layout,
        hmma_ratio_spread_max=args.hmma_ratio_spread_max,
    )
    write_outputs(checks, Path(args.out_csv), Path(args.out_md))
    failures = sum(row["status"] != "pass" for row in checks)
    print(f"A100 NCU precheck rows={len(checks)} nonpass={failures}")
    return 2 if args.fail_on_fail and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
