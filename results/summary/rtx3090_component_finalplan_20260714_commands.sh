#!/usr/bin/env bash
set -euo pipefail

# Generated for rtx3090 on 2026-07-14.
# RTX 3090 / GA102 GDDR6X path. External-memory W_SM sweep spans about 3.4x-27.3x nominal L2. Use total-energy rows; GetPowerUsage fallback has one-second-average semantics.
mkdir -p results/raw results/summary results/ncu

# NCU wrapper. Counter access is probed before the long energy sweep.
# ERR_NVGPUCTRPERM triggers one sudo retry by default; set NCU_AUTO_SUDO=0 to disable.
NCU_BIN_DEFAULT=ncu
NCU_BIN="${NCU_BIN:-${NCU_BIN_DEFAULT}}"
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_AUTO_SUDO="${NCU_AUTO_SUDO:-1}"
NCU_SUDO="${NCU_SUDO:-sudo -E}"
export NCU_USE_SUDO NCU_AUTO_SUDO NCU_SUDO
NVCC_COMMAND="${NVCC:-nvcc}"
if [[ "${NCU_USE_SUDO}" == "1" ]]; then
  NCU_COMMAND="${NCU_SUDO} ${NCU_BIN}"
else
  NCU_COMMAND="${NCU_BIN}"
fi
echo "Using NCU command: ${NCU_COMMAND}"
echo "NCU permission policy: use_sudo=${NCU_USE_SUDO} auto_sudo=${NCU_AUTO_SUDO}"
echo "Using CUDA compiler: ${NVCC_COMMAND}"
L2_BLOCKS_PER_SM=8
L2_RESIDENCY_POLICY=normal
L2_ADDRESS_LAYOUT=contiguous
export L2_BLOCKS_PER_SM L2_RESIDENCY_POLICY L2_ADDRESS_LAYOUT

# 1. Preflight
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile rtx3090 --strict --active-sm 82 --binary ./build/a100_fp16_energy_v2 --ncu "${NCU_COMMAND}" --nvcc "${NVCC_COMMAND}" --out results/summary/rtx3090_component_finalplan_20260714_preflight.md

# 1a. Actual hardware-counter permission probe before expensive energy sweeps.
NCU_PROBE_DIR="${TMPDIR:-/tmp}/gpupower_ncu_probe_rtx3090_${UID}_${PPID}"
NCU_PROBE_RAW="${NCU_PROBE_DIR}/probe_raw.csv"
NCU_PERMISSION_PROBE_ONLY=1 NCU_EXPLICIT_METRICS_ONLY=1 NCU_METRICS=sm__cycles_elapsed.avg NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build/a100_fp16_energy_v2 OUTDIR="${NCU_PROBE_DIR}" RAW_OUT="${NCU_PROBE_RAW}" TARGET_PROFILE=rtx3090 NCU_CHIP=ga102 NCU_FILTER_UNAVAILABLE_METRICS=0 GPU=0 ACTIVE_SM=82 BLOCKS_PER_SM=8 bash scripts/run_ncu_validation.sh
echo "NCU hardware-counter permission probe passed: ${NCU_PROBE_DIR}"
if [[ -f "${NCU_PROBE_DIR}/ncu_permission_mode.txt" ]] && grep -q '^mode=auto_sudo$' "${NCU_PROBE_DIR}/ncu_permission_mode.txt"; then
  NCU_USE_SUDO=1
  export NCU_USE_SUDO
  NCU_COMMAND="${NCU_SUDO} ${NCU_BIN}"
  echo "NCU permission probe selected sudo for the remaining NCU stages."
fi

# 2. Pipeline policy self-tests. Fail early if a gate is broken.
python3 scripts/run_component_regression_sweep.py --self-test
python3 scripts/summarize_ncu_cache_metrics.py --self-test
python3 scripts/merge_ncu_validation_summaries.py --self-test
python3 scripts/analyze_ncu_path_acceptance.py --self-test
python3 scripts/audit_tensor_mma_binary.py --self-test
python3 scripts/select_l2_path_configuration.py --self-test
python3 scripts/analyze_matched_control_energy.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/remediate_wsl_wallclock_intervals.py --self-test
python3 scripts/audit_a100_tensor_l2_remediation.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/write_platform_result_manifest.py --self-test
python3 scripts/audit_documentation_consistency.py --self-test
python3 scripts/selftest_platform_package_gates.py
env -u NCU_USE_SUDO -u NCU_AUTO_SUDO -u NCU_SUDO bash scripts/selftest_ncu_permission_fallback.sh
python3 scripts/audit_documentation_consistency.py --out-csv results/summary/rtx3090_component_finalplan_20260714_documentation_consistency_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_documentation_consistency_audit.md --fail-on-error

