#!/usr/bin/env python3
"""Run a bounded FP16 Softmax operand-rate ATC bracket experiment.

The runner deliberately defaults to one GPU, one S/scale/B setting, one cache
condition, one partial CTA grid, and a same-kernel exp probe.  Comma-separated
condition/grid lists remain available for bounded sensitivity checks.  It
calibrates the *full* treatment separately for each grid and applies the
resulting ITER to both control roles in that pair; it does not duration-match
the control.  The default path runs every ``probe -> full(extra exp) -> probe``
triplet in one CUDA process/context, after one unrecorded warm-up bracket and
with one batch-level idle baseline, so role-to-role process startup and idle
measurement cooling are not part of the bracket.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


EXP_IMPL_METADATA = {
    "fp32": {
        "canonical": "fp32_fast___expf",
        "numerical_check_id": "fp16_softmax_cpu_fp64_v1_pass",
        "native_validation_id": "",
        "exp_input_dtype": "fp32",
        "exp_ptx_instruction": "ex2.approx.f32",
        "results_per_ptx_instruction": 1,
        "xu_documented_results_per_sm_cycle": 16,
    },
    "ptx_f16": {
        "canonical": "ptx_ex2_approx_f16",
        "numerical_check_id": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
        "native_validation_id": "ptx_ex2_f16_all_encodings_v1_pass",
        "exp_input_dtype": "fp16",
        "exp_ptx_instruction": "ex2.approx.f16",
        "results_per_ptx_instruction": 1,
        "xu_documented_results_per_sm_cycle": 0,
    },
    "ptx_f16x2": {
        "canonical": "ptx_ex2_approx_f16x2",
        "numerical_check_id": "fp16_softmax_cpu_fp64_native_ex2_v1_pass",
        "native_validation_id": "ptx_ex2_f16_all_encodings_v1_pass",
        "exp_input_dtype": "fp16x2_packed_b32",
        "exp_ptx_instruction": "ex2.approx.f16x2",
        "results_per_ptx_instruction": 2,
        "xu_documented_results_per_sm_cycle": 0,
    },
}
EXP_RAW_IDENTITY_FIELDS = (
    "exp_impl",
    "exp_input_dtype",
    "special_function_path",
    "exp_ptx_instruction",
    "exp_results_per_ptx_instruction",
    "sass_mufu_ex2_per_ptx_instruction_model",
    "sass_lowering_model_status",
    "expected_control_ex2_scalar_results_per_cta_iter",
    "expected_treatment_ex2_scalar_results_per_cta_iter",
    "expected_probe_ex2_scalar_results_per_cta_iter",
    "expected_control_ex2_ptx_instructions_per_cta_iter",
    "expected_treatment_ex2_ptx_instructions_per_cta_iter",
    "expected_probe_ex2_ptx_instructions_per_cta_iter",
)
A100_PROTOCOL_SOFTMAX_COLS = 512
A100_PROTOCOL_LOGIT_SCALE = 4.0
A100_PROTOCOL_CACHE_CONDITION = "cache_reuse_candidate"
A100_PROTOCOL_CACHE_POLICY = "default"
CONTROL_ROLES = {
    "io": (
        ("io_before", "io", False),
        ("full", "full", False),
        ("io_after", "io", False),
    ),
    "linear": (
        ("linear_before", "linear", False),
        ("full", "full", False),
        ("linear_after", "linear", False),
    ),
    "probe": (
        ("probe_before", "full", False),
        ("full", "full", True),
        ("probe_after", "full", False),
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nvidia_state(gpu_selector: str | int) -> dict[str, str]:
    command = [
        "nvidia-smi",
        f"--id={gpu_selector}",
        "--query-gpu=utilization.gpu,utilization.memory,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return {"state_status": "unavailable", "state_error": result.stderr.strip()}
    fields = [field.strip() for field in result.stdout.strip().split(",")]
    if len(fields) != 4:
        return {"state_status": "unparseable", "state_error": result.stdout.strip()}
    try:
        return {
            "state_status": "ok",
            "gpu_util_pct": f"{float(fields[0]):.3f}",
            "memory_util_pct": f"{float(fields[1]):.3f}",
            "temp_c": f"{float(fields[2]):.3f}",
            "power_w": f"{float(fields[3]):.3f}",
        }
    except ValueError:
        return {"state_status": "unparseable", "state_error": result.stdout.strip()}


def wait_for_quiescence(
    args: argparse.Namespace, gpu_selector: str | int
) -> tuple[dict[str, str], float, bool]:
    """Require consecutive low-util samples after calibration or a prior role."""
    started = time.monotonic()
    consecutive = 0
    last: dict[str, str] = {}
    while time.monotonic() - started <= args.quiescence_timeout_s:
        last = nvidia_state(gpu_selector)
        status = last.get("state_status", "unavailable")
        gpu_util = float(last.get("gpu_util_pct", "nan"))
        memory_util = float(last.get("memory_util_pct", "nan"))
        acceptable = (
            status == "ok"
            and gpu_util <= args.max_gpu_util_pct
            and memory_util <= args.max_memory_util_pct
        )
        consecutive = consecutive + 1 if acceptable else 0
        if consecutive >= args.quiescence_consecutive_samples:
            return last, time.monotonic() - started, True
        time.sleep(args.quiescence_poll_s)
    return last, time.monotonic() - started, False


def run_command(command: list[str], *, dry_run: bool) -> subprocess.CompletedProcess[str] | None:
    print("+", " ".join(command), flush=True)
    if dry_run:
        return None
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    return result


def run_command_with_a100_process_monitor(
    command: list[str], gpu_uuid: str, *, allow_descendants: bool = False
) -> tuple[subprocess.CompletedProcess[str], list[str], list[str]]:
    """Run one persistent batch while allowing only its own CUDA process."""
    print("+", " ".join(command), flush=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stop = threading.Event()
    unexpected: list[str] = []
    monitor_errors: list[str] = []

    def is_descendant(pid: int, ancestor: int) -> bool:
        current = pid
        visited: set[int] = set()
        while current > 1 and current not in visited:
            if current == ancestor:
                return True
            visited.add(current)
            try:
                stat = Path(f"/proc/{current}/stat").read_text(encoding="utf-8")
                # comm may contain spaces/parentheses; fields after the final
                # ')' start with state, then parent PID.
                current = int(stat.rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                return False
        return False

    def monitor() -> None:
        while not stop.is_set():
            try:
                for app in running_compute_apps(gpu_uuid):
                    fields = [field.strip() for field in app.split(",", 2)]
                    pid = int(fields[1]) if len(fields) >= 2 and fields[1].isdigit() else -1
                    if pid != process.pid and not (
                        allow_descendants and is_descendant(pid, process.pid)
                    ):
                        unexpected.append(app)
            except (RuntimeError, ValueError) as error:
                monitor_errors.append(str(error))
            stop.wait(0.25)

    thread = threading.Thread(target=monitor, name="a100-compute-app-monitor", daemon=True)
    thread.start()
    stdout, stderr = process.communicate()
    stop.set()
    thread.join(timeout=2.0)
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {result.returncode}: {' '.join(command)}"
        )
    return result, list(dict.fromkeys(unexpected)), list(dict.fromkeys(monitor_errors))


def common_args(args: argparse.Namespace, condition: str, grid_blocks: int) -> list[str]:
    common = [
        "--gpu-id",
        str(args.gpu_id),
        "--target-profile",
        args.target_profile,
        "--exp-impl",
        args.exp_impl,
        "--softmax-cols",
        str(args.softmax_cols),
        "--blocks-per-sm",
        str(args.blocks_per_sm),
        "--seconds",
        str(args.seconds),
        "--idle-measure-seconds",
        str(args.idle_measure_seconds),
        "--logit-scale",
        str(args.logit_scale),
        "--cache-condition",
        condition,
        "--cache-policy",
        args.cache_policy,
    ]
    if grid_blocks:
        common.extend(("--grid-blocks", str(grid_blocks)))
    return common


def energy_trace_args(args: argparse.Namespace, trace_csv: Path) -> list[str]:
    """Return the trace controls only for energy-bearing role measurements."""
    return [
        "--energy-trace",
        str(args.energy_trace),
        "--energy-trace-sample-ms",
        str(args.energy_trace_sample_ms),
        "--energy-trace-min-updates",
        str(args.energy_trace_min_updates),
        "--energy-trace-output",
        str(trace_csv),
    ]


def parse_calibrated_iters(output: str) -> int:
    match = re.search(r"\bcalibrated_iters=(\d+)\b", output)
    if not match:
        raise RuntimeError("full calibration did not print calibrated_iters")
    return int(match.group(1))


def parse_key_value_output(output: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z0-9_]+", key.strip()):
            metadata[key.strip()] = value.strip()
    return metadata


def exp_metadata(exp_impl: str) -> dict[str, Any]:
    return EXP_IMPL_METADATA[exp_impl]


def output_exp_suffix(exp_impl: str) -> str:
    """Keep legacy FP32 filenames stable while isolating native variants."""
    return "" if exp_impl == "fp32" else f"_{exp_impl}"


def protocol_revision(args: argparse.Namespace, execution: str) -> str:
    if args.exp_impl == "fp32":
        return (
            "fp16_softmax_operand_rate_atc_v5_a100_xu_"
            f"{execution}_{args.control_mode}"
        )
    return (
        "fp16_softmax_operand_rate_atc_v6_native_ex2_"
        f"{execution}_{args.control_mode}_{args.exp_impl}"
    )


def normalize_pci_bus_id(value: str) -> str:
    """Normalize CUDA/NVML PCI spellings such as 0000:17:00.0/00000000:17:00.0."""
    match = re.fullmatch(
        r"\s*([0-9A-Fa-f]{1,8}):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\.([0-7])\s*",
        value,
    )
    if match is None:
        return ""
    domain, bus, device, function = match.groups()
    return f"{int(domain, 16):04x}:{bus.lower()}:{device.lower()}.{function}"


def nvidia_inventory(gpu_selector: str | int) -> dict[str, str]:
    fields = (
        "uuid,pci.bus_id,name,mig.mode.current,compute_mode,persistence_mode,"
        "ecc.mode.current,power.limit,enforced.power.limit,clocks.current.sm,"
        "clocks.current.memory,clocks_event_reasons.active,"
        "clocks_event_reasons.sw_power_cap,"
        "clocks_event_reasons.sw_thermal_slowdown,"
        "clocks_event_reasons.hw_thermal_slowdown,"
        "clocks_event_reasons.hw_power_brake_slowdown,"
        "clocks_event_reasons_counters.sw_power_cap,"
        "clocks_event_reasons_counters.sw_thermal_slowdown,"
        "clocks_event_reasons_counters.hw_thermal_slowdown,"
        "clocks_event_reasons_counters.hw_power_brake_slowdown"
    )
    result = subprocess.run(
        [
            "nvidia-smi",
            f"--id={gpu_selector}",
            f"--query-gpu={fields}",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {
            "inventory_status": "unavailable",
            "inventory_error": result.stderr.strip() or result.stdout.strip(),
        }
    values = [value.strip() for value in result.stdout.strip().split(",")]
    names = fields.split(",")
    if len(values) != len(names):
        return {
            "inventory_status": "unparseable",
            "inventory_error": result.stdout.strip(),
        }
    return {
        "inventory_status": "ok",
        **{f"inventory_{name.replace('.', '_')}": value for name, value in zip(names, values)},
    }


def running_compute_apps(gpu_uuid: str) -> list[str]:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "unable to audit competing compute processes: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.split(",", 1)[0].strip() == gpu_uuid
    ]


A100_STABLE_INVENTORY_FIELDS = (
    "inventory_uuid",
    "inventory_pci_bus_id",
    "inventory_name",
    "inventory_mig_mode_current",
    "inventory_compute_mode",
    "inventory_persistence_mode",
    "inventory_ecc_mode_current",
    "inventory_power_limit",
    "inventory_enforced_power_limit",
)
A100_SLOWDOWN_COUNTER_FIELDS = (
    "inventory_clocks_event_reasons_counters_sw_power_cap",
    "inventory_clocks_event_reasons_counters_sw_thermal_slowdown",
    "inventory_clocks_event_reasons_counters_hw_thermal_slowdown",
    "inventory_clocks_event_reasons_counters_hw_power_brake_slowdown",
)


def nonnegative_counter(value: str) -> int | None:
    try:
        parsed = int(value.strip())
    except (AttributeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def audit_a100_batch_environment(
    baseline: dict[str, str],
    before: dict[str, str],
    after: dict[str, str],
    competitors_before: list[str],
    competitors_during: list[str],
    competitors_after: list[str],
    process_monitor_errors: list[str],
) -> dict[str, str]:
    """Gate identity/state changes while allowing ordinary temperature rise."""
    reasons: list[str] = []
    if any(
        inventory.get("inventory_status") != "ok"
        for inventory in (baseline, before, after)
    ):
        reasons.append("inventory_unavailable")
    for field in A100_STABLE_INVENTORY_FIELDS:
        values = [inventory.get(field, "") for inventory in (baseline, before, after)]
        if not all(values):
            reasons.append(f"missing_{field}")
        elif len(set(values)) != 1:
            reasons.append(f"changed_{field}")
    if competitors_before:
        reasons.append("competing_compute_process_before_batch")
    if competitors_during:
        reasons.append("competing_compute_process_during_batch")
    if competitors_after:
        reasons.append("competing_compute_process_after_batch")
    if process_monitor_errors:
        reasons.append("compute_process_monitor_error")

    deltas: dict[str, str] = {}
    for field in A100_SLOWDOWN_COUNTER_FIELDS:
        start = nonnegative_counter(before.get(field, ""))
        end = nonnegative_counter(after.get(field, ""))
        label = field.removeprefix("inventory_")
        if start is None or end is None:
            reasons.append(f"missing_{label}")
            deltas[f"a100_{label}_delta_us"] = ""
        elif end < start:
            reasons.append(f"reset_{label}")
            deltas[f"a100_{label}_delta_us"] = str(end - start)
        else:
            delta = end - start
            deltas[f"a100_{label}_delta_us"] = str(delta)
            if delta > 0:
                reasons.append(f"increased_{label}")
    return {
        "a100_environment_status": "pass" if not reasons else "fail",
        "a100_environment_reasons": ";".join(dict.fromkeys(reasons)),
        "a100_gpu_uuid": baseline.get("inventory_uuid", ""),
        "a100_inventory_pci_bus_id": normalize_pci_bus_id(
            baseline.get("inventory_pci_bus_id", "")
        ),
        "a100_competing_processes_before": " | ".join(competitors_before),
        "a100_competing_processes_during": " | ".join(competitors_during),
        "a100_competing_processes_after": " | ".join(competitors_after),
        "a100_process_monitor_errors": " | ".join(process_monitor_errors),
        **deltas,
    }


def require_a100_board_preflight(
    binary_metadata: dict[str, str], inventory: dict[str, str], exp_impl: str
) -> None:
    implementation = exp_metadata(exp_impl)
    required_binary = {
        "compute_capability": "8.0",
        "cuda_binary_arch": "80",
        "runtime_sm_count": "108",
        "exp_impl": str(implementation["canonical"]),
        "exp_input_dtype": str(implementation["exp_input_dtype"]),
        "xu_documented_results_per_sm_cycle": str(
            implementation["xu_documented_results_per_sm_cycle"]
        ),
        "smid_sparse_id_self_check": "pass",
    }
    if exp_impl != "fp32":
        required_binary.update(
            {
                "exp_ptx_instruction": str(
                    implementation["exp_ptx_instruction"]
                ),
                "exp_results_per_ptx_instruction": str(
                    implementation["results_per_ptx_instruction"]
                ),
            }
        )
    for field, expected in required_binary.items():
        if binary_metadata.get(field) != expected:
            raise RuntimeError(
                f"A100 binary preflight mismatch for {field}: "
                f"{binary_metadata.get(field, '<missing>')} != {expected}"
            )
    if "a100" not in binary_metadata.get("gpu_name", "").lower():
        raise RuntimeError("A100 binary preflight did not identify an A100 GPU")
    if inventory.get("inventory_status") != "ok":
        raise RuntimeError(f"A100 nvidia-smi inventory is required: {inventory}")
    mig_mode = inventory.get("inventory_mig_mode_current", "").lower()
    if mig_mode != "disabled":
        raise RuntimeError(
            "A100 board-energy measurement requires MIG mode Disabled; "
            f"observed {mig_mode or '<missing>'}"
        )
    gpu_uuid = inventory.get("inventory_uuid", "")
    if not gpu_uuid:
        raise RuntimeError("A100 inventory did not expose the physical GPU UUID")
    cuda_pci = normalize_pci_bus_id(binary_metadata.get("cuda_pci_bus_id", ""))
    nvml_pci = normalize_pci_bus_id(inventory.get("inventory_pci_bus_id", ""))
    if not cuda_pci or not nvml_pci or cuda_pci != nvml_pci:
        raise RuntimeError(
            "A100 CUDA/NVML PCI identity mismatch: "
            f"{binary_metadata.get('cuda_pci_bus_id', '<missing>')} != "
            f"{inventory.get('inventory_pci_bus_id', '<missing>')}"
        )
    competitors = running_compute_apps(gpu_uuid)
    if competitors:
        raise RuntimeError(
            "A100 board-energy preflight found competing compute processes: "
            + " | ".join(competitors)
        )


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def persistent_raw_rows(
    raw_csv: Path,
    pair_prefix: str,
    expected_rows: int,
    idle_policy: str,
    control_mode: str,
    bracket_order: str,
    target_profile: str,
    exp_impl: str,
) -> list[dict[str, str]]:
    """Read exactly the rows emitted by one persistent bracket batch."""
    with raw_csv.open(newline="", encoding="utf-8") as handle:
        rows = [
            dict(row)
            for row in csv.DictReader(handle)
            if row.get("pair_id", "").startswith(f"{pair_prefix}_p")
        ]
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"persistent bracket emitted {len(rows)} rows; expected {expected_rows} for {pair_prefix}"
        )
    required = {
        "execution_model": (
            "persistent_cuda_context_bracket_v3_counterbalanced6"
            if bracket_order == "counterbalanced6"
            else "persistent_cuda_context_bracket_v2"
        ),
        "idle_baseline_scope": idle_policy,
    }
    for field, value in required.items():
        if any(row.get(field) != value for row in rows):
            raise RuntimeError(f"persistent raw metadata mismatch for {field}")
    implementation = exp_metadata(exp_impl)
    required_exp = {
        "exp_impl": str(implementation["canonical"]),
        "exp_input_dtype": str(implementation["exp_input_dtype"]),
        "exp_results_per_ptx_instruction": str(
            implementation["results_per_ptx_instruction"]
        ),
    }
    if exp_impl != "fp32":
        required_exp["exp_ptx_instruction"] = str(
            implementation["exp_ptx_instruction"]
        )
    for field, value in required_exp.items():
        if any(row.get(field) != value for row in rows):
            raise RuntimeError(
                f"persistent raw exponential metadata mismatch for {field}"
            )
    results_per_ptx = int(implementation["results_per_ptx_instruction"])
    for row in rows:
        cols = int(row.get("softmax_cols", "-1"))
        expected_denominators = {
            "expected_control_ex2_scalar_results_per_cta_iter": cols,
            "expected_treatment_ex2_scalar_results_per_cta_iter": 2 * cols,
            "expected_probe_ex2_scalar_results_per_cta_iter": cols,
            "expected_control_ex2_ptx_instructions_per_cta_iter": cols
            // results_per_ptx,
            "expected_treatment_ex2_ptx_instructions_per_cta_iter": 2
            * cols
            // results_per_ptx,
            "expected_probe_ex2_ptx_instructions_per_cta_iter": cols
            // results_per_ptx,
        }
        for field, expected in expected_denominators.items():
            if row.get(field) != str(expected):
                raise RuntimeError(
                    f"persistent raw exponential denominator mismatch for {field}"
                )
    if target_profile == "a100":
        required_a100 = {
            "profile_name": "a100",
            "compute_capability": "8.0",
            "cuda_binary_arch": "80",
            "exp_input_dtype": str(implementation["exp_input_dtype"]),
            "xu_documented_results_per_sm_cycle": str(
                implementation["xu_documented_results_per_sm_cycle"]
            ),
        }
        for field, value in required_a100.items():
            if any(row.get(field) != value for row in rows):
                raise RuntimeError(f"A100 raw metadata mismatch for {field}")
        grids = {int(row.get("grid_blocks", "-1")) for row in rows}
        if len(grids) != 1:
            raise RuntimeError("A100 persistent batch contains multiple CTA grids")
        grid = next(iter(grids))
        if grid not in {27, 54, 108}:
            raise RuntimeError(f"A100 energy batch used an unsupported CTA grid: {grid}")
        for row in rows:
            if (
                int(row.get("runtime_sm_count", "-1")) != 108
                or row.get("smid_all_blocks_observed", "").lower() != "true"
                or int(row.get("smid_unique", "-1")) != grid
                or int(row.get("smid_assignment_max_blocks_per_sm", "-1")) != 1
            ):
                raise RuntimeError(
                    "A100 energy batch failed the one-observed-CTA-per-distinct-SMID gate"
                )
        smid_sets = {row.get("smid_set", "") for row in rows}
        if len(smid_sets) != 1 or not next(iter(smid_sets)):
            raise RuntimeError(
                "A100 energy batch did not retain one exact SMID set across all 18 roles"
            )
    context_ids = {row.get("bracket_context_id", "") for row in rows}
    if len(context_ids) != 1 or not next(iter(context_ids)):
        raise RuntimeError("persistent bracket did not retain one non-empty context id")
    for pair_index in range(expected_rows // 3):
        pair_id = f"{pair_prefix}_p{pair_index:02d}"
        pair_rows = sorted(
            (row for row in rows if row.get("pair_id") == pair_id),
            key=lambda row: int(row.get("sequence_index", "-1")),
        )
        if bracket_order == "counterbalanced6" and pair_index in {1, 2, 5}:
            expected_roles = (
                ("full_before", "full", True),
                ("probe_middle", "full", False),
                ("full_after", "full", True),
            )
        else:
            expected_roles = CONTROL_ROLES[control_mode]
        if len(pair_rows) != len(expected_roles):
            raise RuntimeError(f"persistent pair {pair_id} does not contain three roles")
        for row, (role, _mode, extra_exp_probe) in zip(pair_rows, expected_roles):
            if row.get("role") != role:
                raise RuntimeError(
                    f"persistent pair {pair_id} role mismatch: {row.get('role')} != {role}"
                )
            actual_extra = row.get("extra_exp_probe", "").strip().lower()
            expected_extra = "true" if extra_exp_probe else "false"
            if actual_extra != expected_extra:
                raise RuntimeError(
                    f"persistent pair {pair_id}/{role} extra_exp_probe mismatch: "
                    f"{actual_extra or 'missing'} != {expected_extra}"
                )
    return rows


def require_preheat_elapsed_in_range(
    elapsed_text: str, minimum_s: float, maximum_s: float
) -> float:
    """Return a finite in-range elapsed time or fail before measurement."""
    try:
        elapsed_s = float(elapsed_text)
    except ValueError as error:
        raise RuntimeError(
            f"thermal preheat elapsed_s is not numeric: {elapsed_text!r}"
        ) from error
    if not math.isfinite(elapsed_s):
        raise RuntimeError(
            f"thermal preheat elapsed_s is not finite: {elapsed_text!r}"
        )
    if not minimum_s <= elapsed_s <= maximum_s:
        raise RuntimeError(
            "thermal preheat elapsed_s failed the configured pre-bracket "
            f"gate: {elapsed_s:.6f} not in "
            f"[{minimum_s:.6f}, {maximum_s:.6f}]"
        )
    return elapsed_s


def run_thermal_preheat(
    args: argparse.Namespace,
    binary: str,
    base: list[str],
    condition: str,
    grid_blocks: int,
    iters: int,
    binary_sha: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Warm the board before a bounded condition without polluting ATC raw data.

    It is a thermal-state preparation step only.  Its NVML row is written to
    a separate file and is never fed to the operand-rate analyzer.
    """
    if args.preheat_seconds <= 0.0:
        return {
            "preheat_requested_seconds": "0",
            "preheat_iters": "0",
            "preheat_output": "",
            "preheat_elapsed_s": "",
            "preheat_role": "not_run",
            "preheat_binary_sha256": "",
            "preheat_actual_min_seconds": "",
            "preheat_actual_max_seconds": "",
            "preheat_actual_gate_status": "not_run",
        }
    preheat_iters = max(1, math.ceil(iters * args.preheat_seconds / args.seconds))
    grid_label = "derived" if grid_blocks == 0 else f"g{grid_blocks}"
    preheat_out = thermal_preheat_output_path(args, condition, grid_blocks)
    command = [
        binary,
        "--mode",
        "full",
        *base,
        "--iters",
        str(preheat_iters),
        "--output",
        str(preheat_out),
        "--pair-id",
        f"preheat_{args.tag}_{condition}_{grid_label}",
        "--role",
        "preheat",
        "--repeat-index",
        "-1",
        "--sequence-index",
        "-1",
        "--extra-exp-probe",
        "1" if args.control_mode == "probe" else "0",
        "--energy-trace",
        "0",
        "--numerical-check-id",
        str(exp_metadata(args.exp_impl)["numerical_check_id"]),
        "--binary-sha256",
        binary_sha,
    ]
    result = run_command(command, dry_run=dry_run)
    preheat_elapsed_s = ""
    preheat_role = ""
    preheat_row_sha = ""
    preheat_gate_enabled = (
        args.preheat_actual_min_seconds is not None
        and args.preheat_actual_max_seconds is not None
    )
    preheat_gate_status = "dry_run" if dry_run else "disabled"
    if result is not None:
        with preheat_out.open(newline="", encoding="utf-8") as handle:
            preheat_rows = list(csv.DictReader(handle))
        if len(preheat_rows) != 1:
            raise RuntimeError(
                f"thermal preheat emitted {len(preheat_rows)} rows; expected exactly 1"
            )
        preheat_row = preheat_rows[0]
        preheat_elapsed_s = preheat_row.get("elapsed_s", "")
        preheat_role = preheat_row.get("role", "")
        preheat_row_sha = preheat_row.get("binary_sha256", "")
        if preheat_role != "preheat" or preheat_row_sha != binary_sha:
            raise RuntimeError(
                "thermal preheat provenance mismatch for role or binary SHA-256"
            )
        if preheat_gate_enabled:
            require_preheat_elapsed_in_range(
                preheat_elapsed_s,
                args.preheat_actual_min_seconds,
                args.preheat_actual_max_seconds,
            )
            preheat_gate_status = "pass"
    print(
        f"condition={condition} grid_blocks={grid_blocks} thermal_preheat_seconds={args.preheat_seconds} "
        f"thermal_preheat_iters={preheat_iters}",
        flush=True,
    )
    return {
        "preheat_requested_seconds": f"{args.preheat_seconds:.6f}",
        "preheat_iters": str(preheat_iters),
        "preheat_output": str(preheat_out),
        "preheat_elapsed_s": preheat_elapsed_s,
        "preheat_role": preheat_role or ("dry_run" if dry_run else ""),
        "preheat_binary_sha256": preheat_row_sha,
        "preheat_actual_min_seconds": (
            f"{args.preheat_actual_min_seconds:.6f}"
            if preheat_gate_enabled
            else ""
        ),
        "preheat_actual_max_seconds": (
            f"{args.preheat_actual_max_seconds:.6f}"
            if preheat_gate_enabled
            else ""
        ),
        "preheat_actual_gate_status": preheat_gate_status,
    }


