#!/usr/bin/env python3
"""Render SHA-bound figures for the whole-Softmax stage Operand-rate ATC run.

Only a passing fail-closed analyzer output is accepted.  The CSV views are
checked against the authoritative arrays in ``analysis.json`` and that
analysis must bind the current run manifest by SHA-256 before any figure is
written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = "softmax_whole_stage_atc_analysis_v1"
MANIFEST_SCHEMA = "softmax_whole_stage_atc_manifest_v1"
FIGURE_SCHEMA = "softmax_whole_stage_atc_figures_v1"
PRIMARY_METRIC = "active_control_atc_delta_pJ_per_logical_softmax_output_element"
METRIC_LABEL = (
    "Operand-rate ATC ΔpJ/logical Softmax output element "
    "for one added stage pass"
)

STAGES = ("exp", "reduction", "normalization")
POLICIES = ("fp32", "fp16_scalar", "fp16x2")
STAGE_LABELS = {
    "exp": "Exp",
    "reduction": "Max + sum reduction",
    "normalization": "Normalization",
}
POLICY_LABELS = {
    "fp32": "FP32",
    "fp16_scalar": "scalar FP16",
    "fp16x2": "packed FP16x2",
}
POLICY_COLORS = {
    "fp32": "#2563EB",
    "fp16_scalar": "#D97706",
    "fp16x2": "#6B7C32",
}
POLICY_MARKERS = {"fp32": "o", "fp16_scalar": "s", "fp16x2": "^"}
POLICY_CODES = {"fp32": "F", "fp16_scalar": "S", "fp16x2": "P"}
STAGE_MARKERS = {"exp": "o", "reduction": "s", "normalization": "^"}
SESSION_OFFSETS = {1: -0.16, 2: 0.0, 3: 0.16}
INK = "#172033"
MUTED = "#667085"
GRID = "#D9DEE8"
ZERO = "#525866"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.edgecolor": "#98A2B3",
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.hashsalt": "softmax-whole-stage-atc-v1",
    }
)


class EvidenceError(ValueError):
    """Raised when plotting evidence fails a fail-closed contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise EvidenceError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_recorded_path(value: Any, run_dir: Path) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve()
    local = (run_dir / path).resolve()
    if local.exists():
        return local
    return (ROOT / path).resolve()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"JSON root must be an object: {path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            require(bool(fields), f"CSV header is missing: {path}")
            require(len(fields) == len(set(fields)), f"CSV header is duplicated: {path}")
            rows = [dict(row) for row in reader]
    except OSError as error:
        raise EvidenceError(f"cannot read CSV {path}: {error}") from error
    require(bool(rows), f"CSV has no rows: {path}")
    require(all(None not in row for row in rows), f"CSV has malformed rows: {path}")
    return rows


def number(row: Mapping[str, Any], field: str, label: str = "row") -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError(f"{label}: {field!r} is not numeric") from error
    require(math.isfinite(value), f"{label}: {field!r} is non-finite")
    return value


def integer(row: Mapping[str, Any], field: str, label: str = "row") -> int:
    try:
        return int(str(row[field]))
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError(f"{label}: {field!r} is not an integer") from error


def scalar_equal(actual: str, expected: Any, label: str) -> None:
    if isinstance(expected, bool):
        require(
            actual.strip().lower() == ("true" if expected else "false"),
            f"{label}: boolean differs from analysis.json",
        )
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            observed = float(actual)
        except ValueError as error:
            raise EvidenceError(f"{label}: numeric value is malformed") from error
        require(math.isfinite(observed), f"{label}: numeric value is non-finite")
        require(
            math.isclose(observed, float(expected), rel_tol=1.0e-12, abs_tol=1.0e-9),
            f"{label}: {observed!r} != {expected!r}",
        )
        return
    require(actual == str(expected), f"{label}: text differs from analysis.json")


