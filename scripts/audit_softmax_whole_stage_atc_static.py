#!/usr/bin/env python3
"""Fail-closed PTX/SASS audit for the RTX 3090 whole-stage ATC binary.

The audit proves a deliberately narrow compiler contract:

* the frozen binary contains one sm_86 specialization for every
  ``S=1024 × stage × precision policy`` cell;
* control and treatment are represented by one kernel symbol with a runtime
  integer flag, not separate kernels;
* the sm_86 machine code derives a predicate from the runtime flag and uses it
  to guard a distinct treatment-only arithmetic path;
* that path contains the selected exp, max+sum, or normalization operations
  with the policy-specific lowering; and
* the added arithmetic result remains data-dependent on the final live-sink
  store.  Merely selecting a role tag or another integer constant is never
  accepted as evidence that an added floating-point stage survived ptxas.

PTX records the source-level intent.  SASS is the authoritative compiler
survival gate.  Energy still comes from NVML; this script does not turn
instruction counts into power or energy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "softmax_whole_stage_atc_static_audit_v2"
KERNEL_CONTRACT = "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"
TARGET_PROFILE = "rtx3090"
CUDA_ARCH = 86
SOFTMAX_COLS = 1024
STAGES = {0: "exp", 1: "reduction", 2: "normalization"}
POLICIES = {0: "fp32", 1: "fp16_scalar", 2: "fp16x2"}
REQUIRED_KEYS = {
    (SOFTMAX_COLS, stage, policy)
    for stage in STAGES
    for policy in POLICIES
}

PTX_ENTRY_RE = re.compile(
    r"^\s*(?:\.visible\s+)?\.entry\s+(\S+?)\s*\(", re.MULTILINE
)
SASS_FUNCTION_RE = re.compile(
    r"^\s*Function\s*:\s*(\S+)\s*$", re.MULTILINE
)
KERNEL_RE = re.compile(
    r"whole_softmax_stage_atc_kernelILi(?P<cols>\d+)"
    r"ELNS0_5StageE(?P<stage>\d+)ELNS0_6PolicyE(?P<policy>\d+)EE"
)

PTX_PATTERNS = {
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
    "rcp_f32": re.compile(
        r"(?<![\w.])rcp(?:\.[A-Za-z0-9_]+)*\.f32(?![\w.])",
        re.IGNORECASE,
    ),
    "conditional_branch": re.compile(r"\bbra(?:\.[A-Za-z0-9_]+)*\b"),
    "predicate_set": re.compile(r"\bsetp(?:\.[A-Za-z0-9_]+)*\b"),
    "global_store": re.compile(r"\bst\.global(?:\.[A-Za-z0-9_]+)*\b"),
    "u32_parameter": re.compile(r"^\s*\.param\s+\.u32\b", re.MULTILINE),
    "u32_parameter_load": re.compile(r"\bld\.param\.u32\b"),
}

SASS_PATTERNS = {
    "branch": re.compile(r"\bBRA\b"),
    "global_store": re.compile(r"\bSTG(?:\.|\s)"),
    "mufu_ex2": re.compile(r"\bMUFU\.EX2(?:\.F16)?\b"),
    "mufu_rcp": re.compile(r"\bMUFU\.RCP(?:\.F16(?:X2)?)?\b"),
    "f32_mul": re.compile(r"\bFMUL\b"),
    "f32_max": re.compile(r"\bFMNMX\b"),
    "f32_add": re.compile(r"\bFADD\b"),
    "half_mul": re.compile(r"\bHMUL2\b"),
    "half_add": re.compile(r"\bHADD2\b"),
    "half_max": re.compile(r"\bHMNMX2\b"),
    "half_to_f32": re.compile(r"\bHADD2\.F32\b"),
    "f32_to_half": re.compile(r"\bF2FP(?:\.|\s)"),
    "extra_flag_parameter": re.compile(r"c\[0x0\]\[0x198\]"),
    "sink_parameter": re.compile(r"c\[0x0\]\[0x180\]"),
}

SASS_INSTRUCTION_RE = re.compile(
    r"^\s*/\*(?P<address>[0-9a-fA-F]+)\*/\s*"
    r"(?:(?P<predicate>@!?(?:U?P\d+|U?PT))\s+)?"
    r"(?P<opcode>[A-Z][A-Z0-9_.]*)"
    r"(?:\s+(?P<operands>.*?))?\s*;\s*(?:/\*|$)"
)
REGISTER_RE = re.compile(r"(?<![A-Za-z0-9_])(?:UR|R)\d+(?![A-Za-z0-9_])")
PREDICATE_RE = re.compile(r"(?<![A-Za-z0-9_])(?:UP|P)\d+(?![A-Za-z0-9_])")
EXTRA_FLAG_PARAMETER_RE = re.compile(r"c\[0x0\]\[0x198\]")
SINK_PARAMETER_RE = re.compile(r"c\[0x0\]\[0x180\]")
STORE_VALUE_RE = re.compile(r"\],\s*((?:UR|R)\d+)(?:\.[A-Za-z0-9_]+)?\s*$")
MEMORY_ADDRESS_RE = re.compile(r"\[([^\]]+)\]")
LOG2E_IMMEDIATE_RE = re.compile(r"(?<!\d)1\.442(?:3828125|6950216293334961)?")


@dataclass(frozen=True)
class SassInstruction:
    """One decoded text instruction from ``cuobjdump --dump-sass``."""

    address: int
    predicate: str | None
    predicate_negated: bool
    opcode: str
    operands: str
    text: str


class AuditError(RuntimeError):
    """Raised when the frozen compiler contract is not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )


