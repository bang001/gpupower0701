# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 2 | 0 | 0 |
| global_l1_hit_path | 2 | 0 | 0 |
| l2_hit_path | 2 | 0 | 0 |
| not_selected | 0 | 0 | 1 |
| register_control_candidate | 2 | 0 | 0 |
| shared_memory_path | 2 | 0 | 0 |
| tensor_increment_candidate | 2 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.0366 | 46.7131 | 0 | 0 | 1.98628e+08 | 1.50755e+08 | 0.003149 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 1.21093 | 0 | 5.37395e+11 | 5.39032e+11 | 5.33361e+11 | 1767 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 3e-06 | 1.11231 | 0 | 1.07479e+12 | 1.07808e+12 | 1.06708e+12 | 1815.73 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9995 | 87.7015 | 0 | 1.07479e+12 | 2.62032e+08 | 2.0898e+08 | 17.444 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9997 | 98.7348 | 0 | 2.14958e+12 | 4.27661e+08 | 3.3091e+08 | 18.5719 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 7e-06 | 99.9821 | 0 | 5.37395e+11 | 5.37674e+11 | 2.28256e+08 | 866.173 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 3e-06 | 99.9872 | 0 | 1.07479e+12 | 1.07538e+12 | 4.81177e+08 | 943.134 |
| reg_mma | tensor_increment_candidate | accepted | pass | 47.0209 | 32.3909 | 0 | 0 | 1.18169e+08 | 7.61514e+07 | 0.003003 |
| reg_mma | tensor_increment_candidate | accepted | pass | 46.9861 | 32.254 | 0 | 0 | 5.96509e+07 | 3.86884e+07 | 0.004581 |
| reg_operand_only | register_control_candidate | accepted | pass | 25.392 | 37.6914 | 0 | 0 | 1.19932e+08 | 7.378e+07 | 0.001792 |
| reg_operand_only | register_control_candidate | accepted | pass | 26.1934 | 34.4159 | 0 | 0 | 4.45724e+07 | 2.73276e+07 | 0.003177 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.6364 | 73.4132 | 5.37401e+11 | 0 | 4.59046e+08 | 3.4019e+08 | 0.002097 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.9985 | 126.571 | 1.0748e+12 | 0 | 2.06008e+08 | 1.61722e+08 | 0.001087 |
