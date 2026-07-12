# Component Energy Figures

현행 DRAM 보고 그림은 다음 파일이다.

- `current_dram_reporting_band.png/.svg`: RTX 3090 `26.709-28.409 pJ/bit`
  provisional cumulative effective-path band

`final_component_coefficients.*`, `finalplan_factor_sweep_coefficients.*` 등 2026-07-08
결과에서 생성된 그림은 historical visualization이다. 특히 옛 DRAM 막대는
`dram_cg_load_only - clocked_empty` 결과이므로 active coefficient나 최신 PPT에
사용하지 않는다.

새 DRAM accepted 결과가 나오기 전까지는
`scripts/plot_dram_reporting_policy.py`가 생성한 current figure만 보고서에 사용한다.
