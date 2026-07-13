#!/usr/bin/env bash
set -euo pipefail

# Generated for v100 on 2026-07-13.
# Volta path. Use nvcc with compute_70 support (CUDA 12.x recommended; CUDA 13 removed Volta offline compilation). Nsight Compute 2024.3 is confirmed for GV100; always require --list-chips and --query-metrics support for gv100 because newer releases can remove Volta.
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

# 1. Preflight
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile v100 --strict --min-device-memory-mib 30000 --active-sm 80 --binary ./build-v100/a100_fp16_energy_v2 --ncu "${NCU_COMMAND}" --nvcc "${NVCC_COMMAND}" --out results/summary/v100_component_finalplan_20260708_preflight.md

# 1a. Actual hardware-counter permission probe before expensive energy sweeps.
NCU_PROBE_DIR="${TMPDIR:-/tmp}/gpupower_ncu_probe_v100_${UID}_${PPID}"
NCU_PROBE_RAW="${NCU_PROBE_DIR}/probe_raw.csv"
NCU_PERMISSION_PROBE_ONLY=1 NCU_EXPLICIT_METRICS_ONLY=1 NCU_METRICS=sm__cycles_elapsed.avg NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build-v100/a100_fp16_energy_v2 OUTDIR="${NCU_PROBE_DIR}" RAW_OUT="${NCU_PROBE_RAW}" TARGET_PROFILE=v100 NCU_CHIP=gv100 NCU_FILTER_UNAVAILABLE_METRICS=0 GPU=0 ACTIVE_SM=80 BLOCKS_PER_SM=32 bash scripts/run_ncu_validation.sh
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
python3 scripts/analyze_ncu_path_acceptance.py --self-test
python3 scripts/analyze_matched_control_energy.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/audit_a100_tensor_l2_remediation.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/write_platform_result_manifest.py --self-test
python3 scripts/selftest_platform_package_gates.py
env -u NCU_USE_SUDO -u NCU_AUTO_SUDO -u NCU_SUDO bash scripts/selftest_ncu_permission_fallback.sh

# 3. Move stale generated outputs aside before writing new CSV schemas.
RUN_STAMP=$(date +%Y%m%d_%H%M%S)
STALE_DIR=results/archive/v100_component_finalplan_20260708_stale_${RUN_STAMP}
STALE_PATHS=(
  results/raw/v100_component_finalplan_20260708_schema_smoke.csv
  results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.csv
  results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.md
  results/raw/v100_component_finalplan_20260708_tensor_pair_calibration.csv
  results/raw/v100_component_finalplan_20260708_dram_pair_calibration.csv
  results/raw/v100_component_finalplan_20260708_tensor.csv
  results/raw/v100_component_finalplan_20260708_shared.csv
  results/raw/v100_component_finalplan_20260708_l1.csv
  results/raw/v100_component_finalplan_20260708_l2.csv
  results/raw/v100_component_finalplan_20260708_dram.csv
  results/raw/v100_component_finalplan_20260708_tensor_matrix.csv
  results/raw/v100_component_finalplan_20260708_shared_matrix.csv
  results/raw/v100_component_finalplan_20260708_l1_matrix.csv
  results/raw/v100_component_finalplan_20260708_l2_matrix.csv
  results/raw/v100_component_finalplan_20260708_dram_matrix.csv
  results/raw/v100_component_finalplan_ncu_factor_20260708.csv
  results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv
  results/summary/v100_component_finalplan_20260708_ncu_acceptance.md
  results/summary/v100_component_finalplan_20260708_power_api_audit.csv
  results/summary/v100_component_finalplan_20260708_power_api_audit.md
  results/summary/v100_component_finalplan_20260708_power_state_audit.csv
  results/summary/v100_component_finalplan_20260708_power_state_audit.md
  results/summary/v100_component_finalplan_20260708_matched_control_summary.csv
  results/summary/v100_component_finalplan_20260708_matched_control_detail.csv
  results/summary/v100_component_finalplan_20260708_matched_control_report.md
  results/summary/v100_component_finalplan_20260708_component_reliability_audit.csv
  results/summary/v100_component_finalplan_20260708_component_reliability_audit.md
  results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.csv
  results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.md
  results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.csv
  results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.md
  results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv
  results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.md
  results/summary/v100_component_finalplan_20260708_result_manifest.csv
  results/summary/v100_component_finalplan_20260708_result_manifest.md
  results/summary/v100_platform_result_package_audit_20260708.csv
  results/summary/v100_platform_result_package_audit_20260708.md
  results/summary/v100_platform_result_package_gaps_20260708.csv
  results/summary/v100_platform_result_package_gaps_20260708.md
)
for path in "${STALE_PATHS[@]}"; do
  if [[ -e "${path}" ]]; then
    mkdir -p "${STALE_DIR}/$(dirname "${path}")"
    mv "${path}" "${STALE_DIR}/${path}"
  fi
