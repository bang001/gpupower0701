#!/usr/bin/env python3
"""Plot external-memory observations and device references by scope."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
DATA = (
    ROOT
    / "results"
    / "summary"
    / "external_memory_scope_comparison_20260714.csv"
)
DEFAULT_OUT = (
    ROOT
    / "docs"
    / "assets"
    / "component_energy_method"
    / "external_memory_scope_comparison.png"
)

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
BLUE = "#2E6F9E"
BLUE_PALE = "#E4EFF7"
AMBER = "#D78A26"
AMBER_PALE = "#FBEED9"
RED = "#B94B4B"


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
        }
    )


def read_rows() -> list[dict[str, str]]:
    with DATA.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def self_test(rows: list[dict[str, str]]) -> None:
    observed = {
        row["label"]: float(row["value_pj_per_bit"])
        for row in rows
        if row["evidence_class"] == "user_reported_observation"
    }
    references = {
        row["label"]: float(row["value_pj_per_bit"])
        for row in rows
        if row["evidence_class"] == "literature_reference"
    }
    path_references = {
        row["label"]: float(row["value_pj_per_bit"])
        for row in rows
        if row["evidence_class"] == "literature_path_reference"
    }
    assert observed == {"RTX 3090": 25.510, "A100": 11.925, "V100": 8.131}
    assert references == {"HBM2 device model": 3.97, "GDDR5 device model": 14.0}
    assert path_references == {
        "K40 DRAM-to-L2": 30.55,
        "Modeled HBM GPU system": 21.1,
    }
    assert all(row["strict_eligible"].lower() == "false" for row in rows)
    assert {
        row["coefficient_scope"]
        for row in rows
        if row["evidence_class"] == "user_reported_observation"
    } == {"effective_gpu_device_external_read_path"}
    assert {
        row["coefficient_scope"]
        for row in rows
        if row["evidence_class"] == "literature_reference"
    } == {"memory_device_access_model"}


def draw_panel(
    ax,
    rows: list[dict[str, str]],
    *,
    color: str,
    pale: str,
    title: str,
    subtitle: str,
) -> None:
    labels = [row["label"] for row in rows]
    values = [float(row["value_pj_per_bit"]) for row in rows]
    positions = list(range(len(rows)))
    bars = ax.barh(
        positions,
        values,
        height=0.56,
        color=pale,
        edgecolor=color,
        linewidth=1.5,
    )
    for bar, value in zip(bars, values):
        ax.text(
            value + 0.45,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f} pJ/bit",
            va="center",
            color=color,
            fontweight="bold",
        )
    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 36)
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=17)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=MUTED, va="bottom")
    ax.grid(axis="x", color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)


def plot(rows: list[dict[str, str]], output: Path) -> None:
    observed = [
        row for row in rows if row["evidence_class"] == "user_reported_observation"
    ]
    references = [
        row for row in rows if row["evidence_class"] == "literature_reference"
    ]
    path_references = [
        row for row in rows if row["evidence_class"] == "literature_path_reference"
    ]
    fig, axes = plt.subplots(3, 1, figsize=(13.5, 9.6), sharex=True)
    draw_panel(
        axes[0],
        observed,
        color=BLUE,
        pale=BLUE_PALE,
        title="A. User-reported external-memory read-path observations",
        subtitle=(
            "NVML GPU-device energy delta / NCU external-read bit; "
            "raw packages unavailable here, strict rerun required"
        ),
    )
    draw_panel(
        axes[1],
        path_references,
        color="#3A7D5D",
        pale="#E4F1EA",
        title="B. Literature transaction/system-path references",
        subtitle=(
            "GPUJoule K40 hardware EPT and HPCA 2019 modeled HBM GPU-system path; "
            "historical context, not direct A100/V100/RTX measurement"
        ),
    )
    draw_panel(
        axes[2],
        references,
        color=AMBER,
        pale=AMBER_PALE,
        title="C. Literature memory-device/access references",
        subtitle=(
            "Fine-Grained DRAM, MICRO 2017; GDDR5 is not a GDDR6X reference"
        ),
    )
    axes[2].set_xlabel("Energy coefficient [pJ/bit]")
    fig.suptitle(
        "External-memory energy values use different measurement scopes",
        x=0.08,
        y=0.985,
        ha="left",
        fontsize=18,
        fontweight="bold",
        color=INK,
    )
    fig.text(
        0.08,
        0.015,
        "Do not interpret gaps between panels as pure controller/PHY overhead: "
        "the numerator, workload, process, memory generation, and measurement boundary differ.",
        color=RED,
        fontweight="bold",
    )
    fig.subplots_adjust(left=0.25, right=0.95, top=0.90, bottom=0.09, hspace=0.72)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    svg_output = output.with_suffix(".svg")
    fig.savefig(svg_output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    configure_style()
    rows = read_rows()
    self_test(rows)
    if args.self_test:
        print("external-memory scope visualization self-test passed")
        return 0
    plot(rows, args.output)
    print(f"wrote {args.output}")
    print(f"wrote {args.output.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
