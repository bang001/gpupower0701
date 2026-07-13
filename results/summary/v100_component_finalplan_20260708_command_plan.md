# V100 Component Finalplan Command Plan

Generated: 2026-07-13

| item | value |
|---|---|
| target profile | `v100` |
| CUDA arch | `sm_70` |
| active_SM (SMs) | `80` |
| energy sweep blocks/SM | `4,16,32` |
| strict NCU blocks/SM | `32` |
| expected power semantics | `instant` |
| minimum visible device memory (MiB) | `30000` |
| seconds (s) | `10.0` |
| repeats | `5` |
| Tensor control calibration floor (s) | `1.0` |
| DRAM address-control calibration floor (s) | `1.0` |
| binary | `./build-v100/a100_fp16_energy_v2` |
| NCU | `ncu` |
| NCU counter permission probe | baseline hardware-counter profile before energy sweep |
| NCU automatic sudo retry | enabled by default with `NCU_AUTO_SUDO=1` |
| NCU sudo fallback | `NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh` |
| generated shell | `results/summary/v100_component_finalplan_20260708_commands.sh` |

## Platform Note

Volta path. Use nvcc with compute_70 support (CUDA 12.x recommended; CUDA 13 removed Volta offline compilation). Nsight Compute 2024.3 is confirmed for GV100; always require --list-chips and --query-metrics support for gv100 because newer releases can remove Volta.


For the V100 reference package, `30,000 MiB` is a strict lower bound for a
32 GB HBM2 device visible to the process. This distinguishes the intended 32 GB
SKU from a 16 GB board or a smaller vGPU partition; it does not change the
L1/shared/L2 hierarchy coordinates. Override this threshold only when running a
separately labelled non-32 GB V100 experiment.


## Build Requirement

Build the benchmark for `sm_70` before running the generated
shell. The preflight dry-run rejects a binary built for the wrong compute
capability, but using a profile-specific build directory avoids wasting the
target node allocation.

```bash
NVCC="${NVCC:-/path/to/cuda-12/bin/nvcc}"
"${NVCC}" --list-gpu-arch | grep -Fx compute_70
cmake -S . -B build-v100 \
  -DCMAKE_CUDA_COMPILER="${NVCC}" \
  -DCMAKE_CUDA_ARCHITECTURES=70
cmake --build build-v100 --clean-first -j
```

Use a clean rebuild after every `git pull` that changes `src/`, `include/`, or
`CMakeLists.txt`. In particular, raw CSVs for final runs must be produced by a
binary whose CSV header includes `measurement_scope`.

## Component Coordinates

| component/path | modes | energy W_SM (KiB) | strict NCU W_SM/B | factor |
|---|---|---:|---:|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 2048/32 | reuse 1,2,4,8,16; treatment/control-floor dual-calibrated pair-locked ITER |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 32,64 | 32/32 | energy load_repeat 4,8,16; NCU also checks 1,2 |
| Global L1 | `global_addr_only,global_l1_load_only` | 8,16,32 | 32/32 | energy load_repeat 4,8,16; NCU also checks 1,2 |
| L2 | `global_addr_only,l2_cg_load_only` | 32,64 | 32/32 | energy load_repeat 4,8,16; treatment/control-floor dual-calibrated pair-locked ITER; NCU also checks 1,2 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | 8192/32 | energy load_repeat 4,8,16; treatment/control-floor dual-calibrated pair-locked ITER; NCU checks 1,4,8,16 |

The energy runner applies the same 1 KiB/block feasibility rule to treatment and
matched control. Global L1 valid coordinates are
`W8/B4,W16/B4,W16/B16,W32/B4,W32/B16,W32/B32`. Coordinates omitted before execution because
`W_SM < blocks/SM` are `W8/B16,W8/B32,W16/B32`. The
generated matrix retains rejected rows with `valid=false`, but no rejected row
is sent to the binary. Before collecting energy, every unique valid coordinate
is also checked with the binary's `--dry-run` mode.

## Architecture-Specific NCU Evidence

The generated package is not valid from hit rate alone. Every target-profile
run must keep the architecture-specific NCU sidecar and acceptance report with
both cache-hit direction and traffic magnitude:

The hard gates require path-specific L1 hit evidence and path-specific L2 read hit
evidence; aggregate cache percentages are diagnostic context only.
The matched-control analyzer also requires exact-coordinate accepted NCU rows
for `reg_operand_only` and `global_addr_only`; a clean treatment cannot rescue
an unvalidated or traffic-contaminated control.

| evidence | required columns | unit / meaning |
|---|---|---|
| L1 hit direction | `l1_path_hit_rate_pct`, `l1_hit_bytes` | percent, bytes; global-load lookup hit/miss path |
| L2 hit direction | `l2_path_hit_rate_pct`, `l2_read_hit_sectors`, `l2_read_miss_sectors` | percent, sectors; srcunit-TEX read path |
| access magnitude | `l1_accesses`, `l2_accesses`, `dram_accesses` | L1 requests when available, otherwise sectors; L2/DRAM sectors |
| byte magnitude | `shared_bytes`, `l1_request_bytes`, `l1_hit_bytes`, `l2_read_bytes`, `dram_bytes` | bytes; L1 request bytes are not L1 hit bytes; L2 pJ/bit uses L2 read bytes |
| spill/local traffic | `local_read_bytes`, `local_write_bytes`, `spill_local_read_inst`, `spill_local_write_inst`, `spill_evidence_source` | bytes/instructions; unsupported dedicated spill counters fall back to zero local-memory bytes only |
| stall context | `stall_long_scoreboard_pct` | percent-like NCU stall signal |
| launch/resource context | `achieved_occupancy_pct`, `registers_per_thread`, `shared_mem_per_block_static`, `shared_mem_per_block_dynamic` | requested B value가 실제 residency로 이어졌는지 해석하는 보조 evidence |