def validate_csv_array(
    rows: list[dict[str, str]],
    expected: Any,
    *,
    identity: Sequence[str],
    label: str,
) -> None:
    require(
        isinstance(expected, list) and all(isinstance(row, dict) for row in expected),
        f"analysis.json {label} array is invalid",
    )
    require(
        len(rows) == len(expected),
        f"{label}: CSV/analysis cardinality mismatch ({len(rows)} != {len(expected)})",
    )
    actual_by_key = {
        tuple(str(row.get(field, "")) for field in identity): row for row in rows
    }
    expected_by_key = {
        tuple(str(row.get(field, "")) for field in identity): row for row in expected
    }
    require(
        len(actual_by_key) == len(rows) == len(expected_by_key),
        f"{label}: identity is empty or duplicated",
    )
    require(
        set(actual_by_key) == set(expected_by_key),
        f"{label}: CSV/analysis identities differ",
    )
    for key, expected_row in expected_by_key.items():
        actual_row = actual_by_key[key]
        require(
            set(actual_row) == set(expected_row),
            f"{label}/{key}: CSV/analysis fields differ",
        )
        for field, expected_value in expected_row.items():
            scalar_equal(actual_row[field], expected_value, f"{label}/{key}/{field}")


def validate_quality_csv(
    rows: list[dict[str, str]], analysis: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    gates = analysis.get("quality_gates")
    sessions = analysis.get("session_effects")
    require(isinstance(gates, dict) and bool(gates), "analysis quality_gates is invalid")
    require(isinstance(sessions, list), "analysis session_effects is invalid")
    require(
        len(rows) == len(gates) + len(sessions),
        "quality_gates CSV/analysis cardinality mismatch",
    )
    run_rows = [row for row in rows if row.get("scope") == "run"]
    cell_rows = [row for row in rows if row.get("scope") == "fresh_session_cell"]
    require(len(run_rows) == len(gates), "quality_gates run-row cardinality mismatch")
    require(len(cell_rows) == len(sessions), "quality_gates cell-row cardinality mismatch")
    observed_gates = {row.get("gate"): row.get("status") for row in run_rows}
    require(len(observed_gates) == len(run_rows), "quality_gates run gate is duplicated")
    require(observed_gates == gates, "quality_gates run rows differ from analysis.json")
    fixture = manifest.get("analysis_test_fixture") is True
    for gate, status in gates.items():
        allowed = status == "pass" or (
            fixture and gate == "static_audit_binding" and status == "test_fixture_bypass"
        )
        require(allowed, f"quality gate is not passing: {gate}={status}")
    expected_cells = {
        (str(row["stage"]), str(row["policy"]), str(row["session_id"])): str(
            row["quality_status"]
        )
        for row in sessions
    }
    observed_cells = {
        (row.get("stage", ""), row.get("policy", ""), row.get("session_id", "")): row.get(
            "status", ""
        )
        for row in cell_rows
    }
    require(
        len(observed_cells) == len(cell_rows) and observed_cells == expected_cells,
        "quality_gates cell rows differ from analysis.json",
    )
    require(
        all(status == "pass" for status in observed_cells.values()),
        "a fresh-session cell quality gate is not pass",
    )


def load_evidence(
    run_dir: Path, analysis_dir: Path | None = None
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, Path],
]:
    run_dir = run_dir.resolve()
    analysis_dir = (analysis_dir or run_dir / "analysis").resolve()
    analysis_path = analysis_dir / "analysis.json"
    manifest_path = run_dir / "manifest.json"
    analysis = read_json(analysis_path)
    manifest = read_json(manifest_path)
    require(
        analysis.get("schema_version") == ANALYSIS_SCHEMA,
        "analysis schema is not certified",
    )
    require(analysis.get("status") == "pass", "analysis status is not pass")
    require(
        analysis.get("primary_metric") == PRIMARY_METRIC,
        "analysis primary metric drifted",
    )
    require(
        analysis.get("primary_uses_idle") is False,
        "analysis incorrectly permits idle in the primary estimator",
    )
    require(
        manifest.get("schema_version") == MANIFEST_SCHEMA,
        "run manifest schema is not certified",
    )
    require(manifest.get("status") == "complete", "run manifest status is not complete")
    recorded_manifest = resolve_recorded_path(analysis.get("manifest_path", ""), run_dir)
    require(
        recorded_manifest == manifest_path.resolve(),
        "analysis manifest path does not identify this run",
    )
    manifest_hash = str(analysis.get("manifest_sha256", ""))
    require(is_sha256(manifest_hash), "analysis manifest SHA-256 is invalid")
    require(
        sha256_file(manifest_path) == manifest_hash,
        "analysis does not bind the current manifest",
    )
    expected_counts = {
        "role_count": 162,
        "cell_count": 27,
        "orientation_effect_count": 54,
        "summary_count": 9,
    }
    for field, expected in expected_counts.items():
        require(
            analysis.get(field) == expected,
            f"analysis {field} is not the complete experiment ({analysis.get(field)!r})",
        )

    paths = {
        "analysis_json": analysis_path,
        "manifest": manifest_path,
        "matched_effects": analysis_dir / "matched_effects.csv",
        "session_summary": analysis_dir / "session_summary.csv",
        "cell_summary": analysis_dir / "cell_summary.csv",
        "quality_gates": analysis_dir / "quality_gates.csv",
    }
    matched = read_csv(paths["matched_effects"])
    sessions = read_csv(paths["session_summary"])
    cells = read_csv(paths["cell_summary"])
    quality = read_csv(paths["quality_gates"])
    validate_csv_array(
        matched,
        analysis.get("orientation_effects"),
        identity=("session_id", "cell_id", "bracket_index"),
        label="matched_effects",
    )
    validate_csv_array(
        sessions,
        analysis.get("session_effects"),
        identity=("session_id", "cell_id"),
        label="session_summary",
    )
    validate_csv_array(
        cells,
        analysis.get("implementation_stage_summary"),
        identity=("stage", "policy"),
        label="cell_summary",
    )
    validate_quality_csv(quality, analysis, manifest)
    require(len(matched) == 54, "matched_effects must contain 54 bracket effects")
    require(len(sessions) == 27, "session_summary must contain 27 fresh-session effects")
    require(len(cells) == 9, "cell_summary must contain nine stage/policy cells")
    require(
        {(row["stage"], row["policy"]) for row in cells}
        == {(stage, policy) for stage in STAGES for policy in POLICIES},
        "cell_summary does not contain the exact 3×3 matrix",
    )
    require(
        {
            (row["stage"], row["policy"], integer(row, "session_index"))
            for row in sessions
        }
        == {
            (stage, policy, session)
            for stage in STAGES
            for policy in POLICIES
            for session in (1, 2, 3)
        },
        "session_summary does not contain the exact 3×3×3 matrix",
    )
    for row in cells:
        require(integer(row, "fresh_session_count") == 3, "cell n is not three")
        require(row.get("quality_status") == "pass", "cell quality status is not pass")
    return analysis, manifest, matched, sessions, cells, quality, paths


