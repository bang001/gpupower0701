# RTX 3090 Shared fixed-ITER LR4/LR8/LR16 점검

작성일: 2026-07-08

이 보고서는 Shared scalar path의 `load_repeat` 민감성이 duration-calibrated 실행 구조 때문인지, 아니면 fixed-ITER 조건에서도 남는지 확인한 후속 실험이다.

```text
결론: fixed-ITER에서도 Shared aggregate는 0.140 pJ/bit로
기존 Shared primary 0.152 pJ/bit 및 interleaved aggregate 0.145 pJ/bit와 정합한다.
다만 LR16 약신호 row 1개와 factor별 spread가 남아,
Shared는 계속 accepted_with_caution effective coefficient로 보고한다.
```

## 1. 왜 다시 했나

직전 interleaved 30초 run은 LR4/LR8/LR16을 같은 run 안에서 순환했지만, 각 command가 30초 duration-calibrated 방식이었다. 이 방식에서는 `load_repeat`를 키우면 ITER가 줄어들어 총 shared bytes denominator가 거의 비슷해질 수 있다.

| run | LR4 denominator | LR8 denominator | LR16 denominator | 해석 |
|---|---:|---:|---:|---|
| duration-calibrated interleaved 30초 | 1.83e14 B | 1.85e14 B | 1.91e14 B | 시간 고정 때문에 LR별 총 bytes가 크게 벌어지지 않음 |
| fixed-ITER follow-up | 9.14e13 B | 1.83e14 B | 3.65e14 B | treatment ITER 고정으로 LR별 bytes가 약 1x/2x/4x로 벌어짐 |

따라서 fixed-ITER run은 “byte denominator가 실제로 커질 때 ΔE도 같이 커지는가?”를 확인하는 보조실험이다.

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
| treatment ITER | 17,000,000 |
| control | 30초 duration-calibrated |
| cycles | 3 |
| warmup | 1 cycle |
| measurement commands | 27 |

Control은 fixed ITER가 아니라 30초 power-rate baseline으로 실행했다. Treatment는 ITER를 고정했다. 그래서 treatment elapsed는 LR4 약 16초, LR8 약 31초, LR16 약 61초로 달라진다. Matched-control 분석에서는 control power를 treatment elapsed에 맞게 scaling했다.

## 3. Power API와 power-state gate

Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다.

| gate | 결과 | 의미 |
|---|---:|---|
| raw measurement rows | 27 | 3 cycles x 3 LR x C/T/C |
| Power API audit | 27/27 `final_candidate` | `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta` |
| Measurement scope | 27/27 `gpu_device_total_energy_counter` | GPU/device total energy telemetry |
| Power semantics metadata | 27/27 `one_sec_average` | RTX 3090 `GetPowerUsage` fallback 의미만 기록 |
| Power-state audit | 18 `ok`, 9 `caution` | caution은 treatment small-group metadata이고 coefficient eligible |

Endpoint power는 metadata일 뿐이고, pJ/bit 분자는 NVML total-energy mJ counter 차분이다.

## 4. NCU path와 denominator

이번 energy run은 NCU를 동시에 실행하지 않았다. NCU path validation과 actual denominator scale은 기존 factor sidecar `results/ncu/rtx3090_finalplan_ncu_factor_stability_20260708/ncu_cache_validation_summary.csv`를 사용했다. 이 sidecar는 같은 `W_SM=64 KiB`, `blocks/SM=16`, `load_repeat=4/8/16` 조건에서 shared scalar path가 accepted임을 기록한다.

| load_repeat | treatment ITER | expected shared bytes | NCU denominator source | 해석 |
|---:|---:|---:|---|---|
| 4 | 17,000,000 | 9.1357184e13 B | `ncu_actual_exact` scale | fixed-ITER 1x |
| 8 | 17,000,000 | 1.82714368e14 B | `ncu_actual_exact` scale | fixed-ITER 2x |
| 16 | 17,000,000 | 3.65428736e14 B | `ncu_actual_exact` scale | fixed-ITER 4x |

## 5. 결과

### 5.1 Aggregate

