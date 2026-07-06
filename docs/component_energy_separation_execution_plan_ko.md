# Component Energy 분리 실험 실행 계획

작성일: 2026-07-05

## 결론 요약

현재 목표는 GPU 물리 회로의 순수 bitcell energy를 직접 측정하는 것이 아니라,
동일 microbenchmark harness 안에서 관측되는 board-level effective coefficient를
분리하는 것이다. 최종 보고 대상은 다음 네 항목이다.

| Component/path | 목표 단위 | 최종 해석 |
|---|---:|---|
| Tensor 연산 | pJ/FLOP | no-MMA register/control 대비 FP16 WMMA 추가분 |
| Register operand/control | pJ/logical operand bit 또는 pJ/reg-update | spill-free register/control path 진단값 |
| Shared memory / global L1 | pJ/actual bit | shared instruction path와 global L1 hit path를 분리 |
| L2 hit | pJ/actual bit | L1 지배를 제거한 L2-hit transaction path |

DRAM은 필수 목표가 아니라 L2 분리의 sanity check로만 둔다. DRAM 값을 쓰는 경우도
HBM/GDDR device energy가 아니라 GPU transaction-path effective coefficient로
표기한다.

## 원문 아키텍처 검토

이번 설계는 NVIDIA whitepaper의 capacity를 기준으로 다시 정리했다.

| GPU | Source | Register file | L1/shared | L2 | 실험상 의미 |
|---|---|---:|---:|---:|---|
| RTX 3090 / GA102 | NVIDIA GA102 whitepaper Appendix A | 20,992 KiB total, 즉 256 KiB/SM | 10,496 KiB total, 즉 128 KiB/SM | 6,144 KiB | L2/SM이 약 74.9 KiB라 W_SM만으로 L1-miss/L2-hit 창을 만들기 어렵다. |
| A100 / GA100 | NVIDIA A100 whitepaper | 256 KiB/SM | 192 KiB combined L1/shared, shared allocation 최대 164 KiB/SM | 40 MiB | L2/SM이 약 379 KiB라 192-320 KiB W_SM으로 capacity 기반 L2-hit 실험이 가능하다. |

주의: 현재 harness profile의 RTX 3090 `shared_kib_per_sm=100`은 CUDA dynamic
shared allocation/실험 feasibility를 위한 보수적 값이다. whitepaper의 물리
combined L1/shared 128 KiB/SM과 같은 의미가 아니다.

## 기존 실험 평가

| 항목 | 판단 | 이유 | 새 결정 |
|---|---|---|---|
| `reg_mma`에서 `W_SM`을 register 크기로 해석 | 잘못 | register footprint는 `ptxas registers/thread * 32 threads * blocks/SM`로 결정된다. | `W_SM`은 register 실험 축으로 쓰지 않는다. |
| RTX 3090 일반 `l2_load_only`로 L2 분리 | 잘못 | W_SM=64 KiB는 L2에도 맞지만 L1/shared에도 맞아 L1 hit가 지배될 수 있다. | RTX 3090 L2는 `l2_cg_load_only`로 L1을 우회한다. |
| `*_load_only - empty` 단순 차분 | 부적절 | elapsed, issue, stall, checksum/address 비용이 함께 섞인다. | elapsed-aware 회귀와 NCU actual traffic을 사용한다. |
| DRAM 중심 재실험 | 우선순위 낮음 | 사용자가 원하는 핵심은 Tensor/Register/L1/L2다. | DRAM은 hierarchy sanity check로 제한한다. |
| static expected byte pJ/bit | smoke/진단용 | 실제 L1/L2/DRAM sector traffic이 아니다. | 최종 pJ/bit는 NCU actual byte 기준만 채택한다. |
| `scalar_register_pressure`를 RF energy로 해석 | 잘못 | scalar ALU, scheduler, register access, control이 섞인다. | `register operand/control diagnostic`으로만 보고한다. |

## 분리 전략

### Tensor

| Mode pair | 계산 | 단위 | 채택 조건 |
|---|---|---:|---|
| `reg_mma - reg_operand_only` | matched pair 또는 power-rate 회귀 | pJ/FLOP | tensor instruction count > 0, spill/local memory 0 |

`reg_operand_only`는 pure register energy가 아니라 Tensor Core가 없는
register-fragment/control baseline이다. 따라서 결과명은 `Tensor Core incremental`
또는 `effective Tensor + register incremental`로 쓴다.

### Register operand/control

