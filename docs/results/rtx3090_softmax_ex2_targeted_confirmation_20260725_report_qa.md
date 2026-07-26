# RTX 3090 Softmax EX2 CTA=48/S=1024 targeted confirmation report QA

## Overall assessment: Share with caveats after artifact validation and portable packaging

The builder independently accepted the frozen `CTA=48, S=1024` program, 9/9 complete quality-pass cells, three cyclic fresh sessions, 27 matched blocks, exact denominator aliases, three implementation summaries, native numerical validation, static SASS audit, and dynamic NCU path-only audit. The canonical artifact is ready for external `validate_artifact` and portable HTML packaging; those two results are appended by the owning workflow.

## Calculation spot-checks

- Primary independent unit: one fresh session implementation mean, `n=3` per implementation. Matched blocks are not pooled as independent repetitions.
- `pJ/logical result == incremental pJ/element` row-wise for all 9 cells because treatment adds exactly one logical EX2 result per input element.
- FP32 mean: `82.164` incremental pJ/element.
- Scalar FP16 mean: `19.393` incremental pJ/element.
- Packed FP16x2 mean: `25.055` incremental pJ/element.
- Packed−scalar contrast: `5.662`; diagnostic t95 `[ -19.253, 30.577 ]`, which includes zero.
- Native NCU observed/expected treatment-control XU delta: `49,152,000` for scalar FP16 and packed FP16x2; profiler energy is excluded.
- SASS: packed source has 4 `f16x2` PTX instructions but final sm86 code has 8 scalar `MUFU.EX2.F16`; it is not evidence of one physical two-lane MUFU issue.

## Required caveats

- This is incremental board-energy contrast for an added exponent path, not total Softmax pJ/element or pure functional-unit energy.
- Three fresh sessions provide only a descriptive df=2 interval; the report does not claim packed superiority.
- Historical 60-cell target values are context only and are excluded from the new primary aggregate.
- Temperature/clock fields are QA diagnostics, not randomized causal covariates.

## Artifact inventory

- Generated: `2026-07-25T13:20:21+09:00`
- Canonical artifact: `docs/results/rtx3090_softmax_ex2_targeted_confirmation_20260725_artifact.json`
- Artifact SHA-256: `2aacbbffde5ae0b08a78fe383e41d74a83953f98927c816ee9e3287e5f1064d8`
- Builder SHA-256: `22b123e6a578286ae30667bcac3a6b5e277ed6ea3afefd40ecc4a65e2513baee`
- Datasets: `7`; rows: `42`; serialized bytes: `65949`

## Input hashes

- `docs/results/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_analysis_ko.md` — SHA-256 `3b0860ba9bba7a51c66827dd5bea02ac68471a8f2cb2ae42cbba0c21d9859156`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_session_cells.csv` — SHA-256 `79233d4adeb17af3c6eca0eadaf3f9e1971a1c2fa374c0814278ec08710670ed`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_contrast_summary.csv` — SHA-256 `b034ad37ac668a3f1b107721b31d4a09329ccf485055450c18f0a43c2a7dad75`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_within_session_contrasts.csv` — SHA-256 `02e4969e87ee967872ee7631dd78993f717540648bbc6b1d1afd9e0bf4a74238`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_diagnostics.csv` — SHA-256 `8e10dc657ce000b61c5e5dcbea418c6e64bf304e0adf7095b4ffa288396549be`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_historical_context.csv` — SHA-256 `c07f0c313f2d34ed2d9175bb72b56a086efafcecbb866bd193068d66e0149116`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_historical_scalar_blocks.csv` — SHA-256 `db682d7335dcec01f6a456def97dc014452a83b1fc995da8435557f2104e9aa3`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_implementation_summary.csv` — SHA-256 `ae028d2f2b229fb6b2348571f200f0b57e023b4dead4d67502a780aa1e1d7583`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_matched_blocks.csv` — SHA-256 `988f10bc9ce3c4a0e11dac243c8de210cb4c998e4dacc97adffa908a7170db3c`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_ncu_audit.csv` — SHA-256 `a50ebecb10495051f3df2382ba02fa13f6614381ee8dde12600d6c42cdd549e7`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_numerical_validation.csv` — SHA-256 `ef4e0af3a5ba3882db6a7da6e29017e53dfe25690005afe9ff5dfe590346805f`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_plan.csv` — SHA-256 `67a317b4e611a4eb9efbb55cdfd067d7e4d043c07f38c75f9bb8ec1ec024ef05`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_program.csv` — SHA-256 `0926d04694ae343c641e8a24f99ff52fedd022b0e253b89721b86caefcadd4c2`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_sass_audit.csv` — SHA-256 `d4e4b509bcc1f52a1fb7776cfc44768ce2fe53fe9915190c975a1c5b333a759c`
- `results/summary/rtx3090_softmax_ex2_targeted_confirmation_targeted_g48s1024_confirm_v1_20260725_state.csv` — SHA-256 `b0e1c738bc13bcde154e8b45720235fe3b18f980cba8cdbe0841ddf41a2763e1`

## Packaging status

Canonical `validate_artifact` passed: `surface=report`, `dataset_count=7`,
`source_count=13`, `snapshot_status=ready`.

Portable HTML packaging passed:

- Command: `npm run report:deliver -- --input docs/results/rtx3090_softmax_ex2_targeted_confirmation_20260725_artifact.json --output docs/results/rtx3090_softmax_ex2_targeted_confirmation_20260725_report.html`
- Stages: validation `passed`, package `passed`, verification `structural_only`
- Blocks/charts/tables: `21 / 5 / 2`
- HTML SHA-256: `e438165ea2416e96022d9e86826c1d82f50b98238afed5756e214df2da35f312`

`structural_only` means the canonical payload, package roots, and semantic
fallback passed, but an installed Chromium headless shell was unavailable.
No browser was downloaded; chart SVG extraction, viewport checks, and source
dialog interaction were therefore not run. The delivered HTML retains its
semantic chart/table fallback, and this is a QA limitation rather than an
energy-data limitation.

## Matplotlib companion figure QA (2026-07-26)

The static Matplotlib figures are a companion for visualizing the primary
fresh-session spread; they do not edit the canonical artifact or the portable
HTML above. Their generator is
[`scripts/plot_softmax_ex2_targeted_confirmation.py`](../../scripts/plot_softmax_ex2_targeted_confirmation.py),
and its input/output contract is documented in the
[asset inventory](../assets/softmax_ex2_targeted_confirmation/README.md).

- Self-test passed against the frozen inputs: exactly 3 implementation summaries,
  9 quality-pass session cells, 3 same-session contrast types, and 27 nested
  quality-pass matched blocks.
- The generator checks that each implementation appears in positions 1/2/3 once,
  and that displayed summary/contrast means reproduce the session-cell arithmetic.
- It writes PNG and SVG pairs for session spread, paired contrasts, cyclic-order
  diagnostics, and nested matched-block diagnostics. PNG exports were decoded
  with Pillow and checked for at least 1200×700 pixels.
- The primary conclusion remains based on three fresh sessions per implementation;
  the 27 matched blocks remain nested diagnostic measurements, not `n=27`
  independent repetitions.
