# NCU 검증과 pJ 계산 보고서

작성일: 2026-07-07, updated 2026-07-14

## 핵심 요약

이 실험에서 Nsight Compute(NCU)는 component energy를 직접 측정하지 않는다. NCU의 역할은 다음 두 가지다.

| 역할 | 의미 |
|---|---|
| Path validation | 해당 kernel이 의도한 Tensor, shared, L1, L2, DRAM 경로를 실제로 사용했는지 확인한다. |
| Denominator validation | memory path의 pJ/byte 또는 pJ/bit 계산에 사용할 실제 traffic byte를 확인하거나 보정한다. |

에너지 분자 `J`는 NVML energy run에서 얻는다. NCU는 분자에 쓰지 않는다. 따라서 최종값은 다음처럼 표현해야 한다.

```text
NCU로 path와 denominator가 검증된 board-level effective microbenchmark coefficient
```

다음 표현은 피해야 한다.

```text
NCU가 측정한 L1 energy
순수 Tensor Core energy
순수 SRAM/HBM bitcell energy
```

## 전체 계산 흐름

```text
1. NVML energy run
   - NCU 없이 kernel 실행
   - mode별 net_E_J 측정

2. NCU sidecar run
   - 별도 실행에서 NCU counter 수집
   - hit rate, access count, bytes, stall, spill, Tensor instruction 확인

3. Path acceptance
   - 의도한 경로가 counter로 확인된 row만 accepted

4. Matched-control 계산
   - Tensor/Shared/Global L1/L2 CG/DRAM CG 모두 동일 ITER로 실행
   - treatment-control net energy를 직접 차감하며 duration-scaled power 보정은 사용하지 않음

5. pJ/FLOP, pJ/byte, pJ/bit 계산
   - Tensor는 logical FLOP denominator 사용
   - memory path는 NCU actual bytes denominator 우선 사용
```

## NCU로 검증한 항목

| Component/path | NCU에서 확인한 항목 | 채택 의도 |
|---|---|---|
| Tensor MMA incremental | Tensor/HMMA instruction, control total SASS instruction, spill/local memory, L1/L2/DRAM traffic | `reg_mma`가 Tensor instruction을 실행하고, control은 HMMA 없이 expected register work에 비례해 실행되어야 한다. |
| Shared scalar path | shared accesses, shared bytes, shared instruction count, bank conflict | shared memory scalar load path가 충분히 발생하고 bank conflict가 낮아야 한다. |
| Global L1-hit path | path-specific L1 hit rate, L1 accesses, L1 request/hit bytes, L2 read/DRAM bytes | global load가 L1 lookup hit 중심이어야 하며 L2/DRAM leakage가 낮아야 한다. |
| L2 CG hit path | path-specific L1 hit bytes, L2 source read hit/miss, architecture-specific fabric/remote lookup, native hit, DRAM read | `.cg` 요청은 L1TEX를 통과하되 L1 cache hit는 거의 없어야 한다. GA100/GH100은 첫 partition miss와 최종 L2 miss를 구분한다. |
| External-memory read path | DRAM read/write bytes, global-read expected bytes, L1/L2 final-service hit, DRAM read bandwidth | read 요청의 90% 이상이 external memory에서 서비스되고 write 오염이 1% 이하인지 검증한다. |
| 공통 | long/short scoreboard stall, wait stall, SMID histogram, spill/local | stall 또는 placement 문제를 보고서에 같이 기록한다. |

