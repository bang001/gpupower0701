#!/usr/bin/env python3
"""Render static Matplotlib diagnostics for the targeted Softmax EX2 result.

The primary experimental unit is a fresh-session mean (three sessions per
implementation), not one matched block.  These figures intentionally expose
the nine session cells and keep matched blocks in a separate, explicitly
secondary diagnostic.  They are companion views for the frozen 2026-07-25
CTA=48/S=1024 confirmation and do not alter its canonical HTML artifact.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAG = "20260725"
DEFAULT_SUMMARY_DIR = ROOT / "results" / "summary"
DEFAULT_OUT_DIR = ROOT / "docs" / "assets" / "softmax_ex2_targeted_confirmation"
OUTPUT_PREFIX = "rtx3090_softmax_ex2_targeted_confirmation_"

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
ZERO = "#EEF2F3"
BLUE = "#2E6F9E"
GOLD = "#B88719"
ORANGE = "#D06F2B"
PURPLE = "#7E5A9B"
SESSION_COLOURS = {1: "#4C78A8", 2: "#59A14F", 3: "#B279A2"}
SESSION_MARKERS = {1: "o", 2: "s", 3: "^"}

IMPLEMENTATIONS = ("fp32", "ptx_f16", "ptx_f16x2")
IMPLEMENTATION_LABELS = {
    "fp32": "FP32 __expf",
    "ptx_f16": "scalar FP16\nptx_f16",
    "ptx_f16x2": "packed FP16\nptx_f16x2",
}
SHORT_IMPLEMENTATION_LABELS = {
    "fp32": "FP32",
    "ptx_f16": "scalar",
    "ptx_f16x2": "packed",
}
IMPLEMENTATION_COLOURS = {
    "fp32": BLUE,
    "ptx_f16": GOLD,
    "ptx_f16x2": PURPLE,
}
CONTRASTS = (
    "fp32_minus_ptx_f16",
    "fp32_minus_ptx_f16x2",
    "ptx_f16x2_minus_ptx_f16",
)
CONTRAST_LABELS = {
    "fp32_minus_ptx_f16": "FP32 - scalar FP16",
    "fp32_minus_ptx_f16x2": "FP32 - packed FP16",
    "ptx_f16x2_minus_ptx_f16": "packed FP16 - scalar FP16",
}
CONTRAST_COLOURS = {
    "fp32_minus_ptx_f16": BLUE,
    "fp32_minus_ptx_f16x2": ORANGE,
    "ptx_f16x2_minus_ptx_f16": PURPLE,
}


def configure_style() -> None:
    """Use the repository's quiet, publication-oriented Matplotlib style."""

    system_font = Path("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf")
    if system_font.exists():
        font_manager.fontManager.addfont(system_font)
        family = font_manager.FontProperties(fname=system_font).get_name()
    else:
        family = "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": family,
            "font.size": 10.5,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{column!r} is not a finite number in {row}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{column!r} is not finite in {row}")
    return value


