# RTX 3090, V100, A100, H100 지원 계획

작성일: 2026-07-02

## 목적

현재 코드는 RTX 3090과 A100 중심의 FP16 Tensor Core 에너지 microbenchmark로 정리되어 있다. 다음 단계에서는 RTX 3090, V100, A100, H100을 같은 실험 harness에서 지원하되, GPU 세대별 구조 차이, NVML power/energy API 의미 차이, Tensor Core 지원 데이터형 차이, Nsight Compute 지원 차이를 코드와 결과 해석에 명시적으로 반영한다.

이 문서는 바로 구현에 들어가기 전의 설계 및 검증 계획이다.

## 핵심 원칙

- GPU 이름으로 동작을 암묵 결정하지 않는다. `compute capability`, 실제 SM 수, L2 크기, shared/L1 carveout, NVML capability, NCU metric availability를 runtime preflight로 기록한다.
- 에너지 측정과 NCU profiling은 분리한다. NCU replay가 에너지 값을 왜곡할 수 있으므로 NCU 결과는 instruction, memory path, stall, occupancy 검증용 sidecar로만 사용한다.
- 모든 결과 CSV는 `power_source`, `energy_source`, `ncu_version`, `ncu_supported`, `profile_name`, `compute_capability`, `sm_count`, `l2_mib`, `unified_l1_shared_kib_per_sm`, `shared_kib_per_sm`를 포함해야 한다.
- 서로 다른 NVML source에서 나온 에너지 수치를 같은 의미로 비교하지 않는다. total energy counter, instantaneous power integration, 1초 averaged power integration은 별도 라벨로 유지한다.
- 공통 baseline은 FP16 WMMA `m16n16k16` logical op로 둔다. H100 FP8/WGMMA, A100 FP64 Tensor Core, RTX 3090 TF32/BF16 등은 후속 optional variant로 분리한다.

## 공식 문서에서 확인한 제약

- NVML `nvmlDeviceGetTotalEnergyConsumption()`은 GPU의 driver reload 이후 누적 에너지 소비량을 mJ 단위로 반환하며, Volta 이상 fully supported device 대상이다. 지원하지 않으면 `NVML_ERROR_NOT_SUPPORTED`가 가능하다.
- NVML `nvmlDeviceGetPowerUsage()`는 mW 단위 power를 반환하지만 의미가 세대별로 다르다. Ampere 중 GA100을 제외한 GPU 또는 그 이후 GPU에서는 1초 평균 power를 반환하고, GA100 및 그 이전 architecture에서는 instantaneous power를 반환한다.
- NVML field API에는 `NVML_FI_DEV_POWER_AVERAGE`와 `NVML_FI_DEV_POWER_INSTANT`가 있으며, `POWER_AVERAGE`는 Ampere 중 GA100 제외 또는 이후 architecture에서 1초 평균 power로 정의되고, `POWER_INSTANT`는 모든 architecture의 현재 power로 정의된다.
- CUDA Programming Guide는 compute capability별 resident block, shared memory, Tensor Core data type을 별도 표로 제공한다. CC 8.6은 resident block/SM 16, shared memory/SM 100 KB, max shared memory/block 99 KB이고, CC 8.0은 block/SM 32, shared memory/SM 164 KB, max/block 163 KB이다. CC 9.0은 block/SM 32, shared memory/SM 228 KB, max/block 227 KB이다.
- Hopper Tuning Guide 기준 H100은 CC 9.0, shared memory/SM 228 KB, max shared memory/block 227 KB, L2 50 MB, TMA, Thread Block Cluster, Distributed Shared Memory를 지원한다.
- NVIDIA Nsight Compute release history 기준 2026-06-29 현재 최신 공개 버전은 2026.2.1 계열이다. NVIDIA release highlights에는 Volta/GV100 지원 제거가 공지되어 있으므로, V100 profiling은 버전 이름이 아니라 `ncu --list-chips`에 `gv100`이 있는지로 판단한다. `gv100`이 없으면 2024.3/2025.1 계열 같은 Volta 지원 toolchain 또는 대체 검증 경로가 필요하다.

## GPU별 1차 지원 행렬

