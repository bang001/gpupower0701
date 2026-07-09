#!/usr/bin/env bash
set -euo pipefail

# Generated for a100 on 2026-07-09.
# A100 can test capacity L2 and CG L2 side by side.
mkdir -p results/raw results/summary results/ncu

# 1. Preflight
python3 scripts/preflight_gpu_support.py --gpu 0 --target-profile a100 --strict --active-sm 108 --binary ./build-a100/a100_fp16_energy_v2 --ncu ncu --out results/summary/a100_component_finalplan_20260708_preflight.md

# 2. Power API policy self-test. Fail early if the gate is broken.
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test

# 3. Move stale generated outputs aside before writing new CSV schemas.
RUN_STAMP=$(date +%Y%m%d_%H%M%S)
STALE_DIR=results/archive/a100_component_finalplan_20260708_stale_${RUN_STAMP}
STALE_PATHS=(
  results/raw/a100_component_finalplan_20260708_schema_smoke.csv
  results/summary/a100_component_finalplan_20260708_schema_smoke_power_api_audit.csv
  results/summary/a100_component_finalplan_20260708_schema_smoke_power_api_audit.md
  results/raw/a100_component_finalplan_20260708_tensor.csv
  results/raw/a100_component_finalplan_20260708_shared.csv
  results/raw/a100_component_finalplan_20260708_l1.csv
  results/raw/a100_component_finalplan_20260708_l2.csv
  results/raw/a100_component_finalplan_20260708_dram.csv
  results/raw/a100_component_finalplan_20260708_tensor_matrix.csv
  results/raw/a100_component_finalplan_20260708_shared_matrix.csv
  results/raw/a100_component_finalplan_20260708_l1_matrix.csv
  results/raw/a100_component_finalplan_20260708_l2_matrix.csv
  results/raw/a100_component_finalplan_20260708_dram_matrix.csv
  results/raw/a100_component_finalplan_ncu_factor_20260708.csv
  results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv
  results/summary/a100_component_finalplan_20260708_ncu_acceptance.md
  results/summary/a100_component_finalplan_20260708_power_api_audit.csv
  results/summary/a100_component_finalplan_20260708_power_api_audit.md
  results/summary/a100_component_finalplan_20260708_power_state_audit.csv
  results/summary/a100_component_finalplan_20260708_power_state_audit.md
  results/summary/a100_component_finalplan_20260708_matched_control_summary.csv
  results/summary/a100_component_finalplan_20260708_matched_control_detail.csv
  results/summary/a100_component_finalplan_20260708_matched_control_report.md
  results/summary/a100_component_finalplan_20260708_component_reliability_audit.csv
  results/summary/a100_component_finalplan_20260708_component_reliability_audit.md
  results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.csv
  results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.md
  results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.csv
  results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.md
  results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv
  results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.md
  results/summary/a100_component_finalplan_20260708_result_manifest.csv
  results/summary/a100_component_finalplan_20260708_result_manifest.md
  results/summary/a100_platform_result_package_audit_20260708.csv
  results/summary/a100_platform_result_package_audit_20260708.md
  results/summary/a100_platform_result_package_gaps_20260708.csv
  results/summary/a100_platform_result_package_gaps_20260708.md
)
for path in "${STALE_PATHS[@]}"; do
  if [[ -e "${path}" ]]; then
    mkdir -p "${STALE_DIR}/$(dirname "${path}")"
    mv "${path}" "${STALE_DIR}/${path}"
  fi
done
if [[ -e results/ncu/a100_component_finalplan_ncu_factor_20260708 ]]; then
  mkdir -p "${STALE_DIR}/$(dirname results/ncu/a100_component_finalplan_ncu_factor_20260708)"
  mv results/ncu/a100_component_finalplan_ncu_factor_20260708 "${STALE_DIR}/results/ncu/a100_component_finalplan_ncu_factor_20260708"
fi

# 4. One-row schema smoke test. This catches old binaries before the full sweep.
./build-a100/a100_fp16_energy_v2 --gpu-list 0 --mode clocked_empty --w-sm-kib 1 --blocks-per-sm 1 --target-profile a100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/a100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
python3 scripts/audit_power_api_measurements.py results/raw/a100_component_finalplan_20260708_schema_smoke.csv --target-profile a100 --out-csv results/summary/a100_component_finalplan_20260708_schema_smoke_power_api_audit.csv --out-md results/summary/a100_component_finalplan_20260708_schema_smoke_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope

# 5. Energy sweeps. Keep NCU detached from these runs.
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-a100/a100_fp16_energy_v2 --target-profile a100 --gpu-ids 0 --max-active-gpus 1 --modes reg_operand_only,reg_mma --w-sm-kib-values 2048 --blocks-per-sm-values 16,32 --active-sm-values 108 --reuse-factors 1,2,4,8,16 --load-repeats 1 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/a100_component_finalplan_20260708_tensor.csv --matrix-csv results/raw/a100_component_finalplan_20260708_tensor_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-a100/a100_fp16_energy_v2 --target-profile a100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,shared_scalar_load_only --w-sm-kib-values 64,128 --blocks-per-sm-values 16,32 --active-sm-values 108 --reuse-factors 1 --load-repeats 1,2,4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/a100_component_finalplan_20260708_shared.csv --matrix-csv results/raw/a100_component_finalplan_20260708_shared_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-a100/a100_fp16_energy_v2 --target-profile a100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,global_l1_load_only --w-sm-kib-values 16,32 --blocks-per-sm-values 16,32 --active-sm-values 108 --reuse-factors 1 --load-repeats 1,2,4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/a100_component_finalplan_20260708_l1.csv --matrix-csv results/raw/a100_component_finalplan_20260708_l1_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-a100/a100_fp16_energy_v2 --target-profile a100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,l2_load_only,l2_cg_load_only --w-sm-kib-values 256 --blocks-per-sm-values 16,32 --active-sm-values 108 --reuse-factors 1 --load-repeats 1,2,4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/a100_component_finalplan_20260708_l2.csv --matrix-csv results/raw/a100_component_finalplan_20260708_l2_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-a100/a100_fp16_energy_v2 --target-profile a100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,dram_cg_load_only --w-sm-kib-values 8192 --blocks-per-sm-values 16,32 --active-sm-values 108 --reuse-factors 1 --load-repeats 1,4,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/a100_component_finalplan_20260708_dram.csv --matrix-csv results/raw/a100_component_finalplan_20260708_dram_matrix.csv

# 6. Power API audit before spending time on NCU.
python3 scripts/audit_power_api_measurements.py results/raw/a100_component_finalplan_20260708_tensor.csv results/raw/a100_component_finalplan_20260708_shared.csv results/raw/a100_component_finalplan_20260708_l1.csv results/raw/a100_component_finalplan_20260708_l2.csv results/raw/a100_component_finalplan_20260708_dram.csv --target-profile a100 --out-csv results/summary/a100_component_finalplan_20260708_power_api_audit.csv --out-md results/summary/a100_component_finalplan_20260708_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope

# 7. Power-state row-quality audit. This does not replace the power API gate.
python3 scripts/audit_power_state_stability.py results/raw/a100_component_finalplan_20260708_tensor.csv results/raw/a100_component_finalplan_20260708_shared.csv results/raw/a100_component_finalplan_20260708_l1.csv results/raw/a100_component_finalplan_20260708_l2.csv results/raw/a100_component_finalplan_20260708_dram.csv --out-csv results/summary/a100_component_finalplan_20260708_power_state_audit.csv --out-md results/summary/a100_component_finalplan_20260708_power_state_audit.md

# 8. NCU sidecar validation. These profiler runs are not energy rows.
NCU_EXPLICIT_METRICS_ONLY=1 NCU=ncu BIN=./build-a100/a100_fp16_energy_v2 OUTDIR=results/ncu/a100_component_finalplan_ncu_factor_20260708 RAW_OUT=results/raw/a100_component_finalplan_ncu_factor_20260708.csv TARGET_PROFILE=a100 GPU=0 ACTIVE_SM=108 BLOCKS_PER_SM=16 REG_BLOCKS_PER_SM=16 REG_PRESSURE_PAYLOAD_BYTES=256 REG_W_SM_KIB=2048 L1_W_SM_KIB=16 SHARED_W_SM_KIB=128 L2_W_SM_KIB=256 DRAM_W_SM_KIB_OVERRIDE=8192 INCLUDE_L2_CAPACITY_NCU=1 INCLUDE_DIAGNOSTIC_NCU=0 REUSE_FACTOR=1 LOAD_REPEAT=1 TENSOR_REUSE_FACTORS=1,2,4,8,16 MEMORY_LOAD_REPEATS=1,2,4,8,16 DRAM_LOAD_REPEATS=1,4,16 bash scripts/run_ncu_validation.sh

# 9. Path acceptance.
python3 scripts/analyze_ncu_path_acceptance.py results/ncu/a100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --out-csv results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv --out-md results/summary/a100_component_finalplan_20260708_ncu_acceptance.md --tensor-memory-bytes-max 3e8 --register-memory-bytes-max 3e8 --tensor-memory-bytes-per-hmma-max 1.0 --register-memory-bytes-per-op-max 1.0

# 10. Matched-control analysis with NCU byte-denominator scaling.
python3 scripts/analyze_matched_control_energy.py results/raw/a100_component_finalplan_20260708_tensor.csv results/raw/a100_component_finalplan_20260708_shared.csv results/raw/a100_component_finalplan_20260708_l1.csv results/raw/a100_component_finalplan_20260708_l2.csv results/raw/a100_component_finalplan_20260708_dram.csv --acceptance-csv results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv --ncu-summary-csv results/ncu/a100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --power-state-audit-csv results/summary/a100_component_finalplan_20260708_power_state_audit.csv --exclude-power-state-rejects --require-ncu-denominator --require-total-energy --expected-power-semantics instant --min-elapsed-s 8.0 --max-elapsed-ratio 1.35 --pairing nearest-control --min-delta-j 10.0 --min-delta-fraction 0.005 --out-summary-csv results/summary/a100_component_finalplan_20260708_matched_control_summary.csv --out-detail-csv results/summary/a100_component_finalplan_20260708_matched_control_detail.csv --out-md results/summary/a100_component_finalplan_20260708_matched_control_report.md

