#!/usr/bin/env python3
"""Render Matplotlib companions for the whole-Softmax stage-isolation run.

The input is the fail-closed analyzer output, not the legacy EX2 probe
artifacts.  Each point is one fresh CUDA-process session and the primary unit
is net pJ per logical Softmax output element.  The charts intentionally retain
the three session values and descriptive (not inferential) t intervals.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = (
    ROOT
    / "results/raw/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1"
)
DEFAULT_OUT_DIR = ROOT / "docs/assets/softmax_whole_precision_stage_isolation"
PREFIX = "rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1"

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
LIGHT = "#EEF2F3"
BASELINE = "#465B65"
SCALAR = "#2E6F9E"
PACKED = "#D06F2B"
SESSION_COLOURS = {1: "#4C78A8", 2: "#59A14F", 3: "#B279A2"}
SESSION_MARKERS = {1: "o", 2: "s", 3: "^"}
T95_N3 = 4.30265272991

STAGES = ("exp", "reduction", "normalization")
STAGE_LABELS = {
    "exp": "exp",
    "reduction": "max + sum reduction",
    "normalization": "normalization",
}
STAGE_SHORT_LABELS = {
    "exp": "exp",
    "reduction": "reduction",
    "normalization": "normalization",
}
POLICIES = {
    "exp": ("fp16_io_fp32_all", "exp_fp16_scalar", "exp_fp16x2"),
    "reduction": (
        "fp16_io_fp32_all",
        "reduction_fp16_scalar",
        "reduction_fp16x2",
    ),
    "normalization": (
        "fp16_io_fp32_all",
        "normalization_fp16_scalar",
        "normalization_fp16x2",
    ),
}
POLICY_LABELS = {
    "fp16_io_fp32_all": "FP32 stages\n(FP16 I/O)",
    "exp_fp16_scalar": "scalar FP16",
    "exp_fp16x2": "packed FP16",
    "reduction_fp16_scalar": "scalar FP16",
    "reduction_fp16x2": "packed FP16",
    "normalization_fp16_scalar": "scalar FP16",
    "normalization_fp16x2": "packed FP16",
}
POLICY_COLOURS = {
    "fp16_io_fp32_all": BASELINE,
    "exp_fp16_scalar": SCALAR,
    "exp_fp16x2": PACKED,
    "reduction_fp16_scalar": SCALAR,
    "reduction_fp16x2": PACKED,
    "normalization_fp16_scalar": SCALAR,
    "normalization_fp16x2": PACKED,
}


def configure_style() -> None:
    """Use a quiet, readable publication style with Korean-capable fonts."""

    candidates = (
        Path("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    family = "DejaVu Sans"
    for candidate in candidates:
        if candidate.exists():
            font_manager.fontManager.addfont(candidate)
            family = font_manager.FontProperties(fname=candidate).get_name()
            break
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
        raise ValueError(f"{column!r} is not numeric in {row}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{column!r} is not finite in {row}")
    return value


def integer(row: dict[str, str], column: str) -> int:
    try:
        return int(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{column!r} is not an integer in {row}") from exc


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot calculate a mean of no values")
    return statistics.fmean(values)


def descriptive_t95(values: list[float]) -> tuple[float, float, float]:
    """Return mean, low and high t interval; n=3 is descriptive only."""

    average = mean(values)
    if len(values) != 3:
        raise ValueError("this frozen visual design expects exactly n=3 sessions")
    sample_std = statistics.stdev(values)
    half_width = T95_N3 * sample_std / math.sqrt(len(values))
    return average, average - half_width, average + half_width


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


def repo_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def write_figure(fig: plt.Figure, output_dir: Path, stem: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{stem}.png"
    svg_path = output_dir / f"{stem}.svg"
    metadata = {"Creator": Path(__file__).name, "Date": None}
    fig.savefig(png_path, dpi=220, bbox_inches="tight", facecolor="white", metadata=metadata)
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white", metadata=metadata)
    normalize_svg(svg_path)
    plt.close(fig)
    return [png_path, svg_path]


def load_inputs(run_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    analysis_dir = run_dir / "analysis"
    cells_path = analysis_dir / "validated_cells.csv"
    summary_path = analysis_dir / "summary.csv"
    analysis_path = analysis_dir / "analysis.json"
    manifest_path = run_dir / "manifest.json"
    if (
        not cells_path.is_file()
        or not summary_path.is_file()
        or not analysis_path.is_file()
        or not manifest_path.is_file()
    ):
        raise FileNotFoundError(
            "missing analyzer output or run manifest; run analyze_softmax_whole_precision_stage_isolation.py first"
        )
    cells = read_csv(cells_path)
    summary = read_csv(summary_path)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    analysis_manifest = analysis.get("manifest", {})
    if analysis.get("schema_version") != "softmax_whole_precision_stage_isolation_analysis_v1":
        raise ValueError("analysis.json has an unexpected stage-isolation schema")
    if analysis.get("allow_partial") is not False:
        raise ValueError("figures require a complete, not partial, analyzed run")
    if analysis.get("primary_metric") != "net_pJ_per_logical_output_element":
        raise ValueError("analysis.json has an unexpected primary metric")
    if analysis.get("interpretation_boundary") != (
        "complete Softmax policy comparison, not EX2 operand-rate ATC or pure SFU/MUFU energy"
    ):
        raise ValueError("analysis.json has an unexpected whole-Softmax interpretation boundary")
    if analysis_manifest.get("sha256") != expected_manifest_sha:
        raise ValueError("analysis.json does not bind to the current manifest SHA-256")
    if analysis_manifest.get("run_tag") != manifest.get("run_tag"):
        raise ValueError("analysis.json run tag does not match the current manifest")
    if analysis_manifest.get("protocol_revision") != manifest.get("protocol_revision"):
        raise ValueError("analysis.json protocol revision does not match the current manifest")
    return cells, summary, analysis


def validate_inputs(
    cells: list[dict[str, str]], summary: list[dict[str, str]], analysis: dict[str, Any]
) -> None:
    if analysis.get("status") != "pass" or analysis.get("validated_cell_count") != 27:
        raise ValueError("analysis.json does not certify a 27-cell passing run")
    if len(cells) != 27:
        raise ValueError(f"expected 27 validated cells, found {len(cells)}")
    if len(summary) != 15:
        raise ValueError(f"expected 15 summary rows, found {len(summary)}")
    observed = {(row["stage_group"], row["policy"]) for row in cells}
    expected = {(stage, policy) for stage in STAGES for policy in POLICIES[stage]}
    if observed != expected:
        raise ValueError("validated cells do not contain the frozen stage/policy matrix")
    for stage in STAGES:
        for policy in POLICIES[stage]:
            group = [row for row in cells if row["stage_group"] == stage and row["policy"] == policy]
            if len(group) != 3:
                raise ValueError(f"{stage}/{policy} is not represented by three fresh sessions")
            if {integer(row, "session_index_within_stage") for row in group} != {1, 2, 3}:
                raise ValueError(f"{stage}/{policy} does not occupy all three session positions")


def by_stage_policy(cells: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in cells:
        grouped[(row["stage_group"], row["policy"])].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: integer(item, "session_index_within_stage"))
    return grouped


def by_stage_session(cells: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in cells:
        key = (row["stage_group"], integer(row, "session_index_within_stage"))
        grouped[key][row["policy"]] = row
    return grouped


def plot_absolute_session_spread(
    grouped: dict[tuple[str, str], list[dict[str, str]]], output_dir: Path
) -> list[Path]:
    """Faceted absolute values, with raw sessions and descriptive mean intervals."""

    fig, axes = plt.subplots(1, 3, figsize=(15.8, 5.4), sharey=True)
    for index, stage in enumerate(STAGES):
        ax = axes[index]
        policies = POLICIES[stage]
        for position, policy in enumerate(policies):
            rows = grouped[(stage, policy)]
            values = [number(row, "net_pJ_per_logical_output_element") for row in rows]
            average, low, high = descriptive_t95(values)
            colour = POLICY_COLOURS[policy]
            jitter = (-0.12, 0.0, 0.12)
            for row, offset in zip(rows, jitter):
                session = integer(row, "session_index_within_stage")
                ax.scatter(
                    position + offset,
                    number(row, "net_pJ_per_logical_output_element"),
                    marker=SESSION_MARKERS[session],
                    s=46,
                    facecolor="white",
                    edgecolor=colour,
                    linewidth=1.5,
                    zorder=3,
                )
            ax.vlines(position, low, high, color=colour, linewidth=1.8, zorder=2)
            ax.scatter(position, average, marker="D", s=55, color=colour, zorder=4)
            ax.text(position, average + 145, f"{average:,.0f}", ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_title(STAGE_LABELS[stage], loc="left", fontweight="bold", pad=10)
        ax.set_xticks(range(3), [POLICY_LABELS[policy] for policy in policies])
        # The reduction-scalar descriptive n=3 interval reaches above 5k;
        # keep the shared absolute scale at zero and leave its full interval
        # visible rather than clipping it for visual compactness.
        ax.set_ylim(0, 6000)
        style_axis(ax)
    axes[0].set_ylabel("net pJ / logical output element")
    fig.suptitle(
        "Whole-Softmax energy by isolated precision stage",
        x=0.07,
        ha="left",
        y=1.02,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.955,
        "RTX 3090 · S=512 · grid=16 CTA · FP16 I/O held fixed · raw fresh sessions (n=3) + descriptive t95 interval",
        ha="left",
        color=MUTED,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], marker="D", color="none", markerfacecolor=BASELINE, label="mean"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=INK, label="fresh session"),
        ],
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, -0.035),
        frameon=False,
    )
    fig.subplots_adjust(left=0.075, right=0.985, top=0.82, bottom=0.20, wspace=0.10)
    return write_figure(fig, output_dir, f"{PREFIX}_absolute_session_spread")


def paired_deltas(
    grouped: dict[tuple[str, int], dict[str, dict[str, str]]]
) -> dict[tuple[str, str], list[float]]:
    result: dict[tuple[str, str], list[float]] = {}
    for stage in STAGES:
        baseline = POLICIES[stage][0]
        for policy in POLICIES[stage][1:]:
            values = []
            for session in (1, 2, 3):
                session_rows = grouped[(stage, session)]
                values.append(
                    number(session_rows[policy], "net_pJ_per_logical_output_element")
                    - number(session_rows[baseline], "net_pJ_per_logical_output_element")
                )
            result[(stage, policy)] = values
    return result


def plot_paired_contrasts(
    session_grouped: dict[tuple[str, int], dict[str, dict[str, str]]], output_dir: Path
) -> list[Path]:
    """Forest-style paired contrasts; zero is the common FP32-stage baseline."""

    contrasts = paired_deltas(session_grouped)
    entries = [(stage, policy) for stage in STAGES for policy in POLICIES[stage][1:]]
    fig, ax = plt.subplots(figsize=(12.3, 6.3))
    positions = list(reversed(range(len(entries))))
    for y, (stage, policy) in zip(positions, entries):
        values = contrasts[(stage, policy)]
        average, low, high = descriptive_t95(values)
        colour = POLICY_COLOURS[policy]
        ax.hlines(y, low, high, color=colour, linewidth=2.0, zorder=2)
        ax.scatter(average, y, marker="D", s=60, color=colour, zorder=4)
        for value, session in zip(values, (1, 2, 3)):
            ax.scatter(
                value,
                y,
                marker=SESSION_MARKERS[session],
                s=44,
                facecolor="white",
                edgecolor=colour,
                linewidth=1.5,
                zorder=3,
            )
        label = f"{STAGE_SHORT_LABELS[stage]} · {POLICY_LABELS[policy].replace(chr(10), ' ')}"
        ax.text(3850, y, f"mean {average:+,.0f}", ha="right", va="center", fontsize=9, color=INK)
        ax.text(-2450, y, label, ha="left", va="center", fontsize=10, color=INK)
    ax.axvline(0, color=INK, linewidth=1.15, zorder=1)
    ax.set_xlim(-2550, 3950)
    ax.set_ylim(-0.9, len(entries) - 0.1)
    ax.set_yticks([])
    ax.set_xlabel("paired delta vs FP32-stage baseline (net pJ / logical output element)")
    style_axis(ax, grid_axis="x")
    fig.suptitle(
        "Paired stage contrasts vs common FP32-stage baseline",
        x=0.08,
        ha="left",
        y=0.98,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.925,
        "Diamonds and horizontal bars: mean and descriptive t95 interval (n=3). Open markers: the three paired fresh sessions. Negative is lower measured net energy.",
        ha="left",
        color=MUTED,
    )
    fig.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.12)
    return write_figure(fig, output_dir, f"{PREFIX}_paired_contrasts")


def plot_within_session_paths(
    session_grouped: dict[tuple[str, int], dict[str, dict[str, str]]], output_dir: Path
) -> list[Path]:
    """Show the exact three-policy paths inside each fresh process/session."""

    fig, axes = plt.subplots(1, 3, figsize=(15.8, 5.4), sharey=True)
    for index, stage in enumerate(STAGES):
        ax = axes[index]
        policies = POLICIES[stage]
        for session in (1, 2, 3):
            rows = session_grouped[(stage, session)]
            values = [number(rows[policy], "net_pJ_per_logical_output_element") for policy in policies]
            order = rows[policies[0]]["session_order"]
            ax.plot(
                range(3),
                values,
                color=SESSION_COLOURS[session],
                linewidth=1.8,
                marker=SESSION_MARKERS[session],
                markersize=6.2,
                label=f"session {session} ({order})",
                zorder=2,
            )
        ax.set_title(STAGE_LABELS[stage], loc="left", fontweight="bold", pad=10)
        ax.set_xticks(range(3), [POLICY_LABELS[policy] for policy in policies])
        ax.set_ylim(0, 5000)
        style_axis(ax)
    axes[0].set_ylabel("net pJ / logical output element")
    fig.suptitle(
        "Within-session paired policy paths",
        x=0.07,
        ha="left",
        y=1.02,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.955,
        "Each stage cycles policy positions as ABC, CAB, BCA; lines connect only the three roles measured in the same fresh CUDA process.",
        ha="left",
        color=MUTED,
    )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.035), frameon=False)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.82, bottom=0.20, wspace=0.20)
    return write_figure(fig, output_dir, f"{PREFIX}_within_session_paths")


def plot_quality_gates(cells: list[dict[str, str]], output_dir: Path) -> list[Path]:
    """Make preheat, trace, and temperature evidence visible without pooling cells."""

    ordered = sorted(
        cells,
        key=lambda row: (
            STAGES.index(row["stage_group"]),
            integer(row, "session_index_within_stage"),
            integer(row, "sequence_index"),
        ),
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 4.8), gridspec_kw={"width_ratios": (1.0, 1.0, 1.18)})
    session_rows: dict[tuple[str, int], dict[str, str]] = {}
    for row in ordered:
        session_rows.setdefault((row["stage_group"], integer(row, "session_index_within_stage")), row)
    sessions = sorted(session_rows, key=lambda item: (STAGES.index(item[0]), item[1]))
    xs = list(range(1, len(sessions) + 1))
    preheats = [number(session_rows[key], "preheat_actual_s") for key in sessions]
    axes[0].scatter(xs, preheats, color=BASELINE, s=45, zorder=3)
    axes[0].axhline(20, color=INK, linewidth=1.1, label="requested 20 s")
    axes[0].axhspan(16, 25, color=LIGHT, zorder=0, label="accepted gate")
    axes[0].set_ylim(15.5, 25.5)
    axes[0].set_xticks(xs, [f"{stage[:3]}-{session}" for stage, session in sessions], rotation=35, ha="right")
    axes[0].set_ylabel("seconds")
    axes[0].set_title("Shared baseline preheat", loc="left", fontweight="bold")
    axes[0].legend(loc="upper right", frameon=False, fontsize=8)
    style_axis(axes[0])

    role_x = list(range(1, len(ordered) + 1))
    r2 = [number(row, "energy_trace_r2") for row in ordered]
    colours = [POLICY_COLOURS[row["policy"]] for row in ordered]
    axes[1].scatter(role_x, r2, c=colours, s=35, edgecolor="white", linewidth=0.5, zorder=3)
    axes[1].axhline(0.98, color=INK, linewidth=1.1, label="gate 0.98")
    axes[1].set_ylim(0.979, 1.0001)
    axes[1].set_xlabel("measured role (27 total)")
    axes[1].set_ylabel("Theil–Sen energy-trace $R^2$")
    axes[1].set_title("Qualified energy traces", loc="left", fontweight="bold")
    axes[1].legend(loc="lower right", frameon=False, fontsize=8)
    style_axis(axes[1])

    starts = [number(row, "temperature_start_C") for row in ordered]
    ends = [number(row, "temperature_end_C") for row in ordered]
    for x, start, end, colour in zip(role_x, starts, ends, colours):
        axes[2].plot([x, x], [start, end], color=colour, alpha=0.72, linewidth=1.4, zorder=2)
    axes[2].scatter(role_x, starts, c="white", edgecolor=INK, linewidth=0.8, s=32, marker="o", label="start", zorder=3)
    axes[2].scatter(role_x, ends, c=INK, edgecolor="white", linewidth=0.5, s=34, marker="^", label="end", zorder=3)
    axes[2].set_xlabel("measured role (27 total)")
    axes[2].set_ylabel("GPU temperature (°C)")
    axes[2].set_title("Recorded thermal range", loc="left", fontweight="bold")
    axes[2].legend(loc="upper left", frameon=False, fontsize=8)
    style_axis(axes[2])

    fig.suptitle(
        "Measurement-quality gates retained for all 27 roles",
        x=0.065,
        ha="left",
        y=1.02,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.065,
        0.95,
        "Temperature is recorded context, not a hard rejection rule. All roles also passed the SMID and numerical validation gates.",
        ha="left",
        color=MUTED,
    )
    fig.subplots_adjust(left=0.065, right=0.985, top=0.80, bottom=0.21, wspace=0.36)
    return write_figure(fig, output_dir, f"{PREFIX}_quality_gates")


def build_manifest(
    run_dir: Path, output_dir: Path, generated: list[Path], analysis: dict[str, Any]
) -> Path:
    """Write a small, reproducible figure inventory for docs and report linkage."""

    figures = []
    for path in generated:
        if path.suffix != ".png":
            continue
        figures.append(
            {
                "png": repo_or_absolute(path),
                "svg": repo_or_absolute(path.with_suffix(".svg")),
            }
        )
    payload = {
        "schema_version": "softmax_whole_precision_stage_isolation_figures_v1",
        "run_dir": repo_or_absolute(run_dir),
        "analysis_input": repo_or_absolute(run_dir / "analysis" / "analysis.json"),
        "analyzed_run_manifest_sha256": analysis["manifest"]["sha256"],
        "primary_unit": "net pJ per logical Softmax output element",
        "fresh_sessions_per_stage_policy": 3,
        "figures": figures,
    }
    path = output_dir / f"{PREFIX}_figure_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.out_dir.resolve()
    configure_style()
    cells, summary, analysis = load_inputs(run_dir)
    validate_inputs(cells, summary, analysis)
    stage_policy = by_stage_policy(cells)
    stage_session = by_stage_session(cells)
    generated: list[Path] = []
    generated.extend(plot_absolute_session_spread(stage_policy, output_dir))
    generated.extend(plot_paired_contrasts(stage_session, output_dir))
    generated.extend(plot_within_session_paths(stage_session, output_dir))
    generated.extend(plot_quality_gates(cells, output_dir))
    manifest = build_manifest(run_dir, output_dir, generated, analysis)
    print(f"figure_status=pass")
    print(f"output_dir={output_dir}")
    for path in generated:
        print(f"figure={path}")
    print(f"figure_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
