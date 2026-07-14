# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | sass | 0 | 0 | 18.3689 | 19.8903 | 0 sectors | 0 | 1.86296e+06 | 0 | 0 | 7.51307e+07 | 6.01452e+07 | 0 | 0.002683 | 0.000551 | 378.947 | 5.76064 |  | 16 | 0 | 0 | ok |  |
| dram_cg_load_only_W8192_B8_LR1 | dram_cg_load_only | 8192 | 8 | 0 | sass | 0 | 0 | 0 | 2.51524e-05 | 2.0992e+09 sectors | 2.0992e+09 | 2.10178e+09 | 0 | 6.71744e+10 | 6.72675e+10 | 6.72578e+10 | 0 | 543.679 | 67.9496 | 269.975 | 6.12769 |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W8192_B8_LR16 | dram_cg_load_only | 8192 | 8 | 0 | sass | 0 | 0 | 0 | 0.000444108 | 3.35872e+10 sectors | 3.35872e+10 | 3.36271e+10 | 0 | 1.07479e+12 | 1.07623e+12 | 1.07607e+12 | 0 | 729.065 | 75.9638 | 218.957 | 5.73393 |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W8192_B8_LR4 | dram_cg_load_only | 8192 | 8 | 0 | sass | 0 | 0 | 0 | 0.00402388 | 8.3968e+09 sectors | 8.39894e+09 | 8.4082e+09 | 0 | 2.68698e+11 | 2.69321e+11 | 2.69155e+11 | 0 | 701.554 | 72.5113 | 224.758 | 5.98592 |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W8192_B8_LR8 | dram_cg_load_only | 8192 | 8 | 0 | sass | 0 | 0 | 0 | 0.000494997 | 1.67936e+10 sectors | 1.67937e+10 | 1.68138e+10 | 0 | 5.37395e+11 | 5.38136e+11 | 5.38047e+11 | 0 | 725.559 | 74.7572 | 220.862 | 5.79785 |  | 38 | 0 | 0 | ok |  |
| global_addr_only_dram_W8192_B8_LR1 | global_addr_only | 8192 | 8 | 0 | sass | 0 | 0 | 17.1494 | 19.77 | 0 sectors | 0 | 1.24122e+06 | 0 | 0 | 4.86491e+07 | 3.97189e+07 | 0 | 0.005569 | 63.9047 | 196.86 | 17.4313 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W8192_B8_LR16 | global_addr_only | 8192 | 8 | 0 | sass | 0 | 0 | 17.1494 | 20.7661 | 0 sectors | 0 | 1.49599e+07 | 0 | 0 | 6.04462e+08 | 4.78717e+08 | 0 | 0.000394 | 70.9199 | 166.431 | 18.2492 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W8192_B8_LR4 | global_addr_only | 8192 | 8 | 0 | sass | 0 | 0 | 17.1494 | 0 | 0 sectors | 0 | 3.80396e+06 | 0 | 0 | 1.53361e+08 | 1.21727e+08 | 0 | 0.002458 | 69.5282 | 168.827 | 21.52 |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_dram_W8192_B8_LR8 | global_addr_only | 8192 | 8 | 0 | sass | 0 | 0 | 17.1875 | 0 | 0 sectors | 0 | 7.45481e+06 | 0 | 0 | 3.03253e+08 | 2.38554e+08 | 0 | 0.000775 | 70.1977 | 167.08 | 18.795 |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l1_W8_B8_LR1 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.5305 | 21.9001 | 0 sectors | 0 | 638600 | 0 | 0 | 2.60101e+07 | 2.04352e+07 | 0 | 0.005884 | 39.5249 | 234.612 | 24.9467 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.7591 | 22.3167 | 0 sectors | 0 | 7.43774e+06 | 0 | 0 | 3.04505e+08 | 2.38008e+08 | 0 | 0.000387 | 48.8305 | 194.361 | 13.9933 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR2 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.3399 | 20.8559 | 0 sectors | 0 | 1.15505e+06 | 0 | 0 | 4.70859e+07 | 3.69615e+07 | 0 | 0.003077 | 46.0368 | 204.468 | 19.9332 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.1875 | 22.6351 | 0 sectors | 0 | 1.94032e+06 | 0 | 0 | 7.89449e+07 | 6.20904e+07 | 0 | 0.001552 | 46.5081 | 195.714 | 15.0795 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4543 | 21.6139 | 0 sectors | 0 | 3.73606e+06 | 0 | 0 | 1.54072e+08 | 1.19554e+08 | 0 | 0.000819 | 48.0296 | 194.828 | 14.3679 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR1 | global_addr_only | 64 | 8 | 0 | sass | 0 | 0 | 17.1494 | 22.0546 | 0 sectors | 0 | 626168 | 0 | 0 | 2.58116e+07 | 2.00374e+07 | 0 | 0.012362 | 40.9943 | 235.096 | 18.3017 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | 64 | 8 | 0 | sass | 0 | 0 | 16.997 | 22.2584 | 0 sectors | 0 | 7.46049e+06 | 0 | 0 | 3.03886e+08 | 2.38736e+08 | 0 | 0.00095 | 48.8304 | 194.361 | 13.9933 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR2 | global_addr_only | 64 | 8 | 0 | sass | 0 | 0 | 17.2256 | 21.5185 | 0 sectors | 0 | 1.13054e+06 | 0 | 0 | 4.57766e+07 | 3.61774e+07 | 0 | 0.006462 | 46.0205 | 204.595 | 19.9205 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 64 | 8 | 0 | sass | 0 | 0 | 17.5305 | 21.5425 | 0 sectors | 0 | 1.97364e+06 | 0 | 0 | 8.0339e+07 | 6.31565e+07 | 0 | 0.003446 | 46.5081 | 195.714 | 15.0795 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | 64 | 8 | 0 | sass | 0 | 0 | 17.1113 | 20.8871 | 0 sectors | 0 | 3.97887e+06 | 0 | 0 | 1.61884e+08 | 1.27324e+08 | 0 | 0.001837 | 48.0296 | 194.828 | 14.3679 |  | 34 | 0 | 0 | ok |  |
| global_l1_load_only_W8_B8_LR1 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.999 | 100 | 2.0992e+09 sectors | 20992 | 619756 | 0 | 6.71744e+10 | 2.67039e+07 | 1.98322e+07 | 0 | 4.56812 | 53.6178 | 388.936 | 9.03912 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 100 | 3.35872e+10 sectors | 20992 | 8.67712e+06 | 0 | 1.07479e+12 | 3.53947e+08 | 2.77668e+08 | 0 | 1.9885 | 62.7654 | 319.282 | 11.7609 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR2 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9995 | 100 | 4.1984e+09 sectors | 20992 | 1.23952e+06 | 0 | 1.34349e+11 | 5.07055e+07 | 3.96645e+07 | 0 | 2.09408 | 54.061 | 332.775 | 10.2652 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9998 | 100 | 8.3968e+09 sectors | 20992 | 2.4604e+06 | 0 | 2.68698e+11 | 9.90793e+07 | 7.87329e+07 | 0 | 1.61067 | 58.3507 | 325.149 | 11.1182 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 100 | 1.67936e+10 sectors | 20992 | 4.33999e+06 | 0 | 5.37395e+11 | 1.77452e+08 | 1.3888e+08 | 0 | 1.87275 | 60.8382 | 321.183 | 11.5011 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| l2_cg_load_only_W64_B8_LR1 | l2_cg_load_only | 64 | 8 | 0 | sass | 0 | 0 | 0 | 99.9964 | 2.0992e+09 sectors | 2.0992e+09 | 1.32054e+06 | 0 | 6.71744e+10 | 6.72235e+10 | 4.25307e+07 | 0 | 313.425 | 47.2337 | 355.437 | 6.26487 |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 64 | 8 | 0 | sass | 0 | 0 | 0 | 99.9998 | 3.35872e+10 sectors | 3.35874e+10 | 1.65154e+07 | 0 | 1.07479e+12 | 1.07546e+12 | 5.34584e+08 | 0 | 413.894 | 56.5451 | 294.302 | 6.47839 |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR2 | l2_cg_load_only | 64 | 8 | 0 | sass | 0 | 0 | 0 | 99.9982 | 4.1984e+09 sectors | 4.1984e+09 | 2.40923e+06 | 0 | 1.34349e+11 | 1.34441e+11 | 7.74898e+07 | 0 | 326.075 | 47.271 | 302.579 | 8.06047 |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 64 | 8 | 0 | sass | 0 | 0 | 0 | 99.9991 | 8.3968e+09 sectors | 8.3968e+09 | 3.96094e+06 | 0 | 2.68698e+11 | 2.68855e+11 | 1.27301e+08 | 0 | 371.434 | 52.1513 | 298.201 | 7.21903 |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 64 | 8 | 0 | sass | 0 | 0 | 0 | 99.9996 | 1.67936e+10 sectors | 1.67936e+10 | 8.12833e+06 | 0 | 5.37395e+11 | 5.3772e+11 | 2.61077e+08 | 0 | 400.632 | 55 | 295.671 | 6.73231 |  | 38 | 0 | 0 | ok |  |
| reg_mma_W2048_B8_RF1 | reg_mma | 2048 | 8 | 0 | sass | 0 | 0 | 86.7637 | 39.2252 | 0 sectors | 0 | 168492 | 0 | 0 | 8.11005e+06 | 5.39174e+06 | 1.312e+08 | 0.021948 | 0.00555 | 299.915 | 11.608 |  | 26 | 0 | 0 | ok |  |
| reg_mma_W2048_B8_RF16 | reg_mma | 2048 | 8 | 0 | sass | 0 | 0 | 86.7678 | 22.8784 | 0 sectors | 0 | 3.20517e+06 | 0 | 0 | 1.33647e+08 | 1.02565e+08 | 2.0992e+09 | 0.00199 | 0.000321 | 213.871 | 13.2614 |  | 26 | 0 | 0 | ok |  |
| reg_mma_W2048_B8_RF2 | reg_mma | 2048 | 8 | 0 | sass | 0 | 0 | 86.7631 | 42.0908 | 0 sectors | 0 | 202748 | 0 | 0 | 1.13215e+07 | 6.48794e+06 | 2.624e+08 | 0.013473 | 0.00227 | 212.395 | 16.1482 |  | 25 | 0 | 0 | ok |  |
| reg_mma_W2048_B8_RF4 | reg_mma | 2048 | 8 | 0 | sass | 0 | 0 | 86.7619 | 25.7636 | 0 sectors | 0 | 751876 | 0 | 0 | 3.28817e+07 | 2.406e+07 | 5.248e+08 | 0.00734 | 0.001207 | 215.499 | 14.6244 |  | 26 | 0 | 0 | ok |  |
| reg_mma_W2048_B8_RF8 | reg_mma | 2048 | 8 | 0 | sass | 0 | 0 | 86.7655 | 21.7428 | 0 sectors | 0 | 1.77559e+06 | 0 | 0 | 7.37247e+07 | 5.68188e+07 | 1.0496e+09 | 0.003781 | 0.00063 | 214.549 | 13.7375 |  | 26 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B8_RF1 | reg_operand_only | 2048 | 8 | 0 | sass | 0 | 0 | 80.6603 | 37.9644 | 0 sectors | 0 | 132208 | 0 | 0 | 7.06733e+06 | 4.23066e+06 | 0 | 0.034915 | 0.006028 | 393.736 | 3.83123 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B8_RF16 | reg_operand_only | 2048 | 8 | 0 | sass | 0 | 0 | 81.1823 | 28.8315 | 0 sectors | 0 | 620204 | 0 | 0 | 2.74237e+07 | 1.98465e+07 | 0 | 0.00762 | 0.001378 | 427.14 | 1.48325 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B8_RF2 | reg_operand_only | 2048 | 8 | 0 | sass | 0 | 0 | 83.7473 | 51.5384 | 0 sectors | 0 | 61756 | 0 | 0 | 3.95734e+06 | 1.97619e+06 | 0 | 0.03644 | 0.006861 | 278.566 | 11.7273 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B8_RF4 | reg_operand_only | 2048 | 8 | 0 | sass | 0 | 0 | 81.4177 | 96.0948 | 0 sectors | 0 | 3772 | 0 | 0 | 3.12448e+06 | 120704 | 0 | 0.024625 | 0.004379 | 377.265 | 4.5738 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B8_RF8 | reg_operand_only | 2048 | 8 | 0 | sass | 0 | 0 | 81.2047 | 19.343 | 0 sectors | 0 | 603052 | 0 | 0 | 2.39351e+07 | 1.92977e+07 | 0 | 0.013649 | 0.002531 | 407.89 | 2.55176 |  | 22 | 0 | 0 | ok |  |
| shared_scalar_load_only_W64_B8_LR1 | shared_scalar_load_only | 64 | 8 | 5.24842e+08 | sass | 0 | 5.24842e+08 | 17.9497 | 20.2703 | 0 sectors | 0 | 619764 | 6.71798e+10 | 0 | 2.52397e+07 | 1.98324e+07 | 0 | 0.0084 | 74.3871 | 326.168 | 11.3296 |  | 26 | 0 | 8.192 | ok |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 64 | 8 | 8.39684e+09 | sass | 0 | 8.39684e+09 | 17.6448 | 21.0447 | 0 sectors | 0 | 7.55335e+06 | 1.0748e+12 | 0 | 3.0867e+08 | 2.41707e+08 | 0 | 0.000613 | 92.0715 | 299.581 | 13.9793 |  | 26 | 0 | 8.192 | ok |  |
| shared_scalar_load_only_W64_B8_LR2 | shared_scalar_load_only | 64 | 8 | 1.04964e+09 | sass | 0 | 1.04964e+09 | 17.7591 | 26.1627 | 0 sectors | 0 | 803564 | 1.34354e+11 | 0 | 3.53489e+07 | 2.5714e+07 | 0 | 0.004269 | 77.8748 | 290.829 | 12.1518 |  | 26 | 0 | 8.192 | ok |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 64 | 8 | 2.09924e+09 | sass | 0 | 2.09924e+09 | 18.2927 | 18.9468 | 0 sectors | 0 | 2.28146e+06 | 2.68703e+11 | 0 | 9.0202e+07 | 7.30067e+07 | 0 | 0.002305 | 86.4739 | 294.248 | 11.8995 |  | 26 | 0 | 8.192 | ok |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 64 | 8 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 17.5305 | 20.8282 | 0 sectors | 0 | 3.82686e+06 | 5.37401e+11 | 0 | 1.5596e+08 | 1.2246e+08 | 0 | 0.001215 | 90.0843 | 297.874 | 13.5144 |  | 26 | 0 | 8.192 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the srcunit-TEX read hit/miss sectors when available.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 18.3689 | aggregate_fallback | 0 | 0 | 0 |  | 19.5599 |  | 19.8903 | aggregate_fallback | 0 | 0 |  | 0 | 5.96146e+07 |  | 0 |  |  |
| dram_cg_load_only_W8192_B8_LR1 | dram_cg_load_only | 0 | 2.2e-05 | global_load_lookup_hit_miss | 6.71744e+10 | 0 | 6.71744e+10 | 2.51524e-05 | 0.009758 | 0.00973285 | 0.010814 | srcunit_tex_read_lookup_hit_miss | 528 | 2.0992e+09 | 1 | 6.71744e+10 | 6.7257e+10 | 1.00123 | 6.71744e+10 |  |  |
| dram_cg_load_only_W8192_B8_LR16 | dram_cg_load_only | 0 | 1e-06 | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 0.000444108 | 0.010693 | 0.0102489 | 0.011395 | srcunit_tex_read_lookup_hit_miss | 149164 | 3.35872e+10 | 1 | 1.07479e+12 | 1.07607e+12 | 1.00119 | 1.07479e+12 |  |  |
| dram_cg_load_only_W8192_B8_LR4 | dram_cg_load_only | 0 | 5e-06 | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 0.00402388 | 0.014392 | 0.0103681 | 0.049287 | srcunit_tex_read_lookup_hit_miss | 337890 | 8.39678e+09 | 0.999783 | 2.68697e+11 | 2.69063e+11 | 1.00136 | 2.68766e+11 |  |  |
| dram_cg_load_only_W8192_B8_LR8 | dram_cg_load_only | 0 | 3e-06 | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 0.000494997 | 0.011139 | 0.010644 | 0.017261 | srcunit_tex_read_lookup_hit_miss | 83134 | 1.67948e+10 | 1.00007 | 5.37432e+11 | 5.3804e+11 | 1.00113 | 5.37399e+11 |  |  |
| global_addr_only_dram_W8192_B8_LR1 | global_addr_only |  | 17.1494 | aggregate_fallback | 0 | 0 | 0 |  | 19.045 |  | 19.77 | aggregate_fallback | 0 | 0 |  | 0 | 3.97189e+07 |  | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR16 | global_addr_only |  | 17.1494 | aggregate_fallback | 0 | 0 | 0 |  | 20.3076 |  | 20.7661 | aggregate_fallback | 0 | 0 |  | 0 | 4.78717e+08 |  | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR4 | global_addr_only |  | 17.1494 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.2541 | 21.2541 | 21.7437 | srcunit_tex_read_lookup_hit_miss | 0 | 668098 |  | 2.13791e+07 | 1.21727e+08 | 5.69372 | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR8 | global_addr_only |  | 17.1875 | aggregate_fallback | 0 | 0 | 0 | 0 | 20.502 | 20.502 | 21.0957 | srcunit_tex_read_lookup_hit_miss | 0 | 2.56368e+06 |  | 8.20378e+07 | 2.38554e+08 | 2.90785 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR1 | global_addr_only |  | 17.5305 | aggregate_fallback | 0 | 0 | 0 |  | 21.3155 |  | 21.9001 | aggregate_fallback | 0 | 0 |  | 0 | 2.04352e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 17.7591 | aggregate_fallback | 0 | 0 | 0 |  | 21.7304 |  | 22.3167 | aggregate_fallback | 0 | 0 |  | 0 | 2.38008e+08 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR2 | global_addr_only |  | 17.3399 | aggregate_fallback | 0 | 0 | 0 |  | 20.4796 |  | 20.8559 | aggregate_fallback | 0 | 0 |  | 0 | 3.69615e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 17.1875 | aggregate_fallback | 0 | 0 | 0 |  | 22.1731 |  | 22.6351 | aggregate_fallback | 0 | 0 |  | 0 | 6.20904e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 17.4543 | aggregate_fallback | 0 | 0 | 0 |  | 21.1733 |  | 21.6139 | aggregate_fallback | 0 | 0 |  | 0 | 1.19554e+08 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR1 | global_addr_only |  | 17.1494 | aggregate_fallback | 0 | 0 | 0 |  | 21.5682 |  | 22.0546 | aggregate_fallback | 0 | 0 |  | 0 | 2.00374e+07 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only |  | 16.997 | aggregate_fallback | 0 | 0 | 0 |  | 21.6665 |  | 22.2584 | aggregate_fallback | 0 | 0 |  | 0 | 2.38736e+08 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR2 | global_addr_only |  | 17.2256 | aggregate_fallback | 0 | 0 | 0 |  | 20.8246 |  | 21.5185 | aggregate_fallback | 0 | 0 |  | 0 | 3.61774e+07 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  | 17.5305 | aggregate_fallback | 0 | 0 | 0 |  | 21.0087 |  | 21.5425 | aggregate_fallback | 0 | 0 |  | 0 | 6.31565e+07 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only |  | 17.1113 | aggregate_fallback | 0 | 0 | 0 |  | 20.3914 |  | 20.8871 | aggregate_fallback | 0 | 0 |  | 0 | 1.27324e+08 |  | 0 |  |  |
| global_l1_load_only_W8_B8_LR1 | global_l1_load_only | 99.999 | 99.9989 | global_load_lookup_hit_miss | 6.71744e+10 | 6.71737e+10 | 671744 | 100 | 24.4572 | 75.5428 | 25.015 | srcunit_tex_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 1.98322e+07 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 1.07479e+12 | 1.07479e+12 | 671744 | 100 | 20.2322 | 79.7678 | 20.6948 | srcunit_tex_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 2.77668e+08 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR2 | global_l1_load_only | 99.9995 | 99.9994 | global_load_lookup_hit_miss | 1.34349e+11 | 1.34348e+11 | 671744 | 100 | 22.8948 | 77.1052 | 23.5979 | srcunit_tex_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 3.96645e+07 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 99.9998 | 99.9997 | global_load_lookup_hit_miss | 2.68698e+11 | 2.68697e+11 | 671744 | 100 | 19.672 | 80.328 | 20.0196 | srcunit_tex_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 7.87329e+07 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 5.37395e+11 | 5.37395e+11 | 671744 | 100 | 21.0947 | 78.9053 | 21.6608 | srcunit_tex_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 1.3888e+08 |  | 671744 |  |  |
| l2_cg_load_only_W64_B8_LR1 | l2_cg_load_only | 0 | 2.2e-05 | global_load_lookup_hit_miss | 6.71744e+10 | 0 | 6.71744e+10 | 99.9964 | 99.9383 | 0.0580391 | 99.9589 | srcunit_tex_read_lookup_hit_miss | 2.09913e+09 | 76220 | 1 | 2.43904e+06 | 4.22573e+07 | 17.3254 | 6.71744e+10 | 6.71744e+10 | 1 |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 0 | 1e-06 | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 99.9998 | 99.9506 | 0.049204 | 99.9494 | srcunit_tex_read_lookup_hit_miss | 3.35871e+10 | 73572 | 0.999995 | 2.3543e+06 | 5.28492e+08 | 224.479 | 1.0748e+12 | 1.07479e+12 | 1 |
| l2_cg_load_only_W64_B8_LR2 | l2_cg_load_only | 0 | 1.1e-05 | global_load_lookup_hit_miss | 1.34349e+11 | 0 | 1.34349e+11 | 99.9982 | 99.9429 | 0.0553123 | 99.943 | srcunit_tex_read_lookup_hit_miss | 4.19833e+09 | 75140 | 1 | 2.40448e+06 | 7.70954e+07 | 32.0632 | 1.34349e+11 | 1.34349e+11 | 1 |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 | 5e-06 | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 99.9991 | 99.9531 | 0.0459979 | 99.953 | srcunit_tex_read_lookup_hit_miss | 8.39672e+09 | 72052 | 1 | 2.30566e+06 | 1.2675e+08 | 54.9733 | 2.68698e+11 | 2.68698e+11 | 1 |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 0 | 3e-06 | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 99.9996 | 99.9517 | 0.0478797 | 99.9517 | srcunit_tex_read_lookup_hit_miss | 1.67935e+10 | 73440 | 1 | 2.35008e+06 | 2.60107e+08 | 110.68 | 5.37395e+11 | 5.37395e+11 | 1 |
| reg_mma_W2048_B8_RF1 | reg_mma |  | 86.7637 | aggregate_fallback | 0 | 0 | 0 |  | 30.9809 |  | 39.2252 | aggregate_fallback | 0 | 0 |  | 0 | 5.39174e+06 |  | 0 |  |  |
| reg_mma_W2048_B8_RF16 | reg_mma |  | 86.7678 | aggregate_fallback | 0 | 0 | 0 |  | 22.169 |  | 22.8784 | aggregate_fallback | 0 | 0 |  | 0 | 1.02565e+08 |  | 0 |  |  |
| reg_mma_W2048_B8_RF2 | reg_mma |  | 86.7631 | aggregate_fallback | 0 | 0 | 0 |  | 37.2597 |  | 42.0908 | aggregate_fallback | 0 | 0 |  | 0 | 6.48794e+06 |  | 0 |  |  |
| reg_mma_W2048_B8_RF4 | reg_mma |  | 86.7619 | aggregate_fallback | 0 | 0 | 0 |  | 23.6541 |  | 25.7636 | aggregate_fallback | 0 | 0 |  | 0 | 2.406e+07 |  | 0 |  |  |
| reg_mma_W2048_B8_RF8 | reg_mma |  | 86.7655 | aggregate_fallback | 0 | 0 | 0 |  | 20.5344 |  | 21.7428 | aggregate_fallback | 0 | 0 |  | 0 | 5.68188e+07 |  | 0 |  |  |
| reg_operand_only_W2048_B8_RF1 | reg_operand_only |  | 80.6603 | aggregate_fallback | 0 | 0 | 0 |  | 23.2597 |  | 37.9644 | aggregate_fallback | 0 | 0 |  | 0 | 4.23066e+06 |  | 0 |  |  |
| reg_operand_only_W2048_B8_RF16 | reg_operand_only |  | 81.1823 | aggregate_fallback | 0 | 0 | 0 |  | 24.91 |  | 28.8315 | aggregate_fallback | 0 | 0 |  | 0 | 1.98465e+07 |  | 0 |  |  |
| reg_operand_only_W2048_B8_RF2 | reg_operand_only |  | 83.7473 | aggregate_fallback | 0 | 0 | 0 |  | 31.4312 |  | 51.5384 | aggregate_fallback | 0 | 0 |  | 0 | 1.97619e+06 |  | 0 |  |  |
| reg_operand_only_W2048_B8_RF4 | reg_operand_only |  | 81.4177 | aggregate_fallback | 0 | 0 | 0 |  | 93.5066 |  | 96.0948 | aggregate_fallback | 0 | 0 |  | 0 | 120704 |  | 0 |  |  |
| reg_operand_only_W2048_B8_RF8 | reg_operand_only |  | 81.2047 | aggregate_fallback | 0 | 0 | 0 |  | 14.384 |  | 19.343 | aggregate_fallback | 0 | 0 |  | 0 | 1.92977e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR1 | shared_scalar_load_only |  | 17.9497 | aggregate_fallback | 0 | 0 | 0 |  | 19.5439 |  | 20.2703 | aggregate_fallback | 0 | 0 |  | 0 | 1.98324e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 17.6448 | aggregate_fallback | 0 | 0 | 0 |  | 20.6004 |  | 21.0447 | aggregate_fallback | 0 | 0 |  | 0 | 2.41707e+08 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR2 | shared_scalar_load_only |  | 17.7591 | aggregate_fallback | 0 | 0 | 0 |  | 25.6956 |  | 26.1627 | aggregate_fallback | 0 | 0 |  | 0 | 2.5714e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 18.2927 | aggregate_fallback | 0 | 0 | 0 |  | 18.6165 |  | 18.9468 | aggregate_fallback | 0 | 0 |  | 0 | 7.30067e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 17.5305 | aggregate_fallback | 0 | 0 | 0 |  | 20.3483 |  | 20.8282 | aggregate_fallback | 0 | 0 |  | 0 | 1.2246e+08 |  | 0 |  |  |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| dram_cg_load_only_W8192_B8_LR1 | dram_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| dram_cg_load_only_W8192_B8_LR16 | dram_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| dram_cg_load_only_W8192_B8_LR4 | dram_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| dram_cg_load_only_W8192_B8_LR8 | dram_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR1 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR16 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR4 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_dram_W8192_B8_LR8 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR1 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR2 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l2_W64_B8_LR1 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l2_W64_B8_LR2 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR1 | global_l1_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR2 | global_l1_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| l2_cg_load_only_W64_B8_LR1 | l2_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| l2_cg_load_only_W64_B8_LR2 | l2_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| reg_mma_W2048_B8_RF1 | reg_mma | application | none | 4 | normal | contiguous | 1.17965e+06 | 1.312e+08 | 6.56e+07 | 2 |
| reg_mma_W2048_B8_RF16 | reg_mma | application | none | 4 | normal | contiguous | 1.17965e+06 | 2.0992e+09 | 1.0496e+09 | 2 |
| reg_mma_W2048_B8_RF2 | reg_mma | application | none | 4 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 |
| reg_mma_W2048_B8_RF4 | reg_mma | application | none | 4 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 |
| reg_mma_W2048_B8_RF8 | reg_mma | application | none | 4 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 |
| reg_operand_only_W2048_B8_RF1 | reg_operand_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B8_RF16 | reg_operand_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B8_RF2 | reg_operand_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B8_RF4 | reg_operand_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B8_RF8 | reg_operand_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR1 | shared_scalar_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR2 | shared_scalar_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | application | none | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B8 | clocked_empty | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W8192_B8_LR1 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W8192_B8_LR16 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W8192_B8_LR4 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W8192_B8_LR8 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W8192_B8_LR1 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W8192_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W8192_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W8192_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR1 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR2 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR1 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR2 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR1 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR2 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR1 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR2 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B8_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B8_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B8_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B8_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B8_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B8_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B8_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B8_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B8_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B8_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR1 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR2 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
