# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_power_api_audit_20260708.csv` |
| NCU acceptance | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| matched summary | `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_matched_control_summary_20260708.csv` |
| matched detail | `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_matched_control_detail_20260708.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 1 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | measurement scope | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
| `tensor_mma_increment` | `accepted` | 0.129215538161 | pJ/FLOP | 6 | 0 | 10 | `gpu_device_total_energy_counter` | `medium` | - | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
