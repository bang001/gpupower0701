# V100 Platform Result Package Audit

| item | value |
|---|---|
| target profile | `v100` |
| tag | `20260708` |
| expected chip | `gv100` |
| expected compute capability | `7.0` |
| expected L2 | `6 MiB` |
| expected unified L1/shared per SM | `128 KiB` |
| expected shared per SM | `96 KiB` |
| expected active SM | `80` |
| expected runtime SM count | `not exact-checked` |
| expected power semantics | `instant` |
| final numerator policy | `nvml_total_energy` + `total_energy_mj_delta` + `gpu_device_total_energy_counter` |

## Verdict

This package is not yet publishable as final component evidence. Fix missing/fail rows below, then rerun this audit and the goal readiness audit.

## Status Counts

| status | checks |
|---|---:|
| `missing` | 16 |
| `pass` | 2 |

## Checks

| area | check | status | expected | actual | evidence | action |
|---|---|---|---|---|---|---|
| `files` | `command_shell_present` | `pass` | file exists | exists | `results/summary/v100_component_finalplan_20260708_commands.sh` | run the generated command package or copy the artifact from the node |
| `files` | `command_plan_present` | `pass` | file exists | exists | `results/summary/v100_component_finalplan_20260708_command_plan.md` | run the generated command package or copy the artifact from the node |
| `files` | `preflight_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_preflight.md` | run the generated command package or copy the artifact from the node |
| `files` | `raw_present` | `missing` | all expected files exist | missing=results/raw/v100_component_finalplan_20260708_tensor.csv;results/raw/v100_component_finalplan_20260708_shared.csv;results/raw/v100_component_finalplan_20260708_l1.csv;results/raw/v100_component_finalplan_20260708_l2.csv;results/raw/v100_component_finalplan_20260708_dram.csv | `results/raw/v100_component_finalplan_20260708_tensor.csv;results/raw/v100_component_finalplan_20260708_shared.csv;results/raw/v100_component_finalplan_20260708_l1.csv;results/raw/v100_component_finalplan_20260708_l2.csv;results/raw/v100_component_finalplan_20260708_dram.csv` | copy the missing platform result files back from the target node |
| `files` | `tensor_pair_calibration_present` | `missing` | file exists | missing | `results/raw/v100_component_finalplan_20260708_tensor_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `l2_pair_calibration_present` | `missing` | file exists | missing | `results/raw/v100_component_finalplan_20260708_l2_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `dram_pair_calibration_present` | `missing` | file exists | missing | `results/raw/v100_component_finalplan_20260708_dram_pair_calibration.csv` | run the generated command package or copy the artifact from the node |
| `files` | `power_api_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_power_api_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `power_state_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_power_state_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `ncu_summary_present` | `missing` | file exists | missing | `results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv` | run the generated command package or copy the artifact from the node |
| `files` | `ncu_acceptance_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv` | run the generated command package or copy the artifact from the node |
| `files` | `matched_summary_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_matched_control_summary.csv` | run the generated command package or copy the artifact from the node |
| `files` | `matched_detail_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_matched_control_detail.csv` | run the generated command package or copy the artifact from the node |
| `files` | `reliability_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_component_reliability_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `instability_present` | `missing` | file exists | missing | `results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.csv` | run the generated command package or copy the artifact from the node |
| `files` | `strict_summary_present` | `missing` | file exists | missing | `results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.csv` | run the generated command package or copy the artifact from the node |
| `files` | `strict_audit_present` | `missing` | file exists | missing | `results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv` | run the generated command package or copy the artifact from the node |
| `raw` | `raw_energy_power_policy` | `missing` | raw rows use target profile metadata, target active SM, total-energy delta, GPU/device scope, explicit measurement_scope, profile power semantics, positive counter delta, elapsed time, and iteration count; Tensor rows carry the matched-add/scalar-epilogue revision and CG rows carry the ld.global.cg warm-up policy | no_raw_rows_read | `results/raw/v100_component_finalplan_20260708_tensor.csv;results/raw/v100_component_finalplan_20260708_shared.csv;results/raw/v100_component_finalplan_20260708_l1.csv;results/raw/v100_component_finalplan_20260708_l2.csv;results/raw/v100_component_finalplan_20260708_dram.csv` | copy raw energy CSVs from the target node |
