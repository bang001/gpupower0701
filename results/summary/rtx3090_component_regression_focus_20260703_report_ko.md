# RTX 3090 duration-aware component regression 결과

## 결론

새 설계의 1차 focused run은 정상 수행되었다. 가장 중요한 개선점은 이전 pair 실험의 치명적 문제였던 elapsed mismatch가 크게 줄었다는 점이다. 이번 raw row의 kernel elapsed는 전체적으로 2.824~3.503 s 범위에 들어왔다.

하지만 아직 이 결과를 물리 component energy로 보고하면 안 된다. static expected byte 기반 회귀에서는 `shared_bytes`, `reg_operand_ops`, `store_bytes`가 음수로 나왔고, NCU actual traffic이 없어서 L1/L2/DRAM byte denominator가 실제 hardware traffic인지 확인되지 않았다.

## 실행 조건

| 항목 | 값 | 단위/비고 |
|---|---:|---|
| GPU profile | RTX 3090 | `rtx3090` |
| active SM | 82 | SM |
| blocks/SM | 16 | blocks/SM |
| W_SM | 64, 8192 | KiB |
| reuse_factor | 1, 4 | MMA/load |
| load_repeat | 1, 4 | load/tile |
| store_repeat | 1, 4 | store/tile |
| target seconds | 3 | s/row |
| repeats | 2 | runner-level count |
| energy source | nvml_total_energy | NVML total energy |
| byte source in regression | static expected bytes | NCU actual byte 아님 |

## 자가점검

| 항목 | 결과 | 판정 |
|---|---:|---|
| raw measurement rows | 224 | expected 224, 통과 |
| matrix rows | 160 | valid 112, invalid 48 |
| SMID histogram ok | 224/224 | 통과 |
| elapsed min | 2.824395 | s |
| elapsed median | 3.295875 | s |
| elapsed max | 3.502833 | s |
| elapsed max/min | 1.240 | 이전 pair 대비 크게 개선 |

## Mode별 elapsed QA

| mode | rows | median elapsed (s) | min (s) | max (s) |
|---|---:|---:|---:|---:|
| dram_load_only | 16 | 3.3036 | 3.2538 | 3.4042 |
| dram_mma | 16 | 3.3428 | 3.2101 | 3.4357 |
| empty | 32 | 3.1929 | 2.8244 | 3.2764 |
| l2_load_only | 16 | 3.3886 | 3.2473 | 3.4499 |
| l2_mma | 16 | 3.3330 | 3.2919 | 3.5028 |
| reg_mma | 32 | 3.2630 | 3.1310 | 3.3525 |
| reg_operand_only | 32 | 3.2688 | 3.1604 | 3.3590 |
| shared_load_only | 16 | 3.3329 | 3.2987 | 3.4661 |
| shared_mma | 16 | 3.3220 | 3.2372 | 3.3918 |
| store_only | 32 | 3.2901 | 3.1787 | 3.3442 |

## Static-byte regression 결과

| feature | estimate | unit | warning | 해석 |
|---|---:|---|---|---|
| intercept | -309.954 | J |  | 모델 offset. 물리 의미 부여 금지. |
| elapsed_s | 273.078 | W |  | time/active power 항. 이번 모델에서 가장 큰 설명 축. |
| FLOP | 0.0104633 | pJ/FLOP |  | Tensor/MMA 관련 effective slope 후보지만 static model 결과라 보조값. |
| reg_operand_ops | -9283.41 | pJ/reg-op | negative_coefficient | 음수이므로 component coefficient로 무효. |
| shared_bytes_static | -0.475466 | pJ/byte | negative_coefficient;static_byte | 음수이므로 shared/L1 byte energy로 무효. |
| l2_bytes_static | 0.764098 | pJ/byte | static_byte | 양수지만 static expected byte 기준. NCU 검증 전에는 후보값. |
| dram_bytes_static | 20.6839 | pJ/byte | static_byte | 양수지만 static expected byte 기준. NCU 검증 전에는 후보값. |
| store_bytes_static | -980.541 | pJ/byte | negative_coefficient;static_byte | 음수이므로 store byte energy로 무효. |

회귀 품질: RMSE 49.089 J, relative RMSE 9.660%, R2 0.886. Fit 자체는 동작하지만 음수 계수가 남아 있으므로 coefficient 해석은 제한해야 한다.

## pJ/bit 환산 후보

| feature | pJ/byte | pJ/bit | 채택 여부 |
|---|---:|---:|---|
| shared_bytes_static | -0.475 | -0.059 | 무효: 음수 coefficient |
| l2_bytes_static | 0.764 | 0.096 | 후보: NCU actual byte 필요 |
| dram_bytes_static | 20.684 | 2.585 | 후보: NCU actual byte 필요 |
| store_bytes_static | -980.541 | -122.568 | 무효: 음수 coefficient |

## 정합성 판단

| 질문 | 판단 | 근거 |
|---|---|---|
| 이전 elapsed mismatch 문제를 줄였나? | 예 | elapsed max/min이 약 1.240으로 줄었다. 이전 pair에서는 수백 배 차이가 있었다. |
| 이 결과를 component pJ로 바로 쓸 수 있나? | 아니오 | 음수 coefficient가 있고 static expected byte만 사용했다. |
| 회귀 방식은 동작하나? | 예 | 224 rows, 7 features, relative RMSE 9.66%로 fitting 자체는 정상. |
| L2/DRAM 값이 물리적으로 확정됐나? | 아니오 | NCU actual bytes, hit rate, access count, stall 검증이 아직 없다. |

## 다음 조치

1. NCU validation을 같은 대표 좌표에 대해 실행해 L1/L2 hit rate, L1/L2/DRAM access count, DRAM bytes, stall %를 확보한다.
2. `fit_component_energy_model.py --byte-source prefer-ncu`를 NCU byte가 join된 CSV에 다시 적용한다.
3. final coefficient는 `seconds>=10`, `repeats>=5`로 재측정한다.
4. `shared_load_only`/`global_load_only`의 checksum overhead를 더 줄이거나 `checksum_only`, `address_only` control을 별도 추가한다.

## 산출물

- Raw CSV: `results/raw/rtx3090_component_regression_focus_20260703.csv`
- Matrix CSV: `results/raw/rtx3090_component_regression_focus_20260703_matrix.csv`
- Static fit CSV: `results/summary/rtx3090_component_regression_focus_20260703_fit.csv`
- Static fit MD: `results/summary/rtx3090_component_regression_focus_20260703_fit.md`
- Prefer-NCU fit MD: `results/summary/rtx3090_component_regression_focus_20260703_fit_prefer_ncu.md`
