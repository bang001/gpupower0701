# NCU 검증과 pJ 계산 보고서

작성일: 2026-07-07

## 핵심 요약

이 실험에서 Nsight Compute(NCU)는 component energy를 직접 측정하지 않는다. NCU의 역할은 다음 두 가지다.

| 역할 | 의미 |
|---|---|
| Path validation | 해당 kernel이 의도한 Tensor, shared, L1, L2, DRAM 경로를 실제로 사용했는지 확인한다. |
| Denominator validation | memory path의 pJ/byte 또는 pJ/bit 계산에 사용할 실제 traffic byte를 확인하거나 보정한다. |

에너지 분자 `J`는 NVML energy run에서 얻는다. NCU는 분자에 쓰지 않는다. 따라서 최종값은 다음처럼 표현해야 한다.

```text
NCU로 path와 denominator가 검증된 board-level effective microbenchmark coefficient
```

다음 표현은 피해야 한다.

```text
NCU가 측정한 L1 energy
순수 Tensor Core energy
순수 SRAM/HBM bitcell energy
```

## 전체 계산 흐름

```text
1. NVML energy run
   - NCU 없이 kernel 실행
   - mode별 net_E_J 측정

2. NCU sidecar run
   - 별도 실행에서 NCU counter 수집
   - hit rate, access count, bytes, stall, spill, Tensor instruction 확인

3. Path acceptance
   - 의도한 경로가 counter로 확인된 row만 accepted

4. Matched-control 계산
   - treatment energy에서 control energy rate를 같은 시간만큼 차감

5. pJ/FLOP, pJ/byte, pJ/bit 계산
   - Tensor는 logical FLOP denominator 사용
   - memory path는 NCU actual bytes denominator 우선 사용
```

## NCU로 검증한 항목

| Component/path | NCU에서 확인한 항목 | 채택 의도 |
|---|---|---|
| Tensor MMA incremental | Tensor/HMMA instruction, spill/local memory, L1/L2/DRAM traffic | `reg_mma`가 실제 Tensor instruction을 실행하고, control에는 Tensor instruction이 없어야 한다. |
| Shared scalar path | shared accesses, shared bytes, shared instruction count, bank conflict | shared memory scalar load path가 충분히 발생하고 bank conflict가 낮아야 한다. |
| Global L1-hit path | L1 hit rate, L1 bytes, L2 bytes, DRAM bytes | global load가 L1 hit 중심이어야 하며 L2/DRAM leakage가 낮아야 한다. |
| L2 CG hit path | L1 hit rate, L2 hit rate, L2 bytes, DRAM bytes | L1은 사실상 우회되고 L2 hit가 지배적이어야 한다. |
| DRAM CG streaming path | DRAM bytes, L1/L2 hit rate, L2 bytes 대비 DRAM bytes | DRAM streaming sanity check로만 사용한다. |
| 공통 | long/short scoreboard stall, wait stall, SMID histogram, spill/local | stall 또는 placement 문제를 보고서에 같이 기록한다. |

## Path acceptance 기준

현재 `scripts/analyze_ncu_path_acceptance.py`는 mode별로 다음 기준을 적용한다.

| Path | accepted 조건 요약 |
|---|---|
| Tensor | `reg_mma`에서 Tensor/HMMA instruction > 0, spill/local 0, memory traffic이 threshold 이하 |
| Tensor control | `reg_operand_only`에서 Tensor/HMMA instruction = 0, spill/local 0 |
| Shared scalar | shared bytes/accesses > 0, shared instruction 존재, bank conflict ratio 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 | L1 hit >= 95%, L2/L1 byte ratio <= 1%, DRAM/L1 byte ratio <= 1% |
| L2 CG | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 byte ratio <= 2% |
| DRAM sanity | L1 hit <= 1%, L2 hit <= 5%, DRAM bytes dominant |

이 기준을 통과하지 못한 row는 pJ 값이 양수여도 최종 component coefficient로 채택하지 않는다.

## Memory path pJ/byte와 pJ/bit 계산

Memory path는 다음 pair를 사용한다.

| Component/path | treatment | control | denominator |
|---|---|---|---|
| Shared scalar | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes |
| Global L1-hit | `global_l1_load_only` | `clocked_empty` | NCU L1 bytes |
| L2 CG hit | `l2_cg_load_only` | `clocked_empty` | NCU L2 bytes |
| DRAM CG streaming | `dram_cg_load_only` | `clocked_empty` | NCU DRAM bytes |

에너지 차분은 elapsed time 차이를 보정한다.

```text
control_power_W = E_control_J / t_control_s
control_energy_scaled_J = control_power_W * t_treatment_s
delta_E_J = E_treatment_J - control_energy_scaled_J
```

그 다음 coefficient를 계산한다.

```text
pJ/byte = delta_E_J * 1e12 / denominator_bytes
pJ/bit  = pJ/byte / 8
```

초기 expected byte는 코드에서 다음처럼 계산된다.

```text
expected_bytes =
  active_SM * blocks_per_SM * ITER * load_repeat * 1024 bytes
```

하지만 최종 memory coefficient에서는 expected byte를 그대로 쓰지 않는다. NCU sidecar에서 얻은 actual bytes로 scale을 만든다.

```text
NCU scale = NCU actual bytes / expected bytes
final denominator bytes = energy-run expected bytes * NCU scale
```

보고서의 `denominator_source`는 다음처럼 해석한다.

| denominator_source | 의미 | 채택 수준 |
|---|---|---|
| `ncu_actual_exact` | mode, W_SM, blocks/SM, active_SM, reuse/load_repeat까지 같은 NCU row 사용 | 가장 좋음 |
| `ncu_actual_same_working_set` | mode, W_SM, blocks/SM, active_SM은 같고 factor는 대표 NCU scale 사용 | 현재 finalplan에서 사용한 주 방식 |
| `expected_no_ncu_match` | NCU actual denominator 없음 | 최종 pJ/byte 채택 금지 |

