# RTX 3090 Shared/Global-L1 Matched-Pair 재실험

작성일: 2026-07-14

## 결론

새 Shared address control과 동일-ITER 직접 차분은 기존 음수·불안정 문제를 크게 줄였다.
Shared는 15/15 pair가 유효했고 `0.637283 pJ/bit` median, Global L1은 14/15 pair가
유효했고 `0.430305 pJ/bit` median이었다. NCU는 treatment/control 12/12 case를
accepted로 판정했다.

이 값은 5 s targeted remediation 결과다. 경로와 분모는 NCU로 검증됐지만 표준 10 s,
전체 W/B 좌표와 모든 component를 한 tag로 묶은 strict package를 대체하지 않는다.

## 실험 조건

| 항목 | Shared scalar | Global L1 hit |
|---|---|---|
| GPU | RTX 3090, GA102, 82 SM | RTX 3090, GA102, 82 SM |
| treatment | `shared_scalar_load_only` | `global_l1_load_only` |
| control | `shared_scalar_addr_only` | `global_addr_only` |
| W_SM | 64 KiB/SM | 8 KiB/SM |
| blocks/SM | 8 blocks/SM | 8 blocks/SM |
| load repeat | LR 4, 8, 16 | LR 4, 8, 16 |
| energy duration/repeats | target 5 s, 5 repeats | target 5 s, 5 repeats |
| pair work policy | equal pair-locked ITER | equal pair-locked ITER |
| power numerator | NVML total-energy delta, GPU device scope | 동일 |
| NCU | application replay, cache-control none, ITER 100,000 | 동일 |

## Energy 결과

단위는 pJ/bit이며 NCU actual bytes로 보정했다.

| path | LR | valid/total pairs | min | median | mean | max |
|---|---:|---:|---:|---:|---:|---:|
| Shared scalar | 4 | 5/5 | 0.582488 | 0.832661 | 0.761229 | 0.893580 |
| Shared scalar | 8 | 5/5 | 0.489494 | 0.572573 | 0.574919 | 0.688844 |
| Shared scalar | 16 | 5/5 | 0.424864 | 0.637283 | 0.632685 | 0.745638 |
| Global L1 | 4 | 4/5 | 0.203050 | 0.303065 | 0.299708 | 0.389651 |
| Global L1 | 8 | 5/5 | 0.306530 | 0.541109 | 0.534640 | 0.792151 |
| Global L1 | 16 | 5/5 | 0.314335 | 0.514546 | 0.515247 | 0.731053 |

전체 valid-row 집계:

| path | valid rows | median | 95% bootstrap median CI | confidence | reliability |
|---|---:|---:|---:|---|---|
| Shared scalar | 15 | **0.637283 pJ/bit** | 0.572573-0.745638 pJ/bit | medium-high | accepted |
| Global L1 | 14 | **0.430305 pJ/bit** | 0.310432-0.548047 pJ/bit | medium | accepted_with_caution |

Global L1 LR4 한 pair는 `-0.017310 pJ/bit`, signal fraction `-0.246%`로
`delta_fraction<0.005;negative_coefficient` gate에서 제외했다. 이를 0으로 자르거나
평균에 포함하지 않았다.

## NCU 검증

| path/mode | LR | 핵심 traffic | hit/stall | acceptance |
|---|---:|---:|---:|---|
| Shared control | 4/8/16 | shared read 0 B; init write 5,373,950 B/case | long scoreboard 0.000771-0.004877% | 3/3 accepted |
| Shared treatment | 4 | shared read 268,698,000,000 B | bank conflict 0; long scoreboard 0.002284% | accepted |
| Shared treatment | 8 | shared read 537,395,000,000 B | bank conflict 0; long scoreboard 0.001126% | accepted |
| Shared treatment | 16 | shared read 1,074,790,000,000 B | bank conflict 0; long scoreboard 0.001487% | accepted |
| Global L1 control | 4/8/16 | L1 request 0 B | no input load; background DRAM below paired expected-byte gate | 3/3 accepted |
| Global L1 treatment | 4 | L1 request 268,698,000,000 B | L1 hit 99.9992%; long scoreboard 1.52756% | accepted |
| Global L1 treatment | 8 | L1 request 537,395,000,000 B | L1 hit 99.9999%; long scoreboard 1.87994% | accepted |
| Global L1 treatment | 16 | L1 request 1,074,790,000,000 B | L1 hit 99.9999%; long scoreboard 2.60425% | accepted |

Shared treatment/control은 ptxas와 NCU에서 모두 26 registers/thread, spill/local traffic
0으로 확인됐다. dynamic shared allocation은 8,192 B/block이다. control의 shared write는
공통 초기화이며, 반복 read가 0이라는 점이 핵심이다.

## 이전 방식과 비교

| 항목 | 기존 | 현행 targeted run |
|---|---|---|
| Shared control | `clocked_empty` | matched `shared_scalar_addr_only` |
| Shared/L1 work | mode별 ITER | treatment/control 동일 ITER |
| 차분 | control power를 treatment 시간으로 확대 | 두 net energy 직접 차분 |
| Shared 유효 pair | LR16에서 5/5 음수였던 run 존재 | 전체 15/15 양수 |
| Global L1 유효 pair | 4/15 수준의 과거 run 존재 | 14/15 |
| denominator | static/representative 혼용 가능 | 29 valid rows 모두 `ncu_actual_exact` |

개선은 확인됐지만, 새 coefficient는 순수 shared SRAM 또는 L1 bitcell energy가 아니다.
동일 loop work 완료에 추가된 load instruction, arbitration, dependency stall,
scheduler/clocked-SM 시간을 포함한 effective board-level coefficient다.

## QA 및 산출물

| 검사 | 결과 |
|---|---|
| power API audit | 60/60 final_candidate, reject 0 |
| power-state audit | ok 59, caution 1 temperature outlier, reject 0 |
| NCU reports | 12/12 생성 |
| NCU acceptance | 12 accepted, provisional/reject 0 |
| matched detail | 30 rows; valid 29, invalid 1 |
| reliability | Shared accepted, Global L1 accepted_with_caution |

- Energy raw: `results/raw/rtx3090_pairv2b_20260714_{shared,l1}.csv`
- NCU summary: `results/ncu/rtx3090_pairv2b_20260714/ncu_cache_validation_summary.csv`
- Acceptance: `results/summary/rtx3090_pairv2b_20260714_ncu_acceptance.csv`
- Matched detail/summary: `results/summary/rtx3090_pairv2b_20260714_matched_control_{detail,summary}.csv`
- Reliability: `results/summary/rtx3090_pairv2b_20260714_component_reliability_audit.md`