구현 기준은 hit rate만으로 통과시키지 않는 것이다. `ncu_cache_validation_summary.csv`와
`analyze_ncu_path_acceptance.py` 결과에는 `l1_accesses`, `l2_accesses`,
`dram_accesses`, `l1_request_bytes`, `l1_hit_bytes`, `l2_read_bytes`,
`l2_read_hit_sectors`, `l2_read_miss_sectors`, `l2_native_read_hit_rate_pct`,
`l2_read_sector_conservation_ratio`, `l2_read_miss_bytes`, `dram_read_bytes`,
`dram_bytes`, `dram_read_bytes`, `dram_write_bytes`,
`dram_read_to_expected_ratio`, `dram_write_to_read_ratio`,
`dram_read_bandwidth_GBps`, `expected_l2_read_bytes`,
`l2_read_to_expected_ratio`가 함께 있어야 한다.
GA100/GH100 row에는 추가로 `l2_fabric_read/hit/miss_sectors`,
`l2_fabric_read_sector_conservation_ratio`, `l2_logical_read_hit_rate_pct`,
`l2_fabric_model_native_hit_rate_pct`, `l2_native_vs_fabric_model_hit_delta_pct`가
필수다.
L1 access는 NCU가 request counter를 제공하면 request를 쓰고, 없으면 sector로
fallback한다. L2/DRAM access는 sector counter다. byte counter가 없으면 sector를
32 bytes로 환산하지만, 보고서에는 이 값이 NCU-derived effective denominator임을
명시한다.

NCU CSV의 `gpu__time_duration.sum` 단위는 버전에 따라 `ns`, `us`, `ms`, `s` 또는
긴 이름(`nsecond`, `usecond`, `msecond`, `second`)으로 기록된다. Summarizer는 이
표기를 모두 초로 변환한 뒤 bandwidth를 계산한다. 시간 단위 변환 오류는 pJ/bit의
energy/byte 분자·분모에는 직접 영향을 주지 않지만, 보고된 GB/s를 1,000배 이상
왜곡할 수 있으므로 `gpu_duration_s`와 bandwidth sanity를 함께 확인한다.

`lts__t_sector_op_read_hit_rate` native ratio는 확인한 GA100/GA102/GH100 NCU catalog에는
있지만 GV100 catalog에는 없다. GA100 native ratio는 source와 LTC-fabric lookup을 함께
센 모집단일 수 있으므로 95%를 요구하지 않는다. 대신 source+fabric counter로 native
값을 재구성하고 절대 오차 <=2 percentage points를 요구한다. GH100도 같은
source+fabric final-service gate를 적용하며 필수 fabric metric이 없으면 reject한다.
RTX 3090은 검토한 direct/native 교차 gate를 유지한다. V100에서는 unavailable
metric을 95% 통과로 간주하지 않으며 path-specific hit/miss, sector 보존, expected bytes와
DRAM traffic으로 판정한다.

현재 NCU sidecar는 기본적으로 `application replay + cache-control none`을 사용한다.
metric pass마다 application setup과 kernel 전 warm-up을 다시 실행하기 위한 선택이다.
summary에는 `ncu_replay_mode`, `ncu_cache_control`, `global_warmup_passes`,
`ncu_metric_profile`, `l2_residency_policy`, `l2_address_layout`을 남긴다. A100/V100/H100 새 finalplan은 긴 energy
sweep 전에 L2 후보를 먼저 profiling한다. A100/H100은 normal/persisting, V100은 CC 7.0에서
지원되는 normal만 사용하며, 두 working-set anchor에서 strict gate를 통과한
policy/layout/blocks-SM을 최소 L2 NCU와 energy에 동일하게 전달한다. 이 필드들과
selected blocks/SM이 energy 구성과 정확히 일치하지 않으면 reject한다. persisting policy가 선택되면 그 값은
일반 L2가 아니라 residency-managed L2 effective path coefficient다.

L2 hit gate에는 `l2_path_minimal` metric profile만 사용한다. 전체 metric bundle은
application replay pass 수를 늘리고, 서로 다른 pass의 counter를 합쳤을 때
`hit+miss != read`가 되는 사례가 확인되었기 때문이다. 최소 profile은 L1 global-load
hit/miss, device/all-TEX/native L2 read, DRAM traffic, local spill, long scoreboard만 모은다.
GA100/GH100 bundle은 여기에 `srcunit_ltcfabric` read/hit/miss를 같은 replay로 추가한다.
source와 fabric counter coherence를 모두 필수로 한다. 비-L2 component는 별도 `full` profile로
수집한 뒤 `merge_ncu_validation_summaries.py`가 row source를 보존해 canonical summary를
만든다. 서로 다른 profile의 metric을 하나의 row로 합산하지 않는다.

## Path acceptance 기준

현재 `scripts/analyze_ncu_path_acceptance.py`는 mode별로 다음 기준을 적용한다.

