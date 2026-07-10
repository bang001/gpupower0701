# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_power_state_audit_20260708.csv` |
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
| shared_l1_scalar_path | 12 | medium | 12 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.277705 | 1.16049 | 1.08137 | 1.69989 | 0.482402 | 0.816951 | 0.415689 | 0.615567 - 1.50088 | 0.145061 | 0.0347131 - 0.212486 | 0.0769459 - 0.18761 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 279.423 | 0.0311028 | 1.82277e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.53296 | pJ/byte | 0.191619 | 1.06823 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 306.766 | 0.0334317 | 1.8563e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.65257 | pJ/byte | 0.206571 | 1.07721 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 307.927 | 0.0340433 | 1.81146e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.69989 | pJ/byte | 0.212486 | 1.05675 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 269.333 | 0.0297789 | 1.83369e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.4688 | pJ/byte | 0.183601 | 1.10847 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 210.198 | 0.0232203 | 1.88412e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.11563 | pJ/byte | 0.139454 | 1.05983 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 207.274 | 0.0233641 | 1.84551e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.12313 | pJ/byte | 0.140391 | 1.05428 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 222.875 | 0.0249886 | 1.86064e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.19784 | pJ/byte | 0.14973 | 1.06411 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 221.202 | 0.0250599 | 1.84423e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.19942 | pJ/byte | 0.149928 | 1.02655 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 96.7642 | 0.0108367 | 1.89392e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.510919 | pJ/byte | 0.0638649 | 1.02606 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 51.2961 | 0.0059304 | 1.84714e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.277705 | pJ/byte | 0.0347131 | 1.00408 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 92.6295 | 0.0101769 | 1.94041e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.477372 | pJ/byte | 0.0596715 | 1.08091 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 138.068 | 0.0153299 | 1.91704e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.720215 | pJ/byte | 0.0900269 | 1.06016 | True |  |

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
