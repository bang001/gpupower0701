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
| shared_memory_path | 0 | 1 | 0 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.7889 | 46.5043 |  | 0 | 1.77484e+08 | 1.37488e+08 | 0.002726 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 20.8841 | 48.3012 |  | 0 | 3.20883e+08 | 2.3603e+08 | 0.001339 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 7e-06 | 0.161789 |  | 5.37395e+11 | 5.3943e+11 | 5.39078e+11 | 1801.64 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.174694 |  | 1.07479e+12 | 5.39351e+11 | 5.39009e+11 | 1363.77 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.188187 |  | 2.68698e+11 | 1.34899e+11 | 1.34798e+11 | 110.834 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 21.0747 | 47.5244 |  | 0 | 1.44646e+06 | 841600 | 0.114894 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.999 | 49.885 |  | 1.07479e+12 | 4.11585e+08 | 3.2769e+08 | 17.4328 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9218 |  | 5.37395e+11 | 5.38071e+11 | 6.16754e+08 | 865.575 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3763 | 99.707 |  | 1.07479e+12 | 1.2535e+11 | 3.71825e+08 | 70.7224 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9977 | 45.8826 |  | 2.68698e+11 | 1.96563e+08 | 1.56992e+08 | 0.037343 |
| reg_fragment_only | register_control_candidate | accepted | pass | 29.0244 | 92.5991 |  | 0 | 2.70323e+06 | 1.37229e+06 | 0.005863 |
| reg_mma | tensor_increment_candidate | accepted | pass | 47.1167 | 89.4692 |  | 0 | 2.23923e+06 | 350464 | 0.011993 |
| reg_operand_only | register_control_candidate | accepted | pass | 32.6394 | 32.3075 |  | 0 | 2.64683e+07 | 2.12197e+07 | 0.011945 |
| shared_load_only | shared_memory_path | provisional | missing_shared_bytes;missing_shared_instruction_count | 27.206 | 52.6471 |  | 0 | 5.00667e+08 | 3.86795e+08 | 0.000552 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.9852 | 53.094 |  | 0 | 1.62494e+08 | 1.28448e+08 | 0.001918 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9818 | 99.1974 |  | 0 | 4.24367e+09 | 3.58275e+07 | 0.019777 |
