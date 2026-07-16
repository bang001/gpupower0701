# RTX3090 Component Finalplan Command Plan

Generated: 2026-07-16

| item | value |
|---|---|
| target profile | `rtx3090` |
| CUDA arch | `sm_86` |
| active_SM (SMs) | `82` |
| energy sweep blocks/SM | `8` |
| Tensor energy/NCU blocks/SM | `4,8,16` |
| strict NCU blocks/SM | `8` |
| L2 strict blocks/SM | `8` |
| L2 NCU-first selector | `fixed reviewed coordinate` |
| expected power semantics | `one_sec_average` |
| minimum visible device memory (MiB) | `0` |
| seconds (s) | `10.0` |
| repeats | `5` |
| pair max treatment stretch | `6.0` x target duration |
| per-command wall-time guard (s) | `180.0` |
| max pair transition gap (ms) | `30000` (`max(30000, (seconds + 15) x 1000)`) |
| Tensor control calibration floor (s) | `1.0` |
| Shared address-control calibration floor (s) | `1.0` |
| Global-L1 address-control calibration floor (s) | `1.0` |
| DRAM address-control calibration floor (s) | `1.0` |
| binary | `./build/a100_fp16_energy_v2` |
| NCU | `ncu` |
| CUDA binary inspector | selected `nvcc` toolkit's sibling `cuobjdump`; override with `CUOBJDUMP=/absolute/path` |
| NCU counter permission probe | baseline hardware-counter profile before energy sweep |
| NCU automatic sudo retry | enabled by default with `NCU_AUTO_SUDO=1` |
| NCU sudo fallback | `NCU_USE_SUDO=1 bash results/summary/rtx3090_component_finalplan_20260716_commands.sh` |
| Memory NCU metric profiles | L2/external use `l2_path_minimal`; Tensor/Shared/Global-L1 use `full`; disjoint rows are merged with provenance |
| generated shell | `results/summary/rtx3090_component_finalplan_20260716_commands.sh` |

## Platform Note

RTX 3090 / GA102 GDDR6X path. External-memory W_SM sweep spans about 3.4x-27.3x nominal L2. Use total-energy rows; GetPowerUsage fallback has one-second-average semantics.



## Build Requirement

Build the benchmark for `sm_86` before running the generated
shell. The preflight dry-run rejects a binary built for the wrong compute
capability, but using a profile-specific build directory avoids wasting the
target node allocation.

```bash
cmake -S . -B build -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build build --clean-first -j
```

Use a clean rebuild after every `git pull` that changes `src/`, `include/`, or
`CMakeLists.txt`. In particular, raw CSVs for final runs must be produced by a
binary whose CSV header includes `measurement_scope`.

## Component Coordinates

| component/path | modes | energy W_SM (KiB) | strict NCU W_SM/B | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 1 (CLI placeholder; memory W_SM N/A) | 1/4,8,16 | reuse 1,2,4,8,16; every energy B has exact-coordinate NCU; pair-locked ITER |
| Shared scalar | `shared_scalar_addr_only,shared_scalar_load_only` | 64 | 64/8 | energy and NCU load_repeat 4,8,16; dual-calibrated equal ITER |
| Global L1 | `global_addr_only,global_l1_load_only` | 8 | 8/8 | energy and NCU load_repeat 4,8,16; dual-calibrated equal ITER |
| L2 | `global_addr_only,l2_cg_load_only` | 32,64 | 32,64/8 | energy and final NCU load_repeat 4,8,16; selector probes LR4; treatment/control-floor dual-calibrated pair-locked ITER |
| External-memory read path (effective) | `global_addr_only,dram_cg_load_only` | 256,512,2048 | 256,512,2048/8 | W_SM은 nominal L2 배수 sweep; energy load_repeat 4,8,16; pair-locked ITER; NCU read-byte conservation/write-contamination 검증 |

