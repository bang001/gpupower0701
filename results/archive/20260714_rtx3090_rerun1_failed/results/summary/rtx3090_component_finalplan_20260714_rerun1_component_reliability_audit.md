# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_component_finalplan_20260714_rerun1_power_api_audit.csv` |
| NCU acceptance | `results/summary/rtx3090_component_finalplan_20260714_rerun1_ncu_acceptance.csv` |
| matched summary | `results/summary/rtx3090_component_finalplan_20260714_rerun1_matched_control_summary.csv` |
| matched detail | `results/summary/rtx3090_component_finalplan_20260714_rerun1_matched_control_detail.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 2 |
| `accepted_low_stability` | 1 |
| `accepted_sanity` | 1 |
| `accepted_with_caution` | 1 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | measurement scope | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
| `dram_cg_stream_path` | `accepted_sanity` | 25.5169429738 | pJ/bit | 15 | 15 | 18 | `gpu_device_total_energy_counter` | `medium-high` | dram_sanity_path_not_physical_dram_energy | - |
| `global_l1_hit_path` | `accepted_low_stability` | 0.11280472766 | pJ/bit | 4 | 4 | 19 | `gpu_device_total_energy_counter` | `low` | low_stability;invalid_detail_rows:11;shared_l1_global_l1_far_apart | - |
| `l2_hit_cg_path` | `accepted` | 7.74945787957 | pJ/bit | 15 | 15 | 19 | `gpu_device_total_energy_counter` | `medium-high` | - | - |
| `shared_l1_scalar_path` | `accepted_with_caution` | 1.01047072961 | pJ/bit | 9 | 9 | 5 | `gpu_device_total_energy_counter` | `medium` | invalid_detail_rows:6;shared_l1_global_l1_far_apart | - |
| `tensor_mma_increment` | `accepted` | 1.64095668284 | pJ/FLOP | 25 | 0 | 10 | `gpu_device_total_energy_counter` | `medium-high` | - | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_sanity` is used for DRAM streaming sanity. It should not be described as physical DRAM device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
