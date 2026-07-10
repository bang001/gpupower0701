# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W16_B16 | addr_only | 16 | 16 | 0 | 20.9992 | 91.3884 | 0 sectors | 752634 | 1.8307e+06 |  | 0 | 1.18478e+08 | 9.69159e+07 | 0 | 0.008692 | 61.3722 | 338.339 | 56.4884 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 20.9407 | 53.5401 | 0 sectors | 1.8484e+06 | 5.59589e+06 |  | 0 | 3.80099e+08 | 2.81396e+08 | 0 | 0.0012755 | 0.0002935 | 378.948 | 33.6617 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9998 | 0.149232 | 1.67936e+10 sectors | 8.40398e+09 | 8.41158e+09 |  | 5.37398e+11 | 2.69637e+11 | 2.69477e+11 | 0 | 1174.04 | 57.0702 | 186.428 | 21.0976 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.197892 | 1.67936e+10 sectors | 8.40247e+09 | 8.41052e+09 |  | 5.37398e+11 | 2.69524e+11 | 2.69385e+11 | 5.248e+08 | 1310.04 | 67.6018 | 315.012 | 14.4402 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9602 | 96.4205 | 0 sectors | 0 | 336 |  | 0 | 1.33402e+06 | 72196 | 0 | 0.148327 | 0.0300095 | 366.648 | 99.969 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9991 | 54.7983 | 1.67936e+10 sectors | 1.92749e+06 | 4.06906e+06 |  | 5.37398e+11 | 2.54962e+08 | 2.08017e+08 | 0 | 10.6815 | 39.7317 | 201.831 | 98.2999 | ok |  |
| l2_load_only_W16_B16 | l2_load_only | 16 | 16 | 0 | 99.9993 | 62.2679 | 1.67936e+10 sectors | 1.14589e+06 | 3.47518e+06 |  | 5.37398e+11 | 1.97359e+08 | 1.59504e+08 | 0 | 12.5276 | 42.9406 | 242.241 | 86.3388 | ok |  |
| l2_mma_W16_B16 | l2_mma | 16 | 16 | 0 | 99.9991 | 54.3918 | 1.67936e+10 sectors | 1.57679e+06 | 3.8139e+06 |  | 5.37398e+11 | 2.40224e+08 | 1.91882e+08 | 5.248e+08 | 0.061111 | 54.3586 | 441.431 | 32.3381 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 28.8314 | 99.0296 | 0 sectors | 0 | 800 |  | 0 | 2.90024e+06 | 459262 | 0 | 0.0079145 | 45.0084 | 23.3384 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.109 | 6.64121 | 0 sectors | 129756 | 1.34163e+06 |  | 0 | 5.90226e+07 | 4.66583e+07 | 1.312e+08 | 0.0120605 | 0.0081745 | 285.709 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 32.8024 | 187.488 | 0 sectors | 0 | 136336 |  | 0 | 9.05941e+06 | 4.71866e+06 | 0 | 0.011163 | 181.818 | 327.262 | 0 | ok | l2_hit_rate_pct_out_of_range |
| shared_load_only_W16_B16 | shared_load_only | 16 | 16 | 4.35978e+09 | 26.7796 | 41.512 | 0 sectors | 2.42876e+06 | 4.12951e+06 |  | 0 | 2.75224e+08 | 2.10078e+08 | 0 | 0.001225 | 88.8188 | 180.438 | 102.561 | ok |  |
| shared_mma_W16_B16 | shared_mma | 16 | 16 | 4.36155e+09 | 42.6386 | 60.6076 | 0 sectors | 2.0667e+06 | 3.52972e+06 |  | 0 | 2.38104e+08 | 1.83885e+08 | 5.248e+08 | 0.002415 | 68.7987 | 336.329 | 49.4793 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9809 | 98.7401 | 0 sectors | 738470 | 1.82441e+06 |  | 0 | 8.5155e+09 | 9.60237e+07 | 0 | 0.031357 | 574.368 | 275.999 | 8.00099 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
