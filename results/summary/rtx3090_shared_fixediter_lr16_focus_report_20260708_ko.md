# RTX 3090 Shared LR16 fixed-ITER focus 점검

작성일: 2026-07-08

이 보고서는 직전 fixed-ITER LR4/LR8/LR16 실험에서 LR16 row 1개가 `delta_fraction<0.005`로 invalid 처리된 원인을 확인하기 위한 집중 반복 실험이다.

```text
결론: LR16 fixed-ITER focus rerun은 6/6 valid, reliability accepted였다.
따라서 직전 fixed-ITER LR16 weak row는 지속적인 path failure가 아니라
row-level weak-signal/control scaling noise로 보는 것이 타당하다.
LR16 fixed-ITER lower-mid evidence는 0.117 pJ/bit로 보고한다.
```

## 1. 실험 구조

| 항목 | 값 |
|---|---:|
| GPU | RTX 3090 |
| treatment | `shared_scalar_load_only` |
| control | `clocked_empty` |
| sequence | control-treatment-control |
| load_repeat | 16 |
| W_SM | 64 KiB |
| blocks/SM | 16 |
| active SM | 82 |
| treatment ITER | 17,000,000 |
| control | 30초 duration-calibrated |
| cycles | 6 |
| measurement commands | 18 |
| warmup commands | 3 |

이 실험은 LR16만 반복했다. 목적은 LR16 lower-side 자체를 primary로 승격하는 것이 아니라, fixed-ITER aggregate에서 보인 invalid row가 반복되는지 확인하는 것이다.

## 2. Power API와 power-state gate

Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다.

| gate | 결과 | 의미 |
|---|---:|---|
| raw measurement rows | 18 | 6 cycles x C/T/C |
| Power API audit | 18/18 `final_candidate` | `nvml_total_energy`, `total_energy_mj_delta` |
| Measurement scope | 18/18 `gpu_device_total_energy_counter` | GPU/device total energy telemetry |
| Power semantics metadata | 18/18 `one_sec_average` | RTX 3090 fallback power sample 의미 기록 |
| Power-state audit | 18/18 `ok` | power-state outlier 없음 |

## 3. Raw sanity

| mode | rows | median ITER | median elapsed | median net_E | median temp |
|---|---:|---:|---:|---:|---:|
| `clocked_empty` | 12 | 79,461,379.5 | 30.412 s | 8405.54 J | 80 C |
| `shared_scalar_load_only` | 6 | 17,000,000 | 61.400 s | 17319.32 J | 79 C |

Treatment ITER와 expected shared bytes는 모든 LR16 treatment row에서 동일했다.

## 4. Matched-control 결과

| 항목 | 값 |
|---|---:|
| matched detail rows | 6/6 valid |
| reliability | `accepted` |
| confidence | medium |
| median | 0.935514631397 pJ/byte |
| median pJ/bit | 0.116939328925 pJ/bit |
| bootstrap median 95% CI | 0.108716672776-0.122303499231 pJ/bit |
| median delta_E | 341.865392406 J |
| median signal fraction | 0.019739026375 |
| denominator | 3.654303e14 B |

Detail row의 pJ/bit 범위는 `0.1078-0.1232 pJ/bit`였고, 모든 row가 `delta_fraction >= 0.005` gate를 통과했다.

## 5. 판단

| 질문 | 판단 |
|---|---|
| 직전 fixed-ITER LR16 weak row가 반복됐나? | 아니다. focus rerun은 6/6 valid였다. |
| LR16 fixed-ITER 값을 어떻게 봐야 하나? | lower-mid auxiliary evidence로 `0.117 pJ/bit`를 사용한다. |
| Shared primary를 바꿔야 하나? | 아니다. primary는 targeted mixed-LR `0.152 pJ/bit`, interleaved aggregate `0.145 pJ/bit`, fixed-ITER aggregate `0.140 pJ/bit`와 함께 보고한다. |
| caution을 제거할 수 있나? | 일부 완화된다. LR16 invalid row는 지속적이지 않지만, LR/factor/method sensitivity 자체는 남아 있으므로 Shared는 pure circuit constant가 아니다. |

## 6. 한 줄 결론

LR16 fixed-ITER focus rerun은 Shared path의 NCU-validated effective coefficient가 `0.117 pJ/bit` lower-mid 범위에 안정적으로 존재함을 보여주며, 이전 weak row를 path failure가 아닌 측정 노이즈로 재분류한다.
