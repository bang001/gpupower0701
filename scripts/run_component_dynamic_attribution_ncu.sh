#!/usr/bin/env bash
set -euo pipefail

# NCU sidecar for component_dynamic_attribution_v3. Energy collection must be
# completed separately; profiler replay is never used as an energy numerator.

TARGET_PROFILE="${TARGET_PROFILE:-rtx3090}"
TAG="${TAG:-$(date +%Y%m%d)}"
GPU="${GPU:-0}"
BIN="${BIN:-./build/a100_fp16_energy_v2}"
NCU="${NCU:-ncu}"
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_AUTO_SUDO="${NCU_AUTO_SUDO:-1}"
DRY_RUN_NCU="${DRY_RUN_NCU:-0}"
NCU_SKIP_QUIESCENCE="${NCU_SKIP_QUIESCENCE:-0}"
NCU_QUIESCENCE_SAMPLES="${NCU_QUIESCENCE_SAMPLES:-12}"
NCU_QUIESCENCE_INTERVAL_MS="${NCU_QUIESCENCE_INTERVAL_MS:-1000}"
NCU_QUIESCENCE_POLICY="${NCU_QUIESCENCE_POLICY:-auto}"
NCU_COUNTER_MAX_MEMORY_UTIL_PCT="${NCU_COUNTER_MAX_MEMORY_UTIL_PCT:-25}"
NCU_COUNTER_P95_MEMORY_UTIL_PCT="${NCU_COUNTER_P95_MEMORY_UTIL_PCT:-25}"
BLOCKS_PER_SM_INPUT="${BLOCKS_PER_SM:-}"
BLOCKS_PER_SM_VALUES_INPUT="${BLOCKS_PER_SM_VALUES:-}"
ATTRIBUTION_COMPONENTS="${ATTRIBUTION_COMPONENTS:-tensor,shared,l1,l2,external}"
TENSOR_REUSE_FACTORS="${TENSOR_REUSE_FACTORS:-1,2,4,8,16}"
MEMORY_LOAD_REPEATS="${MEMORY_LOAD_REPEATS:-4,8,16}"

has_component() {
  [[ ",${ATTRIBUTION_COMPONENTS}," == *",$1,"* ]]
}

append_csv_value() {
  local current="$1"
  local value="$2"
  printf '%s' "${current:+${current},}${value}"
}

case "${TARGET_PROFILE}" in
  rtx3090)
    ACTIVE_SM="${ACTIVE_SM:-82}"
    DEFAULT_BLOCKS_PER_SM_VALUES="4,8,16"
    MAX_BLOCKS_PER_SM=16
    SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-64}"
    L1_W_SM_KIB="${L1_W_SM_KIB:-16}"
    L2_CONTROL_W_SM_KIB="${L2_CONTROL_W_SM_KIB:-32}"
    EXTERNAL_W_SM_KIB="${EXTERNAL_W_SM_KIB:-256}"
    ;;
  v100)
    ACTIVE_SM="${ACTIVE_SM:-80}"
    DEFAULT_BLOCKS_PER_SM_VALUES="4,16,32"
    MAX_BLOCKS_PER_SM=32
    SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-32}"
    L1_W_SM_KIB="${L1_W_SM_KIB:-32}"
    L2_CONTROL_W_SM_KIB="${L2_CONTROL_W_SM_KIB:-32}"
    EXTERNAL_W_SM_KIB="${EXTERNAL_W_SM_KIB:-256}"
    ;;
  a100)
    ACTIVE_SM="${ACTIVE_SM:-108}"
    DEFAULT_BLOCKS_PER_SM_VALUES="4,16,32"
    MAX_BLOCKS_PER_SM=32
    SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-128}"
    L1_W_SM_KIB="${L1_W_SM_KIB:-32}"
    L2_CONTROL_W_SM_KIB="${L2_CONTROL_W_SM_KIB:-128}"
    EXTERNAL_W_SM_KIB="${EXTERNAL_W_SM_KIB:-2048}"
    ;;
  h100)
    ACTIVE_SM="${ACTIVE_SM:-132}"
    DEFAULT_BLOCKS_PER_SM_VALUES="4,16,32"
    MAX_BLOCKS_PER_SM=32
    SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-128}"
    L1_W_SM_KIB="${L1_W_SM_KIB:-32}"
    L2_CONTROL_W_SM_KIB="${L2_CONTROL_W_SM_KIB:-128}"
    EXTERNAL_W_SM_KIB="${EXTERNAL_W_SM_KIB:-2048}"
    ;;
  *)
    echo "unsupported TARGET_PROFILE=${TARGET_PROFILE}" >&2
    exit 2
    ;;
