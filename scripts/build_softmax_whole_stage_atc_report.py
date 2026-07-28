#!/usr/bin/env python3
"""Build a Korean technical Markdown report for whole-stage Operand-rate ATC.

The report is generated only from a passing analyzer result and a passing,
SHA-bound figure manifest.  Real runs additionally carry a manifest-bound NCU
dynamic-instruction audit; NCU evidence is never presented as energy data.
The report intentionally treats n=3 intervals and all cross-cell comparisons
as descriptive.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import re
import shlex
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import plot_softmax_whole_stage_atc as plotter


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "softmax_whole_stage_atc_report_v1"
REQUIRED_FIGURES = (
    "mean_t95_sessions",
    "stage_policy_heatmap",
    "ctc_vs_tct",
    "position_stability",
)


class ReportError(ValueError):
    """Raised when report evidence is incomplete, stale, or malformed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise ReportError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReportError(f"cannot read JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"JSON root must be an object: {path}")
    return payload


def resolve_artifact_path(value: Any) -> Path:
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def markdown_path(target: Path, report_path: Path) -> str:
    return Path(os.path.relpath(target.resolve(), report_path.parent.resolve())).as_posix()


def normalize_image_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.rstrip("/")
    parsed = urlsplit(normalized)
    require(parsed.scheme == "https", "image base URL must use HTTPS")
    require(
        parsed.netloc == "raw.githubusercontent.com",
        "image base URL must use raw.githubusercontent.com without credentials or a port",
    )
    require(
        not parsed.query and not parsed.fragment,
        "image base URL must not contain a query or fragment",
    )
    require("%" not in parsed.path, "image base URL must not use percent-encoded paths")
    require("//" not in parsed.path, "image base URL path must be canonical")
    path_parts = [part for part in parsed.path.split("/") if part]
    require(
        all(part not in {".", ".."} for part in path_parts),
        "image base URL must not contain dot path segments",
    )
    require(
        len(path_parts) >= 4,
        "image base URL must include owner, repository, commit, and asset directory",
    )
    require(
        re.fullmatch(r"[0-9a-fA-F]{40}", path_parts[2]) is not None,
        "image base URL must pin a full 40-character Git commit SHA",
    )
    return normalized


def numeric(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ReportError(f"{field!r} is not numeric") from error
    require(math.isfinite(value), f"{field!r} is non-finite")
    return value


def integer(row: Mapping[str, Any], field: str) -> int:
    try:
        return int(str(row[field]))
    except (KeyError, TypeError, ValueError) as error:
        raise ReportError(f"{field!r} is not an integer") from error


def load_figure_manifest(
    figure_manifest_path: Path,
    analysis_path: Path,
    run_manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Path]]]:
    payload = read_json(figure_manifest_path)
    require(
        payload.get("schema_version") == plotter.FIGURE_SCHEMA,
        "figure manifest schema is not certified",
    )
    require(payload.get("status") == "pass", "figure manifest status is not pass")
    require(payload.get("metric") == plotter.METRIC_LABEL, "figure metric drifted")
    render_options = payload.get("render_options")
    require(isinstance(render_options, dict), "figure render options are missing")
    render_out_dir = resolve_artifact_path(render_options.get("out_dir", ""))
    render_prefix = str(render_options.get("prefix", ""))
    require(
        render_out_dir == figure_manifest_path.resolve().parent,
        "figure render output directory does not match the manifest location",
    )
    require(
        render_prefix
        and all(character.isalnum() or character in "-_" for character in render_prefix),
        "figure render prefix is invalid",
    )
    analysis_binding = payload.get("analysis")
    require(isinstance(analysis_binding, dict), "figure analysis binding is missing")
    require(
        analysis_binding.get("schema_version") == plotter.ANALYSIS_SCHEMA
        and analysis_binding.get("status") == "pass",
        "figure analysis binding is not a passing certified analysis",
    )
    require(
        resolve_artifact_path(analysis_binding.get("path", ""))
        == analysis_path.resolve(),
        "figure manifest identifies a different analysis.json",
    )
    require(
        resolve_artifact_path(analysis_binding.get("manifest_path", ""))
        == run_manifest_path.resolve(),
        "figure manifest identifies a different run manifest",
    )
    require(
        analysis_binding.get("sha256") == sha256_file(analysis_path),
        "figure manifest does not bind the current analysis.json",
    )
    require(
        analysis_binding.get("manifest_sha256") == sha256_file(run_manifest_path),
        "figure manifest does not bind the current run manifest",
    )
    sources = payload.get("source_artifacts")
    require(isinstance(sources, dict), "figure source_artifacts is missing")
    required_sources = {
        "analysis_json",
        "manifest",
        "matched_effects",
        "session_summary",
        "cell_summary",
        "quality_gates",
    }
    require(required_sources <= set(sources), "figure source_artifacts is incomplete")
    for name in required_sources:
        record = sources[name]
        require(isinstance(record, dict), f"figure source record is invalid: {name}")
        path = resolve_artifact_path(record.get("path", ""))
        require(path.is_file(), f"figure source is missing: {path}")
        require(
            record.get("sha256") == sha256_file(path),
            f"figure source hash mismatch: {name}",
        )
    cardinalities = payload.get("cardinalities")
    require(isinstance(cardinalities, dict), "figure cardinalities is missing")
    require(
        cardinalities.get("measured_roles") == 162
        and cardinalities.get("fresh_session_cells") == 27
        and cardinalities.get("bracket_effects") == 54
        and cardinalities.get("stage_policy_summaries") == 9
        and cardinalities.get("figures") == 4
        and cardinalities.get("rendered_files") == 8,
        "figure manifest cardinalities are incomplete",
    )
    figures = payload.get("figures")
    require(
        isinstance(figures, list) and len(figures) == 4,
        "figure manifest must contain four figures",
    )
    by_id: dict[str, dict[str, Path]] = {}
    for entry in figures:
        require(isinstance(entry, dict), "figure entry is invalid")
        identifier = str(entry.get("id", ""))
        require(identifier in REQUIRED_FIGURES, f"unexpected figure id: {identifier}")
        require(identifier not in by_id, f"duplicate figure id: {identifier}")
        require(
            entry.get("metric") == plotter.METRIC_LABEL
            and entry.get("fresh_sessions_per_cell") == 3,
            f"figure metric/sample contract drifted: {identifier}",
        )
        files = entry.get("files")
        require(isinstance(files, dict) and set(files) == {"png", "svg"},
                f"figure output set is invalid: {identifier}")
        resolved: dict[str, Path] = {}
        for suffix in ("png", "svg"):
            record = files[suffix]
            require(isinstance(record, dict), f"figure file record invalid: {identifier}/{suffix}")
            path = resolve_artifact_path(record.get("path", ""))
            require(path.is_file() and path.suffix == f".{suffix}",
                    f"figure file is missing or has wrong suffix: {path}")
            require(record.get("sha256") == sha256_file(path),
                    f"figure file hash mismatch: {identifier}/{suffix}")
            require(record.get("bytes") == path.stat().st_size and path.stat().st_size > 0,
                    f"figure byte count mismatch: {identifier}/{suffix}")
            resolved[suffix] = path
        by_id[identifier] = resolved
    require(set(by_id) == set(REQUIRED_FIGURES), "required figure set is incomplete")
    return payload, by_id


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:,.{digits}f}"


