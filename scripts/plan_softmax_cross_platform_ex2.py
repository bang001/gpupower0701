#!/usr/bin/env python3
"""Create a fail-closed run package for the portable Softmax EX2 matrix.

The package deliberately has a small, fixed factor space:

* exponent implementation: FP32 ``__expf``, scalar FP16 EX2, packed FP16 EX2;
* CTA grid: 16, 32, 48, 64;
* Softmax row width: 128, 256, 512, 1024, 2048.

It writes both an immutable planning CSV and a serial shell command package.
The shell delegates measurement and analysis to the existing runner/analyzer,
so it cannot bypass numerical validation, NVML total-energy tracing,
counterbalanced brackets, or platform identity gates.  Unsupported cells are
written as explicit ``skipped`` rows and never replaced with a fallback.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import shlex
from datetime import date
from pathlib import Path
from typing import Any

from run_softmax_ex2_factorial_matrix import (
    ordered_macroblocks,
    stratified_implementation_assignment,
    validate_stratified_implementation_assignment,
)
from softmax_platform_profiles import (
    CTA_GRIDS,
    EXP_IMPLEMENTATIONS,
    SOFTMAX_COLS,
    assert_contract as assert_platform_contract,
    implementation_status,
    profile_for,
    profile_names,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_REVISION = "softmax_cross_platform_ex2_v1"
SCHEDULE_ALGORITHM = (
    "sha256_ranked_macroblocks_stratified_impl_permutations_v2_reused"
)
CELL_RUNNER = Path("scripts/run_softmax_operand_rate_atc.py")
CELL_ANALYZER = Path("scripts/analyze_softmax_probe_counterbalanced.py")
SASS_AUDITOR = Path("scripts/audit_softmax_native_ex2_sass.py")

CACHE_CONDITION = "cache_reuse_candidate"
CACHE_POLICY = "default"
LOGIT_SCALE = 4.0
BLOCKS_PER_SM = 2
ROLE_TARGET_SECONDS = 13.0
IDLE_MEASURE_SECONDS = 1.0
PAIRS = 6
BRACKET_WARMUP_PAIRS = 1
BRACKET_ORDER = "counterbalanced6"
BRACKET_IDLE_POLICY = "batch_once"
PREHEAT_SECONDS = 20.0
PREHEAT_ACTUAL_MIN_SECONDS = 16.0
PREHEAT_ACTUAL_MAX_SECONDS = 30.0
ENERGY_TRACE_MIN_FIT_POINTS = 16


PLAN_FIELDS = (
    "protocol_revision",
    "schedule_algorithm",
    "matrix_tag",
    "order_seed",
    "slot_index",
    "execution_order_index",
    "macroblock_index",
    "macroblock_id",
    "within_macroblock_index",
    "implementation_permutation",
    "cell_id",
    "cell_tag",
    "target_profile",
    "cuda_arch",
    "compute_capability",
    "implementation",
    "softmax_cols",
    "cta_grid_blocks",
    "blocks_per_sm",
    "status",
    "skip_reason",
    "toolchain_requirement",
    "result_scope",
    "preheat_seconds",
    "preheat_actual_bounds_seconds",
    "energy_trace_min_fit_points",
    "binary",
    "raw_csv",
    "manifest_csv",
    "trace_csv",
    "preheat_csv",
    "triplets_csv",
    "matched_csv",
    "summary_csv",
    "analysis_report_md",
    "runner_command",
    "analyzer_command",
)


def relative_or_absolute(path: Path) -> str:
    """Render repository paths readably without changing their meaning."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def output_exp_suffix(exp_impl: str) -> str:
    return "" if exp_impl == "fp32" else f"_{exp_impl}"


def trace_sample_ms(profile_name: str) -> float:
    return 500.0 if profile_name == "rtx3090" else 200.0


def toolchain_requirement(profile_name: str) -> str:
    if profile_name == "v100":
        return "CUDA_12_x_required_for_sm70"
    return "CUDA_toolkit_with_sm%d_support" % profile_for(profile_name).cuda_arch


def result_scope(profile_name: str) -> str:
    if profile_name == "h100":
        return (
            "preliminary_only_until_sm90_lowering_contract_and_target_ncu_audit"
        )
    if profile_name == "v100":
        return "fp32_baseline_only_not_eligible_for_native_ex2_comparison"
    return "candidate_after_target_ncu_and_environment_gates"