# 3. Move stale generated outputs aside before writing new CSV schemas.
RUN_STAMP=$(date +%Y%m%d_%H%M%S)
STALE_DIR=results/archive/rtx3090_component_finalplan_20260714_stale_${RUN_STAMP}
STALE_PATHS=(
  results/raw/rtx3090_component_finalplan_20260714_schema_smoke.csv
  results/summary/rtx3090_component_finalplan_20260714_schema_smoke_power_api_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_schema_smoke_power_api_audit.md
  results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.md
  results/raw/rtx3090_component_finalplan_20260714_tensor_pair_calibration.csv
  results/raw/rtx3090_component_finalplan_20260714_shared_pair_calibration.csv
  results/raw/rtx3090_component_finalplan_20260714_l1_pair_calibration.csv
  results/raw/rtx3090_component_finalplan_20260714_l2_pair_calibration.csv
  results/raw/rtx3090_component_finalplan_20260714_dram_pair_calibration.csv
  results/summary/rtx3090_component_finalplan_20260714_l2_path_selection.csv
  results/summary/rtx3090_component_finalplan_20260714_l2_path_selection.md
  results/summary/rtx3090_component_finalplan_20260714_l2_path_selection.env
  results/raw/rtx3090_component_finalplan_20260714_tensor.csv
  results/raw/rtx3090_component_finalplan_20260714_shared.csv
  results/raw/rtx3090_component_finalplan_20260714_l1.csv
  results/raw/rtx3090_component_finalplan_20260714_l2.csv
  results/raw/rtx3090_component_finalplan_20260714_dram.csv
  results/raw/rtx3090_component_finalplan_20260714_tensor_matrix.csv
  results/raw/rtx3090_component_finalplan_20260714_shared_matrix.csv
  results/raw/rtx3090_component_finalplan_20260714_l1_matrix.csv
  results/raw/rtx3090_component_finalplan_20260714_l2_matrix.csv
  results/raw/rtx3090_component_finalplan_20260714_dram_matrix.csv
  results/raw/rtx3090_component_finalplan_ncu_factor_20260714.csv
  results/raw/rtx3090_component_finalplan_ncu_l2_minimal_20260714.csv
  results/raw/rtx3090_component_finalplan_ncu_dram_minimal_20260714.csv
  results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv
  results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.md
  results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_power_api_audit.md
  results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_power_state_audit.md
  results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv
  results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv
  results/summary/rtx3090_component_finalplan_20260714_matched_control_report.md
  results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.md
  results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.csv
  results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.md
  results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.csv
  results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md
  results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.csv
  results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.md
  results/summary/rtx3090_component_finalplan_20260714_result_manifest.csv
  results/summary/rtx3090_component_finalplan_20260714_result_manifest.md
  results/summary/rtx3090_platform_result_package_audit_20260714.csv
  results/summary/rtx3090_platform_result_package_audit_20260714.md
  results/summary/rtx3090_platform_result_package_gaps_20260714.csv
  results/summary/rtx3090_platform_result_package_gaps_20260714.md
)
for path in "${STALE_PATHS[@]}"; do
  if [[ -e "${path}" ]]; then
    mkdir -p "${STALE_DIR}/$(dirname "${path}")"
    mv "${path}" "${STALE_DIR}/${path}"
  fi
done
if [[ -e results/ncu/rtx3090_component_finalplan_ncu_factor_20260714 ]]; then
  mkdir -p "${STALE_DIR}/$(dirname results/ncu/rtx3090_component_finalplan_ncu_factor_20260714)"
  mv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714 "${STALE_DIR}/results/ncu/rtx3090_component_finalplan_ncu_factor_20260714"
fi

