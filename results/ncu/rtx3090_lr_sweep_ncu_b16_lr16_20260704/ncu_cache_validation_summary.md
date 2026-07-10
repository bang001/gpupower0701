# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 21.0938 | 51.5442 | 0 sectors | 7.54935e+06 | 1.84279e+07 |  | 0 | 1.22771e+09 | 9.72223e+08 | 0 | 0.00081 | 112.849 | 314.582 | 57.2273 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.7226 | 50.8593 | 0 sectors | 6.66507e+06 | 2.62907e+07 |  | 0 | 1.70826e+09 | 1.27588e+09 | 0 | 0.000507 | 0.000114 | 175 | 127.078 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.162613 | 1.34349e+11 sectors | 6.72315e+10 | 6.7269e+10 |  | 4.29916e+12 | 2.15625e+12 | 2.15496e+12 | 0 | 1422.35 | 67.781 | 146.816 | 18.6851 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 50.3529 | 0.894016 | 8.3968e+09 sectors | 4.18189e+09 | 4.18392e+09 |  | 2.68698e+11 | 1.35164e+11 | 1.34501e+11 | 2.624e+08 | 24.1148 | 140.478 | 235.493 | 67.4798 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.7317 | 1649.58 | 0 sectors | 0 | 68700 |  | 0 | 2.84768e+06 | 2.21363e+06 | 0 | 0.125841 | 0.029956 | 366.647 | 99.7501 | ok | l2_hit_rate_pct_out_of_range |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9989 | 46.0291 | 1.34349e+11 sectors | 1.46848e+07 | 3.59645e+07 |  | 4.29916e+12 | 2.11509e+09 | 1.72224e+09 | 0 | 19.2038 | 56.5945 | 212.32 | 79.4641 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 88.5489 | 99.6526 | 1.34349e+11 sectors | 1.53993e+10 | 4.77299e+07 |  | 4.29916e+12 | 4.94725e+11 | 2.18814e+09 | 0 | 72.8972 | 52.7626 | 180.168 | 82.5905 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.9895 | 31.7845 | 8.3968e+09 sectors | 7.80896e+06 | 1.13344e+07 |  | 2.68698e+11 | 8.96759e+08 | 6.78301e+08 | 2.624e+08 | 0.017508 | 62.1688 | 290.235 | 69.4056 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.007 | 81.7372 | 0 sectors | 0 | 10612 |  | 0 | 1.8505e+06 | 497536 | 0 | 0.00553 | 45.0064 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0906 | 15.6733 | 0 sectors | 0 | 331052 |  | 0 | 1.26813e+07 | 1.06367e+07 | 6.56e+07 | 0.012251 | 0.006339 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 32.7439 | 15.1875 | 0 sectors | 0 | 516024 |  | 0 | 1.90196e+07 | 1.67186e+07 | 0 | 0.011491 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 3.50098e+10 | 27.5697 | 31.5735 | 0 sectors | 6.10192e+07 | 6.20522e+07 |  | 0 | 5.01969e+09 | 3.81552e+09 | 0 | 0.000137 | 95.2839 | 193.757 | 78.8323 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 8.74803e+09 | 43.2644 | 46.8119 | 0 sectors | 6.58629e+06 | 1.01468e+07 |  | 0 | 6.56351e+08 | 5.24777e+08 | 2.624e+08 | 0.000712 | 103.793 | 336.77 | 48.2342 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.3822 | 0 sectors | 395954 | 973092 |  | 0 | 4.25795e+09 | 5.26223e+07 | 0 | 0.019516 | 574.364 | 275.998 | 8.00192 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
