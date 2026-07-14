# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| global_address_control | 3 | 0 | 0 |
| global_l1_hit_path | 3 | 0 | 0 |
| shared_address_control | 3 | 0 | 0 |
| shared_memory_path | 3 | 0 | 0 |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | native-derived delta (pp) | L2 sector conservation | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only | global_address_control | accepted | pass | contiguous |  | 59.5969 | 26.1984 | 33.3985 |  | 0 sectors | 0 sectors | 7.45432e+06 sectors | 0 | 0 | 0 | 0 | 0 | 2.38538e+08 | 2.38538e+08 |  | 1.17965e+06 | 0.000408 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.6198 |  |  | 0 sectors | 0 sectors | 1.87002e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.98408e+07 | 5.98408e+07 |  | 1.17965e+06 | 0.002722 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  | 100 | 20.7533 | 79.2467 |  | 0 sectors | 0 sectors | 3.79232e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.21354e+08 | 1.21354e+08 |  | 1.17965e+06 | 0.000826 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9999 | 47.9313 | 20.273 | 27.6584 | 3.57428 | 3.35872e+10 sectors | 122755 sectors | 8.64317e+06 sectors | 0 | 1.07479e+12 | 1.07479e+12 | 3.92816e+06 | 4.56208e+06 | 2.76582e+08 | 2.7924e+08 |  | 1.17965e+06 | 2.60425 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9992 | 99.8668 | 17.4586 | 82.4081 | 0.0405598 | 8.3968e+09 sectors | 518641 sectors | 2.72669e+06 sectors | 0 | 2.68698e+11 | 2.68696e+11 | 1.65965e+07 | 4480 | 8.72541e+07 | 1.0352e+08 |  | 1.17965e+06 | 1.52756 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9999 | 99.9835 | 23.35 | 76.6335 | 11.9961 | 1.67936e+10 sectors | 20992 sectors | 4.31415e+06 sectors | 0 | 5.37395e+11 | 5.37395e+11 | 671744 | 7.38758e+06 | 1.38053e+08 | 1.38053e+08 |  | 1.17965e+06 | 1.87994 |
| shared_scalar_addr_only | shared_address_control | accepted | pass | contiguous |  | 100 | 21.7958 | 78.2042 |  | 0 sectors | 0 sectors | 6.98109e+06 sectors | 5.37395e+06 | 0 | 0 | 0 | 0 | 2.23395e+08 | 2.23395e+08 |  | 1.17965e+06 | 0.000771 |
| shared_scalar_addr_only | shared_address_control | accepted | pass | contiguous |  | 0 | 21.1832 | 21.1832 |  | 0 sectors | 0 sectors | 1.84944e+06 sectors | 5.37395e+06 | 0 | 0 | 0 | 0 | 5.91821e+07 | 5.91821e+07 |  | 1.17965e+06 | 0.004877 |
| shared_scalar_addr_only | shared_address_control | accepted | pass | contiguous |  |  | 11.2873 |  | 0 | 0 sectors | 3.71888e+06 sectors | 5.88478e+06 sectors | 5.37395e+06 | 0 | 0 | 1.19004e+08 | 0 | 1.88313e+08 | 2.86993e+08 |  | 1.17965e+06 | 0.001545 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  | 69.8307 | 21.45 | 48.3807 |  | 0 sectors | 0 sectors | 7.5941e+06 sectors | 1.0748e+12 | 0 | 0 | 0 | 1.68267e+07 | 2.43011e+08 | 2.43011e+08 |  | 1.17965e+06 | 0.001487 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 15.6141 |  | 0 | 0 sectors | 931245 sectors | 2.39382e+06 sectors | 2.68703e+11 | 0 | 0 | 2.97998e+07 | 0 | 7.66022e+07 | 1.02752e+08 |  | 1.17965e+06 | 0.002284 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 21.1833 |  |  | 0 sectors | 0 sectors | 3.80866e+06 sectors | 5.37401e+11 | 0 | 0 | 0 | 0 | 1.21877e+08 | 1.21877e+08 |  | 1.17965e+06 | 0.001126 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator.
