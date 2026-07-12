# FP16 Tensor Core Energy Experiment v2

CUDA/C++ microbenchmark framework for estimating effective energy of a logical
warp-level FP16 `m16n16k16` MMA operation on NVIDIA Tensor Core GPUs.

## Presentation

GPU component/path별 effective microbenchmark coefficient가 만들어지는 전체 과정을
22장 PowerPoint로 정리했다. 현행 finalplan과 2026-07-08 RTX 3090 historical snapshot을
분리하고, NVML measurement scope, treatment-control, NCU denominator/path 검증 및
strict/package audit를 단계별로 설명한다.

- [PowerPoint](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.pptx)
- [Rendered PDF](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.pdf)
- [Evidence notes](docs/presentations/gpu_component_energy_experiment_whitepaper_ko.md)

The default runtime profile in this checkout targets GeForce RTX 3090
(`sm_86`, 82 SMs, 6 MiB nominal L2). Additional profiles are available for
V100, A100, and H100. Use `--target-profile auto` to select a profile from the
runtime CUDA device when running on the target machine.

This repository implements the v2 design in
`docs/design/a100_fp16_energy_experiment_design_v2.md`.
For component-energy claims, use the acceptance-first finalplan flow:
`docs/methodology/component_energy_final_experiment_plan_ko.md` and
`docs/platforms/cross_platform_component_experiment_guide_ko.md`. Memory pJ/bit results
must use NCU actual traffic counters and should be reported as transaction-path
effective coefficients, not as SRAM/HBM bitcell energy. The self-critique and
known limitations are tracked in `docs/audits/component_energy_self_critique_ko.md`.
For the detailed NCU validation and pJ/FLOP or pJ/byte calculation method, see
`docs/methodology/ncu_validation_energy_calculation_ko.md`.

For a quick map of active vs archived material, start with `docs/README.md` and
`scripts/README.md`. Legacy design/code paths are kept under
`archive/legacy_20260707/`.
GPU-generation-specific power/energy API support, sampling semantics, scope,
and final-numerator eligibility are summarized in
`docs/platforms/power_measurement_api_matrix_ko.md`; check this before
comparing RTX 3090, V100, A100, and H100 measurements. API visibility is not
the same as coefficient validity.
Final component coefficients should use `nvmlDeviceGetTotalEnergyConsumption`
rows when available. `nvmlDeviceGetPowerUsage` is treated as a fallback because
its meaning changes by chip family: V100/A100 are recorded as instantaneous,
while RTX 3090/H100 are recorded as one-second average semantics.
Do not equate API visibility with coefficient validity: `power.draw.*`,
`GetPowerUsage`, Hopper module power, and GPU memory power are useful metadata
or provisional fallbacks, but the current final denominator policy requires a
GPU/device total-energy mJ delta plus NCU path validation.

**Current protocol status (2026-07-12):** the RTX 3090 coefficients produced on
2026-07-08 are historical evidence, not current strict-final values. Their
Global L1/L2 energy pairs use `clocked_empty` and do not carry same-coordinate
`global_addr_only` NCU acceptance. The current protocol requires address
controls, exact control NCU acceptance, and pair-locked Tensor/DRAM work. See
`docs/audits/current_goal_alignment_audit_ko.md` and rerun
`results/summary/rtx3090_component_finalplan_20260712_commands.sh` before
publishing updated RTX 3090 coefficients.

Historical RTX 3090 result artifacts:

