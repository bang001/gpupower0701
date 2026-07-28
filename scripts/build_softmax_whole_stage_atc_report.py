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
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import plot_softmax_whole_stage_atc as plotter


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "softmax_whole_stage_atc_report_v1"
EXPLAINER_SCHEMA = "softmax_whole_stage_atc_generated_explainer_v1"
REQUIRED_EXPLAINER_QA_CHECKS = frozenset(
    {
        "control_and_treatment_both_active",
        "probe_off_on_distinction_visible",
        "ctc_and_tct_brackets_visible",
        "interpolated_control_star_visible",
        "power_height_and_energy_area_distinguished",
        "negative_atc_not_labeled_negative_energy",
        "korean_text_legible_at_original_resolution",
        "no_clipping_or_watermark",
    }
)
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


def require_image_base_directory_match(
    normalized_base_url: str | None,
    local_directory: Path,
) -> None:
    if normalized_base_url is None:
        return
    try:
        relative_directory = local_directory.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return
    path_parts = [
        part for part in urlsplit(normalized_base_url).path.split("/") if part
    ]
    require(
        tuple(path_parts[3:]) == relative_directory.parts,
        "image base URL directory does not match the local repository asset directory",
    )


def png_metadata(path: Path) -> tuple[int, int, str]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ReportError(f"cannot inspect PNG {path}: {error}") from error
    require(
        len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n",
        f"generated explainer is not a valid PNG: {path}",
    )
    offset = 8
    chunk_index = 0
    width = height = bit_depth = color_type = 0
    interlace = -1
    idat = bytearray()
    saw_ihdr = False
    saw_iend = False
    while offset < len(data):
        require(
            offset + 12 <= len(data),
            f"generated explainer PNG has a truncated chunk header: {path}",
        )
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        require(
            crc_end <= len(data),
            f"generated explainer PNG has a truncated {kind!r} chunk: {path}",
        )
        payload = data[payload_start:payload_end]
        recorded_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        require(
            recorded_crc == (zlib.crc32(kind + payload) & 0xFFFFFFFF),
            f"generated explainer PNG chunk CRC mismatch: {kind!r}",
        )
        if chunk_index == 0:
            require(
                kind == b"IHDR" and length == 13,
                "generated explainer PNG must begin with a 13-byte IHDR",
            )
        if kind == b"IHDR":
            require(not saw_ihdr, "generated explainer PNG has duplicate IHDR")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", payload)
            require(
                compression == 0 and filter_method == 0 and interlace == 0,
                "generated explainer PNG uses unsupported encoding options",
            )
            saw_ihdr = True
        elif kind == b"IDAT":
            require(saw_ihdr and not saw_iend, "generated explainer PNG IDAT order is invalid")
            idat.extend(payload)
        elif kind == b"IEND":
            require(
                saw_ihdr and idat and length == 0 and not saw_iend,
                "generated explainer PNG IEND is invalid",
            )
            saw_iend = True
            require(
                crc_end == len(data),
                "generated explainer PNG has trailing bytes after IEND",
            )
        offset = crc_end
        chunk_index += 1
    require(
        saw_ihdr and saw_iend and idat,
        "generated explainer PNG is missing IHDR, IDAT, or IEND",
    )
    require(
        width > 0 and height > 0 and bit_depth == 8 and color_type == 2,
        "generated explainer must be a non-empty 8-bit RGB PNG",
    )
    require(
        width * height <= 100_000_000,
        "generated explainer PNG dimensions exceed the validation limit",
    )
    expected_scanline_bytes = height * (1 + width * 3)
    try:
        pixels = zlib.decompress(bytes(idat))
    except zlib.error as error:
        raise ReportError(
            f"generated explainer PNG IDAT stream cannot be decoded: {error}"
        ) from error
    require(
        len(pixels) == expected_scanline_bytes,
        "generated explainer PNG decoded byte count is inconsistent with IHDR",
    )
    row_stride = 1 + width * 3
    require(
        all(pixels[row * row_stride] <= 4 for row in range(height)),
        "generated explainer PNG contains an invalid scanline filter",
    )
    return width, height, "RGB"


