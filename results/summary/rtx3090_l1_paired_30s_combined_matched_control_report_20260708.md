# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_l1_paired_30s_stability_20260708.csv, results/raw/rtx3090_l1_paired_30s_stability_rerun2_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_l1_paired_30s_combined_power_state_audit_20260708.csv` |
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
| global_l1_hit_path | 12 | medium-high | 12 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.822693 | 1.18781 | 1.32284 | 2.68417 | 0.465507 | 0.199908 | 0.391905 | 1.14356 - 1.36129 | 0.148476 | 0.102837 - 0.335521 | 0.142944 - 0.170161 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 294.148 | 0.0303781 | 2.53372e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.16093 | pJ/byte | 0.145116 | 1.04164 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 278.968 | 0.0293448 | 2.47711e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.12618 | pJ/byte | 0.140772 | 1.0104 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 395.599 | 0.0407872 | 2.52454e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.56701 | pJ/byte | 0.195877 | 1.03699 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 262.368 | 0.0272902 | 2.51305e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.04402 | pJ/byte | 0.130503 | 1.04592 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 332.368 | 0.0349731 | 2.47478e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.34302 | pJ/byte | 0.167877 | 1.01952 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 293.588 | 0.0309673 | 2.45863e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.19411 | pJ/byte | 0.149264 | 1.00071 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 293.822 | 0.0308686 | 2.48541e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.18219 | pJ/byte | 0.147774 | 1.01307 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 296.078 | 0.0306571 | 2.5159e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.17683 | pJ/byte | 0.147104 | 1.03692 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 296.382 | 0.0311597 | 2.48346e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.19342 | pJ/byte | 0.149178 | 1.01942 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 342.725 | 0.0357961 | 2.48432e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.37955 | pJ/byte | 0.172444 | 1.01975 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 670.85 | 0.0698078 | 2.49928e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.68417 | pJ/byte | 0.335521 | 1.03536 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 202.485 | 0.0214825 | 2.46124e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.822693 | pJ/byte | 0.102837 | 1.01869 | True |  |

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
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
