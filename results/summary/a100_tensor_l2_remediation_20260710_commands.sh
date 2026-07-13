#!/usr/bin/env bash
set -euo pipefail

# Targeted A100 rerun for the RF>=4 Tensor failure and the rejected L2 .cg path.
TAG="${TAG:-20260710}"
GPU="${GPU:-0}"
ACTIVE_SM="${ACTIVE_SM:-108}"
BINARY="${BINARY:-./build-a100/a100_fp16_energy_v2}"
NVCC_COMMAND="${NVCC:-nvcc}"
NCU_BIN="${NCU_BIN:-ncu}"
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_SUDO="${NCU_SUDO:-sudo -E}"
REBUILD="${REBUILD:-1}"

if [[ "${NCU_USE_SUDO}" == "1" ]]; then
  NCU_COMMAND="${NCU_SUDO} ${NCU_BIN}"
else
  NCU_COMMAND="${NCU_BIN}"
fi

PREFIX="a100_tensor_l2_remediation_${TAG}"
RAW_PREFIX="results/raw/${PREFIX}"
SUMMARY_PREFIX="results/summary/${PREFIX}"
NCU_DIR="results/ncu/${PREFIX}"
TENSOR_RAW="${RAW_PREFIX}_tensor.csv"
TENSOR_MATRIX="${RAW_PREFIX}_tensor_matrix.csv"
PAIR_CALIBRATION="${RAW_PREFIX}_tensor_pair_calibration.csv"
L2_RAW="${RAW_PREFIX}_l2.csv"
L2_MATRIX="${RAW_PREFIX}_l2_matrix.csv"
SCHEMA_SMOKE="${RAW_PREFIX}_schema_smoke.csv"
NCU_RAW="${RAW_PREFIX}_ncu_sidecar.csv"
L2_NORMAL_NCU_RAW="${RAW_PREFIX}_l2_policy_normal_ncu_sidecar.csv"
L2_PERSISTING_NCU_RAW="${RAW_PREFIX}_l2_policy_persisting_ncu_sidecar.csv"
POWER_AUDIT_CSV="${SUMMARY_PREFIX}_power_api_audit.csv"
POWER_AUDIT_MD="${SUMMARY_PREFIX}_power_api_audit.md"
POWER_STATE_CSV="${SUMMARY_PREFIX}_power_state_audit.csv"
POWER_STATE_MD="${SUMMARY_PREFIX}_power_state_audit.md"
NCU_ACCEPTANCE_CSV="${SUMMARY_PREFIX}_ncu_acceptance.csv"
NCU_ACCEPTANCE_MD="${SUMMARY_PREFIX}_ncu_acceptance.md"
NCU_PRECHECK_CSV="${SUMMARY_PREFIX}_ncu_precheck.csv"
NCU_PRECHECK_MD="${SUMMARY_PREFIX}_ncu_precheck.md"
L2_NORMAL_ACCEPTANCE_CSV="${SUMMARY_PREFIX}_l2_policy_normal_acceptance.csv"
L2_NORMAL_ACCEPTANCE_MD="${SUMMARY_PREFIX}_l2_policy_normal_acceptance.md"
L2_PERSISTING_ACCEPTANCE_CSV="${SUMMARY_PREFIX}_l2_policy_persisting_acceptance.csv"
L2_PERSISTING_ACCEPTANCE_MD="${SUMMARY_PREFIX}_l2_policy_persisting_acceptance.md"
L2_POLICY_CSV="${SUMMARY_PREFIX}_l2_policy_selection.csv"
L2_POLICY_MD="${SUMMARY_PREFIX}_l2_policy_selection.md"
L2_POLICY_ENV="${SUMMARY_PREFIX}_l2_policy_selection.env"
MATCHED_SUMMARY="${SUMMARY_PREFIX}_matched_control_summary.csv"
MATCHED_DETAIL="${SUMMARY_PREFIX}_matched_control_detail.csv"
MATCHED_MD="${SUMMARY_PREFIX}_matched_control_report.md"
INSTABILITY_CSV="${SUMMARY_PREFIX}_instability_audit.csv"
INSTABILITY_MD="${SUMMARY_PREFIX}_instability_audit.md"
REMEDIATION_CSV="${SUMMARY_PREFIX}_audit.csv"
REMEDIATION_MD="${SUMMARY_PREFIX}_audit.md"

