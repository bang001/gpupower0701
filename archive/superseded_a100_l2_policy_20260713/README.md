# Superseded A100 L2 Policy Selector

`select_a100_l2_residency_policy.py` only compared normal and persisting cache
policies at a fixed B16 contiguous layout. It was replaced on 2026-07-13 by
`scripts/select_a100_l2_path_configuration.py`, which also validates address
layout, blocks/SM, observed/expected traffic, and the persisting-cache counter.

This directory is retained for historical reproducibility. Do not use it for a
new A100 remediation run.
