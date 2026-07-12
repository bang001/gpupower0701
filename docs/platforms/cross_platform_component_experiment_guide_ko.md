# Cross-Platform Component Energy 실험 가이드

작성일: 2026-07-06, updated 2026-07-11

## 1. 현재 코드와 실험 내용 요약

이 저장소는 CUDA/NVML 기반 microbenchmark로 FP16 WMMA `m16n16k16` logical op를 실행하고, board-level 또는 GPU-level energy delta를 측정한다. component 분리는 순수 회로 에너지를 직접 읽는 방식이 아니라, NCU로 경로를 검증한 microbenchmark들을 matched-control 차분/회귀로 비교하는 방식이다. GPU 세대별 power/energy API 의미와 제약은 [power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)를 함께 따른다.

현행 final package는 treatment path만 검증하지 않는다.
`--require-control-ncu-acceptance`를 사용해 Tensor의 `reg_operand_only`와 Global
L1/L2/DRAM의 `global_addr_only`도 treatment와 같은 좌표에서 NCU `accepted`인지
확인한다. control evidence가 없거나 오염되면 coefficient를 만들지 않는다.

현재 채택 가능한 component 후보는 다음이다.

| Component/path | numerator | control | denominator | 해석 |
|---|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | FLOP | no-MMA register/control 대비 WMMA 추가분 |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes + access count | shared-memory scalar instruction path |
| Global L1 hit path | `global_l1_load_only` | `global_addr_only` | NCU L1 bytes + L1/L2/DRAM access count | 같은 주소/loop control 대비 global L1-hit path |
| L2 hit path | `l2_cg_load_only` | `global_addr_only` | NCU L2 bytes + L1/L2/DRAM access count | L1-bypassed L2-hit transaction path |
| DRAM streaming sanity | `dram_cg_load_only` | `global_addr_only` | NCU DRAM bytes + DRAM access count | hierarchy sanity check |

V100/A100/H100의 DRAM pair는 동일 ITER를 강제한다. `dram_cg_load_only`의 목표
측정시간과 `global_addr_only`의 control-duration floor를 각각 calibration하고, 두
candidate 중 큰 ITER를 treatment/control 모두에 적용한다. 이후
`delta_E = net_E_treatment - net_E_control`로 직접 차분한다. 같은 시간 동안 서로
다른 ITER를 실행한 control power를 treatment 시간으로 늘려 빼는 duration-scaled
DRAM 계산은 cross-platform coefficient에서 허용하지 않는다.

보고서에서는 `register`, `L1`, `L2`, `DRAM`이라고 줄여 쓰더라도 반드시 **effective microbenchmark coefficient**라고 명시한다. NVML board energy에는 scheduler, issue, LSU, cache controller, memory controller, clock/power-state 변화가 함께 들어간다.

## 2. 공통 실행 순서

모든 플랫폼에서 순서는 동일하다.

| 단계 | 명령/도구 | 산출물 | 채택 기준 |
|---|---|---|---|
| static readiness | `scripts/audit_platform_power_readiness.py` | `results/summary/platform_power_readiness_audit_*.md` | profile, power API 의미, 문서, 생성 command plan 정합성 확인 |
| preflight | `scripts/preflight_gpu_support.py` | `results/summary/*_preflight.md` | profile, CC, SM 수, NVML, CUDA target, NCU 상태 기록 |
| energy sweep | `scripts/run_component_regression_sweep.py` | `results/raw/*_component_finalplan_*.csv` | NCU 없이 실행, `seconds>=10`, `repeats>=5` 권장 |
| power API audit | `scripts/audit_power_api_measurements.py` | `results/summary/*_power_api_audit.md` | `nvml_total_energy`, integration, profile power semantics 확인 |
| power-state audit | `scripts/audit_power_state_stability.py` | `results/summary/*_power_state_audit.md` | raw row 평균 전력/endpoint power outlier 확인 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | `results/ncu/*/ncu_cache_validation_summary.csv` | chip별 metric availability를 먼저 걸러낸 뒤 hit/access/bytes/stall/spill/achieved occupancy/launch resource 확인 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | `results/summary/*_ncu_acceptance.md` | accepted mode만 coefficient 후보 |
| matched-control | `scripts/analyze_matched_control_energy.py` | `results/summary/*_matched_control_report.md` | NCU actual-byte denominator 사용 |
| component reliability | `scripts/audit_component_reliability.py` | `results/summary/*_component_reliability_audit.md` | power/NCU/계수 안정성을 결합한 최종 verdict |
| instability/root-cause | `scripts/audit_matched_control_instability.py` | `results/summary/*_matched_control_instability_audit.md` | weak-signal/negative row 원인과 follow-up 조건 |
| strict summary build | `scripts/build_strict_component_summary.py` | `results/summary/*_strict_scope_fresh_ncu_component_coefficients_*.csv` | accepted reliability와 NCU artifact를 묶어 보고용 component summary 생성, component별 NCU path evidence를 표에 직접 노출 |
| strict summary audit | `scripts/audit_strict_component_summary.py` | `results/summary/*_strict_scope_component_summary_audit.md` | curated strict summary와 reliability artifact/detail row/power scope/NCU denominator, NCU counter schema/coordinate/path-evidence 노출 일치 확인 |
| platform package audit | `scripts/audit_platform_result_package.py` | `results/summary/*_platform_result_package_audit_*.md` | 단일 profile/tag 결과 패키지의 strict profile/CUDA compiler/NCU preflight, raw metadata, active SM, power, reliability, strict summary gate 검수 |
| report | 수동/문서화 | `results/summary/*_report_ko.md` | 단위 포함 표, rejected row 명시 |

Preflight와 raw CSV에서는 아래 power 측정 metadata를 반드시 확인한다.

| 항목 | 단위 | 해석 |
|---|---:|---|
| `nvml_total_energy_supported` | boolean | total energy mJ counter 사용 가능 여부 |
| `energy_source` | string | `nvml_total_energy` 우선, fallback이면 별도 표시 |
| `energy_integration_method` | string | `total_energy_mj_delta` 또는 `endpoint_power_trapezoid` |
| `nvml_power_usage_semantics` | string | V100/A100은 `instant`, RTX 3090/H100은 `one_sec_average` profile |
| `measurement_scope` | string | `gpu_device_total_energy_counter`만 final 후보, fallback/module/memory scope는 분리 |
| `power_before_mw`, `power_after_mw` | mW | fallback 또는 진단용 endpoint power |
| `sm_clock_mhz`, `mem_clock_mhz`, `temp_c` | MHz, Celsius | clock/thermal 상태 |
| preflight power-scope excerpt | text | H100/HGX module/memory power, power smoothing/profile 노출 여부 |

세대별 power API 해석은 실험 성공 여부와 별개로 coefficient 채택 조건이다.
중요한 구분은 "플랫폼에서 보이는 API"와 "최종 pJ/FLOP 또는 pJ/bit 분자로 채택할
수 있는 API"가 다르다는 점이다.

새 플랫폼 보고서에는 반드시
[power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)의
`빠른 결론: 세대별 Power API 해석`, `API 사용 등급`,
`0.A.4.1 플랫폼별 보고서에 넣을 Power API availability 표`를 채워 넣는다. 이 표는
GPU 세대별 API 지원 여부를 자랑하기 위한 표가 아니라, 최종 coefficient의 분자가
어떤 telemetry scope에서 왔는지 검증하기 위한 표다. 특히 A100 결과가 좋지 않을 때
RTX 3090 기준 좌표가 섞였는지 보기 전에 `energy_source`,
`energy_integration_method`, `measurement_scope`, `nvml_power_usage_semantics`가
A100/GA100 기준과 맞는지 먼저 확인한다.

먼저 아래 네 가지 질문을 분리해서 답한다.

