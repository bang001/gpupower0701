# GPU Support Preflight

- Date: 2026-07-13T19:49:51
- GPU index: 0
- Requested profile: `a100`
- Detected profile: `rtx3090`

## Preflight Verdict

- `strict`: true
- `profile_gate`: fail
- `device_memory_gate`: pass
- `ncu_gate`: fail
- `cuda_compiler_gate`: fail
- `dry_run_gate`: pass
- `overall`: fail
- `errors`: profile_mismatch_requested_a100_detected_rtx3090;ncu_chip_not_supported_unknown;ncu_query_metrics_not_ok_127;nvcc_target_not_supported_compute_80_unknown

## GPU

- `index`: 0
- `name`: NVIDIA GeForce RTX 3090
- `uuid`: GPU-6176a2fd-d534-e78c-edd2-78b8db8109b0
- `driver_version`: 591.86
- `compute_cap`: 8.6
- `memory.total`: 24576
- `power.draw`: 17.77
- `power.draw.average`: 17.77
- `power.draw.instant`: 19.67
- `power.limit`: 370.00
- `clocks.sm`: 210
- `clocks.mem`: 405
- `temperature.gpu`: 47
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
Average Power Draw                             : 18.01 W
Instantaneous Power Draw                       : 19.07 W
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

- `cc`: 8.0
- `cuda_arch`: 80
- `full_sm`: 108
- `l2_mib`: 40
- `combined_l1_shared_kib`: 192
- `shared_kib`: 164
- `max_shared_per_block_kib`: 163
- `max_blocks_per_sm`: 32
- `ncu_chip`: ga100
- `power_usage_semantics`: instant
- `ncu_policy`: Current Nsight Compute supports GA100.
- `cuda_toolchain_policy`: not_applicable
- `reference_memory`: not_applicable
- `dry_run_gpu`: 0
- `dry_run_active_sm`: 108
- `min_device_memory_mib`: 0

## CUDA Compiler

- `target`: compute_80
- `target_supported`: unknown
- `version_rc`: 127
- `version`: not found: nvcc
- `list_gpu_arch_rc`: 127
- `list_gpu_arch_error`: not found: nvcc

## Nsight Compute

- `version_rc`: 127
- `version`: not found: ncu
- `list_chips_rc`: 127
- `chip_supported`: unknown
- `query_metrics_rc`: 127
- `query_metrics_ok`: false
- `list_chips_error`: not found: ncu
- `query_metrics_error`: not found: ncu

## Binary Dry Run

- `return_code`: 0

```text
dry_run=true
mode=shared_scalar_load_only
gpu_list=0
target_profile=a100
architecture_family=ampere_ga100
chip=ga100
cuda_arch=80
compute_capability=8.0
max_blocks_per_SM=32
target_l2_MiB=40
target_unified_L1_shared_KiB_per_SM=192
target_shared_KiB_per_SM=164
target_max_shared_KiB_per_block=163
nvml_power_usage_semantics=instant
tensor_modes=implemented:fp16_wmma;hardware_optional:tf32,bf16,fp64_tc,int8,int4,binary,sparsity
W_SM_KiB=64
W_SM_label=64 KiB
blocks_per_SM=16
threads_per_block=32
active_SM=108
reuse_factor=1
load_repeat=1
store_repeat=1
global_warmup_passes=1
l2_residency_policy=normal
l2_address_layout=contiguous
global_block_stride_bytes=4096
physical_global_allocation_bytes=7077888
reg_payload_bytes_per_block=0
reg_payload_regs_per_thread=0
valid_feasibility=true
mode_allowed=true
regime=shared_resident
shared_resident=true
l2_candidate=true
dram_candidate=false
reason=W_SM + B KiB fits a100 shared memory capacity; full-GPU working set also fits nominal L2
W_block_KiB=4
tiles_per_block=4
full_gpu_working_set_MiB=6.75
```
