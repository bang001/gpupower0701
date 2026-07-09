# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_strict_scope_fresh_ncu_combined_power_api_audit_20260708.csv` |
| NCU acceptance | `results/summary/rtx3090_strict_scope_fresh_ncu_combined_acceptance_20260708.csv` |
| matched summary | `results/summary/rtx3090_strict_scope_fresh_ncu_combined_matched_control_summary_20260708.csv` |
| matched detail | `results/summary/rtx3090_strict_scope_fresh_ncu_combined_matched_control_detail_20260708.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 4 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | measurement scope | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
| `tensor_mma_increment` | `accepted` | 0.129215538161 | pJ/FLOP | 6 | 0 | 8 | `gpu_device_total_energy_counter` | `medium` | - | - |
| `global_l1_hit_path` | `accepted` | 0.17348298164 | pJ/bit | 6 | 6 | 3 | `gpu_device_total_energy_counter` | `medium` | - | - |
| `l2_hit_cg_path` | `accepted` | 1.13107277508 | pJ/bit | 6 | 6 | 3 | `gpu_device_total_energy_counter` | `medium` | - | - |
| `shared_l1_scalar_path` | `accepted` | 0.170589502631 | pJ/bit | 6 | 6 | 3 | `gpu_device_total_energy_counter` | `medium` | - | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