| artifact | path |
|---|---|
| current-protocol alignment audit | `docs/audits/current_goal_alignment_audit_ko.md` |
| current-protocol reaudit of old strict result | `results/summary/rtx3090_current_protocol_reaudit_20260712.md` |
| current-protocol rerun plan | `results/summary/rtx3090_component_finalplan_20260712_command_plan.md` |
| strict + fresh NCU component summary | `results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md` |
| strict + fresh NCU reliability audit | `results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md` |
| strict + fresh NCU acceptance CSV | `results/summary/rtx3090_strict_scope_fresh_ncu_combined_acceptance_20260708.csv` |
| strict + fresh NCU summary audit | `results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260708.md` |
| legacy explicit-scope component summary | `results/summary/rtx3090_strict_scope_component_coefficients_20260708.md` |
| legacy explicit-scope component CSV | `results/summary/rtx3090_strict_scope_component_coefficients_20260708.csv` |
| strict report | `results/summary/rtx3090_finalplan_stability_strict_report_20260708_ko.md` |
| strict summary CSV | `results/summary/rtx3090_finalplan_stability_strict_matched_control_summary_20260708.csv` |
| factor exact-NCU report | `results/summary/rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md` |
| factor exact-NCU CSV | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_summary_20260708.csv` |
| power API audit | `results/summary/rtx3090_finalplan_stability_power_api_audit_20260708.md` |
| power-state audit | `results/summary/rtx3090_finalplan_stability_power_state_audit_20260708.md` |
| component reliability audit | `results/summary/rtx3090_finalplan_stability_component_reliability_audit_20260708.md` |
| matched-control instability audit | `results/summary/rtx3090_finalplan_stability_matched_control_instability_audit_20260708.md` |
| platform power/readiness audit | `results/summary/platform_power_readiness_audit_20260708.md` |
| current component-energy goal readiness audit | `results/summary/component_energy_goal_readiness_audit_20260712.md` |
| Tensor targeted rerun | `results/summary/rtx3090_tensor_targeted_rf8_rf16_report_20260708_ko.md` |
| Tensor fixed-ITER check | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_report_20260708_ko.md` |
| Tensor RF8 duration-scaling check | `results/summary/rtx3090_tensor_rf8_duration_scaling_report_20260708_ko.md` |
| Tensor RF16 duration-scaling check | `results/summary/rtx3090_tensor_rf16_duration_scaling_report_20260708_ko.md` |
| Shared/L1 targeted rerun | `results/summary/rtx3090_targeted_shared_l1_stability_report_20260708_ko.md` |
| Shared duration-scaling check | `results/summary/rtx3090_shared_duration_scaling_report_20260708_ko.md` |
| Shared LR4 paired 30 s stability auxiliary check | `results/summary/rtx3090_shared_paired_lr4_30s_stability_report_20260708_ko.md` |
| Shared LR8 paired 30 s combined auxiliary check | `results/summary/rtx3090_shared_paired_lr8_30s_combined_report_20260708_ko.md` |
| Shared LR16 paired 30 s combined auxiliary check | `results/summary/rtx3090_shared_paired_lr16_30s_combined_report_20260708_ko.md` |
| Shared LR16 paired 60 s low-stability auxiliary check | `results/summary/rtx3090_shared_paired_lr16_60s_stability_report_20260708_ko.md` |
| Shared LR4/LR8/LR16 interleaved 30 s auxiliary check | `results/summary/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_report_20260708_ko.md` |
| Shared LR4/LR8/LR16 fixed-ITER auxiliary check | `results/summary/rtx3090_shared_fixediter_lr4_lr8_lr16_report_20260708_ko.md` |
| Shared LR16 fixed-ITER focus check | `results/summary/rtx3090_shared_fixediter_lr16_focus_report_20260708_ko.md` |
| Shared LR4/LR8 fixed-ITER focus check | `results/summary/rtx3090_shared_fixediter_lr4_lr8_focus_report_20260708_ko.md` |
| L1 duration-scaling check | `results/summary/rtx3090_l1_duration_scaling_report_20260708_ko.md` |
| L1 30 s stability check | `results/summary/rtx3090_l1_30s_stability_report_20260708_ko.md` |
| L1 60 s stability auxiliary check | `results/summary/rtx3090_l1_60s_stability_report_20260708_ko.md` |
| L1 paired 30 s combined primary check | `results/summary/rtx3090_l1_paired_30s_combined_report_20260708_ko.md` |
| L1 LR8 paired 30 s auxiliary check | `results/summary/rtx3090_l1_paired_lr8_30s_stability_report_20260708_ko.md` |
| Shared/L2 LR4 30 s stability check | `results/summary/rtx3090_shared_l2_30s_stability_report_20260708_ko.md` |
| L2 targeted rerun | `results/summary/rtx3090_targeted_l2_stability_report_20260708_ko.md` |
| L2 LR4/LR8 paired 30 s combined primary check | `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_report_20260708_ko.md` |
| L2 LR4 paired 30 s auxiliary check | `results/summary/rtx3090_l2_paired_lr4_30s_stability_report_20260708_ko.md` |
| L2 LR8 paired 30 s auxiliary check | `results/summary/rtx3090_l2_paired_lr8_30s_stability_report_20260708_ko.md` |
| historical 2026-07-08 reporting CSV | `results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv` |
| historical 2026-07-08 evidence matrix | `results/summary/rtx3090_current_reporting_evidence_matrix_20260708.md` |
| historical 2026-07-08 sanity audit | `results/summary/rtx3090_current_component_sanity_audit_20260708.md` |
| historical 2026-07-08 primary selection audit | `results/summary/rtx3090_current_primary_selection_audit_20260708_ko.md` |
| current DRAM reporting policy | `results/summary/rtx3090_dram_current_reporting_policy_20260712.md` |
| result overview | `docs/results/gpu_power_modeling_experiment_results_ko.md` |

Experiment setup and method documents:

| question | document |
|---|---|
| How does the current experiment work? | `docs/methodology/howitworks.md` |
| What are the final sweep/settings and gates? | `docs/methodology/component_energy_final_experiment_plan_ko.md` |
| How are NCU counters used for pJ/FLOP and pJ/bit? | `docs/methodology/ncu_validation_energy_calculation_ko.md` |
| Why did the A100 Tensor RF/L2 strict run fail, and what changed? | `docs/audits/a100_strict_summary_failure_remediation_ko.md` |
| How should A100/V100/H100 be run? | `docs/platforms/cross_platform_component_experiment_guide_ko.md` |
| How do RTX 3090/A100/V100 parameters and experiment counts differ? | `docs/platforms/cross_platform_component_experiment_guide_ko.md` sections 4.0-4.5 |
| What power APIs are available by GPU generation, and which ones can be final numerators? | `docs/platforms/power_measurement_api_matrix_ko.md` |
| How do I check profile/power readiness before a new platform run? | `results/summary/platform_power_readiness_audit_20260708.md` and `scripts/audit_platform_power_readiness.py` |
| How do I refresh local audits, external package gap reports, and the dashboard? | `scripts/run_local_readiness_checks.sh` |
| Is the broader multi-platform goal complete? | `results/summary/component_energy_goal_readiness_audit_20260712.md` and `scripts/audit_component_goal_readiness.py` |
| Where is the full documentation map? | `docs/README.md` |

