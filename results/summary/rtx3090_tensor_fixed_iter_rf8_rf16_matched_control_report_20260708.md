# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_fixed_iter_rf8_rf16_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `` |
| min elapsed (s) | 3 |
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
| tensor_mma_increment | 10 | medium-high | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.010359 | 0.145635 | 0.146208 | 0.263018 | 0.073525 | 0.0472777 | 0.504858 | 0.108536 - 0.201568 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 103.655 | 0.0884311 | 6.87866e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.150691 | pJ/FLOP |  | 1.02675 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 180.921 | 0.147572 | 6.87866e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.263018 | pJ/FLOP |  | 1.00895 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 110.981 | 0.0939855 | 6.87866e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.161342 | pJ/FLOP |  | 1.011 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 108.507 | 0.0932053 | 6.87866e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.157744 | pJ/FLOP |  | 1.01356 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 173.528 | 0.142772 | 6.87866e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.25227 | pJ/FLOP |  | 1.0239 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 124.488 | 0.0556546 | 1.37573e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0904885 | pJ/FLOP |  | 1.00275 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 174.787 | 0.0754943 | 1.37573e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.127051 | pJ/FLOP |  | 1.00165 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 14.2511 | 0.00643847 | 1.37573e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.010359 | pJ/FLOP |  | 1.00925 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 149.316 | 0.0635137 | 1.37573e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.108536 | pJ/FLOP |  | 1.00759 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 193.399 | 0.0839916 | 1.37573e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.140579 | pJ/FLOP |  | 1.00399 | True |  |

## QA

- Detail rows: 10
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
