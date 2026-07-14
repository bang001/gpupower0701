# GPU Component Energy Experiment Presentation

This directory contains the presentation source, generated PowerPoint, generated
technical illustrations, and platform sweep charts used by the deck.

## Deliverables

- `gpu_component_energy_experiment_whitepaper_ko.pptx`: 22-slide Korean deck
- `gpu_component_energy_experiment_whitepaper_ko.pdf`: rendered review copy
- `gpu_component_energy_experiment_whitepaper_ko.md`: slide-by-slide evidence notes
- `gpu_component_energy_experiment_whitepaper_ko_rendered_contact_sheet.png`: actual LibreOffice render review sheet
- `gpu_component_energy_experiment_whitepaper_ko_contact_sheet.png`: lightweight shape-layout diagnostic
- `assets/system_measurement_architecture.png`: system configuration illustration
- `assets/treatment_control_method.png`: differential method illustration
- `assets/ncu_audit_validation.png`: validation and audit illustration
- `assets/platform_blocks_per_sm_sweep.png`: platform-specific blocks/SM sweep and strict NCU anchors
- `assets/platform_wsm_path_sweep.png`: platform-specific Shared, Global L1, L2, and DRAM W_SM candidates
- `assets/platform_capacity_context.png`: selected working sets relative to per-SM and L2 capacities
- `../assets/component_energy_method/external_memory_scope_comparison.png`: user-reported effective-path observations and literature device-reference scopes
- `image_generation_prompts.md`: reproducible prompt summaries and generation mode

## Regeneration

```bash
python3 scripts/build_gpu_component_energy_presentation.py
```

The deck builder regenerates the three sweep charts through
`scripts/plot_platform_sweep_design.py` before assembling the slides. Run the
chart script with `--self-test` when changing platform profiles.
It also runs `scripts/plot_external_memory_scope_review.py`, which keeps
GPU-device effective-path observations separate from memory-device references.

The script reads repository code and result artifacts. Historical RTX 3090
numbers are intentionally labeled as a 2026-07-08 snapshot and are not promoted
to current-protocol final coefficients.
