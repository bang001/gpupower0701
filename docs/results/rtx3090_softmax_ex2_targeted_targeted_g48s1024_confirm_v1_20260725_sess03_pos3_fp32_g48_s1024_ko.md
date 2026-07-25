# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `positive_identified_pilot`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `fp32_fast___expf`
- order-balanced effect: 84.262 pJ/logical scalar exponent result
- pair-t 95% CI: [27.363, 141.160] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [61.351, 105.245] pJ/logical scalar exponent result
- middle-position bias mean: -10.256 pJ/logical scalar exponent result
- auxiliary PTX-op effect: not applicable to the CUDA `__expf` path

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 110.535 | 97.956 | 104.246 | 6.290 | pass |
| 1 | R-F | 75.846 | 102.701 | 89.273 | -13.427 | pass |
| 2 | F-R | 35.636 | 82.895 | 59.266 | -23.629 | pass |
