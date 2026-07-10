# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_tensor_register_b16_duration_20260705.csv, results/raw/rtx3090_component_accept_energy_duration_20260705.csv` |
| acceptance CSV | `results/summary/rtx3090_component_sep_ncu_scalarshared_regb16_acceptance_20260705.csv` |
| min elapsed (s) | 1 |
| max elapsed ratio | 1.35 |

## Component Summary

| component | rows | estimate unit | min | median | mean | max | stdev | median pJ/bit | pJ/bit min-max |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| dram_cg_stream_path | 3 | pJ/byte | 17.0118 | 35.8406 | 33.7321 | 48.344 | 15.7722 | 4.48008 | 2.12647 - 6.043 |
| global_l1_hit_path | 4 | pJ/byte | 0.161142 | 3.59549 | 2.84278 | 4.01899 | 1.81584 | 0.449436 | 0.0201428 - 0.502374 |
| l2_hit_cg_path | 5 | pJ/byte | 4.37316 | 6.38041 | 10.1722 | 20.3108 | 6.71776 | 0.797551 | 0.546645 - 2.53885 |
| shared_l1_scalar_path | 6 | pJ/byte | 0.120023 | 1.78461 | 2.30002 | 6.26443 | 2.12819 | 0.223076 | 0.0150028 - 0.783054 |
| tensor_mma_increment | 6 | pJ/FLOP | 0.0348587 | 0.145561 | 0.156565 | 0.271056 | 0.0926475 |  |  |

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
| register_operand_control | 2048 | 16 | 1 | 1 | reg_operand_only_minus_clocked_empty | -221.678 | 3.18561e+10 | -6958.72 | pJ/reg-op | -0.849453 | 1.03146 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 2 | 1 | reg_operand_only_minus_clocked_empty | -356.527 | 1.98077e+10 | -17999.4 | pJ/reg-op | -2.19719 | 1.0127 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 4 | 1 | reg_operand_only_minus_clocked_empty | -282.819 | 3.05636e+10 | -9253.47 | pJ/reg-op | -1.12957 | 1.02676 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 8 | 1 | reg_operand_only_minus_clocked_empty | -324.579 | 3.15417e+10 | -10290.5 | pJ/reg-op | -1.25616 | 1.00921 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 16 | 1 | reg_operand_only_minus_clocked_empty | -349.817 | 3.20236e+10 | -10923.7 | pJ/reg-op | -1.33346 | 1.04765 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 32 | 1 | reg_operand_only_minus_clocked_empty | -310.968 | 3.12896e+10 | -9938.39 | pJ/reg-op | -1.21318 | 1.01342 | False | negative_coefficient |
| register_operand_control | 2048 | 16 | 64 | 1 | reg_operand_only_minus_clocked_empty | -356.919 | 3.17329e+10 | -11247.6 | pJ/reg-op | -1.373 | 1.01189 | False | negative_coefficient |
| shared_l1_scalar_path | 16 | 16 | 1 | 1 | shared_scalar_load_only_minus_clocked_empty | 41.0971 | 1.84008e+13 | 2.23344 | pJ/byte | 0.27918 | 1.21207 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | 52.2213 | 1.99651e+13 | 2.61563 | pJ/byte | 0.326953 | 1.0091 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | 2.58609 | 2.15467e+13 | 0.120023 | pJ/byte | 0.0150028 | 1.0173 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 1 | shared_scalar_load_only_minus_clocked_empty | 109.452 | 1.7472e+13 | 6.26443 | pJ/byte | 0.783054 | 1.00439 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 4 | shared_scalar_load_only_minus_clocked_empty | 24.4925 | 1.98997e+13 | 1.2308 | pJ/byte | 0.15385 | 1.00553 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | 16 | shared_scalar_load_only_minus_clocked_empty | 29.9224 | 2.24008e+13 | 1.33578 | pJ/byte | 0.166972 | 1.02141 | True |  |
| tensor_mma_increment | 2048 | 16 | 1 | 1 | reg_mma_minus_reg_operand_only | 41.2175 | 2.35511e+14 | 0.175013 | pJ/FLOP |  | 1.01254 | True |  |
| tensor_mma_increment | 2048 | 16 | 2 | 1 | reg_mma_minus_reg_operand_only | 41.3404 | 1.65014e+14 | 0.250527 | pJ/FLOP |  | 1.02059 | True |  |
| tensor_mma_increment | 2048 | 16 | 4 | 1 | reg_mma_minus_reg_operand_only | 68.6288 | 2.53191e+14 | 0.271056 | pJ/FLOP |  | 1.0413 | True |  |
| tensor_mma_increment | 2048 | 16 | 8 | 1 | reg_mma_minus_reg_operand_only | 28.7687 | 2.47775e+14 | 0.116108 | pJ/FLOP |  | 1.02305 | True |  |
| tensor_mma_increment | 2048 | 16 | 16 | 1 | reg_mma_minus_reg_operand_only | -14.0193 | 2.61495e+14 | -0.0536122 | pJ/FLOP |  | 1.00035 | False | negative_coefficient |
| tensor_mma_increment | 2048 | 16 | 32 | 1 | reg_mma_minus_reg_operand_only | 23.5284 | 2.5623e+14 | 0.0918256 | pJ/FLOP |  | 1.00658 | True |  |
| tensor_mma_increment | 2048 | 16 | 64 | 1 | reg_mma_minus_reg_operand_only | 9.03884 | 2.59299e+14 | 0.0348587 | pJ/FLOP |  | 1.00225 | True |  |
| tensor_register_path | 2048 | 16 | 1 | 1 | reg_mma_minus_clocked_empty | -183.24 | 2.35511e+14 | -0.778052 | pJ/FLOP |  | 1.0444 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 2 | 1 | reg_mma_minus_clocked_empty | -322.527 | 1.65014e+14 | -1.95455 | pJ/FLOP |  | 1.03355 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 4 | 1 | reg_mma_minus_clocked_empty | -225.87 | 2.53191e+14 | -0.892094 | pJ/FLOP |  | 1.01415 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 8 | 1 | reg_mma_minus_clocked_empty | -288.496 | 2.47775e+14 | -1.16435 | pJ/FLOP |  | 1.01372 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 16 | 1 | reg_mma_minus_clocked_empty | -363.713 | 2.61495e+14 | -1.3909 | pJ/FLOP |  | 1.04728 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 32 | 1 | reg_mma_minus_clocked_empty | -285.406 | 2.5623e+14 | -1.11387 | pJ/FLOP |  | 1.0201 | False | negative_coefficient |
| tensor_register_path | 2048 | 16 | 64 | 1 | reg_mma_minus_clocked_empty | -347.078 | 2.59299e+14 | -1.33852 | pJ/FLOP |  | 1.00961 | False | negative_coefficient |

## QA

- Detail rows: 42
- Invalid detail rows: 18
- negative_coefficient: 18

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
