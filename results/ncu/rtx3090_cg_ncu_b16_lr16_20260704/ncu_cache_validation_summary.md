# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 20.846 | 56.751 | 0 sectors | 3.56087e+06 | 6.86258e+06 |  | 0 | 5.13556e+08 | 3.78513e+08 | 0 | 0.001657 | 112.875 | 314.574 | 57.239 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 20.7889 | 57.0373 | 0 sectors | 3.37341e+06 | 9.03411e+06 |  | 0 | 6.81871e+08 | 4.68301e+08 | 0 | 0.000527 | 0.000116 | 175 | 127.022 | ok |  |
| dram_cg_load_only_W8192_B16 | dram_cg_load_only | 8192 | 16 | 0 | 2e-06 | 0.155437 | 6.71744e+10 sectors | 6.72222e+10 | 6.7261e+10 |  | 2.14958e+12 | 2.15579e+12 | 2.15462e+12 | 0 | 1865.97 | 77.5992 | 230.468 | 10.3921 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.161554 | 1.34349e+11 sectors | 6.72303e+10 | 6.72652e+10 |  | 4.29916e+12 | 2.15608e+12 | 2.15481e+12 | 0 | 1416.65 | 67.797 | 146.84 | 18.7751 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 50.3459 | 1.03009 | 8.3968e+09 sectors | 4.18236e+09 | 4.17904e+09 |  | 2.68698e+11 | 1.35124e+11 | 1.34306e+11 | 2.624e+08 | 24.0157 | 140.498 | 235.499 | 67.5046 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9413 | 29.5418 | 0 sectors | 0 | 45336 |  | 0 | 2.10154e+06 | 1.46701e+06 | 0 | 0.118021 | 0.029905 | 366.645 | 99.9697 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.9992 | 55.4988 | 1.34349e+11 sectors | 1.09235e+07 | 1.86867e+07 |  | 4.29916e+12 | 1.38924e+09 | 1.05344e+09 | 0 | 19.2038 | 56.5925 | 212.32 | 79.4644 | ok |  |
| l2_cg_load_only_W64_B16 | l2_cg_load_only | 64 | 16 | 0 | 2e-06 | 99.9406 | 6.71744e+10 sectors | 6.71914e+10 | 4.03278e+07 |  | 2.14958e+12 | 2.15192e+12 | 2.09159e+09 | 0 | 988.773 | 56.9232 | 305.041 | 13.2899 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 88.5473 | 99.8401 | 1.34349e+11 sectors | 1.5397e+10 | 2.45422e+07 |  | 4.29916e+12 | 4.93846e+11 | 1.26169e+09 | 0 | 72.8851 | 52.7633 | 180.169 | 82.6169 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.9941 | 57.1588 | 8.3968e+09 sectors | 3.90869e+06 | 7.35961e+06 |  | 2.68698e+11 | 5.42762e+08 | 4.02169e+08 | 2.624e+08 | 0.016953 | 62.1678 | 290.239 | 69.4076 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 32.108 | 5.90721 | 0 sectors | 53246 | 200828 |  | 0 | 2.4552e+07 | 1.7761e+07 | 0 | 0.005691 | 45.0088 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.1167 | 33.687 | 0 sectors | 0 | 118824 |  | 0 | 5.84134e+06 | 3.84704e+06 | 6.56e+07 | 0.012264 | 0.006341 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.1934 | 90.1542 | 0 sectors | 0 | 7140 |  | 0 | 2.61635e+06 | 348416 | 0 | 0.011298 | 181.815 | 327.264 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 3.50091e+10 | 27.7134 | 53.9369 | 0 sectors | 1.88766e+07 | 2.22496e+07 |  | 0 | 1.70794e+09 | 1.28495e+09 | 0 | 0.000145 | 95.2836 | 193.757 | 78.8331 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 8.74805e+09 | 42.9094 | 59.0685 | 0 sectors | 4.30069e+06 | 5.36558e+06 |  | 0 | 4.05995e+08 | 3.07014e+08 | 2.624e+08 | 0.000696 | 103.795 | 336.771 | 48.2345 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.6527 | 0 sectors | 365806 | 465488 |  | 0 | 4.24102e+09 | 3.60104e+07 | 0 | 0.019211 | 574.364 | 275.998 | 8.0021 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
