# 현재 실험 목표 정합성 감사

작성일: 2026-07-13, 갱신일: 2026-07-14

## 감사 기준

현재 목표는 board/device-level energy와 differential microbenchmark를 사용해 다음
네 경로의 **effective coefficient**를 추정하는 것이다.

| 목표 | 단위 | 현행 treatment-control |
|---|---|---|
| Tensor MMA incremental | pJ/FLOP | `reg_mma - reg_operand_only` |
| Shared scalar path | pJ/bit | `shared_scalar_load_only - clocked_empty` |
| Global L1 hit path | pJ/bit | `global_l1_load_only - global_addr_only` |
| L2 CG hit path | pJ/bit | `l2_cg_load_only - global_addr_only` |

DRAM CG streaming은 유용한 sanity/effective path지만 strict 4-component final table에는
넣지 않는다. Register direct/register-pressure는 control/proxy이며 순수 RF energy가
아니다. 모든 값은 pure silicon/bitcell energy가 아니라 NCU로 경로를 검증한
workload-dependent effective microbenchmark coefficient다.

## 발견한 불일치와 조치

| 우선순위 | 발견 | 영향 | 조치 | 상태 |
|---:|---|---|---|---|
| 1 | matched-control analyzer가 treatment의 exact NCU acceptance만 필터링하고 `reg_operand_only`/`global_addr_only` control의 acceptance를 직접 요구하지 않음 | 오염된 control도 차분에 들어갈 수 있음 | `--require-control-ncu-acceptance` 추가, final plan에서 강제 | 수정 완료 |
| 2 | strict summary/build/package gate가 Global L1/L2의 `global_addr_only`를 exact-coordinate evidence mode로 요구하지 않음 | 보고서는 treatment만 검증하고도 strict로 보일 수 있음 | builder, strict audit, package audit, reliability gate에 address control 추가 | 수정 완료 |
| 3 | DRAM treatment와 address control을 서로 다른 duration-calibrated ITER로 비교 | work count 차이가 DRAM energy로 섞일 수 있음 | treatment/control-floor dual calibration 후 큰 동일 ITER 적용, direct net-energy 차분 | 수정 완료 |
| 4 | 문서 일부가 DRAM L2 hit를 고정 `<=5%`로만 설명 | A100/H100 large-L2 residual residency를 잘못 reject할 수 있음 | 코드와 문서를 `max(5%, 2 * L2_capacity/full_WS + 2%)` 정책으로 통일 | 수정 완료 |
| 5 | 방법 비교/백서/결과 문서가 2026-07-08 RTX 3090 `clocked_empty` 기반 L1/L2/DRAM 값을 현행 final처럼 표현 | 최신 address-control protocol과 결과 provenance가 충돌 | historical/provisional 경고 추가, 현행 pair 표와 구분 | 수정 완료 |
| 6 | 기존 RTX 3090 strict CSV의 Global L1/L2 NCU evidence에 `global_addr_only`가 없음 | 현행 control gate를 소급 통과했다고 주장 불가 | 기존 숫자는 보존하되 현행 final에서 제외, 재실행 package 생성 | 재측정 필요 |
| 7 | 문서는 새 `reg_operand_only` HMMA=0을 요구하지만 acceptance가 과거 fixed epilogue HMMA를 허용 | no-MMA control 정의와 코드 판정이 충돌 | 현행 `reg_operand_only`는 HMMA가 하나라도 있으면 reject; 완화는 legacy proxy mode에만 유지 | 수정 완료 |
| 8 | V100 L2 treatment와 address control이 독립 duration calibration되어 control ITER가 약 2배 큼 | NCU path는 통과했지만 9개 energy 좌표가 모두 음수이며 동일 작업량 차분이 아님 | L2도 dual calibration의 최대 동일 ITER 적용, direct net-energy 차분, calibration/raw/detail package hard gate 추가 | 수정 완료; L2 재측정 필요 |
| 9 | `SKILL.md`와 일부 active 문서가 분류 전 경로, legacy mode, 과거 L2 duration 정책을 함께 기술 | 작업자와 자동화가 서로 다른 실험 protocol을 선택할 수 있음 | canonical 문서 지도와 현행 pair/동일-ITER 정책으로 재작성하고 `audit_documentation_consistency.py`로 자동 검사 | 수정 완료 |
| 10 | superseded A100 v2 설계와 current protocol 이전 그림/방법 비교 문서가 active `docs/`에 공존 | 과거 설계와 현재 실행 절차를 구분하기 어려움 | 원래 구조를 보존한 날짜별 archive로 이동하고 active 방법 비교 문서를 current protocol 기준으로 축약 | 수정 완료 |
| 11 | strict summary 생성기가 RTX 3090이면 과거 정적 결과 그림을 무조건 삽입 | 새 측정 summary에도 다른 protocol의 수치와 NCU 증거가 표시될 수 있음 | 자동 정적 그림 삽입을 제거하고 summary 자체의 표와 artifact 경로만 생성 | 수정 완료 |
| 12 | local readiness가 새 문서 감사기와 일부 핵심 분석기의 정적/self-test를 실행하지 않음 | 문서-코드 회귀가 통합 검사에서 누락됨 | 문서 감사, matched-control self-test, 주요 분석기 `py_compile`을 wrapper에 연결 | 수정 완료 |
| 13 | intake dashboard가 package audit 없는 과거 RTX strict artifact를 현재 완료 플랫폼으로 집계하고 package tag 날짜의 오래된 readiness만 읽음 | 실제 현행 gate 실패가 `1/4 complete`로 가려질 수 있음 | 과거 증거를 `historical_local_evidence`/`historical_pass`로 강등하고, 완료 집계에서 제외하며 `--goal-readiness-csv`로 최신 감사 파일을 명시 | 수정 완료 |

