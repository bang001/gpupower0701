#!/usr/bin/env python3
"""Preflight support checks for the multi-GPU FP16 energy harness."""

from __future__ import annotations

import argparse
import datetime as dt
import shlex
import subprocess
from pathlib import Path
from typing import Any


PROFILES: dict[str, dict[str, Any]] = {
    "v100": {
        "aliases": ["v100", "tesla v100"],
        "cc": "7.0",
        "cuda_arch": "70",
        "full_sm": 80,
        "l2_mib": 6,
        "shared_kib": 96,
        "max_blocks_per_sm": 32,
        "ncu_chip": "gv100",
        "ncu_policy": "Use Nsight Compute 2024.3 or 2025.1; current 13.3 no longer supports Volta.",
        "power_usage_semantics": "instant",
    },
    "rtx3090": {
        "aliases": ["rtx 3090", "geforce rtx 3090", "3090"],
        "cc": "8.6",
        "cuda_arch": "86",
        "full_sm": 82,
        "l2_mib": 6,
        "shared_kib": 100,
        "max_blocks_per_sm": 16,
        "ncu_chip": "ga102",
        "ncu_policy": "Current Nsight Compute supports GA10x; WSL needs performance counter permission.",
        "power_usage_semantics": "one_sec_average",
    },
    "a100": {
        "aliases": ["a100"],
        "cc": "8.0",
        "cuda_arch": "80",
        "full_sm": 108,
        "l2_mib": 40,
        "shared_kib": 164,
        "max_blocks_per_sm": 32,
        "ncu_chip": "ga100",
        "ncu_policy": "Current Nsight Compute supports GA100.",
        "power_usage_semantics": "instant",
    },
    "h100": {
        "aliases": ["h100", "h800"],
        "cc": "9.0",
        "cuda_arch": "90",
        "full_sm": 132,
        "l2_mib": 50,
        "shared_kib": 228,
        "max_blocks_per_sm": 32,
        "ncu_chip": "gh100",
        "ncu_policy": "Current Nsight Compute supports GH100; WGMMA/TMA metrics need separate checks.",
        "power_usage_semantics": "one_sec_average",
    },
}


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
        return 124, (exc.stdout or "") + "\nTIMEOUT"


def split_csv_line(line: str) -> list[str]:
    return [item.strip() for item in line.split(",")]


def detect_profile(name: str, compute_cap: str) -> str | None:
    cc = compute_cap.strip()
    for profile, info in PROFILES.items():
        if cc == info["cc"]:
            return profile
    lowered = name.lower()
    for profile, info in PROFILES.items():
        if any(alias in lowered for alias in info["aliases"]):
            return profile
    return None


def query_gpu(gpu: int) -> dict[str, str]:
    fields = [
        "index",
        "name",
        "uuid",
        "driver_version",
        "compute_cap",
        "power.draw",
        "power.limit",
        "clocks.sm",
        "clocks.mem",
    ]
    rc, out = run(
        [
            "nvidia-smi",
            f"--id={gpu}",
            f"--query-gpu={','.join(fields)}",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0:
        return {"query_error": out}
    values = split_csv_line(out.splitlines()[0])
    return dict(zip(fields, values))


def query_ncu(ncu: str, chip: str) -> dict[str, str]:
    ncu_cmd = shlex.split(ncu)
    result: dict[str, str] = {}
    rc, out = run(ncu_cmd + ["--version"])
    result["version_rc"] = str(rc)
    result["version"] = out.splitlines()[0] if out else out

    rc, out = run(ncu_cmd + ["--list-chips"])
    result["list_chips_rc"] = str(rc)
    result["chip_supported"] = "unknown"
    if rc == 0:
        result["chip_supported"] = str(chip.lower() in out.lower()).lower()
    else:
        result["list_chips_error"] = out

    rc, out = run(
        ncu_cmd
        + [
            "--query-metrics",
            "--chips",
            chip,
        ],
        timeout=60,
    )
    result["query_metrics_rc"] = str(rc)
    result["query_metrics_ok"] = str(rc == 0).lower()
    if rc != 0:
        result["query_metrics_error"] = out[:1000]
    return result


def dry_run_binary(binary: str, profile: str, active_sm: int) -> tuple[int, str]:
    return run(
        [
            binary,
            "--gpu-list",
            "0",
            "--mode",
            "shared_mma",
            "--w-sm-kib",
            "64",
            "--blocks-per-sm",
            "16",
            "--target-profile",
            profile,
            "--active-sm",
            str(active_sm),
            "--dry-run",
        ]
    )


def markdown_report(
    gpu: int,
    target_profile: str,
    detected_profile: str | None,
    gpu_info: dict[str, str],
    profile: dict[str, Any],
    ncu_info: dict[str, str],
    dry_run: tuple[int, str],
) -> str:
    lines: list[str] = []
    lines.append("# GPU Support Preflight")
    lines.append("")
    lines.append(f"- Date: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- GPU index: {gpu}")
    lines.append(f"- Requested profile: `{target_profile}`")
    lines.append(f"- Detected profile: `{detected_profile or 'unknown'}`")
    lines.append("")
    lines.append("## GPU")
    lines.append("")
    for key in [
        "index",
        "name",
        "uuid",
        "driver_version",
        "compute_cap",
        "power.draw",
        "power.limit",
        "clocks.sm",
        "clocks.mem",
        "query_error",
    ]:
        if key in gpu_info:
            lines.append(f"- `{key}`: {gpu_info[key]}")
    lines.append("")
    lines.append("## Selected Harness Profile")
    lines.append("")
    for key in [
        "cc",
        "cuda_arch",
        "full_sm",
        "l2_mib",
        "shared_kib",
        "max_blocks_per_sm",
        "ncu_chip",
        "power_usage_semantics",
        "ncu_policy",
    ]:
        lines.append(f"- `{key}`: {profile[key]}")
    lines.append("")
    lines.append("## Nsight Compute")
    lines.append("")
    for key in [
        "version_rc",
        "version",
        "list_chips_rc",
        "chip_supported",
        "query_metrics_rc",
        "query_metrics_ok",
        "list_chips_error",
        "query_metrics_error",
    ]:
        if key in ncu_info:
            value = ncu_info[key].replace("\n", " ")
            lines.append(f"- `{key}`: {value}")
    lines.append("")
    lines.append("## Binary Dry Run")
    lines.append("")
    lines.append(f"- `return_code`: {dry_run[0]}")
    lines.append("")
    lines.append("```text")
    lines.append(dry_run[1])
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--target-profile", default="auto", choices=["auto", *sorted(PROFILES)])
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--ncu", default="ncu")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    gpu_info = query_gpu(args.gpu)
    detected = None
    if "query_error" not in gpu_info:
        detected = detect_profile(gpu_info.get("name", ""), gpu_info.get("compute_cap", ""))

    selected = detected if args.target_profile == "auto" else args.target_profile
    if not selected or selected not in PROFILES:
        raise SystemExit(
            "could not select a supported profile; pass --target-profile explicitly"
        )
    profile = PROFILES[selected]
    ncu_info = query_ncu(args.ncu, profile["ncu_chip"])
    dry = dry_run_binary(args.binary, selected, profile["full_sm"])
    report = markdown_report(
        args.gpu, args.target_profile, detected, gpu_info, profile, ncu_info, dry
    )

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(report)
    return 0 if dry[0] == 0 else dry[0]


if __name__ == "__main__":
    raise SystemExit(main())
