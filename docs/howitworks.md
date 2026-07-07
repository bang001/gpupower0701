# How It Works: Component Energy Microbenchmark

작성일: 2026-07-02
최종 업데이트: 2026-07-07

이 문서는 현재 코드 기준으로 GPU component energy 실험이 어떻게 동작하는지 설명한다. 예전 문서에는 `shared_mma`, `l2_mma`, `dram_mma` 중심의 초기 탐색 설명이 많이 섞여 있었지만, 현재 최종 해석은 **acceptance-first finalplan**을 기준으로 한다.

핵심은 다음 한 문장이다.

```text
이 실험의 pJ/FLOP, pJ/byte, pJ/bit 값은 NVML board-level energy를
matched-control로 차분하고, NCU로 path와 traffic denominator를 검증한
effective microbenchmark coefficient다.
```

순수 Tensor Core 회로 에너지, 순수 register-file 에너지, 순수 SRAM/HBM bitcell 에너지를 직접 측정하는 실험이 아니다.

## 1. 실험 목적

이 저장소의 목적은 GPU 전체 전력 측정값에서 다음 경로의 **effective energy coefficient**를 합리적으로 분리해 보는 것이다.

| 목표 component/path | 목표 단위 | 현재 코드에서 채택 가능한 해석 |
|---|---:|---|
| Tensor MMA incremental | pJ/FLOP | no-MMA register/control 대비 FP16 WMMA/HMMA 추가 에너지 |
| Shared memory scalar path | pJ/byte, pJ/bit | shared-memory scalar load instruction path의 effective traffic energy |
| Global L1 hit path | pJ/byte, pJ/bit | global load가 L1 hit로 끝나는 path의 effective traffic energy |
| L2 hit path | pJ/byte, pJ/bit | L1을 배제하거나 낮춘 L2-hit transaction path의 effective traffic energy |
| DRAM streaming sanity path | pJ/byte, pJ/bit | DRAM streaming이 실제로 보이는지 확인하는 hierarchy sanity coefficient |
| Register/control | pJ/reg-op 또는 진단값 | pure register energy가 아니라 no-MMA control/proxy |

이 목적을 달성하기 위해 실험은 세 가지를 함께 사용한다.

| 방법 | 역할 | 왜 필요한가 |
|---|---|---|
| Parameter sweep | `blocks/SM`, `W_SM`, `reuse_factor`, `load_repeat`를 바꿔 path가 분리되는 조건을 찾음 | GPU 구조마다 L1/shared/L2/DRAM 크기와 behavior가 다르기 때문 |
| Matched-control 차분 | treatment energy에서 control energy rate를 같은 시간만큼 빼서 incremental energy를 계산 | scheduler/loop/idle 같은 공통 비용을 일부 제거하기 위해 |
| NCU path validation | L1/L2/DRAM/shared bytes, hit rate, Tensor instruction, spill, stall을 확인 | mode 이름만으로는 실제 경로를 보장할 수 없기 때문 |

## 2. 현재 최종 실험 축

현재 finalplan에서 component는 다음 pair로 본다.

| 실험 축 | treatment / control | 의미 | 최종 단위 |
|---|---|---|---|
| Tensor | `reg_mma - reg_operand_only` | FP16 WMMA/HMMA incremental cost 후보 | pJ/FLOP |
| Shared scalar | `shared_scalar_load_only - clocked_empty` | shared-memory scalar load path | pJ/byte, pJ/bit |
| Global L1 | `global_l1_load_only - clocked_empty` | global load가 L1 hit로 끝나는 path | pJ/byte, pJ/bit |
| L2 | `l2_cg_load_only - clocked_empty` | L1을 배제한 L2-hit path | pJ/byte, pJ/bit |
| L2 capacity diagnostic | `l2_load_only - clocked_empty` | A100처럼 L2가 큰 GPU에서 capacity 기반 L2 후보와 CG L2를 비교 | 현재는 주로 NCU 비교/진단 |
| DRAM | `dram_cg_load_only - clocked_empty` | DRAM streaming sanity path | pJ/byte, pJ/bit 후보 |

