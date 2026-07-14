# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 64 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 1.87134e+06 |  | 0 | 0 | 5.98829e+07 |  |  |  |  |  |  | 34 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 64 | 8 |  |  |  |  | 0 | 99.9992 | 8.3968e+09 sectors | 8.3968e+09 | 4.28264e+06 |  | 2.68698e+11 | 2.68698e+11 | 1.37389e+08 |  |  |  |  |  |  | 38 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 22.3107 |  |  |  | 0 | 0 |  | 0 | 5.98829e+07 |  | 0 |  |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 99.9992 | 99.9479 | 0.0512732 |  | srcunit_tex_device_read_lookup_hit_miss | 8.39663e+09 | 69928 | 0.999988 | 2.2377e+06 | 1.37044e+08 | 61.2435 | 2.68698e+11 | 2.68698e+11 | 1 |

## L2 Scope And Eviction Diagnostics

These columns diagnose a low A100 L2 hit result. They do not relax the path gate. A high miss count accompanied by DRAM reads is a real off-chip refill signal; a large native/path disagreement indicates different event populations.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | device read/hit/miss sectors | device/all-TEX conservation | coherent | evict-first (%) | evict-normal (%) | evict-last (%) | DRAM read/L2 miss ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W64_B8_LR4 |  |  | 22.3107 | 0/0/0 | / |  |  |  |  |  |
| l2_cg_load_only_W64_B8_LR4 | 99.9992 | 99.9992 | 99.9479 | 8.3968e+09/8.39663e+09/69928 | 0.999988/0.999988 | 1 |  |  |  | 61.2435 |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only |  |  |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
