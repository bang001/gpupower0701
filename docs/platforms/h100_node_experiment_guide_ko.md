# H100 노드 실험 실행 가이드

External-memory 결과의 최신 명칭, read-only NCU 분모와 W sweep은
[External-Memory Read-Path 설계](../methodology/external_memory_read_path_experiment_design_ko.md)를 우선 적용한다.

작성일: 2026-07-08, updated 2026-07-15

## 목적

이 문서는 H100/GH100 노드에서 FP16 Tensor Core energy microbenchmark와 component-energy finalplan 실험을 실행하기 위한 가이드다. 기본 profile은 **H100 SXM5, 132 SM, 50 MiB L2, HBM3** planning profile이며 H100 PCIe 결과에는 그대로 쓰지 않는다. 현재 코드의 primary Tensor path는 CUDA WMMA compatibility path다. 따라서 H100에서 실행하더라도 이 결과는 **Hopper-native WGMMA/TMA/FP8 에너지**가 아니라, H100에서의 WMMA 기반 effective microbenchmark coefficient다.

## H100 기준 profile

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU profile | `h100` | - |
| architecture | Hopper GH100 | - |
| compute capability | 9.0 | - |
| CUDA arch flag | `sm_90` | - |
| default full SM count | 132 | SMs |
| nominal L2 | 50 | MiB |
| combined L1/shared profile | 256 | KiB/SM |
| shared allocation profile | 228 | KiB/SM |
| max dynamic shared memory per block | 227 | KiB/block |
| max resident blocks per SM | 32 | blocks/SM |
| NCU chip alias | `gh100` | - |
| NVML `GetPowerUsage` 의미 | one-second average로 기록 | mW |

주의:

- H100 SXM/PCIe, H800, MIG, 클러스터 partition에 따라 runtime SM 수와 memory 구성이 달라질 수 있다.
- preflight에서 runtime SM 수가 132가 아니면 `--active-sm`을 runtime 값으로 바꾼다.
- 현재 harness profile의 50 MiB L2는 기본 가이드 값이다. SKU별 L2가 다르면 결과 보고서에 runtime/profile 차이를 명시한다.
- `combined L1/shared profile`은 SM 내부 통합 capacity이고, `shared allocation profile`은 shared-memory 실험 feasibility에 쓰는 CUDA shared capacity다.
- Power 측정은 [power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)를 따른다. H100/GH100에서는 `GetPowerUsage`를 one-second average로 기록하고, Hopper datacenter 제품에서 보일 수 있는 module power와 GPU power를 같은 coefficient 표에 섞지 않는다. 최종 energy numerator는 가능하면 `nvmlDeviceGetTotalEnergyConsumption` mJ counter 차분을 우선한다.

H100 결과를 채택할 때는 아래 gate를 적용한다.

| 항목 | 채택 기준 |
|---|---|
| final numerator | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy` |
| integration method | `total_energy_mj_delta` |
| fallback | `GetPowerUsage` one-second average endpoint 적분은 provisional만 허용 |
| profile semantics | `nvml_power_usage_semantics=one_sec_average` |
| measurement scope | `measurement_scope=gpu_device_total_energy_counter` |
| power scope | GPU/device power, module power, GPU memory power를 같은 coefficient numerator에 섞지 않음 |

## 1. 저장소 준비

```bash
git clone https://github.com/bang001/gpupower0701.git
cd gpupower0701
git pull
```

이미 checkout이 있으면 `git pull`만 실행한다.

## 2. 노드 preflight

```bash
nvidia-smi -L
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
nvidia-smi -q -d POWER,CLOCK,TEMPERATURE
nvidia-smi -q | grep -i -E "Product Name|MIG|Compute Mode|FB Memory|BAR1|Power Limit|Module Power|GPU Power"
```

가능하면 persistence mode를 켠다.

```bash
sudo nvidia-smi -pm 1
```

preflight script:

```bash
python3 scripts/preflight_gpu_support.py \
  --gpu 0 \
  --target-profile h100 \
  --strict \
  --active-sm 132 \
  --ncu "$(command -v ncu)" \
  --out results/summary/h100_gpu0_preflight.md
