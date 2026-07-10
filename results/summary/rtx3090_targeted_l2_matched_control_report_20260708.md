# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_targeted_l2_stability_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 4 |
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
| l2_hit_cg_path | 30 | medium-high | 30 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 3.29994 | 7.82558 | 8.06544 | 11.9947 | 2.12427 | 2.42241 | 0.271452 | 7.47892 - 9.11526 | 0.978197 | 0.412492 - 1.49933 | 0.934865 - 1.13941 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 510.043 | 0.0805518 | 5.04057e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.1188 | pJ/byte | 1.26484 | 1.11986 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 514.903 | 0.082454 | 4.95488e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.3918 | pJ/byte | 1.29898 | 1.00651 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 599.433 | 0.0961159 | 4.9975e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.9947 | pJ/byte | 1.49933 | 1.02554 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 395.191 | 0.0641436 | 4.98806e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.92273 | pJ/byte | 0.990341 | 1.00113 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 576.125 | 0.0920049 | 5.03181e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.4496 | pJ/byte | 1.43121 | 1.00974 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 514.847 | 0.0825488 | 4.97878e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.3408 | pJ/byte | 1.2926 | 1.00967 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 455.664 | 0.0748336 | 4.92878e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.24496 | pJ/byte | 1.15562 | 1.00495 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 448.541 | 0.0744338 | 4.88808e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.17623 | pJ/byte | 1.14703 | 1.02322 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 568.883 | 0.0913538 | 5.01615e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.341 | pJ/byte | 1.41763 | 1.00491 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 459.194 | 0.0739248 | 4.98007e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.22064 | pJ/byte | 1.15258 | 1.02309 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 460.567 | 0.0721117 | 5.08672e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.05429 | pJ/byte | 1.13179 | 1.01575 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 388.16 | 0.0626948 | 5.03011e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.71672 | pJ/byte | 0.96459 | 1.00632 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 466.429 | 0.0747333 | 4.97321e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.37884 | pJ/byte | 1.17235 | 1.01013 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 375.734 | 0.0615006 | 4.86172e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.72843 | pJ/byte | 0.966053 | 1.00631 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 437.142 | 0.07049 | 4.93378e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.86018 | pJ/byte | 1.10752 | 1.00078 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 350.012 | 0.0577434 | 4.94178e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.08271 | pJ/byte | 0.885339 | 1.0002 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 373.291 | 0.0617281 | 4.93311e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.56705 | pJ/byte | 0.945881 | 1.00262 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 374.849 | 0.0596149 | 5.01641e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.47245 | pJ/byte | 0.934056 | 1.01955 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 321.6 | 0.0511248 | 5.11354e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 6.28919 | pJ/byte | 0.786149 | 1.01455 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 437.285 | 0.0713325 | 4.93439e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.86199 | pJ/byte | 1.10775 | 1.01442 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 431.789 | 0.0680664 | 5.02327e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.59577 | pJ/byte | 1.07447 | 1.00418 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 320.215 | 0.0506748 | 5.04124e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 6.35191 | pJ/byte | 0.793989 | 1.03835 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 309.936 | 0.0503488 | 5.03117e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 6.16031 | pJ/byte | 0.770039 | 1.0035 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 163.042 | 0.0271402 | 4.94076e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 3.29994 | pJ/byte | 0.412492 | 1.01633 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 388.873 | 0.0611558 | 5.11263e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.60612 | pJ/byte | 0.950765 | 1.01513 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 377.198 | 0.0598983 | 5.03912e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.48539 | pJ/byte | 0.935673 | 1.02582 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 173.63 | 0.0287423 | 4.87077e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 3.56473 | pJ/byte | 0.445592 | 1.00933 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 274.448 | 0.0444979 | 4.97451e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.51709 | pJ/byte | 0.689637 | 1.01469 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 274.623 | 0.0442678 | 5.04719e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 5.44111 | pJ/byte | 0.680139 | 1.00482 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | nearest-control | 330.299 | 0.0545643 | 4.90952e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 6.72772 | pJ/byte | 0.840964 | 1.01999 | True |  |

## QA

- Detail rows: 30
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
