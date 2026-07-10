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
- GPU 세대별 power API 의미는 다르다. 최종 분석에서는 `nvmlDeviceGetTotalEnergyConsumption` 기반 `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_total_energy_supported=true` row를 우선하고, `GetPowerUsage` fallback row는 provisional로 둔다. 세부 기준은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다.
- Energy sweep 직후 `scripts/audit_power_api_measurements.py`를 실행한다. 새 finalplan에서는 `--require-explicit-measurement-scope`를 사용해 raw CSV에 `measurement_scope`가 직접 기록되었는지 확인한다. 이 단계에서 `final_candidate`가 아닌 row가 있으면 NCU path가 좋아도 최종 coefficient로 채택하지 않는다.
- Matched-control 이후 `scripts/audit_component_reliability.py`를 실행해 power/NCU/계수 안정성 gate를 결합한 verdict를 만든다.
- 따라서 최종 보고서는 “pure physical bitcell energy”가 아니라 “NCU로 path가 검증된 microbenchmark의 effective coefficient”로 쓴다.
- 계수는 NCU path 검증과 energy 차분/회귀 검증을 모두 통과해야 후보값으로 채택한다.

## 2. 아키텍처 기준

사용자가 지정한 NVIDIA whitepaper를 기준으로 capacity와 경로를 분리한다.

| GPU | Register file / SM | L1/shared / SM | L2 | Memory | 실험 설계 영향 |
|---|---:|---:|---:|---|---|
| RTX 3090, GA102 | 256 KiB | 128 KiB combined | 6 MiB | GDDR6X | L2/SM이 작고 L1/shared와 겹치므로 W_SM만으로 L2-only를 만들기 어렵다. L2는 `l2_cg_load_only`를 우선 사용한다. |
| A100, GA100 | 256 KiB | 192 KiB combined, shared allocation 최대 164 KiB | 40 MiB | HBM2 | 큰 L2라도 normal global load는 L1과 섞인다. strict L2는 `l2_cg_load_only`와 byte-ratio 검증을 사용한다. |

주의: CUDA에서 설정 가능한 dynamic shared memory 한계와 whitepaper의 물리 combined L1/shared capacity는 같은 값이 아닐 수 있다. 실험 채택은 capacity 계산이 아니라 NCU hit/access counter를 우선한다.

## 3. 기존 결과의 냉정한 판정

| 기존 항목 | 판정 | 이유 | 새 처리 |
|---|---|---|---|
| Tensor `0.146-0.170 pJ/FLOP` broad sweep | 후보값 | HMMA와 spill-free는 확인됐지만 no-MMA control 차분이며 reuse별 산포가 컸다. | RF=8/16 targeted 20초 반복 결과 0.107 pJ/FLOP를 blended candidate로 두고, RF=8 duration-scaling 0.143 pJ/FLOP와 RF=16 duration-scaling 0.077 pJ/FLOP로 RF-dependent range를 분리 보고한다. |
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
| Tensor control | `reg_operand_only` | HMMA 0이 원칙. legacy fixed epilogue는 block당 <= 1, expected register-op 대비 <= 1e-5일 때만 허용 |
| Shared scalar | `shared_scalar_load_only` | shared bytes/accesses 존재, expected shared bytes와 같은 order, bank conflict 0 또는 매우 낮음 |
| Global L1 | `global_l1_load_only` | L1 hit >= 95%, L2/L1 byte ratio <= 1%, DRAM/L1 byte ratio <= 1% |
| L2 hit | `l2_cg_load_only` | L2 hit >= 95%, L1 bytes/L2 bytes <= 1%, DRAM/L2 byte ratio <= 2% |
| DRAM sanity | `dram_cg_load_only` | L1 hit <= 1%, DRAM bytes가 충분, L2 hit은 `L2 capacity / working set` 기반 residual bound 내 |

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

Matched-control 분석은 다음 gate를 켠다.

| gate | 목적 |
|---|---|
| `--require-ncu-denominator` | memory pJ/byte에서 NCU actual traffic denominator가 없는 row 제외 |
| `--require-total-energy` | endpoint power fallback이 final coefficient에 섞이는 것 방지 |
| `--expected-power-semantics <profile>` | V100/A100 `instant`, RTX 3090/H100 `one_sec_average` metadata 확인 |
| `--pairing nearest-control` | 반복 run에서 treatment를 실행 순서상 가장 가까운 control과 비교해 thermal/clock drift 완화 |
| `--min-delta-j`, `--min-delta-fraction` | `delta_E`가 noise floor 안에 있는 양수 row를 최종 summary에서 제외 |

