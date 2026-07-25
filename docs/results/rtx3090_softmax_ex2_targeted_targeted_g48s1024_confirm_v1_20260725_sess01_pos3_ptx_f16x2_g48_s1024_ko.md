# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16x2`
- order-balanced effect: 22.347 pJ/logical scalar exponent result
- pair-t 95% CI: [-1.436, 46.131] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [10.805, 33.311] pJ/logical scalar exponent result
- middle-position bias mean: 2.625 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 44.695 pJ/ex2.approx.f16x2 instruction (369289887744 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 23.104 | 20.214 | 21.659 | 1.445 | pass |
| 1 | R-F | 24.633 | 1.639 | 13.136 | 11.497 | pass |
| 2 | F-R | 27.181 | 37.314 | 32.247 | -5.067 | pass |
