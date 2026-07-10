# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 20.7889 | 33.8099 | 0 sectors | 359148 | 1.83892e+06 |  | 0 | 8.91387e+07 | 7.79581e+07 | 0 | 0.007147 | 61.4468 | 338.272 | 56.4985 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.3796 | 61.1771 | 0 sectors | 708866 | 4.89669e+06 |  | 0 | 2.37137e+08 | 1.97969e+08 | 0 | 0.002486 | 0.000589 | 378.947 | 33.8852 | ok |  |
| dram_cg_load_only_W8192_B16 | dram_cg_load_only | 8192 | 16 | 0 | 2.5e-05 | 0.378531 | 4.1984e+09 sectors | 4.20475e+09 | 4.21232e+09 |  | 1.34349e+11 | 1.35236e+11 | 1.35103e+11 | 0 | 1656.51 | 68.9641 | 275.329 | 11.3215 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9996 | 0.171256 | 8.3968e+09 sectors | 4.20222e+09 | 4.20605e+09 |  | 2.68698e+11 | 1.3487e+11 | 1.34778e+11 | 0 | 1176.28 | 57.1518 | 186.35 | 21.7572 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.353387 | 8.3968e+09 sectors | 4.20584e+09 | 4.21262e+09 |  | 2.68698e+11 | 1.35308e+11 | 1.3515e+11 | 2.624e+08 | 1329.51 | 67.5946 | 314.855 | 14.3413 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 21.1128 | 105.833 | 0 sectors | 0 | 172 |  | 0 | 663264 | 30976 | 0 | 0.12006 | 0.029854 | 366.646 | 99.9675 | ok | l2_hit_rate_pct_out_of_range |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9976 | 57.2335 | 8.3968e+09 sectors | 1.38897e+06 | 3.15354e+06 |  | 2.68698e+11 | 1.88662e+08 | 1.57051e+08 | 0 | 10.7002 | 39.7449 | 201.836 | 98.3123 | ok |  |
| l2_cg_load_only_W64_B16 | l2_cg_load_only | 64 | 16 | 0 | 2.6e-05 | 99.8384 | 4.1984e+09 sectors | 4.20083e+09 | 6.56124e+06 |  | 1.34349e+11 | 1.34689e+11 | 3.29848e+08 | 0 | 649.241 | 48.0744 | 358.509 | 17.6593 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 87.5195 | 99.5277 | 8.3968e+09 sectors | 1.0496e+09 | 4.66752e+06 |  | 2.68698e+11 | 3.37762e+10 | 2.2699e+08 | 0 | 62.4076 | 43.1576 | 240.713 | 76.3983 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 85.9738 | 98.9159 | 8.3968e+09 sectors | 1.18048e+09 | 6.63057e+06 |  | 2.68698e+11 | 3.81725e+10 | 3.96131e+08 | 2.624e+08 | 41.334 | 54.2575 | 438.999 | 29.5225 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 28.7108 | 154.229 | 0 sectors | 0 | 364576 |  | 0 | 1.31386e+07 | 1.17631e+07 | 0 | 0.005779 | 45.0068 | 23.3374 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0035 | 26.6224 | 0 sectors | 65413 | 687404 |  | 0 | 3.03355e+07 | 2.38893e+07 | 6.56e+07 | 0.01287 | 0.006341 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.8293 | 15.2734 | 0 sectors | 64982 | 255824 |  | 0 | 1.66e+07 | 1.19724e+07 | 0 | 0.023832 | 181.816 | 327.263 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 2.17943e+09 | 26.5679 | 31.3253 | 0 sectors | 3.9645e+06 | 4.7232e+06 |  | 0 | 3.45188e+08 | 2.71321e+08 | 0 | 0.001878 | 88.7903 | 180.41 | 102.561 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 2.18083e+09 | 41.973 | 70.3511 | 0 sectors | 2.4679e+06 | 3.3579e+06 |  | 0 | 2.29749e+08 | 1.84773e+08 | 2.624e+08 | 0.00251 | 68.7896 | 336.06 | 49.4835 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9898 | 99.4044 | 0 sectors | 0 | 774456 |  | 0 | 4.22704e+09 | 2.61541e+07 | 0 | 0.022657 | 574.369 | 275.999 | 8.00148 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
