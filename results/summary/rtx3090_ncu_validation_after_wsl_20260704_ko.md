# RTX 3090 NCU 검증 결과: WSL 재시작 이후

## 실행 목적

NVIDIA Control Panel 설정과 WSL 재시작 이후 Nsight Compute performance counter 권한이 실제로 해결되었는지 확인하고, 현재 component energy 실험 mode가 의도한 cache/memory 경로를 타는지 double check했다.

## 실행 결과

| 항목 | 결과 |
|---|---|
| GPU | RTX 3090, GA102, 82 SM |
| NCU 실행 | 성공 |
| permission error | 없음 |
| 대표 W sweep sidecar | `results/ncu/rtx3090_redo_ncu_explicit_20260704/` |
| W=16KiB sidecar | `results/ncu/rtx3090_redo_ncu_explicit_w16_20260704/` |
| 각 sidecar case 수 | 14 |
| 수집 metric | L1/L2 hit rate, L1/L2/DRAM access/byte, shared wavefront, tensor HMMA instruction, stall percentage |
| register spill metric | 이 NCU export에서는 `sass__inst_executed_register_spilling_*` 컬럼이 제공되지 않음 |

## 핵심 판정

| mode | W_SM | 주요 NCU 결과 | 판정 |
|---|---:|---|---|
| `global_l1_load_only` | 16 KiB | L1 hit 약 99.999%, L1 bytes 약 5.37e11 B, L2/DRAM bytes 약 2e8 B | L1-resident 후보로 타당 |
| `l2_load_only` | 16 KiB | L1 hit 약 99.999%, L2 bytes 약 1.97e8 B | L2 실험으로 부적합, 사실상 L1-resident |
| `l2_load_only` | 64 KiB | L2 hit 약 99.738%, L2 bytes 약 6.74e10 B, DRAM bytes 약 2.14e8 B | L2 stress 후보. 단, L1 bytes도 커서 순수 L2로 해석하면 안 됨 |
| `dram_load_only` | 8192 KiB | L2 hit 약 0.15-0.17%, DRAM bytes 약 2.69e11 B | DRAM streaming 후보로 타당 |
| `shared_load_only` | 16/64 KiB | shared wavefront 약 4.36e9, L1 global bytes 0 | shared/L1 경로 확인용으로 사용 가능. shared byte는 NCU direct byte metric이 없어 static 계산 병행 필요 |
| `reg_mma` | 2048 KiB, B=4 | HMMA inst 약 1.312e8, L1 bytes 0, L2/DRAM 초기화성 traffic 존재 | tensor/register stress 후보. 다만 memory traffic이 완전히 0은 아님 |

## Stall 확인

요약 파일에 다음 NCU stall percentage 컬럼을 추가했다.

| 컬럼 | 의미 |
|---|---|
| `stall_long_scoreboard_pct` | memory dependency 등 long scoreboard stall 계열 |
| `stall_short_scoreboard_pct` | short scoreboard stall 계열 |
| `stall_wait_pct` | wait stall 계열 |
| `stall_not_selected_pct` | ready warp가 선택되지 않은 비율 계열 |

주의: NCU의 `smsp__average_warps_issue_stalled_*_per_issue_active.pct` 값은 여러 stall reason을 독립적으로 평균한 파생 지표다. 따라서 모든 stall percentage의 합이 100%가 되거나 각 값이 항상 100% 이하라는 의미로 해석하면 안 된다. mode 간 병목 성향 비교용으로 사용해야 한다.

## Energy fit 현황

NCU counter를 기존 1초 smoke energy CSV와 결합했다.

| 파일 | 내용 |
|---|---|
| `results/raw/rtx3090_redo_transaction_energy_smoke_20260703_joined_ncu_multi_20260704.csv` | 13개 energy row 중 9개가 NCU counter와 결합됨 |
| `results/summary/rtx3090_redo_transaction_energy_smoke_20260703_fit_prefer_ncu_multi_20260704.md` | NCU byte 우선 regression fit |

현재 fit 결과는 최종 component pJ 값으로 채택하지 않는다.

| 계수 | 현재 smoke fit |
|---|---:|
| L1 bytes | 약 0.537 pJ/byte |
| L2 bytes | 약 0.0204 pJ/byte |
| DRAM bytes | 0 pJ/byte 경계 |

이 값은 문헌 기준과 비교해 L2/DRAM이 비현실적으로 작고, DRAM이 0 경계에 붙는다. 원인은 물리적으로 DRAM 에너지가 0이라는 뜻이 아니라, 기존 1초 smoke 에너지 행렬이 부족하고 elapsed/mode baseline이 slope를 흡수하기 때문이다.

## 다음 실험 설계 판단

1. `W_SM=16KiB`의 `l2_load_only`는 L2 실험에서 제외한다.
2. L2 계수는 `W_SM=64KiB` 이상에서, L1 traffic을 별도 covariate로 두고 회귀해야 한다.
3. DRAM 계수는 `W_SM=8192KiB`처럼 L2 hit가 1% 미만인 row를 여러 duration/repeat로 늘려야 한다.
4. 최종 pJ/bit 보고에는 1초 smoke가 아니라 5-10초 이상, 반복 3회 이상, W/blocks/repeat variation이 있는 energy matrix를 사용해야 한다.
5. NCU sidecar는 energy matrix와 동일한 `(mode, W_SM, blocks/SM, active_SM, load_repeat, store_repeat)` key로 수집해야 한다.
