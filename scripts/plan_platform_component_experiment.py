#!/usr/bin/env python3
"""Write a platform-specific component-energy experiment command plan.

The generated commands follow the acceptance-first flow:

1. Run architecture/GPU preflight.
2. Run duration-calibrated energy sweeps without NCU attached.
3. Run a separate NCU sidecar validation.
4. Classify NCU path acceptance.
5. Analyze matched-control energy with NCU byte-denominator scaling.

The script does not execute experiments. It writes a shell script and a short
markdown plan so platform runs can be reviewed before submission to a node.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shlex
from pathlib import Path
from typing import Any


PROFILES: dict[str, dict[str, Any]] = {
    "v100": {
        "cuda_arch": "70",
        "active_sm": 80,
        "blocks": "16,32",
        "shared_w": "32,64",
        "l1_w": "8,16",
        "l2_w": "64",
        "l2_modes": "clocked_empty,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "gv100",
        "tensor_threshold": "2e8",
        "register_threshold": "2e8",
        "note": "Volta path. Use an NCU version that still supports gv100.",
    },
    "a100": {
        "cuda_arch": "80",
        "active_sm": 108,
        "blocks": "16,32",
        "shared_w": "64,128",
        "l1_w": "16,32",
        "l2_w": "256",
        "l2_modes": "clocked_empty,l2_load_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "ga100",
        "tensor_threshold": "3e8",
        "register_threshold": "3e8",
        "note": "A100 can test capacity L2 and CG L2 side by side.",
    },
    "h100": {
        "cuda_arch": "90",
        "active_sm": 132,
        "blocks": "16,32",
        "shared_w": "64,128",
        "l1_w": "16,32",
        "l2_w": "256",
        "l2_modes": "clocked_empty,l2_load_only,l2_cg_load_only",
        "dram_w": "8192",
        "ncu_chip": "gh100",
        "tensor_threshold": "4e8",
        "register_threshold": "4e8",
        "note": "Current kernel uses WMMA compatibility path, not Hopper WGMMA/TMA.",
    },
}


def q(value: str | Path) -> str:
    return shlex.quote(str(value))


def line(parts: list[str]) -> str:
    return " ".join(parts)


def run_component_command(
    *,
    binary: str,
    profile: str,
    gpu_ids: str,
    active_sm: int,
    seconds: float,
    repeats: int,
    modes: str,
    w_values: str,
    blocks: str,
    reuse_factors: str,
    load_repeats: str,
    output: str,
    matrix: str,
) -> str:
    return line(
        [
            "python3",
            "scripts/run_component_regression_sweep.py",
            "--execute",
            "--binary",
            q(binary),
            "--target-profile",
            q(profile),
            "--gpu-ids",
            q(gpu_ids),
            "--max-active-gpus",
            "1",
            "--modes",
            q(modes),
            "--w-sm-kib-values",
            q(w_values),
            "--blocks-per-sm-values",
            q(blocks),
            "--active-sm-values",
            q(str(active_sm)),
            "--reuse-factors",
            q(reuse_factors),
            "--load-repeats",
            q(load_repeats),
            "--store-repeats",
            "1",
            "--seconds",
            q(str(seconds)),
            "--repeats",
            q(str(repeats)),
            "--output",
            q(output),
            "--matrix-csv",
            q(matrix),
        ]
    )


def write_shell(args: argparse.Namespace, profile: dict[str, Any], path: Path) -> None:
    tag = args.tag
    active_sm = args.active_sm or profile["active_sm"]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    binary = args.binary
    ncu = args.ncu

    raw_prefix = f"results/raw/{args.target_profile}_component_finalplan_{tag}"
    summary_prefix = f"results/summary/{args.target_profile}_component_finalplan_{tag}"
    ncu_dir = f"results/ncu/{args.target_profile}_component_finalplan_ncu_lr4_{tag}"
    ncu_raw = f"results/raw/{args.target_profile}_component_finalplan_ncu_lr4_{tag}.csv"
    ncu_summary = f"{ncu_dir}/ncu_cache_validation_summary.csv"
    acceptance_csv = f"{summary_prefix}_ncu_acceptance.csv"
    acceptance_md = f"{summary_prefix}_ncu_acceptance.md"
    matched_summary = f"{summary_prefix}_matched_control_summary.csv"
    matched_detail = f"{summary_prefix}_matched_control_detail.csv"
    matched_md = f"{summary_prefix}_matched_control_report.md"

    energy_csvs = [
        f"{raw_prefix}_tensor.csv",
        f"{raw_prefix}_shared.csv",
        f"{raw_prefix}_l1.csv",
        f"{raw_prefix}_l2.csv",
        f"{raw_prefix}_dram.csv",
    ]

    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# Generated for {args.target_profile} on {dt.date.today().isoformat()}.",
        f"# {profile['note']}",
        "mkdir -p results/raw results/summary results/ncu",
        "",
        "# 1. Preflight",
        line(
            [
                "python3",
                "scripts/preflight_gpu_support.py",
                "--gpu",
                q(args.gpu_ids.split(",")[0]),
                "--target-profile",
                "auto",
                "--binary",
                q(binary),
                "--ncu",
                q(ncu),
                "--out",
                q(f"{summary_prefix}_preflight.md"),
            ]
        ),
        "",
        "# 2. Energy sweeps. Keep NCU detached from these runs.",
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="reg_operand_only,reg_mma",
            w_values="2048",
            blocks=blocks,
            reuse_factors="1,2,4,8,16",
            load_repeats="1",
            output=energy_csvs[0],
            matrix=f"{raw_prefix}_tensor_matrix.csv",
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="clocked_empty,shared_scalar_load_only",
            w_values=profile["shared_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats="1,2,4,8,16",
            output=energy_csvs[1],
            matrix=f"{raw_prefix}_shared_matrix.csv",
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="clocked_empty,global_l1_load_only",
            w_values=profile["l1_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats="1,2,4,8,16",
            output=energy_csvs[2],
            matrix=f"{raw_prefix}_l1_matrix.csv",
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes=profile["l2_modes"],
            w_values=profile["l2_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats="1,2,4,8,16",
            output=energy_csvs[3],
            matrix=f"{raw_prefix}_l2_matrix.csv",
        ),
        run_component_command(
            binary=binary,
            profile=args.target_profile,
            gpu_ids=args.gpu_ids,
            active_sm=active_sm,
            seconds=args.seconds,
            repeats=args.repeats,
            modes="clocked_empty,dram_cg_load_only",
            w_values=profile["dram_w"],
            blocks=blocks,
            reuse_factors="1",
            load_repeats="1,4,16",
            output=energy_csvs[4],
            matrix=f"{raw_prefix}_dram_matrix.csv",
        ),
        "",
        "# 3. NCU sidecar validation. These profiler runs are not energy rows.",
        line(
            [
                f"NCU_EXPLICIT_METRICS_ONLY=1",
                f"NCU={q(ncu)}",
                f"BIN={q(binary)}",
                f"OUTDIR={q(ncu_dir)}",
                f"RAW_OUT={q(ncu_raw)}",
                f"TARGET_PROFILE={q(args.target_profile)}",
                f"GPU={q(args.gpu_ids.split(',')[0])}",
                f"ACTIVE_SM={active_sm}",
                f"BLOCKS_PER_SM={blocks.split(',')[0]}",
                f"REG_BLOCKS_PER_SM={blocks.split(',')[0]}",
                "REG_PRESSURE_PAYLOAD_BYTES=256",
                "REG_W_SM_KIB=2048",
                f"L1_W_SM_KIB={profile['l1_w'].split(',')[0]}",
                f"SHARED_W_SM_KIB={profile['shared_w'].split(',')[-1]}",
                f"L2_W_SM_KIB={profile['l2_w'].split(',')[0]}",
                f"DRAM_W_SM_KIB_OVERRIDE={profile['dram_w']}",
                "REUSE_FACTOR=4",
                "LOAD_REPEAT=4",
                "bash",
                "scripts/run_ncu_validation.sh",
            ]
        ),
        "",
        "# 4. Path acceptance.",
        line(
            [
                "python3",
                "scripts/analyze_ncu_path_acceptance.py",
                q(ncu_summary),
                "--out-csv",
                q(acceptance_csv),
                "--out-md",
                q(acceptance_md),
                "--tensor-memory-bytes-max",
                profile["tensor_threshold"],
                "--register-memory-bytes-max",
                profile["register_threshold"],
            ]
        ),
        "",
        "# 5. Matched-control analysis with NCU byte-denominator scaling.",
        line(
            [
                "python3",
                "scripts/analyze_matched_control_energy.py",
                *(q(path) for path in energy_csvs),
                "--acceptance-csv",
                q(acceptance_csv),
                "--ncu-summary-csv",
                q(ncu_summary),
                "--require-ncu-denominator",
                "--min-elapsed-s",
                q(str(max(1.0, args.seconds * 0.8))),
                "--max-elapsed-ratio",
                "1.35",
                "--out-summary-csv",
                q(matched_summary),
                "--out-detail-csv",
                q(matched_detail),
                "--out-md",
                q(matched_md),
            ]
        ),
        "",
        "echo 'Done. Review:'",
        f"echo '  {matched_md}'",
        f"echo '  {acceptance_md}'",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(commands) + "\n")
    path.chmod(0o755)


def write_markdown(args: argparse.Namespace, profile: dict[str, Any], path: Path) -> None:
    active_sm = args.active_sm or profile["active_sm"]
    blocks = args.blocks_per_sm_values or profile["blocks"]
    out_sh = args.out_sh
    text = f"""# {args.target_profile.upper()} Component Finalplan Command Plan

