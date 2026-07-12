# Repository Active/Archive 점검 기록

작성일: 2026-07-08

> 2026-07-12 갱신: 이 문서의 “현재 RTX 3090 대표 수치” 표현은 당시
> active/archive 분류를 기록한 것이다. 현행 protocol은 Global L1/L2/DRAM
> `global_addr_only` control과 exact-coordinate control NCU acceptance를 추가했다.
> 따라서 아래 2026-07-08 strict 결과는 active provenance로 보존하지만 현행 strict
> final 값은 아니다. 최신 판정은 `docs/audits/current_goal_alignment_audit_ko.md`를
> 따른다.

점검 범위: `results/`, `docs/`, `include/`, `src/`

목적: 현재 finalplan coefficient 산출에 직접 필요한 파일과 과거 탐색/진단 파일을 분리한다. 현재 산출값과 무관한 과거 결과가 active 경로에 남아 있으면 RTX 3090 final coefficient의 근거를 잘못 이해할 수 있으므로 archive로 이동했다.

## 1. 결론

| 경로 | 판단 | 조치 |
|---|---|---|
| `results/` | tracked 20260701/20260702 raw sweep, smoke, fixed-W sweep, old NCU validation은 현재 coefficient 직접 입력이 아님 | `archive/legacy_20260707/results/`로 이동 |
| `docs/` | finalplan 이전 설계 문서와 과거 백서 시간순 로그는 혼동 위험이 큼 | legacy 문서는 archive 이동, active 백서는 현재 finalplan 기준으로 재작성 |
| `include/` | 현재 CUDA/NVML harness의 public header surface | 유지 |
| `src/` | 현재 mode kernel, CLI, NVML energy, result writer 구현 | 유지 |

## 2. Active 결과 파일 기준

현재 coefficient 산출의 primary source는 아래 finalplan 계열이다.

| 역할 | 파일 |
|---|---|
| 최종 strict 결과 보고서 | `results/summary/rtx3090_finalplan_stability_strict_report_20260708_ko.md` |
| strict coefficient summary | `results/summary/rtx3090_finalplan_stability_strict_matched_control_summary_20260708.csv` |
| strict factor별 coefficient detail | `results/summary/rtx3090_finalplan_stability_strict_matched_control_detail_20260708.csv` |
| 이전 finalplan 결과 보고서 | `results/summary/rtx3090_finalplan_component_energy_report_20260705_ko.md` |
| NCU acceptance/counter table | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.csv` |
| NCU 기본 threshold acceptance | `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_20260705.csv` |
| NCU cache validation summary | `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv` |

위 strict summary 파일은 현재 RTX 3090 대표 수치의 근거이므로 active `results/summary/`에 보관한다. 2026-07-05 finalplan 결과는 재측정 전 이력과 비교 기준으로 유지한다. 다만 raw energy CSV와 NCU sidecar export는 용량과 플랫폼 의존성이 커서, 새 플랫폼에서는 `scripts/plan_platform_component_experiment.py`, `scripts/run_component_regression_sweep.py`, `scripts/analyze_ncu_path_acceptance.py`, `scripts/analyze_matched_control_energy.py` 순서로 다시 생성하는 것이 기준이다.

## 3. Archive로 이동한 결과

아래 tracked 결과는 현재 final coefficient를 직접 만들지 않는다.

| 종류 | 이동 대상 |
|---|---|
| raw sweep/smoke CSV | `results/raw/*20260701*`, `results/raw/*20260702*`, dry-run sample |
| 초기 sweep summary | `results/summary/rtx3090_full_sweep_20260701_*`, `results/summary/rtx3090_sweep1_blocks_fixedw_20260702_*` |
| old NCU validation | `results/ncu/rtx3090_sweep1_fixedw_validation_20260702/` |
| old PNG plots | `results/plots/rtx3090_full_sweep_20260701/`, `results/plots/rtx3090_smoke_20260701_fixed/` |

이동 후 위치:

```text
archive/legacy_20260707/results/
```

초기 sweep 그림을 다시 생성해야 하는 경우
`archive/pre_current_protocol_20260712/scripts/plot_component_method_visuals.py`를 사용한다.
이 스크립트, `build_component_evidence_matrix.py`,
`audit_current_component_sanity.py`는 2026-07-08 historical reporting 전용이며 현행
final coefficient 산출 경로가 아니다.
`run_interleaved_component_stability.py`도 과거 `clocked_empty` 중심 auxiliary run
재현용으로 같은 archive에 이동했다. 현행 drift 재측정은 explicit control을 요구하는
`scripts/run_paired_component_stability.py`를 사용한다.

## 4. Active 문서 기준

| 목적 | 문서 |
|---|---|
| 현재 코드 동작 설명 | `docs/methodology/howitworks.md` |
| 현재 RTX 3090 결과 정리 | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| 백서용 현재 기준 종합 | `docs/reports/gpu_power_modeling_whitepaper_synthesis_ko.md` |
| 최종 실험 계획 | `docs/methodology/component_energy_final_experiment_plan_ko.md` |
| NCU 검증과 pJ 계산 | `docs/methodology/ncu_validation_energy_calculation_ko.md` |
| 방법 비교/오해 방지 | `docs/methodology/component_energy_method_comparison_ko.md` |
| 한계/자가비판 | `docs/audits/component_energy_self_critique_ko.md` |
| 문헌값 비교 | `docs/audits/literature_energy_values_audit_ko.md` |

과거 백서 원문은 아래로 이동했다.

```text
archive/legacy_20260707/docs/gpu_power_modeling_whitepaper_synthesis_history_ko.md
```

2026-07-08 당시의 상세 결과/백서 문서는 현행 address-control protocol 도입 후 아래에
추가 보존했다. Active 경로에는 현재 상태와 재실행 기준만 남긴다.

```text
archive/pre_current_protocol_20260712/docs/gpu_power_modeling_experiment_results_ko.md
archive/pre_current_protocol_20260712/docs/gpu_power_modeling_whitepaper_synthesis_ko.md
```

## 5. include/src 점검

`include/`와 `src/`는 legacy archive 대상이 아니다. 이유는 다음과 같다.

| 파일 | 역할 | 판단 |
|---|---|---|
| `include/config.hpp` | mode/config/profile 선언 | active |
| `include/kernels.cuh` | kernel launch interface | active |
| `include/nvml_compat.hpp` | NVML compatibility shim | active |
| `include/nvml_energy.hpp` | energy measurement interface | active |
| `include/result_writer.hpp` | CSV output interface | active |
| `src/kernels.cu` | `reg_mma`, `shared_scalar_load_only`, `global_l1_load_only`, `l2_cg_load_only`, `dram_cg_load_only` 등 kernel 구현 | active |
| `src/main.cu` | CLI, mode parsing, expected denominator metadata | active |
| `src/nvml_energy.cpp` | NVML energy/power sampling | active |
| `src/result_writer.cpp` | result CSV writer | active |

## 6. 남긴 이유가 있는 legacy sweep

초기 Sweep 1/2 표와 SVG는 `docs/results/gpu_power_modeling_experiment_results_ko.md`에 남겨둔다. 이유는 다음과 같다.

| 남긴 항목 | 이유 | 오해 방지 문구 |
|---|---|---|
| Sweep 1 blocks/SM trend | occupancy 후보를 어떻게 골랐는지 설명 | final coefficient 입력 아님 |
| Sweep 2 W_SM trend | working-set 후보 영역을 어떻게 찾았는지 설명 | final coefficient 입력 아님 |

즉 active 문서에 남은 sweep은 “결과 산출 근거”가 아니라 “실험 설계 히스토리와 후보 선택 근거”다.