V100 uses `NCU_CHIP=gv100` and `l2_cg_load_only` as the L2
final path. Its energy sweep covers blocks/SM=4,16,32; the generated strict
anchor is B32, L2 W_SM=32 KiB. L2
W_SM=64 KiB is retained as a capacity-stress point.
The NCU binary must explicitly support GV100.

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
bash results/summary/v100_component_finalplan_20260708_commands.sh
```

The generated shell performs a real baseline hardware-counter profile before
the long energy sweep. If Nsight Compute reports `ERR_NVGPUCTRPERM`, the wrapper
retries that case once through `sudo -E` by default. The preferred permanent fix
is administrator-side access for non-admin GPU performance counters. Automatic
retry can be disabled with `NCU_AUTO_SUDO=0`. To use sudo from the beginning:

```bash
NCU_USE_SUDO=1 bash results/summary/v100_component_finalplan_20260708_commands.sh
```

If `sudo` does not preserve the CUDA/Nsight Compute environment, make the NCU
binary explicit and preserve the environment:

```bash
NCU_BIN="$(command -v ncu)" NCU_USE_SUDO=1 NCU_SUDO="sudo -E" bash results/summary/v100_component_finalplan_20260708_commands.sh
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

The generated NCU sidecar profiles primary finalplan modes at every energy
`reuse_factor`/`load_repeat` coordinate and includes 1,2 as lower-signal
diagnostic points. This lets `analyze_matched_control_energy.py` prefer
`ncu_actual_exact` denominators instead of representative same-working-set
scaling. The global-memory pairs use `global_addr_only` as a matched address
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
`scripts/analyze_ncu_path_acceptance.py --self-test`,
`scripts/analyze_matched_control_energy.py --self-test`,
`scripts/audit_power_api_measurements.py --self-test`, and
`scripts/audit_a100_tensor_l2_remediation.py --self-test`,
`scripts/build_strict_component_summary.py --self-test`,
`scripts/audit_strict_component_summary.py --self-test`,
`scripts/write_platform_result_manifest.py --self-test`, and
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
`accepted_sanity`.

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
L2 CG energy rows use `--memory-pair-lock-iters` with
`--memory-pair-control-min-seconds=1.0`. Each
W/B/LR coordinate calibrates `l2_cg_load_only` for the treatment target and
`global_addr_only` for the control-duration floor, then applies the larger
identical ITER to both. Analysis uses `--l2-pair-policy matched-iters` and
directly computes `net_E(l2_cg_load_only) - net_E(global_addr_only)`. This is
required even when NCU reports a perfect L2-hit path: path acceptance proves
where bytes traveled, while equal ITER proves that the energy numerator compares
the same logical work. An ITER mismatch is a hard-invalid L2 row.
DRAM energy rows use `--memory-pair-lock-iters` together with
`--memory-pair-control-min-seconds=1.0`. Each W/B/LR
coordinate calibrates `dram_cg_load_only` for the treatment target and
`global_addr_only` for the control-duration floor, then runs both with the
larger identical ITER. Matched-control analysis uses
`--dram-pair-policy matched-iters` and directly computes
`net_E(dram_cg_load_only) - net_E(global_addr_only)`. An ITER mismatch is a
hard-invalid DRAM detail row; duration-scaled DRAM coefficients are not final
cross-platform evidence.
The runner rotates complete control-treatment coordinate pairs between repeats;
it never rotates a flat list by one command and split a pair across repeat
boundaries. The same atomic pair ordering applies to the generated Shared,
Global L1, L2 CG, and DRAM CG treatment-control sweeps.
Both Tensor kernels execute the same dependent register integer add once per
RF iteration, so the liveness/control instruction cancels in the direct pair.
The control no longer performs the former RF-proportional FP32 FMA/checksum or
memory work. Both modes use the same per-thread eight-scalar-store epilogue
instead of a WMMA store intrinsic. The treatment stores all accumulator
fragment values to keep HMMA live; the control stores sink values with the same
address pattern while keeping its HMMA count at zero.
The raw Tensor rows must contain
`tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2` in `notes`.
CG rows must contain `global_warmup_policy=ld_global_cg`. The package audit
rejects either missing marker so a stale binary with the same CSV schema cannot
silently pass.
Because the no-MMA control completes the same ITER much faster, dual calibration
prevents it from falling below 1.0 s by construction. The
analyzer uses a separate
`--tensor-control-min-elapsed-s=0.8` floor
instead of the full treatment `--min-elapsed-s`; non-positive control net
energy remains rejected. The package audit cross-checks both candidate ITERs,
the max-resolution policy, the raw ITER,
matched-detail basis, ITER ratio, and control elapsed time.

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
sectors and bytes, L1/L2/DRAM access counts, DRAM traffic, and long-scoreboard stall counters
before the result can be treated as final evidence. Hit rate alone is not enough:
accepted cache rows must also show path-relevant access/byte magnitude. The NCU
summary must include
`clocked_empty`, `reg_operand_only`, `reg_mma`, `shared_scalar_load_only`,
`global_l1_load_only`, `l2_cg_load_only`, and `dram_cg_load_only` coverage.
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
