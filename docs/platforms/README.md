# Platform Guide Index

작성일: 2026-07-08, updated 2026-07-14

이 문서는 RTX 3090, V100, A100, H100에서 component-energy finalplan 실험을 실행할 때 먼저 확인해야 하는 플랫폼 차이를 정리한다. 구현 전 계획 문서였던 `multi_gpu_support_plan_ko.md`의 핵심은 이 문서와 각 플랫폼 가이드에 반영했고, 원문은 `archive/legacy_20260707/docs/multi_gpu_support_plan_ko.md`에 보관한다.

## 공통 원칙

| 원칙 | 이유 |
|---|---|
| `--target-profile auto` 또는 명시 profile을 기록 | GPU 이름만으로 SM/L2/shared/NVML 의미를 가정하면 안 됨. Final command package preflight는 명시 profile과 `--strict`를 사용 |
| energy run과 NCU sidecar를 분리 | NCU replay가 board-level energy 측정을 왜곡할 수 있음 |
| pJ/bit는 NCU actual traffic denominator 사용 | static expected bytes만으로 L1/L2/DRAM path를 확정할 수 없음 |
| 결과에는 단위와 mode 의미를 항상 표기 | pJ/FLOP, pJ/byte, pJ/bit를 섞어 읽는 오류 방지 |
| archive 결과를 final coefficient로 재사용하지 않음 | 초기 sweep은 후보 탐색이지 현재 수치의 직접 입력이 아님 |

## 플랫폼별 문서

| GPU | 문서 | 목적 |
|---|---|---|
| 공통 | `docs/platforms/cross_platform_component_experiment_guide_ko.md` | 모든 플랫폼의 공통 finalplan 절차와 해석 기준 |
| RTX/A100/V100 비교 | `docs/platforms/cross_platform_component_experiment_guide_ko.md` 4.0-4.5절 | 실험 파라미터, 유효/제외 좌표, energy raw row 수, NCU case 수, strict 좌표 비교 |
| Power API | `docs/platforms/power_measurement_api_matrix_ko.md` | GPU 세대별 NVML/nvidia-smi power/energy API 의미와 제약 |
| Readiness audit | `results/summary/platform_power_readiness_audit_20260708.md` | RTX 3090/V100/A100/H100 profile, power API, 문서, 생성 command plan 정합성 점검 결과 |
| A100 | `docs/platforms/a100_node_experiment_guide_ko.md` | A100/GA100 profile, 40 MiB L2, HBM 계열 실험 절차 |
| V100 | `docs/platforms/v100_node_experiment_guide_ko.md` | V100/GV100 profile, CUDA 12.x `compute_70`/Volta NCU toolchain 주의, 실행 절차 |
| V100 L2 audit | `docs/audits/v100_l2_iter_mismatch_remediation_ko.md` | NCU path 성공과 energy 작업량 실패를 분리하고 동일-ITER 재실험 정책 기록 |
| H100 | `docs/platforms/h100_node_experiment_guide_ko.md` | H100/GH100 profile, Hopper에서 WMMA path 해석 주의 |
| V100 prompt | `docs/platforms/prompts/v100_experiment_prompt_ko.md` | 다른 작업자/에이전트에게 V100 실험을 전달할 때 쓰는 프롬프트 |

## Generated Command Packages

아래 파일은 각 플랫폼에서 바로 검토 후 실행할 수 있도록 생성해 둔 finalplan command
package다. 실제 측정 결과가 아니라 실행 계획이므로, target node에서 실행한 뒤 goal
readiness audit으로 결과 패키지를 다시 검증한다.

각 command package는 profile별 CUDA arch와 binary path를 고정한다. 기본 `build`
디렉터리는 RTX 3090/sm_86 로컬 실험용이므로, A100/V100/H100 결과를 만들 때 그대로
쓰면 profile 혼입으로 보고 final coefficient에서 제외한다.

| GPU | command plan | executable shell | result manifest |
|---|---|---|---|
| A100 | `results/summary/a100_component_finalplan_20260708_command_plan.md` | `results/summary/a100_component_finalplan_20260708_commands.sh` | `results/summary/a100_component_finalplan_20260708_result_manifest.md` |
| V100 | `results/summary/v100_component_finalplan_20260708_command_plan.md` | `results/summary/v100_component_finalplan_20260708_commands.sh` | `results/summary/v100_component_finalplan_20260708_result_manifest.md` |
| H100 | `results/summary/h100_component_finalplan_20260708_command_plan.md` | `results/summary/h100_component_finalplan_20260708_commands.sh` | `results/summary/h100_component_finalplan_20260708_result_manifest.md` |

