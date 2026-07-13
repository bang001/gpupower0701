# Platform Power/Readiness Audit

이 보고서는 RTX 3090, V100, A100, H100 profile의 power API 의미, preflight profile, finalplan 생성 스크립트, 플랫폼 문서가 서로 맞는지 정적으로 점검한다. 실제 GPU 측정 결과가 아니라, 새 노드에서 실험하기 전 RTX 3090 기준이 섞이지 않도록 확인하는 readiness gate다.

- detail CSV: `results/summary/platform_power_readiness_audit_20260708.csv`
- checks: 85
- failures: 0

## Verdict

정적 readiness check는 통과했다. 단, 이것은 A100/V100/H100에서 component coefficient가 검증되었다는 뜻이 아니다. 각 노드에서 power API audit, NCU path acceptance, matched-control/reliability audit을 새로 통과해야 final 후보가 된다.

## Profile Summary

| profile | pass | fail |
|---|---:|---:|
| `a100` | 19 | 0 |
| `all` | 3 | 0 |
| `h100` | 19 | 0 |
| `rtx3090` | 19 | 0 |
| `v100` | 25 | 0 |

## a100

| check | status | expected | actual |
|---|---|---|---|
| `plan_profile_present` | `pass` | `present` | `True` |
| `preflight_profile_present` | `pass` | `present` | `True` |
| `plan_cuda_arch` | `pass` | `80` | `80` |
| `plan_active_sm` | `pass` | `108` | `108` |
| `plan_ncu_chip` | `pass` | `ga100` | `ga100` |
| `plan_power_semantics` | `pass` | `instant` | `instant` |
| `preflight_cuda_arch` | `pass` | `80` | `80` |
| `preflight_active_sm` | `pass` | `108` | `108` |
| `preflight_ncu_chip` | `pass` | `ga100` | `ga100` |
| `preflight_power_semantics` | `pass` | `instant` | `instant` |
| `guide_exists` | `pass` | `exists` | `True` |
| `guide_power_and_platform_terms` | `pass` | `all required guide terms` | `ok` |
| `generated_plan_runs` | `pass` | `return code 0` | `0` |
| `generated_shell_final_gates` | `pass` | `power/ncu/matched/reliability gates` | `ok` |
| `generated_shell_goal_dashboard_order` | `pass` | `goal readiness audit before dashboard refresh` | `ok` |
| `generated_gap_report_tagged` | `pass` | `gap report command carries target profile and tag` | `ok` |
| `generated_default_binary_path` | `pass` | `profile-built binary path ./build-a100/a100_fp16_energy_v2` | `ok` |
| `generated_markdown_power_api_note` | `pass` | `power matrix and effective-energy caveat` | `ok` |
| `generated_l2_capacity_policy` | `pass` | `0` | `0` |

## all

| check | status | expected | actual |
|---|---|---|---|
| `power_matrix_exists` | `pass` | `exists` | `True` |
| `power_matrix_core_terms` | `pass` | `all core API/scope/gate terms` | `ok` |
| `ncu_permission_fallback_policy` | `pass` | `counter probe, exact-error sudo retry, child-process coverage` | `ok` |

## h100

| check | status | expected | actual |
|---|---|---|---|
| `plan_profile_present` | `pass` | `present` | `True` |
| `preflight_profile_present` | `pass` | `present` | `True` |
| `plan_cuda_arch` | `pass` | `90` | `90` |
| `plan_active_sm` | `pass` | `132` | `132` |
| `plan_ncu_chip` | `pass` | `gh100` | `gh100` |
| `plan_power_semantics` | `pass` | `one_sec_average` | `one_sec_average` |
| `preflight_cuda_arch` | `pass` | `90` | `90` |
| `preflight_active_sm` | `pass` | `132` | `132` |
| `preflight_ncu_chip` | `pass` | `gh100` | `gh100` |
| `preflight_power_semantics` | `pass` | `one_sec_average` | `one_sec_average` |
| `guide_exists` | `pass` | `exists` | `True` |
| `guide_power_and_platform_terms` | `pass` | `all required guide terms` | `ok` |
| `generated_plan_runs` | `pass` | `return code 0` | `0` |
| `generated_shell_final_gates` | `pass` | `power/ncu/matched/reliability gates` | `ok` |
| `generated_shell_goal_dashboard_order` | `pass` | `goal readiness audit before dashboard refresh` | `ok` |
| `generated_gap_report_tagged` | `pass` | `gap report command carries target profile and tag` | `ok` |
| `generated_default_binary_path` | `pass` | `profile-built binary path ./build-h100/a100_fp16_energy_v2` | `ok` |
| `generated_markdown_power_api_note` | `pass` | `power matrix and effective-energy caveat` | `ok` |
| `generated_l2_capacity_policy` | `pass` | `0` | `0` |

## rtx3090

