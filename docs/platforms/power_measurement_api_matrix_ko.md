# GPU 세대별 Power/Energy 측정 API 기준

작성일: 2026-07-09
공식 문서 확인일: 2026-07-09, NVIDIA NVML API Reference Guide vR610

이 문서는 RTX 3090, V100, A100, H100에서 component-energy microbenchmark를
실행할 때 NVML/nvidia-smi power 값을 어떻게 해석하고, 어떤 값을 최종
`pJ/FLOP` 또는 `pJ/bit` 계산의 energy numerator로 쓸 수 있는지 정리한다.

핵심 결론은 하나다.

```text
최종 component coefficient의 energy numerator는 가능한 한
NVML GPU/device total-energy mJ counter의 전후 차분을 사용한다.

GetPowerUsage, power.draw.*, Hopper module power, GPU memory power는
세대별 시간 의미와 measurement scope가 달라 final numerator가 아니라
metadata, sanity check, 또는 fallback/provisional 용도다.
```

이 값들은 순수 회로 에너지나 transistor-level energy가 아니다. 본 저장소의
결과는 CUDA microbenchmark의 treatment-control 차분 energy를 NCU counter로
검증된 FLOP/byte denominator로 나눈 effective microbenchmark coefficient다.

## 공식 근거

| 공식 문서 | 이 실험에서 가져온 기준 |
|---|---|
| NVIDIA NVML device queries: <https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html> | `nvmlDeviceGetTotalEnergyConsumption`, `nvmlDeviceGetPowerUsage` 의미와 세대별 power sample semantics |
| NVIDIA NVML field value enums: <https://docs.nvidia.com/deploy/nvml-api/group__nvmlFieldValueEnums.html> | `NVML_FI_DEV_POWER_INSTANT`, `NVML_FI_DEV_POWER_AVERAGE` field 존재 |
| NVIDIA NVML field value queries: <https://docs.nvidia.com/deploy/nvml-api/group__nvmlFieldValueQueries.html> | field API 조회 방식 |
| NVIDIA nvidia-smi manual: <https://docs.nvidia.com/deploy/nvidia-smi/index.html#gpu-power-readings> | GPU power readings, Module Power Readings, GPU Memory Power Readings 의미 |
| NVIDIA NVML change log: <https://docs.nvidia.com/deploy/nvml-api/change-log.html> | power/energy v2 API 존재 여부 확인 |

공식 문서에서 중요한 차이는 `nvmlDeviceGetPowerUsage`다. GA100과 그 이전
architecture에서는 instantaneous power로 해석하고, GA100을 제외한 Ampere 이상은
최근 1초 평균 power로 해석한다. 따라서 V100/GV100과 A100/GA100은 `instant`,
RTX 3090/GA102와 H100/GH100은 `one_sec_average` profile로 기록한다.

또 하나의 핵심 근거는 `nvmlDeviceGetTotalEnergyConsumption`이다. NVIDIA NVML
문서는 이 API가 driver reload 이후의 GPU total energy consumption을 mJ 단위로
반환하며, Volta 이상 fully supported device에서 제공된다고 설명한다. 따라서 본
저장소의 최종 numerator는 power sample을 시간 적분한 값이 아니라 이 mJ counter의
전후 차분이다. nvidia-smi 문서는 `Average Power Draw`가 "last second" 평균이며
Ampere 중 GA100을 제외한 장치에서 지원된다고 설명하고, Hopper 이상 datacenter
제품에는 `Module Power Readings`, GPU memory subsystem power readings가 별도로
있다고 설명한다. 이 때문에 module/memory power field는 preflight metadata로만
남기고 component pJ 계산 분자로 섞지 않는다.

## 실험 전 1페이지 판정표

Power 측정값은 이름이 비슷해도 세대별로 시간 의미와 포함 범위가 다르다. 새
플랫폼에서 실험을 시작하기 전에는 아래 네 단계를 순서대로 확인한다.