```

runtime SM 수가 132가 아니면 위 `--active-sm`을 preflight에서 확인한 값으로 바꾸고,
이후 generated command plan과 package audit의 `--expected-active-sm`도 같은 값으로
맞춘다.

확인 항목:

| 항목 | 기대 |
|---|---|
| detected profile | `h100` |
| compute capability | `9.0` |
| selected CUDA arch | `90` |
| dry-run GPU | `dry_run_gpu: 0` 또는 preflight `--gpu`와 같은 index |
| dry-run active SM | `dry_run_active_sm: 132`, SKU/partition이면 runtime SM 수 |
| NCU chip | `gh100` |
| binary dry run | `return_code: 0` |

## 3. 빌드

```bash
cmake -S . -B build-h100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=90

cmake --build build-h100 --clean-first -j
```

CUDA toolkit 경로를 명시해야 하는 환경:

```bash
cmake -S . -B build-h100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/path/to/nvcc \
  -DCUDAToolkit_ROOT=/path/to/cuda \
  -DCMAKE_CUDA_ARCHITECTURES=90

cmake --build build-h100 --clean-first -j
```

빌드 로그에서 ptxas register count와 spill을 확인한다. 주요 kernel에서 spill이 발생하면 component coefficient 후보에서 제외하거나 별도 위험으로 표시한다.
`git pull` 후 `src/`, `include/`, `CMakeLists.txt`가 바뀐 경우에는 반드시 clean rebuild를 한다.
특히 final run raw CSV는 C++ harness의 CSV header에 `measurement_scope` 컬럼이 있는
바이너리로 생성되어야 한다.

## 4. Dry-run sanity

```bash
./build-h100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 2048 \
  --blocks-per-sm 16 \
  --target-profile h100 \
  --active-sm 132 \
  --dry-run
```

shared path:

```bash
./build-h100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_scalar_load_only \
  --w-sm-kib 128 \
  --blocks-per-sm 32 \
  --target-profile h100 \
  --active-sm 132 \
  --dry-run
```

L2 capacity path:

```bash
./build-h100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode l2_load_only \
  --w-sm-kib 256 \
  --blocks-per-sm 16 \
  --target-profile h100 \
  --active-sm 132 \
  --dry-run
```

`W_SM=256 KiB`이면 132 SM 기준 full working set이 약 33 MiB라 50 MiB L2 후보가 된다. 그래도 최종 채택은 NCU hit/access 결과로 판단한다.

## 5. Smoke run

```bash
./build-h100/a100_fp16_energy_v2 \
  --gpu-list none \
  --mode idle \
  --w-sm-kib 1 \
  --blocks-per-sm 1 \
  --target-profile h100 \
  --active-sm 132 \
  --seconds 1 \
  --repeats 1 \
  --output results/raw/h100_smoke_idle.csv
```

```bash
./build-h100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 2048 \
  --blocks-per-sm 16 \
  --target-profile h100 \
  --active-sm 132 \
  --seconds 1 \
  --repeats 1 \
  --reuse-factor 2 \
  --output results/raw/h100_smoke_reg_mma.csv \
  --verify-smid 1
```

확인:

| 컬럼 | 기대 |
|---|---|
| `profile_name` | `h100` |
| `compute_capability` | `9.0` |
| `energy_source` | `nvml_total_energy` 우선 |
| `measurement_scope` | `gpu_device_total_energy_counter` |
| `nvml_power_usage_semantics` | `one_sec_average` |
| `smid_histogram_ok` | active row에서 `true` |

schema smoke audit:

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/h100_smoke_reg_mma.csv \
  --target-profile h100 \
  --out-csv results/summary/h100_smoke_power_api_audit.csv \
  --out-md results/summary/h100_smoke_power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope \
  --require-exact-measurement-interval \
  --require-mode-notes-marker \
  reg_mma=tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6
```

