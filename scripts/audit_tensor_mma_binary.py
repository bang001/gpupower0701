#!/usr/bin/env python3
"""Audit compiled Tensor treatment/control kernels with cuobjdump.

Static SASS proves opcode presence and resource shape. Runtime NCU counters are
still required to prove how often those opcodes execute for each RF coordinate.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FIXED_REUSE_FACTORS = (1, 2, 4, 8, 16)
MODE_PATTERNS = {
    "reg_mma": re.compile(r"reg_mma_kernelILi(\d+)EEE"),
    "reg_operand_only": re.compile(r"reg_operand_only_kernelILi(\d+)EEE"),
}
RESOURCE_PATTERN = re.compile(
    r"REG:(?P<registers>\d+)\s+STACK:(?P<stack>\d+)\s+"
    r"SHARED:(?P<shared>\d+)\s+LOCAL:(?P<local>\d+)"
)
OPCODE_PATTERNS = {
    "hmma_static": re.compile(r"\bHMMA(?:\.|\b)"),
    "wgmma_static": re.compile(r"\bWGMMA(?:\.|\b)"),
    "tma_static": re.compile(r"\b(?:UTMA|TMA)(?:\.|\b)"),
    "ldg_static": re.compile(r"\bLDG(?:\.|\b)"),
    "lds_static": re.compile(r"\bLDS(?:\.|\b)"),
    "ldl_static": re.compile(r"\bLDL(?:\.|\b)"),
    "stl_static": re.compile(r"\bSTL(?:\.|\b)"),
}
SASS_ADDRESS_PATTERN = re.compile(r"/\*(?P<address>[0-9a-fA-F]+)\*/")
BRANCH_TARGET_PATTERN = re.compile(r"\bBRA\s+0x(?P<target>[0-9a-fA-F]+)\b")
RUNTIME_TOKEN_PATTERN = re.compile(
    r"\b(?:CS2R|S2R|S2UR)\b[^\n]*\bSR_CLOCKLO\b"
)


def find_cuobjdump(explicit: str = "") -> str:
    if explicit:
        resolved = shutil.which(explicit)
        return resolved or explicit

    resolved = shutil.which("cuobjdump")
    if resolved:
        return resolved

    candidates: list[Path] = []
    for env_name in ("CUDA_HOME", "CUDA_PATH", "CUDAToolkit_ROOT", "CONDA_PREFIX"):
        root = os.environ.get(env_name, "").strip()
        if root:
            candidates.append(Path(root) / "bin" / "cuobjdump")

    nvcc = os.environ.get("NVCC", "").strip() or shutil.which("nvcc") or ""
    if nvcc and " " not in nvcc:
        candidates.append(Path(nvcc).resolve().parent / "cuobjdump")

    prefix = Path(sys.prefix)
    candidates.extend(
        [
            prefix / "bin" / "cuobjdump",
            prefix / "targets" / "x86_64-linux" / "bin" / "cuobjdump",
        ]
    )
    candidates.extend(
        sorted(
            prefix.glob(
                "lib/python*/site-packages/triton/backends/nvidia/bin/cuobjdump"
            )
        )
    )
    candidates.extend(
        sorted(
            prefix.glob(
                "lib/python*/site-packages/triton/third_party/cuda/bin/cuobjdump"
            )
        )
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return ""


def count_backward_branches(sass: str) -> int:
    count = 0
    for line in sass.splitlines():
        address_match = SASS_ADDRESS_PATTERN.search(line)
        target_match = BRANCH_TARGET_PATTERN.search(line)
        if not address_match or not target_match:
            continue
        address = int(address_match.group("address"), 16)
        target = int(target_match.group("target"), 16)
        if target < address:
            count += 1
    return count


def count_runtime_observed_backward_loops(sass: str) -> int:
    token_addresses: list[int] = []
    branches: list[tuple[int, int]] = []
    for line in sass.splitlines():
        address_match = SASS_ADDRESS_PATTERN.search(line)
        if not address_match:
            continue
        address = int(address_match.group("address"), 16)
        if RUNTIME_TOKEN_PATTERN.search(line):
            token_addresses.append(address)
        target_match = BRANCH_TARGET_PATTERN.search(line)
        if target_match:
            target = int(target_match.group("target"), 16)
            if target < address:
                branches.append((target, address))
    return sum(
        1
        for target, branch_address in branches
        if any(target <= token < branch_address for token in token_addresses)
    )


def run_cuobjdump(cuobjdump: str, binary: str, option: str) -> str:
    result = subprocess.run(
        [cuobjdump, option, binary],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cuobjdump {option} failed with rc={result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def parse_resource_usage(text: str) -> dict[str, dict[str, int]]:
    resources: dict[str, dict[str, int]] = {}
    symbol = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Function ") and stripped.endswith(":"):
            symbol = stripped[len("Function ") : -1]
            continue
        if not symbol:
            continue
        match = RESOURCE_PATTERN.search(stripped)
        if match:
            resources[symbol] = {
                key: int(value) for key, value in match.groupdict().items()
            }
            symbol = ""
    return resources


def parse_sass_functions(text: str) -> dict[str, str]:
    functions: dict[str, list[str]] = {}
    symbol = ""
    for line in text.splitlines():
        match = re.search(r"Function\s*:\s*(\S+)", line)
        if match:
            symbol = match.group(1)
            functions.setdefault(symbol, [])
            continue
        if symbol:
            functions[symbol].append(line)
    return {name: "\n".join(lines) for name, lines in functions.items()}


def mode_and_rf(symbol: str) -> tuple[str, int] | None:
    for mode, pattern in MODE_PATTERNS.items():
        match = pattern.search(symbol)
        if match:
            return mode, int(match.group(1))
    return None


def build_rows(
    *, profile: str, binary: str, resources_text: str, sass_text: str
) -> list[dict[str, str]]:
    resources = parse_resource_usage(resources_text)
    sass_functions = parse_sass_functions(sass_text)
    symbols: dict[tuple[str, int], str] = {}
    for symbol in set(resources) | set(sass_functions):
        parsed = mode_and_rf(symbol)
        if parsed and parsed[1] in FIXED_REUSE_FACTORS:
            symbols[parsed] = symbol

    rows: list[dict[str, str]] = []
    for reuse_factor in FIXED_REUSE_FACTORS:
        for mode in ("reg_mma", "reg_operand_only"):
            symbol = symbols.get((mode, reuse_factor), "")
            resource = resources.get(symbol, {})
            sass = sass_functions.get(symbol, "")
            counts = {
                name: len(pattern.findall(sass))
                for name, pattern in OPCODE_PATTERNS.items()
            }
            counts["hmma_predicated_static"] = sum(
                1
                for line in sass.splitlines()
                if "HMMA" in line
                and re.search(r"@[!]?P\d+\s+HMMA(?:\.|\b)", line)
            )
            counts["backward_branch_static"] = count_backward_branches(sass)
            counts["runtime_token_static"] = len(
                RUNTIME_TOKEN_PATTERN.findall(sass)
            )
            counts["runtime_token_loop_static"] = (
                count_runtime_observed_backward_loops(sass)
            )
            reasons: list[str] = []
            if not symbol:
                reasons.append("kernel_symbol_missing")
            if not resource:
                reasons.append("resource_usage_missing")
            if not sass:
                reasons.append("sass_missing")
            if mode == "reg_mma":
                if counts["hmma_static"] <= 0:
                    reasons.append("hmma_missing_in_treatment")
                if counts["hmma_predicated_static"] > 0:
                    reasons.append("predicated_hmma_path_present")
                if counts["wgmma_static"] > 0 or counts["tma_static"] > 0:
                    reasons.append("unexpected_wgmma_or_tma_in_wmma_mode")
                if counts["runtime_token_loop_static"] <= 0:
                    reasons.append("runtime_token_loop_missing_in_treatment")
            else:
                if (
                    counts["hmma_static"] > 0
                    or counts["wgmma_static"] > 0
                    or counts["tma_static"] > 0
                ):
                    reasons.append("tensor_opcode_present_in_control")
                if counts["backward_branch_static"] <= 0:
                    reasons.append("control_loop_missing_after_ptxas")
                if counts["runtime_token_loop_static"] <= 0:
                    reasons.append("runtime_token_loop_missing_in_control")
            if resource.get("local", -1) != 0 or resource.get("stack", -1) != 0:
                reasons.append("local_or_stack_allocation_present")
            if counts["ldl_static"] > 0 or counts["stl_static"] > 0:
                reasons.append("local_memory_instruction_present")
            if counts["ldg_static"] > 0 or counts["lds_static"] > 0:
                reasons.append("memory_operand_load_present")

            rows.append(
                {
                    "profile": profile,
                    "binary": binary,
                    "mode": mode,
                    "reuse_factor": str(reuse_factor),
                    "symbol": symbol,
                    "registers_per_thread": str(resource.get("registers", "")),
                    "stack_bytes": str(resource.get("stack", "")),
                    "local_bytes": str(resource.get("local", "")),
                    "shared_bytes_static": str(resource.get("shared", "")),
                    **{name: str(value) for name, value in counts.items()},
                    "instruction_api_scope": "wmma_m16n16k16_f16_f32",
                    "lowering_scope": "architecture_lowered_hmma_compatibility",
                    "static_count_semantics": "presence_only_not_runtime_execution_count",
                    "status": "pass" if not reasons else "fail",
                    "reasons": ";".join(reasons) if reasons else "pass",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = rows[0]["profile"] if rows else "unknown"
    binary = rows[0]["binary"] if rows else "unknown"
    by_key = {(row["reuse_factor"], row["mode"]): row for row in rows}
    all_pass = bool(rows) and all(row["status"] == "pass" for row in rows)
    with path.open("w", encoding="utf-8") as out:
        out.write("# Tensor MMA Binary Audit\n\n")
        out.write(f"- profile: `{profile}`\n")
        out.write(f"- binary: `{binary}`\n")
        out.write(f"- verdict: `{'pass' if all_pass else 'fail'}`\n")
        out.write("- API scope: `wmma::mma_sync m16n16k16 FP16 input / FP32 accumulate`\n")
        out.write("- expected lowering: architecture-specific `HMMA` compatibility path\n\n")
        out.write(
            "Static SASS counts only prove that an opcode exists in a compiled kernel. "
            "They do not equal runtime instruction counts. NCU must separately prove "
            "HMMA/logical-MMA linearity across RF and zero HMMA in the control.\n\n"
        )
        out.write(
            "| RF | treatment HMMA | control HMMA | treatment/control registers/thread | "
            "predicated treatment HMMA | runtime-token loops treatment/control | "
            "control backward branches | WGMMA/TMA | LDG/LDS treatment | "
            "local treatment/control | status |\n"
        )
        out.write("|---:|---:|---:|---|---:|---|---:|---|---|---|---|\n")
        for rf in FIXED_REUSE_FACTORS:
            treatment = by_key.get((str(rf), "reg_mma"), {})
            control = by_key.get((str(rf), "reg_operand_only"), {})
            statuses = {treatment.get("status", "fail"), control.get("status", "fail")}
            out.write(
                f"| {rf} | {treatment.get('hmma_static', '')} | "
                f"{control.get('hmma_static', '')} | "
                f"{treatment.get('registers_per_thread', '')}/"
                f"{control.get('registers_per_thread', '')} | "
                f"{treatment.get('hmma_predicated_static', '')} | "
                f"{treatment.get('runtime_token_loop_static', '')}/"
                f"{control.get('runtime_token_loop_static', '')} | "
                f"{control.get('backward_branch_static', '')} | "
                f"{treatment.get('wgmma_static', '')}/"
                f"{treatment.get('tma_static', '')} | "
                f"{treatment.get('ldg_static', '')}/"
                f"{treatment.get('lds_static', '')} | "
                f"{treatment.get('local_bytes', '')}/"
                f"{control.get('local_bytes', '')} | "
                f"{'pass' if statuses == {'pass'} else 'fail'} |\n"
            )
        out.write("\n## Interpretation\n\n")
        out.write(
            "A register-footprint difference is expected in the current implementation: "
            "the treatment keeps WMMA operand and accumulator fragments live, while ptxas "
            "reduces the no-MMA control. Therefore the measured coefficient is the "
            "incremental effective board-level WMMA/HMMA plus its register/scheduler path, "
            "not pure Tensor Core circuit energy and not an isolated register coefficient.\n"
        )


def run_self_test() -> None:
    resource = """
 Function xxxreg_mma_kernelILi1EEEfoo:
  REG:32 STACK:0 SHARED:0 LOCAL:0 CONSTANT[0]:10
 Function xxxreg_operand_only_kernelILi1EEEfoo:
  REG:16 STACK:0 SHARED:0 LOCAL:0 CONSTANT[0]:10