done
if [[ -e results/ncu/v100_component_finalplan_ncu_factor_20260708 ]]; then
  mkdir -p "${STALE_DIR}/$(dirname results/ncu/v100_component_finalplan_ncu_factor_20260708)"
  mv results/ncu/v100_component_finalplan_ncu_factor_20260708 "${STALE_DIR}/results/ncu/v100_component_finalplan_ncu_factor_20260708"
fi

# 4. Three-row schema/revision smoke test. Catch stale binaries before the full sweep.
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode clocked_empty --w-sm-kib 1 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode reg_operand_only --w-sm-kib 2048 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode l2_cg_load_only --w-sm-kib 32 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
python3 scripts/audit_power_api_measurements.py results/raw/v100_component_finalplan_20260708_schema_smoke.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.csv --out-md results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg

# 5. Energy sweeps. Keep NCU detached from these runs.
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes reg_operand_only,reg_mma --w-sm-kib-values 2048 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1,2,4,8,16 --load-repeats 1 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_tensor.csv --matrix-csv results/raw/v100_component_finalplan_20260708_tensor_matrix.csv --tensor-pair-lock-iters --tensor-pair-control-min-seconds 1.0 --pair-calibration-csv results/raw/v100_component_finalplan_20260708_tensor_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,shared_scalar_load_only --w-sm-kib-values 32,64 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_shared.csv --matrix-csv results/raw/v100_component_finalplan_20260708_shared_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,global_l1_load_only --w-sm-kib-values 8,16,32 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_l1.csv --matrix-csv results/raw/v100_component_finalplan_20260708_l1_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,l2_cg_load_only --w-sm-kib-values 32,64 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_l2.csv --matrix-csv results/raw/v100_component_finalplan_20260708_l2_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,dram_cg_load_only --w-sm-kib-values 8192 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_dram.csv --matrix-csv results/raw/v100_component_finalplan_20260708_dram_matrix.csv --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/v100_component_finalplan_20260708_dram_pair_calibration.csv

# 6. Power API audit before spending time on NCU.
python3 scripts/audit_power_api_measurements.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_power_api_audit.csv --out-md results/summary/v100_component_finalplan_20260708_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_v1 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg

# 7. Power-state row-quality audit. This does not replace the power API gate.
python3 scripts/audit_power_state_stability.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --out-csv results/summary/v100_component_finalplan_20260708_power_state_audit.csv --out-md results/summary/v100_component_finalplan_20260708_power_state_audit.md

