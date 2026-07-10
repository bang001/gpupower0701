# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B8 | addr_only | 64 | 8 | 0 | 17.378 | 48.4002 | 0 sectors | 305415 | 1.21625e+06 |  | 0 | 7.53094e+07 | 5.38028e+07 | 0 | 0.004921 | 92.1426 | 291.629 | 15.9434 | ok |  |
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | 17.7973 | 50.1892 | 0 sectors | 416068 | 1.9008e+06 |  | 0 | 1.23659e+08 | 8.15428e+07 | 0 | 0.001038 | 0.000305 | 245.714 | 22.7584 | ok |  |
| dram_load_only_W8192_B8 | dram_load_only | 8192 | 8 | 0 | 49.9998 | 0.097336 | 1.67936e+10 sectors | 8.39993e+09 | 8.40928e+09 |  | 5.37395e+11 | 2.69366e+11 | 2.69241e+11 | 0 | 532.96 | 64.6744 | 150.325 | 10.6391 | ok |  |
| dram_mma_W8192_B8 | dram_mma | 8192 | 8 | 0 | 49.9999 | 0.177871 | 4.1984e+09 sectors | 2.10049e+09 | 2.10512e+09 |  | 1.34349e+11 | 6.74913e+10 | 6.74259e+10 | 1.312e+08 | 108.897 | 95.8253 | 236.899 | 14.375 | ok |  |
| empty_W64_B8 | empty | 64 | 8 | 0 | 17.9878 | 107.363 | 0 sectors | 0 | 172 |  | 0 | 452864 | 11264 | 0 | 0.097706 | 0.028532 | 366.642 | 16.6655 | ok | l2_hit_rate_pct_out_of_range |
| global_l1_load_only_W64_B8 | global_l1_load_only | 64 | 8 | 0 | 95.8994 | 98.9857 | 1.67936e+10 sectors | 6.89498e+08 | 4.53512e+06 |  | 5.37395e+11 | 2.22496e+10 | 1.88539e+08 | 0 | 33.4409 | 50.3459 | 198.398 | 18.2366 | ok |  |
| l2_load_only_W64_B8 | l2_load_only | 64 | 8 | 0 | 96.341 | 98.5101 | 1.67936e+10 sectors | 6.15366e+08 | 6.04338e+06 |  | 5.37395e+11 | 1.99301e+10 | 2.3684e+08 | 0 | 32.357 | 51.5592 | 181.037 | 24.4212 | ok |  |
| l2_mma_W64_B8 | l2_mma | 64 | 8 | 0 | 99.9957 | 39.9509 | 4.1984e+09 sectors | 594589 | 2.32609e+06 |  | 1.34349e+11 | 1.27402e+08 | 9.667e+07 | 1.312e+08 | 0.027353 | 50.4856 | 305.713 | 14.6322 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 28.6063 | 76.7619 | 0 sectors | 0 | 7584 |  | 0 | 1.89069e+06 | 550016 | 0 | 0.005566 | 45.0063 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0383 | 86.4696 | 0 sectors | 0 | 223120 |  | 0 | 9.27734e+06 | 7.3303e+06 | 6.56e+07 | 0.012136 | 0.006342 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.3676 | 40.358 | 0 sectors | 65021 | 381472 |  | 0 | 2.05792e+07 | 1.36966e+07 | 0 | 0.012029 | 181.816 | 327.263 | 0 | ok |  |
| shared_load_only_W64_B8 | shared_load_only | 64 | 8 | 4.29312e+09 | 25.466 | 56.3324 | 0 sectors | 2.5178e+06 | 3.40301e+06 |  | 0 | 2.49403e+08 | 1.77306e+08 | 0 | 0.000923 | 85.516 | 188.19 | 16.7503 | ok |  |
| shared_mma_W64_B8 | shared_mma | 64 | 8 | 1.07464e+09 | 42.9051 | 55.2827 | 0 sectors | 1.03814e+06 | 1.3984e+06 |  | 0 | 1.00903e+08 | 7.48334e+07 | 1.312e+08 | 0.003443 | 47.5636 | 332.861 | 11.7229 | ok |  |
| store_only_W64_B8 | store_only | 64 | 8 | 0 | 99.9897 | 100.242 | 0 sectors | 0 | 222264 |  | 0 | 2.10847e+09 | 7.7129e+06 | 0 | 0.015243 | 122.892 | 272.795 | 8.66569 | ok | l2_hit_rate_pct_out_of_range |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
