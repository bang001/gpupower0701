#!/usr/bin/env python3
"""Generate lightweight SVG figures for the component-energy method note."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "assets" / "component_energy_method"


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


def metric_mid(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    parts = [part.strip() for part in value.split("/") if part.strip()]
    nums = [fnum(part, float("nan")) for part in parts]
    nums = [num for num in nums if math.isfinite(num)]
    if not nums:
        return default
    return nums[len(nums) // 2]


def ci_bounds(value: str | None, fallback: float) -> tuple[float, float]:
    if not value:
        return fallback, fallback
    if "-" not in value:
        parsed = fnum(value, fallback)
        return parsed, parsed
    left, right = value.split("-", 1)
    return fnum(left, fallback), fnum(right, fallback)


def fmt_eng(value: float, unit: str = "") -> str:
    if not math.isfinite(value):
        return "n/a"
    for scale, suffix in [(1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "K")]:
        if abs(value) >= scale:
            return f"{value / scale:.3g}{suffix}{unit}"
    return f"{value:.3g}{unit}"


def fmt_pct(value: float) -> str:
    if not math.isfinite(value):
        return "n/a"
    if abs(value) < 0.001 and value != 0.0:
        return f"{value:.6f}%"
    if abs(value) >= 99.9:
        return f"{value:.4f}%"
    return f"{value:.3g}%"


def strict_component_rows() -> list[dict[str, str]]:
    path = ROOT / "results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.csv"
    if not path.exists():
        return []
    return read_csv(str(path.relative_to(ROOT)))


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def replace_with_current_reporting_sources(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Prefer the source artifacts named in the current reporting CSV.

    The base factor-exact summary remains useful for legacy sweep plots, but the
    final coefficient figure should follow the accepted current reporting CSV.
    """
    current_path = ROOT / "results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv"
    if not current_path.exists():
        return rows
    by_component = {row.get("component", ""): row for row in rows}
    for current in read_csv(str(current_path.relative_to(ROOT))):
        component = current.get("component", "")
        if component.startswith("tensor_mma_increment_fixed_iter"):
            continue
        source = current.get("source_artifact", "")
        if not source or not (ROOT / source).exists():
            continue
        source_rows = read_csv(source)
        source_row = next((row for row in source_rows if row.get("component") == component), None)
        if source_row:
            by_component[component] = source_row
    return list(by_component.values())


def current_reporting_rows() -> list[dict[str, str]]:
    path = ROOT / "results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv"
    if not path.exists():
        return []
    return read_csv(str(path.relative_to(ROOT)))


