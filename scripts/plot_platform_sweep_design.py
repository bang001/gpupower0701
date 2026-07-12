#!/usr/bin/env python3
"""Plot architecture-aware sweep design for the component-energy experiment."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

from plan_platform_component_experiment import PROFILES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "docs" / "presentations" / "assets"

PLATFORM_ORDER = ["rtx3090", "v100", "a100", "h100"]
LABELS = {
    "rtx3090": "RTX 3090 / GA102",
    "v100": "V100 / GV100",
    "a100": "A100 / GA100",
    "h100": "H100 / GH100",
}
COMBINED_L1_SHARED_KIB = {"rtx3090": 128, "v100": 128, "a100": 192, "h100": 256}
MAX_BLOCKS_PER_SM = {"rtx3090": 16, "v100": 32, "a100": 32, "h100": 32}

INK = "#172A3A"
MUTED = "#667784"
LINE = "#D5DEE2"
PALE = "#F2F5F6"
TEAL = "#187D77"
BLUE = "#2E6F9E"
AMBER = "#D78A26"
PURPLE = "#6655A5"
GREEN = "#3A7D5D"
RED = "#B94B4B"


def ints(csv_values: str) -> list[int]:
    return [int(value) for value in csv_values.split(",") if value]


def configure_style() -> None:
    system_font = Path("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf")
    if system_font.exists():
        font_manager.fontManager.addfont(system_font)
    preferred = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
    if system_font.exists():
        preferred.insert(0, font_manager.FontProperties(fname=system_font).get_name())
    available = {font.name for font in font_manager.fontManager.ttflist}
    font = next((name for name in preferred if name in available), "DejaVu Sans")
    plt.rcParams.update(
        {
            "font.family": font,
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "axes.edgecolor": LINE,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_blocks_per_sm(out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(15.5, 4.65))
    xpos = {value: index for index, value in enumerate([1, 2, 4, 8, 16, 32])}
    for row, profile_name in enumerate(PLATFORM_ORDER[::-1]):
        profile = PROFILES[profile_name]
        values = ints(profile["blocks"])
        anchor = int(profile["ncu_blocks"])
        y = row
        ax.plot([xpos[v] for v in values], [y] * len(values), color=LINE, linewidth=4, zorder=1)
        for value in values:
            is_v100_diagnostic = profile_name == "v100" and value < 32
            color = "#AAB8BF" if is_v100_diagnostic else TEAL
            ax.scatter(xpos[value], y, s=125, color=color, edgecolor="white", linewidth=1.5, zorder=3)
            fraction = 100.0 * value / MAX_BLOCKS_PER_SM[profile_name]
            ax.text(xpos[value], y + 0.18, f"B{value}\n{fraction:.0f}%", ha="center", va="bottom", fontsize=8, color=MUTED)
        ax.scatter(xpos[anchor], y, s=300, marker="D", facecolor=AMBER, edgecolor=INK, linewidth=1.2, zorder=4)
        ax.text(xpos[anchor], y - 0.23, "strict NCU", ha="center", va="top", fontsize=8.5, color=AMBER, fontweight="bold")

    ax.set_yticks(range(4), [LABELS[name] for name in PLATFORM_ORDER[::-1]])
    ax.set_xticks(range(6), ["1", "2", "4", "8", "16", "32"])
    ax.set_xlabel("요청 blocks/SM [count, log2 sweep point]")
    ax.set_xlim(-0.45, 5.45)
    ax.set_ylim(-0.65, 3.75)
    ax.grid(axis="x", color=LINE, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_title("플랫폼별 blocks/SM sweep와 strict NCU anchor", loc="left", color=INK, pad=22)
    ax.text(
        0,
        1.02,
        "V100 B1-B16은 utilization 진단을 넓히는 선택이며 architecture 필수조건이 아니다. "
        "요청 B는 실제 residency를 보장하지 않으므로 NCU occupancy/resource로 검증한다.",
        transform=ax.transAxes,
        fontsize=10,
        color=RED,
        va="bottom",
    )
    path = out_dir / "platform_blocks_per_sm_sweep.png"
    save(fig, path)
    return path


def plot_wsm_paths(out_dir: Path) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(16.0, 7.5), sharex=True, sharey=True)
    paths = [
        ("Shared 명시 경로", "shared_w", TEAL, "s"),
        ("Global L1", "l1_w", BLUE, "o"),
        ("L2 (.cg)", "l2_w", PURPLE, "D"),
        ("DRAM sanity", "dram_w", AMBER, "^"),
    ]
    y_positions = {name: 3 - idx for idx, (name, *_rest) in enumerate(paths)}
    for ax, profile_name in zip(axes.flat, PLATFORM_ORDER):
        profile = PROFILES[profile_name]
        for name, key, color, marker in paths:
            values = ints(profile[key])
            y = y_positions[name]
            ax.plot(values, [y] * len(values), color=color, linewidth=2.4, alpha=0.55)
            ax.scatter(values, [y] * len(values), color=color, marker=marker, s=90, edgecolor="white", linewidth=1.2, zorder=3)
            for value in values:
                ax.annotate(f"{value}", (value, y), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=8, color=color)

        shared_cap = profile["shared_capacity_kib"]
        combined = COMBINED_L1_SHARED_KIB[profile_name]
        l2_equiv = profile["l2_mib"] * 1024.0 / profile["active_sm"]
        ax.axvline(shared_cap, color=TEAL, linestyle=":", linewidth=1.1)
        ax.axvline(combined, color=BLUE, linestyle="--", linewidth=1.1)
        ax.axvline(l2_equiv, color=PURPLE, linestyle="-.", linewidth=1.1)
        ax.text(shared_cap, 3.45, f"shared {shared_cap}", rotation=90, va="top", ha="right", fontsize=7.5, color=TEAL)
        ax.text(combined, 3.45, f"combined {combined}", rotation=90, va="top", ha="left", fontsize=7.5, color=BLUE)
        ax.text(l2_equiv, -0.42, f"L2/SM eq. {l2_equiv:.0f}", rotation=90, va="bottom", ha="right", fontsize=7.5, color=PURPLE)
        ax.set_xscale("log", base=2)
        ax.set_xlim(4, 16384)
        ax.set_ylim(-0.55, 3.65)
        ax.grid(axis="x", color=LINE, linewidth=0.7)
        ax.set_title(LABELS[profile_name], loc="left", color=INK)
        ax.spines[["top", "right", "left"]].set_visible(False)

    for ax in axes[:, 0]:
        ax.set_yticks([3, 2, 1, 0], ["Shared 명시 경로", "Global L1", "L2 (.cg)", "DRAM sanity"])
    for ax in axes[1, :]:
        ax.set_xlabel("W_SM [KiB/SM, log2 scale]")
        ax.set_xticks([8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192], ["8", "16", "32", "64", "128", "256", "512", "1K", "2K", "4K", "8K"])
    fig.suptitle("플랫폼별 W_SM sweep: 의도한 경로 후보이며 자동 cache 이동이 아님", x=0.05, y=0.99, ha="left", fontsize=17, fontweight="bold", color=INK)
    fig.text(
        0.05,
        0.015,
        "Shared는 별도 주소 공간이므로 W_SM 변화로 Global L1이 되지 않는다. Global load는 W_SM과 cache policy(.cg)로 후보를 만들고, "
        "NCU hit/access/bytes가 L1·L2·DRAM 채택을 결정한다.",
        color=RED,
        fontsize=10,
    )
    fig.tight_layout(rect=[0.04, 0.05, 0.99, 0.95])
    path = out_dir / "platform_wsm_path_sweep.png"
    save(fig, path)
    return path


def plot_capacity_context(out_dir: Path) -> Path:
    metrics = ["Shared 예약량 / allocation", "Global L1 W / combined", "L2 전체 WS / capacity"]
    colors = [TEAL, BLUE, PURPLE]
    values: dict[str, list[float]] = {}
    for profile_name in PLATFORM_ORDER:
        p = PROFILES[profile_name]
        b = int(p["ncu_blocks"])
        shared_fraction = 100.0 * (int(p["shared_ncu_w"]) + b) / p["shared_capacity_kib"]
        l1_fraction = 100.0 * int(p["l1_ncu_w"]) / COMBINED_L1_SHARED_KIB[profile_name]
        l2_fraction = 100.0 * (p["active_sm"] * int(p["l2_ncu_w"]) / 1024.0) / p["l2_mib"]
        values[profile_name] = [shared_fraction, l1_fraction, l2_fraction]

    fig, ax = plt.subplots(figsize=(13.2, 6.8))
    x = np.arange(len(PLATFORM_ORDER))
    width = 0.23
    for idx, (metric, color) in enumerate(zip(metrics, colors)):
        heights = [values[name][idx] for name in PLATFORM_ORDER]
        bars = ax.bar(x + (idx - 1) * width, heights, width, label=metric, color=color)
        for bar, height in zip(bars, heights):
            ax.text(bar.get_x() + bar.get_width() / 2, height + 1.5, f"{height:.1f}%", ha="center", va="bottom", fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(x, [LABELS[name] for name in PLATFORM_ORDER])
    ax.set_ylabel("Nominal profile 대비 비율 [%]")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", color=LINE, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    ax.set_title("Generated strict anchor의 capacity 맥락", loc="left", color=INK, pad=45)
    ax.text(
        0,
        -0.18,
        "이 값은 nominal 설계 비율이며 측정 hit rate가 아니다. Global L1은 dynamic unified cache를 사용하고 A100/H100 L2는 추가 W 좌표를 포함하므로, "
        "최종 선택에는 exact-coordinate NCU evidence가 필요하다.",
        transform=ax.transAxes,
        color=RED,
        fontsize=10,
    )
    path = out_dir / "platform_capacity_context.png"
    save(fig, path)
    return path


def self_test() -> None:
    for name in PLATFORM_ORDER:
        p = PROFILES[name]
        b = int(p["ncu_blocks"])
        assert b in ints(p["blocks"])
        assert int(p["shared_ncu_w"]) >= b
        assert int(p["l1_ncu_w"]) >= b
        assert int(p["l2_ncu_w"]) >= b
        assert int(p["shared_ncu_w"]) + b <= int(p["shared_capacity_kib"])
        full_l2_mib = p["active_sm"] * int(p["l2_ncu_w"]) / 1024.0
        assert full_l2_mib <= float(p["l2_mib"])
        assert int(p["dram_w"]) > float(p["l2_mib"]) * 1024.0 / p["active_sm"]
    assert math.isclose(82 * 64 / 1024, 5.125)
    assert math.isclose(80 * 32 / 1024, 2.5)
    assert math.isclose(108 * 128 / 1024, 13.5)
    assert math.isclose(132 * 128 / 1024, 16.5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    configure_style()
    self_test()
    if args.self_test:
        print("platform sweep visualization self-test passed")
        return 0
    paths = [
        plot_blocks_per_sm(args.out_dir),
        plot_wsm_paths(args.out_dir),
        plot_capacity_context(args.out_dir),
    ]
    for path in paths:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