이 단계에서 모든 row가 `missing_column:measurement_scope` 또는
`missing_explicit_measurement_scope`로 reject되면, H100 power scope 문제가 아니라
stale binary/schema 문제다. 현재 source를 pull한 뒤 `cmake --build build-h100
--clean-first -j`로 다시 빌드하고, 기존 `results/raw/h100_component_finalplan_*.csv`는
archive로 옮긴 뒤 재실행한다. 구버전 CSV에 새 row를 append하면 power API audit이
전체 reject될 수 있다.

`matched_runtime_clock_observed_control_fixed_rf_v6`는 RF1/2/4/8/16 모두 fixed-trip
`unroll 1` kernel을 사용하고 한 A fragment의 sign bit를 in-place로 뒤집어
accumulator를 bounded 상태로 유지한다. Treatment/control의 inner step에 공통
`SR_CLOCKLO` token을 소비해 launch-only control을 막는다. Hopper에서의 lowering을
Ampere와 같다고 가정하지 않으며 H100 NCU에서 RF별
predicated HMMA=0, `HMMA/logical MMA` 상대 spread<=10%, control HMMA=0을 다시 확인한다. 이 검사는 여전히
WMMA compatibility path 검증이며 Hopper-native WGMMA 검증은 아니다. Static binary
audit에서 treatment/control runtime-token backward loop를 확인하고 runtime NCU에서
`SASS instructions/expected register op >= 0.1`도 통과해야 한다. 이 gate가 없던 v4
Tensor energy 결과는 재사용하지 않는다.
Pair calibration trial 각각 `>=0.05 s`, control/treatment ITER ratio `<=6`, 개별
command `<=180 s`를 통과한 실행만 채택한다.

## 6. Component finalplan 실행

표준 명령 생성:

`--gpu-ids`를 생략하면 GPU 0을 사용한다. 다른 GPU를 쓰는 경우에만 물리
CUDA/NVML index를 명시한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile h100 \
  --binary ./build-h100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --active-sm 132 \
  --seconds 10 \
  --repeats 5
```

생성된 script를 검토한 뒤 실행:

```bash
bash results/summary/h100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

멀티 GPU raw에서 같은 `run_id`의 inactive GPU 행은 repeat가 아니다. 현행
power-state/matched-control 경로는 `(sweep_source_id, run_id, gpu_id)` 복합키와
sweep별 pairing 격리를 사용한다. 따라서 L1/L2/DRAM의 동일 좌표 control이 서로
혼합되지 않으며, 이 identity 열이 없는 구형 audit은 재생성해야 한다.

기본 좌표:

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | N/A (CLI placeholder 1) | 4,16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `shared_scalar_addr_only,shared_scalar_load_only` | 128 | 16 | energy/NCU load_repeat 4,8,16; 동일 pair ITER |
| Global L1 | `global_addr_only,global_l1_load_only` | 16 | 16 | energy/NCU load_repeat 4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 64,128 | NCU가 B16/B8 중 선택 | energy/final NCU load_repeat 4,8,16; selector는 LR4 |
| External-memory read path | `global_addr_only,dram_cg_load_only` | 2048,4096,8192 | 16 | energy/NCU load_repeat 4,8,16 |

### H100 sweep를 그래프로 해석하기

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

- Shared W128/B16의 보수적 예약량은 144 KiB/SM이며 energy와 NCU가 동일 좌표다.
- Global L1 W16/B16은 block당 1 KiB를 제공하는 단일 cached-global anchor다.
- L2 W64/W128은 전체 8.25/16.5 MiB로 50 MiB L2의 약 16.5/33%다. A100처럼 더 작은
  W를 포함하지 않은 것은 current heuristic이며 두 endpoint의 target-node NCU plateau 검증이 필요하다.
- External-memory W2048/4096/8192는 전체 약 264/528/1,056 MiB다. HBM3 physical
  energy가 아니라 effective GPU-device read path로 해석한다.

