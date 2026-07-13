# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| global_addr_only_l2_W16_B16_LR4 | global_addr_only | 16 | 16 | 0 | sass | 0 | 0 | 20.1982 | 100 | 0 sectors | 349211 | 3.53307e+06 | 0 | 0 | 1.65734e+08 | 1.32522e+08 | 0 | 0.004875 | 47.5401 | 197.628 | 78.3325 |  | 33 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree;l2_read_sector_conservation_failed |
| l2_cg_load_only_W16_B16_LR4 | l2_cg_load_only | 16 | 16 | 0 | sass | 0 | 0 | 0 | 99.9977 | 1.67936e+10 sectors | 1.6794e+10 | 7.71095e+06 | 0 | 5.37395e+11 | 5.37727e+11 | 2.67044e+08 | 0 | 869.303 | 52.5797 | 308.842 | 14.7706 |  | 36 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the srcunit-TEX read hit/miss sectors when available.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W16_B16_LR4 | global_addr_only |  | 20.1982 | aggregate_fallback | 0 | 0 | 0 | 100 | 24.13 | 75.87 | 60.4073 | srcunit_tex_read_lookup_hit_miss | 196882 | 0 | 0.563791 | 0 | 1.13058e+08 |  | 1.11748e+07 |
| l2_cg_load_only_W16_B16_LR4 | l2_cg_load_only | 0 | 6e-06 | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 99.9977 | 99.9542 | 0.0434927 | 99.9542 | srcunit_tex_read_lookup_hit_miss | 1.67936e+10 | 394369 | 1 | 1.26198e+07 | 2.4675e+08 | 19.5526 | 5.37407e+11 |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | warm-up passes | L2 residency | persisting L2 size (bytes) | HMMA inst | logical MMA | HMMA/logical MMA |
|---|---|---|---|---:|---|---:|---:|---:|---:|
| global_addr_only_l2_W16_B16_LR4 | global_addr_only | application | none | 4 | persisting | 4.32538e+06 | 0 |  |  |
| l2_cg_load_only_W16_B16_LR4 | l2_cg_load_only | application | none | 4 | persisting | 4.32538e+06 | 0 |  |  |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| global_addr_only_l2_W16_B16_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W16_B16_LR4 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
