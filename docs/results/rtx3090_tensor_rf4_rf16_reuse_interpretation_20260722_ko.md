# RTX 3090 FP16 Tensor RF4/RF16 역전 해석과 재실험 설계

갱신일: 2026-07-22
측정 범위: RTX 3090, B16, FP16 WMMA 입력 + FP32 누산, board-level NVML total-energy
결론 등급: **진단 결과이며 final Tensor silicon energy가 아님**

## 1. 결론

30초 operand-rate ATC에서 RF4 `0.266 pJ/FLOP`, RF16 `0.335 pJ/FLOP`가 나온
직접 원인은 RF16의 Tensor 연산 자체가 더 비싸다고 확인됐기 때문이 아니다.
두 좌표의 Tensor 처리율은 약 `63.9`와 `63.6 TFLOP/s`로 비슷하지만,
`reg_mma - reg_operand_only` active-power 차가 RF4 `17.0 W`, RF16 `21.7 W`로
RF16에서 약 28% 컸기 때문이다.

```text
operand-rate ATC [pJ/FLOP]
  = (P_reg_mma - P_reg_operand_only) / Tensor throughput
```

| RF [count] | treatment power [W] | operand-control power [W] | power gap [W] | throughput [TFLOP/s] | coefficient [pJ/FP16 FLOP] |
|---:|---:|---:|---:|---:|---:|
| 4 | 265.18 | 247.50 | 17.02 | 63.91 | 0.266 |
| 16 | 261.95 | 241.04 | 21.74 | 63.61 | 0.335 |

표의 값은 pair별 measurement-valid 중앙값이다. power 열과 gap 열은 각 행의
중앙값을 따로 계산했으므로 단순 뺄셈과 소수점 수준에서 정확히 일치하지 않을 수 있다.

## 2. RF가 커지면 반드시 낮아져야 하는가

아니다. 현재 kernel의 RF는 랜덤 접근이나 cache reuse 횟수가 아니다.
register에 이미 존재하는 동일 FP16 A/B fragment를 outer ITER 안에서 몇 번 MMA에
사용하는지를 뜻한다. 각 inner step에는 treatment와 control 모두 fragment 유지,
부호 toggle, register-control 연산이 있고 treatment에만 `mma_sync`가 추가된다.

```text
reg_operand_only: [register/control step] x RF
reg_mma:          [MMA + register/control step] x RF
```

초기 fragment 생성과 마지막 store는 RF가 커질수록 FLOP당 상각되지만, 수십 초 동안
수십억 번 도는 steady loop에서는 이 고정비가 이미 매우 작다. 따라서 RF4에서 RF16으로
갈 때 기대해야 하는 것은 단조 감소가 아니라, control이 완전한 반사실이라면
**비슷한 plateau**다. 다음 항목이 RF별로 달라지면 plateau가 깨질 수 있다.

특히 현재 fixed-RF specialization은 같은 inner-step 수를 수행할 때 RF16이 RF4보다
outer-loop counter/branch를 덜 실행한다. 이 상각은 treatment와 control에 동일한 전력
감소를 보장하지 않는다. 실제 30초 측정에서는 RF4 대비 RF16 treatment power가 약
`3.23 W` 낮아졌지만 operand-control power는 약 `6.45 W` 낮아졌다. 즉 control이 더
많이 내려가면서 두 power의 차가 커졌고, 그 차를 throughput으로 나눈 계수가
`0.266 -> 0.335 pJ/FLOP`로 증가했다. 현재 NCU evidence만으로 control power가 더 크게
내려간 원인을 scheduler, DVFS, outer-loop 비율 중 하나로 단정할 수는 없다.

- template specialization과 loop 형태에 따른 SASS instruction scheduling
- accumulator dependency와 eligible warp/issue 상태
- `reg_mma` 28 registers/thread 대 `reg_operand_only` 16 registers/thread의 footprint 차이
- RF별 control active power와 treatment active power의 DVFS/thermal 상태
- 실행 순서, pair drift, display/RDP background activity
- 짧은 duration에서 초기 상태와 NVML/idle 추정 오차가 차지하는 비율

## 3. 전체 duration sweep

![RF4/RF16 duration sweep](../assets/component_energy_method/rtx3090_tensor_fp16_clocked_vs_operand_atc_duration_sweep_20260721.png)

2026-07-21 측정의 전체 sweep 표, 유효 행 수와 strict 판정은
[원본 duration-sweep 보고서](rtx3090_tensor_fp16_clocked_vs_operand_atc_duration_sweep_20260721_ko.md)에
분리해 두었다. 이 문서는 해당 결과의 원인 해석과 후속 v3 설계에 초점을 둔다.

| Duration [s] | RF4 operand-rate [pJ/FLOP] | RF16 operand-rate [pJ/FLOP] | RF4 power gap [W] | RF16 power gap [W] | 낮은 RF |
|---:|---:|---:|---:|---:|---|
| 5 | 0.998 | 0.751 | 60.74 | 45.83 | RF16 |
| 10 | 0.475 | 0.610 | 29.79 | 41.90 | RF4 |
| 15 | 0.471 | 0.527 | 30.13 | 33.57 | RF4 |
| 30 | 0.266 | 0.335 | 17.02 | 21.74 | RF4 |

RF 순서가 duration에 따라 바뀐다. 이는 단일 RF의 intrinsic Tensor energy 차이보다
초기 상태, control-state power, DVFS와 시간 보정에 민감한 effective coefficient라는
증거다. `0.266 pJ/FLOP`은 현재 후보 중 낮은 진단값이지 보장된 하한이 아니다.

## 4. NCU가 확인한 것과 확인하지 못한 것

