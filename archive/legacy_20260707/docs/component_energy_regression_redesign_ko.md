# Component Energy Regression Redesign

작성일: 2026-07-03

업데이트: 문헌 pJ/bit 감사 이후 최종 실험 기준은
`docs/component_energy_redo_experiment_design_ko.md`를 따른다. 이 문서의
static expected byte 기반 결과는 legacy/smoke 분석으로만 사용하고, 최종
component energy 표에는 NCU actual traffic 기반 결과만 채택한다.

## 목적

기존 `component_pairs` 방식은 같은 `ITER`를 여러 mode에 재사용해 paired
difference를 계산했다. 이 방식은 mode별 실행 시간이 크게 달라지면 component
energy를 분리하지 못한다. 실제 RTX 3090 focused run에서 `empty`는 약
0.01 s에 끝났지만 `shared_load_only`, `l2_load_only`, `dram_load_only`는
각각 수 초 동안 실행되었다. 따라서 `load_only - empty`는 memory byte
energy가 아니라 긴 active kernel 실행 에너지를 대부분 포함했다.

이 redesign의 목표는 현재 코드를 다음 구조로 바꾸는 것이다.

1. 측정은 mode마다 목표 시간에 맞춘다.
2. memory, tensor, store, time 항을 회귀 모델에서 동시에 추정한다.
3. static expected byte 기반 결과와 NCU actual byte 기반 결과를 구분한다.
4. 음수 계수, 큰 residual, collinearity를 자동으로 경고한다.
5. 보고서에는 물리 component energy가 아니라 microbenchmark 조건의
   effective coefficient로 제한해 쓴다.

## 2026-07-03 음수 coefficient 재점검 결론

RTX 3090 focused run의 초기 OLS 회귀에서 `reg_operand_ops`,
`shared_bytes_static`, `store_bytes_static`가 음수로 나왔다. 원인은 단순한
계산 실수가 아니라 다음 설계 문제가 겹친 것이다.

| 원인 | 관측 | 영향 |
|---|---|---|
| mode baseline 미분리 | `reg_operand_only`, `store_only`의 median `net_E_J`가 `empty`보다 낮은 구간이 있음 | 전역 OLS가 mode별 fixed/control 비용을 component slope에 밀어 넣음 |
| duration calibration의 byte 상쇄 | `load_repeat`를 키우면 binary calibration이 `ITER`를 줄여 총 expected byte가 크게 늘지 않음 | byte slope 식별력이 약해짐 |
| static byte denominator | `expected_*_bytes`는 logical byte이며 NCU actual L1/L2/DRAM traffic이 아님 | pJ/byte를 physical SRAM/L2/HBM 값으로 해석할 수 없음 |
| load-only control overhead | checksum, address generation, scheduler/issue/stall이 함께 포함됨 | memory-only energy로 차분 불가 |
| 짧은 fixed-ITER row | elapsed가 짧은 row는 idle subtraction 후 `net_E_J`가 음수가 될 수 있음 | smoke 결과에서 noise가 계수에 섞임 |

따라서 최종 보고에서는 음수 coefficient를 그대로 pJ로 쓰지 않는다. 새 분석
정책은 다음과 같다.

| 정책 | 구현 | 해석 |
|---|---|---|
| mode/family baseline 분리 | `fit_component_energy_model.py --baseline-terms mode|family` | mode별 fixed/control offset을 component slope와 분리 |
| 비음수 constrained fit | `--non-negative` active-set solver | 물리 component 후보 slope를 0 이상으로 제한 |
| unconstrained probe 보존 | `unconstrained_estimate` 컬럼 | 왜 0에 붙었는지, 기존 OLS가 음수였는지 추적 |
| 0 coefficient 처리 | `zero_bound_or_not_identified` 경고 | 0 pJ가 아니라 현재 matrix에서 positive independent slope가 식별되지 않았다는 뜻 |
| 품질 필터 | `--min-elapsed-s`, `--exclude-negative-net-energy` | 짧은/noisy row를 smoke 분석에서 제외 가능 |
| fixed-ITER supplemental | `run_component_regression_sweep.py --iters` | byte variation 및 monotonicity 점검용. elapsed spread가 크면 final pJ로 쓰지 않음 |

