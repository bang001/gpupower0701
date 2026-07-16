#!/usr/bin/env python3
"""Audit raw energy rows for power-state outliers.

This is a measurement-quality audit. It does not prove or reject NCU paths and
it does not compute component coefficients. Its purpose is to separate obvious
row-level power-state anomalies from ordinary weak matched-control signal.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


def source_id(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1] if normalized else ""


def is_active_row(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=1" in notes:
        return True
    if "gpu_active=0" in notes:
        return False
    return as_float(row, "n_gpu_active") > 0.0


def as_float(row: dict[str, str], key: str) -> float:
    try:
        value = row.get(key, "")
        if value == "":
            return float("nan")
        return float(value)
    except ValueError:
        return float("nan")


def median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def mad(values: list[float], center: float) -> float:
    finite = [abs(value - center) for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else float("nan")


def normalized(value: str, default: str = "") -> str:
    if value == "":
        return default
    try:
        parsed = float(value)
    except ValueError:
        return value
    if not math.isfinite(parsed):
        return default
    rounded = round(parsed)
    if abs(parsed - rounded) < 1.0e-9:
        return str(int(rounded))
    return f"{parsed:g}"


def group_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("_sweep_source_id", ""),
        row.get("profile_name", ""),
        row.get("gpu_id", ""),
        row.get("n_gpu_active", ""),
        row.get("mode", ""),
        normalized(row.get("W_SM_KiB", "")),
        normalized(row.get("blocks_per_SM", "")),
        normalized(row.get("active_SM", "")),
        normalized(row.get("reuse_factor", "1"), "1"),
        normalized(row.get("load_repeat", "1"), "1"),
        normalized(row.get("store_repeat", "1"), "1"),
    )


def read_rows(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_sources: dict[str, str] = {}
    for path in paths:
        sweep_source_id = source_id(path)
        if not sweep_source_id:
            raise ValueError(f"raw CSV path has no portable source id: {path!r}")
        previous = seen_sources.get(sweep_source_id)
        if previous and Path(previous) != Path(path):
            raise ValueError(
                "raw CSV basenames must be unique for portable audit joins: "
                f"{previous!r} and {path!r} both map to {sweep_source_id!r}"
            )
        seen_sources[sweep_source_id] = path
        with Path(path).open(newline="") as f:
            for idx, row in enumerate(csv.DictReader(f), start=2):
                row = dict(row)
                row["_input_file"] = path
                row["_sweep_source_id"] = sweep_source_id
                row["_row_index"] = str(idx)
                elapsed = as_float(row, "elapsed_s")
                energy = as_float(row, "net_E_J")
                row["_avg_power_W"] = (
                    f"{energy / elapsed:.12g}"
                    if elapsed > 0.0 and math.isfinite(energy)
                    else ""
                )
                rows.append(row)
    return rows


def audit(
    rows: list[dict[str, str]],
    *,
    min_group_size: int,
    relative_power_tolerance: float,
    min_power_delta_w: float,
    mad_threshold: float,
    endpoint_after_min_ratio: float,
    temp_delta_c: float,
    clock_delta_pct: float,
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[group_key(row)].append(row)

    group_stats: dict[tuple[str, ...], dict[str, float]] = {}
    for key, group in grouped.items():
        powers = [as_float(row, "_avg_power_W") for row in group]
        power_median = median(powers)
        power_mad = mad(powers, power_median)
        endpoint_after = [as_float(row, "power_after_mw") / 1000.0 for row in group]
        temp = [as_float(row, "temp_C") for row in group]
        clock = [as_float(row, "clock_sm_mhz") for row in group]
        group_stats[key] = {
            "rows": float(len(group)),
            "power_median": power_median,
            "power_mad": power_mad,
            "endpoint_after_median": median(endpoint_after),
            "temp_median": median(temp),
            "clock_median": median(clock),
        }

    out: list[dict[str, str]] = []
    for row in rows:
        key = group_key(row)
        stats = group_stats[key]
        avg_power = as_float(row, "_avg_power_W")
        endpoint_after_w = as_float(row, "power_after_mw") / 1000.0
        temp = as_float(row, "temp_C")
        clock = as_float(row, "clock_sm_mhz")
        reasons: list[str] = []
        notes: list[str] = []
        power_delta_w = float("nan")

        if stats["rows"] < min_group_size:
            notes.append("small_group")

        power_median = stats["power_median"]
        if not math.isfinite(avg_power) or avg_power <= 0.0:
            reasons.append("invalid_average_power")
        elif math.isfinite(power_median) and power_median > 0.0:
            power_delta_w = avg_power - power_median
            abs_delta_w = abs(power_delta_w)
            mad_w = stats["power_mad"] if math.isfinite(stats["power_mad"]) else 0.0
            threshold_w = max(
                min_power_delta_w,
                relative_power_tolerance * power_median,
                mad_threshold * mad_w,
            )
            if stats["rows"] >= min_group_size and abs_delta_w > threshold_w:
                direction = "low" if power_delta_w < 0.0 else "high"
                reasons.append(f"avg_power_{direction}_outlier")

        endpoint_after_median = stats["endpoint_after_median"]
        endpoint_after_ratio = float("nan")
        if (
            math.isfinite(endpoint_after_w)
            and math.isfinite(endpoint_after_median)
            and endpoint_after_median > 0.0
        ):
            endpoint_after_ratio = endpoint_after_w / endpoint_after_median
            if endpoint_after_ratio < endpoint_after_min_ratio:
                notes.append("endpoint_power_after_low")

        temp_median = stats["temp_median"]
        if math.isfinite(temp) and math.isfinite(temp_median):
            if abs(temp - temp_median) >= temp_delta_c:
                notes.append("temperature_outlier")

        clock_median = stats["clock_median"]
        if (
            math.isfinite(clock)
            and math.isfinite(clock_median)
            and clock_median > 0.0
            and abs(clock - clock_median) / clock_median > clock_delta_pct
        ):
            notes.append("clock_outlier")

        status = "reject" if reasons else ("caution" if notes else "ok")
        out.append(
            {
                "input_file": row.get("_input_file", ""),
                "sweep_source_id": row.get("_sweep_source_id", ""),
                "row_index": row.get("_row_index", ""),
                "run_id": row.get("run_id", ""),
                "gpu_id": row.get("gpu_id", ""),
                "n_gpu_active": row.get("n_gpu_active", ""),
                "gpu_active": "true" if is_active_row(row) else "false",
                "mode": row.get("mode", ""),
                "W_SM_KiB": row.get("W_SM_KiB", ""),
                "blocks_per_SM": row.get("blocks_per_SM", ""),
                "active_SM": row.get("active_SM", ""),
                "reuse_factor": row.get("reuse_factor", ""),
                "load_repeat": row.get("load_repeat", ""),
                "store_repeat": row.get("store_repeat", ""),
                "elapsed_s": row.get("elapsed_s", ""),
                "net_E_J": row.get("net_E_J", ""),
                "average_power_W": row.get("_avg_power_W", ""),
                "group_rows": f"{int(stats['rows'])}",
                "group_power_median_W": f"{stats['power_median']:.12g}",
                "group_power_mad_W": f"{stats['power_mad']:.12g}",
                "average_power_delta_W": (
                    f"{power_delta_w:.12g}" if math.isfinite(power_delta_w) else ""
                ),
                "endpoint_after_W": (
                    f"{endpoint_after_w:.12g}" if math.isfinite(endpoint_after_w) else ""
                ),
                "group_endpoint_after_median_W": (
                    f"{endpoint_after_median:.12g}"
                    if math.isfinite(endpoint_after_median)
                    else ""
                ),
                "endpoint_after_ratio": (
                    f"{endpoint_after_ratio:.12g}"
                    if math.isfinite(endpoint_after_ratio)
                    else ""
                ),
                "temp_C": row.get("temp_C", ""),
                "group_temp_median_C": (
                    f"{temp_median:.12g}" if math.isfinite(temp_median) else ""
                ),
                "clock_sm_mhz": row.get("clock_sm_mhz", ""),
                "group_clock_sm_median_mhz": (
                    f"{clock_median:.12g}" if math.isfinite(clock_median) else ""
                ),
                "status": status,
                "coefficient_eligible": "false" if status == "reject" else "true",
                "reasons": ";".join(reasons),
                "notes": ";".join(notes),
            }
        )
    return out


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "input_file",
        "sweep_source_id",
        "row_index",
        "run_id",
        "gpu_id",
        "n_gpu_active",
        "gpu_active",
        "mode",
        "W_SM_KiB",
        "blocks_per_SM",
        "active_SM",
        "reuse_factor",
        "load_repeat",
        "store_repeat",
        "elapsed_s",
        "net_E_J",
        "average_power_W",
        "group_rows",
        "group_power_median_W",
        "group_power_mad_W",
        "average_power_delta_W",
        "endpoint_after_W",
        "group_endpoint_after_median_W",
        "endpoint_after_ratio",
        "temp_C",
        "group_temp_median_C",
        "clock_sm_mhz",
        "group_clock_sm_median_mhz",
        "status",
        "coefficient_eligible",
        "reasons",
        "notes",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_values(value: str) -> list[str]:
    return [item for item in value.split(";") if item]


def write_markdown(path: str, rows: list[dict[str, str]], csv_path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(row["status"] for row in rows)
    reason_counts: Counter[str] = Counter()
    note_counts: Counter[str] = Counter()
    for row in rows:
        reason_counts.update(split_values(row["reasons"]))
        note_counts.update(split_values(row["notes"]))

    with out.open("w") as f:
        f.write("# Power-State Stability Audit\n\n")
        f.write(
            "This report flags raw energy rows whose average power or endpoint "
            "power metadata is inconsistent with peer rows of the same mode and "
            "configuration. It is a measurement-quality audit, not an NCU path "
            "acceptance report and not a component coefficient report.\n\n"
        )
        f.write(
            "Rows retain `sweep_source_id`, physical `gpu_id`, and `run_id`. "
            "Downstream analysis joins on all three fields so inactive GPUs and "
            "same-coordinate controls from another sweep cannot overwrite or "
            "cross-pair the selected GPU row.\n\n"
        )
        f.write(f"- audit CSV: `{csv_path}`\n\n")

        f.write("## Status Counts\n\n")
        f.write("| status | rows |\n|---|---:|\n")
        for status, count in sorted(status_counts.items()):
            f.write(f"| `{status}` | {count} |\n")
        f.write("\n")

        if reason_counts:
            f.write("## Reject Reasons\n\n")
            f.write("| reason | rows |\n|---|---:|\n")
            for reason, count in sorted(reason_counts.items()):
                f.write(f"| `{reason}` | {count} |\n")
            f.write("\n")

        if note_counts:
            f.write("## Notes\n\n")
            f.write("| note | rows |\n|---|---:|\n")
            for note, count in sorted(note_counts.items()):
                f.write(f"| `{note}` | {count} |\n")
            f.write("\n")

        rejects = [row for row in rows if row["status"] == "reject"]
        if rejects:
            f.write("## Rejected Rows\n\n")
            f.write(
                "| sweep | GPU | active | mode | W_SM (KiB) | B/SM | LR | avg power (W) | group median (W) | "
                "endpoint after ratio | temp (C) | reasons | notes |\n"
            )
            f.write("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|\n")
            for row in rejects:
                f.write(
                    f"| `{row['sweep_source_id']}` | {row['gpu_id']} | "
                    f"{row['gpu_active']} | `{row['mode']}` | {row['W_SM_KiB']} | {row['blocks_per_SM']} | "
                    f"{row['load_repeat']} | {row['average_power_W']} | "
                    f"{row['group_power_median_W']} | {row['endpoint_after_ratio']} | "
                    f"{row['temp_C']} | {row['reasons'] or '-'} | {row['notes'] or '-'} |\n"
                )
            f.write("\n")

        f.write("## Interpretation\n\n")
        f.write(
            "- `reject` rows should not be used as evidence for a stable coefficient "
            "until the run is repeated under stable clocks/power state.\n"
        )
        f.write(
            "- Endpoint power fields are metadata. Final energy numerator still comes "
            "from `nvml_total_energy` when the power API audit passes.\n"
        )
        f.write(
            "- If matched-control rows are negative but this audit has no reject row, "
            "the likely issue is weak treatment-control signal rather than an obvious "
            "power-state anomaly.\n"
        )


def run_self_test() -> None:
    common = {
        "profile_name": "a100",
        "n_gpu_active": "1",
        "mode": "global_addr_only",
        "W_SM_KiB": "16",
        "blocks_per_SM": "16",
        "active_SM": "108",
        "reuse_factor": "1",
        "load_repeat": "4",
        "store_repeat": "1",
        "elapsed_s": "10",
        "net_E_J": "100",
        "power_after_mw": "100000",
        "temp_C": "45",
        "clock_sm_mhz": "1200",
        "run_id": "global_addr_only_100000_r0",
    }
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / "a100_component_finalplan_selftest_l1.csv"
        rows = [
            {**common, "gpu_id": "0", "notes": "gpu_active=1"},
            {**common, "gpu_id": "1", "notes": "gpu_active=0"},
        ]
        with raw.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        audited = audit(
            read_rows([str(raw)]),
            min_group_size=1,
            relative_power_tolerance=0.05,
            min_power_delta_w=10.0,
            mad_threshold=6.0,
            endpoint_after_min_ratio=0.75,
            temp_delta_c=8.0,
            clock_delta_pct=0.05,
        )
    assert len(audited) == 2
    assert {row["gpu_id"] for row in audited} == {"0", "1"}
    assert {row["gpu_active"] for row in audited} == {"true", "false"}
    assert {row["sweep_source_id"] for row in audited} == {raw.name}
    print("power-state audit multi-GPU identity self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_csv", nargs="*")
    parser.add_argument("--out-csv", default="results/summary/power_state_audit.csv")
    parser.add_argument("--out-md", default="results/summary/power_state_audit.md")
    parser.add_argument("--min-group-size", type=int, default=4)
    parser.add_argument("--relative-power-tolerance", type=float, default=0.05)
    parser.add_argument("--min-power-delta-w", type=float, default=10.0)
    parser.add_argument("--mad-threshold", type=float, default=6.0)
    parser.add_argument("--endpoint-after-min-ratio", type=float, default=0.75)
    parser.add_argument("--temp-delta-c", type=float, default=8.0)
    parser.add_argument("--clock-delta-pct", type=float, default=0.05)
    parser.add_argument("--fail-on-reject", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if not args.raw_csv:
        parser.error("at least one raw CSV path is required")

    rows = audit(
        read_rows(args.raw_csv),
        min_group_size=args.min_group_size,
        relative_power_tolerance=args.relative_power_tolerance,
        min_power_delta_w=args.min_power_delta_w,
        mad_threshold=args.mad_threshold,
        endpoint_after_min_ratio=args.endpoint_after_min_ratio,
        temp_delta_c=args.temp_delta_c,
        clock_delta_pct=args.clock_delta_pct,
    )
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args.out_csv)
    counts = Counter(row["status"] for row in rows)
    print(
        "power-state audit "
        + " ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    )
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")
    if args.fail_on_reject and counts.get("reject", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
