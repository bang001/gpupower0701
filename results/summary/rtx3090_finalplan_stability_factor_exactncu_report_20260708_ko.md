# RTX 3090 Finalplan Factor Exact-NCU Report

작성일: 2026-07-08

## 목적

이 문서는 RTX 3090 stability energy run을 factor별 NCU sidecar와 결합해 다시 분석한
결과다. 이전 LR=4 NCU 대표 검증과 달리, 이번 NCU sidecar는 현재 stability raw가
사용한 factor를 직접 포함한다.

| path | NCU factor coverage |
|---|---|
| Tensor/control | `reuse_factor=1,2,4,8,16` |
| Shared scalar | `load_repeat=4,8,16` |
| Global L1 | `load_repeat=4,8,16` |
| L2 CG | `load_repeat=4,8,16` |
| DRAM CG | `load_repeat=4,8,16` |

따라서 memory path denominator는 `ncu_actual_same_working_set`이 아니라
`ncu_actual_exact`로 계산된다.

## 입력과 Power API Gate

| 항목 | 값 |
|---|---|
| GPU | RTX 3090 / GA102 |
| NCU version | Nsight Compute 2026.1.1 |
| NCU summary | `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv` |
| NCU acceptance | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| matched-control summary | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_summary_20260708.csv` |
| matched-control detail | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_detail_20260708.csv` |
| power API audit | `results/summary/rtx3090_finalplan_stability_power_api_audit_20260708.md` |
| component reliability audit | `results/summary/rtx3090_finalplan_stability_component_reliability_audit_20260708.md` |
| matched-control instability audit | `results/summary/rtx3090_finalplan_stability_matched_control_instability_audit_20260708.md` |
| Tensor targeted rerun | `results/summary/rtx3090_tensor_targeted_rf8_rf16_report_20260708_ko.md` |
| Shared/L1 targeted rerun | `results/summary/rtx3090_targeted_shared_l1_stability_report_20260708_ko.md` |

Power API 해석은 [power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)를 따른다.

| gate | 통과 여부 | 근거 |
|---|---|---|
| total energy counter | pass | power API audit에서 102/102 row `nvml_total_energy_supported=true` |
| energy source | pass | power API audit에서 102/102 row `energy_source=nvml_total_energy` |
| integration | pass | power API audit에서 102/102 row `energy_integration_method=total_energy_mj_delta` |
| power semantics | pass | power API audit에서 102/102 row RTX 3090 profile의 `nvml_power_usage_semantics=one_sec_average` |
| fallback power integral | not used | power API audit에서 provisional/reject row 0 |
| NCU denominator | pass | memory path summary rows 모두 `ncu_denominator_rows > 0` |

RTX 3090의 `GetPowerUsage` fallback 의미는 1초 평균이지만, 이번 energy numerator는
fallback power integration이 아니라 NVML total energy mJ counter 차분이다.

## Component Reliability Verdict

아래 verdict는 power API audit, NCU acceptance, matched-control summary/detail을
결합한 [component reliability audit](rtx3090_finalplan_stability_component_reliability_audit_20260708.md)의 결과다.

| component | verdict | median | unit | 해석 |
|---|---|---:|---|---|
| Tensor MMA incremental, broad RF sweep | `accepted_low_stability` | 0.169745 | pJ/FLOP | path는 accepted지만 confidence가 low라 targeted follow-up을 우선 |
| Shared scalar path | `accepted_with_caution` | 0.151126 | pJ/bit | core gates 통과, invalid detail row 3개 존재 |
| Global L1 hit path | `accepted_with_caution` | 0.150451 | pJ/bit | core gates 통과, invalid detail row 2개 존재 |
| L2 CG hit path | `accepted` | 1.138107 | pJ/bit | power, NCU path, denominator, 안정도 gate 통과 |
| DRAM CG streaming path | `accepted_sanity` | 3.540698 | pJ/bit | hierarchy sanity 값이며 physical DRAM device energy가 아님 |

## Instability Root Cause

[matched-control instability audit](rtx3090_finalplan_stability_matched_control_instability_audit_20260708.md)
기준으로 `accepted_with_caution`의 원인은 다음이다.

| component | valid/detail rows | invalid 이유 | 판단 |
|---|---:|---|---|
| Shared scalar path | 6/9 | `negative_coefficient` 2개, `delta_E<10J`/`delta_fraction<0.005` 1개 | NCU path가 아니라 treatment-control 신호가 작고 control drift에 민감함 |
| Global L1 hit path | 7/9 | `negative_coefficient` 1개, `delta_E<10J`/`delta_fraction<0.005` 1개 | NCU path가 아니라 board-level delta signal이 noise floor에 가까움 |

