# Register Footprint 실험 설계

## 목적

기존 `reg_mma` 실험에서 `W_SM`을 register working set처럼 해석하면 안 된다. `reg_mma`의 실제 register footprint는 `W_SM`이 아니라 ptxas가 보고하는 `registers/thread`, `threads/block`, resident `blocks/SM`으로 정해진다.

따라서 register 축은 다음처럼 재정의한다.

```text
compiler_footprint_B_per_block
  = ptxas_registers_per_thread * threads_per_block * 4

compiler_footprint_B_per_SM
  = compiler_footprint_B_per_block * resident_blocks_per_SM
```

## 실험을 둘로 분리하는 이유

| 실험 | 목적 | 축 | 주의 |
|---|---|---|---|
| WMMA `reg_mma` | register-resident WMMA fragment를 Tensor Core MMA에 공급 | fixed ptxas footprint, `blocks/SM`, `reuse_factor` | `W_SM`이 register footprint가 아님 |
| scalar `reg_pressure` | Tensor Core 없이 scalar register payload를 변화 | target payload B/block, measured ptxas footprint B/block, `blocks/SM` | pure register energy가 아니라 register-pressure/control coefficient |

256 B부터 시작하는 축은 WMMA `m16n16k16`에는 맞지 않는다. FP16 A 또는 B logical tile 하나가 이미 512 B/warp이고, A+B는 1 KiB/warp, C accumulator까지 포함하면 2 KiB/warp다. 대신 256 B는 scalar register-pressure microbenchmark의 target payload로 사용할 수 있다.

## 새 mode: `reg_pressure`

`reg_pressure`는 Tensor Core를 사용하지 않는다. compile-time template variant로 thread당 live scalar register payload를 늘리고, loop 안에서 각 payload register를 갱신해 register liveness를 유지한다.

지원 target payload:

| target payload | payload regs/thread |
|---:|---:|
| 256 B/block | 2 |
| 512 B/block | 4 |
| 1 KiB/block | 8 |
| 2 KiB/block | 16 |
| 4 KiB/block | 32 |
| 8 KiB/block | 64 |
| 16 KiB/block | 128 |

중요: 이 값은 target payload다. 실제 compiler footprint는 ptxas 결과를 기준으로 다시 기록한다.

RTX 3090 sm_86 빌드에서 자가점검한 ptxas 결과:

| target payload (B/block) | payload regs/thread | ptxas regs/thread | compiler footprint (B/block) | spill-free | estimated max blocks/SM |
|---:|---:|---:|---:|---|---:|
| 256 | 2 | 21 | 2688 | true | 16 |
| 512 | 4 | 22 | 2816 | true | 16 |
| 1024 | 8 | 19 | 2432 | true | 16 |
| 2048 | 16 | 31 | 3968 | true | 16 |
| 4096 | 32 | 44 | 5632 | true | 16 |
| 8192 | 64 | 76 | 9728 | true | 16 |
| 16384 | 128 | 140 | 17920 | true | 14 |

작은 target payload에서는 ptxas total footprint가 단조 증가하지 않을 수 있다. 이는 base overhead와 compiler scheduling/optimization이 섞이기 때문이다. 보고서에서는 target payload보다 `ptxas regs/thread`와 `compiler footprint`를 우선 축으로 사용한다.

## 실행 전 자가점검

`scripts/inspect_register_footprint.py`가 `src/kernels.cu`를 `-Xptxas=-v`로 컴파일해 다음을 기록한다.

| 항목 | 단위 | 의미 |
|---|---|---|
| `ptxas_registers_per_thread` | registers/thread | 실제 compiler-visible register count |
| `compiler_footprint_bytes_per_block` | B/block | `ptxas_registers/thread * 32 * 4` |
| `compiler_footprint_bytes_per_sm` | B/SM | footprint per block * requested blocks/SM |
| `spill_free` | true/false | stack frame, spill stores, spill loads가 모두 0인지 |
| `max_resident_blocks_per_sm_est` | blocks/SM | register/thread, max blocks, max warps, max threads 기반 추정 |

`blocks/SM`이 `max_resident_blocks_per_sm_est`를 넘거나 spill-free가 아니면 기본 runner는 해당 좌표를 실행하지 않는다. 필요할 때만 `--allow-spills`로 spill 포함 실험을 따로 수행한다.

## 실행 예시

Dry-run matrix:

```bash
python3 scripts/run_register_footprint_sweep.py \
  --binary ./build/a100_fp16_energy_v2 \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --reg-payload-bytes-values 256,512,1024,2048,4096,8192,16384 \
  --blocks-per-sm-values 1,2,4,8,16 \
  --active-sm-values 82 \
  --reuse-factors 1,2,4,8 \
  --seconds 10 \
  --repeats 3 \
  --matrix-csv results/raw/rtx3090_register_footprint_matrix.csv \
  --ptxas-csv results/summary/rtx3090_register_footprint_ptxas.csv
```

실행:

```bash
python3 scripts/run_register_footprint_sweep.py \
  --binary ./build/a100_fp16_energy_v2 \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --reg-payload-bytes-values 256,512,1024,2048,4096,8192,16384 \
  --blocks-per-sm-values 1,2,4,8,16 \
  --active-sm-values 82 \
  --reuse-factors 1,2,4,8 \
  --seconds 10 \
  --repeats 3 \
  --output results/raw/rtx3090_register_footprint_20260703.csv \
  --calibration-output results/raw/rtx3090_register_footprint_20260703_calibration.csv \
  --matrix-csv results/raw/rtx3090_register_footprint_20260703_matrix.csv \
  --ptxas-csv results/summary/rtx3090_register_footprint_20260703_ptxas.csv \
  --execute
```

분석:

```bash
python3 scripts/analyze_register_footprint.py \
  results/raw/rtx3090_register_footprint_20260703.csv \
  --matrix-csv results/raw/rtx3090_register_footprint_20260703_matrix.csv \
  --out-csv results/summary/rtx3090_register_footprint_20260703_summary.csv \
  --out-md results/summary/rtx3090_register_footprint_20260703_summary.md
```

## 해석

| 비교 | 계산 | 단위 | 의미 |
|---|---|---|---|
| scalar register pressure | `reg_pressure - empty` | pJ/reg-update | Tensor Core 없는 scalar register payload/control coefficient |
| WMMA MMA incremental | `reg_mma - reg_operand_only` | pJ/FLOP | register-fragment control 대비 MMA 추가분 후보 |

두 값을 같은 “순수 register energy”로 부르면 안 된다. 전자는 scalar register pressure 계수이고, 후자는 WMMA/Tensor Core 경로의 matched-control 차분이다.