| 단계 | 질문 | 확인 위치 | final 후보 조건 |
|---|---|---|---|
| 1. API visibility | 이 GPU/driver/OS에서 어떤 API가 실제로 성공했는가? | preflight, raw CSV의 `nvml_total_energy_supported`, field support columns | total-energy counter가 성공해야 final 후보 |
| 2. time semantics | fallback power sample이 instantaneous인가, 1초 평균인가? | `nvml_power_usage_semantics` | profile 기대값과 일치해야 함 |
| 3. measurement scope | 값이 GPU/device, module, GPU memory 중 어느 범위인가? | raw CSV `measurement_scope`, preflight `Power Scope` | `gpu_device_total_energy_counter`만 final 후보 |
| 4. numerator eligibility | matched-control `delta_E` 분자로 쓸 수 있는가? | power API audit status | `final_candidate`만 coefficient 표에 포함 |

현재 repository의 final component coefficient에서 허용하는 energy numerator는 아래
조합으로 제한한다.

```text
nvml_total_energy_supported=true
energy_source=nvml_total_energy
energy_integration_method=total_energy_mj_delta
measurement_scope=gpu_device_total_energy_counter
```

API/scope가 맞아도 raw row 내부의 counter evidence가 깨져 있으면 final 후보가 아니다.
package audit는 아래 row-level sanity도 함께 확인한다.

| raw CSV field | final 후보 조건 | 실패 시 의미 |
|---|---|---|
| `elapsed_s` | `> 0` | kernel/run 구간 시간이 기록되지 않았거나 실행 실패 가능성 |
| `ITER` | `> 0` | denominator 계산에 필요한 반복 수가 없거나 잘못됨 |
| `E_before_mJ`, `E_after_mJ` | 둘 다 양수이고 `E_after_mJ > E_before_mJ` | total-energy counter 전후 차분이 성립하지 않음 |
| `delta_E_J` | `> 0` | energy numerator가 0/음수라 pJ 계산 불가 |
| `delta_E_J` vs counter delta | `delta_E_J ~= (E_after_mJ - E_before_mJ) / 1000` | CSV에 기록된 energy delta와 NVML counter 전후값이 불일치 |
| `idle_baseline_J`, `net_E_J` | 음수가 아니어야 함 | idle 보정 또는 run 품질이 깨졌을 가능성 |

아래 값들은 실험 조건 확인과 failure diagnosis에는 유용하지만 final numerator가
아니다.

| 값 | 왜 final numerator가 아닌가? |
|---|---|
| `nvmlDeviceGetPowerUsage` endpoint 적분 | 세대별로 instant/1초 평균 의미가 다르고, endpoint 두 점이 kernel 구간 전체를 대표하지 못한다 |
| `power.draw.average`, `power.draw.instant` | nvidia-smi field 노출과 sampling window가 driver/SKU/OS별로 다르다 |
| H100/HGX module power | GPU 외 module 구성요소가 포함될 수 있어 GPU component denominator와 scope가 다르다 |
| GPU memory power | memory subsystem power이지 L1/L2/DRAM traffic counter와 같은 계층의 energy가 아니다 |

## 빠른 결론: 세대별 Power API 해석

| GPU/profile | `GetPowerUsage` 의미 | final에 쓸 수 있는 값 | 가장 흔한 오류 |
|---|---|---|---|
| RTX 3090 / GA102 / `rtx3090` | 1초 평균 | total-energy mJ counter delta가 성공한 row | 1초 평균 endpoint power를 짧은 microbenchmark energy로 적분 |
| V100 / GV100 / `v100` | instantaneous | total-energy mJ counter delta + GV100 NCU accepted row | 최신 NCU가 GV100 counter를 못 읽는데 coefficient로 확정 |
| A100 / GA100 / `a100` | instantaneous. GA100은 Ampere 평균-power 규칙의 예외 | total-energy mJ counter delta + A100 capacity/active SM 재설정 row | RTX 3090의 SM/L2/shared 좌표 또는 `one_sec_average` semantics 혼입 |
| H100 / GH100 / `h100` | 1초 평균 | GPU/device total-energy mJ counter delta | module power 또는 GPU memory power를 component numerator로 사용 |

