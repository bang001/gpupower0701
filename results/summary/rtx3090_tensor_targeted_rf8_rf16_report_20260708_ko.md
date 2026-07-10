# RTX 3090 Tensor Targeted RF8/RF16 Stability Report

작성일: 2026-07-08

## 목적

기존 factor exact-NCU 결과에서 Tensor MMA incremental 값은 NCU path는 accepted였지만
계수 분산이 커서 `accepted_low_stability`로 분류됐다. 이 문서는 Tensor만 대상으로
더 긴 duration과 더 많은 반복을 적용해 `reg_mma - reg_operand_only` 차분이 안정적으로
나오는지 확인한 targeted follow-up이다.

이 값은 순수 Tensor Core 회로 에너지가 아니다. NVML total energy counter로 얻은
board-level energy에서 no-MMA register/control kernel을 차분한
effective microbenchmark coefficient다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment | `reg_mma` | FP16 WMMA/HMMA 실행 |
| control | `reg_operand_only` | HMMA 없이 register fragment/operand loop 유지 |
| W_SM | 2048 | KiB/SM, Tensor mode에서는 register footprint가 아니라 고정 좌표 |
| blocks/SM | 16 | resident blocks per SM |
| active_SM | 82 | SM |
| reuse_factor | 8, 16 | count |
| seconds | 20 | s per command |
| repeats | 6 | count per mode/reuse |
| raw rows | 24 | 2 modes x 2 reuse factors x 6 repeats |
| matched-control rows | 12 | treatment rows matched to nearest control |

## Power API / 상태 Gate

Power API 해석은 `docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따른다.

| gate | 결과 | 근거 |
|---|---:|---|
| Power API audit | 24/24 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| fallback power integral | 0 row | `GetPowerUsage` endpoint 적분 미사용 |
| RTX 3090 power semantics metadata | 24/24 `one_sec_average` | profile metadata 일치 |
| Power-state audit | 24/24 `ok` | 평균 전력/endpoint power outlier 없음 |
| SMID check | 24/24 ok | active SM/block 배치 정상 |
| matched-control valid | 12/12 | negative/weak-signal row 없음 |

## 결과

| view | rows | median | min | max | unit | confidence/status |
|---|---:|---:|---:|---:|---|---|
| RF=8/16 combined | 12 | 0.106658 | 0.032230 | 0.174529 | pJ/FLOP | `medium-high`, reliability `accepted` |
| RF=8 only | 6 | 0.133532 | 0.094569 | 0.174529 | pJ/FLOP | stable positive rows |
| RF=16 only | 6 | 0.083454 | 0.032230 | 0.121056 | pJ/FLOP | stable positive rows, lower median |

| 항목 | 값 |
|---|---:|
| bootstrap median 95% CI | 0.083454 - 0.133532 pJ/FLOP |
| combined stdev | 0.041018 pJ/FLOP |
| combined relative IQR | 0.419 |
| combined CV | 0.385 |
| delta_E median | 173.476 J |
| delta signal fraction median | 0.0502 |

## 기존 Tensor 결과와 비교

| 실험 | 조건 | rows | median | unit | verdict |
|---|---|---:|---:|---|---|
| Factor exact-NCU broad sweep | RF=1,2,4,8,16, 5 s, 3 repeats | 15 | 0.169745 | pJ/FLOP | `accepted_low_stability` |
| Targeted Tensor follow-up | RF=8,16, 20 s, 6 repeats | 12 | 0.106658 | pJ/FLOP | `accepted` |

해석:

- Targeted run은 power API와 power-state gate를 모두 통과했고, 12개 matched-control row가 모두 양수다.
- 따라서 RTX 3090 Tensor reporting value는 broad sweep의 0.170 pJ/FLOP보다
  targeted RF=8/16 결과인 0.107 pJ/FLOP를 더 신뢰도 높은 lower-side 후보로 둔다.
- 이후 fixed `ITER=8000000` 보조실험이 0.146 pJ/FLOP median으로 통과했고,
  RF=8 duration-scaling은 0.143 pJ/FLOP, RF=16 duration-scaling은 0.077 pJ/FLOP로
  통과했다. 최종 보고에서는 Tensor를 RF-dependent effective coefficient로 표기한다.
- 추가 RF=8 duration-scaling 보조실험은 0.143 pJ/FLOP median과
  0.144-0.156 pJ/FLOP slope를 보여 range 상단을 지지했다.
- 추가 RF=16 duration-scaling 보조실험은 0.077 pJ/FLOP median과
  0.053-0.071 pJ/FLOP slope를 보여 lower-side가 재현됨을 보였다.
- 단 RF=8 median은 0.134 pJ/FLOP, RF=16 median은 0.083 pJ/FLOP로 차이가 있다.
  따라서 이 값은 workload-effective coefficient이며, Tensor Core transistor-level
  constant로 쓰면 안 된다.

## 자가비판

| 한계 | 영향 | 다음 보완 |
|---|---|---|
| RF=8/16만 targeted rerun | RF=1/2/4의 broad sweep 분산을 직접 제거한 것은 아님 | RF=4/8/16 fixed-ITER 확장 가능 |
| duration-calibrated runner | reuse_factor가 커져도 ITER가 줄어 총 FLOP가 완전히 선형 증가하지 않음 | fixed-ITER 보조 실험에서 0.146 pJ/FLOP로 method sensitivity 확인 |
| board-level NVML numerator | Tensor Core 외 scheduler, issue, register/control, clock state가 섞임 | report에서 effective microbenchmark coefficient로만 표기 |
| NCU sidecar 재사용 | 이번 targeted run 자체의 NCU를 다시 돌린 것은 아님 | 기존 factor NCU에서 RF=8/16 HMMA/spill-free가 accepted였음을 근거로 사용 |

## 산출물

| 역할 | 파일 |
|---|---|
| raw energy CSV | `results/raw/rtx3090_tensor_targeted_rf8_rf16_20260708.csv` |
| sweep matrix | `results/raw/rtx3090_tensor_targeted_rf8_rf16_20260708_matrix.csv` |
| power API audit | `results/summary/rtx3090_tensor_targeted_rf8_rf16_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_tensor_targeted_rf8_rf16_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_tensor_targeted_rf8_rf16_matched_control_report_20260708.md` |
| component reliability audit | `results/summary/rtx3090_tensor_targeted_rf8_rf16_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_tensor_targeted_rf8_rf16_instability_audit_20260708.md` |
