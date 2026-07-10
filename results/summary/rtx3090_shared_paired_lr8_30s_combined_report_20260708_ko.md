# RTX 3090 Shared LR8 paired 30초 combined auxiliary report

대상 결과: 2026-07-08 RTX 3090 `shared_scalar_load_only - clocked_empty` control-treatment-control paired 30초 run 2회 결합 분석.

## 목적

Shared scalar path의 current primary는 targeted mixed-LR rerun에서 `0.152395459548 pJ/bit`였지만, LR4/LR8/LR16 조건에 따라 보조 결과가 크게 갈라졌다. 특히 기존 LR8 paired 30초 auxiliary는 `0.162006021207 pJ/bit`로 primary에 가까웠지만 6개 treatment row뿐이었다. 이 실험은 같은 LR8 조건을 한 번 더 실행해, LR8 중간값이 재현되는지 확인하고 Shared 축의 신뢰도를 보강하기 위한 것이다.

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
| treatment 반복 수 | original 6 + rerun2 6 = 12 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, NCU actual shared bytes denominator |

## Gate 결과

| 검증 항목 | original | rerun2 | combined | 해석 |
|---|---:|---:|---:|---|
| Power API audit | 18/18 final | 18/18 final | 36/36 final | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 18/18 ok | 18/18 ok | 36/36 ok | clock, power, temperature drift gate 통과 |
| Matched-control detail | 6/6 valid | 6/6 valid | 12/12 valid | negative/weak-signal row 없음 |
| Reliability audit | accepted | accepted | accepted | current reporting의 auxiliary evidence로 사용 가능 |
| Instability audit | stable | stable | stable | 추가 반복 필요 신호 없음 |

## NCU path validation

NCU denominator는 `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`의 `shared_scalar_load_only_W64_B16_LR8` row를 사용했다.

| 항목 | 값 | 해석 |
|---|---:|---|
| Shared accesses | 8.39684e9 | shared scalar instruction path가 충분히 발생 |
| Shared bytes | 1.0748e12 B | pJ/bit denominator |
| Shared bank conflicts | 0 | bank conflict 오염 없음 |
| L1 accesses | 0 sectors | Global L1 hit path가 아니라 shared path |
| L1 bytes | 0 B | L1 cache traffic denominator가 아님 |
| L2 bytes | 3.73815e8 B | shared bytes 대비 약 0.035% |
| DRAM bytes | 2.73733e8 B | shared bytes 대비 약 0.025% |
| Short scoreboard | 96.1431% | shared scalar instruction dependency/issue overhead가 섞임 |
| Wait | 310.274% | pure array energy로 해석하면 안 되는 이유 |

## 결과

| run | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| original LR8 paired 30초 | 0.1620060212072571 | pJ/bit | 0.11382885510708404-0.17847990402587965 | 6 | medium |
| rerun2 LR8 paired 30초 | 0.18063270571580864 | pJ/bit | 0.15660769184185241-0.1904498237567046 | 6 | medium |
| combined LR8 paired 30초 | 0.17683780985788863 | pJ/bit | 0.1499503129616267-0.18115958218032208 | 12 | medium-high |

combined byte 기준 median은 `1.414702478863109 pJ/byte`다. `delta_E` median은 약 `284.356 J`, signal fraction median은 약 `2.96%`로 weak-signal gate를 통과했다.

## 해석

LR8 paired 결과는 원본과 rerun2가 같은 범위에서 재현되었고, combined 분석은 12/12 valid로 medium-high confidence까지 올라갔다. 따라서 Shared LR8은 current primary `0.152 pJ/bit` 근처의 중간 조건 evidence로 볼 수 있다.

다만 Shared 전체를 단일 상수로 줄이면 안 된다. LR4 paired는 `0.236 pJ/bit`, LR8 combined는 `0.177 pJ/bit`, LR16 combined는 `0.064 pJ/bit`로 갈라진다. 이는 shared scalar path coefficient가 load_repeat/control 정책과 instruction scheduling에 민감한 effective coefficient라는 뜻이다.

| 항목 | 판단 |
|---|---|
| Shared primary | targeted mixed-LR `0.152 pJ/bit`를 유지 |
| Shared LR8 paired auxiliary | combined `0.177 pJ/bit`로 갱신 |
| Shared LR4 paired auxiliary | high-side `0.236 pJ/bit` |
| Shared LR16 paired combined auxiliary | low-side `0.064 pJ/bit` |
| 보고 방식 | `0.15-0.24 pJ/bit` 범위와 LR16 low-side caution을 함께 제시 |

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_20260708.csv` | original paired raw measurement |
| `results/raw/rtx3090_shared_paired_lr8_30s_stability_rerun2_20260708.csv` | rerun2 paired raw measurement |
| `results/raw/rtx3090_shared_paired_lr8_30s_combined_20260708.csv` | original + rerun2 combined measurement |
| `results/summary/rtx3090_shared_paired_lr8_30s_combined_power_api_audit_20260708.md` | combined Power API audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_combined_power_state_audit_20260708.md` | combined power-state audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_combined_matched_control_summary_20260708.csv` | combined matched-control summary |
| `results/summary/rtx3090_shared_paired_lr8_30s_combined_component_reliability_audit_20260708.md` | combined reliability audit |
| `results/summary/rtx3090_shared_paired_lr8_30s_combined_instability_audit_20260708.md` | combined instability audit |
