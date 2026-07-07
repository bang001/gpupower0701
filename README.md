# FP16 Tensor Core Energy Experiment v2

CUDA/C++ microbenchmark framework for estimating effective energy of a logical
warp-level FP16 `m16n16k16` MMA operation on NVIDIA Tensor Core GPUs.

The default runtime profile in this checkout targets GeForce RTX 3090
(`sm_86`, 82 SMs, 6 MiB nominal L2). Additional profiles are available for
V100, A100, and H100. Use `--target-profile auto` to select a profile from the
runtime CUDA device when running on the target machine.

This repository implements the v2 design in
`docs/a100_fp16_energy_experiment_design_v2.md`.
For component-energy claims, use the acceptance-first finalplan flow:
`docs/component_energy_final_experiment_plan_ko.md` and
`docs/cross_platform_component_experiment_guide_ko.md`. Memory pJ/bit results
must use NCU actual traffic counters and should be reported as transaction-path
effective coefficients, not as SRAM/HBM bitcell energy. The self-critique and
known limitations are tracked in `docs/component_energy_self_critique_ko.md`.
For the detailed NCU validation and pJ/FLOP or pJ/byte calculation method, see
`docs/ncu_validation_energy_calculation_ko.md`.

Platform guides:

| GPU | guide |
|---|---|
| A100 | `docs/a100_node_experiment_guide_ko.md` |
| V100 | `docs/v100_node_experiment_guide_ko.md` |
| H100 | `docs/h100_node_experiment_guide_ko.md` |

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

| profile | GPU family | CC | default SMs | L2 | combined L1/shared | shared allocation | max shared/block | max blocks/SM | NVML `GetPowerUsage` meaning |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `v100` | Volta GV100 | 7.0 | 80 | 6 MiB | 128 KiB/SM | 96 KiB/SM | 96 KiB/block | 32 | instantaneous |
| `rtx3090` | Ampere GA10x | 8.6 | 82 | 6 MiB | 128 KiB/SM | 100 KiB/SM | 99 KiB/block | 16 | 1-second average |
| `a100` | Ampere GA100 | 8.0 | 108 | 40 MiB | 192 KiB/SM | 164 KiB/SM | 163 KiB/block | 32 | instantaneous |
| `h100` | Hopper GH100 | 9.0 | 132 default, runtime/SKU should be checked | 50 MiB | 256 KiB/SM | 228 KiB/SM | 227 KiB/block | 32 | 1-second average |

`combined L1/shared` is the SM-local unified capacity. `shared allocation`
is the CUDA shared-memory capacity used for feasibility checks. Do not treat
these two columns as the same quantity.

Run a support preflight before collecting new data:

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto \
  --ncu /path/to/ncu \
  --out results/summary/gpu_support_preflight.md
