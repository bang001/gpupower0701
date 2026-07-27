#!/usr/bin/env python3
"""Audit the sm86 lowering contract of the whole-Softmax precision binary.

This is intentionally separate from ``audit_softmax_native_ex2_sass.py``.
The older audit covers the EX2 operand-rate harness; this one checks complete
Softmax policies and, in particular, records three facts which must not be
inferred from C++ types alone:

* scalar FP16 max/sum is emitted as scalar PTX (``max.f16``/``add.f16``),
  then lowered on sm86 through ``HMNMX2``/``HADD2`` with ``.H0_H0`` operands;
* packed max/sum uses independent row lanes (``*.f16x2`` PTX and no scalar
  lane replication in the relevant sm86 SASS instructions); and
* isolated exponent policies retain scalar ``ex2.approx.f16`` versus packed
  ``ex2.approx.f16x2`` PTX.  On this frozen sm86 build both lower to four
  scalar ``MUFU.EX2.F16`` instructions, so packed PTX is not misreported as a
  single physical two-lane MUFU issue; and
* the ``hrcp(half)`` normalization path is lowered through FP32 reciprocal,
  followed by conversion back to FP16.  It is therefore not evidence of a
  native FP16 reciprocal instruction.

The exact PTX instruction counts apply to the fixed initial S=512, two-row
per CTA implementation.  The SASS checks deliberately use structural bounds
rather than fragile whole-function opcode totals, because conversion and
scheduling instructions can legitimately vary across CUDA toolkits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "softmax_whole_precision_sass_audit_v1"
EXPECTED_ARCH = 86

POLICY_NAMES = {
    0: "fp32_io_fp32_all",
    1: "fp16_io_fp32_all",
    2: "exp_fp16_scalar",
    3: "exp_fp16x2",
    4: "reduction_fp16_scalar",
    5: "reduction_fp16x2",
    6: "normalization_fp16_scalar",
    7: "normalization_fp16x2",
    8: "fp16_scalar_all",
    9: "fp16x2_all",
}

PTX_ENTRY_RE = re.compile(
    r"^\s*(?:\.visible\s+)?\.entry\s+(\S+?)\s*\(", re.MULTILINE
)
SASS_FUNCTION_RE = re.compile(r"^\s*Function\s*:\s*(\S+)\s*$", re.MULTILINE)
POLICY_RE = re.compile(r"whole_precision_softmax_kernelILNS0_6PolicyE(?P<id>\d+)E")

PTX_OPCODE_PATTERNS = {
    "ex2_f16": re.compile(
        r"(?<![\w.])ex2\.approx\.f16(?!x2)(?![\w.])", re.IGNORECASE
    ),
    "ex2_f16x2": re.compile(
        r"(?<![\w.])ex2\.approx\.f16x2(?![\w.])", re.IGNORECASE
    ),
    "max_f16": re.compile(r"(?<![\w.])max\.f16(?!x2)(?![\w.])", re.IGNORECASE),
    "max_f16x2": re.compile(r"(?<![\w.])max\.f16x2(?![\w.])", re.IGNORECASE),
    "add_f16": re.compile(r"(?<![\w.])add\.f16(?!x2)(?![\w.])", re.IGNORECASE),
    "add_f16x2": re.compile(r"(?<![\w.])add\.f16x2(?![\w.])", re.IGNORECASE),
    "mul_f16": re.compile(r"(?<![\w.])mul\.f16(?!x2)(?![\w.])", re.IGNORECASE),
    "mul_f16x2": re.compile(r"(?<![\w.])mul\.f16x2(?![\w.])", re.IGNORECASE),
    "rcp_approx_ftz_f32": re.compile(
        r"(?<![\w.])rcp\.approx\.ftz\.f32(?![\w.])", re.IGNORECASE
    ),
    "rcp_f16_or_f16x2": re.compile(
        r"(?<![\w.])rcp(?:\.[A-Za-z0-9_]+)*\.f16(?:x2)?(?![\w.])",
        re.IGNORECASE,
    ),
}
RCP_FP32_CONVERSION_SEQUENCE_RE = re.compile(
    r"cvt(?:\.[A-Za-z0-9_]+)*\.f32\.f16"
    r".*?rcp\.approx\.ftz\.f32"
    r".*?cvt(?:\.[A-Za-z0-9_]+)*\.f16\.f32",
    re.IGNORECASE | re.DOTALL,
)

SASS_PATTERNS = {
    "mufu_ex2_f16": re.compile(r"\bMUFU\.EX2\.F16\b"),
    "hmnmx2": re.compile(r"\bHMNMX2\b"),
    "hmnmx2_h0_h0": re.compile(r"\bHMNMX2\b[^\n]*\.H0_H0"),
    "hmnmx2_h1_h1": re.compile(r"\bHMNMX2\b[^\n]*\.H1_H1"),
    "hadd2_non_f32": re.compile(r"\bHADD2\b(?!\.F32)"),
    "hadd2_non_f32_h0_h0": re.compile(r"\bHADD2\b(?!\.F32)[^\n]*\.H0_H0"),
    "hadd2_non_f32_h1_h1": re.compile(r"\bHADD2\b(?!\.F32)[^\n]*\.H1_H1"),
    "mufu_rcp": re.compile(r"\bMUFU\.RCP\b(?!\.)"),
    "mufu_rcp_f16": re.compile(r"\bMUFU\.RCP\.F16(?:X2)?\b"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_cuobjdump(explicit: str) -> str:
    """Resolve a concrete cuobjdump executable without shell interpolation."""

    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    environment_value = os.environ.get("CUOBJDUMP", "")
    if environment_value:
        candidates.append(environment_value)
    path_value = shutil.which("cuobjdump")
    if path_value:
        candidates.append(path_value)

    for candidate in candidates:
        resolved = Path(candidate).expanduser()
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return str(resolved.resolve())
    raise SystemExit(
        "cuobjdump was not found; pass --cuobjdump or source "
        "scripts/activate_softmax_experiment_env.sh"
    )


def run_cuobjdump(cuobjdump: str, option: str, binary: Path) -> str:
    completed = subprocess.run(
        [cuobjdump, option, str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(detail or f"cuobjdump {option} failed")
    return completed.stdout


def tool_version(cuobjdump: str) -> str:
    completed = subprocess.run(
        [cuobjdump, "--version"], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        return "unavailable"
    return (completed.stdout.strip() or completed.stderr.strip() or "unknown")


def named_sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    return [
        (
            match.group(1),
            text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)],
        )
        for index, match in enumerate(matches)
    ]


def policy_sections(
    sections: list[tuple[str, str]],
) -> dict[int, list[tuple[str, str]]]:
    grouped: dict[int, list[tuple[str, str]]] = {policy: [] for policy in POLICY_NAMES}
    for name, body in sections:
        match = POLICY_RE.search(name)
        if match is None:
            continue
        policy_id = int(match.group("id"))
        if policy_id in grouped:
            grouped[policy_id].append((name, body))
    return grouped


def counts(body: str, patterns: dict[str, re.Pattern[str]]) -> dict[str, int]:
    return {name: len(pattern.findall(body)) for name, pattern in patterns.items()}


def instruction_examples(
    body: str, pattern: re.Pattern[str], limit: int = 4
) -> list[str]:
    examples: list[str] = []
    for line in body.splitlines():
        if pattern.search(line):
            examples.append(line.strip())
            if len(examples) == limit:
                break
    return examples


def check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    expected: Any,
    observed: Any,
    explanation: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "pass": passed,
            "expected": expected,
            "observed": observed,
            "explanation": explanation,
        }
    )


def require_count(
    checks: list[dict[str, Any]],
    check_id: str,
    observed_counts: dict[str, int],
    key: str,
    expected: int,
    explanation: str,
) -> None:
    check(checks, check_id, observed_counts[key] == expected, expected, observed_counts[key], explanation)


def require_at_least(
    checks: list[dict[str, Any]],
    check_id: str,
    observed_counts: dict[str, int],
    key: str,
    minimum: int,
    explanation: str,
) -> None:
    check(
        checks,
        check_id,
        observed_counts[key] >= minimum,
        {"minimum": minimum},
        observed_counts[key],
        explanation,
    )


def reduction_scalar_checks(
    ptx: dict[str, int], sass: dict[str, int], checks: list[dict[str, Any]]
) -> None:
    """Check E4: scalar PTX, then sm86 H0-lane vector instruction lowering."""

    require_count(checks, "scalar_ptx_max_f16", ptx, "max_f16", 18,
                  "Two rows × (one local + eight tree) scalar max operations.")
    require_count(checks, "scalar_ptx_add_f16", ptx, "add_f16", 18,
                  "Two rows × (one local + eight tree) scalar sum operations.")
    require_count(checks, "scalar_ptx_no_max_f16x2", ptx, "max_f16x2", 0,
                  "The scalar policy must not become a packed PTX reduction.")
    require_count(checks, "scalar_ptx_no_add_f16x2", ptx, "add_f16x2", 0,
                  "The scalar policy must not become a packed PTX reduction.")
    require_at_least(checks, "scalar_sass_hmnmx2_h0_lowering", sass,
                     "hmnmx2_h0_h0", 16,
                     "sm86 scalar tree stages are expected to replicate the low half lane.")
    require_at_least(checks, "scalar_sass_hadd2_h0_lowering", sass,
                     "hadd2_non_f32_h0_h0", 16,
                     "sm86 scalar tree stages are expected to replicate the low half lane.")
    require_count(checks, "scalar_sass_no_hmnmx2_h1_replication", sass,
                  "hmnmx2_h1_h1", 0,
                  "The established scalar lowering uses H0_H0, not H1_H1.")
    require_count(checks, "scalar_sass_no_hadd2_h1_replication", sass,
                  "hadd2_non_f32_h1_h1", 0,
                  "The established scalar lowering uses H0_H0, not H1_H1.")


def exponent_checks(
    scalar_ptx: dict[str, int],
    scalar_sass: dict[str, int],
    packed_ptx: dict[str, int],
    packed_sass: dict[str, int],
    checks: list[dict[str, Any]],
) -> None:
    """Check E2/E3's source PTX distinction and sm86 scalarized SASS form."""

    require_count(checks, "exp_scalar_ptx_ex2_f16", scalar_ptx, "ex2_f16", 4,
                  "Two rows × two elements use four scalar f16 EX2 PTX operations.")
    require_count(checks, "exp_scalar_ptx_no_ex2_f16x2", scalar_ptx, "ex2_f16x2", 0,
                  "The scalar exponent policy must not contain packed f16x2 EX2 PTX.")
    require_count(checks, "exp_scalar_sass_mufu_ex2_f16", scalar_sass, "mufu_ex2_f16", 4,
                  "The fixed sm86 scalar exponent specialization has four MUFU.EX2.F16 instructions.")
    require_count(checks, "exp_packed_ptx_ex2_f16x2", packed_ptx, "ex2_f16x2", 2,
                  "Two rows × one two-element pair use two packed f16x2 EX2 PTX operations.")
    require_count(checks, "exp_packed_ptx_no_ex2_f16", packed_ptx, "ex2_f16", 0,
                  "The packed exponent policy must not fall back to scalar f16 EX2 PTX.")
    require_count(checks, "exp_packed_sass_mufu_ex2_f16", packed_sass, "mufu_ex2_f16", 4,
                  "On this frozen sm86 build packed f16x2 PTX lowers to four scalar MUFU.EX2.F16 instructions.")


