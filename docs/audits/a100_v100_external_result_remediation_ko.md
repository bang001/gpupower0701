# A100/V100 외부 결과 원인 분석 및 재실행 조치

작성일: 2026-07-14

## 1. 전달받은 결과의 현재 판정

아래 값은 사용자가 전달한 외부 노드 요약을 그대로 기록한 것이다. 원본 raw/NCU CSV를
이 저장소에서 아직 읽지 못했으므로 수치를 재계산한 결과가 아니다.

| GPU | component | 전달값 | pipeline status | 현재 보고 가능 여부 |
|---|---|---:|---|---|
| A100 | Tensor MMA increment | 0.625 pJ/FLOP | `accepted_with_caution` | provisional effective coefficient; raw/NCU package 확인 필요 |
| A100 | Global L1 hit path | 0.327 pJ/bit | `accepted_low_stability` | 안정성 후속 측정 전 final 금지 |
| A100 | Shared scalar path | - | 유일 후보가 legacy `pair_start_distance_ms>30000` | 새 timing 규칙으로 재분석 전 결론 금지 |
| A100 | L2 CG hit path | - | 20/20 NCU reject, L2 hit 58-72% | coefficient 없음 |
| A100 | External-memory read path | 11.925 pJ/bit | legacy `accepted_low_stability` | historical effective-path observation; strict 재실험 필요 |
| V100 | Tensor MMA increment | 1.034 pJ/FLOP | `accepted_with_caution` | provisional effective coefficient; raw/NCU package 확인 필요 |
| V100 | Global L1 hit path | 0.672 pJ/bit | `accepted_low_stability` | 안정성 후속 측정 전 final 금지 |
| V100 | Shared scalar path | 1.124 pJ/bit | 유일 후보가 legacy `pair_start_distance_ms>30000` | 값은 탈락 row의 진단값이며 coefficient로 인용 금지 |
| V100 | L2 CG hit path | 2.272 pJ/bit | 20/20 NCU reject, L2 hit 58-72% | 값은 경로 미검증 row이며 인용 금지 |
| V100 | External-memory read path | 8.131 pJ/bit | legacy `accepted_low_stability` | historical effective-path observation; strict 재실험 필요 |

`accepted_low_stability`는 “물리적으로 확정”이 아니라 power/NCU 기본 gate를 통과한
row의 분포가 불안정하다는 뜻이다. 이 실험값은 순수 SRAM/Tensor/HBM 회로 에너지가
아니라 board-level 차분과 NCU traffic denominator로 얻은 workload-dependent effective
coefficient다.

External-memory 값은 strict NCU `dram__bytes_read.sum`, high-entropy input,
architecture별 L2 배수 W sweep을 적용하지 않은 기존 protocol 결과다. 따라서 물리
HBM2 pJ/bit와 직접 비교하지 않으며 최신 재실행은
[external-memory 설계](../methodology/external_memory_read_path_experiment_design_ko.md)를 따른다.

## 2. 확인된 원인

### 2.1 Pair 시간 gate의 의미 오류

기존 analyzer의 `pair_start_distance_ms`는 이름과 달리 두 benchmark의 시작 간격이
아니었다. C++ binary는 kernel 완료 뒤 `run_id`를 만들고, 각 control/treatment를 별도
프로세스로 실행하면서 각각 idle baseline도 측정한다. 따라서 기존 값은 대략 다음과 같다.

```text
legacy distance = abs(treatment completion - control completion)
```

인접한 `control -> treatment` pair여도 두 번째 프로세스의 idle baseline, setup, kernel
시간이 모두 포함되어 30초를 넘을 수 있다. 이것은 thermal adjacency 실패의 증거가
아니며 gate 정의 오류다.

수정 후에는 raw CSV가 timed kernel 직전의 epoch와 monotonic elapsed 기반 종료값인
`measurement_start_epoch_ms`/`measurement_end_epoch_ms`를 기록한다. analyzer는 두
간격 `pair_transition_gap_ms`만 한계와 비교한다. 이전 CSV는
다음 fallback으로 재분석한다.

```text
legacy inferred start = run_id completion timestamp - elapsed_s
transition gap = later inferred start - earlier inferred end
```

