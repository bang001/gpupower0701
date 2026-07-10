# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_strict_scope_shared_lr8_focus_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_strict_scope_shared_lr8_focus_power_state_audit_20260708.csv` |
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
| shared_l1_scalar_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 0.878464 | 1.36472 | 1.3215 | 1.6843 | 0.307575 | 0.419113 | 0.225376 | 0.975908 - 1.62386 | 0.17059 | 0.109808 - 0.210538 | 0.121988 - 0.202983 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 293.115 | 0.0307891 | 1.99692e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.46783 | pJ/byte | 0.183479 | 1.0274 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 260.805 | 0.0264145 | 2.06726e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.2616 | pJ/byte | 0.1577 | 1.06126 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 345.678 | 0.0351587 | 2.05235e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.6843 | pJ/byte | 0.210538 | 1.06016 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 316.705 | 0.0326406 | 2.02571e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.56343 | pJ/byte | 0.195428 | 1.01452 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 218.498 | 0.0225198 | 2.03566e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.07335 | pJ/byte | 0.134169 | 1.06487 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 170.84 | 0.0185354 | 1.94476e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.878464 | pJ/byte | 0.109808 | 1.0044 | True |  |

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
