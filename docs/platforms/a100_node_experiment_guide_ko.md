# A100 노드 실험 실행 가이드

External-memory 결과의 최신 명칭, read-only NCU 분모와 W sweep은
[External-Memory Read-Path 설계](../methodology/external_memory_read_path_experiment_design_ko.md)를 우선 적용한다.

작성일: 2026-07-08, updated 2026-07-22

## 목적

이 문서는 A100 기준 노드에서 FP16 Tensor Core energy microbenchmark를 재현하기 위한 실행 가이드다. 기본 목표는 A100 profile에서 `blocks/SM`, `W_SM` sweep을 수행하고, NVML energy 결과와 NCU sidecar 검증 결과를 분리해서 수집하는 것이다.

Tensor만 새 v3 방법으로 재측정할 때는 build 후 다음 package를
생성한다. `pilot`이 정상 완료된 뒤에만 `--preset final`로 바꾼다.

```bash
TAG="$(date +%Y%m%d)"
python3 scripts/plan_tensor_fp16_cross_platform_experiment.py \
  --target-profile a100 --gpu-id 0 --preset pilot --tag "$TAG"
bash "results/summary/a100_tensor_fp16_cross_platform_pilot_${TAG}_command.sh"
```

A100 Tensor v3 좌표는 B `4,16,32`, pilot RF `1,4,16`, duration `5,15 s`다.
`W_SM=1 KiB/SM`은 CLI placeholder이며 register footprint가 아니다. 실제 RF
footprint와 spill은 NCU register/local counter로 판정한다.

GA100 L2의 source partition, LTC fabric, logical final-service counter 모델과 수식은
[A100 L2 fabric-aware 실험 설계](../methodology/a100_l2_fabric_aware_experiment_design_ko.md)를
기준으로 한다. 과거에 생성한 command package에는 이 metric/gate가 없을 수 있으므로
새 실행에서는 현재 checkout으로 package를 다시 생성한다.

> **2026-07-15 필수 주의:** `a100_component_finalplan_20260714`의 Tensor
> run은 재개하지 않는다. B32/RF8 `reg_operand_only`의 10억 ITER가
> 약 1 ms에 종료되어 control calibration이 무효였고, 같은 ITER의
> `reg_mma`가 2,096-4,280 s 실행됐다. 현재 v6 source를 clean build한 뒤
> 새 tag package로 시작한다. 세부 판정은
> [A100 Tensor control calibration 실패 감사](../audits/a100_tensor_control_calibration_failure_20260715_ko.md)를
> 따른다.

## A100 기준 profile

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU profile | `a100` | - |
| architecture | Ampere GA100 | - |
| compute capability | 8.0 | - |
| CUDA arch flag | `sm_80` | - |
| default full SM count | 108 | SMs |
| nominal L2 | 40 | MiB |
| combined L1/shared profile | 192 | KiB/SM |
| shared allocation profile | 164 | KiB/SM |
| max dynamic shared memory per block | 163 | KiB/block |
| max resident blocks per SM | 32 | blocks/SM |
| NVML `GetPowerUsage` 의미 | instantaneous | mW |

주의: 실제 A100 SKU, MIG 설정, 클러스터 정책에 따라 보이는 SM 수가 달라질 수 있다. 실행 전 preflight 결과의 runtime SM 수를 확인한다. `combined L1/shared profile`은 SM 내부 통합 capacity이고, `shared allocation profile`은 shared-memory 실험 feasibility에 쓰는 CUDA shared capacity다.

Power 측정은 [power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)를 따른다. A100/GA100은 `GetPowerUsage`를 instantaneous로 기록하지만, 최종 energy numerator는 가능하면 `nvmlDeviceGetTotalEnergyConsumption` mJ counter 차분을 우선한다. `energy_source=legacy_get_power_usage_integral`이면 최종 coefficient가 아니라 provisional/fallback 결과로 표시한다.

A100 결과를 채택할 때는 아래 gate를 적용한다.

| 항목 | 채택 기준 |
|---|---|
| final numerator | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy` |
| integration method | `total_energy_mj_delta` |
| fallback | `GetPowerUsage` instant endpoint 적분은 provisional만 허용 |
| profile semantics | `nvml_power_usage_semantics=instant` |
| measurement scope | `measurement_scope=gpu_device_total_energy_counter` |
| partition | MIG/full GPU 여부와 runtime active SM 수를 보고서에 기록 |

## 1. 저장소 준비

```bash
git clone https://github.com/bang001/gpupower0701.git
cd gpupower0701
git pull
```

이미 노드에 checkout이 있으면 `git pull`만 실행한다.

## 2. 노드 preflight

먼저 GPU, NVML, Nsight Compute 상태를 기록한다.

```bash
nvidia-smi -L
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
nvidia-smi -q -d POWER,CLOCK,TEMPERATURE
```

가능하면 persistence mode를 켠다.

```bash
sudo nvidia-smi -pm 1
```

MIG가 켜져 있으면 full A100 기준 실험과 비교가 어려울 수 있다.

```bash
nvidia-smi -q | grep -i -E "MIG|Product Name|UUID|FB Memory|Compute Mode"
```

preflight script:

```bash
python3 scripts/preflight_gpu_support.py \
  --gpu 0 \
  --target-profile a100 \
  --strict \
  --active-sm 108 \
  --ncu "${NCU_BIN:-/usr/local/cuda-13.0/bin/ncu}" \
  --nvcc "${NVCC:-/usr/local/cuda-13.0/bin/nvcc}" \
  --out results/summary/a100_gpu0_preflight.md
