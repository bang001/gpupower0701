# RTX 3090 component energy 음수 coefficient 재설계 결과

작성일: 2026-07-03

## 결론

기존 duration-aware OLS에서 나온 음수 coefficient는 계산 실수라기보다
`empty`와 모든 mode를 하나의 전역 baseline으로 묶은 모델 구조, duration
calibration에 따른 byte variation 상쇄, static byte denominator 사용이
겹친 결과다.

수정 후 `mode/family baseline + non-negative active-set` 분석에서는 physical
candidate coefficient가 음수로 출력되지 않는다. 단, 0으로 붙은 항은
`0 pJ`가 아니라 **현재 matrix에서 양의 독립 slope가 식별되지 않음**으로
보고해야 한다.

## 원인 진단

| 항목 | 관측 | 결론 |
|---|---|---|
| 기존 OLS 음수 | `reg_operand_ops=-9283.41 pJ/reg-op`, `shared=-0.475 pJ/byte`, `store=-980.541 pJ/byte` | 전역 OLS를 component pJ로 쓰면 안 됨 |
| mode별 net energy | `reg_operand_only`, `store_only` 일부가 `empty`보다 낮음 | mode fixed/control 비용 분리 필요 |
| duration calibration | `load_repeat` 증가 시 `ITER`가 감소 | 총 expected byte variation이 약해짐 |
| NCU actual byte | raw CSV의 `ncu_*_bytes`가 0 | static logical byte 기준 결과만 존재 |
| fixed-ITER supplemental | byte는 8배 증가하지만 elapsed가 0.16~13.30 s로 확산 | monotonicity 점검용, final pJ 아님 |

## 구현 반영

| 파일 | 변경 |
|---|---|
| `scripts/fit_component_energy_model.py` | `--baseline-terms none|family|mode`, `--non-negative`, active-set solver, `unconstrained_estimate`, `--min-elapsed-s`, `--exclude-negative-net-energy` 추가 |
| `scripts/run_component_regression_sweep.py` | `--iters` 고정 ITER 실행 지원 |
| `README.md` | primary regression 예시를 non-negative + mode baseline으로 수정 |
| `docs/component_energy_regression_redesign_ko.md` | 음수 coefficient 원인과 새 해석 정책 기록 |

## 재분석 결과

| 분석 | rows | RMSE (J) | relative RMSE (%) | R2 | physical 음수 |
|---|---:|---:|---:|---:|---|
| duration + mode baseline + non-negative | 224 | 36.630 | 7.208 | 0.936 | 없음 |
| duration + family baseline + non-negative | 224 | 41.603 | 8.186 | 0.918 | 없음 |
| corrected fixed-ITER + mode baseline + non-negative | 24 | 13.423 | 3.975 | 0.9996 | 없음 |
| corrected fixed-ITER filtered + mode baseline + non-negative | 16 | 15.543 | 3.163 | 0.9996 | 없음 |

## Component coefficient 요약

| 분석 | coefficient | estimate | 단위 | 판정 |
|---|---|---:|---|---|
| duration + mode baseline | elapsed | 166.878 | W | active-time 후보 |
| duration + mode baseline | FLOP | 0 | pJ/FLOP | 식별 실패: unconstrained 음수 |
| duration + mode baseline | reg operand | 0 | pJ/reg-op | 식별 실패: unconstrained 음수 |
| duration + mode baseline | shared static byte | 1.865 | pJ/byte | 후보: NCU actual byte 필요 |
| duration + mode baseline | L2 static byte | 3.786 | pJ/byte | 후보: NCU actual byte 필요 |
| duration + mode baseline | DRAM static byte | 0 | pJ/byte | 식별 실패: unconstrained 음수 |
| duration + mode baseline | store static byte | 14398.670 | pJ/byte | denominator/설계 재검토 필요 |
| corrected fixed-ITER | reg operand | 6990.441 | pJ/reg-op | active-time 포함, final 아님 |
| corrected fixed-ITER | shared static byte | 46.907 | pJ/byte | active-time 포함, final 아님 |
| corrected fixed-ITER | L2 static byte | 52.638 | pJ/byte | active-time 포함, final 아님 |
| corrected fixed-ITER | DRAM static byte | 287.092 | pJ/byte | active-time 포함, final 아님 |
| corrected fixed-ITER | store static byte | 2545.998 | pJ/byte | active-time 포함, final 아님 |

## 해석

duration-calibrated non-negative 결과는 음수 출력 문제를 해결하지만, `FLOP`,
`reg_operand`, `DRAM`이 0 bound에 붙었다. 이는 현재 matrix만으로 해당 항의
양의 독립 slope를 분리하지 못했다는 뜻이다.

fixed-ITER supplemental은 `load_repeat`와 `store_repeat`에 따른 byte 증가가
실제로 slope에 반영되는지 보는 stress test로 유효하다. 하지만 elapsed spread가
크기 때문에 active SM, scheduler, dependency, stall, power-state 시간이 모두
byte slope로 들어간다. 그래서 이 값은 물리 SRAM/L2/HBM pJ/byte로 보고하면
안 된다.

## 다음 설계

| 단계 | 목적 | 실행 조건 |
|---|---|---|
| 1 | duration-calibrated final 재측정 | seconds >= 10, repeats >= 5, mode baseline + non-negative |
| 2 | fixed-ITER는 monotonicity만 확인 | elapsed spread 표를 같이 보고 final coefficient에서는 제외 |
| 3 | NCU actual traffic join | L1 hit rate, L2 hit rate, L1/L2/DRAM access count, stall % 확보 |
| 4 | store denominator 재설계 | final checksum store와 repeated store loop를 분리 |
| 5 | register/tensor 분리 강화 | `reg_operand_only` noise 감소, longer elapsed, possible matched scheduler-only control |

## 산출물

| 파일 | 내용 |
|---|---|
| `results/summary/rtx3090_component_regression_focus_20260703_fit_nnls_mode.md` | 기존 duration raw의 mode-baseline non-negative fit |
| `results/summary/rtx3090_component_regression_focus_20260703_fit_nnls_family.md` | 기존 duration raw의 family-baseline non-negative fit |
| `results/raw/rtx3090_component_regression_fixed_iter_corrected_20260703.csv` | corrected fixed-ITER supplemental raw |
| `results/summary/rtx3090_component_regression_fixed_iter_corrected_20260703_fit_nnls_mode.md` | corrected fixed-ITER non-negative fit |
| `results/summary/rtx3090_component_regression_fixed_iter_corrected_20260703_fit_nnls_mode_filtered.md` | elapsed/net-energy 필터 적용 fit |
