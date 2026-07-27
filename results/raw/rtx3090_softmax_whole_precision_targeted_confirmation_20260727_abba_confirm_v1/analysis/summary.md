# RTX 3090 Whole-Softmax targeted AB/BA confirmation summary

All manifest, frozen-provenance, raw-schema, conditioning, trace, SMID, numerical, denominator, and SASS gates passed.

- Manifest: `results/raw/rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1/manifest.json`
- Primary unit: net pJ / logical Softmax output element
- Scope: two exploratory-selected implementation-path contrasts at fixed RTX 3090 sm86, S=512, grid CTA=16.
- Independent unit: a fresh CUDA-process pair session (n=6 per candidate), not an individual role.
- The exploratory stage-isolation result and this confirmation are not pooled.

## Candidate summaries

Positive Δ means the treatment used more observed net pJ/output than the same-session FP16-I/O + FP32-stage baseline.

| candidate | treatment | n | AB / BA | mean Δ | SD | descriptive t95 | negative / positive |
|---|---|---:|---:|---:|---:|---:|---:|
| exp_packed | exp_fp16x2 | 6 | 3 / 3 | -69.766 | 288.369 | [-372.390, 232.859] | 4 / 2 |
| reduction_scalar | reduction_fp16_scalar | 6 | 3 / 3 | 1,127.525 | 1,036.806 | [39.464, 2,215.587] | 1 / 5 |

## Interpretation boundary

This is a fresh targeted replication of two contrasts selected from an earlier exploratory run. It is not a broad all-stage confirmation, a pure SFU/MUFU or ALU energy measurement, an additive stage decomposition, or an EX2 operand-rate ATC result. Packed reduction still means half2 lanes across two independent CTA rows; normalization is outside this confirmation.

The t95 intervals are descriptive n=6 paired summaries. Candidate selection was informed by the prior exploratory evidence, so the report does not claim population-wide or cross-platform superiority. AB/BA balances pair position and direct predecessor direction, but does not turn temperature or board state into a causal adjustment.

## Quality gates

| check | coverage | result |
|---|---|---|
| evidence binding | 12 fresh processes / 24 measured roles | pass |
| AB/BA and conditioning | exp packed: AB=3 BA=3; reduction scalar: AB=3 BA=3 | pass |
| trace, placement and numerics | preheat 19.878-19.976 s; R² 0.999714829-0.999955990; 24/24 roles | pass |
| recorded thermal context | 52-57 °C | recorded |
| sm86 compiled path | ad33175b2388 (results/raw/rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1/sass_audit.json) | pass |
