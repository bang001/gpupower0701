# RTX 3090 whole-Softmax targeted confirmation figures

이 디렉터리는 stage-isolation 탐색 결과를 다시 합산하지 않고, 선택된 두 contrast만
fresh AB/BA process로 재측정한 정적 그림이다. 분석의 독립 반복 단위는 role이 아니라
두 role을 포함한 fresh CUDA-process pair session이며, 각 contrast는 AB 3회 + BA 3회
(`n=6`)다.

- Run: `results/raw/rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1/`
- Authoritative analysis: `.../analysis/analysis.json` (`status=pass`)
- Figure binding: `rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1_figure_manifest.json`

| 그림 | 읽는 방법 |
|---|---|
| `*_paired_slopes` | 같은 fresh session 안의 baseline → treatment 변화. 색은 AB/BA, 숫자는 전역 실행 순서다. |
| `*_paired_deltas` | 개별 paired Δ, 평균 diamond, descriptive t95를 0선과 함께 표시한다. 후보 두 개를 합산하거나 순위화하지 않는다. |
| `*_orientation_diagnostic` | AB/BA 각 3 session의 평균과 sample SD. order effect의 인과 추정이 아니라 잔여 순서 의존성 점검이다. |
| `*_quality_context` | 기록된 온도 범위와 baseline/treatment trace R². 온도는 hard rejection 또는 causal adjustment에 쓰지 않았다. |

재생성은 다음과 같다.

```bash
source scripts/activate_softmax_experiment_env.sh
RUN="results/raw/rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1"
python3 scripts/plot_softmax_whole_precision_targeted_confirmation.py \
  --run-dir "$RUN" \
  --out-dir docs/assets/softmax_whole_precision_targeted_confirmation
```

plotter는 현재 `manifest.json` SHA가 analysis에 결속돼 있는지 확인하고,
`analysis.json` 내부의 authoritative 배열과 CSV view를 교차 검증한 뒤 PNG/SVG와
figure manifest를 생성한다.
