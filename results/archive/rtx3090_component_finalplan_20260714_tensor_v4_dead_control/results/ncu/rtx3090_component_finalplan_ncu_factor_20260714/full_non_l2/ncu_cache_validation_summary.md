# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | sass | 0 | 0 | 18.0259 | 20.3516 | 0 sectors | 0 | 1.86341e+06 | 0 | 0 | 7.45055e+07 | 5.96291e+07 | 0 | 0.002715 | 0.00055 | 378.947 | 5.83285 | 16.5758 | 16 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4543 | 19.2281 | 0 sectors | 0 | 7.56668e+06 | 0 | 0 | 3.07897e+08 | 2.42134e+08 | 0 | 0.000394 | 48.8304 | 194.361 | 13.9933 | 16.6667 | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.0732 | 100 | 0 sectors | 0 | 1.96435e+06 | 0 | 0 | 8.01757e+07 | 6.28593e+07 | 0 | 0.001523 | 46.5081 | 195.714 | 15.0795 | 16.6666 | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.2637 | 100 | 0 sectors | 0 | 4.19753e+06 | 0 | 0 | 1.68047e+08 | 1.34321e+08 | 0 | 0.000804 | 48.0296 | 194.828 | 14.3679 | 16.6666 | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 100 | 3.35872e+10 sectors | 20992 | 8.395e+06 | 0 | 1.07479e+12 | 3.39651e+08 | 2.6864e+08 | 0 | 1.90891 | 62.3875 | 319.299 | 11.4776 | 16.6665 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9998 | 51.5774 | 8.3968e+09 sectors | 20992 | 1.96177e+06 | 0 | 2.68698e+11 | 8.24601e+07 | 6.27767e+07 | 0 | 1.67691 | 58.5156 | 325.228 | 11.1783 | 16.6429 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 51.0605 | 1.67936e+10 sectors | 20992 | 4.5885e+06 | 0 | 5.37395e+11 | 1.85322e+08 | 1.46832e+08 | 0 | 1.74391 | 60.9679 | 321.201 | 11.4209 | 16.6643 | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| reg_mma_W1_B16_RF1 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7878 | 23.2123 | 0 sectors | 0 | 497972 | 0 | 0 | 2.12494e+07 | 1.59351e+07 | 2.624e+08 | 0.060876 | 0.006388 | 116.504 | 28.1949 | 23.3128 | 35 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF16 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7908 | 0 | 0 sectors | 0 | 6.85006e+06 | 0 | 0 | 2.79408e+08 | 2.19202e+08 | 4.1984e+09 | 0.002795 | 0.000389 | 93.3754 | 23.9967 | 22.138 | 30 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B16_RF2 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.789 | 19.5918 | 0 sectors | 0 | 1.09222e+06 | 0 | 0 | 4.38329e+07 | 3.49512e+07 | 5.248e+08 | 0.011932 | 0.002777 | 103.438 | 29.1549 | 22.9035 | 26 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF4 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7787 | 21.7812 | 0 sectors | 0 | 1.87118e+06 | 0 | 0 | 7.63062e+07 | 5.98778e+07 | 1.0496e+09 | 0.00643 | 0.001484 | 97.6788 | 25.5759 | 22.2315 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF8 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7943 | 100 | 0 sectors | 0 | 3.54844e+06 | 0 | 0 | 1.44398e+08 | 1.1355e+08 | 2.0992e+09 | 0.003143 | 0.000767 | 94.8536 | 24.2651 | 22.1579 | 30 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6678 | 98.0527 | 0 sectors | 0 | 396 | 0 | 0 | 1.33926e+06 | 12672 | 6.56e+07 | 0.04081 | 0.006072 | 116.032 | 0 | 8.25413 | 35 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6678 | 22.0912 | 0 sectors | 0 | 1.86706e+06 | 0 | 0 | 7.63858e+07 | 5.97459e+07 | 1.0496e+09 | 0.00114 | 0.000375 | 92.5441 | 0 | 8.22481 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF2 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6701 | 103.703 | 0 sectors | 0 | 464 | 0 | 0 | 2.4783e+06 | 14848 | 1.312e+08 | 0.008052 | 0.002671 | 102.476 | 0 | 8.17482 | 26 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range;l2_native_read_hit_rate_pct_out_of_range |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6583 | 19.2634 | 0 sectors | 0 | 618992 | 0 | 0 | 2.4428e+07 | 1.98077e+07 | 2.624e+08 | 0.004364 | 0.001424 | 97.0843 | 0 | 8.20184 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF8 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6654 | 24.5211 | 0 sectors | 0 | 836296 | 0 | 0 | 3.525e+07 | 2.67615e+07 | 5.248e+08 | 0.003541 | 0.000737 | 94.1097 | 0 | 8.20882 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF1 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7655 | 100 | 0 sectors | 0 | 93508 | 0 | 0 | 5.56202e+06 | 2.99226e+06 | 1.312e+08 | 0.034385 | 0.00585 | 115.831 | 12.0979 | 13.7725 | 35 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B8_RF16 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7737 | 100 | 0 sectors | 0 | 3.55954e+06 | 0 | 0 | 1.43929e+08 | 1.13905e+08 | 2.0992e+09 | 0.001573 | 0.000365 | 93.0521 | 11.3221 | 13.5698 | 30 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W1_B8_RF2 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7643 | 18.9401 | 0 sectors | 0 | 622116 | 0 | 0 | 2.46593e+07 | 1.99077e+07 | 2.624e+08 | 0.011103 | 0.002595 | 103.494 | 13.5656 | 13.8807 | 26 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF4 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.769 | 20.564 | 0 sectors | 0 | 1.10737e+06 | 0 | 0 | 4.36135e+07 | 3.54358e+07 | 5.248e+08 | 0.008775 | 0.001386 | 97.5005 | 12.2647 | 13.4783 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF8 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7684 | 21.5009 | 0 sectors | 0 | 1.7856e+06 | 0 | 0 | 7.1813e+07 | 5.71392e+07 | 1.0496e+09 | 0.002937 | 0.000712 | 94.6605 | 11.4943 | 13.5679 | 30 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 78.6962 | 134.929 | 0 sectors | 0 | 128 | 0 | 0 | 2.62154e+06 | 4096 | 0 | 985.362 | 263.177 | 223.715 | 21.9042 | 20.6561 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 75.0256 | 108.135 | 0 sectors | 0 | 96 | 0 | 0 | 3.29814e+06 | 3072 | 0 | 982.974 | 536.445 | 222.63 | 19.1432 | 20.3736 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 72.136 | 93.3462 | 0 sectors | 0 | 280 | 0 | 0 | 3.69066e+06 | 8960 | 0 | 988.764 | 560.177 | 222.557 | 19.8097 | 20.3109 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 75.8593 | 119.667 | 0 sectors | 0 | 104 | 0 | 0 | 2.91558e+06 | 3328 | 0 | 952.431 | 288.868 | 223.398 | 21.2853 | 20.3295 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 72.551 | 99.0925 | 0 sectors | 0 | 240 | 0 | 0 | 3.54714e+06 | 7680 | 0 | 952.162 | 559.075 | 222.539 | 19.0395 | 20.2312 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 79.964 | 119.572 | 0 sectors | 0 | 100 | 0 | 0 | 637472 | 3200 | 0 | 548.836 | 153.452 | 191.549 | 0 | 7.43136 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 76.7245 | 98.8095 | 0 sectors | 0 | 100 | 0 | 0 | 725728 | 3200 | 0 | 551.009 | 153.843 | 191.549 | 0 | 7.43478 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 79.7038 | 99.1361 | 0 sectors | 0 | 212 | 0 | 0 | 648256 | 6784 | 0 | 554.509 | 153.581 | 191.549 | 0 | 7.43167 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 77.7015 | 90.7102 | 0 sectors | 0 | 292 | 0 | 0 | 705120 | 9344 | 0 | 555.492 | 153.852 | 191.549 | 0 | 7.44362 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 79.6979 | 99.9802 | 0 sectors | 0 | 100 | 0 | 0 | 644928 | 3200 | 0 | 598.317 | 153.405 | 191.549 | 0 | 7.43097 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 81.5066 | 99.6124 | 0 sectors | 0 | 100 | 0 | 0 | 1.40355e+06 | 3200 | 0 | 785.143 | 166.446 | 208.176 | 16.3075 | 13.2193 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 81.8545 | 100.151 | 0 sectors | 0 | 100 | 0 | 0 | 1.3743e+06 | 3200 | 0 | 806.065 | 165.414 | 208.039 | 16.2184 | 13.1648 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 81.6891 | 101.621 | 0 sectors | 0 | 100 | 0 | 0 | 1.39168e+06 | 3200 | 0 | 825.598 | 168.792 | 208.146 | 16.1425 | 13.2294 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 81.1441 | 101.071 | 0 sectors | 0 | 212 | 0 | 0 | 1.41091e+06 | 6784 | 0 | 811.575 | 169.635 | 208.272 | 16.137 | 13.166 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 80.3654 | 96.6203 | 0 sectors | 0 | 228 | 0 | 0 | 1.45811e+06 | 7296 | 0 | 813.356 | 172.173 | 208.277 | 16.2962 | 13.2536 | 16 | 0 | 0 | ok |  |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.6067 | 0 | 0 sectors | 0 | 6.89215e+06 | 5.37395e+06 | 0 | 2.80376e+08 | 2.20549e+08 | 0 | 0.000521 | 58.7973 | 236.047 | 11.7798 | 16.6667 | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.4924 | 21.8 | 0 sectors | 0 | 1.87721e+06 | 5.37395e+06 | 0 | 7.58694e+07 | 6.00708e+07 | 0 | 0.002135 | 55.705 | 235.174 | 12.3575 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 18.1402 | 23.1538 | 0 sectors | 0 | 3.24184e+06 | 5.37395e+06 | 0 | 1.34373e+08 | 1.03739e+08 | 0 | 0.001026 | 57.7237 | 235.744 | 11.9804 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 64 | 8 | 8.39684e+09 | sass | 0 | 8.39684e+09 | 18.1784 | 21.0876 | 0 sectors | 0 | 7.54339e+06 | 1.0748e+12 | 0 | 3.06177e+08 | 2.41388e+08 | 0 | 0.00081 | 91.933 | 299.64 | 13.868 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 64 | 8 | 2.09924e+09 | sass | 0 | 2.09924e+09 | 17.8354 | 21.4608 | 0 sectors | 0 | 1.98599e+06 | 2.68703e+11 | 0 | 8.02771e+07 | 6.35517e+07 | 0 | 0.002333 | 86.6222 | 294.404 | 11.6515 | 16.6666 | 26 | 0 | 8192 | ok |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 64 | 8 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 18.1784 | 20.1309 | 0 sectors | 0 | 4.16835e+06 | 5.37401e+11 | 0 | 1.66353e+08 | 1.33387e+08 | 0 | 0.00118 | 90.0004 | 298.034 | 13.6293 | 16.6666 | 26 | 0 | 8192 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 18.0259 | aggregate_fallback | 0 | 0 | 0 |  | 19.7373 |  | 20.3516 | aggregate_fallback | 0 | 0 |  | 0 | 5.96291e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 17.4543 | aggregate_fallback | 0 | 0 | 0 | 19.2281 | 21.4086 | 2.18047 | 21.9567 | srcunit_tex_read_lookup_hit_miss | 29553 | 124144 |  | 3.97261e+06 | 2.42134e+08 | 60.9508 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 17.0732 | aggregate_fallback | 0 | 0 | 0 | 100 | 22.8313 | 77.1687 | 38.514 | srcunit_tex_device_read_lookup_hit_miss | 10030 | 0 |  | 0 | 6.28593e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 17.2637 | aggregate_fallback | 0 | 0 | 0 | 100 | 19.5857 | 80.4143 | 27.794 | srcunit_tex_device_read_lookup_hit_miss | 0 | 124176 |  | 0 | 1.34321e+08 |  | 0 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 1.07479e+12 | 1.07479e+12 | 671744 | 100 | 21.172 | 78.828 | 21.8402 | srcunit_tex_device_read_lookup_hit_miss | 1772 | 142531 | 1 | 0 | 2.6864e+08 |  | 671744 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 99.9998 | 99.9997 | global_load_lookup_hit_miss | 2.68698e+11 | 2.68697e+11 | 671744 | 51.5774 | 24.5421 | 27.0353 | 25.0043 | srcunit_tex_device_read_lookup_hit_miss | 20992 | 19248 | 1.93883 | 630656 | 6.27767e+07 | 99.5419 | 671744 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 5.37395e+11 | 5.37395e+11 | 671744 | 51.0605 | 19.8396 | 31.2209 | 20.244 | srcunit_tex_device_read_lookup_hit_miss | 20992 | 0 | 1.95846 | 643840 | 1.46832e+08 | 228.057 | 671744 |  |  |
| reg_mma_W1_B16_RF1 | reg_mma |  | 86.7878 | aggregate_fallback | 0 | 0 | 0 |  | 17.0909 |  | 23.2123 | aggregate_fallback | 0 | 0 |  | 0 | 1.59351e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF16 | reg_mma |  | 86.7908 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.7409 | 21.7409 | 22.6858 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 8.06074e+06 | 2.19202e+08 | 27.1938 | 0 |  |  |
| reg_mma_W1_B16_RF2 | reg_mma |  | 86.789 | aggregate_fallback | 0 | 0 | 0 |  | 16.5238 |  | 19.5918 | aggregate_fallback | 0 | 0 |  | 0 | 3.49512e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF4 | reg_mma |  | 86.7787 | aggregate_fallback | 0 | 0 | 0 |  | 19.6909 |  | 21.7812 | aggregate_fallback | 0 | 0 |  | 0 | 5.98778e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF8 | reg_mma |  | 86.7943 | aggregate_fallback | 0 | 0 | 0 | 100 | 20.4635 | 79.5365 | 28.993 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 0 | 1.1355e+08 |  | 0 |  |  |
| reg_mma_W1_B4_RF1 | reg_mma |  | 86.6678 | aggregate_fallback | 0 | 0 | 0 |  | 97.1161 |  | 98.0527 | aggregate_fallback | 0 | 0 |  | 0 | 12672 |  | 0 |  |  |
| reg_mma_W1_B4_RF16 | reg_mma |  | 86.6678 | aggregate_fallback | 0 | 0 | 0 |  | 21.2382 |  | 22.0912 | aggregate_fallback | 0 | 0 |  | 0 | 5.97459e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  | 86.6701 | aggregate_fallback | 0 | 0 | 0 |  | 104.592 |  | 103.703 | aggregate_fallback | 0 | 0 |  | 0 | 14848 |  | 0 |  |  |
| reg_mma_W1_B4_RF4 | reg_mma |  | 86.6583 | aggregate_fallback | 0 | 0 | 0 |  | 17.4908 |  | 19.2634 | aggregate_fallback | 0 | 0 |  | 0 | 1.98077e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF8 | reg_mma |  | 86.6654 | aggregate_fallback | 0 | 0 | 0 |  | 23.0169 |  | 24.5211 | aggregate_fallback | 0 | 0 |  | 0 | 2.67615e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF1 | reg_mma |  | 86.7655 | aggregate_fallback | 0 | 0 | 0 | 100 | 36.4829 | 63.5171 | 45.7359 | srcunit_tex_read_lookup_hit_miss | 28763 | 0 |  | 0 | 2.99226e+06 |  | 0 |  |  |
| reg_mma_W1_B8_RF16 | reg_mma |  | 86.7737 | aggregate_fallback | 0 | 0 | 0 | 100 | 20.3008 | 79.6992 | 21.0543 | srcunit_tex_read_lookup_hit_miss | 14538 | 0 |  | 0 | 1.13905e+08 |  | 0 |  |  |
| reg_mma_W1_B8_RF2 | reg_mma |  | 86.7643 | aggregate_fallback | 0 | 0 | 0 |  | 15.9569 |  | 18.9401 | aggregate_fallback | 0 | 0 |  | 0 | 1.99077e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF4 | reg_mma |  | 86.769 | aggregate_fallback | 0 | 0 | 0 |  | 18.5576 |  | 20.564 | aggregate_fallback | 0 | 0 |  | 0 | 3.54358e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF8 | reg_mma |  | 86.7684 | aggregate_fallback | 0 | 0 | 0 |  | 20.2397 |  | 21.5009 | aggregate_fallback | 0 | 0 |  | 0 | 5.65171e+07 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 78.6962 | aggregate_fallback | 0 | 0 | 0 |  | 88.9023 |  | 134.929 | aggregate_fallback | 0 | 0 |  | 0 | 4096 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 75.0256 | aggregate_fallback | 0 | 0 | 0 |  | 89.2473 |  | 108.135 | aggregate_fallback | 0 | 0 |  | 0 | 3072 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF2 | reg_operand_only |  | 72.136 | aggregate_fallback | 0 | 0 | 0 |  | 72.3092 |  | 93.3462 | aggregate_fallback | 0 | 0 |  | 0 | 8960 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 75.8593 | aggregate_fallback | 0 | 0 | 0 |  | 88.411 |  | 119.667 | aggregate_fallback | 0 | 0 |  | 0 | 3328 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF8 | reg_operand_only |  | 72.551 | aggregate_fallback | 0 | 0 | 0 |  | 75.6423 |  | 99.0925 | aggregate_fallback | 0 | 0 |  | 0 | 7680 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 79.964 | aggregate_fallback | 0 | 0 | 0 |  | 88.7255 |  | 119.572 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 76.7245 | aggregate_fallback | 0 | 0 | 0 |  | 87.1359 |  | 98.8095 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 79.7038 | aggregate_fallback | 0 | 0 | 0 |  | 77.6344 |  | 99.1361 | aggregate_fallback | 0 | 0 |  | 0 | 6784 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 77.7015 | aggregate_fallback | 0 | 0 | 0 |  | 71.4851 |  | 90.7102 | aggregate_fallback | 0 | 0 |  | 0 | 9344 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 79.6979 | aggregate_fallback | 0 | 0 | 0 |  | 86.2697 |  | 99.9802 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 81.5066 | aggregate_fallback | 0 | 0 | 0 |  | 87.4396 |  | 99.6124 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 81.8545 | aggregate_fallback | 0 | 0 | 0 |  | 88 |  | 100.151 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF2 | reg_operand_only |  | 81.6891 | aggregate_fallback | 0 | 0 | 0 |  | 87.9081 |  | 101.621 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 81.1441 | aggregate_fallback | 0 | 0 | 0 |  | 77.3163 |  | 101.071 | aggregate_fallback | 0 | 0 |  | 0 | 6784 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF8 | reg_operand_only |  | 80.3654 | aggregate_fallback | 0 | 0 | 0 |  | 76.2605 |  | 96.6203 | aggregate_fallback | 0 | 0 |  | 0 | 7296 |  | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only |  | 17.6067 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.5808 | 21.5808 | 22.0405 | srcunit_tex_read_lookup_hit_miss | 0 | 278266 |  | 8.90451e+06 | 2.20549e+08 | 24.7682 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only |  | 17.4924 | aggregate_fallback | 0 | 0 | 0 |  | 21.186 |  | 21.8 | aggregate_fallback | 0 | 0 |  | 0 | 6.00708e+07 |  | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only |  | 18.1402 | aggregate_fallback | 0 | 0 | 0 |  | 22.8066 |  | 23.1538 | aggregate_fallback | 0 | 0 |  | 0 | 1.03739e+08 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 18.1784 | aggregate_fallback | 0 | 0 | 0 |  | 20.6619 |  | 21.0876 | aggregate_fallback | 0 | 0 |  | 0 | 2.41388e+08 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 17.8354 | aggregate_fallback | 0 | 0 | 0 |  | 20.9902 |  | 21.4608 | aggregate_fallback | 0 | 0 |  | 0 | 6.35517e+07 |  | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 18.1784 | aggregate_fallback | 0 | 0 | 0 |  | 19.7094 |  | 20.1309 | aggregate_fallback | 0 | 0 |  | 0 | 1.33387e+08 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 0 |  | 5.96291e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00105668 |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 0 |  | 2.42134e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00097793 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 0 |  | 6.28593e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000971911 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 0 |  | 1.34321e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00107471 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only |  | 671744 |  | 2.6864e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000972327 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only |  | 671744 |  | 6.27767e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000859043 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only |  | 671744 |  | 1.46832e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00104472 |
| reg_mma_W1_B16_RF1 | reg_mma |  | 0 |  | 1.59351e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00105851 |
| reg_mma_W1_B16_RF16 | reg_mma |  | 0 |  | 2.19202e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000989925 |
| reg_mma_W1_B16_RF2 | reg_mma |  | 0 |  | 3.49512e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00123912 |
| reg_mma_W1_B16_RF4 | reg_mma |  | 0 |  | 5.98778e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00106872 |
| reg_mma_W1_B16_RF8 | reg_mma |  | 0 |  | 1.1355e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00102085 |
| reg_mma_W1_B4_RF1 | reg_mma |  | 0 |  | 12672 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 3.23826e-06 |
| reg_mma_W1_B4_RF16 | reg_mma |  | 0 |  | 5.97459e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000979478 |
| reg_mma_W1_B4_RF2 | reg_mma |  | 0 |  | 14848 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.78169e-06 |
| reg_mma_W1_B4_RF4 | reg_mma |  | 0 |  | 1.98077e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00125354 |
| reg_mma_W1_B4_RF8 | reg_mma |  | 0 |  | 2.67615e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000864771 |
| reg_mma_W1_B8_RF1 | reg_mma |  | 0 |  | 2.99226e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000395124 |
| reg_mma_W1_B8_RF16 | reg_mma |  | 0 |  | 1.13905e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00101055 |
| reg_mma_W1_B8_RF2 | reg_mma |  | 0 |  | 1.99077e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00136634 |
| reg_mma_W1_B8_RF4 | reg_mma |  | 0 |  | 3.54358e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00122555 |
| reg_mma_W1_B8_RF8 | reg_mma |  | 0 |  | 5.65171e+07 | dram__bytes_read.sum |  | 622080 | dram__bytes_write.sum | 0.0110069 | 0.000998115 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 0 |  | 4096 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 7.19101e-07 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 0 |  | 3072 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 4.89796e-07 |
| reg_operand_only_W1_B16_RF2 | reg_operand_only |  | 0 |  | 8960 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.34615e-06 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 0 |  | 3328 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 5.17413e-07 |
| reg_operand_only_W1_B16_RF8 | reg_operand_only |  | 0 |  | 7680 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.2e-06 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.34579e-07 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 8.92857e-07 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 0 |  | 6784 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.98131e-06 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 0 |  | 9344 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 2.60714e-06 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.34579e-07 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 6.53595e-07 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 6.71141e-07 |
| reg_operand_only_W1_B8_RF2 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 6.66667e-07 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 0 |  | 6784 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.38562e-06 |
| reg_operand_only_W1_B8_RF8 | reg_operand_only |  | 0 |  | 7296 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.52e-06 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only |  | 0 |  | 2.20549e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000963898 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only |  | 0 |  | 6.00708e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000996042 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only |  | 0 |  | 1.03739e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000893562 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 0 |  | 2.41388e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000981144 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 0 |  | 6.35517e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000985351 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 0 |  | 1.33387e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00107901 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 |  |  | 19.7373 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR16 |  | 19.2281 | 21.4086 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR4 | 100 | 100 | 22.8313 |  |  |  |  | 0/28710/0 | // |  |  | // |  | // |
| global_addr_only_l1_W8_B8_LR8 | 100 | 0 | 19.5857 |  |  |  |  | 0/29516/0 | // |  |  | // |  | // |
| global_l1_load_only_W8_B8_LR16 | 100 | 1.22797 | 21.172 |  |  |  |  | 20992/20992/0 | // |  |  | 1// | 399.914 | 0/100/0 |
| global_l1_load_only_W8_B8_LR4 | 51.5774 | 52.167 | 24.5421 |  |  |  |  | 20992/20992/19708 | // |  |  | 0// | 93.4533 | 0/100/0 |
| global_l1_load_only_W8_B8_LR8 | 51.0605 | 100 | 19.8396 |  |  |  |  | 20992/20992/20120 | // |  |  | 0// | 218.583 | 6.10744/93.8926/0 |
| reg_mma_W1_B16_RF1 |  |  | 17.0909 |  |  |  |  | 0/0/0 | // |  |  | // |  | 6.42794/93.5721/0 |
| reg_mma_W1_B16_RF16 | 0 |  | 21.7409 |  |  |  |  | 0/0/251898 | // |  |  | // |  | 8.40116/91.5988/0 |
| reg_mma_W1_B16_RF2 |  |  | 16.5238 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF4 |  |  | 19.6909 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF8 | 100 |  | 20.4635 |  |  |  |  | 0/28583/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF1 |  |  | 97.1161 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF16 |  |  | 21.2382 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF2 |  |  | 104.592 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF4 |  |  | 17.4908 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF8 |  |  | 23.0169 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF1 |  | 100 | 36.4829 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF16 |  | 100 | 20.3008 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF2 |  |  | 15.9569 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF4 |  |  | 18.5576 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF8 |  |  | 20.2397 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF1 |  |  | 88.9023 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF16 |  |  | 89.2473 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF2 |  |  | 72.3092 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF4 |  |  | 88.411 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF8 |  |  | 75.6423 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  | 88.7255 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF16 |  |  | 87.1359 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF2 |  |  | 77.6344 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF4 |  |  | 71.4851 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF8 |  |  | 86.2697 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF1 |  |  | 87.4396 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF16 |  |  | 88 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF2 |  |  | 87.9081 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF4 |  |  | 77.3163 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF8 |  |  | 76.2605 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR16 |  | 0 | 21.5808 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR4 |  |  | 21.186 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_addr_only_W64_B8_LR8 |  |  | 22.8066 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_load_only_W64_B8_LR16 |  |  | 20.6619 |  |  |  |  | 0/0/0 | // |  |  | // |  | 2.52747/97.4725/0 |
| shared_scalar_load_only_W64_B8_LR4 |  |  | 20.9902 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| shared_scalar_load_only_W64_B8_LR8 |  |  | 19.7094 |  |  |  |  | 0/0/0 | // |  |  | // |  | 2.53175/97.4683/0 |

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

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.5758 | 33.3333 | 16 |
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6667 | 33.3333 | 34 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 33.3333 | 34 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 33.3333 | 34 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6665 | 33.3333 | 33 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6429 | 33.3333 | 33 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6643 | 33.3333 | 33 |
| reg_mma_W1_B16_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 49.3296 | 23.3128 | 33.3333 | 35 |
| reg_mma_W1_B16_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 4.1984e+09 | 2.0992e+09 | 2 | 1.71966e+13 | 1.71966e+13 | 1 | 48.3595 | 22.138 | 33.3333 | 30 |
| reg_mma_W1_B16_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 47.3054 | 22.9035 | 33.3333 | 26 |
| reg_mma_W1_B16_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 47.7618 | 22.2315 | 33.3333 | 30 |
| reg_mma_W1_B16_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 48.1247 | 22.1579 | 33.3333 | 30 |
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.56e+07 | 3.28e+07 | 2 | 2.68698e+11 | 2.68698e+11 | 1 | 47.438 | 8.25413 | 33.3333 | 35 |
| reg_mma_W1_B4_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 43.7225 | 8.22481 | 33.3333 | 30 |
| reg_mma_W1_B4_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 39.7463 | 8.17482 | 33.3333 | 26 |
| reg_mma_W1_B4_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 41.9643 | 8.20184 | 33.3333 | 30 |
| reg_mma_W1_B4_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 43.0963 | 8.20882 | 33.3333 | 30 |
| reg_mma_W1_B8_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 49.0192 | 13.7725 | 33.3333 | 35 |
| reg_mma_W1_B8_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 47.4129 | 13.5698 | 33.3333 | 30 |
| reg_mma_W1_B8_RF2 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 45.548 | 13.8807 | 33.3333 | 26 |
| reg_mma_W1_B8_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 46.3623 | 13.4783 | 33.3333 | 30 |
| reg_mma_W1_B8_RF8 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 47.1155 | 13.5679 | 33.3333 | 30 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 20.6561 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 20.3736 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 20.3109 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 20.3295 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 20.2312 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 7.43136 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 7.43478 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 7.43167 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 7.44362 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 7.43097 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 13.2193 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 13.1648 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF2 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 13.2294 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 13.166 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF8 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 13.2536 | 33.3333 | 16 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6667 | 22.9167 | 26 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 | 16.6666 | 22.9167 | 26 |

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
