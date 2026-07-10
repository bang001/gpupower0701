# Documentation Map

이 디렉토리는 현재 finalplan 기준 문서를 목적별로 분류한다. 과거 탐색 설계, 폐기된 분석 흐름, 현재 coefficient 산출에 직접 쓰지 않는 초기 결과는 `archive/legacy_20260707/`에 보관한다.

## 빠른 시작

| 목적 | 먼저 볼 문서 |
|---|---|
| 현재 코드와 실험 구조 이해 | `docs/methodology/howitworks.md` |
| RTX 3090 최종 결과 확인 | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| 백서용 문장/주장 범위 확인 | `docs/reports/gpu_power_modeling_whitepaper_synthesis_ko.md` |
| 다른 GPU에서 실행 | `docs/platforms/README.md` |
| GPU 세대별 power API 사용 가능성/제약/최종 채택 기준 확인 | `docs/platforms/power_measurement_api_matrix_ko.md` |
| 플랫폼 profile/power 정합성 audit | `results/summary/platform_power_readiness_audit_20260708.md` |
| strict + fresh NCU 결과 확인 | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md` |
| strict + fresh NCU reliability 확인 | `results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md` |
| strict + fresh NCU summary audit 확인 | `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260708.md` |
| strict raw power API 재감사 확인 | `results/summary/rtx3090_strict_scope_power_api_reaudit_20260708.md` |
| 전체 목표 readiness 확인 | `results/summary/component_energy_goal_readiness_audit_20260708.md` |
| 플랫폼 결과 intake dashboard | `results/summary/platform_component_intake_dashboard_20260708.md` |
| A100/V100/H100 command package | `results/summary/a100_component_finalplan_20260708_command_plan.md`, `results/summary/v100_component_finalplan_20260708_command_plan.md`, `results/summary/h100_component_finalplan_20260708_command_plan.md` |
| active/archive 경계 확인 | `docs/audits/repository_active_archive_audit_ko.md` |
| A100 strict summary 및 L1 W16/B32 중단 리메디에이션 | `docs/audits/a100_strict_summary_failure_remediation_ko.md` |
| V100 32GB 구조/좌표 재검토 | `docs/audits/v100_32gb_platform_review_ko.md` |

## 실험 설정/방법 문서 위치

실험을 다시 실행하거나 다른 플랫폼에 전달할 때는 아래 순서로 문서를 보면 된다.

| 단계 | 확인할 문서 | 여기서 확인할 내용 |
|---|---|---|
| 1. 전체 목적/구조 | `docs/methodology/howitworks.md` | treatment-control, mode 의미, shared/L1/L2/DRAM path 구분, 전체 흐름 |
| 2. 실험 조건과 sweep | `docs/methodology/component_energy_final_experiment_plan_ko.md` | Tensor RF sweep, memory LR sweep, W_SM, blocks/SM, 채택/제외 기준 |
| 3. NCU 검증/계산법 | `docs/methodology/ncu_validation_energy_calculation_ko.md` | cache hit rate, L1/L2/DRAM traffic denominator, pJ/FLOP/pJ/bit 계산 |
| 4. 플랫폼 공통 절차 | `docs/platforms/cross_platform_component_experiment_guide_ko.md` | preflight, energy run, NCU sidecar, acceptance, matched-control 분석 순서 |
| 5. 세대별 power API | `docs/platforms/power_measurement_api_matrix_ko.md` | 실험 전 1페이지 판정표, NVML total energy, `GetPowerUsage`, nvidia-smi GPU/module/memory power의 사용 가능성, 제약, final/provisional/reject 기준 |
| 6. 플랫폼 정합성 audit | `results/summary/platform_power_readiness_audit_20260708.md` | RTX 3090/V100/A100/H100 profile, power API, 문서, 생성 plan 일치 여부 |
| 7. GPU별 실행 가이드 | `docs/platforms/a100_node_experiment_guide_ko.md`, `docs/platforms/v100_node_experiment_guide_ko.md`, `docs/platforms/h100_node_experiment_guide_ko.md` | A100/V100/H100에서 수정해야 할 SM/L2/shared/NCU/NVML 조건 |
| 8. 결과 해석 | `docs/results/gpu_power_modeling_experiment_results_ko.md` | RTX 3090 기준 결과 표, sweep 결과, 현재 인정 가능한 coefficient |
| 9. 결과 sanity audit | `results/summary/rtx3090_current_component_sanity_audit_20260708.md` | 현재 보고값의 power scope, 단위, 계층 순서, warning/fail 확인 |
| 10. strict + fresh NCU 확인 | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md` | raw CSV에 explicit `measurement_scope`가 기록되고 fresh NCU sidecar로 denominator/path를 재검증한 RTX 3090 결과 |
| 11. strict summary build/audit | `scripts/build_strict_component_summary.py`, `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260708.md` | accepted reliability에서 보고용 summary 생성 후 reliability artifact, power scope, NCU denominator, hierarchy/plausibility gate, NCU counter schema/coordinate/path-evidence 노출 여부 확인 |
| 12. goal readiness audit | `results/summary/component_energy_goal_readiness_audit_20260708.md` | RTX 3090 accepted 증거, NCU availability, A100/V100/H100 결과 패키지 누락 여부, platform summary/power API/power-state/reliability/NCU acceptance policy |
| 12a. 외부 플랫폼 결과 intake | `results/summary/component_energy_goal_readiness_audit_20260708.md`의 `External Platform Result Intake Checklist` | A100/V100/H100 노드에서 실행 후 되가져와야 할 raw, power API, power-state, NCU, reliability, strict summary artifact 목록 |
| 12b. 외부 플랫폼 패키지 audit | `scripts/audit_platform_result_package.py` | 복사해 온 A100/V100/H100 결과 패키지가 profile metadata, active SM, power matrix, NCU, reliability, strict summary 기준을 만족하는지 단일 profile/tag로 검수 |
| 12c. 플랫폼 intake dashboard | `results/summary/platform_component_intake_dashboard_20260708.md` | RTX 3090 local strict evidence와 V100/A100/H100 외부 package/gap/strict summary 상태를 한 표로 확인 |
| 12d. 로컬 readiness wrapper | `scripts/run_local_readiness_checks.sh` | preflight/power API/strict summary build/audit/package/goal/manifest/gap/dashboard self-test, platform power readiness, RTX 3090 strict summary audit, goal readiness audit, dashboard refresh, `git diff --check`를 한 번에 실행 |
| 13. 백서/보고서 작성 | `docs/reports/gpu_power_modeling_whitepaper_synthesis_ko.md` | 주장 범위, 한계, effective coefficient 문구 |