따라서 다음 개선 실험은 gate를 낮추는 것이 아니라 Shared/L1만 대상으로
`seconds=20-30`, `repeats>=10`, 동일 power API audit, 동일 NCU factor sidecar 조건으로
targeted stability rerun을 수행하는 것이다. 이 follow-up은
[rtx3090_targeted_shared_l1_stability_report_20260708_ko.md](rtx3090_targeted_shared_l1_stability_report_20260708_ko.md)에
정리했다.

## Tensor Targeted Stability Follow-up

Tensor만 RF=8/16 조건에서 20초, 6회 반복으로 다시 측정했다. 이 follow-up은
[rtx3090_tensor_targeted_rf8_rf16_report_20260708_ko.md](rtx3090_tensor_targeted_rf8_rf16_report_20260708_ko.md)에
정리했다.

| gate/result | 값 | 해석 |
|---|---:|---|
| Power API audit | 24/24 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| Power-state audit | 24/24 `ok` | 평균 전력 outlier 없음 |
| matched-control valid | 12/12 | 음수/weak-signal row 없음 |
| combined median | 0.106658 pJ/FLOP | lower-side Tensor candidate |
| bootstrap median 95% CI | 0.083454-0.133532 pJ/FLOP | medium-high stability |
| RF=8 median | 0.133532 pJ/FLOP | RF 의존성 존재 |
| RF=16 median | 0.083454 pJ/FLOP | RF 의존성 존재 |

따라서 RTX 3090 Tensor는 broad RF sweep의 0.169745 pJ/FLOP보다 targeted
RF=8/16 결과인 0.106658 pJ/FLOP를 lower-side candidate로 둔다. 이후 fixed
`ITER=8000000` 보조실험에서 0.145635 pJ/FLOP, RF=8 duration-scaling에서
0.143114 pJ/FLOP, RF=16 duration-scaling에서 0.076647 pJ/FLOP가 나왔으므로,
최종 보고에서는 Tensor를 RF-dependent effective coefficient로 표기한다.

## Shared/L1 Targeted Stability Follow-up

Shared/L1만 20초, 10회 반복으로 다시 측정했다. Power API audit은 120/120 row가
`final_candidate`로 통과했으므로 이번 rerun도 `nvml_total_energy` 기반이다.

| component | factor exact-NCU median | targeted median | targeted valid/total | 판단 |
|---|---:|---:|---:|---|
| Shared scalar path | 0.151126 pJ/bit | 0.152395 pJ/bit | 29/30 | 값과 hierarchy가 정합한다. caution은 유지하되 안정성은 개선됨 |
| Global L1 hit path | 0.150451 pJ/bit | 0.104690 pJ/bit | 26/30 | LR=16 negative row 4개가 남아 대표값 교체 보류 |

이 follow-up은 Shared scalar path의 0.15 pJ/bit 수준 계수를 지지하지만, Global L1은
아직 board-level 차분 noise와 control drift에 민감하다는 점을 더 분명히 보여준다.
추가 power-state audit에서는 Global L1 negative row 중 2개가 평균 전력 저하
outlier로 확인되었다. 따라서 L1의 남은 문제는 NCU hit-rate 실패가 아니라
row-level power-state anomaly와 weak matched-control signal의 혼합이다.

추가로 `load_repeat=4`를 고정하고 10초, 20초, 30초로 duration을 바꾼
[L1 duration-scaling check](rtx3090_l1_duration_scaling_report_20260708_ko.md)를 수행했다.
이 실험은 30/30 row가 power API final 후보였고 power-state audit도 30/30 ok였다.
matched-control median은 0.156 pJ/bit, OLS slope는 0.147 pJ/bit, Theil-Sen slope는
0.149 pJ/bit로 기존 L1 0.150 pJ/bit와 정합했다.

## NCU Acceptance

| component candidate | accepted | rejected | 해석 |
|---|---:|---:|---|
| Tensor increment candidate | 5 | 0 | 모든 reuse factor에서 HMMA 확인 |
| Register control candidate | 5 | 0 | 모든 reuse factor에서 no-HMMA control 확인 |
| Shared memory path | 3 | 0 | LR 4,8,16 shared bytes 확인 |
| Global L1 hit path | 3 | 0 | LR 4,8,16 L1 hit 확인 |
| L2 hit path | 3 | 0 | LR 4,8,16 L1 bypass/L2 hit 확인 |
| DRAM sanity path | 3 | 0 | LR 4,8,16 DRAM streaming 확인 |

