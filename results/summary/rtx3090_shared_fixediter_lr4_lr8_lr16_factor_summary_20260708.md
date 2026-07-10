# Matched-Control Factor Summary

- detail CSV: `results/summary/rtx3090_shared_fixediter_lr4_lr8_lr16_matched_control_detail_20260708.csv`
- factor: `load_repeat`

| component | factor value | valid/total | median | unit | median pJ/bit | delta_E median (J) | signal fraction median | invalid diagnostics |
|---|---:|---:|---:|---|---:|---:|---:|---|
| shared_l1_scalar_path | 4 | 3/3 | 1.23069458884 | pJ/byte | 0.153836823605 | 112.434005465 | 0.0249906606662 |  |
| shared_l1_scalar_path | 8 | 3/3 | 1.54739655125 | pJ/byte | 0.193424568906 | 282.734108258 | 0.032118934574 |  |
| shared_l1_scalar_path | 16 | 2/3 | 0.948754765026 | pJ/byte | 0.118594345628 | 346.70373841 | 0.0199571891243 | delta_fraction<0.005 |

## Interpretation

- This table does not recompute energy. It summarizes valid matched-control detail rows by factor.
- `median_pJ_per_bit` is meaningful only for memory-path rows where the matched-control analyzer emitted that column.
- Invalid diagnostics are retained because weak-signal rows are evidence about measurement stability, not values to hide.
