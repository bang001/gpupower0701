# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_duration_scaling_20260708.csv` |
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
| shared_l1_scalar_path | 15 | medium-high | 15 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.26748 | 1.58614 | 1.92258 | 3.6851 | 0.69163 | 0.784468 | 0.436047 | 1.41456 - 2.30852 | 0.198267 | 0.158434 - 0.460637 | 0.175339 - 0.25971 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 133.775 | 0.0505675 | 6.43865e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.07768 | pJ/byte | 0.25971 | 1.14146 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 169.638 | 0.0649699 | 6.32793e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.68078 | pJ/byte | 0.335097 | 1.00364 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 84.389 | 0.0324854 | 6.37412e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.32393 | pJ/byte | 0.165491 | 1.0108 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 176.631 | 0.067119 | 6.38729e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.76534 | pJ/byte | 0.345668 | 1.01603 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 231.91 | 0.0881132 | 6.29317e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 3.6851 | pJ/byte | 0.460637 | 1.02327 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 204.559 | 0.0331772 | 1.28967e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.58614 | pJ/byte | 0.198267 | 1.13368 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 176.805 | 0.0296196 | 1.26045e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.40271 | pJ/byte | 0.175339 | 1.01059 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 289.497 | 0.0491259 | 1.25404e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.30852 | pJ/byte | 0.288566 | 1.01028 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 196.111 | 0.0328847 | 1.2663e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.54869 | pJ/byte | 0.193586 | 1.00111 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 253.6 | 0.042391 | 1.2636e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.00696 | pJ/byte | 0.25087 | 1.0063 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 243.826 | 0.0257711 | 1.91853e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.2709 | pJ/byte | 0.158863 | 1.09489 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 296.411 | 0.0315702 | 1.89987e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.56016 | pJ/byte | 0.19502 | 1.01197 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 271.933 | 0.0287192 | 1.92239e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.41456 | pJ/byte | 0.17682 | 1.00444 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 367.671 | 0.0391549 | 1.89551e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.9397 | pJ/byte | 0.242462 | 1.00551 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 237.605 | 0.0257627 | 1.87463e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.26748 | pJ/byte | 0.158434 | 1.01398 | True |  |

## QA

- Detail rows: 15
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
