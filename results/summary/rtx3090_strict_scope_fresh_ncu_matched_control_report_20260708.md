# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_strict_scope_tensor_rf8_rf16_20260708.csv, results/raw/rtx3090_strict_scope_shared_lr8_focus_20260708.csv, results/raw/rtx3090_strict_scope_l1_lr4_focus_20260708.csv, results/raw/rtx3090_strict_scope_l2_lr4_lr8_focus_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_strict_scope_fresh_ncu_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_strict_scope_fresh_ncu_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_power_state_audit_20260708.csv, results/summary/rtx3090_strict_scope_shared_lr8_focus_power_state_audit_20260708.csv, results/summary/rtx3090_strict_scope_l1_lr4_focus_power_state_audit_20260708.csv, results/summary/rtx3090_strict_scope_l2_lr4_lr8_focus_power_state_audit_20260708.csv` |
| min elapsed (s) | 10 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 0 |
| min delta fraction | 0.005 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| global_l1_hit_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 1.19872 | 1.38786 | 1.39001 | 1.62093 | 0.153799 | 0.17678 | 0.110817 | 1.22666 - 1.5555 | 0.173483 | 0.14984 - 0.202616 | 0.153333 - 0.194437 |
| l2_hit_cg_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 6.48279 | 9.04858 | 8.92761 | 11.0192 | 1.80207 | 2.66599 | 0.199155 | 6.88796 - 10.8463 | 1.13107 | 0.810349 - 1.37741 | 0.860995 - 1.35578 |
| shared_l1_scalar_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 0.878464 | 1.36472 | 1.3215 | 1.6843 | 0.307575 | 0.419113 | 0.225376 | 0.975908 - 1.62386 | 0.17059 | 0.109808 - 0.210538 | 0.121988 - 0.202983 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 401.441 | 0.0421732 | 2.47661e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.62093 | pJ/byte | 0.202616 | 1.009 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 297.887 | 0.0329761 | 2.37435e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.2546 | pJ/byte | 0.156825 | 1.02491 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 360.182 | 0.0387522 | 2.41722e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.49007 | pJ/byte | 0.186259 | 1.0076 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 347.13 | 0.0362944 | 2.50053e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.38823 | pJ/byte | 0.173528 | 1.03582 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 295.949 | 0.0313706 | 2.46888e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.19872 | pJ/byte | 0.14984 | 1.01093 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 340.129 | 0.0361675 | 2.45137e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.3875 | pJ/byte | 0.173438 | 1.02097 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 818.675 | 0.0809959 | 7.67029e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 10.6733 | pJ/byte | 1.33416 | 1.03482 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 648.209 | 0.0676576 | 7.37701e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 8.78689 | pJ/byte | 1.09836 | 1.009 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | nearest-control | 826.334 | 0.0843161 | 7.49901e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 11.0192 | pJ/byte | 1.37741 | 1.00654 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 557.556 | 0.0556356 | 7.64495e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 7.29312 | pJ/byte | 0.911641 | 1.04244 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 707.817 | 0.0713963 | 7.60253e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 9.31028 | pJ/byte | 1.16378 | 1.01534 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 8 | l2_cg_load_only_minus_clocked_empty | nearest-control | 484.419 | 0.0499981 | 7.47239e+13 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 6.48279 | pJ/byte | 0.810349 | 1.01937 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 293.115 | 0.0307891 | 1.99692e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.46783 | pJ/byte | 0.183479 | 1.0274 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 260.805 | 0.0264145 | 2.06726e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.2616 | pJ/byte | 0.1577 | 1.06126 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 345.678 | 0.0351587 | 2.05235e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.6843 | pJ/byte | 0.210538 | 1.06016 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 316.705 | 0.0326406 | 2.02571e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.56343 | pJ/byte | 0.195428 | 1.01452 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 218.498 | 0.0225198 | 2.03566e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.07335 | pJ/byte | 0.134169 | 1.06487 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 170.84 | 0.0185354 | 1.94476e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 0.878464 | pJ/byte | 0.109808 | 1.0044 | True |  |

## QA

- Detail rows: 18
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
