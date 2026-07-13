# A100 노드 실험 실행 가이드

작성일: 2026-07-08, updated 2026-07-14

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
  --require-mode-notes-marker \
  reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2
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
NCU_USE_SUDO=1 bash results/summary/a100_component_finalplan_20260708_commands.sh
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
| energy sweep | `scripts/run_component_regression_sweep.py` | NCU 없이 energy 수집. Shared/Global L1은 duration-calibrated, Tensor/L2 CG/DRAM CG는 treatment/control-floor dual calibration의 최대 ITER를 양쪽에 동일 적용 |
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

기존 실행에서 Tensor RF4 이상 음수/weak 또는 L2 CG path reject를 재현한 경우에는 full
package를 반복하기 전에 다음 targeted remediation package를 실행한다.

```bash
NCU_USE_SUDO=1 bash results/summary/a100_tensor_l2_remediation_20260710_commands.sh
```

실행 조건과 pass 기준은
[`a100_tensor_l2_remediation_20260710_command_plan.md`](../../results/summary/a100_tensor_l2_remediation_20260710_command_plan.md)에 정리되어 있다.
전용 audit가 pass한 뒤에만 표준 finalplan을 다시 실행해 Shared/L1/DRAM과 합친다.

2026-07-13 A100 후속 실행에서 Tensor는 dual calibration 후 RF1-16 모두 양수
0.35-0.54 pJ/FLOP였지만, L2 path-specific hit는 W16/32/64/128에서 58.5-60.1%로
strict 95% 기준을 통과하지 못했다. 이 수치는 final component table에 넣지 않는다.
Tensor 값도 local raw/NCU artifact와 `fixed_rf_v2` marker 증거가 없으므로 새 package로
RF1-16 전체를 재측정해야 한다. 현행 동일 protocol RTX 3090 median은 2.2525 pJ/FLOP이며,
과거 0.129-0.146 pJ/FLOP를 비교 기준으로 사용하면 안 된다.
최신 targeted script는 긴 energy sweep 전에 다음 순서로 fail-fast한다.

| 순서 | 조건 | 통과 의미 |
|---:|---|---|
| 1 | normal/contiguous/B16, W_SM 16/128 KiB, LR4, NCU application replay, CG warm-up 4회 | 두 W treatment/control이 모두 strict gate를 통과하면 기본 layout 선택 |
| 2 | normal `sm_interleaved` B16, B8, B4 | 128 B guard와 virtual-grid block-region 전치, 동시 blocks/SM 변경으로 address-topology conflict 진단 |
| 3 | 모든 normal 실패 시 persisting contiguous/B16과 sm_interleaved B16/B8/B4 | residency policy 효과 진단. API/metric unavailable이면 strict 미선정 |
| 4 | 선택된 policy/layout/B로 W16/32/64/128, LR1/2/4/8/16 full NCU | derived/native hit, sector conservation, observed/expected traffic, DRAM traffic 재검증 |
| 5 | 같은 구성으로 LR4/8/16 energy sweep | exact NCU denominator와 양수 차분으로 pJ/bit 계산 |

8개 후보가 모두 실패하면 script가 energy sweep 전에 종료되는 것이 정상이다.
MIG에서는 persisting L2 set-aside를 사용할 수 없을 수 있으므로 모든 normal 후보도
실패하면 해당 partition에서는 strict L2 coefficient가 없다고 보고한다.

특히 기존 58.5-60.1%는 lookup hit/miss에서 계산한 비율만으로 실제 capacity/residency
miss라고 확정하지 않는다. 최신 summary에서 `l2_native_read_hit_rate_pct`,
`l2_native_vs_derived_hit_delta_pct`, `l2_read_sector_conservation_ratio`,
`l2_read_bytes_to_expected`, `l2_read_miss_bytes`, `dram_read_bytes`,
`launch_persisting_l2_cache_size_bytes`를 함께 확인한다.
두 hit rate가 95% 이상, 차이가 2 percentage points 이하, sector conservation이
0.98-1.02, observed/expected traffic이 0.95-1.05여야 strict precheck를 통과한다.

