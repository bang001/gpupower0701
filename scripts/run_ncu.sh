#!/usr/bin/env bash
set -euo pipefail

BIN="${BIN:-./build/a100_fp16_energy_v2}"
NCU="${NCU:-ncu}"
read -r -a NCU_BASE_CMD <<< "${NCU}"
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
GPU="${GPU:-0}"
MODE="${MODE:-shared_mma}"
W_SM_KIB="${W_SM_KIB:-128}"
BLOCKS_PER_SM="${BLOCKS_PER_SM:-1}"
ACTIVE_SM="${ACTIVE_SM:-82}"
TARGET_PROFILE="${TARGET_PROFILE:-rtx3090}"
NCU_CHIP="${NCU_CHIP:-}"
ITERS="${ITERS:-4096}"
OUTDIR="${OUTDIR:-results/ncu}"
CACHE_CONTROL="${CACHE_CONTROL:-none}"
REUSE_FACTOR="${REUSE_FACTOR:-1}"
LOAD_REPEAT="${LOAD_REPEAT:-1}"
STORE_REPEAT="${STORE_REPEAT:-1}"
SUMMARY_CSV="${SUMMARY_CSV:-}"
SUMMARY_MD="${SUMMARY_MD:-}"

print_ncu_permission_hint() {
  cat >&2 <<'EOF'

Nsight Compute failed with ERR_NVGPUCTRPERM.
The user account does not have GPU performance-counter permission.

Preferred fix:
  Ask the node administrator to allow non-admin GPU performance counters.

Temporary sudo fallback for this script:
  NCU_USE_SUDO=1 NCU="$(command -v ncu)" ... bash scripts/run_ncu.sh

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
  local log="$1"
  shift
  local retry_log="${log%.log}_sudo_retry.log"
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
        echo "NCU sudo retry succeeded." >&2
      else
        echo "NCU sudo retry failed; no counter evidence is accepted." >&2
        return "${permission_rc}"
      fi
    else
      return "${permission_rc}"
    fi
  fi
  return "${rc}"
}

if [[ "${1:-}" == "--query-metrics" ]]; then
  chip_args=()
  if [[ -n "${NCU_CHIP}" ]]; then
    chip_args=(--chips "${NCU_CHIP}")
  fi
  "${NCU_CMD[@]}" --query-metrics "${chip_args[@]}" \
    | grep -E "tensor|shared|warps|occupancy|smsp|sm__|dram__(bytes|sectors)|l1tex__(t_(sector_hit_rate|sectors|requests|bytes)|m_(xbar2l1tex_read_sectors|l1tex2xbar_write_sectors))|lts__(t_(sector_hit_rate|sectors|tag_requests)|t_sectors_srcunit_tex)" || true
  exit 0
fi

if [[ "${1:-}" == "--list-chips" ]]; then
  "${NCU_CMD[@]}" --list-chips
  exit 0
fi

mkdir -p "${OUTDIR}"

REPORT="${OUTDIR}/ncu_${MODE}_W${W_SM_KIB}_B${BLOCKS_PER_SM}_SM${ACTIVE_SM}_GPU${GPU}"

echo "Writing Nsight Compute report to ${REPORT}.ncu-rep"
echo "Metric names vary by NCU version; run '$0 --query-metrics' when a focused metric set is needed."

run_ncu_profile "${REPORT}_ncu_stderr.log" \
  --set full \
  --target-processes all \
  --replay-mode application \
  --cache-control "${CACHE_CONTROL}" \
  -o "${REPORT}" \
  "${BIN}" \
    --gpu-list "${GPU}" \
    --mode "${MODE}" \
    --w-sm-kib "${W_SM_KIB}" \
    --blocks-per-sm "${BLOCKS_PER_SM}" \
    --target-profile "${TARGET_PROFILE}" \
    --active-sm "${ACTIVE_SM}" \
    --iters "${ITERS}" \
    --reuse-factor "${REUSE_FACTOR}" \
    --load-repeat "${LOAD_REPEAT}" \
    --store-repeat "${STORE_REPEAT}" \
    --repeats 1 \
    --seconds 1 \
    --output "results/raw/ncu_sidecar_runs.csv" \
    --verify-smid 1

if [[ ! -s "${REPORT}.ncu-rep" ]]; then
  echo "NCU produced no usable report: ${REPORT}.ncu-rep" >&2
  exit 3
fi

"${NCU_CMD[@]}" --import "${REPORT}.ncu-rep" --page raw --csv \
  > "${REPORT}_raw_metrics.csv"
"${NCU_CMD[@]}" --import "${REPORT}.ncu-rep" --page details --csv \
  > "${REPORT}_details.csv"

CASE_MANIFEST="${REPORT}_case.csv"
printf "label,kernel_regex,mode,W_SM_KiB,blocks_per_SM,active_SM,ITER,reuse_factor,load_repeat,store_repeat,report\n" > "${CASE_MANIFEST}"
printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
  "$(basename "${REPORT}")" "" "${MODE}" "${W_SM_KIB}" "${BLOCKS_PER_SM}" \
  "${ACTIVE_SM}" "${ITERS}" "${REUSE_FACTOR}" "${LOAD_REPEAT}" \
  "${STORE_REPEAT}" "${REPORT}" >> "${CASE_MANIFEST}"

SUMMARY_CSV="${SUMMARY_CSV:-${REPORT}_cache_summary.csv}"
SUMMARY_MD="${SUMMARY_MD:-${REPORT}_cache_summary.md}"
python3 scripts/summarize_ncu_cache_metrics.py \
  "${REPORT}_raw_metrics.csv" \
  --case-manifest "${CASE_MANIFEST}" \
  --out-csv "${SUMMARY_CSV}" \
  --out-md "${SUMMARY_MD}"

echo "NCU cache summary written to ${SUMMARY_CSV} and ${SUMMARY_MD}"
