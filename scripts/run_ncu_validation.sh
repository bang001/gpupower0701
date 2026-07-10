#!/usr/bin/env bash
set -euo pipefail

NCU="${NCU:-/home/bang001/miniforge3/envs/ssc21env/bin/ncu}"
read -r -a NCU_CMD <<< "${NCU}"
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_SUDO="${NCU_SUDO:-sudo -E}"
if [[ "${NCU_USE_SUDO}" == "1" ]]; then
  read -r -a NCU_SUDO_CMD <<< "${NCU_SUDO}"
  NCU_CMD=("${NCU_SUDO_CMD[@]}" "${NCU_CMD[@]}")
fi
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
L1_W_SM_KIB="${L1_W_SM_KIB:-16}"
L2_W_SM_KIB="${L2_W_SM_KIB:-64}"
DRAM_W_SM_KIB="${DRAM_W_SM_KIB_OVERRIDE:-${DRAM_W_SM_KIB}}"
BLOCKS_PER_SM="${BLOCKS_PER_SM:-16}"
REG_W_SM_KIB="${REG_W_SM_KIB:-2048}"
REG_BLOCKS_PER_SM="${REG_BLOCKS_PER_SM:-4}"
REG_PRESSURE_PAYLOAD_BYTES="${REG_PRESSURE_PAYLOAD_BYTES:-8192}"
REUSE_FACTOR="${REUSE_FACTOR:-1}"
LOAD_REPEAT="${LOAD_REPEAT:-1}"
STORE_REPEAT="${STORE_REPEAT:-1}"
TENSOR_REUSE_FACTORS="${TENSOR_REUSE_FACTORS:-${REUSE_FACTOR}}"
MEMORY_LOAD_REPEATS="${MEMORY_LOAD_REPEATS:-${LOAD_REPEAT}}"
DRAM_LOAD_REPEATS="${DRAM_LOAD_REPEATS:-${MEMORY_LOAD_REPEATS}}"
INCLUDE_L2_CAPACITY_NCU="${INCLUDE_L2_CAPACITY_NCU:-0}"
INCLUDE_DIAGNOSTIC_NCU="${INCLUDE_DIAGNOSTIC_NCU:-0}"
DRY_RUN_NCU="${DRY_RUN_NCU:-0}"
SUMMARY_CSV="${SUMMARY_CSV:-${OUTDIR}/ncu_cache_validation_summary.csv}"
SUMMARY_MD="${SUMMARY_MD:-${OUTDIR}/ncu_cache_validation_summary.md}"
CASE_MANIFEST="${CASE_MANIFEST:-${OUTDIR}/ncu_validation_cases.csv}"

mkdir -p "${OUTDIR}" "$(dirname "${RAW_OUT}")"
printf "label,kernel_regex,mode,W_SM_KiB,blocks_per_SM,active_SM,ITER,reuse_factor,load_repeat,store_repeat,report\n" > "${CASE_MANIFEST}"

print_ncu_permission_hint() {
  cat >&2 <<'EOF'

Nsight Compute failed with ERR_NVGPUCTRPERM.
The user account does not have GPU performance-counter permission.

Preferred fix:
  Ask the node administrator to allow non-admin GPU performance counters.

Temporary sudo fallback for this script:
  NCU_USE_SUDO=1 NCU="$(command -v ncu)" ... bash scripts/run_ncu_validation.sh

For generated platform packages:
  NCU_USE_SUDO=1 bash results/summary/<profile>_component_finalplan_<tag>_commands.sh

Keep NCU sidecar runs separate from NVML energy sweeps. Do not replace failed
NCU evidence with unvalidated denominators in final component coefficients.
EOF
}

run_ncu_profile() {
  local label="$1"
  shift
  local log="${OUTDIR}/${label}_ncu_stderr.log"
  set +e
  "${NCU_CMD[@]}" "$@" 2> >(tee "${log}" >&2)
  local rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]] && grep -q "ERR_NVGPUCTRPERM" "${log}" 2>/dev/null; then
    print_ncu_permission_hint
  fi
  return "${rc}"
}

csv_to_array() {
  local var_name="$1"
  local csv="$2"
  csv="${csv//[[:space:]]/}"
  if [[ -z "${csv}" ]]; then
    echo "empty CSV list for ${var_name}" >&2
    exit 2
  fi
  IFS=',' read -r -a "${var_name}" <<< "${csv}"
}