For A100/V100/H100, the generated shell first preserves independent Tensor,
Shared, Global-L1, and external-memory energy sweeps. It then performs the L2 NCU
selector before the L2 energy sweep. It records every rejected candidate in
`results/summary/rtx3090_component_finalplan_20260716_l2_path_selection.csv`.
If no candidate passes, the shell stops without manufacturing an L2 coefficient,
but the earlier non-L2 raw energy and calibration manifests remain available for
their own audits. The 95% threshold is not relaxed.

The energy runner applies the same 1 KiB/block feasibility rule to treatment and
matched control. Global L1 valid coordinates are
`W8/B8`. Coordinates omitted before execution because
`W_SM < blocks/SM` are `none`. The
generated matrix retains rejected rows with `valid=false`, but no rejected row
is sent to the binary. Before collecting energy, every unique valid coordinate
is also checked with the binary's `--dry-run` mode.

The early `run_component_regression_sweep.py --self-test` stage uses only
synthetic fixtures and performs no GPU measurement. Its normal output is one
success line with no stderr. Real Tensor calibration starts only after the shell
prints `REAL GPU CALIBRATION: profile=rtx3090` and
`runtime Tensor pair calibration start`. A later rejection prefixed with
`Runtime` and these real profile coordinates is a target-node failure.

## Architecture-Specific NCU Evidence

The generated package is not valid from hit rate alone. Every target-profile
run must keep the architecture-specific NCU sidecar and acceptance report with
both cache-hit direction and traffic magnitude:

The hard gates require path-specific L1 hit evidence and path-specific L2 read hit
evidence; aggregate cache percentages are diagnostic context only.
The matched-control analyzer also requires exact-coordinate accepted NCU rows
for `reg_operand_only`, `shared_scalar_addr_only`, and `global_addr_only`; a clean treatment cannot rescue
an unvalidated or traffic-contaminated control.

| evidence | required columns | unit / meaning |
|---|---|---|
| L1 hit direction | `l1_path_hit_rate_pct`, `l1_hit_bytes` | percent, bytes; global-load lookup hit/miss path |
| L2 hit direction | `l2_device_path_hit_rate_pct`, `l2_logical_read_hit_rate_pct`, `l2_fabric_hit_rate_pct`, `l2_native_read_hit_rate_pct` | percent; GA100/GH100 distinguish first-partition, final-service, fabric, and transaction-weighted native rates |
| L2 counter coherence | `l2_read_sector_conservation_ratio`, `l2_fabric_read_sector_conservation_ratio`, `l2_fabric_model_coherent`, `ncu_metric_profile` | ratio/boolean/profile; GA100/GH100 strict L2 requires coherent source and fabric populations in `l2_path_minimal` |
| access magnitude | `l1_accesses`, `l2_accesses`, `dram_accesses` | L1 requests when available, otherwise sectors; L2/DRAM sectors |
| byte magnitude | `shared_read_bytes`, `shared_write_bytes`, `l1_request_bytes`, `l1_hit_bytes`, `l2_read_bytes`, `dram_read_bytes`, `dram_write_bytes` | bytes; Shared pJ/bit uses read bytes, L1 request bytes are not L1 hit bytes, L2 pJ/bit uses L2 read bytes |
| external-byte provenance | `dram_read_bytes_source`, `dram_write_bytes_source` | strict external path requires direct `dram__bytes_read.sum` and `dram__bytes_write.sum`; derived fallback is diagnostic-only |
| spill/local traffic | `local_read_bytes`, `local_write_bytes`, `spill_local_read_inst`, `spill_local_write_inst`, `spill_evidence_source` | bytes/instructions; unsupported dedicated spill counters fall back to zero local-memory bytes only |
| stall context | `stall_long_scoreboard_pct` | percent-like NCU stall signal |
| launch/resource context | `achieved_occupancy_pct`, `registers_per_thread`, `shared_mem_per_block_static`, `shared_mem_per_block_dynamic` | requested B value가 실제 residency로 이어졌는지 해석하는 보조 evidence |