### 재분석 결과 요약

기존 duration-calibrated raw를 mode baseline + 비음수 제약으로 재분석하면
physical 후보 항의 음수는 제거된다.

| 분석 | rows | RMSE (J) | relative RMSE (%) | R2 | 음수 physical coefficient |
|---|---:|---:|---:|---:|---|
| duration + mode baseline + non-negative | 224 | 36.630 | 7.208 | 0.936 | 없음 |
| duration + family baseline + non-negative | 224 | 41.603 | 8.186 | 0.918 | 없음 |
| corrected fixed-ITER + mode baseline + non-negative | 24 | 13.423 | 3.975 | 0.9996 | 없음 |

대표 coefficient는 다음처럼 validity label과 함께 해석한다.

| 분석 | coefficient | estimate | 단위 | 해석 |
|---|---|---:|---|---|
| duration + mode baseline | `shared_bytes_static` | 1.865 | pJ/byte | static byte 기준 후보. NCU actual byte 전에는 보조값 |
| duration + mode baseline | `l2_bytes_static` | 3.786 | pJ/byte | static byte 기준 후보 |
| duration + mode baseline | `dram_bytes_static` | 0 | pJ/byte | `zero_bound_or_not_identified`; 현재 matrix에서 positive slope 식별 실패 |
| duration + mode baseline | `FLOP` | 0 | pJ/FLOP | `zero_bound_or_not_identified`; register/control과 분리 부족 |
| corrected fixed-ITER | `shared_bytes_static` | 46.907 | pJ/byte | elapsed spread가 커 active-time energy가 byte slope에 포함됨 |
| corrected fixed-ITER | `l2_bytes_static` | 52.638 | pJ/byte | monotonicity/stress-test 결과, final pJ 아님 |
| corrected fixed-ITER | `dram_bytes_static` | 287.092 | pJ/byte | monotonicity/stress-test 결과, final pJ 아님 |

fixed-ITER 결과는 음수 방지와 byte variation 검증에는 유용하지만 elapsed가
0.16~13.30 s로 벌어졌다. 이 상태에서 pJ/byte는 memory cell energy가 아니라
load loop 전체 active-time coefficient가 된다. 최종 component pJ에는
duration-calibrated non-negative 결과와 NCU actual traffic 검증을 우선한다.

## 2026-07-03 architecture-aware broad validation 반영

후속 확장 실험에서는 전역 회귀 하나로 모든 component를 강제로 분리하는 대신,
component별로 맞는 식별 축을 따로 사용한다.

| Component | 최종 분석 경로 | 이유 |
|---|---|---|
| Tensor Core | `reg_mma - reg_operand_only` matched pair의 power-rate median | no-MMA register-fragment/control을 뺀 MMA incremental 후보 |
| Register operand | `reg_operand_only` 내부 power-vs-logical-op-rate slope | `reg_operand_only - empty`는 음수이므로 폐기 |
| Shared/L1, L2, DRAM | `shared <= L2 <= DRAM` ordered memory rate model | unconstrained L2 slope가 noise로 음수/0에 붙는 문제 방지 |

RTX 3090에서 현재 보고 가능한 값은 다음이다.

| Component | Estimate | Unit | 보조 환산 |
|---|---:|---|---:|
| Tensor Core incremental | 0.219729 | pJ/FLOP | positive-pair median 0.237645 pJ/FLOP |
| Register operand | 8351.222 | pJ/logical-reg-op | 1.019436 pJ/logical-operand-bit |
| Shared/L1 increment | 49.641 | pJ/byte | 6.205 pJ/bit |
| L2 increment over Shared/L1 | 10.784 | pJ/byte | 1.348 pJ/bit |
| DRAM increment over L2 | 169.443 | pJ/byte | 21.180 pJ/bit |