스크립트 사용법은 `scripts/README.md`에서 확인한다. 새 플랫폼에서는 먼저
`scripts/preflight_gpu_support.py`를 실행하고, 그 다음
`scripts/plan_platform_component_experiment.py`가 생성한 command plan을 기준으로
실험한다.

## 폴더 구조

| 폴더 | 목적 | 현재성 |
|---|---|---|
| `docs/methodology/` | 실험 설계, mode 의미, NCU 검증, pJ 계산 방식 | active |
| `docs/results/` | 현재 결과 표와 시각화 해석 | active |
| `docs/reports/` | 백서/보고서용 종합 문서 | active |
| `docs/platforms/` | A100/V100/H100 등 플랫폼별 실행 가이드와 프롬프트 | active |
| `docs/audits/` | 자가비판, 문헌값 검토, repository 정리 기록 | active |
| `docs/design/` | 초기 v2 실험 상세설계와 설계 자산 | active reference |
| `docs/assets/` | 문서 그림, 표, 보조 plot script | active assets |

## Active 문서 목록

| 분류 | 문서 | 작성/갱신일 | 목적 |
|---|---|---|---|
| methodology | `docs/methodology/howitworks.md` | 2026-07-02, updated 2026-07-08 | 현재 코드의 mode, treatment-control, NCU 검증 흐름 설명 |
| methodology | `docs/methodology/component_energy_final_experiment_plan_ko.md` | 2026-07-05, updated 2026-07-08 | finalplan 실험 조건과 채택/제외 기준 |
| methodology | `docs/methodology/component_energy_method_comparison_ko.md` | 2026-07-06, updated 2026-07-08 | 초기 sweep과 finalplan 방식의 차이, sweep 조건 설명 |
| methodology | `docs/methodology/ncu_validation_energy_calculation_ko.md` | 2026-07-08 | NCU counter로 path와 denominator를 검증하는 방법 |
| results | `docs/results/gpu_power_modeling_experiment_results_ko.md` | 2026-07-08 | RTX 3090 finalplan strict 결과와 sweep 표 |
| reports | `docs/reports/gpu_power_modeling_whitepaper_synthesis_ko.md` | 2026-07-08 | 백서용 핵심 주장, 결과, 한계 정리 |
| platforms | `docs/platforms/README.md` | 2026-07-08, updated 2026-07-09 | GPU별 구조/NVML/NCU 차이와 power API 채택 기준 |
| platforms | `docs/platforms/cross_platform_component_experiment_guide_ko.md` | 2026-07-06, updated 2026-07-10 | A100/V100/H100 공통 실행/해석 기준과 V100 CUDA 12.x gate |
| platforms | `docs/platforms/power_measurement_api_matrix_ko.md` | 2026-07-09 | GPU 세대별 NVML/nvidia-smi power/energy API 의미와 final/provisional gate |
| platforms | `docs/platforms/a100_node_experiment_guide_ko.md` | 2026-07-08 | A100 노드 실행 가이드 |
| platforms | `docs/platforms/v100_node_experiment_guide_ko.md` | 2026-07-02, updated 2026-07-10 | V100 노드 실행 가이드와 V100 전용 strict 좌표 |
| platforms | `docs/platforms/h100_node_experiment_guide_ko.md` | 2026-07-08 | H100 노드 실행 가이드 |
| platforms | `docs/platforms/prompts/v100_experiment_prompt_ko.md` | 2026-07-07, updated 2026-07-10 | V100 작업 전달용 프롬프트와 CUDA/NCU 독립 gate |
| audits | `docs/audits/component_energy_self_critique_ko.md` | 2026-07-06, updated 2026-07-08 | 잘못된 설계/해석과 수정 내역 |
| audits | `docs/audits/literature_energy_values_audit_ko.md` | 2026-07-03 | 문헌 pJ/bit 값과 본 실험값의 해석 레벨 비교 |
| audits | `docs/audits/a100_strict_summary_failure_remediation_ko.md` | 2026-07-10 | A100 strict summary 실패 원인, Global L1 coordinate filter, 재실행 조건 |
| audits | `docs/audits/v100_32gb_platform_review_ko.md` | 2026-07-10 | V100 32GB capacity, blocks sweep, strict NCU W/B 좌표 검토 |
| audits | `docs/audits/repository_active_archive_audit_ko.md` | 2026-07-08 | active/archive 분리 근거 |
| design | `docs/design/a100_fp16_energy_experiment_design_v2.md` | 2026-07-01 계열 | 초기 FP16 WMMA v2 상세설계 reference |

## Archive 기준

다음 성격의 문서는 active `docs/`에서 제거하고 `archive/legacy_20260707/`에 보관한다.

| archive 대상 | 이유 |
|---|---|
| finalplan 이전 decomposition/regression/register-footprint 설계 | 현재 coefficient 산출 경로가 아님 |
| 20260701/20260702 raw sweep result/plot | 후보 탐색 결과이며 final coefficient 직접 입력이 아님 |
| 구현 전 multi-GPU 지원 계획 | 현재 플랫폼 가이드와 `docs/platforms/README.md`에 병합됨 |
| 과거 백서 시간순 원문 | 현재 백서는 finalplan 기준으로 재작성됨 |

새 실험과 보고서에는 active 문서를 우선 사용한다. archive 문서를 사용할 때는 보고서에 `legacy exploration` 또는 `legacy diagnostic`이라고 명시한다.
