# NCU 검증과 pJ 계산 보고서

작성일: 2026-07-07, updated 2026-07-11

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
   - memory는 control energy rate를 treatment 시간으로 보정
   - Tensor는 동일 ITER로 실행한 treatment-control net energy를 직접 차감

5. pJ/FLOP, pJ/byte, pJ/bit 계산
   - Tensor는 logical FLOP denominator 사용
   - memory path는 NCU actual bytes denominator 우선 사용
```

## NCU로 검증한 항목

| Component/path | NCU에서 확인한 항목 | 채택 의도 |
|---|---|---|
| Tensor MMA incremental | Tensor/HMMA instruction, spill/local memory, L1/L2/DRAM traffic | `reg_mma`가 실제 Tensor instruction을 실행하고, control에는 Tensor instruction이 없어야 한다. |
| Shared scalar path | shared accesses, shared bytes, shared instruction count, bank conflict | shared memory scalar load path가 충분히 발생하고 bank conflict가 낮아야 한다. |
| Global L1-hit path | path-specific L1 hit rate, L1 accesses, L1 request/hit bytes, L2 read/DRAM bytes | global load가 L1 lookup hit 중심이어야 하며 L2/DRAM leakage가 낮아야 한다. |
| L2 CG hit path | path-specific L1 hit bytes, L2 read hit/miss sectors, L1 request/L2 read/DRAM bytes | `.cg` 요청은 L1TEX를 통과하되 L1 cache hit는 거의 없고 L2 read hit가 지배적이어야 한다. |
| DRAM CG streaming path | DRAM accesses, DRAM bytes, L1/L2 hit rate, L2 bytes 대비 DRAM bytes | DRAM streaming sanity check로만 사용한다. |
| 공통 | long/short scoreboard stall, wait stall, SMID histogram, spill/local | stall 또는 placement 문제를 보고서에 같이 기록한다. |

구현 기준은 hit rate만으로 통과시키지 않는 것이다. `ncu_cache_validation_summary.csv`와
`analyze_ncu_path_acceptance.py` 결과에는 `l1_accesses`, `l2_accesses`,
`dram_accesses`, `l1_request_bytes`, `l1_hit_bytes`, `l2_read_bytes`,
`l2_read_hit_sectors`, `l2_read_miss_sectors`, `dram_bytes`가 함께 있어야 한다.
L1 access는 NCU가 request counter를 제공하면 request를 쓰고, 없으면 sector로
fallback한다. L2/DRAM access는 sector counter다. byte counter가 없으면 sector를
32 bytes로 환산하지만, 보고서에는 이 값이 NCU-derived effective denominator임을
명시한다.

## Path acceptance 기준

현재 `scripts/analyze_ncu_path_acceptance.py`는 mode별로 다음 기준을 적용한다.

| Path | accepted 조건 요약 |
|---|---|
| Tensor | `reg_mma`에서 Tensor/HMMA instruction > 0, spill/local 0, memory traffic이 threshold 이하 |
| Tensor control | `reg_operand_only`에서 Tensor/HMMA instruction = 0, spill/local 0 |
| Shared scalar | shared bytes/accesses > 0, shared instruction 존재, bank conflict ratio 낮음, global/L2/DRAM traffic 낮음 |
| Global L1 | path-specific L1 hit >=95%, L1 request/hit bytes 존재, L2 read/L1 request <=1%, DRAM/L1 request <=1% |
| L2 CG | path-specific L2 read hit >=95%, L1 path hit <=1%, L1 hit/request bytes <=1%, DRAM/L2 read <=2%. aggregate hit rate는 진단값 |
| DRAM sanity | path-specific L1 hit <=1%, DRAM bytes dominant, path-specific L2 read hit은 `max(5%, 2 x L2_capacity/full_working_set + 2%)` 이하 |

L2 CG mode은 measurement 전 warm-up도 `ld.global.cg.u32`를 쓰는
`global_cg_warmup_kernel`로 수행한다. 일반 cached load warm-up이 L1을 채운 뒤
L2 target을 시작하는 혼입을 막기 위한 조치다. 그러나 `.cg` 요청이 L1TEX를
통과하는 것은 정상이므로 L1 request byte 자체는 reject 조건이 아니다.

이 기준을 통과하지 못한 row는 pJ 값이 양수여도 최종 component coefficient로 채택하지 않는다.

## Memory path pJ/byte와 pJ/bit 계산

Memory path는 다음 pair를 사용한다.

| Component/path | treatment | control | denominator |
|---|---|---|---|
| Shared scalar | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes |
| Global L1-hit | `global_l1_load_only` | `global_addr_only` | NCU L1 request bytes |
| L2 CG hit | `l2_cg_load_only` | `global_addr_only` | NCU L2 read bytes |
| DRAM CG streaming | `dram_cg_load_only` | `global_addr_only` | NCU DRAM bytes |

에너지 차분은 elapsed time 차이를 보정한다.

```text
control_power_W = E_control_J / t_control_s
control_energy_scaled_J = control_power_W * t_treatment_s
delta_E_J = E_treatment_J - control_energy_scaled_J
```

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
MEMORY_LOAD_REPEATS=1,2,4,8,16 \
DRAM_LOAD_REPEATS=1,4,16 \
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
| control | `reg_operand_only` | 같은 register fragment 구조를 쓰지만 `mma_sync`는 실행하지 않음 |

Tensor finalplan은 각 RF에서 treatment 목표시간의 `reg_mma` ITER와 control 최소시간의
`reg_operand_only` ITER를 각각 구하고, 둘 중 큰 값을 두 mode에 동일 적용한다. 서로 다른
ITER를 각 mode에 적용한 뒤 elapsed time으로 보정하는 이전 방식은 A100 RF4
이상에서 work mismatch와 음수 delta를 만들 수 있어 final 경로에서 제외했다.
`reg_operand_only`의 기존 RF 비례 FP32 FMA/checksum/memory는 제거했다. 대신
compiler가 loop를 삭제하지 못하도록 RF당 dependent register integer add 1개를
두 mode에 모두 넣었다. 따라서 공통 add 비용은 treatment-control 차분에서
상쇄된다.

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

예시 row:

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

RTX 3090 broad reuse sweep에서는 여러 reuse row의 accepted candidate를 요약해 Tensor
median을 약 `0.170 pJ/FLOP`로 기록했지만 confidence가 low였다. 이후 RF=8/16만
20초, 6회 반복으로 targeted rerun한 결과는 12/12 valid, median `0.107 pJ/FLOP`,
medium-high confidence로 갱신됐다. 같은 RF=8/16에서 fixed `ITER=8000000` 보조실험은
10/10 valid, median `0.146 pJ/FLOP`였다. RF=8 duration-scaling check는
10/20/30초 sweep에서 15/15 valid, median `0.143 pJ/FLOP`, slope
`0.144-0.156 pJ/FLOP`였다. RF=16 duration-scaling check는 15/15 valid,
median `0.077 pJ/FLOP`, slope `0.053-0.071 pJ/FLOP`였다. 따라서 현재 RTX 3090
Tensor는 단일값이 아니라 RF-dependent effective coefficient로 보고한다. 요약하면
RF16 lower는 약 `0.06-0.09 pJ/FLOP`, RF8 upper는 약 `0.14-0.15 pJ/FLOP`다.

## Tensor에서 NCU의 역할

Tensor pJ/FLOP의 분모는 NCU byte가 아니라 logical FLOP다. 따라서 Tensor에서 NCU는 denominator를 만드는 도구가 아니라, 다음 조건을 검증하는 도구다.

| 확인 | 이유 |
|---|---|
| `reg_mma`에서 Tensor/HMMA instruction > 0 | 실제 Tensor path가 실행됐는지 확인 |
| `reg_operand_only`에서 Tensor/HMMA instruction = 0 | control이 no-MMA control인지 확인 |
| spill/local memory = 0 | register spill로 L2/DRAM traffic이 섞이는 것을 방지 |
| L1/L2/DRAM traffic이 작음 | Tensor coefficient가 memory traffic에 오염되지 않았는지 확인 |

따라서 Tensor 결과는 다음처럼 써야 한다.

```text
reg_operand_only 대비 reg_mma의 effective MMA incremental cost
```

다음처럼 쓰면 안 된다.

```text
순수 Tensor Core transistor-level energy
```

## RTX 3090 finalplan 예시

현재 RTX 3090 finalplan matched-control 보고서의 요약은 다음과 같다.

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
| DRAM cumulative effective path | 213.672-227.272 | pJ/byte 환산 범위 | 26.709-28.409 | provisional reference-aligned band; matched-ITER address-control 실측 필요 |

이 표는 순수 회로 에너지 표가 아니다. GPU/device-level energy, control 차분, NCU
denominator가 결합된 microbenchmark coefficient 표다. DRAM 행은 아직 측정 결과가
아니라 최신 보고 범위이며, 동일 ITER `global_addr_only` pair와 exact NCU DRAM bytes를
확보한 뒤에만 median/CI로 교체한다.

## A100/V100/H100 적용 시 주의

NCU denominator scale과 path acceptance는 GPU마다 다시 생성해야 한다. RTX 3090의 NCU scale이나 accepted row를 A100, V100, H100에 그대로 적용하면 안 된다.

| GPU | 반드시 다시 확인할 항목 |
|---|---|
| A100 | `sm_80`, `target_profile=a100`, `NCU_CHIP=ga100`, runtime active SM, L2 40 MiB, shared allocation 164 KiB/SM |
| V100 | `sm_70`, `target_profile=v100`, energy B=1-32, strict NCU Shared/L1/L2 W32/B32, `NCU_CHIP=gv100`, 2024.3 또는 실제 metric query가 성공한 toolchain |
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