이 표에서 "쓸 수 있는 값"은 API 이름만으로 결정하지 않는다. raw CSV의
`energy_source`, `energy_integration_method`, `measurement_scope`,
`nvml_total_energy_supported`, `nvml_power_usage_semantics`와 power API audit 결과가
최종 판정을 결정한다.

## API 사용 등급

| 등급 | 허용 경로 | 의미 | 실험에서의 처리 |
|---|---|---|---|
| final numerator | `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | GPU/device total energy counter delta | matched-control `delta_E`의 분자로 사용 가능 |
| provisional/fallback | `nvmlDeviceGetPowerUsage` endpoint 적분 | V100/A100은 instant, RTX 3090/H100은 1초 평균 power sample | smoke, sanity, 원인 분석용. final 표와 분리 |
| metadata/diagnostic | `power.draw.*`, `NVML_FI_DEV_POWER_INSTANT`, `NVML_FI_DEV_POWER_AVERAGE` | nvidia-smi/NVML field power sample | power-state audit, preflight, field 지원 여부 기록 |
| non-numerator scope | Hopper module power, GPU memory power | GPU/device보다 넓거나 memory subsystem에 한정된 scope | H100/HGX metadata. component pJ 분자로 사용 금지 |

## 현재 코드의 API 호출과 CSV 필드 매핑

현재 harness는 [src/nvml_energy.cpp](../../src/nvml_energy.cpp) 기준으로 NVML v1
API를 호출한다. 따라서 문서와 보고서도 아래 CSV 필드를 기준으로 해석해야 한다.

| 현재 harness 호출 | 결과 CSV 의미 | final 사용 |
|---|---|---|
| `nvmlDeviceGetTotalEnergyConsumption` | `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, `measurement_scope=gpu_device_total_energy_counter` | final 후보 |
| `nvmlDeviceGetPowerUsage` | `energy_source=legacy_get_power_usage_integral`, `energy_integration_method=endpoint_power_trapezoid`, `measurement_scope=gpu_device_power_usage_fallback` | provisional/fallback |
| `nvmlDeviceGetFieldValues` + `NVML_FI_DEV_POWER_INSTANT` | `nvml_field_power_instant_supported`, optional instant value in notes | metadata |
| `nvmlDeviceGetFieldValues` + `NVML_FI_DEV_POWER_AVERAGE` | `nvml_field_power_average_supported`, optional average value in notes | metadata |

`power_before_mw`와 `power_after_mw`가 raw CSV에 있더라도, total-energy row에서는 이
두 값을 pJ 계산 분자로 쓰지 않는다. 최종 pJ/FLOP 또는 pJ/bit의 분자는
`total_energy_mj_delta` 기반 matched-control `delta_E`다.

## NVML v2 API와 현재 harness 범위

NVML 문서에는 `nvmlDeviceGetPowerUsage_v2`,
`nvmlDeviceGetTotalEnergyConsumption_v2` 같은 v2 API가 추가되어 있다. 이것은
"새 드라이버에서 더 많은 power/energy query entry point가 있을 수 있다"는 뜻이지,
본 저장소의 기존 raw CSV가 자동으로 v2 의미를 갖는다는 뜻은 아니다.

향후 v2 API를 코드에 넣는다면 아래 원칙을 따른다.

