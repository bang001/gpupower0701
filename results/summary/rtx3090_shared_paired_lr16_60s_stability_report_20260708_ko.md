# RTX 3090 Shared LR16 paired 60초 stability 점검

작성일: 2026-07-08

이 보고서는 Shared scalar path의 `load_repeat=16` lower-side 값이 단순히 30초 실행시간 부족 때문에 나온 것인지 확인하기 위해 수행한 후속 점검이다. 결론부터 말하면 60초로 늘려도 낮은 값은 재현됐지만, treatment-control delta signal이 여전히 작아 current primary로 승격하지 않는다.

## 1. 실험 목적

기존 Shared scalar path는 targeted mixed-LR primary가 `0.152 pJ/bit`였고, paired 30초 auxiliary에서는 LR4 `0.236 pJ/bit`, LR8 `0.177 pJ/bit`, LR16 `0.064 pJ/bit`로 갈라졌다. 이 실험은 LR16 값이 낮게 나온 이유가 짧은 duration 또는 control drift인지 확인하기 위한 follow-up이다.

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 |
| treatment | `shared_scalar_load_only` |
| control | `clocked_empty` |
| sequence | control-treatment-control paired |
| W_SM | 64 KiB |
| blocks/SM | 16 |
| active SM | 82 |
| load_repeat | 16 |
| seconds | 60 s |
| treatment repeats | 6 |
| warmup | 10 s, 1 repeat |
| denominator | NCU shared bytes sidecar |

## 2. Power API와 power-state gate

Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다. RTX 3090의 `nvmlDeviceGetPowerUsage`는 1초 평균 semantics로 기록되지만, 이번 coefficient 분자는 endpoint power fallback이 아니라 NVML total-energy mJ counter의 전후 차분이다.

| gate | 결과 | 의미 |
|---|---:|---|
| Power API audit | 18/18 `final_candidate` | `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta` |
| Measurement scope | 18/18 `gpu_device_total_energy_counter` | GPU/device total energy telemetry |
| Power semantics metadata | 18/18 `one_sec_average` | RTX 3090 `GetPowerUsage` fallback semantics 기록 |
| Power-state audit | 18/18 `ok` | 평균 전력/endpoint power outlier 없음 |

따라서 이번 낮은 LR16 값의 직접 원인을 power API fallback 또는 명백한 power-state reject로 보기는 어렵다.

## 3. NCU path 검증

이번 energy run 자체는 NCU를 동시에 켠 것이 아니라, 동일 finalplan factor 조건의 NCU sidecar를 denominator/path 검증에 사용한다. Shared LR16 대표 NCU row는 다음과 같다.

| metric | 값 | 해석 |
|---|---:|---|
| shared bytes | 2.14959e12 B | denominator로 사용할 shared traffic이 충분히 큼 |
| shared accesses | 1.67936e10 | shared scalar load가 실제로 발생 |
| shared bank conflicts | 0 | bank conflict 오염 없음 |
| L1 bytes | 0 B | global L1 traffic 중심 실험이 아님 |
| L2 bytes | 1.09455e9 B | shared bytes 대비 작음 |
| DRAM bytes | 7.91497e8 B | shared bytes 대비 작음 |
| stall long scoreboard | 0.000693% | long memory stall 지배 아님 |
| stall short scoreboard | 98.8766% | short dependency/issue 관련 stall이 큼 |
| stall wait | 312.017% | warp issue/control overhead가 coefficient에 섞일 수 있음 |

NCU 관점에서는 shared path 자체는 맞다. 문제는 path 검증이 아니라, board-level treatment-control delta가 shared traffic 증가만큼 안정적으로 커지지 않는다는 점이다.

## 4. Matched-control 결과

| 항목 | 값 |
|---|---:|
| matched rows | 5/6 valid |
| invalid reason | `delta_fraction<0.005` 1개 |
| median delta_E | 232.855450946 J |
| median signal fraction | 0.0125259051152 |
| median coefficient | 0.076818689337 pJ/bit |
| bootstrap median 95% CI | 0.041951174531-0.106106546632 pJ/bit |
| confidence | low |
| reliability | `accepted_low_stability` |

LR16 60초 median `0.0768 pJ/bit`는 LR16 30초 combined `0.0635 pJ/bit`와 같은 낮은 영역에 있다. 즉 LR16 lower-side는 60초에서도 재현된다. 하지만 valid row가 5개뿐이고, 하나는 weak-signal gate에서 제외됐으며, CI 상대 폭이 크다.

## 5. 해석

이번 결과는 Shared scalar path를 다음처럼 해석해야 함을 강화한다.

| 관찰 | 판단 |
|---|---|
| LR4 paired 30초는 0.236 pJ/bit | 낮은 reuse/반복 조건에서는 fixed issue/control overhead가 더 크게 보임 |
| LR8 paired 30초 combined는 0.177 pJ/bit | targeted mixed primary 0.152 pJ/bit와 가까운 중간 evidence |
| LR16 paired 30초 combined는 0.064 pJ/bit | high load_repeat에서 lower-side가 나타남 |
| LR16 paired 60초는 0.077 pJ/bit | duration을 늘려도 lower-side는 사라지지 않지만 안정성은 낮음 |

따라서 current primary는 targeted mixed-LR `0.152 pJ/bit`를 유지한다. Shared는 단일 순수 shared-memory 회로 에너지가 아니라, `0.15-0.24 pJ/bit` 수준의 primary/high-side evidence와 LR16 lower-side caution을 함께 보고해야 한다. LR16 60초 값은 lower-bound/method-sensitivity 보조근거로만 사용한다.

## 6. 자가점검

| 질문 | 답 |
|---|---|
| power API 때문에 낮아졌나? | 현재 evidence로는 아니다. 18/18 row가 total-energy final candidate다. |
| power-state reject 때문인가? | 현재 evidence로는 아니다. 18/18 row가 ok다. |
| NCU path가 shared가 아닌가? | NCU row 기준 shared bytes가 충분하고 bank conflict가 0이며 L1 bytes가 0이다. shared scalar path 검증은 통과한다. |
| primary로 써도 되나? | 아니다. `accepted_low_stability`, 5/6 valid, signal fraction 1.25% 수준이라 auxiliary lower-side evidence로 둔다. |
| 다음 개선은? | LR16만 더 반복하기보다 LR4/LR8/LR16을 같은 C-T-C sequence에서 교차 실행하고, stall short scoreboard/wait와 coefficient를 함께 회귀해 fixed issue/control overhead를 분리해야 한다. |
