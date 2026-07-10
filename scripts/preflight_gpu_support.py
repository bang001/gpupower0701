#!/usr/bin/env python3
"""Preflight support checks for the multi-GPU FP16 energy harness."""

from __future__ import annotations

import argparse
import datetime as dt
import shlex
import subprocess
from pathlib import Path
from typing import Any


POWER_DETAIL_KEYWORDS = (
    "power readings",
    "module power",
    "gpu memory power",
    "power draw",
    "power limit",
    "base power",
    "ceiling power",
    "power smoothing",
    "current tmp",
)


PROFILES: dict[str, dict[str, Any]] = {
    "v100": {
        "aliases": ["v100", "tesla v100"],
        "cc": "7.0",
        "cuda_arch": "70",
        "full_sm": 80,
        "l2_mib": 6,
        "combined_l1_shared_kib": 128,
        "shared_kib": 96,
        "max_shared_per_block_kib": 96,
        "max_blocks_per_sm": 32,
        "ncu_chip": "gv100",
        "ncu_policy": "Nsight Compute 2024.3 is confirmed to support GV100. Always require --list-chips and --query-metrics --chips gv100 success because newer releases can remove Volta support.",
        "cuda_toolchain_policy": "Use a compiler that lists compute_70. CUDA 12.x is the recommended V100 build line; CUDA 13 removed Volta offline compilation support.",
        "power_usage_semantics": "instant",
        "reference_memory": "32 GB HBM2 reference package; pass --min-device-memory-mib 0 for a separately reported 16 GB SKU.",
    },
    "rtx3090": {
        "aliases": ["rtx 3090", "geforce rtx 3090", "3090"],
        "cc": "8.6",
        "cuda_arch": "86",
        "full_sm": 82,
        "l2_mib": 6,
        "combined_l1_shared_kib": 128,
        "shared_kib": 100,
        "max_shared_per_block_kib": 99,
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
        "combined_l1_shared_kib": 192,
        "shared_kib": 164,
        "max_shared_per_block_kib": 163,
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
        "combined_l1_shared_kib": 256,
        "shared_kib": 228,
        "max_shared_per_block_kib": 227,
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


def query_gpu_fields(gpu: int, fields: list[str]) -> tuple[int, dict[str, str], str]:
    rc, out = run(
        [
            "nvidia-smi",
            f"--id={gpu}",
            f"--query-gpu={','.join(fields)}",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0:
        return rc, {}, out
    values = split_csv_line(out.splitlines()[0])
    return rc, dict(zip(fields, values)), ""


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
    base_fields = [
        "index",
        "name",
        "uuid",
        "driver_version",
        "compute_cap",
        "memory.total",
        "power.draw",
        "power.limit",
        "clocks.sm",
        "clocks.mem",
        "temperature.gpu",
        "ecc.mode.current",
    ]
    extended_fields = [
        "index",
        "name",
        "uuid",
        "driver_version",
        "compute_cap",
        "memory.total",
        "power.draw",
        "power.draw.average",
        "power.draw.instant",
        "power.limit",
        "clocks.sm",
        "clocks.mem",
        "temperature.gpu",
        "ecc.mode.current",
    ]

    fields = extended_fields
    rc, result, error = query_gpu_fields(gpu, fields)
    if rc != 0:
        fields = base_fields
        rc, result, error = query_gpu_fields(gpu, fields)
    if rc != 0:
        return {"query_error": error}
    result["power_query_fields"] = "extended" if fields == extended_fields else "base"
    return result


def query_power_scope(gpu: int) -> dict[str, str]:
    """Collect non-fatal nvidia-smi power-scope metadata for reports.

    The component coefficient numerator is still the harness NVML energy CSV.
    This preflight output only records whether the platform exposes GPU,
    module, and memory power scopes that must not be mixed later.
    """

    result: dict[str, str] = {}

    module_fields = [
        "module.power.draw.average",
        "module.power.draw.instant",
        "module.power.limit",
        "module.enforced.power.limit",
    ]
    rc, values, error = query_gpu_fields(gpu, module_fields)
    result["module_power_query_rc"] = str(rc)
    if rc == 0:
        for key, value in values.items():
            result[key] = value
    else:
        result["module_power_query_status"] = "unsupported_or_unavailable"
        result["module_power_query_error"] = error[:500]

    rc, out = run(["nvidia-smi", "-i", str(gpu), "-q", "-d", "POWER"])
    result["power_detail_query_rc"] = str(rc)
    if rc == 0:
        excerpt: list[str] = []
        for line in out.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if any(keyword in lowered for keyword in POWER_DETAIL_KEYWORDS):
                excerpt.append(stripped)
        result["power_detail_excerpt"] = "\n".join(excerpt[:80])
    else:
        result["power_detail_query_error"] = out[:500]
    return result


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


def query_cuda_compiler(nvcc: str, cuda_arch: str) -> dict[str, str]:
    """Check that the selected nvcc can emit code for the profile architecture."""

    nvcc_cmd = shlex.split(nvcc)
    target = f"compute_{cuda_arch}"
    result: dict[str, str] = {"target": target}

    rc, out = run(nvcc_cmd + ["--version"])
    result["version_rc"] = str(rc)
    result["version"] = out.replace("\n", " | ")[:1000]

    rc, out = run(nvcc_cmd + ["--list-gpu-arch"])
    result["list_gpu_arch_rc"] = str(rc)
    result["target_supported"] = "unknown"
    if rc == 0:
        supported = {line.strip() for line in out.splitlines() if line.strip()}
        result["target_supported"] = str(target in supported).lower()
        result["supported_arches"] = ",".join(sorted(supported))
    else:
        result["list_gpu_arch_error"] = out[:1000]
    return result


def dry_run_binary(binary: str, gpu: int, profile: str, active_sm: int) -> tuple[int, str]:
    return run(
        [
            binary,
            "--gpu-list",
            str(gpu),
            "--mode",
            "shared_scalar_load_only",
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


def strict_gate_errors(
    *,
    requested_profile: str,
    detected_profile: str | None,
    gpu_info: dict[str, str],
    ncu_info: dict[str, str],
    cuda_compiler_info: dict[str, str] | None,
    dry_run: tuple[int, str],
    min_device_memory_mib: int = 0,
) -> list[str]:
    errors: list[str] = []
    if requested_profile == "auto":
        if "query_error" in gpu_info:
            errors.append("gpu_query_failed")
        if not detected_profile:
            errors.append("detected_profile_unknown")
    else:
        if "query_error" in gpu_info:
            errors.append("gpu_query_failed")
        elif not detected_profile:
            errors.append("detected_profile_unknown")
        elif detected_profile != requested_profile:
            errors.append(
                f"profile_mismatch_requested_{requested_profile}_detected_{detected_profile}"
            )

    if ncu_info.get("chip_supported") != "true":
        errors.append(f"ncu_chip_not_supported_{ncu_info.get('chip_supported', 'missing')}")
    if ncu_info.get("query_metrics_ok") != "true":
        errors.append(f"ncu_query_metrics_not_ok_{ncu_info.get('query_metrics_rc', 'missing')}")
    if (
        cuda_compiler_info is not None
        and cuda_compiler_info.get("target_supported") != "true"
    ):
        errors.append(
            "nvcc_target_not_supported_"
            f"{cuda_compiler_info.get('target', 'unknown')}_"
            f"{cuda_compiler_info.get('target_supported', 'missing')}"
        )
    if dry_run[0] != 0:
        errors.append(f"binary_dry_run_failed_rc_{dry_run[0]}")
    if min_device_memory_mib > 0:
        try:
            observed_memory_mib = float(gpu_info.get("memory.total", ""))
        except ValueError:
            errors.append("gpu_memory_total_unavailable")
        else:
            if observed_memory_mib < min_device_memory_mib:
                errors.append(
                    "gpu_memory_total_below_min_"
                    f"{min_device_memory_mib}_mib_observed_{observed_memory_mib:g}_mib"
                )
    return errors


def assert_selftest(condition: bool, name: str, detail: str = "") -> None:
    if not condition:
        suffix = f": {detail}" if detail else ""
        raise AssertionError(f"{name} failed{suffix}")


def run_self_test() -> None:
    good_ncu = {
        "chip_supported": "true",
        "query_metrics_ok": "true",
        "query_metrics_rc": "0",
    }
    good_gpu = {
        "name": "NVIDIA A100",
        "compute_cap": "8.0",
        "memory.total": "40960",
    }
    no_errors = strict_gate_errors(
        requested_profile="a100",
        detected_profile="a100",
        gpu_info=good_gpu,
        ncu_info=good_ncu,
        cuda_compiler_info={"target": "compute_80", "target_supported": "true"},
        dry_run=(0, "dry_run=true"),
        min_device_memory_mib=30000,
    )
    assert_selftest(not no_errors, "strict_good_profile", ";".join(no_errors))

    mismatch = strict_gate_errors(
        requested_profile="a100",
        detected_profile="rtx3090",
        gpu_info={"name": "NVIDIA GeForce RTX 3090", "compute_cap": "8.6"},
        ncu_info=good_ncu,
        cuda_compiler_info=None,
        dry_run=(0, "dry_run=true"),
    )
    assert_selftest(
        "profile_mismatch_requested_a100_detected_rtx3090" in mismatch,
        "strict_profile_mismatch",
        ";".join(mismatch),
    )

    auto_unknown = strict_gate_errors(
        requested_profile="auto",
        detected_profile=None,
        gpu_info={"name": "Unknown GPU", "compute_cap": "9.9"},
        ncu_info=good_ncu,
        cuda_compiler_info=None,
        dry_run=(0, "dry_run=true"),
    )
    assert_selftest(
        "detected_profile_unknown" in auto_unknown,
        "strict_auto_unknown_profile",
        ";".join(auto_unknown),
    )

    ncu_bad = strict_gate_errors(
        requested_profile="v100",
        detected_profile="v100",
        gpu_info={"name": "Tesla V100", "compute_cap": "7.0"},
        ncu_info={
            "chip_supported": "false",
            "query_metrics_ok": "false",
            "query_metrics_rc": "1",
        },
        cuda_compiler_info=None,
        dry_run=(0, "dry_run=true"),
    )
    assert_selftest(
        "ncu_chip_not_supported_false" in ncu_bad
        and "ncu_query_metrics_not_ok_1" in ncu_bad,
        "strict_ncu_failure",
        ";".join(ncu_bad),
    )

    dry_bad = strict_gate_errors(
        requested_profile="h100",
        detected_profile="h100",
        gpu_info={"name": "NVIDIA H100", "compute_cap": "9.0"},
        ncu_info=good_ncu,
        cuda_compiler_info=None,
        dry_run=(2, "invalid combination"),
    )
    assert_selftest(
        "binary_dry_run_failed_rc_2" in dry_bad,
        "strict_dry_run_failure",
        ";".join(dry_bad),
    )

    v100_16gb = strict_gate_errors(
        requested_profile="v100",
        detected_profile="v100",
        gpu_info={
            "name": "Tesla V100",
            "compute_cap": "7.0",
            "memory.total": "16160",
        },
        ncu_info=good_ncu,
        cuda_compiler_info=None,
        dry_run=(0, "dry_run=true"),
        min_device_memory_mib=30000,
    )
    assert_selftest(
        any(error.startswith("gpu_memory_total_below_min_30000_mib") for error in v100_16gb),
        "strict_v100_32gb_memory_gate",
        ";".join(v100_16gb),
    )

    v100_cuda13 = strict_gate_errors(
        requested_profile="v100",
        detected_profile="v100",
        gpu_info={"name": "Tesla V100", "compute_cap": "7.0"},
        ncu_info=good_ncu,
        cuda_compiler_info={
            "target": "compute_70",
            "target_supported": "false",
        },
        dry_run=(0, "dry_run=true"),
    )
    assert_selftest(
        "nvcc_target_not_supported_compute_70_false" in v100_cuda13,
        "strict_v100_nvcc_arch_gate",
        ";".join(v100_cuda13),
    )

    report = markdown_report(
        gpu=0,
        target_profile="a100",
        detected_profile="rtx3090",
        strict=True,
        strict_errors=mismatch,
        dry_run_active_sm=108,
        gpu_info={"name": "NVIDIA GeForce RTX 3090", "compute_cap": "8.6"},
        power_scope={},
        profile=PROFILES["a100"],
        ncu_info=good_ncu,
        cuda_compiler_info={
            "target": "compute_80",
            "target_supported": "true",
        },
        dry_run=(0, "dry_run=true"),
        min_device_memory_mib=0,
    )
    assert_selftest(
        "- `strict`: true" in report
        and "- `overall`: fail" in report
        and "profile_mismatch_requested_a100_detected_rtx3090" in report,
        "strict_markdown_verdict",
    )

    print("preflight strict gate self-test passed")


def markdown_report(
    gpu: int,
    target_profile: str,
    detected_profile: str | None,
    strict: bool,
    strict_errors: list[str],
    dry_run_active_sm: int,
    gpu_info: dict[str, str],
    power_scope: dict[str, str],
    profile: dict[str, Any],
    ncu_info: dict[str, str],
    cuda_compiler_info: dict[str, str],
    dry_run: tuple[int, str],
    min_device_memory_mib: int,
) -> str:
    lines: list[str] = []
    lines.append("# GPU Support Preflight")
    lines.append("")
    lines.append(f"- Date: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- GPU index: {gpu}")
    lines.append(f"- Requested profile: `{target_profile}`")
    lines.append(f"- Detected profile: `{detected_profile or 'unknown'}`")
    lines.append("")
    lines.append("## Preflight Verdict")
    lines.append("")
    profile_errors = [
        error
        for error in strict_errors
        if error.startswith("gpu_query")
        or error.startswith("detected_profile")
        or error.startswith("profile_mismatch")
    ]
    memory_errors = [error for error in strict_errors if error.startswith("gpu_memory")]
    ncu_errors = [error for error in strict_errors if error.startswith("ncu_")]
    compiler_errors = [error for error in strict_errors if error.startswith("nvcc_")]
    dry_errors = [error for error in strict_errors if error.startswith("binary_dry_run")]
    lines.append(f"- `strict`: {str(strict).lower()}")
    lines.append(f"- `profile_gate`: {'pass' if not profile_errors else 'fail'}")
    lines.append(f"- `device_memory_gate`: {'pass' if not memory_errors else 'fail'}")
    lines.append(f"- `ncu_gate`: {'pass' if not ncu_errors else 'fail'}")
    lines.append(f"- `cuda_compiler_gate`: {'pass' if not compiler_errors else 'fail'}")
    lines.append(f"- `dry_run_gate`: {'pass' if not dry_errors else 'fail'}")
    lines.append(
        f"- `overall`: {'pass' if not strict_errors else 'fail' if strict else 'warning'}"
    )
    lines.append(
        f"- `errors`: {'none' if not strict_errors else ';'.join(strict_errors)}"
    )
    lines.append("")
    lines.append("## GPU")
    lines.append("")
    for key in [
        "index",
        "name",
        "uuid",
        "driver_version",
        "compute_cap",
        "memory.total",
        "power.draw",
        "power.draw.average",
        "power.draw.instant",
        "power.limit",
        "clocks.sm",
        "clocks.mem",
        "temperature.gpu",
        "ecc.mode.current",
        "power_query_fields",
        "query_error",
    ]:
        if key in gpu_info:
            lines.append(f"- `{key}`: {gpu_info[key]}")
    lines.append("")
    lines.append("## Power Scope")
    lines.append("")
    lines.append(
        "The final component-energy numerator must come from the harness raw "
        "CSV, preferably `nvml_total_energy`. The fields below are preflight "
        "metadata for distinguishing GPU/device, module, and memory power "
        "scopes; do not mix module or memory power into component coefficients."
    )
    lines.append("")
    for key in [
        "module_power_query_rc",
        "module.power.draw.average",
        "module.power.draw.instant",
        "module.power.limit",
        "module.enforced.power.limit",
        "module_power_query_status",
        "module_power_query_error",
        "power_detail_query_rc",
        "power_detail_query_error",
    ]:
        if key in power_scope:
            value = power_scope[key].replace("\n", " ")
            lines.append(f"- `{key}`: {value}")
    if power_scope.get("power_detail_excerpt"):
        lines.append("")
        lines.append("```text")
        lines.append(power_scope["power_detail_excerpt"])
        lines.append("```")
    lines.append("")
    lines.append("## Selected Harness Profile")
    lines.append("")
    for key in [
        "cc",
        "cuda_arch",
        "full_sm",
        "l2_mib",
        "combined_l1_shared_kib",
        "shared_kib",
        "max_shared_per_block_kib",
        "max_blocks_per_sm",
        "ncu_chip",
        "power_usage_semantics",
        "ncu_policy",
        "cuda_toolchain_policy",
        "reference_memory",
    ]:
        lines.append(f"- `{key}`: {profile.get(key, 'not_applicable')}")
    lines.append(f"- `dry_run_gpu`: {gpu}")
    lines.append(f"- `dry_run_active_sm`: {dry_run_active_sm}")
    lines.append(f"- `min_device_memory_mib`: {min_device_memory_mib}")
    lines.append("")
    lines.append("## CUDA Compiler")
    lines.append("")
    for key in [
        "target",
        "target_supported",
        "version_rc",
        "version",
        "list_gpu_arch_rc",
        "supported_arches",
        "list_gpu_arch_error",
    ]:
        if key in cuda_compiler_info:
            lines.append(f"- `{key}`: {cuda_compiler_info[key]}")
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
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--target-profile", default="auto", choices=["auto", *sorted(PROFILES)])
    parser.add_argument("--binary", default="./build/a100_fp16_energy_v2")
    parser.add_argument("--ncu", default="ncu")
    parser.add_argument(
        "--nvcc",
        default="nvcc",
        help="CUDA compiler command whose supported GPU architectures are checked.",
    )
    parser.add_argument(
        "--min-device-memory-mib",
        type=int,
        default=0,
        help=(
            "Require this much visible device memory in strict preflight. "
            "Use 30000 for the V100 32 GB reference package; use 0 for no SKU-capacity gate."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit nonzero if the requested profile does not match the detected GPU, "
            "CUDA compiler target or NCU chip/metric support is unavailable, "
            "or binary dry-run fails."
        ),
    )
    parser.add_argument(
        "--active-sm",
        type=int,
        default=0,
        help=(
            "Active SM count used by the binary dry-run. Defaults to the full "
            "profile count; pass the runtime/preflight value for MIG or "
            "partitioned nodes."
        ),
    )
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in strict preflight gate regression checks and exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

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
    dry_run_active_sm = args.active_sm or profile["full_sm"]
    power_scope = query_power_scope(args.gpu)
    ncu_info = query_ncu(args.ncu, profile["ncu_chip"])
    cuda_compiler_info = query_cuda_compiler(args.nvcc, profile["cuda_arch"])
    dry = dry_run_binary(args.binary, args.gpu, selected, dry_run_active_sm)
    strict_errors = strict_gate_errors(
        requested_profile=args.target_profile,
        detected_profile=detected,
        gpu_info=gpu_info,
        ncu_info=ncu_info,
        cuda_compiler_info=cuda_compiler_info,
        dry_run=dry,
        min_device_memory_mib=args.min_device_memory_mib,
    )
    report = markdown_report(
        args.gpu,
        args.target_profile,
        detected,
        args.strict,
        strict_errors,
        dry_run_active_sm,
        gpu_info,
        power_scope,
        profile,
        ncu_info,
        cuda_compiler_info,
        dry,
        args.min_device_memory_mib,
    )

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(report)
    if args.strict and strict_errors:
        print("strict preflight failed: " + ";".join(strict_errors))
        return dry[0] if dry[0] != 0 else 2
    return 0 if dry[0] == 0 else dry[0]


if __name__ == "__main__":
    raise SystemExit(main())
