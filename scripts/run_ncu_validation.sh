#!/usr/bin/env bash
set -euo pipefail

NCU="${NCU:-ncu}"
if [[ -x "${NCU}" ]]; then
  # Preserve installed paths containing spaces (common for Nsight Compute on WSL).
  NCU_BASE_CMD=("${NCU}")
else
  read -r -a NCU_BASE_CMD <<< "${NCU}"
fi
NCU_CMD=("${NCU_BASE_CMD[@]}")
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_AUTO_SUDO="${NCU_AUTO_SUDO:-1}"
NCU_SUDO="${NCU_SUDO:-sudo -E}"
NCU_IS_PRIVILEGED=0
if [[ "${NCU_USE_SUDO}" == "1" ]]; then
  read -r -a NCU_SUDO_CMD <<< "${NCU_SUDO}"
  NCU_CMD=("${NCU_SUDO_CMD[@]}" "${NCU_BASE_CMD[@]}")
  NCU_IS_PRIVILEGED=1
elif [[ "${NCU_BASE_CMD[0]##*/}" == "sudo" ]]; then
  NCU_IS_PRIVILEGED=1
fi
BIN="${BIN:-./build/a100_fp16_energy_v2}"
OUTDIR="${OUTDIR:-results/ncu/rtx3090_validation_20260701}"
RAW_OUT="${RAW_OUT:-results/raw/ncu_validation_sidecar_20260701.csv}"
GPU="${GPU:-0}"
TARGET_PROFILE="${TARGET_PROFILE:-rtx3090}"

case "${TARGET_PROFILE}" in
  v100)
    DEFAULT_ACTIVE_SM=80
    DRAM_W_SM_KIB=2048
    DEFAULT_DRAM_W_SM_KIB_VALUES=256,512,2048
    DEFAULT_NCU_CHIP=gv100
    DEFAULT_FILTER_UNAVAILABLE_METRICS=1
    ;;
  rtx3090)
    DEFAULT_ACTIVE_SM=82
    DRAM_W_SM_KIB=2048
    DEFAULT_DRAM_W_SM_KIB_VALUES=256,512,2048
    DEFAULT_NCU_CHIP=ga102
    DEFAULT_FILTER_UNAVAILABLE_METRICS=1
    ;;
  a100)
    DEFAULT_ACTIVE_SM=108
    DRAM_W_SM_KIB=8192
    DEFAULT_DRAM_W_SM_KIB_VALUES=2048,4096,8192
    DEFAULT_NCU_CHIP=ga100
    DEFAULT_FILTER_UNAVAILABLE_METRICS=1
    ;;
  h100)
    DEFAULT_ACTIVE_SM=132
    DRAM_W_SM_KIB=8192
    DEFAULT_DRAM_W_SM_KIB_VALUES=2048,4096,8192
    DEFAULT_NCU_CHIP=gh100
    DEFAULT_FILTER_UNAVAILABLE_METRICS=1
    ;;
  *)
    DEFAULT_ACTIVE_SM=82
    DRAM_W_SM_KIB=2048
    DEFAULT_DRAM_W_SM_KIB_VALUES=256,512,2048
    DEFAULT_NCU_CHIP=""
    DEFAULT_FILTER_UNAVAILABLE_METRICS=0
    ;;
esac

