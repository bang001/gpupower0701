# RTX 3090 Shared/L1 Targeted Stability Rerun

작성일: 2026-07-08

## 목적

기존 factor exact-NCU 결과에서 Shared scalar와 Global L1 path는 NCU path 자체는
accepted였지만 matched-control detail row 일부가 negative 또는 weak-signal로
제외되었다. 이번 rerun은 전체 sweep을 다시 수행한 것이 아니라, 문제가 남아 있던
Shared/L1 조건만 길게 반복 측정하여 board-level energy 차분 안정성이 개선되는지
확인한 targeted stability check다.

## 측정 조건

| component | treatment mode | control mode | W_SM (KiB) | blocks/SM | active_SM | sweep parameter | sweep values | seconds | repeats |
|---|---|---|---:|---:|---:|---|---|---:|---:|
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | 64 | 16 | 82 | `load_repeat` | 4, 8, 16 | 20 | 10 |
| Global L1 hit path | `global_l1_load_only` | `clocked_empty` | 16 | 16 | 82 | `load_repeat` | 4, 8, 16 | 20 | 10 |

NCU denominator는 새로 측정하지 않고, 기존 factor exact-NCU accepted sidecar의
`ncu_actual_exact` 값을 사용했다. 따라서 이번 rerun은 path 검증 재실험이 아니라
energy numerator 안정성 재확인이다.

## Power API gate

| 항목 | 결과 |
|---|---:|
| raw energy rows | 120 |
| `final_candidate` | 120 |
| `provisional` | 0 |
| `reject` | 0 |

이번 결과는 `energy_source=nvml_total_energy`,
`energy_integration_method=total_energy_mj_delta`,
`nvml_total_energy_supported=true` 조건을 통과했다. RTX 3090의
`GetPowerUsage` fallback 의미는 `one_sec_average`이지만, 이번 coefficient 분자는
endpoint power fallback이 아니라 NVML total energy counter 차분이다.

## 결과 비교

| component | 이전 median | 이전 valid/total | targeted median | targeted valid/total | 판정 |
|---|---:|---:|---:|---:|---|
| Shared scalar path | 0.151 pJ/bit | 6/9 | 0.152 pJ/bit | 29/30 | 값은 정합, 안정성 개선. 단 1개 negative row가 있어 caution 유지 |
| Global L1 hit path | 0.150 pJ/bit | 7/9 | 0.105 pJ/bit | 26/28 filtered | 표본은 증가했지만 LR=16에서 weak/negative row 2개가 남음. 대표값 교체 보류 |

상세 결과:

| component | median | unit | min | max | bootstrap median CI | confidence | reliability |
|---|---:|---|---:|---:|---:|---|---|
| Shared scalar path | 0.152 | pJ/bit | 0.0356 | 0.263 | 0.114-0.204 | medium | `accepted_with_caution` |
| Global L1 hit path | 0.105 | pJ/bit | 0.0284 | 0.219 | 0.0762-0.129 | medium | `accepted_with_caution` |

## Invalid row 원인

| component | invalid/total | 주요 원인 | 집중 조건 |
|---|---:|---|---|
| Shared scalar path | 1/30 | `negative_coefficient`, `delta_fraction<0.005` | `load_repeat=16` |
| Global L1 hit path | 2/28 filtered | `negative_coefficient`, weak signal | `load_repeat=16` |

Power-state audit을 추가로 수행한 결과, 원본 Global L1 invalid row 4개 중 2개는
명확한 row-level power-state outlier였다. filtered matched-control 분석에서는 이 두
row를 pairing 전에 제외했다. 나머지 작은 음수 row 2개와 Shared의 음수 row 1개는
power-state outlier가 아니라 weak treatment-control signal로 보는 것이 맞다.

따라서 L1의 NCU path는 accepted로 볼 수 있지만, board-level energy coefficient는
여전히 `accepted_with_caution`으로 보고해야 한다. 이 경우 gate를 낮추지 말고,
power-state outlier가 없는 조건에서 duration 또는 denominator sweep을 다시 설계한다.

Shared의 남은 LR=16 weak row를 확인하기 위해 별도 control-treatment-control paired
30초 auxiliary도 수행했다. 같은 paired protocol에서 LR4는 6/6 valid,
`0.236 pJ/bit`, reliability `accepted`였고, LR16은 5/6 valid,
`0.054 pJ/bit`, confidence low였다. 따라서 paired sequence 자체가 값을 낮춘 것은
아니며, Shared coefficient가 LR/control 정책에 민감하다는 high/low evidence로
사용한다.

## 결론

- Shared scalar path는 기존 0.151 pJ/bit와 targeted 0.152 pJ/bit가 거의 같고,
  valid row가 6/9에서 29/30으로 증가했다. 현재로서는 Shared scalar path의 대표값을
  `0.15 pJ/bit` 수준의 effective coefficient로 보는 것이 합리적이다.
- Shared LR4 paired 30초 auxiliary는 `0.236 pJ/bit`로 clean high-side evidence이고,
  LR16 paired 30초 auxiliary는 `0.054 pJ/bit`로 lower-side evidence다. 둘 다
  primary replacement가 아니라 method sensitivity evidence다.
- Global L1 hit path는 targeted median이 0.105 pJ/bit로 낮아졌고 LR=16 negative row가
  반복적으로 발생했다. 기존 0.150 pJ/bit와 targeted 0.105 pJ/bit 중 하나를
  단정적으로 final로 교체하지 말고, 범위와 caution을 함께 보고해야 한다.
- 이 값들은 순수 L1/shared SRAM bitcell energy가 아니다. NVML board-level energy,
  treatment-control 차분, NCU denominator 검증을 결합한 workload-dependent effective
  microbenchmark coefficient다.

## 관련 산출물

| artifact | path |
|---|---|
| power API audit | `results/summary/rtx3090_targeted_shared_l1_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_targeted_shared_l1_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_targeted_shared_l1_matched_control_report_20260708.md` |
| power-state filtered matched-control report | `results/summary/rtx3090_targeted_shared_l1_powerstate_filtered_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_targeted_shared_l1_component_reliability_audit_20260708.md` |
| power-state filtered reliability audit | `results/summary/rtx3090_targeted_shared_l1_powerstate_filtered_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_targeted_shared_l1_instability_audit_20260708.md` |
| power-state filtered instability audit | `results/summary/rtx3090_targeted_shared_l1_powerstate_filtered_instability_audit_20260708.md` |
| Shared LR4 paired report | `results/summary/rtx3090_shared_paired_lr4_30s_stability_report_20260708_ko.md` |
| Shared LR16 paired report | `results/summary/rtx3090_shared_paired_lr16_30s_stability_report_20260708_ko.md` |
| Shared raw CSV | `results/raw/rtx3090_targeted_shared_stability_20260708.csv` |
| L1 raw CSV | `results/raw/rtx3090_targeted_l1_stability_20260708.csv` |
