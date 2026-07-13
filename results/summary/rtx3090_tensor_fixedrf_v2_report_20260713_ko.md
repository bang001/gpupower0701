# RTX 3090 Tensor Fixed-RF v2 검증 보고서

- 실행일: 2026-07-13
- GPU: NVIDIA GeForce RTX 3090, GA102, 82 SM
- 커널 revision: `tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2`

## 결론

dynamic reuse loop를 사용한 v1은 RF2에서 `HMMA/logical MMA=3`이고 다른
primary RF는 2로 나와 logical FLOP과 issued HMMA의 비례가 깨졌다. v2는 RF1은
기존 dynamic path, RF2/4/8/16은 compile-time fixed-trip `unroll 1` treatment/control로
실행한다. 새 NCU run에서 모든 RF의 treatment `HMMA/logical MMA=2`, control
HMMA=0, local read/write=0을 확인했다.

현재 프로토콜로 채택한 RTX 3090 Tensor MMA incremental coefficient는 **median
2.2525 pJ/FLOP**, 범위 **1.9454-2.3692 pJ/FLOP**이다. 이값은 pure Tensor
Core 회로 에너지가 아니라, 동일 logical work에서 `reg_operand_only`보다 `reg_mma`가
추가로 소모한 board-level effective energy를 logical FLOP으로 나눈 값이다.

## 실험 조건

| 항목 | 값 | 단위/의미 |
|---|---:|---|
| blocks/SM | 16 | block/SM |
| active SM | 82 | SM |
| W_SM | 2,048 | KiB; register-only mode의 실제 RF capacity를 뜻하지 않는 planner coordinate |
| RF sweep | 1, 2, 4, 8, 16 | reuse factor |
| target treatment duration | 20 | s |
| control calibration floor | 2 | s |
| repeats | 7 | repeat/RF |
| raw rows | 70/70 | power API final candidate |
| energy source | `nvml_total_energy` | GPU device total-energy counter |
| measurement scope | `gpu_device_total_energy_counter` | board/device-level |
| NCU replay/cache | `application` / `none` | pass마다 application warm-up 재실행 |

## RF별 결과

| RF | valid pair / total | coefficient median | min-max | treatment elapsed median | control elapsed median | treatment net power median | control net power median | treatment throughput median |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7 / 7 | 1.9754 pJ/FLOP | 1.9454-2.0227 pJ/FLOP | 19.459 s | 7.223 s | 204.579 W | 215.645 W | 62.877 TFLOP/s |
| 2 | 7 / 7 | 2.3211 pJ/FLOP | 2.2954-2.3692 pJ/FLOP | 20.577 s | 2.983 s | 198.933 W | 217.981 W | 71.856 TFLOP/s |
| 4 | 6 / 7 | 2.2733 pJ/FLOP | 2.2387-2.2925 pJ/FLOP | 20.596 s | 3.015 s | 199.896 W | 220.877 W | 74.170 TFLOP/s |
| 8 | 7 / 7 | 2.2525 pJ/FLOP | 2.2143-2.2786 pJ/FLOP | 20.548 s | 2.772 s | 198.353 W | 219.031 W | 74.979 TFLOP/s |
| 16 | 6 / 7 | 2.2458 pJ/FLOP | 2.2407-2.2810 pJ/FLOP | 19.990 s | 2.462 s | 194.869 W | 214.195 W | 75.092 TFLOP/s |

RF 내부 min-max 폭은 각 median의 1.8-3.9%이다. RF1-16 median 전체 폭은 약
15.3%로 remediation gate 75%보다 작다. RF4와 RF16은 각각 control power outlier 1개가
power-state audit에서 reject되었다. analyzer가 수분 떨어진 다른 repeat control로
대체하지 못하도록 60,000 ms pair timestamp gate를 적용해 해당 treatment 2개도
요약에서 제외했다. 최종 summary는 33개 valid pair를 사용한다.

## NCU acceptance

