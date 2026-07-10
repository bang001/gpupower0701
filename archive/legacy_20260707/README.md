# Legacy Archive 2026-07-07

이 디렉토리는 finalplan 이전에 사용했던 탐색 문서와 진단 코드를 보관한다. 파일을 삭제하지 않은 이유는 실험 설계의 히스토리와 실패 원인을 추적할 수 있게 하기 위해서다.

## 왜 이동했나

현재 component energy 결론은 acceptance-first finalplan을 기준으로 한다. 과거 문서와 스크립트가 active `docs/`, `scripts/`에 같이 있으면 다음과 같은 문제가 생긴다.

- raw `*_mma` sweep 결과를 final component coefficient로 오해할 수 있다.
- `run_component_pairs.py` 기반 pair difference를 현재 primary 분석으로 착각할 수 있다.
- static expected bytes 기반 pJ/bit를 NCU actual traffic 기반 결과와 혼동할 수 있다.
- register-pressure 진단값을 pure register-file energy로 잘못 해석할 수 있다.

## 보관된 문서

| 파일 | 성격 |
|---|---|
| `docs/component_energy_decomposition_experiment_design_ko.md` | 초기 component decomposition 설계 |
| `docs/component_energy_redo_experiment_design_ko.md` | redo 설계 초안 |
| `docs/component_energy_regression_redesign_ko.md` | NNLS/regression 기반 재설계 |
| `docs/component_energy_separation_execution_plan_ko.md` | separation 실행 계획 초안 |
| `docs/register_footprint_experiment_design_ko.md` | register footprint/register-pressure 진단 설계 |
| `docs/gpu_power_modeling_whitepaper_synthesis_history_ko.md` | 과거 실험 시간순 흐름을 포함한 백서 초안 원문 |
| `docs/multi_gpu_support_plan_ko.md` | 구현 전 multi-GPU 지원 계획. 현재 내용은 `docs/platforms/README.md`와 플랫폼별 가이드에 병합됨 |

## 보관된 코드

| 파일 | 성격 |
|---|---|
| `scripts/run_component_pairs.py` | legacy pair-centric runner |
| `scripts/analyze_component_pairs.py` | legacy pair-difference analyzer |
| `scripts/fit_component_energy_model.py` | legacy NNLS/regression analyzer |
| `scripts/estimate_component_energy.py` | legacy component estimate generator |
| `scripts/analyze_logical_component_energy.py` | legacy logical component analyzer |
| `scripts/analyze_reference_aligned_memory.py` | legacy reference-aligned memory analyzer |
| `scripts/join_ncu_summary.py` | legacy NCU/energy join helper |
| `scripts/run_register_footprint_sweep.py` | legacy register footprint runner |
| `scripts/analyze_register_footprint.py` | legacy register footprint analyzer |
| `scripts/inspect_register_footprint.py` | legacy ptxas register footprint helper |

## 보관된 결과

| 경로 | 성격 |
|---|---|
| `results/raw/` | 20260701/20260702 raw sweep, smoke, dry-run sample |
| `results/summary/` | 초기 full sweep, fixed-W sweep, old NCU validation summary |
| `results/plots/` | 초기 sweep/smoke PNG plots |
| `results/ncu/` | 초기 sweep1 NCU validation case |

이 결과들은 현재 finalplan coefficient의 직접 입력이 아니다. 후보 영역 탐색, 실패 원인 추적, 과거 보고서 검증 용도로만 사용한다.

## 사용 규칙

새 실험과 보고서에는 active 문서를 우선 사용한다.

```text
docs/methodology/howitworks.md
docs/results/gpu_power_modeling_experiment_results_ko.md
docs/methodology/component_energy_final_experiment_plan_ko.md
docs/platforms/cross_platform_component_experiment_guide_ko.md
docs/methodology/ncu_validation_energy_calculation_ko.md
docs/platforms/README.md
```

archive 코드를 다시 사용할 때는 보고서에 `legacy diagnostic`이라고 명시하고, final coefficient와 섞지 않는다.

보관된 Python 스크립트는 원래 `scripts/` 루트에 있던 파일을 그대로 옮긴 것이다. 따라서 직접 실행하면 상대 import 또는 hard-coded `scripts/...` 경로가 맞지 않을 수 있다. 재실행이 꼭 필요하면 active checkout에서 별도 branch를 만들고 경로를 조정한 뒤 legacy diagnostic으로만 사용한다.
