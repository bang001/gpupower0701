# GPU Power Modeling 실험 결과

갱신일: 2026-07-22
현재 측정 플랫폼: RTX 3090 (GA102, 82 active SM, GDDR6X)

## 최신 측정 결과와 현재 protocol 경계

### 2026-07-22 FP16 Tensor-only v3 진단 실행

현행 Tensor-only v3 코드로 RTX 3090에서 `blocks/SM=4,8,16`,
`RF=1,4,16`, 목표 duration `5,15 s`를 sweep했다. 각 좌표는 1회만
실행했으며 energy와 NCU는 같은 binary SHA-256
`500bcb73a3dffebc92f041072ccba3ff5f4f85a836e045ba6eff9715cdb99862`를
사용했다. Treatment/control 18 pair는 모두 동일 ITER였고, NCU에서 treatment의
FP16 HMMA work denominator 18/18, control HMMA=0 18/18, spill=0 18/18을
확인했다.

다만 RDP/WSL background가 있는 상태에서 pre-run memory-controller activity의
max와 p95가 모두 `43%`로 strict gate를 통과하지 못했다. 이 때문에 energy와 NCU의
quiescence gate를 명시적으로 생략해 실행했으며 repeat도 1회뿐이다. 대신 각 pair는
시작 전력 `12.47-19.32 W`, 온도 `41-48 degC`를 기록했고, 시작 전력 `<=35 W`,
온도 `<=48 degC`를 3회 연속 만족한 뒤 실행했다. 아래 값은 코드와 경로를 검증하기
위한 **diagnostic candidate**이지 논문용 final coefficient가 아니다.

| v3 estimator | median | 95% bootstrap median CI | 판정 | 의미 |
|---|---:|---:|---|---|
| matched-ITER completion | 2.720 pJ/FLOP | 2.500-2.977 pJ/FLOP | diagnostic only | 같은 ITER를 완료하는 데 추가된 전체 board energy |
| clocked MI-ATC | 0.840 pJ/FLOP | 0.323-1.073 pJ/FLOP | diagnostic only | pair 인접 `clocked_empty` 순전력으로 추가 active time을 보정한 대리값 |
| control-rate/operand-rate ATC | 0.897 pJ/FLOP | 0.834-1.008 pJ/FLOP | diagnostic only | no-MMA control의 순전력률을 treatment 시간으로 확장한 operand-rate 대리값 |
| joint regression | not identified | - | rejected | repeat=1이고 coefficient CI가 0을 포함해 Tensor와 추가시간 항을 분리하지 못함 |

Energy gate는 17/18 pair, NCU path gate는 18/18 pair가 통과했지만,
quiescence와 반복성 gate를 통과한 final estimator는 **0개**다. 따라서 `0.840`이나
`0.897 pJ/FLOP`을 순수 Tensor 회로 에너지 또는 확정 계수로 인용하면 안 된다.
세부 sweep 표, blocks/SM/RF/duration 추세, NCU 검증 그림은
[RTX 3090 FP16 Tensor v3 진단 보고서](rtx3090_tensor_fp16_v3_diagnostic_20260722_ko.md)에
기록했다.

### 2026-07-14 v5 historical strict package

2026-07-14 RTX 3090 finalplan은 Tensor v5 control, matched ITER,
GPU/device total-energy counter, treatment/control exact-coordinate NCU acceptance를
사용했다. 네 strict component와 별도 external-memory effective path가 모두 reliability
gate를 통과했다. 이 값은 **GA102 v5 protocol에서 accepted된 측정 결과**로
보존한다.

2026-07-15 A100에서 v5 `reg_operand_only` control이 launch-only로 실행되어
과대 ITER와 16시간 이상 run을 만든 portability 실패가 확인됐다. 따라서
신규 Tensor-only 실행은 v3 dynamic-attribution package를 사용하며, 아래 RTX 3090
v5 숫자를 v3 결과와 혼합하거나 A100/V100/H100에 복사하지 않는다. 2026-07-22
v3 실행은 완료됐지만 quiescence와 반복성 gate를 생략한 diagnostic이므로 새로운
strict 계수로 승격하지 않는다.

이 값은 순수 회로 또는 SRAM/GDDR6X bitcell energy가 아니다. 다음과 같이 표현해야
한다.

> NCU로 treatment와 control 경로를 검증한 workload-dependent effective
> board-level microbenchmark coefficient

