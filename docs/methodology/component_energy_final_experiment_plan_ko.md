# Component Energy 최종 실험 계획

작성일: 2026-07-05, updated 2026-07-15

## 1. 실험 목표

이 실험의 목표는 RTX 3090, A100, V100과 H100 확장 profile에서 다음 경로의
**board-level effective energy coefficient**를 합리적으로 분리하는 것이다.

| 목표 항목 | 목표 단위 | 채택 가능한 해석 |
|---|---:|---|
| Tensor MMA incremental | pJ/FLOP | no-MMA register/control 대비 FP16 WMMA 추가 에너지 |
| Register operand/control | pJ/reg-op 또는 진단값 | spill-free register/control workload의 board-level proxy |
| Shared memory scalar path | pJ/bit | shared-memory load instruction path의 effective traffic energy |
| Global L1 hit path | pJ/bit | global load가 L1 hit로 끝나는 path의 effective traffic energy |
| L2 hit path | pJ/bit | L1을 배제하고 L2 hit로 끝나는 path의 effective traffic energy |
| External-memory read path | effective pJ/bit | SM-to-HBM/GDDR 전체 read service path; 물리 memory-device energy가 아님 |

중요한 제한은 다음과 같다.

- NVML energy는 보드/디바이스 전체 에너지다. Tensor Core, register file, scheduler, LSU, interconnect, cache, memory controller, DRAM, clock/power-state 변화가 함께 들어간다.
- GPU 세대별 power API 의미는 다르다. 최종 분석에서는 `nvmlDeviceGetTotalEnergyConsumption` 기반 `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_total_energy_supported=true` row를 우선하고, `GetPowerUsage` fallback row는 provisional로 둔다. 세부 기준은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다.
- Energy sweep 직후 `scripts/audit_power_api_measurements.py`를 실행한다. 새 finalplan에서는 `--require-explicit-measurement-scope --require-exact-measurement-interval`을 사용해 raw CSV에 `measurement_scope`와 timed-kernel 시작/종료 epoch가 직접 기록되었는지 확인한다. 이 단계에서 `final_candidate`가 아닌 row가 있으면 NCU path가 좋아도 최종 coefficient로 채택하지 않는다.
- Matched-control 이후 `scripts/audit_component_reliability.py`를 실행해 power/NCU/계수 안정성 gate를 결합한 verdict를 만든다.
- Final analyzer는 `--require-control-ncu-acceptance`를 사용한다. Tensor의 `reg_operand_only`와 Global L1/L2/DRAM의 `global_addr_only`가 treatment와 같은 좌표에서 NCU accepted가 아니면 해당 pair를 최종 계수에 사용하지 않는다.
- 따라서 최종 보고서는 “pure physical bitcell energy”가 아니라 “NCU로 path가 검증된 microbenchmark의 effective coefficient”로 쓴다.
- 계수는 NCU path 검증과 energy 차분/회귀 검증을 모두 통과해야 후보값으로 채택한다.

## 2. 아키텍처 기준

사용자가 지정한 NVIDIA whitepaper를 기준으로 capacity와 경로를 분리한다.

| GPU | Register file / SM | L1/shared / SM | L2 | Memory | 실험 설계 영향 |
|---|---:|---:|---:|---|---|
| RTX 3090, GA102 | 256 KiB | 128 KiB combined | 6 MiB | GDDR6X | L2/SM이 작고 L1/shared와 겹치므로 W_SM만으로 L2-only를 만들기 어렵다. L2는 `l2_cg_load_only`를 우선 사용한다. |
| V100, GV100 | 256 KiB급 | 128 KiB combined, shared allocation 96 KiB profile | 6 MiB | HBM2 | B4/B16 utilization 민감도와 strict B32 anchor를 측정한다. Volta 지원 CUDA/NCU 조합을 별도로 확인한다. |
| A100, GA100 | 256 KiB | 192 KiB combined, shared allocation 최대 164 KiB | 40 MiB | HBM2 | 큰 L2라도 normal global load는 L1과 섞인다. strict L2는 `l2_cg_load_only`와 path-specific L1 hit/L2 read 검증을 사용한다. |
| H100, GH100 | 256 KiB급 | 256 KiB combined, shared allocation 228 KiB profile | 50 MiB | HBM2e/HBM3, SKU별 상이 | 현재 kernel은 WMMA compatibility path이며 Hopper-native WGMMA/TMA 계수로 해석하지 않는다. |

