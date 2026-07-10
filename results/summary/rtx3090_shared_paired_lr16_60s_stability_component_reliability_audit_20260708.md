# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_shared_paired_lr16_60s_stability_power_api_audit_20260708.csv` |
| NCU acceptance | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| matched summary | `results/summary/rtx3090_shared_paired_lr16_60s_stability_matched_control_summary_20260708.csv` |
| matched detail | `results/summary/rtx3090_shared_paired_lr16_60s_stability_matched_control_detail_20260708.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted_low_stability` | 1 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|
| `shared_l1_scalar_path` | `accepted_low_stability` | 0.0768186893369 | pJ/bit | 5 | 5 | 3 | `low` | few_valid_rows;low_stability;invalid_detail_rows:1 | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