The goal readiness audit treats a platform result package as valid only when the
component summary policy, strict summary audit artifact, reliability artifact,
power API audit artifact, power-state audit artifact, and fresh NCU acceptance
artifact all pass under the power measurement matrix. New platform packages
should build their report summary with `scripts/build_strict_component_summary.py`
from the accepted reliability, matched-control, power API, power-state, and NCU
acceptance artifacts before running `scripts/audit_strict_component_summary.py`.
It also checks that A100/V100/H100 generated command packages exist and contain
the expected finalplan gates; that check proves execution readiness, not measured
component coefficients.

Older inferred-scope RTX 3090 reporting medians retained for
method-sensitivity/history: Tensor targeted RF=8/16 is
`0.107 pJ/FLOP`, the fixed-ITER auxiliary check is `0.146 pJ/FLOP`, and
the RF=8 duration-scaling auxiliary check is `0.143 pJ/FLOP` with slope
estimates around `0.144-0.156 pJ/FLOP`. The RF=16 duration-scaling check is
`0.077 pJ/FLOP` with slope estimates around `0.053-0.071 pJ/FLOP`. Therefore
Tensor should be reported as RF-dependent: RF16 lower side around
`0.06-0.09 pJ/FLOP`, RF8 upper side around `0.14-0.15 pJ/FLOP`, not as a pure
circuit constant. Shared scalar primary is
`0.149 pJ/bit`, Global L1 is `0.148 pJ/bit`, L2 CG is `1.017 pJ/bit`. DRAM은
`26.709-28.409 pJ/bit`의 provisional reference-aligned cumulative-path band로만
보고한다. 현행 matched-ITER `global_addr_only` raw pair가 아직 없으므로 accepted 실측
coefficient가 아니며 V100/A100/H100에 전이하지 않는다. Memory path denominators use
`ncu_actual_exact` for the current stability factor set. The broader Tensor
factor exact-NCU sweep over RF=1,2,4,8,16 produced `0.170 pJ/FLOP` with low
stability, so it is retained as history rather than the current Tensor
reporting value. The current evidence matrix now marks Tensor, Shared, Global L1, and
L2 as `strong_candidate`; DRAM은 strict component 표와 분리된 provisional reporting
band다. The L2 targeted rerun remains auxiliary
support because it is consistent with the paired primary but carries one
traceability-only control temperature caution row. The current sanity audit has
0 failures and 4 expected warnings: Tensor RF sensitivity, Shared method
sensitivity, the requirement to report all values as workload-dependent
effective coefficients, and an explicit-scope warning. The 2026-07-08 RTX 3090
component raw rows mostly predate the explicit `measurement_scope` CSV column,
so their GPU/device scope was inferred from `nvml_total_energy` +
`total_energy_mj_delta`; new finalplan runs require explicit
`measurement_scope=gpu_device_total_energy_counter`.

Under the 2026-07-08 protocol, explicit measurement-scope + fresh NCU rerun
values were stricter than the older inferred-scope table: Tensor
`0.129 pJ/FLOP` (`accepted`), Shared scalar `0.171 pJ/bit` (`accepted`),
Global L1 `0.173 pJ/bit` (`accepted`), and L2 CG `1.131 pJ/bit` (`accepted`).
These rows all use `nvml_total_energy` with
`total_energy_mj_delta` and `measurement_scope=gpu_device_total_energy_counter`.
Shared uses an LR8-only follow-up to separate the previous LR4 weak row in the
mixed LR4/LR8 run; Global L1 uses an LR4-only follow-up to separate the previous
LR8 weak-signal behavior.
The fresh NCU replay was run from a no-space WSL path (`/tmp/ncu2025/.../ncu`)
because the Windows Nsight Compute install directory contains spaces. The
historical combined fresh NCU reliability audit accepted Tensor, Shared,
Global L1, and L2 under that version's treatment-focused NCU gate.
The strict table is generated or cross-checked from accepted reliability evidence
with `scripts/build_strict_component_summary.py` and then checked by
`scripts/audit_strict_component_summary.py`;
the fresh NCU 2026-07-08 audit had 169 pass checks, 0 failures, and 0 warnings
under the older audit schema,
including
matched-control detail-row scope, power API audit artifact, energy-source,
power-state reject, and exact NCU denominator checks.

