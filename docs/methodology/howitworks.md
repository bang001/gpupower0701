# How It Works: Component Energy Microbenchmark

작성일: 2026-07-02
최종 업데이트: 2026-07-14

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
| Matched-control 차분 | Shared/Global L1은 control energy rate를 같은 시간만큼 빼고, Tensor/L2 CG/DRAM CG final pair는 동일 ITER의 net energy를 직접 뺀다 | scheduler/loop/idle 같은 공통 비용을 일부 제거하기 위해 |
| NCU path validation | L1/L2/DRAM/shared bytes, hit rate, Tensor instruction, spill, stall을 확인 | mode 이름만으로는 실제 경로를 보장할 수 없기 때문 |

## 2. 현재 최종 실험 축

현재 finalplan에서 component는 다음 pair로 본다.

| 실험 축 | treatment / control | 의미 | 최종 단위 |
|---|---|---|---|
| Tensor | `reg_mma - reg_operand_only` | FP16 WMMA/HMMA incremental cost 후보 | pJ/FLOP |
| Shared scalar | `shared_scalar_load_only - clocked_empty` | shared-memory scalar load path | pJ/byte, pJ/bit |
| Global L1 | `global_l1_load_only - global_addr_only` | 같은 주소/loop control 대비 global L1-hit load path | pJ/byte, pJ/bit |
| L2 | `l2_cg_load_only - global_addr_only` | 같은 주소/loop control 대비 L1-bypassed L2-hit path | pJ/byte, pJ/bit |
| L2 capacity diagnostic | `l2_load_only` | 일반 global-load path가 L1과 섞이는지 확인 | strict coefficient 제외, NCU 진단 전용 |
| DRAM | `dram_cg_load_only - global_addr_only` | 같은 주소/loop control 대비 DRAM streaming sanity path | pJ/byte, pJ/bit 후보 |

중요한 현재 코드 기준:

- `scripts/plan_platform_component_experiment.py`는 `tensor`, `shared`, `l1`, `l2`, `dram` energy CSV를 나누어 생성한다.
- `scripts/analyze_matched_control_energy.py`의 기본 final pair는 `l2_cg_load_only` 기반 L2 coefficient를 계산한다.
- `l2_load_only`는 normal global load라 global L1을 우회하지 않는다. 따라서 strict L2 coefficient로 쓰지 않고, 필요한 경우 NCU 진단에만 사용한다.
- `shared_mma`, `l2_mma`, `dram_mma`는 여전히 코드에 있지만 현재 최종 component coefficient의 primary pair가 아니다. 보조 진단 또는 과거 탐색용으로 본다.

## 3. 전체 실행 흐름

전체 실험은 energy run과 NCU run을 분리한다. NCU replay는 kernel 실행을 바꿀 수 있으므로 NCU에서 나온 energy를 최종 pJ 분자로 쓰지 않는다.

```mermaid
flowchart TD
  A[문서/플랫폼 확인] --> B[build/preflight]
  B --> C[energy sweep<br/>NCU 없이 NVML energy 측정]
  C --> P[power API audit<br/>energy numerator gate]
  P --> Q[power-state audit<br/>row quality check]
  Q --> D[NCU sidecar<br/>counter만 수집]
  D --> E[path acceptance<br/>의도한 경로인지 판정]
  Q --> F[matched-control analysis<br/>energy 차분]
  E --> F
  F --> R[component reliability audit<br/>최종 verdict]
  R --> I[instability audit<br/>weak/negative 원인]
  R --> G[accepted coefficient table]
  P --> H[rejected/provisional row 기록]
  E --> H
  R --> H
  I --> H
```

| 단계 | 대표 script | 산출물 | 핵심 판정 |
|---|---|---|---|
| preflight | `scripts/preflight_gpu_support.py` | `results/summary/*_preflight.md` | GPU profile, CC, SM 수, NVML, NCU 상태 확인 |
| energy sweep | `scripts/run_component_regression_sweep.py` | `results/raw/*_component_finalplan_*.csv` | NCU 없이 `net_E_J`, elapsed, expected denominator 수집 |
| power API audit | `scripts/audit_power_api_measurements.py` | `results/summary/*_power_api_audit.md` | `nvml_total_energy`, integration method, profile power semantics 확인 |
| power-state audit | `scripts/audit_power_state_stability.py` | `results/summary/*_power_state_audit.md` | 같은 mode/config row 사이의 평균 전력, endpoint power, 온도/clock outlier 확인 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | `results/ncu/*/ncu_cache_validation_summary.csv` | hit rate, bytes, accesses, stall, spill, Tensor instruction 확인 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | `results/summary/*_ncu_acceptance.*` | accepted/provisional/rejected 분류 |
| matched-control | `scripts/analyze_matched_control_energy.py` | `results/summary/*_matched_control_report.md` | pJ/FLOP, pJ/byte, pJ/bit 계산 |
| component reliability audit | `scripts/audit_component_reliability.py` | `results/summary/*_component_reliability_audit.md` | power/NCU/계수 안정성을 결합해 accepted/caution/sanity/reject 판정 |
| matched-control instability audit | `scripts/audit_matched_control_instability.py` | `results/summary/*_matched_control_instability_audit.md` | weak-signal/negative row의 원인과 follow-up 조건 요약 |

## 4. Energy Run이 측정하는 것

Energy run은 NVML을 이용해 kernel 실행 전후의 GPU energy 또는 power를 측정한다. raw CSV의 `net_E_J`는 mode별 독립 실행값이다.