| 변경 사항 | 필요한 metadata | 이유 |
|---|---|---|
| v1 total-energy에서 v2 total-energy로 변경 | `energy_api_version=v2` 또는 `energy_source=nvml_total_energy_v2` | v1/v2 지원 범위와 반환 구조가 다를 수 있으므로 비교 가능성을 명시 |
| v1 power usage에서 v2 power usage로 변경 | sample semantics, averaging window, scope를 CSV에 기록 | power sample은 세대별 의미가 달라 coefficient에 직접 쓰기 어렵다 |
| v1/v2 row가 섞인 raw CSV | run class를 분리하거나 audit에서 reject | 같은 component coefficient의 numerator가 서로 다른 API가 되면 차분/회귀가 불안정 |

현재 RTX 3090 strict 결과와 A100/V100/H100 실행 가이드는 "NVML v1 total-energy
counter delta 기반"으로 해석한다.

## API 사용 가능성과 final 채택 가능성은 다르다

세대별 API 차이에서 가장 자주 생기는 실수는 "보이는 값"을 곧바로 component
coefficient 분자로 쓰는 것이다. 본 저장소의 판정은 아래처럼 분리한다.

| 구분 | 질문 | 예 | coefficient 채택 |
|---|---|---|---|
| API support | 이 GPU/driver에서 호출이 성공하는가? | `nvmlDeviceGetTotalEnergyConsumption`이 `NVML_SUCCESS`인지 | 성공만으로는 부족하다 |
| sample semantics | 값이 어떤 시간 의미를 갖는가? | `GetPowerUsage`가 instant인지 1초 평균인지 | fallback 해석에만 사용 |
| measurement scope | 값이 GPU/device, module, memory 중 무엇을 포함하는가? | H100 `module.power.draw.average` vs GPU power | GPU/device total-energy 외 scope는 final 제외 |
| numerator eligibility | matched-control 분자로 쓸 수 있는가? | `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta` | 이 조건을 만족해야 final 후보 |
| path denominator | NCU가 의도한 bytes/FLOP를 확인했는가? | L1 hit, L2 hit, DRAM bytes, Tensor op | NCU rejected면 energy API가 좋아도 final 제외 |

Raw CSV에서는 아래 필드 조합으로 이 구분을 기계적으로 확인한다.

| CSV field | final 후보에서 기대하는 값 | 이탈 시 해석 |
|---|---|---|
| `nvml_total_energy_supported` | `true` | false이면 total-energy counter를 쓰지 못한 run이다 |
| `energy_source` | `nvml_total_energy` | `legacy_get_power_usage_integral`이면 fallback/provisional |
| `energy_integration_method` | `total_energy_mj_delta` | `endpoint_power_trapezoid`이면 endpoint power 적분이다 |
| `measurement_scope` | `gpu_device_total_energy_counter` | fallback, module, memory, unknown scope는 final coefficient에서 제외 |
| `nvml_power_usage_semantics` | profile 기대값과 일치 | profile 혼입 또는 잘못된 platform 설정 가능성 |
| `power_sample_count` | final 판정의 핵심 아님 | fallback일 때 1-2개 sample이면 특히 위험 |
| `power_before_mw`, `power_after_mw` | metadata | total-energy row에서도 pJ 계산 분자로 직접 쓰지 않는다 |

## 세대별 API 의미가 실험 설계에 주는 직접 영향

