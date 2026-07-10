# RTX 3090 Component Evidence Matrix

이 문서는 current reporting coefficient가 어떤 증거를 통과했는지 한 표로 묶은 감사 기록이다. Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다.

| input | path |
|---|---|
| current reporting CSV | `results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv` |
| NCU acceptance CSV | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |

## Evidence Summary

| component | median | unit | evidence level | power final/prov/reject | scope | NCU accepted | NCU denom rows | reliability | risks |
|---|---:|---|---|---:|---|---:|---:|---|---|
| `tensor_mma_increment_duration_targeted` | 0.10665776832378673 | pJ/FLOP | `strong_candidate` | 24/0/0 | `gpu_device_total_energy_counter=24` | 10 | 0 | `accepted` | - |
| `tensor_mma_increment_fixed_iter_aux` | 0.14563510742808028 | pJ/FLOP | `auxiliary_support` | 20/0/0 | `gpu_device_total_energy_counter=20` | 10 | 0 | `accepted` | auxiliary_not_primary |
| `tensor_mma_increment_rf8_duration_scaling_aux` | 0.14311392977894904 | pJ/FLOP | `auxiliary_support` | 30/0/0 | `gpu_device_total_energy_counter=30` | 10 | 0 | `accepted` | power_state_caution_rows:1;auxiliary_not_primary |
| `tensor_mma_increment_rf16_duration_scaling_aux` | 0.07664658010202229 | pJ/FLOP | `auxiliary_support` | 30/0/0 | `gpu_device_total_energy_counter=30` | 10 | 0 | `accepted` | auxiliary_not_primary |
| `shared_l1_scalar_path` | 0.14873523687352952 | pJ/bit | `strong_candidate` | 30/0/0 | `gpu_device_total_energy_counter=30` | 3 | 10 | `accepted` | - |
| `shared_l1_scalar_path_lr4_paired_30s_aux` | 0.2363226800687383 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 6 | `accepted` | auxiliary_not_primary |
| `shared_l1_scalar_path_lr8_paired_30s_aux` | 0.17683780985788863 | pJ/bit | `auxiliary_support` | 36/0/0 | `gpu_device_total_energy_counter=36` | 3 | 12 | `accepted` | auxiliary_not_primary |
| `shared_l1_scalar_path_lr4_30s_aux` | 0.2162184841866812 | pJ/bit | `auxiliary_support` | 30/0/0 | `gpu_device_total_energy_counter=30` | 3 | 9 | `accepted_with_caution` | reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `shared_l1_scalar_path_lr16_paired_30s_aux` | 0.06354557112089149 | pJ/bit | `auxiliary_support` | 36/0/0 | `gpu_device_total_energy_counter=36` | 3 | 11 | `accepted_with_caution` | power_state_reject_rows:1;reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `shared_l1_scalar_path_lr16_paired_60s_aux` | 0.076818689336874 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 5 | `accepted_low_stability` | reliability_accepted_low_stability;reliability_cautions:few_valid_rows;low_stability;invalid_detail_rows:1;low_or_missing_confidence;auxiliary_not_primary |
| `shared_l1_scalar_path_interleaved_lr4_lr8_lr16_30s_aux` | 0.14506066279874935 | pJ/bit | `auxiliary_support` | 36/0/0 | `gpu_device_total_energy_counter=36` | 3 | 12 | `accepted` | auxiliary_not_primary |
| `shared_l1_scalar_path_fixediter_lr4_lr8_lr16_aux` | 0.14032742819189833 | pJ/bit | `auxiliary_support` | 27/0/0 | `gpu_device_total_energy_counter=27` | 3 | 8 | `accepted_with_caution` | power_state_caution_rows:9;reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `shared_l1_scalar_path_fixediter_lr16_focus_aux` | 0.11693932892462786 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 6 | `accepted` | auxiliary_not_primary |
| `shared_l1_scalar_path_targeted_mixed_lr_aux` | 0.15239545954836017 | pJ/bit | `auxiliary_support` | 120/0/0 | `gpu_device_total_energy_counter=120` | 3 | 29 | `accepted_with_caution` | power_state_caution_rows:1;reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `global_l1_hit_path` | 0.14847568285000448 | pJ/bit | `strong_candidate` | 36/0/0 | `gpu_device_total_energy_counter=36` | 3 | 12 | `accepted` | - |
| `global_l1_hit_path_duration_scaling_aux` | 0.1561091370146893 | pJ/bit | `auxiliary_support` | 30/0/0 | `gpu_device_total_energy_counter=30` | 3 | 14 | `accepted_with_caution` | reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `global_l1_hit_path_60s_aux` | 0.11914777440046519 | pJ/bit | `auxiliary_support` | 16/0/0 | `gpu_device_total_energy_counter=16` | 3 | 7 | `accepted` | power_state_reject_rows:1;auxiliary_not_primary |
| `global_l1_hit_path_lr8_paired_30s_aux` | 0.10904234486631326 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 6 | `accepted` | auxiliary_not_primary |
| `l2_hit_cg_path` | 1.016556433726509 | pJ/bit | `strong_candidate` | 36/0/0 | `gpu_device_total_energy_counter=36` | 3 | 12 | `accepted` | - |
| `l2_hit_cg_path_targeted_aux` | 0.9781974616407318 | pJ/bit | `auxiliary_support` | 60/0/0 | `gpu_device_total_energy_counter=60` | 3 | 30 | `accepted` | power_state_caution_rows:1;auxiliary_not_primary |
| `l2_hit_cg_path_lr4_paired_30s_aux` | 1.0272539734213253 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 6 | `accepted` | auxiliary_not_primary |
| `l2_hit_cg_path_lr8_paired_30s_aux` | 0.9596403819965263 | pJ/bit | `auxiliary_support` | 18/0/0 | `gpu_device_total_energy_counter=18` | 3 | 6 | `accepted` | auxiliary_not_primary |
| `l2_hit_cg_path_lr4_30s_aux` | 1.2976392121691205 | pJ/bit | `auxiliary_support` | 30/0/0 | `gpu_device_total_energy_counter=30` | 3 | 9 | `accepted_with_caution` | power_state_reject_rows:1;reliability_accepted_with_caution;reliability_cautions:invalid_detail_rows:1;auxiliary_not_primary |
| `dram_cg_stream_path` | 3.5406977697485584 | pJ/bit | `sanity_only` | 102/0/0 | `gpu_device_total_energy_counter=102` | 3 | 9 | `accepted_sanity` | power_state_caution_rows:45;reliability_cautions:dram_sanity_path_not_physical_dram_energy;dram_sanity_not_physical_device_energy |