RTX 3090 uses `NCU_CHIP=ga102` and `l2_cg_load_only` at
W_SM=32,64 KiB as the strict L2 path. The generated strict anchor is
B8; the existing accepted RTX 3090 reporting package uses separate
B16 targeted/stability evidence and must not be confused with this generated plan.

CG measurement paths also use an `ld.global.cg` warm-up kernel so the harness
does not pre-populate L1 with a normal cached-load warm-up.
Some NCU metric catalogs, including the reviewed GA100 catalog, may omit the dedicated
`sass__inst_executed_register_spilling_*` metrics. The sidecar also requests
local-memory load/store bytes; because these kernels have no intentional local
memory path, zero local bytes plus ptxas spill zero is recorded as
`spill_zero_verified=1` with
`spill_evidence_source=local_memory_bytes_zero_inference`. Architectures with
dedicated spill instruction counters can also produce `spill_zero_verified=1`.
Any positive local bytes or spill instructions reject the path.
`l2_load_only` follows the normal global-load policy, can hit L1, and is therefore
diagnostic-only rather than strict L2 evidence.

## How To Run

```bash
bash results/summary/rtx3090_component_finalplan_20260716_commands.sh
```

The generated shell performs a real baseline hardware-counter profile before
the long energy sweep. If Nsight Compute reports `ERR_NVGPUCTRPERM`, the wrapper
retries that case once through `sudo -E` by default. The preferred permanent fix
is administrator-side access for non-admin GPU performance counters. Automatic
retry can be disabled with `NCU_AUTO_SUDO=0`. To use sudo from the beginning:

```bash
NCU_USE_SUDO=1 bash results/summary/rtx3090_component_finalplan_20260716_commands.sh
```

The shell resolves `cuobjdump` beside the selected `NVCC` executable and passes
that exact path to the Tensor SASS audit. A global `ERR` trap prints the active
stage, shell line, return code, and failed command for every unhandled failure.
The schema smoke is split into
`schema_smoke_kernel_execution`, `schema_smoke_power_api_audit`, and
`tensor_binary_static_audit`. Every checked command prints begin/pass/fail lines,
its shell-escaped command, and a nonzero return code. Do not bypass a failure:
use the reported label plus the generated power or Tensor audit CSV to determine
whether the cause is a stale binary, an invalid power schema, or a real SASS gate.

If `sudo` does not preserve the CUDA/Nsight Compute environment, make the NCU
binary explicit and preserve the environment:

```bash
NCU_BIN="$(command -v ncu)" NCU_USE_SUDO=1 NCU_SUDO="sudo -E" bash results/summary/rtx3090_component_finalplan_20260716_commands.sh
```

For non-interactive scheduler jobs, pre-cache sudo credentials or request the
administrator-side permission change; otherwise sudo may be unable to prompt.
The wrapper writes `ncu_permission_mode.txt` as `unprivileged`, `explicit_sudo`,
or `auto_sudo`.
NCU stderr is streamed through a synchronous `tee` pipeline and the wrapper
checks `PIPESTATUS` only after the complete log is written, so the permission
decision cannot race the log writer. The generated pipeline invokes the
permission fallback self-test with `NCU_USE_SUDO`, `NCU_AUTO_SUDO`, and
`NCU_SUDO` removed through `env -u`; the self-test also clears those variables
internally. Therefore
an outer `NCU_USE_SUDO=1` policy cannot make the self-test start privileged.
`--target-processes all` is used so kernels launched through child processes are
not silently omitted.

The generated shell keeps NVML energy sweeps detached from NCU. The sudo
fallback is only for the NCU sidecar/preflight/goal-readiness commands; failed
NCU evidence must not be replaced with unvalidated denominators in final
component coefficients.

