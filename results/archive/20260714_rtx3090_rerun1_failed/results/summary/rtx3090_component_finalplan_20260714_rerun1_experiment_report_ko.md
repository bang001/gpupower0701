# RTX 3090 Component Energy Rerun Report

## 실행 범위

| 항목 | 값 |
|---|---|
| GPU | NVIDIA GeForce RTX 3090, GA102, CC 8.6 |
| active SM | 82 SMs |
| driver | 591.86 |
| 측정 시간 | 좌표당 10 s |
| 반복 | 5회 |
| 에너지 소스 | NVML total-energy counter delta |
| 측정 범위 | GPU/device board-level effective energy |
| NCU | Nsight Compute 2026.1.1, application replay |
| 실행 태그 | `20260714_rerun1` |

이 결과는 순수 회로 에너지가 아니다. Treatment-control 차분, NVML 보드 에너지,
NCU 실제 path/traffic 검증으로 계산한 workload-dependent effective coefficient다.

## Parameter Sweep

| component | treatment - control | W_SM (KiB/SM) | blocks/SM | factor | power rows | strict 선택 좌표 |
|---|---|---:|---:|---|---:|---|
| Tensor MMA | `reg_mma - reg_operand_only` | 2048 | 8, 16 | RF=1,2,4,8,16 | 100 | W2048/B8, 전체 RF |
| Shared scalar | `shared_scalar_load_only - clocked_empty` | 32, 64 | 8, 16 | LR=4,8,16 | 120 | W64/B8, LR=4,8,16 |
| Global L1 hit | `global_l1_load_only - global_addr_only` | 8, 16 | 8, 16 | LR=4,8,16 | 90 | W8/B8, LR=4,8,16 |
| L2 CG hit | `l2_cg_load_only - global_addr_only` | 64 | 8, 16 | LR=4,8,16 | 60 | W64/B8, LR=4,8,16 |
| DRAM CG sanity | `dram_cg_load_only - global_addr_only` | 8192 | 8, 16 | LR=4,8,16 | 60 | W8192/B8, LR=4,8,16 |

Global L1의 W8/B16은 block당 1 KiB 미만이므로 실행 전에 제외됐다. Strict 결과는
exact-coordinate NCU가 있는 B8 anchor만 사용한다. B16 및 추가 W_SM power row는 이번
strict coefficient의 분모 근거가 아니라 진단용 sweep이다.

## 측정 및 NCU 결과

| component | coefficient | valid pairs | reliability | NCU path 근거 | 판단 |
|---|---:|---:|---|---|---|
| Tensor MMA increment | 1.64096 pJ/FLOP | 25/25 | accepted | treatment/control NCU 모두 통과, spill/local 0 | 현재 실행에서 채택 가능 |
| Shared scalar path | 1.01047 pJ/bit | 9/15 | accepted_with_caution | shared bytes 양수, 5/5 NCU 통과 | strict final 불가 |
| Global L1-hit path | 0.112805 pJ/bit | 4/15 | accepted_low_stability | L1 path hit 99.9990-99.9999% | strict final 불가 |
| L2 CG-hit path | 7.74946 pJ/bit | 15/15 | accepted | L1 hit 0%, L2 read hit 99.9964-99.9998% | 현재 실행에서 채택 가능 |
| DRAM CG stream sanity | 25.5169 pJ/bit | 15/15 | accepted_sanity | L1 hit 0%, L2 read hit 0-0.0041% | sanity 값으로만 채택 |

DRAM 값은 GDDR6 device 자체 에너지가 아니라 SM 요청부터 L1TEX/L2/interconnect/
memory-controller/DRAM 경로가 함께 반영된 board-level streaming coefficient다.

## Strict 실패 원인

1. Shared LR4는 중앙값 약 1.047 pJ/bit였지만 LR8은 약 0.210 pJ/bit로 감소했고,
   LR16은 5/5 pair가 음수였다. 더 긴 측정으로 해결되는 단순 white noise 형태가 아니다.
2. Global L1은 15개 pair 중 10개가 음수이고 1개가 signal-fraction gate를 통과하지
   못했다. NCU는 L1 hit path를 명확히 확인했으므로 path 실패가 아니라 에너지 차분
   control의 비가산성 문제다.
3. `clocked_empty`와 `global_addr_only`는 treatment에 동일 traffic을 더하기만 한
   회로-level baseline이 아니다. Treatment가 load/stall/issue behavior를 바꾸므로,
   control power가 treatment power보다 높아질 수 있다. 음수값을 절댓값이나 0으로
   강제하면 안 된다.
4. Power-state audit는 430행 중 423 ok, 3 caution, 4 reject였다. reject는 후속
   pairing에서 제외됐지만 Shared/L1의 체계적인 음수 분포를 설명하지는 못한다.

따라서 이번 실행으로 확정 가능한 높은 신뢰도 결과는 Tensor MMA increment와 L2 CG-hit
path다. DRAM은 sanity coefficient이며, Shared와 Global L1은 숫자가 생성됐더라도 strict
최종값으로 보고하지 않는다.

## WSL Interval Remediation

초기 power audit에서 125행이 약 60초 주기의 Windows/WSL wall-clock 보정 때문에
`measurement_interval_elapsed_mismatch`로 reject됐다. NVML energy, ITER, steady-clock
elapsed 및 power 값의 오류는 아니었다.

- 원본 430행은 `results/archive/rtx3090_component_finalplan_20260714_rerun1_wallclock_original_20260714_114619/`에 보존했다.
- 복구 manifest는 `results/summary/rtx3090_component_finalplan_20260714_rerun1_wallclock_remediation.csv`다.
- 종료 epoch metadata만 `start epoch + steady-clock elapsed`로 재산출했다.
- 복구 후 power API audit는 430/430 `final_candidate`였다.
- 수정 바이너리의 별도 70초 검증도 exact interval audit를 통과했다.

## 최종 판정

전체 power sweep과 NCU 검증은 완료됐다. 그러나 strict package는 Shared와 Global L1의
신뢰도 gate 때문에 의도적으로 실패했다. 이번 결과를 모든 component가 확정된 final
breakdown으로 표시하면 안 된다. 다음 설계는 Shared/L1에 대해 기존 control 차분을 단순
반복하기보다, traffic을 독립 변수로 둔 다점 회귀와 issue/stall-matched control을 새로
검증해야 한다.