Shared/L1 targeted rerun: Shared scalar remained consistent at `0.152 pJ/bit`
with 29/30 valid rows. Global L1 measured `0.105 pJ/bit` with 26/30 valid rows
but kept `accepted_with_caution` because LR=16 still produced negative
matched-control rows. The targeted power-state audit identified two of those
L1 LR=16 negative rows as average-power low outliers.
Shared duration-scaling produced 15/15 valid rows with ratio median
`0.198 pJ/bit`, but slope estimates with an intercept were `0.10-0.12 pJ/bit`.
This is retained as historical method-sensitivity evidence; the former primary is the
cleaner LR4/LR8 fixed-ITER focus result at `0.149 pJ/bit`.
Shared LR=4 paired 30 s auxiliary produced `0.236 pJ/bit` with 6/6 valid rows,
Shared LR=8 paired 30 s combined auxiliary produced `0.177 pJ/bit` with
12/12 valid rows, 36/36 final power API rows, and 36/36 power-state ok rows.
The combined Shared LR=16 paired 30 s auxiliary produced `0.064 pJ/bit`
with 11/12 valid rows and medium confidence. This confirms Shared is
LR/method-sensitive; it remains lower-bound evidence rather than replacing the
clean LR4/LR8 fixed-ITER primary.
Extending the same LR=16 paired check to 60 s produced `0.077 pJ/bit` with
5/6 valid matched rows, 18/18 final power API rows, 18/18 power-state ok rows,
and `accepted_low_stability`. This confirms the LR16 lower side persists, but
it remains a lower-bound/method-sensitivity auxiliary rather than a primary.
The interleaved LR=4/8/16 C-T-C 30 s run produced aggregate `0.145 pJ/bit`
with 12/12 valid matched rows, 36/36 final power API rows, and 36/36
power-state ok rows. Its factor split was LR4 `0.199`, LR8 `0.145`, and LR16
`0.0618 pJ/bit`, so it supports the current Shared primary near `0.149 pJ/bit`, but the
LR/method sensitivity is now confirmed inside one rotated run.
The fixed-ITER Shared follow-up kept treatment ITER at `17,000,000`, making
shared bytes scale by roughly 1x/2x/4x across LR4/LR8/LR16. It produced
aggregate `0.140 pJ/bit` with 8/9 valid matched rows and 27/27 final power API
rows. This supports the `0.145-0.149 pJ/bit` Shared primary range, but one
LR16 weak-signal row keeps this mixed LR4/LR8/LR16 run as auxiliary evidence.
The LR16 fixed-ITER focus rerun then produced `0.117 pJ/bit` with 6/6 valid
matched rows, 18/18 final power API rows, and 18/18 power-state ok rows. This
means the prior LR16 weak row was not persistent, although Shared remains
method-sensitive and should not be described as a pure shared-memory circuit
constant.
The LR4/LR8 fixed-ITER focus rerun produced aggregate `0.149 pJ/bit` with
10/10 valid matched rows, 30/30 final power API rows, and 30/30 power-state ok
rows. Its LR4/LR8 split was `0.179`/`0.142 pJ/bit`, so it strongly supports the
current Shared primary and is now the selected clean primary artifact while
preserving the LR/factor sensitivity caveat.
L1 duration-scaling with `load_repeat=4` and 10/20/30 s runs produced
`0.156 pJ/bit` median, `0.147 pJ/bit` OLS slope, and `0.149 pJ/bit`
Theil-Sen slope, supporting the `0.15 pJ/bit` L1 range as auxiliary evidence.
The follow-up 30 s, 10-repeat L1 stability run reproduced this at
`0.153 pJ/bit` with 9/10 valid matched rows and 20/20 power API/state gates ok;
one weak-signal negative row remains, so that run is kept as auxiliary while the
paired combined run is the clean Global L1 primary.
The 60 s L1 auxiliary run produced `0.119 pJ/bit` after the one power-state
reject treatment row was excluded before matched-control pairing. This is
recorded as control-drift/thermal sensitivity evidence, not as a replacement
primary value.
The paired 30 s L1 auxiliary runs used a control-treatment-control sequence and
the combined result produced `0.148 pJ/bit` with 12/12 valid matched rows,
36/36 final power API rows, and 36/36 power-state ok rows. This supports the
`~0.15 pJ/bit` L1 range, is now the current Global L1 primary, and shows why
paired ordering is better for drift-sensitive paths.
The additional L1 LR8 paired 30 s auxiliary produced `0.109 pJ/bit` with
6/6 valid matched rows, 18/18 final power API rows, and 18/18 power-state ok
rows. This does not replace the LR4 paired primary, but it narrows
the honest interpretation to a method-sensitive Global L1 effective range around
`0.11-0.16 pJ/bit`.
The Shared/L2 LR4 30 s auxiliary run produced Shared `0.216 pJ/bit` and
non-paired L2 `1.298 pJ/bit`. A follow-up L2 LR4 paired 30 s run produced
`1.027 pJ/bit` with 6/6 valid rows, 18/18 final power API rows, and 18/18
power-state ok rows. This supports the L2 primary near `0.98-1.03 pJ/bit` and
reclassifies the older non-paired LR4 L2 value as drift/order-sensitive
high-side evidence.
The additional L2 LR8 paired 30 s auxiliary produced `0.960 pJ/bit` with
6/6 valid rows, 18/18 final power API rows, and 18/18 power-state ok rows.
NCU sidecar validation showed L1 hit `0.000003%`, L2 hit `99.9368%`, and
DRAM bytes only about `0.12%` of L2 bytes. This reinforces L2 as the most
stable current memory coefficient axis, while still limiting the claim to a
board-level effective L2-hit microbenchmark coefficient.
The combined L2 LR4/LR8 paired primary is `1.017 pJ/bit` with 12/12 valid rows,
36/36 final power API rows, and 36/36 power-state ok rows. The previous targeted
mixed-LR value `0.978 pJ/bit` is retained as auxiliary support because it is
consistent but carries one traceability-only power-state caution row.

Platform guides:

| GPU | guide |
|---|---|
| A100 | `docs/platforms/a100_node_experiment_guide_ko.md` |
| V100 | `docs/platforms/v100_node_experiment_guide_ko.md` |
| H100 | `docs/platforms/h100_node_experiment_guide_ko.md` |

Generated cross-platform command packages:

| GPU | command plan | executable shell |
|---|---|---|
| A100 | `results/summary/a100_component_finalplan_20260708_command_plan.md` | `results/summary/a100_component_finalplan_20260708_commands.sh` |
| A100 Tensor/L2 remediation | `results/summary/a100_tensor_l2_remediation_20260710_command_plan.md` | `results/summary/a100_tensor_l2_remediation_20260710_commands.sh` |
| V100 | `results/summary/v100_component_finalplan_20260708_command_plan.md` | `results/summary/v100_component_finalplan_20260708_commands.sh` |
| H100 | `results/summary/h100_component_finalplan_20260708_command_plan.md` | `results/summary/h100_component_finalplan_20260708_commands.sh` |

