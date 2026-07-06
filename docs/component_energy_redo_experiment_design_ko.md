# Component energy 실험 재설계

작성일: 2026-07-03

업데이트: RTX 3090/A100 architecture 차이, 기존 실험 폐기 기준, 2026-07-05
preflight/smoke 실행 결과, 다음 NCU/final 실행 순서는
`docs/component_energy_separation_execution_plan_ko.md`를 우선한다.

## 한 줄 결론

현재 결과는 component를 완전히 잘못 측정했다기보다, **문헌의 device/circuit
energy와 우리가 얻은 board-level effective coefficient를 섞어 해석한 것이
위험하다.** 따라서 기존 결과는 최종값으로 쓰지 않고, NCU actual traffic을
denominator로 쓰는 transaction-path 실험으로 다시 진행한다.

## 이번 재설계의 원칙

| 원칙 | 결정 |
|---|---|
| 정직한 측정 대상 | 순수 bitcell energy가 아니라 GPU hierarchy transaction-path effective energy를 측정한다. |
| 문헌 비교 기준 | HBM device, SRAM primitive, GPU transaction path, NVML board coefficient를 같은 표에서 직접 비교하지 않는다. |
| denominator | static `expected_*_bytes`는 smoke/설계 점검용이다. 최종 pJ/bit는 NCU actual traffic counter를 사용한다. |
| register | pure register-file pJ/bit는 CUDA/NVML microbenchmark만으로 주장하지 않는다. `register operand/control path`로 표기한다. |
| L1/shared | shared memory와 global L1 cache는 분리한다. 기존 `shared/L1` 묶음은 최종 표에서 폐기한다. |
| 결과 채택 | hit rate, access count, stall, spill, SMID coverage를 통과한 row만 coefficient에 사용한다. |

## 기존 설계에서 잘못된 점

| 항목 | 기존 설계 | 잘못된 이유 | 새 결정 |
|---|---|---|---|
| `*_load_only - empty` | load path pJ/byte로 해석 | `empty`와 load mode의 elapsed가 다르고 checksum/address/control/stall이 섞임 | 최종 component 값에서 폐기 |
| static bytes | `expected_shared/l2/dram_bytes`로 pJ/bit 계산 | logical byte이며 실제 L1/L2/DRAM sector traffic이 아님 | NCU actual byte를 우선 |
| `shared/L1` 묶음 | shared와 L1을 같은 계층으로 보고 해석 | NVIDIA의 unified L1/shared 구조와 shared memory instruction path는 다름 | `shared`, `global_l1`, `l2`, `dram`으로 분리 |
| L2/DRAM 경계 | W_SM과 nominal L2 capacity만으로 판단 | 실제 cache hit/miss는 access pattern, cache policy, warm-up, NCU replay 영향에 좌우됨 | NCU hit rate와 sector count로 row 채택 |
| register | `reg_mma`의 W_SM 또는 register footprint를 RF energy로 해석 | W_SM은 memory working set이고 ptxas register count가 실제 register footprint임 | ptxas spill-free + NCU local memory 0 조건에서 operand/control path로만 보고 |
| 회귀 | 모든 component를 하나의 OLS에 넣음 | collinearity와 mode baseline 때문에 음수/0-bound 발생 | 계층별 rate model + mode/control baseline + bootstrap CI |
| 문헌 비교 | HBM2 3.9 pJ/bit와 GPU path 20-30 pJ/bit를 같은 값처럼 비교 | device energy와 transaction path energy가 다름 | 표에 `level`, `denominator`, `scope`를 필수 표기 |

## 새 실험 목표

최종 보고 표는 다음 네 종류로 분리한다.

| 결과 레벨 | 단위 | 의미 | 채택 조건 |
|---|---|---|---|
| Tensor Core incremental | pJ/FLOP | no-MMA register/control 대비 MMA 추가분 | tensor instruction count 확인, no spill |
| Register operand/control path | pJ/logical operand bit | WMMA fragment/register operand를 유지/소비하는 logical path | no spill, local memory traffic 0, register footprint 보고 |
| Shared memory transaction path | pJ/actual shared bit | shared memory load/store instruction path | NCU shared access count 사용 |
| Global memory transaction path | pJ/actual L1/L2/DRAM bit | global load가 L1/L2/DRAM을 통과하는 effective path | NCU L1/L2/DRAM hit/access/stall 기준 통과 |

