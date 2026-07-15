# Component Energy 실험 자가비판

갱신일: 2026-07-15

## 현재 판정

RTX 3090은 2026-07-14 v5 package에서 Tensor, Shared scalar, Global L1, L2
strict table과 별도 external-memory effective path를 생성했다. Fresh runtime NCU,
board-energy, reliability, strict-summary, package audit가 모두 통과했다. 따라서
이 결과는 GA102 v5 protocol-specific accepted evidence로 보존한다.

다만 A100에서 v5 control이 launch-only로 남아 과대 ITER와 16시간 이상
run을 만든 portability 실패가 2026-07-15 확인됐다. 따라서 현행 source
protocol은 v6이며, RTX 3090 v5 결과를 v6 교차 플랫폼 계수로
취급하지 않는다.

다만 V100/A100/H100은 코드와 command package만 준비됐고, 각 target node의 accepted
전체 package가 저장소에 반입되지 않았다. RTX 3090 결과도 pure circuit energy가
아니며, 특히 Tensor treatment/control register footprint가 완전히 같지 않다.

따라서 “코드가 구현됐다”, “NCU path가 통과했다”, “component coefficient가 확정됐다”를
서로 다른 상태로 구분한다.

## 발견한 주요 오류와 현재 조치

| 과거 오류 | 왜 문제였나 | 현행 조치 | 남은 증거 |
|---|---|---|---|
| `W_SM`을 `reg_mma` register working set으로 설명 | register footprint는 ptxas registers/thread와 residency로 결정 | register mode에서 W_SM은 표준 좌표로만 보고 spill/local=0 확인 | 플랫폼별 ptxas/NCU resource 재확인 |
| `reg_pressure` pJ/update를 RF energy로 해석 | scalar ALU, dependency, scheduler, clock가 함께 변함 | diagnostic/control proxy로만 유지 | pure RF 분리는 별도 ISA/control 설계 필요 |
| 일반 `l2_load_only`를 L2-only로 간주 | RTX 3090에서 L1 hit가 높았음 | `l2_cg_load_only`와 path-specific counter 사용 | GPU별 exact-coordinate NCU 필요 |
| `shared_load_only`를 clean shared path로 간주 | bank conflict가 커 경로가 오염됨 | `shared_scalar_load_only`를 primary로 선택 | bank conflict와 global leakage 계속 보고 |
| expected bytes만으로 pJ/bit 계산 | 실제 transaction 수와 다를 수 있음 | strict memory row는 `ncu_actual_exact` 요구 | metric availability와 sector 단위 GPU별 확인 |
| Global L1/L2에 `clocked_empty` control 사용 | 주소 생성과 global loop 비용이 treatment에만 남음 | `global_addr_only` exact-coordinate control로 변경 | RTX 3090 통과; 외부 플랫폼 재실행 |
| Tensor mode별 독립 ITER | control/treatment logical work가 달라질 수 있음 | RF별 dual calibration의 최대 동일 ITER | 플랫폼별 새 raw/calibration manifest |
| v4/v5 Tensor control portability | v4 loop는 제거됐고, v5 output sink는 GA102에서 통과했지만 A100에서 10억 ITER가 약 1 ms에 종료 | v6에 공통 runtime clock token, static token-loop, 50 ms trial, 6x stretch, 180 s timeout 추가 | RTX/A100/V100/H100 target-node v6 fresh power/NCU |
| V100 L2 mode별 독립 ITER | NCU L2 hit는 통과했지만 control ITER가 약 2배라 9개 음수 | L2 동일 ITER, direct net-energy 차분, mismatch hard reject | V100 L2 energy와 downstream package 재실행 |
| DRAM duration-scaled pair | address control과 treatment work count가 다를 수 있음 | DRAM도 동일 ITER 직접 차분 | DRAM은 strict 4-component 표 밖 sanity로 유지 |
| 음수 또는 작은 양수를 결과로 승격 | drift/noise/control mismatch 신호일 수 있음 | negative, minimum delta/fraction, power-state gate 적용 | 반복과 confidence interval 계속 필요 |
| 문헌값에 맞춰 숫자 선택 | 측정 경계가 다른 값을 fitting하면 검증이 아님 | 문헌값은 order-of-magnitude sanity로만 사용 | path/device/board 경계 명시 |

## 현재 신뢰할 수 있는 범위

| 주장 | 신뢰 수준 | 근거와 제한 |
|---|---|---|
| 코드가 RTX 3090/V100/A100/H100 profile과 finalplan을 생성함 | 높음, 정적 구현 | profile/preflight/planner audit과 self-test 기준; target-node 실행 성공과는 다름 |
| historical RTX 3090 NCU가 Shared/L1/L2/DRAM 방향의 path를 보여줌 | 높음, 역사적 path evidence | current control acceptance와 새 binary revision 전체를 보증하지 않음 |
| RTX 3090 fixed-RF v2 Tensor median 2.252501 pJ/FLOP | historical only | 당시 power/NCU pair gate는 통과했지만 accumulator 정체 가능성 때문에 superseded |
| RTX 3090 fixed-RF v4 Tensor path/FLOP | 무효 | treatment counter는 선형이었지만 control이 launch-only여서 pair 검증 실패 |
| RTX 3090 v5 Tensor 2.140 pJ/FLOP | medium-high, historical GA102 effective coefficient | GA102 static control loop, runtime HMMA/SASS/spill, 75/75 pair 및 strict/package audit 통과; v6과 혼합 금지 |
| A100 v5 Tensor 20260714 | 무효 | launch-only control과 과대 pair-locked ITER; Tensor energy row 전체 reject |
| Cross-platform Tensor v6 | 미확정 | local sm86/sm80/sm90 static audit는 통과했지만 target-node fresh power/NCU 필요 |
| RTX 3090 Shared/L1/L2 0.714/0.852/9.078 pJ/bit | medium-high, current effective paths | address control, NCU actual denominator, 60/60 pair 및 strict/package audit 통과; SRAM bitcell energy는 아님 |
| V100 L2 구형 음수 계수 | 무효 | NCU path 성공과 별개로 ITER mismatch |
| RTX 3090 external-memory 24.949 pJ/bit | medium-high, accepted effective path | 45/45 pair와 read-path NCU 통과; strict 4-component 밖이며 physical GDDR6X energy 아님 |
| A100/V100 external-memory 11.925/8.131 pJ/bit | historical/user-reported | current raw package 미확보; 재실험 전 final 사용 금지 |
| Register file pJ/access | 미확정 | 현재 kernel로 RF 단독 분리가 불가능 |
| Physical HBM/GDDR energy | 미확정 | NVML GPU/device-level path delta의 경계 밖 |

