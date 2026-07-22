# Combined NCU Validation Summary

This canonical table combines disjoint NCU runs. L2 and external-memory gating rows use the coherent `l2_path_minimal` profile; Tensor, Shared, and Global-L1 rows use the full diagnostic profile. NCU runs are validation evidence, not energy rows.

## Inputs

- `results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv`
- `results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv`
- `results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv`
- binary: `./build/a100_fp16_energy_v2`
- binary SHA-256: `500bcb73a3dffebc92f041072ccba3ff5f4f85a836e045ba6eff9715cdb99862`
- hash capture: `pre_post_collection_verified`
- NCU quiescence: `skipped`

| label | mode | W_SM (KiB/SM) | blocks/SM | LR | metric profile | status | L1 path hit (%) | L2 direct/native/logical hit (%) | fabric fraction | conservation | long scoreboard status | source |
|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| clocked_empty_W64_B4 | clocked_empty | 64 | 4 | 1 | full | ok |  | /20.7071/ |  |  | 0.00215 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_mma_W1_B4_RF1 | reg_mma | 1 | 4 | 1 | full | ok |  | /21.2246/ |  | 0 | 0.053965 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_mma_W1_B4_RF16 | reg_mma | 1 | 4 | 1 | full | ok |  | /20.8516/ |  |  | 0.000877 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_mma_W1_B4_RF4 | reg_mma | 1 | 4 | 1 | full | ok |  | /28.4798/ |  |  | 0.003405 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B4_RF1 | reg_operand_only | 1 | 4 | 1 | full | ok |  | /95.0257/ |  |  | 0.074362 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B4_RF16 | reg_operand_only | 1 | 4 | 1 | full | ok |  | /19.7433/ |  |  | 0.002861 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B4_RF4 | reg_operand_only | 1 | 4 | 1 | full | ok |  | /14.8257/ |  |  | 0.009351 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B4/ncu_cache_validation_summary.csv |
| clocked_empty_W64_B8 | clocked_empty | 64 | 8 | 1 | full | ok |  | /20.0474/ |  |  | 0.002726 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_mma_W1_B8_RF1 | reg_mma | 1 | 8 | 1 | full | ok |  | /12.4076/ |  |  | 0.026176 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_mma_W1_B8_RF16 | reg_mma | 1 | 8 | 1 | full | ok |  | /19.5496/ |  |  | 0.001157 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_mma_W1_B8_RF4 | reg_mma | 1 | 8 | 1 | full | ok |  | /25.282/ |  |  | 0.00454 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B8_RF1 | reg_operand_only | 1 | 8 | 1 | full | ok |  | /115.487/ |  |  | 0.103442 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B8_RF16 | reg_operand_only | 1 | 8 | 1 | full | ok |  | /19.7186/ |  |  | 0.00353 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B8_RF4 | reg_operand_only | 1 | 8 | 1 | full | ok |  | /17.5287/ |  |  | 0.012863 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B8/ncu_cache_validation_summary.csv |
| clocked_empty_W64_B16 | clocked_empty | 64 | 16 | 1 | full | ok |  | /22.4712/ |  |  | 0.003208 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_mma_W1_B16_RF1 | reg_mma | 1 | 16 | 1 | full | ok |  | /16.7146/ |  |  | 0.027634 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_mma_W1_B16_RF16 | reg_mma | 1 | 16 | 1 | full | ok |  | /21.0999/ |  |  | 0.001275 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_mma_W1_B16_RF4 | reg_mma | 1 | 16 | 1 | full | ok |  | /21.4936/ |  |  | 0.007164 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B16_RF1 | reg_operand_only | 1 | 16 | 1 | full | ok |  | /103.113/ |  |  | 0.111272 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B16_RF16 | reg_operand_only | 1 | 16 | 1 | full | ok |  | 19.1785/27.1674/ |  |  | 0.011123 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
| reg_operand_only_W1_B16_RF4 | reg_operand_only | 1 | 16 | 1 | full | ok |  | /20.2173/ |  |  | 0.014262 | results/ncu/rtx3090_tensor_fp16_v3_diagnostic_20260722_ncu_unverified/full_non_l2/B16/ncu_cache_validation_summary.csv |