| GPU | API 의미 차이 | 실험 설계 영향 | 결과 보고 문구 |
|---|---|---|---|
| RTX 3090 / GA102 | `GetPowerUsage` fallback은 1초 평균이다. GeForce/WSL에서는 field 노출이 driver 의존적이다. | 10-30초 이상 측정하고, final은 total-energy delta row만 사용한다. fallback row는 실험 실패 원인 분석용이다. | "RTX 3090 fallback power는 1초 평균이므로 endpoint 적분값을 final coefficient로 쓰지 않았다." |
| V100 / GV100 | `GetPowerUsage` fallback은 instantaneous다. total-energy counter는 Volta 이상 조건상 기대되지만 runtime 확인이 필요하다. | instant endpoint 두 점은 noise에 취약하므로 fallback이면 반복을 늘려도 final이 아니라 provisional이다. | "V100 total-energy delta가 확보된 row만 final 후보로 보았다." |
| A100 / GA100 | Ampere지만 GA100은 `GetPowerUsage`가 instantaneous인 예외다. MIG/full GPU 상태가 power/SM/L2 해석에 영향을 준다. | RTX 3090 좌표를 그대로 쓰지 않고 A100 active SM, 40 MiB L2, 164 KiB shared allocation에 맞춰 다시 계획한다. | "A100은 GA100 예외로 power sample semantics가 instant이며, final numerator는 total-energy delta다." |
| H100 / GH100 | `GetPowerUsage` fallback은 1초 평균이고, GPU/module/memory power scope가 함께 보일 수 있다. | module/memory power를 component coefficient 분자로 섞지 않는다. H100-native WGMMA/TMA/FP8은 별도 kernel이 필요하다. | "H100 module/memory power는 metadata로만 보고, GPU/device total-energy delta만 final 후보로 사용했다." |

## 0.A.4.1 플랫폼별 보고서에 넣을 Power API availability 표

새 플랫폼 보고서에는 아래 표를 채워 넣는다. 이 표가 없으면 component coefficient의
분자가 어떤 scope와 API에서 왔는지 독자가 확인할 수 없다.

| 항목 | 보고 값 | 예시/기대 |
|---|---|---|
| GPU / chip / profile | GPU 이름, chip, `target_profile` | `A100 / GA100 / a100` |
| driver / NVML version | driver와 NVML 버전 | preflight 또는 `nvidia-smi` 결과 |
| OS / driver mode | Linux bare-metal, WSL, WDDM/TCC 등 | GeForce/WSL은 field 노출 차이 기록 |
| total energy counter | 지원 여부와 raw CSV 값 | `nvml_total_energy_supported=true` |
| selected numerator | 최종 pJ 계산에 사용한 분자 | `nvml_total_energy` + `total_energy_mj_delta` |
| fallback power semantics | profile 기대값 | V100/A100 `instant`, RTX 3090/H100 `one_sec_average` |
| nvidia-smi power fields | `power.draw`, `power.draw.average`, `power.draw.instant` 노출 여부 | metadata only |
| measurement scope | raw CSV의 명시 scope | `gpu_device_total_energy_counter` |
| module/memory power scope | H100/HGX에서 보이면 별도 기록 | final numerator와 분리 |
| power limit / clocks / temp | W, MHz, Celsius | power-state audit 입력 |
| final 판정 | final/provisional/reject | power API audit 결과 |

보고서에는 다음 문장을 함께 넣는다.

```text
본 coefficient의 energy numerator는 NVML GPU/device total-energy counter의 전후 mJ
차분이다. GetPowerUsage, power.draw.*, H100 module power, GPU memory power는
세대별 시간 의미와 scope가 달라 final numerator로 사용하지 않았다.
```

## 0.A.5 세대별 failure pattern과 수정 지시

새 플랫폼 결과가 나쁠 때는 coefficient 값부터 비교하지 말고 power API/scope가 맞는지
먼저 본다. 아래 패턴 중 하나라도 있으면 NCU hit rate가 좋아도 final coefficient로
채택하지 않는다.

