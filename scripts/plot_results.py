#!/usr/bin/env python3
"""Generate standard PNG visualizations for A100 FP16 energy v2 CSV files."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
except ModuleNotFoundError as exc:
    raise SystemExit("matplotlib is required: install it with `python -m pip install matplotlib`") from exc


BLOCKS_PER_SM = [1, 2, 4, 8, 16, 32]
W_SM_KIB = [
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
]


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        return default if value == "" else float(value)
    except ValueError:
        return default


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        value = row.get(key, "")
        return default if value == "" else int(float(value))
    except ValueError:
        return default


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def median(values: list[float]) -> float:
    values = [v for v in values if math.isfinite(v)]
    return statistics.median(values) if values else 0.0


def active_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if as_int(r, "N_MMA") > 0]


def save_line_plot(path: Path, xlabel: str, ylabel: str, title: str, series: dict[str, list[tuple[float, float]]], logx: bool = False) -> None:
    if not series:
        return
    plt.figure(figsize=(8, 5))
    for label, points in sorted(series.items()):
        points = sorted(points)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        plt.plot(xs, ys, marker="o", label=label)
    if logx:
        plt.xscale("log", base=2)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, which="both", alpha=0.3)
    if len(series) <= 16:
        plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_energy_vs_gpu(rows: list[dict[str, str]], outdir: Path) -> None:
    by_run: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "e": 0.0})
    for row in rows:
        run_id = row.get("run_id", "")
        n_gpu = as_int(row, "n_gpu_active")
        if n_gpu == 0 or row.get("notes", "").find("gpu_active=1") < 0:
            continue
        by_run[run_id]["n"] = n_gpu
        by_run[run_id]["e"] += as_float(row, "net_E_J")
    grouped: dict[int, list[float]] = defaultdict(list)
    for item in by_run.values():
        grouped[int(item["n"])].append(item["e"])
    series = {"active GPU net energy": [(n, median(v)) for n, v in grouped.items()]}
    save_line_plot(outdir / "energy_vs_active_gpu_count.png", "active GPU count", "net energy (J)", "Energy vs active GPU count", series)


def plot_energy_vs_active_sm(rows: list[dict[str, str]], outdir: Path) -> None:
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in active_rows(rows):
        grouped[(row.get("mode", ""), as_int(row, "active_SM"))].append(as_float(row, "net_E_J"))
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for (mode, active_sm), values in grouped.items():
        series[mode].append((active_sm, median(values)))
    save_line_plot(outdir / "energy_vs_active_sm_count.png", "active SM count", "net energy (J)", "Energy vs active SM count", series, logx=True)


def plot_pj_vs_blocks(rows: list[dict[str, str]], outdir: Path) -> None:
    grouped: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for row in active_rows(rows):
        key = (row.get("mode", ""), as_int(row, "W_SM_KiB"), as_int(row, "blocks_per_SM"))
        grouped[key].append(as_float(row, "pJ_per_FLOP"))
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for (mode, w_sm, blocks), values in grouped.items():
        series[f"{mode} W={w_sm}KiB"].append((blocks, median(values)))
    save_line_plot(outdir / "pj_flop_vs_blocks_per_sm.png", "blocks/SM", "pJ/FLOP", "pJ/FLOP vs blocks/SM", series, logx=True)


def plot_pj_vs_wsm(rows: list[dict[str, str]], outdir: Path, metric: str, filename: str, ylabel: str) -> None:
    grouped: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for row in active_rows(rows):
        key = (row.get("mode", ""), as_int(row, "blocks_per_SM"), as_int(row, "W_SM_KiB"))
        grouped[key].append(as_float(row, metric))
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for (mode, blocks, w_sm), values in grouped.items():
        series[f"{mode} B={blocks}"].append((w_sm, median(values)))
    save_line_plot(outdir / filename, "W_SM (KiB)", ylabel, f"{ylabel} vs W_SM", series, logx=True)


def plot_ncu_bytes_per_op(rows: list[dict[str, str]], outdir: Path) -> None:
    metrics = [
        ("ncu_shared_bytes", "shared bytes/op"),
        ("ncu_l2_bytes", "L2 bytes/op"),
        ("ncu_dram_bytes", "DRAM bytes/op"),
    ]
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in active_rows(rows):
        n_mma = as_float(row, "N_MMA")
        if n_mma <= 0:
            continue
        w_sm = as_int(row, "W_SM_KiB")
        mode = row.get("mode", "")
        for key, label in metrics:
            value = as_float(row, key)
            if value > 0:
                series[f"{mode} {label}"].append((w_sm, value / n_mma))
    save_line_plot(outdir / "ncu_bytes_per_logical_op_vs_wsm.png", "W_SM (KiB)", "bytes / logical op", "NCU bytes per logical op vs W_SM", series, logx=True)


def classify(w_sm: int, b: int) -> int:
    if w_sm < b:
        return 0
    if w_sm + b <= 164 and (w_sm / b) <= 163:
        return 1
    if 108 * w_sm / 1024.0 <= 40:
        return 2
    return 3


def plot_feasibility_heatmap(outdir: Path) -> None:
    labels = ["invalid_min_tile", "shared_resident", "l2_candidate", "dram_mixed_streaming"]
    colors = ["#d9d9d9", "#4c78a8", "#59a14f", "#f28e2b"]
    cmap = ListedColormap(colors)
    matrix = [[classify(w, b) for b in BLOCKS_PER_SM] for w in W_SM_KIB]
    plt.figure(figsize=(8, 7))
    plt.imshow(matrix, aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=3)
    plt.xticks(range(len(BLOCKS_PER_SM)), BLOCKS_PER_SM)
    plt.yticks(range(len(W_SM_KIB)), [str(w) for w in W_SM_KIB])
    plt.xlabel("blocks/SM")
    plt.ylabel("W_SM (KiB)")
    plt.title("Feasibility heatmap")
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[i]) for i in range(len(labels))]
    plt.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)
    plt.tight_layout()
    plt.savefig(outdir / "feasibility_heatmap.png", dpi=180)
    plt.close()


def plot_residual_if_present(rows: list[dict[str, str]], outdir: Path) -> None:
    if not rows or "predicted_E_J" not in rows[0]:
        return
    points = []
    for row in active_rows(rows):
        predicted = as_float(row, "predicted_E_J", float("nan"))
        actual = as_float(row, "net_E_J", float("nan"))
        if math.isfinite(predicted) and math.isfinite(actual):
            points.append((predicted, actual - predicted))
    if not points:
        return
    plt.figure(figsize=(7, 5))
    plt.scatter([p[0] for p in points], [p[1] for p in points], s=18)
    plt.axhline(0.0, color="black", linewidth=1)
    plt.xlabel("predicted energy (J)")
    plt.ylabel("residual (J)")
    plt.title("Regression residual")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "regression_residual.png", dpi=180)
    plt.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--outdir", default="results/plots")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(Path(args.csv))

    plot_energy_vs_gpu(rows, outdir)
    plot_energy_vs_active_sm(rows, outdir)
    plot_pj_vs_blocks(rows, outdir)
    plot_pj_vs_wsm(rows, outdir, "pJ_per_FLOP", "pj_flop_vs_wsm.png", "pJ/FLOP")
    plot_pj_vs_wsm(rows, outdir, "pJ_per_input_bit", "pj_input_bit_vs_wsm.png", "pJ/input-bit")
    plot_ncu_bytes_per_op(rows, outdir)
    plot_feasibility_heatmap(outdir)
    plot_residual_if_present(rows, outdir)
    print(f"plots written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
