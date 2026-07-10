# RTX 3090 Global L1 30초 안정성 추가 점검

작성일: 2026-07-08

## 목적

기존 Global L1 duration-scaling 결과는 `0.156 pJ/bit` 수준으로 기존 L1 후보값과
정합했지만, 15개 matched-control row 중 1개 음수 row가 남아 있었다. 이 추가 실험은
같은 조건을 30초로 고정하고 반복 수를 10회로 늘려, 음수 row가 사라지는지와 L1
coefficient가 기존 값과 같은 범위에 머무는지를 확인하기 위한 안정성 점검이다.

## 실험 조건

| 항목 | 값 |
|---|---|
| GPU/profile | RTX 3090 / `rtx3090` |
| component | Global L1 hit path |
| treatment mode | `global_l1_load_only` |
| control mode | `clocked_empty` |
| W_SM | 16 KiB |
| blocks/SM | 16 |
| active_SM | 82 SM |
| load_repeat | 4 |
| seconds | 30 s |
| repeats | 10 |
| denominator | NCU `global_l1_load_only_W16_B16_LR4` 대표 L1 bytes |

## Power API 및 상태 점검

| gate | 결과 | 해석 |
|---|---:|---|
| raw rows | 20 | treatment 10개, control 10개 |
| Power API audit | 20/20 `final_candidate` | 모두 `nvml_total_energy + total_energy_mj_delta` |
| `nvml_power_usage_semantics` | `one_sec_average` | RTX 3090 profile과 일치. 단, final numerator는 total-energy counter |
| Power-state audit | 20/20 `ok` | clock/temperature/power-limit outlier 없음 |
| SMID 검증 | 20/20 ok | active SM 배치 이상 없음 |

## NCU 경로 검증

기존 factor-stability NCU sidecar의 동일 좌표를 denominator로 사용했다.

| metric | 값 | 의미 |
|---|---:|---|
| L1 hit rate | 99.9982 % | global load가 거의 L1 hit로 끝남 |
| L1 bytes | 1.07479e12 bytes | pJ/bit denominator의 기준 |
| L2 bytes | 5.92794e8 bytes | L1 bytes 대비 매우 작음 |
| DRAM bytes | 4.52661e8 bytes | L1 bytes 대비 매우 작음 |
| stall long scoreboard | 17.4469 % | load path stall이 존재하므로 순수 L1 SRAM energy가 아님 |

## Matched-control 결과

| 항목 | 값 |
|---|---:|
| valid rows | 9/10 |
| invalid rows | 1/10 |
| median | 0.152768827798 pJ/bit |
| min valid | 0.093695899933 pJ/bit |
| max valid | 0.167966693886 pJ/bit |
| 95% median CI | 0.117940151997-0.167549992202 pJ/bit |
| confidence | medium-high |
| reliability verdict | accepted_with_caution |

무효 row의 원인은 `delta_E=-2.754 J`, `delta_fraction=-0.0002926`,
`negative_coefficient`다. Power-state audit은 이 row를 outlier로 표시하지 않았으므로,
이 문제는 power cap/temperature outlier보다는 treatment-control 차분 신호가 약하고
nearest-control drift에 민감한 문제로 보는 것이 맞다.

## 기존 L1 결과와 비교

| 실험 | 조건 | valid/total | median | status |
|---|---|---:|---:|---|
| L1 duration-scaling | 10/20/30 s, repeats 5 | 14/15 | 0.156109137015 pJ/bit | accepted_with_caution |
| L1 30초 stability | 30 s, repeats 10 | 9/10 | 0.152768827798 pJ/bit | accepted_with_caution |

두 결과의 중앙값은 거의 같다. 따라서 Global L1 hit path의 대표값은
`0.15 pJ/bit` 수준으로 유지할 수 있다. 다만 음수 row가 완전히 사라지지 않았으므로,
이 값은 `accepted`가 아니라 `accepted_with_caution`으로 보고한다.

## 판단

- NCU hit rate와 traffic 기준으로 Global L1 경로는 잘 분리되었다.
- Power API는 모두 final 후보 조건을 통과했다.
- 그러나 board-level treatment-control 차분 신호는 아직 약하다.
- 따라서 이 결과는 L1 SRAM bitcell의 순수 회로 에너지가 아니라, NCU로 L1 hit path가
  검증된 workload-dependent effective microbenchmark coefficient다.
- RTX 3090 최종 보고서에는 Global L1을 약 `0.15 pJ/bit`로 쓰되,
  `accepted_with_caution`, 1개 음수 row, weak-signal/control drift 가능성을 함께 적는다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_l1_30s_stability_20260708.csv` |
| power API audit | `results/summary/rtx3090_l1_30s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_l1_30s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_l1_30s_stability_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_l1_30s_stability_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_l1_30s_stability_instability_audit_20260708.md` |
