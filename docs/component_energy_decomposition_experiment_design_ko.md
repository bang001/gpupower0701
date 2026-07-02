# Component별 유효에너지 분해 실험 설계

작성일: 2026-07-02

## 목적

현재 실험은 FP16 Tensor Core `m16n16k16` logical MMA를 기준으로 RTX 3090에서 `blocks/SM`과 `W_SM`을 sweep하여 register, shared/L1, L2, DRAM 경로의 유효 에너지 차이를 관찰했다. 다음 단계의 목표는 이 관찰을 더 방어 가능한 component-level 추정으로 바꾸는 것이다.

핵심 방향은 두 가지다.

- 기존 mode별 비교를 유지하되, 각 mode에 대응되는 `memory-only` 또는 `path-only` control mode를 추가한다.
- 각 component를 단순 mode 평균 차이가 아니라 paired-difference와 회귀 모델로 함께 추정한다.

여기서 말하는 component 에너지는 물리적으로 순수한 Tensor Core, 순수한 SRAM, 순수한 DRAM 에너지가 아니다. 벤치마크 구조 안에서 관측되는 effective component coefficient다.

## 유효성 검토 요약

현재 문서의 방향은 타당하다. 특히 `memory-only` 또는 `path-only` control mode를 추가하고 같은 좌표에서 paired-difference를 계산하는 방식은 기존 mode별 절대값 비교보다 논리적으로 강하다. 다만 이 설계만으로 “물리 component energy”를 직접 분리했다고 주장하면 안 된다. 올바른 표현은 “동일 microbenchmark 구조 안에서 관측되는 effective component coefficient”다.

| 판단 항목 | 판정 | 이유 | 보강 필요 |
|---|---|---|---|
| 현재 mode별 비교의 진단 가치 | 유효 | register/shared/L2/DRAM 경로별 pJ/FLOP 경향을 보여준다. | NCU path 검증과 반복 측정 필요 |
| paired-difference 설계 | 유효 | 같은 좌표에서 기능 하나를 추가/제거하므로 mode 간 baseline 차이를 줄인다. | pair 간 instruction mix와 runtime 차이를 기록해야 한다. |
| 회귀 기반 component 분해 | 조건부 유효 | bytes, MMA 수, elapsed time을 동시에 모델링할 수 있다. | `N_MMA`와 memory bytes가 독립적으로 변하도록 추가 sweep이 필요하다. |
| 순수 물리 energy 분리 주장 | 부적절 | GPU 내부 component는 동시에 동작하고 DVFS, scheduler, cache 상태가 결합된다. | 항상 effective coefficient로 표현한다. |
| NCU 없는 해석 | 제한적 유효 | static expected bytes와 PTX 검증으로 1차 확인은 가능하다. | stall %, SOL %, 실제 bytes/op는 NCU sidecar가 있어야 확정 가능하다. |

가장 중요한 보강점은 식별성이다. 현재 `shared_mma`, `l2_mma`, `dram_mma`는 logical MMA 1회마다 A+B 1 KiB operand를 공급하는 구조에 가깝다. 그러면 `N_MMA`, input bytes, elapsed time이 함께 증가해서 회귀 모델에서 tensor coefficient와 memory coefficient가 서로 섞일 수 있다. 따라서 다음 설계에서는 `reuse_factor`, `load_repeat`, `store_repeat` 같은 축을 추가해 FLOP 수와 byte 수가 독립적으로 변하도록 만들어야 한다.

## 현재 실험의 목표

| 항목 | 내용 |
|---|---|
| 측정 대상 | FP16 WMMA `m16n16k16` logical MMA |
| logical op 정의 | 1 op = 4096 FMA = 8192 FLOP = A+B 입력 8192 bit |
| 주요 비교 축 | `mode`, `blocks/SM`, `W_SM (KiB)`, `active_SM (SMs)` |
| 주요 산출값 | `net_E_J (J)`, `pJ/FLOP`, `pJ/input-bit`, SMID placement status |
| 현재 RTX 3090 sweep | `blocks/SM = 1, 2, 4, 8, 16`; `blocks/SM=32`는 invalid 기록 |
| 현재 W sweep | `W_SM = 1 KiB`부터 `128 MiB`까지 2배 증가 |

현재 실험이 답하려는 질문은 다음이다.

