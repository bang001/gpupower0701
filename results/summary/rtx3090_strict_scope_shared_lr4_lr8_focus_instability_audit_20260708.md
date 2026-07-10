# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_strict_scope_shared_lr4_lr8_focus_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_strict_scope_shared_lr4_lr8_focus_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `shared_l1_scalar_path` | `needs_stability_followup` | 3/6 | elapsed_ratio>1.35:3 | 174.61331635 | 0.0201896286575 | 0.119456777424 | inspect_invalid_rows_before_final_claim |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `shared_l1_scalar_path` | W=64KiB,B/SM=16,RF=1,LR=4,delta_E=125.4J,frac=0.02803 | W=64KiB,B/SM=16,RF=1,LR=4,delta_E=90.43J,frac=0.02039 | W=64KiB,B/SM=16,RF=1,LR=4,delta_E=90.57J,frac=0.0204 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
