# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 20.7889 | 46.5043 | 0 sectors | 1.07851e+06 | 2.74772e+06 |  | 0 | 1.77484e+08 | 1.37488e+08 | 0 | 0.002726 | 95.7927 | 308.066 | 62.1941 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 20.8841 | 48.3012 | 0 sectors | 1.42292e+06 | 5.0113e+06 |  | 0 | 3.20883e+08 | 2.3603e+08 | 0 | 0.001339 | 0.000312 | 245.714 | 100.38 | ok |  |
| dram_cg_load_only_W8192_B16 | dram_cg_load_only | 8192 | 16 | 0 | 7e-06 | 0.161789 | 1.67936e+10 sectors | 1.68081e+10 | 1.68246e+10 |  | 5.37395e+11 | 5.3943e+11 | 5.39078e+11 | 0 | 1801.64 | 74.0376 | 236.043 | 10.7243 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.174694 | 3.35872e+10 sectors | 1.68082e+10 | 1.68237e+10 |  | 1.07479e+12 | 5.39351e+11 | 5.39009e+11 | 0 | 1363.77 | 65.0834 | 152.77 | 19.2544 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.188187 | 8.3968e+09 sectors | 4.20202e+09 | 4.20721e+09 |  | 2.68698e+11 | 1.34899e+11 | 1.34798e+11 | 2.624e+08 | 110.834 | 115.283 | 258.407 | 56.1569 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 21.0747 | 47.5244 | 0 sectors | 0 | 25124 |  | 0 | 1.44646e+06 | 841600 | 0 | 0.114894 | 0.030014 | 366.646 | 99.9679 | ok |  |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.999 | 49.885 | 3.35872e+10 sectors | 2.84891e+06 | 6.67753e+06 |  | 1.07479e+12 | 4.11585e+08 | 3.2769e+08 | 0 | 17.4328 | 52.7559 | 210.023 | 80.9291 | ok |  |
| l2_cg_load_only_W64_B16 | l2_cg_load_only | 64 | 16 | 0 | 6e-06 | 99.9218 | 1.67936e+10 sectors | 1.67978e+10 | 1.28149e+07 |  | 5.37395e+11 | 5.38071e+11 | 6.16754e+08 | 0 | 865.575 | 52.6352 | 309.061 | 15.5535 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 88.3763 | 99.707 | 3.35872e+10 sectors | 3.90638e+09 | 8.20773e+06 |  | 1.07479e+12 | 1.2535e+11 | 3.71825e+08 | 0 | 70.7224 | 50.5018 | 188.872 | 80.8787 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.9977 | 45.8826 | 8.3968e+09 sectors | 1.20545e+06 | 3.27061e+06 |  | 2.68698e+11 | 1.96563e+08 | 1.56992e+08 | 2.624e+08 | 0.037343 | 50.2149 | 325.978 | 59.7974 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.0244 | 92.5991 | 0 sectors | 0 | 38524 |  | 0 | 2.70323e+06 | 1.37229e+06 | 0 | 0.005863 | 45.0063 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.1167 | 89.4692 | 0 sectors | 0 | 5704 |  | 0 | 2.23923e+06 | 350464 | 6.56e+07 | 0.011993 | 0.006342 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 32.6394 | 32.3075 | 0 sectors | 65035 | 542284 |  | 0 | 2.64683e+07 | 2.12197e+07 | 0 | 0.011945 | 181.815 | 327.263 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 8.73754e+09 | 27.206 | 52.6471 | 0 sectors | 4.95622e+06 | 7.41748e+06 |  | 0 | 5.00667e+08 | 3.86795e+08 | 0 | 0.000552 | 89.7835 | 194.147 | 79.9967 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 2.168e+09 | 43.9852 | 53.094 | 0 sectors | 1.64372e+06 | 2.37225e+06 |  | 0 | 1.62494e+08 | 1.28448e+08 | 2.624e+08 | 0.001918 | 47.73 | 350.519 | 49.5471 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.1974 | 0 sectors | 363442 | 539932 |  | 0 | 4.24367e+09 | 3.58275e+07 | 0 | 0.019777 | 574.365 | 275.998 | 8.00198 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