주의: CUDA에서 설정 가능한 dynamic shared memory 한계와 whitepaper의 물리 combined L1/shared capacity는 같은 값이 아닐 수 있다. 실험 채택은 capacity 계산이 아니라 NCU hit/access counter를 우선한다.

## 3. 기존 결과의 냉정한 판정

| 기존 항목 | 판정 | 이유 | 새 처리 |
|---|---|---|---|
| Tensor v1-v4, A100 v5 | superseded/rejected | v1은 RF별 HMMA 비례성이 깨졌고, v2는 장시간 양의 FP32 누적이 정체될 수 있다. v3는 predicated HMMA 두 경로를 발행했고 v4 control loop는 제거됐다. A100 v5 control은 10억 ITER가 약 1 ms에 종료되어 pair calibration을 오염시켰다. | v6는 두 mode의 inner loop에 runtime clock token을 추가하고 static token-loop, 50 ms trial, 6x stretch, 180 s timeout을 모두 요구 |
| Global L1 `0.449 pJ/bit` | 후보값 미만 | L1 hit path는 맞지만 energy row 6개 중 2개가 음수였다. | 음수 row가 사라지는지 seconds/repeats를 늘려 재실험한다. |
| L2 `0.798 pJ/bit` | 후보값 | CG L2 path는 맞지만 long scoreboard가 크고 1개 음수 row가 있었다. | L2는 stall을 보고하고, pJ/bit를 L2 SRAM 단독값으로 부르지 않는다. |
| External-memory 기존 전달값: RTX 25.510, A100 11.925, V100 8.131 pJ/bit | historical observation | raw/NCU scope가 완전히 재현되지 않았고 total/expected denominator, 압축 가능 입력, 단일 W 문제가 있었다. | RTX는 high-entropy/W sweep/read-only denominator로 24.949 pJ/bit 재측정 완료; A100/V100은 재실험한다. |
| Register direct `263 pJ/update` | 폐기 | scalar ALU, dependency, scheduler/control, active power를 작은 update 수로 나눈 값이다. | pure register-file energy로 쓰지 않는다. |

## 4. 실험 분리 원칙

### 4.1 NCU path acceptance

energy 계수는 아래 NCU 기준을 통과한 mode만 사용한다.

| Path | mode | NCU 채택 기준 |
|---|---|---|
| Tensor | `reg_mma` | HMMA instruction > 0, spill/local memory 0, L1/L2/DRAM traffic이 작음 |
| Tensor control | `reg_operand_only` | HMMA=정확히 0, spill/local=0, `SR_CLOCKLO` token이 static backward loop 내에 존재, runtime SASS/expected register op>=0.1, treatment와 동일 ITER |
| Shared scalar | `shared_scalar_load_only` | shared bytes/accesses 존재, expected shared bytes와 같은 order, bank conflict 0 또는 매우 낮음 |
| Global L1 | `global_l1_load_only` | path-specific L1 hit >=95%, L1 request/hit bytes 존재, L2 read/L1 request <=1%, DRAM/L1 request <=1% |
| L2 hit | `l2_cg_load_only` | architecture-specific final L2 service >=95%, L1 path hit <=1%, L1 hit/request bytes <=1%, DRAM-read/source-L2-read <=2%. GA100은 source+LTC-fabric logical hit와 native-model coherence 사용 |
| External-memory read | `dram_cg_load_only` | L1 hit <=1%, final L2 hit <=10%, source/expected 0.95-1.05, DRAM read/source >=0.90, write/read <=0.01, spill 0 |

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

