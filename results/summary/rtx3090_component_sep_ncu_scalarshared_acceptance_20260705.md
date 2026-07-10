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
| shared_memory_path | 1 | 0 | 1 |
| tensor_increment_candidate | 1 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 21.3034 | 46.4094 | 0 | 0 | 1.81784e+08 | 1.4475e+08 | 0.002716 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.1128 | 55.079 | 0 | 0 | 2.55347e+08 | 1.77452e+08 | 0.001384 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 7e-06 | 0.160443 | 0 | 5.37395e+11 | 5.39242e+11 | 5.3894e+11 | 1768.24 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.163338 | 0 | 1.07479e+12 | 5.39328e+11 | 5.38995e+11 | 1338.86 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.231574 | 0 | 2.68698e+11 | 1.34922e+11 | 1.34821e+11 | 108.567 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 21.1509 | 16.0966 | 0 | 0 | 4.23981e+06 | 3.59488e+06 | 0.11756 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9991 | 48.3978 | 0 | 1.07479e+12 | 3.76402e+08 | 3.00274e+08 | 17.4197 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9313 | 0 | 5.37395e+11 | 5.38035e+11 | 5.85991e+08 | 868.636 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3824 | 99.7322 | 0 | 1.07479e+12 | 1.25281e+11 | 3.68831e+08 | 70.6814 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9972 | 44.7625 | 0 | 2.68698e+11 | 2.31516e+08 | 1.85169e+08 | 0.03074 |
| reg_fragment_only | register_control_candidate | accepted | pass | 29.9303 | 86.7276 | 0 | 0 | 1.65926e+06 | 417280 | 0.005686 |
| reg_mma | tensor_increment_candidate | accepted | pass | 47.108 | 372.428 | 0 | 0 | 2.15712e+06 | 203136 | 0.012826 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.2544 | 111.128 | 0 | 0 | 7.49098e+06 | 5.33901e+06 | 0.012076 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 27.1124 | 51.6173 | 5.37401e+11 | 0 | 4.56293e+08 | 3.54165e+08 | 0.000561 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 43.6019 | 58.8585 | 1.34354e+11 | 0 | 1.62872e+08 | 1.28516e+08 | 0.002017 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 21.1319 | 49.4491 | 5.37401e+11 | 0 | 3.44276e+08 | 2.61844e+08 | 0.002052 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9818 | 99.3466 | 0 | 0 | 4.25406e+09 | 4.885e+07 | 0.019458 |