중요한 현재 코드 기준:

- `scripts/plan_platform_component_experiment.py`는 `tensor`, `shared`, `l1`, `l2`, `dram` energy CSV를 나누어 생성한다.
- `scripts/analyze_matched_control_energy.py`의 기본 final pair는 `l2_cg_load_only` 기반 L2 coefficient를 계산한다.
- A100에서 `l2_load_only`도 같이 실행할 수 있지만, 이 mode는 먼저 NCU에서 L1 hit가 낮고 L2 hit가 높은지 확인해야 한다. 별도 최종 coefficient로 쓰려면 analyzer pair 정의가 추가로 필요하다.
- `shared_mma`, `l2_mma`, `dram_mma`는 여전히 코드에 있지만 현재 최종 component coefficient의 primary pair가 아니다. 보조 진단 또는 과거 탐색용으로 본다.

## 3. 전체 실행 흐름

전체 실험은 energy run과 NCU run을 분리한다. NCU replay는 kernel 실행을 바꿀 수 있으므로 NCU에서 나온 energy를 최종 pJ 분자로 쓰지 않는다.

```mermaid
flowchart TD
  A[문서/플랫폼 확인] --> B[build/preflight]
  B --> C[energy sweep<br/>NCU 없이 NVML energy 측정]
  C --> D[NCU sidecar<br/>counter만 수집]
  D --> E[path acceptance<br/>의도한 경로인지 판정]
  C --> F[matched-control analysis<br/>energy 차분]
  E --> F
  F --> G[accepted coefficient table]
  E --> H[rejected/provisional row 기록]
```

| 단계 | 대표 script | 산출물 | 핵심 판정 |
|---|---|---|---|
| preflight | `scripts/preflight_gpu_support.py` | `results/summary/*_preflight.md` | GPU profile, CC, SM 수, NVML, NCU 상태 확인 |
| energy sweep | `scripts/run_component_regression_sweep.py` | `results/raw/*_component_finalplan_*.csv` | NCU 없이 `net_E_J`, elapsed, expected denominator 수집 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | `results/ncu/*/ncu_cache_validation_summary.csv` | hit rate, bytes, accesses, stall, spill, Tensor instruction 확인 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | `results/summary/*_ncu_acceptance.*` | accepted/provisional/rejected 분류 |
| matched-control | `scripts/analyze_matched_control_energy.py` | `results/summary/*_matched_control_report.md` | pJ/FLOP, pJ/byte, pJ/bit 계산 |

## 4. Energy Run이 측정하는 것

Energy run은 NVML을 이용해 kernel 실행 전후의 GPU energy 또는 power를 측정한다. raw CSV의 `net_E_J`는 mode별 독립 실행값이다.

```text
delta_E_J = NVML energy after - NVML energy before
idle_baseline_scaled_J = idle energy measured for same seconds, scaled to kernel elapsed time
net_E_J = delta_E_J - idle_baseline_scaled_J
```

주의:

- `shared_mma` row에 `reg_mma`가 미리 빠져 있지 않다.
- `l2_mma` row에 `shared_mma`나 `reg_mma`가 미리 빠져 있지 않다.
- raw `pJ_per_FLOP`, raw `pJ_per_input_bit`는 mode 자체의 1차 지표일 뿐 component별 최종값이 아니다.

## 5. NCU가 하는 일

NCU는 energy를 직접 측정하지 않는다. NCU의 역할은 두 가지다.

| 역할 | 의미 |
|---|---|
| Path validation | 해당 kernel이 의도한 Tensor, shared, L1, L2, DRAM 경로를 실제로 사용했는지 확인 |
| Denominator validation | memory path의 pJ/byte 또는 pJ/bit 계산에 사용할 실제 traffic byte를 확인하거나 보정 |

NCU에서 확인해야 하는 항목은 다음이다.

