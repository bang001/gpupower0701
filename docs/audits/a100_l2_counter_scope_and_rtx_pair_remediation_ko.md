# A100 L2 Counter Scope 및 RTX 3090 Pair 교정 감사

작성일: 2026-07-14

## 결론

1. A100의 `derived 51-62%`, `native 67-72.5%` 조합은 GA100에서 첫 L2 partition
   miss가 LTC fabric을 거쳐 다른 partition에서 hit하는 경우의 lookup 수학식과 거의
   정확히 일치한다.
2. source/TEX miss는 해당 첫 lookup의 실제 miss이며 NCU 오분류가 아니다. 과거 오류는
   이 값을 logical request의 최종 L2 miss로 해석하고, native lookup hit에도 95%를
   강제한 것이다.
3. RTX 3090 Shared/Global-L1의 기존 음수·불안정 값은 memory 회로 특성보다
   duration-scaled control과 treatment의 작업량·issue/stall 상태 불일치가 주원인이다.
4. 현행 A100 코드는 source와 `srcunit_ltcfabric` hit/miss를 같은 minimal replay에서
   수집해 logical final-service hit를 계산한다. native metric은 95% gate가 아니라
   source+fabric model의 교차검증값이다.
5. A100 L2는 새 protocol을 노드에서 재실행해야 하며, 통과 전 기존 L2 coefficient를
   final 값으로 복구하지 않는다.

## A100에서 관찰된 값

아래 값은 사용자가 A100 외부 실행에서 전달한 범위다. 이 저장소에 같은 tag의 raw
`.ncu-rep`가 반입되기 전에는 독립 재계산값이 아니라 **reported external evidence**다.

| 지표 | 관찰 범위 | 모집단 | 교정된 판정 |
|---|---:|---|---|
| device/all-TEX source L2 read hit | 51-62 % | 첫 partition lookup hit/(hit+miss) | 단독 pass/reject 금지 |
| native op-read hit | 67-72.5 % | source와 fabric lookup을 포함할 수 있는 lookup-level 모집단 | 95% 직접 gate 금지 |
| logical final-service hit | 미수집 | `(source hit + fabric hit) / source read` | 새 strict primary, >=95% 필요 |
| native-model 차이 | 미수집 | native와 source+fabric 재구성값 차이 | <=2 percentage points 필요 |

source direct hit를 `d`라고 하고 모든 direct miss가 fabric lookup에서 hit한다면 native
lookup-level hit는 `1/(2-d)`가 된다. `d=51%`이면 67.11%, `d=62%`이면 72.46%다.
사용자 보고 native 범위와 일치한다. 다만 수치 일치만으로는 증명이 아니므로 실제
`srcunit_ltcfabric` read/hit/miss와 DRAM read를 수집한다.

재현용 metric 확인:

```bash
ncu --query-metrics --chips ga100 --query-metrics-mode all | \
  grep -E 'lts__t_sector_op_read_hit_rate|srcunit_(tex|ltcfabric).*op_read.*lookup_(hit|miss)'
```

## Partition 가설 재판단

