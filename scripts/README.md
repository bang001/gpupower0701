# Scripts Map

이 디렉토리에는 현재 finalplan 실행에 필요한 active script만 둔다. 과거 pair-centric, NNLS/regression, reference-aligned, register-footprint diagnostic script는 `archive/legacy_20260707/scripts/`로 이동했다.

## Active Finalplan Flow

| 단계 | script | 역할 |
|---|---|---|
| preflight | `preflight_gpu_support.py` | GPU profile, NVML, CUDA compiler target, NCU, power scope, binary dry-run 확인. `--strict`는 profile/toolchain mismatch와 dry-run 실패를 nonzero로 막고 `--self-test`로 회귀 검증 |
| command plan | `plan_platform_component_experiment.py` | 플랫폼별 finalplan 명령 생성 |
| platform readiness | `audit_platform_power_readiness.py` | RTX 3090/V100/A100/H100 profile, power API 의미, 문서, 생성 plan 정합성 점검 |
| energy sweep | `run_component_regression_sweep.py` | Python/C++ feasibility self-test와 unique-coordinate binary dry-run 후 NCU 없이 duration-calibrated energy CSV 수집 |
| paired stability | `run_paired_component_stability.py` | drift-sensitive component를 control-treatment-control 순서로 재측정 |
| power API audit | `audit_power_api_measurements.py` | raw energy CSV가 power measurement matrix 기준 final/provisional/reject인지 판정하고 새 finalplan에서는 explicit `measurement_scope`를 요구하며 `--self-test`로 A100 semantics, fallback numerator, H100 module scope 혼입 회귀를 검증 |
| power-state audit | `audit_power_state_stability.py` | raw row의 평균 전력/endpoint power outlier를 찾아 측정 품질 문제와 weak-signal 문제를 분리 |
| NCU sidecar | `run_ncu_validation.sh` | chip별 metric availability를 확인한 뒤 primary finalplan mode의 hit/access/byte/stall/spill/occupancy/launch-resource counter 수집 |
| NCU summary | `summarize_ncu_cache_metrics.py` | NCU raw export를 cache/path와 achieved occupancy/register/shared-block summary로 정리 |
| path acceptance | `analyze_ncu_path_acceptance.py` | accepted/provisional/rejected path 판정 |
| matched-control | `analyze_matched_control_energy.py` | NCU byte denominator 기반 pJ/FLOP, pJ/byte, pJ/bit 계산 |
| component reliability | `audit_component_reliability.py` | power/NCU/matched-control 결과를 결합해 component별 최종 verdict 생성 |
| instability audit | `audit_matched_control_instability.py` | invalid/weak-signal matched-control row 원인과 follow-up 실험 조건 요약 |
| strict summary build | `build_strict_component_summary.py` | accepted reliability, matched-control, NCU acceptance artifact에서 보고용 strict component coefficient summary 생성. 여러 NCU summary artifact가 입력되면 component별 strict detail 좌표를 덮는 artifact만 row에 연결하고, path-relevant NCU hit/access/byte/stall evidence를 summary row에 직접 노출하며 `--self-test`로 Tensor B4/B16 artifact 선택 회귀를 검증 |
| strict summary audit | `audit_strict_component_summary.py` | strict component summary가 reliability artifact, matched-control detail row, power API scope, NCU denominator, 계층 순서, broad plausibility range, NCU counter schema, coordinate alignment, `ncu_evidence_summary_fields`에 일치하는지 검증하고, `--self-test`로 strict detail 좌표 mismatch를 잡는지 검증 |
| platform package audit | `audit_platform_result_package.py` | 외부 노드에서 복사해 온 단일 profile/tag 결과 패키지의 raw profile metadata, active SM, power, NCU, reliability, strict summary gate를 검수 |
| platform package gap report | `summarize_platform_package_gaps.py` | package audit의 `missing`/`fail` row를 단계별 원인, power matrix 관련성, 재실행 조치로 번역 |
| platform intake dashboard | `build_platform_intake_dashboard.py` | RTX 3090/V100/A100/H100 package audit, gap report, strict summary 상태를 한 표로 집계 |
| platform gate self-test | `selftest_platform_package_gates.py` | mock package로 L2/L1 역전, out-of-range coefficient, stale strict audit, preflight strict verdict 실패/driver/power-scope/NCU metadata 누락, strict summary/raw CSV의 profile power semantics 오류, fallback numerator, H100 module scope 혼입, power API audit의 non-final row, power-state evidence/reject 오류, matched summary component/median/NCU denominator 누락, reliability status/invalid rows/scope 오류, NCU cache/access 컬럼 누락, path counter 0, NCU path acceptance 후보 누락/rejected/evidence column 누락/accepted evidence 실패가 fail 처리되는지 검증 |
| platform result manifest | `write_platform_result_manifest.py` | 외부 노드에서 복사해 와야 할 raw/audit/NCU/summary artifact 목록을 CSV/Markdown으로 생성 |
| goal readiness audit | `audit_component_goal_readiness.py` | power matrix, RTX 3090 strict evidence, NCU availability, local readiness runner policy, A100/V100/H100 result package 누락 여부를 상위 목표 기준으로 점검하며 preflight/power API/strict summary/package/goal validator self-test 상태도 확인 |
| local readiness runner | `run_local_readiness_checks.sh` | preflight/power API/strict summary/package/goal/manifest/gap/dashboard self-test, platform readiness, A100/V100/H100 manifest+package audit+gap report refresh, RTX 3090 strict audit, goal readiness, dashboard refresh, `git diff --check`를 한 번에 실행 |
| evidence matrix | `build_component_evidence_matrix.py` | current reporting coefficient별 power scope, NCU, reliability, power-state 증거를 통합 |
| current sanity audit | `audit_current_component_sanity.py` | 보고용 coefficient의 scope, 단위, 양수 CI, 계층 순서, primary/auxiliary 구분, auxiliary spread를 최종 점검 |
| result figures | `plot_component_method_visuals.py` | 문서용 SVG 생성 |