def shell_join(command: list[str]) -> str:
    return shlex.join(command)


def cell_paths(
    *,
    profile_name: str,
    cell_tag: str,
    exp_impl: str,
    grid_blocks: int,
    raw_dir: Path,
    summary_dir: Path,
    report_dir: Path,
) -> dict[str, Path]:
    output_prefix = (
        f"{profile_name}_fp16_softmax_operand_rate_atc_{cell_tag}"
        f"{output_exp_suffix(exp_impl)}"
    )
    analysis_prefix = summary_dir / (
        f"{profile_name}_softmax_cross_platform_ex2_{cell_tag}"
    )
    return {
        "raw_csv": raw_dir / f"{output_prefix}_raw.csv",
        "manifest_csv": raw_dir / f"{output_prefix}_manifest.csv",
        "trace_csv": raw_dir / f"{output_prefix}_raw_energy_trace.csv",
        "preheat_csv": raw_dir
        / f"{output_prefix}_{CACHE_CONDITION}_g{grid_blocks}_preheat.csv",
        "triplets_csv": Path(f"{analysis_prefix}_triplets.csv"),
        "matched_csv": Path(f"{analysis_prefix}_matched.csv"),
        "summary_csv": Path(f"{analysis_prefix}_summary.csv"),
        "analysis_report_md": report_dir
        / f"{profile_name}_softmax_cross_platform_ex2_{cell_tag}_ko.md",
    }


def runner_command(
    *,
    profile_name: str,
    binary: Path,
    gpu_id: int,
    exp_impl: str,
    softmax_cols: int,
    grid_blocks: int,
    cell_tag: str,
    raw_dir: Path,
) -> list[str]:
    return [
        "python3",
        relative_or_absolute(CELL_RUNNER),
        "--binary",
        relative_or_absolute(binary),
        "--gpu-id",
        str(gpu_id),
        "--target-profile",
        profile_name,
        "--cross-platform-design",
        "--exp-impl",
        exp_impl,
        "--softmax-cols",
        str(softmax_cols),
        "--blocks-per-sm",
        str(BLOCKS_PER_SM),
        "--grid-blocks-list",
        str(grid_blocks),
        "--control-mode",
        "probe",
        "--logit-scale",
        str(LOGIT_SCALE),
        "--seconds",
        str(ROLE_TARGET_SECONDS),
        "--idle-measure-seconds",
        str(IDLE_MEASURE_SECONDS),
        "--pairs",
        str(PAIRS),
        "--bracket-warmup-pairs",
        str(BRACKET_WARMUP_PAIRS),
        "--execution-mode",
        "persistent_bracket",
        "--bracket-idle-policy",
        BRACKET_IDLE_POLICY,
        "--bracket-order",
        BRACKET_ORDER,
        "--preheat-seconds",
        str(PREHEAT_SECONDS),
        "--preheat-actual-min-seconds",
        str(PREHEAT_ACTUAL_MIN_SECONDS),
        "--preheat-actual-max-seconds",
        str(PREHEAT_ACTUAL_MAX_SECONDS),
        "--conditions",
        CACHE_CONDITION,
        "--cache-policy",
        CACHE_POLICY,
        "--energy-trace",
        "1",
        "--energy-trace-sample-ms",
        str(trace_sample_ms(profile_name)),
        "--energy-trace-min-updates",
        str(ENERGY_TRACE_MIN_FIT_POINTS),
        "--tag",
        cell_tag,
        "--out-dir",
        relative_or_absolute(raw_dir),
        "--max-gpu-util-pct",
        "10.0",
        "--max-memory-util-pct",
        "15.0",
        "--quiescence-timeout-s",
        "60.0",
        "--quiescence-poll-s",
        "1.0",
        "--quiescence-consecutive-samples",
        "2",
    ]


