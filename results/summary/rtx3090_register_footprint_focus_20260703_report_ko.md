# RTX 3090 Register Footprint Focus Sweep 결과

## 결론

이번 실험은 우리의 수정된 생각과 대체로 정합한다. 핵심은 `reg_pressure` 실험의 축을 사용자가 지정한 payload 크기 자체가 아니라 ptxas가 실제로 만든 `registers/thread`와 `compiler footprint B/block`로 해석해야 한다는 점이다.

특히 1024 B/block target은 ptxas 결과가 19 regs/thread, 2432 B/block로 256 B 및 512 B target보다 작았다. 따라서 `W_SM` 또는 target payload 이름만으로 register footprint를 단조 증가한다고 가정하면 안 된다.

다만 이 실험은 순수한 물리 register-file energy를 직접 분리한 것이 아니다. `reg_pressure - empty`는 Tensor Core 없는 scalar register-pressure/control coefficient이며, NVML의 device-level energy에는 scheduler, instruction issue, loop/control, residual memory write가 함께 포함된다.

## 실험 조건

| 항목 | 값 | 단위/비고 |
|---|---:|---|
| GPU profile | RTX 3090 | `rtx3090`, GA102/sm_86 |
| active SM | 82 | SM |
| blocks/SM | 8, 16 | block/SM |
| target register payload | 256, 512, 1024, 2048, 4096, 8192, 16384 | B/block |
| reuse factor | 1, 4 | 회/loop |
| measurement seconds | 3 | s/row |
| repeats | 3 | paired row당 `empty` 3회 + `reg_pressure` 3회 |
| energy source | nvml_total_energy | NVML device total energy |
| NCU | 미사용 | 이번 focused sweep는 ptxas + NVML + SMID 검증 |

## ptxas register footprint

| target payload (B/block) | payload regs/thread | ptxas regs/thread | compiler footprint (B/block) | compiler footprint (KiB/block) | max resident blocks/SM | spill-free |
|---:|---:|---:|---:|---:|---:|---|
| 256 | 2 | 21 | 2688 | 2.625 | 16 | True |
| 512 | 4 | 22 | 2816 | 2.750 | 16 | True |
| 1024 | 8 | 19 | 2432 | 2.375 | 16 | True |
| 2048 | 16 | 31 | 3968 | 3.875 | 16 | True |
| 4096 | 32 | 44 | 5632 | 5.500 | 16 | True |
| 8192 | 64 | 76 | 9728 | 9.500 | 16 | True |
| 16384 | 128 | 140 | 17920 | 17.500 | 14 | True |

해석상 중요한 점은 1024 B/block target이 실제 compiler footprint 기준으로 가장 작다는 것이다. 즉 256 B부터 시작하는 설계는 방향이 맞지만, 최종 축은 target payload가 아니라 ptxas 결과여야 한다.

## 자가점검

| 점검 항목 | 결과 | 판정 |
|---|---:|---|
| raw measurement rows | 156 | expected 156, 통과 |
| calibration rows | 26 | expected 26, 통과 |
| paired summary rows | 26 | expected 26, 통과 |
| mode balance | empty 78, reg_pressure 78 | 통과 |
| SMID histogram ok | 156/156 | 통과 |
| paired rows completeness | 26/26 | pressure 3/3, empty 3/3 |
| matrix invalid rows | 4 | 의도된 skip 포함 |

Invalid matrix row는 모두 16384 B/block target에서 blocks/SM=16을 요구한 경우다. ptxas 추정 resident limit이 14 blocks/SM이므로 실행하지 않는 것이 맞다.

| skipped target payload (B/block) | blocks/SM | reuse | mode | reason |
|---:|---:|---:|---|---|
| 16384 | 16 | 1 | empty | blocks_per_SM exceeds ptxas-estimated resident limit 14 |
| 16384 | 16 | 1 | reg_pressure | blocks_per_SM exceeds ptxas-estimated resident limit 14 |
| 16384 | 16 | 4 | empty | blocks_per_SM exceeds ptxas-estimated resident limit 14 |
| 16384 | 16 | 4 | reg_pressure | blocks_per_SM exceeds ptxas-estimated resident limit 14 |

