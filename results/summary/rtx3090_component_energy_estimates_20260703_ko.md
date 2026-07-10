# RTX 3090 컴포넌트별 유효 에너지 추정 결과

작성일: 2026-07-03

> 2026-07-04 정정: 이 문서의 memory hierarchy 값은 static expected byte와
> `shared/L1` 묶음 기반 legacy 결과다. reference-aligned 최종 후보로 쓰지
> 않는다. NCU actual traffic 기반 재실험 결과는
> `results/summary/rtx3090_reference_aligned_redo_report_20260704_ko.md`와
> `results/summary/rtx3090_reference_aligned_memory_b16_20260704_ko.md`를
> 우선한다.

## 요약

이번 재실험/재분석에서는 전역 OLS 하나로 모든 컴포넌트를 강제로 분리하지
않고, 컴포넌트별로 맞는 축을 사용했다.

| 컴포넌트 | 산출 방식 | 결과 | 단위 | 보조 환산 |
|---|---|---:|---|---:|
| Tensor Core incremental | `reg_mma - reg_operand_only` matched pair의 power-rate median | 0.219729 | pJ/FLOP | positive-pair median 0.237645 pJ/FLOP |
| Register operand | `reg_operand_only`의 power-vs-logical-op-rate slope | 8351.222 | pJ/logical-reg-op | 1.019436 pJ/logical-operand-bit |
| Shared/L1 increment | ordered memory rate model의 base term | 49.641 | pJ/byte | 6.205 pJ/bit |
| L2 increment over Shared/L1 | ordered memory rate model의 L2 추가분 | 10.784 | pJ/byte | 1.348 pJ/bit |
| DRAM increment over L2 | ordered memory rate model의 DRAM 추가분 | 169.443 | pJ/byte | 21.180 pJ/bit |

## Memory cumulative path

increment와 path 전체 비용은 다르게 봐야 한다. 예를 들어 L2-hit path는
Shared/L1 base + L2 increment로 계산된다.

| Path | 결과 | 단위 | pJ/bit |
|---|---:|---|---:|
| Shared/L1 cumulative path | 49.641 | pJ/byte | 6.205 |
| L2-hit cumulative path | 60.425 | pJ/byte | 7.553 |
| DRAM streaming cumulative path | 229.868 | pJ/byte | 28.733 |

## 실험/분석 QA

| 항목 | 결과 |
|---|---:|
| Tensor matched pairs | 19 |
| Tensor positive pairs | 16/19 |
| Register rows | 35 |
| Register relative RMSE | 16.788% |
| Memory rows | 99 |
| Memory ordered fit relative RMSE | 15.426% |
| Memory active-set iterations | 4 |
| `blocks/SM` memory sweep SMID | 45/45 pass |

## 해석

Tensor Core incremental 값은 `reg_mma`에서 `reg_operand_only`를 뺀 matched
pair 기반이다. 따라서 register fragment/control 비용을 일부 제거한 Tensor
Core incremental 후보로 볼 수 있다.

Register 값은 실제 register-file port 하나의 물리 에너지가 아니라,
`reg_operand_only` kernel에서 정의한 logical WMMA operand event 기준이다.
1 logical register operand event는 현재 분석에서 8192 logical operand bit로
환산했다.

Memory 값은 ordered 제약을 둔 power-rate 모델로 계산했다.

```text
Shared/L1 path <= L2-hit path <= DRAM streaming path

shared_path = shared_increment
l2_path     = shared_increment + l2_increment
dram_path   = shared_increment + l2_increment + dram_increment
```

이 제약을 넣은 이유는 이전 unconstrained 모델에서 L2 slope가 음수 또는 0으로
붙는 문제가 있었기 때문이다. `blocks/SM` full-SM sweep를 추가해 access-rate
축을 넓혔고, 그 결과 Shared/L1, L2, DRAM을 모두 양수 increment로 분리했다.

## 제한

이 값들은 NVML board energy와 static expected traffic을 사용한
**effective microbenchmark coefficient**다. 특히 memory 값은 load instruction,
address/control, dependency, stall, scheduler, cache path가 함께 포함된다.
따라서 순수 SRAM/L2/DRAM bitcell energy로 쓰면 안 된다.

최종 논문/보고서에서 물리 계층 주장을 하려면 같은 대표 좌표에 대해 NCU actual
L1/L2/DRAM access count, hit rate, stall percentage를 join해야 한다.

## 산출물

| 파일 | 내용 |
|---|---|
| `results/summary/rtx3090_component_energy_estimates_20260703.csv` | 컴포넌트별 추정값 CSV |
| `results/summary/rtx3090_component_energy_estimates_20260703.md` | 영어/기계 판독형 요약 |
| `results/raw/rtx3090_component_rate_blocks_20260703.csv` | full-SM `blocks/SM` memory sweep raw |
| `results/raw/rtx3090_component_rate_blocks_mem_20260703_matrix.csv` | full-SM `blocks/SM` memory sweep matrix |
