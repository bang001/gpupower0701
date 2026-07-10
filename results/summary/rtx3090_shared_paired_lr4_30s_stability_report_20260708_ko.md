# RTX 3090 Shared LR=4 Paired 30초 안정성 점검

작성일: 2026-07-08

## 목적

Shared LR=16 paired auxiliary는 `0.054 pJ/bit`로 낮고 confidence가 low였다. 이
실험은 같은 control-treatment-control paired 구조에서 `load_repeat=4`를 측정해,
값이 낮아진 이유가 paired sequence 자체 때문인지, 아니면 Shared path가
`load_repeat` 조건에 민감하기 때문인지 분리하기 위한 보강 실험이다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU/profile | RTX 3090 / `rtx3090` | GA102 |
| treatment mode | `shared_scalar_load_only` | shared-memory scalar load path |
| control mode | `clocked_empty` | 같은 launch/clock 구조 control |
| sequence | control-before -> treatment -> control-after | paired/bracketed |
| W_SM | 64 | KiB/SM |
| blocks/SM | 16 | blocks/SM |
| active_SM | 82 | SM |
| load_repeat | 4 | count |
| seconds | 30 | s |
| treatment repeats | 6 | rows |
| measurement rows | 18 | 12 controls + 6 treatments |

NCU denominator는 기존 factor stability NCU sidecar의 accepted `shared_memory_path`
및 `ncu_actual_exact` 값을 재사용했다. 따라서 이 run은 NCU path 재검증이 아니라
energy numerator와 pairing 안정성 확인이다.

## Power API 및 Power-State Gate

Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다.
RTX 3090의 `GetPowerUsage` metadata는 `one_sec_average`지만, coefficient 분자는
endpoint power fallback이 아니라 `nvml_total_energy` + `total_energy_mj_delta`다.

| gate | 결과 | 해석 |
|---|---:|---|
| Power API audit | 18/18 `final_candidate` | total energy counter만 사용 |
| `energy_source` | `nvml_total_energy` | final numerator 후보 |
| `energy_integration_method` | `total_energy_mj_delta` | mJ counter 전후 차분 |
| `nvml_power_usage_semantics` | `one_sec_average` | RTX 3090 profile과 일치 |
| Power-state audit | 18/18 `ok` | reject/caution 없음 |

## Matched-Control 결과

| 항목 | 값 | 단위 |
|---|---:|---|
| detail rows | 6 | treatment rows |
| valid rows | 6 | rows |
| invalid rows | 0 | rows |
| median | 0.236322680069 | pJ/bit |
| min-max valid | 0.207948743674-0.297012907789 | pJ/bit |
| bootstrap median 95% CI | 0.212347530850-0.296771026679 | pJ/bit |
| confidence | medium | - |
| reliability | `accepted` | - |
| instability | `stable_detail_rows` | - |

## LR4/LR16 비교

| 실험 | condition | valid/total | median | 단위 | 해석 |
|---|---|---:|---:|---|---|
| Shared primary | LR=4/8/16 mixed, 20 s targeted | 29/30 | 0.152 | pJ/bit | current primary, mixed condition |
| Shared LR4 non-paired auxiliary | LR=4, 30 s | 9/10 | 0.216 | pJ/bit | high-side auxiliary |
| Shared LR4 paired auxiliary | LR=4, C-T-C paired 30 s | 6/6 | 0.236 | pJ/bit | clean high-side auxiliary |
| Shared LR16 paired auxiliary | LR=16, C-T-C paired 30 s | 5/6 | 0.054 | pJ/bit | low-side, low-stability auxiliary |

LR4 paired 결과가 기존 LR4 non-paired auxiliary와 정합하므로, paired sequence 자체가
Shared 값을 낮춘 것은 아니다. LR16 paired가 낮게 나온 것은 LR/control/denominator
조건에 따른 method sensitivity로 해석하는 것이 타당하다.

## 판단

- Power API, power-state, matched-control, reliability gate가 모두 통과했다.
- Shared LR4 high-side coefficient는 `0.22-0.24 pJ/bit` 수준으로 재현됐다.
- Shared LR16 paired auxiliary는 lower-side evidence로 남기며 primary로 쓰지 않는다.
- 현재 보고에서는 Shared primary `0.152 pJ/bit`를 유지하되, LR4 paired `0.236 pJ/bit`
  및 LR16 paired `0.054 pJ/bit`를 함께 제시해 LR/method sensitivity를 숨기지 않는다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_shared_paired_lr4_30s_stability_20260708.csv` |
| matrix CSV | `results/raw/rtx3090_shared_paired_lr4_30s_stability_20260708_matrix.csv` |
| warmup CSV | `results/raw/rtx3090_shared_paired_lr4_30s_stability_20260708_warmup.csv` |
| power API audit | `results/summary/rtx3090_shared_paired_lr4_30s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_shared_paired_lr4_30s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_shared_paired_lr4_30s_stability_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_shared_paired_lr4_30s_stability_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_shared_paired_lr4_30s_stability_instability_audit_20260708.md` |
