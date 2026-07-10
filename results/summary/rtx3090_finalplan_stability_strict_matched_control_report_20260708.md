# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_finalplan_stability_tensor_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_shared_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_l1_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_l2_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_dram_20260708_stability.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_20260705.csv, results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 1 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| dram_cg_stream_path | 9 | medium-high | 9 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 22.8652 | 28.3337 | 30.2919 | 42.8367 | 6.39658 | 7.91218 | 0.225759 | 23.7157 - 35.6348 | 3.54171 | 2.85814 - 5.35459 | 2.96446 - 4.45435 |
| global_l1_hit_path | 7 | medium | 7 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.218198 | 1.20361 | 1.09603 | 2.07724 | 0.691871 | 1.02629 | 0.574831 | 0.441139 - 1.70962 | 0.150451 | 0.0272747 - 0.259655 | 0.0551423 - 0.213702 |
| l2_hit_cg_path | 9 | medium | 9 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 4.35697 | 9.10711 | 8.93595 | 17.2208 | 4.01397 | 5.17657 | 0.440751 | 5.65304 - 11.3883 | 1.13839 | 0.544621 - 2.1526 | 0.70663 - 1.42353 |
| shared_l1_scalar_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.420415 | 1.209 | 1.45954 | 2.5277 | 0.816173 | 0.99475 | 0.675078 | 0.727675 - 2.44195 | 0.151126 | 0.0525519 - 0.315962 | 0.0909594 - 0.305244 |
| tensor_mma_increment | 15 | low | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.054161 | 0.169745 | 0.197452 | 0.359773 | 0.106696 | 0.17299 | 0.628567 | 0.120146 - 0.310835 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 260.898 | 0.126641 | 7.32144e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 35.6348 | pJ/byte | 4.45435 | 1.00735 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 247.44 | 0.118639 | 7.35234e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 33.6545 | pJ/byte | 4.20681 | 1.01624 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 228.334 | 0.11343 | 7.18518e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 31.7785 | pJ/byte | 3.97232 | 1.0464 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 8 | dram_cg_load_only_minus_clocked_empty | nearest-control | 318.277 | 0.149366 | 7.43e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 42.8367 | pJ/byte | 5.35459 | 1.00911 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 8 | dram_cg_load_only_minus_clocked_empty | nearest-control | 209.659 | 0.0997722 | 7.47042e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 28.0653 | pJ/byte | 3.50816 | 1.05114 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 8 | dram_cg_load_only_minus_clocked_empty | nearest-control | 203.948 | 0.0996743 | 7.19808e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 28.3337 | pJ/byte | 3.54171 | 1.0345 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | nearest-control | 183.445 | 0.0921707 | 7.12618e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 25.7423 | pJ/byte | 3.21779 | 1.05844 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | nearest-control | 176.056 | 0.08438 | 7.42359e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 23.7157 | pJ/byte | 2.96446 | 1.02645 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | nearest-control | 164.6 | 0.0817911 | 7.19871e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 22.8652 | pJ/byte | 2.85814 | 1.04384 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 78.2646 | 0.0408751 | 6.5025e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20361 | pJ/byte | 0.150451 | 1.01933 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 112.518 | 0.057497 | 6.58145e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.70962 | pJ/byte | 0.213702 | 1.01611 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 2.85899 | 0.00154598 | 6.48791e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0440665 | pJ/byte | 0.00550831 | 1.00525 | False | delta_E<10J;delta_fraction<0.005 |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 30.0908 | 0.0146781 | 6.82117e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.441139 | pJ/byte | 0.0551423 | 1.12911 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 41.3767 | 0.0221595 | 6.68278e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.619155 | pJ/byte | 0.0773944 | 1.01715 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 143.817 | 0.0732083 | 6.92343e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.07724 | pJ/byte | 0.259655 | 1.02971 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | -42.3328 | -0.0218603 | 7.09559e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.596607 | pJ/byte | -0.0745758 | 1.03827 | False | negative_coefficient |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 15.3229 | 0.008011 | 7.02248e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.218198 | pJ/byte | 0.0272747 | 1.00518 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 98.8137 | 0.0498379 | 7.04173e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.40326 | pJ/byte | 0.175407 | 1.02344 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 195.54 | 0.0959022 | 2.03938e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.5882 | pJ/byte | 1.19852 | 1.01359 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 222.472 | 0.107978 | 2.00127e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.1166 | pJ/byte | 1.38957 | 1.00602 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 342.046 | 0.168412 | 1.98624e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 17.2208 | pJ/byte | 2.1526 | 1.02423 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 86.6868 | 0.0429636 | 1.98961e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 4.35697 | pJ/byte | 0.544621 | 1.00576 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 186.111 | 0.0917771 | 2.04358e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.10711 | pJ/byte | 1.13839 | 1.00339 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 226.495 | 0.111948 | 1.98885e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.3883 | pJ/byte | 1.42353 | 1.00104 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 119.343 | 0.0588236 | 2.00914e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.93998 | pJ/byte | 0.742498 | 1.01671 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 115.475 | 0.0571783 | 2.04271e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.65304 | pJ/byte | 0.70663 | 1.02111 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 121.277 | 0.0605193 | 2.00369e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 6.05267 | pJ/byte | 0.756584 | 1.01197 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 61.2632 | 0.0320971 | 5.09927e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20141 | pJ/byte | 0.150176 | 1.01219 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 116.52 | 0.0639049 | 4.94525e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.35621 | pJ/byte | 0.294526 | 1.05145 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 52.2756 | 0.0279058 | 5.05109e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.03494 | pJ/byte | 0.129367 | 1.02974 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | -14.9673 | -0.00794293 | 5.2687e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.284079 | pJ/byte | -0.0355099 | 1.0294 | False | negative_coefficient |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 135.43 | 0.0672732 | 5.35783e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.5277 | pJ/byte | 0.315962 | 1.04071 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 64.6468 | 0.0336655 | 5.31374e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.2166 | pJ/byte | 0.152075 | 1.0081 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | -18.3725 | -0.00943837 | 5.50428e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.333785 | pJ/byte | -0.0417232 | 1.0286 | False | negative_coefficient |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 2.26807 | 0.00116504 | 5.45782e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0415564 | pJ/byte | 0.00519455 | 1.02092 | False | delta_E<10J;delta_fraction<0.005 |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 23.238 | 0.0115572 | 5.52738e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.420415 | pJ/byte | 0.0525519 | 1.00298 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 125.677 | 0.102531 | 5.57063e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.225606 | pJ/FLOP |  | 1.08863 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 190.569 | 0.149507 | 5.5121e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.345728 | pJ/FLOP |  | 1.06436 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 30.0216 | 0.0254139 | 5.54304e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.054161 | pJ/FLOP |  | 1.03872 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 32.6415 | 0.0360443 | 4.15888e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0784861 | pJ/FLOP |  | 1.00803 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 34.2253 | 0.0373333 | 4.18723e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0817373 | pJ/FLOP |  | 1.02896 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 150.466 | 0.153433 | 4.18746e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.359326 | pJ/FLOP |  | 1.02951 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 119.965 | 0.113099 | 6.43616e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.186392 | pJ/FLOP |  | 1.01676 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 201.791 | 0.173937 | 6.49189e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.310835 | pJ/FLOP |  | 1.02647 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 231.326 | 0.210861 | 6.42978e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.359773 | pJ/FLOP |  | 1.0037 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 62.1824 | 0.0690533 | 6.2422e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0996163 | pJ/FLOP |  | 1.03946 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 158.69 | 0.163839 | 6.22544e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.254906 | pJ/FLOP |  | 1.04362 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 105.387 | 0.113181 | 6.27579e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.167926 | pJ/FLOP |  | 1.01507 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 78.3712 | 0.0875799 | 6.523e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.120146 | pJ/FLOP |  | 1.01673 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 95.4679 | 0.106522 | 6.4766e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.147404 | pJ/FLOP |  | 1.0121 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 110.449 | 0.115996 | 6.50675e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.169745 | pJ/FLOP |  | 1.0049 | True |  |

## QA

- Detail rows: 51
- Invalid detail rows: 5
- delta_E<10J: 2
- delta_fraction<0.005: 2
- negative_coefficient: 3

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
