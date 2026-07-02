# FP16 Tensor Core Energy Experiment v2

CUDA/C++ microbenchmark framework for estimating effective energy of a logical
warp-level FP16 `m16n16k16` MMA operation on NVIDIA Tensor Core GPUs.

The default runtime profile in this checkout targets GeForce RTX 3090
(`sm_86`, 82 SMs, 6 MiB nominal L2). Additional profiles are available for
V100, A100, and H100. Use `--target-profile auto` to select a profile from the
runtime CUDA device when running on the target machine.

This repository implements the v2 design in
`docs/a100_fp16_energy_experiment_design_v2.md`.

## Operation Definition

- 1 logical op = 1 warp-level FP16 `m16n16k16` MMA.
- 1 logical op = 4096 FMA = 8192 FLOP.
- 1 logical op input footprint = A+B FP16 = 1KiB = 8192 bits.
- `threads/block = 32`, so `blocks/SM = resident warps/SM`.

The current kernel implementation uses CUDA WMMA as the portable Tensor Core
path. In low-level SASS this may compile to multiple tensor instructions for one
logical `m16n16k16` op. Raw inline PTX `mma.sync.aligned.m16n8k16` and explicit
`ldmatrix` are not the primary implementation yet; CSV rows mark
`wmma_fallback=1` in `notes`.

## Build

```bash
/home/bang001/miniforge3/envs/ssc21env/bin/cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/home/bang001/miniforge3/envs/ssc21env/bin/nvcc \
  -DCUDAToolkit_ROOT=/home/bang001/miniforge3/envs/ssc21env \
  -DCMAKE_CUDA_ARCHITECTURES=86
/home/bang001/miniforge3/envs/ssc21env/bin/cmake --build build -j
```

NVML is required. If CMake cannot find it, make sure the NVIDIA driver
development files are installed or `CUDA_PATH` points at a CUDA toolkit
installation. The build enables `-Xptxas=-v` so register count and spill warnings
are visible in the build log.

Before measurement, check the platform state manually:

```bash
nvidia-smi -L
sudo nvidia-smi -pm 1
nvidia-smi --query-gpu=index,name,clocks.sm,clocks.mem,power.limit,temperature.gpu,ecc.mode.current --format=csv
```

This tool records clocks, temperature, power limit, and ECC metadata where NVML
exposes them, but it does not change clocks or power limits.

## CLI Examples

Feasibility only:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_mma \
  --w-sm-kib 128 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --dry-run
```

Supported target profiles:

| profile | GPU family | CC | default SMs | L2 | shared/SM | max blocks/SM | NVML `GetPowerUsage` meaning |
|---|---|---:|---:|---:|---:|---:|---|
| `v100` | Volta GV100 | 7.0 | 80 | 6 MiB | 96 KiB | 32 | instantaneous |
| `rtx3090` | Ampere GA10x | 8.6 | 82 | 6 MiB | 100 KiB | 16 | 1-second average |
| `a100` | Ampere GA100 | 8.0 | 108 | 40 MiB | 164 KiB | 32 | instantaneous |
| `h100` | Hopper GH100 | 9.0 | 132 default, runtime/SKU should be checked | 50 MiB | 228 KiB | 32 | 1-second average |

Run a support preflight before collecting new data:

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto \
  --ncu /path/to/ncu \
  --out results/summary/gpu_support_preflight.md
```

The preflight records the detected profile, NVML/NVIDIA driver state, Nsight
Compute chip support, and a binary dry-run result.

Single GPU register/Tensor Core run:

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

L2 and DRAM path examples:

```bash
./build/a100_fp16_energy_v2 --gpu-list 0 --mode l2_mma \
  --w-sm-kib 64 --blocks-per-sm 8 --target-profile rtx3090 --active-sm 82 --seconds 10

./build/a100_fp16_energy_v2 --gpu-list 0 --mode dram_mma \
  --w-sm-kib 128 --blocks-per-sm 8 --target-profile rtx3090 --active-sm 82 --seconds 10
```

Idle baseline with zero active GPUs:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list none --mode idle --w-sm-kib 1 --blocks-per-sm 1 \
  --target-profile rtx3090 --active-sm 82 --seconds 10 --repeats 5