ACTIVE_SM="${ACTIVE_SM:-${DEFAULT_ACTIVE_SM}}"
NCU_CHIP="${NCU_CHIP:-${DEFAULT_NCU_CHIP}}"
NCU_FILTER_UNAVAILABLE_METRICS="${NCU_FILTER_UNAVAILABLE_METRICS:-${DEFAULT_FILTER_UNAVAILABLE_METRICS}}"
SHARED_W_SM_KIB="${SHARED_W_SM_KIB:-64}"
L1_W_SM_KIB="${L1_W_SM_KIB:-16}"
L2_W_SM_KIB="${L2_W_SM_KIB:-64}"
L2_W_SM_KIB_VALUES="${L2_W_SM_KIB_VALUES:-${L2_W_SM_KIB}}"
DRAM_W_SM_KIB="${DRAM_W_SM_KIB_OVERRIDE:-${DRAM_W_SM_KIB}}"
DRAM_W_SM_KIB_VALUES="${DRAM_W_SM_KIB_VALUES:-${DRAM_W_SM_KIB_OVERRIDE:-${DEFAULT_DRAM_W_SM_KIB_VALUES}}}"
BLOCKS_PER_SM="${BLOCKS_PER_SM:-16}"
L2_BLOCKS_PER_SM="${L2_BLOCKS_PER_SM:-${BLOCKS_PER_SM}}"
REG_W_SM_KIB="${REG_W_SM_KIB:-1}"
REG_BLOCKS_PER_SM="${REG_BLOCKS_PER_SM:-4}"
REG_BLOCKS_PER_SM_VALUES="${REG_BLOCKS_PER_SM_VALUES:-${REG_BLOCKS_PER_SM}}"
REG_PRESSURE_PAYLOAD_BYTES="${REG_PRESSURE_PAYLOAD_BYTES:-8192}"
REUSE_FACTOR="${REUSE_FACTOR:-1}"
SCHEDULER_MATCH_STEPS="${SCHEDULER_MATCH_STEPS:-1}"
INCLUDE_SCHEDULER_MATCHED_NCU="${INCLUDE_SCHEDULER_MATCHED_NCU:-0}"
ISSUE_MATCH_STEPS="${ISSUE_MATCH_STEPS:-1}"
ISSUE_MATCH_EXTRA_PERIOD="${ISSUE_MATCH_EXTRA_PERIOD:-0}"
INCLUDE_ISSUE_DEPENDENCY_NCU="${INCLUDE_ISSUE_DEPENDENCY_NCU:-0}"
LATENCY_MATCH_NS="${LATENCY_MATCH_NS:-0}"
LATENCY_MATCH_PERIOD="${LATENCY_MATCH_PERIOD:-1}"
RESIDENT_STALL_NS="${RESIDENT_STALL_NS:-128}"
RESIDENT_STALL_PERIOD="${RESIDENT_STALL_PERIOD:-1}"
INCLUDE_RESIDENT_STALL_NCU="${INCLUDE_RESIDENT_STALL_NCU:-0}"
LOAD_REPEAT="${LOAD_REPEAT:-1}"
STORE_REPEAT="${STORE_REPEAT:-1}"
TENSOR_REUSE_FACTORS="${TENSOR_REUSE_FACTORS:-${REUSE_FACTOR}}"
TENSOR_NCU_ITERS="${TENSOR_NCU_ITERS:-100000}"
MEMORY_LOAD_REPEATS="${MEMORY_LOAD_REPEATS:-${LOAD_REPEAT}}"
DRAM_LOAD_REPEATS="${DRAM_LOAD_REPEATS:-${MEMORY_LOAD_REPEATS}}"
NCU_COMPONENTS="${NCU_COMPONENTS:-baseline,tensor,shared,l1,l2,dram}"
NCU_METRIC_PROFILE="${NCU_METRIC_PROFILE:-full}"
NCU_REPLAY_MODE="${NCU_REPLAY_MODE:-application}"
NCU_CACHE_CONTROL="${NCU_CACHE_CONTROL:-none}"
GLOBAL_WARMUP_PASSES="${GLOBAL_WARMUP_PASSES:-1}"
L2_RESIDENCY_POLICY="${L2_RESIDENCY_POLICY:-normal}"
L2_ADDRESS_LAYOUT="${L2_ADDRESS_LAYOUT:-contiguous}"
INCLUDE_L2_CAPACITY_NCU="${INCLUDE_L2_CAPACITY_NCU:-0}"
INCLUDE_DIAGNOSTIC_NCU="${INCLUDE_DIAGNOSTIC_NCU:-0}"
DRY_RUN_NCU="${DRY_RUN_NCU:-0}"
NCU_PERMISSION_PROBE_ONLY="${NCU_PERMISSION_PROBE_ONLY:-0}"
SUMMARY_CSV="${SUMMARY_CSV:-${OUTDIR}/ncu_cache_validation_summary.csv}"
SUMMARY_MD="${SUMMARY_MD:-${OUTDIR}/ncu_cache_validation_summary.md}"
CASE_MANIFEST="${CASE_MANIFEST:-${OUTDIR}/ncu_validation_cases.csv}"

mkdir -p "${OUTDIR}" "$(dirname "${RAW_OUT}")"
if [[ "${NCU_IS_PRIVILEGED}" == "1" ]]; then
  printf "mode=explicit_sudo\ncommand=%s\n" "${NCU_CMD[*]}" > "${OUTDIR}/ncu_permission_mode.txt"
else
  printf "mode=unprivileged\ncommand=%s\n" "${NCU_CMD[*]}" > "${OUTDIR}/ncu_permission_mode.txt"
fi
case "${NCU_REPLAY_MODE}" in
  application|kernel) ;;
  *) echo "NCU_REPLAY_MODE must be application or kernel" >&2; exit 2 ;;
esac
case "${NCU_CACHE_CONTROL}" in
  none|all) ;;
  *) echo "NCU_CACHE_CONTROL must be none or all" >&2; exit 2 ;;
esac
case "${L2_RESIDENCY_POLICY}" in
  normal|persisting) ;;
  *) echo "L2_RESIDENCY_POLICY must be normal or persisting" >&2; exit 2 ;;
esac
case "${L2_ADDRESS_LAYOUT}" in
  contiguous|sm_interleaved) ;;
  *) echo "L2_ADDRESS_LAYOUT must be contiguous or sm_interleaved" >&2; exit 2 ;;