def style_axis(axis: plt.Axes, *, grid_axis: str = "y") -> None:
    axis.grid(axis=grid_axis, color=GRID, linewidth=0.8, alpha=0.8, zorder=0)
    axis.spines[["top", "right"]].set_visible(False)
    axis.set_axisbelow(True)


def add_zero_y(axis: plt.Axes) -> None:
    axis.axhline(0.0, color=ZERO, linewidth=1.15, linestyle="--", zorder=1)


def add_figure_heading(figure: plt.Figure, subtitle: str) -> None:
    layout_engine = figure.get_layout_engine()
    if layout_engine is not None:
        layout_engine.set(rect=(0.0, 0.0, 1.0, 0.88))
    figure.suptitle(METRIC_LABEL, fontsize=14, fontweight="semibold", y=0.985)
    figure.text(
        0.5,
        0.935,
        subtitle,
        ha="center",
        va="top",
        color=MUTED,
        fontsize=9.5,
    )


def normalize_svg(source: str) -> str:
    """Normalize cache-sensitive Matplotlib clip-path identifiers."""

    clip_ids = re.findall(r'<clipPath id="([^"]+)">', source)
    require(len(clip_ids) == len(set(clip_ids)), "SVG clip-path IDs are duplicated")
    for index, old_id in enumerate(clip_ids, start=1):
        new_id = f"clip_path_{index:03d}"
        source = source.replace(f'id="{old_id}"', f'id="{new_id}"')
        source = source.replace(f"url(#{old_id})", f"url(#{new_id})")
    unresolved = re.findall(r'clip-path="url\(#([^)]+)\)"', source)
    defined = set(re.findall(r'<clipPath id="([^"]+)">', source))
    require(set(unresolved) <= defined, "SVG contains an unresolved clip-path reference")
    return "\n".join(line.rstrip() for line in source.splitlines()) + "\n"


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg"]
    figure.canvas.draw()
    for path in paths:
        if path.suffix == ".svg":
            metadata = {"Creator": "plot_softmax_whole_stage_atc.py", "Date": None}
        else:
            metadata = {"Software": "plot_softmax_whole_stage_atc.py"}
        figure.savefig(
            path,
            dpi=180,
            bbox_inches="tight",
            facecolor="white",
            metadata=metadata,
        )
        if path.suffix == ".svg":
            source = path.read_text(encoding="utf-8")
            normalized = normalize_svg(source)
            if source != normalized:
                path.write_text(normalized, encoding="utf-8")
    plt.close(figure)
    return paths