def reduction_packed_checks(
    ptx: dict[str, int], sass: dict[str, int], checks: list[dict[str, Any]]
) -> None:
    """Check E5: two independent rows occupy the two packed lanes."""

    require_count(checks, "packed_ptx_max_f16x2", ptx, "max_f16x2", 9,
                  "One two-row local+tree max reduction has nine f16x2 operations.")
    require_count(checks, "packed_ptx_add_f16x2", ptx, "add_f16x2", 9,
                  "One two-row local+tree sum reduction has nine f16x2 operations.")
    require_count(checks, "packed_ptx_no_max_f16", ptx, "max_f16", 0,
                  "The packed policy must not fall back to scalar PTX reduction.")
    require_count(checks, "packed_ptx_no_add_f16", ptx, "add_f16", 0,
                  "The packed policy must not fall back to scalar PTX reduction.")
    require_at_least(checks, "packed_sass_hmnmx2_pairwise", sass, "hmnmx2", 9,
                     "The packed local+tree max uses pairwise HMNMX2 operations.")
    require_at_least(checks, "packed_sass_hadd2_pairwise", sass, "hadd2_non_f32", 9,
                     "The packed local+tree sum uses pairwise HADD2 operations.")
    require_count(checks, "packed_sass_no_hmnmx2_h0_replication", sass,
                  "hmnmx2_h0_h0", 0,
                  "Packed rows must remain independent lanes, not H0 replication.")
    require_count(checks, "packed_sass_no_hadd2_h0_replication", sass,
                  "hadd2_non_f32_h0_h0", 0,
                  "Packed rows must remain independent lanes, not H0 replication.")


