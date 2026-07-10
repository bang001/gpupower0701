# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_targeted_shared_l1_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_targeted_shared_l1_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `global_l1_hit_path` | `needs_stability_followup` | 26/30 | delta_E<10J:1;delta_fraction<0.005:2;negative_coefficient:4 | 139.234818505 | 0.0230982689244 | 0.104689502947 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |
| `shared_l1_scalar_path` | `needs_stability_followup` | 29/30 | delta_fraction<0.005:1;negative_coefficient:1 | 170.019440846 | 0.0270265269725 | 0.152395459548 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `global_l1_hit_path` | W=16KiB,B/SM=16,RF=1,LR=16,delta_E=-6.857J,frac=-0.001108 | W=16KiB,B/SM=16,RF=1,LR=16,delta_E=-536.1J,frac=-0.07869 | W=16KiB,B/SM=16,RF=1,LR=16,delta_E=-441.8J,frac=-0.06563 | W=16KiB,B/SM=16,RF=1,LR=16,delta_E=-15.67J,frac=-0.002629 |
| `shared_l1_scalar_path` | W=64KiB,B/SM=16,RF=1,LR=16,delta_E=-28.01J,frac=-0.004682 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
