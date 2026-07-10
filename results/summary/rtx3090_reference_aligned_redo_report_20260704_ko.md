# RTX 3090 Reference-Aligned Component Energy 재실험 보고서

작성일: 2026-07-04

## 결론

기존 `rtx3090_component_energy_estimates_20260703`의 memory 값은 최종 대표값으로 쓰면 안 된다. 특히 `Shared/L1 increment = 6.205 pJ/bit`, `L2 increment = 1.348 pJ/bit`는 reference 문헌의 transaction-path 해석과 맞지 않았다. 원인은 `shared`와 `global L1`을 묶었고, NCU actual traffic이 아니라 static expected byte를 denominator로 썼기 때문이다.

이번 재실험에서는 NCU actual byte를 denominator로 사용하고, hit-rate/access 기준으로 row를 채택했다. 그 결과 full-occupancy에 가까운 `blocks/SM=16` subset에서는 다음처럼 정리된다.

| Path | Estimate | Unit | NCU 채택 기준 |
|---|---:|---|---|
| Global L1 hit path | 3.275 | pJ/bit | L1 hit 약 99.999%, L2/L1 byte ratio 낮음 |
| L2 hit path | 30.330 | pJ/bit | L2 hit 약 99.801%, DRAM/L2 byte ratio 낮음 |
| DRAM streaming path | 31.771 | pJ/bit | L2 hit 약 0.173%, DRAM bytes 큼 |

따라서 사용자가 지적한 "L1이 L2보다 크게 나오는 문제"는 reference-aligned 재분석 후 해소됐다. 현재 대표 subset 기준 order는 다음과 같다.

```text
Global L1 hit path (3.275 pJ/bit)
  < L2 hit path (30.330 pJ/bit)
  ~= DRAM streaming path (31.771 pJ/bit)
```

## Reference 정합성

문헌값은 서로 같은 레벨이 아니므로 직접 동일값으로 맞추면 안 된다. 다만 GPU hierarchy transaction-path order를 점검하는 reference로는 GPUJoule 계열의 K40 값이 유용하다.

| 항목 | Reference 예 | 이번 RTX 3090 B=16 결과 | 판단 |
|---|---:|---:|---|
| L1/global load path | L1->RF 약 5.85 pJ/bit | 3.275 pJ/bit | 같은 order |
| L2 path | L2->L1 약 15.48 pJ/bit | 30.330 pJ/bit | L1보다 큼, transaction-path로 정합 |
| DRAM path | DRAM->L2 약 30.55 pJ/bit | 31.771 pJ/bit | 매우 가까운 order |

주의: 위 reference는 K40/GDDR5 transaction-path 관점이고, 이번 값은 RTX 3090/GDDR6X의 NVML board-level effective coefficient다. 순수 SRAM/HBM/GDDR device bitcell energy가 아니다.

## 실험 조건

| 항목 | 값 |
|---|---|
| GPU | RTX 3090, GA102, 82 SM |
| Energy source | NVML total energy delta |
| Energy matrix | `results/raw/rtx3090_reference_aligned_energy_20260704.csv` |
| Energy rows | 78 |
| SMID 검증 | 78/78 pass |
| negative net energy | 0 |
| 목표 시간 | 3 s/row |
| 실제 elapsed | median 3.319 s, min 2.918 s, max 3.421 s |
| 최대 온도 | 80 C |
| Clock 상태 | unlocked clocks |
| W_SM | 16, 64, 8192 KiB |
| blocks/SM | 8, 16 |
| load_repeat | 4 |
| repeats | 3 |

NCU sidecar는 아래 네 조합으로 수행했다.

| NCU sidecar | 목적 |
|---|---|
| `rtx3090_refalign_ncu_b8_w16_lr4_20260704` | B=8, W=16 L1/L1-dominated 후보 |
| `rtx3090_refalign_ncu_b8_w64_lr4_20260704` | B=8, W=64 L2 후보 |
| `rtx3090_refalign_ncu_b16_w16_lr4_20260704` | B=16, W=16 L1/L1-dominated 후보 |
| `rtx3090_refalign_ncu_b16_w64_lr4_20260704` | B=16, W=64 L2 후보 |

## 분석 개선

이번에 수정한 핵심은 다음이다.