These command packages are generated plans, not measured platform results. Run
them on the matching target node after building the profile-specific binary, then
rerun the power API, power-state, NCU, reliability, strict-summary, and goal
readiness audits.

Prompt templates:

| GPU | prompt |
|---|---|
| V100 | `docs/platforms/prompts/v100_experiment_prompt_ko.md` |

## Operation Definition

- 1 logical op = 1 warp-level FP16 `m16n16k16` MMA.
- 1 logical op = 4096 FMA = 8192 FLOP.
- 1 logical op input footprint = A+B FP16 = 1KiB = 8192 bits.
- `threads/block = 32`, so `blocks/SM = resident warps/SM`.

For V100, the energy diagnostic sweep uses `blocks/SM=1,2,4,8,16,32` and the
strict NCU sidecar uses B32 with Shared/Global-L1/L2 `W_SM=32 KiB`. Because the
kernel has one warp per block, B32 requests at most 32 warps/SM, or 50% of
GV100's 64-warp limit. Register/shared-memory limits can reduce actual
residency, so NCU achieved occupancy and launch registers/thread must be
reported; B32 is not proof of 32 simultaneously resident blocks or full warp
occupancy. The V100 strict L2 point is 2.5 MiB total
(`80 SM x 32 KiB`), while W64=5 MiB is retained only as a 6 MiB-L2 stress point.

The current kernel implementation uses CUDA WMMA as the portable Tensor Core
path. In low-level SASS this may compile to multiple tensor instructions for one
logical `m16n16k16` op. Raw inline PTX `mma.sync.aligned.m16n8k16` and explicit
`ldmatrix` are not the primary implementation yet; CSV rows mark
`wmma_fallback=1` in `notes`.

## Build

The default `build` directory below targets the local RTX 3090 profile
(`sm_86`). For cross-platform runs, build into a profile-specific directory so
an A100/V100/H100 result cannot accidentally come from an RTX 3090 binary.

| profile | CUDA arch | build directory | binary used by generated finalplan |
|---|---:|---|---|
| `rtx3090` | 86 | `build` | `./build/a100_fp16_energy_v2` |
| `v100` | 70 | `build-v100` | `./build-v100/a100_fp16_energy_v2` |
| `a100` | 80 | `build-a100` | `./build-a100/a100_fp16_energy_v2` |
| `h100` | 90 | `build-h100` | `./build-h100/a100_fp16_energy_v2` |

V100 is a toolchain exception: CUDA 13 removed Volta offline compilation
support. Use a CUDA 12.x compiler and verify that
`nvcc --list-gpu-arch` contains `compute_70` before configuring `build-v100`.
The NCU executable is an independent choice; the reviewed baseline is Nsight
Compute 2024.3 with live `gv100` chip/metric queries.

```bash
/home/bang001/miniforge3/envs/ssc21env/bin/cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/home/bang001/miniforge3/envs/ssc21env/bin/nvcc \
  -DCUDAToolkit_ROOT=/home/bang001/miniforge3/envs/ssc21env \
  -DCMAKE_CUDA_ARCHITECTURES=86
/home/bang001/miniforge3/envs/ssc21env/bin/cmake --build build -j
```

NVML is required. If CMake cannot find it, make sure the NVIDIA driver
development files are installed or `CUDA_PATH` points at a CUDA toolkit
installation. The build enables `-Xptxas=-v` so register count and spill warnings
are visible in the build log.

Before measurement, check the platform state manually:

```bash
nvidia-smi -L
sudo nvidia-smi -pm 1
nvidia-smi --query-gpu=index,name,uuid,driver_version,compute_cap,power.draw,power.draw.average,power.draw.instant,power.limit,clocks.sm,clocks.mem,temperature.gpu,ecc.mode.current --format=csv
nvidia-smi -q -d POWER,CLOCK,TEMPERATURE
```

This tool records clocks, temperature, power limit, and ECC metadata where NVML
exposes them, but it does not change clocks or power limits.
On H100/HGX-class systems, keep GPU power, module power, and GPU memory power
readings separate. The current component coefficients use NVML GPU/device total
energy deltas where available, not module-level or memory-subsystem-only power.
Across GPU generations, `nvmlDeviceGetPowerUsage` is not a uniform energy
source: V100/A100 profiles treat it as instantaneous power, while RTX 3090/H100
profiles treat it as one-second average power. It is therefore only a fallback
or diagnostic path in this repository; final component coefficients require the
NVML total-energy mJ counter whenever the runtime exposes it.

## CLI Examples

Feasibility only:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode shared_mma \
  --w-sm-kib 128 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --dry-run
