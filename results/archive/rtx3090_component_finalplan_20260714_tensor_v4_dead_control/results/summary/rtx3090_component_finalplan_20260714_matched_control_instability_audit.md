# Matched-Control Instability Audit

This report explains weak-signal or negative matched-control rows. It does not change coefficients; it identifies why some rows were excluded from the component summary and what follow-up experiment is needed.

- matched-control detail: `results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv`
- audit CSV: `results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.csv`

## Component Summary

| component | status | valid/total | invalid reasons | valid delta_E median (J) | valid signal fraction median | valid coefficient median | recommendation |
|---|---|---:|---|---:|---:|---:|---|
| `external_memory_read_path` | `stable_detail_rows` | 45/45 | - | 1763.54041965 | 0.65112221093 | 24.9485633919 | no_followup_required_by_detail_rows |
| `global_l1_hit_path` | `stable_detail_rows` | 15/15 | - | 262.74446758 | 0.104388175915 | 0.85247325547 | no_followup_required_by_detail_rows |
| `l2_hit_cg_path` | `stable_detail_rows` | 30/30 | - | 1446.90610456 | 0.560820846213 | 9.0784023317 | no_followup_required_by_detail_rows |
| `shared_l1_scalar_path` | `stable_detail_rows` | 15/15 | - | 244.96242344 | 0.101145657536 | 0.713811591343 | no_followup_required_by_detail_rows |

## Invalid Coordinates

| component | invalid coordinates |
|---|---|

## Interpretation

- `delta_E<...` and `delta_fraction<...` mean the treatment-control energy difference is inside the configured noise floor.
- `negative_coefficient` means the scaled control energy exceeded the treatment energy. With NCU path accepted, this usually points to weak board-level signal or control/thermal drift, not a negative physical component energy.
- For rows marked `needs_stability_followup`, do not relax the delta gate to make the row pass. Rerun with longer duration, more repeats, and explicit power API audit.