```

preflight에서 확인할 항목:

| 항목 | 기대값 |
|---|---|
| detected profile | `a100` |
| compute capability | `8.0` |
| selected CUDA arch | `80` |
| dry-run GPU | `dry_run_gpu: 0` 또는 preflight `--gpu`와 같은 index |
| dry-run active SM | `dry_run_active_sm: 108`, MIG이면 runtime SM 수 |
| NCU chip | `ga100` |
| NCU query metrics | `query_metrics_ok: true` |
| binary dry run | `return_code: 0` |

## 3. 빌드

A100에서는 `CMAKE_CUDA_ARCHITECTURES=80`으로 빌드한다.
현재 보고된 서버의 CUDA 13.0 toolkit은 다음처럼 compiler,
binary inspector, NCU 경로를 같은 toolkit으로 고정한다.

```bash
export NVCC=/usr/local/cuda-13.0/bin/nvcc
export CUOBJDUMP=/usr/local/cuda-13.0/bin/cuobjdump
export NCU_BIN=/usr/local/cuda-13.0/bin/ncu
test -x "$NVCC" -a -x "$CUOBJDUMP" -a -x "$NCU_BIN"

cmake -S . -B build-a100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DCUDAToolkit_ROOT=/usr/local/cuda-13.0 \
  -DCMAKE_CUDA_ARCHITECTURES=80

cmake --build build-a100 --clean-first -j
```

conda/toolkit 경로를 명시해야 하는 환경이면 다음처럼 지정한다.

```bash
cmake -S . -B build-a100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/path/to/nvcc \
  -DCUDAToolkit_ROOT=/path/to/cuda \
  -DCMAKE_CUDA_ARCHITECTURES=80

cmake --build build-a100 --clean-first -j
```

빌드 로그에서 `ptxas` register count와 spill을 확인한다. 주요 kernel에서 `spill stores` 또는 `spill loads`가 발생하면 보고서에 위험으로 기록한다.
`git pull` 후 `src/`, `include/`, `CMakeLists.txt`가 바뀐 경우에는 반드시 clean rebuild를 한다.
특히 final run raw CSV는 C++ harness의 CSV header에 `measurement_scope` 컬럼이 있는
바이너리로 생성되어야 한다.

## 4. Dry-run sanity check

실제 측정 전 A100 profile의 feasibility를 확인한다.

```bash
./build-a100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_mma \
  --w-sm-kib 128 \
  --blocks-per-sm 32 \
  --target-profile a100 \
  --active-sm 108 \
  --dry-run
```

기대:

| 출력 항목 | 기대값 |
|---|---|
| `target_profile` | `a100` |
| `compute_capability` | `8.0` |
| `max_blocks_per_SM` | `32` |
| `target_l2_MiB` | `40` |
| `target_shared_KiB_per_SM` | `164` |
| `mode_allowed` | strict/실행 좌표는 반드시 `true`; `false`이면 dry-run 종료 코드 2로 중단 |

탐색 단계에서는 `--target-profile auto`도 한 번 확인할 수 있지만, final package에
넣는 preflight는 `--target-profile a100 --strict`로 실행한다.

```bash
./build-a100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
  --target-profile auto \
  --dry-run
```

## 5. Smoke run

짧은 실행으로 CSV schema와 NVML energy source를 확인한다.

```bash
./build-a100/a100_fp16_energy_v2 \
  --gpu-list none \
  --mode idle \
  --w-sm-kib 1 \
  --blocks-per-sm 1 \
  --target-profile a100 \
  --active-sm 108 \
  --seconds 1 \
  --repeats 1 \
  --output results/raw/a100_smoke_idle.csv
```

```bash
./build-a100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
  --target-profile a100 \
  --active-sm 108 \
  --seconds 1 \
  --repeats 1 \
  --output results/raw/a100_smoke_reg_mma.csv \
  --verify-smid 1
```

register/tensor 분리 control도 짧게 확인한다.

```bash
./build-a100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_operand_only \
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
  --target-profile a100 \
  --active-sm 108 \
  --seconds 1 \
  --repeats 1 \
  --reuse-factor 2 \
  --output results/raw/a100_smoke_reg_operand_only.csv \
  --verify-smid 1
```

2026-07-15 실패 좌표인 B32/RF8을 calibration-only로 먼저 재현 검사한다.
이 두 명령은 power CSV를 쓰지 않고 energy sweep 전에 종료된다.

```bash
for MODE in reg_operand_only reg_mma; do
  ./build-a100/a100_fp16_energy_v2 \
    --gpu-list 0 \
    --mode "$MODE" \
    --w-sm-kib 1 \
    --blocks-per-sm 32 \
    --target-profile a100 \
    --active-sm 108 \
    --seconds 1 \
    --reuse-factor 8 \
    --repeats 1 \
    --verify-smid 0 \
    --calibrate-only
