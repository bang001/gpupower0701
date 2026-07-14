# V100 노드 실험 실행 가이드

External-memory 결과의 최신 명칭, read-only NCU 분모와 W sweep은
[External-Memory Read-Path 설계](../methodology/external_memory_read_path_experiment_design_ko.md)를 우선 적용한다.

작성일: 2026-07-02, V100 L2 동일-ITER 정책 재검토: 2026-07-13

## 목적

이 문서는 V100 기준 노드에서 FP16 Tensor Core energy microbenchmark를 재현하기 위한 실행 가이드다. 기본 목표는 V100 profile에서 `blocks/SM`, `W_SM` sweep을 수행하고, NVML energy 결과와 NCU sidecar 검증 결과를 분리해서 수집하는 것이다.

V100은 Volta GV100 / compute capability 7.0 GPU이므로 A100/RTX 3090/H100과 비교할 때 다음 차이를 반드시 분리해서 기록한다.

- CUDA build arch는 `sm_70`이다. CUDA 13은 Volta offline compilation을 제거했으므로
  `compute_70`을 실제로 나열하는 compiler를 써야 한다. 이 프로젝트의 V100 build는
  CUDA 12.x를 권장한다.
- FP16 Tensor Core baseline은 가능하지만 TF32/BF16/FP64 Tensor Core baseline은 A100/H100과 다르다.
- Nsight Compute 2024.3은 GV100 지원이 공식 확인되지만 최신 release에서는 Volta 지원이 제거될 수 있다. V100 NCU 검증은 버전명만 믿지 않고 `ncu --list-chips`와 `ncu --query-metrics --chips gv100`이 모두 성공하는 toolchain으로 진행한다.
- NVML `GetPowerUsage` 의미는 instantaneous로 취급한다. 최종 비교에서는 `energy_source`와 `nvml_power_usage_semantics`를 반드시 표기한다.

Power 측정 API의 세대별 의미는 [power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)를 기준으로 해석한다. V100은 Volta이므로 total energy counter가 기대되는 세대지만, 실제 사용 가능 여부는 runtime CSV의 `nvml_total_energy_supported`로 확인한다. total energy counter가 없고 `GetPowerUsage` fallback만 남으면 최종 coefficient가 아니라 provisional/fallback 결과로 보고한다.
최종 coefficient 후보에는 `energy_source=nvml_total_energy`,
`energy_integration_method=total_energy_mj_delta`,
`measurement_scope=gpu_device_total_energy_counter`,
`nvml_power_usage_semantics=instant`인 row만 올린다.

새 V100 노드에서 다른 작업자나 에이전트에게 실험을 맡길 때는 프롬프트를 본 문서에 섞지 말고 [v100_experiment_prompt_ko.md](prompts/v100_experiment_prompt_ko.md)를 별도로 전달한다. 이 가이드는 실행 절차와 판정 기준이고, 프롬프트 문서는 “무엇을 확인하고 어떤 산출물을 만들어야 하는지”를 지시하는 용도다.

## V100 기준 profile

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU profile | `v100` | - |
| architecture | Volta GV100 | - |
| compute capability | 7.0 | - |
| CUDA arch flag | `sm_70` | - |
| default full SM count | 80 | SMs |
| register file | 256 | KiB/SM, 65,536 x 32-bit registers |
| max resident warps | 64 | warps/SM |
| max resident threads | 2,048 | threads/SM |
| nominal L2 | 6 | MiB |
| combined L1/shared profile | 128 | KiB/SM |
| shared allocation profile | 96 | KiB/SM |
| max dynamic shared memory per block | 96 | KiB/block |
| max resident blocks per SM | 32 | blocks/SM |
| NVML `GetPowerUsage` 의미 | instantaneous | mW |
| NCU chip alias | `gv100` | - |

주의: V100 PCIe/SXM, MIG가 아닌 다른 가상화 환경, 클러스터 할당 정책에 따라 보이는 GPU와 clock/power state가 달라질 수 있다. 실행 전 preflight 결과의 runtime SM 수와 power limit을 확인한다. `combined L1/shared profile`은 SM 내부 통합 capacity이고, `shared allocation profile`은 shared-memory 실험 feasibility에 쓰는 CUDA shared capacity다.

현재 kernel은 `threads/block=32`, 즉 block당 warp가 하나다. `blocks/SM=32`는 SM당
최대 32개 block을 요청하는 grid geometry이고, 이론상 32 warps/SM으로서 V100 최대
64 warps/SM의 50%다. 그러나 register/shared-memory 자원 제한 때문에 실제 동시 resident
block 수는 더 작을 수 있다. 따라서 B32를 occupancy 보장으로 쓰지 않고 NCU의
`achieved_occupancy_pct`, `registers_per_thread`, static/dynamic shared bytes per block을
함께 확인한다.

## V100에서 반드시 분리할 기준

RTX 3090이나 A100에서 쓰던 좌표를 그대로 V100에 적용하면 L1/L2 path acceptance가 쉽게 깨진다. 다음 값이 섞이면 최종 component coefficient로 채택하지 않는다.

