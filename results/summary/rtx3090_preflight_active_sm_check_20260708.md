# GPU Support Preflight

- Date: 2026-07-08T23:42:16
- GPU index: 0
- Requested profile: `auto`
- Detected profile: `rtx3090`

## GPU

- `index`: 0
- `name`: NVIDIA GeForce RTX 3090
- `uuid`: GPU-6176a2fd-d534-e78c-edd2-78b8db8109b0
- `driver_version`: 591.86
- `compute_cap`: 8.6
- `power.draw`: 20.69
- `power.draw.average`: 20.69
- `power.draw.instant`: 17.48
- `power.limit`: 370.00
- `clocks.sm`: 210
- `clocks.mem`: 405
- `temperature.gpu`: 49
- `ecc.mode.current`: [N/A]
- `power_query_fields`: extended

## Power Scope

The final component-energy numerator must come from the harness raw CSV, preferably `nvml_total_energy`. The fields below are preflight metadata for distinguishing GPU/device, module, and memory power scopes; do not mix module or memory power into component coefficients.

- `module_power_query_rc`: 0
- `module.power.draw.average`: [N/A]
- `module.power.draw.instant`: [N/A]
- `module.power.limit`: [N/A]
- `module.enforced.power.limit`: [N/A]
- `power_detail_query_rc`: 0

```text
GPU Power Readings
Average Power Draw                             : 20.45 W
Instantaneous Power Draw                       : 18.72 W
Current Power Limit                            : 370.00 W
Requested Power Limit                          : 370.00 W
Default Power Limit                            : 370.00 W
Min Power Limit                                : 100.00 W
Max Power Limit                                : 390.00 W
GPU Memory Power Readings
Average Power Draw                             : N/A
Instantaneous Power Draw                       : N/A
Module Power Readings
Average Power Draw                             : N/A
Instantaneous Power Draw                       : N/A
Current Power Limit                            : N/A
Requested Power Limit                          : N/A
Default Power Limit                            : N/A
Min Power Limit                                : N/A
Max Power Limit                                : N/A
```

## Selected Harness Profile

- `cc`: 8.6
- `cuda_arch`: 86
- `full_sm`: 82
- `l2_mib`: 6
- `combined_l1_shared_kib`: 128
- `shared_kib`: 100
- `max_shared_per_block_kib`: 99
- `max_blocks_per_sm`: 16
- `ncu_chip`: ga102
- `power_usage_semantics`: one_sec_average
- `ncu_policy`: Current Nsight Compute supports GA10x; WSL needs performance counter permission.
- `dry_run_gpu`: 0
- `dry_run_active_sm`: 82

## Nsight Compute

- `version_rc`: 0
- `version`: NVIDIA (R) Nsight Compute Command Line Profiler
- `list_chips_rc`: 0
- `chip_supported`: true
- `query_metrics_rc`: 0
- `query_metrics_ok`: true

## Binary Dry Run

- `return_code`: 0

```text
dry_run=true
mode=shared_scalar_load_only
gpu_list=0
target_profile=rtx3090
architecture_family=ampere_ga10x
chip=ga102
cuda_arch=86
compute_capability=8.6
max_blocks_per_SM=16
target_l2_MiB=6
target_unified_L1_shared_KiB_per_SM=128
target_shared_KiB_per_SM=100
target_max_shared_KiB_per_block=99
nvml_power_usage_semantics=one_sec_average
tensor_modes=implemented:fp16_wmma;hardware_optional:tf32,bf16,int8,int4,sparsity
W_SM_KiB=64
W_SM_label=64 KiB
blocks_per_SM=16
threads_per_block=32
active_SM=82
reuse_factor=1
load_repeat=1
store_repeat=1
reg_payload_bytes_per_block=0
reg_payload_regs_per_thread=0
valid_feasibility=true
mode_allowed=true
regime=shared_resident
shared_resident=true
l2_candidate=true
dram_candidate=false
reason=W_SM + B KiB fits rtx3090 shared memory capacity; full-GPU working set also fits nominal L2
W_block_KiB=4
tiles_per_block=4
full_gpu_working_set_MiB=5.125
```
