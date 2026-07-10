# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_l1_duration_scaling_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_l1_duration_scaling_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `global_l1_hit_path` | `needs_stability_followup` | 14/15 | negative_coefficient:1 | 196.120943856 | 0.0333440019369 | 0.156109137015 | targeted_control_drift_rerun;increase_repeats_10_or_more;inspect_nearest_control_distance_temperature_clock;do_not_report_negative_rows |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `global_l1_hit_path` | W=16KiB,B/SM=16,RF=1,LR=4,delta_E=-81.08J,frac=-0.008742 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
