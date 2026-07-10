# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_finalplan_stability_power_api_audit_20260708.csv` |
| NCU acceptance | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| matched summary | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_summary_20260708.csv` |
| matched detail | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_detail_20260708.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 1 |
| `accepted_low_stability` | 1 |
| `accepted_sanity` | 1 |
| `accepted_with_caution` | 2 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|
| `dram_cg_stream_path` | `accepted_sanity` | 3.54069776975 | pJ/bit | 9 | 9 | 3 | `medium-high` | dram_sanity_path_not_physical_dram_energy | - |
| `global_l1_hit_path` | `accepted_with_caution` | 0.150450885901 | pJ/bit | 7 | 7 | 3 | `medium` | invalid_detail_rows:2 | - |
| `l2_hit_cg_path` | `accepted` | 1.1381074518 | pJ/bit | 9 | 9 | 3 | `medium` | - | - |
| `shared_l1_scalar_path` | `accepted_with_caution` | 0.151125742676 | pJ/bit | 6 | 6 | 3 | `medium` | invalid_detail_rows:3 | - |
| `tensor_mma_increment` | `accepted_low_stability` | 0.169744684821 | pJ/FLOP | 15 | 0 | 10 | `low` | low_stability | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
