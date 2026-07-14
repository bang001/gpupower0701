# Platform Component Result Intake Dashboard

This dashboard summarizes package audits and gap reports. It does not replace package audits, strict summary audits, or the goal readiness audit.

| item | value |
|---|---|
| tag | `20260714_rerun1` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| profiles passing package + strict summary | `0/4` |
| goal readiness audit | `results/summary/component_energy_goal_readiness_audit_20260714_rerun1.csv` |
| goal readiness status | `fail` (pass=33, missing=6, fail=4, warning=0) |

## Platform Status

| profile | power semantics | package status | package pass/missing/fail | gap blockers | first open stage | strict summary | accepted components |
|---|---|---|---:|---:|---|---|---:|
| `rtx3090` | `one_sec_average` | `fail` | 26/1/3 | 1 | strict summary | `missing_summary` | 0 |
| `v100` | `instant` | `missing_audit` | 0/0/0 | 0 | - | `missing_summary` | 0 |
| `a100` | `instant` | `missing_audit` | 0/0/0 | 0 | - | `missing_summary` | 0 |
| `h100` | `one_sec_average` | `missing_audit` | 0/0/0 | 0 | - | `missing_summary` | 0 |

## First Corrective Actions

| profile | first issue | corrective action | next command | gap report |
|---|---|---|---|---|
| `rtx3090` | missing | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/build_strict_component_summary.py ...` | `results/summary/rtx3090_platform_result_package_gaps_20260714_rerun1.csv` |
| `v100` | none | none | `none` | `results/summary/v100_platform_result_package_gaps_20260714_rerun1.csv` |
| `a100` | none | none | `none` | `results/summary/a100_platform_result_package_gaps_20260714_rerun1.csv` |
| `h100` | none | none | `none` | `results/summary/h100_platform_result_package_gaps_20260714_rerun1.csv` |

## Interpretation

A platform is not final merely because the command package exists. External platforms need a clean package audit, a strict component summary, and a strict summary audit. RTX 3090 evidence without a current package audit is shown as `historical_local_evidence`/`historical_pass`; it is context only and never counts as a current completed platform. Power-related rows must satisfy the power measurement matrix policy: `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` plus the profile-specific `nvml_power_usage_semantics`.
