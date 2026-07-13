# Results Directory

갱신일: 2026-07-14

`results/`는 current 결과만 모은 폴더가 아니라 원시 측정 provenance와 여러 protocol
세대의 생성 산출물을 보존하는 영역이다. 파일명의 `current`, `strict`, `accepted`만으로
현행 결과라고 판단하지 않는다.

| 경로 | 내용 | 정책 |
|---|---|---|
| `raw/` | NVML energy run CSV와 calibration/matrix | 원본 보존; 값을 일괄 수정하거나 덮어쓰지 않음 |
| `ncu/` | NCU raw export, report, cache summary | 원본 보존; target profile/tag/좌표가 맞는지 acceptance로 판정 |
| `summary/` | 분석, audit, command plan, 보고서 | [summary selection](summary/README.md)에서 current/historical 지위 확인 |
| `plots/` | 원시 sweep 시각화 | 해당 source CSV와 protocol을 함께 표기 |

현행 component table은 동일 profile/tag의 power API, power-state, NCU treatment/control
acceptance, matched-control, reliability, strict summary, strict-summary audit와 package
audit가 모두 통과해야 한다. 현재 결과 상태의 기준 문서는
[`docs/results/gpu_power_modeling_experiment_results_ko.md`](../docs/results/gpu_power_modeling_experiment_results_ko.md)다.