```

Supported target profiles:

| profile | GPU family | CC | default SMs | L2 | combined L1/shared | shared allocation | max shared/block | max blocks/SM | NVML `GetPowerUsage` meaning |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `v100` | Volta GV100 | 7.0 | 80 | 6 MiB | 128 KiB/SM | 96 KiB/SM | 96 KiB/block | 32 | instantaneous |
| `rtx3090` | Ampere GA10x | 8.6 | 82 | 6 MiB | 128 KiB/SM | 100 KiB/SM | 99 KiB/block | 16 | 1-second average (`one_sec_average`) |
| `a100` | Ampere GA100 | 8.0 | 108 | 40 MiB | 192 KiB/SM | 164 KiB/SM | 163 KiB/block | 32 | instantaneous |
| `h100` | Hopper GH100 | 9.0 | 132 default, runtime/SKU should be checked | 50 MiB | 256 KiB/SM | 228 KiB/SM | 227 KiB/block | 32 | 1-second average (`one_sec_average`) |

`combined L1/shared` is the SM-local unified capacity. `shared allocation`
is the CUDA shared-memory capacity used for feasibility checks. Do not treat
these two columns as the same quantity.
The NVML power column is only the meaning of `nvmlDeviceGetPowerUsage`; final
energy runs prefer `nvmlDeviceGetTotalEnergyConsumption` when the runtime device
supports it. See `docs/platforms/power_measurement_api_matrix_ko.md` for the
full API matrix and reporting rules.

Power measurement acceptance:

| status | required metadata |
|---|---|
| final candidate | `nvml_total_energy_supported=true`, `energy_source=nvml_total_energy`, `energy_integration_method=total_energy_mj_delta`, explicit `measurement_scope=gpu_device_total_energy_counter`, expected `nvml_power_usage_semantics` |
| provisional only | `energy_source=legacy_get_power_usage_integral` or missing total energy counter |
| reject for coefficient | mixed energy sources, wrong profile power semantics, non-GPU/device measurement scope, or missing NCU path validation |

Across RTX 3090, V100, A100, and H100, do not infer final energy validity from
GPU name alone. Check the raw CSV metadata and the power API matrix. The final
numerator is the NVML GPU/device total-energy mJ delta when available;
`GetPowerUsage`, `power.draw.*`, Hopper module power, and GPU memory power are
fallback or metadata scopes with different meanings.
For new finalplan runs, run `scripts/audit_power_api_measurements.py` with
`--require-explicit-measurement-scope`. Historical rows whose scope can only be
inferred from source/integration should be reported as legacy/inferred-scope
evidence, not strict cross-platform final evidence.
Matched-control analysis can also take a power-state audit CSV; rows marked
`status=reject` or `coefficient_eligible=false` are excluded from coefficient
pairing when `--exclude-power-state-rejects` is used.

Run a support preflight before collecting new data:

```bash
python3 scripts/audit_platform_power_readiness.py \
  --out-csv results/summary/platform_power_readiness_audit_YYYYMMDD.csv \
  --out-md results/summary/platform_power_readiness_audit_YYYYMMDD.md
```

This readiness audit checks static consistency across RTX 3090, V100, A100, and
H100 profiles. It does not replace node-local power API, NCU, or reliability
audits.

```bash
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile auto \
  --ncu /path/to/ncu \
  --nvcc /path/to/nvcc \
  --out results/summary/gpu_support_preflight.md
```

The preflight records the detected profile, combined/shared capacity metadata,
NVML/NVIDIA driver state, CUDA compiler target support, Nsight Compute chip
support, and a binary dry-run result.
For final A100/V100/H100 command packages, use the generated script. It runs
preflight with an explicit `--target-profile <profile> --strict`, so a wrong GPU,
missing CUDA compiler/NCU target support, or failed binary dry-run stops before
energy collection.
Returned platform packages are accepted only when the preflight markdown records
`strict=true`, `profile_gate=pass`, `cuda_compiler_gate=pass`, `ncu_gate=pass`,
`dry_run_gate=pass`, `overall=pass`, and `errors=none`. A non-strict, warning-only, or failed
preflight is treated as an intake failure even if the later CSV files exist.

Single GPU Tensor Core treatment/control sanity run:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_operand_only \
  --w-sm-kib 2048 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_fp16_energy_v2_raw.csv

./build/a100_fp16_energy_v2 \
  --gpu-list 0 \
  --mode reg_mma \
  --w-sm-kib 2048 \
  --blocks-per-sm 16 \
  --target-profile rtx3090 \
  --active-sm 82 \
  --seconds 10 \
  --repeats 5 \
  --output results/raw/a100_fp16_energy_v2_raw.csv
```

L2 and DRAM path examples:

```bash
./build/a100_fp16_energy_v2 --gpu-list 0 --mode l2_cg_load_only \
  --w-sm-kib 64 --blocks-per-sm 16 --target-profile rtx3090 --active-sm 82 --seconds 10

./build/a100_fp16_energy_v2 --gpu-list 0 --mode dram_cg_load_only \
  --w-sm-kib 8192 --blocks-per-sm 16 --target-profile rtx3090 --active-sm 82 --seconds 10
```

Idle baseline with zero active GPUs:

```bash
./build/a100_fp16_energy_v2 \
  --gpu-list none --mode idle --w-sm-kib 1 --blocks-per-sm 1 \
  --target-profile rtx3090 --active-sm 82 --seconds 10 --repeats 5
```

## Modes

The binary still supports several historical and diagnostic modes, but the
current component-energy claim should be based on the acceptance-first finalplan
subset below.

Primary finalplan modes:

| component/path | treatment mode | control mode | why it is used |
|---|---|---|---|
| Tensor MMA increment | `reg_mma` | `reg_operand_only` | RF별 treatment 목표와 control 최소시간을 각각 calibration하고 두 ITER 중 큰 값을 두 mode에 동일 적용한 뒤 direct net-energy 차분으로 extra WMMA/HMMA work를 추정 |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | measures a simple shared-memory scalar load path without Tensor Core work |
| Global L1 hit path | `global_l1_load_only` | `global_addr_only` | same address/tile/repeat control; NCU must show L1-hit-dominated traffic |
| L2 hit path | `l2_cg_load_only` | `global_addr_only` | uses cache-global loads to reduce L1 participation and target L2-hit traffic |
| L2 capacity diagnostic | `l2_load_only` | none | normal global-load diagnostic; excluded from strict L2 coefficient because it can hit L1 |
| DRAM streaming sanity | `dram_cg_load_only` | `global_addr_only` | treatment/control-floor dual calibration, identical ITER, direct net-energy subtraction; NCU must show DRAM-dominant traffic |

