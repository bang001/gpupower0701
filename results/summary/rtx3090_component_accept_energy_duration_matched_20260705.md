# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_component_accept_energy_duration_20260705.csv` |
| acceptance CSV | `results/summary/rtx3090_component_sep_ncu_scalarshared_acceptance_20260705.csv` |
| min elapsed (s) | 1 |
| max elapsed ratio | 1.35 |

## Component Summary

| component | rows | estimate unit | min | median | mean | max | stdev | median pJ/bit | pJ/bit min-max |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| dram_cg_stream_path | 3 | pJ/byte | 17.0118 | 35.8406 | 33.7321 | 48.344 | 15.7722 | 4.48008 | 2.12647 - 6.043 |
| global_l1_hit_path | 4 | pJ/byte | 0.161142 | 3.59549 | 2.84278 | 4.01899 | 1.81584 | 0.449436 | 0.0201428 - 0.502374 |
| l2_hit_cg_path | 5 | pJ/byte | 4.37316 | 6.38041 | 10.1722 | 20.3108 | 6.71776 | 0.797551 | 0.546645 - 2.53885 |
| shared_l1_scalar_path | 6 | pJ/byte | 0.120023 | 1.78461 | 2.30002 | 6.26443 | 2.12819 | 0.223076 | 0.0150028 - 0.783054 |

## Detail Rows

| component | W_SM (KiB) | blocks/SM | load_repeat | pair | delta_E (J) | denominator | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---|---|
| dram_cg_stream_path | 8192 | 16 | 1 | dram_cg_load_only_minus_clocked_empty | 139.614 | 2.88793e+12 | 48.344 | pJ/byte | 6.043 | 1.0358 | True |  |
| dram_cg_stream_path | 8192 | 16 | 4 | dram_cg_load_only_minus_clocked_empty | 103.648 | 2.89192e+12 | 35.8406 | pJ/byte | 4.48008 | 1.00092 | True |  |
| dram_cg_stream_path | 8192 | 16 | 16 | dram_cg_load_only_minus_clocked_empty | 49.0646 | 2.88416e+12 | 17.0118 | pJ/byte | 2.12647 | 1.0162 | True |  |
| global_l1_hit_path | 16 | 16 | 1 | global_l1_load_only_minus_clocked_empty | 37.6614 | 1.14398e+13 | 3.29214 | pJ/byte | 0.411518 | 1.18122 | True |  |
| global_l1_hit_path | 16 | 16 | 4 | global_l1_load_only_minus_clocked_empty | 52.7419 | 1.31232e+13 | 4.01899 | pJ/byte | 0.502374 | 1.01833 | True |  |
| global_l1_hit_path | 16 | 16 | 16 | global_l1_load_only_minus_clocked_empty | 2.27851 | 1.41397e+13 | 0.161142 | pJ/byte | 0.0201428 | 1.01896 | True |  |
| global_l1_hit_path | 64 | 16 | 1 | global_l1_load_only_minus_clocked_empty | 37.9535 | 9.73455e+12 | 3.89884 | pJ/byte | 0.487355 | 1.00383 | True |  |
| global_l1_hit_path | 64 | 16 | 4 | global_l1_load_only_minus_clocked_empty | -17.3904 | 1.07331e+13 | -1.62026 | pJ/byte | -0.202533 | 1.013 | False | negative_coefficient |
| global_l1_hit_path | 64 | 16 | 16 | global_l1_load_only_minus_clocked_empty | -56.2443 | 1.12223e+13 | -5.01185 | pJ/byte | -0.626482 | 1.01186 | False | negative_coefficient |
| l2_hit_cg_path | 16 | 16 | 1 | l2_cg_load_only_minus_clocked_empty | 32.1615 | 7.35429e+12 | 4.37316 | pJ/byte | 0.546645 | 1.19617 | True |  |
| l2_hit_cg_path | 16 | 16 | 4 | l2_cg_load_only_minus_clocked_empty | 47.3856 | 7.42673e+12 | 6.38041 | pJ/byte | 0.797551 | 1.01716 | True |  |
| l2_hit_cg_path | 16 | 16 | 16 | l2_cg_load_only_minus_clocked_empty | -1.75688 | 7.17721e+12 | -0.244785 | pJ/byte | -0.0305982 | 1.02325 | False | negative_coefficient |
| l2_hit_cg_path | 64 | 16 | 1 | l2_cg_load_only_minus_clocked_empty | 160.624 | 7.90828e+12 | 20.3108 | pJ/byte | 2.53885 | 1.01459 | True |  |
| l2_hit_cg_path | 64 | 16 | 4 | l2_cg_load_only_minus_clocked_empty | 110.397 | 8.03291e+12 | 13.7431 | pJ/byte | 1.71789 | 1.00483 | True |  |
| l2_hit_cg_path | 64 | 16 | 16 | l2_cg_load_only_minus_clocked_empty | 48.1164 | 7.94853e+12 | 6.0535 | pJ/byte | 0.756688 | 1.00813 | True |  |
| shared_l1_scalar_path | 16 | 16 | 1 | shared_scalar_load_only_minus_clocked_empty | 41.0971 | 1.84008e+13 | 2.23344 | pJ/byte | 0.27918 | 1.21207 | True |  |
| shared_l1_scalar_path | 16 | 16 | 4 | shared_scalar_load_only_minus_clocked_empty | 52.2213 | 1.99651e+13 | 2.61563 | pJ/byte | 0.326953 | 1.0091 | True |  |
| shared_l1_scalar_path | 16 | 16 | 16 | shared_scalar_load_only_minus_clocked_empty | 2.58609 | 2.15467e+13 | 0.120023 | pJ/byte | 0.0150028 | 1.0173 | True |  |
| shared_l1_scalar_path | 64 | 16 | 1 | shared_scalar_load_only_minus_clocked_empty | 109.452 | 1.7472e+13 | 6.26443 | pJ/byte | 0.783054 | 1.00439 | True |  |
| shared_l1_scalar_path | 64 | 16 | 4 | shared_scalar_load_only_minus_clocked_empty | 24.4925 | 1.98997e+13 | 1.2308 | pJ/byte | 0.15385 | 1.00553 | True |  |
| shared_l1_scalar_path | 64 | 16 | 16 | shared_scalar_load_only_minus_clocked_empty | 29.9224 | 2.24008e+13 | 1.33578 | pJ/byte | 0.166972 | 1.02141 | True |  |

## QA

- Detail rows: 21
- Invalid detail rows: 3
- negative_coefficient: 3

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
