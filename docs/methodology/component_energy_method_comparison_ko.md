# Component Energy 실험 방법 비교와 해석 가이드

갱신일: 2026-07-14

## 목적

이 문서는 초기 raw sweep과 현재 acceptance-first finalplan의 차이를 설명한다. 현재
실험은 GPU 보드/디바이스 전체 에너지에서 treatment-control 차이를 구하고, NCU로
실제 실행 경로와 traffic denominator를 검증해 component별 **effective
microbenchmark coefficient**를 추정한다. 순수 회로 또는 SRAM bitcell 에너지를 직접
측정하는 실험이 아니다.

전체 구현은 [howitworks.md](howitworks.md), 최종 좌표는
[component_energy_final_experiment_plan_ko.md](component_energy_final_experiment_plan_ko.md),
계산식과 NCU gate는
[ncu_validation_energy_calculation_ko.md](ncu_validation_energy_calculation_ko.md)를
기준으로 한다.

## 초기 방식과 현재 방식

| 항목 | 초기 raw sweep | 현행 component finalplan |
|---|---|---|
| 목적 | 실행 가능한 blocks/SM과 W_SM 영역 탐색 | Tensor/Shared/Global-L1/L2 경로의 유효 계수 추정 |
| 대표 mode | `reg_mma`, `shared_mma`, `l2_mma`, `dram_mma` | 명시적 treatment-control pair |
| 에너지 계산 | mode별 net energy 또는 pJ/FLOP | matched-control energy 차분 |
| memory 분모 | logical/static bytes 중심 | exact-coordinate NCU actual bytes |
| path 판정 | W_SM과 nominal capacity로 추정 | hit rate, access, bytes, spill, stall로 acceptance |
| 최종 지위 | 후보 탐색과 역사적 진단 | 모든 power/NCU/reliability/package gate 통과 시에만 final 후보 |

초기 방식은 sweep 범위를 고르는 데 유효했지만, `W_SM`이 작다고 L1이고 크다고 DRAM이라고
단정할 수는 없었다. 실제 RTX 3090에서 일반 `l2_load_only`는 L1 hit가 높았고,
`shared_load_only`는 bank conflict가 컸다. 현재 방식은 이 실패를 숨기지 않고 NCU에서
reject한다.

과거 상세 표와 auxiliary 결과는
`archive/pre_current_protocol_20260712/docs/methodology/component_energy_method_comparison_full_history_ko.md`에
보존한다.

## 현행 Component Pair

| Component | Treatment | Control | 작업량 정책 | 에너지 분자 | 분모/단위 |
|---|---|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | RF별 dual calibration 후 동일 ITER | 두 net energy 직접 차분 | logical FLOP, pJ/FLOP |
| Shared scalar | `shared_scalar_load_only` | `shared_scalar_addr_only` | dual calibration 후 동일 ITER | 두 net energy 직접 차분 | NCU shared read bytes, pJ/bit |
| Global L1 hit | `global_l1_load_only` | `global_addr_only` | dual calibration 후 동일 ITER | 두 net energy 직접 차분 | NCU L1 request bytes, pJ/bit |
| L2 CG hit | `l2_cg_load_only` | `global_addr_only` | dual calibration 후 동일 ITER | 두 net energy 직접 차분 | NCU L2 read bytes, pJ/bit |
| DRAM CG sanity | `dram_cg_load_only` | `global_addr_only` | dual calibration 후 동일 ITER | 두 net energy 직접 차분 | NCU DRAM bytes, pJ/bit |

Tensor와 모든 memory pair는 `matched_iters_net_energy`와 `iter_ratio=1`이 모두
확인되어야 한다. L2에서 hit rate가 99% 이상이어도 control과 treatment의 ITER가 다르면
같은 작업량의 에너지를 비교한 것이 아니므로 reject한다.

요약하면 L2 CG - address control pair는 동일 ITER의 직접 차분이다.

## Parameter Sweep과 선택 좌표

### 공통 탐색 축

| 실험자가 조절한 값 | 범위/단위 | 관찰한 값 | 목적 |
|---|---|---|---|
| blocks/SM | `1,2,4,8,16,32` blocks/SM 중 profile 허용값 | elapsed, energy, SMID, occupancy/resources | requested grid density와 고정비 amortization 민감도 확인 |
| W_SM | `1 KiB/SM`에서 `128 MiB/SM`까지 2배 sweep | feasibility, hit rate, L1/L2/DRAM bytes | memory hierarchy 후보 영역 탐색 |
| reuse factor | RF `1,2,4,8,16` count | HMMA/logical MMA, pJ/FLOP | Tensor steady-loop 대비 setup/final-store 영향 확인 |
| load repeat | LR `1,2,4,8,16` count | path bytes, stalls, pJ/bit | memory traffic 증가에 따른 유효 계수 안정성 확인 |
| duration/repeats | final target `10 s`, `5 repeats` | net energy, drift, min/median/max | NVML noise floor와 반복 분산 확인 |

