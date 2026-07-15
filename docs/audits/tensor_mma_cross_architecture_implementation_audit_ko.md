# Tensor MMA 구현 및 아키텍처 교차 감사

작성일: 2026-07-14, updated 2026-07-15
대상 revision: `matched_runtime_clock_observed_control_fixed_rf_v6`

## 1. 결론

`reg_mma - reg_operand_only`는 FP16 WMMA/HMMA와 관련 register,
scheduler, clocked-SM 경로의 **workload-dependent board-level 증분 계수**다.
순수 Tensor Core 회로 에너지나 순수 register-file energy가 아니다.

v5는 RTX 3090/GA102에서 strict result를 만들었지만, 2026-07-15 A100
run에서 portability 실패가 확인됐다. B32/RF8 control의
`ITER=1,047,022,600`이 약 1.15 ms에 종료되어 no-MMA loop가 runtime
work로 남지 않았음을 보였고, 같은 ITER의 treatment는 2,096.5 s
걸렸다. 해당 A100 Tensor row는 무효다. 세부 판정은
[A100 Tensor control calibration 실패 감사](a100_tensor_control_calibration_failure_20260715_ko.md)를
따른다.

v6는 treatment/control에 동일한 `SR_CLOCKLO` runtime token dependency를
넣어 루프 제거를 막고, calibration trial 50 ms, treatment 신장 6배,
개별 command 180 s gate로 장시간 실패를 energy 수집 전에 차단한다.

## 2. Revision 감사

| revision | 구현 | 확인된 문제/개선 | 현재 판정 |
|---|---|---|---|
| v2 | 양의 상수 A/B를 FP32 C에 장시간 누적 | FP32 accumulator가 정밀도 한계에서 더 이상 갱신되지 않을 수 있음 | superseded |
| v3 | A+/A- fragment를 phase branch로 선택 | RF2 이상에서 양/음 HMMA path가 predication으로 함께 발행 | rejected |
| v4 | 한 A fragment의 sign bit를 MMA 후 flip | no-MMA control loop 전체가 ptxas에서 제거 | rejected |
| v5 | scalar sink를 output에 저장 | GA102에서 통과했으나 A100 `sm_80` control이 launch-only로 실행된 관측 | GA102 historical; cross-platform superseded |
| v6 | v5 + treatment/control 공통 `SR_CLOCKLO` dependency + calibration/timeout gate | runtime-dependent loop와 실행시간 증거를 static/dynamic으로 동시 요구 | current candidate |

## 3. v6 kernel 동작

1. A, B, C WMMA fragment를 `fill_fragment`로 register에 만든다.
2. A는 `+1/8`, B는 `+1/16`, C는 0에서 시작한다.
3. `reg_mma`만 `wmma::mma_sync(c, a, b, c)`를 발행한다.
4. 두 mode 모두 inner step에서 `SR_CLOCKLO`를 register로 읽어 scalar sink에
   연결한다. 이는 메모리 load가 아니며 ptxas 제거 방지용이다.
5. 두 mode 모두 fragment liveness barrier와 A sign flip을 실행한다.
6. `reg_mma`의 C는 A 부호가 교대하여 두 유한 상태를 왕복한다.
7. 마지막 sink와 C fragment를 output에 저장한다.

RF는 cache reuse factor가 아니라 outer iteration 하나 안에서 위 inner
step을 몇 번 실행하는지 나타내는 grouping이다. Tensor mode의
`W_SM=1 KiB`는 CLI placeholder이며 memory working set이 아니다.

`SR_CLOCKLO`는 새 비용을 도입한다. 두 mode에 동일하게 들어가지만,
MMA와 overlap되는 방식이 다를 수 있으므로 완벽히 상쇄된다고
단정하지 않는다. 이것이 v6 계수도 pure Tensor energy가 아닌 이유다.

## 4. FLOP 분모와 NCU

```text
N_MMA = active_SM * blocks_per_SM * ITER * RF
FLOP  = N_MMA * 8192
8192  = 16 * 16 * 16 * 2
```

NCU는 이 수식을 대체하는 전력 측정기가 아니다. 실제 코드가
예상 HMMA/FLOP, no-MMA control, spill-free register operand path를 실행했는지
검증한다.

| gate | 기준 |
|---|---:|
| treatment HMMA | `> 0` |
| control HMMA | `= 0` |
| RF별 HMMA/logical-MMA spread | `<= 10%` |
| FP16-to-FP32 ops / expected FLOP | counter 제공 시 `0.98-1.02` |
| predicated treatment HMMA | `0` |
| runtime-token backward loop | treatment/control RF1/2/4/8/16 모두 `> 0` |
| control runtime SASS/expected register op | `>= 0.1` |
| local/spill read/write | `0` |
| operand LDG/LDS static SASS | `0` |

