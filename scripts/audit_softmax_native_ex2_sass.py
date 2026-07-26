#!/usr/bin/env python3
"""Audit native FP16 EX2 PTX/SASS for one row width in a Softmax binary.

The audit deliberately keeps the algorithm mode, exponential implementation,
and cache policy as separate identity axes.  In particular, it does not fold
the three full-Softmax implementations into one ``full`` set member; doing so
would let duplicate or missing native-EX2 specializations pass unnoticed.
S=512 remains the default for backward compatibility; ``--softmax-cols`` can
select every specialization used by the factorial experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, NamedTuple


SASS_FUNCTION_RE = re.compile(r"^\s*Function\s*:\s*(\S+)\s*$", re.MULTILINE)
PTX_ENTRY_RE = re.compile(
    r"^\s*(?:\.visible\s+)?\.entry\s+(\S+?)\s*\(", re.MULTILINE
)
RESOURCE_FUNCTION_RE = re.compile(
    r"^\s*Function\s+(\S+):\s*$", re.MULTILINE
)
KERNEL_ID_RE = re.compile(
    r"softmax_row_kernelILi(?P<cols>\d+)"
    r"ELNS_11SoftmaxModeE(?P<mode>\d+)"
    r"ELNS_17ExpImplementationE(?P<exp>\d+)"
    r"ELb(?P<cache>[01])EE"
)


class Variant(NamedTuple):
    mode: int
    exp: int
    cache: int


MODE_NAMES = {
    0: "full",
    1: "linear_control",
    2: "io_control",
}
EXP_NAMES = {
    0: "fp32_fast___expf",
    1: "ptx_ex2_approx_f16",
    2: "ptx_ex2_approx_f16x2",
}
CACHE_NAMES = {
    0: "default",
    1: "cg",
}

# Per cache: three full implementations plus the two FP32-only controls.
EXPECTED_VARIANTS = frozenset(
    Variant(mode, exp, cache)
    for cache in (0, 1)
    for mode, exp in ((0, 0), (0, 1), (0, 2), (1, 0), (2, 0))
)
EXPECTED_COUNTER = Counter({variant: 1 for variant in EXPECTED_VARIANTS})


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_cuobjdump(cuobjdump: str, option: str, binary: Path) -> str:
    process = subprocess.run(
        [cuobjdump, option, str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise SystemExit(detail or f"cuobjdump {option} failed")
    return process.stdout


def named_sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), text[match.start() : end]))
    return sections


def variant_for(name: str, softmax_cols: int) -> Variant | None:
    match = KERNEL_ID_RE.search(name)
    if match is None or int(match.group("cols")) != softmax_cols:
        return None
    return Variant(
        int(match.group("mode")),
        int(match.group("exp")),
        int(match.group("cache")),
    )


def group_variants(
    sections: Iterable[tuple[str, str]],
    softmax_cols: int,
) -> dict[Variant, list[tuple[str, str]]]:
    grouped: dict[Variant, list[tuple[str, str]]] = defaultdict(list)
    for name, body in sections:
        variant = variant_for(name, softmax_cols)
        if variant is not None:
            grouped[variant].append((name, body))
    return dict(grouped)


def section_counter(grouped: dict[Variant, list[tuple[str, str]]]) -> Counter[Variant]:
    return Counter({variant: len(entries) for variant, entries in grouped.items()})


def architecture_list(text: str, suffix: str) -> list[int]:
    return sorted(
        {int(value) for value in re.findall(rf"\.sm_(\d+)\.{suffix}\b", text)}
    )


def count_regex(pattern: str, bodies: Iterable[str], flags: int = 0) -> int:
    return sum(len(re.findall(pattern, body, flags)) for body in bodies)


def resource_values(entries: list[tuple[str, str]], label: str) -> list[int]:
    values: list[int] = []
    pattern = re.compile(rf"\b{re.escape(label)}:(\d+)\b")
    for _, body in entries:
        match = pattern.search(body)
        if match is not None:
            values.append(int(match.group(1)))
    return values


def join_ints(values: list[int]) -> str:
    return "|".join(str(value) for value in values)


def expected_opcode_counts(
    variant: Variant, softmax_cols: int
) -> dict[str, int] | None:
    if variant not in EXPECTED_VARIANTS:
        return None
    if variant.mode != 0:
        return {
            "ptx_f32": 0,
            "ptx_ftz_f32": 0,
            "ptx_f16": 0,
            "ptx_f16x2": 0,
            "sass_plain": 0,
            "sass_f16": 0,
            "pred_plain": 0,
            "pred_f16": 0,
        }
    elements_per_thread = (
        1 if softmax_cols <= 256 else softmax_cols // 256
    )
    if variant.exp == 0:
        return {
            "ptx_f32": 2 * elements_per_thread,
            "ptx_ftz_f32": 0,
            "ptx_f16": 0,
            "ptx_f16x2": 0,
            "sass_plain": 2 * elements_per_thread,
            "sass_f16": 0,
            "pred_plain": elements_per_thread,
            "pred_f16": 0,
        }
    if variant.exp == 1:
        return {
            "ptx_f32": 0,
            "ptx_ftz_f32": 0,
            "ptx_f16": 2 * elements_per_thread,
            "ptx_f16x2": 0,
            "sass_plain": 0,
            "sass_f16": 2 * elements_per_thread,
            "pred_plain": 0,
            "pred_f16": elements_per_thread,
        }
    packed_ptx_count = (
        2 if elements_per_thread == 1 else elements_per_thread
    )
    return {
        "ptx_f32": 0,
        "ptx_ftz_f32": 0,
        "ptx_f16": 0,
        "ptx_f16x2": packed_ptx_count,
        # CUDA 13.2 lowers each packed PTX instruction to two scalar F16
        # MUFU instructions on both sm_80 and sm_86.
        "sass_plain": 0,
        "sass_f16": 2 * packed_ptx_count,
        "pred_plain": 0,
        "pred_f16": (
            2 if elements_per_thread == 1 else elements_per_thread
        ),
    }


def display_name(mapping: dict[int, str], value: int, prefix: str) -> str:
    return mapping.get(value, f"unknown_{prefix}{value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--cuobjdump", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--softmax-cols",
        type=int,
        choices=(128, 256, 512, 1024, 2048, 4096),
        default=512,
        help="row-width specialization to audit (default: 512)",
    )
    parser.add_argument(
        "--expected-cuda-arch",
        type=int,
        choices=(80, 86),
        required=True,
        help="require a single native sm_80 or sm_86 artifact",
    )
    args = parser.parse_args()

    if not args.binary.is_file():
        raise SystemExit(f"binary does not exist: {args.binary}")

    binary_sha256 = sha256(args.binary)
    elf_listing = run_cuobjdump(args.cuobjdump, "--list-elf", args.binary)
    ptx_listing = run_cuobjdump(args.cuobjdump, "--list-ptx", args.binary)
    ptx_dump = run_cuobjdump(args.cuobjdump, "--dump-ptx", args.binary)
    sass_dump = run_cuobjdump(args.cuobjdump, "--dump-sass", args.binary)
    resource_dump = run_cuobjdump(
        args.cuobjdump, "--dump-resource-usage", args.binary
    )

    binary_architectures = architecture_list(elf_listing, "cubin")
    ptx_architectures = architecture_list(ptx_listing, "ptx")
    native_arch_gate_pass = binary_architectures == [args.expected_cuda_arch]
    embedded_ptx_arch_gate_pass = ptx_architectures == [args.expected_cuda_arch]
    architecture_gate_pass = native_arch_gate_pass and embedded_ptx_arch_gate_pass

    ptx_grouped = group_variants(
        named_sections(ptx_dump, PTX_ENTRY_RE), args.softmax_cols
    )
    sass_grouped = group_variants(
        named_sections(sass_dump, SASS_FUNCTION_RE), args.softmax_cols
    )
    resource_grouped = group_variants(
        named_sections(resource_dump, RESOURCE_FUNCTION_RE),
        args.softmax_cols,
    )
    ptx_counter = section_counter(ptx_grouped)
    sass_counter = section_counter(sass_grouped)
    resource_counter = section_counter(resource_grouped)
    ptx_exact_set_gate_pass = ptx_counter == EXPECTED_COUNTER
    sass_exact_set_gate_pass = sass_counter == EXPECTED_COUNTER
    resource_exact_set_gate_pass = resource_counter == EXPECTED_COUNTER
    exact_variant_set_gate_pass = (
        ptx_exact_set_gate_pass
        and sass_exact_set_gate_pass
        and resource_exact_set_gate_pass
    )

    all_variants = sorted(
        EXPECTED_VARIANTS
        | set(ptx_grouped)
        | set(sass_grouped)
        | set(resource_grouped)
    )
    rows: list[dict[str, object]] = []
    for variant in all_variants:
        ptx_entries = ptx_grouped.get(variant, [])
        sass_entries = sass_grouped.get(variant, [])
        resource_entries = resource_grouped.get(variant, [])
        ptx_bodies = [body for _, body in ptx_entries]
        sass_bodies = [body for _, body in sass_entries]

        ptx_f32_count = count_regex(
            r"(?<![\w.])ex2\.approx\.f32\b", ptx_bodies, re.IGNORECASE
        )
        ptx_ftz_f32_count = count_regex(
            r"(?<![\w.])ex2\.approx\.ftz\.f32\b", ptx_bodies, re.IGNORECASE
        )
        ptx_f16_count = count_regex(
            r"(?<![\w.])ex2\.approx\.f16\b(?!x2)",
            ptx_bodies,
            re.IGNORECASE,
        )
        ptx_f16x2_count = count_regex(
            r"(?<![\w.])ex2\.approx\.f16x2\b", ptx_bodies, re.IGNORECASE
        )

        sass_plain_count = count_regex(
            r"\bMUFU\.EX2\b(?!\.)", sass_bodies
        )
        sass_f16_count = count_regex(r"\bMUFU\.EX2\.F16\b", sass_bodies)
        pred_plain_count = count_regex(
            r"@!?P\d+\s+MUFU\.EX2\b(?!\.)", sass_bodies
        )
        pred_f16_count = count_regex(
            r"@!?P\d+\s+MUFU\.EX2\.F16\b", sass_bodies
        )
        prmt_count = count_regex(r"\bPRMT\b", sass_bodies)
        uprmt_count = count_regex(r"\bUPRMT\b", sass_bodies)
        ldl_count = count_regex(r"\bLDL(?:\.|\s)", sass_bodies)
        stl_count = count_regex(r"\bSTL(?:\.|\s)", sass_bodies)

        registers = resource_values(resource_entries, "REG")
        shared_bytes = resource_values(resource_entries, "SHARED")
        stack_bytes = resource_values(resource_entries, "STACK")
        local_bytes = resource_values(resource_entries, "LOCAL")
        expected = expected_opcode_counts(variant, args.softmax_cols)

        section_gate_pass = (
            variant in EXPECTED_VARIANTS
            and len(ptx_entries) == 1
            and len(sass_entries) == 1
            and len(resource_entries) == 1
        )
        ptx_names = [name for name, _ in ptx_entries]
        sass_names = [name for name, _ in sass_entries]
        resource_names = [name for name, _ in resource_entries]
        function_name_consistent = (
            section_gate_pass
            and ptx_names[0] == sass_names[0] == resource_names[0]
        )
        sass_arch_header_present = (
            len(sass_bodies) == 1
            and f"EF_CUDA_SM{args.expected_cuda_arch}" in sass_bodies[0]
        )
        resource_metadata_gate_pass = (
            len(registers) == len(shared_bytes) == len(stack_bytes) == len(local_bytes) == 1
            and registers[0] > 0
        )
        spill_local_gate_pass = (
            resource_metadata_gate_pass
            and stack_bytes[0] == 0
            and local_bytes[0] == 0
            and ldl_count == 0
            and stl_count == 0
        )

        if expected is None:
            ptx_opcode_gate_pass = False
            sass_opcode_gate_pass = False
            predicated_probe_gate_pass = False
        else:
            ptx_opcode_gate_pass = (
                ptx_f32_count == expected["ptx_f32"]
                and ptx_ftz_f32_count == expected["ptx_ftz_f32"]
                and ptx_f16_count == expected["ptx_f16"]
                and ptx_f16x2_count == expected["ptx_f16x2"]
            )
            sass_opcode_gate_pass = (
                sass_plain_count == expected["sass_plain"]
                and sass_f16_count == expected["sass_f16"]
            )
            predicated_probe_gate_pass = (
                pred_plain_count == expected["pred_plain"]
                and pred_f16_count == expected["pred_f16"]
            )

        # This is recorded as a lowering observation.  Opcode counts above,
        # rather than a compiler-specific number of PRMT instructions, are the
        # hard semantic gate.
        prmt_or_uprmt_present = prmt_count + uprmt_count > 0
        packed_path_prmt_observation_pass = (
            variant.exp != 2 or prmt_or_uprmt_present
        )

        failure_reasons: list[str] = []
        if not architecture_gate_pass:
            failure_reasons.append("architecture")
        if not exact_variant_set_gate_pass:
            failure_reasons.append("exact_variant_set")
        if not section_gate_pass:
            failure_reasons.append("section_multiplicity")
        if not function_name_consistent:
            failure_reasons.append("function_name_consistency")
        if not sass_arch_header_present:
            failure_reasons.append("sass_arch_header")
        if not ptx_opcode_gate_pass:
            failure_reasons.append("ptx_opcode_count")
        if not sass_opcode_gate_pass:
            failure_reasons.append("sass_opcode_count")
        if not predicated_probe_gate_pass:
            failure_reasons.append("predicated_probe_count")
        if not resource_metadata_gate_pass:
            failure_reasons.append("resource_metadata")
        if not spill_local_gate_pass:
            failure_reasons.append("spill_or_local_memory")

        verdict = "pass" if not failure_reasons else "fail"
        expected_or_negative = expected or {
            "ptx_f32": -1,
            "ptx_ftz_f32": -1,
            "ptx_f16": -1,
            "ptx_f16x2": -1,
            "sass_plain": -1,
            "sass_f16": -1,
            "pred_plain": -1,
            "pred_f16": -1,
        }
        rows.append(
            {
                "mode": display_name(MODE_NAMES, variant.mode, "mode_e"),
                "softmax_mode_enum": variant.mode,
                "exp_implementation": display_name(
                    EXP_NAMES, variant.exp, "exp_e"
                ),
                "exp_implementation_enum": variant.exp,
                "cache_policy": display_name(
                    CACHE_NAMES, variant.cache, "cache_e"
                ),
                "cache_policy_bool": variant.cache,
                "softmax_cols": args.softmax_cols,
                "binary": str(args.binary),
                "binary_sha256": binary_sha256,
                "cuobjdump": args.cuobjdump,
                "binary_architectures": "|".join(map(str, binary_architectures)),
                "embedded_ptx_architectures": "|".join(map(str, ptx_architectures)),
                "expected_cuda_arch": args.expected_cuda_arch,
                "native_arch_gate_pass": bool_text(native_arch_gate_pass),
                "embedded_ptx_arch_gate_pass": bool_text(
                    embedded_ptx_arch_gate_pass
                ),
                "architecture_gate_pass": bool_text(architecture_gate_pass),
                "expected_variant_count": len(EXPECTED_VARIANTS),
                "ptx_observed_selected_cols_section_count": sum(
                    ptx_counter.values()
                ),
                "sass_observed_selected_cols_section_count": sum(
                    sass_counter.values()
                ),
                "resource_observed_selected_cols_section_count": sum(
                    resource_counter.values()
                ),
                # Retain the historical fields for S=512 consumers.  They are
                # deliberately blank for other row-width audits.
                "ptx_observed_s512_section_count": (
                    sum(ptx_counter.values())
                    if args.softmax_cols == 512
                    else ""
                ),
                "sass_observed_s512_section_count": (
                    sum(sass_counter.values())
                    if args.softmax_cols == 512
                    else ""
                ),
                "resource_observed_s512_section_count": (
                    sum(resource_counter.values())
                    if args.softmax_cols == 512
                    else ""
                ),
                "ptx_exact_variant_set_gate_pass": bool_text(
                    ptx_exact_set_gate_pass
                ),
                "sass_exact_variant_set_gate_pass": bool_text(
                    sass_exact_set_gate_pass
                ),
                "resource_exact_variant_set_gate_pass": bool_text(
                    resource_exact_set_gate_pass
                ),
                "exact_variant_set_gate_pass": bool_text(
                    exact_variant_set_gate_pass
                ),
                "ptx_section_count": len(ptx_entries),
                "sass_section_count": len(sass_entries),
                "resource_section_count": len(resource_entries),
                "section_multiplicity_gate_pass": bool_text(section_gate_pass),
                "function_name_consistent": bool_text(function_name_consistent),
                "sass_arch_header_present": bool_text(sass_arch_header_present),
                "ptx_ex2_approx_f32_static_count": ptx_f32_count,
                "ptx_ex2_approx_ftz_f32_static_count": ptx_ftz_f32_count,
                "ptx_ex2_approx_f16_static_count": ptx_f16_count,
                "ptx_ex2_approx_f16x2_static_count": ptx_f16x2_count,
                "expected_ptx_ex2_approx_f32_static_count": expected_or_negative[
                    "ptx_f32"
                ],
                "expected_ptx_ex2_approx_ftz_f32_static_count": expected_or_negative[
                    "ptx_ftz_f32"
                ],
                "expected_ptx_ex2_approx_f16_static_count": expected_or_negative[
                    "ptx_f16"
                ],
                "expected_ptx_ex2_approx_f16x2_static_count": expected_or_negative[
                    "ptx_f16x2"
                ],
                "ptx_opcode_count_gate_pass": bool_text(ptx_opcode_gate_pass),
                "sass_mufu_ex2_plain_static_count": sass_plain_count,
                "sass_mufu_ex2_f16_static_count": sass_f16_count,
                "expected_sass_mufu_ex2_plain_static_count": expected_or_negative[
                    "sass_plain"
                ],
                "expected_sass_mufu_ex2_f16_static_count": expected_or_negative[
                    "sass_f16"
                ],
                "sass_opcode_count_gate_pass": bool_text(sass_opcode_gate_pass),
                "sass_predicated_mufu_ex2_plain_static_count": pred_plain_count,
                "sass_predicated_mufu_ex2_f16_static_count": pred_f16_count,
                "expected_sass_predicated_mufu_ex2_plain_static_count": expected_or_negative[
                    "pred_plain"
                ],
                "expected_sass_predicated_mufu_ex2_f16_static_count": expected_or_negative[
                    "pred_f16"
                ],
                "predicated_probe_count_gate_pass": bool_text(
                    predicated_probe_gate_pass
                ),
                "sass_prmt_static_count": prmt_count,
                "sass_uprmt_static_count": uprmt_count,
                "sass_prmt_or_uprmt_static_count": prmt_count + uprmt_count,
                "sass_prmt_or_uprmt_present": bool_text(
                    prmt_or_uprmt_present
                ),
                "packed_path_prmt_observation_pass": bool_text(
                    packed_path_prmt_observation_pass
                ),
                "sass_ldl_static_count": ldl_count,
                "sass_stl_static_count": stl_count,
                "resource_registers": join_ints(registers),
                "resource_shared_bytes": join_ints(shared_bytes),
                "resource_stack_bytes": join_ints(stack_bytes),
                "resource_local_bytes": join_ints(local_bytes),
                "resource_metadata_gate_pass": bool_text(
                    resource_metadata_gate_pass
                ),
                "spill_local_gate_pass": bool_text(spill_local_gate_pass),
                "verdict": verdict,
                "failure_reasons": "|".join(failure_reasons),
                "ptx_functions": "|".join(ptx_names),
                "sass_functions": "|".join(sass_names),
                "resource_functions": "|".join(resource_names),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"{row['mode']}/{row['exp_implementation']}/{row['cache_policy']}: "
            f"{row['verdict']}"
        )
    passed = len(rows) == len(EXPECTED_VARIANTS) and all(
        row["verdict"] == "pass" for row in rows
    )
    print(f"audit_status={'pass' if passed else 'fail'}")
    print(f"binary_sha256={binary_sha256}")
    print(f"output_csv={args.out}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