fallback 사용 여부는 `pair_timing_source=legacy_run_id_elapsed_inferred`로 남는다. 따라서
A100/V100 Shared raw를 즉시 폐기할 필요는 없다. 새 분석에서 transition gap, NCU
acceptance, power-state, delta signal, 반복 안정성을 모두 통과하면 **진단 후보**를 복구할
수 있다. 다만 inferred timing은 실제 kernel interval의 직접 증거가 아니므로 현행 strict
platform package에서는 final accepted로 승격하지 않는다. 완전한 accepted 등급에는 새
binary로 exact epoch interval을 기록한 재실행이 필요하다.

새 finalplan의 실제 한계는
`max(30000, (seconds+15)x1000)` ms이다. 표준 10초 run은 30,000 ms,
20초 stability run은 35,000 ms를 쓴다. 이는 각 별도 process가 timed kernel 앞에
`seconds`만큼 idle baseline을 측정하는 현재 harness 구조를 반영한 것이다.
한계를 늘려서 통과시키는 우회가 되지 않도록 각 detail row에
`pair_transition_gap_limit_ms`를 남기고 package audit가 gap과 한계를 함께 검증한다.

### 2.2 L2는 A100 counter 모집단 오류와 V100 경로 검증을 분리해야 함

A100의 source direct 51-62%와 native 67-72.5%는 서로 다른 lookup 모집단이며,
둘 중 하나를 logical final hit로 간주할 수 없다. 동시에 두 값에 95%를 요구한 것도
GA100 partition-fabric 구조에는 잘못이었다. 기존 report에는 `srcunit_ltcfabric` evidence가
없으므로 전달된 A100 L2 pJ/bit는 여전히 미승인이다. V100은 기존 architecture-specific
direct path 기준을 별도로 유지한다.

기존 standard finalplan은 A100 remediation에 있던 topology/policy selector를 실제
표준 실행 앞단에 연결하지 않았다. normal/contiguous 고정 좌표로 긴 energy sweep을
먼저 수행한 뒤 NCU에서 전체 reject되는 구조였다. V100도 W32/B32 고정만 사용했다.

수정된 finalplan은 energy 전에 다음 순서로 NCU-only precheck를 수행한다.

| GPU | anchor W_SM | candidate 순서 | 금지 조건 |
|---|---:|---|---|
| A100 | 16, 128 KiB/SM | normal contiguous B16/B8/B4/B2/B1 -> normal sm_interleaved B16/B8/B4 -> persisting contiguous B16/B8/B4/B1 -> persisting sm_interleaved B8/B4 | logical final-service 95% gate 완화 금지 |
| V100 | 32, 64 KiB/SM | normal contiguous B32 -> normal sm_interleaved B32/B16/B4 | persisting 사용 금지(CC 7.0) |

각 후보는 두 W anchor 모두에서 다음을 통과해야 한다.

| evidence | strict gate |
|---|---:|
| path-specific L1 hit | <=1% |
| A100 source direct hit | 보고값, 단독 threshold 없음 |
| A100 logical final hit | `(source hit + fabric hit)/source read >=95%` |
| A100 native-model 차이 | <=2 percentage points |
| A100 source/fabric `(hit+miss)/read` | 각각 0.98-1.02 |
| V100 derived L2 read hit | >=95%; native는 제공될 때만 교차검증 |
| observed/expected L2 bytes | 0.95-1.05 |
| DRAM read/L2 read | <=2% |
| treatment/control acceptance | 둘 다 accepted |

첫 통과 후보의 policy/layout/blocks-SM만 L2 energy와 `l2_path_minimal` NCU에 동일 전달한다. 후보가
없으면 L2 energy 전에 종료한다. 이는 실패가 아니라 “현재 microbenchmark로 해당
노드의 strict L2-hit coefficient를 식별하지 못했다”는 올바른 결과다.

V100에서 `lts__t_sector_op_read_hit_rate` native metric을 제공하지 않는
GV100/NCU 조합이 있다. 공통 selector가 이 값을 A100처럼 필수로 요구하면
derived hit가 99%여도 V100은 항상 탈락한다. 수정본은
`native_l2_gate=ga100_fabric_model`을 A100에 적용하고, V100은
`optional_unavailable` 또는 `optional_present_cross_checked`를 기록한다.
V100에서 native metric이 없음은 95% 통과로 위조하는 것이 아니라,
path-specific hit/miss-derived ratio, sector 보존, expected traffic, DRAM 비율로
대체 검증한다는 의미다.