| 질문 | 확인 위치 | 통과 조건 |
|---|---|---|
| 이 API가 보이는가? | preflight, raw CSV, `nvidia-smi -q -d POWER` | 호출 성공 여부를 기록한다. 성공만으로 final 채택은 아니다 |
| 값의 시간 의미는 무엇인가? | `nvml_power_usage_semantics` | V100/A100은 `instant`, RTX 3090/H100은 `one_sec_average` |
| 값의 scope는 무엇인가? | `measurement_scope`, H100 power-scope preflight | GPU/device total energy, fallback, module, GPU memory를 구분 |
| final numerator로 쓸 수 있는가? | power API audit | `nvml_total_energy` + `total_energy_mj_delta` + profile semantics 일치 |

| GPU | 보일 수 있는 power/energy API | fallback `GetPowerUsage` 의미 | final numerator로 채택 | 실험자가 수정/확인할 점 |
|---|---|---|---|---|
| RTX 3090 / GA102 | total energy counter, `GetPowerUsage`, `power.draw.*` runtime 확인 | 1초 평균 power | `nvml_total_energy` + `total_energy_mj_delta`만 final | fallback row는 final 표에서 제외하고, WSL/driver field 노출 차이를 preflight에 기록 |
| V100 / GV100 | total energy counter 기대, `GetPowerUsage` fallback | instantaneous power | total energy 성공 + GV100 NCU path accepted | CUDA 12.x `compute_70`, `sm_70`, `NCU_CHIP=gv100`, total energy support를 같이 확인 |
| A100 / GA100 | total energy counter 기대, `GetPowerUsage` fallback | instantaneous power. GA100은 Ampere 평균-power 규칙의 예외 | total energy 성공 + A100 capacity 재설정 + NCU accepted | MIG/full GPU, runtime SM 수, power limit, A100 capacity에 맞춘 W_SM을 기록 |
| H100 / GH100 | total energy counter, GPU power, module power, GPU memory power field 가능 | 1초 평균 power | GPU/device total energy만 final numerator | module power와 GPU memory power를 coefficient numerator로 섞지 않음 |

Power API gate는 final coefficient 채택 여부를 직접 결정한다.

| 상태 | 조건 | 결과 해석 |
|---|---|---|
| final candidate | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, profile power semantics 일치 | component coefficient 표에 포함 가능 |
| provisional | total energy counter가 없고 `legacy_get_power_usage_integral`만 존재 | fallback 표로 분리. RTX 3090/H100은 1초 평균 window 때문에 짧은 kernel 해석 금지 |
| reject | profile과 `nvml_power_usage_semantics` 불일치, source 혼합, non-GPU/device scope, NCU rejected | 최종 pJ/FLOP 또는 pJ/bit 계산에서 제외 |

GPU 세대별로 `nvmlDeviceGetPowerUsage`의 의미가 다르다. V100/GV100과 A100/GA100은 instantaneous semantics로 기록하고, RTX 3090/GA102와 H100/GH100은 one-second average semantics로 기록한다. 단, 이 차이는 fallback power API의 의미일 뿐이다. 최종 energy numerator는 가능한 한 `nvmlDeviceGetTotalEnergyConsumption`의 mJ counter 차분이어야 한다. H100/HGX에서 보이는 module power와 GPU memory power는 preflight metadata로만 남기고, L1/L2/DRAM pJ/bit의 분자에는 넣지 않는다.

새 플랫폼 결과가 좋지 않을 때는 component kernel부터 의심하기 전에 power API gate를
먼저 본다. 예를 들어 A100 결과인데 `nvml_power_usage_semantics=one_sec_average`로
기록되었거나, `measurement_scope`가 module/memory power로 섞였거나,
`energy_source=legacy_get_power_usage_integral`만 남아 있으면 NCU hit rate가 좋아도
coefficient는 final이 아니다. 이 경우 설정을 고쳐 energy run을 다시 수행한다.
세대별 대표 failure pattern과 수정 지시는
[power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)의
`0.A.5 세대별 failure pattern과 수정 지시`를 따른다.

새 노드에서 실행하기 전에는 정적 readiness audit을 먼저 돌린다. 이 audit은
RTX 3090/V100/A100/H100 profile이 `plan_platform_component_experiment.py`,
`preflight_gpu_support.py`, 플랫폼 문서, power API matrix에서 같은 의미로 쓰이는지
확인한다. 현재 통과 결과는
`results/summary/platform_power_readiness_audit_20260708.md`에 있다. 단, 이것은
실제 GPU 측정이나 NCU 검증을 대체하지 않는다.

Power-state audit은 power API gate와 다르다. Power API gate가 numerator API의
의미를 검사한다면, power-state audit은 같은 mode/config 반복 row 안에서 특정
row의 평균 전력, endpoint power, 온도, clock이 튀었는지 확인한다. `reject` row가
있으면 coefficient를 억지로 통과시키지 말고 해당 조건을 재측정한다. 표준
`plan_platform_component_experiment.py` 생성 shell은 matched-control 단계에서
`--power-state-audit-csv`와 `--exclude-power-state-rejects`를 함께 사용해 reject row를
treatment/control pairing 전에 제외한다.

Energy sweep 이후에는 NCU를 돌리기 전에 아래 audit을 먼저 통과시킨다.

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/a100_component_finalplan_YYYYMMDD_tensor.csv \
  results/raw/a100_component_finalplan_YYYYMMDD_shared.csv \
  results/raw/a100_component_finalplan_YYYYMMDD_l1.csv \
  results/raw/a100_component_finalplan_YYYYMMDD_l2.csv \
  results/raw/a100_component_finalplan_YYYYMMDD_dram.csv \
  --target-profile a100 \
  --out-csv results/summary/a100_component_finalplan_YYYYMMDD_power_api_audit.csv \
  --out-md results/summary/a100_component_finalplan_YYYYMMDD_power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope
```

이 audit이 실패하면 NCU 결과가 좋아도 final coefficient로 쓰지 않는다. 먼저
`energy_source`, `energy_integration_method`, `nvml_power_usage_semantics`,
`measurement_scope`, 측정 시간, clock/power limit 상태를 고쳐서 energy run을 다시
수행한다. 새 finalplan에서는 raw CSV에 `measurement_scope` 컬럼이 직접 있어야 하며,
기존 파일처럼 source/integration에서 scope를 추론한 row는 final 후보로 보지 않는다.

Matched-control 이후에는 component reliability audit을 실행한다. 이 단계는 power
audit, NCU acceptance, matched-control summary/detail을 결합해 component별 상태를
`accepted`, `accepted_with_caution`, `accepted_low_stability`, `accepted_sanity`,
`reject`로 나눈다. 최종 보고서의 component 표에는 이 verdict와 caution/reject reason을
같이 적는다.

`accepted_with_caution` 또는 invalid detail row가 남으면 instability/root-cause audit을
확인한다. NCU path가 accepted인데 `negative_coefficient`나 `delta_E<...`가 나오면
cache path 실패라기보다 board-level treatment-control signal이 noise floor에 걸렸거나
control drift에 민감한 상태로 해석한다. 이때는 gate를 낮추지 말고 seconds/repeats를
늘린 targeted rerun을 수행한다.

Reliability audit 이후에는 strict component summary를 자동 생성한다. 이 단계는 새로
계수를 계산하지 않고, accepted reliability median과 matched-control/NCU artifact 경로를
하나의 보고용 CSV로 묶는다. Builder는 power measurement matrix 기준의
`nvml_total_energy`, `total_energy_mj_delta`, `gpu_device_total_energy_counter`,
profile별 `nvml_power_usage_semantics`, accepted NCU candidate를 만족하지 못하면
실패한다. 또한 power API/state audit artifact 경로를 summary CSV에 보존해 최종 분자
정책과 row quality를 나중에 역추적할 수 있게 한다. 여러 NCU summary CSV를 입력한
경우에는 component별 strict matched-control detail 좌표를 실제로 덮는 NCU artifact만
해당 row에 연결한다. 예를 들어 Tensor strict row가 `blocks/SM=16`이라면 과거
`blocks/SM=4` Tensor sidecar는 해당 Tensor row의 증거 artifact로 남기지 않는다.

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

Strict component summary를 만든 뒤에는 strict summary audit을 실행한다. 이 단계는
summary CSV가 실제 reliability artifact와 일치하는지, matched-control detail row가
`gpu_device_total_energy_counter` scope와 total-energy numerator를 쓰는지, memory path가
exact NCU denominator를 갖는지 확인한다. 또한 strict summary가 참조하는 NCU summary
artifact에 L1/L2 hit rate, L1/L2/DRAM access count, L1/L2/DRAM byte traffic, Tensor
HMMA instruction, long-scoreboard stall 컬럼과 component-relevant OK mode row가
있는지도 검증한다. 이 OK mode row는 strict matched-control detail의 `mode`,
`W_SM_KiB`, `blocks_per_SM`, `active_SM`, `reuse_factor`, `load_repeat`, `store_repeat`
좌표와도 일치해야 한다. L2가 shared/global L1보다 작아지는 hierarchy 오류와
Tensor/Shared/L1/L2 coefficient가 broad plausibility range 밖으로 튀는
order-of-magnitude 오류도 fail로 잡는다.
또한 strict coefficient table 자체에 `ncu_evidence_summary_fields`가 있어야 한다.
이 필드는 path-relevant hit/access/byte/stall evidence와 caveat를 row에 노출한다.
Shared scalar path에서는 shared-memory byte/access evidence가 주 증거이며 global
L1/L2 hit-rate counter는 background context로 분리해서 읽는다.

```bash
python3 scripts/audit_strict_component_summary.py \
  --summary-csv results/summary/your_strict_scope_component_coefficients.csv \
  --out-csv results/summary/your_strict_scope_component_summary_audit.csv \
  --out-md results/summary/your_strict_scope_component_summary_audit.md \
  --require-path-specific-cache-evidence \
  --fail-on-fail
