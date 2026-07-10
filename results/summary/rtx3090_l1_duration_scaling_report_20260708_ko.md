# RTX 3090 Global L1 Duration-Scaling Check

작성일: 2026-07-08

## 목적

기존 L1 factor sweep은 `load_repeat`를 바꾸는 방식이었다. 하지만 duration-calibrated
runner는 목표 실행 시간에 맞게 `ITER`를 다시 calibrate하므로, `load_repeat`를 키워도
총 L1 byte denominator가 2배씩 증가하지 않는다. 즉 기존 LR sweep은 총 byte sweep이라기보다
instruction mix/rate sweep에 가깝다.

이 확인 실험은 `load_repeat=4`를 고정하고 실행 시간만 10초, 20초, 30초로 바꿔
총 denominator를 키웠다. 목적은 Global L1 hit path의 coefficient가 duration scaling에서도
기존 `0.15 pJ/bit` 수준으로 유지되는지 확인하는 것이다.

## 실험 조건

| component | treatment mode | control mode | W_SM (KiB) | blocks/SM | active_SM | load_repeat | seconds sweep | repeats |
|---|---|---|---:|---:|---:|---:|---|---:|
| Global L1 hit path | `global_l1_load_only` | `clocked_empty` | 16 | 16 | 82 | 4 | 10, 20, 30 s | 5 |

NCU denominator는 기존 factor exact-NCU sidecar의 `global_l1_load_only`,
`W_SM=16 KiB`, `blocks/SM=16`, `load_repeat=4` accepted row를 사용했다.

## Gate 결과

| gate | 결과 |
|---|---:|
| Power API audit | 30/30 `final_candidate` |
| Power-state audit | 30/30 `ok` |
| NCU denominator | `ncu_actual_exact` |
| matched-control detail | 14/15 valid |
| reliability | `accepted_with_caution` |

한 개 negative row가 남았지만, power-state audit에서는 outlier가 없었다. 따라서 이 row는
전력 상태 이상보다는 weak treatment-control signal 또는 nearest-control drift로 해석한다.

## 결과

| seconds | valid/total | median | unit | min | max |
|---:|---:|---:|---|---:|---:|
| 10 | 5/5 | 0.168 | pJ/bit | 0.0907 | 0.287 |
| 20 | 5/5 | 0.151 | pJ/bit | 0.105 | 0.216 |
| 30 | 4/5 | 0.156 | pJ/bit | 0.145 | 0.176 |
| 전체 | 14/15 | 0.156 | pJ/bit | 0.0907 | 0.287 |

회귀 관점에서도 기존 결과와 정합한다.

| regression view | coefficient |
|---|---:|
| median of valid row ratios | 0.156 pJ/bit |
| OLS slope with intercept | 0.147 pJ/bit |
| through-origin OLS slope | 0.158 pJ/bit |
| Theil-Sen median slope | 0.149 pJ/bit |

## 판단

- L1 duration scaling은 기존 factor exact-NCU L1 결과 `0.150 pJ/bit`와 정합한다.
- `load_repeat=16` targeted rerun에서 보였던 큰 negative row는 L1 path 실패라기보다
  power-state outlier였고, duration scaling에서는 같은 종류의 outlier가 나오지 않았다.
- Global L1 coefficient는 여전히 순수 SRAM bitcell energy가 아니라 NCU로 L1 hit path가
  검증된 board-level effective microbenchmark coefficient다.
- 최종 문서에서는 Global L1을 `0.15 pJ/bit` 수준의 accepted-with-caution 값으로 두되,
  LR=16 outlier와 weak-signal row를 함께 명시한다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_l1_duration_scaling_20260708.csv` |
| power API audit | `results/summary/rtx3090_l1_duration_scaling_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_l1_duration_scaling_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_l1_duration_scaling_matched_control_report_20260708.md` |
| power-state filtered matched-control report | `results/summary/rtx3090_l1_duration_scaling_powerstate_filtered_matched_control_report_20260708.md` |
| component reliability audit | `results/summary/rtx3090_l1_duration_scaling_component_reliability_audit_20260708.md` |
| power-state filtered component reliability audit | `results/summary/rtx3090_l1_duration_scaling_powerstate_filtered_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_l1_duration_scaling_instability_audit_20260708.md` |
| power-state filtered instability audit | `results/summary/rtx3090_l1_duration_scaling_powerstate_filtered_instability_audit_20260708.md` |
