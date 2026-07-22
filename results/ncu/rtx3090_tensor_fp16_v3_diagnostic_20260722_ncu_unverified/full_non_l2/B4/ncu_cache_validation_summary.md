# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B4 | clocked_empty | 64 | 4 | 0 | sass | 0 | 0 | 12.1189 | 21.0915 | 0 sectors | 0 | 1.68938e+06 | 0 | 0 | 6.78531e+07 | 5.406e+07 | 0 | 0.00215 | 0.000574 | 378.946 | 0 | 8.33332 | 16 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6725 | 10.1034 | 0 sectors | 156073 | 173136 | 0 | 0 | 1.91273e+07 | 5.54035e+06 | 6.56e+07 | 0.053965 | 132.014 | 198.822 | 0 | 8.22345 | 34 | 0 | 0 | ok | l2_read_sector_conservation_failed |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6737 | 21.3709 | 0 sectors | 0 | 3.58077e+06 | 0 | 0 | 1.45534e+08 | 1.14585e+08 | 1.0496e+09 | 0.000877 | 98.8378 | 178.634 | 0 | 8.23379 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6689 | 30.155 | 0 sectors | 0 | 619724 | 0 | 0 | 2.78234e+07 | 1.98312e+07 | 2.624e+08 | 0.003405 | 95.0631 | 178.814 | 0 | 8.236 | 28 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 71.6357 | 96.7419 | 0 sectors | 0 | 144 | 0 | 0 | 1.52432e+06 | 4608 | 0 | 0.074362 | 524.616 | 277.646 | 0 | 8.33296 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 77.5238 | 20.6933 | 0 sectors | 0 | 1.6871e+06 | 0 | 0 | 6.80285e+07 | 5.39872e+07 | 0 | 0.002861 | 298.666 | 233.333 | 0 | 8.33332 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 77.6697 | 17.5051 | 0 sectors | 0 | 619732 | 0 | 0 | 2.44872e+07 | 1.98314e+07 | 0 | 0.009351 | 266.664 | 233.333 | 0 | 8.33327 | 16 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B4 | clocked_empty |  | 12.1189 | aggregate_fallback | 0 | 0 | 0 |  | 20.7071 |  | 21.0915 | aggregate_fallback | 0 | 0 |  | 0 | 5.406e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF1 | reg_mma |  | 86.6725 | aggregate_fallback | 0 | 0 | 0 |  | 21.2246 |  | 10.1034 | aggregate_fallback | 0 | 0 | 0 | 0 | 487296 |  | 4.99434e+06 |  |  |
| reg_mma_W1_B4_RF16 | reg_mma |  | 86.6737 | aggregate_fallback | 0 | 0 | 0 |  | 20.8516 |  | 21.3709 | aggregate_fallback | 0 | 0 |  | 0 | 1.14585e+08 |  | 0 |  |  |
| reg_mma_W1_B4_RF4 | reg_mma |  | 86.6689 | aggregate_fallback | 0 | 0 | 0 |  | 28.4798 |  | 30.155 | aggregate_fallback | 0 | 0 |  | 0 | 1.98312e+07 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 71.6357 | aggregate_fallback | 0 | 0 | 0 |  | 95.0257 |  | 96.7419 | aggregate_fallback | 0 | 0 |  | 0 | 4608 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 77.5238 | aggregate_fallback | 0 | 0 | 0 |  | 19.7433 |  | 20.6933 | aggregate_fallback | 0 | 0 |  | 0 | 5.39872e+07 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 77.6697 | aggregate_fallback | 0 | 0 | 0 |  | 14.8257 |  | 17.5051 | aggregate_fallback | 0 | 0 |  | 0 | 1.98314e+07 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| clocked_empty_W64_B4 | clocked_empty |  | 0 |  | 5.406e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.01365 |
| reg_mma_W1_B4_RF1 | reg_mma |  | 4.99434e+06 |  | 487296 | dram__bytes_read.sum |  | 5.05306e+06 | dram__bytes_write.sum | 10.3696 | 0.0610622 |
| reg_mma_W1_B4_RF16 | reg_mma |  | 0 |  | 1.14585e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.00021 |
| reg_mma_W1_B4_RF4 | reg_mma |  | 0 |  | 1.98312e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.682068 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 0 |  | 4608 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00164914 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 0 |  | 5.39872e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.01638 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 0 |  | 1.98314e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.42607 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B4 |  |  | 20.7071 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF1 |  |  | 21.2246 |  |  |  |  | 154839/0/0 | // |  |  | 0// | 0.0975697 | // |
| reg_mma_W1_B4_RF16 |  |  | 20.8516 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF4 |  |  | 28.4798 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  | 95.0257 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF16 |  |  | 19.7433 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF4 |  |  | 14.8257 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| clocked_empty_W64_B4 | clocked_empty | 0 | 0 |
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B4 | clocked_empty | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.23202e+09 |  |  | 0 |  |  | 0 |  |  | 0 | 8.33332 | 33.3333 | 16 |
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.97038e+08 | 3.28e+07 | 21.2511 | 6.56e+07 | 3.28e+07 | 2 | 2.68698e+11 | 2.68698e+11 | 1 | 26.8752 | 8.22345 | 33.3333 | 34 |
| reg_mma_W1_B4_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.48912e+10 | 5.248e+08 | 28.3751 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 23.0972 | 8.23379 | 33.3333 | 28 |
| reg_mma_W1_B4_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 3.87043e+09 | 1.312e+08 | 29.5002 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 22.5774 | 8.236 | 33.3333 | 28 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.74282e+08 | 3.28e+07 | 5.31347 | 0 |  |  | 0 |  |  | 0 | 8.33296 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 4.92002e+09 | 5.248e+08 | 9.37505 | 0 |  |  | 0 |  |  | 0 | 8.33332 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.37762e+09 | 1.312e+08 | 10.5002 | 0 |  |  | 0 |  |  | 0 | 8.33327 | 33.3333 | 16 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B4 | clocked_empty | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