def analyzer_command(
    *,
    exp_impl: str,
    grid_blocks: int,
    paths: dict[str, Path],
    seed: int,
) -> list[str]:
    return [
        "python3",
        relative_or_absolute(CELL_ANALYZER),
        "--cross-platform-design",
        "--input",
        relative_or_absolute(paths["raw_csv"]),
        "--energy-trace-input",
        relative_or_absolute(paths["trace_csv"]),
        "--manifest",
        relative_or_absolute(paths["manifest_csv"]),
        "--exp-impl",
        exp_impl,
        "--grid-blocks",
        str(grid_blocks),
        "--triplet-out",
        relative_or_absolute(paths["triplets_csv"]),
        "--matched-out",
        relative_or_absolute(paths["matched_csv"]),
        "--summary-out",
        relative_or_absolute(paths["summary_csv"]),
        "--report-out",
        relative_or_absolute(paths["analysis_report_md"]),
        "--decision-stage",
        "pilot",
        "--energy-trace-min-fit-points",
        str(ENERGY_TRACE_MIN_FIT_POINTS),
        "--bootstrap-samples",
        "4000",
        "--seed",
        str(seed),
    ]


def build_plan(
    *,
    profile_name: str,
    matrix_tag: str,
    order_seed: int,
    binary: Path,
    gpu_id: int,
    cuda_major: int | None,
    raw_dir: Path,
    summary_dir: Path,
    report_dir: Path,
) -> list[dict[str, str]]:
    """Build the exact 3x4x5 plan, retaining deliberate skip cells."""

    profile = profile_for(profile_name)
    macroblocks = ordered_macroblocks(order_seed)
    assignments = stratified_implementation_assignment(macroblocks, order_seed)
    # The imported solver is independent of GPU architecture.  Recheck its
    # invariant here so this planner cannot silently weaken the ordering rule.
    validate_stratified_implementation_assignment(assignments, macroblocks)

    rows: list[dict[str, str]] = []
    slot_index = 0
    execution_index = 0
    for macroblock_index, (softmax_cols, grid_blocks) in enumerate(
        macroblocks, start=1
    ):
        permutation = assignments[(softmax_cols, grid_blocks)]
        macroblock_id = f"mb{macroblock_index:02d}_g{grid_blocks}_s{softmax_cols}"
        for within_index, exp_impl in enumerate(permutation, start=1):
            slot_index += 1
            status, skip_reason = implementation_status(
                profile_name, exp_impl, cuda_major=cuda_major
            )
            if status == "runnable":
                execution_index += 1
                execution_order_index = str(execution_index)
            else:
                execution_order_index = ""
            cell_id = (
                f"c{slot_index:03d}_mb{macroblock_index:02d}_"
                f"{exp_impl}_g{grid_blocks}_s{softmax_cols}"
            )
            cell_tag = (
                f"{matrix_tag}_mb{macroblock_index:02d}_s{slot_index:03d}_"
                f"{exp_impl}_g{grid_blocks}_s{softmax_cols}"
            )
            paths = cell_paths(
                profile_name=profile_name,
                cell_tag=cell_tag,
                exp_impl=exp_impl,
                grid_blocks=grid_blocks,
                raw_dir=raw_dir,
                summary_dir=summary_dir,
                report_dir=report_dir,
            )
            runner = (
                runner_command(
                    profile_name=profile_name,
                    binary=binary,
                    gpu_id=gpu_id,
                    exp_impl=exp_impl,
                    softmax_cols=softmax_cols,
                    grid_blocks=grid_blocks,
                    cell_tag=cell_tag,
                    raw_dir=raw_dir,
                )
                if status == "runnable"
                else []
            )
            analyzer = (
                analyzer_command(
                    exp_impl=exp_impl,
                    grid_blocks=grid_blocks,
                    paths=paths,
                    seed=order_seed + slot_index * 1009,
                )
                if status == "runnable"
                else []
            )
            rows.append(
                {
                    "protocol_revision": PROTOCOL_REVISION,
                    "schedule_algorithm": SCHEDULE_ALGORITHM,
                    "matrix_tag": matrix_tag,
                    "order_seed": str(order_seed),
                    "slot_index": str(slot_index),
                    "execution_order_index": execution_order_index,
                    "macroblock_index": str(macroblock_index),
                    "macroblock_id": macroblock_id,
                    "within_macroblock_index": str(within_index),
                    "implementation_permutation": ">".join(permutation),
                    "cell_id": cell_id,
                    "cell_tag": cell_tag,
                    "target_profile": profile_name,
                    "cuda_arch": str(profile.cuda_arch),
                    "compute_capability": profile.compute_capability,
                    "implementation": exp_impl,
                    "softmax_cols": str(softmax_cols),
                    "cta_grid_blocks": str(grid_blocks),
                    "blocks_per_sm": str(BLOCKS_PER_SM),
                    "status": status,
                    "skip_reason": skip_reason,
                    "toolchain_requirement": toolchain_requirement(profile_name),
                    "result_scope": result_scope(profile_name),
                    "preheat_seconds": str(PREHEAT_SECONDS),
                    "preheat_actual_bounds_seconds": (
                        f"{PREHEAT_ACTUAL_MIN_SECONDS:g}-"
                        f"{PREHEAT_ACTUAL_MAX_SECONDS:g}"
                    ),
                    "energy_trace_min_fit_points": str(
                        ENERGY_TRACE_MIN_FIT_POINTS
                    ),
                    "binary": relative_or_absolute(binary),
                    **{
                        field: relative_or_absolute(path)
                        for field, path in paths.items()
                    },
                    "runner_command": shell_join(runner) if runner else "",
                    "analyzer_command": shell_join(analyzer) if analyzer else "",
                }
            )
    validate_plan(rows, profile_name=profile_name, cuda_major=cuda_major)
    return rows


