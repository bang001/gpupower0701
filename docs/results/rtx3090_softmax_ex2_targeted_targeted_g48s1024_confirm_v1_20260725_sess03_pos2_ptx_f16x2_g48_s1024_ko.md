# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `positive_identified_pilot`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16x2`
- order-balanced effect: 31.366 pJ/logical scalar exponent result
- pair-t 95% CI: [1.682, 61.049] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [17.939, 44.293] pJ/logical scalar exponent result
- middle-position bias mean: 21.611 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 62.731 pJ/ex2.approx.f16x2 instruction (370720923648 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 1.645 | 51.729 | 26.687 | -25.042 | pass |
| 1 | R-F | 90.604 | -45.676 | 22.464 | 68.140 | pass |
| 2 | F-R | 66.682 | 23.210 | 44.946 | 21.736 | pass |
