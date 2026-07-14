# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only | 2048 | 8 |  |  |  |  | 0 | 0.00736658 | 3.35872e+10 sectors | 3.35874e+10 | 3.36253e+10 |  | 1.07479e+12 | 1.0748e+12 | 1.07601e+12 |  | 681.153 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only | 2048 | 8 |  |  |  |  | 0 | 0.00677987 | 8.3968e+09 sectors | 8.39696e+09 | 8.40681e+09 |  | 2.68698e+11 | 2.68703e+11 | 2.69018e+11 |  | 654.715 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only | 2048 | 8 |  |  |  |  | 0 | 0.00739389 | 1.67936e+10 sectors | 1.67936e+10 | 1.68126e+10 |  | 5.37395e+11 | 5.37395e+11 | 5.38004e+11 |  | 680.731 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only | 256 | 8 |  |  |  |  | 0 | 0.216399 | 3.35872e+10 sectors | 3.35874e+10 | 3.35558e+10 |  | 1.07479e+12 | 1.0748e+12 | 1.07378e+12 |  | 669.539 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only | 256 | 8 |  |  |  |  | 0 | 0.219313 | 8.3968e+09 sectors | 8.3968e+09 | 8.38902e+09 |  | 2.68698e+11 | 2.68698e+11 | 2.68449e+11 |  | 643.323 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only | 256 | 8 |  |  |  |  | 0 | 0.220179 | 1.67936e+10 sectors | 1.67938e+10 | 1.6777e+10 |  | 5.37395e+11 | 5.374e+11 | 5.36863e+11 |  | 670.85 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only | 512 | 8 |  |  |  |  | 0 | 0.0670954 | 3.35872e+10 sectors | 3.35874e+10 | 3.36054e+10 |  | 1.07479e+12 | 1.0748e+12 | 1.07537e+12 |  | 670.066 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only | 512 | 8 |  |  |  |  | 0 | 0.062281 | 8.3968e+09 sectors | 8.39697e+09 | 8.40182e+09 |  | 2.68698e+11 | 2.68703e+11 | 2.68858e+11 |  | 644.438 |  |  |  |  | 38 | 0 | 0 | ok |  |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only | 512 | 8 |  |  |  |  | 0 | 0.0672881 | 1.67936e+10 sectors | 1.67938e+10 | 1.68027e+10 |  | 5.37395e+11 | 5.374e+11 | 5.37685e+11 |  | 670.641 |  |  |  |  | 38 | 0 | 0 | ok |  |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only | 2048 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 1.49557e+07 |  | 0 | 0 | 4.78583e+08 |  | 0.000528 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only | 2048 | 8 |  |  |  |  |  |  | 0 sectors | 154070 | 4.48754e+06 |  | 0 | 4.93024e+06 | 1.43601e+08 |  | 0.002046 |  |  |  |  | 34 | 0 | 0 | ok | l2_read_sector_conservation_failed |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only | 2048 | 8 |  |  |  |  |  | 0 | 0 sectors | 0 | 7.48172e+06 |  | 0 | 0 | 2.39415e+08 |  | 0.001026 |  |  |  |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only | 256 | 8 |  |  |  |  |  | 19.5997 | 0 sectors | 152417 | 1.50552e+07 |  | 0 | 4.87734e+06 | 4.81767e+08 |  | 0.000522 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only | 256 | 8 |  |  |  |  |  |  | 0 sectors | 153362 | 4.03164e+06 |  | 0 | 4.90758e+06 | 1.29013e+08 |  | 0.002078 |  |  |  |  | 34 | 0 | 0 | ok | l2_read_sector_conservation_failed |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only | 256 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 7.49637e+06 |  | 0 | 0 | 2.39884e+08 |  | 0.001048 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only | 512 | 8 |  |  |  |  |  | 31.9027 | 0 sectors | 152856 | 1.56502e+07 |  | 0 | 4.89139e+06 | 5.00807e+08 |  | 0.000522 |  |  |  |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only | 512 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 3.74928e+06 |  | 0 | 0 | 1.19977e+08 |  | 0.002035 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only | 512 | 8 |  |  |  |  |  | 0 | 0 sectors | 153111 | 7.74984e+06 |  | 0 | 4.89955e+06 | 2.47995e+08 |  | 0.00106 |  |  |  |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 0.00736658 | 0.016974 | 0.00960742 |  | srcunit_tex_device_read_lookup_hit_miss | 2.47424e+06 | 3.35849e+10 | 1 | 1.07472e+12 | 1.076e+12 | 1.00119 | 1.0748e+12 |  | 1 |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 0.00677987 | 0.017273 | 0.0104931 |  | srcunit_tex_device_read_lookup_hit_miss | 569292 | 8.39623e+09 | 0.999981 | 2.68679e+11 | 2.69008e+11 | 1.00122 | 2.68703e+11 |  | 1.00002 |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 0.00739389 | 0.017614 | 0.0102201 |  | srcunit_tex_device_read_lookup_hit_miss | 1.24172e+06 | 1.67926e+10 | 1.00001 | 5.37363e+11 | 5.38001e+11 | 1.00119 | 5.37395e+11 |  | 1 |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 0.216399 | 0.225035 | 0.00863583 |  | srcunit_tex_device_read_lookup_hit_miss | 7.26871e+07 | 3.35167e+10 | 1.00006 | 1.07253e+12 | 1.07377e+12 | 1.00116 | 1.0748e+12 |  | 1 |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 0.219313 | 0.228914 | 0.0096014 |  | srcunit_tex_device_read_lookup_hit_miss | 1.84159e+07 | 8.37868e+09 | 1.00004 | 2.68118e+11 | 2.68447e+11 | 1.00123 | 2.68698e+11 |  | 1 |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 0.220179 | 0.230026 | 0.00984682 |  | srcunit_tex_device_read_lookup_hit_miss | 3.69766e+07 | 1.67569e+10 | 1.00001 | 5.36221e+11 | 5.36855e+11 | 1.00118 | 5.374e+11 |  | 1.00001 |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 0.0670954 | 0.076571 | 0.00947558 |  | srcunit_tex_device_read_lookup_hit_miss | 2.25359e+07 | 3.35652e+10 | 1.00001 | 1.07409e+12 | 1.07536e+12 | 1.00119 | 1.0748e+12 |  | 1 |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 0.062281 | 0.071798 | 0.009517 |  | srcunit_tex_device_read_lookup_hit_miss | 5.22962e+06 | 8.39159e+09 | 0.999982 | 2.68531e+11 | 2.68846e+11 | 1.00118 | 2.68703e+11 |  | 1.00002 |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only | 0 |  | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 0.0672881 | 0.077121 | 0.00983286 |  | srcunit_tex_device_read_lookup_hit_miss | 1.13003e+07 | 1.67826e+10 | 1.00001 | 5.37044e+11 | 5.37677e+11 | 1.00118 | 5.374e+11 |  | 1.00001 |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 21.0027 |  |  |  | 0 | 0 |  | 0 | 4.78583e+08 |  | 0 |  |  |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 18.1361 |  |  |  | 0 | 0 | 0 | 0 | 1.395e+08 |  | 4.93024e+06 |  |  |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only |  |  |  | 0 | 0 | 0 | 0 | 21.0044 | 21.0044 |  | srcunit_tex_device_read_lookup_hit_miss | 0 | 124073 |  | 3.9231e+06 | 2.39415e+08 | 61.0269 | 0 |  |  |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only |  |  |  | 0 | 0 | 0 | 19.5997 | 20.2974 | 0.697739 |  | srcunit_tex_device_read_lookup_hit_miss | 29815 | 123781 | 1.00781 | 3.91376e+06 | 4.77465e+08 | 121.997 | 4.87734e+06 |  |  |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 20.3931 |  |  |  | 0 | 0 | 0 | 0 | 1.24872e+08 |  | 4.90758e+06 |  |  |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 21.0013 |  |  |  | 0 | 0 |  | 0 | 2.39884e+08 |  | 0 |  |  |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only |  |  |  | 0 | 0 | 0 | 31.9027 | 20.9939 | 10.9089 |  | srcunit_tex_device_read_lookup_hit_miss | 57348 | 123887 | 1.18747 | 3.91715e+06 | 4.96424e+08 | 126.731 | 4.89139e+06 |  |  |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 21.2688 |  |  |  | 0 | 0 |  | 0 | 1.19437e+08 |  | 0 |  |  |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only |  |  |  | 0 | 0 | 0 | 0 | 20.6289 | 20.6289 |  | srcunit_tex_device_read_lookup_hit_miss | 0 | 99156 | 0.644178 | 3.12576e+06 | 2.43804e+08 | 77.9982 | 4.89955e+06 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only | 1.07479e+12 | 1.0748e+12 | 1 | 1.076e+12 | dram__bytes_read.sum | 1.00112 | 1.14551e+07 | dram__bytes_write.sum | 1.0646e-05 | 863.514 |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only | 2.68698e+11 | 2.68703e+11 | 1.00002 | 2.69008e+11 | dram__bytes_read.sum | 1.00116 | 9.82618e+06 | dram__bytes_write.sum | 3.65274e-05 | 861.11 |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only | 5.37395e+11 | 5.37395e+11 | 1 | 5.38001e+11 | dram__bytes_read.sum | 1.00113 | 3.36538e+06 | dram__bytes_write.sum | 6.25534e-06 | 864.724 |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only | 1.07479e+12 | 1.0748e+12 | 1 | 1.07377e+12 | dram__bytes_read.sum | 0.999054 | 1.12361e+07 | dram__bytes_write.sum | 1.04641e-05 | 865.151 |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only | 2.68698e+11 | 2.68698e+11 | 1 | 2.68447e+11 | dram__bytes_read.sum | 0.999068 | 1.55738e+06 | dram__bytes_write.sum | 5.80142e-06 | 863.35 |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only | 5.37395e+11 | 5.374e+11 | 1.00001 | 5.36855e+11 | dram__bytes_read.sum | 0.998994 | 8.58995e+06 | dram__bytes_write.sum | 1.60005e-05 | 865.375 |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only | 1.07479e+12 | 1.0748e+12 | 1 | 1.07536e+12 | dram__bytes_read.sum | 1.00053 | 1.17961e+07 | dram__bytes_write.sum | 1.09694e-05 | 868.849 |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only | 2.68698e+11 | 2.68703e+11 | 1.00002 | 2.68846e+11 | dram__bytes_read.sum | 1.00055 | 1.19246e+07 | dram__bytes_write.sum | 4.43547e-05 | 866.766 |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only | 5.37395e+11 | 5.374e+11 | 1.00001 | 5.37677e+11 | dram__bytes_read.sum | 1.00052 | 8.34035e+06 | dram__bytes_write.sum | 1.55118e-05 | 869.422 |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only |  | 0 |  | 4.78583e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.9854 |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only |  | 4.93024e+06 |  | 1.395e+08 | dram__bytes_read.sum |  | 4.1015e+06 | dram__bytes_write.sum | 0.0294015 | 1.11401 |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only |  | 0 |  | 2.39415e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.994278 |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only |  | 4.87734e+06 |  | 4.77465e+08 | dram__bytes_read.sum |  | 4.30157e+06 | dram__bytes_write.sum | 0.00900917 | 0.981863 |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only |  | 4.90758e+06 |  | 1.24872e+08 | dram__bytes_read.sum |  | 4.14067e+06 | dram__bytes_write.sum | 0.0331593 | 0.988773 |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only |  | 0 |  | 2.39884e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.993521 |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only |  | 4.89139e+06 |  | 4.96424e+08 | dram__bytes_read.sum |  | 4.38285e+06 | dram__bytes_write.sum | 0.00882883 | 1.0216 |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only |  | 0 |  | 1.19437e+08 | dram__bytes_read.sum |  | 539776 | dram__bytes_write.sum | 0.00451933 | 0.953316 |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only |  | 4.89955e+06 |  | 2.43804e+08 | dram__bytes_read.sum |  | 4.19149e+06 | dram__bytes_write.sum | 0.0171921 | 1.01049 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dram_cg_load_only_W2048_B8_LR16 | 0.00736658 | 0.00736658 | 0.016974 |  |  |  |  | 3.35874e+10/2.47424e+06/3.35849e+10 | // |  |  | 1// | 1.00112 | // |
| dram_cg_load_only_W2048_B8_LR4 | 0.00677987 | 0.00677987 | 0.017273 |  |  |  |  | 8.39696e+09/569292/8.39623e+09 | // |  |  | 1// | 1.00114 | // |
| dram_cg_load_only_W2048_B8_LR8 | 0.00739389 | 0.00739389 | 0.017614 |  |  |  |  | 1.67936e+10/1.24172e+06/1.67926e+10 | // |  |  | 1// | 1.00113 | // |
| dram_cg_load_only_W256_B8_LR16 | 0.216399 | 0.216399 | 0.225035 |  |  |  |  | 3.35874e+10/7.26871e+07/3.35167e+10 | // |  |  | 1// | 0.999049 | // |
| dram_cg_load_only_W256_B8_LR4 | 0.219313 | 0.219313 | 0.228914 |  |  |  |  | 8.3968e+09/1.84159e+07/8.37868e+09 | // |  |  | 1// | 0.999068 | // |
| dram_cg_load_only_W256_B8_LR8 | 0.220179 | 0.220179 | 0.230026 |  |  |  |  | 1.67938e+10/3.69766e+07/1.67569e+10 | // |  |  | 1// | 0.998984 | // |
| dram_cg_load_only_W512_B8_LR16 | 0.0670954 | 0.0670954 | 0.076571 |  |  |  |  | 3.35874e+10/2.25359e+07/3.35652e+10 | // |  |  | 1// | 1.00053 | // |
| dram_cg_load_only_W512_B8_LR4 | 0.062281 | 0.062281 | 0.071798 |  |  |  |  | 8.39696e+09/5.22962e+06/8.39159e+09 | // |  |  | 1// | 1.00053 | // |
| dram_cg_load_only_W512_B8_LR8 | 0.0672881 | 0.0672881 | 0.077121 |  |  |  |  | 1.67938e+10/1.13003e+07/1.67826e+10 | // |  |  | 1// | 1.00051 | // |
| global_addr_only_dram_W2048_B8_LR16 |  |  | 21.0027 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_dram_W2048_B8_LR4 |  |  | 18.1361 |  |  |  |  | 152594/0/0 | // |  |  | 0// | 28.2947 | // |
| global_addr_only_dram_W2048_B8_LR8 | 0 | 0 | 21.0044 |  |  |  |  | 0/0/122597 | // |  |  | // |  | // |
| global_addr_only_dram_W256_B8_LR16 | 19.5997 | 19.4113 | 20.2974 |  |  |  |  | 150941/29815/122305 | // |  |  | 1// | 97.8946 | // |
| global_addr_only_dram_W256_B8_LR4 |  |  | 20.3931 |  |  |  |  | 151886/0/0 | // |  |  | 0// | 25.4447 | // |
| global_addr_only_dram_W256_B8_LR8 |  |  | 21.0013 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_dram_W512_B8_LR16 | 31.9027 | 31.6429 | 20.9939 |  |  |  |  | 151380/57348/122411 | // |  |  | 0// | 101.489 | // |
| global_addr_only_dram_W512_B8_LR4 |  |  | 21.2688 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_dram_W512_B8_LR8 | 0 | 0 | 20.6289 |  |  |  |  | 151635/0/97680 | // |  |  | 0// | 49.7604 | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only |  |  |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only |  |  |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only |  |  |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only |  |  |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only |  |  |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only |  |  |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only |  |  |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only |  |  |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only |  |  |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only |  |  |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only |  |  |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only |  |  |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only |  |  |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only |  |  |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only |  |  |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only |  |  |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only |  |  |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only |  |  |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| dram_cg_load_only_W2048_B8_LR16 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W2048_B8_LR4 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W2048_B8_LR8 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W256_B8_LR16 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W256_B8_LR4 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W256_B8_LR8 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W512_B8_LR16 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W512_B8_LR4 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| dram_cg_load_only_W512_B8_LR8 | dram_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W2048_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W2048_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W2048_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W256_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W256_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W256_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W512_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W512_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_dram_W512_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