| 플랫폼 | 관찰되는 문제 | 왜 문제가 되는가 | 수정 지시 |
|---|---|---|---|
| RTX 3090 / GA102 | `energy_source=legacy_get_power_usage_integral` | 1초 평균 power endpoint 적분은 treatment/control kernel 구간을 정확히 대표하지 못한다 | total-energy counter가 나오는 driver/환경에서 재측정하거나 provisional로 분리 |
| RTX 3090 / WSL | `nvml_total_energy_supported=false`, `power.draw.*` field 일부 missing | GeForce/WSL/driver 조합에서 NVML field 노출이 달라질 수 있다 | WSL/NVIDIA driver 상태를 preflight에 남기고 final 표에서는 제외 |
| V100 / GV100 | `nvml_power_usage_semantics=one_sec_average` | V100 profile 기대값은 `instant`이므로 profile 또는 CSV 혼입 가능성이 높다 | `--target-profile v100`, `sm_70`, raw CSV profile을 확인 후 재실행 |
| V100 / GV100 | NCU `gv100` query 실패 | denominator/path 검증이 안 되므로 pJ/bit path claim을 할 수 없다 | GV100 지원 Nsight Compute를 지정하거나 NCU 미검증으로 분리 |
| A100 / GA100 | `nvml_power_usage_semantics=one_sec_average` | GA100은 Ampere 예외로 instant semantics다 | `--target-profile a100` 및 plan script profile을 확인 |
| A100 / GA100 | RTX 3090 `active_SM=82`, L2 6 MiB 좌표가 섞임 | A100의 108 SM, 40 MiB L2, 164 KiB shared allocation을 쓰지 않은 결과다 | A100 guide 기준 W_SM/blocks/SM을 다시 생성 |
| A100 MIG | runtime SM 수가 full 108과 다름 | energy numerator는 visible partition 상태의 GPU telemetry이고 denominator도 active SM에 의존한다 | MIG/full GPU 상태, visible SM 수, UUID를 보고서에 명시하고 `--active-sm` 조정 |
| H100 / GH100 | module power 또는 GPU memory power를 pJ/bit 분자로 사용 | module/memory scope가 GPU/device total energy와 다르다 | module/memory power는 preflight metadata로만 두고 GPU/device total-energy row로 재분석 |
| H100 / GH100 | power smoothing/profile 설정이 run마다 다름 | 같은 microbenchmark라도 power response와 평균 전력이 달라질 수 있다 | `nvidia-smi -q -d POWER` excerpt를 함께 저장하고 설정별 결과를 분리 |

## 같은 GPU라도 run마다 달라질 수 있는 조건

| 조건 | 왜 분리해야 하는가 | 보고서 표기 |
|---|---|---|
| driver/NVML version | field support와 sampling 동작이 달라질 수 있음 | `driver_version`, `nvml_version` |
| WDDM/TCC/WSL/리눅스 bare-metal | GeForce/WSL에서는 NVML field와 profiling 권한이 달라질 수 있음 | OS/driver mode, WSL 여부 |
| power limit / application clocks | treatment-control delta가 clock/power cap에 민감함 | `power.limit`, `clocks.sm`, `clocks.mem` |
| ECC / MIG / partition | available SM, memory behavior, telemetry scope가 바뀔 수 있음 | ECC, MIG mode, UUID, active SM |
| temperature / throttling | 반복 row의 평균 power와 elapsed time이 흔들림 | `temp_C`, power-state audit |
| NCU attached vs detached | profiler replay가 runtime power 측정을 왜곡할 수 있음 | energy run과 NCU sidecar 분리 여부 |

## 0.C 새 플랫폼 결과를 받을 때의 판정 흐름

새로운 RTX 3090, V100, A100, H100 결과를 받으면 아래 순서로 판정한다.

```text
GPU 이름과 profile 확인
→ raw CSV의 nvml_total_energy_supported 확인
→ energy_source와 energy_integration_method 확인
→ nvml_power_usage_semantics가 profile 기대값과 같은지 확인
→ measurement_scope가 gpu_device_total_energy_counter인지 확인
→ clock/temp/power-limit outlier를 power-state audit으로 확인
→ NCU path accepted와 denominator 확인
→ pJ/FLOP 또는 pJ/bit coefficient 채택
```

| 상태 | 조건 | 보고 방식 |
|---|---|---|
| `final_candidate` | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, profile semantics 일치, `measurement_scope=gpu_device_total_energy_counter` | component coefficient 표에 포함 가능 |
| `provisional` | total energy counter가 없고 `GetPowerUsage` 또는 `power.draw.*` 기반 fallback만 있음 | fallback 표로 분리. 세대별 sample 의미와 측정 시간을 명시 |
| `reject for coefficient` | source 혼합, profile semantics 불일치, module/memory power를 GPU numerator로 사용, NCU rejected | 최종 pJ/FLOP 또는 pJ/bit 계산에서 제외 |

