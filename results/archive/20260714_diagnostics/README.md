# 2026-07-14 Diagnostic Artifacts

These files are retained for auditability but are not final coefficient evidence.

- `ncu/rtx3090_pairv2b_permission*`: failed or partial NCU permission-fallback probes.
- `ncu/rtx3090_l2_minimal_profile_20260714`: the first minimal L2 bundle before
  the long-scoreboard metric was restored.
- `raw/`: raw CSVs associated with those incomplete probes.

The authoritative minimal L2 validation is
`results/ncu/rtx3090_l2_minimal_stall_profile_20260714/`. The authoritative
targeted Shared/Global-L1 run is `results/ncu/rtx3090_pairv2b_20260714/` plus
the matching raw and summary files.
