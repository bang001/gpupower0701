# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16`
- order-balanced effect: 17.764 pJ/logical scalar exponent result
- pair-t 95% CI: [-44.371, 79.898] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [-3.807, 42.656] pJ/logical scalar exponent result
- middle-position bias mean: 12.054 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 17.764 pJ/ex2.approx.f16 instruction (745947906048 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | -1.162 | -5.446 | -3.304 | 2.142 | pass |
| 1 | R-F | 74.995 | 15.819 | 45.407 | 29.588 | pass |
| 2 | F-R | 15.620 | 6.756 | 11.188 | 4.432 | pass |