# 8. NCU sidecar validation. These profiler runs are not energy rows.
NCU_EXPLICIT_METRICS_ONLY=1 NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build-v100/a100_fp16_energy_v2 OUTDIR=results/ncu/v100_component_finalplan_ncu_factor_20260708 RAW_OUT=results/raw/v100_component_finalplan_ncu_factor_20260708.csv TARGET_PROFILE=v100 NCU_CHIP=gv100 NCU_FILTER_UNAVAILABLE_METRICS=1 GPU=0 ACTIVE_SM=80 BLOCKS_PER_SM=32 REG_BLOCKS_PER_SM=32 REG_PRESSURE_PAYLOAD_BYTES=256 REG_W_SM_KIB=2048 L1_W_SM_KIB=32 SHARED_W_SM_KIB=32 L2_W_SM_KIB=32 L2_W_SM_KIB_VALUES=32 DRAM_W_SM_KIB_OVERRIDE=8192 INCLUDE_L2_CAPACITY_NCU=0 INCLUDE_DIAGNOSTIC_NCU=0 REUSE_FACTOR=1 LOAD_REPEAT=1 TENSOR_REUSE_FACTORS=1,2,4,8,16 MEMORY_LOAD_REPEATS=1,2,4,8,16 DRAM_LOAD_REPEATS=1,4,8,16 bash scripts/run_ncu_validation.sh

# 9. Path acceptance.
python3 scripts/analyze_ncu_path_acceptance.py results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --out-md results/summary/v100_component_finalplan_20260708_ncu_acceptance.md --tensor-memory-bytes-max 2e8 --register-memory-bytes-max 2e8 --tensor-memory-bytes-per-hmma-max 1.0 --register-memory-bytes-per-op-max 1.0

# 10. Matched-control analysis with NCU byte-denominator scaling.
python3 scripts/analyze_matched_control_energy.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --acceptance-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --ncu-summary-csv results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --power-state-audit-csv results/summary/v100_component_finalplan_20260708_power_state_audit.csv --exclude-power-state-rejects --require-ncu-denominator --require-total-energy --expected-power-semantics instant --min-elapsed-s 8.0 --tensor-control-min-elapsed-s 0.8 --max-elapsed-ratio 1.35 --pairing nearest-control --tensor-pair-policy matched-iters --dram-pair-policy matched-iters --dram-control-min-elapsed-s 0.8 --require-control-ncu-acceptance --min-delta-j 10.0 --min-delta-fraction 0.005 --out-summary-csv results/summary/v100_component_finalplan_20260708_matched_control_summary.csv --out-detail-csv results/summary/v100_component_finalplan_20260708_matched_control_detail.csv --out-md results/summary/v100_component_finalplan_20260708_matched_control_report.md

# 11. Component reliability audit.
set +e
python3 scripts/audit_component_reliability.py --power-audit-csv results/summary/v100_component_finalplan_20260708_power_api_audit.csv --ncu-acceptance-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --matched-summary-csv results/summary/v100_component_finalplan_20260708_matched_control_summary.csv --matched-detail-csv results/summary/v100_component_finalplan_20260708_matched_control_detail.csv --expected-power-semantics instant --out-csv results/summary/v100_component_finalplan_20260708_component_reliability_audit.csv --out-md results/summary/v100_component_finalplan_20260708_component_reliability_audit.md --fail-on-reject
RELIABILITY_AUDIT_RC=$?
set -e

# 12. Matched-control instability/root-cause audit.
python3 scripts/audit_matched_control_instability.py results/summary/v100_component_finalplan_20260708_matched_control_detail.csv --out-csv results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.csv --out-md results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.md

# 13. Build strict component summary package from accepted evidence.
set +e
python3 scripts/build_strict_component_summary.py --target-profile v100 --gpu-label V100 --matched-summary-csv results/summary/v100_component_finalplan_20260708_matched_control_summary.csv --matched-detail-csv results/summary/v100_component_finalplan_20260708_matched_control_detail.csv --power-api-audit-csv results/summary/v100_component_finalplan_20260708_power_api_audit.csv --power-state-audit-csv results/summary/v100_component_finalplan_20260708_power_state_audit.csv --reliability-csv results/summary/v100_component_finalplan_20260708_component_reliability_audit.csv --ncu-acceptance-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --ncu-summary-csv results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --instability-artifact results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.csv --out-csv results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.csv --out-md results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.md
STRICT_BUILD_RC=$?
set -e