```text
delta_E_J = NVML energy after - NVML energy before
idle_baseline_scaled_J = idle energy measured for same seconds, scaled to kernel elapsed time
net_E_J = delta_E_J - idle_baseline_scaled_J
```

Power API audit은 이 분자가 `nvml_total_energy` 기반 final 후보인지 확인한다.
Power-state audit은 같은 mode/config 반복 row와 비교해 특정 row의 평균 전력 또는
endpoint power가 비정상적으로 무너졌는지 확인한다. 이 둘은 역할이 다르다.
Power API audit을 통과해도 power-state outlier row는 matched-control delta를
왜곡할 수 있다.

GPU 세대별 power API 의미가 다르기 때문에 energy run은 아래처럼 해석한다.

| 측정 경로 | 세대별 의미 | 최종 coefficient 사용 |
|---|---|---|
| `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | Volta 이상 fully supported device에서 기대되는 누적 GPU/device energy counter. 실제 지원 여부는 raw CSV로 확인 | 우선 사용 |
| `nvmlDeviceGetPowerUsage` endpoint 적분 | total energy counter가 없을 때의 fallback. V100/A100은 instant, RTX 3090/H100은 1초 평균 의미로 기록 | provisional/diagnostic |
| `power.draw.average` / `power.draw.instant` | nvidia-smi field. average는 GA100 제외 Ampere 이상에서 기대, instant는 runtime 지원 여부 확인 | metadata/diagnostic |
| H100 module power | GPU + supported NVIDIA CPU + module 구성요소 power | component numerator로 섞지 않음 |
| GPU memory power | GPU memory subsystem power | HBM/DRAM sanity metadata로만 사용 |

세대별로 final numerator gate는 다음처럼 다르게 확인한다. 이 표는 API 지원 여부를
자랑하기 위한 표가 아니라, matched-control `delta_E_J`의 분자가 같은 의미인지 확인하는
표다.

| GPU/profile | fallback power 의미 | final pJ 계산에 필요한 power metadata | final 제외 조건 |
|---|---|---|---|
| RTX 3090 / `rtx3090` | `GetPowerUsage`는 1초 평균 | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=one_sec_average` | WSL/driver에서 total-energy counter가 없고 endpoint fallback만 남은 row |
| V100 / `v100` | `GetPowerUsage`는 instantaneous | total-energy delta, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=instant`, GV100 NCU path accepted | GV100 NCU 미지원 또는 `one_sec_average` semantics가 섞인 row |
| A100 / `a100` | GA100은 Ampere 예외로 instantaneous | total-energy delta, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=instant`, MIG/full GPU와 runtime SM 기록 | RTX 3090의 active SM/L2/shared 좌표 또는 `one_sec_average` semantics가 섞인 row |
| H100 / `h100` | `GetPowerUsage`는 1초 평균 | GPU/device total-energy delta, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=one_sec_average`, module/memory power 분리 기록 | module power 또는 GPU memory power를 L1/L2/DRAM denominator와 나눈 row |

여기서 중요한 점은 API가 보이는 것과 final coefficient로 쓸 수 있는 것이 다르다는
것이다. 새 플랫폼 결과를 볼 때는 항상 아래 순서로 확인한다.

| 확인 질문 | 확인할 CSV/문서 항목 | final 후보 조건 |
|---|---|---|
| total energy counter가 실제로 성공했는가? | `nvml_total_energy_supported`, `energy_source` | `true`, `nvml_total_energy` |
| energy 계산 방식이 무엇인가? | `energy_integration_method` | `total_energy_mj_delta` |
| fallback power sample의 시간 의미가 profile과 맞는가? | `nvml_power_usage_semantics` | RTX 3090/H100 `one_sec_average`, V100/A100 `instant` |
| 측정 scope가 GPU/device인가? | `measurement_scope`, preflight power scope | `gpu_device_total_energy_counter` |
| NCU denominator/path가 의도대로인가? | NCU acceptance CSV | treatment path `accepted` |

이 중 하나라도 깨지면 pJ/FLOP 또는 pJ/bit 숫자가 양수여도 final component
coefficient로 채택하지 않는다. 특히 H100/HGX에서 보이는 module power나 GPU memory
power는 "추가로 관찰한 telemetry"이지 L1/L2/DRAM denominator로 나눌 energy 분자가 아니다.

상세한 세대별 API 표와 final/provisional/reject 기준은
[power_measurement_api_matrix_ko.md](../platforms/power_measurement_api_matrix_ko.md)에
둔다.

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
| Global L1 | path-specific L1 hit rate, L1 request/hit bytes, L2 read bytes, DRAM bytes | global load가 L1 lookup hit 중심이어야 함 |
| L2 CG | path-specific L1 hit bytes, L2 read hit/miss sectors, L1 request/L2 read/DRAM bytes | `.cg` 요청은 L1TEX를 통과하지만 L1 cache hit는 거의 없고 L2 read hit가 지배적이어야 함 |
| DRAM CG | DRAM bytes, L1/L2 hit rate, L2 bytes 대비 DRAM bytes | DRAM streaming이 보이는지 sanity check |
| 공통 | long/short scoreboard stall, wait stall, SMID histogram, spill/local | stall 또는 placement 문제를 결과에 같이 기록 |

현재 acceptance 기준은 다음처럼 요약된다.

| Path | accepted 조건 요약 |
|---|---|
| Tensor | `reg_mma`에서 Tensor/HMMA instruction > 0, spill/local 0, memory traffic이 threshold 이하 |
| Tensor control | `reg_operand_only`에서 Tensor/HMMA instruction = 정확히 0, spill/local 0, treatment와 동일 NCU 좌표 accepted. 과거 fixed-epilogue 완화는 현행 final에 적용하지 않음 |
| Shared scalar | shared bytes/accesses > 0, shared instruction 존재, bank conflict ratio 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 | path-specific L1 hit >=95%, L1 request/hit bytes 존재, L2 read/L1 request <=1%, DRAM/L1 request <=1% |
| L2 CG | path-specific L2 read hit >=95%, L1 path hit <=1%, L1 hit bytes/request bytes <=1%, DRAM/L2 read bytes <=2%. aggregate hit rate는 hard gate가 아님 |
| DRAM sanity | path-specific L1 hit <= 1%, DRAM bytes dominant, path-specific L2 read hit은 최소 5% 상한과 `L2 capacity / full working set` 기반 residual 상한 중 큰 값 이하 |

이 기준을 통과하지 못한 row는 pJ 값이 양수여도 최종 component coefficient로 채택하지 않는다.

NCU 버전에 따라 `sass__inst_executed_register_spilling_mem_local_op_*`가 GA100 metric
catalog에 없을 수 있다. 현재 sidecar는 함께 요청한
`l1tex__t_bytes_pipe_lsu_mem_local_op_ld/st`를 fallback으로 사용한다. 실험 kernel이
명시적 local-memory 자료구조를 사용하지 않으므로 두 local byte counter가 모두 0이고
ptxas도 spill 0일 때 `spill_evidence_source=local_memory_bytes_zero_inference`로 기록한다.
이때 architecture-neutral gate인 `spill_zero_verified=1`도 함께 기록한다. local bytes가
양수면 전용 spill instruction counter의 유무와 관계없이 reject한다.

## 6. pJ 계산 방식

### 6.1 Matched-control energy 차분

Shared와 Global L1 path runner는 mode마다 목표 시간에 맞게 ITER를 따로 calibrate한다.
이 두 pair는 control energy를 power rate로 바꾼 뒤 treatment elapsed time만큼 보정한다.
반면 Tensor, L2 CG, DRAM CG final pair는 treatment/control에 동일 ITER를 강제하고 두
idle-corrected net energy를 직접 뺀다.

| pair | final work policy | energy 차분 |
|---|---|---|
| Shared scalar - clocked empty | mode별 duration calibration | control power를 treatment 시간으로 보정 |
| Global L1 - address control | mode별 duration calibration | control power를 treatment 시간으로 보정 |
| Tensor MMA - register operand control | dual calibration 후 동일 ITER | `net_E_treatment - net_E_control` |
| L2 CG - address control | dual calibration 후 동일 ITER | `net_E_treatment - net_E_control` |
| DRAM CG - address control | dual calibration 후 동일 ITER | `net_E_treatment - net_E_control` |

```text
control_power_W = E_control_J / t_control_s
control_energy_scaled_J = control_power_W * t_treatment_s
delta_E_J = E_treatment_J - control_energy_scaled_J
```

고정 ITER만 사용하면 같은 work가 대역폭 또는 처리량이 높은 GPU에서 더 빨리 끝날 수 있다.
현재 energy sweep의 `--seconds=10`은 ITER 고정값이 아니라 calibration 목표시간이다. 각
플랫폼에서 짧은 calibration run으로 필요한 ITER를 추정하므로, 더 빠른 GPU는 대체로 더
큰 ITER를 선택하고 실제 power 측정창은 약 10 s로 유지한다. 따라서 플랫폼 간 ITER 수는
직접 성능 비교값이 아니며, 실제 `elapsed_s`와 NCU가 확인한 bytes/operations를 분모로 써야
한다. 또한 이 보정은 peak memory bandwidth만으로 결정되지 않는다. cache hit 경로,
latency, SM 수, blocks/SM, occupancy, clock과 instruction dependency가 함께 영향을 준다.

Tensor final pair는 per-mode duration scaling의 예외다. `reg_mma`와
`reg_operand_only`를 따로 duration
calibration한 ITER를 각 mode에 그대로 쓰면 RF가 커질수록 서로 다른 work count를 비교하게
된다. 현재 finalplan은 각 RF에서 treatment 목표시간의 `reg_mma` ITER와 control 최소시간의
`reg_operand_only` ITER를 구하고, 둘 중 큰 ITER를 두 mode에 동일하게 적용한다.

L2 CG도 같은 이유로 동일 ITER가 필수다. `global_addr_only`가 `l2_cg_load_only`보다
빠르거나 느리다는 이유로 각 mode에 서로 다른 ITER를 주면, 주소 제어 작업과 L2 load
작업의 실행 횟수 자체가 달라진다. 현행 finalplan은 각 W/B/LR 좌표에서
`l2_cg_load_only`의 목표시간 candidate와 `global_addr_only`의 control 최소시간 candidate를
구하고, 둘 중 큰 값을 양쪽에 적용한다. 산출물 `*_l2_pair_calibration.csv`, raw 두 mode의
`ITER`, matched detail의 `pair_energy_basis=matched_iters_net_energy`와 `iter_ratio=1`이 모두
일치해야 한다.

2026-07-13 이전 V100 실행에서 NCU L2 read hit 약 99.9996%, L1 hit 0%를 얻었더라도,
control ITER가 treatment보다 약 2배 많아 모든 좌표가 음수였던 결과는 L2 path 검증만
성공한 것이다. 그 음수 `-12~-9 pJ/byte` 계수는 동일 작업량 차분이 아니므로 물리적
L2 에너지나 유효 coefficient로 해석하지 않는다.

```text
ITER_reg_mma = ITER_reg_operand_only
delta_E_tensor_J = net_E_reg_mma_J - net_E_reg_operand_only_J
```

Analyzer detail의 `pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`이 둘 다
확인되어야 한다. duration-scaled Tensor row는 새 final coefficient에서 reject한다.
또한 final analyzer는 `--require-control-ncu-acceptance`를 사용한다. 따라서
`reg_operand_only`와 `global_addr_only`도 treatment와 같은
`W_SM, blocks/SM, active_SM, RF/LR` 좌표에서 NCU `accepted`여야 한다.
treatment만 깨끗하고 control에 HMMA 또는 global input traffic이 남은 pair는 계수를
만들지 않는다.
동일 ITER control은 MMA treatment보다 빨리 끝난다. 따라서 표준 10 s package는 control
calibration floor 1 s, A100 targeted 20 s package는 2 s를 사용하고 analyzer는 각 floor의
80% 이상을 요구한다. 이보다 짧거나 `net_E_J <=0`이면 total-energy counter/noise floor에서
식별되지 않은 것으로 reject한다.

같은 ITER가 **같은 실행시간**을 뜻하지는 않는다. `reg_mma`가 더 오래 실행되면 direct
`net_E_treatment - net_E_control`에는 MMA instruction 자체뿐 아니라 그 추가 active time 동안의
scheduler, clocked SM, register-fragment lifetime 비용도 남는다. 반대로 control power를
treatment 시간으로 단순 확대하면 서로 다른 work를 가정하게 되므로 pure Tensor energy가
되지는 않는다. 현재 값은 동일 logical work를 완료하는 데 추가된 board-level energy라는
의미의 effective coefficient이며, 보고서에는 treatment TFLOP/s, 두 mode elapsed time과
net power를 함께 표기한다. GPU 간 값 차이는 Tensor 회로뿐 아니라 처리시간 차이의 영향도
받는다.

반복 run이 있을 때는 treatment row를 실행 순서상 가장 가까운 control row와 비교하는
`nearest-control` pairing을 우선 사용한다. GPU 온도와 clock이 시간에 따라 변하기 때문에,
mode별 median을 따로 고른 뒤 차분하면 실제로 같은 상태에서 측정되지 않은 두 row를
비교할 수 있다.

현재 sweep runner는 알려진 두 mode pair를 하나의 원자적 실행 단위로 취급한다.
Tensor, Shared, Global L1, L2 CG, DRAM CG 모두 반복 시작점을 바꿀 때 command 한 개가 아니라
완전한 `control -> treatment` pair를 회전한다. 따라서 pair 하나가 repeat의 시작과 끝으로
분리되지 않는다. matched detail의 legacy 열이름 `pair_start_distance_ms`는 두
raw `run_id` timestamp의 차이이며 command 개수가 아니다. `run_id`가 idle baseline과
kernel 실행 완료 후 생성되므로 엄밀히는 시작 간격이 아니라 completion timestamp
간격이다. 따라서 10초 finalplan은 30,000 ms, 20초 A100 targeted remediation은
60,000 ms를 사용한다. 정상 인접 pair의 측정 overhead를 허용하되 수분 떨어진
다른 repeat control의 재사용은 reject한다.

또한 `delta_E_J`가 양수여도 충분히 크지 않으면 최종값으로 쓰지 않는다. 이 문서의 현재
기준은 `delta_E_J >= 10 J`이고,
`delta_E_J / max(E_treatment, control_energy_scaled) >= 0.5%`이다. 이 gate는
L1/shared처럼 treatment와 control의 board-level energy 차이가 작은 path에서 noise floor
안의 값을 component coefficient로 오해하지 않기 위한 장치다.

최종 summary에는 반복 안정도를 보기 위해 `IQR`, `MAD`, `CV`, bootstrap median 95% CI,
`confidence_class`도 함께 기록한다. 이 값들은 coefficient가 반복 run에서 얼마나 흔들리는지
보여주는 품질 지표이며, pure component isolation을 보증하지 않는다.

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

각 RF 좌표에서 treatment/control의 `ITER`가 동일해야 하며, pair calibration manifest와
raw CSV를 package audit이 대조한다. control inner loop는 RF마다 dependent register integer
add 1개를 실행해 ptxas가 loop를 제거하지 못하게 하고 fragment 값도 register input으로
유지한다. `reg_mma`에도 같은 add를 MMA 다음에 한 번씩 실행하므로 차분에서
이 공통 instruction은 상쇄된다. 기존 control의 RF 비례 FP32 FMA/checksum과 memory
access는 없다. 두 mode의 output은 같은 per-thread 8개 scalar store, 총 256
floats/block 패턴을 쓴다. treatment는 accumulator fragment 8개를 저장해 compiler가
MMA를 제거하지 못하게 하고, control은 sink 값을 같은 주소 패턴으로 저장한다.
`store_matrix_sync`는 두 mode 모두 사용하지 않는다.

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
| Global L1 hit | `global_l1_load_only` | `global_addr_only` | NCU L1 request bytes |
| L2 CG hit | `l2_cg_load_only` | `global_addr_only` | NCU L2 read bytes |
| DRAM CG streaming | `dram_cg_load_only` | `global_addr_only` | NCU DRAM bytes |

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
| `ncu_actual_same_working_set` | mode, W_SM, blocks/SM, active_SM은 같고 factor는 대표 NCU scale 사용 | 기존 RTX 3090 strict 결과의 한계. 새 final run에서는 보조/fallback |
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

Memory traffic이나 MMA 없이 persistent grid/loop 구조를 만드는 control이다. 현행
final protocol에서는 Shared scalar path에만 직접 사용한다. Global L1/L2/DRAM은 주소
계산과 loop를 더 잘 맞춘 `global_addr_only`를 control로 사용한다.

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

fragment 초기화와 compiler 최적화 방지용 dependent register
integer add가 포함된다. 같은 add는 `reg_mma`에도 있어 pair 차분에서 공통 비용으로
상쇄된다. RF 비례 FP32 FMA/checksum은 제거했다. 따라서 여전히 pure RF
pJ/access가 아니라 `reg_mma`의 work-matched no-MMA control로 쓴다.
output은 treatment와 같은 per-thread 8개 scalar store 패턴을 사용하되 WMMA store
intrinsic은 사용하지 않는다.

### `reg_mma`

memory-backed operand 공급을 최대한 줄이고 register fragment 기반으로 FP16 WMMA `mma_sync`를 반복한다.

의미:

```text
reg_mma - reg_operand_only ~= effective Tensor MMA incremental cost
```

`reg_mma`도 순수 Tensor Core 에너지는 아니다. scheduler, issue, register fragment read/write, accumulator update, 공통 scalar epilogue의 불완전 상쇄, measurement residual이 함께 들어간다.

현재 final RF 중 RF1은 정확성이 확인된 dynamic treatment/control을 유지하고,
RF2/4/8/16은 compile-time fixed-trip `unroll 1` kernel로 dispatch한다. GA102 probe에서
dynamic loop의 RF2와 RF6이 추가 HMMA issue를 만들었던 문제를 제거하면서 control이
과도하게 최적화되지 않도록 하기 위한 것이다. 임의 RF는 diagnostic용 dynamic fallback을
사용할 수 있지만 final coefficient 후보가 되려면 NCU의 `HMMA/logical MMA` 선형성 gate를
별도로 통과해야 한다.

### `shared_scalar_load_only`

dynamic shared memory를 만들고, shared memory scalar load를 반복한다. 현재 shared path의 primary mode다.

의미:

```text
shared_scalar_load_only - clocked_empty
  ~= shared-memory scalar load path effective coefficient
