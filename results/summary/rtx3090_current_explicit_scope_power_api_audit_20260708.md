# Power API Measurement Audit

This report audits raw energy CSV rows against `docs/platforms/power_measurement_api_matrix_ko.md`. It checks whether the energy numerator is suitable for final component coefficients before NCU path acceptance and matched-control analysis.

- detail CSV: `results/summary/rtx3090_current_explicit_scope_power_api_audit_20260708.csv`
- total rows: 894

## Status Counts

| value | rows |
|---|---:|
| `reject` | 893 |
| `final_candidate` | 1 |

## Energy Source Counts

| value | rows |
|---|---:|
| `nvml_total_energy` | 894 |

## Integration Method Counts

| value | rows |
|---|---:|
| `total_energy_mj_delta` | 894 |

## Measurement Scope Counts

| value | rows |
|---|---:|
| `gpu_device_total_energy_counter` | 894 |

## Power Semantics Counts

| value | rows |
|---|---:|
| `one_sec_average` | 894 |

## File Counts

| file | final_candidate | provisional | reject |
|---|---:|---:|---:|
| `results/raw/rtx3090_finalplan_stability_dram_20260708_stability.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_finalplan_stability_l1_20260708_stability.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_finalplan_stability_l2_20260708_stability.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_finalplan_stability_shared_20260708_stability.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_finalplan_stability_tensor_20260708_stability.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_l1_30s_stability_20260708.csv` | 0 | 0 | 20 |
| `results/raw/rtx3090_l1_60s_stability_20260708.csv` | 0 | 0 | 16 |
| `results/raw/rtx3090_l1_duration_scaling_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_l1_paired_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_l1_paired_30s_stability_rerun2_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_l1_paired_lr8_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_l2_paired_lr4_lr8_30s_combined_20260708.csv` | 0 | 0 | 36 |
| `results/raw/rtx3090_l2_paired_lr8_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_power_scope_smoke_20260708.csv` | 1 | 0 | 0 |
| `results/raw/rtx3090_shared_duration_scaling_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_shared_fixediter_lr16_focus_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_fixediter_lr4_lr8_focus_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_shared_fixediter_lr4_lr8_lr16_20260708.csv` | 0 | 0 | 27 |
| `results/raw/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_20260708.csv` | 0 | 0 | 36 |
| `results/raw/rtx3090_shared_l2_30s_stability_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_rerun2_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_paired_lr16_60s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_paired_lr4_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_paired_lr8_30s_combined_20260708.csv` | 0 | 0 | 36 |
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_rerun2_20260708.csv` | 0 | 0 | 18 |
| `results/raw/rtx3090_targeted_l1_stability_20260708.csv` | 0 | 0 | 60 |
| `results/raw/rtx3090_targeted_l2_stability_20260708.csv` | 0 | 0 | 60 |
| `results/raw/rtx3090_targeted_shared_stability_20260708.csv` | 0 | 0 | 60 |
| `results/raw/rtx3090_tensor_fixed_iter_rf8_rf16_20260708.csv` | 0 | 0 | 20 |
| `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708.csv` | 0 | 0 | 30 |
| `results/raw/rtx3090_tensor_targeted_rf8_rf16_20260708.csv` | 0 | 0 | 24 |

## Reject Reasons

| value | rows |
|---|---:|
| `missing_explicit_measurement_scope` | 893 |

## Interpretation

- `final_candidate` means the row uses `nvml_total_energy` with `total_energy_mj_delta` and the expected `GetPowerUsage` semantics metadata for the profile. When `--require-explicit-measurement-scope` is used, the raw CSV must also contain `measurement_scope=gpu_device_total_energy_counter`; old rows that only allow inferred scope are rejected for final analysis.
- `provisional` means the row uses a fallback power integral. It should not be mixed into final pJ/FLOP or pJ/bit tables.
- `reject` means the row contradicts the expected power API matrix or lacks required metadata.
- This audit does not prove L1/L2/DRAM path correctness. NCU path acceptance is still required after this step.
- The measurement scope here is GPU/device telemetry from the raw harness CSV. Hopper module power and GPU memory power readings are preflight metadata only and must not be mixed into final component coefficients.