## 최종 계수

| component | treatment - control | median | 95% bootstrap median CI | min-max | valid pairs | 판정 |
|---|---|---:|---:|---:|---:|---|
| Tensor MMA incremental | `reg_mma - reg_operand_only` | **2.140 pJ/FLOP** | 2.114-2.170 pJ/FLOP | 1.907-2.314 pJ/FLOP | 75/75 | strict accepted |
| Shared scalar path | `shared_scalar_load_only - shared_scalar_addr_only` | **0.714 pJ/bit** | 0.680-0.923 pJ/bit | 0.484-1.027 pJ/bit | 15/15 | strict accepted |
| Global L1 hit path | `global_l1_load_only - global_addr_only` | **0.852 pJ/bit** | 0.813-0.888 pJ/bit | 0.667-0.947 pJ/bit | 15/15 | strict accepted |
| L2 CG hit path | `l2_cg_load_only - global_addr_only` | **9.078 pJ/bit** | 8.935-9.299 pJ/bit | 8.668-9.672 pJ/bit | 30/30 | strict accepted |
| External-memory read path | `dram_cg_load_only - global_addr_only` | **24.949 pJ/bit** | 24.864-25.101 pJ/bit | 24.229-26.038 pJ/bit | 45/45 | accepted effective path |

External-memory 값은 strict 4-component 표 밖의 sanity/effective-path 결과다. GPU core의
global-load 발행부터 L1TEX, L2, controller/PHY 및 GDDR6X board path 변화가 포함될 수
있으므로 **물리 GDDR6X device energy**라고 부르면 안 된다.

![RTX 3090 v5 component coefficient](../assets/component_energy_method/rtx3090_current_component_coefficients_20260714.png)

그림의 Tensor 패널은 pJ/FLOP, memory 패널은 pJ/bit이므로 서로 막대 높이를 직접
비교하지 않는다. Memory 패널은 값 범위가 넓어 log scale이다. 빈 마름모로 표시한
external-memory 값은 strict 네 component와 측정 경계가 다르다는 뜻이다.

Shared와 Global L1의 median은 다르지만 CI가 겹친다. 따라서 이 run만으로
`Shared가 Global L1보다 확실히 저전력`이라고 결론 내릴 수 없다. 두 값은 같은 unified
L1/shared 물리 자원의 순수 SRAM energy가 아니라, 서로 다른 instruction/address-space,
arbitration, request denominator를 가진 두 **effective path**다.

## Parameter Sweep

실험자가 바꾼 값과 최종 선택 좌표를 단위와 함께 기록한다. 모든 pair는 treatment와
control에 같은 ITER를 적용했고, 각 좌표를 5회 반복했다. 목표 timed-kernel 구간은 약
10 s다.

| component | W_SM sweep (KiB/SM) | blocks/SM sweep | RF/LR sweep (count) | 선택/사용 좌표 | pair rows | raw rows |
|---|---:|---:|---:|---|---:|---:|
| Tensor MMA | 1 | 4, 8, 16 | RF 1, 2, 4, 8, 16 | 전 좌표; W_SM은 CLI placeholder이고 register working set이 아님 | 75 | 150 |
| Shared scalar | 64 | 8 | LR 4, 8, 16 | 전 좌표 | 15 | 30 |
| Global L1 | 8 | 8 | LR 4, 8, 16 | 전 좌표 | 15 | 30 |
| L2 CG | 32, 64 | 8 | LR 4, 8, 16 | 전 좌표 | 30 | 60 |
| External-memory read | 256, 512, 2,048 | 8 | LR 4, 8, 16 | 전 좌표 | 45 | 90 |
| **합계** | - | - | - | 36 configuration coordinates x 5 repeats | **180** | **360** |

`RF`는 Tensor inner MMA grouping 수이고 cache 랜덤화 비율이 아니다. `LR`은 한 loop
body에서 같은 경로의 load를 반복 발행하는 수다. W_SM은 memory mode에서 SM당 목표
working set이고, Tensor mode에서는 register 용량을 의미하지 않는다.

Sweep의 목적은 한 좌표의 숫자를 골라내는 것이 아니라 다음을 확인하는 데 있다.