| 축 | 설명 |
|---|---|
| primary axis | `reg_payload_bytes_per_block`, `blocks/SM`, `reuse_factor` |
| 금지 | `W_SM`을 register working set으로 해석하지 않는다. |
| 검증 | ptxas registers/thread, spill store/load 0, NCU local memory 0 |

최종 표기는 `Register operand/control path`로 제한한다. 순수 register file
pJ/access라고 쓰지 않는다.

### Shared memory와 global L1

| Path | Mode | W_SM 후보 | Denominator |
|---|---|---:|---|
| Shared memory instruction path | `shared_load_only` | RTX 3090: 16, 32, 64 KiB / A100: 32, 64, 128 KiB | NCU shared access/byte, fallback은 expected shared bytes |
| Global L1 hit path | `global_l1_load_only` | RTX 3090: 4, 8, 16 KiB / A100: 4, 8, 16, 32 KiB | NCU L1 bytes |

Shared memory와 global L1 cache는 Ampere에서 combined capacity를 공유하지만,
instruction path가 다르므로 최종 표에서 분리한다.

### L2

| GPU | 설계 |
|---|---|
| RTX 3090 | `l2_cg_load_only`를 사용한다. W_SM만으로 L1-miss/L2-hit 구간을 만들기 어렵기 때문이다. |
| A100 | capacity 기반 `l2_load_only`를 기본으로 하고, `l2_cg_load_only`를 control로 비교한다. 후보 W_SM은 192, 256, 320 KiB다. |

L2 row 채택 기준은 capacity rule이 아니라 NCU다.

| 기준 | 통과 조건 |
|---|---:|
| L1 hit rate | RTX 3090 CG L2 row는 1% 미만 권장 |
| L2 hit rate | 95% 이상 권장 |
| DRAM/L2 byte ratio | 1-2% 이하 권장 |
| long scoreboard | 값 자체를 숨기지 않고 보고 |

## Sweep 설계

### RTX 3090

| Component | blocks/SM | W_SM | factor sweep | 목적 |
|---|---:|---:|---:|---|
| Tensor | 1, 2, 4, 8, 16 | register mode에서는 해석 금지 | reuse_factor 1, 2, 4, 8, 16 | pJ/FLOP |
| Register/control | 1, 2, 4, 8, 16 | 사용 금지 | reg payload 256 B-16 KiB/block | spill-free 진단 |
| Shared | 1, 2, 4, 8, 16 | 16, 32, 64 KiB | load_repeat 1, 2, 4, 8, 16 | shared path pJ/bit |
| Global L1 | 1, 2, 4, 8, 16 | 4, 8, 16 KiB | load_repeat 1, 2, 4, 8, 16 | L1 hit path |
| L2 | 1, 2, 4, 8, 16 | 64 KiB 중심 | load_repeat 1, 2, 4, 8, 16 | CG 기반 L2-hit |
| DRAM optional | 8, 16 | 8192 KiB 이상 | load_repeat 1, 2, 4, 8, 16 | sanity check |

### A100

| Component | blocks/SM | W_SM | factor sweep | 목적 |
|---|---:|---:|---:|---|
| Tensor | 1, 2, 4, 8, 16, 32 | register mode에서는 해석 금지 | reuse_factor 1, 2, 4, 8, 16 | pJ/FLOP |
| Register/control | 1, 2, 4, 8, 16, 32 | 사용 금지 | reg payload 256 B-16 KiB/block | spill-free 진단 |
| Shared | 1, 2, 4, 8, 16, 32 | 32, 64, 128 KiB | load_repeat 1, 2, 4, 8, 16 | shared path |
| Global L1 | 1, 2, 4, 8, 16, 32 | 4, 8, 16, 32 KiB | load_repeat 1, 2, 4, 8, 16 | L1 hit path |
| L2 | 1, 2, 4, 8, 16, 32 | 192, 256, 320 KiB | load_repeat 1, 2, 4, 8, 16 | capacity 기반 L2-hit |
| DRAM optional | 8, 16, 32 | 8192 KiB 이상 | load_repeat 1, 2, 4, 8, 16 | sanity check |

## 회귀 모델

Energy run은 NCU 없이 수행하고, NCU는 sidecar로 actual traffic과 stall만 얻는다.

```text
P_dynamic =
  alpha_mode
  + beta_tensor * FLOP_rate
  + beta_register_control * logical_operand_bit_rate
  + beta_shared * ncu_shared_bit_rate
  + beta_l1 * ncu_l1_bit_rate
  + beta_l2_increment * ncu_l2_bit_rate
  + beta_dram_increment * ncu_dram_bit_rate
  + residual
```

최종 reporting은 cumulative path와 increment를 분리한다.