esac
case "${NCU_METRIC_PROFILE}" in
  full|l2_path_minimal) ;;
  *) echo "NCU_METRIC_PROFILE must be full or l2_path_minimal" >&2; exit 2 ;;
esac
if ! [[ "${GLOBAL_WARMUP_PASSES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "GLOBAL_WARMUP_PASSES must be a positive integer" >&2
  exit 2
fi
if ! [[ "${TENSOR_NCU_ITERS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "TENSOR_NCU_ITERS must be a positive integer" >&2
  exit 2
fi
if ! [[ "${L2_BLOCKS_PER_SM}" =~ ^(1|2|4|8|16|32)$ ]]; then
  echo "L2_BLOCKS_PER_SM must be 1, 2, 4, 8, 16, or 32" >&2
  exit 2
fi
if ! [[ "${SCHEDULER_MATCH_STEPS}" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]]; then
  echo "SCHEDULER_MATCH_STEPS must be an integer from 1 to 64" >&2
  exit 2
fi
if ! [[ "${ISSUE_MATCH_STEPS}" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]]; then
  echo "ISSUE_MATCH_STEPS must be an integer from 1 to 64" >&2
  exit 2
fi
if ! [[ "${ISSUE_MATCH_EXTRA_PERIOD}" =~ ^([0-9]|[1-9][0-9]{1,2}|10[01][0-9]|102[0-4])$ ]]; then
  echo "ISSUE_MATCH_EXTRA_PERIOD must be an integer from 0 to 1024" >&2
  exit 2
fi
if ! [[ "${LATENCY_MATCH_NS}" =~ ^([0-9]|[1-9][0-9]{1,3}|10000)$ ]]; then
  echo "LATENCY_MATCH_NS must be an integer from 0 to 10000" >&2
  exit 2
fi
if ! [[ "${LATENCY_MATCH_PERIOD}" =~ ^([1-9]|[1-9][0-9]{1,2}|10[01][0-9]|102[0-4])$ ]]; then
  echo "LATENCY_MATCH_PERIOD must be an integer from 1 to 1024" >&2
  exit 2
fi
printf "label,kernel_regex,mode,W_SM_KiB,blocks_per_SM,active_SM,ITER,reuse_factor,issue_match_steps,issue_match_extra_period,latency_match_ns,latency_match_period,scheduler_match_steps,load_repeat,store_repeat,ncu_replay_mode,ncu_cache_control,ncu_metric_profile,global_warmup_passes,l2_residency_policy,l2_address_layout,report\n" > "${CASE_MANIFEST}"

print_ncu_permission_hint() {
  cat >&2 <<'EOF'

Nsight Compute failed with ERR_NVGPUCTRPERM.
The user account does not have GPU performance-counter permission.

Preferred fix:
  Ask the node administrator to allow non-admin GPU performance counters.

Temporary sudo fallback for this script:
  NCU_USE_SUDO=1 NCU="$(command -v ncu)" ... bash scripts/run_ncu_validation.sh

Automatic fallback is enabled by default and retries only after the exact
ERR_NVGPUCTRPERM error. Disable it with NCU_AUTO_SUDO=0.

For generated platform packages:
  NCU_USE_SUDO=1 bash results/summary/<profile>_component_finalplan_<tag>_commands.sh

Keep NCU sidecar runs separate from NVML energy sweeps. Do not replace failed
NCU evidence with unvalidated denominators in final component coefficients.
EOF
}

enable_sudo_ncu() {
  if [[ "${NCU_IS_PRIVILEGED}" == "1" ]]; then
    return 0
  fi
  read -r -a NCU_SUDO_CMD <<< "${NCU_SUDO}"
  if [[ "${#NCU_SUDO_CMD[@]}" -eq 0 ]] || ! command -v "${NCU_SUDO_CMD[0]}" >/dev/null 2>&1; then
    echo "NCU automatic sudo fallback unavailable: '${NCU_SUDO}' was not found." >&2
    return 1
  fi
  NCU_CMD=("${NCU_SUDO_CMD[@]}" "${NCU_BASE_CMD[@]}")
  NCU_IS_PRIVILEGED=1
  printf "mode=auto_sudo\ncommand=%s\n" "${NCU_CMD[*]}" > "${OUTDIR}/ncu_permission_mode.txt"
  echo "Retrying NCU with elevated privileges after ERR_NVGPUCTRPERM: ${NCU_CMD[*]}" >&2
}

run_ncu_once_logged() {
  local log="$1"
  shift
  local -a pipeline_status=()
  local command_rc=1
  local tee_rc=1
  local stdout_fd

  : > "${log}"
  exec {stdout_fd}>&1
  if "${NCU_CMD[@]}" "$@" 2>&1 1>&${stdout_fd} | tee "${log}" >&2; then
    pipeline_status=("${PIPESTATUS[@]}")
  else
    pipeline_status=("${PIPESTATUS[@]}")
  fi
  exec {stdout_fd}>&-

  command_rc="${pipeline_status[0]:-1}"
  tee_rc="${pipeline_status[1]:-1}"
  if [[ "${tee_rc}" -ne 0 ]]; then
    echo "Failed to write complete NCU stderr log: ${log} (tee rc=${tee_rc})" >&2
    if [[ "${command_rc}" -eq 0 ]]; then
      return "${tee_rc}"
    fi
  fi
  return "${command_rc}"
}

run_ncu_profile() {
  local label="$1"
  shift
  local log="${OUTDIR}/${label}_ncu_stderr.log"
  local retry_log="${OUTDIR}/${label}_ncu_sudo_retry_stderr.log"
  local rc=0
  if run_ncu_once_logged "${log}" "$@"; then
    rc=0
  else
    rc=$?
  fi
  if grep -q "ERR_NVGPUCTRPERM" "${log}" 2>/dev/null; then
    local permission_rc="${rc}"
    if [[ "${permission_rc}" -eq 0 ]]; then
      permission_rc=13
    fi
    print_ncu_permission_hint
    if [[ "${NCU_AUTO_SUDO}" == "1" && "${NCU_IS_PRIVILEGED}" != "1" ]]; then
      enable_sudo_ncu || return "${permission_rc}"
      if run_ncu_once_logged "${retry_log}" "$@"; then
        rc=0
      else
        rc=$?
      fi
      if [[ "${rc}" -eq 0 ]] && ! grep -q "ERR_NVGPUCTRPERM" "${retry_log}" 2>/dev/null; then
        echo "NCU sudo retry succeeded for ${label}." >&2
      else
        echo "NCU sudo retry failed for ${label}; no counter evidence is accepted." >&2
        return "${permission_rc}"
      fi
    else
      return "${permission_rc}"
    fi
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
csv_to_array REG_BLOCKS_PER_SM_LIST "${REG_BLOCKS_PER_SM_VALUES}"
csv_to_array MEMORY_LOAD_REPEAT_LIST "${MEMORY_LOAD_REPEATS}"
csv_to_array DRAM_LOAD_REPEAT_LIST "${DRAM_LOAD_REPEATS}"
csv_to_array DRAM_W_SM_KIB_LIST "${DRAM_W_SM_KIB_VALUES}"
csv_to_array L2_W_SM_KIB_LIST "${L2_W_SM_KIB_VALUES}"
csv_to_array NCU_COMPONENT_LIST "${NCU_COMPONENTS}"

component_enabled() {
  local requested="$1"
  local component
  for component in "${NCU_COMPONENT_LIST[@]}"; do
    case "${component}" in
      all)
        return 0
        ;;
      baseline|tensor|shared|l1|l2|dram)
        if [[ "${component}" == "${requested}" ]]; then
          return 0
        fi
        ;;
      *)
        echo "unknown NCU component '${component}'; expected baseline,tensor,shared,l1,l2,dram or all" >&2
        return 2
        ;;
    esac
  done
  return 1
}

# Validate the complete list before launching the first profiler case.
for component in "${NCU_COMPONENT_LIST[@]}"; do
  case "${component}" in
    all|baseline|tensor|shared|l1|l2|dram) ;;
    *)
      echo "unknown NCU component '${component}'; expected baseline,tensor,shared,l1,l2,dram or all" >&2
      exit 2
      ;;
  esac
