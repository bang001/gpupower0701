---
name: fp16-energy-experiment
description: Run, validate, and document the RTX 3090, V100, A100, and H100 CUDA/NVML/NCU component-energy microbenchmarks in this repository.
---

# FP16 Energy Experiment

Operate this repository as an experiment harness. Keep NVML energy runs separate
from NCU profiler runs, preserve measured artifacts, and report effective
microbenchmark coefficients rather than pure circuit energy.

## Canonical Documents

Read these active documents before changing experiment behavior or interpreting
results:

1. `README.md`
2. `docs/methodology/howitworks.md`
3. `docs/methodology/component_energy_final_experiment_plan_ko.md`
4. `docs/methodology/ncu_validation_energy_calculation_ko.md`
5. `docs/platforms/cross_platform_component_experiment_guide_ko.md`
6. `docs/audits/component_energy_self_critique_ko.md`

Platform routing:

- RTX 3090: `README.md` and
  `results/summary/rtx3090_component_finalplan_20260712_command_plan.md`
- V100: `docs/platforms/v100_node_experiment_guide_ko.md`
- A100: `docs/platforms/a100_node_experiment_guide_ko.md`
- H100: `docs/platforms/h100_node_experiment_guide_ko.md`

The original A100 v2 design is historical background under
`archive/superseded_v2_design_20260714/`. It is not the current execution guide.

## Canonical Definitions

- One logical Tensor operation is one warp-level FP16 `m16n16k16` MMA.
- Use `8192 FLOP/op` and `8192 input bits/op` for A+B FP16 inputs.
- The harness fixes `threads/block=32` and one warp/block.
- `blocks/SM` is the requested persistent-grid density. Do not claim actual
  simultaneous residency without SMID and NCU occupancy/resource evidence.
- `W_SM` is a memory working-set coordinate. For `reg_mma` it is not the
  physical register-file footprint.
- All reported coefficients are workload-dependent GPU/device-level effective
  coefficients. They are not Tensor, RF, SRAM, HBM, or PHY transistor-level
  energies.

## Current Component Pairs

| Component | Treatment | Control | Final work policy | Unit |
|---|---|---|---|---|
| Tensor MMA increment | `reg_mma` | `reg_operand_only` | equal pair-locked ITER, direct net-energy subtraction | pJ/FLOP |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | mode-duration calibration and elapsed-aware control power | pJ/bit |
| Global L1-hit path | `global_l1_load_only` | `global_addr_only` | mode-duration calibration and elapsed-aware control power | pJ/bit |
| L2 CG-hit path | `l2_cg_load_only` | `global_addr_only` | equal pair-locked ITER, direct net-energy subtraction | pJ/bit |
| DRAM CG sanity path | `dram_cg_load_only` | `global_addr_only` | equal pair-locked ITER, direct net-energy subtraction | pJ/bit |

For L2 final rows, run the energy pair with
`--memory-pair-lock-iters` and analyze it with
`--l2-pair-policy matched-iters`. A duration-scaled L2 row or
`iter_ratio != 1` is invalid even when NCU reports a perfect L2-hit path.
The runner mode pair is `--modes global_addr_only,l2_cg_load_only`.

## Profile Boundaries

Keep unified L1/shared capacity and CUDA shared allocation separate.

| Profile | SMs | Combined L1/shared | Shared allocation | Max shared/block | L2 | Max blocks/SM | `GetPowerUsage` semantics |
|---|---:|---:|---:|---:|---:|---:|---|
| V100/GV100 | 80 | 128 KiB/SM | 96 KiB/SM | 96 KiB/block | 6 MiB | 32 | instant |
| RTX 3090/GA102 | 82 | 128 KiB/SM | 100 KiB/SM | 99 KiB/block | 6 MiB | 16 | one-second average |
| A100/GA100 | 108 | 192 KiB/SM | 164 KiB/SM | 163 KiB/block | 40 MiB | 32 | instant |
| H100/GH100 | 132 default | 256 KiB/SM | 228 KiB/SM | 227 KiB/block | 50 MiB | 32 | one-second average |

These are planning profiles. Runtime SM count, SKU, MIG/vGPU partition, memory
capacity, clocks, and power scope must be recorded on the target node.

Feasibility rules shared by C++ and Python:

- Memory-backed modes require `W_SM_KiB >= blocks_per_SM`, which provides at
  least one logical 1 KiB tile per block.
- Shared modes require `W_SM + blocks/SM <= shared allocation per SM` and the
  per-block allocation limit.
- L1/L2 candidates require the full active-SM working set to fit nominal L2;
  NCU still decides whether the actual path is L1- or L2-hit dominated.
- DRAM candidates require a full working set larger than nominal L2.

## Build And Preflight

Check `git status --short` before editing or running. Do not overwrite measured
rows. Use the generated platform package whenever possible.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build build -j
```

Use `70`, `80`, or `90` for V100, A100, or H100. V100 requires a CUDA compiler
that still lists `compute_70`; CUDA 12.x is the recommended line. Inspect ptxas
register counts and spill output.

Strict preflight example:

```bash
python3 scripts/preflight_gpu_support.py \
  --gpu 0 --target-profile a100 --strict \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --out results/summary/a100_preflight.md
```

A profile mismatch, missing binary, unsupported CUDA target, missing NCU chip,
or failed dry-run is a failed preflight, not a target-platform result.

## Standard Platform Run

Generate and review the command package instead of assembling final runs by
hand:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 --repeats 5 --tag "$(date +%Y%m%d)"

bash results/summary/a100_component_finalplan_"$(date +%Y%m%d)"_commands.sh
```

The required order is:

1. strict platform/toolchain/power preflight;
2. energy sweeps without NCU;
3. power API and power-state audits;
4. NCU sidecar runs;
5. path acceptance for treatment and exact-coordinate controls;
6. matched-control coefficient analysis;
7. reliability, strict-summary, package, and goal-readiness audits.

Energy run and NCU replay data are separate experiments. Never use NCU replay
energy as an NVML energy row.

## NCU Validation

NCU does not measure component energy. It validates the path and the denominator.
Reports must include, with units:

| Evidence | Unit/meaning |
|---|---|
| Tensor/HMMA instructions | instructions or normalized logical MMA |
| Shared traffic | bytes and accesses/instructions |
| L1 hit rate | %; path-specific hit evidence preferred |
| L2 read hit rate | %; hit/miss-derived and native cross-check where available |
| L1 accesses | requests preferred, sectors fallback; state the unit |
| L2/DRAM accesses | sectors |
| L1/L2/DRAM traffic | bytes |
| Long scoreboard | NCU per-issue-active stall signal; not elapsed-time percentage |
| Spill/local traffic | bytes; primary Tensor controls require zero |
| SMID/occupancy/resources | placement and actual residency context |

For `.cg` L2 loads, L1TEX request bytes are normal. L2 acceptance requires
near-zero L1 hit bytes/rate, high path-specific L2 read hit rate, expected-byte
conservation, and low DRAM leakage. It does not require zero L1 request traffic.

If NCU reports `ERR_NVGPUCTRPERM`, use the generated sudo fallback. Explicit
privileged execution is:

```bash
NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh
```

On WSL, enable performance counters for all users in the Windows NVIDIA control
panel and run `wsl --shutdown` before retrying. V100 additionally requires an
NCU release whose `--list-chips` and `--query-metrics --chips gv100` succeed.

## Mode Reporting

Every experiment report must explain each reported mode before presenting
numbers. At minimum, use this current table:

| Mode | Meaning | Status |
|---|---|---|
| `clocked_empty` | clocked persistent-loop control | primary Shared control |
| `reg_operand_only` | live WMMA/register loop without workload-proportional MMA | primary Tensor control |
| `reg_mma` | FP16 WMMA loop | primary Tensor treatment |
| `global_addr_only` | same global address/tile/repeat loop without data load | primary Global L1/L2/DRAM control |
| `shared_scalar_load_only` | software-managed shared scalar loads | primary Shared treatment |
| `global_l1_load_only` | normal global load selected and verified as L1-hit path | primary Global L1 treatment |
| `l2_cg_load_only` | cache-global load selected and verified as L2-hit path | primary L2 treatment |
| `dram_cg_load_only` | cache-global streaming load larger than L2 | DRAM sanity treatment |

`idle`, `empty`, `reg_fragment_only`, `reg_pressure`, `addr_only`, `shared_load_only`,
`shared_mma`, `l2_load_only`, `l2_mma`, `dram_load_only`, `dram_mma`,
`store_only`, and `store_path` remain implemented diagnostics or legacy modes.
Do not put them in the strict component table unless the current plan and all
acceptance gates explicitly select them.

## Result And Report Rules

- Preserve raw CSVs in `results/raw/`, NCU artifacts in `results/ncu/`, plots in
  `results/plots/`, and generated audit/report files in `results/summary/`.
- Treat per-GPU rows as separate rows and aggregate only matching `run_id`
  groups when a multi-GPU total is explicitly required.
- Exclude placement failures and power-state rejects from primary summaries.
- Memory coefficients require `denominator_source=ncu_actual_exact` for strict
  reporting.
- Tensor, L2, and DRAM pair details require
  `pair_energy_basis=matched_iters_net_energy`, equal positive ITER, and
  `iter_ratio=1`.
- A negative coefficient is a failed pair/signal result. Never take its absolute
  value or force a nonnegative fit to claim a component value.
- Total-energy counter scope, power semantics, measurement duration, repeats,
  clocks, temperature, power limit, accepted/rejected coordinates, and reasons
  must remain visible in the report.

Whenever an experiment used a sweep, summarize it as a table. Include units in
every header or cell label, including `W_SM (KiB/SM)`, `blocks/SM`, `active_SM
(SMs)`, duration `(s)`, `ITER (count)`, energy `(J)`, traffic `(B)`, hit rate
(%)`, `pJ/FLOP`, and `pJ/bit`. Explain the selected coordinates and rejected
coordinates after the table.

Use these interpretation labels:

- effective Tensor MMA incremental coefficient;
- effective Shared scalar path coefficient;
- effective Global L1-hit path coefficient;
- effective L2 CG-hit path coefficient;
- effective DRAM CG streaming sanity coefficient.

Do not call these pure Tensor Core, register-file, L1/L2 SRAM, HBM, GDDR, or PHY
energies.

## Register And Hopper Boundaries

For `reg_mma`, the physical register footprint comes from ptxas
registers/thread, 32 threads/block, requested blocks/SM, and actual residency.
Changing `W_SM` does not shrink that footprint. Require no spill/local traffic
and compare `reg_mma` against `reg_operand_only`; this still produces a Tensor
plus register/scheduler/control incremental path, not separable pure RF energy.

The H100 profile currently runs FP16 WMMA compatibility kernels. It does not
measure Hopper-native WGMMA, TMA, or FP8 component coefficients. Those require
separate kernels, counters, controls, and documentation.

## Repository Hygiene

Run the consistency audit after code, profile, or documentation changes:

```bash
python3 scripts/audit_documentation_consistency.py --fail-on-error
```

Active documents live under `docs/` by purpose. Superseded designs, historical
coefficient visualizations, and failed wrong-platform preflights belong under a
dated `archive/` directory with a README explaining why they are not current
evidence.