mkdir -p results/raw results/summary results/ncu results/archive

if [[ "${REBUILD}" == "1" ]]; then
  cmake -S . -B build-a100 \
    -DCMAKE_CUDA_ARCHITECTURES=80 \
    -DCMAKE_CUDA_COMPILER="${NVCC_COMMAND}"
  cmake --build build-a100 --clean-first -j
fi

python3 scripts/preflight_gpu_support.py \
  --gpu "${GPU}" \
  --target-profile a100 \
  --strict \
  --active-sm "${ACTIVE_SM}" \
  --binary "${BINARY}" \
  --ncu "${NCU_COMMAND}" \
  --nvcc "${NVCC_COMMAND}" \
  --out "${SUMMARY_PREFIX}_preflight.md"

python3 scripts/run_component_regression_sweep.py --self-test
python3 scripts/summarize_ncu_cache_metrics.py --self-test
python3 scripts/analyze_ncu_path_acceptance.py --self-test
python3 scripts/analyze_matched_control_energy.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/audit_a100_tensor_l2_remediation.py --self-test
python3 scripts/audit_a100_ncu_precheck.py --self-test
python3 scripts/select_a100_l2_residency_policy.py --self-test

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
STALE_DIR="results/archive/${PREFIX}_stale_${RUN_STAMP}"
STALE_PATHS=(
  "${SCHEMA_SMOKE}"
  "${SUMMARY_PREFIX}_schema_smoke_power_api_audit.csv"
  "${SUMMARY_PREFIX}_schema_smoke_power_api_audit.md"
  "${TENSOR_RAW}"
  "${TENSOR_MATRIX}"
  "${PAIR_CALIBRATION}"
  "${L2_RAW}"
  "${L2_MATRIX}"
  "${NCU_RAW}"
  "${L2_NORMAL_NCU_RAW}"
  "${L2_PERSISTING_NCU_RAW}"
  "${POWER_AUDIT_CSV}"
  "${POWER_AUDIT_MD}"
  "${POWER_STATE_CSV}"
  "${POWER_STATE_MD}"
  "${NCU_ACCEPTANCE_CSV}"
  "${NCU_ACCEPTANCE_MD}"
  "${NCU_PRECHECK_CSV}"
  "${NCU_PRECHECK_MD}"
  "${L2_NORMAL_ACCEPTANCE_CSV}"
  "${L2_NORMAL_ACCEPTANCE_MD}"
  "${L2_PERSISTING_ACCEPTANCE_CSV}"
  "${L2_PERSISTING_ACCEPTANCE_MD}"
  "${L2_POLICY_CSV}"
  "${L2_POLICY_MD}"
  "${L2_POLICY_ENV}"
  "${MATCHED_SUMMARY}"
  "${MATCHED_DETAIL}"
  "${MATCHED_MD}"
  "${INSTABILITY_CSV}"
  "${INSTABILITY_MD}"
  "${REMEDIATION_CSV}"
  "${REMEDIATION_MD}"
)
for path in "${STALE_PATHS[@]}"; do
  if [[ -e "${path}" ]]; then
    mkdir -p "${STALE_DIR}/$(dirname "${path}")"
    mv "${path}" "${STALE_DIR}/${path}"
  fi
done
if [[ -e "${NCU_DIR}" ]]; then
  mkdir -p "${STALE_DIR}/$(dirname "${NCU_DIR}")"
  mv "${NCU_DIR}" "${STALE_DIR}/${NCU_DIR}"
fi

# Three rows prove the current CSV schema and both implementation revisions.
"${BINARY}" --gpu-list "${GPU}" --mode clocked_empty --w-sm-kib 1 \
  --blocks-per-sm 1 --target-profile a100 --active-sm 1 --seconds 0.2 \
  --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 \
  --output "${SCHEMA_SMOKE}" --verify-smid 0
"${BINARY}" --gpu-list "${GPU}" --mode reg_operand_only --w-sm-kib 2048 \
  --blocks-per-sm 1 --target-profile a100 --active-sm 1 --seconds 0.2 \
  --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 \
  --output "${SCHEMA_SMOKE}" --verify-smid 0
