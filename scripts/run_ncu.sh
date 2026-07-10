#!/usr/bin/env bash
set -euo pipefail

BIN="${BIN:-./build/a100_fp16_energy_v2}"
NCU="${NCU:-ncu}"
read -r -a NCU_CMD <<< "${NCU}"
NCU_USE_SUDO="${NCU_USE_SUDO:-0}"
NCU_SUDO="${NCU_SUDO:-sudo -E}"
if [[ "${NCU_USE_SUDO}" == "1" ]]; then
  read -r -a NCU_SUDO_CMD <<< "${NCU_SUDO}"
  NCU_CMD=("${NCU_SUDO_CMD[@]}" "${NCU_CMD[@]}")
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

run_ncu_profile() {
  local log="$1"
  shift
  set +e
  "${NCU_CMD[@]}" "$@" 2> >(tee "${log}" >&2)
  local rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]] && grep -q "ERR_NVGPUCTRPERM" "${log}" 2>/dev/null; then
    print_ncu_permission_hint
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
