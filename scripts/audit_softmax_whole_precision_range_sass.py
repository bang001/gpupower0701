#!/usr/bin/env python3
"""Statically audit the endpoint-range whole-Softmax binary.

This audit binds the *range* target to the platform on which it will be
measured.  It is deliberately narrower than the older sm86-only whole-Softmax
audit:

* Every requested row width must have one PTX and one native SASS endpoint
  specialization for the policy set allowed by the target profile.
* The fixed 256-thread/two-row range mapping has exact PTX count and type
  contracts for the FP32 (policy 0), scalar-FP16 (policy 8), and packed-FP16x2
  (policy 9) endpoints.
* SASS is recorded only as provenance from the requested target-native cubin.
  No Ampere opcode expectation is imposed on Volta or Hopper.

V100 is intentionally FP32-only.  The two FP16 endpoints need native
``ex2.approx.f16`` / ``ex2.approx.f16x2``, whose PTX ISA availability starts at
sm_75; this script records that unsupported state instead of treating a
software fallback or a zero-filled result as an endpoint measurement.
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
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "softmax_whole_precision_range_static_audit_v1"
RANGE_KERNEL_SYMBOL = "whole_precision_range_softmax_kernel"
SUPPORTED_SOFTMAX_COLS = (512, 1024, 2048, 4096)
ENDPOINT_POLICY_IDS = (0, 8, 9)
NATIVE_FP16_EX2_MIN_ARCH = 75

PROFILE_CONTRACTS: dict[str, dict[str, Any]] = {
    "rtx3090": {
        "native_cuda_arch": 86,
        "required_policy_ids": ENDPOINT_POLICY_IDS,
    },
    "v100": {
        "native_cuda_arch": 70,
        "required_policy_ids": (0,),
    },
    "a100": {
        "native_cuda_arch": 80,
        "required_policy_ids": ENDPOINT_POLICY_IDS,
    },
    "h100": {
        "native_cuda_arch": 90,
        "required_policy_ids": ENDPOINT_POLICY_IDS,
    },
}

POLICY_NAMES = {
    0: "fp32_io_fp32_all",
    8: "fp16_scalar_all",
    9: "fp16x2_all",
}

PTX_ENTRY_RE = re.compile(r"^\s*(?:\.visible\s+)?\.entry\s+(\S+?)\s*\(", re.MULTILINE)
SASS_FUNCTION_RE = re.compile(r"^\s*Function\s*:\s*(\S+)\s*$", re.MULTILINE)
RANGE_KERNEL_RE = re.compile(
    r"whole_precision_range_softmax_kernelILi(?P<cols>\d+)"
    r"ELNS0_6PolicyE(?P<policy>\d+)EE"
)

# These patterns are intentionally applied to one selected PTX entry, not to
# the whole fatbinary.  The former is an endpoint-semantic contract; the
# latter would be contaminated by the executable's host/support code.
PTX_OPCODE_PATTERNS = {
    "ex2_f32": re.compile(
        r"(?<![\w.])ex2\.approx(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
    "ex2_f16": re.compile(
        r"(?<![\w.])ex2\.approx(?:\.[A-Za-z0-9_]+)*\.f16(?!x2)(?![\w.])",
        re.IGNORECASE,
    ),
    "ex2_f16x2": re.compile(
        r"(?<![\w.])ex2\.approx(?:\.[A-Za-z0-9_]+)*\.f16x2(?![\w.])",
        re.IGNORECASE,
    ),
    "max_f32": re.compile(
        r"(?<![\w.])max(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
    "max_f16": re.compile(
        r"(?<![\w.])max(?:\.[A-Za-z0-9_]+)*\.f16(?!x2)(?![\w.])",
        re.IGNORECASE,
    ),
    "max_f16x2": re.compile(
        r"(?<![\w.])max(?:\.[A-Za-z0-9_]+)*\.f16x2(?![\w.])",
        re.IGNORECASE,
    ),
    "add_f32": re.compile(
        r"(?<![\w.])add(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
    "add_f16": re.compile(
        r"(?<![\w.])add(?:\.[A-Za-z0-9_]+)*\.f16(?!x2)(?![\w.])",
        re.IGNORECASE,
    ),
    "add_f16x2": re.compile(
        r"(?<![\w.])add(?:\.[A-Za-z0-9_]+)*\.f16x2(?![\w.])",
        re.IGNORECASE,
    ),
    "mul_f32": re.compile(
        r"(?<![\w.])mul(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
    "mul_f16": re.compile(
        r"(?<![\w.])mul(?:\.[A-Za-z0-9_]+)*\.f16(?!x2)(?![\w.])",
        re.IGNORECASE,
    ),
    "mul_f16x2": re.compile(
        r"(?<![\w.])mul(?:\.[A-Za-z0-9_]+)*\.f16x2(?![\w.])",
        re.IGNORECASE,
    ),
    "div_or_rcp_f32": re.compile(
        r"(?<![\w.])(?:div|rcp)(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
}

# The following are descriptive evidence only.  In particular, no expected
# MUFU/HADD2/HMNMX2 count appears in this script: a target's native SASS is
# captured and identified, but never judged against another architecture's
# lowering behavior.
SASS_OBSERVATION_PATTERNS = {
    "mufu_ex2": re.compile(r"\bMUFU\.EX2(?:\.F16)?\b"),
    "hmnmx2": re.compile(r"\bHMNMX2\b"),
    "hadd2": re.compile(r"\bHADD2\b"),
    "mufu_rcp": re.compile(r"\bMUFU\.RCP(?:\.F16(?:X2)?)?\b"),
    "ldl": re.compile(r"\bLDL(?:\.|\s)"),
    "stl": re.compile(r"\bSTL(?:\.|\s)"),
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_cuobjdump(explicit: str) -> str:
    """Resolve cuobjdump without relying on shell interpolation."""

    candidates = [value for value in (explicit, os.environ.get("CUOBJDUMP", "")) if value]
    path_candidate = shutil.which("cuobjdump")
    if path_candidate:
        candidates.append(path_candidate)
    for candidate in candidates:
        direct = Path(candidate).expanduser()
        if direct.is_file() and os.access(direct, os.X_OK):
            return str(direct.resolve())
        discovered = shutil.which(candidate)
        if discovered:
            return str(Path(discovered).resolve())
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


def cuobjdump_version(cuobjdump: str) -> str:
    completed = subprocess.run(
        [cuobjdump, "--version"], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        return "unavailable"
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def named_sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    return [
        (
            match.group(1),
            text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)],
        )
        for index, match in enumerate(matches)
    ]


def group_range_sections(
    sections: Iterable[tuple[str, str]],
) -> dict[tuple[int, int], list[tuple[str, str]]]:
    grouped: dict[tuple[int, int], list[tuple[str, str]]] = defaultdict(list)
    for name, body in sections:
        match = RANGE_KERNEL_RE.search(name)
        if match is not None:
            grouped[(int(match.group("cols")), int(match.group("policy")))].append(
                (name, body)
            )
    return dict(grouped)


def architectures_from_listing(text: str, suffix: str) -> list[int]:
    return sorted({int(value) for value in re.findall(rf"\.sm_(\d+)\.{suffix}\b", text)})


def list_files(text: str, label: str) -> list[str]:
    return re.findall(rf"^\s*{label}\s+file\s+\d+:\s*(\S+)\s*$", text, re.MULTILINE)


def opcode_counts(body: str) -> dict[str, int]:
    return {name: len(pattern.findall(body)) for name, pattern in PTX_OPCODE_PATTERNS.items()}


def sass_observations(body: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    counts = {name: len(pattern.findall(body)) for name, pattern in SASS_OBSERVATION_PATTERNS.items()}
    examples: dict[str, list[str]] = {}
    for name, pattern in SASS_OBSERVATION_PATTERNS.items():
        matches: list[str] = []
        for line in body.splitlines():
            if pattern.search(line):
                matches.append(line.strip())
                if len(matches) == 3:
                    break
        examples[name] = matches
    return counts, examples


def expected_ptx_counts(policy_id: int, softmax_cols: int) -> dict[str, int]:
    """Return exact PTX counts for one range endpoint specialization.

    The range kernel has 256 threads and two logical rows per CTA.  Let
    ``e = S / 256``.  The local work contributes two rows times ``e`` scalar
    terms.  Its fixed CTA reduction tree contributes 18/20 scalar FP32
    max/add PTX operations, 14/14 scalar-FP16 operations, or 7/7 half2
    operations.  The count contract therefore remains explicit for every
    supported S without extrapolating a SASS lowering rule across targets.
    """

    elements_per_thread = softmax_cols // 256
    all_zero = {name: 0 for name in PTX_OPCODE_PATTERNS}
    if policy_id == 0:
        return {
            **all_zero,
            "ex2_f32": 2 * elements_per_thread,
            "max_f32": 2 * elements_per_thread + 18,
            "add_f32": 2 * elements_per_thread + 20,
            "mul_f32": 4 * elements_per_thread,
            "div_or_rcp_f32": 2,
        }
    if policy_id == 8:
        return {
            **all_zero,
            "ex2_f16": 2 * elements_per_thread,
            "max_f16": 2 * elements_per_thread + 14,
            "add_f16": 2 * elements_per_thread + 14,
            "mul_f16": 4 * elements_per_thread,
            "div_or_rcp_f32": 2,
        }
    if policy_id == 9:
        return {
            **all_zero,
            "ex2_f16x2": elements_per_thread,
            "max_f16x2": elements_per_thread + 7,
            "add_f16x2": elements_per_thread + 7,
            "mul_f16x2": 2 * elements_per_thread,
            "div_or_rcp_f32": 2,
        }
    raise ValueError(f"unknown endpoint policy: {policy_id}")


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
            "pass": bool(passed),
            "expected": expected,
            "observed": observed,
            "explanation": explanation,
        }
    )


def parse_required_softmax_cols(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--required-softmax-cols must be a comma-separated integer list"
        ) from error
    if not parsed:
        raise argparse.ArgumentTypeError("--required-softmax-cols must not be empty")
    if len(set(parsed)) != len(parsed):
        raise argparse.ArgumentTypeError("--required-softmax-cols must not repeat a width")
    unsupported = sorted(set(parsed) - set(SUPPORTED_SOFTMAX_COLS))
    if unsupported:
        raise argparse.ArgumentTypeError(
            "unsupported range width(s): " + ", ".join(map(str, unsupported))
        )
    return tuple(sorted(parsed))


def capture_record(
    *,
    name: str,
    text: str,
    directory: Path | None,
) -> dict[str, Any]:
    encoded = text.encode("utf-8")
    record: dict[str, Any] = {
        "sha256": sha256_bytes(encoded),
        "bytes": len(encoded),
        "lines": text.count("\n"),
        "path": None,
    }
    if directory is not None:
        output = directory / f"{name}.txt"
        atomic_write_text(output, text)
        record["path"] = str(output.resolve())
    return record


def unsupported_v100_policies() -> dict[str, dict[str, Any]]:
    return {
        f"policy_{policy_id}": {
            "policy_id": policy_id,
            "policy": POLICY_NAMES[policy_id],
            "pass": True,
            "status": "unsupported_native_fp16_ex2_sm70",
            "min_native_cuda_arch": NATIVE_FP16_EX2_MIN_ARCH,
            "target_native_cuda_arch": PROFILE_CONTRACTS["v100"]["native_cuda_arch"],
            "reason": (
                "The endpoint requires native ex2.approx.f16 or "
                "ex2.approx.f16x2; PTX ISA availability begins at sm_75. "
                "No fallback endpoint is accepted for the V100 comparison."
            ),
        }
        for policy_id in (8, 9)
    }


def default_capture_dir(out: str) -> Path | None:
    if out == "-":
        return None
    output = Path(out).expanduser().resolve()
    return output.parent / f"{output.stem}_cuobjdump"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True,
                        help="range executable to inspect")
    parser.add_argument("--target-profile", choices=tuple(PROFILE_CONTRACTS), required=True,
                        help="platform profile whose native cubin is required")
    parser.add_argument(
        "--required-softmax-cols",
        type=parse_required_softmax_cols,
        default=SUPPORTED_SOFTMAX_COLS,
        metavar="S[,S...]",
        help=(
            "required compiled widths (default: 512,1024,2048,4096); "
            "the requested list is a subset contract, not a broad sweep"
        ),
    )
    parser.add_argument("--cuobjdump", default="",
                        help="explicit cuobjdump path; defaults to $CUOBJDUMP or PATH")
    parser.add_argument("--out", default="-",
                        help="JSON evidence path, or '-' for stdout (default)")
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=None,
        help=(
            "directory for immutable text captures of --list-elf/--list-ptx/"
            "--dump-ptx/--dump-sass; defaults beside --out when --out is a file"
        ),
    )
    parser.add_argument(
        "--fail-on-unexpected",
        action="store_true",
        help="exit 2 after writing JSON when any structural/PTX contract check fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.expanduser().resolve()
    if not binary.is_file():
        raise SystemExit(f"binary does not exist: {binary}")
    cuobjdump = find_cuobjdump(args.cuobjdump)
    profile = PROFILE_CONTRACTS[args.target_profile]
    expected_arch = int(profile["native_cuda_arch"])
    required_cols = tuple(args.required_softmax_cols)
    required_policy_ids = tuple(profile["required_policy_ids"])
    capture_dir = (
        args.capture_dir.expanduser().resolve()
        if args.capture_dir is not None
        else default_capture_dir(args.out)
    )

    elf_listing = run_cuobjdump(cuobjdump, "--list-elf", binary)
    ptx_listing = run_cuobjdump(cuobjdump, "--list-ptx", binary)
    ptx_dump = run_cuobjdump(cuobjdump, "--dump-ptx", binary)
    sass_dump = run_cuobjdump(cuobjdump, "--dump-sass", binary)
    dump_captures = {
        "list_elf": capture_record(name="list_elf", text=elf_listing, directory=capture_dir),
        "list_ptx": capture_record(name="list_ptx", text=ptx_listing, directory=capture_dir),
        "dump_ptx": capture_record(name="dump_ptx", text=ptx_dump, directory=capture_dir),
        "dump_sass": capture_record(name="dump_sass", text=sass_dump, directory=capture_dir),
    }

    native_architectures = architectures_from_listing(elf_listing, "cubin")
    embedded_ptx_architectures = architectures_from_listing(ptx_listing, "ptx")
    ptx_grouped = group_range_sections(named_sections(ptx_dump, PTX_ENTRY_RE))
    sass_grouped = group_range_sections(named_sections(sass_dump, SASS_FUNCTION_RE))
    observed_range_cols = sorted({cols for cols, _ in set(ptx_grouped) | set(sass_grouped)})
    observed_range_policy_ids = sorted(
        {policy for _, policy in set(ptx_grouped) | set(sass_grouped)}
    )

    checks: list[dict[str, Any]] = []
    check(
        checks,
        "target_native_cubin_architecture",
        native_architectures == [expected_arch],
        [expected_arch],
        native_architectures,
        "The executable must contain exactly the target profile's native cubin architecture.",
    )
    check(
        checks,
        "target_embedded_ptx_architecture",
        embedded_ptx_architectures == [expected_arch],
        [expected_arch],
        embedded_ptx_architectures,
        "The executable must contain exactly the target profile's embedded PTX architecture.",
    )
    check(
        checks,
        "required_range_widths_present",
        set(required_cols).issubset(observed_range_cols),
        list(required_cols),
        observed_range_cols,
        "Every requested range width must have at least one endpoint specialization.",
    )
    check(
        checks,
        "no_unsupported_range_widths",
        set(observed_range_cols).issubset(SUPPORTED_SOFTMAX_COLS),
        list(SUPPORTED_SOFTMAX_COLS),
        observed_range_cols,
        "The range binary may contain only its four compile-time-supported widths.",
    )
    check(
        checks,
        "no_unexpected_range_endpoint_policy",
        set(observed_range_policy_ids).issubset(ENDPOINT_POLICY_IDS),
        list(ENDPOINT_POLICY_IDS),
        observed_range_policy_ids,
        "The range binary must not silently add an unreviewed endpoint policy.",
    )

    unsupported = unsupported_v100_policies() if args.target_profile == "v100" else {}
    if args.target_profile == "v100":
        check(
            checks,
            "v100_fp32_only_native_ex2_contract",
            expected_arch < NATIVE_FP16_EX2_MIN_ARCH and required_policy_ids == (0,),
            {
                "native_cuda_arch_less_than": NATIVE_FP16_EX2_MIN_ARCH,
                "required_policy_ids": [0],
            },
            {
                "native_cuda_arch": expected_arch,
                "required_policy_ids": list(required_policy_ids),
                "unsupported_policies": unsupported,
            },
            "V100 records policy 8/9 as unsupported native-FP16-EX2 endpoints, not as measurements.",
        )

    captures: dict[str, dict[str, dict[str, Any]]] = {}
    for softmax_cols in required_cols:
        capture_by_policy: dict[str, dict[str, Any]] = {}
        for policy_id in required_policy_ids:
            ptx_entries = ptx_grouped.get((softmax_cols, policy_id), [])
            sass_entries = sass_grouped.get((softmax_cols, policy_id), [])
            ptx_body = ptx_entries[0][1] if len(ptx_entries) == 1 else ""
            sass_body = sass_entries[0][1] if len(sass_entries) == 1 else ""
            ptx_counts = opcode_counts(ptx_body)
            expected_counts = expected_ptx_counts(policy_id, softmax_cols)
            ptx_checks: list[dict[str, Any]] = []
            check(
                ptx_checks,
                "ptx_entry_multiplicity",
                len(ptx_entries) == 1,
                1,
                len(ptx_entries),
                "Each required endpoint must have exactly one selected PTX entry.",
            )
            check(
                ptx_checks,
                "sass_function_multiplicity",
                len(sass_entries) == 1,
                1,
                len(sass_entries),
                "Each required endpoint must have exactly one selected native SASS function.",
            )
            ptx_names = [name for name, _ in ptx_entries]
            sass_names = [name for name, _ in sass_entries]
            check(
                ptx_checks,
                "ptx_sass_function_name_match",
                len(ptx_names) == len(sass_names) == 1 and ptx_names[0] == sass_names[0],
                "one identical PTX/SASS function name",
                {"ptx": ptx_names, "sass": sass_names},
                "PTX and native SASS evidence must describe the same specialization.",
            )
            for opcode in sorted(PTX_OPCODE_PATTERNS):
                check(
                    ptx_checks,
                    f"ptx_{opcode}_exact_count",
                    ptx_counts[opcode] == expected_counts[opcode],
                    expected_counts[opcode],
                    ptx_counts[opcode],
                    "Fixed range endpoint PTX count/type contract.",
                )

            header = re.search(r'\.headerflags\s+@"([^"]+)"', sass_body)
            header_value = header.group(1) if header is not None else ""
            header_present = f"EF_CUDA_SM{expected_arch}" in header_value
            canonical_native_header = (
                f"sm_{expected_arch}; {header_value}" if header_value else f"sm_{expected_arch}"
            )
            target_native_only = (
                native_architectures == [expected_arch]
                and embedded_ptx_architectures == [expected_arch]
                and header_present
            )
            check(
                ptx_checks,
                "target_native_sass_provenance",
                target_native_only,
                {
                    "native_architectures": [expected_arch],
                    "embedded_ptx_architectures": [expected_arch],
                    "sass_header_contains": f"EF_CUDA_SM{expected_arch}",
                },
                {
                    "native_architectures": native_architectures,
                    "embedded_ptx_architectures": embedded_ptx_architectures,
                    "sass_header": header_value,
                },
                "SASS is provenance for this target-native cubin only; no cross-architecture opcode contract is applied.",
            )
            observed_sass_counts, sass_examples = sass_observations(sass_body)
            capture_pass = all(item["pass"] for item in ptx_checks)
            capture = {
                "policy_id": policy_id,
                "policy": POLICY_NAMES[policy_id],
                "softmax_cols": softmax_cols,
                "elements_per_thread": softmax_cols // 256,
                "ptx_entries": ptx_names,
                "sass_entries": sass_names,
                "ptx_section_sha256": sha256_bytes(ptx_body.encode("utf-8")) if ptx_body else None,
                "sass_section_sha256": sha256_bytes(sass_body.encode("utf-8")) if sass_body else None,
                "ptx_counts": ptx_counts,
                "ptx_expected_counts": expected_counts,
                "ptx_checks": ptx_checks,
                "sass_provenance": {
                    "native_arch_header_present": header_present,
                    "native_arch_header": canonical_native_header,
                    "native_arch_header_raw": header_value,
                    "target_native_only": target_native_only,
                    "opcode_contract": "observation_only_no_crossarch_claim",
                    "observed_opcode_counts": observed_sass_counts,
                    "examples": sass_examples,
                },
                "pass": capture_pass,
            }
            capture_by_policy[f"policy_{policy_id}"] = capture
            for item in ptx_checks:
                checks.append(
                    {
                        **item,
                        "id": f"s{softmax_cols}_policy_{policy_id}_{item['id']}",
                    }
                )
        captures[f"s{softmax_cols}"] = capture_by_policy

    nonrequired_inventory: dict[str, dict[str, Any]] = {}
    for softmax_cols in required_cols:
        entries: dict[str, Any] = {}
        for policy_id in ENDPOINT_POLICY_IDS:
            if policy_id in required_policy_ids:
                continue
            ptx_entries = ptx_grouped.get((softmax_cols, policy_id), [])
            sass_entries = sass_grouped.get((softmax_cols, policy_id), [])
            ptx_body = ptx_entries[0][1] if len(ptx_entries) == 1 else ""
            entries[f"policy_{policy_id}"] = {
                "policy_id": policy_id,
                "policy": POLICY_NAMES[policy_id],
                "ptx_entry_count": len(ptx_entries),
                "sass_function_count": len(sass_entries),
                "observed_ptx_counts": opcode_counts(ptx_body),
            }
        if entries:
            nonrequired_inventory[f"s{softmax_cols}"] = entries

    failures = [item["id"] for item in checks if not item["pass"]]
    contract = {
        "target_profile": args.target_profile,
        "native_cuda_arch": expected_arch,
        "required_softmax_cols": list(required_cols),
        "required_policy_ids": list(required_policy_ids),
        "required_policy_names": [POLICY_NAMES[policy] for policy in required_policy_ids],
        "required_policies": [
            {"policy_id": policy, "policy": POLICY_NAMES[policy]}
            for policy in required_policy_ids
        ],
        "unsupported_policies": unsupported,
        "range_kernel_symbol": RANGE_KERNEL_SYMBOL,
        "threads_per_block": 256,
        "rows_per_block": 2,
        "native_fp16_ex2_min_cuda_arch": NATIVE_FP16_EX2_MIN_ARCH,
        "sass_interpretation": "target_native_provenance_only_no_crossarch_opcode_claim",
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "binary": {
            "path": str(binary),
            "sha256": sha256_file(binary),
            "bytes": binary.stat().st_size,
            "native_architectures": native_architectures,
            "embedded_ptx_architectures": embedded_ptx_architectures,
        },
        "tool": {"cuobjdump": cuobjdump, "version": cuobjdump_version(cuobjdump)},
        "contract": contract,
        "unsupported_policies": unsupported,
        "cuobjdump_captures": {
            **dump_captures,
            "capture_dir": str(capture_dir) if capture_dir is not None else None,
            "list_elf_files": list_files(elf_listing, "ELF"),
            "list_ptx_files": list_files(ptx_listing, "PTX"),
        },
        "observed_range_inventory": {
            "softmax_cols": observed_range_cols,
            "endpoint_policy_ids": observed_range_policy_ids,
        },
        "captures": captures,
        "nonrequired_endpoint_inventory": nonrequired_inventory,
        "checks": checks,
        "overall": {
            "pass": not failures,
            "unexpected_check_ids": failures,
            "fail_on_unexpected": args.fail_on_unexpected,
        },
    }

    if args.out == "-":
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    else:
        atomic_write_json(Path(args.out).expanduser().resolve(), report)
    if failures and args.fail_on_unexpected:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
