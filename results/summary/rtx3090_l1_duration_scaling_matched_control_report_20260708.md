# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_l1_duration_scaling_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 8 |
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
| global_l1_hit_path | 14 | medium-high | 14 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.72594 | 1.24887 | 1.31538 | 2.29495 | 0.423568 | 0.387219 | 0.33916 | 1.04253 - 1.4769 | 0.156109 | 0.0907425 - 0.286869 | 0.130316 - 0.184612 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 58.8731 | 0.0224737 | 8.10991e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.72594 | pJ/byte | 0.0907425 | 1.19247 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 188.869 | 0.0711674 | 8.22975e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.29495 | pJ/byte | 0.286869 | 1.00322 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 152.48 | 0.0573907 | 8.31085e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.83471 | pJ/byte | 0.229339 | 1.03811 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 86.3279 | 0.0329874 | 8.2806e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.04253 | pJ/byte | 0.130316 | 1.00464 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 113.076 | 0.0418763 | 8.42993e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.34136 | pJ/byte | 0.16767 | 1.04177 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 139.684 | 0.0237502 | 1.6123e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.866366 | pJ/byte | 0.108296 | 1.01014 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 244.587 | 0.0403239 | 1.65609e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.4769 | pJ/byte | 0.184612 | 1.00619 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 203.373 | 0.0326733 | 1.68532e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20674 | pJ/byte | 0.150842 | 1.01836 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 280.562 | 0.046681 | 1.62581e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.72567 | pJ/byte | 0.215709 | 1.00008 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 135.207 | 0.0229728 | 1.61312e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.83817 | pJ/byte | 0.104771 | 1.00311 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | -81.0784 | -0.00874174 | 2.50051e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.324247 | pJ/byte | -0.0405309 | 1.03967 | False | negative_coefficient |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 322.257 | 0.0337006 | 2.49616e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.29101 | pJ/byte | 0.161376 | 1.008 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 353.176 | 0.0365325 | 2.51294e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.40543 | pJ/byte | 0.175678 | 1.03203 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 305.478 | 0.0313904 | 2.5331e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.20595 | pJ/byte | 0.150744 | 1.05879 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 292.727 | 0.0303629 | 2.52429e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.15964 | pJ/byte | 0.144955 | 1.01904 | True |  |

## QA

- Detail rows: 15
- Invalid detail rows: 1
- negative_coefficient: 1

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