| GPU | uArch / chip | CC | 기본 SM 수 | L2 | shared/L1 관련 | Tensor Core baseline | 주요 주의점 |
|---|---|---:|---:|---:|---|---|---|
| RTX 3090 | Ampere GA102 / GA10x | 8.6 | 82 | 6 MiB | 128 KiB combined L1/shared, 100 KiB shared allocation, max shared/block 99 KiB, max blocks/SM 16 | FP16, TF32, BF16, INT8, INT4. FP64 Tensor Core 없음 | `blocks/SM=32` 불가. NVML `GetPowerUsage`는 1초 평균 의미. WSL에서는 NCU performance counter 권한 이슈 가능 |
| V100 | Volta GV100 | 7.0 | 80 | 6 MiB | 128 KiB combined L1/shared, 96 KiB shared allocation, max shared/block 96 KiB, max blocks/SM 32 | FP16 input, FP16 또는 FP32 accumulate 중심 | 최신 계열 NCU에서는 Volta 지원 제거가 공지되어 있다. `gv100` 지원 NCU 또는 정적 SASS/PTX 검증 필요 |
| A100 | Ampere GA100 | 8.0 | 108 | 40 MiB | 192 KiB combined L1/shared, 164 KiB shared allocation, max shared/block 163 KiB, max blocks/SM 32 | FP16, BF16, TF32, FP64, INT8, INT4, Binary, sparsity | `GetPowerUsage`는 GA100 예외로 instantaneous 의미. MIG 사용 시 L2 set-aside 등 일부 기능 영향 |
| H100 | Hopper GH100 | 9.0 | SKU별 상이, runtime 우선 | 50 MiB | 256 KiB combined L1/shared, 228 KiB shared allocation, max shared/block 227 KiB, max blocks/SM 32, TMA/DSM/cluster | FP16/BF16/TF32 계열 + FP8, WGMMA 계열 optional | 기존 WMMA baseline은 가능하지만 Hopper 특화 실험은 WGMMA/TMA 별도 kernel 필요 |

SM 수는 SKU별 차이가 있을 수 있으므로 위 값은 default profile일 뿐이다. 실제 실행 전 `cudaDevAttrMultiProcessorCount`와 `nvmlDeviceGetCudaComputeCapability()` 결과를 CSV에 기록하고, profile 값과 다르면 경고 또는 `--allow-profile-mismatch`가 필요하다.

## 코드 구조 변경 계획

### 1. HardwareProfile 확장

현재 `HardwareProfile`은 RTX 3090/A100에 필요한 최소 필드만 가진다. 다음 필드를 추가한다.

- `architecture_family`: `volta`, `ampere_ga10x`, `ampere_ga100`, `hopper_gh100`
- `chip`: `gv100`, `ga102`, `ga100`, `gh100`
- `default_sm_count`, `allow_runtime_sm_override`
- `max_warps_per_sm`, `max_threads_per_sm`
- `unified_l1_shared_kib`, `shared_capacity_per_sm_kib`, `max_shared_per_block_kib`
- `l2_kib`
- `max_blocks_per_sm`
- `supports_l2_persistence`, `supports_async_copy`, `supports_tma`, `supports_clusters`
- `tensor_modes`: hardware capability metadata다. 현재 공통 구현 baseline은 FP16 WMMA이고, `tf32`, `bf16`, `fp64_tc`, `fp8`, `wgmma`, `tma`, `int8`, `int4`, `sparsity`는 GPU별 optional capability 또는 후속 kernel 후보로 분리한다.
- `ncu_chip_aliases`: `gv100`, `ga100`, `ga102`, `gh100` 등. 문서상의 family 이름은 GA10x지만 `ncu --list-chips`는 대개 `ga102`처럼 구체 chip명을 쓴다.
- `recommended_ncu_version`: V100은 `ncu --list-chips`에 `gv100`이 있는 toolchain을 요구한다. 2024.3/2025.1 계열은 예시이고, 최신 계열은 Volta 지원 제거 공지를 기준으로 미리 배제하거나 반드시 preflight로 확인한다. Ampere/Hopper도 현재 버전 가능 여부를 preflight로 확인한다.

Profile은 compile-time default가 아니라 runtime target으로 취급한다. `--target-profile auto`를 추가해 NVML/CUDA query 결과로 profile을 선택하고, 수동 profile은 검증용으로만 사용한다.

### 2. Feasibility 규칙 일반화

현재 규칙은 `shared_resident`, `l2_candidate`, `dram_mixed_streaming`을 profile L2/shared 기준으로 판단한다. 여기에 다음을 추가한다.

