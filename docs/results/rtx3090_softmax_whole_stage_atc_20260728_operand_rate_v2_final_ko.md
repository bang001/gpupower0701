# RTX 3090 Whole-Softmax stage Operand-rate ATC 보고서

## 기술 요약

**Base 검토 결론: active control은 probe OFF/ON의 signed power contrast를 위한 구조적 대조군으로는 적절하지만, stage의 물리적 에너지 원가를 추정하는 base로는 충분하지 않다.** 특히 treatment와 control의 runtime이 달라지면 `(P_T−P_C*)/treatment rate`는 실제 두 role의 energy 차가 아니다. 따라서 acquisition contract에서 primary로 명명한 Operand-rate ATC는 보존하되, 에너지 질문에서는 **secondary power-behavior diagnostic**으로 재분류한다. Fixed-work `ΔE_hat/N` 또는 complete-Softmax/stage-replacement endpoint를 energy-oriented primary로 사용해야 한다. Fail-closed 분석은 162개 measured role, 27개 fresh-session cell, 54개 bracket effect와 9개 stage×implementation summary를 모두 통과시켰다.

9개 mean은 -700.436–+47.067 ΔpJ/logical output 범위였다. 3/3 session이 양수인 cell은 1/9, 0/3인 cell은 4/9였다. descriptive t95가 0보다 큰 cell은 1/9, 0보다 작은 cell은 4/9, 0을 포함한 cell은 4/9였다. 최저 mean은 Max + sum reduction · scalar FP16 -700.436, 최고 mean은 Normalization · scalar FP16 +47.067였다. 이 최저/최고는 이 단일 좌표의 기술적 비교이며 stage 원가의 보편적 순위가 아니다. 특히 음수는 treatment가 control보다 오래 실행되면서 평균 board power가 낮아진 signed contrast이며, 추가 연산이 음의 물리 에너지를 소비하거나 Softmax 에너지를 절감했다는 뜻이 아니다.

양수라는 부호 자체는 base 타당성 검사가 아니다. Exp의 3/3 cell은 descriptive t95가 0을 포함했고, normalization도 packed FP16x2에서는 -52.910 pJ/output으로 음수였다. Reduction의 큰 음수가 power와 runtime을 분리해서 보아야 한다는 설계 한계를 가장 선명하게 드러냈다.

## Operand-rate ATC를 stage의 물리적 에너지 원가와 구분하는 법

### 비교 대상은 idle(유휴 상태)이 아니라 같은 Softmax를 실행하는 active control(활성 대조군)이다

- **Active control(활성 대조군, C):** GPU가 쉬는 idle 상태가 아니다. Treatment와 같은 kernel symbol, 입력·출력, grid/CTA geometry, ITER 및 resource 계약으로 complete Softmax를 반복 실행하되, 측정 대상 added-stage pass만 runtime flag로 끈 실행이다.
- **Treatment(처리군, T):** 동일한 complete-Softmax kernel을 실행하면서, 선택된 stage의 계산 지점에서 main output과 분리된 redundant exp, reduction(max+sum) 또는 normalization(reciprocal+multiply) probe path를 runtime flag로 켠 실행이다. Primary output path는 그대로 유지되며 control과 treatment의 main Softmax output은 bit-identical gate를 통과해야 한다.

### 그림으로 보는 ATC: power는 높이, energy는 면적이다

아래 생성형 이미지는 계산 절차를 쉽게 설명하기 위한 **개념도**이며 측정 그래프가 아니다. 세로 높이는 평균 power, 가로 폭은 runtime, 사각형의 면적은 energy를 뜻한다. Reduction처럼 treatment가 더 낮은 높이로 더 오래 실행되면 `P_T−P_C*`는 음수여도 same-work energy contrast는 양수일 수 있다. 초록 상자의 A와 B는 **서로 다른 두 후속 arm**이며 두 결과를 더하지 않는다. 정확한 식과 수치는 이 문서의 SHA-bound CSV/JSON이 기준이다.

