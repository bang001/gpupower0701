# Whole-Softmax 정밀도 범위 측정 설계

## 결정

FP32, scalar FP16, packed FP16x2의 complete Softmax 에너지 범위는 큰
CTA×S factorial sweep 대신 **네 개의 사전 지정 좌표**로 먼저 측정한다.

| 좌표 | S | runtime SM coverage | 역할 |
|---|---:|---:|---|
| `s512_q50` | 512 | 50% | 256-thread CTA에서 자연스럽게 2 element/thread가 되는 anchor |
| `s1024_q50` | 1024 | 50% | 사전 지정 대표값 및 A100 plateau 진입 가설 |
| `s4096_q50` | 4096 | 50% | 큰 width에서 register/occupancy regime가 바뀌는 경계 |
| `s1024_q25` | 1024 | 25% | 동시 CTA 수에 대한 민감도 점검 |

이는 “무조건 많은 S를 넣는 것”보다 충분한 동시 작업과 서로 다른 실행
regime를 보려는 설계다. full-SM saturation(`q=100%`)은 요구하지 않는다.

`S=128/256`은 첫 screen에서 제외한다. 고정 `kThreadsPerBlock=256`에서
thread당 element 수와 packed pair mapping을 바꾸므로, S=512 이상과 다른
kernel geometry를 섞어 범위를 넓히는 것보다 별도 sensitivity 실험으로 두는
편이 타당하다. `S=2048`도 처음부터 넣지 않는다.

사용자가 관찰한 “A100에서 S≥1024는 수렴”은 유용한 prior이지만 이 저장소에는
그 A100 raw 결과가 없다. 따라서 이 문서에서는 **검증할 plateau 가설**로만
사용하며, `S=4096`을 제외하지 않는다.

## 무엇을 비교하는가

모든 policy는 max/subtract, exponent, max+sum reduction, normalization,
I/O를 포함하는 하나의 Softmax forward다.

| policy | I/O | exp | max+sum | normalization |
|---|---|---|---|---|
| `fp32_io_fp32_all` | FP32 | FP32 `__expf` | FP32 | FP32 |
| `fp16_scalar_all` | FP16 | scalar PTX FP16 EX2 | scalar FP16 | scalar FP16 |
| `fp16x2_all` | FP16 | packed PTX FP16x2 EX2 | half2 lane-wise | packed FP16x2 |

기본 지표는 다음과 같다.

```text
net pJ / logical Softmax output element
= (qualified NVML trace energy - idle power × kernel elapsed) × 1e12
  / logical_output_elements
```

이는 end-to-end policy 차이다. FP32는 FP32 I/O이고 두 FP16 policy는 FP16
I/O이므로, “순수 EX2/SFU/ALU 회로 에너지”라고 해석하면 안 된다. 기존
Operand-rate ATC의 `pJ/logical exponent result`와 단위·분모가 다르므로
`82.164 / 19.393 / 25.055 pJ` 같은 EX2 probe 값과 같은 표에서 평균, 차감,
합산하지 않는다.

이 harness는 CTA가 반복 iteration에서 같은 row storage를 재사용한다. 따라서
결과 범위는 **이 cache-reuse/compute 중심 Softmax 좌표**의 범위이며, DRAM
streaming workload 전체의 보편적 범위는 아니다.

## 플랫폼별 실행 계약

| 플랫폼 | profile | CC / native binary | full SM | screen policy | q=25 CTA | q=50 CTA |
|---|---|---|---:|---|---:|---:|
| RTX 3090 | `rtx3090` | 8.6 / sm_86 | 82 | 3-way | 21 | 41 |
| V100 SXM2 | `v100` | 7.0 / sm_70 | 80 | FP32 only | 20 | 40 |
| A100 SXM4 | `a100` | 8.0 / sm_80 | 108 | 3-way | 27 | 54 |
| H100 SXM5 | `h100` | 9.0 / sm_90 | 132 | 3-way | 33 | 66 |
| H100 PCIe | `h100` | 9.0 / sm_90 | 114 | 3-way, 별도 cohort | 29 | 57 |

V100에서 일반 FP16 연산 자체가 불가능하다는 뜻은 아니다. 비교 endpoint의
exponent가 native `ex2.approx.f16`/`ex2.approx.f16x2`를 요구하며 PTX ISA 상
sm_75 이상이 필요하기 때문에, 같은 의미의 scalar/packed endpoint는
`unsupported_native_fp16_ex2_sm70`으로 skip한다. software fallback, 0 pJ 채움,
FP32와 섞은 3-way 평균은 금지한다. V100 build는 sm_70을 지원하는 CUDA 12
toolchain을 사용한다.

