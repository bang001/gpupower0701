#!/usr/bin/env python3
"""Audit energy CSV rows against the repository power API matrix.

This is a pre-analysis gate. It does not validate cache paths or compute final
coefficients. It only checks whether the energy numerator rows are suitable for
final matched-control component analysis under
docs/platforms/power_measurement_api_matrix_ko.md.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PROFILE_POWER_SEMANTICS = {
    "rtx3090": "one_sec_average",
    "3090": "one_sec_average",
    "ga102": "one_sec_average",
    "v100": "instant",
    "gv100": "instant",
    "a100": "instant",
    "ga100": "instant",
    "h100": "one_sec_average",
    "gh100": "one_sec_average",
}

REQUIRED_COLUMNS = {
    "profile_name",
    "chip",
    "energy_source",
    "energy_integration_method",
    "nvml_total_energy_supported",
    "nvml_power_usage_semantics",
    "nvml_field_power_instant_supported",
    "nvml_field_power_average_supported",
    "power_before_mw",
    "power_after_mw",
    "power_sample_count",
    "power_sample_period_ms",
}


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def normalize_profile(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def expected_semantics(row: dict[str, str], target_profile: str) -> tuple[str, str]:
    if target_profile != "auto":
        key = normalize_profile(target_profile)
        return PROFILE_POWER_SEMANTICS.get(key, ""), key
    for column in ("profile_name", "chip"):
        key = normalize_profile(row.get(column, ""))
        if key in PROFILE_POWER_SEMANTICS:
            return PROFILE_POWER_SEMANTICS[key], key
    return "", ""


def audit_row(
    row: dict[str, str],
    *,
    input_file: str,
    row_index: int,
    target_profile: str,
    require_explicit_measurement_scope: bool,
    require_exact_measurement_interval: bool = False,
    required_mode_notes_markers: dict[str, str | list[str]] | None = None,
) -> dict[str, str]:
    marker_rules = required_mode_notes_markers or {}
    required_columns = set(REQUIRED_COLUMNS)
    if require_explicit_measurement_scope:
        required_columns.add("measurement_scope")
    if require_exact_measurement_interval:
        required_columns.update(
            {
                "elapsed_s",
                "measurement_start_epoch_ms",
                "measurement_end_epoch_ms",
            }
        )
    if marker_rules:
        required_columns.update({"mode", "notes"})
    missing = sorted(col for col in required_columns if col not in row)
    reasons: list[str] = [f"missing_column:{col}" for col in missing]
    notes: list[str] = []

    mode = row.get("mode", "")
    required_markers = marker_rules.get(mode, [])
    if isinstance(required_markers, str):
        required_markers = [required_markers]
    for required_marker in required_markers:
        if required_marker and required_marker not in row.get("notes", ""):
            reasons.append(f"missing_mode_notes_marker:{mode}:{required_marker}")

    expected, expected_profile = expected_semantics(row, target_profile)
    actual_semantics = row.get("nvml_power_usage_semantics", "")
    if not expected:
        reasons.append("unknown_expected_power_semantics")
    elif not actual_semantics:
        reasons.append("missing_power_semantics")
    elif actual_semantics != expected:
        reasons.append(f"power_semantics_not_{expected}")

    source = row.get("energy_source", "")
    integration = row.get("energy_integration_method", "")
    total_supported = truthy(row.get("nvml_total_energy_supported", ""))
    power_sample_count = row.get("power_sample_count", "")

    fallback = (
        source == "legacy_get_power_usage_integral"
        or integration == "endpoint_power_trapezoid"
    )

    if source == "nvml_total_energy":
        inferred_measurement_scope = "gpu_device_total_energy_counter"
        if not total_supported:
            reasons.append("source_total_energy_but_support_false")
        if integration != "total_energy_mj_delta":
            reasons.append("source_total_energy_but_integration_mismatch")
    elif fallback:
        inferred_measurement_scope = "gpu_device_power_usage_fallback"
        notes.append("power_usage_fallback_provisional")
        if total_supported:
            reasons.append("total_counter_supported_but_fallback_used")
        if actual_semantics == "one_sec_average":
            notes.append("one_second_average_endpoint_fallback_high_risk")
        if power_sample_count in {"", "0", "1", "2"}:
            notes.append("endpoint_two_sample_or_missing_power_integral")
    else:
        inferred_measurement_scope = "unknown"
        reasons.append("unknown_energy_source_or_integration")

    raw_measurement_scope = row.get("measurement_scope", "")
    measurement_scope = raw_measurement_scope or inferred_measurement_scope
    if require_explicit_measurement_scope and "measurement_scope" not in row:
        reasons.append("missing_explicit_measurement_scope")
        notes.append("raw_csv_schema_missing_measurement_scope_rebuild_harness")
    elif require_explicit_measurement_scope and not raw_measurement_scope:
        reasons.append("missing_explicit_measurement_scope")
    if raw_measurement_scope and raw_measurement_scope != inferred_measurement_scope:
        reasons.append("measurement_scope_energy_source_mismatch")
        notes.append(f"inferred_measurement_scope={inferred_measurement_scope}")

    if require_exact_measurement_interval:
        try:
            elapsed_s = float(row.get("elapsed_s", ""))
            measurement_start_ms = float(row.get("measurement_start_epoch_ms", ""))
            measurement_end_ms = float(row.get("measurement_end_epoch_ms", ""))
        except (TypeError, ValueError):
            elapsed_s = measurement_start_ms = measurement_end_ms = math.nan
        if not math.isfinite(elapsed_s) or elapsed_s <= 0.0:
            reasons.append("invalid_elapsed_s_for_measurement_interval")
        if not math.isfinite(measurement_start_ms) or measurement_start_ms <= 0.0:
            reasons.append("invalid_measurement_start_epoch_ms")
        if (
            not math.isfinite(measurement_end_ms)
            or not math.isfinite(measurement_start_ms)
            or measurement_end_ms < measurement_start_ms
        ):
            reasons.append("invalid_measurement_end_epoch_ms")
        if (
            math.isfinite(elapsed_s)
            and elapsed_s > 0.0
            and math.isfinite(measurement_start_ms)
            and math.isfinite(measurement_end_ms)
            and measurement_end_ms >= measurement_start_ms
        ):
            interval_ms = measurement_end_ms - measurement_start_ms
            expected_ms = elapsed_s * 1000.0
            if abs(interval_ms - expected_ms) > max(5.0, expected_ms * 0.01):
                reasons.append("measurement_interval_elapsed_mismatch")

    if source != "nvml_total_energy":
        notes.append("not_final_coefficient_numerator")
    if integration != "total_energy_mj_delta":
        notes.append("not_total_energy_delta")

    if reasons:
        status = "reject"
    elif fallback:
        status = "provisional"
    else:
        status = "final_candidate"

    return {
        "input_file": input_file,
        "row_index": str(row_index),
        "profile_name": row.get("profile_name", ""),
        "chip": row.get("chip", ""),
        "expected_profile": expected_profile,
        "expected_power_semantics": expected,
        "actual_power_semantics": actual_semantics,
        "energy_source": source,
        "energy_integration_method": integration,
        "raw_measurement_scope": raw_measurement_scope,
        "measurement_scope": measurement_scope,
        "nvml_total_energy_supported": row.get("nvml_total_energy_supported", ""),
        "nvml_field_power_instant_supported": row.get(
            "nvml_field_power_instant_supported", ""
        ),
        "nvml_field_power_average_supported": row.get(
            "nvml_field_power_average_supported", ""
        ),
        "power_before_mw": row.get("power_before_mw", ""),
        "power_after_mw": row.get("power_after_mw", ""),
        "power_sample_count": power_sample_count,
        "power_sample_period_ms": row.get("power_sample_period_ms", ""),
        "measurement_start_epoch_ms": row.get("measurement_start_epoch_ms", ""),
        "measurement_end_epoch_ms": row.get("measurement_end_epoch_ms", ""),
        "status": status,
        "reasons": ";".join(reasons),
        "notes": ";".join(notes),
    }


def read_rows(
    paths: Iterable[str],
    target_profile: str,
    *,
    require_explicit_measurement_scope: bool,
    require_exact_measurement_interval: bool = False,
    required_mode_notes_markers: dict[str, str | list[str]] | None = None,
) -> list[dict[str, str]]:
    audited: list[dict[str, str]] = []
    for path_str in paths:
        path = Path(path_str)
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=2):
                audited.append(
                    audit_row(
                        row,
                        input_file=str(path),
                        row_index=idx,
                        target_profile=target_profile,
                        require_explicit_measurement_scope=require_explicit_measurement_scope,
                        require_exact_measurement_interval=require_exact_measurement_interval,
                        required_mode_notes_markers=required_mode_notes_markers,
                    )
                )
    return audited


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "input_file",
        "row_index",
        "profile_name",
        "chip",
        "expected_profile",
        "expected_power_semantics",
        "actual_power_semantics",
        "energy_source",
        "energy_integration_method",
        "raw_measurement_scope",
        "measurement_scope",
        "nvml_total_energy_supported",
        "nvml_field_power_instant_supported",
        "nvml_field_power_average_supported",
        "power_before_mw",
        "power_after_mw",
        "power_sample_count",
        "power_sample_period_ms",
        "measurement_start_epoch_ms",
        "measurement_end_epoch_ms",
        "status",
        "reasons",
        "notes",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def count_by(rows: list[dict[str, str]], key: str) -> Counter[str]:
    return Counter(row.get(key, "") for row in rows)


def write_count_table(f, title: str, counts: Counter[str]) -> None:
    f.write(f"## {title}\n\n")
    f.write("| value | rows |\n|---|---:|\n")
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        label = value if value else "(empty)"
        f.write(f"| `{label}` | {count} |\n")
    f.write("\n")


def write_markdown(path: str, rows: list[dict[str, str]], csv_path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    by_file: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    note_counts: Counter[str] = Counter()
    for row in rows:
        by_file[row["input_file"]][row["status"]] += 1
        for reason in row["reasons"].split(";"):
            if reason:
                reason_counts[reason] += 1
        for note in row["notes"].split(";"):
            if note:
                note_counts[note] += 1

    with out.open("w") as f:
        f.write("# Power API Measurement Audit\n\n")
        f.write(
            "This report audits raw energy CSV rows against "
            "`docs/platforms/power_measurement_api_matrix_ko.md`. It checks "
            "whether the energy numerator is suitable for final component "
            "coefficients before NCU path acceptance and matched-control "
            "analysis.\n\n"
        )
        f.write(f"- detail CSV: `{csv_path}`\n")
        f.write(f"- total rows: {len(rows)}\n\n")
        write_count_table(f, "Status Counts", count_by(rows, "status"))
        write_count_table(f, "Energy Source Counts", count_by(rows, "energy_source"))
        write_count_table(
            f, "Integration Method Counts", count_by(rows, "energy_integration_method")
        )
        write_count_table(f, "Measurement Scope Counts", count_by(rows, "measurement_scope"))
        write_count_table(
            f, "Power Semantics Counts", count_by(rows, "actual_power_semantics")
        )
        f.write("## File Counts\n\n")
        f.write("| file | final_candidate | provisional | reject |\n")
        f.write("|---|---:|---:|---:|\n")
        for file_name, counts in sorted(by_file.items()):
            f.write(
                f"| `{file_name}` | {counts['final_candidate']} | "
                f"{counts['provisional']} | {counts['reject']} |\n"
            )
        f.write("\n")
        if reason_counts:
            write_count_table(f, "Reject Reasons", reason_counts)
        if note_counts:
            write_count_table(f, "Notes", note_counts)
        f.write("## Interpretation\n\n")
        f.write(
            "- `final_candidate` means the row uses `nvml_total_energy` with "
            "`total_energy_mj_delta` and the expected `GetPowerUsage` semantics "
            "metadata for the profile. When "
            "`--require-explicit-measurement-scope` is used, the raw CSV must "
            "also contain `measurement_scope=gpu_device_total_energy_counter`; "
            "old rows that only allow inferred scope are rejected for final "
            "analysis.\n"
        )
        f.write(
            "- When `--require-exact-measurement-interval` is used, the raw row "
            "must contain positive timed-kernel start/end epoch fields consistent "
            "with `elapsed_s`. Legacy run-id timing inference is diagnostic only.\n"
        )
        f.write(
            "- `provisional` means the row uses a fallback power integral. It "
            "should not be mixed into final pJ/FLOP or pJ/bit tables.\n"
        )
        f.write(
            "- `reject` means the row contradicts the expected power API matrix "
            "or lacks required metadata.\n"
        )
        f.write(
            "- When `--require-mode-notes-marker MODE=MARKER` is supplied, rows "
            "for that mode must carry the exact implementation revision marker "
            "in the raw `notes` column. This rejects stale binaries even when "
            "their CSV schema is otherwise current.\n"
        )
        f.write(
            "- If every row is rejected with `missing_column:measurement_scope` "
            "or `raw_csv_schema_missing_measurement_scope_rebuild_harness`, the "
            "raw CSV was produced by an old benchmark binary or appended to an "
            "old schema. Pull the current source, rebuild the target-profile "
            "binary, move the stale raw CSVs aside, and rerun the energy sweep.\n"
        )
        f.write(
            "- This audit does not prove L1/L2/DRAM path correctness. NCU path "
            "acceptance is still required after this step.\n"
        )
        f.write(
            "- The measurement scope here is GPU/device telemetry from the raw "
            "harness CSV. Hopper module power and GPU memory power readings are "
            "preflight metadata only and must not be mixed into final component "
            "coefficients.\n"
        )


def selftest_row(**overrides: str) -> dict[str, str]:
    row = {
        "mode": "clocked_empty",
        "notes": "",
        "profile_name": "a100",
        "chip": "ga100",
        "energy_source": "nvml_total_energy",
        "energy_integration_method": "total_energy_mj_delta",
        "measurement_scope": "gpu_device_total_energy_counter",
        "nvml_total_energy_supported": "true",
        "nvml_power_usage_semantics": "instant",
        "nvml_field_power_instant_supported": "true",
        "nvml_field_power_average_supported": "false",
        "power_before_mw": "250000",
        "power_after_mw": "255000",
        "power_sample_count": "0",
        "power_sample_period_ms": "0",
        "elapsed_s": "10",
        "measurement_start_epoch_ms": "100000",
        "measurement_end_epoch_ms": "110000",
    }
    row.update(overrides)
    return row


def assert_selftest(condition: bool, name: str, detail: str = "") -> None:
    if not condition:
        suffix = f": {detail}" if detail else ""
        raise AssertionError(f"{name} failed{suffix}")


def run_self_test() -> None:
    good = audit_row(
        selftest_row(),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        good["status"] == "final_candidate",
        "good_a100_total_energy",
        good["reasons"],
    )

    good_exact_interval = audit_row(
        selftest_row(),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
        require_exact_measurement_interval=True,
    )
    assert_selftest(
        good_exact_interval["status"] == "final_candidate",
        "good_exact_measurement_interval",
        good_exact_interval["reasons"],
    )

    missing_exact_interval = selftest_row()
    missing_exact_interval.pop("measurement_start_epoch_ms")
    missing_exact_interval_result = audit_row(
        missing_exact_interval,
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
        require_exact_measurement_interval=True,
    )
    assert_selftest(
        missing_exact_interval_result["status"] == "reject"
        and "missing_column:measurement_start_epoch_ms"
        in missing_exact_interval_result["reasons"],
        "missing_exact_measurement_interval",
        missing_exact_interval_result["reasons"],
    )

    bad_semantics = audit_row(
        selftest_row(nvml_power_usage_semantics="one_sec_average"),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        bad_semantics["status"] == "reject"
        and "power_semantics_not_instant" in bad_semantics["reasons"],
        "bad_a100_power_semantics",
        bad_semantics["reasons"],
    )

    missing_scope = selftest_row()
    missing_scope.pop("measurement_scope")
    missing_scope_result = audit_row(
        missing_scope,
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        missing_scope_result["status"] == "reject"
        and "missing_column:measurement_scope" in missing_scope_result["reasons"]
        and "missing_explicit_measurement_scope" in missing_scope_result["reasons"],
        "missing_explicit_measurement_scope",
        missing_scope_result["reasons"],
    )

    fallback = audit_row(
        selftest_row(
            energy_source="legacy_get_power_usage_integral",
            energy_integration_method="endpoint_power_trapezoid",
            measurement_scope="gpu_device_power_usage_fallback",
            nvml_total_energy_supported="false",
            power_sample_count="2",
            power_sample_period_ms="10000",
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        fallback["status"] == "provisional"
        and "power_usage_fallback_provisional" in fallback["notes"],
        "fallback_is_provisional",
        f"{fallback['reasons']} / {fallback['notes']}",
    )

    fallback_despite_total = audit_row(
        selftest_row(
            energy_source="legacy_get_power_usage_integral",
            energy_integration_method="endpoint_power_trapezoid",
            measurement_scope="gpu_device_power_usage_fallback",
            nvml_total_energy_supported="true",
            power_sample_count="2",
            power_sample_period_ms="10000",
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        fallback_despite_total["status"] == "reject"
        and "total_counter_supported_but_fallback_used"
        in fallback_despite_total["reasons"],
        "fallback_rejected_when_total_counter_supported",
        fallback_despite_total["reasons"],
    )

    module_scope = audit_row(
        selftest_row(
            profile_name="h100",
            chip="gh100",
            measurement_scope="module_power",
            nvml_power_usage_semantics="one_sec_average",
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="h100",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        module_scope["status"] == "reject"
        and "measurement_scope_energy_source_mismatch" in module_scope["reasons"],
        "h100_module_scope_rejected",
        module_scope["reasons"],
    )

    auto_profile = audit_row(
        selftest_row(
            profile_name="rtx3090",
            chip="ga102",
            nvml_power_usage_semantics="one_sec_average",
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="auto",
        require_explicit_measurement_scope=True,
    )
    assert_selftest(
        auto_profile["status"] == "final_candidate"
        and auto_profile["expected_power_semantics"] == "one_sec_average",
        "auto_profile_semantics",
        f"{auto_profile['status']} / {auto_profile['expected_power_semantics']}",
    )

    marker_rules = {
        "reg_operand_only": (
            "tensor_pair_kernel_revision="
            "matched_runtime_clock_observed_control_fixed_rf_v6"
        ),
        "l2_cg_load_only": "global_warmup_policy=ld_global_cg",
        "dram_cg_load_only": [
            "global_warmup_policy=ld_global_cg",
            "input_data_pattern=splitmix64_uniform_fp16_v1",
        ],
    }
    good_marker = audit_row(
        selftest_row(
            mode="reg_operand_only",
            notes=(
                "tensor_pair_kernel_revision="
                "matched_runtime_clock_observed_control_fixed_rf_v6;other=value"
            ),
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
        required_mode_notes_markers=marker_rules,
    )
    assert_selftest(
        good_marker["status"] == "final_candidate",
        "current_tensor_revision_marker",
        good_marker["reasons"],
    )

    stale_marker = audit_row(
        selftest_row(mode="l2_cg_load_only", notes="global_warmup_policy=default_cached"),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
        required_mode_notes_markers=marker_rules,
    )
    assert_selftest(
        stale_marker["status"] == "reject"
        and "missing_mode_notes_marker:l2_cg_load_only:global_warmup_policy=ld_global_cg"
        in stale_marker["reasons"],
        "stale_cg_warmup_revision_marker",
        stale_marker["reasons"],
    )

    stale_input_pattern = audit_row(
        selftest_row(
            mode="dram_cg_load_only",
            notes="global_warmup_policy=ld_global_cg;input_data_pattern=legacy32;",
        ),
        input_file="selftest.csv",
        row_index=2,
        target_profile="a100",
        require_explicit_measurement_scope=True,
        required_mode_notes_markers=marker_rules,
    )
    assert_selftest(
        stale_input_pattern["status"] == "reject"
        and "missing_mode_notes_marker:dram_cg_load_only:input_data_pattern=splitmix64_uniform_fp16_v1"
        in stale_input_pattern["reasons"],
        "stale_external_memory_input_pattern_marker",
        stale_input_pattern["reasons"],
    )

    print("power API measurement audit self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_paths", nargs="*")
    parser.add_argument(
        "--target-profile",
        default="auto",
        help="Use a fixed profile expectation instead of per-row profile/chip.",
    )
    parser.add_argument(
        "--out-csv",
        default="results/summary/power_api_measurement_audit.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/power_api_measurement_audit.md",
    )
    parser.add_argument(
        "--fail-on-reject",
        action="store_true",
        help="Exit nonzero if any row is rejected.",
    )
    parser.add_argument(
        "--fail-on-provisional",
        action="store_true",
        help="Exit nonzero if any row is provisional.",
    )
    parser.add_argument(
        "--require-explicit-measurement-scope",
        action="store_true",
        help=(
            "Reject rows that do not explicitly contain the measurement_scope "
            "CSV column/value. Use this for new finalplan runs."
        ),
    )
    parser.add_argument(
        "--require-exact-measurement-interval",
        action="store_true",
        help=(
            "Reject rows without positive timed-kernel start/end epoch fields "
            "consistent with elapsed_s. Use this for new finalplan runs."
        ),
    )
    parser.add_argument(
        "--require-mode-notes-marker",
        action="append",
        default=[],
        metavar="MODE=MARKER",
        help=(
            "Require rows for MODE to contain MARKER in the raw notes column. "
            "Repeat this option for multiple implementation revisions."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in power API policy regression checks and exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    if not args.csv_paths:
        parser.error("csv_paths are required unless --self-test is used")

    required_mode_notes_markers: dict[str, list[str]] = {}
    for value in args.require_mode_notes_marker:
        mode, separator, marker = value.partition("=")
        if not separator or not mode or not marker:
            parser.error(
                "--require-mode-notes-marker must use non-empty MODE=MARKER"
            )
        markers = required_mode_notes_markers.setdefault(mode, [])
        if marker not in markers:
            markers.append(marker)

    rows = read_rows(
        args.csv_paths,
        args.target_profile,
        require_explicit_measurement_scope=args.require_explicit_measurement_scope,
        require_exact_measurement_interval=args.require_exact_measurement_interval,
        required_mode_notes_markers=required_mode_notes_markers,
    )
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args.out_csv)

    status_counts = count_by(rows, "status")
    print(
        "power audit rows="
        f"{len(rows)} final_candidate={status_counts['final_candidate']} "
        f"provisional={status_counts['provisional']} reject={status_counts['reject']}"
    )
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")

    if args.fail_on_reject and status_counts["reject"]:
        return 2
    if args.fail_on_provisional and status_counts["provisional"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
