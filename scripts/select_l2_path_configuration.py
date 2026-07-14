#!/usr/bin/env python3
"""Select the first fully validated platform L2 topology/policy candidate.

The selector preserves a 95% final-service L2 requirement. GA100 derives that
rate from the source-partition and LTC-fabric lookup populations; other current
profiles use the direct path-specific rate. Every rejected coordinate remains
visible before the energy sweep is allowed to start.
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


def parse_candidate(
    value: str, *, target_profile: str
) -> tuple[str, str, int, Path]:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            "candidate must be POLICY:LAYOUT:BLOCKS_PER_SM:ACCEPTANCE_CSV"
        )
    policy, layout, blocks_text, path_text = parts
    if policy not in {"normal", "persisting"}:
        raise ValueError(f"unsupported L2 policy: {policy}")
    if target_profile == "v100" and policy == "persisting":
        raise ValueError(
            "V100 (compute capability 7.0) does not support CUDA L2 "
            "persisting-access controls; use policy=normal"
        )
    if layout not in {"contiguous", "sm_interleaved"}:
        raise ValueError(f"unsupported L2 layout: {layout}")
    blocks = int(blocks_text)
    if blocks not in {1, 2, 4, 8, 16, 32}:
        raise ValueError("L2 candidate blocks/SM must be 1, 2, 4, 8, 16, or 32")
    return policy, layout, blocks, Path(path_text)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def evaluate_candidate(
    rows: list[dict[str, str]],
    *,
    target_profile: str,
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
            if row.get("ncu_metric_profile") != "l2_path_minimal":
                reasons.append(f"{row_name}_not_l2_path_minimal_profile")
            if row.get("l2_residency_policy") != policy:
                reasons.append(f"{row_name}_policy_mismatch")
            if row.get("l2_address_layout") != layout:
                reasons.append(f"{row_name}_layout_mismatch")
        l1_hit = number(treatment, "l1_path_hit_rate_pct")
        derived_hit = number(treatment, "l2_path_hit_rate_pct")
        native_hit = number(treatment, "l2_native_read_hit_rate_pct")
        native_delta = number(treatment, "l2_native_vs_derived_hit_delta_pct")
        logical_hit = number(treatment, "l2_logical_read_hit_rate_pct")
        fabric_hit = number(treatment, "l2_fabric_hit_rate_pct")
        fabric_metrics_present = number(treatment, "l2_fabric_metrics_present")
        fabric_counter_coherent = number(
            treatment, "l2_fabric_counter_coherent"
        )
        fabric_model_coherent = number(treatment, "l2_fabric_model_coherent")
        native_fabric_delta = number(
            treatment, "l2_native_vs_fabric_model_hit_delta_pct"
        )
        conservation = number(treatment, "l2_read_sector_conservation_ratio")
        traffic_ratio = number(treatment, "l2_read_bytes_to_expected")
        persisting_size = number(
            treatment, "launch_persisting_l2_cache_size_bytes", 0.0
        )
        if not math.isfinite(l1_hit) or l1_hit > 1.0:
            reasons.append("l1_bypass_failed")
        if not math.isfinite(derived_hit):
            reasons.append("missing_derived_l2_hit")
        if target_profile == "a100":
            native_gate = "ga100_fabric_model"
            if not math.isfinite(logical_hit) or logical_hit < 95.0:
                reasons.append("logical_l2_hit_below_95pct")
            elif logical_hit > 100.5:
                reasons.append("logical_l2_hit_above_100_5pct")
            if fabric_metrics_present != 1.0:
                reasons.append("missing_required_l2_fabric_metrics")
            if fabric_counter_coherent != 1.0:
                reasons.append("l2_fabric_counters_incoherent")
            if fabric_model_coherent != 1.0:
                reasons.append("l2_fabric_model_incoherent")
            if not math.isfinite(native_hit):
                reasons.append("missing_required_native_l2_hit")
            if not math.isfinite(native_fabric_delta):
                reasons.append("missing_native_fabric_model_delta")
            elif native_fabric_delta > 2.0:
                reasons.append("native_fabric_model_delta_above_2pp")
        else:
            if math.isfinite(derived_hit) and derived_hit < 95.0:
                reasons.append("derived_l2_hit_below_95pct")
            native_required = target_profile != "v100"
            native_gate = "required" if native_required else "optional_unavailable"
            if native_required:
                if not math.isfinite(native_hit):
                    reasons.append("missing_required_native_l2_hit")
                elif native_hit < 95.0:
                    reasons.append("native_l2_hit_below_95pct")
                if not math.isfinite(native_delta):
                    reasons.append("missing_required_native_derived_delta")
                elif native_delta > 2.0:
                    reasons.append("native_derived_delta_above_2pp")
            elif math.isfinite(native_hit):
                native_gate = "optional_present_cross_checked"
                if native_hit < 95.0:
                    reasons.append("optional_native_l2_hit_below_95pct")
                if not math.isfinite(native_delta):
                    reasons.append("missing_optional_native_derived_delta")
                elif native_delta > 2.0:
                    reasons.append("optional_native_derived_delta_above_2pp")
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
                "ncu_metric_profile": treatment.get("ncu_metric_profile", ""),
                "l1_path_hit_rate_pct": treatment.get("l1_path_hit_rate_pct", ""),
                "l2_path_hit_rate_pct": treatment.get("l2_path_hit_rate_pct", ""),
                "l2_tex_path_hit_rate_pct": treatment.get(
                    "l2_tex_path_hit_rate_pct", ""
                ),
                "l2_device_path_hit_rate_pct": treatment.get(
                    "l2_device_path_hit_rate_pct", ""
                ),
                "l2_native_read_hit_rate_pct": treatment.get(
                    "l2_native_read_hit_rate_pct", ""
                ),
                "l2_native_vs_derived_hit_delta_pct": treatment.get(
                    "l2_native_vs_derived_hit_delta_pct", ""
                ),
                "l2_logical_read_hit_rate_pct": treatment.get(
                    "l2_logical_read_hit_rate_pct", ""
                ),
                "l2_fabric_hit_rate_pct": treatment.get(
                    "l2_fabric_hit_rate_pct", ""
                ),
                "l2_fabric_read_fraction": treatment.get(
                    "l2_fabric_read_fraction", ""
                ),
                "l2_fabric_read_to_source_miss_ratio": treatment.get(
                    "l2_fabric_read_to_source_miss_ratio", ""
                ),
                "l2_fabric_counter_coherent": treatment.get(
                    "l2_fabric_counter_coherent", ""
                ),
                "l2_fabric_model_coherent": treatment.get(
                    "l2_fabric_model_coherent", ""
                ),
                "l2_native_vs_fabric_model_hit_delta_pct": treatment.get(
                    "l2_native_vs_fabric_model_hit_delta_pct", ""
                ),
                "native_l2_gate": native_gate,
                "l2_read_sector_conservation_ratio": treatment.get(
                    "l2_read_sector_conservation_ratio", ""
                ),
                "l2_read_bytes_to_expected": treatment.get(
                    "l2_read_bytes_to_expected", ""
                ),
                "dram_read_to_l2_read_ratio": (
                    f"{dram_ratio:.9g}" if math.isfinite(dram_ratio) else ""
                ),
                "dram_read_to_l2_miss_bytes_ratio": treatment.get(
                    "dram_read_to_l2_miss_bytes_ratio", ""
                ),
                "l2_evict_first_read_pct": treatment.get(
                    "l2_evict_first_read_pct", ""
                ),
                "l2_evict_normal_read_pct": treatment.get(
                    "l2_evict_normal_read_pct", ""
                ),
                "l2_evict_last_read_pct": treatment.get(
                    "l2_evict_last_read_pct", ""
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


def write_markdown(
    rows: list[dict[str, str]],
    selected: dict[str, str],
    path: Path,
    *,
    target_profile: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write(f"# {target_profile.upper()} L2 Path Configuration Selection\n\n")
        out.write(
            "Candidates are evaluated in command-line order using the minimal, "
            "counter-coherent L2 metric profile. The 95% requirement applies to "
            "final L2 service. On GA100 this combines direct-partition and explicit "
            "LTC-fabric hits; native and first-lookup rates are not substituted for "
            "that model.\n\n"
        )
        if selected:
            out.write(
                f"Selected: policy=`{selected['policy']}`, layout=`{selected['layout']}`, "
                f"blocks/SM=`{selected['blocks_per_SM']}`.\n\n"
            )
        else:
            out.write("Selected: `none`; L2 energy measurement must not run.\n\n")
        out.write(
            "| policy | layout | blocks/SM | W_SM (KiB/SM) | LR | metric profile | L1 hit (%) | "
            "L2 device/TEX/native/logical hit (%) | fabric hit/fraction (%) | native gate | "
            "native-direct/native-model delta (pp) | source/fabric/model coherent | traffic/expected | "
            "DRAM-read/L2-read | DRAM-read/L2-miss | eviction F/N/L (%) | "
            "persisting bytes | selected | status | reason |\n"
        )
        out.write(
            "|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|---|\n"
        )
        for row in rows:
            out.write(
                f"| {row['policy']} | {row['layout']} | {row['blocks_per_SM']} | "
                f"{row['W_SM_KiB']} | {row['load_repeat']} | "
                f"{row['ncu_metric_profile']} | "
                f"{row['l1_path_hit_rate_pct']} | "
                f"{row['l2_device_path_hit_rate_pct']}/"
                f"{row['l2_tex_path_hit_rate_pct']}/"
                f"{row['l2_native_read_hit_rate_pct']}/"
                f"{row['l2_logical_read_hit_rate_pct']} | "
                f"{row['l2_fabric_hit_rate_pct']}/"
                f"{row['l2_fabric_read_fraction']} | "
                f"{row['native_l2_gate']} | "
                f"{row['l2_native_vs_derived_hit_delta_pct']}/"
                f"{row['l2_native_vs_fabric_model_hit_delta_pct']} | "
                f"{row['l2_read_sector_conservation_ratio']}/"
                f"{row['l2_fabric_counter_coherent']}/"
                f"{row['l2_fabric_model_coherent']} | "
                f"{row['l2_read_bytes_to_expected']} | "
                f"{row['dram_read_to_l2_read_ratio']} | "
                f"{row['dram_read_to_l2_miss_bytes_ratio']} | "
                f"{row['l2_evict_first_read_pct']}/"
                f"{row['l2_evict_normal_read_pct']}/"
                f"{row['l2_evict_last_read_pct']} | "
                f"{row['launch_persisting_l2_cache_size_bytes']} | "
                f"{row['selected_candidate']} | {row['status']} | "
                f"{row['reason']} |\n"
            )


def self_test() -> None:
    base = {
        "acceptance": "accepted",
        "ncu_replay_mode": "application",
        "ncu_cache_control": "none",
        "ncu_metric_profile": "l2_path_minimal",
        "l2_residency_policy": "normal",
        "l2_address_layout": "sm_interleaved",
        "blocks_per_SM": "8",
        "load_repeat": "4",
        "l1_path_hit_rate_pct": "0",
        "l2_path_hit_rate_pct": "55",
        "l2_native_read_hit_rate_pct": "68.6207",
        "l2_native_vs_derived_hit_delta_pct": "13.6207",
        "l2_logical_read_hit_rate_pct": "99.5",
        "l2_fabric_hit_rate_pct": "98.8889",
        "l2_fabric_read_fraction": "0.310345",
        "l2_fabric_read_to_source_miss_ratio": "1",
        "l2_fabric_metrics_present": "1",
        "l2_fabric_counter_coherent": "1",
        "l2_fabric_model_coherent": "1",
        "l2_native_vs_fabric_model_hit_delta_pct": "0",
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
        target_profile="a100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert choose([evaluated])["blocks_per_SM"] == "8"
    failed_rows = [dict(row) for row in rows]
    next(row for row in failed_rows if row["mode"] == "l2_cg_load_only")[
        "l2_logical_read_hit_rate_pct"
    ] = "60"
    failed = evaluate_candidate(
        failed_rows,
        target_profile="a100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert not choose([failed])
    over_recovered_rows = [dict(row) for row in rows]
    next(
        row for row in over_recovered_rows if row["mode"] == "l2_cg_load_only"
    )["l2_logical_read_hit_rate_pct"] = "101"
    over_recovered = evaluate_candidate(
        over_recovered_rows,
        target_profile="a100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert not choose([over_recovered])
    full_profile_rows = [
        {**row, "ncu_metric_profile": "full"} for row in rows
    ]
    full_profile_evaluated = evaluate_candidate(
        full_profile_rows,
        target_profile="a100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert not choose([full_profile_evaluated])
    assert "not_l2_path_minimal_profile" in full_profile_evaluated[0]["reason"]
    v100_rows = [
        {
            **row,
            "W_SM_KiB": "32" if row["W_SM_KiB"] == "16" else "64",
            "l2_path_hit_rate_pct": "99.5",
            "l2_native_read_hit_rate_pct": "",
            "l2_native_vs_derived_hit_delta_pct": "",
        }
        for row in rows
    ]
    v100_evaluated = evaluate_candidate(
        v100_rows,
        target_profile="v100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(32, 64),
        load_repeat=4,
    )
    assert choose([v100_evaluated])["native_l2_gate"] == "optional_unavailable"
    v100_bad_native = evaluate_candidate(
        [
            {
                **row,
                "l2_native_read_hit_rate_pct": "80",
                "l2_native_vs_derived_hit_delta_pct": "19.5",
            }
            for row in v100_rows
        ],
        target_profile="v100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(32, 64),
        load_repeat=4,
    )
    assert not choose([v100_bad_native])
    a100_without_native = evaluate_candidate(
        [
            {
                **row,
                "l2_native_read_hit_rate_pct": "",
                "l2_native_vs_derived_hit_delta_pct": "",
            }
            for row in rows
        ],
        target_profile="a100",
        policy="normal",
        layout="sm_interleaved",
        blocks_per_sm=8,
        expected_w=(16, 128),
        load_repeat=4,
    )
    assert not choose([a100_without_native])
    try:
        parse_candidate(
            "persisting:contiguous:16:unused.csv", target_profile="v100"
        )
    except ValueError as exc:
        assert "does not support" in str(exc)
    else:
        raise AssertionError("V100 persisting L2 candidate was not rejected")
    print("platform L2 path configuration selector self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-profile",
        choices=("rtx3090", "v100", "a100", "h100"),
        default="a100",
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="POLICY:LAYOUT:BLOCKS_PER_SM:ACCEPTANCE_CSV; repeat in preference order",
    )
    parser.add_argument("--expected-w", default="16,128")
    parser.add_argument("--load-repeat", type=int, default=4)
    parser.add_argument("--out-csv", default="results/summary/l2_path_selection.csv")
    parser.add_argument("--out-md", default="results/summary/l2_path_selection.md")
    parser.add_argument("--out-env", default="results/summary/l2_path_selection.env")
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
        policy, layout, blocks, path = parse_candidate(
            value, target_profile=args.target_profile
        )
        evaluated = evaluate_candidate(
            read_rows(path),
            target_profile=args.target_profile,
            policy=policy,
            layout=layout,
            blocks_per_sm=blocks,
            expected_w=expected_w,
            load_repeat=args.load_repeat,
        )
        candidate_rows.append(evaluated)
        flat_rows.extend(evaluated)
    selected = choose(candidate_rows)
    selected_key = (
        selected.get("policy", ""),
        selected.get("layout", ""),
        selected.get("blocks_per_SM", ""),
    )
    for row in flat_rows:
        row_key = (row["policy"], row["layout"], row["blocks_per_SM"])
        row["selected_candidate"] = "yes" if selected and row_key == selected_key else "no"
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat_rows)
    write_markdown(
        flat_rows,
        selected,
        Path(args.out_md),
        target_profile=args.target_profile,
    )
    env_path = Path(args.out_env)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "\n".join(
            [
                f"L2_RESIDENCY_POLICY={selected.get('policy', '')}",
                f"L2_ADDRESS_LAYOUT={selected.get('layout', '')}",
                f"L2_BLOCKS_PER_SM={selected.get('blocks_per_SM', '')}",
                f"L2_PATH_SELECTION_STATUS={'selected' if selected else 'none'}",
                f"L2_PATH_SELECTION_PROFILE={args.target_profile}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        f"selected {args.target_profile.upper()} L2 path: "
        + (
            f"{selected['policy']}/{selected['layout']}/B{selected['blocks_per_SM']}"
            if selected
            else "none"
        )
    )
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
