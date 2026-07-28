# Whole-Softmax precision range analysis

이 문서는 complete Softmax forward의 `net pJ/logical output element`만 다룬다. EX2 Operand-rate ATC의 `pJ/logical exponent result`와 섞지 않는다.

## Best / representative / worst (screened)

| endpoint | screened best | fixed representative S1024/q50 | screened worst | status |
|---|---:|---:|---:|---|
| scalar FP16 endpoint | 2,055.8 (s1024_q50) | 2,055.8 | 5,056.1 (s4096_q25) | followup_complete_screened_range_not_fresh_extrema_confirmed |
| packed FP16x2 endpoint | 1,626.8 (s512_q50) | 1,738.9 | 5,320.5 (s4096_q25) | followup_complete_screened_range_not_fresh_extrema_confirmed |
| FP32 endpoint | 2,089.3 (s512_q50) | 2,596.7 | 6,456.4 (s4096_q25) | followup_complete_screened_range_not_fresh_extrema_confirmed |

## Fixed representative interpretation

사전 고정 대표 좌표 `S=1024,q50`의 median은 FP32 2,596.7, scalar FP16 2,055.8, packed FP16x2 1,738.9 pJ/logical output element였다. packed가 이 대표 좌표에서는 가장 낮지만, screened envelope 전체의 범위는 coordinate에 따라 겹친다. 따라서 이를 모든 S·CTA 조건에서 packed가 보편적으로 우월하다는 주장으로 일반화하지 않는다.

## Coordinate summary

| coordinate | endpoint | n | median | SD | descriptive t95 |
|---|---|---:|---:|---:|---:|
| S=1024 · q25 | scalar FP16 endpoint | 3 | 2,518.2 | 110.8 | [2,283.7, 2,834.4] |
| S=1024 · q25 | packed FP16x2 endpoint | 3 | 1,961.5 | 66.6 | [1,775.8, 2,106.7] |
| S=1024 · q25 | FP32 endpoint | 3 | 2,989.9 | 68.3 | [2,827.1, 3,166.6] |
| S=1024 · q50 (representative) | scalar FP16 endpoint | 3 | 2,055.8 | 190.2 | [1,575.2, 2,519.9] |
| S=1024 · q50 (representative) | packed FP16x2 endpoint | 3 | 1,738.9 | 259.0 | [980.5, 2,267.5] |
| S=1024 · q50 (representative) | FP32 endpoint | 3 | 2,596.7 | 126.3 | [2,210.2, 2,837.5] |
| S=2048 · q50 | scalar FP16 endpoint | 3 | 3,020.9 | 100.0 | [2,741.9, 3,238.5] |
| S=2048 · q50 | packed FP16x2 endpoint | 3 | 2,829.7 | 62.6 | [2,679.8, 2,990.8] |
| S=2048 · q50 | FP32 endpoint | 3 | 5,031.6 | 151.0 | [4,680.0, 5,430.3] |
| S=4096 · q25 | scalar FP16 endpoint | 3 | 5,056.1 | 723.2 | [3,206.4, 6,799.7] |
| S=4096 · q25 | packed FP16x2 endpoint | 3 | 5,320.5 | 831.4 | [2,783.2, 6,913.6] |
| S=4096 · q25 | FP32 endpoint | 3 | 6,456.4 | 256.7 | [5,932.6, 7,208.1] |
| S=4096 · q50 | scalar FP16 endpoint | 3 | 4,989.4 | 377.6 | [4,038.6, 5,914.9] |
| S=4096 · q50 | packed FP16x2 endpoint | 3 | 4,797.9 | 371.0 | [3,872.6, 5,716.0] |
| S=4096 · q50 | FP32 endpoint | 3 | 5,979.3 | 201.4 | [5,478.3, 6,478.8] |
| S=512 · q25 | scalar FP16 endpoint | 3 | 2,209.9 | 786.2 | [482.5, 4,388.4] |
| S=512 · q25 | packed FP16x2 endpoint | 3 | 2,131.2 | 127.1 | [1,774.8, 2,406.3] |
| S=512 · q25 | FP32 endpoint | 3 | 2,611.2 | 75.6 | [2,400.8, 2,776.3] |
| S=512 · q50 | scalar FP16 endpoint | 3 | 2,455.6 | 11.9 | [2,425.8, 2,485.1] |
| S=512 · q50 | packed FP16x2 endpoint | 3 | 1,626.8 | 25.4 | [1,553.2, 1,679.6] |
| S=512 · q50 | FP32 endpoint | 3 | 2,089.3 | 69.3 | [1,895.5, 2,240.0] |

## Adaptive decision

`followup_complete_screened_range_not_fresh_extrema_confirmed`; requested/remaining coordinates: `none`.

Temperature is recorded context only. Screened extrema need an independent fresh confirmation before being named a confirmed observed range.
