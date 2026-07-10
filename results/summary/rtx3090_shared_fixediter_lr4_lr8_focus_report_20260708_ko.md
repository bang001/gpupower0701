# RTX 3090 Shared LR4/LR8 fixed-ITER focus 점검

작성일: 2026-07-08

이 보고서는 Shared scalar path의 fixed-ITER 보조 실험에서 LR4/LR8 구간이
primary `~0.15 pJ/bit`와 정합하는지 확인하기 위한 집중 반복 실험이다.

```text
결론: LR4/LR8 fixed-ITER focus run은 10/10 valid, reliability accepted였다.
aggregate median은 0.149 pJ/bit이고, LR4는 0.179 pJ/bit, LR8은 0.142 pJ/bit다.
따라서 Shared scalar primary 0.152 pJ/bit와 interleaved/fixed-ITER aggregate
0.145-0.140 pJ/bit 범위를 강하게 지지한다.
```

## 1. 실험 구조

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 |
| treatment | `shared_scalar_load_only` |
| control | `clocked_empty` |
| sequence | control-treatment-control |
| load_repeat | 4, 8 |
| W_SM | 64 KiB |
| blocks/SM | 16 |
| active SM | 82 |
| treatment ITER | 17,000,000 |
| control | 30초 duration-calibrated |
| cycles | 5 |
| measurement commands | 30 |
| warmup commands | 6 |

이 실험은 treatment ITER를 고정하고 `load_repeat`만 바꿨다. 따라서 LR4와 LR8의
expected shared bytes는 각각 `9.1357184e13 B`, `1.82714368e14 B`로 정확히 2배
차이가 난다. 목적은 LR4/LR8 조건에서 board-level matched-control coefficient가
기존 Shared primary 범위와 일관적인지 확인하는 것이다.

## 2. Power API와 power-state gate

Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다.

| gate | 결과 | 의미 |
|---|---:|---|
| raw measurement rows | 30 | 5 cycles x 2 LR x C/T/C |
| Power API audit | 30/30 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| Measurement scope | 30/30 `gpu_device_total_energy_counter` | GPU/device total energy telemetry |
| Power semantics metadata | 30/30 `one_sec_average` | RTX 3090 fallback power sample 의미 기록 |
| Power-state audit | 30/30 `ok` | 평균 전력, endpoint power, 온도 outlier 없음 |

## 3. Raw sanity

| mode / LR | rows | median ITER | median elapsed | median net_E | median temp |
|---|---:|---:|---:|---:|---:|
| `clocked_empty` | 20 | 174,328,053 | 30.155 s | 8239.74 J | 76.5 C |
| `shared_scalar_load_only`, LR4 | 5 | 17,000,000 | 16.182 s | 4500.45 J | 76 C |
| `shared_scalar_load_only`, LR8 | 5 | 17,000,000 | 31.226 s | 8757.00 J | 78 C |

LR8은 LR4보다 bytes가 2배이고 elapsed도 약 2배에 가깝다. 이 때문에 단순 raw
energy 차이가 아니라 matched-control로 control energy rate를 보정한 뒤 pJ/bit를
해석해야 한다.

## 4. Matched-control 결과

| 항목 | 값 |
|---|---:|
| matched detail rows | 10/10 valid |
| reliability | `accepted` |
| confidence | medium-high |
| median | 1.189881894988 pJ/byte |
| median pJ/bit | 0.148735236874 pJ/bit |
| bootstrap median 95% CI | 0.124267865074-0.179085853450 pJ/bit |
| median delta_E | 161.313757801 J |
| median signal fraction | 0.024779016951 |

Factor split:

| load_repeat | valid rows | median pJ/byte | median pJ/bit | pJ/bit range | median delta_E | median signal fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 5/5 | 1.432686827600 | 0.179085853450 | 0.109387664824-0.202055916617 | 130.887646753 J | 0.029005994605 |
| 8 | 5/5 | 1.138989333890 | 0.142373666736 | 0.119688372504-0.164371019074 | 208.111575130 J | 0.023739162095 |

## 5. 판단

| 질문 | 판단 |
|---|---|
| LR4/LR8 fixed-ITER 결과가 primary와 정합하는가? | 그렇다. aggregate 0.149 pJ/bit는 current Shared primary 0.152 pJ/bit와 거의 같다. |
| LR4와 LR8이 완전히 같은 값인가? | 아니다. LR4가 LR8보다 높다. 이는 instruction mix, scheduler/issue, elapsed/control scaling 차이가 coefficient에 남는 effective microbenchmark 값이라는 뜻이다. |
| Shared primary를 바꿔야 하나? | 아니다. primary는 targeted mixed-LR 0.152 pJ/bit를 유지하고, 이번 run은 강한 auxiliary support로 추가한다. |
| caution을 제거할 수 있나? | 일부 완화된다. LR4/LR8 fixed-ITER는 안정적이지만, LR16 lower-side와 LR/factor sensitivity가 남아 pure shared-memory circuit constant라고 말할 수는 없다. |

## 6. 한 줄 결론

LR4/LR8 fixed-ITER focus run은 Shared scalar path의 NCU-validated effective coefficient가
`~0.15 pJ/bit` 근방에서 재현됨을 보여주며, current Shared primary를 교체하지 않고
보강하는 auxiliary evidence로 사용한다.
