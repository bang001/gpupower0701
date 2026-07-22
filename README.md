# FP16 Tensor Core Energy Experiment v2

CUDA/C++ microbenchmark framework for estimating effective energy of a logical
warp-level FP16 `m16n16k16` MMA operation on NVIDIA Tensor Core GPUs.

## Presentation

GPU component/path별 effective microbenchmark coefficient가 만들어지는 전체 과정을
22장 PowerPoint로 정리했다. 현행 finalplan과 2026-07-14 RTX 3090 v5 결과를 중심으로
NVML measurement scope, treatment-control, NCU denominator/path 검증 및
strict/package audit를 단계별로 설명한다. 이전 protocol은 historical로만 구분한다.

- [PowerPoint](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.pptx)
- [Rendered PDF](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.pdf)
- [Evidence notes](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.md)

The default runtime profile in this checkout targets GeForce RTX 3090
(`sm_86`, 82 SMs, 6 MiB nominal L2). Additional profiles are available for
V100, A100, and H100. Use `--target-profile auto` to select a profile from the
runtime CUDA device when running on the target machine.

## Current FP16 Tensor-only v3

새 FP16 Tensor 계수 실험의 표준 진입점은
`scripts/plan_tensor_fp16_cross_platform_experiment.py`다. 이 package는 memory
component를 함께 실행하지 않고 `clocked_empty`, `reg_operand_only`,
`reg_mma`만 수집한다. 하나의 measurement bundle에서 다음 네 방법을
동시에 계산하며, v3를 특정 한 방법의 이름으로 해석하지 않는다.

| v3 출력 | 계산 경계 | 주요 해석 |
|---|---|---|
| matched-ITER completion | 동일 ITER의 `net_E_treatment - net_E_control` | 같은 work 완료의 실측 증분 |
| clocked MI-ATC | completion에서 pair 인접 `clocked_empty` 순전력 x 실행시간 차를 제거 | 저활동 active-time 보정 대리값 |
| control-rate ATC | `reg_operand_only`의 순전력률을 treatment 시간으로 확장해 제거 | Tensor operand-rate arm 진단 |
| joint regression | FLOP과 추가 실행시간을 별도 설명변수로 추정 | sweep 전체의 식별 가능성 진단 |

빠른 경로/캘리브레이션 점검은 `pilot`, 계수 후보 수집은 `final`로
분리한다. Pilot은 repeat 1이므로 final coefficient로 승격하지 않는다.

```bash
TAG="$(date +%Y%m%d)"
python3 scripts/plan_tensor_fp16_cross_platform_experiment.py \
  --target-profile rtx3090 --gpu-id 0 --preset pilot --tag "$TAG"
bash "results/summary/rtx3090_tensor_fp16_cross_platform_pilot_${TAG}_command.sh"
```

수식, RF/duration/blocks/SM sweep, NCU denominator, acceptance 규칙은
[GPU Component 동적 에너지 귀속 프로토콜](docs/methodology/component_dynamic_attribution_protocol_ko.md)이
기준이다. 기존 full-component finalplan은 memory path 실험을 위해 보존하며,
새 Tensor-only 계수와 구형 finalplan 결과를 직접 혼합하지 않는다.

2026-07-22 RTX 3090에서 이 경로를 실제로 다시 실행한 결과와 NCU 검증은
[Tensor-only v3 진단 보고서](docs/results/rtx3090_tensor_fp16_v3_diagnostic_20260722_ko.md)에
있다. 이 실행은 energy/NCU 코드 경로는 확인했지만 quiescence를 생략하고 좌표당
1회만 측정했으므로 final coefficient가 아니라 diagnostic evidence다.

The implementation inherits the logical FP16 WMMA operation definition from the
original v2 design. New Tensor-only runs use the v3 package above; the
acceptance-first full-component flow remains documented in
`docs/methodology/component_energy_final_experiment_plan_ko.md` and
`docs/platforms/cross_platform_component_experiment_guide_ko.md`. Memory pJ/bit results
must use NCU actual traffic counters and should be reported as transaction-path
effective coefficients, not as SRAM/HBM bitcell energy. The self-critique and
known limitations are tracked in `docs/audits/component_energy_self_critique_ko.md`.
For the detailed NCU validation and pJ/FLOP or pJ/byte calculation method, see
`docs/methodology/ncu_validation_energy_calculation_ko.md`.

## Platform별 빠른 실행 가이드

항상 대상 GPU 노드에서 최신 `main`을 받은 뒤 **새로운 날짜 태그로 command
package를 생성**한다. 저장소에 포함된 과거 날짜의 `*_commands.sh`는 당시
프로토콜을 재현하기 위한 자료이며, 새 실험의 기본 진입점이 아니다.

```bash
git switch main
git pull --ff-only origin main
nvidia-smi
NVCC="$(command -v nvcc)"
NCU_BIN="$(command -v ncu)"
CUOBJDUMP="$(dirname "$NVCC")/cuobjdump"
"$NVCC" --version
"$NCU_BIN" --version
test -x "$NVCC" -a -x "$NCU_BIN" -a -x "$CUOBJDUMP"
export NVCC NCU_BIN CUOBJDUMP
TAG="$(date +%Y%m%d)"
```