# 11. Component reliability audit.
python3 scripts/audit_component_reliability.py --power-audit-csv results/summary/a100_component_finalplan_20260708_power_api_audit.csv --ncu-acceptance-csv results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv --matched-summary-csv results/summary/a100_component_finalplan_20260708_matched_control_summary.csv --matched-detail-csv results/summary/a100_component_finalplan_20260708_matched_control_detail.csv --expected-power-semantics instant --out-csv results/summary/a100_component_finalplan_20260708_component_reliability_audit.csv --out-md results/summary/a100_component_finalplan_20260708_component_reliability_audit.md --fail-on-reject

# 12. Matched-control instability/root-cause audit.
python3 scripts/audit_matched_control_instability.py results/summary/a100_component_finalplan_20260708_matched_control_detail.csv --out-csv results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.csv --out-md results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.md

# 13. Build strict component summary package from accepted evidence.
python3 scripts/build_strict_component_summary.py --target-profile a100 --gpu-label A100 --matched-summary-csv results/summary/a100_component_finalplan_20260708_matched_control_summary.csv --matched-detail-csv results/summary/a100_component_finalplan_20260708_matched_control_detail.csv --power-api-audit-csv results/summary/a100_component_finalplan_20260708_power_api_audit.csv --power-state-audit-csv results/summary/a100_component_finalplan_20260708_power_state_audit.csv --reliability-csv results/summary/a100_component_finalplan_20260708_component_reliability_audit.csv --ncu-acceptance-csv results/summary/a100_component_finalplan_20260708_ncu_acceptance.csv --ncu-summary-csv results/ncu/a100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --instability-artifact results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.csv --out-csv results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.csv --out-md results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.md

# 14. Audit strict component summary against reliability/detail artifacts.
python3 scripts/audit_strict_component_summary.py --summary-csv results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.csv --expected-power-semantics instant --out-csv results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.csv --out-md results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.md --fail-on-fail

# 15. Write the expected result manifest for copy-back and gap triage.
python3 scripts/write_platform_result_manifest.py --target-profile a100 --tag 20260708 --expected-active-sm 108 --out-csv results/summary/a100_component_finalplan_20260708_result_manifest.csv --out-md results/summary/a100_component_finalplan_20260708_result_manifest.md

# 16. Audit the full platform result package before publishing or copying back.
set +e
python3 scripts/audit_platform_result_package.py --target-profile a100 --tag 20260708 --expected-active-sm 108 --out-csv results/summary/a100_platform_result_package_audit_20260708.csv --out-md results/summary/a100_platform_result_package_audit_20260708.md --fail-on-incomplete
PACKAGE_AUDIT_RC=$?
set -e

# 17. Always write triage/goal-readiness/dashboard artifacts.
python3 scripts/summarize_platform_package_gaps.py --target-profile a100 --tag 20260708 --audit-csv results/summary/a100_platform_result_package_audit_20260708.csv --manifest-csv results/summary/a100_component_finalplan_20260708_result_manifest.csv --out-csv results/summary/a100_platform_result_package_gaps_20260708.csv --out-md results/summary/a100_platform_result_package_gaps_20260708.md
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/audit_component_goal_readiness.py --ncu ncu --out-csv results/summary/component_energy_goal_readiness_audit_20260708.csv --out-md results/summary/component_energy_goal_readiness_audit_20260708.md
python3 scripts/build_platform_intake_dashboard.py --tag 20260708 --out-csv results/summary/platform_component_intake_dashboard_20260708.csv --out-md results/summary/platform_component_intake_dashboard_20260708.md

echo 'Done. Review:'
echo '  results/summary/a100_strict_scope_fresh_ncu_component_coefficients_20260708.md'
echo '  results/summary/a100_strict_scope_fresh_ncu_component_summary_audit_20260708.md'
echo '  results/summary/a100_platform_result_package_audit_20260708.md'
echo '  results/summary/a100_platform_result_package_gaps_20260708.md'
echo '  results/summary/platform_component_intake_dashboard_20260708.md'
echo '  results/summary/component_energy_goal_readiness_audit_20260708.md'
echo '  results/summary/a100_component_finalplan_20260708_component_reliability_audit.md'
echo '  results/summary/a100_component_finalplan_20260708_matched_control_instability_audit.md'
echo '  results/summary/a100_component_finalplan_20260708_power_state_audit.md'
echo '  results/summary/a100_component_finalplan_20260708_power_api_audit.md'
echo '  results/summary/a100_component_finalplan_20260708_matched_control_report.md'
echo '  results/summary/a100_component_finalplan_20260708_ncu_acceptance.md'
if [[ "${PACKAGE_AUDIT_RC}" -ne 0 ]]; then
  echo 'Package audit failed. Inspect the package audit and gap report above.'
  exit "${PACKAGE_AUDIT_RC}"
fi
