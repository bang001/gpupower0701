# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 1 |
| register_control_candidate | 1 | 0 | 0 |
| shared_memory_path | 1 | 0 | 0 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.3986 | 44.4211 | 0 sectors | 704830 sectors | 2.67196e+06 sectors | 0 | 0 | 1.701e+08 | 1.2375e+08 | 0.002553 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 7e-06 | 0.038381 | 1.67936e+10 sectors | 1.67998e+10 sectors | 1.6818e+10 sectors | 0 | 5.37395e+11 | 5.38663e+11 | 5.3847e+11 | 1784.08 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9998 | 57.2715 | 3.35872e+10 sectors | 41984 sectors | 4.3892e+06 sectors | 0 | 1.07479e+12 | 1.79393e+08 | 1.40454e+08 | 17.4343 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 7e-06 | 99.9066 | 1.67936e+10 sectors | 1.67994e+10 sectors | 1.40017e+07 sectors | 0 | 5.37395e+11 | 5.38188e+11 | 7.19515e+08 | 864.97 |
| reg_mma | tensor_increment_candidate | accepted | pass | 36.2957 | 32.3856 | 0 sectors | 431231 sectors | 2.1648e+06 sectors | 0 | 0 | 1.20292e+08 | 9.38189e+07 | 0.010564 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.7291 | 63.2529 | 0 sectors | 427908 sectors | 2.11342e+06 sectors | 0 | 0 | 1.2116e+08 | 9.01961e+07 | 0.009671 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.8079 | 15.0719 | 0 sectors | 724793 sectors | 3.04068e+06 sectors | 5.37401e+11 | 0 | 1.55649e+08 | 1.19054e+08 | 0.001967 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. The byte columns are used as the preferred denominator for pJ/bit or pJ/byte attribution.
