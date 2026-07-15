# Documentation Consistency Audit

- Checks: 27
- Pass: 27
- Fail: 0

| Area | Check | Status | Actual | Evidence |
|---|---|---|---|---|
| links | `active_markdown_local_links` | **pass** | checked=97 | `README.md;SKILL.md;docs/**/*.md` |
| links | `archive_markdown_local_links` | **pass** | checked=70 | `archive/**/*.md` |
| inventory | `canonical_active_documents` | **pass** | all present | `docs/README.md` |
| inventory | `superseded_v2_design_archived` | **pass** | active=False,archive=True | `docs/design/a100_fp16_energy_experiment_design_v2.md;archive/superseded_v2_design_20260714/docs/design/a100_fp16_energy_experiment_design_v2.md` |
| policy | `no_stale_active_document_paths` | **pass** | none | `README.md;SKILL.md;docs/**/*.md` |
| policy | `no_superseded_l2_energy_policy` | **pass** | none | `README.md;SKILL.md;docs/**/*.md` |
| policy | `current_tensor_revision_v6` | **pass** | all current | `README.md;src/main.cu;scripts/plan_platform_component_experiment.py;docs/platforms/a100_node_experiment_guide_ko.md;docs/platforms/v100_node_experiment_guide_ko.md;docs/platforms/h100_node_experiment_guide_ko.md` |
| policy | `required_terms:README.md` | **pass** | all present | `README.md` |
| policy | `required_terms:SKILL.md` | **pass** | all present | `SKILL.md` |
| policy | `required_terms:docs/methodology/component_energy_method_comparison_ko.md` | **pass** | all present | `docs/methodology/component_energy_method_comparison_ko.md` |
| policy | `required_terms:docs/methodology/howitworks.md` | **pass** | all present | `docs/methodology/howitworks.md` |
| policy | `required_terms:docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md` | **pass** | all present | `docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md` |
| policy | `required_terms:docs/results/gpu_power_modeling_experiment_results_ko.md` | **pass** | all present | `docs/results/gpu_power_modeling_experiment_results_ko.md` |
| policy | `required_terms:docs/audits/component_energy_self_critique_ko.md` | **pass** | all present | `docs/audits/component_energy_self_critique_ko.md` |
| policy | `required_terms:scripts/plan_platform_component_experiment.py` | **pass** | all present | `scripts/plan_platform_component_experiment.py` |
| policy | `required_terms:scripts/run_ncu_validation.sh` | **pass** | all present | `scripts/run_ncu_validation.sh` |
| policy | `required_terms:scripts/summarize_ncu_cache_metrics.py` | **pass** | all present | `scripts/summarize_ncu_cache_metrics.py` |
| policy | `required_terms:scripts/build_platform_intake_dashboard.py` | **pass** | all present | `scripts/build_platform_intake_dashboard.py` |
| policy | `required_terms:scripts/run_local_readiness_checks.sh` | **pass** | all present | `scripts/run_local_readiness_checks.sh` |
| profiles | `rtx3090_profile_consistency` | **pass** | compared=26 | `include/config.hpp;scripts/run_sweep.py;scripts/preflight_gpu_support.py;scripts/plan_platform_component_experiment.py` |
| profiles | `v100_profile_consistency` | **pass** | compared=26 | `include/config.hpp;scripts/run_sweep.py;scripts/preflight_gpu_support.py;scripts/plan_platform_component_experiment.py` |
| profiles | `a100_profile_consistency` | **pass** | compared=26 | `include/config.hpp;scripts/run_sweep.py;scripts/preflight_gpu_support.py;scripts/plan_platform_component_experiment.py` |
| profiles | `h100_profile_consistency` | **pass** | compared=26 | `include/config.hpp;scripts/run_sweep.py;scripts/preflight_gpu_support.py;scripts/plan_platform_component_experiment.py` |
| modes | `cpp_mode_inventory` | **pass** | idle,empty,clocked_empty,reg_fragment_only,reg_operand_only,reg_mma,reg_pressure,addr_only,global_addr_only,global_l1_load_only,shared_scalar_addr_only,shared_scalar_load_only,shared_load_only,shared_mma,l2_load_only,l2_cg_load_only,l2_mma,dram_load_only,dram_cg_load_only,dram_mma,store_only,store_path | `include/config.hpp` |
| modes | `primary_mode_integration` | **pass** | complete | `README.md;SKILL.md;scripts/plan_platform_component_experiment.py;scripts/run_ncu_validation.sh` |
| modes | `diagnostic_mode_classification` | **pass** | complete | `README.md;SKILL.md` |
| assets | `active_component_assets_referenced` | **pass** | all referenced | `docs/assets/component_energy_method` |