| 항목 | 값 |
|---|---:|
| matched detail rows | 8/9 valid |
| invalid row | LR16 1개, `delta_fraction<0.005` |
| reliability | `accepted_with_caution` |
| confidence | medium |
| aggregate median | 0.140327428192 pJ/bit |
| bootstrap median 95% CI | 0.093717469771-0.193424568906 pJ/bit |
| median delta_E | 202.567772359 J |
| median signal fraction | 0.023160394710 |

Aggregate `0.140 pJ/bit`는 targeted Shared primary `0.152 pJ/bit`와 interleaved 30초 aggregate `0.145 pJ/bit`를 지지한다.

### 5.2 Factor별 결과

| load_repeat | valid/total | median pJ/bit | delta_E median | signal fraction median | denominator median | 해석 |
|---:|---:|---:|---:|---:|---:|---|
| 4 | 3/3 | 0.153836823605 | 112.434005465 J | 0.024990660666 | 9.135817e13 B | primary 근처 |
| 8 | 3/3 | 0.193424568906 | 282.734108258 J | 0.032118934574 | 1.82716e14 B | high-side |
| 16 | 2/3 | 0.118594345628 | 346.703738410 J | 0.019957189124 | 3.654303e14 B | lower-mid, weak row 1개 |

### 5.3 간단한 byte-scaling 회귀

Valid detail row 8개에서 `delta_E = intercept + slope * bytes`로 단순 OLS를 계산하면 다음과 같다.

| fit | intercept | slope |
|---|---:|---:|
| valid detail OLS | 39.43 J | 0.1105 pJ/bit |
| valid detail through-origin | - | 0.1300 pJ/bit |
| factor median OLS | 80.45 J | 0.0978 pJ/bit |
| factor median through-origin | - | 0.1345 pJ/bit |

이 회귀는 최종 coefficient를 대체하는 모델이 아니다. 다만 fixed overhead 또는 control scaling noise가 남아 있더라도 byte-scaled slope가 `0.10-0.13 pJ/bit` 수준이고, ratio median이 `0.140 pJ/bit`라서 current Shared primary `0.152 pJ/bit`가 터무니없이 큰 값은 아니라는 보조 근거다.

## 6. 판단

| 질문 | 판단 |
|---|---|
| Shared primary를 바꿔야 하나? | 아니다. 기존 `0.152 pJ/bit`, interleaved `0.145 pJ/bit`, fixed-ITER `0.140 pJ/bit`가 같은 범위다. |
| Shared caution을 제거할 수 있나? | 아직 아니다. fixed-ITER에서도 LR16 weak row 1개와 factor spread가 남았다. |
| duration-calibrated run의 LR split은 bytes denominator artifact인가? | 일부는 duration-calibrated 구조 영향이 있다. fixed-ITER에서는 LR4/LR8/LR16 split이 줄었고 aggregate가 primary에 가까워졌다. |
| 순수 shared SRAM pJ/bit라고 말할 수 있나? | 아니다. NVML board-level delta에는 LSU, scheduler, issue, shared/L1 crossbar, stall, control scaling 영향이 들어간다. |

## 7. 다음 개선

| 우선순위 | 내용 | 이유 |
|---:|---|---|
| 1 | fixed-ITER Shared를 5 cycles 이상으로 반복 | 현재 8/9 valid라 trend는 보이지만 LR16 weak row가 남음 |
| 2 | NCU가 가능한 환경에서 같은 fixed-ITER 조건을 profile | 현재는 기존 sidecar scale을 사용했으므로 fixed-ITER 자체의 stall/instruction counter는 없음 |
| 3 | `delta_E = fixed overhead + bytes slope + stall proxy` 회귀 | Shared effective coefficient의 fixed/control 성분과 byte-scaled 성분을 분리하기 위함 |

## 8. 한 줄 결론

Fixed-ITER LR sweep은 Shared scalar path의 current primary `0.152 pJ/bit`가 합리적인 범위임을 강화하지만, 순수 shared-memory 회로 에너지가 아니라 NCU로 path가 검증된 board-level effective coefficient라는 caution은 유지해야 한다.