done
```

두 출력 모두 `CALIBRATION_REACHED_FLOOR=1`,
`CALIBRATION_TRIAL_ELAPSED_S>=0.05`여야 한다. control이 다시 약 1 ms에
끝나거나 10억 단위 `CALIBRATED_ITERS`를 내면 full run을 시작하지 않는다.

CSV에서 확인할 항목:

| 컬럼 | 기대 |
|---|---|
| `profile_name` | `a100` |
| `compute_capability` | `8.0` |
| `sm_count` | 보통 `108`, MIG/SKU에 따라 다를 수 있음 |
| `energy_source` | `nvml_total_energy` 우선 |
| `measurement_scope` | `gpu_device_total_energy_counter` |
| `nvml_power_usage_semantics` | `instant` |
| `smid_histogram_ok` | active row에서 `true` |
| `expected_reg_operand_ops` | `reg_operand_only`, `reg_mma`에서 `active_SM * blocks/SM * ITER * reuse_factor` |

schema smoke audit:

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/a100_smoke_reg_mma.csv \
  --target-profile a100 \
  --out-csv results/summary/a100_smoke_power_api_audit.csv \
  --out-md results/summary/a100_smoke_power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope \
  --require-exact-measurement-interval \
  --require-mode-notes-marker \
  reg_mma=tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6
```

이 단계에서 모든 row가 `missing_column:measurement_scope`,
`missing_column:measurement_start_epoch_ms` 또는
`missing_explicit_measurement_scope`로 reject되면, GPU 측정값 문제가 아니라 stale
binary/schema 문제다. 현재 source를 pull한 뒤 `cmake --build build-a100
--clean-first -j`로 다시 빌드하고, 기존 `results/raw/a100_component_finalplan_*.csv`는
archive로 옮긴 뒤 재실행한다. 구버전 CSV에 새 row를 append하면 power API audit이
전체 reject될 수 있다.

## 6. Full sweep 실행

요청 sweep 조건:

| sweep | 값 | 단위 |
|---|---|---|
| Sweep 1 | `blocks/SM = 1, 2, 4, 8, 16, 32` | blocks/SM |
| Sweep 2 | `W_SM = 1 KiB`부터 `128 MiB`까지 2배 증가 | KiB/MiB |
| active SM | `108` | SMs |
| final seconds | `10` 이상 권장 | s |
| final repeats | `5` 이상 권장 | count |

이 표는 원래 요청한 **broad diagnostic sweep**이다. 현행 acceptance-first final
component package의 A100 energy 좌표는 11절의 `blocks/SM=16,32`와 component별
선택 `W_SM`만 사용한다. 따라서 component coefficient 실험을 실행할 때 이 broad
`run_sweep.py`를 표준 finalplan 대신 사용하지 않는다.

Matrix만 먼저 생성:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --include-idle \
  --target-profile a100 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --active-sm-values 108 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_full_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/a100_full_sweep_$(date +%Y%m%d)_matrix.csv
```

실행:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --include-idle \
  --execute \
  --target-profile a100 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --active-sm-values 108 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_full_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/a100_full_sweep_$(date +%Y%m%d)_matrix.csv
```

짧은 sanity sweep:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --execute \
  --target-profile a100 \
  --gpu-ids 0 \
  --modes empty,reg_fragment_only,reg_operand_only,reg_mma,shared_mma,l2_mma,dram_mma,store_path \
  --w-sm-kib-values 32,128,512,8192 \
  --blocks-per-sm-values 1,8,16,32 \
  --active-sm-values 108 \
  --seconds 2 \
  --repeats 1 \
  --output results/raw/a100_sanity_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/a100_sanity_sweep_$(date +%Y%m%d)_matrix.csv
```

### Legacy component pair 실행

기존 `run_component_pairs.py` / `analyze_component_pairs.py` 방식은 현재 primary 경로가 아니다. 이 방식은 elapsed mismatch와 instruction-mix 차이가 커서 final component coefficient로 쓰기 어렵다.

관련 코드는 혼동 방지를 위해 archive로 이동했다.

```text
archive/legacy_20260707/scripts/run_component_pairs.py
archive/legacy_20260707/scripts/analyze_component_pairs.py
```

A100 component coefficient 후보는 이 문서 11장의 acceptance-first finalplan flow를 우선 사용한다.

## 7. NCU validation

NCU는 energy run과 분리해서 실행한다. A100은 NCU chip alias가 `ga100`이다.

Metric availability:

```bash
NCU="$(command -v ncu)" NCU_CHIP=ga100 scripts/run_ncu.sh --query-metrics
```

대표 mode validation:

```bash
NCU="$(command -v ncu)" \
BIN=./build-a100/a100_fp16_energy_v2 \
TARGET_PROFILE=a100 \
ACTIVE_SM=108 \
GPU=0 \
OUTDIR=results/ncu/a100_validation_$(date +%Y%m%d) \
RAW_OUT=results/raw/a100_ncu_validation_sidecar_$(date +%Y%m%d).csv \
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
TAG="$(date +%Y%m%d)"
NCU_USE_SUDO=1 bash "results/summary/a100_component_finalplan_${TAG}_commands.sh"
```

수동 NCU validation만 다시 돌릴 때는 기존 명령에 `NCU_USE_SUDO=1`을 붙인다.

```bash
NCU_USE_SUDO=1 \
NCU="$(command -v ncu)" \
BIN=./build-a100/a100_fp16_energy_v2 \
TARGET_PROFILE=a100 \
ACTIVE_SM=108 \
GPU=0 \
OUTDIR=results/ncu/a100_validation_$(date +%Y%m%d) \
RAW_OUT=results/raw/a100_ncu_validation_sidecar_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