| profile | CUDA arch | required build command | generated binary path |
|---|---:|---|---|
| `v100` | 70 | `cmake -S . -B build-v100 -DCMAKE_CUDA_ARCHITECTURES=70` | `./build-v100/a100_fp16_energy_v2` |
| `a100` | 80 | `cmake -S . -B build-a100 -DCMAKE_CUDA_ARCHITECTURES=80` | `./build-a100/a100_fp16_energy_v2` |
| `h100` | 90 | `cmake -S . -B build-h100 -DCMAKE_CUDA_ARCHITECTURES=90` | `./build-h100/a100_fp16_energy_v2` |

`scripts/plan_platform_component_experiment.py`에서 `--binary`를 생략하면 위 profile별
기본 경로를 사용한다. command plan의 `Build Requirement`, shell의 `--binary`, NCU
sidecar의 `BIN=...` 값이 서로 같아야 한다.

V100 package는 일반 energy `blocks/SM=4,16,32`와 Shared/Global-L1 strict NCU B32를
분리한다. L2는 energy 전에 normal contiguous B32와 sm-interleaved B32/B16/B4를
W32/W64에서 검사하고 첫 strict-pass B만 energy/full NCU에 사용한다. V100 CC 7.0에는
persisting-L2 policy를 사용하지 않는다. Generated NCU command는 `NCU_CHIP=gv100`으로
metric availability를 확인하고, 필수 counter가 빠지면 acceptance에서 reject한다.
L2 energy pair는 W/B/LR별 `l2_cg_load_only`와 `global_addr_only`를 dual-calibrate한 뒤
동일 resolved ITER를 사용한다. `*_l2_pair_calibration.csv`, raw ITER equality,
`pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1`이 package 필수 증거다.

V100 build는 CUDA 13 `nvcc`를 사용할 수 없다. CUDA 12.x compiler를 권장하며
`nvcc --list-gpu-arch`에 `compute_70`이 있어야 strict preflight가 통과한다. CUDA
compiler와 NCU는 독립 toolchain이므로 각각 `NVCC`와 `NCU_BIN`으로 지정한다.

## Architecture 차이 체크리스트

| 항목 | RTX 3090 | V100 | A100 | H100 |
|---|---|---|---|---|
| profile | `rtx3090` | `v100` | `a100` | `h100` |
| architecture | Ampere GA102 | Volta GV100 | Ampere GA100 | Hopper GH100 |
| typical CC | 8.6 | 7.0 | 8.0 | 9.0 |
| default SM count in profile | 82 | 80 | 108 | 132, runtime/SKU 확인 필요 |
| nominal L2 | 6 MiB | 6 MiB | 40 MiB | 50 MiB |
| SM-local L1/shared | 128 KiB/SM combined | 128 KiB/SM combined | 192 KiB/SM combined | 256 KiB/SM combined |
| max CUDA shared allocation used by profile | 100 KiB/SM class | 96 KiB/SM class | 164 KiB/SM class | 228 KiB/SM class |
| memory type | GDDR6X | HBM2 | HBM2e | HBM3/HBM 계열 |
| Tensor path in current code | WMMA FP16 | WMMA FP16 | WMMA FP16 | WMMA compatibility FP16, not WGMMA/FP8 |
| build toolchain gate | `compute_86` 지원 nvcc | CUDA 12.x 권장, `compute_70` 필수; CUDA 13 불가 | `compute_80` 지원 nvcc | `compute_90` 지원 nvcc |
| NCU caveat | GA10x metrics | recent NCU may drop GV100 support | GA100 metrics | Hopper metrics, WGMMA/TMA not primary code path |
| NVML power caveat | power usage may be 1 s averaged | usually instantaneous semantics | usually instantaneous semantics | may be 1 s averaged |

위 표는 실험 planning 기준이다. 실제 보고서에는 preflight가 기록한 `gpu_name`, `compute_capability`, `SM count`, `L2`, `shared limit`, CUDA target support, `NVML power semantics`, `NCU chip support`를 우선한다. Power/energy API의 세대별 의미는 `docs/platforms/power_measurement_api_matrix_ko.md`를 기준으로 기록한다.

현재 표준 package의 빠른 규모 비교는 다음과 같다. 전체 계산식과 component별 분해는
[cross-platform guide](cross_platform_component_experiment_guide_ko.md)의 4.0-4.5절을
기준으로 하며, 아래 raw row 수는 schema/revision smoke 3행과 NCU sidecar를 포함하지 않는다.