```

새 A100/V100/H100 package와 새로 생성하는 RTX 3090 package는 위 플래그를
제거하지 않는다. 플래그가 없는 기본 경로는 path-specific alias를 수집하기
전에 생성된 기존 RTX 3090 aggregate-only artifact를 재감사하는 호환 용도로만
남겨 둔다. 이 호환 경로로 새 target-node 결과를 final로 승격하면 안 된다.

이 audit은 fresh NCU replay를 의미하지 않는다. 기존 NCU sidecar를 재사용했다면
보고서에 그 사실을 별도 제한으로 적어야 한다.

외부 노드에서 결과를 복사해 온 직후에는 platform result package intake audit을 먼저
실행한다. 이 audit은 파일 존재만이 아니라 preflight, raw energy row, power API audit,
power-state audit, NCU acceptance, matched-control detail, reliability, strict summary,
strict summary audit이 같은 profile/tag와 power measurement matrix 기준을 만족하는지
한 번에 확인한다. 또한 raw CSV의 `profile_name`, `architecture_family`, `chip`,
`compute_capability`, `l2_mib`, `unified_l1_shared_kib_per_sm`,
`shared_kib_per_sm`, `active_SM`을 target profile과 대조한다. 따라서 A100 노드에서
실험했다고 보고했지만 raw row가 RTX 3090/GA102/6 MiB L2/128 KiB L1-shared profile로
남아 있으면 이 단계에서 실패해야 한다.
preflight markdown도 검사 대상이다. `dry_run_active_sm`, dry-run 출력의
`dry_run_gpu`, `target_profile`, `chip`, `compute_capability`, `target_l2_MiB`,
`target_unified_L1_shared_KiB_per_SM`, `target_shared_KiB_per_SM`, `active_SM`이
target profile과 맞아야 한다.
NCU summary도 파일 존재만으로는 부족하다. package audit는 `l1_hit_rate_pct`,
`l2_hit_rate_pct`, `l1_accesses`, `l2_accesses`, `dram_accesses`, `l1_bytes`,
`l2_bytes`, `dram_bytes`, `stall_long_scoreboard_pct` 컬럼이 있고, shared/L1/L2/DRAM/Tensor
대표 mode에서 해당 path counter가 양수인지 확인한다. 또한 `clocked_empty`,
`reg_operand_only`, `reg_mma`, `shared_scalar_load_only`, `global_l1_load_only`,
`l2_cg_load_only`, `dram_cg_load_only`가 NCU summary에 모두 있어야 한다. `global_addr_only`는
memory pair의 no-input-load control이며 global-load L1 request byte 0을 확인한다. SMID verification
atomic은 L2 sector에 보일 수 있으므로 L2 sector 0을 요구하지 않는다. strict L2 evidence에는
`l2_load_only`를 요구하지 않는다.
Tensor pair는 `reuse_factor`
최소 3점 이상, memory path는 `load_repeat` 최소 3점 이상을 포함해야 한다.
Strict summary audit CSV에는 `ncu_summary_counter_schema`,
`ncu_summary_coordinate_alignment`, `ncu_evidence_summary_fields`,
`hard_plausibility_range`, `l2_greater_than_shared`,
`l2_greater_than_l1`, `shared_l1_same_order` check가 포함되어야 한다. 이 check가 없으면
이전 버전 audit artifact를 재사용한 것으로 보고 package audit에서 실패시킨다.

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile a100 \
  --tag YYYYMMDD \
  --expected-active-sm 108 \
  --out-csv results/summary/a100_platform_result_package_audit_YYYYMMDD.csv \
  --out-md results/summary/a100_platform_result_package_audit_YYYYMMDD.md \
  --fail-on-incomplete
```

이 audit에서 `missing`은 아직 artifact를 덜 가져왔다는 뜻이고, `fail`은 가져온
artifact가 final numerator, power-state, NCU denominator/path, reliability, strict
summary 기준 중 하나를 위반했다는 뜻이다. `fail` row가 있으면 goal readiness audit
전에 해당 플랫폼 실험을 수정하거나 재실행한다.

Package audit이 `missing` 또는 `fail`을 내면 gap report를 함께 만든다. 이 report는
검증을 대체하지 않고, 실패 row를 preflight/raw energy/power API/NCU/matched-control/
strict summary stage로 나누어 원인과 다음 조치를 설명한다. 특히 power API 관련 row는
[power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)의
`nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` 정책과
profile별 `nvml_power_usage_semantics` 기준으로 해석한다.

```bash
python3 scripts/summarize_platform_package_gaps.py \
  --target-profile a100 \
  --tag YYYYMMDD \
  --audit-csv results/summary/a100_platform_result_package_audit_YYYYMMDD.csv \
  --manifest-csv results/summary/a100_component_finalplan_YYYYMMDD_result_manifest.csv \
  --out-csv results/summary/a100_platform_result_package_gaps_YYYYMMDD.csv \
  --out-md results/summary/a100_platform_result_package_gaps_YYYYMMDD.md
```

여러 플랫폼을 비교할 때는 dashboard를 생성한다. Dashboard는 RTX 3090 local strict
evidence와 V100/A100/H100 외부 package 상태를 한 표로 보여준다. 단, 이 문서도 승인
gate가 아니라 package audit과 strict summary audit 결과를 읽기 쉽게 모은 것이다.

```bash
python3 scripts/build_platform_intake_dashboard.py \
  --tag YYYYMMDD \
  --out-csv results/summary/platform_component_intake_dashboard_YYYYMMDD.csv \
  --out-md results/summary/platform_component_intake_dashboard_YYYYMMDD.md
```

