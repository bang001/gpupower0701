# Component Energy Figures

이 폴더에는 현행 문서가 직접 사용하는 그림만 둔다.

- `current_dram_reporting_band.png/.svg`: RTX 3090 `26.709-28.409 pJ/bit`
  provisional cumulative effective-path band

2026-07-08 구형 coefficient, strict summary, NCU evidence, factor sweep, 설계 matrix 시각화는
`archive/pre_current_protocol_20260712/docs/assets/component_energy_method/`로
이동했다. 특히 옛 DRAM 막대는 `dram_cg_load_only - clocked_empty` 결과이므로
active coefficient나 최신 PPT에 사용하지 않는다.

새 DRAM accepted 결과가 나오기 전까지는
`scripts/plot_dram_reporting_policy.py`가 생성한 current figure만 보고서에 사용한다.
