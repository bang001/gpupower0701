#!/usr/bin/env python3
"""Capture and gate RTX 3090 native-FP16 EX2 control/treatment NCU evidence.

This is a deliberately small, path-only experiment.  For each of the scalar
``ex2.approx.f16`` and packed ``ex2.approx.f16x2`` implementations it profiles
the same full-Softmax kernel symbol twice: once without the runtime extra-EX2
probe and once with it.  The gate requires an exact additional

    grid_blocks * ITER * softmax_cols

predicated XU thread instructions, identical launch resources, and identical
request-side memory-traffic counters.  Device-wide DRAM bytes are reported as
an observation but are not used as a path-equivalence gate on a display-attached
RTX 3090.  Application-side energy and timing collected while Nsight Compute
replays a kernel are explicitly unusable for ATC energy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import os
import shutil
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


AUDIT_REVISION = "rtx3090_softmax_native_ex2_ncu_v1"
TARGET_METRIC = "smsp__thread_inst_executed_pipe_xu_pred_on.sum"
DEFAULT_SOFTMAX_COLS = 512
SUPPORTED_SOFTMAX_COLS = (128, 256, 512, 1024, 2048, 4096)
THREADS_PER_BLOCK = 256
CACHE_CONDITION = "cache_reuse_candidate"
CACHE_POLICY = "default"
LOGIT_SCALE = 4.0

IMPLEMENTATIONS = (
    ("ptx_f16", "ptx_ex2_approx_f16", "ex2.approx.f16", 1),
    ("ptx_f16x2", "ptx_ex2_approx_f16x2", "ex2.approx.f16x2", 2),
)

RESOURCE_METRICS = (
    "launch__registers_per_thread",
    "launch__registers_per_thread_allocated",
    "launch__shared_mem_per_block",
    "launch__shared_mem_per_block_allocated",
    "launch__shared_mem_per_block_static",
    "launch__occupancy_limit_blocks",
    "launch__occupancy_limit_registers",
    "launch__occupancy_limit_shared_mem",
    "launch__occupancy_limit_warps",
)

TRAFFIC_METRICS = (
    "smsp__inst_executed_pipe_lsu.sum",
    "smsp__inst_executed_pipe_cbu.sum",
    "smsp__inst_executed_op_global_ld.sum",
    "smsp__inst_executed_op_global_st.sum",
    "smsp__inst_executed_op_shared_ld.sum",
    "smsp__inst_executed_op_shared_st.sum",
    "l1tex__t_requests_pipe_lsu_mem_global_op_ld.sum",
    "l1tex__t_requests_pipe_lsu_mem_global_op_st.sum",
    "dram__bytes_read.sum",
    "dram__bytes_write.sum",
)

NCU_METRICS = ",".join((*RESOURCE_METRICS, TARGET_METRIC, *TRAFFIC_METRICS))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def ncu_kernel_row(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        first_csv = next(
            index
            for index, line in enumerate(lines)
            if line.startswith('"ID",') or line.startswith("ID,")
        )
    except StopIteration as error:
        raise RuntimeError(f"NCU raw CSV header not found: {path}") from error
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[first_csv:]))))
    kernels = [
        row
        for row in rows
        if "softmax_row_kernel"
        in (row.get("Kernel Name", "") or row.get("launch__kernel_name", ""))
    ]
    if len(kernels) != 1:
        raise RuntimeError(
            f"expected exactly one profiled softmax_row_kernel in {path}, "
            f"got {len(kernels)}"
        )
    return kernels[0]


def kernel_name(row: dict[str, str]) -> str:
    return (row.get("Kernel Name", "") or row.get("launch__kernel_name", "")).strip()


def integer(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "").replace(",", "").strip()
    if not raw or raw.lower() in {"n/a", "na", "--"}:
        raise RuntimeError(f"missing NCU metric {field}")
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise RuntimeError(f"NCU metric {field} is not numeric: {raw!r}") from error
    integral = value.to_integral_value()
    if value != integral:
        raise RuntimeError(f"NCU counter {field} is not integral: {raw!r}")
    return int(integral)


def tuple_product(value: str) -> int:
    values = [int(part) for part in value.strip("() ").split(",") if part.strip()]
    if not values:
        raise RuntimeError(f"invalid NCU launch tuple: {value!r}")
    return math.prod(values)


def launch_size(row: dict[str, str], scalar: str, tuple_name: str) -> int:
    raw = row.get(scalar, "").replace(",", "").strip()
    if raw:
        return int(Decimal(raw))
    return tuple_product(row.get(tuple_name, ""))


def ncu_version(ncu: Path) -> str:
    process = subprocess.run(
        [str(ncu), "--version"], check=False, capture_output=True, text=True
    )
    text = "\n".join((process.stdout, process.stderr))
    for line in text.splitlines():
        if line.startswith("Version "):
            return line.removeprefix("Version ").strip()
    return "unknown"


def classify_capture_failure(text: str) -> str:
    lowered = text.lower()
    if "err_nvgpuctrperm" in lowered or "permission" in lowered:
        return "ncu_counter_permission_denied"
    if "unknown metric" in lowered or "cannot be found" in lowered:
        return "ncu_metric_unavailable"
    return "ncu_capture_failed"


def expected_xu_counts(
    grid_blocks: int, iters: int, softmax_cols: int
) -> tuple[int, int, int]:
    # ptxas predicates the reciprocal on threads that own an output element.
    # For S < one CTA this is S threads; for longer rows all CTA threads
    # contribute one or more output elements.
    reciprocal_threads = min(softmax_cols, THREADS_PER_BLOCK)
    expected_delta = grid_blocks * iters * softmax_cols
    expected_control = grid_blocks * iters * (
        softmax_cols + reciprocal_threads
    )
    return expected_control, expected_control + expected_delta, expected_delta


def run_self_test() -> int:
    assert expected_xu_counts(16, 5000, 128) == (
        20_480_000,
        30_720_000,
        10_240_000,
    )
    assert expected_xu_counts(16, 5000, 256) == (
        40_960_000,
        61_440_000,
        20_480_000,
    )
    assert expected_xu_counts(16, 5000, 512) == (
        61_440_000,
        102_400_000,
        40_960_000,
    )
    print("self_test=pass")
    return 0


def require_runtime_row(
    path: Path,
    *,
    binary_hash: str,
    canonical_impl: str,
    ptx_instruction: str,
    packed_width: int,
    grid_blocks: int,
    iters: int,
    softmax_cols: int,
    extra_probe: bool,
) -> dict[str, str]:
    rows = read_rows(path)
    if len(rows) != 1:
        raise RuntimeError(f"{path} must contain exactly one runtime row")
    row = rows[0]
    required = {
        "profile_name": "rtx3090",
        "compute_capability": "8.6",
        "cuda_binary_arch": "86",
        "mode": "softmax_full_f16io_f32acc",
        "exp_impl": canonical_impl,
        "exp_ptx_instruction": ptx_instruction,
        "exp_results_per_ptx_instruction": str(packed_width),
        "extra_exp_probe": "true" if extra_probe else "false",
        "grid_blocks": str(grid_blocks),
        "grid_blocks_source": "explicit",
        "ITER": str(iters),
        "softmax_cols": str(softmax_cols),
        "threads_per_block": str(THREADS_PER_BLOCK),
        "cache_condition": CACHE_CONDITION,
        "cache_policy": CACHE_POLICY,
        "binary_sha256": binary_hash,
        "measurement_scope": "resource_sidecar_energy_excluded",
        "energy_trace_status": "disabled_endpoint_only",
        "smid_all_blocks_observed": "true",
        "smid_total_blocks": str(grid_blocks),
    }
    failures = [
        f"{field}={row.get(field, '<missing>')} expected {expected}"
        for field, expected in required.items()
        if row.get(field) != expected
    ]
    if failures:
        raise RuntimeError("runtime provenance mismatch: " + "; ".join(failures))
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    binary: Path,
    binary_hash: str,
    ncu: Path,
    version: str,
    grid_blocks: int,
    iters: int,
    softmax_cols: int,
    failure: str = "",
) -> None:
    overall = "pass" if rows and all(row.get("verdict") == "pass" for row in rows) else "fail"
    lines = [
        "# RTX 3090 native FP16 EX2 NCU dynamic gate",
        "",
        f"- overall: `{overall}`",
        f"- audit revision: `{AUDIT_REVISION}`",
        f"- binary: `{binary}`",
        f"- binary SHA-256: `{binary_hash}`",
        f"- NCU: `{ncu}` (`{version}`)",
        f"- coordinate: grid `{grid_blocks}`, ITER `{iters}`, S `{softmax_cols}`, threads/CTA `{THREADS_PER_BLOCK}`",
        f"- target: `{TARGET_METRIC}` (predicated XU thread instructions)",
        "- energy usability: `false` — profiler replay timing and application NVML deltas are excluded from ATC energy",
        "",
    ]
    if failure:
        lines.extend(("## Capture blocker", "", failure, ""))
    if rows:
        lines.extend(
            (
                "## Gate results",
                "",
                "| PTX implementation | same symbol | XU control | XU treatment | observed delta | expected delta | resources | request traffic | DRAM observation | verdict |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            )
        )
        for row in rows:
            lines.append(
                "| `{exp_ptx_instruction}` | {same_kernel_symbol_status} | {control_xu_thread_instructions} | "
                "{treatment_xu_thread_instructions} | {observed_xu_delta} | {expected_xu_delta} | "
                "{resource_match_status} | {logical_traffic_match_status} | {dram_traffic_match_status} | "
                "**{verdict}** |".format(**row)
            )
        expected_control, expected_treatment, expected_delta = expected_xu_counts(
            grid_blocks, iters, softmax_cols
        )
        reciprocal_threads = min(softmax_cols, THREADS_PER_BLOCK)
        lines.extend(
            (
                "",
                "## Interpretation",
                "",
                f"The control expectation is `{grid_blocks} * {iters} * ({softmax_cols} base EX2 + {reciprocal_threads} active-lane reciprocal) = {expected_control}` XU thread instructions. Treatment adds `{grid_blocks} * {iters} * {softmax_cols} = {expected_delta}` probe instructions, giving `{expected_treatment}`.",
                "",
                "The exact delta is one additional scalar EX2 result per element. Combined with the final-binary SASS audit, the packed-path count confirms that Ampere executes two predicated `MUFU.EX2.F16` thread instructions for each packed two-result PTX operation; it is not a single 2-result hardware instruction on this binary.",
                "",
                "Resource equality checks registers, shared memory, and occupancy limits. The traffic gate checks LSU, global/shared load-store instructions, and L1 global requests. CBU counts and device-wide DRAM bytes are observations, not traffic gates: CBU is a control-flow pipeline counter, while DRAM bytes on this display-attached RTX 3090 also reflect cache state and non-kernel board traffic. Neither can establish a memory-path mismatch when the attributable request counters are exactly equal.",
                "",
                "## Scope limitation",
                "",
                "This proves the dynamic instruction/path contrast for the exact RTX 3090 binary and coordinate only. It neither supplies an energy coefficient nor proves an A100 runtime result.",
                "",
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--self-test", action="store_true")
    result.add_argument("--binary", type=Path)
    result.add_argument("--out-dir", type=Path)
    result.add_argument("--summary-prefix", type=Path)
    result.add_argument(
        "--ncu",
        type=Path,
        default=Path("/home/bang001/.local/NVIDIA-Nsight-Compute-2026.2.1/ncu"),
    )
    result.add_argument("--gpu-id", type=int, default=0)
    result.add_argument("--grid-blocks", type=int, default=16)
    result.add_argument("--iters", type=int, default=5000)
    result.add_argument(
        "--softmax-cols",
        type=int,
        choices=SUPPORTED_SOFTMAX_COLS,
        default=DEFAULT_SOFTMAX_COLS,
        help=f"Softmax row width (default: {DEFAULT_SOFTMAX_COLS})",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        return run_self_test()
    missing = [
        name
        for name in ("binary", "out_dir", "summary_prefix")
        if getattr(args, name) is None
    ]
    if missing:
        raise SystemExit(
            "missing required arguments outside --self-test: "
            + ", ".join(f"--{name.replace('_', '-')}" for name in missing)
        )
    binary = args.binary.resolve()
    ncu = args.ncu.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"missing executable: {binary}")
    if not ncu.is_file() or not os.access(ncu, os.X_OK):
        fallback = shutil.which(str(args.ncu))
        if not fallback:
            raise SystemExit(f"NCU executable not found: {args.ncu}")
        ncu = Path(fallback).resolve()
    if args.grid_blocks <= 0 or args.iters <= 0:
        raise SystemExit("--grid-blocks and --iters must be positive")
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit(f"refusing non-empty NCU output directory: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.summary_prefix.parent.mkdir(parents=True, exist_ok=True)

    binary_hash = sha256(binary)
    version = ncu_version(ncu)
    captured: dict[tuple[str, str], tuple[dict[str, str], dict[str, str], Path, Path]] = {}
    manifest_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    failure = ""

    try:
        for cli_impl, canonical_impl, ptx_instruction, packed_width in IMPLEMENTATIONS:
            for role, extra_probe in (("control", False), ("treatment", True)):
                stem = f"{cli_impl}_{role}"
                ncu_csv = args.out_dir / f"{stem}.csv"
                runtime_csv = args.out_dir / f"{stem}_runtime_energy_excluded.csv"
                stdout_log = args.out_dir / f"{stem}_stdout.log"
                stderr_log = args.out_dir / f"{stem}_stderr.log"
                command = [
                    str(ncu),
                    "--target-processes", "all",
                    "--csv", "--page", "raw", "--print-units", "base", "--print-fp",
                    "--cache-control", "none", "--clock-control", "none",
                    "--metrics", NCU_METRICS,
                    "--kernel-name", "regex:softmax_row_kernel",
                    "--launch-count", "1",
                    "--log-file", str(ncu_csv),
                    str(binary),
                    "--mode", "full",
                    "--gpu-id", str(args.gpu_id),
                    "--target-profile", "rtx3090",
                    "--softmax-cols", str(args.softmax_cols),
                    "--exp-impl", cli_impl,
                    "--grid-blocks", str(args.grid_blocks),
                    "--blocks-per-sm", "1",
                    "--iters", str(args.iters),
                    "--cache-condition", CACHE_CONDITION,
                    "--cache-policy", CACHE_POLICY,
                    "--logit-scale", str(LOGIT_SCALE),
                    "--idle-measure-seconds", "0.02",
                    "--energy-trace", "0",
                    "--measurement-purpose", "resource_sidecar",
                    "--numerical-check-id", "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
                    "--binary-sha256", binary_hash,
                    "--extra-exp-probe", "1" if extra_probe else "0",
                    "--pair-id", f"rtx3090_native_ncu_{cli_impl}_g{args.grid_blocks}",
                    "--role", role,
                    "--output", str(runtime_csv),
                ]
                started = time.time()
                process = subprocess.run(command, check=False, capture_output=True, text=True)
                ended = time.time()
                stdout_log.write_text(process.stdout, encoding="utf-8")
                stderr_log.write_text(process.stderr, encoding="utf-8")
                combined = "\n".join((process.stdout, process.stderr))
                if process.returncode != 0:
                    category = classify_capture_failure(combined)
                    raise RuntimeError(
                        f"{category}: {cli_impl}/{role} NCU exited {process.returncode}; "
                        f"see {stderr_log} and {stdout_log}"
                    )
                if sha256(binary) != binary_hash:
                    raise RuntimeError("binary_changed_during_capture")
                if not ncu_csv.is_file() or ncu_csv.stat().st_size == 0:
                    raise RuntimeError(f"NCU did not emit {ncu_csv}")
                ncu_row = ncu_kernel_row(ncu_csv)
                runtime_row = require_runtime_row(
                    runtime_csv,
                    binary_hash=binary_hash,
                    canonical_impl=canonical_impl,
                    ptx_instruction=ptx_instruction,
                    packed_width=packed_width,
                    grid_blocks=args.grid_blocks,
                    iters=args.iters,
                    softmax_cols=args.softmax_cols,
                    extra_probe=extra_probe,
                )
                captured[(cli_impl, role)] = (
                    ncu_row,
                    runtime_row,
                    ncu_csv,
                    runtime_csv,
                )
                manifest_rows.append(
                    {
                        "audit_revision": AUDIT_REVISION,
                        "capture_started_epoch_s": f"{started:.6f}",
                        "capture_ended_epoch_s": f"{ended:.6f}",
                        "exp_impl_cli": cli_impl,
                        "exp_impl": canonical_impl,
                        "exp_ptx_instruction": ptx_instruction,
                        "role": role,
                        "extra_exp_probe": str(extra_probe).lower(),
                        "grid_blocks": args.grid_blocks,
                        "ITER": args.iters,
                        "softmax_cols": args.softmax_cols,
                        "threads_per_block": THREADS_PER_BLOCK,
                        "binary": str(binary),
                        "binary_sha256": binary_hash,
                        "ncu": str(ncu),
                        "ncu_version": version,
                        "ncu_source": str(ncu_csv.resolve()),
                        "ncu_source_sha256": sha256(ncu_csv),
                        "runtime_source": str(runtime_csv.resolve()),
                        "runtime_source_sha256": sha256(runtime_csv),
                        "kernel_name": kernel_name(ncu_row),
                        "measurement_scope": "resource_sidecar_energy_excluded",
                        "energy_usable": "false",
                    }
                )

        expected_control, expected_treatment, expected_delta = expected_xu_counts(
            args.grid_blocks, args.iters, args.softmax_cols
        )
        for cli_impl, canonical_impl, ptx_instruction, packed_width in IMPLEMENTATIONS:
            control, control_runtime, control_source, control_runtime_source = captured[
                (cli_impl, "control")
            ]
            treatment, treatment_runtime, treatment_source, treatment_runtime_source = captured[
                (cli_impl, "treatment")
            ]
            control_kernel = kernel_name(control)
            treatment_kernel = kernel_name(treatment)
            same_symbol = control_kernel == treatment_kernel and bool(control_kernel)
            launch_match = (
                launch_size(control, "launch__grid_size", "Grid Size")
                == launch_size(treatment, "launch__grid_size", "Grid Size")
                == args.grid_blocks
                and launch_size(control, "launch__block_size", "Block Size")
                == launch_size(treatment, "launch__block_size", "Block Size")
                == THREADS_PER_BLOCK
            )
            control_xu = integer(control, TARGET_METRIC)
            treatment_xu = integer(treatment, TARGET_METRIC)
            observed_delta = treatment_xu - control_xu
            resource_values = {
                metric: (integer(control, metric), integer(treatment, metric))
                for metric in RESOURCE_METRICS
            }
            traffic_values = {
                metric: (integer(control, metric), integer(treatment, metric))
                for metric in TRAFFIC_METRICS
            }
            resource_match = all(left == right for left, right in resource_values.values())
            logical_metrics = tuple(
                metric
                for metric in TRAFFIC_METRICS
                if not metric.startswith("dram__")
                and metric != "smsp__inst_executed_pipe_cbu.sum"
            )
            logical_traffic_match = all(
                traffic_values[metric][0] == traffic_values[metric][1]
                for metric in logical_metrics
            )
            dram_traffic_match = all(
                traffic_values[metric][0] == traffic_values[metric][1]
                for metric in TRAFFIC_METRICS
                if metric.startswith("dram__")
            )
            cbu_match = (
                traffic_values["smsp__inst_executed_pipe_cbu.sum"][0]
                == traffic_values["smsp__inst_executed_pipe_cbu.sum"][1]
            )
            exact_counts = (
                control_xu == expected_control
                and treatment_xu == expected_treatment
                and observed_delta == expected_delta
            )
            runtime_smid_match = (
                control_runtime.get("smid_set") == treatment_runtime.get("smid_set")
                and control_runtime.get("smid_histogram")
                == treatment_runtime.get("smid_histogram")
            )
            checks = {
                "same_kernel_symbol": same_symbol,
                "launch_coordinate": launch_match,
                "exact_xu_counts": exact_counts,
                "resource_match": resource_match,
                "logical_traffic_match": logical_traffic_match,
                "runtime_smid_assignment_match": runtime_smid_match,
            }
            reasons = [name for name, passed in checks.items() if not passed]
            row: dict[str, Any] = {
                "audit_revision": AUDIT_REVISION,
                "exp_impl_cli": cli_impl,
                "exp_impl": canonical_impl,
                "exp_ptx_instruction": ptx_instruction,
                "exp_results_per_ptx_instruction": packed_width,
                "binary": str(binary),
                "binary_sha256": binary_hash,
                "ncu": str(ncu),
                "ncu_version": version,
                "gpu_name": control_runtime.get("gpu_name", ""),
                "compute_capability": control_runtime.get("compute_capability", ""),
                "cuda_binary_arch": control_runtime.get("cuda_binary_arch", ""),
                "grid_blocks": args.grid_blocks,
                "ITER": args.iters,
                "softmax_cols": args.softmax_cols,
                "threads_per_block": THREADS_PER_BLOCK,
                "control_kernel_name": control_kernel,
                "treatment_kernel_name": treatment_kernel,
                "same_kernel_symbol_status": "pass" if same_symbol else "fail",
                "launch_coordinate_status": "pass" if launch_match else "fail",
                "target_metric": TARGET_METRIC,
                "target_count_unit": "predicated_thread_instruction",
                "control_xu_thread_instructions": control_xu,
                "expected_control_xu_thread_instructions": expected_control,
                "control_xu_count_status": "pass" if control_xu == expected_control else "fail",
                "treatment_xu_thread_instructions": treatment_xu,
                "expected_treatment_xu_thread_instructions": expected_treatment,
                "treatment_xu_count_status": "pass" if treatment_xu == expected_treatment else "fail",
                "observed_xu_delta": observed_delta,
                "expected_xu_delta": expected_delta,
                "xu_delta_status": "pass" if observed_delta == expected_delta else "fail",
                "resource_match_status": "pass" if resource_match else "fail",
                "logical_traffic_match_status": "pass" if logical_traffic_match else "fail",
                "cbu_count_match_status": "pass" if cbu_match else "observed_mismatch",
                "cbu_count_gate_required": "false",
                "cbu_count_gate_exclusion_reason": "CBU is a control-flow pipeline counter, not a memory-traffic counter",
                "dram_traffic_match_status": "pass" if dram_traffic_match else "observed_mismatch",
                "dram_traffic_gate_required": "false",
                "dram_traffic_gate_exclusion_reason": "device-wide display/cache/background traffic is not attributable to the profiled kernel; request-side counters are the path gate",
                "runtime_smid_assignment_match_status": "pass" if runtime_smid_match else "fail",
                "energy_usable": "false",
                "energy_exclusion_reason": "NCU replay changes execution and timing; application NVML deltas are path-only artifacts",
                "control_ncu_source": str(control_source.resolve()),
                "control_ncu_sha256": sha256(control_source),
                "treatment_ncu_source": str(treatment_source.resolve()),
                "treatment_ncu_sha256": sha256(treatment_source),
                "control_runtime_source": str(control_runtime_source.resolve()),
                "control_runtime_sha256": sha256(control_runtime_source),
                "treatment_runtime_source": str(treatment_runtime_source.resolve()),
                "treatment_runtime_sha256": sha256(treatment_runtime_source),
                "verdict": "pass" if not reasons else "fail",
                "failure_reasons": ";".join(reasons),
            }
            for metric, (left, right) in resource_values.items():
                stem = metric.replace("__", "_").replace(".", "_")
                row[f"control_{stem}"] = left
                row[f"treatment_{stem}"] = right
                row[f"delta_{stem}"] = right - left
            for metric, (left, right) in traffic_values.items():
                stem = metric.replace("__", "_").replace(".", "_")
                row[f"control_{stem}"] = left
                row[f"treatment_{stem}"] = right
                row[f"delta_{stem}"] = right - left
            audit_rows.append(row)

        write_csv(args.out_dir / "capture_manifest.csv", manifest_rows)
    except Exception as error:  # emit durable evidence for permission/metric blockers
        failure = str(error)
        audit_rows = [
            {
                "audit_revision": AUDIT_REVISION,
                "exp_impl_cli": "capture",
                "exp_impl": "capture",
                "exp_ptx_instruction": "",
                "binary": str(binary),
                "binary_sha256": binary_hash,
                "ncu": str(ncu),
                "ncu_version": version,
                "grid_blocks": args.grid_blocks,
                "ITER": args.iters,
                "softmax_cols": args.softmax_cols,
                "threads_per_block": THREADS_PER_BLOCK,
                "energy_usable": "false",
                "verdict": "fail",
                "failure_reasons": failure,
            }
        ]

    csv_path = args.summary_prefix.with_suffix(".csv")
    md_path = args.summary_prefix.with_suffix(".md")
    write_csv(csv_path, audit_rows)
    write_markdown(
        md_path,
        audit_rows if not failure else [],
        binary=binary,
        binary_hash=binary_hash,
        ncu=ncu,
        version=version,
        grid_blocks=args.grid_blocks,
        iters=args.iters,
        softmax_cols=args.softmax_cols,
        failure=failure,
    )
    print(f"summary_csv={csv_path}")
    print(f"summary_md={md_path}")
    print(f"binary_sha256={binary_hash}")
    print(f"energy_usable=false")
    verdict = not failure and all(row.get("verdict") == "pass" for row in audit_rows)
    print(f"overall={'pass' if verdict else 'fail'}")
    if failure:
        print(f"failure={failure}", file=sys.stderr)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
