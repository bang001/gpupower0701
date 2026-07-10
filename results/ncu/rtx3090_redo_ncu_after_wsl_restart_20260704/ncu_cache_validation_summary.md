# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| addr_only_W64_B16 | addr_only | 64 | 16 |  | 17.4543 | 32.0249 |  | 0.955093 |  |  |  | 30.563 | 843.269 | partial |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 |  | 19.8742 | 52.1298 |  | 0.704655 |  |  |  | 22.549 | 464.108 | partial |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 |  | 49.9996 | 0.16783 |  | 132.79 |  |  |  | 4249.27 | 1084.66 | partial |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 |  | 49.9999 | 0.157987 |  | 132.817 |  |  |  | 4250.16 | 1085.45 | partial |
| empty_W64_B16 | empty | 64 | 16 |  | 19.8361 | 96.8307 |  | 0.436847 |  |  |  | 13.9791 | 857.234 | partial |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 |  | 99.9985 | 33.6283 |  | 0.781899 |  |  |  | 25.0208 | 556.91 | partial |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 |  | 87.5134 | 99.8182 |  | 108.614 |  |  |  | 3475.65 | 467.524 | partial |
| l2_mma_W64_B16 | l2_mma | 64 | 16 |  | 85.9798 | 99.8054 |  | 123.862 |  |  |  | 3963.59 | 552.03 | partial |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 |  | 27.9094 | 6.5327 |  | 1.07506 |  |  |  | 34.4018 | 786.362 | partial |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 |  | 46.6986 | 8.89777 |  | 0.827115 |  |  |  | 26.4677 | 560.155 | partial |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 |  | 31.0627 | 15.5251 |  | 0.597744 |  |  |  | 19.1278 | 276.268 | partial |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 |  | 26.9142 | 59.702 |  | 0.923208 |  |  |  | 29.5427 | 720.81 | partial |
| shared_mma_W64_B16 | shared_mma | 64 | 16 |  | 42.2452 | 62.0946 |  | 0.708879 |  |  |  | 22.6841 | 444.203 | partial |
| store_only_W64_B16 | store_only | 64 | 16 |  | 99.9817 | 99.5578 |  | 45.2345 |  |  |  | 1447.5 | 715.823 | partial |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable.