한 sweep에서 여러 축을 동시에 바꾸면 어떤 변화가 결과를 만들었는지 구분하기 어렵다.
따라서 같은 component 안에서는 W_SM, blocks/SM, RF/LR을 좌표로 명시하고, NCU도 최종
채택할 exact coordinate에서 수집한다.

### 플랫폼별 현행 범위

| GPU | Energy blocks/SM | Shared W_SM (KiB/SM) | Global L1 W_SM (KiB/SM) | L2 W_SM (KiB/SM) | DRAM W_SM (KiB/SM) |
|---|---|---|---|---|---|
| RTX 3090 | 8,16 | 32,64 | 8,16 | 64 | 8192 |
| V100 | 4,16,32 | 32,64 | 8,16,32 | 32,64 | 8192 |
| A100 | 16,32 | 64,128 | 16,32 | 16,32,64,128 | 8192 |
| H100 | 16,32 | 64,128 | 16,32 | 64,128 | 8192 |

Memory mode의 W_SM은 KiB/SM 단위다. `reg_mma`와 `reg_operand_only`에는 memory
working set이 없으며 현재 CLI의 W_SM=1 KiB는 parser placeholder다. 실제 register
사용량은 ptxas/NCU registers/thread와 실제 resident blocks/SM로 확인한다.

![플랫폼별 blocks/SM sweep](../presentations/assets/platform_blocks_per_sm_sweep.png)

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

## NCU가 검증하는 것

NCU는 에너지를 측정하지 않는다. NCU가 제공하는 것은 treatment/control이 의도한
경로를 사용했는지와 pJ/bit 분모로 쓸 실제 traffic이다.

| Path | 필수 확인 항목 | 통과 의미 | 통과해도 알 수 없는 것 |
|---|---|---|---|
| Tensor | treatment HMMA>0, control workload-proportional HMMA=0, spill/local=0 | no-MMA control 대비 Tensor workload가 존재 | 순수 Tensor Core 회로 에너지 |
| Shared | shared bytes/access/instruction>0, bank conflict와 global leakage 제한 | software-managed shared scalar path | unified L1/shared 전체의 단일 물리 상수 |
| Global L1 | path-specific L1 hit>=95%, L2/DRAM leakage<=1% | global load가 L1 hit 중심 | Shared path와 동일한 instruction/arbitration 비용 |
| L2 CG | L1 hit<=1%, architecture-specific final L2 service>=95%, observed/expected bytes 정합, DRAM-read leakage<=2%. GA100은 source+LTC-fabric logical hit와 native-model coherence 사용 | `.cg` load가 L2 hierarchy에서 완료됨 | L2 SRAM array 단독 에너지; GA100 coefficient는 partition fabric도 포함 |
| External-memory CG read | L1 hit <=1%, final L2 hit <=10%, external read/source >=90%, write/read <=1% | effective GPU-device external-memory read path | HBM/GDDR device-only pJ/bit |

![NCU path별 traffic](../assets/component_energy_method/ncu_path_validation_bytes.png)

Shared와 Global L1은 물리적으로 unified L1/shared subsystem 자원을 일부 공유해도
CUDA address space, instruction, arbitration, bank/cache behavior와 denominator가 다르다.
따라서 두 값은 서로 모순되는 “같은 메모리의 두 물리 상수”가 아니라 서로 다른
microbenchmark path coefficient다.

GA100도 direct source hit와 native lookup hit의 분모가 다르다. 첫 partition miss가
LTC fabric을 통해 다른 partition에서 hit할 수 있으므로 두 값에 동일한 95% threshold를
적용하지 않는다. `l2_logical_read_hit_rate_pct`가 final-service primary gate이고,
source/fabric/native/DRAM-read counter가 이를 교차검증한다.

## Effective Coefficient 계산

모든 현행 final pair는 동일 ITER를 쓴다.

```text
ITER_treatment = ITER_control = N
delta_E_J = net_E_treatment_J(N) - net_E_control_J(N)
```

계수는 다음과 같다.

```text
pJ/FLOP = delta_E_J * 1e12 / logical_FLOP
pJ/byte = delta_E_J * 1e12 / NCU_actual_bytes
pJ/bit  = pJ/byte / 8
```

