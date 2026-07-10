# GPU architecture 고려 컴포넌트 에너지 재점검 보고서

작성일: 2026-07-03

## 결론

RTX 3090에서 실험을 넓혀 다시 확인한 결과, 전역 OLS나 단순
`load_only - empty` 차분 대신 다음 구조가 현재 코드에서 가장 방어 가능하다.

| 컴포넌트 | 채택 방식 | 최종 판정 |
|---|---|---|
| Tensor Core | `reg_mma - reg_operand_only` matched pair의 power-rate median | 조건부 채택 |
| Register operand | `reg_operand_only` 내부 power-vs-logical-op-rate slope | 조건부 채택, 단위는 logical event 기준 |
| Shared/L1, L2, DRAM | `shared <= L2 <= DRAM` ordered memory rate model | 조건부 채택, NCU actual traffic 전까지 effective path coefficient |
| NCU 검증 | 시도했으나 환경 문제로 미완료 | blocker 기록 필요 |
| A100/V100/H100 | dry-run matrix로 regime boundary 확인 | 실제 계수는 각 노드에서 재실험 필요 |

현재 보고 가능한 RTX 3090 컴포넌트별 유효 에너지 값은 다음과 같다.

| 컴포넌트 | 결과 | 단위 | 보조 환산 |
|---|---:|---|---:|
| Tensor Core incremental | 0.219729 | pJ/FLOP | positive-pair median 0.237645 pJ/FLOP |
| Register operand | 8351.222 | pJ/logical-reg-op | 1.019436 pJ/logical-operand-bit |
| Shared/L1 increment | 49.641 | pJ/byte | 6.205 pJ/bit |
| L2 increment over Shared/L1 | 10.784 | pJ/byte | 1.348 pJ/bit |
| DRAM increment over L2 | 169.443 | pJ/byte | 21.180 pJ/bit |

Memory path 전체 비용은 increment를 누적해서 해석한다.

| Memory path | 결과 | 단위 | pJ/bit |
|---|---:|---|---:|
| Shared/L1 cumulative path | 49.641 | pJ/byte | 6.205 |
| L2-hit cumulative path | 60.425 | pJ/byte | 7.553 |
| DRAM streaming cumulative path | 229.868 | pJ/byte | 28.733 |

이 값은 순수 SRAM/L2/HBM bitcell energy가 아니다. NVML board energy와 static
expected traffic으로 추정한 **effective microbenchmark coefficient**다.
문헌 pJ/bit 값과 비교할 때도 device/circuit energy, GPU hierarchy transaction
energy, board-level effective coefficient를 분리해야 한다. 상세 감사는
`docs/literature_energy_values_audit_ko.md`에 기록했다.

## 수정 필요사항 점검

| 항목 | 상태 | 판단 |
|---|---|---|
| 단순 paired-difference 문서 | `component_energy_decomposition_experiment_design_ko.md`에 아직 강조 구간 존재 | 최종 보고에서는 diagnostic-only로 낮춰야 함 |
| 전역 OLS 회귀 | 음수/0-bound 문제가 있었음 | 최종값 산출에는 부적합 |
| fixed-ITER 단독 추정 | byte variation은 커지지만 elapsed spread가 큼 | monotonicity/stress-test 전용 |
| partial `active_SM` sweep | SMID 17/68, 음수 net rows 14개 | 최종 추정에서 제외 |
| full-SM `blocks/SM` memory sweep | SMID 45/45 pass | memory hierarchy 분리에 사용 |
| NCU 검증 | sudo는 sandbox 차단, non-sudo는 stub CUDA driver 오류 | actual traffic 검증 미완료 |
| H100 지원 | profile은 있으나 kernel은 WMMA 중심 | H100 WGMMA/TMA 전용 에너지로 해석 금지 |

## GPU architecture 고려

