# RTX 3090 Component Guarantee Audit

작성 시점: 2026-07-05

## 결론

현재 실험에서 높은 guarantee를 줄 수 있는 것은 **pJ 계수 자체**가 아니라 **NCU로 검증된 실행 path**다. pJ 계수는 아직 final 값이 아니다. `seconds=10`, `repeats>=3`, NCU actual-byte join, negative row 처리 기준이 추가되어야 한다.

## Guarantee Table

| component | representative mode | path guarantee | coefficient guarantee | current estimate | unit | 이유 |
|---|---|---|---|---:|---|---|
| Tensor MMA incremental | `reg_mma - reg_operand_only` | high | medium | 0.146 | pJ/FLOP | HMMA count와 spill-free는 확인됨. 다만 7개 reuse 중 1개 negative |
| Shared/L1 scalar path | `shared_scalar_load_only - clocked_empty` | high | medium | 0.223 | pJ/bit | shared bytes 기대치 일치, bank conflict 0, 6/6 positive. 단 min-max 편차 큼 |
| Global L1 hit path | `global_l1_load_only - clocked_empty` | high | low-medium | 0.449 | pJ/bit | L1 hit 99.999%로 path는 좋지만 6개 중 2개 negative |
| L2 hit path | `l2_cg_load_only - clocked_empty` | high | medium-low | 0.798 | pJ/bit | L1 hit 약 0%, L2 hit 약 99.93%. 6개 중 1개 negative, long scoreboard 큼 |
| DRAM streaming path | `dram_cg_load_only - clocked_empty` | high | low-medium | 4.48 | pJ/bit | DRAM traffic은 명확하지만 3 rows only, RTX 3090 GDDR6X에서 physical DRAM energy로 해석 금지 |

## High-Guarantee Claims That Are Safe

| claim | guarantee | 근거 |
|---|---|---|
| `reg_mma`는 Tensor path를 실제 수행했다 | high | HMMA instruction 약 2.624e8, spill/local 0 |
| `shared_scalar_load_only`는 clean shared path다 | high | shared bytes 약 5.374e11 B, bank conflicts 0, shared inst 약 4.198e9 |
| `global_l1_load_only`는 L1-hit path다 | high | L1 hit 약 99.999%, L2/DRAM pollution 낮음 |
| `l2_cg_load_only`는 L2-hit path다 | high | L1 hit 약 0%, L2 hit 약 99.93%, DRAM/L2 낮음 |
| `dram_cg_load_only`는 DRAM streaming sanity path다 | high | L1/L2 hit 낮고 DRAM bytes가 L2 bytes와 같은 order |

## Claims That Are Not Safe Yet

| claim | decision | 이유 |
|---|---|---|
| Tensor = 0.146 pJ/FLOP final | not safe | 1개 negative row, 2 repeats 수준, WMMA control 차분 |
| L1 = 0.449 pJ/bit final | not safe | 2 negative rows |
| L2 = 0.798 pJ/bit final | not safe | long scoreboard가 매우 크고 1 negative row |
| DRAM = 4.48 pJ/bit physical DRAM energy | not safe | RTX 3090 GDDR6X physical value가 아니라 effective board-level streaming delta |
| Shared/L1 = 0.223 pJ/bit final | not safe | path는 좋지만 coefficient min-max가 큼 |

## Errors Or Risky Interpretations Found

| item | issue | fix |
|---|---|---|
| HBM2 comparison in RTX 3090 report | RTX 3090은 GDDR6X이므로 HBM2 3.9 pJ/bit와 직접 정합한다고 쓰면 안 됨 | report 문구 수정 |
| register 263 pJ/update | direct division 값이며 register energy가 아님 | rejected as register energy로 수정 |
| static expected bytes | energy rows는 NCU actual bytes가 join된 값이 아님 | final 전 actual-byte join 필요 |
| `clocked_empty` control | 일부 component에서 negative row 발생 | same-duration/matched control 개선 필요 |
| NCU representative-only validation | energy sweep의 모든 W/load_repeat row를 직접 검증한 것은 아님 | final matrix에 NCU sidecar 확장 필요 |

## Current Ranking

현재 가장 보수적으로 믿을 수 있는 순서는 다음과 같다.

```text
path guarantee:
shared_scalar ~= L2 ~= DRAM ~= Tensor ~= global_L1

coefficient guarantee:
shared_scalar > Tensor ~= DRAM > L2 > global_L1
```

단, 이 ranking은 현재 RTX 3090 1차 반복 실험에 한정된다.
