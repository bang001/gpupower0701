---
name: fp16-energy-experiment
description: Run, debug, validate, and analyze the FP16 Tensor Core energy microbenchmark in this repository. Use when Codex is asked to build the CUDA/NVML project, run idle/empty/reg_fragment_only/reg_operand_only/reg_mma/shared_mma/l2_mma/dram_mma/store_path experiments, generate RTX 3090 or A100 sweep matrices, collect Nsight Compute validation reports, compute pJ/FLOP or pJ/input-bit metrics, inspect feasibility rules, or produce plots for the FP16 energy experiment.
---

# FP16 Energy Experiment

Use this skill to operate the repository as an experiment harness, not as a generic CUDA sample. Preserve the v2 definitions and keep energy runs separate from profiler runs.

## Canonical Definitions

- Treat 1 logical op as 1 warp-level FP16 `m16n16k16` MMA.
- Use `8192 FLOP/op` and `8192 input bits/op` for A+B FP16 input.
- Keep `threads/block = 32` and `warps/block = 1`.
- Interpret `blocks/SM` as resident warps per SM for this design.
- Treat reported energy as effective microbenchmark energy, not pure physical component energy.

## First Checks

1. Read `README.md`, `docs/a100_fp16_energy_experiment_design_v2.md`, and `docs/cross_platform_component_experiment_guide_ko.md` from the current workspace root when the task involves experiment interpretation or design changes. For component-energy claims also read `docs/component_energy_final_experiment_plan_ko.md` and `docs/component_energy_self_critique_ko.md`.
2. Check `git status --short` before editing; do not overwrite user data or measured results.
3. Confirm the target machine has Ampere-class CUDA, NVML, `cmake`, `nvcc`, `nvidia-smi`, and Python with `matplotlib` before promising build or plot success.
4. The default runtime profile is RTX 3090 (`--target-profile rtx3090`, `sm_86`, 82 SMs). Supported profiles are `v100`, `rtx3090`, `a100`, and `h100`; use `--target-profile auto` on the target machine when the profile should be selected from the runtime CUDA device.
5. If running without CUDA tooling, limit work to dry-run matrix generation, code inspection, and documentation updates.

Platform guide routing:

- A100 node runs: read `docs/a100_node_experiment_guide_ko.md`.
- V100 node runs: read `docs/v100_node_experiment_guide_ko.md`.
- H100 node runs: read `docs/h100_node_experiment_guide_ko.md`.

## Build Workflow

Use the project CMake target:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build build -j
```

Inspect build output for `ptxas` register counts and spills. If spills appear in primary kernels, mention the risk in the result summary and recommend an NCU spill/local-memory check.

## Feasibility Rules

Use the same profile-aware classification in code, sweeps, plots, and explanations:

- `invalid_min_tile`: `W_SM_KiB < blocks_per_SM`.
- `shared_resident`: `W_SM + B KiB <= profile shared KiB` and `W_SM/B <= profile max shared/block KiB`.
- `l2_candidate`: shared-resident is impossible and the full-profile working set fits profile L2.
- `dram_mixed_streaming`: full-profile working set exceeds profile L2.

Profile boundaries:

- V100: 80 SMs, 96 KiB shared/L1 per SM, max 32 resident blocks/SM, 6 MiB nominal L2.
- RTX 3090: 82 SMs, 100 KiB shared/L1 per SM, 99 KiB max dynamic shared memory per block, 6 MiB nominal L2, max 16 resident blocks/SM.
- A100: 108 SMs, 164 KiB shared/L1 per SM, 163 KiB max dynamic shared memory per block, 40 MiB nominal L2, max 32 resident blocks/SM.
- H100: SKU-dependent SM count, default profile 132 SMs, 228 KiB shared/L1 per SM, 227 KiB max dynamic shared memory per block, 50 MiB nominal L2, max 32 resident blocks/SM.

`blocks/SM=32` is valid for V100/A100/H100 but invalid/skipped on RTX 3090.

Reject or skip mode/regime mismatches:

- Run `shared_mma` only for `shared_resident`.
- Run `l2_mma` only for `l2_candidate`.
- Run `dram_mma` only for `dram_mixed_streaming`.

Use `--dry-run` before real measurement when changing `W_SM_KiB`, `blocks_per_SM`, `active_SM`, or mode.

## Energy Runs

Use NVML energy runs without Nsight Compute attached:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_fp16_energy_v2_raw.csv
```

