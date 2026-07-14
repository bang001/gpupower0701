# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 78.4243 | 15.5775 | 0 sectors | 0 | 266424 | 0 | 0 | 1.02453e+07 | 8.52557e+06 | 6.56e+07 | 0.090571 | 0.030549 | 446.968 | 0 | 8.33305 | 34 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6701 | 20.7597 | 0 sectors | 0 | 3.64668e+06 | 0 | 0 | 1.45603e+08 | 1.16694e+08 | 2.0992e+09 | 0.002362 | 0.000461 | 228.777 | 0 | 8.28158 | 35 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF2 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6689 | 17.3683 | 0 sectors | 0 | 621848 | 0 | 0 | 2.42869e+07 | 1.98991e+07 | 2.624e+08 | 0.027729 | 0.003203 | 224.998 | 0 | 8.25529 | 35 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6748 | 28.2234 | 0 sectors | 0 | 682688 | 0 | 0 | 2.97223e+07 | 2.1846e+07 | 5.248e+08 | 0.005685 | 0.001732 | 227.026 | 0 | 8.26413 | 35 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF8 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6725 | 0 | 0 sectors | 0 | 1.77232e+06 | 0 | 0 | 7.24491e+07 | 5.67141e+07 | 1.0496e+09 | 0.004496 | 0.000903 | 228.168 | 0 | 8.28201 | 35 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 75.4473 | 93.9043 | 0 sectors | 0 | 100 | 0 | 0 | 760672 | 3200 | 0 | 911.809 | 154.522 | 191.549 | 0 | 7.44896 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 73.5298 | 93.5929 | 0 sectors | 0 | 100 | 0 | 0 | 812096 | 3200 | 0 | 556.364 | 153.805 | 191.549 | 0 | 7.4539 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 79.6261 | 113.83 | 0 sectors | 0 | 164 | 0 | 0 | 650624 | 5248 | 0 | 569.418 | 154.212 | 191.549 | 0 | 7.42765 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 78.416 | 105.632 | 0 sectors | 0 | 132 | 0 | 0 | 680128 | 4224 | 0 | 589.784 | 154.328 | 191.549 | 0 | 7.64907 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 76.2407 | 96.8145 | 0 sectors | 0 | 100 | 0 | 0 | 738336 | 3200 | 0 | 562.431 | 154.32 | 191.549 | 0 | 7.42319 | 16 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  | 78.4243 | aggregate_fallback | 0 | 0 | 0 |  | 8.55196 |  | 15.5775 | aggregate_fallback | 0 | 0 |  | 0 | 8.52557e+06 |  | 0 |  |  |
| reg_mma_W1_B4_RF16 | reg_mma |  | 86.6701 | aggregate_fallback | 0 | 0 | 0 |  | 20.2471 |  | 20.7597 | aggregate_fallback | 0 | 0 |  | 0 | 1.16694e+08 |  | 0 |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  | 86.6689 | aggregate_fallback | 0 | 0 | 0 |  | 15.8127 |  | 17.3683 | aggregate_fallback | 0 | 0 |  | 0 | 1.98991e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF4 | reg_mma |  | 86.6748 | aggregate_fallback | 0 | 0 | 0 |  | 26.5118 |  | 28.2234 | aggregate_fallback | 0 | 0 |  | 0 | 2.1846e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF8 | reg_mma |  | 86.6725 | aggregate_fallback | 0 | 0 | 0 | 0 | 20.208 | 20.208 | 20.8811 | srcunit_tex_device_read_lookup_hit_miss | 0 | 0 |  | 1.25235e+06 | 5.67141e+07 | 45.2861 | 0 |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 75.4473 | aggregate_fallback | 0 | 0 | 0 |  | 87.0146 |  | 93.9043 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 73.5298 | aggregate_fallback | 0 | 0 | 0 |  | 85.9413 |  | 93.5929 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 79.6261 | aggregate_fallback | 0 | 0 | 0 |  | 81.6235 |  | 113.83 | aggregate_fallback | 0 | 0 |  | 0 | 5248 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 78.416 | aggregate_fallback | 0 | 0 | 0 |  | 86.6747 |  | 105.632 | aggregate_fallback | 0 | 0 |  | 0 | 4224 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 76.2407 | aggregate_fallback | 0 | 0 | 0 |  | 91.5648 |  | 96.8145 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  | 0 |  | 8.52557e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00229767 |
| reg_mma_W1_B4_RF16 | reg_mma |  | 0 |  | 1.16694e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00104635 |
| reg_mma_W1_B4_RF2 | reg_mma |  | 0 |  | 1.98991e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00135116 |
| reg_mma_W1_B4_RF4 | reg_mma |  | 0 |  | 2.1846e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00076438 |
| reg_mma_W1_B4_RF8 | reg_mma |  | 0 |  | 5.67141e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00100857 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 8.92857e-07 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 8.84956e-07 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 0 |  | 5248 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.50459e-06 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 0 |  | 4224 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.06452e-06 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.25926e-07 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 |  |  | 8.55196 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF16 |  |  | 20.2471 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF2 |  |  | 15.8127 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF4 |  |  | 26.5118 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF8 | 0 |  | 20.208 |  |  |  |  | 0/0/39136 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  | 87.0146 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF16 |  |  | 85.9413 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF2 |  |  | 81.6235 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF4 |  |  | 86.6747 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF8 |  |  | 91.5648 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF2 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 |
| reg_mma_W1_B4_RF8 | reg_mma | 0 | 0 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 0 | 0 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 6.56e+07 | 3.28e+07 | 2 | 49.9754 | 8.33305 | 33.3333 | 34 |
| reg_mma_W1_B4_RF16 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 2.0992e+09 | 5.248e+08 | 4 | 47.1017 | 8.28158 | 33.3333 | 35 |
| reg_mma_W1_B4_RF2 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 6.56e+07 | 4 | 44.5962 | 8.25529 | 33.3333 | 35 |
| reg_mma_W1_B4_RF4 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 1.312e+08 | 4 | 45.9589 | 8.26413 | 33.3333 | 35 |
| reg_mma_W1_B4_RF8 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 2.624e+08 | 4 | 46.7145 | 8.28201 | 33.3333 | 35 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 | 7.44896 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 | 7.4539 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 | 7.42765 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 | 7.64907 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 | 7.42319 | 33.3333 | 16 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF16 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF4 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF8 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