| 문제 | 수정 |
|---|---|
| static expected byte를 최종 denominator로 사용 | NCU actual `l1tex/lts/dram bytes`를 denominator로 사용 |
| shared와 global L1 혼합 | `shared_load_only`는 traffic verified만 하고, global L1은 `global_l1_load_only`로 분리 |
| W=16 `l2_load_only`가 L2 실험으로 섞임 | L2 hit 및 L2/L1 byte ratio 기준으로 자동 기각 |
| NCU `Tbyte` 단위 미변환 | `Tbyte -> 1e12 byte` 변환 추가 |
| raw/details CSV 중복 합산 | raw explicit metric CSV만 집계하도록 수정 |
| B=8 L2 row의 fixed active energy 영향 | B=16 representative subset을 별도 산출 |

## 전체 결과와 대표 결과

모든 채택 row를 사용하면 L2 path가 B=8 row 때문에 크게 튄다.

| Path | All accepted rows | Unit | 판단 |
|---|---:|---|---|
| Global L1 path | 3.898 | pJ/bit | 안정적 |
| L2 hit path | 79.953 | pJ/bit | B=8 outlier 포함, 대표값으로 부적합 |
| DRAM streaming path | 32.397 | pJ/bit | 안정적 |

B=16 subset만 사용하면 fixed active energy가 더 잘 amortize되고 reference order와 정합한다.

| Path | B=16 estimate | Min | Max | Unit | 사용 여부 |
|---|---:|---:|---:|---|---|
| Global L1 path | 3.275 | 3.262 | 3.409 | pJ/bit | 대표 후보 |
| L2 hit path | 30.330 | 29.105 | 30.668 | pJ/bit | 대표 후보 |
| DRAM streaming path | 31.771 | 31.350 | 31.919 | pJ/bit | 대표 후보 |

진단용 delta는 다음이다. 이 값은 순수 component isolation이 아니라 path estimate 간 차이다.

| Delta | 값 | Unit | 해석 |
|---|---:|---|---|
| L2 path - L1 path | 27.055 | pJ/bit | L2 추가 path가 L1보다 충분히 큼 |
| DRAM path - L2 path | 1.441 | pJ/bit | DRAM/L2가 현재 workload에서 거의 비슷하게 나옴 |

## Row 채택/기각

B=16 대표 subset 기준:

| 항목 | row 수 |
|---|---:|
| accepted rows | 15 |
| Global L1 accepted | 3 |
| L2 accepted | 3 |
| DRAM accepted | 3 |
| Shared traffic verified | 6 |

기각 이유:

| reason | rows | 의미 |
|---|---:|---|
| `blocks_per_sm_not_selected` | 39 | B=16 대표 subset에서 B=8 제외 |
| `l2_hit_below_threshold` | 3 | W=16 `l2_load_only`가 L2 row가 아님 |
| `l1_hit_below_threshold` | 3 | W=64 `global_l1_load_only`가 L1 row가 아님 |
| `missing_ncu_join` | 9 | NCU를 의도적으로 수집하지 않은 control/W 조합 |
| `mode_not_in_memory_path_set` | 9 | control mode |

## 남은 한계

1. Shared memory는 NCU shared wavefront/access는 확인됐지만, 이 환경에서 shared byte direct denominator가 없어 pJ/bit 대표값을 보류했다.
2. 현재 값은 3초, 3회 반복, unlocked clocks 조건이다. 논문 표에는 10초 이상, 5회 이상, clock/thermal 조건을 더 강하게 통제한 final run이 필요하다.
3. `net_E_J / NCU actual path bits`는 board-level effective path coefficient다. 순수 L1/L2/GDDR6X device energy가 아니다.
4. B=8 L2 row는 NCU hit 조건은 통과하지만 denominator가 작아 fixed active energy가 pJ/bit에 크게 섞인다. 대표값에서는 제외하는 것이 타당하다.

## 산출물

| 파일 | 내용 |
|---|---|
| `results/raw/rtx3090_reference_aligned_energy_20260704.csv` | 개선 energy matrix raw |
| `results/raw/rtx3090_reference_aligned_energy_20260704_joined_ncu.csv` | NCU actual traffic 결합 CSV |
| `results/summary/rtx3090_reference_aligned_memory_20260704_ko.md` | 전체 accepted row 분석 |
| `results/summary/rtx3090_reference_aligned_memory_b16_20260704_ko.md` | B=16 대표 subset 분석 |
| `scripts/analyze_reference_aligned_memory.py` | reference-aligned 분석기 |