The generated NCU stage runs minimal coherent L2 and external-memory sidecars
plus a separate full Tensor/Shared/Global-L1 sidecar, then merges disjoint rows
with `ncu_summary_source` provenance. It profiles every energy
`reuse_factor`/`load_repeat` coordinate; memory LR is exactly 4,8,16. This lets
`analyze_matched_control_energy.py` prefer
`ncu_actual_exact` denominators instead of representative same-working-set
scaling. Shared uses `shared_scalar_addr_only`, which keeps the same dynamic-shared
allocation, initialization, index loop, and dependent checksum while removing
shared reads. Global L1/L2/DRAM use `global_addr_only` as a matched address
control; NCU verifies global-load L1 request bytes are zero and treats SMID atomic L2
sectors as control bookkeeping rather than input traffic. Legacy diagnostic
modes such as `l2_load_only`, `shared_mma`, `l2_mma`, and `dram_mma` are not
profiled unless `INCLUDE_DIAGNOSTIC_NCU=1` is set manually.

For a quick profiler preflight only, override the sidecar lists manually, for
example `TENSOR_REUSE_FACTORS=4 MEMORY_LOAD_REPEATS=4 DRAM_LOAD_REPEATS=4`.

Before the energy sweeps, the generated shell moves stale generated artifacts
for this profile/tag into `results/archive/..._stale_<timestamp>`. This avoids
appending new rows to an old CSV schema. It then runs a three-row schema and
implementation-revision smoke test (`clocked_empty`, `reg_operand_only`, and
`l2_cg_load_only`). The audit requires an explicit `measurement_scope` plus the
exact Tensor pair and `.cg` warm-up revision markers in raw `notes`. If the
binary is stale, the script stops there instead of producing hundreds or
thousands of unusable rows.

Before the schema smoke and energy sweeps, the generated shell runs Tensor pair
calibration, NCU path-counter, matched-control policy, power API, and strict
summary self-tests. In particular,
`scripts/run_component_regression_sweep.py --self-test`,
`scripts/summarize_ncu_cache_metrics.py --self-test`,
`scripts/merge_ncu_validation_summaries.py --self-test`,
`scripts/analyze_ncu_path_acceptance.py --self-test`,
`scripts/audit_tensor_mma_binary.py --self-test`,
`scripts/analyze_matched_control_energy.py --self-test`,
`scripts/audit_power_api_measurements.py --self-test`, and
`scripts/remediate_wsl_wallclock_intervals.py --self-test`,
`scripts/audit_a100_tensor_l2_remediation.py --self-test`,
`scripts/build_strict_component_summary.py --self-test`,
`scripts/audit_strict_component_summary.py --self-test`,
`scripts/write_platform_result_manifest.py --self-test`,
`scripts/audit_documentation_consistency.py --self-test`, and
`scripts/selftest_platform_package_gates.py` so Tensor pair-lock, A100 path-specific
L2 semantics,
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
`accepted_effective_path`.

Matched-control consumes the generated power-state audit CSV with
`--exclude-power-state-rejects`, so rows flagged as `status=reject` or
`coefficient_eligible=false` are removed before treatment/control pairing. This
keeps power-state drops from appearing as negative component coefficients.

