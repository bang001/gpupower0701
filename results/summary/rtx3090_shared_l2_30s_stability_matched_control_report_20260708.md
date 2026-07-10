# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_l2_30s_stability_20260708.csv` |
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
| l2_hit_cg_path | 9 | medium-high | 9 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 8.91591 | 10.3811 | 10.008 | 11.3415 | 0.853635 | 1.32047 | 0.0822296 | 8.98263 - 10.7078 | 1.29764 | 1.11449 - 1.41769 | 1.12283 - 1.33847 |
| shared_l1_scalar_path | 9 | medium-high | 9 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.23671 | 1.72975 | 1.68533 | 2.06587 | 0.235893 | 0.241435 | 0.136374 | 1.51665 - 1.87627 | 0.216218 | 0.154589 - 0.258234 | 0.189582 - 0.234534 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 676.977 | 0.0677838 | 7.59291e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.91591 | pJ/byte | 1.11449 | 1.11281 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 803.415 | 0.0820277 | 7.50309e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.7078 | pJ/byte | 1.33847 | 1.00344 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 860.859 | 0.0868559 | 7.59032e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 11.3415 | pJ/byte | 1.41769 | 1.02007 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 687.268 | 0.0705881 | 7.54388e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.11027 | pJ/byte | 1.13878 | 1.00006 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 755.504 | 0.0762047 | 7.70597e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.80415 | pJ/byte | 1.22552 | 1.0191 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 780.995 | 0.0796429 | 7.52323e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.3811 | pJ/byte | 1.29764 | 1.0035 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 793.528 | 0.0810635 | 7.60759e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.4307 | pJ/byte | 1.30384 | 1.00025 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | -50.0148 | -0.00539639 | 7.67154e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.651952 | pJ/byte | -0.081494 | 1.02412 | False | negative_coefficient |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 804.317 | 0.0801802 | 7.73528e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 10.398 | pJ/byte | 1.29975 | 1.02761 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 674.226 | 0.0692229 | 7.50589e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.98263 | pJ/byte | 1.12283 | 1.00355 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 238.427 | 0.0250725 | 1.92791e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.23671 | pJ/byte | 0.154589 | 1.10812 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 10.5711 | 0.00119388 | 1.86477e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0566884 | pJ/byte | 0.00708605 | 1.02014 | False | delta_fraction<0.005 |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 327.737 | 0.0349438 | 1.89144e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.73274 | pJ/byte | 0.216592 | 1.0003 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 286.803 | 0.0311747 | 1.85649e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.54487 | pJ/byte | 0.193109 | 1.01519 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 337.549 | 0.0362036 | 1.88965e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.78631 | pJ/byte | 0.223288 | 1.0001 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 357.854 | 0.0380476 | 1.90726e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.87627 | pJ/byte | 0.234534 | 1.00605 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 325.581 | 0.0351577 | 1.88224e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.72975 | pJ/byte | 0.216218 | 1.00651 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 290.536 | 0.0307876 | 1.91563e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.51665 | pJ/byte | 0.189582 | 1.01064 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 315.683 | 0.0340304 | 1.88044e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.67877 | pJ/byte | 0.209847 | 1.0153 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 388.406 | 0.0416887 | 1.88011e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.06587 | pJ/byte | 0.258234 | 1.01898 | True |  |

## QA

- Detail rows: 20
- Invalid detail rows: 2
- delta_fraction<0.005: 1
- negative_coefficient: 1

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
