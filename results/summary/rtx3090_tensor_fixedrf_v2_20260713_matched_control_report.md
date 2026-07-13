# Matched-Control Component Energy

## Method

Default rows use `delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`. Tensor and DRAM rows use direct net-energy subtraction only when their pair policy is `matched-iters` and both ITER values match.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_fixedrf_v2_20260713.csv` |
| acceptance CSVs | `results/summary/rtx3090_tensor_fixedrf_v2_20260713_ncu_acceptance.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_tensor_fixedrf_v2_20260713/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_tensor_fixedrf_v2_20260713_power_state_audit.csv` |
| min elapsed (s) | 16 |
| Tensor control min elapsed (s) | 1.6 |
| DRAM control min elapsed (s) | 0.5 |
| DRAM pair policy | duration-scaled |
| require exact control NCU acceptance | True |
| max elapsed ratio | 1.35 |
| max pair start distance (ms) | 60000 |
| pairing | `nearest-control` |
| Tensor pair policy | `matched-iters` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | False |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| tensor_mma_increment | 33 | medium-high | 0 | 0 | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | pJ/FLOP | 1.94539 | 2.2525 | 2.21296 | 2.36922 | 0.130429 | 0.0423892 | 0.0579043 | 2.24071 - 2.27664 |  |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2393.01 | 0.610788 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.95578 | pJ/FLOP |  | 2.66562 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2474.88 | 0.612785 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.02268 | pJ/FLOP |  | 2.70355 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2444.82 | 0.61084 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.99812 | pJ/FLOP |  | 2.69184 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2427.84 | 0.611283 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.98424 | pJ/FLOP |  | 2.63954 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2382.13 | 0.602761 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.94688 | pJ/FLOP |  | 2.70634 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2417.04 | 0.606419 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.97542 | pJ/FLOP |  | 2.65064 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 2380.3 | 0.602947 | 1.22356e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 1.94539 | pJ/FLOP |  | 2.68564 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3394 | 0.839514 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.29541 | pJ/FLOP |  | 6.62848 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3431.98 | 0.840696 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.32109 | pJ/FLOP |  | 6.87833 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3473.41 | 0.840645 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.34911 | pJ/FLOP |  | 6.96047 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3479.33 | 0.841161 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.35312 | pJ/FLOP |  | 6.93197 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3503.15 | 0.842689 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.36922 | pJ/FLOP |  | 6.71489 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3407.86 | 0.836753 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.30478 | pJ/FLOP |  | 6.67337 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3419.02 | 0.833987 | 1.47861e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.31232 | pJ/FLOP |  | 6.98137 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3419.71 | 0.837712 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.23866 | pJ/FLOP |  | 6.84922 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3467.63 | 0.84279 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.27003 | pJ/FLOP |  | 6.8618 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3481.97 | 0.838318 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.27941 | pJ/FLOP |  | 6.72532 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3425.78 | 0.834827 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24263 | pJ/FLOP |  | 6.80381 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3501.93 | 0.839427 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.29248 | pJ/FLOP |  | 6.76202 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3477.74 | 0.838874 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.27664 | pJ/FLOP |  | 6.83439 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3462.04 | 0.838262 | 1.52757e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.26637 | pJ/FLOP |  | 6.88473 | False | pair_start_distance_ms>60000 |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3411.4 | 0.849523 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.21428 | pJ/FLOP |  | 7.5133 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3452.81 | 0.850965 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24116 | pJ/FLOP |  | 7.1663 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3510.56 | 0.852369 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.27865 | pJ/FLOP |  | 7.4664 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3470.28 | 0.85121 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.2525 | pJ/FLOP |  | 7.35457 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3507.46 | 0.852783 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.27663 | pJ/FLOP |  | 7.18841 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3458.19 | 0.851996 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24465 | pJ/FLOP |  | 7.59088 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3492.7 | 0.851896 | 1.54063e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.26705 | pJ/FLOP |  | 7.40655 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3424.04 | 0.868033 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.28105 | pJ/FLOP |  | 7.98629 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3363.41 | 0.86508 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24065 | pJ/FLOP |  | 8.10932 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3363.5 | 0.864755 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24071 | pJ/FLOP |  | 8.13484 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3377.2 | 0.864268 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24984 | pJ/FLOP |  | 8.23534 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3400.38 | 0.864442 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.26528 | pJ/FLOP |  | 8.1182 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3381.03 | 0.865429 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.25239 | pJ/FLOP |  | 8.22116 | False | pair_start_distance_ms>60000 |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | nearest-control | 3365.07 | 0.864877 | 1.50108e+15 | logical_or_expected | nvml_total_energy | total_energy_mj_delta | gpu_device_total_energy_counter | one_sec_average | 2.24176 | pJ/FLOP |  | 8.26052 | True |  |

## QA

- Detail rows: 35
- Invalid detail rows: 2
- pair_start_distance_ms>60000: 2

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