## 현행 Hard Gate가 해결하는 것

| Gate | 방지하는 오류 | 해결하지 못하는 것 |
|---|---|---|
| strict preflight | 잘못된 GPU/profile/toolchain/NCU 실행 | target node의 장기 drift |
| explicit total-energy scope | fallback/module/memory power 혼입 | GPU 내부 component 단독 측정 |
| treatment/control exact NCU acceptance | 오염된 control 또는 잘못된 path | replay run과 energy run의 완전 동일성 |
| NCU actual denominator | static byte 계산 오류 | metric 자체의 architecture 차이 |
| 모든 final pair의 matched ITER | 서로 다른 logical work 차분 | 두 mode의 elapsed/power-state 차이 |
| min delta 및 power-state audit | noise floor와 throttling 일부 | 모든 thermal/order effect |
| strict/package/goal audit | 누락 artifact와 stale 결과 승격 | gate가 모델의 물리적 순수성을 보증하지는 않음 |

## 아직 약한 부분

| 약점 | 영향 | 필요한 후속 작업 |
|---|---|---|
| Shared/Global L1은 같은 unified L1/shared 자원을 일부 공유하지만 coefficient가 다름 | instruction/address-space, arbitration, denominator와 stall이 달라 순수 SRAM 비교가 아님 | RTX 3090 matched-address/동일 ITER 결과의 겹치는 CI를 보고하고 path coefficient로만 해석 |
| Tensor control도 scheduler/register/final-store가 완전히 같지 않고 v6 runtime token이 있음 | coefficient에 Tensor 외 증분이 남으며 token/MMA overlap이 다를 수 있음 | SASS, registers/thread, operation-proportional counter, elapsed/power 비교 유지 |
| L2/DRAM matched ITER에서 elapsed가 다름 | 같은 work여도 clock/temperature 상태가 다를 수 있음 | control floor, pair adjacency, repeats, power-state filtering |
| A100 L2 source 51-62%, native 67-72.5% | source와 lookup-level native에 동일 95% gate를 적용해 remote-partition recovery를 놓침 | B16/B8/B4/B2/B1 sweep에서 source+`srcunit_ltcfabric` logical final hit, native-model, DRAM read를 검증; logical 95% plateau가 없으면 energy 전에 중단 |
| V100 NCU/CUDA 버전 제약 | permission/toolchain 실패가 coefficient 누락으로 이어짐 | CUDA 12.x `compute_70`, GV100 metric query, sudo fallback 확인 |
| H100 native 경로 미구현 | WMMA 결과를 WGMMA/TMA/FP8로 확대 해석할 위험 | 별도 Hopper-native kernel/control/counter 설계 |
| 여러 profile 정의가 C++/Python에 중복 | 수정 시 drift 가능 | `audit_documentation_consistency.py`와 platform readiness를 계속 gate로 사용 |

## 플랫폼 확장 원칙

| 원칙 | 이유 |
|---|---|
| RTX 3090 coefficient를 다른 GPU에 복사하지 않는다 | SM, cache/shared/L2, memory, NVML/NCU 의미가 다름 |
| 각 GPU에서 strict preflight 후 실행한다 | profile/SKU/MIG/vGPU/toolchain을 정적으로 보장할 수 없음 |
| Energy run과 NCU replay를 분리한다 | profiler overhead를 energy numerator에 넣지 않기 위해서 |
| Sweep과 선택 좌표를 단위 포함 표로 남긴다 | 어떤 W/B/RF/LR가 채택됐는지 재현하기 위해서 |
| rejected row와 이유를 결과에 포함한다 | 설계 실패를 숨기지 않기 위해서 |
| 숫자 hierarchy가 그럴듯해도 gate를 우회하지 않는다 | plausible value가 valid measurement를 뜻하지 않음 |

## 다음 우선순위

1. A100 v6 Tensor calibration smoke, static token-loop, fresh NCU/power package를 먼저 통과한다.
2. V100은 CUDA 12.x target node에서 v6 Tensor static/runtime gate와 L2 동일 ITER를 함께 재실행한다.
3. A100 targeted L2 precheck에서 logical final-service hit/byte-conservation plateau를 확보한다.
4. 각 외부 플랫폼에서 min/median/mean/max와 rejected 좌표를 단위 포함 표로 작성한다.
5. RTX 3090 v6를 재실행해 v5 계수에 runtime-token protocol이 미친 영향을 분리한다.
6. H100 native WGMMA/TMA/FP8는 현재 WMMA 실험과 별도 연구 축으로 설계한다.
