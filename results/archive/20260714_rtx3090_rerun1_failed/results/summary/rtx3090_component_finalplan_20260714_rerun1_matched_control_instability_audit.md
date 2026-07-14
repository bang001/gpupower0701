# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_component_finalplan_20260714_rerun1_matched_control_detail.csv`
- audit CSV: `results/summary/rtx3090_component_finalplan_20260714_rerun1_matched_control_instability_audit.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `dram_cg_stream_path` | `stable_detail_rows` | 15/15 | - | 1802.45226441 | 0.653228557629 | 25.5169429738 | no_followup_required_by_detail_rows |
| `global_l1_hit_path` | `needs_stability_followup` | 4/15 | delta_fraction<0.005:1;negative_coefficient:10 | 34.9766613297 | 0.0139025864047 | 0.11280472766 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |
| `l2_hit_cg_path` | `stable_detail_rows` | 15/15 | - | 1219.05009766 | 0.516068043982 | 7.74945787957 | no_followup_required_by_detail_rows |
| `shared_l1_scalar_path` | `needs_stability_followup` | 9/15 | delta_E<10J:1;delta_fraction<0.005:1;negative_coefficient:5 | 343.22198665 | 0.14034302027 | 1.01047072961 | targeted_stability_rerun;use_longer_seconds_20_to_30;increase_repeats_10_or_more;keep_power_api_audit;inspect_control_drift_and_temperature_clock;do_not_relax_delta_gate |
| `tensor_mma_increment` | `stable_detail_rows` | 25/25 | - | 1095.79492426 | 0.805928548121 | 1.64095668284 | no_followup_required_by_detail_rows |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|
| `global_l1_hit_path` | W=8KiB,B/SM=8,RF=1,LR=4,delta_E=-129.5J,frac=-0.05028 | W=8KiB,B/SM=8,RF=1,LR=4,delta_E=-18.11J,frac=-0.007072 | W=8KiB,B/SM=8,RF=1,LR=4,delta_E=-73.18J,frac=-0.02862 | W=8KiB,B/SM=8,RF=1,LR=4,delta_E=-51.6J,frac=-0.01982 | W=8KiB,B/SM=8,RF=1,LR=8,delta_E=-56.43J,frac=-0.02221 | W=8KiB,B/SM=8,RF=1,LR=8,delta_E=-15.63J,frac=-0.006035 | W=8KiB,B/SM=8,RF=1,LR=8,delta_E=10.37J,frac=0.004013 | W=8KiB,B/SM=8,RF=1,LR=8,delta_E=-30.21J,frac=-0.01174 | W=8KiB,B/SM=8,RF=1,LR=8,delta_E=-24.91J,frac=-0.009646 | W=8KiB,B/SM=8,RF=1,LR=16,delta_E=-63.22J,frac=-0.02397 | W=8KiB,B/SM=8,RF=1,LR=16,delta_E=-13.2J,frac=-0.005195 |
| `shared_l1_scalar_path` | W=64KiB,B/SM=8,RF=1,LR=8,delta_E=5.721J,frac=0.002325 | W=64KiB,B/SM=8,RF=1,LR=16,delta_E=-75.97J,frac=-0.03042 | W=64KiB,B/SM=8,RF=1,LR=16,delta_E=-118.9J,frac=-0.0464 | W=64KiB,B/SM=8,RF=1,LR=16,delta_E=-123.9J,frac=-0.04871 | W=64KiB,B/SM=8,RF=1,LR=16,delta_E=-59.84J,frac=-0.02389 | W=64KiB,B/SM=8,RF=1,LR=16,delta_E=-165.7J,frac=-0.0654 |

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