def int_value(row: dict[str, str], column: str) -> int:
    try:
        return int(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{column!r} is not an integer in {row}") from exc


def source_path(summary_dir: Path, tag: str, suffix: str) -> Path:
    path = (
        summary_dir
        / "rtx3090_softmax_ex2_targeted_confirmation_"
        f"targeted_g48s1024_confirm_v1_{tag}_{suffix}.csv"
    )
    if not path.is_file():
        raise FileNotFoundError(f"missing targeted-confirmation input: {path}")
    return path


def load_inputs(summary_dir: Path, tag: str) -> dict[str, list[dict[str, str]]]:
    return {
        "implementation_summary": read_csv(source_path(summary_dir, tag, "implementation_summary")),
        "session_cells": read_csv(source_path(summary_dir, tag, "session_cells")),
        "within_session_contrasts": read_csv(
            source_path(summary_dir, tag, "within_session_contrasts")
        ),
        "contrast_summary": read_csv(source_path(summary_dir, tag, "contrast_summary")),
        "matched_blocks": read_csv(source_path(summary_dir, tag, "matched_blocks")),
    }


def grouped_rows(
    rows: list[dict[str, str]], key: str
) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return dict(groups)


def rows_by_implementation(
    cells: list[dict[str, str]]
) -> dict[str, list[dict[str, str]]]:
    grouped = grouped_rows(cells, "implementation")
    return {
        implementation: sorted(rows, key=lambda row: int_value(row, "session_index"))
        for implementation, rows in grouped.items()
    }


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot compute a mean of no values")
    return statistics.fmean(values)


def verify_input_contract(inputs: dict[str, list[dict[str, str]]]) -> None:
    """Fail early if the figure inputs no longer describe the frozen design."""

    summaries = inputs["implementation_summary"]
    cells = inputs["session_cells"]
    contrasts = inputs["within_session_contrasts"]
    contrast_summaries = inputs["contrast_summary"]
    blocks = inputs["matched_blocks"]

    if len(summaries) != 3 or {row["implementation"] for row in summaries} != set(IMPLEMENTATIONS):
        raise AssertionError("expected exactly the three frozen implementation summaries")
    if len(cells) != 9 or any(row.get("quality_status") != "pass" for row in cells):
        raise AssertionError("expected nine quality-pass fresh session cells")
    if len(contrasts) != 9 or len(contrast_summaries) != 3:
        raise AssertionError("expected three within-session contrasts across three sessions")
    if len(blocks) != 27 or any(row.get("quality_status") != "pass" for row in blocks):
        raise AssertionError("expected 27 quality-pass nested matched blocks")

    by_implementation = rows_by_implementation(cells)
    if set(by_implementation) != set(IMPLEMENTATIONS):
        raise AssertionError("session cells have an unexpected implementation set")
    for implementation, rows in by_implementation.items():
        if len(rows) != 3:
            raise AssertionError(f"expected three sessions for {implementation}")
        if {int_value(row, "implementation_position") for row in rows} != {1, 2, 3}:
            raise AssertionError(
                f"{implementation} does not occupy each cyclic position exactly once"
            )

    summary_by_implementation = {row["implementation"]: row for row in summaries}
    for implementation, rows in by_implementation.items():
        observed_mean = mean([number(row, "incremental_pJ_per_element") for row in rows])
        reported_mean = number(
            summary_by_implementation[implementation], "mean_incremental_pJ_per_element"
        )
        if not math.isclose(observed_mean, reported_mean, rel_tol=0.0, abs_tol=1e-9):
            raise AssertionError(f"summary mean does not match session cells for {implementation}")

    contrast_by_name = grouped_rows(contrasts, "contrast")
    summary_by_contrast = {row["contrast"]: row for row in contrast_summaries}
    if set(contrast_by_name) != set(CONTRASTS) or set(summary_by_contrast) != set(CONTRASTS):
        raise AssertionError("contrast names do not match the frozen design")
    for contrast, rows in contrast_by_name.items():
        reported_mean = number(
            summary_by_contrast[contrast], "mean_incremental_pJ_per_element"
        )
        observed_mean = mean([number(row, "contrast_incremental_pJ_per_element") for row in rows])
        if not math.isclose(observed_mean, reported_mean, rel_tol=0.0, abs_tol=1e-9):
            raise AssertionError(f"summary contrast does not match raw session contrast: {contrast}")


def style_axis(ax: plt.Axes, *, grid_axis: str = "y") -> None:
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=LINE, linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(LINE)
    ax.spines["bottom"].set_color(LINE)


def normalize_svg(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def write_figure(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{stem}.png"
    svg_path = output_dir / f"{stem}.svg"
    metadata = {"Creator": Path(__file__).name, "Date": None}
    fig.savefig(png_path, dpi=220, bbox_inches="tight", facecolor="white", metadata=metadata)
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white", metadata=metadata)
    normalize_svg(svg_path)
    plt.close(fig)
    return png_path, svg_path


def session_lookup(cells: list[dict[str, str]]) -> dict[tuple[int, str], dict[str, str]]:
    return {
        (int_value(row, "session_index"), row["implementation"]): row for row in cells
    }


def plot_session_spread(
    cells: list[dict[str, str]],
    summaries: list[dict[str, str]],
    output_dir: Path,
    tag: str,
) -> tuple[Path, Path]:
    """Show all fresh-session values beside their paired categorical paths."""

    summary_by_implementation = {row["implementation"]: row for row in summaries}
    by_implementation = rows_by_implementation(cells)
    fig, (interval_ax, path_ax) = plt.subplots(
        1,
        2,
        figsize=(13.4, 5.5),
        gridspec_kw={"width_ratios": (1.06, 1.14)},
    )

    y_positions = {implementation: 2 - index for index, implementation in enumerate(IMPLEMENTATIONS)}
    offsets = (-0.18, 0.0, 0.18)
    for implementation in IMPLEMENTATIONS:
        row = summary_by_implementation[implementation]
        y = y_positions[implementation]
        low = number(row, "diagnostic_t95_low_incremental_pJ_per_element")
        high = number(row, "diagnostic_t95_high_incremental_pJ_per_element")
        value = number(row, "mean_incremental_pJ_per_element")
        colour = IMPLEMENTATION_COLOURS[implementation]
        interval_ax.hlines(y, low, high, color=colour, linewidth=4.0, zorder=2)
        interval_ax.vlines((low, high), y - 0.09, y + 0.09, color=colour, linewidth=1.5, zorder=2)
        for offset, cell in zip(offsets, by_implementation[implementation], strict=True):
            session = int_value(cell, "session_index")
            interval_ax.scatter(
                number(cell, "incremental_pJ_per_element"),
                y + offset,
                s=58,
                marker=SESSION_MARKERS[session],
                color=colour,
                edgecolor="white",
                linewidth=0.8,
                zorder=3,
            )
        interval_ax.scatter(
            value,
            y,
            s=78,
            marker="D",
            color="white",
            edgecolor=INK,
            linewidth=1.35,
            zorder=4,
        )
        interval_ax.text(
            high + 1.8,
            y,
            f"mean {value:.1f}",
            va="center",
            ha="left",
            fontsize=9.2,
            color=INK,
        )

    interval_ax.axvline(0.0, color=ZERO, linewidth=1.2, zorder=0)
    interval_ax.set_xlim(-5.0, 106.0)
    interval_ax.set_ylim(-0.62, 2.62)
    interval_ax.set_yticks([y_positions[implementation] for implementation in IMPLEMENTATIONS])
    interval_ax.set_yticklabels([IMPLEMENTATION_LABELS[implementation] for implementation in IMPLEMENTATIONS])
    interval_ax.set_xlabel("incremental energy (pJ / input element)")
    interval_ax.set_title("Fresh-session spread and descriptive t95")
    style_axis(interval_ax, grid_axis="x")
    interval_ax.legend(
        handles=[
            *[
                Line2D(
                    [0],
                    [0],
                    marker=SESSION_MARKERS[session],
                    color="none",
                    markerfacecolor=INK,
                    markeredgecolor="white",
                    markersize=7,
                    label=f"session {session}",
                )
                for session in (1, 2, 3)
            ],
            Line2D(
                [0],
                [0],
                marker="D",
                color="none",
                markerfacecolor="white",
                markeredgecolor=INK,
                markersize=7,
                label="mean",
            ),
            Line2D([0], [0], color=INK, linewidth=3, label="diagnostic t95"),
        ],
        loc="lower right",
        ncol=2,
        frameon=False,
        fontsize=8.3,
        handletextpad=0.45,
        columnspacing=0.8,
    )

    lookup = session_lookup(cells)
    x_positions = list(range(len(IMPLEMENTATIONS)))
    for session in (1, 2, 3):
        values = [
            number(lookup[(session, implementation)], "incremental_pJ_per_element")
            for implementation in IMPLEMENTATIONS
        ]
        path_ax.plot(
            x_positions,
            values,
            color=SESSION_COLOURS[session],
            linewidth=1.7,
            alpha=0.72,
            zorder=1,
        )
        for x, implementation, value in zip(x_positions, IMPLEMENTATIONS, values, strict=True):
            path_ax.scatter(
                x,
                value,
                s=60,
                marker=SESSION_MARKERS[session],
                color=IMPLEMENTATION_COLOURS[implementation],
                edgecolor="white",
                linewidth=0.8,
                zorder=2,
            )
    path_ax.axhline(0.0, color=ZERO, linewidth=1.2, zorder=0)
    path_ax.set_xlim(-0.25, 2.25)
    path_ax.set_ylim(-5.0, 100.0)
    path_ax.set_xticks(x_positions)
    path_ax.set_xticklabels([IMPLEMENTATION_LABELS[implementation] for implementation in IMPLEMENTATIONS])
    path_ax.set_ylabel("incremental energy (pJ / input element)")
    path_ax.set_title("Paired values within each fresh session")
    style_axis(path_ax, grid_axis="y")
    path_ax.legend(
        handles=[
            Line2D(
                [0],
                [0],
                color=SESSION_COLOURS[session],
                marker=SESSION_MARKERS[session],
                linewidth=1.7,
                label=f"session {session}",
            )
            for session in (1, 2, 3)
        ],
        loc="upper right",
        frameon=False,
        fontsize=8.5,
    )
    path_ax.text(
        0.02,
        0.03,
        "Lines link the same session only; the categorical axis is not a time trend.",
        transform=path_ax.transAxes,
        fontsize=8.4,
        color=MUTED,
        va="bottom",
    )

    fig.suptitle(
        "CTA=48, S=1024 — one added logical EX2 result per input element",
        fontsize=13.2,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.005,
        "n=3 fresh sessions per implementation; t95 is a descriptive df=2 diagnostic, not a decision threshold.",
        ha="center",
        color=MUTED,
        fontsize=9.1,
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 0.94))
    return write_figure(fig, output_dir, f"{OUTPUT_PREFIX}{tag}_session_spread")


def plot_path_contrasts(
    contrasts: list[dict[str, str]],
    contrast_summaries: list[dict[str, str]],
    output_dir: Path,
    tag: str,
) -> tuple[Path, Path]:
    """Plot same-session complete-path differences, including the packed comparison."""

    contrast_by_name = {
        name: sorted(rows, key=lambda row: int_value(row, "session_index"))
        for name, rows in grouped_rows(contrasts, "contrast").items()
    }
    summary_by_name = {row["contrast"]: row for row in contrast_summaries}
    fig, (forest_ax, packed_ax) = plt.subplots(
        1,
        2,
        figsize=(13.4, 5.3),
        gridspec_kw={"width_ratios": (1.25, 0.88)},
    )

    y_positions = {contrast: 2 - index for index, contrast in enumerate(CONTRASTS)}
    offsets = (-0.18, 0.0, 0.18)
    for contrast in CONTRASTS:
        y = y_positions[contrast]
        colour = CONTRAST_COLOURS[contrast]
        summary = summary_by_name[contrast]
        low = number(summary, "diagnostic_t95_low_incremental_pJ_per_element")
        high = number(summary, "diagnostic_t95_high_incremental_pJ_per_element")
        value = number(summary, "mean_incremental_pJ_per_element")
        forest_ax.hlines(y, low, high, color=colour, linewidth=4.0, zorder=2)
        forest_ax.vlines((low, high), y - 0.09, y + 0.09, color=colour, linewidth=1.4, zorder=2)
        for offset, row in zip(offsets, contrast_by_name[contrast], strict=True):
            session = int_value(row, "session_index")
            forest_ax.scatter(
                number(row, "contrast_incremental_pJ_per_element"),
                y + offset,
                s=58,
                marker=SESSION_MARKERS[session],
                color=colour,
                edgecolor="white",
                linewidth=0.8,
                zorder=3,
            )
        forest_ax.scatter(
            value,
            y,
            s=78,
            marker="D",
            color="white",
            edgecolor=INK,
            linewidth=1.35,
            zorder=4,
        )
        forest_ax.text(
            92.0,
            y,
            f"{value:+.1f}",
            va="center",
            ha="right",
            color=INK,
            fontsize=9.3,
        )

    forest_ax.axvline(0.0, color=INK, linewidth=1.1, zorder=0)
    forest_ax.set_xlim(-30.0, 96.0)
    forest_ax.set_ylim(-0.62, 2.62)
    forest_ax.set_yticks([y_positions[contrast] for contrast in CONTRASTS])
    forest_ax.set_yticklabels([CONTRAST_LABELS[contrast] for contrast in CONTRASTS])
    forest_ax.set_xlabel("paired Δ incremental energy (pJ / input element)")
    forest_ax.set_title("All same-session implementation-path contrasts")
    style_axis(forest_ax, grid_axis="x")
    forest_ax.text(
        0.02,
        0.03,
        "Positive means the left path has higher incremental energy."
        "\nIntervals are descriptive t95 values for n=3 paired sessions.",
        transform=forest_ax.transAxes,
        fontsize=8.6,
        color=MUTED,
        va="bottom",
    )

    packed_contrast = "ptx_f16x2_minus_ptx_f16"
    packed_summary = summary_by_name[packed_contrast]
    packed_low = number(packed_summary, "diagnostic_t95_low_incremental_pJ_per_element")
    packed_high = number(packed_summary, "diagnostic_t95_high_incremental_pJ_per_element")
    packed_mean = number(packed_summary, "mean_incremental_pJ_per_element")
    packed_ax.axvline(0.0, color=INK, linewidth=1.2, zorder=0)
    packed_ax.hlines(0.0, packed_low, packed_high, color=PURPLE, linewidth=5.0, zorder=2)
    packed_ax.vlines((packed_low, packed_high), -0.10, 0.10, color=PURPLE, linewidth=1.5, zorder=2)
    for offset, row in zip(offsets, contrast_by_name[packed_contrast], strict=True):
        session = int_value(row, "session_index")
        value = number(row, "contrast_incremental_pJ_per_element")
        packed_ax.scatter(
            value,
            offset,
            s=68,
            marker=SESSION_MARKERS[session],
            color=PURPLE,
            edgecolor="white",
            linewidth=0.85,
            zorder=3,
        )
        packed_ax.annotate(
            f"S{session}: {value:+.1f}",
            (value, offset),
            xytext=(0, 9 if offset >= 0.0 else -14),
            textcoords="offset points",
            ha="center",
            fontsize=8.6,
            color=INK,
        )
    packed_ax.scatter(
        packed_mean,
        0.0,
        s=88,
        marker="D",
        color="white",
        edgecolor=INK,
        linewidth=1.35,
        zorder=4,
    )
    packed_ax.set_xlim(-25.0, 36.0)
    packed_ax.set_ylim(-0.46, 0.46)
    packed_ax.set_yticks([])
    packed_ax.set_xlabel("packed - scalar (pJ / input element)")
    packed_ax.set_title("Packed FP16 versus scalar FP16 (zoom)")
    style_axis(packed_ax, grid_axis="x")
    packed_ax.text(
        0.02,
        0.94,
        f"mean {packed_mean:+.3f}\ndiagnostic t95 [{packed_low:+.3f}, {packed_high:+.3f}]",
        transform=packed_ax.transAxes,
        va="top",
        fontsize=9.0,
        color=INK,
    )
    packed_ax.text(
        0.02,
        0.05,
        "The interval crosses zero; this does not support a packed-energy benefit.",
        transform=packed_ax.transAxes,
        fontsize=8.3,
        color=MUTED,
        va="bottom",
    )

    fig.suptitle(
        "CTA=48, S=1024 — paired complete implementation-path differences",
        fontsize=13.2,
        fontweight="bold",
        y=0.995,
    )
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.94))
    return write_figure(fig, output_dir, f"{OUTPUT_PREFIX}{tag}_path_contrasts")


