# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_paired_lr4_30s_stability_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_shared_paired_lr4_30s_stability_power_state_audit_20260708.csv` |
| min elapsed (s) | 24 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| shared_l1_scalar_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.66359 | 1.89058 | 1.98784 | 2.3761 | 0.324634 | 0.549339 | 0.171711 | 1.69878 - 2.37417 | 0.236323 | 0.207949 - 0.297013 | 0.212348 - 0.296771 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 454.935 | 0.0478841 | 1.91463e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.3761 | pJ/byte | 0.297013 | 1.03043 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 447.11 | 0.0476414 | 1.88477e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.37223 | pJ/byte | 0.296529 | 1.00324 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 328.947 | 0.0352159 | 1.89707e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.73397 | pJ/byte | 0.216746 | 1.00877 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 332.722 | 0.0355699 | 1.90203e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.7493 | pJ/byte | 0.218662 | 1.01188 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 389.432 | 0.0409422 | 1.91662e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.03187 | pJ/byte | 0.253983 | 1.01351 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 316.526 | 0.0338015 | 1.90267e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.66359 | pJ/byte | 0.207949 | 1.00926 | True |  |

## QA

- Detail rows: 6
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