| GPU | CC | SM 수 | L2 | shared/SM | Tensor 지원 | 실험상 주의 |
|---|---:|---:|---:|---:|---|---|
| V100 | 7.0 | 80 | 6 MiB | 96 KiB usable shared | FP16 WMMA | TF32/BF16 없음, `blocks/SM=32` 가능 |
| RTX 3090 | 8.6 | 82 | 6 MiB | 100 KiB usable shared | FP16/TF32/BF16/INT/sparsity | `blocks/SM=32` invalid, NVML power usage는 1초 평균 의미 |
| A100 | 8.0 | 108 | 40 MiB | 164 KiB usable shared | FP16/TF32/BF16/FP64 TC/INT/sparsity | L2가 커서 DRAM boundary가 RTX/V100보다 뒤로 이동 |
| H100 | 9.0 | 132 profile 기준 | 50 MiB profile 기준 | 228 KiB usable shared | FP16/BF16/TF32/FP8/WGMMA/TMA | 현재 kernel은 WMMA path이므로 Hopper 특화 WGMMA/TMA energy 아님 |

Architecture별 dry-run matrix 결과:

| Profile | matrix rows | valid rows | shared/L2 후보 `W_SM` | DRAM 후보 `W_SM` |
|---|---:|---:|---|---|
| RTX 3090 | 300 | 165 | 1-64 KiB | 128, 512, 8192 KiB |
| V100 | 300 | 192 | 1-64 KiB | 128, 512, 8192 KiB |
| A100 | 300 | 198 | 1-128 KiB | 512, 8192 KiB |
| H100 | 300 | 198 | 1-128 KiB | 512, 8192 KiB |

이 결과는 L2 크기와 shared capacity 차이가 matrix에 반영되고 있음을 보여준다.
A100/H100은 L2가 크므로 RTX 3090/V100에서 DRAM 후보인 128 KiB가 L2/shared
후보 영역으로 남는다.

## 추가 실험

### 1. partial active-SM sweep

목적은 active SM 수를 바꿔 access-rate 축을 넓히는 것이었다.

| Raw | rows | SMID pass | negative net rows | ITER |
|---|---:|---:|---:|---|
| `rtx3090_component_rate_active_sm_20260703.csv` | 68 | 17 | 14 | 500000 |

판단: partial SM 배치가 의도대로 고정되지 않았고 짧은 row에서 idle subtraction
noise가 커졌다. 최종 계수 산출에서는 제외한다.

### 2. full-SM blocks/SM memory sweep

목적은 full SM을 유지한 상태에서 `blocks/SM=1,2,4,8,16`을 바꿔 memory
access-rate 축을 넓히는 것이었다.

| Raw | rows | SMID pass | negative net rows | ITER |
|---|---:|---:|---:|---|
| `rtx3090_component_rate_blocks_20260703.csv` | 45 | 45 | 6 | 500000 |

판단: SMID가 모두 통과했고, negative rows는 짧은 low-work rows에 제한됐다.
non-negative/ordered rate model에서 사용할 수 있다.

## 분석 방식

### Tensor

Tensor는 `reg_mma`와 `reg_operand_only`를 같은 좌표로 matching한 뒤,
power-rate 기준으로 차분했다.

```text
Tensor pJ/FLOP =
  (P_reg_mma - P_reg_operand_only) / FLOP_rate_reg_mma
```

QA:

| 항목 | 결과 |
|---|---:|
| matched pairs | 19 |
| positive pairs | 16/19 |
| all-pair median | 0.219729 pJ/FLOP |
| positive-pair median | 0.237645 pJ/FLOP |

### Register

Register는 `reg_operand_only - empty`가 전부 음수였으므로 폐기했다. 대신
`reg_operand_only` 내부에서 logical register operand rate와 power의 slope를
사용했다.

| 항목 | 결과 |
|---|---:|
| rows | 35 |
| slope | 8351.222 pJ/logical-reg-op |
| logical operand bit 환산 | 1.019436 pJ/logical-operand-bit |
| relative RMSE | 16.788% |

주의: 이 값은 register-file port 1회 access가 아니라 현재 kernel의
`expected_reg_operand_ops` logical event 기준이다.

