# Component Energy Figures

이 폴더에는 현행 문서가 직접 사용하는 그림만 둔다.

- `rtx3090_current_component_coefficients_20260714.png/.svg`: 20260714 GA102 v5
  matched-control coefficient와 bootstrap median CI. Tensor와 memory 단위를 분리하고
  external-memory effective path를 빈 마름모로 표시
- `rtx3090_current_ncu_path_evidence_20260714.png/.svg`: accepted treatment row의
  Shared/L1/L2/DRAM bytes, access count, long-scoreboard median을 path별로 비교

파일명의 `current`는 생성 당시 명칭이다. A100 v5 portability 실패 후
현행 신규 실행 protocol은 v6이며, 이 그림은 v6 계수 그림이 아니다.
- `external_memory_scope_comparison.png/.svg`: RTX 3090/A100/V100
  user-reported effective-path observation과 HBM2/GDDR5 device/access reference를
  scope별로 분리한 역사적 비교 그림. 현행 RTX 3090 coefficient 그림은 아님

2026-07-08 구형 coefficient, strict summary, NCU evidence, factor sweep, 설계 matrix 시각화는
`archive/pre_current_protocol_20260712/docs/assets/component_energy_method/`로
이동했다. 특히 옛 DRAM 막대는 `dram_cg_load_only - clocked_empty` 결과이므로
active coefficient나 최신 PPT에 사용하지 않는다.

`current_dram_reporting_band.png/.svg`는 2026-07-12 legacy provisional policy 그림으로
현행 보고서에 사용하지 않는다. 2026-07-14 RTX 3090 결과 그림은
`scripts/plot_current_rtx3090_results.py`로만 다시 생성한다.
