# RTX3090 Platform Package Gap Report

This report explains open rows from `audit_platform_result_package.py`.
It is not a replacement for the package audit; it is a debugging guide.

| item | value |
|---|---|
| package audit CSV | `results/summary/rtx3090_platform_result_package_audit_20260714.csv` |
| result manifest CSV | `results/summary/rtx3090_component_finalplan_20260714_result_manifest.csv` |
| expected power semantics | `one_sec_average` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| open gaps | `6` |

## Severity Counts

| severity | gaps |
|---|---:|
| `blocker` | 1 |
| `high` | 3 |
| `medium` | 2 |

## Next Actions

| stage | severity | status | issue | evidence | corrective action | next command |
|---|---|---|---|---|---|---|
| raw energy | `high` | `fail` | results/raw/rtx3090_component_finalplan_20260714_tensor.csv:2:E_after_not_greater_than_E_before;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:2:delta_E_J=0;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:2:net_E_J=-0.63645319901;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:5:E_after_not_greater_than_E_before;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:5:delta_E_J=0;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:5:net_E_J=-0.609683280415;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:6:E_after_not_greater_than_E_before;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:6:delta_E_J=0;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:6:net_E_J=-0.592907179191;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:9:E_after_not_greater_than_E_before;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:9:delta_E_J=0;results/raw/rtx3090_component_finalplan_20260714_tensor.csv:9:net_E_J=-0.646294565637 | `results/raw/rtx3090_component_finalplan_20260714_tensor.csv;results/raw/rtx3090_component_finalplan_20260714_shared.csv;results/raw/rtx3090_component_finalplan_20260714_l1.csv;results/raw/rtx3090_component_finalplan_20260714_l2.csv;results/raw/rtx3090_component_finalplan_20260714_dram.csv (raw energy CSVs)` | Rerun the energy sweep and keep rows only when `elapsed_s > 0`, `ITER > 0`, `E_after_mJ > E_before_mJ`, and `delta_E_J == (E_after_mJ - E_before_mJ) / 1000`. | `bash results/summary/rtx3090_component_finalplan_20260714_commands.sh` |
| power state | `medium` | `fail` | results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:2:reject;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:2:coefficient_ineligible;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:2:net_E_J=-0.63645319901;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:2:average_power_W=-72.0228279939;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:2:group_power_median_W=-88.9180516261;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:5:reject;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:5:coefficient_ineligible;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:5:net_E_J=-0.609683280415;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:5:average_power_W=-77.8830458145;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:5:group_power_median_W=-83.2761918672;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:6:reject;results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv:6:coefficient_ineligible | `results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv (power-state stability audit)` | Exclude rejected rows before pairing or rerun the unstable conditions with longer seconds/repeats. | `python3 scripts/audit_power_state_stability.py ...` |
| matched-control | `high` | `fail` | tensor_mma_increment:missing | `results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv (matched-control summary)` | Rerun `scripts/analyze_matched_control_energy.py` with `--require-ncu-denominator --require-total-energy --expected-power-semantics`. | `python3 scripts/analyze_matched_control_energy.py ... --require-ncu-denominator --require-total-energy` |
| component reliability | `medium` | `fail` | missing_accepted=tensor_mma_increment | `results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.csv (component reliability audit)` | Rerun targeted component conditions or keep weak/rejected components out of the strict summary. | `python3 scripts/audit_component_reliability.py ...` |
| strict summary | `blocker` | `missing` | missing | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.csv (strict component coefficient summary)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/build_strict_component_summary.py ...` |
| strict summary audit | `high` | `fail` | rows=1, failures=1, warnings=0, missing_checks=hard_plausibility_range,l2_greater_than_l1,l2_greater_than_shared,ncu_evidence_summary_fields,ncu_summary_coordinate_alignment,ncu_summary_counter_schema,shared_l1_same_order | `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.csv (strict component summary audit)` | Rerun the current `audit_strict_component_summary.py`; stale audits missing hierarchy/plausibility checks are invalid. | `python3 scripts/audit_strict_component_summary.py ... --fail-on-fail` |

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