| GPU | planner profile | CUDA arch | build directory | 실행 전 핵심 확인 | 상세 가이드 |
|---|---|---:|---|---|---|
| RTX 3090 (GA102) | `rtx3090` | `sm_86` | `build` | 실험 중 다른 그래픽/compute 부하를 최소화하고 현재 strict protocol로 재측정 | [cross-platform guide](docs/platforms/cross_platform_component_experiment_guide_ko.md) |
| V100 (GV100) | `v100` | `sm_70` | `build-v100` | `compute_70`을 지원하는 CUDA 12.x 사용; CUDA 13.x는 `sm_70` 빌드 불가 | [V100 node guide](docs/platforms/v100_node_experiment_guide_ko.md) |
| A100 (GA100) | `a100` | `sm_80` | `build-a100` | L2 NCU-first selector와 fabric-aware acceptance를 임의로 우회하지 않음 | [A100 node guide](docs/platforms/a100_node_experiment_guide_ko.md) |
| H100 SXM5 profile (GH100) | `h100` | `sm_90` | `build-h100` | 132-SM/HBM3 profile; partition-fabric L2와 WMMA compatibility path 검증. PCIe SKU는 별도 label 필요 | [H100 node guide](docs/platforms/h100_node_experiment_guide_ko.md) |

현행 strict 기본 좌표는 다음과 같다. Tensor만 utilization을 보기 위해 B 세 점을
유지하고, memory path는 energy와 exact-coordinate NCU가 같은 단일 B anchor를 쓴다.

| GPU | Tensor blocks/SM | memory blocks/SM | Shared W_SM (KiB/SM) | Global L1 W_SM (KiB/SM) | L2 W_SM (KiB/SM) | External W_SM (KiB/SM) | RF/LR |
|---|---|---|---:|---:|---:|---:|---|
| RTX 3090 | 4,8,16 | 8 | 64 | 8 | 32,64 | 256,512,2048 | RF 1,2,4,8,16; LR 4,8,16 |
| V100 | 4,16,32 | 32 | 32 | 32 | 32,64; selector B32/16/4 | 256,512,2048 | RF 1,2,4,8,16; LR 4,8,16 |
| A100 | 4,16,32 | 16 | 128 | 16 | 16,128; selector B16/8/4/2/1 | 2048,4096,8192 | RF 1,2,4,8,16; LR 4,8,16 |
| H100 SXM5 | 4,16,32 | 16 | 128 | 16 | 64,128; selector B16/8 | 2048,4096,8192 | RF 1,2,4,8,16; LR 4,8,16 |

기본 package는 각 플랫폼에서 72 energy commands, 5 repeats 기준 360 raw rows와
73 final NCU cases를 만든다. A100/V100/H100 L2 selector precheck는 별도이며 첫 통과
후 중단한다. 좌표 선정 근거와 제거한 sweep은
[memory-path audit](docs/audits/memory_path_cross_architecture_sweep_audit_ko.md)에 기록한다.

### RTX 3090

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build build --clean-first -j

python3 scripts/plan_platform_component_experiment.py \
  --target-profile rtx3090 \
  --binary ./build/a100_fp16_energy_v2 \
  --ncu "$NCU_BIN" \
  --tag "$TAG"

bash "results/summary/rtx3090_component_finalplan_${TAG}_commands.sh"
```

### V100

V100은 먼저 선택한 CUDA toolkit이 `compute_70`을 제공하는지 확인한다.

```bash
export NVCC=/usr/local/cuda-12.4/bin/nvcc
export CUOBJDUMP=/usr/local/cuda-12.4/bin/cuobjdump
export NCU_BIN=/usr/local/cuda-12.4/bin/ncu
"$NVCC" --list-gpu-arch | grep -q compute_70
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DCUDAToolkit_ROOT=/usr/local/cuda-12.4 \
  -DCMAKE_CUDA_ARCHITECTURES=70
cmake --build build-v100 --clean-first -j

python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --ncu "$NCU_BIN" \
  --tag "$TAG"

bash "results/summary/v100_component_finalplan_${TAG}_commands.sh"
```

### A100

```bash
export NVCC=/usr/local/cuda-13.0/bin/nvcc
export CUOBJDUMP=/usr/local/cuda-13.0/bin/cuobjdump
export NCU_BIN=/usr/local/cuda-13.0/bin/ncu
cmake -S . -B build-a100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DCUDAToolkit_ROOT=/usr/local/cuda-13.0 \
  -DCMAKE_CUDA_ARCHITECTURES=80
cmake --build build-a100 --clean-first -j

python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$NCU_BIN" \
  --tag "$TAG"

bash "results/summary/a100_component_finalplan_${TAG}_commands.sh"
```

### H100

```bash
cmake -S . -B build-h100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=90
cmake --build build-h100 --clean-first -j

python3 scripts/plan_platform_component_experiment.py \
  --target-profile h100 \
  --binary ./build-h100/a100_fp16_energy_v2 \
  --ncu "$NCU_BIN" \
  --tag "$TAG"