def plot_mean_t95_sessions(
    sessions: list[dict[str, str]],
    cells: list[dict[str, str]],
    output_dir: Path,
    prefix: str,
) -> list[Path]:
    summary = {(row["stage"], row["policy"]): row for row in cells}
    figure, axes = plt.subplots(
        1, 3, figsize=(15.5, 5.4), sharey=True, constrained_layout=True
    )
    for axis, stage in zip(axes, STAGES):
        for xpos, policy in enumerate(POLICIES):
            row = summary[(stage, policy)]
            mean = number(row, "mean_atc_delta_pJ_per_logical_output_element")
            low = number(
                row, "descriptive_t95_low_pJ_per_logical_output_element"
            )
            high = number(
                row, "descriptive_t95_high_pJ_per_logical_output_element"
            )
            color = POLICY_COLORS[policy]
            marker = POLICY_MARKERS[policy]
            raw = sorted(
                (
                    item
                    for item in sessions
                    if item["stage"] == stage and item["policy"] == policy
                ),
                key=lambda item: integer(item, "session_index"),
            )
            for session_row in raw:
                session = integer(session_row, "session_index")
                value = number(
                    session_row,
                    "order_balanced_atc_delta_pJ_per_logical_output_element",
                )
                axis.scatter(
                    xpos + SESSION_OFFSETS[session],
                    value,
                    marker=marker,
                    s=54,
                    facecolor="white",
                    edgecolor=color,
                    linewidth=1.45,
                    zorder=3,
                )
                axis.annotate(
                    str(session),
                    (xpos + SESSION_OFFSETS[session], value),
                    xytext=(0, 6),
                    textcoords="offset points",
                    ha="center",
                    color=MUTED,
                    fontsize=7.5,
                )
            axis.errorbar(
                xpos,
                mean,
                yerr=[[mean - low], [high - mean]],
                fmt=marker,
                markersize=8,
                markerfacecolor=color,
                markeredgecolor=INK,
                markeredgewidth=0.8,
                color=INK,
                ecolor=INK,
                capsize=5,
                linewidth=1.7,
                zorder=4,
            )
        add_zero_y(axis)
        style_axis(axis)
        axis.set_title(STAGE_LABELS[stage], pad=10)
        axis.set_xticks(range(3), [POLICY_LABELS[policy] for policy in POLICIES])
        axis.tick_params(axis="x", rotation=18)
    axes[0].set_ylabel("ΔpJ / logical Softmax output element")
    add_figure_heading(
        figure,
        "Filled marker = mean ± descriptive t95; open markers = fresh sessions "
        "1–3 (n=3, interval is descriptive).",
    )
    return save_figure(figure, output_dir, f"{prefix}_mean_t95_sessions")


