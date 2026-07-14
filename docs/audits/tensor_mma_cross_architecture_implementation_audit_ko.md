# Tensor MMA 구현 및 아키텍처 교차 감사

작성일: 2026-07-14
대상 revision: `matched_inplace_signflip_fragment_epilogue_fixed_rf_v4`

## 1. 결론

현재 `reg_mma - reg_operand_only`는 **FP16 WMMA/HMMA와 그 register/scheduler
경로의 workload-dependent board-level 증분 계수 후보**다. 순수 Tensor Core 회로
에너지나 순수 register-file 에너지가 아니다.

v4의 RTX 3090 B4 실측 NCU는 RF1/2/4/8/16 treatment와 control 10개 row를 모두
accept했다. 모든 treatment에서 `HMMA/logical MMA=2.0`, control HMMA=0,
local/spill=0이었다. RF1/2의 별도 precision-path counter도
`FP16-to-FP32 Tensor ops / expected FLOP=1.0`이었다. 따라서 v4의 논리 FLOP
denominator는 RTX 3090에서 동작 검증을 통과했다.

다만 v4 board-energy run은 아직 수행하지 않았다. 기존 RTX 3090 `2.2525 pJ/FLOP`,
A100 `0.625 pJ/FLOP`, V100 `1.034 pJ/FLOP`는 v4 coefficient가 아니며 새 결과로
인용하거나 직접 비교하면 안 된다.

## 2. 과거 구현에서 확인된 오류

| revision | 구현 | 확인된 문제 | 현재 판정 |
|---|---|---|---|
| v2 | 양의 상수 A/B를 FP32 C에 장시간 누적 | 동일 크기 덧셈을 매우 오래 반복하면 FP32 C가 더 이상 갱신되지 않을 수 있음 | superseded |
| v3 | A+와 A- fragment를 phase branch로 선택 | RTX 3090 RF2 이상에서 양/음 HMMA branch가 predication으로 함께 발행되어 HMMA/logical 비율이 RF1 2, RF2-16 4로 달라짐 | rejected |
| v4 | 한 A fragment의 sign bit를 매 MMA 후 in-place flip | predicated HMMA 제거, bounded accumulator 유지 | current candidate |

v3 오류는 단순 counter alias가 아니다. SASS에 RF2 이상 양/음 HMMA 두 경로가
predicated instruction으로 함께 존재했고, NCU의 HMMA와 FP16-to-FP32 operation
counter가 모두 논리값의 2배를 보고했다. 따라서 v3 RF sweep은 같은 연산을 비교한
것이 아니었다.

## 3. v4 kernel 동작

1. A, B, C WMMA fragment를 `fill_fragment`로 register에 만든다.
2. A는 `+1/8`, B는 `+1/16`, C는 0에서 시작한다.
3. `reg_mma`만 `wmma::mma_sync(c, a, b, c)`를 발행한다.
4. treatment/control 모두 같은 dependent scalar update와 fragment liveness barrier를 실행한다.
5. treatment/control 모두 A fragment의 FP16 sign bit를 뒤집는다.
6. 다음 MMA는 반대 부호 A를 사용하므로 C가 두 유한 상태 사이를 왕복한다.
7. 마지막 C/sink를 같은 output 패턴으로 저장해 compiler 제거를 막는다.

RF는 cache reuse factor가 아니라 outer iteration 하나 안에서 위 단계를 몇 번 수행하는지
나타내는 **inner MMA grouping**이다. Tensor mode의 `W_SM=1 KiB`는 CLI 좌표
placeholder이고 memory working set이 아니다.

## 4. FLOP denominator

```text
N_MMA = active_SM * blocks_per_SM * ITER * RF
FLOP  = N_MMA * 8192
8192  = 16 * 16 * 16 * 2
```

NCU는 이 수식을 임의로 대체하지 않고, 실제 lowering이 수식과 선형인지 검증한다.

| gate | 기준 |
|---|---:|
| treatment HMMA | `> 0` |
| control HMMA | `= 0` |
| RF별 HMMA/logical-MMA spread | `<= 10%` |
| FP16-to-FP32 ops / expected FLOP | counter 제공 시 `0.98-1.02` |
| predicated HMMA static SASS | `0` |
| local/spill read/write | `0` |
| operand LDG/LDS static SASS | `0` |

