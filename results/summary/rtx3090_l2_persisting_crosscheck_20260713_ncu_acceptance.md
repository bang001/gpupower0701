# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| global_address_control | 1 | 0 | 0 |
| l2_hit_path | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | native-derived delta (pp) | L2 sector conservation | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM bytes | persisting L2 size (bytes) | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only | global_address_control | accepted | pass |  | 100 | 24.13 | 75.87 | 0.563791 | 0 sectors | 349211 sectors | 3.53307e+06 sectors | 0 | 0 | 0 | 1.11748e+07 | 0 | 1.13058e+08 | 1.32522e+08 | 4.32538e+06 | 0.004875 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 0 | 99.9977 | 99.9542 | 0.0434927 | 1 | 1.67936e+10 sectors | 1.6794e+10 sectors | 7.71095e+06 sectors | 0 | 5.37395e+11 | 0 | 5.37407e+11 | 1.26198e+07 | 2.4675e+08 | 2.67044e+08 | 4.32538e+06 | 869.303 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator.