```

The preflight records the detected profile, combined/shared capacity metadata,
NVML/NVIDIA driver state, Nsight Compute chip support, and a binary dry-run
result.

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
- `clocked_empty`: duration-calibrated scheduler/control loop with no memory
  operand traffic.
- `reg_fragment_only`: WMMA fragment/register setup without MMA.
- `reg_operand_only`: WMMA register fragments kept live and sampled in the
  same `ITER * reuse_factor` loop shape as `reg_mma`, but without `mma_sync`.
- `reg_mma`: WMMA fragments filled in registers, repeated MMA, final checksum store.
- `reg_pressure`: scalar register-pressure payload sweep without Tensor Core work.
- `addr_only`: global-memory tile address walk without issuing operand loads.
- `global_l1_load_only`: small global working set candidate for L1-hit operand
  loads. Treat as a candidate until NCU verifies L1 hit rate and traffic.
- `shared_load_only`: dynamic shared working set, shared WMMA operand loads, no MMA.
- `shared_mma`: dynamic shared working set, shared load to WMMA fragments, MMA.
- `l2_load_only`: global working set warm-up, L2-hit candidate operand loads, no MMA.
- `l2_mma`: global working set, warm-up before measurement, cache-hit candidate.
- `dram_load_only`: large global working set with streaming operand loads, no MMA.
- `dram_mma`: large global working set with streaming tile order.
- `store_only`: repeated global store loop without MMA.
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

Component-decomposition now uses an acceptance-first finalplan flow for primary
results. Generate a platform-specific command plan, run energy sweeps without
NCU attached, run NCU sidecar validation separately, classify accepted paths,
then analyze matched controls with NCU byte-denominator scaling:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5

bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

Use `--target-profile v100` or `--target-profile h100` on those platforms.
Review the generated shell script before submitting a long cluster job. Final
byte-path claims must use `scripts/analyze_ncu_path_acceptance.py` and
`scripts/analyze_matched_control_energy.py --require-ncu-denominator`.

The older duration-calibrated regression/NNLS path remains useful for model
stress tests. It lets each mode calibrate to the requested measurement time and
then fits `net_E_J` with an explicit `elapsed_s` term:

```bash
python3 scripts/run_component_regression_sweep.py \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --modes empty,reg_operand_only,reg_mma,shared_load_only,shared_mma,l2_load_only,l2_mma,dram_load_only,dram_mma,store_only \
  --w-sm-kib-values 64,8192 \
  --blocks-per-sm-values 8,16 \
  --active-sm-values 82 \
  --reuse-factors 1,2,4,8 \
  --load-repeats 1,2,4,8 \
  --store-repeats 1,2,4,8 \
  --seconds 10 \
  --repeats 5 \
  --execute

python3 scripts/fit_component_energy_model.py \
  results/raw/component_regression_raw.csv \
  --out-csv results/summary/component_regression_fit.csv \
  --out-md results/summary/component_regression_fit.md \
  --baseline-terms mode \
  --non-negative
```

`--baseline-terms mode|family` separates mode-specific fixed/control offsets
from physical candidate slopes. `--non-negative` uses an active-set constrained
fit so elapsed and component candidate coefficients are not reported as
negative. If a coefficient is clamped to zero, treat it as
`zero_bound_or_not_identified`, not as proof that the physical component has
zero energy. For noisy smoke runs, add `--min-elapsed-s` and
`--exclude-negative-net-energy`.

For a supplemental byte-variation stress test, the regression runner can bypass
per-mode calibration and use fixed `ITER`:

```bash
python3 scripts/run_component_regression_sweep.py \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --modes shared_load_only,l2_load_only,dram_load_only \
  --w-sm-kib-values 64,8192 \
  --blocks-per-sm-values 16 \
  --active-sm-values 82 \
  --reuse-factors 1 \
  --load-repeats 1,2,4,8 \
  --store-repeats 1 \
  --seconds 1 \
  --iters 1000000 \
  --repeats 1 \
  --execute
```

Fixed-ITER runs make logical bytes vary directly, but elapsed can spread widely.
Use them to check monotonicity and model identifiability, not as final physical
pJ/byte values without NCU traffic and stall validation.

The older pair-centric runner is retained as a diagnostic/sanity-check tool. It
calibrates a reference mode once per coordinate and reuses the same `ITER` for
paired control modes, so elapsed-time mismatch can invalidate component
interpretation. `scripts/analyze_component_pairs.py` now emits
`elapsed_ratio`, `valid_component_estimate`, and `diagnostic` columns:

```bash
python3 scripts/run_component_pairs.py \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --w-sm-kib-values 64,128 \
  --blocks-per-sm-values 8,16 \
  --active-sm-values 82 \
  --seconds 10 \
  --repeats 5

