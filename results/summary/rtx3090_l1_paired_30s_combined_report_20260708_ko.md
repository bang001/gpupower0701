# RTX 3090 Global L1 paired 30초 combined auxiliary report

대상 결과: 2026-07-08 RTX 3090 Global L1 hit path control-treatment-control paired 30초 run 2회 결합.

## 목적

Global L1 hit path의 `0.15 pJ/bit` 근처 계수가 control drift나 실행 순서에 의해 우연히 나온 값인지 점검하기 위해 paired 설계를 반복했다. 이 보고서는 기존 6개 treatment row와 추가 6개 treatment row를 합쳐, L1 auxiliary evidence의 표본 수와 power-state 검증 강도를 높인 결과다.

이 값은 순수 SRAM bitcell energy가 아니다. `docs/platforms/power_measurement_api_matrix_ko.md` 기준에 따라 RTX 3090 raw row의 최종 energy numerator는 `nvml_total_energy` / `total_energy_mj_delta`이고, `GetPowerUsage`의 `one_sec_average` 의미는 보조 metadata로만 기록했다. 따라서 결과는 board-level measured energy에서 matched control energy를 뺀 effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 / GA102 |
| treatment mode | `global_l1_load_only` |
| control mode | `clocked_empty` |
| pair 순서 | control - treatment - control |
| `W_SM` | 16 KiB/SM |
| blocks/SM | 16 |
| load repeat | 4 |
| treatment 반복 수 | 12 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, power-state reject 제외 |

## Gate 결과

| 검증 항목 | 결과 | 해석 |
|---|---:|---|
| Power API audit | 36/36 `final_candidate` | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 36/36 `ok` | treatment/control clock, power, temperature drift gate 통과 |
| Matched-control detail | 12/12 valid | 모든 treatment row가 양의 충분한 `delta_E` 보유 |
| Reliability audit | `accepted` | current reporting의 auxiliary evidence로 사용 가능 |
| Instability audit | `stable_detail_rows` | 추가 반복 필요 신호 없음 |

## 결과

| component | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| Global L1 hit path paired 30초 auxiliary | 0.14847568285000448 | pJ/bit | 0.1429444591506696-0.17016063207757137 | 12 | medium-high |

동일 값을 byte 기준으로 보면 median `1.1878054628000358 pJ/byte`다. 이 값은 duration-scaling primary `0.1561091370146893 pJ/bit`와 같은 범위에 있으며, Global L1 primary를 `0.15 pJ/bit` 근처 effective coefficient로 보고하는 판단을 강화한다.

## 해석

이 combined result는 기존 paired 6-row auxiliary `0.14719027487031412 pJ/bit`와 사실상 같은 중심값을 유지하면서 표본 수를 12개로 늘렸다. Power API gate와 power-state gate가 모두 통과했기 때문에, 이번 L1 auxiliary는 현재 RTX 3090 결과 중 비교적 신뢰도가 높은 보조 증거다.

다만 이 결과도 `global_l1_load_only - clocked_empty`라는 특정 microbenchmark 차분값이다. 즉 CUDA global load가 L1 hit로 종료되는 경로의 board-level incremental cost를 나타내며, L1 SRAM array 자체의 물리 회로 에너지나 transistor-level 에너지를 직접 측정한 것은 아니다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_l1_paired_30s_stability_20260708.csv` | 기존 paired raw run |
| `results/raw/rtx3090_l1_paired_30s_stability_rerun2_20260708.csv` | 추가 paired raw rerun |
| `results/summary/rtx3090_l1_paired_30s_combined_power_api_audit_20260708.md` | 결합 raw row power API audit |
| `results/summary/rtx3090_l1_paired_30s_combined_power_state_audit_20260708.md` | 결합 raw row power-state audit |
| `results/summary/rtx3090_l1_paired_30s_combined_matched_control_summary_20260708.csv` | 결합 matched-control summary |
| `results/summary/rtx3090_l1_paired_30s_combined_component_reliability_audit_20260708.md` | 결합 reliability audit |
| `results/summary/rtx3090_l1_paired_30s_combined_instability_audit_20260708.md` | 결합 instability audit |
