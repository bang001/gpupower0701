# RTX 3090 current primary selection audit

작성일: 2026-07-08

이 문서는 `results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv`에서 어떤 artifact를 current primary로 선택했는지 점검한 기록이다. Power/energy numerator 해석은 `docs/platforms/power_measurement_api_matrix_ko.md`를 따른다. 즉 final coefficient의 분자는 `nvmlDeviceGetTotalEnergyConsumption` 기반 `nvml_total_energy` / `total_energy_mj_delta` row를 우선하며, RTX 3090의 `GetPowerUsage` 1초 평균 값은 final numerator로 쓰지 않는다.

## Selection rule

| 기준 | primary 선택 원칙 |
|---|---|
| Power API | `final_candidate` row만 사용. `provisional` 또는 fallback power integration은 primary 제외 |
| Measurement scope | `gpu_device_total_energy_counter` scope 유지 |
| NCU | 해당 path의 NCU acceptance와 denominator row 필요 |
| Matched-control | negative/weak-signal row가 없거나, 있으면 primary 대신 auxiliary/caution으로 격하 |
| Power-state | reject row는 primary에서 제외. caution row는 원인을 문서화 |
| Method sensitivity | clean run이 있어도 다른 LR/duration 결과와 함께 range로 보고 |

주의: 2026-07-08 RTX 3090 component raw 파일 대부분은 explicit `measurement_scope`
CSV 컬럼 도입 이전 schema다. 기존 power audit의 scope는 `nvml_total_energy`와
`total_energy_mj_delta` 조합에서 추론한 것이다. 새 finalplan/A100/V100/H100 결과는
`--require-explicit-measurement-scope`를 통과한 raw CSV만 strict final 후보로 본다.

## Primary decisions

| Component | current primary | decision | 이유 |
|---|---:|---|---|
| Tensor MMA incremental | 0.106657768324 pJ/FLOP | 유지 | RF=8/16 targeted run이 12/12 valid, power API 24/24 final, power-state 24/24 ok. 단 RF8/RF16 auxiliary와 함께 RF-dependent range로 보고 |
| Shared scalar path | 0.148735236874 pJ/bit | LR4/LR8 fixed-ITER focus로 승격 | LR4/LR8 fixed-ITER focus가 10/10 valid, power API 30/30 final, power-state 30/30 ok, reliability accepted로 가장 깨끗하다. targeted mixed-LR 0.152 pJ/bit, interleaved aggregate 0.145 pJ/bit, fixed-ITER LR4/LR8/LR16 aggregate 0.140 pJ/bit가 같은 범위를 지지한다. 다만 LR16 lower-side와 LR/policy별 coefficient spread는 남아 single constant 아님 |
| Global L1 hit path | 0.148475682850 pJ/bit | paired combined로 승격 | 기존 duration-scaling 0.156 pJ/bit는 14/15 valid지만 invalid detail 1개가 남음. C-T-C paired combined는 12/12 valid, power API 36/36 final, power-state 36/36 ok, reliability accepted |
| L2 CG hit path | 1.016556433727 pJ/bit | paired LR4/LR8 combined로 승격 | C-T-C paired LR4/LR8 combined는 12/12 valid, power API 36/36 final, power-state 36/36 ok, reliability accepted. targeted mixed-LR 0.978 pJ/bit는 caution metadata가 있어 auxiliary support로 유지 |
| DRAM CG streaming path | 3.540697769749 pJ/bit | sanity only | hierarchy sanity 값. physical DRAM/GDDR6X/HBM device energy로 해석하지 않음 |

## Global L1 change

Global L1은 이전 current primary가 duration-scaling artifact였다.

| Artifact | median | rows | reliability | 판단 |
|---|---:|---:|---|---|
| duration-scaling filtered | 0.1561091370146893 pJ/bit | 14 | accepted_with_caution | slope/duration auxiliary로 유지 |
| paired 30초 combined | 0.14847568285000448 pJ/bit | 12 | accepted | current primary로 승격 |
| LR8 paired 30초 | 0.10904234486631326 pJ/bit | 6 | accepted | lower-side method-sensitivity evidence |
| 60초 filtered | 0.11914777440046519 pJ/bit | 7 | accepted | duration/power drift sensitivity evidence |

따라서 Global L1은 `0.148 pJ/bit`를 current primary로 쓰되, 단일 L1 SRAM bitcell energy가 아니라 NCU로 L1-hit path가 확인된 board-level effective coefficient로 해석한다. 보고서에서는 `0.11-0.16 pJ/bit` 범위를 함께 제시한다.

## L2 change

L2는 이전 current primary가 targeted mixed-LR artifact였다.

| Artifact | median | rows | reliability | 판단 |
|---|---:|---:|---|---|
| targeted mixed-LR filtered | 0.9781974616407318 pJ/bit | 30 | accepted | auxiliary support로 유지. control temperature caution 1개가 traceability metadata로 남음 |
| paired LR4/LR8 30초 combined | 1.016556433726509 pJ/bit | 12 | accepted | current primary로 승격. power API 36/36 final, power-state 36/36 ok |
| LR4 paired 30초 | 1.0272539734213253 pJ/bit | 6 | accepted | paired combined를 지지하는 high-side auxiliary |
| LR8 paired 30초 | 0.9596403819965263 pJ/bit | 6 | accepted | paired combined를 지지하는 low-side auxiliary |
| LR4 non-paired 30초 | 1.2976392121691205 pJ/bit | 9 | accepted | drift/order-sensitive high-side evidence |

따라서 L2는 `1.017 pJ/bit`를 current primary로 쓰되, L2 SRAM bitcell energy가 아니라
NCU로 L1-bypass/L2-hit path가 확인된 board-level effective coefficient로 해석한다.
보고서에서는 targeted 0.978 pJ/bit, LR8 paired 0.960 pJ/bit, LR4 paired
1.027 pJ/bit를 함께 제시한다.

## Remaining cautions

| Component | 남은 문제 | 다음 개선 방향 |
|---|---|---|
| Shared scalar | LR에 따른 high/mid/low split이 큼. Interleaved/fixed-ITER aggregate와 LR4/LR8 focus는 primary를 지지하고 LR16 focus는 prior weak row를 해소했지만, factor spread는 남음 | NCU가 가능한 환경에서 fixed-ITER condition의 instruction issue/stall counter를 함께 수집 |
| L2 CG | primary 자체의 power-state caution은 해소됐지만 LR4/LR8/targeted/non-paired 간 method sensitivity가 남음 | L2-only C-T-C repeats를 더 늘리고 long-scoreboard stall과 coefficient를 함께 회귀 |
| DRAM CG | sanity path이고 physical DRAM energy가 아님 | DRAM은 hierarchy sanity로만 유지하거나 외부 power meter/HBM-specific telemetry가 있을 때 별도 분석 |
| Cross-platform | A100/V100/H100 실측은 아직 RTX 3090 evidence로 대체 불가 | 각 platform에서 `power_measurement_api_matrix_ko.md` 기준으로 raw metadata, NCU denominator, power-state audit을 새로 수집 |
