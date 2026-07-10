# V100 Component Finalplan Command Plan

Generated: 2026-07-10

| item | value |
|---|---|
| target profile | `v100` |
| CUDA arch | `sm_70` |
| active_SM (SMs) | `80` |
| blocks/SM | `16,32` |
| expected power semantics | `instant` |
| seconds (s) | `10.0` |
| repeats | `5` |
| binary | `./build-v100/a100_fp16_energy_v2` |
| NCU | `ncu` |
| NCU sudo fallback | `NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh` |
| generated shell | `results/summary/v100_component_finalplan_20260708_commands.sh` |

## Platform Note

Volta path. Use an NCU toolchain whose --list-chips includes gv100.

## Build Requirement

Build the benchmark for `sm_70` before running the generated
shell. The preflight dry-run rejects a binary built for the wrong compute
capability, but using a profile-specific build directory avoids wasting the
target node allocation.

```bash
cmake -S . -B build-v100 -DCMAKE_CUDA_ARCHITECTURES=70
cmake --build build-v100 --clean-first -j
```

Use a clean rebuild after every `git pull` that changes `src/`, `include/`, or
`CMakeLists.txt`. In particular, raw CSVs for final runs must be produced by a
binary whose CSV header includes `measurement_scope`.

## Component Coordinates

| component/path | modes | W_SM (KiB) | factor |
|---|---|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | reuse 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 32,64 | energy load_repeat 4,8,16; NCU also checks 1,2 |
| Global L1 | `global_addr_only,global_l1_load_only` | 8,16 | energy load_repeat 4,8,16; NCU also checks 1,2 |
| L2 | `global_addr_only,l2_cg_load_only` | 64 | energy load_repeat 4,8,16; NCU also checks 1,2 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | energy load_repeat 4,8,16; NCU checks 1,4,8,16 |

## Architecture-Specific NCU Evidence

The generated package is not valid from hit rate alone. Every V100/A100/H100
run must keep the architecture-specific NCU sidecar and acceptance report with
both cache-hit direction and traffic magnitude:

| evidence | required columns | unit / meaning |
|---|---|---|
| L1 hit direction | `l1_hit_rate_pct` | percent |
| L2 hit direction | `l2_hit_rate_pct` | percent |
| access magnitude | `l1_accesses`, `l2_accesses`, `dram_accesses` | L1 requests when available, otherwise sectors; L2/DRAM sectors |
| byte magnitude | `shared_bytes`, `l1_bytes`, `l2_bytes`, `dram_bytes` | bytes, preferred denominator for memory pJ/byte or pJ/bit |
| stall context | `stall_long_scoreboard_pct` | percent-like NCU stall signal |

V100 uses `NCU_CHIP=gv100` and uses `l2_cg_load_only` as the L2 final path.
A100 uses `NCU_CHIP=ga100`; its final L2 point is intentionally below the 40 MiB
L2 capacity and uses `ld.global.cg` to bypass global L1. `l2_load_only` follows
the normal global-load policy, can hit L1, and is therefore diagnostic-only rather
than strict L2 evidence. H100 uses `NCU_CHIP=gh100`; the current kernels are WMMA
compatibility kernels, so the NCU evidence validates the executed compatibility
path, not Hopper-native WGMMA/TMA/FP8 paths.

## How To Run

```bash
bash results/summary/v100_component_finalplan_20260708_commands.sh
```

If Nsight Compute fails with `ERR_NVGPUCTRPERM`, the account does not have GPU
performance-counter permission. The preferred fix is administrator-side access
to non-admin GPU performance counters. For a temporary target-node run, rerun
only the NCU wrapper path through sudo:

```bash
NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh
```

If `sudo` does not preserve the CUDA/Nsight Compute environment, make the NCU
binary explicit and preserve the environment:

```bash
NCU_BIN="$(command -v ncu)" NCU_USE_SUDO=1 NCU_SUDO="sudo -E" bash results/summary/v100_component_finalplan_20260708_commands.sh
```

The generated shell keeps NVML energy sweeps detached from NCU. The sudo
fallback is only for the NCU sidecar/preflight/goal-readiness commands; failed
NCU evidence must not be replaced with unvalidated denominators in final
component coefficients.

The generated NCU sidecar profiles primary finalplan modes at every energy
`reuse_factor`/`load_repeat` coordinate and includes 1,2 as lower-signal
diagnostic points. This lets `analyze_matched_control_energy.py` prefer
`ncu_actual_exact` denominators instead of representative same-working-set
scaling. The global-memory pairs use `global_addr_only` as a matched address
control; NCU verifies global-load L1 bytes are zero and treats SMID atomic L2
sectors as control bookkeeping rather than input traffic. Legacy diagnostic
modes such as `l2_load_only`, `shared_mma`, `l2_mma`, and `dram_mma` are not
profiled unless `INCLUDE_DIAGNOSTIC_NCU=1` is set manually.

For a quick profiler preflight only, override the sidecar lists manually, for
example `TENSOR_REUSE_FACTORS=4 MEMORY_LOAD_REPEATS=4 DRAM_LOAD_REPEATS=4`.

Before the energy sweeps, the generated shell moves stale generated artifacts
for this profile/tag into `results/archive/..._stale_<timestamp>`. This avoids
appending new rows to an old CSV schema. It then runs a one-row schema smoke
test and audits that row with `--require-explicit-measurement-scope`. If the
binary is stale and the CSV header lacks `measurement_scope`, the script stops
there instead of producing thousands of unusable rows.

