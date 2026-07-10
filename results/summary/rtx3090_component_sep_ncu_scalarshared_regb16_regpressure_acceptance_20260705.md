# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_capacity_candidate | 0 | 0 | 1 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 8 |
| register_control_candidate | 2 | 0 | 1 |
| shared_memory_path | 1 | 0 | 1 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.5412 | 50.9357 | 0 | 0 | 1.7803e+08 | 1.3532e+08 | 0.002702 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.3796 | 53.0632 | 0 | 0 | 2.6662e+08 | 1.837e+08 | 0.002513 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 7e-06 | 0.155589 | 0 | 5.37395e+11 | 5.38951e+11 | 5.38659e+11 | 1769.01 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.16201 | 0 | 1.07479e+12 | 5.3922e+11 | 5.38861e+11 | 1347.53 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.236097 | 0 | 2.68698e+11 | 1.34853e+11 | 1.34749e+11 | 108.659 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 20.5793 | 24.823 | 0 | 0 | 2.51277e+06 | 1.8697e+06 | 0.125022 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9991 | 56.9783 | 0 | 1.07479e+12 | 3.29764e+08 | 2.53723e+08 | 17.4332 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9414 | 0 | 5.37395e+11 | 5.37998e+11 | 5.44981e+08 | 872.744 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3599 | 99.8259 | 0 | 1.07479e+12 | 1.25474e+11 | 3.19853e+08 | 70.8199 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9976 | 52.4194 | 0 | 2.68698e+11 | 1.71102e+08 | 1.29902e+08 | 0.037363 |
| reg_fragment_only | register_control_candidate | accepted | pass | 27.4064 | 65.2748 | 0 | 0 | 1.77514e+07 | 1.34913e+07 | 0.011146 |
| reg_mma | tensor_increment_candidate | accepted | pass | 41.2173 | 63.996 | 0 | 0 | 2.5706e+07 | 1.75702e+07 | 0.024088 |
| reg_operand_only | register_control_candidate | accepted | pass | 32.3955 | 70.9087 | 0 | 0 | 3.91571e+07 | 2.93234e+07 | 0.023195 |
| reg_pressure | register_control_candidate | rejected | l2_traffic_too_high_for_register_control;dram_traffic_too_high_for_register_control | 21.4558 | 49.8481 | 0 | 0 | 4.54489e+08 | 3.62733e+08 | 0.001171 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 26.8445 | 54.5952 | 5.37401e+11 | 0 | 4.33068e+08 | 3.2294e+08 | 0.000806 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.3907 | 66.4118 | 1.34354e+11 | 0 | 1.45311e+08 | 1.11153e+08 | 0.002085 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 21.3986 | 85.7669 | 5.37401e+11 | 0 | 2.70781e+08 | 1.97173e+08 | 0.002156 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9818 | 99.5379 | 0 | 0 | 4.24595e+09 | 4.04224e+07 | 0.019727 |
