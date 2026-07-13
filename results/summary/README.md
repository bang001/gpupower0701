# Results Summary Selection

갱신일: 2026-07-14

`results/summary/`에는 서로 다른 날짜와 protocol의 산출물이 함께 있다. 파일명이
`current`, `strict`, `accepted`를 포함하더라도 최신 active protocol을 자동으로
의미하지 않는다.

| 결과 묶음 | 현재 지위 | 우선 확인 파일 |
|---|---|---|
| RTX 3090 fixed-RF v2 Tensor | current standalone evidence | `rtx3090_tensor_fixedrf_v2_report_20260713_ko.md` |
| RTX 3090 2026-07-08 strict/fresh-NCU | historical protocol evidence | `rtx3090_current_protocol_reaudit_20260714.md` |
| RTX 3090 Shared/Global-L1/L2 full table | current package 미완료 | `../../docs/results/gpu_power_modeling_experiment_results_ko.md` |
| A100/V100/H100 `*_commands.sh` | 실행 계획, 측정 결과 아님 | 각 `*_command_plan.md`와 `../../docs/platforms/` 가이드 |
| Documentation consistency | current static audit | `documentation_consistency_audit_20260714.md` |

RTX 3090 DRAM을 보고할 때의 우선순위는 다음과 같다.

1. `rtx3090_dram_current_reporting_policy_20260712.csv/.md`
2. 새 matched-ITER `dram_cg_load_only - global_addr_only` strict package가 생성되면 그 결과
3. 과거 `dram_cg_load_only - clocked_empty` summary는 provenance/reproduction only

현재 DRAM 보고값은 `26.709-28.409 pJ/bit`의
`provisional_reference_aligned_range`다. 이 값은 accepted 실측 coefficient가 아니다.
과거 summary의 약 28.3 pJ/byte 및 약 3.54 pJ/bit는 산술적으로 서로 환산되지만,
현행 address-control matched-ITER 정책과 다르므로 active 보고에 사용하지 않는다.

원시 CSV, matched-control detail, audit artifact는 실험 provenance이므로 숫자를
일괄 치환하지 않는다. 새 실험을 완료하면 새 tag의 artifact를 만들고 reporting policy를
accepted median/CI로 교체한다.