## 3. 값이 상대적으로 높아진 이유를 지금 확정할 수 없는 이유

현재 숫자만으로는 회로 에너지가 증가했다고 결론 낼 수 없다. 최소한 다음 항목을 함께
봐야 한다.

| 확인 항목 | 높은 값이 만들어질 수 있는 경우 |
|---|---|
| `delta_E_J`, `delta_signal_fraction` | treatment-control 차이가 board energy의 0.5% 부근이면 작은 drift가 coefficient를 크게 변경 |
| NCU actual denominator | expected bytes보다 실제 bytes가 작거나 counter coordinate가 다르면 pJ/bit 과대평가 |
| elapsed/ITER | matched-ITER라도 treatment가 훨씬 오래 걸리면 scheduler/clock/active-time residual 포함 |
| clock, temperature, power state | pair 사이 clock/temperature 변화 또는 rejected nearest control 제거 후 먼 control 선택 |
| pair 실행 순서 | 모든 반복이 control 다음 treatment이면 warm-up/thermal drift가 treatment 증분으로 섞임 |
| coefficient 분포 | 단일 median만으로 outlier, IQR, CV, bootstrap CI를 알 수 없음 |
| path acceptance | Shared/L1/L2/DRAM traffic이 목표 경로와 다르면 다른 component 비용이 numerator에 혼입 |

A100 Tensor 0.625와 V100 Tensor 1.034 pJ/FLOP는 현재 RTX 3090 fixed-RF v2 값과 protocol,
clock, throughput이 모두 확인되기 전에는 “높다/낮다”로 직접 비교하지 않는다. Global
L1과 DRAM 값도 broad plausibility 안에 있을 수 있지만 `accepted_low_stability`를 final로
승격할 근거는 없다.

현행 runner는 이 순서 편향을 줄이기 위해 반복과 좌표 index를 함께 사용해 pair
방향을 counterbalance하고 matched detail에
`pair_execution_order`를 기록한다. Strict package는 각 핵심 component에서
`control_then_treatment`와 `treatment_then_control` valid row를 모두 요구한다. 이는 drift를
줄이고 검출하는 조치이지, 전달된 높은 수치가 순서 편향 때문이었다고 확정하는 것은 아니다.

## 4. 재분석 및 재실행

### 4.1 기존 raw에서 Shared 후보 복구

원본 artifact가 있는 노드에서 기존 analyzer command의 옵션만 다음처럼 바꿔 같은 tag를
별도 output 이름으로 재분석한다.

```bash
python3 scripts/analyze_matched_control_energy.py \
  results/raw/<profile>_component_finalplan_<tag>_{tensor,shared,l1,l2,dram}.csv \
  --acceptance-csv results/summary/<profile>_component_finalplan_<tag>_ncu_acceptance.csv \
  --ncu-summary-csv results/ncu/<profile>_component_finalplan_ncu_factor_<tag>/ncu_cache_validation_summary.csv \
  --power-state-audit-csv results/summary/<profile>_component_finalplan_<tag>_power_state_audit.csv \
  --exclude-power-state-rejects --require-ncu-denominator \
  --require-control-ncu-acceptance --require-total-energy \
  --pairing nearest-control --max-pair-transition-gap-ms 30000 \
  --tensor-pair-policy matched-iters --l2-pair-policy matched-iters \
  --dram-pair-policy matched-iters \
  --out-summary-csv results/summary/<profile>_component_finalplan_<tag>_timingfix_summary.csv \
  --out-detail-csv results/summary/<profile>_component_finalplan_<tag>_timingfix_detail.csv \
  --out-md results/summary/<profile>_component_finalplan_<tag>_timingfix.md
```

`{...}` 확장은 shell에서 다섯 경로로 확장된다. 실제 실행 때 `<profile>`, `<tag>`, power
semantics와 min-duration/delta 옵션은 원 command plan 값으로 유지한다. 새 detail에서
Shared row의 `valid_component_estimate`, `pair_transition_gap_ms`, `pair_timing_source`,
`diagnostic`을 먼저 본다.

