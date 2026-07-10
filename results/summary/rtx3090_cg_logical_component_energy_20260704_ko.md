# RTX 3090 Logical Component Energy Analysis

## 결론

고정 ITER + NCU traffic sweep에서 hierarchical residual 기준 `L2 < DRAM` 순서가 성립했다. 단, 이 값은 NVML board-level effective coefficient이며 물리 bitcell energy가 아니다.

핵심 주의점은 NVML energy가 board 전체 전력이고, `l2_cg_load_only`와 `dram_cg_load_only`의 long-scoreboard stall 및 active power가 traffic 증가와 함께 변하기 때문이다. 즉 같은 byte 수라도 SM issue rate와 memory stall이 다르면 단순 `J/bit`가 component energy만 나타내지 않는다.

RTX 3090에서는 `L2/SM = 6 MiB / 82 SM ≈ 74.9 KiB/SM`이고, `blocks/SM=16`에서 shared/L1-resident 상한은 대략 `100 KiB - 16 KiB = 84 KiB/SM`이다. 그래서 `W_SM`만으로는 `L1에는 안 맞지만 L2에는 맞는` 구간이 없다. 이 보고서는 그 한계를 `ld.global.cg` 기반 `l2_cg_load_only`로 보완해 L1 hit를 거의 0%로 낮춘 뒤 L2 hit path를 따로 측정한 결과다.

## 입력 데이터

| 항목 | 값 |
|---|---|
| joined energy+NCU CSV | `results/raw/rtx3090_cg_fixediter_lr_sweep_20260704_joined_ncu.csv` |
| register summary CSV | `results/summary/rtx3090_register_footprint_focus_20260703_summary.csv` |
| tensor/register pairs CSV | `results/summary/rtx3090_register_tensor_pairs_20260702_summary.csv` |
| selected blocks/SM | 16 |
| selected active_SM (SMs) | 82 |
| L1 W_SM (KiB) | 16 |
| shared W_SM (KiB) | 64 |
| L2 W_SM (KiB) | 64 |
| DRAM W_SM (KiB) | 8192 |

## NCU Acceptance Summary

| 항목 | 값 | 단위 |
|---|---:|---|
| detail rows | 104 | rows |
| accepted rows | 59 | rows |
| rejected rows | 45 | rows |
| accepted `global_l1_path` | 15 | rows |
| accepted `shared_l1_path` | 14 | rows |
| accepted `l2_hit_path` | 15 | rows |
| accepted `dram_streaming_path` | 15 | rows |

| rejection reason | rows |
|---|---:|
| missing_ncu_join | 45 |

## Mode Meaning

| mode | selected W_SM | interpretation | denominator |
|---|---:|---|---|
| `global_l1_load_only` | 16 KiB | L1-hit global load path | NCU L1 bytes |
| `shared_load_only` | 64 KiB | shared-memory operand load path | expected shared bytes, NCU shared accesses for validation |
| `l2_cg_load_only` | 64 KiB | L2-hit global load path | NCU L2 bytes |
| `dram_cg_load_only` | 8192 KiB | DRAM streaming global load path | NCU DRAM bytes |

## Component Estimates

| kind | component | estimate | unit | rows | LR values | R2 | RMSE (J) | L1 hit (%) | L2 hit (%) | long scoreboard (%) | status | notes |
|---|---|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|
| register_scalar_control | scalar_register_pressure | 140.563 | pJ/reg-update | 10 |  |  |  |  |  |  | diagnostic_only | reg_pressure-empty; not pure register-file pJ/bit |
| tensor_register_pair | wmma_tensor_register_increment | 0.383763 | pJ/FLOP | 17 |  |  |  |  |  |  | diagnostic_only | reg_mma-reg_operand_only; effective Tensor+register, not pure Tensor Core |
| path_slope | shared_l1_path | 5.83392 | pJ/bit | 14 | 1,2,4,8,16 | 0.997658 | 8.39351 | 27.7134 | 53.9369 | 0.000145 | ok |  |
| path_slope | global_l1_path | 3.09049 | pJ/bit | 15 | 1,2,4,8,16 | 0.995597 | 12.0504 | 99.9992 | 55.4988 | 19.2038 | ok |  |
| path_slope | l2_hit_path | 11.5683 | pJ/bit | 15 | 1,2,4,8,16 | 0.999181 | 9.71717 | 2e-06 | 99.9406 | 988.773 | ok |  |
| path_slope | dram_streaming_path | 31.5808 | pJ/bit | 15 | 1,2,4,8,16 | 0.999591 | 18.7669 | 2e-06 | 0.155437 | 1865.97 | ok |  |
| hierarchical_residual | l2_increment_residual | 8.48107 | pJ/bit | 15 | 1,2,4,8,16 | 0.998479 | 9.71353 | 2e-06 | 99.9406 | 988.773 | ok |  |
| hierarchical_residual | dram_increment_residual | 20.0117 | pJ/bit | 15 | 1,2,4,8,16 | 0.998983 | 18.7648 | 2e-06 | 0.155437 | 1865.97 | ok |  |
| nnls_mode_intercept | global_l1_component_nnls | 3.08321 | pJ/bit | 45 |  | 0.99958 | 14.0549 |  |  |  | ok | active_set_iterations=4 |
| nnls_mode_intercept | l2_increment_nnls | 8.46992 | pJ/bit | 45 |  | 0.99958 | 14.0549 |  |  |  | ok | active_set_iterations=4 |
| nnls_mode_intercept | dram_increment_nnls | 20.0301 | pJ/bit | 45 |  | 0.99958 | 14.0549 |  |  |  | ok | active_set_iterations=4 |

## Reference Check

| reference path | pJ/bit | interpretation |
|---|---:|---|
| GPUJoule K40 shared->RF | 5.32 | GPU transaction path |
| GPUJoule K40 L1->RF | 5.85 | GPU transaction path |
| GPUJoule K40 L2->L1 | 15.48 | GPU transaction path |
| GPUJoule K40 DRAM->L2 | 30.55 | external DRAM transaction path |
| HBM system DRAM->L2 assumption | 21.1 | HBM-based system path assumption |
| HBM2 device access | 3.95 | HBM device/access only, not SM-to-register path |

따라서 `L2 increment`와 `DRAM increment`가 비슷하게 나오면 reference 관점에서 물리 component energy로 받아들이면 안 된다. 그 경우는 stall, elapsed coupling, cache-counter denominator, 또는 커널 구조가 분리를 못 만든 것으로 해석해야 한다.

## Remaining Checks

1. 현재 CG 분석은 LR=1과 LR=16 NCU spot-check를 반영했고, 중간 LR=2/4/8은 NCU traffic scaling으로 결합했다. 최종 제출용 표에는 전체 LR별 NCU를 추가하면 가장 엄밀하다.
2. `ld.global.cg` mode는 Tensor/WMMA operand path가 아니라 data-movement calibration path다. Tensor 포함 결과와는 별도 표로 유지한다.
3. long-scoreboard stall이 크므로 pJ/bit는 physical SRAM/HBM bitcell 값이 아니라 effective board-level coefficient로 표기한다.