done
for tensor_blocks_per_sm in "${REG_BLOCKS_PER_SM_LIST[@]}"; do
  if ! [[ "${tensor_blocks_per_sm}" =~ ^(1|2|4|8|16|32)$ ]]; then
    echo "REG_BLOCKS_PER_SM_VALUES entries must be 1, 2, 4, 8, 16, or 32" >&2
    exit 2
  fi
done

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
DEFAULT_NCU_METRICS="l1tex__t_sector_hit_rate,l1tex__t_sectors_pipe_lsu_mem_global_op_ld,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__t_bytes_pipe_lsu_mem_global_op_ld,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__t_bytes_pipe_lsu_mem_local_op_ld,l1tex__t_bytes_pipe_lsu_mem_local_op_st,l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld,l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st,l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_ld,l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_st,smsp__sass_data_bytes_mem_shared,smsp__sass_data_bytes_mem_shared_op_ld,smsp__sass_data_bytes_mem_shared_op_ldsm,smsp__sass_data_bytes_mem_shared_op_st,smsp__sass_inst_executed,smsp__sass_inst_executed_op_shared,smsp__sass_inst_executed_op_shared_ld,smsp__sass_inst_executed_op_shared_st,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ld,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_ldsm,smsp__sass_l1tex_data_pipe_lsu_wavefronts_mem_shared_op_st,smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_ldsm,smsp__sass_l1tex_data_bank_conflicts_pipe_lsu_mem_shared_op_st,lts__t_sector_hit_rate,lts__t_sector_op_read_hit_rate,lts__t_sectors_srcunit_tex_op_read,lts__t_sectors_srcunit_tex_op_read_lookup_hit,lts__t_sectors_srcunit_tex_op_read_lookup_miss,lts__t_sectors_srcunit_tex_aperture_device_op_read,lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_hit,lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_miss,lts__t_sectors_srcunit_tex_op_read_evict_first,lts__t_sectors_srcunit_tex_op_read_evict_first_lookup_hit,lts__t_sectors_srcunit_tex_op_read_evict_first_lookup_miss,lts__t_sectors_srcunit_tex_op_read_evict_normal,lts__t_sectors_srcunit_tex_op_read_evict_normal_lookup_hit,lts__t_sectors_srcunit_tex_op_read_evict_normal_lookup_miss,lts__t_sectors_srcunit_tex_op_read_evict_last,lts__t_sectors_srcunit_tex_op_read_evict_last_lookup_hit,lts__t_sectors_srcunit_tex_op_read_evict_last_lookup_miss,lts__t_bytes,lts__t_bytes_equiv_l1sectormiss_pipe_lsu_mem_global_op_ld,dram__bytes,dram__bytes_read,dram__bytes_write,dram__sectors,dram__sectors_read,dram__sectors_write,gpu__time_duration.sum,smsp__average_warps_issue_stalled_long_scoreboard_per_issue_active,smsp__average_warps_issue_stalled_short_scoreboard_per_issue_active,smsp__average_warps_issue_stalled_wait_per_issue_active,smsp__average_warps_issue_stalled_not_selected_per_issue_active,smsp__warp_issue_stalled_sleeping_per_warp_active,smsp__average_warp_latency_issue_stalled_sleeping,sm__issue_active.avg.pct_of_peak_sustained_active,sm__warps_active.avg.pct_of_peak_sustained_active,sm__pipe_tensor_cycles_active.avg.pct_of_peak_sustained_active,sm__pipe_alu_cycles_active.avg.pct_of_peak_sustained_active,sm__pipe_fma_cycles_active.avg.pct_of_peak_sustained_active,launch__registers_per_thread,launch__shared_mem_per_block_static,launch__shared_mem_per_block_dynamic,launch__persisting_l2_cache_size,sm__inst_executed_pipe_tensor_op_hmma,sm__inst_executed_pipe_fma_type_fp16,sm__ops_path_tensor_src_fp16_dst_fp32,smsp__sass_thread_inst_executed_op_ffma_pred_on,smsp__sass_thread_inst_executed_op_fp16_pred_on,smsp__sass_thread_inst_executed_op_fp32_pred_on,smsp__sass_thread_inst_executed_op_integer_pred_on,sass__inst_executed_register_spilling_mem_local_op_read,sass__inst_executed_register_spilling_mem_local_op_write"
L2_PATH_MINIMAL_NCU_METRICS="l1tex__t_sectors_pipe_lsu_mem_global_op_ld,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__t_bytes_pipe_lsu_mem_global_op_ld,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_hit,l1tex__t_bytes_pipe_lsu_mem_global_op_ld_lookup_miss,l1tex__t_bytes_pipe_lsu_mem_local_op_ld,l1tex__t_bytes_pipe_lsu_mem_local_op_st,lts__t_sector_op_read_hit_rate,lts__t_sectors_srcunit_tex_op_read,lts__t_sectors_srcunit_tex_op_read_lookup_hit,lts__t_sectors_srcunit_tex_op_read_lookup_miss,lts__t_sectors_srcunit_tex_aperture_device_op_read,lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_hit,lts__t_sectors_srcunit_tex_aperture_device_op_read_lookup_miss,lts__t_bytes_equiv_l1sectormiss_pipe_lsu_mem_global_op_ld,dram__bytes,dram__bytes_read,dram__bytes_write,dram__sectors,dram__sectors_read,dram__sectors_write,gpu__time_duration.sum,smsp__average_warps_issue_stalled_long_scoreboard_per_issue_active,launch__registers_per_thread,launch__shared_mem_per_block_static,launch__shared_mem_per_block_dynamic,launch__persisting_l2_cache_size"
if [[ "${TARGET_PROFILE}" == "a100" || "${TARGET_PROFILE}" == "h100" ]]; then
  # GA100 and GH100 use partitioned L2 fabrics. Keep cross-partition lookups in
  # the same replay bundle so first-lookup and final-service populations can be
  # checked for conservation. Missing fabric metrics remain a hard reject.
  L2_PATH_MINIMAL_NCU_METRICS+=",lts__t_sectors_srcunit_ltcfabric_op_read,lts__t_sectors_srcunit_ltcfabric_op_read_lookup_hit,lts__t_sectors_srcunit_ltcfabric_op_read_lookup_miss,lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read,lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_hit,lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read_lookup_miss"
