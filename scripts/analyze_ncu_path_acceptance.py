#!/usr/bin/env python3
"""Classify NCU validation rows as accepted/provisional/rejected.

This is intentionally stricter than the raw NCU summary. A row is accepted only
when the measured counters prove the intended path. Rows that execute but lack a
required denominator, such as shared bytes, are provisional rather than final.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import median


def f(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def ratio(num: float, den: float) -> float:
    return num / den if den > 0.0 else math.inf


def expected_shared_bytes(row: dict[str, str]) -> float:
    active_sm = f(row, "active_SM")
    blocks = f(row, "blocks_per_SM")
    iters = f(row, "ITER")
    load_repeat = f(row, "load_repeat", 1.0)
    return active_sm * blocks * iters * load_repeat * 1024.0


def expected_register_ops(row: dict[str, str]) -> float:
    active_sm = f(row, "active_SM")
    blocks = f(row, "blocks_per_SM")
    iters = f(row, "ITER")
    reuse = f(row, "reuse_factor", 1.0)
    return active_sm * blocks * iters * reuse


def memory_reason_if_high(
    *,
    value: float,
    absolute_max: float,
    ratio_denominator: float,
    ratio_max: float,
    reason: str,
) -> str | None:
    if value <= absolute_max:
        return None
    if ratio_denominator > 0.0 and ratio(value, ratio_denominator) <= ratio_max:
        return None
    return reason


def classify(row: dict[str, str], args: argparse.Namespace) -> dict[str, str]:
    mode = row.get("mode", "")
    ncu_status = row.get("status", "")
    status = "rejected"
    component = "not_selected"
    reasons: list[str] = []

    if ncu_status != "ok":
        reasons.append(f"ncu_status_{ncu_status or 'missing'}")

    l1_hit = f(row, "l1_hit_rate_pct", -1.0)
    l2_hit = f(row, "l2_hit_rate_pct", -1.0)
    l1_bytes = f(row, "l1_bytes")
    l2_bytes = f(row, "l2_bytes")
    dram_bytes = f(row, "dram_bytes")
    shared_bytes = f(row, "shared_bytes")
    shared_accesses = f(row, "shared_accesses")
    shared_bank_conflicts = f(row, "shared_bank_conflicts")
    shared_inst = f(row, "shared_inst")
    tensor_hmma = f(row, "tensor_hmma_inst")
    spill_read = f(row, "spill_local_read_inst")
    spill_write = f(row, "spill_local_write_inst")

    if spill_read > 0.0 or spill_write > 0.0:
        reasons.append("local_spill_traffic_present")

    if mode == "global_l1_load_only":
        component = "global_l1_hit_path"
        if l1_hit < args.l1_hit_min_pct:
            reasons.append("l1_hit_below_threshold")
        if l1_bytes <= 0.0:
            reasons.append("missing_l1_bytes")
        if ratio(l2_bytes, l1_bytes) > args.l1_l2_ratio_max:
            reasons.append("l2_traffic_too_high_for_l1")
        if ratio(dram_bytes, l1_bytes) > args.l1_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_l1")

    elif mode == "l2_cg_load_only":
        component = "l2_hit_path"
        if l1_hit > args.l2_l1_hit_max_pct:
            reasons.append("l1_hit_too_high_for_l2")
        if l2_hit < args.l2_hit_min_pct:
            reasons.append("l2_hit_below_threshold")
        if l2_bytes <= 0.0:
            reasons.append("missing_l2_bytes")
        if ratio(dram_bytes, l2_bytes) > args.l2_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_l2")

    elif mode == "l2_load_only":
        component = "l2_capacity_candidate"
        if l1_hit > args.l2_l1_hit_max_pct:
            reasons.append("l1_hit_too_high_for_l2")
        if l2_hit < args.l2_hit_min_pct:
            reasons.append("l2_hit_below_threshold")
        if ratio(dram_bytes, l2_bytes) > args.l2_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_l2")

    elif mode in {"shared_scalar_load_only", "shared_load_only"}:
        component = "shared_memory_path"
        expected = expected_shared_bytes(row)
        if shared_accesses <= 0.0:
            reasons.append("missing_shared_accesses")
        if shared_bytes <= 0.0:
            reasons.append("missing_shared_bytes")
        else:
            observed_expected_ratio = ratio(shared_bytes, expected)
            if not (args.shared_expected_ratio_min <= observed_expected_ratio <= args.shared_expected_ratio_max):
                reasons.append("shared_bytes_expected_mismatch")
        if ratio(l1_bytes, max(shared_bytes, expected, 1.0)) > args.shared_global_ratio_max:
            reasons.append("global_l1_traffic_too_high_for_shared")
        if ratio(l2_bytes, max(shared_bytes, expected, 1.0)) > args.shared_global_ratio_max:
            reasons.append("l2_traffic_too_high_for_shared")
        if ratio(dram_bytes, max(shared_bytes, expected, 1.0)) > args.shared_global_ratio_max:
            reasons.append("dram_traffic_too_high_for_shared")
        if shared_bank_conflicts > 0.0 and ratio(shared_bank_conflicts, max(shared_accesses, 1.0)) > args.shared_bank_conflict_ratio_max:
            reasons.append("shared_bank_conflicts_high")
        if shared_inst <= 0.0:
            reasons.append("missing_shared_instruction_count")

    elif mode == "reg_mma":
        component = "tensor_increment_candidate"
        if tensor_hmma <= 0.0:
            reasons.append("missing_tensor_hmma")
        for value, reason in [
            (l1_bytes, "l1_traffic_too_high_for_tensor"),
            (l2_bytes, "l2_traffic_too_high_for_tensor"),
            (dram_bytes, "dram_traffic_too_high_for_tensor"),
        ]:
            maybe_reason = memory_reason_if_high(
                value=value,
                absolute_max=args.tensor_memory_bytes_max,
                ratio_denominator=tensor_hmma,
                ratio_max=args.tensor_memory_bytes_per_hmma_max,
                reason=reason,
            )
            if maybe_reason:
                reasons.append(maybe_reason)

    elif mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}:
        component = "register_control_candidate"
        expected_ops = expected_register_ops(row)
        if tensor_hmma > 0.0:
            reasons.append("tensor_hmma_present_in_control")
        for value, reason in [
            (l1_bytes, "l1_traffic_too_high_for_register_control"),
            (l2_bytes, "l2_traffic_too_high_for_register_control"),
            (dram_bytes, "dram_traffic_too_high_for_register_control"),
        ]:
            maybe_reason = memory_reason_if_high(
                value=value,
                absolute_max=args.register_memory_bytes_max,
                ratio_denominator=expected_ops,
                ratio_max=args.register_memory_bytes_per_op_max,
                reason=reason,
            )
            if maybe_reason:
                reasons.append(maybe_reason)

    elif mode == "dram_cg_load_only":
        component = "dram_sanity_path"
        if l1_hit > args.dram_l1_hit_max_pct:
            reasons.append("l1_hit_too_high_for_dram")
        if l2_hit > args.dram_l2_hit_max_pct:
            reasons.append("l2_hit_too_high_for_dram")
        if dram_bytes <= 0.0:
            reasons.append("missing_dram_bytes")
        if ratio(dram_bytes, l2_bytes) < args.dram_l2_ratio_min:
            reasons.append("dram_not_dominant_over_l2")

    else:
        reasons.append("mode_not_final_component_candidate")

    if not reasons:
        status = "accepted"
    elif component == "shared_memory_path" and reasons == ["missing_shared_bytes"]:
        status = "provisional"
    elif all(reason.startswith("missing_") for reason in reasons):
        status = "provisional"

    out = dict(row)
    out.update(
        {
            "component_candidate": component,
            "acceptance": status,
            "acceptance_reason": ";".join(reasons) if reasons else "pass",
            "expected_shared_bytes": (
                f"{expected_shared_bytes(row):.6g}"
                if mode in {"shared_scalar_load_only", "shared_load_only"}
                else ""
            ),
            "shared_bytes_to_expected": (
                f"{ratio(shared_bytes, expected_shared_bytes(row)):.6g}"
                if mode in {"shared_scalar_load_only", "shared_load_only"} and shared_bytes > 0.0
                else ""
            ),
            "l2_to_l1_bytes": f"{ratio(l2_bytes, l1_bytes):.6g}" if l1_bytes > 0.0 else "",
            "dram_to_l2_bytes": f"{ratio(dram_bytes, l2_bytes):.6g}" if l2_bytes > 0.0 else "",
            "tensor_l2_bytes_per_hmma": (
                f"{ratio(l2_bytes, tensor_hmma):.6g}"
                if mode == "reg_mma" and tensor_hmma > 0.0
                else ""
            ),
            "tensor_dram_bytes_per_hmma": (
                f"{ratio(dram_bytes, tensor_hmma):.6g}"
                if mode == "reg_mma" and tensor_hmma > 0.0
                else ""
            ),
            "register_l2_bytes_per_op": (
                f"{ratio(l2_bytes, expected_register_ops(row)):.6g}"
                if mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}
                and expected_register_ops(row) > 0.0
                else ""
            ),
            "register_dram_bytes_per_op": (
                f"{ratio(dram_bytes, expected_register_ops(row)):.6g}"
                if mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}
                and expected_register_ops(row) > 0.0
                else ""
            ),
        }
    )
    return out


def write_markdown(rows: list[dict[str, str]], path: Path) -> None:
    by_component: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_component.setdefault(row["component_candidate"], []).append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as out:
        out.write("# NCU Path Acceptance\n\n")
        out.write("Accepted rows are the only rows eligible for final component energy coefficients.\n\n")
        out.write("| component | accepted | provisional | rejected |\n")
        out.write("|---|---:|---:|---:|\n")
        for component, group in sorted(by_component.items()):
            counts = {key: 0 for key in ["accepted", "provisional", "rejected"]}
            for row in group:
                counts[row["acceptance"]] += 1
            out.write(
                f"| {component} | {counts['accepted']} | "
                f"{counts['provisional']} | {counts['rejected']} |\n"
            )

        out.write("\n")
        out.write("| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |\n")
        out.write("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            out.write(
                f"| {row.get('mode','')} | {row['component_candidate']} | "
                f"{row['acceptance']} | {row['acceptance_reason']} | "
                f"{row.get('l1_hit_rate_pct','')} | {row.get('l2_hit_rate_pct','')} | "
                f"{row.get('shared_bytes','')} | {row.get('l1_bytes','')} | "
                f"{row.get('l2_bytes','')} | {row.get('dram_bytes','')} | "
                f"{row.get('stall_long_scoreboard_pct','')} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ncu_summary_csv")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--l1-hit-min-pct", type=float, default=95.0)
    parser.add_argument("--l1-l2-ratio-max", type=float, default=0.01)
    parser.add_argument("--l1-dram-ratio-max", type=float, default=0.01)
    parser.add_argument("--l2-l1-hit-max-pct", type=float, default=1.0)
    parser.add_argument("--l2-hit-min-pct", type=float, default=95.0)
    parser.add_argument("--l2-dram-ratio-max", type=float, default=0.02)
    parser.add_argument("--shared-expected-ratio-min", type=float, default=0.5)
    parser.add_argument("--shared-expected-ratio-max", type=float, default=2.0)
    parser.add_argument("--shared-global-ratio-max", type=float, default=0.02)
    parser.add_argument("--shared-bank-conflict-ratio-max", type=float, default=0.05)
    parser.add_argument("--tensor-memory-bytes-max", type=float, default=1.0e8)
    parser.add_argument("--register-memory-bytes-max", type=float, default=1.0e8)
    parser.add_argument("--tensor-memory-bytes-per-hmma-max", type=float, default=1.0)
    parser.add_argument("--register-memory-bytes-per-op-max", type=float, default=1.0)
    parser.add_argument("--dram-l1-hit-max-pct", type=float, default=1.0)
    parser.add_argument("--dram-l2-hit-max-pct", type=float, default=5.0)
    parser.add_argument("--dram-l2-ratio-min", type=float, default=0.5)
    args = parser.parse_args()

    with Path(args.ncu_summary_csv).open(newline="") as f:
        rows = [classify(dict(row), args) for row in csv.DictReader(f)]

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    write_markdown(rows, Path(args.out_md))
    print(f"rows: {len(rows)}")
    print(f"accepted: {sum(1 for row in rows if row['acceptance'] == 'accepted')}")
    print(f"provisional: {sum(1 for row in rows if row['acceptance'] == 'provisional')}")
    print(f"rejected: {sum(1 for row in rows if row['acceptance'] == 'rejected')}")
    print(f"wrote csv: {out_csv}")
    print(f"wrote markdown: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
