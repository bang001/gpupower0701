# Validation Report — RTX 3090 whole-Softmax precision stage isolation

## Overall Assessment: Share with caveats

The measurement and calculation evidence is ready to share as a bounded
RTX 3090 result. All 27 measured roles passed the analyzer's manifest, raw
schema, SHA-256, cyclic-order, denominator, numerical, qualified trace, and
SMID gates. The result is not ready to support an energy-based implementation
selection because every n=3 paired descriptive t95 interval includes zero.

## Methodology Review

- Question answered: whether complete-Softmax `exp`, `max+sum reduction`, and
  `normalization` should be separately compared at FP32, scalar FP16, and
  packed FP16.
- Population and scope: one full RTX 3090 (CC 8.6, 82 SM), S=512, grid=16
  CTA, 256 threads/CTA, two independent rows/CTA, FP16 I/O, logit scale=4.
- Baseline: `fp16_io_fp32_all`, so input/output precision is held fixed while
  the named compute stage changes.
- Independent repeat: one fresh CUDA-process session. Each stage group has
  exactly three sessions in ABC/CAB/BCA cyclic order; role rows are not
  treated as 27 independent samples. After the baseline-only preheat, each
  session also performs schedule-order calibration and an unrecorded same-order
  full-policy warm-up; cyclic order balances position, not every directed
  carryover.
- Metric: `net_pJ_per_logical_output_element = (qualified trace energy −
  idle power × elapsed) × 1e12 / logical output elements`.

## Issues Found

1. **Severity: Medium — n=3 uncertainty.** All six paired descriptive t95
   intervals include zero. Directional means must not be presented as an
   energy win or loss.
2. **Severity: Medium — fixed operating point.** No CTA/S sweep, stage
   interaction factorial, fixed-clock experiment, or external-meter study was
   performed. Results do not generalize to A100/H100/V100 or other shapes.
3. **Severity: Medium — premeasurement carryover.** The 20-second baseline
   preheat is common, but schedule-order calibration and an unrecorded
   same-order warm-up precede recorded roles. ABC/CAB/BCA rotates policy
   position but not all directed adjacent predecessors, so a thermal or
   scheduling carryover cannot be separated from a stage contrast.
4. **Severity: Low — portable HTML browser QA.** The portable builder passed
   artifact validation, packaging, payload equality, and structural fallback
   verification. It reported `structural_only` because no Chromium
   headless-shell is installed, so interactive source-dialog and viewport QA
   are not independently browser-verified.

## Calculation Spot-Checks

- **Evidence identity:** Verified — analyzer accepted all 9 session raw/trace
  pairs and 27 roles against the immutable manifest and binary/runner hashes.
- **Denominator and primary metric:** Verified — the analyzer recomputed
  logical element counts from CTA×rows×ITER×S and reconciled net and gross
  pJ/output fields against energy numerators.
- **Pairing:** Verified — every scalar/packed contrast is calculated only
  against the shared baseline within the same stage/session identity; this
  does not make directed carryover fully counterbalanced.
- **Trace quality:** Verified — all roles use qualified Theil–Sen trace energy
  with R² `0.999885643–0.999966829` and 28–29 counter updates.
- **Numerical correctness:** Verified — all roles have zero non-finite output
  and passed their absolute-error and row-sum gates.
- **Compiled path:** Verified — `sass_audit.json` passed, including scalar vs
  packed exponent PTX form, scalar/packed reduction shape, and the absence of
  native FP16 reciprocal evidence.

## Visualization Review

- Four Matplotlib figures were generated and visually inspected: absolute
  session spread, paired contrasts, within-session paths, and quality gates.
- Absolute-energy charts start at zero. The paired-delta chart has an explicit
  zero reference, visible raw session markers, and descriptive intervals.
- Chart titles and subtitles expose the unit, fixed scope, and fresh-session
  sample size. Temperature is labeled context rather than a causal result.
- The HTML report contains two native charts and four source-backed tables.
  Its delivered semantic fallback is present; see the browser-QA limitation
  above.

## Suggested Improvements

1. Confirm only two decision-relevant candidates—packed exp vs baseline and
   scalar reduction vs baseline—with a small two-policy AB/BA fresh-session
   protocol at the same S=512/CTA=16 coordinate and a common/fixed
   premeasurement conditioning block.
2. If a deployment decision depends on the energy difference, repeat the
   confirmation under fixed-clock or an external higher-resolution meter.
3. Re-run the per-policy PTX/SASS audit on every new GPU/toolchain before
   claiming scalar/packed equivalence or difference across architectures.

## Required Caveats for Stakeholders

- This is a complete-Softmax `net pJ/logical output element` result, not the
  older EX2 Operand-rate ATC metric and not pure MUFU/SFU/FP16-ALU energy.
- Packed reduction uses the two independent CTA rows as half2 lanes; it is not
  an intra-row pseudo-pack.
- Normalization compares FP16-rounded reciprocal plus scalar/packed multiply;
  it does not establish a native FP16 reciprocal instruction energy.
- Stage deltas are not additive predictors of an all-FP16 policy.
- The reported cyclic schedule balances position but not all calibration/warm-up
  carryovers, so the directional means remain descriptive.