fi
if [[ "${NCU_METRIC_PROFILE}" == "l2_path_minimal" ]]; then
  PROFILE_NCU_METRICS="${L2_PATH_MINIMAL_NCU_METRICS}"
else
  PROFILE_NCU_METRICS="${DEFAULT_NCU_METRICS}"
fi
NCU_METRICS="${NCU_METRICS:-${PROFILE_NCU_METRICS}}"

filter_unavailable_ncu_metrics() {
  local available_file="${OUTDIR}/ncu_available_metrics_${NCU_CHIP:-native}.txt"
  local dropped_file="${OUTDIR}/ncu_dropped_metrics_${NCU_CHIP:-native}.txt"
  local chip_args=()
  local requested=()
  local selected=()
  local dropped=()

  if [[ -n "${NCU_CHIP}" ]]; then
    chip_args=(--chips "${NCU_CHIP}")
  fi
  if ! "${NCU_CMD[@]}" --query-metrics "${chip_args[@]}" > "${available_file}"; then
    echo "failed to query NCU metrics for chip '${NCU_CHIP:-native}'" >&2
    return 2
  fi

  csv_to_array requested "${NCU_METRICS}"
  for metric in "${requested[@]}"; do
    local metric_regex="${metric//./\\.}"
    local metric_base="${metric%%.*}"
    local metric_base_regex="${metric_base//./\\.}"
    if grep -Eq "(^|[^[:alnum:]_])(${metric_regex}|${metric_base_regex})([.]|[^[:alnum:]_]|$)" "${available_file}"; then
      selected+=("${metric}")
    else
      dropped+=("${metric}")
    fi
  done

  if [[ "${#selected[@]}" -eq 0 ]]; then
    echo "none of the requested NCU metrics are available for '${NCU_CHIP:-native}'" >&2
    return 2
  fi
  printf "%s\n" "${dropped[@]}" > "${dropped_file}"
  NCU_METRICS="$(IFS=,; echo "${selected[*]}")"
  echo "NCU metric availability: selected=${#selected[@]} dropped=${#dropped[@]} chip=${NCU_CHIP:-native}"
  if [[ "${#dropped[@]}" -gt 0 ]]; then
    echo "Dropped unavailable metrics are recorded in ${dropped_file}; path acceptance must still reject missing required evidence."
  fi
}

