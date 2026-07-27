#!/usr/bin/env python3
"""Build the Korean technical report and portable artifact for AB/BA confirmation.

Only a passing, manifest-bound confirmation analysis may enter this report.  It
keeps the two selected contrasts separate and never pools them with the older
stage-isolation selection dataset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = "softmax_whole_precision_targeted_confirmation_analysis_v1"
PRIMARY_METRIC = "net_pJ_per_logical_output_element"
INTERPRETATION_BOUNDARY = (
    "fresh targeted AB/BA replication of two exploratory-selected complete-Softmax "
    "contrasts; not pooled with exploratory data, not EX2 operand-rate ATC or pure unit energy"
)
DEFAULT_PLUGIN_ROOT = Path(
    "/home/bang001/.codex/plugins/cache/openai-curated-remote/data-analytics/"
    "0.2.8-13ceeea1f599"
)

CANDIDATE_LABEL = {
    "exp_packed": "exp · packed FP16",
    "reduction_scalar": "max+sum reduction · scalar FP16",
}


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
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"CSV has no rows: {path}")
    return rows


def number(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field!r} is not numeric in {row}") from error
    if not math.isfinite(value):
        raise ValueError(f"{field!r} is not finite in {row}")
    return value


def integer(row: Mapping[str, Any], field: str) -> int:
    try:
        return int(str(row[field]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field!r} is not an integer in {row}") from error


def fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_evidence(
    run_dir: Path,
    figure_manifest: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    analysis_dir = run_dir / "analysis"
    analysis = read_json(analysis_dir / "analysis.json")
    manifest = read_json(run_dir / "manifest.json")
    sass = read_json(run_dir / "sass_audit.json")
    require(analysis.get("schema_version") == ANALYSIS_SCHEMA, "analysis schema is not certified")
    require(analysis.get("status") == "pass", "analysis status is not pass")
    require(analysis.get("primary_metric") == PRIMARY_METRIC, "primary metric drifted")
    require(analysis.get("validated_cell_count") == 24, "report requires 24 passing role rows")
    require(analysis.get("validated_pair_count") == 12, "report requires 12 passing pair rows")
    require(analysis.get("exploratory_pooling_prohibited") is True, "analysis permits exploratory pooling")
    require(analysis.get("interpretation_boundary") == INTERPRETATION_BOUNDARY,
            "analysis interpretation boundary drifted")
    current_manifest_sha = sha256_file(run_dir / "manifest.json")
    analysis_manifest = analysis.get("manifest", {})
    require(analysis_manifest.get("sha256") == current_manifest_sha,
            "analysis does not bind the current manifest")
    binding = manifest.get("sass_audit", {})
    analysis_sass = analysis.get("sass_audit", {})
    require(binding.get("path") == repo_path(run_dir / "sass_audit.json"),
            "manifest SASS path is not the run-local audit")
    require(binding.get("sha256") == sha256_file(run_dir / "sass_audit.json"),
            "manifest SASS SHA mismatch")
    require(analysis_sass.get("sha256") == binding.get("sha256"),
            "analysis SASS SHA does not bind manifest SASS evidence")
    require(sass.get("overall", {}).get("pass") is True, "SASS audit did not pass")
    require(sass.get("binary", {}).get("sha256") == manifest.get("binary", {}).get("sha256"),
            "SASS audit binary differs from measurement binary")
    # The analysis JSON is the SHA-bound authoritative analysis product.  CSV
    # files are convenient for users and plotting, but must not silently become
    # an unbound second source for a published report.
    summary = analysis.get("candidate_summary")
    pairs = analysis.get("validated_pairs")
    orientation = analysis.get("orientation_diagnostics")
    quality = analysis.get("quality_gates")
    require(all(isinstance(rows, list) for rows in (summary, pairs, orientation, quality)),
            "analysis does not contain the required authoritative result arrays")
    require(all(isinstance(row, dict) for row in summary + pairs + orientation + quality),
            "analysis result arrays contain a non-object row")
    require(len(summary) == 2 and len(pairs) == 12 and len(orientation) == 4,
            "unexpected summary, pair, or orientation cardinality")
    for row in summary:
        candidate = row.get("candidate_id")
        require(candidate in CANDIDATE_LABEL, f"unknown candidate: {candidate}")
        require(integer(row, "fresh_pair_session_count") == 6, "summary n is not six")
        require(integer(row, "ab_session_count") == 3 and integer(row, "ba_session_count") == 3,
                "summary AB/BA balance drifted")
    figures: dict[str, Any] | None = None
    if figure_manifest is not None:
        figures = read_json(figure_manifest)
        require(figures.get("analysis", {}).get("sha256") == sha256_file(analysis_dir / "analysis.json"),
                "figure manifest does not bind the current analysis")
        require(figures.get("analysis", {}).get("manifest_sha256") == current_manifest_sha,
                "figure manifest does not bind the current manifest")
    return analysis, manifest, sass, summary, pairs, orientation, quality, figures


def friendly_summary(summary: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, row in enumerate(summary, start=1):
        mean = number(row, "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element")
        low = number(row, "t95_low_delta_net_pJ_per_logical_output_element")
        high = number(row, "t95_high_delta_net_pJ_per_logical_output_element")
        rows.append(
            {
                "candidate_order": order,
                "candidate_id": row["candidate_id"],
                "candidate_label": CANDIDATE_LABEL[row["candidate_id"]],
                "baseline_policy": row["baseline_policy"],
                "treatment_policy": row["treatment_policy"],
                "fresh_pair_sessions": integer(row, "fresh_pair_session_count"),
                "ab_sessions": integer(row, "ab_session_count"),
                "ba_sessions": integer(row, "ba_session_count"),
                "baseline_mean_net_pj": number(row, "baseline_mean_net_pJ_per_logical_output_element"),
                "treatment_mean_net_pj": number(row, "treatment_mean_net_pJ_per_logical_output_element"),
                "mean_delta_net_pj": mean,
                "sample_std_delta_net_pj": number(row, "sample_std_delta_net_pJ_per_logical_output_element"),
                "t95_low_delta_net_pj": low,
                "t95_high_delta_net_pj": high,
                "negative_sessions": integer(row, "negative_delta_session_count"),
                "positive_sessions": integer(row, "positive_delta_session_count"),
                "zero_excluded": str(row["zero_excluded_by_descriptive_t95"]).lower() == "true",
                "all_same_direction": str(row["all_session_directions_same"]).lower() == "true",
            }
        )
    return rows


def friendly_pairs(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in pairs:
        result.append(
            {
                "candidate_id": row["candidate_id"],
                "candidate_label": CANDIDATE_LABEL[row["candidate_id"]],
                "global_session_index": integer(row, "global_session_index"),
                "session_order": row["session_order"],
                "baseline_net_pj": number(row, "baseline_net_pJ_per_logical_output_element"),
                "treatment_net_pj": number(row, "treatment_net_pJ_per_logical_output_element"),
                "delta_net_pj": number(row, "delta_treatment_minus_baseline_net_pJ_per_logical_output_element"),
                "preheat_s": number(row, "preheat_actual_s"),
                "temperature_min_c": number(row, "temperature_min_C"),
                "temperature_max_c": number(row, "temperature_max_C"),
            }
        )
    return result


def friendly_orientation(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": row["candidate_id"],
            "candidate_label": CANDIDATE_LABEL[row["candidate_id"]],
            "session_order": row["session_order"],
            "fresh_pair_sessions": integer(row, "fresh_pair_session_count"),
            "mean_delta_net_pj": number(row, "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element"),
            "sample_std_delta_net_pj": number(row, "sample_std_delta_net_pJ_per_logical_output_element"),
        }
        for row in rows
    ]


def image_markdown(figures: dict[str, Any] | None, key: str) -> str:
    if figures is None:
        return ""
    figure_rows = figures.get("figures", [])
    if not isinstance(figure_rows, list):
        return ""
    for row in figure_rows:
        if row.get("id") == key and isinstance(row.get("png"), str):
            path = Path(row["png"])
            try:
                relative = os.path.relpath(ROOT / path, ROOT / "docs/results")
            except ValueError:
                relative = row["png"]
            return f"\n\n![{key}]({relative.replace(os.sep, '/')})"
    return ""


def candidate_decision_text(exp: Mapping[str, Any], reduction: Mapping[str, Any]) -> tuple[str, str]:
    """State a coordinate-local action without turning small-n evidence into a broad claim."""
    exp_mean = float(exp["mean_delta_net_pj"])
    exp_low = float(exp["t95_low_delta_net_pj"])
    exp_high = float(exp["t95_high_delta_net_pj"])
    reduction_mean = float(reduction["mean_delta_net_pj"])
    reduction_low = float(reduction["t95_low_delta_net_pj"])
    reduction_high = float(reduction["t95_high_delta_net_pj"])
    exp_text = (
        f"`exp_fp16x2`는 평균 Δ={fmt(exp_mean)} pJ/output, descriptive t95 "
        f"[{fmt(exp_low)}, {fmt(exp_high)}]다. "
    )
    if exp_low <= 0.0 <= exp_high:
        exp_text += "0을 포함하므로 이 좌표에서 energy-saving endpoint 후보로 승격하지 않는다."
    elif exp_high < 0.0:
        exp_text += "모든 descriptive interval이 음수지만, exploratory-selected small-n evidence이므로 broad sweep 대신 별도 endpoint AB/BA test로만 진전한다."
    else:
        exp_text += "관측된 비용 증가 방향이므로 endpoint 또는 CTA/S sweep으로 확대하지 않는다."
    reduction_text = (
        f"`reduction_fp16_scalar`는 평균 Δ={fmt(reduction_mean)} pJ/output, descriptive t95 "
        f"[{fmt(reduction_low)}, {fmt(reduction_high)}]다. "
    )
    if reduction_low > 0.0:
        reduction_text += "이 고정 좌표에서는 개선 후보가 아니라 관측된 비용 증가이므로 endpoint 또는 CTA/S sweep으로 확대하지 않는다."
    elif reduction_low <= 0.0 <= reduction_high:
        reduction_text += "0을 포함하므로 endpoint 또는 CTA/S sweep으로 확대하지 않는다."
    else:
        reduction_text += "음수 방향은 후속 endpoint AB/BA test의 후보일 수 있으나, exploratory-selected small-n evidence를 broad sweep으로 일반화하지 않는다."
    return exp_text, reduction_text


def report_markdown(
    rows: list[dict[str, Any]],
    quality: list[dict[str, str]],
    figures: dict[str, Any] | None,
) -> str:
    by_candidate = {row["candidate_id"]: row for row in rows}
    exp = by_candidate["exp_packed"]
    red = by_candidate["reduction_scalar"]
    exp_decision, reduction_decision = candidate_decision_text(exp, red)
    lines = [
        "# RTX 3090 Softmax targeted AB/BA confirmation (2026-07-27)",
        "",
        "## 기술 요약",
        "",
        "이 보고서는 이전 stage-isolation 탐색에서 선택된 두 contrast만 **새로운 AB/BA fresh CUDA-process session**으로 재확인한다. 각 후보는 AB 3회와 BA 3회, 총 n=6 paired session으로 측정했으며, primary metric은 `net pJ/logical Softmax output element`이다. baseline은 `fp16_io_fp32_all` 즉 **FP16 I/O + FP32-stage baseline**이다.",
        "",
        f"exp packed의 treatment−baseline 평균 Δ는 {fmt(exp['mean_delta_net_pj'])} pJ/output (descriptive t95 [{fmt(exp['t95_low_delta_net_pj'])}, {fmt(exp['t95_high_delta_net_pj'])}]), reduction scalar는 {fmt(red['mean_delta_net_pj'])} pJ/output (descriptive t95 [{fmt(red['t95_low_delta_net_pj'])}, {fmt(red['t95_high_delta_net_pj'])}])이다. 이 구간은 후보를 탐색 결과로 선택한 뒤의 n=6 descriptive summary이며, broad superiority의 확정 검정으로 해석하지 않는다.",
        "",
        "## 두 후보의 fresh paired evidence",
        "",
        "음수 Δ는 같은 fresh session에서 treatment가 baseline보다 낮게 관측된 idle-subtracted NVML GPU/device total-energy를 뜻한다. 각 candidate는 다른 candidate와 합치거나 순위 평균으로 합산하지 않는다.",
        "",
        "| 후보 | baseline | treatment | n | AB / BA | mean Δ pJ/output | descriptive t95 | 음수 / 양수 session |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate_label']} | FP16 I/O + FP32 stages | `{row['treatment_policy']}` | {row['fresh_pair_sessions']} | {row['ab_sessions']} / {row['ba_sessions']} | {fmt(row['mean_delta_net_pj'])} | [{fmt(row['t95_low_delta_net_pj'])}, {fmt(row['t95_high_delta_net_pj'])}] | {row['negative_sessions']} / {row['positive_sessions']} |"
        )
    lines.extend([
        image_markdown(figures, "paired_slopes"),
        "",
        "paired-slope figure는 session 한 개 안의 baseline→treatment 변화를 연결한다. forest/delta figure의 0선과 t95 interval은 sign과 uncertainty를 동시에 보이기 위한 descriptive evidence이며, candidate 선택의 p-value로 사용하지 않는다.",
        image_markdown(figures, "paired_deltas"),
        "",
        "## 이번 run의 설계 결정",
        "",
        f"- {exp_decision}",
        f"- {reduction_decision}",
        "",
        "## 범위와 metric 정의",
        "",
        "RTX 3090 sm86(82-SM device), S=512, grid=16 CTA, CTA당 독립 row 2개, logit scale=4, 13 s role, 1 s idle baseline, 20 s conditioner를 고정했다. grid=16은 full-SM saturation 실험이 아니다. 모든 비교는 complete Softmax forward이며, `net pJ/output = (qualified trace energy − idle power × elapsed) × 1e12 / logical output elements`다. 이는 기존 EX2 Operand-rate ATC의 `pJ/added logical exponent result`와 다른 단위이므로 비교·합산·차감하지 않는다.",
        "",
        "## 순서 효과를 줄인 방법",
        "",
        "각 fresh process는 정확히 두 role만 실행한다. 두 policy의 numerical validation과 calibrated iteration count는 measurement order와 무관한 canonical enum 순서로 먼저 완료하고, 이후 `fp16_io_fp32_all`만 20초 conditioning한다. 그 뒤 unrecorded policy warm-up 없이 AB 또는 BA를 측정한다. AB/BA 3회씩은 각 treatment의 first/second position과 directed predecessor를 균형화한다.",
        image_markdown(figures, "orientation_diagnostic"),
        "",
        "",
        "## 불확실성과 한계",
        "",
        "후보가 기존 exploratory result를 보고 선택됐으므로 이 결과는 두 contrast의 **targeted fresh replication**이다. 추정치와 interval은 exploratory data와 pool하지 않는다. AB/BA는 position/carryover를 줄이지만 온도·board power state·DVFS의 모든 영향을 제거하지 않으며, 온도는 기록 context이지 rejection gate나 causal adjustment가 아니다. 외부 power meter나 fixed-clock condition은 사용하지 않았다.",
        "",
        "exp packed PTX가 `f16x2`라고 해서 sm86에서 한 번의 물리적 two-result MUFU issue나 절반의 energy를 뜻하지 않는다. reduction scalar/packed stage delta를 더해 all-FP16 endpoint energy를 예측할 수도 없다. 이 보고서는 pure SFU/MUFU/ALU 회로 에너지나 다른 GPU, S/CTA에 일반화하지 않는다.",
        "",
        "## 다음 의사결정 단계",
        "",
        "한 후보의 fresh paired interval과 방향이 충분히 일관되면, 다음 단계는 그 policy를 사용한 **end-to-end endpoint** (`fp16_io_fp32_all` vs all-stage endpoint)의 별도 AB/BA test다. 여전히 interval이 넓으면 CTA/S sweep을 늘리기보다 fixed-clock 또는 external-meter 조건을 별도 sensitivity run으로 추가해 variance source를 분리하는 편이 타당하다.",
        "",
        "## 추가 질문",
        "",
        "A100/H100에서 같은 source가 어떤 target-specific PTX/SASS lowering을 보이는가? workload-level numerical tolerance가 더 엄격할 때 FP16 reduction boundary는 유지되는가? external power meter가 board-level trace variance를 줄이는가?",
        "",
        "## 품질 gate",
        "",
        "| check | coverage | result |",
        "|---|---|---|",
    ])
    for row in quality:
        lines.append(f"| {row['check']} | {row['coverage']} | {row['result']} |")
    lines.extend([image_markdown(figures, "quality_context"), ""])
    return "\n".join(line for line in lines if line is not None)


def artifact_payload(
    run_dir: Path,
    analysis: dict[str, Any],
    sass: dict[str, Any],
    summary: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    orientation: list[dict[str, Any]],
    quality: list[dict[str, str]],
) -> dict[str, Any]:
    analysis_dir = run_dir / "analysis"
    analysis_source = {
        "id": "analysis",
        "label": "Fail-closed targeted AB/BA confirmation analysis",
        "path": repo_path(analysis_dir / "analysis.json"),
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT candidate_summary FROM read_json_auto('{repo_path(analysis_dir / 'analysis.json')}');",
            "description": "The report consumes the SHA-bound authoritative arrays embedded in analysis.json. The analyzer validates frozen binary/runner, manifest, raw/trace SHA-256, exact AB/BA balance, canonical conditioning, qualified trace, SMID, numerical and logical-denominator contracts before producing those summaries.",
            "tables_used": [
                repo_path(run_dir / "manifest.json"),
                repo_path(analysis_dir / "analysis.json"),
            ],
            "metric_definitions": [
                "Primary metric = idle-subtracted NVML GPU/device total-energy trace in net pJ per logical Softmax output element.",
                "One fresh CUDA-process pair session is the independent repeat; individual role rows are not pooled.",
            ],
            "filters": [
                "RTX 3090 sm86", "S=512", "grid CTA=16", "2 rows/CTA", "FP16 I/O", "AB=3 BA=3 per candidate", "no exploratory pooling",
            ],
        },
    }
    sass_source = {
        "id": "sass",
        "label": "sm86 frozen confirmation-binary PTX/SASS audit",
        "path": repo_path(run_dir / "sass_audit.json"),
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT * FROM read_json_auto('{repo_path(run_dir / 'sass_audit.json')}');",
            "description": "Static code-path audit for the exact frozen confirmation executable; instruction-path evidence is not a board-energy measurement.",
            "tables_used": [repo_path(run_dir / "sass_audit.json")],
            "metric_definitions": ["Audit binary SHA-256 must equal the measured frozen binary SHA-256."],
            "filters": ["sm86", "complete Softmax", "fixed S=512 / two rows per CTA"],
        },
    }
    sources = [analysis_source, sass_source]
    by_candidate = {row["candidate_id"]: row for row in summary}
    exp_decision, reduction_decision = candidate_decision_text(
        by_candidate["exp_packed"], by_candidate["reduction_scalar"]
    )
    return {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "RTX 3090 Softmax targeted AB/BA confirmation",
            "description": "Two exploratory-selected complete-Softmax implementation contrasts remeasured in six fresh AB/BA pair sessions each.",
            "generatedAt": analysis["generated_at"],
            "sources": sources,
            "charts": [
                {
                    "id": "paired_delta",
                    "title": "Candidate-wise paired mean delta",
                    "subtitle": "Treatment minus FP16-I/O + FP32-stage baseline; n=6 fresh pair sessions per candidate, signed pJ/logical output element.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "How large and in which direction is each candidate's same-session treatment-minus-baseline delta?",
                    "rationale": "A signed bar chart centers the two independent candidate summaries on zero; the paired table retains interval and raw-session context.",
                    "comparisonContext": {"baseline": "same-session fp16_io_fp32_all", "denominator": "one logical Softmax output element", "grain": "mean of six fresh paired deltas", "unit": "net pJ/logical output element"},
                    "dataset": "candidate_summary",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "candidate_label", "type": "ordinal", "label": "Targeted contrast"},
                        "y": {"field": "mean_delta_net_pj", "type": "quantitative", "label": "Mean paired delta", "unit": "pJ/logical output element", "format": "number"},
                        "tooltip": [
                            {"field": "candidate_label", "type": "nominal", "label": "Candidate"},
                            {"field": "mean_delta_net_pj", "type": "quantitative", "label": "Mean Δ", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "t95_low_delta_net_pj", "type": "quantitative", "label": "Descriptive t95 low", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "t95_high_delta_net_pj", "type": "quantitative", "label": "Descriptive t95 high", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "fresh_pair_sessions", "type": "quantitative", "label": "Fresh pairs", "format": "number"},
                        ],
                    },
                    "palette": {"kind": "single-root", "name": "whole-softmax-confirmation"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "none"},
                    "referenceLines": [{"axis": "y", "value": 0, "label": "no observed difference", "color": "neutral", "lineStyle": "solid"}],
                },
                {
                    "id": "order_orientation",
                    "title": "AB versus BA orientation diagnostic",
                    "subtitle": "Each bar summarizes three fresh pair sessions; it is a carryover diagnostic, not an order-effect estimate.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "Do AB and BA sessions show materially different descriptive treatment-minus-baseline directions?",
                    "rationale": "Two order groups per candidate expose the balanced orientation diagnostic without pooling candidates.",
                    "comparisonContext": {"baseline": "same-session fp16_io_fp32_all", "denominator": "one logical Softmax output element", "grain": "three pair sessions per candidate/order", "unit": "net pJ/logical output element"},
                    "dataset": "orientation",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "candidate_label", "type": "ordinal", "label": "Targeted contrast"},
                        "y": {"field": "mean_delta_net_pj", "type": "quantitative", "label": "Mean paired delta", "unit": "pJ/logical output element", "format": "number"},
                        "color": {"field": "session_order", "type": "nominal", "label": "Measurement order"},
                        "tooltip": [
                            {"field": "candidate_label", "type": "nominal", "label": "Candidate"},
                            {"field": "session_order", "type": "nominal", "label": "Order"},
                            {"field": "mean_delta_net_pj", "type": "quantitative", "label": "Mean Δ", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "fresh_pair_sessions", "type": "quantitative", "label": "Fresh pairs", "format": "number"},
                        ],
                    },
                    "palette": {"kind": "hard-two-root", "name": "whole-softmax-confirmation-order"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "bottom"},
                    "referenceLines": [{"axis": "y", "value": 0, "label": "no observed difference", "color": "neutral", "lineStyle": "solid"}],
                },
            ],
            "tables": [
                {
                    "id": "candidate_table", "title": "Candidate paired-summary table",
                    "subtitle": "Each row is a separate six-session targeted replication; descriptive t95 intervals are not a broad selection test.",
                    "dataset": "candidate_summary", "sourceId": "analysis",
                    "defaultSort": {"field": "candidate_label", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [
                        {"field": "candidate_label", "label": "Candidate"}, {"field": "treatment_policy", "label": "Treatment"},
                        {"field": "fresh_pair_sessions", "label": "Fresh pairs", "format": "number"}, {"field": "ab_sessions", "label": "AB", "format": "number"}, {"field": "ba_sessions", "label": "BA", "format": "number"},
                        {"field": "mean_delta_net_pj", "label": "Mean Δ pJ/output", "format": "number"}, {"field": "sample_std_delta_net_pj", "label": "Session SD", "format": "number"},
                        {"field": "t95_low_delta_net_pj", "label": "t95 low", "format": "number"}, {"field": "t95_high_delta_net_pj", "label": "t95 high", "format": "number"},
                        {"field": "negative_sessions", "label": "Negative sessions", "format": "number"}, {"field": "positive_sessions", "label": "Positive sessions", "format": "number"},
                    ],
                },
                {
                    "id": "pair_table", "title": "Fresh-session paired deltas",
                    "subtitle": "One row is one fresh CUDA-process pair; raw role rows are not treated as independent samples.",
                    "dataset": "paired_sessions", "sourceId": "analysis",
                    "defaultSort": {"field": "global_session_index", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [
                        {"field": "candidate_label", "label": "Candidate"}, {"field": "global_session_index", "label": "Run order", "format": "number"}, {"field": "session_order", "label": "AB/BA"},
                        {"field": "baseline_net_pj", "label": "Baseline net pJ/output", "format": "number"}, {"field": "treatment_net_pj", "label": "Treatment net pJ/output", "format": "number"},
                        {"field": "delta_net_pj", "label": "Treatment−baseline Δ", "format": "number", "movement": True}, {"field": "preheat_s", "label": "Conditioning seconds", "format": "number"},
                    ],
                },
                {
                    "id": "quality_table", "title": "Evidence and measurement-quality gates",
                    "subtitle": "Temperature is retained as context rather than a causal adjustment or hard rejection gate.",
                    "dataset": "quality", "sourceId": "analysis",
                    "defaultSort": {"field": "check", "direction": "asc"}, "density": "spacious", "layout": "full",
                    "columns": [{"field": "check", "label": "Check"}, {"field": "coverage", "label": "Coverage"}, {"field": "result", "label": "Result"}, {"field": "meaning", "label": "Meaning"}],
                },
            ],
            "blocks": [
                {"id": "title", "type": "markdown", "body": "# RTX 3090 Softmax targeted AB/BA confirmation"},
                {"id": "technical_summary", "type": "markdown", "sourceId": "analysis", "body": "## 기술 요약\n\n**이 run은 exploratory stage-isolation에서 선택된 exp packed와 reduction scalar 두 complete-Softmax contrast의 fresh targeted replication이다.** 각 candidate는 AB 3회와 BA 3회, n=6 fresh CUDA-process paired session으로 측정했다. primary unit은 `net pJ/logical Softmax output element`이며, individual role 24개나 이전 exploratory result와 pool하지 않는다."},
                {"id": "finding_intro", "type": "markdown", "sourceId": "analysis", "body": "## 두 candidate의 paired evidence\n\n음수 Δ는 같은 session에서 treatment가 FP16 I/O + FP32-stage baseline보다 낮게 관측된 net pJ/output을 뜻한다. 아래 bar는 두 independent candidate의 mean paired delta만 보여 주며, descriptive t95와 raw pair evidence는 표에서 함께 확인한다."},
                {"id": "paired_delta_block", "type": "chart", "chartId": "paired_delta"},
                {"id": "candidate_table_block", "type": "table", "tableId": "candidate_table"},
                {"id": "orientation_intro", "type": "markdown", "sourceId": "analysis", "body": "## AB/BA balance는 순서효과를 진단하기 위한 장치다\n\n각 candidate에서 AB와 BA를 세 번씩 실행해 first/second position과 directed predecessor를 균형화했다. order별 bar는 carryover diagnostic일 뿐, small-n order effect의 causal estimate나 post-hoc selection rule이 아니다."},
                {"id": "orientation_block", "type": "chart", "chartId": "order_orientation"},
                {"id": "pair_table_block", "type": "table", "tableId": "pair_table"},
                {"id": "scope", "type": "markdown", "sourceId": "analysis", "body": "## Scope, data, and metric definition\n\nRTX 3090 sm86 is an 82-SM device, but this fixed grid uses 16 CTA and is not a full-SM-saturation experiment. S=512, two independent rows/CTA, logit scale=4, ~13 s role and 20 s baseline conditioner are fixed. `net pJ/output = (qualified trace energy − idle power × elapsed) × 1e12 / logical output elements`. This is complete Softmax forward, not the older EX2 Operand-rate ATC denominator."},
                {"id": "method", "type": "markdown", "sourceId": "analysis", "body": "## Canonical preparation and common conditioning\n\nWithin each fresh process, validation and all calibration happen in canonical policy-enum order before a fixed 20 s `fp16_io_fp32_all` conditioner. There is no unrecorded policy warm-up. Only then does the untouched two-role AB or BA schedule run, with the same 1 s idle baseline before each role."},
                {"id": "quality_intro", "type": "markdown", "sourceId": "analysis", "body": "## Trace, placement, numerical, and static-code evidence\n\nAll 24 roles passed qualified Theil-Sen trace, SMID placement, logical denominator, and FP64-reference numerical gates. The manifest binds the frozen executable, runner, raw/trace SHA-256, and a passing sm86 SASS audit for that exact binary."},
                {"id": "quality_table_block", "type": "table", "tableId": "quality_table"},
                {"id": "limitations", "type": "markdown", "body": "## What this result does not establish\n\nCandidate choice came from exploratory evidence, so the intervals are descriptive targeted-replication summaries, not a broad generalization or pure unit-energy measurement. AB/BA reduces a documented order problem but does not remove all DVFS, temperature, or device-state variation. The result does not transfer automatically to other S/CTA coordinates or V100/A100/H100; stage deltas are not additive all-FP16 endpoint predictions."},
                {"id": "next_steps", "type": "markdown", "body": "## Recommended next steps\n\n" + exp_decision + "\n\n" + reduction_decision + "\n\nIf the exp contrast must be resolved, use a separate fixed-clock or external-meter sensitivity run at this same coordinate before increasing a broad CTA/S sweep."},
                {"id": "questions", "type": "markdown", "body": "## Further questions\n\nDoes target-specific lowering change on A100/H100? Does a workload-specific numerical tolerance preserve the candidate boundary? Does an external power meter materially reduce board-level trace variance?"},
            ],
        },
        "snapshot": {"version": 1, "generatedAt": analysis["generated_at"], "status": "ready", "datasets": {"candidate_summary": summary, "paired_sessions": pairs, "orientation": orientation, "quality": quality}},
        "sources": sources,
    }


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/results")
    parser.add_argument("--figure-manifest", type=Path, default=None)
    parser.add_argument("--portable-builder", type=Path,
                        default=DEFAULT_PLUGIN_ROOT / "skills/build-report/scripts/deliver_portable_artifact.mjs")
    parser.add_argument("--skip-package", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = args.out_dir.resolve()
    figure_manifest = args.figure_manifest.resolve() if args.figure_manifest else None
    analysis, _manifest, sass, raw_summary, raw_pairs, raw_orientation, quality, figures = load_evidence(run_dir, figure_manifest)
    summary = friendly_summary(raw_summary)
    pairs = friendly_pairs(raw_pairs)
    orientation = friendly_orientation(raw_orientation)
    tag = str(analysis["manifest"]["run_tag"])
    prefix = f"rtx3090_softmax_whole_precision_targeted_confirmation_{tag}"
    markdown = report_markdown(summary, quality, figures)
    artifact = artifact_payload(run_dir, analysis, sass, summary, pairs, orientation, quality)
    markdown_path = out_dir / f"{prefix}_analysis_ko.md"
    artifact_path = out_dir / f"{prefix}_artifact.json"
    html_path = out_dir / f"{prefix}_report.html"
    qa_path = out_dir / f"{prefix}_report_qa.md"
    write_text(markdown_path, markdown.rstrip() + "\n")
    write_text(artifact_path, json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    receipt: dict[str, Any] | None = None
    if not args.skip_package:
        if not args.portable_builder.is_file():
            raise ValueError(f"portable report builder is missing: {args.portable_builder}")
        result = subprocess.run(
            ["node", str(args.portable_builder), "--input", str(artifact_path), "--output", str(html_path)],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise ValueError("portable report packaging failed:\n" + result.stdout + result.stderr)
        receipt = json.loads(result.stdout.strip().splitlines()[-1])
        require(receipt.get("ok") is True, "portable report receipt is not OK")
        require(receipt.get("html") == str(html_path), "portable report receipt path mismatch")
        qa = ["# Targeted confirmation report QA", "", "```json", json.dumps(receipt, ensure_ascii=False, indent=2), "```", ""]
        if receipt.get("stages", {}).get("verification") == "structural_only":
            qa.extend(["Chromium이 설치되어 있지 않아 portable HTML의 payload/semantic fallback 구조 검증만 수행됐다. 차트 SVG와 browser-layout 검증은 수행되지 않았다.", ""])
        write_text(qa_path, "\n".join(qa))
    print("report_source_status=pass")
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
