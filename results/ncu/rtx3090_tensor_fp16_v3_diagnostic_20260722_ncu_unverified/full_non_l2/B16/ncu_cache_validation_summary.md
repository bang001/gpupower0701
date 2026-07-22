# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | sass | 0 | 0 | 19.7409 | 23.0898 | 0 sectors | 0 | 1.96784e+06 | 0 | 0 | 8.00145e+07 | 6.29709e+07 | 0 | 0.003208 | 0.0006 | 378.947 | 33.5927 | 32.4641 | 16 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF1 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7908 | 21.8269 | 0 sectors | 0 | 621128 | 0 | 0 | 2.56695e+07 | 1.98761e+07 | 2.624e+08 | 0.027634 | 132.036 | 204.872 | 35.2618 | 26.2001 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF16 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.7917 | 21.8496 | 0 sectors | 0 | 8.01563e+06 | 0 | 0 | 3.2643e+08 | 2.565e+08 | 4.1984e+09 | 0.001275 | 98.8911 | 188.176 | 24.0285 | 24.1817 | 28 | 0 | 0 | ok |  |
| reg_mma_W1_B16_RF4 | reg_mma | 1 | 16 | 0 | sass | 0 | 0 | 86.8037 | 23.5887 | 0 sectors | 0 | 1.93098e+06 | 0 | 0 | 8.01178e+07 | 6.17915e+07 | 1.0496e+09 | 0.007164 | 95.1288 | 188.522 | 28.7001 | 24.6887 | 28 | 0 | 0 | ok |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.5704 | 103.906 | 0 sectors | 0 | 0 | 0 | 0 | 2.29949e+06 | 0 | 0 | 0.111272 | 531.021 | 277.652 | 11.0856 | 33.3091 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range;l2_native_read_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.8152 | 19.1785 | 0 sectors | 0 | 1.96207e+06 | 0 | 0 | 7.95057e+07 | 6.27862e+07 | 0 | 0.011123 | 302.701 | 233.333 | 38.3354 | 32.385 | 16 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 1 | 16 | 0 | sass | 0 | 0 | 86.784 | 25.9448 | 0 sectors | 0 | 517544 | 0 | 0 | 2.23573e+07 | 1.65614e+07 | 0 | 0.014262 | 269.35 | 233.334 | 38.1503 | 33.3077 | 16 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B16 | clocked_empty |  | 19.7409 | aggregate_fallback | 0 | 0 | 0 |  | 22.4712 |  | 23.0898 | aggregate_fallback | 0 | 0 |  | 0 | 6.29709e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF1 | reg_mma |  | 86.7908 | aggregate_fallback | 0 | 0 | 0 |  | 16.7146 |  | 21.8269 | aggregate_fallback | 0 | 0 |  | 0 | 1.98761e+07 |  | 0 |  |  |
| reg_mma_W1_B16_RF16 | reg_mma |  | 86.7917 | aggregate_fallback | 0 | 0 | 0 |  | 21.0999 |  | 21.8496 | aggregate_fallback | 0 | 0 |  | 0 | 2.56455e+08 |  | 0 |  |  |
| reg_mma_W1_B16_RF4 | reg_mma |  | 86.8037 | aggregate_fallback | 0 | 0 | 0 |  | 21.4936 |  | 23.5887 | aggregate_fallback | 0 | 0 |  | 0 | 6.17894e+07 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 86.5704 | aggregate_fallback | 0 | 0 | 0 |  | 103.113 |  | 103.906 | aggregate_fallback | 0 | 0 |  | 0 | 0 |  | 0 |  |  |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 86.8152 | aggregate_fallback | 0 | 0 | 0 | 19.1785 | 27.1674 | 7.98886 | 75.5179 | srcunit_tex_device_read_lookup_hit_miss | 0 | 825768 |  | 2.07813e+07 | 6.15306e+07 | 2.96086 | 0 |  |  |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 86.784 | aggregate_fallback | 0 | 0 | 0 |  | 20.2173 |  | 25.9448 | aggregate_fallback | 0 | 0 |  | 0 | 1.65614e+07 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| clocked_empty_W64_B16 | clocked_empty |  | 0 |  | 6.29709e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.959425 |
| reg_mma_W1_B16_RF1 | reg_mma |  | 0 |  | 1.98761e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.17703 |
| reg_mma_W1_B16_RF16 | reg_mma |  | 0 |  | 2.56455e+08 | dram__bytes_read.sum |  | 45440 | dram__bytes_write.sum | 0.000177185 | 1.00363 |
| reg_mma_W1_B16_RF4 | reg_mma |  | 0 |  | 6.17894e+07 | dram__bytes_read.sum |  | 2048 | dram__bytes_write.sum | 3.31448e-05 | 0.966954 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only |  | 0 |  | 0 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum |  | 0 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only |  | 0 |  | 6.15306e+07 | dram__bytes_read.sum |  | 1.25555e+06 | dram__bytes_write.sum | 0.0204053 | 0.989861 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only |  | 0 |  | 1.65614e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.02965 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B16 |  |  | 22.4712 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF1 |  |  | 16.7146 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF16 |  |  | 21.0999 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B16_RF4 |  |  | 21.4936 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF1 |  |  | 103.113 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF16 | 19.1785 | 0 | 27.1674 |  |  |  |  | 0/154103/649416 | // |  |  | // |  | // |
| reg_operand_only_W1_B16_RF4 |  |  | 20.2173 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| clocked_empty_W64_B16 | clocked_empty | 0 | 0 |
| reg_mma_W1_B16_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B16_RF4 | reg_mma | 0 | 0 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 0 | 0 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty_W64_B16 | clocked_empty | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.49281e+10 |  |  | 0 |  |  | 0 |  |  | 0 | 32.4641 | 33.3333 | 16 |
| reg_mma_W1_B16_RF1 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 2.78815e+09 | 1.312e+08 | 21.2511 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 44.6389 | 26.2001 | 33.3333 | 34 |
| reg_mma_W1_B16_RF16 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.95649e+10 | 2.0992e+09 | 28.3751 | 4.1984e+09 | 2.0992e+09 | 2 | 1.71966e+13 | 1.71966e+13 | 1 | 42.0135 | 24.1817 | 33.3333 | 28 |
| reg_mma_W1_B16_RF4 | reg_mma | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.54817e+10 | 5.248e+08 | 29.5002 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 42.0996 | 24.6887 | 33.3333 | 28 |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 6.97127e+08 | 1.312e+08 | 5.31347 | 0 |  |  | 0 |  |  | 0 | 33.3091 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 1.96801e+10 | 2.0992e+09 | 9.37505 | 0 |  |  | 0 |  |  | 0 | 32.385 | 33.3333 | 16 |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | application | none | full | 4 | normal | contiguous | 1.17965e+06 | 5.51049e+09 | 5.248e+08 | 10.5002 | 0 |  |  | 0 |  |  | 0 | 33.3077 | 33.3333 | 16 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B16 | clocked_empty | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B16_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
