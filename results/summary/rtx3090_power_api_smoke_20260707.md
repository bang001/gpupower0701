# RTX 3090 Power API Smoke Check

작성일: 2026-07-07

목적: [docs/platforms/power_measurement_api_matrix_ko.md](../../docs/platforms/power_measurement_api_matrix_ko.md)의 기준을 현재 RTX 3090/WSL 환경에 적용했을 때, energy run이 어떤 NVML 경로를 쓰는지 확인한다.

## Preflight

| item | value |
|---|---|
| GPU | NVIDIA GeForce RTX 3090 |
| driver | 591.86 |
| compute capability | 8.6 |
| profile | `rtx3090` |
| `power.draw` | 19.94 W |
| `power.draw.average` | 19.94 W |
| `power.draw.instant` | 21.02 W |
| `power.limit` | 370.00 W |
| `nvml_power_usage_semantics` | `one_sec_average` |
| `ncu` in PATH | not found |
| preflight file | `results/summary/rtx3090_power_api_preflight_20260707.md` |

## Sequential Energy Smoke

Raw CSV: `results/raw/rtx3090_power_api_smoke_20260707.csv`

| mode | elapsed (s) | net_E_J (J) | energy_source | integration | total energy supported | power semantics | field instant | field average | SM clock (MHz) | mem clock (MHz) | temp (C) |
|---|---:|---:|---|---|---|---|---|---|---:|---:|---:|
| `clocked_empty` | 1.9275 | 346.602 | `nvml_total_energy` | `total_energy_mj_delta` | true | `one_sec_average` | false | false | 1935 | 9501 | 66 |
| `shared_scalar_load_only` | 2.1760 | 407.847 | `nvml_total_energy` | `total_energy_mj_delta` | true | `one_sec_average` | false | false | 1920 | 9501 | 71 |

## Interpretation

- 현재 RTX 3090 환경에서는 finalplan raw energy row와 새 smoke 모두 `nvml_total_energy`를 사용한다.
- `GetPowerUsage` 의미는 `one_sec_average`로 기록되지만, 이번 finalplan coefficient의 energy numerator는 endpoint power fallback이 아니라 total energy mJ counter 차분이다.
- `ncu`가 현재 PATH에 없으므로 이 환경에서 새 NCU sidecar를 추가 수집하려면 Nsight Compute 경로를 명시해야 한다.
- 위 smoke는 2초/1회 실행이라 component coefficient로 사용하지 않는다. 신뢰 가능한 coefficient는 기존 finalplan energy sweep과 NCU acceptance 결과를 재분석한 `results/summary/rtx3090_finalplan_matched_control_report_20260705.md`를 기준으로 한다.