"${BINARY}" --gpu-list "${GPU}" --mode l2_cg_load_only --w-sm-kib 16 \
  --blocks-per-sm 1 --target-profile a100 --active-sm 1 --seconds 0.2 \
  --iters 1 --repeats 1 --reuse-factor 1 --load-repeat 1 --store-repeat 1 \
  --global-warmup-passes 4 --l2-residency-policy normal \
  --output "${SCHEMA_SMOKE}" --verify-smid 0

python3 scripts/audit_power_api_measurements.py "${SCHEMA_SMOKE}" \
  --target-profile a100 \
  --out-csv "${SUMMARY_PREFIX}_schema_smoke_power_api_audit.csv" \
  --out-md "${SUMMARY_PREFIX}_schema_smoke_power_api_audit.md" \
  --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope \
  --require-mode-notes-marker \
  reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 \
  --require-mode-notes-marker \
  l2_cg_load_only=global_warmup_policy=ld_global_cg

# Fail fast on the original L2 problem before running the long energy sweep.
# The same W/LR points are first profiled with ordinary .cg caching. An explicit
# CUDA persisting-L2 access-policy window is tried only if normal caching fails.
run_l2_policy_diagnostic() {
  local policy="$1"
  local outdir="$2"
  local raw_out="$3"
  local acceptance_csv="$4"
  local acceptance_md="$5"

  NCU_COMPONENTS=l2 \
  NCU_EXPLICIT_METRICS_ONLY=1 \
  NCU="${NCU_COMMAND}" \
  BIN="${BINARY}" \
  OUTDIR="${outdir}" \
  RAW_OUT="${raw_out}" \
  TARGET_PROFILE=a100 \
  NCU_CHIP=ga100 \
  NCU_FILTER_UNAVAILABLE_METRICS=1 \
  NCU_REPLAY_MODE=application \
  NCU_CACHE_CONTROL=none \
  GLOBAL_WARMUP_PASSES=4 \
  L2_RESIDENCY_POLICY="${policy}" \
  GPU="${GPU}" \
  ACTIVE_SM="${ACTIVE_SM}" \
  BLOCKS_PER_SM=16 \
  L2_W_SM_KIB_VALUES=16,128 \
  MEMORY_LOAD_REPEATS=4 \
  INCLUDE_L2_CAPACITY_NCU=0 \
  INCLUDE_DIAGNOSTIC_NCU=0 \
  bash scripts/run_ncu_validation.sh

  python3 scripts/analyze_ncu_path_acceptance.py \
    "${outdir}/ncu_cache_validation_summary.csv" \
    --target-profile a100 \
    --out-csv "${acceptance_csv}" \
    --out-md "${acceptance_md}" \
    --require-ncu-replay-mode application \
    --require-ncu-cache-control none \
    --require-l2-residency-policy "${policy}"
}

run_l2_policy_diagnostic normal \
  "${NCU_DIR}/l2_policy_normal" \
  "${L2_NORMAL_NCU_RAW}" \
  "${L2_NORMAL_ACCEPTANCE_CSV}" \
  "${L2_NORMAL_ACCEPTANCE_MD}"

# Prefer normal caching. Persisting controls are attempted only after that
# strict normal diagnostic fails.
if python3 scripts/select_a100_l2_residency_policy.py \
  --normal-acceptance "${L2_NORMAL_ACCEPTANCE_CSV}" \
  --expected-w 16,128 \
  --load-repeat 4 \
  --out-csv "${L2_POLICY_CSV}" \
  --out-md "${L2_POLICY_MD}" \
  --out-env "${L2_POLICY_ENV}"; then
  source "${L2_POLICY_ENV}"
else
  run_l2_policy_diagnostic persisting \
    "${NCU_DIR}/l2_policy_persisting" \
    "${L2_PERSISTING_NCU_RAW}" \
    "${L2_PERSISTING_ACCEPTANCE_CSV}" \
    "${L2_PERSISTING_ACCEPTANCE_MD}"

  python3 scripts/select_a100_l2_residency_policy.py \
    --normal-acceptance "${L2_NORMAL_ACCEPTANCE_CSV}" \
    --persisting-acceptance "${L2_PERSISTING_ACCEPTANCE_CSV}" \
    --expected-w 16,128 \
    --load-repeat 4 \
    --out-csv "${L2_POLICY_CSV}" \
    --out-md "${L2_POLICY_MD}" \
    --out-env "${L2_POLICY_ENV}"
  source "${L2_POLICY_ENV}"
