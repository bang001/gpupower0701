# GPU Component 동적 에너지 귀속 프로토콜

갱신일: 2026-07-22
프로토콜: `component_dynamic_attribution_v3`
대상: RTX 3090, V100, A100, H100

## 1. 목적과 측정 대상

이 프로토콜은 NVML GPU-device/board energy에서 component별로 다음 세 경계를 함께
추정한다.

1. **동일 ITER 완료 직접 차분**: 같은 반복수를 완료할 때 treatment가 control보다
   추가로 소비한 실측 net energy
2. **동일 ITER 활성시간 보정 차분(MI-ATC)**: 직접 차분에서 같은 blocks/SM의
   저활동 active-time energy를 모델로 제거한 값
3. **bytes/time 공동회귀**: NCU가 검증한 operation 또는 traffic과 추가 실행시간의
   영향을 여러 sweep 좌표에서 동시에 추정한 값
4. **control-rate ATC 진단**: control의 단위시간 net energy를 treatment 시간으로
   확장해 제거한 값. Tensor에서는 operand-rate ATC와 같다.

네 결과 모두 순수 트랜지스터, SRAM bitcell 또는 HBM/GDDR device-only energy가 아니다.
이들은 NCU로 경로가 검증된 workload-dependent effective GPU-device coefficient다.

## 2. Component별 변경 설계

| Component | 직접 차분 treatment - control | 새 기본 귀속 경계 | 주 결과 | 보조 결과 |
|---|---|---|---|---|
| Tensor MMA | `reg_mma - reg_operand_only` | 동일 pair | 동일 ITER 완료 | MI-ATC 동적 Tensor 대리값 |
| L1 Shared | `shared_scalar_load_only - shared_scalar_addr_only` | 동일 pair | 동일 ITER 완료 | MI-ATC와 shared bytes/time 공동회귀 |
| Global L1 | `global_l1_load_only - global_addr_only` | 동일 pair | 동일 ITER 완료 | MI-ATC와 L1 request bytes/time 공동회귀 |
| L2 | 과거 `l2_cg_load_only - global_addr_only` | **`l2_cg_load_only - global_l1_load_only`** | 인접 계층 동일 ITER 완료 | 인접 계층 MI-ATC와 L2 bytes/time 공동회귀 |
| External memory | 과거 `dram_cg_load_only - global_addr_only` | **`dram_cg_load_only - l2_cg_load_only`** | 인접 계층 동일 ITER 완료 | 인접 계층 MI-ATC와 external-read bytes/time 공동회귀 |

`External memory`는 controller, PHY/link, GDDR/HBM 및 background state를 포함한다.
결과 열 이름에 DRAM이 남아 있어도 physical DRAM-only coefficient로 해석하지 않는다.

### 2.1 Tensor no-MMA control의 현재 지위

표준 Tensor-only v3 package는 `reg_operand_only`와 `reg_mma`만 coefficient pair로
사용한다. 아래 모드는 scheduler/latency 반사실을 탐색하기 위해 binary에 구현되어
있지만, non-Tensor work 또는 모델 가정이 추가되므로 자동으로 더 순수한 control이
되지는 않는다.

| mode | 맞추려는 조건 | 추가로 들어가는 활동 | 현행 지위 |
|---|---|---|---|
| `reg_resident_stall_no_mma` | register residency와 낮은 issue rate | sparse `nanosleep`, register live padding | experimental diagnostic |
| `reg_issue_dependency_no_mma` | dependent issue/scheduler pressure | integer bitwise dependency chain | experimental diagnostic |
| `reg_scheduler_matched_no_mma` | warp issue와 dependency | dependent FP32 proxy arithmetic | FP32 ALU energy가 포함되는 diagnostic |

이들을 최종 control로 승격하려면 treatment와 동일 좌표에서 executed HMMA=0,
register/spill, achieved occupancy, issue/stall distribution, elapsed-time matching을 NCU로
확인하고, 추가 ALU 또는 sleep 에너지가 결과를 어떻게 바꾸는지 별도 민감도 분석을 해야
한다. 이번 2026-07-22 v3 coefficient 진단 실행에는 이 세 모드를 포함하지 않았다.