bash "results/summary/h100_component_finalplan_${TAG}_commands.sh"
```

생성된 shell은 strict preflight, power/energy 측정, treatment-control NCU
검증, matched-control 분석, reliability audit, strict summary 및 package
audit를 순서대로 수행한다. Energy sweep 전에는 `cuobjdump` 기반 Tensor binary
audit도 실행해 treatment HMMA, control HMMA=0, local spill=0뿐 아니라
`reg_operand_only`의 backward loop가 ptxas 후에도 남아 있는지 확인한다. NCU가
`ERR_NVGPUCTRPERM`을 반환하면 기본 자동
재시도가 `sudo -E`를 사용한다. 처음부터 sudo NCU를 강제하려면 다음처럼
실행한다. 전체 energy harness가 아니라 NCU invocation만 권한 상승 대상이다.

`schema_revision_smoke` 는 kernel execution, power/schema audit, Tensor binary
audit으로 분리해 표시한다. 실패한 명령은
`PIPELINE_COMMAND_FAILED` 행에 stage, label, return code를 남긴다. Tensor
audit은 PATH의 임의 `cuobjdump`가 아니라 `NVCC`와 같은 toolkit의
binary inspector를 사용한다. 중단 판독은
[A100/V100 schema smoke 감사](docs/audits/a100_v100_schema_smoke_stop_20260716_ko.md)를 따른다.
Smoke 밖의 처리되지 않은 오류도 `PIPELINE_ABORT`에 active stage,
shell line, return code, failed command를 남긴다.
멀티 GPU row identity와 동일 좌표 L1/L2/DRAM control 격리의 수정 근거는
[pairing identity 감사](docs/audits/multigpu_sweep_pairing_identity_fix_20260716_ko.md)에 기록한다.

```bash
NCU_USE_SUDO=1 bash \
  "results/summary/<profile>_component_finalplan_${TAG}_commands.sh"
```

실험 완료는 단순히 shell이 끝났다는 뜻이 아니다. `results/summary/`에서
power API audit, power-state audit, NCU acceptance, matched-control,
reliability, strict component summary와 package audit가 모두 생성되고 각 필수
gate가 통과했는지 확인해야 한다. 특정 경로가 reject되면 계수를 임의로 채우지
말고 해당 경로를 미측정 상태로 보고한다. 플랫폼별 capacity, sweep 좌표,
NVML 의미 및 NCU counter 차이는
[cross-platform guide](docs/platforms/cross_platform_component_experiment_guide_ko.md)와
[power API matrix](docs/platforms/power_measurement_api_matrix_ko.md)를 함께 확인한다.

For a quick map of active vs archived material, start with `docs/README.md` and
`scripts/README.md`. Legacy design/code paths are kept under
`archive/legacy_20260707/`.
GPU-generation-specific power/energy API support, sampling semantics, scope,
and final-numerator eligibility are summarized in
`docs/platforms/power_measurement_api_matrix_ko.md`; check this before
comparing RTX 3090, V100, A100, and H100 measurements. API visibility is not
the same as coefficient validity.
Final component coefficients should use `nvmlDeviceGetTotalEnergyConsumption`
rows when available. `nvmlDeviceGetPowerUsage` is treated as a fallback because
its meaning changes by chip family: V100/A100 are recorded as instantaneous,
while RTX 3090/H100 are recorded as one-second average semantics.
Do not equate API visibility with coefficient validity: `power.draw.*`,
`GetPowerUsage`, Hopper module power, and GPU memory power are useful metadata
or provisional fallbacks, but the current final denominator policy requires a
GPU/device total-energy mJ delta plus NCU path validation.

**Measured result status (2026-07-14):** the RTX 3090 v5 finalplan package is
complete. All four strict components passed reliability, strict-summary, and
platform-package audits. The external-memory row passed separately as an
effective GPU-device read path, not physical GDDR6X energy. This is preserved
as GA102 v5 evidence; it is not silently relabeled as a v6 result.

**Current Tensor kernel source revision (v6, 2026-07-16):** this kernel revision is
required underneath every new Tensor-only v3 run. Here, v6 names the C++/CUDA
control-kernel revision; v3 names the measurement and analysis package. An A100
v5 run exposed a launch-only `reg_operand_only` control: more than
one billion requested iterations completed in about 1 ms, and the resulting
pair-lock made one `reg_mma` command run for 2,096-4,280 s. Those A100 Tensor
rows are rejected. v6 adds a matched `SR_CLOCKLO` runtime token, a 50 ms
calibration trial floor, a 6x treatment-stretch gate, and a 180 s per-command
wall-time guard. See the
[A100 Tensor calibration failure audit](docs/audits/a100_tensor_control_calibration_failure_20260715_ko.md).

| Path | Current result | Scope/status |
|---|---:|---|
| Tensor MMA incremental | `2.140 pJ/FLOP` | strict accepted; includes unmatched WMMA register/scheduler path |
| Shared scalar | `0.714 pJ/bit` | strict accepted effective path |
| Global L1 hit | `0.852 pJ/bit` | strict accepted effective path |
| L2 CG hit | `9.078 pJ/bit` | strict accepted effective path |
| External-memory read | `24.949 pJ/bit` | `accepted_effective_path`; not GDDR6X device energy |

The run contains 360 raw energy rows, 180/180 valid matched pairs, and 73 NCU
rows. Final treatment/control evidence accounts for 72 accepted NCU rows; the
remaining `clocked_empty` baseline is intentionally `not_selected`. The strict
summary audit passed 193 checks with no failures or warnings, and the platform
package audit passed 31 checks with no failures, missing artifacts, or warnings.

Current RTX 3090 artifacts:

| artifact | path |
|---|---|
| readable result report and figures | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| strict component summary | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md` |
| NCU acceptance and raw counter table | `results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.md` |
| Tensor v5 binary audit | `results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.md` |
| power API / power-state audits | `results/summary/rtx3090_component_finalplan_20260714_power_api_audit.md`, `results/summary/rtx3090_component_finalplan_20260714_power_state_audit.md` |
| strict/package audits | `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.md`, `results/summary/rtx3090_platform_result_package_audit_20260714.md` |
| multi-platform readiness audit | `results/summary/component_energy_goal_readiness_audit_20260716.md` |

Experiment setup and method documents:

| question | document |
|---|---|
| How does the current experiment work? | `docs/methodology/howitworks.md` |
| What are the final sweep/settings and gates? | `docs/methodology/component_energy_final_experiment_plan_ko.md` |
| How are NCU counters used for pJ/FLOP and pJ/bit? | `docs/methodology/ncu_validation_energy_calculation_ko.md` |
| How are platform capacities, sweeps, and NCU differences handled? | `docs/platforms/cross_platform_component_experiment_guide_ko.md` |
| What power APIs and semantics apply by GPU generation? | `docs/platforms/power_measurement_api_matrix_ko.md` |
| Where is the full documentation map? | `docs/README.md` |

The current Tensor source revision is
`matched_runtime_clock_observed_control_fixed_rf_v6`. Static binary audit
requires treatment HMMA, control HMMA=0, no local allocation, and a backward
loop containing an `SR_CLOCKLO` runtime-token read in both modes. Calibration
must prove a trial runtime of at least 50 ms before extrapolating ITER. Runtime
NCU additionally requires HMMA/logical-MMA linearity, operation-proportional
control SASS, and zero spill/local traffic. `W_SM=1 KiB` is only a Tensor CLI
placeholder and RF means inner MMA grouping. The coefficient is not pure Tensor
circuitry because the runtime token, WMMA operand/accumulator registers,
scheduler behavior, and unequal treatment/control completion time remain in the
effective board-level difference.

The v4 control loop was removed by ptxas and is invalid. v5 repaired GA102 but
was not portable to the observed A100 `sm_80` code generation. Earlier snapshots
remain under `archive/pre_current_protocol_20260712/` and `results/archive/`;
v4, failed A100 v5, and new v6 results must not be averaged together.

Platform guides:

| GPU | guide |
|---|---|
| A100 | `docs/platforms/a100_node_experiment_guide_ko.md` |
| V100 | `docs/platforms/v100_node_experiment_guide_ko.md` |
| H100 | `docs/platforms/h100_node_experiment_guide_ko.md` |

Generated cross-platform command packages:

| GPU | command plan | executable shell |
|---|---|---|
| A100 | `results/summary/a100_component_finalplan_20260716_command_plan.md` | `results/summary/a100_component_finalplan_20260716_commands.sh` |
| A100 Tensor/L2 remediation | `results/summary/a100_tensor_l2_remediation_20260710_command_plan.md` | `results/summary/a100_tensor_l2_remediation_20260710_commands.sh` |
| RTX 3090 | `results/summary/rtx3090_component_finalplan_20260716_command_plan.md` | `results/summary/rtx3090_component_finalplan_20260716_commands.sh` |
| V100 | `results/summary/v100_component_finalplan_20260716_command_plan.md` | `results/summary/v100_component_finalplan_20260716_commands.sh` |
| H100 | `results/summary/h100_component_finalplan_20260716_command_plan.md` | `results/summary/h100_component_finalplan_20260716_commands.sh` |

These command packages are generated plans, not measured platform results. Run
them on the matching target node after building the profile-specific binary, then
rerun the power API, power-state, NCU, reliability, strict-summary, and goal
readiness audits.

The standard A100, V100, and H100 finalplans first collect and preserve the
independent Tensor, Shared, Global-L1, and external-memory energy sweeps. They
then run an NCU-first L2 selector before the L2 energy sweep. Therefore, an L2
selector rejection does not erase or invalidate the non-L2 raw measurements.
The standalone A100 remediation package remains a focused diagnostic for the
previously observed direct-partition hit range. The selector runs
application-replay NCU prechecks over an ordered
policy/address-layout/blocks-per-SM candidate list. On GA100 and GH100, the 95% gate applies
to logical final service computed from source/TEX plus `srcunit_ltcfabric` hits;
native lookup hit is checked against the reconstructed fabric model instead of
being forced above 95%. It also requires observed L2 bytes to match logical
expected traffic and verifies the persisting-cache size counter. It
stops before the L2 energy sweep if no candidate passes. A persisting or
`sm_interleaved` result is configuration-specific effective path evidence, not a
universal default-L2 value.

The message `W=2048KiB B=16 SM=108 RF=4 ... ratio=21.930` was an intentional
negative fixture inside the old policy self-test, not an A100 or V100 hardware
calibration result. Current packages label synthetic tests explicitly, suppress
their expected rejection diagnostics, and print the real profile and coordinate
before runtime calibration. See
`docs/audits/a100_v100_synthetic_selftest_false_failure_20260716_ko.md`.

All platform packages now profile strict L2 rows with the smaller
`NCU_METRIC_PROFILE=l2_path_minimal` bundle and require hit/miss/read sector
conservation. Tensor/Shared/Global-L1/external-memory paths use a separate full diagnostic run;
`merge_ncu_validation_summaries.py` combines the disjoint rows without mixing
metrics from different replay passes into one row. A full-bundle L2 hit rate
cannot override an incoherent minimal-profile result.

Prompt templates:

| GPU | prompt |
|---|---|
| V100 | `docs/platforms/prompts/v100_experiment_prompt_ko.md` |

## Operation Definition

- 1 logical op = 1 warp-level FP16 `m16n16k16` MMA.
- 1 logical op = 4096 FMA = 8192 FLOP.
- 1 logical op input footprint = A+B FP16 = 1KiB = 8192 bits.
- `threads/block = 32`, so `blocks/SM = resident warps/SM`.