MIG, partition, H100 PCIe/SXM 차이처럼 runtime SM 수가 기본 profile의 full SM 수와
다르면 preflight 값을 기준으로 command plan을 `--active-sm <runtime SM count>`로 다시
생성한다. 이때 package audit에도 같은 값을 `--expected-active-sm`으로 넘긴다. raw
CSV의 runtime `sm_count`까지 exact check하려면 `--expected-sm-count <runtime SM count>`를
추가한다.

마지막으로 전체 목표 완료 여부는 goal readiness audit으로 확인한다. 이 audit은
RTX 3090 fresh NCU evidence와 A100/V100/H100 결과 패키지를 같은 기준으로 점검한다.
새 플랫폼 결과 패키지가 있더라도 아래 항목을 모두 통과해야 final 후보로 본다.

| goal readiness check | 의미 | fail이면 할 일 |
|---|---|---|
| `platform_command_package` | A100/V100/H100 실행용 finalplan shell/markdown이 있고 power API, power-state, NCU, reliability, strict summary gate를 포함하는지 확인 | `scripts/plan_platform_component_experiment.py`로 target profile command package를 다시 생성하고 shell을 검토 |
| `platform_summary_policy` | component summary의 Tensor/Shared/L1/L2가 `accepted`, 양수 median, 올바른 단위, `nvml_total_energy`, `total_energy_mj_delta`, `gpu_device_total_energy_counter`, profile별 power semantics, same-coordinate NCU row, path-relevant NCU evidence field를 만족하고, Register/DRAM 같은 unexpected final row가 없는지 확인 | summary를 reliability artifact에서 다시 만들거나 energy/power API/NCU run을 재실행 |
| `platform_summary_audit_artifact` | strict summary audit CSV가 존재하고 0 fail / 0 warning이며 `ncu_summary_counter_schema`, `ncu_summary_coordinate_alignment`, `ncu_evidence_summary_fields`를 포함하는지 확인 | `scripts/audit_strict_component_summary.py`를 다시 실행하고 실패 row를 수정 |
| `platform_power_api_artifacts` | power API audit CSV가 존재하고 모든 row가 `final_candidate`, `nvml_total_energy`, `total_energy_mj_delta`, `gpu_device_total_energy_counter`, profile별 semantics와 일치하는지 확인 | `scripts/audit_power_api_measurements.py` 재실행 후 strict summary를 다시 build |
| `platform_power_state_artifacts` | power-state audit CSV가 존재하고 `reject` 또는 `coefficient_eligible=false` row가 없으며 `average_power_W`, `group_power_median_W`, `elapsed_s`, `temp_C`, `clock_sm_mhz`, run 좌표 evidence가 유효한지 확인 | `scripts/audit_power_state_stability.py` 재실행, reject row 제외 후 matched-control과 strict summary를 다시 build |
| `platform_reliability_artifacts` | component reliability CSV가 존재하고 reject 없이 accepted component를 포함하는지 확인 | `scripts/audit_component_reliability.py` 재실행 |
| `platform_ncu_acceptance_artifacts` | fresh NCU acceptance가 tensor/no-MMA control/address control/shared/L1/L2 path를 accepted로 덮고 `acceptance_reason=pass`, L1/L2 hit rate, shared/L1/L2/DRAM byte ratio evidence가 path별 threshold를 만족하는지 확인 | `scripts/run_ncu_validation.sh`와 `scripts/analyze_ncu_path_acceptance.py`를 해당 platform 좌표로 재실행 |
| `platform_result_package_audit` | 단일 profile/tag 결과 패키지 audit이 0 fail / 0 missing / 0 warning인지 확인 | `scripts/audit_platform_result_package.py` 재실행, missing이면 artifact 복사, fail이면 해당 stage 재실행 |

```bash
python3 scripts/audit_component_goal_readiness.py \
  --ncu "$(command -v ncu)" \
  --out-csv results/summary/component_energy_goal_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/component_energy_goal_readiness_audit_YYYYMMDD.md
```

로컬에서 코드/문서/요약 artifact가 서로 맞는지 한 번에 확인하려면 wrapper를 사용한다.

```bash
TAG=YYYYMMDD scripts/run_local_readiness_checks.sh
```

이 wrapper는 self-test, platform power readiness, RTX 3090 strict summary audit,
goal readiness audit, intake dashboard refresh, `git diff --check`를 실행한다. 실제
A100/V100/H100 측정 run을 대신하지는 않는다. 따라서 새 플랫폼 raw/power/NCU 결과
패키지가 아직 없으면 wrapper가 통과해도 goal readiness에는 missing 항목이 남아야 한다.

새 플랫폼에서는 먼저 표준 명령을 생성한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5
```

`--binary`를 생략하면 generator가 profile별 기본 경로를 선택한다. 기본값은
`v100 -> ./build-v100/a100_fp16_energy_v2`,
`a100 -> ./build-a100/a100_fp16_energy_v2`,
`h100 -> ./build-h100/a100_fp16_energy_v2`다. RTX 3090용 `./build` binary를
A100/V100/H100 command package에 섞으면 package audit에서 실패해야 한다.

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

Generated package는 긴 energy sweep 전에 실제 hardware-counter permission probe를
수행한다. `ERR_NVGPUCTRPERM`이면 기본 `NCU_AUTO_SUDO=1` 정책으로 같은 profile을
`sudo -E`로 한 번 재시도하고 `ncu_permission_mode.txt`를 남긴다. 관리자에게
non-admin counter 접근을 열어 달라고 요청하는 것이 장기적으로 우선이다. 자동 retry를
끄려면 `NCU_AUTO_SUDO=0`, 처음부터 sudo를 사용하려면 아래와 같이 실행한다. 이 옵션은
NCU 경로에만 적용되며 NVML energy sweep은 분리된다.

```bash
NCU_USE_SUDO=1 bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_$(date +%Y%m%d)_commands.sh
NCU_USE_SUDO=1 bash results/summary/h100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

sudo가 CUDA/Nsight Compute 경로를 지우는 환경이면 다음처럼 NCU binary와 sudo
동작을 명시한다.