def load_explainer_metadata(
    metadata_path: Path,
) -> tuple[dict[str, Any], Path]:
    payload = read_json(metadata_path)
    require(
        payload.get("schema_version") == EXPLAINER_SCHEMA,
        "generated explainer metadata schema is not certified",
    )
    require(
        payload.get("status") == "pass"
        and payload.get("asset_role") == "explanatory_not_measurement_evidence",
        "generated explainer metadata is not a passing explanatory asset",
    )
    image = payload.get("image")
    require(isinstance(image, dict), "generated explainer image binding is missing")
    image_path = resolve_artifact_path(image.get("path", ""))
    require(image_path.is_file(), f"generated explainer image is missing: {image_path}")
    require(
        image_path.suffix.lower() == ".png",
        "generated explainer image must use a .png extension",
    )
    width, height, color_mode = png_metadata(image_path)
    require(
        image.get("sha256") == sha256_file(image_path)
        and image.get("bytes") == image_path.stat().st_size
        and image.get("width_px") == width
        and image.get("height_px") == height
        and image.get("color_mode") == color_mode,
        "generated explainer image binding does not match the current PNG",
    )
    human_qa = payload.get("human_qa")
    require(
        isinstance(human_qa, dict) and human_qa.get("status") == "pass",
        "generated explainer human QA is not pass",
    )
    checks = human_qa.get("checks")
    require(
        isinstance(checks, dict)
        and set(checks) == set(REQUIRED_EXPLAINER_QA_CHECKS)
        and all(value is True for value in checks.values()),
        "generated explainer human QA checks do not match the required contract",
    )
    return payload, image_path


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


