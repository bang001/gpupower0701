# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | sass | 0 | 0 | 20.9032 | 54.2557 | 0 sectors | 1.16481e+06 | 2.17401e+06 | 0 | 0 | 1.6519e+08 | 1.2457e+08 | 0 | 0.002732 | 95.805 | 308.067 | 62.238 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | sass | 0 | 0 | 20.9985 | 56.3586 | 0 sectors | 1.32759e+06 | 3.51008e+06 | 0 | 0 | 2.67718e+08 | 1.86897e+08 | 0 | 0.002394 | 0.000313 | 245.714 | 100.16 | ok |  |
| dram_cg_load_only_W8192_B16 | dram_cg_load_only | 8192 | 16 | 0 | sass | 0 | 0 | 7e-06 | 0.155081 | 1.67936e+10 sectors | 1.68051e+10 | 1.6815e+10 | 0 | 5.37395e+11 | 5.38918e+11 | 5.38632e+11 | 0 | 1779.75 | 74.074 | 236.07 | 10.8265 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | sass | 0 | 0 | 49.9997 | 0.164232 | 3.35872e+10 sectors | 1.6808e+10 | 1.68164e+10 | 0 | 1.07479e+12 | 5.39033e+11 | 5.38713e+11 | 0 | 1359.58 | 65.1162 | 152.807 | 19.4624 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | sass | 0 | 0 | 49.9999 | 0.227064 | 8.3968e+09 sectors | 4.20224e+09 | 4.20533e+09 | 0 | 2.68698e+11 | 1.34852e+11 | 1.34747e+11 | 2.624e+08 | 109.676 | 115.367 | 258.464 | 56.3172 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | sass | 0 | 0 | 21.1128 | 22.4714 | 0 sectors | 0 | 66228 | 0 | 0 | 2.78954e+06 | 2.13427e+06 | 0 | 0.120952 | 0.029902 | 366.646 | 99.9671 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | sass | 0 | 0 | 99.999 | 54.1408 | 3.35872e+10 sectors | 2.90087e+06 | 5.08281e+06 | 0 | 1.07479e+12 | 3.60889e+08 | 2.77051e+08 | 0 | 17.4288 | 52.7527 | 210.022 | 80.9236 | ok |  |
| l2_cg_load_only_W64_B16 | l2_cg_load_only | 64 | 16 | 0 | sass | 0 | 0 | 6e-06 | 99.9489 | 1.67936e+10 sectors | 1.67976e+10 | 9.935e+06 | 0 | 5.37395e+11 | 5.37952e+11 | 5.0709e+08 | 0 | 868.648 | 52.6304 | 309.002 | 15.4243 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | sass | 0 | 0 | 88.3624 | 99.7798 | 3.35872e+10 sectors | 3.91106e+09 | 6.3156e+06 | 0 | 1.07479e+12 | 1.25435e+11 | 3.10626e+08 | 0 | 70.7878 | 50.5006 | 188.87 | 80.8902 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | sass | 0 | 0 | 99.9977 | 53.0073 | 8.3968e+09 sectors | 1.2019e+06 | 2.44801e+06 | 0 | 2.68698e+11 | 1.68159e+08 | 1.30211e+08 | 2.624e+08 | 0.0307 | 50.2158 | 325.969 | 59.8022 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | sass | 0 | 0 | 30.0087 | 11.0823 | 0 sectors | 52820 | 182964 | 0 | 0 | 1.30283e+07 | 9.02976e+06 | 0 | 0.00567 | 45.0092 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | sass | 0 | 0 | 47.0732 | 84.4251 | 0 sectors | 0 | 179884 | 0 | 0 | 9.41805e+06 | 5.83514e+06 | 6.56e+07 | 0.012121 | 0.00634 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | sass | 0 | 0 | 32.3955 | 91.0645 | 0 sectors | 0 | 162384 | 0 | 0 | 9.15078e+06 | 5.3536e+06 | 0 | 0.01213 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 8.39688e+09 | sass | 4.1984e+09 | 83968 | 27.1429 | 54.4387 | 0 sectors | 4.35606e+06 | 5.58224e+06 | 5.37401e+11 | 0 | 4.15986e+08 | 3.13143e+08 | 0 | 0.000518 | 89.7825 | 194.147 | 79.9969 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 2.09928e+09 | sass | 1.0496e+09 | 83968 | 43.3537 | 55.5801 | 0 sectors | 1.64764e+06 | 2.07438e+06 | 1.34354e+11 | 0 | 1.55392e+08 | 1.19065e+08 | 2.624e+08 | 0.00237 | 47.73 | 350.526 | 49.545 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | sass | 0 | 0 | 99.9818 | 99.6937 | 0 sectors | 364677 | 428076 | 0 | 0 | 4.23991e+09 | 3.48225e+07 | 0 | 0.019253 | 574.364 | 275.998 | 8.00195 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