| Path | accepted 조건 요약 |
|---|---|
| Tensor | `reg_mma`에서 Tensor/HMMA instruction > 0, spill/local 0, memory traffic이 threshold 이하 |
| Tensor control | `reg_operand_only`에서 Tensor/HMMA instruction = 0, spill/local 0 |
| Shared scalar | shared bytes/accesses > 0, shared instruction 존재, bank conflict ratio 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 | path-specific L1 hit >=95%, L1 request/hit bytes 존재, L2 read/L1 request <=1%, DRAM/L1 request <=1% |
| L2 CG | `ncu_metric_profile=l2_path_minimal`. GA100/GH100은 `(source hit + fabric hit)/source read >=95%`, source/fabric sector 보존 0.98-1.02, coherent routing, native-fabric-model 오차 <=2 pp를 요구한다. RTX 3090은 검토된 direct/native 정책을 사용한다. 공통으로 observed/expected source L2 bytes=0.95-1.05, L1 path hit <=1%, L1 hit/request bytes <=1%, DRAM-read/source-L2-read <=2%가 필요하다. GV100은 native metric만 생략 가능하며 aggregate/full-bundle hit rate는 진단값이다. |
| External-memory read path | L1 hit <=1%, final-service L2 hit <=10%(A100/H100은 source+fabric logical hit), source/expected bytes 0.95-1.05, external read/expected 0.85-1.05, external read/source read >=0.90, write/read <=0.01, direct read/write byte-counter provenance |

L2 CG mode은 measurement 전 warm-up도 `ld.global.cg.u32`를 쓰는
`global_cg_warmup_kernel`로 수행한다. 일반 cached load warm-up이 L1을 채운 뒤
L2 target을 시작하는 혼입을 막기 위한 조치다. 그러나 `.cg` 요청이 L1TEX를
통과하는 것은 정상이므로 L1 request byte 자체는 reject 조건이 아니다.

이 기준을 통과하지 못한 row는 pJ 값이 양수여도 최종 component coefficient로 채택하지 않는다.

## Memory path pJ/byte와 pJ/bit 계산

Memory path는 다음 pair를 사용한다.

| Component/path | treatment | control | denominator |
|---|---|---|---|
| Shared scalar | `shared_scalar_load_only` | `shared_scalar_addr_only` | NCU shared read bytes |
| Global L1-hit | `global_l1_load_only` | `global_addr_only` | NCU L1 request bytes |
| L2 CG hit | `l2_cg_load_only` | `global_addr_only` | NCU L2 read bytes |
| External-memory read path | `dram_cg_load_only` | `global_addr_only` | NCU `dram__bytes_read.sum` only |

`dram_cg_load_only`는 호환성을 위해 유지한 mode 이름이다. 결과 component는
`external_memory_read_path`로 표기한다. 이 값은 SM issue/stall, L1/L2 miss,
interconnect, controller/PHY, HBM/GDDR 및 GPU-device power-delivery overhead를 포함한
effective coefficient이며 순수 memory-device energy가 아니다. 세부 설계는
[external_memory_read_path_experiment_design_ko.md](external_memory_read_path_experiment_design_ko.md)를 따른다.

GA100의 L2 denominator는 원래 TEX/device source read sectors에서 환산한 logical source
bytes다. `source + LTC-fabric` bytes를 더하지 않는다. fabric lookup은 같은 logical
payload의 원격 재조회이므로 분모에 더하면 요청 데이터를 이중 계수한다. 대신 fabric
read sectors/fraction을 별도 보고하고, pJ/bit는 L2 lookup과 partition fabric을 포함한
effective path coefficient라고 명시한다.

모든 final memory pair는 treatment/control별 calibration candidate 중 큰 ITER를 양쪽에
동일하게 적용한다. 실행시간은 달라도 loop work count는 같으며, 두 net energy를 직접 뺀다.

```text
ITER_treatment = ITER_control = N
delta_E_J = net_E_treatment(N) - net_E_control(N)
```

과거 Shared/L1 duration-scaled power subtraction은 memory stall이 scheduler/clock power를
바꾸는 효과를 독립적인 control power로 잘못 가정해 음수·불안정 계수를 만들었다. 현행
strict 분석에서는 duration-scaled row와 `iter_ratio != 1`을 reject한다.