# 4. Three-row schema/revision smoke test. Catch stale binaries before the full sweep.
./build/a100_fp16_energy_v2 --gpu-list 0 --mode clocked_empty --w-sm-kib 1 --blocks-per-sm 1 --target-profile rtx3090 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/rtx3090_component_finalplan_20260714_schema_smoke.csv --verify-smid 0
./build/a100_fp16_energy_v2 --gpu-list 0 --mode reg_operand_only --w-sm-kib 1 --blocks-per-sm 1 --target-profile rtx3090 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/rtx3090_component_finalplan_20260714_schema_smoke.csv --verify-smid 0
./build/a100_fp16_energy_v2 --gpu-list 0 --mode l2_cg_load_only --w-sm-kib 32 --blocks-per-sm 1 --target-profile rtx3090 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/rtx3090_component_finalplan_20260714_schema_smoke.csv --verify-smid 0
python3 scripts/audit_power_api_measurements.py results/raw/rtx3090_component_finalplan_20260714_schema_smoke.csv --target-profile rtx3090 --out-csv results/summary/rtx3090_component_finalplan_20260714_schema_smoke_power_api_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_schema_smoke_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-exact-measurement-interval --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_inplace_signflip_observable_control_fixed_rf_v5 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_inplace_signflip_observable_control_fixed_rf_v5 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=input_data_pattern=splitmix64_uniform_fp16_v1
python3 scripts/audit_tensor_mma_binary.py --binary ./build/a100_fp16_energy_v2 --profile rtx3090 --out-csv results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_tensor_mma_binary_audit.md

# 5. This profile retains its reviewed fixed L2 coordinate.
echo "L2 precheck selector not enabled for this profile; using policy=${L2_RESIDENCY_POLICY} layout=${L2_ADDRESS_LAYOUT} blocks/SM=${L2_BLOCKS_PER_SM}"

# 6. Energy sweeps. Keep NCU detached from these runs.
python3 scripts/run_component_regression_sweep.py --execute --binary ./build/a100_fp16_energy_v2 --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --modes reg_operand_only,reg_mma --w-sm-kib-values 1 --blocks-per-sm-values 4,8,16 --active-sm-values 82 --reuse-factors 1,2,4,8,16 --load-repeats 1 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/rtx3090_component_finalplan_20260714_tensor.csv --matrix-csv results/raw/rtx3090_component_finalplan_20260714_tensor_matrix.csv --tensor-pair-lock-iters --tensor-pair-control-min-seconds 1.0 --pair-calibration-csv results/raw/rtx3090_component_finalplan_20260714_tensor_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build/a100_fp16_energy_v2 --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --modes shared_scalar_addr_only,shared_scalar_load_only --w-sm-kib-values 64 --blocks-per-sm-values 8 --active-sm-values 82 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/rtx3090_component_finalplan_20260714_shared.csv --matrix-csv results/raw/rtx3090_component_finalplan_20260714_shared_matrix.csv --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/rtx3090_component_finalplan_20260714_shared_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build/a100_fp16_energy_v2 --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,global_l1_load_only --w-sm-kib-values 8 --blocks-per-sm-values 8 --active-sm-values 82 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/rtx3090_component_finalplan_20260714_l1.csv --matrix-csv results/raw/rtx3090_component_finalplan_20260714_l1_matrix.csv --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/rtx3090_component_finalplan_20260714_l1_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build/a100_fp16_energy_v2 --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,l2_cg_load_only --w-sm-kib-values 32,64 --blocks-per-sm-values 8 --active-sm-values 82 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/rtx3090_component_finalplan_20260714_l2.csv --matrix-csv results/raw/rtx3090_component_finalplan_20260714_l2_matrix.csv --global-warmup-passes 4 --l2-residency-policy "${L2_RESIDENCY_POLICY}" --l2-address-layout "${L2_ADDRESS_LAYOUT}" --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/rtx3090_component_finalplan_20260714_l2_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build/a100_fp16_energy_v2 --target-profile rtx3090 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,dram_cg_load_only --w-sm-kib-values 256,512,2048 --blocks-per-sm-values 8 --active-sm-values 82 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/rtx3090_component_finalplan_20260714_dram.csv --matrix-csv results/raw/rtx3090_component_finalplan_20260714_dram_matrix.csv --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/rtx3090_component_finalplan_20260714_dram_pair_calibration.csv

