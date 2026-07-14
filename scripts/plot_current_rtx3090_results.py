#!/usr/bin/env python3
"""Plot the current RTX 3090 coefficients and accepted NCU path evidence."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LogNorm
from matplotlib.ticker import NullFormatter, ScalarFormatter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "docs" / "assets" / "component_energy_method"

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
ZERO = "#EEF2F3"
BLUE = "#2E6F9E"
GREEN = "#3A7D5D"
GOLD = "#B88719"
ORANGE = "#D06F2B"
PINK = "#A84D75"

COMPONENT_LABELS = {
    "tensor_mma_increment": "Tensor MMA increment",
    "shared_l1_scalar_path": "Shared scalar path",
    "global_l1_hit_path": "Global L1 hit path",
    "l2_hit_cg_path": "L2 CG hit path",
    "external_memory_read_path": "External-memory read path",
}

PATH_MODES = {
    "Shared scalar": "shared_scalar_load_only",
    "Global L1": "global_l1_load_only",
    "L2 CG": "l2_cg_load_only",
    "External read": "dram_cg_load_only",
}


def configure_style() -> None:
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
            "xtick.color": MUTED,
            "ytick.color": INK,
            "axes.titlecolor": INK,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_svg(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def number(row: dict[str, str], column: str) -> float:
    value = row.get(column, "")
    if value == "":
        return float("nan")
    try:
        result = float(value)
    except ValueError:
        return float("nan")
    return result if math.isfinite(result) else float("nan")


def finite_median(rows: list[dict[str, str]], column: str) -> float:
    values = [number(row, column) for row in rows]
    values = [value for value in values if math.isfinite(value)]
    return statistics.median(values) if values else float("nan")


def engineering(value: float, *, count: bool = False) -> str:
    if not math.isfinite(value) or value <= 0.0:
        return "0"
    units = [(1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k")]
    for scale, suffix in units:
        if value >= scale:
            unit = "" if count else "B"
            return f"{value / scale:.3g} {suffix}{unit}"
    return f"{value:.3g}" + ("" if count else " B")


def coefficient_record(row: dict[str, str]) -> tuple[float, float, float, str]:
    unit = row["unit"]
    if unit == "pJ/FLOP":
        return (
            number(row, "median"),
            number(row, "median_ci_low"),
            number(row, "median_ci_high"),
            unit,
        )
    return (
        number(row, "median_pJ_per_bit"),
        number(row, "median_pJ_per_bit_ci_low"),
        number(row, "median_pJ_per_bit_ci_high"),
        "pJ/bit",
    )


def plot_coefficients(rows: list[dict[str, str]], output: Path, *, tag: str) -> None:
    by_component = {row["component"]: row for row in rows}
    tensor = coefficient_record(by_component["tensor_mma_increment"])
    memory_keys = [
        "shared_l1_scalar_path",
        "global_l1_hit_path",
        "l2_hit_cg_path",
        "external_memory_read_path",
    ]
    colors = [GREEN, BLUE, GOLD, ORANGE]

    fig, (tensor_ax, memory_ax) = plt.subplots(
        1, 2, figsize=(14.2, 5.8), gridspec_kw={"width_ratios": [0.9, 1.65]}
    )

    tensor_value, tensor_low, tensor_high, _ = tensor
    tensor_ax.errorbar(
        tensor_value,
        0,
        xerr=[[tensor_value - tensor_low], [tensor_high - tensor_value]],
        fmt="o",
        markersize=11,
        color=BLUE,
        ecolor=BLUE,
        elinewidth=3,
        capsize=7,
    )
    tensor_ax.text(
        tensor_value,
        0.12,
        f"{tensor_value:.3f} pJ/FLOP\n95% bootstrap CI {tensor_low:.3f}-{tensor_high:.3f}",
        ha="center",
        va="bottom",
        color=BLUE,
        fontweight="bold",
    )
    tensor_ax.set_xlim(0, max(2.7, tensor_high * 1.2))
    tensor_ax.set_ylim(-0.35, 0.45)
    tensor_ax.set_yticks([0], ["Tensor MMA increment"])
    tensor_ax.set_xlabel("Effective coefficient [pJ/FLOP]")
    tensor_ax.set_title("A. Tensor treatment-control coefficient", loc="left", fontweight="bold")
    tensor_ax.grid(axis="x", color=LINE, linewidth=0.8)
    tensor_ax.tick_params(axis="y", length=0)

    positions = list(range(len(memory_keys)))
    for position, key, color in zip(positions, memory_keys, colors):
        value, low, high, _ = coefficient_record(by_component[key])
        is_external = key == "external_memory_read_path"
        memory_ax.errorbar(
            value,
            position,
            xerr=[[value - low], [high - value]],
            fmt="D" if is_external else "o",
            markersize=9,
            markerfacecolor="white" if is_external else color,
            markeredgecolor=color,
            markeredgewidth=2,
            ecolor=color,
            elinewidth=2.5,
            capsize=6,
        )
        memory_ax.text(
            value * 1.12,
            position,
            f"{value:.3f} pJ/bit",
            va="center",
            color=color,
            fontweight="bold",
        )
    memory_ax.set_xscale("log")
    memory_ax.set_xlim(0.35, 45)
    memory_ax.set_xticks([0.5, 1, 2, 5, 10, 20, 40])
    memory_ax.get_xaxis().set_major_formatter(ScalarFormatter())
    memory_ax.set_yticks(
        positions,
        [COMPONENT_LABELS[key] for key in memory_keys],
    )
    memory_ax.invert_yaxis()
    memory_ax.set_xlabel("Effective coefficient [pJ/bit], log scale")
    memory_ax.set_title("B. Memory-path coefficients", loc="left", fontweight="bold")
    memory_ax.grid(axis="x", which="both", color=LINE, linewidth=0.8)
    memory_ax.tick_params(axis="y", length=0)

    for ax in (tensor_ax, memory_ax):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_axisbelow(True)

    fig.suptitle(
        "RTX 3090 current component-energy coefficients",
        x=0.06,
        y=0.99,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.015,
        f"Tag {tag}. Medians and bootstrap median CIs from accepted matched-control rows. "
        "The open diamond is an accepted GPU-device external-read effective path, not physical GDDR6X energy.",
        color=MUTED,
    )
    fig.subplots_adjust(left=0.16, right=0.96, top=0.84, bottom=0.20, wspace=0.38)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    svg_output = output.with_suffix(".svg")
    fig.savefig(svg_output, bbox_inches="tight", facecolor="white")
    normalize_svg(svg_output)
    plt.close(fig)


def path_rows(
    acceptance_rows: list[dict[str, str]], mode: str
) -> list[dict[str, str]]:
    return [
        row
        for row in acceptance_rows
        if row.get("mode") == mode and row.get("acceptance") == "accepted"
    ]


def matrix_values(
    acceptance_rows: list[dict[str, str]], columns: list[str]
) -> tuple[list[str], list[list[float]], list[float]]:
    labels: list[str] = []
    matrix: list[list[float]] = []
    stalls: list[float] = []
    for label, mode in PATH_MODES.items():
        rows = path_rows(acceptance_rows, mode)
        labels.append(label)
        matrix.append([finite_median(rows, column) for column in columns])
        stalls.append(finite_median(rows, "stall_long_scoreboard_pct"))
    return labels, matrix, stalls


def draw_log_matrix(ax, values, row_labels, col_labels, *, count: bool) -> None:
    positive = [
        value
        for row in values
        for value in row
        if math.isfinite(value) and value > 0.0
    ]
    vmin = min(positive)
    vmax = max(positive)
    plotted = [
        [value if math.isfinite(value) and value > 0.0 else float("nan") for value in row]
        for row in values
    ]
    image = ax.imshow(
        plotted,
        aspect="auto",
        cmap="YlGnBu",
        norm=LogNorm(vmin=vmin, vmax=vmax),
    )
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            if not math.isfinite(value) or value <= 0.0:
                text_value = "0"
                color = MUTED
            else:
                text_value = engineering(value, count=count)
                normalized = image.norm(value)
                color = "white" if normalized > 0.58 else INK
            ax.text(
                column_index,
                row_index,
                text_value,
                ha="center",
                va="center",
                color=color,
                fontweight="bold",
                fontsize=9.2,
            )
    ax.set_xticks(range(len(col_labels)), col_labels)
    ax.set_yticks(range(len(row_labels)), row_labels)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_color("white")


def plot_ncu_evidence(
    acceptance_rows: list[dict[str, str]], output: Path, *, tag: str
) -> None:
    byte_columns = [
        "shared_read_bytes",
        "l1_request_bytes",
        "l2_read_bytes",
        "dram_read_bytes",
    ]
    access_columns = ["l1_accesses", "l2_accesses", "dram_accesses"]
    labels, byte_values, stalls = matrix_values(acceptance_rows, byte_columns)
    _, access_values, _ = matrix_values(acceptance_rows, access_columns)

    fig = plt.figure(figsize=(14.4, 9.4))
    grid = fig.add_gridspec(
        2, 2, width_ratios=[1.7, 1.0], height_ratios=[1.0, 0.88], hspace=0.48, wspace=0.34
    )
    byte_ax = fig.add_subplot(grid[0, :])
    access_ax = fig.add_subplot(grid[1, 0])
    stall_ax = fig.add_subplot(grid[1, 1])

    draw_log_matrix(
        byte_ax,
        byte_values,
        labels,
        ["Shared read", "L1 request", "L2 read", "DRAM read"],
        count=False,
    )
    byte_ax.set_title(
        "A. Median path traffic from accepted treatment rows",
        loc="left",
        fontweight="bold",
        pad=13,
    )
    byte_ax.set_xlabel("Traffic counter [byte]; cell color uses log scale")

    draw_log_matrix(
        access_ax,
        access_values,
        labels,
        ["L1 access", "L2 access", "DRAM access"],
        count=True,
    )
    access_ax.set_title(
        "B. Median access counts", loc="left", fontweight="bold", pad=13
    )
    access_ax.set_xlabel("RTX 3090 summary units: sectors")

    positions = list(range(len(labels)))
    colors = [GREEN, BLUE, GOLD, ORANGE]
    stall_ax.barh(positions, stalls, color=colors, height=0.55)
    for position, value, color in zip(positions, stalls, colors):
        stall_ax.text(
            value * 1.18,
            position,
            f"{value:.4g}",
            va="center",
            color=color,
            fontweight="bold",
        )
    stall_ax.set_xscale("log")
    stall_ax.set_xlim(3e-4, max(stalls) * 2.5)
    stall_ticks = [1e-3, 1e-2, 1e-1, 1, 10, 100, 1000]
    stall_ax.set_xticks(
        stall_ticks,
        ["0.001", "0.01", "0.1", "1", "10", "100", "1000"],
    )
    stall_ax.xaxis.set_minor_formatter(NullFormatter())
    stall_ax.set_yticks(positions, labels)
    stall_ax.invert_yaxis()
    stall_ax.set_xlabel("Long-scoreboard signal [%-like, log scale]")
    stall_ax.set_title(
        "C. Median long-scoreboard status", loc="left", fontweight="bold", pad=13
    )
    stall_ax.grid(axis="x", which="both", color=LINE, linewidth=0.8)
    stall_ax.spines[["top", "right", "left"]].set_visible(False)
    stall_ax.tick_params(axis="y", length=0)
    stall_ax.set_axisbelow(True)

    fig.suptitle(
        "RTX 3090 current NCU path evidence",
        x=0.08,
        y=0.985,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.015,
        f"Tag {tag}. Every plotted treatment row and its exact-coordinate control passed acceptance. "
        "Long scoreboard is an NCU per-issue-active derived signal; values above 100 are not elapsed-time percentages.",
        color=MUTED,
    )
    fig.subplots_adjust(left=0.18, right=0.95, top=0.90, bottom=0.10)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    svg_output = output.with_suffix(".svg")
    fig.savefig(svg_output, bbox_inches="tight", facecolor="white")
    normalize_svg(svg_output)
    plt.close(fig)


def self_test(
    coefficient_rows: list[dict[str, str]], acceptance_rows: list[dict[str, str]]
) -> None:
    expected_components = set(COMPONENT_LABELS)
    actual_components = {row.get("component", "") for row in coefficient_rows}
    if actual_components != expected_components:
        raise AssertionError(
            f"expected current component rows {sorted(expected_components)}, got {sorted(actual_components)}"
        )
    for row in coefficient_rows:
        median, low, high, _ = coefficient_record(row)
        if not (0.0 < low <= median <= high):
            raise AssertionError(f"invalid coefficient interval: {row}")

    accepted_rows = [row for row in acceptance_rows if row.get("acceptance") == "accepted"]
    rejected_rows = [row for row in acceptance_rows if row.get("acceptance") == "rejected"]
    if len(accepted_rows) != 72 or len(rejected_rows) != 1:
        raise AssertionError(
            f"expected 72 accepted plus one baseline reject, got {len(accepted_rows)}/{len(rejected_rows)}"
        )
    for label, mode in PATH_MODES.items():
        rows = path_rows(acceptance_rows, mode)
        if not rows:
            raise AssertionError(f"missing accepted rows for {label}/{mode}")
        if not math.isfinite(finite_median(rows, "stall_long_scoreboard_pct")):
            raise AssertionError(f"missing long-scoreboard evidence for {label}/{mode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="20260714")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    summary_path = (
        ROOT
        / "results"
        / "summary"
        / f"rtx3090_component_finalplan_{args.tag}_matched_control_summary.csv"
    )
    acceptance_path = (
        ROOT
        / "results"
        / "summary"
        / f"rtx3090_component_finalplan_{args.tag}_ncu_acceptance.csv"
    )
    coefficient_rows = read_csv(summary_path)
    acceptance_rows = read_csv(acceptance_path)
    self_test(coefficient_rows, acceptance_rows)
    if args.self_test:
        print("current RTX 3090 visualization self-test passed")
        return 0

    configure_style()
    coefficient_out = args.out_dir / f"rtx3090_current_component_coefficients_{args.tag}.png"
    ncu_out = args.out_dir / f"rtx3090_current_ncu_path_evidence_{args.tag}.png"
    plot_coefficients(coefficient_rows, coefficient_out, tag=args.tag)
    plot_ncu_evidence(acceptance_rows, ncu_out, tag=args.tag)
    for path in (coefficient_out, coefficient_out.with_suffix(".svg"), ncu_out, ncu_out.with_suffix(".svg")):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
