# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 |  |  |  |  |  |  |  |  |  |  | 0 |  |  | 6.56e+07 |  |  |  |  |  | 35 | 0 | 0 | partial |  |
| reg_mma_W1_B4_RF2 | reg_mma | 1 | 4 |  |  |  |  |  |  |  |  |  |  | 0 |  |  | 1.312e+08 |  |  |  |  |  | 26 | 0 | 0 | partial |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 |  |  |  |  |  |  |  |  |  |  | 0 |  |  | 0 |  |  |  |  |  | 16 | 0 | 0 | partial |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 1 | 4 |  |  |  |  |  |  |  |  |  |  | 0 |  |  | 0 |  |  |  |  |  | 16 | 0 | 0 | partial |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  |  |  |  |  |  |  |  |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  |  |  |  |  |  |  |  |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  |  |  |  |  |  |  |  |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  |  |  |  |  |  |  |  |  |  |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 |  |  |  |  |  |  |  | // | // |  |  | // |  | // |
| reg_mma_W1_B4_RF2 |  |  |  |  |  |  |  | // | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF1 |  |  |  |  |  |  |  | // | // |  |  | // |  | // |
| reg_operand_only_W1_B4_RF2 |  |  |  |  |  |  |  | // | // |  |  | // |  | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma |  |  |
| reg_mma_W1_B4_RF2 | reg_mma |  |  |
| reg_operand_only_W1_B4_RF1 | reg_operand_only |  |  |
| reg_operand_only_W1_B4_RF2 | reg_operand_only |  |  |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma_W1_B4_RF1 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 6.56e+07 | 3.28e+07 | 2 | 2.68698e+11 | 2.68698e+11 | 1 | 47.438 |  | 33.3333 | 35 |
| reg_mma_W1_B4_RF2 | reg_mma | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 39.7446 |  | 33.3333 | 26 |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 |  | 33.3333 | 16 |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | application | none | full | 1 | normal | contiguous | 1.17965e+06 | 0 |  |  | 0 |  |  | 0 |  | 33.3333 | 16 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| reg_mma_W1_B4_RF1 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_mma_W1_B4_RF2 | reg_mma | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| reg_operand_only_W1_B4_RF2 | reg_operand_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