- Tensor Core MMA를 register operand 중심으로 반복할 때의 유효 비용은 어느 정도인가?
- operand를 shared/L1, L2, DRAM 경로에서 공급할 때 pJ/FLOP가 어떻게 달라지는가?
- `blocks/SM` 증가가 resident warp 수와 latency hiding을 통해 유효 에너지를 낮추는가?
- `W_SM` 증가가 shared-resident, L2-hit candidate, DRAM streaming regime boundary와 일관되게 연결되는가?

## 현재 실험 구조

| mode | 현재 의미 | 주요 sweep 축 | 단위 | 해석상 목표 |
|---|---|---|---|---|
| `idle` | 커널 없이 NVML energy delta 측정 | `seconds`, `repeats` | s, count | idle NVML baseline |
| `empty` | 같은 persistent grid, MMA 없음 | `blocks/SM`, `active_SM` | blocks/SM, SMs | scheduling/loop/placement baseline |
| `reg_mma` | WMMA fragment를 register 값으로 채우고 MMA 반복 | `blocks/SM`, `active_SM` | blocks/SM, SMs | effective Tensor Engine + register path |
| `shared_mma` | shared memory에 operand를 staging한 뒤 WMMA load + MMA | `W_SM`, `blocks/SM` | KiB, blocks/SM | effective shared/L1 operand path |
| `l2_mma` | L2에 들어갈 수 있는 global working set warm-up 후 global load + MMA | `W_SM`, `blocks/SM` | KiB, blocks/SM | effective L2-hit operand path |
| `dram_mma` | nominal L2보다 큰 global working set streaming load + MMA | `W_SM`, `blocks/SM` | KiB, blocks/SM | effective DRAM streaming operand path |
| `store_path` | persistent execution에서 global store/output overhead 확인 | `blocks/SM`, `active_SM` | blocks/SM, SMs | store-side overhead check |

## 현재 구조의 이점

| 이점 | 설명 |
|---|---|
| logical op 기준 통일 | 모든 MMA mode가 `8192 FLOP/op`, `8192 input bits/op` 기준으로 정규화된다. |
| 동일 grid 구조 | `threads/block=32`, `warps/block=1`, `blocks/SM`을 고정하므로 resident warp 수와 placement를 비교하기 쉽다. |
| regime boundary 명시 | shared-resident, L2 candidate, DRAM streaming을 GPU profile의 shared/L2 용량 기준으로 분류한다. |
| RTX 3090 제약 반영 | `blocks/SM=32`를 실행하지 않고 invalid matrix row로 남긴다. |
| 에너지 측정과 NCU 분리 | NVML energy run과 NCU replay profiling을 섞지 않아 energy 값 왜곡을 줄인다. |
| SMID 검증 가능 | `smid_histogram_ok`로 active SM 배치가 의도대로 되었는지 1차 확인할 수 있다. |

## 현재 구조의 한계

| 한계 | 왜 문제가 되는가 | 영향 |
|---|---|---|
| `l2_mma`, `dram_mma`에 memory + MMA + stall이 섞임 | global memory load와 Tensor Core compute가 같은 kernel 안에 있다. | L2/DRAM component만 분리했다고 말하기 어렵다. |
| `shared_mma`에 shared load + MMA + barrier/initialization이 섞임 | shared operand staging과 MMA 실행이 동시에 포함된다. | shared/L1 path overhead와 Tensor Core cost가 겹친다. |
| `reg_mma`와 memory-backed MMA의 instruction mix가 다름 | operand source가 다르면 load instruction, dependency, issue stall이 달라진다. | mode 차이를 component 차이로 바로 해석하면 과대해석 가능성이 있다. |
| `W_SM`이 모든 mode에서 실제 working set은 아님 | `reg_mma`, `empty`, `store_path`는 sweep coordinate만 맞춘다. | `W_SM` 의존성은 memory-backed mode 중심으로만 해석해야 한다. |
| NCU counter 검증 미완료 가능성 | RTX 3090 WSL 환경은 `ERR_NVGPUCTRPERM`가 발생할 수 있다. | stall %, SOL %, memory traffic %로 정상 수행 여부를 확정하지 못할 수 있다. |
| NVML API 의미가 GPU별로 다름 | `GetPowerUsage`는 GA100 이전/GA100과 GA10x/Hopper에서 의미가 다르다. | total energy counter와 power integration 결과를 같은 의미로 섞으면 안 된다. |
| effective coefficient만 가능 | GPU 내부 component는 동시 동작, clock, DVFS, cache replacement, scheduler와 결합된다. | 물리적 순수 component energy라고 표현하면 안 된다. |

## 제안 실험 구조 개요