주의: 위 값들은 여전히 board-level dynamic energy에서 추정한 effective coefficient다.
HBM device-only energy 또는 SRAM bitcell energy가 아니다.

## 필요한 mode 재정의

### 유지할 mode

| Mode | 새 역할 | 비고 |
|---|---|---|
| `empty` | duration-matched baseline 후보 | 단독 subtraction이 아니라 model baseline으로 사용 |
| `reg_operand_only` | no-MMA register/control baseline | pure RF energy가 아님 |
| `reg_mma` | Tensor Core incremental 측정 | `reg_operand_only`와 matched pair |
| `shared_load_only` | shared memory transaction path | NCU shared counter 필수 |
| `l2_load_only` | L2-hit 후보 | NCU가 L2-hit row로 확인할 때만 채택 |
| `dram_load_only` | DRAM streaming 후보 | NCU가 DRAM row로 확인할 때만 채택 |

### 추가해야 할 mode

| 새 mode | 목적 | 필요한 이유 |
|---|---|---|
| `global_l1_load_only` | global load가 L1에서 hit되는 path 측정 | 기존 코드는 shared memory와 global L1 cache를 분리하지 못함 |
| `addr_only` | 동일한 index/address generation에서 load만 제거한 control | memory byte slope에서 address/control 비용을 분리 |
| `clocked_empty` | 목표 시간 동안 scheduler/loop만 유지 | 짧은 `empty`와 긴 load kernel 차이를 줄임 |
| `global_l2_cold_warmup` 또는 strict `l2_load_only` | warm-up 이후 L2 hit 확인 | L2 row 채택 기준을 자동화 |
| `dram_stream_cold` 또는 strict `dram_load_only` | L2보다 충분히 큰 streaming access | DRAM row에서 L2 reuse를 줄임 |

추가 mode는 새 이름을 쓰는 것이 좋다. 기존 `l2_load_only`, `dram_load_only`를
바로 최종 mode로 승격하면 과거 결과와 의미가 섞인다.

## Working set 설계

Working set은 GPU별 architecture profile로 계산한다.

| 계층 | W_SM 기준 | 총 working set 기준 | 채택 기준 |
|---|---|---|---|
| Register/control | W_SM 사용 금지 | ptxas registers/thread와 blocks/SM 기준 | spill 0, local memory sectors 0 |
| Shared | shared capacity의 25-75% | per-SM shared resident | shared access가 expected와 정합 |
| Global L1 | L1 usable capacity보다 작게 | per-SM 반복 reuse | L1 hit rate 높음, L2/DRAM traffic 낮음 |
| L2 | L1보다 크고 total <= 50-75% L2 | full GPU L2 resident | L2 hit rate 높음, DRAM traffic 낮음 |
| DRAM | total >= 4x L2 | streaming/cold walk | DRAM bytes가 expected와 정합, L2 hit 낮음 |

GPU별 예시는 다음처럼 시작한다. 실제 채택은 NCU 결과로 판단한다.

| GPU | Shared 후보 W_SM | Global L1 후보 W_SM | L2 후보 W_SM | DRAM 후보 W_SM |
|---|---:|---:|---:|---:|
| V100 | 16, 32, 64 KiB | 4, 8, 16 KiB | 64 KiB | 512 KiB, 8192 KiB |
| RTX 3090 | 16, 32, 64 KiB | 4, 8, 16 KiB | 64 KiB | 512 KiB, 8192 KiB |
| A100 | 32, 64, 128 KiB | 4, 8, 16, 32 KiB | 128, 256 KiB | 1024 KiB, 8192 KiB |
| H100 | 32, 64, 128 KiB | 4, 8, 16, 32 KiB | 128, 256 KiB | 1024 KiB, 8192 KiB |

이 표는 시작점일 뿐이다. 최종 row는 capacity rule이 아니라 NCU hit/access rule로
선택한다.

## 측정 절차

