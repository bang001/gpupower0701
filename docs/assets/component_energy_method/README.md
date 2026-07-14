# Component Energy Figures

이 폴더에는 현행 문서가 직접 사용하는 그림만 둔다.

- `external_memory_scope_comparison.png/.svg`: RTX 3090/A100/V100
  user-reported effective-path observation과 HBM2/GDDR5 device/access reference를
  scope별로 분리한 현행 그림

2026-07-08 구형 coefficient, strict summary, NCU evidence, factor sweep, 설계 matrix 시각화는
`archive/pre_current_protocol_20260712/docs/assets/component_energy_method/`로
이동했다. 특히 옛 DRAM 막대는 `dram_cg_load_only - clocked_empty` 결과이므로
active coefficient나 최신 PPT에 사용하지 않는다.

`current_dram_reporting_band.png/.svg`는 2026-07-12 legacy provisional policy 그림으로
현행 보고서에 사용하지 않는다. 새 strict 결과가 나오기 전에는
`scripts/plot_external_memory_scope_review.py`가 생성한 scope 비교 그림만 사용한다.
