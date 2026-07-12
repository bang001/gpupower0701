#!/usr/bin/env python3
"""Plot the current RTX 3090 DRAM reporting band and its evidence boundary."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "results" / "summary" / "rtx3090_dram_current_reporting_policy_20260712.csv"
DEFAULT_OUT = ROOT / "docs" / "assets" / "component_energy_method" / "current_dram_reporting_band.png"

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
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
    plt.rcParams.update({"font.family": family, "font.size": 11, "text.color": INK})


def read_policy() -> dict[str, str]:
    with POLICY.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"expected one DRAM reporting row in {POLICY}")
    return rows[0]


def self_test(row: dict[str, str]) -> None:
    low = float(row["estimate_low"])
    high = float(row["estimate_high"])
    midpoint = float(row["midpoint"])
    assert row["unit"] == "pJ/bit"
    assert row["reporting_status"] == "provisional_reference_aligned_range"
    assert row["strict_eligible"].lower() == "false"
    assert low < midpoint < high
    assert abs(midpoint - (low + high) / 2.0) < 1e-9
    assert abs(low * 8.0 - 213.672) < 1e-9
    assert abs(high * 8.0 - 227.272) < 1e-9


def plot(row: dict[str, str], output: Path) -> None:
    low = float(row["estimate_low"])
    high = float(row["estimate_high"])
    midpoint = float(row["midpoint"])
    fig, ax = plt.subplots(figsize=(13.5, 5.4))
    ax.axvspan(low, high, color=AMBER_PALE, zorder=1)
    ax.hlines(0, low, high, color=AMBER, linewidth=12, zorder=3)
    ax.scatter([low, midpoint, high], [0, 0, 0], color=[AMBER, INK, AMBER], s=[110, 150, 110], zorder=4)
    ax.text(low - 0.2, 0.12, f"하한  {low:.3f}", ha="right", va="bottom", fontweight="bold", color=INK)
    ax.text(midpoint, 0.34, f"midpoint\n{midpoint:.3f}", ha="center", va="bottom", fontweight="bold", color=INK)
    ax.text(high + 0.2, 0.12, f"{high:.3f}  상한", ha="left", va="bottom", fontweight="bold", color=INK)
    ax.text(
        midpoint,
        -0.23,
        "provisional reference-aligned cumulative effective path band",
        ha="center",
        va="top",
        color=AMBER,
        fontweight="bold",
    )
    ax.text(
        0.01,
        0.93,
        "현재 저장소에는 matched-ITER global_addr_only pair가 없으므로 accepted 실측 coefficient가 아니다.",
        transform=ax.transAxes,
        color=RED,
        fontweight="bold",
    )
    ax.text(
        0.01,
        0.06,
        "확정 조건: dram_cg_load_only - global_addr_only · 동일 ITER · NVML total-energy delta · exact NCU dram_bytes × 8 · strict audits",
        transform=ax.transAxes,
        color=MUTED,
    )
    ax.set_xlim(0, 32)
    ax.set_ylim(-0.55, 0.65)
    ax.set_yticks([])
    ax.set_xlabel("Effective path energy [pJ/bit]")
    ax.set_title("RTX 3090 DRAM 최신 보고 범위", loc="left", fontsize=18, fontweight="bold", pad=20)
    ax.grid(axis="x", color=LINE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    svg_output = output.with_suffix(".svg")
    fig.savefig(svg_output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    normalized_svg = "\n".join(line.rstrip() for line in svg_output.read_text(encoding="utf-8").splitlines()) + "\n"
    svg_output.write_text(normalized_svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    configure_style()
    row = read_policy()
    self_test(row)
    if args.self_test:
        print("DRAM reporting policy self-test passed")
        return 0
    plot(row, args.output)
    print(f"wrote {args.output}")
    print(f"wrote {args.output.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
