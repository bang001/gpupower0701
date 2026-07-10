# RTX 3090 Shared LR4/LR8/LR16 interleaved 30초 stability 점검

작성일: 2026-07-08

이 보고서는 Shared scalar path의 LR별 coefficient 분산이 단순 실행 순서/thermal drift 때문인지 확인하기 위한 후속 실험이다. 결론은 다음과 같다.

```text
Shared aggregate는 0.145 pJ/bit로 current primary 0.152 pJ/bit와 정합한다.
하지만 같은 interleaved run 안에서도 LR4 > LR8 > LR16 split이 유지된다.
따라서 Shared scalar path는 단일 순수 shared-memory 회로 상수가 아니라
LR/method-sensitive effective microbenchmark coefficient로 보고해야 한다.
```

## 1. 실험 목적

기존 Shared 결과는 다음처럼 갈라졌다.

| 조건 | median | unit | 해석 |
|---|---:|---|---|
| targeted mixed-LR primary | 0.152 | pJ/bit | current primary, 29/30 valid |
| LR4 paired 30초 | 0.236 | pJ/bit | high-side auxiliary |
| LR8 paired 30초 combined | 0.177 | pJ/bit | middle auxiliary |
| LR16 paired 30초 combined | 0.064 | pJ/bit | lower-side auxiliary |
| LR16 paired 60초 | 0.077 | pJ/bit | lower-side persists, low-stability |

이 결과만으로는 LR별 실험이 서로 다른 시간대에 실행되어 run-order나 thermal drift가 영향을 줬을 가능성이 남는다. 이번 실험은 LR4, LR8, LR16을 같은 measurement cycle 안에서 교차 실행해 그 가능성을 줄인다.

## 2. 실험 구조

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 |
| runner | `scripts/run_interleaved_component_stability.py` |
| treatment | `shared_scalar_load_only` |
| control | `clocked_empty` |
| sequence | factor별 control-treatment-control |
| factor | `load_repeat` |
| factor values | 4, 8, 16 |
| factor order | rotate |
| W_SM | 64 KiB |
| blocks/SM | 16 |
| active SM | 82 |
| seconds | 30 s |
| cycles | 4 |
| warmup | 10 s, 1 cycle |
| measurement commands | 36 |
| warmup commands | 9 |

실제 measurement 순서는 다음 형태다.

```text
cycle 0: LR4 C-T-C -> LR8 C-T-C -> LR16 C-T-C
cycle 1: LR8 C-T-C -> LR16 C-T-C -> LR4 C-T-C
cycle 2: LR16 C-T-C -> LR4 C-T-C -> LR8 C-T-C
cycle 3: LR4 C-T-C -> LR8 C-T-C -> LR16 C-T-C
```

이 구조의 목적은 LR4가 항상 먼저 실행되고 LR16이 항상 늦게 실행되는 식의 순서 편향을 줄이는 것이다.

## 3. Power API와 power-state gate

Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다. RTX 3090의 `nvmlDeviceGetPowerUsage`는 `one_sec_average` semantics로 기록되지만, coefficient 분자는 endpoint power fallback이 아니라 NVML total-energy mJ counter의 전후 차분이다.

| gate | 결과 | 의미 |
|---|---:|---|
| raw measurement rows | 36 | 4 cycles x 3 LR x C/T/C |
| raw warmup rows | 9 | coefficient에는 사용하지 않음 |
| Power API audit | 36/36 `final_candidate` | `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta` |
| Measurement scope | 36/36 `gpu_device_total_energy_counter` | GPU/device total energy telemetry |
| Power semantics metadata | 36/36 `one_sec_average` | RTX 3090 `GetPowerUsage` fallback semantics 기록 |
| Power-state audit | 36/36 `ok` | 평균 전력/endpoint power outlier 없음 |

## 4. NCU path와 denominator

이번 energy run은 NCU를 동시에 켜지 않았다. NCU path validation과 denominator는 같은 factor 조건을 포함한 기존 sidecar `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`를 사용했다.

