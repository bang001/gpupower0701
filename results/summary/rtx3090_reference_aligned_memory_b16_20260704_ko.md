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
| global_l1_path | 3 | 3.27505 | pJ/bit | 3.2623 | 3.40863 | net_E_J / NCU_actual_path_bits |
| l2_hit_path | 3 | 30.3304 | pJ/bit | 29.1052 | 30.6684 | net_E_J / NCU_actual_path_bits |
| dram_streaming_path | 3 | 31.7713 | pJ/bit | 31.3504 | 31.9194 | net_E_J / NCU_actual_path_bits |
| shared_path_traffic_verified | 6 |  | pJ/bit |  |  | traffic_verified_only_no_ncu_shared_byte_denominator |
| l2_minus_l1_path_delta |  | 27.0554 | pJ/bit |  |  | diagnostic_delta_not_pure_component |
| dram_minus_l2_path_delta |  | 1.4409 | pJ/bit |  |  | diagnostic_delta_not_pure_component |

## Important Interpretation

The path estimates above use NVML board net energy divided by NCU actual path traffic. They are reference-aligned effective path coefficients, not SRAM/HBM bitcell energy. Diagnostic deltas are shown only to test ordering; they are not pure isolated component energy.

## Row QA

| item | count |
|---|---:|
| accepted rows | 15 |
| rejected rows | 63 |

### Accepted Rows

| mode | W_SM (KiB) | blocks/SM | component | pJ/bit | L1 hit (%) | L2 hit (%) | reason |
|---|---:|---:|---|---:|---:|---:|---|
| global_l1_load_only | 16 | 16 | global_l1_path | 3.40863 | 99.999 | 55.6124 | accepted |
| shared_load_only | 16 | 16 | shared_path_traffic_verified |  | 26.8619 | 54.425 | accepted_no_shared_byte_denominator |
| shared_load_only | 64 | 16 | shared_path_traffic_verified |  | 27.169 | 49.5815 | accepted_no_shared_byte_denominator |
| l2_load_only | 64 | 16 | l2_hit_path | 30.6684 | 88.3843 | 99.8014 | accepted |
| dram_load_only | 8192 | 16 | dram_streaming_path | 31.9194 | 49.9997 | 0.173057 | accepted |
| global_l1_load_only | 16 | 16 | global_l1_path | 3.27505 | 99.999 | 55.6124 | accepted |
| shared_load_only | 16 | 16 | shared_path_traffic_verified |  | 26.8619 | 54.425 | accepted_no_shared_byte_denominator |
| shared_load_only | 64 | 16 | shared_path_traffic_verified |  | 27.169 | 49.5815 | accepted_no_shared_byte_denominator |
| l2_load_only | 64 | 16 | l2_hit_path | 30.3304 | 88.3843 | 99.8014 | accepted |
| dram_load_only | 8192 | 16 | dram_streaming_path | 31.7713 | 49.9997 | 0.173057 | accepted |
| global_l1_load_only | 16 | 16 | global_l1_path | 3.2623 | 99.999 | 55.6124 | accepted |
| shared_load_only | 16 | 16 | shared_path_traffic_verified |  | 26.8619 | 54.425 | accepted_no_shared_byte_denominator |
| shared_load_only | 64 | 16 | shared_path_traffic_verified |  | 27.169 | 49.5815 | accepted_no_shared_byte_denominator |
| l2_load_only | 64 | 16 | l2_hit_path | 29.1052 | 88.3843 | 99.8014 | accepted |
| dram_load_only | 8192 | 16 | dram_streaming_path | 31.3504 | 49.9997 | 0.173057 | accepted |

### Rejection Reasons

| reason | rows |
|---|---:|
| blocks_per_sm_not_selected | 39 |
| l1_hit_below_threshold | 3 |
| l2_hit_below_threshold | 3 |
| missing_ncu_join | 9 |
| mode_not_in_memory_path_set | 9 |