For V100, Tensor uses `blocks/SM=4,16,32`; Shared, Global-L1, and external-memory
energy/NCU use B32. L2 first tests
normal-residency contiguous B32 and sm-interleaved B32/B16/B4 at W32/W64, then
uses the first strict-pass B in both L2 energy and minimal coherent L2 NCU. V100 does not use
persisting-L2 controls. Because the
kernel has one warp per block, B32 requests at most 32 warps/SM, or 50% of
GV100's 64-warp limit. Register/shared-memory limits can reduce actual
residency, so NCU achieved occupancy and launch registers/thread must be
reported; B32 is not proof of 32 simultaneously resident blocks or full warp
occupancy. The V100 L2 anchors are 2.5 and 5 MiB total
(`80 SM x 32/64 KiB`); both must pass before an L2 coefficient is attempted.

The current kernel implementation uses CUDA WMMA as the portable Tensor Core
path. In low-level SASS this may compile to multiple tensor instructions for one
logical `m16n16k16` op. Raw inline PTX `mma.sync.aligned.m16n8k16` and explicit
`ldmatrix` are not the primary implementation yet; CSV rows mark
`wmma_fallback=1` in `notes`.

## Build

The default `build` directory below targets the local RTX 3090 profile
(`sm_86`). For cross-platform runs, build into a profile-specific directory so
an A100/V100/H100 result cannot accidentally come from an RTX 3090 binary.

| profile | CUDA arch | build directory | binary used by generated finalplan |
|---|---:|---|---|
| `rtx3090` | 86 | `build` | `./build/a100_fp16_energy_v2` |
| `v100` | 70 | `build-v100` | `./build-v100/a100_fp16_energy_v2` |
| `a100` | 80 | `build-a100` | `./build-a100/a100_fp16_energy_v2` |
| `h100` | 90 | `build-h100` | `./build-h100/a100_fp16_energy_v2` |

V100 is a toolchain exception: CUDA 13 removed Volta offline compilation
support. Use a CUDA 12.x compiler and verify that
`nvcc --list-gpu-arch` contains `compute_70` before configuring `build-v100`.
The NCU executable is an independent choice; the reviewed baseline is Nsight
Compute 2024.3 with live `gv100` chip/metric queries.

```bash
/home/bang001/miniforge3/envs/ssc21env/bin/cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/home/bang001/miniforge3/envs/ssc21env/bin/nvcc \
  -DCUDAToolkit_ROOT=/home/bang001/miniforge3/envs/ssc21env \
  -DCMAKE_CUDA_ARCHITECTURES=86
/home/bang001/miniforge3/envs/ssc21env/bin/cmake --build build -j
```

NVML is required. If CMake cannot find it, make sure the NVIDIA driver
development files are installed or `CUDA_PATH` points at a CUDA toolkit
installation. The build enables `-Xptxas=-v` so register count and spill warnings
are visible in the build log.

Before measurement, check the platform state manually:

```bash
nvidia-smi -L
sudo nvidia-smi -pm 1
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
nvidia-smi -q -d POWER,CLOCK,TEMPERATURE
```

This tool records clocks, temperature, power limit, and ECC metadata where NVML
exposes them, but it does not change clocks or power limits.
On H100/HGX-class systems, keep GPU power, module power, and GPU memory power
readings separate. The current component coefficients use NVML GPU/device total
energy deltas where available, not module-level or memory-subsystem-only power.
Across GPU generations, `nvmlDeviceGetPowerUsage` is not a uniform energy
source: V100/A100 profiles treat it as instantaneous power, while RTX 3090/H100
profiles treat it as one-second average power. It is therefore only a fallback
or diagnostic path in this repository; final component coefficients require the
NVML total-energy mJ counter whenever the runtime exposes it.

## CLI Examples

Feasibility only:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_scalar_load_only \
  --w-sm-kib 64 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --dry-run
```

Supported target profiles:

| profile | GPU family | CC | default SMs | L2 | combined L1/shared | shared allocation | max shared/block | max blocks/SM | NVML `GetPowerUsage` meaning |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `v100` | Volta GV100 | 7.0 | 80 | 6 MiB | 128 KiB/SM | 96 KiB/SM | 96 KiB/block | 32 | instantaneous |
| `rtx3090` | Ampere GA10x | 8.6 | 82 | 6 MiB | 128 KiB/SM | 100 KiB/SM | 99 KiB/block | 16 | 1-second average (`one_sec_average`) |
| `a100` | Ampere GA100 | 8.0 | 108 | 40 MiB | 192 KiB/SM | 164 KiB/SM | 163 KiB/block | 32 | instantaneous |
| `h100` | Hopper GH100 | 9.0 | 132 default, runtime/SKU should be checked | 50 MiB | 256 KiB/SM | 228 KiB/SM | 227 KiB/block | 32 | 1-second average (`one_sec_average`) |

`combined L1/shared` is the SM-local unified capacity. `shared allocation`
is the CUDA shared-memory capacity used for feasibility checks. Do not treat
these two columns as the same quantity.
The NVML power column is only the meaning of `nvmlDeviceGetPowerUsage`; final
energy runs prefer `nvmlDeviceGetTotalEnergyConsumption` when the runtime device
supports it. See `docs/platforms/power_measurement_api_matrix_ko.md` for the
full API matrix and reporting rules.

Power measurement acceptance:

| status | required metadata |
|---|---|
| final candidate | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, explicit `measurement_scope=gpu_device_total_energy_counter`, expected `nvml_power_usage_semantics` |
| provisional only | `energy_source=legacy_get_power_usage_integral` or missing total energy counter |
| reject for coefficient | mixed energy sources, wrong profile power semantics, non-GPU/device measurement scope, or missing NCU path validation |

Across RTX 3090, V100, A100, and H100, do not infer final energy validity from
GPU name alone. Check the raw CSV metadata and the power API matrix. The final
numerator is the NVML GPU/device total-energy mJ delta when available;
`GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power are
fallback or metadata scopes with different meanings.
For new finalplan runs, run `scripts/audit_power_api_measurements.py` with
`--require-explicit-measurement-scope --require-exact-measurement-interval`.
Historical rows whose scope or timed-kernel interval can only be
inferred from source/integration should be reported as legacy/inferred-scope
evidence, not strict cross-platform final evidence.
Matched-control analysis can also take a power-state audit CSV; rows marked
`status=reject` or `coefficient_eligible=false` are excluded from coefficient
pairing when `--exclude-power-state-rejects` is used.
The audit and raw rows are joined by `(sweep_source_id, run_id, gpu_id)`, and
pairing is isolated by input sweep CSV. Equal-coordinate `global_addr_only`
rows from the L1, L2, and DRAM sweeps are therefore not interchangeable.

