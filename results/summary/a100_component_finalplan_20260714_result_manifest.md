# A100 External Result Manifest

This manifest lists files that should be copied back from the target GPU node.
It is a transfer checklist, not a validation result. After copying files, run `scripts/audit_platform_result_package.py`.

| item | value |
|---|---|
| profile | `a100` |
| tag | `20260714` |
| expected active SM | `108` |
| expected runtime SM count | `not exact-checked` |
| CUDA arch | `80` |
| build directory | `build-a100` |
| binary | `./build-a100/a100_fp16_energy_v2` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |

## Build Requirement

Build the profile-specific binary before running the command package. The default `build` directory is RTX 3090/sm_86 only; do not reuse it for A100/V100/H100 results.

```bash
cmake -S . -B build-a100 -DCMAKE_CUDA_ARCHITECTURES=80
cmake --build build-a100 -j
```

## Copy Checklist

| artifact group | expected path | purpose | validated by |
|---|---|---|---|
| generated runnable command package | `results/summary/a100_component_finalplan_20260714_commands.sh` | documents the exact finalplan commands used on the target node | `platform_command_package` |
| generated command plan markdown | `results/summary/a100_component_finalplan_20260714_command_plan.md` | records target profile, coordinates, power semantics, NCU and audit gates | `platform_command_package` |
| node preflight report | `results/summary/a100_component_finalplan_20260714_preflight.md` | proves GPU/profile, NVML, power scope, NCU availability, and binary dry-run | `preflight` |
| raw energy CSVs | `results/raw/a100_component_finalplan_20260714_tensor.csv` | contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM | `raw_energy_profile_and_power` |
| raw energy CSVs | `results/raw/a100_component_finalplan_20260714_shared.csv` | contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM | `raw_energy_profile_and_power` |
| raw energy CSVs | `results/raw/a100_component_finalplan_20260714_l1.csv` | contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM | `raw_energy_profile_and_power` |
| raw energy CSVs | `results/raw/a100_component_finalplan_20260714_l2.csv` | contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM | `raw_energy_profile_and_power` |
| raw energy CSVs | `results/raw/a100_component_finalplan_20260714_dram.csv` | contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM | `raw_energy_profile_and_power` |
| Tensor pair calibration manifest | `results/raw/a100_component_finalplan_20260714_tensor_pair_calibration.csv` | proves reg_mma-calibrated ITER was applied identically to treatment and control | `tensor_pair_calibration_policy` |
| L2 pair calibration manifest | `results/raw/a100_component_finalplan_20260714_l2_pair_calibration.csv` | proves L2 treatment and address control used identical resolved ITER | `l2_pair_calibration_policy` |
| DRAM pair calibration manifest | `results/raw/a100_component_finalplan_20260714_dram_pair_calibration.csv` | proves DRAM treatment and address control used identical resolved ITER | `dram_pair_calibration_policy` |
| power API audit | `results/summary/a100_component_finalplan_20260714_power_api_audit.csv` | proves final rows use nvml_total_energy + total_energy_mj_delta + GPU/device scope | `power_api_final_candidate` |
| power-state stability audit | `results/summary/a100_component_finalplan_20260714_power_state_audit.csv` | excludes average-power, endpoint-power, clock, and temperature outlier rows | `power_state_quality` |
| NCU counter summary | `results/ncu/a100_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv` | records L1/L2 hit rates, L1/L2/DRAM bytes/access counts, shared bytes, tensor inst, stalls | `ncu_summary_quality` |
| NCU path acceptance | `results/summary/a100_component_finalplan_20260714_ncu_acceptance.csv` | proves tensor/control/shared/global-L1/L2 candidates use intended paths | `ncu_path_acceptance` |
| matched-control summary | `results/summary/a100_component_finalplan_20260714_matched_control_summary.csv` | summarizes treatment-control delta_E and pJ/FLOP or pJ/bit estimates | `matched_control_summary` |
| matched-control detail | `results/summary/a100_component_finalplan_20260714_matched_control_detail.csv` | preserves row-level numerator/control pairing, source files, scopes, and denominators | `matched_control_detail` |
| component reliability audit | `results/summary/a100_component_finalplan_20260714_component_reliability_audit.csv` | combines power, NCU, and matched-control evidence into accepted/reject component verdicts | `component_reliability` |
| instability audit | `results/summary/a100_component_finalplan_20260714_matched_control_instability_audit.csv` | explains weak-signal, negative, or noisy matched-control rows and follow-up conditions | `instability_diagnosis` |
| strict component coefficient summary | `results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260714.csv` | reporting table built only from accepted reliability evidence | `strict_summary_policy` |
| strict component summary audit | `results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260714.csv` | verifies traceability, power matrix policy, NCU denominator, counter schema, coordinate alignment, hierarchy, and plausibility gates | `strict_summary_audit_clean` |
| L2 NCU-first path selection | `results/summary/a100_component_finalplan_20260714_l2_path_selection.csv` | records the policy/layout/blocks-SM candidates and the strict path verdict before energy measurement | `l2_path_selection_policy` |

## After Copy

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile a100 \
  --tag 20260714 \
  --expected-active-sm 108 \
  --out-csv results/summary/a100_platform_result_package_audit_20260714.csv \
  --out-md results/summary/a100_platform_result_package_audit_20260714.md \
  --fail-on-incomplete
```

If the package audit reports `missing` or `fail`, generate a gap report:

```bash
python3 scripts/summarize_platform_package_gaps.py \
  --target-profile a100 \
  --tag 20260714 \
  --audit-csv results/summary/a100_platform_result_package_audit_20260714.csv \
  --manifest-csv results/summary/a100_component_finalplan_20260714_result_manifest.csv \
  --out-csv results/summary/a100_platform_result_package_gaps_20260714.csv \
  --out-md results/summary/a100_platform_result_package_gaps_20260714.md
```

Refresh the goal readiness audit and cross-platform dashboard:

```bash
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/audit_component_goal_readiness.py \
  --ncu "$(command -v ncu || echo ncu)" \
  --out-csv results/summary/component_energy_goal_readiness_audit_20260714.csv \
  --out-md results/summary/component_energy_goal_readiness_audit_20260714.md
python3 scripts/build_platform_intake_dashboard.py \
  --tag 20260714 \
  --goal-readiness-csv results/summary/component_energy_goal_readiness_audit_20260714.csv \
  --out-csv results/summary/platform_component_intake_dashboard_20260714.csv \
  --out-md results/summary/platform_component_intake_dashboard_20260714.md
```

The strict summary audit must include NCU counter schema and coordinate alignment checks. A row is not final if the NCU sidecar validates only the mode name but was captured with different `W_SM`, `blocks/SM`, `active_SM`, `reuse_factor`, `load_repeat`, or `store_repeat` values.