def plot_heatmap(
    cells: list[dict[str, str]], output_dir: Path, prefix: str
) -> list[Path]:
    by_cell = {(row["stage"], row["policy"]): row for row in cells}
    matrix = [
        [
            number(
                by_cell[(stage, policy)],
                "mean_atc_delta_pJ_per_logical_output_element",
            )
            for policy in POLICIES
        ]
        for stage in STAGES
    ]
    max_abs = max(max(abs(value) for value in row) for row in matrix)
    max_abs = max(max_abs, 1.0e-12)
    cmap = LinearSegmentedColormap.from_list(
        "atc_signed", ("#2563EB", "#F8FAFC", "#D97706")
    )
    figure, axis = plt.subplots(figsize=(9.8, 5.9), constrained_layout=True)
    image = axis.imshow(
        matrix,
        cmap=cmap,
        norm=TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs),
        aspect="auto",
    )
    axis.set_xticks(range(3), [POLICY_LABELS[policy] for policy in POLICIES])
    axis.set_yticks(range(3), [STAGE_LABELS[stage] for stage in STAGES])
    for row_index, stage in enumerate(STAGES):
        for column_index, policy in enumerate(POLICIES):
            cell = by_cell[(stage, policy)]
            value = matrix[row_index][column_index]
            positive = integer(cell, "positive_session_count")
            text_color = "white" if abs(value) > 0.58 * max_abs else INK
            axis.text(
                column_index,
                row_index,
                f"{value:+.3f}\npositive {positive}/3",
                ha="center",
                va="center",
                color=text_color,
                fontsize=10,
                fontweight="semibold",
            )
    colorbar = figure.colorbar(image, ax=axis, shrink=0.82, pad=0.04)
    colorbar.set_label("mean ΔpJ / logical output element")
    axis.set_xlabel("Implementation policy")
    axis.set_ylabel("Added stage pass")
    axis.tick_params(length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)
    add_figure_heading(
        figure,
        "Cell annotation = three-session mean and positive-session count; "
        "signed scale is centered at zero (n=3/cell).",
    )
    return save_figure(figure, output_dir, f"{prefix}_stage_policy_heatmap")


def plot_ctc_tct(
    sessions: list[dict[str, str]], output_dir: Path, prefix: str
) -> list[Path]:
    x_values = [
        number(row, "ctc_atc_delta_pJ_per_logical_output_element")
        for row in sessions
    ]
    y_values = [
        number(row, "tct_atc_delta_pJ_per_logical_output_element")
        for row in sessions
    ]
    limit = max(max(abs(value) for value in x_values + y_values) * 1.12, 1.0)
    figure, axis = plt.subplots(figsize=(8.5, 7.2), constrained_layout=True)
    for row, xvalue, yvalue in zip(sessions, x_values, y_values):
        stage = row["stage"]
        policy = row["policy"]
        axis.scatter(
            xvalue,
            yvalue,
            marker=STAGE_MARKERS[stage],
            s=72,
            facecolor=POLICY_COLORS[policy],
            edgecolor=INK,
            linewidth=0.7,
            alpha=0.88,
            zorder=3,
        )
    axis.axhline(0.0, color=ZERO, linewidth=1.0, linestyle="--", zorder=1)
    axis.axvline(0.0, color=ZERO, linewidth=1.0, linestyle="--", zorder=1)
    axis.plot(
        (-limit, limit),
        (-limit, limit),
        color=INK,
        linewidth=1.1,
        linestyle=":",
        label="C-T-C = T-C-T",
        zorder=1,
    )
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("C-T-C bracket ΔpJ / logical output element")
    axis.set_ylabel("T-C-T bracket ΔpJ / logical output element")
    style_axis(axis, grid_axis="both")
    policy_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=POLICY_COLORS[policy],
            markeredgecolor=INK,
            label=POLICY_LABELS[policy],
        )
        for policy in POLICIES
    ]
    stage_handles = [
        Line2D(
            [0],
            [0],
            marker=STAGE_MARKERS[stage],
            color=INK,
            markerfacecolor="white",
            linestyle="none",
            label=STAGE_LABELS[stage],
        )
        for stage in STAGES
    ]
    diagonal = Line2D([0], [0], color=INK, linestyle=":", label="diagonal agreement")
    axis.legend(
        handles=policy_handles + stage_handles + [diagonal],
        loc="upper left",
        frameon=False,
        ncol=2,
        fontsize=8.5,
    )
    add_figure_heading(
        figure,
        "Each point is one fresh-session cell; color = implementation, marker = "
        "stage. Zero axes and diagonal show sign/agreement context.",
    )
    return save_figure(figure, output_dir, f"{prefix}_ctc_vs_tct")