## Interpretation

- `strong_candidate`: power API, NCU path, reliability, positivity, and confidence gates are all clean for the current artifact.
- `accepted_with_caution`: core gates pass, but invalid detail rows, medium confidence, or other cautions remain.
- `auxiliary_support`: useful to bound method sensitivity, but not a standalone primary coefficient.
- `sanity_only`: hierarchy sanity result. Do not report as physical DRAM/HBM device energy.

## Required Follow-up

| component | next action |
|---|---|
| `tensor_mma_increment_duration_targeted` | use_with_auxiliary_range_not_as_single_final |
| `tensor_mma_increment_fixed_iter_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `tensor_mma_increment_rf8_duration_scaling_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `tensor_mma_increment_rf16_duration_scaling_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path` | keep_as_current_primary_candidate |
| `shared_l1_scalar_path_lr4_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_lr8_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_lr4_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_lr16_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_lr16_paired_60s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_interleaved_lr4_lr8_lr16_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_fixediter_lr4_lr8_lr16_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_fixediter_lr16_focus_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `shared_l1_scalar_path_targeted_mixed_lr_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `global_l1_hit_path` | keep_as_current_primary_candidate |
| `global_l1_hit_path_duration_scaling_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `global_l1_hit_path_60s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `global_l1_hit_path_lr8_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `l2_hit_cg_path` | keep_as_current_primary_candidate |
| `l2_hit_cg_path_targeted_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `l2_hit_cg_path_lr4_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `l2_hit_cg_path_lr8_paired_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `l2_hit_cg_path_lr4_30s_aux` | use_to_bound_method_sensitivity_not_as_single_final |
| `dram_cg_stream_path` | report_only_as_hierarchy_sanity |

## Scope Notes

- All rows here must use GPU/device total energy counter scope for final reporting. Hopper module power and GPU memory power are preflight metadata only.
- For these historical 2026-07-08 RTX 3090 raw files, `measurement_scope` was inferred from `nvml_total_energy` + `total_energy_mj_delta`; most component rows predate the explicit CSV column. See `results/summary/rtx3090_current_explicit_scope_power_api_audit_20260708.md`. New finalplan runs must pass `--require-explicit-measurement-scope`.
- A100/V100/H100 are not validated by this RTX 3090 evidence matrix; they require platform-specific reruns with their own power API and NCU evidence.