fi

if [[ -z "${L2_RESIDENCY_POLICY}" ]]; then
  echo "No A100 L2 residency policy passed the strict path gates" >&2
  exit 2
fi

# Full NCU runs before energy. Any Tensor RF scaling or L2 W/LR path failure
# stops the package before the long 20-second repeated measurements.
NCU_COMPONENTS=tensor,l2 \
NCU_EXPLICIT_METRICS_ONLY=1 \
NCU="${NCU_COMMAND}" \
BIN="${BINARY}" \
OUTDIR="${NCU_DIR}" \
RAW_OUT="${NCU_RAW}" \
TARGET_PROFILE=a100 \
NCU_CHIP=ga100 \
NCU_FILTER_UNAVAILABLE_METRICS=1 \
NCU_REPLAY_MODE=application \
NCU_CACHE_CONTROL=none \
GLOBAL_WARMUP_PASSES=4 \
L2_RESIDENCY_POLICY="${L2_RESIDENCY_POLICY}" \
GPU="${GPU}" \
ACTIVE_SM="${ACTIVE_SM}" \
BLOCKS_PER_SM=16 \
REG_BLOCKS_PER_SM=16 \
REG_W_SM_KIB=2048 \
L2_W_SM_KIB_VALUES=16,32,64,128 \
TENSOR_REUSE_FACTORS=1,2,4,8,16 \
MEMORY_LOAD_REPEATS=1,2,4,8,16 \
INCLUDE_L2_CAPACITY_NCU=0 \
INCLUDE_DIAGNOSTIC_NCU=0 \
bash scripts/run_ncu_validation.sh

python3 scripts/analyze_ncu_path_acceptance.py \
  "${NCU_DIR}/ncu_cache_validation_summary.csv" \
  --target-profile a100 \
  --out-csv "${NCU_ACCEPTANCE_CSV}" \
  --out-md "${NCU_ACCEPTANCE_MD}" \
  --tensor-memory-bytes-max 3e8 \
  --register-memory-bytes-max 3e8 \
  --tensor-memory-bytes-per-hmma-max 1.0 \
  --register-memory-bytes-per-op-max 1.0 \
  --require-ncu-replay-mode application \
  --require-ncu-cache-control none \
  --require-l2-residency-policy "${L2_RESIDENCY_POLICY}"

python3 scripts/audit_a100_ncu_precheck.py "${NCU_ACCEPTANCE_CSV}" \
  --expected-rf 1,2,4,8,16 \
  --expected-w 16,32,64,128 \
  --expected-lr 1,2,4,8,16 \
  --blocks-per-sm 16 \
  --active-sm "${ACTIVE_SM}" \
  --ncu-replay-mode application \
  --ncu-cache-control none \
  --global-warmup-passes 4 \
  --l2-residency-policy "${L2_RESIDENCY_POLICY}" \
  --hmma-ratio-spread-max 0.10 \
  --out-csv "${NCU_PRECHECK_CSV}" \
  --out-md "${NCU_PRECHECK_MD}" \
  --fail-on-fail

# Strict Tensor coordinate. Pair-locked ITER and atomic pair rotation are mandatory.
python3 scripts/run_component_regression_sweep.py \
  --execute \
  --binary "${BINARY}" \
  --target-profile a100 \
  --gpu-ids "${GPU}" \
  --max-active-gpus 1 \
  --modes reg_operand_only,reg_mma \
  --w-sm-kib-values 2048 \
  --blocks-per-sm-values 16 \
  --active-sm-values "${ACTIVE_SM}" \
  --reuse-factors 1,2,4,8,16 \
  --load-repeats 1 \
  --store-repeats 1 \
  --seconds 20 \
  --repeats 7 \
  --output "${TENSOR_RAW}" \
  --matrix-csv "${TENSOR_MATRIX}" \
  --tensor-pair-lock-iters \
  --tensor-pair-control-min-seconds 2 \
  --pair-calibration-csv "${PAIR_CALIBRATION}"