Memory path 전체 비용은 increment를 누적한다.

| Path | Estimate | Unit | pJ/bit |
|---|---:|---|---:|
| Shared/L1 cumulative path | 49.641 | pJ/byte | 6.205 |
| L2-hit cumulative path | 60.425 | pJ/byte | 7.553 |
| DRAM streaming cumulative path | 229.868 | pJ/byte | 28.733 |

이 값들은 NVML board energy와 static expected traffic으로 계산한 effective
microbenchmark coefficient다. NCU actual traffic과 stall 검증 전에는 순수
SRAM/L2/DRAM bitcell energy 또는 논문상의 physical component energy로 쓰지
않는다.

Architecture별 dry-run matrix에서는 L2/shared 용량 차이가 regime boundary에
반영됐다.

| Profile | shared/L2 후보 `W_SM` | DRAM 후보 `W_SM` | 주의 |
|---|---|---|---|
| RTX 3090 | 1-64 KiB | 128, 512, 8192 KiB | `blocks/SM=32` invalid |
| V100 | 1-64 KiB | 128, 512, 8192 KiB | TF32/BF16 없음 |
| A100 | 1-128 KiB | 512, 8192 KiB | L2 40 MiB로 DRAM boundary가 뒤로 이동 |
| H100 | 1-128 KiB | 512, 8192 KiB | 현재 kernel은 WMMA compatibility path, WGMMA/TMA energy 아님 |

자세한 판단 보고서는
`results/summary/component_energy_architecture_broad_validation_20260703_ko.md`에
기록한다.

## 현재 방식에서 잘못된 부분

| 항목 | 기존 방식 | 문제 |
|---|---|---|
| 측정 시간 | reference mode의 `ITER`를 control mode에 재사용 | mode별 elapsed가 크게 달라져 시간 에너지가 component 차분에 섞임 |
| 구분 | `*_load_only - empty`를 memory component로 사용 | load-only에 checksum, address/control, issue/stall이 포함됨 |
| denominator | `expected_*_bytes` 사용 | logical byte일 뿐 actual L1/L2/DRAM traffic이 아님 |
| 회귀 | paired difference 중심 | `elapsed_s`, FLOP, bytes의 동시 설명력이 반영되지 않음 |
| 검증 | SMID 중심 | cache hit/access/stall 검증이 없음 |

## 새 측정 구조

### Runner

새 runner는 `scripts/run_component_regression_sweep.py`다.

| 항목 | 설계 |
|---|---|
| calibration | 각 mode/좌표별로 binary 자체 calibration 사용. `--iters`를 넘기지 않는다. |
| measurement time | `--seconds` 기준으로 mode마다 비슷한 elapsed를 목표로 한다. final은 10 s 이상 권장. |
| 반복 | `--repeats`를 runner가 외부에서 반복하고 run order를 회전시킨다. |
| 독립 축 | `reuse_factor`, `load_repeat`, `store_repeat`, `active_SM`, `blocks/SM`, `W_SM`을 matrix로 생성한다. |
| matrix | valid/invalid row와 regime을 CSV에 남긴다. |

이 방식은 paired difference를 포기한다는 뜻이 아니다. pair는 sanity check로
남기되 최종 component coefficient는 regression 결과를 우선한다.

### 권장 측정 matrix

RTX 3090 smoke:

| 구분 | 값 | 단위 |
|---|---:|---|
| `seconds` | 3 | s |
| `repeats` | 2 | count |
| `blocks/SM` | 8, 16 | blocks/SM |
| `active_SM` | 82 | SM |
| shared/L2 `W_SM` | 64 | KiB |
| DRAM `W_SM` | 8192 | KiB |
| `reuse_factor` | 1, 4 | MMA/load |
| `load_repeat` | 1, 4 | load/tile |
| `store_repeat` | 1, 4 | store/tile |

Final:

| 구분 | 값 | 단위 |
|---|---:|---|
| `seconds` | 10 이상 | s |
| `repeats` | 5 이상 | count |
| `blocks/SM` | GPU별 valid set | blocks/SM |
| `active_SM` | full SM 우선, optional partial SM | SM |
| `reuse_factor` | 1, 2, 4, 8, 16 | MMA/load |
| `load_repeat` | 1, 2, 4, 8, 16 | load/tile |
| `store_repeat` | 1, 2, 4, 8, 16 | store/tile |

## 새 회귀 모델

새 analyzer는 `scripts/fit_component_energy_model.py`다.

기본 모델:

```text
net_E_J =
  intercept
  + beta_time * elapsed_s
  + beta_flop * FLOP
  + beta_reg_operand * expected_reg_operand_ops
  + beta_shared * expected_shared_bytes
  + beta_l2 * expected_l2_bytes
  + beta_dram * expected_dram_bytes
  + beta_store * expected_store_bytes
  + residual
```

출력 단위:

| 계수 | 출력 단위 |
|---|---|
| `beta_time` | W = J/s |
| `beta_flop` | pJ/FLOP |
| `beta_reg_operand` | pJ/reg-op-equivalent |
| `beta_shared`, `beta_l2`, `beta_dram`, `beta_store` | pJ/byte |

NCU actual byte가 있는 경우:

```text
expected_shared_bytes -> ncu_shared_bytes
expected_l2_bytes     -> ncu_l2_bytes
expected_dram_bytes   -> ncu_dram_bytes
```

NCU 기반 모델은 static 모델보다 우선한다. static 모델은 설계 점검과
smoke 용도다.

## 자동 경고 기준

| 경고 | 기준 | 의미 |
|---|---|---|
| `negative_coefficient` | memory/tensor/store coefficient < 0 | component 분해 실패 또는 collinearity |
| `large_elapsed_spread` | 같은 model group에서 elapsed max/min > 2 | time term 의존성이 큼 |
| `underdetermined` | row 수 <= feature 수 | 회귀 불가 |
| `high_condition_hint` | feature scale이 극단적으로 다름 | 계수 불안정 가능 |
| `high_residual` | relative RMSE가 큼 | 모델이 workload를 설명하지 못함 |
| `missing_ncu_actual_bytes` | actual counter 없음 | physical traffic 기준 해석 불가 |

## 기존 pair analyzer의 역할

`scripts/analyze_component_pairs.py`는 폐기하지 않는다. 대신 다음 진단을
추가한다.

| 추가 컬럼 | 의미 |
---|---|
| `numerator_elapsed_s` | numerator mode median elapsed |
| `baseline_elapsed_s` | baseline mode median elapsed |
| `elapsed_ratio` | 긴 elapsed / 짧은 elapsed |
| `valid_component_estimate` | elapsed mismatch/negative coefficient 등을 반영한 boolean |
| `diagnostic` | invalid 이유 |

최종 보고서에서는 `valid_component_estimate=false`인 pair를 component 값으로
쓰지 않는다.

## 실험 후 보고서에 반드시 포함할 표

| 표 | 필수 열 |
---|---|
| 측정 조건 | GPU, profile, SMs, L2/shared capacity, seconds (s), repeats, energy source |
| sweep matrix | mode, `W_SM` (KiB), `blocks/SM`, `reuse_factor`, `load_repeat`, `store_repeat` |
| timing QA | mode, elapsed median (s), min/max (s), rows |
| regression coefficient | feature, estimate, unit, sign, warning |
| residual QA | rows, features, RMSE (J), relative RMSE (%), R2 |
| NCU validation | L1 hit %, L2 hit %, L1/L2/DRAM access count, DRAM bytes, stall % |

## 구현 우선순위

1. `run_component_regression_sweep.py` 추가.
2. `fit_component_energy_model.py` 추가.
3. `analyze_component_pairs.py`에 elapsed/validity diagnostics 추가.
4. `README.md`와 GPU node guide에서 기존 component pair 결과를 final coefficient로 쓰지 말라고 수정.
5. NCU summary와 raw energy CSV를 join하는 옵션을 regression analyzer에 추가.