| 실험자가 조절한 것 | 관찰한 것 | 해석 |
|---|---|---|
| Tensor blocks/SM | Tensor pipe activity, occupancy, pJ/FLOP 분산 | GPU utilization 변화에도 계수가 유지되는지 |
| Tensor RF | HMMA/logical MMA 선형성, control SASS scaling | treatment work와 no-MMA control work가 실제로 증가하는지 |
| Memory W_SM | L1/L2/DRAM service 위치 | capacity 이름만 믿지 않고 NCU로 실제 residency를 확인 |
| Memory LR | traffic bytes와 energy delta | 분모와 신호가 반복량에 따라 함께 증가하는지 |
| 5 repeats | min/median/max, CI, power-state outlier | drift와 단일 측정 우연성을 확인 |

## 측정과 계산

각 raw row의 numerator는 NVML `nvmlDeviceGetTotalEnergyConsumption`의 timed-kernel
구간 전후 차이인 `total_energy_mj_delta`다. scope는
`gpu_device_total_energy_counter`이며 RTX 3090의 보조 power semantics metadata는
`one_sec_average`다. `GetPowerUsage` 적분값을 final numerator로 섞지 않았다.

Treatment-control 계산의 의미는 다음과 같다.

```text
net energy(mode) = measured GPU/device energy - idle baseline energy
delta E = net energy(treatment) - net energy(control)
Tensor coefficient = delta E / logical FP16 MMA FLOP
Memory coefficient = delta E / NCU-validated path bytes / 8
```

분자는 board/device-level energy 차분이고, 분모는 실제 늘어난 Tensor FLOP 또는 NCU
path byte다. 값이 작을수록 이 microbenchmark 조건에서 한 FLOP 또는 한 bit를 처리하는
증분 board energy가 작다는 뜻이다. 다른 GPU나 일반 application에 그대로 적용되는
물리 상수라는 뜻은 아니다.

## NCU 검증

NCU는 power run과 분리한 sidecar replay에서 수집했다. profiler overhead를 energy
numerator에 넣지 않으면서도, energy와 동일한
`mode,W_SM,blocks/SM,active_SM,RF,LR` 좌표를 검증한다. 전체 73 NCU row 중 final path와
control 72개가 accepted였고, 비교용 `clocked_empty` 1개만 `not_selected`로 reject됐다.

![RTX 3090 v5 NCU path evidence](../assets/component_energy_method/rtx3090_current_ncu_path_evidence_20260714.png)

위 그림 A/B는 accepted treatment row의 median traffic과 access count다. byte cell과
access cell의 색은 log scale이다. 그림 C의 long-scoreboard 값은 NCU
`per_issue_active` 계열의 percent-like 신호로, 100을 넘어도 실행 시간의 100%를
뜻하지 않는다.

### Path Acceptance

| component | treatment/control NCU rows | 핵심 acceptance evidence | 결과 |
|---|---:|---|---|
| Tensor MMA | 15/15 | treatment HMMA/logical MMA=2, control HMMA=0, control SASS/expected op>=0.1, spill/local=0 | accepted |
| Shared scalar | 3/3 | shared read bytes>0, address control shared read=0, bank conflict=0, global L1 request=0 | accepted |
| Global L1 | 3/3 | path-specific L1 hit 99.9998-99.9999%, L1 hit bytes nearly equal request bytes | accepted |
| L2 CG | 6/6 | path-specific L1 hit=0%, final L2 read hit 99.9974-100%, low DRAM leakage | accepted |
| External read | 9/9 | L1 hit=0%, external read/expected traffic 정합, write/read<=0.0045% | accepted effective path |

Tensor static binary audit도 RF 1/2/4/8/16에서 treatment HMMA>0, control HMMA=0,
control backward branch>0, local allocation=0을 확인했다. 이는 GA102에서 v4의
dead control 문제가 v5 run에는 발생하지 않았다는 증거다. A100에도 portable하다는
증거는 아니며, 실제 A100 v5 run은 반대 결과를 보였다. 다만 treatment는
WMMA fragment를 유지하고 control은 더 작은 scalar footprint를 사용하므로 2.140
pJ/FLOP에는 Tensor Core뿐 아니라 unmatched register/operand/scheduler path가 포함된다.

### 실제 Access/Byte/Stall 값

다음 값은 accepted treatment row의 median이다. RTX 3090 summary의 access unit은
sector이고 traffic unit은 byte(B)다.