```text
Global L1 path = beta_l1
L2 path        = beta_l1 + beta_l2_increment
DRAM path      = beta_l1 + beta_l2_increment + beta_dram_increment
```

음수 coefficient는 0으로 둔 뒤 `zero_bound_or_not_identified`로 보고한다. 0 pJ라는
뜻이 아니라 현재 matrix에서 양의 독립 slope가 식별되지 않았다는 뜻이다.

## 실행 결과: 2026-07-05 RTX 3090

### Preflight

| 항목 | 값 |
|---|---|
| 파일 | `results/summary/component_energy_preflight_20260705.md` |
| GPU | NVIDIA GeForce RTX 3090 |
| detected profile | `rtx3090` |
| compute capability | 8.6 |
| SM | 82 |
| L2 | 6 MiB |
| harness shared/SM | 100 KiB |
| Nsight Compute chip support | pass |
| NCU metric query | pass |
| binary dry-run | pass |

### 설계 matrix dry-run

| 항목 | 값 |
|---|---:|
| matrix file | `results/raw/rtx3090_component_sep_plan_matrix_20260705.csv` |
| total rows including invalid | 288 |
| valid commands | 228 |
| invalid/skipped rows | 60 |

| valid mode | commands |
|---|---:|
| `empty` | 36 |
| `clocked_empty` | 36 |
| `reg_operand_only` | 36 |
| `reg_mma` | 36 |
| `global_l1_load_only` | 24 |
| `shared_load_only` | 24 |
| `l2_cg_load_only` | 24 |
| `dram_cg_load_only` | 12 |

### Smoke energy 실행

| 항목 | 값 |
|---|---|
| raw CSV | `results/raw/rtx3090_component_sep_smoke_20260705.csv` |
| matrix CSV | `results/raw/rtx3090_component_sep_smoke_matrix_20260705.csv` |
| fit report | `results/summary/rtx3090_component_sep_smoke_fit_20260705.md` |
| rows | 38 |
| non-positive net energy rows | 0 |
| SMID placement failures | 0 |
| elapsed range | 0.977-1.121 s |
| static-byte regression relative RMSE | 4.204% |

Smoke 결과는 실행 가능성 확인용이다. NCU actual traffic이 join되지 않았으므로
최종 component pJ/bit 표에는 쓰지 않는다.

| mode | rows | avg elapsed (s) | avg net_E (J) |
|---|---:|---:|---:|
| `empty` | 6 | 1.049 | 182.222 |
| `clocked_empty` | 6 | 1.081 | 184.627 |
| `reg_operand_only` | 6 | 1.092 | 108.572 |
| `reg_mma` | 6 | 1.058 | 121.974 |
| `global_l1_load_only` | 4 | 1.111 | 210.466 |
| `shared_load_only` | 4 | 1.099 | 206.156 |
| `l2_cg_load_only` | 4 | 1.109 | 209.003 |
| `dram_cg_load_only` | 2 | 1.101 | 232.910 |

### NCU sidecar 실행

| 항목 | 값 |
|---|---|
| NCU outdir | `results/ncu/rtx3090_component_sep_ncu_20260705/` |
| NCU summary | `results/ncu/rtx3090_component_sep_ncu_20260705/ncu_cache_validation_summary.md` |
| raw sidecar CSV | `results/raw/rtx3090_component_sep_ncu_20260705.csv` |
| joined CSV | `results/raw/rtx3090_component_sep_ncu_20260705_joined.csv` |
| cases | 16 |
| NCU status | 16/16 `ok` |
| warning | caches/clocks uncontrolled; final run에서는 그대로 보고하거나 clock 고정 필요 |

대표 row의 NCU 결과는 다음과 같다.

| mode | W_SM (KiB) | L1 hit (%) | L2 hit (%) | L1 bytes | L2 bytes | DRAM bytes | Long SB stall (%) | 판단 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `global_l1_load_only` | 16 | 99.999 | 49.885 | 1.07479e12 | 4.11585e8 | 3.27690e8 | 17.433 | global L1 hit row로 채택 가능 |
| `shared_load_only` | 64 | 27.206 | 52.647 | 0 | 5.00667e8 | 3.86795e8 | 0.000552 | shared access 8.73754e9 확인, shared path 후보 |
| `l2_load_only` | 64 | 88.376 | 99.707 | 1.07479e12 | 1.25350e11 | 3.71825e8 | 70.722 | L1 지배, RTX 3090 L2 최종 row에서 제외 |
| `l2_cg_load_only` | 64 | 0.000006 | 99.922 | 5.37395e11 | 5.38071e11 | 6.16754e8 | 865.575 | RTX 3090 L2-hit row로 채택 가능 |
| `dram_cg_load_only` | 8192 | 0.000007 | 0.162 | 5.37395e11 | 5.39430e11 | 5.39078e11 | 1801.640 | DRAM sanity row, stall 매우 큼 |

