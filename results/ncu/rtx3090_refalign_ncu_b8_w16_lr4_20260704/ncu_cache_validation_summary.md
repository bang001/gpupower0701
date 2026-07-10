# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W16_B8 | addr_only | 16 | 8 | 0 | 17.4924 | 53.3456 | 0 sectors | 305636 | 1.09407e+06 |  | 0 | 7.07034e+07 | 4.98106e+07 | 0 | 0.002314 | 92.169 | 291.704 | 15.964 | ok |  |
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | 16.9588 | 52.1808 | 0 sectors | 413470 | 1.75951e+06 |  | 0 | 1.20136e+08 | 7.63891e+07 | 0 | 0.0011 | 0.000306 | 245.714 | 22.735 | ok |  |
| dram_load_only_W8192_B8 | dram_load_only | 8192 | 8 | 0 | 49.9998 | 0.09012 | 1.67936e+10 sectors | 8.39985e+09 | 8.40509e+09 |  | 5.37395e+11 | 2.69219e+11 | 2.69098e+11 | 0 | 531.937 | 64.6671 | 150.325 | 10.608 | ok |  |
| dram_mma_W8192_B8 | dram_mma | 8192 | 8 | 0 | 49.9999 | 0.161073 | 4.1984e+09 sectors | 2.10041e+09 | 2.10284e+09 |  | 1.34349e+11 | 6.74074e+10 | 6.7351e+10 | 1.312e+08 | 109.571 | 95.8531 | 236.906 | 14.3993 | ok |  |
| empty_W64_B8 | empty | 64 | 8 | 0 | 18.1021 | 94.3848 | 0 sectors | 0 | 168 |  | 0 | 459328 | 11648 | 0 | 0.17077 | 0.028512 | 366.641 | 16.6655 | ok |  |
| global_l1_load_only_W16_B8 | global_l1_load_only | 16 | 8 | 0 | 99.9984 | 52.1133 | 1.67936e+10 sectors | 1.09275e+06 | 2.64313e+06 |  | 5.37395e+11 | 1.72617e+08 | 1.22249e+08 | 0 | 16.3466 | 50.4366 | 198.788 | 19.0904 | ok |  |
| l2_load_only_W16_B8 | l2_load_only | 16 | 8 | 0 | 99.9984 | 50.1356 | 1.67936e+10 sectors | 1.07369e+06 | 2.75968e+06 |  | 5.37395e+11 | 1.73493e+08 | 1.25231e+08 | 0 | 16.3257 | 51.9216 | 181.144 | 25.6135 | ok |  |
| l2_mma_W16_B8 | l2_mma | 16 | 8 | 0 | 99.9982 | 61.3065 | 4.1984e+09 sectors | 400922 | 1.33126e+06 |  | 1.34349e+11 | 8.19247e+07 | 5.71922e+07 | 1.312e+08 | 0.012776 | 50.5101 | 305.518 | 14.5299 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.0418 | 17.4543 | 0 sectors | 0 | 201488 |  | 0 | 7.91277e+06 | 6.6784e+06 | 0 | 0.006 | 45.0058 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.047 | 100.618 | 0 sectors | 0 | 688 |  | 0 | 1.98269e+06 | 153088 | 6.56e+07 | 0.0119 | 0.006342 | 285.708 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.4286 | 14.1166 | 0 sectors | 64858 | 222652 |  | 0 | 1.54002e+07 | 9.02144e+06 | 0 | 0.012667 | 181.816 | 327.263 | 0 | ok |  |
| shared_load_only_W16_B8 | shared_load_only | 16 | 8 | 4.29345e+09 | 25.3005 | 56.1641 | 0 sectors | 1.57126e+06 | 2.64056e+06 |  | 0 | 1.93739e+08 | 1.29026e+08 | 0 | 0.000985 | 85.544 | 188.188 | 16.7408 | ok |  |
| shared_mma_W16_B8 | shared_mma | 16 | 8 | 1.07459e+09 | 41.9948 | 55.4938 | 0 sectors | 329839 | 806176 |  | 0 | 5.22523e+07 | 3.72239e+07 | 1.312e+08 | 0.003656 | 47.5888 | 332.712 | 11.7086 | ok |  |
| store_only_W64_B8 | store_only | 64 | 8 | 0 | 99.9897 | 100.241 | 0 sectors | 0 | 221096 |  | 0 | 2.10839e+09 | 7.71853e+06 | 0 | 0.015622 | 123.084 | 272.324 | 8.89231 | ok | l2_hit_rate_pct_out_of_range |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