### Phase 0. 환경 고정

| 항목 | 기준 |
|---|---|
| persistence mode | 가능하면 활성화 |
| clocks | 가능하면 graphics/memory clock 고정 |
| thermal | 시작 온도와 종료 온도를 기록, throttling row 제외 |
| power source | NVML power/energy source를 CSV에 기록 |
| background | 다른 GPU process 없음 |
| NCU 권한 | performance counter 접근 가능 여부를 preflight에서 확인 |

clock 고정이 불가능한 환경에서는 결과 표에 `unlocked_clocks`를 명시하고, row별
clock/temperature/power cap 상태를 함께 보고한다.

### Phase 1. Energy run

NCU를 붙이지 않고 energy를 측정한다. NCU replay는 runtime과 cache behavior를
바꿀 수 있으므로 energy run과 NCU validation run은 분리한다.

| 항목 | smoke | final |
|---|---:|---:|
| duration per row | 5 s | 20-30 s |
| repeats | 3 | 7 이상 |
| order | mode/W/repeat randomized | randomized |
| active SM | full SM 우선 | full SM, optional partial SM |
| blocks/SM | valid set 전체 | valid set 전체 |

### Phase 2. NCU sidecar run

대표 좌표와 outlier 좌표만 NCU로 검증한다. NCU 결과는 energy 값으로 쓰지 않고,
actual traffic denominator와 row acceptance에 사용한다.

필수 metric은 다음이다.

| 분류 | 필수 값 |
|---|---|
| Tensor | tensor instruction count, tensor pipe utilization |
| Shared | shared load/store transaction 또는 sector count |
| L1 | L1 hit rate (%), L1 request/sector count |
| L2 | L2 hit rate (%), L2 sector count |
| DRAM | DRAM sector/byte count, DRAM throughput |
| Spill | local memory load/store sector count |
| Stall | long scoreboard, memory dependency, barrier, not selected, issue active 비율 |
| Occupancy | active warps, achieved occupancy, SM active % |

### Phase 3. Row acceptance

| Row type | 통과 기준 |
|---|---|
| 공통 | SMID coverage pass, elapsed >= final target의 80%, net energy > 0, thermal throttle 없음 |
| Tensor | tensor inst count > 0, local memory traffic 0, top stall이 barrier/control로 치우치지 않음 |
| Register/control | tensor inst count 0, local memory traffic 0, ptxas spill 0 |
| Shared | shared actual bytes/expected bytes가 0.5-2.0 범위, DRAM bytes는 낮음 |
| Global L1 | L1 hit rate >= 80%, DRAM bytes 낮음 |
| L2 | L2 hit rate >= 80%, DRAM bytes 낮음, L1 hit이 지배적이면 L1 row로 재분류 |
| DRAM | DRAM bytes가 충분히 크고 L2 hit rate가 낮음, long scoreboard stall을 보고 |

기준을 통과하지 못한 row는 버리지 말고 `rejected_reason`을 남긴다.

## 분석 모델

### Tensor

```text
tensor_pJ_per_FLOP =
  median_over_pairs(
    (P_reg_mma - P_reg_operand_only) / FLOP_rate_reg_mma
  )
```

채택 조건은 matched pair의 elapsed, clocks, NCU tensor instruction count가
정합하는 것이다. 이 값은 Tensor Core incremental 후보이며, register/control이
완전히 제거된 순수 tensor bitcell energy가 아니다.

### Register/control

```text
register_operand_path =
  slope(P_reg_operand_only, logical_operand_bit_rate)
```

최종 표기명은 `Register operand/control path`로 한다. `Register file energy`라고
쓰지 않는다.

### Memory transaction path

energy run의 power와 NCU sidecar의 actual traffic rate를 결합한다.

```text
P_dynamic =
  alpha_mode
  + beta_shared * ncu_shared_bit_rate
  + beta_l1     * ncu_l1_bit_rate
  + beta_l2     * ncu_l2_bit_rate
  + beta_dram   * ncu_dram_bit_rate
  + residual
```

여기서 `beta_*`는 pJ/actual bit이다. L2/DRAM은 increment와 cumulative path를
분리해 보고한다.

