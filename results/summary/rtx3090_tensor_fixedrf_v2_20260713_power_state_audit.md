# Power-State Stability Audit

This report flags raw energy rows whose average power or endpoint power metadata is inconsistent with peer rows of the same mode and configuration. It is a measurement-quality audit, not an NCU path acceptance report and not a component coefficient report.

- audit CSV: `results/summary/rtx3090_tensor_fixedrf_v2_20260713_power_state_audit.csv`

## Status Counts

| status | rows |
|---|---:|
| `caution` | 1 |
| `ok` | 67 |
| `reject` | 2 |

## Reject Reasons

| reason | rows |
|---|---:|
| `avg_power_high_outlier` | 1 |
| `avg_power_low_outlier` | 1 |

## Notes

| note | rows |
|---|---:|
| `temperature_outlier` | 1 |

## Rejected Rows

| mode | W_SM (KiB) | B/SM | LR | avg power (W) | group median (W) | endpoint after ratio | temp (C) | reasons | notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `reg_operand_only` | 2048 | 16 | 1 | 198.710030255 | 214.195041806 | 1.0020149012 | 70 | avg_power_low_outlier | - |
| `reg_operand_only` | 2048 | 16 | 1 | 233.046804823 | 220.876756019 | 1.00157450015 | 71 | avg_power_high_outlier | - |

## Interpretation

- `reject` rows should not be used as evidence for a stable coefficient until the run is repeated under stable clocks/power state.
- Endpoint power fields are metadata. Final energy numerator still comes from `nvml_total_energy` when the power API audit passes.
- If matched-control rows are negative but this audit has no reject row, the likely issue is weak treatment-control signal rather than an obvious power-state anomaly.