새 구조는 `paired-difference`를 중심으로 한다. 즉, 같은 `W_SM (KiB)`, `blocks/SM`, `active_SM (SMs)`, `ITER`, `seconds (s)`, `repeats` 조건에서 기능 하나만 추가한 mode 쌍을 비교한다.

### 핵심 아이디어

| pair | 차분 | 추정하려는 항목 | 단위 |
|---|---|---|---|
| `reg_mma - empty` | `E_reg_mma - E_empty` | Tensor Core + register operand path 유효 비용 | J, pJ/FLOP |
| `shared_load_only - empty` | `E_shared_load_only - E_empty` | shared/L1 operand load/staging 유효 비용 | J, pJ/byte |
| `shared_mma - shared_load_only` | `E_shared_mma - E_shared_load_only` | shared operand가 있는 상태의 MMA incremental cost | J, pJ/FLOP |
| `l2_load_only - empty` | `E_l2_load_only - E_empty` | L2-hit candidate global load 유효 비용 | J, pJ/byte |
| `l2_mma - l2_load_only` | `E_l2_mma - E_l2_load_only` | L2 operand 공급 조건에서 MMA incremental cost | J, pJ/FLOP |
| `dram_load_only - empty` | `E_dram_load_only - E_empty` | DRAM streaming global load 유효 비용 | J, pJ/byte |
| `dram_mma - dram_load_only` | `E_dram_mma - E_dram_load_only` | DRAM operand 공급 조건에서 MMA incremental cost | J, pJ/FLOP |
| `store_only - empty` | `E_store_only - E_empty` | global store/output path 유효 비용 | J, pJ/byte |

이 방식의 장점은 `l2_mma`와 `dram_mma`의 총 에너지에서 memory traffic과 MMA가 섞이는 문제를 줄인다는 점이다. 완벽한 물리 분리는 아니지만, 현재 mode별 절대값 비교보다 component 해석이 훨씬 명확해진다.

## 더 의미 있는 상세 설계: 독립 축 추가

paired-difference만으로도 현재보다 나아지지만, 회귀 분해까지 의미 있게 하려면 FLOP 수와 memory byte 수를 독립적으로 바꿔야 한다. 이를 위해 다음 세 축을 추가한다.

| 축 | 값 후보 | 단위 | 목적 |
|---|---|---|---|
| `reuse_factor` | `1, 2, 4, 8, 16` | MMA/load | 같은 operand load 뒤 MMA를 여러 번 수행해 FLOP만 증가시킨다. |
| `load_repeat` | `1, 2, 4, 8, 16` | load/tile | MMA 없이 operand load 횟수만 늘려 byte traffic을 증가시킨다. |
| `store_repeat` | `1, 2, 4, 8, 16` | store/tile | output store traffic만 독립적으로 증가시킨다. |

이 축이 필요한 이유:

| 문제 | 기존 설계 | 보강 설계 |
|---|---|---|
| `N_MMA`와 memory bytes가 같이 증가 | 1 MMA마다 1 KiB input load | `reuse_factor`로 input bytes는 거의 고정하고 MMA 수만 증가 |
| memory-only가 MMA kernel과 너무 다름 | load-only와 MMA의 dependency graph 차이 큼 | `wmma_load_only`와 `mma_after_load`를 같은 load instruction 형태로 맞춤 |
| store overhead가 결과 store와 섞임 | 모든 mode가 final checksum/store를 가짐 | `store_repeat`와 matched final store policy로 store traffic을 별도 추정 |
| runtime leakage가 component와 섞임 | elapsed time 차이가 energy 차이에 포함 | 회귀에 `elapsed_s (s)` 항을 넣고 pair 안에서는 run order를 rotate |

### 식별 가능한 계수

| 계수 | 식별에 필요한 독립 변화 | 권장 mode |
|---|---|---|
| Tensor/MMA coefficient | `reuse_factor` 변화로 `N_MMA`만 증가 | `reg_mma_reuse`, `shared_mma_reuse`, `l2_mma_reuse`, `dram_mma_reuse` |
| shared/L1 byte coefficient | `load_repeat` 변화로 shared load bytes 증가 | `shared_load_only` |
| L2 byte coefficient | L2 resident working set에서 `load_repeat` 변화 | `l2_load_only` |
| DRAM byte coefficient | L2보다 큰 working set에서 streaming `load_repeat` 변화 | `dram_load_only` |
| store byte coefficient | `store_repeat` 변화 | `store_only` |
| time/leakage coefficient | elapsed time 변화 | 모든 mode의 `elapsed_s` |

### 권장 계층 구조

실험은 세 단계로 나눈다.