| GPU | energy blocks/SM | 유효 좌표/1 repeat | energy raw rows (`repeats=5`) | Tensor calibration coordinates / commands | L2 calibration coordinates / commands | primary NCU cases | 상태 |
|---|---|---:|---:|---:|---:|---:|---|
| RTX 3090 | 8,16 | 86 count | 430 rows | 10 / 20 | 6 / 12 | 44 cases | 기존 accepted 결과는 별도 B16 targeted package |
| A100 | general 16,32; L2 selected B16/8/4 | 98 count | 490 rows | 10 / 20 | 12 / 24 | 74 cases + up to 32 precheck | W16/W128 selector 통과 필요 |
| V100 | general 4,16,32; L2 selected B32/16/4 | 132 count | 660 rows | 15 / 30 | 6 / 12 | 54 cases + up to 16 precheck | W32/W64 selector 통과 필요 |

새 플랫폼 결과를 되가져오면 `scripts/audit_platform_result_package.py`로 raw CSV의
`profile_name`, `architecture_family`, `chip`, `compute_capability`, `l2_mib`,
`unified_l1_shared_kib_per_sm`, `shared_kib_per_sm`, `active_SM`이 target profile과
일치하는지 확인한다. A100 실험인데 raw row가 RTX 3090/GA102 profile로 남아 있으면
power API나 NCU가 통과해도 component coefficient로 쓰지 않는다. MIG, partition,
SKU 차이로 runtime SM 수가 다르면 preflight 값을 기준으로 plan의 `--active-sm`과
package audit의 `--expected-active-sm`을 같은 값으로 맞춘다.
package audit는 preflight markdown의 `dry_run_active_sm`과 dry-run 출력의 chip/L2/shared
좌표도 함께 확인하므로, 실행 전 dry-run 단계의 profile 혼입도 잡아야 한다. 여러 GPU가
있는 노드에서는 preflight의 `GPU index`와 `dry_run_gpu`가 같은지 확인한다.
NCU summary도 hit rate만으로는 부족하다. V100/A100/H100 모두 `l1_hit_rate_pct`,
`l2_hit_rate_pct`와 함께 `l1_accesses`, `l2_accesses`, `dram_accesses`,
`l1_bytes`, `l2_bytes`, `dram_bytes`, `shared_bytes`를 남겨야 한다. L1 access는
request counter가 있으면 request, 없으면 sector로 기록하고, L2/DRAM access는
sector counter로 기록한다. 이 access/byte evidence가 없으면 caching path가
검증된 final coefficient로 보지 않는다.
Final result package의 preflight는 warning용 auto-detect 리포트가 아니라 명시
profile의 strict gate 리포트여야 한다. `strict=true`, `profile_gate=pass`,
`ncu_gate=pass`, `dry_run_gate=pass`, `overall=pass`, `errors=none`이 모두 기록되지
않으면, raw energy/NCU CSV가 있어도 해당 package는 final coefficient 후보가 아니다.
package audit이 `missing` 또는 `fail`을 내면
`scripts/summarize_platform_package_gaps.py`로 gap report를 만든다. 이 리포트는
실패한 stage를 preflight, raw energy, power API, NCU summary, matched-control,
strict summary 등으로 나누고, power measurement matrix 기준과 연결된 원인 및 재실행
조치를 제시한다.

## Power/Energy 측정 API 체크

세대별 Power API는 "사용 가능 여부"와 "최종 coefficient 사용 가능 여부"를
분리해서 본다. 빠른 판정은
[power_measurement_api_matrix_ko.md](power_measurement_api_matrix_ko.md)의
`실험 전 1페이지 판정표`,
`빠른 결론: 세대별 Power API 해석`,
`API 사용 등급`,
`현재 코드의 API 호출과 CSV 필드 매핑`,
`API 사용 가능성과 final 채택 가능성은 다르다`, 그리고
`0.C 새 플랫폼 결과를 받을 때의 판정 흐름`을 먼저 따른다. 새 플랫폼 보고서에는
같은 문서의 `0.A.4.1 플랫폼별 보고서에 넣을 Power API availability 표`를 반드시
채워 넣는다. RTX 3090에서
`measurement_scope`가 raw CSV에 직접 기록되고 fresh NCU sidecar로 다시 검증된 strict
rerun 예시는 같은 문서의 `0.D RTX 3090 strict measurement-scope 적용 예시`를 본다.

실험을 시작하기 전에는 같은 문서 맨 앞의 `실험 전 1페이지 판정표`를 먼저 채운다.
이 표는 API가 보이는지, 그 값의 시간 의미가 무엇인지, GPU/device scope인지, final
coefficient 분자로 쓸 수 있는지를 분리한다. 이 네 단계가 맞지 않으면 NCU hit rate가
좋아도 결과는 final이 아니라 provisional 또는 reject다.

