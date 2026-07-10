# RTX 3090 Shared Duration-Scaling Check

작성일: 2026-07-08

## 목적

Shared scalar path의 current reporting 값은 targeted stability rerun의
`0.152 pJ/bit`다. 다만 targeted rerun에는 invalid detail row 1개와 control
temperature caution이 남아 있었다. 이 문서는 Shared path만 Global L1과 분리하고,
`load_repeat=4`를 고정한 채 duration을 10/20/30초로 늘려 Shared coefficient가
duration scaling에서도 안정적인지 확인한 결과다.

이 실험도 power 측정 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를
따른다. RTX 3090의 `GetPowerUsage`는 1초 평균 fallback이지만, 이번 결과의
energy numerator는 fallback이 아니라 `nvmlDeviceGetTotalEnergyConsumption` mJ
counter 차분이다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 / GA102 | target profile `rtx3090` |
| treatment mode | `shared_scalar_load_only` | shared-memory scalar load path |
| control mode | `clocked_empty` | clocked empty control |
| W_SM | 64 | KiB/SM |
| blocks/SM | 16 | blocks/SM |
| active SM | 82 | SM |
| load_repeat | 4 | count |
| seconds sweep | 10, 20, 30 | s |
| repeats | 5 | count per duration |
| raw rows | 30 | 2 modes x 3 durations x 5 repeats |
| matched-control rows | 15 | treatment rows only |

## Gate 결과

| gate | 결과 | 해석 |
|---|---:|---|
| Power API audit | 30/30 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| Power-state audit | 28/30 `ok`, 2/30 `caution` | reject 없음. 10초 초반 cold/temperature outlier |
| NCU path | accepted | 기존 factor sidecar LR=4 shared path 사용 |
| matched-control valid | 15/15 | negative/weak-signal row 없음 |
| reliability | `accepted` | core reliability gate 통과 |
| instability audit | `stable_detail_rows` | 추가 weak-signal follow-up은 필요 없음 |

Power-state caution 2개는 모두 10초 초반 row였다. coefficient 계산 자체를 reject할
정도는 아니지만, duration scaling의 ratio가 짧은 duration에서 더 커지는 현상과
같이 해석해야 한다.

## Ratio 기반 결과

| duration bucket | valid rows | median | min | max | 단위 |
|---:|---:|---:|---:|---:|---|
| 10 s | 5 | 0.335 | 0.165 | 0.461 | pJ/bit |
| 20 s | 5 | 0.198 | 0.175 | 0.289 | pJ/bit |
| 30 s | 5 | 0.177 | 0.158 | 0.242 | pJ/bit |
| 전체 | 15 | 0.198 | 0.158 | 0.461 | pJ/bit |

전체 ratio median은 `0.198 pJ/bit`, bootstrap median 95% CI는
`0.175-0.260 pJ/bit`다. 기존 targeted Shared median `0.152 pJ/bit`보다 높지만,
targeted CI 상한 `0.204 pJ/bit`와 일부 겹친다.

## Slope 기반 확인

duration을 늘리면 denominator와 delta_E가 함께 커진다. 이때 단순 ratio는
고정 오버헤드가 있으면 커질 수 있으므로, `delta_E = intercept + slope * bytes`
형태도 같이 확인했다.

| 방식 | slope | 단위 | 해석 |
|---|---:|---|---|
| OLS with intercept | 0.122 | pJ/bit | 고정 오버헤드가 있다고 보고 per-byte 항만 추정 |
| Theil-Sen pairwise slope | 0.108 | pJ/bit | robust slope |
| bucket-median Theil-Sen | 0.101 | pJ/bit | duration bucket median끼리의 robust slope |
| through-origin slope | 0.205 | pJ/bit | intercept를 0으로 강제. ratio median과 유사 |

즉 Shared scalar path에는 per-byte 성분 외에 fixed/control/temperature overhead가
섞여 있다. 따라서 `0.198 pJ/bit`를 순수 shared access energy로 쓰면 안 된다.

## 결론

이 실험은 Shared path가 실패했다는 뜻이 아니라, Shared coefficient가 계산 방식에
민감하다는 증거다.

| 판단 | 내용 |
|---|---|
| path validity | NCU shared path accepted |
| power numerator | total energy counter 기반 |
| row stability | 15/15 valid, reliability accepted |
| ratio estimate | 0.198 pJ/bit |
| slope estimate | 0.10-0.12 pJ/bit |
| current reporting | targeted median 0.152 pJ/bit 유지, duration-scaling은 sensitivity evidence로 병기 |

보고서에는 Shared scalar를 단일 회로 상수처럼 쓰지 말고, current RTX 3090
microbenchmark에서 `0.15-0.20 pJ/bit` 수준의 effective coefficient로 설명하는 것이
더 솔직하다. 단 current CSV에는 기존 broad result와 targeted rerun이 정합했던
`0.152 pJ/bit`를 primary로 유지한다.