| Component/path | NCU에서 확인할 항목 | 채택 의도 |
|---|---|---|
| Tensor | HMMA/Tensor instruction, spill/local memory, L1/L2/DRAM traffic | `reg_mma`는 Tensor instruction을 실행하고, control은 Tensor instruction이 없어야 함 |
| Shared scalar | shared accesses, shared bytes, shared instruction count, bank conflict | shared memory scalar load path가 충분히 발생하고 bank conflict가 낮아야 함 |
| Global L1 | L1 hit rate, L1 bytes, L2 bytes, DRAM bytes | global load가 L1 hit 중심이어야 함 |
| L2 CG | L1 hit rate, L2 hit rate, L2 bytes, DRAM bytes | L1은 사실상 우회되고 L2 hit가 지배적이어야 함 |
| DRAM CG | DRAM bytes, L1/L2 hit rate, L2 bytes 대비 DRAM bytes | DRAM streaming이 보이는지 sanity check |
| 공통 | long/short scoreboard stall, wait stall, SMID histogram, spill/local | stall 또는 placement 문제를 결과에 같이 기록 |

현재 acceptance 기준은 다음처럼 요약된다.

| Path | accepted 조건 요약 |
|---|---|
| Tensor | `reg_mma`에서 Tensor/HMMA instruction > 0, spill/local 0, memory traffic이 threshold 이하 |
| Tensor control | `reg_operand_only`에서 Tensor/HMMA instruction = 0, spill/local 0 |
| Shared scalar | shared bytes/accesses > 0, shared instruction 존재, bank conflict ratio 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 | L1 hit >= 95%, L2/L1 byte ratio <= 1%, DRAM/L1 byte ratio <= 1% |
| L2 CG | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 byte ratio <= 2% |
| DRAM sanity | L1 hit <= 1%, L2 hit <= 5%, DRAM bytes dominant |

이 기준을 통과하지 못한 row는 pJ 값이 양수여도 최종 component coefficient로 채택하지 않는다.

## 6. pJ 계산 방식

### 6.1 Matched-control energy 차분

Duration-calibrated runner는 mode마다 목표 시간에 맞게 ITER를 따로 calibrate한다. 그래서 단순히 `E_treatment - E_control`을 빼지 않고, control energy를 power rate로 바꾼 뒤 treatment elapsed time만큼 보정한다.

```text
control_power_W = E_control_J / t_control_s
control_energy_scaled_J = control_power_W * t_treatment_s
delta_E_J = E_treatment_J - control_energy_scaled_J
```

그 다음 denominator로 나눈다.

```text
pJ/FLOP = delta_E_J * 1e12 / FLOP
pJ/byte = delta_E_J * 1e12 / denominator_bytes
pJ/bit  = pJ/byte / 8
```

### 6.2 Tensor pJ/FLOP

Tensor는 byte denominator가 아니라 logical FLOP denominator를 사용한다.

| 항목 | mode | 의미 |
|---|---|---|
| treatment | `reg_mma` | register fragment를 준비하고 `mma_sync` 반복 |
| control | `reg_operand_only` | 비슷한 register fragment 구조를 쓰지만 `mma_sync` 없음 |
| denominator | FLOP | logical `m16n16k16` WMMA op 수 * 8192 FLOP |

FLOP 계산:

```text
N_MMA = active_SM * blocks_per_SM * ITER * reuse_factor
FLOP  = N_MMA * 8192
```

`8192 FLOP`는 FP16 WMMA `m16n16k16` 한 번을 logical GEMM 기준으로 본 값이다.

```text
16 * 16 * 16 multiply-add = 4096 FMA = 8192 FLOP
```

Tensor에서 NCU는 denominator를 만드는 도구가 아니라 다음 조건을 확인하는 도구다.

