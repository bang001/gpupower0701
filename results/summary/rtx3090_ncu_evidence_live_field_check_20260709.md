# RTX 3090 Live NCU Evidence Field Check

Source: `results/summary/rtx3090_ncu_evidence_check_acceptance_20260709.csv`

| mode | acceptance | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses | DRAM accesses | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB (%) | status | reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `dram_cg_load_only` | accepted | 7e-06 | 0.038381 | 1.67936e+10 sectors | 1.67998e+10 sectors | 1.6818e+10 sectors | 0 | 5.37395e+11 | 5.38663e+11 | 5.3847e+11 | 1784.08 | pass | all_required_evidence_present |
| `global_l1_load_only` | accepted | 99.9998 | 57.2715 | 3.35872e+10 sectors | 41984 sectors | 4.3892e+06 sectors | 0 | 1.07479e+12 | 1.79393e+08 | 1.40454e+08 | 17.4343 | pass | all_required_evidence_present |
| `l2_cg_load_only` | accepted | 7e-06 | 99.9066 | 1.67936e+10 sectors | 1.67994e+10 sectors | 1.40017e+07 sectors | 0 | 5.37395e+11 | 5.38188e+11 | 7.19515e+08 | 864.97 | pass | all_required_evidence_present |
| `reg_mma` | accepted | 36.2957 | 32.3856 | 0 sectors | 431231 sectors | 2.1648e+06 sectors | 0 | 0 | 1.20292e+08 | 9.38189e+07 | 0.010564 | pass | all_required_evidence_present |
| `reg_operand_only` | accepted | 31.7291 | 63.2529 | 0 sectors | 427908 sectors | 2.11342e+06 sectors | 0 | 0 | 1.2116e+08 | 9.01961e+07 | 0.009671 | pass | all_required_evidence_present |
| `shared_scalar_load_only` | accepted | 20.8079 | 15.0719 | 0 sectors | 724793 sectors | 3.04068e+06 sectors | 5.37401e+11 | 0 | 1.55649e+08 | 1.19054e+08 | 0.001967 | pass | all_required_evidence_present |

Result: 6/6 representative rows passed.