def position_adjusted_values(
    cells: list[dict[str, str]]
) -> list[tuple[dict[str, str], float]]:
    """Remove additive session and implementation means for a position diagnostic.

    The cyclic Latin design has one cell at every implementation/position and
    session/position combination.  This residual-like quantity is descriptive:
    the nine cells leave only two residual degrees of freedom in a full additive
    model, so it is not used for a causal position estimate.
    """

    overall = mean([number(row, "incremental_pJ_per_element") for row in cells])
    session_means = {
        session: mean(
            [
                number(row, "incremental_pJ_per_element")
                for row in cells
                if int_value(row, "session_index") == session
            ]
        )
        for session in (1, 2, 3)
    }
    implementation_means = {
        implementation: mean(
            [
                number(row, "incremental_pJ_per_element")
                for row in cells
                if row["implementation"] == implementation
            ]
        )
        for implementation in IMPLEMENTATIONS
    }
    return [
        (
            row,
            number(row, "incremental_pJ_per_element")
            - session_means[int_value(row, "session_index")]
            - implementation_means[row["implementation"]]
            + overall,
        )
        for row in cells
    ]


def plot_position_balance(
    cells: list[dict[str, str]], output_dir: Path, tag: str
) -> tuple[Path, Path]:
    """Visualize the cyclic order and a deliberately non-causal order diagnostic."""

    adjusted = position_adjusted_values(cells)
    adjusted_by_position: dict[int, list[float]] = defaultdict(list)
    fig, (residual_ax, order_ax) = plt.subplots(
        1,
        2,
        figsize=(13.4, 5.2),
        gridspec_kw={"width_ratios": (1.08, 0.92)},
    )

    offset_by_session = {1: -0.13, 2: 0.0, 3: 0.13}
    for row, value in adjusted:
        position = int_value(row, "implementation_position")
        session = int_value(row, "session_index")
        adjusted_by_position[position].append(value)
        residual_ax.scatter(
            position + offset_by_session[session],
            value,
            s=66,
            marker=SESSION_MARKERS[session],
            color=IMPLEMENTATION_COLOURS[row["implementation"]],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
    effects = {position: mean(values) for position, values in adjusted_by_position.items()}
    for position in (1, 2, 3):
        residual_ax.scatter(
            position,
            effects[position],
            s=86,
            marker="D",
            color="white",
            edgecolor=INK,
            linewidth=1.35,
            zorder=4,
        )
        residual_ax.annotate(
            f"{effects[position]:+.2f}",
            (position, effects[position]),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=9.0,
            color=INK,
        )
    residual_ax.axhline(0.0, color=INK, linewidth=1.1, zorder=0)
    residual_ax.set_xlim(0.55, 3.45)
    residual_ax.set_xticks((1, 2, 3))
    residual_ax.set_xlabel("execution position within session")
    residual_ax.set_ylabel("session- and implementation-adjusted value (pJ / element)")
    residual_ax.set_title("Execution-position diagnostic")
    style_axis(residual_ax, grid_axis="y")
    residual_ax.text(
        0.02,
        0.04,
        "Three cells per position; descriptive only (not a causal order estimate).",
        transform=residual_ax.transAxes,
        fontsize=8.6,
        color=MUTED,
        va="bottom",
    )

    order_ax.set_xlim(0.0, 3.0)
    order_ax.set_ylim(3.0, 0.0)
    for row in cells:
        position = int_value(row, "implementation_position") - 1
        session = int_value(row, "session_index") - 1
        implementation = row["implementation"]
        order_ax.add_patch(
            Rectangle(
                (position, session),
                1.0,
                1.0,
                facecolor=IMPLEMENTATION_COLOURS[implementation],
                edgecolor="white",
                linewidth=2.0,
                alpha=0.72,
            )
        )
        order_ax.text(
            position + 0.5,
            session + 0.46,
            f"{SHORT_IMPLEMENTATION_LABELS[implementation]}\n"
            f"{number(row, 'incremental_pJ_per_element'):.1f}",
            ha="center",
            va="center",
            fontsize=10.0,
            color="white",
            fontweight="bold",
        )
    order_ax.set_xticks((0.5, 1.5, 2.5), ("position 1", "position 2", "position 3"))
    order_ax.set_yticks((0.5, 1.5, 2.5), ("session 1", "session 2", "session 3"))
    order_ax.tick_params(length=0)
    for spine in order_ax.spines.values():
        spine.set_visible(False)
    order_ax.set_title("Cyclic Latin order (cell mean shown)")
    order_ax.legend(
        handles=[
            Patch(facecolor=IMPLEMENTATION_COLOURS[implementation], label=SHORT_IMPLEMENTATION_LABELS[implementation])
            for implementation in IMPLEMENTATIONS
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=False,
        fontsize=8.6,
    )

    fig.suptitle(
        "CTA=48, S=1024 — implementation order is balanced across positions",
        fontsize=13.0,
        fontweight="bold",
        y=0.995,
    )
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.94))
    return write_figure(fig, output_dir, f"{OUTPUT_PREFIX}{tag}_position_balance")


