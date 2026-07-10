# Component Energy 실험 자가비판

작성일: 2026-07-06, updated 2026-07-10

## 1. 가장 큰 오류

| 오류 | 왜 문제였나 | 현재 수정 |
|---|---|---|
| `W_SM`을 `reg_mma` register working set처럼 설명 | register footprint는 `W_SM`이 아니라 ptxas register/thread, threads/block, blocks/SM로 결정된다. | register-mode에서 `W_SM`은 고정 좌표로만 취급한다. |
| `reg_pressure` direct pJ/update를 register energy처럼 해석 | scalar ALU, dependency chain, scheduler/control, active power가 포함된다. | register 결과는 `register/control diagnostic only`로 격하했다. |
| 일반 `l2_load_only`를 RTX 3090 L2로 해석 | NCU에서 L1 hit가 높아 L2-only가 아니었다. | RTX 3090/V100 L2는 `l2_cg_load_only`를 우선 사용한다. |
| `shared_load_only`를 clean shared path로 사용 | NCU에서 bank conflict가 컸다. | `shared_scalar_load_only`를 primary shared path로 사용한다. |
| static expected bytes로 pJ/bit 계산 | 실제 L1/L2/DRAM sector traffic과 다를 수 있다. | NCU actual-byte denominator를 분석에 반영했다. |
| 음수 coefficient를 늦게 문제 삼음 | control mismatch와 power-state noise가 있다는 직접 증거다. | 음수 row는 final coefficient에서 제외한다. |
| 작은 양수 coefficient를 무조건 채택 | `delta_E`가 board-level baseline 대비 너무 작으면 양수라도 noise floor 안의 값일 수 있다. | `nearest-control` pairing과 `--min-delta-j`, `--min-delta-fraction` gate를 추가했다. |
| HBM2 physical pJ/bit와 RTX 3090 GDDR6X path를 섞어 비교 | device-level DRAM energy와 GPU transaction-path effective energy는 의미가 다르다. | DRAM은 streaming sanity로만 보고한다. |
| GPU 세대별 power API 의미를 결과 gate에 늦게 반영 | `GetPowerUsage`가 instant인지 1초 평균인지, total energy counter인지에 따라 신뢰도가 달라진다. | `power_measurement_api_matrix_ko.md` 작성, analyzer에 `--require-total-energy`와 `--expected-power-semantics` gate 추가 |

## 2. 현재 코드/분석에서 여전히 약한 부분

| 약점 | 영향 | 필요한 추가 실험 |
|---|---|---|
| 기존 RTX 3090 strict NCU sidecar가 representative LR=4 중심 | 모든 load_repeat/reuse row의 actual traffic을 직접 검증하지 못했다. | 2026-07-08 factor sidecar로 RTX 3090 stability factor set은 `ncu_actual_exact` 재산출 완료 |
| Shared/L1 일부 row가 negative 또는 weak-signal | path는 NCU로 맞아도 board-level treatment-control delta가 작아 noise floor에 걸린다. | strict gate로 제외하고, 다음 단계에서 더 matched된 control 설계 |
| Tensor acceptance threshold가 absolute byte 기준이었다 | SM 수와 reuse factor가 커질 때 정상적인 setup/cache traffic도 absolute byte만으로 커 보인다. | bytes/HMMA, bytes/register-op ratio gate를 추가 |
| `clocked_empty` control이 모든 memory path에 완전 matched가 아님 | 일부 L1 row에서 음수/큰 분산이 발생한다. | address-only/control instruction mix를 더 맞춘 pair 추가 |
| L1/shared의 board-level delta signal이 작음 | 긴 run에서도 일부 반복은 `delta_E`가 10 J 미만 또는 0.5% 미만이다. | strict report에서는 weak-signal row를 제외하고, 다음 단계에서 matched control을 개선 |
| NVML energy source가 GPU별로 다름 | `GetPowerUsage` semantics와 energy counter support가 다르다. | 결과 표에 `energy_source`, `energy_integration_method`, `nvml_power_usage_semantics`를 포함하고, fallback row는 provisional로 제한 |
| H100에서 Hopper-native 경로 미구현 | WGMMA/TMA/FP8 energy를 측정하지 않는다. | 별도 H100-native kernel set 설계 |
| V100 NCU 지원 버전 이슈 | NCU hit/stall 검증이 실패할 수 있다. | 지원되는 NCU toolchain 명시, 실패 시 energy-only로 분리 보고 |
| V100 build compiler를 target 검증 없이 사용 | CUDA 13은 Volta offline compilation을 제거해 `sm_70` configure가 실패한다. 기존 preflight는 compiler target을 검사하지 않았다. | CUDA 12.x를 권장하고 `nvcc --list-gpu-arch`의 `compute_70`을 strict preflight gate로 추가 |
| 외부 package audit가 함수 인자 대신 CLI 전역 `args`를 참조 | self-test와 V100 결과 intake가 `NameError`로 중단될 수 있었다. | `audit_package()`의 `profile` 인자를 사용하도록 수정하고 package gate self-test에 CUDA compiler gate/NCU control-mode fixture를 보강 |
| V100 Global L1 NCU를 W8/B16으로 생성 | block당 0.5 KiB라 harness의 최소 1 KiB tile 조건을 위반해 sidecar가 시작 전에 실패한다. | strict Global L1을 W32/B32로 변경하고 planner coordinate validation 추가 |
| V100 L2를 W64=5 MiB 단일점으로 사용 | 6 MiB L2의 약 83%라 background traffic/set conflict에 민감하고 residency margin이 작다. | strict W32=2.5 MiB와 W64 stress point를 분리 |

