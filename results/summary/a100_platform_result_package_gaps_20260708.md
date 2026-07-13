# A100 Platform Package Gap Report

This report explains open rows from `audit_platform_result_package.py`.
It is not a replacement for the package audit; it is a debugging guide.

| item | value |
|---|---|
| package audit CSV | `results/summary/a100_platform_result_package_audit_20260708.csv` |
| result manifest CSV | `results/summary/a100_component_finalplan_20260708_result_manifest.csv` |
| expected power semantics | `instant` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| open gaps | `16` |

## Severity Counts

| severity | gaps |
|---|---:|
| `blocker` | 16 |

## Next Actions

| stage | severity | status | issue | evidence | corrective action | next command |
|---|---|---|---|---|---|---|
| preflight | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_preflight.md (node preflight report)` | Run strict preflight on the target node with the explicit profile, expected active SM count, binary path, and NCU path, then copy the markdown report back. | `python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile a100 --strict --active-sm 108 --binary ./build-a100/a100_fp16_energy_v2 --ncu "$(command -v ncu || echo ncu)" --out results/summary/a100_component_finalplan_20260708_preflight.md` |
| raw energy | `blocker` | `missing` | no_raw_rows_read | `results/raw/a100_component_finalplan_20260708_tensor.csv;results/raw/a100_component_finalplan_20260708_shared.csv;results/raw/a100_component_finalplan_20260708_l1.csv;results/raw/a100_component_finalplan_20260708_l2.csv;results/raw/a100_component_finalplan_20260708_dram.csv (raw energy CSVs)` | Run the generated command shell on the target GPU node and copy all tensor/shared/L1/L2/DRAM raw CSV files. | `bash results/summary/a100_component_finalplan_20260708_commands.sh` |
| raw energy | `blocker` | `missing` | missing=results/raw/a100_component_finalplan_20260708_tensor.csv;results/raw/a100_component_finalplan_20260708_shared.csv;results/raw/a100_component_finalplan_20260708_l1.csv;results/raw/a100_component_finalplan_20260708_l2.csv;results/raw/a100_component_finalplan_20260708_dram.csv | `results/raw/a100_component_finalplan_20260708_tensor.csv;results/raw/a100_component_finalplan_20260708_shared.csv;results/raw/a100_component_finalplan_20260708_l1.csv;results/raw/a100_component_finalplan_20260708_l2.csv;results/raw/a100_component_finalplan_20260708_dram.csv (raw energy CSVs)` | Run the generated command shell on the target GPU node and copy all tensor/shared/L1/L2/DRAM raw CSV files. | `bash results/summary/a100_component_finalplan_20260708_commands.sh` |
| power API | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_power_api_audit.csv (power API audit)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/audit_power_api_measurements.py ... --fail-on-provisional --require-explicit-measurement-scope` |
| power state | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_power_state_audit.csv (power-state stability audit)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/audit_power_state_stability.py ...` |
| NCU summary | `blocker` | `missing` | missing | `results/ncu/a100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv (NCU counter summary)` | Run the NCU sidecar on the target GPU and summarize cache/path counters before copying results back. | `bash scripts/run_ncu_validation.sh && python3 scripts/summarize_ncu_cache_metrics.py ...` |
| NCU path acceptance | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv (NCU path acceptance)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/analyze_ncu_path_acceptance.py ...` |
| matched-control | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_matched_control_detail.csv (matched-control detail)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/analyze_matched_control_energy.py ... --require-ncu-denominator --require-total-energy` |
| matched-control | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_matched_control_summary.csv (matched-control summary)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/analyze_matched_control_energy.py ... --require-ncu-denominator --require-total-energy` |
| component reliability | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_component_reliability_audit.csv (component reliability audit)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/audit_component_reliability.py ...` |
| instability diagnosis | `blocker` | `missing` | missing | `results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.csv (instability audit)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/audit_matched_control_instability.py ...` |
| strict summary | `blocker` | `missing` | missing | `results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.csv (strict component coefficient summary)` | Generate or copy the missing artifact listed in the package audit and manifest. | `python3 scripts/build_strict_component_summary.py ...` |
| strict summary audit | `blocker` | `missing` | missing | `results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv (strict component summary audit)` | Run `scripts/audit_strict_component_summary.py --fail-on-fail` after building the strict summary. | `python3 scripts/audit_strict_component_summary.py ... --fail-on-fail` |
| other | `blocker` | `missing` | missing | `results/raw/a100_component_finalplan_20260708_dram_pair_calibration.csv (DRAM pair calibration manifest)` | Generate or copy the missing artifact listed in the package audit and manifest. | `` |
| other | `blocker` | `missing` | missing | `results/raw/a100_component_finalplan_20260708_l2_pair_calibration.csv (L2 pair calibration manifest)` | Generate or copy the missing artifact listed in the package audit and manifest. | `` |
| other | `blocker` | `missing` | missing | `results/raw/a100_component_finalplan_20260708_tensor_pair_calibration.csv (Tensor pair calibration manifest)` | Generate or copy the missing artifact listed in the package audit and manifest. | `` |

## Power API Interpretation

A package can only produce final component coefficients when the energy rows satisfy the power measurement matrix policy: `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` and the profile-specific `nvml_power_usage_semantics=instant`. `GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power remain metadata or fallback/provisional evidence.

## Re-run Intake

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile a100 \
  --tag <YYYYMMDD> \
  --expected-active-sm 108 \
  --out-csv results/summary/a100_platform_result_package_audit_<YYYYMMDD>.csv \
  --out-md results/summary/a100_platform_result_package_audit_<YYYYMMDD>.md \
  --fail-on-incomplete
```
