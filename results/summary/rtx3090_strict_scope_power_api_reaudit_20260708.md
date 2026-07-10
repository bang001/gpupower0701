# Power API Measurement Audit

This report audits raw energy CSV rows against `docs/platforms/power_measurement_api_matrix_ko.md`. It checks whether the energy numerator is suitable for final component coefficients before NCU path acceptance and matched-control analysis.

- detail CSV: `results/summary/rtx3090_strict_scope_power_api_reaudit_20260708.csv`
- total rows: 72

## Status Counts

| value | rows |
|---|---:|
| `final_candidate` | 72 |

## Energy Source Counts

| value | rows |
|---|---:|
| `nvml_total_energy` | 72 |

## Integration Method Counts

| value | rows |
|---|---:|
| `total_energy_mj_delta` | 72 |

## Measurement Scope Counts

| value | rows |
|---|---:|
| `gpu_device_total_energy_counter` | 72 |

## Power Semantics Counts

| value | rows |
|---|---:|
| `one_sec_average` | 72 |

## File Counts

| file | final_candidate | provisional | reject |
|---|---:|---:|---:|
| `results/raw/rtx3090_strict_scope_l1_lr4_focus_20260708.csv` | 18 | 0 | 0 |
| `results/raw/rtx3090_strict_scope_l2_lr4_lr8_focus_20260708.csv` | 18 | 0 | 0 |
| `results/raw/rtx3090_strict_scope_shared_lr8_focus_20260708.csv` | 18 | 0 | 0 |
| `results/raw/rtx3090_strict_scope_tensor_rf8_rf16_20260708.csv` | 18 | 0 | 0 |

## Interpretation

- `final_candidate` means the row uses `nvml_total_energy` with `total_energy_mj_delta` and the expected `GetPowerUsage` semantics metadata for the profile. When `--require-explicit-measurement-scope` is used, the raw CSV must also contain `measurement_scope=gpu_device_total_energy_counter`; old rows that only allow inferred scope are rejected for final analysis.
- `provisional` means the row uses a fallback power integral. It should not be mixed into final pJ/FLOP or pJ/bit tables.
- `reject` means the row contradicts the expected power API matrix or lacks required metadata.
- This audit does not prove L1/L2/DRAM path correctness. NCU path acceptance is still required after this step.
- The measurement scope here is GPU/device telemetry from the raw harness CSV. Hopper module power and GPU memory power readings are preflight metadata only and must not be mixed into final component coefficients.
