# RTX 3090 Logical Component Energy Analysis

## 결론

이번 데이터에서는 hierarchical residual 기준의 `L2 < DRAM` 분리가 안정적으로 성립하지 않았다. 따라서 L2와 DRAM 값을 억지로 reference 순서에 맞춰 보정하지 않고, 현재 커널/측정 구조에서는 해당 component 증가분이 `not_identified`임을 명시한다.

핵심 이유는 NVML energy가 board 전체 전력이고, `l2_load_only`와 `dram_load_only`의 long-scoreboard stall 및 active power가 traffic 증가와 함께 변하기 때문이다. 즉 같은 byte 수라도 SM issue rate와 memory stall이 다르면 단순 `J/bit`가 component energy만 나타내지 않는다.

RTX 3090에서는 `L2/SM = 6 MiB / 82 SM ≈ 74.9 KiB/SM`이고, `blocks/SM=16`에서 shared/L1-resident 상한은 대략 `100 KiB - 16 KiB = 84 KiB/SM`이다. 따라서 `W_SM`만으로는 `L1에는 안 맞지만 L2에는 맞는` 구간이 없다. 현재 L2 후보는 L2 hit rate가 높더라도 L1 hit rate도 높아 L1-dominated로 봐야 한다.

## 입력 데이터

| 항목 | 값 |
|---|---|
| joined energy+NCU CSV | `results/raw/rtx3090_fixediter_lr_sweep_20260704_joined_ncu.csv` |
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
| detail rows | 150 | rows |
| accepted rows | 60 | rows |
| rejected rows | 90 | rows |
| accepted `global_l1_path` | 15 | rows |
| accepted `shared_l1_path` | 15 | rows |
| accepted `l2_hit_path` | 15 | rows |
| accepted `dram_streaming_path` | 15 | rows |

| rejection reason | rows |
|---|---:|
| mode_or_w_not_selected | 48 |
| elapsed_too_short | 36 |
| missing_ncu_join | 6 |

## Mode Meaning

| mode | selected W_SM | interpretation | denominator |
|---|---:|---|---|
| `global_l1_load_only` | 16 KiB | L1-hit global load path | NCU L1 bytes |
| `shared_load_only` | 64 KiB | shared-memory operand load path | expected shared bytes, NCU shared accesses for validation |
| `l2_load_only` | 64 KiB | L2-hit global load path | NCU L2 bytes |
| `dram_load_only` | 8192 KiB | DRAM streaming global load path | NCU DRAM bytes |

## Component Estimates

| kind | component | estimate | unit | rows | LR values | R2 | RMSE (J) | L1 hit (%) | L2 hit (%) | long scoreboard (%) | status | notes |
|---|---|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|
| register_scalar_control | scalar_register_pressure | 140.563 | pJ/reg-update | 10 |  |  |  |  |  |  | diagnostic_only | reg_pressure-empty; not pure register-file pJ/bit |
| tensor_register_pair | wmma_tensor_register_increment | 0.383763 | pJ/FLOP | 17 |  |  |  |  |  |  | diagnostic_only | reg_mma-reg_operand_only; effective Tensor+register, not pure Tensor Core |
| path_slope | shared_l1_path | 5.86005 | pJ/bit | 15 | 1,2,4,8,16 | 0.997939 | 7.80707 | 27.2387 | 49.5815 | 0.000738 | ok |  |
| path_slope | global_l1_path | 3.07268 | pJ/bit | 15 | 1,2,4,8,16 | 0.997503 | 9.0136 | 99.9989 | 42.928 | 17.4286 | ok |  |
| path_slope | l2_hit_path | 28.2949 | pJ/bit | 15 | 1,2,4,8,16 | 0.998916 | 6.23914 | 88.3843 | 99.6563 | 70.6588 | diagnostic_only | L2-hit candidate is L1-dominated; RTX3090 has no clean capacity-only L1-miss/L2-hit W_SM window at this blocks/SM |
| path_slope | dram_streaming_path | 32.5925 | pJ/bit | 15 | 1,2,4,8,16 | 0.998073 | 42.0795 | 49.9997 | 0.198869 | 1355.29 | ok |  |
| hierarchical_residual | l2_increment_residual | 1.37521 | pJ/bit | 15 | 1,2,4,8,16 | 0.740898 | 5.44257 | 88.3843 | 99.6563 | 70.6588 | not_identified | L2 residual is L1-dominated because L1 hit rate remains high; need L1-bypass/CG loads or a GPU/profile with a real L1-miss/L2-hit capacity window; below reference-plausible L2 transaction range |
| hierarchical_residual | dram_increment_residual | 26.4608 | pJ/bit | 15 | 1,2,4,8,16 | 0.997067 | 42.1668 | 49.9997 | 0.198869 | 1355.29 | ok |  |
| nnls_mode_intercept | global_l1_component_nnls | 3.06402 | pJ/bit | 45 |  | 0.998757 | 25.1163 |  |  |  | ok | active_set_iterations=4 |
| nnls_mode_intercept | l2_increment_nnls | 1.34227 | pJ/bit | 45 |  | 0.998757 | 25.1163 |  |  |  | reference_mismatch | active_set_iterations=4; below reference-plausible L2 transaction range |
| nnls_mode_intercept | dram_increment_nnls | 25.1351 | pJ/bit | 45 |  | 0.998757 | 25.1163 |  |  |  | ok | active_set_iterations=4 |

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

## Required Next Design If Not Identified

1. `ITER` 고정은 유지하되 LR=1의 실행 시간이 너무 짧으면 제외하거나 mode별 `ITER`를 따로 정해 denominator range와 runtime을 동시에 확보한다.
2. L2/DRAM load-only kernel은 long-scoreboard stall이 너무 커서 active power가 낮아질 수 있으므로 independent load streams와 작은 compute filler를 추가한 variant를 만든다.
3. `addr_only`는 64-bit integer address hash/control 비용이 커서 subtract baseline으로 쓰지 않는다.
4. 최종 논문 표에는 path slope와 residual component를 분리하고, `not_identified`를 0 또는 reference 보정값으로 바꾸지 않는다.