```bash
NCU_BIN="$(command -v ncu)" NCU_USE_SUDO=1 NCU_SUDO="sudo -E" \
  bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

`--target-profile`은 `rtx3090`, `a100`, `v100`, `h100`을 지원한다.
생성된 script는 power API policy self-test, energy sweep, power API audit, NCU sidecar, path acceptance,
matched-control, reliability, instability audit, strict summary build, strict summary
audit, platform package audit, result manifest, gap report, intake dashboard, goal
readiness self-test와 full goal readiness audit까지 포함한다. Package audit이
실패해도 gap/dashboard/goal readiness artifact를 남긴 뒤 package audit exit code로
종료한다. 따라서 run이 끝난 뒤에는
`results/summary/<profile>_strict_scope_fresh_ncu_component_coefficients_YYYYMMDD.csv`,
대응 strict summary audit, platform package audit, gap report, goal readiness audit을
함께 확인한다.

2026-07-08 기준으로 검토 가능한 command package도 생성해 두었다.

| GPU | command plan | executable shell |
|---|---|---|
| A100 | `results/summary/a100_component_finalplan_20260708_command_plan.md` | `results/summary/a100_component_finalplan_20260708_commands.sh` |
| V100 | `results/summary/v100_component_finalplan_20260708_command_plan.md` | `results/summary/v100_component_finalplan_20260708_commands.sh` |
| H100 | `results/summary/h100_component_finalplan_20260708_command_plan.md` | `results/summary/h100_component_finalplan_20260708_commands.sh` |

V100 노드 작업을 다른 작업자나 에이전트에게 전달할 때는 실행 프롬프트를 [v100_experiment_prompt_ko.md](prompts/v100_experiment_prompt_ko.md)에 따로 분리해 두었다. 이 프롬프트는 `sm_70`, `NCU_CHIP=gv100`, V100 L2/shared capacity, NCU path acceptance 기준을 명시해서 RTX 3090/A100 좌표가 섞이는 문제를 줄이기 위한 것이다.

## 3. 플랫폼별 핵심 차이

| GPU | build arch | default SMs | register/SM | L1/shared capacity | L2 | memory | 주요 실험 차이 |
|---|---:|---:|---:|---:|---:|---|---|
| RTX 3090 / GA102 | sm_86 | 82 | 256 KiB급 | 128 KiB combined, 100 KiB shared allocation profile | 6 MiB | GDDR6X | energy B8/B16, strict NCU B8 계획. 기존 accepted 실측 package는 B16 targeted rerun을 사용 |
| V100 / GV100 | sm_70 | 80 | 256 KiB급 | 128 KiB combined, 96 KiB shared allocation | 6 MiB | HBM2 | CUDA 12.x `compute_70` compiler와 Volta NCU 지원 확인 필수, L2는 CG path 우선 |
| A100 / GA100 | sm_80 | 108 | 256 KiB | 192 KiB combined, 164 KiB shared allocation | 40 MiB | HBM2 | capacity L2와 CG L2를 모두 비교 가능 |
| H100 / GH100 | sm_90 | 132 default | 256 KiB급 | 256 KiB combined, 228 KiB shared allocation profile | 50 MiB | HBM2e/HBM3 SKU별 상이 | 현재 kernel은 WMMA compatibility path, WGMMA/TMA 실험 아님 |

주의:

- NVML `GetPowerUsage` 의미는 세대별로 다르다. V100/A100은 instant 계열로 보고, RTX 3090/H100은 1초 평균 power로 보고한다. 최종값은 가능하면 `nvmlDeviceGetTotalEnergyConsumption` mJ counter 차분을 사용한다.
- H100/HGX 계열에서는 GPU power, module power, GPU memory power reading이 함께 보일 수 있다. 현재 component coefficient는 NVML device/GPU energy 기준이며, module power나 memory-subsystem power를 같은 numerator로 섞지 않는다.
- `active_SM`은 profile 기본값이 아니라 runtime/preflight에서 확인한 값을 우선한다. MIG, partition, SKU 차이가 있으면 `--active-sm`을 반드시 조정한다.
- `combined L1/shared`는 SM 내부의 통합 L1/shared capacity이고, `shared allocation`은 CUDA dynamic/shared-memory 실험에서 사용할 수 있는 shared memory profile이다. 두 값을 같은 의미로 쓰면 안 된다.
- H100은 SKU에 따라 SM 수와 HBM 구성이 달라질 수 있다. profile default 132는 가이드용 기본값이다.
- V100은 최신 Nsight Compute release highlights에서 Volta/GV100 support 제거가 공지되어 있다. `ncu --list-chips`에 `gv100`이 없으면 energy run과 별도로 “NCU 검증 미완료”로 보고한다.
- V100은 CUDA 13에서 offline compilation 대상이 아니다. `nvcc --version`만 보지 말고
  `nvcc --list-gpu-arch`의 `compute_70`을 확인한다. generated package는 `NVCC` 환경변수로
  compiler를 받고 strict preflight에서 이 조건을 검사한다.

## 4. 추천 좌표

아래 좌표는 시작점이다. 최종값은 NCU acceptance 결과로 다시 걸러야 한다.

### 4.0 RTX 3090/A100/V100/H100 실행 package 한눈에 보는 비교

이 표는 현재 `scripts/plan_platform_component_experiment.py`가 생성하는 표준
package 하나를 `seconds=10 s`, `repeats=5 count`, GPU 1장에서 실행할 때의
기준이다. RTX 3090의 과거 targeted/stability 재실험 파일 전체를 세는
표가 아니며, A100/V100/H100 수치는 아직 node-local NCU/power gate를 통과한
실측 결과가 아닌 **실행 계획**이다.

| 구분 | RTX 3090 / GA102 | A100 / GA100 | V100 / GV100 | H100 / GH100 | 단위 및 조건 |
|---|---|---|---|---|---|
| CUDA / profile | `sm_86`, 82 SM | `sm_80`, 108 SM | `sm_70`, 80 SM | `sm_90`, 132 SM | runtime SM 수가 profile과 다르면 preflight에서 중단 |
| energy blocks/SM | 8,16 | 16,32 | 1,2,4,8,16,32 | 16,32 | V100은 저밀도 구간까지 utilization sweep |
| Tensor | W2048; RF 1,2,4,8,16 | W2048; RF 1,2,4,8,16 | W2048; RF 1,2,4,8,16 | W2048; RF 1,2,4,8,16 | W: KiB/SM 고정 좌표, RF: count; 실제 RF footprint는 ptxas/NCU로 확인 |
| Shared scalar W | 32,64 | 64,128 | 32,64 | 64,128 | KiB/SM; shared residency 한도 통과 필수 |
| Global L1 유효 W/B | W8/B8; W16/B8,16 | W16/B16; W32/B16,32 | W8/B1,2,4,8; W16/B1,2,4,8,16; W32/B1,2,4,8,16,32 | W16/B16; W32/B16,32 | W: KiB/SM, B: blocks/SM; block당 tile 1 KiB 미만 제외 |
| L2 CG 유효 W/B | W64/B8,16 | W16/B16; W32,64,128/B16,32 | W32,64/B1,2,4,8,16,32 | W64,128/B16,32 | `ld.global.cg`; A100 W16/B32는 0.5 KiB/block이라 제외 |
| DRAM sanity | W8192; B8,16 | W8192; B16,32 | W8192; B1,2,4,8,16,32 | W8192; B16,32 | KiB/SM; 총 working set이 nominal L2보다 커야 함 |
| memory energy LR | 4,8,16 | 4,8,16 | 4,8,16 | 4,8,16 | load repeat, count |
| candidate matrix | 92 | 128 | 348 | 104 | rows/1 repeat, feasibility 필터 전 |
| 유효 energy 좌표 | 86 | 116 | 330 | 98 | commands/1 repeat, treatment/control 모두 포함 |
| energy raw | 430 | 580 | 1,650 | 490 | rows, 유효 좌표 x 5 repeats; schema/revision smoke 3행 별도 |
| Tensor pair calibration | 10 coordinates / 20 commands | 10 coordinates / 20 commands | 30 coordinates / 60 commands | 10 coordinates / 20 commands | B x RF 좌표마다 treatment/control-floor calibration 2회; energy raw에 미포함 |
| primary NCU sidecar | 44 | 74 | 44 | 44 | cases; energy run과 분리, diagnostic mode 미포함 |
| strict NCU anchor B | 8 | 16 | 32 | 16 | blocks/SM; B가 다른 energy row를 채택하려면 exact-coordinate NCU 추가 필요 |
| power fallback 의미 | 1 s average | instantaneous | instantaneous | 1 s average | 최종 numerator는 모두 total-energy mJ delta 요구 |
| 핵심 플랫폼 제약 | GA102 16 blocks/SM profile, 6 MiB L2 | 40 MiB L2에서 4개 W plateau 후보 검증 | CUDA 12.x `compute_70` + `gv100` 지원 NCU 필수 | 50 MiB L2, 현재 Tensor는 WMMA compatibility path | 조건 미충족 시 coefficient reject |

개수를 해석할 때 `candidate matrix`, `energy raw`, `calibration`, `NCU sidecar`를
합산하지 않는다. 서로 다른 단계의 실행이며, 최종 coefficient는
energy raw가 있는 것만으로 채택하지 않고 exact-coordinate NCU acceptance,
power API audit, reliability audit을 모두 통과해야 한다.

### 4.0.1 플랫폼별 sweep을 그래프로 읽는 방법

![플랫폼별 blocks/SM sweep](../presentations/assets/platform_blocks_per_sm_sweep.png)

`blocks/SM`은 같은 component path의 issue density와 utilization을 바꾸는 축이다. 요청 B가
커져도 실제 resident block/warp가 같은 경우가 있으므로 graph의 marker를 occupancy로
직접 읽으면 안 된다. NCU `achieved_occupancy_pct`, `registers_per_thread`, static/dynamic
shared bytes/block이 함께 증가하는지 확인한다. V100 B1-B16은 diagnostic 범위를 넓힌
현재 policy이며 architecture 필수조건이 아니다. final cross-platform 비교는 각 GPU의
strict anchor 또는 동일 normalized density에서 exact-coordinate NCU를 갖춘 row끼리 해야 한다.

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

그래프는 네 플랫폼의 current planner 좌표를 동일 log2 W 축에 표시한다. Shared 행은
explicit shared-memory path이고 Global L1/L2/DRAM 행은 global-memory hierarchy 후보다.
따라서 Shared -> L1 -> L2 -> DRAM을 하나의 automatic cache migration으로 해석하지 않는다.

| Sweep에서 보는 변화 | 기대하는 NCU evidence | 결론 |
|---|---|---|
| cached global W에서 L1 hit plateau | L1 path hit >=95%, L2/DRAM 누출 낮음 | Global L1 후보 |
| `.cg` W에서 L1 hit가 사라지고 L2 hit plateau | L1 <=1%, L2 read hit >=95% | L2 후보 |
| full-GPU W가 L2보다 커지고 DRAM traffic 우세 | capacity-aware L2 residual, DRAM/L2 bytes ratio 충분 | DRAM sanity 후보 |
| W 증가 시 hit path가 혼합되거나 stall 급증 | hit/access/bytes와 long scoreboard가 동시에 불안정 | 경계/혼합 좌표로 reject 또는 diagnostic |

![strict anchor capacity 맥락](../presentations/assets/platform_capacity_context.png)

대표 좌표의 capacity 비율도 플랫폼마다 동일하지 않다. RTX L2 W64는 6 MiB의 약 85%,
V100 strict W32는 약 42%, A100 W16은 약 4%, H100 W64는 약 17%다. A100은 네 W에서
NCU plateau를 선택하므로 strict anchor 비율 하나만 비교해서는 안 된다. 향후 동일한
capacity fraction sweep을 추가할 수 있지만, unified L1 partition과 set mapping 때문에
capacity 계산은 여전히 NCU acceptance를 대체하지 못한다.

| GPU | Tensor W_SM (KiB) | Shared W_SM (KiB) | L1 W_SM (KiB) | L2 W_SM (KiB) | DRAM W_SM (KiB) | blocks/SM |
|---|---:|---:|---:|---:|---:|---|
| RTX 3090 | 2048 | 32,64 | 8,16 | 64 with `l2_cg_load_only` | 8192 | energy 8,16; generated strict NCU 8 |
| V100 | 2048 | 32,64 | 8,16,32 | 32,64 with `l2_cg_load_only` | 8192 | energy 1,2,4,8,16,32; strict NCU 32 |
| A100 | 2048 | 64,128 | 16,32 | 16,32,64,128 with `l2_cg_load_only` | 8192 | 16,32 |
| H100 | 2048 | 64,128 | 16,32 | 64,128 with `l2_cg_load_only` | 8192 | 16,32 |

Tensor `W_SM=2048 KiB`는 register working-set 크기라는 뜻이 아니다. register-mode에서 `W_SM`은 고정 좌표일 뿐이고, 실제 register footprint는 ptxas register count, threads/block, resident blocks/SM로 판단한다.

A100 Global L1의 `W16,32 x B16,32` 표기는 feasibility-filtered sweep이다. 실제 valid
좌표는 W16/B16, W32/B16, W32/B32이며 W16/B32는 0.5 KiB/block이라 treatment와
`global_addr_only` control 모두 제외한다. strict NCU 좌표는 W16/B16이다.

V100 strict 좌표는 Shared `W32/B32`, Global L1 `W32/B32`, L2 CG
`W32/B32`다. L2 strict working set은 `80 x 32 KiB = 2.5 MiB`로 6 MiB
L2의 약 42%이며, `W64 = 5 MiB`는 capacity-stress 보조점이다. 현재 kernel은
one warp/block이므로 B32도 최대 64 warps/SM의 50%에 해당한다. B1-B16은 energy
utilization sweep이고, final coefficient에는 exact-coordinate NCU evidence가 있는 row만
사용한다.

### 4.1 비교 범위와 개수 정의

아래 비교는 `scripts/plan_platform_component_experiment.py`의 현재 profile로 새 표준
package 하나를 생성해 GPU 한 장에서 실행하는 경우다. 공통 설정은 `seconds=10 s`,
`repeats=5 count`, `store_repeat=1 count`이며 energy run에는 NCU를 붙이지 않는다.
RTX 3090 디렉터리에 누적된 여러 targeted/stability rerun의 전체 파일 수를 세는 표가
아니다.

| 용어 | 계산 방법 | 단위/포함 범위 |
|---|---|---|
| candidate matrix row | mode x W_SM x blocks/SM x RF 또는 LR | count, feasibility 판정 전 |
| 유효 좌표/1회 반복 | candidate 중 Python feasibility와 mode 조건을 통과한 command | count, treatment와 control 모두 포함 |
| 예상 energy raw row | 유효 좌표 x `repeats=5` | rows, 각 command는 harness `repeats=1`로 한 행 기록 |
| schema/revision smoke | full sweep 전에 `clocked_empty`, `reg_operand_only`, `l2_cg_load_only` 각 한 행 | 3 rows/platform, 아래 energy raw 합계에서 제외; CSV schema와 Tensor/CG 구현 marker 확인 |
| Tensor pair calibration | 각 blocks/SM x RF에서 `reg_mma` treatment 목표와 `reg_operand_only` control 최소시간을 각각 calibration | coordinates/commands, 두 candidate ITER의 최대값을 두 Tensor mode에 공급하며 raw energy row가 아님 |
| NCU sidecar case | energy와 분리해 profiler로 한 번 실행하는 exact-coordinate case | cases, energy raw row에 포함하지 않음 |

따라서 이 문서의 `개수`는 순수한 물리 상태 수가 아니라 실제 실행 command/CSV row
수다. treatment-control pair는 두 개 command로 계산하며, 같은 좌표라도 RF 또는 LR이
다르면 별도 command다.

### 4.2 플랫폼별 실험 파라미터

| 파라미터 | RTX 3090 / GA102 | A100 / GA100 | V100 / GV100 | H100 / GH100 | 단위/조건 |
|---|---|---|---|---|---|
| CUDA arch | `sm_86` | `sm_80` | `sm_70` | `sm_90` | V100은 `compute_70` 지원 CUDA 12.x 필요 |
| profile active SM | 82 | 108 | 80 | 132 | SMs, runtime/preflight 값이 우선 |
| profile max blocks/SM | 16 | 32 | 32 | 32 | blocks/SM |
| energy blocks/SM | 8,16 | 16,32 | 1,2,4,8,16,32 | 16,32 | blocks/SM |
| generated strict NCU blocks/SM | 8 | 16 | 32 | 16 | blocks/SM |
| Tensor W_SM | 2048 | 2048 | 2048 | 2048 | KiB, register footprint 크기가 아닌 고정 좌표 |
| Tensor RF | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | reuse factor, unitless |
| Tensor ITER policy | RF별 treatment/control-floor dual calibration 후 pair-lock | 동일 | 동일 | 동일 | 두 candidate ITER의 최대값을 두 mode에 동일 적용, direct net-energy subtraction |
| Tensor common inner op | RF당 dependent register integer add 1개 | 동일 | 동일 | 동일 | treatment/control에 모두 포함해 차분에서 상쇄; control FP32 FMA/checksum/memory 없음 |
| Shared W_SM | 32,64 | 64,128 | 32,64 | 64,128 | KiB/SM |
| Global L1 W_SM | 8,16 | 16,32 | 8,16,32 | 16,32 | KiB/SM |
| L2 CG W_SM | 64 | 16,32,64,128 | 32,64 | 64,128 | KiB/SM |
| DRAM sanity W_SM | 8192 | 8192 | 8192 | 8192 | KiB/SM = 8 MiB/SM |
| memory energy LR | 4,8,16 | 4,8,16 | 4,8,16 | 4,8,16 | load repeat, count |
| Tensor NCU RF | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | unitless |
| Shared/L1/L2 NCU LR | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | 1,2,4,8,16 | count |
| DRAM NCU LR | 1,4,8,16 | 1,4,8,16 | 1,4,8,16 | 1,4,8,16 | count |
| measurement duration | 10 | 10 | 10 | 10 | s/energy command |
| energy repeats | 5 | 5 | 5 | 5 | count/valid coordinate |
| fallback power semantics | `one_sec_average` | `instant` | `instant` | `one_sec_average` | final numerator는 모두 total-energy mJ delta 요구 |
| NCU chip | `ga102` | `ga100` | `gv100` | `gh100` | unavailable metric은 기록 후 필터, 필수 evidence 누락 시 reject |

### 대역폭과 ITER/측정시간 해석

같은 고정 ITER라면 더 높은 실효 처리량을 내는 GPU에서 kernel이 더 빨리 끝나는 것이
맞다. 다만 위 표의 `measurement duration=10 s`는 모든 GPU에 동일 ITER를 주는 뜻이
아니다. energy sweep는 플랫폼과 좌표별로 ITER를 calibration해 약 10 s의 측정창을 만든다.
따라서 빠른 GPU에서는 보통 ITER가 더 커지고, 결과 비교는 ITER 자체가 아니라 측정된
`elapsed_s`, NCU bytes/operations와 total-energy delta를 기준으로 한다.

메모리 bandwidth 사양만으로 실행시간을 예측해서는 안 된다. V100 32 GB의 HBM2
bandwidth는 제품 형태에 따라 RTX 3090과 비슷한 수준일 수 있고, A100/H100도 SKU별로
다르다. 더구나 Shared/L1/L2 실험은 HBM peak bandwidth가 아니라 해당 on-chip path,
occupancy, SM 수, block 수, clock과 instruction dependency의 영향을 받는다. DRAM path도
working set과 실제 NCU DRAM bytes가 충분할 때만 외부-memory bandwidth 차이가 직접
드러난다.

Global L1에서 실제 실행되는 W/B 조합은 다음과 같다. 모든 표기의 W 단위는 KiB/SM이고
B 단위는 blocks/SM이다.

| GPU | 유효 Global L1 W/B | 제외되는 W/B | 제외 이유 |
|---|---|---|---|
| RTX 3090 | W8/B8, W16/B8, W16/B16 | W8/B16 | 0.5 KiB/block |
| A100 | W16/B16, W32/B16, W32/B32 | W16/B32 | 0.5 KiB/block |
| V100 | W8/B1,2,4,8; W16/B1,2,4,8,16; W32/B1,2,4,8,16,32 | W8/B16, W8/B32, W16/B32 | 1 KiB/block 미만 |
| H100 | W16/B16, W32/B16, W32/B32 | W16/B32 | 0.5 KiB/block |

L2 CG도 같은 최소 tile 조건을 적용한다. A100은 L2 hit plateau를 찾기 위해 W sweep을
확장했으므로 Global L1 표와 별도로 다음 유효 좌표를 사용한다.

| GPU | 유효 L2 CG W/B | 제외되는 W/B | 제외 이유 |
|---|---|---|---|
| RTX 3090 | W64/B8,16 | 없음 | 모든 좌표가 1 KiB/block 이상 |
| A100 | W16/B16; W32,64,128/B16,32 | W16/B32 | 0.5 KiB/block |
| V100 | W32,64/B1,2,4,8,16,32 | 없음 | 모든 좌표가 1 KiB/block 이상 |
| H100 | W64,128/B16,32 | 없음 | 모든 좌표가 1 KiB/block 이상 |

### 4.3 표준 package의 실험 개수

각 셀은 `유효 좌표/1회 반복 / repeats=5 적용 후 예상 raw rows` 형식이다. 두 숫자의
단위는 각각 count와 rows다.

| Component/path | RTX 3090 | A100 | V100 | H100 | 개수에 포함된 변화 축 |
|---|---:|---:|---:|---:|---|
| Tensor | 20 / 100 | 20 / 100 | 60 / 300 | 20 / 100 | 2 modes x blocks/SM x RF 5개 |
| Shared scalar | 24 / 120 | 24 / 120 | 72 / 360 | 24 / 120 | 2 modes x W/B x LR 3개 |
| Global L1 | 18 / 90 | 18 / 90 | 90 / 450 | 18 / 90 | 2 modes x valid W/B x LR 3개 |
| L2 CG | 12 / 60 | 42 / 210 | 72 / 360 | 24 / 120 | 2 modes x valid W/B x LR 3개 |
| DRAM sanity | 12 / 60 | 12 / 60 | 36 / 180 | 12 / 60 | 2 modes x blocks/SM x LR 3개 |
| **합계** | **86 / 430** | **116 / 580** | **330 / 1,650** | **98 / 490** | schema/revision smoke와 NCU 제외 |

| package 규모 항목 | RTX 3090 | A100 | V100 | H100 | 단위/해석 |
|---|---:|---:|---:|---:|---|
| candidate matrix rows/1 repeat | 92 | 128 | 348 | 104 | rows |
| feasibility로 제외된 matrix rows/1 repeat | 6 | 12 | 18 | 6 | rows, A100은 Global L1 6 + L2 CG 6, 나머지는 Global L1 최소 tile 조건 |
| 유효 energy 좌표/1 repeat | 86 | 116 | 330 | 98 | count |
| 예상 energy raw rows (`repeats=5`) | 430 | 580 | 1,650 | 490 | rows |
| schema/revision smoke | 3 | 3 | 3 | 3 | rows, 별도 CSV; full sweep 전 stale binary 거부 |
| Tensor pair calibration | 10 coordinates / 20 commands | 10 coordinates / 20 commands | 30 coordinates / 60 commands | 10 coordinates / 20 commands | blocks/SM x RF마다 2회 calibration; energy raw row에는 포함하지 않고 manifest 한 행/좌표로 기록 |
| primary NCU sidecar | 44 | 74 | 44 | 44 | cases, diagnostic mode 제외 |
| nominal energy kernel time | 4,300 | 5,800 | 16,500 | 4,900 | s, raw rows x 10 s 기준. Dual calibration의 control candidate가 크면 Tensor treatment가 연장되며 calibration/launch/NCU/분석 시간도 별도 |

RTX 3090/V100/H100의 NCU 44 cases는 `clocked_empty` 1개, Tensor treatment/control
`2 modes x RF 5 = 10`개, Shared 1 mode와 Global L1/L2 treatment-control을 합한
`5 modes x LR 5 = 25`개, DRAM treatment/control `2 modes x LR 4 = 8`개의 합이다.
A100은 L2의 4개 W마다 treatment/control을 수집하므로 memory 구간이
`(Shared 1 + Global L1 2 + L2 8) x LR 5 = 55` cases가 되어 총 74 cases다.
`INCLUDE_DIAGNOSTIC_NCU=1`을 켜면 이 수보다 증가하므로 보고서에 별도로 표기한다.

V100의 row 수가 큰 주된 이유는 같은 component 수를 쓰면서 blocks/SM을 6개 값으로
넓게 sweep하기 때문이다. 이 저밀도 B1-B16 행은 utilization/min/median/max 진단용이며,
strict coefficient는 exact NCU sidecar가 있는 B32 행을 우선한다.

### 4.4 strict 좌표와 기존 RTX 3090 실측 좌표 구분

새 표준 package generator가 지정하는 strict NCU anchor는 다음과 같다.

| Component/path | RTX 3090 generated plan | A100 generated plan | V100 generated plan | H100 generated plan | 단위 |
|---|---|---|---|---|---|
| Tensor | W2048/B8 | W2048/B16 | W2048/B32 | W2048/B16 | KiB/SM, blocks/SM |
| Shared scalar | W64/B8 | W128/B16 | W32/B32 | W128/B16 | KiB/SM, blocks/SM |
| Global L1 | W8/B8 | W16/B16 | W32/B32 | W16/B16 | KiB/SM, blocks/SM |
| L2 CG | W64/B8 | W16,32,64,128/B16 | W32/B32 | W64/B16 | KiB/SM, blocks/SM; A100은 후보 set |
| DRAM sanity | W8192/B8 | W8192/B16 | W8192/B32 | W8192/B16 | KiB/SM, blocks/SM |

같은 W_SM 숫자라도 architecture capacity 대비 위치가 다르다. 아래 비율은 generated
strict anchor의 nominal profile 계산이며 실제 residency/hit은 NCU로 다시 확인한다.

| capacity check | RTX 3090 | A100 | V100 | H100 | 해석 |
|---|---:|---:|---:|---:|---|
| Shared 예약 근사 `W_SM+B` / shared profile | 72/100 KiB (72.0%) | 144/164 KiB (87.8%) | 64/96 KiB (66.7%) | 144/228 KiB (63.2%) | Shared strict point의 profile 한도 대비 위치 |
| Global L1 W_SM / combined L1-shared | 8/128 KiB (6.3%) | 16/192 KiB (8.3%) | 32/128 KiB (25.0%) | 16/256 KiB (6.3%) | shared를 할당하지 않는 global L1 후보의 per-SM footprint |
| L2 full-GPU W / nominal L2 | 5.125/6 MiB (85.4%) | 1.688-13.5/40 MiB (4.2-33.8%) | 2.5/6 MiB (41.7%) | 8.25/50 MiB (16.5%) | A100은 4개 W에서 NCU-accepted plateau를 선택; H100 W128은 energy 보조점 |
| DRAM full-GPU W | 656 MiB | 864 MiB | 640 MiB | 1,056 MiB | 모두 nominal L2보다 충분히 큰 streaming sanity footprint |

Tensor의 W2048은 위 capacity 계산 대상이 아니다. Tensor/register mode의 실제
resident block 수는 ptxas register count와 NCU의 registers/thread, achieved occupancy로
판정하며, 요청 B 값만으로 residency를 확정하지 않는다.

현재 공개된 RTX 3090 accepted coefficient는 generator를 새로 한 번 실행한 package가
아니라 안정성 재실험에서 선택한 B16 exact-NCU evidence다. 따라서 다음 실측 좌표를 위
generated B8 계획과 바꾸어 읽으면 안 된다.

| RTX 3090 accepted component | 실제 선택 좌표 | factor | 상태 |
|---|---|---|---|
| Tensor | W2048 KiB, B16, active SM 82 | RF8, RF16 | accepted, RF-dependent |
| Shared scalar | W64 KiB, B16, active SM 82 | LR8 | accepted |
| Global L1 | W16 KiB, B16, active SM 82 | LR4 | accepted |
| L2 CG | W64 KiB, B16, active SM 82 | LR4, LR8 | accepted |
| DRAM sanity | W8192 KiB, B16, active SM 82 | 별도 sanity | strict 4-component summary에는 미포함 |

A100과 V100 표는 아직 target-node accepted coefficient가 아니라 실행 계획이다. 실제
결과에서 NCU path acceptance, power API audit, reliability audit이 통과하지 않으면 위
strict 좌표라도 final coefficient로 채택하지 않는다.

### 4.5 공통 feasibility와 채택 조건

| 조건 | 판정식/검증 | 실패 시 처리 |
|---|---|---|
| block당 최소 memory tile | memory-backed mode에서 `W_SM_KiB >= blocks/SM`, 즉 block당 1 KiB 이상 | matrix `valid=false`, treatment/control 모두 실행 제외 |
| shared residency | `W_SM + blocks/SM <= profile shared KiB/SM` 및 `W_SM / blocks/SM <= max shared KiB/block` | Shared mode 실행 제외 |
| L2 candidate | `profile full SM x W_SM <= nominal L2` | L2 mode 실행 제외 또는 DRAM candidate로 분류 |
| Python/C++ 정합성 | 유효 unique 좌표를 binary `--dry-run`으로 energy 전에 재검사 | 첫 energy command 전에 명시적 실패 |
| final energy numerator | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` | fallback/provisional 또는 reject |
| NCU path | hit rate뿐 아니라 access count, bytes, spill, stall, occupancy를 exact 좌표에서 확인 | component coefficient reject |

