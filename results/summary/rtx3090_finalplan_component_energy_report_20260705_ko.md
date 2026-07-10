# RTX 3090 Finalplan Component Energy Report

작성일: 2026-07-05

## 1. 결론

이번 반복은 기존보다 더 엄격하게 진행했다. 먼저 계획을 문서화했고, energy run과 NCU validation을 분리했으며, byte-path denominator는 NCU actual traffic으로 보정했다. 그 결과 계층 순서는 이전보다 논리적으로 정합한다.

| Component/path | median estimate | unit | min | max | rows used | status |
|---|---:|---|---:|---:|---:|---|
| Tensor MMA incremental | 0.168 | pJ/FLOP | 0.0878 | 0.295 | 5 | accepted candidate |
| Global L1 hit path, W_SM=16 KiB | 0.156 | pJ/bit | 0.0789 | 0.690 | 5 | accepted candidate, variance high |
| Shared scalar path, W_SM=64 KiB | 0.271 | pJ/bit | 0.0997 | 0.919 | 5 | accepted candidate, variance high |
| L2 CG hit path, W_SM=64 KiB | 1.176 | pJ/bit | 0.947 | 3.064 | 5 | accepted candidate, stall-heavy |
| DRAM CG streaming path, W_SM=8192 KiB | 4.006 | pJ/bit | 2.825 | 6.044 | 3 | sanity candidate only |

이 값은 순수 회로/bitcell energy가 아니다. NVML board-level energy에서 matched-control 차분으로 얻은 effective microbenchmark coefficient다. 특히 DRAM 값은 RTX 3090 GDDR6X streaming path sanity 값이며 HBM2 physical energy와 직접 비교하면 안 된다.

2026-07-07 재점검에서 [power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)의 기준을 분석에 반영했다. 최종 matched-control row는 `nvml_total_energy`, `total_energy_mj_delta`, `nvml_total_energy_supported=true`인 row만 사용하도록 gate를 추가했고, RTX 3090 profile의 `GetPowerUsage` 의미는 `one_sec_average`로 기록했다. 이 `one_sec_average`는 fallback power API의 의미이며, 아래 최종 coefficient의 energy numerator는 endpoint power fallback이 아니라 total energy mJ counter 차분이다.

## 2. 문서화한 계획

계획 문서:

- `docs/methodology/component_energy_final_experiment_plan_ko.md`
- `docs/platforms/power_measurement_api_matrix_ko.md`

핵심 설계:

| 설계 항목 | 적용 내용 |
|---|---|
| GPU architecture | RTX 3090 GA102 기준 256 KiB register/SM, 128 KiB combined L1/shared/SM, 6 MiB L2, GDDR6X |
| Tensor | `reg_mma - reg_operand_only`, denominator는 FLOP |
| Shared | `shared_scalar_load_only - clocked_empty`, denominator는 NCU shared bytes |
| Global L1 | `global_l1_load_only - clocked_empty`, denominator는 NCU L1 bytes |
| L2 | RTX 3090에서는 일반 `l2_load_only`가 L1 hit 지배라 제외하고 `l2_cg_load_only` 사용 |
| DRAM | 필수 component가 아니라 L2/DRAM order sanity check |
| Reject rule | 음수 coefficient, NCU denominator 없음, NCU path reject는 final table에서 제외 |

## 3. 실행 조건

Energy run은 NCU 없이 실행했다.

| File | rows | elapsed range (s) | non-positive net energy rows | SMID bad rows |
|---|---:|---:|---:|---:|
| `results/raw/rtx3090_finalplan_tensor_energy_20260705.csv` | 30 | 4.931-5.614 | 0 | 0 |
| `results/raw/rtx3090_finalplan_shared_energy_20260705.csv` | 30 | 4.783-5.754 | 0 | 0 |
| `results/raw/rtx3090_finalplan_l1_energy_20260705.csv` | 60 | 4.801-5.847 | 0 | 0 |
| `results/raw/rtx3090_finalplan_l2_energy_20260705.csv` | 30 | 4.770-5.657 | 0 | 0 |
| `results/raw/rtx3090_finalplan_dram_energy_20260705.csv` | 18 | 4.806-5.541 | 0 | 0 |

Power measurement metadata:

| Item | Value | Meaning |
|---|---|---|
| energy_source | `nvml_total_energy` | NVML total energy mJ counter 차분 사용 |
| energy_integration_method | `total_energy_mj_delta` | endpoint power trapezoid fallback이 아님 |
| nvml_total_energy_supported | `true` for all finalplan energy rows | Volta+ total energy counter path 사용 가능 |
| nvml_power_usage_semantics | `one_sec_average` | RTX 3090에서 `GetPowerUsage` fallback의 의미 |
| power API smoke | `results/summary/rtx3090_power_api_smoke_20260707.md` | 현재 환경의 power field/preflight 확인 |

