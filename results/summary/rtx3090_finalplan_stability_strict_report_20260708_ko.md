# RTX 3090 Finalplan Stability/Strict Component Energy Report

작성일: 2026-07-08

## 1. 목적

2026-07-05 finalplan 결과는 NCU path acceptance와 NVML total-energy gate를 통과했지만,
L1/shared 계수의 분산이 컸다. 이번 반복은 같은 NCU-accepted 좌표에서 energy run만 더 길게
재측정하고, 반복 run을 더 보수적으로 분석해 noise floor 안의 row를 제외하는 것이 목적이다.

이 값은 순수 회로 에너지가 아니다. `nvml_total_energy` 기반 board-level energy에서
treatment-control 차분을 수행하고, NCU counter로 path와 byte denominator를 검증한
effective microbenchmark coefficient다.

## 2. 추가 적용한 분석 gate

| Gate | 값 | 이유 |
|---|---:|---|
| Energy source | `nvml_total_energy` | endpoint power fallback 배제 |
| Integration | `total_energy_mj_delta` | 실행 전후 누적 mJ counter 차분 |
| Power semantics | `one_sec_average` | RTX 3090 profile metadata 확인 |
| Pairing | `nearest-control` | 반복 run에서 실행 순서상 가장 가까운 control과 비교 |
| Minimum delta_E | 10 J | 너무 작은 양수 delta를 noise floor로 제외 |
| Minimum delta fraction | 0.005 | `delta_E / max(treatment_E, scaled_control_E)`가 0.5% 미만인 row 제외 |
| NCU denominator | required | memory pJ/byte는 NCU actual-byte scale 없으면 제외 |

## 3. 재측정 조건

| Component | modes | W_SM (KiB) | blocks/SM | active_SM (SM) | factor values | target time (s) | repeats |
|---|---|---:|---:|---:|---|---:|---:|
| Tensor | `reg_operand_only`, `reg_mma` | 2048 | 16 | 82 | reuse 1,2,4,8,16 | 8 | 3 |
| Shared scalar | `clocked_empty`, `shared_scalar_load_only` | 64 | 16 | 82 | load_repeat 4,8,16 | 8 | 3 |
| Global L1 | `clocked_empty`, `global_l1_load_only` | 16 | 16 | 82 | load_repeat 4,8,16 | 8 | 3 |
| L2 CG | `clocked_empty`, `l2_cg_load_only` | 64 | 16 | 82 | load_repeat 4,8,16 | 8 | 3 |
| DRAM CG | `clocked_empty`, `dram_cg_load_only` | 8192 | 16 | 82 | load_repeat 4,8,16 | 8 | 3 |

## 4. Raw run 품질

| raw CSV | rows | elapsed range (s) | temperature range (C) | SM clock range (MHz) | energy source |
|---|---:|---:|---:|---:|---|
| `results/raw/rtx3090_finalplan_stability_tensor_20260708_stability.csv` | 30 | 7.947-9.118 | 63-72 | 1920-1950 | `nvml_total_energy` |
| `results/raw/rtx3090_finalplan_stability_shared_20260708_stability.csv` | 18 | 8.858-9.390 | 74-80 | 1890-1905 | `nvml_total_energy` |
| `results/raw/rtx3090_finalplan_stability_l1_20260708_stability.csv` | 18 | 8.949-10.432 | 69-78 | 1890-1920 | `nvml_total_energy` |
| `results/raw/rtx3090_finalplan_stability_l2_20260708_stability.csv` | 18 | 8.872-9.160 | 76-82 | 1890-1905 | `nvml_total_energy` |
| `results/raw/rtx3090_finalplan_stability_dram_20260708_stability.csv` | 18 | 8.780-9.366 | 76-79 | 1875-1905 | `nvml_total_energy` |

모든 row는 `energy_integration_method=total_energy_mj_delta`,
`nvml_total_energy_supported=true`, `nvml_power_usage_semantics=one_sec_average`였다.

## 5. Strict 결과

| Component/path | median | unit | bootstrap median 95% CI | rows used | confidence | invalid rows | 판단 |
|---|---:|---|---:|---:|---|---:|---|
| Tensor MMA incremental | 0.170 | pJ/FLOP | 0.120-0.311 | 15 | low | 0 | accepted candidate, variance remains |
| Shared scalar path | 0.151 | pJ/bit | 0.0910-0.305 | 6 | medium | 3 | accepted candidate, weak-signal rows excluded |
| Global L1 hit path | 0.150 | pJ/bit | 0.0551-0.214 | 7 | medium | 2 | accepted candidate, weak/negative rows excluded |
| L2 CG hit path | 1.138 | pJ/bit | 0.707-1.424 | 9 | medium | 0 | accepted candidate, stall-heavy |
| DRAM CG streaming path | 3.542 | pJ/bit | 2.964-4.454 | 9 | medium-high | 0 | sanity candidate only |

