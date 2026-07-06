# V100 노드 실험 실행 가이드

작성일: 2026-07-02

## 목적

이 문서는 V100 기준 노드에서 FP16 Tensor Core energy microbenchmark를 재현하기 위한 실행 가이드다. 기본 목표는 V100 profile에서 `blocks/SM`, `W_SM` sweep을 수행하고, NVML energy 결과와 NCU sidecar 검증 결과를 분리해서 수집하는 것이다.

V100은 Volta GV100 / compute capability 7.0 GPU이므로 A100/RTX 3090/H100과 비교할 때 다음 차이를 반드시 분리해서 기록한다.

- CUDA build arch는 `sm_70`이다.
- FP16 Tensor Core baseline은 가능하지만 TF32/BF16/FP64 Tensor Core baseline은 A100/H100과 다르다.
- 최신 Nsight Compute release highlights에는 Volta/GV100 support 제거가 공지되어 있다. V100 NCU 검증은 `ncu --list-chips`에 `gv100`이 있는 toolchain으로 진행한다.
- NVML `GetPowerUsage` 의미는 instantaneous로 취급한다. 최종 비교에서는 `energy_source`와 `nvml_power_usage_semantics`를 반드시 표기한다.

## V100 기준 profile

| 항목 | 값 | 단위 |
|---|---:|---|
| GPU profile | `v100` | - |
| architecture | Volta GV100 | - |
| compute capability | 7.0 | - |
| CUDA arch flag | `sm_70` | - |
| default full SM count | 80 | SMs |
| nominal L2 | 6 | MiB |
| combined L1/shared profile | 128 | KiB/SM |
| shared allocation profile | 96 | KiB/SM |
| max dynamic shared memory per block | 96 | KiB/block |
| max resident blocks per SM | 32 | blocks/SM |
| NVML `GetPowerUsage` 의미 | instantaneous | mW |
| NCU chip alias | `gv100` | - |

주의: V100 PCIe/SXM, MIG가 아닌 다른 가상화 환경, 클러스터 할당 정책에 따라 보이는 GPU와 clock/power state가 달라질 수 있다. 실행 전 preflight 결과의 runtime SM 수와 power limit을 확인한다. `combined L1/shared profile`은 SM 내부 통합 capacity이고, `shared allocation profile`은 shared-memory 실험 feasibility에 쓰는 CUDA shared capacity다.

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
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
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

## 3. NCU toolchain 확인

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
| `gv100` 없음 또는 query 실패 | 현재 NCU로 Volta profiling 불가 | `gv100`을 지원하는 NCU toolchain 지정. 2024.3/2025.1 계열은 예시 |

예시:

```bash
export NCU=/path/to/nsight-compute-2024.3/ncu
"${NCU}" --version
"${NCU}" --list-chips | tr ',' '\n' | grep -i gv100
```

NCU가 미지원이어도 NVML energy run은 진행할 수 있다. 이 경우 보고서에는 “NCU counter 기반 stall/SOL 검증 미완료”라고 분리 기록한다.

## 4. 빌드

V100에서는 `CMAKE_CUDA_ARCHITECTURES=70`으로 빌드한다.

```bash
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=70

cmake --build build-v100 -j
```

conda/toolkit 경로를 명시해야 하는 환경이면 다음처럼 지정한다.

```bash
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/path/to/nvcc \
  -DCUDAToolkit_ROOT=/path/to/cuda \
  -DCMAKE_CUDA_ARCHITECTURES=70

cmake --build build-v100 -j
```

빌드 로그에서 `ptxas` register count와 spill을 확인한다. 주요 kernel에서 `spill stores` 또는 `spill loads`가 발생하면 보고서에 위험으로 기록한다.

## 5. Harness preflight

빌드 후 preflight script로 profile, NCU, binary dry-run을 기록한다.