| RF | treatment HMMA | expected logical MMA | HMMA/logical MMA | control HMMA | local read/write | acceptance |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 262,400,000 | 131,200,000 | 2.0 | 0 | 0 B / 0 B | accepted |
| 2 | 524,800,000 | 262,400,000 | 2.0 | 0 | 0 B / 0 B | accepted |
| 4 | 1,049,600,000 | 524,800,000 | 2.0 | 0 | 0 B / 0 B | accepted |
| 8 | 2,099,200,000 | 1,049,600,000 | 2.0 | 0 | 0 B / 0 B | accepted |
| 16 | 4,198,400,000 | 2,099,200,000 | 2.0 | 0 | 0 B / 0 B | accepted |

NCU 10/10 row가 accepted되었다. Tensor pJ/FLOP의 denominator는 logical FLOP이며 NCU
HMMA 숫자 자체를 denominator로 사용하지 않는다. NCU는 treatment의 Tensor path,
control의 no-HMMA, RF별 instruction 선형성과 spill 0을 검증한다.

## L2 cross-validation smoke

새 L2 counter 교차검증은 RTX 3090 W16/B16/LR4 persisting policy에서 다음을
확인했다.

| 항목 | 값 |
|---|---:|
| L1 path hit | 0% |
| derived L2 read hit | 99.9977% |
| native L2 op-read hit | 99.9542% |
| native-derived 차이 | 0.0435 percentage point |
| `(hit+miss)/read sectors` | 1.0 |
| persisting L2 window | 4,325,380 B |
| acceptance | treatment/control 2/2 accepted |

이 결과는 CUDA persisting API, application replay, manifest, summarizer와 acceptance gate의
연결을 검증한 smoke이다. RTX 3090 결과로 A100의 기존 L2 hit 58.5-60.1%가
해결됐다고 결론 내리면 안 된다. A100은 새 binary와 normal/persisting precheck를
대상 노드에서 다시 실행해야 한다.

## 해석 한계

1. `reg_mma - reg_operand_only`는 pure Tensor transistor energy가 아니다.
2. 동일 ITER에서 treatment가 control보다 오래 실행되므로 active scheduler, clock,
   register-fragment lifetime 차이가 `delta_E_J`에 포함된다.
3. 이 보고서는 RTX 3090 Tensor path만 현재 protocol로 갱신한다. Shared, Global L1,
   L2 energy와 DRAM을 포함한 완전한 current-protocol component table은 아직 없다.
4. 기존 RTX 3090 `0.129-0.146 pJ/FLOP` 자료는 v2와 control/kernel/protocol이
   다른 historical result이므로 직접 평균하거나 v2 final로 인용하지 않는다.

## 근거 파일

- raw energy: [`../raw/rtx3090_tensor_fixedrf_v2_20260713.csv`](../raw/rtx3090_tensor_fixedrf_v2_20260713.csv)
- calibration: [`../raw/rtx3090_tensor_fixedrf_v2_20260713_calibration.csv`](../raw/rtx3090_tensor_fixedrf_v2_20260713_calibration.csv)
- matrix: [`../raw/rtx3090_tensor_fixedrf_v2_20260713_matrix.csv`](../raw/rtx3090_tensor_fixedrf_v2_20260713_matrix.csv)
- Tensor NCU summary: [`../ncu/rtx3090_tensor_fixedrf_v2_20260713/ncu_cache_validation_summary.csv`](../ncu/rtx3090_tensor_fixedrf_v2_20260713/ncu_cache_validation_summary.csv)
- Tensor NCU acceptance: [`rtx3090_tensor_fixedrf_v2_20260713_ncu_acceptance.csv`](rtx3090_tensor_fixedrf_v2_20260713_ncu_acceptance.csv)
- matched-control detail: [`rtx3090_tensor_fixedrf_v2_20260713_matched_control_detail.csv`](rtx3090_tensor_fixedrf_v2_20260713_matched_control_detail.csv)
- matched-control summary: [`rtx3090_tensor_fixedrf_v2_20260713_matched_control_summary.csv`](rtx3090_tensor_fixedrf_v2_20260713_matched_control_summary.csv)
- L2 smoke NCU summary: [`../ncu/rtx3090_l2_persisting_crosscheck_20260713/ncu_cache_validation_summary.csv`](../ncu/rtx3090_l2_persisting_crosscheck_20260713/ncu_cache_validation_summary.csv)