Power API gate는 NCU path 검증을 대체하지 않는다. energy numerator가 final 후보여도
NCU에서 L1/L2/DRAM path가 rejected이면 component coefficient로 채택하지 않는다.

## 0.D RTX 3090 strict measurement-scope 적용 예시

2026-07-08 새 binary 기준으로 raw CSV에 `measurement_scope`가 직접 기록되는 strict
rerun을 수행했다. 이 run은 기존 inferred-scope row와 분리하며,
`--require-explicit-measurement-scope` audit을 통과한 결과만 사용한다.

![RTX 3090 strict measurement-scope coefficients](../assets/component_energy_method/rtx3090_strict_scope_component_coefficients.svg)

| Component/path | energy numerator | measurement scope | power semantics | median | unit | reliability | 해석 |
|---|---|---|---|---:|---|---|---|
| Tensor MMA incremental | `nvml_total_energy` + `total_energy_mj_delta` | `gpu_device_total_energy_counter` | `one_sec_average` | 0.129216 | pJ/FLOP | `accepted` | strict energy numerator 기준 Tensor 후보 |
| Shared scalar path | `nvml_total_energy` + `total_energy_mj_delta` | `gpu_device_total_energy_counter` | `one_sec_average` | 0.170590 | pJ/bit | `accepted` | LR8-only strict follow-up. LR4/LR8 calibrated 0.161 pJ/bit는 보조 근거 |
| Global L1 hit path | `nvml_total_energy` + `total_energy_mj_delta` | `gpu_device_total_energy_counter` | `one_sec_average` | 0.173483 | pJ/bit | `accepted` | LR4-only follow-up으로 LR8 weak-signal row를 분리 |
| L2 CG hit path | `nvml_total_energy` + `total_energy_mj_delta` | `gpu_device_total_energy_counter` | `one_sec_average` | 1.131073 | pJ/bit | `accepted` | strict+fresh NCU 기준에서도 L1 < L2 계층 순서와 정합 |

상세 결과는
[rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md)에
정리했다. fresh NCU reliability audit은
[rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md)이고,
4개 component가 모두 `accepted`다. 이 예시는 RTX 3090의 `GetPowerUsage` fallback
의미가 `one_sec_average`여도, 최종 coefficient의 분자는 endpoint power 적분이 아니라
total-energy counter delta여야 한다는 점을 보여준다. 새 플랫폼 결과는 반드시 해당
GPU에서 새 NCU sidecar까지 다시 수집해야 한다.

## Power API audit 실행

Energy sweep 직후에는 NCU보다 먼저 power API audit을 실행한다.

```bash
python3 scripts/audit_power_api_measurements.py \
  results/raw/your_tensor.csv \
  results/raw/your_shared.csv \
  results/raw/your_l1.csv \
  results/raw/your_l2.csv \
  results/raw/your_dram.csv \
  --target-profile a100 \
  --out-csv results/summary/your_power_api_audit.csv \
  --out-md results/summary/your_power_api_audit.md \
  --fail-on-reject \
  --fail-on-provisional \
  --require-explicit-measurement-scope
```

Profile별 expected semantics:

| profile | expected `nvml_power_usage_semantics` |
|---|---|
| `rtx3090` | `one_sec_average` |
| `v100` | `instant` |
| `a100` | `instant` |
| `h100` | `one_sec_average` |

Audit가 `provisional` 또는 `reject`를 내면 NCU 결과가 좋아도 final coefficient로 쓰지
않는다. 새 finalplan run에서는 `--require-explicit-measurement-scope`를 사용해 raw
CSV에 `measurement_scope`가 직접 기록되었는지 확인한다.

