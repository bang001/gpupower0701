# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_l1_paired_30s_stability_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_l1_paired_30s_stability_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `global_l1_hit_path` | `stable_detail_rows` | 6/6 | - | 293.867782002 | 0.0306727241436 | 0.147190221872 | no_followup_required_by_detail_rows |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
