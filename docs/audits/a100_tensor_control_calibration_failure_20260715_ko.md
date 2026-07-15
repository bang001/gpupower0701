# A100 Tensor control calibration 장시간 실패 감사

작성일: 2026-07-15
대상: `a100_component_finalplan_20260714` Tensor energy run

## 1. 결론

해당 A100 run의 Tensor 구간은 정상적인 장시간 측정이 아니다.
`reg_operand_only` control의 반복 work가 A100 `sm_80` 코드에서 사실상
제거되었고, 이 약 1 ms launch time을 기준으로 10억 회 이상의
`ITER`가 산출되었다. 같은 `ITER`를 실제 MMA treatment에 적용하면
명령 하나가 35-71분 걸린다. 이 실패로 생성된 Tensor energy row는
pJ/FLOP 계수에 사용하지 않는다.

## 2. 관측 값과 판정

| 항목 | 관측값 | 산술/해석 |
|---|---:|---|
| CSV completed rows | 448 rows | NVML-visible GPU가 4개이므로 `448 / 4 = 112` 완료 command |
| shell progress | `[113/150]` | 다음 명령 진입 상태와 일치 |
| Tensor wall span | 16.719 h | 정상 목표시간이 아님 |
| active elapsed median | 31.039 s | 이미 몇 개의 장시간 outlier에 영향받음 |
| active elapsed maximum | 4,280.324 s | 약 71.3 min/command |
| control, B32/RF8 | `ITER=1,047,022,600`, 0.001155 s | 10억 회 work가 1 ms에 완료될 수 없으므로 launch-only에 가까움 |
| treatment, B32/RF8 | 동일 ITER, 2,096.514 s | 약 34.9 min/command; 잘못된 control ITER 전파 |

`448 rows`를 `448 commands`로 해석하면 안 된다. 현재 harness는 한 명령에서
NVML에 보이는 모든 GPU의 row를 기록한다. command 수를 세려면 대상
`gpu_id`를 고정하거나 `notes` 내 `gpu_active=1`만 필터링해야 한다.

## 3. 근본 원인

1. v5 control은 scalar sink를 출력에 저장했지만, GA100의 ptxas가
   내부 no-MMA work를 `ITER`/RF에 비례하는 루프로 남기지 않았다.
2. 기존 calibration은 10번 시도 후에도 trial runtime이 50 ms에 도달하지
   못했을 때 실패하지 않고 launch overhead에서 외삽했다.
3. pair resolver는 control-derived `ITER`가 treatment 실행시간을 몇 배로
   늘릴지 검사하지 않았다.
4. 개별 energy command wall-time 제한이 없어 이상 좌표가 전체 run을
   십수 시간 점유했다.
5. 기존 static audit의 backward-branch 존재 확인만으로는 우리가 의도한
   runtime-dependent control work가 그 루프 안에 남았는지 증명하지 못했다.

## 4. v6 재발 방지 설계

현재 revision은
`matched_runtime_clock_observed_control_fixed_rf_v6`이다.

| 개선 | 구현 | 실패 방지 의미 |
|---|---|---|
| runtime-observed control | treatment/control inner step 모두에 `SR_CLOCKLO` register token을 읽고 scalar dependency에 연결 | memory traffic 없이 ptxas의 loop 제거 방지 |
| stronger SASS audit | RF1/2/4/8/16의 treatment/control 모두에서 `SR_CLOCKLO` read가 backward-loop 내에 있는지 확인 | epilogue branch를 work loop로 오인하지 않음 |
| calibration runtime floor | 최종 trial이 `>=0.05 s`에 도달하지 못하면 즉시 실패 | 1 ms launch overhead 외삽 금지 |
| manifest evidence | trial ITER/time, control/treatment ITER ratio, predicted treatment time 기록 | 사후 계수 audit 가능 |
| stretch gate | 예상 treatment time이 목표의 6배를 초과하면 energy 수집 전 reject | 잘못된 pair-lock 차단 |
| command guard | 표준 finalplan의 개별 energy command를 180 s에 종료 | 잔여 장시간 실패 차단 |

