# Reference-Aligned Memory Energy Analysis

## Acceptance Rules

| rule | value |
|---|---:|
| L1 hit min (%) | 95 |
| L1 row max L2/L1 byte ratio | 0.01 |
| L2 hit min (%) | 80 |
| L2 row min L2/L1 byte ratio | 0.02 |
| L2 row max DRAM/L2 byte ratio | 0.02 |
| DRAM row max L2 hit (%) | 5 |

## Component/Path Estimates

| component/path | accepted rows | estimate | unit | min | max | method |
|---|---:|---:|---|---:|---:|---|
| global_l1_path | 1 | 1.66752 | pJ/bit | 1.66752 | 1.66752 | net_E_J / NCU_actual_path_bits |
| l2_hit_path | 1 | 15.4749 | pJ/bit | 15.4749 | 15.4749 | net_E_J / NCU_actual_path_bits |
| dram_streaming_path | 1 | 14.956 | pJ/bit | 14.956 | 14.956 | net_E_J / NCU_actual_path_bits |
| shared_path_traffic_verified | 2 |  | pJ/bit |  |  | traffic_verified_only_no_ncu_shared_byte_denominator |
| l2_minus_l1_path_delta |  | 13.8074 | pJ/bit |  |  | diagnostic_delta_not_pure_component |
| dram_minus_l2_path_delta |  | -0.5189 | pJ/bit |  |  | diagnostic_delta_not_pure_component |

## Important Interpretation

The path estimates above use NVML board net energy divided by NCU actual path traffic. They are reference-aligned effective path coefficients, not SRAM/HBM bitcell energy. Diagnostic deltas are shown only to test ordering; they are not pure isolated component energy.

## Row QA

| item | count |
|---|---:|
| accepted rows | 5 |
| rejected rows | 8 |

### Accepted Rows

| mode | W_SM (KiB) | blocks/SM | component | pJ/bit | L1 hit (%) | L2 hit (%) | reason |
|---|---:|---:|---|---:|---:|---:|---|
| global_l1_load_only | 16 | 16 | global_l1_path | 1.66752 | 99.9991 | 54.7983 | accepted |
| shared_load_only | 16 | 16 | shared_path_traffic_verified |  | 26.7796 | 41.512 | accepted_no_shared_byte_denominator |
| shared_load_only | 64 | 16 | shared_path_traffic_verified |  | 26.9297 | 36.4107 | accepted_no_shared_byte_denominator |
| l2_load_only | 64 | 16 | l2_hit_path | 15.4749 | 87.4992 | 99.7379 | accepted |
| dram_load_only | 8192 | 16 | dram_streaming_path | 14.956 | 49.9998 | 0.149232 | accepted |

### Rejection Reasons

| reason | rows |
|---|---:|
| l2_hit_below_threshold | 1 |
| missing_ncu_join | 4 |
| mode_not_in_memory_path_set | 3 |
