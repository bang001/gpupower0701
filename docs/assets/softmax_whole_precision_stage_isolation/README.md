# RTX 3090 whole-Softmax precision stage-isolation figures

These Matplotlib figures accompany the 2026-07-27 complete-Softmax stage
experiment. Their primary unit is **net pJ per logical Softmax output
element**. They are not the older Softmax EX2 Operand-rate ATC
`pJ/added logical exponent result` figures.

| Figure | Purpose |
|---|---|
| `*_absolute_session_spread.{png,svg}` | Three fresh sessions per stage-policy plus mean and descriptive t95 interval |
| `*_paired_contrasts.{png,svg}` | Same-session scalar/packed deltas vs the FP32-stage baseline; explicit zero line |
| `*_within_session_paths.{png,svg}` | ABC/CAB/BCA paired paths without treating roles as independent repeats |
| `*_quality_gates.{png,svg}` | Shared preheat, qualified trace R², and recorded temperature context |

All charts are bounded to RTX 3090, S=512, grid CTA=16, two rows/CTA, and
FP16 I/O fixed. Descriptive intervals use fresh-session `n=3` and are not
selection tests.

Regenerate after the fail-closed analyzer succeeds:

```bash
source scripts/activate_softmax_experiment_env.sh
python3 scripts/analyze_softmax_whole_precision_stage_isolation.py \
  --run-dir results/raw/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1
python3 scripts/plot_softmax_whole_precision_stage_isolation.py \
  --run-dir results/raw/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1 \
  --out-dir docs/assets/softmax_whole_precision_stage_isolation
```

The generated `*_figure_manifest.json` records the analyzed run path, its
manifest SHA-256, and figure metadata; the fail-closed analyzer remains the
underlying raw/trace hash-binding evidence.
