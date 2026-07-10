# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | sass | 0 | 0 | 20.846 | 50.2693 | 0 sectors | 700453 | 2.43666e+06 | 0 | 0 | 1.58399e+08 | 1.18954e+08 | 0 | 0.002551 | 0.000583 | 378.947 | 33.6618 | ok |  |
| dram_cg_load_only_W128_B16_LR4 | dram_cg_load_only | 128 | 16 | 0 | sass | 0 | 0 | 6e-06 | 1.14747 | 1.67936e+10 sectors | 1.6807e+10 | 1.66523e+10 | 0 | 5.37395e+11 | 5.39261e+11 | 5.33522e+11 | 0 | 1787.03 | 74.0485 | 235.952 | 10.5928 | ok |  |
| global_l1_load_only_W16_B16_LR4 | global_l1_load_only | 16 | 16 | 0 | sass | 0 | 0 | 99.9997 | 101.675 | 3.35872e+10 sectors | 506521 | 4.67812e+06 | 0 | 1.07479e+12 | 2.1452e+08 | 1.70847e+08 | 0 | 17.4317 | 52.7463 | 210.022 | 80.9255 | ok | l2_hit_rate_pct_out_of_range |
| l2_cg_load_only_W64_B16_LR4 | l2_cg_load_only | 64 | 16 | 0 | sass | 0 | 0 | 7e-06 | 99.961 | 1.67936e+10 sectors | 1.67979e+10 | 1.27413e+07 | 0 | 5.37395e+11 | 5.38069e+11 | 6.08968e+08 | 0 | 865.733 | 52.6332 | 309.022 | 15.4742 | ok |  |
| reg_mma_W2048_B16_RF16 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 35.7274 | 81.6141 | 0 sectors | 2.92258e+06 | 7.66716e+06 | 0 | 0 | 5.44255e+08 | 3.85784e+08 | 4.1984e+09 | 0.005973 | 0.00163 | 531.335 | 77.2843 | ok |  |
| reg_mma_W2048_B16_RF8 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 37.5218 | 48.263 | 0 sectors | 1.2988e+06 | 4.5037e+06 | 0 | 0 | 2.83158e+08 | 2.10225e+08 | 2.0992e+09 | 0.008349 | 0.002432 | 490.197 | 56.5579 | ok |  |
| reg_operand_only_W2048_B16_RF16 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 31.9991 | 58.8888 | 0 sectors | 2.49823e+06 | 8.26175e+06 | 0 | 0 | 5.18752e+08 | 3.88583e+08 | 0 | 0.003941 | 1075.88 | 107.748 | 17.9031 | ok |  |
| reg_operand_only_W2048_B16_RF8 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 32.01 | 22.8084 | 0 sectors | 0 | 3.34845e+06 | 0 | 0 | 1.38338e+08 | 1.07153e+08 | 0 | 0.005612 | 970.907 | 133.752 | 15.212 | ok |  |
| shared_scalar_load_only_W64_B16_LR4 | shared_scalar_load_only | 64 | 16 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 20.7889 | 58.2832 | 0 sectors | 4.34067e+06 | 5.21698e+06 | 5.37401e+11 | 0 | 3.98446e+08 | 2.94741e+08 | 0 | 0.001958 | 91.0426 | 307.003 | 51.0063 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