| 혼입 신호 | 왜 문제인가 | 조치 |
|---|---|---|
| `sm_86`, `active_SM=82`, `max_blocks_per_SM=16` | RTX 3090/GA102 기준이 V100 실행에 섞인 상태 | build와 run option을 `sm_70`, `target_profile=v100`, `active_SM=80`으로 재확인 |
| `sm_80`, `ga100`, `L2=40 MiB`, `shared=164 KiB/SM` | A100/GA100 기준이 섞인 상태 | A100 결과와 V100 결과를 다른 CSV/report로 분리 |
| `NCU_CHIP` 미지정 또는 `gv100` query 실패 | Volta counter 경로 검증이 불가능할 수 있음 | `NCU_CHIP=gv100`으로 재실행하고, 실패하면 “NCU path acceptance 미완료”로 보고 |
| L2 후보에서 L1 request bytes가 L2 bytes와 비슷함 | `.cg` 요청도 L1TEX를 통과하므로 request byte만으로 L1 cache hit를 판정한 오류 | V100 L2는 `l2_cg_load_only` 우선, path-specific L1 hit bytes/request <=1%와 L2 read hit >=95% 확인. aggregate hit는 진단값 |
| External-memory W가 L2와 비슷함 | L2 재사용을 external read로 오인할 수 있음 | `DRAM_W_SM_KIB_VALUES=256,512,2048` low/mid/high sweep과 strict NCU gate 적용 |

이 실험의 최종값은 순수 회로 에너지가 아니라 NCU로 경로가 검증된 effective microbenchmark coefficient다. 즉 `pJ/FLOP`, `pJ/bit`, `pJ/Byte`는 “이 커널, 이 access pattern, 이 GPU 상태에서 관찰된 board-level incremental coefficient”로 해석해야 한다.

## 1. 저장소 준비

```bash
git clone https://github.com/bang001/gpupower0701.git
cd gpupower0701
git pull
```

이미 노드에 checkout이 있으면 `git pull`만 실행한다.

## 2. 노드 상태 확인

먼저 GPU, NVML, driver 상태를 기록한다.

```bash
nvidia-smi -L
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,memory.total,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
nvidia-smi -q -d POWER,CLOCK,TEMPERATURE
```

가능하면 persistence mode를 켠다.

```bash
sudo nvidia-smi -pm 1
```

GPU가 V100으로 잡히는지 확인한다.

```bash
nvidia-smi --query-gpu=index,name,compute_cap --format=csv,noheader
```

기대:

| 항목 | 기대값 |
|---|---|
| GPU name | `V100` 포함 |
| compute capability | `7.0` |
| target profile | `v100` |

## 3. CUDA/NCU toolchain 확인

CUDA compiler와 NCU는 서로 다른 gate다. V100 binary는 `compute_70`을 생성할 수 있는
CUDA compiler가 필요하고, counter sidecar는 `gv100`을 지원하는 NCU가 필요하다. 한쪽이
통과했다고 다른 쪽도 통과한 것으로 간주하지 않는다.

```bash
export NVCC="${NVCC:-$(command -v nvcc)}"
"${NVCC}" --version
"${NVCC}" --list-gpu-arch | grep -Fx compute_70
```

마지막 명령이 실패하면 그 compiler로 V100 binary를 새로 만들 수 없다. 특히 CUDA 13
`nvcc`는 `sm_70` offline compilation을 지원하지 않는다. CUDA 12.x module/toolkit을
선택한 뒤 다시 확인한다. 예시는 다음과 같다.

```bash
export NVCC=/path/to/cuda-12/bin/nvcc
export CUDAToolkit_ROOT=/path/to/cuda-12
```

V100은 NCU 버전 제약이 중요하다. 먼저 현재 `ncu`가 `gv100`을 지원하는지 확인한다.

```bash
ncu --version
ncu --list-chips | tr ',' '\n' | grep -i gv100 || true
ncu --query-metrics --chips gv100 >/tmp/ncu_gv100_metrics.txt
echo $?
```

판정:

| 결과 | 의미 | 조치 |
|---|---|---|
| `gv100` 있음, query 성공 | V100 NCU validation 가능 | 현재 `ncu` 사용 |
| `gv100` 없음 또는 query 실패 | 현재 NCU로 Volta profiling 불가 | 공식적으로 GV100 지원이 확인되는 2024.3 계열을 우선 사용하고 다시 query |

예시:

```bash
export NCU=/path/to/nsight-compute-2024.3/ncu
"${NCU}" --version
"${NCU}" --list-chips | tr ',' '\n' | grep -i gv100
```

NCU가 미지원이어도 NVML energy run은 진행할 수 있다. 이 경우 보고서에는 “NCU counter 기반 stall/SOL 검증 미완료”라고 분리 기록한다.

## 4. 빌드

V100에서는 위에서 `compute_70` 지원을 확인한 CUDA 12.x compiler와
`CMAKE_CUDA_ARCHITECTURES=70`으로 빌드한다.

```bash
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="${NVCC}" \
  -DCMAKE_CUDA_ARCHITECTURES=70

cmake --build build-v100 --clean-first -j
```

conda/toolkit 경로를 명시해야 하는 환경이면 다음처럼 지정한다.

```bash
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/path/to/nvcc \
  -DCUDAToolkit_ROOT=/path/to/cuda \
  -DCMAKE_CUDA_ARCHITECTURES=70

cmake --build build-v100 --clean-first -j
```