Tensor energy rows use `--tensor-pair-lock-iters` together with
`--tensor-pair-control-min-seconds=1.0`. Each RF coordinate
calibrates `reg_mma` for the treatment target and `reg_operand_only` for the
control-duration floor, records both candidate ITER values, and runs both modes
with their maximum. Matched-control
analysis then uses `--tensor-pair-policy matched-iters` and directly subtracts
the two idle-corrected net energies. An ITER mismatch is a hard-invalid Tensor
detail row; the analysis no longer rescales a differently calibrated Tensor
control by elapsed-time power.
Shared scalar energy rows use `--memory-pair-lock-iters` with
`--memory-pair-control-min-seconds=1.0` and directly
compute `net_E(shared_scalar_load_only) - net_E(shared_scalar_addr_only)` at
equal ITER. NCU requires shared read bytes in the treatment and zero repeated
shared read traffic in the control; fixed shared initialization stores are
allowed. This coefficient includes the board-level completion-time effect of
shared-load latency and is not pure shared-SRAM access energy.
Global L1 energy rows use `--memory-pair-lock-iters` with
`--memory-pair-control-min-seconds=1.0` and directly compute
`net_E(global_l1_load_only) - net_E(global_addr_only)` at equal ITER. This
replaces duration-scaled power subtraction, which could become negative when
the load dependency reduced issue activity relative to the no-load control.
L2 CG energy rows use `--memory-pair-lock-iters` with
`--memory-pair-control-min-seconds=1.0`. Each
W/B/LR coordinate calibrates `l2_cg_load_only` for the treatment target and
`global_addr_only` for the control-duration floor, then applies the larger
identical ITER to both. Analysis uses `--l2-pair-policy matched-iters` and
directly computes `net_E(l2_cg_load_only) - net_E(global_addr_only)`. This is
required even when NCU reports a perfect L2-hit path: path acceptance proves
where bytes traveled, while equal ITER proves that the energy numerator compares
the same logical work. An ITER mismatch is a hard-invalid L2 row.
External-memory read-path rows use `--memory-pair-lock-iters` together with
`--memory-pair-control-min-seconds=1.0`. Each W/B/LR
coordinate calibrates `dram_cg_load_only` for the treatment target and
`global_addr_only` for the control-duration floor, then runs both with the
larger identical ITER. Matched-control analysis uses
`--dram-pair-policy matched-iters` and directly computes
`net_E(dram_cg_load_only) - net_E(global_addr_only)`. An ITER mismatch is a
hard-invalid row. The denominator is strict NCU `dram__bytes_read.sum`; total
DRAM bytes and expected bytes are not final denominators. NCU must also prove
global-read byte conservation, at least 90% external-read service, at most 1%
write contamination, low L1/L2 service hit, and zero local spills. The result is
an effective GPU-device external-memory read-path coefficient, not physical
HBM/GDDR device energy.
The runner rotates complete control-treatment coordinate pairs between repeats;
it never rotates a flat list by one command and split a pair across repeat
boundaries. It counterbalances `control -> treatment` and
`treatment -> control` using both repeat and coordinate index, so one repeat
also contains opposing pair directions and thermal/clock drift is not
systematically assigned to the treatment. The same atomic and counterbalanced pair
policy applies to Shared, Global L1, L2 CG, and external-memory sweeps. Strict package
audit requires valid rows from both execution orders.
Current raw CSVs anchor `measurement_start_epoch_ms` immediately before the
timed benchmark and derive `measurement_end_epoch_ms` from the monotonic
`steady_clock` elapsed interval. This prevents Windows/WSL wall-clock
corrections from corrupting interval duration. Matched-control adjacency
uses the non-overlapping `pair_transition_gap_ms`, not the formerly misnamed
completion timestamp difference `pair_start_distance_ms`. Legacy raw CSVs remain
reanalyzable by estimating each interval from `run_id - elapsed_s`, with
`pair_timing_source=legacy_run_id_elapsed_inferred` recorded explicitly.
The generated transition-gap limit is
`max(30000, (seconds + 15) x 1000)` ms. Each binary invocation measures an idle
baseline for `seconds` before its timed kernel, so a fixed 30-second gate would
reject valid adjacent pairs in longer stability runs. The 15-second allowance
covers process startup, allocation, warm-up, and synchronization; the actual
limit is recorded as `pair_transition_gap_limit_ms` in every matched-detail row.
Both Tensor kernels execute the same fragment-dependent register integer update,
consume the same `SR_CLOCKLO` runtime token, and perform the same in-place FP16
sign-bit flip once per RF iteration. `reg_mma` therefore
uses one A fragment with alternating sign, so its FP32 accumulator remains bounded
instead of becoming numerically stagnant
after millions of constant-sign accumulations. Both modes use the same
`c.num_elements` scalar-store epilogue and issue no operand memory load. The
no-MMA control can still compile to fewer registers than treatment; therefore the
coefficient includes WMMA/HMMA operand and accumulator RF activity and is not a
pure Tensor circuit coefficient. Report both launch register counts.
The raw Tensor rows must contain
`tensor_pair_kernel_revision=matched_runtime_clock_observed_control_fixed_rf_v6`
and `tensor_operand_source=register_fill_no_memory` in `notes`.
Before the energy sweep, `audit_tensor_mma_binary.py` must find an `SR_CLOCKLO`
read inside a backward loop in every RF1/2/4/8/16 treatment and control kernel
after ptxas. Pair calibration must then prove at least 50 ms of treatment and
control trial runtime, and reject a control-derived ITER that predicts more than
6.0x the treatment target duration. Runtime NCU requires
`smsp__sass_inst_executed.sum / expected register operations >= 0.1`; HMMA=0 by
itself is not proof that a no-MMA control loop executed.
CG rows must contain `global_warmup_policy=ld_global_cg`. The package audit
rejects either missing marker so a stale binary with the same CSV schema cannot
silently pass.
Because the no-MMA control completes the same ITER much faster, dual calibration
prevents it from falling below 1.0 s by construction. The
analyzer uses a separate
`--tensor-control-min-elapsed-s=0.8` floor
instead of the full treatment `--min-elapsed-s`; non-positive control net
energy remains rejected. The package audit cross-checks both candidate ITERs,
the trial runtime, control/treatment ITER ratio, predicted treatment duration,
max-resolution policy, the raw ITER,
matched-detail basis, ITER ratio, and control elapsed time.

