# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| dram_sanity_path | 3 | 0 | 0 |
| global_l1_hit_path | 3 | 0 | 0 |
| l2_hit_path | 3 | 0 | 0 |
| not_selected | 0 | 0 | 1 |
| register_control_candidate | 5 | 0 | 0 |
| shared_memory_path | 3 | 0 | 0 |
| tensor_increment_candidate | 5 | 0 | 0 |

| mode | component | acceptance | reason | L1 hit (%) | L2 hit (%) | shared bytes | L1 bytes | L2 bytes | DRAM bytes | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | 20.8841 | 72.874 | 0 | 0 | 2.04873e+08 | 1.56682e+08 | 0.002485 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 2e-06 | 0.191041 | 0 | 2.14958e+12 | 2.15615e+12 | 2.15497e+12 | 1839.39 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 6e-06 | 0.104067 | 0 | 5.37395e+11 | 5.38836e+11 | 5.38608e+11 | 1747.88 |
| dram_cg_load_only | dram_sanity_path | accepted | pass | 3e-06 | 0.081395 | 0 | 1.07479e+12 | 1.07786e+12 | 1.07733e+12 | 1819.66 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9992 | 24.9571 | 0 | 4.29916e+12 | 1.56133e+09 | 1.22093e+09 | 19.1984 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9982 | 66.9942 | 0 | 1.07479e+12 | 5.92794e+08 | 4.52661e+08 | 17.4469 |
| global_l1_load_only | global_l1_hit_path | accepted | pass | 99.9997 | 27.0991 | 0 | 2.14958e+12 | 4.42726e+08 | 3.53405e+08 | 18.5812 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 2e-06 | 99.9232 | 0 | 2.14958e+12 | 2.15181e+12 | 1.97364e+09 | 984.081 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 6e-06 | 99.8978 | 0 | 5.37395e+11 | 5.37997e+11 | 5.40672e+08 | 867.454 |
| l2_cg_load_only | l2_hit_path | accepted | pass | 3e-06 | 99.9368 | 0 | 1.07479e+12 | 1.07618e+12 | 1.26191e+09 | 945.037 |
| reg_mma | tensor_increment_candidate | accepted | pass | 41.2587 | 33.0425 | 0 | 0 | 1.77891e+07 | 1.21038e+07 | 0.02072 |
| reg_mma | tensor_increment_candidate | accepted | pass | 35.5771 | 32.9416 | 0 | 0 | 7.31657e+08 | 5.20539e+08 | 0.006081 |
| reg_mma | tensor_increment_candidate | accepted | pass | 43.787 | 47.9334 | 0 | 0 | 9.86899e+07 | 7.44187e+07 | 0.013766 |
| reg_mma | tensor_increment_candidate | accepted | pass | 34.9586 | 77.5795 | 0 | 0 | 8.02851e+07 | 6.39284e+07 | 0.010039 |
| reg_mma | tensor_increment_candidate | accepted | pass | 42.1429 | 97.3512 | 0 | 0 | 1.5188e+08 | 1.21071e+08 | 0.010504 |
| reg_operand_only | register_control_candidate | accepted | pass | 34.1071 | 19.9438 | 0 | 0 | 2.5177e+07 | 2.02623e+07 | 0.020298 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.9686 | 63.6909 | 0 | 0 | 5.02782e+08 | 3.5592e+08 | 0.003515 |
| reg_operand_only | register_control_candidate | accepted | pass | 29.2835 | 42.4735 | 0 | 0 | 1.36189e+08 | 1.02902e+08 | 0.015632 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.189 | 26.0331 | 0 | 0 | 1.87625e+08 | 1.47636e+08 | 0.009723 |
| reg_operand_only | register_control_candidate | accepted | pass | 31.6986 | 41.1394 | 0 | 0 | 3.22722e+08 | 2.42892e+08 | 0.007216 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.6936 | 67.7472 | 2.14959e+12 | 0 | 1.09455e+09 | 7.91497e+08 | 0.000693 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 21.0747 | 42.0761 | 5.37401e+11 | 0 | 4.05844e+08 | 3.02841e+08 | 0.002106 |
| shared_scalar_load_only | shared_memory_path | accepted | pass | 20.9032 | 12.0389 | 1.0748e+12 | 0 | 3.73815e+08 | 2.73733e+08 | 0.00101 |
