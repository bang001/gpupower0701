# RTX 3090 component energy 재실험 진행 보고

작성일: 2026-07-03

## 결론

문헌 기준을 반영해 실험 구조를 다시 잡고, 기존 static-byte component 값은 최종
값에서 제외했다. 이번 진행에서는 새 transaction-path 실험에 필요한 code path를
구현하고 RTX 3090에서 energy smoke까지 통과했다.

다만 최종 pJ/actual bit 결과는 아직 보고하지 않는다. NCU가 sandbox 밖에서는
CUDA driver에 연결되지만 `ERR_NVGPUCTRPERM`으로 performance counter 접근이
막혀 actual L1/L2/DRAM/shared traffic을 확보하지 못했기 때문이다.

## 잘못됐던 점

| 항목 | 판단 |
|---|---|
| `*_load_only - empty` 차분 | elapsed/control/stall이 맞지 않아 component energy로 무효 |
| static `expected_*_bytes` | logical byte일 뿐 actual cache/DRAM traffic이 아님 |
| `shared/L1` 묶음 | shared memory instruction path와 global L1 cache hit path가 섞임 |
| register pJ/bit 표현 | RF bitcell energy가 아니라 register operand/control path로만 표기 가능 |
| 문헌값 비교 | HBM device, SRAM primitive, GPU transaction path, NVML board coefficient를 분리해야 함 |

## 구현한 변경

| 구분 | 내용 |
|---|---|
| 새 mode | `clocked_empty`, `addr_only`, `global_l1_load_only` |
| 새 kernel | `clocked_empty_kernel`, `global_addr_only_kernel`, `global_l1_load_only_kernel` |
| 새 CSV 컬럼 | `expected_l1_bytes`, `expected_addr_ops`, `ncu_l1_bytes`, `mode_family`, `denominator_level` |
| Python runner | `run_sweep.py`, `run_component_regression_sweep.py`에 새 mode 반영 |
| 분석 feature | `fit_component_energy_model.py`에 L1 static/NCU feature 추가 |
| NCU summary | shared/L1/L2/DRAM byte 후보, repeat metadata 출력 |
| NCU join | `scripts/join_ncu_summary.py` 추가 |

## Build/self-check

| 항목 | 결과 |
|---|---|
| CUDA build | 통과 |
| 새 kernel ptxas spill | 0 bytes spill stores, 0 bytes spill loads |
| Python compile | 통과 |
| `git diff --check` | 통과 |

## RTX 3090 new-mode smoke

Raw: `results/raw/rtx3090_redo_new_modes_smoke_20260703.csv`

| 항목 | 결과 |
|---|---:|
| rows | 8 |
| SMID pass | 8/8 |
| negative net energy rows | 0 |

## RTX 3090 transaction energy smoke

Raw: `results/raw/rtx3090_redo_transaction_energy_smoke_20260703.csv`

| Mode | W_SM | elapsed (s) | net power (W) | denominator |
|---|---:|---:|---:|---|
| `clocked_empty` | 16 KiB | 0.960 | 125.64 | none |
| `addr_only` | 16 KiB | 1.105 | 173.22 | expected_addr_ops |
| `global_l1_load_only` | 16 KiB | 1.081 | 177.62 | expected_l1_bytes_static |
| `shared_load_only` | 16 KiB | 1.078 | 191.08 | expected_shared_bytes_static |
| `l2_load_only` | 16 KiB | 1.093 | 162.69 | expected_l2_bytes_static |
| `clocked_empty` | 64 KiB | 1.074 | 165.33 | none |
| `addr_only` | 64 KiB | 1.092 | 148.39 | expected_addr_ops |
| `global_l1_load_only` | 64 KiB | 1.096 | 174.07 | expected_l1_bytes_static |
| `shared_load_only` | 64 KiB | 1.095 | 154.83 | expected_shared_bytes_static |
| `l2_load_only` | 64 KiB | 1.129 | 170.57 | expected_l2_bytes_static |
| `clocked_empty` | 8192 KiB | 1.021 | 118.26 | none |
| `addr_only` | 8192 KiB | 1.093 | 177.79 | expected_addr_ops |
| `dram_load_only` | 8192 KiB | 1.088 | 197.79 | expected_dram_bytes_static |

QA:

| 항목 | 결과 |
|---|---:|
| rows | 13 |
| SMID pass | 13/13 |
| negative net energy rows | 0 |
| static fit relative RMSE | 7.223% |

해석: 이 smoke는 실행 구조 확인용이다. `l2_load_only`가 `global_l1_load_only`보다
항상 크지 않고, static fit에서 shared/DRAM slope가 0-bound에 붙었다. 이것은
static expected byte만으로 계층별 pJ/bit를 채택하면 안 된다는 신호다.

## NCU 상태

| 실행 | 결과 |
|---|---|
| sandbox 내부 `sudo -n ncu` | `no new privileges`로 sudo 차단 |
| sandbox 내부 non-sudo NCU | CUDA driver stub 연결 오류 |
| sandbox 밖 non-sudo NCU | CUDA driver 연결 성공, `ERR_NVGPUCTRPERM` |
| sandbox 밖 `sudo -n ncu` | CUDA driver 연결 성공, 동일하게 `ERR_NVGPUCTRPERM` |

따라서 현재 환경에서는 NCU actual traffic 기반 final pJ/actual bit를 만들 수 없다.

## 다음 실행 조건

최종 component energy 표를 만들려면 다음이 필요하다.

| 필요 항목 | 이유 |
|---|---|
| NCU performance counter 권한 해결 | L1/L2/DRAM/shared actual traffic denominator 확보 |
| NCU sidecar 재실행 | hit rate, access count, stall percentage 확인 |
| `join_ncu_summary.py` 실행 | energy row에 NCU actual bytes join |
| final energy run | 20-30 s, 7 repeats 이상 |

최종 보고에서는 NCU 통과 row만 사용하고, 통과하지 못한 row는 `rejected_reason`으로
분리한다.
