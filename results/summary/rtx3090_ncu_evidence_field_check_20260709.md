# RTX 3090 NCU Evidence Field Check

Source: `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv`

This check verifies that the selected NCU validation fields are present and path-relevant for representative RF/LR=4 rows.

| mode | coord | acceptance | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses | DRAM accesses | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB (%) | status | reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `dram_cg_load_only` | LR=4 | accepted | 6e-06 | 0.104067 | 1.67936e+10 sectors | 1.68016e+10 sectors | 1.68197e+10 sectors | 0 | 5.37395e+11 | 5.38836e+11 | 5.38608e+11 | 1747.88 | pass | all_required_evidence_present |
| `global_l1_load_only` | LR=4 | accepted | 99.9982 | 66.9942 | 3.35872e+10 sectors | 5.66108e+06 sectors | 7.19713e+06 sectors | 0 | 1.07479e+12 | 5.92794e+08 | 4.52661e+08 | 17.4469 | pass | all_required_evidence_present |
| `l2_cg_load_only` | LR=4 | accepted | 6e-06 | 99.8978 | 1.67936e+10 sectors | 1.6797e+10 sectors | 1.19183e+07 sectors | 0 | 5.37395e+11 | 5.37997e+11 | 5.40672e+08 | 867.454 | pass | all_required_evidence_present |
| `reg_mma` | RF=4 | accepted | 34.9586 | 77.5795 | 0 sectors | 0 sectors | 1.99776e+06 sectors | 0 | 0 | 8.02851e+07 | 6.39284e+07 | 0.010039 | pass | all_required_evidence_present |
| `reg_operand_only` | RF=4 | accepted | 31.189 | 26.0331 | 0 sectors | 903367 sectors | 3.19101e+06 sectors | 0 | 0 | 1.87625e+08 | 1.47636e+08 | 0.009723 | pass | all_required_evidence_present |
| `shared_scalar_load_only` | LR=4 | accepted | 21.0747 | 42.0761 | 0 sectors | 4.14979e+06 sectors | 5.72894e+06 sectors | 5.37401e+11 | 0 | 4.05844e+08 | 3.02841e+08 | 0.002106 | pass | all_required_evidence_present |

Result: 6/6 representative rows passed the evidence-field check.