`reg_mma_disabled_latency_control`이라는 runtime-predicated 설계도 시험했지만
최종 코드에서는 제거했다. 2026-07-22 GA102 B16/RF4 NCU probe에서
`mma_enabled=0`으로 launch했는데도 HMMA `1.0496e9`개와 FP16 Tensor ops
`4.29916e12`가 treatment와 동일하게 관찰됐다. 따라서 source-level 조건문이나
predicated HMMA가 zero-MMA 반사실을 보장한다고 가정하면 안 된다.

## 3. 계산 경계

각 harness row의 `net_E_J`에는 해당 실행시간의 idle baseline이 이미 제거돼 있다.

```text
delta_E_completion = net_E_treatment - net_E_control
delta_t            = t_treatment - t_control

P_active_pair
  = median(P_clocked_empty_before, P_clocked_empty_after)

delta_E_MI_ATC
  = delta_E_completion - P_active_pair * delta_t

delta_E_control_rate_ATC
  = E_treatment - (E_control / t_control) * t_treatment
```

[과거 RTX 3090 Tensor 재비교 문서](../results/rtx3090_tensor_rf4_rf16_reuse_interpretation_20260722_ko.md)의
`4. v6 활성시간 보정` 열은 **같은 계산식**이므로 현재 용어로 MI-ATC다.
다만 그 문서의 `0.329 pJ/FLOP`은 Tensor pair보다 약 9.92시간 뒤에
수집한 B16 `clocked_empty`를 사용한 사후 모델값이다. v2/v3 MI-ATC는
pair 전후의 같은 B baseline을 같은 session에서 interleave하고 drift gate를
적용한다. 즉 수식은 같지만 과거 `0.329`의 증거 등급은 v2 final과 같지 않다.

`P_clocked_empty`는 idle power가 아니라 idle 초과 순전력이다. 새 runner는 기준선을 실험
끝에 일괄 수집하지 않고 각 pair의 바로 앞과 뒤에 배치한다.

```text
baseline-before -> (control -> treatment 또는 treatment -> control) -> baseline-after
```

Treatment/control 순서는 repeat와 coordinate에 따라 반전한다. 각 row에는 physical
`gpu_id`, `repeat`, `pair_id`, `role`, `execution_order`를 별도 기록한다.
v3는 cooldown을 각 role 사이가 아니라 pair 시작 전에 한 번만 수행한다. 중단 후
`--resume`하면 완료된 pair는 건너뛰고 불완전 pair는 새 attempt로 다시 수집한다.
Resume 전에 design, manifest, calibration과 raw CSV의 필수 schema를 검사하므로
`measurement_scope`가 없던 구형 raw 파일에는 append하지 않고 새 tag를 요구한다.

## 4. 공동회귀

Shared, Global L1, L2, External에는 다음 모델을 사용한다. Tensor에도 진단 목적으로 같은
형식을 적용할 수 있지만 MI-ATC를 우선한다.

```text
delta_E_J
  = beta_component * NCU_delta_operation_or_bits / 1e12
  + beta_time * delta_t_s
  + C(blocks_per_SM)
  + C(RF_or_LR)
  + C(execution_order)
  + C(repeat)
  + residual
```

여기서 `beta_component`의 단위는 Tensor이면 pJ/FLOP, memory이면 pJ/bit다.
`beta_time`의 단위는 W다. `C(...)`는 occupancy, factor, pair 실행순서와 repeat
pass별 고정 오프셋이다. 이 항을 생략해 B별 energy 차이나 9시간 이상 세션의
순서·온도 변화를 component slope로 오인하지 않는다. 공선성은
이 고정효과를 제거한 operation/bytes와 `delta_t`의 residual correlation으로 판정한다.
회귀 95% CI는 같은 설정의 반복을 독립 row로 과대계상하지 않도록
`coordinate_id` 단위 cluster bootstrap으로 계산한다.
Direct/MI-ATC 중앙값 CI도 같은 이유로 row bootstrap이 아니라
`coordinate_id` 단위 cluster bootstrap을 사용한다.
음수가 나오지 않도록 계수를 강제로 자르지 않는다. 다음 상황에서는 component가
식별되지 않은 것으로 판정한다.

Tensor와 memory 분모는 논리 expected 값만 무조건 사용하지 않는다. exact-coordinate
NCU에서 같은 counter의 control leakage를 먼저 뺀 뒤 energy run의 expected
operation/traffic에 scale한다.

