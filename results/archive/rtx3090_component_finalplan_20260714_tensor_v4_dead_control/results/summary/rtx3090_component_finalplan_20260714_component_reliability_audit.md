# Component Reliability Audit

This report combines the power API audit, NCU path acceptance, and matched-control coefficient summary. It is a reliability gate for effective microbenchmark coefficients, not a proof of pure silicon-level component energy.

| input | path |
|---|---|
| power API audit | `results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv` |
| NCU acceptance | `results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv` |
| matched summary | `results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv` |
| matched detail | `results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv` |

## Status Counts

| status | components |
|---|---:|
| `accepted` | 3 |
| `accepted_effective_path` | 1 |

## Component Verdicts

| component | status | median | unit | rows | NCU denominator rows | NCU accepted rows | measurement scope | confidence | cautions | reject reasons |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
| `external_memory_read_path` | `accepted_effective_path` | 24.9485633919 | pJ/bit | 45 | 45 | 27 | `gpu_device_total_energy_counter` | `medium-high` | effective_external_read_path_not_physical_memory_energy | - |
| `global_l1_hit_path` | `accepted` | 0.85247325547 | pJ/bit | 15 | 15 | 21 | `gpu_device_total_energy_counter` | `medium-high` | - | - |
| `l2_hit_cg_path` | `accepted` | 9.0784023317 | pJ/bit | 30 | 30 | 24 | `gpu_device_total_energy_counter` | `medium-high` | - | - |
| `shared_l1_scalar_path` | `accepted` | 0.713811591343 | pJ/bit | 15 | 15 | 6 | `gpu_device_total_energy_counter` | `medium-high` | - | - |

## Interpretation

- `accepted` means power, NCU path, denominator, positivity, and stability gates passed without extra cautions.
- `accepted_with_caution` means core gates passed but invalid rows, few rows, or hierarchy cautions remain.
- `accepted_low_stability` means the path is accepted but the coefficient distribution is still unstable. Report this separately.
- `accepted_effective_path` is used for the NCU-validated external memory read path. It includes GPU-device path overhead and must not be described as physical HBM/GDDR device energy.
- `reject` means at least one required gate failed and the component must be excluded from final coefficient tables.
