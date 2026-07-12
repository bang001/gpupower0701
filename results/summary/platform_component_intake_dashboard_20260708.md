# Platform Component Result Intake Dashboard

This dashboard summarizes package audits and gap reports. It does not replace package audits, strict summary audits, or the goal readiness audit.

| item | value |
|---|---|
| tag | `20260708` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| profiles passing package + strict summary | `1/4` |
| goal readiness audit | `results/summary/component_energy_goal_readiness_audit_20260708.csv` |
| goal readiness status | `incomplete` (pass=36, missing=6, fail=0, warning=0) |

## Platform Status

| profile | power semantics | package status | package pass/missing/fail | gap blockers | first open stage | strict summary | accepted components |
|---|---|---|---:|---:|---|---|---:|
| `rtx3090` | `one_sec_average` | `local_strict_evidence` | 0/0/0 | 0 | - | `pass` | 4 |
| `v100` | `instant` | `missing_artifacts` | 2/15/0 | 15 | preflight | `missing_summary` | 0 |
| `a100` | `instant` | `missing_artifacts` | 2/15/0 | 15 | preflight | `missing_summary` | 0 |
| `h100` | `one_sec_average` | `missing_artifacts` | 2/15/0 | 15 | preflight | `missing_summary` | 0 |

## First Corrective Actions

| profile | first issue | corrective action | next command | gap report |
|---|---|---|---|---|
| `rtx3090` | none | none | `none` | `results/summary/rtx3090_platform_result_package_gaps_20260708.csv` |
| `v100` | missing | Run strict preflight on the target node with the explicit profile, expected active SM count, binary path, and NCU path, then copy the markdown report back. | `python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile v100 --strict --active-sm 80 --binary ./build-v100/a100_fp16_energy_v2 --ncu "$(command -v ncu || echo ncu)" --out results/summary/v100_component_finalplan_20260708_preflight.md` | `results/summary/v100_platform_result_package_gaps_20260708.csv` |
| `a100` | missing | Run strict preflight on the target node with the explicit profile, expected active SM count, binary path, and NCU path, then copy the markdown report back. | `python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile a100 --strict --active-sm 108 --binary ./build-a100/a100_fp16_energy_v2 --ncu "$(command -v ncu || echo ncu)" --out results/summary/a100_component_finalplan_20260708_preflight.md` | `results/summary/a100_platform_result_package_gaps_20260708.csv` |
| `h100` | missing | Run strict preflight on the target node with the explicit profile, expected active SM count, binary path, and NCU path, then copy the markdown report back. | `python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile h100 --strict --active-sm 132 --binary ./build-h100/a100_fp16_energy_v2 --ncu "$(command -v ncu || echo ncu)" --out results/summary/h100_component_finalplan_20260708_preflight.md` | `results/summary/h100_platform_result_package_gaps_20260708.csv` |

## Interpretation

A platform is not final merely because the command package exists. External platforms need a clean package audit, a strict component summary, and a strict summary audit. RTX 3090 is shown as local strict evidence when its strict summary and strict audit pass without an external package audit. Power-related rows must satisfy the power measurement matrix policy: `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` plus the profile-specific `nvml_power_usage_semantics`.
