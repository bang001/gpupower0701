# GPU Support Preflight

- Date: 2026-07-13T19:49:44
- GPU index: 0
- Requested profile: `v100`
- Detected profile: `rtx3090`

## Preflight Verdict

- `strict`: true
- `profile_gate`: fail
- `device_memory_gate`: fail
- `ncu_gate`: fail
- `cuda_compiler_gate`: fail
- `dry_run_gate`: fail
- `overall`: fail
- `errors`: profile_mismatch_requested_v100_detected_rtx3090;ncu_chip_not_supported_unknown;ncu_query_metrics_not_ok_127;nvcc_target_not_supported_compute_70_unknown;binary_dry_run_failed_rc_127;gpu_memory_total_below_min_30000_mib_observed_24576_mib

## GPU

- `index`: 0
- `name`: NVIDIA GeForce RTX 3090
- `uuid`: GPU-6176a2fd-d534-e78c-edd2-78b8db8109b0
- `driver_version`: 591.86
- `compute_cap`: 8.6
- `memory.total`: 24576
- `power.draw`: 19.29
- `power.draw.average`: 19.29
- `power.draw.instant`: 19.98
- `power.limit`: 370.00
- `clocks.sm`: 210
- `clocks.mem`: 405
- `temperature.gpu`: 48
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
Average Power Draw                             : 19.33 W
Instantaneous Power Draw                       : 19.77 W
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

- `cc`: 7.0
- `cuda_arch`: 70
- `full_sm`: 80
- `l2_mib`: 6
- `combined_l1_shared_kib`: 128
- `shared_kib`: 96
- `max_shared_per_block_kib`: 96
- `max_blocks_per_sm`: 32
- `ncu_chip`: gv100
- `power_usage_semantics`: instant
- `ncu_policy`: Nsight Compute 2024.3 is confirmed to support GV100. Always require --list-chips and --query-metrics --chips gv100 success because newer releases can remove Volta support.
- `cuda_toolchain_policy`: Use a compiler that lists compute_70. CUDA 12.x is the recommended V100 build line; CUDA 13 removed Volta offline compilation support.
- `reference_memory`: 32 GB HBM2 reference package; pass --min-device-memory-mib 0 for a separately reported 16 GB SKU.
- `dry_run_gpu`: 0
- `dry_run_active_sm`: 80
- `min_device_memory_mib`: 30000

## CUDA Compiler

- `target`: compute_70
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

- `return_code`: 127

```text
not found: ./build-v100/a100_fp16_energy_v2
```
