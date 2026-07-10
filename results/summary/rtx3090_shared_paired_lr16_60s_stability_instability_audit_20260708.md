# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_shared_paired_lr16_60s_stability_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_shared_paired_lr16_60s_stability_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `shared_l1_scalar_path` | `needs_stability_followup` | 5/6 | delta_fraction<0.005:1 | 232.855450946 | 0.0125259051152 | 0.0768186893369 | weak_signal_rerun;increase_seconds_20_to_30;prefer_high_signal_factor_rows;keep_min_delta_and_fraction_gate |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `shared_l1_scalar_path` | W=64KiB,B/SM=16,RF=1,LR=16,delta_E=81.15J,frac=0.004394 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
