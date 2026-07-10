# Component Pair Summary

| profile | GPU | W_SM (KiB) | blocks/SM | active_SM (SMs) | ITER | factors | pair | delta_E_J (J) | denominator | coefficient |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| rtx3090 | 0 | 64 | 16 | 82 | 3411304 | reuse=4, load=4, store=4 | l2_load_minus_empty | 1168.43 | 1.83322e+13 | 63.7364 pJ/byte |
| rtx3090 | 0 | 64 | 16 | 82 | 3411304 | reuse=4, load=4, store=4 | l2_mma_minus_l2_load | -501.919 | 1.46657e+14 | -3.42239 pJ/FLOP |
| rtx3090 | 0 | 64 | 16 | 82 | 3981322 | reuse=4, load=4, store=4 | shared_load_minus_empty | 1171.46 | 2.13954e+13 | 54.7528 pJ/byte |
| rtx3090 | 0 | 64 | 16 | 82 | 3981322 | reuse=4, load=4, store=4 | shared_mma_minus_shared_load | -651.902 | 1.71163e+14 | -3.80865 pJ/FLOP |
| rtx3090 | 0 | 64 | 16 | 82 | 5012200 | reuse=4, load=4, store=4 | reg_fragment_minus_empty | 115.157 | 0 | 115.157 J |
| rtx3090 | 0 | 64 | 16 | 82 | 5012200 | reuse=4, load=4, store=4 | reg_mma_minus_empty | 302.003 | 2.15483e+14 | 1.40152 pJ/FLOP |
| rtx3090 | 0 | 64 | 16 | 82 | 5012200 | reuse=4, load=4, store=4 | reg_mma_minus_reg_operand | 72.6064 | 2.15483e+14 | 0.336948 pJ/FLOP |
| rtx3090 | 0 | 64 | 16 | 82 | 5012200 | reuse=4, load=4, store=4 | reg_operand_minus_empty | 229.396 | 2.6304e+10 | 8720.97 pJ/reg-op |
| rtx3090 | 0 | 64 | 16 | 82 | 5576378 | reuse=4, load=4, store=4 | store_only_minus_empty | 447.39 | 1.17059e+11 | 3821.9 pJ/byte |
| rtx3090 | 0 | 64 | 16 | 82 | 5576378 | reuse=4, load=4, store=4 | store_path_minus_store_only | -51.6358 | 1.17059e+11 | -441.108 pJ/byte |
| rtx3090 | 0 | 8192 | 16 | 82 | 1438005 | reuse=4, load=4, store=4 | dram_load_minus_empty | 2322.55 | 7.72777e+12 | 300.546 pJ/byte |
| rtx3090 | 0 | 8192 | 16 | 82 | 1438005 | reuse=4, load=4, store=4 | dram_mma_minus_dram_load | -1570.63 | 6.18222e+13 | -25.4056 pJ/FLOP |
| rtx3090 | 0 | 8192 | 16 | 82 | 5151818 | reuse=4, load=4, store=4 | reg_fragment_minus_empty | 134.532 | 0 | 134.532 J |
| rtx3090 | 0 | 8192 | 16 | 82 | 5151818 | reuse=4, load=4, store=4 | reg_mma_minus_empty | 295.18 | 2.21485e+14 | 1.33273 pJ/FLOP |
| rtx3090 | 0 | 8192 | 16 | 82 | 5151818 | reuse=4, load=4, store=4 | reg_mma_minus_reg_operand | 61.9607 | 2.21485e+14 | 0.279751 pJ/FLOP |
| rtx3090 | 0 | 8192 | 16 | 82 | 5151818 | reuse=4, load=4, store=4 | reg_operand_minus_empty | 233.22 | 2.70367e+10 | 8626.03 pJ/reg-op |
| rtx3090 | 0 | 8192 | 16 | 82 | 5481384 | reuse=4, load=4, store=4 | store_only_minus_empty | 453.348 | 1.15065e+11 | 3939.93 pJ/byte |
| rtx3090 | 0 | 8192 | 16 | 82 | 5481384 | reuse=4, load=4, store=4 | store_path_minus_store_only | -49.6415 | 1.15065e+11 | -431.421 pJ/byte |
