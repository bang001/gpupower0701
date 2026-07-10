# RTX 3090 Tensor RF16 Duration-Scaling Follow-up Report

작성일: 2026-07-08

## 목적

RF=8 duration-scaling은 Tensor incremental coefficient를 약 0.14-0.15 pJ/FLOP로
보여줬다. 하지만 기존 RF=8/16 targeted run에서 RF=16 row는 더 낮았다. 이 문서는
RF=16만 고정하고 10/20/30초 duration sweep을 수행해 낮은 값이 우연한 잡음인지,
reuse 조건에 따른 재현 가능한 lower-side coefficient인지 확인한다.

이 실험은 순수 Tensor Core transistor-level energy를 직접 측정한 것이 아니다.
Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따르며,
최종 분자는 `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분이다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment | `reg_mma` | FP16 WMMA/HMMA 실행 |
| control | `reg_operand_only` | HMMA 없이 register fragment/operand loop 유지 |
| W_SM | 2048 | KiB/SM, Tensor mode에서는 register working set이 아니라 고정 좌표 |
| blocks/SM | 16 | resident blocks per SM |
| active_SM | 82 | SM |
| reuse_factor | 16 | count |
| seconds sweep | 10, 20, 30 | s per command |
| repeats | 5 | count per mode/seconds |
| raw rows | 30 | 2 modes x 3 durations x 5 repeats |
| matched-control rows | 15 | treatment rows matched to nearest control |

## Power API / 상태 Gate

| gate | 결과 | 근거 |
|---|---:|---|
| Power API audit | 30/30 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| fallback power integral | 0 row | `GetPowerUsage` endpoint 적분 미사용 |
| RTX 3090 power semantics metadata | 30/30 `one_sec_average` | profile metadata 일치 |
| Power-state audit | 30/30 `ok` | 평균 전력/endpoint power outlier 없음 |
| SMID check | 30/30 ok | active SM/block 배치 정상 |
| matched-control valid | 15/15 | negative/weak-signal row 없음 |
| reliability audit | `accepted` | medium-high confidence |

## Ratio 결과

| duration bucket | rows | median | min | max | unit | 해석 |
|---|---:|---:|---:|---:|---|---|
| 10 s | 5 | 0.083468 | 0.037287 | 0.135713 | pJ/FLOP | 기존 RF=16 targeted median과 유사 |
| 20 s | 5 | 0.076647 | 0.012220 | 0.095151 | pJ/FLOP | 낮은 RF16 값 재현 |
| 30 s | 5 | 0.063566 | 0.037178 | 0.101034 | pJ/FLOP | duration이 길어져도 RF8 상단으로 올라가지 않음 |
| all RF=16 | 15 | 0.076647 | 0.012220 | 0.135713 | pJ/FLOP | accepted auxiliary, RF16 lower-side |

## Slope 기반 확인

| 방식 | slope | unit | 해석 |
|---|---:|---|---|
| OLS with intercept | 0.058801 | pJ/FLOP | intercept를 허용한 선형 추정 |
| through-origin OLS | 0.071065 | pJ/FLOP | 원점을 강제한 선형 추정 |
| Theil-Sen | 0.053485 | pJ/FLOP | outlier에 비교적 강한 slope |

Slope 추정도 0.053-0.071 pJ/FLOP 범위로, RF=8의 0.144-0.156 pJ/FLOP보다 명확히 낮다.

## RF8 결과와 비교

| 실험 | reuse_factor | rows | median | slope range | unit | verdict |
|---|---:|---:|---:|---:|---|---|
| RF8 duration-scaling | 8 | 15 | 0.143114 | 0.144-0.156 | pJ/FLOP | accepted auxiliary, upper-side |
| RF16 duration-scaling | 16 | 15 | 0.076647 | 0.053-0.071 | pJ/FLOP | accepted auxiliary, lower-side |
| RF8/16 targeted combined | 8, 16 | 12 | 0.106658 | - | pJ/FLOP | accepted blended candidate |
| RF8/16 fixed-ITER combined | 8, 16 | 10 | 0.145635 | - | pJ/FLOP | accepted auxiliary, method sensitivity |

판단:

- RF16 lower-side는 power API, power-state, matched-control, reliability gate를 통과했다.
- 따라서 기존 RF=8/16 combined median이 낮아진 것은 단순 잡음이 아니라 reuse factor
  조건 의존성으로 보는 것이 타당하다.
- 현재 RTX 3090 Tensor는 단일 coefficient로 줄이면 안 된다. 보고서에서는
  **RF16 lower: 약 0.06-0.09 pJ/FLOP**, **RF8 upper: 약 0.14-0.15 pJ/FLOP**로
  분리해서 설명한다.
- 하나의 넓은 범위가 필요하면 `0.06-0.15 pJ/FLOP`라고 쓰되, 이것은 순수 Tensor Core
  회로 상수가 아니라 workload-dependent effective coefficient range다.

## 자가비판

| 한계 | 영향 | 다음 보완 |
|---|---|---|
| RF=8과 RF=16만 duration-scaling 완료 | RF=4 이하 broad sweep 분산 원인은 아직 완전히 분리되지 않음 | RF=4 duration-scaling 또는 fixed-ITER 추가 |
| NCU sidecar 재사용 | 이번 RF16 energy run 자체에 NCU를 붙인 것은 아님 | RF16 조건의 별도 NCU sidecar 수집 가능 |
| board-level numerator | Tensor Core 외 scheduler, issue, register/control, clock state가 섞임 | 항상 effective coefficient로 보고 |
| RF dependence 원인 미분리 | RF가 바뀌면 instruction mix/rate, calibration ITER, thermal/control drift가 함께 변함 | fixed ITER + fixed duration을 동시에 통제하는 paired runner 설계 |

## 산출물

| 역할 | 파일 |
|---|---|
| raw energy CSV | `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708.csv` |
| 10초 matrix | `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708_10s_matrix.csv` |
| 20초 matrix | `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708_20s_matrix.csv` |
| 30초 matrix | `results/raw/rtx3090_tensor_rf16_duration_scaling_20260708_30s_matrix.csv` |
| power API audit | `results/summary/rtx3090_tensor_rf16_duration_scaling_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_tensor_rf16_duration_scaling_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_tensor_rf16_duration_scaling_matched_control_report_20260708.md` |
| component reliability audit | `results/summary/rtx3090_tensor_rf16_duration_scaling_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_tensor_rf16_duration_scaling_instability_audit_20260708.md` |
