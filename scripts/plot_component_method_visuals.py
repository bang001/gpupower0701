#!/usr/bin/env python3
"""Generate lightweight SVG figures for the component-energy method note."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "component_energy_method_assets"


COLORS = {
    "tensor": "#5B5FC7",
    "l1": "#0F766E",
    "shared": "#D97706",
    "l2": "#2563EB",
    "dram": "#B91C1C",
    "rejected": "#71717A",
    "grid": "#D4D4D8",
    "text": "#18181B",
    "muted": "#52525B",
}


def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "" or value.lower() == "nan":
        return default
    return float(value)


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Svg:
    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self.items: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f"<title>{esc(title)}</title>",
            '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        ]

    def text(
        self,
        x: float,
        y: float,
        text: object,
        size: int = 14,
        weight: int = 400,
        fill: str = COLORS["text"],
        anchor: str = "start",
    ) -> None:
        self.items.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{esc(text)}</text>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 1.0) -> None:
        self.items.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width:.1f}"/>'
        )

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str | None = None) -> None:
        stroke_attr = f' stroke="{stroke}"' if stroke else ""
        self.items.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}"{stroke_attr}/>'
        )

    def circle(self, x: float, y: float, r: float, fill: str) -> None:
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}"/>')

    def polyline(self, points: list[tuple[float, float]], stroke: str, width: float = 2.0) -> None:
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.items.append(
            f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="{width:.1f}"/>'
        )

    def save(self, path: Path) -> None:
        self.items.append("</svg>")
        path.write_text("\n".join(self.items) + "\n", encoding="utf-8")


def plot_component_coefficients() -> None:
    rows = read_csv("results/summary/rtx3090_finalplan_matched_control_summary_20260705.csv")
    labels = {
        "global_l1_hit_path": ("Global L1 hit", "l1"),
        "shared_l1_scalar_path": ("Shared scalar", "shared"),
        "l2_hit_cg_path": ("L2 CG hit", "l2"),
        "dram_cg_stream_path": ("DRAM CG stream", "dram"),
        "tensor_mma_increment": ("Tensor MMA incr.", "tensor"),
    }

    memory = []
    tensor = None
    for row in rows:
        name = row["component"]
        if name == "tensor_mma_increment":
            tensor = row
        elif name in labels:
            memory.append(row)

    order = ["global_l1_hit_path", "shared_l1_scalar_path", "l2_hit_cg_path", "dram_cg_stream_path"]
    memory.sort(key=lambda r: order.index(r["component"]))

    svg = Svg(940, 470, "Final component coefficient candidates")
    svg.text(38, 38, "Final accepted candidate coefficients", 22, 700)
    svg.text(38, 62, "Memory paths use pJ/bit; Tensor uses pJ/FLOP. Values are effective coefficients, not pure circuit energy.", 13, 400, COLORS["muted"])

    x0, y0, w, row_h = 230, 105, 560, 58
    max_val = max(fnum(r["max_pJ_per_bit"]) for r in memory) * 1.08
    for tick in [0, 1, 2, 3, 4, 5, 6]:
        x = x0 + w * tick / max_val
        svg.line(x, y0 - 20, x, y0 + row_h * len(memory) - 8, COLORS["grid"])
        svg.text(x, y0 + row_h * len(memory) + 14, tick, 11, 400, COLORS["muted"], "middle")
    svg.text(x0 + w / 2, y0 + row_h * len(memory) + 38, "pJ/bit", 12, 700, COLORS["muted"], "middle")

    for idx, row in enumerate(memory):
        y = y0 + idx * row_h
        label, color_key = labels[row["component"]]
        med = fnum(row["median_pJ_per_bit"])
        mn = fnum(row["min_pJ_per_bit"])
        mx = fnum(row["max_pJ_per_bit"])
        bar_w = w * med / max_val
        min_x = x0 + w * mn / max_val
        max_x = x0 + w * mx / max_val
        svg.text(38, y + 22, label, 14, 700)
        svg.text(38, y + 41, f"min {mn:.3g}, median {med:.3g}, max {mx:.3g}", 11, 400, COLORS["muted"])
        svg.rect(x0, y + 8, bar_w, 20, COLORS[color_key])
        svg.line(min_x, y + 18, max_x, y + 18, COLORS["text"], 1.2)
        svg.line(min_x, y + 13, min_x, y + 23, COLORS["text"], 1.2)
        svg.line(max_x, y + 13, max_x, y + 23, COLORS["text"], 1.2)
        svg.text(x0 + bar_w + 8, y + 24, f"{med:.3g}", 12, 700)

    if tensor:
        y = 382
        mn = fnum(tensor["min"])
        med = fnum(tensor["median"])
        mx = fnum(tensor["max"])
        scale = 520 / 0.32
        svg.text(38, y, "Tensor MMA incremental", 14, 700)
        svg.text(38, y + 19, f"min {mn:.3g}, median {med:.3g}, max {mx:.3g} pJ/FLOP", 11, 400, COLORS["muted"])
        svg.rect(x0, y - 14, med * scale, 20, COLORS["tensor"])
        svg.line(x0 + mn * scale, y - 4, x0 + mx * scale, y - 4, COLORS["text"], 1.2)
        svg.text(x0 + med * scale + 8, y + 2, f"{med:.3g} pJ/FLOP", 12, 700)

    svg.text(38, 444, "Error bars show min-max across valid rows. DRAM is sanity-only for RTX 3090 GDDR6X.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "final_component_coefficients.svg")


def plot_sweep1_blocks() -> None:
    rows = read_csv("results/summary/rtx3090_sweep1_blocks_fixedw_20260702_summary.csv")
    modes = ["reg_mma", "shared_mma", "l2_mma", "dram_mma"]
    colors = {
        "reg_mma": COLORS["tensor"],
        "shared_mma": COLORS["shared"],
        "l2_mma": COLORS["l2"],
        "dram_mma": COLORS["dram"],
    }
    data: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        if row["mode"] in modes:
            data[row["mode"]].append((int(row["blocks_per_SM"]), fnum(row["pJ_per_FLOP_median"])))
    for pts in data.values():
        pts.sort()

    svg = Svg(940, 500, "Sweep 1 blocks per SM trend")
    svg.text(38, 38, "Sweep 1: blocks/SM trend", 22, 700)
    svg.text(38, 62, "Fixed W_SM per mode; y-axis is log10(pJ/FLOP) to compare compute and memory-heavy modes.", 13, 400, COLORS["muted"])

    x0, y0, w, h = 92, 95, 760, 310
    xmin, xmax = 1, 16
    ymin, ymax = math.log10(2), math.log10(130)

    def xmap(b: int) -> float:
        return x0 + w * (math.log2(b) / math.log2(xmax))

    def ymap(v: float) -> float:
        return y0 + h - h * ((math.log10(v) - ymin) / (ymax - ymin))

    for value in [2, 5, 10, 20, 50, 100]:
        y = ymap(value)
        svg.line(x0, y, x0 + w, y, COLORS["grid"])
        svg.text(x0 - 12, y + 4, value, 11, 400, COLORS["muted"], "end")
    for block in [1, 2, 4, 8, 16]:
        x = xmap(block)
        svg.line(x, y0, x, y0 + h, COLORS["grid"])
        svg.text(x, y0 + h + 22, block, 12, 400, COLORS["muted"], "middle")

    svg.line(x0, y0 + h, x0 + w, y0 + h, COLORS["text"], 1.2)
    svg.line(x0, y0, x0, y0 + h, COLORS["text"], 1.2)
    svg.text(x0 + w / 2, y0 + h + 48, "blocks/SM", 13, 700, COLORS["muted"], "middle")
    svg.text(22, y0 + h / 2, "pJ/FLOP", 13, 700, COLORS["muted"], "middle")

    for mode in modes:
        pts = [(xmap(b), ymap(v)) for b, v in data[mode]]
        svg.polyline(pts, colors[mode], 2.6)
        for x, y in pts:
            svg.circle(x, y, 4, colors[mode])

    lx, ly = 690, 100
    for idx, mode in enumerate(modes):
        y = ly + idx * 24
        svg.rect(lx, y - 11, 16, 8, colors[mode])
        svg.text(lx + 24, y - 3, mode, 12, 400)

    svg.text(38, 464, "Interpretation: decreasing pJ/FLOP with higher blocks/SM is a trend signal, not a component split.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "sweep1_blocks_trend.svg")


def plot_ncu_path_bytes() -> None:
    rows = read_csv("results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv")
    selected_modes = [
        "shared_scalar_load_only",
        "global_l1_load_only",
        "l2_cg_load_only",
        "dram_cg_load_only",
        "l2_load_only",
        "shared_load_only",
    ]
    selected = [r for r in rows if r["mode"] in selected_modes]
    selected.sort(key=lambda r: selected_modes.index(r["mode"]))

    svg = Svg(1080, 560, "NCU path validation traffic")
    svg.text(38, 38, "NCU path validation traffic", 22, 700)
    svg.text(38, 62, "Bars show log10(bytes) for representative LR=4 rows. Accepted/rejected status comes from path criteria.", 13, 400, COLORS["muted"])

    x0, y0, w, h = 98, 105, 860, 330
    max_log = 12.2
    min_log = 0.0

    def ymap_log(v: float) -> float:
        lv = math.log10(max(v, 1.0))
        return y0 + h - h * ((lv - min_log) / (max_log - min_log))

    for tick in [0, 3, 6, 9, 12]:
        y = ymap_log(10**tick)
        svg.line(x0, y, x0 + w, y, COLORS["grid"])
        svg.text(x0 - 10, y + 4, f"1e{tick}", 11, 400, COLORS["muted"], "end")

    metrics = [
        ("shared_bytes", "Shared", COLORS["shared"]),
        ("l1_bytes", "L1", COLORS["l1"]),
        ("l2_bytes", "L2", COLORS["l2"]),
        ("dram_bytes", "DRAM", COLORS["dram"]),
    ]
    group_w = w / len(selected)
    bar_w = 14
    for idx, row in enumerate(selected):
        cx = x0 + group_w * idx + group_w / 2
        accepted = row["acceptance"] == "accepted"
        name = row["mode"].replace("_load_only", "").replace("_scalar", "_scalar").replace("_", "\n")
        for j, (col, _label, color) in enumerate(metrics):
            v = fnum(row[col])
            y = ymap_log(v)
            x = cx - 34 + j * 18
            svg.rect(x, y, bar_w, y0 + h - y, color)
        svg.text(cx, y0 + h + 22, name.replace("\n", " "), 10, 700 if accepted else 400, COLORS["text"], "middle")
        svg.text(cx, y0 + h + 40, "accepted" if accepted else "rejected", 10, 700, COLORS["l1"] if accepted else COLORS["rejected"], "middle")
        svg.text(cx, y0 + h + 56, f"L1 {fnum(row['l1_hit_rate_pct']):.1f}% / L2 {fnum(row['l2_hit_rate_pct']):.1f}%", 9, 400, COLORS["muted"], "middle")

    svg.line(x0, y0 + h, x0 + w, y0 + h, COLORS["text"], 1.2)
    svg.line(x0, y0, x0, y0 + h, COLORS["text"], 1.2)
    svg.text(24, y0 + h / 2, "bytes, log scale", 13, 700, COLORS["muted"], "middle")

    lx, ly = 780, 92
    for idx, (_col, label, color) in enumerate(metrics):
        x = lx + idx * 70
        svg.rect(x, ly - 10, 16, 8, color)
        svg.text(x + 22, ly - 3, label, 11, 400)

    svg.text(38, 535, "Rejected examples show why capacity/W_SM alone is not enough: NCU can reveal L1 hits or bank conflicts.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "ncu_path_validation_bytes.svg")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_component_coefficients()
    plot_sweep1_blocks()
    plot_ncu_path_bytes()
    print(f"Wrote SVG assets to {OUT_DIR}")


if __name__ == "__main__":
    main()