| check | status | expected | actual |
|---|---|---|---|
| `plan_profile_present` | `pass` | `present` | `True` |
| `preflight_profile_present` | `pass` | `present` | `True` |
| `plan_cuda_arch` | `pass` | `86` | `86` |
| `plan_active_sm` | `pass` | `82` | `82` |
| `plan_ncu_chip` | `pass` | `ga102` | `ga102` |
| `plan_power_semantics` | `pass` | `one_sec_average` | `one_sec_average` |
| `preflight_cuda_arch` | `pass` | `86` | `86` |
| `preflight_active_sm` | `pass` | `82` | `82` |
| `preflight_ncu_chip` | `pass` | `ga102` | `ga102` |
| `preflight_power_semantics` | `pass` | `one_sec_average` | `one_sec_average` |
| `guide_exists` | `pass` | `exists` | `True` |
| `guide_power_and_platform_terms` | `pass` | `all required guide terms` | `ok` |
| `generated_plan_runs` | `pass` | `return code 0` | `0` |
| `generated_shell_final_gates` | `pass` | `power/ncu/matched/reliability gates` | `ok` |
| `generated_shell_goal_dashboard_order` | `pass` | `goal readiness audit before dashboard refresh` | `ok` |
| `generated_gap_report_tagged` | `pass` | `gap report command carries target profile and tag` | `ok` |
| `generated_default_binary_path` | `pass` | `profile-built binary path ./build/a100_fp16_energy_v2` | `ok` |
| `generated_markdown_power_api_note` | `pass` | `power matrix and effective-energy caveat` | `ok` |
| `generated_l2_capacity_policy` | `pass` | `0` | `0` |

## v100

| check | status | expected | actual |
|---|---|---|---|
| `plan_profile_present` | `pass` | `present` | `True` |
| `preflight_profile_present` | `pass` | `present` | `True` |
| `plan_cuda_arch` | `pass` | `70` | `70` |
| `plan_active_sm` | `pass` | `80` | `80` |
| `plan_ncu_chip` | `pass` | `gv100` | `gv100` |
| `plan_power_semantics` | `pass` | `instant` | `instant` |
| `plan_blocks` | `pass` | `4,16,32` | `4,16,32` |
| `plan_ncu_blocks` | `pass` | `32` | `32` |
| `plan_shared_ncu_w` | `pass` | `32` | `32` |
| `plan_l1_ncu_w` | `pass` | `32` | `32` |
| `plan_l2_ncu_w` | `pass` | `32` | `32` |
| `preflight_cuda_arch` | `pass` | `70` | `70` |
| `preflight_cuda_toolchain_policy` | `pass` | `contains:compute_70` | `Use a compiler that lists compute_70. CUDA 12.x is the recommended V100 build line; CUDA 13 removed Volta offline compilation support.` |
| `preflight_active_sm` | `pass` | `80` | `80` |
| `preflight_ncu_chip` | `pass` | `gv100` | `gv100` |
| `preflight_power_semantics` | `pass` | `instant` | `instant` |
| `guide_exists` | `pass` | `exists` | `True` |
| `guide_power_and_platform_terms` | `pass` | `all required guide terms` | `ok` |
| `generated_plan_runs` | `pass` | `return code 0` | `0` |
| `generated_shell_final_gates` | `pass` | `power/ncu/matched/reliability gates` | `ok` |
| `generated_shell_goal_dashboard_order` | `pass` | `goal readiness audit before dashboard refresh` | `ok` |
| `generated_gap_report_tagged` | `pass` | `gap report command carries target profile and tag` | `ok` |
| `generated_default_binary_path` | `pass` | `profile-built binary path ./build-v100/a100_fp16_energy_v2` | `ok` |
| `generated_markdown_power_api_note` | `pass` | `power matrix and effective-energy caveat` | `ok` |
| `generated_l2_capacity_policy` | `pass` | `0` | `0` |

## Interpretation

- `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분이 final numerator의 우선 경로다.
- `nvmlDeviceGetPowerUsage`는 세대별 의미가 다르다. V100/A100은 `instant`, RTX 3090/H100은 `one_sec_average`로 기록한다.
- 최신 NVML의 `nvmlDeviceGetPowerUsage_v2`와 `nvmlDeviceGetTotalEnergyConsumption_v2`는 현재 harness가 아직 호출하지 않는다. v2를 도입하면 v1/v2 결과를 별도 metadata와 run class로 분리한다.
- H100/HGX의 module power와 GPU memory power는 preflight metadata로만 기록하고 component coefficient numerator로 섞지 않는다.
- final row는 `measurement_scope=gpu_device_total_energy_counter`여야 하며, fallback/module/memory scope는 별도 provisional 또는 reject로 분리한다.
- 이 readiness audit은 코드/문서 정합성만 확인한다. 실제 coefficient 채택은 각 플랫폼의 raw CSV, NCU counter, reliability audit 결과로 판정한다.
