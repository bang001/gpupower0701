# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 21.3034 | 44.8647 | 0 sectors | 1.89166e+06 | 6.28912e+06 |  | 0 | 3.5908e+08 | 2.89171e+08 | 0 | 0.001522 | 106.164 | 312.471 | 59.5683 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.2652 | 71.8104 | 0 sectors | 2.6428e+06 | 1.07113e+07 |  | 0 | 6.31455e+08 | 4.74208e+08 | 0 | 0.00168 | 0.000197 | 205.556 | 116.907 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.198869 | 6.71744e+10 sectors | 3.36167e+10 | 3.36819e+10 |  | 2.14958e+12 | 1.07977e+12 | 1.07907e+12 | 0 | 1407.74 | 66.8501 | 148.819 | 18.8466 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 50.0036 | 0.358158 | 8.3968e+09 sectors | 4.2046e+09 | 4.22413e+09 |  | 2.68698e+11 | 1.35688e+11 | 1.35484e+11 | 2.624e+08 | 49.8171 | 131.181 | 244.073 | 64.077 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.7127 | 99.0262 | 0 sectors | 0 | 140 |  | 0 | 644096 | 4480 | 0 | 0.119363 | 0.029923 | 366.646 | 99.9679 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9992 | 42.928 | 6.71744e+10 sectors | 5.45398e+06 | 1.59225e+07 |  | 2.14958e+12 | 8.83173e+08 | 7.21623e+08 | 0 | 18.5925 | 55.275 | 211.504 | 79.9824 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 88.5377 | 99.8115 | 6.71744e+10 sectors | 7.70473e+09 | 2.0602e+07 |  | 2.14958e+12 | 2.4737e+11 | 8.81044e+08 | 0 | 71.7493 | 51.9384 | 183.122 | 81.945 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.996 | 38.996 | 8.3968e+09 sectors | 2.46438e+06 | 7.45202e+06 |  | 2.68698e+11 | 4.20386e+08 | 3.39277e+08 | 2.624e+08 | 0.020917 | 57.5701 | 304.539 | 65.68 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.3554 | 2176.18 | 0 sectors | 0 | 256 |  | 0 | 1.45514e+06 | 8192 | 0 | 0.005953 | 45.0071 | 23.3373 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0645 | 9.7669 | 0 sectors | 64927 | 381876 |  | 0 | 2.03646e+07 | 1.4105e+07 | 6.56e+07 | 0.013359 | 0.00634 | 285.707 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 32.4477 | 13.8947 | 0 sectors | 0 | 400608 |  | 0 | 1.67604e+07 | 1.30592e+07 | 0 | 0.011351 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 1.74968e+10 | 27.5871 | 80.5235 | 0 sectors | 2.23788e+07 | 2.58522e+07 |  | 0 | 1.94869e+09 | 1.49594e+09 | 0 | 0.000434 | 93.4117 | 193.888 | 79.342 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 4.35868e+09 | 42.9573 | 71.3282 | 0 sectors | 7.76802e+06 | 8.37591e+06 |  | 0 | 6.51217e+08 | 5.04026e+08 | 2.624e+08 | 0.001188 | 79.9861 | 342.888 | 49.1421 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.0798 | 0 sectors | 368757 | 1.4791e+06 |  | 0 | 4.27646e+09 | 6.833e+07 | 0 | 0.019317 | 574.364 | 275.998 | 8.00205 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