| load_repeat | shared bytes | shared bank conflicts | L1 bytes | L2 bytes | DRAM bytes | stall short scoreboard | 해석 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 4 | 5.37401e11 B | 0 | 0 B | 4.05844e8 B | 3.02841e8 B | 91.0446% | shared traffic 지배, conflict 없음 |
| 8 | 1.07480e12 B | 0 | 0 B | 3.73815e8 B | 2.73733e8 B | 96.1431% | shared traffic 지배, conflict 없음 |
| 16 | 2.14959e12 B | 0 | 0 B | 1.09455e9 B | 7.91497e8 B | 98.8766% | shared traffic 지배, conflict 없음 |

NCU 기준으로 path 자체는 shared scalar path가 맞다. LR이 커질수록 shared bytes denominator는 커지지만, board-level `delta_E`가 비례해서 커지지 않아 pJ/bit가 낮아진다.

## 5. 결과

### 5.1 Aggregate matched-control 결과

| 항목 | 값 |
|---|---:|
| matched detail rows | 12/12 valid |
| reliability | `accepted` |
| confidence | medium |
| aggregate median | 0.145060662799 pJ/bit |
| bootstrap median 95% CI | 0.076945887347-0.187609995987 pJ/bit |
| median delta_E | 215.699968446 J |
| median signal fraction | 0.024176342067 |
| NCU denominator rows | 12/12 |

Aggregate median `0.145 pJ/bit`는 targeted mixed-LR primary `0.152 pJ/bit`와 정합한다. 따라서 current primary를 바꿀 필요는 없다.

### 5.2 Factor별 결과

| load_repeat | valid/total | median | unit | median pJ/bit | delta_E median | signal fraction median | 해석 |
|---:|---:|---:|---|---:|---:|---:|---|
| 4 | 4/4 | 1.59276188001 | pJ/byte | 0.199095235002 | 293.094116966 J | 0.032267253475 | high-side, 기존 LR4 0.216-0.236보다 약간 낮지만 같은 order |
| 8 | 4/4 | 1.16048530239 | pJ/byte | 0.145060662799 | 215.699968446 J | 0.024176342067 | primary 0.152와 거의 정합 |
| 16 | 4/4 | 0.494145443960 | pJ/byte | 0.061768180495 | 94.696849526 J | 0.010506833962 | lower-side가 interleaved run에서도 유지 |

LR16은 이번에는 4/4 valid이고 power-state reject도 없었다. 따라서 LR16 lower-side를 단순한 실행 순서 artefact로 보기는 어렵다. 다만 signal fraction이 LR4/LR8보다 작으므로 lower-bound evidence로 해석한다.

## 6. 판단

| 질문 | 판단 |
|---|---|
| current Shared primary를 바꿔야 하나? | 아니다. aggregate 0.145 pJ/bit는 기존 primary 0.152 pJ/bit와 정합한다. |
| LR split은 실험 순서 때문인가? | 이번 interleaved run에서도 LR4 > LR8 > LR16이 유지되어 순서만으로 설명하기 어렵다. |
| Shared를 하나의 순수 회로 pJ/bit로 주장할 수 있나? | 아니다. 같은 shared path에서도 LR/control 정책에 따라 effective coefficient가 달라진다. |
| 보고서에서 어떻게 써야 하나? | Shared scalar path primary는 0.152 pJ/bit, interleaved support는 0.145 pJ/bit, LR4 high-side는 약 0.20-0.24 pJ/bit, LR16 lower-side는 약 0.06-0.08 pJ/bit로 구분한다. |
| 다음 개선은? | LR별 short scoreboard/wait stall, issued instruction 수, denominator 증가율, delta_E 증가율을 함께 회귀해서 fixed issue/control overhead와 byte-scaled component를 분리한다. |

## 7. 해석 한계

- 이 값은 순수 shared SRAM bitcell energy가 아니다.
- NVML GPU/device total energy에는 scheduler, issue, LSU, shared/L1 crossbar, cache controller, clock/power-state 효과가 함께 들어간다.
- NCU는 energy numerator가 아니라 path validation과 denominator를 제공한다.
- LR16 lower-side는 accepted이지만 signal fraction이 작다. 따라서 lower-bound/method-sensitivity evidence로 둔다.
