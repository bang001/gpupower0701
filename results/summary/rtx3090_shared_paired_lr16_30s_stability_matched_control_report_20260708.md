# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_shared_paired_lr16_30s_stability_power_state_audit_20260708.csv` |
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
| shared_l1_scalar_path | 5 | low | 5 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.262804 | 0.43195 | 0.467215 | 0.832476 | 0.226902 | 0.207885 | 0.525297 | 0.262804 - 0.832476 | 0.0539937 | 0.0328505 - 0.10406 | 0.0328505 - 0.10406 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 107.926 | 0.0109156 | 2.12301e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.508365 | pJ/byte | 0.0635456 | 1.05576 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 61.6399 | 0.00644584 | 2.05139e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.300479 | pJ/byte | 0.0375599 | 1.00594 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 170.839 | 0.0176051 | 2.05218e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.832476 | pJ/byte | 0.10406 | 1.01624 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 53.7611 | 0.00564663 | 2.04567e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.262804 | pJ/byte | 0.0328505 | 1.00452 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 89.1371 | 0.00930268 | 2.0636e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.43195 | pJ/byte | 0.0539937 | 1.02721 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 28.7207 | 0.0029217 | 2.11261e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.135949 | pJ/byte | 0.0169936 | 1.05267 | False | delta_fraction<0.005 |

## QA

- Detail rows: 6
- Invalid detail rows: 1
- delta_fraction<0.005: 1

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
