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
| pairing | `median-control` |
| min delta_E (J) | 0 |
| min delta fraction | 0 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| dram_cg_stream_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 28.5877 | 35.6348 | 33.6744 | 36.8006 | 4.44359 | 4.10646 | 0.124698 | 28.5877 - 36.8006 | 4.45435 | 3.57346 - 4.60008 | 3.57346 - 4.60008 |
| global_l1_hit_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.0226303 | 1.00425 | 1.1727 | 2.49123 | 1.24289 | 1.2343 | 1.23763 | 0.0226303 - 2.49123 | 0.125531 | 0.00282878 - 0.311404 | 0.00282878 - 0.311404 |
| l2_hit_cg_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 5.71996 | 9.69605 | 8.72249 | 10.7515 | 2.65327 | 2.51575 | 0.273645 | 5.71996 - 10.7515 | 1.21201 | 0.714995 - 1.34393 | 0.714995 - 1.34393 |
| shared_l1_scalar_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.0415564 | 1.20073 | 0.946444 | 1.59704 | 0.80832 | 0.777744 | 0.673191 | 0.0415564 - 1.59704 | 0.150091 | 0.00519455 - 0.199631 | 0.00519455 - 0.199631 |
| tensor_mma_increment | 5 | low | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.0817373 | 0.184052 | 0.181152 | 0.25768 | 0.0703112 | 0.0874827 | 0.382018 | 0.0817373 - 0.25768 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | median-control | 260.898 | 0.126641 | 7.32144e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 35.6348 | pJ/byte | 4.45435 | 1.00735 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 8 | dram_cg_load_only_minus_clocked_empty | median-control | 274.916 | 0.130826 | 7.47042e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 36.8006 | pJ/byte | 4.60008 | 1.00144 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | median-control | 205.795 | 0.102261 | 7.19871e+12 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 28.5877 | pJ/byte | 3.57346 | 1.05854 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | median-control | 65.3014 | 0.0341049 | 6.5025e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.00425 | pJ/byte | 0.125531 | 1.00687 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | median-control | 172.479 | 0.0877984 | 6.92343e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.49123 | pJ/byte | 0.311404 | 1.00169 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | median-control | 1.58921 | 0.000830855 | 7.02248e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0226303 | pJ/byte | 0.00282878 | 1.02467 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | median-control | 197.74 | 0.096981 | 2.03938e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.69605 | pJ/byte | 1.21201 | 1.00784 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | median-control | 213.83 | 0.105688 | 1.98885e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.7515 | pJ/byte | 1.34393 | 1.02134 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | median-control | 116.842 | 0.0578552 | 2.04271e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.71996 | pJ/byte | 0.714995 | 1.00102 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | median-control | 60.65 | 0.0323762 | 5.05109e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20073 | pJ/byte | 0.150091 | 1.00786 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | median-control | 84.8628 | 0.0441931 | 5.31374e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.59704 | pJ/byte | 0.199631 | 1.00686 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | median-control | 2.26807 | 0.00116504 | 5.45782e+13 | ncu_actual_same_working_set | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0415564 | pJ/byte | 0.00519455 | 1.02092 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | median-control | 130.847 | 0.106749 | 5.57063e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.234887 | pJ/FLOP |  | 1.05385 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | median-control | 34.2253 | 0.0373333 | 4.18723e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0817373 | pJ/FLOP |  | 1.02896 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | median-control | 165.683 | 0.151025 | 6.42978e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.25768 | pJ/FLOP |  | 1.00663 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | median-control | 115.507 | 0.12405 | 6.27579e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.184052 | pJ/FLOP |  | 1.03626 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | median-control | 95.4679 | 0.106522 | 6.4766e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.147404 | pJ/FLOP |  | 1.0121 | True |  |

## QA

- Detail rows: 17
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