빌드 로그에서 `ptxas` register count와 spill을 확인한다. 주요 kernel에서 `spill stores` 또는 `spill loads`가 발생하면 보고서에 위험으로 기록한다.
`git pull` 후 `src/`, `include/`, `CMakeLists.txt`가 바뀐 경우에는 반드시 clean rebuild를 한다.
특히 final run raw CSV는 C++ harness의 CSV header에 `measurement_scope` 컬럼이 있는
바이너리로 생성되어야 한다.

## 5. Harness preflight

빌드 후 preflight script로 profile, NCU, binary dry-run을 기록한다.

```bash
python3 scripts/preflight_gpu_support.py \
  --gpu 0 \
  --target-profile v100 \
  --strict \
  --min-device-memory-mib 30000 \
  --active-sm 80 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --ncu "${NCU:-$(command -v ncu)}" \
  --nvcc "${NVCC}" \
  --out results/summary/v100_gpu0_preflight.md
```

preflight에서 확인할 항목:

| 항목 | 기대값 |
|---|---|
| detected profile | `v100` |
| compute capability | `7.0` |
| visible device memory | 32GB reference이면 `memory.total >= 30000 MiB` |
| selected CUDA arch | `70` |
| CUDA compiler target | `target=compute_70`, `target_supported=true` |
| dry-run GPU | `dry_run_gpu: 0` 또는 preflight `--gpu`와 같은 index |
| dry-run active SM | `dry_run_active_sm: 80`, partition이면 runtime SM 수 |
| NCU chip | `gv100` |
| NCU query metrics | 지원 NCU면 `query_metrics_ok: true` |
| binary dry run | `return_code: 0` |

## 6. Dry-run sanity check

실제 측정 전 V100 profile의 feasibility를 확인한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_scalar_load_only \
  --w-sm-kib 32 \
  --blocks-per-sm 32 \
  --target-profile v100 \
  --active-sm 80 \
  --dry-run
```

기대:

| 출력 항목 | 기대값 |
|---|---|
| `target_profile` | `v100` |
| `compute_capability` | `7.0` |
| `max_blocks_per_SM` | `32` |
| `target_l2_MiB` | `6` |
| `target_shared_KiB_per_SM` | `96` |
| `mode_allowed` | strict/실행 좌표는 반드시 `true`; `false`이면 dry-run 종료 코드 2로 중단 |

탐색 단계에서는 `--target-profile auto`도 한 번 확인할 수 있지만, final package에
넣는 preflight는 `--target-profile v100 --strict`로 실행한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 2048 \
  --blocks-per-sm 32 \
  --target-profile auto \
  --dry-run
```

## 7. Smoke run

짧은 실행으로 CSV schema와 NVML energy source를 확인한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list none \
  --mode idle \
  --w-sm-kib 1 \
  --blocks-per-sm 1 \
  --target-profile v100 \
  --active-sm 80 \
  --seconds 1 \
  --repeats 1 \
  --output results/raw/v100_smoke_idle.csv
```

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 2048 \
  --blocks-per-sm 32 \
  --target-profile v100 \
  --active-sm 80 \
  --seconds 1 \
  --repeats 1 \
  --output results/raw/v100_smoke_reg_mma.csv \
  --verify-smid 1
```

register/tensor 분리 control도 짧게 확인한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_operand_only \
  --w-sm-kib 2048 \
  --blocks-per-sm 32 \
  --target-profile v100 \
  --active-sm 80 \
  --seconds 1 \
  --repeats 1 \
  --reuse-factor 2 \
  --output results/raw/v100_smoke_reg_operand_only.csv \
  --verify-smid 1
```

CSV에서 확인할 항목:

| 컬럼 | 기대 |
|---|---|
| `profile_name` | `v100` |
| `compute_capability` | `7.0` |
| `sm_count` | 보통 `80`, SKU/할당 환경에 따라 다를 수 있음 |
| `energy_source` | `nvml_total_energy` 우선, 미지원이면 fallback source 명시 |
| `measurement_scope` | `gpu_device_total_energy_counter` |
| `nvml_power_usage_semantics` | `instant` |
| `smid_histogram_ok` | active row에서 `true` |
| `expected_reg_operand_ops` | `reg_operand_only`, `reg_mma`에서 `active_SM * blocks/SM * ITER * reuse_factor` |

schema smoke audit:

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/v100_smoke_reg_mma.csv \
  --target-profile v100 \
  --out-csv results/summary/v100_smoke_power_api_audit.csv \
  --out-md results/summary/v100_smoke_power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope \
  --require-exact-measurement-interval \
  --require-mode-notes-marker \
  reg_mma=tensor_pair_kernel_revision=matched_inplace_signflip_observable_control_fixed_rf_v5
```

이 단계에서 모든 row가 `missing_column:measurement_scope`,
`missing_column:measurement_start_epoch_ms` 또는
`missing_explicit_measurement_scope`로 reject되면, V100 power counter 문제가 아니라
stale binary/schema 문제다. 현재 source를 pull한 뒤 `cmake --build build-v100
--clean-first -j`로 다시 빌드하고, 기존 `results/raw/v100_component_finalplan_*.csv`는
archive로 옮긴 뒤 재실행한다. 구버전 CSV에 새 row를 append하면 power API audit이
전체 reject될 수 있다.