현재 hierarchy는 다음처럼 정리된다.

```text
Shared scalar ~= Global L1 hit  <  L2 CG hit  <  DRAM CG streaming sanity
0.151 pJ/bit     0.150 pJ/bit      1.138 pJ/bit   3.542 pJ/bit
```

`confidence`는 row 수, relative IQR, bootstrap median CI 폭으로 만든 반복 안정도
라벨이다. 물리 component isolation의 보증이 아니다. Tensor는 median 자체는 기존 결과와
가깝지만 reuse별 산포가 커서 low로 표기했다.

## 5.1 Factor exact-NCU 재분석

현재 analyzer는 NCU acceptance와 denominator를 factor 좌표까지 맞춰 필터링할 수 있다.
2026-07-08에 현재 stability factor set을 직접 포함하는 NCU sidecar를 추가 실행했다.
그 결과 memory path는 모두 `ncu_actual_exact` denominator로 재계산되었고, broad strict
median과 사실상 같은 값이 나왔다.

| Component/path | exact condition | median | unit | median pJ/bit | rows used | confidence |
|---|---|---:|---|---:|---:|---|
| Tensor MMA incremental | reuse 1,2,4,8,16 | 0.169745 | pJ/FLOP | - | 15 | low |
| Shared scalar path | load_repeat 4,8,16 | 1.20901 | pJ/byte | 0.151126 | 6 | medium |
| Global L1 hit path | load_repeat 4,8,16 | 1.20361 | pJ/byte | 0.150451 | 7 | medium |
| L2 CG hit path | load_repeat 4,8,16 | 9.10486 | pJ/byte | 1.13811 | 9 | medium |
| DRAM CG streaming path | load_repeat 4,8,16 | 28.3256 | pJ/byte | 3.54070 | 9 | medium-high |

상세 내용은 [rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md](rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md)에 둔다.

## 6. 기존 결과와 비교

| Component/path | 2026-07-05 median | 2026-07-08 strict median | 단위 | 해석 |
|---|---:|---:|---|---|
| Tensor MMA incremental | 0.168 | 0.170 | pJ/FLOP | 거의 동일 |
| Shared scalar path | 0.271 | 0.151 | pJ/bit | 약한 delta row 제거 후 L1과 비슷한 수준 |
| Global L1 hit path | 0.156 | 0.150 | pJ/bit | 거의 동일 |
| L2 CG hit path | 1.176 | 1.138 | pJ/bit | 거의 동일 |
| DRAM CG streaming path | 4.006 | 3.542 | pJ/bit | 더 긴 반복에서 산포 감소 |

## 7. 자가비판

| 항목 | 판단 |
|---|---|
| L1/shared 수치 | reference order에는 맞지만, board-level 차분 신호가 작아 여전히 최종 확정값은 아니다. |
| Tensor 수치 | median은 안정적이나 min-max 폭이 크다. `reg_operand_only` control이 pure register-only가 아니므로 Tensor-only physical energy로 부르면 안 된다. |
| L2 수치 | L1 bypass와 L2 hit는 NCU로 확인했지만 long scoreboard stall이 커서 stall/control 성분이 섞인다. |
| DRAM 수치 | L2보다 충분히 크고 GDDR6X streaming sanity로는 합리적이다. HBM physical pJ/bit와 같은 의미가 아니다. |
| NCU 검증 | factor별 NCU sidecar를 추가 실행해 현재 stability factor set의 memory denominator를 `ncu_actual_exact`로 재계산했다. |

## 8. 다음 개선

| 우선순위 | 개선 | 이유 |
|---:|---|---|
| 1 | A100/V100/H100 factor sidecar 실행 | RTX 3090에서는 representative LR=4 denominator 가정을 제거했으므로 다른 플랫폼에도 같은 기준 적용 |
| 2 | L1/shared 전용 matched control 추가 | `clocked_empty`보다 instruction/control path를 더 비슷하게 맞춤 |
| 3 | Tensor bytes/FLOP acceptance threshold 추가 | absolute memory threshold 완화의 주관성 감소 |
| 4 | A100에서 같은 strict gate로 재실험 | L2 40 MiB, L1/shared 구조 차이 반영 |
| 5 | 결과 report generator 작성 | 플랫폼별 표준 보고서 반복 생성 |
