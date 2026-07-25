# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `positive_identified_pilot`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `fp32_fast___expf`
- order-balanced effect: 78.561 pJ/logical scalar exponent result
- pair-t 95% CI: [47.385, 109.738] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [64.513, 91.948] pJ/logical scalar exponent result
- middle-position bias mean: -25.084 pJ/logical scalar exponent result
- auxiliary PTX-op effect: not applicable to the CUDA `__expf` path

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 37.364 | 134.108 | 85.736 | -48.372 | pass |
| 1 | R-F | 64.272 | 63.868 | 64.070 | 0.202 | pass |
| 2 | F-R | 58.796 | 112.960 | 85.878 | -27.082 | pass |