# 7. Power API audit before spending time on NCU.
python3 scripts/audit_power_api_measurements.py results/raw/rtx3090_component_finalplan_20260714_tensor.csv results/raw/rtx3090_component_finalplan_20260714_shared.csv results/raw/rtx3090_component_finalplan_20260714_l1.csv results/raw/rtx3090_component_finalplan_20260714_l2.csv results/raw/rtx3090_component_finalplan_20260714_dram.csv --target-profile rtx3090 --out-csv results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-exact-measurement-interval --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_inplace_signflip_observable_control_fixed_rf_v5 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_inplace_signflip_observable_control_fixed_rf_v5 --require-mode-notes-marker shared_scalar_addr_only=shared_pair_kernel_revision=matched_shared_addr_v1 --require-mode-notes-marker shared_scalar_load_only=shared_pair_kernel_revision=matched_shared_addr_v1 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=input_data_pattern=splitmix64_uniform_fp16_v1

# 7. Power-state row-quality audit. This does not replace the power API gate.
python3 scripts/audit_power_state_stability.py results/raw/rtx3090_component_finalplan_20260714_tensor.csv results/raw/rtx3090_component_finalplan_20260714_shared.csv results/raw/rtx3090_component_finalplan_20260714_l1.csv results/raw/rtx3090_component_finalplan_20260714_l2.csv results/raw/rtx3090_component_finalplan_20260714_dram.csv --out-csv results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_power_state_audit.md

# 8a. Selected L2 path: minimal coherent counter bundle for gating.
NCU_COMPONENTS=l2 NCU_EXPLICIT_METRICS_ONLY=1 NCU_METRIC_PROFILE=l2_path_minimal NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build/a100_fp16_energy_v2 OUTDIR=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/l2_selected_minimal RAW_OUT=results/raw/rtx3090_component_finalplan_ncu_l2_minimal_20260714.csv SUMMARY_CSV=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/l2_selected_minimal/ncu_cache_validation_summary.csv SUMMARY_MD=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/l2_selected_minimal/ncu_cache_validation_summary.md TARGET_PROFILE=rtx3090 NCU_CHIP=ga102 NCU_FILTER_UNAVAILABLE_METRICS=1 GPU=0 ACTIVE_SM=82 BLOCKS_PER_SM="${L2_BLOCKS_PER_SM}" L2_BLOCKS_PER_SM="${L2_BLOCKS_PER_SM}" L2_W_SM_KIB_VALUES=32,64 MEMORY_LOAD_REPEATS=4,8,16 GLOBAL_WARMUP_PASSES=4 L2_RESIDENCY_POLICY="${L2_RESIDENCY_POLICY}" L2_ADDRESS_LAYOUT="${L2_ADDRESS_LAYOUT}" INCLUDE_L2_CAPACITY_NCU=0 INCLUDE_DIAGNOSTIC_NCU=0 bash scripts/run_ncu_validation.sh

# 8b. External-memory path: minimal coherent memory-counter bundle.
NCU_COMPONENTS=dram NCU_EXPLICIT_METRICS_ONLY=1 NCU_METRIC_PROFILE=l2_path_minimal NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build/a100_fp16_energy_v2 OUTDIR=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/external_memory_minimal RAW_OUT=results/raw/rtx3090_component_finalplan_ncu_dram_minimal_20260714.csv SUMMARY_CSV=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/external_memory_minimal/ncu_cache_validation_summary.csv SUMMARY_MD=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/external_memory_minimal/ncu_cache_validation_summary.md TARGET_PROFILE=rtx3090 NCU_CHIP=ga102 NCU_FILTER_UNAVAILABLE_METRICS=1 GPU=0 ACTIVE_SM=82 BLOCKS_PER_SM=8 DRAM_W_SM_KIB_VALUES=256,512,2048 DRAM_LOAD_REPEATS=4,8,16 GLOBAL_WARMUP_PASSES=4 INCLUDE_L2_CAPACITY_NCU=0 INCLUDE_DIAGNOSTIC_NCU=0 bash scripts/run_ncu_validation.sh

