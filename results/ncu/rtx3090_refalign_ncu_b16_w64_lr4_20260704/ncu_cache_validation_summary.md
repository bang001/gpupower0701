# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 20.6936 | 58.9064 | 0 sectors | 1.0412e+06 | 2.12188e+06 |  | 0 | 1.5268e+08 | 1.15629e+08 | 0 | 0.002794 | 95.7925 | 308.085 | 62.1991 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.2271 | 73.2344 | 0 sectors | 1.3213e+06 | 3.52444e+06 |  | 0 | 2.64971e+08 | 1.87027e+08 | 0 | 0.001328 | 0.000312 | 245.714 | 100.135 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9997 | 0.173057 | 3.35872e+10 sectors | 1.68083e+10 | 1.68239e+10 |  | 1.07479e+12 | 5.39301e+11 | 5.38972e+11 | 0 | 1355.29 | 65.1031 | 152.772 | 19.3801 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.204397 | 8.3968e+09 sectors | 4.20186e+09 | 4.20744e+09 |  | 2.68698e+11 | 1.34896e+11 | 1.34798e+11 | 2.624e+08 | 110.385 | 115.313 | 258.418 | 56.2265 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.9223 | 93.4835 | 0 sectors | 0 | 360 |  | 0 | 683552 | 19712 | 0 | 0.208354 | 0.029865 | 366.646 | 99.7515 | ok |  |
| global_l1_load_only_W64_B16 | global_l1_load_only | 64 | 16 | 0 | 88.1275 | 99.7473 | 3.35872e+10 sectors | 3.99043e+09 | 8.95388e+06 |  | 1.07479e+12 | 1.28066e+11 | 4.09535e+08 | 0 | 69.2961 | 52.363 | 208.09 | 70.5369 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 88.3843 | 99.8014 | 3.35872e+10 sectors | 3.90376e+09 | 8.11004e+06 |  | 1.07479e+12 | 1.2526e+11 | 3.68326e+08 | 0 | 70.6588 | 50.4984 | 188.868 | 80.8065 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 99.9973 | 50.3728 | 8.3968e+09 sectors | 1.45005e+06 | 3.67089e+06 |  | 2.68698e+11 | 2.25228e+08 | 1.79753e+08 | 2.624e+08 | 0.028268 | 50.2163 | 325.98 | 59.7976 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 28.9199 | 89.2153 | 0 sectors | 0 | 5908 |  | 0 | 1.66221e+06 | 255744 | 0 | 0.005675 | 45.0065 | 23.3369 | 0 | ok |  |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0557 | 90.2827 | 0 sectors | 0 | 6396 |  | 0 | 2.19584e+06 | 218368 | 6.56e+07 | 0.012302 | 0.006342 | 285.708 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 32.9094 | 18.7639 | 0 sectors | 65053 | 129356 |  | 0 | 1.25071e+07 | 7.78611e+06 | 0 | 0.012697 | 181.816 | 327.263 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 8.73768e+09 | 27.169 | 49.5815 | 0 sectors | 4.73935e+06 | 7.38614e+06 |  | 0 | 4.92393e+08 | 3.81874e+08 | 0 | 0.000738 | 89.7834 | 194.146 | 79.9966 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 2.16795e+09 | 43.1642 | 53.8631 | 0 sectors | 1.64481e+06 | 2.38921e+06 |  | 0 | 1.63927e+08 | 1.28673e+08 | 2.624e+08 | 0.001949 | 47.7259 | 350.528 | 49.5474 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9818 | 99.4826 | 0 sectors | 365685 | 679452 |  | 0 | 4.24781e+09 | 4.25542e+07 | 0 | 0.019219 | 574.365 | 275.998 | 8.00196 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
