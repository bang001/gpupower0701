# RTX 3090 FP16 Tensor RF4/RF16 duration sweep 비교

> 결론: RF4가 RF16보다 항상 높아야 한다는 가설은 현재 control에서는 성립하지 않았다. 5초에서만 RF4가 높았고 10/15/30초에서는 반전됐다. 반전은 treatment 처리율보다 RF별 operand-control active power 변화와 함께 움직였으므로, 순수 Tensor RF 효과가 아니라 control-state/DVFS 민감도로 본다.

![RF와 duration 비교](../assets/component_energy_method/rtx3090_tensor_fp16_clocked_vs_operand_atc_duration_sweep_20260721.png)

## 실험 행렬

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| GPU | RTX 3090 (GA102) | board |
| precision | FP16 A/B, FP32 accumulator | WMMA m16n16k16 |
| blocks/SM | 16 | block/SM |
| reuse factor | 4, 16 | MMA/outer iteration [count] |
| treatment duration | 5, 10, 15, 30 | s |
| 반복 | 각 좌표 3 | pair [count] |
| 전체 | 24 pair, 96 energy role | count |

## Operand-rate ATC 결과

주 값은 양수만 고른 값이 아니라 measurement gate를 통과한 signed row의 중앙값이다. 괄호는 valid/3이다.

| duration [s] | RF4 [pJ/FLOP] | RF16 [pJ/FLOP] | RF4-RF16 [pJ/FLOP] | RF4 power gap [W] | RF16 power gap [W] | 관찰 |
|---:|---:|---:|---:|---:|---:|---|
| 5 | 0.998 (3/3) | 0.751 (3/3) | +0.247 | 60.7 | 45.8 | RF4 > RF16 |
| 10 | 0.475 (3/3) | 0.610 (2/3) | -0.135 | 29.8 | 41.9 | RF4 < RF16 (reversal) |
| 15 | 0.471 (1/3) | 0.527 (3/3) | -0.056 | 30.1 | 33.6 | RF4 < RF16 (reversal) |
| 30 | 0.266 (3/3) | 0.335 (2/3) | -0.069 | 17.0 | 21.7 | RF4 < RF16 (reversal) |

## Clocked-empty MI-ATC 결과

| duration [s] | RF4 [pJ/FLOP] | RF16 [pJ/FLOP] | RF4-RF16 [pJ/FLOP] | 판정 |
|---:|---:|---:|---:|---|
| 5 | 0.222 (3/3) | 0.008 (3/3) | +0.214 | control overactive; coefficient 채택 불가 |
| 10 | 0.023 (3/3) | -0.003 (2/3) | +0.025 | control overactive; coefficient 채택 불가 |
| 15 | 0.026 (1/3) | -0.069 (3/3) | +0.095 | control overactive; coefficient 채택 불가 |
| 30 | -0.068 (3/3) | -0.118 (2/3) | +0.051 | control overactive; coefficient 채택 불가 |

## 왜 순서가 뒤집혔는가

Operand-rate ATC는 각 pair에서 정확히 다음 관계를 만족한다.

```text
coefficient = (P_treatment - P_operand-control) / treatment_FLOP_rate
            [pJ/FLOP] = [W] / [TFLOP/s]
```

따라서 RF 순서는 주로 active power gap이 결정한다. 처리율은 모든 좌표에서 약 61-64 TFLOP/s로 유사했지만, power gap은 5초에서 RF4가 더 크고 10/15/30초에서는 RF16이 더 컸다. 계수 순서도 그대로 바뀌었다.

| duration [s] | RF4 throughput [TFLOP/s] | RF16 throughput [TFLOP/s] | RF4 gap [W] | RF16 gap [W] |
|---:|---:|---:|---:|---:|
| 5 | 62.073 | 61.006 | 60.7 | 45.8 |
| 10 | 62.948 | 63.404 | 29.8 | 41.9 |
| 15 | 63.908 | 63.137 | 30.1 | 33.6 |
| 30 | 63.909 | 63.606 | 17.0 | 21.7 |

`reg_operand_only`도 RF에 따라 loop branch, issue, ALU 활동이 바뀌며 NCU에서 treatment scheduler state와 일치하지 않았다. RF16이 outer-loop overhead를 더 amortize하면 control power가 낮아져 오히려 덜 차감되고 계수가 높아질 수 있다. 그러므로 현재 protocol에서 `RF4 > RF16`은 물리 법칙이 아니다.

## 품질 판정

| 검증 | 결과 | 의미 |
|---|---:|---|
| method rows | 48/48 | 완전성 pass |
| measurement-valid | 40/48 | idle/clock/temperature gate 통과 |
| environment-valid | 2/48 | RDP memory-util gate 통과 |
| strict accepted | 0/48 | 최종 Tensor coefficient로 채택 불가 |
| FP16 NCU path | pass | treatment HMMA/FLOP 정합, control HMMA=0, spill=0 |
| NCU control-state | fail | clocked 및 operand 모두 treatment issue/ALU/FMA state 불일치 |

15/30초 실행 중 pre-command memory utilization은 3-23%였고, 냉각 대기는 일부 role에서 90-170초까지 늘었다. 또한 5/10초와 15/30초는 별도 session이다. 따라서 duration 추세에는 RDP/background activity와 열 상태 차이가 포함될 수 있다.

## 객관적 결론

1. 15초와 30초를 추가해도 RF4가 RF16보다 항상 높다는 패턴은 복원되지 않았다.
2. 15초 결과는 RF4 0.471, RF16 0.527 pJ/FLOP이고, 30초 결과는 RF4 0.266, RF16 0.335 pJ/FLOP이다. 모두 diagnostic effective coefficient다.
3. 반전의 직접 원인은 분모가 아니라 operand-control과 treatment의 RF별 power gap 변화다. 이는 NCU control-state mismatch와 정합한다.
4. 30초에서 repeat spread는 줄었지만 cross-duration drift가 크므로, 긴 duration이 자동으로 더 순수한 Tensor 에너지를 주는 것은 아니다.
5. 다음 단계는 RF별 control 자체의 issue/ALU/clock/power를 treatment와 맞춘 뒤 같은 5/10/15/30초 행렬을 재실행하는 것이다.

## 재현 근거

- detail: `results/summary/rtx3090_tensor_fp16_clocked_vs_operand_atc_20260721_v1_detail.csv`
- detail: `results/summary/rtx3090_tensor_fp16_clocked_vs_operand_atc_d15_d30_20260721_v1_detail.csv`
- combined summary: `results/summary/rtx3090_tensor_fp16_clocked_vs_operand_atc_d5_d10_d15_d30_20260721_summary.csv`
