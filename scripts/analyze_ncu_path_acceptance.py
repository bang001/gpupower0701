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

PROFILE_EXTERNAL_MEMORY = {
    "v100": "HBM2",
    "rtx3090": "GDDR6X",
    "a100": "HBM2",
    "h100": "HBM3",
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
    has_l2_native_hit = bool(row.get("l2_native_read_hit_rate_pct", "").strip())
    l2_native_hit = f(row, "l2_native_read_hit_rate_pct", -1.0)
    has_l2_native_delta = bool(
        row.get("l2_native_vs_derived_hit_delta_pct", "").strip()
    )
    l2_native_delta = f(row, "l2_native_vs_derived_hit_delta_pct", -1.0)
    has_l2_logical_hit = bool(
        row.get("l2_logical_read_hit_rate_pct", "").strip()
    )
    l2_logical_hit = f(row, "l2_logical_read_hit_rate_pct", -1.0)
    l2_fabric_metrics_present = f(row, "l2_fabric_metrics_present", 0.0)
    l2_fabric_counter_coherent = f(
        row, "l2_fabric_counter_coherent", -1.0
    )
    l2_fabric_model_coherent = f(row, "l2_fabric_model_coherent", -1.0)
    has_native_fabric_model_delta = bool(
        row.get("l2_native_vs_fabric_model_hit_delta_pct", "").strip()
    )
    native_fabric_model_delta = f(
        row, "l2_native_vs_fabric_model_hit_delta_pct", -1.0
    )
    has_l1_request_bytes = bool(row.get("l1_request_bytes", "").strip())
    has_l1_hit_bytes = bool(row.get("l1_hit_bytes", "").strip())
    has_l1_path_hit = bool(row.get("l1_path_hit_rate_pct", "").strip())
    has_l2_read_bytes = bool(row.get("l2_read_bytes", "").strip())
    has_l2_path_hit = bool(row.get("l2_path_hit_rate_pct", "").strip())
    has_l2_path_counter_coherence = bool(
        row.get("l2_path_counter_coherent", "").strip()
    )
    l2_path_counter_coherent = f(row, "l2_path_counter_coherent", -1.0)
    dram_bytes = f(row, "dram_bytes")
    has_dram_read_bytes = bool(row.get("dram_read_bytes", "").strip())
    dram_read_bytes = f(row, "dram_read_bytes")
    dram_read_bytes_source = row.get("dram_read_bytes_source", "").strip()
    has_dram_write_bytes = bool(row.get("dram_write_bytes", "").strip())
    dram_write_bytes = f(row, "dram_write_bytes")
    dram_write_bytes_source = row.get("dram_write_bytes_source", "").strip()
    shared_bytes = f(row, "shared_bytes")
    shared_read_bytes = f(row, "shared_read_bytes", shared_bytes)
    shared_write_bytes = f(row, "shared_write_bytes")
    shared_accesses = f(row, "shared_accesses")
    shared_bank_conflicts = f(row, "shared_bank_conflicts")
    shared_inst = f(row, "shared_inst")
    tensor_hmma = f(row, "tensor_hmma_inst")
    has_tensor_fp16_f32_ops = bool(
        row.get("tensor_fp16_f32_ops", "").strip()
    )
    tensor_fp16_f32_ops = f(row, "tensor_fp16_f32_ops")
    expected_logical_mma = f(row, "expected_logical_mma")
    expected_logical_flop = f(row, "expected_logical_flop")
    tensor_hmma_per_logical_mma = f(
        row, "tensor_hmma_per_logical_mma", -1.0
    )
    tensor_ops_to_expected_flop = f(
        row, "tensor_ops_to_expected_flop", -1.0
    )
    registers_per_thread = f(row, "registers_per_thread", -1.0)
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
    l2_acceptance_model = ""
    l2_acceptance_hit_rate = -1.0

    required_replay = getattr(args, "require_ncu_replay_mode", "")
    required_cache_control = getattr(args, "require_ncu_cache_control", "")
    if required_replay and row.get("ncu_replay_mode", "") != required_replay:
        reasons.append("ncu_replay_mode_mismatch")
    if (
        required_cache_control
        and row.get("ncu_cache_control", "") != required_cache_control
    ):
        reasons.append("ncu_cache_control_mismatch")

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
        if row.get("ncu_metric_profile", "") != "l2_path_minimal":
            reasons.append("l2_metric_profile_not_minimal")
        required_l2_policy = getattr(args, "require_l2_residency_policy", "")
        required_l2_layout = getattr(args, "require_l2_address_layout", "")
        if (
            required_l2_policy
            and row.get("l2_residency_policy", "") != required_l2_policy
        ):
            reasons.append("l2_residency_policy_mismatch")
        if required_l2_layout and row.get("l2_address_layout", "") != required_l2_layout:
            reasons.append("l2_address_layout_mismatch")
        if not has_l2_path_hit:
            reasons.append("missing_l2_path_hit_rate")
        if args.target_profile == "a100":
            # GA100 has two L2 partitions. A miss in the directly connected
            # partition can be recovered by a srcunit_ltcfabric hit in the
            # other partition. Validate the final service path instead of
            # requiring the first lookup or the double-lookup native ratio to
            # be at least 95%.
            l2_acceptance_model = "ga100_source_plus_ltcfabric"
            l2_acceptance_hit_rate = l2_logical_hit
            if l2_fabric_metrics_present != 1.0:
                reasons.append("missing_required_l2_fabric_metrics")
            if l2_fabric_counter_coherent != 1.0:
                reasons.append("l2_fabric_counters_incoherent")
            if l2_fabric_model_coherent != 1.0:
                reasons.append("l2_fabric_model_incoherent")
            if not has_l2_logical_hit:
                reasons.append("missing_l2_logical_hit_rate")
            elif l2_logical_hit < args.l2_hit_min_pct:
                reasons.append("l2_logical_hit_below_threshold")
            elif l2_logical_hit > 100.5:
                reasons.append("l2_logical_hit_above_counter_tolerance")
            if not has_l2_native_hit:
                reasons.append("missing_required_native_l2_hit")
            if not has_native_fabric_model_delta:
                reasons.append("missing_required_native_fabric_model_delta")
            elif (
                native_fabric_model_delta
                > args.l2_native_derived_delta_max_pct
            ):
                reasons.append("native_fabric_model_delta_above_threshold")
        else:
            l2_acceptance_model = "direct_partition_lookup"
            l2_acceptance_hit_rate = l2_path_hit
            if has_l2_path_hit and l2_path_hit < args.l2_hit_min_pct:
                reasons.append("l2_hit_below_threshold")
            native_required = args.target_profile != "v100"
            if native_required and not has_l2_native_hit:
                reasons.append("missing_required_native_l2_hit")
            elif has_l2_native_hit and l2_native_hit < args.l2_hit_min_pct:
                reasons.append("native_l2_hit_below_threshold")
            if native_required and not has_l2_native_delta:
                reasons.append("missing_required_native_derived_delta")
            elif (
                has_l2_native_delta
                and l2_native_delta > args.l2_native_derived_delta_max_pct
            ):
                reasons.append("native_derived_delta_above_threshold")
        if not has_l2_path_counter_coherence:
            reasons.append("missing_l2_path_counter_coherence")
        elif l2_path_counter_coherent != 1.0:
            reasons.append("l2_path_counters_incoherent")
        if not has_l2_read_bytes or l2_read_bytes <= 0.0:
            reasons.append("missing_l2_read_bytes")
        else:
            expected_l2_bytes = expected_shared_bytes(row)
            observed_expected = ratio(l2_read_bytes, expected_l2_bytes)
            if not (
                args.l2_expected_ratio_min
                <= observed_expected
                <= args.l2_expected_ratio_max
            ):
                reasons.append("l2_read_bytes_expected_mismatch")
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
        if not has_dram_read_bytes:
            reasons.append("missing_dram_read_bytes_for_l2")
        elif ratio(dram_read_bytes, l2_read_bytes) > args.l2_dram_ratio_max:
            reasons.append("dram_read_traffic_too_high_for_l2")

    elif mode == "l2_load_only":
        component = "l2_capacity_diagnostic"
        reasons.append("l2_load_only_is_not_l2_bypass_path")

    elif mode in {"shared_scalar_load_only", "shared_load_only"}:
        component = "shared_memory_path"
        expected = expected_shared_bytes(row)
        if shared_accesses <= 0.0:
            reasons.append("missing_shared_accesses")
        if shared_read_bytes <= 0.0:
            reasons.append("missing_shared_read_bytes")
        else:
            observed_expected_ratio = ratio(shared_read_bytes, expected)
            if not (args.shared_expected_ratio_min <= observed_expected_ratio <= args.shared_expected_ratio_max):
                reasons.append("shared_read_bytes_expected_mismatch")
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

    elif mode == "shared_scalar_addr_only":
        component = "shared_address_control"
        # Initialization stores and the same dynamic-shared allocation are
        # intentional. The timed loop must not issue shared reads.
        if shared_read_bytes > 0.0:
            reasons.append("shared_read_traffic_present_in_address_control")
        if f(row, "shared_mem_per_block_dynamic") <= 0.0:
            reasons.append("missing_dynamic_shared_allocation_in_control")
        expected = expected_shared_bytes(row)
        traffic_scale = max(expected, shared_write_bytes, 1.0)
        if ratio(l1_bytes, traffic_scale) > args.shared_global_ratio_max:
            reasons.append("global_l1_traffic_too_high_for_shared_control")
        if ratio(l2_bytes, traffic_scale) > args.shared_global_ratio_max:
            reasons.append("l2_traffic_too_high_for_shared_control")
        if ratio(dram_bytes, traffic_scale) > args.shared_global_ratio_max:
            reasons.append("dram_traffic_too_high_for_shared_control")
        if tensor_hmma > 0.0:
            reasons.append("tensor_hmma_present_in_shared_control")

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
        if expected_logical_mma <= 0.0:
            reasons.append("missing_expected_logical_mma")
        if tensor_hmma_per_logical_mma <= 0.0:
            reasons.append("invalid_hmma_per_logical_mma")
        if expected_logical_flop <= 0.0:
            reasons.append("missing_expected_logical_flop")
        if has_tensor_fp16_f32_ops and not (
            args.tensor_ops_to_expected_min
            <= tensor_ops_to_expected_flop
            <= args.tensor_ops_to_expected_max
        ):
            reasons.append("tensor_ops_expected_flop_mismatch")
        if registers_per_thread <= 0.0:
            reasons.append("missing_treatment_register_footprint")
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
        if has_tensor_fp16_f32_ops and tensor_fp16_f32_ops > 0.0:
            reasons.append("tensor_ops_present_in_control")
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
        if mode == "reg_operand_only" and registers_per_thread <= 0.0:
            reasons.append("missing_control_register_footprint")
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
        component = "external_memory_read_path"
        if not has_l1_path_hit:
            reasons.append("missing_l1_path_hit_rate_for_external_memory")
        elif l1_path_hit > args.dram_l1_hit_max_pct:
            reasons.append("l1_hit_too_high_for_external_memory")
        external_l2_hit = l2_path_hit
        has_external_l2_hit = has_l2_path_hit
        if args.target_profile == "a100":
            external_l2_hit = l2_logical_hit
            has_external_l2_hit = has_l2_logical_hit
        if not has_external_l2_hit:
            reasons.append("missing_l2_service_hit_rate_for_external_memory")
        dram_expected_l2_hit_pct = expected_l2_residency_hit_pct(
            row, args.target_profile
        )
        dram_l2_hit_limit_pct = min(
            args.dram_l2_hit_max_pct,
            dram_expected_l2_hit_pct * args.dram_l2_expected_multiplier
            + args.dram_l2_expected_slack_pct,
        )
        if has_external_l2_hit and external_l2_hit > dram_l2_hit_limit_pct:
            reasons.append("l2_hit_too_high_for_external_memory")
        expected_source_bytes = expected_shared_bytes(row)
        source_to_expected = ratio(l2_read_bytes, expected_source_bytes)
        read_to_expected = ratio(dram_read_bytes, expected_source_bytes)
        external_read_fraction = ratio(dram_read_bytes, l2_read_bytes)
        write_to_read = ratio(dram_write_bytes, dram_read_bytes)
        if not has_dram_read_bytes or dram_read_bytes <= 0.0:
            reasons.append("missing_external_memory_read_bytes")
        elif dram_read_bytes_source != "dram__bytes_read.sum":
            reasons.append("external_read_bytes_not_direct_counter")
        if not has_dram_write_bytes:
            reasons.append("missing_external_memory_write_bytes")
        elif dram_write_bytes_source != "dram__bytes_write.sum":
            reasons.append("external_write_bytes_not_direct_counter")
        if not has_l2_read_bytes or l2_read_bytes <= 0.0:
            reasons.append("missing_l2_read_bytes_for_external_memory")
        elif not (
            args.dram_source_expected_ratio_min
            <= source_to_expected
            <= args.dram_source_expected_ratio_max
        ):
            reasons.append("global_read_bytes_not_conserved")
        if has_dram_read_bytes and not (
            args.dram_read_expected_ratio_min
            <= read_to_expected
            <= args.dram_read_expected_ratio_max
        ):
            reasons.append("external_read_bytes_not_expected")
        if (
            has_dram_read_bytes
            and has_l2_read_bytes
            and l2_read_bytes > 0.0
            and external_read_fraction < args.dram_l2_ratio_min
        ):
            reasons.append("external_memory_read_not_dominant")
        if (
            has_dram_write_bytes
            and has_dram_read_bytes
            and dram_read_bytes > 0.0
            and write_to_read > args.dram_write_read_ratio_max
        ):
            reasons.append("external_memory_write_contamination")

    else:
        reasons.append("mode_not_final_component_candidate")

    if not reasons:
        status = "accepted"
    elif component == "shared_memory_path" and reasons == ["missing_shared_read_bytes"]:
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
            "dram_read_to_l2_read_bytes": (
                f"{ratio(dram_read_bytes, l2_read_bytes):.6g}"
                if l2_read_bytes > 0.0 and has_dram_read_bytes
                else ""
            ),
            "external_memory_technology": PROFILE_EXTERNAL_MEMORY.get(
                args.target_profile, "unknown"
            ),
            "external_memory_coefficient_scope": (
                "effective_gpu_device_external_read_path"
                if mode == "dram_cg_load_only"
                else ""
            ),
            "external_memory_l2_service_hit_rate_pct": (
                f"{external_l2_hit:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "external_memory_source_to_expected_ratio": (
                f"{source_to_expected:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "external_memory_read_to_expected_ratio": (
                f"{read_to_expected:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "external_memory_write_to_read_ratio": (
                f"{write_to_read:.6g}" if mode == "dram_cg_load_only" else ""
            ),
            "l2_acceptance_model": l2_acceptance_model,
            "l2_acceptance_hit_rate_pct": (
                f"{l2_acceptance_hit_rate:.6g}"
                if mode == "l2_cg_load_only" and l2_acceptance_hit_rate >= 0.0
                else ""
            ),
            "l2_read_bytes_to_expected": (
                f"{ratio(l2_read_bytes, expected_shared_bytes(row)):.6g}"
                if mode == "l2_cg_load_only" and l2_read_bytes > 0.0
                else ""
            ),
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
            "tensor_hmma_ratio_group_median": "",
            "tensor_hmma_ratio_group_relative_spread": "",
            "tensor_control_pair_status": "",
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


def enforce_tensor_pair_consistency(
    rows: list[dict[str, str]], args: argparse.Namespace
) -> None:
    def coord(row: dict[str, str]) -> tuple[str, ...]:
        return tuple(
            row.get(name, "")
            for name in (
                "W_SM_KiB",
                "blocks_per_SM",
                "active_SM",
                "ITER",
                "reuse_factor",
                "load_repeat",
            )
        )

    controls = {
        coord(row): row
        for row in rows
        if row.get("mode") == "reg_operand_only"
    }
    treatment_groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("mode") != "reg_mma":
            continue
        key = (
            row.get("W_SM_KiB", ""),
            row.get("blocks_per_SM", ""),
            row.get("active_SM", ""),
        )
        treatment_groups.setdefault(key, []).append(row)

    for group in treatment_groups.values():
        ratios = [
            f(row, "tensor_hmma_per_logical_mma", -1.0)
            for row in group
            if f(row, "tensor_hmma_per_logical_mma", -1.0) > 0.0
        ]
        group_median = median(ratios) if ratios else 0.0
        relative_spread = (
            (max(ratios) - min(ratios)) / group_median
            if ratios and group_median > 0.0
            else math.inf
        )
        group_reason = ""
        if len(ratios) < args.tensor_min_ratio_points:
            group_reason = "insufficient_hmma_ratio_points"
        elif relative_spread > args.tensor_hmma_ratio_relative_spread_max:
            group_reason = "hmma_per_logical_mma_unstable_across_rf"

        for row in group:
            row["tensor_hmma_ratio_group_median"] = (
                f"{group_median:.6g}" if group_median > 0.0 else ""
            )
            row["tensor_hmma_ratio_group_relative_spread"] = (
                f"{relative_spread:.6g}" if math.isfinite(relative_spread) else ""
            )
            control = controls.get(coord(row))
            control_ok = bool(
                control and control.get("acceptance") == "accepted"
            )
            row["tensor_control_pair_status"] = (
                "accepted" if control_ok else "missing_or_rejected"
            )
            reasons = [
                reason
                for reason in row.get("acceptance_reason", "").split(";")
                if reason and reason != "pass"
            ]
            if group_reason and group_reason not in reasons:
                reasons.append(group_reason)
            if not control_ok:
                reasons.append("tensor_control_pair_not_accepted")
            if reasons:
                row["acceptance"] = "rejected"
                row["acceptance_reason"] = ";".join(dict.fromkeys(reasons))


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

        out.write("\n## Tensor Pair Diagnostics\n\n")
        out.write(
            "The HMMA/logical-MMA ratio is allowed to differ by architecture, but "
            "must stay stable across RF at each blocks/SM coordinate. Register "
            "counts expose the treatment/control footprint mismatch rather than "
            "claiming pure Tensor-circuit isolation.\n\n"
        )
        out.write(
            "| mode | blocks/SM | RF | HMMA | logical MMA | HMMA/logical | "
            "FP16-to-FP32 ops | expected FLOP | ops/expected | group median | "
            "relative spread | control pair | Tensor pipe active (%) | "
            "registers/thread | acceptance |\n"
        )
        out.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|\n")
        for row in rows:
            if row.get("mode") not in {"reg_mma", "reg_operand_only"}:
                continue
            out.write(
                f"| {row.get('mode','')} | {row.get('blocks_per_SM','')} | "
                f"{row.get('reuse_factor','')} | {row.get('tensor_hmma_inst','')} | "
                f"{row.get('expected_logical_mma','')} | "
                f"{row.get('tensor_hmma_per_logical_mma','')} | "
                f"{row.get('tensor_fp16_f32_ops','')} | "
                f"{row.get('expected_logical_flop','')} | "
                f"{row.get('tensor_ops_to_expected_flop','')} | "
                f"{row.get('tensor_hmma_ratio_group_median','')} | "
                f"{row.get('tensor_hmma_ratio_group_relative_spread','')} | "
                f"{row.get('tensor_control_pair_status','')} | "
                f"{row.get('tensor_pipe_active_pct','')} | "
                f"{row.get('registers_per_thread','')} | "
                f"{row.get('acceptance','')} |\n"
            )

        out.write("\n")
        out.write(
            "| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | "
            "L2 native read hit (%) | L2 logical hit (%) | L2 fabric hit (%) | acceptance model | "
            "native/model delta (pp) | source/fabric/model coherent | "
            "L1 accesses | L2 accesses | DRAM accesses | shared bytes | "
            "L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | "
            "DRAM read bytes | DRAM write bytes | DRAM-read/L2-read | source/expected | "
            "external-read/expected | write/read | memory technology | DRAM read GB/s | "
            "DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |\n"
        )
        out.write("|---|" * 13 + "---:|" * 21 + "\n")
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
                f"{row.get('l2_address_layout','')} | "
                f"{row.get('l1_path_hit_rate_pct','')} | {row.get('l2_path_hit_rate_pct','')} | "
                f"{row.get('l2_native_read_hit_rate_pct','')} | "
                f"{row.get('l2_logical_read_hit_rate_pct','')} | "
                f"{row.get('l2_fabric_hit_rate_pct','')} | "
                f"{row.get('l2_acceptance_model','')} | "
                f"{row.get('l2_native_vs_fabric_model_hit_delta_pct','')} | "
                f"{row.get('l2_path_counter_coherent','')}/"
                f"{row.get('l2_fabric_counter_coherent','')}/"
                f"{row.get('l2_fabric_model_coherent','')} | "
                f"{l1_accesses} | {l2_accesses} | {dram_accesses} | "
                f"{row.get('shared_bytes','')} | {row.get('l1_request_bytes','')} | "
                f"{row.get('l1_hit_bytes','')} | {row.get('l2_read_bytes','')} | "
                f"{row.get('l2_read_miss_bytes','')} | "
                f"{row.get('dram_read_bytes','')} | "
                f"{row.get('dram_write_bytes','')} | "
                f"{row.get('dram_read_to_l2_read_bytes','')} | "
                f"{row.get('external_memory_source_to_expected_ratio','')} | "
                f"{row.get('external_memory_read_to_expected_ratio','')} | "
                f"{row.get('external_memory_write_to_read_ratio','')} | "
                f"{row.get('external_memory_technology','')} | "
                f"{row.get('dram_read_bandwidth_GBps','')} | "
                f"{row.get('dram_bytes','')} | "
                f"{row.get('l2_read_bytes_to_expected','')} | "
                f"{row.get('launch_persisting_l2_cache_size_bytes','')} | "
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
            "L2 read bytes are the preferred L2 pJ/bit denominator. GA100 uses "
            "a source-plus-LTC-fabric final-service hit rate; its coefficient "
            "therefore includes the workload-dependent partition-fabric cost and "
            "is not a pure local L2-SRAM coefficient. External-memory acceptance "
            "requires NCU read bytes, conserved global-read requests, at least 90% "
            "external-read service, and at most 1% write contamination. Its energy "
            "coefficient remains an effective GPU-device path value, not HBM/GDDR "
            "cell or package energy.\n"
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
        l2_native_derived_delta_max_pct=2.0,
        l2_expected_ratio_min=0.95,
        l2_expected_ratio_max=1.05,
        l2_dram_ratio_max=0.02,
        shared_expected_ratio_min=0.5,
        shared_expected_ratio_max=2.0,
        shared_global_ratio_max=0.02,
        shared_bank_conflict_ratio_max=0.05,
        tensor_memory_bytes_max=1.0e8,
        register_memory_bytes_max=1.0e8,
        tensor_memory_bytes_per_hmma_max=1.0,
        tensor_min_ratio_points=3,
        tensor_hmma_ratio_relative_spread_max=0.10,
        tensor_ops_to_expected_min=0.98,
        tensor_ops_to_expected_max=1.02,
        register_memory_bytes_per_op_max=1.0,
        control_hmma_per_block_max=1.0,
        control_hmma_per_reg_op_max=1.0e-5,
        dram_l1_hit_max_pct=1.0,
        dram_l2_hit_max_pct=10.0,
        dram_l2_expected_multiplier=2.0,
        dram_l2_expected_slack_pct=2.0,
        dram_l2_ratio_min=0.9,
        dram_source_expected_ratio_min=0.95,
        dram_source_expected_ratio_max=1.05,
        dram_read_expected_ratio_min=0.85,
        dram_read_expected_ratio_max=1.05,
        dram_write_read_ratio_max=0.01,
        global_address_control_dram_ratio_max=1.0e-3,
        require_ncu_replay_mode="",
        require_ncu_cache_control="",
        require_l2_residency_policy="",
        require_l2_address_layout="",
    )


