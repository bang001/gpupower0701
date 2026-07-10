# Matched-Control Factor Summary

- detail CSV: `results/summary/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_matched_control_detail_20260708.csv`
- factor: `load_repeat`

| component | factor value | valid/total | median | unit | median pJ/bit | delta_E median (J) | signal fraction median | invalid diagnostics |
|---|---:|---:|---:|---|---:|---:|---:|---|
| shared_l1_scalar_path | 4 | 4/4 | 1.59276188001 | pJ/byte | 0.199095235002 | 293.094116966 | 0.0322672534748 |  |
| shared_l1_scalar_path | 8 | 4/4 | 1.16048530239 | pJ/byte | 0.145060662799 | 215.699968446 | 0.0241763420666 |  |
| shared_l1_scalar_path | 16 | 4/4 | 0.49414544396 | pJ/byte | 0.061768180495 | 94.6968495265 | 0.010506833962 |  |

## Interpretation

- This table does not recompute energy. It summarizes valid matched-control detail rows by factor.
- `median_pJ_per_bit` is meaningful only for memory-path rows where the matched-control analyzer emitted that column.
- Invalid diagnostics are retained because weak-signal rows are evidence about measurement stability, not values to hide.