if [[ "${DRY_RUN_NCU}" != "1" && "${NCU_FILTER_UNAVAILABLE_METRICS}" == "1" ]]; then
  filter_unavailable_ncu_metrics
fi
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
  local scheduler_match_steps="${11:-${SCHEDULER_MATCH_STEPS}}"
  local issue_match_steps="${12:-${ISSUE_MATCH_STEPS}}"
  local issue_match_extra_period="${13:-${ISSUE_MATCH_EXTRA_PERIOD}}"
  local latency_match_ns="${14:-${LATENCY_MATCH_NS}}"
  local latency_match_period="${15:-${LATENCY_MATCH_PERIOD}}"
  local case_l2_residency_policy="normal"
  local case_l2_address_layout="contiguous"
  if [[ "${label}" == l2_cg_load_only_* ||
        "${label}" == global_addr_only_l2_* ]]; then
    case_l2_residency_policy="${L2_RESIDENCY_POLICY}"
    case_l2_address_layout="${L2_ADDRESS_LAYOUT}"
  fi
  local report="${OUTDIR}/${label}"

  echo "== ${label}: mode=${mode} W=${w_sm_kib}KiB B=${blocks_per_sm} iters=${iters} reuse=${reuse_factor} issue_steps=${issue_match_steps} issue_extra_period=${issue_match_extra_period} latency_ns=${latency_match_ns} latency_period=${latency_match_period} scheduler_steps=${scheduler_match_steps} load_repeat=${load_repeat}"
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "${label}" "${kernel_regex}" "${mode}" "${w_sm_kib}" "${blocks_per_sm}" \
    "${ACTIVE_SM}" "${iters}" "${reuse_factor}" "${issue_match_steps}" "${issue_match_extra_period}" "${latency_match_ns}" "${latency_match_period}" "${scheduler_match_steps}" "${load_repeat}" \
    "${store_repeat}" "${NCU_REPLAY_MODE}" "${NCU_CACHE_CONTROL}" \
    "${NCU_METRIC_PROFILE}" "${GLOBAL_WARMUP_PASSES}" "${case_l2_residency_policy}" \
    "${case_l2_address_layout}" \
    "${report}" >> "${CASE_MANIFEST}"
  if [[ "${DRY_RUN_NCU}" == "1" ]]; then
    return 0
  fi

  run_ncu_profile "${label}" \
    "${COMMON_SECTIONS[@]}" \
    "${EXPLICIT_METRIC_ARGS[@]}" \
    --target-processes all \
    --kernel-name-base demangled \
    --kernel-name "regex:${kernel_regex}" \
    --launch-count 1 \
    --replay-mode "${NCU_REPLAY_MODE}" \
    --cache-control "${NCU_CACHE_CONTROL}" \
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
      --issue-match-steps "${issue_match_steps}" \
      --issue-match-extra-period "${issue_match_extra_period}" \
      --latency-match-ns "${latency_match_ns}" \
      --latency-match-period "${latency_match_period}" \
      --scheduler-match-steps "${scheduler_match_steps}" \
      --load-repeat "${load_repeat}" \
      --store-repeat "${store_repeat}" \
      --global-warmup-passes "${GLOBAL_WARMUP_PASSES}" \
      --l2-residency-policy "${case_l2_residency_policy}" \
      --l2-address-layout "${case_l2_address_layout}" \
      --reg-payload-bytes "${reg_payload_bytes}" \
      --repeats 1 \
      --seconds 1 \
      --skip-idle-baseline \
      --output "${RAW_OUT}" \
      --verify-smid 1

  if [[ ! -s "${report}.ncu-rep" ]]; then
    echo "NCU produced no usable report for ${label}: ${report}.ncu-rep" >&2
    return 3
  fi

  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page raw --csv \
    > "${report}_raw_metrics.csv"
  "${NCU_CMD[@]}" --import "${report}.ncu-rep" --page details --csv \
    > "${report}_details.csv"
}