## 5. NCU Acceptance 기준

| Path | accept 조건 |
|---|---|
| Tensor | HMMA > 0, spill/local 0, memory traffic이 FLOP 대비 작음 |
| Tensor control | HMMA 0, spill/local 0 |
| Shared scalar | shared bytes/accesses 존재, bank conflict 0 또는 매우 낮음 |
| Global L1 | path-specific L1 hit >= 95%, L1 request bytes 존재, L2/L1 request byte ratio <= 1%, DRAM/L1 request byte ratio <= 1% |
| L2 hit | path-specific L2 read hit >= 95%, L2 read bytes 존재, L1 path hit <= 1%, L1 hit bytes/L1 request bytes <= 1%, DRAM/L2 read bytes <= 2%. `.cg`도 L1TEX request는 발생하므로 L1 request bytes가 0이어야 한다고 판정하지 않음 |
| DRAM sanity | path-specific L1 hit <=1%, DRAM access/bytes가 충분하고 dominant, path-specific L2 read hit은 `max(5%, 2 x L2_capacity/full_working_set + 2%)` 이하 |

L2/DRAM CG mode의 pre-measurement warm-up도 `ld.global.cg.u32` 전용 kernel을
사용한다. 일반 cached warm-up이 L1을 먼저 채워 path 판정을 오염시키지 않도록 하기
위한 조건이며, 각 플랫폼에서 실제 L1/L2 hit/miss는 여전히 NCU로 확인한다.