def validate_plan(
    rows: list[dict[str, str]], *, profile_name: str, cuda_major: int | None
) -> None:
    if len(rows) != len(EXP_IMPLEMENTATIONS) * len(CTA_GRIDS) * len(SOFTMAX_COLS):
        raise ValueError("plan must retain the full nominal 3x4x5 cell space")
    if [int(row["slot_index"]) for row in rows] != list(range(1, 61)):
        raise ValueError("slot index must be exactly 1..60")
    factors = {
        (row["implementation"], int(row["cta_grid_blocks"]), int(row["softmax_cols"]))
        for row in rows
    }
    expected = set(itertools.product(EXP_IMPLEMENTATIONS, CTA_GRIDS, SOFTMAX_COLS))
    if factors != expected:
        raise ValueError("plan does not cover the nominal 3x4x5 factor space")
    if len({row["cell_id"] for row in rows}) != len(rows):
        raise ValueError("cell identifiers must be unique")
    if len({row["cell_tag"] for row in rows}) != len(rows):
        raise ValueError("cell tags must be unique")
    runnable = [row for row in rows if row["status"] == "runnable"]
    expected_runnable = sum(
        implementation_status(profile_name, impl, cuda_major=cuda_major)[0]
        == "runnable"
        for impl in EXP_IMPLEMENTATIONS
    ) * len(CTA_GRIDS) * len(SOFTMAX_COLS)
    if len(runnable) != expected_runnable:
        raise ValueError("runnable row count does not match platform capability")
    if [int(row["execution_order_index"]) for row in runnable] != list(
        range(1, len(runnable) + 1)
    ):
        raise ValueError("runnable cells do not have a contiguous execution order")
    skipped = [row for row in rows if row["status"] == "skipped"]
    if any(row["runner_command"] or row["analyzer_command"] for row in skipped):
        raise ValueError("skipped cells must not emit measurement commands")
    if profile_name == "v100":
        if any(row["implementation"] != "fp32" for row in runnable):
            raise ValueError("V100 must never schedule native FP16 EX2")
        if cuda_major is not None and cuda_major >= 13 and runnable:
            raise ValueError("CUDA 13+ V100 plan must have no runnable cells")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PLAN_FIELDS, extrasaction="raise", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def shell_cell_commands(row: dict[str, str], *, gpu_id: int) -> str:
    if row["status"] == "skipped":
        return (
            f"echo {shlex.quote('SKIP ' + row['cell_id'] + ': ' + row['skip_reason'])}\n"
        )
    # The plan records the concrete binary path.  The shell replaces only that
    # argument with $BIN so target-node operators may override it safely.
    runner = row["runner_command"].replace(
        shlex.quote(row["binary"]), '"${BIN}"'
    )
    runner = runner.replace(f"--gpu-id {gpu_id}", '--gpu-id "${GPU}"')
    return (
        f"echo {shlex.quote('RUN ' + row['cell_id'])}\n"
        f"{runner}\n"
        f"{row['analyzer_command']}\n"
    )