## 결과 요약

| target payload (B/block) | ptxas regs/thread | footprint (B/block) | blocks/SM | reuse | delta_E (J) | updates | coefficient (pJ/reg-update) | rows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 256 | 21 | 2688 | 8 | 1 | 453.105 | 1.60552e+12 | 282.217 | 3/3 |
| 256 | 21 | 2688 | 8 | 4 | 657.967 | 3.42882e+12 | 191.893 | 3/3 |
| 256 | 21 | 2688 | 16 | 1 | 678.443 | 2.44833e+12 | 277.105 | 3/3 |
| 256 | 21 | 2688 | 16 | 4 | 683.899 | 3.8576e+12 | 177.286 | 3/3 |
| 512 | 22 | 2816 | 8 | 1 | 574.004 | 2.68467e+12 | 213.808 | 3/3 |
| 512 | 22 | 2816 | 8 | 4 | 700.090 | 4.12611e+12 | 169.673 | 3/3 |
| 512 | 22 | 2816 | 16 | 1 | 680.950 | 3.32809e+12 | 204.607 | 3/3 |
| 512 | 22 | 2816 | 16 | 4 | 700.840 | 4.49105e+12 | 156.053 | 3/3 |
| 1024 | 19 | 2432 | 8 | 1 | 650.624 | 3.50165e+12 | 185.805 | 3/3 |
| 1024 | 19 | 2432 | 8 | 4 | 707.023 | 4.50338e+12 | 156.998 | 3/3 |
| 1024 | 19 | 2432 | 16 | 1 | 672.393 | 3.9664e+12 | 169.522 | 3/3 |
| 1024 | 19 | 2432 | 16 | 4 | 711.500 | 4.8321e+12 | 147.245 | 3/3 |
| 2048 | 31 | 3968 | 8 | 1 | 735.132 | 4.35139e+12 | 168.942 | 3/3 |
| 2048 | 31 | 3968 | 8 | 4 | 729.178 | 4.93667e+12 | 147.706 | 3/3 |
| 2048 | 31 | 3968 | 16 | 1 | 713.143 | 4.64945e+12 | 153.382 | 3/3 |
| 2048 | 31 | 3968 | 16 | 4 | 747.320 | 5.19143e+12 | 143.953 | 3/3 |
| 4096 | 44 | 5632 | 8 | 1 | 719.635 | 4.89778e+12 | 146.931 | 3/3 |
| 4096 | 44 | 5632 | 8 | 4 | 722.820 | 5.25324e+12 | 137.595 | 3/3 |
| 4096 | 44 | 5632 | 16 | 1 | 699.833 | 4.94326e+12 | 141.573 | 3/3 |
| 4096 | 44 | 5632 | 16 | 4 | 690.891 | 5.00004e+12 | 138.177 | 3/3 |
| 8192 | 76 | 9728 | 8 | 1 | 734.357 | 5.1671e+12 | 142.122 | 3/3 |
| 8192 | 76 | 9728 | 8 | 4 | 741.269 | 5.17298e+12 | 143.296 | 3/3 |
| 8192 | 76 | 9728 | 16 | 1 | 745.581 | 5.18129e+12 | 143.899 | 3/3 |
| 8192 | 76 | 9728 | 16 | 4 | 693.696 | 5.09888e+12 | 136.049 | 3/3 |
| 16384 | 140 | 17920 | 8 | 1 | 727.780 | 5.21511e+12 | 139.552 | 3/3 |
| 16384 | 140 | 17920 | 8 | 4 | 730.222 | 5.28323e+12 | 138.215 | 3/3 |

## Payload별 coefficient 범위

