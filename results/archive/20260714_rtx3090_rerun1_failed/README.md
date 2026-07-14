# RTX 3090 `20260714_rerun1` Failed Package

This directory preserves the complete historical package that exited with code
1. It is not final coefficient evidence.

- The old Shared pair used `clocked_empty`, which produced unstable and
  negative differentials.
- Global L1 had only 4/15 valid pairs.
- L2 was profiled with the old full metric bundle and predates the coherent
  `l2_path_minimal` gate.
- The strict coefficient artifact was not generated.

The files retain their original `results/...` text references for audit history;
those paths are relative to the repository layout at the time of the failed run.
Use `results/summary/rtx3090_shared_l1_matched_pair_report_20260714_ko.md` and
`results/ncu/rtx3090_l2_minimal_stall_profile_20260714/` for the current targeted
evidence.