## Tensor pJ/FLOP 계산

Tensor는 memory path처럼 pJ/byte가 아니라 pJ/FLOP로 계산한다. 사용 pair는 다음이다.

| 항목 | mode | 의미 |
|---|---|---|
| treatment | `reg_mma` | register fragment를 준비하고 `mma_sync`를 반복 실행 |
| control | `reg_operand_only` | 같은 register fragment 구조를 쓰지만 `mma_sync`는 실행하지 않음 |

Tensor incremental energy는 다음처럼 계산한다.

```text
control_power_W = E_reg_operand_only_J / t_reg_operand_only_s
control_energy_scaled_J = control_power_W * t_reg_mma_s
delta_E_J = E_reg_mma_J - control_energy_scaled_J
```

FLOP denominator는 logical MMA 정의에서 나온다.

```text
N_MMA = active_SM * blocks_per_SM * ITER * reuse_factor
FLOP  = N_MMA * 8192
```

`8192 FLOP`는 FP16 WMMA `m16n16k16` 한 번을 logical GEMM 기준으로 본 값이다.

```text
16 * 16 * 16 multiply-add = 4096 FMA = 8192 FLOP
```

최종 Tensor coefficient는 다음과 같다.

```text
pJ/FLOP = delta_E_J * 1e12 / FLOP
```

예시 row:

| 항목 | 값 |
|---|---:|
| pair | `reg_mma_minus_reg_operand_only` |
| delta_E_J | 53.2879 J |
| denominator | 3.63176e14 FLOP |
| coefficient | 0.146727 pJ/FLOP |

계산:

```text
53.2879 * 1e12 / 3.63176e14 = 0.1467 pJ/FLOP
```

최종 RTX 3090 보고서에서는 여러 reuse row의 accepted candidate를 요약해 Tensor median을 약 `0.168 pJ/FLOP`로 기록했다.

## Tensor에서 NCU의 역할

Tensor pJ/FLOP의 분모는 NCU byte가 아니라 logical FLOP다. 따라서 Tensor에서 NCU는 denominator를 만드는 도구가 아니라, 다음 조건을 검증하는 도구다.

| 확인 | 이유 |
|---|---|
| `reg_mma`에서 Tensor/HMMA instruction > 0 | 실제 Tensor path가 실행됐는지 확인 |
| `reg_operand_only`에서 Tensor/HMMA instruction = 0 | control이 no-MMA control인지 확인 |
| spill/local memory = 0 | register spill로 L2/DRAM traffic이 섞이는 것을 방지 |
| L1/L2/DRAM traffic이 작음 | Tensor coefficient가 memory traffic에 오염되지 않았는지 확인 |

따라서 Tensor 결과는 다음처럼 써야 한다.

```text
reg_operand_only 대비 reg_mma의 effective MMA incremental cost
```

다음처럼 쓰면 안 된다.

```text
순수 Tensor Core transistor-level energy
```

## RTX 3090 finalplan 예시

현재 RTX 3090 finalplan matched-control 보고서의 요약은 다음과 같다.

| Component/path | median | unit | median pJ/bit | 해석 |
|---|---:|---|---:|---|
| Tensor MMA incremental | 0.168 | pJ/FLOP | - | no-MMA register/control 대비 WMMA 추가분 |
| Shared scalar path | 2.164 | pJ/byte | 0.271 | NCU shared bytes 기준 effective path coefficient |
| Global L1-hit path | 1.251 | pJ/byte | 0.156 | NCU L1 bytes 기준 effective path coefficient |
| L2 CG hit path | 9.405 | pJ/byte | 1.176 | NCU L2 bytes 기준 effective path coefficient |
| DRAM CG streaming path | 32.048 | pJ/byte | 4.006 | DRAM streaming sanity coefficient |

이 표는 순수 회로 에너지 표가 아니다. GPU board-level energy, control 차분, NCU denominator가 결합된 microbenchmark coefficient 표다.

## A100/V100/H100 적용 시 주의

NCU denominator scale과 path acceptance는 GPU마다 다시 생성해야 한다. RTX 3090의 NCU scale이나 accepted row를 A100, V100, H100에 그대로 적용하면 안 된다.

| GPU | 반드시 다시 확인할 항목 |
|---|---|
| A100 | `sm_80`, `target_profile=a100`, `NCU_CHIP=ga100`, runtime active SM, L2 40 MiB, shared allocation 164 KiB/SM |
| V100 | `sm_70`, `target_profile=v100`, `NCU_CHIP=gv100` 지원 toolchain, Tensor metric 이름 호환성 |
| H100 | `sm_90`, `target_profile=h100`, `NCU_CHIP=gh100`, WMMA compatibility path와 Hopper-native WGMMA/TMA path 구분 |

A100에서 결과가 좋지 않으면 먼저 다음을 확인한다.

```text
active_SM=82
target_profile=rtx3090
chip=ga102
cuda_arch=86
L2=6 MiB
max blocks/SM=16
```

이 값이 A100 run 또는 analysis filter에 섞인 row는 최종 보고에서 reject해야 한다.

## 결론

NCU 검증은 “에너지를 직접 측정하는 단계”가 아니라 “path와 denominator를 검증하는 단계”다. 최종 pJ 값은 NVML energy 차분과 NCU traffic 검증을 결합한 값이다.

가장 안전한 한 문장 요약은 다음이다.

```text
본 실험의 pJ/FLOP, pJ/byte, pJ/bit 값은 NVML board-level energy를 matched-control로 차분하고, NCU로 경로와 traffic denominator를 검증한 effective microbenchmark coefficient다.
```
