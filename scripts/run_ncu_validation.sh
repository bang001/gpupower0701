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
REUSE_FACTOR="${REUSE_FACTOR:-1}"
LOAD_REPEAT="${LOAD_REPEAT:-1}"
STORE_REPEAT="${STORE_REPEAT:-1}"
SUMMARY_CSV="${SUMMARY_CSV:-${OUTDIR}/ncu_cache_validation_summary.csv}"
SUMMARY_MD="${SUMMARY_MD:-${OUTDIR}/ncu_cache_validation_summary.md}"
CASE_MANIFEST="${CASE_MANIFEST:-${OUTDIR}/ncu_validation_cases.csv}"

mkdir -p "${OUTDIR}" "$(dirname "${RAW_OUT}")"
printf "label,kernel_regex,mode,W_SM_KiB,blocks_per_SM,active_SM,ITER,reuse_factor,load_repeat,store_repeat,report\n" > "${CASE_MANIFEST}"

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
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "${label}" "${kernel_regex}" "${mode}" "${w_sm_kib}" "${blocks_per_sm}" \
    "${ACTIVE_SM}" "${iters}" "${REUSE_FACTOR}" "${LOAD_REPEAT}" \
    "${STORE_REPEAT}" "${report}" >> "${CASE_MANIFEST}"
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
      --reuse-factor "${REUSE_FACTOR}" \
      --load-repeat "${LOAD_REPEAT}" \
      --store-repeat "${STORE_REPEAT}" \
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
run_case "reg_fragment_only_W2048_B4" "reg_fragment_only_kernel" "reg_fragment_only" 2048 4 100000
run_case "reg_operand_only_W2048_B4" "reg_operand_only_kernel" "reg_operand_only" 2048 4 100000
run_case "reg_mma_W2048_B4" "reg_mma_kernel" "reg_mma" 2048 4 100000
run_case "shared_load_only_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}" "shared_load_only_kernel" "shared_load_only" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "shared_mma_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}" "shared_mma_kernel" "shared_mma" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "l2_load_only_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_load_only_kernel" "l2_load_only" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "l2_mma_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "l2_mma" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "dram_load_only_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_load_only_kernel" "dram_load_only" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "dram_mma_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "dram_mma" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
run_case "store_only_W64_B${BLOCKS_PER_SM}" "store_path_kernel" "store_only" 64 "${BLOCKS_PER_SM}" 100000

python3 scripts/summarize_ncu_cache_metrics.py \
  "${OUTDIR}/*_raw_metrics.csv" \
  --case-manifest "${CASE_MANIFEST}" \
  --out-csv "${SUMMARY_CSV}" \
  --out-md "${SUMMARY_MD}"

echo "NCU validation reports written to ${OUTDIR}"
echo "NCU cache summary written to ${SUMMARY_CSV} and ${SUMMARY_MD}"
