# GPU Component Energy Experiment Presentation Evidence Notes

## Deck identity

- Repository: `https://github.com/bang001/gpupower0701`
- Generated from the current worktree on 2026-07-12.
- The title slide records the checked-out branch and HEAD SHA.
- The deck has 22 slides and three generated technical illustrations.

## Source-of-truth order

1. CUDA/NVML implementation and generated planner commands
2. Raw CSV columns and artifact provenance
3. NCU, power, reliability, strict, and package audit artifacts
4. Active methodology/platform documentation
5. Official NVIDIA NVML API documentation for API semantics

## Slide evidence

1. **Title** — repository/HEAD from Git; generated system illustration.
2. **Purpose** — `README.md`, `scripts/plan_platform_component_experiment.py`.
3. **Interpretation boundary** — `src/main.cu`, `scripts/analyze_matched_control_energy.py`.
4. **System** — `src/main.cu`, `src/nvml_energy.cpp`, `scripts/run_ncu_validation.sh`. The pictured instrument is conceptual; actual code uses NVML, not an external meter.
5. **Hierarchy** — `include/config.hpp`, `src/kernels.cu`, `docs/methodology/howitworks.md`.
6. **Repository map** — `src/`, `include/`, `scripts/`, `results/`.
7. **Active pairs** — `scripts/analyze_matched_control_energy.py:25-81`, `scripts/build_strict_component_summary.py:34-62`.
8. **Core pipeline** — generated command packages.
9. **Actual pipeline** — `scripts/plan_platform_component_experiment.py:430-1016`.
10. **Profiles and blocks/SM sweep** — `include/config.hpp:18-135`, planner profiles, and `platform_blocks_per_sm_sweep.png`. V100 uses B4/B16 sensitivity points and the strict B32 anchor; requested blocks/SM still needs NCU occupancy/resource validation.
11. **Platform W_SM path sweep** — planner profiles, generated `*_command_plan.md`, and `platform_wsm_path_sweep.png`. Shared is a separate address-space path; only global-memory candidates are interpreted across L1/L2/DRAM after exact-coordinate NCU acceptance.
12. **Host sequence** — `src/main.cu:628-650,919-1010`.
13. **Raw energy** — `src/main.cu:417-425,692-720,950-978`.
14. **Memory differential** — `scripts/analyze_matched_control_energy.py:620-658`. Shared/L1/L2 can use duration-scaled control power. Current DRAM finalplan requires matched ITER and direct net-energy subtraction.
15. **Tensor differential** — `scripts/run_component_regression_sweep.py:323-430`; matched-ITER fields in matched detail.
16. **Energy vs NCU** — planner comments #5 and #8.
17. **Tensor denominator** — `include/config.hpp:12-16`, `src/main.cu:781-791`. NCU HMMA is validation evidence, not the final FLOP denominator.
18. **Memory denominator** — `scripts/analyze_matched_control_energy.py:339-399,643-658`. `expected_no_ncu_match` is not eligible for strict memory coefficients.
19. **NCU acceptance** — `scripts/analyze_ncu_path_acceptance.py`. Acceptance uses path-specific rates plus access/byte/local/stall evidence, not aggregate hit rate alone.
20. **Audit states** — each audit script owns a distinct state vocabulary; states are not collapsed into one grade.
21. **RTX 3090 snapshot and DRAM policy** — the historical strict snapshot contains four rows and fails the active control/schema reaudit. DRAM is now shown as the 26.709-28.409 pJ/bit `provisional_reference_aligned_range` from `rtx3090_dram_current_reporting_policy_20260712.csv`; no completed matched-ITER address-control raw pair exists, so the band is not strict measured evidence.
22. **Cross-platform state** — current readiness/package audits. A command package is not evidence that a target-node experiment completed.

## Corrected statements

- The strict RTX 3090 snapshot has four historical components, not five. DRAM is displayed separately as a provisional cumulative-path reporting band.
- Global L1 and L2 historical rows used `clocked_empty`; active finalplan uses `global_addr_only`.
- Current DRAM finalplan uses pair-locked identical ITER; it is not duration-scaled.
- `l2_load_only` is a normal global-load capacity diagnostic, not automatic strict L2-only evidence.
- The H100 implementation is FP16 WMMA compatibility code, not Hopper-native WGMMA/TMA.
- NVML total-energy delta is labeled GPU/device scope. It is not represented as an external whole-board meter.

## Official NVIDIA references

- NVML API Reference, `nvmlDeviceGetTotalEnergyConsumption`: https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html
  - Reports total GPU energy in mJ since driver reload; supported on Volta or newer fully supported devices.
- NVML API Reference, `nvmlDeviceGetPowerUsage`: https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html
  - Ampere except GA100 and newer: 1-second averaged power.
  - GA100 and older: instantaneous power.
  - The API reports GPU power and associated circuitry such as memory.

## Generated illustrations

The three raster illustrations were generated with the built-in image generation tool using the `scientific-educational` use case. Exact labels, equations, and status values are PowerPoint text/shapes so that technical claims are not dependent on generated in-image text.
