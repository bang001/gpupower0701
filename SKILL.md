---
name: fp16-energy-experiment
description: Run, debug, validate, and analyze the FP16 Tensor Core energy microbenchmark in this repository. Use when Codex is asked to build the CUDA/NVML project, run idle/empty/reg_mma/shared_mma/l2_mma/dram_mma/store_path experiments, generate RTX 3090 or A100 sweep matrices, collect Nsight Compute validation reports, compute pJ/FLOP or pJ/input-bit metrics, inspect feasibility rules, or produce plots for the FP16 energy experiment.
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

1. Read `README.md` and `docs/a100_fp16_energy_experiment_design_v2.md` from the current workspace root when the task involves experiment interpretation or design changes.
2. Check `git status --short` before editing; do not overwrite user data or measured results.
3. Confirm the target machine has Ampere-class CUDA, NVML, `cmake`, `nvcc`, `nvidia-smi`, and Python with `matplotlib` before promising build or plot success.
4. The default runtime profile is RTX 3090 (`--target-profile rtx3090`, `sm_86`, 82 SMs). Use `--target-profile a100` and `sm_80` only when explicitly targeting A100.
5. If running without CUDA tooling, limit work to dry-run matrix generation, code inspection, and documentation updates.

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

For RTX 3090, the default profile uses 82 SMs, 100 KiB shared/L1 per SM, 99 KiB max dynamic shared memory per block, 6 MiB nominal L2, and max 16 resident blocks per SM. `blocks/SM=32` is valid for A100 but invalid/skipped on RTX 3090.

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

Keep NCU validation separate from energy measurements. Use NCU to confirm tensor instruction count, shared/L2/DRAM bytes, spill/local bytes, occupancy, active warps, and SMID distribution.

Query metrics when the NCU version is unknown:

```bash
scripts/run_ncu.sh --query-metrics
```

Run representative validation:

```bash
MODE=shared_mma W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 scripts/run_ncu.sh
MODE=l2_mma W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 scripts/run_ncu.sh
MODE=dram_mma W_SM_KIB=128 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 scripts/run_ncu.sh
```

For WSL on Windows drivers, `sudo` inside Linux may not be sufficient for NCU counters. If `ERR_NVGPUCTRPERM` persists, enable GPU Performance Counters for all users in the NVIDIA App or NVIDIA Control Panel on Windows, then run `wsl --shutdown` before retrying.

Do not merge NCU replay energy with NVML energy-run CSV values. Join exported NCU counters later by run metadata when needed.

## Result Handling

- Keep raw measured CSVs under `results/raw/`.
- Keep NCU reports under `results/ncu/`.
- Keep generated plots under `results/plots/`.
- Do not delete or rewrite existing result files unless the user explicitly asks.
- Treat rows as per-GPU rows. Sum active GPU rows with the same `run_id` for aggregate multi-GPU energy.
- Exclude primary-analysis rows with `smid_histogram_ok=false` unless the user specifically wants placement-failure diagnostics.

Compute:

```text
N_MMA = active_SM * blocks_per_SM * ITER
FLOP = N_MMA * 8192
input_bits = N_MMA * 8192
pJ/FLOP = net_E_J * 1e12 / FLOP
pJ/input-bit = net_E_J * 1e12 / input_bits
```

The binary already writes these columns for active MMA rows; recompute only when auditing.

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

## Known Implementation Boundary

The current kernels use WMMA fallback and mark CSV notes with `wmma_fallback=1`. If asked for a stricter low-level implementation, implement or review inline PTX `mma.sync.aligned.m16n8k16` and explicit `ldmatrix.shared`, then update README, this skill, and NCU expectations together.
