# H100 노드 실험 실행 가이드

작성일: 2026-07-08

## 목적

이 문서는 H100/GH100 노드에서 FP16 Tensor Core energy microbenchmark와 component-energy finalplan 실험을 실행하기 위한 가이드다. 현재 코드의 primary Tensor path는 CUDA WMMA compatibility path다. 따라서 H100에서 실행하더라도 이 결과는 **Hopper-native WGMMA/TMA/FP8 에너지**가 아니라, H100에서의 WMMA 기반 effective microbenchmark coefficient다.

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
  --require-explicit-measurement-scope
```

이 단계에서 모든 row가 `missing_column:measurement_scope` 또는
`missing_explicit_measurement_scope`로 reject되면, H100 power scope 문제가 아니라
stale binary/schema 문제다. 현재 source를 pull한 뒤 `cmake --build build-h100
--clean-first -j`로 다시 빌드하고, 기존 `results/raw/h100_component_finalplan_*.csv`는
archive로 옮긴 뒤 재실행한다. 구버전 CSV에 새 row를 append하면 power API audit이
전체 reject될 수 있다.

## 6. Component finalplan 실행

표준 명령 생성:

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

기본 좌표:

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 64,128 | 16,32 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 |
| Global L1 | `global_addr_only,global_l1_load_only` | 16,32 | 16,32 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 64,128 | 16,32 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | 16,32 | energy load_repeat 4,8,16; NCU 1,4,8,16 |

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
REG_W_SM_KIB=2048 \
L1_W_SM_KIB=16 \
SHARED_W_SM_KIB=128 \
L2_W_SM_KIB=64 \
DRAM_W_SM_KIB_OVERRIDE=8192 \
REUSE_FACTOR=1 \
LOAD_REPEAT=1 \
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=1,2,4,8,16 \
DRAM_LOAD_REPEATS=1,4,16 \
OUTDIR=results/ncu/h100_component_finalplan_ncu_factor_$(date +%Y%m%d) \
RAW_OUT=results/raw/h100_component_finalplan_ncu_factor_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

권한 문제가 있으면 다음 오류가 날 수 있다.

```text
ERR_NVGPUCTRPERM
```

이 경우 관리자가 performance counter 접근을 허용하는 것이 가장 좋다. 노드 정책상 즉시
변경이 어렵고 sudo 권한이 있으면 NCU sidecar만 sudo로 우회할 수 있다. Finalplan
package 전체를 재실행할 때는 다음처럼 실행한다.

```bash
NCU_USE_SUDO=1 bash results/summary/h100_component_finalplan_20260708_commands.sh
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
REG_W_SM_KIB=2048 \
L1_W_SM_KIB=16 \
SHARED_W_SM_KIB=128 \
L2_W_SM_KIB=64 \
DRAM_W_SM_KIB_OVERRIDE=8192 \
REUSE_FACTOR=1 \
LOAD_REPEAT=1 \
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=1,2,4,8,16 \
DRAM_LOAD_REPEATS=1,4,16 \
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