Before measurement, record or ask the user to record:

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto --ncu /path/to/ncu --out results/summary/gpu_support_preflight.md
# For final platform packages, prefer the generated shell or explicit strict preflight:
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile a100 --strict --ncu /path/to/ncu --out results/summary/gpu_support_preflight.md
nvidia-smi -L
nvidia-smi --query-gpu=index,name,clocks.sm,clocks.mem,power.limit,temperature.gpu,ecc.mode.current --format=csv
```

Prefer `--seconds 10` or longer for final data. Use shorter runs only for sanity checks and label them as such.

## Sweep Workflow

Generate the matrix first:

```bash
python3 scripts/run_sweep.py --include-idle
```

Execute only after confirming the matrix size and runtime budget:

```bash
python3 scripts/run_sweep.py --include-idle --execute --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --seconds 10 --repeats 5
```

For smoke tests, constrain the matrix:

```bash
python3 scripts/run_sweep.py --execute \
  --gpu-ids 0 \
  --modes reg_mma,shared_mma \
  --w-sm-kib-values 32,128 \
  --blocks-per-sm-values 1,8,16 \
  --active-sm-values 82 \
  --seconds 2 \
  --repeats 1
```

## NCU Validation

Keep NCU validation separate from energy measurements. Use NCU to confirm tensor instruction count, L1/L2 cache hit rate, L1/L2/DRAM access counts, shared/L2/DRAM bytes, spill/local bytes, occupancy, active warps, and SMID distribution.

Query metrics when the NCU version is unknown:

```bash
scripts/run_ncu.sh --query-metrics
```

Run representative validation:

```bash
MODE=shared_mma W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 TARGET_PROFILE=rtx3090 scripts/run_ncu.sh
MODE=l2_mma W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 TARGET_PROFILE=rtx3090 scripts/run_ncu.sh
MODE=dram_mma W_SM_KIB=128 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 TARGET_PROFILE=rtx3090 scripts/run_ncu.sh
```

For WSL on Windows drivers, `sudo` inside Linux may not be sufficient for NCU counters. If `ERR_NVGPUCTRPERM` persists, enable GPU Performance Counters for all users in the NVIDIA App or NVIDIA Control Panel on Windows, then run `wsl --shutdown` before retrying.

V100/GV100 requires an Nsight Compute toolchain whose `ncu --list-chips` output includes `gv100`. NVIDIA's current release highlights announce dropped Volta support, so 2024.3/2025.1 are examples of candidate toolchains rather than a hard-coded rule.

Do not merge NCU replay energy with NVML energy-run CSV values. Join exported NCU counters later by run metadata when needed.

## Cross-Platform Component Finalplan

For A100/V100/H100 component-energy runs, prefer the generated finalplan command
script over hand-written command sequences:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5
```

Review and then run the generated shell script under `results/summary/`. The
flow must remain:

1. preflight,
2. energy sweeps without NCU,
3. NCU sidecar validation,
4. `analyze_ncu_path_acceptance.py`,
5. `analyze_matched_control_energy.py --require-ncu-denominator`.

For H100, explicitly state that the current kernels use the repository's WMMA
compatibility path, not Hopper-native WGMMA/TMA/FP8 paths.

NCU validation reports must include a cache/memory table with units:

| field | unit |
|---|---|
| L1 hit rate | % |
| L2 hit rate | % |
| L1 accesses | requests preferred, sectors fallback |
| L2 accesses | sectors |
| DRAM accesses | sectors |
| L1/L2/DRAM bytes | bytes |

## Result Handling

- Keep raw measured CSVs under `results/raw/`.
- Keep NCU reports under `results/ncu/`.
- Keep generated plots under `results/plots/`.
- Do not delete or rewrite existing result files unless the user explicitly asks.
- Treat rows as per-GPU rows. Sum active GPU rows with the same `run_id` for aggregate multi-GPU energy.
- Exclude primary-analysis rows with `smid_histogram_ok=false` unless the user specifically wants placement-failure diagnostics.
- When reporting completed sweep experiments, summarize the sweep conditions and results in tables whenever practical. Include units in every table header or cell label, such as `W_SM (KiB)`, `blocks/SM`, `active_SM (SMs)`, `elapsed_s (s)`, `net_E_J (J)`, `pJ/FLOP`, `pJ/input-bit`, `power (mW)`, `L2 (MiB)`, and `shared memory (KiB)`.
- Do not present sweep results only as prose when the data has clear axes such as mode, `W_SM`, `blocks/SM`, GPU profile, or pJ/FLOP. Use prose to explain trends after the table.

Compute:

```text
N_MMA = active_SM * blocks_per_SM * ITER
FLOP = N_MMA * 8192
input_bits = N_MMA * 8192
pJ/FLOP = net_E_J * 1e12 / FLOP
pJ/input-bit = net_E_J * 1e12 / input_bits
```

The binary already writes these columns for active MMA rows; recompute only when auditing.

## Mode Descriptions

Every experiment report must explain what each reported mode means before interpreting the numbers. Use a concise table like this when the report includes multiple modes:

| mode | meaning | main path being isolated |
|---|---|---|
| `idle` | No benchmark kernel is launched; NVML energy is measured during sleep. | System/GPU idle baseline |
| `empty` | Same persistent grid shape as active modes, but no MMA work is performed. | Launch, scheduling, loop, and placement overhead |
| `reg_fragment_only` | WMMA fragment/register setup without MMA. | Register/fragment setup control |
| `reg_operand_only` | WMMA register fragments are kept live and sampled in the same `ITER * reuse_factor` loop shape as `reg_mma`, but `mma_sync` is not executed. | No-MMA register-fragment/control baseline |
| `reg_mma` | WMMA fragments are filled from register values and repeatedly accumulated. | Effective Tensor Engine + register path |
| `reg_pressure` | Tensor Core is not used; scalar register payload variants are compiled and updated in a persistent loop. | Scalar register-pressure/control coefficient |
| `shared_load_only` | Operands are staged in CUDA shared memory and loaded into WMMA fragments without MMA. | Effective shared/L1 load control |
| `shared_mma` | Operands are staged in CUDA shared memory and loaded into WMMA fragments from shared memory. | Effective shared/L1 operand path |
| `l2_load_only` | Operands are loaded from a global working set selected to fit nominal GPU L2 after warm-up, without MMA. | Effective L2-hit load control |
| `l2_mma` | Operands are loaded from a global working set selected to fit nominal GPU L2 after warm-up. | Effective L2-hit operand path |
| `dram_load_only` | Operands are loaded from a larger streaming global working set exceeding nominal L2, without MMA. | Effective DRAM streaming load control |
| `dram_mma` | Operands are loaded from a larger streaming global working set exceeding nominal L2. | Effective DRAM streaming operand path |
| `store_only` | Repeated global store loop without MMA. | Store-only control |
| `store_path` | Focuses on global store/output-side overhead with the same persistent execution style. | Store-side overhead check |

When a report includes `shared_mma`, explicitly state that it is not A100-only: it means CUDA shared-memory operand staging, while the physical shared/L1 capacity and carveout limits are GPU-profile dependent.

## Plotting

Use:

```bash
python3 scripts/plot_results.py results/raw/a100_fp16_energy_v2_raw.csv --outdir results/plots
```

If `matplotlib` is missing, report that plotting cannot be verified locally and provide the install hint:

```bash
python3 -m pip install matplotlib
```

## Interpretation Language

Use these labels in reports and summaries:

- `effective Tensor Engine + register`
- `effective shared/L1 path`
- `effective L2-hit path`
- `effective DRAM streaming path`
- `empty persistent-kernel baseline`
- `idle NVML baseline`

Avoid claiming pure Tensor Core, pure register file, pure L2, or pure DRAM physical energy.

For `reg_mma`, never interpret `W_SM_KiB` as the register working-set size. In
the current WMMA implementation, `W_SM` is only a sweep coordinate for
register/control modes. The real register footprint is determined by ptxas
`registers/thread`, `threads_per_block`, and resident `blocks/SM`. Record the
ptxas register count and spill stores/loads whenever discussing `reg_mma`
precision. On the RTX 3090 sm_86 build checked on 2026-07-02,
`reg_mma_kernel` and `reg_operand_only_kernel` used 26 registers/thread with
0 spill stores/loads, which is about 3.25 KiB/block for 32 threads/block and
about 52 KiB/SM at 16 blocks/SM. Do not claim that choosing `W_SM=1 KiB`
or `W_SM=256 B` shrinks this register footprint; it does not. A 256 B
starting point can be a valid axis for a separate scalar/register-pressure
microbenchmark, but it is not a valid physical working-set axis for the
current WMMA `m16n16k16` `reg_mma` kernel because one FP16 A or B logical tile
is already 512 B/warp, A+B is 1 KiB/warp, and A+B+C is 2 KiB/warp before
compiler overhead. Better `reg_mma` precision comes from spill-free
compilation, large enough `ITER * reuse_factor` to amortize
prologue/epilogue/final-store costs, paired-difference against
`reg_operand_only`, and NCU/SASS confirmation that the steady loop has no
shared/global operand loads.

For scalar register-footprint experiments, use
`scripts/run_register_footprint_sweep.py` and
`scripts/analyze_register_footprint.py`. Always report both target payload
bytes/block and measured ptxas footprint bytes/block. Treat
`reg_pressure - empty` as a scalar register-pressure/control coefficient in
pJ/reg-update, not as pure register-file energy and not as the WMMA
`reg_mma` footprint.

## Known Implementation Boundary

The current kernels use WMMA fallback and mark CSV notes with `wmma_fallback=1`. If asked for a stricter low-level implementation, implement or review inline PTX `mma.sync.aligned.m16n8k16` and explicit `ldmatrix.shared`, then update README, this skill, and NCU expectations together.