```

## Modes

- `idle`: no kernel, NVML energy delta during sleep.
- `empty`: same grid shape, persistent loop, no MMA.
- `reg_mma`: WMMA fragments filled in registers, repeated MMA, final checksum store.
- `shared_mma`: dynamic shared working set, shared load to WMMA fragments, MMA.
- `l2_mma`: global working set, warm-up before measurement, cache-hit candidate.
- `dram_mma`: large global working set with streaming tile order.
- `store_path`: global store-focused path for output-side overhead checks.

`shared_mma` is not an A100-only concept. On RTX 3090 / Ampere GA102 it means
the operands are staged through CUDA shared memory and loaded into WMMA
fragments from the shared-memory address space. The physical L1/shared-memory
organization and limits differ from A100, so feasibility uses the RTX 3090
profile values rather than the A100 164 KiB shared/L1 budget.
The same interpretation applies to V100 and H100, but with their own profile
limits.

Invalid combinations fail before execution. The shared/L2/DRAM classification is
the design rule:

- `invalid_min_tile`: `W_SM_KiB < blocks_per_SM`.
- `shared_resident`: `W_SM + B KiB <= profile shared KiB` and
  `W_SM/B <= profile max shared/block KiB`.
- `l2_candidate`: full-profile working set fits the nominal profile L2
  (`82 * W_SM <= 6MiB` for RTX 3090).
- `dram_mixed_streaming`: full-profile working set exceeds nominal profile L2.

## Sweep

Materialize the design matrix without executing:

```bash
python3 scripts/run_sweep.py --include-idle
```

Run the matrix:

```bash
python3 scripts/run_sweep.py \
  --include-idle \
  --execute \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --seconds 10 \
  --repeats 5
```

For short sanity runs, constrain the matrix:

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

## Nsight Compute

Energy runs and NCU profiling runs are intentionally separate.

```bash
scripts/run_ncu.sh --query-metrics

MODE=shared_mma W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 \
  scripts/run_ncu.sh

MODE=dram_mma W_SM_KIB=8192 BLOCKS_PER_SM=8 CACHE_CONTROL=all \
  scripts/run_ncu.sh
```

NCU reports are written under `results/ncu/`. The raw energy CSV includes NCU
columns, initialized to zero; populate or join those columns from NCU exports
before using the NCU bytes/op visualization.

Nsight Compute support is version dependent. Current Nsight Compute supports
GA10x, GA100, and GH100, while V100/GV100 requires an older supported NCU
toolchain such as the 2024.3 or 2025.1 release series.

## Plotting

```bash
python3 scripts/plot_results.py results/raw/a100_fp16_energy_v2_raw.csv \
  --outdir results/plots
```

Generated plots include:

- energy vs active GPU count
- energy vs active SM count
- pJ/FLOP vs blocks/SM
- pJ/FLOP vs `W_SM`
- pJ/input-bit vs `W_SM`
- NCU shared/L2/DRAM bytes per logical op vs `W_SM`
- feasibility heatmap
- regression residual plot when `predicted_E_J` exists in the CSV

## CSV Notes

Rows are per GPU. For multi-GPU runs, active GPU rows use per-GPU operation
counts:

```text
N_MMA = active_SM * blocks_per_SM * ITER
FLOP = N_MMA * 8192
input_bits = N_MMA * 8192
```

Aggregate multi-GPU energy by summing active rows with the same `run_id`. Inactive
GPU rows are still emitted so idle drift and system-side effects remain visible.

For non-idle modes the binary performs a pre-run idle measurement and stores an
elapsed-time-scaled `idle_baseline_J`. `net_E_J = delta_E_J - idle_baseline_J`.

## Current Limitations

- WMMA fallback is implemented; raw inline PTX `m16n8k16` and explicit
  `ldmatrix.shared` are future refinements.
- SM placement uses soft control (`grid = active_SM * blocks_per_SM`) plus SMID
  histogram validation. Runs with `smid_histogram_ok=false` should be excluded
  from primary analysis.
- Reported coefficients are effective microbenchmark coefficients, not pure
  physical component energies. Prefer labels such as `effective Tensor Engine +
  register`, `effective shared/L1 path`, `effective L2-hit path`, and `effective
  DRAM streaming path`.

## Included Reference Assets

- `docs/a100_fp16_energy_experiment_design_v2.md`
- `docs/a100_v2_design_assets/a100_v2_feasibility_matrix.csv`
- `docs/a100_v2_design_assets/a100_v2_feasibility_heatmap.png`
- `docs/a100_v2_design_assets/a100_v2_workingset_boundaries.png`
- `docs/a100_v2_design_assets/a100_v2_ops_per_iteration.png`