csv_to_array TENSOR_REUSE_FACTOR_LIST "${TENSOR_REUSE_FACTORS}"
csv_to_array MEMORY_LOAD_REPEAT_LIST "${MEMORY_LOAD_REPEATS}"
csv_to_array DRAM_LOAD_REPEAT_LIST "${DRAM_LOAD_REPEATS}"

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
DEFAULT_NCU_METRICS="l1tex__t_sector_hit_rate,l1tex__t_sectors_pipe_lsu_mem_global_op_ld,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__t_bytes_pipe_lsu_mem_global_op_ld,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld,l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st,l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_ld,l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_st,smsp__sass_data_bytes_mem_shared,smsp__sass_data_bytes_mem_shared_op_ld,smsp__sass_data_bytes_mem_shared_op_ldsm,smsp__sass_data_bytes_mem_shared_op_st,smsp__sass_inst_executed_op_shared,smsp__sass_inst_executed_op_shared_ld,smsp__sass_inst_executed_op_shared_st,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ld,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ldsm,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_st,smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_ldsm,smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_st,lts__t_sector_hit_rate,lts__t_sectors_srcunit_tex_op_read,lts__t_sectors_srcunit_tex_op_read_lookup_hit,lts__t_sectors_srcunit_tex_op_read_lookup_miss,lts__t_bytes,lts__t_bytes_equiv_l1sectormiss_pipe_lsu_mem_global_op_ld,dram__bytes,dram__bytes_read,dram__sectors,dram__sectors_read,smsp__average_warps_issue_stalled_long_scoreboard_per_issue_active,smsp__average_warps_issue_stalled_short_scoreboard_per_issue_active,smsp__average_warps_issue_stalled_wait_per_issue_active,smsp__average_warps_issue_stalled_not_selected_per_issue_active,sm__inst_executed_pipe_tensor_op_hmma,sass__inst_executed_register_spilling_mem_local_op_read,sass__inst_executed_register_spilling_mem_local_op_write"
NCU_METRICS="${NCU_METRICS:-${DEFAULT_NCU_METRICS}}"
if [[ "${NCU_EXPLICIT_METRICS_ONLY:-0}" == "1" ]]; then
  COMMON_SECTIONS=()
fi
EXPLICIT_METRIC_ARGS=()
if [[ -n "${NCU_METRICS}" ]]; then
  EXPLICIT_METRIC_ARGS=(--metrics "${NCU_METRICS}")
fi

run_case() {
  local label="$1"
  local kernel_regex="$2"
  local mode="$3"
  local w_sm_kib="$4"
  local blocks_per_sm="$5"
  local iters="$6"
  local reg_payload_bytes="${7:-0}"
  local reuse_factor="${8:-${REUSE_FACTOR}}"
  local load_repeat="${9:-${LOAD_REPEAT}}"
  local store_repeat="${10:-${STORE_REPEAT}}"
  local report="${OUTDIR}/${label}"

  echo "== ${label}: mode=${mode} W=${w_sm_kib}KiB B=${blocks_per_sm} iters=${iters} reuse=${reuse_factor} load_repeat=${load_repeat}"
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "${label}" "${kernel_regex}" "${mode}" "${w_sm_kib}" "${blocks_per_sm}" \
    "${ACTIVE_SM}" "${iters}" "${reuse_factor}" "${load_repeat}" \
    "${store_repeat}" "${report}" >> "${CASE_MANIFEST}"
  if [[ "${DRY_RUN_NCU}" == "1" ]]; then
    return 0
  fi

  run_ncu_profile "${label}" \
    "${COMMON_SECTIONS[@]}" \
    "${EXPLICIT_METRIC_ARGS[@]}" \
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
      --reuse-factor "${reuse_factor}" \
      --load-repeat "${load_repeat}" \
      --store-repeat "${store_repeat}" \
      --reg-payload-bytes "${reg_payload_bytes}" \
      --repeats 1 \
      --seconds 1 \
      --output "${RAW_OUT}" \
      --verify-smid 1

  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page raw --csv \
    > "${report}_raw_metrics.csv"
  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page details --csv \
    > "${report}_details.csv"
}