esac

unique_csv() {
  local input="$1"
  local output=""
  local value
  local seen=","
  IFS=',' read -r -a values <<< "${input}"
  for value in "${values[@]}"; do
    if [[ "${seen}" != *",${value},"* ]]; then
      output="${output:+${output},}${value}"
      seen="${seen}${value},"
    fi
  done
  printf '%s' "${output}"
}

if [[ -n "${BLOCKS_PER_SM_VALUES_INPUT}" ]]; then
  BLOCKS_PER_SM_VALUES="${BLOCKS_PER_SM_VALUES_INPUT}"
elif [[ -n "${BLOCKS_PER_SM_INPUT}" ]]; then
  BLOCKS_PER_SM_VALUES="${BLOCKS_PER_SM_INPUT}"
else
  BLOCKS_PER_SM_VALUES="${DEFAULT_BLOCKS_PER_SM_VALUES}"
fi
BLOCKS_PER_SM_VALUES="$(unique_csv "${BLOCKS_PER_SM_VALUES}")"
IFS=',' read -r -a BLOCKS_PER_SM_LIST <<< "${BLOCKS_PER_SM_VALUES}"
for blocks_per_sm in "${BLOCKS_PER_SM_LIST[@]}"; do
  if ! [[ "${blocks_per_sm}" =~ ^(1|2|4|8|16|32)$ ]] \
    || (( blocks_per_sm > MAX_BLOCKS_PER_SM )); then
    echo "invalid blocks/SM=${blocks_per_sm} for ${TARGET_PROFILE}" >&2
    exit 2
  fi
done

ROOT_OUT="${OUTDIR:-results/ncu/${TARGET_PROFILE}_component_dynamic_attribution_ncu_${TAG}}"
RAW_OUT="${RAW_OUT:-results/raw/${TARGET_PROFILE}_component_dynamic_attribution_ncu_${TAG}.csv}"
COMBINED_SUMMARY="${ROOT_OUT}/ncu_cache_validation_summary.csv"
COMBINED_MD="${ROOT_OUT}/ncu_cache_validation_summary.md"
ACCEPTANCE_CSV="${ACCEPTANCE_CSV:-results/summary/${TARGET_PROFILE}_component_dynamic_attribution_${TAG}_ncu_acceptance.csv}"
ACCEPTANCE_MD="${ACCEPTANCE_MD:-results/summary/${TARGET_PROFILE}_component_dynamic_attribution_${TAG}_ncu_acceptance.md}"
L2_VALUES="$(unique_csv "${L1_W_SM_KIB},${L2_CONTROL_W_SM_KIB}")"

NCU_BINARY_SHA256_BEFORE=""
if [[ -f "${BIN}" ]]; then
  NCU_BINARY_SHA256_BEFORE="$(sha256sum "${BIN}" | cut -d' ' -f1)"
elif [[ "${DRY_RUN_NCU}" != "1" ]]; then
  echo "NCU binary does not exist: ${BIN}" >&2
  exit 2
fi

mkdir -p "${ROOT_OUT}" "$(dirname "${RAW_OUT}")" "$(dirname "${ACCEPTANCE_CSV}")"
SUMMARY_INPUTS=()
NCU_QUIESCENCE_STATUS="skipped"

if [[ "${NCU_QUIESCENCE_POLICY}" == "auto" ]]; then
  if [[ "${TARGET_PROFILE}" == "rtx3090" \
    && -r /proc/sys/kernel/osrelease \
    && "$(< /proc/sys/kernel/osrelease)" =~ [Mm]icrosoft ]]; then
    NCU_QUIESCENCE_POLICY="counter_scope"
  else
    NCU_QUIESCENCE_POLICY="strict"
  fi
fi
case "${NCU_QUIESCENCE_POLICY}" in
  strict|counter_scope) ;;
  *)
    echo "invalid NCU_QUIESCENCE_POLICY=${NCU_QUIESCENCE_POLICY}; expected auto, strict, or counter_scope" >&2
    exit 2
    ;;
esac

