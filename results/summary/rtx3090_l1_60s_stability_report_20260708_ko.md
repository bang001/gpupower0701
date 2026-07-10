# RTX 3090 Global L1 60초 안정성 추가 점검

작성일: 2026-07-08

## 목적

기존 Global L1 결과는 `0.153-0.156 pJ/bit` 범위였지만 30초 stability run에서도
1개 weak-signal negative row가 남았다. 이번 실험은 같은 NCU-accepted L1 hit 좌표를
60초로 늘려, 단순히 duration을 늘리면 차분 신호가 안정화되는지 확인하기 위한
보강 실험이다.

## 실험 조건

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU/profile | RTX 3090 / `rtx3090` | - |
| treatment mode | `global_l1_load_only` | - |
| control mode | `clocked_empty` | - |
| W_SM | 16 | KiB/SM |
| blocks/SM | 16 | blocks/SM |
| active_SM | 82 | SM |
| load_repeat | 4 | repeats/load loop |
| seconds | 60 | s |
| repeats | 8 | rows/mode |
| raw rows | 16 | rows |

Power API 해석은 [docs/platforms/power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)를 따른다. RTX 3090의 `GetPowerUsage` metadata는 `one_sec_average`지만, 이번 계산의 numerator는 `nvml_total_energy + total_energy_mj_delta`이다.

## Power API 및 상태 점검

| gate | 결과 | 해석 |
|---|---:|---|
| Power API audit | 16/16 `final_candidate` | 모두 `nvml_total_energy`와 `total_energy_mj_delta` 사용 |
| `nvml_power_usage_semantics` | `one_sec_average` | RTX 3090 profile과 일치 |
| SMID 검증 | 16/16 true | active SM 배치 이상 없음 |
| Power-state audit | 15/16 `ok`, 1/16 `reject` | treatment row 1개가 평균전력/endpoint/온도 outlier |

Reject row는 `global_l1_load_only`, W=16KiB, B/SM=16, LR=4 조건에서
`avg_power_low_outlier`, `endpoint_power_after_low`, `temperature_outlier`로 잡혔다.
따라서 이 run은 power API는 깨끗하지만, 측정 상태 안정성에는 여전히 문제가 있다.

## NCU 경로 검증

이번 run은 기존 factor-stability NCU sidecar의 동일 좌표
`global_l1_load_only_W16_B16_LR4`를 denominator로 재사용했다.

| metric | 값 | 단위 | 의미 |
|---|---:|---|---|
| L1 hit rate | 99.9982 | % | global load가 거의 L1 hit로 끝남 |
| L1 bytes | 1.07479e12 | bytes | pJ/bit denominator 기준 |
| L2 bytes | 5.92794e8 | bytes | L1 대비 매우 작음 |
| DRAM bytes | 4.52661e8 | bytes | L1 대비 매우 작음 |
| stall long scoreboard | 17.4469 | % | 순수 L1 SRAM energy가 아니라 load path effective coefficient임 |

## Matched-Control 결과

원본 matched-control에서는 8개 treatment row 중 1개가
`negative_coefficient`였다. 이 row는 power-state audit의 reject treatment row와
같으므로, filtered 분석에서는 `--power-state-audit-csv`와
`--exclude-power-state-rejects`를 적용해 pairing 전에 제외했다.

| 항목 | 값 | 단위 |
|---|---:|---|
| filtered detail rows | 7 | rows |
| filtered valid rows | 7 | rows |
| filtered invalid rows | 0 | rows |
| median | 0.119147774400 | pJ/bit |
| min valid | 0.062533593163 | pJ/bit |
| max valid | 0.204819328251 | pJ/bit |
| 95% median CI | 0.108972822709-0.122434009146 | pJ/bit |
| confidence | medium | - |
| reliability verdict | accepted_with_caution | - |

제외된 원본 무효 row는 `delta_E=-1045 J`, `delta_fraction=-0.04708`,
`negative_coefficient`였고 power-state reject row와 같은 treatment outlier로 해석된다.

## 기존 L1 결과와 비교

| 실험 | 조건 | valid/total | median | 단위 | 해석 |
|---|---|---:|---:|---|---|
| L1 duration-scaling primary | 10/20/30 s, repeats 5 | 14/15 | 0.156109137015 | pJ/bit | 현재 primary |
| L1 30초 stability | 30 s, repeats 10 | 9/10 | 0.152768827798 | pJ/bit | primary와 정합 |
| L1 60초 stability | 60 s, repeats 8 | 7/7 filtered | 0.119147774400 | pJ/bit | 더 낮음, 원본 outlier는 power-state reject로 제외 |

60초로 늘렸는데도 원본 row에서는 invalid row가 발생했고, 이를 power-state filter로
제외한 뒤에도 median은 기존 30초 결과보다 낮아졌다. 따라서 L1의 남은 caution은
단순 duration 부족만이 아니라, treatment-control 순서, thermal/power drift,
row-level power-state 변화의 영향을 받는 것으로 판단한다.

## 판단

- NCU hit rate 기준으로 L1 hit path 자체는 잘 분리되어 있다.
- Power API 기준은 final candidate 조건을 모두 통과했다.
- 그러나 power-state reject row와 negative matched-control row가 같은 좌표에서 발생했다.
- filtered matched-control에서는 해당 reject row를 pairing 전에 제외해 negative
  coefficient가 summary에 들어가지 않도록 했다.
- 60초 결과는 L1 primary 값을 대체하지 않는다.
- 현재 보고는 Global L1 primary를 `0.156 pJ/bit`로 유지하되, 60초 auxiliary
  `0.119 pJ/bit`를 control-drift/thermal sensitivity evidence로 추가한다.
- Global L1은 계속 `accepted_with_caution`이며, 순수 L1 SRAM bitcell energy가 아니라
  NCU로 L1 hit path가 검증된 workload-dependent effective microbenchmark coefficient다.

## 다음 개선 방향

| 문제 | 다음 실험/구현 |
|---|---|
| control/treatment drift | control-treatment-control bracketing sequence를 생성하는 paired runner 추가 |
| thermal/power-state outlier | warmup 이후 측정 시작, 온도 안정 구간만 채택 |
| negative row | power-state reject row를 matched-control 입력에서 제외하는 filtered-analysis를 구현했고, 이 보고서에 반영 |
| L1 primary 불확실성 | 30초 primary와 60초 auxiliary를 모두 표시하고 단일 회로 상수 주장 금지 |

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_l1_60s_stability_20260708.csv` |
| matrix CSV | `results/raw/rtx3090_l1_60s_stability_20260708_matrix.csv` |
| power API audit | `results/summary/rtx3090_l1_60s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_l1_60s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_l1_60s_stability_matched_control_report_20260708.md` |
| power-state filtered matched-control report | `results/summary/rtx3090_l1_60s_stability_powerstate_filtered_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_l1_60s_stability_component_reliability_audit_20260708.md` |
| power-state filtered reliability audit | `results/summary/rtx3090_l1_60s_stability_powerstate_filtered_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_l1_60s_stability_instability_audit_20260708.md` |
| power-state filtered instability audit | `results/summary/rtx3090_l1_60s_stability_powerstate_filtered_instability_audit_20260708.md` |
