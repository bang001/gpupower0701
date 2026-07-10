# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_targeted_rf8_rf16_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `` |
| min elapsed (s) | 10 |
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
| tensor_mma_increment | 12 | medium-high | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.0322302 | 0.106658 | 0.109685 | 0.174529 | 0.0410182 | 0.0446373 | 0.384578 | 0.0834535 - 0.133532 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 162.549 | 0.0471409 | 1.585e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.102554 | pJ/FLOP |  | 1.08416 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 146.249 | 0.0436316 | 1.54648e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0945691 | pJ/FLOP |  | 1.05424 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 282.334 | 0.0784995 | 1.61769e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.174529 | pJ/FLOP |  | 1.03063 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 266.819 | 0.0789134 | 1.54522e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.172674 | pJ/FLOP |  | 1.04413 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 202.733 | 0.0596424 | 1.5621e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.129782 | pJ/FLOP |  | 1.04391 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 217.626 | 0.062475 | 1.58526e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.137281 | pJ/FLOP |  | 1.02233 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 121.592 | 0.0364222 | 1.64601e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0738705 | pJ/FLOP |  | 1.02011 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 126.941 | 0.0369446 | 1.66325e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0763211 | pJ/FLOP |  | 1.01968 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 184.402 | 0.0533062 | 1.66486e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.110761 | pJ/FLOP |  | 1.04023 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 52.7976 | 0.0159068 | 1.63814e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0322302 | pJ/FLOP |  | 1.006 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 148.617 | 0.0440325 | 1.64062e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0905859 | pJ/FLOP |  | 1.01147 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 197.091 | 0.0581604 | 1.6281e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.121056 | pJ/FLOP |  | 1.02085 | True |  |

## QA

- Detail rows: 12
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