| target payload (B/block) | ptxas footprint (B/block) | coefficient min | coefficient mean | coefficient max | 단위 |
|---:|---:|---:|---:|---:|---|
| 256 | 2688 | 177.286 | 232.125 | 282.217 | pJ/reg-update |
| 512 | 2816 | 156.053 | 186.035 | 213.808 | pJ/reg-update |
| 1024 | 2432 | 147.245 | 164.893 | 185.805 | pJ/reg-update |
| 2048 | 3968 | 143.953 | 153.496 | 168.942 | pJ/reg-update |
| 4096 | 5632 | 137.595 | 141.069 | 146.931 | pJ/reg-update |
| 8192 | 9728 | 136.049 | 141.341 | 143.899 | pJ/reg-update |
| 16384 | 17920 | 138.215 | 138.884 | 139.552 | pJ/reg-update |

## 우리 생각과의 정합성

| 검토 항목 | 관찰 | 판단 |
|---|---|---|
| 작은 working set 필요성 | 1024 B target의 ptxas footprint가 2432 B/block로 가장 작고 spill-free였다. | 정합. 32 KiB부터 시작하는 설계보다 256 B~1 KiB 구간을 먼저 보는 설계가 더 적절하다. |
| target payload와 실제 footprint 구분 | 256 B, 512 B, 1024 B target 순서와 ptxas footprint 순서가 다르다. | 정합. 결과 해석 축은 반드시 ptxas footprint여야 한다. |
| resident block feasibility | 16384 B target은 ptxas footprint 17920 B/block, max resident 14 blocks/SM라서 B=16이 skip되었다. | 정합. occupancy 가능 여부는 ptxas footprint로 거르는 것이 맞다. |
| reg-only 근사 | 모든 payload kernel이 spill-free이고 SMID 분포가 156/156 통과했다. | 부분 정합. compiler 관점에서는 register-resident지만, device energy에는 issue/control 비용이 포함된다. |
| coefficient 단조성 | pJ/reg-update는 작은 payload에서 크고, 4096 B 이상에서는 대략 136~147 pJ/reg-update 범위로 수렴한다. | 모순 아님. 작은 payload는 fixed/control overhead가 덜 amortize되고, reuse=4에서 coefficient가 대체로 낮아진다. |

## 한계

- 이 결과는 `reg_pressure - empty` 차분이며, Tensor Core를 포함하지 않는다.
- `register + tensor만 동작`했다는 증명은 아니다. Tensor Core register-only 근사는 `reg_operand_only`/`reg_mma` 계열과 별도 NCU 확인이 필요하다.
- NVML total energy는 GPU 전체 에너지이므로 register file, scheduler, instruction issue, clock/power-state 효과를 물리적으로 완전 분리하지 못한다.
- 이번 focused run은 NCU cache hit/access counter를 포함하지 않았다. L1/L2/DRAM 검증은 `l2_*`, `dram_*` mode에서 NCU validation으로 따로 확인해야 한다.

## 다음 확인 제안

1. `reg_operand_only`와 `reg_mma`의 ptxas footprint 3328 B/block 조건을 별도로 paired 측정해서 Tensor Core 추가분을 확인한다.
2. NCU spot-check로 `reg_pressure`, `reg_operand_only`, `reg_mma`에서 local memory spill 및 의도치 않은 L1/L2/DRAM traffic이 없는지 확인한다.
3. 논문/보고서에는 256 B~1 KiB target을 “small compiler-footprint 후보”로 표현하고, 실제 표는 ptxas footprint B/block와 regs/thread를 반드시 함께 적는다.

## 산출물

- Raw CSV: `results/raw/rtx3090_register_footprint_focus_20260703.csv`
- Calibration CSV: `results/raw/rtx3090_register_footprint_focus_20260703_calibration.csv`
- Matrix CSV: `results/raw/rtx3090_register_footprint_focus_20260703_matrix.csv`
- ptxas CSV: `results/summary/rtx3090_register_footprint_focus_20260703_ptxas.csv`
- Summary CSV: `results/summary/rtx3090_register_footprint_focus_20260703_summary.csv`
