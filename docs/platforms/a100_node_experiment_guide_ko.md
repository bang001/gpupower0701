# A100 노드 실험 실행 가이드

작성일: 2026-07-08

## 목적

이 문서는 A100 기준 노드에서 FP16 Tensor Core energy microbenchmark를 재현하기 위한 실행 가이드다. 기본 목표는 A100 profile에서 `blocks/SM`, `W_SM` sweep을 수행하고, NVML energy 결과와 NCU sidecar 검증 결과를 분리해서 수집하는 것이다.

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
  --ncu "$(command -v ncu)" \
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

```bash
cmake -S . -B build-a100 \
  -DCMAKE_BUILD_TYPE=Release \
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
| `mode_allowed` | `true` 또는 의도한 skip reason |

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
  --require-explicit-measurement-scope
```

이 단계에서 모든 row가 `missing_column:measurement_scope` 또는
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

이 경우 관리자가 performance counter 접근을 허용하거나 root/admin 권한으로 NCU를 실행해야 한다. NCU가 실패해도 NVML energy run 자체와 섞지 말고, 보고서에는 “NCU counter 검증 미완료”로 분리 기록한다.

## 8. Mode 설명

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
| energy sweep | `scripts/run_component_regression_sweep.py` | NCU 없이 duration-calibrated energy row 수집 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | path hit/access/stall/spill 검증 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | accepted component 후보만 선별 |
| matched-control | `scripts/analyze_matched_control_energy.py` | NCU actual-byte denominator로 pJ/bit 계산 |

표준 명령 생성:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --active-sm 108 \
  --seconds 10 \
  --repeats 5
```

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

A100 추천 finalplan 좌표:

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 64,128 | 16,32 | load_repeat 1,2,4,8,16 |
| Global L1 | `clocked_empty,global_l1_load_only` | 16,32 | 16,32 | load_repeat 1,2,4,8,16 |
| L2 capacity/CG | `clocked_empty,l2_load_only,l2_cg_load_only` | 256 | 16,32 | load_repeat 1,2,4,8,16 |
| DRAM sanity | `clocked_empty,dram_cg_load_only` | 8192 | 16,32 | load_repeat 1,4,16 |

A100은 40 MiB L2가 있으므로 `W_SM=256 KiB`에서 capacity 기반 `l2_load_only`가 L2 후보가 될 수 있다. 하지만 최종 채택은 NCU 기준이다.

| NCU 기준 | 통과 조건 |
|---|---:|
| Global L1 | L1 hit >= 95%, L1 access/bytes 존재, L2/L1 bytes <= 1% |
| L2 capacity | L1 hit <= 1%, L2 hit >= 95%, L2 access/bytes 존재, DRAM/L2 bytes <= 2% |
| Shared scalar | shared access/bytes 존재, bank conflict 0 또는 매우 낮음 |
| Tensor | HMMA > 0, spill/local 0 |

보고서에는 `board-level effective coefficient`, `not pure physical component energy`를 명시한다. A100의 HBM2 물리 pJ/bit 문헌값과 본 실험의 DRAM streaming pJ/bit는 같은 의미가 아니다.