| 단계 | 목적 | 실행 조건 | 결과 |
|---|---|---|---|
| Level 1: paired-difference | 현재 mode 분해를 더 깨끗하게 만들기 | 같은 `W_SM`, `blocks/SM`, `active_SM`, `ITER`에서 paired mode 실행 | pJ/FLOP, pJ/byte 차분 |
| Level 2: factorial sweep | 회귀 계수 식별성 확보 | `reuse_factor`, `load_repeat`, `store_repeat` 추가 sweep | tensor/byte/time coefficient |
| Level 3: NCU validation | 실제 path와 stall 확인 | 대표 좌표만 NCU profiling | tensor %, bytes/op, stall % |

Level 1만으로는 “더 나은 차분 실험”이고, Level 2까지 해야 “component coefficient 모델”이라고 부를 수 있다.

## 신규 mode 설계

| 신규 mode | 목적 | 동작 | 대응 기존 mode | 주요 metric |
|---|---|---|---|---|
| `shared_load_only` | shared/L1 operand load 비용 측정 | shared memory에서 WMMA fragment 또는 scalar vector로 operand를 반복 load하고 checksum만 store | `shared_mma` | shared bytes/op, elapsed_s, net_E_J |
| `l2_load_only` | L2-hit global load 비용 측정 | warm-up 후 nominal L2에 들어가는 global working set을 MMA 없이 load | `l2_mma` | L2 bytes/op, L2 hit rate, net_E_J |
| `dram_load_only` | DRAM streaming load 비용 측정 | nominal L2보다 큰 global working set을 streaming pattern으로 load | `dram_mma` | DRAM bytes/op, DRAM throughput %, long scoreboard stall % |
| `store_only` | global store 비용 측정 | MMA 없이 output path와 같은 store pattern 반복 | `store_path` | store bytes/op, L2/DRAM write bytes, net_E_J |
| `reg_fragment_only` | register/fragment setup 비용 측정 | WMMA fragment fill 또는 register dependency loop만 수행하고 MMA 없음 | `reg_mma` | instruction count, net_E_J |

`reg_fragment_only`는 optional이다. 현재 `empty`가 baseline 역할을 하지만, fragment fill 자체가 `reg_mma`에 포함된다면 이를 분리하기 위해 추가한다.

### Kernel별 상세 동작

| mode | per-iteration 동작 | output/anti-optimization | expected logical counts |
|---|---|---|---|
| `empty` | dependent integer loop 또는 minimal loop | block당 final scalar store | `N_MMA=0`, expected bytes 거의 0 |
| `reg_fragment_only` | WMMA fragment fill 또는 register dependency update, MMA 없음 | fragment/register checksum store | `N_MMA=0`, register setup count 기록 |
| `reg_mma` | register fragment 준비 후 `reuse_factor`만큼 MMA | accumulator final store | `N_MMA = active_SM * B * ITER * reuse_factor` |
| `shared_load_only` | shared memory에서 A/B tile을 WMMA fragment로 load, MMA 없음 | fragment element checksum store | shared bytes = `active_SM * B * ITER * load_repeat * 1024` |
| `shared_mma` | shared memory에서 A/B tile load 후 `reuse_factor`만큼 MMA | accumulator final store | shared bytes와 `N_MMA`를 별도 기록 |
| `l2_load_only` | L2-resident global tile에서 A/B tile load, MMA 없음 | fragment checksum store | L2 candidate bytes = `ITER * load_repeat * 1024` per active block |
| `l2_mma` | L2-resident global tile load 후 `reuse_factor`만큼 MMA | accumulator final store | L2 bytes와 `N_MMA` 별도 기록 |
| `dram_load_only` | streaming global tile에서 A/B tile load, MMA 없음 | fragment checksum store | DRAM candidate bytes = `ITER * load_repeat * 1024` per active block |
| `dram_mma` | streaming global tile load 후 `reuse_factor`만큼 MMA | accumulator final store | DRAM bytes와 `N_MMA` 별도 기록 |
| `store_only` | output buffer에 반복 store | store value depends on loop index | store bytes = `active_SM * B * ITER * store_repeat * sizeof(float)` 또는 명시한 store width |

구현상 주의:

- `load_only` kernel은 compiler가 load를 제거하지 못하도록 loaded fragment 값을 checksum으로 소비한다.
- WMMA fragment 내부 element 접근은 compiler/toolchain 차이가 있을 수 있으므로, 구현 후 PTX/SASS에서 `wmma.load` 또는 대응 load instruction이 남아 있는지 확인한다.
- `load_only`의 final store는 `mma` mode의 final store와 최대한 같은 크기/빈도로 맞춘다. 그렇지 않으면 store overhead가 차분에 섞인다.
- global `l2_load_only`와 `dram_load_only`는 동일 kernel을 쓰되 tile 선택 정책만 다르게 한다. L2 mode는 warm-up 후 반복 tile 순회, DRAM mode는 large working set streaming/hash 순회를 사용한다.
- shared mode의 shared memory initialization은 측정 전/측정 중 포함 여부를 명확히 정해야 한다. 현재 구조처럼 kernel 내부에서 한 번 초기화한다면 `shared_init_only` control을 추가하거나 notes에 `shared_init_included=1`을 기록한다.

### 추가 control mode

더 엄밀하게 하려면 다음 control mode를 추가한다.

| control mode | 목적 | 필요한 이유 |
|---|---|---|
| `address_only` | tile index 계산과 loop/address generation만 수행 | load-only에서 address 계산 비용을 분리 |
| `shared_init_only` | shared memory 초기화만 수행 | `shared_load_only`에서 one-time shared initialization 비용 분리 |
| `global_warmup_only` | global working set warm-up만 측정 | L2 warm-up 비용이 measurement에 들어가지 않았는지 확인 |
| `matched_store_only` | 각 mode의 final store와 동일한 store만 수행 | output store overhead 보정 |

최소 구현은 `shared_load_only`, `l2_load_only`, `dram_load_only`, `store_only` 네 개로 시작한다. 논문 수준 주장을 강화하려면 `address_only`, `shared_init_only`, `matched_store_only`까지 추가한다.

## 상세 실험 matrix

### 공통 축

| 축 | 값 | 단위 | 설명 |
|---|---|---|---|
| `blocks/SM` | `1, 2, 4, 8, 16, 32` | blocks/SM | RTX 3090은 `32` invalid 기록, 실행 제외 |
| `W_SM` | `1 KiB`부터 `128 MiB`까지 2배 증가 | KiB, MiB | shared/L2/DRAM regime boundary 확인 |
| `active_SM` | full SM 우선, optional `16, 32, 64, full` | SMs | 최종 비교는 full SM 기준 우선 |
| `seconds` | final `10` 이상 | s | NVML power averaging 영향 완화 |
| `repeats` | final `5` 이상 | count | thermal drift와 run-to-run noise 추정 |
| `energy_source` | `nvml_total_energy` 우선 | mJ delta | fallback이면 별도 분석 group |

### GPU별 feasibility boundary

| GPU profile | CC | default SMs (SMs) | L2 (MiB) | shared/SM (KiB) | max blocks/SM | `blocks/SM=32` |
|---|---:|---:|---:|---:|---:|---|
| `v100` | 7.0 | 80 | 6 | 96 | 32 | 실행 후보 |
| `rtx3090` | 8.6 | 82 | 6 | 100 | 16 | invalid 기록 |
| `a100` | 8.0 | 108 | 40 | 164 | 32 | 실행 후보 |
| `h100` | 9.0 | SKU/runtime 우선 | 50 | 228 | 32 | 실행 후보 |

### mode set

| group | modes | 목적 |
|---|---|---|
| baseline | `idle`, `empty` | idle/system 및 persistent-kernel overhead 기준 |
| register/tensor | `reg_fragment_only`, `reg_mma` | register setup과 Tensor Core incremental cost 분리 |
| shared path | `shared_load_only`, `shared_mma` | shared/L1 operand path와 MMA incremental cost 분리 |
| L2 path | `l2_load_only`, `l2_mma` | L2-hit global load와 MMA incremental cost 분리 |
| DRAM path | `dram_load_only`, `dram_mma` | DRAM streaming load와 MMA incremental cost 분리 |
| store path | `store_only`, `store_path` | output/store overhead 분리 |

## 실행 순서 설계

열 drift를 줄이기 위해 mode를 한꺼번에 몰아서 실행하지 않는다. 같은 좌표의 paired mode를 가까이 실행하되, pair 순서는 반복마다 바꾼다.

예시:

| 순서 | run group | mode | 목적 |
|---:|---|---|---|
| 1 | baseline | `empty` | pair baseline |
| 2 | register | `reg_fragment_only` | fragment/register setup |
| 3 | register | `reg_mma` | Tensor Core incremental |
| 4 | shared | `shared_load_only` | shared/L1 load only |
| 5 | shared | `shared_mma` | shared + MMA |
| 6 | L2 | `l2_load_only` | L2 load only |
| 7 | L2 | `l2_mma` | L2 + MMA |
| 8 | DRAM | `dram_load_only` | DRAM load only |
| 9 | DRAM | `dram_mma` | DRAM + MMA |
| 10 | store | `store_only` | store only |