def plot_position_stability(
    sessions: list[dict[str, str]], output_dir: Path, prefix: str
) -> list[Path]:
    figure, axes = plt.subplots(
        1, 3, figsize=(15.5, 5.4), sharey=True, constrained_layout=True
    )
    for axis, stage in zip(axes, STAGES):
        for policy in POLICIES:
            rows = sorted(
                (
                    row
                    for row in sessions
                    if row["stage"] == stage and row["policy"] == policy
                ),
                key=lambda row: integer(row, "policy_position"),
            )
            positions = [integer(row, "policy_position") + 1 for row in rows]
            values = [
                number(
                    row,
                    "order_balanced_atc_delta_pJ_per_logical_output_element",
                )
                for row in rows
            ]
            axis.plot(
                positions,
                values,
                color=POLICY_COLORS[policy],
                marker=POLICY_MARKERS[policy],
                markerfacecolor="white",
                markeredgewidth=1.4,
                linewidth=1.6,
                markersize=6.5,
                label=POLICY_LABELS[policy],
                zorder=3,
            )
            for row, xpos, value in zip(rows, positions, values):
                vertical_offset = {
                    "fp32": -10,
                    "fp16_scalar": 3,
                    "fp16x2": 8,
                }[policy]
                axis.annotate(
                    f"S{integer(row, 'session_index')}",
                    (xpos, value),
                    xytext=(4, vertical_offset),
                    textcoords="offset points",
                    color=MUTED,
                    fontsize=7.5,
                )
        add_zero_y(axis)
        style_axis(axis)
        axis.set_title(STAGE_LABELS[stage], pad=10)
        axis.set_xticks((1, 2, 3), ("first", "second", "third"))
        axis.set_xlabel("policy position within stage session")
    axes[0].set_ylabel("order-balanced ΔpJ / logical output element")
    axes[-1].legend(frameon=False, loc="best", fontsize=8.5)
    add_figure_heading(
        figure,
        "Each line connects one implementation across cyclic ABC/BCA/CAB positions; "
        "S1–S3 are the three fresh sessions (n=3/cell).",
    )
    return save_figure(figure, output_dir, f"{prefix}_position_stability")


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def figure_entry(
    identifier: str,
    title: str,
    subtitle: str,
    paths: Iterable[Path],
) -> dict[str, Any]:
    by_suffix = {path.suffix.lstrip("."): path for path in paths}
    require(set(by_suffix) == {"png", "svg"}, f"{identifier}: output set is incomplete")
    files: dict[str, Any] = {}
    for suffix in ("png", "svg"):
        path = by_suffix[suffix]
        require(path.is_file() and path.stat().st_size > 0, f"figure is empty: {path}")
        files[suffix] = {
            "path": repo_path(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    return {
        "id": identifier,
        "title": title,
        "subtitle": subtitle,
        "metric": METRIC_LABEL,
        "fresh_sessions_per_cell": 3,
        "files": files,
    }


def render_figures(
    run_dir: Path,
    analysis_dir: Path | None,
    output_dir: Path,
    prefix: str,
) -> tuple[Path, dict[str, Any]]:
    (
        analysis,
        _manifest,
        matched,
        sessions,
        cells,
        _quality,
        source_paths,
    ) = load_evidence(run_dir, analysis_dir)
    entries = [
        figure_entry(
            "mean_t95_sessions",
            "Three-stage × three-policy mean, descriptive t95, and sessions",
            "All nine cells; filled summaries and three open fresh-session markers.",
            plot_mean_t95_sessions(sessions, cells, output_dir, prefix),
        ),
        figure_entry(
            "stage_policy_heatmap",
            "Stage × implementation mean ATC matrix",
            "Signed mean with positive-session count in every cell.",
            plot_heatmap(cells, output_dir, prefix),
        ),
        figure_entry(
            "ctc_vs_tct",
            "C-T-C versus T-C-T bracket agreement",
            "Twenty-seven fresh-session cells with diagonal and zero context.",
            plot_ctc_tct(sessions, output_dir, prefix),
        ),
        figure_entry(
            "position_stability",
            "Fresh-session policy-position stability",
            "Cyclic ABC/BCA/CAB position diagnostic for each stage and policy.",
            plot_position_stability(sessions, output_dir, prefix),
        ),
    ]
    manifest_payload = {
        "schema_version": FIGURE_SCHEMA,
        "status": "pass",
        "metric": METRIC_LABEL,
        "render_options": {
            "out_dir": repo_path(output_dir),
            "prefix": prefix,
        },
        "analysis": {
            "path": repo_path(source_paths["analysis_json"]),
            "sha256": sha256_file(source_paths["analysis_json"]),
            "schema_version": ANALYSIS_SCHEMA,
            "status": "pass",
            "manifest_path": repo_path(source_paths["manifest"]),
            "manifest_sha256": analysis["manifest_sha256"],
        },
        "source_artifacts": {
            name: {
                "path": repo_path(path),
                "sha256": sha256_file(path),
            }
            for name, path in source_paths.items()
        },
        "cardinalities": {
            "measured_roles": analysis["role_count"],
            "fresh_session_cells": len(sessions),
            "bracket_effects": len(matched),
            "stage_policy_summaries": len(cells),
            "figures": len(entries),
            "rendered_files": sum(len(entry["files"]) for entry in entries),
        },
        "chart_map": [
            {
                "id": "mean_t95_sessions",
                "question": "What is each cell's mean, descriptive t95, and raw-session spread?",
                "family": "uncertainty and benchmark",
                "encoding": "stage facets; policy x; ATC y; raw sessions and mean interval",
                "palette": "three restrained policy roots plus marker shapes",
            },
            {
                "id": "stage_policy_heatmap",
                "question": "How do signed cell means compare across the 3×3 matrix?",
                "family": "matrix",
                "encoding": "stage rows; policy columns; signed mean fill and direct labels",
                "palette": "blue–neutral–orange diverging scale centered at zero",
            },
            {
                "id": "ctc_vs_tct",
                "question": "Do the two balanced brackets agree in sign and magnitude?",
                "family": "relationship",
                "encoding": "C-T-C x; T-C-T y; policy color; stage marker",
                "palette": "three restrained policy roots plus stage marker shapes",
            },
            {
                "id": "position_stability",
                "question": "Does the session effect change with policy position?",
                "family": "ordered comparison",
                "encoding": "policy position x; session effect y; stage facets",
                "palette": "three restrained policy roots plus marker shapes",
            },
        ],
        "figures": entries,
        "caveat": (
            "n=3 fresh sessions per stage/policy cell; t95 intervals are "
            "descriptive and no multiple-comparison claim is made."
        ),
    }
    figure_manifest = output_dir / "figure_manifest.json"
    atomic_write_json(figure_manifest, manifest_payload)
    return figure_manifest, manifest_payload


def self_test() -> None:
    analyzer = importlib.import_module("analyze_softmax_whole_stage_atc")
    with tempfile.TemporaryDirectory(prefix="softmax_whole_stage_atc_plot_test_") as tmp:
        root = Path(tmp)
        run_dir, _expected = analyzer.build_synthetic_fixture(root / "fixture")
        analysis = analyzer.analyze_run(run_dir)
        analyzer.write_outputs(analysis, run_dir / "analysis")
        first_manifest, first_payload = render_figures(
            run_dir, None, root / "figures_first", "synthetic"
        )
        second_manifest, second_payload = render_figures(
            run_dir, None, root / "figures_second", "synthetic"
        )
        require(first_manifest.is_file(), "self-test figure manifest is missing")
        require(
            len(first_payload["figures"]) == 4
            and first_payload["cardinalities"]["rendered_files"] == 8,
            "self-test figure output cardinality",
        )
        first_hashes = [
            entry["files"][suffix]["sha256"]
            for entry in first_payload["figures"]
            for suffix in ("png", "svg")
        ]
        second_hashes = [
            entry["files"][suffix]["sha256"]
            for entry in second_payload["figures"]
            for suffix in ("png", "svg")
        ]
        require(first_hashes == second_hashes, "self-test figure rendering is not deterministic")
        require(
            normalize_svg(
                '<svg><g clip-path="url(#p_old_a)"/><defs>'
                '<clipPath id="p_old_a"><path/></clipPath></defs></svg>'
            )
            == normalize_svg(
                '<svg><g clip-path="url(#p_old_b)"/><defs>'
                '<clipPath id="p_old_b"><path/></clipPath></defs></svg>'
            ),
            "self-test SVG clip-path normalization is not deterministic",
        )

        cell_path = run_dir / "analysis" / "cell_summary.csv"
        original = cell_path.read_text(encoding="utf-8")
        lines = original.splitlines()
        fields = lines[0].split(",")
        mean_index = fields.index("mean_atc_delta_pJ_per_logical_output_element")
        values = lines[1].split(",")
        values[mean_index] = str(float(values[mean_index]) + 1.0)
        cell_path.write_text(
            "\n".join([lines[0], ",".join(values), *lines[2:]]) + "\n",
            encoding="utf-8",
        )
        try:
            load_evidence(run_dir)
        except EvidenceError as error:
            require(
                "differs" in str(error) or "!=" in str(error),
                "self-test CSV rejection reason",
            )
        else:
            raise EvidenceError("self-test failed to reject a CSV/JSON mismatch")
        cell_path.write_text(original, encoding="utf-8")

        manifest_path = run_dir / "manifest.json"
        manifest_payload = read_json(manifest_path)
        manifest_payload["status"] = "tampered"
        manifest_path.write_text(json.dumps(manifest_payload) + "\n", encoding="utf-8")
        try:
            load_evidence(run_dir)
        except EvidenceError as error:
            require(
                "manifest status" in str(error) or "bind" in str(error),
                "self-test manifest rejection reason",
            )
        else:
            raise EvidenceError("self-test failed to reject a tampered manifest")
    print(
        "self_test=pass scenarios=render_4x_png_svg,deterministic_hashes,"
        "cache_independent_svg_clip_ids,csv_json_rejection,manifest_rejection"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--prefix", default="rtx3090_softmax_whole_stage_atc")
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
    output_dir = (
        args.out_dir.resolve()
        if args.out_dir
        else (analysis_dir or run_dir / "analysis") / "figures"
    )
    require(
        args.prefix
        and all(character.isalnum() or character in "-_" for character in args.prefix),
        "--prefix may contain only letters, digits, '-' and '_'",
    )
    figure_manifest, payload = render_figures(
        run_dir, analysis_dir, output_dir, args.prefix
    )
    print("figure_status=pass")
    print(f"figures={payload['cardinalities']['figures']}")
    print(f"rendered_files={payload['cardinalities']['rendered_files']}")
    print(f"figure_manifest={figure_manifest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as error:
        print(f"error: {error}", file=os.sys.stderr)
        raise SystemExit(2)
