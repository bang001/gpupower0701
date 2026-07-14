# Power API Measurement Audit

This report audits raw energy CSV rows against `docs/platforms/power_measurement_api_matrix_ko.md`. It checks whether the energy numerator is suitable for final component coefficients before NCU path acceptance and matched-control analysis.

- detail CSV: `results/summary/rtx3090_component_finalplan_20260714_rerun1_power_api_audit.csv`
- total rows: 430

## Status Counts

| value | rows |
|---|---:|
| `final_candidate` | 430 |

## Energy Source Counts

| value | rows |
|---|---:|
| `nvml_total_energy` | 430 |

## Integration Method Counts

| value | rows |
|---|---:|
| `total_energy_mj_delta` | 430 |

## Measurement Scope Counts

| value | rows |
|---|---:|
| `gpu_device_total_energy_counter` | 430 |

## Power Semantics Counts

| value | rows |
|---|---:|
| `one_sec_average` | 430 |

## File Counts

| file | final_candidate | provisional | reject |
|---|---:|---:|---:|
| `results/raw/rtx3090_component_finalplan_20260714_rerun1_dram.csv` | 60 | 0 | 0 |
| `results/raw/rtx3090_component_finalplan_20260714_rerun1_l1.csv` | 90 | 0 | 0 |
| `results/raw/rtx3090_component_finalplan_20260714_rerun1_l2.csv` | 60 | 0 | 0 |
| `results/raw/rtx3090_component_finalplan_20260714_rerun1_shared.csv` | 120 | 0 | 0 |
| `results/raw/rtx3090_component_finalplan_20260714_rerun1_tensor.csv` | 100 | 0 | 0 |

## Interpretation

- `final_candidate` means the row uses `nvml_total_energy` with `total_energy_mj_delta` and the expected `GetPowerUsage` semantics metadata for the profile. When `--require-explicit-measurement-scope` is used, the raw CSV must also contain `measurement_scope=gpu_device_total_energy_counter`; old rows that only allow inferred scope are rejected for final analysis.
- When `--require-exact-measurement-interval` is used, the raw row must contain positive timed-kernel start/end epoch fields consistent with `elapsed_s`. Legacy run-id timing inference is diagnostic only.
- `provisional` means the row uses a fallback power integral. It should not be mixed into final pJ/FLOP or pJ/bit tables.
- `reject` means the row contradicts the expected power API matrix or lacks required metadata.
- When `--require-mode-notes-marker MODE=MARKER` is supplied, rows for that mode must carry the exact implementation revision marker in the raw `notes` column. This rejects stale binaries even when their CSV schema is otherwise current.
- If every row is rejected with `missing_column:measurement_scope` or `raw_csv_schema_missing_measurement_scope_rebuild_harness`, the raw CSV was produced by an old benchmark binary or appended to an old schema. Pull the current source, rebuild the target-profile binary, move the stale raw CSVs aside, and rerun the energy sweep.
- This audit does not prove L1/L2/DRAM path correctness. NCU path acceptance is still required after this step.
- The measurement scope here is GPU/device telemetry from the raw harness CSV. Hopper module power and GPU memory power readings are preflight metadata only and must not be mixed into final component coefficients.