Run a support preflight before collecting new data:

```bash
python3 scripts/audit_platform_power_readiness.py \
  --out-csv results/summary/platform_power_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/platform_power_readiness_audit_YYYYMMDD.md
```

This readiness audit checks static consistency across RTX 3090, V100, A100, and
H100 profiles. It does not replace node-local power API, NCU, or reliability
audits.

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto \
  --ncu /path/to/ncu \
  --nvcc /path/to/nvcc \
  --out results/summary/gpu_support_preflight.md
```

The preflight records the detected profile, combined/shared capacity metadata,
NVML/NVIDIA driver state, CUDA compiler target support, Nsight Compute chip
support, and a binary dry-run result.
For final A100/V100/H100 command packages, use the generated script. It runs
preflight with an explicit `--target-profile <profile> --strict`, so a wrong GPU,
missing CUDA compiler/NCU target support, or failed binary dry-run stops before
energy collection.
Returned platform packages are accepted only when the preflight markdown records
`strict=true`, `profile_gate=pass`, `cuda_compiler_gate=pass`, `ncu_gate=pass`,
`dry_run_gate=pass`, `overall=pass`, and `errors=none`. A non-strict, warning-only, or failed
preflight is treated as an intake failure even if the later CSV files exist.

Single GPU Tensor Core treatment/control sanity run:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_operand_only \
  --w-sm-kib 1 \
  --blocks-per-sm 8 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_fp16_energy_v2_raw.csv

./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 1 \
  --blocks-per-sm 8 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_fp16_energy_v2_raw.csv
```

L2 and DRAM path examples:

```bash
./build/a100_fp16_energy_v2 --gpu-list 0 --mode l2_cg_load_only \
  --w-sm-kib 32 --blocks-per-sm 8 --target-profile rtx3090 --active-sm 82 --seconds 10

./build/a100_fp16_energy_v2 --gpu-list 0 --mode dram_cg_load_only \
  --w-sm-kib 2048 --blocks-per-sm 8 --target-profile rtx3090 --active-sm 82 --seconds 10
```

Idle baseline with zero active GPUs:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list none --mode idle --w-sm-kib 1 --blocks-per-sm 1 \
  --target-profile rtx3090 --active-sm 82 --seconds 10 --repeats 5
