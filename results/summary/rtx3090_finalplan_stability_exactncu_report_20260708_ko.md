# RTX 3090 Finalplan Exact-NCU Subset Report

작성일: 2026-07-08

상태: superseded. 이 문서는 LR/RF=4 대표 NCU sidecar만 사용한 중간 sanity 결과다.
현재 RTX 3090 대표 결과는 factor별 NCU sidecar를 사용한
[rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md](rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md)를 우선한다.

## 목적

이 문서는 기존 RTX 3090 stability energy run을 현재 더 엄격해진 분석 기준으로
재분석한 결과다. 기존 strict report는 LR=4 NCU sidecar의 actual/expected scale을
같은 working-set row에 확장 적용했다. 이번 보고서는 그보다 보수적으로,
NCU acceptance와 denominator가 energy row의 핵심 factor와 정확히 맞는 subset만
채택한다.

따라서 이 표는 기존 broad strict 결과를 대체하는 최종 전체 sweep 값이 아니다.
`reuse_factor=4`, `load_repeat=4` 중심의 exact-NCU subset sanity 결과다.

## 입력과 Gate

| 항목 | 값 |
|---|---|
| GPU | RTX 3090 / GA102 |
| energy raw | `results/raw/rtx3090_finalplan_stability_*_20260708_stability.csv` |
| NCU summary | `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv` |
| NCU acceptance | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv` |
| analysis output | `results/summary/rtx3090_finalplan_stability_exactncu_matched_control_summary_20260708.csv` |
| detail output | `results/summary/rtx3090_finalplan_stability_exactncu_matched_control_detail_20260708.csv` |
| method report | `results/summary/rtx3090_finalplan_stability_exactncu_matched_control_report_20260708.md` |

Power API gate는 [power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)를 따른다.

| gate | 통과 여부 | 근거 |
|---|---|---|
| total energy counter | pass | `nvml_total_energy_supported=true` |
| energy source | pass | `energy_source=nvml_total_energy` |
| integration | pass | `energy_integration_method=total_energy_mj_delta` |
| power semantics | pass | RTX 3090 profile의 `nvml_power_usage_semantics=one_sec_average` |
| fallback power integral | not used | `legacy_get_power_usage_integral` row 없음 |
| NCU denominator | memory path pass | accepted LR=4 row에서 `ncu_actual_exact` 사용 |

RTX 3090의 `GetPowerUsage`는 one-second average semantics지만, 이번 energy numerator는
endpoint power fallback이 아니라 total energy mJ counter 차분이다.

## Exact-NCU Subset 결과

| component | accepted rows | condition | median | unit | median pJ/bit | confidence |
|---|---:|---|---:|---|---:|---|
| Tensor MMA incremental | 3 | `reuse_factor=4` | 0.310835 | pJ/FLOP | - | low |
| Shared scalar path | 3 | `load_repeat=4` | 1.20141 | pJ/byte | 0.150176 | low |
| Global L1 hit path | 2 | `load_repeat=4` | 1.45661 | pJ/byte | 0.182076 | low |
| L2 CG hit path | 3 | `load_repeat=4` | 11.1166 | pJ/byte | 1.38957 | low |
| DRAM CG streaming sanity | 3 | `load_repeat=4` | 33.6545 | pJ/byte | 4.20681 | low |

## NCU Path Evidence

| path | NCU condition | hit/access evidence |
|---|---|---|
| Shared scalar | W=64 KiB, B=16, LR=4 | shared bytes `5.37401e11`, L2 leakage `2.57983e8`, DRAM leakage `1.71737e8` |
| Global L1 | W=16 KiB, B=16, LR=4 | L1 hit `99.9991%`, L2 bytes `3.14066e8`, DRAM bytes `2.19269e8` |
| L2 CG | W=64 KiB, B=16, LR=4 | L1 hit near zero, L2 hit `99.9409%`, DRAM bytes `4.83025e8` |
| DRAM CG | W=8192 KiB, B=16, LR=4 | L1 hit near zero, L2 hit `0.156441%`, DRAM bytes `5.38511e11` |
| Tensor | W=2048 KiB, B=16, RF=4 | `reg_mma` accepted, `reg_operand_only` accepted, local spill rejected if present |

## 해석

이 결과는 기존 broad strict 결과보다 denominator 검증이 강하다. 특히 memory path는
`ncu_actual_same_working_set`이 아니라 `ncu_actual_exact`로 계산되었다.

하지만 row 수가 작고 모두 `confidence=low`다. 따라서 보고서에서는 다음처럼 써야 한다.

| 쓰면 되는 표현 | 피해야 하는 표현 |
|---|---|
| “RTX 3090 LR/RF=4 exact-NCU subset에서 관찰된 effective coefficient” | “RTX 3090 전체 sweep의 최종 물리 에너지” |
| “board-level total energy와 NCU path counter를 결합한 microbenchmark coefficient” | “L1/L2/DRAM silicon bitcell energy” |
| “DRAM CG streaming sanity는 HBM/GDDR device energy가 아니라 board-level path sanity 값” | “DRAM physical pJ/bit 실측값” |

## 기존 Broad Strict 결과와의 차이

| component | broad strict median | exact-NCU subset median | 해석 |
|---|---:|---:|---|
| Tensor | 0.170 pJ/FLOP | 0.310835 pJ/FLOP | exact subset은 RF=4만 남아 전체 reuse sweep median과 다름 |
| Shared scalar | 0.151 pJ/bit | 0.150176 pJ/bit | 두 분석이 거의 일치 |
| Global L1 | 0.150 pJ/bit | 0.182076 pJ/bit | exact subset은 LR=4 valid row 2개만 반영 |
| L2 CG | 1.138 pJ/bit | 1.38957 pJ/bit | exact subset에서 더 큼, row 수 3 |
| DRAM CG | 3.542 pJ/bit | 4.20681 pJ/bit | exact subset이 문헌상 GDDR/HBM order와 더 가까운 sanity 값 |

## 결론

현 시점에서 가장 솔직한 RTX 3090 보고 방식은 두 값을 분리하는 것이다.

| 용도 | 사용할 값 |
|---|---|
| factor sweep 전체 추세 설명 | broad strict stability 결과 |
| NCU denominator exact sanity | 이 exact-NCU subset 결과 |
| 논문/백서의 final representative claim | factor-list NCU sidecar를 새로 실행한 뒤 재산출 필요 |

다음 실험은 `run_ncu_validation.sh`의 `TENSOR_REUSE_FACTORS`, `MEMORY_LOAD_REPEATS`,
`DRAM_LOAD_REPEATS`를 사용해 모든 sweep factor의 NCU sidecar를 재수집해야 한다.
