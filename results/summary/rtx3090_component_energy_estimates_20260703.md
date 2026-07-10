# Component Energy Estimates

## Inputs

| role | files |
|---|---|
| tensor/register | `results/raw/rtx3090_component_regression_focus_20260703.csv, results/raw/rtx3090_component_regression_fixed_iter_corrected_20260703.csv` |
| memory hierarchy | `results/raw/rtx3090_component_regression_focus_20260703.csv, results/raw/rtx3090_component_regression_fixed_iter_corrected_20260703.csv, results/raw/rtx3090_component_rate_blocks_20260703.csv` |

## Recommended Component Table

| component | estimate | unit | secondary | secondary unit | method | QA |
|---|---:|---|---:|---|---|---|
| tensor_core_increment | 0.219729 | pJ/FLOP |  |  | matched reg_mma - reg_operand_only power-rate median | positive_pairs=16/19 |
| register_operand | 8351.22 | pJ/logical-reg-op | 1.01944 | pJ/logical-operand-bit | reg_operand_only power-vs-op-rate slope | relative_rmse_pct=16.788 |
| shared_l1_increment | 49.6405 | pJ/byte | 6.20507 | pJ/bit | ordered shared<=L2<=DRAM power-rate model | relative_rmse_pct=15.426 |
| l2_increment_over_shared | 10.7842 | pJ/byte | 1.34802 | pJ/bit | ordered shared<=L2<=DRAM power-rate model | relative_rmse_pct=15.426 |
| dram_increment_over_l2 | 169.443 | pJ/byte | 21.1804 | pJ/bit | ordered shared<=L2<=DRAM power-rate model | relative_rmse_pct=15.426 |

## Cumulative Memory Paths

| path | estimate | unit | pJ/bit |
|---|---:|---|---:|
| shared_l1_cumulative_path | 49.6405 | pJ/byte | 6.20507 |
| l2_hit_cumulative_path | 60.4247 | pJ/byte | 7.55309 |
| dram_stream_cumulative_path | 229.868 | pJ/byte | 28.7335 |

## QA

- Tensor pairs: 16/19 positive, all-pair power median 0.219729 pJ/FLOP, positive-pair median 0.237645 pJ/FLOP.
- Register fit: 35 rows, RMSE 14.6807 W, relative RMSE 16.788%.
- Memory ordered fit: 99 rows, RMSE 24.3989 W, relative RMSE 15.426%, active-set iterations 4.

## Interpretation Limits

These are effective microbenchmark coefficients based on NVML board energy and static expected traffic. The memory numbers include load instruction/control/stall effects and must not be described as pure SRAM/L2/DRAM bitcell energy until NCU actual L1/L2/DRAM traffic and stall counters are joined.