# 8c. Full diagnostic bundle for Tensor, Shared, and Global L1.
NCU_COMPONENTS=baseline,tensor,shared,l1 NCU_EXPLICIT_METRICS_ONLY=1 NCU_METRIC_PROFILE=full NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build/a100_fp16_energy_v2 OUTDIR=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/full_non_l2 RAW_OUT=results/raw/rtx3090_component_finalplan_ncu_factor_20260714.csv SUMMARY_CSV=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/full_non_l2/ncu_cache_validation_summary.csv SUMMARY_MD=results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/full_non_l2/ncu_cache_validation_summary.md TARGET_PROFILE=rtx3090 NCU_CHIP=ga102 NCU_FILTER_UNAVAILABLE_METRICS=1 GPU=0 ACTIVE_SM=82 BLOCKS_PER_SM=8 REG_BLOCKS_PER_SM=4 REG_BLOCKS_PER_SM_VALUES=4,8,16 REG_PRESSURE_PAYLOAD_BYTES=256 REG_W_SM_KIB=1 L1_W_SM_KIB=8 SHARED_W_SM_KIB=64 INCLUDE_DIAGNOSTIC_NCU=0 GLOBAL_WARMUP_PASSES=4 TENSOR_REUSE_FACTORS=1,2,4,8,16 MEMORY_LOAD_REPEATS=4,8,16 bash scripts/run_ncu_validation.sh

# 8d. Canonical summary: disjoint full core/local plus minimal memory rows.
python3 scripts/merge_ncu_validation_summaries.py results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/full_non_l2/ncu_cache_validation_summary.csv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/l2_selected_minimal/ncu_cache_validation_summary.csv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/external_memory_minimal/ncu_cache_validation_summary.csv --out-csv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv --out-md results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.md

# 9. Path acceptance.
python3 scripts/analyze_ncu_path_acceptance.py results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv --target-profile rtx3090 --out-csv results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv --out-md results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.md --tensor-memory-bytes-max 2e8 --register-memory-bytes-max 2e8 --tensor-memory-bytes-per-hmma-max 1.0 --register-memory-bytes-per-op-max 1.0 --require-ncu-replay-mode application --require-ncu-cache-control none --require-l2-residency-policy "${L2_RESIDENCY_POLICY}" --require-l2-address-layout "${L2_ADDRESS_LAYOUT}"

# 10. Matched-control analysis with NCU byte-denominator scaling.
python3 scripts/analyze_matched_control_energy.py results/raw/rtx3090_component_finalplan_20260714_tensor.csv results/raw/rtx3090_component_finalplan_20260714_shared.csv results/raw/rtx3090_component_finalplan_20260714_l1.csv results/raw/rtx3090_component_finalplan_20260714_l2.csv results/raw/rtx3090_component_finalplan_20260714_dram.csv --acceptance-csv results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv --ncu-summary-csv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv --power-state-audit-csv results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv --exclude-power-state-rejects --require-ncu-denominator --require-total-energy --expected-power-semantics one_sec_average --min-elapsed-s 8.0 --tensor-control-min-elapsed-s 0.8 --max-elapsed-ratio 1.35 --max-pair-transition-gap-ms 30000 --pairing nearest-control --tensor-pair-policy matched-iters --shared-pair-policy matched-iters --shared-control-min-elapsed-s 0.8 --l1-pair-policy matched-iters --l1-control-min-elapsed-s 0.8 --l2-pair-policy matched-iters --l2-control-min-elapsed-s 0.8 --dram-pair-policy matched-iters --dram-control-min-elapsed-s 0.8 --require-control-ncu-acceptance --min-delta-j 10.0 --min-delta-fraction 0.005 --out-summary-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv --out-detail-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv --out-md results/summary/rtx3090_component_finalplan_20260714_matched_control_report.md

# 11. Component reliability audit.
set +e
python3 scripts/audit_component_reliability.py --power-audit-csv results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv --ncu-acceptance-csv results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv --matched-summary-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv --matched-detail-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv --expected-power-semantics one_sec_average --out-csv results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.md --fail-on-reject
RELIABILITY_AUDIT_RC=$?
set -e