```

## Modes

The binary still supports several historical and diagnostic modes, but the
current component-energy claim should be based on the acceptance-first finalplan
subset below.

Primary finalplan modes:

| component/path | treatment mode | control mode | why it is used |
|---|---|---|---|
| Tensor MMA increment | `reg_mma` | `reg_operand_only` | RF별 treatment 목표와 control 최소시간을 각각 calibration하고 두 ITER 중 큰 값을 두 mode에 동일 적용한 뒤 direct net-energy 차분으로 extra WMMA/HMMA work를 추정 |
| Shared scalar path | `shared_scalar_load_only` | `shared_scalar_addr_only` | same dynamic-shared allocation/init/index/checksum shape, equal ITER, direct net-energy difference; NCU must show treatment read traffic and no repeated control reads |
| Global L1 hit path | `global_l1_load_only` | `global_addr_only` | same address/tile/repeat control, equal ITER, direct net-energy difference; NCU must show L1-hit-dominated traffic |
| L2 hit path | `l2_cg_load_only` | `global_addr_only` | uses cache-global loads to reduce L1 participation and target L2-hit traffic |
| L2 capacity diagnostic | `l2_load_only` | none | normal global-load diagnostic; excluded from strict L2 coefficient because it can hit L1 |
| External-memory read path | `dram_cg_load_only` | `global_addr_only` | identical ITER, architecture-specific W sweep, strict NCU `dram__bytes_read.sum`; effective GPU-device path, not physical HBM/GDDR energy |

Final platform packages pass `--require-control-ncu-acceptance`. Consequently,
`reg_operand_only`, `shared_scalar_addr_only`, and `global_addr_only` must have an accepted NCU row at the
same `W_SM`, blocks/SM, active-SM, and RF/LR coordinate as the treatment. A
clean treatment row is insufficient when its subtraction control is unverified.

Control and diagnostic modes:

| mode | status | purpose |
|---|---|---|
| `idle` | support | no kernel; records NVML energy delta during sleep |
| `empty` | diagnostic | same grid shape, persistent loop, no MMA; older control, not the final matched-control default |
| `clocked_empty` | baseline/diagnostic | clocked scheduler/control loop; no longer the Shared final subtraction control |
| `shared_scalar_addr_only` | primary Shared control | same shared allocation, initialization, tile/index loop, and checksum dependency as the Shared treatment without repeated shared loads |
| `global_addr_only` | primary global-memory control | same global address/tile/repeat/checksum loop without an input load |
| `reg_fragment_only` | diagnostic | WMMA fragment/register setup without MMA |
| `reg_operand_only` | primary control | declares the same A/B/C fragments, dependent scalar update, in-place A-sign flip, and source epilogue but issues no MMA; ptxas reduces it to fewer registers than treatment, so it is a lightweight no-MMA control rather than a register-footprint-matched pure Tensor control |
| `reg_resident_stall_no_mma` | experimental diagnostic | keeps extra registers live and inserts sparse `nanosleep` to study a low-issue resident-stall counterfactual; not selected by the v3 package |
| `reg_issue_dependency_no_mma` | experimental diagnostic | adds dependent integer issue work and register padding to study issue-rate matching; its non-Tensor ALU energy prevents direct use as a pure Tensor control |
| `reg_scheduler_matched_no_mma` | experimental diagnostic | uses a dependent FP32 scheduler proxy; it intentionally consumes FP32 ALU energy and is not the standard v3 no-MMA control |
| `reg_pressure` | diagnostic | scalar register-pressure payload sweep; do not report as pure register-file energy |
| `addr_only` | diagnostic | global-memory tile address walk without issuing operand loads |
| `shared_load_only` | diagnostic | shared WMMA operand loads without MMA; useful for NCU comparison, not primary coefficient |
| `shared_mma` | legacy/diagnostic | shared operand load plus MMA; useful for old sweep continuity, not primary coefficient |
| `l2_mma` | legacy/diagnostic | global L2-candidate operand load plus MMA; not primary coefficient |
| `dram_load_only` | diagnostic | non-CG DRAM candidate; cache behavior must be checked carefully |
| `dram_mma` | legacy/diagnostic | streaming global operand load plus MMA; not primary coefficient |
| `store_only` | diagnostic | repeated global store loop |
| `store_path` | diagnostic | output-side store overhead check |

`shared_mma` is not an A100-only concept. On RTX 3090 / Ampere GA102 it means
the operands are staged through CUDA shared memory and loaded into WMMA
fragments from the shared-memory address space. The physical L1/shared-memory
organization and limits differ from A100, so feasibility uses the RTX 3090
profile values rather than the A100 164 KiB shared/L1 budget.
The same interpretation applies to V100 and H100, but with their own profile
limits.

Invalid combinations fail before execution. The shared/L2/DRAM classification is
the design rule:

- `invalid_min_tile`: `W_SM_KiB < blocks_per_SM`. This applies to both a
  memory treatment and its `global_addr_only` matched control.
- `shared_resident`: `W_SM + B KiB <= profile shared KiB` and
  `W_SM/B <= profile max shared/block KiB`.
- `l2_candidate`: runtime active-SM working set fits the nominal profile L2
  (`active_SM * W_SM <= L2`).
- `dram_mixed_streaming`: runtime active-SM working set exceeds nominal profile L2.

The matrix CSV retains invalid rows with `valid=false`, but the runner does not
execute them. With `--execute`, it first sends every unique valid coordinate to
the binary with `--dry-run`; an unexpected Python/C++ feasibility mismatch is
reported before any energy command starts. Generated strict profiles only use
coordinates with at least 1 KiB/block; broader user overrides remain subject to
this gate.

## Sweep

Materialize the design matrix without executing:

```bash
python3 scripts/run_sweep.py --include-idle
```

Run the matrix:

```bash
python3 scripts/run_sweep.py \
  --include-idle \
  --execute \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --seconds 10 \
  --repeats 5
```

For short sanity runs, constrain the matrix:

```bash
python3 scripts/run_sweep.py --execute \
  --gpu-ids 0 \
  --modes shared_scalar_addr_only,shared_scalar_load_only \
  --w-sm-kib-values 32,64 \
  --blocks-per-sm-values 8,16 \
  --active-sm-values 82 \
  --seconds 2 \
  --repeats 1
```

위 명령은 kernel smoke test다. 최종 Shared coefficient는
`run_component_regression_sweep.py --memory-pair-lock-iters`로 두 mode의 ITER를 같게
만든 뒤 계산한다.

Component-decomposition now uses an acceptance-first finalplan flow for primary
results. Generate a platform-specific command plan, run energy sweeps without
NCU attached, run NCU sidecar validation separately, classify accepted paths,
then analyze matched controls with NCU byte-denominator scaling:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5

bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

Use `--target-profile v100` or `--target-profile h100` on those platforms.
Review the generated shell script before submitting a long cluster job. Final
byte-path claims must use `scripts/analyze_ncu_path_acceptance.py` and
`scripts/analyze_matched_control_energy.py --require-ncu-denominator`.

For a supplemental byte-variation stress test, the active regression runner can
bypass per-mode calibration and use fixed `ITER`:

```bash
python3 scripts/run_component_regression_sweep.py \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --modes shared_scalar_load_only,global_l1_load_only,l2_cg_load_only,dram_cg_load_only \
  --w-sm-kib-values 64,8192 \
  --blocks-per-sm-values 16 \
  --active-sm-values 82 \
  --reuse-factors 1 \
  --load-repeats 1,2,4,8 \
  --store-repeats 1 \
  --seconds 1 \
  --iters 1000000 \
  --repeats 1 \
  --execute
```

Fixed-ITER runs make logical bytes vary directly, but elapsed can spread widely.
Use them to check monotonicity and model identifiability, not as final physical
pJ/byte values without NCU traffic and stall validation.

## Legacy Archive

Older pair-centric, NNLS/regression, reference-aligned, and register-footprint
diagnostic flows were moved out of the active `scripts/` and `docs/` directories
to reduce confusion. They remain available for historical comparison under:

```text
archive/legacy_20260707/
```

Do not use archived scripts for new component-energy claims unless the report
explicitly labels them as legacy diagnostics. The current implementation path is the
acceptance-first finalplan flow above.

## Nsight Compute

Energy runs and NCU profiling runs are intentionally separate.

```bash
scripts/run_ncu.sh --query-metrics

