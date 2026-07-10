# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 1 | 0 | 0 |
| global_l1_hit_path | 1 | 0 | 0 |
| l2_hit_path | 1 | 0 | 0 |
| not_selected | 0 | 0 | 1 |
| register_control_candidate | 2 | 0 | 0 |
| shared_memory_path | 1 | 0 | 0 |
| tensor_increment_candidate | 2 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 20.846 | 50.2693 | 0 | 0 | 1.58399e+08 | 1.18954e+08 | 0.002551 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 1.14747 | 0 | 5.37395e+11 | 5.39261e+11 | 5.33522e+11 | 1787.03 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9997 | 101.675 | 0 | 1.07479e+12 | 2.1452e+08 | 1.70847e+08 | 17.4317 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 7e-06 | 99.961 | 0 | 5.37395e+11 | 5.38069e+11 | 6.08968e+08 | 865.733 |
| reg_mma | tensor_increment_candidate | accepted | pass | 35.7274 | 81.6141 | 0 | 0 | 5.44255e+08 | 3.85784e+08 | 0.005973 |
| reg_mma | tensor_increment_candidate | accepted | pass | 37.5218 | 48.263 | 0 | 0 | 2.83158e+08 | 2.10225e+08 | 0.008349 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.9991 | 58.8888 | 0 | 0 | 5.18752e+08 | 3.88583e+08 | 0.003941 |
| reg_operand_only | register_control_candidate | accepted | pass | 32.01 | 22.8084 | 0 | 0 | 1.38338e+08 | 1.07153e+08 | 0.005612 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.7889 | 58.2832 | 5.37401e+11 | 0 | 3.98446e+08 | 2.94741e+08 | 0.001958 |