## Supporting Tools

| script | 역할 |
|---|---|
| `run_sweep.py` | 초기 feasibility/blocks/W_SM sweep 및 active runner helper |
| `run_ncu.sh` | 단일 mode NCU profiling helper |
| `plot_results.py` | raw sweep CSV용 일반 plot helper |

`run_ncu_validation.sh`는 기본적으로 `clocked_empty`, `reg_operand_only`,
`reg_mma`, `shared_scalar_load_only`, `global_l1_load_only`,
`l2_cg_load_only`, `dram_cg_load_only`만 실행한다. A100/H100의 capacity L2
비교가 필요하면 `INCLUDE_L2_CAPACITY_NCU=1`, 과거 sweep과의 비교가
필요하면 `INCLUDE_DIAGNOSTIC_NCU=1`을 명시한다.

최종 run에서는 NCU sidecar도 energy sweep과 같은 factor list로 실행한다.
WSL에서 Windows Nsight Compute를 사용할 때 설치 경로에 공백이 있으면 NCU가
`The installation directory must not contain whitespace characters`로 실패할 수 있다.
이 경우 `target/linux-desktop-...`와 `sections/`를 `/tmp/ncu2025` 같은 공백 없는
경로로 복사하고 `NCU=/tmp/ncu2025/target/.../ncu`를 지정한다. `/tmp`는 WSL 재시작 시
사라질 수 있으므로 새 세션에서 다시 확인한다.

새 플랫폼에서 실행하기 전에는 정적 readiness audit을 먼저 돌린다. 이 audit은
실제 GPU 측정이 아니라 `plan_platform_component_experiment.py`,
`preflight_gpu_support.py`, 플랫폼 문서, power API matrix가 서로 같은 profile
기준을 쓰는지 확인한다.

```bash
python3 scripts/audit_platform_power_readiness.py \
  --out-csv results/summary/platform_power_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/platform_power_readiness_audit_YYYYMMDD.md
```

이 audit이 통과해도 A100/V100/H100 coefficient가 검증된 것은 아니다. 각 노드에서
raw CSV의 power API audit, NCU path acceptance, matched-control/reliability audit을
새로 통과해야 한다. 생성된 command script는 reliability 이후
`build_strict_component_summary.py`와 `audit_strict_component_summary.py`까지 실행해서
goal readiness가 찾는 `*_strict_scope_fresh_ncu_component_coefficients_*.csv` 패키지를
만든다.

2026-07-08 기준으로 생성해 둔 persistent command package는 아래와 같다. 이 파일들은
측정 결과가 아니라 target node에서 실행할 계획이다.

| GPU | command plan | executable shell |
|---|---|---|
| A100 | `results/summary/a100_component_finalplan_20260708_command_plan.md` | `results/summary/a100_component_finalplan_20260708_commands.sh` |
| V100 | `results/summary/v100_component_finalplan_20260708_command_plan.md` | `results/summary/v100_component_finalplan_20260708_commands.sh` |
| H100 | `results/summary/h100_component_finalplan_20260708_command_plan.md` | `results/summary/h100_component_finalplan_20260708_commands.sh` |

