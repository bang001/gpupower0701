# Component Energy 최종 실험 계획

작성일: 2026-07-05

## 1. 실험 목표

이 실험의 목표는 RTX 3090과 A100 계열 GPU에서 다음 경로의 **board-level effective energy coefficient**를 합리적으로 분리하는 것이다.

| 목표 항목 | 목표 단위 | 채택 가능한 해석 |
|---|---:|---|
| Tensor MMA incremental | pJ/FLOP | no-MMA register/control 대비 FP16 WMMA 추가 에너지 |
| Register operand/control | pJ/reg-op 또는 진단값 | spill-free register/control workload의 board-level proxy |
| Shared memory scalar path | pJ/bit | shared-memory load instruction path의 effective traffic energy |
| Global L1 hit path | pJ/bit | global load가 L1 hit로 끝나는 path의 effective traffic energy |
| L2 hit path | pJ/bit | L1을 배제하고 L2 hit로 끝나는 path의 effective traffic energy |
| DRAM streaming path | pJ/bit | 필수 목표가 아니라 L2 분리 sanity check |

중요한 제한은 다음과 같다.

- NVML energy는 보드/디바이스 전체 에너지다. Tensor Core, register file, scheduler, LSU, interconnect, cache, memory controller, DRAM, clock/power-state 변화가 함께 들어간다.
- 따라서 최종 보고서는 “pure physical bitcell energy”가 아니라 “NCU로 path가 검증된 microbenchmark의 effective coefficient”로 쓴다.
- 계수는 NCU path 검증과 energy 차분/회귀 검증을 모두 통과해야 후보값으로 채택한다.

## 2. 아키텍처 기준

사용자가 지정한 NVIDIA whitepaper를 기준으로 capacity와 경로를 분리한다.

| GPU | Register file / SM | L1/shared / SM | L2 | Memory | 실험 설계 영향 |
|---|---:|---:|---:|---|---|
| RTX 3090, GA102 | 256 KiB | 128 KiB combined | 6 MiB | GDDR6X | L2/SM이 작고 L1/shared와 겹치므로 W_SM만으로 L2-only를 만들기 어렵다. L2는 `l2_cg_load_only`를 우선 사용한다. |
| A100, GA100 | 256 KiB | 192 KiB combined, shared allocation 최대 164 KiB | 40 MiB | HBM2 | capacity 기반 L2-hit 창을 만들 수 있다. `l2_load_only`와 `l2_cg_load_only`를 모두 검증한다. |

주의: CUDA에서 설정 가능한 dynamic shared memory 한계와 whitepaper의 물리 combined L1/shared capacity는 같은 값이 아닐 수 있다. 실험 채택은 capacity 계산이 아니라 NCU hit/access counter를 우선한다.

## 3. 기존 결과의 냉정한 판정

| 기존 항목 | 판정 | 이유 | 새 처리 |
|---|---|---|---|
| Tensor `0.146 pJ/FLOP` | 후보값 | HMMA와 spill-free는 확인됐지만 no-MMA control 차분이며 negative row가 있었다. | 반복 수를 늘리고 reuse 축별 안정성을 다시 본다. |
| Global L1 `0.449 pJ/bit` | 후보값 미만 | L1 hit path는 맞지만 energy row 6개 중 2개가 음수였다. | 음수 row가 사라지는지 seconds/repeats를 늘려 재실험한다. |
| L2 `0.798 pJ/bit` | 후보값 | CG L2 path는 맞지만 long scoreboard가 크고 1개 음수 row가 있었다. | L2는 stall을 보고하고, pJ/bit를 L2 SRAM 단독값으로 부르지 않는다. |
| DRAM `4.48 pJ/bit` | sanity 후보 | RTX 3090은 GDDR6X라 HBM2 physical 3.9 pJ/bit와 직접 비교하면 안 된다. | L2/DRAM hierarchy sanity check로만 둔다. |
| Register direct `263 pJ/update` | 폐기 | scalar ALU, dependency, scheduler/control, active power를 작은 update 수로 나눈 값이다. | pure register-file energy로 쓰지 않는다. |

## 4. 실험 분리 원칙

### 4.1 NCU path acceptance

energy 계수는 아래 NCU 기준을 통과한 mode만 사용한다.

| Path | mode | NCU 채택 기준 |
|---|---|---|
| Tensor | `reg_mma` | HMMA instruction > 0, spill/local memory 0, L1/L2/DRAM traffic이 작음 |
| Tensor control | `reg_operand_only` | HMMA 0, spill/local memory 0, register/control traffic만 존재 |
| Shared scalar | `shared_scalar_load_only` | shared bytes/accesses 존재, expected shared bytes와 같은 order, bank conflict 0 또는 매우 낮음 |
| Global L1 | `global_l1_load_only` | L1 hit >= 95%, L2/L1 byte ratio <= 1%, DRAM/L1 byte ratio <= 1% |
| L2 hit | `l2_cg_load_only` 또는 A100 capacity `l2_load_only` | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 byte ratio <= 2% |
| DRAM sanity | `dram_cg_load_only` | L1 hit <= 1%, L2 hit <= 5%, DRAM bytes가 충분히 큼 |

NCU 보고 표에는 반드시 단위를 적는다.

| 지표 | 단위 |
|---|---|
| L1 hit rate | % |
| L2 hit rate | % |
| Shared accesses | access count |
| L1 accesses | requests 또는 sectors |
| L2 accesses | sectors |
| DRAM accesses | sectors |
| Shared/L1/L2/DRAM bytes | bytes |
| Stall long scoreboard | % |
| Stall short scoreboard / wait | % |

### 4.2 Energy coefficient