```

NCU에서 shared bytes/accesses와 bank conflict를 반드시 확인한다.

### `global_l1_load_only`

작은 global working set을 반복해서 `ld.global.ca.u32` scalar load로 읽어 global load가 L1 hit로 끝나도록 만드는 mode다. WMMA fragment load를 쓰지 않으므로 memory pair의 control과 per-thread scalar loop 구조가 맞는다.

의미:

```text
global_l1_load_only - global_addr_only
  ~= same-address/same-loop control 대비 global-load L1-hit path coefficient
```

NCU에서 L1 hit rate가 높고 L2/DRAM traffic이 낮아야 한다.

### `global_addr_only`

`global_l1_load_only`, `l2_cg_load_only`, `dram_cg_load_only`의 matched control이다.
같은 block별 base address, tile 선택, repeat loop, checksum 연산을 실행하지만 pointer를
주소값으로만 소비하고 global input load는 발행하지 않는다. 따라서 아래 차분은 단순 empty
loop 차분보다 주소 계산과 loop control 비용을 잘 제거한다.

```text
global_*_load_only - global_addr_only
```

NCU에서는 global-load L1 request byte가 0인지 확인한다. `--verify-smid=1`의 SMID atomic은 L2
sector counter에 나타날 수 있으므로, address control의 L2 sector가 0이어야 한다고 해석하면
안 된다. DRAM background는 paired treatment expected input bytes의 0.1% 이하만 허용한다.
이 상한은 output store, SMID atomic, profiler replay를 위한 것이며 global input request 0
조건을 대체하지 않는다.

### `l2_cg_load_only`

global load에 `ld.global.cg.u32` 경로를 사용해 L1을 최대한 배제하고 L2 hit path를 만들기 위한 mode다. RTX 3090/V100처럼 L2-only window를 W_SM만으로 만들기 어려운 GPU에서 primary L2 mode다.

의미:

```text
l2_cg_load_only - global_addr_only
  ~= same-address/same-loop control 대비 L1-bypassed L2-hit path coefficient
