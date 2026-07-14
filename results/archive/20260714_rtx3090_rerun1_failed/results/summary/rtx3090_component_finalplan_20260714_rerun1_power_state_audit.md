# Power-State Stability Audit

This report flags raw energy rows whose average power or endpoint power metadata is inconsistent with peer rows of the same mode and configuration. It is a measurement-quality audit, not an NCU path acceptance report and not a component coefficient report.

- audit CSV: `results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv`

## Status Counts

| status | rows |
|---|---:|
| `caution` | 3 |
| `ok` | 423 |
| `reject` | 4 |

## Reject Reasons

| reason | rows |
|---|---:|
| `avg_power_high_outlier` | 2 |
| `avg_power_low_outlier` | 2 |

## Notes

| note | rows |
|---|---:|
| `temperature_outlier` | 3 |

## Rejected Rows

| mode | W_SM (KiB) | B/SM | LR | avg power (W) | group median (W) | endpoint after ratio | temp (C) | reasons | notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `reg_operand_only` | 2048 | 16 | 1 | 128.850332718 | 114.514657031 | 1.00067826473 | 68 | avg_power_high_outlier | - |
| `clocked_empty` | 64 | 16 | 8 | 201.860824729 | 215.762986117 | 1.13326973314 | 76 | avg_power_low_outlier | - |
| `global_addr_only` | 16 | 8 | 16 | 216.95328089 | 229.267334666 | 0.788224048613 | 74 | avg_power_low_outlier | - |
| `global_addr_only` | 8192 | 16 | 16 | 214.286531971 | 203.344253743 | 1.00216474566 | 78 | avg_power_high_outlier | - |

## Interpretation

- `reject` rows should not be used as evidence for a stable coefficient until the run is repeated under stable clocks/power state.
- Endpoint power fields are metadata. Final energy numerator still comes from `nvml_total_energy` when the power API audit passes.
- If matched-control rows are negative but this audit has no reject row, the likely issue is weak treatment-control signal rather than an obvious power-state anomaly.
