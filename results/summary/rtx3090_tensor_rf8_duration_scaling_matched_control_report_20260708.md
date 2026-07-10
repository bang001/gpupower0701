# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 4 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | False |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| tensor_mma_increment | 15 | medium-high | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.0358693 | 0.143114 | 0.137531 | 0.209237 | 0.0405686 | 0.0371321 | 0.28347 | 0.115328 - 0.159923 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 75.6603 | 0.0565241 | 7.78034e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0972455 | pJ/FLOP |  | 1.07357 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 114.121 | 0.0829021 | 7.97412e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.143114 | pJ/FLOP |  | 1.0103 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 28.3884 | 0.0214185 | 7.91439e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0358693 | pJ/FLOP |  | 1.02272 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 86.2251 | 0.0618692 | 8.10103e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.106437 | pJ/FLOP |  | 1.00964 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 136.175 | 0.100392 | 7.71353e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.176541 | pJ/FLOP |  | 1.03976 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 176.769 | 0.0527338 | 1.53274e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.115328 | pJ/FLOP |  | 1.04709 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 238.318 | 0.068602 | 1.58252e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.150594 | pJ/FLOP |  | 1.00065 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 324.132 | 0.0946132 | 1.54911e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.209237 | pJ/FLOP |  | 1.06661 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 288.742 | 0.080522 | 1.62719e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.177448 | pJ/FLOP |  | 1.00961 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 236.75 | 0.0678897 | 1.59027e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.148874 | pJ/FLOP |  | 1.02525 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 320.633 | 0.0570828 | 2.43764e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.131535 | pJ/FLOP |  | 1.13505 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 373.66 | 0.0690159 | 2.3365e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.159923 | pJ/FLOP |  | 1.03651 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 375.253 | 0.0662924 | 2.42294e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.154875 | pJ/FLOP |  | 1.01277 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 289.743 | 0.0535518 | 2.31413e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.125206 | pJ/FLOP |  | 1.06533 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 301.402 | 0.0563379 | 2.30528e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.130745 | pJ/FLOP |  | 1.0552 | True |  |

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
