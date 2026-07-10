# Matched-Control Component Energy

## Method

`delta_E_J = E_mode_J - (E_control_J / t_control_s) * t_mode_s`.

Only rows passing elapsed, net-energy, SMID, and optional NCU acceptance filters are summarized. Values are effective microbenchmark coefficients, not pure physical component energies.

## Inputs

| item | value |
|---|---|
| raw CSVs | `results/raw/rtx3090_strict_scope_tensor_rf8_rf16_20260708.csv` |
| acceptance CSVs | `results/summary/rtx3090_strict_scope_fresh_ncu_acceptance_20260708.csv` |
| NCU summary CSVs | `results/ncu/rtx3090_strict_scope_fresh_ncu_20260708/ncu_cache_validation_summary.csv` |
| power-state audit CSVs | `results/summary/rtx3090_strict_scope_tensor_rf8_rf16_power_state_audit_20260708.csv` |
| min elapsed (s) | 10 |
| max elapsed ratio | 1.35 |
| pairing | `nearest-control` |
| min delta_E (J) | 0 |
| min delta fraction | 0.005 |
| require NCU denominator | False |
| require total energy counter | True |
| expected power semantics | `one_sec_average` |
| exclude power-state rejects | True |

## Component Summary

| component | rows | confidence | NCU denominator rows | expected denominator rows | energy source | integration | measurement scope | power semantics | estimate unit | min | median | mean | max | stdev | IQR | CV | median CI | median pJ/bit | pJ/bit min-max | pJ/bit median CI |
|---|---:|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|

## Detail Rows

| component | W_SM (KiB) | blocks/SM | reuse | load_repeat | pair | pairing | delta_E (J) | signal fraction | denominator | denominator source | energy source | integration | measurement scope | power semantics | coeff | unit | pJ/bit | elapsed ratio | valid | diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---:|---:|---|---|

## QA

- Detail rows: 0
- Invalid detail rows: 0

## Interpretation Limits

- `register_operand_control` is a no-MMA register-fragment/control proxy, not a pure register-file bitcell value.
- For `pJ/reg-op` rows, the pJ/bit column divides by 8192 logical input bits per warp-level m16n16k16 op; it is not a measured physical register-file bit energy.
- `tensor_mma_increment` is `reg_mma - reg_operand_only`, so it is the effective MMA incremental cost under this kernel, not a pure Tensor Core transistor-level energy.
- Byte-path values are accepted only when the corresponding NCU path validation confirms hit rate/access behavior for that mode.
- `delta_signal_fraction` is `delta_E_J / max(treatment_E, scaled_control_E)`. Rows below the configured signal gate are reported but excluded from component summaries.
- `confidence_class` is a stability label from row count, relative IQR, and bootstrap median CI width. It is a reporting aid, not a claim of physical component isolation.
- Rows using `legacy_get_power_usage_integral` are fallback power estimates. For final coefficients, prefer `nvml_total_energy` with `total_energy_mj_delta` and report `nvml_power_usage_semantics` beside the result.
- When `--exclude-power-state-rejects` is used, rows marked `status=reject` or `coefficient_eligible=false` by the power-state audit are removed before treatment/control pairing. This keeps power-state drops from becoming negative component coefficients.
