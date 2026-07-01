#!/usr/bin/env bash
set -euo pipefail

BIN="${BIN:-./build/a100_fp16_energy_v2}"
GPU="${GPU:-0}"
MODE="${MODE:-shared_mma}"
W_SM_KIB="${W_SM_KIB:-128}"
BLOCKS_PER_SM="${BLOCKS_PER_SM:-1}"
ACTIVE_SM="${ACTIVE_SM:-82}"
TARGET_PROFILE="${TARGET_PROFILE:-rtx3090}"
ITERS="${ITERS:-4096}"
OUTDIR="${OUTDIR:-results/ncu}"
CACHE_CONTROL="${CACHE_CONTROL:-none}"

if [[ "${1:-}" == "--query-metrics" ]]; then
  ncu --query-metrics-mode suffix --query-metrics \
    | grep -E "tensor|dram|lts|l1tex|shared|warps|occupancy|smsp|sm__" || true
  exit 0
fi

mkdir -p "${OUTDIR}"

REPORT="${OUTDIR}/ncu_${MODE}_W${W_SM_KIB}_B${BLOCKS_PER_SM}_SM${ACTIVE_SM}_GPU${GPU}"

echo "Writing Nsight Compute report to ${REPORT}.ncu-rep"
echo "Metric names vary by NCU version; run '$0 --query-metrics' when a focused metric set is needed."

ncu \
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
    --repeats 1 \
    --seconds 1 \
    --output "results/raw/ncu_sidecar_runs.csv" \
    --verify-smid 1
