#!/usr/bin/env bash
set -euo pipefail

# The test must always begin unprivileged, regardless of the caller's package
# policy. All fake NCU/sudo settings are supplied explicitly below.
unset NCU_USE_SUDO NCU_AUTO_SUDO NCU_SUDO NCU FAKE_NCU_PRIVILEGED

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

assert_contains() {
  local pattern="$1"
  local path="$2"
  local description="$3"
  if ! grep -q -- "${pattern}" "${path}" 2>/dev/null; then
    echo "NCU permission fallback self-test failed: ${description}" >&2
    echo "Expected pattern '${pattern}' in ${path}" >&2
    if [[ -f "${path}" ]]; then
      sed -n '1,160p' "${path}" >&2
    else
      echo "File does not exist: ${path}" >&2
    fi
    exit 1
  fi
}

assert_nonempty() {
  local path="$1"
  local description="$2"
  if [[ ! -s "${path}" ]]; then
    echo "NCU permission fallback self-test failed: ${description}" >&2
    echo "Expected a non-empty file: ${path}" >&2
    exit 1
  fi
}

assert_not_contains() {
  local pattern="$1"
  local path="$2"
  local description="$3"
  if grep -q -- "${pattern}" "${path}" 2>/dev/null; then
    echo "NCU permission fallback self-test failed: ${description}" >&2
    echo "Unexpected pattern '${pattern}' in ${path}" >&2
    sed -n '1,160p' "${path}" >&2
    exit 1
  fi
}

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
assert_contains 'ERR_NVGPUCTRPERM' "${AUTO_OUT}/clocked_empty_W64_B32_ncu_stderr.log" \
  "the unprivileged denial was not captured synchronously"
assert_contains 'NCU sudo retry succeeded' "${TMP_ROOT}/auto.stderr" \
  "the automatic sudo retry did not complete"
assert_contains '^mode=auto_sudo$' "${AUTO_OUT}/ncu_permission_mode.txt" \
  "the permission mode was not recorded as auto_sudo"
assert_nonempty "${AUTO_OUT}/clocked_empty_W64_B32.ncu-rep" \
  "the automatic sudo retry produced no report"

SINGLE_OUT="${TMP_ROOT}/single"
env \
  NCU="${FAKE_NCU}" \
  NCU_SUDO="${FAKE_SUDO} -E" \
  NCU_AUTO_SUDO=1 \
  BIN="${TMP_ROOT}/fake_binary" \
  OUTDIR="${SINGLE_OUT}" \
  TARGET_PROFILE=v100 \
  NCU_CHIP=gv100 \
  GPU=0 \
  ACTIVE_SM=80 \
  BLOCKS_PER_SM=32 \
  MODE=clocked_empty \
  bash "${ROOT}/scripts/run_ncu.sh" > "${TMP_ROOT}/single.stdout" 2> "${TMP_ROOT}/single.stderr"
assert_contains 'ERR_NVGPUCTRPERM' "${SINGLE_OUT}/ncu_clocked_empty_W128_B32_SM80_GPU0_ncu_stderr.log" \
  "the single-case wrapper did not capture the unprivileged denial"
assert_contains 'NCU sudo retry succeeded' "${TMP_ROOT}/single.stderr" \
  "the single-case wrapper did not complete its sudo retry"
assert_nonempty "${SINGLE_OUT}/ncu_clocked_empty_W128_B32_SM80_GPU0.ncu-rep" \
  "the single-case wrapper produced no report after sudo retry"

EXPLICIT_OUT="${TMP_ROOT}/explicit"
env "${COMMON_ENV[@]}" NCU_USE_SUDO=1 NCU_AUTO_SUDO=0 OUTDIR="${EXPLICIT_OUT}" \
  bash "${ROOT}/scripts/run_ncu_validation.sh" > "${TMP_ROOT}/explicit.stdout" 2> "${TMP_ROOT}/explicit.stderr"
assert_contains '^mode=explicit_sudo$' "${EXPLICIT_OUT}/ncu_permission_mode.txt" \
  "explicit NCU_USE_SUDO=1 was not recorded"
assert_not_contains 'ERR_NVGPUCTRPERM' "${EXPLICIT_OUT}/clocked_empty_W64_B32_ncu_stderr.log" \
  "explicit NCU_USE_SUDO=1 unexpectedly started unprivileged"
assert_nonempty "${EXPLICIT_OUT}/clocked_empty_W64_B32.ncu-rep" \
  "explicit NCU_USE_SUDO=1 produced no report"

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
assert_contains '^mode=unprivileged$' "${NO_AUTO_OUT}/ncu_permission_mode.txt" \
  "NCU_AUTO_SUDO=0 did not remain unprivileged"

echo "NCU permission fallback self-test passed"