Sweep 조건:

| Component | modes | W_SM (KiB) | blocks/SM | active_SM (SM) | factor sweep | seconds (s) | repeats |
|---|---|---:|---:|---:|---|---:|---:|
| Tensor | `reg_operand_only`, `reg_mma` | 2048 | 16 | 82 | reuse 1,2,4,8,16 | 5 | 3 |
| Shared scalar | `clocked_empty`, `shared_scalar_load_only` | 64 | 16 | 82 | load_repeat 1,2,4,8,16 | 5 | 3 |
| Global L1 | `clocked_empty`, `global_l1_load_only` | 16,64 | 16 | 82 | load_repeat 1,2,4,8,16 | 5 | 3 |
| L2 CG | `clocked_empty`, `l2_cg_load_only` | 64 | 16 | 82 | load_repeat 1,2,4,8,16 | 5 | 3 |
| DRAM CG | `clocked_empty`, `dram_cg_load_only` | 8192 | 16 | 82 | load_repeat 1,4,16 | 5 | 3 |

## 4. NCU Path Validation

NCU result files:

- `results/ncu/rtx3090_finalplan_ncu_lr4_20260705/ncu_cache_validation_summary.csv`
- `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_20260705.md`
- `results/summary/rtx3090_finalplan_ncu_lr4_acceptance_tensor200m_20260705.md`

Tensor/register row는 default absolute memory threshold 100 MB에서 `reg_mma`와 `reg_operand_only`가 약간 reject됐다. 이유는 spill이 아니라 L2 bytes가 각각 약 126 MB, 121 MB였기 때문이다. reuse=4/B16 대표 row에서는 이 absolute threshold가 너무 보수적이라, 별도 acceptance 파일에서 tensor/register absolute threshold를 200 MB로 완화했다. 이 완화는 final report에 명시하며, pure-register claim으로 사용하지 않는다.

| Mode | Candidate | Acceptance | L1 hit (%) | L2 hit (%) | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB (%) | Note |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `reg_mma` | Tensor | accepted with 200 MB tensor threshold | 36.420 | 40.839 | 0 | 0 | 1.264e8 | 8.098e7 | 0.0128 | HMMA 1.050e9, spill/local 0 |
| `reg_operand_only` | Tensor control | accepted with 200 MB register threshold | 31.405 | 60.183 | 0 | 0 | 1.212e8 | 7.737e7 | 0.0101 | HMMA 0, spill/local 0 |
| `shared_scalar_load_only` | Shared scalar | accepted | 20.941 | 69.318 | 5.374e11 | 0 | 2.580e8 | 1.717e8 | 0.00208 | shared bank conflicts 0 |
| `global_l1_load_only` | Global L1 | accepted | 99.999 | 58.191 | 0 | 1.075e12 | 3.141e8 | 2.193e8 | 17.429 | L2/L1 byte ratio 0.000292 |
| `l2_load_only` | L2 capacity | rejected | 88.369 | 99.794 | 0 | 1.075e12 | 1.254e11 | 2.955e8 | 70.728 | L1 hit too high |
| `l2_cg_load_only` | L2 CG | accepted | 0.000006 | 99.941 | 0 | 5.374e11 | 5.380e11 | 4.830e8 | 866.815 | DRAM/L2 byte ratio 0.000898 |
| `dram_cg_load_only` | DRAM sanity | accepted | 0.000006 | 0.156 | 0 | 5.374e11 | 5.389e11 | 5.385e11 | 1770.600 | DRAM streaming sanity |
| `shared_load_only` | Shared WMMA load | rejected | 26.849 | 57.606 | 5.374e11 | 0 | 4.561e8 | 3.195e8 | 0.000554 | bank conflicts high |

## 5. Energy Calculation

Analysis files:

- `results/summary/rtx3090_finalplan_matched_control_summary_20260705.csv`
- `results/summary/rtx3090_finalplan_matched_control_detail_20260705.csv`
- `results/summary/rtx3090_finalplan_matched_control_report_20260705.md`

분석 명령은 `--require-ncu-denominator`, `--require-total-energy`, `--expected-power-semantics one_sec_average`를 사용했다. Tensor acceptance는 기본 memory threshold 보고서와 `tensor200m` threshold 보고서를 함께 넣어 accepted mode union으로 처리했다.

계산식:

```text
delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s
coefficient = delta_E_J / denominator
```