### Shared/L1, L2, DRAM

Memory는 unconstrained slope에서 L2가 음수로 떨어지는 문제가 있었다. 따라서
architecture 상식에 맞게 다음 ordered model을 사용했다.

```text
shared_path <= l2_hit_path <= dram_streaming_path

shared_path = shared_increment
l2_path     = shared_increment + l2_increment
dram_path   = shared_increment + l2_increment + dram_increment
```

QA:

| 항목 | 결과 |
|---|---:|
| rows used | 99 |
| active-set iterations | 4 |
| RMSE | 24.399 W |
| relative RMSE | 15.426% |

## NCU 검증 상태

NCU 검증은 실행을 시도했지만 현재 세션에서는 완료하지 못했다.

| 시도 | 결과 |
|---|---|
| `sudo -n ncu` | sandbox `no new privileges` 때문에 sudo 차단 |
| non-sudo `ncu` | `Nsight Compute failed to connect to the CUDA driver (stub libcuda.so...)` |
| `LD_LIBRARY_PATH=/usr/lib/wsl/lib` | NCU driver 문제는 유지, 벤치마크 NVML 초기화도 실패 |

따라서 이번 보고서의 memory 계수는 actual NCU traffic denominator가 아니라
static expected traffic denominator다. 최종 논문 수준 주장을 위해서는 다음
표가 필요하다.

| NCU 필수 항목 | 필요 이유 |
|---|---|
| L1 hit rate (%) | shared/L1 path가 의도대로 동작했는지 확인 |
| L2 hit rate (%) | L2 candidate가 실제 L2 hit인지 확인 |
| L1 access count | expected shared/global load와 실제 request 비교 |
| L2 sector count | L2-hit path denominator 보정 |
| DRAM sector/byte count | DRAM streaming denominator 보정 |
| stall percentage | long scoreboard, memory dependency, issue stall이 energy slope에 섞였는지 확인 |

## 최종 판단

| 질문 | 판단 |
|---|---|
| Tensor/register/shared/L1/L2/DRAM으로 모두 양수 분리됐는가? | 예, effective coefficient 기준으로는 분리됨 |
| 값이 물리 component energy인가? | 아니오, static traffic 기반 effective microbenchmark coefficient |
| L2가 shared보다 커지고 DRAM이 가장 큰가? | ordered model에서 `Shared/L1 < L2-hit < DRAM`으로 정합 |
| A100/V100/H100에 그대로 적용 가능한가? | 실행 framework는 가능하지만 각 GPU에서 재측정 필요 |
| H100 특화 Tensor/WGMMA까지 지원하나? | 아니오, 현재는 WMMA 기반 compatibility path |
| NCU로 최종 검증됐나? | 아니오, 환경 blocker로 미완료 |

현재 보고 가능한 결론은 다음이다.

> RTX 3090에서 FP16 WMMA microbenchmark를 기준으로 Tensor, register,
> Shared/L1, L2, DRAM의 유효 에너지 계수는 모두 양수로 분리됐다. 다만 이 값은
> board-level NVML energy와 static expected traffic에 기반한 effective
> coefficient이며, 순수 하드웨어 bitcell energy로 해석하려면 NCU actual traffic
> 및 stall 검증이 추가로 필요하다.

## 산출물

| 파일 | 내용 |
|---|---|
| `results/summary/rtx3090_component_energy_estimates_20260703_ko.md` | 최종 컴포넌트별 수치 요약 |
| `results/summary/rtx3090_component_energy_estimates_20260703.csv` | 수치 CSV |
| `results/raw/rtx3090_component_rate_blocks_20260703.csv` | full-SM blocks/SM memory sweep |
| `results/raw/rtx3090_component_rate_active_sm_20260703.csv` | partial active-SM sweep, 최종 제외 |
| `results/raw/arch_matrix_*.csv` | GPU profile별 dry-run feasibility matrix |
| `scripts/estimate_component_energy.py` | 컴포넌트별 추정 analyzer |
