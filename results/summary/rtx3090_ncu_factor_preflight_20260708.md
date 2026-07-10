# GPU Support Preflight

- Date: 2026-07-08T01:15:53
- GPU index: 0
- Requested profile: `rtx3090`
- Detected profile: `rtx3090`

## GPU

- `index`: 0
- `name`: NVIDIA GeForce RTX 3090
- `uuid`: GPU-6176a2fd-d534-e78c-edd2-78b8db8109b0
- `driver_version`: 591.86
- `compute_cap`: 8.6
- `power.draw`: 19.01
- `power.draw.average`: 19.01
- `power.draw.instant`: 18.62
- `power.limit`: 370.00
- `clocks.sm`: 210
- `clocks.mem`: 405
- `power_query_fields`: extended

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