python3 scripts/analyze_component_pairs.py results/raw/component_pairs_raw.csv
```

The most important register/Tensor Core pairs are:

| pair | interpretation | unit |
|---|---|---|
| `reg_operand_only - empty` | no-MMA register-fragment/control baseline | pJ/reg-op |
| `reg_mma - reg_operand_only` | effective Tensor Core MMA incremental cost candidate | pJ/FLOP |
| `reg_mma - empty` | legacy effective Tensor Engine + register path baseline | pJ/FLOP |

`reg_operand_only` is not pure register-file energy. It is a matched no-MMA
control that keeps WMMA fragments live and samples fragment values to prevent
optimization, so `reg_mma - reg_operand_only` must still be reported as an
effective incremental cost.

Use `--reuse-factors`, `--load-repeats`, and `--store-repeats` to vary logical
MMA reuse, operand-load count, and store count independently. The raw CSV writes
`expected_reg_operand_ops`, `expected_shared_bytes`, `expected_l2_bytes`,
`expected_dram_bytes`, and `expected_store_bytes` for static
paired-difference and regression analysis.

Static expected-byte regression is still not physical SRAM/L2/DRAM energy.
For final cache hierarchy claims, run NCU validation and prefer actual L1/L2/DRAM
traffic counters over `expected_*_bytes`.

## Register Footprint Sweep

Do not use `W_SM` as the register working-set axis for `reg_mma`. For register
footprint experiments, use the dedicated scalar `reg_pressure` mode and the
ptxas-derived footprint metadata.

```bash
python3 scripts/run_register_footprint_sweep.py \
  --binary ./build/a100_fp16_energy_v2 \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --reg-payload-bytes-values 256,512,1024,2048,4096,8192,16384 \
  --blocks-per-sm-values 1,2,4,8,16 \
  --active-sm-values 82 \
  --reuse-factors 1,2,4,8 \
  --seconds 10 \
  --repeats 3 \
  --output results/raw/rtx3090_register_footprint.csv \
  --calibration-output results/raw/rtx3090_register_footprint_calibration.csv \
  --matrix-csv results/raw/rtx3090_register_footprint_matrix.csv \
  --ptxas-csv results/summary/rtx3090_register_footprint_ptxas.csv \
  --execute

python3 scripts/analyze_register_footprint.py \
  results/raw/rtx3090_register_footprint.csv \
  --matrix-csv results/raw/rtx3090_register_footprint_matrix.csv \
  --out-csv results/summary/rtx3090_register_footprint_summary.csv \
  --out-md results/summary/rtx3090_register_footprint_summary.md
```

The runner first writes ptxas metadata: target payload bytes/block, measured
registers/thread, compiler footprint bytes/block, estimated resident
blocks/SM, and spill-free status. By default it skips payload/block
coordinates that would spill or exceed the ptxas-estimated resident block
limit. Use `--allow-spills` only for an explicit spill-sensitivity experiment.

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
`scripts/run_ncu.sh` and `scripts/run_ncu_validation.sh` also export raw/details
NCU CSV files and generate cache summaries. The summary table includes L1 hit
rate (%), L2 hit rate (%), L1 accesses, L2 accesses (sectors), DRAM accesses
(sectors), and L1/L2/DRAM bytes. L1 accesses prefer request counters when NCU
provides them and fall back to sector counters otherwise.

Nsight Compute support is version dependent. As of the 2026-06-29 release
history, NVIDIA lists Nsight Compute 2026.2.1 as the latest public release, and
the release highlights announce dropped Volta support. For V100/GV100, use an
NCU toolchain whose `ncu --list-chips` output includes `gv100`; 2024.3/2025.1
are examples, not a hard-coded rule.

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
- Do not report `*_load_only - empty` pair coefficients as physical component
  energy unless elapsed-time matching and NCU traffic validation pass. Large
  elapsed ratios or negative `*_mma - *_load_only` coefficients mean the pair is
  diagnostic-only.

## Included Reference Assets

- `docs/a100_fp16_energy_experiment_design_v2.md`
- `docs/a100_v2_design_assets/a100_v2_feasibility_matrix.csv`
- `docs/a100_v2_design_assets/a100_v2_feasibility_heatmap.png`
- `docs/a100_v2_design_assets/a100_v2_workingset_boundaries.png`
- `docs/a100_v2_design_assets/a100_v2_ops_per_iteration.png`