`SR_CLOCKLO` read는 순수 Tensor 회로의 일부가 아니다. 두 mode에 동일하게
넣어 제거하려는 matched-control 장치이며, 남은 비대칭성과 실행시간
차이 때문에 결과는 여전히 **effective board-level Tensor-path increment**이지
순수 Tensor silicon energy가 아니다.

## 5. 기존 run의 사용 범위

| 데이터 | 판정 |
|---|---|
| `a100_component_finalplan_20260714` Tensor raw/calibration | rejected, 계수 산출 금지 |
| 해당 run의 Tensor NCU | energy pair와 프로토콜이 다르므로 최종 pJ/FLOP 증거 금지 |
| 같은 tag의 다른 component | 독립 power/NCU/pair gate를 완료한 row만 별도 판정; 미완료 run을 final package로 보고하지 않음 |
| RTX 3090 v5 20260714 | GA102에서 통과한 historical protocol result로 보존; v6 플랫폼 비교에 직접 혼합 금지 |

## 6. A100 재실행 절차

1. 현재 실행은 `Ctrl-C`로 중단한다.
2. 소스를 업데이트한 뒤 `build-a100` 디렉터리를 clean rebuild한다.
3. target A100에서 Tensor binary audit 10/10 pass를 확인한다.
4. 새 날짜 tag의 command package를 생성해 실행한다. 구형
   `20260714` shell을 재개하지 않는다.
5. energy 수집 전에 생성된 `*_tensor_pair_calibration.csv`를 열어 아래
   기준을 확인한다.

| 사전 gate | 통과 기준 |
|---|---:|
| `treatment_trial_elapsed_s` | `>= 0.05 s` |
| `control_trial_elapsed_s` | `>= 0.05 s` |
| `control_to_treatment_iter_ratio` | `<= 6.0` |
| `predicted_treatment_seconds` | `<= target_seconds x 6` |
| `status` | `pair_locked` |
| Tensor raw `elapsed_s` | control가 launch-only 수준이 아니고 analyzer의 control floor 통과 |
| 개별 command | `<= 180 s`; timeout은 계속 진행 사유가 아니라 run reject 사유 |

Target-node 최종 확인에서는 `reg_operand_only` HMMA=0,
`reg_mma` HMMA>0, spill/local=0, RF별 HMMA/FLOP 선형성과 두 mode의
runtime-token loop를 모두 통과해야 한다.

## 7. 수정본 로컬 검증

2026-07-15에 현재 소스를 `sm_86`, `sm_80`, `sm_90`으로 각각 빌드했다.
세 바이너리의 Tensor static audit는 모두 10/10 pass였다. 특히 A100용
`sm_80` SASS에서 RF1/2/4/8/16 모두 control HMMA=0, treatment HMMA>0,
local/spill allocation=0, treatment/control runtime-token loop 존재를 확인했다.

A100용 `sm_80` 바이너리를 로컬 RTX 3090에서 실행한 B16/RF8 짧은
runtime smoke 결과는 다음과 같다. 이 값은 계수가 아니라 장시간 실패가
재발하지 않는지 확인한 실행 증거다.

| mode | calibration target | final trial ITER | final trial time | calibrated ITER |
|---|---:|---:|---:|---:|
| `reg_operand_only` | 1 s | 180,160 | 0.0584 s | 3,392,219 |
| `reg_mma` | 1 s | 37,390 | 0.0542 s | 758,751 |

control ITER 3,392,219를 treatment에 고정 적용한 추가 smoke의 active
elapsed는 4.369 s였다. 같은 조건에서 예상한 약 4.47 s와 가깝고 6배
stretch gate 안이다. 이는 과거처럼 launch-only control에서 수십 분짜리
treatment를 만드는 실패가 로컬에서 차단되었음을 보인다.

단, RTX 3090 runtime smoke는 실제 GA100 전력 결과를 대신하지 않는다.
최종 A100 판정은 target node에서 clean build한 뒤 calibration manifest,
SASS audit, NCU runtime count, NVML energy를 새 tag로 다시 수집해야 한다.