def current_memory_auxiliaries() -> dict[str, list[dict[str, str]]]:
    auxiliaries: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in current_reporting_rows():
        component = row.get("component", "")
        if component == "shared_l1_scalar_path_lr4_paired_30s_aux":
            row["aux_label"] = "LR4 paired"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_lr8_paired_30s_aux":
            row["aux_label"] = "LR8 paired"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_lr4_30s_aux":
            row["aux_label"] = "LR4 30s"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_lr16_paired_30s_aux":
            row["aux_label"] = "LR16 paired"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_lr16_paired_60s_aux":
            row["aux_label"] = "LR16 60s"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_interleaved_lr4_lr8_lr16_30s_aux":
            row["aux_label"] = "interleaved"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_fixediter_lr4_lr8_lr16_aux":
            row["aux_label"] = "fixed ITER"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_fixediter_lr16_focus_aux":
            row["aux_label"] = "LR16 fixed"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "shared_l1_scalar_path_fixediter_lr4_lr8_focus_aux":
            row["aux_label"] = "LR4/8 fixed"
            auxiliaries["shared_l1_scalar_path"].append(row)
        elif component == "l2_hit_cg_path_lr4_paired_30s_aux":
            row["aux_label"] = "LR4 paired"
            auxiliaries["l2_hit_cg_path"].append(row)
        elif component == "l2_hit_cg_path_lr8_paired_30s_aux":
            row["aux_label"] = "LR8 paired"
            auxiliaries["l2_hit_cg_path"].append(row)
        elif component == "l2_hit_cg_path_targeted_aux":
            row["aux_label"] = "targeted"
            auxiliaries["l2_hit_cg_path"].append(row)
        elif component == "l2_hit_cg_path_lr4_30s_aux":
            row["aux_label"] = "LR4 30s"
            auxiliaries["l2_hit_cg_path"].append(row)
        elif component == "global_l1_hit_path_60s_aux":
            row["aux_label"] = "60s"
            auxiliaries["global_l1_hit_path"].append(row)
        elif component == "global_l1_hit_path_duration_scaling_aux":
            row["aux_label"] = "duration"
            auxiliaries["global_l1_hit_path"].append(row)
        elif component == "global_l1_hit_path_paired_30s_aux":
            row["aux_label"] = "paired 30s"
            auxiliaries["global_l1_hit_path"].append(row)
        elif component == "global_l1_hit_path_lr8_paired_30s_aux":
            row["aux_label"] = "LR8 paired"
            auxiliaries["global_l1_hit_path"].append(row)
    return auxiliaries


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
    rows = read_csv(
        "results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_summary_20260708.csv"
    )
    tensor_source = "factor exact-NCU broad RF sweep"
    tensor_aux_summary = None
    targeted_tensor_summary = (
        "results/summary/rtx3090_tensor_targeted_rf8_rf16_matched_control_summary_20260708.csv"
    )
    if (ROOT / targeted_tensor_summary).exists():
        targeted_rows = read_csv(targeted_tensor_summary)
        targeted_tensor = next(
            (row for row in targeted_rows if row["component"] == "tensor_mma_increment"),
            None,
        )
        if targeted_tensor:
            rows = [
                targeted_tensor if row["component"] == "tensor_mma_increment" else row
                for row in rows
            ]
            tensor_source = "targeted RF=8/16, 20 s, 6 repeats"
    fixed_iter_tensor_summary = (
        "results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_matched_control_summary_20260708.csv"
    )
    if (ROOT / fixed_iter_tensor_summary).exists():
        fixed_iter_rows = read_csv(fixed_iter_tensor_summary)
        tensor_aux_summary = next(
            (row for row in fixed_iter_rows if row["component"] == "tensor_mma_increment"),
            None,
        )
    tensor_rf8_duration_summary = None
    rf8_duration_summary = (
        "results/summary/rtx3090_tensor_rf8_duration_scaling_matched_control_summary_20260708.csv"
    )
    if (ROOT / rf8_duration_summary).exists():
        rf8_duration_rows = read_csv(rf8_duration_summary)
        tensor_rf8_duration_summary = next(
            (row for row in rf8_duration_rows if row["component"] == "tensor_mma_increment"),
            None,
        )
    tensor_rf16_duration_summary = None
    rf16_duration_summary = (
        "results/summary/rtx3090_tensor_rf16_duration_scaling_matched_control_summary_20260708.csv"
    )
    if (ROOT / rf16_duration_summary).exists():
        rf16_duration_rows = read_csv(rf16_duration_summary)
        tensor_rf16_duration_summary = next(
            (row for row in rf16_duration_rows if row["component"] == "tensor_mma_increment"),
            None,
        )
    rows = replace_with_current_reporting_sources(rows)
    memory_aux = current_memory_auxiliaries()
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

    aux_max = max(
        (fnum(row.get("ci_high")) for rows in memory_aux.values() for row in rows),
        default=0.0,
    )
    svg = Svg(940, 500, "Current component coefficient candidates")
    svg.text(38, 38, "Current accepted candidate coefficients", 22, 700)
    svg.text(38, 62, "Memory bars are primary pJ/bit; outlined ticks show auxiliary checks where available. Values are effective coefficients.", 13, 400, COLORS["muted"])

    x0, y0, w, row_h = 230, 105, 560, 58
    max_val = max(max(fnum(r["max_pJ_per_bit"]) for r in memory), aux_max) * 1.08
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
        aux_rows = memory_aux.get(row["component"], [])
        aux_text = ""
        if aux_rows:
            aux_text = "; " + ", ".join(
                f"{aux.get('aux_label', 'aux')} {fnum(aux.get('median')):.3g}"
                for aux in aux_rows
            )
        svg.text(38, y + 41, f"min {mn:.3g}, median {med:.3g}, max {mx:.3g}{aux_text}", 11, 400, COLORS["muted"])
        svg.rect(x0, y + 8, bar_w, 20, COLORS[color_key])
        svg.line(min_x, y + 18, max_x, y + 18, COLORS["text"], 1.2)
        svg.line(min_x, y + 13, min_x, y + 23, COLORS["text"], 1.2)
        svg.line(max_x, y + 13, max_x, y + 23, COLORS["text"], 1.2)
        svg.text(x0 + bar_w + 8, y + 24, f"{med:.3g}", 12, 700)
        for aux_idx, aux in enumerate(aux_rows):
            aux_med = fnum(aux.get("median"))
            aux_label = aux.get("aux_label", "aux")
            aux_low = fnum(aux.get("ci_low"), aux_med)
            aux_high = fnum(aux.get("ci_high"), aux_med)
            aux_x = x0 + w * aux_med / max_val
            aux_low_x = x0 + w * aux_low / max_val
            aux_high_x = x0 + w * aux_high / max_val
            aux_y = y + 39 + aux_idx * 8
            svg.line(aux_low_x, aux_y, aux_high_x, aux_y, COLORS["muted"], 1.2)
            svg.line(aux_x, aux_y - 7, aux_x, aux_y + 7, COLORS["muted"], 2.0)
            svg.text(aux_x + 5, aux_y + 10, aux_label, 8, 700, COLORS["muted"])

    if tensor:
        y = 396
        mn = fnum(tensor["min"])
        med = fnum(tensor["median"])
        mx = fnum(tensor["max"])
        aux_med = fnum(tensor_aux_summary["median"]) if tensor_aux_summary else None
        aux_min = fnum(tensor_aux_summary["min"]) if tensor_aux_summary else None
        aux_max = fnum(tensor_aux_summary["max"]) if tensor_aux_summary else None
        rf8_med = fnum(tensor_rf8_duration_summary["median"]) if tensor_rf8_duration_summary else None
        rf8_min = fnum(tensor_rf8_duration_summary["min"]) if tensor_rf8_duration_summary else None
        rf8_max = fnum(tensor_rf8_duration_summary["max"]) if tensor_rf8_duration_summary else None
        rf16_med = fnum(tensor_rf16_duration_summary["median"]) if tensor_rf16_duration_summary else None
        rf16_min = fnum(tensor_rf16_duration_summary["min"]) if tensor_rf16_duration_summary else None
        rf16_max = fnum(tensor_rf16_duration_summary["max"]) if tensor_rf16_duration_summary else None
        visual_max = max(mx, aux_max or 0.0, rf8_max or 0.0, rf16_max or 0.0)
        scale = 520 / max(0.38, visual_max * 1.1)
        svg.text(38, y, "Tensor MMA incremental", 14, 700)
        if aux_med is not None and rf8_med is not None and rf16_med is not None:
            range_low = min(med, aux_med, rf8_med, rf16_med)
            range_high = max(med, aux_med, rf8_med, rf16_med)
            desc = (
                f"RF16 duration {rf16_med:.3g}; RF8 duration {rf8_med:.3g}; "
                f"fixed-ITER {aux_med:.3g} pJ/FLOP"
            )
        elif aux_med is not None and rf8_med is not None:
            range_low = min(med, aux_med, rf8_med)
            range_high = max(med, aux_med, rf8_med)
            desc = (
                f"duration RF8/16 {med:.3g}; fixed-ITER {aux_med:.3g}; "
                f"RF8 duration {rf8_med:.3g} pJ/FLOP"
            )
        elif aux_med is not None:
            desc = (
                f"duration median {med:.3g}; fixed-ITER auxiliary median {aux_med:.3g} "
                f"pJ/FLOP; report as method-sensitive range"
            )
            range_low = min(med, aux_med)
            range_high = max(med, aux_med)
        else:
            desc = f"min {mn:.3g}, median {med:.3g}, max {mx:.3g} pJ/FLOP; {tensor_source}"
            range_low = med
            range_high = med
        svg.text(38, y + 19, desc, 11, 400, COLORS["muted"])
        svg.rect(x0, y - 14, med * scale, 20, COLORS["tensor"])
        svg.line(x0 + mn * scale, y - 4, x0 + mx * scale, y - 4, COLORS["text"], 1.2)
        if aux_med is not None:
            svg.rect(x0, y + 10, aux_med * scale, 12, "#A5B4FC")
            svg.line(x0 + aux_min * scale, y + 16, x0 + aux_max * scale, y + 16, COLORS["muted"], 1.0)
            if rf8_med is not None:
                svg.rect(x0, y + 28, rf8_med * scale, 12, "#C7D2FE")
                svg.line(x0 + rf8_min * scale, y + 34, x0 + rf8_max * scale, y + 34, COLORS["muted"], 1.0)
            if rf16_med is not None:
                svg.rect(x0, y + 44, rf16_med * scale, 12, "#E0E7FF")
                svg.line(x0 + rf16_min * scale, y + 50, x0 + rf16_max * scale, y + 50, COLORS["muted"], 1.0)
            svg.text(
                x0 + range_high * scale + 8,
                y + 2,
                f"{range_low:.3g}-{range_high:.3g} pJ/FLOP",
                12,
                700,
            )
            svg.text(
                x0 + 4,
                y + 66,
                "dark: RF8/16, mid: fixed-ITER, light: RF8 duration, pale: RF16 duration",
                10,
                400,
                COLORS["muted"],
            )
        else:
            svg.text(x0 + med * scale + 8, y + 2, f"{med:.3g} pJ/FLOP", 12, 700)

    svg.text(38, 474, "Error bars show min-max across valid rows. DRAM is sanity-only; outlined ticks are auxiliary, not replacement values.", 12, 400, COLORS["muted"])
    svg.save(OUT_DIR / "final_component_coefficients.svg")


