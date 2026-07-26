#!/usr/bin/env python3
"""Build the canonical technical report artifact for the targeted EX2 check.

This is intentionally a report-only step.  It consumes the fail-closed
CTA=48/S=1024 confirmation outputs, independently checks their primary
session-level aggregates, and writes a bounded canonical artifact plus a
pre-packaging QA note.  It never launches a GPU workload or profiles energy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


TITLE = "RTX 3090 Softmax EX2 CTA=48/S=1024 targeted confirmation"
TAG = "targeted_g48s1024_confirm_v1_20260725"
PREFIX = f"rtx3090_softmax_ex2_targeted_confirmation_{TAG}"
IMPLEMENTATIONS = ("fp32", "ptx_f16", "ptx_f16x2")
IMPLEMENTATION_LABELS = {
    "fp32": "FP32 __expf",
    "ptx_f16": "scalar FP16 PTX",
    "ptx_f16x2": "packed FP16x2 PTX",
}


class EvidenceError(RuntimeError):
    """Raised when a report input is incomplete or internally inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def read_csv(path: Path, label: str) -> list[dict[str, str]]:
    require(path.is_file(), f"{label} is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, f"{label} has no header")
        require(
            len(reader.fieldnames) == len(set(reader.fieldnames)),
            f"{label} has duplicate fields",
        )
        rows = list(reader)
    require(bool(rows), f"{label} has no rows")
    return rows


def require_fields(rows: list[dict[str, str]], fields: Iterable[str], label: str) -> None:
    missing = set(fields) - set(rows[0])
    require(not missing, f"{label} is missing fields: {sorted(missing)}")


def number(row: Mapping[str, Any], field: str, label: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError(f"{label}.{field} is not numeric: {row.get(field)!r}") from error
    require(math.isfinite(value), f"{label}.{field} is not finite")
    return value


def integer(row: Mapping[str, Any], field: str, label: str) -> int:
    raw = row.get(field)
    try:
        value = int(str(raw))
    except (TypeError, ValueError) as error:
        raise EvidenceError(f"{label}.{field} is not an integer: {raw!r}") from error
    return value


def near(actual: float, expected: float, label: str, tolerance: float = 1.0e-9) -> None:
    require(
        abs(actual - expected) <= tolerance * max(1.0, abs(actual), abs(expected)),
        f"{label} mismatch: {actual} != {expected}",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as error:
        raise EvidenceError(f"source must be a repository-local file: {path}") from error


def display_number(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def csv_source(
    source_id: str,
    label: str,
    path: str,
    description: str,
    metric_definitions: list[str],
    filters: list[str] | None = None,
    order_by: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {
        "engine": "duckdb",
        "language": "sql",
        "sql": f"SELECT * FROM read_csv_auto('{path}');",
        "description": description,
        "tables_used": [path],
        "metric_definitions": metric_definitions,
    }
    if filters:
        query["filters"] = filters
    if order_by:
        query["order_by"] = order_by
    return {"id": source_id, "label": label, "path": path, "query": query}


def file_source(source_id: str, label: str, path: str, description: str) -> dict[str, Any]:
    return {"id": source_id, "label": label, "path": path, "query": {"description": description}}


def chart(
    *,
    chart_id: str,
    title: str,
    subtitle: str,
    question: str,
    rationale: str,
    dataset: str,
    source_id: str,
    chart_type: str,
    x_field: str,
    x_type: str,
    x_label: str,
    y_field: str,
    y_label: str,
    y_unit: str,
    tooltip: list[dict[str, Any]],
    color_field: str | None = None,
    color_label: str | None = None,
    zero_reference: bool = False,
    grain: str = "one record",
) -> dict[str, Any]:
    encodings: dict[str, Any] = {
        "x": {"field": x_field, "type": x_type, "label": x_label},
        "y": {"field": y_field, "type": "quantitative", "label": y_label, "unit": y_unit, "format": "number"},
        "tooltip": tooltip,
    }
    if color_field:
        encodings["color"] = {"field": color_field, "type": "nominal", "label": color_label or color_field}
    output: dict[str, Any] = {
        "id": chart_id,
        "title": title,
        "subtitle": subtitle,
        "type": chart_type,
        "intent": "relationship" if chart_type == "scatter" else "comparison",
        "question": question,
        "rationale": rationale,
        "comparisonContext": {
            "baseline": "0 incremental pJ/element" if zero_reference else "historical target cells and fresh confirmation sessions",
            "denominator": "one additional logical exponent result per input element",
            "grain": grain,
            "unit": y_unit,
        },
        "dataset": dataset,
        "sourceId": source_id,
        "encodings": encodings,
        "palette": {"kind": "categorical", "name": "softmax-ex2-targeted"},
        "labels": {"values": "auto" if chart_type == "bar" else "none"},
        "layout": "full",
        "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
    }
    if color_field:
        output["legend"] = {"position": "bottom"}
    if zero_reference:
        output["referenceLines"] = [{"axis": "y", "value": 0, "label": "0", "color": "neutral", "lineStyle": "solid"}]
    return output


def normalized_bool(value: str) -> bool:
    require(value in {"true", "false"}, f"expected true/false but got {value!r}")
    return value == "true"


def validate_inputs(root: Path) -> tuple[dict[str, Path], dict[str, list[dict[str, str]]], dict[str, Any]]:
    summary = root / "results/summary"
    paths: dict[str, Path] = {
        name: summary / f"{PREFIX}_{suffix}.csv"
        for name, suffix in {
            "program": "program",
            "plan": "plan",
            "state": "state",
            "cells": "session_cells",
            "matched": "matched_blocks",
            "impl": "implementation_summary",
            "contrasts": "within_session_contrasts",
            "contrast_summary": "contrast_summary",
            "diagnostics": "diagnostics",
            "numerics": "numerical_validation",
            "sass": "sass_audit",
            "ncu": "ncu_audit",
            "historical": "historical_context",
            "historical_scalar": "historical_scalar_blocks",
        }.items()
    }
    paths["analysis"] = root / "docs/results" / f"{PREFIX}_analysis_ko.md"
    paths["kernel"] = root / "src/softmax_kernels.cu"
    paths["runner"] = root / "scripts/run_softmax_ex2_targeted_confirmation.py"
    paths["analyzer"] = root / "scripts/analyze_softmax_ex2_targeted_confirmation.py"
    rows = {name: read_csv(path, name) for name, path in paths.items() if path.suffix == ".csv"}

    require(len(rows["program"]) == 1, "program must contain exactly one row")
    program = rows["program"][0]
    require(program["target_tag"] == TAG, "program target tag drifted")
    require(program["coordinate"] == "CTA=48,S=1024", "program coordinate drifted")
    require(program["primary_metric"] == "incremental_pJ_per_element", "program primary metric drifted")
    require(program["status"] == "pass", "program status is not pass")
    require(len(rows["plan"]) == len(rows["state"]) == len(rows["cells"]) == 9, "expected exactly nine planned/state/cell rows")
    require(len(rows["matched"]) == 27, "expected 27 matched blocks")
    require(len(rows["impl"]) == 3, "expected three implementation summaries")
    require(len(rows["contrasts"]) == 9 and len(rows["contrast_summary"]) == 3, "contrast row counts drifted")
    require(len(rows["diagnostics"]) == 9, "expected nine diagnostic rows")
    require(len(rows["numerics"]) == 3 and len(rows["sass"]) == 3 and len(rows["ncu"]) == 2, "validation/audit row counts drifted")
    require(len(rows["historical"]) == 6 and len(rows["historical_scalar"]) == 6, "historical context row counts drifted")

    cell_required = {
        "session_id", "session_index", "implementation_position", "implementation", "grid_blocks", "softmax_cols",
        "incremental_pJ_per_element", "incremental_pJ_per_logical_scalar_exponent_result", "quality_status",
        "logical_added_results_equals_elements", "results_per_ptx_instruction", "raw_source", "manifest_source",
    }
    require_fields(rows["cells"], cell_required, "session_cells")
    by_session: dict[str, list[dict[str, str]]] = {}
    by_impl: dict[str, list[dict[str, str]]] = {value: [] for value in IMPLEMENTATIONS}
    for index, row in enumerate(rows["cells"], 1):
        label = f"cell[{index}]"
        require(row["implementation"] in IMPLEMENTATIONS, f"{label} implementation drifted")
        require(integer(row, "grid_blocks", label) == 48 and integer(row, "softmax_cols", label) == 1024, f"{label} coordinate drifted")
        require(row["quality_status"] == "pass", f"{label} quality failed")
        require(normalized_bool(row["logical_added_results_equals_elements"]), f"{label} denominator proof failed")
        near(number(row, "incremental_pJ_per_element", label), number(row, "incremental_pJ_per_logical_scalar_exponent_result", label), f"{label} denominator alias")
        require((root / row["raw_source"]).is_file(), f"{label} raw source is missing")
        require((root / row["manifest_source"]).is_file(), f"{label} manifest source is missing")
        by_session.setdefault(row["session_id"], []).append(row)
        by_impl[row["implementation"]].append(row)
    require(len(by_session) == 3, "expected three fresh sessions")
    for session, session_rows in by_session.items():
        require(len(session_rows) == 3, f"{session} does not contain three implementations")
        require(set(row["implementation"] for row in session_rows) == set(IMPLEMENTATIONS), f"{session} implementation set drifted")
        require(sorted(integer(row, "implementation_position", session) for row in session_rows) == [1, 2, 3], f"{session} position balance drifted")
    for impl, impl_rows in by_impl.items():
        require(len(impl_rows) == 3, f"{impl} does not have three fresh sessions")
        require(sorted(integer(row, "implementation_position", impl) for row in impl_rows) == [1, 2, 3], f"{impl} does not occupy each position once")

    require(all(row.get("status") == "complete" and row.get("quality_status") == "pass" for row in rows["state"]), "state contains a non-pass cell")
    require(len({row.get("cell_id") for row in rows["plan"]}) == 9, "plan cell IDs are not unique")
    require(all(row.get("quality_status") == "pass" for row in rows["matched"]), "matched block quality failed")

    require_fields(rows["impl"], {"implementation", "session_count", "mean_incremental_pJ_per_element", "sample_sd_incremental_pJ_per_element"}, "implementation_summary")
    summary_by_impl = {row["implementation"]: row for row in rows["impl"]}
    require(set(summary_by_impl) == set(IMPLEMENTATIONS), "implementation summary set drifted")
    for impl, impl_rows in by_impl.items():
        values = [number(row, "incremental_pJ_per_element", impl) for row in impl_rows]
        summary_row = summary_by_impl[impl]
        require(integer(summary_row, "session_count", impl) == 3, f"{impl} summary session count drifted")
        near(statistics.fmean(values), number(summary_row, "mean_incremental_pJ_per_element", impl), f"{impl} summary mean")
        near(statistics.stdev(values), number(summary_row, "sample_sd_incremental_pJ_per_element", impl), f"{impl} summary SD")

    require(all(row.get("verdict") == "pass" for row in rows["numerics"]), "numerical validation failed")
    require(all(row.get("verdict") == "pass" for row in rows["sass"]), "SASS audit failed")
    for row in rows["ncu"]:
        label = f"ncu[{row['implementation']}]"
        require(row["verdict"] == "pass", f"{label} failed")
        require(integer(row, "observed_xu_delta", label) == integer(row, "expected_xu_delta", label) == 49_152_000, f"{label} delta mismatch")
        require(row["energy_usable"] == "false", f"{label} must not supply energy")
    packed = next(row for row in rows["sass"] if row["implementation"] == "ptx_f16x2")
    scalar = next(row for row in rows["sass"] if row["implementation"] == "ptx_f16")
    require(integer(packed, "ptx_f16x2_static_count", "packed SASS") == 4, "packed PTX count drifted")
    require(integer(packed, "sass_mufu_ex2_f16_static_count", "packed SASS") == 8, "packed SASS count drifted")
    require(integer(scalar, "ptx_f16_static_count", "scalar SASS") == 8, "scalar PTX count drifted")
    require(integer(scalar, "sass_mufu_ex2_f16_static_count", "scalar SASS") == 8, "scalar SASS count drifted")

    contrast_by_name = {row["contrast"]: row for row in rows["contrast_summary"]}
    packed_contrast = contrast_by_name["ptx_f16x2_minus_ptx_f16"]
    require(number(packed_contrast, "diagnostic_t95_low_incremental_pJ_per_element", "packed contrast") < 0, "packed contrast lower interval must include zero")
    require(number(packed_contrast, "diagnostic_t95_high_incremental_pJ_per_element", "packed contrast") > 0, "packed contrast upper interval must include zero")
    details = {
        "program": program,
        "summary_by_impl": summary_by_impl,
        "contrast_by_name": contrast_by_name,
        "by_impl": by_impl,
        "input_hashes": {name: sha256(path) for name, path in paths.items() if path.is_file()},
    }
    return paths, rows, details


def datasets(rows: dict[str, list[dict[str, str]]], details: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    impl_summary: list[dict[str, Any]] = []
    for row in rows["impl"]:
        impl = row["implementation"]
        impl_summary.append({
            "implementation": impl,
            "implementation_label": IMPLEMENTATION_LABELS[impl],
            "mean_incremental_pj_per_element": number(row, "mean_incremental_pJ_per_element", impl),
            "median_incremental_pj_per_element": number(row, "median_incremental_pJ_per_element", impl),
            "sample_sd": number(row, "sample_sd_incremental_pJ_per_element", impl),
            "diagnostic_t95_low": number(row, "diagnostic_t95_low_incremental_pJ_per_element", impl),
            "diagnostic_t95_high": number(row, "diagnostic_t95_high_incremental_pJ_per_element", impl),
            "positive_session_effects": integer(row, "positive_session_effect_count", impl),
            "positive_cell_verdicts": integer(row, "positive_cell_verdict_count", impl),
            "session_count": integer(row, "session_count", impl),
        })
    session_effects: list[dict[str, Any]] = []
    for row in rows["cells"]:
        impl = row["implementation"]
        session_effects.append({
            "session_label": row["session_id"],
            "session_index": integer(row, "session_index", impl),
            "implementation_position": integer(row, "implementation_position", impl),
            "session_order": row["session_order"],
            "implementation": impl,
            "implementation_label": IMPLEMENTATION_LABELS[impl],
            "effect_incremental_pj_per_element": number(row, "incremental_pJ_per_element", impl),
            "forward_incremental_pj_per_element": number(row, "forward_incremental_pJ_per_element", impl),
            "reverse_incremental_pj_per_element": number(row, "reverse_incremental_pJ_per_element", impl),
            "temperature_min_c": number(row, "temperature_min_C", impl),
            "temperature_max_c": number(row, "temperature_max_C", impl),
            "temperature_mid_c": (number(row, "temperature_min_C", impl) + number(row, "temperature_max_C", impl)) / 2.0,
            "preheat_actual_s": number(row, "preheat_actual_s", impl),
            "trace_r2": number(row, "trace_fit_r2_min", impl),
            "cell_verdict": row["cell_verdict"],
        })
    historical_and_fresh: list[dict[str, Any]] = []
    history_label = {"matrix60_original": "historical original", "matrix60_reproduction": "historical reproduction"}
    for row in rows["historical"]:
        impl = row["implementation"]
        historical_and_fresh.append({
            "implementation": impl,
            "implementation_label": IMPLEMENTATION_LABELS[impl],
            "series": history_label[row["session_label"]],
            "effect_incremental_pj_per_element": number(row, "incremental_pJ_per_element", impl),
            "scope": "historical_context_not_primary_pool",
        })
    for row in impl_summary:
        historical_and_fresh.append({
            "implementation": row["implementation"],
            "implementation_label": row["implementation_label"],
            "series": "fresh 3-session mean",
            "effect_incremental_pj_per_element": row["mean_incremental_pj_per_element"],
            "scope": "primary_fresh_session_aggregate",
        })
    contrast_rows: list[dict[str, Any]] = []
    contrast_labels = {
        "fp32_minus_ptx_f16": "FP32 − scalar FP16",
        "fp32_minus_ptx_f16x2": "FP32 − packed FP16x2",
        "ptx_f16x2_minus_ptx_f16": "packed FP16x2 − scalar FP16",
    }
    for row in rows["contrasts"]:
        contrast_rows.append({
            "session_index": integer(row, "session_index", row["contrast"]),
            "session_label": row["session_id"],
            "contrast": row["contrast"],
            "contrast_label": contrast_labels[row["contrast"]],
            "effect_incremental_pj_per_element": number(row, "contrast_incremental_pJ_per_element", row["contrast"]),
            "left_position": integer(row, "left_position", row["contrast"]),
            "right_position": integer(row, "right_position", row["contrast"]),
        })
    lowering: list[dict[str, Any]] = []
    for row in rows["sass"]:
        impl = row["implementation"]
        if impl == "fp32":
            continue
        fields = (("PTX EX2 count", "ptx_f16_static_count" if impl == "ptx_f16" else "ptx_f16x2_static_count"), ("final SASS MUFU.EX2.F16 count", "sass_mufu_ex2_f16_static_count"))
        for stage, field in fields:
            lowering.append({"implementation": impl, "implementation_label": IMPLEMENTATION_LABELS[impl], "stage": stage, "static_instruction_count": integer(row, field, impl)})
    native_validation: list[dict[str, Any]] = []
    for row in rows["numerics"]:
        impl = row["implementation"]
        native_validation.append({
            "implementation": impl,
            "implementation_label": IMPLEMENTATION_LABELS[impl],
            "max_abs_error": number(row, "max_abs_error", impl),
            "max_row_sum_error": number(row, "max_row_sum_error", impl),
            "bit_identical": row["control_treatment_bit_identical"],
            "packed_scalar_bit_mismatch_count": row["packed_scalar_bit_mismatch_count"],
            "native_verdict": row["verdict"],
        })
    audit_summary = [
        {"check": "cell execution", "coverage": "9/9", "result": "pass", "meaning": "raw, trace, manifest, plan/state evidence present"},
        {"check": "session position balance", "coverage": "3 sessions", "result": "pass", "meaning": "each implementation occupies position 1, 2, and 3 once"},
        {"check": "native numerical validation", "coverage": "FP16 scalar + packed", "result": "pass", "meaning": "bit identity; native all-encoding mismatch count 0"},
        {"check": "static SASS", "coverage": "S=1024 / CTA=48 specialization", "result": "pass", "meaning": "packed f16x2 PTX lowers to 8 scalar F16 MUFU instructions"},
        {"check": "dynamic NCU path", "coverage": "two native paths", "result": "pass (energy excluded)", "meaning": "observed and expected XU delta both 49,152,000"},
    ]
    return {
        "implementation_summary": impl_summary,
        "fresh_session_effects": session_effects,
        "historical_and_fresh": historical_and_fresh,
        "within_session_contrasts": contrast_rows,
        "static_lowering": lowering,
        "native_validation": native_validation,
        "audit_summary": audit_summary,
    }


def sources(paths: dict[str, Path], root: Path) -> list[dict[str, Any]]:
    relative = {name: repo_relative(path, root) for name, path in paths.items()}
    return [
        csv_source("program", "Targeted confirmation program", relative["program"], "One fail-closed program row defining target coordinate, unit, frozen binary, and primary session-level unit.", ["Primary metric is treatment-control incremental board energy divided by CTA×ITER×S.", "One added logical exponent result equals one processed input element in this treatment."], ["CTA=48", "S=1024", "3 fresh sessions", "status=pass"]),
        csv_source("session_cells", "Nine fresh session-cell results", relative["cells"], "One row per fresh session and implementation, including effect, forward/reverse diagnostics, denominator proof, and operating-state fields.", ["The independent repeat is the fresh session mean across three matched orientation blocks.", "The pJ/logical-result and incremental-pJ/element fields are exact aliases for this probe only."], ["quality_status=pass", "9 rows"], "session_index, implementation_position"),
        csv_source("implementation_summary", "Fresh-session implementation summary", relative["impl"], "Three implementation summaries recomputed from three independent fresh session effects each.", ["Diagnostic t95 intervals have df=2 and are descriptive, not preregistered decision thresholds."], ["session_count=3", "all_session_quality_pass=true"]),
        csv_source("contrasts", "Within-session implementation-path contrasts", relative["contrasts"], "Three complete implementation-path contrasts in each fresh session.", ["Contrasts include operand construction, pack/unpack, compiler lowering, and scheduling; they are not pure functional-unit energy."], ["3 sessions × 3 contrasts"]),
        csv_source("contrast_summary", "Within-session contrast summary", relative["contrast_summary"], "Three descriptive summaries across the three matched fresh sessions.", ["The packed-minus-scalar interval includes zero, so no packed energy advantage is identified at n=3."], ["session_count=3"]),
        csv_source("historical", "Historical target coordinate context", relative["historical"], "The two prior 60-cell target coordinate values, retained for context and excluded from the new primary aggregate.", ["Historical values are not pooled with fresh confirmation sessions."], ["CTA=48", "S=1024", "context only"]),
        csv_source("numerics", "Exact native numerical validation", relative["numerics"], "FP64-reference, treatment/control bit identity, and native all-encoding validation results.", ["Packed/scalar mismatch count is a lane-function validation; it is not an energy result."], ["verdict=pass"]),
        csv_source("sass", "Frozen binary SASS audit", relative["sass"], "Static source PTX and final SASS opcode counts for the exact S=1024 specialization.", ["For sm86, packed f16x2 source PTX count 4 lowers to final scalar F16 MUFU count 8."], ["verdict=pass"]),
        csv_source("ncu", "Dynamic native path audit", relative["ncu"], "Exact control-treatment XU counter delta, symbol/resource/traffic equality for native paths.", ["NCU replay energy is explicitly excluded from the ATC numerator."], ["observed_xu_delta=expected_xu_delta=49152000", "energy_usable=false"]),
        file_source("analysis", "Targeted confirmation analyzer note", relative["analysis"], "Analyzer-authored concise result and evidence inventory."),
        file_source("kernel", "Softmax CUDA kernel", relative["kernel"], "Source implementation of FP32, scalar FP16, and packed FP16x2 exponent paths."),
        file_source("runner", "Targeted confirmation runner", relative["runner"], "Immutable 9-cell cyclic-order plan and execution binding."),
        file_source("analyzer", "Targeted confirmation analyzer", relative["analyzer"], "Fail-closed primary session-level aggregation and audit join."),
    ]


def tables() -> list[dict[str, Any]]:
    return [
        {
            "id": "implementation_summary_table", "title": "Fresh-session implementation summary", "subtitle": "Each row summarizes three independent fresh sessions at CTA=48, S=1024; interval is descriptive df=2.", "dataset": "implementation_summary", "sourceId": "implementation_summary", "defaultSort": {"field": "mean_incremental_pj_per_element", "direction": "desc"}, "density": "spacious", "layout": "full",
            "columns": [
                {"field": "implementation_label", "label": "Implementation"},
                {"field": "session_count", "label": "Fresh sessions", "format": "number"},
                {"field": "mean_incremental_pj_per_element", "label": "Mean ΔpJ/element", "format": "number"},
                {"field": "median_incremental_pj_per_element", "label": "Median", "format": "number"},
                {"field": "sample_sd", "label": "Session SD", "format": "number"},
                {"field": "diagnostic_t95_low", "label": "Diagnostic t95 low", "format": "number"},
                {"field": "diagnostic_t95_high", "label": "Diagnostic t95 high", "format": "number"},
                {"field": "positive_session_effects", "label": "Positive session effects", "format": "number"},
            ],
        },
        {
            "id": "fresh_session_table", "title": "Fresh session-cell effects", "subtitle": "One row is one implementation in one independently created CUDA measurement session; matched blocks are not pooled as independent repeats.", "dataset": "fresh_session_effects", "sourceId": "session_cells", "defaultSort": {"field": "session_index", "direction": "asc"}, "density": "dense", "layout": "full",
            "columns": [
                {"field": "session_index", "label": "Session", "format": "number"},
                {"field": "implementation_label", "label": "Implementation"},
                {"field": "implementation_position", "label": "Position", "format": "number"},
                {"field": "effect_incremental_pj_per_element", "label": "ΔpJ/element", "format": "number"},
                {"field": "forward_incremental_pj_per_element", "label": "Forward", "format": "number"},
                {"field": "reverse_incremental_pj_per_element", "label": "Reverse", "format": "number"},
                {"field": "temperature_min_c", "label": "Temp min °C", "format": "number"},
                {"field": "temperature_max_c", "label": "Temp max °C", "format": "number"},
                {"field": "preheat_actual_s", "label": "Preheat actual s", "format": "number"},
                {"field": "trace_r2", "label": "Min trace R²", "format": "number"},
            ],
        },
        {
            "id": "audit_table", "title": "Correctness and path-audit gates", "subtitle": "Energy conclusions use board-energy evidence only; NCU is a path/count sidecar and its replay energy is excluded.", "dataset": "audit_summary", "sourceId": "ncu", "defaultSort": {"field": "check", "direction": "asc"}, "density": "spacious", "layout": "full",
            "columns": [
                {"field": "check", "label": "Check"},
                {"field": "coverage", "label": "Coverage"},
                {"field": "result", "label": "Result"},
                {"field": "meaning", "label": "Evidence"},
            ],
        },
    ]


def blocks(details: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = details["summary_by_impl"]
    fp32 = number(summaries["fp32"], "mean_incremental_pJ_per_element", "fp32")
    scalar = number(summaries["ptx_f16"], "mean_incremental_pJ_per_element", "scalar")
    packed = number(summaries["ptx_f16x2"], "mean_incremental_pJ_per_element", "packed")
    packed_diff = details["contrast_by_name"]["ptx_f16x2_minus_ptx_f16"]
    diff = number(packed_diff, "mean_incremental_pJ_per_element", "packed diff")
    diff_low = number(packed_diff, "diagnostic_t95_low_incremental_pJ_per_element", "packed diff")
    diff_high = number(packed_diff, "diagnostic_t95_high_incremental_pJ_per_element", "packed diff")
    return [
        {"id": "title", "type": "markdown", "body": f"# {TITLE}"},
        {"id": "technical_summary", "type": "markdown", "sourceId": "implementation_summary", "body": (
            "## 기술 요약\n\n"
            f"**CTA=48, S=1024에서 fresh CUDA measurement session 3개를 cyclic implementation order로 실행한 결과, FP32는 {display_number(fp32)}, scalar FP16은 {display_number(scalar)}, packed FP16x2는 {display_number(packed)} incremental ΔpJ/element였다.** 세 구현은 모두 양의 fresh-session point estimate를 보였지만, packed−scalar contrast는 {display_number(diff)} ΔpJ/element이고 diagnostic t95가 [{display_number(diff_low)}, {display_number(diff_high)}]로 0을 포함한다. 따라서 이 데이터는 packed 우위를 식별하지 않는다.\n\n"
            "과거 60-cell 재연에서 scalar FP16이 10.994→1.632으로 움직인 값은 이번 position-balanced 3-session 평균 19.393으로 안정된 implementation 고유값으로 재현되지 않았다. 이 보고서는 추가 CTA/S sweep을 하지 않고 이 하나의 논쟁 좌표를 확인한 결과다."
        )},
        {"id": "unit_definition", "type": "markdown", "sourceId": "program", "body": (
            "## 단위: pJ/logical result와 incremental pJ/element\n\n"
            "이 probe의 treatment는 각 input element에 **추가 EX2 logical result 하나**를 정확히 넣는다. 따라서 `Nadded = CTA × ITER × S = processed elements`이고, 기존 `pJ/added logical scalar exponent result`는 수치상 `incremental ΔpJ/element`와 같다. 여기서 logical scalar는 **결과 개수 회계 단위**이지 FP32 정밀도나 physical scalar instruction이라는 뜻이 아니다. 이 값은 전체 Softmax의 absolute pJ/element도, pure MUFU energy도 아니다.\n\n"
            "packed 경로의 `pJ/PTX op`은 두 logical result를 하나의 PTX f16x2 op가 생성하므로 보조적으로 2배가 되지만, hardware-instruction energy라고 부르지 않는다."
        )},
        {"id": "implementation_definition", "type": "markdown", "sourceId": "kernel", "body": (
            "## 세 구현이 뜻하는 것\n\n"
            "세 구현은 모두 FP16 input/output와 FP32 max, sum, reduction, reciprocal, normalization을 공유한다. **다른 것은 exponent/probe 경로다.** `fp32`는 scalar FP32 `__expf`/F32 EX2 경로, `ptx_f16`은 FP32 centered-logit을 FP16으로 반올림한 scalar `ex2.approx.f16` 경로, `ptx_f16x2`는 인접 두 FP16 operand를 b32에 pack한 `ex2.approx.f16x2` PTX 경로다. 따라서 셋을 모두 “scalar FP32 연산”이라고 부르는 것은 맞지 않으며, cross-implementation 값은 순수 opcode 회로 계수가 아니라 complete implementation-path contrast다."
        )},
        {"id": "history_context_intro", "type": "markdown", "sourceId": "historical", "body": (
            "## 과거 scalar 하락은 새 session 평균으로 재현되지 않았다\n\n"
            "아래 비교는 historical two-session target values와 새 3-session mean을 함께 보되, historical rows를 primary aggregate에 합치지 않는다. 과거 scalar 재연의 낮은 값은 inverse order block의 음수 효과와 동반됐고, 이번 cyclic position balance에서는 세 scalar session mean 모두 양수였다. 이는 code defect나 temperature 단독 원인을 확정하는 증거가 아니라, 이 board-level differential 측정이 session/order state에 민감하다는 증거다."
        )},
        {"id": "history_chart", "type": "chart", "chartId": "historical_and_fresh_effects"},
        {"id": "fresh_session_intro", "type": "markdown", "sourceId": "session_cells", "body": (
            "## 새 세션의 효과는 session 단위로 읽는다\n\n"
            "각 fresh session은 세 구현을 한 번씩 포함하고 각 구현이 position 1·2·3을 정확히 한 번씩 차지하도록 cyclic order를 사용했다. 따라서 차트의 점 하나가 primary repeat 하나다. cell 내부의 3 matched block은 control/treatment order-balance 진단을 위한 것이며, 27개 block을 27개의 독립 반복으로 pool하지 않았다."
        )},
        {"id": "fresh_session_chart", "type": "chart", "chartId": "fresh_session_effects"},
        {"id": "fresh_session_table_block", "type": "table", "tableId": "fresh_session_table"},
        {"id": "contrast_intro", "type": "markdown", "sourceId": "contrasts", "body": (
            "## scalar와 packed의 차이는 아직 불확실하다\n\n"
            "동일 fresh session 안에서의 packed−scalar contrast는 세 session에서 −3.785, +4.584, +16.187 ΔpJ/element였다. 평균은 양수지만 n=3 diagnostic interval이 0을 포함한다. 따라서 packed PTX의 존재나 higher-level pair packing은 확인됐어도, 이 결과만으로 packed가 scalar보다 에너지상 개선됐다고 결론내리지 않는다."
        )},
        {"id": "contrast_chart", "type": "chart", "chartId": "within_session_contrasts"},
        {"id": "path_audit_intro", "type": "markdown", "sourceId": "sass", "body": (
            "## packed PTX는 존재하지만 sm86에서 physical two-lane MUFU는 아니다\n\n"
            "S=1024 specialization에서 scalar path는 source PTX `ex2.approx.f16` 8개와 final SASS `MUFU.EX2.F16` 8개를 보였다. packed path는 source PTX `ex2.approx.f16x2` 4개를 보였지만 final SASS `MUFU.EX2.F16`도 8개였다. 즉 packed는 **PTX 수준의 두-result representation**으로는 정상이나, 이 CUDA 13.2/sm86 frozen binary에서는 두 scalar F16 MUFU와 permutation으로 lowering된다."
        )},
        {"id": "path_audit_chart", "type": "chart", "chartId": "static_lowering"},
        {"id": "correctness_intro", "type": "markdown", "sourceId": "numerics", "body": (
            "## 수치·정적·동적 path 검증은 통과했다\n\n"
            "세 implementation의 FP64-reference Softmax error와 treatment/control output bit identity를 확인했다. native scalar와 packed는 all-encoding validation에서 mismatch 0, NaN classification failure 0을 기록했다. dynamic NCU sidecar는 두 native path 모두 observed/expected XU delta 49,152,000과 symbol/resource/traffic equality를 통과했으나, NCU replay energy는 ATC numerator에 사용하지 않았다."
        )},
        {"id": "correctness_table", "type": "table", "tableId": "audit_table"},
        {"id": "methodology", "type": "markdown", "sourceId": "program", "body": (
            "## 범위와 방법\n\n"
            "고정 조건은 RTX 3090 GPU 0, frozen binary SHA binding, CTA=48, S=1024, blocks-per-SM=2, logit scale=4, 13 s role, 6 counterbalanced pairs, warmup 1, nominal preheat 20 s다. actual preheat는 18.716–19.130 s였고 모든 9 cell은 raw/trace/manifest/plan/state quality gate를 통과했다. 온도와 clock은 기록하되 randomized treatment가 아니므로 에너지 효과의 인과 보정에 쓰지 않았다."
        )},
        {"id": "operating_state_intro", "type": "markdown", "sourceId": "session_cells", "body": (
            "## operating state는 결과를 설명하는 인과변수가 아니다\n\n"
            "아래 산점도는 fresh cell effect와 trace temperature midpoint를 함께 보이는 QA 진단이다. 세션 수가 작고 implementation, position, 시간 경과가 함께 존재하므로 기울기나 상관을 thermal coefficient로 해석하지 않는다."
        )},
        {"id": "operating_state_chart", "type": "chart", "chartId": "effect_vs_temperature"},
        {"id": "limitations", "type": "markdown", "body": (
            "## 한계와 불확실성\n\n"
            "이 결과는 한 RTX 3090, 한 coordinate, 세 fresh session에 한정된다. NVML board-energy differential은 sub-watt 차이에 민감하고, n=3 interval은 넓은 descriptive diagnostic이다. FP32와 native FP16 경로는 operand generation/precision/compiler path가 다르며, packed path는 pack/unpack, predicate, XOR sink, scheduling, final SASS lowering 효과를 포함한다. 따라서 총 Softmax energy, physical MUFU energy, cross-GPU coefficient, packed throughput/energy superiority를 주장하지 않는다."
        )},
        {"id": "next_steps", "type": "markdown", "body": (
            "## 권장 다음 단계\n\n"
            "1. 이 결과만으로 CTA/S sweep을 더 넓히지 않는다.\n"
            "2. scalar–packed 차이를 결정해야 하면 fresh session 수와 meter resolution을 사전에 고정한 별도 protocol을 사용한다.\n"
            "3. packed lane-order 불안을 더 줄이려면 asymmetric half-pair all-encoding test를 별도로 추가한다.\n"
            "4. 절대 component energy가 필요하면 external high-resolution meter 또는 더 큰, 사전등록된 measurement design을 사용한다."
        )},
        {"id": "further_questions", "type": "markdown", "body": (
            "## 후속 질문\n\n"
            "새 independent date 또는 board에서도 scalar의 session variability가 같은 규모인가? fixed-clock 또는 external meter가 scalar–packed contrast의 interval을 실제로 줄이는가? sm80 또는 이후 architecture에서 f16x2의 final lowering과 result가 어떻게 달라지는가?"
        )},
    ]


def charts() -> list[dict[str, Any]]:
    unit = "incremental pJ/element"
    return [
        chart(chart_id="historical_and_fresh_effects", title="Historical target values and fresh confirmation mean", subtitle="CTA=48, S=1024; historical rows are context only and the fresh mean uses three independent sessions.", question="How does the disputed target coordinate compare with the position-balanced confirmation?", rationale="Grouped discrete bars are appropriate for three implementation paths and three explicitly labeled session scopes.", dataset="historical_and_fresh", source_id="historical", chart_type="bar", x_field="implementation_label", x_type="ordinal", x_label="Implementation", y_field="effect_incremental_pj_per_element", y_label="Energy increment", y_unit=unit, color_field="series", color_label="Evidence scope", tooltip=[{"field":"implementation_label","type":"nominal","label":"Implementation"},{"field":"series","type":"nominal","label":"Series"},{"field":"effect_incremental_pj_per_element","type":"quantitative","label":"ΔpJ/element","unit":unit,"format":"number"}], zero_reference=True, grain="one historical target cell or fresh three-session mean"),
        chart(chart_id="fresh_session_effects", title="Fresh session effects", subtitle="Nine quality-pass cell means; each implementation occupies positions 1, 2, and 3 once across the three sessions.", question="How variable are the three independent fresh session effects?", rationale="A small labeled scatter retains all nine primary experimental-unit observations without pretending matched blocks are independent.", dataset="fresh_session_effects", source_id="session_cells", chart_type="scatter", x_field="implementation_position", x_type="quantitative", x_label="Implementation position within session", y_field="effect_incremental_pj_per_element", y_label="Energy increment", y_unit=unit, color_field="implementation_label", color_label="Implementation", tooltip=[{"field":"session_label","type":"nominal","label":"Session"},{"field":"implementation_label","type":"nominal","label":"Implementation"},{"field":"implementation_position","type":"quantitative","label":"Position","format":"number"},{"field":"effect_incremental_pj_per_element","type":"quantitative","label":"ΔpJ/element","unit":unit,"format":"number"},{"field":"cell_verdict","type":"nominal","label":"Cell diagnostic verdict"}], zero_reference=True, grain="one fresh session implementation mean"),
        chart(chart_id="within_session_contrasts", title="Within-session implementation-path contrasts", subtitle="Each point is a complete-path contrast in one fresh session; 0 means no observed difference.", question="Does packed FP16x2 differ from scalar FP16 consistently within the same session?", rationale="Contrast dots show sign and session variation directly, including the uncertainty-relevant negative packed-minus-scalar session.", dataset="within_session_contrasts", source_id="contrasts", chart_type="scatter", x_field="session_index", x_type="quantitative", x_label="Fresh session", y_field="effect_incremental_pj_per_element", y_label="Path contrast", y_unit=unit, color_field="contrast_label", color_label="Contrast", tooltip=[{"field":"session_label","type":"nominal","label":"Session"},{"field":"contrast_label","type":"nominal","label":"Contrast"},{"field":"effect_incremental_pj_per_element","type":"quantitative","label":"ΔpJ/element","unit":unit,"format":"number"},{"field":"left_position","type":"quantitative","label":"Left position","format":"number"},{"field":"right_position","type":"quantitative","label":"Right position","format":"number"}], zero_reference=True, grain="one within-session implementation-path contrast"),
        chart(chart_id="static_lowering", title="Static PTX-to-SASS EX2 instruction counts", subtitle="Exact S=1024 generated specialization on the frozen RTX 3090 binary; counts are static code counts, not energy.", question="Does packed f16x2 remain a single two-lane MUFU in final sm86 SASS?", rationale="Paired category bars compare source PTX form with final SASS lowering without conflating instruction count with energy.", dataset="static_lowering", source_id="sass", chart_type="bar", x_field="implementation_label", x_type="ordinal", x_label="Native implementation", y_field="static_instruction_count", y_label="Static instruction count", y_unit="count", color_field="stage", color_label="Code stage", tooltip=[{"field":"implementation_label","type":"nominal","label":"Implementation"},{"field":"stage","type":"nominal","label":"Stage"},{"field":"static_instruction_count","type":"quantitative","label":"Count","unit":"count","format":"number"}], zero_reference=True, grain="one static code specialization"),
        chart(chart_id="effect_vs_temperature", title="Fresh effect and trace temperature midpoint", subtitle="QA diagnostic only: nine cell means at the fixed coordinate; no thermal causal effect is estimated.", question="Are fresh cell effects visibly accompanied by a particular temperature pattern?", rationale="A scatter preserves the small set of session-cell observations and prevents a causal trend claim from a sequential design.", dataset="fresh_session_effects", source_id="session_cells", chart_type="scatter", x_field="temperature_mid_c", x_type="quantitative", x_label="Trace temperature midpoint", y_field="effect_incremental_pj_per_element", y_label="Energy increment", y_unit=unit, color_field="implementation_label", color_label="Implementation", tooltip=[{"field":"session_label","type":"nominal","label":"Session"},{"field":"implementation_label","type":"nominal","label":"Implementation"},{"field":"temperature_mid_c","type":"quantitative","label":"Temperature midpoint","unit":"°C","format":"number"},{"field":"effect_incremental_pj_per_element","type":"quantitative","label":"ΔpJ/element","unit":unit,"format":"number"},{"field":"preheat_actual_s","type":"quantitative","label":"Preheat actual","unit":"s","format":"number"}], zero_reference=True, grain="one fresh session implementation mean"),
    ]


def local_contract(artifact: dict[str, Any]) -> dict[str, Any]:
    manifest = artifact["manifest"]
    require(artifact["surface"] == "report" and manifest["surface"] == "report", "artifact surface drifted")
    require(manifest["title"] == TITLE, "artifact title drifted")
    require(manifest["blocks"][0]["body"] == f"# {TITLE}", "first title block drifted")
    ids = lambda entries: [entry["id"] for entry in entries]
    require(len(ids(manifest["sources"])) == len(set(ids(manifest["sources"]))), "duplicate source ID")
    require(len(ids(manifest["charts"])) == len(set(ids(manifest["charts"]))), "duplicate chart ID")
    require(len(ids(manifest["tables"])) == len(set(ids(manifest["tables"]))), "duplicate table ID")
    datasets = artifact["snapshot"]["datasets"]
    for item in manifest["charts"]:
        require(item["dataset"] in datasets and item["sourceId"] in set(ids(manifest["sources"])), f"bad chart linkage: {item['id']}")
    for item in manifest["tables"]:
        require(item["dataset"] in datasets and item["sourceId"] in set(ids(manifest["sources"])), f"bad table linkage: {item['id']}")
    for item in manifest["blocks"]:
        if "sourceId" in item:
            require(item["sourceId"] in set(ids(manifest["sources"])), f"bad block source: {item['id']}")
    serialized = json.dumps(artifact, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    require(len(serialized.encode("utf-8")) <= 3 * 1024 * 1024, "artifact exceeds 3 MB")
    require(len(json.dumps(datasets, ensure_ascii=False, allow_nan=False)) <= 200_000, "snapshot exceeds inline size budget")
    require(all(len(value) <= 2000 for value in datasets.values()), "dataset row limit exceeded")
    return {"dataset_count": len(datasets), "row_count": sum(len(value) for value in datasets.values()), "serialized_size_bytes": len(serialized.encode("utf-8")), "payload": serialized}


def qa_markdown(generated_at: str, artifact_rel: str, artifact_hash: str, builder_hash: str, notes: dict[str, Any], paths: dict[str, Path], root: Path) -> str:
    summary = notes["summary_by_impl"]
    packed_diff = notes["contrast_by_name"]["ptx_f16x2_minus_ptx_f16"]
    source_lines = "\n".join(f"- `{repo_relative(path, root)}` — SHA-256 `{sha256(path)}`" for name, path in sorted(paths.items()) if path.is_file() and name not in {"kernel", "runner", "analyzer"})
    return f"""# RTX 3090 Softmax EX2 CTA=48/S=1024 targeted confirmation report QA

## Overall assessment: Share with caveats after artifact validation and portable packaging

The builder independently accepted the frozen `CTA=48, S=1024` program, 9/9 complete quality-pass cells, three cyclic fresh sessions, 27 matched blocks, exact denominator aliases, three implementation summaries, native numerical validation, static SASS audit, and dynamic NCU path-only audit. The canonical artifact is ready for external `validate_artifact` and portable HTML packaging; those two results are appended by the owning workflow.

## Calculation spot-checks

- Primary independent unit: one fresh session implementation mean, `n=3` per implementation. Matched blocks are not pooled as independent repetitions.
- `pJ/logical result == incremental pJ/element` row-wise for all 9 cells because treatment adds exactly one logical EX2 result per input element.
- FP32 mean: `{display_number(number(summary['fp32'], 'mean_incremental_pJ_per_element', 'fp32'))}` incremental pJ/element.
- Scalar FP16 mean: `{display_number(number(summary['ptx_f16'], 'mean_incremental_pJ_per_element', 'scalar'))}` incremental pJ/element.
- Packed FP16x2 mean: `{display_number(number(summary['ptx_f16x2'], 'mean_incremental_pJ_per_element', 'packed'))}` incremental pJ/element.
- Packed−scalar contrast: `{display_number(number(packed_diff, 'mean_incremental_pJ_per_element', 'contrast'))}`; diagnostic t95 `[ {display_number(number(packed_diff, 'diagnostic_t95_low_incremental_pJ_per_element', 'contrast'))}, {display_number(number(packed_diff, 'diagnostic_t95_high_incremental_pJ_per_element', 'contrast'))} ]`, which includes zero.
- Native NCU observed/expected treatment-control XU delta: `49,152,000` for scalar FP16 and packed FP16x2; profiler energy is excluded.
- SASS: packed source has 4 `f16x2` PTX instructions but final sm86 code has 8 scalar `MUFU.EX2.F16`; it is not evidence of one physical two-lane MUFU issue.

## Required caveats

- This is incremental board-energy contrast for an added exponent path, not total Softmax pJ/element or pure functional-unit energy.
- Three fresh sessions provide only a descriptive df=2 interval; the report does not claim packed superiority.
- Historical 60-cell target values are context only and are excluded from the new primary aggregate.
- Temperature/clock fields are QA diagnostics, not randomized causal covariates.

## Artifact inventory

- Generated: `{generated_at}`
- Canonical artifact: `{artifact_rel}`
- Artifact SHA-256: `{artifact_hash}`
- Builder SHA-256: `{builder_hash}`
- Datasets: `{notes['dataset_count']}`; rows: `{notes['row_count']}`; serialized bytes: `{notes['serialized_size_bytes']}`

## Input hashes

{source_lines}

## Packaging status

Pending external canonical artifact validation and the Data Analytics portable HTML packager. The owner must update this section before handoff.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact-out", type=Path, default=Path("docs/results/rtx3090_softmax_ex2_targeted_confirmation_20260725_artifact.json"))
    parser.add_argument("--qa-out", type=Path, default=Path("docs/results/rtx3090_softmax_ex2_targeted_confirmation_20260725_report_qa.md"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    artifact_path = args.artifact_out if args.artifact_out.is_absolute() else root / args.artifact_out
    qa_path = args.qa_out if args.qa_out.is_absolute() else root / args.qa_out
    paths, rows, details = validate_inputs(root)
    generated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    artifact_sources = sources(paths, root)
    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": TITLE,
            "description": "Technical confirmation of the disputed RTX 3090 Softmax EX2 CTA=48/S=1024 coordinate with three position-balanced fresh sessions.",
            "generatedAt": generated_at,
            "sources": artifact_sources,
            "charts": charts(),
            "tables": tables(),
            "blocks": blocks(details),
        },
        "snapshot": {"version": 1, "generatedAt": generated_at, "status": "ready", "datasets": datasets(rows, details)},
        "sources": artifact_sources,
    }
    notes = local_contract(artifact)
    artifact_payload = notes.pop("payload")
    atomic_write(artifact_path, artifact_payload)
    artifact_hash = sha256(artifact_path)
    builder_hash = sha256(Path(__file__).resolve())
    artifact_rel = artifact_path.resolve().relative_to(root).as_posix()
    qa_payload = qa_markdown(generated_at, artifact_rel, artifact_hash, builder_hash, {**notes, **details}, paths, root)
    atomic_write(qa_path, qa_payload)
    print(f"artifact={artifact_rel}")
    print(f"qa={qa_path.resolve().relative_to(root).as_posix()}")
    print(f"artifact_sha256={artifact_hash}")
    print(f"datasets={notes['dataset_count']}")
    print(f"rows={notes['row_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as error:
        raise SystemExit(f"evidence error: {error}")
