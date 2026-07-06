# Cross-Platform Component Energy 실험 가이드

작성일: 2026-07-06

## 1. 현재 코드와 실험 내용 요약

이 저장소는 CUDA/NVML 기반 microbenchmark로 FP16 WMMA `m16n16k16` logical op를 실행하고, board-level energy delta를 측정한다. component 분리는 순수 회로 에너지를 직접 읽는 방식이 아니라, NCU로 경로를 검증한 microbenchmark들을 matched-control 차분/회귀로 비교하는 방식이다.

현재 채택 가능한 component 후보는 다음이다.

| Component/path | numerator | control | denominator | 해석 |
|---|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | FLOP | no-MMA register/control 대비 WMMA 추가분 |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | NCU shared bytes | shared-memory scalar instruction path |
| Global L1 hit path | `global_l1_load_only` | `clocked_empty` | NCU L1 bytes | global load L1-hit path |
| L2 hit path | `l2_cg_load_only` 또는 capacity `l2_load_only` | `clocked_empty` | NCU L2 bytes | L2-hit transaction path |
| DRAM streaming sanity | `dram_cg_load_only` | `clocked_empty` | NCU DRAM bytes | hierarchy sanity check |

보고서에서는 `register`, `L1`, `L2`, `DRAM`이라고 줄여 쓰더라도 반드시 **effective microbenchmark coefficient**라고 명시한다. NVML board energy에는 scheduler, issue, LSU, cache controller, memory controller, clock/power-state 변화가 함께 들어간다.

## 2. 공통 실행 순서

모든 플랫폼에서 순서는 동일하다.

| 단계 | 명령/도구 | 산출물 | 채택 기준 |
|---|---|---|---|
| preflight | `scripts/preflight_gpu_support.py` | `results/summary/*_preflight.md` | profile, CC, SM 수, NVML, NCU 상태 기록 |
| energy sweep | `scripts/run_component_regression_sweep.py` | `results/raw/*_component_finalplan_*.csv` | NCU 없이 실행, `seconds>=10`, `repeats>=5` 권장 |
| NCU sidecar | `scripts/run_ncu_validation.sh` | `results/ncu/*/ncu_cache_validation_summary.csv` | hit rate, bytes, stall, spill/local 확인 |
| path acceptance | `scripts/analyze_ncu_path_acceptance.py` | `results/summary/*_ncu_acceptance.md` | accepted mode만 coefficient 후보 |
| matched-control | `scripts/analyze_matched_control_energy.py` | `results/summary/*_matched_control_report.md` | NCU actual-byte denominator 사용 |
| report | 수동/문서화 | `results/summary/*_report_ko.md` | 단위 포함 표, rejected row 명시 |

새 플랫폼에서는 먼저 표준 명령을 생성한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5
```

생성된 shell script를 검토한 뒤 실행한다.

```bash
bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

`--target-profile`은 `a100`, `v100`, `h100`을 지원한다.

## 3. 플랫폼별 핵심 차이

| GPU | build arch | default SMs | register/SM | L1/shared capacity | L2 | memory | 주요 실험 차이 |
|---|---:|---:|---:|---:|---:|---|---|
| V100 / GV100 | sm_70 | 80 | 256 KiB급 | 128 KiB combined, 96 KiB shared allocation | 6 MiB | HBM2 | Volta NCU 지원 버전 확인 필수, L2는 CG path 우선 |
| A100 / GA100 | sm_80 | 108 | 256 KiB | 192 KiB combined, 164 KiB shared allocation | 40 MiB | HBM2 | capacity L2와 CG L2를 모두 비교 가능 |
| H100 / GH100 | sm_90 | 132 default | 256 KiB급 | 256 KiB combined, 228 KiB shared allocation profile | 50 MiB | HBM2e/HBM3 SKU별 상이 | 현재 kernel은 WMMA compatibility path, WGMMA/TMA 실험 아님 |

주의:

- `active_SM`은 profile 기본값이 아니라 runtime/preflight에서 확인한 값을 우선한다. MIG, partition, SKU 차이가 있으면 `--active-sm`을 반드시 조정한다.
- `combined L1/shared`는 SM 내부의 통합 L1/shared capacity이고, `shared allocation`은 CUDA dynamic/shared-memory 실험에서 사용할 수 있는 shared memory profile이다. 두 값을 같은 의미로 쓰면 안 된다.
- H100은 SKU에 따라 SM 수와 HBM 구성이 달라질 수 있다. profile default 132는 가이드용 기본값이다.
- V100은 최신 Nsight Compute release highlights에서 Volta/GV100 support 제거가 공지되어 있다. `ncu --list-chips`에 `gv100`이 없으면 energy run과 별도로 “NCU 검증 미완료”로 보고한다.

## 4. 추천 좌표

아래 좌표는 시작점이다. 최종값은 NCU acceptance 결과로 다시 걸러야 한다.

| GPU | Tensor W_SM (KiB) | Shared W_SM (KiB) | L1 W_SM (KiB) | L2 W_SM (KiB) | DRAM W_SM (KiB) | blocks/SM |
|---|---:|---:|---:|---:|---:|---|
| V100 | 2048 | 32,64 | 8,16 | 64 with `l2_cg_load_only` | 8192 | 16,32 |
| A100 | 2048 | 64,128 | 16,32 | 256 with `l2_load_only,l2_cg_load_only` | 8192 | 16,32 |
| H100 | 2048 | 64,128 | 16,32 | 256 with `l2_load_only,l2_cg_load_only` | 8192 | 16,32 |

Tensor `W_SM=2048 KiB`는 register working-set 크기라는 뜻이 아니다. register-mode에서 `W_SM`은 고정 좌표일 뿐이고, 실제 register footprint는 ptxas register count, threads/block, resident blocks/SM로 판단한다.

## 5. NCU Acceptance 기준

| Path | accept 조건 |
|---|---|
| Tensor | HMMA > 0, spill/local 0, memory traffic이 FLOP 대비 작음 |
| Tensor control | HMMA 0, spill/local 0 |
| Shared scalar | shared bytes/accesses 존재, bank conflict 0 또는 매우 낮음 |
| Global L1 | L1 hit >= 95%, L2/L1 byte ratio <= 1%, DRAM/L1 byte ratio <= 1% |
| L2 hit | L1 hit <= 1%, L2 hit >= 95%, DRAM/L2 byte ratio <= 2% |
| DRAM sanity | L1 hit <= 1%, L2 hit <= 5%, DRAM bytes dominant |

NCU 표에는 다음 단위를 반드시 포함한다.

| metric | unit |
|---|---|
| L1 hit rate | % |
| L2 hit rate | % |
| shared accesses | access count |
| L1/L2/DRAM accesses | requests 또는 sectors |
| shared/L1/L2/DRAM bytes | bytes |
| stall_long_scoreboard | % |

## 6. 결과 보고 언어

| 상황 | 보고 표현 |
|---|---|
| NCU accepted, coefficient 모두 양수 | `accepted candidate` |
| NCU accepted, 일부 음수/분산 큼 | `path accepted, coefficient provisional` |
| NCU rejected | `rejected for component coefficient` |
| register-pressure direct division | `register/control diagnostic only` |
| DRAM | `streaming sanity path`, physical DRAM energy라고 쓰지 않음 |

## 7. 자가비판 요약

이 실험은 다음 한계가 있다.

| 한계 | 영향 | 보완 |
|---|---|---|
| NVML board-level energy | component 외 power가 섞임 | NCU path validation과 matched-control을 같이 사용 |
| representative NCU | 모든 energy row의 actual traffic을 직접 본 것은 아님 | 최종 run은 load_repeat/reuse 좌표별 NCU 확장 |
| register 분리 어려움 | pure RF pJ/access를 주장하기 어려움 | register는 control/proxy로 제한 |
| L2/DRAM stall | pJ/bit에 stall/control이 포함됨 | stall_long_scoreboard를 함께 보고 |
| H100 WMMA path | Hopper native WGMMA/TMA 에너지가 아님 | 별도 H100-native kernel 설계 필요 |