def plot_sweep1_blocks() -> None:
    rows = read_csv(
        "archive/legacy_20260707/results/summary/rtx3090_sweep1_blocks_fixedw_20260702_summary.csv"
    )
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
    rows = read_csv(
        "archive/legacy_20260707/results/summary/rtx3090_full_sweep_20260701_by_w_summary.csv"
    )
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


def plot_strict_scope_component_coefficients_summary() -> None:
    rows = strict_component_rows()
    if not rows:
        return
    by_key = {row["component_key"]: row for row in rows}
    tensor = by_key.get("tensor_mma_increment")
    memory_order = [
        ("shared_l1_scalar_path", "Shared scalar", COLORS["shared"]),
        ("global_l1_hit_path", "Global L1 hit", COLORS["l1"]),
        ("l2_hit_cg_path", "L2 CG hit", COLORS["l2"]),
    ]
    memory = [(key, label, color, by_key[key]) for key, label, color in memory_order if key in by_key]

    svg = Svg(1120, 640, "RTX 3090 strict component coefficient summary")
    svg.text(38, 38, "RTX 3090 strict component coefficients", 22, 700)
    svg.text(
        38,
        62,
        "Accepted strict-scope rows only. Tensor uses pJ/FLOP; memory paths use pJ/bit, so the two panels are not directly comparable.",
        13,
        400,
        COLORS["muted"],
    )

    if tensor:
        med = fnum(tensor["median"])
        lo, hi = ci_bounds(tensor.get("median_ci"), med)
        x0, y0, w = 205, 130, 470
        scale_max = max(0.16, hi * 1.18)
        svg.text(38, 122, "Tensor path", 15, 700)
        svg.text(38, 145, "reg_mma - reg_operand_only", 11, 400, COLORS["muted"])
        svg.text(38, 165, tensor["condition"], 10, 400, COLORS["muted"])
        for tick in [0.0, 0.05, 0.10, 0.15]:
            x = x0 + w * tick / scale_max
            svg.line(x, 106, x, 184, COLORS["grid"])
            svg.text(x, 202, f"{tick:.2f}", 10, 400, COLORS["muted"], "middle")
        bar_w = w * med / scale_max
        low_x = x0 + w * lo / scale_max
        high_x = x0 + w * hi / scale_max
        svg.rect(x0, 132, bar_w, 22, COLORS["tensor"])
        svg.line(low_x, 143, high_x, 143, COLORS["text"], 1.2)
        svg.line(low_x, 137, low_x, 149, COLORS["text"], 1.2)
        svg.line(high_x, 137, high_x, 149, COLORS["text"], 1.2)
        svg.text(x0 + bar_w + 10, 148, f"{med:.3f} pJ/FLOP", 13, 700)
        svg.text(x0 + w / 2, 226, "Tensor Core operation denominator", 11, 700, COLORS["muted"], "middle")
        svg.text(720, 126, f"rows: {tensor['rows_used']}", 11, 700, COLORS["muted"])
        svg.text(720, 146, f"NCU rows: {tensor['ncu_accepted_rows']}", 11, 700, COLORS["muted"])
        svg.text(720, 166, "NCU: HMMA present, L1 bytes zero", 11, 400, COLORS["muted"])

    if memory:
        y0, row_h = 295, 78
        x0, w = 250, 610
        max_val = max(ci_bounds(row.get("median_ci"), fnum(row["median"]))[1] for *_rest, row in memory)
        scale_max = max(1.4, max_val * 1.12)
        svg.text(38, 268, "Memory paths", 15, 700)
        svg.text(
            38,
            290,
            "All memory denominators are same-coordinate NCU actual bytes where available.",
            11,
            400,
            COLORS["muted"],
        )
        for tick in [0.0, 0.25, 0.50, 0.75, 1.00, 1.25]:
            x = x0 + w * tick / scale_max
            svg.line(x, y0 - 24, x, y0 + row_h * len(memory) - 18, COLORS["grid"])
            svg.text(x, y0 + row_h * len(memory) + 10, f"{tick:.2f}", 10, 400, COLORS["muted"], "middle")
        svg.text(x0 + w / 2, y0 + row_h * len(memory) + 36, "pJ/bit", 12, 700, COLORS["muted"], "middle")

        for idx, (_key, label, color, row) in enumerate(memory):
            y = y0 + idx * row_h
            med = fnum(row["median"])
            lo, hi = ci_bounds(row.get("median_ci"), med)
            bar_w = w * med / scale_max
            low_x = x0 + w * lo / scale_max
            high_x = x0 + w * hi / scale_max
            svg.text(38, y + 16, label, 14, 700)
            svg.text(38, y + 35, row["mode_pair"], 10, 400, COLORS["muted"])
            svg.text(38, y + 53, row["condition"], 10, 400, COLORS["muted"])
            svg.rect(x0, y + 5, bar_w, 22, color)
            svg.line(low_x, y + 16, high_x, y + 16, COLORS["text"], 1.2)
            svg.line(low_x, y + 10, low_x, y + 22, COLORS["text"], 1.2)
            svg.line(high_x, y + 10, high_x, y + 22, COLORS["text"], 1.2)
            svg.text(x0 + bar_w + 10, y + 22, f"{med:.3f} pJ/bit", 13, 700)
            svg.text(
                890,
                y + 22,
                f"{row['reliability_status']} / {row['confidence']}",
                11,
                700,
                COLORS["muted"],
            )
            svg.text(890, y + 42, f"NCU rows {row['ncu_accepted_rows']}", 11, 400, COLORS["muted"])

    svg.text(
        38,
        604,
        "Interpretation: these are effective board-level microbenchmark coefficients, not pure silicon-level Tensor/L1/L2 circuit energy.",
        12,
        400,
        COLORS["muted"],
    )
    svg.save(OUT_DIR / "rtx3090_strict_scope_component_coefficients_summary.svg")