이 결과는 이전 판단을 다시 확인한다. RTX 3090에서 일반 `l2_load_only`는 L2 hit가
높아 보여도 L1 hit가 88.376%라 L2 component 분리용으로 부적절하다. 반면
`l2_cg_load_only`는 L1 hit가 사실상 0%이고 L2 hit가 99.922%라 RTX 3090의 L2
분리에는 CG 경로를 써야 한다.

## 다음 실행 순서

### 1. RTX 3090 NCU sidecar 확장

대표 좌표 검증은 완료됐다. 최종 memory coefficient 전에는 `LOAD_REPEAT=1,2,4,8,16`
또는 final energy sweep 좌표 전체에 대해 NCU sidecar를 확장한다.

```bash
NCU_EXPLICIT_METRICS_ONLY=1 \
NCU=/home/bang001/miniforge3/envs/ssc21env/bin/ncu \
OUTDIR=results/ncu/rtx3090_component_sep_ncu_lrX_YYYYMMDD \
RAW_OUT=results/raw/rtx3090_component_sep_ncu_lrX_YYYYMMDD.csv \
TARGET_PROFILE=rtx3090 \
GPU=0 \
BLOCKS_PER_SM=16 \
ACTIVE_SM=82 \
L1_W_SM_KIB=16 \
SHARED_W_SM_KIB=64 \
L2_W_SM_KIB=64 \
DRAM_W_SM_KIB_OVERRIDE=8192 \
LOAD_REPEAT=<1|2|4|8|16> \
bash scripts/run_ncu_validation.sh
```

채택 표에는 L1 hit rate (%), L2 hit rate (%), L1/L2/DRAM bytes, shared access,
spill/local memory, long scoreboard stall (%)를 모두 넣는다.

### 2. RTX 3090 final energy

NCU pass 후 final은 다음 조건으로 확장한다.

| 항목 | 값 |
|---|---:|
| seconds | 20-30 s |
| repeats | 7 이상 |
| blocks/SM | 1, 2, 4, 8, 16 |
| load_repeat | 1, 2, 4, 8, 16 |
| reuse_factor | 1, 2, 4, 8, 16 |
| row order | repeat별 rotate 또는 randomized |

### 3. A100 실행

A100에서는 RTX 3090 결과를 그대로 쓰지 않는다. 먼저 preflight 후 다음을 확인한다.

| 확인 | 기준 |
|---|---|
| profile | `a100`, CC 8.0, SM 수 runtime 확인 |
| shared/L1 | 192 KiB combined, shared allocation 최대 164 KiB/SM |
| L2 | 40 MiB |
| L2 row | W_SM 192, 256, 320 KiB에서 NCU L2 hit > 95% |
| async copy | 현 harness는 WMMA/global/shared path이며 A100 `cp.async` path와 구분 |

## 최종 보고서 필수 표

| 표 | 필수 열 |
|---|---|
| GPU architecture | GPU, SM, register/SM (KiB), L1/shared (KiB), L2 (MiB), source |
| sweep 조건 | mode, W_SM (KiB), blocks/SM, active_SM (SM), reuse_factor, load_repeat, seconds (s), repeats |
| NCU validation | L1 hit (%), L2 hit (%), L1 bytes, L2 bytes, DRAM bytes, shared accesses, stall_long_scoreboard (%) |
| accepted rows | component, accepted rows, rejected rows, rejected reason |
| coefficients | component/path, estimate, unit, min, avg/median, max, CI, denominator, status |
| 제한 | board-level effective coefficient, not pure physical bitcell energy |

## 현재 판정

| 질문 | 판정 |
|---|---|
| 지금 완전히 잘 분리됐는가? | 아니다. RTX 3090 L2는 CG 기반으로 개선됐지만, final은 NCU sidecar 전체 검증 후 가능하다. |
| 불필요하게 한 실험이 있는가? | 있다. DRAM 중심 반복과 일반 `l2_load_only` L2 해석은 최종 목적 대비 우선순위가 낮거나 부적절했다. |
| 지금 실행 가능한가? | 가능하다. 2026-07-05 preflight와 38-row smoke energy 실행이 통과했다. |
| 다음 핵심은 무엇인가? | RTX 3090 NCU sidecar로 L1/shared/L2-CG traffic을 확인하고, 그 뒤 final duration/repeat로 확장한다. |