def build_shell_script(
    *,
    profile_name: str,
    binary: Path,
    gpu_id: int,
    matrix_tag: str,
    plan_path: Path,
    rows: list[dict[str, str]],
) -> str:
    profile = profile_for(profile_name)
    binary_text = relative_or_absolute(binary)
    build_dir = binary.parent
    log_path = Path("results/logs") / (
        f"{profile_name}_softmax_cross_platform_ex2_{matrix_tag}.log"
    )
    audit_dir = Path("results/summary")
    h100_audit_flag = (
        " --allow-unestablished-sass-lowering" if profile_name == "h100" else ""
    )
    native_sass_preamble = ""
    if profile.native_ex2_supported:
        sass_output = (
            f"{audit_dir}/{profile_name}_softmax_cross_platform_ex2_"
            f"{matrix_tag}_sass_s${{S}}.csv"
        )
        native_sass_preamble = f"""
echo "[gate] static native-EX2 SASS audit"
for S in {" ".join(str(value) for value in SOFTMAX_COLS)}; do
  python3 {shell_join([relative_or_absolute(SASS_AUDITOR)])} \\
    --binary "${{BIN}}" --cuobjdump "${{CUOBJDUMP}}" \\
    --expected-cuda-arch {profile.cuda_arch} --softmax-cols "${{S}}" \\
    --out "{sass_output}"{h100_audit_flag}
done
"""
    else:
        native_sass_preamble = """
echo "[skip] V100 has no native FP16 EX2 ISA path; native SASS audit is not applicable"
"""

    h100_notice = ""
    if profile_name == "h100":
        h100_notice = """
echo "[scope] H100 SASS audit is explicitly provisional. Energy/analyzer output remains preliminary"
echo "[scope] Do not publish a final cross-platform coefficient until an SM90 lowering contract and target-node native-EX2 NCU audit exist."
"""
    v100_toolchain_gate = ""
    if profile_name == "v100":
        v100_toolchain_gate = """
CUDA_MAJOR="$("${NVCC}" --version 2>/dev/null | sed -n 's/.*release \\([0-9][0-9]*\\)\\..*/\\1/p' | head -n 1 || true)"
if [[ -z "${CUDA_MAJOR}" || "${CUDA_MAJOR}" -ge 13 ]]; then
  echo "[skip] V100 Softmax requires CUDA 12.x to compile sm_70; found CUDA ${CUDA_MAJOR:-unknown}."
  echo "[skip] No substitute architecture or fallback implementation will be run."
  exit 0
fi
"""

    command_body = "\n".join(
        shell_cell_commands(row, gpu_id=gpu_id) for row in rows
    )
    return f"""#!/usr/bin/env bash
set -euo pipefail

# Generated by {relative_or_absolute(Path(__file__))}.
# Plan: {relative_or_absolute(plan_path)}
# Nominal cells: 60.  Unsupported cells remain explicit SKIP lines.

TARGET_PROFILE={shlex.quote(profile_name)}
GPU="${{GPU:-{gpu_id}}}"
BIN="${{BIN:-{binary_text}}}"
BUILD_DIR="${{BUILD_DIR:-{relative_or_absolute(build_dir)}}}"
NVCC="${{NVCC:-nvcc}}"
CUOBJDUMP="${{CUOBJDUMP:-cuobjdump}}"
SKIP_BUILD="${{SKIP_BUILD:-0}}"
LOG={shlex.quote(str(log_path))}

mkdir -p results/raw results/summary results/logs docs/results
exec > >(tee -a "${{LOG}}") 2>&1

echo "profile=${{TARGET_PROFILE}} gpu=${{GPU}} binary=${{BIN}}"
echo "matrix=3 implementations x 4 CTA grids x 5 Softmax widths; preheat={PREHEAT_SECONDS:g}s"
{v100_toolchain_gate}
if [[ "${{SKIP_BUILD}}" != "1" ]]; then
  cmake -S . -B "${{BUILD_DIR}}" \\
    -DCMAKE_BUILD_TYPE=Release \\
    -DCMAKE_CUDA_COMPILER="${{NVCC}}" \\
    -DCMAKE_CUDA_ARCHITECTURES={profile.cuda_arch}
  cmake --build "${{BUILD_DIR}}" --target a100_fp16_softmax_energy -j
fi
if [[ ! -x "${{BIN}}" ]]; then
  echo "binary is missing or not executable: ${{BIN}}" >&2
  exit 2
fi
{native_sass_preamble}{h100_notice}
{command_body}
echo "complete plan={relative_or_absolute(plan_path)}"
"""


