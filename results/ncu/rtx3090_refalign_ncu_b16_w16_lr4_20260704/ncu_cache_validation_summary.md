# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W16_B16 | addr_only | 16 | 16 | 0 | 20.9223 | 56.914 | 0 sectors | 1.1304e+06 | 2.10552e+06 |  | 0 | 1.56879e+08 | 1.2065e+08 | 0 | 0.002616 | 95.2857 | 308.503 | 61.8675 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.2081 | 55.7819 | 0 sectors | 1.32955e+06 | 3.83041e+06 |  | 0 | 2.77338e+08 | 1.97016e+08 | 0 | 0.001404 | 0.000311 | 245.714 | 100.052 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.16295 | 3.35872e+10 sectors | 1.68086e+10 | 1.6817e+10 |  | 1.07479e+12 | 5.39097e+11 | 5.38766e+11 | 0 | 1354.35 | 65.1248 | 152.763 | 19.5134 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.205085 | 8.3968e+09 sectors | 4.20203e+09 | 4.20532e+09 |  | 2.68698e+11 | 1.34835e+11 | 1.34736e+11 | 2.624e+08 | 110.626 | 115.313 | 258.377 | 56.2113 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9032 | 83.5306 | 0 sectors | 0 | 2796 |  | 0 | 816640 | 104960 | 0 | 0.122732 | 0.029947 | 366.646 | 99.9674 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.999 | 55.6124 | 3.35872e+10 sectors | 2.69563e+06 | 5.10181e+06 |  | 1.07479e+12 | 3.5065e+08 | 2.71369e+08 | 0 | 17.4286 | 52.7454 | 210.023 | 80.9224 | ok |  |
| l2_load_only_W16_B16 | l2_load_only | 16 | 16 | 0 | 99.999 | 54.3239 | 3.35872e+10 sectors | 2.69554e+06 | 4.70175e+06 |  | 1.07479e+12 | 3.39071e+08 | 2.58873e+08 | 0 | 16.7124 | 50.6185 | 190.272 | 92.8219 | ok |  |
| l2_mma_W16_B16 | l2_mma | 16 | 16 | 0 | 99.9975 | 53.318 | 8.3968e+09 sectors | 1.2634e+06 | 2.2245e+06 |  | 2.68698e+11 | 1.67164e+08 | 1.25442e+08 | 2.624e+08 | 0.035049 | 50.2138 | 326.145 | 59.7972 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.4948 | 117.875 | 0 sectors | 0 | 316 |  | 0 | 1.43286e+06 | 69888 | 0 | 0.005594 | 45.0065 | 23.3369 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0557 | 14.3528 | 0 sectors | 64593 | 171564 |  | 0 | 1.35562e+07 | 7.23635e+06 | 6.56e+07 | 0.022337 | 0.006346 | 285.707 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 33.9024 | 100.87 | 0 sectors | 0 | 448 |  | 0 | 2.23872e+06 | 60928 | 0 | 0.01162 | 181.815 | 327.264 | 0 | ok | l2_hit_rate_pct_out_of_range |
| shared_load_only_W16_B16 | shared_load_only | 16 | 16 | 8.73735e+09 | 26.8619 | 54.425 | 0 sectors | 3.76206e+06 | 5.01548e+06 |  | 0 | 3.83027e+08 | 2.83064e+08 | 0 | 0.000891 | 89.7858 | 194.186 | 80.0038 | ok |  |
| shared_mma_W16_B16 | shared_mma | 16 | 16 | 2.16791e+09 | 43.1969 | 61.2321 | 0 sectors | 1.26619e+06 | 1.55998e+06 |  | 0 | 1.24042e+08 | 9.29997e+07 | 2.624e+08 | 0.004209 | 47.7277 | 350.778 | 49.5403 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.5878 | 0 sectors | 364384 | 548472 |  | 0 | 4.24372e+09 | 3.8475e+07 | 0 | 0.019604 | 574.363 | 275.998 | 8.00196 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