분자가 작다는 것은 control 대비 추가 board-level energy가 작다는 뜻이다. 분모가 크면
같은 에너지가 많은 operation/traffic에 분산되어 coefficient가 작아진다. 따라서 분자와
분모의 provenance를 함께 보지 않고 숫자 크기만 비교하면 안 된다.

## 현재 결과 상태

2026-07-14 기준, 현행 protocol로 Tensor/Shared/Global-L1/L2를 모두 재실행한 RTX 3090
전체 component table은 없다.

| 항목 | 값 | 단위 | 상태 |
|---|---:|---|---|
| RTX 3090 Tensor fixed-RF v2 median | 2.252501 | pJ/FLOP | superseded historical; accumulator 정체 가능성 때문에 v4 power 재실행 전 인용 금지 |
| RTX 3090 Tensor fixed-RF v4 | - | pJ/FLOP | RF1-16 runtime NCU/FLOP path 검증 완료, board-energy 미실행 |
| RTX 3090 Shared/Global-L1/L2 과거 계수 | 문서상 historical 값 | pJ/bit | current control/schema gate 미충족, final 인용 금지 |
| RTX 3090 external-memory observation | 25.510 | effective pJ/bit | 사용자 전달 historical candidate; strict raw package 재실행 필요 |
| A100 external-memory observation | 11.925 | effective pJ/bit | 사용자 전달 historical candidate; 현 저장소에서 원본 package 독립 재계산 불가 |
| V100 external-memory observation | 8.131 | effective pJ/bit | 사용자 전달 historical candidate; 현 저장소에서 원본 package 독립 재계산 불가 |
| V100/A100/H100 전체 계수 | 문서상 명확한 accepted package 없음 | - | 각 target node에서 재실행 필요 |

![External-memory effective path와 memory-device reference의 scope 비교](../assets/component_energy_method/external_memory_scope_comparison.png)

위 그림의 A 패널은 NVML GPU-device 전체 energy 차분을 NCU external
read bit로 나눈 관측값, B는 문헌의 transaction/system-path 값, C는
memory-device/access model이다. 패널 간 간격을 controller/PHY의 순수
energy로 차분하면 안 된다. 상세 재실험 설계는
[`external_memory_read_path_experiment_design_ko.md`](external_memory_read_path_experiment_design_ko.md)를 따른다.

과거 coefficient가 문헌의 계층 순서와 비슷하더라도 current protocol gate를 대신하지
않는다. 특히 2026-07-08 Global L1/L2는 `clocked_empty` control을 사용했고,
V100의 구형 L2 run은 NCU path가 맞아도 ITER가 달라 음수였다. 둘 다 현행 final 값이
아니다.

## 방법별 장단점

| 방법 | 장점 | 한계/오해하기 쉬운 점 |
|---|---|---|
| Wide raw sweep | 실행 가능 영역과 큰 추세를 빠르게 찾음 | raw `*_mma` 차이는 component 단독 에너지가 아님 |
| Matched-control | 공통 loop/주소/제어 비용 일부 상쇄 | control이 완전히 동일하지 않으며 drift와 weak signal이 남음 |
| Equal-ITER pair | 같은 logical work의 직접 energy 차분 | 두 mode 시간이 달라 power state가 변할 수 있어 control floor와 반복이 필요 |
| NCU path acceptance | mode 이름이 아니라 실제 traffic으로 경로 판정 | 별도 replay run이며 에너지 분자를 직접 측정하지 않음 |
| NCU actual denominator | expected bytes보다 실제 transaction에 가까움 | request/sector/byte 단위와 metric availability가 GPU별로 다름 |
| Strict/package audit | 누락 evidence와 stale 결과 승격을 차단 | gate 통과는 pure silicon-level energy 보증이 아님 |

## 보고할 때 반드시 포함할 것

| 구분 | 필수 내용과 단위 |
|---|---|
| GPU/profile | GPU name, chip, SM count (SMs), L2 (MiB), shared allocation (KiB/SM) |
| Sweep | W_SM (KiB/SM), blocks/SM, RF/LR (count), duration (s), repeats (count) |
| Power | energy source, integration method, measurement scope, net energy (J) |
| NCU | hit rate (%), access unit, shared/L1/L2/DRAM bytes (B), spill/local (B), stall signal |
| Pair | treatment, control, ITER (count), pair basis, accepted/rejected reason |
| 결과 | pJ/FLOP 또는 pJ/bit, min/median/mean/max, valid/invalid rows |

숫자를 보고할 때는 “NCU로 path와 denominator가 검증된 workload-dependent
GPU/device-level effective microbenchmark coefficient”라고 표현한다.