# 12. Matched-control instability/root-cause audit.
python3 scripts/audit_matched_control_instability.py results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv --out-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.csv --out-md results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.md

# 13. Build strict component summary package from accepted evidence.
set +e
python3 scripts/build_strict_component_summary.py --target-profile rtx3090 --gpu-label RTX3090 --matched-summary-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv --matched-detail-csv results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv --power-api-audit-csv results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv --power-state-audit-csv results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv --reliability-csv results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.csv --ncu-acceptance-csv results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv --ncu-summary-csv results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv --instability-artifact results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.csv --out-csv results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.csv --out-md results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md
STRICT_BUILD_RC=$?
set -e

# 14. Audit strict component summary against reliability/detail artifacts.
set +e
python3 scripts/audit_strict_component_summary.py --summary-csv results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.csv --expected-power-semantics one_sec_average --out-csv results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.csv --out-md results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.md --require-path-specific-cache-evidence --fail-on-fail
STRICT_AUDIT_RC=$?
set -e

# 15. Write the expected result manifest for copy-back and gap triage.
python3 scripts/write_platform_result_manifest.py --target-profile rtx3090 --tag 20260714 --expected-active-sm 82 --out-csv results/summary/rtx3090_component_finalplan_20260714_result_manifest.csv --out-md results/summary/rtx3090_component_finalplan_20260714_result_manifest.md

# 16. Audit the full platform result package before publishing or copying back.
set +e
python3 scripts/audit_platform_result_package.py --target-profile rtx3090 --tag 20260714 --expected-active-sm 82 --out-csv results/summary/rtx3090_platform_result_package_audit_20260714.csv --out-md results/summary/rtx3090_platform_result_package_audit_20260714.md --fail-on-incomplete
PACKAGE_AUDIT_RC=$?
set -e

# 17. Always write triage/goal-readiness/dashboard artifacts.
python3 scripts/summarize_platform_package_gaps.py --target-profile rtx3090 --tag 20260714 --audit-csv results/summary/rtx3090_platform_result_package_audit_20260714.csv --manifest-csv results/summary/rtx3090_component_finalplan_20260714_result_manifest.csv --out-csv results/summary/rtx3090_platform_result_package_gaps_20260714.csv --out-md results/summary/rtx3090_platform_result_package_gaps_20260714.md
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/audit_component_goal_readiness.py --ncu "${NCU_COMMAND}" --out-csv results/summary/component_energy_goal_readiness_audit_20260714.csv --out-md results/summary/component_energy_goal_readiness_audit_20260714.md
python3 scripts/build_platform_intake_dashboard.py --tag 20260714 --goal-readiness-csv results/summary/component_energy_goal_readiness_audit_20260714.csv --out-csv results/summary/platform_component_intake_dashboard_20260714.csv --out-md results/summary/platform_component_intake_dashboard_20260714.md

echo 'Done. Review:'
echo '  results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md'
echo '  results/summary/rtx3090_strict_scope_fresh_ncu_component_summary_audit_20260714.md'
echo '  results/summary/rtx3090_platform_result_package_audit_20260714.md'
echo '  results/summary/rtx3090_platform_result_package_gaps_20260714.md'
echo '  results/summary/platform_component_intake_dashboard_20260714.md'
echo '  results/summary/component_energy_goal_readiness_audit_20260714.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_power_state_audit.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_power_api_audit.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_matched_control_report.md'
echo '  results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.md'
FINAL_RC=${PACKAGE_AUDIT_RC}
if [[ "${FINAL_RC}" -eq 0 && "${RELIABILITY_AUDIT_RC}" -ne 0 ]]; then FINAL_RC=${RELIABILITY_AUDIT_RC}; fi
if [[ "${FINAL_RC}" -eq 0 && "${STRICT_BUILD_RC}" -ne 0 ]]; then FINAL_RC=${STRICT_BUILD_RC}; fi
if [[ "${FINAL_RC}" -eq 0 && "${STRICT_AUDIT_RC}" -ne 0 ]]; then FINAL_RC=${STRICT_AUDIT_RC}; fi
if [[ "${FINAL_RC}" -ne 0 ]]; then
  echo 'Strict evidence package is incomplete. Inspect the package audit and gap report above.'
  exit "${FINAL_RC}"
fi