def self_test() -> None:
    assert_platform_contract()
    common = dict(
        matrix_tag="selftest",
        order_seed=20260727,
        gpu_id=0,
        raw_dir=Path("results/raw"),
        summary_dir=Path("results/summary"),
        report_dir=Path("docs/results"),
    )
    v100 = build_plan(
        profile_name="v100",
        binary=Path("build-v100/a100_fp16_softmax_energy"),
        cuda_major=12,
        **common,
    )
    assert len(v100) == 60
    assert sum(row["status"] == "runnable" for row in v100) == 20
    assert sum(row["status"] == "skipped" for row in v100) == 40
    assert all(
        not row["runner_command"]
        for row in v100
        if row["implementation"] != "fp32"
    )
    v100_cuda13 = build_plan(
        profile_name="v100",
        binary=Path("build-v100/a100_fp16_softmax_energy"),
        cuda_major=13,
        **common,
    )
    assert not any(row["status"] == "runnable" for row in v100_cuda13)
    for profile_name in ("a100", "h100"):
        profile = profile_for(profile_name)
        rows = build_plan(
            profile_name=profile_name,
            binary=profile.default_binary,
            cuda_major=None,
            **common,
        )
        assert len(rows) == 60
        assert all(row["status"] == "runnable" for row in rows)
        script = build_shell_script(
            profile_name=profile_name,
            binary=profile.default_binary,
            gpu_id=0,
            matrix_tag="selftest",
            plan_path=Path("results/summary/selftest.csv"),
            rows=rows,
        )
        if profile_name == "h100":
            assert "--allow-unestablished-sass-lowering" in script
            assert "preliminary" in script
        else:
            assert "--allow-unestablished-sass-lowering" not in script
    print("softmax_cross_platform_ex2_planner_self_test=pass")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--target-profile", choices=profile_names())
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--binary", type=Path, default=None)
    parser.add_argument(
        "--cuda-major",
        type=int,
        default=None,
        help=(
            "toolchain major used for planning; required for V100 so CUDA "
            "13+ produces an explicit all-skip plan"
        ),
    )
    parser.add_argument("--tag", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--order-seed", type=int, default=20260727)
    parser.add_argument("--raw-dir", type=Path, default=Path("results/raw"))
    parser.add_argument(
        "--summary-dir", type=Path, default=Path("results/summary")
    )
    parser.add_argument("--report-dir", type=Path, default=Path("docs/results"))
    parser.add_argument("--plan-out", type=Path, default=None)
    parser.add_argument("--output-script", type=Path, default=None)
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.target_profile:
        parser.error("--target-profile is required")
    if args.gpu_id < 0:
        parser.error("--gpu-id must be non-negative")
    if args.cuda_major is not None and args.cuda_major <= 0:
        parser.error("--cuda-major must be positive")
    if args.target_profile == "v100" and args.cuda_major is None:
        parser.error(
            "--cuda-major is required for V100 so the FP32 plan cannot mask "
            "a CUDA 13+ sm_70 toolchain skip"
        )

    profile = profile_for(args.target_profile)
    binary = args.binary or profile.default_binary
    plan_out = args.plan_out or args.summary_dir / (
        f"{args.target_profile}_softmax_cross_platform_ex2_{args.tag}_plan.csv"
    )
    output_script = args.output_script or args.summary_dir / (
        f"{args.target_profile}_softmax_cross_platform_ex2_{args.tag}_commands.sh"
    )
    rows = build_plan(
        profile_name=args.target_profile,
        matrix_tag=args.tag,
        order_seed=args.order_seed,
        binary=binary,
        gpu_id=args.gpu_id,
        cuda_major=args.cuda_major,
        raw_dir=args.raw_dir,
        summary_dir=args.summary_dir,
        report_dir=args.report_dir,
    )
    script = build_shell_script(
        profile_name=args.target_profile,
        binary=binary,
        gpu_id=args.gpu_id,
        matrix_tag=args.tag,
        plan_path=plan_out,
        rows=rows,
    )
    if args.print_only:
        print(script, end="")
        return 0
    write_csv(plan_out, rows)
    output_script.parent.mkdir(parents=True, exist_ok=True)
    output_script.write_text(script, encoding="utf-8")
    output_script.chmod(0o755)
    runnable = sum(row["status"] == "runnable" for row in rows)
    skipped = len(rows) - runnable
    print(f"plan_out={plan_out}")
    print(f"output_script={output_script}")
    print(f"runnable_cells={runnable}")
    print(f"skipped_cells={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
