# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.0732 | 59.5969 | 0 sectors | 0 | 7.45432e+06 | 0 | 0 | 3.06109e+08 | 2.38538e+08 | 0 | 0.000408 | 48.8304 | 194.449 | 13.9933 |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4543 | 23.3594 | 0 sectors | 0 | 1.87002e+06 | 0 | 0 | 7.74088e+07 | 5.98408e+07 | 0 | 0.002722 | 46.5081 | 195.714 | 15.0795 |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 8 | 8 | 0 | sass | 0 | 0 | 17.4924 | 100 | 0 sectors | 0 | 3.79232e+06 | 0 | 0 | 1.54712e+08 | 1.21354e+08 | 0 | 0.000826 | 48.0296 | 194.828 | 14.3679 |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 47.9313 | 3.35872e+10 sectors | 122755 | 8.64317e+06 | 0 | 1.07479e+12 | 3.60466e+08 | 2.7924e+08 | 0 | 2.60425 | 63.2212 | 319.415 | 11.7109 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9992 | 99.8668 | 8.3968e+09 sectors | 518641 | 2.72669e+06 | 0 | 2.68698e+11 | 1.45419e+08 | 1.0352e+08 | 0 | 1.52756 | 58.9682 | 325.209 | 11.7202 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 8 | 8 | 0 | sass | 0 | 0 | 99.9999 | 99.9835 | 1.67936e+10 sectors | 20992 | 4.31415e+06 | 0 | 5.37395e+11 | 1.75495e+08 | 1.38053e+08 | 0 | 1.87994 | 61.0396 | 322.219 | 11.4757 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.8735 | 100 | 0 sectors | 0 | 6.98109e+06 | 5.37395e+06 | 0 | 2.84242e+08 | 2.23395e+08 | 0 | 0.000771 | 58.7973 | 236.047 | 11.7798 |  | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 17.8735 | 0 | 0 sectors | 0 | 1.84944e+06 | 5.37395e+06 | 0 | 7.56871e+07 | 5.91821e+07 | 0 | 0.004877 | 55.705 | 235.174 | 12.3575 |  | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 64 | 8 | 41984 | sass | 0 | 41984 | 18.2927 | 7.80852 | 0 sectors | 3.71888e+06 | 5.88478e+06 | 5.37395e+06 | 0 | 4.00537e+08 | 2.86993e+08 | 0 | 0.001545 | 57.8337 | 235.744 | 12.3531 |  | 26 | 0 | 8192 | ok | l2_read_sector_conservation_failed |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 64 | 8 | 8.39684e+09 | sass | 0 | 8.39684e+09 | 18.0259 | 69.8307 | 0 sectors | 0 | 7.5941e+06 | 1.0748e+12 | 0 | 3.10874e+08 | 2.43011e+08 | 0 | 0.001487 | 92.1028 | 299.149 | 13.9895 |  | 26 | 0 | 8192 | ok | l2_native_derived_hit_rate_disagree |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 64 | 8 | 2.09924e+09 | sass | 0 | 2.09924e+09 | 18.1784 | 12.1769 | 0 sectors | 931245 | 2.39382e+06 | 2.68703e+11 | 0 | 1.388e+08 | 1.02752e+08 | 0 | 0.002284 | 86.4503 | 294.438 | 11.8357 |  | 26 | 0 | 8192 | ok | l2_read_sector_conservation_failed |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 64 | 8 | 4.19844e+09 | sass | 0 | 4.19844e+09 | 18.1021 | 21.68 | 0 sectors | 0 | 3.80866e+06 | 5.37401e+11 | 0 | 1.55283e+08 | 1.21877e+08 | 0 | 0.001126 | 90.0526 | 297.754 | 13.2806 |  | 26 | 0 | 8192 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l1_W8_B8_LR16 | global_addr_only |  | 17.0732 | aggregate_fallback | 0 | 0 | 0 | 59.5969 | 26.1984 | 33.3985 | 81.1372 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 0 | 2.38538e+08 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only |  | 17.4543 | aggregate_fallback | 0 | 0 | 0 |  | 21.6198 |  | 23.3594 | aggregate_fallback | 0 | 0 |  | 0 | 5.98408e+07 |  | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only |  | 17.4924 | aggregate_fallback | 0 | 0 | 0 | 100 | 20.7533 | 79.2467 | 21.4738 | srcunit_tex_read_lookup_hit_miss | 212847 | 0 |  | 0 | 1.21354e+08 |  | 0 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 1.07479e+12 | 1.07479e+12 | 1.04896e+06 | 47.9313 | 20.273 | 27.6584 | 20.3995 | srcunit_tex_device_read_lookup_hit_miss | 296196 | 142565 | 3.57428 | 4.56208e+06 | 2.76582e+08 | 60.6262 | 3.92816e+06 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 99.9992 | 99.9992 | global_load_lookup_hit_miss | 2.68698e+11 | 2.68696e+11 | 2.0192e+06 | 99.8668 | 17.4586 | 82.4081 | 13.8461 | srcunit_tex_device_read_lookup_hit_miss | 20896 | 140 | 0.0405598 | 4480 | 8.72541e+07 | 19476.4 | 1.65965e+07 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 99.9999 | 99.9999 | global_load_lookup_hit_miss | 5.37395e+11 | 5.37395e+11 | 671744 | 99.9835 | 23.35 | 76.6335 | 42.5138 | srcunit_tex_device_read_lookup_hit_miss | 20960 | 230862 | 11.9961 | 7.38758e+06 | 1.38053e+08 | 18.6871 | 671744 |  |  |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only |  | 17.8735 | aggregate_fallback | 0 | 0 | 0 | 100 | 21.7958 | 78.2042 | 22.3962 | srcunit_tex_read_lookup_hit_miss | 572934 | 0 |  | 0 | 2.23395e+08 |  | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only |  | 17.8735 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.1832 | 21.1832 | 21.6243 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 0 | 5.91821e+07 |  | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only |  | 18.2927 | aggregate_fallback | 0 | 0 | 0 |  | 11.2873 |  | 7.80852 | aggregate_fallback | 0 | 0 | 0 | 0 | 1.88313e+08 |  | 1.19004e+08 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only |  | 18.0259 | aggregate_fallback | 0 | 0 | 0 | 69.8307 | 21.45 | 48.3807 | 22.031 | srcunit_tex_read_lookup_hit_miss | 1.21711e+06 | 525833 |  | 1.68267e+07 | 2.43011e+08 | 14.442 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only |  | 18.1784 | aggregate_fallback | 0 | 0 | 0 |  | 15.6141 |  | 12.1769 | aggregate_fallback | 0 | 0 | 0 | 0 | 7.66022e+07 |  | 2.97998e+07 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only |  | 18.1021 | aggregate_fallback | 0 | 0 | 0 |  | 21.1833 |  | 21.68 | aggregate_fallback | 0 | 0 |  | 0 | 1.21877e+08 |  | 0 |  |  |