```text
ITER_treatment = ITER_control = N
delta_E_J = net_E_treatment_J(N) - net_E_control_J(N)
```

특히 L2 CG는 각 W_SM/blocks-per-SM/load-repeat 좌표에서 treatment 목표시간 ITER와
control 최소시간 ITER를 각각 calibration한 뒤, 더 큰 ITER를 두 mode에 공통 적용한다.
`*_l2_pair_calibration.csv`, raw CSV의 동일 `ITER`, matched detail의
`pair_energy_basis=matched_iters_net_energy`와 `iter_ratio=1`이 모두 일치해야 한다.
NCU hit rate가 통과해도 ITER가 다르면 path만 검증된 것이며 energy coefficient는 reject한다.

그 다음 coefficient를 계산한다.

```text
pJ/byte = delta_E_J * 1e12 / denominator_bytes
pJ/bit  = pJ/byte / 8
```

초기 expected byte는 코드에서 다음처럼 계산된다.

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
| `ncu_actual_same_working_set` | mode, W_SM, blocks/SM, active_SM은 같고 factor는 대표 NCU scale 사용 | 기존 RTX 3090 strict 결과의 한계. 새 final run에서는 피하는 것이 원칙 |
| `expected_no_ncu_match` | NCU actual denominator 없음 | 최종 pJ/byte 채택 금지 |

새 플랫폼의 최종 실행에서는 `run_ncu_validation.sh`에 factor list를 넘겨
energy sweep과 같은 좌표를 NCU sidecar에서도 수집한다.

```bash
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=4,8,16 \
DRAM_LOAD_REPEATS=4,8,16 \
bash scripts/run_ncu_validation.sh
```

이렇게 실행하면 `ncu_validation_cases.csv`에 reuse/load_repeat별 row가 생성되고,
matched-control 분석은 가능한 경우 `ncu_actual_exact` denominator를 사용한다.
또한 acceptance CSV가 reuse/load_repeat별 row를 포함하면, 분석기는 같은 좌표에서
accepted된 treatment row만 최종 후보로 사용한다.
이때 Tensor/register 계열은 `reuse_factor`를, memory 계열은 `load_repeat`를
핵심 factor로 비교한다. memory mode의 `reuse_factor`처럼 kernel 동작에 직접
쓰이지 않는 manifest 값은 exact acceptance 판단에서 핵심 축으로 보지 않는다.
대표 조건만 빠르게 확인하려면 세 list를 모두 `4`로 제한할 수 있지만, 그 결과는
preflight/provisional로 보고한다.

## Power/Energy API gate

NCU는 energy numerator를 제공하지 않는다. Energy numerator는 NVML 측정값에서 온다. GPU 세대별 power API 의미가 다르므로, matched-control 분석에는 [power_measurement_api_matrix_ko.md](../platforms/power_measurement_api_matrix_ko.md)의 기준을 적용한다.

최종 coefficient용 분석 명령은 다음 gate를 사용한다.

```bash
python3 scripts/analyze_matched_control_energy.py ... \
  --require-ncu-denominator \
  --require-total-energy \
  --expected-power-semantics one_sec_average \
  --pairing nearest-control \
  --tensor-pair-policy matched-iters \
  --min-delta-j 10 \
  --min-delta-fraction 0.005
```

`--expected-power-semantics` 값은 platform profile에 맞춘다.

| GPU | expected value |
|---|---|
| RTX 3090 / GA102 | `one_sec_average` |
| V100 / GV100 | `instant` |
| A100 / GA100 | `instant` |
| H100 / GH100 | `one_sec_average` |

NCU path acceptance에서 Tensor/register memory leakage는 두 단계로 본다.

| 항목 | 기본 gate | ratio gate | 이유 |
|---|---|---|---|
| Tensor treatment | `--tensor-memory-bytes-max` | `--tensor-memory-bytes-per-hmma-max` | reuse가 커지면 setup/cache traffic absolute byte도 커질 수 있으므로 HMMA당 leakage를 함께 확인 |
| Register/control | `--register-memory-bytes-max` | `--register-memory-bytes-per-op-max` | no-MMA control의 traffic을 operation count 대비로 보정 |