L1처럼 treatment-control drift가 의심되는 component는 factor sweep runner 대신
paired stability runner를 사용한다. 이 runner는 각 repeat를
`clocked_empty -> treatment -> clocked_empty`로 bracket해서 nearest-control pairing의
시간/온도 거리를 줄인다.

```bash
python3 scripts/run_paired_component_stability.py \
  --execute \
  --binary ./build/a100_fp16_energy_v2 \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --active-sm 82 \
  --treatment-mode global_l1_load_only \
  --w-sm-kib 16 \
  --blocks-per-sm 16 \
  --load-repeat 4 \
  --seconds 30 \
  --repeats 8 \
  --warmup-repeats 1 \
  --output results/raw/rtx3090_l1_paired_stability_YYYYMMDD.csv \
  --matrix-csv results/raw/rtx3090_l1_paired_stability_YYYYMMDD_matrix.csv
```

Energy sweep 직후에는 power API audit을 먼저 통과시킨다. 이 단계는 NCU path
검증이 아니라 energy numerator 검증이다.

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/*_tensor.csv \
  results/raw/*_shared.csv \
  results/raw/*_l1.csv \
  results/raw/*_l2.csv \
  results/raw/*_dram.csv \
  --target-profile rtx3090 \
  --out-csv results/summary/power_api_audit.csv \
  --out-md results/summary/power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope
```

`final_candidate`는 `nvml_total_energy`와 `total_energy_mj_delta`를 사용하고,
profile의 `nvml_power_usage_semantics`가 맞는 row다. `GetPowerUsage`
fallback row는 `provisional`로 분리하고 final pJ/FLOP, pJ/bit 표에 섞지 않는다.
새 finalplan에서는 raw CSV의 `measurement_scope`가 직접 기록되어야 한다. 기존 파일처럼
source/integration에서 scope를 추론해야 하는 row는 history/provisional로 분리한다.
Audit CSV의 `measurement_scope`는 `gpu_device_total_energy_counter` 또는
`gpu_device_power_usage_fallback`으로 기록된다. H100/HGX에서 보이는 module power나
GPU memory power는 preflight metadata일 뿐이며, 이 audit의 final numerator로
허용하지 않는다.
세대별 power API 사용 가능성, `GetPowerUsage`의 instant/1초 평균 의미, module/memory
power scope, v1/v2 API 분리 기준은
`docs/platforms/power_measurement_api_matrix_ko.md`가 기준 문서다.
특히 새 플랫폼에서는 해당 문서의 `실험 전 1페이지 판정표`를 먼저 확인해 API
visibility, time semantics, measurement scope, numerator eligibility를 분리한다.

Power API audit을 통과했더라도 raw row 내부에 power-state outlier가 있을 수 있다.
예를 들어 `nvml_total_energy` 분자는 유효하지만 특정 treatment row의 평균 전력이
같은 mode/config peer보다 크게 낮으면 matched-control delta가 음수로 보일 수 있다.
이 경우 아래 audit으로 row 품질을 별도 기록한다.
power-state audit artifact에는 `average_power_W`, `group_power_median_W`,
`elapsed_s`, `net_E_J`, `temp_C`, `clock_sm_mhz`, run coordinate columns, `status`,
`coefficient_eligible`가 있어야 한다. package audit은 `status=reject`,
`coefficient_eligible=false`, 평균 전력/clock/temp evidence 누락을 실패로 본다.

```bash
python3 scripts/audit_power_state_stability.py \
  results/raw/*_tensor.csv \
  results/raw/*_shared.csv \
  results/raw/*_l1.csv \
  results/raw/*_l2.csv \
  results/raw/*_dram.csv \
  --out-csv results/summary/power_state_audit.csv \
  --out-md results/summary/power_state_audit.md
```

이 audit은 coefficient를 계산하거나 NCU path를 판정하지 않는다. `reject` row는
실험 안정성 원인 분석에 사용하고, gate를 낮춰서 통과시키는 근거로 쓰지 않는다.

Matched-control 분석에는 power-state audit CSV를 같이 넣는다. 이때
`--exclude-power-state-rejects`를 사용하면 `status=reject` 또는
`coefficient_eligible=false` 행이 treatment/control pairing 전에 제외된다.
`scripts/plan_platform_component_experiment.py`가 생성하는 finalplan shell도 이
옵션을 자동으로 포함한다.

```bash
python3 scripts/analyze_matched_control_energy.py \
  results/raw/component_energy.csv \
  --acceptance-csv results/summary/ncu_acceptance.csv \
  --ncu-summary-csv results/ncu/ncu_cache_validation_summary.csv \
  --power-state-audit-csv results/summary/power_state_audit.csv \
  --exclude-power-state-rejects \
  --require-ncu-denominator \
  --require-total-energy \
  --expected-power-semantics one_sec_average \
  --pairing nearest-control \
  --min-elapsed-s 10 \
  --min-delta-fraction 0.005 \
  --out-summary-csv results/summary/matched_control_summary.csv \
  --out-detail-csv results/summary/matched_control_detail.csv \
  --out-md results/summary/matched_control_report.md
```

Matched-control 이후에는 component reliability audit을 실행한다.

```bash
python3 scripts/audit_component_reliability.py \
  --power-audit-csv results/summary/power_api_audit.csv \
  --ncu-acceptance-csv results/summary/ncu_acceptance.csv \
  --matched-summary-csv results/summary/matched_control_summary.csv \
  --matched-detail-csv results/summary/matched_control_detail.csv \
  --expected-power-semantics one_sec_average \
  --out-csv results/summary/component_reliability_audit.csv \
  --out-md results/summary/component_reliability_audit.md \
  --fail-on-reject
```

`accepted_low_stability`와 `accepted_with_caution`은 최종 표에 넣을 수는 있지만,
보고서에서 낮은 반복 안정도나 invalid detail row 이유를 반드시 같이 적는다.
`accepted_sanity`는 DRAM streaming sanity처럼 물리 device energy로 해석하면 안 되는
항목에 사용한다.

Reliability audit에서 `accepted_with_caution`이 남으면 instability audit으로 원인을
확인한다.

```bash
python3 scripts/audit_matched_control_instability.py \
  results/summary/matched_control_detail.csv \
  --out-csv results/summary/matched_control_instability_audit.csv \
  --out-md results/summary/matched_control_instability_audit.md
```

`negative_coefficient`나 `delta_E<...`가 반복되면 NCU path가 맞더라도 component
수치 자체가 안정적이라는 뜻은 아니다. 이 경우 duration/repeats를 늘린 targeted
rerun을 수행하고, delta gate를 낮춰서 통과시키지 않는다.

Reliability artifact가 accepted이면 먼저 strict component summary를 생성한다. 이 단계는
새 coefficient를 fitting하지 않고, reliability audit의 accepted median을 복사하면서
matched-control detail, NCU acceptance, NCU summary artifact 경로를 묶는다. 따라서 수동
표 정리 중 median, 단위, power scope, NCU evidence가 어긋나는 실수를 줄인다.

```bash
python3 scripts/build_strict_component_summary.py \
  --target-profile a100 \
  --gpu-label A100 \
  --matched-summary-csv results/summary/a100_component_finalplan_YYYYMMDD_matched_control_summary.csv \
  --matched-detail-csv results/summary/a100_component_finalplan_YYYYMMDD_matched_control_detail.csv \
  --power-api-audit-csv results/summary/a100_component_finalplan_YYYYMMDD_power_api_audit.csv \
  --power-state-audit-csv results/summary/a100_component_finalplan_YYYYMMDD_power_state_audit.csv \
  --reliability-csv results/summary/a100_component_finalplan_YYYYMMDD_component_reliability_audit.csv \
  --ncu-acceptance-csv results/summary/a100_component_finalplan_YYYYMMDD_ncu_acceptance.csv \
  --ncu-summary-csv results/ncu/a100_component_finalplan_ncu_factor_YYYYMMDD/ncu_cache_validation_summary.csv \
  --out-csv results/summary/a100_strict_scope_fresh_ncu_component_coefficients_YYYYMMDD.csv \
  --out-md results/summary/a100_strict_scope_fresh_ncu_component_coefficients_YYYYMMDD.md
```

이 builder는 `nvml_total_energy`, `total_energy_mj_delta`,
`gpu_device_total_energy_counter`, profile별 `nvml_power_usage_semantics`, accepted
NCU candidate가 맞지 않으면 실패하고, power API/state audit artifact 경로도 summary
CSV에 보존한다. 즉 output CSV가 만들어졌다는 것 자체가 power measurement matrix 기준의
최소 gate를 통과했다는 뜻이다.

Strict result table을 만든 뒤에는 strict summary audit을 실행한다. 이 audit은
summary CSV의 median/status/scope가 각 component reliability artifact와 일치하는지,
matched-control detail row가 strict scope와 total-energy numerator를 쓰는지,
memory path가 `ncu_actual_exact` denominator를 갖는지, `measurement_scope`가 명시적인
`gpu_device_total_energy_counter`인지 확인한다. 또한 L2가 shared/global L1보다 작아지는
계층 오류와, L1/L2가 수십 pJ/bit로 튀는 broad order-of-magnitude 오류를 fail로 잡는다.
이 range gate는 문헌값에 맞추는 과정이 아니라 unit, NCU denominator, power source,
path attribution 오류를 막는 최소 보고 gate다.

```bash
python3 scripts/audit_strict_component_summary.py \
  --summary-csv results/summary/rtx3090_strict_scope_component_coefficients_YYYYMMDD.csv \
  --out-csv results/summary/rtx3090_strict_scope_component_summary_audit_YYYYMMDD.csv \
  --out-md results/summary/rtx3090_strict_scope_component_summary_audit_YYYYMMDD.md \
  --fail-on-fail
```

이 audit이 통과해도 새 NCU replay를 수행했다는 뜻은 아니다. NCU sidecar가 기존
좌표를 재사용한 경우에는 결과 문서에 반드시 그렇게 적는다. fresh NCU를 실제로
재수집한 경우에는 `audit_component_reliability.py` 결과와 NCU acceptance CSV를
별도 artifact로 남긴다. RTX 3090 strict+fresh NCU 예시는
`results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md`와
`results/summary/rtx3090_strict_scope_fresh_ncu_combined_acceptance_20260708.csv`다.

목표 완료 여부를 판단하기 전에는 goal readiness audit을 실행한다. 이 audit은
RTX 3090 strict 결과가 accepted인지, `docs/platforms/power_measurement_api_matrix_ko.md`
기준이 문서에 남아 있는지, 현재 노드에서 fresh NCU replay가 가능한지, A100/V100/H100
command package가 준비됐는지, 결과 패키지가 아직 빠져 있는지를 한 번에 보여준다.
플랫폼별 결과 패키지가 존재하면 단순 파일 존재만 보지 않고, component summary policy,
strict summary audit artifact, power API audit artifact, power-state audit artifact,
component reliability artifact, fresh NCU acceptance artifact를 함께 검사한다. 또한
strict summary audit CSV가 stale 파일인지 확인하기 위해 `hard_plausibility_range`,
`l2_greater_than_shared`, `l2_greater_than_l1`, `shared_l1_same_order`,
`ncu_summary_counter_schema`, `ncu_summary_coordinate_alignment`,
`ncu_evidence_summary_fields` check가 실제로 포함되어 있는지도 본다. goal readiness의 power-state artifact 검사는 package audit와
같이 `average_power_W`, `group_power_median_W`, `elapsed_s`, `temp_C`, `clock_sm_mhz`,
`W_SM_KiB`, `blocks_per_SM`, `active_SM` evidence가 있고 값이 유효한지도 확인한다.

```bash
python3 scripts/audit_component_goal_readiness.py \
  --out-csv results/summary/component_energy_goal_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/component_energy_goal_readiness_audit_YYYYMMDD.md
```

`missing` row가 있으면 목표는 아직 완료가 아니다. 예를 들어 `ncu_available_for_fresh_replay`
또는 `a100/v100/h100 platform_component_summary`가 missing이면 RTX 3090 결과가 좋아도
cross-platform component-energy 목표는 계속 진행 중으로 둔다. `platform_summary_policy`,
`platform_summary_audit_artifact`, `platform_power_api_artifacts`,
`platform_power_state_artifacts`, `platform_reliability_artifacts`,
`platform_ncu_acceptance_artifacts`가 fail이면 해당 플랫폼 결과는 존재하더라도 final
coefficient로 인정하지 않는다.
`platform_result_package_audit`가 missing이면 외부 노드 결과 패키지를 덜 가져온 상태이고,
fail이면 package audit이 power matrix, NCU, reliability, strict summary 중 하나의
위반을 발견한 상태다.
`platform_ncu_acceptance_artifacts`는 accepted 후보 존재만 보지 않고
`acceptance_reason=pass`, L1/L2 hit rate, shared/L1/L2/DRAM byte ratio 같은 path-specific
counter evidence도 검사한다.
`platform_command_package`는 실행 준비성 gate다. 이것이 pass여도 실제 component
coefficient가 존재한다는 뜻은 아니다.

외부 A100/V100/H100 노드에서 결과를 복사해 온 직후에는 platform result package
intake audit을 먼저 실행한다. 이 audit은 파일 존재뿐 아니라 preflight, raw energy row,
power API audit, power-state audit, NCU acceptance, matched-control detail,
reliability, strict summary, strict summary audit이 같은 profile/tag와 power
measurement matrix 기준을 만족하는지 한 번에 확인한다. raw energy row의
`profile_name`, `architecture_family`, `chip`, `compute_capability`, `l2_mib`,
`unified_l1_shared_kib_per_sm`, `shared_kib_per_sm`, `active_SM`도 함께 검사하므로,
A100 결과 파일에 RTX 3090/GA102 profile이 섞이면 여기서 실패해야 한다.
또한 raw row의 `elapsed_s`, `E_before_mJ`, `E_after_mJ`, `delta_E_J`, `ITER`가 양수이고
`E_after_mJ > E_before_mJ`, `delta_E_J == (E_after_mJ - E_before_mJ) / 1000`에 가까운지
확인한다. 이 검사는 final numerator가 total-energy counter delta라는 power matrix
정책을 실제 row 품질까지 연결하기 위한 것이다.
preflight markdown의 `dry_run_gpu`, `dry_run_active_sm`과 binary dry-run 출력의
`target_profile`, `chip`, `compute_capability`, L2/L1-shared/shared capacity,
`active_SM`도 같은 기준으로 검사한다. 또한 `uuid`, `driver_version`,
`power_query_fields`, `module_power_query_rc`, `power_detail_query_rc`, NCU
`chip_supported=true`와 query status가 있어야 한다. 이 값들은 coefficient 분자가
아니지만, power matrix의 platform availability 표와 H100 module/memory power 혼입
여부를 사후 확인하는 데 필요하다.
Final package preflight는 `--target-profile <profile> --strict` 결과여야 한다.
`strict=true`, `profile_gate=pass`, `cuda_compiler_gate=pass`, `ncu_gate=pass`, `dry_run_gate=pass`,
`overall=pass`, `errors=none` 중 하나라도 빠지면 package audit이 실패한다.
NCU summary에는 `l1_hit_rate_pct`, `l2_hit_rate_pct`, `l1_accesses`, `l2_accesses`,
`dram_accesses`, `l1_bytes`, `l2_bytes`, `dram_bytes`, `stall_long_scoreboard_pct`와
`W_SM_KiB`, `blocks_per_SM`, `active_SM`, `ITER` 실행 좌표가 있어야 한다.
`active_SM`은 package audit에 넘긴 target active SM과 일치해야 하며, 이 검사는
A100 결과에 RTX 3090의 82 SM 설정이 섞이는 문제를 조기에 잡기 위한 것이다.
또한 `clocked_empty`, `reg_operand_only`, `reg_mma`,
`shared_scalar_load_only`, `global_addr_only`, `global_l1_load_only`, `l2_cg_load_only`,
`dram_cg_load_only` mode를 포함해야 한다. shared/L1/L2/DRAM/Tensor 대표 mode는 해당
path counter가 양수여야 하며, 최소 1개 row는 NCU path acceptance와 같은 방향의
hit-rate sanity를 만족해야 한다. 예를 들어 `global_l1_load_only`는 L1 hit 중심,
`l2_cg_load_only`는 높은 L2 hit와 낮은 L1-bytes/L2-bytes ratio,
`dram_cg_load_only`는 낮은 L1/L2 hit와 DRAM traffic 중심이어야 한다.
`l2_load_only`는 capacity diagnostic이며 strict package 필수 mode가 아니다. Tensor pair는 `reuse_factor`가 최소 3개 이상,
memory path는 `load_repeat`가 최소 3개 이상이어야 한다.
Strict summary는 양수/단위/power scope뿐 아니라 L2가 shared/global L1보다 커야 한다는
broad hierarchy gate와, Tensor/Shared/L1/L2가 넓은 plausibility range 안에 들어오는지도
검사한다. 이 gate는 문헌값 fitting이 아니라 단위, denominator, path attribution 오류를
막기 위한 intake fail 조건이다.
NCU path acceptance 파일은 `component_candidate=...`와 `acceptance=accepted`만으로는
부족하다. accepted row에는 `acceptance_reason=pass`, mode status, L1/L2 hit rate,
shared/L1/L2/DRAM bytes, Tensor HMMA instruction count 같은 evidence column이 있어야
하며, package audit은 이 값들이 대표 path sanity와 모순되면 실패시킨다.
matched-control summary는 Tensor/Shared/Global L1/L2 component row를 모두 포함해야
한다. 각 row는 `rows > 0`, `median > 0`, `energy_source=nvml_total_energy`,
`measurement_scope=gpu_device_total_energy_counter`, profile power semantics를 만족해야
하며, memory component는 `ncu_denominator_rows > 0`과 `median_pJ_per_bit > 0`이 있어야
한다.
component reliability artifact도 strict summary의 직접 입력이므로 같은 수준으로 본다.
Tensor/Shared/Global L1/L2는 `status=accepted`, 양수 median, 기대 unit, `valid_detail_rows > 0`,
`invalid_detail_rows=0`, total-energy GPU/device scope, profile power semantics를 가져야
하며, memory component는 `ncu_denominator_rows > 0`, 모든 component는
`ncu_accepted_rows > 0`이어야 한다. `accepted_with_caution`, `accepted_low_stability`,
`accepted_sanity`는 분석용으로 남길 수 있지만 strict package gate에서는 최종 reporting
component로 통과시키지 않는다.

복사 전에 expected artifact manifest를 만들 수 있다. 이 manifest는 검증 결과가 아니라,
target node에서 실행 후 어떤 파일을 되가져와야 하는지 보여주는 transfer checklist다.

```bash
python3 scripts/write_platform_result_manifest.py \
  --target-profile a100 \
  --tag YYYYMMDD \
  --expected-active-sm 108
```

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile a100 \
  --tag YYYYMMDD \
  --expected-active-sm 108 \
  --out-csv results/summary/a100_platform_result_package_audit_YYYYMMDD.csv \
  --out-md results/summary/a100_platform_result_package_audit_YYYYMMDD.md \
  --fail-on-incomplete
```

Audit이 `missing` 또는 `fail`을 내면 gap report를 같이 만든다. 이 리포트는 결과를
새로 검증하지 않고, package audit row를 읽어서 어떤 stage로 돌아가야 하는지 설명한다.
Power API 관련 row는 `docs/platforms/power_measurement_api_matrix_ko.md`의
`nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` 기준과
profile별 `nvml_power_usage_semantics`를 함께 표시한다.

```bash
python3 scripts/summarize_platform_package_gaps.py \
  --target-profile a100 \
  --tag YYYYMMDD \
  --audit-csv results/summary/a100_platform_result_package_audit_YYYYMMDD.csv \
  --manifest-csv results/summary/a100_component_finalplan_YYYYMMDD_result_manifest.csv \
  --out-csv results/summary/a100_platform_result_package_gaps_YYYYMMDD.csv \
  --out-md results/summary/a100_platform_result_package_gaps_YYYYMMDD.md
```

여러 플랫폼의 intake 상태를 한 번에 보려면 dashboard를 생성한다. 이 dashboard도
승인 gate가 아니라 package audit, gap report, strict summary, goal readiness 상태를
모아 보여주는 요약 계층이다.

```bash
python3 scripts/build_platform_intake_dashboard.py \
  --tag YYYYMMDD \
  --out-csv results/summary/platform_component_intake_dashboard_YYYYMMDD.csv \
  --out-md results/summary/platform_component_intake_dashboard_YYYYMMDD.md
```

`scripts/plan_platform_component_experiment.py`가 생성하는 shell은 energy sweep 전에
`audit_power_api_measurements.py --self-test`를 실행하고, result manifest,
package audit, gap report, intake dashboard, `audit_component_goal_readiness.py --self-test`,
full goal readiness audit까지 후처리로 실행한다. Package audit이 실패해도 gap/dashboard/
goal readiness artifact를 남기고 마지막에 package audit exit code로 종료한다.
로컬 저장소의 `scripts/run_local_readiness_checks.sh`도 A100/V100/H100 result manifest,
package audit, gap report를 매번 다시 생성한 뒤 dashboard를 만들기 때문에, 외부 결과
파일을 복사한 직후에는 이 wrapper만 실행해도 첫 open stage와 다음 명령이 최신 상태로
정리된다.
기본 active SM 기준은 A100=108, V100=80, H100=132이며, runtime/preflight 값이 다르면
`A100_ACTIVE_SM=<n>`, `V100_ACTIVE_SM=<n>`, `H100_ACTIVE_SM=<n>`로 override한다.

MIG, partition, H100 PCIe/SXM 차이처럼 preflight의 runtime SM 수가 기본 profile 값과
다르면 command plan을 `--active-sm <runtime SM count>`로 다시 만들고, package audit도
같은 값을 `--expected-active-sm`으로 넘긴다. runtime `sm_count`까지 exact check가
필요하면 `--expected-sm-count <runtime SM count>`를 추가한다.

이 audit이 `missing`이면 아직 결과 파일을 덜 가져온 것이고, `fail`이면 결과가 있더라도
`docs/platforms/power_measurement_api_matrix_ko.md`의 final numerator 기준이나 NCU/path
기준을 만족하지 못한 것이다. 통과 후에 goal readiness audit을 다시 실행한다.

Package gate 자체를 수정한 뒤에는 mock self-test도 실행한다. 이 test는 실제 GPU나 NCU를
사용하지 않고, 최소 strict summary/audit CSV를 만들어 L2/L1 역전, 50 pJ/bit급
out-of-range coefficient, stale strict audit CSV, strict summary와 raw CSV 양쪽의 A100
power semantics 오류, 그리고 `legacy_get_power_usage_integral` fallback numerator를
package audit이 실패시키는지 확인한다. 또한 NCU summary의 `l1_hit_rate_pct` 같은
cache/access 필수 컬럼이 빠지거나 `l2_cg_load_only`의 L2 byte counter가 0이면
실패해야 하며, L1/L2/DRAM 대표 mode의 hit-rate sanity가 깨져도 실패해야 한다.
raw energy row의 `delta_E_J`가 0이거나 energy counter 전후 차분과 맞지 않는 경우도
실패해야 한다.
matched-control summary에서 L2 component가 빠지거나, memory component의 NCU
denominator row가 0이거나, Tensor median이 0이면 실패해야 한다.
component reliability에서 accepted가 아닌 status, invalid detail row, memory component의
NCU denominator 0, H100 module scope 혼입도 실패해야 한다.
preflight에서 driver version, UUID, module power query status, NCU chip support가 빠져도
실패해야 한다.
power-state audit에서 평균 전력 evidence column이 빠지거나 reject row, 평균 전력 0 row가
있어도 실패해야 한다.
NCU path acceptance CSV에서 evidence column이 빠지거나 accepted row의 counter가
accepted 판정과 맞지 않아도 실패해야 한다.
새 플랫폼 self-test에는 A100 NCU summary가 `active_SM=82`처럼 RTX 3090 좌표를
가져온 경우도 포함되어야 한다.

```bash
scripts/run_local_readiness_checks.sh
```

개별 self-test를 따로 돌려야 할 때는 아래 명령을 사용한다.

```bash
python3 scripts/preflight_gpu_support.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/selftest_platform_package_gates.py
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/write_platform_result_manifest.py --self-test
python3 scripts/summarize_platform_package_gaps.py --self-test
python3 scripts/build_platform_intake_dashboard.py --self-test
```

| env | 예시 | 의미 |
|---|---|---|
| `TENSOR_REUSE_FACTORS` | `1,2,4,8,16` | `reg_operand_only`, `reg_mma` reuse sweep |
| `MEMORY_LOAD_REPEATS` | `1,2,4,8,16` | shared/L1/L2 load_repeat sweep |
| `DRAM_LOAD_REPEATS` | `1,4,16` | DRAM sanity load_repeat sweep |
| `DRY_RUN_NCU` | `1` | NCU 실행 없이 case manifest만 생성 |

대표 조건만 빠르게 확인하려면 세 list를 모두 `4`로 제한한다. 그 결과는
preflight/provisional로 보고하고, final coefficient에는 factor list sidecar를
우선한다.

## Legacy Archive

아래 흐름은 현재 final component coefficient 산출의 primary 경로가 아니다.

```text
archive/legacy_20260707/scripts/
```

보관된 대표 흐름:

- `run_component_pairs.py`, `analyze_component_pairs.py`
- `fit_component_energy_model.py`, `estimate_component_energy.py`
- `analyze_reference_aligned_memory.py`, `join_ncu_summary.py`
- `run_register_footprint_sweep.py`, `analyze_register_footprint.py`, `inspect_register_footprint.py`

새 실험/보고서에는 active finalplan flow를 우선 사용한다.
