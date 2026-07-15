# A100/V100 synthetic self-test 오인 실패 감사

작성일: 2026-07-16

## 결론

보고된 아래 문구는 A100 또는 V100에서 실행한 실제 Tensor calibration
결과가 아니다.

```text
Tensor pair calibration rejected before energy collection:
W=2048KiB B=16 SM=108 RF=4
control/treatment ITER ratio=21.930
predicted treatment=438.596s, limit=120.000s
```

이 숫자는 `scripts/run_component_regression_sweep.py --self-test` 안에서
폭주 ITER를 거부하는 gate가 작동하는지 확인하기 위해 만든 synthetic fixture와
정확히 일치한다. 이 self-test의 정상 종료코드는 0이다. 그러나 예상 거부 문구를
stderr에 실제 플랫폼 오류처럼 출력했기 때문에 사용자 또는 stderr 기반 실행기가
실패로 오인할 수 있었다.

## 실제 좌표와 다른 증거

| 항목 | synthetic fixture | 실제 A100 Tensor | 실제 V100 Tensor |
|---|---:|---:|---:|
| `W_SM` | 2,048 KiB | 1 KiB placeholder | 1 KiB placeholder |
| active SM | 108 SM | 108 SM | 80 SM |
| blocks/SM | 16 | 4,16,32 sweep | 4,16,32 sweep |
| RF | 4 | 1,2,4,8,16 | 1,2,4,8,16 |
| treatment candidate | 456 ITER | runtime calibration | runtime calibration |
| control candidate | 10,000 ITER | runtime calibration | runtime calibration |

특히 V100에서도 `SM=108`이 표시됐다는 사실은 실제 V100 calibration일 수
없음을 확정한다. V100 profile은 active SM 80을 사용한다.

## 실제 중단을 혼동하게 만든 두 문제

1. Negative self-test가 예상 거부 문구를 stderr에 그대로 내보냈다.
2. 기존 finalplan은 L2 NCU selector를 모든 장시간 energy sweep보다 먼저
   실행했다. L2 후보가 reject되면 Tensor, Shared, Global-L1,
   external-memory energy까지 하나도 수집하지 않고 종료했다.

첫 번째는 false failure presentation 문제이고, 두 번째는 컴포넌트 간
실패 격리가 부족한 pipeline ordering 문제다. 6배 ITER stretch gate 자체는
실제 launch-only 또는 폭주 treatment를 막는 유효한 gate이므로 낮추지 않는다.

## 20260716 수정

| 수정 | 새 동작 |
|---|---|
| self-test 출력 캡처 | synthetic 내부 stdout/stderr를 캡처하고 성공 한 줄만 출력 |
| stderr 정책 | 정상 self-test는 stderr 0 byte |
| 실제 calibration 식별 | `runtime Tensor pair calibration start`와 profile/W/B/SM/RF 출력 |
| shell stage marker | `PIPELINE_STAGE`로 현재 실행 단계를 명시 |
| component ordering | Tensor, Shared, Global-L1, external-memory energy를 먼저 수집 |
| L2 격리 | NCU selector 이후 선택된 좌표에서만 L2 energy 실행 |
| L2 실패 | L2 coefficient를 만들지 않고 non-L2 raw/calibration은 보존 |
| fixture 식별 | 현재 부정 fixture는 `profile=synthetic_selftest`, `GPU=none`, `SM=3`을 사용 |

새 self-test의 정상 출력은 다음 한 줄이다.

```text
component regression sweep self-test passed (synthetic runaway rejection verified; no GPU measurement performed)
```

## 실제 runtime 실패 판정

새 실행에서 실제 Tensor calibration이 6배 gate에 걸리면 문구가 다음처럼
`Runtime`으로 시작하며 target profile과 실제 좌표를 포함한다.

```text
Runtime Tensor pair calibration rejected before energy collection:
profile=a100 W=1KiB ... SM=108 ...
```

이때만 실제 target GPU failure로 판정한다. 함께 생성된
`results/raw/<profile>_component_finalplan_20260716_tensor_pair_calibration.csv`에서
다음을 확인한다.

| column | 의미/판정 |
|---|---|
| `treatment_trial_elapsed_s` | 실제 treatment trial, 0.05 s 이상 필요 |
| `control_trial_elapsed_s` | 실제 control trial, 0.05 s 이상 필요 |
| `control_to_treatment_iter_ratio` | 서로 다른 목표시간을 반영한 candidate ITER 비율 |
| `predicted_treatment_seconds` | max ITER를 treatment에 적용한 예상시간 |
| `status` | `pair_locked`만 energy 실행 가능 |

## 재실행 기준

1. `git pull origin main` 후 target profile build를 clean rebuild한다.
2. 기존 `20260715` shell을 재개하지 않고 `20260716` shell을 실행한다.
3. 로그에서 `PIPELINE_STAGE: tensor_energy_sweep`과
   `REAL GPU CALIBRATION`을 확인한다.
4. 실제 reject가 발생하면 전체 로그보다 먼저 Tensor calibration CSV와
   reject 직전/직후 로그를 보존한다.
5. L2 selector 실패는 Tensor failure로 기록하지 않는다. 이 경우 non-L2
   raw 결과와 L2 selection report를 별도 반입한다.

이 변경은 false failure를 제거하고 컴포넌트 실패를 격리한다. 실제
A100/V100 coefficient의 채택 여부는 여전히 target-node NVML energy, NCU path,
matched-control, reliability 및 strict/package audit가 결정한다.
