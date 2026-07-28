# Whole-Softmax precision range analysis

이 값은 complete Softmax forward의 `net pJ/logical output element`다. 기존 EX2 Operand-rate ATC의 pJ/logical exponent result와 합산하거나 비교하지 않는다.

대표값은 사전 고정한 `S=1024, q=50%`이고, best/worst는 screen에서 선택된 관측 범위라 fresh extrema confirmation 전까지 확정값이 아니다.

| policy | best (screened) | representative S1024/q50 | worst (screened) |
|---|---:|---:|---:|
| `fp16_scalar_all` | 2055.763 (s1024_q50) | 2055.763 | 4989.379 (s4096_q50) |
| `fp16x2_all` | 1626.780 (s512_q50) | 1738.945 | 4797.917 (s4096_q50) |
| `fp32_io_fp32_all` | 2089.330 (s512_q50) | 2596.747 | 5979.345 (s4096_q50) |

## Adaptive decision

status: `followup_required`

follow-up coordinates: `s2048_q50, s512_q25, s4096_q25`

온도는 기록 context만이며, 플랫폼 사이의 값은 pool하거나 하나의 순위로 만들지 않는다.