Final platform packages pass `--require-control-ncu-acceptance`. Consequently,
`reg_operand_only` and `global_addr_only` must have an accepted NCU row at the
same `W_SM`, blocks/SM, active-SM, and RF/LR coordinate as the treatment. A
clean treatment row is insufficient when its subtraction control is unverified.

Control and diagnostic modes:

| mode | status | purpose |
|---|---|---|
| `idle` | support | no kernel; records NVML energy delta during sleep |
| `empty` | diagnostic | same grid shape, persistent loop, no MMA; older control, not the final matched-control default |
| `clocked_empty` | shared-path control | duration-calibrated scheduler/control loop with no operand traffic |
| `global_addr_only` | primary global-memory control | same global address/tile/repeat/checksum loop without an input load |
| `reg_fragment_only` | diagnostic | WMMA fragment/register setup without MMA |
| `reg_operand_only` | primary control | one dependent register integer add per RF keeps the loop/fragments live without the former FP32 FMA/checksum or memory; `reg_mma` executes the same add so it cancels in the same-ITER direct difference |
| `reg_pressure` | diagnostic | scalar register-pressure payload sweep; do not report as pure register-file energy |
| `addr_only` | diagnostic | global-memory tile address walk without issuing operand loads |
| `shared_load_only` | diagnostic | shared WMMA operand loads without MMA; useful for NCU comparison, not primary coefficient |
| `shared_mma` | legacy/diagnostic | shared operand load plus MMA; useful for old sweep continuity, not primary coefficient |
| `l2_mma` | legacy/diagnostic | global L2-candidate operand load plus MMA; not primary coefficient |
| `dram_load_only` | diagnostic | non-CG DRAM candidate; cache behavior must be checked carefully |
| `dram_mma` | legacy/diagnostic | streaming global operand load plus MMA; not primary coefficient |
| `store_only` | diagnostic | repeated global store loop |
| `store_path` | diagnostic | output-side store overhead check |

`shared_mma` is not an A100-only concept. On RTX 3090 / Ampere GA102 it means
the operands are staged through CUDA shared memory and loaded into WMMA
fragments from the shared-memory address space. The physical L1/shared-memory
organization and limits differ from A100, so feasibility uses the RTX 3090
profile values rather than the A100 164 KiB shared/L1 budget.
The same interpretation applies to V100 and H100, but with their own profile
limits.

Invalid combinations fail before execution. The shared/L2/DRAM classification is
the design rule:

- `invalid_min_tile`: `W_SM_KiB < blocks_per_SM`. This applies to both a
  memory treatment and its `global_addr_only` matched control.
- `shared_resident`: `W_SM + B KiB <= profile shared KiB` and
  `W_SM/B <= profile max shared/block KiB`.
- `l2_candidate`: full-profile working set fits the nominal profile L2
  (`82 * W_SM <= 6MiB` for RTX 3090).
- `dram_mixed_streaming`: full-profile working set exceeds nominal profile L2.

The matrix CSV retains invalid rows with `valid=false`, but the runner does not
execute them. With `--execute`, it first sends every unique valid coordinate to
the binary with `--dry-run`; an unexpected Python/C++ feasibility mismatch is
reported before any energy command starts. For A100 Global L1, W16/B16,
W32/B16, and W32/B32 are valid, while W16/B32 is excluded.

## Sweep

Materialize the design matrix without executing:

```bash
python3 scripts/run_sweep.py --include-idle
```

Run the matrix:

```bash
python3 scripts/run_sweep.py \
  --include-idle \
  --execute \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --max-active-gpus 1 \
  --seconds 10 \
  --repeats 5
```

For short sanity runs, constrain the matrix:

```bash
python3 scripts/run_sweep.py --execute \
  --gpu-ids 0 \
  --modes reg_mma,shared_mma \
  --w-sm-kib-values 32,128 \
  --blocks-per-sm-values 1,8,16 \
  --active-sm-values 82 \
  --seconds 2 \
  --repeats 1
```

Component-decomposition now uses an acceptance-first finalplan flow for primary
results. Generate a platform-specific command plan, run energy sweeps without
NCU attached, run NCU sidecar validation separately, classify accepted paths,
then analyze matched controls with NCU byte-denominator scaling:

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 \
  --repeats 5

bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

Use `--target-profile v100` or `--target-profile h100` on those platforms.
Review the generated shell script before submitting a long cluster job. Final
byte-path claims must use `scripts/analyze_ncu_path_acceptance.py` and
`scripts/analyze_matched_control_energy.py --require-ncu-denominator`.

For a supplemental byte-variation stress test, the active regression runner can
bypass per-mode calibration and use fixed `ITER`:

```bash
python3 scripts/run_component_regression_sweep.py \
  --target-profile rtx3090 \
  --gpu-ids 0 \
  --modes shared_scalar_load_only,global_l1_load_only,l2_cg_load_only,dram_cg_load_only \
  --w-sm-kib-values 64,8192 \
  --blocks-per-sm-values 16 \
  --active-sm-values 82 \
  --reuse-factors 1 \
  --load-repeats 1,2,4,8 \
  --store-repeats 1 \
  --seconds 1 \
  --iters 1000000 \
  --repeats 1 \
  --execute
```