| 항목 | RF4 | RF16 | 해석 |
|---|---:|---:|---|
| treatment/control HMMA | 1,049,600,000 / 0 | 4,198,400,000 / 0 | FP16 Tensor path 존재, control HMMA 없음 |
| Tensor ops / expected FLOP | 1.000 | 1.000 | 논리 FLOP 분모 정합 |
| issue C/O/T [%] | 62.1 / 54.9 / 38.8 | 62.1 / 50.4 / 37.3 | operand와 treatment 실행 상태가 RF별로 변함 |
| registers C/O/T [register/thread] | 16 / 16 / 28 | 16 / 16 / 28 | operand control이 treatment register footprint를 일치시키지 못함 |

`C/O/T`는 clocked-empty, operand control, treatment 순서다. NCU는 HMMA/FLOP 경로는
검증했지만 no-MMA control의 scheduler·issue·register 상태가 treatment와 같다는 것은
검증하지 못했다. 기존 12개 pair의 strict accepted row는 `0`개다. 따라서 RF4/RF16
차이를 순수 Tensor Core 회로 에너지 차이로 결론 내리면 안 된다.

## 5. 대체 실험 설계

새 기본 경로는 `component_dynamic_attribution_v3`이며 RTX 전용 B16/RF4/RF16
스크립트를 final 경로로 사용하지 않는다.

| 축 | RTX 3090 | V100 | A100 | H100 | 단위/목적 |
|---|---|---|---|---|---|
| blocks/SM | 4, 8, 16 | 4, 16, 32 | 4, 16, 32 | 4, 16, 32 | occupancy/issue density sweep |
| RF | 1, 2, 4, 8, 16 | 동일 | 동일 | 동일 | RF plateau와 control bias 확인 |
| duration | 5, 15, 30 | 동일 | 동일 | 동일 | 짧은 transient와 steady-state 민감도 |
| repeats | 3 | 동일 | 동일 | 동일 | order 반전과 signed 분포 |
| precision | FP16 input, FP32 accumulate | 동일 | 동일 | 동일 WMMA compatibility path | logical FP16 FLOP |
| energy roles | baseline-before, control, treatment, baseline-after | 동일 | 동일 | 동일 | 4 rows/pair |
| final 규모 | 135 pairs / 540 rows | 동일 | 동일 | 동일 | 3 B x 5 RF x 3 duration x 3 repeat |

각 pair는 같은 ITER의 `reg_operand_only`와 `reg_mma`를 사용한다. cooldown은 role마다
넣지 않고 pair 시작 전에 한 번만 적용해 treatment-control gap을 늘리지 않는다.
각 command는 자신의 idle baseline을 측정하며 pair 앞뒤 `clocked_empty`를 별도로 둔다.

세 계수를 동시에 보고한다.

| 방법 | 식의 의미 | 지위 |
|---|---|---|
| matched-ITER completion | 같은 work 완료 시 실제 net-energy 차 | 실측 completion boundary |
| clocked MI-ATC | completion에서 clocked active-time energy 제거 | model surrogate |
| control-rate ATC | operand-control power를 treatment 시간으로 확장해 제거 | Tensor에서는 operand-rate diagnostic |
| FLOP/time 공동회귀 | FLOP와 추가 elapsed effect를 B/RF/duration/order/repeat에서 동시 추정 | 식별성 gate 통과 시만 채택 |

NCU는 각 B와 RF 1/2/4/8/16에서 treatment HMMA, control HMMA, FP16 ops/FLOP,
register footprint, spill/local traffic과 RF 간 HMMA/logical-MMA 안정성을 검증한다.
V100/A100/H100의 HMMA lowering count가 같다고 가정하지 않고 각 아키텍처 내부의
비례성과 path acceptance를 사용한다.

## 6. 실행 진입점

```bash
python3 scripts/plan_tensor_fp16_cross_platform_experiment.py \
  --target-profile a100 \
  --gpu-id 0 \
  --preset final

bash results/summary/a100_tensor_fp16_cross_platform_final_YYYYMMDD_command.sh
```

동일 방식으로 `--target-profile v100`, `h100`, `rtx3090`을 선택한다. 먼저
`--preset pilot`으로 NCU 경로와 calibration을 확인하되 pilot 값은 final로 승격하지
않는다. 생성 shell은 완료 pair를 재개 시 건너뛰며 NCU 권한 오류는 기존 sudo fallback을
사용한다.

## 7. 최종 판단 규칙

1. RF별 최솟값만 선택하지 않는다. measurement-valid signed 분포와 반복을 먼저 본다.
2. HMMA/FLOP가 맞아도 control register/issue 상태가 다르면 pure Tensor라고 부르지 않는다.
3. 세 estimator가 크게 다르거나 duration에 따라 RF 순서가 바뀌면 단일 final 값 채택을 보류한다.
4. 공동회귀가 traffic/time 공선성, 0 포함 CI 또는 부호 불안정을 보이면 `not_identified`로 둔다.
5. 최종 수치는 NCU로 경로가 검증된 workload-dependent effective board-level coefficient다.

## 근거 파일

- 결합 요약: `results/summary/rtx3090_tensor_fp16_clocked_vs_operand_atc_d5_d10_d15_d30_20260721_summary.csv`
- 15/30초 detail: `results/summary/rtx3090_tensor_fp16_clocked_vs_operand_atc_d15_d30_20260721_v1_detail.csv`
- 원 보고서: `docs/results/rtx3090_tensor_fp16_clocked_vs_operand_atc_d15_d30_20260721_ko.md`
- 새 runner: `scripts/run_component_dynamic_attribution.py`
- 새 analyzer: `scripts/analyze_component_dynamic_attribution.py`
- 새 planner: `scripts/plan_tensor_fp16_cross_platform_experiment.py`
