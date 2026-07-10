# RTX 3090 L2 LR4 paired 30초 auxiliary report

대상 결과: 2026-07-08 RTX 3090 `l2_cg_load_only - clocked_empty` control-treatment-control paired 30초 run.

## 목적

기존 L2 current primary는 targeted mixed-LR rerun에서 `0.978197461641 pJ/bit`였고 reliability는 accepted였다. 반면 기존 non-paired LR4 30초 auxiliary는 `1.297639212169 pJ/bit`로 더 높았고, L2 row 1개가 power-state reject/negative였다. 이 실험은 같은 LR4 조건을 paired ordering으로 재측정해, LR4 high-side가 실제 조건 의존성인지 control/treatment drift의 영향인지 확인하기 위한 보조 실험이다.

이 값은 순수 L2 SRAM array energy가 아니다. `docs/platforms/power_measurement_api_matrix_ko.md` 기준에 따라 RTX 3090 raw row의 최종 energy numerator는 `nvml_total_energy` / `total_energy_mj_delta`이고, `GetPowerUsage`의 `one_sec_average` 의미는 보조 metadata로만 기록했다. 따라서 결과는 board-level measured energy에서 matched control energy를 뺀 effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 / GA102 |
| treatment mode | `l2_cg_load_only` |
| control mode | `clocked_empty` |
| pair 순서 | control - treatment - control |
| `W_SM` | 64 KiB/SM |
| blocks/SM | 16 |
| load repeat | 4 |
| treatment 반복 수 | 6 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, NCU actual L2 bytes denominator |

## Gate 결과

| 검증 항목 | 결과 | 해석 |
|---|---:|---|
| Power API audit | 18/18 `final_candidate` | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 18/18 `ok` | treatment/control clock, power, temperature drift gate 통과 |
| Matched-control detail | 6/6 valid | 모든 treatment row가 양의 충분한 `delta_E` 보유 |
| Reliability audit | `accepted` | current reporting의 auxiliary evidence로 사용 가능 |
| Instability audit | `stable_detail_rows` | 추가 반복 필요 신호 없음 |

## 결과

| component | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| L2 CG hit path LR4 paired 30초 auxiliary | 1.0272539734213253 | pJ/bit | 0.9835597417446175-1.129187704812146 | 6 | medium |

byte 기준 median은 `8.218031787370602 pJ/byte`다. `delta_E` median은 약 `619.628 J`, signal fraction median은 약 `6.38%`로 weak-signal 문제는 없었다.

## 해석

이 paired 결과는 기존 targeted L2 primary `0.978197461641 pJ/bit`와 같은 범위에 있다. 반대로 기존 non-paired LR4 30초 auxiliary `1.297639212169 pJ/bit`보다는 낮다. 따라서 현재 판단은 다음과 같다.

| 항목 | 판단 |
|---|---|
| L2 primary | targeted mixed-LR `0.978 pJ/bit`를 유지 |
| L2 LR4 paired auxiliary | `1.027 pJ/bit`를 clean support로 추가 |
| 기존 non-paired LR4 auxiliary | drift/order-sensitive high-side evidence로 낮춰 해석 |

L2는 여전히 physical L2 SRAM bitcell energy가 아니라 `l2_cg_load_only` microbenchmark의 board-level effective coefficient다. 다만 이번 paired run은 Power API, power-state, matched-control, reliability gate를 모두 통과했기 때문에 L2 current primary가 `~1.0 pJ/bit` 근처라는 해석을 강화한다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708.csv` | paired raw measurement |
| `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708_matrix.csv` | 실행 matrix |
| `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708_warmup.csv` | warmup raw measurement |
| `results/summary/rtx3090_l2_paired_lr4_30s_stability_power_api_audit_20260708.md` | Power API audit |
| `results/summary/rtx3090_l2_paired_lr4_30s_stability_power_state_audit_20260708.md` | Power-state audit |
| `results/summary/rtx3090_l2_paired_lr4_30s_stability_matched_control_summary_20260708.csv` | matched-control summary |
| `results/summary/rtx3090_l2_paired_lr4_30s_stability_component_reliability_audit_20260708.md` | reliability audit |
| `results/summary/rtx3090_l2_paired_lr4_30s_stability_instability_audit_20260708.md` | instability audit |
