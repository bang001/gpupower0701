# RTX 3090 Shared LR=16 Paired 30초 안정성 점검

작성일: 2026-07-08

## 목적

Shared scalar primary 결과는 `0.152 pJ/bit`였지만, `load_repeat=16` 조건에서
weak/negative matched-control row 1개가 남았다. 이 실험은 L1에서 효과가 있었던
control-treatment-control paired 순서를 Shared `load_repeat=16`에도 적용해, 남은
문제가 control drift인지 또는 LR=16 조건 자체의 weak signal인지 확인하기 위한
보조 실험이다.

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
| load_repeat | 16 | count |
| seconds | 30 | s |
| treatment repeats | 6 | rows |
| measurement rows | 18 | 12 controls + 6 treatments |

NCU denominator는 기존 factor stability NCU sidecar의 accepted
`shared_memory_path` / `ncu_actual_exact` 값을 재사용했다. 따라서 이 run은 NCU
path 재검증이 아니라 energy numerator와 treatment-control pairing 안정성 확인이다.

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
| Power-state audit | 17/18 `ok`, 1/18 `reject` | reject row는 control row |

Power-state reject는 `clocked_empty` control 1개에서 발생했다. 분석에서는
`--power-state-audit-csv`와 `--exclude-power-state-rejects`를 적용해 이 row를
pairing 전에 제외했다.

## Matched-Control 결과

| 항목 | 값 | 단위 |
|---|---:|---|
| detail rows | 6 | treatment rows |
| valid rows | 5 | rows |
| invalid rows | 1 | rows |
| median | 0.053993691505 | pJ/bit |
| min-max valid | 0.032850497594-0.104059511517 | pJ/bit |
| bootstrap median 95% CI | 0.032850497594-0.104059511517 | pJ/bit |
| confidence | low | - |
| reliability | `accepted_low_stability` | - |
| instability | `needs_stability_followup` | - |

Invalid row는 negative가 아니라 `delta_fraction<0.005`이다. 즉 paired 순서로
큰 음수는 줄었지만, LR=16 조건의 board-level treatment-control delta가 여전히
작아서 안정적인 primary coefficient로 쓰기 어렵다.

## 기존 Shared 결과와 비교

| 실험 | 조건 | valid/total | median | 단위 | 해석 |
|---|---|---:|---:|---|---|
| Shared primary | W=64 KiB, LR=4/8/16, 20 s | 29/30 | 0.152 | pJ/bit | current primary, accepted_with_caution |
| Shared LR4 30초 auxiliary | W=64 KiB, LR=4, 30 s | 9/10 | 0.216 | pJ/bit | high-side auxiliary |
| Shared LR16 paired 30초 auxiliary | W=64 KiB, LR=16, C-T-C paired | 5/6 | 0.054 | pJ/bit | low-stability lower-side auxiliary |

이 결과는 Shared primary를 `0.054 pJ/bit`로 교체하라는 뜻이 아니다. 오히려 Shared
scalar path coefficient가 `load_repeat`와 paired/control 정책에 민감하고, LR=16에서는
분모가 커지는 반면 추가 board-level energy delta가 충분히 커지지 않아 low-side 값이
나온다는 점을 보여준다.

## 판단

- Power API 기준은 통과했다. 모든 measurement row가 `nvml_total_energy`와
  `total_energy_mj_delta`를 사용했다.
- Power-state reject control row 1개는 coefficient pairing 전에 제외했다.
- NCU shared path는 기존 accepted sidecar를 사용했으므로 denominator는
  `ncu_actual_exact`다.
- 결과는 5/6 valid지만 confidence가 low이고 1개 weak-signal row가 남았다.
- 따라서 이 run은 Shared primary를 강화하는 보조 근거라기보다, Shared coefficient의
  LR/method sensitivity와 lower-side bound를 보여주는 auxiliary evidence다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708.csv` |
| matrix CSV | `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708_matrix.csv` |
| warmup CSV | `results/raw/rtx3090_shared_paired_lr16_30s_stability_20260708_warmup.csv` |
| power API audit | `results/summary/rtx3090_shared_paired_lr16_30s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_shared_paired_lr16_30s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_shared_paired_lr16_30s_stability_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_shared_paired_lr16_30s_stability_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_shared_paired_lr16_30s_stability_instability_audit_20260708.md` |