## 보고서에 남겨야 하는 metadata

| 항목 | 단위/값 | 왜 필요한가 |
|---|---|---|
| GPU name, chip, compute capability | string, CC | power semantics와 NCU counter set이 다름 |
| driver version, NVML version | string | API field 노출과 counter support가 driver에 따라 다를 수 있음 |
| `energy_source` | string | total energy counter인지 fallback power 적분인지 구분 |
| `energy_integration_method` | string | `total_energy_mj_delta`와 `endpoint_power_trapezoid`를 구분 |
| `nvml_total_energy_supported` | boolean | final numerator 채택 가능성 판단 |
| `nvml_power_usage_semantics` | `instant` 또는 `one_sec_average` | fallback power sample의 시간 의미 판단 |
| `measurement_scope` | string | GPU/device total energy인지, fallback인지, module/memory scope인지 구분 |
| `seconds`, `repeats` | s, count | telemetry window와 noise floor 평가 |
| `power_before_mw`, `power_after_mw` | mW | endpoint sanity와 power-state audit 입력 |
| clock, temperature, power limit | MHz, Celsius, W/mW | drift, throttling, power cap 영향 확인 |
| NCU path verdict | accepted/rejected | denominator/path가 의도대로인지 확인 |

## 결과 해석 문구

결과 보고서의 measurement method 또는 limitations에는 아래 내용을 포함한다.

```text
본 실험의 energy numerator는 NVML GPU-level/board-level telemetry에서 얻은 값이다.
GPU 세대별로 total energy counter 지원 여부와 GetPowerUsage의 instant/1초 평균
의미가 다르므로, 모든 coefficient는 energy_source, integration method, measurement
scope, 측정 시간, 반복 횟수, clock/power-limit 상태와 함께 해석한다. 이 값은 순수
silicon-level component energy가 아니라 workload-dependent effective
microbenchmark coefficient다.
```

잘못된 표현과 대체 표현:

| 피해야 할 표현 | 왜 문제인가 | 대신 쓸 표현 |
|---|---|---|
| "NVML로 Tensor Core 회로 에너지를 직접 측정했다" | NVML은 GPU/device 또는 board-level telemetry다 | "Tensor microbenchmark의 matched-control effective coefficient를 추정했다" |
| "`power.draw`를 적분해서 final pJ/bit를 계산했다" | `power.draw` 의미와 sampling window가 chip별로 다르다 | "total energy mJ counter가 없으면 fallback/provisional로만 보고했다" |
| "H100 module power를 GPU component numerator로 썼다" | module power는 GPU 외 구성요소를 포함할 수 있다 | "GPU/device energy와 module/memory power를 분리해 기록했다" |
| "GPU memory power = DRAM path pJ/bit" | memory subsystem power와 kernel DRAM traffic denominator는 같은 레벨이 아니다 | "HBM/DRAM sanity metadata로만 사용했다" |

## 다른 문서와의 연결

| 목적 | 문서 |
|---|---|
| 전체 실험 구조와 mode 의미 | [howitworks.md](../methodology/howitworks.md) |
| finalplan 조건, sweep, 채택/제외 기준 | [component_energy_final_experiment_plan_ko.md](../methodology/component_energy_final_experiment_plan_ko.md) |
| NCU counter 검증과 pJ/FLOP, pJ/byte, pJ/bit 계산 | [ncu_validation_energy_calculation_ko.md](../methodology/ncu_validation_energy_calculation_ko.md) |
| A100/V100/H100 공통 실행 절차 | [cross_platform_component_experiment_guide_ko.md](cross_platform_component_experiment_guide_ko.md) |
| 플랫폼별 실행 가이드 | [a100_node_experiment_guide_ko.md](a100_node_experiment_guide_ko.md), [v100_node_experiment_guide_ko.md](v100_node_experiment_guide_ko.md), [h100_node_experiment_guide_ko.md](h100_node_experiment_guide_ko.md) |
