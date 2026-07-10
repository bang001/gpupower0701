# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708.csv` |
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
| tensor_mma_increment | 15 | medium-high | 0 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/FLOP | 0.0122199 | 0.0766466 | 0.0764157 | 0.135713 | 0.0332835 | 0.0361638 | 0.434246 | 0.054059 - 0.0948017 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 53.1299 | 0.0403826 | 8.25429e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0643664 | pJ/FLOP |  | 1.12402 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 105.71 | 0.0772738 | 8.37337e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.126246 | pJ/FLOP |  | 1.0007 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 68.4178 | 0.053496 | 8.19691e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0834678 | pJ/FLOP |  | 1.00702 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 111.972 | 0.083615 | 8.25065e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.135713 | pJ/FLOP |  | 1.00782 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 30.9725 | 0.0241164 | 8.30649e+14 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0372871 | pJ/FLOP |  | 1.00286 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 20.1061 | 0.00600815 | 1.64536e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0122199 | pJ/FLOP |  | 1.1486 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 122.706 | 0.0368189 | 1.62832e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0753576 | pJ/FLOP |  | 1.00546 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 155.285 | 0.0457873 | 1.638e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0948017 | pJ/FLOP |  | 1.01161 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 125.392 | 0.036972 | 1.63598e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0766466 | pJ/FLOP |  | 1.00509 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 154.932 | 0.0462564 | 1.62827e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0951511 | pJ/FLOP |  | 1.0256 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 215.33 | 0.0401472 | 2.41562e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0891409 | pJ/FLOP |  | 1.09171 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 90.9461 | 0.016981 | 2.44625e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0371778 | pJ/FLOP |  | 1.01929 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 251.565 | 0.0453838 | 2.4899e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.101034 | pJ/FLOP |  | 1.02405 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 132.556 | 0.0246855 | 2.45206e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.054059 | pJ/FLOP |  | 1.01669 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 153.914 | 0.0286442 | 2.42132e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.0635661 | pJ/FLOP |  | 1.02307 | True |  |

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
