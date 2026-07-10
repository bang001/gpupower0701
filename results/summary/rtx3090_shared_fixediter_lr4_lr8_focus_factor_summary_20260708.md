# Matched-Control Factor Summary

- detail CSV: `results/summary/rtx3090_shared_fixediter_lr4_lr8_focus_matched_control_detail_20260708.csv`
- factor: `load_repeat`

| component | factor value | valid/total | median | unit | median pJ/bit | delta_E median (J) | signal fraction median | invalid diagnostics |
|---|---:|---:|---:|---|---:|---:|---:|---|
| shared_l1_scalar_path | 4 | 5/5 | 1.4326868276 | pJ/byte | 0.17908585345 | 130.887646753 | 0.029005994605 |  |
| shared_l1_scalar_path | 8 | 5/5 | 1.13898933389 | pJ/byte | 0.142373666736 | 208.11157513 | 0.0237391620951 |  |

## Interpretation

- This table does not recompute energy. It summarizes valid matched-control detail rows by factor.
- `median_pJ_per_bit` is meaningful only for memory-path rows where the matched-control analyzer emitted that column.
- Invalid diagnostics are retained because weak-signal rows are evidence about measurement stability, not values to hide.