RTX 3090 factor sidecar 재분석에서는 ratio max를 `1.0 B/op` 수준으로 두어
RF=16처럼 absolute byte만으로는 커 보이지만 operation 대비 leakage가 작은 row를
부당하게 제외하지 않도록 했다.

분석에서 확인하는 CSV metadata:

| CSV column | 통과 기준 | 이유 |
|---|---|---|
| `nvml_total_energy_supported` | `true` | total energy mJ counter 사용 가능 |
| `energy_source` | `nvml_total_energy` | endpoint power fallback 배제 |
| `energy_integration_method` | `total_energy_mj_delta` | 실행 전후 누적 energy 차분 |
| `nvml_power_usage_semantics` | profile과 일치 | fallback power API 의미를 보고서에 명시 |
| `measurement_scope` | `gpu_device_total_energy_counter` | module power, GPU memory power, fallback power scope와 혼동 방지 |

반복 energy run이 있는 경우에는 `nearest-control` pairing을 권장한다. 각 treatment row를
실행 순서상 가장 가까운 control row와 비교하므로, 시간에 따른 온도/클럭 drift가 mode별
median 선택에 섞이는 문제를 줄일 수 있다. 또한 `delta_E`가 너무 작으면 양수 coefficient라도
noise floor 안에 있을 수 있으므로, `--min-delta-j`와 `--min-delta-fraction`으로 최종
summary에서 제외한다.

`energy_source=legacy_get_power_usage_integral` row는 최종 component coefficient에서 제외하거나 provisional로만 보고한다. 특히 RTX 3090/H100처럼 `GetPowerUsage`가 1초 평균인 profile에서는 짧은 kernel의 endpoint power trapezoid가 kernel 구간과 맞지 않을 수 있다.
H100/HGX에서 노출될 수 있는 module power와 GPU memory power도 최종 분자가 아니다.
module power는 GPU 외 구성요소를 포함할 수 있고, GPU memory power는 memory subsystem
telemetry일 뿐 NCU L1/L2/DRAM traffic denominator와 같은 scope가 아니다.

## Tensor pJ/FLOP 계산

Tensor는 memory path처럼 pJ/byte가 아니라 pJ/FLOP로 계산한다. 사용 pair는 다음이다.

| 항목 | mode | 의미 |
|---|---|---|
| treatment | `reg_mma` | register fragment를 준비하고 `mma_sync`를 반복 실행 |
| control | `reg_operand_only` | source상 같은 fragment/phase/epilogue를 선언하지만 `mma_sync`는 실행하지 않는 lightweight control |

Tensor finalplan은 각 RF에서 treatment 목표시간의 `reg_mma` ITER와 control 최소시간의
`reg_operand_only` ITER를 각각 구하고, 둘 중 큰 값을 두 mode에 동일 적용한다. 서로 다른
ITER를 각 mode에 적용한 뒤 elapsed time으로 보정하는 이전 방식은 A100 RF4
이상에서 work mismatch와 음수 delta를 만들 수 있어 final 경로에서 제외했다.
`reg_operand_only`의 기존 RF 비례 FP32 FMA/checksum/memory는 제거했다. v5는
A/B/C fragment, A fragment in-place sign flip, dependent scalar update, C epilogue를
source상 공통으로 두고 treatment만 MMA를 발행한다. A 부호를 매 logical MMA마다 교대해 FP32 accumulator가
bounded 상태를 유지한다. Scalar sink는 공통 output에 기록해 ptxas가 no-MMA control
반복문을 제거하지 못하게 한다. 다만 ptxas가 control fragment를 줄여 treatment/control의 실제
registers/thread는 다르므로 차분값은 pure Tensor 회로 에너지가 아니다.

```text
ITER_reg_mma = ITER_reg_operand_only
delta_E_J = net_E_reg_mma_J - net_E_reg_operand_only_J
```

