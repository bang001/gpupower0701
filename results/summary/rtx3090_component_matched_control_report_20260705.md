# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_register_duration_20260705.csv, results/raw/rtx3090_component_accept_energy_duration_20260705.csv` |
| acceptance CSV | `results/summary/rtx3090_component_sep_ncu_scalarshared_acceptance_20260705.csv` |
| min elapsed (s) | 1 |
| max elapsed ratio | 1.35 |

## Component Summary

| component | rows | estimate unit | min | median | mean | max | stdev | median pJ/bit | pJ/bit min-max |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| dram_cg_stream_path | 3 | pJ/byte | 17.0118 | 35.8406 | 33.7321 | 48.344 | 15.7722 | 4.48008 | 2.12647 - 6.043 |
| global_l1_hit_path | 4 | pJ/byte | 0.161142 | 3.59549 | 2.84278 | 4.01899 | 1.81584 | 0.449436 | 0.0201428 - 0.502374 |
| l2_hit_cg_path | 5 | pJ/byte | 4.37316 | 6.38041 | 10.1722 | 20.3108 | 6.71776 | 0.797551 | 0.546645 - 2.53885 |
| register_operand_control | 4 | pJ/reg-op | 494.167 | 767.271 | 780.017 | 1091.36 | 276.45 | 0.093661 | 0.0603232 - 0.133222 |
| shared_l1_scalar_path | 6 | pJ/byte | 0.120023 | 1.78461 | 2.30002 | 6.26443 | 2.12819 | 0.223076 | 0.0150028 - 0.783054 |
| tensor_mma_increment | 4 | pJ/FLOP | 0.0222683 | 0.194024 | 0.247911 | 0.581327 | 0.263443 |  |  |
| tensor_register_path | 5 | pJ/FLOP | 0.0590796 | 0.114916 | 0.13438 | 0.20883 | 0.0663076 |  |  |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | delta_E (J) | denominator | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | 1 | dram_cg_load_only_minus_clocked_empty | 139.614 | 2.88793e+12 | 48.344 | pJ/byte | 6.043 | 1.0358 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 4 | dram_cg_load_only_minus_clocked_empty | 103.648 | 2.89192e+12 | 35.8406 | pJ/byte | 4.48008 | 1.00092 | True |  |
| dram_cg_stream_path | 8192 | 16 | 1 | 16 | dram_cg_load_only_minus_clocked_empty | 49.0646 | 2.88416e+12 | 17.0118 | pJ/byte | 2.12647 | 1.0162 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 1 | global_l1_load_only_minus_clocked_empty | 37.6614 | 1.14398e+13 | 3.29214 | pJ/byte | 0.411518 | 1.18122 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | 52.7419 | 1.31232e+13 | 4.01899 | pJ/byte | 0.502374 | 1.01833 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | 2.27851 | 1.41397e+13 | 0.161142 | pJ/byte | 0.0201428 | 1.01896 | True |  |
| global_l1_hit_path | 64 | 16 | 1 | 1 | global_l1_load_only_minus_clocked_empty | 37.9535 | 9.73455e+12 | 3.89884 | pJ/byte | 0.487355 | 1.00383 | True |  |
| global_l1_hit_path | 64 | 16 | 1 | 4 | global_l1_load_only_minus_clocked_empty | -17.3904 | 1.07331e+13 | -1.62026 | pJ/byte | -0.202533 | 1.013 | False | negative_coefficient |
| global_l1_hit_path | 64 | 16 | 1 | 16 | global_l1_load_only_minus_clocked_empty | -56.2443 | 1.12223e+13 | -5.01185 | pJ/byte | -0.626482 | 1.01186 | False | negative_coefficient |
| l2_hit_cg_path | 16 | 16 | 1 | 1 | l2_cg_load_only_minus_clocked_empty | 32.1615 | 7.35429e+12 | 4.37316 | pJ/byte | 0.546645 | 1.19617 | True |  |
| l2_hit_cg_path | 16 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | 47.3856 | 7.42673e+12 | 6.38041 | pJ/byte | 0.797551 | 1.01716 | True |  |
| l2_hit_cg_path | 16 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | -1.75688 | 7.17721e+12 | -0.244785 | pJ/byte | -0.0305982 | 1.02325 | False | negative_coefficient |
| l2_hit_cg_path | 64 | 16 | 1 | 1 | l2_cg_load_only_minus_clocked_empty | 160.624 | 7.90828e+12 | 20.3108 | pJ/byte | 2.53885 | 1.01459 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 4 | l2_cg_load_only_minus_clocked_empty | 110.397 | 8.03291e+12 | 13.7431 | pJ/byte | 1.71789 | 1.00483 | True |  |
| l2_hit_cg_path | 64 | 16 | 1 | 16 | l2_cg_load_only_minus_clocked_empty | 48.1164 | 7.94853e+12 | 6.0535 | pJ/byte | 0.756688 | 1.00813 | True |  |
| register_operand_control | 2048 | 4 | 1 | 1 | reg_operand_only_minus_clocked_empty | -50.9864 | 1.38524e+10 | -3680.68 | pJ/reg-op | -0.449302 | 1.08663 | False | negative_coefficient |
| register_operand_control | 2048 | 4 | 2 | 1 | reg_operand_only_minus_clocked_empty | -45.3793 | 1.57244e+10 | -2885.91 | pJ/reg-op | -0.352284 | 1.01255 | False | negative_coefficient |
| register_operand_control | 2048 | 4 | 4 | 1 | reg_operand_only_minus_clocked_empty | 34.3369 | 3.14626e+10 | 1091.36 | pJ/reg-op | 0.133222 | 1.0191 | True |  |
| register_operand_control | 2048 | 4 | 8 | 1 | reg_operand_only_minus_clocked_empty | 27.6983 | 2.9916e+10 | 925.868 | pJ/reg-op | 0.113021 | 1.09013 | True |  |
| register_operand_control | 2048 | 4 | 16 | 1 | reg_operand_only_minus_clocked_empty | -15.2728 | 3.07637e+10 | -496.455 | pJ/reg-op | -0.0606025 | 1.04444 | False | negative_coefficient |
| register_operand_control | 2048 | 4 | 32 | 1 | reg_operand_only_minus_clocked_empty | 15.1015 | 3.05595e+10 | 494.167 | pJ/reg-op | 0.0603232 | 1.00512 | True |  |
| register_operand_control | 2048 | 4 | 64 | 1 | reg_operand_only_minus_clocked_empty | 19.1269 | 3.14238e+10 | 608.673 | pJ/reg-op | 0.0743009 | 1.05341 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | 1 | shared_scalar_load_only_minus_clocked_empty | 41.0971 | 1.84008e+13 | 2.23344 | pJ/byte | 0.27918 | 1.21207 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | 52.2213 | 1.99651e+13 | 2.61563 | pJ/byte | 0.326953 | 1.0091 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | 2.58609 | 2.15467e+13 | 0.120023 | pJ/byte | 0.0150028 | 1.0173 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 1 | shared_scalar_load_only_minus_clocked_empty | 109.452 | 1.7472e+13 | 6.26443 | pJ/byte | 0.783054 | 1.00439 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | 24.4925 | 1.98997e+13 | 1.2308 | pJ/byte | 0.15385 | 1.00553 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | 29.9224 | 2.24008e+13 | 1.33578 | pJ/byte | 0.166972 | 1.02141 | True |  |
| tensor_mma_increment | 2048 | 4 | 1 | 1 | reg_mma_minus_reg_operand_only | 79.6805 | 1.37066e+14 | 0.581327 | pJ/FLOP |  | 1.00138 | True |  |
| tensor_mma_increment | 2048 | 4 | 2 | 1 | reg_mma_minus_reg_operand_only | 42.8705 | 1.27588e+14 | 0.336007 | pJ/FLOP |  | 1.01427 | True |  |
| tensor_mma_increment | 2048 | 4 | 4 | 1 | reg_mma_minus_reg_operand_only | -0.849718 | 1.7365e+14 | -0.00489329 | pJ/FLOP |  | 1.02778 | False | negative_coefficient |
| tensor_mma_increment | 2048 | 4 | 8 | 1 | reg_mma_minus_reg_operand_only | -9.91972 | 1.9228e+14 | -0.05159 | pJ/FLOP |  | 1.01211 | False | negative_coefficient |
| tensor_mma_increment | 2048 | 4 | 16 | 1 | reg_mma_minus_reg_operand_only | 4.89676 | 2.19898e+14 | 0.0222683 | pJ/FLOP |  | 1.03814 | True |  |
| tensor_mma_increment | 2048 | 4 | 32 | 1 | reg_mma_minus_reg_operand_only | 12.7227 | 2.44475e+14 | 0.0520411 | pJ/FLOP |  | 1.01787 | True |  |
| tensor_mma_increment | 2048 | 4 | 64 | 1 | reg_mma_minus_reg_operand_only | -4.18424 | 2.50341e+14 | -0.0167142 | pJ/FLOP |  | 1.00804 | False | negative_coefficient |
| tensor_register_path | 2048 | 4 | 1 | 1 | reg_mma_minus_clocked_empty | 28.6236 | 1.37066e+14 | 0.20883 | pJ/FLOP |  | 1.08813 | True |  |
| tensor_register_path | 2048 | 4 | 2 | 1 | reg_mma_minus_clocked_empty | -3.15653 | 1.27588e+14 | -0.02474 | pJ/FLOP |  | 1.00171 | False | negative_coefficient |
| tensor_register_path | 2048 | 4 | 4 | 1 | reg_mma_minus_clocked_empty | 34.441 | 1.7365e+14 | 0.198336 | pJ/FLOP |  | 1.04741 | True |  |
| tensor_register_path | 2048 | 4 | 8 | 1 | reg_mma_minus_clocked_empty | 17.4471 | 1.9228e+14 | 0.0907378 | pJ/FLOP |  | 1.10334 | True |  |
| tensor_register_path | 2048 | 4 | 16 | 1 | reg_mma_minus_clocked_empty | -9.81491 | 2.19898e+14 | -0.0446339 | pJ/FLOP |  | 1.00607 | False | negative_coefficient |
| tensor_register_path | 2048 | 4 | 32 | 1 | reg_mma_minus_clocked_empty | 28.0942 | 2.44475e+14 | 0.114916 | pJ/FLOP |  | 1.01268 | True |  |
| tensor_register_path | 2048 | 4 | 64 | 1 | reg_mma_minus_clocked_empty | 14.79 | 2.50341e+14 | 0.0590796 | pJ/FLOP |  | 1.04501 | True |  |

## QA

- Detail rows: 42
- Invalid detail rows: 11
- negative_coefficient: 11

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