```text
Tensor:
NCU_incremental_FLOP = NCU_treatment_tensor_ops - NCU_control_tensor_ops
denominator_FLOP = expected_treatment_FLOP *
                   (NCU_incremental_FLOP / NCU_expected_FLOP)

Memory:
NCU_incremental_bytes = NCU_treatment_bytes - NCU_control_bytes
denominator_bits = expected_treatment_bytes *
                   (NCU_incremental_bytes / NCU_expected_bytes) * 8
```

따라서 Tensor는 `reg_mma Tensor FP16 ops - reg_operand_only Tensor FP16 ops`, L2는
`L2 treatment bytes - Global-L1 control의 L2 leakage bytes`, External은 `External
treatment bytes - L2 control의 external leakage bytes`가 분모다. 차이가 0 이하이면
계수를 계산하지 않고 경로 분리 실패로 reject한다.

- operation/bytes와 `delta_t`의 상관이 너무 높아 두 효과를 분리할 수 없음
- 회귀 행렬이 singular 또는 ill-conditioned
- coefficient bootstrap 신뢰구간이 0을 포함
- LR/RF/duration subgroup에서 부호가 일관되지 않음
- NCU path 또는 denominator가 exact coordinate에서 reject됨

## 5. Parameter sweep

### 5.1 공통 축

| 축 | 기본값 | 단위 | 목적 |
|---|---|---|---|
| Tensor RF | 1, 2, 4, 8, 16 | MMA/ITER grouping count | Tensor plateau와 control bias 민감도 |
| Memory LR | 4, 8, 16 | load/ITER count | traffic/time 기울기 식별 |
| blocks/SM | RTX 3090: 4, 8, 16; V100/A100/H100: 4, 16, 32 | blocks/SM | 동일 총 work에서 occupancy와 `delta_t`를 독립적으로 변화 |
| treatment duration | 5, 15, 30 | s | transient/steady-state와 elapsed 축의 회귀 식별 |
| repeats | 3 | count/coordinate | 순서·온도·noise 분포와 bootstrap |
| active baseline | pair 앞/뒤 각 1회, 목표 3 | s/run | 시간에 가까운 blocks/SM별 active power |
| warm-up | 4 | full working-set passes | cache path의 시작 상태 안정화 |

Pilot은 RF `1,4,16`, duration `5,15 s`, repeat `1`로 경로와 calibration만 신속히
점검한다. Pilot은 final coefficient로 승격하지 않으며, final은 quiescence와 NCU를
통과한 RF `1,2,4,8,16 x 5,15,30 s x 3 repeats`를 사용한다.

### 5.2 Factorial-grid calibration

각 RF/LR를 독립적으로 같은 duration에 calibration하면 total operation/bytes와
`delta_t`가 거의 함께 움직여 공동회귀가 식별되지 않을 수 있다. 실제 RTX 3090 첫
진단 pilot에서도 L2와 External의 predictor correlation이 약 `0.999`였다.
v1 `traffic_grid`는 factor만 바꿔 이 문제를 해결하지 못했다. v3 runner의 기본
`--calibration-policy factorial_grid`는 duration별 중간 factor와 중간 blocks/SM을
anchor로 calibration한 뒤 다음 조건을 맞춘다.

```text
grid_work_units = ITER_anchor * factor_anchor * blocks_per_SM_anchor
ITER_coordinate = ceil(grid_work_units / (factor * blocks_per_SM))
```

따라서 같은 duration level 안에서 `ITER * RF/LR * blocks/SM`이 같다.
총 operation/bytes를 고정한 채 factor와 occupancy가 만드는 `delta_t` 차이를
관찰한다. duration 5/15/30 s는 anchor target이지 모든 좌표의 실제 elapsed가
정확히 그 시간이라는 뜻은 아니다. `traffic_grid`와 `independent_duration`은
direct/MI-ATC 진단에는 쓸 수 있지만 bytes/FLOP-time 회귀를 final로
승인하지 않는다.

### 5.3 플랫폼별 기본 좌표

| GPU profile | blocks/SM | Shared W_SM (KiB/SM) | Global-L1/L2 contrast W_SM (KiB/SM) | External control L2 W_SM (KiB/SM) | External W_SM (KiB/SM) |
|---|---:|---:|---:|---:|---:|
| RTX 3090 | 4, 8, 16 | 64 | 16 | 32 | 256 |
| V100 | 4, 16, 32 | 32 | 32 | 32 | 256 |
| A100 | 4, 16, 32 | 128 | 32 | 128 | 2,048 |
| H100 | 4, 16, 32 | 128 | 32 | 128 | 2,048 |

