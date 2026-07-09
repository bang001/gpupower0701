#!/usr/bin/env python3
"""Audit matched-control weak-signal and negative-row instability."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def as_float(row: dict[str, str], key: str) -> float:
    try:
        value = row.get(key, "")
        if value == "":
            return float("nan")
        return float(value)
    except ValueError:
        return float("nan")


def finite_stats(values: list[float]) -> tuple[str, str, str]:
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return "", "", ""
    return (
        f"{min(finite):.12g}",
        f"{statistics.median(finite):.12g}",
        f"{max(finite):.12g}",
    )


def split_reasons(value: str) -> list[str]:
    return [item for item in value.split(";") if item]


def coordinate(row: dict[str, str]) -> str:
    return (
        f"W={row.get('W_SM_KiB', '')}KiB,"
        f"B/SM={row.get('blocks_per_SM', '')},"
        f"RF={row.get('reuse_factor', '')},"
        f"LR={row.get('load_repeat', '')},"
        f"delta_E={as_float(row, 'delta_E_J'):.4g}J,"
        f"frac={as_float(row, 'delta_signal_fraction'):.4g}"
    )


def component_recommendation(reason_counts: Counter[str], invalid_rows: int) -> str:
    if invalid_rows == 0:
        return "no_followup_required_by_detail_rows"
    has_negative = reason_counts.get("negative_coefficient", 0) > 0
    has_weak = any(key.startswith("delta_E<") or key.startswith("delta_fraction<") for key in reason_counts)
    if has_negative and has_weak:
        return (
            "targeted_stability_rerun;use_longer_seconds_20_to_30;"
            "increase_repeats_10_or_more;keep_power_api_audit;"
            "inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate"
        )
    if has_negative:
        return (
            "targeted_control_drift_rerun;increase_repeats_10_or_more;"
            "inspect_nearest_control_distance_temperature_clock;do_not_report_negative_rows"
        )
    if has_weak:
        return (
            "weak_signal_rerun;increase_seconds_20_to_30;"
            "prefer_high_signal_factor_rows;keep_min_delta_and_fraction_gate"
        )
    return "inspect_invalid_rows_before_final_claim"


def audit(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("component", "")].append(row)

    out_rows: list[dict[str, str]] = []
    for component, comp_rows in sorted(grouped.items()):
        valid = [row for row in comp_rows if truthy(row.get("valid_component_estimate", ""))]
        invalid = [row for row in comp_rows if not truthy(row.get("valid_component_estimate", ""))]

        reason_counts: Counter[str] = Counter()
        for row in invalid:
            reason_counts.update(split_reasons(row.get("diagnostic", "")))

        valid_delta_stats = finite_stats([as_float(row, "delta_E_J") for row in valid])
        invalid_delta_stats = finite_stats([as_float(row, "delta_E_J") for row in invalid])
        valid_fraction_stats = finite_stats(
            [as_float(row, "delta_signal_fraction") for row in valid]
        )
        invalid_fraction_stats = finite_stats(
            [as_float(row, "delta_signal_fraction") for row in invalid]
        )
        coefficient_key = (
            "coefficient_pJ_per_bit"
            if any(row.get("coefficient_pJ_per_bit", "") for row in comp_rows)
            else "coefficient"
        )
        coefficient_stats = finite_stats([as_float(row, coefficient_key) for row in valid])

        status = "stable_detail_rows"
        if invalid:
            status = "needs_stability_followup"
        if not valid:
            status = "no_valid_rows"

        out_rows.append(
            {
                "component": component,
                "status": status,
                "total_rows": str(len(comp_rows)),
                "valid_rows": str(len(valid)),
                "invalid_rows": str(len(invalid)),
                "invalid_reason_counts": ";".join(
                    f"{key}:{count}" for key, count in sorted(reason_counts.items())
                ),
                "invalid_coordinates": " | ".join(coordinate(row) for row in invalid),
                "valid_delta_E_min_J": valid_delta_stats[0],
                "valid_delta_E_median_J": valid_delta_stats[1],
                "valid_delta_E_max_J": valid_delta_stats[2],
                "invalid_delta_E_min_J": invalid_delta_stats[0],
                "invalid_delta_E_median_J": invalid_delta_stats[1],
                "invalid_delta_E_max_J": invalid_delta_stats[2],
                "valid_signal_fraction_min": valid_fraction_stats[0],
                "valid_signal_fraction_median": valid_fraction_stats[1],
                "valid_signal_fraction_max": valid_fraction_stats[2],
                "invalid_signal_fraction_min": invalid_fraction_stats[0],
                "invalid_signal_fraction_median": invalid_fraction_stats[1],
                "invalid_signal_fraction_max": invalid_fraction_stats[2],
                "valid_coefficient_min": coefficient_stats[0],
                "valid_coefficient_median": coefficient_stats[1],
                "valid_coefficient_max": coefficient_stats[2],
                "recommendation": component_recommendation(reason_counts, len(invalid)),
            }
        )
    return out_rows


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "component",
        "status",
        "total_rows",
        "valid_rows",
        "invalid_rows",
        "invalid_reason_counts",
        "invalid_coordinates",
        "valid_delta_E_min_J",
        "valid_delta_E_median_J",
        "valid_delta_E_max_J",
        "invalid_delta_E_min_J",
        "invalid_delta_E_median_J",
        "invalid_delta_E_max_J",
        "valid_signal_fraction_min",
        "valid_signal_fraction_median",
        "valid_signal_fraction_max",
        "invalid_signal_fraction_min",
        "invalid_signal_fraction_median",
        "invalid_signal_fraction_max",
        "valid_coefficient_min",
        "valid_coefficient_median",
        "valid_coefficient_max",
        "recommendation",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: str, rows: list[dict[str, str]], detail_csv: str, out_csv: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write("# Matched-Control Instability Audit\n\n")
        f.write(
            "This report explains weak-signal or negative matched-control rows. "
            "It does not change coefficients; it identifies why some rows were "
            "excluded from the component summary and what follow-up experiment is "
            "needed.\n\n"
        )
        f.write(f"- matched-control detail: `{detail_csv}`\n")
        f.write(f"- audit CSV: `{out_csv}`\n\n")

        f.write("## Component Summary\n\n")
        f.write(
            "| component | status | valid/total | invalid reasons | valid delta_E median (J) | "
            "valid signal fraction median | valid coefficient median | recommendation |\n"
        )
        f.write("|---|---|---:|---|---:|---:|---:|---|\n")
        for row in rows:
            valid_total = f"{row['valid_rows']}/{row['total_rows']}"
            f.write(
                f"| `{row['component']}` | `{row['status']}` | {valid_total} | "
                f"{row['invalid_reason_counts'] or '-'} | "
                f"{row['valid_delta_E_median_J'] or '-'} | "
                f"{row['valid_signal_fraction_median'] or '-'} | "
                f"{row['valid_coefficient_median'] or '-'} | "
                f"{row['recommendation']} |\n"
            )
        f.write("\n")

        f.write("## Invalid Coordinates\n\n")
        f.write("| component | invalid coordinates |\n|---|---|\n")
        for row in rows:
            if row["invalid_rows"] == "0":
                continue
            f.write(
                f"| `{row['component']}` | {row['invalid_coordinates'] or '-'} |\n"
            )
        f.write("\n")

        f.write("## Interpretation\n\n")
        f.write(
            "- `delta_E<...` and `delta_fraction<...` mean the treatment-control "
            "energy difference is inside the configured noise floor.\n"
        )
        f.write(
            "- `negative_coefficient` means the scaled control energy exceeded "
            "the treatment energy. With NCU path accepted, this usually points "
            "to weak board-level signal or control/thermal drift, not a negative "
            "physical component energy.\n"
        )
        f.write(
            "- For rows marked `needs_stability_followup`, do not relax the "
            "delta gate to make the row pass. Rerun with longer duration, more "
            "repeats, and explicit power API audit.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("matched_detail_csv")
    parser.add_argument(
        "--out-csv",
        default="results/summary/matched_control_instability_audit.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/matched_control_instability_audit.md",
    )
    args = parser.parse_args()

    rows = audit(read_csv(args.matched_detail_csv))
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args.matched_detail_csv, args.out_csv)
    status_counts = Counter(row["status"] for row in rows)
    print(
        "matched-control instability rows="
        f"{len(rows)} "
        + " ".join(f"{key}={status_counts[key]}" for key in sorted(status_counts))
    )
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