## L2 Scope And Eviction Diagnostics

These columns diagnose a low A100 L2 hit result. They do not relax the path gate. A high miss count accompanied by DRAM reads is a real off-chip refill signal; a large native/path disagreement indicates different event populations.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | device hit/miss sectors | evict-first (%) | evict-normal (%) | evict-last (%) | DRAM read/L2 miss ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l1_W8_B8_LR16 | 59.5969 |  | 26.1984 | 473726/321157 | 7.65906 | 92.3409 | 0 |  |
| global_addr_only_l1_W8_B8_LR4 |  |  | 21.6198 | 0/0 |  |  |  |  |
| global_addr_only_l1_W8_B8_LR8 |  | 100 | 20.7533 | 0/0 |  |  |  |  |
| global_l1_load_only_W8_B8_LR16 | 47.9313 | 67.5074 | 20.273 | 19324/20992 | 6.84772 | 93.1523 | 0 | 60.6262 |
| global_l1_load_only_W8_B8_LR4 | 99.8668 | 99.3345 | 17.4586 | 20988/28 | 0 | 100 | 0 | 19476.4 |
| global_l1_load_only_W8_B8_LR8 | 99.9835 | 8.32334 | 23.35 | 169473/28 | 0 | 100 | 0 | 18.6871 |
| shared_scalar_addr_only_W64_B8_LR16 |  | 100 | 21.7958 | 0/0 | 2.53706 | 97.4629 | 0 |  |
| shared_scalar_addr_only_W64_B8_LR4 | 0 |  | 21.1832 | 0/537476 |  |  |  |  |
| shared_scalar_addr_only_W64_B8_LR8 |  |  | 11.2873 | 0/0 |  |  |  |  |
| shared_scalar_load_only_W64_B8_LR16 |  | 69.8307 | 21.45 | 0/0 | 2.53856 | 97.4614 | 0 | 14.442 |
| shared_scalar_load_only_W64_B8_LR4 |  |  | 15.6141 | 0/0 | 2.53607 | 97.4639 | 0 |  |
| shared_scalar_load_only_W64_B8_LR8 |  |  | 21.1833 | 0/0 |  |  |  |  |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 0 | 0 |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 0 | 0 |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 0 | 0 |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 0 | 0 |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 0 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 1.07479e+12 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 2.68698e+11 | 5.37395e+06 |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 5.37395e+11 | 5.37395e+06 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | application | none | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| global_addr_only_l1_W8_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l1_W8_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR16 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR4 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_l1_load_only_W8_B8_LR8 | global_l1_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR16 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR4 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_addr_only_W64_B8_LR8 | shared_scalar_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR16 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR4 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| shared_scalar_load_only_W64_B8_LR8 | shared_scalar_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
