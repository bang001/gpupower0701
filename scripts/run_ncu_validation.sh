#!/usr/bin/env bash
set -euo pipefail

NCU="${NCU:-/home/bang001/miniforge3/envs/ssc21env/bin/ncu}"
read -r -a NCU_CMD <<< "${NCU}"
BIN="${BIN:-./build/a100_fp16_energy_v2}"
OUTDIR="${OUTDIR:-results/ncu/rtx3090_validation_20260701}"
RAW_OUT="${RAW_OUT:-results/raw/ncu_validation_sidecar_20260701.csv}"
GPU="${GPU:-0}"
TARGET_PROFILE="${TARGET_PROFILE:-rtx3090}"

case "${TARGET_PROFILE}" in
  v100)
    DEFAULT_ACTIVE_SM=80
    DRAM_W_SM_KIB=128
    ;;
  rtx3090)
    DEFAULT_ACTIVE_SM=82
    DRAM_W_SM_KIB=128
    ;;
  a100)
    DEFAULT_ACTIVE_SM=108
    DRAM_W_SM_KIB=512
    ;;
  h100)
    DEFAULT_ACTIVE_SM=132
    DRAM_W_SM_KIB=512
    ;;
  *)
    DEFAULT_ACTIVE_SM=82
    DRAM_W_SM_KIB=128
    ;;
esac

ACTIVE_SM="${ACTIVE_SM:-${DEFAULT_ACTIVE_SM}}"
SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-64}"
L2_W_SM_KIB="${L2_W_SM_KIB:-64}"
DRAM_W_SM_KIB="${DRAM_W_SM_KIB_OVERRIDE:-${DRAM_W_SM_KIB}}"
BLOCKS_PER_SM="${BLOCKS_PER_SM:-16}"

mkdir -p "${OUTDIR}" "$(dirname "${RAW_OUT}")"

COMMON_SECTIONS=(
  --section LaunchStats
  --section Occupancy
  --section SpeedOfLight
  --section WorkloadDistribution
  --section InstructionStats
  --section SchedulerStats
  --section WarpStateStats
  --section MemoryWorkloadAnalysis
)

run_case() {
  local label="$1"
  local kernel_regex="$2"
  local mode="$3"
  local w_sm_kib="$4"
  local blocks_per_sm="$5"
  local iters="$6"
  local report="${OUTDIR}/${label}"

  echo "== ${label}: mode=${mode} W=${w_sm_kib}KiB B=${blocks_per_sm} iters=${iters}"
  "${NCU_CMD[@]}" \
    "${COMMON_SECTIONS[@]}" \
    --target-processes application-only \
    --kernel-name-base demangled \
    --kernel-name "regex:${kernel_regex}" \
    --launch-count 1 \
    --replay-mode kernel \
    --cache-control none \
    --clock-control none \
    -f \
    -o "${report}" \
    "${BIN}" \
      --gpu-list "${GPU}" \
      --mode "${mode}" \
      --w-sm-kib "${w_sm_kib}" \
      --blocks-per-sm "${blocks_per_sm}" \
      --target-profile "${TARGET_PROFILE}" \
      --active-sm "${ACTIVE_SM}" \
      --iters "${iters}" \
      --repeats 1 \
      --seconds 1 \
      --output "${RAW_OUT}" \
      --verify-smid 1

  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page raw --csv \
    > "${report}_raw_metrics.csv"
  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page details --csv \
    > "${report}_details.csv"
}

run_case "empty_W64_B${BLOCKS_PER_SM}" "empty_kernel" "empty" 64 "${BLOCKS_PER_SM}" 1000000
run_case "reg_mma_W2048_B4" "reg_mma_kernel" "reg_mma" 2048 4 100000
run_case "shared_mma_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}" "shared_mma_kernel" "shared_mma" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "l2_mma_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "l2_mma" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "dram_mma_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "dram_mma" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000

echo "NCU validation reports written to ${OUTDIR}"
