# RTX 3090 Whole-Softmax stage Operand-rate ATC 보고서

## 기술 요약

**이 보고서의 primary 결과는 idle-subtracted complete-Softmax energy나 stage의 물리적 에너지 원가가 아니라, 동일 active-control 대비 treatment의 signed Operand-rate power projection이다.** 즉 `(P_T-P_C)/treatment logical-output rate`를 ΔpJ/logical output으로 표시한다. Fail-closed 분석은 162개 measured role, 27개 fresh-session cell, 54개 bracket effect와 9개 stage×implementation summary를 모두 통과시켰다.

9개 mean은 -700.436–+47.067 ΔpJ/logical output 범위였다. 3/3 session이 양수인 cell은 1/9, 0/3인 cell은 4/9였다. descriptive t95가 0보다 큰 cell은 1/9, 0보다 작은 cell은 4/9, 0을 포함한 cell은 4/9였다. 최저 mean은 Max + sum reduction · scalar FP16 -700.436, 최고 mean은 Normalization · scalar FP16 +47.067였다. 이 최저/최고는 이 단일 좌표의 기술적 비교이며 stage 원가의 보편적 순위가 아니다. 특히 음수는 treatment가 control보다 오래 실행되면서 평균 board power가 낮아진 signed contrast이며, 추가 연산이 음의 물리 에너지를 소비하거나 Softmax 에너지를 절감했다는 뜻이 아니다.

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

Reduction의 18/18 bracket에서 `P_T−P_C`가 음수였지만, 같은 ITER의 role energy를 비교한 비-primary diagnostic은 18/18 bracket에서 양수였다. 아래 `same-ITER gross ΔE/N`은 각 role의 qualified trace power에 실제 elapsed를 곱한 뒤 같은 midpoint 규칙으로 role energy를 보간해 계산한다. Idle은 사용하지 않는다.

| Implementation | primary mean ATC ΔpJ/output | mean ΔP | mean T/C elapsed | non-primary same-ITER gross ΔE/N | diagnostic descriptive t95 |
|---|---:|---:|---:|---:|---:|
| FP32 | -600.909 | -16.152 W | 1.390× | +1,826.390 | [+1,747.040, +1,905.740] |
| scalar FP16 | -700.436 | -14.216 W | 1.726× | +3,530.892 | [+3,376.873, +3,684.912] |
| packed FP16x2 | -473.433 | -16.833 W | 1.442× | +1,423.060 | [+1,316.610, +1,529.511] |

이 진단은 treatment가 더 오래 실행된다는 사실을 회계에 포함하므로 reduction ATC 음수가 물리적 에너지 절감을 뜻하지 않음을 보여준다. 다만 complete Softmax 공통 작업의 추가 runtime까지 포함한 gross board-energy contrast이므로 순수 reduction stage 원가로 재명명해서도 안 된다. Primary Operand-rate ATC를 대체하거나 두 값을 합산하지 않는다.

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
- primary 단위: `Operand-rate ATC ΔpJ/logical Softmax output element for one added stage pass`.
- logical denominator: `grid_blocks × 2 rows/CTA × observed ITER × S`. FP16x2도 두 scalar output을 각각 세며 별도의 `/2` 보정은 없다.
- C-T-C: middle treatment power에서 두 outer active-control power의 시간보간값을 빼고 middle treatment logical-output rate로 나눈다.
- T-C-T: 두 outer treatment power와 output rate를 middle 시점으로 보간한 뒤 middle active-control power를 뺀다.
- session effect: C-T-C와 T-C-T의 signed effect 평균. Cell summary는 fresh 3-session mean, sample SD, `t(0.975, df=2)` descriptive interval이다.
- non-primary same-ITER diagnostic: 각 role에서 `E_role = qualified trace power × elapsed`를 계산하고, 같은 bracket midpoint 보간 뒤 `(E_T−E_C) × 1e12 / N_same_ITER`로 낸다. Idle을 쓰지 않으며 primary ATC를 대체하지 않는다.
- idle: `diagnostic_only_excluded_from_ATC_numerator`. 즉 기록은 하지만 primary numerator에 사용하지 않는다.

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
- Added pass는 원래 complete Softmax 뒤의 redundant probe다. 원래 stage를 제거·교체한 endpoint 비교가 아니며 compiler lowering과 live-sink 상호작용을 포함한다.
- 이 공식 acquisition의 입력은 frozen binary 기본값인 logit scale `4.0`, seed `5573589319906701683`으로 결정론적으로 생성됐다. 당시 command/raw/manifest가 두 값을 중복 기록하지 않은 provenance 한계가 있으나 frozen binary SHA로 경로는 동결돼 있다. 후속 runner는 두 값을 CLI와 manifest/raw에 명시한다.
- Same-ITER여도 control과 treatment의 wall time은 같지 않다. 특히 reduction은 treatment가 더 오래 실행되고 평균 board power가 낮아져 음의 Operand-rate projection이 생겼다. 따라서 부호를 stage의 실제 에너지 비용 부호로 바꾸어 읽을 수 없다.
- C-T-C/T-C-T와 cyclic order는 시간 drift를 줄이고 드러내지만 모든 DVFS, 온도, 전원상태 confounding을 제거하지 않는다.
- Static PTX/SASS audit와 NCU dynamic instruction audit는 treatment code-path와 실제 instruction delta의 frozen-binary 근거다. NCU/SASS 자체가 board power를 측정한 것은 아니며 에너지 결과는 NVML 기반이다.

## 다음 실험은 불확실한 cell만 좁게 확인한다

1. 넓은 CTA×S sweep 전에 불확실성이 큰 `Exp · FP32, Exp · scalar FP16, Normalization · scalar FP16`만 같은 좌표에서 fresh session을 추가하거나 fixed-clock/external-meter sensitivity로 확인한다.
2. Operand-rate ATC를 primary로 유지하고 이번에 추가한 same-ITER gross board-energy diagnostic도 계속 별도 표기한다. 어느 쪽도 다른 쪽으로 재명명하거나 두 값을 합산하지 않는다.
3. 추가 확인에서도 같은 symbol/geometry/ITER와 C-T-C/T-C-T balance를 유지하고 가능하면 fixed clock 또는 외부 전력계 sensitivity를 추가한다.
4. 한두 targeted 좌표에서 방향이 재현된 뒤에만 S 또는 CTA 한 축을 증분한다. stage×policy×S×CTA 전체 sweep을 바로 열지 않는다.
5. 플랫폼 비교는 각 GPU의 native binary/static audit와 동일 logical denominator를 별도로 검증하고, 플랫폼 간 절대 pJ를 clock/thermal 조건 없이 직접 순위화하지 않는다.

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
- NCU dynamic instruction audit: [`results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/ncu_audit/audit.json`](../../results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final/ncu_audit/audit.json) (SHA-256 `99a0a9287c684a80da860cbf6deac74a547f919a9d51e2e65a1a632a411400c8`)

재생성 명령:

```bash
python3 scripts/plot_softmax_whole_stage_atc.py --run-dir results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final --out-dir docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final --prefix rtx3090_softmax_whole_stage_atc_operand_rate_v2
python3 scripts/build_softmax_whole_stage_atc_report.py --run-dir results/raw/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final --figure-manifest docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final/figure_manifest.json --image-base-url https://raw.githubusercontent.com/bang001/gpupower0701/f2df8b4df44cbe809110549e29d7330ae49a7cc3/docs/assets/softmax_whole_stage_atc_20260728_operand_rate_v2_final --out docs/results/rtx3090_softmax_whole_stage_atc_20260728_operand_rate_v2_final_ko.md
```
