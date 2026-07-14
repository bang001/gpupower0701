# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 4 | 0 | 0 |
| global_address_control | 14 | 0 | 0 |
| global_l1_hit_path | 5 | 0 | 0 |
| l2_hit_path | 5 | 0 | 0 |
| not_selected | 0 | 0 | 1 |
| register_control_candidate | 5 | 0 | 0 |
| shared_memory_path | 5 | 0 | 0 |
| tensor_increment_candidate | 5 | 0 | 0 |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | native-derived delta (pp) | L2 sector conservation | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | contiguous |  |  | 19.5599 |  |  | 0 sectors | 0 sectors | 1.86296e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.96146e+07 | 6.01452e+07 |  | 1.17965e+06 | 0.002683 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | contiguous | 0 | 2.51524e-05 | 0.009758 | 0.00973285 | 1 | 2.0992e+09 sectors | 2.0992e+09 sectors | 2.10178e+09 sectors | 0 | 6.71744e+10 | 0 | 6.71744e+10 | 6.71744e+10 | 6.7257e+10 | 6.72578e+10 |  | 1.17965e+06 | 543.679 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | contiguous | 0 | 0.000444108 | 0.010693 | 0.0102489 | 1 | 3.35872e+10 sectors | 3.35872e+10 sectors | 3.36271e+10 sectors | 0 | 1.07479e+12 | 0 | 1.07479e+12 | 1.07479e+12 | 1.07607e+12 | 1.07607e+12 |  | 1.17965e+06 | 729.065 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | contiguous | 0 | 0.00402388 | 0.014392 | 0.0103681 | 0.999783 | 8.3968e+09 sectors | 8.39894e+09 sectors | 8.4082e+09 sectors | 0 | 2.68698e+11 | 0 | 2.68766e+11 | 2.68697e+11 | 2.69063e+11 | 2.69155e+11 |  | 1.17965e+06 | 701.554 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | contiguous | 0 | 0.000494997 | 0.011139 | 0.010644 | 1.00007 | 1.67936e+10 sectors | 1.67937e+10 sectors | 1.68138e+10 sectors | 0 | 5.37395e+11 | 0 | 5.37399e+11 | 5.37432e+11 | 5.3804e+11 | 5.38047e+11 |  | 1.17965e+06 | 725.559 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 19.045 |  |  | 0 sectors | 0 sectors | 1.24122e+06 sectors | 0 | 0 | 0 | 0 | 0 | 3.97189e+07 | 3.97189e+07 |  | 1.17965e+06 | 0.005569 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 20.3076 |  |  | 0 sectors | 0 sectors | 1.49599e+07 sectors | 0 | 0 | 0 | 0 | 0 | 4.78717e+08 | 4.78717e+08 |  | 1.17965e+06 | 0.000394 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  | 0 | 21.2541 | 21.2541 |  | 0 sectors | 0 sectors | 3.80396e+06 sectors | 0 | 0 | 0 | 0 | 2.13791e+07 | 1.21727e+08 | 1.21727e+08 |  | 1.17965e+06 | 0.002458 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  | 0 | 20.502 | 20.502 |  | 0 sectors | 0 sectors | 7.45481e+06 sectors | 0 | 0 | 0 | 0 | 8.20378e+07 | 2.38554e+08 | 2.38554e+08 |  | 1.17965e+06 | 0.000775 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.3155 |  |  | 0 sectors | 0 sectors | 638600 sectors | 0 | 0 | 0 | 0 | 0 | 2.04352e+07 | 2.04352e+07 |  | 1.17965e+06 | 0.005884 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.7304 |  |  | 0 sectors | 0 sectors | 7.43774e+06 sectors | 0 | 0 | 0 | 0 | 0 | 2.38008e+08 | 2.38008e+08 |  | 1.17965e+06 | 0.000387 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 20.4796 |  |  | 0 sectors | 0 sectors | 1.15505e+06 sectors | 0 | 0 | 0 | 0 | 0 | 3.69615e+07 | 3.69615e+07 |  | 1.17965e+06 | 0.003077 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 22.1731 |  |  | 0 sectors | 0 sectors | 1.94032e+06 sectors | 0 | 0 | 0 | 0 | 0 | 6.20904e+07 | 6.20904e+07 |  | 1.17965e+06 | 0.001552 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.1733 |  |  | 0 sectors | 0 sectors | 3.73606e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.19554e+08 | 1.19554e+08 |  | 1.17965e+06 | 0.000819 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.5682 |  |  | 0 sectors | 0 sectors | 626168 sectors | 0 | 0 | 0 | 0 | 0 | 2.00374e+07 | 2.00374e+07 |  | 1.17965e+06 | 0.012362 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.6665 |  |  | 0 sectors | 0 sectors | 7.46049e+06 sectors | 0 | 0 | 0 | 0 | 0 | 2.38736e+08 | 2.38736e+08 |  | 1.17965e+06 | 0.00095 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 20.8246 |  |  | 0 sectors | 0 sectors | 1.13054e+06 sectors | 0 | 0 | 0 | 0 | 0 | 3.61774e+07 | 3.61774e+07 |  | 1.17965e+06 | 0.006462 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 21.0087 |  |  | 0 sectors | 0 sectors | 1.97364e+06 sectors | 0 | 0 | 0 | 0 | 0 | 6.31565e+07 | 6.31565e+07 |  | 1.17965e+06 | 0.003446 |
| global_addr_only | global_address_control | accepted | pass | contiguous |  |  | 20.3914 |  |  | 0 sectors | 0 sectors | 3.97887e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.27324e+08 | 1.27324e+08 |  | 1.17965e+06 | 0.001837 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.999 | 100 | 24.4572 | 75.5428 | 1 | 2.0992e+09 sectors | 20992 sectors | 619756 sectors | 0 | 6.71744e+10 | 6.71737e+10 | 671744 | 0 | 1.98322e+07 | 1.98322e+07 |  | 1.17965e+06 | 4.56812 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9999 | 100 | 20.2322 | 79.7678 | 1 | 3.35872e+10 sectors | 20992 sectors | 8.67712e+06 sectors | 0 | 1.07479e+12 | 1.07479e+12 | 671744 | 0 | 2.77668e+08 | 2.77668e+08 |  | 1.17965e+06 | 1.9885 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9995 | 100 | 22.8948 | 77.1052 | 1 | 4.1984e+09 sectors | 20992 sectors | 1.23952e+06 sectors | 0 | 1.34349e+11 | 1.34348e+11 | 671744 | 0 | 3.96645e+07 | 3.96645e+07 |  | 1.17965e+06 | 2.09408 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9998 | 100 | 19.672 | 80.328 | 1 | 8.3968e+09 sectors | 20992 sectors | 2.4604e+06 sectors | 0 | 2.68698e+11 | 2.68697e+11 | 671744 | 0 | 7.87329e+07 | 7.87329e+07 |  | 1.17965e+06 | 1.61067 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | contiguous | 99.9999 | 100 | 21.0947 | 78.9053 | 1 | 1.67936e+10 sectors | 20992 sectors | 4.33999e+06 sectors | 0 | 5.37395e+11 | 5.37395e+11 | 671744 | 0 | 1.3888e+08 | 1.3888e+08 |  | 1.17965e+06 | 1.87275 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9964 | 99.9383 | 0.0580391 | 1 | 2.0992e+09 sectors | 2.0992e+09 sectors | 1.32054e+06 sectors | 0 | 6.71744e+10 | 0 | 6.71744e+10 | 2.43904e+06 | 4.22573e+07 | 4.25307e+07 | 1 | 1.17965e+06 | 313.425 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9998 | 99.9506 | 0.049204 | 0.999995 | 3.35872e+10 sectors | 3.35874e+10 sectors | 1.65154e+07 sectors | 0 | 1.07479e+12 | 0 | 1.0748e+12 | 2.3543e+06 | 5.28492e+08 | 5.34584e+08 | 1.00001 | 1.17965e+06 | 413.894 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9982 | 99.9429 | 0.0553123 | 1 | 4.1984e+09 sectors | 4.1984e+09 sectors | 2.40923e+06 sectors | 0 | 1.34349e+11 | 0 | 1.34349e+11 | 2.40448e+06 | 7.70954e+07 | 7.74898e+07 | 1 | 1.17965e+06 | 326.075 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9991 | 99.9531 | 0.0459979 | 1 | 8.3968e+09 sectors | 8.3968e+09 sectors | 3.96094e+06 sectors | 0 | 2.68698e+11 | 0 | 2.68698e+11 | 2.30566e+06 | 1.2675e+08 | 1.27301e+08 | 1 | 1.17965e+06 | 371.434 |
| l2_cg_load_only | l2_hit_path | accepted | pass | contiguous | 0 | 99.9996 | 99.9517 | 0.0478797 | 1 | 1.67936e+10 sectors | 1.67936e+10 sectors | 8.12833e+06 sectors | 0 | 5.37395e+11 | 0 | 5.37395e+11 | 2.35008e+06 | 2.60107e+08 | 2.61077e+08 | 1 | 1.17965e+06 | 400.632 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 30.9809 |  |  | 0 sectors | 0 sectors | 168492 sectors | 0 | 0 | 0 | 0 | 0 | 5.39174e+06 | 5.39174e+06 |  | 1.17965e+06 | 0.021948 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 22.169 |  |  | 0 sectors | 0 sectors | 3.20517e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.02565e+08 | 1.02565e+08 |  | 1.17965e+06 | 0.00199 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 37.2597 |  |  | 0 sectors | 0 sectors | 202748 sectors | 0 | 0 | 0 | 0 | 0 | 6.48794e+06 | 6.48794e+06 |  | 1.17965e+06 | 0.013473 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 23.6541 |  |  | 0 sectors | 0 sectors | 751876 sectors | 0 | 0 | 0 | 0 | 0 | 2.406e+07 | 2.406e+07 |  | 1.17965e+06 | 0.00734 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 20.5344 |  |  | 0 sectors | 0 sectors | 1.77559e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.68188e+07 | 5.68188e+07 |  | 1.17965e+06 | 0.003781 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 23.2597 |  |  | 0 sectors | 0 sectors | 132208 sectors | 0 | 0 | 0 | 0 | 0 | 4.23066e+06 | 4.23066e+06 |  | 1.17965e+06 | 0.034915 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 24.91 |  |  | 0 sectors | 0 sectors | 620204 sectors | 0 | 0 | 0 | 0 | 0 | 1.98465e+07 | 1.98465e+07 |  | 1.17965e+06 | 0.00762 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 31.4312 |  |  | 0 sectors | 0 sectors | 61756 sectors | 0 | 0 | 0 | 0 | 0 | 1.97619e+06 | 1.97619e+06 |  | 1.17965e+06 | 0.03644 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 93.5066 |  |  | 0 sectors | 0 sectors | 3772 sectors | 0 | 0 | 0 | 0 | 0 | 120704 | 120704 |  | 1.17965e+06 | 0.024625 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 14.384 |  |  | 0 sectors | 0 sectors | 603052 sectors | 0 | 0 | 0 | 0 | 0 | 1.92977e+07 | 1.92977e+07 |  | 1.17965e+06 | 0.013649 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 19.5439 |  |  | 0 sectors | 0 sectors | 619764 sectors | 6.71798e+10 | 0 | 0 | 0 | 0 | 1.98324e+07 | 1.98324e+07 |  | 1.17965e+06 | 0.0084 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 20.6004 |  |  | 0 sectors | 0 sectors | 7.55335e+06 sectors | 1.0748e+12 | 0 | 0 | 0 | 0 | 2.41707e+08 | 2.41707e+08 |  | 1.17965e+06 | 0.000613 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 25.6956 |  |  | 0 sectors | 0 sectors | 803564 sectors | 1.34354e+11 | 0 | 0 | 0 | 0 | 2.5714e+07 | 2.5714e+07 |  | 1.17965e+06 | 0.004269 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 18.6165 |  |  | 0 sectors | 0 sectors | 2.28146e+06 sectors | 2.68703e+11 | 0 | 0 | 0 | 0 | 7.30067e+07 | 7.30067e+07 |  | 1.17965e+06 | 0.002305 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | contiguous |  |  | 20.3483 |  |  | 0 sectors | 0 sectors | 3.82686e+06 sectors | 5.37401e+11 | 0 | 0 | 0 | 0 | 1.2246e+08 | 1.2246e+08 |  | 1.17965e+06 | 0.001215 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator.