# 14. Audit strict component summary against reliability/detail artifacts.
set +e
python3 scripts/audit_strict_component_summary.py --summary-csv results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.csv --expected-power-semantics instant --out-csv results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv --out-md results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.md --require-path-specific-cache-evidence --fail-on-fail
STRICT_AUDIT_RC=$?
set -e

# 15. Write the expected result manifest for copy-back and gap triage.
python3 scripts/write_platform_result_manifest.py --target-profile v100 --tag 20260708 --expected-active-sm 80 --out-csv results/summary/v100_component_finalplan_20260708_result_manifest.csv --out-md results/summary/v100_component_finalplan_20260708_result_manifest.md

# 16. Audit the full platform result package before publishing or copying back.
set +e
python3 scripts/audit_platform_result_package.py --target-profile v100 --tag 20260708 --expected-active-sm 80 --out-csv results/summary/v100_platform_result_package_audit_20260708.csv --out-md results/summary/v100_platform_result_package_audit_20260708.md --fail-on-incomplete
PACKAGE_AUDIT_RC=$?
set -e

# 17. Always write triage/goal-readiness/dashboard artifacts.
python3 scripts/summarize_platform_package_gaps.py --target-profile v100 --tag 20260708 --audit-csv results/summary/v100_platform_result_package_audit_20260708.csv --manifest-csv results/summary/v100_component_finalplan_20260708_result_manifest.csv --out-csv results/summary/v100_platform_result_package_gaps_20260708.csv --out-md results/summary/v100_platform_result_package_gaps_20260708.md
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/audit_component_goal_readiness.py --ncu "${NCU_COMMAND}" --out-csv results/summary/component_energy_goal_readiness_audit_20260708.csv --out-md results/summary/component_energy_goal_readiness_audit_20260708.md
python3 scripts/build_platform_intake_dashboard.py --tag 20260708 --out-csv results/summary/platform_component_intake_dashboard_20260708.csv --out-md results/summary/platform_component_intake_dashboard_20260708.md

echo 'Done. Review:'
echo '  results/summary/v100_strict_scope_fresh_ncu_component_coefficients_20260708.md'
echo '  results/summary/v100_strict_scope_fresh_ncu_component_summary_audit_20260708.md'
echo '  results/summary/v100_platform_result_package_audit_20260708.md'
echo '  results/summary/v100_platform_result_package_gaps_20260708.md'
echo '  results/summary/platform_component_intake_dashboard_20260708.md'
echo '  results/summary/component_energy_goal_readiness_audit_20260708.md'
echo '  results/summary/v100_component_finalplan_20260708_component_reliability_audit.md'
echo '  results/summary/v100_component_finalplan_20260708_matched_control_instability_audit.md'
echo '  results/summary/v100_component_finalplan_20260708_power_state_audit.md'
echo '  results/summary/v100_component_finalplan_20260708_power_api_audit.md'
echo '  results/summary/v100_component_finalplan_20260708_matched_control_report.md'
echo '  results/summary/v100_component_finalplan_20260708_ncu_acceptance.md'
FINAL_RC=${PACKAGE_AUDIT_RC}
if [[ "${FINAL_RC}" -eq 0 && "${RELIABILITY_AUDIT_RC}" -ne 0 ]]; then FINAL_RC=${RELIABILITY_AUDIT_RC}; fi
if [[ "${FINAL_RC}" -eq 0 && "${STRICT_BUILD_RC}" -ne 0 ]]; then FINAL_RC=${STRICT_BUILD_RC}; fi
if [[ "${FINAL_RC}" -eq 0 && "${STRICT_AUDIT_RC}" -ne 0 ]]; then FINAL_RC=${STRICT_AUDIT_RC}; fi
if [[ "${FINAL_RC}" -ne 0 ]]; then
  echo 'Strict evidence package is incomplete. Inspect the package audit and gap report above.'
  exit "${FINAL_RC}"
fi
