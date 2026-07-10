# RTX 3090 Shared LR8 paired 30초 auxiliary report

대상 결과: 2026-07-08 RTX 3090 `shared_scalar_load_only - clocked_empty` control-treatment-control paired 30초 run.

## 목적

Shared scalar path는 current primary가 `0.152395459548 pJ/bit`이지만, paired auxiliary에서 LR4는 `0.236322680068 pJ/bit`, LR16은 `0.053993691505 pJ/bit`로 크게 벌어졌다. 이 실험은 중간 조건인 `load_repeat=8`을 paired 방식으로 측정해, Shared coefficient가 LR에 따라 실제로 변하는지 또는 LR16만 power/state/weak-signal 문제인지 확인하기 위한 보조 실험이다.

이 값은 순수 shared memory SRAM array energy가 아니다. `docs/platforms/power_measurement_api_matrix_ko.md` 기준에 따라 RTX 3090 raw row의 최종 energy numerator는 `nvml_total_energy` / `total_energy_mj_delta`이고, `GetPowerUsage`의 `one_sec_average` 의미는 보조 metadata로만 기록했다. 따라서 결과는 board-level measured energy에서 matched control energy를 뺀 effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 / GA102 |
| treatment mode | `shared_scalar_load_only` |
| control mode | `clocked_empty` |
| pair 순서 | control - treatment - control |
| `W_SM` | 64 KiB/SM |
| blocks/SM | 16 |
| load repeat | 8 |
| treatment 반복 수 | 6 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, NCU actual shared bytes denominator |

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
| Shared scalar path LR8 paired 30초 auxiliary | 0.1620060212072571 | pJ/bit | 0.11382885510708404-0.17847990402587965 | 6 | medium |

byte 기준 median은 `1.2960481696580568 pJ/byte`다. `delta_E` median은 약 `261.212 J`, signal fraction median은 약 `2.71%`로, LR16 paired보다 signal이 안정적이었다.

## LR별 비교

| 조건 | median | unit | rows | reliability | 해석 |
|---|---:|---|---:|---|---|
| LR4 paired 30초 | 0.236 | pJ/bit | 6 | accepted | high-side Shared auxiliary |
| LR8 paired 30초 | 0.162 | pJ/bit | 6 | accepted | mixed primary `0.152 pJ/bit`와 가까운 중간 조건 |
| LR16 paired 30초 | 0.054 | pJ/bit | 5 | accepted_low_stability | lower-side, weak/stability caution |

LR8 paired 결과는 LR4 high-side와 LR16 low-side 사이에 있으며, current mixed primary `0.152 pJ/bit`와 가깝다. 따라서 Shared scalar path는 하나의 순수 회로 상수로 보고하기보다 `load_repeat`, control ordering, fixed overhead에 민감한 effective microbenchmark coefficient로 보고해야 한다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_20260708.csv` | paired raw measurement |
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_20260708_matrix.csv` | 실행 matrix |
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_20260708_warmup.csv` | warmup raw measurement |
| `results/summary/rtx3090_shared_paired_lr8_30s_stability_power_api_audit_20260708.md` | Power API audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_stability_power_state_audit_20260708.md` | Power-state audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_stability_matched_control_summary_20260708.csv` | matched-control summary |
| `results/summary/rtx3090_shared_paired_lr8_30s_stability_component_reliability_audit_20260708.md` | reliability audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_stability_instability_audit_20260708.md` | instability audit |
