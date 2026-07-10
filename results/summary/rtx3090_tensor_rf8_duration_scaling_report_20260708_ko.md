# RTX 3090 Tensor RF8 Duration-Scaling Follow-up Report

작성일: 2026-07-08

## 목적

Tensor MMA incremental coefficient는 기존 RF=8/16 targeted run에서
`0.106658 pJ/FLOP`, fixed-ITER 보조실험에서 `0.145635 pJ/FLOP`로 나왔다. 두 값이
같은 order지만 차이가 있으므로, RF=8만 고정하고 실행시간을 10/20/30초로 늘려
duration scaling에 따른 안정성을 확인했다.

이 실험은 순수 Tensor Core 회로 에너지를 직접 측정한 것이 아니다. Power API 해석은
`docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다. 최종 분자는
`nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분이며, RTX 3090의
`GetPowerUsage` 1초 평균 fallback은 coefficient 분자로 쓰지 않았다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment | `reg_mma` | FP16 WMMA/HMMA 실행 |
| control | `reg_operand_only` | HMMA 없이 register fragment/operand loop 유지 |
| W_SM | 2048 | KiB/SM, Tensor mode에서는 register working set이 아니라 고정 좌표 |
| blocks/SM | 16 | resident blocks per SM |
| active_SM | 82 | SM |
| reuse_factor | 8 | count |
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
| Power-state audit | 29/30 `ok`, 1/30 `caution` | 첫 10초 control row의 temperature outlier |
| SMID check | 30/30 ok | active SM/block 배치 정상 |
| matched-control valid | 15/15 | negative/weak-signal row 없음 |
| reliability audit | `accepted` | medium-high confidence |

Power-state caution은 첫 10초 control row의 낮은 온도에서 나온 warm-up 성격의
metadata다. 해당 row도 coefficient gate에서는 유효했지만, 10초 bucket 자체가 더
흔들리므로 최종 해석에서는 20/30초 bucket과 slope를 함께 본다.

## Ratio 결과

| duration bucket | rows | median | min | max | unit | 해석 |
|---|---:|---:|---:|---:|---|---|
| 10 s | 5 | 0.106437 | 0.035869 | 0.176541 | pJ/FLOP | 짧은 duration이라 분산이 큼 |
| 20 s | 5 | 0.150594 | 0.115328 | 0.209237 | pJ/FLOP | fixed-ITER 보조값과 가까움 |
| 30 s | 5 | 0.131535 | 0.125206 | 0.159923 | pJ/FLOP | 분산이 줄고 0.13-0.16 범위에 모임 |
| all RF=8 | 15 | 0.143114 | 0.035869 | 0.209237 | pJ/FLOP | accepted auxiliary |

## Slope 기반 확인

단순 row별 `delta_E / FLOP` 외에, denominator와 `delta_E`의 관계에서 slope를 계산했다.

| 방식 | slope | unit | 해석 |
|---|---:|---|---|
| OLS with intercept | 0.155595 | pJ/FLOP | intercept를 허용한 선형 추정 |
| through-origin OLS | 0.144237 | pJ/FLOP | 원점을 강제한 선형 추정 |
| Theil-Sen | 0.154667 | pJ/FLOP | outlier에 비교적 강한 slope |
| bucket-median Theil-Sen | 0.151715 | pJ/FLOP | duration bucket 중앙값 기반 |
| bucket-median OLS | 0.152047 | pJ/FLOP | duration bucket 중앙값 기반 |

Slope 추정은 0.144-0.156 pJ/FLOP에 모인다. 따라서 RF=8 조건에서는 Tensor incremental
coefficient를 약 0.14-0.15 pJ/FLOP로 보는 것이 10초 단독 median보다 타당하다.

## 기존 Tensor 결과와의 비교

| 실험 | 조건 | rows | median | unit | verdict |
|---|---|---:|---:|---|---|
| Broad factor exact-NCU | RF=1,2,4,8,16, 5 s, 3 repeats | 15 | 0.169745 | pJ/FLOP | `accepted_low_stability` |
| Targeted RF=8/16 | duration-calibrated, 20 s, 6 repeats | 12 | 0.106658 | pJ/FLOP | `accepted`, lower-side candidate |
| Fixed-ITER RF=8/16 | fixed `ITER=8000000`, 5 repeats | 10 | 0.145635 | pJ/FLOP | `accepted_auxiliary` |
| RF=8 duration-scaling | 10/20/30 s, 5 repeats each | 15 | 0.143114 | pJ/FLOP | `accepted_auxiliary` |

판단:

- RF=8만 보면 duration scaling과 fixed-ITER 결과가 0.14-0.16 pJ/FLOP 부근으로 정합한다.
- RF=16을 섞은 targeted RF=8/16 combined median은 0.107 pJ/FLOP로 낮아진다.
- 따라서 Tensor 값을 `0.107 pJ/FLOP` 단일값으로만 쓰면 RF/policy dependence를 숨긴다.
- RF=16 duration-scaling follow-up은 0.077 pJ/FLOP median과 0.053-0.071 pJ/FLOP
  slope로 통과했다. 따라서 현재 보고서는 Tensor를 단일 range/상수로 고정하지 않고,
  RF=8 upper 약 0.14-0.15 pJ/FLOP와 RF=16 lower 약 0.06-0.09 pJ/FLOP로 분리한다.
  RF=8 duration-scaling은 이 RF-dependent range의 상단을 지지하는 auxiliary evidence다.

## 자가비판

| 한계 | 영향 | 다음 보완 |
|---|---|---|
| RF=8만 duration sweep | RF=16에서 낮아지는 원인을 직접 분리하지 못함 | RF=16도 10/20/30초 duration-scaling으로 추가 확인 |
| NCU sidecar 재사용 | 이번 30초 energy run 자체에 NCU를 붙인 것은 아님 | RF=8 조건의 별도 NCU sidecar를 수집하면 더 강함 |
| board-level numerator | Tensor Core 외 scheduler, issue, register/control, clock state가 섞임 | 항상 effective coefficient로 보고 |
| 첫 10초 control temperature caution | 10초 bucket 분산 해석에 주의 필요 | warm-up 후 20/30초 중심으로 해석 |

## 산출물

| 역할 | 파일 |
|---|---|
| raw energy CSV | `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708.csv` |
| 10초 matrix | `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708_10s_matrix.csv` |
| 20초 matrix | `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708_20s_matrix.csv` |
| 30초 matrix | `results/raw/rtx3090_tensor_rf8_duration_scaling_20260708_30s_matrix.csv` |
| power API audit | `results/summary/rtx3090_tensor_rf8_duration_scaling_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_tensor_rf8_duration_scaling_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_tensor_rf8_duration_scaling_matched_control_report_20260708.md` |
| component reliability audit | `results/summary/rtx3090_tensor_rf8_duration_scaling_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_tensor_rf8_duration_scaling_instability_audit_20260708.md` |