## 3. 현재 믿을 수 있는 것과 없는 것

| 항목 | 현재 신뢰도 | 이유 |
|---|---|---|
| NCU accepted path가 의도한 memory hierarchy를 탔다 | 높음 | hit rate, bytes, stall, bank conflict로 확인 가능 |
| RTX 3090 finalplan의 계층 순서 L1/shared < L2 < DRAM | 중간 이상 | NCU actual-byte denominator, total-energy gate, nearest-control strict gate 기반 |
| RTX 3090 finalplan energy numerator | 중간 이상 | 2026-07-07 재점검에서 final row와 smoke 모두 `nvml_total_energy` + `total_energy_mj_delta` 확인. 다만 board-level effective energy 한계는 남음 |
| Tensor incremental pJ/FLOP | 낮음-중간 | HMMA와 no-MMA control은 있으나 pure Tensor 단독은 아니고, 2026-07-08 strict 반복에서 confidence_class가 low로 나왔다. |
| L1/shared pJ/bit | 중간 | strict gate 후 hierarchy는 맞지만 board-level delta signal이 작고 confidence_class는 medium 수준이다. |
| Register file pJ/access | 낮음 | 현재 구현은 pure RF isolation이 아니다 |
| Physical DRAM device pJ/bit | 낮음 | NVML board-level streaming delta일 뿐이다 |

## 4. 플랫폼 확장 시 원칙

| 원칙 | 이유 |
|---|---|
| RTX 3090 결과를 A100/V100/H100에 이식하지 않는다. | cache/shared/L2/memory/NVML semantics가 다르다. |
| 각 플랫폼에서 preflight와 NCU acceptance를 먼저 본다. | profile 가정과 실제 노드 상태가 다를 수 있다. |
| `l2_load_only`는 NCU L1 hit가 낮을 때만 채택한다. | capacity 계산만으로는 L2-only가 보장되지 않는다. |
| H100 결과는 WMMA compatibility path라고 명시한다. | H100 native WGMMA/TMA와 다르다. |
| 최종 표에는 rejected row와 이유를 함께 남긴다. | 수치를 숨기면 설계 실패를 확인할 수 없다. |
| `energy_source=legacy_get_power_usage_integral` row는 final coefficient에서 제외한다. | endpoint power fallback은 GPU 세대별 sampling semantics에 민감하다. |

## 5. 다음 코드 개선 제안

| 우선순위 | 개선 | 목적 |
|---:|---|---|
| 1 | A100/V100/H100에서 bytes/HMMA, bytes/register-op ratio gate 검증 | RTX 3090에서 absolute threshold 왜곡을 완화했으므로 다른 GPU에도 적용 |
| 2 | factor-list NCU sidecar로 A100/V100/H100 재실행 | RTX 3090과 같은 `ncu_actual_exact` 기준을 다른 architecture에 적용 |
| 3 | L1/global control용 `global_addr_load_control` 추가 | `clocked_empty` mismatch 축소 |
| 4 | bootstrap/CI-style confidence interval report 추가 | L1/shared처럼 산포가 큰 coefficient의 신뢰구간 명시 |
| 5 | fallback power row 전용 polling/integration runner 추가 | total energy counter가 없는 플랫폼에서 provisional 분석 품질 개선 |
| 6 | H100-native WGMMA/TMA mode 추가 | Hopper 구조 반영 |
| 7 | report generator 추가 | 플랫폼별 결과 표준화 |
