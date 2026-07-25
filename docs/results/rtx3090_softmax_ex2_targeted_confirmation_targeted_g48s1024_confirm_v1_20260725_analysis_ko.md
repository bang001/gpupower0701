# CTA=48, S=1024 targeted Softmax EX2 confirmation

## Result

The three new cyclic-order sessions all passed raw/trace/manifest verification. The primary metric is incremental pJ per input element: one extra exponent result is added per element in treatment. It is not total Softmax pJ per element.

| implementation | fresh-session mean ΔpJ/element | sample SD | diagnostic t95 (n=3) | positive session effects |
|---|---:|---:|---:|---:|
| `fp32` | 82.164 | 3.134 | [74.379, 89.950] | 3/3 |
| `ptx_f16` | 19.393 | 5.223 | [6.417, 32.368] | 3/3 |
| `ptx_f16x2` | 25.055 | 5.484 | [11.433, 38.677] | 3/3 |

The t intervals are descriptive diagnostics with only three independent sessions, not a preregistered decision rule. The scalar FP16 target cell moved from historical 10.994 → 1.632 to a three-session mean of 19.393 ΔpJ/element after implementation-position balancing.

## Interpretation bounds

- All three paths share FP16 I/O and FP32 max/sum/reduction/normalization. They differ in the exponent/probe path, so comparisons are complete implementation-path contrasts, not isolated functional-unit coefficients.
- `ptx_f16x2` emits packed two-result PTX, but frozen sm_86 SASS lowers it to two scalar `MUFU.EX2.F16` instructions. Its pJ/element value must not be interpreted as half of scalar FP16 or as a physical two-lane-MUFU energy.
- Exact CTA=48/S=1024 native NCU sidecar confirms one added scalar EX2 result per element for both native paths; profiler energy is explicitly excluded from the ATC numerator.

## Evidence outputs

- `program`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_program.csv`
- `session_cells`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_session_cells.csv`
- `matched_blocks`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_matched_blocks.csv`
- `implementation_summary`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_implementation_summary.csv`
- `within_session_contrasts`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_within_session_contrasts.csv`
- `contrast_summary`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_contrast_summary.csv`
- `diagnostics`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_diagnostics.csv`
- `numerical_validation`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_numerical_validation.csv`
- `sass_audit`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_sass_audit.csv`
- `ncu_audit`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_ncu_audit.csv`
- `historical_context`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_historical_context.csv`
- `historical_scalar_blocks`: `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_historical_scalar_blocks.csv`
- `analysis_markdown`: `docs/results/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_analysis_ko.md`