Byte path denominator는 NCU actual bytes로 보정했다. 같은 W_SM/blocks/SM/active_SM에서 load_repeat만 다른 energy row는 NCU LR=4 대표 row의 actual/expected ratio를 사용했다. NCU denominator가 없는 byte row는 invalid 처리했다.

| Component | median | unit | median pJ/bit | NCU denominator rows | energy source | integration | power semantics | invalid rows | Interpretation |
|---|---:|---|---:|---:|---|---|---|---:|---|
| Tensor MMA incremental | 0.168 | pJ/FLOP |  | 0 | `nvml_total_energy` | `total_energy_mj_delta` | `one_sec_average` | 0 | `reg_mma - reg_operand_only` effective incremental |
| Shared scalar path | 2.164 | pJ/byte | 0.271 | 5 | `nvml_total_energy` | `total_energy_mj_delta` | `one_sec_average` | 0 | shared instruction path |
| Global L1 hit path, W=16 only | 1.251 | pJ/byte | 0.156 | 5 | `nvml_total_energy` | `total_energy_mj_delta` | `one_sec_average` | 5 | global L1 hit path; W=64 rows rejected |
| L2 CG hit path | 9.405 | pJ/byte | 1.176 | 5 | `nvml_total_energy` | `total_energy_mj_delta` | `one_sec_average` | 0 | L1 bypassed L2-hit transaction path |
| DRAM CG streaming path | 32.048 | pJ/byte | 4.006 | 3 | `nvml_total_energy` | `total_energy_mj_delta` | `one_sec_average` | 0 | GDDR6X streaming sanity |

## 6. Rejected Results

| Item | Rejection reason | Decision |
|---|---|---|
| Global L1 W_SM=64 KiB energy rows | NCU denominator가 없고 5개 중 3개가 negative coefficient | final L1 coefficient에서 제외 |
| `l2_load_only` | NCU L1 hit 88.369% | RTX 3090 L2 coefficient에서 제외 |
| `shared_load_only` | NCU shared bank conflicts high | shared scalar path 대신 사용하지 않음 |
| Register direct pJ/update | scalar ALU/control/active power 포함 | register file energy로 보고하지 않음 |
| DRAM physical pJ/bit claim | RTX 3090 GDDR6X board-level streaming path | physical DRAM device energy로 보고하지 않음 |
| `legacy_get_power_usage_integral` fallback | endpoint power trapezoid는 1초 평균 window와 짧은 kernel에 취약 | final coefficient에서 제외하고 provisional로만 보고 |

## 7. 판단

이번 실험은 이전보다 훨씬 나아졌다. 특히 L1/shared가 L2보다 작고, L2가 DRAM sanity보다 작은 순서가 나왔다.

```text
Global L1 hit:       0.156 pJ/bit
Shared scalar:       0.271 pJ/bit
L2 CG hit:           1.176 pJ/bit
DRAM CG streaming:   4.006 pJ/bit
Tensor incremental:  0.168 pJ/FLOP
```

하지만 아직 final physical component energy라고 부르면 안 된다. 남은 제한은 다음과 같다.

| Limitation | Impact |
|---|---|
| NVML board-level energy | scheduler/control/cache/memory controller가 섞인다. |
| GPU 세대별 power API 의미 | RTX 3090의 `GetPowerUsage`는 1초 평균이다. 이번 최종 row는 total energy counter를 써서 fallback 문제를 피했지만, fallback row는 직접 비교하면 안 된다. |
| NCU LR=4 representative only | 모든 energy row를 NCU로 1:1 검증한 것은 아니다. |
| Tensor/register acceptance threshold 완화 | pure Tensor claim이 아니라 effective incremental 후보로 제한해야 한다. |
| L1 variance high | W=16은 양수지만 min-max가 크다. W=64는 invalid다. |
| L2/DRAM long scoreboard high | pJ/bit가 memory path와 stall/control을 함께 반영한다. |

## 8. 다음 단계

| Priority | Action | Reason |
|---:|---|---|
| 1 | L1 W_SM=16에 대해 NCU sidecar를 load_repeat 1,2,4,8,16 전체로 확장 | representative denominator 가정을 제거 |
| 2 | Shared/L2도 load_repeat 전체 NCU sidecar로 확장 | actual bytes와 stall 변화를 직접 join |
| 3 | Tensor NCU acceptance를 absolute byte threshold 대신 bytes/FLOP ratio 기준으로 개선 | threshold 완화의 주관성을 줄임 |
| 4 | A100에서 같은 acceptance-first flow 실행 | 40 MiB L2와 192 KiB L1/shared에서 capacity 기반 L2 실험 검증 |
| 5 | 10-20초, repeats 5-7 final run | L1 variance와 thermal/clock drift 축소 |