반복 간에는 순서를 rotate한다. 예를 들어 repeat 2에서는 shared pair를 먼저 실행하고, repeat 3에서는 DRAM pair를 먼저 실행한다.

### Pair calibration 규칙

paired-difference에서는 pair 안의 operation count가 달라지면 해석이 약해진다. 따라서 다음 규칙을 둔다.

| 규칙 | 내용 |
|---|---|
| 고정 `ITER` | 같은 좌표의 pair는 동일 `ITER`를 사용한다. mode별 자동 calibration으로 서로 다른 `ITER`를 쓰지 않는다. |
| reference calibration | 먼저 reference mode를 짧게 calibration하고, 그 `ITER`를 pair 전체에 적용한다. 예: `shared_mma` 기준 `ITER`를 `shared_load_only`에도 사용 |
| elapsed 기록 | pair 안에서도 `elapsed_s (s)`가 달라질 수 있으므로 CSV와 회귀 모델에 반드시 포함한다. |
| idle 보정 | `idle_baseline_J`는 각 run elapsed에 비례해 보정하되, 최종 회귀에는 `elapsed_s` 항을 별도로 둔다. |
| run order rotation | thermal drift 방지를 위해 repeat마다 pair 순서를 바꾼다. |

권장 calibration 방식:

| group | reference mode | 같은 `ITER`를 공유할 mode |
|---|---|---|
| register | `reg_mma` | `empty`, `reg_fragment_only`, `reg_mma` |
| shared | `shared_mma` | `empty`, `shared_init_only`, `shared_load_only`, `shared_mma` |
| L2 | `l2_mma` | `empty`, `l2_load_only`, `l2_mma` |
| DRAM | `dram_mma` | `empty`, `dram_load_only`, `dram_mma` |
| store | `store_only` | `empty`, `matched_store_only`, `store_only`, `store_path` |

## 분석 모델

### 1차 분석: paired-difference

각 좌표 `x = (GPU, W_SM, blocks/SM, active_SM, ITER)`에서 다음을 계산한다.

```text
Delta_reg_tensor_J      = E(reg_mma, x) - E(empty, x)
Delta_shared_load_J     = E(shared_load_only, x) - E(empty, x)
Delta_shared_mma_J      = E(shared_mma, x) - E(shared_load_only, x)
Delta_l2_load_J         = E(l2_load_only, x) - E(empty, x)
Delta_l2_mma_J          = E(l2_mma, x) - E(l2_load_only, x)
Delta_dram_load_J       = E(dram_load_only, x) - E(empty, x)
Delta_dram_mma_J        = E(dram_mma, x) - E(dram_load_only, x)
Delta_store_J           = E(store_only, x) - E(empty, x)
```

정규화 단위:

| coefficient | 계산 | 단위 |
|---|---|---|
| tensor register cost | `Delta_reg_tensor_J * 1e12 / FLOP` | pJ/FLOP |
| shared load cost | `Delta_shared_load_J * 1e12 / shared_bytes` | pJ/byte |
| L2 load cost | `Delta_l2_load_J * 1e12 / l2_bytes` | pJ/byte |
| DRAM load cost | `Delta_dram_load_J * 1e12 / dram_bytes` | pJ/byte |
| store cost | `Delta_store_J * 1e12 / store_bytes` | pJ/byte |
| path-specific MMA cost | `Delta_*_mma_J * 1e12 / FLOP` | pJ/FLOP |

### 2차 분석: 회귀 분해

paired-difference 이후 전체 row를 모아 회귀 모델을 맞춘다.

```text
net_E_J =
  alpha_time * elapsed_s
+ beta_tensor * N_MMA
+ beta_shared * shared_bytes
+ beta_l2 * l2_bytes
+ beta_dram * dram_bytes
+ beta_store * store_bytes
+ beta_barrier * N_barrier
+ beta_launch * 1
+ residual
```

| 항 | 의미 | coefficient 단위 |
|---|---|---|
| `alpha_time` | 시간 기반 idle/system drift | J/s |
| `beta_tensor` | logical MMA 1회당 incremental cost | J/op 또는 pJ/op |
| `beta_shared` | shared/L1 byte당 cost | J/byte 또는 pJ/byte |
| `beta_l2` | L2 byte당 cost | J/byte 또는 pJ/byte |
| `beta_dram` | DRAM byte당 cost | J/byte 또는 pJ/byte |
| `beta_store` | store byte당 cost | J/byte 또는 pJ/byte |
| `beta_barrier` | barrier/synchronization overhead | J/barrier |