| 항목 | 반드시 확인할 내용 |
|---|---|
| total energy counter | `nvml_total_energy_supported=true`인지 확인. 가능하면 이 값을 최종 energy numerator로 우선 사용 |
| fallback power integral | `energy_source=legacy_get_power_usage_integral`이면 endpoint power trapezoid이므로 provisional 또는 보조값으로 보고 |
| `GetPowerUsage` 의미 | V100/A100은 `instant`, RTX 3090/H100은 `one_sec_average` profile로 기록 |
| nvidia-smi power fields | `power.draw`, `power.draw.average`, `power.draw.instant` 지원 여부를 preflight에 남김 |
| Hopper module/memory power | preflight `Power Scope` 섹션에 기록하되 GPU/device coefficient numerator와 섞지 않음 |
| measurement scope | `gpu_device_total_energy_counter`, `gpu_device_power_usage_fallback`, module power, GPU memory power를 구분 |
| NVML API version | 현재 harness는 v1 `nvmlDeviceGetTotalEnergyConsumption` / `nvmlDeviceGetPowerUsage` 기준. v2 API를 도입하면 `energy_api_version` 또는 별도 `energy_source`로 v1/v2 row를 분리 |
| power smoothing/profile | Hopper 이상 datacenter 환경에서 노출될 수 있으므로 `nvidia-smi -q -d POWER` excerpt를 보관 |

새 플랫폼에서 power 값이 이상하면 coefficient 값보다 아래 네 가지를 먼저 확인한다.

| 질문 | final 후보에서 기대하는 답 |
|---|---|
| 어떤 API가 노출되었는가? | total energy counter가 성공했고, power field들은 metadata로만 남았다 |
| 그 API의 시간 의미는 무엇인가? | profile 기대값과 일치한다. V100/A100은 `instant`, RTX 3090/H100은 `one_sec_average` |
| measurement scope는 무엇인가? | `gpu_device_total_energy_counter` |
| NCU denominator와 같은 레벨인가? | energy는 GPU/device total delta, denominator는 NCU path counter임을 분리해서 보고한다 |

최종 component coefficient의 분자는 원칙적으로 `nvmlDeviceGetTotalEnergyConsumption`
전후 mJ 차분이다. `nvmlDeviceGetPowerUsage`, `power.draw.*`, H100 module power,
GPU memory power는 세대별 의미와 포함 범위가 다르므로 final numerator로 섞지 않는다.
최신 NVML에는 power/energy v2 API도 있지만, 현재 repository harness는 v1 API를
사용한다. v2 기반 결과를 추가할 경우 기존 v1 strict 결과와 같은 run class에 섞지
않고 별도 metadata와 audit 조건을 둔다.

상세 표와 보고서 문구는 `docs/platforms/power_measurement_api_matrix_ko.md`에 둔다.

세대별 해석 차이:

| GPU | 최종 분자로 우선할 값 | `GetPowerUsage` fallback의 의미 | 주의 |
|---|---|---|---|
| RTX 3090 / GA102 | NVML total energy mJ delta | 1초 평균 power | fallback endpoint 적분은 짧은 kernel에 부적합 |
| V100 / GV100 | NVML total energy mJ delta | instantaneous power | NCU GV100 지원 여부가 별도 gate |
| A100 / GA100 | NVML total energy mJ delta | instantaneous power | MIG/full GPU와 runtime active SM 수 기록 |
| H100 / GH100 | GPU/device total energy mJ delta | 1초 평균 power | module/memory power scope를 component numerator와 분리 |

Power API별 final 채택 기준:

| 측정 경로 | final coefficient 사용 | 이유 |
|---|---|---|
| `nvmlDeviceGetTotalEnergyConsumption` 전후 mJ 차분 | 가능 | kernel 전후 누적 energy delta라 matched-control numerator에 가장 적합 |
| `nvmlDeviceGetPowerUsage` endpoint 적분 | 원칙적으로 불가, fallback/provisional | 세대별 instant/1초 평균 의미가 다르고 endpoint 두 점만으로 kernel energy를 대표하기 어려움 |
| `power.draw.average` / `power.draw.instant` | 진단/metadata | nvidia-smi field는 지원 여부와 sampling window가 driver/SKU별로 다름 |
| H100 module power | 불가 | GPU 외 module 구성요소가 포함되어 component coefficient numerator가 달라짐 |
| GPU memory power reading | 불가 | memory subsystem power이지 L1/L2/DRAM traffic pJ/bit numerator가 아님 |