| 확인 | 이유 |
|---|---|
| `reg_mma`에서 Tensor/HMMA instruction > 0 | 실제 Tensor path 실행 확인 |
| `reg_operand_only`에서 Tensor/HMMA instruction = 0 | no-MMA control 확인 |
| spill/local memory = 0 | register spill로 L1/L2/DRAM traffic이 섞이는 것을 방지 |
| L1/L2/DRAM traffic이 작음 | Tensor coefficient가 memory traffic에 오염되지 않았는지 확인 |

### 6.3 Memory pJ/byte와 pJ/bit

Memory path는 다음 pair를 사용한다.

| Component/path | treatment | control | denominator 우선순위 |
|---|---|---|---|
| Shared scalar | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes |
| Global L1 hit | `global_l1_load_only` | `clocked_empty` | NCU L1 bytes |
| L2 CG hit | `l2_cg_load_only` | `clocked_empty` | NCU L2 bytes |
| DRAM CG streaming | `dram_cg_load_only` | `clocked_empty` | NCU DRAM bytes |

초기 expected bytes는 코드에서 다음처럼 계산된다.

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
| `ncu_actual_same_working_set` | mode, W_SM, blocks/SM, active_SM은 같고 factor는 대표 NCU scale 사용 | 현재 finalplan에서 사용하는 대표 방식 |
| `expected_no_ncu_match` | NCU actual denominator 없음 | 최종 pJ/byte 채택 금지 |

## 7. Shared Scalar와 Global L1의 차이

RTX 3090 GA102도 L1 data cache와 shared memory가 완전히 독립된 두 SRAM 블록처럼 떨어져 있는 구조가 아니다. NVIDIA GA102 whitepaper 기준으로 GA10x SM의 네 partition은 **combined 128 KiB L1 data cache/shared memory subsystem**을 공유하고, compute mode에서는 L1/shared 용량 구성을 workload에 맞게 나눌 수 있다.

하지만 실험 해석에서는 shared와 global L1을 그냥 같은 값으로 합치면 안 된다. 같은 on-chip subsystem에 가까운 자원을 공유하더라도, CUDA 주소 공간, instruction, datapath, NCU counter가 다르기 때문이다.

| 구분 | Shared scalar | Global L1 |
|---|---|---|
| 대표 mode | `shared_scalar_load_only` | `global_l1_load_only` |
| 접근 공간 | `__shared__` memory | global memory |
| 데이터 관리 | software-managed scratchpad | hardware-managed cache |
| 의도한 경로 | shared memory load path | global load가 L1 cache hit로 끝나는 path |
| 데이터 위치 | block 내부 shared memory | global 주소 공간의 데이터가 L1에 캐시된 상태 |
| 주 검증 counter | shared bytes/accesses, shared instruction, bank conflict | L1 hit rate, L1 bytes, L2/DRAM traffic 낮음 |
| 보면 안 되는 해석 | scalar ALU energy | shared memory energy |

쉽게 말하면:

```text
Shared scalar = __shared__ 배열을 반복해서 읽는 software-managed shared path
Global L1     = global pointer를 읽지만 L1 cache hit로 끝나게 만든 hardware cache path
```

왜 둘을 분리해야 하는가:

- RTX 3090에서 L1 cache와 shared memory는 combined/unified L1/shared subsystem을 공유하지만, 접근 instruction과 datapath는 동일하지 않다.
- shared memory는 thread block이 명시적으로 관리하는 scratchpad다.
- global L1은 global memory instruction이 cache hierarchy를 통해 처리되는 path다.
- 따라서 `shared_scalar_load_only`의 pJ/bit와 `global_l1_load_only`의 pJ/bit를 둘 다 “L1 energy”라고 합쳐 쓰면 안 된다.
- 논문/보고서에서는 `Shared scalar path`와 `Global L1-hit path`를 별도 coefficient로 쓰고, 필요할 때만 상위 범주로 `on-chip L1/shared subsystem effective traffic`이라고 묶어 표현한다.

## 8. 주요 mode 설명

### `clocked_empty`

Memory traffic이나 MMA 없이 같은 persistent grid/loop 구조를 만드는 control이다. Memory path coefficient에서는 대부분 `clocked_empty`를 control로 쓴다.