# L2 strict coordinate family. Keep blocks/SM fixed while sweeping W and LR.
python3 scripts/run_component_regression_sweep.py \
  --execute \
  --binary "${BINARY}" \
  --target-profile a100 \
  --gpu-ids "${GPU}" \
  --max-active-gpus 1 \
  --modes global_addr_only,l2_cg_load_only \
  --w-sm-kib-values 16,32,64,128 \
  --blocks-per-sm-values 16 \
  --active-sm-values "${ACTIVE_SM}" \
  --reuse-factors 1 \
  --load-repeats 4,8,16 \
  --store-repeats 1 \
  --seconds 20 \
  --repeats 7 \
  --global-warmup-passes 4 \
  --l2-residency-policy "${L2_RESIDENCY_POLICY}" \
  --output "${L2_RAW}" \
  --matrix-csv "${L2_MATRIX}"

python3 scripts/audit_power_api_measurements.py "${TENSOR_RAW}" "${L2_RAW}" \
  --target-profile a100 \
  --out-csv "${POWER_AUDIT_CSV}" \
  --out-md "${POWER_AUDIT_MD}" \
  --fail-on-reject --fail-on-provisional --require-explicit-measurement-scope \
  --require-mode-notes-marker \
  reg_operand_only=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 \
  --require-mode-notes-marker \
  reg_mma=tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2 \
  --require-mode-notes-marker \
  l2_cg_load_only=global_warmup_policy=ld_global_cg

python3 scripts/audit_power_state_stability.py "${TENSOR_RAW}" "${L2_RAW}" \
  --out-csv "${POWER_STATE_CSV}" \
  --out-md "${POWER_STATE_MD}"

python3 scripts/analyze_matched_control_energy.py "${TENSOR_RAW}" "${L2_RAW}" \
  --acceptance-csv "${NCU_ACCEPTANCE_CSV}" \
  --ncu-summary-csv "${NCU_DIR}/ncu_cache_validation_summary.csv" \
  --power-state-audit-csv "${POWER_STATE_CSV}" \
  --exclude-power-state-rejects \
  --require-ncu-denominator \
  --require-total-energy \
  --expected-power-semantics instant \
  --min-elapsed-s 16 \
  --tensor-control-min-elapsed-s 1.6 \
  --max-elapsed-ratio 1.35 \
  --max-pair-start-distance-ms 60000 \
  --pairing nearest-control \
  --tensor-pair-policy matched-iters \
  --min-delta-j 10 \
  --min-delta-fraction 0.005 \
  --out-summary-csv "${MATCHED_SUMMARY}" \
  --out-detail-csv "${MATCHED_DETAIL}" \
  --out-md "${MATCHED_MD}"

python3 scripts/audit_matched_control_instability.py "${MATCHED_DETAIL}" \
  --out-csv "${INSTABILITY_CSV}" \
  --out-md "${INSTABILITY_MD}"

python3 scripts/audit_a100_tensor_l2_remediation.py \
  --tensor-raw "${TENSOR_RAW}" \
  --l2-raw "${L2_RAW}" \
  --pair-calibration "${PAIR_CALIBRATION}" \
  --ncu-acceptance "${NCU_ACCEPTANCE_CSV}" \
  --matched-detail "${MATCHED_DETAIL}" \
  --expected-rf 1,2,4,8,16 \
  --expected-l2-w 16,32,64,128 \
  --ncu-load-repeats 1,2,4,8,16 \
  --energy-load-repeats 4,8,16 \
  --blocks-per-sm 16 \
  --active-sm "${ACTIVE_SM}" \
  --expected-repeats 7 \
  --min-valid-repeats 5 \
  --tensor-treatment-target-seconds 20 \
  --tensor-control-calibration-min-seconds 2 \
  --min-delta-j 10 \
  --max-pair-start-distance-ms 60000 \
  --ncu-replay-mode application \
  --ncu-cache-control none \
  --l2-residency-policy "${L2_RESIDENCY_POLICY}" \
  --global-warmup-passes 4 \
  --address-control-dram-ratio-max 0.001 \
  --out-csv "${REMEDIATION_CSV}" \
  --out-md "${REMEDIATION_MD}" \
  --fail-on-fail

echo "Targeted remediation passed. Review ${REMEDIATION_MD}"