NCU 표에는 다음 단위를 반드시 포함한다.

| metric | unit |
|---|---|
| L1 hit rate | % |
| L2 hit rate | % |
| shared accesses | access count |
| L1/L2/DRAM accesses | requests 또는 sectors |
| shared/L1/L2/DRAM bytes | bytes |
| stall_long_scoreboard | % |

## 6. 결과 보고 언어

| 상황 | 보고 표현 |
|---|---|
| NCU accepted, coefficient 모두 양수 | `accepted candidate` |
| NCU accepted, 일부 음수/분산 큼 | `path accepted, coefficient provisional` |
| NCU rejected | `rejected for component coefficient` |
| register-pressure direct division | `register/control diagnostic only` |
| DRAM | `streaming sanity path`, physical DRAM energy라고 쓰지 않음 |

## 7. 자가비판 요약

이 실험은 다음 한계가 있다.

| 한계 | 영향 | 보완 |
|---|---|---|
| NVML board-level energy | component 외 power가 섞임 | NCU path validation과 matched-control을 같이 사용 |
| representative NCU | 기존 RTX 3090 strict 결과는 모든 energy row의 actual traffic을 직접 본 것은 아님 | 새 final run은 `TENSOR_REUSE_FACTORS`, `MEMORY_LOAD_REPEATS`, `DRAM_LOAD_REPEATS`로 좌표별 NCU sidecar 실행 |
| register 분리 어려움 | pure RF pJ/access를 주장하기 어려움 | register는 control/proxy로 제한 |
| L2/DRAM stall | pJ/bit에 stall/control이 포함됨 | stall_long_scoreboard를 함께 보고 |
| H100 WMMA path | Hopper native WGMMA/TMA 에너지가 아님 | 별도 H100-native kernel 설계 필요 |
