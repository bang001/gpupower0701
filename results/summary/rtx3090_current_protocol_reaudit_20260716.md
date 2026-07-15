# Strict Component Summary Audit

This audit verifies the curated strict measurement-scope summary against its reliability artifacts. It is a reporting consistency gate, not a silicon-level energy proof and not a fresh NCU replay.

- strict summary: `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260716.csv`

## Status Counts

| status | checks |
|---|---:|
| `fail` | 1 |

## Checks

| component | check | status | expected | actual | interpretation |
|---|---|---|---|---|---|
| strict_summary_package | summary_artifact_exists | `fail` | strict component summary CSV exists | results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260716.csv | strict summary build did not produce an artifact; inspect the reliability and NCU acceptance reports before treating any component coefficient as final |
