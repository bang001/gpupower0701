# GPU Power Modeling 실험 결과 상태

갱신일: 2026-07-12

## 현재 결론

현재 저장소에는 **현행 protocol을 모두 통과한 RTX 3090 component coefficient가
없다**. 2026-07-08 결과는 유효한 실험 이력이지만 Global L1/L2 energy pair가
`clocked_empty` control을 사용했고, `global_addr_only`의 동일 좌표 NCU acceptance와
현행 path-specific counter schema가 없다.

따라서 아래 과거 수치는 현행 final 값으로 인용하지 않는다.

| Component/path | 과거 보고값 | 단위 | 과거 pair | 현행 상태 |
|---|---:|---|---|---|
| Tensor MMA incremental | 0.129216 | pJ/FLOP | `reg_mma - reg_operand_only` | historical; 현행 pair-lock/control gate 재실행 필요 |
| Shared scalar path | 0.170590 | pJ/bit | `shared_scalar_load_only - clocked_empty` | historical; 전체 package 재실행 필요 |
| Global L1 hit path | 0.173483 | pJ/bit | `global_l1_load_only - clocked_empty` | provisional; address control 누락 |
| L2 CG hit path | 1.131073 | pJ/bit | `l2_cg_load_only - clocked_empty` | provisional; address control 누락 |
| DRAM cumulative effective path | **26.709-28.409** | pJ/bit | 목표: `dram_cg_load_only - global_addr_only` matched ITER | `provisional_reference_aligned_range`; 현행 raw pair가 없어 strict 실측값 아님 |

DRAM 범위를 제외한 과거 값들은 pure circuit/bitcell energy가 아니라 당시 NVML
total-energy 차분과 NCU treatment-path evidence로 얻은 effective microbenchmark
coefficients였다. DRAM 범위는 최신 보고 정책이며, accepted 측정값이 아니다.

![RTX 3090 DRAM 최신 provisional 보고 범위](../assets/component_energy_method/current_dram_reporting_band.png)

과거 `clocked_empty` DRAM 수치는 pJ/byte에서 pJ/bit로 환산한 산술 자체보다 control
정책이 문제다. 현행 설계는 동일 ITER의 address control을 요구하므로 그 값을 최신
DRAM coefficient로 재사용하지 않는다. 상세 정책은
`results/summary/rtx3090_dram_current_reporting_policy_20260712.md`를 따른다.

과거 전체 표, sweep, 그래프, 해석은
`archive/pre_current_protocol_20260712/docs/gpu_power_modeling_experiment_results_ko.md`에
보존한다. 옛 DRAM 막대가 최신값처럼 보이지 않도록 historical coefficient 그림은
active 결과 문서에서 제거했다.

## 현행 재감사 결과

| Audit | 결과 | 의미 |
|---|---:|---|
| old strict summary current-protocol reaudit | 181 pass, 8 fail | old path-specific schema와 address-control evidence 부족 |
| current goal readiness | 4 fail, 6 missing, 0 warning | RTX 3090 재실행 및 외부 V100/A100/H100 결과 필요 |
| platform implementation readiness | all pass | profile/command package 구현은 정적 기준 통과 |

근거:

- `results/summary/rtx3090_current_protocol_reaudit_20260712.md`
- `results/summary/component_energy_goal_readiness_audit_20260712.md`
- `docs/audits/current_goal_alignment_audit_ko.md`

## RTX 3090 재실행 조건

| Component | modes | energy W_SM (KiB/SM) | energy blocks/SM | strict NCU W/B | sweep |
|---|---|---:|---|---|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 8,16 | 2048/8 | RF 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 32,64 | 8,16 | 64/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| Global L1 | `global_addr_only,global_l1_load_only` | 8,16 | 8,16 | 8/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 64 | 8,16 | 64/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | 8,16 | 8192/8 | LR 4,8,16; NCU 1,4,8,16 |

공통 energy 조건은 target 10 s, 5 repeats다. Tensor와 DRAM은 treatment/control-floor
dual calibration 후 큰 동일 ITER를 두 mode에 적용한다. Final analyzer는
`--require-control-ncu-acceptance`를 사용한다.

실행:

```bash
bash results/summary/rtx3090_component_finalplan_20260712_commands.sh
```

NCU 권한 오류가 있을 때만 NCU 경로를 sudo로 실행한다.

```bash
NCU_USE_SUDO=1 bash results/summary/rtx3090_component_finalplan_20260712_commands.sh
```

상세 명령과 acceptance 기준은
`results/summary/rtx3090_component_finalplan_20260712_command_plan.md`를 따른다.

## Final 인정 조건

1. Power row가 explicit GPU/device total-energy counter scope를 사용한다.
2. Tensor/Shared/Global L1/L2 treatment NCU path가 exact coordinate에서 accepted다.
3. `reg_operand_only`와 `global_addr_only` control도 같은 좌표에서 accepted다.
4. Memory denominator가 `ncu_actual_exact`이고 단위가 표에 기록된다.
5. matched-control, reliability, strict summary, strict summary audit, package audit가
   모두 통과한다.
6. 숫자의 hierarchy가 그럴듯하다는 이유로 실패 gate를 무시하지 않는다.

새 결과가 생성되기 전까지 보고서에는 “RTX 3090 historical/provisional result”라고
표기한다.
