# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_strict_scope_l1_lr4_focus_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_strict_scope_l1_lr4_focus_power_state_audit_20260708.csv` |
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
| global_l1_hit_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 1.19872 | 1.38786 | 1.39001 | 1.62093 | 0.153799 | 0.17678 | 0.110817 | 1.22666 - 1.5555 | 0.173483 | 0.14984 - 0.202616 | 0.153333 - 0.194437 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 401.441 | 0.0421732 | 2.47661e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.62093 | pJ/byte | 0.202616 | 1.009 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 297.887 | 0.0329761 | 2.37435e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.2546 | pJ/byte | 0.156825 | 1.02491 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 360.182 | 0.0387522 | 2.41722e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.49007 | pJ/byte | 0.186259 | 1.0076 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 347.13 | 0.0362944 | 2.50053e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.38823 | pJ/byte | 0.173528 | 1.03582 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 295.949 | 0.0313706 | 2.46888e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.19872 | pJ/byte | 0.14984 | 1.01093 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 340.129 | 0.0361675 | 2.45137e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.3875 | pJ/byte | 0.173438 | 1.02097 | True |  |

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