# Primary finalplan validation cases. These are the only modes needed for the
# default component coefficient flow.
if component_enabled baseline; then
  run_case "clocked_empty_W64_B${BLOCKS_PER_SM}" "clocked_empty_kernel" "clocked_empty" 64 "${BLOCKS_PER_SM}" 1000000
fi

if [[ "${NCU_PERMISSION_PROBE_ONLY}" == "1" ]]; then
  echo "NCU permission probe succeeded; hardware counters are accessible with mode ${NCU_IS_PRIVILEGED}."
  exit 0
fi

if component_enabled tensor; then
  for tensor_blocks_per_sm in "${REG_BLOCKS_PER_SM_LIST[@]}"; do
    for reuse_factor in "${TENSOR_REUSE_FACTOR_LIST[@]}"; do
      tensor_ncu_iters_var="TENSOR_NCU_ITERS_RF${reuse_factor}"
      tensor_ncu_iters="${!tensor_ncu_iters_var:-${TENSOR_NCU_ITERS}}"
      if ! [[ "${tensor_ncu_iters}" =~ ^[1-9][0-9]*$ ]]; then
        echo "${tensor_ncu_iters_var} must be a positive integer" >&2
        exit 2
      fi
      run_case "reg_operand_only_W${REG_W_SM_KIB}_B${tensor_blocks_per_sm}_RF${reuse_factor}" "reg_operand_only_kernel" "reg_operand_only" "${REG_W_SM_KIB}" "${tensor_blocks_per_sm}" "${tensor_ncu_iters}" 0 "${reuse_factor}" 1
      if [[ "${INCLUDE_SCHEDULER_MATCHED_NCU}" == "1" ]]; then
        run_case "reg_scheduler_matched_no_mma_W${REG_W_SM_KIB}_B${tensor_blocks_per_sm}_RF${reuse_factor}_S${SCHEDULER_MATCH_STEPS}" "reg_scheduler_matched_no_mma_kernel" "reg_scheduler_matched_no_mma" "${REG_W_SM_KIB}" "${tensor_blocks_per_sm}" "${tensor_ncu_iters}" 0 "${reuse_factor}" 1 1 "${SCHEDULER_MATCH_STEPS}"
      fi
      if [[ "${INCLUDE_ISSUE_DEPENDENCY_NCU}" == "1" ]]; then
        issue_steps_var="ISSUE_MATCH_STEPS_RF${reuse_factor}"
        issue_steps="${!issue_steps_var:-${ISSUE_MATCH_STEPS}}"
        issue_extra_period_var="ISSUE_MATCH_EXTRA_PERIOD_RF${reuse_factor}"
        issue_extra_period="${!issue_extra_period_var:-${ISSUE_MATCH_EXTRA_PERIOD}}"
        if ! [[ "${issue_steps}" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]]; then
          echo "${issue_steps_var} must be an integer from 1 to 64" >&2
          exit 2
        fi
        if ! [[ "${issue_extra_period}" =~ ^([0-9]|[1-9][0-9]{1,2}|10[01][0-9]|102[0-4])$ ]]; then
          echo "${issue_extra_period_var} must be an integer from 0 to 1024" >&2
          exit 2
        fi
        run_case "reg_issue_dependency_no_mma_W${REG_W_SM_KIB}_B${tensor_blocks_per_sm}_RF${reuse_factor}_I${issue_steps}_P${issue_extra_period}" "reg_issue_dependency_no_mma_kernel" "reg_issue_dependency_no_mma" "${REG_W_SM_KIB}" "${tensor_blocks_per_sm}" "${tensor_ncu_iters}" 0 "${reuse_factor}" 1 1 1 "${issue_steps}" "${issue_extra_period}"
      fi
      if [[ "${INCLUDE_RESIDENT_STALL_NCU}" == "1" ]]; then
        resident_ns_var="RESIDENT_STALL_NS_RF${reuse_factor}"
        resident_ns="${!resident_ns_var:-${RESIDENT_STALL_NS}}"
        resident_period_var="RESIDENT_STALL_PERIOD_RF${reuse_factor}"
        resident_period="${!resident_period_var:-${RESIDENT_STALL_PERIOD}}"
        if ! [[ "${resident_ns}" =~ ^([0-9]|[1-9][0-9]{1,3}|10000)$ ]]; then
          echo "${resident_ns_var} must be an integer from 0 to 10000" >&2
          exit 2
        fi
        if ! [[ "${resident_period}" =~ ^([1-9]|[1-9][0-9]{1,2}|10[01][0-9]|102[0-4])$ ]]; then
          echo "${resident_period_var} must be an integer from 1 to 1024" >&2
          exit 2
        fi
        run_case "reg_resident_stall_no_mma_W${REG_W_SM_KIB}_B${tensor_blocks_per_sm}_RF${reuse_factor}_N${resident_ns}_P${resident_period}" "reg_resident_stall_no_mma_kernel" "reg_resident_stall_no_mma" "${REG_W_SM_KIB}" "${tensor_blocks_per_sm}" "${tensor_ncu_iters}" 0 "${reuse_factor}" 1 1 1 1 0 "${resident_ns}" "${resident_period}"
      fi
      run_case "reg_mma_W${REG_W_SM_KIB}_B${tensor_blocks_per_sm}_RF${reuse_factor}" "reg_mma_kernel" "reg_mma" "${REG_W_SM_KIB}" "${tensor_blocks_per_sm}" "${tensor_ncu_iters}" 0 "${reuse_factor}" 1
    done
  done
