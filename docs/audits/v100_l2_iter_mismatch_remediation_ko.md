# V100 L2 ITER 불일치 점검 및 수정

작성일: 2026-07-13

## 결론

외부 V100 실행에서 보고된 NCU 결과는 L2 경로 검증으로는 성공했다. 그러나
`global_addr_only` control의 `ITER`가 `l2_cg_load_only` treatment보다 약 2배 많았으므로,
9개 좌표에서 계산된 음수 `-12~-9 pJ/byte`는 L2 energy coefficient로 사용할 수 없다.
경로가 맞다는 사실과 energy 차분의 작업량이 맞다는 사실은 별개의 gate다.

## 보고된 증거의 판정

| 항목 | 보고값 | 단위 | 판정 |
|---|---:|---|---|
| L2 read hit | 약 99.9996 | % | L2-hit path acceptance 성공 |
| L1 hit | 0 | % | L1 cache hit 혼입 없음 |
| energy 좌표 | 9 | coordinates | 모든 좌표의 작업량 불일치로 coefficient 무효 |
| control/treatment ITER | 약 2:1 | ratio | 동일 작업량 차분 실패 |
| 계산 coefficient | 약 -12~-9 | pJ/byte | 물리적 음의 L2 energy가 아니라 잘못된 pair 구성 신호 |

이 표의 수치는 사용자가 외부 V100 노드에서 전달한 결과다. 해당 raw/NCU CSV가 현재
workspace에 없으므로 여기서 값을 재계산한 것은 아니다.

## 원인

수정 전 표준 L2 energy command는 두 mode를 독립적으로 duration calibration했다.
빠른 mode와 느린 mode가 같은 목표시간을 채우기 위해 서로 다른 횟수의 loop를 실행했고,
분석기는 control power를 treatment 시간으로 보정했다. 이 방식은 steady-state power 비교에는
쓸 수 있지만, 같은 logical address/update 횟수에서 L2 load 추가분을 구하려는 현재 목적에는
맞지 않는다.

특히 NCU acceptance는 다음만 증명한다.

```text
l2_cg_load_only bytes -> L1 hit 없이 L2 read hit
```

NCU acceptance만으로 다음을 증명하지는 않는다.

```text
ITER(l2_cg_load_only) == ITER(global_addr_only)
```

## 수정된 정책

| 단계 | 수정 내용 | 필수 증거 |
|---|---|---|
| calibration | treatment 목표시간과 control 최소시간을 각각 calibration | 두 candidate ITER |
| ITER 선택 | 두 candidate 중 큰 값을 treatment/control 양쪽에 적용 | `resolved_iters=max(candidates)` |
| 실행 | control 바로 다음에 treatment를 실행하고 pair 단위로 순서를 회전 | raw 두 mode의 동일 positive `ITER` |
| 에너지 차분 | elapsed-time power scaling 없이 net energy 직접 차분 | `pair_energy_basis=matched_iters_net_energy` |
| 분석 gate | ITER가 다르면 L2 row를 hard reject | `iter_ratio=1`, mismatch diagnostic 없음 |
| package gate | L2 calibration manifest와 raw/detail을 교차검사 | `*_l2_pair_calibration.csv` |

수정된 계산은 다음과 같다.

```text
delta_E_J = net_E_J(l2_cg_load_only, ITER=N)
          - net_E_J(global_addr_only, ITER=N)

pJ/byte = delta_E_J * 1e12 / NCU-validated L2 bytes
pJ/bit  = pJ/byte / 8
```

분자는 동일 횟수의 treatment-control energy 차이고, 분모는 NCU가 검증한 L2 traffic이다.
이 값은 순수 L2 SRAM bitcell energy가 아니라 address generation, L1TEX 통과, L2 lookup/data
return, interconnect, scheduler/stall 및 board power-state 영향을 포함하는 effective coefficient다.

## V100 재실행 조건

현재 생성기는 V100 L2 sweep에 아래 조건을 자동으로 넣는다.

| parameter | 선택값 | 단위 |
|---|---|---|
| mode pair | `global_addr_only,l2_cg_load_only` | - |
| `W_SM` | 32, 64 | KiB/SM |
| blocks/SM | 4, 16, 32 | blocks/SM |
| load repeat | 4, 8, 16 | loads/iteration factor |
| treatment target | 10 | s |
| control floor | 1 | s |
| repeats | 5 | repeats/coordinate |

새 command package를 생성하거나 repository의 갱신된 package를 실행한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 \
  --binary ./build-v100/a100_fp16_energy_v2 \
  --active-sm 80 \
  --seconds 10 \
  --repeats 5 \
  --tag 20260713

bash results/summary/v100_component_finalplan_20260713_commands.sh
```

기존 NCU artifact는 같은 binary revision, W/B/active-SM/LR와 accepted path evidence가
확인되면 경로/traffic scale 증거로 재검토할 수 있다. 다만 L2 energy raw, L2 pair calibration,
power-state audit, matched-control detail/summary와 그 downstream strict package는 반드시 다시
생성해야 한다.

## 최종 승인 체크

| check | 통과 기준 |
|---|---|
| NCU path | L2 read hit >=95%, L1 path hit <=1%, L1 hit/request <=1%, DRAM/L2 read <=2% |
| calibration manifest | 모든 W/B/LR에 source=`l2_cg_load_only`, status=`pair_locked` |
| raw work | treatment/control의 positive `ITER`가 resolved ITER와 동일 |
| matched detail | `pair_energy_basis=matched_iters_net_energy`, `iter_ratio=1` |
| energy signal | `delta_E_J>0`, configured minimum delta와 power-state gate 통과 |
| reporting | pJ/byte와 pJ/bit 모두 단위 표기, min/median/max 및 rejected 좌표 포함 |

재실험 전에는 V100 L2 coefficient를 “미확정”으로 유지한다. NCU 99.9996%는 유지할 수 있는
강한 path evidence지만, 기존 음수 energy 값을 양수로 보정하거나 절댓값으로 바꾸는 근거는 아니다.