![Operand-rate ATC 실험 방법 개념도](https://raw.githubusercontent.com/bang001/gpupower0701/e1ba9ea51b1fbe27fb2ada6f39c293b320a32a34/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_atc_method_explainer.png)

[PNG 파일](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_atc_method_explainer.png) · [생성·검수 metadata](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/atc_method_explainer_metadata.json)

> 이미지 역할: `explanatory_not_measurement_evidence`. 측정 데이터 도표가 아닌 개념 설명용 그림이며, 인접한 식과 SHA-bound CSV/JSON을 정량 근거로 사용한다.

따라서 C와 T 모두 GPU가 실제 작업을 수행한다. 이 비교가 묻는 질문은 “Softmax 한 번의 절대 에너지는 얼마인가?”가 아니라 다음과 같다.

> 이미 complete Softmax를 수행 중인 active control과 비교했을 때, added-stage pass를 켠 treatment의 board power(보드 전체 전력)가 얼마나 달라졌고, 그 차이를 treatment의 logical-output rate(논리 출력 처리율)로 나누면 scalar output 하나당 얼마인가?

### 계산식은 active-power 차이를 treatment 처리율로 환산한다

C-T-C bracket의 단순화된 표기는 다음과 같다.

```text
ΔATC = (P_T - P_C*) / R_T × 10^12  [pJ/logical output]
R_T  = N_T / t_T
N_T  = 41 CTA × 2 rows/CTA × observed ITER × 1024 logical outputs/row
```

- `P_T`는 qualified NVML total-energy trace에서 얻은 treatment의 board-power estimate다.
- `P_C*`는 treatment의 시간 위치에 맞추어 두 outer active-control power를 보간한 값이다. 별표는 단일 control 측정값이 아니라 시간보간 기준값임을 뜻한다.
- `R_T`는 treatment가 초당 생성한 logical Softmax output 수다. 여기서 logical output은 scalar element 하나이며, packed FP16x2는 두 lane을 각각 세므로 별도의 `/2` 보정이 없다.
- T-C-T bracket에서는 두 outer treatment의 power와 output rate를 가운데 control 시점으로 보간한다. 한 fresh session의 effect는 C-T-C와 T-C-T effect의 평균이다.

`W = J/s`이므로 `W ÷ (logical output/s) = J/logical output`이고, `10^12`를 곱해 pJ/logical output으로 표시한다. 그러나 단위가 에너지/원소라고 해서 실제 role energy를 직접 뺀 값은 아니다. C-T-C 식은 다음처럼 쓸 수 있다.

```text
(P_T - P_C*) / (N_T/t_T) = (P_T - P_C*) × t_T / N_T
```

즉 관측된 active-power 차이가 treatment 실행시간 동안 유지된다고 놓고 treatment 처리량에 배분한 값이다. 실제 control의 `P_C × t_C`를 treatment의 `P_T × t_T`에서 빼는 계산이 아니므로 **power projection**이라고 부른다. `signed`는 절댓값을 취하지 않고 `P_T−P_C*`의 방향을 그대로 보존한다는 뜻이다.

두 식을 나란히 쓰면 차이가 더 분명하다.

```text
현재 Operand-rate ATC = P_T×t_T/N − P_C*×t_T/N
C-T-C fixed-work = (E_hat_T − E_hat_C*)/N
T-C-T fixed-work = (E_hat_T* − E_hat_C)/N
E_hat_role = P_hat_trace,role × t_CUDA,role
```

현재 ATC의 control 항은 outer-control 추정 role energy `E_hat_C*`가 아니라 보간 power `P_C*`에 treatment 시간 `t_T`를 곱한 투영값이다. 반면 C-T-C의 `E_hat_C*`는 두 outer control의 추정 role energy를 treatment 시점으로 보간하고, T-C-T의 `E_hat_T*`는 두 outer treatment의 추정 role energy를 control 시점으로 보간한다. 여기서 `P_hat_trace`는 qualified cumulative-energy trace의 guarded Theil–Sen slope이며 `t_CUDA`는 CUDA elapsed다. 직접 joule endpoint를 적분한 값이라고 과장하지 않는다. `t_T≈t_C`일 때에는 ATC와 fixed-work 값이 우연히 비슷해질 수 있지만, runtime이 갈라지면 서로 다른 질문에 답한다.

### Base 검토 결론: 구조 비교에는 적절하지만 물리 에너지 base로는 불충분하다

| 검토 항목 | 결과 | 의미 |
|---|---|---|
| 같은 kernel symbol, grid/CTA, ITER, I/O, resource와 main output | 통과 | probe OFF/ON의 구조적 counterfactual은 성립한다. |
| C-T-C와 T-C-T의 시간보간 | 통과 | 선형 drift와 중간 위치 편향을 완화하지만 서로 다른 runtime·throughput을 같게 만들지는 않는다. |
| Static/NCU instruction delta | 통과 | treatment의 added path가 실제 실행됐다는 근거이며 power 또는 energy 측정은 아니다. |
| Reduction의 사후 elapsed 근사 진단 (`0.98–1.02`) | **근사 범위 밖** | FP32 `1.390×`, scalar FP16 `1.726×`, packed FP16x2 `1.442×`로 `t_T≈t_C`가 세 구현에서 성립하지 않는다. 이 범위는 완료 v2의 원래 fail-closed gate가 아니다. |

즉 baseline 실행 자체가 잘못 구성된 것은 아니다. **문제는 그 baseline과 추정량을 stage energy라는 질문에 사용한 estimand mismatch**다. Exp와 FP32/scalar normalization은 elapsed 비가 거의 1이어서 ATC와 same-ITER energy contrast가 비슷하게 보였을 뿐이며, 양수 부호가 이 mismatch를 검증하거나 해소한 것은 아니다.

`0.98–1.02`는 2026-07-29 감사에서 ATC와 fixed-work contrast가 가까워질 조건을 설명하기 위해 추가한 **사후 민감도 기준**이다. 완료 v2의 원래 quality gate가 아니며, fixed-work energy contrast의 유효 조건도 아니다. 후속 equal-duration arm에서만 사전 gate로 사용할 것을 제안한다.

### 왜 added stage의 물리적 에너지 원가가 아닌가

Active-control 차분은 두 실행의 공통 complete-Softmax board-power 성분을 상당 부분 상쇄하여 added pass에 민감한 contrast를 만들려는 설계다. 이 상쇄가 공통 작업의 물리적 에너지를 완전히 제거했음을 보장하지는 않는다. 또한 added stage에 속한 회로나 명령만 별도 전력계로 계측한 것이 아니므로 다음 효과가 분자에 함께 결합될 수 있다.

- NVML 수치는 GPU core만이 아니라 장치 전체의 board-level power다.
- Added pass는 명령 스케줄, memory traffic, synchronization, resource contention, clock/power state와 전체 runtime을 함께 바꿀 수 있다.
- 원래 complete Softmax의 해당 stage는 그대로 남아 있고, 선택된 stage 계산 지점에서 main output과 분리된 redundant probe가 활성화된다. 원래 stage를 제거하거나 다른 precision stage로 교체한 endpoint 비교가 아니다.
- 공통 작업의 상쇄는 active-control 비교가 confounding을 줄이는 방식이지, complete Softmax를 서로 독립적인 stage별 joule 항으로 정확히 분해했다는 보장이 아니다.

따라서 이 수치는 **이 GPU·이 geometry·이 처리율에서 added pass를 켰을 때의 board-power contrast**로는 읽을 수 있지만, 다른 실행에도 그대로 적용되는 opcode 에너지나 stage 고유의 보편적 pJ/element 계수로 읽을 수 없다.

### 부호는 물리적 stage energy의 부호가 아니라 active-power contrast의 부호다

| ATC 결과 | 말할 수 있는 것 | 말하면 안 되는 것 |
|---|---|---|
| 양수 | Treatment의 active board power가 대응 control보다 높았고, 이를 treatment rate로 환산한 값이 양수다. | Added stage가 그만큼의 독립적인 물리 에너지를 소비했다. |
| 음수 | Treatment의 active board power가 대응 control보다 낮았다. | GPU가 에너지를 만들었다, added stage가 음의 에너지를 소비했다, 또는 complete Softmax 에너지가 절감됐다. |
| 0에 가깝거나 t95가 0을 포함 | 관측된 active-power contrast가 작거나 fresh-session 방향이 불확실하다. | 해당 stage의 물리적 에너지 비용이 0이다. |

Treatment는 평균 board power가 더 낮더라도 더 오래 실행될 수 있다. 그러면 signed Operand-rate ATC는 음수지만 같은 수의 output을 처리하는 총 board energy는 더 클 수 있다. 이 때문에 음수 값을 ‘에너지 절감량’으로 바꾸어 읽을 수 없다.

### 같은 pJ/output 표기라도 추정 대상(estimand)이 다르며 stage끼리 합산할 수 없다

| 지표 | 계산의 핵심 | 실행시간을 다루는 방식 | 대답하는 질문 |
|---|---|---|---|
| **Operand-rate ATC (power diagnostic)** | `(P_T−P_C*)/(N_T/t_T)` | Treatment 처리율로 active-power 차이를 투영 | Active control 대비 power contrast는 treatment output 하나당 얼마인가? |
| **Idle-subtracted complete-Softmax energy** | 예: `(E_softmax−P_idle×t_softmax)/N` | Complete workload의 실제 실행시간과 idle baseline을 사용 | Softmax 전체가 idle 위에서 소비한 energy/output은 얼마인가? **이번 added-pass acquisition에서 직접 측정한 값이 아니며 ATC로 복원할 수 없다.** |
| **Same-ITER gross ΔE/N diagnostic** | C-T-C `(E_hat_T−E_hat_C*)/N`; T-C-T `(E_hat_T*−E_hat_C)/N`; `E_hat_role=P_hat_trace×t_CUDA` | C와 T 각각의 CUDA runtime을 추정 role energy에 포함 | 같은 ITER에서 treatment와 active control의 gross board-energy 차이는 얼마인가? |

표의 `E_hat_C*`는 두 outer control 각각의 `E_hat_role=P_hat_trace×t_CUDA`를 treatment midpoint에 보간한 추정 energy이며, T-C-T에서는 같은 방식의 `E_hat_T*`를 사용한다. Same-ITER 진단도 idle을 빼지 않으며 treatment의 늘어난 실행시간 동안 반복된 complete-Softmax 공통 작업까지 포함한다. 에너지 질문에는 ATC보다 적절한 intervention contrast지만, 그 자체도 순수 added-stage 원가로 재명명하지 않는다. 실제 scalar FP16 reduction은 ATC가 -700.436 pJ/output이지만 treatment/control elapsed 비가 1.726×이고, same-ITER gross 진단은 +3,530.892 pJ/output이었다. 같은 단위에서 반대 부호가 나온 것은 계산 오류가 아니라 두 지표가 서로 다른 질문에 답하기 때문이다.

Stage별 ATC도 각각 별도의 control/treatment 실행, power, runtime 및 처리율에서 얻은 contrast라 서로 더할 수 없다. 예를 들어 FP32의 Exp +34.978, Reduction -600.909, Normalization +34.630을 산술적으로 더한 -531.301 pJ/output은 complete-Softmax 절대 에너지, 세 stage의 물리 원가 합, 실제 fused treatment의 에너지 중 어느 것도 나타내지 않는다.

## 3×3 결과와 fresh-session 편차

아래 도표에서 채운 marker는 fresh 3-session mean과 descriptive t95이고, 빈 marker 1–3은 독립 CUDA process session이다. t95는 n=3의 기술적 불확실성 표시이며 다중비교 보정된 추론 구간이 아니다.
본문 그림은 위치가 바뀌어도 렌더링되도록 immutable commit의 HTTPS PNG를 사용한다. 각 그림 아래의 저장소 상대경로 PNG와 SVG는 offline fallback 및 원본 검증용이다.

![3×3 mean, t95, and raw sessions](https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_mean_t95_sessions.png)

[PNG 파일](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_mean_t95_sessions.png) · [SVG 원본](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_mean_t95_sessions.svg)

- **Exp:** FP32 +34.978 (t95 includes 0, positive 1/3); scalar FP16 +16.335 (t95 includes 0, positive 2/3); packed FP16x2 +12.169 (t95 includes 0, positive 2/3).
- **Max + sum reduction:** FP32 -600.909 (t95 < 0, positive 0/3); scalar FP16 -700.436 (t95 < 0, positive 0/3); packed FP16x2 -473.433 (t95 < 0, positive 0/3).
- **Normalization:** FP32 +34.630 (t95 includes 0, positive 1/3); scalar FP16 +47.067 (t95 > 0, positive 3/3); packed FP16x2 -52.910 (t95 < 0, positive 0/3).

| Added stage | Implementation | mean ΔpJ/output | SD | descriptive t95 | positive sessions | mean \|C-T-C − T-C-T\| |
|---|---|---:|---:|---:|---:|---:|
| Exp | FP32 | +34.978 | 127.818 | [-282.539, +352.494] | 1/3 | 120.400 |
| Exp | scalar FP16 | +16.335 | 34.846 | [-70.228, +102.897] | 2/3 | 77.541 |
| Exp | packed FP16x2 | +12.169 | 32.096 | [-67.561, +91.900] | 2/3 | 38.364 |
| Max + sum reduction | FP32 | -600.909 | 103.083 | [-856.981, -344.836] | 0/3 | 102.614 |
| Max + sum reduction | scalar FP16 | -700.436 | 116.748 | [-990.453, -410.419] | 0/3 | 265.876 |
| Max + sum reduction | packed FP16x2 | -473.433 | 51.194 | [-600.606, -346.260] | 0/3 | 24.609 |
| Normalization | FP32 | +34.630 | 98.027 | [-208.883, +278.143] | 1/3 | 55.241 |
| Normalization | scalar FP16 | +47.067 | 15.392 | [+8.832, +85.302] | 3/3 | 75.630 |
| Normalization | packed FP16x2 | -52.910 | 13.889 | [-87.414, -18.407] | 0/3 | 63.333 |

## 음수 ATC와 same-ITER gross board-energy 진단은 서로 다른 질문이다

Reduction의 18/18 bracket에서 `P_T−P_C`가 음수였지만, 같은 ITER의 role energy를 비교한 diagnostic은 18/18 bracket에서 양수였다. 아래 `same-ITER gross ΔE/N`은 각 role의 guarded Theil–Sen trace-power estimate `P_hat_trace`에 CUDA elapsed를 곱해 `E_hat_role`을 만든 뒤, orientation별 midpoint 규칙으로 보간해 계산한다. Idle은 사용하지 않는다.

| Implementation | historical mean ATC ΔpJ/output | mean ΔP | mean T elapsed | mean C elapsed | mean T/C | same-ITER gross ΔE/N | diagnostic descriptive t95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FP32 | -600.909 | -16.152 W | 13.386 s | 9.627 s | 1.390× | +1,826.390 | [+1,747.040, +1,905.740] |
| scalar FP16 | -700.436 | -14.216 W | 13.344 s | 7.731 s | 1.726× | +3,530.892 | [+3,376.873, +3,684.912] |
| packed FP16x2 | -473.433 | -16.833 W | 13.376 s | 9.273 s | 1.442× | +1,423.060 | [+1,316.610, +1,529.511] |

이 진단은 treatment가 더 오래 실행된다는 사실을 회계에 포함하므로 reduction ATC 음수가 물리적 에너지 절감을 뜻하지 않음을 보여준다. 다만 complete Softmax 공통 작업의 추가 runtime까지 포함한 gross board-energy contrast이므로 순수 reduction stage 원가로 재명명해서도 안 된다. 두 값은 서로 다른 estimand이므로 합산하지 않는다.

## stage×implementation 행렬은 부호와 크기만 요약한다

Heatmap은 각 cell의 mean과 3개 session 중 양수 개수를 직접 표시한다. 서로 다른 added stage의 값은 완전한 Softmax의 구성비로 더할 수 없으며, packed FP16x2도 scalar logical output element 기준이므로 2로 나누지 않는다.

![Stage by policy heatmap](https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_stage_policy_heatmap.png)

[PNG 파일](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_stage_policy_heatmap.png) · [SVG 원본](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_stage_policy_heatmap.svg)

## C-T-C와 T-C-T는 중간 위치 편향을 서로 반대 방향에서 진단한다

27개 fresh-session cell 중 두 bracket의 부호가 일치한 것은 19/27개였다. orientation 간 절대 차이의 범위는 1.814–731.484 pJ/output이었다. 대각선에서 멀수록 bracket 방향에 민감했음을 뜻하지만, 그 차이를 별도 causal order effect로 해석하지 않는다.

![C-T-C versus T-C-T](https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_ctc_vs_tct.png)

[PNG 파일](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_ctc_vs_tct.png) · [SVG 원본](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_ctc_vs_tct.svg)

## cyclic policy position은 안정성 문맥이지 독립 position 실험이 아니다

ABC/BCA/CAB 순환으로 각 implementation이 first, second, third position에 한 번씩 배치됐다. 가장 큰 세 position 관측 범위는 Exp · FP32에서 235.166 pJ/output이었다. position마다 한 fresh session뿐이므로 이 선은 drift 진단이며 position 효과 추정치가 아니다.

![Policy position stability](https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_position_stability.png)

[PNG 파일](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_position_stability.png) · [SVG 원본](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_position_stability.svg)

## 측정 범위와 metric 정의

- 장치/좌표: RTX 3090, runtime SM 82, S=1024, grid=41 CTA, 256 threads/CTA, 2 rows/CTA.
- 실험 행렬: added stage 3종 × implementation 3종 × fresh session 3회 = 27 cell.
- acquisition contract에 기록된 ATC 단위: `Operand-rate ATC ΔpJ/logical Softmax output element for one added stage pass`. Base 사후검토 뒤 에너지 해석에서는 secondary diagnostic으로 분류한다.
- logical denominator: `grid_blocks × 2 rows/CTA × observed ITER × S`. FP16x2도 두 scalar output을 각각 세며 별도의 `/2` 보정은 없다.
- C-T-C: middle treatment power에서 두 outer active-control power의 시간보간값을 빼고 middle treatment logical-output rate로 나눈다.
- T-C-T: 두 outer treatment power와 output rate를 middle 시점으로 보간한 뒤 middle active-control power를 뺀다.
- session effect: C-T-C와 T-C-T의 signed effect 평균. Cell summary는 fresh 3-session mean, sample SD, `t(0.975, df=2)` descriptive interval이다.
- non-primary same-ITER diagnostic: 각 role에서 `E_hat_role = P_hat_trace × t_CUDA`를 계산한다. C-T-C는 `(E_hat_T−E_hat_C*)×1e12/N_same_ITER`, T-C-T는 `(E_hat_T*−E_hat_C)×1e12/N_same_ITER`이며 두 orientation을 평균한다. Idle을 쓰지 않는다. 순수 stage energy는 아니지만 runtime이 다른 fixed-work intervention의 gross energy 차에는 ATC보다 직접적이다.
- idle: `diagnostic_only_excluded_from_ATC_numerator`. 즉 기록은 하지만 ATC numerator에 사용하지 않는다.

## 실험 설계와 fail-closed 검증

Control과 treatment는 같은 kernel symbol, geometry, ITER, I/O 및 resource 계약을 사용하고, runtime flag만 treatment의 redundant added-stage pass를 활성화한다. Main Softmax output은 control과 treatment 사이에 bit-identical gate를 통과해야 한다. 각 stage session은 fresh CUDA process이고 내부 context는 지속된다.

공통 preheat 요청은 5.0 s이며 actual gate는 [3.75, 6.25] s다. 각 stage에서 policy order는 ABC/BCA/CAB로 순환하고, 각 cell은 C-T-C 뒤 T-C-T의 여섯 role을 실행한다. 에너지는 `nvml_total_energy`를 사용하며 integration은 `guarded_interior_theil_sen`이다. 기록된 cell 단위 온도 범위의 전체 외곽은 55.0–69.0 °C였다. 이는 문맥 정보이며 보정값이나 hard rejection gate가 아니다.

Manifest에 결합된 NCU dynamic instruction audit는 18개 target launch와 9개 stage×implementation control/treatment pair의 same-symbol 및 instruction-delta gate를 통과했다. NCU는 instruction evidence일 뿐이며 에너지 수치는 `nvml_total_energy` NVML trace에서만 계산했다.

| Gate | Status |
|---|---|
| `exact_3x3x3_schedule` | `pass` |
| `guarded_trace_slopes` | `pass` |
| `idle_primary_exclusion` | `pass` |
| `independent_trace_fit_window_reconstruction` | `pass` |
| `logical_output_denominator` | `pass` |
| `ncu_dynamic_instruction_audit_binding` | `pass` |
| `output_equivalence` | `pass` |
| `per_cell_treatment_calibration` | `pass` |
| `raw_trace_manifest_hashes` | `pass` |
| `resource_and_smid_placement` | `pass` |
| `same_iter_diagnostic_separate_from_primary` | `pass` |
| `same_symbol_geometry_iters` | `pass` |
| `six_roles_per_cell` | `pass` |
| `static_audit_binding` | `pass` |
| `treatment_calibration_duration` | `pass` |
| `treatment_invariant_live_sink_dataflow` | `pass` |

## 불확실성, 한계, 강건성 범위

- 이 값은 board-level active-control contrast다. 순수 opcode 에너지, complete-Softmax 절대 에너지, 또는 stage별 독립 원가 계수가 아니다.
- n=3/cell이라 SD와 t95가 한 session에 민감하다. t95는 descriptive이며 9개 cell의 동시 추론이나 일반화 보장을 제공하지 않는다.
- RTX 3090의 S=1024, q50 underfilled grid 한 좌표만 측정했다. V100/A100/H100, 다른 S/CTA, full-SM saturation으로 자동 전이되지 않는다.
- Added pass는 원래 stage를 제거·교체하지 않고, complete-Softmax kernel 내부의 선택된 stage 계산 지점에서 treatment가 활성화하는 redundant probe다. Probe 결과는 main output이 아니라 live sink로 관측되므로 compiler lowering과 sink dataflow의 영향도 포함한다.
- 이 공식 acquisition의 입력은 frozen binary 기본값인 logit scale `4.0`, seed `5573589319906701683`으로 결정론적으로 생성됐다. 당시 command/raw/manifest가 두 값을 중복 기록하지 않은 provenance 한계가 있으나 frozen binary SHA로 경로는 동결돼 있다. 후속 runner는 두 값을 CLI와 manifest/raw에 명시한다.
- Same-ITER여도 control과 treatment의 wall time은 같지 않다. 특히 reduction은 treatment가 더 오래 실행되고 평균 board power가 낮아져 음의 Operand-rate projection이 생겼다. 따라서 부호를 stage의 실제 에너지 비용 부호로 바꾸어 읽을 수 없다.
- C-T-C/T-C-T와 cyclic order는 시간 drift를 줄이고 드러내지만 모든 DVFS, 온도, 전원상태 confounding을 제거하지 않는다.
- Static PTX/SASS audit와 NCU dynamic instruction audit는 treatment code-path와 실제 instruction delta의 frozen-binary 근거다. NCU/SASS 자체가 board power를 측정한 것은 아니며 에너지 결과는 NVML 기반이다.

## 다음 실험은 3개 cell의 두 추정량만 좁게 확인한다

**상태: proposed v3 / not implemented.** 아래 설계는 완료된 v2의 manifest, raw data 또는 quality gate를 소급 변경하지 않는다.

1. 넓은 CTA×S sweep은 열지 않고 scalar FP16의 Exp, Reduction, Normalization 세 cell만 동일 좌표에서 다시 측정한다.
2. **Arm A — equal-duration power-rate:** C와 T의 ITER를 독립 보정해 각 role을 약 13 s로 맞추고 elapsed ratio gate를 `0.98–1.02`로 둔다. C-T-C/T-C-T는 선형 drift 완화용으로 유지하며 ATC는 power-behavior diagnostic으로 보고한다.
3. **Arm B — exact same-work energy:** C와 T에 동일 ITER를 주고 각 role의 `E_hat_role=P_hat_trace×t_CUDA`로 만든 orientation-specific fixed-work gross `ΔE_hat/N`을 energy-oriented primary로 보고한다. 충분히 긴 bracketed idle을 새로 수집할 수 있을 때만 idle-adjusted 값은 sensitivity로 추가한다.
4. 각 cell은 4개 fresh session으로 한다. Arm 순서는 `A→B` 2회와 `B→A` 2회, bracket 시작 순서는 `C-T-C→T-C-T` 2회와 `T-C-T→C-T-C` 2회를 2×2로 교차 균형화한다. Preheat는 5 s를 유지한다. 해석이 남을 때만 동일 3-cell/4-session 구성의 fixed-SM-clock sensitivity cohort를 한 번 추가한다.
5. 원래 목표인 FP32/scalar FP16/packed FP16x2 complete-Softmax 비교는 각 구현의 고정 logical workload endpoint energy/output으로 판단한다. 한 stage의 precision 효과는 나머지 I/O·stage를 고정한 stage-replacement endpoint로 판단한다.
6. 이 3-cell 결과가 재현된 뒤에도 좌표 의존성을 확인해야 할 때만 S 또는 CTA 한 축의 끝점 하나를 추가하고, stage×policy×S×CTA 전체 sweep은 열지 않는다.
7. 플랫폼 비교는 각 GPU의 native binary/static audit와 동일 logical denominator를 별도로 검증하고, 플랫폼 간 절대 pJ를 clock/thermal 조건 없이 직접 순위화하지 않는다.

## 남은 질문

- t95가 0을 포함하거나 orientation disagreement가 mean보다 큰 cell은 fresh session 추가 시 방향이 유지되는가?
- fixed SM clock 또는 외부 전력계 sensitivity에서 bracket disagreement가 줄어드는가?
- S 또는 CTA 한 축의 두 targeted 끝점에서 implementation 간 방향이 유지되는가?
- A100/H100 native lowering에서도 동일한 added-stage 의미와 live-sink 증거가 유지되는가?

## 근거 파일과 재현 경로

- report schema: `softmax_whole_stage_atc_report_v1`
- figure manifest SHA-256: `a18e54ecf934df460949448479b7a8b2b391fe9fdc35a7b7c64dc2f30704ec2e`
- run manifest SHA-256: `0cf0f16fea34a95e21cd7ddfd077b58ae471cc4ee424a3b461dda0f69ccfbbe5`
- figure caveat: n=3 fresh sessions per stage/policy cell; t95 intervals are descriptive and no multiple-comparison claim is made.
- run manifest: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/manifest.json`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/manifest.json) (SHA-256 `0cf0f16fea34a95e21cd7ddfd077b58ae471cc4ee424a3b461dda0f69ccfbbe5`)
- analysis JSON: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/analysis.json`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/analysis.json) (SHA-256 `d72eb597c0f53d5ab54eb557ef9d538d2ddd1ba4257c7afa517c17605990395b`)
- matched effects: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/matched_effects.csv`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/matched_effects.csv) (SHA-256 `77ac31f30ba45c0163c93e3840efa51ef6ceb9cd8e834f8d51daf5a2e97d88de`)
- session summary: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/session_summary.csv`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/session_summary.csv) (SHA-256 `0c569d06e3295224d77b1d00bf3ad6f08be3b4d73694be250d893d1b535ab731`)
- cell summary: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/cell_summary.csv`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/cell_summary.csv) (SHA-256 `de44d889e8eb3f4fd8f0cdbc2cc681c1b70480e29e8091d0e0cb4fb7fca8b240`)
- quality gates: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/quality_gates.csv`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/analysis/quality_gates.csv) (SHA-256 `c2c942fd07954146f74c1addc34cdf83174fd100a3d01fb5e25b4464eee0fcfd`)
- figure manifest: [`docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/figure_manifest.json`](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/figure_manifest.json) (SHA-256 `a18e54ecf934df460949448479b7a8b2b391fe9fdc35a7b7c64dc2f30704ec2e`)
- ATC generated explainer metadata: [`docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/atc_method_explainer_metadata.json`](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/atc_method_explainer_metadata.json) (SHA-256 `b24c5e04b5b205fe7f39ee697acfd5ad7fcb3959f31c4200d2fda190377aecf1`)
- ATC generated explainer PNG: [`docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_atc_method_explainer.png`](../assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/rtx3090_softmax_whole_stage_atc_operand_rate_v2_atc_method_explainer.png) (SHA-256 `632859720763096e3f2a6df11182afc8bd7e298218d9706687ceb70cdfb2710e`)
- NCU dynamic instruction audit: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/ncu_audit/audit.json`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/ncu_audit/audit.json) (SHA-256 `99a0a9287c684a80da860cbf6deac74a547f919a9d51e2e65a1a632a411400c8`)

재생성 명령:

```bash
python3 scripts/plot_softmax_whole_stage_atc.py --run-dir results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final --out-dir docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final --prefix rtx3090_softmax_whole_stage_atc_operand_rate_v2
python3 scripts/build_softmax_whole_stage_atc_report.py --run-dir results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final --figure-manifest docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/figure_manifest.json --image-base-url https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final --explainer-metadata docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/atc_method_explainer_metadata.json --explainer-image-base-url https://raw.githubusercontent.com/bang001/gpupower0701/e1ba9ea51b1fbe27fb2ada6f39c293b320a32a34/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final --out docs/results/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final_ko.md
```
