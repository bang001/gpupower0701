#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TMP_ROOT}"' EXIT

FAKE_NCU="${TMP_ROOT}/fake_ncu"
FAKE_SUDO="${TMP_ROOT}/fake_sudo"

cat > "${FAKE_NCU}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--import" ]]; then
  printf 'ID,Kernel Name,Metric Name,Metric Unit,Metric Value\n'
  exit 0
fi
if [[ "${FAKE_NCU_PRIVILEGED:-0}" != "1" ]]; then
  echo '==ERROR== ERR_NVGPUCTRPERM - fake counter permission denial' >&2
  exit 9
fi
report=""
while [[ "$#" -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then
    report="$2"
    shift 2
  else
    shift
  fi
done
[[ -n "${report}" ]]
mkdir -p "$(dirname "${report}")"
printf 'fake ncu report\n' > "${report}.ncu-rep"
EOF

cat > "${FAKE_SUDO}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-E" ]]; then
  shift
fi
export FAKE_NCU_PRIVILEGED=1
exec "$@"
EOF
chmod +x "${FAKE_NCU}" "${FAKE_SUDO}"

COMMON_ENV=(
  NCU_PERMISSION_PROBE_ONLY=1
  NCU_EXPLICIT_METRICS_ONLY=1
  NCU_METRICS=fake_counter
  NCU_FILTER_UNAVAILABLE_METRICS=0
  NCU="${FAKE_NCU}"
  NCU_SUDO="${FAKE_SUDO} -E"
  BIN="${TMP_ROOT}/fake_binary"
  RAW_OUT="${TMP_ROOT}/probe_raw.csv"
  TARGET_PROFILE=v100
  NCU_CHIP=gv100
  GPU=0
  ACTIVE_SM=80
  BLOCKS_PER_SM=32
)

AUTO_OUT="${TMP_ROOT}/auto"
env "${COMMON_ENV[@]}" NCU_AUTO_SUDO=1 OUTDIR="${AUTO_OUT}" \
  bash "${ROOT}/scripts/run_ncu_validation.sh" > "${TMP_ROOT}/auto.stdout" 2> "${TMP_ROOT}/auto.stderr"
grep -q 'ERR_NVGPUCTRPERM' "${AUTO_OUT}/clocked_empty_W64_B32_ncu_stderr.log"
grep -q 'NCU sudo retry succeeded' "${TMP_ROOT}/auto.stderr"
grep -q '^mode=auto_sudo$' "${AUTO_OUT}/ncu_permission_mode.txt"
test -s "${AUTO_OUT}/clocked_empty_W64_B32.ncu-rep"

NO_AUTO_OUT="${TMP_ROOT}/no_auto"
set +e
env "${COMMON_ENV[@]}" NCU_AUTO_SUDO=0 OUTDIR="${NO_AUTO_OUT}" \
  bash "${ROOT}/scripts/run_ncu_validation.sh" > "${TMP_ROOT}/no_auto.stdout" 2> "${TMP_ROOT}/no_auto.stderr"
NO_AUTO_RC=$?
set -e
if [[ "${NO_AUTO_RC}" -eq 0 ]]; then
  echo "NCU_AUTO_SUDO=0 unexpectedly accepted a permission-denied profile" >&2
  exit 1
fi
grep -q '^mode=unprivileged$' "${NO_AUTO_OUT}/ncu_permission_mode.txt"

echo "NCU permission fallback self-test passed"