Matched detail에서 `pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`을 확인하고,
`*_tensor_pair_calibration.csv`의 resolved ITER가 두 raw mode의 ITER와 같은지도 package
audit으로 검증한다.
같은 ITER의 no-MMA control은 더 짧게 실행되므로 calibration 단계에서 별도 duration
floor를 둔다. 표준 10 s package는 1 s floor와 0.8 s analyzer gate, A100 targeted 20 s
package는 2 s floor와 1.6 s gate를 사용한다. Gate 미만 또는 non-positive control net
energy는 식별 불충분으로 reject한다.

여기서 direct energy 차분은 pure Tensor 회로 energy가 아니다. 동일 ITER라도 treatment와
control의 elapsed time은 다르며, 더 긴 treatment의 active scheduler/clock/register lifetime
비용이 `delta_E_J`에 포함된다. 따라서 플랫폼 비교 시 coefficient와 함께 treatment
TFLOP/s, treatment/control elapsed time, 두 mode의 net power를 보고해야 한다. duration을
강제로 맞춘 control-power scaling도 work equivalence를 깨므로 이 문제를 제거하지 못한다.

FLOP denominator는 logical MMA 정의에서 나온다.

```text
N_MMA = active_SM * blocks_per_SM * ITER * reuse_factor
FLOP  = N_MMA * 8192
```

`8192 FLOP`는 FP16 WMMA `m16n16k16` 한 번을 logical GEMM 기준으로 본 값이다.

```text
16 * 16 * 16 multiply-add = 4096 FMA = 8192 FLOP
```

최종 Tensor coefficient는 다음과 같다.

```text
pJ/FLOP = delta_E_J * 1e12 / FLOP
```

과거 protocol 예시 row:

| 항목 | 값 |
|---|---:|
| pair | `reg_mma_minus_reg_operand_only` |
| delta_E_J | 53.2879 J |
| denominator | 3.63176e14 FLOP |
| coefficient | 0.146727 pJ/FLOP |

계산:

```text
53.2879 * 1e12 / 3.63176e14 = 0.1467 pJ/FLOP
```

이 `0.1467 pJ/FLOP`와 broad/targeted duration-scaling에서 얻은
`0.077-0.170 pJ/FLOP` 범위는 current v6 protocol 이전의 historical
method-sensitivity 자료다. v1 dynamic loop는 GA102 RF2에서 `HMMA/logical MMA=3`,
다른 primary RF에서 2를 보여 logical FLOP과 issued HMMA의 비례가 깨졌다. 따라서
이 과거 값을 현행 Tensor coefficient로 인용하거나 다른 revision과 평균하지 않는다.

2026-07-13 RTX 3090 fixed-RF v2 재실행 결과는 다음과 같은 **역사적 결과**다.

| 항목 | 역사적 v2 결과 |
|---|---:|
| RF sweep | 1, 2, 4, 8, 16 |
| treatment/control NCU acceptance | 10/10 |
| treatment `HMMA/logical MMA` | 모든 RF에서 2.0 |
| control HMMA | 모든 RF에서 0 |
| local read/write | 모든 row에서 0 B / 0 B |
| valid energy pair | 33/35 |
| coefficient median | 2.252501 pJ/FLOP |
| coefficient min-max | 1.945385-2.369221 pJ/FLOP |

v2는 당시 동일 ITER와 NCU instruction gate를 통과했지만, positive-only FP32
accumulator가 장시간 반복에서 더 이상 수치적으로 갱신되지 않을 수 있어 superseded됐다.
v3의 A+/A- branch도 RF2 이상에서 두 HMMA 경로가 predication으로 함께 발행돼 reject됐다.
v4는 단일 A fragment의 FP16 sign bit를 뒤집었지만 scalar sink가 empty asm에만 연결되어
RTX 3090 ptxas가 `reg_operand_only` 반복문 전체를 제거했다. HMMA=0과 spill=0만 보던
기존 gate는 launch-only control을 검출하지 못했다. v5 output sink는 GA102에서
통과했지만 A100에서는 10억 ITER control이 약 1 ms에 종료되어 충분하지
않았다. 현행 v6는 treatment/control inner loop에 공통 `SR_CLOCKLO` token을
넣고, static token-loop, calibration trial `>=0.05 s`, ITER stretch `<=6`, runtime
`SASS instructions/expected register op >= 0.1`을 요구한다. v4와 실패한 A100 v5
Tensor energy/NCU acceptance는 현행 계수로 사용할 수 없다.

