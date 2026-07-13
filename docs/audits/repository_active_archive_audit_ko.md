# Repository Active/Archive 점검 기록

갱신일: 2026-07-14

점검 범위: `README.md`, `SKILL.md`, `docs/`, `scripts/`, `include/`, `src/`,
`results/`, `archive/`

## 결론

활성 문서는 현행 acceptance-first finalplan을 설명하는 파일만 `docs/`에 남긴다.
초기 설계, pre-current-protocol coefficient 시각화, 잘못된 GPU에서 생성된 preflight는
날짜와 이유를 명시한 `archive/`로 이동한다. 원시 측정 CSV와 NCU artifact는 재현성과
provenance 때문에 삭제하지 않는다.

| 영역 | 현재 판단 | 조치 |
|---|---|---|
| `include/`, `src/` | 네 profile과 primary/diagnostic mode를 구현하는 active harness | 전체 유지, profile audit 대상 |
| `scripts/` | finalplan 생성/실행/NCU/분석/audit 도구는 active | archived script를 SKILL/README 실행 경로에서 제거 |
| `docs/` | 현재 방법·플랫폼·결과 상태·감사 문서만 active | 초기 v2 설계와 구형 상세 결과 문서 archive |
| `results/raw`, `results/ncu` | 측정 provenance | 삭제/재작성 금지, current 여부는 manifest와 audit로 판정 |
| `results/summary` | current와 historical 산출물이 공존 | 문서에서 status를 명시하고 current package 이름으로 판정 |
| `docs/assets` | 활성 문서/생성기가 사용하는 그림만 유지 | unreferenced pre-current 그림 archive |

## Active 문서 기준

| 목적 | 기준 문서 |
|---|---|
| 전체 동작과 mode | `docs/methodology/howitworks.md` |
| 최종 sweep/좌표/gate | `docs/methodology/component_energy_final_experiment_plan_ko.md` |
| 초기 방식과 현행 방식 비교 | `docs/methodology/component_energy_method_comparison_ko.md` |
| NCU와 pJ 계산 | `docs/methodology/ncu_validation_energy_calculation_ko.md` |
| 현재 결과 상태 | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| 공통 플랫폼 실행 | `docs/platforms/cross_platform_component_experiment_guide_ko.md` |
| GPU별 실행 | `docs/platforms/{a100,v100,h100}_node_experiment_guide_ko.md` |
| Power API 의미 | `docs/platforms/power_measurement_api_matrix_ko.md` |
| 현재 한계 | `docs/audits/component_energy_self_critique_ko.md` |
| 코드/문서 목표 정합성 | `docs/audits/current_goal_alignment_audit_ko.md` |

`SKILL.md`와 `docs/README.md`는 위 경로만 canonical로 안내해야 한다. archive 문서를
실행 기준으로 참조하면 documentation consistency audit가 실패한다.

## 2026-07-14 이동 내역

| 이동 대상 | 새 위치 | 이유 |
|---|---|---|
| 초기 A100 FP16 v2 상세설계와 feasibility 자산 | `archive/superseded_v2_design_20260714/` | logical operation의 출발점이지만 현재 primary mode/control/NCU/package 정책과 다름 |
| 2026-07-08 coefficient/factor/sweep 시각화와 전체 방법 이력 | `archive/pre_current_protocol_20260712/docs/` | old `clocked_empty` global-memory control과 superseded Tensor 결과가 섞임 |
| 로컬 RTX 3090에서 생성된 A100/V100 strict preflight 실패 | `archive/failed_preflight_20260713/` | target-platform evidence가 아니며 profile/toolchain gate 실패 기록임 |

이동은 삭제가 아니다. archive README에는 실패/보관 이유와 current evidence로 사용할 수
없는 범위를 기록한다.

## 이전 Archive

| 경로 | 내용 | 현재 사용 |
|---|---|---|
| `archive/legacy_20260707/` | 초기 decomposition/regression/register-footprint 설계와 7월 1-2일 sweep | 역사적 탐색만 |
| `archive/pre_current_protocol_20260712/` | address-control/exact-NCU 이전 결과·백서·시각화 | 과거 해석 재현만 |
| `archive/superseded_a100_l2_policy_20260713/` | A100 L2 residency selector 이전 정책 | superseded diagnostic |
| `archive/superseded_v2_design_20260714/` | 원래 A100 v2 상세설계와 자산 | logical-op 설계 이력만 |
| `archive/failed_preflight_20260713/` | wrong-platform strict preflight 실패 | 실패 gate 동작 증거만 |

## Results 보존 정책

`results/`에는 많은 historical artifact가 남아 있다. 다음 이유로 이번 정리에서 raw/NCU
파일을 대량 이동하지 않았다.

1. 원시 측정과 profiler export는 수정 불가능한 provenance다.
2. 현재 결과 상태 문서가 일부 historical NCU path evidence를 링크한다.
3. 파일 이름만으로 current 여부를 판단하지 않고 result manifest, strict/package audit,
   binary revision과 treatment-control policy로 판단해야 한다.

최종 보고서에서 current로 사용할 수 있는 것은 현재 command package와 같은 tag/profile의
power API, power-state, NCU acceptance, matched detail/summary, reliability, strict summary,
strict audit, package audit가 모두 통과한 묶음뿐이다. 그 외 결과는 historical 또는
provisional이다.

## Include/Src 전수 판정

| 파일 | 역할 | 판정 |
|---|---|---|
| `include/config.hpp` | profile, mode, feasibility 정의 | active source of truth |
| `include/kernels.cuh` | kernel launch interface | active |
| `include/nvml_compat.hpp` | NVML compatibility declaration | active |
| `include/nvml_energy.hpp` | energy/power measurement interface | active |
| `include/result_writer.hpp` | CSV schema interface | active |
| `src/kernels.cu` | treatment/control/diagnostic kernel 구현 | active |
| `src/main.cu` | CLI, runtime profile, denominator metadata, measurement flow | active |
| `src/nvml_energy.cpp` | total-energy와 fallback power 처리 | active |
| `src/result_writer.cpp` | explicit measurement scope 포함 CSV writer | active |

코드의 diagnostic/legacy mode는 삭제하지 않는다. 과거 결과 재현과 경로 비교에 필요하며,
`README.md`가 primary와 diagnostic을 구분한다. 다만 finalplan과 strict summary는 primary
pair만 사용한다.

## 자동 검증

```bash
python3 scripts/audit_documentation_consistency.py --fail-on-error
```

검사는 다음을 hard gate로 본다.

- active/archive Markdown local link가 모두 존재한다.
- 구형 root-level docs 경로가 활성 문서에 남지 않는다.
- L2 final energy가 동일 ITER/direct net-energy 정책으로 설명된다.
- C++/sweep/preflight/planner의 SM, shared, L2, blocks/SM, power semantics가 일치한다.
- 활성 component asset이 현행 문서/생성기에서 참조되거나 source/render pair다.