def find_cuobjdump(explicit: str | None) -> str:
    candidates = [
        candidate
        for candidate in (
            explicit,
            os.environ.get("CUOBJDUMP"),
            shutil.which("cuobjdump"),
        )
        if candidate
    ]
    for candidate in candidates:
        path = Path(str(candidate)).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
        discovered = shutil.which(str(candidate))
        if discovered:
            return str(Path(discovered).resolve())
    raise AuditError(
        "cuobjdump was not found; source scripts/activate_softmax_experiment_env.sh"
    )


def run_cuobjdump(executable: str, option: str, binary: Path) -> str:
    completed = subprocess.run(
        [executable, option, str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AuditError(detail or f"cuobjdump {option} failed")
    return completed.stdout


def named_sections(
    text: str, pattern: re.Pattern[str]
) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    return [
        (
            match.group(1),
            text[
                match.start() : (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(text)
                )
            ],
        )
        for index, match in enumerate(matches)
    ]


def grouped_kernel_sections(
    sections: Iterable[tuple[str, str]],
) -> dict[tuple[int, int, int], list[tuple[str, str]]]:
    grouped: dict[tuple[int, int, int], list[tuple[str, str]]] = defaultdict(list)
    for name, body in sections:
        match = KERNEL_RE.search(name)
        if match is not None:
            key = (
                int(match.group("cols")),
                int(match.group("stage")),
                int(match.group("policy")),
            )
            grouped[key].append((name, body))
    return dict(grouped)


def count_patterns(
    body: str, patterns: dict[str, re.Pattern[str]]
) -> dict[str, int]:
    return {
        name: len(pattern.findall(body))
        for name, pattern in patterns.items()
    }


def parse_sass_instructions(body: str) -> list[SassInstruction]:
    instructions: list[SassInstruction] = []
    for line in body.splitlines():
        match = SASS_INSTRUCTION_RE.match(line)
        if match is None:
            continue
        predicate_token = match.group("predicate")
        predicate = (
            predicate_token.lstrip("@!").upper()
            if predicate_token is not None
            else None
        )
        instructions.append(
            SassInstruction(
                address=int(match.group("address"), 16),
                predicate=predicate,
                predicate_negated=(
                    predicate_token is not None
                    and predicate_token.startswith("@!")
                ),
                opcode=match.group("opcode").upper(),
                operands=(match.group("operands") or "").strip(),
                text=line.strip(),
            )
        )
    return instructions


def operand_fields(instruction: SassInstruction) -> list[str]:
    return [
        value.strip()
        for value in instruction.operands.split(",")
        if value.strip()
    ]


def value_destination(instruction: SassInstruction) -> str | None:
    if instruction.opcode.startswith(
        (
            "ST",
            "BRA",
            "EXIT",
            "BAR",
            "MEMBAR",
            "NANOSLEEP",
            "NOP",
            "YIELD",
        )
    ):
        return None
    fields = operand_fields(instruction)
    if not fields:
        return None
    match = REGISTER_RE.fullmatch(fields[0].split(".", 1)[0])
    return match.group(0) if match is not None else None


def value_sources(instruction: SassInstruction) -> set[str]:
    registers = REGISTER_RE.findall(instruction.operands)
    destination = value_destination(instruction)
    if destination is not None and registers and registers[0] == destination:
        registers = registers[1:]
    return set(registers)


def predicate_destination(instruction: SassInstruction) -> str | None:
    if "SETP" not in instruction.opcode and not instruction.opcode.startswith(
        ("PLOP", "R2P")
    ):
        return None
    fields = operand_fields(instruction)
    if not fields:
        return None
    match = PREDICATE_RE.search(fields[0])
    return match.group(0) if match is not None else None


def branch_target(instruction: SassInstruction) -> int | None:
    if not instruction.opcode.startswith("BRA"):
        return None
    matches = re.findall(r"0x([0-9a-fA-F]+)", instruction.operands)
    return int(matches[-1], 16) if matches else None


def shared_address(instruction: SassInstruction) -> str | None:
    match = MEMORY_ADDRESS_RE.search(instruction.operands)
    if match is None:
        return None
    return re.sub(r"\.reuse\b", "", match.group(1).replace(" ", ""))


def comparison_truth_when_treatment(opcode: str) -> bool | None:
    """Return predicate truth for ``extra_stage_pass == 1``.

    The audited command contract restricts the runtime value to zero or one.
    ptxas currently emits either an equality or inequality comparison with
    zero.  Other relations are rejected rather than guessed.
    """

    components = opcode.split(".")
    if "NE" in components:
        return True
    if "EQ" in components:
        return False
    return None


def p2r_predicate_truth(
    instruction: SassInstruction,
    predicate_truth: dict[str, bool],
) -> bool | None:
    """Map an exact one-bit ``P2R`` mask back to its predicate provenance."""

    if not instruction.opcode.startswith("P2R"):
        return None
    masks = re.findall(r"0x([0-9a-fA-F]+)", instruction.operands)
    if not masks:
        return None
    mask = int(masks[-1], 16)
    if mask <= 0 or mask & (mask - 1):
        return None
    predicate_index = mask.bit_length() - 1
    return predicate_truth.get(f"P{predicate_index}")


def preserves_boolean_value(instruction: SassInstruction) -> bool:
    """Allow only explicit register-copy lowering for flag GPR provenance."""

    return "MOV" in instruction.opcode.split(".")


def treatment_controlled_indices(
    instructions: list[SassInstruction],
) -> tuple[set[int], list[dict[str, Any]]]:
    """Find treatment-only SASS instructions controlled by the last argument.

    Predicate provenance is tracked from ``c[0][0x198]`` through direct
    ``ISETP`` or uniform ``ULDC`` + ``UISETP`` lowering.  A canonical forward
    branch whose fall-through executes only for treatment contributes one
    control-flow range.  Directly predicated treatment instructions are also
    accepted.  Constant selection (``SEL``/``USEL``) deliberately contributes
    no controlled arithmetic range.
    """

    # The boolean value means "this GPR is non-zero in treatment".  Keeping
    # the sense matters when ptxas spills a predicate through P2R and later
    # reconstructs it with ISETP.EQ rather than ISETP.NE.
    flag_values: dict[str, bool] = {}
    shared_flag_addresses: dict[str, bool] = {}
    predicate_truth: dict[str, bool] = {}
    direct_indices: set[int] = set()
    direct_evidence: list[dict[str, Any]] = []
    ranges: list[tuple[int, int, dict[str, Any]]] = []

    for index, instruction in enumerate(instructions):
        if instruction.predicate in predicate_truth:
            predicate_true_in_treatment = predicate_truth[
                instruction.predicate
            ]
            executes_in_treatment = (
                not predicate_true_in_treatment
                if instruction.predicate_negated
                else predicate_true_in_treatment
            )
            if executes_in_treatment and not instruction.opcode.startswith(
                "BRA"
            ):
                direct_indices.add(index)
                direct_evidence.append(
                    {
                        "control_kind": "predicate",
                        "instruction_address": (
                            f"0x{instruction.address:x}"
                        ),
                        "predicate": (
                            ("!" if instruction.predicate_negated else "")
                            + str(instruction.predicate)
                        ),
                    }
                )

        target = branch_target(instruction)
        if (
            target is not None
            and target > instruction.address
            and instruction.predicate in predicate_truth
        ):
            predicate_true_in_treatment = predicate_truth[
                instruction.predicate
            ]
            branch_taken_in_treatment = (
                not predicate_true_in_treatment
                if instruction.predicate_negated
                else predicate_true_in_treatment
            )
            if not branch_taken_in_treatment:
                end_index = next(
                    (
                        candidate
                        for candidate in range(index + 1, len(instructions))
                        if instructions[candidate].address >= target
                    ),
                    len(instructions),
                )
                if end_index > index + 1:
                    evidence = {
                        "control_kind": "forward_branch_fallthrough",
                        "flag_branch_address": f"0x{instruction.address:x}",
                        "branch_target": f"0x{target:x}",
                        "predicate": (
                            ("!" if instruction.predicate_negated else "")
                            + str(instruction.predicate)
                        ),
                        "first_controlled_address": (
                            f"0x{instructions[index + 1].address:x}"
                        ),
                        "last_controlled_address": (
                            f"0x{instructions[end_index - 1].address:x}"
                        ),
                    }
                    ranges.append((index + 1, end_index, evidence))

        source_values = value_sources(instruction)
        destination = value_destination(instruction)
        source_flag_senses = {
            flag_values[source]
            for source in source_values
            if source in flag_values
        }
        flag_loaded_from_shared: bool | None = None
        address = shared_address(instruction)
        if instruction.opcode.startswith("STS") and address is not None:
            value = store_value(instruction)
            if value is not None and value in flag_values:
                shared_flag_addresses[address] = flag_values[value]
            elif instruction.predicate is None:
                shared_flag_addresses.pop(address, None)
        elif (
            instruction.opcode.startswith("LDS")
            and destination is not None
            and address in shared_flag_addresses
        ):
            flag_loaded_from_shared = shared_flag_addresses[address]

        if destination is not None:
            if EXTRA_FLAG_PARAMETER_RE.search(instruction.operands):
                flag_values[destination] = True
            elif flag_loaded_from_shared is not None:
                flag_values[destination] = flag_loaded_from_shared
            elif (
                p2r_truth := p2r_predicate_truth(
                    instruction, predicate_truth
                )
            ) is not None:
                flag_values[destination] = p2r_truth
            elif (
                len(source_flag_senses) == 1
                and preserves_boolean_value(instruction)
            ):
                flag_values[destination] = next(
                    iter(source_flag_senses)
                )
            else:
                flag_values.pop(destination, None)

        predicate_output = predicate_destination(instruction)
        if predicate_output is not None:
            comparison_nonzero_truth = comparison_truth_when_treatment(
                instruction.opcode
            )
            direct_flag_comparison = (
                EXTRA_FLAG_PARAMETER_RE.search(instruction.operands)
                is not None
            )
            if direct_flag_comparison:
                source_nonzero_in_treatment: bool | None = True
            elif len(source_flag_senses) == 1:
                source_nonzero_in_treatment = next(
                    iter(source_flag_senses)
                )
            else:
                source_nonzero_in_treatment = None
            if (
                comparison_nonzero_truth is not None
                and source_nonzero_in_treatment is not None
            ):
                predicate_truth[predicate_output] = (
                    source_nonzero_in_treatment
                    if comparison_nonzero_truth
                    else not source_nonzero_in_treatment
                )
            else:
                predicate_truth.pop(predicate_output, None)

    controlled = set(direct_indices)
    evidence_rows: list[dict[str, Any]] = list(direct_evidence)
    for start, end, evidence in ranges:
        controlled.update(range(start, end))
        evidence_rows.append(evidence)
    return controlled, evidence_rows


def is_exp_scale(instruction: SassInstruction, policy: int) -> bool:
    opcode_match = (
        instruction.opcode.startswith("FMUL")
        if policy == 0
        else instruction.opcode.startswith("HMUL2")
    )
    return opcode_match and LOG2E_IMMEDIATE_RE.search(
        instruction.operands
    ) is not None


def is_exp(instruction: SassInstruction, policy: int) -> bool:
    if not instruction.opcode.startswith("MUFU.EX2"):
        return False
    if policy == 0:
        return ".F16" not in instruction.opcode
    return ".F16" in instruction.opcode


def is_reduction_max(instruction: SassInstruction, policy: int) -> bool:
    expected = "FMNMX" if policy == 0 else "HMNMX2"
    return instruction.opcode.startswith(expected)


def is_reduction_add(instruction: SassInstruction, policy: int) -> bool:
    expected = "FADD" if policy == 0 else "HADD2"
    return instruction.opcode.startswith(expected) and not (
        policy != 0 and ".F32" in instruction.opcode
    )


def is_reciprocal(instruction: SassInstruction) -> bool:
    return instruction.opcode.startswith("MUFU.RCP")


def is_normalization_mul(
    instruction: SassInstruction, policy: int
) -> bool:
    expected = "FMUL" if policy == 0 else "HMUL2"
    return instruction.opcode.startswith(expected)


def is_half_to_float(instruction: SassInstruction) -> bool:
    return instruction.opcode.startswith("HADD2.F32")


def is_float_to_half(instruction: SassInstruction) -> bool:
    return instruction.opcode.startswith("F2FP")


def store_value(instruction: SassInstruction) -> str | None:
    match = STORE_VALUE_RE.search(instruction.operands)
    return match.group(1) if match is not None else None


def live_sink_store_index(
    instructions: list[SassInstruction],
) -> int | None:
    """Return the final sink store, rejecting ambiguous parameter provenance."""

    stores = [
        index
        for index, instruction in enumerate(instructions)
        if instruction.opcode.startswith("STG")
    ]
    if not stores:
        return None
    sink_store = stores[-1]
    if not any(
        SINK_PARAMETER_RE.search(instruction.operands)
        for instruction in instructions[: sink_store + 1]
    ):
        return None
    return sink_store


def producer_reaches_consumer(
    instructions: list[SassInstruction],
    producer_indices: set[int],
    consumer_indices: set[int],
) -> bool:
    """Conservative register def-use proof between two controlled operations."""

    tainted: set[str] = set()
    for index, instruction in enumerate(instructions):
        sources = value_sources(instruction)
        if index in consumer_indices and bool(sources & tainted):
            return True
        destination = value_destination(instruction)
        if destination is None:
            continue
        source_tainted = bool(sources & tainted)
        if index in producer_indices or source_tainted:
            tainted.add(destination)
        elif instruction.predicate is None:
            tainted.discard(destination)
    return False


def producers_reach_sink(
    instructions: list[SassInstruction],
    producer_indices: set[int],
    sink_index: int,
) -> bool:
    """Trace added-stage outputs through registers/shared memory to the sink.

    Shared-memory reductions require a limited alias abstraction: a tainted
    ``STS`` makes a later ``LDS`` tainted until the end of the loop body.  This
    is intentionally one-way and only begins from an already verified
    treatment-only floating-point producer.  Role-tag constants cannot seed
    this analysis.
    """

    tainted: set[str] = set()
    shared_tainted = False
    for index, instruction in enumerate(instructions):
        sources = value_sources(instruction)
        if index == sink_index:
            value = store_value(instruction)
            return value is not None and value in tainted

        destination = value_destination(instruction)
        if index in producer_indices and destination is not None:
            tainted.add(destination)

        if instruction.opcode.startswith("STS"):
            value = store_value(instruction)
            if value is not None and value in tainted:
                shared_tainted = True
            continue

        if instruction.opcode.startswith("LDS"):
            if destination is not None:
                if shared_tainted:
                    tainted.add(destination)
                elif instruction.predicate is None:
                    tainted.discard(destination)
            continue

        if destination is None or index in producer_indices:
            continue
        source_tainted = bool(sources & tainted)
        if source_tainted:
            tainted.add(destination)
        elif instruction.predicate is None:
            tainted.discard(destination)
    return False


def added_stage_sass_evidence(
    body: str, stage: int, policy: int
) -> dict[str, Any]:
    instructions = parse_sass_instructions(body)
    require(instructions, "SASS instruction parser returned no instructions")
    controlled, control_evidence = treatment_controlled_indices(instructions)
    require(
        controlled,
        (
            "extra_stage_pass has no treatment-only forward branch block "
            "or predicate-dominated instruction"
        ),
    )
    sink_index = live_sink_store_index(instructions)
    require(
        sink_index is not None,
        "final live-sink STG cannot be tied to kernel parameter 0x180",
    )
    assert sink_index is not None

    def matching_indices(predicate: Any) -> set[int]:
        return {
            index
            for index in controlled
            if predicate(instructions[index])
        }

    operations: dict[str, set[int]]
    if stage == 0:
        scale = matching_indices(
            lambda instruction: is_exp_scale(instruction, policy)
        )
        ex2 = matching_indices(
            lambda instruction: is_exp(instruction, policy)
        )
        require(scale, "treatment-only exp path lacks log2(e) scale")
        require(ex2, "treatment-only exp path lacks policy-typed MUFU.EX2")
        require(
            producer_reaches_consumer(instructions, scale, ex2),
            "treatment-only log2(e) scale does not feed MUFU.EX2",
        )
        require(
            producers_reach_sink(instructions, ex2, sink_index),
            "treatment-only MUFU.EX2 result does not reach live sink",
        )
        operations = {"log2e_scale": scale, "ex2": ex2}
    elif stage == 1:
        maximum = matching_indices(
            lambda instruction: is_reduction_max(instruction, policy)
        )
        addition = matching_indices(
            lambda instruction: is_reduction_add(instruction, policy)
        )
        require(maximum, "treatment-only reduction path lacks maximum")
        require(addition, "treatment-only reduction path lacks sum addition")
        require(
            producers_reach_sink(instructions, maximum, sink_index),
            "treatment-only maximum result does not reach live sink",
        )
        require(
            producers_reach_sink(instructions, addition, sink_index),
            "treatment-only sum result does not reach live sink",
        )
        operations = {"maximum": maximum, "sum_add": addition}
    else:
        reciprocal = matching_indices(is_reciprocal)
        multiply = matching_indices(
            lambda instruction: is_normalization_mul(instruction, policy)
        )
        require(
            reciprocal,
            "treatment-only normalization path lacks reciprocal",
        )
        require(
            multiply,
            "treatment-only normalization path lacks policy-typed multiply",
        )
        require(
            producer_reaches_consumer(instructions, reciprocal, multiply),
            "treatment-only reciprocal does not feed normalization multiply",
        )
        if policy != 0:
            half_to_float = matching_indices(is_half_to_float)
            float_to_half = matching_indices(is_float_to_half)
            require(
                half_to_float,
                "FP16 reciprocal path lacks half-to-FP32 lowering",
            )
            require(
                float_to_half,
                "FP16 reciprocal path lacks FP32-to-half lowering",
            )
            require(
                producer_reaches_consumer(
                    instructions, reciprocal, float_to_half
                ),
                "FP16 reciprocal does not feed FP32-to-half conversion",
            )
            operations = {
                "half_to_f32": half_to_float,
                "rcp_f32": reciprocal,
                "f32_to_half": float_to_half,
                "multiply_f16": multiply,
            }
        else:
            operations = {
                "rcp_f32": reciprocal,
                "multiply_f32": multiply,
            }
        require(
            producers_reach_sink(instructions, multiply, sink_index),
            "treatment-only normalization multiply does not reach live sink",
        )

    return {
        "flag_parameter_offset": "0x198",
        "sink_parameter_offset": "0x180",
        "controlled_branch_count": sum(
            evidence["control_kind"] == "forward_branch_fallthrough"
            for evidence in control_evidence
        ),
        "controlled_predicate_instruction_count": sum(
            evidence["control_kind"] == "predicate"
            for evidence in control_evidence
        ),
        "control_evidence": control_evidence,
        "operation_addresses": {
            name: [
                f"0x{instructions[index].address:x}"
                for index in sorted(indices)
            ]
            for name, indices in operations.items()
        },
        "sink_store_address": f"0x{instructions[sink_index].address:x}",
        "result_to_sink_dataflow": "pass",
    }


def capture_metadata(path: Path, output_path: Path) -> dict[str, str]:
    try:
        display = path.resolve().relative_to(output_path.parent.resolve())
        path_value = display.as_posix()
    except ValueError:
        path_value = str(path.resolve())
    return {"path": path_value, "sha256": sha256_file(path)}


def audit(binary: Path, cuobjdump: str, output: Path, capture_dir: Path) -> dict[str, Any]:
    binary = binary.resolve()
    require(binary.is_file(), f"binary is missing: {binary}")
    listing = run_cuobjdump(cuobjdump, "--list-elf", binary)
    ptx = run_cuobjdump(cuobjdump, "--dump-ptx", binary)
    sass = run_cuobjdump(cuobjdump, "--dump-sass", binary)

    capture_dir.mkdir(parents=True, exist_ok=True)
    capture_paths = {
        "ptx": capture_dir / "dump_ptx.txt",
        "sass": capture_dir / "dump_sass.txt",
        "list_elf": capture_dir / "list_elf.txt",
    }
    atomic_text(capture_paths["ptx"], ptx)
    atomic_text(capture_paths["sass"], sass)
    atomic_text(capture_paths["list_elf"], listing)

    ptx_grouped = grouped_kernel_sections(named_sections(ptx, PTX_ENTRY_RE))
    sass_grouped = grouped_kernel_sections(
        named_sections(sass, SASS_FUNCTION_RE)
    )
    ptx_required = {
        key: ptx_grouped.get(key, [])
        for key in sorted(REQUIRED_KEYS)
    }
    sass_required = {
        key: sass_grouped.get(key, [])
        for key in sorted(REQUIRED_KEYS)
    }

    checks: dict[str, str] = {}

    def check(name: str, condition: bool, detail: str) -> None:
        require(condition, f"{name}: {detail}")
        checks[name] = "pass"

    architectures = sorted(
        {int(value) for value in re.findall(r"\.sm_(\d+)\.cubin\b", listing)}
    )
    check(
        "target_native_sm86",
        CUDA_ARCH in architectures,
        f"observed cubin architectures {architectures}",
    )
    check(
        "required_ptx_specializations",
        all(len(entries) == 1 for entries in ptx_required.values()),
        "every S1024 stage×policy cell must have exactly one PTX entry",
    )
    check(
        "required_sass_specializations",
        all(len(entries) == 1 for entries in sass_required.values()),
        "every S1024 stage×policy cell must have exactly one SASS function",
    )
    ptx_names = {key: entries[0][0] for key, entries in ptx_required.items()}
    sass_names = {
        key: entries[0][0] for key, entries in sass_required.items()
    }
    check(
        "ptx_sass_symbol_identity",
        ptx_names == sass_names,
        "PTX and SASS specialization symbols differ",
    )
    all_kernel_names = [
        name
        for entries in ptx_grouped.values()
        for name, _ in entries
    ]
    check(
        "no_role_specific_kernel_symbols",
        all(
            "control" not in name.lower() and "treatment" not in name.lower()
            for name in all_kernel_names
        ),
        "found a role-specific control/treatment kernel symbol",
    )

    ptx_counts: dict[tuple[int, int, int], dict[str, int]] = {}
    sass_counts: dict[tuple[int, int, int], dict[str, int]] = {}
    specialization_rows: list[dict[str, Any]] = []
    for key in sorted(REQUIRED_KEYS):
        ptx_name, ptx_body = ptx_required[key][0]
        sass_name, sass_body = sass_required[key][0]
        observed_ptx = count_patterns(ptx_body, PTX_PATTERNS)
        observed_sass = count_patterns(sass_body, SASS_PATTERNS)
        ptx_counts[key] = observed_ptx
        sass_counts[key] = observed_sass
        cols, stage, policy = key
        check(
            f"runtime_flag_{stage}_{policy}",
            observed_ptx["u32_parameter"] >= 1
            and observed_ptx["u32_parameter_load"] >= 1
            and observed_ptx["predicate_set"] >= 1
            and observed_ptx["conditional_branch"] >= 1,
            f"{STAGES[stage]}/{POLICIES[policy]} lacks a live runtime flag branch",
        )
        check(
            f"live_sink_store_{stage}_{policy}",
            observed_ptx["global_store"] >= 2
            and observed_sass["global_store"] >= 2,
            f"{STAGES[stage]}/{POLICIES[policy]} lacks output+sink stores",
        )
        try:
            stage_evidence = added_stage_sass_evidence(
                sass_body, stage, policy
            )
        except AuditError as error:
            raise AuditError(
                f"sass_added_stage_{stage}_{policy}: "
                f"{STAGES[stage]}/{POLICIES[policy]}: {error}"
            ) from error
        check(
            f"sass_added_stage_{stage}_{policy}",
            stage_evidence["result_to_sink_dataflow"] == "pass",
            (
                f"{STAGES[stage]}/{POLICIES[policy]} lacks a "
                "flag-controlled live added-stage path"
            ),
        )
        specialization_rows.append(
            {
                "softmax_cols": cols,
                "stage_id": stage,
                "stage": STAGES[stage],
                "policy_id": policy,
                "policy": POLICIES[policy],
                "symbol": ptx_name,
                "ptx_section_sha256": sha256_bytes(
                    ptx_body.encode("utf-8")
                ),
                "sass_section_sha256": sha256_bytes(
                    sass_body.encode("utf-8")
                ),
                "ptx_opcode_counts": observed_ptx,
                "sass_opcode_counts": observed_sass,
                "sass_added_stage_evidence": stage_evidence,
                "sass_symbol": sass_name,
            }
        )

    type_suffix = {0: "f32", 1: "f16", 2: "f16x2"}
    for policy, suffix in type_suffix.items():
        exp_key = (SOFTMAX_COLS, 0, policy)
        reduction_key = (SOFTMAX_COLS, 1, policy)
        norm_key = (SOFTMAX_COLS, 2, policy)
        ex2_name = f"ex2_{suffix}"
        max_name = f"max_{suffix}"
        add_name = f"add_{suffix}"
        mul_name = f"mul_{suffix}"
        check(
            f"policy_opcode_types_{policy}",
            all(
                ptx_counts[(SOFTMAX_COLS, stage, policy)][ex2_name] > 0
                and ptx_counts[(SOFTMAX_COLS, stage, policy)][max_name] > 0
                and ptx_counts[(SOFTMAX_COLS, stage, policy)][add_name] > 0
                and ptx_counts[(SOFTMAX_COLS, stage, policy)][mul_name] > 0
                for stage in STAGES
            ),
            f"{POLICIES[policy]} does not retain its declared PTX data type",
        )
        check(
            f"extra_exp_pass_{policy}",
            ptx_counts[exp_key][ex2_name]
            > ptx_counts[reduction_key][ex2_name]
            and ptx_counts[exp_key][ex2_name]
            > ptx_counts[norm_key][ex2_name],
            f"{POLICIES[policy]} exp specialization has no extra EX2 pass",
        )
        check(
            f"extra_reduction_pass_{policy}",
            ptx_counts[reduction_key][max_name]
            > ptx_counts[exp_key][max_name]
            and ptx_counts[reduction_key][max_name]
            > ptx_counts[norm_key][max_name]
            and ptx_counts[reduction_key][add_name]
            > ptx_counts[exp_key][add_name]
            and ptx_counts[reduction_key][add_name]
            > ptx_counts[norm_key][add_name],
            f"{POLICIES[policy]} reduction specialization has no extra max+sum pass",
        )
        check(
            f"extra_normalization_pass_{policy}",
            ptx_counts[norm_key]["rcp_f32"]
            > ptx_counts[exp_key]["rcp_f32"]
            and ptx_counts[norm_key]["rcp_f32"]
            > ptx_counts[reduction_key]["rcp_f32"],
            f"{POLICIES[policy]} normalization specialization has no extra reciprocal pass",
        )

    check(
        "same_symbol_runtime_flag",
        len(ptx_names) == len(REQUIRED_KEYS),
        "control/treatment did not collapse to one symbol per cell",
    )
    check(
        "extra_stage_pass_survives",
        all(
            checks[f"extra_exp_pass_{policy}"] == "pass"
            and checks[f"extra_reduction_pass_{policy}"] == "pass"
            and checks[f"extra_normalization_pass_{policy}"] == "pass"
            for policy in POLICIES
        )
        and all(
            checks[f"sass_added_stage_{stage}_{policy}"] == "pass"
            for stage in STAGES
            for policy in POLICIES
        ),
        "one or more selected extra stages was optimized away",
    )
    check(
        "live_sink_dataflow",
        all(
            checks[f"live_sink_store_{stage}_{policy}"] == "pass"
            for stage in STAGES
            for policy in POLICIES
        ),
        "one or more specializations lacks a live sink store",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "generated_at": timestamp(),
        "target_profile": TARGET_PROFILE,
        "cuda_arch": CUDA_ARCH,
        "softmax_cols": SOFTMAX_COLS,
        "kernel_contract": KERNEL_CONTRACT,
        "binary_path": str(binary),
        "binary_sha256": sha256_file(binary),
        "cuobjdump_path": cuobjdump,
        "observed_cubin_architectures": architectures,
        "required_specialization_count": len(REQUIRED_KEYS),
        "observed_specialization_count": len(ptx_names),
        "checks": checks,
        "captures": {
            name: capture_metadata(path, output)
            for name, path in capture_paths.items()
        },
        "specializations": specialization_rows,
        "interpretation": (
            "PTX records same-symbol runtime-flag stage intent; sm86 SASS "
            "proves a flag-controlled policy-typed added arithmetic path and "
            "its data dependence on the live sink; NVML supplies energy"
        ),
    }


def self_test() -> None:
    require(len(REQUIRED_KEYS) == 9, "self-test required key count")
    sample = (
        "_ZN11fp16softmax15whole_stage_atc67_GLOBAL__N__x"
        "whole_softmax_stage_atc_kernelILi1024ELNS0_5StageE2"
        "ELNS0_6PolicyE1EEEv"
    )
    match = KERNEL_RE.search(sample)
    require(match is not None, "self-test symbol parser")
    assert match is not None
    require(
        (
            int(match.group("cols")),
            int(match.group("stage")),
            int(match.group("policy")),
        )
        == (1024, 2, 1),
        "self-test symbol identity",
    )
    valid_exp = """
        /*0010*/ ISETP.NE.AND P0, PT, RZ, c[0x0][0x198], PT ; /* code */
        /*0020*/ @!P0 BRA 0x0060 ; /* code */
        /*0030*/ FMUL R1, R2, 1.4426950216293334961 ; /* code */
        /*0040*/ MUFU.EX2 R3, R1 ; /* code */
        /*0050*/ IADD3 R4, R3, R5, RZ ; /* code */
        /*0060*/ IADD3 R4, R4, R6, RZ ; /* code */
        /*0070*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*0080*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*0090*/ STG.E [R8.64], R4 ; /* code */
    """
    evidence = added_stage_sass_evidence(valid_exp, 0, 0)
    require(
        evidence["result_to_sink_dataflow"] == "pass",
        "self-test valid treatment path",
    )
    valid_if_converted_exp = """
        /*0010*/ ISETP.EQ.AND P4, PT, RZ, c[0x0][0x198], PT ; /* code */
        /*0020*/ @!P4 FMUL R1, R2, 1.4426950216293334961 ; /* code */
        /*0030*/ @!P4 MUFU.EX2 R3, R1 ; /* code */
        /*0040*/ IADD3 R4, R3, R5, RZ ; /* code */
        /*0050*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*0060*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*0070*/ STG.E [R8.64], R4 ; /* code */
    """
    if_converted_evidence = added_stage_sass_evidence(
        valid_if_converted_exp, 0, 0
    )
    require(
        if_converted_evidence[
            "controlled_predicate_instruction_count"
        ]
        == 2,
        "self-test if-converted treatment predicates",
    )
    valid_materialized_flag = """
        /*0010*/ MOV R9, c[0x0][0x198] ; /* code */
        /*0020*/ STS [R10], R9 ; /* code */
        /*0030*/ LDS R11, [R10] ; /* code */
        /*0040*/ ISETP.NE.AND P0, PT, R11, RZ, PT ; /* code */
        /*0050*/ @!P0 BRA 0x0090 ; /* code */
        /*0060*/ FMUL R1, R2, 1.4426950216293334961 ; /* code */
        /*0070*/ MUFU.EX2 R3, R1 ; /* code */
        /*0080*/ IADD3 R4, R3, R5, RZ ; /* code */
        /*0090*/ IADD3 R4, R4, R6, RZ ; /* code */
        /*00a0*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*00b0*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*00c0*/ STG.E [R8.64], R4 ; /* code */
    """
    materialized_evidence = added_stage_sass_evidence(
        valid_materialized_flag, 0, 0
    )
    require(
        materialized_evidence["controlled_branch_count"] == 1,
        "self-test materialized flag provenance",
    )
    valid_p2r_reduction = """
        /*0010*/ ISETP.NE.AND P6, PT, RZ, c[0x0][0x198], PT ; /* code */
        /*0020*/ P2R R20, PR, RZ, 0x40 ; /* code */
        /*0030*/ @!P6 BRA 0x0060 ; /* code */
        /*0040*/ FMNMX R1, R2, R3, !PT ; /* code */
        /*0050*/ IADD3 R9, R9, R1, RZ ; /* code */
        /*0060*/ ISETP.GT.U32.AND P6, PT, R7, 0x1f, PT ; /* code */
        /*0070*/ ISETP.NE.AND P6, PT, R20, RZ, PT ; /* code */
        /*0080*/ @!P6 BRA 0x00b0 ; /* code */
        /*0090*/ FADD R3, R4, R5 ; /* code */
        /*00a0*/ IADD3 R9, R9, R3, RZ ; /* code */
        /*00b0*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*00c0*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*00d0*/ STG.E [R8.64], R9 ; /* code */
    """
    p2r_evidence = added_stage_sass_evidence(
        valid_p2r_reduction, 1, 0
    )
    require(
        p2r_evidence["controlled_branch_count"] == 2,
        "self-test P2R predicate spill/restore provenance",
    )
    p2r_instruction = parse_sass_instructions(
        "/*0010*/ P2R R20, PR, RZ, 0x40 ; /* code */"
    )[0]
    require(
        p2r_predicate_truth(p2r_instruction, {"P6": True}) is True
        and p2r_predicate_truth(
            p2r_instruction, {"P6": False}
        )
        is False,
        "self-test P2R predicate sense",
    )
    multi_bit_p2r = parse_sass_instructions(
        "/*0010*/ P2R R20, PR, RZ, 0x60 ; /* code */"
    )[0]
    require(
        p2r_predicate_truth(
            multi_bit_p2r, {"P5": True, "P6": True}
        )
        is None,
        "self-test multi-bit P2R fail-closed",
    )

    # Regression shape from the rejected v1 binary: the flag only selects a
    # role-tag constant, while all floating-point work is unconditional.
    invalid_role_tag_only = """
        /*0010*/ ISETP.NE.AND P0, PT, RZ, c[0x0][0x198], PT ; /* code */
        /*0020*/ SEL R4, RZ, 0xa5c31e27, !P0 ; /* code */
        /*0030*/ FMUL R1, R2, 1.4426950216293334961 ; /* code */
        /*0040*/ MUFU.EX2 R3, R1 ; /* code */
        /*0050*/ IADD3 R4, R4, R3, RZ ; /* code */
        /*0060*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*0070*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*0080*/ STG.E [R8.64], R4 ; /* code */
    """
    try:
        added_stage_sass_evidence(invalid_role_tag_only, 0, 0)
    except AuditError as error:
        require(
            "no treatment-only forward branch" in str(error),
            "self-test regression rejection reason",
        )
    else:
        raise AuditError("self-test accepted role-tag-only v1 SASS")

    invalid_dead_exp = """
        /*0010*/ ISETP.NE.AND P0, PT, RZ, c[0x0][0x198], PT ; /* code */
        /*0020*/ @!P0 BRA 0x0050 ; /* code */
        /*0030*/ FMUL R1, R2, 1.4426950216293334961 ; /* code */
        /*0040*/ MUFU.EX2 R3, R1 ; /* code */
        /*0050*/ MOV R4, R7 ; /* code */
        /*0060*/ ISETP.NE.AND P1, PT, RZ, c[0x0][0x180], PT ; /* code */
        /*0070*/ IMAD.WIDE.U32 R8, R7, 0x4, c[0x0][0x180] ; /* code */
        /*0080*/ STG.E [R8.64], R4 ; /* code */
    """
    try:
        added_stage_sass_evidence(invalid_dead_exp, 0, 0)
    except AuditError as error:
        require(
            "does not reach live sink" in str(error),
            "self-test dead-result rejection reason",
        )
    else:
        raise AuditError("self-test accepted dead treatment arithmetic")
    print("softmax_whole_stage_atc_static_audit_self_test=pass")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--cuobjdump")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.binary is None or args.out is None:
        raise SystemExit("--binary and --out are required")
    output = args.out.resolve()
    capture_dir = (
        args.capture_dir.resolve()
        if args.capture_dir is not None
        else output.parent / "static_audit"
    )
    payload = audit(
        args.binary,
        find_cuobjdump(args.cuobjdump),
        output,
        capture_dir,
    )
    atomic_json(output, payload)
    print("static_audit_status=pass")
    print(f"specializations={payload['observed_specialization_count']}")
    print(f"static_audit_json={output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AuditError, OSError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        raise SystemExit(2)