Generated: {dt.date.today().isoformat()}

| item | value |
|---|---|
| target profile | `{args.target_profile}` |
| CUDA arch | `sm_{profile['cuda_arch']}` |
| active_SM (SMs) | `{active_sm}` |
| blocks/SM | `{blocks}` |
| seconds (s) | `{args.seconds}` |
| repeats | `{args.repeats}` |
| binary | `{args.binary}` |
| NCU | `{args.ncu}` |
| generated shell | `{out_sh}` |

## Platform Note

{profile['note']}

## Component Coordinates

| component/path | modes | W_SM (KiB) | factor |
|---|---|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | {profile['shared_w']} | load_repeat 1,2,4,8,16 |
| Global L1 | `clocked_empty,global_l1_load_only` | {profile['l1_w']} | load_repeat 1,2,4,8,16 |
| L2 | `{profile['l2_modes']}` | {profile['l2_w']} | load_repeat 1,2,4,8,16 |
| DRAM sanity | `clocked_empty,dram_cg_load_only` | {profile['dram_w']} | load_repeat 1,4,16 |

## How To Run

```bash
bash {out_sh}
```

Review the NCU acceptance report before treating any coefficient as usable.
Values are board-level effective coefficients, not pure physical bitcell energy.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main() -> int:
    today = dt.date.today().strftime("%Y%m%d")
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--ncu", default="ncu")
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--active-sm", type=int, default=0)
    parser.add_argument("--blocks-per-sm-values", default="")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--tag", default=today)
    parser.add_argument("--out-sh", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    profile = PROFILES[args.target_profile]
    if not args.out_sh:
        args.out_sh = (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_commands.sh"
        )
    if not args.out_md:
        args.out_md = (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_command_plan.md"
        )

    write_shell(args, profile, Path(args.out_sh))
    write_markdown(args, profile, Path(args.out_md))
    print(f"wrote shell: {args.out_sh}")
    print(f"wrote markdown: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