if [[ "${DRY_RUN_NCU}" != "1" && "${NCU_SKIP_QUIESCENCE}" != "1" ]]; then
  QUIESCENCE_ARGS=(
    --gpu "${GPU}"
    --samples "${NCU_QUIESCENCE_SAMPLES}"
    --interval-ms "${NCU_QUIESCENCE_INTERVAL_MS}"
    --out-csv "${ROOT_OUT}/ncu_preflight_quiescence.csv"
    --out-md "${ROOT_OUT}/ncu_preflight_quiescence.md"
    --strict
  )
  if [[ "${NCU_QUIESCENCE_POLICY}" == "counter_scope" ]]; then
    QUIESCENCE_ARGS+=(
      --max-memory-util-pct "${NCU_COUNTER_MAX_MEMORY_UTIL_PCT}"
      --p95-memory-util-pct "${NCU_COUNTER_P95_MEMORY_UTIL_PCT}"
    )
    NCU_QUIESCENCE_STATUS="counter_scope_passed"
  else
    NCU_QUIESCENCE_STATUS="strict_passed"
  fi
  printf '%s\n' \
    "policy=${NCU_QUIESCENCE_POLICY}" \
    "status_on_pass=${NCU_QUIESCENCE_STATUS}" \
    "max_memory_util_pct=${NCU_COUNTER_MAX_MEMORY_UTIL_PCT}" \
    "p95_memory_util_pct=${NCU_COUNTER_P95_MEMORY_UTIL_PCT}" \
    > "${ROOT_OUT}/ncu_quiescence_policy.txt"
  echo "NCU quiescence policy: ${NCU_QUIESCENCE_POLICY}"
  python3 scripts/audit_gpu_quiescence.py "${QUIESCENCE_ARGS[@]}"
fi

for BLOCKS_PER_SM in "${BLOCKS_PER_SM_LIST[@]}"; do
  FULL_OUT="${ROOT_OUT}/full_non_l2/B${BLOCKS_PER_SM}"
  MINIMAL_OUT="${ROOT_OUT}/l2_path_minimal/B${BLOCKS_PER_SM}"
  FULL_SUMMARY="${FULL_OUT}/ncu_cache_validation_summary.csv"
  MINIMAL_SUMMARY="${MINIMAL_OUT}/ncu_cache_validation_summary.csv"
  mkdir -p "${FULL_OUT}" "${MINIMAL_OUT}"

  FULL_COMPONENTS=""
  if has_component tensor; then
    FULL_COMPONENTS="$(append_csv_value "${FULL_COMPONENTS}" baseline)"
    FULL_COMPONENTS="$(append_csv_value "${FULL_COMPONENTS}" tensor)"
  fi
  if has_component shared; then
    FULL_COMPONENTS="$(append_csv_value "${FULL_COMPONENTS}" shared)"
  fi
  if has_component l1; then
    FULL_COMPONENTS="$(append_csv_value "${FULL_COMPONENTS}" l1)"
  fi

  if [[ -n "${FULL_COMPONENTS}" ]]; then
    echo "NCU full path bundle: ${FULL_COMPONENTS}; B=${BLOCKS_PER_SM}"
    NCU="${NCU}" \
  NCU_USE_SUDO="${NCU_USE_SUDO}" \
  NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" \
  BIN="${BIN}" \
  GPU="${GPU}" \
  TARGET_PROFILE="${TARGET_PROFILE}" \
  ACTIVE_SM="${ACTIVE_SM}" \
  BLOCKS_PER_SM="${BLOCKS_PER_SM}" \
  REG_BLOCKS_PER_SM_VALUES="${BLOCKS_PER_SM}" \
  REG_W_SM_KIB=1 \
  TENSOR_REUSE_FACTORS="${TENSOR_REUSE_FACTORS}" \
  SHARED_W_SM_KIB="${SHARED_W_SM_KIB}" \
  L1_W_SM_KIB="${L1_W_SM_KIB}" \
  MEMORY_LOAD_REPEATS="${MEMORY_LOAD_REPEATS}" \
  NCU_COMPONENTS="${FULL_COMPONENTS}" \
  NCU_METRIC_PROFILE=full \
  NCU_EXPLICIT_METRICS_ONLY=1 \
  NCU_REPLAY_MODE=application \
  NCU_CACHE_CONTROL=none \
  GLOBAL_WARMUP_PASSES=4 \
  OUTDIR="${FULL_OUT}" \
  RAW_OUT="${RAW_OUT}" \
  SUMMARY_CSV="${FULL_SUMMARY}" \
  SUMMARY_MD="${FULL_OUT}/ncu_cache_validation_summary.md" \
  DRY_RUN_NCU="${DRY_RUN_NCU}" \
    bash scripts/run_ncu_validation.sh
    SUMMARY_INPUTS+=("${FULL_SUMMARY}")
  fi

  MINIMAL_COMPONENTS=""
  if has_component l2; then
    MINIMAL_COMPONENTS="$(append_csv_value "${MINIMAL_COMPONENTS}" l2)"
  fi
  if has_component external; then
    MINIMAL_COMPONENTS="$(append_csv_value "${MINIMAL_COMPONENTS}" dram)"
  fi
  if [[ -n "${MINIMAL_COMPONENTS}" ]]; then
    echo "NCU coherent L2/external path bundle: ${MINIMAL_COMPONENTS}; B=${BLOCKS_PER_SM}"
    NCU="${NCU}" \
  NCU_USE_SUDO="${NCU_USE_SUDO}" \
  NCU_AUTO_SUDO="${NCU_AUTO_SUDO}" \
  BIN="${BIN}" \
  GPU="${GPU}" \
  TARGET_PROFILE="${TARGET_PROFILE}" \
  ACTIVE_SM="${ACTIVE_SM}" \
  BLOCKS_PER_SM="${BLOCKS_PER_SM}" \
  L2_BLOCKS_PER_SM="${BLOCKS_PER_SM}" \
  L2_W_SM_KIB_VALUES="${L2_VALUES}" \
  DRAM_W_SM_KIB_VALUES="${EXTERNAL_W_SM_KIB}" \
  MEMORY_LOAD_REPEATS="${MEMORY_LOAD_REPEATS}" \
  DRAM_LOAD_REPEATS="${MEMORY_LOAD_REPEATS}" \
  NCU_COMPONENTS="${MINIMAL_COMPONENTS}" \
  NCU_METRIC_PROFILE=l2_path_minimal \
  NCU_EXPLICIT_METRICS_ONLY=1 \
  NCU_REPLAY_MODE=application \
  NCU_CACHE_CONTROL=none \
  GLOBAL_WARMUP_PASSES=4 \
  L2_RESIDENCY_POLICY=normal \
  L2_ADDRESS_LAYOUT=contiguous \
  OUTDIR="${MINIMAL_OUT}" \
  RAW_OUT="${RAW_OUT}" \
  SUMMARY_CSV="${MINIMAL_SUMMARY}" \
  SUMMARY_MD="${MINIMAL_OUT}/ncu_cache_validation_summary.md" \
  DRY_RUN_NCU="${DRY_RUN_NCU}" \
    bash scripts/run_ncu_validation.sh
    SUMMARY_INPUTS+=("${MINIMAL_SUMMARY}")
  fi
