#!/usr/bin/env python3
"""Render static, SHA-bound figures for the whole-Softmax AB/BA confirmation.

The input is a passing fail-closed analysis.  This script refuses an analysis
whose bound manifest differs from the current run, and cross-checks the CSV
views against the authoritative arrays embedded in ``analysis.json`` before it
draws any chart.  It deliberately shows session-level paired evidence rather
than collapsing the two selected contrasts into a single ranking.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = "softmax_whole_precision_targeted_confirmation_analysis_v1"
FIGURE_SCHEMA = "softmax_whole_precision_targeted_confirmation_figures_v1"
PRIMARY_METRIC = "net_pJ_per_logical_output_element"
T95_N6 = 2.570581835636314

CANDIDATES = (
    ("exp_packed", "exp · packed FP16"),
    ("reduction_scalar", "max+sum reduction · scalar FP16"),
)
LABELS = dict(CANDIDATES)
ORDER_COLOR = {"AB": "#2563eb", "BA": "#d97706"}
MEAN_COLOR = "#111827"


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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"JSON root must be an object: {path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise ValueError(f"cannot read CSV {path}: {error}") from error
    require(bool(rows), f"CSV has no rows: {path}")
    require(all(None not in row for row in rows), f"CSV has malformed rows: {path}")
    return rows


def number(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field!r} is not numeric") from error
    require(math.isfinite(value), f"{field!r} is not finite")
    return value


def integer(row: Mapping[str, Any], field: str) -> int:
    try:
        value = int(str(row[field]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field!r} is not an integer") from error
    return value


def close(left: float, right: float, label: str) -> None:
    require(math.isclose(left, right, rel_tol=1.0e-10, abs_tol=1.0e-8),
            f"analysis/CSV mismatch: {label}: {left} != {right}")


def validate_csv_view(
    rows: list[dict[str, str]],
    expected: object,
    *,
    identity: tuple[str, ...],
    numeric_fields: tuple[str, ...],
    label: str,
) -> None:
    require(isinstance(expected, list) and all(isinstance(row, dict) for row in expected),
            f"analysis has invalid {label} array")
    require(len(rows) == len(expected), f"{label} CSV cardinality differs from analysis")
    actual_by_key = {tuple(str(row.get(key, "")) for key in identity): row for row in rows}
    expected_by_key = {tuple(str(row.get(key, "")) for key in identity): row for row in expected}
    require(len(actual_by_key) == len(rows) == len(expected_by_key), f"{label} identity is not unique")
    require(set(actual_by_key) == set(expected_by_key), f"{label} identities differ from analysis")
    for key, expected_row in expected_by_key.items():
        actual = actual_by_key[key]
        for field in numeric_fields:
            close(number(actual, field), number(expected_row, field), f"{label}/{key}/{field}")


def load_evidence(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    analysis_path = run_dir / "analysis" / "analysis.json"
    manifest_path = run_dir / "manifest.json"
    analysis = read_json(analysis_path)
    manifest = read_json(manifest_path)
    require(analysis.get("schema_version") == ANALYSIS_SCHEMA, "analysis schema is not certified")
    require(analysis.get("status") == "pass", "analysis status is not pass")
    require(analysis.get("primary_metric") == PRIMARY_METRIC, "primary metric drifted")
    require(analysis.get("manifest", {}).get("sha256") == sha256_file(manifest_path),
            "analysis does not bind the current manifest")
    require(analysis.get("validated_pair_count") == 12 and analysis.get("validated_cell_count") == 24,
            "analysis does not represent the complete 12-pair / 24-role confirmation")
    require(analysis.get("exploratory_pooling_prohibited") is True,
            "analysis permits exploratory pooling")

    analysis_dir = run_dir / "analysis"
    pairs = read_csv(analysis_dir / "validated_pairs.csv")
    summary = read_csv(analysis_dir / "candidate_summary.csv")
    orientation = read_csv(analysis_dir / "orientation_diagnostics.csv")
    quality = read_csv(analysis_dir / "quality_gates.csv")
    validate_csv_view(
        pairs, analysis.get("validated_pairs"),
        identity=("candidate_id", "global_session_index", "session_order"),
        numeric_fields=(
            "baseline_net_pJ_per_logical_output_element",
            "treatment_net_pJ_per_logical_output_element",
            "delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
            "preheat_actual_s", "baseline_trace_r2", "treatment_trace_r2",
            "temperature_min_C", "temperature_max_C",
        ), label="validated_pairs",
    )
    validate_csv_view(
        summary, analysis.get("candidate_summary"), identity=("candidate_id",),
        numeric_fields=(
            "baseline_mean_net_pJ_per_logical_output_element",
            "treatment_mean_net_pJ_per_logical_output_element",
            "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
            "sample_std_delta_net_pJ_per_logical_output_element",
            "t95_low_delta_net_pJ_per_logical_output_element",
            "t95_high_delta_net_pJ_per_logical_output_element",
        ), label="candidate_summary",
    )
    validate_csv_view(
        orientation, analysis.get("orientation_diagnostics"), identity=("candidate_id", "session_order"),
        numeric_fields=(
            "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element",
            "sample_std_delta_net_pJ_per_logical_output_element",
        ), label="orientation_diagnostics",
    )
    require(len(pairs) == 12 and len(summary) == 2 and len(orientation) == 4 and len(quality) >= 4,
            "unexpected plot input cardinality")
    for identifier, _label in CANDIDATES:
        candidate_rows = [row for row in pairs if row["candidate_id"] == identifier]
        require(len(candidate_rows) == 6, f"{identifier} does not have six paired sessions")
        require(sum(row["session_order"] == "AB" for row in candidate_rows) == 3,
                f"{identifier} AB count is not three")
        require(sum(row["session_order"] == "BA" for row in candidate_rows) == 3,
                f"{identifier} BA count is not three")
    return analysis, manifest, pairs, summary, orientation, quality


def add_zero_line(axis: plt.Axes) -> None:
    axis.axhline(0.0, color="#6b7280", linewidth=1.1, linestyle="--", zorder=0)


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg"]
    for path in paths:
        figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        # Matplotlib's SVG serializer deliberately wraps path coordinates with
        # trailing spaces.  Strip only end-of-line whitespace so generated
        # evidence remains ``git diff --check`` clean without changing SVG
        # geometry or metadata.
        if path.suffix == ".svg":
            source = path.read_text(encoding="utf-8")
            normalized = "\n".join(line.rstrip() for line in source.splitlines()) + "\n"
            if source != normalized:
                path.write_text(normalized, encoding="utf-8")
    plt.close(figure)
    return paths


def plot_paired_slopes(pairs: list[dict[str, str]], summary: list[dict[str, str]], output_dir: Path, prefix: str) -> list[Path]:
    summary_by_candidate = {row["candidate_id"]: row for row in summary}
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 5.1), constrained_layout=True)
    for axis, (identifier, label) in zip(axes, CANDIDATES):
        rows = sorted((row for row in pairs if row["candidate_id"] == identifier), key=lambda row: integer(row, "global_session_index"))
        for row in rows:
            baseline = number(row, "baseline_net_pJ_per_logical_output_element")
            treatment = number(row, "treatment_net_pJ_per_logical_output_element")
            color = ORDER_COLOR[row["session_order"]]
            axis.plot((0, 1), (baseline, treatment), color=color, linewidth=1.8, marker="o", markersize=5.5, alpha=0.86)
            axis.text(1.035, treatment, str(integer(row, "global_session_index")), color=color, va="center", fontsize=8)
        mean_delta = number(summary_by_candidate[identifier], "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element")
        low = number(summary_by_candidate[identifier], "t95_low_delta_net_pJ_per_logical_output_element")
        high = number(summary_by_candidate[identifier], "t95_high_delta_net_pJ_per_logical_output_element")
        axis.set_title(f"{label}\nmean Δ={mean_delta:,.1f}; t95 [{low:,.1f}, {high:,.1f}]")
        axis.set_xticks((0, 1), ("baseline\nFP16 I/O + FP32 stages", "treatment"))
        axis.set_ylabel("net pJ / logical output element")
        axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
        axis.spines[["top", "right"]].set_visible(False)
    figure.suptitle("Fresh-process paired paths (session number = global run order)", fontsize=13, y=1.02)
    figure.legend(
        handles=[Line2D([0], [0], color=ORDER_COLOR[order], marker="o", label=order) for order in ("AB", "BA")],
        loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.06),
    )
    return save_figure(figure, output_dir, f"{prefix}_paired_slopes")


def plot_paired_deltas(pairs: list[dict[str, str]], summary: list[dict[str, str]], output_dir: Path, prefix: str) -> list[Path]:
    figure, axis = plt.subplots(figsize=(10.5, 5.7), constrained_layout=True)
    summary_by_candidate = {row["candidate_id"]: row for row in summary}
    offsets = (-0.17, -0.10, -0.03, 0.03, 0.10, 0.17)
    for xpos, (identifier, label) in enumerate(CANDIDATES):
        rows = sorted((row for row in pairs if row["candidate_id"] == identifier), key=lambda row: integer(row, "global_session_index"))
        for offset, row in zip(offsets, rows):
            delta = number(row, "delta_treatment_minus_baseline_net_pJ_per_logical_output_element")
            axis.scatter(xpos + offset, delta, color=ORDER_COLOR[row["session_order"]], s=62, zorder=3, edgecolor="white", linewidth=0.8)
            axis.annotate(str(integer(row, "global_session_index")), (xpos + offset, delta), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8)
        row = summary_by_candidate[identifier]
        mean = number(row, "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element")
        low = number(row, "t95_low_delta_net_pJ_per_logical_output_element")
        high = number(row, "t95_high_delta_net_pJ_per_logical_output_element")
        axis.errorbar(xpos, mean, yerr=[[mean - low], [high - mean]], fmt="D", color=MEAN_COLOR,
                      markersize=7, capsize=6, linewidth=2.0, zorder=4)
    add_zero_line(axis)
    axis.set_xticks(range(len(CANDIDATES)), [label for _, label in CANDIDATES])
    axis.set_ylabel("treatment − baseline\nnet pJ / logical output element")
    axis.set_title("Session deltas, mean diamond, and descriptive t95 interval")
    axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=ORDER_COLOR["AB"], label="AB session"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor=ORDER_COLOR["BA"], label="BA session"),
            Line2D([0], [0], marker="D", color=MEAN_COLOR, label="mean ± descriptive t95"),
        ], loc="upper left", frameon=False,
    )
    return save_figure(figure, output_dir, f"{prefix}_paired_deltas")


def plot_orientation(orientation: list[dict[str, str]], output_dir: Path, prefix: str) -> list[Path]:
    figure, axis = plt.subplots(figsize=(10.5, 5.5), constrained_layout=True)
    width = 0.31
    for xpos, (identifier, label) in enumerate(CANDIDATES):
        for shift, order in ((-width / 2, "AB"), (width / 2, "BA")):
            row = next(item for item in orientation if item["candidate_id"] == identifier and item["session_order"] == order)
            mean = number(row, "mean_delta_treatment_minus_baseline_net_pJ_per_logical_output_element")
            std = number(row, "sample_std_delta_net_pJ_per_logical_output_element")
            axis.bar(xpos + shift, mean, width=width, color=ORDER_COLOR[order], alpha=0.9, label=order if xpos == 0 else None)
            axis.errorbar(xpos + shift, mean, yerr=std, color="#111827", capsize=4, linewidth=1.3)
            axis.annotate(f"{mean:,.0f}", (xpos + shift, mean), xytext=(0, 5 if mean >= 0 else -13),
                          textcoords="offset points", ha="center", fontsize=8)
    add_zero_line(axis)
    axis.set_xticks(range(len(CANDIDATES)), [label for _, label in CANDIDATES])
    axis.set_ylabel("mean Δ pJ / logical output element\n(error bar: sample SD, n=3/order)")
    axis.set_title("AB/BA orientation diagnostic — descriptive only")
    axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False)
    return save_figure(figure, output_dir, f"{prefix}_orientation_diagnostic")


def plot_quality(pairs: list[dict[str, str]], output_dir: Path, prefix: str) -> list[Path]:
    rows = sorted(pairs, key=lambda row: integer(row, "global_session_index"))
    indices = [integer(row, "global_session_index") for row in rows]
    figure, (temperature_axis, trace_axis) = plt.subplots(2, 1, figsize=(11.0, 7.3), sharex=True, constrained_layout=True)
    temperature_min = [number(row, "temperature_min_C") for row in rows]
    temperature_max = [number(row, "temperature_max_C") for row in rows]
    temperature_axis.vlines(indices, temperature_min, temperature_max, color="#7c3aed", linewidth=4, alpha=0.72)
    temperature_axis.scatter(indices, temperature_min, color="#5b21b6", s=28, zorder=3, label="minimum")
    temperature_axis.scatter(indices, temperature_max, color="#a78bfa", s=28, zorder=3, label="maximum")
    temperature_axis.set_ylabel("recorded temperature (°C)")
    temperature_axis.set_title("Recorded thermal context and qualified trace fit")
    temperature_axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    temperature_axis.spines[["top", "right"]].set_visible(False)
    temperature_axis.legend(frameon=False, ncol=2)

    baseline_r2 = [number(row, "baseline_trace_r2") for row in rows]
    treatment_r2 = [number(row, "treatment_trace_r2") for row in rows]
    trace_axis.plot(indices, baseline_r2, marker="o", color="#0f766e", label="baseline trace R²")
    trace_axis.plot(indices, treatment_r2, marker="s", color="#be123c", label="treatment trace R²")
    trace_axis.axhline(0.98, color="#6b7280", linewidth=1.0, linestyle="--", label="qualification gate (0.98)")
    trace_axis.set_ylim(0.975, 1.0002)
    trace_axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:.3f}"))
    trace_axis.set_xlabel("global fresh-process session order")
    trace_axis.set_ylabel("Theil–Sen trace R²")
    trace_axis.set_xticks(indices)
    trace_axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    trace_axis.spines[["top", "right"]].set_visible(False)
    trace_axis.legend(frameon=False, ncol=3, loc="lower center")
    return save_figure(figure, output_dir, f"{prefix}_quality_context")


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def figure_entry(identifier: str, title: str, paths: Iterable[Path]) -> dict[str, Any]:
    by_suffix = {path.suffix.lstrip("."): path for path in paths}
    return {
        "id": identifier,
        "title": title,
        "png": repo_path(by_suffix["png"]),
        "svg": repo_path(by_suffix["svg"]),
        "png_sha256": sha256_file(by_suffix["png"]),
        "svg_sha256": sha256_file(by_suffix["svg"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path,
                        default=ROOT / "docs/assets/softmax_whole_precision_targeted_confirmation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.out_dir.resolve()
    analysis, _manifest, pairs, summary, orientation, _quality = load_evidence(run_dir)
    prefix = f"rtx3090_softmax_whole_precision_targeted_confirmation_{analysis['manifest']['run_tag']}"
    entries = [
        figure_entry("paired_slopes", "Fresh-process paired paths", plot_paired_slopes(pairs, summary, output_dir, prefix)),
        figure_entry("paired_deltas", "Paired delta distribution and descriptive t95", plot_paired_deltas(pairs, summary, output_dir, prefix)),
        figure_entry("orientation_diagnostic", "AB/BA orientation diagnostic", plot_orientation(orientation, output_dir, prefix)),
        figure_entry("quality_context", "Recorded temperature and trace-fit context", plot_quality(pairs, output_dir, prefix)),
    ]
    manifest_path = output_dir / f"{prefix}_figure_manifest.json"
    atomic_write_json(
        manifest_path,
        {
            "schema_version": FIGURE_SCHEMA,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "analysis": {
                "path": repo_path(run_dir / "analysis/analysis.json"),
                "sha256": sha256_file(run_dir / "analysis/analysis.json"),
                "manifest_sha256": sha256_file(run_dir / "manifest.json"),
            },
            "figures": entries,
            "interpretation_boundary": "two separate fresh targeted contrasts; no exploratory pooling or cross-candidate ranking",
        },
    )
    print("figure_status=pass")
    print(f"figure_manifest={repo_path(manifest_path)}")
    for entry in entries:
        print(f"{entry['id']}={entry['png']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=__import__("sys").stderr)
        raise SystemExit(2)
