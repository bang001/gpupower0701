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


PROFILE_L2_MIB = {
    "v100": 6.0,
    "rtx3090": 6.0,
    "a100": 40.0,
    "h100": 50.0,
}


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


def launched_blocks(row: dict[str, str]) -> float:
    return f(row, "active_SM") * f(row, "blocks_per_SM")


def expected_l2_residency_hit_pct(
    row: dict[str, str], target_profile: str
) -> float:
    """Return the cache-capacity upper-bound context for a DRAM stream.

    A streaming working set larger than L2 can still retain a small fraction of
    lines in L2. Treating every hit above a fixed 5% as a failure is wrong on
    large-L2 GPUs such as GA100 and GH100.
    """

    l2_mib = PROFILE_L2_MIB.get(target_profile, 0.0)
    working_set_mib = f(row, "active_SM") * f(row, "W_SM_KiB") / 1024.0
    if l2_mib <= 0.0 or working_set_mib <= 0.0:
        return 0.0
    return min(100.0, 100.0 * l2_mib / working_set_mib)


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
    l1_request_bytes = f(row, "l1_request_bytes", l1_bytes)
    l1_hit_bytes = f(row, "l1_hit_bytes")
    l1_path_hit = f(row, "l1_path_hit_rate_pct", l1_hit)
    l2_read_bytes = f(row, "l2_read_bytes", l2_bytes)
    l2_path_hit = f(row, "l2_path_hit_rate_pct", l2_hit)
    has_l1_request_bytes = bool(row.get("l1_request_bytes", "").strip())
    has_l1_hit_bytes = bool(row.get("l1_hit_bytes", "").strip())
    has_l1_path_hit = bool(row.get("l1_path_hit_rate_pct", "").strip())
    has_l2_read_bytes = bool(row.get("l2_read_bytes", "").strip())
    has_l2_path_hit = bool(row.get("l2_path_hit_rate_pct", "").strip())
    dram_bytes = f(row, "dram_bytes")
    shared_bytes = f(row, "shared_bytes")
    shared_accesses = f(row, "shared_accesses")
    shared_bank_conflicts = f(row, "shared_bank_conflicts")
    shared_inst = f(row, "shared_inst")
    tensor_hmma = f(row, "tensor_hmma_inst")
    local_read_bytes = f(row, "local_read_bytes")
    local_write_bytes = f(row, "local_write_bytes")
    spill_zero_verified = f(row, "spill_zero_verified", -1.0)
    spill_read = f(row, "spill_local_read_inst")
    spill_write = f(row, "spill_local_write_inst")
    control_hmma_class = ""
    control_hmma_per_block = 0.0
    control_hmma_per_reg_op = 0.0
    dram_expected_l2_hit_pct = 0.0
    dram_l2_hit_limit_pct = args.dram_l2_hit_max_pct
    address_control_dram_ratio = 0.0

    if not row.get("spill_zero_verified", "").strip():
        reasons.append("missing_spill_zero_evidence")
    elif (
        spill_read > 0.0
        or spill_write > 0.0
        or local_read_bytes > 0.0
        or local_write_bytes > 0.0
        or spill_zero_verified != 1.0
    ):
        reasons.append("local_spill_traffic_present")

    if mode == "global_l1_load_only":
        component = "global_l1_hit_path"
        if l1_path_hit < args.l1_hit_min_pct:
            reasons.append("l1_hit_below_threshold")
        if l1_request_bytes <= 0.0:
            reasons.append("missing_l1_bytes")
        if not has_l2_read_bytes:
            reasons.append("missing_l2_read_bytes_for_l1")
        elif ratio(l2_read_bytes, l1_request_bytes) > args.l1_l2_ratio_max:
            reasons.append("l2_traffic_too_high_for_l1")
        if ratio(dram_bytes, l1_request_bytes) > args.l1_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_l1")

    elif mode == "l2_cg_load_only":
        component = "l2_hit_path"
        if not has_l2_path_hit:
            reasons.append("missing_l2_path_hit_rate")
        elif l2_path_hit < args.l2_hit_min_pct:
            reasons.append("l2_hit_below_threshold")
        if not has_l2_read_bytes or l2_read_bytes <= 0.0:
            reasons.append("missing_l2_read_bytes")
        if not has_l1_request_bytes or l1_request_bytes <= 0.0:
            reasons.append("missing_l1_request_bytes_for_l2_cg")
        if not has_l1_path_hit:
            reasons.append("missing_l1_path_hit_rate_for_l2_cg")
        elif l1_path_hit > args.l2_l1_hit_max_pct:
            reasons.append("l1_cache_hit_too_high_for_l2_cg")
        if not has_l1_hit_bytes:
            reasons.append("missing_l1_hit_bytes_for_l2_cg")
        elif ratio(l1_hit_bytes, l1_request_bytes) > args.l2_l1_bytes_ratio_max:
            reasons.append("l1_hit_bytes_too_high_for_l2_cg")
        if ratio(dram_bytes, l2_read_bytes) > args.l2_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_l2")

    elif mode == "l2_load_only":
        component = "l2_capacity_diagnostic"
        reasons.append("l2_load_only_is_not_l2_bypass_path")

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

    elif mode == "global_addr_only":
        component = "global_address_control"
        # This control must retain index arithmetic but issue no global input
        # loads. SMID verification uses global atomics, which can appear as
        # L2 sectors; only global-load bytes and DRAM scale are meaningful here.
        if l1_request_bytes > 0.0:
            reasons.append("global_load_traffic_present_in_address_control")
        expected_input_bytes = expected_shared_bytes(row)
        address_control_dram_ratio = ratio(dram_bytes, expected_input_bytes)
        if address_control_dram_ratio > args.global_address_control_dram_ratio_max:
            reasons.append("dram_traffic_too_high_for_address_control")

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
        control_hmma_per_block = ratio(tensor_hmma, launched_blocks(row))
        control_hmma_per_reg_op = ratio(tensor_hmma, expected_ops)
        if mode == "reg_operand_only" and tensor_hmma > 0.0:
            reasons.append("tensor_hmma_present_in_control")
            control_hmma_class = "strict_no_hmma_reject"
        elif tensor_hmma > 0.0:
            fixed_epilogue_limit = (
                launched_blocks(row) * args.control_hmma_per_block_max
            )
            if (
                tensor_hmma > fixed_epilogue_limit
                and control_hmma_per_reg_op > args.control_hmma_per_reg_op_max
            ):
                reasons.append("tensor_hmma_workload_proportional_in_control")
                control_hmma_class = "workload_proportional_reject"
            else:
                control_hmma_class = "fixed_epilogue_allowed"
        elif mode == "reg_operand_only":
            control_hmma_class = "strict_no_hmma_pass"
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
        if not has_l1_path_hit:
            reasons.append("missing_l1_path_hit_rate_for_dram")
        elif l1_path_hit > args.dram_l1_hit_max_pct:
            reasons.append("l1_hit_too_high_for_dram")
        if not has_l2_path_hit:
            reasons.append("missing_l2_path_hit_rate_for_dram")
        dram_expected_l2_hit_pct = expected_l2_residency_hit_pct(
            row, args.target_profile
        )
        dram_l2_hit_limit_pct = max(
            args.dram_l2_hit_max_pct,
            dram_expected_l2_hit_pct * args.dram_l2_expected_multiplier
            + args.dram_l2_expected_slack_pct,
        )
        if has_l2_path_hit and l2_path_hit > dram_l2_hit_limit_pct:
            reasons.append("l2_hit_too_high_for_dram")
        if dram_bytes <= 0.0:
            reasons.append("missing_dram_bytes")
        if not has_l2_read_bytes or l2_read_bytes <= 0.0:
            reasons.append("missing_l2_read_bytes_for_dram")
        elif ratio(dram_bytes, l2_read_bytes) < args.dram_l2_ratio_min:
            reasons.append("dram_not_dominant_over_l2")

    else:
        reasons.append("mode_not_final_component_candidate")

    if not reasons:
        status = "accepted"
    elif component == "shared_memory_path" and reasons == ["missing_shared_bytes"]:
        status = "provisional"
    elif component != "l2_hit_path" and all(
        reason.startswith("missing_") for reason in reasons
    ):
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
            "l2_to_l1_bytes": f"{ratio(l2_read_bytes, l1_request_bytes):.6g}" if l1_request_bytes > 0.0 else "",
            "dram_to_l2_bytes": f"{ratio(dram_bytes, l2_read_bytes):.6g}" if l2_read_bytes > 0.0 else "",
            "l1_hit_to_request_bytes": (
                f"{ratio(l1_hit_bytes, l1_request_bytes):.6g}"
                if l1_request_bytes > 0.0 and has_l1_hit_bytes
                else ""
            ),
            "l1_request_to_l2_read_bytes": (
                f"{ratio(l1_request_bytes, l2_read_bytes):.6g}"
                if l2_read_bytes > 0.0
                else ""
            ),
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
            "tensor_control_hmma_class": control_hmma_class,
            "tensor_control_hmma_per_block": (
                f"{control_hmma_per_block:.6g}"
                if mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}
                else ""
            ),
            "tensor_control_hmma_per_reg_op": (
                f"{control_hmma_per_reg_op:.6g}"
                if mode in {"reg_operand_only", "reg_fragment_only", "reg_pressure"}
                else ""
            ),
            "dram_expected_l2_hit_pct": (
                f"{dram_expected_l2_hit_pct:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "dram_l2_hit_limit_pct": (
                f"{dram_l2_hit_limit_pct:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "global_address_control_dram_to_expected": (
                f"{address_control_dram_ratio:.6g}"
                if mode == "global_addr_only"
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
        out.write(
            "| mode | component | acceptance | reason | L1 path hit (%) | L2 read hit (%) | "
            "L1 accesses | L2 accesses | DRAM accesses | shared bytes | "
            "L1 request bytes | L1 hit bytes | L2 read bytes | DRAM bytes | long SB (%) |\n"
        )
        out.write("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            l1_accesses = row.get("l1_accesses", "")
            if l1_accesses and row.get("l1_access_unit"):
                l1_accesses = f"{l1_accesses} {row['l1_access_unit']}"
            l2_accesses = row.get("l2_accesses", "")
            if l2_accesses and row.get("l2_access_unit"):
                l2_accesses = f"{l2_accesses} {row['l2_access_unit']}"
            dram_accesses = row.get("dram_accesses", "")
            if dram_accesses and row.get("dram_access_unit"):
                dram_accesses = f"{dram_accesses} {row['dram_access_unit']}"
            out.write(
                f"| {row.get('mode','')} | {row['component_candidate']} | "
                f"{row['acceptance']} | {row['acceptance_reason']} | "
                f"{row.get('l1_path_hit_rate_pct','')} | {row.get('l2_path_hit_rate_pct','')} | "
                f"{l1_accesses} | {l2_accesses} | {dram_accesses} | "
                f"{row.get('shared_bytes','')} | {row.get('l1_request_bytes','')} | "
                f"{row.get('l1_hit_bytes','')} | {row.get('l2_read_bytes','')} | "
                f"{row.get('dram_bytes','')} | "
                f"{row.get('stall_long_scoreboard_pct','')} |\n"
            )
        out.write("\n")
        out.write(
            "Cache-path evidence rule: accepted memory-path rows must expose hit-rate "
            "evidence and at least the path-relevant byte/access counters. L1 accesses "
            "use request counters when available and otherwise fall back to sectors; "
            "L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes "
            "are expected because the request traverses L1TEX; bypass is proven by "
            "near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. "
            "L2 read bytes are the preferred L2 pJ/bit denominator.\n"
        )


def self_test_args() -> argparse.Namespace:
    return argparse.Namespace(
        target_profile="a100",
        l1_hit_min_pct=95.0,
        l1_l2_ratio_max=0.01,
        l1_dram_ratio_max=0.01,
        l2_l1_hit_max_pct=1.0,
        l2_l1_bytes_ratio_max=0.01,
        l2_hit_min_pct=95.0,
        l2_dram_ratio_max=0.02,
        shared_expected_ratio_min=0.5,
        shared_expected_ratio_max=2.0,
        shared_global_ratio_max=0.02,
        shared_bank_conflict_ratio_max=0.05,
        tensor_memory_bytes_max=1.0e8,
        register_memory_bytes_max=1.0e8,
        tensor_memory_bytes_per_hmma_max=1.0,
        register_memory_bytes_per_op_max=1.0,
        control_hmma_per_block_max=1.0,
        control_hmma_per_reg_op_max=1.0e-5,
        dram_l1_hit_max_pct=1.0,
        dram_l2_hit_max_pct=5.0,
        dram_l2_expected_multiplier=2.0,
        dram_l2_expected_slack_pct=2.0,
        dram_l2_ratio_min=0.5,
        global_address_control_dram_ratio_max=1.0e-3,
    )


def run_self_test() -> None:
    args = self_test_args()
    row = {
        "mode": "l2_cg_load_only",
        "status": "ok",
        "active_SM": "108",
        "blocks_per_SM": "16",
        "W_SM_KiB": "64",
        "ITER": "100000",
        "load_repeat": "4",
        # Deliberately misleading aggregate/legacy values from the failure case.
        "l1_hit_rate_pct": "71.5",
        "l2_hit_rate_pct": "71.5",
        "l1_bytes": "7.15e11",
        "l2_bytes": "1e12",
        # Path-specific evidence proves L1 bypass and an L2 read hit.
        "l1_path_hit_rate_pct": "0",
        "l1_request_bytes": "1e12",
        "l1_hit_bytes": "0",
        "l2_path_hit_rate_pct": "99.5",
        "l2_read_bytes": "1e12",
        "dram_bytes": "1e9",
        "local_read_bytes": "0",
        "local_write_bytes": "0",
        "spill_zero_verified": "1",
        "spill_evidence_source": "local_memory_bytes_zero_inference",
    }
    accepted = classify(row, args)
    assert accepted["acceptance"] == "accepted", accepted["acceptance_reason"]
    assert accepted["l1_request_to_l2_read_bytes"] == "1"
    assert accepted["l1_hit_to_request_bytes"] == "0"

    low_l2 = classify({**row, "l2_path_hit_rate_pct": "72"}, args)
    assert low_l2["acceptance"] == "rejected"
    assert "l2_hit_below_threshold" in low_l2["acceptance_reason"]

    l1_polluted = classify({**row, "l1_hit_bytes": "7.2e11"}, args)
    assert l1_polluted["acceptance"] == "rejected"
    assert "l1_hit_bytes_too_high_for_l2_cg" in l1_polluted["acceptance_reason"]

    local_spill = classify(
        {**row, "local_read_bytes": "32", "spill_zero_verified": "0"}, args
    )
    assert local_spill["acceptance"] == "rejected"
    assert "local_spill_traffic_present" in local_spill["acceptance_reason"]

    missing_path = dict(row)
    for key in (
        "l1_path_hit_rate_pct",
        "l1_request_bytes",
        "l1_hit_bytes",
        "l2_path_hit_rate_pct",
        "l2_read_bytes",
    ):
        missing_path.pop(key)
    missing = classify(missing_path, args)
    assert missing["acceptance"] == "rejected"
    assert "missing_l2_path_hit_rate" in missing["acceptance_reason"]

    address_control = {
        **row,
        "mode": "global_addr_only",
        "l1_request_bytes": "0",
        "l1_hit_bytes": "0",
        "dram_bytes": "3.5e8",
    }
    accepted_control = classify(address_control, args)
    assert accepted_control["acceptance"] == "accepted", accepted_control[
        "acceptance_reason"
    ]
    polluted_control = classify(
        {**address_control, "dram_bytes": "1.5e9"}, args
    )
    assert polluted_control["acceptance"] == "rejected"
    assert "dram_traffic_too_high_for_address_control" in polluted_control[
        "acceptance_reason"
    ]

    dram_stream = {
        **row,
        "mode": "dram_cg_load_only",
        "W_SM_KiB": "8192",
        # Aggregate values may include unrelated traffic. The path-specific
        # global-load/L2-read values are the acceptance evidence.
        "l1_hit_rate_pct": "71",
        "l2_hit_rate_pct": "71",
        "l1_path_hit_rate_pct": "0.1",
        "l2_path_hit_rate_pct": "5.5",
        "l1_request_bytes": "1e12",
        "l1_hit_bytes": "1e9",
        "l2_read_bytes": "1e12",
        "dram_bytes": "9e11",
    }
    accepted_dram = classify(dram_stream, args)
    assert accepted_dram["acceptance"] == "accepted", accepted_dram[
        "acceptance_reason"
    ]
    assert float(accepted_dram["dram_l2_hit_limit_pct"]) > 5.5
    missing_dram_path = classify(
        {**dram_stream, "l2_path_hit_rate_pct": ""}, args
    )
    assert missing_dram_path["acceptance"] == "provisional"
    assert "missing_l2_path_hit_rate_for_dram" in missing_dram_path[
        "acceptance_reason"
    ]
    strict_tensor_control = {
        **row,
        "mode": "reg_operand_only",
        "W_SM_KiB": "2048",
        "reuse_factor": "8",
        "tensor_hmma_inst": "1",
        "l1_bytes": "0",
        "l2_bytes": "0",
        "l2_read_bytes": "0",
        "dram_bytes": "0",
    }
    rejected_tensor_control = classify(strict_tensor_control, args)
    assert rejected_tensor_control["acceptance"] == "rejected"
    assert "tensor_hmma_present_in_control" in rejected_tensor_control[
        "acceptance_reason"
    ]
    print("NCU L2 path-specific acceptance self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ncu_summary_csv", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--target-profile", choices=sorted(PROFILE_L2_MIB), default="")
    parser.add_argument(
        "--out-csv", default="results/summary/ncu_path_acceptance.csv"
    )
    parser.add_argument(
        "--out-md", default="results/summary/ncu_path_acceptance.md"
    )
    parser.add_argument("--l1-hit-min-pct", type=float, default=95.0)
    parser.add_argument("--l1-l2-ratio-max", type=float, default=0.01)
    parser.add_argument("--l1-dram-ratio-max", type=float, default=0.01)
    parser.add_argument(
        "--l2-l1-hit-max-pct",
        type=float,
        default=1.0,
        help="Maximum path-specific L1 hit rate for an ld.global.cg L2 candidate.",
    )
    parser.add_argument(
        "--l2-l1-bytes-ratio-max",
        type=float,
        default=0.01,
        help=(
            "Maximum L1 hit bytes / L1 global-load request bytes for an L2 "
            "candidate. L1 request bytes themselves are not an L1-hit signal."
        ),
    )
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
    parser.add_argument("--control-hmma-per-block-max", type=float, default=1.0)
    parser.add_argument("--control-hmma-per-reg-op-max", type=float, default=1.0e-5)
    parser.add_argument("--dram-l1-hit-max-pct", type=float, default=1.0)
    parser.add_argument("--dram-l2-hit-max-pct", type=float, default=5.0)
    parser.add_argument("--dram-l2-expected-multiplier", type=float, default=2.0)
    parser.add_argument("--dram-l2-expected-slack-pct", type=float, default=2.0)
    parser.add_argument("--dram-l2-ratio-min", type=float, default=0.5)
    parser.add_argument(
        "--global-address-control-dram-ratio-max",
        type=float,
        default=1.0e-3,
        help=(
            "Maximum address-control DRAM bytes divided by the paired path's "
            "expected input bytes. The default 0.1% permits output-store, SMID "
            "atomic, and profiler replay background while L1 input requests "
            "must remain exactly zero."
        ),
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if not args.ncu_summary_csv:
        parser.error("ncu_summary_csv is required")

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
