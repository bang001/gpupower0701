#!/usr/bin/env python3
"""Plot MI-ATC coefficients, parameter sweeps, and NCU path evidence."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


COMPONENTS = ["tensor", "shared", "l1", "l2", "external"]
LABELS = {
    "tensor": "Tensor MMA",
    "shared": "Shared scalar",
    "l1": "Global L1",
    "l2": "L2 CG",
    "external": "External read",
}
COLORS = {
    "tensor": "#2E6F9E",
    "shared": "#3A7D5D",
    "l1": "#357F8E",
    "l2": "#B88719",
    "external": "#D06F2B",
}
INK = "#172A3A"
MUTED = "#667784"
GRID = "#D5DEE2"
DIRECT = "#2E6F9E"
MI_ATC = "#D06F2B"
CONTROL_RATE = "#7A6A2F"
REGRESSION = "#3A7D5D"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.unicode_minus": False,
            "mathtext.fontset": "dejavusans",
            "svg.fonttype": "none",
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def number(row: dict[str, Any], field: str) -> float:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError):
        return float("nan")
    return value if math.isfinite(value) else float("nan")


def truthy(row: dict[str, Any], field: str) -> bool:
    return str(row.get(field, "")).lower() in {"1", "true", "yes"}


def finite_median(values: list[float]) -> float:
    usable = [value for value in values if math.isfinite(value)]
    return statistics.median(usable) if usable else float("nan")


def save_pair(fig: plt.Figure, output_dir: Path, prefix: str, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg"):
        path = output_dir / f"{prefix}_{stem}.{suffix}"
        fig.savefig(path, dpi=220 if suffix == "png" else None, bbox_inches="tight")
        if suffix == "svg":
            text = path.read_text(encoding="utf-8")
            path.write_text(
                "\n".join(line.rstrip() for line in text.splitlines()) + "\n",
                encoding="utf-8",
            )
    plt.close(fig)


def coefficient_error(row: dict[str, str]) -> tuple[float, float, float]:
    value = number(row, "median")
    low = number(row, "bootstrap_ci_low")
    high = number(row, "bootstrap_ci_high")
    lower = max(0.0, value - low) if math.isfinite(low) else 0.0
    upper = max(0.0, high - value) if math.isfinite(high) else 0.0
    return value, lower, upper


def plot_coefficients(
    summary: list[dict[str, str]],
    regression: list[dict[str, str]],
    output_dir: Path,
    prefix: str,
) -> None:
    summary_map = {
        (row.get("component", ""), row.get("estimate_method", "")): row
        for row in summary
    }
    regression_map = {row.get("component", ""): row for row in regression}
    present = {
        row.get("component", "")
        for row in summary
        if row.get("component", "") in COMPONENTS
    }
    panels: list[tuple[list[str], str, str]] = []
    if "tensor" in present:
        panels.append((["tensor"], "Tensor dynamic-path coefficient", "pJ/FLOP"))
    memory_components = [component for component in COMPONENTS[1:] if component in present]
    if memory_components:
        panels.append(
            (memory_components, "Memory-path effective coefficients", "pJ/bit")
        )
    if not panels:
        return
    panel_widths = [max(1.0, len(components) * 0.85) for components, _, _ in panels]
    fig, axes_object = plt.subplots(
        1,
        len(panels),
        figsize=(8.4 if len(panels) == 1 else 14.4, 5.8),
        gridspec_kw={"width_ratios": panel_widths},
        squeeze=False,
    )
    axes = list(axes_object.flat)
    regression_labels_seen: set[str] = set()

    for ax, (components, title, unit) in zip(axes, panels):
        positions = list(range(len(components)))
        for offset, method, label, color in (
            (-0.28, "matched_iter_completion", "Matched-ITER completion", DIRECT),
            (0.0, "mi_atc", "Clocked MI-ATC", MI_ATC),
            (0.28, "control_rate_atc", "Control-rate ATC", CONTROL_RATE),
        ):
            for position, component in zip(positions, components):
                row = summary_map.get((component, method), {})
                value, lower, upper = coefficient_error(row)
                if not math.isfinite(value):
                    continue
                status = row.get("status", "")
                alpha = 1.0 if status == "accepted" else 0.58
                ax.bar(
                    position + offset,
                    value,
                    width=0.25,
                    color=color,
                    alpha=alpha,
                    label=label if position == 0 else None,
                )
                ax.errorbar(
                    position + offset,
                    value,
                    yerr=[[lower], [upper]],
                    fmt="none",
                    ecolor=INK,
                    capsize=3,
                    linewidth=1.2,
                )
                label_y = value + upper if value >= 0.0 else value - lower
                ax.annotate(
                    f"{value:.3g}",
                    (position + offset, label_y),
                    xytext=(0, 5 if value >= 0.0 else -6),
                    textcoords="offset points",
                    ha="center",
                    va="bottom" if value >= 0.0 else "top",
                    fontsize=8.5,
                )
        for position, component in zip(positions, components):
            row = regression_map.get(component, {})
            value = number(row, "component_coefficient")
            if math.isfinite(value):
                status = row.get("status", "")
                identified = status in {
                    "accepted",
                    "diagnostic_only_quiescence_unverified",
                }
                regression_label = (
                    "Traffic/time regression"
                    if identified
                    else "Regression not identified"
                )
                if identified:
                    ax.scatter(
                        position,
                        value,
                        marker="D",
                        s=45,
                        color=REGRESSION,
                        zorder=4,
                        label=(
                            regression_label
                            if regression_label not in regression_labels_seen
                            else None
                        ),
                    )
                else:
                    # A failed fit is a status, not a coefficient. Plot it in
                    # axes coordinates so an extreme diagnostic estimate cannot
                    # collapse the scale of the measured bars.
                    ax.scatter(
                        position,
                        0.97,
                        transform=ax.get_xaxis_transform(),
                        marker="x",
                        s=45,
                        color=MUTED,
                        zorder=4,
                        clip_on=False,
                        label=(
                            regression_label
                            if regression_label not in regression_labels_seen
                            else None
                        ),
                    )
                regression_labels_seen.add(regression_label)
        ax.set_xticks(positions, [LABELS[item] for item in components])
        ax.set_ylabel(unit)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.axhline(0.0, color=INK, linewidth=0.8)
        ax.margins(y=0.18)
        ax.spines[["top", "right"]].set_visible(False)
    legend_handles: list[Any] = []
    legend_labels: list[str] = []
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            if label and label not in legend_labels:
                legend_handles.append(handle)
                legend_labels.append(label)
    fig.legend(
        legend_handles,
        legend_labels,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=min(4, len(legend_labels)),
    )
    fig.suptitle(
        "Board-level differential coefficients: direct observation and modeled correction",
        x=0.04,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.04,
        0.01,
        "Bars use all measurement-valid signed rows; intervals are coordinate-cluster bootstrap CIs and negative rows are not discarded. "
        "Faded bars are diagnostic/rejected statuses; green diamonds are identified regressions and gray x marks at the panel top mean not identified. "
        "Values are effective board-level coefficients, not pure silicon energy.",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0.02, 0.05, 1, 0.84))
    save_pair(fig, output_dir, prefix, "coefficient_methods")


def plot_sweeps(
    detail: list[dict[str, str]], output_dir: Path, prefix: str
) -> None:
    present_components = [
        component
        for component in COMPONENTS
        if any(row.get("component") == component for row in detail)
    ]
    if not present_components:
        return
    columns = min(3, len(present_components))
    rows_count = math.ceil(len(present_components) / columns)
    fig, axes_object = plt.subplots(
        rows_count,
        columns,
        figsize=(5.4 * columns, 4.6 * rows_count + 1.3),
        squeeze=False,
    )
    axes = list(axes_object.flat)
    blocks_values = sorted(
        {
            number(row, "blocks_per_SM")
            for row in detail
            if math.isfinite(number(row, "blocks_per_SM"))
        }
    )
    blocks_colors = ["#2E6F9E", "#3A7D5D", "#D06F2B", "#A84D75"]
    for ax, component in zip(axes, present_components):
        rows = [row for row in detail if row.get("component") == component]
        factors = sorted(
            {
                number(row, "factor_value")
                for row in rows
                if math.isfinite(number(row, "factor_value"))
            }
        )
        for color, blocks_per_sm in zip(blocks_colors, blocks_values):
            blocks_rows = [
                row for row in rows if number(row, "blocks_per_SM") == blocks_per_sm
            ]
            direct = []
            corrected = []
            control_rate = []
            for factor in factors:
                factor_rows = [
                    row
                    for row in blocks_rows
                    if number(row, "factor_value") == factor
                ]
                direct.append(
                    finite_median(
                        [
                            number(row, "completion_coefficient")
                            for row in factor_rows
                            if truthy(row, "measurement_valid")
                        ]
                    )
                )
                corrected.append(
                    finite_median(
                        [
                            number(row, "mi_atc_coefficient")
                            for row in factor_rows
                            if truthy(row, "measurement_valid")
                        ]
                    )
                )
                control_rate.append(
                    finite_median(
                        [
                            number(row, "control_rate_atc_coefficient")
                            for row in factor_rows
                            if truthy(row, "measurement_valid")
                        ]
                    )
                )
            ax.plot(
                factors,
                direct,
                color=color,
                marker="o",
                linewidth=2,
                label=f"B={blocks_per_sm:g} direct",
            )
            ax.plot(
                factors,
                corrected,
                color=color,
                marker="^",
                linewidth=1.6,
                linestyle="--",
                label=f"B={blocks_per_sm:g} MI-ATC",
            )
            if component == "tensor":
                ax.plot(
                    factors,
                    control_rate,
                    color=color,
                    marker="s",
                    linewidth=1.4,
                    linestyle=":",
                    label=f"B={blocks_per_sm:g} operand-rate",
                )
        unit = "pJ/FLOP" if component == "tensor" else "pJ/bit"
        ax.set_title(LABELS[component], loc="left", fontweight="bold")
        ax.set_xlabel(
            "Reuse factor [count]" if component == "tensor" else "Load repeat [count]"
        )
        ax.set_ylabel(unit)
        ax.set_xticks(factors)
        ax.grid(color=GRID, linewidth=0.8)
        ax.axhline(0.0, color=INK, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes[len(present_components):]:
        ax.set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.075),
        ncol=min(3, max(1, len(labels))),
    )
    fig.text(
        0.5,
        0.015,
        "Solid: matched-ITER completion\nDashed: clocked MI-ATC\n"
        "Dotted squares: Tensor operand-rate ATC\n"
        "Points are signed medians across all measurement-valid rows",
        ha="center",
        va="center",
        color=MUTED,
    )
    figure_title = (
        "Tensor coefficient sensitivity across reuse factor and blocks per SM"
        if present_components == ["tensor"]
        else "Coefficient sensitivity across RF/LR and blocks per SM"
    )
    fig.suptitle(
        figure_title,
        x=0.04,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0.02, 0.16, 1, 0.92))
    save_pair(fig, output_dir, prefix, "parameter_sweep")


def component_ncu_value(
    rows: list[dict[str, str]], component: str, field: str, blocks_per_sm: float | None = None
) -> float:
    return finite_median(
        [
            number(row, field)
            for row in rows
            if row.get("component") == component and row.get("role") == "treatment"
            and (
                blocks_per_sm is None
                or number(row, "blocks_per_SM") == blocks_per_sm
            )
        ]
    )


def component_ncu_first_value(
    rows: list[dict[str, str]],
    component: str,
    fields: tuple[str, ...],
    blocks_per_sm: float,
) -> float:
    values: list[float] = []
    for row in rows:
        if row.get("component") != component or row.get("role") != "treatment":
            continue
        if number(row, "blocks_per_SM") != blocks_per_sm:
            continue
        for field in fields:
            value = number(row, field)
            if math.isfinite(value):
                values.append(value)
                break
    return finite_median(values)


def tensor_role_ncu_value(
    rows: list[dict[str, str]],
    role: str,
    field: str,
    blocks_per_sm: float | None = None,
    reuse_factor: float | None = None,
) -> float:
    return finite_median(
        [
            number(row, field)
            for row in rows
            if row.get("component") == "tensor"
            and row.get("role") == role
            and (
                blocks_per_sm is None
                or number(row, "blocks_per_SM") == blocks_per_sm
            )
            and (
                reuse_factor is None
                or number(row, "reuse_factor") == reuse_factor
            )
        ]
    )


def plot_ncu_evidence(
    evidence: list[dict[str, str]], output_dir: Path, prefix: str
) -> None:
    memory = COMPONENTS[1:]
    memory_evidence = [row for row in evidence if row.get("component") in memory]
    if not memory_evidence:
        return
    access_fields = {
        "shared": ("shared_accesses", "shared_read_bytes"),
        "l1": ("l1_accesses", "l1_request_bytes"),
        "l2": ("l2_accesses", "l2_read_bytes"),
        "external": ("dram_accesses", "dram_read_bytes"),
    }
    hit_fields = {
        "shared": (),
        "l1": ("l1_path_hit_rate_pct",),
        "l2": ("l2_logical_read_hit_rate_pct", "l2_path_hit_rate_pct"),
        "external": ("l2_logical_read_hit_rate_pct", "l2_path_hit_rate_pct"),
    }
    blocks_values = sorted(
        {
            number(row, "blocks_per_SM")
            for row in memory_evidence
            if row.get("role") == "treatment"
            and math.isfinite(number(row, "blocks_per_SM"))
        }
    )
    blocks_colors = ["#2E6F9E", "#3A7D5D", "#D06F2B", "#A84D75"]
    positions = list(range(len(memory)))
    fig, axes_grid = plt.subplots(2, 2, figsize=(15.4, 9.0))
    axes = axes_grid.flat
    width = 0.72 / max(len(blocks_values), 1)
    offsets = [
        (index - (len(blocks_values) - 1) / 2.0) * width
        for index in range(len(blocks_values))
    ]

    for offset, blocks_per_sm, color in zip(offsets, blocks_values, blocks_colors):
        accesses = [
            component_ncu_value(evidence, item, access_fields[item][0], blocks_per_sm)
            for item in memory
        ]
        byte_values = [
            component_ncu_value(evidence, item, access_fields[item][1], blocks_per_sm)
            for item in memory
        ]
        hit_values = [
            component_ncu_first_value(
                evidence, item, hit_fields[item], blocks_per_sm
            )
            if hit_fields[item]
            else float("nan")
            for item in memory
        ]
        stalls = [
            component_ncu_value(
                evidence, item, "stall_long_scoreboard_pct", blocks_per_sm
            )
            for item in memory
        ]
        x = [value + offset for value in positions]
        label = f"B={blocks_per_sm:g}"
        axes[0].bar(x, accesses, width, color=color, label=label)
        axes[1].bar(x, byte_values, width, color=color, label=label)
        axes[2].bar(x, hit_values, width, color=color, label=label)
        for xpos, value in zip(x, hit_values):
            if math.isfinite(value):
                axes[2].text(
                    xpos,
                    min(106.0, value + 2.0),
                    f"{value:.3g}",
                    ha="center",
                    va="bottom",
                    rotation=90,
                    fontsize=7.5,
                    color=INK,
                )
        axes[3].bar(x, stalls, width, color=color, label=label)

    axes[0].set_yscale("log")
    axes[0].set_ylabel("Observed access count [log scale]")
    axes[0].set_title("NCU access count", loc="left", fontweight="bold")
    axes[0].legend(frameon=False)

    axes[1].set_yscale("log")
    axes[1].set_ylabel("Observed bytes [B, log scale]")
    axes[1].set_title("NCU traffic bytes", loc="left", fontweight="bold")

    axes[2].set_ylim(0, 110)
    axes[2].set_ylabel("Validated hit rate [%]")
    axes[2].set_title("Selected path hit rate", loc="left", fontweight="bold")
    axes[2].text(positions[0], 3, "N/A", ha="center", color=MUTED, fontsize=9)

    axes[3].set_yscale("symlog", linthresh=1.0)
    axes[3].set_ylabel("Long scoreboard [% of issue-active normalization]")
    axes[3].set_title("Dependency stall evidence", loc="left", fontweight="bold")

    for ax in axes:
        ax.set_xticks(positions, [LABELS[item] for item in memory], rotation=15, ha="right")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "NCU path validation: access, bytes, hit behavior, and stalls",
        x=0.04,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.04,
        0.01,
        "Long-scoreboard is not wall-time percentage and may exceed 100%; it is used as path behavior evidence, not an energy denominator.",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0.02, 0.06, 1, 0.93))
    save_pair(fig, output_dir, prefix, "ncu_path_evidence")


def plot_tensor_ncu_evidence(
    evidence: list[dict[str, str]], output_dir: Path, prefix: str
) -> None:
    tensor = [row for row in evidence if row.get("component") == "tensor"]
    if not tensor:
        return
    blocks_values = sorted(
        {
            number(row, "blocks_per_SM")
            for row in tensor
            if math.isfinite(number(row, "blocks_per_SM"))
        }
    )
    factors = sorted(
        {
            number(row, "reuse_factor")
            for row in tensor
            if math.isfinite(number(row, "reuse_factor"))
        }
    )
    colors = ["#2E6F9E", "#3A7D5D", "#D06F2B", "#A84D75"]
    fig, axes_grid = plt.subplots(2, 2, figsize=(14.8, 9.0))
    axes = axes_grid.flat

    for blocks_per_sm, color in zip(blocks_values, colors):
        hmma = [
            tensor_role_ncu_value(
                tensor, "treatment", "tensor_hmma_inst", blocks_per_sm, factor
            )
            / 1.0e9
            for factor in factors
        ]
        flops_per_hmma = []
        for factor in factors:
            flops = tensor_role_ncu_value(
                tensor, "treatment", "tensor_fp16_f32_ops", blocks_per_sm, factor
            )
            hmma_count = tensor_role_ncu_value(
                tensor, "treatment", "tensor_hmma_inst", blocks_per_sm, factor
            )
            flops_per_hmma.append(
                flops / hmma_count
                if math.isfinite(flops)
                and math.isfinite(hmma_count)
                and hmma_count > 0.0
                else float("nan")
            )
        axes[0].plot(
            factors,
            hmma,
            marker="o",
            linewidth=1.8,
            color=color,
            label=f"B={blocks_per_sm:g}",
        )
        axes[1].plot(
            factors,
            flops_per_hmma,
            marker="o",
            linewidth=1.8,
            color=color,
            label=f"B={blocks_per_sm:g}",
        )

    treatment_registers = [
        tensor_role_ncu_value(tensor, "treatment", "registers_per_thread", None, factor)
        for factor in factors
    ]
    control_registers = [
        tensor_role_ncu_value(tensor, "control", "registers_per_thread", None, factor)
        for factor in factors
    ]
    axes[2].plot(
        factors,
        treatment_registers,
        marker="o",
        linewidth=1.9,
        color=DIRECT,
        label="reg_mma treatment",
    )
    axes[2].plot(
        factors,
        control_registers,
        marker="s",
        linewidth=1.9,
        linestyle="--",
        color=CONTROL_RATE,
        label="operand control",
    )

    treatment_stalls = [
        tensor_role_ncu_value(
            tensor, "treatment", "stall_long_scoreboard_pct", None, factor
        )
        for factor in factors
    ]
    control_stalls = [
        tensor_role_ncu_value(
            tensor, "control", "stall_long_scoreboard_pct", None, factor
        )
        for factor in factors
    ]
    axes[3].plot(
        factors,
        treatment_stalls,
        marker="o",
        linewidth=1.9,
        color=DIRECT,
        label="reg_mma treatment",
    )
    axes[3].plot(
        factors,
        control_stalls,
        marker="s",
        linewidth=1.9,
        linestyle="--",
        color=CONTROL_RATE,
        label="operand control",
    )

    control_hmma = [
        number(row, "tensor_hmma_inst")
        for row in tensor
        if row.get("role") == "control"
        and math.isfinite(number(row, "tensor_hmma_inst"))
    ]
    spill_flags = [
        truthy(row, "spill_zero_verified")
        for row in tensor
        if str(row.get("spill_zero_verified", "")) != ""
    ]
    accepted = sum(row.get("acceptance") == "accepted" for row in tensor)
    control_hmma_max = max(control_hmma, default=float("nan"))
    spill_pass = sum(spill_flags)

    axes[0].set_ylabel("Treatment HMMA instructions [billions]")
    axes[0].set_title("Tensor instruction presence", loc="left", fontweight="bold")
    axes[0].legend(frameon=False)

    axes[1].set_ylim(bottom=0.0)
    axes[1].set_ylabel("NCU FP16 FLOP / HMMA instruction [FLOP/inst]")
    axes[1].set_title("Tensor-counter proportionality", loc="left", fontweight="bold")

    axes[2].set_ylabel("Registers per thread [count]")
    axes[2].set_title("Register-footprint evidence", loc="left", fontweight="bold")
    axes[2].legend(frameon=False)

    axes[3].set_yscale("symlog", linthresh=0.001)
    axes[3].set_ylabel("Long scoreboard [% of issue-active normalization]")
    axes[3].set_title("Dependency-stall evidence", loc="left", fontweight="bold")
    axes[3].legend(frameon=False)
    axes[3].text(
        0.98,
        0.96,
        f"accepted rows: {accepted}/{len(tensor)}\n"
        f"control HMMA max: {control_hmma_max:g}\n"
        f"zero-spill evidence: {spill_pass}/{len(spill_flags)}",
        transform=axes[3].transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color=MUTED,
        bbox={"facecolor": "white", "edgecolor": GRID, "pad": 5.0},
    )

    for ax in axes:
        ax.set_xlabel("Reuse factor [count]")
        ax.set_xticks(factors)
        ax.grid(color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "NCU validation of the FP16 Tensor treatment-control boundary",
        x=0.04,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.04,
        0.01,
        "Accepted NCU evidence must show Tensor work in reg_mma, no HMMA in the operand control, and zero spill. "
        "Overlapping FLOP/HMMA curves indicate proportional counter accounting; none of these counters directly measures silicon energy.",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0.02, 0.06, 1, 0.93))
    save_pair(fig, output_dir, prefix, "tensor_ncu_evidence")


def plot_tensor_rf_duration(
    detail: list[dict[str, str]], output_dir: Path, prefix: str
) -> None:
    rows = [
        row
        for row in detail
        if row.get("component") == "tensor" and truthy(row, "measurement_valid")
    ]
    if not rows:
        return
    blocks_values = sorted(
        {number(row, "blocks_per_SM") for row in rows if math.isfinite(number(row, "blocks_per_SM"))}
    )
    durations = sorted(
        {number(row, "target_duration_s") for row in rows if math.isfinite(number(row, "target_duration_s"))}
    )
    factors = sorted(
        {number(row, "reuse_factor") for row in rows if math.isfinite(number(row, "reuse_factor"))}
    )
    colors = ["#2E6F9E", "#3A7D5D", "#D06F2B", "#A84D75"]
    fig, axes = plt.subplots(2, 2, figsize=(13.8, 9.0))
    for ax, blocks in zip(axes.flat[:3], blocks_values[:3]):
        block_rows = [row for row in rows if number(row, "blocks_per_SM") == blocks]
        for color, duration in zip(colors, durations):
            medians = []
            for factor in factors:
                candidates = [
                    number(row, "control_rate_atc_coefficient")
                    for row in block_rows
                    if number(row, "target_duration_s") == duration
                    and number(row, "reuse_factor") == factor
                ]
                medians.append(finite_median(candidates))
            ax.plot(
                factors,
                medians,
                marker="o",
                linewidth=1.8,
                color=color,
                label=f"{duration:g} s",
            )
        ax.set_title(f"B={blocks:g} blocks/SM", loc="left", fontweight="bold")
        ax.set_xlabel("Reuse factor [count]")
        ax.set_ylabel("Operand-rate ATC [pJ/FP16 FLOP]")
        ax.set_xticks(factors)
        ax.axhline(0.0, color=INK, linewidth=0.8)
        ax.grid(color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)

    power_ax = axes.flat[3]
    for color, duration in zip(colors, durations):
        power_gap = []
        for factor in factors:
            candidates = [
                number(row, "delta_active_power_W")
                for row in rows
                if number(row, "target_duration_s") == duration
                and number(row, "reuse_factor") == factor
            ]
            power_gap.append(finite_median(candidates))
        power_ax.plot(
            factors,
            power_gap,
            marker="s",
            linewidth=1.8,
            color=color,
            label=f"{duration:g} s",
        )
    power_ax.set_title("Treatment - operand control", loc="left", fontweight="bold")
    power_ax.set_xlabel("Reuse factor [count]")
    power_ax.set_ylabel("Active power gap [W]")
    power_ax.set_xticks(factors)
    power_ax.axhline(0.0, color=INK, linewidth=0.8)
    power_ax.grid(color=GRID, linewidth=0.8)
    power_ax.spines[["top", "right"]].set_visible(False)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper center", ncol=max(1, len(labels)))
    fig.suptitle(
        "FP16 Tensor RF-duration sensitivity and control-power bias",
        x=0.04,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.04,
        0.01,
        "Operand-rate ATC is approximately (treatment power - operand-control power) / treatment throughput. "
        "A higher RF coefficient can therefore result from control-state power or throughput changes; it is not direct proof of higher Tensor silicon energy.",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0.02, 0.05, 1, 0.92))
    save_pair(fig, output_dir, prefix, "tensor_rf_duration")


def self_test() -> None:
    rows = [
        {"component": "l2", "role": "treatment", "l2_accesses": "4", "l2_read_bytes": "128"},
        {"component": "l2", "role": "treatment", "l2_accesses": "6", "l2_read_bytes": "192"},
    ]
    assert component_ncu_value(rows, "l2", "l2_accesses") == 5.0
    assert component_ncu_value(rows, "l2", "l2_read_bytes") == 160.0
    rows[0]["blocks_per_SM"] = "8"
    rows[1]["blocks_per_SM"] = "16"
    assert component_ncu_value(rows, "l2", "l2_accesses", 8.0) == 4.0
    tensor_rows = [
        {
            "component": "tensor",
            "role": "treatment",
            "blocks_per_SM": "8",
            "reuse_factor": "4",
            "tensor_hmma_inst": "32",
        },
        {
            "component": "tensor",
            "role": "control",
            "blocks_per_SM": "8",
            "reuse_factor": "4",
            "tensor_hmma_inst": "0",
        },
    ]
    assert tensor_role_ncu_value(
        tensor_rows, "treatment", "tensor_hmma_inst", 8.0, 4.0
    ) == 32.0
    assert tensor_role_ncu_value(
        tensor_rows, "control", "tensor_hmma_inst", 8.0, 4.0
    ) == 0.0
    assert truthy({"ok": "true"}, "ok")
    print("component dynamic-attribution plot self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--detail")
    parser.add_argument("--summary")
    parser.add_argument("--regression")
    parser.add_argument("--ncu-evidence")
    parser.add_argument("--output-dir", default="docs/assets/component_energy_method")
    parser.add_argument("--prefix", default="component_dynamic_attribution")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    required = [args.detail, args.summary, args.regression, args.ncu_evidence]
    if not all(required):
        parser.error("--detail, --summary, --regression, and --ncu-evidence are required")
    configure_style()
    detail = read_csv(Path(args.detail))
    summary = read_csv(Path(args.summary))
    regression = read_csv(Path(args.regression))
    evidence = read_csv(Path(args.ncu_evidence))
    output_dir = Path(args.output_dir)
    plot_coefficients(summary, regression, output_dir, args.prefix)
    plot_sweeps(detail, output_dir, args.prefix)
    plot_tensor_rf_duration(detail, output_dir, args.prefix)
    plot_tensor_ncu_evidence(evidence, output_dir, args.prefix)
    plot_ncu_evidence(evidence, output_dir, args.prefix)
    print(f"wrote figures under {output_dir} with prefix {args.prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