## 5. Calibration 및 시간 gate

Treatment 목표시간과 control 최소시간을 각각 calibrate한 뒤 두
candidate ITER의 최댓값을 두 mode에 동일하게 적용한다. 단, 아래
사전 gate를 모두 통과해야 energy sweep를 시작한다.

| gate | 기준 | 막는 실패 |
|---|---:|---|
| treatment/control trial elapsed | 각각 `>= 0.05 s` | launch overhead 외삽 |
| `control_ITER / treatment_ITER` | `<= max_treatment_stretch` | control 제거로 인한 과대 ITER |
| standard max treatment stretch | `6.0x` | 10 s target가 60 s 이상으로 늘어나는 pair |
| standard command wall time | `180 s` | 사전 gate를 빠져나간 장시간 command |

Timeout은 해당 row를 건너뛰고 계속하라는 의미가 아니다. 전체 run을
즉시 reject하고 calibration/kernel을 점검하라는 fail-fast gate다.

## 6. Cache 오염 해석

`reg_mma`의 A/B operand는 global, shared, L1, L2에서 읽지 않는다. kernel
시작 시 `fill_fragment`가 register fragment에 값을 만들고, 반복 구간은
그 register-resident operand를 재사용한다. 다음을 확인한다.

- treatment operand path의 `LDG`/`LDS` 없음
- local-memory spill 없음
- L1/L2/DRAM traffic이 HMMA 수에 비해 미미함
- control Tensor instruction 0

Output store와 SMID 검증용 atomic 등 작은 bookkeeping traffic은 있을 수 있다.
이를 operand cache supply로 해석하지 않는다.

## 7. 아키텍처별 현재 상태

| GPU | target/API | v6 local static SASS | target-node runtime 판정 |
|---|---|---|---|
| RTX 3090 | sm_86, FP16 WMMA -> HMMA | RF1/2/4/8/16 treatment/control 10/10 pass | v6 fresh power/NCU run 필요; v5 2.140 pJ/FLOP은 historical GA102 result |
| A100 | sm_80, FP16 WMMA -> HMMA | local clean build 10/10 pass | 실제 A100에서 clean build, calibration manifest, NCU, power 재실행 필요 |
| V100 | sm_70, Volta HMMA | local CUDA 13.2가 sm_70 offline compile을 지원하지 않아 미검증 | CUDA 12.x V100 node에서 static/runtime audit 필수 |
| H100 | sm_90, WMMA compatibility HMMA | local clean build 10/10 pass | target H100 fresh power/NCU run 필요; WGMMA/TMA 계수가 아님 |

Local RTX 3090에서 sm_80 cubin을 실행한 v6 smoke test는 B16/RF8 control
calibration trial 0.0589 s, fixed control 1.006 s를 보였다. 이는 v6가
launch-only이 아님을 보여주지만, GA100 target-node 통과를 대체하지 않는다.

Register footprint가 RF와 architecture마다 다르고 no-MMA control이 treatment보다
적은 register로 lowering될 수 있으므로, RF별 계수 차이를 Tensor 회로
차이로만 해석하지 않는다. 보고서에 두 kernel의 registers/thread를
함께 표기한다.

## 8. 증거와 재실행 순서

| 증거 | 경로/상태 |
|---|---|
| RTX 3090 v5 binary audit | `results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.md`, historical |
| RTX 3090 v5 NCU | `results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/full_non_l2/ncu_cache_validation_summary.csv`, historical |
| A100 v5 failure | `docs/audits/a100_tensor_control_calibration_failure_20260715_ko.md`, rejected |
| v6 generated package | `results/summary/<profile>_component_finalplan_20260716_commands.sh` |

1. target node에서 current source를 clean rebuild한다.
2. `scripts/audit_tensor_mma_binary.py`로 RF1/2/4/8/16 treatment/control 10/10을
   통과한다.
3. pair calibration manifest의 trial 50 ms, ratio 6x 이하를 확인한다.
4. energy 좌표와 같은 blocks/SM, RF에서 NCU를 실행한다.
5. HMMA/FLOP 선형성, control HMMA=0, runtime work, spill=0을 통과한다.
6. 그 뒤에만 `net_E(reg_mma)-net_E(reg_operand_only)`를 pJ/FLOP로 나눈다.

이 순서를 통과하지 않은 숫자는 historical/provisional observation으로만
보관한다.