RTX 3090/A100/V100의 전체 파라미터와 command 개수 비교는
[cross-platform component experiment guide](cross_platform_component_experiment_guide_ko.md)의
4.0-4.5절을 기준으로 한다. 현재 A100 표준 package는 유효 좌표 116개/1 repeat,
`repeats=5` 적용 후 energy raw 580행, Tensor pair calibration 10 coordinates/20 commands,
L2 pair calibration 21 coordinates/42 commands, DRAM pair calibration 6 coordinates/12 commands, schema/revision smoke 3행,
primary NCU 74 cases다.

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 64,128 | 16,32 | energy load_repeat 4,8,16; NCU 1,2,4,8,16 |
| Global L1 | `global_addr_only,global_l1_load_only` | 16,32 | valid W/B: 16/16, 32/16, 32/32 | energy load_repeat 4,8,16; strict NCU W16/B16, NCU factor 1,2,4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 16,32,64,128 | valid W/B: 16/16, 32/16,32, 64/16,32, 128/16,32 | energy load_repeat 4,8,16; 동일 pair ITER; NCU는 네 W 모두에서 1,2,4,8,16 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | 16,32 | energy load_repeat 4,8,16; NCU 1,4,8,16 |

### A100 sweep를 그래프로 해석하기

![플랫폼별 W_SM path sweep](../presentations/assets/platform_wsm_path_sweep.png)

- Shared W64/W128은 164 KiB shared allocation profile 안에서 낮은 점과 높은 점을 비교한다.
  strict W128/B16의 보수적 예약량은 `128+16=144 KiB/SM`이다.
- Global L1 W16/W32는 B16/B32에서 block당 1 KiB 이상을 유지하는 작은 cached-global
  working set이다. W16/B32는 0.5 KiB/block이므로 실행하지 않는다.
- L2 W16/W32/W64/W128은 전체 1.688/3.375/6.75/13.5 MiB로 40 MiB L2 안의
  plateau 후보다. 네 점 모두 L2라는 뜻이 아니라 NCU L1 bypass와 L2 read hit를 통과한
  점만 채택한다.
- DRAM W8192는 전체 864 MiB로 L2보다 충분히 크지만, capacity-aware residual L2 hit와
  DRAM bytes dominance가 확인되어야 sanity 후보가 된다.

![strict anchor capacity 맥락](../presentations/assets/platform_capacity_context.png)

A100 L2 strict anchor W16은 nominal L2의 약 4.2%에 불과하므로 대표값 하나만으로 다른
GPU의 40-85% anchor와 직접 비교하지 않는다. A100은 네 W의 coefficient/hit/stall plateau를
함께 보고 선택한다.

Tensor는 각 `W/B/SM/RF` 좌표에서 `reg_mma`를 treatment 목표시간으로,
`reg_operand_only`를 control 최소시간으로 각각 calibration하고 두 ITER 중 큰 값을
두 mode에 똑같이 전달한다. 표준 10 s package의 control floor는 1 s이고, A100 targeted
20 s package는 2 s다. 생성되는 `*_tensor_pair_calibration.csv`에는 두 candidate ITER,
선택 정책, calibration command와 resolved ITER가 남는다.
분석은 `--tensor-pair-policy matched-iters`를 사용해 elapsed-time power scaling 없이
`net_E(reg_mma) - net_E(reg_operand_only)`를 직접 계산한다. 두 ITER가 다르거나 calibration
manifest가 없는 새 package는 final Tensor evidence로 채택하지 않는다.
두 kernel은 RF당 dependent register integer add 1개를 공통으로 실행한다.
control의 기존 FP32 FMA/checksum/memory는 제거되었고, 공통 add는 direct
energy 차분에서 상쇄된다.
두 mode 모두 WMMA store를 쓰지 않고 per-thread 8개 scalar store로 같은 1,024
bytes/block 주소 패턴을 사용한다. treatment는 accumulator fragment를 저장해 HMMA를
보존하고 control은 sink 값을 저장하므로 control HMMA 오염을 피한다.
raw Tensor row의 `notes`에는
`tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2`이 있어야 한다.
RF1은 정확성이 확인된 dynamic loop를 사용하고 RF2/4/8/16은 fixed-trip `unroll 1`
treatment/control kernel을 사용한다. 이 분기는 target A100에서도 RF별
`HMMA/logical MMA` 상대 spread 10% 이하를 통과해야만 유효하다.
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

DRAM은 각 `W_SM/blocks/SM/load_repeat` 좌표에서 `dram_cg_load_only`를 목표
측정시간으로, `global_addr_only`를 최소 control 시간으로 각각 calibration한 뒤 두
ITER 중 큰 값을 두 mode에 동일하게 전달한다. 분석은
`--dram-pair-policy matched-iters`를 사용하여 elapsed power scaling 없이
`net_E(dram_cg_load_only) - net_E(global_addr_only)`를 직접 계산한다. 생성되는
`*_dram_pair_calibration.csv`, 두 raw mode의 `ITER`, matched detail의
`pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`이 모두 일치해야 DRAM
sanity 후보가 된다. Duration-calibrated DRAM 값은 플랫폼 비교용 final evidence가 아니다.

