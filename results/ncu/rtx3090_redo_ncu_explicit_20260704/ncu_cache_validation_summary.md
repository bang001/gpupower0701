# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | status | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| addr_only_W64_B16 | addr_only | 64 | 16 | 0 | 21.2676 | 27.7889 | 0 sectors | 1.48852e+06 | 3.33152e+06 |  | 0 | 2.17144e+08 | 1.7392e+08 | 0 | 0.009611 | 61.2801 | 338.308 | 56.3977 | ok |  |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 0 | 21.0919 | 57.8576 | 0 sectors | 1.84008e+06 | 6.32695e+06 |  | 0 | 4.16603e+08 | 3.13941e+08 | 0 | 0.0012775 | 0.0002945 | 378.948 | 33.9712 | ok |  |
| dram_load_only_W8192_B16 | dram_load_only | 8192 | 16 | 0 | 49.9998 | 0.169496 | 1.67936e+10 sectors | 8.4042e+09 | 8.41215e+09 |  | 5.37398e+11 | 2.69659e+11 | 2.695e+11 | 0 | 1174.98 | 57.1292 | 186.402 | 21.5622 | ok |  |
| dram_mma_W8192_B16 | dram_mma | 8192 | 16 | 0 | 49.9999 | 0.161473 | 1.67936e+10 sectors | 8.40308e+09 | 8.41107e+09 |  | 5.37398e+11 | 2.69598e+11 | 2.6944e+11 | 5.248e+08 | 1313.79 | 67.3922 | 314.979 | 13.4099 | ok |  |
| empty_W64_B16 | empty | 64 | 16 | 0 | 20.6187 | 100.162 | 0 sectors | 0 | 304 |  | 0 | 1.28564e+06 | 9724 | 0 | 0.118333 | 0.0300425 | 366.648 | 99.7515 | ok | l2_hit_rate_pct_out_of_range |
| global_l1_load_only_W16_B16 | global_l1_load_only | 16 | 16 | 0 | 99.999 | 44.7889 | 1.67936e+10 sectors | 2.07975e+06 | 4.27343e+06 |  | 5.37398e+11 | 2.758e+08 | 2.16502e+08 | 0 | 10.6795 | 39.7503 | 201.83 | 98.3183 | ok |  |
| l2_load_only_W64_B16 | l2_load_only | 64 | 16 | 0 | 87.4992 | 99.7379 | 1.67936e+10 sectors | 2.10064e+09 | 4.71401e+06 |  | 5.37398e+11 | 6.74151e+10 | 2.1354e+08 | 0 | 62.2498 | 43.1595 | 240.718 | 76.3906 | ok |  |
| l2_mma_W64_B16 | l2_mma | 64 | 16 | 0 | 85.9815 | 99.8017 | 1.67936e+10 sectors | 2.35527e+09 | 4.5763e+06 |  | 5.37398e+11 | 7.55589e+10 | 2.19461e+08 | 5.248e+08 | 40.9602 | 54.2517 | 439.01 | 29.5121 | ok |  |
| reg_fragment_only_W2048_B4 | reg_fragment_only | 2048 | 4 | 0 | 29.4275 | 425.992 | 0 sectors | 0 | 13824 |  | 0 | 3.32333e+06 | 673538 | 0 | 0.007981 | 45.0079 | 23.3386 | 0 | ok | l2_hit_rate_pct_out_of_range |
| reg_mma_W2048_B4 | reg_mma | 2048 | 4 | 0 | 47.0579 | 7.93966 | 0 sectors | 131500 | 1.04142e+06 |  | 0 | 4.96595e+07 | 3.62034e+07 | 1.312e+08 | 0.0116775 | 0.008172 | 285.709 | 0 | ok |  |
| reg_operand_only_W2048_B4 | reg_operand_only | 2048 | 4 | 0 | 31.322 | 18.4693 | 0 sectors | 0 | 648720 |  | 0 | 2.55e+07 | 2.0924e+07 | 0 | 0.029458 | 181.818 | 327.262 | 0 | ok |  |
| shared_load_only_W64_B16 | shared_load_only | 64 | 16 | 4.35941e+09 | 26.9297 | 36.4107 | 0 sectors | 3.18222e+06 | 4.61104e+06 |  | 0 | 3.14902e+08 | 2.43818e+08 | 0 | 0.000942 | 88.8009 | 180.42 | 102.56 | ok |  |
| shared_mma_W64_B16 | shared_mma | 64 | 16 | 4.36165e+09 | 42.9201 | 53.7517 | 0 sectors | 3.29336e+06 | 4.55428e+06 |  | 0 | 3.14724e+08 | 2.50777e+08 | 5.248e+08 | 0.001192 | 68.7903 | 336.059 | 49.4806 | ok |  |
| store_only_W64_B16 | store_only | 64 | 16 | 0 | 99.9809 | 99.0186 | 0 sectors | 726666 | 1.1337e+06 |  | 0 | 8.48453e+09 | 7.3684e+07 | 0 | 0.021014 | 574.362 | 275.999 | 8.00096 | ok |  |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
