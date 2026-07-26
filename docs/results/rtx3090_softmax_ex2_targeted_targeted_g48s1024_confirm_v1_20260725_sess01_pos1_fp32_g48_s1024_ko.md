# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `positive_identified_pilot`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `fp32_fast___expf`
- order-balanced effect: 83.669 pJ/logical scalar exponent result
- pair-t 95% CI: [17.217, 150.122] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [61.519, 110.137] pJ/logical scalar exponent result
- middle-position bias mean: -26.751 pJ/logical scalar exponent result
- auxiliary PTX-op effect: not applicable to the CUDA `__expf` path

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 58.087 | 101.034 | 79.560 | -21.473 | pass |
| 1 | R-F | 86.210 | 138.264 | 112.237 | -26.027 | pass |
| 2 | F-R | 26.457 | 91.965 | 59.211 | -32.754 | pass |
