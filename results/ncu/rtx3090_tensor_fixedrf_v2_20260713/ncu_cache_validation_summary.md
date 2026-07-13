# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| reg_mma_W2048_B16_RF1 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 86.7946 | 24.3817 | 0 sectors | 0 | 622320 | 0 | 0 | 2.6133e+07 | 1.99142e+07 | 2.624e+08 | 0.040975 | 0.005515 | 300.458 | 27.3614 |  | 26 | 0 | 0 | ok |  |
| reg_mma_W2048_B16_RF16 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 86.8105 | 34.2104 | 0 sectors | 133902 | 6.95814e+06 | 0 | 0 | 3.01664e+08 | 2.29299e+08 | 4.1984e+09 | 0.002171 | 0.00034 | 214.303 | 33.6542 |  | 26 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| reg_mma_W2048_B16_RF2 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 86.7937 | 100 | 0 sectors | 0 | 801360 | 0 | 0 | 3.52233e+07 | 2.56435e+07 | 5.248e+08 | 0.014821 | 0.00246 | 213.123 | 38.66 |  | 25 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W2048_B16_RF4 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 86.7887 | 100 | 0 sectors | 0 | 1.86427e+06 | 0 | 0 | 7.67127e+07 | 5.96567e+07 | 1.0496e+09 | 0.014239 | 0.00132 | 216.363 | 34.3818 |  | 26 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_mma_W2048_B16_RF8 | reg_mma | 2048 | 16 | 0 | sass | 0 | 0 | 86.8102 | 22.3928 | 0 sectors | 0 | 3.73618e+06 | 0 | 0 | 1.52773e+08 | 1.20942e+08 | 2.0992e+09 | 0.01095 | 0.00067 | 214.928 | 34.1936 |  | 26 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B16_RF1 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 86.5115 | 52.5612 | 0 sectors | 0 | 97356 | 0 | 0 | 6.35638e+06 | 4.04442e+06 | 0 | 0.034879 | 0.006265 | 393.737 | 47.9201 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B16_RF16 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 85.3141 | 0 | 0 sectors | 0 | 772124 | 0 | 0 | 3.35201e+07 | 2.4708e+07 | 0 | 0.008326 | 0.001464 | 427.14 | 31.7825 |  | 22 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W2048_B16_RF2 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 86.3293 | 0 | 0 sectors | 0 | 104268 | 0 | 0 | 6.21674e+06 | 4.44454e+06 | 0 | 0.072287 | 0.007072 | 278.567 | 41.9901 |  | 22 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W2048_B16_RF4 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 86.4191 | 44.4798 | 0 sectors | 0 | 154156 | 0 | 0 | 8.77414e+06 | 5.94304e+06 | 0 | 0.027707 | 0.004487 | 377.266 | 37.801 |  | 22 | 0 | 0 | ok |  |
| reg_operand_only_W2048_B16_RF8 | reg_operand_only | 2048 | 16 | 0 | sass | 0 | 0 | 86.1896 | 54.3606 | 0 sectors | 0 | 136504 | 0 | 0 | 1.03218e+07 | 4.36813e+06 | 0 | 0.039868 | 0.002684 | 407.89 | 38.4199 |  | 22 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the srcunit-TEX read hit/miss sectors when available.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W2048_B16_RF1 | reg_mma |  | 86.7946 | aggregate_fallback | 0 | 0 | 0 |  | 18.8834 |  | 24.3817 | aggregate_fallback | 0 | 0 |  | 0 | 1.99142e+07 |  | 0 |
| reg_mma_W2048_B16_RF16 | reg_mma |  | 86.8105 | aggregate_fallback | 0 | 0 | 0 | 34.2104 | 25.5525 | 8.65793 | 50.978 | srcunit_tex_read_lookup_hit_miss | 354645 | 682013 | 7.74192 | 2.18244e+07 | 2.22661e+08 | 10.2024 | 4.28486e+06 |
| reg_mma_W2048_B16_RF2 | reg_mma |  | 86.7937 | aggregate_fallback | 0 | 0 | 0 | 100 | 44.8591 | 55.1409 | 219.625 | srcunit_tex_read_lookup_hit_miss | 205732 | 0 |  | 0 | 2.56435e+07 |  | 0 |
| reg_mma_W2048_B16_RF4 | reg_mma |  | 86.7887 | aggregate_fallback | 0 | 0 | 0 | 100 | 30.4693 | 69.5307 | 111.218 | srcunit_tex_read_lookup_hit_miss | 216230 | 0 |  | 0 | 5.96567e+07 |  | 0 |
| reg_mma_W2048_B16_RF8 | reg_mma |  | 86.8102 | aggregate_fallback | 0 | 0 | 0 |  | 21.2795 |  | 22.3928 | aggregate_fallback | 0 | 0 |  | 0 | 1.19558e+08 |  | 0 |
| reg_operand_only_W2048_B16_RF1 | reg_operand_only |  | 86.5115 | aggregate_fallback | 0 | 0 | 0 |  | 36.1752 |  | 52.5612 | aggregate_fallback | 0 | 0 |  | 0 | 3.11539e+06 |  | 0 |
| reg_operand_only_W2048_B16_RF16 | reg_operand_only |  | 85.3141 | aggregate_fallback | 0 | 0 | 0 | 0 | 21.6082 | 21.6082 | 25.6746 | srcunit_tex_read_lookup_hit_miss | 0 | 605057 |  | 1.93618e+07 | 2.4708e+07 | 1.27612 | 0 |
| reg_operand_only_W2048_B16_RF2 | reg_operand_only |  | 86.3293 | aggregate_fallback | 0 | 0 | 0 | 0 | 24.3572 | 24.3572 | 45.8288 | srcunit_tex_read_lookup_hit_miss | 0 | 202733 |  | 6.48746e+06 | 3.33658e+06 | 0.514312 | 0 |
| reg_operand_only_W2048_B16_RF4 | reg_operand_only |  | 86.4191 | aggregate_fallback | 0 | 0 | 0 |  | 32.3658 |  | 44.4798 | aggregate_fallback | 0 | 0 |  | 0 | 4.93299e+06 |  | 0 |
| reg_operand_only_W2048_B16_RF8 | reg_operand_only |  | 86.1896 | aggregate_fallback | 0 | 0 | 0 |  | 46.1481 |  | 54.3606 | aggregate_fallback | 0 | 0 |  | 0 | 4.36813e+06 |  | 0 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | warm-up passes | L2 residency | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA |
|---|---|---|---|---:|---|---:|---:|---:|---:|
| reg_mma_W2048_B16_RF1 | reg_mma | application | none | 1 | normal | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 |
| reg_mma_W2048_B16_RF16 | reg_mma | application | none | 1 | normal | 1.17965e+06 | 4.1984e+09 | 2.0992e+09 | 2 |
| reg_mma_W2048_B16_RF2 | reg_mma | application | none | 1 | normal | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 |
| reg_mma_W2048_B16_RF4 | reg_mma | application | none | 1 | normal | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 |
| reg_mma_W2048_B16_RF8 | reg_mma | application | none | 1 | normal | 1.17965e+06 | 2.0992e+09 | 1.0496e+09 | 2 |
| reg_operand_only_W2048_B16_RF1 | reg_operand_only | application | none | 1 | normal | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B16_RF16 | reg_operand_only | application | none | 1 | normal | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B16_RF2 | reg_operand_only | application | none | 1 | normal | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B16_RF4 | reg_operand_only | application | none | 1 | normal | 1.17965e+06 | 0 |  |  |
| reg_operand_only_W2048_B16_RF8 | reg_operand_only | application | none | 1 | normal | 1.17965e+06 | 0 |  |  |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| reg_mma_W2048_B16_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B16_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B16_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B16_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W2048_B16_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B16_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B16_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B16_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B16_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W2048_B16_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