```

`.cg`는 global load를 L2와 그 아래 계층에 cache하고 L1에는 cache하지 않지만, 요청 자체는
L1TEX를 통과한다. 따라서 `L1 request bytes / L2 read bytes ~= 1`은 정상일 수 있으며 이를
L1 hit 오염으로 판정하면 안 된다. NCU에서는 global-load lookup 기반 L1 path hit와 hit
bytes가 거의 0인지, L2 read lookup hit/miss로 계산한 path hit가 95% 이상인지 확인한다.
aggregate L1/L2 hit rate는 background/다른 op를 포함할 수 있어 진단값으로만 남긴다.
L2는 lookup hit/miss-derived 비율 하나만으로 승인하지 않는다. NCU native op-read hit
ratio와 derived ratio가 모두 95% 이상이고 차이가 2 percentage points 이하여야 한다.
또한 `(L2 read hit sectors + L2 read miss sectors) / L2 read sectors`가 0.98-1.02인지
확인한다. observed L2 read bytes도
`active_SM * blocks/SM * ITER * load_repeat * 1024 B`로 계산한 logical expected bytes의
0.95-1.05여야 한다. `L2 miss bytes`와 `DRAM read bytes`도 함께 기록해 58-60% 같은 값이 실제
downstream miss traffic을 동반하는지 구분한다. DRAM은 cache-line transaction 때문에
32-byte L2 miss sector와 정확히 1:1일 필요는 없다.
CG mode의 시간 측정 전 warm-up도 `global_cg_warmup_kernel`의
`ld.global.cg.u32`로 수행한다. 이로써 일반 `.ca` warm-up이 L1을 먼저 채워
L2 target에 잔류 hit를 만드는 설계 혼입을 제거한다.

현재 `run_ncu_validation.sh`의 기본 수집 정책은
`NCU_REPLAY_MODE=application`, `NCU_CACHE_CONTROL=none`이다. application replay는
metric pass마다 프로그램을 다시 실행하므로 binary 내부 warm-up도 매번 재실행된다.
반대로 kernel replay/cache-control none은 application warm-up 이후의 cache 상태를
모든 pass에 동일하게 재현한다고 보장할 수 없어 cache-hit 검증의 기본값으로 쓰지 않는다.
case manifest와 NCU summary에는 replay mode, cache control, warm-up 횟수,
L2 residency policy와 address layout이 기록된다.

A100 targeted L2 재실험은 W16/W128 KiB/SM, LR4에서 policy/layout/blocks-SM 후보를
순서대로 검사한다. 먼저 normal contiguous B16과 normal `sm_interleaved` B16/B8/B4를
검사하고, 모든 normal 후보가 실패할 때 persisting을 같은 layout/B 순서로 검사한다.
`sm_interleaved`는 block-private region에 128 B guard를 넣고 virtual-grid 순서를 전치한다.
이는 공개되지 않은 세부 set/slice mapping을 가정해
결론내리는 대신 address-topology와 동시성 변화가 60% hit에 미치는 영향을 NCU로 판별하는
진단이다. 첫 완전 통과 후보만 energy에 전달하며 95% hit gate는 완화하지 않는다.
persisting 결과는 default cache가 아니라 residency-managed L2 path의 effective
coefficient다. persisting 후보는 NCU launch metadata의 실제
`launch__persisting_l2_cache_size`가 0보다 큰지도 확인한다.

### `l2_load_only`

일반 global load 기반 capacity diagnostic mode다.

주의:

- 모든 GPU에서 일반 `l2_load_only`는 L1 hit와 섞일 수 있으므로 L2-only coefficient로 부적절하다.
- 현재 final matched-control analyzer의 primary L2 pair는 `l2_cg_load_only - global_addr_only`다.

### `dram_cg_load_only`

nominal L2보다 충분히 큰 working set으로 global streaming load를 만들고, `.cg` 계열 경로로 DRAM traffic이 지배적인지 확인한다.

의미:

```text
dram_cg_load_only - global_addr_only
  ~= DRAM streaming sanity path coefficient
