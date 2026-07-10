# RTX 3090 Global L1 Paired 30초 안정성 점검

작성일: 2026-07-08

참고: 이 단일 run 결과는 현재 기준에서
`results/summary/rtx3090_l1_paired_30s_combined_report_20260708_ko.md`의
combined auxiliary로 보강됐다. 현재 보고 표에는 2회 paired run을 결합한
`0.148475682850 pJ/bit`, 12/12 valid, medium-high confidence 값을 사용한다.

## 목적

Global L1 기존 결과는 NCU path는 명확했지만 일부 negative/weak-signal row가 남았다.
60초 auxiliary run은 오히려 power-state reject row를 드러냈다. 이 실험은
`clocked_empty -> global_l1_load_only -> clocked_empty` 순서로 treatment를 control
두 개 사이에 배치해서, control/treatment drift를 줄이면 L1 coefficient가 안정화되는지
확인하기 위한 점검이다.

## 실험 조건

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU/profile | RTX 3090 / `rtx3090` | - |
| sequence | `clocked_empty -> global_l1_load_only -> clocked_empty` | - |
| W_SM | 16 | KiB/SM |
| blocks/SM | 16 | blocks/SM |
| active_SM | 82 | SM |
| load_repeat | 4 | repeats/load loop |
| warmup | 1 paired sequence, 10 s/row | - |
| measurement | 6 paired sequences, 30 s/row | - |
| measurement raw rows | 18 | rows |
| treatment rows | 6 | rows |
| control rows | 12 | rows |

## Power API 및 상태 점검

Power API 해석은 [docs/platforms/power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)를 따른다.

| gate | 결과 | 해석 |
|---|---:|---|
| Power API audit | 18/18 `final_candidate` | 모두 `nvml_total_energy + total_energy_mj_delta` |
| `nvml_power_usage_semantics` | `one_sec_average` | RTX 3090 profile과 일치. final numerator는 total-energy counter |
| Power-state audit | 18/18 `ok` | 평균전력/endpoint/온도 outlier 없음 |
| SMID 검증 | 18/18 true | active SM 배치 이상 없음 |

## NCU 경로 검증

기존 factor-stability NCU sidecar의 동일 좌표 `global_l1_load_only_W16_B16_LR4`를
denominator로 사용했다.

| metric | 값 | 단위 | 의미 |
|---|---:|---|---|
| L1 hit rate | 99.9982 | % | global load가 거의 L1 hit로 끝남 |
| L1 bytes | 1.07479e12 | bytes | pJ/bit denominator 기준 |
| L2 bytes | 5.92794e8 | bytes | L1 대비 매우 작음 |
| DRAM bytes | 4.52661e8 | bytes | L1 대비 매우 작음 |
| stall long scoreboard | 17.4469 | % | 순수 L1 SRAM energy가 아니라 effective load path coefficient |

## Matched-Control 결과

| 항목 | 값 | 단위 |
|---|---:|---|
| detail rows | 6 | rows |
| valid rows | 6 | rows |
| invalid rows | 0 | rows |
| median | 0.147190274870 | pJ/bit |
| min valid | 0.130503371171 | pJ/bit |
| max valid | 0.195876828251 | pJ/bit |
| 95% median CI | 0.135637734180-0.181876721332 | pJ/bit |
| confidence | medium | - |
| reliability verdict | accepted | - |
| instability audit | stable_detail_rows | - |

## 기존 L1 결과와 비교

| 실험 | 조건 | valid/total | median | 단위 | 판단 |
|---|---|---:|---:|---|---|
| L1 duration-scaling primary | 10/20/30 s, repeats 5 | 14/15 | 0.156109137015 | pJ/bit | current primary |
| L1 30초 stability | 30 s, repeats 10 | 9/10 | 0.152768827798 | pJ/bit | primary와 정합, weak-signal 1개 |
| L1 60초 auxiliary | 60 s, repeats 8 | 7/8 | 0.119147774400 | pJ/bit | power-state reject 1개, drift sensitivity |
| L1 paired 30초 auxiliary | C-T-C, 30 s, treatment 6개 | 6/6 | 0.147190274870 | pJ/bit | primary range를 지지, clean run |

## 판단

- L1 path 자체는 NCU로 강하게 확인되어 있다.
- paired control-treatment-control sequence를 쓰면 power-state reject와 negative row가 사라졌다.
- paired median `0.147 pJ/bit`는 기존 duration-scaling `0.156 pJ/bit`, 30초 stability
  `0.153 pJ/bit`와 같은 범위다.
- 따라서 Global L1 current primary는 `0.156 pJ/bit`로 유지하되, paired result를
  clean auxiliary support로 추가한다.
- 60초 auxiliary의 낮은 `0.119 pJ/bit`는 primary 대체값이 아니라 drift sensitivity와
  power-state reject의 경고 증거로 유지한다.
- 결론적으로 Global L1은 여전히 pure L1 SRAM energy가 아니라, NCU로 L1 hit path가
  검증된 workload-dependent effective microbenchmark coefficient다.

## 구현 메모

이번 실험을 위해 [scripts/run_paired_component_stability.py](../../scripts/run_paired_component_stability.py)를 추가했다. 기존 factor sweep runner는 조건 탐색에 적합하지만, drift-sensitive path에는 control/treatment 순서가 느슨하다. paired runner는 각 repeat를 control-treatment-control로 bracket해서 nearest-control pairing의 시간/온도 거리를 줄인다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_l1_paired_30s_stability_20260708.csv` |
| warmup CSV | `results/raw/rtx3090_l1_paired_30s_stability_20260708_warmup.csv` |
| matrix CSV | `results/raw/rtx3090_l1_paired_30s_stability_20260708_matrix.csv` |
| power API audit | `results/summary/rtx3090_l1_paired_30s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_l1_paired_30s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_l1_paired_30s_stability_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_l1_paired_30s_stability_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_l1_paired_30s_stability_instability_audit_20260708.md` |