`W16/B32`는 block당 0.5 KiB이므로 Global L1과 L2 CG의
`global_addr_only`/treatment 모두 matrix에서 `valid=false`로 남기고 실행하지 않는다.
B32 L1 diagnostic은 W32/B32에서만 수행한다. 표준 runner는 energy 수집 전에 unique valid 좌표를
binary `--dry-run`으로 다시 검사하므로 Python/C++ feasibility가 어긋나면 첫 측정 전에
명확한 좌표와 return code를 출력하고 중단한다.

A100의 L2는 40 MiB이므로 `W_SM=256 KiB`와 active SM 108개는 전체 27 MiB로 L2 경계에 너무 가깝다. 이 설정은 L2 set/conflict와 background traffic에 따라 hit rate가 흔들릴 수 있다. strict L2 path는 `W_SM=16,32,64,128 KiB`(전체 약 1.688, 3.375, 6.75, 13.5 MiB)를 모두 `ld.global.cg`로 실행하고, path-specific NCU counter에서 L1 hit가 거의 없으면서 L2 read hit가 95% 이상인 plateau만 선택한다. 시간 측정 전 warm-up도 `global_cg_warmup_kernel`의 `ld.global.cg.u32`로 4회 수행한다. NCU는 `application replay + cache-control none`을 사용해 metric pass마다 application과 warm-up을 다시 실행한다. `l2_load_only`는 normal global load라 L1 hit와 섞일 수 있으므로 final L2 coefficient에는 사용하지 않는다.

CG raw row의 `notes`에는 `global_warmup_policy=ld_global_cg`가 있어야 하며,
없으면 stale binary로 보고 package audit에서 reject한다.

| NCU 기준 | 통과 조건 |
|---|---:|
| Global L1 | path-specific L1 hit >= 95%, L1 request bytes 존재, L2/L1 request bytes <= 1% |
| L2 CG | NCU application replay/cache-control none, 선택 residency/layout/B와 warm-up 4회 metadata 일치, derived/native L2 read hit >=95%, 두 값 차이<=2 percentage points, hit+miss/read sectors=1+/-2%, observed/expected L2 bytes=0.95-1.05, L1 path hit<=1%, L1 hit/L1 request bytes<=1%, DRAM/L2 read bytes<=2% |
| Shared scalar | shared access/bytes 존재, bank conflict 0 또는 매우 낮음 |
| Tensor | treatment HMMA > 0, control HMMA=0, spill/local 0, treatment-control ITER 동일, RF1-16의 `HMMA/logical MMA` 상대 spread<=10%. legacy epilogue 완화는 과거 결과 설명용이며 새 final run에는 사용하지 않음 |

`global_addr_only`는 `global_l1_load_only`, `l2_cg_load_only`, `dram_cg_load_only`와 동일한 block/tile/index/repeat loop를 실행하지만 global input load는 수행하지 않는다. 따라서 memory pair의 차분은 단순 `clocked_empty` 대비보다 주소 계산과 loop 비용을 더 잘 제거한다. NCU sidecar에서는 global-load L1 request byte가 0인지 확인한다. `--verify-smid=1` atomic bookkeeping 때문에 L2 sector가 소량 보일 수 있으므로 L2 sector 0을 요구하지 않는다.

분석 단계의 `--require-control-ncu-acceptance`는 이 조건을 mode-level이 아니라
동일 `W_SM/B/active_SM/LR` 좌표로 요구한다. A100 treatment가 accepted여도 대응
`global_addr_only`가 reject이면 해당 계수 row는 생성하지 않는다.

`l2_cg_load_only`에서는 반대로 L1 request byte가 존재해야 한다. `.cg` global load도 요청은
L1TEX를 통과하므로 `L1 request bytes / L2 read bytes`가 약 1인 것은 L1 cache hit 증거가
아니다. 이 경로는 path-specific `L1 hit bytes/request bytes <=1%`와
`L2 read hit >=95%`로 판정한다. aggregate L1/L2 hit rate는 함께 표기하되 hard gate로
사용하지 않는다.

보고서에는 `board-level effective coefficient`, `not pure physical component energy`를 명시한다. A100의 HBM2 물리 pJ/bit 문헌값과 본 실험의 DRAM streaming pJ/bit는 같은 의미가 아니다.
