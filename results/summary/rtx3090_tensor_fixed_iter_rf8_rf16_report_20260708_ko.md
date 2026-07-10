# RTX 3090 Tensor Fixed-ITER RF8/RF16 Auxiliary Report

작성일: 2026-07-08

## 목적

이 문서는 Tensor targeted RF=8/16 결과가 duration-calibrated runner 정책에
의존하는지 확인하기 위한 fixed-ITER 보조실험이다. 이전 targeted run은 RF=8/16에서
20초 목표시간을 맞추기 위해 각 command가 자체적으로 ITER를 calibration했다. 이번
실험은 `ITER=8000000`을 고정하고 RF=8/16 treatment-control 차분을 다시 측정했다.

이 실험도 순수 Tensor Core 회로 에너지 측정이 아니다. Power API 해석은
`docs/platforms/power_measurement_api_matrix_ko.md` 기준을 따르며, 최종 분자는
NVML total energy counter 차분만 사용한다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment | `reg_mma` | FP16 WMMA/HMMA 실행 |
| control | `reg_operand_only` | HMMA 없이 register fragment/operand loop 유지 |
| W_SM | 2048 | KiB/SM |
| blocks/SM | 16 | resident blocks per SM |
| active_SM | 82 | SM |
| reuse_factor | 8, 16 | count |
| ITER | 8000000 | fixed iteration count |
| seconds | 10 | s, idle baseline 측정 길이 |
| repeats | 5 | count per mode/reuse |
| raw rows | 20 | 2 modes x 2 reuse factors x 5 repeats |
| matched-control rows | 10 | treatment rows matched to nearest control |

## Power API / 상태 Gate

| gate | 결과 | 근거 |
|---|---:|---|
| Power API audit | 20/20 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| fallback power integral | 0 row | `GetPowerUsage` endpoint 적분 미사용 |
| RTX 3090 power semantics metadata | 20/20 `one_sec_average` | profile metadata 일치 |
| Power-state audit | 20/20 `ok` | 평균 전력/endpoint power outlier 없음 |
| SMID check | 20/20 ok | active SM/block 배치 정상 |
| matched-control valid | 10/10 | negative/weak-signal row 없음 |

## 결과

| view | rows | median | min | max | unit | confidence/status |
|---|---:|---:|---:|---:|---|---|
| RF=8/16 combined | 10 | 0.145635 | 0.010359 | 0.263018 | pJ/FLOP | `medium-high`, reliability `accepted` |
| RF=8 only | 5 | 0.161342 | 0.150691 | 0.263018 | pJ/FLOP | stable positive rows |
| RF=16 only | 5 | 0.108536 | 0.010359 | 0.140579 | pJ/FLOP | positive rows, one marginal low-signal row |

| 항목 | 값 |
|---|---:|
| bootstrap median 95% CI | 0.108536 - 0.201568 pJ/FLOP |
| combined stdev | 0.073525 pJ/FLOP |
| combined relative IQR | 0.325 |
| combined CV | 0.505 |
| delta_E median | 136.902 J |
| delta signal fraction median | 0.0862 |

## Duration-Targeted 결과와 비교

| 실험 | policy | rows | median | min | max | unit | verdict |
|---|---|---:|---:|---:|---:|---|---|
| Tensor targeted | duration-calibrated, RF=8/16, 20 s, 6 repeats | 12 | 0.106658 | 0.032230 | 0.174529 | pJ/FLOP | `accepted` |
| Tensor fixed-ITER auxiliary | fixed `ITER=8000000`, RF=8/16, 5 repeats | 10 | 0.145635 | 0.010359 | 0.263018 | pJ/FLOP | `accepted` |

판단:

- fixed-ITER도 power API, power-state, matched-control gate를 통과했다.
- median은 duration-targeted보다 높아서 Tensor coefficient가 measurement policy에 민감함을 보여준다.
- 두 실험이 같은 order에 있고 confidence가 모두 medium-high이지만, RF=16
  duration-scaling이 0.077 pJ/FLOP로 통과했다. 따라서 현재 RTX 3090 Tensor 결과는
  단일 물리 상수가 아니라 RF-dependent workload-effective coefficient로 보고하는
  것이 더 정직하다.
- RF=8 duration-scaling 보조실험도 0.143 pJ/FLOP median으로 통과했으므로,
  current reporting CSV에는 duration-targeted 0.107을 blended RF=8/16 candidate로,
  fixed-ITER 0.146, RF8 duration-scaling 0.143, RF16 duration-scaling 0.077을
  accepted auxiliary check로 함께 둔다.

## 자가비판

| 한계 | 영향 | 다음 보완 |
|---|---|---|
| RF=8/16만 fixed-ITER 확인 | RF=4 이하 broad sweep 분산을 완전히 설명하지 못함 | RF=4/8/16 fixed-ITER 확장 가능 |
| `ITER=8000000` 단일 값 | RF=8과 RF=16 elapsed가 달라 thermal/control 상태가 완전히 같지 않음 | fixed elapsed와 fixed ITER를 모두 만족하는 paired runner 설계 |
| RF=16 row 하나가 낮은 계수 | gate는 통과했지만 method variance를 키움 | 더 긴 반복 또는 robust median/trimmed analysis 추가 |
| NCU sidecar 재사용 | 이번 fixed-ITER run 자체의 NCU를 다시 수집한 것은 아님 | RF=8/16 fixed-ITER NCU sidecar를 별도로 수집 가능 |

## 산출물

| 역할 | 파일 |
|---|---|
| raw energy CSV | `results/raw/rtx3090_tensor_fixed_iter_rf8_rf16_20260708.csv` |
| sweep matrix | `results/raw/rtx3090_tensor_fixed_iter_rf8_rf16_20260708_matrix.csv` |
| power API audit | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_power_state_audit_20260708.md` |
| matched-control report | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_matched_control_report_20260708.md` |
| component reliability audit | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_component_reliability_audit_20260708.md` |
| instability audit | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_instability_audit_20260708.md` |