```text
L1 path   = beta_l1
L2 path   = beta_l1 + beta_l2_increment
DRAM path = beta_l1 + beta_l2_increment + beta_dram_increment
```

shared memory는 global L1 path와 별도 표에 둔다.

### 불확실성

| 항목 | 방식 |
|---|---|
| 중심값 | median 또는 robust regression estimate |
| 신뢰구간 | bootstrap 95% CI |
| 품질 | relative RMSE, residual plot, coefficient sign |
| 민감도 | static denominator 결과와 NCU denominator 결과를 병렬 보고 |

## 최종 보고 표 형식

| Component/path | Level | Estimate | Unit | 95% CI | Denominator | NCU status | 해석 |
|---|---|---:|---|---:|---|---|---|
| Tensor Core incremental | board effective | TBD | pJ/FLOP | TBD | FLOP | tensor count verified | no-MMA control 대비 추가분 |
| Register operand/control | board effective | TBD | pJ/logical operand bit | TBD | logical operand bits | spill-free verified | RF bitcell 아님 |
| Shared memory path | transaction path | TBD | pJ/actual bit | TBD | NCU shared bytes | required | shared instruction path |
| Global L1 hit path | transaction path | TBD | pJ/actual bit | TBD | NCU L1 bytes | required | global L1 hit load path |
| L2 hit increment | transaction path | TBD | pJ/actual bit | TBD | NCU L2 bytes | required | L1 대비 추가분 |
| DRAM streaming increment | transaction path | TBD | pJ/actual bit | TBD | NCU DRAM bytes | required | L2 대비 추가분 |

## 코드 반영 계획

현재 구현 상태는 다음과 같다.

| 항목 | 현재 상태 | 판단 |
|---|---|---|
| `reg_operand_only`, `reg_mma` | 구현됨 | Tensor incremental smoke에는 사용 가능 |
| `shared_load_only` | 구현됨 | shared memory path 후보이나 NCU actual shared counter 검증 전에는 final 불가 |
| `l2_load_only`, `dram_load_only` | 구현됨 | strict L2/DRAM row로 채택하려면 NCU hit/access 검증 필요 |
| `global_l1_load_only` | 구현됨, RTX 3090 smoke 통과 | NCU L1 hit 검증 전에는 L1 후보 |
| `addr_only` | 구현됨, RTX 3090 smoke 통과 | address/control baseline 후보 |
| `clocked_empty` | 구현됨, RTX 3090 smoke 통과 | duration-matched control 후보 |
| NCU sidecar 요약 | 확장됨 | shared/L1/L2/DRAM byte 후보와 repeat metadata 출력 |
| NCU summary join | 구현됨 | sidecar ITER와 energy ITER 차이를 scale해서 join |
| actual-traffic analyzer | 부분 구현 | 기존 `fit_component_energy_model.py --byte-source ncu|prefer-ncu` 경로 사용 가능. robust final 전용 analyzer는 추가 여지 있음 |

| 단계 | 변경 |
|---|---|
| 1 | `include/config.hpp`에 `global_l1_load_only`, `addr_only`, `clocked_empty` mode 추가 |
| 2 | `src/kernels.cu`에 cache-hit L1 global load kernel과 address-only control kernel 추가 |
| 3 | `src/main.cu` 결과 row에 `mode_family`, `denominator_level`, `expected_l1_bytes` 추가 |
| 4 | `scripts/run_component_regression_sweep.py`에 새 transaction-path mode 실행 경로 추가 |
| 5 | `scripts/run_ncu_validation.sh`에 `global_l1_load_only`와 strict metric set 추가 |
| 6 | `scripts/summarize_ncu_cache_metrics.py` output을 energy CSV와 join 가능한 schema로 고정 |
| 7 | `fit_component_energy_model.py`에 `expected_l1_bytes`/`ncu_l1_bytes` feature 추가. 필요 시 final 전용 robust analyzer 추가 |
| 8 | 기존 `estimate_component_energy.py` 결과에는 `legacy_effective_static` label을 붙여 final과 분리 |

2026-07-03 진행분:

| 항목 | 결과 |
|---|---|
| 새 mode 구현 | `clocked_empty`, `addr_only`, `global_l1_load_only` 추가 |
| 새 CSV 컬럼 | `expected_l1_bytes`, `expected_addr_ops`, `ncu_l1_bytes`, `mode_family`, `denominator_level` 추가 |
| build | RTX 3090 `sm_86` build 통과, 새 kernel ptxas spill 0 |
| new-mode smoke | `results/raw/rtx3090_redo_new_modes_smoke_20260703.csv`, 8/8 SMID pass, 음수 net energy 0 |
| transaction energy smoke | `results/raw/rtx3090_redo_transaction_energy_smoke_20260703.csv`, 13/13 SMID pass, 음수 net energy 0 |
| smoke static fit | `results/summary/rtx3090_redo_transaction_energy_smoke_20260703_fit.md`, relative RMSE 7.223% |
| NCU | sandbox 밖에서는 CUDA driver 연결 성공, 하지만 `ERR_NVGPUCTRPERM`으로 performance counter 접근 실패 |

주의: smoke static fit의 `shared/l1/l2/dram` coefficient는 최종값이 아니다.
`byte source = static`이고 NCU actual traffic이 없으므로 row 구조와 pipeline
동작 확인용으로만 사용한다.

## 실행 순서

1. RTX 3090에서 smoke run으로 새 mode가 의도대로 동작하는지 확인한다.
2. RTX 3090에서 NCU sidecar를 먼저 통과시킨다. NCU가 막히면 final pJ/bit는 보류한다.
3. RTX 3090 final energy run을 수행한다.
4. 같은 matrix를 A100/V100/H100에 profile-aware로 적용한다.
5. GPU별 결과는 하나의 회귀로 합치지 않고, GPU별 coefficient를 먼저 보고한 뒤 architecture 차이를 비교한다.

## 과감한 폐기 기준

다음은 최종 보고서에서 폐기한다.

| 폐기 대상 | 이유 |
|---|---|
| 기존 `shared/L1 increment = 6.205 pJ/bit` 단독 주장 | shared와 global L1이 분리되지 않았고 static denominator 기반 |
| 기존 `L2 increment = 1.348 pJ/bit` 단독 주장 | NCU actual L2 traffic 검증 전 |
| 기존 `Register = 1.019 pJ/logical bit`를 RF energy로 쓰는 표현 | logical operand/control path일 뿐 |
| `load_only - empty` 기반 component 표 | elapsed/control/stall mismatch |
| NCU 없는 memory pJ/bit final claim | actual traffic denominator 부재 |

기존 결과는 `legacy/static effective coefficient`로 보존하되, 논문 또는 최종
보고서의 대표 component energy 표에는 넣지 않는다.

## 성공 조건

이번 재실험이 성공했다고 말하려면 다음을 모두 만족해야 한다.

| 조건 | 기준 |
|---|---|
| 재현성 | final repeat의 coefficient CV <= 20% 또는 bootstrap CI가 중심값의 +/-30% 이내 |
| 계층 정합 | DRAM cumulative path > L2 cumulative path > L1 path 또는 그 위반 이유를 NCU로 설명 |
| NCU 정합 | 채택 row의 hit/access/stall 기준 통과 |
| 문헌 정합 | GPUJoule/Horowitz/HBM2 값과 비교할 때 level/scope/denominator가 명시됨 |
| 음수 방지 | physical candidate coefficient는 음수로 보고하지 않고, 식별 실패는 `not_identified`로 표기 |
| 솔직한 제한 | device/circuit energy가 아니라 board-level transaction-path effective energy라고 명시 |

## 바로 다음 작업

1. RTX 3090 또는 A100 노드에서 NCU performance counter 권한을 해결한다.
2. `scripts/run_ncu_validation.sh`를 다시 실행해 shared/L1/L2/DRAM actual bytes,
   hit rate, stall summary를 확보한다.
3. `scripts/join_ncu_summary.py`로 NCU summary를 energy CSV에 join한다.
4. NCU 기준을 통과한 row만 final 20-30 s x 7 repeats로 확장한다.
5. 같은 절차를 A100/V100/H100 노드에서 반복한다.
