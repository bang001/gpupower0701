# Power API Measurement Audit

This report audits raw energy CSV rows against `docs/platforms/power_measurement_api_matrix_ko.md`. It checks whether the energy numerator is suitable for final component coefficients before NCU path acceptance and matched-control analysis.

- detail CSV: `results/summary/rtx3090_tensor_targeted_rf8_rf16_power_api_audit_20260708.csv`
- total rows: 24

## Status Counts

| value | rows |
|---|---:|
| `final_candidate` | 24 |

## Energy Source Counts

| value | rows |
|---|---:|
| `nvml_total_energy` | 24 |

## Integration Method Counts

| value | rows |
|---|---:|
| `total_energy_mj_delta` | 24 |

## Measurement Scope Counts

| value | rows |
|---|---:|
| `gpu_device_total_energy_counter` | 24 |

## Power Semantics Counts

| value | rows |
|---|---:|
| `one_sec_average` | 24 |

## File Counts

| file | final_candidate | provisional | reject |
|---|---:|---:|---:|
| `results/raw/rtx3090_tensor_targeted_rf8_rf16_20260708.csv` | 24 | 0 | 0 |

## Interpretation

- `final_candidate` means the row uses `nvml_total_energy` with `total_energy_mj_delta` and the expected `GetPowerUsage` semantics metadata for the profile.
- `provisional` means the row uses a fallback power integral. It should not be mixed into final pJ/FLOP or pJ/bit tables.
- `reject` means the row contradicts the expected power API matrix or lacks required metadata.
- This audit does not prove L1/L2/DRAM path correctness. NCU path acceptance is still required after this step.
- The measurement scope here is GPU/device telemetry from the raw harness CSV. Hopper module power and GPU memory power readings are preflight metadata only and must not be mixed into final component coefficients.