## Tensor에서 NCU의 역할

Tensor pJ/FLOP의 분모는 NCU byte가 아니라 logical FLOP다. 따라서 Tensor에서 NCU는 denominator를 만드는 도구가 아니라, 다음 조건을 검증하는 도구다.

| 확인 | 이유 |
|---|---|
| `reg_mma`에서 Tensor/HMMA instruction > 0 | 실제 WMMA가 architecture별 HMMA path로 실행됐는지 확인 |
| `reg_operand_only`에서 Tensor/HMMA instruction = 0 | control이 no-MMA control인지 확인 |
| treatment/control runtime-token backward loop > 0 | ptxas 후에도 `SR_CLOCKLO` dependency가 실제 work loop 내에 남았는지 확인 |
| control SASS instruction / expected register op >= 0.1 | loop가 runtime work에 비례해 실행되는지 확인 |
| treatment/control registers/thread | register footprint 불일치를 숨기지 않고 coefficient 범위를 규정 |
| spill/local memory = 0 | register spill로 L2/DRAM traffic이 섞이는 것을 방지 |
| L1/L2/DRAM traffic이 작음 | Tensor coefficient가 memory traffic에 오염되지 않았는지 확인 |

RF sweep에서는 각 row의 HMMA 존재만으로 부족하다. `expected_logical_mma = active_SM x
blocks/SM x ITER x RF`를 계산하고 `HMMA/logical MMA` 비율이 RF1/2/4/8/16에서 일정한지
확인한다. GA102의 기존 runtime loop와 v3 dual-branch codegen은 strict 선형성을
깨뜨렸다. 현재 RF1/2/4/8/16은 모두 fixed-trip v6 kernel이며, 절대 비율을 GPU 간
같게 강제하지 않고 각 target GPU 내부의 상대 spread 10% 이하를 요구한다. H100에서도
현재 실험은 WGMMA/TMA가 아니라 FP16 WMMA가 lowering된 HMMA compatibility path다.

따라서 Tensor 결과는 다음처럼 써야 한다.

```text
reg_operand_only 대비 reg_mma의 effective WMMA/HMMA + register/scheduler-path incremental cost
```

다음처럼 쓰면 안 된다.

```text
순수 Tensor Core transistor-level energy
```

2026-07-14 RTX 3090 v5 full package는 75/75 matched pair와 30/30 Tensor
treatment/control NCU row를 통과해 **2.140 pJ/FLOP**(95% bootstrap median CI
2.114-2.170)을 얻었다. 이 값은 GA102 v5 protocol-specific historical
accepted coefficient이며, v6 교차 플랫폼 결과나 2026-07-08/13 수치와
평균하지 않는다.

## 2026-07-08 RTX 3090 historical finalplan 예시

아래 표는 2026-07-08 protocol의 matched-control 요약이며 현행 component table이
아니다. 위 2026-07-13 fixed-RF v2 표와 v4 dead-control 결과도 historical
evidence다. RTX 3090 v5 결과는
`docs/results/gpu_power_modeling_experiment_results_ko.md`의 2026-07-14 표로 보존하되,
새 v6 계수로 표기하지 않는다.