```

DRAM 결과는 특히 조심해야 한다. 이는 physical HBM/GDDR device pJ/bit가 아니라 board-level path coefficient다.

RTX 3090의 최신 보고 정책은 `26.709-28.409 pJ/bit`를 DRAM streaming cumulative
effective path의 **provisional range**로 사용한다. 이는 accepted 측정값이 아니며,
저장소에 현행 matched-ITER `global_addr_only` raw pair가 없기 때문이다. 과거
`clocked_empty` 차분값은 current coefficient에서 제외한다.

![RTX 3090 DRAM 최신 provisional 보고 범위](../assets/component_energy_method/current_dram_reporting_band.png)

새 플랫폼의 DRAM energy pair는 동일 ITER로 실행한다. Treatment와 control을 각각
시간 보정해 control power를 treatment 시간만큼 확장하는 방식은 control이 더 많은
주소/정수 작업을 수행해 DRAM 계수를 과도하게 낮출 수 있다. 따라서
`dram_cg_load_only`와 `global_addr_only`에 동일한 resolved ITER를 전달하고, 각
run에서 idle을 제거한 `net_E`를 직접 차분한다.

```text
delta_E_dram = net_E(dram_cg_load_only, ITER=N)
             - net_E(global_addr_only, ITER=N)

effective pJ/bit = delta_E_dram * 1e12 / (NCU DRAM bytes * 8)
```

`ITER` equality는 경로 검증과 별개의 hard gate다. NCU가 DRAM-dominant traffic을
보여도 treatment/control ITER가 다르면 coefficient는 reject한다.

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

`blocks/SM`을 바꾸면 occupancy, scheduler pressure, memory issue pattern이 함께 바뀐다. 다만
이 값은 requested grid density이지 실제 resident block 수의 보장이 아니다. 실제 residency는
NCU achieved occupancy, registers/thread, static/dynamic shared bytes per block으로 확인한다.
따라서 blocks sweep은 경향을 보는 도구이지 단독으로 component energy를 분리하는 도구가 아니다.

Memory-backed mode는 block당 최소 1 KiB logical tile이 필요하므로 `W_SM >= blocks/SM`을
만족해야 한다. 이 조건은 treatment뿐 아니라 같은 tile/address loop를 사용하는
`global_addr_only` control에도 동일하게 적용한다. 예를 들어 A100 L1의 W16/B32는
0.5 KiB/block이라 두 mode 모두 제외하고, strict W16/B16 및 diagnostic W32/B16,
W32/B32만 실행한다. Matrix는 제외 row를 `valid=false`로 보존하며, 실행 직전 binary
`--dry-run`이 valid 좌표를 다시 검증한다.

#### 9.2.1 왜 blocks/SM을 sweep하는가

![플랫폼별 blocks/SM sweep](../presentations/assets/platform_blocks_per_sm_sweep.png)

`blocks/SM` sweep은 component 종류를 바꾸는 실험이 아니라 같은 path를 얼마나 많은
warp/block이 동시에 구동할 때 effective coefficient와 power state가 달라지는지 보는
utilization 실험이다. 그래프의 마름모는 generated strict NCU anchor이고, 다른 B의 energy
row를 final로 채택하려면 그 B와 정확히 같은 좌표의 NCU acceptance가 추가로 필요하다.

| 관찰 결과 | 해석 | 추가 확인 |
|---|---|---|
| B가 증가해도 coefficient가 plateau | 해당 범위에서 block density에 덜 민감한 후보 | achieved occupancy와 clock이 안정적인지 확인 |
| B 증가와 함께 coefficient 감소 | scheduler/clock/고정 비용이 더 많은 operation에 amortize되었을 가능성 | denominator와 ITER calibration이 동일 정책인지 확인 |
| B 증가와 함께 coefficient 증가 | contention, bank conflict, scoreboard stall 또는 clock 변화 가능성 | long scoreboard, bank conflict, clock, temperature 확인 |
| requested B와 achieved occupancy가 함께 증가하지 않음 | register/shared/resource limit로 실제 residency가 제한됨 | registers/thread, shared bytes/block 확인 |

V100의 B4/B16은 저밀도와 중간 밀도 민감도를 보는 diagnostic 선택이고 strict anchor는
B32다. B1/B2/B8은 실행시간 대비 추가 식별력이 제한적이어서 기본 package에서 제외했다.

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

### 9.5 `W_SM` sweep과 memory path 판정

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

`W_SM`은 SM 하나가 반복 접근하도록 만든 논리 working set이다.

```text
W_block = W_SM / blocks_per_SM
full_GPU_working_set = active_SM * W_SM
```

**Shared는 Global L1 -> L2 -> DRAM 전이축에 포함되지 않는다.** Shared kernel은 별도
shared address space와 instruction을 명시적으로 사용한다. 따라서 Shared W를 늘린다고
Global L1이 되지 않으며, Shared 채택은 shared accesses/bytes와 global traffic 누출로
판정한다.

Global memory path에서는 W와 cache policy를 함께 바꿔 후보를 만든다. 작은 W의 normal
global load는 Global L1 후보이고, `.cg` load는 L1 cache hit를 억제한 L2 후보이며, L2보다
충분히 큰 W의 `.cg` stream은 DRAM sanity 후보다. 그러나 W만으로 경로를 확정하지 않는다.

| 의도한 path | 실험자가 설정 | NCU에서 관찰해야 하는 전이 |
|---|---|---|
| Shared | shared mode, capacity 안의 W | shared bytes/accesses 증가, global L1/L2/DRAM traffic 낮음 |
| Global L1 | 작은 W, cached global load | path-specific L1 hit >=95%, L2/DRAM 누출 <=1% |
| L2 CG | L2 안의 full-GPU W, `ld.global.cg` | L1 path hit <=1%, L2 read hit >=95%, DRAM/L2 read <=2% |
| DRAM sanity | full-GPU W >> nominal L2, `ld.global.cg` | L1 hit <=1%, capacity-aware L2 residual, DRAM bytes dominant |

![strict anchor capacity 맥락](../presentations/assets/platform_capacity_context.png)

위 capacity 비율은 설계 좌표의 nominal 맥락이지 측정 hit rate가 아니다. 특히 unified L1은
동적 partition/cache behavior를 가지므로 `W_SM / combined capacity`만으로 L1 hit를
보장할 수 없다. A100은 과거 W256 전체 27 MiB가 40 MiB L2 경계에서 불안정했던 문제를
피하기 위해 W16/32/64/128에서 NCU-accepted plateau를 찾고, H100 W64/128도 target-node
NCU 검증 전에는 후보일 뿐이다.

## 10. 플랫폼별 설계 차이

GPU architecture가 다르면 같은 `W_SM`이라도 의미가 달라진다.

| GPU | build arch | default SMs | L1/shared | L2 | 주요 설계 포인트 |
|---|---:|---:|---:|---:|---|
| RTX 3090 / GA102 | sm_86 | 82 | 128 KiB combined | 6 MiB | L2/SM이 작고 L1과 섞이기 쉬워 `l2_cg_load_only` 우선 |
| V100 / GV100 | sm_70 | 80 | 128 KiB combined, 96 KiB shared allocation | 6 MiB | CUDA 12.x `compute_70` compiler와 Volta NCU `gv100` 지원 toolchain 필요, L2는 CG path 우선 |
| A100 / GA100 | sm_80 | 108 | 192 KiB combined, 164 KiB shared allocation | 40 MiB | capacity `l2_load_only`와 `l2_cg_load_only` 비교 가능 |
| H100 / GH100 | sm_90 | 132 default | 256 KiB combined, 228 KiB shared allocation profile | 50 MiB | 현재 kernel은 WMMA compatibility path이며 WGMMA/TMA 실험 아님 |

공통 주의:

- `active_SM`은 profile 기본값이 아니라 runtime/preflight에서 확인한 값을 우선한다.
- `combined L1/shared`와 CUDA dynamic shared allocation 한계는 같은 값이 아니다.
- NCU chip alias는 플랫폼별로 다르다: V100 `gv100`, A100 `ga100`, H100 `gh100`.
- V100은 CUDA 13 `nvcc`로 새 `sm_70` binary를 만들 수 없다. CUDA compiler와 NCU는
  독립 gate이며, 각각 `nvcc --list-gpu-arch`의 `compute_70`과
  `ncu --query-metrics --chips gv100` 성공을 확인한다.
- V100은 최신 Nsight Compute에서 Volta/GV100 지원이 빠진 버전이 있을 수 있으므로 `ncu --list-chips`를 확인한다.

## 11. 표준 finalplan 좌표

`scripts/plan_platform_component_experiment.py`가 생성하는 기본 좌표는 다음과 같다.

| GPU | Tensor W_SM (KiB) | Shared W_SM (KiB) | L1 W_SM (KiB) | L2 W_SM (KiB) | DRAM W_SM (KiB) | blocks/SM |
|---|---:|---:|---:|---:|---:|---|
| RTX 3090 | 2048 | 32,64 | 8,16 | 64 with `l2_cg_load_only` | 8192 | energy 8,16; strict NCU 8 |
| V100 | 2048 | 32,64 | 8,16,32 | 32,64 with `l2_cg_load_only` | 8192 | energy 4,16,32; strict NCU 32 |
| A100 | 2048 | 64,128 | 16,32 | 16,32,64,128 with `l2_cg_load_only` | 8192 | energy 16,32; strict NCU B16에서 네 W 모두 검증 |
| H100 | 2048 | 64,128 | 16,32 | 64,128 with `l2_cg_load_only` | 8192 | 16,32 |

생성되는 energy sweep의 대표 factor는 다음이다.

V100 strict NCU 좌표는 Shared/L1/L2 모두 W32/B32다. 이는 기존 Global L1
W8/B16의 block당 tile 부족 오류를 제거하고, L2 strict working set을 2.5 MiB로
낮춰 6 MiB L2 안에서 residency margin을 확보한다. W64 L2는 5 MiB stress
보조점이다. one warp/block 구현이므로 V100 B32는 64 warps/SM의 50%이며 full
warp occupancy를 뜻하지 않는다.

| Component/path | modes | factor |
|---|---|---|
| Tensor | `reg_operand_only,reg_mma` | `reuse_factor=1,2,4,8,16` |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | energy `load_repeat=4,8,16`; NCU 1,2,4,8,16 |
| Global L1 | `global_addr_only,global_l1_load_only` | energy `load_repeat=4,8,16`; NCU 1,2,4,8,16 |
| L2 | `global_addr_only,l2_cg_load_only` | energy `load_repeat=4,8,16`; dual calibration의 최대 동일 ITER; NCU 1,2,4,8,16 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | energy `load_repeat=4,8,16`; NCU 1,4,8,16 |

권장 실행 기준:

| 항목 | 권장값 |
|---|---:|
| final seconds | 10 s 이상 |
| final repeats | 5 이상 |
| NCU sidecar | energy run과 별도 실행, `TENSOR_REUSE_FACTORS`, `MEMORY_LOAD_REPEATS`, `DRAM_LOAD_REPEATS`로 energy sweep과 같은 factor list 수집 |
| memory pJ/byte | `--require-ncu-denominator` 사용 |
| energy source | `--require-total-energy` 사용 |
| power semantics | `--expected-power-semantics`: RTX 3090/H100 `one_sec_average`, V100/A100 `instant` |
| repeated run pairing | `--pairing nearest-control` 사용 |
| pair execution order | 알려진 2-mode pair는 원자적 `control -> treatment` 순서로 회전; `pair_start_distance_ms` 확인 |
| signal quality | `--min-delta-j`, `--min-delta-fraction` 사용 |

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
| `순수 Tensor Core energy` | register, scheduler, issue, accumulator와 공통 scalar epilogue residual이 섞임 |
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
| L2 path가 L1과 섞이지 않았는가? | L2 read path hit >=95%, L1 path hit <=1%, L1 hit/request bytes <=1%, DRAM/L2 read 낮음; aggregate hit는 진단값 |
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
    GA[global_addr_only<br/>address control]
    CE --> SH[shared_scalar_load_only<br/>shared path]
    GA --> L1[global_l1_load_only<br/>L1-hit path]
    GA --> L2[l2_cg_load_only<br/>L2-hit path]
    GA --> DR[dram_cg_load_only<br/>DRAM sanity]
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
Global L1:    global_l1_load_only - global_addr_only
L2:           l2_cg_load_only - global_addr_only
DRAM sanity:  dram_cg_load_only - global_addr_only
```

이 결과는 GPU architecture와 workload geometry에 의존한다. 따라서 RTX 3090에서 통과한 좌표를 A100, V100, H100에 그대로 적용하지 말고, 각 GPU의 register, L1/shared, L2 capacity와 NCU metric 지원 상태를 확인한 뒤 같은 acceptance-first 절차를 다시 실행해야 한다.