def plot_matched_block_diagnostics(
    cells: list[dict[str, str]],
    blocks: list[dict[str, str]],
    output_dir: Path,
    tag: str,
) -> tuple[Path, Path]:
    """Expose nested block variability without promoting it to the primary n."""

    cell_by_key = session_lookup(cells)
    blocks_by_key: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in blocks:
        blocks_by_key[(int_value(row, "session_index"), row["implementation"])].append(row)
    for rows in blocks_by_key.values():
        rows.sort(key=lambda row: int_value(row, "matched_block"))

    all_values = [number(row, "order_balanced_incremental_pJ_per_element") for row in blocks]
    low = min(all_values)
    high = max(all_values)
    padding = max(8.0, (high - low) * 0.10)
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 5.5), sharey=True)
    jitter = (-0.12, 0.0, 0.12)
    for axis, implementation in zip(axes, IMPLEMENTATIONS, strict=True):
        colour = IMPLEMENTATION_COLOURS[implementation]
        for session in (1, 2, 3):
            rows = blocks_by_key[(session, implementation)]
            for offset, row in zip(jitter, rows, strict=True):
                axis.scatter(
                    session + offset,
                    number(row, "order_balanced_incremental_pJ_per_element"),
                    s=52,
                    marker="o",
                    color=colour,
                    alpha=0.52,
                    edgecolor="white",
                    linewidth=0.65,
                    zorder=2,
                )
            cell_mean = number(
                cell_by_key[(session, implementation)], "incremental_pJ_per_element"
            )
            axis.scatter(
                session,
                cell_mean,
                s=90,
                marker="D",
                color="white",
                edgecolor=INK,
                linewidth=1.35,
                zorder=4,
            )
            axis.annotate(
                f"{cell_mean:.1f}",
                (session, cell_mean),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=8.8,
                color=INK,
            )
        axis.axhline(0.0, color=ZERO, linewidth=1.2, zorder=0)
        axis.set_xlim(0.55, 3.45)
        axis.set_ylim(low - padding, high + padding)
        axis.set_xticks((1, 2, 3), ("session 1", "session 2", "session 3"))
        axis.set_title(IMPLEMENTATION_LABELS[implementation].replace("\n", " "))
        style_axis(axis, grid_axis="y")
    axes[0].set_ylabel("order-balanced ΔpJ / input element")
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=MUTED,
                markeredgecolor="white",
                markersize=7,
                alpha=0.65,
                label="matched block (nested)",
            ),
            Line2D(
                [0],
                [0],
                marker="D",
                color="none",
                markerfacecolor="white",
                markeredgecolor=INK,
                markersize=7,
                label="fresh-session cell mean",
            ),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.012),
        fontsize=9.0,
    )
    fig.suptitle(
        "Nested matched-block diagnostic — blocks are not pooled as independent sessions",
        fontsize=13.0,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.075,
        "Each small dot is one of three matched blocks within a session cell. "
        "Primary aggregation remains n=3 fresh sessions per implementation.",
        ha="center",
        color=MUTED,
        fontsize=9.0,
    )
    fig.tight_layout(rect=(0.0, 0.12, 1.0, 0.94))
    return write_figure(fig, output_dir, f"{OUTPUT_PREFIX}{tag}_matched_block_diagnostics")


