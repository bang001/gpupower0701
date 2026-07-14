# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6748 | 52.3039 | 0 sectors | 0 | 41668 | 0 | 0 | 2.68621e+06 | 1.33338e+06 | 6.56e+07 | 0.026054 | 0.006072 | 116.032 | 0 | 8.25417 | 35 | 0 | 0 | ok | l2_native_read_hit_rate_pct_out_of_range |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6725 | 21.5352 | 0 sectors | 0 | 1.95928e+06 | 0 | 0 | 7.9275e+07 | 6.26971e+07 | 1.0496e+09 | 0.002065 | 0.000375 | 92.5441 | 0 | 8.22481 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF2 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6713 | 22.8662 | 0 sectors | 0 | 314512 | 0 | 0 | 1.25098e+07 | 1.00644e+07 | 1.312e+08 | 0.008721 | 0.002669 | 102.476 | 0 | 8.17486 | 26 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6725 | 23.8576 | 0 sectors | 0 | 509640 | 0 | 0 | 2.09132e+07 | 1.63085e+07 | 2.624e+08 | 0.004278 | 0.001425 | 97.0843 | 0 | 8.20184 | 30 | 0 | 0 | ok |  |
| reg_mma_W1_B4_RF8 | reg_mma | 1 | 4 | 0 | sass | 0 | 0 | 86.6713 | 18.8225 | 0 sectors | 0 | 1.14516e+06 | 0 | 0 | 4.56694e+07 | 3.6645e+07 | 5.248e+08 | 0.002256 | 0.000737 | 94.1097 | 0 | 8.20882 | 30 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 77.4849 | 96.2353 | 0 sectors | 0 | 3228 | 0 | 0 | 826208 | 103296 | 0 | 570.384 | 153.298 | 191.549 | 0 | 7.38227 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 76.8728 | 99.034 | 0 sectors | 0 | 100 | 0 | 0 | 652608 | 3200 | 0 | 876.593 | 153.805 | 191.549 | 0 | 7.49425 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 80.0746 | 96.0995 | 0 sectors | 0 | 212 | 0 | 0 | 665344 | 6784 | 0 | 556.591 | 152.971 | 191.549 | 0 | 7.2796 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 81.28 | 99.3878 | 0 sectors | 0 | 100 | 0 | 0 | 648192 | 3200 | 0 | 565.643 | 153.255 | 191.549 | 0 | 7.42539 | 16 | 0 | 0 | ok |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | 1 | 4 | 0 | sass | 0 | 0 | 79.3825 | 108.872 | 0 sectors | 0 | 100 | 0 | 0 | 658592 | 3200 | 0 | 552.246 | 153.839 | 191.549 | 0 | 7.2704 | 16 | 0 | 0 | ok | l2_hit_rate_pct_out_of_range |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  | 86.6748 | aggregate_fallback | 0 | 0 | 0 |  | 103.579 |  | 52.3039 | aggregate_fallback | 0 | 0 |  | 0 | 1.33338e+06 |  | 0 |  |  |
| reg_mma_W1_B4_RF16 | reg_mma |  | 86.6725 | aggregate_fallback | 0 | 0 | 0 |  | 20.0829 |  | 21.5352 | aggregate_fallback | 0 | 0 |  | 0 | 6.26971e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  | 86.6713 | aggregate_fallback | 0 | 0 | 0 |  | 11.5757 |  | 22.8662 | aggregate_fallback | 0 | 0 |  | 0 | 1.00644e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF4 | reg_mma |  | 86.6725 | aggregate_fallback | 0 | 0 | 0 |  | 19.8401 |  | 23.8576 | aggregate_fallback | 0 | 0 |  | 0 | 1.63085e+07 |  | 0 |  |  |
| reg_mma_W1_B4_RF8 | reg_mma |  | 86.6713 | aggregate_fallback | 0 | 0 | 0 |  | 18.7188 |  | 18.8225 | aggregate_fallback | 0 | 0 |  | 0 | 3.6645e+07 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 77.4849 | aggregate_fallback | 0 | 0 | 0 |  | 86.6828 |  | 96.2353 | aggregate_fallback | 0 | 0 |  | 0 | 103296 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 76.8728 | aggregate_fallback | 0 | 0 | 0 |  | 86.9988 |  | 99.034 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 80.0746 | aggregate_fallback | 0 | 0 | 0 |  | 88.2784 |  | 96.0995 | aggregate_fallback | 0 | 0 |  | 0 | 6784 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 81.28 | aggregate_fallback | 0 | 0 | 0 |  | 79.8441 |  | 99.3878 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 79.3825 | aggregate_fallback | 0 | 0 | 0 |  | 85.159 |  | 108.872 | aggregate_fallback | 0 | 0 |  | 0 | 3200 |  | 0 |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  | 0 |  | 1.33338e+06 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.000338877 |
| reg_mma_W1_B4_RF16 | reg_mma |  | 0 |  | 6.26971e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00103587 |
| reg_mma_W1_B4_RF2 | reg_mma |  | 0 |  | 1.00644e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.0012186 |
| reg_mma_W1_B4_RF4 | reg_mma |  | 0 |  | 1.63085e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00104097 |
| reg_mma_W1_B4_RF8 | reg_mma |  | 0 |  | 3.6645e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.00120098 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  | 0 |  | 103296 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 2.90811e-05 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.34579e-07 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  | 0 |  | 6784 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.98131e-06 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.34579e-07 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only |  | 0 |  | 3200 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 9.52381e-07 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 |  |  | 103.579 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF16 |  |  | 20.0829 |  |  |  |  | 0/0/0 | // |  |  | // |  | 8.21986/91.7801/0 |
| reg_mma_W1_B4_RF2 |  |  | 11.5757 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF4 |  |  | 19.8401 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_mma_W1_B4_RF8 |  |  | 18.7188 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  | 86.6828 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF16 |  |  | 86.9988 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF2 |  |  | 88.2784 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF4 |  |  | 79.8441 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF8 |  |  | 85.159 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |

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

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 6.56e+07 | 3.28e+07 | 2 |  | 2.68698e+11 |  | 47.4384 | 8.25417 | 33.3333 | 35 |
| reg_mma_W1_B4_RF16 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 1.0496e+09 | 5.248e+08 | 2 |  | 4.29916e+12 |  | 43.7226 | 8.22481 | 33.3333 | 30 |
| reg_mma_W1_B4_RF2 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 1.312e+08 | 6.56e+07 | 2 |  | 5.37395e+11 |  | 39.7471 | 8.17486 | 33.3333 | 26 |
| reg_mma_W1_B4_RF4 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 2.624e+08 | 1.312e+08 | 2 |  | 1.07479e+12 |  | 41.9647 | 8.20184 | 33.3333 | 30 |
| reg_mma_W1_B4_RF8 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 5.248e+08 | 2.624e+08 | 2 |  | 2.14958e+12 |  | 43.0963 | 8.20882 | 33.3333 | 30 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |  |  |  | 0 | 7.38227 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |  |  |  | 0 | 7.49425 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |  |  |  | 0 | 7.2796 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |  |  |  | 0 | 7.42539 | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF8 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  |  |  |  | 0 | 7.2704 | 33.3333 | 16 |

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
