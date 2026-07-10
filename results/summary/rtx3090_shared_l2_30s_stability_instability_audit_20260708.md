# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_shared_l2_30s_stability_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_shared_l2_30s_stability_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `l2_hit_cg_path` | `needs_stability_followup` | 9/10 | negative_coefficient:1 | 780.994565114 | 0.0796428574376 | 1.29763921217 | targeted_control_drift_rerun;increase_repeats_10_or_more;inspect_nearest_control_distance_temperature_clock;do_not_report_negative_rows |
| `shared_l1_scalar_path` | `needs_stability_followup` | 9/10 | delta_fraction<0.005:1 | 325.580745142 | 0.0349437822397 | 0.216218484187 | weak_signal_rerun;increase_seconds_20_to_30;prefer_high_signal_factor_rows;keep_min_delta_and_fraction_gate |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `l2_hit_cg_path` | W=64KiB,B/SM=16,RF=1,LR=4,delta_E=-50.01J,frac=-0.005396 |
| `shared_l1_scalar_path` | W=64KiB,B/SM=16,RF=1,LR=4,delta_E=10.57J,frac=0.001194 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