| Component/path | median | unit | median pJ/bit | 해석 |
|---|---:|---|---:|---|
| Tensor MMA incremental, RF=8/16 targeted + fixed-ITER/RF8/RF16 duration auxiliary | RF16 0.077, RF8 0.143 | pJ/FLOP | - | no-MMA register/control 대비 WMMA 추가분의 RF-dependent effective range |
| Shared scalar path | 1.219 | pJ/byte | 0.152 | NCU shared bytes 기준 effective path coefficient. 20초/10회 targeted rerun primary |
| Shared scalar LR16 paired 60초 auxiliary | 0.615 | pJ/byte | 0.077 | LR16 lower-side follow-up. 5/6 valid, accepted_low_stability라 primary 대체 아님 |
| Shared scalar LR4/LR8/LR16 interleaved 30초 auxiliary | 1.160 | pJ/byte | 0.145 | 한 run 안에서 LR=4/8/16을 순환시킨 C-T-C 보조실험. aggregate는 primary와 정합하지만 LR4 0.199, LR8 0.145, LR16 0.0618 pJ/bit로 factor sensitivity가 남음 |
| Shared scalar LR4/LR8/LR16 fixed-ITER auxiliary | 1.123 | pJ/byte | 0.140 | treatment ITER=17,000,000 고정. shared bytes가 1x/2x/4x로 벌어진 상태에서도 aggregate는 primary와 정합하지만 LR16 weak row 1개가 남음 |
| Shared scalar LR16 fixed-ITER focus auxiliary | 0.936 | pJ/byte | 0.117 | LR16만 6 cycles 반복. 6/6 valid, power-state 18/18 ok라 prior weak row는 지속적이지 않음 |
| Shared scalar LR4/LR8 fixed-ITER focus auxiliary | 1.190 | pJ/byte | 0.149 | LR4/LR8만 5 cycles 반복. 10/10 valid, power-state 30/30 ok, LR4 0.179/LR8 0.142 pJ/bit로 primary 0.152를 직접 지지 |
| Global L1-hit path | 1.188 | pJ/byte | 0.148 | NCU L1 bytes 기준 effective path coefficient. C-T-C paired 30초 combined primary |
| L2 CG hit path | 8.132 | pJ/byte | 1.017 | NCU L2 bytes 기준 effective path coefficient. C-T-C paired LR4/LR8 30초 combined primary |
| RTX 3090 external-memory read path | 204.080 | pJ/byte 산술 환산 | 25.510 | 사용자 전달 historical observation; 현행 24.949 pJ/bit 결과로 superseded |
| A100 external-memory read path | 95.400 | pJ/byte 산술 환산 | 11.925 | 사용자 전달 historical observation; 원본 package 미확보 |
| V100 external-memory read path | 65.048 | pJ/byte 산술 환산 | 8.131 | 사용자 전달 historical observation; 원본 package 미확보 |

이 표는 순수 회로 에너지 표가 아니다. GPU/device-level energy, control 차분, NCU
denominator가 결합된 과거 microbenchmark coefficient 표다. RTX 3090 external-memory
historical row는 새 high-entropy input, 동일 ITER `global_addr_only` pair, exact NCU
`dram__bytes_read.sum`을 사용한 24.949 pJ/bit current effective-path 결과로 대체됐다.
A100/V100 행은 여전히 원본 current package가 없는 historical observation이다.

## A100/V100/H100 적용 시 주의

NCU denominator scale과 path acceptance는 GPU마다 다시 생성해야 한다. RTX 3090의 NCU scale이나 accepted row를 A100, V100, H100에 그대로 적용하면 안 된다.

| GPU | 반드시 다시 확인할 항목 |
|---|---|
| A100 | `sm_80`, `target_profile=a100`, `NCU_CHIP=ga100`, runtime active SM, L2 40 MiB, shared allocation 164 KiB/SM |
| V100 | `sm_70`, `target_profile=v100`, energy B=4,16,32, strict NCU Shared/L1/L2 W32/B32, `NCU_CHIP=gv100`, 2024.3 또는 실제 metric query가 성공한 toolchain |
| H100 | `sm_90`, `target_profile=h100`, `NCU_CHIP=gh100`, WMMA compatibility path와 Hopper-native WGMMA/TMA path 구분 |

A100에서 결과가 좋지 않으면 먼저 다음을 확인한다.

```text
active_SM=82
target_profile=rtx3090
chip=ga102
cuda_arch=86
L2=6 MiB
max blocks/SM=16
```

이 값이 A100 run 또는 analysis filter에 섞인 row는 최종 보고에서 reject해야 한다.

## 결론

NCU 검증은 “에너지를 직접 측정하는 단계”가 아니라 “path와 denominator를 검증하는 단계”다. 최종 pJ 값은 NVML energy 차분과 NCU traffic 검증을 결합한 값이다.

가장 안전한 한 문장 요약은 다음이다.

```text
본 실험의 pJ/FLOP, pJ/byte, pJ/bit 값은 NVML board-level energy를 matched-control로 차분하고, NCU로 경로와 traffic denominator를 검증한 effective microbenchmark coefficient다.
```