def normalization_checks(
    policy_name: str,
    ptx: dict[str, int],
    sass: dict[str, int],
    ptx_body: str,
    checks: list[dict[str, Any]],
    packed_multiply: bool,
) -> None:
    """Check E6/E7's FP32 reciprocal lowering and FP16 multiply shape."""

    prefix = "normalization_packed" if packed_multiply else "normalization_scalar"
    require_count(checks, f"{prefix}_ptx_rcp_f32", ptx, "rcp_approx_ftz_f32", 2,
                  "One half-typed reciprocal per independently normalized row lowers through FP32.")
    require_count(checks, f"{prefix}_ptx_no_native_rcp_f16", ptx, "rcp_f16_or_f16x2", 0,
                  "hrcp is not native FP16 reciprocal evidence on this build.")
    sequence_count = len(RCP_FP32_CONVERSION_SEQUENCE_RE.findall(ptx_body))
    check(checks, f"{prefix}_ptx_f16_to_f32_rcp_to_f16_sequence",
          sequence_count == 2, 2, sequence_count,
          "Each row must show f16→f32 conversion, FP32 reciprocal, and f32→f16 rounding.")
    require_count(checks, f"{prefix}_sass_mufu_rcp", sass, "mufu_rcp", 2,
                  "sm86 lowers the two reciprocal operations to scalar MUFU.RCP.")
    require_count(checks, f"{prefix}_sass_no_mufu_rcp_f16", sass, "mufu_rcp_f16", 0,
                  "No native FP16 MUFU reciprocal should be claimed.")
    if packed_multiply:
        require_count(checks, f"{prefix}_ptx_mul_f16x2", ptx, "mul_f16x2", 2,
                      "Each row uses one packed probability multiply.")
        require_count(checks, f"{prefix}_ptx_no_mul_f16", ptx, "mul_f16", 0,
                      "Packed normalization must not replace its multiply with scalar PTX.")
    else:
        require_count(checks, f"{prefix}_ptx_mul_f16", ptx, "mul_f16", 4,
                      "Two rows × two elements per thread use scalar probability multiplies.")
        require_count(checks, f"{prefix}_ptx_no_mul_f16x2", ptx, "mul_f16x2", 0,
                      "Scalar normalization must not use a packed PTX multiply.")


