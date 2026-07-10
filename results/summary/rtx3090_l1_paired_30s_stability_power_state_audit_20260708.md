# Power-State Stability Audit

This report flags raw energy rows whose average power or endpoint power metadata is inconsistent with peer rows of the same mode and configuration. It is a measurement-quality audit, not an NCU path acceptance report and not a component coefficient report.

- audit CSV: `results/summary/rtx3090_l1_paired_30s_stability_power_state_audit_20260708.csv`

## Status Counts

| status | rows |
|---|---:|
| `ok` | 18 |

## Interpretation

- `reject` rows should not be used as evidence for a stable coefficient until the run is repeated under stable clocks/power state.
- Endpoint power fields are metadata. Final energy numerator still comes from `nvml_total_energy` when the power API audit passes.
- If matched-control rows are negative but this audit has no reject row, the likely issue is weak treatment-control signal rather than an obvious power-state anomaly.