`sudo`가 CUDA/Nsight Compute 경로를 지우는 환경이면 generated package에는
`NCU_BIN="$(command -v ncu)" NCU_SUDO="sudo -E"`를 같이 지정하고, 수동
`run_ncu_validation.sh`에는 `NCU="$(command -v ncu)" NCU_SUDO="sudo -E"`를 같이
지정한다. NCU가 실패해도 NVML energy run 자체와 섞지 말고, 보고서에는
“NCU counter 검증 미완료”로 분리 기록한다.

## 8. Mode 설명

보고서에는 mode 의미를 반드시 포함한다.

| mode | 의미 | 주 경로 |
|---|---|---|
| `idle` | 커널 없이 NVML energy delta 측정 | idle baseline |
| `empty` | 같은 persistent grid에서 MMA 없음 | loop/scheduler baseline |
| `reg_fragment_only` | WMMA fragment/register setup, MMA 없음 | fragment setup control |
| `reg_operand_only` | `reg_mma`와 같은 `ITER * reuse_factor` loop에서 sampled register fragment 값을 소비, MMA 없음 | no-MMA register-fragment/control baseline |
| `reg_mma` | register 값으로 WMMA fragment를 채우고 MMA 반복 | effective Tensor Engine + register |
| `global_addr_only` | global memory pair와 같은 address/tile/repeat/checksum loop를 실행하되 input load는 하지 않음 | Global L1/L2/DRAM matched address control |
| `global_l1_load_only` | `ld.global.ca` scalar global load 반복 | global L1-hit candidate path |
| `l2_cg_load_only` | `ld.global.cg` scalar global load 반복 | global L1-bypassed L2-hit candidate path |
| `shared_load_only` | shared memory operand staging 후 WMMA load, MMA 없음 | effective shared/L1 load control |
| `shared_mma` | shared memory operand staging 후 WMMA load + MMA | effective shared/L1 path |
| `l2_load_only` | normal global load 기반 capacity diagnostic, MMA 없음 | L1과 섞일 수 있어 strict L2 coefficient 제외 |
| `l2_mma` | L2에 들어가는 global working set warm-up 후 load + MMA | effective L2-hit path |
| `dram_load_only` | nominal L2보다 큰 global working set streaming load, MMA 없음 | effective DRAM streaming load control |
| `dram_mma` | nominal L2보다 큰 global working set streaming load + MMA | effective DRAM streaming path |
| `store_only` | 반복 global store loop, MMA 없음 | store-only control |
| `store_path` | global store/output-side overhead 확인 | store-side path |

## 9. 결과 정리

모든 표에는 단위를 넣는다.

필수 표:

| 표 | 필수 열 |
|---|---|
| 실험 조건 | GPU, CC, SMs, L2 (MiB), shared/SM (KiB), seconds (s), repeats |
| sweep coverage | mode, valid rows, skipped rows, W_SM range (KiB/MiB), blocks/SM range |
| mode summary | mode, pJ/FLOP median, pJ/FLOP min/max, net_E_J median (J) |
| paired-difference | pair, delta_E_J (J), denominator, coefficient, unit |
| blocks sweep | mode, B=1, B=2, B=4, B=8, B=16, B=32 |
| W sweep | mode, W_SM range (KiB/MiB), pJ/FLOP range |
| NCU validation | mode, tensor %, L1 hit rate (%), L2 hit rate (%), L1 accesses (requests/sectors), L2 accesses (sectors), DRAM accesses (sectors), L1 bytes, L2 bytes, DRAM bytes, shared bytes, top stall %, status |

Plot 생성:

```bash
python3 scripts/plot_results.py \
  results/raw/a100_full_sweep_$(date +%Y%m%d).csv \
  --target-profile a100 \
  --outdir results/plots/a100_full_sweep_$(date +%Y%m%d)
```

주의:

- `seconds=1`, `repeats=1` 결과는 smoke/sanity 용도다.
- 최종 수치는 `seconds>=10`, `repeats>=5` 기준을 권장한다.
- `energy_source`가 다른 row는 같은 표에서 직접 비교하지 않는다.
- NCU replay 중 얻은 energy 값은 NVML energy CSV와 합치지 않는다.

## 10. 빠른 체크리스트

| 단계 | 확인 |
|---|---|
| preflight | `detected profile = a100`, `query_metrics_ok = true` |
| build | `CMAKE_CUDA_ARCHITECTURES=80`, 주요 kernel spill 0 |
| dry-run | `target_profile=a100`, `mode_allowed=true` |
| smoke | `energy_source=nvml_total_energy`, `smid_histogram_ok=true` |
| full sweep | raw CSV와 matrix CSV 모두 생성 |
| component pairs | `reg_mma_minus_reg_operand` pair와 단위 포함 summary 생성 |
| NCU | counter 수집 성공 또는 실패 사유 문서화 |
| report | mode 설명 표와 단위 포함 sweep 표 작성 |

## 11. 2026-07-06 Component finalplan 업데이트

기존 `run_component_pairs.py` 방식은 legacy archive로 이동했다. Tensor/Register/L1/Shared/L2/DRAM component coefficient 후보를 만들 때는 다음 acceptance-first flow를 우선한다.

