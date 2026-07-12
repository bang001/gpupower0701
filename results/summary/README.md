# Results Summary Selection

`results/summary/`에는 서로 다른 날짜와 protocol의 산출물이 함께 있다. 파일명이
`current`, `strict`, `accepted`를 포함하더라도 최신 active protocol을 자동으로
의미하지 않는다.

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