실패 원인을 빠르게 찾을 때는 power matrix의
`0.A.5 세대별 failure pattern과 수정 지시`를 먼저 확인한다. 예를 들어 A100 결과에
`nvml_power_usage_semantics=one_sec_average`가 나오거나, H100 결과에서 module power를
coefficient numerator로 쓴 흔적이 있으면 NCU hit rate가 좋아도 final 결과로 보지
않는다.

## 실행 순서

```text
static readiness audit
→ preflight
→ platform guide 확인
→ finalplan command 생성
→ energy run
→ NCU sidecar
→ path acceptance
→ matched-control analysis
→ 결과 문서화
```

정적 readiness audit은 실제 GPU를 측정하지 않고 코드/문서 정합성만 확인한다.

```bash
python3 scripts/audit_platform_power_readiness.py \
  --out-csv results/summary/platform_power_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/platform_power_readiness_audit_YYYYMMDD.md
```

로컬 저장소에서 전체 정적 점검과 요약 artifact 갱신을 한 번에 하려면 아래 wrapper를
쓴다.

```bash
scripts/run_local_readiness_checks.sh
```

이 명령은 Python compile check, power API/package-gate self-test, power readiness audit,
A100/V100/H100 result manifest, package audit, gap report 재생성, RTX 3090 strict summary
audit, goal readiness audit, intake dashboard 갱신, `git diff --check`를 순서대로 실행한다.
실제 A100/V100/H100 kernel을 새로 실행하는
명령은 아니므로, 외부 노드 결과가 없으면 goal readiness는 `missing`을 유지하는 것이
정상이다. 다른 날짜 tag를 점검할 때는 `TAG=YYYYMMDD scripts/run_local_readiness_checks.sh`
처럼 실행한다. preflight에서 확인한 runtime SM 수가 기본값과 다르면
`A100_ACTIVE_SM=<n>`, `V100_ACTIVE_SM=<n>`, `H100_ACTIVE_SM=<n>` 환경변수로 package
audit 기준을 맞춘다.

현재 기준 audit 결과는 `results/summary/platform_power_readiness_audit_20260708.md`에
있다. 이 결과가 통과해도 A100/V100/H100의 component coefficient가 검증되었다는 뜻은
아니며, 각 노드에서 power API audit과 NCU/reliability audit을 새로 통과해야 한다.

현재 외부 플랫폼 결과 패키지는 아직 미완성이다. 누락 상태와 다음 조치는 아래 gap
report와 dashboard에서 확인한다. Dashboard는 package audit, gap report, strict summary
상태와 goal readiness 상태를 한 표로 모으는 요약이며, 승인 gate 자체는 아니다.
dashboard의 `next command`는 gap report에서 가져온 첫 재실행 명령이다.

| dashboard | 목적 |
|---|---|
| `results/summary/platform_component_intake_dashboard_20260708.md` | RTX 3090/V100/A100/H100 package 상태, 첫 open stage, strict summary 상태, goal readiness pass/missing/fail 요약 |

| GPU | package audit | gap report |
|---|---|---|
| A100 | `results/summary/a100_platform_result_package_audit_20260708.md` | `results/summary/a100_platform_result_package_gaps_20260708.md` |
| V100 | `results/summary/v100_platform_result_package_audit_20260708.md` | `results/summary/v100_platform_result_package_gaps_20260708.md` |
| H100 | `results/summary/h100_platform_result_package_audit_20260708.md` | `results/summary/h100_platform_result_package_gaps_20260708.md` |

## A100/V100/H100에서 특히 수정할 포인트

| 플랫폼 | 수정/확인 포인트 |
|---|---|
| A100 | RTX 3090의 W_SM을 그대로 쓰지 말고 40 MiB L2와 164 KiB shared allocation 기준으로 L1/L2/DRAM 후보를 다시 잡는다. HBM 결과는 RTX 3090 GDDR6X sanity 값과 직접 비교하지 않는다. |
| V100 | CUDA 12.x `nvcc --list-gpu-arch`의 `compute_70`, `sm_70` build, GV100 지원 NCU를 각각 확인한다. CUDA 13은 Volta offline build가 불가능하고 최신 NCU에서는 GV100이 빠질 수 있다. |
| H100 | 현재 코드는 Hopper-native WGMMA/TMA/FP8 실험이 아니다. 결과는 H100에서 실행한 WMMA compatibility path의 effective coefficient로 제한한다. |

## Archive 관계

`archive/legacy_20260707/docs/multi_gpu_support_plan_ko.md`는 구현 전 계획 문서다. 현재 실행 기준은 이 문서와 각 플랫폼 가이드이며, archive 계획서를 그대로 실행 지침으로 사용하지 않는다.