fi

for load_repeat in "${MEMORY_LOAD_REPEAT_LIST[@]}"; do
  if component_enabled shared; then
    run_case "shared_scalar_addr_only_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "shared_scalar_addr_only_kernel" "shared_scalar_addr_only" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
    run_case "shared_scalar_load_only_W${SHARED_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "shared_scalar_load_only_kernel" "shared_scalar_load_only" "${SHARED_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  fi
  if component_enabled l1; then
    run_case "global_addr_only_l1_W${L1_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${L1_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
    run_case "global_l1_load_only_W${L1_W_SM_KIB}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_ca_load_only_kernel" "global_l1_load_only" "${L1_W_SM_KIB}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
  fi
  if component_enabled l2; then
    for l2_w_sm_kib in "${L2_W_SM_KIB_LIST[@]}"; do
      if [[ "${INCLUDE_L2_CAPACITY_NCU}" == "1" ]]; then
        run_case "l2_load_only_W${l2_w_sm_kib}_B${L2_BLOCKS_PER_SM}_LR${load_repeat}" "global_load_only_kernel" "l2_load_only" "${l2_w_sm_kib}" "${L2_BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
      fi
      run_case "global_addr_only_l2_W${l2_w_sm_kib}_B${L2_BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${l2_w_sm_kib}" "${L2_BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
      run_case "l2_cg_load_only_W${l2_w_sm_kib}_B${L2_BLOCKS_PER_SM}_LR${load_repeat}" "global_cg_load_only_kernel" "l2_cg_load_only" "${l2_w_sm_kib}" "${L2_BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
    done
  fi
done

if component_enabled dram; then
  for dram_w_sm_kib in "${DRAM_W_SM_KIB_LIST[@]}"; do
    for load_repeat in "${DRAM_LOAD_REPEAT_LIST[@]}"; do
      run_case "global_addr_only_dram_W${dram_w_sm_kib}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_scalar_addr_only_kernel" "global_addr_only" "${dram_w_sm_kib}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
      run_case "dram_cg_load_only_W${dram_w_sm_kib}_B${BLOCKS_PER_SM}_LR${load_repeat}" "global_cg_load_only_kernel" "dram_cg_load_only" "${dram_w_sm_kib}" "${BLOCKS_PER_SM}" 100000 0 1 "${load_repeat}"
    done
  done
fi

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
