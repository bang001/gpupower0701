# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 21.189 | 23.9838 | 0 sectors | 621918 | 2.40798e+06 |  | 0 | 1.26412e+08 | 1.07884e+08 | 0 | 0.015923 | 61.4188 | 338.294 | 56.5402 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.0175 | 37.9636 | 0 sectors | 953142 | 5.34948e+06 |  | 0 | 2.73664e+08 | 2.23168e+08 | 0 | 0.002508 | 0.000589 | 378.947 | 33.827 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9995 | 0.232827 | 8.3968e+09 sectors | 4.2117e+09 | 4.21706e+09 |  | 2.68698e+11 | 1.35775e+11 | 1.3549e+11 | 0 | 1153.79 | 57.1303 | 186.467 | 21.4318 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.141304 | 8.3968e+09 sectors | 4.20663e+09 | 4.21312e+09 |  | 2.68698e+11 | 1.35365e+11 | 1.35188e+11 | 2.624e+08 | 1286.2 | 67.4998 | 315.258 | 13.8687 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9223 | 3.35466 | 0 sectors | 0 | 589032 |  | 0 | 1.95043e+07 | 1.8849e+07 | 0 | 0.123155 | 0.030031 | 366.646 | 99.966 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9891 | 28.7492 | 8.3968e+09 sectors | 8.9994e+06 | 9.63347e+06 |  | 2.68698e+11 | 8.8162e+08 | 6.70604e+08 | 0 | 10.7234 | 39.7414 | 201.83 | 98.2817 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 87.5108 | 99.3572 | 8.3968e+09 sectors | 1.05113e+09 | 6.10492e+06 |  | 2.68698e+11 | 3.38818e+10 | 3.07247e+08 | 0 | 62.1666 | 43.157 | 240.72 | 76.3713 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 85.9696 | 98.8443 | 8.3968e+09 sectors | 1.18225e+09 | 8.20776e+06 |  | 2.68698e+11 | 3.82069e+10 | 4.62374e+08 | 2.624e+08 | 41.4743 | 54.2526 | 439.002 | 29.5025 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.2422 | 5.55649 | 0 sectors | 0 | 759104 |  | 0 | 2.60821e+07 | 2.4529e+07 | 0 | 0.005574 | 45.0063 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.1254 | 238.74 | 0 sectors | 0 | 45308 |  | 0 | 3.48902e+06 | 1.54944e+06 | 6.56e+07 | 0.012471 | 0.006341 | 285.708 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.7857 | 8.69074 | 0 sectors | 0 | 729564 |  | 0 | 2.59296e+07 | 2.34159e+07 | 0 | 0.011795 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 2.17958e+09 | 26.8184 | 50.4958 | 0 sectors | 1.17339e+06 | 3.12456e+06 |  | 0 | 1.66799e+08 | 1.37939e+08 | 0 | 0.001895 | 88.7969 | 180.406 | 102.558 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 2.18077e+09 | 42.1951 | 55.5043 | 0 sectors | 822914 | 2.28101e+06 |  | 0 | 1.20157e+08 | 1.00786e+08 | 2.624e+08 | 0.00251 | 68.7884 | 336.061 | 49.4833 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 98.9721 | 0 sectors | 363862 | 1.35492e+06 |  | 0 | 4.26988e+09 | 6.43287e+07 | 0 | 0.01917 | 574.364 | 275.998 | 8.00195 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
