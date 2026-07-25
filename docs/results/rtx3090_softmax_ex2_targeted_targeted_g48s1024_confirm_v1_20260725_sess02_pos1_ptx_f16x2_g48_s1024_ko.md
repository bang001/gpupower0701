# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16x2`
- order-balanced effect: 21.452 pJ/logical scalar exponent result
- pair-t 95% CI: [-38.683, 81.587] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [0.882, 45.373] pJ/logical scalar exponent result
- middle-position bias mean: 6.038 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 42.903 pJ/ex2.approx.f16x2 instruction (370714533888 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 18.839 | 12.971 | 15.905 | 2.934 | pass |
| 1 | R-F | 85.720 | 10.182 | 47.951 | 37.769 | pass |
| 2 | F-R | -22.089 | 23.086 | 0.499 | -22.587 | pass |
