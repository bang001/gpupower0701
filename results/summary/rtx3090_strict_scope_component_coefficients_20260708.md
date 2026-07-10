# RTX 3090 Strict Measurement-Scope Component Coefficients

작성일: 2026-07-08

이 문서는 raw CSV에 `measurement_scope=gpu_device_total_energy_counter`가 명시된 strict rerun만 모은 요약이다. 값은 순수 회로 에너지가 아니라 NVML GPU/device total-energy delta와 NCU path validation을 결합한 effective microbenchmark coefficient다.

현재 환경에서는 `ncu` 실행 파일이 PATH에 없어 새 NCU replay를 수행하지 못했다. 따라서 denominator/path validation은 기존 `rtx3090_finalplan_ncu_factor_stability_20260708` sidecar와 동일 좌표를 재사용했다.

## Summary Table

| Component/path | mode pair | condition | median | unit | median CI | rows | valid/total detail | NCU denominator rows | status | confidence | cautions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tensor MMA incremental | reg_mma - reg_operand_only | RF=8,16; W_SM=2048 KiB; blocks/SM=16; seconds=20; cycles=3 | 0.129215538161 | pJ/FLOP | 0.0841495-0.137373 | 6 | 6/6 | 0 | accepted | medium | - |
| Shared scalar path | shared_scalar_load_only - clocked_empty | W_SM=64 KiB; blocks/SM=16; load_repeat=8; seconds=30; cycles=6 | 0.170589502631 | pJ/bit | 0.121988-0.202983 | 6 | 6/6 | 6 | accepted | medium | - |
| Global L1 hit path | global_l1_load_only - clocked_empty | W_SM=16 KiB; blocks/SM=16; load_repeat=4; seconds=30; cycles=6 | 0.17348298164 | pJ/bit | 0.153333-0.194437 | 6 | 6/6 | 6 | accepted | medium | - |
| L2 CG hit path | l2_cg_load_only - clocked_empty | W_SM=64 KiB; blocks/SM=16; load_repeat=4,8; seconds=30; cycles=3 | 1.13031049947 | pJ/bit | 0.860355-1.35497 | 6 | 6/6 | 6 | accepted | medium | - |

## Selection Notes

- Tensor MMA incremental: strict accepted Tensor RF8/RF16 run
- Shared scalar path: LR8-only follow-up supersedes LR4/LR8 mixed strict row; LR4/LR8 calibrated median 0.161 pJ/bit remains method-sensitivity support
- Global L1 hit path: LR4-only follow-up isolates accepted L1-hit path after LR8 weak-signal rows
- L2 CG hit path: strict accepted L2 CG hit run

## Interpretation

- Tensor, Shared LR8-only, Global L1 LR4-only, and L2는 strict rerun에서 reliability gate가 `accepted`다.
- Shared LR8-only median 0.171 pJ/bit는 LR4/LR8 calibrated median 0.161 pJ/bit와 정합한다. LR4/LR8 mixed run은 9/10 valid였으므로 method-sensitivity support로 남긴다.
- L1 LR4-only median 0.173 pJ/bit와 L2 median 1.130 pJ/bit는 L1 < L2 계층 순서와 정합한다.
- 모든 row의 energy numerator는 `nvml_total_energy` + `total_energy_mj_delta`이고, `measurement_scope`는 `gpu_device_total_energy_counter`다.
- RTX 3090의 `GetPowerUsage` fallback 의미는 `one_sec_average`지만, 이 strict 표의 numerator는 endpoint fallback power가 아니다.

## Artifacts

- Tensor MMA incremental: `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_matched_control_summary_20260708.csv`, `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_component_reliability_audit_20260708.csv`, `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_instability_audit_20260708.md`
- Shared scalar path: `results/summary/rtx3090_strict_scope_shared_lr8_focus_matched_control_summary_20260708.csv`, `results/summary/rtx3090_strict_scope_shared_lr8_focus_component_reliability_audit_20260708.csv`, `results/summary/rtx3090_strict_scope_shared_lr8_focus_instability_audit_20260708.md`
- Global L1 hit path: `results/summary/rtx3090_strict_scope_l1_lr4_focus_matched_control_summary_20260708.csv`, `results/summary/rtx3090_strict_scope_l1_lr4_focus_component_reliability_audit_20260708.csv`, `results/summary/rtx3090_strict_scope_l1_lr4_focus_instability_audit_20260708.md`
- L2 CG hit path: `results/summary/rtx3090_strict_scope_l2_lr4_lr8_focus_matched_control_summary_20260708.csv`, `results/summary/rtx3090_strict_scope_l2_lr4_lr8_focus_component_reliability_audit_20260708.csv`, `results/summary/rtx3090_strict_scope_l2_lr4_lr8_focus_instability_audit_20260708.md`
- Shared LR4/LR8 calibrated support: `results/summary/rtx3090_strict_scope_shared_lr4_lr8_calibrated_matched_control_report_20260708.md`, `results/summary/rtx3090_strict_scope_shared_lr4_lr8_calibrated_component_reliability_audit_20260708.md`