def plot_strict_scope_ncu_evidence() -> None:
    rows = strict_component_rows()
    if not rows:
        return
    by_key = {row["component_key"]: row for row in rows}
    order = [
        ("tensor_mma_increment", "Tensor MMA", COLORS["tensor"]),
        ("shared_l1_scalar_path", "Shared scalar", COLORS["shared"]),
        ("global_l1_hit_path", "Global L1 hit", COLORS["l1"]),
        ("l2_hit_cg_path", "L2 CG hit", COLORS["l2"]),
    ]

    svg = Svg(1220, 690, "RTX 3090 strict NCU evidence matrix")
    svg.text(38, 38, "RTX 3090 strict NCU validation evidence", 22, 700)
    svg.text(
        38,
        62,
        "Same-coordinate treatment NCU counters used to validate the path before reporting a coefficient.",
        13,
        400,
        COLORS["muted"],
    )

    headers = ["Component", "Dominant evidence", "Hit-rate check", "Traffic context", "Caveat"]
    widths = [150, 300, 235, 250, 235]
    x0, y0, row_h = 28, 125, 112
    x = x0
    for header, width in zip(headers, widths):
        svg.rect(x, y0 - 34, width, 34, "#F4F4F5", COLORS["grid"])
        svg.text(x + 8, y0 - 12, header, 11, 700)
        x += width

    for idx, (key, label, color) in enumerate(order):
        row = by_key.get(key)
        if not row:
            continue
        y = y0 + idx * row_h
        fill = "#FFFFFF" if idx % 2 == 0 else "#FAFAFA"
        x = x0
        for width in widths:
            svg.rect(x, y, width, row_h, fill, COLORS["grid"])
            x += width

        svg.rect(x0 + 8, y + 18, 13, 13, color)
        svg.text(x0 + 28, y + 29, label, 12, 700)
        svg.text(x0 + 28, y + 49, row["unit"], 10, 700, COLORS["muted"])
        svg.text(x0 + 28, y + 68, f"{fnum(row['median']):.3g}", 15, 700, color)
        svg.text(x0 + 28, y + 88, f"rows {row['rows_used']}", 10, 400, COLORS["muted"])

        c1 = x0 + widths[0]
        c2 = c1 + widths[1]
        c3 = c2 + widths[2]
        c4 = c3 + widths[3]

        if key == "tensor_mma_increment":
            hmma = metric_mid(row["ncu_tensor_hmma_inst_min_med_max"])
            l1_bytes = metric_mid(row["ncu_l1_bytes_min_med_max"])
            dominant = [f"HMMA inst: {fmt_eng(hmma)}", f"L1 bytes: {fmt_eng(l1_bytes, 'B')}", "spill counters: not reported"]
            hit_lines = ["Path proof is operation based", "not cache-hit based", "zero L1 byte summary"]
            traffic = [f"L2 bytes context: {fmt_eng(metric_mid(row['ncu_l2_bytes_min_med_max']), 'B')}", f"DRAM bytes context: {fmt_eng(metric_mid(row['ncu_dram_bytes_min_med_max']), 'B')}"]
            caveat = ["Spill-free claim still needs", "ptxas/register-footprint", "evidence."]
        elif key == "shared_l1_scalar_path":
            dominant = [f"Shared bytes: {fmt_eng(metric_mid(row['ncu_shared_bytes_min_med_max']), 'B')}", "Global L1 bytes: 0B", f"DRAM bytes: {fmt_eng(metric_mid(row['ncu_dram_bytes_min_med_max']), 'B')}"]
            hit_lines = ["Shared-memory path", "global L1/L2 hit-rate is", "background context only"]
            traffic = [f"L2 bytes context: {fmt_eng(metric_mid(row['ncu_l2_bytes_min_med_max']), 'B')}", f"DRAM accesses: {fmt_eng(metric_mid(row['ncu_dram_accesses_min_med_max']))}"]
            caveat = ["Do not read global cache", "hit rate as shared-memory", "hit rate."]
        elif key == "global_l1_hit_path":
            l1 = metric_mid(row["ncu_l1_hit_rate_pct_min_med_max"])
            dominant = [f"L1 hit: {fmt_pct(l1)}", f"L1 accesses: {fmt_eng(metric_mid(row['ncu_l1_accesses_min_med_max']))}", f"L1 bytes: {fmt_eng(metric_mid(row['ncu_l1_bytes_min_med_max']), 'B')}"]
            hit_lines = ["Global load terminates", "in L1 for this path", f"L2 hit bg: {fmt_pct(metric_mid(row['ncu_l2_hit_rate_pct_min_med_max']))}"]
            traffic = [f"L2 bytes context: {fmt_eng(metric_mid(row['ncu_l2_bytes_min_med_max']), 'B')}", f"DRAM bytes: {fmt_eng(metric_mid(row['ncu_dram_bytes_min_med_max']), 'B')}"]
            caveat = ["Coefficient still includes", "instruction/control overhead", "after subtraction."]
        else:
            l1 = metric_mid(row["ncu_l1_hit_rate_pct_min_med_max"])
            l2 = metric_mid(row["ncu_l2_hit_rate_pct_min_med_max"])
            dominant = [f"L1 hit: {fmt_pct(l1)}", f"L2 hit: {fmt_pct(l2)}", f"L2 bytes: {fmt_eng(metric_mid(row['ncu_l2_bytes_min_med_max']), 'B')}"]
            hit_lines = ["L1 bypass/near-zero L1 hit", "with high L2 hit", "supports L2 CG path"]
            traffic = [f"L2 accesses: {fmt_eng(metric_mid(row['ncu_l2_accesses_min_med_max']))}", f"DRAM bytes: {fmt_eng(metric_mid(row['ncu_dram_bytes_min_med_max']), 'B')}", f"long SB: {fmt_pct(metric_mid(row['ncu_stall_long_scoreboard_pct_min_med_max']))}"]
            caveat = ["Long-scoreboard is high;", "treat as effective path", "coefficient, not pure L2."]

        for line_idx, text in enumerate(dominant):
            svg.text(c1 + 10, y + 28 + line_idx * 22, text, 11, 700 if line_idx == 0 else 400)
        for line_idx, text in enumerate(hit_lines):
            svg.text(c2 + 10, y + 28 + line_idx * 22, text, 11, 400, COLORS["muted"])
        for line_idx, text in enumerate(traffic):
            svg.text(c3 + 10, y + 28 + line_idx * 22, text, 11, 400, COLORS["muted"])
        for line_idx, text in enumerate(caveat):
            svg.text(c4 + 10, y + 28 + line_idx * 22, text, 11, 400, COLORS["muted"])

        if key in {"global_l1_hit_path", "l2_hit_cg_path"}:
            l1_pct = max(0.0, min(100.0, metric_mid(row["ncu_l1_hit_rate_pct_min_med_max"])))
            l2_pct = max(0.0, min(100.0, metric_mid(row["ncu_l2_hit_rate_pct_min_med_max"])))
            bx, bw = c2 + 10, 150
            svg.rect(bx, y + 81, bw, 7, "#E4E4E7")
            svg.rect(bx, y + 81, bw * l1_pct / 100.0, 7, COLORS["l1"])
            svg.text(bx + bw + 8, y + 88, "L1", 9, 700, COLORS["l1"])
            svg.rect(bx, y + 95, bw, 7, "#E4E4E7")
            svg.rect(bx, y + 95, bw * l2_pct / 100.0, 7, COLORS["l2"])
            svg.text(bx + bw + 8, y + 102, "L2", 9, 700, COLORS["l2"])

    svg.text(
        38,
        650,
        "Counter caveat: NCU validates the intended traffic path; the reported energy remains a workload-dependent board-level delta coefficient.",
        12,
        400,
        COLORS["muted"],
    )
    svg.save(OUT_DIR / "rtx3090_strict_scope_ncu_evidence.svg")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_component_coefficients()
    plot_sweep1_blocks()
    plot_sweep2_wsm()
    plot_ncu_path_bytes()
    plot_finalplan_factor_sweeps()
    plot_finalplan_sweep_design_matrix()
    plot_ncu_hit_rate_validation()
    plot_strict_scope_component_coefficients_summary()
    plot_strict_scope_ncu_evidence()
    print(f"Wrote SVG assets to {OUT_DIR}")


if __name__ == "__main__":
    main()
