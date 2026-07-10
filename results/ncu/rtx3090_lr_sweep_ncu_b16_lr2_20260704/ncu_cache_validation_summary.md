# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 20.9223 | 44.0914 | 0 sectors | 756085 | 2.41699e+06 |  | 0 | 1.36303e+08 | 1.10907e+08 | 0 | 0.005466 | 75.9687 | 338.759 | 54.4137 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.17 | 40.0279 | 0 sectors | 1.13116e+06 | 5.25099e+06 |  | 0 | 2.91734e+08 | 2.27401e+08 | 0 | 0.001702 | 0.000408 | 337.037 | 79.5372 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9996 | 0.380448 | 1.67936e+10 sectors | 8.41437e+09 | 8.42298e+09 |  | 5.37395e+11 | 2.70591e+11 | 2.70254e+11 | 0 | 1286.75 | 61.9263 | 160.012 | 20.4419 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9998 | 0.161192 | 8.3968e+09 sectors | 4.2013e+09 | 4.20711e+09 |  | 2.68698e+11 | 1.34828e+11 | 1.34756e+11 | 2.624e+08 | 577.263 | 86.9586 | 268.62 | 28.0013 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9413 | 35.4917 | 0 sectors | 0 | 41416 |  | 0 | 1.98816e+06 | 1.34246e+06 | 0 | 0.148644 | 0.029957 | 366.646 | 99.9675 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9988 | 40.1891 | 1.67936e+10 sectors | 1.32988e+06 | 4.64004e+06 |  | 5.37395e+11 | 2.42085e+08 | 2.02404e+08 | 0 | 13.3754 | 44.2146 | 201.369 | 97.0667 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 87.719 | 99.6563 | 1.67936e+10 sectors | 2.06371e+09 | 5.92324e+06 |  | 5.37395e+11 | 6.62675e+10 | 2.50804e+08 | 0 | 68.2438 | 47.6743 | 221.057 | 79.2294 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.6647 | 96.4844 | 8.3968e+09 sectors | 2.91292e+07 | 3.51498e+06 |  | 2.68698e+11 | 1.08675e+09 | 1.6223e+08 | 2.624e+08 | 0.845035 | 40.073 | 352.186 | 52.0286 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.0592 | 112.921 | 0 sectors | 0 | 154336 |  | 0 | 6.40749e+06 | 5.14726e+06 | 0 | 0.0058 | 45.0065 | 23.3371 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0557 | 38.4063 | 0 sectors | 129103 | 674576 |  | 0 | 3.60718e+07 | 2.59886e+07 | 6.56e+07 | 0.012865 | 0.006348 | 285.707 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 34.0418 | 42.8121 | 0 sectors | 0 | 95028 |  | 0 | 5.43914e+06 | 3.22701e+06 | 0 | 0.011779 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 4.36716e+09 | 27.2387 | 43.3933 | 0 sectors | 2.17536e+06 | 5.04216e+06 |  | 0 | 2.8119e+08 | 2.28906e+08 | 0 | 0.001059 | 98.7711 | 176.027 | 104.502 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 4.39311e+09 | 43.1119 | 47.5384 | 0 sectors | 2.47066e+06 | 4.34776e+06 |  | 0 | 2.65773e+08 | 2.13247e+08 | 2.624e+08 | 0.00151 | 110.123 | 321.211 | 49.406 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9898 | 99.472 | 0 sectors | 0 | 669228 |  | 0 | 4.22432e+09 | 2.27649e+07 | 0 | 0.022699 | 574.369 | 275.998 | 8.00165 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