Tensor/register acceptance는 absolute bytes threshold만 사용하지 않고,
bytes/HMMA 또는 bytes/register-op ratio를 함께 본다. 이렇게 해야 reuse factor가 커질 때
setup/cache traffic의 absolute byte가 증가한다는 이유만으로 부당하게 reject되는 문제를 줄일 수 있다.

NCU 실행 중 `--cache-control none`, `--clock-control none` 조건이었기 때문에
Nsight Compute가 uncontrolled cache/clock warning을 출력했다. 이는 energy numerator에는
직접 쓰이지 않지만, NCU counter reproducibility 한계로 보고한다.

## Factor Exact-NCU 결과

| component | rows used | median | unit | median pJ/bit | confidence |
|---|---:|---:|---|---:|---|
| Tensor MMA incremental | 15 | 0.169745 | pJ/FLOP | - | low |
| Shared scalar path | 6 | 1.20901 | pJ/byte | 0.151126 | medium |
| Global L1 hit path | 7 | 1.20361 | pJ/byte | 0.150451 | medium |
| L2 CG hit path | 9 | 9.10486 | pJ/byte | 1.13811 | medium |
| DRAM CG streaming sanity | 9 | 28.3256 | pJ/byte | 3.54070 | medium-high |

Hierarchy는 다음처럼 정리된다.

```text
Shared scalar ~= Global L1  <  L2 CG  <  DRAM CG sanity
0.151 pJ/bit    0.150 pJ/bit   1.138 pJ/bit   3.541 pJ/bit
```

## Broad Strict 결과와 비교

| component | broad strict median | factor exact-NCU median | 판단 |
|---|---:|---:|---|
| Tensor broad RF sweep | 0.170 pJ/FLOP | 0.169745 pJ/FLOP | 일치하지만 confidence low. current reporting은 targeted 0.106658 pJ/FLOP primary와 fixed-ITER 0.145635 pJ/FLOP auxiliary를 함께 사용 |
| Shared scalar | 0.151 pJ/bit | 0.151126 pJ/bit | 일치 |
| Global L1 | 0.150 pJ/bit | 0.150451 pJ/bit | 일치 |
| L2 CG | 1.138 pJ/bit | 1.13811 pJ/bit | 일치 |
| DRAM CG | 3.542 pJ/bit | 3.54070 pJ/bit | 일치 |

따라서 2026-07-08 RTX 3090 stability 결과는 “대표 NCU denominator를 확장한 값”이 아니라,
현재 stability factor 범위에서는 factor별 NCU exact denominator로 재현된 값이라고 볼 수 있다.

## 남은 한계

| 한계 | 영향 |
|---|---|
| Tensor broad sweep confidence low | `reg_mma - reg_operand_only` 차분 산포가 큼. Targeted RF=8/16 follow-up은 accepted지만 RF 의존성이 남음 |
| Shared/L1 invalid rows 존재 | targeted rerun에서도 Shared 1/30, L1 4/30 row가 negative 또는 weak-signal로 제외됨 |
| L2/DRAM stall-heavy | long scoreboard가 크므로 pure movement energy로 해석하면 안 됨 |
| NCU cache/clock uncontrolled warning | NCU counter는 path 검증용이며 energy numerator가 아님 |
| RTX 3090만 완료 | A100/V100/H100에서는 architecture별 W_SM, L2/shared/HBM 조건으로 재실험 필요 |

## 결론

RTX 3090에 대해서는 현재 기준에서 memory path 보고값은 factor exact-NCU 결과로 둔다.
Tensor는 targeted RF=8/16 follow-up 0.106658 pJ/FLOP를 blended candidate로,
fixed-ITER auxiliary 0.145635 pJ/FLOP, RF=8 duration-scaling 0.143114 pJ/FLOP,
RF=16 duration-scaling 0.076647 pJ/FLOP를 method-sensitivity check로 함께 둔다.
따라서 Tensor는 RF16 lower 약 0.06-0.09 pJ/FLOP, RF8 upper 약 0.14-0.15 pJ/FLOP로
분리 보고한다. 단 모든 값은 순수 silicon-level energy가 아니라
board-level total energy, matched-control 차분, NCU path/denominator 검증을 결합한
workload-dependent effective microbenchmark coefficient다.
