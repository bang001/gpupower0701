# RTX3090 Platform Package Gap Report

This report explains open rows from `audit_platform_result_package.py`.
It is not a replacement for the package audit; it is a debugging guide.

| item | value |
|---|---|
| package audit CSV | `results/summary/rtx3090_platform_result_package_audit_20260714_rerun1.csv` |
| result manifest CSV | `results/summary/rtx3090_component_finalplan_20260714_rerun1_result_manifest.csv` |
| expected power semantics | `one_sec_average` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| open gaps | `4` |

## Severity Counts

| severity | gaps |
|---|---:|
| `blocker` | 1 |
| `high` | 1 |
| `medium` | 2 |

## Next Actions

| stage | severity | status | issue | evidence | corrective action | next command |
|---|---|---|---|---|---|---|
| power state | `medium` | `fail` | results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:57:reject;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:57:coefficient_ineligible;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:145:reject;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:145:coefficient_ineligible;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:297:reject;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:297:coefficient_ineligible;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:403:reject;results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv:403:coefficient_ineligible | `results/summary/rtx3090_component_finalplan_20260714_rerun1_power_state_audit.csv (power-state stability audit)` | Exclude rejected rows before pairing or rerun the unstable conditions with longer seconds/repeats. | `python3 scripts/audit_power_state_stability.py ...` |
| component reliability | `medium` | `fail` | missing_accepted=global_l1_hit_path,shared_l1_scalar_path;shared_l1_scalar_path:status=accepted_with_caution;shared_l1_scalar_path:invalid_detail_rows=6;shared_l1_scalar_path:cautions=invalid_detail_rows:6;shared_l1_global_l1_far_apart;global_l1_hit_path:status=accepted_low_stability;global_l1_hit_path:invalid_detail_rows=11;global_l1_hit_path:cautions=low_stability;invalid_detail_rows:11;shared_l1_global_l1_far_apart | `results/summary/rtx3090_component_finalplan_20260714_rerun1_component_reliability_audit.csv (component reliability audit)` | Rerun targeted component conditions or keep weak/rejected components out of the strict summary. | `python3 scripts/audit_component_reliability.py ...` |
| strict summary | `blocker` | `missing` | missing | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714_rerun1.csv (strict component coefficient summary)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/build_strict_component_summary.py ...` |
| strict summary audit | `high` | `fail` | rows=1, failures=1, warnings=0, missing_checks=hard_plausibility_range,l2_greater_than_l1,l2_greater_than_shared,ncu_evidence_summary_fields,ncu_summary_coordinate_alignment,ncu_summary_counter_schema,shared_l1_same_order | `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714_rerun1.csv (strict component summary audit)` | Rerun the current `audit_strict_component_summary.py`; stale audits missing hierarchy/plausibility checks are invalid. | `python3 scripts/audit_strict_component_summary.py ... --fail-on-fail` |

## Power API Interpretation

A package can only produce final component coefficients when the energy rows satisfy the power measurement matrix policy: `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` and the profile-specific `nvml_power_usage_semantics=one_sec_average`. `GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power remain metadata or fallback/provisional evidence.

## Re-run Intake

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile rtx3090 \
  --tag <YYYYMMDD> \
  --expected-active-sm 82 \
  --out-csv results/summary/rtx3090_platform_result_package_audit_<YYYYMMDD>.csv \
  --out-md results/summary/rtx3090_platform_result_package_audit_<YYYYMMDD>.md \
  --fail-on-incomplete
```