"""
    sass = """
 Function : xxxreg_mma_kernelILi1EEEfoo
 /*0000*/ CS2R R8, SR_CLOCKLO;
 /*0010*/ HMMA.16816.F32 R0, R2, R4, R0;
 /*0020*/ BRA 0x0;
 Function : xxxreg_operand_only_kernelILi1EEEfoo
 /*0000*/ CS2R R8, SR_CLOCKLO;
 /*0010*/ IADD3 R0, R0, R1, RZ;
 /*0020*/ BRA 0x0;
"""
    resources = parse_resource_usage(resource)
    functions = parse_sass_functions(sass)
    assert resources["xxxreg_mma_kernelILi1EEEfoo"]["registers"] == 32
    assert "HMMA.16816" in functions["xxxreg_mma_kernelILi1EEEfoo"]
    rows = build_rows(
        profile="selftest", binary="selftest.bin", resources_text=resource, sass_text=sass
    )
    rf1_treatment = next(
        row for row in rows if row["mode"] == "reg_mma" and row["reuse_factor"] == "1"
    )
    rf1_control = next(
        row
        for row in rows
        if row["mode"] == "reg_operand_only" and row["reuse_factor"] == "1"
    )
    assert rf1_treatment["status"] == "pass"
    assert rf1_control["status"] == "pass"
    assert rf1_treatment["hmma_static"] == "1"
    assert rf1_treatment["hmma_predicated_static"] == "0"
    assert rf1_control["hmma_static"] == "0"
    assert rf1_control["backward_branch_static"] == "1"
    assert rf1_treatment["runtime_token_loop_static"] == "1"
    assert rf1_control["runtime_token_loop_static"] == "1"
    assert all(
        row["status"] == "fail" for row in rows if row["reuse_factor"] != "1"
    )
    predicated = sass.replace(
        "/*0010*/ HMMA.16816.F32",
        "/*0010*/ @P0 HMMA.16816.F32",
    )
    predicated_rows = build_rows(
        profile="selftest",
        binary="selftest.bin",
        resources_text=resource,
        sass_text=predicated,
    )
    predicated_treatment = next(
        row
        for row in predicated_rows
        if row["mode"] == "reg_mma" and row["reuse_factor"] == "1"
    )
    assert predicated_treatment["status"] == "fail"
    assert "predicated_hmma_path_present" in predicated_treatment["reasons"]
    missing_token_rows = build_rows(
        profile="selftest",
        binary="selftest.bin",
        resources_text=resource,
        sass_text=sass.replace("CS2R R8, SR_CLOCKLO;", "MOV R8, RZ;"),
    )
    missing_token_control = next(
        row
        for row in missing_token_rows
        if row["mode"] == "reg_operand_only" and row["reuse_factor"] == "1"
    )
    assert missing_token_control["status"] == "fail"
    assert "runtime_token_loop_missing_in_control" in missing_token_control["reasons"]
    print("Tensor MMA binary audit self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary")
    parser.add_argument("--profile", default="auto")
    parser.add_argument("--cuobjdump", default="")
    parser.add_argument("--out-csv", default="results/summary/tensor_mma_binary_audit.csv")
    parser.add_argument("--out-md", default="results/summary/tensor_mma_binary_audit.md")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if not args.binary:
        parser.error("--binary is required")
    binary = Path(args.binary)
    if not binary.exists():
        parser.error(f"binary does not exist: {binary}")
    cuobjdump = find_cuobjdump(args.cuobjdump)
    if not cuobjdump:
        parser.error("cuobjdump was not found; pass --cuobjdump")
    print(f"cuobjdump: {cuobjdump}")

    resources_text = run_cuobjdump(cuobjdump, str(binary), "--dump-resource-usage")
    sass_text = run_cuobjdump(cuobjdump, str(binary), "--dump-sass")
    rows = build_rows(
        profile=args.profile,
        binary=str(binary),
        resources_text=resources_text,
        sass_text=sass_text,
    )
    write_csv(Path(args.out_csv), rows)
    write_markdown(Path(args.out_md), rows)
    failed = [row for row in rows if row["status"] != "pass"]
    print(f"rows: {len(rows)}")
    print(f"failed: {len(failed)}")
    print(f"wrote csv: {args.out_csv}")
    print(f"wrote markdown: {args.out_md}")
    for row in failed:
        print(
            "Tensor binary audit failed row: "
            f"mode={row['mode']} RF={row['reuse_factor']} "
            f"symbol={row['symbol'] or 'missing'} reasons={row['reasons']}",
            file=sys.stderr,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
