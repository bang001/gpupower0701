# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_strict_scope_shared_lr4_lr8_focus_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_strict_scope_shared_lr4_lr8_focus_power_state_audit_20260708.csv` |
| min elapsed (s) | 12 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| shared_l1_scalar_path | 3 | low | 3 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 0.915802 | 0.955654 | 1.00615 | 1.14699 | 0.123591 | 0.115596 | 0.129326 | 0.915802 - 1.14699 | 0.119457 | 0.114475 - 0.143374 | 0.114475 - 0.143374 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 125.429 | 0.0280272 | 9.13582e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.37293 | pJ/byte | 0.171617 | 2.09117 | False | elapsed_ratio>1.35 |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 90.4336 | 0.0203867 | 9.13582e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.98988 | pJ/byte | 0.123735 | 2.10465 | False | elapsed_ratio>1.35 |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 90.5714 | 0.020395 | 9.13582e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.991388 | pJ/byte | 0.123924 | 2.08351 | False | elapsed_ratio>1.35 |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 174.613 | 0.0201896 | 1.82716e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.955654 | pJ/byte | 0.119457 | 1.07044 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 209.574 | 0.0241869 | 1.82716e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.14699 | pJ/byte | 0.143374 | 1.08465 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 167.332 | 0.0192172 | 1.82716e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.915802 | pJ/byte | 0.114475 | 1.05379 | True |  |

## QA

- Detail rows: 6
- Invalid detail rows: 3
- elapsed_ratio>1.35: 3

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
