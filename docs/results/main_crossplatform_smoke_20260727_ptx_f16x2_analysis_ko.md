# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/22
- exp implementation: `ptx_ex2_approx_f16x2`
- order-balanced effect: 3.369 pJ/logical scalar exponent result
- pair-t 95% CI: [-171.045, 177.783] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [-68.472, 66.687] pJ/logical scalar exponent result
- middle-position bias mean: -13.738 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 6.738 pJ/ex2.approx.f16x2 instruction (71190188032 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | -14.240 | 66.662 | 26.211 | -40.451 | pass |
| 1 | R-F | 101.233 | 17.397 | 59.315 | 41.918 | pass |
| 2 | F-R | -118.098 | -32.738 | -75.418 | -42.680 | pass |
