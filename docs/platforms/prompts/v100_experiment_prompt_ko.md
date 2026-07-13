# V100 실험 전달용 프롬프트

작성일: 2026-07-07, V100 toolchain/좌표 재검토: 2026-07-10

이 문서는 V100 노드에서 component energy microbenchmark를 다시 실행할 때 다른 작업자나 에이전트에게 전달할 프롬프트를 별도로 모아둔 것이다. 실행 절차의 기준 문서는 [v100_node_experiment_guide_ko.md](../v100_node_experiment_guide_ko.md)이고, cross-platform 해석 기준은 [cross_platform_component_experiment_guide_ko.md](../cross_platform_component_experiment_guide_ko.md)를 따른다.

## 사용 원칙

| 항목 | 기준 |
|---|---|
| 대상 GPU | NVIDIA V100 / Volta GV100 |
| CUDA architecture | `sm_70` |
| CUDA compiler | `nvcc --list-gpu-arch`에 `compute_70`; CUDA 12.x 권장 |
| target profile | `v100` |
| NCU chip | `gv100` |
| 기본 active SM | runtime에서 확인한 값, 보통 80 SM |
| L2 기준 | 6 MiB |
| L1/shared 기준 | 128 KiB/SM combined, 96 KiB/SM shared allocation |
| max blocks/SM | 32 |
| energy blocks/SM sweep | `4,16,32` |
| strict NCU blocks/SM | `32` |
| Tensor baseline | FP16 WMMA baseline |
| 결과 의미 | 순수 회로 에너지가 아니라 NCU로 경로를 검증한 effective microbenchmark coefficient |

## 짧은 인수인계 프롬프트

아래 프롬프트는 이미 저장소와 문서를 알고 있는 작업자에게 전달할 때 사용한다.

```text
V100/GV100 노드에서 gpupower0701 component energy 실험을 실행해줘.

반드시 docs/platforms/v100_node_experiment_guide_ko.md, docs/platforms/cross_platform_component_experiment_guide_ko.md, docs/platforms/power_measurement_api_matrix_ko.md, docs/methodology/component_energy_final_experiment_plan_ko.md, docs/methodology/ncu_validation_energy_calculation_ko.md를 먼저 읽고 진행해.

목표는 Tensor, shared/L1, global L1, L2의 board-level effective microbenchmark coefficient를 얻는 것이며, DRAM은 가능하면 sanity로만 확인해. 순수 회로 pJ가 아니라 NCU counter로 path가 검증된 effective coefficient라는 점을 보고서에 명확히 써줘.

V100 기준을 강제해:
- build: CMAKE_CUDA_ARCHITECTURES=70
- compiler: CUDA 13은 Volta offline compilation을 지원하지 않으므로 CUDA 12.x `nvcc --list-gpu-arch`에서 `compute_70` 확인
- runtime: --target-profile v100
- NCU: NCU_CHIP=gv100
- active SM: runtime에서 확인한 값, 보통 80
- L2: 6 MiB
- L1/shared: 128 KiB/SM combined, 96 KiB/SM shared allocation
- max blocks/SM: 32
- energy sweep blocks/SM: 4,16,32
- strict NCU coordinate: blocks/SM=32, Shared/L1/L2 W_SM=32 KiB

RTX 3090 값(sm_86, active_SM=82, blocks/SM max 16)이나 A100 값(sm_80, L2=40 MiB, shared=164 KiB/SM)이 섞인 row는 최종 coefficient에서 제외해.

실험 순서:
1. git pull 및 node 상태 기록
2. nvidia-smi와 preflight로 V100/CC 7.0/profile v100 확인
3. CUDA 12.x nvcc의 --list-gpu-arch가 compute_70을 포함하는지 확인
4. ncu --list-chips와 --query-metrics --chips gv100 확인
5. sm_70로 build
6. dry-run과 smoke run 실행
7. scripts/plan_platform_component_experiment.py로 V100 finalplan 생성
8. energy sweep 실행
9. NCU sidecar 실행. DRAM sanity는 DRAM_W_SM_KIB_OVERRIDE=8192 이상으로 확인
10. scripts/analyze_ncu_path_acceptance.py로 path acceptance 확인
11. scripts/analyze_matched_control_energy.py로 accepted row만 coefficient 계산
12. 결과 표에는 sweep 조건, 선택된 좌표, 단위, NCU hit/access/stall counter를 모두 포함

NCU에서 gv100이 지원되지 않거나 counter 권한 문제가 있으면 energy raw CSV는 남기되, component coefficient를 최종값으로 보고하지 말고 “NCU path acceptance 미완료”로 분리해.

최종 보고서에는 다음을 포함해:
- 사용한 GPU/driver/CUDA/NCU 버전
- `nvcc --list-gpu-arch`의 `compute_70` 지원 여부
- V100 capacity 표(register, L1/shared, L2, max blocks/SM)
- sweep 표(blocks/SM, W_SM, reuse/load_repeat)
- accepted/rejected row와 이유
- Tensor pJ/FLOP, shared/L1/L2 pJ/bit 또는 pJ/Byte 후보
- NCU L1 hit, L2 hit, L1/L2/DRAM access 수, stall 비율, achieved occupancy, registers/thread, shared/block bytes
- RTX 3090/A100 설정이 섞이지 않았다는 자가점검
```