## 5. Caching 효과

`reg_mma`의 A/B operand는 global, shared, L1, L2에서 읽지 않는다. kernel 시작 때
`fill_fragment`가 값을 register fragment에 만들며 반복 구간에서는 같은 register 값을
사용한다. 따라서 이 실험에서 말하는 operand reuse는 **register-resident operand
reuse**이며 cache hit가 아니다.

NCU와 SASS에서 확인해야 할 것은 다음이다.

- treatment operand path에 `LDG`/`LDS`가 없음
- local-memory spill이 없음
- L1/L2/DRAM traffic이 HMMA 규모에 비해 무시 가능한 수준
- control에도 Tensor instruction이 없음

output store와 SMID 검증용 atomic 등 작은 bookkeeping traffic은 존재할 수 있다. 이
traffic이 0이 아니라고 operand가 cache에서 공급됐다고 해석하지 않는다.

## 6. 아키텍처별 상태

| GPU | target | Tensor API/lowering scope | v4 static SASS | treatment registers/thread RF1/2/4/8/16 | runtime NCU |
|---|---|---|---|---|---|
| RTX 3090 | sm_86 / GA102 | FP16 WMMA -> HMMA | pass, predicated HMMA=0, LDG/LDS/local=0 | 35/26/30/30/30 | B4 RF1-16 pass; HMMA/logical=2.0 |
| A100 | sm_80 / GA100 | FP16 WMMA -> HMMA | local cross-compile pass | 29/26/27/27/27 | A100 node v4 재실행 필요 |
| V100 | sm_70 / GV100 | Volta FP16 WMMA -> architecture-specific HMMA | local CUDA 13.2가 sm_70 offline compile을 지원하지 않아 미검증 | 문서상 명확하지 않음 | CUDA 12.x V100 node에서 필수 |
| H100 | sm_90 / GH100 | FP16 WMMA compatibility HMMA; WGMMA/TMA 아님 | local cross-compile pass, WGMMA/TMA=0 | 29/24/28/28/28 | H100 node v4 재실행 필요 |

register footprint가 RF와 architecture마다 다르므로 RF별 coefficient 차이를 Tensor
회로 차이로만 해석하면 안 된다. control은 현재 모든 local build에서 16
registers/thread였고 treatment보다 작다. 이 차이는 최종 coefficient의 명시적 caveat다.

## 7. 증거 artifact

| 증거 | 경로 |
|---|---|
| RTX 3090 v4 binary audit | `results/summary/rtx3090_tensor_mma_binary_audit_20260714.md` |
| A100 sm_80 v4 local binary audit | `results/summary/a100_tensor_mma_binary_audit_local_sm80_20260714.md` |
| H100 sm_90 v4 local binary audit | `results/summary/h100_tensor_mma_binary_audit_local_sm90_20260714.md` |
| RTX 3090 B4 full RF NCU summary | `results/ncu/rtx3090_tensor_v4_ncu_b4_20260714/ncu_cache_validation_summary.csv` |
| RTX 3090 B4 acceptance | `results/summary/rtx3090_tensor_v4_ncu_b4_20260714_acceptance.md` |
| RTX 3090 RF1/2 Tensor-op cross-check | `results/ncu/rtx3090_tensor_v4_ops_crosscheck_20260714/ncu_cache_validation_summary.csv` |

## 8. 플랫폼 재실행 조건

1. 각 target node에서 현재 source를 clean rebuild한다.
2. `scripts/audit_tensor_mma_binary.py`를 target binary와 node의 `cuobjdump`로 실행한다.
3. energy 좌표와 같은 blocks/SM 및 RF1/2/4/8/16에서 NCU를 실행한다.
4. predicated HMMA=0, control HMMA=0, RF ratio 안정성, spill=0을 확인한다.
5. 가능한 architecture에서는 FP16-to-FP32 ops/FLOP gate도 통과한다.
6. 그 뒤에만 새 v4 power pair를 실행해 pJ/FLOP를 계산한다.

이 순서를 통과하기 전의 숫자는 historical/provisional observation으로만 보관한다.
