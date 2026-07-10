# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_targeted_shared_stability_20260708.csv, results/raw/rtx3090_targeted_l1_stability_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| min elapsed (s) | 16 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 10 |
| min delta fraction | 0.005 |
| require NCU denominator | True |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| global_l1_hit_path | 26 | medium | 26 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.227374 | 0.837516 | 0.846426 | 1.75292 | 0.432079 | 0.521551 | 0.515905 | 0.609589 - 1.01006 | 0.10469 | 0.0284217 - 0.219115 | 0.0761986 - 0.128507 |
| shared_l1_scalar_path | 29 | medium | 29 | 0 | nvml_total_energy | total_energy_mj_delta | one_sec_average | pJ/byte | 0.284804 | 1.21916 | 1.23824 | 2.1044 | 0.544698 | 0.762636 | 0.44678 | 0.914215 - 1.63368 | 0.152395 | 0.0356005 - 0.26305 | 0.114277 - 0.20421 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---:|---|---:|---:|---|---|
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 273.298 | 0.0441658 | 1.6713e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.63524 | pJ/byte | 0.204405 | 1.0316 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 197.765 | 0.0333605 | 1.60747e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.23029 | pJ/byte | 0.153786 | 1.01174 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 165.182 | 0.0286464 | 1.5791e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.04605 | pJ/byte | 0.130756 | 1.03533 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 208.447 | 0.0351024 | 1.61191e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.29316 | pJ/byte | 0.161646 | 1.00549 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 170.086 | 0.0285256 | 1.62089e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.04934 | pJ/byte | 0.131167 | 1.01488 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 275.63 | 0.0447462 | 1.66762e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.65284 | pJ/byte | 0.206605 | 1.01732 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 139.004 | 0.0233408 | 1.63395e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.850721 | pJ/byte | 0.10634 | 1.00548 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 293.482 | 0.0477378 | 1.67425e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.75292 | pJ/byte | 0.219115 | 1.03911 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 165.933 | 0.0275157 | 1.6428e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.01006 | pJ/byte | 0.126258 | 1.00579 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | nearest-control | 139.466 | 0.0226596 | 1.69191e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.824311 | pJ/byte | 0.103039 | 1.0381 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 38.3614 | 0.00647109 | 1.68715e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.227374 | pJ/byte | 0.0284217 | 1.00316 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 165.513 | 0.0271196 | 1.7142e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.965539 | pJ/byte | 0.120692 | 1.01477 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 84.7591 | 0.014474 | 1.66725e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.508377 | pJ/byte | 0.0635472 | 1.00072 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 53.9595 | 0.00892555 | 1.71838e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.314015 | pJ/byte | 0.0392518 | 1.01606 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 161.148 | 0.0262485 | 1.74175e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.925203 | pJ/byte | 0.11565 | 1.02854 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 132.671 | 0.0214949 | 1.73165e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.766151 | pJ/byte | 0.0957689 | 1.04146 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 174.525 | 0.0295889 | 1.66599e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.04758 | pJ/byte | 0.130947 | 1.00025 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 136.402 | 0.0228558 | 1.68332e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.810316 | pJ/byte | 0.10129 | 1.00111 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 150.389 | 0.0261255 | 1.64486e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.914296 | pJ/byte | 0.114287 | 1.00748 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 8 | global_l1_load_only_minus_clocked_empty | nearest-control | 112.547 | 0.0181327 | 1.76829e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.636477 | pJ/byte | 0.0795596 | 1.03641 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 114.914 | 0.0184121 | 1.79066e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.641738 | pJ/byte | 0.0802172 | 1.03856 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 62.4916 | 0.0102822 | 1.75542e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.355993 | pJ/byte | 0.0444991 | 1.02273 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 101.545 | 0.016566 | 1.75853e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.57744 | pJ/byte | 0.07218 | 1.01215 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | -6.85654 | -0.00110809 | 1.79924e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.038108 | pJ/byte | -0.0047635 | 1.04838 | False | delta_E<10J;delta_fraction<0.005;negative_coefficient |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 88.4892 | 0.0143457 | 1.77666e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.498065 | pJ/byte | 0.0622582 | 1.034 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 40.0851 | 0.00661523 | 1.75196e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.228801 | pJ/byte | 0.0286002 | 1.01229 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | -536.068 | -0.0786878 | 1.73146e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -3.09605 | pJ/byte | -0.387006 | 1.15962 | False | negative_coefficient |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | 43.3271 | 0.00710894 | 1.77001e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.244785 | pJ/byte | 0.0305981 | 1.01195 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | -441.838 | -0.0656332 | 1.73086e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -2.55271 | pJ/byte | -0.319089 | 1.15308 | False | negative_coefficient |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | nearest-control | -15.6727 | -0.00262862 | 1.73045e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.0905704 | pJ/byte | -0.0113213 | 1.00145 | False | delta_fraction<0.005;negative_coefficient |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 208.43 | 0.0343334 | 1.27583e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.63368 | pJ/byte | 0.20421 | 1.12743 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 225.496 | 0.0374006 | 1.26752e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.77904 | pJ/byte | 0.222379 | 1.00319 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 260.252 | 0.0438957 | 1.25914e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.06691 | pJ/byte | 0.258364 | 1.02852 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 232.58 | 0.0384243 | 1.27965e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.81753 | pJ/byte | 0.227191 | 1.0178 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 206.418 | 0.0350298 | 1.25109e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.64991 | pJ/byte | 0.206239 | 1.01933 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 269.591 | 0.0441578 | 1.28108e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.1044 | pJ/byte | 0.26305 | 1.02314 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 263.944 | 0.0441689 | 1.26497e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 2.08656 | pJ/byte | 0.26082 | 1.00805 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 222.818 | 0.0383744 | 1.24225e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.79367 | pJ/byte | 0.224209 | 1.0358 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 150.693 | 0.0254156 | 1.25891e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.19701 | pJ/byte | 0.149626 | 1.00848 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 228.371 | 0.0380473 | 1.2676e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.8016 | pJ/byte | 0.2252 | 1.01565 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 120.045 | 0.0195938 | 1.35297e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.887272 | pJ/byte | 0.110909 | 1.0072 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 156.196 | 0.0245148 | 1.40006e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.11564 | pJ/byte | 0.139455 | 1.05404 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 157.203 | 0.0252864 | 1.37019e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.14731 | pJ/byte | 0.143414 | 1.0557 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 183.436 | 0.0294354 | 1.36905e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.33988 | pJ/byte | 0.167485 | 1.04384 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 141.915 | 0.0233202 | 1.32673e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.06966 | pJ/byte | 0.133708 | 1.02075 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 219.621 | 0.0357116 | 1.34037e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.63851 | pJ/byte | 0.204814 | 1.02929 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 170.019 | 0.0288957 | 1.28554e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.32256 | pJ/byte | 0.16532 | 1.03905 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 192.565 | 0.0335138 | 1.25877e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.52978 | pJ/byte | 0.191223 | 1.04743 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 119.18 | 0.0196976 | 1.33298e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.894091 | pJ/byte | 0.111761 | 1.01355 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 8 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 187.531 | 0.0301289 | 1.36979e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.36905 | pJ/byte | 0.171131 | 1.05024 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 56.6616 | 0.00924633 | 1.37066e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.413389 | pJ/byte | 0.0516736 | 1.02722 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 121.264 | 0.0204827 | 1.32643e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.914215 | pJ/byte | 0.114277 | 1.01166 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 83.4379 | 0.0129487 | 1.43602e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.581037 | pJ/byte | 0.0726297 | 1.09558 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 74.4953 | 0.0121815 | 1.36275e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.546654 | pJ/byte | 0.0683318 | 1.0044 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 87.3261 | 0.0142716 | 1.35878e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.642682 | pJ/byte | 0.0803353 | 1.02201 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 93.1041 | 0.0149436 | 1.39196e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.668871 | pJ/byte | 0.0836089 | 1.03694 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 54.5444 | 0.00877382 | 1.38391e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.394134 | pJ/byte | 0.0492667 | 1.0444 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 170.689 | 0.0270265 | 1.40005e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 1.21916 | pJ/byte | 0.152395 | 1.04501 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | -28.013 | -0.00468166 | 1.3423e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | -0.208694 | pJ/byte | -0.0260867 | 1.01633 | False | delta_fraction<0.005;negative_coefficient |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | nearest-control | 39.2366 | 0.00639245 | 1.37767e+14 | ncu_actual_exact | nvml_total_energy | total_energy_mj_delta | one_sec_average | 0.284804 | pJ/byte | 0.0356005 | 1.01289 | True |  |

## QA

- Detail rows: 60
- Invalid detail rows: 5
- delta_E<10J: 1
- delta_fraction<0.005: 3
- negative_coefficient: 5

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
