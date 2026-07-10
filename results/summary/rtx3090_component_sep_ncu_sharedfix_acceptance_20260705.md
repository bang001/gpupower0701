# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_capacity_candidate | 0 | 0 | 1 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 8 |
| register_control_candidate | 2 | 0 | 0 |
| shared_memory_path | 0 | 0 | 1 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.9032 | 54.2557 | 0 | 0 | 1.6519e+08 | 1.2457e+08 | 0.002732 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 20.9985 | 56.3586 | 0 | 0 | 2.67718e+08 | 1.86897e+08 | 0.002394 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 7e-06 | 0.155081 | 0 | 5.37395e+11 | 5.38918e+11 | 5.38632e+11 | 1779.75 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.164232 | 0 | 1.07479e+12 | 5.39033e+11 | 5.38713e+11 | 1359.58 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.227064 | 0 | 2.68698e+11 | 1.34852e+11 | 1.34747e+11 | 109.676 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 21.1128 | 22.4714 | 0 | 0 | 2.78954e+06 | 2.13427e+06 | 0.120952 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.999 | 54.1408 | 0 | 1.07479e+12 | 3.60889e+08 | 2.77051e+08 | 17.4288 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9489 | 0 | 5.37395e+11 | 5.37952e+11 | 5.0709e+08 | 868.648 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3624 | 99.7798 | 0 | 1.07479e+12 | 1.25435e+11 | 3.10626e+08 | 70.7878 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9977 | 53.0073 | 0 | 2.68698e+11 | 1.68159e+08 | 1.30211e+08 | 0.0307 |
| reg_fragment_only | register_control_candidate | accepted | pass | 30.0087 | 11.0823 | 0 | 0 | 1.30283e+07 | 9.02976e+06 | 0.00567 |
| reg_mma | tensor_increment_candidate | accepted | pass | 47.0732 | 84.4251 | 0 | 0 | 9.41805e+06 | 5.83514e+06 | 0.012121 |
| reg_operand_only | register_control_candidate | accepted | pass | 32.3955 | 91.0645 | 0 | 0 | 9.15078e+06 | 5.3536e+06 | 0.01213 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 27.1429 | 54.4387 | 5.37401e+11 | 0 | 4.15986e+08 | 3.13143e+08 | 0.000518 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.3537 | 55.5801 | 1.34354e+11 | 0 | 1.55392e+08 | 1.19065e+08 | 0.00237 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9818 | 99.6937 | 0 | 0 | 4.23991e+09 | 3.48225e+07 | 0.019253 |