def full_policy_consistency_checks(
    scalar_ptx: dict[str, int], packed_ptx: dict[str, int], checks: list[dict[str, Any]]
) -> None:
    """Keep E8/E9 consistent with the isolated reduction implementations."""

    check(checks, "full_scalar_reduction_stays_scalar_ptx",
          scalar_ptx["max_f16"] >= 18 and scalar_ptx["add_f16"] >= 18
          and scalar_ptx["max_f16x2"] == 0 and scalar_ptx["add_f16x2"] == 0,
          {"min_max_f16": 18, "min_add_f16": 18, "f16x2": 0},
          {key: scalar_ptx[key] for key in ("max_f16", "add_f16", "max_f16x2", "add_f16x2")},
          "The all-scalar endpoint must retain the scalar reduction PTX path.")
    check(checks, "full_packed_reduction_stays_packed_ptx",
          packed_ptx["max_f16x2"] >= 9 and packed_ptx["add_f16x2"] >= 9
          and packed_ptx["max_f16"] == 0 and packed_ptx["add_f16"] == 0,
          {"min_max_f16x2": 9, "min_add_f16x2": 9, "f16": 0},
          {key: packed_ptx[key] for key in ("max_f16", "add_f16", "max_f16x2", "add_f16x2")},
          "The all-packed endpoint must retain the packed reduction PTX path.")


