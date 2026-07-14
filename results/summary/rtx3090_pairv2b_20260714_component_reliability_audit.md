# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_pairv2b_20260714_power_api_audit.csv` |
| NCU acceptance | `results/summary/rtx3090_pairv2b_20260714_ncu_acceptance.csv` |
| matched summary | `results/summary/rtx3090_pairv2b_20260714_matched_control_summary.csv` |
| matched detail | `results/summary/rtx3090_pairv2b_20260714_matched_control_detail.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 1 |
| `accepted_with_caution` | 1 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | measurement scope | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
| `global_l1_hit_path` | `accepted_with_caution` | 0.430304972983 | pJ/bit | 14 | 14 | 6 | `gpu_device_total_energy_counter` | `medium` | invalid_detail_rows:1 | - |
| `shared_l1_scalar_path` | `accepted` | 0.637283039735 | pJ/bit | 15 | 15 | 6 | `gpu_device_total_energy_counter` | `medium-high` | - | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
