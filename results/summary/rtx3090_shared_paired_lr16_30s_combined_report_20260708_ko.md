# RTX 3090 Shared LR16 paired 30초 combined auxiliary report

대상 결과: 2026-07-08 RTX 3090 Shared scalar path `load_repeat=16`
control-treatment-control paired 30초 run 2회 결합.

## 목적

기존 Shared LR16 paired run은 median `0.053993691505177854 pJ/bit`였지만
5/6 valid, confidence low였다. Shared LR4 paired `0.236 pJ/bit`, LR8 paired
`0.162 pJ/bit`와 비교하면 하단 evidence로 중요하지만, 표본 수와 산포 때문에
그 자체를 안정적인 lower-bound로 쓰기 어려웠다.

그래서 같은 조건을 한 번 더 실행해 LR16 low-side가 재현되는지 확인하고, 기존 run과
결합해 confidence를 개선했다.

이 값은 순수 shared-memory SRAM bitcell energy가 아니다. `docs/platforms/power_measurement_api_matrix_ko.md`
기준에 따라 RTX 3090 raw row의 최종 energy numerator는 `nvml_total_energy` /
`total_energy_mj_delta`이고, `GetPowerUsage`의 `one_sec_average` 의미는 metadata로만
기록했다. 따라서 결과는 board-level measured energy에서 matched control energy를
뺀 effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 / GA102 |
| treatment mode | `shared_scalar_load_only` |
| control mode | `clocked_empty` |
| pair 순서 | control - treatment - control |
| `W_SM` | 64 KiB/SM |
| blocks/SM | 16 |
| load repeat | 16 |
| 각 row 목표 시간 | 30초 |
| original treatment 반복 수 | 6 |
| rerun2 treatment 반복 수 | 6 |
| combined treatment 반복 수 | 12 |
| 분석 방법 | nearest matched control, power-state reject 제외 |

## Gate 결과

| 검증 항목 | original | rerun2 | combined | 해석 |
|---|---:|---:|---:|---|
| Power API audit | 18/18 final | 18/18 final | 36/36 final | 모든 raw row가 `nvml_total_energy` delta 기반 |
| Power-state audit | 17/18 ok, 1 reject | 18/18 ok | 35/36 ok, 1 reject | combined 분석은 reject row를 pairing 전 제외 |
| Matched-control detail | 5/6 valid | 6/6 valid | 11/12 valid | rerun2에서 low-side가 재현됨 |
| Reliability audit | `accepted_low_stability` | `accepted` | `accepted_with_caution` | combined는 confidence medium이나 산포가 큼 |
| Instability audit | low stability | stable_detail_rows | needs_stability_followup | 값은 양수지만 분포 폭이 넓음 |

## NCU path / denominator 확인

Energy run은 NCU 없이 실행했고, denominator와 path 검증은 같은 조건의 NCU sidecar
`results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`
에서 가져왔다. 이 값은 energy numerator가 아니라 pJ/bit 계산의 denominator와
path sanity를 확인하기 위한 counter다.

| NCU 항목 | 값 | 해석 |
|---|---:|---|
| NCU label | `shared_scalar_load_only_W64_B16_LR16` | LR16, W_SM=64 KiB, blocks/SM=16 대표 조건 |
| Shared accesses | 1.67936e10 | shared scalar load path traffic |
| Shared bytes | 2.14959e12 B | matched-control denominator scale의 근거 |
| Shared bank conflicts | 0 | bank conflict가 coefficient를 지배하지 않음 |
| Shared inst | 1.67936e10 | shared load instruction traffic |
| L1 bytes | 0 B | global L1-hit path와 분리된 shared scalar path |
| L2 bytes | 1.09455e9 B | 보조 traffic |
| DRAM bytes | 7.91497e8 B | 보조 traffic |
| Long scoreboard stall | 0.000693 % | long memory dependency stall은 거의 없음 |
| Short scoreboard stall | 98.8766 % | short latency dependency가 큰 shared scalar kernel 특성 |
| Wait stall | 312.017 % | NCU replay 기반 stall metadata, energy numerator 아님 |
| Not selected stall | 48.654 % | warp scheduler 선택 지연 metadata |

따라서 이번 LR16 결과의 pJ/bit denominator는 static expected bytes만 쓴 것이 아니라,
NCU에서 LR16 조건의 shared scalar traffic이 실제로 shared path로 발생했음을 확인한
뒤 사용했다. 다만 NCU run은 대표 sidecar이므로 energy row마다 profiler를 붙인 것은
아니다.

## 결과

| view | median | unit | 95% CI | rows | confidence | reliability |
|---|---:|---|---:|---:|---|---|
| original LR16 paired | 0.053993691505177854 | pJ/bit | 0.03285049759413827-0.10405951151729738 | 5 | low | accepted_low_stability |
| rerun2 LR16 paired | 0.08644545436495304 | pJ/bit | 0.04941808514443968-0.13250720072109626 | 6 | medium | accepted |
| combined LR16 paired | 0.06354557112089149 | pJ/bit | 0.04571628485881329-0.10405951151729738 | 11 | medium | accepted_with_caution |

동일 값을 byte 기준으로 보면 combined median은 `0.5083645689671319 pJ/byte`다.
combined pJ/bit 범위는 `0.03285049759413827-0.13778655439487988`로 넓다.

## 해석

rerun2는 original보다 약간 높지만 여전히 LR4/LR8보다 낮다. combined median도
`0.0635 pJ/bit`로 Shared LR4 paired `0.236 pJ/bit`, Shared LR8 paired
`0.162 pJ/bit`, targeted mixed primary `0.152 pJ/bit`보다 확실히 낮다.

따라서 Shared LR16 low-side는 재현된 것으로 본다. 그러나 combined instability audit이
`needs_stability_followup`이고 reliability가 `accepted_with_caution`이므로, 이 값을
Shared의 primary로 쓰면 안 된다. Shared scalar path는 LR/fixed overhead/control policy에
민감한 effective coefficient이며, 보고서는 LR4 high-side, LR8 middle, LR16 lower-side를
함께 제시해야 한다.

## 관련 artifact

| 파일 | 의미 |
|---|---|
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708.csv` | original paired raw measurement |
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_rerun2_20260708.csv` | rerun2 paired raw measurement |
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_rerun2_20260708_matrix.csv` | rerun2 실행 matrix |
| `results/raw/rtx3090_shared_paired_lr16_30s_stability_rerun2_20260708_warmup.csv` | rerun2 warmup raw measurement |
| `results/summary/rtx3090_shared_paired_lr16_30s_stability_rerun2_power_api_audit_20260708.md` | rerun2 Power API audit |
| `results/summary/rtx3090_shared_paired_lr16_30s_stability_rerun2_power_state_audit_20260708.md` | rerun2 power-state audit |
| `results/summary/rtx3090_shared_paired_lr16_30s_combined_power_api_audit_20260708.md` | combined Power API audit |
| `results/summary/rtx3090_shared_paired_lr16_30s_combined_power_state_audit_20260708.md` | combined power-state audit |
| `results/summary/rtx3090_shared_paired_lr16_30s_combined_matched_control_summary_20260708.csv` | combined matched-control summary |
| `results/summary/rtx3090_shared_paired_lr16_30s_combined_component_reliability_audit_20260708.md` | combined reliability audit |
| `results/summary/rtx3090_shared_paired_lr16_30s_combined_instability_audit_20260708.md` | combined instability audit |
