# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_detail_20260708.csv`
- audit CSV: `results/summary/rtx3090_finalplan_stability_matched_control_instability_audit_20260708.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `dram_cg_stream_path` | `stable_detail_rows` | 9/9 | - | 209.659293028 | 0.0997722064622 | 3.54069776975 | no_followup_required_by_detail_rows |
| `global_l1_hit_path` | `needs_stability_followup` | 7/9 | delta_E<10J:1;delta_fraction<0.005:1;negative_coefficient:1 | 78.2646016398 | 0.0408751286748 | 0.150450885901 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |
| `l2_hit_cg_path` | `stable_detail_rows` | 9/9 | - | 186.111215907 | 0.0917771420496 | 1.1381074518 | no_followup_required_by_detail_rows |
| `shared_l1_scalar_path` | `needs_stability_followup` | 6/9 | delta_E<10J:1;delta_fraction<0.005:1;negative_coefficient:2 | 62.9550294596 | 0.0328812976807 | 0.151125742676 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |
| `tensor_mma_increment` | `stable_detail_rows` | 15/15 | - | 110.448654153 | 0.113099274341 | 0.169744684821 | no_followup_required_by_detail_rows |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `global_l1_hit_path` | W=16KiB,B/SM=16,RF=1,LR=4,delta_E=2.859J,frac=0.001546 | W=16KiB,B/SM=16,RF=1,LR=16,delta_E=-42.33J,frac=-0.02186 |
| `shared_l1_scalar_path` | W=64KiB,B/SM=16,RF=1,LR=8,delta_E=-14.97J,frac=-0.007943 | W=64KiB,B/SM=16,RF=1,LR=16,delta_E=-18.37J,frac=-0.009438 | W=64KiB,B/SM=16,RF=1,LR=16,delta_E=2.268J,frac=0.001165 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
