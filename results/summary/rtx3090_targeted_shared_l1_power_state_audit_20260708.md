# Power-State Stability Audit

This report flags raw energy rows whose average power or endpoint power metadata is inconsistent with peer rows of the same mode and configuration. It is a measurement-quality audit, not an NCU path acceptance report and not a component coefficient report.

- audit CSV: `results/summary/rtx3090_targeted_shared_l1_power_state_audit_20260708.csv`

## Status Counts

| status | rows |
|---|---:|
| `caution` | 1 |
| `ok` | 117 |
| `reject` | 2 |

## Reject Reasons

| reason | rows |
|---|---:|
| `avg_power_low_outlier` | 2 |

## Notes

| note | rows |
|---|---:|
| `endpoint_power_after_low` | 2 |
| `temperature_outlier` | 3 |

## Rejected Rows

| mode | W_SM (KiB) | B/SM | LR | avg power (W) | group median (W) | endpoint after ratio | temp (C) | reasons | notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `global_l1_load_only` | 16 | 16 | 16 | 244.341885899 | 266.864444082 | 0.596592368002 | 69 | avg_power_low_outlier | endpoint_power_after_low;temperature_outlier |
| `global_l1_load_only` | 16 | 16 | 16 | 246.098623121 | 266.864444082 | 0.602578938668 | 69 | avg_power_low_outlier | endpoint_power_after_low;temperature_outlier |

## Interpretation

- `reject` rows should not be used as evidence for a stable coefficient until the run is repeated under stable clocks/power state.
- Endpoint power fields are metadata. Final energy numerator still comes from `nvml_total_energy` when the power API audit passes.
- If matched-control rows are negative but this audit has no reject row, the likely issue is weak treatment-control signal rather than an obvious power-state anomaly.
