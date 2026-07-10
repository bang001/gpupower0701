# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_paired_lr8_30s_stability_rerun2_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_shared_paired_lr8_30s_stability_rerun2_power_state_audit_20260708.csv` |
| min elapsed (s) | 1 |
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
| shared_l1_scalar_path | 6 | medium | 6 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 1.09303 | 1.44506 | 1.40717 | 1.53911 | 0.160996 | 0.0788147 | 0.111411 | 1.25286 - 1.5236 | 0.180633 | 0.136629 - 0.192389 | 0.156608 - 0.19045 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 222.708 | 0.0228363 | 2.03752e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.09303 | pJ/byte | 0.136629 | 1.04409 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 299.901 | 0.0306267 | 2.05469e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.45959 | pJ/byte | 0.182449 | 1.03354 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 279.964 | 0.0295427 | 1.98178e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.41269 | pJ/byte | 0.176586 | 1.01045 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 307.111 | 0.0316183 | 2.03643e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.50809 | pJ/byte | 0.188511 | 1.04983 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 306.222 | 0.0321685 | 1.98961e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.53911 | pJ/byte | 0.192389 | 1.01874 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 293.411 | 0.0299739 | 2.05106e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.43053 | pJ/byte | 0.178817 | 1.04323 | True |  |

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