def verify_png_outputs(paths: list[Path]) -> None:
    """Decode generated PNGs and reject suspiciously small figure exports."""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - normal environments include Pillow
        raise RuntimeError("Pillow is required for PNG output QA") from exc
    for path in paths:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
        if width < 1_200 or height < 700:
            raise AssertionError(f"unexpectedly small PNG export {path}: {width}x{height}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG, help="targeted-confirmation date tag")
    parser.add_argument("--summary-dir", type=Path, default=DEFAULT_SUMMARY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="validate frozen input shape and aggregate arithmetic without writing images",
    )
    args = parser.parse_args()

    inputs = load_inputs(args.summary_dir, args.tag)
    verify_input_contract(inputs)
    if args.self_test:
        print("Softmax EX2 targeted-confirmation visualization self-test passed")
        return 0

    configure_style()
    outputs: list[tuple[Path, Path]] = [
        plot_session_spread(
            inputs["session_cells"],
            inputs["implementation_summary"],
            args.out_dir,
            args.tag,
        ),
        plot_path_contrasts(
            inputs["within_session_contrasts"],
            inputs["contrast_summary"],
            args.out_dir,
            args.tag,
        ),
        plot_position_balance(inputs["session_cells"], args.out_dir, args.tag),
        plot_matched_block_diagnostics(
            inputs["session_cells"], inputs["matched_blocks"], args.out_dir, args.tag
        ),
    ]
    pngs = [png for png, _ in outputs]
    verify_png_outputs(pngs)
    for png_path, svg_path in outputs:
        print(f"wrote {png_path}")
        print(f"wrote {svg_path}")
    print(f"PNG QA passed for {len(pngs)} figure(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
