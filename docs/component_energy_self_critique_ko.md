# Component Energy 실험 자가비판

작성일: 2026-07-06

## 1. 가장 큰 오류

| 오류 | 왜 문제였나 | 현재 수정 |
|---|---|---|
| `W_SM`을 `reg_mma` register working set처럼 설명 | register footprint는 `W_SM`이 아니라 ptxas register/thread, threads/block, blocks/SM로 결정된다. | register-mode에서 `W_SM`은 고정 좌표로만 취급한다. |
| `reg_pressure` direct pJ/update를 register energy처럼 해석 | scalar ALU, dependency chain, scheduler/control, active power가 포함된다. | register 결과는 `register/control diagnostic only`로 격하했다. |
| 일반 `l2_load_only`를 RTX 3090 L2로 해석 | NCU에서 L1 hit가 높아 L2-only가 아니었다. | RTX 3090/V100 L2는 `l2_cg_load_only`를 우선 사용한다. |
| `shared_load_only`를 clean shared path로 사용 | NCU에서 bank conflict가 컸다. | `shared_scalar_load_only`를 primary shared path로 사용한다. |
| static expected bytes로 pJ/bit 계산 | 실제 L1/L2/DRAM sector traffic과 다를 수 있다. | NCU actual-byte denominator를 분석에 반영했다. |
| 음수 coefficient를 늦게 문제 삼음 | control mismatch와 power-state noise가 있다는 직접 증거다. | 음수 row는 final coefficient에서 제외한다. |
| HBM2 physical pJ/bit와 RTX 3090 GDDR6X path를 섞어 비교 | device-level DRAM energy와 GPU transaction-path effective energy는 의미가 다르다. | DRAM은 streaming sanity로만 보고한다. |

## 2. 현재 코드/분석에서 여전히 약한 부분

| 약점 | 영향 | 필요한 추가 실험 |
|---|---|---|
| NCU sidecar가 representative LR=4 중심 | 모든 load_repeat/reuse row의 actual traffic을 직접 검증하지 못한다. | final run에서는 좌표별 NCU sidecar 확장 |
| Tensor acceptance threshold가 absolute byte 기준 | SM 수가 다른 A100/H100에서 threshold가 주관적일 수 있다. | bytes/FLOP 또는 bytes/HMMA ratio 기준 추가 |
| `clocked_empty` control이 모든 memory path에 완전 matched가 아님 | 일부 L1 row에서 음수/큰 분산이 발생한다. | address-only/control instruction mix를 더 맞춘 pair 추가 |
| NVML energy source가 GPU별로 다름 | `GetPowerUsage` semantics와 energy counter support가 다르다. | `energy_source`, `nvml_power_usage_semantics`를 결과 표에 항상 포함 |
| H100에서 Hopper-native 경로 미구현 | WGMMA/TMA/FP8 energy를 측정하지 않는다. | 별도 H100-native kernel set 설계 |
| V100 NCU 지원 버전 이슈 | NCU hit/stall 검증이 실패할 수 있다. | 지원되는 NCU toolchain 명시, 실패 시 energy-only로 분리 보고 |

## 3. 현재 믿을 수 있는 것과 없는 것

| 항목 | 현재 신뢰도 | 이유 |
|---|---|---|
| NCU accepted path가 의도한 memory hierarchy를 탔다 | 높음 | hit rate, bytes, stall, bank conflict로 확인 가능 |
| RTX 3090 finalplan의 계층 순서 L1/shared < L2 < DRAM | 중간 이상 | NCU actual-byte denominator와 positive rows 기반 |
| Tensor incremental pJ/FLOP | 중간 | HMMA와 no-MMA control은 있으나 pure Tensor 단독은 아님 |
| Register file pJ/access | 낮음 | 현재 구현은 pure RF isolation이 아니다 |
| Physical DRAM device pJ/bit | 낮음 | NVML board-level streaming delta일 뿐이다 |

## 4. 플랫폼 확장 시 원칙

| 원칙 | 이유 |
|---|---|
| RTX 3090 결과를 A100/V100/H100에 이식하지 않는다. | cache/shared/L2/memory/NVML semantics가 다르다. |
| 각 플랫폼에서 preflight와 NCU acceptance를 먼저 본다. | profile 가정과 실제 노드 상태가 다를 수 있다. |
| `l2_load_only`는 NCU L1 hit가 낮을 때만 채택한다. | capacity 계산만으로는 L2-only가 보장되지 않는다. |
| H100 결과는 WMMA compatibility path라고 명시한다. | H100 native WGMMA/TMA와 다르다. |
| 최종 표에는 rejected row와 이유를 함께 남긴다. | 수치를 숨기면 설계 실패를 확인할 수 없다. |

## 5. 다음 코드 개선 제안

| 우선순위 | 개선 | 목적 |
|---:|---|---|
| 1 | `analyze_ncu_path_acceptance.py`에 bytes/FLOP ratio threshold 추가 | Tensor/register absolute threshold 문제 완화 |
| 2 | `run_ncu_validation.sh`가 load_repeat/reuse sweep list를 직접 받도록 확장 | representative-only NCU 문제 완화 |
| 3 | L1/global control용 `global_addr_load_control` 추가 | `clocked_empty` mismatch 축소 |
| 4 | H100-native WGMMA/TMA mode 추가 | Hopper 구조 반영 |
| 5 | report generator 추가 | 플랫폼별 결과 표준화 |