done

if (( ${#SUMMARY_INPUTS[@]} == 0 )); then
  echo "ATTRIBUTION_COMPONENTS selected no supported NCU component: ${ATTRIBUTION_COMPONENTS}" >&2
  exit 2
fi

if [[ "${DRY_RUN_NCU}" == "1" ]]; then
  if [[ -n "${NCU_BINARY_SHA256_BEFORE}" ]]; then
    echo "NCU binary SHA-256 (dry run only): ${NCU_BINARY_SHA256_BEFORE}"
  fi
  echo "DRY_RUN_NCU=1: case manifests written under ${ROOT_OUT}"
  exit 0
fi

NCU_BINARY_SHA256_AFTER="$(sha256sum "${BIN}" | cut -d' ' -f1)"
if [[ -z "${NCU_BINARY_SHA256_BEFORE}" \
  || "${NCU_BINARY_SHA256_BEFORE}" != "${NCU_BINARY_SHA256_AFTER}" ]]; then
  echo "NCU binary changed during profiling; refusing to merge evidence" >&2
  exit 2
fi

python3 scripts/merge_ncu_validation_summaries.py \
  "${SUMMARY_INPUTS[@]}" \
  --out-csv "${COMBINED_SUMMARY}" \
  --out-md "${COMBINED_MD}" \
  --ncu-binary-sha256 "${NCU_BINARY_SHA256_BEFORE}" \
  --ncu-binary-path "${BIN}" \
  --ncu-binary-hash-capture pre_post_collection_verified \
  --ncu-quiescence-status "${NCU_QUIESCENCE_STATUS}"

python3 scripts/analyze_ncu_path_acceptance.py \
  "${COMBINED_SUMMARY}" \
  --target-profile "${TARGET_PROFILE}" \
  --require-ncu-replay-mode application \
  --require-ncu-cache-control none \
  --require-l2-residency-policy normal \
  --require-l2-address-layout contiguous \
  --out-csv "${ACCEPTANCE_CSV}" \
  --out-md "${ACCEPTANCE_MD}"

echo "Combined NCU summary: ${COMBINED_SUMMARY}"
echo "NCU path acceptance: ${ACCEPTANCE_CSV}"
