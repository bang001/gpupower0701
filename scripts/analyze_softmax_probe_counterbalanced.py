#!/usr/bin/env python3
"""Analyze a bounded counterbalanced FP16 Softmax extra-exp probe.

The required six-bracket order is F,R,R,F,F,R, where F is C-T-C and R is
T-C-T.  Every adjacent F/R pair is treated as one matched orientation block.
Power contrasts are always treatment minus control.  They are normalized by
the treatment logical scalar exponent-result rate (one added result per input
element), then decomposed into an order-balanced effect and a middle-position
bias.  A native packed-f16x2 PTX-op denominator (N/2) is auxiliary only:

    delta = (forward + reverse) / 2
    bias  = (forward - reverse) / 2

Role-level uncertainty uses a residual moving-block bootstrap that recomputes
the same Theil--Sen cumulative-energy slope used by the point estimator.
Triplet intervals are diagnostics; the decision gate is applied only to the
three matched-block aggregate.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from analyze_softmax_operand_rate_atc import (
    analyze_trace_role,
    num,
    percentile,
    read_csv,
    read_energy_trace,
    trace_kernel_midpoint_s,
)


EXPECTED_ORIENTATIONS = ("forward", "reverse", "reverse", "forward", "forward", "reverse")
MATCHED_BLOCKS = ((0, 1), (2, 3), (4, 5))
EXPECTED_ROLES = {
    "forward": ("probe_before", "full", "probe_after"),
    "reverse": ("full_before", "probe_middle", "full_after"),
}
T_CRIT_95_DF2 = 4.302652729911275
A100_PROTOCOL_SOFTMAX_COLS = "512"
A100_PROTOCOL_LOGIT_SCALE = 4.0
A100_PROTOCOL_CACHE_CONDITION = "cache_reuse_candidate"
A100_PROTOCOL_CACHE_POLICY = "default"
CROSS_PLATFORM_ENVIRONMENT_PROFILES = frozenset({"a100", "h100"})
EXP_IMPL_METADATA = {
    "fp32": {
        "canonical": "fp32_fast___expf",
        "legacy_aliases": {"", "fast___expf", "fp32_fast___expf"},
        "numerical_check_id": "fp16_softmax_cpu_fp64_v1_pass",
        "native_validation_id": "",
        "exp_input_dtype": "fp32",
        "exp_ptx_instruction": "ex2.approx.f32",
        "results_per_ptx_instruction": 1,
    },
    "ptx_f16": {
        "canonical": "ptx_ex2_approx_f16",
        "legacy_aliases": {"ptx_ex2_approx_f16"},
        "numerical_check_id": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
        "native_validation_id": "ptx_ex2_f16_all_encodings_v1_pass",
        "exp_input_dtype": "fp16",
        "exp_ptx_instruction": "ex2.approx.f16",
        "results_per_ptx_instruction": 1,
    },
    "ptx_f16x2": {
        "canonical": "ptx_ex2_approx_f16x2",
        "legacy_aliases": {"ptx_ex2_approx_f16x2"},
        "numerical_check_id": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
        "native_validation_id": "ptx_ex2_f16_all_encodings_v1_pass",
        "exp_input_dtype": "fp16x2_packed_b32",
        "exp_ptx_instruction": "ex2.approx.f16x2",
        "results_per_ptx_instruction": 2,
    },
}
EXP_IDENTITY_FIELDS = (
    "exp_impl",
    "exp_input_dtype",
    "special_function_path",
    "exp_ptx_instruction",
    "exp_results_per_ptx_instruction",
    "sass_mufu_ex2_per_ptx_instruction_model",
    "sass_lowering_model_status",
    "expected_control_ex2_scalar_results_per_cta_iter",
    "expected_treatment_ex2_scalar_results_per_cta_iter",
    "expected_probe_ex2_scalar_results_per_cta_iter",
    "expected_control_ex2_ptx_instructions_per_cta_iter",
    "expected_treatment_ex2_ptx_instructions_per_cta_iter",
    "expected_probe_ex2_ptx_instructions_per_cta_iter",
)


def requires_profile_environment_status(
    profile_name: str, *, cross_platform_design: bool
) -> bool:
    """Return whether the portable design requires the generic environment gate.

    The frozen A100 protocol predates the generic field and keeps its legacy
    ``a100_environment_status`` check. The portable 5-S x 4-CTA design uses
    one runner field for both A100 and H100, so it cannot silently inherit the
    A100-only gate.
    """

    return (
        cross_platform_design
        and profile_name in CROSS_PLATFORM_ENVIRONMENT_PROFILES
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def truth(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "pass"}


def note_value(notes: str, key: str) -> str:
    prefix = f"{key}="
    for item in notes.split(";"):
        if item.startswith(prefix):
            return item[len(prefix):]
    return ""


def infer_exp_impl(rows: list[dict[str, str]], requested: str | None) -> str:
    observed = {row.get("exp_impl", "") for row in rows}
    if len(observed) != 1:
        raise SystemExit("raw rows contain more than one exp_impl")
    observed_value = next(iter(observed), "")
    if requested is not None:
        if observed_value not in EXP_IMPL_METADATA[requested]["legacy_aliases"]:
            raise SystemExit(
                f"raw exp_impl {observed_value or '<missing>'} does not match "
                f"--exp-impl {requested}"
            )
        return requested
    matches = [
        name
        for name, metadata in EXP_IMPL_METADATA.items()
        if observed_value in metadata["legacy_aliases"]
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"cannot infer one exponential implementation from {observed_value!r}; "
            "pass --exp-impl"
        )
    return matches[0]


def pair_index(rows: list[dict[str, str]]) -> int:
    values = {int(row.get("repeat", "-1")) for row in rows}
    if len(values) != 1:
        raise ValueError("triplet repeat indices differ")
    return next(iter(values))


def interpolation_weight(
    ordered_rows: list[dict[str, str]],
    ordered_trace_rows: list[list[dict[str, str]]],
) -> float:
    before, center, after = [
        trace_kernel_midpoint_s(trace, num(row, "elapsed_s"))
        for row, trace in zip(ordered_rows, ordered_trace_rows)
    ]
    if not all(math.isfinite(value) for value in (before, center, after)) or after <= before:
        return math.nan
    return (center - before) / (after - before)


def lerp(before: float, after: float, weight: float) -> float:
    return before + weight * (after - before)


def ci_label(low: float, high: float) -> str:
    if low > 0.0:
        return "positive"
    if high < 0.0:
        return "negative"
    return "includes_zero"


def analyze_triplet(
    rows: list[dict[str, str]],
    trace_rows: dict[tuple[str, str], list[dict[str, str]]],
    manifest_rows: dict[tuple[str, str], dict[str, str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    index = pair_index(rows)
    cross_platform_design = bool(getattr(args, "cross_platform_design", False))
    if index < 0 or index >= len(EXPECTED_ORIENTATIONS):
        raise ValueError(f"unexpected pair index {index}")
    orientation = EXPECTED_ORIENTATIONS[index]
    roles = EXPECTED_ROLES[orientation]
    by_role = {row.get("role", ""): row for row in rows}
    pair_id = rows[0].get("pair_id", "")
    reasons: list[str] = []
    if len(rows) != 3 or set(by_role) != set(roles):
        reasons.append("role_set_mismatch")
    ordered = [by_role.get(role, {}) for role in roles]
    for sequence, (role, row) in enumerate(zip(roles, ordered)):
        if row.get("sequence_index") != str(sequence):
            reasons.append(f"{role}_sequence_mismatch")
        expected_extra = orientation == "forward" and sequence == 1
        if orientation == "reverse":
            expected_extra = sequence != 1
        if truth(row.get("extra_exp_probe", "")) != expected_extra:
            reasons.append(f"{role}_probe_state_mismatch")
        if row.get("mode") != "softmax_full_f16io_f32acc":
            reasons.append(f"{role}_kernel_mode_mismatch")
        if row.get("numerical_check_id") != args.numerical_check_id:
            reasons.append(f"{role}_numerical_check_mismatch")
        if row.get("exp_impl", "") not in args.exp_impl_metadata["legacy_aliases"]:
            reasons.append(f"{role}_exp_impl_mismatch")
        if args.exp_impl != "fp32":
            if row.get("exp_input_dtype") != args.exp_impl_metadata[
                "exp_input_dtype"
            ]:
                reasons.append(f"{role}_exp_input_dtype_mismatch")
            if row.get("exp_ptx_instruction") != args.exp_impl_metadata[
                "exp_ptx_instruction"
            ]:
                reasons.append(f"{role}_exp_ptx_instruction_mismatch")
            if row.get("exp_results_per_ptx_instruction") != str(
                args.exp_impl_metadata["results_per_ptx_instruction"]
            ):
                reasons.append(f"{role}_exp_ptx_denominator_mismatch")
            try:
                cols = int(row.get("softmax_cols", ""))
                results_per_ptx = int(
                    args.exp_impl_metadata["results_per_ptx_instruction"]
                )
                expected_denominators = {
                    "expected_control_ex2_scalar_results_per_cta_iter": cols,
                    "expected_treatment_ex2_scalar_results_per_cta_iter": 2
                    * cols,
                    "expected_probe_ex2_scalar_results_per_cta_iter": cols,
                    "expected_control_ex2_ptx_instructions_per_cta_iter": cols
                    // results_per_ptx,
                    "expected_treatment_ex2_ptx_instructions_per_cta_iter": 2
                    * cols
                    // results_per_ptx,
                    "expected_probe_ex2_ptx_instructions_per_cta_iter": cols
                    // results_per_ptx,
                }
            except ValueError:
                reasons.append(f"{role}_exp_denominator_metadata_invalid")
            else:
                for field, expected in expected_denominators.items():
                    if row.get(field) != str(expected):
                        reasons.append(f"{role}_{field}_mismatch")
        if row.get("energy_source") != "nvml_total_energy" or not truth(
            row.get("nvml_total_energy_supported", "")
        ):
            reasons.append(f"{role}_energy_source_mismatch")
        if "interior_theil_sen" not in row.get("energy_integration_method", ""):
            reasons.append(f"{role}_integration_method_mismatch")
        if not truth(row.get("smid_all_blocks_observed", "")):
            reasons.append(f"{role}_smid_observation_failed")
        if not truth(row.get("static_single_wave_capacity_gate_pass", "")):
            reasons.append(f"{role}_static_capacity_failed")
        if not truth(row.get("occupancy_gate_pass", "")):
            reasons.append(f"{role}_occupancy_failed")
        if manifest_rows:
            manifest = manifest_rows.get((pair_id, role), {})
            if manifest.get("quiescence_status") != "pass":
                reasons.append(f"{role}_quiescence_not_pass")
            if manifest.get("binary_sha256") != row.get("binary_sha256"):
                reasons.append(f"{role}_manifest_binary_mismatch")
            if manifest.get("cuda_pci_bus_id") != row.get("cuda_pci_bus_id"):
                reasons.append(f"{role}_manifest_pci_mismatch")
            if manifest.get("numerical_check_id") != args.numerical_check_id:
                reasons.append(f"{role}_manifest_numerical_check_mismatch")
            if args.exp_impl != "fp32" and manifest.get(
                "native_ex2_validation_id"
            ) != args.exp_impl_metadata["native_validation_id"]:
                reasons.append(f"{role}_manifest_native_validation_mismatch")
            try:
                configured_fit_points = int(
                    manifest.get("energy_trace_min_updates", "")
                )
            except ValueError:
                reasons.append(f"{role}_manifest_trace_gate_invalid")
            else:
                if configured_fit_points < args.energy_trace_min_fit_points:
                    reasons.append(
                        f"{role}_manifest_trace_gate_below_analysis_gate"
                    )
            for field in EXP_IDENTITY_FIELDS:
                if field in manifest and manifest.get(field, "") != row.get(field, ""):
                    reasons.append(f"{role}_manifest_{field}_mismatch")
            profile_name = row.get("profile_name", "")
            if (
                not cross_platform_design
                and profile_name == "a100"
                and (
                    manifest.get("softmax_cols") != A100_PROTOCOL_SOFTMAX_COLS
                    or manifest.get("cache_condition")
                    != A100_PROTOCOL_CACHE_CONDITION
                    or manifest.get("cache_policy") != A100_PROTOCOL_CACHE_POLICY
                    or manifest.get("logit_scale")
                    != str(A100_PROTOCOL_LOGIT_SCALE)
                )
            ):
                reasons.append(f"{role}_manifest_protocol_coordinate_mismatch")
            if requires_profile_environment_status(
                profile_name,
                cross_platform_design=cross_platform_design,
            ):
                if manifest.get("profile_environment_status") != "pass":
                    reasons.append(f"{role}_profile_environment_not_pass")
            elif (
                profile_name == "a100"
                and manifest.get("a100_environment_status") != "pass"
            ):
                reasons.append(f"{role}_a100_environment_not_pass")

    identity_fields = (
        "gpu_id", "profile_name", "cuda_pci_bus_id", "cuda_binary_arch",
        "softmax_cols", "grid_blocks", "ITER", "n_elements",
        "cache_condition", "cache_policy", "binary_sha256", "bracket_context_id",
        "exp_input_dtype", "special_function_path",
        "xu_documented_results_per_sm_cycle",
        *EXP_IDENTITY_FIELDS,
    )
    for field in identity_fields:
        if len({row.get(field, "") for row in rows}) != 1:
            reasons.append(f"identity_mismatch_{field}")
    if all("smid_set" in row for row in rows):
        smid_sets = {row.get("smid_set", "") for row in rows}
        if "" in smid_sets or "not_checked" in smid_sets:
            reasons.append("smid_set_missing")
        elif len(smid_sets) != 1:
            reasons.append("smid_set_mismatch_within_triplet")
    if any(row.get("profile_name") == "a100" for row in rows):
        for row in rows:
            grid = int(row.get("grid_blocks", "-1"))
            runtime_sms = int(row.get("runtime_sm_count", "-1"))
            unique_sms = int(row.get("smid_unique", "-1"))
            max_blocks = int(row.get("smid_assignment_max_blocks_per_sm", "-1"))
            if grid <= 0 or runtime_sms != 108:
                reasons.append("a100_grid_or_runtime_sm_mismatch")
                break
            if grid <= runtime_sms and (unique_sms != grid or max_blocks != 1):
                reasons.append("a100_underfill_not_one_distinct_cta_per_smid")
                break
    if any(row.get("execution_model") !=
           "persistent_cuda_context_bracket_v3_counterbalanced6" for row in rows):
        reasons.append("execution_model_mismatch")
    if any(row.get("energy_trace_status") != "pass" for row in rows):
        reasons.append("row_trace_status_not_pass")

    analyses = []
    ordered_trace_rows = [trace_rows.get((pair_id, role), []) for role in roles]
    for role_number, role in enumerate(roles):
        analysis = analyze_trace_role(
            ordered_trace_rows[role_number],
            args,
            args.seed + index * 100_003 + role_number * 1_009,
        )
        analyses.append(analysis)
        if analysis["status"] != "pass":
            reasons.append(f"{role}_{analysis['reason']}")
        if int(analysis["fit_points"]) < args.energy_trace_min_fit_points:
            reasons.append(f"{role}_fit_points_below_gate")
        if not math.isfinite(float(analysis["r2"])) or float(analysis["r2"]) < args.min_trace_r2:
            reasons.append(f"{role}_trace_r2_below_gate")

    weight = interpolation_weight(ordered, ordered_trace_rows)
    if not math.isfinite(weight) or not 0.0 <= weight <= 1.0:
        reasons.append("interpolation_weight_invalid")
    n_values = [num(row, "n_elements") for row in ordered]
    if not all(math.isfinite(value) and value > 0.0 for value in n_values):
        reasons.append("logical_scalar_exponent_result_count_invalid")
    results_per_ptx_instruction = int(
        args.exp_impl_metadata["results_per_ptx_instruction"]
    )
    try:
        logical_scalar_exponent_results: int | float = int(
            ordered[1].get("n_elements", "")
        )
    except ValueError:
        logical_scalar_exponent_results = math.nan
    if (
        args.exp_impl != "fp32"
        and isinstance(logical_scalar_exponent_results, int)
        and logical_scalar_exponent_results > 0
        and logical_scalar_exponent_results % results_per_ptx_instruction == 0
    ):
        ptx_ex2_instructions: int | float = (
            logical_scalar_exponent_results // results_per_ptx_instruction
        )
    else:
        ptx_ex2_instructions = math.nan
        if args.exp_impl != "fp32":
            reasons.append("nonintegral_ptx_ex2_instruction_denominator")

    powers = [float(analysis["power_W"]) for analysis in analyses]
    elapsed = [num(row, "elapsed_s") for row in ordered]
    if orientation == "forward":
        contrast_power = powers[1] - lerp(powers[0], powers[2], weight)
        treatment_seconds_per_operand = elapsed[1] / n_values[1]
    else:
        contrast_power = lerp(powers[0], powers[2], weight) - powers[1]
        # Normalize by the interpolated treatment logical-result rate.
        # Interpolating seconds/result would be a different estimand (the numerical
        # difference is small here because outer treatment durations match,
        # but the rate form is the protocol definition).
        treatment_operand_rate = lerp(
            n_values[0] / elapsed[0], n_values[2] / elapsed[2], weight
        )
        treatment_seconds_per_operand = 1.0 / treatment_operand_rate
    effect_pj = contrast_power * treatment_seconds_per_operand * 1.0e12
    treatment_seconds_per_ptx_ex2_instruction = (
        treatment_seconds_per_operand * results_per_ptx_instruction
        if args.exp_impl != "fp32"
        else math.nan
    )
    effect_pj_per_ptx_ex2_instruction = (
        effect_pj * results_per_ptx_instruction
        if args.exp_impl != "fp32"
        else math.nan
    )

    bootstrap_count = min(
        (len(analysis["bootstrap_power_W"]) for analysis in analyses),
        default=0,
    )
    bootstrap_effects: list[float] = []
    for draw in range(bootstrap_count):
        draw_powers = [analysis["bootstrap_power_W"][draw] for analysis in analyses]
        if orientation == "forward":
            draw_contrast = draw_powers[1] - lerp(draw_powers[0], draw_powers[2], weight)
        else:
            draw_contrast = lerp(draw_powers[0], draw_powers[2], weight) - draw_powers[1]
        bootstrap_effects.append(draw_contrast * treatment_seconds_per_operand * 1.0e12)
    ci_low = percentile(bootstrap_effects, 0.025)
    ci_high = percentile(bootstrap_effects, 0.975)

    temperature_values = [
        num(row, field) for row in ordered for field in ("temp_before_C", "temp_after_C")
    ]
    if not all(math.isfinite(value) and value > 0.0 for value in temperature_values):
        reasons.append("temperature_telemetry_missing")
    temp_span = (
        max(temperature_values) - min(temperature_values)
        if all(math.isfinite(value) and value > 0.0 for value in temperature_values)
        else math.nan
    )
    role_gaps = [
        num(row, "preceding_role_gap_s") for row in ordered[1:]
    ]
    max_role_gap = max(role_gaps) if all(math.isfinite(value) for value in role_gaps) else math.nan
    if not math.isfinite(max_role_gap) or max_role_gap > args.max_inter_role_gap_s:
        reasons.append("inter_role_gap_gate_failed")
    clock_values = [
        num(row, field) for row in ordered
        for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
    ]
    clock_median = statistics.median(clock_values) if all(
        math.isfinite(value) and value > 0.0 for value in clock_values
    ) else math.nan
    clock_span_fraction = (
        (max(clock_values) - min(clock_values)) / clock_median
        if math.isfinite(clock_median) else math.nan
    )
    if (not math.isfinite(clock_span_fraction) or
            clock_span_fraction > args.max_sm_clock_span_fraction):
        reasons.append("sm_clock_span_gate_failed")
    if any(row.get("profile_name") == "a100" for row in rows):
        if args.a100_batch_sm_clock_status != "pass":
            reasons.append("a100_batch_sm_clock_span_gate_failed")
        if args.a100_batch_temperature_status != "pass":
            reasons.append("a100_batch_temperature_telemetry_missing")
        if args.a100_batch_smid_status != "pass":
            reasons.append("a100_batch_smid_set_mismatch")
    fit_points = [int(analysis["fit_points"]) for analysis in analyses]
    r2_values = [float(analysis["r2"]) for analysis in analyses]
    query_latency_values = [float(analysis["max_query_latency_s"]) for analysis in analyses]
    result = {
        "pair_id": pair_id,
        "pair_index": index,
        "orientation": orientation,
        "role_order": "->".join(roles),
        "profile_name": ordered[0].get("profile_name", ""),
        "cuda_pci_bus_id": ordered[0].get("cuda_pci_bus_id", ""),
        "cuda_binary_arch": ordered[0].get("cuda_binary_arch", ""),
        "grid_blocks": ordered[0].get("grid_blocks", ""),
        "ITER": ordered[0].get("ITER", ""),
        "n_elements": ordered[0].get("n_elements", ""),
        "exp_impl": args.exp_impl_metadata["canonical"],
        "exp_ptx_instruction": args.exp_impl_metadata["exp_ptx_instruction"],
        "exp_results_per_ptx_instruction": results_per_ptx_instruction,
        "bracket_context_id": ordered[0].get("bracket_context_id", ""),
        "smid_set": ordered[0].get("smid_set", ""),
        "smid_histogram": ordered[0].get("smid_histogram", ""),
        "special_function_path": ordered[0].get("special_function_path", ""),
        "xu_documented_results_per_sm_cycle": ordered[0].get(
            "xu_documented_results_per_sm_cycle", ""
        ),
        "sfu_regime_evidence_status": ordered[0].get(
            "sfu_regime_evidence_status", ""
        ),
        "interpolation_weight": weight,
        "outer_before_power_W": powers[0],
        "middle_power_W": powers[1],
        "outer_after_power_W": powers[2],
        "treatment_minus_control_power_W": contrast_power,
        "logical_scalar_exponent_results": logical_scalar_exponent_results,
        "ptx_ex2_instructions": ptx_ex2_instructions,
        "primary_denominator": "logical_scalar_exponent_result",
        "treatment_seconds_per_operand": treatment_seconds_per_operand,
        "treatment_seconds_per_logical_scalar_exponent_result": treatment_seconds_per_operand,
        "treatment_seconds_per_ptx_ex2_instruction": treatment_seconds_per_ptx_ex2_instruction,
        "effect_pJ_per_operand": effect_pj,
        "effect_pJ_per_logical_scalar_exponent_result": effect_pj,
        "effect_pJ_per_ptx_ex2_instruction": effect_pj_per_ptx_ex2_instruction,
        "residual_mbb_ci_low_pJ_per_operand": ci_low,
        "residual_mbb_ci_high_pJ_per_operand": ci_high,
        "residual_mbb_ci_low_pJ_per_logical_scalar_exponent_result": ci_low,
        "residual_mbb_ci_high_pJ_per_logical_scalar_exponent_result": ci_high,
        "residual_mbb_ci_low_pJ_per_ptx_ex2_instruction": (
            ci_low * results_per_ptx_instruction
            if args.exp_impl != "fp32"
            else math.nan
        ),
        "residual_mbb_ci_high_pJ_per_ptx_ex2_instruction": (
            ci_high * results_per_ptx_instruction
            if args.exp_impl != "fp32"
            else math.nan
        ),
        "triplet_ci_label_diagnostic_only": ci_label(ci_low, ci_high),
        "min_trace_fit_points": min(fit_points),
        "min_trace_r2": min(r2_values),
        "max_query_latency_s": max(query_latency_values),
        "max_inter_role_gap_s": max_role_gap,
        "sm_clock_span_fraction": clock_span_fraction,
        "a100_batch_sm_clock_span_fraction": args.a100_batch_sm_clock_span_fraction,
        "a100_batch_sm_clock_status": args.a100_batch_sm_clock_status,
        "a100_batch_temperature_status": args.a100_batch_temperature_status,
        "a100_batch_smid_status": args.a100_batch_smid_status,
        "temperature_span_C": temp_span,
        "quality_status": "pass" if not reasons else "fail",
        "reasons": ";".join(dict.fromkeys(reasons)),
        "_bootstrap_effects": bootstrap_effects,
    }
    return result


def build_matched_blocks(triplets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index = {int(row["pair_index"]): row for row in triplets}
    blocks: list[dict[str, Any]] = []
    for block_id, pair_indices in enumerate(MATCHED_BLOCKS):
        selected = [by_index[index] for index in pair_indices]
        forward = next(row for row in selected if row["orientation"] == "forward")
        reverse = next(row for row in selected if row["orientation"] == "reverse")
        forward_value = float(forward["effect_pJ_per_operand"])
        reverse_value = float(reverse["effect_pJ_per_operand"])
        results_per_ptx_instruction = int(
            forward["exp_results_per_ptx_instruction"]
        )
        ptx_applicable = forward["exp_impl"] != EXP_IMPL_METADATA["fp32"][
            "canonical"
        ]
        draw_count = min(len(forward["_bootstrap_effects"]), len(reverse["_bootstrap_effects"]))
        effect_draws = [
            (forward["_bootstrap_effects"][draw] + reverse["_bootstrap_effects"][draw]) / 2.0
            for draw in range(draw_count)
        ]
        blocks.append(
            {
                "matched_block": block_id,
                "chronological_orientation_order": "-".join(
                    by_index[index]["orientation"][0].upper() for index in pair_indices
                ),
                "forward_pair_id": forward["pair_id"],
                "reverse_pair_id": reverse["pair_id"],
                "exp_impl": forward["exp_impl"],
                "exp_ptx_instruction": forward["exp_ptx_instruction"],
                "exp_results_per_ptx_instruction": results_per_ptx_instruction,
                "logical_scalar_exponent_results_per_treatment_role": forward[
                    "logical_scalar_exponent_results"
                ],
                "ptx_ex2_instructions_per_treatment_role": forward[
                    "ptx_ex2_instructions"
                ],
                "primary_denominator": "logical_scalar_exponent_result",
                "forward_pJ_per_operand": forward_value,
                "reverse_pJ_per_operand": reverse_value,
                "order_balanced_effect_pJ_per_operand": (forward_value + reverse_value) / 2.0,
                "middle_position_bias_pJ_per_operand": (forward_value - reverse_value) / 2.0,
                "forward_pJ_per_logical_scalar_exponent_result": forward_value,
                "reverse_pJ_per_logical_scalar_exponent_result": reverse_value,
                "order_balanced_effect_pJ_per_logical_scalar_exponent_result": (
                    forward_value + reverse_value
                )
                / 2.0,
                "middle_position_bias_pJ_per_logical_scalar_exponent_result": (
                    forward_value - reverse_value
                )
                / 2.0,
                "forward_pJ_per_ptx_ex2_instruction": (
                    forward_value * results_per_ptx_instruction
                    if ptx_applicable
                    else math.nan
                ),
                "reverse_pJ_per_ptx_ex2_instruction": (
                    reverse_value * results_per_ptx_instruction
                    if ptx_applicable
                    else math.nan
                ),
                "order_balanced_effect_pJ_per_ptx_ex2_instruction": (
                    (forward_value + reverse_value)
                    * results_per_ptx_instruction
                    / 2.0
                    if ptx_applicable
                    else math.nan
                ),
                "middle_position_bias_pJ_per_ptx_ex2_instruction": (
                    (forward_value - reverse_value)
                    * results_per_ptx_instruction
                    / 2.0
                    if ptx_applicable
                    else math.nan
                ),
                "max_temperature_span_C": max(
                    float(forward["temperature_span_C"]), float(reverse["temperature_span_C"])
                ),
                "smid_set_match": forward.get("smid_set", "") == reverse.get("smid_set", ""),
                "quality_status": (
                    "pass"
                    if forward["quality_status"] == reverse["quality_status"] == "pass"
                    and forward.get("smid_set", "") == reverse.get("smid_set", "")
                    else "fail"
                ),
                "_effect_draws": effect_draws,
            }
        )
    return blocks


def summarize(
    triplets: list[dict[str, Any]], blocks: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    effects = [float(row["order_balanced_effect_pJ_per_operand"]) for row in blocks]
    biases = [float(row["middle_position_bias_pJ_per_operand"]) for row in blocks]
    forward = [float(row["effect_pJ_per_operand"]) for row in triplets if row["orientation"] == "forward"]
    reverse = [float(row["effect_pJ_per_operand"]) for row in triplets if row["orientation"] == "reverse"]
    mean = statistics.fmean(effects)
    # Python 3.12's statistics.stdev raises an internal AttributeError when a
    # failed trace contributes NaN.  Preserve that failed-quality state as
    # NaN so the analyzer emits an invalid/not-identified verdict instead of
    # crashing before it can write the gate reasons.
    standard_deviation = math.sqrt(
        sum((value - mean) ** 2 for value in effects) / (len(effects) - 1)
    )
    standard_error = standard_deviation / math.sqrt(len(effects))
    t_low = mean - T_CRIT_95_DF2 * standard_error
    t_high = mean + T_CRIT_95_DF2 * standard_error

    generator = random.Random(args.seed + 9_999_991)
    hierarchical: list[float] = []
    if blocks and all(block["_effect_draws"] for block in blocks):
        for _ in range(args.bootstrap_samples):
            selected_blocks = [generator.randrange(len(blocks)) for _ in blocks]
            draw_values = []
            for block_index in selected_blocks:
                draws = blocks[block_index]["_effect_draws"]
                draw_values.append(draws[generator.randrange(len(draws))])
            hierarchical.append(statistics.fmean(draw_values))
    mbb_low = percentile(hierarchical, 0.025)
    mbb_high = percentile(hierarchical, 0.975)
    combined_low = min(t_low, mbb_low)
    combined_high = max(t_high, mbb_high)
    results_per_ptx_instruction = int(
        triplets[0]["exp_results_per_ptx_instruction"]
    )
    ptx_applicable = triplets[0]["exp_impl"] != EXP_IMPL_METADATA["fp32"][
        "canonical"
    ]
    ptx_multiplier = (
        float(results_per_ptx_instruction) if ptx_applicable else math.nan
    )
    quality_pass = all(row["quality_status"] == "pass" for row in triplets + blocks)
    positive_signs = sum(value > 0.0 for value in effects)
    accepted = (
        quality_pass
        and positive_signs == len(effects)
        and statistics.fmean(forward) > 0.0
        and statistics.fmean(reverse) > 0.0
        and t_low > 0.0
        and mbb_low > 0.0
    )
    return {
        "protocol": "same_context_counterbalanced_probe_v1",
        "exp_impl": triplets[0]["exp_impl"],
        "exp_ptx_instruction": triplets[0]["exp_ptx_instruction"],
        "exp_results_per_ptx_instruction": results_per_ptx_instruction,
        "primary_denominator": "logical_scalar_exponent_result",
        "logical_scalar_exponent_results_per_treatment_role": triplets[0][
            "logical_scalar_exponent_results"
        ],
        "ptx_ex2_instructions_per_treatment_role": triplets[0][
            "ptx_ex2_instructions"
        ],
        "bootstrap_samples": args.bootstrap_samples,
        "bootstrap_seed": args.seed,
        "decision_stage": args.decision_stage,
        "configured_energy_trace_min_fit_points": (
            args.energy_trace_min_fit_points
        ),
        "residual_mbb_block_points": (
            args.energy_trace_block_updates
            if args.energy_trace_block_updates > 0
            else "auto_round_sqrt_fit_points"
        ),
        "grid_blocks": triplets[0]["grid_blocks"],
        "measured_triplets": len(triplets),
        "matched_orientation_blocks": len(blocks),
        "min_trace_fit_points": min(int(row["min_trace_fit_points"]) for row in triplets),
        "min_trace_r2": min(float(row["min_trace_r2"]) for row in triplets),
        "max_query_latency_s": max(float(row["max_query_latency_s"]) for row in triplets),
        "max_inter_role_gap_s": max(float(row["max_inter_role_gap_s"]) for row in triplets),
        "max_sm_clock_span_fraction": max(float(row["sm_clock_span_fraction"]) for row in triplets),
        "a100_batch_sm_clock_span_fraction": triplets[0][
            "a100_batch_sm_clock_span_fraction"
        ],
        "a100_batch_sm_clock_status": triplets[0]["a100_batch_sm_clock_status"],
        "a100_batch_temperature_status": triplets[0][
            "a100_batch_temperature_status"
        ],
        "a100_batch_smid_status": triplets[0]["a100_batch_smid_status"],
        "max_triplet_temperature_span_C": max(float(row["temperature_span_C"]) for row in triplets),
        "forward_mean_pJ_per_operand": statistics.fmean(forward),
        "reverse_mean_pJ_per_operand": statistics.fmean(reverse),
        "order_balanced_mean_pJ_per_operand": mean,
        "order_balanced_median_pJ_per_operand": statistics.median(effects),
        "order_balanced_min_pJ_per_operand": min(effects),
        "order_balanced_max_pJ_per_operand": max(effects),
        "order_balanced_sd_pJ_per_operand": standard_deviation,
        "matched_positive_blocks": positive_signs,
        "pair_t95_ci_low_pJ_per_operand": t_low,
        "pair_t95_ci_high_pJ_per_operand": t_high,
        "hierarchical_residual_mbb_ci_low_pJ_per_operand": mbb_low,
        "hierarchical_residual_mbb_ci_high_pJ_per_operand": mbb_high,
        "conservative_ci_low_pJ_per_operand": combined_low,
        "conservative_ci_high_pJ_per_operand": combined_high,
        "middle_position_bias_mean_pJ_per_operand": statistics.fmean(biases),
        "middle_position_bias_median_pJ_per_operand": statistics.median(biases),
        "forward_mean_pJ_per_logical_scalar_exponent_result": statistics.fmean(
            forward
        ),
        "reverse_mean_pJ_per_logical_scalar_exponent_result": statistics.fmean(
            reverse
        ),
        "order_balanced_mean_pJ_per_logical_scalar_exponent_result": mean,
        "pair_t95_ci_low_pJ_per_logical_scalar_exponent_result": t_low,
        "pair_t95_ci_high_pJ_per_logical_scalar_exponent_result": t_high,
        "hierarchical_residual_mbb_ci_low_pJ_per_logical_scalar_exponent_result": mbb_low,
        "hierarchical_residual_mbb_ci_high_pJ_per_logical_scalar_exponent_result": mbb_high,
        "order_balanced_mean_pJ_per_ptx_ex2_instruction": mean
        * ptx_multiplier,
        "pair_t95_ci_low_pJ_per_ptx_ex2_instruction": t_low
        * ptx_multiplier,
        "pair_t95_ci_high_pJ_per_ptx_ex2_instruction": t_high
        * ptx_multiplier,
        "hierarchical_residual_mbb_ci_low_pJ_per_ptx_ex2_instruction": mbb_low
        * ptx_multiplier,
        "hierarchical_residual_mbb_ci_high_pJ_per_ptx_ex2_instruction": mbb_high
        * ptx_multiplier,
        "quality_status": "pass" if quality_pass else "fail",
        "verdict": (
            f"positive_identified_{args.decision_stage}"
            if accepted
            else "not_identified"
        ),
    }


def write_report(path: Path, summary: dict[str, Any], blocks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ptx_line = (
        "- auxiliary PTX-op effect: "
        f"{float(summary['order_balanced_mean_pJ_per_ptx_ex2_instruction']):.3f} "
        f"pJ/{summary['exp_ptx_instruction']} instruction "
        f"({summary['ptx_ex2_instructions_per_treatment_role']} instructions/role)"
        if math.isfinite(
            float(summary["ptx_ex2_instructions_per_treatment_role"])
        )
        else "- auxiliary PTX-op effect: not applicable to the CUDA `__expf` path"
    )
    lines = [
        "# FP16 Softmax counterbalanced probe 결과",
        "",
        "## 판정",
        "",
        f"- verdict: `{summary['verdict']}`",
        f"- decision stage: `{summary['decision_stage']}`",
        f"- configured/observed minimum fit points: "
        f"{summary['configured_energy_trace_min_fit_points']}/"
        f"{summary['min_trace_fit_points']}",
        f"- exp implementation: `{summary['exp_impl']}`",
        f"- order-balanced effect: {float(summary['order_balanced_mean_pJ_per_operand']):.3f} pJ/logical scalar exponent result",
        f"- pair-t 95% CI: [{float(summary['pair_t95_ci_low_pJ_per_operand']):.3f}, {float(summary['pair_t95_ci_high_pJ_per_operand']):.3f}] pJ/logical scalar exponent result",
        f"- hierarchical residual-MBB 95% CI: [{float(summary['hierarchical_residual_mbb_ci_low_pJ_per_operand']):.3f}, {float(summary['hierarchical_residual_mbb_ci_high_pJ_per_operand']):.3f}] pJ/logical scalar exponent result",
        f"- middle-position bias mean: {float(summary['middle_position_bias_mean_pJ_per_operand']):.3f} pJ/logical scalar exponent result",
        ptx_line,
        "",
        "1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.",
        "",
        "## Matched block",
        "",
        "| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in blocks:
        lines.append(
            f"| {row['matched_block']} | {row['chronological_orientation_order']} | "
            f"{float(row['forward_pJ_per_operand']):.3f} | "
            f"{float(row['reverse_pJ_per_operand']):.3f} | "
            f"{float(row['order_balanced_effect_pJ_per_operand']):.3f} | "
            f"{float(row['middle_position_bias_pJ_per_operand']):.3f} | "
            f"{row['quality_status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--input", type=Path, required=True)
    result.add_argument("--energy-trace-input", type=Path, required=True)
    result.add_argument("--manifest", type=Path)
    result.add_argument(
        "--cross-platform-design",
        action="store_true",
        help=(
            "analyze the portable 5-S x 4-CTA design; bypass only the frozen "
            "A100 S512/scale4/cache coordinate and require "
            "profile_environment_status=pass for A100/H100"
        ),
    )
    result.add_argument(
        "--exp-impl",
        choices=tuple(EXP_IMPL_METADATA),
        default=None,
        help="expected implementation; inferred from raw exp_impl when omitted",
    )
    result.add_argument(
        "--grid-blocks",
        type=int,
        help="select one CTA coordinate when the bounded runner emitted multiple grids",
    )
    result.add_argument("--triplet-out", type=Path, required=True)
    result.add_argument("--matched-out", type=Path, required=True)
    result.add_argument("--summary-out", type=Path, required=True)
    result.add_argument("--report-out", type=Path)
    result.add_argument(
        "--decision-stage",
        choices=("pilot", "confirmation"),
        default="pilot",
        help=(
            "labels a positive verdict; confirmation additionally requires "
            "a configured fit-point gate of at least 16"
        ),
    )
    result.add_argument("--energy-trace-min-fit-points", type=int, default=16)
    result.add_argument("--bootstrap-samples", type=int, default=4000)
    result.add_argument("--energy-trace-block-updates", type=int, default=0)
    result.add_argument(
        "--numerical-check-id",
        default=None,
        help="defaults to the implementation-specific validation pass id",
    )
    result.add_argument("--min-trace-r2", type=float, default=0.98)
    result.add_argument("--max-inter-role-gap-s", type=float, default=0.25)
    result.add_argument("--max-sm-clock-span-fraction", type=float, default=0.15)
    result.add_argument("--seed", type=int, default=20260722)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.energy_trace_min_fit_points < 8 or args.bootstrap_samples < 1000:
        raise SystemExit("min fit points must be >=8 and bootstrap samples >=1000")
    if (
        args.decision_stage == "confirmation"
        and args.energy_trace_min_fit_points < 16
    ):
        raise SystemExit(
            "confirmation requires --energy-trace-min-fit-points >=16"
        )
    # analyze_trace_role expects these names.
    args.energy_trace_bootstrap_samples = args.bootstrap_samples
    raw = [
        row
        for row in read_csv(args.input)
        if row.get("pair_id")
        and (args.grid_blocks is None or row.get("grid_blocks") == str(args.grid_blocks))
    ]
    args.exp_impl = infer_exp_impl(raw, args.exp_impl)
    args.exp_impl_metadata = EXP_IMPL_METADATA[args.exp_impl]
    if args.numerical_check_id is None:
        args.numerical_check_id = args.exp_impl_metadata["numerical_check_id"]
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw:
        groups[row["pair_id"]].append(row)
    if len(raw) != 18 or len(groups) != 6:
        raise SystemExit(f"counterbalanced protocol requires 18 rows/6 triplets; got {len(raw)}/{len(groups)}")
    contexts = {row.get("bracket_context_id", "") for row in raw}
    if len(contexts) != 1 or not next(iter(contexts), ""):
        raise SystemExit("all six triplets must share one non-empty CUDA context id")
    is_a100 = any(row.get("profile_name") == "a100" for row in raw)
    if is_a100 and not args.cross_platform_design:
        try:
            logit_scales = {
                float(note_value(row.get("notes", ""), "logit_scale"))
                for row in raw
            }
        except ValueError as error:
            raise SystemExit("A100 raw logit_scale metadata is invalid") from error
        if (
            {row.get("softmax_cols", "") for row in raw}
            != {A100_PROTOCOL_SOFTMAX_COLS}
            or {row.get("cache_condition", "") for row in raw}
            != {A100_PROTOCOL_CACHE_CONDITION}
            or {row.get("cache_policy", "") for row in raw}
            != {A100_PROTOCOL_CACHE_POLICY}
            or logit_scales != {A100_PROTOCOL_LOGIT_SCALE}
        ):
            raise SystemExit(
                "A100 energy evidence must use the frozen S512/scale4/"
                "cache_reuse_candidate/default coordinate"
            )
    batch_temperatures = [
        num(row, field)
        for row in raw
        for field in ("temp_before_C", "temp_after_C")
    ]
    args.a100_batch_temperature_status = (
        "pass"
        if is_a100
        and all(math.isfinite(value) and value > 0.0 for value in batch_temperatures)
        else "fail" if is_a100 else "not_applicable"
    )
    batch_clocks = [
        num(row, field)
        for row in raw
        for field in ("clock_sm_before_mhz", "clock_sm_after_mhz")
    ]
    batch_clock_median = (
        statistics.median(batch_clocks)
        if is_a100
        and all(math.isfinite(value) and value > 0.0 for value in batch_clocks)
        else math.nan
    )
    args.a100_batch_sm_clock_span_fraction = (
        (max(batch_clocks) - min(batch_clocks)) / batch_clock_median
        if math.isfinite(batch_clock_median)
        else math.nan
    )
    args.a100_batch_sm_clock_status = (
        "pass"
        if is_a100
        and math.isfinite(args.a100_batch_sm_clock_span_fraction)
        and args.a100_batch_sm_clock_span_fraction <= args.max_sm_clock_span_fraction
        else "fail" if is_a100 else "not_applicable"
    )
    batch_smid_sets = {row.get("smid_set", "") for row in raw}
    args.a100_batch_smid_status = (
        "pass"
        if is_a100 and len(batch_smid_sets) == 1 and "" not in batch_smid_sets
        else "fail" if is_a100 else "not_applicable"
    )
    trace = read_energy_trace(args.energy_trace_input)
    if args.exp_impl != "fp32" and args.manifest is None:
        raise SystemExit(
            "native EX2 analysis requires --manifest so implementation and PTX "
            "denominator identity cannot be bypassed"
        )
    requires_cross_platform_manifest = args.cross_platform_design and any(
        requires_profile_environment_status(
            row.get("profile_name", ""),
            cross_platform_design=True,
        )
        for row in raw
    )
    if requires_cross_platform_manifest and args.manifest is None:
        raise SystemExit(
            "cross-platform A100/H100 counterbalanced analysis requires --manifest "
            "so profile_environment_status can be enforced"
        )
    if is_a100 and not args.cross_platform_design and args.manifest is None:
        raise SystemExit(
            "A100 counterbalanced analysis requires --manifest so quiescence, "
            "device identity, competing-process, and slowdown-counter gates cannot be bypassed"
        )
    manifest_rows: dict[tuple[str, str], dict[str, str]] = {}
    if args.manifest:
        manifest_source = read_csv(args.manifest)
        manifest_rows = {}
        for manifest_row in manifest_source:
            key = (manifest_row.get("pair_id", ""), manifest_row.get("role", ""))
            if key in manifest_rows:
                raise SystemExit(f"manifest contains duplicate role row: {key[0]}/{key[1]}")
            manifest_rows[key] = manifest_row
        expected_manifest_keys = {
            (row.get("pair_id", ""), row.get("role", "")) for row in raw
        }
        missing_manifest_keys = expected_manifest_keys - set(manifest_rows)
        if missing_manifest_keys:
            raise SystemExit(
                "manifest is missing raw role rows: "
                + ",".join(f"{pair}/{role}" for pair, role in sorted(missing_manifest_keys))
            )
    triplets = sorted(
        (analyze_triplet(rows, trace, manifest_rows, args) for rows in groups.values()),
        key=lambda row: int(row["pair_index"]),
    )
    if [row["orientation"] for row in triplets] != list(EXPECTED_ORIENTATIONS):
        raise SystemExit("measured orientation order does not match counterbalanced6")
    blocks = build_matched_blocks(triplets)
    summary = summarize(triplets, blocks, args)
    public_triplets = [{key: value for key, value in row.items() if not key.startswith("_")} for row in triplets]
    public_blocks = [{key: value for key, value in row.items() if not key.startswith("_")} for row in blocks]
    write_csv(args.triplet_out, public_triplets)
    write_csv(args.matched_out, public_blocks)
    write_csv(args.summary_out, [summary])
    if args.report_out:
        write_report(args.report_out, summary, public_blocks)
    print(f"triplet_out={args.triplet_out}")
    print(f"matched_out={args.matched_out}")
    print(f"summary_out={args.summary_out}")
    print(f"verdict={summary['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