Tensor의 `W_SM=1 KiB/SM`은 CLI placeholder이며 register working set이 아니다. 실제 RF
footprint는 NCU `registers_per_thread`, requested blocks/SM, local/spill counter로 검증한다.

## 6. NCU 검증

NCU는 energy를 측정하지 않는다. NCU는 treatment/control 경로와 pJ 분모를 검증한다.
Energy와 NCU는 같은 binary hash, profile, W, blocks/SM, active SM, RF/LR 좌표를 사용한다.
NCU wrapper는 profiling 직전과 직후의 SHA-256이 같은지 확인하고
`ncu_binary_sha256`, `ncu_binary_hash_capture=pre_post_collection_verified`를 summary에
기록한다. Analyzer는 이를 energy manifest의 `binary_sha256`과 exact match하지 않으면
해당 pair를 reject한다. 실제 profiling 전에는 NCU quiescence gate도 통과해야 하며,
`NCU_SKIP_QUIESCENCE=1`은 진단용이지 final용이 아니다. Headless/native Linux는
`strict_passed`를 요구한다. WSL/WDDM의 display-attached RTX 3090에서는 NCU가
board-energy 분자가 아니라 대상 kernel counter를 수집한다는 범위 차이를 반영해
`counter_scope_passed`를 허용한다. 이 정책은 memory-controller p95 상한만 `25%`로
조정하고 GPU utilization, 외부 compute process, memory-controller max, VRAM drift 및
실제 NCU hit/access/bytes/operation acceptance는 완화하지 않는다. Energy manifest는
플랫폼과 무관하게 계속 `strict_passed`여야 한다.

| Component | treatment 필수 증거 | control 필수 증거 | 분모 | 비교 표에 반드시 포함 |
|---|---|---|---|---|
| Tensor MMA | HMMA > 0, logical MMA/FLOP 비례, spill/local=0 | workload-proportional HMMA=0, loop SASS 존재, spill/local=0 | logical FP16 MMA FLOP | HMMA count, Tensor ops, registers/thread, spill, occupancy |
| L1 Shared | shared read bytes/access/instruction > 0, global leakage 제한 | shared address loop 존재, treatment shared traffic 없음 | NCU shared read bytes | shared access count/bytes, bank conflict, long scoreboard |
| Global L1 | path-specific L1 hit >=95%, L2/DRAM leakage 제한 | global address loop 존재, input load traffic 없음 | NCU L1 request bytes | L1 access/bytes/hit%, L2/DRAM bytes, long scoreboard |
| L2 | L1 hit <=1%, final L2 service hit >=95%, DRAM leakage 제한 | Global-L1 control 자체가 L1 acceptance 통과 | NCU L2 read bytes | L1/L2 access·bytes·hit%, DRAM bytes, long scoreboard |
| External | L1 hit <=1%, L2 miss 중심, external read/expected 정합 | L2 control 자체가 L2 acceptance 통과 | NCU external/DRAM read bytes | L1/L2/DRAM access·bytes·hit%, bandwidth, long scoreboard |

A100/H100은 direct source hit와 native lookup hit만으로 판정하지 않는다. partition 간 LTC
fabric hit를 포함한 logical final-service hit와 sector conservation을 함께 확인한다.

## 7. Energy acceptance gate

| Gate | 기본 조건 |
|---|---|
| Pair identity | explicit `pair_id`; treatment/control 각각 1개; physical `gpu_id` 일치 |
| Work | treatment/control 동일 ITER, active SM, blocks/SM, RF/LR |
| Timing | pair transition gap <=30 s; 양쪽 baseline이 pair에서 각각 <=45 s |
| Runtime observability | control elapsed >=0.10 s; treatment elapsed >=1.0 s |
| Baseline drift | before/after active net power 상대 차이 <=10% |
| Harness | `smid_histogram_ok=true`, NVML total-energy, GPU-device scope |
| Direct signal | measurement-valid signed coefficient 전체의 median/CI > 0, positive fraction >=80%; row별 음수는 숨기지 않음 |
| MI-ATC | Direct와 독립적으로 signed median/CI > 0, positive fraction >=80%; 음수는 model instability 증거 |
| blocks/SM subgroup | 전체가 통과해도 각 B에서 measurement-valid >=3, signed median >0, positive fraction >=80%여야 단일 전체 coefficient 채택 |
| NCU | treatment와 control exact-coordinate acceptance; energy/NCU binary SHA-256 exact match 및 NCU 전후 hash 검증; fallback denominator로 final 금지 |
| Regression | `factorial_grid`, 최소 12 measurement-valid pairs, RF/LR 3점, blocks/SM 3점, duration 2점 이상, 실행순서 2점, repeat 3점 이상, condition/correlation gate 통과 |