[NVIDIA A100 Tensor Core GPU Architecture whitepaper](https://images.nvidia.com/aem-dam/en-zz/Solutions/data-center/nvidia-ampere-architecture-whitepaper.pdf)는
GA100의 40 MiB L2와 partitioned 구조를 설명한다. Nsight Compute는
`lts__t_sectors_srcunit_ltcfabric...` metric을 제공하고, NVIDIA 개발자 포럼의 counter
설명은 첫 partition miss 후 LTC fabric을 통한 다른 partition lookup을 설명한다.

| 주장 | 판단 | 이유 |
|---|---|---|
| GA100 L2가 partitioned되어 있다 | 확인됨 | NVIDIA architecture whitepaper |
| 주소가 partition/slice로 분산된다 | 구조적으로 타당 | partitioned cache/controller 구조 |
| 사용자가 partition hash를 직접 지정할 수 없다 | 일반 CUDA API에서 직접 제어 인터페이스를 찾지 못함 | layout sweep은 진단 수단일 뿐 hash 제어가 아님 |
| source/TEX miss 뒤 LTC fabric lookup이 발생할 수 있다 | 확인 가능한 모델 | `srcunit_ltcfabric` counter로 직접 검증 |
| source miss를 logical final miss로 본다 | 잘못됨 | fabric hit로 회수될 수 있음 |
| native hit에 95%를 요구한다 | 잘못됨 | source와 fabric lookup을 함께 세면 logical hit 100%에서도 약 67-73% 가능 |
| 51-72.5%만으로 L2 coefficient를 계산한다 | 금지 유지 | fabric 보존성, logical hit, native-model, DRAM read가 아직 필요 |

## 개선된 A100 L2 실험

상세 설계는
`docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md`를 기준으로 한다.
W_SM은 16/128 KiB/SM anchor에서 먼저 검사한다.

| residency | address layout | blocks/SM 후보 | 목적 |
|---|---|---:|---|
| normal | contiguous | 16, 8, 4, 2, 1 | board-power 신호가 큰 좌표부터 동시 request와 partition 민감도 분리 |
| normal | sm_interleaved | 16, 8, 4 | block-region 주소 전치 효과 확인 |
| persisting | contiguous | 16, 8, 4, 1 | 지원되는 full GPU에서 residency policy 효과 확인 |
| persisting | sm_interleaved | 8, 4 | policy와 layout 결합 진단 |

각 후보에서 다음을 한 표에 기록한다.

| 분류 | 지표 | 해석 |
|---|---|---|
| source primary | device-aperture TEX hit/miss와 direct hit % | 첫 partition lookup |
| fabric recovery | device-aperture LTC-fabric hit/miss | 다른 partition lookup과 회수량 |
| logical final | `(source hit + fabric hit) / source read` | 원래 request가 L2 hierarchy에서 완료된 비율 |
| native cross-check | native op-read hit와 fabric-model 값 | 전체 lookup 모집단 재구성 검증 |
| refill | DRAM read bytes | logical miss가 실제 HBM read로 이어지는지 확인 |
| conservation | source/fabric hit+miss/read, observed/expected bytes | counter 누락·분모 오류 탐지 |

선택 기준은 logical final-service hit >=95%, source/fabric sector 보존 0.98-1.02,
native-model 차이 <=2 percentage points, L1 bypass, observed/expected bytes=0.95-1.05,
DRAM-read/L2-source-read <=2%다. 후보가 없으면 A100 L2 coefficient는
`not identified`로 끝낸다.

### NCU metric bundle 분리

전체 metric을 한 profile에 넣어 얻은 replay 수치가 보존되지 않는 문제를 막기 위해
최종 pipeline은 다음 두 실행을 분리한다.

| 실행 | 대상 | metric profile | 용도 |
|---|---|---|---|
| L2 gating | `global_addr_only,l2_cg_load_only` | `l2_path_minimal` | L1 bypass, source/fabric/native L2 lookup, logical final hit, sector 보존성, expected bytes, DRAM-read leakage 판정 |
| full diagnostic | Tensor, Shared, Global L1, DRAM, baseline | `full` | 각 비-L2 path의 traffic, HMMA, shared, spill, stall 진단 |
| canonical merge | 위 두 summary | source column 보존 | acceptance와 coefficient 계산에 하나의 CSV를 제공하되 서로 다른 replay 결과를 같은 행에 섞지 않음 |

L2 selector는 treatment/control 모두 `ncu_metric_profile=l2_path_minimal`이어야 하며,
source와 fabric counter가 보존되지 않으면 logical hit가 높아도 reject한다. 선택 후에는
같은 최소 profile로 모든 W/LR 좌표를 다시 실행한다. 전체 metric L2 실행은 원인
분석용으로만 남기며 strict denominator나 hit gate를 덮어쓰지 않는다.
최종 package audit도 acceptance CSV를 그대로 신뢰하지 않고 sector 보존비와
`active_SM * blocks/SM * ITER * load_repeat * 1024 B` expected traffic을 다시 계산한다.

### RTX 3090 protocol 실측 확인

2026-07-14에 GA102 W64 KiB/SM, B8, LR4, ITER 100,000에서 최소 profile을 실제 실행했다.
control과 treatment 모두 application replay 4회였고 treatment 결과는 다음과 같다.

| 지표 | 값 | 판정 |
|---|---:|---|
| L1 path hit | 0 % | L1 bypass pass |
| device/all-TEX derived L2 hit | 99.9991 % | pass |
| native L2 op-read hit | 99.9451 % | pass |
| `(hit+miss)/device read` | 0.99998 | counter coherent |
| observed/expected L2 bytes | 1.00002 | denominator pass |
| application replay pass | 4 회 | 전체 bundle의 8회보다 감소 |
| long scoreboard | 369.971 NCU per-issue-active signal | 100% 제한의 elapsed-time 비율이 아니며 진단값 |

같은 좌표의 address control은 global input request가 0이고 acceptance를 통과했다. 이
결과는 새 counter protocol이 GA102에서 동작한다는 검증이며, A100 hit가 높아졌다는
증거는 아니다.

## RTX 3090 Shared/Global-L1 원인

기존 RTX 3090 run에서 Shared control `clocked_empty`의 평균 power는 LR4에서 약
186.7 W, LR16에서 약 225.4 W로 변한 반면 treatment는 약 218-220 W였다. duration-scaled
차분은 LR4 약 +355 J, LR16 약 -119 J로 부호가 바뀌었다. Global-L1도 treatment/control
power가 거의 같고 독립 calibration ITER가 약 6-7% 달라 다수 pair가 noise floor에서
음수가 되었다.

이는 다음 가정을 위반한다.

```text
treatment energy = independent control power * treatment time + memory-only energy
```

memory dependency stall은 scheduler issue, SM clock activity와 완료시간을 함께 바꾸므로
control power를 단순 시간 확대할 수 없다.

## 구현 교정

| 항목 | 과거 | 현행 |
|---|---|---|
| Shared control | `clocked_empty` | `shared_scalar_addr_only` |
| Shared 공통 구조 | integer loop만 유사 | 같은 dynamic shared allocation/init/barrier/index/checksum loop |
| Shared load 차이 | 구조 전체가 다름 | treatment만 반복 shared read 발행 |
| Shared/L1 작업량 | mode별 ITER, duration scaling | dual calibration의 큰 ITER를 양쪽에 동일 적용 |
| energy 차분 | scaled control power | `net_E_treatment(N)-net_E_control(N)` |
| Shared NCU gate | treatment traffic 중심 | treatment shared read >0, control shared read=0; init write 허용 |

RTX 3090 sm_86 현재 build의 ptxas 출력에서 Shared treatment/control은 모두 26
registers/thread, spill 0이다. 이는 register footprint를 맞췄다는 정적 증거일 뿐이며,
coefficient의 타당성은 새 energy 반복과 exact-coordinate NCU acceptance로 다시 판단한다.

2026-07-14 targeted 5초 x 5회, equal-ITER, exact-NCU denominator 결과는 Shared
`0.637283 pJ/bit`(15/15 valid), Global-L1 `0.430305 pJ/bit`(14/15 valid)였다. 각각
medium-high와 medium/caution 증거이며 10초 full platform package를 대체하지 않는다.

## 남은 한계

- 동일 ITER여도 treatment가 더 오래 걸린다. 결과는 순수 SRAM bitcell energy가 아니라
  같은 loop work를 완료할 때 추가된 board-level effective energy다.
- NCU replay와 NVML energy run은 동시에 수행하지 않는다. exact coordinate와 kernel
  revision을 맞추지만 두 실행의 온도·클럭이 완전히 같다고 보장하지 않는다.
- A100 L2가 새 후보에서도 logical final-service 95% plateau를 만들지 못하면 현재
  kernel로는 L2를 분리하지 못한 것이다. direct/native lookup hit에 95%를 강제하거나
  숫자를 만들기 위해 logical threshold를 낮추지 않는다.

## 관련 파일

- `scripts/plan_platform_component_experiment.py`
- `scripts/run_ncu_validation.sh`
- `scripts/summarize_ncu_cache_metrics.py`
- `scripts/merge_ncu_validation_summaries.py`
- `scripts/select_l2_path_configuration.py`
- `scripts/analyze_matched_control_energy.py`
- `src/kernels.cu`
- `docs/methodology/howitworks.md`
- `docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md`
