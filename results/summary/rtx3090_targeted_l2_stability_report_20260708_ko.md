# RTX 3090 L2 Targeted Stability Rerun

작성일: 2026-07-08

## 목적

기존 factor exact-NCU 결과에서 L2 CG path는 NCU 경로가 accepted였지만, broad
finalplan power-state audit에 small-group caution이 남아 있었다. 이 문서는 L2만
더 긴 시간과 더 많은 반복으로 다시 측정해 current reporting L2 coefficient를
강화할 수 있는지 확인한 결과다.

이 rerun은 새 NCU profiling run이 아니라 energy numerator 안정성 확인이다. L2
denominator는 기존 2026-07-08 factor NCU sidecar의 exact matching
`ncu_actual_exact` 값을 사용했다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment mode | `l2_cg_load_only` | L1 bypass/cache-global load path |
| control mode | `clocked_empty` | 같은 launch/clock 구조의 empty control |
| W_SM | 64 | KiB/SM |
| blocks/SM | 16 | blocks/SM |
| active SM | 82 | SM |
| load_repeat sweep | 4, 8, 16 | count |
| seconds | 20 | s |
| repeats | 10 | count |
| raw rows | 60 | 2 modes x 3 load_repeat x 10 repeats |
| matched-control rows | 30 | treatment rows only |

## Power API Gate

Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다. RTX
3090의 `GetPowerUsage` fallback 의미는 1초 평균이지만, 이번 결과의 energy
numerator는 endpoint power 적분이 아니라 `nvmlDeviceGetTotalEnergyConsumption`
mJ counter 차분이다.

| gate | 결과 | 해석 |
|---|---:|---|
| power API final candidate | 60/60 | `nvml_total_energy`, `total_energy_mj_delta` |
| provisional | 0/60 | fallback 미사용 |
| reject | 0/60 | profile power semantics mismatch 없음 |
| measurement scope | `gpu_device_total_energy_counter` | GPU/device total energy counter 차분 |

Power-state audit은 59/60 `ok`, 1/60 `caution`이었다. caution row는
`clocked_empty`, LR=4의 temperature outlier였고, reject row는 없었다.

| power-state status | rows | 비고 |
|---|---:|---|
| ok | 59 | coefficient 계산을 막는 outlier 없음 |
| caution | 1 | temperature outlier, control row |
| reject | 0 | 없음 |

## NCU Path Validation

이번 rerun은 기존 factor NCU sidecar를 재사용했다. 같은 좌표
`W_SM=64 KiB`, `blocks/SM=16`, `load_repeat=4/8/16`에 대해 L2 path는 다음처럼
검증되어 있었다.

| load_repeat | L1 hit rate (%) | L2 hit rate (%) | NCU verdict |
|---:|---:|---:|---|
| 4 | 0.000006 | 99.8978 | accepted L2 hit path |
| 8 | 0.000003 | 99.9368 | accepted L2 hit path |
| 16 | 0.000002 | 99.9232 | accepted L2 hit path |

즉 이 결과는 `l2_cg_load_only`가 L1에서 끝난 값을 L2로 오해한 것이 아니라,
NCU hit-rate 기준으로 L1이 거의 배제되고 L2 hit가 지배적인 path임을 확인한 뒤
계산한 effective coefficient다.

## Matched-Control 결과

계산식은 다음이다.

```text
delta_E_J = E_l2_cg_load_only_J - (E_clocked_empty_J / t_control_s) * t_treatment_s
coefficient = delta_E_J / NCU actual L2 bytes
```

| 항목 | 값 | 단위 |
|---|---:|---|
| valid rows | 30/30 | rows |
| denominator source | `ncu_actual_exact` | - |
| median | 7.82558 | pJ/byte |
| median | 0.978197 | pJ/bit |
| min-max | 0.412492-1.49933 | pJ/bit |
| bootstrap median 95% CI | 0.934865-1.13941 | pJ/bit |
| confidence | medium-high | - |
| reliability verdict | accepted | matched-control/power API/NCU gate |
| evidence matrix level | accepted_with_caution | coefficient-eligible control temperature caution 1개를 metadata로 반영 |
| instability audit | stable_detail_rows | - |

기존 broad factor exact-NCU L2 median은 1.138 pJ/bit였다. 새 targeted rerun의
median은 0.978 pJ/bit이며, 새 95% CI 상한 1.139 pJ/bit가 기존 median과 거의
겹친다. 따라서 두 결과는 서로 모순이라기보다 power-state 안정성과 반복 수가
개선되면서 대표값이 약간 낮아진 것으로 보는 것이 합리적이다.

## 결론

L2 CG path는 current reporting primary 값으로 사용할 수 있다. coefficient 자체의
reliability audit은 `accepted`다. Evidence matrix에서는 power-state audit의
coefficient-eligible control temperature caution 1개를 traceability metadata로
남긴다.

| 항목 | 판단 |
|---|---|
| power API | 통과. total energy counter만 사용 |
| power-state | reject 없음. control temperature caution 1개만 존재 |
| NCU path | 통과. L1 hit ~0%, L2 hit ~99.9% |
| matched-control | 30/30 valid, 음수/weak-signal row 없음 |
| current reporting value | 0.978 pJ/bit, `accepted` |

단, 이 값은 L2 SRAM bitcell의 순수 물리 에너지가 아니다. NVML GPU/device energy
차분, L2 hit path microbenchmark, NCU denominator 검증으로 얻은 board-level
effective microbenchmark coefficient다. L2 controller, interconnect, issue,
scoreboard/control overhead가 일부 포함될 수 있다.

## 관련 산출물

| artifact | path |
|---|---|
| power API audit | `results/summary/rtx3090_targeted_l2_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_targeted_l2_power_state_audit_20260708.md` |
| power-state filtered matched-control report | `results/summary/rtx3090_targeted_l2_powerstate_filtered_matched_control_report_20260708.md` |
| power-state filtered reliability audit | `results/summary/rtx3090_targeted_l2_powerstate_filtered_component_reliability_audit_20260708.md` |
| power-state filtered instability audit | `results/summary/rtx3090_targeted_l2_powerstate_filtered_instability_audit_20260708.md` |