`observable_control_fixed_rf_v5`는 RF1/2/4/8/16 모두 fixed-trip `unroll 1` kernel을 사용하고 한 A
fragment의 sign bit를 in-place로 뒤집어 FP32 accumulator를 bounded 상태로 유지한다. V100의 SASS lowering을
Ampere와 같다고 가정하지 않으며 V100 NCU에서
predicated HMMA=0, RF별 `HMMA/logical MMA` 상대 spread<=10%, control HMMA=0을 다시 확인해야 한다.
또한 `reg_operand_only`의 SASS에 backward loop가 있고 runtime
`SASS instructions/expected register op >= 0.1`이어야 한다. 이 gate가 없던 v4에서는
ptxas가 control 반복문을 제거할 수 있었으므로 v4 Tensor energy 결과를 재사용하지 않는다.

## 8. Full sweep 실행

아래 1 KiB-128 MiB sweep은 hierarchy 전이와 invalid 영역을 찾는 **broad
characterization**이다. final component coefficient를 만드는 표준 실행은 13장의 좁은
component별 좌표를 사용한다. broad sweep의 모든 mode/row가 final 후보인 것은 아니다.

요청 sweep 조건:

| sweep | 값 | 단위 |
|---|---|---|
| Sweep 1 | `blocks/SM = 4, 16, 32` | blocks/SM |
| Sweep 2 | `W_SM = 1 KiB`부터 `128 MiB`까지 2배 증가 | KiB/MiB |
| active SM | `80` | SMs |
| final seconds | `10` 이상 권장 | s |
| final repeats | `5` 이상 권장 | count |

Matrix만 먼저 생성:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --include-idle \
  --target-profile v100 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --active-sm-values 80 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/v100_full_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/v100_full_sweep_$(date +%Y%m%d)_matrix.csv
```

실행:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --include-idle \
  --execute \
  --target-profile v100 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --active-sm-values 80 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/v100_full_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/v100_full_sweep_$(date +%Y%m%d)_matrix.csv
```

짧은 sanity sweep:

```bash
python3 scripts/run_sweep.py \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --execute \
  --target-profile v100 \
  --gpu-ids 0 \
  --modes clocked_empty,reg_operand_only,reg_mma,shared_scalar_addr_only,global_addr_only,shared_scalar_load_only,global_l1_load_only,l2_cg_load_only,dram_cg_load_only \
  --w-sm-kib-values 32,64,128,512,8192 \
  --blocks-per-sm-values 1,8,16,32 \
  --active-sm-values 80 \
  --seconds 2 \
  --repeats 1 \
  --output results/raw/v100_sanity_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/v100_sanity_sweep_$(date +%Y%m%d)_matrix.csv
```

### Legacy component pair 실행

기존 `run_component_pairs.py` / `analyze_component_pairs.py` 방식은 현재 primary 경로가 아니다. 이 방식은 elapsed mismatch와 instruction-mix 차이가 커서 final component coefficient로 쓰기 어렵다.

관련 코드는 혼동 방지를 위해 archive로 이동했다.

```text
archive/legacy_20260707/scripts/run_component_pairs.py
archive/legacy_20260707/scripts/analyze_component_pairs.py
```

V100 component coefficient 후보는 이 문서 13장의 acceptance-first finalplan flow를 우선 사용한다.

## 9. NCU validation

NCU는 energy run과 분리해서 실행한다. V100은 NCU chip alias가 `gv100`이다.

Metric availability:

```bash
NCU="${NCU:-$(command -v ncu)}" NCU_CHIP=gv100 scripts/run_ncu.sh --query-metrics
```

대표 mode validation:

```bash
NCU="${NCU:-$(command -v ncu)}" \
NCU_CHIP=gv100 \
BIN=./build-v100/a100_fp16_energy_v2 \
TARGET_PROFILE=v100 \
ACTIVE_SM=80 \
GPU=0 \
DRAM_W_SM_KIB_VALUES=256,512,2048 \
OUTDIR=results/ncu/v100_validation_$(date +%Y%m%d) \
RAW_OUT=results/raw/v100_ncu_validation_sidecar_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

`DRAM_W_SM_KIB_VALUES=256,512,2048`는 full set 20/40/160 MiB,
즉 V100 6 MiB L2의 약 3.3/6.7/13.3/26.7배를 sweep한다. 최종 채택은 크기가
아니라 final L2 hit, DRAM read/source read, write contamination으로 결정한다.

권한 또는 버전 문제가 있으면 다음을 구분해서 기록한다.

| 오류/상태 | 의미 | 조치 |
|---|---|---|
| `ERR_NVGPUCTRPERM` | metric 목록 조회는 가능하지만 실제 hardware counter 권한 없음 | generated package의 사전 counter probe와 sudo retry 사용; 최종적으로 관리자 권한 정책 수정 권장 |
| `gv100` chip 미지원 | NCU 버전이 Volta를 지원하지 않음 | GV100 지원이 확인된 2024.3 계열을 우선 지정하고 `--list-chips`, metric query 재확인 |
| metric query 실패 | metric 이름/section 호환 문제 | `--query-metrics --chips gv100`로 metric availability 확인 |
| `selected=34 dropped=10` | GV100에 없는 optional metric 10개를 제외했다는 뜻 | drop 목록 보존; 필수 path evidence가 빠지면 acceptance에서 reject |
| `Running with uncontrolled GPU caches` | `--cache-control none`에 대한 NCU 경고 | warm/cache path를 유지하려는 현재 정책에서 비치명적; 반복 NCU hit/access 편차는 별도 확인 |
| `No kernels were profiled` | 해당 NCU report는 사용할 수 없음 | permission/kernel regex/target process를 해결하고 report를 다시 생성 |
| child-process warning | root process만 profile한 설정 경고 | 현행 wrapper는 `--target-processes all`을 사용 |

현행 generated package는 긴 energy sweep 전에 baseline hardware-counter profile을
실행한다. 일반 사용자 profile에서 `ERR_NVGPUCTRPERM`이 나오면 정확히 한 번
`sudo -E`로 같은 case를 재시도한다. wrapper는 `ncu_permission_mode.txt`에
`unprivileged`, `explicit_sudo`, `auto_sudo` 중 실제 mode를 기록한다. 자동 retry를 끄려면
`NCU_AUTO_SUDO=0`을 사용한다.

권한 오류 문자열은 동기식 `tee` pipeline이 stderr 로그 기록을 끝낸 뒤 판정한다. 따라서
로그 writer와 `grep ERR_NVGPUCTRPERM` 사이의 race가 없다. 또한 generated package의
permission fallback self-test는 `NCU_USE_SUDO`, `NCU_AUTO_SUDO`, `NCU_SUDO`를 제거한
환경에서 실행되고 self-test 내부에서도 같은 변수를 초기화한다. 전체 package를
`NCU_USE_SUDO=1`로 실행해도 self-test는 의도대로 unprivileged 실패에서 시작한다.

관리자가 non-admin GPU performance counter 접근을 허용하는 것이 가장 좋다. NVIDIA
공식 안내는 Linux에서 sudo/CAP_SYS_ADMIN, R565 이상에서는 CAP_PERFMON, 또는 driver
permission 설정을 제시한다. Legacy regkey 상태는 다음처럼 확인한다.

```bash
grep RmProfilingAdminOnly /proc/driver/nvidia/params
```

`1`이면 일반 사용자 counter 접근이 제한된 상태다. Legacy driver에서 영구 허용하려면
관리자가 `/etc/modprobe.d/*.conf`에 아래 값을 설정하고 initramfs 갱신 및 reboot를
수행한다. 실제 노드 운영정책을 먼저 확인한다.

```text
options nvidia NVreg_RestrictProfilingToAdminUsers=0
```

R610 이상은 `/proc/driver/nvidia-caps/sys-minors`의 `profiler-device` capability와
해당 `/dev/nvidia-caps/nvidia-cap*` 권한을 사용한다. 자세한 절차는 NVIDIA 공식
`ERR_NVGPUCTRPERM` 문서를 따른다:
https://developer.nvidia.com/nvidia-development-tools-solutions-ERR_NVGPUCTRPERM-permission-issue-performance-counters

관리자 정책을 즉시 변경할 수 없으면 처음부터 sudo mode로 실행할 수 있다.

```bash
NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh
```

기본 자동 fallback을 사용하려면 일반 명령 그대로 실행한다.

```bash
NCU_AUTO_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh
```

수동 NCU validation만 다시 돌릴 때는 기존 명령에 `NCU_USE_SUDO=1`을 붙인다.

```bash
NCU_USE_SUDO=1 \
NCU="${NCU:-$(command -v ncu)}" \
NCU_CHIP=gv100 \
BIN=./build-v100/a100_fp16_energy_v2 \
TARGET_PROFILE=v100 \
ACTIVE_SM=80 \
GPU=0 \
DRAM_W_SM_KIB_VALUES=256,512,2048 \
OUTDIR=results/ncu/v100_validation_$(date +%Y%m%d) \
RAW_OUT=results/raw/v100_ncu_validation_sidecar_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

`sudo`가 CUDA/Nsight Compute 경로를 지우는 환경이면 generated package에는
`NCU_BIN="$(command -v ncu)" NCU_SUDO="sudo -E"`를 같이 지정하고, 수동
`run_ncu_validation.sh`에는 `NCU="${NCU:-$(command -v ncu)}" NCU_SUDO="sudo -E"`를
같이 지정한다.

NCU가 실패해도 NVML energy run 자체와 섞지 말고, 보고서에는 “NCU counter 검증 미완료”로 분리 기록한다.

## 10. Mode 설명

보고서에는 mode 의미를 반드시 포함한다.

| mode | 의미 | 주 경로 |
|---|---|---|
| `idle` | 커널 없이 NVML energy delta 측정 | idle baseline |
| `empty` | 같은 persistent grid에서 MMA 없음 | loop/scheduler baseline |
| `reg_fragment_only` | WMMA fragment/register setup, MMA 없음 | fragment setup control |
| `reg_operand_only` | `reg_mma`와 같은 `ITER * reuse_factor` loop에서 sampled register fragment 값을 소비, MMA 없음 | no-MMA register-fragment/control baseline |
| `reg_mma` | register 값으로 WMMA fragment를 채우고 MMA 반복 | effective Tensor Engine + register |
| `shared_load_only` | shared memory operand staging 후 WMMA load, MMA 없음 | effective shared/L1 load control |
| `shared_mma` | shared memory operand staging 후 WMMA load + MMA | effective shared/L1 path |
| `l2_load_only` | L2 후보 global working set warm-up 후 load, MMA 없음 | effective L2-hit load control |
| `l2_mma` | L2에 들어가는 global working set warm-up 후 load + MMA | effective L2-hit path |
| `dram_load_only` | nominal L2보다 큰 global working set streaming load, MMA 없음 | effective DRAM streaming load control |
| `dram_mma` | nominal L2보다 큰 global working set streaming load + MMA | effective DRAM streaming path |
| `store_only` | 반복 global store loop, MMA 없음 | store-only control |
| `store_path` | global store/output-side overhead 확인 | store-side path |

## 11. 결과 정리

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
| NCU validation | mode, tensor %, L1 hit rate (%), L2 hit rate (%), L1 accesses (requests/sectors), L2 accesses (sectors), DRAM accesses (sectors), shared/L1/L2/DRAM bytes, achieved occupancy (%), registers/thread, static/dynamic shared/block (bytes), top stall %, status |

Plot 생성:

```bash
python3 scripts/plot_results.py \
  results/raw/v100_full_sweep_$(date +%Y%m%d).csv \
  --target-profile v100 \
  --outdir results/plots/v100_full_sweep_$(date +%Y%m%d)
```

주의:

- `seconds=1`, `repeats=1` 결과는 smoke/sanity 용도다.
- 최종 수치는 `seconds>=10`, `repeats>=5` 기준을 권장한다.
- `energy_source`가 다른 row는 같은 표에서 직접 비교하지 않는다.
- NCU replay 중 얻은 energy 값은 NVML energy CSV와 합치지 않는다.
- V100과 A100/H100의 Tensor Core 지원 데이터형은 다르므로 FP16 WMMA baseline끼리만 직접 비교한다.

## 12. 빠른 체크리스트

| 단계 | 확인 |
|---|---|
| node 상태 | GPU name에 `V100`, compute capability `7.0` |
| NCU | `gv100` chip 지원 여부 확인 |
| CUDA compiler | `nvcc --list-gpu-arch`에 `compute_70`; CUDA 12.x 권장, CUDA 13 build 금지 |
| build | `CMAKE_CUDA_ARCHITECTURES=70`, 주요 kernel spill 0 |
| preflight | `detected profile = v100`, binary dry-run 성공 |
| dry-run | `target_profile=v100`, `mode_allowed=true` |
| smoke | `energy_source` 기록, `smid_histogram_ok=true` |
| full sweep | raw CSV와 matrix CSV 모두 생성 |
| component pairs | `reg_mma_minus_reg_operand` pair와 단위 포함 summary 생성 |
| NCU | energy sweep 전 hardware-counter permission probe 통과; final sidecar report와 raw/details CSV 존재 |
| report | mode 설명 표와 단위 포함 sweep 표 작성 |

## 13. 2026-07-06 Component finalplan 업데이트

기존 `run_component_pairs.py` 방식은 legacy archive로 이동했다. V100에서 component coefficient 후보를 만들 때는 acceptance-first flow를 우선한다.

| 단계 | script | 목적 |
|---|---|---|
| command plan | `scripts/plan_platform_component_experiment.py` | V100용 표준 energy/NCU/analyze 명령 생성 |
| L2 NCU precheck | `scripts/select_l2_path_configuration.py` | energy 전에 normal residency의 layout/blocks-SM 후보를 strict gate로 선택; persisting은 V100에서 금지 |
| energy sweep | `scripts/run_component_regression_sweep.py` | NCU 없이 energy 수집. 모든 final pair에서 treatment/control-floor dual calibration의 최대 ITER를 두 mode에 동일 적용 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | path hit/access/stall/spill 검증 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | accepted component 후보만 선별 |
| matched-control | `scripts/analyze_matched_control_energy.py` | NCU actual-byte denominator로 pJ/bit 계산 |

표준 명령 생성:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --ncu "${NCU:-$(command -v ncu)}" \
  --active-sm 80 \
  --seconds 10 \
  --repeats 5
```

GPU index 7에서 기존 `20260710_gpu7` tag를 다시 생성하려면 다음처럼 index와 출력명을
명시한다. 새 shell에는 energy sweep 전 counter permission probe와 자동 sudo retry가
포함된다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 \
  --gpu-ids 7 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --ncu "${NCU:-$(command -v ncu)}" \
  --active-sm 80 \
  --seconds 10 \
  --repeats 5 \
  --tag 20260710_gpu7 \
  --out-sh results/summary/v100_component_finalplan_20260710_gpu7_commands.sh \
  --out-md results/summary/v100_component_finalplan_20260710_gpu7_command_plan.md
```

생성 shell은 `NVCC` 환경변수를 preflight에 전달한다. 기본 `nvcc`가 CUDA 13이면 다음처럼
CUDA 12.x compiler를 명시한다. NCU 경로는 별도의 `NCU_BIN`으로 지정할 수 있다.

```bash
NVCC=/path/to/cuda-12/bin/nvcc \
NCU_BIN=/path/to/nsight-compute-2024.3/ncu \
bash results/summary/v100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/v100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

V100 추천 finalplan 좌표:

RTX 3090/A100/V100의 전체 파라미터와 command 개수 비교는
[cross-platform component experiment guide](cross_platform_component_experiment_guide_ko.md)의
4.0-4.5절을 기준으로 한다. 현재 V100 표준 package는 L2 precheck가 선택한 blocks/SM
하나만 L2 energy에 사용한다. 유효 좌표는 72개/1 repeat, `repeats=5`에서 energy raw
360행이며 Tensor pair calibration 15 coordinates/30 commands, L2 pair calibration
6 coordinates/12 commands, external-memory pair calibration 9 coordinates/18 commands, schema
smoke 3행, primary NCU 73 cases다. L2 selector는 첫 후보 통과 시 조기 종료하며
최악에는 4 candidates x 2 W x 2 modes = 16개 NCU precheck case를 추가한다.

`seconds=10 s` 기준 nominal energy kernel 시간은 `360 x 10 s = 3,600 s`, 즉 1시간이다.
calibration, launch, audit와 73-case NCU replay 및 L2 precheck를 포함한 노드 전체
예상시간은 보통 약 2~5시간이며 NCU metric replay 횟수와 노드 부하에 따라 달라진다.
후보가 늦게 선택되면 NCU precheck 시간만큼 더 필요하다.

| Component | modes | energy W_SM (KiB) | energy blocks/SM | strict NCU W_SM/B | factor |
|---|---|---:|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | N/A (CLI placeholder 1) | 4,16,32 | 1/4,16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `shared_scalar_addr_only,shared_scalar_load_only` | 32 | 32 | 32/32 | energy/NCU load_repeat 4,8,16; 동일 pair ITER |
| Global L1 | `global_addr_only,global_l1_load_only` | 32 | 32 | 32/32 | energy/NCU load_repeat 4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 32,64 | NCU가 32/16/4 중 선택 | 32,64/selected B | energy/final NCU load_repeat 4,8,16; selector LR4 |
| External-memory read path | `global_addr_only,dram_cg_load_only` | 256,512,2048 | 32 | 동일 W/B | energy/NCU load_repeat 4,8,16 |

### V100 sweep를 그래프로 해석하기

![플랫폼별 blocks/SM sweep](../presentations/assets/platform_blocks_per_sm_sweep.png)

V100 B4/B16/B32는 Tensor utilization sweep이고 Shared/Global-L1/external-memory는 B32만
사용한다. B4나 B16이 L2 selector에서 선택되면 해당 좌표의 exact-coordinate
`l2_path_minimal` NCU가 자동 수집된다.

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

- Shared strict W32/B32는 `W+B=64 KiB/SM`이며 energy와 NCU가 동일 좌표다.
- Global L1 W32/B32는 block당 1 KiB를 확보하는 단일 strict anchor다.
- L2 W32는 전체 2.5 MiB로 6 MiB L2의 약 42%, W64는 5 MiB로 약 83%인 stress 점이다.
- External-memory W256/512/2048은 전체 20/40/160 MiB다. Shared는 별도 address space이며 이 L1-L2-external-memory
  global hierarchy 전이축과 섞어 해석하지 않는다.

현행 분석은 `--require-control-ncu-acceptance`를 사용한다. 따라서 V100에서도
`reg_operand_only`와 `global_addr_only`가 각 treatment와 동일
`W_SM/B/active_SM/RF 또는 LR` 좌표에서 NCU accepted여야 한다. treatment만 통과한
row는 strict coefficient가 아니다.

Tensor는 각 B/RF 좌표에서 treatment 목표와 no-MMA control 최소시간을 각각 calibration하고
두 candidate ITER의 최대값을 treatment/control에 동일하게 적용한다. 표준 10 s package는
control floor 1 s를 사용한다. `*_tensor_pair_calibration.csv`, 두 raw mode의 ITER,
matched detail의 `pair_energy_basis=matched_iters_net_energy`와 `iter_ratio=1`이 모두
일치해야 final Tensor 후보가 된다. 이 정책은 A100 RF4 이상에서 드러난 mode별 duration
calibration mismatch를 V100에서도 예방한다.
L2 CG pair도 같은 정책을 사용한다. 각 W/B/LR 좌표에서 `l2_cg_load_only` 목표시간
ITER와 `global_addr_only` 최소 control 시간 ITER를 각각 구하고, 두 candidate 중 큰 값을
양쪽에 전달한다. 분석은 `--l2-pair-policy matched-iters`로
`net_E(l2_cg_load_only) - net_E(global_addr_only)`를 직접 계산한다.
`*_l2_pair_calibration.csv`, raw 두 mode의 동일 `ITER`, matched detail의
`pair_energy_basis=matched_iters_net_energy`와 `iter_ratio=1`이 모두 필수다.

2026-07-13 이전 실행에서 L2 NCU acceptance가 L2 read hit 약 99.9996%, L1 hit 0%로
통과했지만 `global_addr_only` ITER가 `l2_cg_load_only`보다 약 2배 많아 9개 좌표가 모두
음수였던 결과는 폐기한다. NCU 결과는 경로가 L2였다는 증거일 뿐, 서로 다른 작업량을 뺀
energy numerator를 정당화하지 않는다. 이 경우 L2 energy sweep과 matched-control 이후
단계를 다시 실행해야 하며, 기존 음수 `-12~-9 pJ/byte`를 L2 계수로 보고하면 안 된다.
External-memory pair도 동일한 원칙을 사용한다. 각 W/B/LR 좌표에서 `dram_cg_load_only`의 목표
시간 ITER와 `global_addr_only`의 최소 control 시간 ITER를 구하고, 그중 큰 동일
ITER를 양쪽에 전달한다. 분석은 `--dram-pair-policy matched-iters`로 두
idle-corrected `net_E`를 직접 차분한다. `*_dram_pair_calibration.csv`가 없거나 raw
`ITER`가 다르거나 matched detail의 `iter_ratio`가 1이 아니면 V100 external-memory
결과는 reject한다. 분모는 NCU `dram__bytes_read.sum`만 사용한다.

두 kernel은 source상 fragment, phase, dependent scalar update, epilogue를 공통으로
두지만 ptxas 최적화 후 control의 register footprint는 더 작다. 따라서
control은 lightweight no-MMA baseline이며 차분값은 pure Tensor 회로 에너지가 아니다.

Energy sweep의 Tensor/Shared/L1/DRAM B4/B16은 utilization 변화와 추세를 보는
diagnostic이다. L2는 precheck가 선택한 B 하나만 energy와 minimal coherent NCU에 동일 적용한다.

좌표 선정 근거:

| 좌표 | 계산과 의미 |
|---|---|
| Global L1 strict W32/B32 | block당 1 KiB tile을 만족하며 32 KiB/SM은 shared를 쓰지 않는 Volta combined 128 KiB cache보다 작음 |
| L2 precheck W32/W64 | 전체 2.5/5 MiB를 normal residency에서 B32 contiguous부터 sm_interleaved B32/B16/B4 순서로 검증 |
| L2 stress W64 | `80 SM x 64 KiB = 5 MiB`, 6 MiB L2의 약 83%라 conflict/background traffic 민감도를 보는 보조점 |
| Shared strict W32/B32 | feasibility의 보수적 계산 `W_SM + B = 64 KiB/SM`, 96 KiB shared 한도 아래 |
| Shared stress W64/B32 | `W_SM + B = 96 KiB/SM`으로 capacity 경계점이므로 strict 기본점이 아닌 stress 보조점 |

V100은 6 MiB L2라 capacity 기반 `l2_load_only`가 L1 hit와 쉽게 섞일 수 있다. 따라서 L2 후보는 우선 `l2_cg_load_only`로 잡고, NCU에서 다음을 확인한다.
CG mode의 warm-up도 `ld.global.cg.u32` 전용 kernel을 사용해 normal warm-up이 L1을
미리 채우지 않도록 한다.
CUDA persisting-L2 control은 compute capability 8.0 이상 기능이므로 V100(CC 7.0)에서는
사용하지 않는다. `persisting` 후보가 plan 또는 selection CSV에 보이면 잘못된 실행이다.

| NCU 기준 | 통과 조건 |
|---|---:|
| L2 CG | path-specific L2 read hit >=95%, L2 read bytes 존재, L1 path hit <=1%, L1 hit/request bytes <=1%, DRAM/L2 read bytes <=2% |
| Global L1 | L1 hit >= 95%, L1 access/bytes 존재, L2/L1 bytes <= 1% |
| Shared scalar | shared access/bytes 존재, bank conflict 0 또는 매우 낮음 |
| Tensor | HMMA > 0, spill/local 0 |

새 raw CSV는 시작 epoch에 monotonic `steady_clock` elapsed를 결합한 exact interval을 기록하고 matched-control은
`pair_transition_gap_ms<=pair_transition_gap_limit_ms`를 검사한다. 생성 plan의
한계는 `max(30000, (seconds+15)x1000)` ms이므로 표준 10초 run은 30,000 ms,
20초 stability run은 35,000 ms다. 과거 `pair_start_distance_ms`는 두 완료
시각 차이여서 treatment 실행시간과 매 실행의 idle baseline이 섞였고 정상 인접 pair를
오탈락시킬 수 있었다. 이전 raw 재분석은 `run_id-elapsed_s` 추정임을 명시한다.
추정 timing row는 진단용으로만 유지하며 strict final package는 새 binary가 기록한 exact
epoch interval을 요구한다.
새 runner는 반복과 좌표 index를 함께 사용해 pair 방향을 counterbalance하고 strict package는 양쪽 실행 순서의 valid row를
모두 요구해 일방향 thermal/clock drift를 검출한다.

B32 row에서는 위 path 기준과 별도로 achieved occupancy, registers/thread, static/dynamic
shared/block을 표에 남긴다. 이 값이 없으면 B32를 “32 blocks가 동시에 resident였다”고
표현하지 않는다. V100 compiler가 달라지면 register allocation도 달라질 수 있으므로
CUDA 12.x build마다 다시 확인한다.

V100에서 NCU `gv100` 지원이 안 되면 component coefficient를 최종값으로 보고하지 않는다. 이 경우 energy raw CSV는 남기되, 보고서에는 “NCU path acceptance 미완료”라고 분리 기록한다.

V100에서 `nvcc`가 `compute_70`을 지원하지 않으면 binary build/preflight 단계에서
중단한다. 이미 존재하는 binary를 우연히 실행할 수 있더라도, 어떤 compiler/arch로
만들었는지 검증되지 않은 binary로 새 final package를 승인하지 않는다.

Generated V100 package는 `NCU_CHIP=gv100`으로 metric availability를 먼저 query하고,
GV100에서 제공되지 않는 선택 metric은 NCU 실행 목록에서 제외한다. 제외 목록은 artifact로
남기며, 필수 hit/access/byte/HMMA/stall evidence가 사라진 path는 acceptance 단계에서
그대로 reject한다. Metric filter는 missing evidence를 통과시키는 우회 수단이 아니다.