의미:

```text
clocked_empty ~= scheduler + warp loop + timing/control baseline
```

### `reg_operand_only`

`reg_mma`와 최대한 비슷한 register-fragment 반복 구조를 만들되 `mma_sync`만 제거한 no-MMA matched control이다.

의미:

```text
reg_operand_only ~= no-MMA register-fragment/control baseline
```

주의:

```text
reg_operand_only != pure register file energy
```

sampled fragment checksum과 compiler 최적화 방지용 소비 경로가 포함된다. 그래서 pure RF pJ/access가 아니라 `reg_mma`의 control로 쓴다.

### `reg_mma`

memory-backed operand 공급을 최대한 줄이고 register fragment 기반으로 FP16 WMMA `mma_sync`를 반복한다.

의미:

```text
reg_mma - reg_operand_only ~= effective Tensor MMA incremental cost
```

`reg_mma`도 순수 Tensor Core 에너지는 아니다. scheduler, issue, register fragment read/write, accumulator update, final store, measurement residual이 함께 들어간다.

### `shared_scalar_load_only`

dynamic shared memory를 만들고, shared memory scalar load를 반복한다. 현재 shared path의 primary mode다.

의미:

```text
shared_scalar_load_only - clocked_empty
  ~= shared-memory scalar load path effective coefficient
```

NCU에서 shared bytes/accesses와 bank conflict를 반드시 확인한다.

### `global_l1_load_only`

작은 global working set을 반복해서 읽어 global load가 L1 hit로 끝나도록 만드는 mode다.

의미:

```text
global_l1_load_only - clocked_empty
  ~= global-load L1-hit path effective coefficient
```

NCU에서 L1 hit rate가 높고 L2/DRAM traffic이 낮아야 한다.

### `l2_cg_load_only`

global load에 `.cg` 계열 경로를 사용해 L1을 최대한 배제하고 L2 hit path를 만들기 위한 mode다. RTX 3090/V100처럼 L2-only window를 W_SM만으로 만들기 어려운 GPU에서 primary L2 mode다.

의미:

```text
l2_cg_load_only - clocked_empty
  ~= L1-bypassed L2-hit path effective coefficient
```

NCU에서 L1 hit가 낮고 L2 hit가 높아야 한다.

### `l2_load_only`

일반 global load 기반 L2 capacity 후보 mode다. A100처럼 L2가 큰 GPU에서는 `l2_cg_load_only`와 비교할 수 있다.

주의:

- RTX 3090/V100에서는 일반 `l2_load_only`가 L1 hit로 끝나는 경우가 많아 L2 coefficient로 부적절할 수 있다.
- 현재 final matched-control analyzer의 primary L2 pair는 `l2_cg_load_only - clocked_empty`다.

### `dram_cg_load_only`

nominal L2보다 충분히 큰 working set으로 global streaming load를 만들고, `.cg` 계열 경로로 DRAM traffic이 지배적인지 확인한다.

의미:

```text
dram_cg_load_only - clocked_empty
  ~= DRAM streaming sanity path coefficient
```

DRAM 결과는 특히 조심해야 한다. 이는 physical HBM/GDDR device pJ/bit가 아니라 board-level path coefficient다.

### 보조/과거 탐색 mode

다음 mode는 코드에 남아 있지만 현재 final coefficient의 primary mode가 아니다.

| mode | 현재 위치 | 주의 |
|---|---|---|
| `shared_load_only` | shared WMMA load control/보조 진단 | bank conflict와 instruction mix 때문에 `shared_scalar_load_only`가 primary |
| `shared_mma` | shared operand + MMA 보조 진단 | `shared_mma - reg_mma`를 바로 shared energy로 해석하지 않음 |
| `l2_mma` | L2 operand + MMA 보조 진단 | L1/L2/DRAM path가 NCU로 확인되지 않으면 최종값 제외 |
| `dram_mma` | DRAM operand + MMA 보조 진단 | stall과 memory hierarchy 비용이 크게 섞임 |
| `reg_pressure` | scalar register-pressure 진단 | pure register-file energy가 아니라 control/proxy |
| `addr_only` | address generation control | memory coefficient primary pair는 아님 |

