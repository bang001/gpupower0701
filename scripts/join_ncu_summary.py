#!/usr/bin/env python3
"""Join NCU cache summary counters into benchmark energy CSV rows.

Nsight Compute sidecar runs often use a fixed ITER that differs from the energy
run. This script matches rows by mode/shape and scales NCU byte counters by the
energy-row ITER divided by the NCU-row ITER. The joined values remain sidecar
estimates and should be used only after the NCU row acceptance checks pass.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


COUNTER_MAP = {
    "shared_bytes": "ncu_shared_bytes",
    "l1_bytes": "ncu_l1_bytes",
    "l2_bytes": "ncu_l2_bytes",
    "dram_bytes": "ncu_dram_bytes",
}
LOAD_SCALED_MAP = {
    "shared_accesses": "ncu_shared_accesses",
    "l1_accesses": "ncu_l1_accesses",
    "l2_accesses": "ncu_l2_accesses",
    "dram_accesses": "ncu_dram_accesses",
    "tensor_hmma_inst": "ncu_tensor_hmma_inst",
}
UNSCALED_MAP = {
    "status": "ncu_status",
    "l1_hit_rate_pct": "ncu_l1_hit_rate_pct",
    "l2_hit_rate_pct": "ncu_l2_hit_rate_pct",
    "stall_long_scoreboard_pct": "ncu_stall_long_scoreboard_pct",
    "stall_short_scoreboard_pct": "ncu_stall_short_scoreboard_pct",
    "stall_wait_pct": "ncu_stall_wait_pct",
    "stall_not_selected_pct": "ncu_stall_not_selected_pct",
    "spill_local_read_inst": "ncu_spill_local_read_inst",
    "spill_local_write_inst": "ncu_spill_local_write_inst",
    "missing_metrics": "ncu_missing_metrics",
    "optional_missing_metrics": "ncu_optional_missing_metrics",
    "validation_notes": "ncu_validation_notes",
}


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def key(row: dict[str, str], *, include_repeats: bool) -> tuple[str, ...]:
    base = (
        row.get("mode", ""),
        row.get("W_SM_KiB", ""),
        row.get("blocks_per_SM", ""),
        row.get("active_SM", ""),
    )
    if not include_repeats:
        return base
    return base + (
        row.get("load_repeat", ""),
        row.get("store_repeat", ""),
    )


def append_note(row: dict[str, str], note: str) -> None:
    existing = row.get("notes", "")
    if existing and not existing.endswith(";"):
        existing += ";"
    row["notes"] = existing + note


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("energy_csv")
    parser.add_argument("ncu_summary_csv", nargs="+")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument(
        "--require-ok",
        action="store_true",
        help="Only join NCU rows whose status is ok.",
    )
    args = parser.parse_args()

    energy_rows = read_rows(Path(args.energy_csv))
    ncu_rows: list[dict[str, str]] = []
    for summary_csv in args.ncu_summary_csv:
        ncu_rows.extend(read_rows(Path(summary_csv)))

    exact: dict[tuple[str, ...], dict[str, str]] = {}
    loose: dict[tuple[str, ...], dict[str, str]] = {}
    for row in ncu_rows:
        if args.require_ok and row.get("status") != "ok":
            continue
        exact[key(row, include_repeats=True)] = row
        loose[key(row, include_repeats=False)] = row

    joined = 0
    for row in energy_rows:
        match_type = "exact"
        match = exact.get(key(row, include_repeats=True))
        if match is None:
            match = loose.get(key(row, include_repeats=False))
            match_type = "loose"
        if match is None:
            append_note(row, "ncu_join_status=missing;")
            continue

        energy_iter = as_float(row, "ITER")
        ncu_iter = as_float(match, "ITER")
        iter_scale = energy_iter / ncu_iter if energy_iter > 0.0 and ncu_iter > 0.0 else 1.0
        energy_load_repeat = as_float(row, "load_repeat", 1.0)
        ncu_load_repeat = as_float(match, "load_repeat", 1.0)
        load_scale = iter_scale
        if energy_load_repeat > 0.0 and ncu_load_repeat > 0.0:
            load_scale *= energy_load_repeat / ncu_load_repeat
        for source, target in COUNTER_MAP.items():
            value = as_float(match, source)
            if value > 0.0:
                row[target] = f"{value * load_scale:.12g}"
        for source, target in LOAD_SCALED_MAP.items():
            value = as_float(match, source)
            if value > 0.0:
                row[target] = f"{value * load_scale:.12g}"
        for source, target in UNSCALED_MAP.items():
            if source in match:
                row[target] = match.get(source, "")
        append_note(
            row,
            "ncu_join_status=joined;"
            f"ncu_match_type={match_type};"
            f"ncu_label={match.get('label', '')};"
            f"ncu_status={match.get('status', '')};"
            f"ncu_iter_scale={iter_scale:.12g};"
            f"ncu_load_scale={load_scale:.12g};",
        )
        joined += 1

    fieldnames = list(energy_rows[0].keys()) if energy_rows else []
    for target in [
        *COUNTER_MAP.values(),
        *LOAD_SCALED_MAP.values(),
        *UNSCALED_MAP.values(),
    ]:
        if target not in fieldnames:
            fieldnames.append(target)

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(energy_rows)

    print(f"energy rows: {len(energy_rows)}")
    print(f"ncu rows: {len(ncu_rows)}")
    print(f"joined rows: {joined}")
    print(f"wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