Energy run은 NCU 없이 실행한다. 모든 final pair는 각 좌표에서 treatment 목표시간과
control 최소시간을 각각 calibrate하고 두 ITER 중 큰 값을 두 mode에 동일하게
적용한 뒤 net energy를 직접 차분한다. Tensor pair는 각 RF에서 `reg_mma`의 treatment 목표시간과
`reg_operand_only`의 control 최소시간을 각각 calibrate하고, 두 ITER 중 큰 값을 treatment와
control에 동일하게 적용한 뒤 net energy를 직접 차분한다.
`reg_mma`와 `reg_operand_only`는 A/B/C fragment 선언, dependent scalar update,
in-place A-sign flip, source epilogue를 공통으로 두되 treatment만 MMA를 발행한다.
A fragment의 FP16 sign bit를 매 logical MMA 후 뒤집어 accumulator를 bounded 상태로
유지한다. v6는 최종 scalar sink를 공통 output에 기록하고 두 mode의
inner step에서 `SR_CLOCKLO` runtime token을 소비해 control 반복문의 제거를
막는다. ptxas 최적화 후 control의
register footprint가 더 작으므로 결과는 pure Tensor 회로 에너지가 아니다.
Shared는 동일 dynamic shared allocation, 초기화, index/checksum loop를 유지하되
반복 shared read만 제거한 `shared_scalar_addr_only`를 control로 쓴다. Global L1/L2/DRAM은
`global_addr_only`를 control로 쓴다. L2와 DRAM pair도 각각 `l2_cg_load_only`/`dram_cg_load_only` treatment와
`global_addr_only` control을
dual-calibrate하고 동일 ITER를 적용한 뒤 두 net energy를 직접 차분한다.

Matched-control 분석은 다음 gate를 켠다.

| gate | 목적 |
|---|---|
| `--require-ncu-denominator` | memory pJ/byte에서 NCU actual traffic denominator가 없는 row 제외 |
| `--require-total-energy` | endpoint power fallback이 final coefficient에 섞이는 것 방지 |
| `--expected-power-semantics <profile>` | V100/A100 `instant`, RTX 3090/H100 `one_sec_average` metadata 확인 |
| `--pairing nearest-control` | 반복 run에서 treatment를 실행 순서상 가장 가까운 control과 비교해 thermal/clock drift 완화 |
| `--tensor-pair-policy matched-iters` | Tensor의 동일 ITER를 확인하고 `E_reg_mma - E_reg_operand_only` 직접 차분 |
| `--shared-pair-policy matched-iters` | Shared treatment/control의 동일 ITER를 확인하고 `E_shared_load - E_shared_addr` 직접 차분 |
| `--l1-pair-policy matched-iters` | Global L1 treatment/address control의 동일 ITER를 확인하고 net energy 직접 차분 |
| `--l2-pair-policy matched-iters` | L2 CG와 address control의 동일 ITER를 확인하고 net energy 직접 차분 |
| `--dram-pair-policy matched-iters` | DRAM treatment/control의 동일 ITER를 확인하고 `net_E_dram - net_E_addr` 직접 차분 |
| `--require-control-ncu-acceptance` | treatment뿐 아니라 no-MMA/address control도 동일 좌표 NCU acceptance를 요구 |
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
delta_E_component_J = net_E(treatment, ITER=N)
                    - net_E(matched_control, ITER=N)