## 전체 실행 프롬프트

아래 프롬프트는 새 플랫폼에서 처음부터 끝까지 작업을 맡길 때 사용한다.

```text
Power Modeling 실험 저장소 gpupower0701을 V100/GV100 노드에서 실행하고, 결과를 문서화해줘.

내 목표는 결과 요약이 아니라, V100 구조를 고려한 component energy 실험이 제대로 수행되었는지 검증하고, Tensor, shared/L1, global L1, L2의 effective microbenchmark coefficient를 합리적으로 얻는 것이다. DRAM은 알 수 있으면 좋지만, V100에서는 L2/DRAM 분리가 불안정하면 sanity 결과로만 보고해도 된다.

중요한 해석 기준:
- 이 실험의 pJ/FLOP, pJ/bit, pJ/Byte는 순수 회로 에너지가 아니다.
- NVML board power에서 idle/control을 차분하고, NCU counter로 실제 경로가 의도대로 탔는지 검증한 effective microbenchmark coefficient다.
- 따라서 결과에는 kernel 구조, working set, blocks/SM, reuse/load_repeat, NCU hit/access/stall counter가 함께 있어야 한다.
- NCU 검증이 없으면 coefficient를 최종값으로 확정하지 말고 후보 또는 미검증 결과로 분리한다.

반드시 먼저 읽을 문서:
- docs/platforms/v100_node_experiment_guide_ko.md
- docs/platforms/cross_platform_component_experiment_guide_ko.md
- docs/platforms/power_measurement_api_matrix_ko.md
- docs/methodology/component_energy_final_experiment_plan_ko.md
- docs/methodology/ncu_validation_energy_calculation_ko.md
- docs/audits/component_energy_self_critique_ko.md

V100 전용 기준:
- GPU: NVIDIA V100 / Volta GV100
- compute capability: 7.0
- build arch: sm_70
- build compiler: CUDA 12.x 권장. CUDA 13 nvcc는 사용하지 말고 `compute_70` 지원을 명령으로 검증
- target profile: v100
- NCU chip alias: gv100
- default full SM count: 80, 단 실제 runtime SM count를 preflight로 확인
- L2: 6 MiB
- combined L1/shared: 128 KiB/SM
- shared allocation: 96 KiB/SM
- max resident blocks/SM: 32
- Tensor baseline: FP16 WMMA

혼입 방지:
- RTX 3090 기준(sm_86, active_SM=82, max blocks/SM=16, GA102)을 V100 결과에 섞지 마.
- A100 기준(sm_80, GA100, L2=40 MiB, shared=164 KiB/SM)을 V100 결과에 섞지 마.
- H100 기준(sm_90, GH100, FP8 중심 해석)을 V100 FP16 baseline과 직접 섞지 마.
- 위 값이 CSV row, command, report에 보이면 최종 coefficient에서 제외하고 원인을 적어.

실행 절차:
1. 저장소 상태 확인
   - git pull
   - git status --short
   - 미추적 과거 results 파일은 새 보고서에 섞지 않는다.

2. 노드 상태 기록
   - nvidia-smi -L
   - nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
   - 가능하면 persistence mode와 clock 상태를 기록한다.
   - raw CSV에서 `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter`, `nvml_power_usage_semantics=instant`인지 확인한다.

3. CUDA compiler 확인
   - `nvcc --version`과 `nvcc --list-gpu-arch`를 기록한다.
   - `compute_70`이 없으면 중단하고 CUDA 12.x compiler를 선택한다.
   - generated package 실행 시 `NVCC=/path/to/cuda-12/bin/nvcc`를 명시한다.

4. NCU 확인
   - ncu --version
   - ncu --list-chips | tr ',' '\n' | grep -i gv100
   - ncu --query-metrics --chips gv100
   - gv100 미지원 또는 ERR_NVGPUCTRPERM이면 원인을 보고하고, NCU path acceptance 미완료로 표시한다.

5. 빌드
   - CMAKE_CUDA_ARCHITECTURES=70으로 build-v100 디렉터리에 빌드한다.
   - ptxas register count와 spill load/store 여부를 기록한다.
   - spill이 있으면 register/Tensor coefficient 신뢰도를 낮게 표시한다.

6. preflight와 dry-run
   - scripts/preflight_gpu_support.py로 detected profile=v100, CC=7.0, NCU chip=gv100 여부를 기록한다.
   - dry-run에서 target_profile=v100, target_l2_MiB=6, target_shared_KiB_per_SM=96, max_blocks_per_SM=32를 확인한다.

7. energy sweep
   - scripts/plan_platform_component_experiment.py --target-profile v100으로 표준 명령을 생성한다.
   - seconds는 최종 실험에서 10 이상, repeats는 5 이상을 권장한다.
   - blocks/SM은 4,16,32를 energy sweep으로 수행한다. B4/B16은 utilization 민감도, B32는 strict anchor다.
   - strict coefficient는 generated sidecar의 exact NCU 좌표 B32와 일치하는 row만 우선 채택한다.
   - Tensor는 RF별로 reg_mma treatment 목표와 reg_operand_only control 최소시간을 각각 calibrate하고 두 ITER 중 큰 값을 두 mode에 적용한 뒤, duration scaling 없이 net-energy를 직접 차분한다. tensor_pair_calibration CSV의 두 candidate/max policy와 matched detail의 `pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`을 확인한다.
   - shared scalar는 clocked_empty와 shared_scalar_load_only 차분으로 본다.
   - global L1은 global_addr_only와 global_l1_load_only 차분으로 본다.
   - L2는 global_addr_only와 l2_cg_load_only를 W/B/LR별 dual-calibrate하고 두 candidate 중 큰 동일 ITER를 양쪽에 적용한 뒤 net-energy를 직접 차분한다. `*_l2_pair_calibration.csv`, raw ITER equality, `pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`을 모두 확인한다.
   - DRAM도 global_addr_only와 dram_cg_load_only에 동일 ITER를 적용해 sanity로 보고, W_SM은 8192 KiB 이상으로 시작한다.

8. NCU sidecar
   - NCU_CHIP=gv100을 반드시 지정한다.
   - Nsight Compute 2024.3은 GV100 지원이 확인된다. 다른 버전은 `--list-chips`와 `--query-metrics --chips gv100` 성공을 먼저 확인한다.
   - generated package가 unavailable metric을 제외해도 필수 path evidence가 없으면 acceptance에서 reject한다.
   - DRAM sanity는 DRAM_W_SM_KIB_OVERRIDE=8192 이상으로 실행한다.
   - NCU replay에서 얻은 energy는 NVML energy CSV와 직접 합치지 않는다.
   - NCU는 경로 검증용이다.
   - B32가 실제 32 resident blocks라는 뜻은 아니다. achieved occupancy, registers/thread, static/dynamic shared/block을 기록한다.

9. path acceptance
   - Tensor: HMMA/Tensor instruction이 존재하고 spill/local memory가 없어야 한다.
   - Shared scalar: shared bytes가 존재하고 bank conflict가 0 또는 매우 낮아야 한다.
   - Global L1: L1 hit >= 95%, L2/L1 bytes <= 1% 수준이어야 한다.
   - L2 CG: path-specific L2 read hit >=95%, L1 path hit <=1%, L1 hit bytes/request bytes <=1%, DRAM/L2 read bytes <=2% 수준이어야 한다. `.cg`의 L1 request bytes 자체와 aggregate hit는 표시하되 hard gate로 쓰지 않는다.
   - DRAM sanity: L2 hit가 낮고 DRAM bytes가 충분히 커야 하며, 그렇지 않으면 DRAM coefficient로 쓰지 않는다.

10. coefficient 계산
   - accepted row만 scripts/analyze_matched_control_energy.py로 계산한다.
   - Tensor는 pJ/FLOP로 보고한다.
   - memory 계층은 pJ/bit와 pJ/Byte를 모두 보고하고, denominator가 NCU actual traffic인지 논리적 bytes인지 명확히 쓴다.
   - min, median, max, average를 분리하고, outlier 제거 기준을 적는다.

11. 보고서 작성
   - 결과 요약보다 방법의 의미를 먼저 설명한다.
   - 각 sweep은 표로 정리하고 단위를 반드시 쓴다.
   - mode별 의미를 설명한다.
   - NCU hit rate와 access 수를 표로 제시한다.
   - accepted/rejected row를 나누고 rejected 이유를 적는다.
   - final coefficient는 “순수 회로 에너지”가 아니라 “NCU로 경로가 검증된 board-level effective microbenchmark coefficient”라고 쓴다.

최종 산출물:
- results/raw/v100_*.csv
- results/ncu/v100_*/
- results/summary/v100_*_acceptance*.csv 또는 .md
- results/summary/v100_*_matched_control*.csv 또는 .md
- V100 실험 보고서 markdown
- 실행 command log 또는 generated command script

자가점검 질문:
- 정말 V100에서 sm_70로 빌드했는가?
- 사용한 nvcc가 `compute_70`을 지원하는가? CUDA 13 compiler를 잘못 사용하지 않았는가?
- active_SM, L2, shared capacity가 V100 값인가?
- NCU chip이 gv100인가?
- L1 coefficient 후보에서 L2/DRAM traffic이 섞이지 않았는가?
- L2 coefficient 후보에서 L1 hit가 낮고 DRAM traffic이 낮은가?
- Tensor coefficient 후보에서 spill/local memory가 없는가?
- B32의 실제 residency를 NCU achieved occupancy와 launch resource로 확인했는가?
- pJ/bit denominator가 NCU actual traffic인지 logical traffic인지 명시했는가?
- NCU 미검증 row를 최종값처럼 쓰지 않았는가?
```

