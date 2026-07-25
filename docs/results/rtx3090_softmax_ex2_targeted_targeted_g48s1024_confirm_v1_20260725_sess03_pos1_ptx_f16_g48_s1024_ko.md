# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16`
- order-balanced effect: 15.178 pJ/logical scalar exponent result
- pair-t 95% CI: [-63.429, 93.786] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [-10.452, 46.594] pJ/logical scalar exponent result
- middle-position bias mean: 8.416 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 15.178 pJ/ex2.approx.f16 instruction (747039916032 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | -26.591 | 38.262 | 5.836 | -32.427 | pass |
| 1 | R-F | 11.567 | -33.052 | -10.743 | 22.309 | pass |
| 2 | F-R | 85.807 | 15.076 | 50.441 | 35.365 | pass |
