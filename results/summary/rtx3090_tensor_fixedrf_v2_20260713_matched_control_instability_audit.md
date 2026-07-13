# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_tensor_fixedrf_v2_20260713_matched_control_detail.csv`
- audit CSV: `results/summary/rtx3090_tensor_fixedrf_v2_20260713_matched_control_instability_audit.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `tensor_mma_increment` | `needs_stability_followup` | 33/35 | pair_start_distance_ms>60000:2 | 3419.70959904 | 0.840695768018 | 2.25250148277 | inspect_invalid_rows_before_final_claim |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `tensor_mma_increment` | W=2048KiB,B/SM=16,RF=4,LR=1,delta_E=3462J,frac=0.8383 | W=2048KiB,B/SM=16,RF=16,LR=1,delta_E=3381J,frac=0.8654 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