## 9. `W_SM`, blocks/SM, factor sweep의 의미

### 9.1 `W_SM`

`W_SM`은 SM당 logical working set 좌표다. 하지만 모든 mode에서 같은 의미가 아니다.

| mode 계열 | `W_SM` 사용 방식 |
|---|---|
| shared 계열 | block당 dynamic shared memory 크기 `W_block = W_SM / blocks_per_SM`에 반영 |
| global L1/L2/DRAM 계열 | `active_SM * W_SM` 크기의 global input buffer에 반영 |
| `reg_mma`, `reg_operand_only` | register footprint를 정하지 않음. sweep table의 좌표에 가까움 |
| `reg_pressure` | `W_SM`보다 `--reg-payload-bytes`와 ptxas register footprint가 중요 |

중요한 정정:

```text
reg_mma W_SM=2048 KiB 또는 과거 W_SM=32 KiB는
register working set 크기가 아니다.
```

`reg_mma`의 실제 register footprint는 ptxas register count, threads/block, resident blocks/SM로 판단해야 한다.

```text
register_footprint_B_per_block
  = ptxas_registers_per_thread * threads_per_block * 4

register_footprint_B_per_SM
  = register_footprint_B_per_block * resident_blocks_per_SM
```

### 9.2 `blocks/SM`

`blocks/SM`은 SM 하나에 동시에 배치하려는 block 수다. 현재 기본 kernel은 block당 32 threads, 즉 1 warp를 쓴다.

| 항목 | 의미 |
|---|---|
| `threads/block = 32` | block 하나가 warp 하나 |
| `grid blocks = active_SM * blocks_per_SM` | 의도한 SM 수에 균등하게 workload를 뿌림 |
| `smid_histogram_ok` | 실제로 각 SM에 의도한 block 수가 갔는지 확인 |

`blocks/SM`을 바꾸면 occupancy, scheduler pressure, memory issue pattern이 함께 바뀐다. 따라서 blocks sweep은 경향을 보는 도구이지 단독으로 component energy를 분리하는 도구가 아니다.

### 9.3 `reuse_factor`

Tensor 계열에서 한 번 준비한 operand로 MMA를 몇 번 반복하는지 정한다.

| 증가하면 | 의미 |
|---|---|
| FLOP 증가 | fixed overhead가 FLOP당 amortize됨 |
| Tensor instruction count 증가 | pJ/FLOP 식별성이 좋아질 수 있음 |
| 너무 크면 | thermal/clock/stall 변화가 생길 수 있음 |

### 9.4 `load_repeat`

Memory load-only 계열에서 iteration당 load를 몇 번 반복하는지 정한다.

| 증가하면 | 의미 |
|---|---|
| expected bytes 증가 | pJ/byte denominator가 커짐 |
| NCU traffic 증가 | path 검증이 쉬워짐 |
| 너무 크면 | stall과 clock 변화가 커질 수 있음 |

## 10. 플랫폼별 설계 차이

GPU architecture가 다르면 같은 `W_SM`이라도 의미가 달라진다.

| GPU | build arch | default SMs | L1/shared | L2 | 주요 설계 포인트 |
|---|---:|---:|---:|---:|---|
| RTX 3090 / GA102 | sm_86 | 82 | 128 KiB combined | 6 MiB | L2/SM이 작고 L1과 섞이기 쉬워 `l2_cg_load_only` 우선 |
| V100 / GV100 | sm_70 | 80 | 128 KiB combined, 96 KiB shared allocation | 6 MiB | Volta NCU `gv100` 지원 toolchain 필요, L2는 CG path 우선 |
| A100 / GA100 | sm_80 | 108 | 192 KiB combined, 164 KiB shared allocation | 40 MiB | capacity `l2_load_only`와 `l2_cg_load_only` 비교 가능 |
| H100 / GH100 | sm_90 | 132 default | 256 KiB combined, 228 KiB shared allocation profile | 50 MiB | 현재 kernel은 WMMA compatibility path이며 WGMMA/TMA 실험 아님 |

