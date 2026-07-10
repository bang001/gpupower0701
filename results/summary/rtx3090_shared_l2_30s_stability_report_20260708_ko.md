# RTX 3090 Shared/L2 30초 LR4 안정성 추가 점검

작성일: 2026-07-08

## 목적

현재 reporting에서 Shared scalar path는 `0.152 pJ/bit`, L2 CG hit path는
`0.978 pJ/bit`를 primary candidate로 둔다. 다만 두 값 모두 LR4/8/16을 섞은
targeted stability rerun에서 나온 중앙값이다. 이 추가 실험은 `load_repeat=4`를
고정하고 30초, 10회 반복으로 다시 실행하여 단일 LR4 조건의 재현성을 확인했다.

이 실험은 primary 값을 즉시 대체하기 위한 것이 아니라, component coefficient가
workload parameter에 얼마나 민감한지 확인하는 보강 실험이다.

## 실험 조건

| 항목 | 값 |
|---|---|
| GPU/profile | RTX 3090 / `rtx3090` |
| treatment modes | `shared_scalar_load_only`, `l2_cg_load_only` |
| control mode | `clocked_empty` |
| W_SM | 64 KiB |
| blocks/SM | 16 |
| active_SM | 82 SM |
| load_repeat | 4 |
| seconds | 30 s |
| repeats | 10 |
| denominator | 기존 factor-stability NCU sidecar의 동일 좌표 actual bytes |

## Power API 및 상태 점검

Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다.

| gate | 결과 | 해석 |
|---|---:|---|
| raw rows | 30 | control 10개, Shared 10개, L2 10개 |
| Power API audit | 30/30 `final_candidate` | 모두 `nvml_total_energy + total_energy_mj_delta` |
| `nvml_power_usage_semantics` | `one_sec_average` | RTX 3090 profile과 일치. final numerator는 total-energy counter |
| SMID 검증 | 30/30 ok | active SM 배치 이상 없음 |
| Power-state audit | 29/30 `ok`, 1/30 `reject` | L2 row 1개가 `avg_power_low_outlier` |

Power-state reject row는 `l2_cg_load_only_1783466460984_r0`이고, matched-control에서도
`delta_E=-50.01 J`인 negative row로 나타났다. 따라서 이 row는 component coefficient
계산에서 제외하는 것이 맞다.

## NCU 경로 검증

기존 factor-stability NCU sidecar의 동일 좌표를 사용했다.

| mode | 주요 NCU 값 | 해석 |
|---|---|---|
| `shared_scalar_load_only`, W=64KiB, LR=4 | shared bytes 5.37401e11 B, bank conflict 0, stall long scoreboard 0.002106 % | shared scalar path로 인정 |
| `l2_cg_load_only`, W=64KiB, LR=4 | L1 hit 0.000006 %, L2 hit 99.8978 %, L2 bytes 5.37997e11 B, DRAM bytes 5.40672e8 B | L1을 사실상 배제한 L2 hit path로 인정 |

NCU는 energy가 아니라 path와 denominator 검증에만 사용했다.

## Matched-control 결과

| component | valid/total | median | unit | 95% median CI | min valid | max valid | reliability |
|---|---:|---:|---|---:|---:|---:|---|
| Shared scalar path, LR4 | 9/10 | 0.216218484187 | pJ/bit | 0.189581848925-0.234533886279 | 0.154589101803 | 0.258233613664 | accepted_with_caution |
| L2 CG hit path, LR4 | 9/10 | 1.297639212169 | pJ/bit | 1.122828663975-1.338472630938 | 1.114488986289 | 1.417690574495 | accepted_with_caution |

무효 row는 다음과 같다.

| component | 원인 |
|---|---|
| Shared scalar path | `delta_fraction=0.001194`로 configured noise floor 0.5% 미만 |
| L2 CG hit path | power-state reject row와 겹친 negative coefficient |

## 기존 targeted 결과와 비교

기존 targeted rerun을 LR별로 나누면 새 결과와 정합한다.

| component | 기존 targeted LR4 median | 새 30초 LR4 median | 기존 mixed LR4/8/16 primary | 해석 |
|---|---:|---:|---:|---|
| Shared scalar path | 0.224704146465 pJ/bit | 0.216218484187 pJ/bit | 0.152395459548 pJ/bit | LR4 단일조건은 mixed median보다 높다 |
| L2 CG hit path | 1.278723713091 pJ/bit | 1.297639212169 pJ/bit | 0.978197461641 pJ/bit | LR4 단일조건은 mixed median보다 높다 |

즉, 새 run은 이전 결과를 반박하지 않는다. 오히려 `load_repeat`/method에 따라
effective coefficient가 달라진다는 점을 더 분명히 보여준다.

## 판단

- Power API 기준은 매우 좋다. 모든 row가 `nvml_total_energy` 기반 final 후보였다.
- NCU path도 기존 sidecar에서 accepted된 동일 좌표를 사용했다.
- Shared와 L2 모두 LR4 조건에서는 기존 mixed primary보다 높은 coefficient가 재현됐다.
- 따라서 Shared와 L2를 하나의 순수 component 상수로 쓰면 안 된다.
- 현재 reporting은 primary median을 유지하되, Shared는 대략 `0.15-0.22 pJ/bit`,
  L2는 mixed primary `0.98 pJ/bit`와 LR4 auxiliary `1.30 pJ/bit`를 함께 보고한다.
- 이 값은 모두 workload-dependent effective microbenchmark coefficient이며,
  순수 SRAM array 또는 bitcell energy가 아니다.

## 관련 산출물

| artifact | path |
|---|---|
| raw CSV | `results/raw/rtx3090_shared_l2_30s_stability_20260708.csv` |
| power API audit | `results/summary/rtx3090_shared_l2_30s_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_shared_l2_30s_stability_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_shared_l2_30s_stability_matched_control_report_20260708.md` |
| reliability audit | `results/summary/rtx3090_shared_l2_30s_stability_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_shared_l2_30s_stability_instability_audit_20260708.md` |
