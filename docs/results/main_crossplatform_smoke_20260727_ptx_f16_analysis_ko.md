# FP16 Softmax counterbalanced probe 결과

## 판정

- verdict: `not_identified`
- decision stage: `pilot`
- configured/observed minimum fit points: 16/19
- exp implementation: `ptx_ex2_approx_f16`
- order-balanced effect: 20.705 pJ/logical scalar exponent result
- pair-t 95% CI: [-214.009, 255.418] pJ/logical scalar exponent result
- hierarchical residual-MBB 95% CI: [-62.221, 113.153] pJ/logical scalar exponent result
- middle-position bias mean: -59.930 pJ/logical scalar exponent result
- auxiliary PTX-op effect: 20.705 pJ/ex2.approx.f16 instruction (129259208704 instructions/role)

1차 분모는 항상 logical scalar exponent result이다. packed f16x2의 PTX-op 분모는 logical result의 1/2인 보조 표시이며, scalar result당 계수와 혼동하지 않는다. 개별 triplet CI는 진단값이며 탈락 gate가 아니다.

## Matched block

| block | order | forward (pJ/result) | reverse (pJ/result) | balanced effect (pJ/result) | middle bias (pJ/result) | quality |
|---:|---|---:|---:|---:|---:|---|
| 0 | F-R | 78.772 | 178.821 | 128.796 | -50.025 | pass |
| 1 | R-F | -111.566 | 19.227 | -46.170 | -65.397 | pass |
| 2 | F-R | -84.880 | 43.855 | -20.512 | -64.367 | pass |