## 결과 채택 기준 요약

| Component | 권장 mode pair | V100 우선 좌표 | NCU 채택 기준 | 결과 단위 |
|---|---|---|---|---|
| Tensor | `reg_mma - reg_operand_only` | energy B4/16/32; strict W2048/B32, reuse sweep | treatment HMMA 존재, control HMMA=0, spill/local 0, 두 mode ITER 동일 | pJ/FLOP |
| Shared/L1 | `shared_scalar_load_only - clocked_empty` | energy W32/64, B1-32; strict W32/B32 | shared bytes 존재, bank conflict 낮음 | pJ/bit, pJ/Byte |
| Global L1 | `global_l1_load_only - global_addr_only` | energy W8/16/32, B4/16/32; strict W32/B32 | L1 hit >= 95%, L2/DRAM 낮음 | pJ/bit, pJ/Byte |
| L2 | `l2_cg_load_only - global_addr_only` | energy W32/64, B4/16/32; strict W32/B32 | 두 mode 동일 ITER, L2 read path hit >=95%, L1 path hit와 hit/request bytes <=1%, DRAM 낮음 | pJ/bit, pJ/Byte |
| DRAM sanity | `dram_cg_load_only - global_addr_only` | energy B4/16/32; strict W8192/B32 | 두 mode 동일 ITER, DRAM bytes 충분, capacity-bound L2 residual hit 허용 | pJ/bit, pJ/Byte 후보 |

## 해석 시 주의할 표현

| 피해야 할 표현 | 권장 표현 |
|---|---|
| “V100 L1 회로 에너지는 x pJ/bit다” | “이 microbenchmark에서 NCU로 L1-hit path가 검증된 effective coefficient는 x pJ/bit다” |
| “DRAM physical energy를 측정했다” | “board-level power와 NCU traffic으로 DRAM streaming 후보 coefficient를 추정했다” |
| “NCU가 없어도 component별 최종값을 얻었다” | “NCU 미검증 결과이므로 coefficient 후보이며 최종 채택하지 않았다” |
| “A100/RTX3090과 같은 W_SM이면 된다” | “각 GPU의 L1/shared, L2 capacity에 맞춰 W_SM과 blocks/SM을 다시 잡았다” |

## 참고 링크

- Nsight Compute get started: <https://developer.nvidia.com/tools-overview/nsight-compute/get-started>
- Nsight Compute release history: <https://developer.nvidia.com/nsight-compute-history>
- NVML device queries: <https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html>
- NVML field values: <https://docs.nvidia.com/deploy/nvml-api/group__nvmlFieldValueEnums.html>