coefficient = delta_E_J / denominator
```

| Component | numerator | control | denominator |
|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | FLOP |
| Shared scalar path | `shared_scalar_load_only` | `shared_scalar_addr_only` | NCU shared read bytes 우선, expected shared bytes fallback |
| Global L1 path | `global_l1_load_only` | `global_addr_only` | NCU L1 bytes 우선, expected L1 bytes fallback |
| L2 hit path | `l2_cg_load_only` | `global_addr_only` | NCU L2 bytes 우선, expected L2 bytes fallback |
| External-memory read path | `dram_cg_load_only` | `global_addr_only` | strict NCU `dram__bytes_read.sum`; fallback 금지 |

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
| `MEMORY_LOAD_REPEATS` | `4,8,16` | shared, global L1, L2의 energy와 exact-coordinate NCU 공통 sweep |
| `DRAM_LOAD_REPEATS` | `4,8,16` | external-memory read path의 energy와 exact-coordinate NCU 공통 sweep |
| `DRAM_W_SM_KIB_VALUES` | profile별 표 참조 | nominal L2 배수 working-set sweep |

빠른 대표 검증을 수행할 때의 최소 좌표는 다음이다.

| Component | blocks/SM | W_SM (KiB) | representative factor | 이유 |
|---|---:|---:|---:|---|
| Tensor | profile 대표 B | N/A (CLI placeholder 1) | reuse 4 | HMMA/spill과 register footprint 확인 |
| Shared scalar | 16 | 64 | load_repeat 4 | shared bytes와 bank conflict 확인 |
| Global L1 | 16 | 16 | load_repeat 4 | L1 hit path 확인 |
| L2 hit | 16 | 64 | load_repeat 4 | RTX 3090은 CG path로 L1을 배제 |
| External-memory read | 16 | RTX/V100 256-2048; A100/H100 2048-8192 | load_repeat 4 | L2 capacity transition과 external-read dominance 확인 |

### 5.2 Energy 재실험

| Component | modes | blocks/SM | W_SM (KiB) | factor sweep | seconds (s) | repeats |
|---|---|---:|---:|---:|---:|---:|
| Tensor | `reg_operand_only`, `reg_mma` | profile별 B sweep | N/A (CLI placeholder 1) | reuse 1,2,4,8,16 | 5 | 3 |
| Shared scalar | `shared_scalar_addr_only`, `shared_scalar_load_only` | profile memory anchor | profile별 표 참조 | load_repeat 4,8,16 | 10 | 5 |
| Global L1 | `global_addr_only`, `global_l1_load_only` | profile memory anchor | profile별 표 참조 | load_repeat 4,8,16 | 10 | 5 |
| L2 hit | `global_addr_only`, `l2_cg_load_only` | fixed anchor 또는 NCU-selected B | profile별 두 W anchor | load_repeat 4,8,16 | 10 | 5 |
| External-memory read | `global_addr_only`, `dram_cg_load_only` | profile memory anchor | RTX/V100 256,512,2048; A100/H100 2048,4096,8192 | load_repeat 4,8,16 | 10 | 5 |

주의: 과거 Shared/L1 duration-scaled power 차분은 memory stall이 issue activity를
낮출 때 control power가 treatment power보다 커져 음수 계수를 만들 수 있었다.
현행 protocol은 동일 ITER 완료 energy를 직접 비교한다. 이 값은 latency로 늘어난
board baseline/scheduler 시간까지 포함한 effective completion-energy coefficient이며,
순수 SRAM bitcell energy가 아니다.
과거 RTX 3090 Tensor v1 `0.077-0.170 pJ/FLOP`와 fixed-RF v2 median
`2.2525 pJ/FLOP`는 모두 역사적 민감도 자료다. v2는 NCU 10/10과 energy pair
33/35를 통과했지만 장시간 constant-positive FP32 accumulation 정체 가능성이 뒤늦게
확인되어 superseded되었다. v3도 predicated dual-HMMA codegen 때문에 reject했다.
v4의 RTX 3090 treatment NCU 선형성은 통과했지만 control loop 제거를 검출하지 못해
현행 근거로 사용할 수 없다. v5도 GA102에서는 통과했지만 A100에서
launch-only control과 과대 ITER를 만들었다. 각 GPU에서 v6 runtime-token-loop binary audit,
calibration trial `>=0.05 s`, ITER stretch `<=6x`, runtime SASS/register-op 및 HMMA/FLOP
gate를 통과한 새 board-energy run으로만 coefficient를 만든다.

성공 기준:

| 기준 | 통과 조건 |
|---|---|
| execution | 모든 row `smid_histogram_ok=true`, elapsed >= 4 s |
| Tensor | 동일 ITER, treatment/control trial>=0.05 s, control/treatment ITER ratio<=6, control HMMA=0, 두 mode runtime-token loop>0, control SASS/expected-op>=0.1, treatment `HMMA/logical MMA` RF spread<=10%, spill/local=0, RF별 최소 5 valid pair, pair timestamp gate, `delta_E>=10 J`, coefficient>0 |
| Shared scalar | 모든 load_repeat에서 양수, NCU shared path accepted |
| Global L1 | 음수 row가 남으면 final에서 제외 또는 control 재설계 |
| L2 | final L2 service >=95%, DRAM-read/source-L2-read <=2%, long scoreboard를 결과 표에 포함. GA100은 direct/native lookup 수치를 final hit로 오인하지 않음 |
| External-memory read path | NCU actual read-byte와 경로 gate를 통과한 effective GPU-device coefficient로만 사용하고 physical HBM/GDDR energy라고 쓰지 않음 |

Tensor/register NCU acceptance는 absolute memory byte threshold와 함께
bytes/HMMA 또는 bytes/register-op ratio를 확인한다. reuse factor가 커질수록
setup/cache traffic의 absolute byte도 커질 수 있으므로, absolute byte만으로 reject하면
RF가 큰 row가 불리해진다.

## 6. V100/A100/H100 확장 계획

### 6.1 RTX 3090/A100/V100/H100 파라미터와 실험 개수 비교

아래 표는 `scripts/plan_platform_component_experiment.py`의 현재 기본 profile로
GPU 한 장에서 새 표준 package를 실행하는 조건이다. 공통으로 energy command당
`seconds=10 s`, 유효 좌표당 `repeats=5 count`, `store_repeat=1 count`를 사용하며,
energy 측정과 NCU profiling은 분리한다. 개수는 2026-07-14에
`run_component_regression_sweep.py` dry-run matrix와 `run_ncu_validation.sh`의
`DRY_RUN_NCU=1` case manifest로 다시 검산했다.

| 파라미터 | RTX 3090 / GA102 | A100 / GA100 | V100 / GV100 | H100 / GH100 | 단위/조건 |
|---|---|---|---|---|---|
| CUDA arch / active SM | `sm_86` / 82 | `sm_80` / 108 | `sm_70` / 80 | `sm_90` / 132 | SM count는 full-GPU profile 기준이며 runtime preflight와 다르면 중단 |
| memory-path energy blocks/SM | 8 | 16 | 32 | 16 | blocks/SM; exact-coordinate NCU와 같은 단일 anchor, Tensor는 별도 sweep |
| Tensor blocks/SM | 4,8,16 | 4,16,32 | 4,16,32 | 4,16,32 | blocks/SM; energy와 NCU에서 모두 수행 |
| strict NCU blocks/SM | Tensor 4/8/16; memory 8 | Tensor 4/16/32; memory 16; L2 selector | Tensor 4/16/32; memory 32; L2 selector | Tensor 4/16/32; memory 16; L2 selector | blocks/SM |
| Tensor W_SM / RF | N/A (CLI 1) / 1,2,4,8,16 | 동일 | 동일 | 동일 | W_SM은 parser placeholder, RF는 inner MMA grouping count |
| Shared scalar W_SM | 64 | 128 | 32 | 128 | KiB/SM; shared allocation 안의 한 architecture anchor |
| Global L1 W_SM | 8 | 16 | 32 | 16 | KiB/SM; 작은 cached-global working set anchor |
| L2 CG W_SM | 32,64 | 16,128 | 32,64 | 64,128 | KiB/SM; 두 endpoint 모두 exact NCU를 가져야 함 |
| External-memory W_SM | 256,512,2048 | 2048,4096,8192 | 256,512,2048 | 2048,4096,8192 | KiB/SM; nominal L2보다 큰 low/mid/high 세 점 |
| memory energy LR | 4,8,16 | 4,8,16 | 4,8,16 | 4,8,16 | load repeat, count |
| Tensor NCU RF | 1,2,4,8,16 | 동일 | 동일 | 동일 | count |
| Shared/L1/L2 NCU LR | 4,8,16 | 동일 | 동일 | 동일 | count; energy LR와 exact match |
| DRAM NCU LR | 4,8,16 | 동일 | 동일 | 동일 | count; energy LR와 exact match |
| fallback power semantics | 1초 평균 | instantaneous | instantaneous | 1초 평균 | final numerator는 모두 NVML total-energy mJ delta만 허용 |

#### 6.1.1 Sweep 선택 근거와 시각화

![플랫폼별 blocks/SM sweep](../presentations/assets/platform_blocks_per_sm_sweep.png)

Tensor는 utilization 민감도를 보기 위해 세 B 점을 유지한다. Memory path는 coefficient에
사용되는 모든 energy row가 동일 좌표의 NCU row를 가져야 하므로 RTX/V100/A100/H100에서
각각 B8/B32/B16/B16 한 점만 실행한다. A100/V100/H100 L2는 이 anchor를 시작점으로
NCU precheck가 architecture별 fallback B를 고를 수 있고, 선택된 한 B를 energy와 final
minimal NCU에 동일 적용한다. 요청 B는 실제 동시 residency를 보장하지 않으므로 SMID와
NCU occupancy/resource evidence로 검증한다.

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

Shared W는 shared allocation capacity와 `W_SM + blocks/SM` 보수적 예약량을 기준으로
RTX/V100/A100/H100에서 각각 W64/W32/W128/W128 한 점을 유지한다. Global L1도 각각
W8/W32/W16/W16 한 점만 남겼다. 제거한 W는 path discovery에는 쓸 수 있지만 exact NCU가
없어 strict coefficient에 쓰이지 않던 중복 energy 좌표였다.

Global L1 W는 작은 cached-global working set과 block당 최소 1 KiB tile을 동시에
만족하도록 선택한다. L2 W는 `active_SM * W_SM`이 nominal L2 안에 남도록 하면서 `.cg`로
L1 hit를 억제한다. External-memory W는 full-GPU working set을 nominal L2의 여러
배로 바꾸며 capacity transition을 측정한다. 이 세 경로는 W 값만으로 판정하지 않고 NCU path-specific hit/access/bytes로
최종 분류한다. Shared는 별도 address space이므로 이 Global L1-L2-DRAM 전이와 분리한다.

![strict anchor capacity 맥락](../presentations/assets/platform_capacity_context.png)

그래프의 비율은 measured hit rate가 아니라 nominal design context다. L2는 각 GPU에서
두 endpoint만 유지한다: RTX W32/W64, V100 W32/W64, A100 W16/W128, H100 W64/W128.
두 점 모두 exact-coordinate minimal NCU를 통과해야 하며, plateau가 없으면 coefficient를
만들지 않는다. 더 촘촘한 W는 selector 실패 원인을 찾는 별도 discovery sweep으로만
실행하고 strict package에 자동 포함하지 않는다.

Memory-backed mode는 block당 최소 1 KiB tile을 요구하므로
`W_SM (KiB) >= blocks/SM`인 좌표만 실행한다. 기본 package의 energy 좌표는 모두 이
조건을 만족하며, reduced-SM/MIG/vGPU에서는 `active_SM * W_SM`으로 L2/streaming regime을
다시 계산한다.

| Path | RTX 3090 유효 W/B | A100 유효 W/B | V100 유효 W/B | H100 유효 W/B | 제외 조건 |
|---|---|---|---|---|---|
| Global L1 | W8/B8 | W16/B16 | W32/B32 | W16/B16 | 한 architecture anchor만 energy/NCU에 동일 사용 |
| L2 CG | W32,64/B8 | selector W16,128/B16,8,4,2,1 | selector W32,64/B32,16,4 | selector W64,128/B16,8 | selector가 두 W를 모두 통과한 B 하나만 energy/final NCU에 전달 |

아래 `유효 좌표`는 treatment와 control command를 모두 포함한 1회 반복 기준이다.
`energy raw rows`는 이 값에 `repeats=5`를 곱한 값이다. Schema smoke,
Tensor calibration, NCU sidecar는 서로 다른 단계이므로 energy raw rows에 합산하지 않는다.

| Component/path | RTX 3090 유효 좌표 / raw rows | A100 유효 좌표 / raw rows | V100 유효 좌표 / raw rows | H100 유효 좌표 / raw rows | 좌표 계산 |
|---|---:|---:|---:|---:|---|
| Tensor | 30 / 150 | 30 / 150 | 30 / 150 | 30 / 150 | 2 modes x B 3개 x RF 5개 |
| Shared scalar | 6 / 30 | 6 / 30 | 6 / 30 | 6 / 30 | 2 modes x W 1개 x B 1개 x LR 3개 |
| Global L1 | 6 / 30 | 6 / 30 | 6 / 30 | 6 / 30 | 2 modes x W/B 1개 x LR 3개 |
| L2 CG | 12 / 60 | 12 / 60 | 12 / 60 | 12 / 60 | 2 modes x W 2개 x selected/fixed B 1개 x LR 3개 |
| External-memory read | 18 / 90 | 18 / 90 | 18 / 90 | 18 / 90 | 2 modes x W 3개 x B 1개 x LR 3개 |
| **합계** | **72 / 360** | **72 / 360** | **72 / 360** | **72 / 360** | 유효 commands / expected CSV rows |

| 별도 실행 단계 | RTX 3090 | A100 | V100 | H100 | 의미 |
|---|---:|---:|---:|---:|---|
| feasibility 전 candidate matrix | 72 rows | 72 rows | 72 rows | 72 rows | 각 strict energy coordinate가 exact NCU coordinate와 일치 |
| feasibility 제외 | 0 rows | 0 rows | 0 rows | 0 rows | 기본 package; 사용자 override는 별도 검증 |
| schema/revision smoke | 3 rows | 3 rows | 3 rows | 3 rows | full sweep 전 CSV schema와 kernel marker 확인 |
| Tensor pair calibration | 15 coordinates / 30 commands | 15 / 30 | 15 / 30 | 15 / 30 | B x RF 좌표마다 treatment/control-floor calibration 2회 |
| Shared/L1 pair calibration | 각 3 coordinates / 6 commands | 동일 | 동일 | 동일 | W 1 x B 1 x LR 3 |
| L2 pair calibration | 6 coordinates / 12 commands | 동일 | 동일 | 동일 | selected/fixed B의 W 2 x LR 3 |
| External-memory pair calibration | 9 coordinates / 18 commands | 동일 | 동일 | 동일 | W 3 x B 1 x LR 3 |
| primary NCU sidecar | 73 cases | 73 cases | 73 cases | 73 cases | full Tensor/Shared/L1 43 + minimal L2 12 + minimal external 18; selector precheck 별도 |
| 최대 L2 precheck | 0 cases | 56 cases | 16 cases | 24 cases | 후보당 W 2 x LR4 x treatment/control 2 cases; 첫 pass에서 조기 종료 가능 |
| nominal energy kernel time | 3,600 s | 3,600 s | 3,600 s | 3,600 s | raw rows x 10 s; calibration/launch/cooling/NCU/precheck 별도 |

상세 계산식, generated strict anchor와 기존 RTX 3090 accepted B16 결과의 구분은
[cross-platform component experiment guide](../platforms/cross_platform_component_experiment_guide_ko.md)의
4.0-4.5절을 기준으로 한다. 계획 좌표는 target-node acceptance를 통과한
실측 결과가 아니라 실행 계획이다.

### 6.2 V100 세부 조건

V100은 RTX 3090과 L2 용량은 비슷하지만 SM 수, 최대 blocks/SM, warp residency,
combined L1/shared 구조와 NCU toolchain 지원 범위가 다르므로 별도 좌표를 사용한다.

| Step | V100 확인 내용 |
|---|---|
| preflight | profile `v100`, CUDA 12.x 권장 compiler의 `compute_70` 지원, `sm_70`, runtime 80 SM, 32GB reference memory >= 30,000 MiB, NVML total energy support |
| blocks sweep | Tensor만 B=4,16,32; Shared/L1/DRAM은 energy와 NCU 모두 B32. L2는 normal contiguous B32 뒤 sm_interleaved B32/B16/B4 중 strict-pass B 선택 |
| shared | energy/NCU 모두 W32/B32. W64/B32 capacity 경계점은 별도 discovery 진단으로 이동 |
| global L1 | energy/NCU 모두 W32/B32. 작은 W/B 진단점은 final package에서 제외 |
| L2 final path | `l2_cg_load_only - global_addr_only`; W32/W64 두 anchor에서 selected B와 normal residency를 검증. V100은 persisting policy 금지 |
| Tensor | `reg_mma - reg_operand_only`, energy와 NCU 모두 B=4,16,32, reuse 1-16 |
| NCU | 2024.3 GV100 지원 확인. `--list-chips`, `--query-metrics --chips gv100`, exact-coordinate hit/access/byte/stall/HMMA evidence 필수 |
| power | `nvml_total_energy`, `total_energy_mj_delta`, device total-energy scope, `instant` semantics만 final candidate |

### 6.3 A100 세부 조건

A100 노드에서는 RTX 3090 결과를 이식하지 않고 같은 acceptance-first 절차를 반복한다.

| Step | A100 확인 내용 |
|---|---|
| preflight | profile `a100`, runtime SM 수, NVML energy support, NCU metric support |
| power API audit | energy sweep CSV가 `nvml_total_energy`, `total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=instant` 조건을 만족하는지 확인 |
| shared/L1 | Shared W128/B16, Global L1 W16/B16을 energy/NCU에 동일 사용한다. 두 path 모두 pair-locked 동일 ITER 직접 차분 |
| L2 final path | `l2_cg_load_only - global_addr_only`, W_SM 16/128 KiB. NCU-first에서 B16/8/4/2/1과 normal/persisting, contiguous/sm_interleaved 후보를 검사한다. `l2_path_minimal`에서 device/TEX source와 `srcunit_ltcfabric` hit/miss를 같은 replay로 수집하고 logical final hit >=95%, source/fabric 보존, native-model 오차 <=2 pp, L1 hit/request bytes <=1%, expected traffic, DRAM-read leakage를 모두 통과한 경우만 선택한다. direct/native hit 자체에는 95%를 강제하지 않는다. L1 request bytes 자체는 허용하고 warm-up도 `ld.global.cg` 사용 |
| L2 diagnostic | `l2_load_only`는 normal global load라 L1과 섞일 수 있으므로 strict coefficient에서 제외 |
| Tensor | `reg_mma - reg_operand_only`, blocks/SM 4/16/32, reuse 1-16. RF별 treatment/control-floor calibration ITER의 최대값을 두 mode에 동일 적용하고 calibration manifest/raw/detail을 audit |
| DRAM | `dram_cg_load_only - global_addr_only`, W_SM 2048/4096/8192 KiB, LR 4/8/16. 좌표별 treatment/control-floor calibration ITER의 최대값을 두 mode에 동일 적용하고 direct net-energy 차분 |
| Register | ptxas footprint와 NCU spill/local 0 확인. pure RF energy로 주장하지 않음 |

### 6.4 H100 세부 조건

기본 H100 profile은 H100 SXM5의 132 SM, 50 MiB L2, HBM3 planning profile이다.
PCIe SKU는 runtime SM 수와 memory subsystem을 기록해 별도 profile/result label로 다룬다.

| Step | H100 확인 내용 |
|---|---|
| Shared/Global L1 | Shared W128/B16, Global L1 W16/B16을 energy/NCU에 동일 사용 |
| L2 final path | W64/W128에서 B16/B8과 normal/persisting, contiguous/sm-interleaved 후보를 순서대로 검사. GH100도 partitioned L2 crossbar이므로 source+`srcunit_ltcfabric` logical final service, sector conservation, native-model, DRAM leakage를 모두 요구 |
| missing counter | GH100 NCU catalog에 필수 fabric metric이 없으면 direct hit로 대체하지 않고 L2 component를 reject |
| Tensor scope | 현재 `reg_mma`는 FP16 WMMA compatibility path. WGMMA/TMA/FP8 에너지로 해석하지 않음 |
| power scope | `GetPowerUsage` one-second-average fallback과 module/GPU-memory power를 total-energy numerator와 섞지 않음 |

## 7. 최종 보고서 형식

최종 보고서는 아래 표를 반드시 포함한다.

| 표 | 필수 열 |
|---|---|
| GPU architecture | GPU, SM, register/SM (KiB), L1/shared (KiB), L2 (MiB), memory type, source |
| Sweep 조건 | mode, W_SM (KiB), blocks/SM, active_SM (SM), reuse_factor, load_repeat, seconds (s), repeats |
| NCU validation | aggregate/path-specific L1/L2 hit (%), shared accesses/bytes, L1 request/hit/miss bytes, L2 read hit/miss sectors와 bytes, DRAM bytes, stall_long_scoreboard (%) |
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