직접 차분이나 MI-ATC가 음수라도 구조·NCU·baseline gate를 통과한
행은 요약과 회귀에서 제거하지 않는다. `delta_t < 0`인 좌표도 time
coefficient를 식별하는 정보다. 양수 행만으로 median을 계산하면
positive-only selection bias가 생기므로, min/median/mean/max/CI는
measurement-valid signed row 전체로 계산한다. Row별 `pair_valid`/
`mi_atc_valid`는 부호 진단을 보존하기 위한 플래그이지, 양수 조건부 중앙값을
만들기 위한 필터가 아니다.

## 8. 보고 규칙

최종 표에는 값을 하나로 합치지 않고 다음을 나란히 둔다.

| Component | 동일 ITER 완료 | clocked MI-ATC | control-rate ATC | 공동회귀 | NCU acceptance | 최종 지위 |
|---|---:|---:|---:|---:|---|---|
| 예시 | pJ/FLOP 또는 pJ/bit | 같은 단위 | 같은 단위 | 같은 단위 | access/bytes/hit/stall | accepted/model-only/reject |

- 동일 ITER 완료는 empirical completion coefficient다.
- MI-ATC는 동적 component attribution에 가까운 model-dependent surrogate다.
- control-rate ATC는 control이 no-component 반사실을 근사할 때만 의미가 있는
  진단값이다. Tensor에서는 operand-rate ATC로 표기할 수 있다.
- 공동회귀는 operation/bytes와 elapsed 효과가 실제로 식별될 때만 채택한다.
- Direct/MI-ATC는 measurement-valid/total, positive/measurement-valid,
  signed min/median/mean/max와 bootstrap CI를 표기한다.
- 전체 중앙값과 함께 blocks/SM별 signed min/median/mean/max를 표기하고, NCU
  access/bytes/hit/stall도 같은 B로 나누어 보고한다.
- 세 값이 크게 다르면 하나를 임의로 선택하지 않고 측정 경계 민감성으로 보고한다.
- 순수 silicon-level energy, 순수 L1 array energy, physical DRAM energy라는 표현은 금지한다.

## 9. 단계별 실행

1. build와 binary hash 기록
2. GPU quiescence audit
3. dry-run design matrix와 capacity 검증
4. RTX 3090 pilot energy run
5. 현행 Tensor package는 B/RF별 full Tensor sidecar를 수집하고, full-component 확장은
   memory full 및 L2-path-minimal sidecar를 추가 수집
6. exact-coordinate NCU acceptance와 Tensor HMMA/FLOP/register/spill/stall 또는
   memory access/bytes/hit/stall 표 생성
7. 직접 차분, MI-ATC, 공동회귀 분석
8. pilot에서 baseline drift, 음수 보정, 회귀 식별성 검토
9. 통과한 좌표만 RF 1/2/4/8/16, 5/15/30 s, 3회 final로 재측정
10. 동일 runner/profile을 V100/A100/H100 target node에서 실행

구현 진입점은 `scripts/run_component_dynamic_attribution.py`, 분석 진입점은
`scripts/analyze_component_dynamic_attribution.py`, NCU wrapper는
`scripts/run_component_dynamic_attribution_ncu.sh`다. Tensor cross-platform package는
`scripts/plan_tensor_fp16_cross_platform_experiment.py`로 생성한다. 생성 보고서에는
계수 방법 비교, B/RF/duration sweep, RF별 active-power gap과 함께 Tensor NCU
검증 그림을 넣는다. Tensor 그림은 treatment HMMA와 FP16 operation의 비례성,
control HMMA 0, treatment/control register footprint, zero-spill, long-scoreboard를
보여준다. 이 그림은 실행 경계를 검증하며 에너지를 직접 측정하지 않는다.
