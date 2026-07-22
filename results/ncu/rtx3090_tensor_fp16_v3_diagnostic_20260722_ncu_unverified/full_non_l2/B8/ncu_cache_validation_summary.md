# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 0 | sass | 0 | 0 | 18.2927 | 20.5181 | 0 sectors | 0 | 1.7528e+06 | 0 | 0 | 7.11668e+07 | 5.60897e+07 | 0 | 0.002726 | 0.000553 | 378.947 | 5.25519 | 16.5701 | 16 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF1 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7619 | 16.7182 | 0 sectors | 0 | 452724 | 0 | 0 | 1.72874e+07 | 1.44872e+07 | 1.312e+08 | 0.026176 | 132.128 | 205.297 | 8.68005 | 16.4916 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF16 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7655 | 20.1619 | 0 sectors | 0 | 4.13326e+06 | 0 | 0 | 1.66916e+08 | 1.32264e+08 | 2.0992e+09 | 0.001157 | 98.9701 | 186.758 | 9.50587 | 16.4442 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B8_RF4 | reg_mma | 1 | 8 | 0 | sass | 0 | 0 | 86.7613 | 27.3181 | 0 sectors | 0 | 779352 | 0 | 0 | 3.42732e+07 | 2.49393e+07 | 5.248e+08 | 0.00454 | 95.3723 | 187.739 | 10.0856 | 16.6023 | 28 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 78.1276 | 106.539 | 0 sectors | 0 | 4 | 0 | 0 | 2.28931e+06 | 128 | 0 | 0.103442 | 525.275 | 277.649 | 1.34507 | 16.6647 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range;l2_native_read_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 81.6897 | 21.1831 | 0 sectors | 0 | 1.86038e+06 | 0 | 0 | 7.63745e+07 | 5.95322e+07 | 0 | 0.00353 | 299.219 | 233.333 | 8.73728 | 16.4096 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 1 | 8 | 0 | sass | 0 | 0 | 82.2965 | 21.7164 | 0 sectors | 0 | 619808 | 0 | 0 | 2.50161e+07 | 1.98339e+07 | 0 | 0.012863 | 267.392 | 233.333 | 6.22631 | 16.5194 | 16 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 18.2927 | aggregate_fallback | 0 | 0 | 0 |  | 20.0474 |  | 20.5181 | aggregate_fallback | 0 | 0 |  | 0 | 5.60897e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF1 | reg_mma |  | 86.7619 | aggregate_fallback | 0 | 0 | 0 |  | 12.4076 |  | 16.7182 | aggregate_fallback | 0 | 0 |  | 0 | 1.44872e+07 |  | 0 |  |  |
| reg_mma_W1_B8_RF16 | reg_mma |  | 86.7655 | aggregate_fallback | 0 | 0 | 0 |  | 19.5496 |  | 20.1619 | aggregate_fallback | 0 | 0 |  | 0 | 1.32264e+08 |  | 0 |  |  |
| reg_mma_W1_B8_RF4 | reg_mma |  | 86.7613 | aggregate_fallback | 0 | 0 | 0 |  | 25.282 |  | 27.3181 | aggregate_fallback | 0 | 0 |  | 0 | 2.49393e+07 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 78.1276 | aggregate_fallback | 0 | 0 | 0 |  | 115.487 |  | 106.539 | aggregate_fallback | 0 | 0 |  | 0 | 128 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 81.6897 | aggregate_fallback | 0 | 0 | 0 |  | 19.7186 |  | 21.1831 | aggregate_fallback | 0 | 0 |  | 0 | 5.95322e+07 |  | 0 |  |  |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 82.2965 | aggregate_fallback | 0 | 0 | 0 |  | 17.5287 |  | 21.7164 | aggregate_fallback | 0 | 0 |  | 0 | 1.98339e+07 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| clocked_empty_W64_B8 | clocked_empty |  | 0 |  | 5.60897e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.00486 |
| reg_mma_W1_B8_RF1 | reg_mma |  | 0 |  | 1.44872e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.79427 |
| reg_mma_W1_B8_RF16 | reg_mma |  | 0 |  | 1.32264e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.05159 |
| reg_mma_W1_B8_RF4 | reg_mma |  | 0 |  | 2.49393e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.775622 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only |  | 0 |  | 128 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 4.5453e-05 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only |  | 0 |  | 5.95322e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.01431 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only |  | 0 |  | 1.98339e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.26785 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 |  |  | 20.0474 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF1 |  |  | 12.4076 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF16 |  |  | 19.5496 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B8_RF4 |  |  | 25.282 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF1 |  |  | 115.487 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF16 |  |  | 19.7186 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B8_RF4 |  |  | 17.5287 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | 0 | 0 |
| reg_mma_W1_B8_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B8_RF4 | reg_mma | 0 | 0 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 0 | 0 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B8 | clocked_empty | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.2464e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 16.5701 | 33.3333 | 16 |
| reg_mma_W1_B8_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.39408e+09 | 6.56e+07 | 21.2511 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 46.3254 | 16.4916 | 33.3333 | 34 |
| reg_mma_W1_B8_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.97825e+10 | 1.0496e+09 | 28.3751 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 42.6849 | 16.4442 | 33.3333 | 28 |
| reg_mma_W1_B8_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 7.74086e+09 | 2.624e+08 | 29.5002 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 41.9887 | 16.6023 | 33.3333 | 28 |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.48564e+08 | 6.56e+07 | 5.31347 | 0 |  |  | 0 |  |  | 0 | 16.6647 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 9.84005e+09 | 1.0496e+09 | 9.37505 | 0 |  |  | 0 |  |  | 0 | 16.4096 | 33.3333 | 16 |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.75525e+09 | 2.624e+08 | 10.5002 | 0 |  |  | 0 |  |  | 0 | 16.5194 | 33.3333 | 16 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B8 | clocked_empty | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B8_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