```bash
python3 scripts/preflight_gpu_support.py \
  --gpu 0 \
  --target-profile auto \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --ncu "${NCU:-$(command -v ncu)}" \
  --out results/summary/v100_gpu0_preflight.md
```

preflight에서 확인할 항목:

| 항목 | 기대값 |
|---|---|
| detected profile | `v100` |
| compute capability | `7.0` |
| selected CUDA arch | `70` |
| NCU chip | `gv100` |
| NCU query metrics | 지원 NCU면 `query_metrics_ok: true` |
| binary dry run | `return_code: 0` |

## 6. Dry-run sanity check

실제 측정 전 V100 profile의 feasibility를 확인한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_mma \
  --w-sm-kib 64 \
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
| `mode_allowed` | `true` 또는 의도한 skip reason |

`--target-profile auto`도 한 번 확인한다.

```bash
./build-v100/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
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
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
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
  --w-sm-kib 32 \
  --blocks-per-sm 16 \
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
| `nvml_power_usage_semantics` | `instant` |
| `smid_histogram_ok` | active row에서 `true` |
| `expected_reg_operand_ops` | `reg_operand_only`, `reg_mma`에서 `active_SM * blocks/SM * ITER * reuse_factor` |

## 8. Full sweep 실행

요청 sweep 조건:

| sweep | 값 | 단위 |
|---|---|---|
| Sweep 1 | `blocks/SM = 1, 2, 4, 8, 16, 32` | blocks/SM |
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
  --modes empty,reg_fragment_only,reg_operand_only,reg_mma,shared_mma,l2_mma,dram_mma,store_path \
  --w-sm-kib-values 32,64,128,512,8192 \
  --blocks-per-sm-values 1,8,16,32 \
  --active-sm-values 80 \
  --seconds 2 \
  --repeats 1 \
  --output results/raw/v100_sanity_sweep_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/v100_sanity_sweep_$(date +%Y%m%d)_matrix.csv
```

### Component pair 실행

component-like coefficient를 계산할 때는 mode별 raw sweep만 쓰지 말고 pair runner를 별도로 실행한다. 이 runner는 각 좌표에서 reference mode를 calibration하고 같은 `ITER`를 control mode에 재사용한다.

```bash
python3 scripts/run_component_pairs.py \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --execute \
  --target-profile v100 \
  --gpu-ids 0 \
  --groups register,shared,l2,dram,store \
  --w-sm-kib-values 32,64,128,512,8192 \
  --blocks-per-sm-values 1,8,16,32 \
  --active-sm-values 80 \
  --reuse-factors 1,2,4,8 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/v100_component_pairs_$(date +%Y%m%d).csv \
  --matrix-csv results/raw/v100_component_pairs_$(date +%Y%m%d)_matrix.csv
```

분석:

```bash
python3 scripts/analyze_component_pairs.py \
  results/raw/v100_component_pairs_$(date +%Y%m%d).csv \
  --out-csv results/summary/v100_component_pair_summary_$(date +%Y%m%d).csv \
  --out-md results/summary/v100_component_pair_summary_$(date +%Y%m%d).md
```

중요한 register/tensor 해석:

| pair | 해석 | 단위 |
|---|---|---|
| `reg_operand_only - empty` | no-MMA register-fragment/control baseline | pJ/reg-op |
| `reg_mma - reg_operand_only` | effective Tensor Core MMA incremental cost 후보 | pJ/FLOP |
| `reg_mma - empty` | 기존 effective Tensor Engine + register path baseline | pJ/FLOP |

`reg_operand_only`는 pure register energy가 아니라 sampled fragment consume과 compiler 최적화 방지 경로가 포함된 matched control이다.

## 9. NCU validation

NCU는 energy run과 분리해서 실행한다. V100은 NCU chip alias가 `gv100`이다.

Metric availability:

```bash
NCU="${NCU:-$(command -v ncu)}" NCU_CHIP=gv100 scripts/run_ncu.sh --query-metrics
```

대표 mode validation:

```bash
NCU="${NCU:-$(command -v ncu)}" \
BIN=./build-v100/a100_fp16_energy_v2 \
TARGET_PROFILE=v100 \
ACTIVE_SM=80 \
GPU=0 \
OUTDIR=results/ncu/v100_validation_$(date +%Y%m%d) \
RAW_OUT=results/raw/v100_ncu_validation_sidecar_$(date +%Y%m%d).csv \
bash scripts/run_ncu_validation.sh
```

권한 또는 버전 문제가 있으면 다음을 구분해서 기록한다.

| 오류/상태 | 의미 | 조치 |
|---|---|---|
| `ERR_NVGPUCTRPERM` | performance counter 권한 없음 | 관리자/root 권한 또는 counter 접근 허용 필요 |
| `gv100` chip 미지원 | NCU 버전이 Volta를 지원하지 않음 | NCU 2024.3/2025.1 계열 지정 |
| metric query 실패 | metric 이름/section 호환 문제 | `--query-metrics --chips gv100`로 metric availability 확인 |

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
| NCU validation | mode, tensor %, L1 hit rate (%), L2 hit rate (%), L1 accesses (requests/sectors), L2 accesses (sectors), DRAM accesses (sectors), shared bytes/op, L2 bytes/op, DRAM bytes/op, top stall %, status |

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
| build | `CMAKE_CUDA_ARCHITECTURES=70`, 주요 kernel spill 0 |
| preflight | `detected profile = v100`, binary dry-run 성공 |
| dry-run | `target_profile=v100`, `mode_allowed=true` |
| smoke | `energy_source` 기록, `smid_histogram_ok=true` |
| full sweep | raw CSV와 matrix CSV 모두 생성 |
| component pairs | `reg_mma_minus_reg_operand` pair와 단위 포함 summary 생성 |
| NCU | counter 수집 성공 또는 실패 사유 문서화 |
| report | mode 설명 표와 단위 포함 sweep 표 작성 |

## 13. 2026-07-06 Component finalplan 업데이트

기존 `run_component_pairs.py` 방식은 보조 진단으로 남긴다. V100에서 component coefficient 후보를 만들 때는 acceptance-first flow를 우선한다.

| 단계 | script | 목적 |
|---|---|---|
| command plan | `scripts/plan_platform_component_experiment.py` | V100용 표준 energy/NCU/analyze 명령 생성 |
| energy sweep | `scripts/run_component_regression_sweep.py` | NCU 없이 duration-calibrated energy row 수집 |
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

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/v100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

V100 추천 finalplan 좌표:

| Component | modes | W_SM (KiB) | blocks/SM | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 16,32 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 32,64 | 16,32 | load_repeat 1,2,4,8,16 |
| Global L1 | `clocked_empty,global_l1_load_only` | 8,16 | 16,32 | load_repeat 1,2,4,8,16 |
| L2 CG | `clocked_empty,l2_cg_load_only` | 64 | 16,32 | load_repeat 1,2,4,8,16 |
| DRAM sanity | `clocked_empty,dram_cg_load_only` | 8192 | 16,32 | load_repeat 1,4,16 |

V100은 6 MiB L2라 capacity 기반 `l2_load_only`가 L1 hit와 쉽게 섞일 수 있다. 따라서 L2 후보는 우선 `l2_cg_load_only`로 잡고, NCU에서 다음을 확인한다.

| NCU 기준 | 통과 조건 |
|---|---:|
| L2 CG | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 bytes <= 2% |
| Global L1 | L1 hit >= 95%, L2/L1 bytes <= 1% |
| Shared scalar | shared bytes 존재, bank conflict 0 또는 매우 낮음 |
| Tensor | HMMA > 0, spill/local 0 |

V100에서 NCU `gv100` 지원이 안 되면 component coefficient를 최종값으로 보고하지 않는다. 이 경우 energy raw CSV는 남기되, 보고서에는 “NCU path acceptance 미완료”라고 분리 기록한다.
