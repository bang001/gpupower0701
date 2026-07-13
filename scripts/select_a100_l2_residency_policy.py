#!/usr/bin/env python3
"""Select a validated A100 L2 residency policy before the long energy sweep."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def as_float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def as_int(row: dict[str, str], key: str, default: int = -1) -> int:
    value = as_float(row, key)
    return int(value) if math.isfinite(value) else default


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_policy(
    rows: list[dict[str, str]],
    *,
    policy: str,
    expected_w: tuple[int, ...],
    load_repeat: int,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for w_sm_kib in expected_w:
        treatment_matches = [
            row
            for row in rows
            if row.get("mode") == "l2_cg_load_only"
            and as_int(row, "W_SM_KiB") == w_sm_kib
            and as_int(row, "load_repeat") == load_repeat
        ]
        control_matches = [
            row
            for row in rows
            if row.get("mode") == "global_addr_only"
            and as_int(row, "W_SM_KiB") == w_sm_kib
            and as_int(row, "load_repeat") == load_repeat
        ]
        row = treatment_matches[0] if len(treatment_matches) == 1 else {}
        control = control_matches[0] if len(control_matches) == 1 else {}
        l1_hit = as_float(row, "l1_path_hit_rate_pct")
        l2_hit = as_float(row, "l2_path_hit_rate_pct")
        l2_native_hit = as_float(row, "l2_native_read_hit_rate_pct")
        l2_hit_delta = as_float(row, "l2_native_vs_derived_hit_delta_pct")
        sector_conservation = as_float(
            row, "l2_read_sector_conservation_ratio"
        )
        persisting_size = as_float(
            row, "launch_persisting_l2_cache_size_bytes", 0.0
        )
        l2_bytes = as_float(row, "l2_read_bytes", 0.0)
        dram_bytes = as_float(row, "dram_bytes", math.inf)
        dram_ratio = dram_bytes / l2_bytes if l2_bytes > 0.0 else math.inf
        reasons: list[str] = []
        if len(treatment_matches) != 1:
            reasons.append(f"treatment_row_count_{len(treatment_matches)}")
        if len(control_matches) != 1:
            reasons.append(f"control_row_count_{len(control_matches)}")
        if row.get("acceptance") != "accepted":
            reasons.append("path_not_accepted")
        if control.get("acceptance") != "accepted":
            reasons.append("control_not_accepted")
        if row.get("ncu_replay_mode") != "application":
            reasons.append("not_application_replay")
        if row.get("ncu_cache_control") != "none":
            reasons.append("cache_control_not_none")
        if row.get("l2_residency_policy") != policy:
            reasons.append("residency_policy_mismatch")
        if (
            control.get("ncu_replay_mode") != "application"
            or control.get("ncu_cache_control") != "none"
            or control.get("l2_residency_policy") != policy
        ):
            reasons.append("control_policy_mismatch")
        if not math.isfinite(l1_hit) or l1_hit > 1.0:
            reasons.append("l1_bypass_failed")
        if not math.isfinite(l2_hit) or l2_hit < 95.0:
            reasons.append("l2_hit_below_95pct")
        if not math.isfinite(l2_native_hit) or l2_native_hit < 95.0:
            reasons.append("l2_native_hit_below_95pct")
        if not math.isfinite(l2_hit_delta) or l2_hit_delta > 2.0:
            reasons.append("l2_native_derived_delta_above_2pp")
        if (
            not math.isfinite(sector_conservation)
            or not 0.98 <= sector_conservation <= 1.02
        ):
            reasons.append("l2_read_sector_conservation_failed")
        if policy == "persisting" and persisting_size <= 0.0:
            reasons.append("persisting_window_not_active")
        if not math.isfinite(dram_ratio) or dram_ratio > 0.02:
            reasons.append("dram_to_l2_above_2pct")
        results.append(
            {
                "policy": policy,
                "W_SM_KiB": str(w_sm_kib),
                "load_repeat": str(load_repeat),
                "treatment_row_count": str(len(treatment_matches)),
                "control_row_count": str(len(control_matches)),
                "control_acceptance": control.get("acceptance", ""),
                "l1_path_hit_rate_pct": row.get("l1_path_hit_rate_pct", ""),
                "l2_path_hit_rate_pct": row.get("l2_path_hit_rate_pct", ""),
                "l2_native_read_hit_rate_pct": row.get(
                    "l2_native_read_hit_rate_pct", ""
                ),
                "l2_native_vs_derived_hit_delta_pct": row.get(
                    "l2_native_vs_derived_hit_delta_pct", ""
                ),
                "l2_read_sector_conservation_ratio": row.get(
                    "l2_read_sector_conservation_ratio", ""
                ),
                "launch_persisting_l2_cache_size_bytes": row.get(
                    "launch_persisting_l2_cache_size_bytes", ""
                ),
                "dram_to_l2_bytes": (
                    f"{dram_ratio:.9g}" if math.isfinite(dram_ratio) else ""
                ),
                "status": "pass" if not reasons else "fail",
                "reason": ";".join(reasons) if reasons else "pass",
            }
        )
    return results


def choose_policy(rows: list[dict[str, str]]) -> str:
    by_policy: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_policy.setdefault(row["policy"], []).append(row)
    for policy in ("normal", "persisting"):
        values = by_policy.get(policy, [])
        if values and all(row["status"] == "pass" for row in values):
            return policy
    return ""


def write_report(rows: list[dict[str, str]], selected: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        handle.write("# A100 L2 Residency Policy Selection\n\n")
        handle.write(
            "The normal `.cg` path is preferred when it passes. Persisting residency "
            "is selected only when normal caching fails and the explicit CUDA L2 "
            "access-policy window passes the same path gates.\n\n"
        )
        handle.write(f"Selected policy: `{selected or 'none'}`\n\n")
        handle.write(
            "| policy | W_SM (KiB/SM) | LR | L1 path hit (%) | L2 derived hit (%) | "
            "L2 native hit (%) | delta (pp) | sector conservation | persisting bytes | "
            "DRAM/L2 bytes | control | status | reason |\n"
        )
        handle.write(
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|\n"
        )
        for row in rows:
            handle.write(
                f"| {row['policy']} | {row['W_SM_KiB']} | {row['load_repeat']} | "
                f"{row['l1_path_hit_rate_pct']} | {row['l2_path_hit_rate_pct']} | "
                f"{row['l2_native_read_hit_rate_pct']} | "
                f"{row['l2_native_vs_derived_hit_delta_pct']} | "
                f"{row['l2_read_sector_conservation_ratio']} | "
                f"{row['launch_persisting_l2_cache_size_bytes']} | "
                f"{row['dram_to_l2_bytes']} | {row['control_acceptance']} | "
                f"{row['status']} | {row['reason']} |\n"
            )


def self_test() -> None:
    base = {
        "mode": "l2_cg_load_only",
        "load_repeat": "4",
        "acceptance": "accepted",
        "ncu_replay_mode": "application",
        "ncu_cache_control": "none",
        "l1_path_hit_rate_pct": "0",
        "l2_path_hit_rate_pct": "99",
        "l2_native_read_hit_rate_pct": "99.2",
        "l2_native_vs_derived_hit_delta_pct": "0.2",
        "l2_read_sector_conservation_ratio": "1",
        "launch_persisting_l2_cache_size_bytes": "0",
        "l2_read_bytes": "1e12",
        "dram_bytes": "1e9",
    }
    normal = [
        {**base, "W_SM_KiB": str(w), "l2_residency_policy": "normal"}
        for w in (16, 128)
    ]
    normal += [
        {
            **base,
            "mode": "global_addr_only",
            "W_SM_KiB": str(w),
            "l2_residency_policy": "normal",
        }
        for w in (16, 128)
    ]
    evaluated = evaluate_policy(normal, policy="normal", expected_w=(16, 128), load_repeat=4)
    assert choose_policy(evaluated) == "normal"
    rejected_control = [dict(row) for row in normal]
    next(
        row
        for row in rejected_control
        if row["mode"] == "global_addr_only" and row["W_SM_KiB"] == "16"
    )["acceptance"] = "rejected"
    rejected_eval = evaluate_policy(
        rejected_control, policy="normal", expected_w=(16, 128), load_repeat=4
    )
    assert choose_policy(rejected_eval) == ""
    failed = [{**row, "status": "fail"} for row in evaluated]
    persist = [
        {
            **base,
            "W_SM_KiB": str(w),
            "l2_residency_policy": "persisting",
            "launch_persisting_l2_cache_size_bytes": "34603008",
        }
        for w in (16, 128)
    ]
    persist += [
        {
            **base,
            "mode": "global_addr_only",
            "W_SM_KiB": str(w),
            "l2_residency_policy": "persisting",
            "launch_persisting_l2_cache_size_bytes": "34603008",
        }
        for w in (16, 128)
    ]
    persist_eval = evaluate_policy(
        persist, policy="persisting", expected_w=(16, 128), load_repeat=4
    )
    assert choose_policy(failed + persist_eval) == "persisting"
    print("A100 L2 residency selector self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-acceptance")
    parser.add_argument("--persisting-acceptance")
    parser.add_argument("--expected-w", default="16,128")
    parser.add_argument("--load-repeat", type=int, default=4)
    parser.add_argument("--out-csv", default="results/summary/a100_l2_policy_selection.csv")
    parser.add_argument("--out-md", default="results/summary/a100_l2_policy_selection.md")
    parser.add_argument("--out-env", default="results/summary/a100_l2_policy_selection.env")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.normal_acceptance:
        parser.error("--normal-acceptance is required")

    expected_w = tuple(int(value) for value in args.expected_w.split(",") if value)
    rows = evaluate_policy(
        read_rows(Path(args.normal_acceptance)),
        policy="normal",
        expected_w=expected_w,
        load_repeat=args.load_repeat,
    )
    if args.persisting_acceptance:
        rows += evaluate_policy(
            read_rows(Path(args.persisting_acceptance)),
            policy="persisting",
            expected_w=expected_w,
            load_repeat=args.load_repeat,
        )
    selected = choose_policy(rows)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_report(rows, selected, Path(args.out_md))
    out_env = Path(args.out_env)
    out_env.parent.mkdir(parents=True, exist_ok=True)
    out_env.write_text(f"L2_RESIDENCY_POLICY={selected}\n")
    print(f"selected L2 residency policy: {selected or 'none'}")
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