이 132-SM, 50-MiB L2, HBM3 좌표는 H100 SXM5 planning profile이다. H100 PCIe는
runtime SM 수와 memory subsystem을 기록하고 별도 profile/result label로 재계획해야 한다.
현재 H100 좌표가 WGMMA/TMA용으로 별도 최적화된 것은 아니다. kernel은 FP16 WMMA
compatibility path이며, WGMMA/TMA energy를 주장하려면 별도 kernel과 NCU instruction
evidence가 필요하다.

현행 분석은 `--require-control-ncu-acceptance`를 사용한다. H100에서도
`reg_operand_only`와 `global_addr_only`가 treatment와 동일 좌표에서 NCU
accepted여야 한다. 이 gate는 WMMA compatibility path의 control 검증이며 WGMMA/TMA
지원 여부를 검증하는 것은 아니다.

GH100도 partitioned L2 crossbar를 사용하므로 L2 selector와 final minimal replay는
source/TEX 첫 lookup에 `srcunit_ltcfabric` hit를 더한 logical final service를 검증한다.
필수 fabric counter가 NCU에서 제공되지 않으면 direct hit rate로 대체하지 않고 L2를
reject한다. L2 CG energy sweep는 각 W/B/LR 좌표에서 `l2_cg_load_only` treatment와
`global_addr_only` control을 dual-calibrate하고 동일 resolved ITER를 양쪽에 전달한다.
분석은 `--l2-pair-policy matched-iters`로 net energy를 직접 차분한다.
`*_l2_pair_calibration.csv`, raw ITER equality, `pair_energy_basis=matched_iters_net_energy`,
`iter_ratio=1`이 필수다. 이는 NCU L2-hit acceptance와 별개의 작업량 정합성 gate다.

External-memory energy sweep는 mode별 duration calibration을 사용하지 않는다. 각 W/B/LR
좌표에서 treatment와 address control을 dual-calibrate하고 동일한 resolved ITER를
`dram_cg_load_only`와 `global_addr_only`에 전달한다. 분석은
`--dram-pair-policy matched-iters`와 direct net-energy subtraction을 사용한다.
`*_dram_pair_calibration.csv`, raw ITER equality, `pair_energy_basis=matched_iters_net_energy`,
`iter_ratio=1`이 H100 external-memory path의 필수 gate다. 분모는 strict NCU
`dram__bytes_read.sum`이다. 이 값도 HBM3 device 단독
에너지가 아니라 Hopper GPU/device-level effective streaming-path coefficient다.

## 7. NCU validation

H100은 NCU chip alias가 `gh100`이다.

```bash
NCU="$(command -v ncu)" NCU_CHIP=gh100 scripts/run_ncu.sh --query-metrics
```

대표 validation은 생성된 command script 안에 포함된다. 수동 실행 예시는 다음과 같다.

```bash
NCU_EXPLICIT_METRICS_ONLY=1 \
NCU="$(command -v ncu)" \
BIN=./build-h100/a100_fp16_energy_v2 \
TARGET_PROFILE=h100 \
ACTIVE_SM=132 \
GPU=0 \
BLOCKS_PER_SM=16 \
REG_BLOCKS_PER_SM=16 \
REG_W_SM_KIB=1 \
L1_W_SM_KIB=16 \
SHARED_W_SM_KIB=128 \
L2_W_SM_KIB_VALUES=64,128 \
DRAM_W_SM_KIB_VALUES=2048,4096,8192 \
REUSE_FACTOR=1 \
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=4,8,16 \
DRAM_LOAD_REPEATS=4,8,16 \
OUTDIR=results/ncu/h100_component_finalplan_ncu_factor_$(date +%Y%m%d) \
RAW_OUT=results/raw/h100_component_finalplan_ncu_factor_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

권한 문제가 있으면 다음 오류가 날 수 있다.

```text
ERR_NVGPUCTRPERM
```

Generated package는 energy sweep 전에 hardware-counter permission probe를 수행하고,
기본 `NCU_AUTO_SUDO=1`에서 이 오류가 나오면 같은 case를 `sudo -E`로 한 번 재시도한다.
관리자가 performance counter 접근을 허용하는 것이 장기적으로 가장 좋다. 처음부터
sudo를 사용하려면 다음처럼 실행한다.

```bash
NCU_USE_SUDO=1 bash results/summary/h100_component_finalplan_20260716_commands.sh
```

수동 NCU validation만 다시 돌릴 때는 기존 명령에 `NCU_USE_SUDO=1`을 붙인다.

```bash
NCU_USE_SUDO=1 \
NCU="$(command -v ncu)" \
BIN=./build-h100/a100_fp16_energy_v2 \
TARGET_PROFILE=h100 \
ACTIVE_SM=132 \
GPU=0 \
BLOCKS_PER_SM=16 \
REG_BLOCKS_PER_SM=16 \
REG_W_SM_KIB=1 \
L1_W_SM_KIB=16 \
SHARED_W_SM_KIB=128 \
L2_W_SM_KIB_VALUES=64,128 \
DRAM_W_SM_KIB_VALUES=2048,4096,8192 \
REUSE_FACTOR=1 \
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=4,8,16 \
DRAM_LOAD_REPEATS=4,8,16 \
OUTDIR=results/ncu/h100_component_finalplan_ncu_factor_$(date +%Y%m%d) \
RAW_OUT=results/raw/h100_component_finalplan_ncu_factor_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