def reduction_diagnostic_table(
    cells: list[dict[str, str]],
    matched: list[dict[str, str]],
) -> str:
    ordered = [
        row
        for row in sorted(
            cells,
            key=lambda row: plotter.POLICIES.index(row["policy"]),
        )
        if row["stage"] == "reduction"
    ]
    require(len(ordered) == 3, "reduction diagnostic matrix is incomplete")
    effects_by_policy = {
        policy: [
            effect
            for effect in matched
            if effect.get("stage") == "reduction"
            and effect.get("policy") == policy
        ]
        for policy in plotter.POLICIES
    }
    require(
        all(len(effects) == 6 for effects in effects_by_policy.values()),
        "reduction diagnostic requires six bracket effects per policy",
    )
    lines = [
        "| Implementation | historical mean ATC ΔpJ/output | mean ΔP | mean T elapsed | mean C elapsed | mean T/C | same-ITER gross ΔE/N | diagnostic descriptive t95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        effects = effects_by_policy[row["policy"]]
        treatment_elapsed = sum(
            numeric(effect, "treatment_elapsed_at_contrast_s")
            for effect in effects
        ) / len(effects)
        control_elapsed = sum(
            numeric(effect, "control_elapsed_at_contrast_s")
            for effect in effects
        ) / len(effects)
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
            f"{fmt(treatment_elapsed)} s | "
            f"{fmt(control_elapsed)} s | "
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
    explainer_metadata_path: Path | None = None,
    explainer_payload: dict[str, Any] | None = None,
    explainer_image_path: Path | None = None,
    explainer_image_base_url: str | None = None,
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
    require_image_base_directory_match(
        normalized_image_base_url,
        figures[REQUIRED_FIGURES[0]]["png"].parent,
    )
    explainer_parts = (
        explainer_metadata_path,
        explainer_payload,
        explainer_image_path,
        explainer_image_base_url,
    )
    require(
        all(value is None for value in explainer_parts)
        or all(value is not None for value in explainer_parts),
        "generated explainer metadata, image, and immutable URL must be supplied together",
    )
    normalized_explainer_image_base_url = normalize_image_base_url(
        explainer_image_base_url
    )
    if explainer_image_path is not None:
        require_image_base_directory_match(
            normalized_explainer_image_base_url,
            explainer_image_path.parent,
        )

    def png(identifier: str) -> str:
        return markdown_path(figures[identifier]["png"], report_path)

    def image(identifier: str) -> str:
        if normalized_image_base_url is None:
            return png(identifier)
        return f"{normalized_image_base_url}/{figures[identifier]['png'].name}"

    def svg(identifier: str) -> str:
        return markdown_path(figures[identifier]["svg"], report_path)

    def explainer_image() -> str:
        require(
            explainer_image_path is not None,
            "generated explainer image was not configured",
        )
        if normalized_explainer_image_base_url is None:
            return markdown_path(explainer_image_path, report_path)
        return f"{normalized_explainer_image_base_url}/{explainer_image_path.name}"

    source_paths = {
        "run manifest": source_artifact_paths["manifest"],
        "analysis JSON": source_artifact_paths["analysis_json"],
        "matched effects": source_artifact_paths["matched_effects"],
        "session summary": source_artifact_paths["session_summary"],
        "cell summary": source_artifact_paths["cell_summary"],
        "quality gates": source_artifact_paths["quality_gates"],
        "figure manifest": figure_manifest_path,
    }
    if explainer_metadata_path is not None and explainer_image_path is not None:
        source_paths["ATC generated explainer metadata"] = explainer_metadata_path
        source_paths["ATC generated explainer PNG"] = explainer_image_path
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
        + (
            ""
            if explainer_metadata_path is None
            else " --explainer-metadata "
            f"{shlex.quote(repo_path(explainer_metadata_path))}"
            " --explainer-image-base-url "
            f"{shlex.quote(str(normalized_explainer_image_base_url))}"
        )
        + " --out "
        f"{shlex.quote(repo_path(report_path))}"
    )

    reduction_by_policy = {
        row["policy"]: row for row in cells if row.get("stage") == "reduction"
    }
    require(
        set(reduction_by_policy) == set(plotter.POLICIES),
        "report requires one reduction summary for every policy",
    )
    scalar_reduction = reduction_by_policy["fp16_scalar"]
    reduction_posthoc_elapsed_match = all(
        0.98
        <= numeric(row, "mean_treatment_over_control_elapsed_ratio")
        <= 1.02
        for row in reduction_by_policy.values()
    )
    reduction_posthoc_elapsed_status = (
        "근사 범위 안" if reduction_posthoc_elapsed_match else "근사 범위 밖"
    )
    reduction_posthoc_elapsed_conclusion = (
        "`t_T≈t_C`가 세 구현에서 성립한다."
        if reduction_posthoc_elapsed_match
        else "`t_T≈t_C`가 세 구현에서 성립하지 않는다."
    )
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
    exp_rows = [row for row in cells if row.get("stage") == "exp"]
    require(
        len(exp_rows) == 3,
        "report requires three Exp summaries",
    )
    exp_t95_crossing_count = sum(
        interval_status(row) == "t95 includes 0" for row in exp_rows
    )
    packed_normalization_rows = [
        row
        for row in cells
        if row.get("stage") == "normalization" and row.get("policy") == "fp16x2"
    ]
    require(
        len(packed_normalization_rows) == 1,
        "report requires one packed FP16x2 normalization summary",
    )
    packed_normalization = packed_normalization_rows[0]
    if explainer_image_path is None:
        explainer_lines: list[str] = []
    else:
        assert explainer_metadata_path is not None
        assert explainer_payload is not None
        explainer_lines = [
            "### 그림으로 보는 ATC: power는 높이, energy는 면적이다",
            "",
            "아래 생성형 이미지는 계산 절차를 쉽게 설명하기 위한 **개념도**이며 측정 "
            "그래프가 아니다. 세로 높이는 평균 power, 가로 폭은 runtime, 사각형의 "
            "면적은 energy를 뜻한다. Reduction처럼 treatment가 더 낮은 높이로 더 "
            "오래 실행되면 `P_T−P_C*`는 음수여도 same-work energy contrast는 "
            "양수일 수 있다. 초록 상자의 A와 B는 **서로 다른 두 후속 arm**이며 "
            "두 결과를 더하지 않는다. 정확한 식과 수치는 이 문서의 SHA-bound "
            "CSV/JSON이 기준이다.",
            "",
            f"![Operand-rate ATC 실험 방법 개념도]({explainer_image()})",
            "",
            f"[PNG 파일]({markdown_path(explainer_image_path, report_path)}) · "
            f"[생성·검수 metadata]({markdown_path(explainer_metadata_path, report_path)})",
            "",
            f"> 이미지 역할: `{explainer_payload.get('asset_role')}`. "
            "측정 데이터 도표가 아닌 개념 설명용 그림이며, 인접한 식과 "
            "SHA-bound CSV/JSON을 정량 근거로 사용한다.",
            "",
        ]

    lines = [
        "# RTX 3090 Whole-Softmax stage Operand-rate ATC 보고서",
        "",
        "## 기술 요약",
        "",
        "**Base 검토 결론: active control은 probe OFF/ON의 signed power contrast를 "
        "위한 구조적 대조군으로는 적절하지만, stage의 물리적 에너지 원가를 추정하는 "
        "base로는 충분하지 않다.** 특히 treatment와 control의 runtime이 달라지면 "
        "`(P_T−P_C*)/treatment rate`는 실제 두 role의 energy 차가 아니다. 따라서 "
        "acquisition contract에서 primary로 명명한 Operand-rate ATC는 보존하되, "
        "에너지 질문에서는 **secondary power-behavior diagnostic**으로 재분류한다. "
        "Fixed-work `ΔE_hat/N` 또는 complete-Softmax/stage-replacement endpoint를 "
        "energy-oriented primary로 사용해야 한다. "
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
        "양수라는 부호 자체는 base 타당성 검사가 아니다. Exp의 "
        f"{exp_t95_crossing_count}/3 cell은 descriptive t95가 0을 포함했고, "
        "normalization도 packed FP16x2에서는 "
        f"{signed(numeric(packed_normalization, 'mean_atc_delta_pJ_per_logical_output_element'))} "
        "pJ/output으로 음수였다. Reduction의 큰 음수가 power와 runtime을 분리해서 "
        "보아야 한다는 설계 한계를 가장 선명하게 드러냈다.",
        "",
        "## Operand-rate ATC를 stage의 물리적 에너지 원가와 구분하는 법",
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
        *explainer_lines,
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
        "두 식을 나란히 쓰면 차이가 더 분명하다.",
        "",
        "```text",
        "현재 Operand-rate ATC = P_T×t_T/N − P_C*×t_T/N",
        "C-T-C fixed-work = (E_hat_T − E_hat_C*)/N",
        "T-C-T fixed-work = (E_hat_T* − E_hat_C)/N",
        "E_hat_role = P_hat_trace,role × t_CUDA,role",
        "```",
        "",
        "현재 ATC의 control 항은 outer-control 추정 role energy `E_hat_C*`가 아니라 "
        "보간 power `P_C*`에 treatment 시간 `t_T`를 곱한 투영값이다. 반면 "
        "C-T-C의 `E_hat_C*`는 두 outer control의 추정 role energy를 treatment "
        "시점으로 보간하고, T-C-T의 `E_hat_T*`는 두 outer treatment의 추정 role "
        "energy를 control 시점으로 보간한다. 여기서 `P_hat_trace`는 qualified "
        "cumulative-energy trace의 guarded Theil–Sen slope이며 `t_CUDA`는 CUDA "
        "elapsed다. 직접 joule endpoint를 적분한 값이라고 과장하지 않는다. "
        "`t_T≈t_C`일 때에는 ATC와 fixed-work 값이 우연히 비슷해질 수 있지만, "
        "runtime이 갈라지면 서로 다른 질문에 답한다.",
        "",
        "### Base 검토 결론: 구조 비교에는 적절하지만 물리 에너지 base로는 불충분하다",
        "",
        "| 검토 항목 | 결과 | 의미 |",
        "|---|---|---|",
        "| 같은 kernel symbol, grid/CTA, ITER, I/O, resource와 main output | 통과 | "
        "probe OFF/ON의 구조적 counterfactual은 성립한다. |",
        "| C-T-C와 T-C-T의 시간보간 | 통과 | 선형 drift와 중간 위치 편향을 완화하지만 "
        "서로 다른 runtime·throughput을 같게 만들지는 않는다. |",
        "| Static/NCU instruction delta | 통과 | treatment의 added path가 실제 실행됐다는 "
        "근거이며 power 또는 energy 측정은 아니다. |",
        "| Reduction의 사후 elapsed 근사 진단 (`0.98–1.02`) | "
        f"**{reduction_posthoc_elapsed_status}** | "
        "FP32 `"
        f"{fmt(numeric(reduction_by_policy['fp32'], 'mean_treatment_over_control_elapsed_ratio'))}×`, "
        "scalar FP16 `"
        f"{fmt(numeric(reduction_by_policy['fp16_scalar'], 'mean_treatment_over_control_elapsed_ratio'))}×`, "
        "packed FP16x2 `"
        f"{fmt(numeric(reduction_by_policy['fp16x2'], 'mean_treatment_over_control_elapsed_ratio'))}×`로 "
        f"{reduction_posthoc_elapsed_conclusion} 이 범위는 완료 v2의 원래 "
        "fail-closed gate가 아니다. |",
        "",
        "즉 baseline 실행 자체가 잘못 구성된 것은 아니다. **문제는 그 baseline과 "
        "추정량을 stage energy라는 질문에 사용한 estimand mismatch**다. Exp와 "
        "FP32/scalar normalization은 elapsed 비가 거의 1이어서 ATC와 same-ITER "
        "energy contrast가 비슷하게 보였을 뿐이며, 양수 부호가 이 mismatch를 "
        "검증하거나 해소한 것은 아니다.",
        "",
        "`0.98–1.02`는 2026-07-29 감사에서 ATC와 fixed-work contrast가 가까워질 "
        "조건을 설명하기 위해 추가한 **사후 민감도 기준**이다. 완료 v2의 원래 "
        "quality gate가 아니며, fixed-work energy contrast의 유효 조건도 아니다. "
        "후속 equal-duration arm에서만 사전 gate로 사용할 것을 제안한다.",
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
        "| ATC 결과 | 말할 수 있는 것 | 말하면 안 되는 것 |",
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
        "| **Operand-rate ATC (power diagnostic)** | `(P_T−P_C*)/(N_T/t_T)` | Treatment "
        "처리율로 active-power 차이를 투영 | Active control 대비 power contrast는 "
        "treatment output 하나당 얼마인가? |",
        "| **Idle-subtracted complete-Softmax energy** | 예: "
        "`(E_softmax−P_idle×t_softmax)/N` | Complete workload의 실제 실행시간과 "
        "idle baseline을 사용 | Softmax 전체가 idle 위에서 소비한 energy/output은 "
        "얼마인가? **이번 added-pass acquisition에서 직접 측정한 값이 아니며 ATC로 "
        "복원할 수 없다.** |",
        "| **Same-ITER gross ΔE/N diagnostic** | C-T-C "
        "`(E_hat_T−E_hat_C*)/N`; T-C-T `(E_hat_T*−E_hat_C)/N`; "
        "`E_hat_role=P_hat_trace×t_CUDA` | C와 T 각각의 CUDA runtime을 추정 "
        "role energy에 포함 | 같은 "
        "ITER에서 treatment와 active control의 gross board-energy 차이는 얼마인가? |",
        "",
        "표의 `E_hat_C*`는 두 outer control 각각의 "
        "`E_hat_role=P_hat_trace×t_CUDA`를 treatment midpoint에 보간한 추정 "
        "energy이며, T-C-T에서는 같은 방식의 `E_hat_T*`를 사용한다. "
        "Same-ITER 진단도 idle을 빼지 않으며 treatment의 늘어난 실행시간 동안 반복된 "
        "complete-Softmax 공통 작업까지 포함한다. 에너지 질문에는 ATC보다 적절한 "
        "intervention contrast지만, 그 자체도 순수 added-stage 원가로 재명명하지 않는다. "
        f"실제 scalar FP16 reduction은 ATC가 "
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
        "`P_T−P_C`가 음수였지만, 같은 ITER의 role energy를 비교한 "
        f"diagnostic은 {positive_reduction_same_iter_count}/18 bracket에서 양수였다. "
        "아래 `same-ITER gross ΔE/N`은 각 role의 guarded Theil–Sen trace-power "
        "estimate `P_hat_trace`에 CUDA elapsed를 곱해 `E_hat_role`을 만든 뒤, "
        "orientation별 midpoint 규칙으로 보간해 계산한다. Idle은 사용하지 않는다.",
        "",
        reduction_diagnostic_table(cells, matched),
        "",
        "이 진단은 treatment가 더 오래 실행된다는 사실을 회계에 포함하므로 reduction "
        "ATC 음수가 물리적 에너지 절감을 뜻하지 않음을 보여준다. 다만 complete "
        "Softmax 공통 작업의 추가 runtime까지 포함한 gross board-energy contrast이므로 "
        "순수 reduction stage 원가로 재명명해서도 안 된다. 두 값은 서로 다른 "
        "estimand이므로 합산하지 않는다.",
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
        f"- acquisition contract에 기록된 ATC 단위: `{plotter.METRIC_LABEL}`. "
        "Base 사후검토 뒤 에너지 해석에서는 secondary diagnostic으로 분류한다.",
        "- logical denominator: `grid_blocks × 2 rows/CTA × observed ITER × S`. "
        "FP16x2도 두 scalar output을 각각 세며 별도의 `/2` 보정은 없다.",
        "- C-T-C: middle treatment power에서 두 outer active-control power의 시간보간값을 "
        "빼고 middle treatment logical-output rate로 나눈다.",
        "- T-C-T: 두 outer treatment power와 output rate를 middle 시점으로 보간한 뒤 "
        "middle active-control power를 뺀다.",
        "- session effect: C-T-C와 T-C-T의 signed effect 평균. Cell summary는 "
        "fresh 3-session mean, sample SD, `t(0.975, df=2)` descriptive interval이다.",
        "- non-primary same-ITER diagnostic: 각 role에서 "
        "`E_hat_role = P_hat_trace × t_CUDA`를 계산한다. C-T-C는 "
        "`(E_hat_T−E_hat_C*)×1e12/N_same_ITER`, T-C-T는 "
        "`(E_hat_T*−E_hat_C)×1e12/N_same_ITER`이며 두 orientation을 평균한다. "
        "Idle을 쓰지 않는다. 순수 stage energy는 아니지만 runtime이 다른 fixed-work "
        "intervention의 gross energy 차에는 ATC보다 직접적이다.",
        f"- idle: `{metric.get('idle_usage')}`. 즉 기록은 하지만 ATC numerator에 "
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
        "## 다음 실험은 3개 cell의 두 추정량만 좁게 확인한다",
        "",
        "**상태: proposed v3 / not implemented.** 아래 설계는 완료된 v2의 manifest, "
        "raw data 또는 quality gate를 소급 변경하지 않는다.",
        "",
        "1. 넓은 CTA×S sweep은 열지 않고 scalar FP16의 Exp, Reduction, "
        "Normalization 세 cell만 동일 좌표에서 다시 측정한다.",
        "2. **Arm A — equal-duration power-rate:** C와 T의 ITER를 독립 보정해 각 role을 "
        "약 13 s로 맞추고 elapsed ratio gate를 `0.98–1.02`로 둔다. C-T-C/T-C-T는 "
        "선형 drift 완화용으로 유지하며 ATC는 power-behavior diagnostic으로 보고한다.",
        "3. **Arm B — exact same-work energy:** C와 T에 동일 ITER를 주고 각 role의 "
        "`E_hat_role=P_hat_trace×t_CUDA`로 만든 orientation-specific fixed-work "
        "gross `ΔE_hat/N`을 energy-oriented primary로 보고한다. 충분히 긴 "
        "bracketed idle을 새로 수집할 수 있을 때만 idle-adjusted 값은 sensitivity로 "
        "추가한다.",
        "4. 각 cell은 4개 fresh session으로 한다. Arm 순서는 `A→B` 2회와 `B→A` "
        "2회, bracket 시작 순서는 `C-T-C→T-C-T` 2회와 "
        "`T-C-T→C-T-C` 2회를 2×2로 교차 균형화한다. Preheat는 5 s를 유지한다. "
        "해석이 남을 때만 동일 3-cell/4-session 구성의 fixed-SM-clock sensitivity "
        "cohort를 한 번 추가한다.",
        "5. 원래 목표인 FP32/scalar FP16/packed FP16x2 complete-Softmax 비교는 "
        "각 구현의 고정 logical workload endpoint energy/output으로 판단한다. 한 stage의 "
        "precision 효과는 나머지 I/O·stage를 고정한 stage-replacement endpoint로 판단한다.",
        "6. 이 3-cell 결과가 재현된 뒤에도 좌표 의존성을 확인해야 할 때만 S 또는 CTA "
        "한 축의 끝점 하나를 추가하고, stage×policy×S×CTA 전체 sweep은 열지 않는다.",
        "7. 플랫폼 비교는 각 GPU의 native binary/static audit와 동일 logical denominator를 "
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
    explainer_metadata_path: Path | None = None,
    explainer_image_base_url: str | None = None,
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
    require(
        (explainer_metadata_path is None) == (explainer_image_base_url is None),
        "--explainer-metadata and --explainer-image-base-url must be supplied together",
    )
    if explainer_metadata_path is None:
        explainer_payload = None
        explainer_image_path = None
    else:
        explainer_payload, explainer_image_path = load_explainer_metadata(
            explainer_metadata_path
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
        explainer_metadata_path,
        explainer_payload,
        explainer_image_path,
        explainer_image_base_url,
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
            "## Operand-rate ATC를 stage의 물리적 에너지 원가와 구분하는 법",
            "### 계산식은 active-power 차이를 treatment 처리율로 환산한다",
            "### Base 검토 결론: 구조 비교에는 적절하지만 물리 에너지 base로는 불충분하다",
            "### 왜 added stage의 물리적 에너지 원가가 아닌가",
            "Same-ITER gross ΔE/N diagnostic",
            "stage끼리 합산할 수 없다",
            "## 3×3 결과와 fresh-session 편차",
            "## 음수 ATC와 same-ITER gross board-energy 진단은 서로 다른 질문이다",
            "## 측정 범위와 metric 정의",
            "## 실험 설계와 fail-closed 검증",
            "## 불확실성, 한계, 강건성 범위",
            "## 다음 실험은 3개 cell의 두 추정량만 좁게 확인한다",
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
        require_image_base_directory_match(
            remote_base,
            ROOT / "docs" / "assets" / "report",
        )
        try:
            require_image_base_directory_match(
                remote_base,
                ROOT / "docs" / "assets" / "different-report",
            )
        except ReportError as error:
            require(
                "directory" in str(error),
                "self-test image directory mismatch rejection reason",
            )
        else:
            raise ReportError("self-test accepted a mismatched image asset directory")
        explainer_png = root / "explainer.png"

        def png_chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        explainer_png.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff\xff\xff"))
            + png_chunk(b"IEND", b"")
        )
        explainer_metadata = root / "explainer_metadata.json"
        explainer_record = {
            "schema_version": EXPLAINER_SCHEMA,
            "status": "pass",
            "asset_role": "explanatory_not_measurement_evidence",
            "image": {
                "path": str(explainer_png),
                "sha256": sha256_file(explainer_png),
                "bytes": explainer_png.stat().st_size,
                "width_px": 2,
                "height_px": 1,
                "color_mode": "RGB",
            },
            "human_qa": {
                "status": "pass",
                "checks": {
                    name: True for name in sorted(REQUIRED_EXPLAINER_QA_CHECKS)
                },
            },
            "caveat": "Synthetic explanatory image for report self-test.",
        }
        atomic_write_text(
            explainer_metadata,
            json.dumps(explainer_record, ensure_ascii=False, indent=2) + "\n",
        )
        explainer_remote_base = (
            "https://raw.githubusercontent.com/example/project/"
            "89abcdef0123456789abcdef0123456789abcdef/docs/assets/explainer"
        )
        with_explainer = build_report(
            run_dir,
            None,
            figure_manifest,
            report_path,
            image_base_url=remote_base,
            explainer_metadata_path=explainer_metadata,
            explainer_image_base_url=explainer_remote_base,
        )
        require(
            with_explainer.count("![") == 5
            and with_explainer.count("[PNG 파일](") == 5
            and "### 그림으로 보는 ATC: power는 높이, energy는 면적이다"
            in with_explainer
            and f"]({explainer_remote_base}/explainer.png)" in with_explainer
            and "ATC generated explainer metadata" in with_explainer,
            "self-test generated explainer integration is incomplete",
        )
        truncated_png = root / "truncated.png"
        truncated_png.write_bytes(explainer_png.read_bytes()[:26])
        truncated_record = json.loads(json.dumps(explainer_record))
        truncated_record["image"].update(
            {
                "path": str(truncated_png),
                "sha256": sha256_file(truncated_png),
                "bytes": truncated_png.stat().st_size,
            }
        )
        truncated_metadata = root / "truncated_metadata.json"
        atomic_write_text(
            truncated_metadata,
            json.dumps(truncated_record, ensure_ascii=False, indent=2) + "\n",
        )
        try:
            build_report(
                run_dir,
                None,
                figure_manifest,
                report_path,
                explainer_metadata_path=truncated_metadata,
                explainer_image_base_url=explainer_remote_base,
            )
        except ReportError as error:
            require(
                "truncated" in str(error) or "missing" in str(error),
                "self-test truncated PNG rejection reason",
            )
        else:
            raise ReportError("self-test accepted a truncated generated explainer PNG")
        invalid_explainer_record = json.loads(json.dumps(explainer_record))
        invalid_explainer_record["image"]["sha256"] = "0" * 64
        invalid_explainer_metadata = root / "invalid_explainer_metadata.json"
        atomic_write_text(
            invalid_explainer_metadata,
            json.dumps(invalid_explainer_record, ensure_ascii=False, indent=2) + "\n",
        )
        try:
            build_report(
                run_dir,
                None,
                figure_manifest,
                report_path,
                explainer_metadata_path=invalid_explainer_metadata,
                explainer_image_base_url=explainer_remote_base,
            )
        except ReportError as error:
            require(
                "binding" in str(error),
                "self-test generated explainer rejection reason",
            )
        else:
            raise ReportError(
                "self-test failed to reject tampered generated explainer metadata"
            )
        invalid_qa_record = json.loads(json.dumps(explainer_record))
        invalid_qa_record["human_qa"]["checks"].pop(
            "interpolated_control_star_visible"
        )
        invalid_qa_metadata = root / "invalid_qa_metadata.json"
        atomic_write_text(
            invalid_qa_metadata,
            json.dumps(invalid_qa_record, ensure_ascii=False, indent=2) + "\n",
        )
        try:
            build_report(
                run_dir,
                None,
                figure_manifest,
                report_path,
                explainer_metadata_path=invalid_qa_metadata,
                explainer_image_base_url=explainer_remote_base,
            )
        except ReportError as error:
            require(
                "human QA checks" in str(error),
                "self-test generated explainer QA rejection reason",
            )
        else:
            raise ReportError(
                "self-test accepted incomplete generated explainer human QA"
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
        "four_measured_figures,generated_explainer,dual_path_images,"
        "immutable_url_enforcement,url_directory_binding,truncated_png_rejection,"
        "explainer_hash_rejection,explainer_qa_rejection,figure_hash_rejection"
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
    parser.add_argument(
        "--explainer-metadata",
        type=Path,
        help=(
            "optional passing metadata JSON for a generated explanatory PNG; "
            "requires --explainer-image-base-url"
        ),
    )
    parser.add_argument(
        "--explainer-image-base-url",
        help=(
            "immutable HTTPS directory for the generated explanatory PNG; "
            "requires --explainer-metadata"
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
        image_base_url=args.image_base_url,
        explainer_metadata_path=(
            args.explainer_metadata.resolve() if args.explainer_metadata else None
        ),
        explainer_image_base_url=args.explainer_image_base_url,
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
