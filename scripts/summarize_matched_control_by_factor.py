#!/usr/bin/env python3
"""Summarize matched-control detail rows by component and factor.

The main matched-control analyzer intentionally reports one component-level
summary.  For sensitivity checks, especially Shared/L1 LR sweeps, we also need
the same coefficient statistics split by load_repeat or reuse_factor.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def finite(values: list[float]) -> list[float]:
    return [v for v in values if math.isfinite(v)]


def q(values: list[float], quantile: float) -> float:
    data = sorted(finite(values))
    if not data:
        return float("nan")
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * quantile
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return data[lo]
    weight = pos - lo
    return data[lo] * (1.0 - weight) + data[hi] * weight


def stats(values: list[float]) -> dict[str, float]:
    data = finite(values)
    if not data:
        return {
            "min": float("nan"),
            "median": float("nan"),
            "mean": float("nan"),
            "max": float("nan"),
            "stdev": float("nan"),
            "q1": float("nan"),
            "q3": float("nan"),
        }
    return {
        "min": min(data),
        "median": statistics.median(data),
        "mean": statistics.mean(data),
        "max": max(data),
        "stdev": statistics.stdev(data) if len(data) >= 2 else 0.0,
        "q1": q(data, 0.25),
        "q3": q(data, 0.75),
    }


def format_float(value: float) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.12g}"


def factor_key(row: dict[str, str], factor: str) -> str:
    value = row.get(factor, "")
    if value == "":
        return "(empty)"
    try:
        parsed = float(value)
    except ValueError:
        return value
    rounded = round(parsed)
    if abs(parsed - rounded) < 1.0e-9:
        return str(int(rounded))
    return f"{parsed:g}"


def sortable_factor(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), value)
    except ValueError:
        return (1, 0.0, value)


def build_rows(rows: list[dict[str, str]], factor: str) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("component", ""), factor_key(row, factor))].append(row)

    out_rows: list[dict[str, str]] = []
    for (component, factor_value), group in sorted(
        grouped.items(), key=lambda item: (item[0][0], sortable_factor(item[0][1]))
    ):
        valid_rows = [row for row in group if truthy(row.get("valid_component_estimate", ""))]
        invalid_rows = [row for row in group if not truthy(row.get("valid_component_estimate", ""))]
        coeffs = [as_float(row, "coefficient") for row in valid_rows]
        bit_coeffs = [
            as_float(row, "coefficient_pJ_per_bit")
            for row in valid_rows
            if row.get("coefficient_pJ_per_bit", "") != ""
        ]
        deltas = [as_float(row, "delta_E_J") for row in valid_rows]
        signal = [as_float(row, "delta_signal_fraction") for row in valid_rows]
        denominators = [as_float(row, "denominator") for row in valid_rows]
        coeff_stats = stats(coeffs)
        bit_stats = stats(bit_coeffs)
        delta_stats = stats(deltas)
        signal_stats = stats(signal)
        denominator_stats = stats(denominators)
        diagnostics = sorted(
            set(row.get("diagnostic", "") for row in invalid_rows if row.get("diagnostic", ""))
        )
        unit = valid_rows[0].get("coefficient_unit", "") if valid_rows else ""
        out_rows.append(
            {
                "component": component,
                "factor": factor,
                "factor_value": factor_value,
                "valid_rows": str(len(valid_rows)),
                "total_rows": str(len(group)),
                "invalid_rows": str(len(invalid_rows)),
                "invalid_diagnostics": ";".join(diagnostics),
                "unit": unit,
                "median": format_float(coeff_stats["median"]),
                "min": format_float(coeff_stats["min"]),
                "max": format_float(coeff_stats["max"]),
                "stdev": format_float(coeff_stats["stdev"]),
                "median_pJ_per_bit": format_float(bit_stats["median"]),
                "min_pJ_per_bit": format_float(bit_stats["min"]),
                "max_pJ_per_bit": format_float(bit_stats["max"]),
                "delta_E_median_J": format_float(delta_stats["median"]),
                "signal_fraction_median": format_float(signal_stats["median"]),
                "denominator_median": format_float(denominator_stats["median"]),
            }
        )
    return out_rows


def write_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "component",
        "factor",
        "factor_value",
        "valid_rows",
        "total_rows",
        "invalid_rows",
        "invalid_diagnostics",
        "unit",
        "median",
        "min",
        "max",
        "stdev",
        "median_pJ_per_bit",
        "min_pJ_per_bit",
        "max_pJ_per_bit",
        "delta_E_median_J",
        "signal_fraction_median",
        "denominator_median",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: str | Path, rows: list[dict[str, str]], detail_path: str, factor: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Matched-Control Factor Summary",
        "",
        f"- detail CSV: `{detail_path}`",
        f"- factor: `{factor}`",
        "",
        "| component | factor value | valid/total | median | unit | median pJ/bit | delta_E median (J) | signal fraction median | invalid diagnostics |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {component} | {factor_value} | {valid_rows}/{total_rows} | {median} | "
            "{unit} | {median_pJ_per_bit} | {delta_E_median_J} | "
            "{signal_fraction_median} | {invalid_diagnostics} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This table does not recompute energy. It summarizes valid matched-control detail rows by factor.",
            "- `median_pJ_per_bit` is meaningful only for memory-path rows where the matched-control analyzer emitted that column.",
            "- Invalid diagnostics are retained because weak-signal rows are evidence about measurement stability, not values to hide.",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("detail_csv")
    parser.add_argument("--factor", default="load_repeat")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    rows = build_rows(read_csv(args.detail_csv), args.factor)
    write_csv(args.out_csv, rows)
    write_md(args.out_md, rows, args.detail_csv, args.factor)
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