def run_self_test() -> None:
    args = self_test_args()
    row = {
        "mode": "l2_cg_load_only",
        "status": "ok",
        "ncu_metric_profile": "l2_path_minimal",
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
        "l1_request_bytes": "7.077888e11",
        "l1_hit_bytes": "0",
        "l2_path_hit_rate_pct": "99.5",
        "l2_native_read_hit_rate_pct": "99.4",
        "l2_native_vs_derived_hit_delta_pct": "0.1",
        "l2_logical_read_hit_rate_pct": "99.5",
        "l2_fabric_hit_rate_pct": "",
        "l2_fabric_metrics_present": "1",
        "l2_fabric_counter_coherent": "1",
        "l2_fabric_model_coherent": "1",
        "l2_fabric_model_native_hit_rate_pct": "99.5",
        "l2_native_vs_fabric_model_hit_delta_pct": "0.1",
        "l2_path_counter_coherent": "1",
        "l2_read_bytes": "7.077888e11",
        "dram_read_bytes": "1e9",
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

    direct_args = argparse.Namespace(**vars(args))
    direct_args.target_profile = "rtx3090"
    low_l2 = classify({**row, "l2_path_hit_rate_pct": "72"}, direct_args)
    assert low_l2["acceptance"] == "rejected"
    assert "l2_hit_below_threshold" in low_l2["acceptance_reason"]

    low_native_l2 = classify(
        {**row, "l2_native_read_hit_rate_pct": "72", "l2_native_vs_derived_hit_delta_pct": "27.5"},
        direct_args,
    )
    assert low_native_l2["acceptance"] == "rejected"
    assert "native_l2_hit_below_threshold" in low_native_l2["acceptance_reason"]

    observed_a100_failure = classify(
        {
            **row,
            "l2_path_hit_rate_pct": "62",
            "l2_native_read_hit_rate_pct": "72.5",
            "l2_native_vs_derived_hit_delta_pct": "10.5",
            "l2_logical_read_hit_rate_pct": "99.5",
            "l2_fabric_hit_rate_pct": "98.6842",
            "l2_fabric_model_native_hit_rate_pct": "72.5",
            "l2_native_vs_fabric_model_hit_delta_pct": "0",
        },
        args,
    )
    assert observed_a100_failure["acceptance"] == "accepted", observed_a100_failure[
        "acceptance_reason"
    ]
    assert (
        observed_a100_failure["l2_acceptance_model"]
        == "ga100_source_plus_ltcfabric"
    )

    missing_fabric = classify(
        {
            **row,
            "l2_path_hit_rate_pct": "62",
            "l2_logical_read_hit_rate_pct": "",
            "l2_fabric_metrics_present": "0",
            "l2_fabric_counter_coherent": "",
            "l2_fabric_model_coherent": "",
            "l2_native_vs_fabric_model_hit_delta_pct": "",
        },
        args,
    )
    assert missing_fabric["acceptance"] == "rejected"
    assert "missing_required_l2_fabric_metrics" in missing_fabric[
        "acceptance_reason"
    ]

    true_a100_miss = classify(
        {
            **row,
            "l2_path_hit_rate_pct": "62",
            "l2_logical_read_hit_rate_pct": "72",
            "l2_fabric_model_native_hit_rate_pct": "60",
            "l2_native_vs_fabric_model_hit_delta_pct": "12.5",
            "dram_read_bytes": "2e11",
        },
        args,
    )
    assert true_a100_miss["acceptance"] == "rejected"
    assert "l2_logical_hit_below_threshold" in true_a100_miss[
        "acceptance_reason"
    ]

    over_recovered = classify(
        {**row, "l2_logical_read_hit_rate_pct": "101"}, args
    )
    assert over_recovered["acceptance"] == "rejected"
    assert "l2_logical_hit_above_counter_tolerance" in over_recovered[
        "acceptance_reason"
    ]

    incoherent_l2 = classify({**row, "l2_path_counter_coherent": "0"}, args)
    assert incoherent_l2["acceptance"] == "rejected"
    assert "l2_path_counters_incoherent" in incoherent_l2["acceptance_reason"]

    full_profile_l2 = classify({**row, "ncu_metric_profile": "full"}, args)
    assert full_profile_l2["acceptance"] == "rejected"
    assert "l2_metric_profile_not_minimal" in full_profile_l2["acceptance_reason"]

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
        "l2_logical_read_hit_rate_pct": "4.0",
        "l1_request_bytes": "7.077888e11",
        "l1_hit_bytes": "1e9",
        "l2_read_bytes": "7.077888e11",
        "dram_read_bytes": "6.8e11",
        "dram_read_bytes_source": "dram__bytes_read.sum",
        "dram_write_bytes": "1e8",
        "dram_write_bytes_source": "dram__bytes_write.sum",
        "dram_bytes": "6.801e11",
    }
    accepted_dram = classify(dram_stream, args)
    assert accepted_dram["acceptance"] == "accepted", accepted_dram[
        "acceptance_reason"
    ]
    assert accepted_dram["component_candidate"] == "external_memory_read_path"
    assert float(accepted_dram["dram_l2_hit_limit_pct"]) >= 5.5
    fallback_dram_counter = classify(
        {
            **dram_stream,
            "dram_read_bytes_source": "dram__sectors_read.sum*32",
        },
        args,
    )
    assert fallback_dram_counter["acceptance"] == "rejected"
    assert "external_read_bytes_not_direct_counter" in fallback_dram_counter[
        "acceptance_reason"
    ]
    missing_dram_path = classify(
        {**dram_stream, "l2_logical_read_hit_rate_pct": ""}, args
    )
    assert missing_dram_path["acceptance"] == "provisional"
    assert "missing_l2_service_hit_rate_for_external_memory" in missing_dram_path[
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

    tensor_rows: list[dict[str, str]] = []
    for reuse in (1, 2, 4):
        expected_mma = 108 * 16 * 100000 * reuse
        common = {
            **row,
            "W_SM_KiB": "1",
            "blocks_per_SM": "16",
            "ITER": "100000",
            "reuse_factor": str(reuse),
            "load_repeat": "1",
            "l1_bytes": "0",
            "l2_bytes": "0",
            "l2_read_bytes": "0",
            "dram_bytes": "0",
            "tensor_hmma_inst": str(expected_mma * 2),
            "tensor_fp16_f32_ops": str(expected_mma * 8192),
            "expected_logical_mma": str(expected_mma),
            "expected_logical_flop": str(expected_mma * 8192),
            "tensor_hmma_per_logical_mma": "2",
            "tensor_ops_to_expected_flop": "1",
            "registers_per_thread": "32",
        }
        tensor_rows.append(classify({**common, "mode": "reg_mma"}, args))
        tensor_rows.append(
            classify(
                {
                    **common,
                    "mode": "reg_operand_only",
                    "tensor_hmma_inst": "0",
                    "tensor_fp16_f32_ops": "0",
                    "expected_logical_mma": "0",
                    "expected_logical_flop": "0",
                    "tensor_hmma_per_logical_mma": "",
                    "tensor_ops_to_expected_flop": "",
                    "registers_per_thread": "16",
                },
                args,
            )
        )
    enforce_tensor_pair_consistency(tensor_rows, args)
    assert all(row["acceptance"] == "accepted" for row in tensor_rows), tensor_rows
    treatments = [row for row in tensor_rows if row["mode"] == "reg_mma"]
    assert all(row["tensor_control_pair_status"] == "accepted" for row in treatments)
    assert all(
        float(row["tensor_hmma_ratio_group_relative_spread"]) == 0.0
        for row in treatments
    )

    unstable_rows = [dict(row) for row in tensor_rows]
    for unstable in unstable_rows:
        if unstable["mode"] == "reg_mma" and unstable["reuse_factor"] == "4":
            unstable["tensor_hmma_per_logical_mma"] = "3"
            unstable["acceptance"] = "accepted"
            unstable["acceptance_reason"] = "pass"
    enforce_tensor_pair_consistency(unstable_rows, args)
    assert all(
        row["acceptance"] == "rejected"
        and "hmma_per_logical_mma_unstable_across_rf"
        in row["acceptance_reason"]
        for row in unstable_rows
        if row["mode"] == "reg_mma"
    )

    ops_mismatch = classify(
        {
            **next(row for row in tensor_rows if row["mode"] == "reg_mma"),
            "tensor_ops_to_expected_flop": "2",
        },
        args,
    )
    assert ops_mismatch["acceptance"] == "rejected"
    assert "tensor_ops_expected_flop_mismatch" in ops_mismatch["acceptance_reason"]
    print("NCU path and Tensor pair consistency self-test passed")


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
    parser.add_argument(
        "--l2-native-fabric-model-delta-max-pct",
        "--l2-native-derived-delta-max-pct",
        dest="l2_native_derived_delta_max_pct",
        type=float,
        default=2.0,
        help=(
            "Maximum hit-rate delta in percentage points. A100 compares native "
            "against the source+LTC-fabric model; other profiles compare native "
            "against the direct path rate. The old option is retained as an alias."
        ),
    )
    parser.add_argument("--l2-expected-ratio-min", type=float, default=0.95)
    parser.add_argument("--l2-expected-ratio-max", type=float, default=1.05)
    parser.add_argument(
        "--require-ncu-replay-mode",
        choices=("", "application", "kernel"),
        default="",
    )
    parser.add_argument(
        "--require-ncu-cache-control",
        choices=("", "none", "all"),
        default="",
    )
    parser.add_argument(
        "--require-l2-residency-policy",
        choices=("", "normal", "persisting"),
        default="",
    )
    parser.add_argument(
        "--require-l2-address-layout",
        choices=("", "contiguous", "sm_interleaved"),
        default="",
    )
    parser.add_argument("--l2-dram-ratio-max", type=float, default=0.02)
    parser.add_argument("--shared-expected-ratio-min", type=float, default=0.5)
    parser.add_argument("--shared-expected-ratio-max", type=float, default=2.0)
    parser.add_argument("--shared-global-ratio-max", type=float, default=0.02)
    parser.add_argument("--shared-bank-conflict-ratio-max", type=float, default=0.05)
    parser.add_argument("--tensor-memory-bytes-max", type=float, default=1.0e8)
    parser.add_argument("--register-memory-bytes-max", type=float, default=1.0e8)
    parser.add_argument("--tensor-memory-bytes-per-hmma-max", type=float, default=1.0)
    parser.add_argument("--tensor-min-ratio-points", type=int, default=3)
    parser.add_argument(
        "--tensor-hmma-ratio-relative-spread-max",
        type=float,
        default=0.10,
        help=(
            "Maximum (max-min)/median HMMA-per-logical-MMA spread across the RF "
            "sweep at one blocks/SM coordinate. The absolute ratio is architecture-specific."
        ),
    )
    parser.add_argument("--tensor-ops-to-expected-min", type=float, default=0.98)
    parser.add_argument("--tensor-ops-to-expected-max", type=float, default=1.02)
    parser.add_argument("--register-memory-bytes-per-op-max", type=float, default=1.0)
    parser.add_argument("--control-hmma-per-block-max", type=float, default=1.0)
    parser.add_argument("--control-hmma-per-reg-op-max", type=float, default=1.0e-5)
    parser.add_argument("--dram-l1-hit-max-pct", type=float, default=1.0)
    parser.add_argument("--dram-l2-hit-max-pct", type=float, default=10.0)
    parser.add_argument("--dram-l2-expected-multiplier", type=float, default=2.0)
    parser.add_argument("--dram-l2-expected-slack-pct", type=float, default=2.0)
    parser.add_argument(
        "--external-read-fraction-min",
        "--dram-l2-ratio-min",
        dest="dram_l2_ratio_min",
        type=float,
        default=0.9,
        help="Minimum dram_read_bytes/l2_read_bytes for an external-read path.",
    )
    parser.add_argument("--dram-source-expected-ratio-min", type=float, default=0.95)
    parser.add_argument("--dram-source-expected-ratio-max", type=float, default=1.05)
    parser.add_argument("--dram-read-expected-ratio-min", type=float, default=0.85)
    parser.add_argument("--dram-read-expected-ratio-max", type=float, default=1.05)
    parser.add_argument("--dram-write-read-ratio-max", type=float, default=0.01)
    parser.add_argument(
        "--global-address-control-dram-ratio-max",
        type=float,
        default=1.0e-3,
        help=(
            "Maximum address-control DRAM bytes divided by the paired path's "
            "expected input bytes. The default 0.1%% permits output-store, SMID "
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
    enforce_tensor_pair_consistency(rows, args)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
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