def thermal_preheat_output_path(
    args: argparse.Namespace, condition: str, grid_blocks: int
) -> Path:
    grid_label = "derived" if grid_blocks == 0 else f"g{grid_blocks}"
    implementation_suffix = output_exp_suffix(args.exp_impl)
    return args.out_dir / (
        f"{args.target_profile}_fp16_softmax_operand_rate_atc_"
        f"{args.tag}{implementation_suffix}_{condition}_{grid_label}_preheat.csv"
    )


def args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="defaults to build-a100 for the A100 profile and build-softmax for RTX 3090",
    )
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument(
        "--target-profile", choices=("rtx3090", "a100"), default="rtx3090"
    )
    parser.add_argument(
        "--exp-impl",
        choices=tuple(EXP_IMPL_METADATA),
        default="fp32",
        help=(
            "exponential implementation; native PTX variants are measured only "
            "with the same-kernel extra-exp probe bracket"
        ),
    )
    parser.add_argument("--softmax-cols", type=int, default=512)
    parser.add_argument("--blocks-per-sm", type=int, default=2)
    parser.add_argument(
        "--grid-blocks-list",
        default=None,
        help=(
            "comma-separated explicit CTA grids; defaults to 16 on RTX 3090 "
            "and 27,54 for the bounded A100 screen"
        ),
    )
    parser.add_argument(
        "--a100-sweep-stage",
        choices=("screen", "confirm"),
        default="screen",
        help=(
            "screen permits only the incremental 27/54 active-SM/SNR coordinates; "
            "confirm permits only 108 and is run only if the screen lacks precision"
        ),
    )
    parser.add_argument(
        "--control-mode",
        choices=tuple(CONTROL_ROLES),
        default="probe",
        help=(
            "bracket control: probe is the same-kernel 1x/2x exp contrast; "
            "io and linear retain the historical diagnostics"
        ),
    )
    parser.add_argument("--logit-scale", type=float, default=4.0)
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help=(
            "per-role target; defaults to 13 s for RTX native EX2 so the "
            "guarded 500 ms trace clears 16 points, and 7 s otherwise"
        ),
    )
    parser.add_argument("--idle-measure-seconds", type=float, default=1.0)
    parser.add_argument("--pairs", type=int, default=None)
    parser.add_argument(
        "--bracket-warmup-pairs",
        type=int,
        default=None,
        help=(
            "unrecorded continuous brackets before persistent measurement; "
            "defaults to 1 for persistent execution and 0 for legacy execution"
        ),
    )
    parser.add_argument(
        "--execution-mode",
        choices=("persistent_bracket", "legacy_per_role_subprocess"),
        default="persistent_bracket",
        help=(
            "persistent_bracket runs all roles in one CUDA context; "
            "legacy_per_role_subprocess is retained only for comparison"
        ),
    )
    parser.add_argument(
        "--bracket-idle-policy",
        choices=("pair_once", "batch_once", "per_role"),
        default="batch_once",
        help="persistent bracket baseline policy; batch_once is the continuous-probe default",
    )
    parser.add_argument(
        "--bracket-order",
        choices=("ctc", "counterbalanced6"),
        default=None,
        help=(
            "probe order inside one persistent context; counterbalanced6 runs "
            "CTC,TCT,TCT,CTC,CTC,TCT and requires --pairs 6"
        ),
    )
    parser.add_argument(
        "--preheat-seconds",
        type=float,
        default=0.0,
        help="one full-treatment thermal preheat per cache condition; excluded from ATC raw CSV",
    )
    parser.add_argument(
        "--preheat-actual-min-seconds",
        type=float,
        default=None,
        help=(
            "optional fail-closed lower bound for the observed preheat kernel "
            "elapsed_s; requires --preheat-actual-max-seconds and is checked "
            "before the measured bracket"
        ),
    )
    parser.add_argument(
        "--preheat-actual-max-seconds",
        type=float,
        default=None,
        help=(
            "optional fail-closed upper bound for the observed preheat kernel "
            "elapsed_s; requires --preheat-actual-min-seconds and is checked "
            "before the measured bracket"
        ),
    )
    parser.add_argument(
        "--conditions",
        default="cache_reuse_candidate",
        help="comma-separated bounded cache conditions",
    )
    parser.add_argument("--cache-policy", choices=("default", "cg"), default="default")
    parser.add_argument(
        "--energy-trace",
        type=int,
        choices=(0, 1),
        default=1,
        help="sample the NVML total-energy counter during each measured kernel",
    )
    parser.add_argument(
        "--energy-trace-sample-ms",
        type=float,
        default=None,
        help=(
            "counter polling interval; defaults to 500 ms on RTX 3090 and "
            "200 ms for the A100 cadence screen"
        ),
    )
    parser.add_argument(
        "--energy-trace-min-updates",
        type=int,
        default=None,
        help=(
            "historical option name; the measurement binary gates the number "
            "of guarded counter-changed fit points"
        ),
    )
    parser.add_argument(
        "--energy-trace-output",
        type=Path,
        default=None,
        help="trace CSV; defaults to the raw CSV stem plus _energy_trace.csv",
    )
    parser.add_argument("--tag", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--out-dir", type=Path, default=Path("results/raw"))
    parser.add_argument("--max-gpu-util-pct", type=float, default=10.0)
    parser.add_argument("--max-memory-util-pct", type=float, default=15.0)
    parser.add_argument("--quiescence-timeout-s", type=float, default=60.0)
    parser.add_argument("--quiescence-poll-s", type=float, default=1.0)
    parser.add_argument("--quiescence-consecutive-samples", type=int, default=2)
    parser.add_argument("--skip-quiescence", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = args_parser().parse_args()
    if args.binary is None:
        args.binary = Path(
            "build-a100/a100_fp16_softmax_energy"
            if args.target_profile == "a100"
            else "build-softmax/a100_fp16_softmax_energy"
        )
    if args.pairs is None:
        args.pairs = (
            6 if args.target_profile == "a100" or args.exp_impl != "fp32" else 3
        )
    if args.bracket_order is None:
        args.bracket_order = (
            "counterbalanced6"
            if args.target_profile == "a100" or args.exp_impl != "fp32"
            else "ctc"
        )
    if args.energy_trace_sample_ms is None:
        args.energy_trace_sample_ms = 200.0 if args.target_profile == "a100" else 500.0
    if args.seconds is None:
        args.seconds = (
            13.0
            if args.target_profile == "rtx3090" and args.exp_impl != "fp32"
            else 7.0
        )
    if args.energy_trace_min_updates is None:
        args.energy_trace_min_updates = (
            16
            if args.target_profile == "a100" or args.exp_impl != "fp32"
            else 8
        )
    if args.grid_blocks_list is None:
        args.grid_blocks_list = (
            "27,54" if args.target_profile == "a100" else "16"
        )
    if args.bracket_warmup_pairs is None:
        args.bracket_warmup_pairs = 1 if args.execution_mode == "persistent_bracket" else 0
    if (
        args.pairs < 1
        or args.seconds <= 0
        or args.idle_measure_seconds <= 0
        or args.preheat_seconds < 0
        or args.bracket_warmup_pairs < 0
        or args.energy_trace_sample_ms <= 0
        or args.energy_trace_min_updates < 2
    ):
        raise SystemExit(
            "pairs/seconds/idle-measure-seconds/trace sample must be positive; "
            "preheat/warmup must be non-negative and trace min updates >= 2"
        )
    preheat_gate_values = (
        args.preheat_actual_min_seconds,
        args.preheat_actual_max_seconds,
    )
    if (preheat_gate_values[0] is None) != (preheat_gate_values[1] is None):
        raise SystemExit(
            "--preheat-actual-min-seconds and "
            "--preheat-actual-max-seconds must be supplied together"
        )
    if preheat_gate_values[0] is not None:
        preheat_min_s, preheat_max_s = preheat_gate_values
        assert preheat_min_s is not None and preheat_max_s is not None
        if (
            args.preheat_seconds <= 0.0
            or not math.isfinite(preheat_min_s)
            or not math.isfinite(preheat_max_s)
            or preheat_min_s < 0.0
            or preheat_max_s < preheat_min_s
        ):
            raise SystemExit(
                "preheat actual bounds require --preheat-seconds > 0 and "
                "finite 0 <= min <= max"
            )
    if (
        args.execution_mode == "legacy_per_role_subprocess"
        and args.bracket_warmup_pairs != 0
    ):
        raise SystemExit(
            "--bracket-warmup-pairs is a persistent-context feature; use 0 in legacy mode"
        )
    if args.bracket_order == "counterbalanced6" and (
        args.execution_mode != "persistent_bracket"
        or args.control_mode != "probe"
        or args.pairs != 6
    ):
        raise SystemExit(
            "--bracket-order counterbalanced6 requires persistent probe mode and --pairs 6"
        )
    if args.execution_mode == "legacy_per_role_subprocess" and args.bracket_order != "ctc":
        raise SystemExit("legacy execution supports only --bracket-order ctc")
    if args.exp_impl != "fp32" and args.control_mode != "probe":
        raise SystemExit(
            "native --exp-impl ptx_f16/ptx_f16x2 requires --control-mode probe; "
            "linear/io controls are different kernels and do not isolate native EX2"
        )
    if args.target_profile == "a100" and (
        args.execution_mode != "persistent_bracket"
        or args.control_mode != "probe"
        or args.bracket_order != "counterbalanced6"
        or args.pairs != 6
        or args.energy_trace != 1
    ):
        raise SystemExit(
            "A100 energy runs require persistent same-kernel probe mode, "
            "counterbalanced6, exactly six brackets, and energy tracing"
        )
    if args.target_profile == "a100" and args.skip_quiescence:
        raise SystemExit("A100 energy runs cannot use --skip-quiescence")
    if (
        args.energy_trace
        and args.target_profile == "rtx3090"
        and args.energy_trace_sample_ms < 200.0
    ):
        raise SystemExit(
            "RTX 3090/WSL total-energy tracing requires >=200 ms polling; "
            "high-frequency queries undercount the counter"
        )
    if not args.binary.is_file():
        raise SystemExit(f"binary does not exist: {args.binary}")
    conditions = tuple(value.strip() for value in args.conditions.split(",") if value.strip())
    allowed = {"cache_reuse_candidate", "streaming_large_ws"}
    if not conditions or any(value not in allowed for value in conditions):
        raise SystemExit("conditions must be cache_reuse_candidate and/or streaming_large_ws")
    if len(conditions) > 2:
        raise SystemExit("this bounded pilot accepts at most two cache conditions")
    if args.target_profile == "a100" and (
        args.softmax_cols != A100_PROTOCOL_SOFTMAX_COLS
        or args.logit_scale != A100_PROTOCOL_LOGIT_SCALE
        or conditions != (A100_PROTOCOL_CACHE_CONDITION,)
        or args.cache_policy != A100_PROTOCOL_CACHE_POLICY
    ):
        raise SystemExit(
            "A100 energy protocol is fixed at S=512, logit_scale=4.0, "
            "cache_reuse_candidate/default; change the protocol revision before "
            "collecting another coordinate"
        )
    try:
        grid_blocks_list = tuple(
            int(value.strip()) for value in args.grid_blocks_list.split(",") if value.strip()
        )
    except ValueError as error:
        raise SystemExit("--grid-blocks-list must contain non-negative integers") from error
    if not grid_blocks_list or any(value < 0 for value in grid_blocks_list):
        raise SystemExit("--grid-blocks-list must contain one or more non-negative integers")
    if args.target_profile == "a100":
        if tuple(sorted(set(grid_blocks_list))) != grid_blocks_list:
            raise SystemExit("A100 CTA coordinates must be unique and strictly increasing")
        if args.a100_sweep_stage == "screen":
            if len(grid_blocks_list) > 2 or any(
                value not in {27, 54} for value in grid_blocks_list
            ):
                raise SystemExit(
                    "A100 screen is bounded to one or both of 27,54 CTA; "
                    "these are active-SM/SNR coordinates, not an SFU-supply sweep"
                )
        elif grid_blocks_list != (108,):
            raise SystemExit(
                "A100 confirm accepts only 108 CTA and must be run after an "
                "imprecise 27/54 screen"
            )

    binary = str(args.binary)
    binary_sha = sha256(args.binary)
    output_prefix = (
        f"{args.target_profile}_fp16_softmax_operand_rate_atc_{args.tag}"
        f"{output_exp_suffix(args.exp_impl)}"
    )
    raw_csv = args.out_dir / f"{output_prefix}_raw.csv"
    manifest_csv = args.out_dir / f"{output_prefix}_manifest.csv"
    trace_csv = args.energy_trace_output or raw_csv.with_name(
        f"{raw_csv.stem}_energy_trace.csv"
    )
    if not args.dry_run:
        existing_outputs = [
            path
            for path in (
                raw_csv,
                manifest_csv,
                trace_csv,
                *(
                    thermal_preheat_output_path(args, condition, grid_blocks)
                    for condition in conditions
                    for grid_blocks in grid_blocks_list
                    if args.preheat_seconds > 0.0
                ),
            )
            if path.exists() and path.stat().st_size > 0
        ]
        if existing_outputs:
            joined = ", ".join(str(path) for path in existing_outputs)
            raise SystemExit(
                "refusing to append to existing experiment outputs; "
                f"choose a fresh --tag or --out-dir: {joined}"
            )
    manifests: list[dict[str, Any]] = []
    gpu_selector: str | int = args.gpu_id
    preflight_metadata: dict[str, str] = {}
    inventory: dict[str, str] = {}
    preflight_manifest: dict[str, str] = {}
    if not args.dry_run:
        first_base = common_args(args, conditions[0], grid_blocks_list[0])
        preflight = run_command(
            [binary, "--mode", "full", *first_base, "--dry-run"], dry_run=False
        )
        assert preflight is not None
        preflight_metadata = parse_key_value_output(preflight.stdout)
        gpu_selector = preflight_metadata.get("cuda_pci_bus_id", "")
        if not gpu_selector:
            raise RuntimeError("binary preflight did not emit cuda_pci_bus_id")
        inventory = nvidia_inventory(gpu_selector)
        if args.target_profile == "a100":
            require_a100_board_preflight(
                preflight_metadata, inventory, args.exp_impl
            )
        preflight_manifest = {
            **{f"preflight_{key}": value for key, value in preflight_metadata.items()},
            **inventory,
        }

    for condition in conditions:
        for grid_index, grid_blocks in enumerate(grid_blocks_list):
            base = common_args(args, condition, grid_blocks)
            validation = run_command([binary, "--mode", "full", *base, "--validate-only"],
                                     dry_run=args.dry_run)
            implementation = exp_metadata(args.exp_impl)
            numerical_check_id = str(implementation["numerical_check_id"])
            native_validation_id = str(implementation["native_validation_id"])
            if validation is not None and numerical_check_id not in validation.stdout:
                raise RuntimeError(
                    "full numerical validation did not emit the expected pass id"
                )
            if (
                validation is not None
                and native_validation_id
                and native_validation_id not in validation.stdout
            ):
                raise RuntimeError(
                    "native EX2 exhaustive validation did not emit the expected pass id"
                )
            if validation is not None:
                validation_metadata = parse_key_value_output(validation.stdout)
                if validation_metadata.get("cuda_pci_bus_id") != str(gpu_selector):
                    raise RuntimeError(
                        "CUDA/NVML identity changed after preflight: "
                        f"{validation_metadata.get('cuda_pci_bus_id')} != {gpu_selector}"
                    )
            calibration_command = [binary, "--mode", "full", *base]
            if args.control_mode == "probe":
                # Calibrate the extra-exp treatment, then reuse that ITER for
                # both sides.  Otherwise the nominal role duration is based on
                # the cheaper control and the counter trace can be undersized.
                calibration_command.extend(("--extra-exp-probe", "1"))
            calibration_command.append("--calibrate-only")
            calibration = run_command(calibration_command, dry_run=args.dry_run)
            iters = 0 if calibration is None else parse_calibrated_iters(calibration.stdout)
            print(
                f"condition={condition} grid_blocks={grid_blocks} common_full_iters={iters}",
                flush=True,
            )
            preheat_metadata = run_thermal_preheat(
                args, binary, base, condition, grid_blocks, iters, binary_sha,
                dry_run=args.dry_run,
            )

            grid_label = "derived" if grid_blocks == 0 else f"g{grid_blocks}"
            pair_impl = "" if args.exp_impl == "fp32" else f"{args.exp_impl}_"
            pair_prefix = (
                f"softmax_oratc_{args.tag}_{condition}_{args.control_mode}_"
                f"{pair_impl}{grid_label}_s{grid_index:02d}"
            )
            if args.execution_mode == "persistent_bracket":
                if args.skip_quiescence:
                    state, quiescence_wait_s, quiescence = (
                        nvidia_state(gpu_selector), 0.0, True
                    )
                else:
                    state, quiescence_wait_s, quiescence = wait_for_quiescence(
                        args, gpu_selector
                    )
                if not quiescence:
                    raise RuntimeError(
                        f"quiescence gate failed before persistent batch {pair_prefix} after "
                        f"{quiescence_wait_s:.1f}s: {state}"
                    )
                batch_inventory_before: dict[str, str] = {}
                competitors_before: list[str] = []
                if args.target_profile == "a100" and not args.dry_run:
                    batch_inventory_before = nvidia_inventory(gpu_selector)
                    require_a100_board_preflight(
                        preflight_metadata, batch_inventory_before, args.exp_impl
                    )
                    competitors_before = running_compute_apps(
                        batch_inventory_before["inventory_uuid"]
                    )
                    if competitors_before:
                        raise RuntimeError(
                            "A100 batch preflight found competing compute processes: "
                            + " | ".join(competitors_before)
                        )
                command = [
                    binary,
                    "--mode",
                    "full",
                    *base,
                    "--iters",
                    str(iters),
                    "--output",
                    str(raw_csv),
                    "--bracket-control",
                    args.control_mode,
                    "--bracket-pairs",
                    str(args.pairs),
                    "--bracket-warmup-pairs",
                    str(args.bracket_warmup_pairs),
                    "--pair-prefix",
                    pair_prefix,
                    "--bracket-idle-policy",
                    args.bracket_idle_policy,
                    "--bracket-order",
                    args.bracket_order,
                    "--extra-exp-probe",
                    "0",
                    *energy_trace_args(args, trace_csv),
                    "--numerical-check-id",
                    numerical_check_id,
                    "--binary-sha256",
                    binary_sha,
                ]
                started = time.time()
                competitors_during: list[str] = []
                process_monitor_errors: list[str] = []
                if args.target_profile == "a100" and not args.dry_run:
                    result, competitors_during, process_monitor_errors = (
                        run_command_with_a100_process_monitor(
                            command, batch_inventory_before["inventory_uuid"]
                        )
                    )
                else:
                    result = run_command(command, dry_run=args.dry_run)
                post_inventory_raw = (
                    {} if result is None else nvidia_inventory(gpu_selector)
                )
                post_inventory = {
                    f"post_{key}": value for key, value in post_inventory_raw.items()
                }
                a100_environment: dict[str, str] = {
                    "a100_environment_status": "not_applicable",
                    "a100_environment_reasons": "",
                }
                if args.target_profile == "a100" and result is not None:
                    after_uuid = post_inventory_raw.get("inventory_uuid", "")
                    competitors_after = (
                        running_compute_apps(after_uuid) if after_uuid else []
                    )
                    a100_environment = audit_a100_batch_environment(
                        inventory,
                        batch_inventory_before,
                        post_inventory_raw,
                        competitors_before,
                        competitors_during,
                        competitors_after,
                        process_monitor_errors,
                    )
                raw_rows = (
                    [] if result is None else persistent_raw_rows(
                        raw_csv, pair_prefix, expected_rows=3 * args.pairs,
                        idle_policy=args.bracket_idle_policy,
                        control_mode=args.control_mode,
                        bracket_order=args.bracket_order,
                        target_profile=args.target_profile,
                        exp_impl=args.exp_impl,
                    )
                )
                for row in raw_rows:
                    manifests.append(
                        {
                            "protocol_revision": protocol_revision(
                                args, "persistent"
                            ),
                            "target_profile": args.target_profile,
                            "a100_sweep_stage": (
                                args.a100_sweep_stage
                                if args.target_profile == "a100"
                                else "not_applicable"
                            ),
                            "pair_id": row["pair_id"],
                            "cache_condition": condition,
                            "cache_policy": args.cache_policy,
                            "softmax_cols": args.softmax_cols,
                            "logit_scale": args.logit_scale,
                            "control_mode": args.control_mode,
                            "grid_blocks_requested": grid_blocks,
                            "grid_sweep_index": grid_index,
                            "role": row["role"],
                            "mode": row["mode"],
                            "sequence_index": row["sequence_index"],
                            "repeat": row["repeat"],
                            "common_full_iters": iters,
                            "execution_mode": args.execution_mode,
                            "raw_execution_model": row.get("execution_model", ""),
                            "bracket_context_id": row.get("bracket_context_id", ""),
                            "idle_baseline_scope": row.get("idle_baseline_scope", ""),
                            "bracket_warmup_pairs": args.bracket_warmup_pairs,
                            "bracket_order": args.bracket_order,
                            "preceding_role_gap_s": row.get("preceding_role_gap_s", ""),
                            "preceding_counter_gap_delta_J": row.get(
                                "preceding_counter_gap_delta_J", ""
                            ),
                            "extra_exp_probe": row.get("extra_exp_probe", ""),
                            "cuda_pci_bus_id": row.get("cuda_pci_bus_id", ""),
                            "cuda_binary_arch": row.get("cuda_binary_arch", ""),
                            "xu_documented_results_per_sm_cycle": row.get(
                                "xu_documented_results_per_sm_cycle", ""
                            ),
                            "grid_experiment_purpose": row.get(
                                "grid_experiment_purpose", ""
                            ),
                            "smid_set": row.get("smid_set", ""),
                            "smid_histogram": row.get("smid_histogram", ""),
                            "sfu_regime_evidence_status": row.get(
                                "sfu_regime_evidence_status", ""
                            ),
                            "energy_trace_enabled": args.energy_trace,
                            "energy_trace_sample_ms": args.energy_trace_sample_ms,
                            "energy_trace_min_updates": args.energy_trace_min_updates,
                            "energy_trace_output": str(trace_csv),
                            **preheat_metadata,
                            "quiescence_scope": "before_persistent_batch",
                            "binary": binary,
                            "binary_sha256": binary_sha,
                            "numerical_check_id": numerical_check_id,
                            "native_ex2_validation_id": native_validation_id,
                            "quiescence_status": (
                                "skipped"
                                if args.skip_quiescence
                                else "pass" if quiescence else "fail"
                            ),
                            "quiescence_wait_s": f"{quiescence_wait_s:.6f}",
                            "command_started_epoch_s": f"{started:.6f}",
                            "command_elapsed_s": f"{time.time() - started:.6f}",
                            "command": " ".join(command),
                            **{
                                field: row.get(field, "")
                                for field in EXP_RAW_IDENTITY_FIELDS
                            },
                            **preflight_manifest,
                            **{
                                f"batch_before_{key}": value
                                for key, value in batch_inventory_before.items()
                            },
                            **post_inventory,
                            **a100_environment,
                            **state,
                        }
                    )
                if (
                    args.target_profile == "a100"
                    and result is not None
                    and a100_environment.get("a100_environment_status") != "pass"
                ):
                    write_manifest(manifest_csv, manifests)
                    raise RuntimeError(
                        "A100 batch environment gate failed: "
                        + a100_environment.get("a100_environment_reasons", "unknown")
                    )
                if result is not None:
                    # Persist provenance after each successful batch so a
                    # later-grid failure cannot leave usable raw rows without
                    # their environment manifest.
                    write_manifest(manifest_csv, manifests)
            else:
                for pair_index in range(args.pairs):
                    pair_id = f"{pair_prefix}_p{pair_index:02d}"
                    for sequence_index, (role, mode, extra_exp_probe) in enumerate(
                        CONTROL_ROLES[args.control_mode]
                    ):
                        if args.skip_quiescence:
                            state, quiescence_wait_s, quiescence = (
                                nvidia_state(gpu_selector), 0.0, True
                            )
                        else:
                            state, quiescence_wait_s, quiescence = wait_for_quiescence(
                                args, gpu_selector
                            )
                        if not quiescence:
                            raise RuntimeError(
                                f"quiescence gate failed before {pair_id}/{role} after "
                                f"{quiescence_wait_s:.1f}s: {state}"
                            )
                        command = [
                            binary,
                            "--mode",
                            mode,
                            *base,
                            "--iters",
                            str(iters),
                            "--output",
                            str(raw_csv),
                            "--pair-id",
                            pair_id,
                            "--role",
                            role,
                            "--repeat-index",
                            str(pair_index),
                            "--sequence-index",
                            str(sequence_index),
                            "--extra-exp-probe",
                            "1" if extra_exp_probe else "0",
                            *energy_trace_args(args, trace_csv),
                            "--numerical-check-id",
                            numerical_check_id,
                            "--binary-sha256",
                            binary_sha,
                        ]
                        started = time.time()
                        result = run_command(command, dry_run=args.dry_run)
                        manifests.append(
                            {
                                "protocol_revision": protocol_revision(
                                    args, "legacy"
                                ),
                                "target_profile": args.target_profile,
                                "pair_id": pair_id,
                                "cache_condition": condition,
                                "cache_policy": args.cache_policy,
                                "softmax_cols": args.softmax_cols,
                                "logit_scale": args.logit_scale,
                                "control_mode": args.control_mode,
                                "grid_blocks_requested": grid_blocks,
                                "grid_sweep_index": grid_index,
                                "role": role,
                                "mode": mode,
                                "sequence_index": sequence_index,
                                "repeat": pair_index,
                                "common_full_iters": iters,
                                "execution_mode": args.execution_mode,
                                "raw_execution_model": "standalone_cuda_context_v1",
                                "idle_baseline_scope": "per_role",
                                "bracket_warmup_pairs": 0,
                                "preceding_role_gap_s": "",
                                "preceding_counter_gap_delta_J": "",
                                "extra_exp_probe": "true" if extra_exp_probe else "false",
                                "energy_trace_enabled": args.energy_trace,
                                "energy_trace_sample_ms": args.energy_trace_sample_ms,
                                "energy_trace_min_updates": args.energy_trace_min_updates,
                                "energy_trace_output": str(trace_csv),
                                **preheat_metadata,
                                "binary": binary,
                                "binary_sha256": binary_sha,
                                "numerical_check_id": numerical_check_id,
                                "native_ex2_validation_id": native_validation_id,
                                "exp_impl": implementation["canonical"],
                                "exp_input_dtype": implementation[
                                    "exp_input_dtype"
                                ],
                                "exp_ptx_instruction": implementation[
                                    "exp_ptx_instruction"
                                ],
                                "exp_results_per_ptx_instruction": implementation[
                                    "results_per_ptx_instruction"
                                ],
                                "expected_control_ex2_scalar_results_per_cta_iter": args.softmax_cols,
                                "expected_treatment_ex2_scalar_results_per_cta_iter": 2
                                * args.softmax_cols,
                                "expected_probe_ex2_scalar_results_per_cta_iter": args.softmax_cols,
                                "expected_control_ex2_ptx_instructions_per_cta_iter": args.softmax_cols
                                // int(implementation["results_per_ptx_instruction"]),
                                "expected_treatment_ex2_ptx_instructions_per_cta_iter": 2
                                * args.softmax_cols
                                // int(implementation["results_per_ptx_instruction"]),
                                "expected_probe_ex2_ptx_instructions_per_cta_iter": args.softmax_cols
                                // int(implementation["results_per_ptx_instruction"]),
                                "quiescence_status": (
                                    "skipped"
                                    if args.skip_quiescence
                                    else "pass" if quiescence else "fail"
                                ),
                                "quiescence_wait_s": f"{quiescence_wait_s:.6f}",
                                "command_started_epoch_s": f"{started:.6f}",
                                "command_elapsed_s": (
                                    "" if result is None else f"{time.time() - started:.6f}"
                                ),
                                "command": " ".join(command),
                                **state,
                            }
                        )
    if not args.dry_run:
        write_manifest(manifest_csv, manifests)
    print(f"raw_csv={raw_csv}")
    print(f"manifest_csv={manifest_csv}")
    print(f"energy_trace_csv={trace_csv}")
    print(f"binary_sha256={binary_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