def section_report(
    policy_id: int,
    ptx_entries: list[tuple[str, str]],
    sass_entries: list[tuple[str, str]],
) -> dict[str, Any]:
    ptx_body = ptx_entries[0][1] if len(ptx_entries) == 1 else ""
    sass_body = sass_entries[0][1] if len(sass_entries) == 1 else ""
    return {
        "policy_id": policy_id,
        "policy": POLICY_NAMES[policy_id],
        "ptx_entries": [name for name, _ in ptx_entries],
        "sass_entries": [name for name, _ in sass_entries],
        "ptx_counts": counts(ptx_body, PTX_OPCODE_PATTERNS),
        "sass_counts": counts(sass_body, SASS_PATTERNS),
        "sass_evidence": {
            "mufu_ex2_f16": instruction_examples(sass_body, SASS_PATTERNS["mufu_ex2_f16"]),
            "hmnmx2_h0_h0": instruction_examples(sass_body, SASS_PATTERNS["hmnmx2_h0_h0"]),
            "hadd2_h0_h0": instruction_examples(sass_body, SASS_PATTERNS["hadd2_non_f32_h0_h0"]),
            "hmnmx2_pairwise": instruction_examples(sass_body, SASS_PATTERNS["hmnmx2"]),
            "hadd2_pairwise": instruction_examples(sass_body, SASS_PATTERNS["hadd2_non_f32"]),
            "mufu_rcp": instruction_examples(sass_body, SASS_PATTERNS["mufu_rcp"]),
        },
        "_ptx_body": ptx_body,
    }


