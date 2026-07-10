# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | sass | 0 | 0 | 21.3986 | 44.4211 | 0 sectors | 704830 | 2.67196e+06 | 0 | 0 | 1.701e+08 | 1.2375e+08 | 0 | 0.002553 | 0.000588 | 378.947 | 33.8725 | ok |  |
| dram_cg_load_only_W8192_B16_LR4 | dram_cg_load_only | 8192 | 16 | 0 | sass | 0 | 0 | 7e-06 | 0.038381 | 1.67936e+10 sectors | 1.67998e+10 | 1.6818e+10 | 0 | 5.37395e+11 | 5.38663e+11 | 5.3847e+11 | 0 | 1784.08 | 74.0864 | 236.104 | 10.8661 | ok |  |
| global_l1_load_only_W16_B16_LR4 | global_l1_load_only | 16 | 16 | 0 | sass | 0 | 0 | 99.9998 | 57.2715 | 3.35872e+10 sectors | 41984 | 4.3892e+06 | 0 | 1.07479e+12 | 1.79393e+08 | 1.40454e+08 | 0 | 17.4343 | 52.7512 | 210.023 | 80.9235 | ok |  |
| l2_cg_load_only_W64_B16_LR4 | l2_cg_load_only | 64 | 16 | 0 | sass | 0 | 0 | 7e-06 | 99.9066 | 1.67936e+10 sectors | 1.67994e+10 | 1.40017e+07 | 0 | 5.37395e+11 | 5.38188e+11 | 7.19515e+08 | 0 | 864.97 | 52.6354 | 309.01 | 15.5608 | ok |  |
| reg_mma_W2048_B16_RF4 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 36.2957 | 32.3856 | 0 sectors | 431231 | 2.1648e+06 | 0 | 0 | 1.20292e+08 | 9.38189e+07 | 1.0496e+09 | 0.010564 | 0.002958 | 409.032 | 29.2122 | ok |  |
| reg_operand_only_W2048_B16_RF4 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 31.7291 | 63.2529 | 0 sectors | 427908 | 2.11342e+06 | 0 | 0 | 1.2116e+08 | 9.01961e+07 | 0 | 0.009671 | 785.145 | 171.431 | 12.6772 | ok |  |
| shared_scalar_load_only_W64_B16_LR4 | shared_scalar_load_only | 64 | 16 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 20.8079 | 15.0719 | 0 sectors | 724793 | 3.04068e+06 | 5.37401e+11 | 0 | 1.55649e+08 | 1.19054e+08 | 0 | 0.001967 | 91.0475 | 307.006 | 51.0026 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