### 4.2 새 binary/finalplan 실행

```bash
git pull
cmake --build build-a100 --clean-first -j   # A100
# V100은 CUDA 12.x의 nvcc와 build-v100 사용

python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 --tag $(date +%Y%m%d)
bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

V100은 `--target-profile v100`, `build-v100`, `active_SM=80`을 사용한다. 새 shell은 L2
precheck가 통과하기 전에는 긴 energy sweep을 시작하지 않는다.

`accepted_low_stability`인 Tensor/L1/DRAM 및 복구된 Shared 후보를 다시 확인할
때는 표준 계획의 측정 시간과 반복을 다음처럼 늘린 새 tag를 사용한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile <a100|v100> --seconds 20 --repeats 10 \
  --tag $(date +%Y%m%d)_stability20s
bash results/summary/<profile>_component_finalplan_$(date +%Y%m%d)_stability20s_commands.sh
```

이 재실행은 수치를 낮게 만들기 위한 것이 아니라, 양방향 pair order와 10회
반복에서 median, IQR, CV, bootstrap CI가 안정하는지 확인하기 위한 것이다.

## 5. 후보가 다시 실패할 때 필요한 artifact

아래 파일을 디렉터리 구조 그대로 전달해야 원인을 counter alias, replay/cache 상태,
address mapping, 실제 DRAM miss 중 어디로 좁힐 수 있다.

| 종류 | 필요한 파일 |
|---|---|
| L2 selector | `results/summary/<profile>_component_finalplan_<tag>_l2_path_selection.csv`와 `.md` |
| candidate acceptance | `results/summary/<profile>_component_finalplan_<tag>_l2_precheck_*_acceptance.csv` |
| candidate summary | `results/ncu/<profile>_component_finalplan_ncu_factor_<tag>/l2_precheck_*/ncu_cache_validation_summary.csv` |
| NCU raw | 같은 디렉터리의 `*_raw_metrics.csv`, `*_details.csv`, `*_ncu_stderr.log`, `ncu_validation_cases.csv` |
| metric catalog | `ncu_available_metrics_<chip>.txt`, `ncu_dropped_metrics_<chip>.txt` |
| pair 재분석 | 기존 다섯 raw energy CSV, power-state audit, NCU acceptance, timingfix detail/summary |

L2 row에서는 특히 다음 열이 필요하다.

`l1_path_hit_rate_pct`, `l1_request_bytes`, `l1_hit_bytes`,
`l2_path_hit_rate_pct`, `l2_native_read_hit_rate_pct`,
`l2_native_vs_derived_hit_delta_pct`, `native_l2_gate`, `l2_read_hit_sectors`,
`l2_read_miss_sectors`, `l2_read_sector_conservation_ratio`, `l2_read_bytes`,
`expected_l2_read_bytes`, `l2_read_to_expected_ratio`, `dram_read_bytes`,
`dram_read_to_l2_miss_bytes_ratio`, `global_warmup_passes`,
`l2_residency_policy`, `l2_address_layout`, `blocks_per_SM`, `W_SM_KiB`,
`load_repeat`, `ITER`.

이 artifact 없이 58-72%의 정확한 원인을 associativity/set mapping이라고 단정하지 않는다.
그 값은 실제 miss일 수도 있고, NCU metric alias/replay/traffic denominator 문제일 수도 있다.

## 6. 최종 판단

1. Pair 탈락의 한 원인은 코드상 확인되었고 수정되었다. 기존 Shared raw는 재분석 가치가 있다.
2. L2 전달값은 A100/V100 모두 현재 무효다. 95% gate를 낮추지 않는다.
3. standard finalplan에 architecture-aware L2 selector를 연결해 같은 실패를 L2 energy 측정 뒤에 발견하지 않도록 했다. 독립 non-L2 energy는 selector 전에 보존한다.
4. Tensor/L1/DRAM 전달값은 버리지 않되, caution/low-stability 등급 그대로 유지한다.
5. 새 selector도 실패하면 위 NCU artifact를 받아 metric과 실제 miss를 구분한 뒤 다음 kernel 설계를 결정한다.
