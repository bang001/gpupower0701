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
    svg.text(x0, y0 - 12, "pJ/FLOP", 13, 700, COLORS["muted"])

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


def plot_sweep2_wsm() -> None:
    rows = read_csv("results/summary/rtx3090_full_sweep_20260701_by_w_summary.csv")
    modes = ["shared_mma", "l2_mma", "dram_mma"]
    colors = {
        "shared_mma": COLORS["shared"],
        "l2_mma": COLORS["l2"],
        "dram_mma": COLORS["dram"],
    }
    data: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        if row["mode"] in modes:
            data[row["mode"]].append((int(row["W_SM_KiB"]), fnum(row["pJ_FLOP_median"])))
    for pts in data.values():
        pts.sort()

    svg = Svg(980, 520, "Sweep 2 W_SM trend")
    svg.text(38, 38, "Sweep 2: W_SM trend", 22, 700)
    svg.text(38, 62, "Initial 1-second sweep. x-axis is per-SM working set in KiB; y-axis is median pJ/FLOP.", 13, 400, COLORS["muted"])

    x0, y0, w, h = 92, 100, 780, 310
    xmin, xmax = 1, 131072
    ymin, ymax = math.log10(4), math.log10(120)

    def xmap(kib: int) -> float:
        return x0 + w * ((math.log2(kib) - math.log2(xmin)) / (math.log2(xmax) - math.log2(xmin)))

    def ymap(value: float) -> float:
        return y0 + h - h * ((math.log10(value) - ymin) / (ymax - ymin))

    for value in [5, 10, 20, 50, 100]:
        y = ymap(value)
        svg.line(x0, y, x0 + w, y, COLORS["grid"])
        svg.text(x0 - 12, y + 4, value, 11, 400, COLORS["muted"], "end")
    for kib, label in [(1, "1 KiB"), (16, "16 KiB"), (64, "64 KiB"), (128, "128 KiB"), (8192, "8 MiB"), (131072, "128 MiB")]:
        x = xmap(kib)
        svg.line(x, y0, x, y0 + h, COLORS["grid"])
        svg.text(x, y0 + h + 22, label, 10, 400, COLORS["muted"], "middle")

    svg.line(x0, y0 + h, x0 + w, y0 + h, COLORS["text"], 1.2)
    svg.line(x0, y0, x0, y0 + h, COLORS["text"], 1.2)
    svg.text(x0 + w / 2, y0 + h + 48, "W_SM working set per SM", 13, 700, COLORS["muted"], "middle")
    svg.text(x0, y0 - 12, "pJ/FLOP", 13, 700, COLORS["muted"])

    for mode in modes:
        pts = [(xmap(kib), ymap(value)) for kib, value in data[mode]]
        svg.polyline(pts, colors[mode], 2.5)
        for x, y in pts:
            svg.circle(x, y, 3.8, colors[mode])

    lx, ly = 700, 106
    for idx, mode in enumerate(modes):
        y = ly + idx * 24
        svg.rect(lx, y - 11, 16, 8, colors[mode])
        svg.text(lx + 24, y - 3, mode, 12, 400)

    svg.text(38, 476, "Interpretation: this sweep located candidate regions; it is not the final component coefficient estimate.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "sweep2_wsm_trend.svg")


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
    svg.text(x0, y0 - 12, "bytes, log scale", 13, 700, COLORS["muted"])

    lx, ly = 780, 92
    for idx, (_col, label, color) in enumerate(metrics):
        x = lx + idx * 70
        svg.rect(x, ly - 10, 16, 8, color)
        svg.text(x + 22, ly - 3, label, 11, 400)

    svg.text(38, 535, "Rejected examples show why capacity/W_SM alone is not enough: NCU can reveal L1 hits or bank conflicts.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "ncu_path_validation_bytes.svg")


def plot_finalplan_factor_sweeps() -> None:
    rows = read_csv("results/summary/rtx3090_finalplan_matched_control_detail_20260705.csv")
    valid_rows = [row for row in rows if row["valid_component_estimate"] == "True"]
    invalid_l1_w64 = [
        row
        for row in rows
        if row["component"] == "global_l1_hit_path"
        and row["W_SM_KiB"] == "64"
        and row["valid_component_estimate"] != "True"
    ]

    panels = [
        {
            "title": "Tensor MMA incremental",
            "component": "tensor_mma_increment",
            "x_col": "reuse_factor",
            "y_col": "coefficient",
            "unit": "pJ/FLOP",
            "color": COLORS["tensor"],
            "x_label": "reuse factor",
        },
        {
            "title": "Shared scalar path",
            "component": "shared_l1_scalar_path",
            "x_col": "load_repeat",
            "y_col": "coefficient_pJ_per_bit",
            "unit": "pJ/bit",
            "color": COLORS["shared"],
            "x_label": "load repeat",
        },
        {
            "title": "Global L1 hit path",
            "component": "global_l1_hit_path",
            "x_col": "load_repeat",
            "y_col": "coefficient_pJ_per_bit",
            "unit": "pJ/bit",
            "color": COLORS["l1"],
            "x_label": "load repeat",
        },
        {
            "title": "L2 CG hit path",
            "component": "l2_hit_cg_path",
            "x_col": "load_repeat",
            "y_col": "coefficient_pJ_per_bit",
            "unit": "pJ/bit",
            "color": COLORS["l2"],
            "x_label": "load repeat",
        },
        {
            "title": "DRAM CG streaming sanity",
            "component": "dram_cg_stream_path",
            "x_col": "load_repeat",
            "y_col": "coefficient_pJ_per_bit",
            "unit": "pJ/bit",
            "color": COLORS["dram"],
            "x_label": "load repeat",
        },
    ]

    svg = Svg(1160, 760, "Finalplan factor sweep coefficients")
    svg.text(38, 38, "RTX 3090 finalplan factor sweep results", 22, 700)
    svg.text(
        38,
        62,
        "Each point is a treatment-control coefficient. Tensor uses FLOP denominator; memory paths use NCU-corrected bytes.",
        13,
        400,
        COLORS["muted"],
    )

    panel_boxes = [
        (58, 105, 320, 205),
        (420, 105, 320, 205),
        (782, 105, 320, 205),
        (238, 390, 320, 205),
        (600, 390, 320, 205),
    ]

    for panel, (px, py, pw, ph) in zip(panels, panel_boxes):
        component_rows = [row for row in valid_rows if row["component"] == panel["component"]]
        component_rows.sort(key=lambda row: fnum(row[panel["x_col"]]))
        xs = [fnum(row[panel["x_col"]]) for row in component_rows]
        ys = [fnum(row[panel["y_col"]]) for row in component_rows]
        if not xs or not ys:
            continue

        chart_x, chart_y = px + 48, py + 38
        chart_w, chart_h = pw - 74, ph - 82
        x_min = min(xs)
        x_max = max(xs)
        y_max = max(ys) * 1.18 if max(ys) > 0 else 1.0
        y_tick_values = [0.0, y_max / 2, y_max]

        def xmap(value: float) -> float:
            if x_min == x_max:
                return chart_x + chart_w / 2
            return chart_x + chart_w * ((math.log2(value) - math.log2(x_min)) / (math.log2(x_max) - math.log2(x_min)))

        def ymap(value: float) -> float:
            return chart_y + chart_h - chart_h * (value / y_max)

        svg.text(px, py, panel["title"], 14, 700)
        svg.text(px, py + 18, panel["unit"], 11, 400, COLORS["muted"])
        svg.line(chart_x, chart_y + chart_h, chart_x + chart_w, chart_y + chart_h, COLORS["text"], 1.1)
        svg.line(chart_x, chart_y, chart_x, chart_y + chart_h, COLORS["text"], 1.1)
        for tick in y_tick_values:
            y = ymap(tick)
            svg.line(chart_x, y, chart_x + chart_w, y, COLORS["grid"])
            svg.text(chart_x - 8, y + 4, f"{tick:.3g}", 10, 400, COLORS["muted"], "end")
        for x_value in xs:
            x = xmap(x_value)
            svg.line(x, chart_y, x, chart_y + chart_h, COLORS["grid"])
            svg.text(x, chart_y + chart_h + 17, f"{int(x_value)}", 10, 400, COLORS["muted"], "middle")
        points = [(xmap(x), ymap(y)) for x, y in zip(xs, ys)]
        svg.polyline(points, panel["color"], 2.4)
        for (x, y), value in zip(points, ys):
            svg.circle(x, y, 4, panel["color"])
            svg.text(x, y - 8, f"{value:.3g}", 9, 700, panel["color"], "middle")
        median_y = sorted(ys)[len(ys) // 2]
        my = ymap(median_y)
        svg.line(chart_x, my, chart_x + chart_w, my, COLORS["muted"], 1.0)
        svg.text(chart_x + chart_w + 6, my + 4, f"med {median_y:.3g}", 9, 400, COLORS["muted"])
        svg.text(chart_x + chart_w / 2, chart_y + chart_h + 37, panel["x_label"], 11, 700, COLORS["muted"], "middle")

    if invalid_l1_w64:
        invalid_l1_w64.sort(key=lambda row: fnum(row["load_repeat"]))
        values = ", ".join(
            f"LR{int(fnum(row['load_repeat']))}: {fnum(row['coefficient_pJ_per_bit']):.3g}"
            for row in invalid_l1_w64
        )
        svg.text(38, 684, "Rejected L1 W_SM=64 KiB rows", 12, 700, COLORS["rejected"])
        svg.text(
            38,
            704,
            f"{values} pJ/bit; excluded because NCU denominator was missing and some coefficients were negative.",
            11,
            400,
            COLORS["muted"],
        )
    svg.text(
        38,
        732,
        "Interpretation: flatter and positive curves are more trustworthy; large spread means the effective coefficient still includes control/stall effects.",
        12,
        400,
        COLORS["muted"],
    )
    svg.save(OUT_DIR / "finalplan_factor_sweep_coefficients.svg")


def plot_finalplan_sweep_design_matrix() -> None:
    rows = [
        (
            "Tensor",
            "reg_mma - reg_operand_only",
            "2048 KiB",
            "16",
            "82 SM",
            "reuse = 1, 2, 4, 8, 16",
            "5 s x 3",
            "HMMA present; spill/local 0",
        ),
        (
            "Shared scalar",
            "shared_scalar_load_only - clocked_empty",
            "64 KiB",
            "16",
            "82 SM",
            "load_repeat = 1, 2, 4, 8, 16",
            "5 s x 3",
            "shared bytes dominant; bank conflicts 0",
        ),
        (
            "Global L1",
            "global_l1_load_only - clocked_empty",
            "16, 64 KiB",
            "16",
            "82 SM",
            "load_repeat = 1, 2, 4, 8, 16",
            "5 s x 3",
            "W=16 accepted; W=64 rejected",
        ),
        (
            "L2 CG",
            "l2_cg_load_only - clocked_empty",
            "64 KiB",
            "16",
            "82 SM",
            "load_repeat = 1, 2, 4, 8, 16",
            "5 s x 3",
            "L1 bypass; L2 hit 99.941%",
        ),
        (
            "DRAM CG",
            "dram_cg_load_only - clocked_empty",
            "8192 KiB",
            "16",
            "82 SM",
            "load_repeat = 1, 4, 16",
            "5 s x 3",
            "sanity path; DRAM traffic dominant",
        ),
    ]
    headers = ["Component", "Treatment-control pair", "W_SM", "blocks/SM", "active_SM", "Sweep", "Run", "NCU validation"]
    widths = [105, 238, 82, 78, 78, 222, 74, 218]
    x0, y0, row_h = 28, 112, 58
    svg = Svg(1160, 470, "Finalplan sweep design matrix")
    svg.text(38, 38, "Finalplan sweep conditions", 22, 700)
    svg.text(38, 62, "All swept parameters are listed with units. Energy coefficients are derived after matched-control subtraction.", 13, 400, COLORS["muted"])

    x = x0
    for header, width in zip(headers, widths):
        svg.rect(x, y0 - 30, width, 30, "#F4F4F5", COLORS["grid"])
        svg.text(x + 7, y0 - 10, header, 11, 700)
        x += width

    for idx, row in enumerate(rows):
        y = y0 + idx * row_h
        fill = "#FFFFFF" if idx % 2 == 0 else "#FAFAFA"
        x = x0
        for value, width in zip(row, widths):
            svg.rect(x, y, width, row_h, fill, COLORS["grid"])
            text = str(value)
            if len(text) > 31 and width < 120:
                text = text[:28] + "..."
            if width > 180 and len(text) > 34:
                parts = text.split("; ")
                if len(parts) > 1:
                    svg.text(x + 7, y + 22, parts[0], 10, 400)
                    svg.text(x + 7, y + 39, "; ".join(parts[1:]), 10, 400, COLORS["muted"])
                else:
                    svg.text(x + 7, y + 22, text[:42], 10, 400)
                    svg.text(x + 7, y + 39, text[42:], 10, 400, COLORS["muted"])
            else:
                svg.text(x + 7, y + 33, text, 10, 700 if width == widths[0] else 400)
            x += width

    svg.text(
        38,
        435,
        "W_SM is working-set size per SM. blocks/SM and active_SM fix occupancy/load while the factor sweep changes operation or byte count.",
        12,
        400,
        COLORS["muted"],
    )
    svg.save(OUT_DIR / "finalplan_sweep_design_matrix.svg")


def plot_ncu_hit_rate_validation() -> None:
    rows = read_csv("results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv")
    modes = [
        "reg_mma",
        "reg_operand_only",
        "shared_scalar_load_only",
        "global_l1_load_only",
        "l2_cg_load_only",
        "dram_cg_load_only",
        "l2_load_only",
        "shared_load_only",
    ]
    labels = {
        "reg_mma": "Tensor treatment",
        "reg_operand_only": "Tensor control",
        "shared_scalar_load_only": "Shared scalar",
        "global_l1_load_only": "Global L1",
        "l2_cg_load_only": "L2 CG",
        "dram_cg_load_only": "DRAM CG",
        "l2_load_only": "L2 capacity reject",
        "shared_load_only": "Shared reject",
    }
    selected = {row["mode"]: row for row in rows if row["mode"] in modes}

    svg = Svg(1200, 620, "NCU hit-rate validation")
    svg.text(38, 38, "NCU hit-rate validation", 22, 700)
    svg.text(38, 62, "Representative LR=4 counters. Accepted paths are used for final coefficients; rejected paths are shown as controls.", 13, 400, COLORS["muted"])

    x0, y0, bar_w, row_h = 260, 105, 600, 54
    for tick in [0, 25, 50, 75, 100]:
        x = x0 + bar_w * tick / 100
        svg.line(x, y0 - 22, x, y0 + row_h * len(modes) - 12, COLORS["grid"])
        svg.text(x, y0 - 31, f"{tick}%", 10, 400, COLORS["muted"], "middle")

    for idx, mode in enumerate(modes):
        row = selected[mode]
        y = y0 + idx * row_h
        accepted = row["acceptance"] == "accepted"
        label_color = COLORS["text"] if accepted else COLORS["rejected"]
        l1 = max(0.0, min(100.0, fnum(row["l1_hit_rate_pct"])))
        l2 = max(0.0, min(100.0, fnum(row["l2_hit_rate_pct"])))
        l1_text_x = x0 + bar_w * l1 / 100 + 6
        l1_text_fill = COLORS["l1"]
        l1_anchor = "start"
        if l1 > 85:
            l1_text_x = x0 + bar_w * l1 / 100 - 8
            l1_text_fill = "#FFFFFF"
            l1_anchor = "end"
        l2_text_x = x0 + bar_w * l2 / 100 + 6
        l2_text_fill = COLORS["l2"]
        l2_anchor = "start"
        if l2 > 85:
            l2_text_x = x0 + bar_w * l2 / 100 - 8
            l2_text_fill = "#FFFFFF"
            l2_anchor = "end"
        svg.text(38, y + 19, labels[mode], 12, 700, label_color)
        reason = row.get("acceptance_reason") or row.get("reason", "")
        svg.text(38, y + 37, "accepted" if accepted else f"rejected: {reason}", 10, 400, COLORS["l1"] if accepted else COLORS["rejected"])
        svg.rect(x0, y + 6, bar_w * l1 / 100, 14, COLORS["l1"])
        svg.rect(x0, y + 28, bar_w * l2 / 100, 14, COLORS["l2"])
        svg.text(l1_text_x, y + 18, f"L1 {fnum(row['l1_hit_rate_pct']):.3g}%", 10, 700, l1_text_fill, l1_anchor)
        svg.text(l2_text_x, y + 40, f"L2 {fnum(row['l2_hit_rate_pct']):.3g}%", 10, 700, l2_text_fill, l2_anchor)
        svg.text(930, y + 19, f"DRAM {fnum(row['dram_bytes']):.3g} B", 10, 400, COLORS["muted"])
        long_sb = row.get("stall_long_scoreboard_pct") or row.get("long_scoreboard_pct")
        svg.text(930, y + 37, f"long SB {fnum(long_sb):.3g}%", 10, 400, COLORS["muted"])

    svg.rect(842, 82, 15, 9, COLORS["l1"])
    svg.text(863, 91, "L1 hit rate", 11, 400)
    svg.rect(930, 82, 15, 9, COLORS["l2"])
    svg.text(951, 91, "L2 hit rate", 11, 400)
    svg.text(
        38,
        588,
        "Key validation: global L1 has ~100% L1 hit; L2 CG bypasses L1 and has ~99.94% L2 hit; DRAM CG has near-zero L2 hit.",
        12,
        400,
        COLORS["muted"],
    )
    svg.save(OUT_DIR / "ncu_hit_rate_validation.svg")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_component_coefficients()
    plot_sweep1_blocks()
    plot_sweep2_wsm()
    plot_ncu_path_bytes()
    plot_finalplan_factor_sweeps()
    plot_finalplan_sweep_design_matrix()
    plot_ncu_hit_rate_validation()
    print(f"Wrote SVG assets to {OUT_DIR}")


if __name__ == "__main__":
    main()