| 단계 | script | 목적 |
|---|---|---|
| command plan | `scripts/plan_platform_component_experiment.py` | A100용 표준 energy/NCU/analyze 명령 생성 |
| L2 NCU precheck | `scripts/select_l2_path_configuration.py` | 독립 non-L2 energy 보존 후, L2 energy 전에 normal/persisting, layout, blocks/SM 후보를 strict gate로 선택 |
| energy sweep | `scripts/run_component_regression_sweep.py` | NCU 없이 energy 수집. 모든 final pair에서 treatment/control-floor dual calibration의 최대 ITER를 양쪽에 동일 적용 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | path hit/access/stall/spill 검증 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | accepted component 후보만 선별 |
| matched-control | `scripts/analyze_matched_control_energy.py` | NCU actual-byte denominator로 pJ/bit 계산 |

표준 명령 생성:

`--gpu-ids`를 생략하면 GPU 0을 사용한다. 다른 GPU를 쓰는 경우에만 예를 들어
`--gpu-ids 1`을 명시한다. raw의 `gpu_id`는 repeat가 아니라 물리 CUDA/NVML index다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "${NCU_BIN}" \
  --active-sm 108 \
  --seconds 10 \
  --repeats 5
```

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

4-GPU 노드에서 GPU 0만 active여도 raw에는 같은 `run_id`의 GPU 0~3 관찰 행이
기록될 수 있다. 현행 power-state audit과 matched-control은
`(sweep_source_id, run_id, gpu_id)`로 조인하며 Tensor/Shared/L1/L2/DRAM CSV 사이의
control pairing도 차단한다. 이 열이 없는 구형 power-state audit은 재생성한다.

`schema_revision_smoke` 뒤에 멈춘 경우 현재 package는 다음 세 단계를
별도로 표시한다.

| 로그 stage | 의미 | 확인 artifact |
|---|---|---|
| `schema_smoke_kernel_execution` | 3개 최소 kernel이 실제로 종료되는지 | `results/raw/a100_component_finalplan_<tag>_schema_smoke.csv` |
| `schema_smoke_power_api_audit` | CSV schema, `measurement_scope`, v6 revision marker, NVML scope | `results/summary/*_schema_smoke_power_api_audit.csv` |
| `tensor_binary_static_audit` | 선택한 `nvcc`와 같은 toolkit의 `cuobjdump`로 HMMA/control loop/spill 검사 | `results/summary/*_tensor_mma_binary_audit.csv` |

실패 시 `PIPELINE_COMMAND_FAILED` 행의 `stage`, `label`, `rc`가 직접
출력된다. Power audit은 reject row와 사유를, Tensor binary audit은
mode/RF별 사유를 stderr에 함께 출력한다. 이 gate를 우회하지 말고
실패 artifact를 먼저 확인한다.
Smoke 이후의 예기치 않은 중단은 `PIPELINE_ABORT`에 stage, line, rc,
command를 남긴다.

2026-07-16 이후 package에서 policy self-test는 synthetic 내부 출력을 캡처하고
성공 한 줄만 남긴다. `W=2048KiB, SM=108, ITER=456/10000,
ratio=21.930`은 과거 self-test fixture이며 실제 A100 측정값이 아니다. 실제
calibration은 `REAL GPU CALIBRATION: profile=a100 W_SM=1KiB`와
`runtime Tensor pair calibration start` 뒤에 출력된다. 구분 근거는
[`a100_v100_synthetic_selftest_false_failure_20260716_ko.md`](../audits/a100_v100_synthetic_selftest_false_failure_20260716_ko.md)에 있다.

A100 추천 finalplan 좌표:

기존 실행에서 Tensor RF4 이상 음수/weak 또는 L2 CG path reject를 재현한 경우에는 다음
targeted remediation package도 사용할 수 있다. 현재 표준 finalplan 자체에도 동일한
NCU-first L2 selector가 통합되어 있으므로 새 실행은 표준 package만으로도 L2 energy 전에
L2 실패 원인을 남긴다. Tensor/Shared/Global-L1/external-memory energy는 selector보다
먼저 실행하므로, L2가 reject돼도 이 네 raw/calibration artifact는 보존된다.

```bash
NCU_USE_SUDO=1 bash results/summary/a100_tensor_l2_remediation_20260710_commands.sh
```

실행 조건과 pass 기준은
[`a100_tensor_l2_remediation_20260710_command_plan.md`](../../results/summary/a100_tensor_l2_remediation_20260710_command_plan.md)에 정리되어 있다.
전용 audit가 pass한 뒤에만 표준 finalplan을 다시 실행해 Shared/L1/DRAM과 합친다.

2026-07-13 A100 후속 실행에서 Tensor는 dual calibration 후 RF1-16 모두 양수
0.35-0.54 pJ/FLOP였지만, L2는 source/TEX direct hit 51-62%, native op-read hit
67-72.5%가 보고됐다. 과거 코드는 두 값에 각각 95%를 요구해 reject했다. 현재 검토 결과
이 조합은 첫 partition miss가 LTC fabric의 다른 partition에서 회수될 때의
`native ~= 1/(2-direct)` 관계와 일치한다. 그러나 기존 report에는
`srcunit_ltcfabric` 원시 counter가 없으므로 소급 accepted로 바꾸지 않으며 final component
table에도 넣지 않는다.
Tensor 값은 v5 marker 유무와 관계없이 A100 launch-only control 실패가 확인됐으므로
모두 현행 계수에서 제외한다. v6 package로 RF1-16 전체를 재측정해야 한다.
과거 RTX 3090 v2 median 2.2525 pJ/FLOP도
양의 accumulator 장시간 누적 문제로 현재 coefficient에서 제외하므로 비교 기준으로
사용하지 않는다.
최신 targeted script는 긴 energy sweep 전에 다음 순서로 fail-fast한다.

| 순서 | 조건 | 통과 의미 |
|---:|---|---|
| 1 | normal/contiguous B16, B8, B4, B2, B1; W_SM 16/128 KiB, LR4, NCU application replay, CG warm-up 4회 | board-power 신호가 큰 좌표부터 동시성과 partition 경로를 분리 |
| 2 | normal `sm_interleaved` B16, B8, B4 | 128 B guard와 virtual-grid block-region 전치 효과 확인 |
| 3 | 모든 normal 실패 시 persisting contiguous B16/B8/B4/B1과 sm_interleaved B8/B4 | residency policy 효과 진단. API/metric unavailable이면 strict 미선정 |
| 4 | 선택된 policy/layout/B로 W16/32/64/128, LR1/2/4/8/16 `l2_path_minimal` NCU | source/fabric hit/miss, logical final hit, native-model, sector conservation, observed/expected traffic, DRAM read, long scoreboard 재검증 |
| 5 | 같은 구성으로 LR4/8/16 energy sweep | exact NCU denominator와 양수 차분으로 pJ/bit 계산 |

14개 후보가 모두 실패하면 script가 energy sweep 전에 종료되는 것이 정상이다.
MIG에서는 persisting L2 set-aside를 사용할 수 없을 수 있으므로 모든 normal 후보도
실패하면 해당 partition에서는 strict L2 coefficient가 없다고 보고한다.

기존 51-62% source와 67-72.5% native 차이는 partition forwarding 가설과 정합하지만,
실제 fabric counter 없이 확정하지 않는다. 최신 summary에서
`l2_device_path_hit_rate_pct`, `l2_tex_path_hit_rate_pct`,
`l2_native_read_hit_rate_pct`, `l2_fabric_read/hit/miss_sectors`,
`l2_logical_read_hit_rate_pct`, `l2_native_vs_fabric_model_hit_delta_pct`,
source/fabric sector conservation과 coherence,
`l2_read_bytes_to_expected`, `l2_read_miss_bytes`, `dram_read_bytes`,
`launch_persisting_l2_cache_size_bytes`를 함께 확인한다. 상세 판단은
[A100 L2 fabric-aware 설계](../methodology/a100_l2_fabric_aware_experiment_design_ko.md)와
[counter scope 감사](../audits/a100_l2_counter_scope_and_rtx_pair_remediation_ko.md)를 따른다.
eviction first/normal/last는 별도 full-profile 진단에서 얻을 수 있지만 strict hit gate의
필수값은 아니다.
logical final-service hit가 95% 이상, native-model 차이가 2 percentage points 이하,
source/fabric sector conservation이 0.98-1.02, observed/expected traffic이
0.95-1.05여야 strict precheck를 통과한다. direct source나 native lookup hit 자체에는
95%를 요구하지 않는다. 또한
`hit+miss/read`가 0.98-1.02를 벗어나면 replay counter 자체가 불일치한 것이므로 두 hit
비율 모두 coefficient 근거에서 제외한다. 현행 package는 L2와 external-memory를
각각 `NCU_METRIC_PROFILE=l2_path_minimal`로 실행하고 Tensor/Shared/L1은 `full`
summary를 사용한다. 세 source를 보존해 merge하며 최종 확인 파일은 다음과 같다.

```text
results/ncu/a100_component_finalplan_ncu_factor_<tag>/
  l2_selected_minimal/ncu_cache_validation_summary.csv
  external_memory_minimal/ncu_cache_validation_summary.csv
  full_non_l2/ncu_cache_validation_summary.csv
  ncu_cache_validation_summary.csv
```

RTX 3090/A100/V100의 전체 파라미터와 command 개수 비교는
[cross-platform component experiment guide](cross_platform_component_experiment_guide_ko.md)의
4.0-4.5절을 기준으로 한다. 현재 A100 표준 package는 L2 precheck가 선택한 blocks/SM
하나만 L2 energy에 사용한다. 유효 좌표는 72개/1 repeat, `repeats=5`에서 energy raw
360행이며 Tensor pair calibration 15 coordinates/30 commands, L2 pair calibration
6 coordinates/12 commands, external-memory pair calibration 9 coordinates/18 commands, schema
smoke 3행, primary NCU 73 cases다. L2 selector는 첫 후보 통과 시 조기 종료하며
최악에는 14 candidates x 2 W x 2 modes = 56개 NCU precheck case를 추가한다.

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | N/A (CLI placeholder 1) | 4,16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `shared_scalar_addr_only,shared_scalar_load_only` | 128 | 16 | energy/NCU load_repeat 4,8,16; 동일 pair ITER |
| Global L1 | `global_addr_only,global_l1_load_only` | 16 | 16 | energy/NCU load_repeat 4,8,16; exact W/B |
| L2 CG | `global_addr_only,l2_cg_load_only` | 16,128 | NCU precheck가 B16/B8/B4/B2/B1 중 하나 선택 | energy/final NCU load_repeat 4,8,16; selector는 LR4만 probe |
| External-memory read path | `global_addr_only,dram_cg_load_only` | 2048,4096,8192 | 16 | energy/NCU load_repeat 4,8,16; strict read-byte gate |

### A100 sweep를 그래프로 해석하기

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

- Shared W128/B16의 보수적 예약량은 `128+16=144 KiB/SM`이며 energy와 NCU가 동일 좌표다.
- Global L1 W16/B16은 block당 1 KiB를 유지하는 cached-global anchor다.
- L2 W16/W128은 전체 1.688/13.5 MiB로 40 MiB L2 안의 두 endpoint다. 두 점 모두
  NCU L1 bypass와 source+fabric final-service gate를 통과해야 한다.
- External-memory W2048/4096/8192는 전체 216/432/864 MiB, 즉 40 MiB L2의
  5.4/10.8/21.6배다. final L2 hit <=10%, DRAM read/L2 read >=90%, write/read <=1%를 확인한다.

![strict anchor capacity 맥락](../presentations/assets/platform_capacity_context.png)

A100 L2 W16은 nominal L2의 약 4.2%, W128은 약 33.8%다. 두 endpoint의
coefficient/hit/stall plateau를 함께 보고 선택한다.

Tensor는 각 `W/B/SM/RF` 좌표에서 `reg_mma`를 treatment 목표시간으로,
`reg_operand_only`를 control 최소시간으로 각각 calibration하고 두 ITER 중 큰 값을
두 mode에 똑같이 전달한다. 표준 10 s package의 control floor는 1 s이고, A100 targeted
20 s package는 2 s다. 생성되는 `*_tensor_pair_calibration.csv`에는 두 candidate ITER,
선택 정책, calibration command, trial ITER/time, control/treatment ITER ratio,
predicted treatment time과 resolved ITER가 남는다. treatment/control trial은 각각
실제 runtime `>=0.05 s`를 증명해야 하고, predicted treatment time이
목표시간의 6배를 초과하면 energy 수집 전에 실패한다. 표준 package의
개별 energy command wall-time gate는 180 s다.
분석은 `--tensor-pair-policy matched-iters`를 사용해 elapsed-time power scaling 없이
`net_E(reg_mma) - net_E(reg_operand_only)`를 직접 계산한다. 두 ITER가 다르거나 calibration
manifest가 없는 새 package는 final Tensor evidence로 채택하지 않는다.
두 kernel은 source상 단일 A/B/C fragment, dependent scalar update, in-place A-sign
flip, C-fragment epilogue를 공통으로 두지만 treatment만 MMA를 발행한다. A fragment의
FP16 sign bit를 매 logical MMA마다 뒤집어 accumulator를 bounded 상태로 유지한다. ptxas는
no-MMA control을 더 적은 register로 최적화하므로 차분값은 Tensor Core 회로만의
에너지가 아니라 WMMA/HMMA register, accumulator, scheduler path를 포함한다.
raw Tensor row의 `notes`에는
`tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6`가 있어야 한다.
RF1/2/4/8/16은 fixed-trip `unroll 1` treatment/control kernel을 사용하며 target A100에서도 RF별
`HMMA/logical MMA` 상대 spread 10% 이하를 통과해야만 유효하다.
Static binary audit에서 treatment/control 모두 `SR_CLOCKLO` token을 포함한
backward loop를 확인하고, runtime NCU에서
`SASS instructions/expected register op >= 0.1`도 통과해야 한다. v4 control은 CUDA
source에 반복문이 있어도 ptxas 후 launch-only kernel이 될 수 있었으므로 v4와
실패한 A100 v5 Tensor energy row는 현행 계수로 사용할 수 없다.
같은 ITER의 no-MMA control은 treatment보다 훨씬 빨리 끝나므로 dual calibration으로
control duration floor를 먼저 보장한다. 표준 package analyzer는 calibration floor의 80%
(1 s floor이면 0.8 s), targeted package는 2 s floor의 80%인 1.6 s를 요구한다. Control
`net_E_J <= 0`이면 duration을 만족해도 energy counter/noise floor에서 식별되지 않은 것으로
보고 reject한다.

L2 CG도 각 `W_SM/blocks/SM/load_repeat` 좌표에서 `l2_cg_load_only` 목표시간과
`global_addr_only` 최소 control 시간을 따로 calibration한 뒤, 두 candidate ITER의 최대값을
양쪽에 동일하게 적용한다. 분석은 `--l2-pair-policy matched-iters`와 direct net-energy
subtraction을 사용한다. `*_l2_pair_calibration.csv`, raw ITER equality,
`pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1` 중 하나라도 없으면 NCU L2 hit가
95% 이상이어도 energy coefficient를 reject한다.

모든 새 raw row는 timed kernel의 `measurement_start_epoch_ms`와 monotonic
`steady_clock` elapsed를 기록하며, 종료 epoch는 시작 epoch에 elapsed를 더해 산출한다.
matched-control은 완료 시각 차이였던 legacy
`pair_start_distance_ms`가 아니라 두 benchmark interval 사이의
`pair_transition_gap_ms<=pair_transition_gap_limit_ms`를 검사한다. 생성 plan의
한계는 `max(30000, (seconds+15)x1000)` ms이므로 표준 10초 run은 30,000 ms,
20초 stability run은 35,000 ms다. 이전 A100 raw는 `run_id-elapsed_s`
fallback으로 재분석할 수 있지만 `pair_timing_source=legacy_run_id_elapsed_inferred`를
결과에 유지한다. 이 fallback row는 진단/후보 복구용이며 strict final package에는 exact
epoch interval 재실행이 필요하다.
새 runner는 반복과 좌표 index를 함께 사용해 pair 방향을 counterbalance하며 strict package는
`pair_execution_order=control_then_treatment,treatment_then_control` 양쪽의 valid row를
요구한다.

External-memory path는 각 `W_SM/blocks/SM/load_repeat` 좌표에서 `dram_cg_load_only`를 목표
측정시간으로, `global_addr_only`를 최소 control 시간으로 각각 calibration한 뒤 두
ITER 중 큰 값을 두 mode에 동일하게 전달한다. 분석은
`--dram-pair-policy matched-iters`를 사용하여 elapsed power scaling 없이
`net_E(dram_cg_load_only) - net_E(global_addr_only)`를 직접 계산하고 strict NCU
`dram__bytes_read.sum`으로만 정규화한다. 생성되는
`*_dram_pair_calibration.csv`, 두 raw mode의 `ITER`, matched detail의
`pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`이 모두 일치해야
effective external-memory 후보가 된다. 물리 HBM2 energy로 해석하지 않는다.

기본 A100 memory 좌표는 모두 block당 최소 1 KiB를 만족한다. 사용자 override도 표준
runner가 energy 수집 전에 binary `--dry-run`으로 재검사하므로 Python/C++ feasibility가
어긋나면 첫 측정 전에 명확한 좌표와 return code를 출력하고 중단한다.

A100의 L2는 40 MiB이므로 `W_SM=256 KiB`와 active SM 108개는 전체 27 MiB로 L2 경계에 너무 가깝다. strict L2 path는 `W_SM=16,128 KiB`(전체 약 1.688, 13.5 MiB)를 `ld.global.cg`로 실행한다. path-specific NCU에서 L1 hit가 거의 없고, source/TEX miss 중 LTC-fabric hit를 더한 logical final-service L2 hit가 95% 이상인 plateau만 선택한다. 시간 측정 전 warm-up도 `global_cg_warmup_kernel`의 `ld.global.cg.u32`로 4회 수행한다. NCU는 `application replay + cache-control none`을 사용해 metric pass마다 application과 warm-up을 다시 실행한다. 중간 W32/W64가 필요하면 별도 discovery tag로 실행하며, `l2_load_only`는 normal global load라 final L2 coefficient에는 사용하지 않는다.

CG raw row의 `notes`에는 `global_warmup_policy=ld_global_cg`가 있어야 하며,
없으면 stale binary로 보고 package audit에서 reject한다.

| NCU 기준 | 통과 조건 |
|---|---:|
| Global L1 | path-specific L1 hit >= 95%, L1 request bytes 존재, L2/L1 request bytes <= 1% |
| L2 CG | NCU application replay/cache-control none, 선택 residency/layout/B와 warm-up 4회 metadata 일치, source+LTC-fabric logical final hit >=95%, source/fabric `(hit+miss)/read=1+/-2%`, native-fabric-model 차이<=2 percentage points, observed/expected source L2 bytes=0.95-1.05, L1 path hit<=1%, L1 hit/L1 request bytes<=1%, DRAM-read/source-L2-read<=2% |
| Shared scalar | shared access/bytes 존재, bank conflict 0 또는 매우 낮음 |
| Tensor | treatment HMMA > 0, control HMMA=0, spill/local 0, treatment-control ITER 동일, RF1-16의 `HMMA/logical MMA` 상대 spread<=10%. legacy epilogue 완화는 과거 결과 설명용이며 새 final run에는 사용하지 않음 |

`global_addr_only`는 `global_l1_load_only`, `l2_cg_load_only`, `dram_cg_load_only`와 동일한 block/tile/index/repeat loop를 실행하지만 global input load는 수행하지 않는다. 따라서 memory pair의 차분은 단순 `clocked_empty` 대비보다 주소 계산과 loop 비용을 더 잘 제거한다. NCU sidecar에서는 global-load L1 request byte가 0인지 확인한다. `--verify-smid=1` atomic bookkeeping 때문에 L2 sector가 소량 보일 수 있으므로 L2 sector 0을 요구하지 않는다.

분석 단계의 `--require-control-ncu-acceptance`는 이 조건을 mode-level이 아니라
동일 `W_SM/B/active_SM/LR` 좌표로 요구한다. A100 treatment가 accepted여도 대응
`global_addr_only`가 reject이면 해당 계수 row는 생성하지 않는다.

`l2_cg_load_only`에서는 반대로 L1 request byte가 존재해야 한다. `.cg` global load도 요청은
L1TEX를 통과하므로 `L1 request bytes / L2 read bytes`가 약 1인 것은 L1 cache hit 증거가
아니다. 이 경로는 path-specific `L1 hit bytes/request bytes <=1%`와 logical
final-service `L2 hit >=95%`로 판정한다. source direct hit, native lookup hit,
aggregate L1/L2 hit는 각각의 분모와 함께 표기하되 단독 hard gate로 사용하지 않는다.

보고서에는 `board-level effective coefficient`, `not pure physical component energy`를 명시한다. A100의 HBM2 물리 pJ/bit 문헌값과 본 실험의 DRAM streaming pJ/bit는 같은 의미가 아니다.
