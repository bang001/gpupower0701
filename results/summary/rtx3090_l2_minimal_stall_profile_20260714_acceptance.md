# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| global_address_control | 1 | 0 | 0 |
| l2_hit_path | 1 | 0 | 0 |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | native-derived delta (pp) | L2 sector conservation | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only | global_address_control | accepted | pass | contiguous |  | 0 | 23.4247 | 23.4247 |  | 0 sectors | 0 sectors | 1.86946e+06 sectors |  | 0 | 0 | 0 | 3.9177e+06 | 5.98228e+07 | 5.98228e+07 |  | 1.17965e+06 | 0.003502 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9991 | 99.9451 | 0.0539898 | 0.99998 | 8.3968e+09 sectors | 8.39696e+09 sectors | 4.76484e+06 sectors |  | 2.68698e+11 | 0 | 2.68703e+11 | 2.35443e+06 | 1.52475e+08 | 1.58439e+08 | 1.00002 | 1.17965e+06 | 369.971 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator.