| path | shared read accesses | L1 accesses | L2 accesses | DRAM accesses | shared read bytes | L1 request bytes | L2 read bytes | DRAM read bytes | long-SB signal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Shared scalar | 4.198 G | 0 | 0 | 3.735 M | 537.395 GB | 0 | 0 | 119.531 MB | 0.001231 |
| Global L1 | 0 | 16.794 G | 20.992 k | 4.398 M | 0 | 537.395 GB | 0.672 MB | 140.728 MB | 2.040 |
| L2 CG | 0 | 16.794 G | 16.794 G | 8.595 M | 0 | 537.395 GB | 537.398 GB | 271.764 MB | 396.113 |
| External read | 0 | 16.794 G | 16.794 G | 16.803 G | 0 | 537.395 GB | 537.400 GB | 537.677 GB | 670.066 |

`ld.global.cg`도 request 발행 과정에서 L1TEX를 통과하므로 L2/External row에 L1 request
access/bytes가 보이는 것은 정상이다. 실제 L1 hit bytes가 0에 가깝고 L2 또는 DRAM
service counter가 증가하는지로 경로를 구분한다.

## 품질 감사

| audit | 결과 | 해석 |
|---|---:|---|
| Power API | 360/360 `final_candidate` | 모든 raw row가 explicit GPU/device total-energy delta 사용 |
| Power state | 358 `ok`, 2 `caution`, 0 `reject` | 2개 temperature outlier를 기록했으나 hard reject는 없음 |
| Matched-control detail | 180/180 valid | 음수, ITER mismatch, NCU/control mismatch 없음 |
| Component reliability | strict 4/4 accepted | external은 별도 `accepted_effective_path` |
| NCU acceptance | 72 accepted, 1 not-selected reject | final treatment/control은 모두 accepted |
| Strict summary audit | 193 checks, 0 failures, 0 warnings | schema, counter, scope, pair 증거 통과 |
| Platform package audit | 31 checks, 0 failures, 0 missing, 0 warnings | RTX 3090 결과 package 완결 |

## 결론 내릴 수 있는 것과 없는 것

| 결론 내릴 수 있는 것 | 결론 내리면 안 되는 것 |
|---|---|
| 2026-07-14 RTX 3090 v5 microbenchmark 조건의 effective coefficient | 순수 Tensor transistor energy 또는 순수 register energy |
| NCU상 Shared, Global-L1, L2, External 경로가 의도대로 분리됨 | Shared SRAM과 L1 SRAM의 물리 bitcell energy가 서로 다르다는 주장 |
| L2 path가 Global L1보다 이 실험에서 큰 board-level 증분을 보임 | 모든 application에서 고정된 L1:L2 에너지 비율 |
| external read path가 약 24.95 pJ/bit임 | GDDR6X chip 자체가 24.95 pJ/bit라는 주장 |
| RTX 3090 v5 package가 당시 gate를 통과함 | V100/A100/H100에도 같은 계수를 복사 가능하다는 주장 |

V100/A100/H100 v6 command package는 준비되어 있으나 해당 target node의 current-protocol
측정 package가 이 저장소에 아직 반입되지 않았다. 플랫폼별 결과는 각 GPU에서 다시
측정하고 같은 audit를 통과시켜야 한다.

## 재검산 경로

| artifact | 경로 |
|---|---|
| strict component summary | [Markdown](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md) / [CSV](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.csv) |
| matched-control summary/detail | [summary](../../results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv) / [detail](../../results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv) |
| NCU acceptance | [Markdown](../../results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.md) / [CSV](../../results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv) |
| NCU normalized counters | [CSV](../../results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv) |
| Tensor binary audit | [Markdown](../../results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.md) |
| Power API/state audit | [API](../../results/summary/rtx3090_component_finalplan_20260714_power_api_audit.md) / [state](../../results/summary/rtx3090_component_finalplan_20260714_power_state_audit.md) |
| Reliability/instability audit | [reliability](../../results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.md) / [instability](../../results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.md) |
| Strict/package audit | [strict](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.md) / [package](../../results/summary/rtx3090_platform_result_package_audit_20260714.md) |

과거 protocol의 수치와 그림은 `archive/pre_current_protocol_20260712/` 및
`results/archive/`에 보존한다. v2/v4/v5/v6와 다른 GPU 결과를 합쳐
평균내지 않는다.
