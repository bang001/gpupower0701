# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | sass | 0 | 0 | 17.9878 | 20.2982 | 0 sectors | 0 | 1.86478e+06 | 0 | 0 | 7.42929e+07 | 5.96728e+07 | 0 | 0.002611 | 0.000554 | 378.947 | 5.06264 | 16.5866 | 16 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4924 | 0 | 0 sectors | 0 | 7.46664e+06 | 0 | 0 | 3.09062e+08 | 2.38932e+08 | 0 | 0.000396 | 48.8304 | 194.361 | 13.9933 | 16.6667 | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 18.0259 | 21.6291 | 0 sectors | 0 | 1.98804e+06 | 0 | 0 | 8.10562e+07 | 6.36173e+07 | 0 | 0.002452 | 46.5081 | 195.714 | 15.0795 | 16.6666 | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4162 | 100 | 0 sectors | 0 | 4.16368e+06 | 0 | 0 | 1.65836e+08 | 1.33238e+08 | 0 | 0.000808 | 48.0296 | 194.828 | 14.3679 | 16.6666 | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 0.282692 | 3.35872e+10 sectors | 20992 | 8.70122e+06 | 0 | 1.07479e+12 | 3.51922e+08 | 2.78439e+08 | 0 | 2.59079 | 62.3338 | 319.202 | 11.511 | 16.6665 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9998 | 100 | 8.3968e+09 sectors | 20992 | 2.37498e+06 | 0 | 2.68698e+11 | 9.54161e+07 | 7.59992e+07 | 0 | 1.48444 | 59.0473 | 325.616 | 11.6589 | 16.6508 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 12.9492 | 1.67936e+10 sectors | 20992 | 4.39776e+06 | 0 | 5.37395e+11 | 1.78862e+08 | 1.40728e+08 | 0 | 2.04036 | 60.8327 | 321.028 | 11.5024 | 16.6637 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| reg_mma_W1_B16_RF1 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7925 | 24.5555 | 0 sectors | 0 | 507320 | 0 | 0 | 2.12335e+07 | 1.62342e+07 | 2.624e+08 | 0.03333 | 0.007978 | 125.651 | 24.1031 | 23.1075 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF16 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7834 | 19.234 | 0 sectors | 218587 | 7.83204e+06 | 0 | 0 | 3.21645e+08 | 2.50625e+08 | 4.1984e+09 | 0.00153 | 0.000332 | 93.8462 | 24.0188 | 22.3367 | 28 | 0 | 0 | ok | l2_read_sector_conservation_failed |
| reg_mma_W1_B16_RF2 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.8084 | 19.8343 | 0 sectors | 0 | 1.17243e+06 | 0 | 0 | 4.64013e+07 | 3.75178e+07 | 5.248e+08 | 0.010975 | 0.002313 | 80.2379 | 28.3167 | 22.7674 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF4 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7828 | 100 | 0 sectors | 0 | 1.85038e+06 | 0 | 0 | 7.60707e+07 | 5.92123e+07 | 1.0496e+09 | 0.011979 | 0.00126 | 98.3565 | 26.4457 | 22.5445 | 28 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B16_RF8 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.807 | 100 | 0 sectors | 0 | 3.67086e+06 | 0 | 0 | 1.49844e+08 | 1.17467e+08 | 2.0992e+09 | 0.003086 | 0.000638 | 95.4214 | 24.8122 | 22.4732 | 28 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6725 | 33.1273 | 0 sectors | 0 | 104312 | 0 | 0 | 4.71046e+06 | 3.33798e+06 | 6.56e+07 | 0.023499 | 0.007734 | 123.532 | 0 | 8.25931 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6689 | 22.8945 | 0 sectors | 0 | 1.86496e+06 | 0 | 0 | 7.74567e+07 | 5.96788e+07 | 1.0496e+09 | 0.001051 | 0.000316 | 92.781 | 0 | 8.21263 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF2 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6701 | 12.6036 | 0 sectors | 0 | 563000 | 0 | 0 | 2.06905e+07 | 1.8016e+07 | 1.312e+08 | 0.007569 | 0.002273 | 78.8482 | 0 | 8.17977 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6678 | 22.9866 | 0 sectors | 0 | 542200 | 0 | 0 | 2.21948e+07 | 1.73504e+07 | 2.624e+08 | 0.004031 | 0.001205 | 96.9397 | 0 | 8.19508 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF8 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6748 | 29.0776 | 0 sectors | 0 | 704588 | 0 | 0 | 3.19801e+07 | 2.25468e+07 | 5.248e+08 | 0.002047 | 0.000622 | 94.211 | 0 | 8.20119 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF1 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7684 | 14.069 | 0 sectors | 0 | 506752 | 0 | 0 | 1.89455e+07 | 1.62161e+07 | 1.312e+08 | 0.030383 | 0.007543 | 125.201 | 9.47296 | 14.2325 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF16 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7672 | 100 | 0 sectors | 0 | 3.74043e+06 | 0 | 0 | 1.50091e+08 | 1.19694e+08 | 2.0992e+09 | 0.001434 | 0.00031 | 93.6416 | 12.9148 | 13.8258 | 28 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B8_RF2 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7625 | 20.4351 | 0 sectors | 0 | 575600 | 0 | 0 | 2.31177e+07 | 1.84192e+07 | 2.624e+08 | 0.010237 | 0.002224 | 79.9052 | 15.7542 | 14.0553 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF4 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7655 | 30.0913 | 0 sectors | 0 | 627044 | 0 | 0 | 2.87255e+07 | 2.00654e+07 | 5.248e+08 | 0.007687 | 0.001182 | 97.9822 | 14.0941 | 13.9473 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF8 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7596 | 22.3695 | 0 sectors | 0 | 1.87136e+06 | 0 | 0 | 7.56824e+07 | 5.98836e+07 | 1.0496e+09 | 0.002749 | 0.00061 | 95.1302 | 13.2735 | 13.8572 | 28 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 85.9965 | 97.5903 | 0 sectors | 0 | 30036 | 0 | 0 | 1.78083e+06 | 961152 | 0 | 1.15279 | 0.121717 | 161.708 | 158.583 | 27.164 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.7419 | 20.0641 | 0 sectors | 0 | 1.22694e+06 | 0 | 0 | 4.84035e+07 | 3.92622e+07 | 0 | 0.00561 | 0.001223 | 259.223 | 39.7015 | 33.0089 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.7814 | 54.1826 | 0 sectors | 0 | 84364 | 0 | 0 | 5.50931e+06 | 2.69965e+06 | 0 | 0.031057 | 0.006377 | 184.213 | 77.326 | 30.7864 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.6531 | 17.6295 | 0 sectors | 0 | 620872 | 0 | 0 | 2.38504e+07 | 1.98679e+07 | 0 | 0.017687 | 0.004118 | 241.935 | 57.1422 | 32.603 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.7337 | 24.6813 | 0 sectors | 0 | 569020 | 0 | 0 | 2.39044e+07 | 1.82086e+07 | 0 | 0.01032 | 0.00228 | 252.727 | 44.4162 | 32.6722 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 76.7304 | 72.9231 | 0 sectors | 0 | 3852 | 0 | 0 | 880928 | 123264 | 0 | 0.881465 | 0.121855 | 161.682 | 0 | 8.32582 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 82.0758 | 25.3389 | 0 sectors | 0 | 622212 | 0 | 0 | 2.64181e+07 | 1.99108e+07 | 0 | 0.00381 | 0.001187 | 259.223 | 0 | 8.33329 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 75.452 | 100.243 | 0 sectors | 0 | 116 | 0 | 0 | 1.58096e+06 | 3712 | 0 | 0.020741 | 0.006424 | 184.212 | 0 | 8.33304 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range;l2_native_read_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 75.8687 | 0 | 0 sectors | 0 | 407556 | 0 | 0 | 1.55712e+07 | 1.30418e+07 | 0 | 0.01981 | 0.003942 | 241.935 | 0 | 8.33319 | 16 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 76.9552 | 46.4425 | 0 sectors | 0 | 141724 | 0 | 0 | 8.3159e+06 | 4.53517e+06 | 0 | 0.007167 | 0.002224 | 252.727 | 0 | 8.33325 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 82.7644 | 97.7327 | 0 sectors | 0 | 140 | 0 | 0 | 1.31114e+06 | 4480 | 0 | 0.642184 | 0.118607 | 161.694 | 53.791 | 16.6376 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 83.2917 | 0 | 0 sectors | 0 | 1.09006e+06 | 0 | 0 | 4.25989e+07 | 3.48819e+07 | 0 | 0.008066 | 0.001238 | 259.223 | 3.85545 | 16.4675 | 16 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 83.6708 | 40.6777 | 0 sectors | 0 | 101376 | 0 | 0 | 5.34339e+06 | 3.24403e+06 | 0 | 0.028089 | 0.006512 | 184.212 | 20.0094 | 16.2621 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 84.2152 | 22.5409 | 0 sectors | 0 | 308724 | 0 | 0 | 1.29919e+07 | 9.87917e+06 | 0 | 0.024137 | 0.004057 | 241.935 | 12.3574 | 16.3166 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 83.3541 | 0 | 0 sectors | 0 | 541532 | 0 | 0 | 2.20073e+07 | 1.7329e+07 | 0 | 0.012599 | 0.002317 | 252.727 | 7.41139 | 16.4883 | 16 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.8354 | 40.4289 | 0 sectors | 0 | 7.40745e+06 | 5.37395e+06 | 0 | 2.99259e+08 | 2.37038e+08 | 0 | 0.000519 | 58.7973 | 236.047 | 11.7798 | 16.6667 | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.9116 | 20.764 | 0 sectors | 0 | 1.88088e+06 | 5.37395e+06 | 0 | 7.65081e+07 | 6.0188e+07 | 0 | 0.002941 | 55.705 | 235.174 | 12.3575 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.7591 | 0 | 0 sectors | 0 | 3.66058e+06 | 5.37395e+06 | 0 | 1.48595e+08 | 1.17139e+08 | 0 | 0.001028 | 57.7236 | 235.744 | 11.9804 | 16.6666 | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 64 | 8 | 8.39684e+09 | sass | 0 | 8.39684e+09 | 18.1402 | 100 | 0 sectors | 467539 | 8.52655e+06 | 1.0748e+12 | 0 | 3.48668e+08 | 2.7285e+08 | 0 | 0.000602 | 92.1789 | 300.036 | 14.5218 | 16.6659 | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 64 | 8 | 2.09924e+09 | sass | 0 | 2.09924e+09 | 18.2546 | 22.0431 | 0 sectors | 0 | 1.87536e+06 | 2.68703e+11 | 0 | 7.6681e+07 | 6.00116e+07 | 0 | 0.002227 | 86.5875 | 294.287 | 11.614 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 64 | 8 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 17.9878 | 21.9887 | 0 sectors | 0 | 3.73533e+06 | 5.37401e+11 | 0 | 1.5247e+08 | 1.19531e+08 | 0 | 0.001231 | 89.9917 | 297.803 | 13.3088 | 16.6659 | 26 | 0 | 8192 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 17.9878 | aggregate_fallback | 0 | 0 | 0 |  | 19.8411 |  | 20.2982 | aggregate_fallback | 0 | 0 |  | 0 | 5.96728e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 17.4924 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.5847 | 21.5847 | 22.3417 | srcunit_tex_read_lookup_hit_miss | 0 | 221911 |  | 7.10115e+06 | 2.38932e+08 | 33.647 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 18.0259 | aggregate_fallback | 0 | 0 | 0 |  | 21.0668 |  | 21.6291 | aggregate_fallback | 0 | 0 |  | 0 | 6.36173e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 17.4162 | aggregate_fallback | 0 | 0 | 0 | 100 | 19.7483 | 80.2517 | 26.7821 | srcunit_tex_device_read_lookup_hit_miss | 29521 | 0 |  | 0 | 1.33238e+08 |  | 0 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 1.07479e+12 | 1.07479e+12 | 671744 | 0.282692 | 20.4732 | 20.1905 | 21.001 | srcunit_tex_device_read_lookup_hit_miss | 51508 | 142620 | 6.74052 | 4.5151e+06 | 2.78439e+08 | 61.6683 | 671744 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 99.9998 | 99.9997 | global_load_lookup_hit_miss | 2.68698e+11 | 2.68697e+11 | 671744 | 100 | 21.7102 | 78.2898 | 22.2401 | srcunit_tex_device_read_lookup_hit_miss | 20992 | 0 | 1 | 0 | 7.59992e+07 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 5.37395e+11 | 5.37395e+11 | 671744 | 12.9492 | 20.878 | 7.92881 | 21.3211 | srcunit_tex_device_read_lookup_hit_miss | 20992 | 20892 | 7.72251 | 4.51581e+06 | 1.40728e+08 | 31.1635 | 671744 |  |  |
| reg_mma_W1_B16_RF1 | reg_mma |  | 86.7925 | aggregate_fallback | 0 | 0 | 0 |  | 17.9818 |  | 24.5555 | aggregate_fallback | 0 | 0 |  | 0 | 1.62342e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF16 | reg_mma |  | 86.7834 | aggregate_fallback | 0 | 0 | 0 |  | 19.5153 |  | 19.234 | aggregate_fallback | 0 | 0 | 0 | 0 | 2.41618e+08 |  | 6.99478e+06 |  |  |
| reg_mma_W1_B16_RF2 | reg_mma |  | 86.8084 | aggregate_fallback | 0 | 0 | 0 |  | 16.5002 |  | 19.8343 | aggregate_fallback | 0 | 0 |  | 0 | 3.75178e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF4 | reg_mma |  | 86.7828 | aggregate_fallback | 0 | 0 | 0 | 100 | 19.9512 | 80.0488 | 22.0624 | srcunit_tex_read_lookup_hit_miss | 30108 | 0 |  | 0 | 5.92123e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF8 | reg_mma |  | 86.807 | aggregate_fallback | 0 | 0 | 0 | 100 | 20.381 | 79.619 | 21.4484 | srcunit_tex_read_lookup_hit_miss | 70824 | 0 |  | 0 | 1.17467e+08 |  | 0 |  |  |
| reg_mma_W1_B4_RF1 | reg_mma |  | 86.6725 | aggregate_fallback | 0 | 0 | 0 |  | 24.6934 |  | 33.1273 | aggregate_fallback | 0 | 0 |  | 0 | 3.33798e+06 |  | 0 |  |  |
| reg_mma_W1_B4_RF16 | reg_mma |  | 86.6689 | aggregate_fallback | 0 | 0 | 0 |  | 21.9043 |  | 22.8945 | aggregate_fallback | 0 | 0 |  | 0 | 5.96788e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  | 86.6701 | aggregate_fallback | 0 | 0 | 0 |  | 10.7201 |  | 12.6036 | aggregate_fallback | 0 | 0 |  | 0 | 1.8016e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF4 | reg_mma |  | 86.6678 | aggregate_fallback | 0 | 0 | 0 |  | 20.7687 |  | 22.9866 | aggregate_fallback | 0 | 0 |  | 0 | 1.73504e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF8 | reg_mma |  | 86.6748 | aggregate_fallback | 0 | 0 | 0 |  | 27.7119 |  | 29.0776 | aggregate_fallback | 0 | 0 |  | 0 | 2.25468e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF1 | reg_mma |  | 86.7684 | aggregate_fallback | 0 | 0 | 0 |  | 10.0714 |  | 14.069 | aggregate_fallback | 0 | 0 |  | 0 | 1.62161e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF16 | reg_mma |  | 86.7672 | aggregate_fallback | 0 | 0 | 0 | 100 | 21.3532 | 78.6468 | 22.0845 | srcunit_tex_read_lookup_hit_miss | 28781 | 0 |  | 0 | 1.19694e+08 |  | 0 |  |  |
| reg_mma_W1_B8_RF2 | reg_mma |  | 86.7625 | aggregate_fallback | 0 | 0 | 0 |  | 17.403 |  | 20.4351 | aggregate_fallback | 0 | 0 |  | 0 | 1.84192e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF4 | reg_mma |  | 86.7655 | aggregate_fallback | 0 | 0 | 0 |  | 27.7326 |  | 30.0913 | aggregate_fallback | 0 | 0 |  | 0 | 2.00654e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF8 | reg_mma |  | 86.7596 | aggregate_fallback | 0 | 0 | 0 |  | 21.1385 |  | 22.3695 | aggregate_fallback | 0 | 0 |  | 0 | 5.98836e+07 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 85.9965 | aggregate_fallback | 0 | 0 | 0 |  | 95.4743 |  | 97.5903 | aggregate_fallback | 0 | 0 |  | 0 | 4352 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 86.7419 | aggregate_fallback | 0 | 0 | 0 |  | 16.9285 |  | 20.0641 | aggregate_fallback | 0 | 0 |  | 0 | 3.92622e+07 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF2 | reg_operand_only |  | 86.7814 | aggregate_fallback | 0 | 0 | 0 |  | 35.1832 |  | 54.1826 | aggregate_fallback | 0 | 0 |  | 0 | 2.69965e+06 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 86.6531 | aggregate_fallback | 0 | 0 | 0 |  | 11.3654 |  | 17.6295 | aggregate_fallback | 0 | 0 |  | 0 | 1.98678e+07 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF8 | reg_operand_only |  | 86.7337 | aggregate_fallback | 0 | 0 | 0 |  | 18.6111 |  | 24.6813 | aggregate_fallback | 0 | 0 |  | 0 | 1.82063e+07 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 76.7304 | aggregate_fallback | 0 | 0 | 0 |  | 31.9288 |  | 72.9231 | aggregate_fallback | 0 | 0 |  | 0 | 123264 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 82.0758 | aggregate_fallback | 0 | 0 | 0 |  | 23.1552 |  | 25.3389 | aggregate_fallback | 0 | 0 |  | 0 | 1.99108e+07 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 75.452 | aggregate_fallback | 0 | 0 | 0 |  | 100.219 |  | 100.243 | aggregate_fallback | 0 | 0 |  | 0 | 3712 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 75.8687 | aggregate_fallback | 0 | 0 | 0 | 0 | 11.3507 | 11.3507 | 15.5039 | srcunit_tex_read_lookup_hit_miss | 0 | 6046 |  | 193472 | 1.30418e+07 | 67.4092 | 0 |  |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 76.9552 | aggregate_fallback | 0 | 0 | 0 |  | 40.8861 |  | 46.4425 | aggregate_fallback | 0 | 0 |  | 0 | 4.53517e+06 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 82.7644 | aggregate_fallback | 0 | 0 | 0 |  | 93.9728 |  | 97.7327 | aggregate_fallback | 0 | 0 |  | 0 | 4480 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 83.2917 | aggregate_fallback | 0 | 0 | 0 | 0 | 16.1146 | 16.1146 | 18.7808 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 2.01562e+06 | 3.48819e+07 | 17.3058 | 0 |  |  |
| reg_operand_only_W1_B8_RF2 | reg_operand_only |  | 83.6708 | aggregate_fallback | 0 | 0 | 0 |  | 24.3698 |  | 40.6777 | aggregate_fallback | 0 | 0 |  | 0 | 3.24403e+06 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 84.2152 | aggregate_fallback | 0 | 0 | 0 |  | 16.0436 |  | 22.5409 | aggregate_fallback | 0 | 0 |  | 0 | 9.87917e+06 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF8 | reg_operand_only |  | 83.3541 | aggregate_fallback | 0 | 0 | 0 | 0 | 15.7038 | 15.7038 | 20.0061 | srcunit_tex_read_lookup_hit_miss | 0 | 148696 |  | 4.75827e+06 | 1.7329e+07 | 3.64187 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only |  | 17.8354 | aggregate_fallback | 0 | 0 | 0 | 40.4289 | 20.6753 | 19.7536 | 21.1114 | srcunit_tex_read_lookup_hit_miss | 188767 | 278144 |  | 8.90061e+06 | 2.37038e+08 | 26.6317 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only |  | 17.9116 | aggregate_fallback | 0 | 0 | 0 |  | 20.3501 |  | 20.764 | aggregate_fallback | 0 | 0 |  | 0 | 6.0188e+07 |  | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only |  | 17.7591 | aggregate_fallback | 0 | 0 | 0 | 0 | 20.6474 | 20.6474 | 21.0767 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 2.62735e+07 | 1.17139e+08 | 4.45843 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 18.1402 | aggregate_fallback | 0 | 0 | 0 | 100 | 20.9196 | 79.0804 | 25.0892 | srcunit_tex_device_read_lookup_hit_miss | 0 | 278564 | 0.404141 | 0 | 2.62808e+08 |  | 1.49612e+07 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 18.2546 | aggregate_fallback | 0 | 0 | 0 |  | 21.5209 |  | 22.0431 | aggregate_fallback | 0 | 0 |  | 0 | 6.00116e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 17.9878 | aggregate_fallback | 0 | 0 | 0 |  | 21.5929 |  | 21.9887 | aggregate_fallback | 0 | 0 |  | 0 | 1.19531e+08 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 0 |  | 5.96728e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.06914 |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 0 |  | 2.38932e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.967676 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 0 |  | 6.36173e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.983829 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 0 |  | 1.33238e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.0651 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only |  | 671744 |  | 2.78439e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.01026 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only |  | 671744 |  | 7.59992e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.0435 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only |  | 671744 |  | 1.40728e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.99273 |
| reg_mma_W1_B16_RF1 | reg_mma |  | 0 |  | 1.62342e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.05475 |
| reg_mma_W1_B16_RF16 | reg_mma |  | 6.99478e+06 |  | 2.41618e+08 | dram__bytes_read.sum |  | 9.00787e+06 | dram__bytes_write.sum | 0.0372815 | 1.02607 |
| reg_mma_W1_B16_RF2 | reg_mma |  | 0 |  | 3.75178e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.3011 |
| reg_mma_W1_B16_RF4 | reg_mma |  | 0 |  | 5.92123e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.999663 |
| reg_mma_W1_B16_RF8 | reg_mma |  | 0 |  | 1.17467e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.999669 |
| reg_mma_W1_B4_RF1 | reg_mma |  | 0 |  | 3.33798e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.833636 |
| reg_mma_W1_B4_RF16 | reg_mma |  | 0 |  | 5.96788e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.915089 |
| reg_mma_W1_B4_RF2 | reg_mma |  | 0 |  | 1.8016e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 2.11432 |
| reg_mma_W1_B4_RF4 | reg_mma |  | 0 |  | 1.73504e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.022 |
| reg_mma_W1_B4_RF8 | reg_mma |  | 0 |  | 2.25468e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.682248 |
| reg_mma_W1_B8_RF1 | reg_mma |  | 0 |  | 1.62161e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 2.10085 |
| reg_mma_W1_B8_RF16 | reg_mma |  | 0 |  | 1.19694e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.00023 |
| reg_mma_W1_B8_RF2 | reg_mma |  | 0 |  | 1.84192e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.24239 |
| reg_mma_W1_B8_RF4 | reg_mma |  | 0 |  | 2.00654e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.660257 |
| reg_mma_W1_B8_RF8 | reg_mma |  | 0 |  | 5.98836e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.998485 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 0 |  | 4352 | dram__bytes_read.sum |  | 956800 | dram__bytes_write.sum | 219.853 | 0.0116021 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 0 |  | 3.92622e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.3287 |
| reg_operand_only_W1_B16_RF2 | reg_operand_only |  | 0 |  | 2.69965e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.531722 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 0 |  | 1.98678e+07 | dram__bytes_read.sum |  | 128 | dram__bytes_write.sum | 6.44259e-06 | 2.24081 |
| reg_operand_only_W1_B16_RF8 | reg_operand_only |  | 0 |  | 1.82063e+07 | dram__bytes_read.sum |  | 2304 | dram__bytes_write.sum | 0.000126549 | 1.16147 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 0 |  | 123264 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.854102 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 0 |  | 1.99108e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.85558 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 0 |  | 3712 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00112906 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 0 |  | 1.30418e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 2.00188 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 0 |  | 4.53517e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.374929 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 0 |  | 4480 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.0219127 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 0 |  | 3.48819e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.39525 |
| reg_operand_only_W1_B8_RF2 | reg_operand_only |  | 0 |  | 3.24403e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.841588 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 0 |  | 9.87917e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.31785 |
| reg_operand_only_W1_B8_RF8 | reg_operand_only |  | 0 |  | 1.7329e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.30022 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only |  | 0 |  | 2.37038e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.03905 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only |  | 0 |  | 6.0188e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.99583 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only |  | 0 |  | 1.17139e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.01152 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 1.49612e+07 |  | 2.62808e+08 | dram__bytes_read.sum |  | 1.00421e+07 | dram__bytes_write.sum | 0.0382109 | 1.06759 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 0 |  | 6.00116e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.942918 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 0 |  | 1.19531e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.966636 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 |  |  | 19.8411 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR16 |  | 0 | 21.5847 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR4 |  |  | 21.0668 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR8 | 100 | 100 | 19.7483 |  |  |  |  | 0/29432/0 | // |  |  | // |  | // |
| global_l1_load_only_W8_B8_LR16 | 0.282692 | 26.533 | 20.4732 |  |  |  |  | 20992/400/141097 | // |  |  | 0// | 414.502 | 0/100/0 |
| global_l1_load_only_W8_B8_LR4 | 100 | 100 | 21.7102 |  |  |  |  | 20992/20992/0 | // |  |  | 1// | 113.137 | 0/100/0 |
| global_l1_load_only_W8_B8_LR8 | 12.9492 | 50.1194 | 20.878 |  |  |  |  | 20992/20992/141119 | // |  |  | 0// | 209.497 | 0/100/0 |
| reg_mma_W1_B16_RF1 |  |  | 17.9818 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF16 |  |  | 19.5153 |  |  |  |  | 216455/0/0 | // |  |  | 0// | 34.5425 | // |
| reg_mma_W1_B16_RF2 |  |  | 16.5002 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF4 |  | 100 | 19.9512 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF8 |  | 100 | 20.381 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF1 |  |  | 24.6934 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF16 |  |  | 21.9043 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF2 |  |  | 10.7201 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF4 |  |  | 20.7687 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF8 |  |  | 27.7119 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF1 |  |  | 10.0714 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF16 |  | 100 | 21.3532 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF2 |  |  | 17.403 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF4 |  |  | 27.7326 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF8 |  |  | 21.1385 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF1 |  |  | 95.4743 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF16 |  |  | 16.9285 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF2 |  |  | 35.1832 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF4 |  |  | 11.3654 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF8 |  |  | 18.6111 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  | 31.9288 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF16 |  |  | 23.1552 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF2 |  |  | 100.219 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF4 |  | 0 | 11.3507 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF8 |  |  | 40.8861 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF1 |  |  | 93.9728 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF16 | 0 |  | 16.1146 |  |  |  |  | 0/0/62988 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF2 |  |  | 24.3698 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF4 |  |  | 16.0436 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF8 |  | 0 | 15.7038 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR16 |  | 40.4289 | 20.6753 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR4 |  |  | 20.3501 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR8 | 0 |  | 20.6474 |  |  |  |  | 0/0/821047 | // |  |  | // |  | 2.54114/97.4589/0 |
| shared_scalar_load_only_W64_B8_LR16 | 100 | 0 | 20.9196 |  |  |  |  | 466063/188355/0 | // |  |  | 0// | 17.5659 | // |
| shared_scalar_load_only_W64_B8_LR4 |  |  | 21.5209 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_load_only_W64_B8_LR8 |  |  | 21.5929 |  |  |  |  | 0/0/0 | // |  |  | // |  | 2.53195/97.468/0 |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | 0 | 0 |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 0 | 0 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 0 | 0 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 0 | 0 |
| reg_mma_W1_B16_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF2 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF4 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF8 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF2 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF8 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF2 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF4 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF8 | reg_mma | 0 | 0 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | 0 | 0 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 1.07479e+12 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 2.68698e+11 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 5.37395e+11 | 5.37395e+06 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.2464e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.5866 | 33.3333 | 16 |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 7.85233e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6667 | 33.3333 | 34 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.06641e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6666 | 33.3333 | 34 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.99505e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6666 | 33.3333 | 34 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.38944e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6665 | 33.3333 | 33 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.7056e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6508 | 33.3333 | 33 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.26688e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6637 | 33.3333 | 33 |
| reg_mma_W1_B16_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.23055e+09 | 1.312e+08 | 17.0012 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 48.5666 | 23.1075 | 33.3333 | 34 |
| reg_mma_W1_B16_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 4.90689e+10 | 2.0992e+09 | 23.3751 | 4.1984e+09 | 2.0992e+09 | 2 | 1.71966e+13 | 1.71966e+13 | 1 | 45.5655 | 22.3367 | 33.3333 | 28 |
| reg_mma_W1_B16_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.82251e+09 | 2.624e+08 | 26.0004 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 46.3146 | 22.7674 | 33.3333 | 28 |
| reg_mma_W1_B16_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.28577e+10 | 5.248e+08 | 24.5002 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 45.1245 | 22.5445 | 33.3333 | 28 |
| reg_mma_W1_B16_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.49281e+10 | 1.0496e+09 | 23.7501 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 45.4193 | 22.4732 | 33.3333 | 28 |
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.57638e+08 | 3.28e+07 | 17.0012 | 6.56e+07 | 3.28e+07 | 2 | 2.68698e+11 | 2.68698e+11 | 1 | 46.6118 | 8.25931 | 33.3333 | 34 |
| reg_mma_W1_B4_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.22672e+10 | 5.248e+08 | 23.3751 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 40.6343 | 8.21263 | 33.3333 | 28 |
| reg_mma_W1_B4_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.70563e+09 | 6.56e+07 | 26.0004 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 38.9013 | 8.17977 | 33.3333 | 28 |
| reg_mma_W1_B4_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.21443e+09 | 1.312e+08 | 24.5002 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 39.0519 | 8.19508 | 33.3333 | 28 |
| reg_mma_W1_B4_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.23203e+09 | 2.624e+08 | 23.7501 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 40.0928 | 8.20119 | 33.3333 | 28 |
| reg_mma_W1_B8_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.11528e+09 | 6.56e+07 | 17.0012 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 48.3857 | 14.2325 | 33.3333 | 34 |
| reg_mma_W1_B8_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.45345e+10 | 1.0496e+09 | 23.3751 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 44.5673 | 13.8258 | 33.3333 | 28 |
| reg_mma_W1_B8_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.41126e+09 | 1.312e+08 | 26.0004 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 44.9522 | 14.0553 | 33.3333 | 28 |
| reg_mma_W1_B8_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.42886e+09 | 2.624e+08 | 24.5002 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 44.0567 | 13.9473 | 33.3333 | 28 |
| reg_mma_W1_B8_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.24641e+10 | 5.248e+08 | 23.7501 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 44.4626 | 13.8572 | 33.3333 | 28 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.06729e+08 | 1.312e+08 | 0.81348 | 0 |  |  | 0 |  |  | 0 | 27.164 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.35137e+10 | 2.0992e+09 | 6.43755 | 0 |  |  | 0 |  |  | 0 | 33.0089 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.4929e+09 | 2.624e+08 | 9.50037 | 0 |  |  | 0 |  |  | 0 | 30.7864 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 4.0673e+09 | 5.248e+08 | 7.75018 | 0 |  |  | 0 |  |  | 0 | 32.603 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 7.2161e+09 | 1.0496e+09 | 6.87509 | 0 |  |  | 0 |  |  | 0 | 32.6722 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.66821e+07 | 3.28e+07 | 0.81348 | 0 |  |  | 0 |  |  | 0 | 8.32582 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.37842e+09 | 5.248e+08 | 6.43755 | 0 |  |  | 0 |  |  | 0 | 8.33329 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.23224e+08 | 6.56e+07 | 9.50037 | 0 |  |  | 0 |  |  | 0 | 8.33304 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.01682e+09 | 1.312e+08 | 7.75018 | 0 |  |  | 0 |  |  | 0 | 8.33319 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.80402e+09 | 2.624e+08 | 6.87509 | 0 |  |  | 0 |  |  | 0 | 8.33325 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.33643e+07 | 6.56e+07 | 0.81348 | 0 |  |  | 0 |  |  | 0 | 16.6376 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.75685e+09 | 1.0496e+09 | 6.43755 | 0 |  |  | 0 |  |  | 0 | 16.4675 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.24645e+09 | 1.312e+08 | 9.50037 | 0 |  |  | 0 |  |  | 0 | 16.2621 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.03365e+09 | 2.624e+08 | 7.75018 | 0 |  |  | 0 |  |  | 0 | 16.3166 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.60805e+09 | 5.248e+08 | 6.87509 | 0 |  |  | 0 |  |  | 0 | 16.4883 | 33.3333 | 16 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.48787e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6667 | 22.9167 | 26 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.72531e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.31283e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.64819e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6659 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.51539e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.89299e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.6659 | 22.9167 | 26 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B8 | clocked_empty | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
