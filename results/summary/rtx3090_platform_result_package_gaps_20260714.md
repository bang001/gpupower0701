# RTX3090 Platform Package Gap Report

This report explains open rows from `audit_platform_result_package.py`.
It is not a replacement for the package audit; it is a debugging guide.

| item | value |
|---|---|
| package audit CSV | `results/summary/rtx3090_platform_result_package_audit_20260714.csv` |
| result manifest CSV | `results/summary/rtx3090_component_finalplan_20260714_result_manifest.csv` |
| expected power semantics | `one_sec_average` |
| final numerator policy | `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |
| open gaps | `0` |

## Severity Counts

| severity | gaps |
|---|---:|
| `none` | 0 |

## Power API Interpretation

A package can only produce final component coefficients when the energy rows satisfy the power measurement matrix policy: `nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` and the profile-specific `nvml_power_usage_semantics=one_sec_average`. `GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power remain metadata or fallback/provisional evidence.

## Re-run Intake

```bash
python3 scripts/audit_platform_result_package.py \
  --target-profile rtx3090 \
  --tag <YYYYMMDD> \
  --expected-active-sm 82 \
  --out-csv results/summary/rtx3090_platform_result_package_audit_<YYYYMMDD>.csv \
  --out-md results/summary/rtx3090_platform_result_package_audit_<YYYYMMDD>.md \
  --fail-on-incomplete
```
