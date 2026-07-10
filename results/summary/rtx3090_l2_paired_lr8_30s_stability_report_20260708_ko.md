# RTX 3090 L2 LR8 paired 30초 auxiliary report

대상 결과: 2026-07-08 RTX 3090 `l2_cg_load_only - clocked_empty` control-treatment-control paired 30초 run.

## 목적

기존 L2 current primary는 targeted mixed-LR rerun에서 `0.978197461641 pJ/bit`였고, LR4 paired auxiliary는 `1.027253973421 pJ/bit`였다. 이 실험은 같은 `W_SM=64 KiB`, `blocks/SM=16` 조건에서 `load_repeat=8`을 따로 실행해 L2 coefficient가 LR4에만 맞춰진 우연한 값인지, paired ordering에서 반복 가능한 값인지 확인하기 위한 보조 실험이다.

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
| load repeat | 8 |
| treatment 반복 수 | 6 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, NCU actual L2 bytes denominator |

## Gate 결과

| 검증 항목 | 결과 | 해석 |
|---|---:|---|
| raw row 구조 | 18 measurement rows, 12 control + 6 treatment | paired run 구조가 의도대로 생성됨 |
| Power API audit | 18/18 `final_candidate` | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 18/18 `ok` | treatment/control clock, power, temperature drift gate 통과 |
| Matched-control detail | 6/6 valid | 모든 treatment row가 양의 충분한 `delta_E` 보유 |
| Reliability audit | `accepted` | current reporting의 auxiliary evidence로 사용 가능 |
| Instability audit | `stable_detail_rows` | 추가 반복 필요 신호 없음 |

## NCU path validation

NCU denominator는 `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`의 `l2_cg_load_only_W64_B16_LR8` row를 사용했다.

| 항목 | 값 | 해석 |
|---|---:|---|
| L1 hit rate | 0.000003% | global load가 L1에서 끝나지 않도록 `cg` path가 형성됨 |
| L2 hit rate | 99.9368% | 대부분의 요청이 L2 hit로 처리됨 |
| L1 access | 3.35872e10 sectors | L1 hit path가 아니라 L2 요청으로 전달되는 트래픽 |
| L2 access | 3.35976e10 sectors | denominator로 쓰는 핵심 L2 traffic |
| DRAM access | 2.42346e7 sectors | L2 traffic 대비 매우 작아 streaming DRAM path가 아님 |
| L1 bytes | 1.07479e12 B | L1 byte counter는 요청 경로 metadata로 기록 |
| L2 bytes | 1.07618e12 B | pJ/bit denominator |
| DRAM bytes | 1.26191e9 B | L2 bytes 대비 약 0.12% 수준 |
| Long scoreboard | 945.037% | L2 hit path라도 stall-heavy microbenchmark임을 의미 |
| Short scoreboard | 55.4243% | dependency/issue overhead가 일부 섞임 |
| Wait | 306.457% | pure SRAM-array energy로 해석하면 안 되는 이유 |

## 결과

| component | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| L2 CG hit path LR8 paired 30초 auxiliary | 0.9596403819965263 | pJ/bit | 0.8979156650194069-1.0999309840237017 | 6 | medium |

byte 기준 median은 `7.677123055972211 pJ/byte`다. `delta_E` median은 약 `571.075 J`, signal fraction median은 약 `5.96%`로 weak-signal 문제는 없었다.

## 해석

LR8 paired 결과는 기존 targeted L2 primary `0.978197461641 pJ/bit`와 거의 같은 범위에 있고, LR4 paired auxiliary `1.027253973421 pJ/bit`와도 CI가 겹친다. 반대로 기존 non-paired LR4 30초 auxiliary `1.297639212169 pJ/bit`보다는 낮다. 따라서 현재 판단은 다음과 같다.

| 항목 | 판단 |
|---|---|
| L2 primary | targeted mixed-LR `0.978 pJ/bit`를 유지 |
| L2 LR4 paired auxiliary | `1.027 pJ/bit` clean support |
| L2 LR8 paired auxiliary | `0.960 pJ/bit` clean support |
| 기존 non-paired LR4 auxiliary | drift/order-sensitive high-side evidence로 낮춰 해석 |

이 결과는 L2가 RTX 3090 현재 실험에서 가장 일관적인 memory component 축이라는 해석을 강화한다. 단, 여전히 `l2_cg_load_only` microbenchmark의 board-level effective coefficient이며, L2 SRAM array 단독 energy나 다른 workload의 보편 상수로 쓰면 안 된다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_l2_paired_lr8_30s_stability_20260708.csv` | paired raw measurement |
| `results/raw/rtx3090_l2_paired_lr8_30s_stability_20260708_matrix.csv` | 실행 matrix |
| `results/raw/rtx3090_l2_paired_lr8_30s_stability_20260708_warmup.csv` | warmup raw measurement |
| `results/summary/rtx3090_l2_paired_lr8_30s_stability_power_api_audit_20260708.md` | Power API audit |
| `results/summary/rtx3090_l2_paired_lr8_30s_stability_power_state_audit_20260708.md` | Power-state audit |
| `results/summary/rtx3090_l2_paired_lr8_30s_stability_matched_control_summary_20260708.csv` | matched-control summary |
| `results/summary/rtx3090_l2_paired_lr8_30s_stability_component_reliability_audit_20260708.md` | reliability audit |
| `results/summary/rtx3090_l2_paired_lr8_30s_stability_instability_audit_20260708.md` | instability audit |
