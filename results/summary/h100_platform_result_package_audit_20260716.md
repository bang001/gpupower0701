# H100 Platform Result Package Audit

| item | value |
|---|---|
| target profile | `h100` |
| tag | `20260716` |
| expected chip | `gh100` |
| expected compute capability | `9.0` |
| expected L2 | `50 MiB` |
| expected unified L1/shared per SM | `256 KiB` |
| expected shared per SM | `228 KiB` |
| expected active SM | `132` |
| expected runtime SM count | `not exact-checked` |
| expected power semantics | `one_sec_average` |
| final numerator policy | `nvml_total_energy` + `total_energy_mj_delta` + `gpu_device_total_energy_counter` |

## Verdict

This package is not yet publishable as final component evidence. Fix missing/fail rows below, then rerun this audit and the goal readiness audit.

## Status Counts

| status | checks |
|---|---:|
| `missing` | 17 |
| `pass` | 2 |

## Checks

| area | check | status | expected | actual | evidence | action |
|---|---|---|---|---|---|---|
| `files` | `command_shell_present` | `pass` | file exists | exists | `results/summary/h100_component_finalplan_20260716_commands.sh` | run the generated command package or copy the artifact from the node |
| `files` | `command_plan_present` | `pass` | file exists | exists | `results/summary/h100_component_finalplan_20260716_command_plan.md` | run the generated command package or copy the artifact from the node |
| `files` | `preflight_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_preflight.md` | run the generated command package or copy the artifact from the node |
| `files` | `raw_present` | `missing` | all expected files exist | missing=results/raw/h100_component_finalplan_20260716_tensor.csv;results/raw/h100_component_finalplan_20260716_shared.csv;results/raw/h100_component_finalplan_20260716_l1.csv;results/raw/h100_component_finalplan_20260716_l2.csv;results/raw/h100_component_finalplan_20260716_dram.csv | `results/raw/h100_component_finalplan_20260716_tensor.csv;results/raw/h100_component_finalplan_20260716_shared.csv;results/raw/h100_component_finalplan_20260716_l1.csv;results/raw/h100_component_finalplan_20260716_l2.csv;results/raw/h100_component_finalplan_20260716_dram.csv` | copy the missing platform result files back from the target node |
| `files` | `tensor_pair_calibration_present` | `missing` | file exists | missing | `results/raw/h100_component_finalplan_20260716_tensor_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `l2_pair_calibration_present` | `missing` | file exists | missing | `results/raw/h100_component_finalplan_20260716_l2_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `dram_pair_calibration_present` | `missing` | file exists | missing | `results/raw/h100_component_finalplan_20260716_dram_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `power_api_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_power_api_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `power_state_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_power_state_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `ncu_summary_present` | `missing` | file exists | missing | `results/ncu/h100_component_finalplan_ncu_factor_20260716/ncu_cache_validation_summary.csv` | run the generated command package or copy the artifact from the node |
| `files` | `ncu_acceptance_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_ncu_acceptance.csv` | run the generated command package or copy the artifact from the node |
| `files` | `matched_summary_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_matched_control_summary.csv` | run the generated command package or copy the artifact from the node |
| `files` | `matched_detail_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_matched_control_detail.csv` | run the generated command package or copy the artifact from the node |
| `files` | `reliability_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_component_reliability_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `instability_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_matched_control_instability_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `strict_summary_present` | `missing` | file exists | missing | `results/summary/h100_strict_scope_fresh_ncu_component_coefficients_20260716.csv` | run the generated command package or copy the artifact from the node |
| `files` | `strict_audit_present` | `missing` | file exists | missing | `results/summary/h100_strict_scope_fresh_ncu_component_summary_audit_20260716.csv` | run the generated command package or copy the artifact from the node |
| `files` | `l2_path_selection_present` | `missing` | file exists | missing | `results/summary/h100_component_finalplan_20260716_l2_path_selection.csv` | run the generated command package or copy the artifact from the node |
| `raw` | `raw_energy_power_policy` | `missing` | raw rows use target profile metadata, target active SM, total-energy delta, GPU/device scope, exact timed-kernel epoch interval, explicit measurement_scope, profile power semantics, positive counter delta, elapsed time, and iteration count; Tensor rows carry the runtime-observed fixed-RF v6 revision, register-only operand source, and non-cache reuse semantics, while CG rows carry the ld.global.cg warm-up policy | no_raw_rows_read | `results/raw/h100_component_finalplan_20260716_tensor.csv;results/raw/h100_component_finalplan_20260716_shared.csv;results/raw/h100_component_finalplan_20260716_l1.csv;results/raw/h100_component_finalplan_20260716_l2.csv;results/raw/h100_component_finalplan_20260716_dram.csv` | copy raw energy CSVs from the target node |