# Primary finalplan validation cases. These are the only modes needed for the
# default component coefficient flow.
run_case "clocked_empty_W64_B${BLOCKS_PER_SM}" "clocked_empty_kernel" "clocked_empty" 64 "${BLOCKS_PER_SM}" 1000000

for reuse_factor in "${TENSOR_REUSE_FACTOR_LIST[@]}"; do
  run_case "reg_operand_only_W${REG_W_SM_KIB}_B${REG_BLOCKS_PER_SM}_RF${reuse_factor}" "reg_operand_only_kernel" "reg_operand_only" "${REG_W_SM_KIB}" "${REG_BLOCKS_PER_SM}" 100000 0 "${reuse_factor}" 1
  run_case "reg_mma_W${REG_W_SM_KIB}_B${REG_BLOCKS_PER_SM}_RF${reuse_factor}" "reg_mma_kernel" "reg_mma" "${REG_W_SM_KIB}" "${REG_BLOCKS_PER_SM}" 100000 0 "${reuse_factor}" 1
done

for load_repeat in "${MEMORY_LOAD_REPEAT_LIST[@]}"; do
  run_case "shared_scalar_load_only_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "shared_scalar_load_only_kernel" "shared_scalar_load_only" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  run_case "global_addr_only_l1_W${L1_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${L1_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  run_case "global_l1_load_only_W${L1_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_ca_load_only_kernel" "global_l1_load_only" "${L1_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  if [[ "${INCLUDE_L2_CAPACITY_NCU}" == "1" ]]; then
    run_case "l2_load_only_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_load_only_kernel" "l2_load_only" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  fi
  run_case "global_addr_only_l2_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  run_case "l2_cg_load_only_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_cg_load_only_kernel" "l2_cg_load_only" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
done

for load_repeat in "${DRAM_LOAD_REPEAT_LIST[@]}"; do
  run_case "global_addr_only_dram_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  run_case "dram_cg_load_only_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_cg_load_only_kernel" "dram_cg_load_only" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
done

if [[ "${INCLUDE_DIAGNOSTIC_NCU}" == "1" ]]; then
  run_case "empty_W64_B${BLOCKS_PER_SM}" "empty_kernel" "empty" 64 "${BLOCKS_PER_SM}" 1000000
  run_case "addr_only_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_addr_only_kernel" "addr_only" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "reg_fragment_only_W${REG_W_SM_KIB}_B${REG_BLOCKS_PER_SM}" "reg_fragment_only_kernel" "reg_fragment_only" "${REG_W_SM_KIB}" "${REG_BLOCKS_PER_SM}" 100000
  run_case "reg_pressure_P${REG_PRESSURE_PAYLOAD_BYTES}_B${REG_BLOCKS_PER_SM}" "reg_pressure_kernel" "reg_pressure" 1 "${REG_BLOCKS_PER_SM}" 100000 "${REG_PRESSURE_PAYLOAD_BYTES}"
  run_case "shared_load_only_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}" "shared_load_only_kernel" "shared_load_only" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "shared_mma_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}" "shared_mma_kernel" "shared_mma" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "l2_mma_W${L2_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "l2_mma" "${L2_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "dram_load_only_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_load_only_kernel" "dram_load_only" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "dram_mma_W${DRAM_W_SM_KIB}_B${BLOCKS_PER_SM}" "global_mma_kernel" "dram_mma" "${DRAM_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000
  run_case "store_only_W64_B${BLOCKS_PER_SM}" "store_path_kernel" "store_only" 64 "${BLOCKS_PER_SM}" 100000
fi

if [[ "${DRY_RUN_NCU}" == "1" ]]; then
  echo "DRY_RUN_NCU=1: wrote case manifest to ${CASE_MANIFEST}"
  exit 0
fi

python3 scripts/summarize_ncu_cache_metrics.py \
  "${OUTDIR}/*_raw_metrics.csv" \
  --case-manifest "${CASE_MANIFEST}" \
  --out-csv "${SUMMARY_CSV}" \
  --out-md "${SUMMARY_MD}"

echo "NCU validation reports written to ${OUTDIR}"
echo "NCU cache summary written to ${SUMMARY_CSV} and ${SUMMARY_MD}"