def write_json(path: str, report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(serialized)
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path,
                        help="whole-precision executable to inspect")
    parser.add_argument("--cuobjdump", default="",
                        help="explicit cuobjdump path; defaults to $CUOBJDUMP or PATH")
    parser.add_argument("--out", default="-",
                        help="JSON report path, or '-' for stdout (default)")
    parser.add_argument("--expected-cuda-arch", type=int, default=EXPECTED_ARCH,
                        help="native/embedded architecture expected by this audit (default: 86)")
    parser.add_argument("--fail-on-unexpected", action="store_true",
                        help="exit 2 after writing JSON when any structural check fails")
    args = parser.parse_args()

    binary = args.binary.expanduser().resolve()
    if not binary.is_file():
        parser.error(f"binary does not exist: {binary}")
    cuobjdump = find_cuobjdump(args.cuobjdump)

    elf_listing = run_cuobjdump(cuobjdump, "--list-elf", binary)
    ptx_listing = run_cuobjdump(cuobjdump, "--list-ptx", binary)
    ptx_dump = run_cuobjdump(cuobjdump, "--dump-ptx", binary)
    sass_dump = run_cuobjdump(cuobjdump, "--dump-sass", binary)

    native_architectures = sorted({int(value) for value in re.findall(r"\.sm_(\d+)\.cubin\b", elf_listing)})
    embedded_ptx_architectures = sorted({int(value) for value in re.findall(r"\.sm_(\d+)\.ptx\b", ptx_listing)})
    ptx_grouped = policy_sections(named_sections(ptx_dump, PTX_ENTRY_RE))
    sass_grouped = policy_sections(named_sections(sass_dump, SASS_FUNCTION_RE))
    sections = {
        policy: section_report(policy, ptx_grouped[policy], sass_grouped[policy])
        for policy in POLICY_NAMES
    }

    checks: list[dict[str, Any]] = []
    check(checks, "sm86_lowering_contract_scope", args.expected_cuda_arch == EXPECTED_ARCH,
          EXPECTED_ARCH, args.expected_cuda_arch,
          "The scalar H0-lane lowering contract is established only for sm86.")
    check(checks, "native_architecture", native_architectures == [args.expected_cuda_arch],
          [args.expected_cuda_arch], native_architectures,
          "The binary must contain exactly the requested native cubin architecture.")
    check(checks, "embedded_ptx_architecture", embedded_ptx_architectures == [args.expected_cuda_arch],
          [args.expected_cuda_arch], embedded_ptx_architectures,
          "The binary must contain exactly the requested embedded PTX architecture.")

    for policy in POLICY_NAMES:
        section = sections[policy]
        check(checks, f"policy_{policy}_ptx_single_section", len(section["ptx_entries"]) == 1,
              1, len(section["ptx_entries"]), "Each policy specialization must have one PTX entry.")
        check(checks, f"policy_{policy}_sass_single_section", len(section["sass_entries"]) == 1,
              1, len(section["sass_entries"]), "Each policy specialization must have one SASS function.")

    scalar_exp = sections[2]
    packed_exp = sections[3]
    scalar_reduction = sections[4]
    packed_reduction = sections[5]
    scalar_norm = sections[6]
    packed_norm = sections[7]
    full_scalar = sections[8]
    full_packed = sections[9]
    exponent_checks(scalar_exp["ptx_counts"], scalar_exp["sass_counts"],
                    packed_exp["ptx_counts"], packed_exp["sass_counts"], checks)
    reduction_scalar_checks(scalar_reduction["ptx_counts"], scalar_reduction["sass_counts"], checks)
    reduction_packed_checks(packed_reduction["ptx_counts"], packed_reduction["sass_counts"], checks)
    normalization_checks("normalization_fp16_scalar", scalar_norm["ptx_counts"],
                         scalar_norm["sass_counts"], scalar_norm["_ptx_body"], checks, False)
    normalization_checks("normalization_fp16x2", packed_norm["ptx_counts"],
                         packed_norm["sass_counts"], packed_norm["_ptx_body"], checks, True)
    full_policy_consistency_checks(full_scalar["ptx_counts"], full_packed["ptx_counts"], checks)

    for section in sections.values():
        section.pop("_ptx_body", None)
    failures = [entry["id"] for entry in checks if not entry["pass"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "binary": {
            "path": str(binary),
            "sha256": sha256(binary),
            "native_architectures": native_architectures,
            "embedded_ptx_architectures": embedded_ptx_architectures,
        },
        "tool": {"cuobjdump": cuobjdump, "version": tool_version(cuobjdump)},
        "contract": {
            "expected_cuda_arch": args.expected_cuda_arch,
            "established_lowering_arch": EXPECTED_ARCH,
            "softmax_cols": 512,
            "rows_per_block": 2,
            "scope": "whole_softmax_precision_kernel",
        },
        "policy_sections": sections,
        "checks": checks,
        "overall": {
            "pass": not failures,
            "unexpected_check_ids": failures,
            "fail_on_unexpected": args.fail_on_unexpected,
        },
    }
    write_json(args.out, report)
    if failures and args.fail_on_unexpected:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