Fixed-ITER runs make logical bytes vary directly, but elapsed can spread widely.
Use them to check monotonicity and model identifiability, not as final physical
pJ/byte values without NCU traffic and stall validation.

## Legacy Archive

Older pair-centric, NNLS/regression, reference-aligned, and register-footprint
diagnostic flows were moved out of the active `scripts/` and `docs/` directories
to reduce confusion. They remain available for historical comparison under:

```text
archive/legacy_20260707/
```

Do not use archived scripts for new component-energy claims unless the report
explicitly labels them as legacy diagnostics. The current implementation path is the
acceptance-first finalplan flow above.

## Nsight Compute

Energy runs and NCU profiling runs are intentionally separate.

```bash
scripts/run_ncu.sh --query-metrics

MODE=shared_scalar_load_only W_SM_KIB=64 BLOCKS_PER_SM=16 ACTIVE_SM=82 GPU=0 \
  scripts/run_ncu.sh

MODE=dram_cg_load_only W_SM_KIB=8192 BLOCKS_PER_SM=16 CACHE_CONTROL=all \
  scripts/run_ncu.sh
```

NCU reports are written under `results/ncu/`. The raw energy CSV includes NCU
columns, initialized to zero; populate or join those columns from NCU exports
before using the NCU bytes/op visualization.
`scripts/run_ncu.sh` and `scripts/run_ncu_validation.sh` also export raw/details
NCU CSV files and generate cache summaries. `run_ncu_validation.sh` profiles
only the primary finalplan modes by default; set `INCLUDE_DIAGNOSTIC_NCU=1` to
also collect legacy/diagnostic modes such as `shared_mma`, `l2_mma`, and
`dram_mma`. The summary table includes aggregate and path-specific L1/L2 hit
rates (%), L1 request/hit/miss bytes, L2 read hit/miss sectors and bytes,
L1 accesses, L2 accesses (sectors), DRAM accesses (sectors), and DRAM bytes.
L1 accesses prefer request counters when NCU provides them and fall back to
sector counters otherwise.

For `ld.global.cg`, L1 request bytes are expected because the request traverses
L1TEX. They are not L1 cache-hit bytes. Strict L2 acceptance therefore checks
near-zero path-specific L1 hit bytes and at least 95% path-specific L2 read hit
rate instead of requiring total L1 request bytes to be near zero.
The timed CG paths are preceded by an `ld.global.cg` warm-up kernel rather than
a normal cached-load warm-up, avoiding pre-population of L1 by the harness.

Nsight Compute support is version dependent. As of the 2026-06-29 release
history, NVIDIA lists Nsight Compute 2026.2.1 as the latest public release, and
the release highlights announce dropped Volta support. The reviewed V100
baseline uses Nsight Compute 2024.3 as the confirmed GV100 reference and still
requires both `--list-chips` and `--query-metrics --chips gv100` to succeed.

## Plotting

```bash
python3 scripts/plot_results.py results/raw/a100_fp16_energy_v2_raw.csv \
  --outdir results/plots
```

Generated plots include:

- energy vs active GPU count
- energy vs active SM count
- pJ/FLOP vs blocks/SM
- pJ/FLOP vs `W_SM`
- pJ/input-bit vs `W_SM`
- NCU shared/L2/DRAM bytes per logical op vs `W_SM`
- feasibility heatmap
- regression residual plot when `predicted_E_J` exists in the CSV

## CSV Notes

Rows are per GPU. For multi-GPU runs, active GPU rows use per-GPU operation
counts:

```text
N_MMA = active_SM * blocks_per_SM * ITER
FLOP = N_MMA * 8192
input_bits = N_MMA * 8192
```

Aggregate multi-GPU energy by summing active rows with the same `run_id`. Inactive
GPU rows are still emitted so idle drift and system-side effects remain visible.

For non-idle modes the binary performs a pre-run idle measurement and stores an
elapsed-time-scaled `idle_baseline_J`. `net_E_J = delta_E_J - idle_baseline_J`.

## Current Limitations

- WMMA fallback is implemented; raw inline PTX `m16n8k16` and explicit
  `ldmatrix.shared` are future refinements.
- SM placement uses soft control (`grid = active_SM * blocks_per_SM`) plus SMID
  histogram validation. Runs with `smid_histogram_ok=false` should be excluded
  from primary analysis.
- Reported coefficients are effective microbenchmark coefficients, not pure
  physical component energies. Prefer labels such as `effective Tensor Engine +
  register`, `effective shared/L1 path`, `effective L2-hit path`, and `effective
  DRAM streaming path`.
- Do not report `*_load_only - empty` pair coefficients as physical component
  energy unless elapsed-time matching and NCU traffic validation pass. Large
  elapsed ratios or negative `*_mma - *_load_only` coefficients mean the pair is
  diagnostic-only.
- V100/A100/H100 DRAM packages require `--memory-pair-lock-iters` and
  `--dram-pair-policy matched-iters`. A duration-scaled DRAM row or `iter_ratio != 1`
  is rejected even when NCU shows a DRAM-dominant path.

## Included Reference Assets

- `docs/design/a100_fp16_energy_experiment_design_v2.md`
- `docs/assets/a100_v2_design/a100_v2_feasibility_matrix.csv`
- `docs/assets/a100_v2_design/a100_v2_feasibility_heatmap.png`
- `docs/assets/a100_v2_design/a100_v2_workingset_boundaries.png`
- `docs/assets/a100_v2_design/a100_v2_ops_per_iteration.png`
