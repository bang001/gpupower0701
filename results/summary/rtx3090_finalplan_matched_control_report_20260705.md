# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_finalplan_tensor_energy_20260705.csv, results/raw/rtx3090_finalplan_shared_energy_20260705.csv, results/raw/rtx3090_finalplan_l1_energy_20260705.csv, results/raw/rtx3090_finalplan_l2_energy_20260705.csv, results/raw/rtx3090_finalplan_dram_energy_20260705.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_20260705.csv, results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 1 |
| max elapsed ratio | 1.35 |
| pairing | `median-control` |
| min delta_E (J) | 0 |
| min delta fraction | 0 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| dram_cg_stream_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 22.6027 | 32.0477 | 34.334 | 48.3517 | 13.0259 | 12.8745 | 0.406453 | 22.6027 - 48.3517 | 4.00596 | 2.82534 - 6.04397 | 2.82534 - 6.04397 |
| global_l1_hit_path | 5 | low | 5 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.631125 | 1.25145 | 2.15785 | 5.51777 | 1.96653 | 1.09359 | 1.5714 | 0.631125 - 5.51777 | 0.156431 | 0.0788907 - 0.689722 | 0.0788907 - 0.689722 |
| l2_hit_cg_path | 5 | low | 5 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 7.57453 | 9.40542 | 12.8701 | 24.5151 | 7.23409 | 7.68312 | 0.769141 | 7.57453 - 24.5151 | 1.17568 | 0.946817 - 3.06439 | 0.946817 - 3.06439 |
| shared_l1_scalar_path | 5 | low | 5 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.797892 | 2.16424 | 3.35809 | 7.35441 | 2.64552 | 2.83385 | 1.22238 | 0.797892 - 7.35441 | 0.27053 | 0.0997365 - 0.919301 | 0.0997365 - 0.919301 |
| tensor_mma_increment | 5 | low | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.0878299 | 0.16802 | 0.17386 | 0.295366 | 0.0757321 | 0.0246271 | 0.450732 | 0.0878299 - 0.295366 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | 1 | dram_cg_load_only_minus_clocked_empty | median-control | 227.927 | 0.181067 | 4.71394e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 48.3517 | pJ/byte | 6.04397 | 1.02237 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | median-control | 151.077 | 0.120931 | 4.71415e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 32.0477 | pJ/byte | 4.00596 | 1.00034 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | median-control | 106.626 | 0.0859281 | 4.71738e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 22.6027 | pJ/byte | 2.82534 | 1.0025 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 1 | global_l1_load_only_minus_clocked_empty | median-control | 84.0143 | 0.0730944 | 3.74857e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.24124 | pJ/byte | 0.280155 | 1.04739 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 2 | global_l1_load_only_minus_clocked_empty | median-control | 231.552 | 0.198777 | 4.19647e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.51777 | pJ/byte | 0.689722 | 1.02896 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | median-control | 54.5318 | 0.0465366 | 4.35749e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.25145 | pJ/byte | 0.156431 | 1.02479 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | median-control | 51.3984 | 0.0436657 | 4.47857e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.14765 | pJ/byte | 0.143456 | 1.01856 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | median-control | 28.6159 | 0.0246841 | 4.5341e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.631125 | pJ/byte | 0.0788907 | 1.01551 | True |  |
| global_l1_hit_path | 64 | 16 | 1 | 1 | global_l1_load_only_minus_clocked_empty | median-control | 40.9839 | 0.0376003 | 1.61643e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.53546 | pJ/byte | 0.316932 | 1.04498 | False | missing_ncu_denominator |
| global_l1_hit_path | 64 | 16 | 1 | 2 | global_l1_load_only_minus_clocked_empty | median-control | 151.805 | 0.139066 | 1.75381e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.65572 | pJ/byte | 1.08197 | 1.03347 | False | missing_ncu_denominator |
| global_l1_hit_path | 64 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | median-control | -16.279 | -0.014819 | 1.74877e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.930881 | pJ/byte | -0.11636 | 1.00889 | False | missing_ncu_denominator;negative_coefficient |
| global_l1_hit_path | 64 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | median-control | -57.9885 | -0.0508551 | 1.82227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | one_sec_average | -3.1822 | pJ/byte | -0.397775 | 1.03154 | False | missing_ncu_denominator;negative_coefficient |
| global_l1_hit_path | 64 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | median-control | -79.3804 | -0.0694949 | 1.82183e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | one_sec_average | -4.35718 | pJ/byte | -0.544647 | 1.00123 | False | missing_ncu_denominator;negative_coefficient |
| l2_hit_cg_path | 64 | 16 | 1 | 1 | l2_cg_load_only_minus_clocked_empty | median-control | 195.855 | 0.157347 | 1.28267e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 15.2693 | pJ/byte | 1.90867 | 1.04485 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 2 | l2_cg_load_only_minus_clocked_empty | median-control | 314.279 | 0.251666 | 1.28198e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 24.5151 | pJ/byte | 3.06439 | 1.02766 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | median-control | 121.46 | 0.0991288 | 1.29138e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.40542 | pJ/byte | 1.17568 | 1.01375 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | median-control | 97.7656 | 0.0800598 | 1.29071e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.57453 | pJ/byte | 0.946817 | 1.01627 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | median-control | 98.4488 | 0.0805718 | 1.29773e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.58623 | pJ/byte | 0.948278 | 1.0155 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 1 | shared_scalar_load_only_minus_clocked_empty | median-control | 134.948 | 0.114511 | 2.8997e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 4.65388 | pJ/byte | 0.581735 | 1.03952 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 2 | shared_scalar_load_only_minus_clocked_empty | median-control | 227.544 | 0.196477 | 3.09399e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.35441 | pJ/byte | 0.919301 | 1.02333 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | median-control | 59.7455 | 0.0522023 | 3.28267e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.82003 | pJ/byte | 0.227503 | 1.00377 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | median-control | 74.5686 | 0.0618902 | 3.44549e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.16424 | pJ/byte | 0.27053 | 1.0225 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | median-control | 28.2121 | 0.023808 | 3.53583e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.797892 | pJ/byte | 0.0997365 | 1.01396 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | median-control | 53.2879 | 0.0740676 | 3.63176e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.146727 | pJ/FLOP |  | 1.02995 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | median-control | 45.3693 | 0.0864916 | 2.70023e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.16802 | pJ/FLOP |  | 1.03925 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | median-control | 124.11 | 0.189035 | 4.2019e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.295366 | pJ/FLOP |  | 1.04086 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | median-control | 70.7121 | 0.126874 | 4.12666e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.171354 | pJ/FLOP |  | 1.0135 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | median-control | 37.469 | 0.0716282 | 4.26609e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0878299 | pJ/FLOP |  | 1.05405 | True |  |

## QA

- Detail rows: 28
- Invalid detail rows: 5
- missing_ncu_denominator: 5
- negative_coefficient: 3

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