`sudo`가 CUDA/Nsight Compute 경로를 지우는 환경이면 generated package에는
`NCU_BIN="$(command -v ncu)" NCU_SUDO="sudo -E"`를 같이 지정하고, 수동
`run_ncu_validation.sh`에는 `NCU="$(command -v ncu)" NCU_SUDO="sudo -E"`를 같이
지정한다. NCU가 실패해도 NVML energy run 자체와 섞지 말고, 보고서에는
“NCU counter 검증 미완료”로 분리 기록한다.

Acceptance:

```bash
python3 scripts/analyze_ncu_path_acceptance.py \
  results/ncu/h100_component_finalplan_ncu_factor_$(date +%Y%m%d)/ncu_cache_validation_summary.csv \
  --out-csv results/summary/h100_component_finalplan_ncu_acceptance_$(date +%Y%m%d).csv \
  --out-md results/summary/h100_component_finalplan_ncu_acceptance_$(date +%Y%m%d).md \
  --tensor-memory-bytes-max 4e8 \
  --register-memory-bytes-max 4e8 \
  --tensor-memory-bytes-per-hmma-max 1.0 \
  --register-memory-bytes-per-op-max 1.0
```

## 8. 결과 해석

H100 보고서에는 다음 문구를 반드시 포함한다.

```text
This run uses the repository's WMMA compatibility kernels on H100.
It does not isolate Hopper-native WGMMA, TMA, or FP8 Tensor Core energy.
Reported coefficients are board-level effective microbenchmark coefficients.
```

필수 표:

| 표 | 필수 열 |
|---|---|
| architecture | GPU, CC, runtime SMs, L1/shared (KiB), L2 (MiB), memory type |
| sweep | mode, W_SM (KiB), blocks/SM, active_SM (SM), seconds (s), repeats |
| NCU | L1 hit (%), L2 hit (%), L1/L2/DRAM access counts, shared bytes (B), L1/L2/DRAM bytes (B), stall_long_scoreboard (%) |
| coefficients | component, median, min, max, unit, rows used, invalid rows, status |
| rejected rows | mode, reason, decision |

## 9. 빠른 체크리스트

| 단계 | 확인 |
|---|---|
| preflight | `detected profile=h100`, CC 9.0, runtime SM 수 확인 |
| build | `CMAKE_CUDA_ARCHITECTURES=90`, spill 확인 |
| dry-run | `reg_mma`, `shared_scalar_load_only`, `l2_cg_load_only` allowed 여부 |
| smoke | `energy_source`, `smid_histogram_ok` 확인 |
| finalplan | generated command script 검토 후 실행 |
| NCU | `gh100` metrics 수집, acceptance report 생성 |
| report | WMMA compatibility limitation 명시 |
