#!/usr/bin/env python3
"""Audit whether a GPU is quiet enough to start a strict energy experiment."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any


GPU_FIELDS = (
    "utilization.gpu",
    "utilization.memory",
    "memory.used",
    "memory.free",
    "power.draw",
    "pstate",
    "clocks.sm",
    "clocks.mem",
    "temperature.gpu",
)


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired as exc:
        return 124, str(exc.stdout or "TIMEOUT")


def parse_float(value: str) -> float | None:
    normalized = value.strip().replace("MiB", "").replace("W", "")
    if not normalized or normalized.lower() in {"n/a", "[not supported]"}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def query_sample(gpu: int, sample_index: int) -> tuple[dict[str, Any] | None, str]:
    rc, out = run(
        [
            "nvidia-smi",
            f"--id={gpu}",
            f"--query-gpu={','.join(GPU_FIELDS)}",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0 or not out:
        return None, out or f"nvidia-smi returned {rc}"
    line = out.splitlines()[0]
    values = [item.strip() for item in line.split(",")]
    if len(values) != len(GPU_FIELDS):
        return None, f"unexpected field count: {line}"
    now = dt.datetime.now().astimezone()
    row: dict[str, Any] = {
        "sample_index": sample_index,
        "timestamp_iso": now.isoformat(timespec="milliseconds"),
        "timestamp_epoch_ms": int(now.timestamp() * 1000),
    }
    row.update(dict(zip(GPU_FIELDS, values)))
    return row, ""


def query_compute_processes(gpu: int) -> tuple[list[str], str]:
    rc, out = run(
        [
            "nvidia-smi",
            f"--id={gpu}",
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0:
        return [], out or f"nvidia-smi returned {rc}"
    rows = [line.strip() for line in out.splitlines() if line.strip()]
    return rows, ""


def numeric_values(samples: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in samples:
        value = parse_float(str(row.get(field, "")))
        if value is not None:
            values.append(value)
    return values


def evaluate(
    samples: list[dict[str, Any]],
    compute_processes: list[str],
    sample_errors: list[str],
    *,
    max_gpu_util_pct: float,
    p95_gpu_util_pct: float,
    max_memory_util_pct: float,
    p95_memory_util_pct: float,
    max_memory_used_drift_mib: float,
) -> tuple[dict[str, Any], list[str]]:
    gpu_util = numeric_values(samples, "utilization.gpu")
    memory_util = numeric_values(samples, "utilization.memory")
    memory_used = numeric_values(samples, "memory.used")
    power = numeric_values(samples, "power.draw")
    summary: dict[str, Any] = {
        "sample_count": len(samples),
        "sample_error_count": len(sample_errors),
        "compute_process_count": len(compute_processes),
        "gpu_util_max_pct": max(gpu_util) if gpu_util else math.nan,
        "gpu_util_p95_pct": percentile_nearest_rank(gpu_util, 0.95),
        "gpu_util_median_pct": statistics.median(gpu_util) if gpu_util else math.nan,
        "memory_util_max_pct": max(memory_util) if memory_util else math.nan,
        "memory_util_p95_pct": percentile_nearest_rank(memory_util, 0.95),
        "memory_util_median_pct": (
            statistics.median(memory_util) if memory_util else math.nan
        ),
        "memory_used_min_mib": min(memory_used) if memory_used else math.nan,
        "memory_used_max_mib": max(memory_used) if memory_used else math.nan,
        "memory_used_drift_mib": (
            max(memory_used) - min(memory_used) if memory_used else math.nan
        ),
        "power_min_w": min(power) if power else math.nan,
        "power_max_w": max(power) if power else math.nan,
        "power_median_w": statistics.median(power) if power else math.nan,
    }
    reasons: list[str] = []
    if sample_errors:
        reasons.append(f"sample_query_errors={len(sample_errors)}")
    if len(gpu_util) != len(samples) or len(memory_util) != len(samples):
        reasons.append("missing_utilization_samples")
    if not samples:
        reasons.append("no_gpu_samples")
    if gpu_util and max(gpu_util) > max_gpu_util_pct:
        reasons.append(
            f"gpu_util_max_pct={max(gpu_util):g}>{max_gpu_util_pct:g}"
        )
    gpu_p95 = percentile_nearest_rank(gpu_util, 0.95)
    if gpu_util and gpu_p95 > p95_gpu_util_pct:
        reasons.append(f"gpu_util_p95_pct={gpu_p95:g}>{p95_gpu_util_pct:g}")
    if memory_util and max(memory_util) > max_memory_util_pct:
        reasons.append(
            f"memory_util_max_pct={max(memory_util):g}>{max_memory_util_pct:g}"
        )
    memory_p95 = percentile_nearest_rank(memory_util, 0.95)
    if memory_util and memory_p95 > p95_memory_util_pct:
        reasons.append(
            f"memory_util_p95_pct={memory_p95:g}>{p95_memory_util_pct:g}"
        )
    if memory_used:
        drift = max(memory_used) - min(memory_used)
        if drift > max_memory_used_drift_mib:
            reasons.append(
                f"memory_used_drift_mib={drift:g}>{max_memory_used_drift_mib:g}"
            )
    if compute_processes:
        reasons.append(f"external_compute_processes={len(compute_processes)}")
    summary["status"] = "pass" if not reasons else "reject"
    summary["reasons"] = ";".join(reasons) if reasons else "none"
    return summary, reasons


def write_csv(path: Path, samples: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["sample_index", "timestamp_iso", "timestamp_epoch_ms", *GPU_FIELDS]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(samples)


def format_number(value: Any, digits: int = 3) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "not_available"
    return f"{float(value):.{digits}f}"


def write_markdown(
    path: Path,
    gpu: int,
    summary: dict[str, Any],
    compute_processes: list[str],
    process_error: str,
    sample_errors: list[str],
    thresholds: dict[str, float],
    csv_path: Path,
) -> None:
    lines = [
        "# GPU Quiescence Audit",
        "",
        f"- Date: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- GPU index: `{gpu}`",
        f"- Verdict: `{summary['status']}`",
        f"- Reasons: `{summary['reasons']}`",
        f"- Raw samples: `{csv_path}`",
        "",
        "## Utilization Summary",
        "",
        "| metric | value | strict limit | unit |",
        "|---|---:|---:|---|",
        f"| GPU utilization max | {format_number(summary['gpu_util_max_pct'])} | {thresholds['max_gpu_util_pct']:g} | % |",
        f"| GPU utilization p95 | {format_number(summary['gpu_util_p95_pct'])} | {thresholds['p95_gpu_util_pct']:g} | % |",
        f"| memory-controller utilization max | {format_number(summary['memory_util_max_pct'])} | {thresholds['max_memory_util_pct']:g} | % |",
        f"| memory-controller utilization p95 | {format_number(summary['memory_util_p95_pct'])} | {thresholds['p95_memory_util_pct']:g} | % |",
        f"| frame-buffer memory used min | {format_number(summary['memory_used_min_mib'])} | not gated | MiB |",
        f"| frame-buffer memory used max | {format_number(summary['memory_used_max_mib'])} | not gated | MiB |",
        f"| frame-buffer memory used drift | {format_number(summary['memory_used_drift_mib'])} | {thresholds['max_memory_used_drift_mib']:g} | MiB |",
        f"| board power min-median-max | {format_number(summary['power_min_w'])} / {format_number(summary['power_median_w'])} / {format_number(summary['power_max_w'])} | diagnostic | W |",
        f"| visible compute processes | {summary['compute_process_count']} | 0 | process count |",
        "",
        "## Process Evidence",
        "",
    ]
    if compute_processes:
        lines.extend(["```text", *compute_processes, "```"])
    elif process_error:
        lines.append(f"Compute-process query failed: `{process_error}`")
    else:
        lines.append("No compute process was reported by `nvidia-smi`.")
    if sample_errors:
        lines.extend(["", "Sample errors:", "", "```text", *sample_errors, "```"])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `memory.used` is allocated frame-buffer memory, not allocated L2 cache. "
            "It is recorded for context but its absolute value is not a rejection gate.",
            "- L2 has no meaningful pre-run hit-rate value. Hit rate is defined by a "
            "kernel's requests and must be measured with NCU during that workload.",
            "- Sustained memory-controller utilization or another compute process can "
            "evict benchmark cache lines and contaminate board-energy measurements.",
            "- Under WSL/WDDM, Windows graphics processes may not appear in the Linux "
            "compute-process list. The utilization time series remains a required gate.",
            "- Passing this audit proves only that the sampled pre-run interval was quiet. "
            "It does not prove exclusive ownership for the entire later experiment.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_test() -> int:
    quiet = [
        {
            "utilization.gpu": "0",
            "utilization.memory": "1",
            "memory.used": str(1000 + i),
            "power.draw": "20",
        }
        for i in range(10)
    ]
    summary, reasons = evaluate(
        quiet,
        [],
        [],
        max_gpu_util_pct=10,
        p95_gpu_util_pct=5,
        max_memory_util_pct=25,
        p95_memory_util_pct=10,
        max_memory_used_drift_mib=128,
    )
    assert not reasons and summary["status"] == "pass", (summary, reasons)
    busy = [dict(row) for row in quiet]
    for row in busy[2:]:
        row["utilization.memory"] = "30"
    summary, reasons = evaluate(
        busy,
        [],
        [],
        max_gpu_util_pct=10,
        p95_gpu_util_pct=5,
        max_memory_util_pct=25,
        p95_memory_util_pct=10,
        max_memory_used_drift_mib=128,
    )
    assert summary["status"] == "reject"
    assert any(reason.startswith("memory_util_p95_pct") for reason in reasons)
    summary, reasons = evaluate(
        quiet,
        ["1234, another_process, 256"],
        [],
        max_gpu_util_pct=10,
        p95_gpu_util_pct=5,
        max_memory_util_pct=25,
        p95_memory_util_pct=10,
        max_memory_used_drift_mib=128,
    )
    assert "external_compute_processes=1" in reasons
    print("gpu quiescence audit self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--interval-ms", type=int, default=1000)
    parser.add_argument("--max-gpu-util-pct", type=float, default=10.0)
    parser.add_argument("--p95-gpu-util-pct", type=float, default=5.0)
    parser.add_argument("--max-memory-util-pct", type=float, default=25.0)
    parser.add_argument("--p95-memory-util-pct", type=float, default=10.0)
    parser.add_argument("--max-memory-used-drift-mib", type=float, default=128.0)
    parser.add_argument("--out-csv", default="results/summary/gpu_quiescence.csv")
    parser.add_argument("--out-md", default="results/summary/gpu_quiescence.md")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.samples <= 0 or args.interval_ms < 0:
        parser.error("--samples must be positive and --interval-ms non-negative")

    samples: list[dict[str, Any]] = []
    errors: list[str] = []
    next_sample = time.monotonic()
    for index in range(args.samples):
        row, error = query_sample(args.gpu, index)
        if row is not None:
            samples.append(row)
        else:
            errors.append(f"sample {index}: {error}")
        next_sample += args.interval_ms / 1000.0
        if index + 1 < args.samples:
            time.sleep(max(0.0, next_sample - time.monotonic()))

    processes, process_error = query_compute_processes(args.gpu)
    if process_error:
        errors.append(f"compute process query: {process_error}")
    thresholds = {
        "max_gpu_util_pct": args.max_gpu_util_pct,
        "p95_gpu_util_pct": args.p95_gpu_util_pct,
        "max_memory_util_pct": args.max_memory_util_pct,
        "p95_memory_util_pct": args.p95_memory_util_pct,
        "max_memory_used_drift_mib": args.max_memory_used_drift_mib,
    }
    summary, reasons = evaluate(
        samples,
        processes,
        errors,
        **thresholds,
    )
    csv_path = Path(args.out_csv)
    md_path = Path(args.out_md)
    write_csv(csv_path, samples)
    write_markdown(
        md_path,
        args.gpu,
        summary,
        processes,
        process_error,
        errors,
        thresholds,
        csv_path,
    )
    print(
        f"GPU quiescence: {summary['status']} reasons={summary['reasons']} "
        f"samples={len(samples)} report={md_path}"
    )
    return 2 if args.strict and reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