It also runs `scripts/audit_matched_control_instability.py` to explain weak
signal or negative matched-control rows and to suggest targeted follow-up runs.

Finally, the generated shell runs `scripts/build_strict_component_summary.py`,
`scripts/audit_strict_component_summary.py`, and
`scripts/audit_platform_result_package.py`. The builder copies accepted
reliability medians into
`results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260716.csv`
and records matched-control, power API, power-state, NCU acceptance, NCU summary,
and instability artifacts. The audit verifies that the packaged summary still
matches the underlying evidence and the power measurement matrix. It also fails
hierarchy/order mistakes such as L2 <= shared/global L1 and broad
order-of-magnitude mistakes outside the strict plausibility ranges.
Generated target-node packages invoke the audit with
`--require-path-specific-cache-evidence`; aggregate-only historical cache
counters cannot satisfy a new A100/V100/H100 result package.
The package intake audit then checks the raw energy CSVs, power API audit,
power-state audit, NCU acceptance, matched-control detail, reliability audit,
strict summary, and strict summary audit as one profile/tag package before the
result is copied back or published. It also checks that raw CSV rows carry the
target profile metadata (`chip`, `compute_capability`, L2 size, L1/shared
capacity) and the generated `active_SM` value. If a target node uses MIG,
partitioning, or an SKU with fewer visible SMs, regenerate this plan with
`--active-sm <runtime SM count>` after preflight and keep the same value in the
package audit.
The package audit also verifies that the NCU summary exposes aggregate and
path-specific L1/L2 hit rates, L1 request/hit/miss bytes, L2 read hit/miss
sectors and bytes, `hit+miss/read` conservation, metric-profile provenance,
L1/L2/DRAM access counts, DRAM traffic, and long-scoreboard stall counters
before the result can be treated as final evidence. Hit rate alone is not enough:
accepted cache rows must also show path-relevant access/byte magnitude. The NCU
summary must include
`clocked_empty`, `reg_operand_only`, `reg_mma`, `shared_scalar_addr_only`,
`shared_scalar_load_only`,
`global_addr_only`, `global_l1_load_only`, `l2_cg_load_only`, and
`dram_cg_load_only` coverage.
All generated platform packages use `l2_cg_load_only` as the strict L2 path;
`l2_load_only` is diagnostic-only and is not required. Tensor pair NCU rows need at least three
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
