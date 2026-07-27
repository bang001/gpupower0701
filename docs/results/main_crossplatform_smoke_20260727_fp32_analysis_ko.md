# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/22
- exp implementation: `fp32_fast___expf`
- order-balanced effect: 110.930 pJ/logical scalar exponent result
- pair-t 95% CI: [-65.360, 287.219] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [44.210, 183.233] pJ/logical scalar exponent result
- middle-position bias mean: -51.788 pJ/logical scalar exponent result
- auxiliary PTX-op effect: not applicable to the CUDA `__expf` path

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 185.953 | 7.589 | 96.771 | 89.182 | pass |
| 1 | R-F | 96.882 | 278.933 | 187.908 | -91.025 | pass |
| 2 | F-R | -105.411 | 201.631 | 48.110 | -153.521 | pass |
