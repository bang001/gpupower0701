# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_capacity_candidate | 0 | 0 | 1 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 8 |
| register_control_candidate | 1 | 0 | 1 |
| shared_memory_path | 1 | 0 | 1 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.8651 | 41.5404 | 0 | 0 | 2.17685e+08 | 1.7967e+08 | 0.002826 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.3605 | 66.2162 | 0 | 0 | 9.19488e+08 | 6.33304e+08 | 0.001634 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 0.155812 | 0 | 5.37395e+11 | 5.3945e+11 | 5.39153e+11 | 1776.47 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.161987 | 0 | 1.07479e+12 | 5.39596e+11 | 5.39267e+11 | 1343.28 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.219888 | 0 | 2.68698e+11 | 1.35e+11 | 1.34902e+11 | 109.748 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 20.8651 | 24.4927 | 0 | 0 | 2.56102e+06 | 1.9168e+06 | 0.150394 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.999 | 42.5934 | 0 | 1.07479e+12 | 4.63504e+08 | 3.81465e+08 | 17.4261 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 7e-06 | 99.9092 | 0 | 5.37395e+11 | 5.38165e+11 | 7.28161e+08 | 873.118 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3592 | 99.7131 | 0 | 1.07479e+12 | 1.25616e+11 | 4.56407e+08 | 70.7483 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9972 | 38.9853 | 0 | 2.68698e+11 | 2.62948e+08 | 2.13472e+08 | 0.037757 |
| reg_fragment_only | register_control_candidate | rejected | l2_traffic_too_high_for_register_control | 27.9268 | 61.6389 | 0 | 0 | 1.38467e+08 | 9.93357e+07 | 0.010625 |
| reg_mma | tensor_increment_candidate | accepted | pass | 41.3088 | 15.4973 | 0 | 0 | 6.29894e+07 | 4.91094e+07 | 0.022814 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.4547 | 59.8041 | 0 | 0 | 8.65324e+07 | 6.70696e+07 | 0.022787 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 26.8859 | 45.5553 | 5.37401e+11 | 0 | 5.59901e+08 | 4.4881e+08 | 0.000515 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.3406 | 47.6434 | 1.34354e+11 | 0 | 1.81481e+08 | 1.47239e+08 | 0.001936 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 21.2652 | 55.2725 | 5.37401e+11 | 0 | 3.53482e+08 | 2.75507e+08 | 0.002043 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9898 | 99.556 | 0 | 0 | 4.22063e+09 | 1.98125e+07 | 0.023283 |
