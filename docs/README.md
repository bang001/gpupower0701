# Documentation Map

갱신일: 2026-07-16

`docs/`에는 현행 acceptance-first finalplan을 실행하고 해석하는 데 필요한 문서만
남긴다. 초기 설계, 구형 coefficient 시각화와 과거 전체 보고서는 `archive/`에 보존한다.

## 빠른 시작

| 질문 | 먼저 볼 문서 |
|---|---|
| 현재 실험은 어떻게 동작하는가 | `docs/methodology/howitworks.md` |
| 어떤 sweep과 좌표를 실행하는가 | `docs/methodology/component_energy_final_experiment_plan_ko.md` |
| 초기 방식과 현재 방식은 무엇이 다른가 | `docs/methodology/component_energy_method_comparison_ko.md` |
| NCU로 무엇을 검증하고 pJ를 어떻게 계산하는가 | `docs/methodology/ncu_validation_energy_calculation_ko.md` |
| External-memory pJ/bit의 범위와 architecture별 W sweep은 무엇인가 | `docs/methodology/external_memory_read_path_experiment_design_ko.md` |
| A100 L2 source/fabric/final-service를 어떻게 분리하는가 | `docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md` |
| 현재 확정된 결과와 미확정 결과는 무엇인가 | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| 백서에 어떤 표현을 써야 하는가 | `docs/reports/gpu_power_modeling_whitepaper_synthesis_ko.md` |
| 다른 GPU에서 어떻게 실행하는가 | `docs/platforms/README.md` |
| 코드/문서/결과의 현재 한계는 무엇인가 | `docs/audits/component_energy_self_critique_ko.md` |
| A100/V100 외부 결과가 왜 탈락했고 무엇을 다시 받아야 하는가 | `docs/audits/a100_v100_external_result_remediation_ko.md` |
| A100 L2 lookup 모집단 오류와 RTX Shared/L1 pair를 어떻게 교정했는가 | `docs/audits/a100_l2_counter_scope_and_rtx_pair_remediation_ko.md` |
| Tensor MMA 구현·FLOP·cache 오염을 어떻게 감사했는가 | `docs/audits/tensor_mma_cross_architecture_implementation_audit_ko.md` |
| A100 Tensor run이 16시간 이상 걸린 이유와 재발 방지는 무엇인가 | `docs/audits/a100_tensor_control_calibration_failure_20260715_ko.md` |
| A100/V100의 ratio 21.930 메시지가 왜 실제 GPU 실패가 아닌가 | `docs/audits/a100_v100_synthetic_selftest_false_failure_20260716_ko.md` |
| A100/V100이 schema smoke 다음에 중단된 원인을 어떻게 구분하는가 | `docs/audits/a100_v100_schema_smoke_stop_20260716_ko.md` |
| 멀티 GPU `run_id` overwrite와 L1/L2/DRAM control 혼합을 어떻게 막았는가 | `docs/audits/multigpu_sweep_pairing_identity_fix_20260716_ko.md` |
| Memory path와 제거한 sweep을 GPU별로 어떻게 감사했는가 | `docs/audits/memory_path_cross_architecture_sweep_audit_ko.md` |
| 무엇이 archive로 이동했는가 | `docs/audits/repository_active_archive_audit_ko.md` |

## 실행 순서

| 단계 | 문서/도구 | 확인할 내용 |
|---:|---|---|
| 1 | `docs/methodology/howitworks.md` | treatment-control과 primary mode 의미 |
| 2 | `docs/platforms/power_measurement_api_matrix_ko.md` | GPU별 NVML API 의미와 final numerator 조건 |
| 3 | GPU별 node guide | build, preflight, CUDA/NCU/NVML 제약 |
| 4 | `scripts/plan_platform_component_experiment.py` | profile별 command package 생성 |
| 5 | generated `*_commands.sh` | energy, NCU, acceptance, strict/package audit 전체 실행 |
| 6 | `docs/results/gpu_power_modeling_experiment_results_ko.md` | 결과 지위와 보고 가능 범위 확인 |

GPU별 가이드:

| GPU | 가이드 | 표준 실행 package |
|---|---|---|
| RTX 3090 | `README.md` | `results/summary/rtx3090_component_finalplan_20260716_commands.sh` |
| V100 | `docs/platforms/v100_node_experiment_guide_ko.md` | `results/summary/v100_component_finalplan_20260716_commands.sh` |
| A100 | `docs/platforms/a100_node_experiment_guide_ko.md` | `results/summary/a100_component_finalplan_20260716_commands.sh` |
| H100 | `docs/platforms/h100_node_experiment_guide_ko.md` | `results/summary/h100_component_finalplan_20260716_commands.sh` |

새 실행에서는 날짜 tag로 package를 다시 생성하는 것이 가장 명확하다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --tag "$(date +%Y%m%d)"
```

## 폴더별 역할

| 폴더 | 역할 | 현재성 |
|---|---|---|
| `docs/methodology/` | 실험 목적, pair, sweep, NCU/pJ 계산 | active |
| `docs/platforms/` | GPU 구조/profile, NVML/NCU/toolchain, 실행 가이드 | active |
| `docs/results/` | 현재 결과 상태와 historical evidence 경계 | active |
| `docs/reports/` | 백서용 주장과 보고 원칙 | active |
| `docs/audits/` | 실패 원인, 자가비판, 문헌/정합성/archive 감사 | active |
| `docs/presentations/` | 발표 자료와 생성 근거 | active deliverable |
| `docs/assets/` | 활성 문서가 사용하는 그림 | active assets |

초기 `docs/design/`은 제거했다. 원래 A100 v2 설계는
`archive/superseded_v2_design_20260714/`에 있다.

## Active 문서 목록

| 분류 | 파일 | 역할 |
|---|---|---|
| methodology | `howitworks.md` | 현재 코드와 component pair의 상세 동작 |
| methodology | `component_energy_final_experiment_plan_ko.md` | profile별 sweep, 선택 좌표, acceptance 기준 |
| methodology | `component_energy_method_comparison_ko.md` | raw sweep과 current finalplan 비교 |
| methodology | `ncu_validation_energy_calculation_ko.md` | counter, denominator, pJ/FLOP/pJ/bit 계산 |
| methodology | `external_memory_read_path_experiment_design_ko.md` | HBM/GDDR device energy와 effective path 구분, strict NCU read gate, W sweep |
| methodology | `a100_l2_fabric_aware_experiment_design_ko.md` | GA100 source/LTC-fabric counter 모델, sweep, gate, 계수 해석 |
| results | `gpu_power_modeling_experiment_results_ko.md` | current/historical/provisional 결과 상태 |
| reports | `gpu_power_modeling_whitepaper_synthesis_ko.md` | 백서용 종합 주장 |
| platforms | `README.md` | GPU별 가이드와 package routing |
| platforms | `cross_platform_component_experiment_guide_ko.md` | 공통 실행·검증·반입 절차 |
| platforms | `power_measurement_api_matrix_ko.md` | NVML/nvidia-smi API scope와 semantics |
| platforms | `a100_node_experiment_guide_ko.md` | A100 실행 |
| platforms | `v100_node_experiment_guide_ko.md` | V100 실행 |
| platforms | `h100_node_experiment_guide_ko.md` | H100 실행 |
| audits | `current_goal_alignment_audit_ko.md` | 목표와 코드/문서 gate 정합성 |
| audits | `component_energy_self_critique_ko.md` | 현재 신뢰도와 남은 약점 |
| audits | `a100_strict_summary_failure_remediation_ko.md` | A100 Tensor/L2 실패 교정 |
| audits | `a100_v100_external_result_remediation_ko.md` | A100/V100 pair timing 및 L2 58-72% 외부 결과 교정 |
| audits | `a100_l2_counter_scope_and_rtx_pair_remediation_ko.md` | A100 L2 counter scope와 RTX matched-control 교정 |
| audits | `tensor_mma_cross_architecture_implementation_audit_ko.md` | Tensor v2-v5 오류, v6 runtime-observed control, FLOP/cache 및 GPU별 검증 상태 |
| audits | `a100_tensor_control_calibration_failure_20260715_ko.md` | A100 launch-only control, 10억 ITER, 장시간 run 무효화와 v6 교정 |
| audits | `a100_v100_synthetic_selftest_false_failure_20260716_ko.md` | synthetic ratio 21.930 오인, clean self-test 출력, non-L2/L2 failure isolation |
| audits | `a100_v100_schema_smoke_stop_20260716_ko.md` | schema kernel/power audit/Tensor SASS 중단 구분, toolkit binding, 재실행 증거 |
| audits | `multigpu_sweep_pairing_identity_fix_20260716_ko.md` | `(sweep_source_id, run_id, gpu_id)` 조인, sweep별 control pairing 격리, GPU 0 기본값 |
| audits | `memory_path_cross_architecture_sweep_audit_ko.md` | Shared/Global-L1/L2/external path 논리, exact-NCU coverage, 제거/유지 sweep |
| audits | `v100_l2_iter_mismatch_remediation_ko.md` | V100 L2 동일 ITER 교정 |
| audits | `v100_32gb_platform_review_ko.md` | V100 32GB SKU/toolchain 검토 |
| audits | `literature_energy_values_audit_ko.md` | 문헌값과 측정 경계 비교 |
| audits | `repository_active_archive_audit_ko.md` | repository 분류 근거 |

## 결과 지위

| 결과 | 현재 지위 |
|---|---|
| RTX 3090 fixed-RF v2 Tensor | superseded historical energy evidence; 현행 계수로 인용 금지 |
| RTX 3090 fixed-RF v4 Tensor | rejected; ptxas가 no-MMA control loop를 제거했으므로 이전 NCU acceptance와 energy pair 무효 |
| RTX 3090 fixed-RF v5 Tensor | 2026-07-14 GA102 full package에서 2.140 pJ/FLOP, historical strict accepted; v6 플랫폼 비교에 직접 혼합 금지 |
| A100 fixed-RF v5 Tensor 20260714 | rejected; control 10억 ITER가 약 1 ms에 종료되어 calibration과 energy pair가 무효 |
| Tensor v6 source/package | 새 실행의 현행 protocol; target-node binary/NCU/power gate 통과 전에는 신규 계수 없음 |
| RTX 3090 Shared/Global-L1/L2 | 0.714/0.852/9.078 pJ/bit, strict accepted effective paths |
| RTX 3090 external-memory read | 24.949 pJ/bit, `accepted_effective_path`; physical GDDR6X energy가 아님 |
| 2026-07-08 RTX 3090 component coefficients | historical/provisional; current control/schema gate 미충족 |
| A100/V100 external-memory observations | `11.925 / 8.131 pJ/bit`; user-reported historical candidates, strict rerun required; physical memory-device energy 아님 |
| V100/A100/H100 generated command package | 실행 준비 상태; target-node accepted 결과 증거 아님 |

Current 여부는 파일의 이름이나 숫자 모양이 아니라 같은 profile/tag의 power API,
power-state, NCU treatment/control acceptance, matched detail, reliability, strict summary,
strict audit와 package audit로 판정한다.

## Archive

| 경로 | 내용 |
|---|---|
| `archive/legacy_20260707/` | 초기 decomposition/regression/register 실험 |
| `archive/pre_current_protocol_20260712/` | address-control/exact-NCU 이전 보고서·코드·시각화 |
| `archive/superseded_a100_l2_policy_20260713/` | 폐기된 A100 L2 policy selector |
| `archive/superseded_v2_design_20260714/` | 초기 A100 FP16 v2 상세설계와 feasibility 자산 |
| `archive/failed_preflight_20260713/` | 잘못된 로컬 GPU에서 실행한 target-profile preflight 실패 |

Archive 문서를 인용할 때는 `historical`, `legacy diagnostic`, `superseded` 중 하나를
명시한다.

## 정합성 검사

```bash
python3 scripts/audit_documentation_consistency.py --fail-on-error
```

이 검사는 active/archive local link, canonical path, L2 동일 ITER 정책,
C++/Python profile 수치, 활성 asset 참조를 확인한다. 전체 코드/audit self-test는
`scripts/run_local_readiness_checks.sh`를 사용한다.