MODE=shared_scalar_load_only W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 \
  scripts/run_ncu.sh

MODE=dram_cg_load_only W_SM_KIB=8192 BLOCKS_PER_SM=16 CACHE_CONTROL=all \
  scripts/run_ncu.sh
```

NCU reports are written under `results/ncu/`. The raw energy CSV includes NCU
columns, initialized to zero; populate or join those columns from NCU exports
before using the NCU bytes/op visualization.
`scripts/run_ncu.sh` and `scripts/run_ncu_validation.sh` also export raw/details
NCU CSV files and generate cache summaries. `run_ncu_validation.sh` profiles
only the primary finalplan modes by default; set `INCLUDE_DIAGNOSTIC_NCU=1` to
also collect legacy/diagnostic modes such as `shared_mma`, `l2_mma`, and
`dram_mma`. The summary table includes aggregate and path-specific L1/L2 hit
rates (%), L1 request/hit/miss bytes, L2 read hit/miss sectors and bytes,
L1 accesses, L2 accesses (sectors), DRAM accesses (sectors), and DRAM bytes.
L1 accesses prefer request counters when NCU provides them and fall back to
sector counters otherwise.

For `ld.global.cg`, L1 request bytes are expected because the request traverses
L1TEX. They are not L1 cache-hit bytes. Strict L2 acceptance therefore checks
near-zero path-specific L1 hit bytes instead of requiring total L1 request bytes
to be near zero. GA100 additionally combines source/TEX and LTC-fabric lookup
hit/miss counters: its >=95% requirement applies to logical final-service L2 hit,
while direct and native lookup-level percentages are reported with their distinct
denominators.
The timed CG paths are preceded by an `ld.global.cg` warm-up kernel rather than
a normal cached-load warm-up, avoiding pre-population of L1 by the harness.

Nsight Compute support is version dependent. As of the 2026-06-29 release
history, NVIDIA lists Nsight Compute 2026.2.1 as the latest public release, and
the release highlights announce dropped Volta support. The reviewed V100
baseline uses Nsight Compute 2024.3 as the confirmed GV100 reference and still
requires both `--list-chips` and `--query-metrics --chips gv100` to succeed.

## Plotting

```bash
python3 scripts/plot_results.py results/raw/a100_fp16_energy_v2_raw.csv \
  --outdir results/plots
```

Generated plots include:

- energy vs active GPU count
- energy vs active SM count
- pJ/FLOP vs blocks/SM
- pJ/FLOP vs `W_SM`
- pJ/input-bit vs `W_SM`
- NCU shared/L2/DRAM bytes per logical op vs `W_SM`
- feasibility heatmap
- regression residual plot when `predicted_E_J` exists in the CSV

현행 RTX 3090 coefficient 및 NCU access/byte/stall 그림은 accepted summary에서
직접 다시 생성한다.

```bash
python3 scripts/plot_current_rtx3090_results.py --self-test
python3 scripts/plot_current_rtx3090_results.py --tag 20260714
```

## CSV Notes

Rows are per GPU. For multi-GPU runs, active GPU rows use per-GPU operation
counts:

```text
N_MMA = active_SM * blocks_per_SM * ITER
FLOP = N_MMA * 8192
input_bits = N_MMA * 8192
```

Aggregate multi-GPU energy by summing active rows with the same `run_id`. Inactive
GPU rows are still emitted so idle drift and system-side effects remain visible.
`gpu_id` is the physical CUDA/NVML device index, not a repeat index. If
`--gpu-list`/`--gpu-ids` is omitted, the binary and Python runners select GPU 0.
Power-state evidence uses `(sweep_source_id, run_id, gpu_id)` so an inactive
device row cannot overwrite the selected device's audit status.

For non-idle modes the binary performs a pre-run idle measurement and stores an
elapsed-time-scaled `idle_baseline_J`. `net_E_J = delta_E_J - idle_baseline_J`.

## Current Limitations

- WMMA fallback is implemented; raw inline PTX `m16n8k16` and explicit
  `ldmatrix.shared` are future refinements.
- SM placement uses soft control (`grid = active_SM * blocks_per_SM`) plus SMID
  histogram validation. Runs with `smid_histogram_ok=false` should be excluded
  from primary analysis.
- Reported coefficients are effective microbenchmark coefficients, not pure
  physical component energies. Prefer labels such as `effective Tensor Engine +
  register`, `effective shared/L1 path`, `effective L2-hit path`, and `effective
  DRAM streaming path`.
- Do not report `*_load_only - empty` pair coefficients as physical component
  energy unless elapsed-time matching and NCU traffic validation pass. Large
  elapsed ratios or negative `*_mma - *_load_only` coefficients mean the pair is
  diagnostic-only.
- Current final packages require pair-locked identical ITER for Tensor and every
  final memory pair: Shared scalar, Global L1, L2 CG, and external-memory CG.
  The planner uses matched-ITER pair policies and analyzer hard gates; a
  duration-scaled row or `iter_ratio != 1` is rejected even when NCU shows the
  intended path.

## Included Reference Assets

- Original v2 design and feasibility assets:
  `archive/superseded_v2_design_20260714/`
- Pre-current-protocol coefficient/sweep visualizations:
  `archive/pre_current_protocol_20260712/docs/assets/component_energy_method/`
