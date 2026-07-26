# CTA=48, S=1024 Softmax EX2 Matplotlib figures

이 폴더는 2026-07-25 RTX 3090 targeted confirmation의 **fresh-session 편차를
직접 보이기 위한 정적 Matplotlib companion**이다. Canonical portable HTML report나
artifact를 수정하지 않으며, 그와 같은 summary CSV에서 다시 생성된다.

재생성 명령:

```bash
python3 scripts/plot_softmax_ex2_targeted_confirmation.py --tag 20260725
python3 scripts/plot_softmax_ex2_targeted_confirmation.py --self-test
```

입력은 `implementation_summary`, `session_cells`, `within_session_contrasts`,
`contrast_summary`, `matched_blocks` CSV다. `--self-test`는 3개 구현, 9/9 quality-pass
session cell, 3개 same-session contrast, 27개 nested matched block, aggregate 산술과
cyclic position 균형을 확인한다. 일반 실행은 PNG와 SVG를 함께 쓰고 Pillow로 PNG
decode 및 최소 해상도도 확인한다.

| 그림 | 질문 | 해석 경계 |
|---|---|---|
| `..._session_spread.png/.svg` | 평균 뒤의 3개 fresh-session 값은 얼마나 흔들리는가? | 점은 primary unit인 session mean, diamond는 평균, 선은 descriptive df=2 t95다. |
| `..._path_contrasts.png/.svg` | 같은 session 안에서 세 implementation-path contrast는 어떻게 달라지는가? | `packed - scalar`가 0을 가로지르는지를 확대해 표시한다. 순수 opcode/MUFU 에너지 비교는 아니다. |
| `..._position_balance.png/.svg` | implementation 순환 배정이 실제로 위치를 균형화했는가? | session·implementation 평균을 뺀 diagnostic일 뿐, n=3에서 순서·온도의 인과효과를 추정하지 않는다. |
| `..._matched_block_diagnostics.png/.svg` | cell 내부 matched block의 산포는 어느 정도인가? | 27 block은 9개의 session cell 안에 nested되어 있으므로 독립 n=27로 pool하지 않는다. |

모든 y축의 주 단위는 `incremental pJ / input element`다. 이 설계에서 logical EX2
result가 element당 하나 추가되므로 `pJ/logical scalar exponent result`와 수치상
같지만, 전체 Softmax `pJ/element`나 순수 MUFU 회로 에너지는 아니다.