Power API gate는 `docs/platforms/power_measurement_api_matrix_ko.md`를 기준으로
아래처럼 해석한다.

| GPU | `GetPowerUsage` 의미 | final energy numerator | fallback 처리 |
|---|---|---|---|
| RTX 3090 / GA102 | 1초 평균 power | `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | provisional only |
| V100 / GV100 | instantaneous power | `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | provisional only |
| A100 / GA100 | instantaneous power | `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | provisional only |
| H100 / GH100 | 1초 평균 power | GPU/device total-energy mJ 차분 | module/memory power와 분리, provisional only |

즉, 세대별 power sample 의미는 metadata와 fallback 해석을 바꾸지만, 최종
pJ/FLOP 또는 pJ/bit의 분자는 가능한 한 세대 공통으로 total-energy counter 차분을
쓴다. total-energy counter가 없으면 그 결과는 component coefficient final 표가 아니라
fallback/provisional 표로 분리한다.

```text
delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s
coefficient = delta_E_J / denominator
```

| Component | numerator | control | denominator |
|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | FLOP |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes 우선, expected shared bytes fallback |
| Global L1 path | `global_l1_load_only` | `global_addr_only` | NCU L1 bytes 우선, expected L1 bytes fallback |
| L2 hit path | `l2_cg_load_only` | `global_addr_only` | NCU L2 bytes 우선, expected L2 bytes fallback |
| DRAM sanity path | `dram_cg_load_only` | `global_addr_only` | NCU DRAM bytes 우선, expected DRAM bytes fallback |

음수 coefficient는 component energy로 채택하지 않는다. 단순히 0으로 클리핑하지 않고 `not_identified_or_control_failed`로 기록한다.

## 5. 이번 RTX 3090 실행 계획

이번 실행은 “최종 논문값”이 아니라 final-quality로 가기 위한 강한 재현성 점검이다. 목표는 음수 row가 줄어드는지, NCU path 검증과 energy 계수가 같은 방향인지 확인하는 것이다.

### 5.1 NCU 검증

대표 LR=4 검증은 빠른 preflight에는 유용하지만, 최종 coefficient에서는
energy sweep과 같은 `reuse_factor`/`load_repeat` list를 NCU sidecar에서도 수집한다.
`scripts/run_ncu_validation.sh`는 다음 환경변수를 받는다.

| 환경변수 | 최종 권장값 | 의미 |
|---|---|---|
| `TENSOR_REUSE_FACTORS` | `1,2,4,8,16` | `reg_operand_only`, `reg_mma` Tensor/control sweep |
| `MEMORY_LOAD_REPEATS` | `1,2,4,8,16` | shared, global L1, L2 path sweep |
| `DRAM_LOAD_REPEATS` | `1,4,8,16` | DRAM streaming sanity sweep; energy LR 4,8,16과 exact coordinate를 맞춤 |

빠른 대표 검증을 수행할 때의 최소 좌표는 다음이다.

| Component | blocks/SM | W_SM (KiB) | representative factor | 이유 |
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
| Global L1 | `global_addr_only`, `global_l1_load_only` | 16 | 16,64 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 | 5 | 3 |
| L2 hit | `global_addr_only`, `l2_cg_load_only` | 16 | 64 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 | 5 | 3 |
| DRAM sanity | `global_addr_only`, `dram_cg_load_only` | 16 | 8192 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 | 5 | 3 |

주의: 현재 primary runner는 duration-calibrated 방식이다. 따라서 `load_repeat`를
2배로 늘리면 `ITER`가 줄어 목표 실행 시간을 맞추기 때문에 총 byte denominator가
반드시 2배로 늘지는 않는다. `load_repeat` sweep은 path의 instruction mix/rate 안정성을
보는 축이고, 총 denominator scaling을 확인하려면 같은 `load_repeat`에서 duration sweep
또는 fixed-ITER 보조 실험을 별도로 수행한다. RTX 3090 L1에서는 `load_repeat=4`,
10/20/30초 duration-scaling check가 기존 0.15 pJ/bit 결과와 정합했다.
Tensor도 같은 이유로 broad `reuse_factor` sweep만으로 단일 상수를 확정하지 않는다.
RTX 3090에서는 RF=8/16, 20초, 6회 targeted follow-up이 12/12 valid와
0.107 pJ/FLOP median을 보여 lower-side Tensor reporting candidate로 둔다. 같은
RF=8/16에서 `ITER=8000000`을 고정한 fixed-ITER 보조실험은 10/10 valid와
0.146 pJ/FLOP median을 보였다. 추가 RF=8 duration-scaling은 15/15 valid,
0.143 pJ/FLOP median, 0.144-0.156 pJ/FLOP slope를 보였다. RF=16
duration-scaling은 15/15 valid, 0.077 pJ/FLOP median, 0.053-0.071 pJ/FLOP slope를
보였다. 따라서 Tensor는 단일 회로 상수가 아니라 RF-dependent effective coefficient로
표기한다. 현재 RTX 3090 조건에서는 RF16 lower 약 0.06-0.09 pJ/FLOP, RF8 upper 약
0.14-0.15 pJ/FLOP다.

성공 기준:

| 기준 | 통과 조건 |
|---|---|
| execution | 모든 row `smid_histogram_ok=true`, elapsed >= 4 s |
| Tensor | reuse sweep에서 음수 coefficient 0 또는 원인 설명 가능 |
| Shared scalar | 모든 load_repeat에서 양수, NCU shared path accepted |
| Global L1 | 음수 row가 남으면 final에서 제외 또는 control 재설계 |
| L2 | L2 hit >= 95%, DRAM/L2 <= 2%, long scoreboard를 결과 표에 포함 |
| DRAM | sanity check로만 사용, physical DRAM energy라고 쓰지 않음 |

Tensor/register NCU acceptance는 absolute memory byte threshold와 함께
bytes/HMMA 또는 bytes/register-op ratio를 확인한다. reuse factor가 커질수록
setup/cache traffic의 absolute byte도 커질 수 있으므로, absolute byte만으로 reject하면
RF가 큰 row가 불리해진다.

## 6. V100/A100 확장 계획

V100은 RTX 3090과 L2 용량은 비슷하지만 SM 수, 최대 blocks/SM, warp residency,
combined L1/shared 구조와 NCU toolchain 지원 범위가 다르므로 별도 좌표를 사용한다.

| Step | V100 확인 내용 |
|---|---|
| preflight | profile `v100`, CUDA 12.x 권장 compiler의 `compute_70` 지원, `sm_70`, runtime 80 SM, 32GB reference memory >= 30,000 MiB, NVML total energy support |
| blocks sweep | energy B=1,2,4,8,16,32; strict NCU 대표 B=32. one warp/block이라 이론상 64 warps/SM의 50%이며, 실제 residency는 achieved occupancy/registers/shared-block NCU evidence로 확인 |
| shared | energy W_SM 32/64 KiB; strict NCU W32/B32. W64/B32는 96 KiB capacity 경계 stress point |
| global L1 | energy W_SM 8/16/32 KiB; strict NCU W32/B32. 기존 W8/B16은 block당 1 KiB tile 미만이라 폐기 |
| L2 final path | `l2_cg_load_only - global_addr_only`; strict W32/B32 = 2.5 MiB total, W64 = 5 MiB stress point |
| Tensor | `reg_mma - reg_operand_only`, energy B=1-32, strict NCU B32, reuse 1-16 |
| NCU | 2024.3 GV100 지원 확인. `--list-chips`, `--query-metrics --chips gv100`, exact-coordinate hit/access/byte/stall/HMMA evidence 필수 |
| power | `nvml_total_energy`, `total_energy_mj_delta`, device total-energy scope, `instant` semantics만 final candidate |

A100 노드에서는 RTX 3090 결과를 이식하지 않고 같은 acceptance-first 절차를 반복한다.

| Step | A100 확인 내용 |
|---|---|
| preflight | profile `a100`, runtime SM 수, NVML energy support, NCU metric support |
| power API audit | energy sweep CSV가 `nvml_total_energy`, `total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=instant` 조건을 만족하는지 확인 |
| shared/L1 | `shared_scalar_load_only` W_SM 64/128 KiB. Global L1은 strict W16/B16, diagnostic W32/B16 및 W32/B32; invalid W16/B32는 treatment/control 모두 자동 제외 |
| L2 final path | `l2_cg_load_only - global_addr_only`, W_SM 64/128 KiB에서 L2 hit plateau와 L1 bytes/L2 bytes <= 1% 확인 |
| L2 diagnostic | `l2_load_only`는 normal global load라 L1과 섞일 수 있으므로 strict coefficient에서 제외 |
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
| Reliability audit | component/path, verdict, cautions, reject reasons |
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