공통 주의:

- `active_SM`은 profile 기본값이 아니라 runtime/preflight에서 확인한 값을 우선한다.
- `combined L1/shared`와 CUDA dynamic shared allocation 한계는 같은 값이 아니다.
- NCU chip alias는 플랫폼별로 다르다: V100 `gv100`, A100 `ga100`, H100 `gh100`.
- V100은 최신 Nsight Compute에서 Volta/GV100 지원이 빠진 버전이 있을 수 있으므로 `ncu --list-chips`를 확인한다.

## 11. 표준 finalplan 좌표

`scripts/plan_platform_component_experiment.py`가 생성하는 기본 좌표는 다음과 같다.

| GPU | Tensor W_SM (KiB) | Shared W_SM (KiB) | L1 W_SM (KiB) | L2 W_SM (KiB) | DRAM W_SM (KiB) | blocks/SM |
|---|---:|---:|---:|---:|---:|---|
| V100 | 2048 | 32,64 | 8,16 | 64 with `l2_cg_load_only` | 8192 | 16,32 |
| A100 | 2048 | 64,128 | 16,32 | 256 with `l2_load_only,l2_cg_load_only` | 8192 | 16,32 |
| H100 | 2048 | 64,128 | 16,32 | 256 with `l2_load_only,l2_cg_load_only` | 8192 | 16,32 |

생성되는 energy sweep의 대표 factor는 다음이다.

| Component/path | modes | factor |
|---|---|---|
| Tensor | `reg_operand_only,reg_mma` | `reuse_factor=1,2,4,8,16` |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | `load_repeat=1,2,4,8,16` |
| Global L1 | `clocked_empty,global_l1_load_only` | `load_repeat=1,2,4,8,16` |
| L2 | `clocked_empty,l2_cg_load_only` 또는 A100/H100에서 `l2_load_only` 포함 | `load_repeat=1,2,4,8,16` |
| DRAM sanity | `clocked_empty,dram_cg_load_only` | `load_repeat=1,4,16` |

권장 실행 기준:

| 항목 | 권장값 |
|---|---:|
| final seconds | 10 s 이상 |
| final repeats | 5 이상 |
| NCU sidecar | energy run과 별도 실행 |
| memory pJ/byte | `--require-ncu-denominator` 사용 |

## 12. 결과를 어떻게 해석해야 하는가

### 안전한 표현

| 결과 | 안전한 표현 |
|---|---|
| Tensor | `reg_operand_only` 대비 `reg_mma`의 effective MMA incremental cost |
| Shared scalar | NCU shared bytes 기준 shared-memory scalar load path coefficient |
| Global L1 | NCU L1 bytes 기준 global-load L1-hit path coefficient |
| L2 | NCU L2 bytes 기준 L1-bypassed L2-hit path coefficient |
| DRAM | NCU DRAM bytes 기준 streaming sanity path coefficient |

### 피해야 할 표현

| 피해야 할 표현 | 이유 |
|---|---|
| `순수 Tensor Core energy` | register, scheduler, issue, accumulator, final store가 섞임 |
| `순수 register file energy` | 현재 `reg_operand_only`와 `reg_pressure`는 control/proxy |
| `L1 SRAM bitcell pJ/bit` | NVML board energy와 path overhead가 섞임 |
| `HBM physical pJ/bit 측정` | DRAM path에는 cache/controller/interconnect/stall이 포함됨 |
| `W_SM만 맞으면 L2 실험` | 실제 L1/L2/DRAM 경로는 NCU hit/access로 확인해야 함 |

## 13. 자가점검 체크리스트

문서/보고서 작성 전에 다음을 확인한다.

