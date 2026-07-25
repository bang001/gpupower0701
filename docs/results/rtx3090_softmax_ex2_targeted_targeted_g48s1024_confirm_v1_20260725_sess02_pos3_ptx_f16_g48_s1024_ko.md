# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `positive_identified_pilot`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/20
- exp implementation: `ptx_ex2_approx_f16`
- order-balanced effect: 25.237 pJ/logical scalar exponent result
- pair-t 95% CI: [1.272, 49.201] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [14.152, 34.587] pJ/logical scalar exponent result
- middle-position bias mean: -17.274 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 25.237 pJ/ex2.approx.f16 instruction (741195792384 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 20.170 | 33.909 | 27.040 | -6.869 | pass |
| 1 | R-F | -11.739 | 41.370 | 14.815 | -26.554 | pass |
| 2 | F-R | 15.455 | 52.255 | 33.855 | -18.400 | pass |
