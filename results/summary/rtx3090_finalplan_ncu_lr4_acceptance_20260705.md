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
| tensor_increment_candidate | 0 | 0 | 1 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| addr_only | not_selected | rejected | mode_not_final_component_candidate | 20.9413 | 61.0798 | 0 | 0 | 1.47209e+08 | 9.93574e+07 | 0.002881 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 21.17 | 57.6372 | 0 | 0 | 2.61842e+08 | 1.58831e+08 | 0.001438 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 0.156441 | 0 | 5.37395e+11 | 5.3889e+11 | 5.38511e+11 | 1770.6 |
| dram_load_only | not_selected | rejected | mode_not_final_component_candidate | 49.9997 | 0.162914 | 0 | 1.07479e+12 | 5.39014e+11 | 5.38596e+11 | 1340.46 |
| dram_mma | not_selected | rejected | mode_not_final_component_candidate | 49.9999 | 0.251429 | 0 | 2.68698e+11 | 1.34858e+11 | 1.34716e+11 | 70.4117 |
| empty | not_selected | rejected | mode_not_final_component_candidate | 21.0938 | 3241.94 | 0 | 0 | 660224 | 6016 | 0.129696 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9991 | 58.1914 | 0 | 1.07479e+12 | 3.14066e+08 | 2.19269e+08 | 17.4289 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.9409 | 0 | 5.37395e+11 | 5.37957e+11 | 4.83025e+08 | 866.815 |
| l2_load_only | l2_capacity_candidate | rejected | l1_hit_too_high_for_l2 | 88.3689 | 99.7936 | 0 | 1.07479e+12 | 1.25376e+11 | 2.95498e+08 | 70.7279 |
| l2_mma | not_selected | rejected | mode_not_final_component_candidate | 99.9968 | 61.7257 | 0 | 2.68698e+11 | 2.3418e+08 | 1.60002e+08 | 0.033717 |
| reg_fragment_only | register_control_candidate | accepted | pass | 28.1555 | 78.0094 | 0 | 0 | 3.36911e+07 | 1.8176e+07 | 0.010795 |
| reg_mma | tensor_increment_candidate | rejected | l2_traffic_too_high_for_tensor | 36.4199 | 40.8386 | 0 | 0 | 1.26372e+08 | 8.09829e+07 | 0.012802 |
| reg_operand_only | register_control_candidate | rejected | l2_traffic_too_high_for_register_control | 31.4046 | 60.1825 | 0 | 0 | 1.21153e+08 | 7.73731e+07 | 0.010143 |
| reg_pressure | register_control_candidate | accepted | pass | 21.4367 | 67.282 | 0 | 0 | 4.21656e+07 | 2.5264e+07 | 0.006855 |
| shared_load_only | shared_memory_path | rejected | shared_bank_conflicts_high | 26.8489 | 57.6059 | 5.37401e+11 | 0 | 4.56121e+08 | 3.19504e+08 | 0.000554 |
| shared_mma | not_selected | rejected | mode_not_final_component_candidate | 38.5192 | 45.5763 | 1.34354e+11 | 0 | 2.61894e+08 | 1.83325e+08 | 0.001718 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.9413 | 69.3175 | 5.37401e+11 | 0 | 2.57983e+08 | 1.71737e+08 | 0.002077 |
| store_only | not_selected | rejected | mode_not_final_component_candidate | 99.9898 | 100.52 | 0 | 0 | 4.20432e+09 | 2.23232e+06 | 0.01986 |
