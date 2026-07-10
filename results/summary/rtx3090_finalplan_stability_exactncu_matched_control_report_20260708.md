# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_finalplan_stability_tensor_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_shared_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_l1_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_l2_20260708_stability.csv, results/raw/rtx3090_finalplan_stability_dram_20260708_stability.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 7 |
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
| dram_cg_stream_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 31.7785 | 33.6545 | 33.6893 | 35.6348 | 1.92838 | 1.92814 | 0.0572992 | 31.7785 - 35.6348 | 4.20681 | 3.97232 - 4.45435 | 3.97232 - 4.45435 |
| global_l1_hit_path | 2 | low | 2 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.20361 | 1.45661 | 1.45661 | 1.70962 | 0.357803 | 0.253005 | 0.24564 | 1.20361 - 1.70962 | 0.182076 | 0.150451 - 0.213702 | 0.150451 - 0.213702 |
| l2_hit_cg_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 9.5882 | 11.1166 | 12.6418 | 17.2208 | 4.03843 | 3.81629 | 0.363281 | 9.5882 - 17.2208 | 1.38957 | 1.19852 - 2.1526 | 1.19852 - 2.1526 |
| shared_l1_scalar_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.03494 | 1.20141 | 1.53085 | 2.35621 | 0.719609 | 0.660636 | 0.59897 | 1.03494 - 2.35621 | 0.150176 | 0.129367 - 0.294526 | 0.129367 - 0.294526 |
| tensor_mma_increment | 3 | low | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.186392 | 0.310835 | 0.285667 | 0.359773 | 0.0893889 | 0.0866908 | 0.287577 | 0.186392 - 0.359773 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 260.898 | 0.126641 | 7.32144e+12 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 35.6348 | pJ/byte | 4.45435 | 1.00735 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 247.44 | 0.118639 | 7.35234e+12 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 33.6545 | pJ/byte | 4.20681 | 1.01624 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | nearest-control | 228.334 | 0.11343 | 7.18518e+12 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 31.7785 | pJ/byte | 3.97232 | 1.0464 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 78.2646 | 0.0408751 | 6.5025e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20361 | pJ/byte | 0.150451 | 1.01933 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 112.518 | 0.057497 | 6.58145e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.70962 | pJ/byte | 0.213702 | 1.01611 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 2.85899 | 0.00154598 | 6.48791e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0440665 | pJ/byte | 0.00550831 | 1.00525 | False | delta_E<10J;delta_fraction<0.005 |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 195.54 | 0.0959022 | 2.03938e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.5882 | pJ/byte | 1.19852 | 1.01359 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 222.472 | 0.107978 | 2.00127e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.1166 | pJ/byte | 1.38957 | 1.00602 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 342.046 | 0.168412 | 1.98624e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 17.2208 | pJ/byte | 2.1526 | 1.02423 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 61.2632 | 0.0320971 | 5.09927e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20141 | pJ/byte | 0.150176 | 1.01219 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 116.52 | 0.0639049 | 4.94525e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.35621 | pJ/byte | 0.294526 | 1.05145 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 52.2756 | 0.0279058 | 5.05109e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.03494 | pJ/byte | 0.129367 | 1.02974 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 119.965 | 0.113099 | 6.43616e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.186392 | pJ/FLOP |  | 1.01676 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 201.791 | 0.173937 | 6.49189e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.310835 | pJ/FLOP |  | 1.02647 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 231.326 | 0.210861 | 6.42978e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.359773 | pJ/FLOP |  | 1.0037 | True |  |

## QA

- Detail rows: 15
- Invalid detail rows: 1
- delta_E<10J: 1
- delta_fraction<0.005: 1

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