def signed(value: float, digits: int = 3) -> str:
    return f"{value:+,.{digits}f}"


def interval_status(row: Mapping[str, Any]) -> str:
    low = numeric(row, "descriptive_t95_low_pJ_per_logical_output_element")
    high = numeric(row, "descriptive_t95_high_pJ_per_logical_output_element")
    if low > 0.0:
        return "t95 > 0"
    if high < 0.0:
        return "t95 < 0"
    return "t95 includes 0"


def cell_name(row: Mapping[str, Any]) -> str:
    return (
        f"{plotter.STAGE_LABELS[str(row['stage'])]} · "
        f"{plotter.POLICY_LABELS[str(row['policy'])]}"
    )


def result_table(cells: list[dict[str, str]]) -> str:
    ordered = sorted(
        cells,
        key=lambda row: (
            plotter.STAGES.index(row["stage"]),
            plotter.POLICIES.index(row["policy"]),
        ),
    )
    lines = [
        "| Added stage | Implementation | mean ΔpJ/output | SD | descriptive t95 | positive sessions | mean \\|C-T-C − T-C-T\\| |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        mean = numeric(row, "mean_atc_delta_pJ_per_logical_output_element")
        sd = numeric(row, "sample_sd_atc_delta_pJ_per_logical_output_element")
        low = numeric(row, "descriptive_t95_low_pJ_per_logical_output_element")
        high = numeric(row, "descriptive_t95_high_pJ_per_logical_output_element")
        disagreement = numeric(
            row, "mean_orientation_disagreement_abs_pJ_per_logical_output_element"
        )
        lines.append(
            f"| {plotter.STAGE_LABELS[row['stage']]} | "
            f"{plotter.POLICY_LABELS[row['policy']]} | {signed(mean)} | "
            f"{fmt(sd)} | [{signed(low)}, {signed(high)}] | "
            f"{integer(row, 'positive_session_count')}/3 | {fmt(disagreement)} |"
        )
    return "\n".join(lines)


def reduction_diagnostic_table(cells: list[dict[str, str]]) -> str:
    ordered = [
        row
        for row in sorted(
            cells,
            key=lambda row: plotter.POLICIES.index(row["policy"]),
        )
        if row["stage"] == "reduction"
    ]
    require(len(ordered) == 3, "reduction diagnostic matrix is incomplete")
    lines = [
        "| Implementation | primary mean ATC ΔpJ/output | mean ΔP | mean T/C elapsed | non-primary same-ITER gross ΔE/N | diagnostic descriptive t95 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        diagnostic_mean = numeric(
            row,
            "mean_same_iter_gross_board_energy_contrast_pJ_per_logical_output",
        )
        diagnostic_low = numeric(
            row,
            "descriptive_t95_low_same_iter_gross_board_energy_contrast_pJ_per_logical_output",
        )
        diagnostic_high = numeric(
            row,
            "descriptive_t95_high_same_iter_gross_board_energy_contrast_pJ_per_logical_output",
        )
        lines.append(
            f"| {plotter.POLICY_LABELS[row['policy']]} | "
            f"{signed(numeric(row, 'mean_atc_delta_pJ_per_logical_output_element'))} | "
            f"{signed(numeric(row, 'mean_delta_power_W'))} W | "
            f"{fmt(numeric(row, 'mean_treatment_over_control_elapsed_ratio'))}× | "
            f"{signed(diagnostic_mean)} | "
            f"[{signed(diagnostic_low)}, {signed(diagnostic_high)}] |"
        )
    return "\n".join(lines)


def stage_findings(cells: list[dict[str, str]]) -> list[str]:
    findings: list[str] = []
    for stage in plotter.STAGES:
        rows = [
            row
            for row in cells
            if row["stage"] == stage
        ]
        rows.sort(key=lambda row: plotter.POLICIES.index(row["policy"]))
        values = "; ".join(
            f"{plotter.POLICY_LABELS[row['policy']]} "
            f"{signed(numeric(row, 'mean_atc_delta_pJ_per_logical_output_element'))} "
            f"({interval_status(row)}, positive "
            f"{integer(row, 'positive_session_count')}/3)"
            for row in rows
        )
        findings.append(f"- **{plotter.STAGE_LABELS[stage]}:** {values}.")
    return findings


def thermal_context(sessions: list[dict[str, str]]) -> str:
    values: list[float] = []
    for row in sessions:
        for field in ("temperature_min_C", "temperature_max_C"):
            value = str(row.get(field, ""))
            if value and value != "not_recorded":
                try:
                    parsed = float(value)
                except ValueError:
                    continue
                if math.isfinite(parsed):
                    values.append(parsed)
    if not values:
        return "온도 메타데이터는 analyzer output에 기록되지 않았다."
    return (
        f"기록된 cell 단위 온도 범위의 전체 외곽은 {fmt(min(values), 1)}–"
        f"{fmt(max(values), 1)} °C였다. 이는 문맥 정보이며 보정값이나 "
        "hard rejection gate가 아니다."
    )


def report_markdown(
    report_path: Path,
    run_dir: Path,
    analysis: dict[str, Any],
    manifest: dict[str, Any],
    matched: list[dict[str, str]],
    sessions: list[dict[str, str]],
    cells: list[dict[str, str]],
    quality: list[dict[str, str]],
    source_artifact_paths: Mapping[str, Path],
    figure_manifest_path: Path,
    figure_payload: dict[str, Any],
    figures: dict[str, dict[str, Path]],
    image_base_url: str | None = None,
) -> str:
    means = [
        numeric(row, "mean_atc_delta_pJ_per_logical_output_element") for row in cells
    ]
    lowest = min(cells, key=lambda row: numeric(row, "mean_atc_delta_pJ_per_logical_output_element"))
    highest = max(cells, key=lambda row: numeric(row, "mean_atc_delta_pJ_per_logical_output_element"))
    all_positive = [
        row for row in cells if integer(row, "positive_session_count") == 3
    ]
    all_negative = [
        row for row in cells if integer(row, "positive_session_count") == 0
    ]
    t95_positive = [
        row
        for row in cells
        if numeric(row, "descriptive_t95_low_pJ_per_logical_output_element") > 0.0
    ]
    t95_negative = [
        row
        for row in cells
        if numeric(row, "descriptive_t95_high_pJ_per_logical_output_element") < 0.0
    ]
    t95_crossing = len(cells) - len(t95_positive) - len(t95_negative)
    sign_agreement = sum(
        (
            numeric(row, "ctc_atc_delta_pJ_per_logical_output_element") > 0.0
            and numeric(row, "tct_atc_delta_pJ_per_logical_output_element") > 0.0
        )
        or (
            numeric(row, "ctc_atc_delta_pJ_per_logical_output_element") < 0.0
            and numeric(row, "tct_atc_delta_pJ_per_logical_output_element") < 0.0
        )
        for row in sessions
    )
    disagreement_values = [
        numeric(
            row, "orientation_disagreement_abs_pJ_per_logical_output_element"
        )
        for row in sessions
    ]
    position_ranges = []
    for stage in plotter.STAGES:
        for policy in plotter.POLICIES:
            values = [
                numeric(
                    row,
                    "order_balanced_atc_delta_pJ_per_logical_output_element",
                )
                for row in sessions
                if row["stage"] == stage and row["policy"] == policy
            ]
            require(len(values) == 3, "report position diagnostic cell is incomplete")
            position_ranges.append((max(values) - min(values), stage, policy))
    widest_range, widest_stage, widest_policy = max(position_ranges)
    diagnostic_contract = analysis.get("non_primary_diagnostic")
    require(
        isinstance(diagnostic_contract, dict)
        and diagnostic_contract.get("name")
        == "same_iter_gross_board_energy_contrast_pJ_per_logical_output"
        and diagnostic_contract.get("uses_idle") is False
        and diagnostic_contract.get("replaces_primary") is False,
        "same-ITER non-primary diagnostic contract is missing",
    )
    reduction_effects = [
        row for row in matched if row.get("stage") == "reduction"
    ]
    require(
        len(reduction_effects) == 18,
        "reduction diagnostic requires 18 bracket effects",
    )
    negative_reduction_power_count = sum(
        numeric(row, "delta_power_W") < 0.0 for row in reduction_effects
    )
    positive_reduction_same_iter_count = sum(
        numeric(
            row,
            "same_iter_gross_board_energy_contrast_pJ_per_logical_output",
        )
        > 0.0
        for row in reduction_effects
    )

    coordinate = manifest.get("coordinate", {})
    design = manifest.get("design", {})
    thermal = manifest.get("thermal_contract", {})
    energy = manifest.get("energy_contract", {})
    metric = manifest.get("metric", {})
    placement = manifest.get("placement_contract", {})
    require(
        all(isinstance(value, dict) for value in (coordinate, design, thermal, energy, metric, placement)),
        "report manifest design sections are incomplete",
    )
    run_gate_rows = [row for row in quality if row.get("scope") == "run"]
    quality_table_lines = [
        "| Gate | Status |",
        "|---|---|",
        *[
            f"| `{row['gate']}` | `{row['status']}` |"
            for row in sorted(run_gate_rows, key=lambda row: row["gate"])
        ],
    ]

    normalized_image_base_url = normalize_image_base_url(image_base_url)

    def png(identifier: str) -> str:
        return markdown_path(figures[identifier]["png"], report_path)

    def image(identifier: str) -> str:
        if normalized_image_base_url is None:
            return png(identifier)
        return f"{normalized_image_base_url}/{figures[identifier]['png'].name}"

    def svg(identifier: str) -> str:
        return markdown_path(figures[identifier]["svg"], report_path)

    source_paths = {
        "run manifest": source_artifact_paths["manifest"],
        "analysis JSON": source_artifact_paths["analysis_json"],
        "matched effects": source_artifact_paths["matched_effects"],
        "session summary": source_artifact_paths["session_summary"],
        "cell summary": source_artifact_paths["cell_summary"],
        "quality gates": source_artifact_paths["quality_gates"],
        "figure manifest": figure_manifest_path,
    }
    is_fixture = manifest.get("analysis_test_fixture") is True
    ncu_binding = manifest.get("ncu_audit")
    if is_fixture:
        ncu_evidence_text = (
            "이 synthetic report fixture에서는 NCU binding gate를 명시적으로 우회했다."
        )
    else:
        require(isinstance(ncu_binding, dict), "report NCU audit binding is missing")
        assert isinstance(ncu_binding, dict)
        ncu_audit_path = resolve_artifact_path(ncu_binding.get("path", ""))
        require(
            ncu_binding.get("schema_version")
            == "softmax_whole_stage_atc_ncu_audit_v1"
            and ncu_binding.get("status") == "pass"
            and ncu_binding.get("launch_count") == 18
            and ncu_binding.get("pair_count") == 9
            and ncu_binding.get("energy_usable") is False
            and ncu_audit_path.is_file()
            and ncu_binding.get("sha256") == sha256_file(ncu_audit_path),
            "report NCU audit binding is not a passing hash-bound artifact",
        )
        source_paths["NCU dynamic instruction audit"] = ncu_audit_path
        ncu_evidence_text = (
            "Manifest에 결합된 NCU dynamic instruction audit는 18개 target launch와 "
            "9개 stage×implementation control/treatment pair의 same-symbol 및 "
            "instruction-delta gate를 통과했다. NCU는 instruction evidence일 뿐이며 "
            f"에너지 수치는 `{energy.get('source')}` NVML trace에서만 계산했다."
        )
    source_lines = []
    for label, path in source_paths.items():
        source_lines.append(
            f"- {label}: [`{repo_path(path)}`]({markdown_path(path, report_path)}) "
            f"(SHA-256 `{sha256_file(path)}`)"
        )
    recorded_analysis_dir = source_artifact_paths["analysis_json"].parent.resolve()
    default_analysis_dir = (run_dir / "analysis").resolve()
    analysis_option = (
        ""
        if recorded_analysis_dir == default_analysis_dir
        else f" --analysis-dir {shlex.quote(repo_path(recorded_analysis_dir))}"
    )
    plot_command = (
        "python3 scripts/plot_softmax_whole_stage_atc.py --run-dir "
        f"{shlex.quote(repo_path(run_dir))}{analysis_option} --out-dir "
        f"{shlex.quote(str(figure_payload['render_options']['out_dir']))} --prefix "
        f"{shlex.quote(str(figure_payload['render_options']['prefix']))}"
    )
    report_command = (
        "python3 scripts/build_softmax_whole_stage_atc_report.py --run-dir "
        f"{shlex.quote(repo_path(run_dir))}{analysis_option} --figure-manifest "
        f"{shlex.quote(repo_path(figure_manifest_path))}"
        + (
            ""
            if normalized_image_base_url is None
            else " --image-base-url "
            f"{shlex.quote(normalized_image_base_url)}"
        )
        + " --out "
        f"{shlex.quote(repo_path(report_path))}"
    )

    unresolved = [
        row
        for row in cells
        if interval_status(row) == "t95 includes 0"
        or numeric(
            row, "mean_orientation_disagreement_abs_pJ_per_logical_output_element"
        )
        > abs(numeric(row, "mean_atc_delta_pJ_per_logical_output_element"))
    ]
    unresolved.sort(
        key=lambda row: numeric(
            row, "mean_orientation_disagreement_abs_pJ_per_logical_output_element"
        ),
        reverse=True,
    )
    if unresolved:
        targeted = ", ".join(cell_name(row) for row in unresolved[:3])
        recommendation = (
            f"넓은 CTA×S sweep 전에 불확실성이 큰 `{targeted}`만 같은 좌표에서 "
            "fresh session을 추가하거나 fixed-clock/external-meter sensitivity로 확인한다."
        )
    else:
        recommendation = (
            "현재 좌표에서는 먼저 같은 설계를 한 차례 독립 재현한 뒤, 넓은 sweep 대신 "
            "S 또는 CTA 한 축의 양 끝점 두 곳만 targeted verification으로 추가한다."
        )

    scalar_reduction_rows = [
        row
        for row in cells
        if row.get("stage") == "reduction" and row.get("policy") == "fp16_scalar"
    ]
    require(
        len(scalar_reduction_rows) == 1,
        "report requires one scalar FP16 reduction summary",
    )
    scalar_reduction = scalar_reduction_rows[0]
    fp32_by_stage = {
        row["stage"]: row for row in cells if row.get("policy") == "fp32"
    }
    require(
        set(fp32_by_stage) == set(plotter.STAGES),
        "report requires one FP32 summary for every stage",
    )
    fp32_sum = sum(
        numeric(
            fp32_by_stage[stage],
            "mean_atc_delta_pJ_per_logical_output_element",
        )
        for stage in plotter.STAGES
    )

    lines = [
        "# RTX 3090 Whole-Softmax stage Operand-rate ATC 보고서",
        "",
        "## 기술 요약",
        "",
        "**이 보고서의 primary 결과는 idle-subtracted complete-Softmax energy나 "
        "stage의 물리적 에너지 원가가 아니라, 동일 active-control 대비 treatment의 "
        "signed Operand-rate power projection이다.** 즉 `(P_T-P_C)/treatment "
        "logical-output rate`를 ΔpJ/logical output으로 표시한다. "
        f"Fail-closed 분석은 {analysis['role_count']}개 measured role, "
        f"{analysis['cell_count']}개 fresh-session cell, "
        f"{analysis['orientation_effect_count']}개 bracket effect와 9개 "
        "stage×implementation summary를 모두 통과시켰다.",
        "",
        f"9개 mean은 {signed(min(means))}–{signed(max(means))} "
        "ΔpJ/logical output 범위였다. "
        f"3/3 session이 양수인 cell은 {len(all_positive)}/9, 0/3인 cell은 "
        f"{len(all_negative)}/9였다. descriptive t95가 0보다 큰 cell은 "
        f"{len(t95_positive)}/9, 0보다 작은 cell은 {len(t95_negative)}/9, "
        f"0을 포함한 cell은 {t95_crossing}/9였다. 최저 mean은 "
        f"{cell_name(lowest)} {signed(numeric(lowest, 'mean_atc_delta_pJ_per_logical_output_element'))}, "
        f"최고 mean은 {cell_name(highest)} "
        f"{signed(numeric(highest, 'mean_atc_delta_pJ_per_logical_output_element'))}였다. "
        "이 최저/최고는 이 단일 좌표의 기술적 비교이며 stage 원가의 보편적 순위가 아니다. "
        "특히 음수는 treatment가 control보다 오래 실행되면서 평균 board power가 "
        "낮아진 signed contrast이며, 추가 연산이 음의 물리 에너지를 소비하거나 "
        "Softmax 에너지를 절감했다는 뜻이 아니다.",
        "",
        "## Primary Operand-rate ATC를 stage의 물리적 에너지 원가와 구분하는 법",
        "",
        "### 비교 대상은 idle(유휴 상태)이 아니라 같은 Softmax를 실행하는 "
        "active control(활성 대조군)이다",
        "",
        "- **Active control(활성 대조군, C):** GPU가 쉬는 idle 상태가 아니다. "
        "Treatment와 같은 "
        "kernel symbol, 입력·출력, grid/CTA geometry, ITER 및 resource 계약으로 "
        "complete Softmax를 반복 실행하되, 측정 대상 added-stage pass만 runtime "
        "flag로 끈 실행이다.",
        "- **Treatment(처리군, T):** 동일한 complete-Softmax kernel을 실행하면서, 선택된 "
        "stage의 계산 지점에서 main output과 분리된 redundant exp, reduction(max+sum) "
        "또는 normalization(reciprocal+multiply) probe path를 runtime flag로 켠 "
        "실행이다. Primary output path는 그대로 유지되며 control과 treatment의 main "
        "Softmax output은 bit-identical gate를 통과해야 한다.",
        "",
        "따라서 C와 T 모두 GPU가 실제 작업을 수행한다. 이 비교가 묻는 질문은 "
        "“Softmax 한 번의 절대 에너지는 얼마인가?”가 아니라 다음과 같다.",
        "",
        "> 이미 complete Softmax를 수행 중인 active control과 비교했을 때, "
        "added-stage pass를 켠 treatment의 board power(보드 전체 전력)가 얼마나 "
        "달라졌고, 그 차이를 treatment의 logical-output rate(논리 출력 처리율)로 "
        "나누면 scalar output 하나당 얼마인가?",
        "",
        "### 계산식은 active-power 차이를 treatment 처리율로 환산한다",
        "",
        "C-T-C bracket의 단순화된 표기는 다음과 같다.",
        "",
        "```text",
        "ΔATC = (P_T - P_C*) / R_T × 10^12  [pJ/logical output]",
        "R_T  = N_T / t_T",
        f"N_T  = {coordinate.get('grid_blocks')} CTA × "
        f"{coordinate.get('rows_per_block')} rows/CTA × observed ITER × "
        f"{coordinate.get('softmax_cols')} logical outputs/row",
        "```",
        "",
        "- `P_T`는 qualified NVML total-energy trace에서 얻은 treatment의 board-power "
        "estimate다.",
        "- `P_C*`는 treatment의 시간 위치에 맞추어 두 outer active-control power를 "
        "보간한 값이다. 별표는 단일 control 측정값이 아니라 시간보간 기준값임을 뜻한다.",
        "- `R_T`는 treatment가 초당 생성한 logical Softmax output 수다. 여기서 logical "
        "output은 scalar element 하나이며, packed FP16x2는 두 lane을 각각 세므로 "
        "별도의 `/2` 보정이 없다.",
        "- T-C-T bracket에서는 두 outer treatment의 power와 output rate를 가운데 "
        "control 시점으로 보간한다. 한 fresh session의 effect는 C-T-C와 T-C-T "
        "effect의 평균이다.",
        "",
        "`W = J/s`이므로 `W ÷ (logical output/s) = J/logical output`이고, "
        "`10^12`를 곱해 pJ/logical output으로 표시한다. 그러나 단위가 에너지/원소라고 "
        "해서 실제 role energy를 직접 뺀 값은 아니다. C-T-C 식은 다음처럼 쓸 수 있다.",
        "",
        "```text",
        "(P_T - P_C*) / (N_T/t_T) = (P_T - P_C*) × t_T / N_T",
        "```",
        "",
        "즉 관측된 active-power 차이가 treatment 실행시간 동안 유지된다고 놓고 "
        "treatment 처리량에 배분한 값이다. 실제 control의 `P_C × t_C`를 treatment의 "
        "`P_T × t_T`에서 빼는 계산이 아니므로 **power projection**이라고 부른다. "
        "`signed`는 절댓값을 취하지 않고 `P_T−P_C*`의 방향을 그대로 보존한다는 뜻이다.",
        "",
        "### 왜 added stage의 물리적 에너지 원가가 아닌가",
        "",
        "Active-control 차분은 두 실행의 공통 complete-Softmax board-power 성분을 "
        "상당 부분 상쇄하여 added pass에 민감한 contrast를 만들려는 설계다. 이 상쇄가 "
        "공통 작업의 물리적 에너지를 완전히 제거했음을 보장하지는 않는다. 또한 added "
        "stage에 속한 회로나 명령만 별도 전력계로 계측한 것이 아니므로 다음 효과가 "
        "분자에 함께 결합될 수 있다.",
        "",
        "- NVML 수치는 GPU core만이 아니라 장치 전체의 board-level power다.",
        "- Added pass는 명령 스케줄, memory traffic, synchronization, resource "
        "contention, clock/power state와 전체 runtime을 함께 바꿀 수 있다.",
        "- 원래 complete Softmax의 해당 stage는 그대로 남아 있고, 선택된 stage 계산 "
        "지점에서 main output과 분리된 redundant probe가 활성화된다. 원래 stage를 "
        "제거하거나 다른 precision stage로 교체한 endpoint 비교가 아니다.",
        "- 공통 작업의 상쇄는 active-control 비교가 confounding을 줄이는 방식이지, "
        "complete Softmax를 서로 독립적인 stage별 joule 항으로 정확히 분해했다는 "
        "보장이 아니다.",
        "",
        "따라서 이 수치는 **이 GPU·이 geometry·이 처리율에서 added pass를 켰을 때의 "
        "board-power contrast**로는 읽을 수 있지만, 다른 실행에도 그대로 적용되는 "
        "opcode 에너지나 stage 고유의 보편적 pJ/element 계수로 읽을 수 없다.",
        "",
        "### 부호는 물리적 stage energy의 부호가 아니라 active-power contrast의 부호다",
        "",
        "| Primary 결과 | 말할 수 있는 것 | 말하면 안 되는 것 |",
        "|---|---|---|",
        "| 양수 | Treatment의 active board power가 대응 control보다 높았고, 이를 "
        "treatment rate로 환산한 값이 양수다. | Added stage가 그만큼의 독립적인 "
        "물리 에너지를 소비했다. |",
        "| 음수 | Treatment의 active board power가 대응 control보다 낮았다. | GPU가 "
        "에너지를 만들었다, added stage가 음의 에너지를 소비했다, 또는 complete "
        "Softmax 에너지가 절감됐다. |",
        "| 0에 가깝거나 t95가 0을 포함 | 관측된 active-power contrast가 작거나 "
        "fresh-session 방향이 불확실하다. | 해당 stage의 물리적 에너지 비용이 0이다. |",
        "",
        "Treatment는 평균 board power가 더 낮더라도 더 오래 실행될 수 있다. 그러면 "
        "signed Operand-rate ATC는 음수지만 같은 수의 output을 처리하는 총 board "
        "energy는 더 클 수 있다. 이 때문에 음수 값을 ‘에너지 절감량’으로 바꾸어 읽을 "
        "수 없다.",
        "",
        "### 같은 pJ/output 표기라도 추정 대상(estimand)이 다르며 stage끼리 합산할 수 없다",
        "",
        "| 지표 | 계산의 핵심 | 실행시간을 다루는 방식 | 대답하는 질문 |",
        "|---|---|---|---|",
        "| **Primary Operand-rate ATC** | `(P_T−P_C*)/(N_T/t_T)` | Treatment "
        "처리율로 active-power 차이를 투영 | Active control 대비 power contrast는 "
        "treatment output 하나당 얼마인가? |",
        "| **Idle-subtracted complete-Softmax energy** | 예: "
        "`(E_softmax−P_idle×t_softmax)/N` | Complete workload의 실제 실행시간과 "
        "idle baseline을 사용 | Softmax 전체가 idle 위에서 소비한 energy/output은 "
        "얼마인가? **이번 primary estimand가 아니며 ATC 값으로 복원할 수 없다.** |",
        "| **Same-ITER gross ΔE/N diagnostic** | `(E_T−E_C*)/N`, "
        "`E_role=P_role×t_role` | C와 T 각각의 실제 runtime을 energy에 포함 | 같은 "
        "ITER에서 treatment와 active control의 gross board-energy 차이는 얼마인가? |",
        "",
        "표의 `E_C*`는 두 outer control 각각의 `E_role=P_role×t_role`을 treatment "
        "midpoint에 보간한 energy이며, T-C-T에서는 같은 방식의 `E_T*`를 사용한다. "
        "Same-ITER 진단도 idle을 빼지 않으며 treatment의 늘어난 실행시간 동안 반복된 "
        "complete-Softmax 공통 작업까지 포함한다. 따라서 primary를 대체하지 않고, "
        "그 자체도 순수 added-stage 원가로 재명명하지 않는다. "
        f"실제 scalar FP16 reduction은 primary가 "
        f"{signed(numeric(scalar_reduction, 'mean_atc_delta_pJ_per_logical_output_element'))} "
        "pJ/output이지만 treatment/control elapsed 비가 "
        f"{fmt(numeric(scalar_reduction, 'mean_treatment_over_control_elapsed_ratio'), 3)}×이고, "
        "same-ITER gross 진단은 "
        f"{signed(numeric(scalar_reduction, 'mean_same_iter_gross_board_energy_contrast_pJ_per_logical_output'))} "
        "pJ/output이었다. 같은 단위에서 반대 부호가 나온 것은 계산 오류가 아니라 "
        "두 지표가 서로 다른 질문에 답하기 때문이다.",
        "",
        "Stage별 ATC도 각각 별도의 control/treatment 실행, power, runtime 및 처리율에서 "
        "얻은 contrast라 서로 더할 수 없다. 예를 들어 FP32의 Exp "
        f"{signed(numeric(fp32_by_stage['exp'], 'mean_atc_delta_pJ_per_logical_output_element'))}, "
        "Reduction "
        f"{signed(numeric(fp32_by_stage['reduction'], 'mean_atc_delta_pJ_per_logical_output_element'))}, "
        "Normalization "
        f"{signed(numeric(fp32_by_stage['normalization'], 'mean_atc_delta_pJ_per_logical_output_element'))}을 "
        f"산술적으로 더한 {signed(fp32_sum)} pJ/output은 complete-Softmax 절대 "
        "에너지, 세 stage의 물리 원가 합, 실제 fused treatment의 에너지 중 어느 것도 "
        "나타내지 않는다.",
        "",
        "## 3×3 결과와 fresh-session 편차",
        "",
        "아래 도표에서 채운 marker는 fresh 3-session mean과 descriptive t95이고, "
        "빈 marker 1–3은 독립 CUDA process session이다. t95는 n=3의 기술적 "
        "불확실성 표시이며 다중비교 보정된 추론 구간이 아니다.",
        (
            "본문 그림은 저장소 상대경로로 렌더링하며 각 그림 아래에 PNG와 SVG "
            "원본 링크를 함께 둔다."
            if normalized_image_base_url is None
            else "본문 그림은 위치가 바뀌어도 렌더링되도록 immutable commit의 HTTPS "
            "PNG를 사용한다. 각 그림 아래의 저장소 상대경로 PNG와 SVG는 offline "
            "fallback 및 원본 검증용이다."
        ),
        "",
        f"![3×3 mean, t95, and raw sessions]({image('mean_t95_sessions')})",
        "",
        f"[PNG 파일]({png('mean_t95_sessions')}) · "
        f"[SVG 원본]({svg('mean_t95_sessions')})",
        "",
        *stage_findings(cells),
        "",
        result_table(cells),
        "",
        "## 음수 ATC와 same-ITER gross board-energy 진단은 서로 다른 질문이다",
        "",
        f"Reduction의 {negative_reduction_power_count}/18 bracket에서 "
        "`P_T−P_C`가 음수였지만, 같은 ITER의 role energy를 비교한 비-primary "
        f"diagnostic은 {positive_reduction_same_iter_count}/18 bracket에서 양수였다. "
        "아래 `same-ITER gross ΔE/N`은 각 role의 qualified trace power에 실제 "
        "elapsed를 곱한 뒤 같은 midpoint 규칙으로 role energy를 보간해 계산한다. "
        "Idle은 사용하지 않는다.",
        "",
        reduction_diagnostic_table(cells),
        "",
        "이 진단은 treatment가 더 오래 실행된다는 사실을 회계에 포함하므로 reduction "
        "ATC 음수가 물리적 에너지 절감을 뜻하지 않음을 보여준다. 다만 complete "
        "Softmax 공통 작업의 추가 runtime까지 포함한 gross board-energy contrast이므로 "
        "순수 reduction stage 원가로 재명명해서도 안 된다. Primary Operand-rate ATC를 "
        "대체하거나 두 값을 합산하지 않는다.",
        "",
        "## stage×implementation 행렬은 부호와 크기만 요약한다",
        "",
        "Heatmap은 각 cell의 mean과 3개 session 중 양수 개수를 직접 표시한다. "
        "서로 다른 added stage의 값은 완전한 Softmax의 구성비로 더할 수 없으며, "
        "packed FP16x2도 scalar logical output element 기준이므로 2로 나누지 않는다.",
        "",
        f"![Stage by policy heatmap]({image('stage_policy_heatmap')})",
        "",
        f"[PNG 파일]({png('stage_policy_heatmap')}) · "
        f"[SVG 원본]({svg('stage_policy_heatmap')})",
        "",
        "## C-T-C와 T-C-T는 중간 위치 편향을 서로 반대 방향에서 진단한다",
        "",
        f"27개 fresh-session cell 중 두 bracket의 부호가 일치한 것은 "
        f"{sign_agreement}/27개였다. orientation 간 절대 차이의 범위는 "
        f"{fmt(min(disagreement_values))}–{fmt(max(disagreement_values))} "
        "pJ/output이었다. 대각선에서 멀수록 bracket 방향에 민감했음을 뜻하지만, "
        "그 차이를 별도 causal order effect로 해석하지 않는다.",
        "",
        f"![C-T-C versus T-C-T]({image('ctc_vs_tct')})",
        "",
        f"[PNG 파일]({png('ctc_vs_tct')}) · "
        f"[SVG 원본]({svg('ctc_vs_tct')})",
        "",
        "## cyclic policy position은 안정성 문맥이지 독립 position 실험이 아니다",
        "",
        "ABC/BCA/CAB 순환으로 각 implementation이 first, second, third position에 "
        "한 번씩 배치됐다. 가장 큰 세 position 관측 범위는 "
        f"{plotter.STAGE_LABELS[widest_stage]} · "
        f"{plotter.POLICY_LABELS[widest_policy]}에서 {fmt(widest_range)} pJ/output이었다. "
        "position마다 한 fresh session뿐이므로 이 선은 drift 진단이며 position "
        "효과 추정치가 아니다.",
        "",
        f"![Policy position stability]({image('position_stability')})",
        "",
        f"[PNG 파일]({png('position_stability')}) · "
        f"[SVG 원본]({svg('position_stability')})",
        "",
        "## 측정 범위와 metric 정의",
        "",
        f"- 장치/좌표: RTX 3090, runtime SM {placement.get('runtime_sm_count')}, "
        f"S={coordinate.get('softmax_cols')}, grid={coordinate.get('grid_blocks')} CTA, "
        f"{coordinate.get('threads_per_block')} threads/CTA, "
        f"{coordinate.get('rows_per_block')} rows/CTA.",
        f"- 실험 행렬: added stage 3종 × implementation 3종 × fresh session "
        f"{design.get('fresh_sessions_per_stage')}회 = {design.get('total_cells')} cell.",
        f"- primary 단위: `{plotter.METRIC_LABEL}`.",
        "- logical denominator: `grid_blocks × 2 rows/CTA × observed ITER × S`. "
        "FP16x2도 두 scalar output을 각각 세며 별도의 `/2` 보정은 없다.",
        "- C-T-C: middle treatment power에서 두 outer active-control power의 시간보간값을 "
        "빼고 middle treatment logical-output rate로 나눈다.",
        "- T-C-T: 두 outer treatment power와 output rate를 middle 시점으로 보간한 뒤 "
        "middle active-control power를 뺀다.",
        "- session effect: C-T-C와 T-C-T의 signed effect 평균. Cell summary는 "
        "fresh 3-session mean, sample SD, `t(0.975, df=2)` descriptive interval이다.",
        "- non-primary same-ITER diagnostic: 각 role에서 "
        "`E_role = qualified trace power × elapsed`를 계산하고, 같은 bracket "
        "midpoint 보간 뒤 `(E_T−E_C) × 1e12 / N_same_ITER`로 낸다. Idle을 쓰지 "
        "않으며 primary ATC를 대체하지 않는다.",
        f"- idle: `{metric.get('idle_usage')}`. 즉 기록은 하지만 primary numerator에 "
        "사용하지 않는다.",
        "",
        "## 실험 설계와 fail-closed 검증",
        "",
        "Control과 treatment는 같은 kernel symbol, geometry, ITER, I/O 및 resource "
        "계약을 사용하고, runtime flag만 treatment의 redundant added-stage pass를 "
        "활성화한다. Main Softmax output은 control과 treatment 사이에 bit-identical "
        "gate를 통과해야 한다. 각 stage session은 fresh CUDA process이고 내부 context는 "
        "지속된다.",
        "",
        f"공통 preheat 요청은 {thermal.get('preheat_requested_s')} s이며 actual gate는 "
        f"{thermal.get('preheat_actual_gate_s')} s다. 각 stage에서 policy order는 "
        "ABC/BCA/CAB로 순환하고, 각 cell은 C-T-C 뒤 T-C-T의 여섯 role을 실행한다. "
        f"에너지는 `{energy.get('source')}`를 사용하며 integration은 "
        f"`{energy.get('integration')}`이다. {thermal_context(sessions)}",
        "",
        ncu_evidence_text,
        "",
        "\n".join(quality_table_lines),
        "",
        "## 불확실성, 한계, 강건성 범위",
        "",
        "- 이 값은 board-level active-control contrast다. 순수 opcode 에너지, "
        "complete-Softmax 절대 에너지, 또는 stage별 독립 원가 계수가 아니다.",
        "- n=3/cell이라 SD와 t95가 한 session에 민감하다. t95는 descriptive이며 "
        "9개 cell의 동시 추론이나 일반화 보장을 제공하지 않는다.",
        "- RTX 3090의 S=1024, q50 underfilled grid 한 좌표만 측정했다. V100/A100/H100, "
        "다른 S/CTA, full-SM saturation으로 자동 전이되지 않는다.",
        "- Added pass는 원래 stage를 제거·교체하지 않고, complete-Softmax kernel "
        "내부의 선택된 stage 계산 지점에서 treatment가 활성화하는 redundant probe다. "
        "Probe 결과는 main output이 아니라 live sink로 관측되므로 compiler lowering과 "
        "sink dataflow의 영향도 포함한다.",
        "- 이 공식 acquisition의 입력은 frozen binary 기본값인 logit scale `4.0`, "
        "seed `5573589319906701683`으로 결정론적으로 생성됐다. 당시 command/raw/manifest가 "
        "두 값을 중복 기록하지 않은 provenance 한계가 있으나 frozen binary SHA로 경로는 "
        "동결돼 있다. 후속 runner는 두 값을 CLI와 manifest/raw에 명시한다.",
        "- Same-ITER여도 control과 treatment의 wall time은 같지 않다. 특히 reduction은 "
        "treatment가 더 오래 실행되고 평균 board power가 낮아져 음의 Operand-rate "
        "projection이 생겼다. 따라서 부호를 stage의 실제 에너지 비용 부호로 바꾸어 "
        "읽을 수 없다.",
        "- C-T-C/T-C-T와 cyclic order는 시간 drift를 줄이고 드러내지만 모든 DVFS, "
        "온도, 전원상태 confounding을 제거하지 않는다.",
        "- Static PTX/SASS audit와 NCU dynamic instruction audit는 treatment "
        "code-path와 실제 instruction delta의 frozen-binary 근거다. NCU/SASS "
        "자체가 board power를 측정한 것은 아니며 에너지 결과는 NVML 기반이다.",
        "",
        "## 다음 실험은 불확실한 cell만 좁게 확인한다",
        "",
        f"1. {recommendation}",
        "2. Operand-rate ATC를 primary로 유지하고 이번에 추가한 same-ITER gross "
        "board-energy diagnostic도 계속 별도 표기한다. 어느 쪽도 다른 쪽으로 "
        "재명명하거나 두 값을 합산하지 않는다.",
        "3. 추가 확인에서도 같은 symbol/geometry/ITER와 C-T-C/T-C-T balance를 유지하고 "
        "가능하면 fixed clock 또는 외부 전력계 sensitivity를 추가한다.",
        "4. 한두 targeted 좌표에서 방향이 재현된 뒤에만 S 또는 CTA 한 축을 증분한다. "
        "stage×policy×S×CTA 전체 sweep을 바로 열지 않는다.",
        "5. 플랫폼 비교는 각 GPU의 native binary/static audit와 동일 logical denominator를 "
        "별도로 검증하고, 플랫폼 간 절대 pJ를 clock/thermal 조건 없이 직접 순위화하지 않는다.",
        "",
        "## 남은 질문",
        "",
        "- t95가 0을 포함하거나 orientation disagreement가 mean보다 큰 cell은 fresh "
        "session 추가 시 방향이 유지되는가?",
        "- fixed SM clock 또는 외부 전력계 sensitivity에서 bracket disagreement가 줄어드는가?",
        "- S 또는 CTA 한 축의 두 targeted 끝점에서 implementation 간 방향이 유지되는가?",
        "- A100/H100 native lowering에서도 동일한 added-stage 의미와 live-sink 증거가 유지되는가?",
        "",
        "## 근거 파일과 재현 경로",
        "",
        f"- report schema: `{REPORT_SCHEMA}`",
        f"- figure manifest SHA-256: `{sha256_file(figure_manifest_path)}`",
        f"- run manifest SHA-256: `{analysis['manifest_sha256']}`",
        f"- figure caveat: {figure_payload.get('caveat')}",
        *source_lines,
        "",
        "재생성 명령:",
        "",
        "```bash",
        plot_command,
        report_command,
        "```",
        "",
    ]
    return "\n".join(lines)


def build_report(
    run_dir: Path,
    analysis_dir: Path | None,
    figure_manifest_path: Path,
    report_path: Path,
    image_base_url: str | None = None,
) -> str:
    (
        analysis,
        manifest,
        matched,
        sessions,
        cells,
        quality,
        source_paths,
    ) = plotter.load_evidence(run_dir, analysis_dir)
    figure_payload, figures = load_figure_manifest(
        figure_manifest_path,
        source_paths["analysis_json"],
        source_paths["manifest"],
    )
    return report_markdown(
        report_path,
        run_dir.resolve(),
        analysis,
        manifest,
        matched,
        sessions,
        cells,
        quality,
        source_paths,
        figure_manifest_path.resolve(),
        figure_payload,
        figures,
        image_base_url,
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def self_test() -> None:
    analyzer = importlib.import_module("analyze_softmax_whole_stage_atc")
    with tempfile.TemporaryDirectory(prefix="softmax_whole_stage_atc_report_test_") as tmp:
        root = Path(tmp)
        run_dir, _expected = analyzer.build_synthetic_fixture(root / "fixture")
        analysis = analyzer.analyze_run(run_dir)
        analyzer.write_outputs(analysis, run_dir / "analysis")
        figure_manifest, _payload = plotter.render_figures(
            run_dir, None, root / "figures", "synthetic"
        )
        report_path = root / "report_ko.md"
        first = build_report(run_dir, None, figure_manifest, report_path)
        second = build_report(run_dir, None, figure_manifest, report_path)
        require(first == second, "self-test report generation is not deterministic")
        required_text = (
            "## 기술 요약",
            "## Primary Operand-rate ATC를 stage의 물리적 에너지 원가와 구분하는 법",
            "### 계산식은 active-power 차이를 treatment 처리율로 환산한다",
            "### 왜 added stage의 물리적 에너지 원가가 아닌가",
            "Same-ITER gross ΔE/N diagnostic",
            "stage끼리 합산할 수 없다",
            "## 3×3 결과와 fresh-session 편차",
            "## 음수 ATC와 same-ITER gross board-energy 진단은 서로 다른 질문이다",
            "## 측정 범위와 metric 정의",
            "## 실험 설계와 fail-closed 검증",
            "## 불확실성, 한계, 강건성 범위",
            "## 다음 실험은 불확실한 cell만 좁게 확인한다",
            "## 남은 질문",
            "## 근거 파일과 재현 경로",
            plotter.METRIC_LABEL,
        )
        require(
            all(text in first for text in required_text),
            "self-test report required structure is incomplete",
        )
        require(first.count("![") == 4, "self-test report figure count is not four")
        require(
            first.count("[PNG 파일](") == 4,
            "self-test report PNG fallback count is not four",
        )
        remote_base = (
            "https://raw.githubusercontent.com/example/project/"
            "0123456789abcdef0123456789abcdef01234567/docs/assets/report"
        )
        remote = build_report(
            run_dir,
            None,
            figure_manifest,
            report_path,
            image_base_url=remote_base,
        )
        require(
            remote.count(f"]({remote_base}/") == 4,
            "self-test remote image count is not four",
        )
        require(
            remote.count("[PNG 파일](") == 4,
            "self-test remote report lost local PNG fallbacks",
        )
        try:
            normalize_image_base_url("http://example.invalid/report-assets")
        except ReportError as error:
            require("HTTPS" in str(error), "self-test insecure URL rejection reason")
        else:
            raise ReportError("self-test accepted an insecure image base URL")
        invalid_remote_bases = (
            "https://raw.githubusercontent.com/example/project/main/docs/assets/report",
            "https://example.invalid/example/project/"
            "0123456789abcdef0123456789abcdef01234567/docs/assets/report",
            "https://raw.githubusercontent.com/example/project/"
            "0123456789abcdef0123456789abcdef01234567/docs/%2e%2e/report",
        )
        for invalid_remote_base in invalid_remote_bases:
            try:
                normalize_image_base_url(invalid_remote_base)
            except ReportError:
                pass
            else:
                raise ReportError(
                    "self-test accepted a mutable or non-canonical image base URL"
                )
        atomic_write_text(report_path, first)
        require(report_path.is_file() and report_path.stat().st_size > 0,
                "self-test report file is missing")

        figure_payload = read_json(figure_manifest)
        png_path = resolve_artifact_path(
            figure_payload["figures"][0]["files"]["png"]["path"]
        )
        png_path.write_bytes(png_path.read_bytes() + b"tamper")
        try:
            build_report(run_dir, None, figure_manifest, report_path)
        except ReportError as error:
            require("hash mismatch" in str(error), "self-test figure rejection reason")
        else:
            raise ReportError("self-test failed to reject a tampered figure")
    print(
        "self_test=pass scenarios=deterministic_report,required_sections,"
        "four_figures,dual_path_images,immutable_url_enforcement,"
        "figure_hash_rejection"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--figure-manifest", type=Path)
    parser.add_argument(
        "--image-base-url",
        help=(
            "optional immutable HTTPS directory used for rendered PNGs; local PNG "
            "and SVG links remain as fallbacks"
        ),
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.run_dir is None:
        raise SystemExit("--run-dir is required unless --self-test is used")
    run_dir = args.run_dir.resolve()
    analysis_dir = args.analysis_dir.resolve() if args.analysis_dir else None
    figure_manifest = (
        args.figure_manifest.resolve()
        if args.figure_manifest
        else (analysis_dir or run_dir / "analysis") / "figures" / "figure_manifest.json"
    )
    report_path = (
        args.out.resolve()
        if args.out
        else (analysis_dir or run_dir / "analysis") / "report_ko.md"
    )
    report = build_report(
        run_dir,
        analysis_dir,
        figure_manifest,
        report_path,
        args.image_base_url,
    )
    atomic_write_text(report_path, report.rstrip() + "\n")
    print("report_status=pass")
    print(f"report={report_path}")
    print(f"report_sha256={sha256_file(report_path)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (plotter.EvidenceError, ReportError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        raise SystemExit(2)