NCU counter가 없으면 `shared_bytes`, `l2_bytes`, `dram_bytes`, `store_bytes`는 static expected bytes로 먼저 계산한다. NCU가 가능하면 actual counter 기반으로 회귀를 다시 맞추고 두 결과를 비교한다.

### 회귀 설계 유효성 조건

회귀 모델은 다음 조건을 만족해야 의미가 있다.

| 조건 | 통과 기준 | 실패 시 해석 |
|---|---|---|
| 독립 변수 collinearity | `N_MMA`, shared bytes, L2 bytes, DRAM bytes, store bytes가 완전히 같은 비율로 움직이지 않아야 한다. | tensor/memory coefficient를 분리하지 못한다. |
| coefficient sign | 주요 byte coefficient와 tensor coefficient가 음수가 아니어야 한다. | baseline, idle 보정, mode matching 오류 가능성 |
| residual structure | residual이 특정 mode나 `W_SM`에 체계적으로 몰리지 않아야 한다. | 누락된 항목 또는 regime mismatch 가능성 |
| cross-validation | 일부 `W_SM` 또는 `blocks/SM`을 제외하고 학습해도 예측 trend가 유지되어야 한다. | overfit 또는 측정 noise 가능성 |
| source consistency | `energy_source`가 같은 row끼리만 fit한다. | NVML API 의미 차이로 coefficient가 섞인다. |
| NCU consistency | NCU actual bytes와 static expected bytes의 차이가 큰 row는 별도 flag 처리한다. | path가 의도대로 수행되지 않았을 가능성 |

권장 모델 단계:

| 모델 | 목적 | 사용 feature |
|---|---|---|
| Model A: time-only baseline | idle/system drift 확인 | `elapsed_s` |
| Model B: paired local coefficients | 각 pair의 단순 차분 | pair별 `delta_E_J` |
| Model C: static-byte regression | NCU 없이 1차 coefficient 추정 | expected bytes, `N_MMA`, `elapsed_s` |
| Model D: NCU-byte regression | 실제 memory path 검증 후 coefficient 추정 | NCU bytes, tensor inst, stall %, `elapsed_s` |

최종 보고서에서는 Model B를 주 결과로 두고, Model C/D를 일관성 검증으로 제시하는 것이 가장 방어적이다.

## NCU 검증 설계

NCU는 energy 측정값에 합치지 않고, 각 mode가 의도한 path를 실제로 타는지 검증하는 sidecar다.

| 검증 항목 | 봐야 할 metric 예 | 기대 |
|---|---|---|
| Tensor Core 실행 | tensor instruction count, tensor pipe utilization | `*_mma`에서 증가, `*_load_only`에서는 낮거나 없음 |
| L1/shared path | L1 hit rate (%), L1 access count, shared/L1 bytes, short scoreboard stall | `shared_load_only`, `shared_mma`에서 증가 |
| L2 path | L2 hit rate (%), L2 access count, L2 bytes | `l2_load_only`, `l2_mma`에서 DRAM보다 L2 우세 |
| DRAM path | DRAM access count, DRAM bytes, DRAM throughput %, long scoreboard stall % | `dram_load_only`, `dram_mma`에서 증가 |
| store path | L2/DRAM write bytes | `store_only`, `store_path`에서 증가 |
| occupancy | achieved occupancy, active warps | `blocks/SM` 변화와 일관 |
| stall | `long_scoreboard`, `short_scoreboard`, `math_pipe_throttle`, `not_selected` | memory path별 병목 해석 |

현재 RTX 3090 WSL 환경에서는 NCU counter permission 문제가 있으므로, `ERR_NVGPUCTRPERM`이 남아 있으면 NCU 검증은 `blocked`로 기록하고 PTX/SASS 정적 검증만 사용한다.

## 결과 보고서 구조

실험 보고서는 반드시 표 중심으로 작성한다. 모든 표에는 단위를 넣는다.

### 필수 표