RTX 3090/A100/H100은 해당 platform에서 **native cubin**을 새로 build하고
`--validate-only`, binary architecture, resource/occupancy, target-architecture
SASS/PTX audit을 통과한 뒤에만 final evidence가 된다. sm86 lowering을 sm80/sm90에
복사해 해석하지 않는다.

하드웨어 SM 수의 근거는 NVIDIA의 [GA102 whitepaper](https://www.nvidia.com/content/dam/en-zz/Solutions/geforce/ampere/pdf/NVIDIA-ampere-GA102-GPU-Architecture-Whitepaper-V1.pdf),
[Ampere architecture material](https://developer.nvidia.com/blog/?p=17431),
[Hopper architecture material](https://developer.nvidia.com/blog/nvidia-hopper-architecture-in-depth/)을
따른다. FP16 EX2의 ISA 지원 조건은 [PTX ISA EX2 문서](https://docs.nvidia.com/cuda/parallel-thread-execution/#half-precision-floating-point-instructions-ex2)를
따른다.

## CTA/occupancy 검증

이 protocol은 `blocks-per-sm`를 입력으로 쓰지 않는다. explicit
`grid_blocks = ceil(runtime_SM_count × q)`만 쓴다. 각 policy/S에서 runtime
occupancy API가 반환한 값을 `O`라 하면,

```text
static_single_wave_capacity_blocks = runtime_SM_count × O
```

이고 모든 session은 `grid_blocks ≤ static_single_wave_capacity_blocks`를
fail-closed로 확인한다. CSV에는 아래를 남긴다.

- `threads_per_block`, `elements_per_thread`
- `occupancy_max_blocks_per_sm`
- `static_single_wave_capacity_blocks`
- `grid_nominal_ctas_per_sm`, `grid_sm_coverage`
- `static_single_wave_capacity_gate_pass`

이 protocol의 `q=25%/50%`는 단순히 요청한 `grid_blocks/SM` 비율로 끝내지 않는다.
grid가 runtime SM 수를 넘지 않는 initial screen에서는 measured role마다
`smid_unique = grid_blocks`, `smid_max_blocks_on_sm = 1`을 요구한다. 즉 kernel
entry에서 각 CTA가 서로 다른 SM에 한 번씩 관측되어야 한다. 이것은 장기 resident
CTA나 SM affinity의 증명은 아니지만, “25%/50% 동시 CTA placement” 해석에 필요한
실제 launch 분산 gate다.

RTX 3090 sm86에서 새 target을 `--validate-only`로 확인한 초기 resource 결과는
다음과 같다. 모든 path는 spill 0이었고, S=4096에서만 FP32 endpoint가 4 CTA/SM로
낮아졌다.

| S | FP32 occupancy | scalar FP16 occupancy | packed FP16x2 occupancy |
|---:|---:|---:|---:|
| 512 | 6 | 6 | 6 |
| 1024 | 6 | 6 | 6 |
| 4096 | 4 | 6 | 6 |

따라서 4096은 “1024 이상이라 같을 것”으로 제거하면 안 되는 resource-boundary
sentinel이다.

소스 target build도 runtime 측정과 구분해 확인했다. CUDA 13.2에서는 A100용 sm80와
H100용 sm90 binary가 모두 build되며, 모든 `S×endpoint` specialization에서 stack/spill
0 B였다. 이 표는 compile-time resource check이지 A100/H100 energy 측정값은 아니다.

| S | A100 sm80 registers (FP32 / scalar / packed) | H100 sm90 registers (FP32 / scalar / packed) |
|---:|---:|---:|
| 512 | 26 / 21 / 20 | 31 / 21 / 21 |
| 1024 | 30 / 28 / 26 | 32 / 28 / 28 |
| 2048 | 40 / 32 / 32 | 40 / 32 / 32 |
| 4096 | 56 / 39 / 32 | 56 / 41 / 40 |

현재 CUDA 13.2 toolchain은 sm70 code generation을 제공하지 않는다. V100 range run은
CUDA 12.x toolchain에서 별도 sm70 binary를 build해야 하며, 이 target의 FP32 endpoint만
eligible이다.

## Fresh-process 측정 순서

3-way platform의 각 coordinate는 fresh CUDA process 세 개로 구성한다.

```text
session 1: FP32 → scalar FP16 → packed FP16x2   (ABC)
session 2: scalar FP16 → packed FP16x2 → FP32   (BCA)
session 3: packed FP16x2 → FP32 → scalar FP16   (CAB)
```

coordinate도 repetition마다 interleave한다. 따라서 initial screen은

```text
4 coordinates × 3 fresh sessions × 3 policies = 36 role rows
```

이며, V100은 4×3×1=12 FP32 role rows다. 60-cell full grid보다 작지만 policy
position과 coordinate 시간을 한 block에 몰아 두지 않는다.

각 fresh process에서 다음 contract를 강제한다.

1. 모든 endpoint numerical validation과 policy별 calibrated iteration count를
   canonical policy enum 순서로 끝낸다.
2. 측정 policy와 무관한 `fp32_io_fp32_all` conditioner를 **한 번만 5 s** 실행한다.
   C++ actual gate는 3.75–6.25 s이고 actual 값을 raw CSV에 기록한다.
3. unrecorded policy warm-up 없이 사전 선언된 ABC/BCA/CAB schedule을 실행한다.
4. role당 약 13 s kernel, role 전 1 s idle baseline, 500 ms NVML sampling,
   최소 16 counter update와 trace R²≥0.98을 적용한다.

온도는 기록 context다. 사용자가 허용한 대로 온도차 자체는 hard reject나 causal
correction으로 쓰지 않는다. 반대로 NVML trace fallback, numerical failure,
SMID failure, binary architecture mismatch, static-capacity failure는 hard reject다.

## 범위와 adaptive 분석

각 `(platform, policy, coordinate)`에서 fresh session 3개의 mean, median, sample
SD, min/max, descriptive t95를 만든다. 분석 단위는 role 하나가 아니라 fresh
process/session이다.

- **대표값:** 결과를 본 뒤 고르지 않고 `S=1024, q=50%` median으로 고정한다.
- **screened best/worst:** 승인된 screen coordinate 중 median 최저/최고다.
- **tie set:** 최저 또는 최고와 10% 이내인 coordinate는 단일 승자를 강제하지
  않고 함께 보고한다.
- **confirmed observed range:** screened extrema는 selection bias가 있으므로,
  각 policy의 선택된 best/worst coordinate를 새 fresh 3-session으로 재측정한
  뒤에만 이 이름으로 승격한다.

10% practical gate는 유의성 검정이 아니라 불필요한 sweep을 막는 의사결정
threshold다.

| gate | 조건 | 다음 행동 |
|---|---|---|
| plateau | 어떤 지원 policy라도 `S1024/q50`와 `S4096/q50` median 차이가 >10% | `S2048/q50`만 추가 |
| load | 어떤 지원 policy라도 `S1024/q25`와 `S1024/q50` median 차이가 >10% | `S512/q25`, `S4096/q25`만 추가 |
| 둘 다 미충족 | 모든 지원 policy가 10% 이내 | screen에서 중단, broad sweep 없음 |

플랫폼 간 pJ 값은 pool하거나 하나의 best GPU ranking으로 만들지 않는다. 각
platform은 I/O, cache, clock, driver, target cubin이 다른 독립 cohort다.

## 실행 방법

```bash
source scripts/activate_softmax_experiment_env.sh

# RTX 3090
cmake -S . -B build-whole-precision-range-rtx3090 \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build build-whole-precision-range-rtx3090 \
  --target a100_fp16_softmax_whole_precision_range_energy -j

TAG="$(date +%Y%m%d)_range"
"$GPUPWR_PYTHON_BIN" scripts/run_softmax_whole_precision_range.py \
  --target-profile rtx3090 --build-dir build-whole-precision-range-rtx3090 \
  --session-tag "$TAG" --gpu-id 0 --phase screen --execute
RUN="results/raw/rtx3090_softmax_whole_precision_range_${TAG}_screen"
"$GPUPWR_PYTHON_BIN" scripts/audit_softmax_whole_precision_range_sass.py \
  --binary "$RUN/frozen/a100_fp16_softmax_whole_precision_range_energy" \
  --target-profile rtx3090 --required-softmax-cols 512,1024,4096 \
  --out "$RUN/sass_audit.json" --capture-dir "$RUN/static_audit" --fail-on-unexpected
"$GPUPWR_PYTHON_BIN" scripts/bind_softmax_whole_precision_range_sass.py \
  --run-dir "$RUN" --sass-audit "$RUN/sass_audit.json"
"$GPUPWR_PYTHON_BIN" scripts/analyze_softmax_whole_precision_range.py \
  --run-dir "$RUN"
```

다른 platform은 build architecture와 profile을 바꾼다. H100은 SXM5(132 SM)와
PCIe(114 SM)를 같은 cohort로 섞지 않으므로 `--runtime-sm-count`도 명시한다.

```bash
# A100: -DCMAKE_CUDA_ARCHITECTURES=80 --target-profile a100
# H100 SXM5: -DCMAKE_CUDA_ARCHITECTURES=90 --target-profile h100 --runtime-sm-count 132
# H100 PCIe: -DCMAKE_CUDA_ARCHITECTURES=90 --target-profile h100 --runtime-sm-count 114
# V100: CUDA 12 environment에서 -DCMAKE_CUDA_ARCHITECTURES=70 --target-profile v100
```

SASS audit은 **measurement 뒤** run-local frozen binary에 수행한다. 이것은 static
evidence가 acquisition 전 frozen executable에 대응한다는 것을 raw/trace SHA와 함께
manifest에 bind하기 위한 순서다. PTX endpoint type/count는 hard gate지만, SASS opcode
family는 platform-native provenance로만 기록한다. 즉 sm86의 lowering을 sm70/sm80/sm90
cycle·energy·physical issue count로 일반화하지 않는다.

분석기는 `analysis/coordinate_summary.csv`, `analysis/range_summary.csv`,
`analysis/followup_plan.json`, `analysis/quality_gates.csv` 및 `analysis.json`을
만든다. follow-up이 필요한 경우 이 JSON의 coordinate만 새 run으로 실행한다.
새 follow-up/confirmation run을 `--run-dir "$CHILD"`만으로 분석하면 parent screen과
자동 결합하지 않고 `supplemental_coordinate_run_not_combined_with_parent`로 표시한다.
이는 child 하나만 보고 post-hoc best/representative/worst를 다시 고르는 것을 막기
위한 기본 동작이다.

화면 전체의 screened range를 갱신할 때만 아래처럼 **명시적으로** hash-bound
`--parent-run`을 준다. analyzer는 child가 `followup` phase인지, parent가 initial
`screen`인지, child가 audit/bind 시점의 parent manifest **path+SHA**를 갖는지, profile과
frozen binary SHA가 같은지, 그리고 child coordinate가 parent gate가 요청한 집합과
정확히 같은지를 모두 fail-closed로 확인한 뒤 child의 `analysis/`에 결합 결과를 쓴다.
이 결합은 동일 platform/cohort의 adaptive
coordinate만 대상으로 하며, historical 20 s cohort나 다른 GPU platform을 pool하지
않고, selected extrema의 독립 fresh confirmation도 대체하지 않는다.

```bash
# followup_plan.json에 실제로 적힌 coordinate만 정확히 입력한다.
FOLLOWUP_COORDS="<comma-separated coordinate IDs from $RUN/analysis/followup_plan.json>"
FOLLOWUP_S="<the sorted unique S values represented by FOLLOWUP_COORDS>"
FOLLOWUP_TAG="${TAG}_followup"
"$GPUPWR_PYTHON_BIN" scripts/run_softmax_whole_precision_range.py \
  --target-profile rtx3090 --build-dir build-whole-precision-range-rtx3090 \
  --binary "$RUN/frozen/a100_fp16_softmax_whole_precision_range_energy" \
  --output-dir results/raw --session-tag "$FOLLOWUP_TAG" --gpu-id 0 \
  --phase followup --coordinates "$FOLLOWUP_COORDS" --continue-from "$RUN" --execute
CHILD="results/raw/rtx3090_softmax_whole_precision_range_${FOLLOWUP_TAG}_followup"
"$GPUPWR_PYTHON_BIN" scripts/audit_softmax_whole_precision_range_sass.py \
  --binary "$CHILD/frozen/a100_fp16_softmax_whole_precision_range_energy" \
  --target-profile rtx3090 --required-softmax-cols "$FOLLOWUP_S" \
  --out "$CHILD/sass_audit.json" --capture-dir "$CHILD/static_audit" --fail-on-unexpected
"$GPUPWR_PYTHON_BIN" scripts/bind_softmax_whole_precision_range_sass.py \
  --run-dir "$CHILD" --sass-audit "$CHILD/sass_audit.json"
"$GPUPWR_PYTHON_BIN" scripts/analyze_softmax_whole_precision_range.py \
  --run-dir "$CHILD" --parent-run "$RUN"

# RUN (screen만 종료) 또는 CHILD (명시 결합 follow-up)의 final analyzer product를 보고서로 만든다.
"$GPUPWR_PYTHON_BIN" scripts/build_softmax_whole_precision_range_report.py \
  --run-dir "${CHILD:-$RUN}" --out-dir docs/results
```

## 현재 구현 상태

- range 전용 target `a100_fp16_softmax_whole_precision_range_energy`는 기존
  stage-isolation/confirmation binary를 덮어쓰지 않는다.
- 지원 S는 의도적으로 `512|1024|2048|4096`만 compile-time specialize한다.
- RTX 3090에서 S=512/1024/4096의 FP32/scalar/packed numerical validation,
  resource query, contiguous-pair mapping과 5 s conditioner/actual SM placement smoke
  session을 확인했다.
- CUDA 13.2에서 A100(sm80)와 H100(sm90) native build를 확인했지만, 두 platform의
  pJ 범위는 target node fresh acquisition 전까지 비어 있다.
- A100/V100/H100의 final pJ 범위는 해당 hardware에서 native build와 fresh
  acquisition을 완료하기 전에는 이 문서에 수치로 채우지 않는다.