기존 RTX 3090 strict summary를 현행 audit로 다시 검사한 결과는
`results/summary/rtx3090_current_protocol_reaudit_20260714.md`에 기록했다. 결과는
189 checks 중 8 failures다. 과거 NCU summary의 path-specific schema 누락과
Global L1/L2 address-control evidence 누락이 명시적으로 검출됐다.

## 현행 hard gate

| 영역 | 필수 조건 |
|---|---|
| Energy numerator | `nvml_total_energy`, `total_energy_mj_delta`, explicit `measurement_scope=gpu_device_total_energy_counter` |
| Tensor | pair-locked 동일 ITER, `reg_mma` HMMA > 0, `reg_operand_only` no workload-proportional HMMA, spill/local 0 |
| Shared | shared bytes/access/instruction > 0, expected bytes와 정합, bank conflict와 global leakage 제한 |
| Global L1 | path-specific L1 hit >=95%, L2/DRAM leakage <=1% |
| L2 CG | pair-locked 동일 ITER, `matched_iters_net_energy`, path-specific L2 read hit >=95%, L1 path hit/hit-byte ratio <=1%, DRAM/L2 read <=2% |
| DRAM sanity | pair-locked 동일 ITER, L1 hit <=1%, capacity-aware L2 residual, DRAM bytes dominant |
| Control | `reg_operand_only`/`global_addr_only`가 treatment와 동일 좌표에서 NCU accepted |
| 반복 안정성 | positive signal, minimum delta/fraction, power-state reject 제외, sufficient valid rows |

## 플랫폼별 설계 경계

| Profile | active SM | shared allocation profile | L2 | strict NCU blocks/SM | 주의 |
|---|---:|---:|---:|---:|---|
| RTX 3090 / GA102 | 82 | 100 KiB/SM | 6 MiB | 8 | 기존 B16 결과와 새 generated anchor를 혼동하지 않음 |
| V100 32GB / GV100 | 80 | 96 KiB/SM | 6 MiB | 32 | CUDA 12.x/GV100 NCU 지원 확인, W32/B32 strict anchor |
| A100 / GA100 | 108 | 164 KiB/SM | 40 MiB | 16 | L2 W16/32/64/128 plateau를 path-specific counter로 선택 |
| H100 / GH100 | 132 | 228 KiB/SM | 50 MiB | 16 | 현재 Tensor kernel은 WMMA compatibility path이며 WGMMA/TMA 실험이 아님 |

용량값은 실행 좌표를 고르는 profile metadata다. 실제 cache residency와 path는 반드시
해당 노드의 NCU counter로 다시 확인한다.

## 남은 제한

1. RTX 3090의 기존 0.129/0.171/0.173/1.131 계수는 현행 exact-control gate 이전
   결과다. Tensor만 fixed-RF v2로 재실행해 2.2525 pJ/FLOP standalone 근거를
   확보했으며, Shared/Global-L1/L2를 포함한 current strict table은 아직 아니다.
2. A100/V100/H100은 실행 코드와 package gate가 준비됐지만 이 저장소에서 실제 GPU
   결과를 생성한 것은 아니다.
3. 로컬 CUDA 13.2에서 sm_86/sm_80/sm_90 build는 성공했다. CUDA 13.2는 sm_70
   offline compilation을 지원하지 않으므로 V100 build는 CUDA 12.x 대상 노드에서
   수행해야 한다.
4. Shared와 Global L1은 물리적으로 unified L1/shared subsystem에 가깝지만 주소 공간,
   instruction path, arbitration, denominator가 달라 별도 effective path로 보고한다.

## 완료 판정 기준

플랫폼별 현행 final이라고 부르려면 generated command package 전체 실행 후 power API,
power-state, NCU acceptance, matched-control, reliability, strict summary, strict summary
audit, platform package audit가 모두 통과해야 한다. 숫자의 hierarchy가 그럴듯하다는
이유만으로 실패 gate를 덮어쓰지 않는다.