| 표 | 필수 열 |
|---|---|
| 실험 조건 표 | GPU, CC, SMs, L2 (MiB), shared/SM (KiB), energy_source, seconds (s), repeats |
| mode 설명 표 | mode, meaning, main path |
| sweep coverage 표 | mode, valid rows, skipped rows, W_SM range (KiB/MiB), blocks/SM range |
| paired-difference 표 | pair, delta_E_J (J), normalized coefficient, unit |
| regression coefficient 표 | coefficient, estimate, unit, confidence interval, residual note |
| NCU 검증 표 | mode, tensor %, L1 hit rate (%), L2 hit rate (%), L1 accesses (requests 또는 sectors), L2 accesses (sectors), DRAM accesses (sectors), shared bytes/op, L2 bytes/op, DRAM bytes/op, top stall %, status |

### 해석 문장 규칙

- `pure Tensor Core energy`처럼 쓰지 않는다. `effective Tensor Engine + register path`처럼 쓴다.
- `DRAM energy`라고 단정하지 않는다. `effective DRAM streaming path coefficient`라고 쓴다.
- NCU가 실패한 경우, “NCU counter 기반 stall/SOL 검증은 미완료”라고 첫 요약에 포함한다.
- `seconds=1`, `repeats=1` smoke 결과는 최종 coefficient로 쓰지 않는다.

## 구현 작업 목록

| 단계 | 작업 | 산출물 | MVP 여부 |
|---:|---|---|---|
| 1 | 신규 mode enum 추가: `shared_load_only`, `l2_load_only`, `dram_load_only`, `store_only` | `include/config.hpp`, `src/main.cu` | 필수 |
| 2 | 각 신규 mode kernel 구현, checksum 소비 경로 포함 | `src/kernels.cu`, `include/kernels.cuh` | 필수 |
| 3 | `reuse_factor`, `load_repeat`, `store_repeat` CLI 옵션 추가 | `src/main.cu`, CSV notes/columns | 필수 |
| 4 | static expected bytes/op, expected stores/op, expected MMA count 컬럼 추가 | result CSV | 필수 |
| 5 | pair 고정 `ITER` runner 추가 | `scripts/run_component_pairs.py` | 필수 |
| 6 | paired-difference 분석 스크립트 작성 | `scripts/analyze_component_pairs.py` | 필수 |
| 7 | `reg_fragment_only`, `address_only`, `shared_init_only`, `matched_store_only` 추가 | kernels + modes | 확장 |
| 8 | regression 분석 스크립트 작성 | `scripts/fit_component_energy_model.py` | 확장 |
| 9 | NCU validation script를 신규 mode까지 확장 | `scripts/run_ncu_validation.sh` | 확장 |
| 10 | 보고서 generator 작성 | `results/summary/component_energy_<gpu>_<date>.md` | 확장 |

## 우선순위 제안

1. `shared_load_only`, `l2_load_only`, `dram_load_only`, `store_only`와 expected byte 컬럼부터 구현한다.
2. `reuse_factor`, `load_repeat`, `store_repeat`를 추가해 `N_MMA`와 bytes가 독립적으로 변하는지 확인한다.
3. RTX 3090에서 짧은 smoke run으로 CSV schema, checksum anti-optimization, paired-difference 계산을 검증한다.
4. PTX/SASS에서 load-only와 MMA mode의 instruction이 의도대로 남아 있는지 확인한다.
5. NCU permission이 풀리면 representative mode만 먼저 NCU 검증한다.
6. A100/H100/V100은 같은 binary/profile로 dry-run matrix를 먼저 확인한 뒤 실제 run을 진행한다.
7. 최종 보고서는 paired-difference 표를 중심으로 쓰고, 회귀 모델은 보조 검증으로 붙인다.

## 기대되는 개선점

| 기존 구조 | 제안 구조 |
|---|---|
| mode별 절대 pJ/FLOP 비교 | 같은 좌표에서 paired-difference 계산 |
| memory + MMA + stall 혼합 | `load_only`와 `mma`를 분리 |
| NCU 없으면 path 검증 약함 | static bytes 모델과 NCU sidecar를 병행 |
| GPU별 차이를 결과 후처리에서 설명 | profile-aware matrix와 report에서 선제 반영 |
| pJ/FLOP 중심 | pJ/FLOP + pJ/byte + residual까지 함께 보고 |

## 남는 한계

이 설계도 물리적 component energy를 직접 측정하지는 못한다. GPU 내부에서는 Tensor Core, register file, shared memory, L2, DRAM, scheduler, clock/power management가 동시에 동작한다. 따라서 최종 표현은 항상 “microbenchmark 조건에서의 effective component coefficient”로 제한해야 한다.

또한 `load_only` kernel이 `mma` kernel과 완전히 같은 dependency graph를 만들 수는 없다. 이 차이는 NCU stall metric과 instruction mix를 함께 보고 해석해야 한다.
