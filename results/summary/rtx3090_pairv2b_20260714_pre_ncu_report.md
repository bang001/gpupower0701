# Matched-Control Component Energy

## Method

Default rows use `delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`. Tensor, L2 CG, and DRAM rows use direct net-energy subtraction only when their pair policy is `matched-iters` and both ITER values match.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_pairv2b_20260714_shared.csv, results/raw/rtx3090_pairv2b_20260714_l1.csv` |
| acceptance CSVs | `` |
| NCU summary CSVs | `` |
| power-state audit CSVs | `results/summary/rtx3090_pairv2b_20260714_power_state_audit.csv` |
| min elapsed (s) | 3.5 |
| Tensor control min elapsed (s) | 0.05 |
| L2 control min elapsed (s) | 0.5 |
| DRAM control min elapsed (s) | 0.5 |
| DRAM pair policy | matched-iters |
| L2 pair policy | matched-iters |
| require exact control NCU acceptance | False |
| max elapsed ratio | 8 |
| max pair transition gap (ms) | 30000 |
| pair timing semantics | exact benchmark intervals when present; legacy run_id minus elapsed fallback otherwise |
| pairing | `nearest-control` |
| Tensor pair policy | `matched-iters` |
| min delta_E (J) | 2 |
| min delta fraction | 0.005 |
| require NCU denominator | False |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| global_l1_hit_path | 14 | medium | 0 | 14 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 1.6244 | 3.44244 | 3.68472 | 6.33721 | 1.40952 | 1.89732 | 0.409454 | 2.45935 - 4.35732 | 0.430305 | 0.20305 - 0.792151 | 0.310432 - 0.548047 |
| shared_l1_scalar_path | 15 | medium-high | 0 | 15 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/byte | 3.39891 | 5.09826 | 5.25022 | 7.14865 | 1.08879 | 1.27678 | 0.213562 | 4.65793 - 5.96511 | 0.637283 | 0.424864 - 0.893582 | 0.572572 - 0.745638 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | execution order | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 8 | 8 | 1 | 4 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | -2.34197 | -0.00246058 | 1.69116e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | -0.138483 | pJ/byte | -0.0173104 | 1.11307 | False | delta_fraction<0.005;negative_coefficient |
| global_l1_hit_path | 8 | 8 | 1 | 4 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 40.4136 | 0.0428115 | 1.69116e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.38969 | pJ/byte | 0.298712 | 1.09686 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 4 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 52.7171 | 0.0560392 | 1.69116e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.11721 | pJ/byte | 0.389652 | 1.09894 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 4 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 27.4712 | 0.029143 | 1.69116e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.6244 | pJ/byte | 0.20305 | 1.10759 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 4 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 41.5915 | 0.0440771 | 1.69116e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.45935 | pJ/byte | 0.307419 | 1.10444 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 8 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 112.946 | 0.112834 | 1.78227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 6.33721 | pJ/byte | 0.792151 | 1.11716 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 8 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 91.4025 | 0.0914612 | 1.78227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.12842 | pJ/byte | 0.641053 | 1.11516 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 8 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 43.7056 | 0.0455255 | 1.78227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.45224 | pJ/byte | 0.30653 | 1.09018 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 8 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 77.1523 | 0.0776028 | 1.78227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 4.32887 | pJ/byte | 0.541109 | 1.0866 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 8 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 55.9425 | 0.0582844 | 1.78227e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.13883 | pJ/byte | 0.392354 | 1.10455 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 16 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 106.385 | 0.104488 | 1.81903e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.84842 | pJ/byte | 0.731053 | 1.10671 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 16 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 79.7533 | 0.0798421 | 1.81903e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 4.38438 | pJ/byte | 0.548047 | 1.10028 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 16 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 45.7428 | 0.0472461 | 1.81903e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.51468 | pJ/byte | 0.314335 | 1.0803 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 16 | global_l1_load_only_minus_global_addr_only | nearest-control | treatment_then_control | 74.8781 | 0.0750702 | 1.81903e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 4.11637 | pJ/byte | 0.514546 | 1.09298 | True |  |
| global_l1_hit_path | 8 | 8 | 1 | 16 | global_l1_load_only_minus_global_addr_only | nearest-control | control_then_treatment | 68.1419 | 0.069117 | 1.81903e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.74605 | pJ/byte | 0.468256 | 1.08924 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 4 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 102.321 | 0.106118 | 1.96355e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.21102 | pJ/byte | 0.651378 | 1.0359 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 4 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 91.4997 | 0.0949746 | 1.96355e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 4.65991 | pJ/byte | 0.582489 | 1.04229 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 4 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 132.899 | 0.134504 | 1.96355e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 6.76832 | pJ/byte | 0.846041 | 1.03478 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 4 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 130.798 | 0.134606 | 1.96355e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 6.66129 | pJ/byte | 0.832662 | 1.03404 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 4 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 140.367 | 0.143941 | 1.96355e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 7.14865 | pJ/byte | 0.893582 | 1.04568 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 8 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 88.4381 | 0.0841781 | 2.25841e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.91595 | pJ/byte | 0.489494 | 1.0265 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 8 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 124.455 | 0.117597 | 2.25841e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.51075 | pJ/byte | 0.688844 | 1.03376 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 8 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 103.448 | 0.0986663 | 2.25841e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 4.58058 | pJ/byte | 0.572572 | 1.02228 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 8 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 89.5861 | 0.0843877 | 2.25841e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.96678 | pJ/byte | 0.495848 | 1.03728 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 8 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 113.433 | 0.105171 | 2.25841e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.02269 | pJ/byte | 0.627836 | 1.05444 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 16 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 121.28 | 0.126763 | 2.03316e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.96511 | pJ/byte | 0.745638 | 1.02413 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 16 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 69.1053 | 0.0755333 | 2.03316e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 3.39891 | pJ/byte | 0.424864 | 1.04626 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 16 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 118.512 | 0.124343 | 2.03316e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.82895 | pJ/byte | 0.728619 | 1.05155 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 16 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | treatment_then_control | 101.987 | 0.105328 | 2.03316e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.01616 | pJ/byte | 0.62702 | 1.03414 | True |  |
| shared_l1_scalar_path | 64 | 8 | 1 | 16 | shared_scalar_load_only_minus_shared_scalar_addr_only | nearest-control | control_then_treatment | 103.656 | 0.109326 | 2.03316e+13 | expected_no_ncu_match | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 5.09826 | pJ/byte | 0.637283 | 1.01493 | True |  |

## QA

- Detail rows: 30
- Invalid detail rows: 1
- delta_fraction<0.005: 1
- negative_coefficient: 1

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
