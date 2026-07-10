# RTX 3090 FP16 Energy Full Sweep Summary

## Scope

- GPU profile: RTX 3090, sm_86, 82 active SMs.
- Requested Sweep 1: blocks/SM = 1, 2, 4, 8, 16, 32.
- Executed blocks/SM: 1, 2, 4, 8, 16. blocks/SM=32 is invalid on compute capability 8.6 and is recorded only in the matrix.
- Requested Sweep 2: W_SM = 1 KiB through 128 MiB, doubling each step.
- Runtime: seconds=1, repeats=1, active_SM=82, gpu=0.

## Coverage

- Raw result rows: 346 including idle; non-idle rows: 345.
- Matrix rows: 649; valid/executed rows: 346; skipped/invalid rows: 303.
- Rows by mode: {'idle': 1, 'empty': 80, 'reg_mma': 80, 'shared_mma': 25, 'l2_mma': 25, 'dram_mma': 55, 'store_path': 80}.
- SMID histogram failures among non-idle rows: 0.
- Energy sources: {'nvml_total_energy': 346}.

## Invalid/Skipped Matrix Rows

| Reason | Count |
|---|---:|
| skipped_for_mode_or_invalid:full-GPU working set exceeds nominal L2 | 110 |
| skipped_for_mode_or_invalid:blocks_per_SM exceeds resident block limit 16 | 108 |
| skipped_for_mode_or_invalid:W_SM_KiB < blocks_per_SM | 60 |
| skipped_for_mode_or_invalid:fits shared memory | 25 |

## Best pJ/FLOP Rows

| Mode | W_SM KiB | blocks/SM | pJ/FLOP | net E J | elapsed s |
|---|---:|---:|---:|---:|---:|
| reg_mma | 2048 | 4 | 0.4639 | 38.929 | 1.164 |
| shared_mma | 8 | 1 | 0.4345 | 1.911 | 1.078 |
| l2_mma | 8 | 1 | 2.1778 | 9.731 | 1.153 |
| dram_mma | 128 | 16 | 12.7323 | 228.233 | 1.188 |

## Files

- Raw CSV: `results/raw/rtx3090_full_sweep_20260701.csv`
- Matrix CSV: `results/raw/rtx3090_full_sweep_20260701_matrix.csv`
- Clean result CSV: `results/summary/rtx3090_full_sweep_20260701_clean_results.csv`
- Mode summary CSV: `results/summary/rtx3090_full_sweep_20260701_mode_summary.csv`
- Best rows CSV: `results/summary/rtx3090_full_sweep_20260701_best_pj_flop.csv`
- By-blocks summary CSV: `results/summary/rtx3090_full_sweep_20260701_by_blocks_summary.csv`
- By-W summary CSV: `results/summary/rtx3090_full_sweep_20260701_by_w_summary.csv`
- Plots: `results/plots/rtx3090_full_sweep_20260701/`
