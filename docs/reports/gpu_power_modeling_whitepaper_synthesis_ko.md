# GPU Power Modeling 백서용 종합 정리

갱신일: 2026-07-12

## 핵심 주장

이 연구는 NVIDIA GPU 내부 transistor/bitcell energy를 직접 측정하지 않는다. CUDA
microbenchmark를 treatment-control pair로 실행하고, NVML GPU/device total-energy
delta에서 공통 비용을 차분한 뒤, NCU counter로 실행 경로와 traffic denominator를
검증해 **workload-dependent effective board-level energy coefficient**를 추정한다.

안전한 표현:

```text
NCU로 treatment와 control 경로가 검증된 board-level effective microbenchmark coefficient
```

피해야 할 표현:

```text
순수 Tensor Core 회로 에너지
순수 register-file access energy
순수 L1/L2 SRAM bitcell energy
순수 DRAM/HBM device energy
```

## Component 정의

| Component | treatment | control | 단위 | 해석 |
|---|---|---|---|---|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | pJ/FLOP | no-MMA register/control 대비 FP16 WMMA/HMMA 증분 |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | pJ/bit | software-managed shared scalar-load path |
| Global L1 hit path | `global_l1_load_only` | `global_addr_only` | pJ/bit | global load가 L1 hit로 끝나는 path |
| L2 CG hit path | `l2_cg_load_only` | `global_addr_only` | pJ/bit | L1 hit를 낮춘 L2 read-hit path |
| DRAM cumulative effective path | `dram_cg_load_only` | `global_addr_only` | pJ/bit | 26.709-28.409 provisional reporting band; strict 4-component 표 제외, matched-ITER 실측 필요 |

Shared와 Global L1은 unified L1/shared subsystem과 관련되지만 주소 공간, instruction
path, arbitration, denominator가 다르므로 별도 effective coefficient로 보고한다.

## 측정 및 검증 구조

```text
profile/preflight
  -> treatment/control sweep
  -> NVML total-energy delta + idle subtraction
  -> NCU sidecar: HMMA, shared bytes, L1/L2 hit+bytes, DRAM bytes, spill, stall
  -> treatment와 control의 exact-coordinate acceptance
  -> matched-control coefficient
  -> reliability + strict summary + package audit
```

Tensor와 DRAM은 동일 ITER의 net energy를 직접 차분한다. Shared/Global L1/L2는
elapsed-aware control-power 차분을 사용한다. 모든 memory final row는 NCU actual bytes를
분모로 사용한다.

## 현재 결과 상태

현행 protocol을 모두 통과한 RTX 3090/V100/A100/H100 coefficient table은 아직 없다.

| Platform | command readiness | measured current-protocol package | 상태 |
|---|---|---|---|
| RTX 3090 | ready | Tensor fixed-RF v2 standalone | Tensor 33 valid pair/NCU 10/10 통과; Shared/Global-L1/L2 전체 package는 재실행 필요 |
| V100 32GB | ready | 없음 | target node 실행/반입 필요 |
| A100 | ready | 없음 | target node 실행/반입 필요 |
| H100 | ready | 없음 | target node 실행/반입 필요 |

기존 RTX 3090 strict summary를 현행 기준으로 재감사한 결과는 189 checks 중 8
failures다. Global L1/L2의 `clocked_empty` control과 과거 NCU schema가 원인이다.

| 과거 path | 과거 값 | 단위 | 현행 해석 |
|---|---:|---|---|
| Tensor MMA incremental | 0.129216 | pJ/FLOP | historical evidence |
| Shared scalar | 0.170590 | pJ/bit | historical evidence |
| Global L1 | 0.173483 | pJ/bit | provisional; address control 없음 |
| L2 CG | 1.131073 | pJ/bit | provisional; address control 없음 |
| DRAM cumulative path | **26.709-28.409** | pJ/bit | provisional reference-aligned band; matched-ITER DRAM raw pair 없음 |

현행 standalone Tensor는 fixed-RF v2에서 median **2.252501 pJ/FLOP**, 범위
**1.945385-2.369221 pJ/FLOP**이다. 모든 RF treatment의 `HMMA/logical MMA=2`,
control HMMA=0, local read/write=0이다. 이 값은 pure Tensor 회로 에너지가 아니라
board-level effective MMA incremental coefficient이다. 상세는
`results/summary/rtx3090_tensor_fixedrf_v2_report_20260713_ko.md`를 따른다.

DRAM 범위는 strict coefficient가 아니다. 목표 pair는
`dram_cg_load_only - global_addr_only`이며, 동일 ITER의 energy 차분과 exact NCU
`dram_bytes * 8` 분모를 확보하기 전에는 범위로만 보고한다.

과거 결과의 전체 분석과 시각화는
`archive/pre_current_protocol_20260712/docs/gpu_power_modeling_whitepaper_synthesis_ko.md`와
`archive/pre_current_protocol_20260712/docs/gpu_power_modeling_experiment_results_ko.md`에
보존한다.

## 보고 원칙

최종 표에는 반드시 다음 열을 포함한다.

| 필드 | 이유 |
|---|---|
| GPU/profile, SM 수 | architecture/runtime 조건 고정 |
| treatment-control pair | coefficient 의미 결정 |
| W_SM (KiB/SM), blocks/SM, RF/LR | sweep 좌표와 occupancy/working-set 해석 |
| seconds (s), repeats (count), ITER | 측정 신호와 work-count 검증 |
| NCU treatment/control acceptance | path와 control contamination 검증 |
| denominator source와 bytes/FLOP | pJ 단위 계산 추적 |
| min/median/mean/max, CI, valid/invalid rows | 분산과 재현성 표시 |
| NVML source/integration/scope | GPU 세대별 API 의미 구분 |
| long-scoreboard stall | memory-path stall context 표시 |

문헌 pJ/bit는 sanity/order-of-magnitude 비교에만 사용한다. GPUJoule의 transaction-path
값과 HBM device/access 값은 measurement boundary가 다르므로 목표값으로 fitting하지
않는다.

## 다음 실험

1. RTX 3090은 `results/summary/rtx3090_component_finalplan_20260712_commands.sh`로
   현행 protocol을 재실행한다.
2. V100/A100/H100은 각 generated command package를 target node에서 실행한다.
3. 결과 반입 후 `scripts/run_local_readiness_checks.sh`를 실행한다.
4. 모든 strict/package gate가 통과한 플랫폼만 component table과 visualization을 만든다.

현재 감사 근거는 `docs/audits/current_goal_alignment_audit_ko.md`와
`results/summary/component_energy_goal_readiness_audit_20260712.md`다.
