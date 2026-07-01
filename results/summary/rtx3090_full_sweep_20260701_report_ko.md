# RTX 3090 FP16 Tensor Core Energy Sweep 정리

## 실험 범위

- GPU: NVIDIA GeForce RTX 3090, compute capability 8.6, 82 active SM.
- Sweep 1 요청 조건: `blocks/SM = 1, 2, 4, 8, 16, 32`.
- 실제 실행 조건: `blocks/SM = 1, 2, 4, 8, 16`.
- `blocks/SM = 32`는 RTX 3090 / CC 8.6의 resident block 한계가 16이므로 실행하지 않고 matrix에 invalid로 기록했다.
- Sweep 2 조건: `W_SM = 1 KiB`부터 `128 MiB`까지 2배씩 증가.
- 실행 설정: `seconds=1`, `repeats=1`, `active_SM=82`, `gpu=0`.

## 실행 커버리지

| 항목 | 값 |
|---|---:|
| matrix 전체 행 | 649 |
| 실제 실행 행 | 346 |
| skip/invalid 행 | 303 |
| raw CSV 행 | 346 |
| non-idle 행 | 345 |
| SMID 검증 실패 | 0 |
| 에너지 소스 | NVML total-energy counter |

Mode별 실행 행 수:

| mode | rows |
|---|---:|
| idle | 1 |
| empty | 80 |
| reg_mma | 80 |
| shared_mma | 25 |
| l2_mma | 25 |
| dram_mma | 55 |
| store_path | 80 |

## Mode별 중앙값 요약

| mode | pJ/FLOP median | pJ/FLOP min | pJ/FLOP max | net_E_J median |
|---|---:|---:|---:|---:|
| reg_mma | 0.885 | 0.464 | 2.017 | 56.290 |
| shared_mma | 5.087 | 0.435 | 10.266 | 66.480 |
| l2_mma | 5.824 | 2.178 | 8.870 | 76.839 |
| dram_mma | 35.626 | 12.732 | 60.145 | 166.917 |

해석상 `reg_mma`, `empty`, `store_path`는 sweep grid 좌표를 맞추기 위해 `W_SM`을 기록하지만, 해당 커널 경로는 `W_SM` working set을 직접 사용하지 않는다. `W_SM` 의존성 해석은 `shared_mma`, `l2_mma`, `dram_mma` 중심으로 보는 것이 맞다.

## Sweep 1: blocks/SM 중앙값

| mode | B=1 | B=2 | B=4 | B=8 | B=16 |
|---|---:|---:|---:|---:|---:|
| reg_mma | 1.381 | 0.969 | 0.795 | 0.840 | 0.788 |
| shared_mma | 6.535 | 5.841 | 4.952 | 4.237 | 3.719 |
| l2_mma | 7.303 | 7.720 | 5.674 | 5.507 | 4.581 |
| dram_mma | 51.855 | 43.009 | 35.626 | 30.593 | 29.799 |

단일 반복 기준에서는 `blocks/SM`이 커질수록 `shared_mma`, `l2_mma`, `dram_mma`의 pJ/FLOP 중앙값이 낮아지는 경향이 나타난다. RTX 3090에서는 `B=16`이 실행 가능한 최대 resident block 조건이다.

## Sweep 2: W_SM 중앙값

`shared_mma`는 shared-resident 조건 때문에 `1 KiB`부터 `64 KiB`까지만 실행됐다. `l2_mma`도 nominal 6 MiB L2 기준으로 full-GPU working set이 들어가는 `1 KiB`부터 `64 KiB`까지 실행됐다. `dram_mma`는 `128 KiB`부터 `128 MiB`까지 실행됐다.

| mode | W range | pJ/FLOP median range |
|---|---|---:|
| shared_mma | 1 KiB - 64 KiB | 4.544 - 10.266 |
| l2_mma | 1 KiB - 64 KiB | 5.344 - 8.461 |
| dram_mma | 128 KiB - 128 MiB | 23.081 - 38.891 |

`dram_mma`는 `W_SM=128 KiB`에서 중앙값이 가장 낮았고, 더 큰 working set에서는 대체로 30-40 pJ/FLOP 범위에 머물렀다.

## 산출물

- Raw result CSV: `results/raw/rtx3090_full_sweep_20260701.csv`
- Full matrix CSV: `results/raw/rtx3090_full_sweep_20260701_matrix.csv`
- Clean result CSV: `results/summary/rtx3090_full_sweep_20260701_clean_results.csv`
- Mode summary CSV: `results/summary/rtx3090_full_sweep_20260701_mode_summary.csv`
- Best rows CSV: `results/summary/rtx3090_full_sweep_20260701_best_pj_flop.csv`
- Blocks summary CSV: `results/summary/rtx3090_full_sweep_20260701_by_blocks_summary.csv`
- W summary CSV: `results/summary/rtx3090_full_sweep_20260701_by_w_summary.csv`
- Plots: `results/plots/rtx3090_full_sweep_20260701/`

## 주의

이번 sweep는 전체 조합 확인과 추세 파악을 위한 `seconds=1`, `repeats=1` 실행이다. 논문/보고서의 최종 수치로 쓰려면 주요 후보 조합에 대해 `seconds=10`, `repeats>=5`로 반복 측정하는 후속 run이 필요하다.
