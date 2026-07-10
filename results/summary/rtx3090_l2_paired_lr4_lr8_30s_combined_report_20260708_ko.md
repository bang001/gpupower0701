# RTX 3090 L2 LR4/LR8 paired 30초 combined primary report

대상 결과: 2026-07-08 RTX 3090 `l2_cg_load_only - clocked_empty` control-treatment-control paired 30초 LR4/LR8 결합 분석.

## 목적

기존 L2 current primary는 targeted mixed-LR rerun의 `0.978197461641 pJ/bit`였고, reliability는 accepted였다. 다만 해당 artifact의 power-state audit에는 coefficient-invalid는 아니지만 control temperature caution 1개가 metadata로 남아 있었다. 반면 L2 LR4 paired 30초와 LR8 paired 30초 run은 각각 6/6 valid, power-state 18/18 ok였다.

이 분석은 두 clean paired run을 결합해, power-state caution 없이 current L2 primary로 쓸 수 있는지 확인하기 위한 것이다.

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
| load repeat | 4, 8 |
| treatment 반복 수 | LR4 6 + LR8 6 = 12 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, NCU actual L2 bytes denominator |

## Gate 결과

| 검증 항목 | LR4 paired | LR8 paired | combined | 해석 |
|---|---:|---:|---:|---|
| Power API audit | 18/18 final | 18/18 final | 36/36 final | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 18/18 ok | 18/18 ok | 36/36 ok | clock, power, temperature drift gate 통과 |
| Matched-control detail | 6/6 valid | 6/6 valid | 12/12 valid | negative/weak-signal row 없음 |
| Reliability audit | accepted | accepted | accepted | current reporting primary로 사용 가능 |
| Instability audit | stable | stable | stable | 추가 반복 필요 신호 없음 |

## NCU path validation

NCU denominator는 `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`의 `l2_cg_load_only_W64_B16_LR4`와 `l2_cg_load_only_W64_B16_LR8` row를 사용했다.

| NCU label | L1 hit rate | L2 hit rate | L1 bytes | L2 bytes | DRAM bytes | 해석 |
|---|---:|---:|---:|---:|---:|---|
| `l2_cg_load_only_W64_B16_LR4` | 0.000006% | 99.8978% | 5.37395e11 B | 5.37997e11 B | 5.40672e8 B | L1 bypass + L2 hit dominated |
| `l2_cg_load_only_W64_B16_LR8` | 0.000003% | 99.9368% | 1.07479e12 B | 1.07618e12 B | 1.26191e9 B | L1 bypass + L2 hit dominated |

두 NCU row 모두 L1 hit rate가 사실상 0이고 L2 hit rate가 약 99.9%다. DRAM bytes는 L2 bytes 대비 약 0.1% 수준이므로 DRAM streaming path가 아니라 L2-hit path로 해석한다. 다만 long scoreboard stall이 크기 때문에 pure L2 SRAM array energy로 해석하지 않는다.

## 결과

| run | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| L2 LR4 paired 30초 | 1.0272539734213253 | pJ/bit | 0.9835597417446175-1.129187704812146 | 6 | medium |
| L2 LR8 paired 30초 | 0.9596403819965263 | pJ/bit | 0.8979156650194069-1.0999309840237017 | 6 | medium |
| L2 LR4/LR8 paired 30초 combined | 1.016556433726509 | pJ/bit | 0.9473333505165014-1.0711219304762705 | 12 | medium-high |

combined byte 기준 median은 `8.132451469812072 pJ/byte`다. `delta_E` median은 약 `612.906 J`, signal fraction median은 약 `6.35%`로 weak-signal 문제는 없었다.

## 해석

paired LR4/LR8 combined 결과는 기존 targeted mixed-LR primary `0.978197461641 pJ/bit`와 같은 범위다. 또한 기존 non-paired LR4 auxiliary `1.297639212169 pJ/bit`보다 낮아, control ordering과 drift가 L2 high-side 값을 키웠다는 기존 판단을 지지한다.

| 항목 | 판단 |
|---|---|
| L2 current primary | paired LR4/LR8 combined `1.017 pJ/bit`로 승격 |
| Targeted mixed-LR | `0.978 pJ/bit` auxiliary support로 유지 |
| LR4 paired | `1.027 pJ/bit` clean support |
| LR8 paired | `0.960 pJ/bit` clean support |
| LR4 non-paired | `1.298 pJ/bit` drift/order-sensitive high-side evidence |

따라서 L2는 현재 RTX 3090 memory components 중 가장 안정적으로 분리된 축에 가깝다. 그래도 이 값은 L2 SRAM array 단독 에너지가 아니라, L1 bypass와 L2 hit가 NCU로 확인된 `l2_cg_load_only` board-level effective microbenchmark coefficient다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_l2_paired_lr4_30s_stability_20260708.csv` | LR4 paired raw measurement |
| `results/raw/rtx3090_l2_paired_lr8_30s_stability_20260708.csv` | LR8 paired raw measurement |
| `results/raw/rtx3090_l2_paired_lr4_lr8_30s_combined_20260708.csv` | LR4 + LR8 combined measurement |
| `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_power_api_audit_20260708.md` | combined Power API audit |
| `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_power_state_audit_20260708.md` | combined power-state audit |
| `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_matched_control_summary_20260708.csv` | combined matched-control summary |
| `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_component_reliability_audit_20260708.md` | combined reliability audit |
| `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_instability_audit_20260708.md` | combined instability audit |
