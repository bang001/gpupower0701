#!/usr/bin/env bash
set -euo pipefail

# Generated for v100 on 2026-07-14.
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
L2_BLOCKS_PER_SM=32
L2_RESIDENCY_POLICY=normal
L2_ADDRESS_LAYOUT=contiguous
export L2_BLOCKS_PER_SM L2_RESIDENCY_POLICY L2_ADDRESS_LAYOUT

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
python3 scripts/select_l2_path_configuration.py --self-test
python3 scripts/analyze_matched_control_energy.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/audit_a100_tensor_l2_remediation.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/write_platform_result_manifest.py --self-test
python3 scripts/audit_documentation_consistency.py --self-test
python3 scripts/selftest_platform_package_gates.py
env -u NCU_USE_SUDO -u NCU_AUTO_SUDO -u NCU_SUDO bash scripts/selftest_ncu_permission_fallback.sh
python3 scripts/audit_documentation_consistency.py --out-csv results/summary/v100_component_finalplan_20260708_documentation_consistency_audit.csv --out-md results/summary/v100_component_finalplan_20260708_documentation_consistency_audit.md --fail-on-error

# 3. Move stale generated outputs aside before writing new CSV schemas.
RUN_STAMP=$(date +%Y%m%d_%H%M%S)
STALE_DIR=results/archive/v100_component_finalplan_20260708_stale_${RUN_STAMP}
STALE_PATHS=(
  results/raw/v100_component_finalplan_20260708_schema_smoke.csv
  results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.csv
  results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.md
  results/raw/v100_component_finalplan_20260708_tensor_pair_calibration.csv
  results/raw/v100_component_finalplan_20260708_l2_pair_calibration.csv
  results/raw/v100_component_finalplan_20260708_dram_pair_calibration.csv
  results/summary/v100_component_finalplan_20260708_l2_path_selection.csv
  results/summary/v100_component_finalplan_20260708_l2_path_selection.md
  results/summary/v100_component_finalplan_20260708_l2_path_selection.env
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
shopt -s nullglob
for path in results/raw/v100_component_finalplan_20260708_l2_precheck_* results/summary/v100_component_finalplan_20260708_l2_precheck_*; do
  mkdir -p "${STALE_DIR}/$(dirname "${path}")"
  mv "${path}" "${STALE_DIR}/${path}"
done
shopt -u nullglob

# 4. Three-row schema/revision smoke test. Catch stale binaries before the full sweep.
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode clocked_empty --w-sm-kib 1 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode reg_operand_only --w-sm-kib 2048 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
./build-v100/a100_fp16_energy_v2 --gpu-list 0 --mode l2_cg_load_only --w-sm-kib 32 --blocks-per-sm 1 --target-profile v100 --active-sm 1 --seconds 0.2 --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 --output results/raw/v100_component_finalplan_20260708_schema_smoke.csv --verify-smid 0
python3 scripts/audit_power_api_measurements.py results/raw/v100_component_finalplan_20260708_schema_smoke.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.csv --out-md results/summary/v100_component_finalplan_20260708_schema_smoke_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-exact-measurement-interval --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg

# 5. NCU-first L2 path selection. The 95% hit gate is never relaxed.
run_l2_path_candidate() {
  local policy="$1"
  local layout="$2"
  local blocks_per_sm="$3"
  local candidate="${policy}_${layout}_B${blocks_per_sm}"
  local outdir=results/ncu/v100_component_finalplan_ncu_factor_20260708/l2_precheck_${candidate}
  local raw_out=results/raw/v100_component_finalplan_20260708_l2_precheck_${candidate}.csv
  local acceptance_csv=results/summary/v100_component_finalplan_20260708_l2_precheck_${candidate}_acceptance.csv
  local acceptance_md=results/summary/v100_component_finalplan_20260708_l2_precheck_${candidate}_acceptance.md

  NCU_COMPONENTS=l2 \
  NCU_EXPLICIT_METRICS_ONLY=1 \
  NCU="${NCU_BIN}" \
  NCU_USE_SUDO="${NCU_USE_SUDO}" \
  NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" \
  NCU_SUDO="${NCU_SUDO}" \
  BIN=./build-v100/a100_fp16_energy_v2 \
  OUTDIR="${outdir}" \
  RAW_OUT="${raw_out}" \
  TARGET_PROFILE=v100 \
  NCU_CHIP=gv100 \
  NCU_FILTER_UNAVAILABLE_METRICS=1 \
  NCU_REPLAY_MODE=application \
  NCU_CACHE_CONTROL=none \
  GLOBAL_WARMUP_PASSES=4 \
  L2_RESIDENCY_POLICY="${policy}" \
  L2_ADDRESS_LAYOUT="${layout}" \
  GPU=0 \
  ACTIVE_SM=80 \
  BLOCKS_PER_SM="${blocks_per_sm}" \
  L2_BLOCKS_PER_SM="${blocks_per_sm}" \
  L2_W_SM_KIB_VALUES=32,64 \
  MEMORY_LOAD_REPEATS=4 \
  INCLUDE_L2_CAPACITY_NCU=0 \
  INCLUDE_DIAGNOSTIC_NCU=0 \
  bash scripts/run_ncu_validation.sh || return 2

  python3 scripts/analyze_ncu_path_acceptance.py \
    "${outdir}/ncu_cache_validation_summary.csv" \
    --target-profile v100 \
    --out-csv "${acceptance_csv}" \
    --out-md "${acceptance_md}" \
    --require-ncu-replay-mode application \
    --require-ncu-cache-control none \
    --require-l2-residency-policy "${policy}" \
    --require-l2-address-layout "${layout}" || return 2

  L2_CANDIDATE_ARGS+=(--candidate "${policy}:${layout}:${blocks_per_sm}:${acceptance_csv}")
  local selector_rc=0
  python3 scripts/select_l2_path_configuration.py \
    --target-profile v100 \
    "${L2_CANDIDATE_ARGS[@]}" \
    --expected-w 32,64 \
    --load-repeat 4 \
    --out-csv results/summary/v100_component_finalplan_20260708_l2_path_selection.csv \
    --out-md results/summary/v100_component_finalplan_20260708_l2_path_selection.md \
    --out-env results/summary/v100_component_finalplan_20260708_l2_path_selection.env || selector_rc=$?
  if [[ "${selector_rc}" == "0" ]]; then
    source results/summary/v100_component_finalplan_20260708_l2_path_selection.env
    export L2_BLOCKS_PER_SM L2_RESIDENCY_POLICY L2_ADDRESS_LAYOUT
    return 0
  fi
  [[ "${selector_rc}" == "2" ]] && return 1
  return 2
}

L2_CANDIDATE_ARGS=()
L2_PATH_SELECTED=0
L2_CANDIDATES=(
  "normal contiguous 32"
  "normal sm_interleaved 32"
  "normal sm_interleaved 16"
  "normal sm_interleaved 4"
)
for candidate in "${L2_CANDIDATES[@]}"; do
  read -r candidate_policy candidate_layout candidate_blocks <<< "${candidate}"
  if run_l2_path_candidate "${candidate_policy}" "${candidate_layout}" "${candidate_blocks}"; then
    L2_PATH_SELECTED=1
    break
  else
    candidate_rc=$?
    if [[ "${candidate_rc}" != "1" ]]; then
      echo "L2 candidate profiling failed before a path verdict" >&2
      exit "${candidate_rc}"
    fi
  fi
done
if [[ "${L2_PATH_SELECTED}" != "1" || -z "${L2_BLOCKS_PER_SM:-}" || -z "${L2_RESIDENCY_POLICY:-}" || -z "${L2_ADDRESS_LAYOUT:-}" ]]; then
  echo "No V100 L2 candidate passed strict NCU gates; energy sweep was not started." >&2
  echo "Inspect results/summary/v100_component_finalplan_20260708_l2_path_selection.md and the l2_precheck_* NCU logs." >&2
  exit 2
fi
echo "Selected L2 path: policy=${L2_RESIDENCY_POLICY} layout=${L2_ADDRESS_LAYOUT} blocks/SM=${L2_BLOCKS_PER_SM}"

# 6. Energy sweeps. Keep NCU detached from these runs.
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes reg_operand_only,reg_mma --w-sm-kib-values 2048 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1,2,4,8,16 --load-repeats 1 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_tensor.csv --matrix-csv results/raw/v100_component_finalplan_20260708_tensor_matrix.csv --tensor-pair-lock-iters --tensor-pair-control-min-seconds 1.0 --pair-calibration-csv results/raw/v100_component_finalplan_20260708_tensor_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes clocked_empty,shared_scalar_load_only --w-sm-kib-values 32,64 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_shared.csv --matrix-csv results/raw/v100_component_finalplan_20260708_shared_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,global_l1_load_only --w-sm-kib-values 8,16,32 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_l1.csv --matrix-csv results/raw/v100_component_finalplan_20260708_l1_matrix.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,l2_cg_load_only --w-sm-kib-values 32,64 --blocks-per-sm-values "${L2_BLOCKS_PER_SM}" --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_l2.csv --matrix-csv results/raw/v100_component_finalplan_20260708_l2_matrix.csv --global-warmup-passes 4 --l2-residency-policy "${L2_RESIDENCY_POLICY}" --l2-address-layout "${L2_ADDRESS_LAYOUT}" --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/v100_component_finalplan_20260708_l2_pair_calibration.csv
python3 scripts/run_component_regression_sweep.py --execute --binary ./build-v100/a100_fp16_energy_v2 --target-profile v100 --gpu-ids 0 --max-active-gpus 1 --modes global_addr_only,dram_cg_load_only --w-sm-kib-values 8192 --blocks-per-sm-values 4,16,32 --active-sm-values 80 --reuse-factors 1 --load-repeats 4,8,16 --store-repeats 1 --seconds 10.0 --repeats 5 --output results/raw/v100_component_finalplan_20260708_dram.csv --matrix-csv results/raw/v100_component_finalplan_20260708_dram_matrix.csv --memory-pair-lock-iters --memory-pair-control-min-seconds 1.0 --memory-pair-calibration-csv results/raw/v100_component_finalplan_20260708_dram_pair_calibration.csv

# 7. Power API audit before spending time on NCU.
python3 scripts/audit_power_api_measurements.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_power_api_audit.csv --out-md results/summary/v100_component_finalplan_20260708_power_api_audit.md --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope --require-exact-measurement-interval --require-mode-notes-marker reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 --require-mode-notes-marker reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 --require-mode-notes-marker l2_cg_load_only=global_warmup_policy=ld_global_cg --require-mode-notes-marker dram_cg_load_only=global_warmup_policy=ld_global_cg

# 7. Power-state row-quality audit. This does not replace the power API gate.
python3 scripts/audit_power_state_stability.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --out-csv results/summary/v100_component_finalplan_20260708_power_state_audit.csv --out-md results/summary/v100_component_finalplan_20260708_power_state_audit.md

# 8. NCU sidecar validation. These profiler runs are not energy rows.
NCU_EXPLICIT_METRICS_ONLY=1 NCU="${NCU_BIN}" NCU_USE_SUDO="${NCU_USE_SUDO}" NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" NCU_SUDO="${NCU_SUDO}" BIN=./build-v100/a100_fp16_energy_v2 OUTDIR=results/ncu/v100_component_finalplan_ncu_factor_20260708 RAW_OUT=results/raw/v100_component_finalplan_ncu_factor_20260708.csv TARGET_PROFILE=v100 NCU_CHIP=gv100 NCU_FILTER_UNAVAILABLE_METRICS=1 GPU=0 ACTIVE_SM=80 BLOCKS_PER_SM=32 L2_BLOCKS_PER_SM="${L2_BLOCKS_PER_SM}" REG_BLOCKS_PER_SM=32 REG_PRESSURE_PAYLOAD_BYTES=256 REG_W_SM_KIB=2048 L1_W_SM_KIB=32 SHARED_W_SM_KIB=32 L2_W_SM_KIB=32 L2_W_SM_KIB_VALUES=32,64 DRAM_W_SM_KIB_OVERRIDE=8192 INCLUDE_L2_CAPACITY_NCU=0 INCLUDE_DIAGNOSTIC_NCU=0 GLOBAL_WARMUP_PASSES=4 L2_RESIDENCY_POLICY="${L2_RESIDENCY_POLICY}" L2_ADDRESS_LAYOUT="${L2_ADDRESS_LAYOUT}" REUSE_FACTOR=1 LOAD_REPEAT=1 TENSOR_REUSE_FACTORS=1,2,4,8,16 MEMORY_LOAD_REPEATS=1,2,4,8,16 DRAM_LOAD_REPEATS=1,4,8,16 bash scripts/run_ncu_validation.sh

# 9. Path acceptance.
python3 scripts/analyze_ncu_path_acceptance.py results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --target-profile v100 --out-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --out-md results/summary/v100_component_finalplan_20260708_ncu_acceptance.md --tensor-memory-bytes-max 2e8 --register-memory-bytes-max 2e8 --tensor-memory-bytes-per-hmma-max 1.0 --register-memory-bytes-per-op-max 1.0 --require-ncu-replay-mode application --require-ncu-cache-control none --require-l2-residency-policy "${L2_RESIDENCY_POLICY}" --require-l2-address-layout "${L2_ADDRESS_LAYOUT}"

# 10. Matched-control analysis with NCU byte-denominator scaling.
python3 scripts/analyze_matched_control_energy.py results/raw/v100_component_finalplan_20260708_tensor.csv results/raw/v100_component_finalplan_20260708_shared.csv results/raw/v100_component_finalplan_20260708_l1.csv results/raw/v100_component_finalplan_20260708_l2.csv results/raw/v100_component_finalplan_20260708_dram.csv --acceptance-csv results/summary/v100_component_finalplan_20260708_ncu_acceptance.csv --ncu-summary-csv results/ncu/v100_component_finalplan_ncu_factor_20260708/ncu_cache_validation_summary.csv --power-state-audit-csv results/summary/v100_component_finalplan_20260708_power_state_audit.csv --exclude-power-state-rejects --require-ncu-denominator --require-total-energy --expected-power-semantics instant --min-elapsed-s 8.0 --tensor-control-min-elapsed-s 0.8 --max-elapsed-ratio 1.35 --max-pair-transition-gap-ms 30000 --pairing nearest-control --tensor-pair-policy matched-iters --l2-pair-policy matched-iters --l2-control-min-elapsed-s 0.8 --dram-pair-policy matched-iters --dram-control-min-elapsed-s 0.8 --require-control-ncu-acceptance --min-delta-j 10.0 --min-delta-fraction 0.005 --out-summary-csv results/summary/v100_component_finalplan_20260708_matched_control_summary.csv --out-detail-csv results/summary/v100_component_finalplan_20260708_matched_control_detail.csv --out-md results/summary/v100_component_finalplan_20260708_matched_control_report.md

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
python3 scripts/build_platform_intake_dashboard.py --tag 20260708 --goal-readiness-csv results/summary/component_energy_goal_readiness_audit_20260708.csv --out-csv results/summary/platform_component_intake_dashboard_20260708.csv --out-md results/summary/platform_component_intake_dashboard_20260708.md

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