- `max_blocks_per_sm` 초과는 GPU별 invalid로 기록한다.
- shared mode는 `W_SM + block_overhead <= shared_capacity_per_sm_kib`와 `W_SM / blocks_per_SM <= max_shared_per_block_kib`를 사용한다.
- L2 mode는 nominal L2만 보지 말고, A100/H100의 L2 persistence 가능 여부와 MIG 여부를 notes에 기록한다.
- H100 cluster/DSM/TMA mode는 기존 `shared_mma`와 섞지 않고 `hopper_tma_mma`, `hopper_wgmma` 같은 별도 mode 후보로 남긴다.

### 3. NVML Power/Energy abstraction 재설계

현재 코드는 total energy counter를 우선 사용하고 실패 시 power 적분 fallback을 사용한다. 이를 명시적 strategy로 분리한다.

우선순위:

1. `total_energy_mj_delta`: `nvmlDeviceGetTotalEnergyConsumption` 시작/종료 차분. 지원 시 primary.
2. `field_power_instant_integral`: `NVML_FI_DEV_POWER_INSTANT` 샘플 적분. short kernel 검증용 fallback.
3. `field_power_average_integral`: `NVML_FI_DEV_POWER_AVERAGE` 샘플 적분. RTX 3090/H100 등에서 1초 averaging이 섞이는 경우 label 필수.
4. `legacy_get_power_usage_integral`: `nvmlDeviceGetPowerUsage` 샘플 적분. API 의미가 세대별로 다르므로 final coefficient 비교에는 주의.

CSV에 추가할 필드:

- `nvml_total_energy_supported`
- `nvml_power_usage_semantics`: `instant`, `one_sec_average`, `unknown`
- `nvml_field_power_instant_supported`
- `nvml_field_power_average_supported`
- `energy_integration_method`
- `power_sample_count`
- `power_sample_period_ms`
- `driver_version`, `nvml_version`

짧은 1초 run은 average power source에서 큰 오차가 날 수 있으므로, total energy counter가 없는 GPU/환경은 `seconds>=10`, `repeats>=5`를 기본 정책으로 둔다.

### 4. Tensor Core kernel 정책

공통 baseline:

- 모든 GPU에서 `fp16_wmma_m16n16k16`를 유지한다.
- logical op 정의는 기존처럼 `8192 FLOP/op`, `8192 input bits/op`로 유지한다.
- V100/RTX3090/A100/H100 간 공정 비교는 이 baseline만 사용한다.

Optional variants:

- V100: FP16 WMMA + 가능한 경우 SASS에서 `HMMA` 계열 확인.
- RTX 3090: FP16/BF16/TF32 WMMA 또는 inline PTX variant. FP64 Tensor Core는 제외.
- A100: FP16/BF16/TF32/FP64 Tensor Core variant, sparsity는 별도 실험.
- H100: 기존 WMMA baseline 외에 WGMMA/FP8/TMA pipeline은 별도 mode로 추가한다. 기존 결과와 직접 합치지 않는다.

검증 기준:

- PTX/SASS에서 tensor instruction 확인.
- NCU에서 tensor pipe utilization, instruction count, shared/global/L2/DRAM traffic 확인.
- kernel별 register spill/local memory 여부 확인.

### 5. Nsight Compute 지원 정책

NCU는 GPU와 버전 조합이 중요하다.

| GPU | 2025.4+/2026.x 계열 | 2024.3/2025.1 계열 | 계획 |
|---|---|---|---|
| RTX 3090 / GA10x | 지원 | 지원 | 현재 NCU 사용 가능. WSL performance counter 권한 preflight 필수 |
| V100 / GV100 | 공식 highlights 기준 지원 제거, `ncu --list-chips`로 확인 | 지원 가능 | V100 profiling은 `gv100` chip이 노출되는 NCU toolchain을 별도 설치/지정 |
| A100 / GA100 | 지원 | 지원 | 현재 NCU 사용 가능 |
| H100 / GH100 | 지원 | 지원 | 현재 NCU 사용 가능. Hopper metric 이름과 TMA/WGMMA section 별도 확인 |

NCU preflight:

```bash
ncu --version
ncu --list-chips
ncu --query-metrics --chips <chip>
```

공통 sections:

- `LaunchStats`
- `Occupancy`
- `SpeedOfLight`
- `WorkloadDistribution`
- `InstructionStats`
- `SchedulerStats`
- `WarpStateStats`
- `MemoryWorkloadAnalysis`

GPU별 추가 확인:

- V100: Volta metric 이름 호환, `smsp__sass_*`, tensor instruction count, shared/L1 metric availability.
- RTX 3090: WSL `ERR_NVGPUCTRPERM` preflight, GA10x tensor/DRAM/L2 metric availability.
- A100: MIG 여부, L2 set-aside 상태, FP64 Tensor Core metric availability.
- H100: GH100 chip alias, WGMMA/TMA/cluster 관련 metric availability, PM sampling section 사용 가능 여부.

### 6. Preflight suite 추가

새 스크립트 후보:

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto
```

출력:

- CUDA runtime device properties
- NVML name, UUID, driver/NVML version, compute capability
- actual SM count
- shared memory opt-in limit
- L2 cache size
- total energy support 여부
- power instant/average field support 여부
- NCU binary/version/chip support 여부
- 권장 `--target-profile`, `CMAKE_CUDA_ARCHITECTURES`

Preflight 실패를 실험 실패와 구분한다. 예를 들어 V100에서 최신 NCU만 있으면 energy run은 가능하지만 NCU validation은 `blocked_by_ncu_version`으로 기록한다.

### 7. 실험 matrix 정책

공통 sweep:

- Sweep 1: `blocks/SM = 1, 2, 4, 8, 16, 32`
- Sweep 2: `W_SM = 1 KiB`부터 `128 MiB`까지 2배 증가

GPU별 실행 가능성:

- RTX 3090: `blocks/SM=32` invalid로 matrix에 기록하고 실행하지 않는다.
- V100/A100/H100: `blocks/SM=32` 가능 후보지만 shared/register/occupancy 제한을 preflight와 dry-run에서 확인한다.
- H100: shared capacity가 커서 shared-resident boundary가 달라진다. TMA/WGMMA optional mode는 별도 matrix로 둔다.

결과 산출:

- GPU별 raw CSV: `results/raw/<gpu>_full_sweep_<date>.csv`
- GPU별 matrix CSV: `results/raw/<gpu>_full_sweep_<date>_matrix.csv`
- GPU별 summary: `results/summary/<gpu>_full_sweep_<date>_summary.md`
- cross-GPU summary: `results/summary/cross_gpu_fp16_energy_<date>.md`

Cross-GPU 비교는 동일 baseline, 동일 energy source class, 동일 반복 정책을 만족하는 row만 사용한다.

## 구현 단계

### Phase 1: 조사 및 profile schema

- `HardwareProfile` 확장.
- `rtx3090`, `v100`, `a100`, `h100` profile 추가.
- `--target-profile auto` 추가.
- CUDA/NVML runtime query와 profile mismatch warning 추가.
- README와 SKILL 문서의 A100/RTX3090 중심 표현을 multi-GPU 기준으로 수정.

완료 조건:

- 네 GPU profile이 dry-run matrix를 생성한다.
- 각 GPU의 invalid reason이 GPU별 한계로 설명된다.

### Phase 2: NVML measurement layer

- total energy, field instant, field average, legacy power usage를 strategy로 분리.
- API별 support flag를 CSV에 기록.
- `nvmlDeviceGetPowerUsage`의 세대별 의미를 notes에 기록.
- power integration fallback의 sampling period와 sample count를 저장.

완료 조건:

- total energy가 지원되는 환경에서는 기존 결과와 동일한 계산 경로를 유지한다.
- total energy 미지원 환경에서는 fallback 결과가 `energy_source`로 명확히 구분된다.

### Phase 3: NCU capability layer

- `scripts/run_ncu_validation.sh`를 profile-aware로 확장.
- `ncu --list-chips`, `--query-metrics --chips` 기반 metric availability cache를 생성한다.
- V100은 NCU 버전이 맞지 않으면 실행하지 않고 `blocked_by_ncu_version` 상태 문서를 생성한다.
- RTX 3090/WSL은 `ERR_NVGPUCTRPERM` preflight를 문서화한다.

완료 조건:

- 지원되는 GPU/NCU 조합에서 stall percentage, SOL percentage, L1/L2 hit rate (%), L1/L2/DRAM access count, memory path percentage를 CSV/Markdown으로 요약한다.
- 지원되지 않는 조합은 명확한 이유와 대체 검증 경로를 남긴다.

### Phase 4: Tensor kernel variants

- 공통 FP16 WMMA baseline은 유지한다.
- inline PTX `mma.sync` variant는 Volta/Ampere/Hopper 호환성을 따로 검토한다.
- H100 WGMMA/FP8/TMA는 `experimental` mode로 분리한다.
- A100 FP64 Tensor Core, RTX3090 TF32/BF16 등은 baseline과 별도 metric으로 분리한다.

완료 조건:

- baseline 결과와 architecture-specific 결과가 CSV/plot에서 섞이지 않는다.
- NCU 또는 PTX/SASS 검증으로 실제 tensor path 수행 여부를 확인한다.

### Phase 5: cross-GPU 보고서

- GPU별 feasibility boundary plot 생성.
- GPU별 pJ/FLOP, pJ/input-bit summary 생성.
- power source별 결과를 분리한 cross-GPU 비교표 작성.
- NCU stall/SOL/memory path 요약을 energy coefficient와 병렬로 제공한다.

완료 조건:

- `cross_gpu_fp16_energy_<date>.md` 하나에서 네 GPU의 실행 조건, power source, NCU support, 주요 결과, 비교 가능/불가능 조건이 명확히 보인다.

## 우선순위

1. Profile schema와 auto-detection.
2. NVML power/energy source 의미 분리.
3. V100 NCU 버전 분리 정책.
4. H100 Hopper 특화 기능은 baseline 안정화 후 optional로 추가.
5. Cross-GPU 보고서 자동 생성.

## 남은 확인 항목

- H100 대상 SKU가 PCIe인지 SXM인지, 실제 SM 수와 power cap이 무엇인지 확인해야 한다.
- V100에서 사용 가능한 NCU 버전을 실제 머신에 설치할 수 있는지 확인해야 한다.
- 각 GPU에서 `nvmlDeviceGetTotalEnergyConsumption`이 실제로 성공하는지 preflight가 필요하다. 공식 문서는 Volta 이상을 대상으로 하지만 제품/드라이버/가상화 환경에 따라 `NOT_SUPPORTED`가 가능하다.
- Windows/WSL RTX 3090 환경은 NVIDIA App/Control Panel의 performance counter 권한과 `wsl --shutdown` 후 재실행이 필요할 수 있다.

## 참고 공식 문서

- NVIDIA NVML API Reference, Device Queries: `nvmlDeviceGetPowerUsage`, `nvmlDeviceGetTotalEnergyConsumption`
  - https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html
- NVIDIA NVML API Reference, Field Value Enums: `NVML_FI_DEV_POWER_AVERAGE`, `NVML_FI_DEV_POWER_INSTANT`
  - https://docs.nvidia.com/deploy/nvml-api/group__nvmlFieldValueEnums.html
- CUDA Programming Guide, Compute Capabilities
  - https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/compute-capabilities.html
- NVIDIA Hopper Tuning Guide
  - https://docs.nvidia.com/cuda/hopper-tuning-guide/index.html
- NVIDIA Nsight Compute Release History
  - https://developer.nvidia.com/nsight-compute-history
- NVIDIA Nsight Compute Get Started / Release Highlights
  - https://developer.nvidia.com/tools-overview/nsight-compute/get-started
- NVIDIA Nsight Compute current Release Notes
  - https://docs.nvidia.com/nsight-compute/ReleaseNotes/index.html
- NVIDIA Nsight Compute 2024.3 Release Notes archive
  - https://archive.docs.nvidia.com/nsight-compute/2024.3/ReleaseNotes/index.html
- NVIDIA Nsight Compute 2025.1 Release Notes archive
  - https://archive.docs.nvidia.com/nsight-compute/2025.1/ReleaseNotes/index.html
- NVIDIA Tesla V100 GPU Architecture Whitepaper
  - https://images.nvidia.com/content/volta-architecture/pdf/volta-architecture-whitepaper.pdf
- NVIDIA A100 Tensor Core GPU Architecture Whitepaper
  - https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/nvidia-ampere-architecture-whitepaper.pdf
- NVIDIA Ampere GA102 GPU Architecture Whitepaper
  - https://www.nvidia.com/content/dam/en-zz/Solutions/geforce/ampere/pdf/NVIDIA-ampere-GA102-GPU-Architecture-Whitepaper-V1.pdf
