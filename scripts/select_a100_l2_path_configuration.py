#!/usr/bin/env python3
"""Select the first fully validated A100 L2 topology/policy candidate.

The selector never lowers the 95% L2 hit-rate requirement. It searches an
explicitly ordered candidate list and records why every rejected candidate
failed before the energy sweep is allowed to start.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def number(row: dict[str, str], name: str, default: float = math.nan) -> float:
    try:
        value = float(row.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def integer(row: dict[str, str], name: str, default: int = -1) -> int:
    value = number(row, name)
    return int(value) if math.isfinite(value) else default


def parse_candidate(value: str) -> tuple[str, str, int, Path]:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            "candidate must be POLICY:LAYOUT:BLOCKS_PER_SM:ACCEPTANCE_CSV"
        )
    policy, layout, blocks_text, path_text = parts
    if policy not in {"normal", "persisting"}:
        raise ValueError(f"unsupported L2 policy: {policy}")
    if layout not in {"contiguous", "sm_interleaved"}:
        raise ValueError(f"unsupported L2 layout: {layout}")
    blocks = int(blocks_text)
    if blocks not in {4, 8, 16, 32}:
        raise ValueError("A100 L2 candidate blocks/SM must be 4, 8, 16, or 32")
    return policy, layout, blocks, Path(path_text)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def evaluate_candidate(
    rows: list[dict[str, str]],
    *,
    policy: str,
    layout: str,
    blocks_per_sm: int,
    expected_w: tuple[int, ...],
    load_repeat: int,
) -> list[dict[str, str]]:
    evaluated: list[dict[str, str]] = []
    for w_sm_kib in expected_w:
        matches = [
            row
            for row in rows
            if row.get("mode") == "l2_cg_load_only"
            and integer(row, "W_SM_KiB") == w_sm_kib
            and integer(row, "blocks_per_SM") == blocks_per_sm
            and integer(row, "load_repeat") == load_repeat
        ]
        controls = [
            row
            for row in rows
            if row.get("mode") == "global_addr_only"
            and integer(row, "W_SM_KiB") == w_sm_kib
            and integer(row, "blocks_per_SM") == blocks_per_sm
            and integer(row, "load_repeat") == load_repeat
        ]
        treatment = matches[0] if len(matches) == 1 else {}
        control = controls[0] if len(controls) == 1 else {}
        l2_read = number(treatment, "l2_read_bytes", 0.0)
        dram_read = number(treatment, "dram_read_bytes", math.inf)
        dram_ratio = dram_read / l2_read if l2_read > 0.0 else math.inf
        reasons: list[str] = []
        if len(matches) != 1:
            reasons.append(f"treatment_row_count_{len(matches)}")
        if len(controls) != 1:
            reasons.append(f"control_row_count_{len(controls)}")
        if treatment.get("acceptance") != "accepted":
            reasons.append("treatment_not_accepted")
        if control.get("acceptance") != "accepted":
            reasons.append("control_not_accepted")
        for row_name, row in (("treatment", treatment), ("control", control)):
            if row.get("ncu_replay_mode") != "application":
                reasons.append(f"{row_name}_not_application_replay")
            if row.get("ncu_cache_control") != "none":
                reasons.append(f"{row_name}_cache_control_not_none")
            if row.get("l2_residency_policy") != policy:
                reasons.append(f"{row_name}_policy_mismatch")
            if row.get("l2_address_layout") != layout:
                reasons.append(f"{row_name}_layout_mismatch")
        l1_hit = number(treatment, "l1_path_hit_rate_pct")
        derived_hit = number(treatment, "l2_path_hit_rate_pct")
        native_hit = number(treatment, "l2_native_read_hit_rate_pct")
        native_delta = number(treatment, "l2_native_vs_derived_hit_delta_pct")
        conservation = number(treatment, "l2_read_sector_conservation_ratio")
        traffic_ratio = number(treatment, "l2_read_bytes_to_expected")
        persisting_size = number(
            treatment, "launch_persisting_l2_cache_size_bytes", 0.0
        )
        if not math.isfinite(l1_hit) or l1_hit > 1.0:
            reasons.append("l1_bypass_failed")
        if not math.isfinite(derived_hit) or derived_hit < 95.0:
            reasons.append("derived_l2_hit_below_95pct")
        if not math.isfinite(native_hit) or native_hit < 95.0:
            reasons.append("native_l2_hit_below_95pct")
        if not math.isfinite(native_delta) or native_delta > 2.0:
            reasons.append("native_derived_delta_above_2pp")
        if not math.isfinite(conservation) or not 0.98 <= conservation <= 1.02:
            reasons.append("l2_sector_conservation_failed")
        if not math.isfinite(traffic_ratio) or not 0.95 <= traffic_ratio <= 1.05:
            reasons.append("l2_traffic_expected_mismatch")
        if not math.isfinite(dram_ratio) or dram_ratio > 0.02:
            reasons.append("dram_read_to_l2_above_2pct")
        if policy == "persisting" and persisting_size <= 0.0:
            reasons.append("persisting_set_aside_not_observed")
        evaluated.append(
            {
                "policy": policy,
                "layout": layout,
                "blocks_per_SM": str(blocks_per_sm),
                "W_SM_KiB": str(w_sm_kib),
                "load_repeat": str(load_repeat),
                "l1_path_hit_rate_pct": treatment.get("l1_path_hit_rate_pct", ""),
                "l2_path_hit_rate_pct": treatment.get("l2_path_hit_rate_pct", ""),
                "l2_native_read_hit_rate_pct": treatment.get(
                    "l2_native_read_hit_rate_pct", ""
                ),
                "l2_native_vs_derived_hit_delta_pct": treatment.get(
                    "l2_native_vs_derived_hit_delta_pct", ""
                ),
                "l2_read_sector_conservation_ratio": treatment.get(
                    "l2_read_sector_conservation_ratio", ""
                ),
                "l2_read_bytes_to_expected": treatment.get(
                    "l2_read_bytes_to_expected", ""
                ),
                "dram_read_to_l2_read_ratio": (
                    f"{dram_ratio:.9g}" if math.isfinite(dram_ratio) else ""
                ),
                "launch_persisting_l2_cache_size_bytes": treatment.get(
                    "launch_persisting_l2_cache_size_bytes", ""
                ),
                "status": "pass" if not reasons else "fail",
                "reason": ";".join(reasons) if reasons else "pass",
            }
        )
    return evaluated


def choose(rows_by_candidate: list[list[dict[str, str]]]) -> dict[str, str]:
    for rows in rows_by_candidate:
        if rows and all(row["status"] == "pass" for row in rows):
            return rows[0]
    return {}


def write_markdown(rows: list[dict[str, str]], selected: dict[str, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write("# A100 L2 Path Configuration Selection\n\n")
        out.write(
            "Candidates are evaluated in command-line order. The selector does not "
            "relax the 95% L2 hit gate; it changes blocks/SM, address topology, and "
            "then residency policy to isolate the source of the prior 59-60% result.\n\n"
        )
        if selected:
            out.write(
                f"Selected: policy=`{selected['policy']}`, layout=`{selected['layout']}`, "
                f"blocks/SM=`{selected['blocks_per_SM']}`.\n\n"
            )
        else:
            out.write("Selected: `none`; L2 energy measurement must not run.\n\n")
        out.write(
            "| policy | layout | blocks/SM | W_SM (KiB/SM) | LR | L1 hit (%) | "
            "L2 derived/native hit (%) | delta (pp) | conservation | traffic/expected | "
            "DRAM-read/L2-read | persisting bytes | status | reason |\n"
        )
        out.write(
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|\n"
        )
        for row in rows:
            out.write(
                f"| {row['policy']} | {row['layout']} | {row['blocks_per_SM']} | "
                f"{row['W_SM_KiB']} | {row['load_repeat']} | "
                f"{row['l1_path_hit_rate_pct']} | {row['l2_path_hit_rate_pct']}/"
                f"{row['l2_native_read_hit_rate_pct']} | "
                f"{row['l2_native_vs_derived_hit_delta_pct']} | "
                f"{row['l2_read_sector_conservation_ratio']} | "
                f"{row['l2_read_bytes_to_expected']} | "
                f"{row['dram_read_to_l2_read_ratio']} | "
                f"{row['launch_persisting_l2_cache_size_bytes']} | "
                f"{row['status']} | {row['reason']} |\n"
            )


def self_test() -> None:
    base = {
        "acceptance": "accepted",
        "ncu_replay_mode": "application",
        "ncu_cache_control": "none",
        "l2_residency_policy": "normal",
        "l2_address_layout": "sm_interleaved",
        "blocks_per_SM": "8",
        "load_repeat": "4",
        "l1_path_hit_rate_pct": "0",
        "l2_path_hit_rate_pct": "99.5",
        "l2_native_read_hit_rate_pct": "99.4",
        "l2_native_vs_derived_hit_delta_pct": "0.1",
        "l2_read_sector_conservation_ratio": "1",
        "l2_read_bytes_to_expected": "1.001",
        "l2_read_bytes": "1e12",
        "dram_read_bytes": "1e9",
        "launch_persisting_l2_cache_size_bytes": "0",
    }
    rows = []
    for w in (16, 128):
        rows.append({**base, "mode": "l2_cg_load_only", "W_SM_KiB": str(w)})
        rows.append({**base, "mode": "global_addr_only", "W_SM_KiB": str(w)})
    evaluated = evaluate_candidate(
        rows,
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert choose([evaluated])["blocks_per_SM"] == "8"
    failed_rows = [dict(row) for row in rows]
    next(row for row in failed_rows if row["mode"] == "l2_cg_load_only")[
        "l2_path_hit_rate_pct"
    ] = "60"
    failed = evaluate_candidate(
        failed_rows,
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert not choose([failed])
    print("A100 L2 path configuration selector self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="POLICY:LAYOUT:BLOCKS_PER_SM:ACCEPTANCE_CSV; repeat in preference order",
    )
    parser.add_argument("--expected-w", default="16,128")
    parser.add_argument("--load-repeat", type=int, default=4)
    parser.add_argument("--out-csv", default="results/summary/a100_l2_path_selection.csv")
    parser.add_argument("--out-md", default="results/summary/a100_l2_path_selection.md")
    parser.add_argument("--out-env", default="results/summary/a100_l2_path_selection.env")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.candidate:
        parser.error("at least one --candidate is required")
    expected_w = tuple(int(value) for value in args.expected_w.split(",") if value)
    candidate_rows: list[list[dict[str, str]]] = []
    flat_rows: list[dict[str, str]] = []
    for value in args.candidate:
        policy, layout, blocks, path = parse_candidate(value)
        evaluated = evaluate_candidate(
            read_rows(path),
            policy=policy,
            layout=layout,
            blocks_per_sm=blocks,
            expected_w=expected_w,
            load_repeat=args.load_repeat,
        )
        candidate_rows.append(evaluated)
        flat_rows.extend(evaluated)
    selected = choose(candidate_rows)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat_rows)
    write_markdown(flat_rows, selected, Path(args.out_md))
    env_path = Path(args.out_env)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "\n".join(
            [
                f"L2_RESIDENCY_POLICY={selected.get('policy', '')}",
                f"L2_ADDRESS_LAYOUT={selected.get('layout', '')}",
                f"L2_BLOCKS_PER_SM={selected.get('blocks_per_SM', '')}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        "selected A100 L2 path: "
        + (
            f"{selected['policy']}/{selected['layout']}/B{selected['blocks_per_SM']}"
            if selected
            else "none"
        )
    )
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
