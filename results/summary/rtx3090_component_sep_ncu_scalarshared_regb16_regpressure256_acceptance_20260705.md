# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_capacity_candidate | 0 | 0 | 1 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 8 |
| register_control_candidate | 3 | 0 | 0 |
| shared_memory_path | 1 | 0 | 1 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.827 | 56.4008 | 0 | 0 | 1.58994e+08 | 1.21445e+08 | 0.002824 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.189 | 61.1903 | 0 | 0 | 2.51838e+08 | 1.7529e+08 | 0.001487 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 0.155932 | 0 | 5.37395e+11 | 5.39184e+11 | 5.3889e+11 | 1769.13 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.17756 | 0 | 1.07479e+12 | 5.39316e+11 | 5.38986e+11 | 1339.02 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.219304 | 0 | 2.68698e+11 | 1.34935e+11 | 1.3483e+11 | 109.48 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 20.8841 | 2.32843 | 0 | 0 | 2.75193e+07 | 1.84897e+07 | 0.123252 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.999 | 48.5253 | 0 | 1.07479e+12 | 4.21483e+08 | 3.34884e+08 | 17.4263 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9286 | 0 | 5.37395e+11 | 5.3807e+11 | 6.18904e+08 | 872.024 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3695 | 99.7991 | 0 | 1.07479e+12 | 1.25467e+11 | 4.11677e+08 | 70.8111 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9967 | 35.7952 | 0 | 2.68698e+11 | 2.52965e+08 | 1.96885e+08 | 0.029971 |
| reg_fragment_only | register_control_candidate | accepted | pass | 28.3014 | 44.5164 | 0 | 0 | 5.95843e+07 | 4.6428e+07 | 0.019764 |
| reg_mma | tensor_increment_candidate | accepted | pass | 41.4612 | 66.7431 | 0 | 0 | 4.22271e+07 | 3.26312e+07 | 0.023369 |
| reg_operand_only | register_control_candidate | accepted | pass | 32.0884 | 58.9937 | 0 | 0 | 4.64642e+07 | 3.64778e+07 | 0.022925 |
| reg_pressure | register_control_candidate | accepted | pass | 21.2652 | 8.34164 | 0 | 0 | 3.57206e+07 | 2.75081e+07 | 0.020994 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 27.1886 | 54.3581 | 5.37401e+11 | 0 | 4.34563e+08 | 3.31365e+08 | 0.000566 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.5431 | 45.3572 | 1.34354e+11 | 0 | 1.90096e+08 | 1.50957e+08 | 0.002119 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 21.0366 | 64.0742 | 5.37401e+11 | 0 | 2.58526e+08 | 1.90038e+08 | 0.00217 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9818 | 98.949 | 0 | 0 | 4.24657e+09 | 4.1286e+07 | 0.035248 |