Energy run은 NCU 없이 실행한다. 동일 mode/config의 반복값에서 median을 쓰고, control은 power로 환산해 elapsed를 맞춘다.

```text
delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s
coefficient = delta_E_J / denominator
```

| Component | numerator | control | denominator |
|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | FLOP |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes 우선, expected shared bytes fallback |
| Global L1 path | `global_l1_load_only` | `clocked_empty` | NCU L1 bytes 우선, expected L1 bytes fallback |
| L2 hit path | `l2_cg_load_only` | `clocked_empty` | NCU L2 bytes 우선, expected L2 bytes fallback |
| DRAM sanity path | `dram_cg_load_only` | `clocked_empty` | NCU DRAM bytes 우선, expected DRAM bytes fallback |

음수 coefficient는 component energy로 채택하지 않는다. 단순히 0으로 클리핑하지 않고 `not_identified_or_control_failed`로 기록한다.

## 5. 이번 RTX 3090 실행 계획

이번 실행은 “최종 논문값”이 아니라 final-quality로 가기 위한 강한 재현성 점검이다. 목표는 음수 row가 줄어드는지, NCU path 검증과 energy 계수가 같은 방향인지 확인하는 것이다.

### 5.1 NCU 대표 검증

| Component | blocks/SM | W_SM (KiB) | factor | 이유 |
|---|---:|---:|---:|---|
| Tensor | 16 | 2048 | reuse 4 | B16 full occupancy에서 HMMA/spill 확인 |
| Shared scalar | 16 | 64 | load_repeat 4 | shared bytes와 bank conflict 확인 |
| Global L1 | 16 | 16 | load_repeat 4 | L1 hit path 확인 |
| L2 hit | 16 | 64 | load_repeat 4 | RTX 3090은 CG path로 L1을 배제 |
| DRAM sanity | 16 | 8192 | load_repeat 4 | L2 miss/DRAM streaming 확인 |

### 5.2 Energy 재실험

| Component | modes | blocks/SM | W_SM (KiB) | factor sweep | seconds (s) | repeats |
|---|---|---:|---:|---:|---:|---:|
| Tensor | `reg_operand_only`, `reg_mma` | 16 | 2048 | reuse 1,2,4,8,16 | 5 | 3 |
| Shared scalar | `clocked_empty`, `shared_scalar_load_only` | 16 | 64 | load_repeat 1,2,4,8,16 | 5 | 3 |
| Global L1 | `clocked_empty`, `global_l1_load_only` | 16 | 16,64 | load_repeat 1,2,4,8,16 | 5 | 3 |
| L2 hit | `clocked_empty`, `l2_cg_load_only` | 16 | 64 | load_repeat 1,2,4,8,16 | 5 | 3 |
| DRAM sanity | `clocked_empty`, `dram_cg_load_only` | 16 | 8192 | load_repeat 1,4,16 | 5 | 3 |

성공 기준:

| 기준 | 통과 조건 |
|---|---|
| execution | 모든 row `smid_histogram_ok=true`, elapsed >= 4 s |
| Tensor | reuse sweep에서 음수 coefficient 0 또는 원인 설명 가능 |
| Shared scalar | 모든 load_repeat에서 양수, NCU shared path accepted |
| Global L1 | 음수 row가 남으면 final에서 제외 또는 control 재설계 |
| L2 | L2 hit >= 95%, DRAM/L2 <= 2%, long scoreboard를 결과 표에 포함 |
| DRAM | sanity check로만 사용, physical DRAM energy라고 쓰지 않음 |

## 6. A100 확장 계획

A100 노드에서는 RTX 3090 결과를 이식하지 않고 같은 acceptance-first 절차를 반복한다.

| Step | A100 확인 내용 |
|---|---|
| preflight | profile `a100`, runtime SM 수, NVML energy support, NCU metric support |
| shared/L1 | `shared_scalar_load_only` W_SM 64/128 KiB, `global_l1_load_only` W_SM 16/32 KiB |
| L2 capacity | `l2_load_only` W_SM 192/256/320 KiB에서 L1 hit 낮고 L2 hit 높은지 확인 |
| L2 control | `l2_cg_load_only`와 capacity L2 결과를 비교 |
| Tensor | `reg_mma - reg_operand_only`, blocks/SM 16/32, reuse 1-16 |
| Register | ptxas footprint와 NCU spill/local 0 확인. pure RF energy로 주장하지 않음 |

## 7. 최종 보고서 형식

최종 보고서는 아래 표를 반드시 포함한다.

| 표 | 필수 열 |
|---|---|
| GPU architecture | GPU, SM, register/SM (KiB), L1/shared (KiB), L2 (MiB), memory type, source |
| Sweep 조건 | mode, W_SM (KiB), blocks/SM, active_SM (SM), reuse_factor, load_repeat, seconds (s), repeats |
| NCU validation | L1 hit (%), L2 hit (%), shared accesses, L1 bytes, L2 bytes, DRAM bytes, stall_long_scoreboard (%) |
| Acceptance | mode, component, accepted/rejected, reason |
| Energy coefficients | component/path, estimate, unit, min, median, max, rows used, invalid rows, status |
| 제한 | board-level effective coefficient, not pure physical energy |

## 8. 이번 실행 후 판정 언어

| 상태 | 보고 문구 |
|---|---|
| NCU path accepted, energy 양수/안정 | `accepted candidate` |
| NCU path accepted, energy 일부 음수/편차 큼 | `path accepted, coefficient provisional` |
| NCU path rejected | `rejected for component coefficient` |
| Register proxy | `register/control diagnostic only` |
| DRAM | `sanity path only on RTX 3090 GDDR6X` |

이 기준을 통과하지 못한 수치는 문서에 남기되, component별 최종 pJ 표에는 넣지 않는다.