| 질문 | 통과 기준 |
|---|---|
| GPU profile이 맞는가? | `target_profile`, build arch, active_SM, L2/shared capacity가 플랫폼과 일치 |
| NCU chip이 맞는가? | V100 `gv100`, A100 `ga100`, H100 `gh100` |
| energy run과 NCU run을 섞지 않았는가? | energy 분자는 NVML run, path/denominator는 NCU sidecar |
| Tensor control이 no-MMA인가? | `reg_operand_only` HMMA 0, `reg_mma` HMMA > 0 |
| register spill이 없는가? | ptxas spill 0, NCU local spill 0 |
| Shared path가 진짜 shared인가? | shared bytes/accesses 존재, bank conflict 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 path가 진짜 L1 hit인가? | L1 hit >= 95%, L2/DRAM leakage 낮음 |
| L2 path가 L1과 섞이지 않았는가? | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 낮음 |
| DRAM은 sanity로 표현했는가? | physical DRAM energy라고 쓰지 않음 |
| pJ/byte denominator가 NCU 기반인가? | `ncu_actual_exact` 또는 `ncu_actual_same_working_set` |
| 음수 coefficient를 숨기지 않았는가? | 음수는 `not_identified_or_control_failed`로 기록 |
| 모든 표에 단위가 있는가? | W_SM KiB/MiB, blocks/SM, seconds s, repeats count, bytes, %, pJ/FLOP, pJ/bit 명시 |

## 14. 한눈에 보는 실험 구조

```mermaid
flowchart LR
  subgraph TensorPair[Tensor pair]
    RO[reg_operand_only<br/>no-MMA control] --> RM[reg_mma<br/>WMMA/HMMA]
    RM --> TF[pJ/FLOP]
  end

  subgraph MemoryPairs[Memory path pairs]
    CE[clocked_empty<br/>baseline]
    CE --> SH[shared_scalar_load_only<br/>shared path]
    CE --> L1[global_l1_load_only<br/>L1-hit path]
    CE --> L2[l2_cg_load_only<br/>L2-hit path]
    CE --> DR[dram_cg_load_only<br/>DRAM sanity]
    SH --> SB[pJ/byte, pJ/bit]
    L1 --> L1B[pJ/byte, pJ/bit]
    L2 --> L2B[pJ/byte, pJ/bit]
    DR --> DB[pJ/byte, pJ/bit]
  end

  NCU[NCU validation<br/>hit/access/stall/spill] --> TF
  NCU --> SB
  NCU --> L1B
  NCU --> L2B
  NCU --> DB
```

최종적으로 보고해야 하는 것은 “component 이름만 붙인 숫자”가 아니라 다음 네 가지가 함께 있는 표다.

| 반드시 같이 보고할 것 | 이유 |
|---|---|
| treatment/control pair | 어떤 차분인지 알아야 숫자의 의미가 결정됨 |
| sweep 조건 | W_SM, blocks/SM, reuse/load_repeat가 path와 coefficient를 바꿈 |
| NCU acceptance | mode 이름만으로 path가 보장되지 않음 |
| coefficient와 단위 | pJ/FLOP, pJ/byte, pJ/bit를 섞으면 해석이 틀림 |

## 15. 결론

현재 코드의 component 실험은 다음처럼 이해하는 것이 가장 정확하다.

```text
Tensor:       reg_mma - reg_operand_only
Shared path:  shared_scalar_load_only - clocked_empty
Global L1:    global_l1_load_only - clocked_empty
L2:           l2_cg_load_only - clocked_empty
DRAM sanity:  dram_cg_load_only - clocked_empty
```

이 결과는 GPU architecture와 workload geometry에 의존한다. 따라서 RTX 3090에서 통과한 좌표를 A100, V100, H100에 그대로 적용하지 말고, 각 GPU의 register, L1/shared, L2 capacity와 NCU metric 지원 상태를 확인한 뒤 같은 acceptance-first 절차를 다시 실행해야 한다.
