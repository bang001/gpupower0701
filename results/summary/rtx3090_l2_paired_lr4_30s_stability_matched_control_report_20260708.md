# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_l2_paired_lr4_30s_stability_power_state_audit_20260708.csv` |
| min elapsed (s) | 10 |
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
| l2_hit_cg_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 7.63183 | 8.21803 | 8.37334 | 9.20534 | 0.567009 | 0.596527 | 0.0689957 | 7.86848 - 9.0335 | 1.02725 | 0.953978 - 1.15067 | 0.98356 - 1.12919 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 687.715 | 0.0695767 | 7.47083e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 9.20534 | pJ/byte | 1.15067 | 1.02738 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 653.835 | 0.0688747 | 7.37825e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.86166 | pJ/byte | 1.10771 | 1.01462 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 620.791 | 0.0641083 | 7.50084e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.27629 | pJ/byte | 1.03454 | 1.00432 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 565.799 | 0.0592213 | 7.41368e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 7.63183 | pJ/byte | 0.953978 | 1.00695 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 607.348 | 0.0633232 | 7.44319e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.15977 | pJ/byte | 1.01997 | 1.01018 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 618.465 | 0.0635876 | 7.63053e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 8.10513 | pJ/byte | 1.01314 | 1.01343 | True |  |

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