Before the schema smoke and energy sweeps, the generated shell runs
`scripts/audit_power_api_measurements.py --self-test` and
`scripts/build_strict_component_summary.py --self-test` and
`scripts/audit_strict_component_summary.py --self-test` so the A100 semantics,
fallback-numerator, explicit-scope, H100 module-scope, strict NCU artifact
selection, and strict NCU coordinate-alignment checks fail early if the gates
themselves regress. Before NCU, it then runs
`scripts/audit_power_api_measurements.py` on the raw energy CSVs. This applies
the rules in
`docs/platforms/power_measurement_api_matrix_ko.md`: final coefficients require
`energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`,
`measurement_scope=gpu_device_total_energy_counter`, and the expected profile
power semantics. The generated command also requires raw CSVs to contain an
explicit `measurement_scope` column/value; inferred scope is history/provisional
only. Fallback `GetPowerUsage` rows fail the generated finalplan script and
must be reported separately as provisional.

After matched-control analysis, the generated shell runs
`scripts/audit_component_reliability.py`. This joins the power API audit, NCU
path acceptance, and matched-control summary/detail into component-level verdicts
such as `accepted`, `accepted_with_caution`, `accepted_low_stability`, and
`accepted_sanity`.

Matched-control consumes the generated power-state audit CSV with
`--exclude-power-state-rejects`, so rows flagged as `status=reject` or
`coefficient_eligible=false` are removed before treatment/control pairing. This
keeps power-state drops from appearing as negative component coefficients.

It also runs `scripts/audit_matched_control_instability.py` to explain weak
signal or negative matched-control rows and to suggest targeted follow-up runs.

Finally, the generated shell runs `scripts/build_strict_component_summary.py`,
`scripts/audit_strict_component_summary.py`, and
`scripts/audit_platform_result_package.py`. The builder copies accepted
reliability medians into
`results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.csv`
and records matched-control, power API, power-state, NCU acceptance, NCU summary,
and instability artifacts. The audit verifies that the packaged summary still
matches the underlying evidence and the power measurement matrix. It also fails
hierarchy/order mistakes such as L2 <= shared/global L1 and broad
order-of-magnitude mistakes outside the strict plausibility ranges.
The package intake audit then checks the raw energy CSVs, power API audit,
power-state audit, NCU acceptance, matched-control detail, reliability audit,
strict summary, and strict summary audit as one profile/tag package before the
result is copied back or published. It also checks that raw CSV rows carry the
target profile metadata (`chip`, `compute_capability`, L2 size, L1/shared
capacity) and the generated `active_SM` value. If a target node uses MIG,
partitioning, or an SKU with fewer visible SMs, regenerate this plan with
`--active-sm <runtime SM count>` after preflight and keep the same value in the
package audit.
The package audit also verifies that the NCU summary exposes L1/L2 hit rates,
L1/L2/DRAM access counts, byte traffic, and long-scoreboard stall counters
before the result can be treated as final evidence. Hit rate alone is not enough:
accepted cache rows must also show path-relevant access/byte magnitude. The NCU
summary must include
`clocked_empty`, `reg_operand_only`, `reg_mma`, `shared_scalar_load_only`,
`global_l1_load_only`, `l2_cg_load_only`, and `dram_cg_load_only` coverage.
A100/H100 packages use `l2_cg_load_only` as the strict L2 path; `l2_load_only`
is diagnostic-only and is not required. Tensor pair NCU rows need at least three
`reuse_factor` points, and memory-path rows need at
least three `load_repeat` points.
The package audit requires the strict summary audit CSV to contain
`hard_plausibility_range`, `l2_greater_than_shared`, `l2_greater_than_l1`, and
`shared_l1_same_order`, so stale pre-plausibility audit artifacts do not pass.
It also requires `ncu_summary_counter_schema`,
`ncu_summary_coordinate_alignment`, and `ncu_evidence_summary_fields`: the strict
summary must point to NCU summary artifacts with cache hit-rate/access/byte/stall
columns, the accepted NCU mode rows must match the matched-control energy
coordinates, and the report row itself must expose path-relevant NCU evidence.
`build_strict_component_summary.py` uses component-specific NCU artifact
selection so, for example, a Tensor row cannot accidentally cite a sidecar
captured with different `blocks/SM` or `reuse_factor`. Shared scalar rows report
shared-memory byte/access evidence separately from background global L1/L2
hit-rate counters.
Before copying results back from the target node, use
`scripts/write_platform_result_manifest.py` to generate a transfer checklist for
all raw, power, NCU, matched-control, reliability, strict summary, and audit
artifacts expected by the package audit. The generated shell now writes this
manifest automatically before package intake.
If the package audit reports `missing` or `fail`, run
`scripts/summarize_platform_package_gaps.py` with the package audit CSV and
result manifest CSV using the same `--tag` as the platform package. The gap
report does not approve results; it maps each open row to the failed stage and
explains whether the issue is a missing artifact, a power measurement matrix
violation, an NCU path problem, or a strict summary/reliability problem.
The generated shell captures the package
audit exit code, still writes the gap report, and exits with the package audit
status after the diagnostic reports are written.
After multiple platform packages are copied back, run
`scripts/build_platform_intake_dashboard.py` to summarize RTX 3090, V100, A100,
and H100 package status, first open stage, and strict summary status in one
table. The generated shell first runs
`scripts/audit_component_goal_readiness.py --self-test` plus the full goal
readiness audit, then refreshes the dashboard so the target-node result bundle
records both validator health and the latest cross-platform intake status.

Review the NCU acceptance report before treating any coefficient as usable.
Values are board-level effective coefficients, not pure physical bitcell energy.
