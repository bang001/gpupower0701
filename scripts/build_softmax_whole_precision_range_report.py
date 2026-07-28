#!/usr/bin/env python3
"""Build the portable Korean report for a validated Softmax range screen.

The report consumes only the fail-closed range analyzer product.  It keeps a
screened best/worst range distinct from fresh extrema confirmation, and never
mixes complete-Softmax pJ/output with the older EX2 Operand-rate ATC metric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = "softmax_whole_precision_range_analysis_v1"
STATIC_AUDIT_SCHEMA = "softmax_whole_precision_range_static_audit_v1"
METRIC = "net_pJ_per_logical_output_element"
DISPLAY_UNIT = "pJ/element"
DISPLAY_METRIC = "net pJ/element"
PLUGIN_ROOT = Path(
    "/home/bang001/.codex/plugins/cache/openai-curated-remote/data-analytics/"
    "0.2.8-13ceeea1f599"
)
POLICY_LABELS = {
    "fp32_io_fp32_all": "FP32 endpoint",
    "fp16_scalar_all": "scalar FP16 endpoint",
    "fp16x2_all": "packed FP16x2 endpoint",
}
COORDINATE_LABELS = {
    "s512_q50": "S=512 · q50",
    "s1024_q50": "S=1024 · q50 (representative)",
    "s2048_q50": "S=2048 · q50",
    "s4096_q50": "S=4096 · q50",
    "s512_q25": "S=512 · q25",
    "s1024_q25": "S=1024 · q25",
    "s4096_q25": "S=4096 · q25",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"JSON root is not an object: {path}")
    return payload


def resolve_evidence_path(value: object, label: str) -> Path:
    require(isinstance(value, str) and bool(value), f"{label} path is missing")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def validate_manifest_audit(manifest: Mapping[str, Any], label: str) -> dict[str, Any]:
    """Validate the audit binding for one analysis evidence manifest.

    A combined follow-up analysis has two manifest/audit pairs.  Rechecking
    both prevents a report generated later from silently retaining parent
    values after that parent evidence has changed or disappeared.
    """

    binding = manifest.get("sass_audit")
    require(isinstance(binding, dict), f"{label} lacks a bound static audit")
    audit_path = resolve_evidence_path(binding.get("path"), f"{label} static-audit")
    require(audit_path.is_file() and sha256_file(audit_path) == binding.get("sha256"),
            f"{label} static-audit binding is not intact")
    audit = read_json(audit_path)
    require(audit.get("schema_version") == STATIC_AUDIT_SCHEMA,
            f"{label} static-audit schema mismatch")
    require(audit.get("overall", {}).get("pass") is True,
            f"{label} static audit did not pass")
    binary = manifest.get("binary")
    require(isinstance(binary, dict) and
            audit.get("binary", {}).get("sha256") == binary.get("sha256"),
            f"{label} static audit and measured binary differ")
    return audit


def number(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field} is not numeric") from error
    require(math.isfinite(value), f"{field} is not finite")
    return value


def fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def load_evidence(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    analysis_path = run_dir / "analysis" / "analysis.json"
    manifest_path = run_dir / "manifest.json"
    analysis = read_json(analysis_path)
    manifest = read_json(manifest_path)
    require(analysis.get("schema_version") == ANALYSIS_SCHEMA, "range analysis schema mismatch")
    require(analysis.get("status") == "pass", "range analysis did not pass")
    require(analysis.get("primary_metric") == METRIC, "range primary metric drifted")
    analysis_manifest = analysis.get("manifest")
    require(isinstance(analysis_manifest, dict) and
            analysis_manifest.get("sha256") == sha256_file(manifest_path),
            "analysis is not bound to the current manifest")
    evidence_runs = analysis.get("evidence_runs")
    require(isinstance(evidence_runs, list) and evidence_runs,
            "analysis evidence-run list is missing")
    current_seen = False
    current_audit: dict[str, Any] | None = None
    for index, evidence in enumerate(evidence_runs, start=1):
        require(isinstance(evidence, dict), f"analysis evidence run {index} is invalid")
        evidence_dir = resolve_evidence_path(evidence.get("run_dir"), f"analysis evidence run {index}")
        evidence_manifest_path = evidence_dir / "manifest.json"
        require(evidence_manifest_path.is_file(),
                f"analysis evidence run {index} manifest is missing")
        require(sha256_file(evidence_manifest_path) == evidence.get("manifest_sha256"),
                f"analysis evidence run {index} manifest SHA changed after analysis")
        evidence_manifest = read_json(evidence_manifest_path)
        evidence_audit = validate_manifest_audit(evidence_manifest, f"analysis evidence run {index}")
        audit_record = evidence.get("static_audit")
        binding = evidence_manifest.get("sass_audit")
        require(isinstance(audit_record, dict) and
                isinstance(binding, dict) and
                audit_record.get("sha256") == binding.get("sha256") and
                resolve_evidence_path(audit_record.get("path"),
                                      f"analysis evidence run {index} audit") ==
                resolve_evidence_path(binding.get("path"),
                                      f"analysis evidence run {index} bound audit") and
                audit_record.get("sha256") == sha256_file(
                    resolve_evidence_path(audit_record.get("path"),
                                          f"analysis evidence run {index} audit")
                ),
                f"analysis evidence run {index} audit SHA changed after analysis")
        if evidence_dir == run_dir:
            require(not current_seen, "analysis lists the current run more than once")
            current_seen = True
            current_audit = evidence_audit
    require(current_seen and current_audit is not None,
            "analysis evidence-run list does not include the requested run")
    return analysis, manifest, current_audit


def friendly_coordinate_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        coordinate = str(row["coordinate_id"])
        policy = str(row["policy"])
        result.append({
            "coordinate_id": coordinate,
            "coordinate_label": COORDINATE_LABELS.get(coordinate, coordinate),
            "policy": policy,
            "policy_label": POLICY_LABELS.get(policy, policy),
            "softmax_cols": int(row["softmax_cols"]),
            "grid_blocks": int(row["grid_blocks"]),
            "requested_sm_coverage": number(row, "requested_sm_coverage"),
            "occupancy_max_blocks_per_sm": int(row["occupancy_max_blocks_per_sm"]),
            "fresh_sessions": int(row["n"]),
            "median_net_pj": number(row, "median_net_pj"),
            "mean_net_pj": number(row, "mean_net_pj"),
            "sample_std_net_pj": number(row, "sample_std_net_pj"),
            "min_session_net_pj": number(row, "min_session_net_pj"),
            "max_session_net_pj": number(row, "max_session_net_pj"),
            "t95_low_net_pj": number(row, "t95_low_net_pj"),
            "t95_high_net_pj": number(row, "t95_high_net_pj"),
        })
    return sorted(result, key=lambda item: (item["coordinate_id"], item["policy"]))


def friendly_range_rows(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for row in rows:
        policy = str(row["policy"])
        best = number(row, "best_median_net_pj")
        worst = number(row, "worst_median_net_pj")
        representative = row.get("representative_median_net_pj", "")
        require(representative != "", "report requires an S1024/q50 representative")
        representative_value = number(row, "representative_median_net_pj")
        item = {
            "policy": policy,
            "policy_label": POLICY_LABELS.get(policy, policy),
            "range_status": str(row["range_status"]),
            "best_coordinate": str(row["best_coordinate_primary"]),
            "best_coordinate_set_within_10pct": str(row["best_coordinate_set_within_10pct"]),
            "best_median_net_pj": best,
            "representative_coordinate": str(row["representative_coordinate"]),
            "representative_median_net_pj": representative_value,
            "representative_mean_net_pj": number(row, "representative_mean_net_pj"),
            "representative_t95_low_net_pj": number(row, "representative_t95_low_net_pj"),
            "representative_t95_high_net_pj": number(row, "representative_t95_high_net_pj"),
            "worst_coordinate": str(row["worst_coordinate_primary"]),
            "worst_coordinate_set_within_10pct": str(row["worst_coordinate_set_within_10pct"]),
            "worst_median_net_pj": worst,
        }
        summary.append(item)
        for role, value, coordinate in (
            ("screened best", best, item["best_coordinate"]),
            ("fixed representative", representative_value, item["representative_coordinate"]),
            ("screened worst", worst, item["worst_coordinate"]),
        ):
            points.append({
                "policy": policy,
                "policy_label": item["policy_label"],
                "range_role": role,
                "coordinate_id": coordinate,
                "coordinate_label": COORDINATE_LABELS.get(coordinate, coordinate),
                "median_net_pj": value,
            })
    return sorted(summary, key=lambda item: item["policy"]), points


def representative_readout(rows: list[Mapping[str, Any]]) -> str:
    """Return the decision-relevant fixed-coordinate comparison.

    The fixed representative is deliberately more useful than a post-hoc
    global minimum: it answers the user's FP32/FP16/FP16x2 comparison at one
    predeclared coordinate while keeping the broader screened envelope visible.
    """

    by_policy = {str(row["policy"]): row for row in rows}
    required = ("fp32_io_fp32_all", "fp16_scalar_all", "fp16x2_all")
    require(all(policy in by_policy for policy in required),
            "three endpoint rows are required for the representative readout")
    fp32 = number(by_policy["fp32_io_fp32_all"], "representative_median_net_pj")
    scalar = number(by_policy["fp16_scalar_all"], "representative_median_net_pj")
    packed = number(by_policy["fp16x2_all"], "representative_median_net_pj")
    return (
        "사전 고정 대표 좌표 `S=1024,q50`의 median은 "
        f"FP32 {fmt(fp32)}, scalar FP16 {fmt(scalar)}, packed FP16x2 {fmt(packed)} "
        "pJ/element였다. 여기서 element는 logical Softmax output element 하나이고, "
        "packed FP16x2도 두 scalar element를 이미 분모에 포함한다. packed가 이 대표 좌표에서는 가장 낮지만, "
        "screened envelope 전체의 범위는 coordinate에 따라 겹친다. 따라서 이를 모든 "
        "S·CTA 조건에서 packed가 보편적으로 우월하다는 주장으로 일반화하지 않는다."
    )


def source_record(run_dir: Path, analysis: Mapping[str, Any]) -> dict[str, Any]:
    analysis_path = run_dir / "analysis" / "analysis.json"
    evidence_runs = analysis.get("evidence_runs", [])
    require(isinstance(evidence_runs, list) and evidence_runs, "analysis evidence-run list missing")
    tables = [repo_path(analysis_path)]
    for evidence in evidence_runs:
        require(isinstance(evidence, dict), "invalid evidence-run item")
        tables.append(repo_path(
            resolve_evidence_path(evidence.get("run_dir"), "analysis evidence run") / "manifest.json"
        ))
    return {
        "id": "analysis",
        "label": "Fail-closed whole-Softmax precision range analysis",
        "path": repo_path(analysis_path),
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT range_summary, coordinate_summary FROM read_json_auto('{repo_path(analysis_path)}');",
            "description": (
                "The report consumes the analyzer's SHA-bound result arrays. The analyzer checks "
                "frozen binary/runner, raw/trace SHA, target-native PTX/SASS audit binding, "
                "5-second common conditioning, numerical validation, logical denominator, trace, "
                "and one-CTA-per-distinct-SM placement before computing medians."
            ),
            "tables_used": tables,
            "metric_definitions": [
                "Primary metric = (qualified NVML trace energy − idle power × elapsed) × 1e12 / logical Softmax output elements; displayed as net pJ/element.",
                "A coordinate/policy estimate is the median of three fresh CUDA-process sessions.",
                "Best/worst are screened coordinate medians; the representative is predeclared S=1024,q50.",
            ],
            "filters": [
                "complete Softmax forward endpoint", "256 threads/CTA", "2 rows/CTA",
                "5-second requested common FP32 conditioner", "temperature recorded but not adjusted",
            ],
        },
    }


def artifact_payload(
    run_dir: Path, analysis: Mapping[str, Any], manifest: Mapping[str, Any],
    audit: Mapping[str, Any], range_rows: list[dict[str, Any]],
    range_points: list[dict[str, Any]], coordinate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    source = source_record(run_dir, analysis)
    profile = manifest["profile"]["name"]
    device = "RTX 3090" if profile == "rtx3090" else profile
    followup = analysis["followup_plan"]
    status = str(followup.get("status"))
    action = ", ".join(followup.get("coordinates", [])) or "none"
    if status == "followup_complete_screened_range_not_fresh_extrema_confirmed":
        action_text = "gate-triggered follow-up coordinates were acquired; extrema remain screened, not independently confirmed."
    elif status == "followup_required":
        action_text = f"only these adaptive coordinates remain: {action}."
    else:
        action_text = "no broader CTA×S factorial sweep is justified by this screen."
    quality = analysis["quality_gates"]
    readout = representative_readout(range_rows)
    title = f"{device} complete-Softmax FP32 / FP16 / FP16x2 range screen"
    return {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": title,
            "description": "Minimal cross-platform-ready endpoint range screen with fixed representative and adaptive stop rule.",
            "generatedAt": analysis["analyzed_at"],
            "sources": [source],
            "charts": [
                {
                    "id": "screened_range",
                    "title": "Policy별 screened best / fixed representative / screened worst",
                    "subtitle": "각 bar는 해당 coordinate의 fresh 3-session median; screened extrema는 별도 fresh confirmation 전 확정값이 아니다.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "각 complete-Softmax precision endpoint에서 사전 지정 envelope의 범위와 대표값은 무엇인가?",
                    "rationale": "best/representative/worst를 한 common pJ/element axis에 두되, coordinate label을 tooltip으로 남겨 post-hoc 단일 우승자로 과장하지 않는다.",
                    "comparisonContext": {
                        "baseline": "not a paired baseline; within-policy coordinate medians",
                        "denominator": "one logical Softmax output element",
                        "grain": "three fresh CUDA-process sessions per coordinate/policy",
                        "unit": DISPLAY_METRIC,
                    },
                    "dataset": "range_points",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "policy_label", "type": "ordinal", "label": "Complete Softmax endpoint"},
                        "y": {"field": "median_net_pj", "type": "quantitative", "label": "Fresh-session median", "unit": DISPLAY_UNIT, "format": "number"},
                        "color": {"field": "range_role", "type": "nominal", "label": "Range role"},
                        "tooltip": [
                            {"field": "policy_label", "type": "nominal", "label": "Endpoint"},
                            {"field": "range_role", "type": "nominal", "label": "Role"},
                            {"field": "coordinate_label", "type": "nominal", "label": "Coordinate"},
                            {"field": "median_net_pj", "type": "quantitative", "label": "Median", "unit": DISPLAY_UNIT, "format": "number"},
                        ],
                    },
                    "palette": {"kind": "hard-three-root", "name": "whole-softmax-range-roles"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "bottom"},
                },
                {
                    "id": "coordinate_medians",
                    "title": "Coordinate별 fresh-session median",
                    "subtitle": "S width와 requested q의 영향은 endpoint별로 별도 표시한다; platform 간 수치는 pool하지 않는다.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "initial/adaptive coordinate가 pJ/element에 practical 차이를 보이는가?",
                    "rationale": "adaptive stop decision이 쓰는 coordinate median을 endpoint color로 직접 보여 준다.",
                    "comparisonContext": {
                        "baseline": "not applicable; independent coordinate medians",
                        "denominator": "one logical Softmax output element",
                        "grain": "three fresh CUDA-process sessions per coordinate/policy",
                        "unit": DISPLAY_METRIC,
                    },
                    "dataset": "coordinate_summary",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "coordinate_label", "type": "ordinal", "label": "Coordinate"},
                        "y": {"field": "median_net_pj", "type": "quantitative", "label": "Fresh-session median", "unit": DISPLAY_UNIT, "format": "number"},
                        "color": {"field": "policy_label", "type": "nominal", "label": "Endpoint"},
                        "tooltip": [
                            {"field": "coordinate_label", "type": "nominal", "label": "Coordinate"},
                            {"field": "policy_label", "type": "nominal", "label": "Endpoint"},
                            {"field": "median_net_pj", "type": "quantitative", "label": "Median", "unit": DISPLAY_UNIT, "format": "number"},
                            {"field": "sample_std_net_pj", "type": "quantitative", "label": "Session SD", "unit": DISPLAY_UNIT, "format": "number"},
                        ],
                    },
                    "palette": {"kind": "hard-three-root", "name": "whole-softmax-range-policies"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "bottom"},
                },
            ],
            "tables": [
                {
                    "id": "range_table", "title": "Screened range and fixed representative",
                    "subtitle": "10% tie set is reported rather than forcing a single winner; values are not a pure EX2/SFU energy coefficient.",
                    "dataset": "range_summary", "sourceId": "analysis",
                    "defaultSort": {"field": "policy_label", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [
                        {"field": "policy_label", "label": "Endpoint"},
                        {"field": "best_coordinate", "label": "Screened best coordinate"},
                        {"field": "best_median_net_pj", "label": "Best median", "format": "number"},
                        {"field": "representative_coordinate", "label": "Fixed representative"},
                        {"field": "representative_median_net_pj", "label": "Representative median", "format": "number"},
                        {"field": "worst_coordinate", "label": "Screened worst coordinate"},
                        {"field": "worst_median_net_pj", "label": "Worst median", "format": "number"},
                        {"field": "range_status", "label": "Status"},
                    ],
                },
                {
                    "id": "coordinate_table", "title": "Coordinate summary and repeatability context",
                    "subtitle": "n=3 fresh sessions per endpoint/coordinate; t95 is descriptive, not a cross-platform ranking test.",
                    "dataset": "coordinate_summary", "sourceId": "analysis",
                    "defaultSort": {"field": "coordinate_id", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [
                        {"field": "coordinate_id", "label": "Coordinate ID"},
                        {"field": "coordinate_label", "label": "Coordinate"},
                        {"field": "policy_label", "label": "Endpoint"},
                        {"field": "fresh_sessions", "label": "Fresh sessions", "format": "number"},
                        {"field": "median_net_pj", "label": "Median", "format": "number"},
                        {"field": "sample_std_net_pj", "label": "Session SD", "format": "number"},
                        {"field": "t95_low_net_pj", "label": "t95 low", "format": "number"},
                        {"field": "t95_high_net_pj", "label": "t95 high", "format": "number"},
                        {"field": "occupancy_max_blocks_per_sm", "label": "Occupancy CTA/SM", "format": "number"},
                    ],
                },
                {
                    "id": "quality_table", "title": "Evidence-quality gates",
                    "subtitle": "Temperature is recorded as context, not used as a causal correction.",
                    "dataset": "quality", "sourceId": "analysis",
                    "defaultSort": {"field": "check", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [
                        {"field": "check", "label": "Gate"}, {"field": "result", "label": "Result"}, {"field": "detail", "label": "Detail"},
                    ],
                },
            ],
            "blocks": [
                {"id": "title", "type": "markdown", "body": f"# {title}"},
                {"id": "technical_summary", "type": "markdown", "sourceId": "analysis", "body": (
                    "## 기술 요약\n\n"
                    f"**{device}에서 complete Softmax FP32, scalar FP16, packed FP16x2 endpoint를 작은 사전 지정 envelope로 측정했다.** "
                    "대표값은 결과를 본 뒤 고르지 않은 `S=1024,q50`이고, best/worst는 fresh 3-session coordinate median의 screened 범위다. "
                    "이 값은 `net pJ/element`이며, element는 logical Softmax output element 하나다. packed FP16x2도 두 scalar element를 이미 분모에 포함한다. EX2 Operand-rate ATC의 pJ/logical exponent result와 평균·차감·합산할 수 없다.\n\n"
                    f"{readout}"
                )},
                {"id": "range_intro", "type": "markdown", "sourceId": "analysis", "body": (
                    "## Screened range versus fixed representative\n\n"
                    "아래 chart는 각 policy에서 screened best, 사전 고정 representative, screened worst를 함께 보인다. "
                    "10% 안의 tie coordinate는 table에 남기며, extrema를 다시 fresh session으로 확인하기 전에는 `confirmed observed range`라고 부르지 않는다."
                )},
                {"id": "range_chart", "type": "chart", "chartId": "screened_range"},
                {"id": "range_table_block", "type": "table", "tableId": "range_table"},
                {"id": "coordinate_intro", "type": "markdown", "sourceId": "analysis", "body": (
                    "## 왜 이 좌표만 측정했는가\n\n"
                    "256-thread CTA에서 S=512는 2 element/thread natural anchor, S=1024는 fixed representative/plateau-entry test, "
                    "S=4096는 resource boundary, q25는 concurrency sensitivity다. S=128/256 같은 다른 geometry는 처음부터 섞지 않았다. "
                    "실제 measured role은 `smid_unique=grid_blocks`, `smid_max_blocks_on_sm=1` gate를 통과해야 q placement로 해석한다."
                )},
                {"id": "coordinate_chart", "type": "chart", "chartId": "coordinate_medians"},
                {"id": "coordinate_table_block", "type": "table", "tableId": "coordinate_table"},
                {"id": "method", "type": "markdown", "sourceId": "analysis", "body": (
                    "## Measurement and static-code evidence\n\n"
                    "각 fresh CUDA process는 canonical policy order로 numerical validation/calibration을 마친 뒤 FP32 endpoint로 요청 5 s common conditioner를 한 번 실행한다. "
                    "unrecorded policy warm-up은 없고, three-way order는 ABC/BCA/CAB로 회전한다. "
                    "final analyzer는 frozen binary/runner, raw/trace SHA, 5 s actual gate, qualified NVML trace, logical denominator, SMID placement, FP64-reference numerical validation, "
                    "그리고 같은 frozen binary의 target-native PTX/SASS audit binding을 모두 확인한다."
                )},
                {"id": "quality_table_block", "type": "table", "tableId": "quality_table"},
                {"id": "interpretation", "type": "markdown", "body": (
                    "## 해석 경계\n\n"
                    "FP32 endpoint는 FP32 I/O이고 FP16 endpoint는 FP16 I/O이므로, 이 비교는 pure EX2/SFU/ALU 회로 에너지가 아니라 I/O·rounding·reduction·normalization을 포함한다. "
                    "CTA가 repeated iteration에서 같은 row storage를 재사용하므로 cache-reuse/compute 중심 coordinate의 결과다. "
                    "platform 간 값은 pool하거나 하나의 GPU ranking으로 만들지 않는다. SASS audit도 target-native provenance이며 다른 architecture의 same-lowering, physical two-lane issue, cycle 또는 energy attribution을 주장하지 않는다."
                )},
                {"id": "next_steps", "type": "markdown", "body": (
                    "## Adaptive decision and next step\n\n"
                    f"analysis status: `{status}`. {action_text}\n\n"
                    "screened best/worst를 final range로 승격해야 한다면, policy별로 선택된 extrema를 새 fresh 3-session으로 재확인한다. "
                    "그 전에는 broad CTA×S sweep이나 cross-platform pJ ranking을 확대하지 않는다."
                )},
                {"id": "questions", "type": "markdown", "body": (
                    "## 추가 확인 질문\n\n"
                    "A100/H100 native cubin에서 같은 PTX endpoint contract가 어떤 target-specific SASS provenance를 보이는가? "
                    "workload-level numerical tolerance가 stricter할 때 FP16 reduction boundary는 유지되는가? "
                    "fixed clock 또는 external meter가 board-level trace variance 해석을 바꾸는가?"
                )},
            ],
        },
        "snapshot": {
            "version": 1, "generatedAt": analysis["analyzed_at"], "status": "ready",
            "datasets": {
                "range_summary": range_rows,
                "range_points": range_points,
                "coordinate_summary": coordinate_rows,
                "quality": analysis["quality_gates"],
            },
        },
        "sources": [source],
    }


def markdown_report(
    analysis: Mapping[str, Any], range_rows: list[Mapping[str, Any]],
    coordinate_rows: list[Mapping[str, Any]],
) -> str:
    lines = [
        "# Whole-Softmax precision range analysis",
        "",
        "이 문서는 complete Softmax forward의 `net pJ/element`만 다룬다. element는 logical Softmax output element 하나이며, packed FP16x2도 두 scalar element를 이미 분모에 포함한다. EX2 Operand-rate ATC의 `pJ/logical exponent result`와 섞지 않는다.",
        "",
        "## Best / representative / worst (screened)",
        "",
        "| endpoint | screened best (pJ/element) | fixed representative S1024/q50 (pJ/element) | screened worst (pJ/element) | status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in range_rows:
        lines.append(
            f"| {row['policy_label']} | {fmt(row['best_median_net_pj'])} ({row['best_coordinate']}) | "
            f"{fmt(row['representative_median_net_pj'])} | {fmt(row['worst_median_net_pj'])} ({row['worst_coordinate']}) | {row['range_status']} |"
        )
    readout = representative_readout(range_rows)
    lines.extend([
        "",
        "## Fixed representative interpretation",
        "",
        readout,
        "",
        "## Coordinate summary",
        "",
        "| coordinate | endpoint | n | median | SD | descriptive t95 |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in coordinate_rows:
        lines.append(
            f"| {row['coordinate_label']} | {row['policy_label']} | {row['fresh_sessions']} | "
            f"{fmt(row['median_net_pj'])} | {fmt(row['sample_std_net_pj'])} | "
            f"[{fmt(row['t95_low_net_pj'])}, {fmt(row['t95_high_net_pj'])}] |"
        )
    followup = analysis["followup_plan"]
    lines.extend([
        "",
        "## Adaptive decision",
        "",
        f"`{followup.get('status')}`; requested/remaining coordinates: `{', '.join(followup.get('coordinates', [])) or 'none'}`.",
        "",
        "Temperature is recorded context only. Screened extrema need an independent fresh confirmation before being named a confirmed observed range.",
        "",
    ])
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/results")
    parser.add_argument(
        "--portable-builder", type=Path,
        default=PLUGIN_ROOT / "skills/build-report/scripts/deliver_portable_artifact.mjs",
    )
    parser.add_argument("--skip-package", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = args.out_dir.resolve()
    analysis, manifest, audit = load_evidence(run_dir)
    raw_ranges = analysis.get("range_summary")
    raw_coordinates = analysis.get("coordinate_summary")
    require(isinstance(raw_ranges, list) and raw_ranges and
            isinstance(raw_coordinates, list) and raw_coordinates,
            "analysis range/coordinate summaries missing")
    range_rows, range_points = friendly_range_rows(raw_ranges)
    coordinate_rows = friendly_coordinate_rows(raw_coordinates)
    artifact = artifact_payload(
        run_dir, analysis, manifest, audit, range_rows, range_points, coordinate_rows
    )
    prefix = run_dir.name
    markdown_path = out_dir / f"{prefix}_analysis_ko.md"
    artifact_path = out_dir / f"{prefix}_artifact.json"
    html_path = out_dir / f"{prefix}_report.html"
    qa_path = out_dir / f"{prefix}_report_qa.md"
    write_text(markdown_path, markdown_report(analysis, range_rows, coordinate_rows))
    write_text(artifact_path, json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    receipt: dict[str, Any] | None = None
    if not args.skip_package:
        require(args.portable_builder.is_file(), "portable report builder is missing")
        completed = subprocess.run(
            ["node", str(args.portable_builder), "--input", str(artifact_path), "--output", str(html_path)],
            check=False, capture_output=True, text=True,
        )
        if completed.returncode != 0:
            raise ValueError("portable report packaging failed:\n" + completed.stdout + completed.stderr)
        try:
            receipt = json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as error:
            raise ValueError("portable report receipt is missing or invalid") from error
        require(receipt.get("ok") is True and receipt.get("html") == str(html_path),
                "portable report receipt failed")
        qa = ["# Whole-Softmax range report QA", "", "```json",
              json.dumps(receipt, ensure_ascii=False, indent=2), "```", ""]
        if receipt.get("stages", {}).get("verification") == "structural_only":
            qa.append("Chromium 부재로 portable HTML의 structural verification만 수행됐다.")
            qa.append("")
        write_text(qa_path, "\n".join(qa))
    print("range_report_status=pass")
    print(f"markdown={markdown_path}")
    print(f"artifact={artifact_path}")
    if receipt is not None:
        print(f"html={html_path}")
        print(f"qa={qa_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
