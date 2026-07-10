# RTX 3090 Global L1 LR8 paired 30초 auxiliary report

대상 결과: 2026-07-08 RTX 3090 Global L1 hit path `load_repeat=8`
control-treatment-control paired 30초 run.

## 목적

기존 Global L1 current primary는 `load_repeat=4` duration-scaling 결과
`0.156 pJ/bit`이고, LR4 control-treatment-control paired auxiliary는
`0.148 pJ/bit`였다. 그러나 broad finalplan에서는 LR8/LR16 조건의 산포가 컸고,
60초 auxiliary는 `0.119 pJ/bit`로 낮아졌다.

따라서 LR8을 같은 paired 구조로 다시 측정해 Global L1 coefficient가 LR4에만
국한된 값인지, 또는 load-repeat/duration에 민감한 effective coefficient인지
확인했다.

이 값은 순수 L1 SRAM bitcell energy가 아니다. `docs/platforms/power_measurement_api_matrix_ko.md`
기준에 따라 RTX 3090 raw row의 최종 energy numerator는 `nvml_total_energy` /
`total_energy_mj_delta`이고, `GetPowerUsage`의 `one_sec_average` 의미는 metadata로만
기록했다. 따라서 결과는 board-level measured energy에서 matched control energy를
뺀 effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 / GA102 |
| treatment mode | `global_l1_load_only` |
| control mode | `clocked_empty` |
| pair 순서 | control - treatment - control |
| `W_SM` | 16 KiB/SM |
| blocks/SM | 16 |
| load repeat | 8 |
| treatment 반복 수 | 6 |
| 각 row 목표 시간 | 30초 |
| 분석 방법 | nearest matched control, power-state reject 제외 |

## Gate 결과

| 검증 항목 | 결과 | 해석 |
|---|---:|---|
| Power API audit | 18/18 `final_candidate` | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 18/18 `ok` | treatment/control clock, power, temperature drift gate 통과 |
| NCU path validation | `accepted` | `global_l1_load_only_W16_B16_LR8`가 L1-hit path로 검증됨 |
| Matched-control detail | 6/6 valid | 모든 treatment row가 양의 충분한 `delta_E` 보유 |
| Reliability audit | `accepted` | current reporting의 auxiliary evidence로 사용 가능 |
| Instability audit | `stable_detail_rows` | 추가 반복 필요 신호 없음 |

## NCU path / denominator 확인

Energy run은 profiler overhead를 피하기 위해 NCU 없이 실행했고, denominator와 path
검증은 같은 조건의 NCU sidecar
`results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`
에서 가져왔다. 이 값은 energy numerator가 아니라 pJ/bit 계산의 denominator와
path sanity를 확인하기 위한 counter다.

| NCU 항목 | 값 | 해석 |
|---|---:|---|
| NCU label | `global_l1_load_only_W16_B16_LR8` | LR8, W_SM=16 KiB, blocks/SM=16 대표 조건 |
| L1 hit rate | 99.9997 % | global load가 사실상 L1 hit로 끝남 |
| L2 hit rate | 27.0991 % | L1-hit path 검증에서 주 denominator가 아님 |
| L1 accesses | 6.71744e10 sectors | L1 request/sector traffic |
| L2 accesses | 1.40358e6 sectors | L1 hit 대비 매우 작음 |
| DRAM accesses | 9.36747e6 sectors | L1 path의 주 traffic이 아님 |
| L1 bytes | 2.14958e12 B | matched-control denominator scale의 근거 |
| L2 bytes | 4.42726e8 B | 보조 counter |
| DRAM bytes | 3.53405e8 B | 보조 counter |
| Long scoreboard stall | 18.5812 % | memory dependency stall이 과도하게 지배적이지 않은지 확인용 |
| Short scoreboard stall | 55.2786 % | instruction dependency/short latency stall metadata |
| Wait stall | 211.504 % | NCU replay 기반 stall breakdown, energy numerator 아님 |
| Not selected stall | 79.9835 % | warp scheduler 선택 지연 metadata |

따라서 이번 LR8 결과의 pJ/bit denominator는 static expected bytes만 쓴 것이 아니라,
NCU에서 LR8 조건의 L1 traffic이 실제로 L1-hit dominated path임을 확인한 뒤 사용했다.
다만 이 NCU run은 대표 sidecar이므로 energy row마다 profiler를 붙인 것은 아니다.

## 결과

| component | median | unit | 95% CI | rows | confidence |
|---|---:|---|---:|---:|---|
| Global L1 hit path LR8 paired 30초 auxiliary | 0.10904234486631326 | pJ/bit | 0.08794267694165234-0.12903365042531625 | 6 | medium |

동일 값을 byte 기준으로 보면 median `0.872338758930506 pJ/byte`다. 모든 detail row는
valid였고, pJ/bit 범위는 `0.08634504726065986-0.13266731425374942`였다.

## 해석

LR8 paired 결과는 LR4 paired combined auxiliary `0.14847568285000448 pJ/bit`보다
낮고, 60초 auxiliary `0.11914777440046519 pJ/bit`와 가깝다. 따라서 Global L1을
하나의 고정된 SRAM 회로 상수처럼 보고하면 안 된다. 현재 RTX 3090 결과에서는
LR4/duration-scaling primary `0.156 pJ/bit`를 대표값으로 유지하되, LR8 paired와
60초 auxiliary를 함께 제시해 Global L1 effective coefficient가 대략
`0.11-0.16 pJ/bit` 범위에서 method-sensitive하다고 보고하는 것이 더 솔직하다.

이번 run은 Power API, power-state, matched-control, reliability gate가 모두
통과했으므로 rejected evidence가 아니다. 다만 primary를 즉시 교체하지 않는 이유는
이 값이 LR8 단일조건 auxiliary이며, 기존 LR4 paired/duration-scaling과 다른
load-repeat 조건에서 측정된 값이기 때문이다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_l1_paired_lr8_30s_stability_20260708.csv` | paired raw measurement |
| `results/raw/rtx3090_l1_paired_lr8_30s_stability_20260708_matrix.csv` | 실행 matrix |
| `results/raw/rtx3090_l1_paired_lr8_30s_stability_20260708_warmup.csv` | warmup raw measurement |
| `results/summary/rtx3090_l1_paired_lr8_30s_stability_power_api_audit_20260708.md` | Power API audit |
| `results/summary/rtx3090_l1_paired_lr8_30s_stability_power_state_audit_20260708.md` | Power-state audit |
| `results/summary/rtx3090_l1_paired_lr8_30s_stability_matched_control_summary_20260708.csv` | matched-control summary |
| `results/summary/rtx3090_l1_paired_lr8_30s_stability_component_reliability_audit_20260708.md` | reliability audit |
| `results/summary/rtx3090_l1_paired_lr8_30s_stability_instability_audit_20260708.md` | instability audit |
