#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-20260708}"
READINESS_TAG="${READINESS_TAG:-20260714}"
NCU_BIN="${NCU:-}"

if [[ -z "${NCU_BIN}" ]]; then
  if [[ -x /tmp/ncu2025/target/linux-desktop-glibc_2_11_3-x64/ncu ]]; then
    NCU_BIN=/tmp/ncu2025/target/linux-desktop-glibc_2_11_3-x64/ncu
  elif command -v ncu >/dev/null 2>&1; then
    NCU_BIN="$(command -v ncu)"
  else
    NCU_BIN=ncu
  fi
fi

echo "[readiness] tag=${TAG}"
echo "[readiness] report_tag=${READINESS_TAG}"
echo "[readiness] ncu=${NCU_BIN}"

echo "[readiness] python syntax"
python3 -m py_compile \
  scripts/audit_platform_result_package.py \
  scripts/selftest_platform_package_gates.py \
  scripts/summarize_platform_package_gaps.py \
  scripts/build_platform_intake_dashboard.py \
  scripts/write_platform_result_manifest.py \
  scripts/audit_platform_power_readiness.py \
  scripts/preflight_gpu_support.py \
  scripts/audit_power_api_measurements.py \
  scripts/audit_power_state_stability.py \
  scripts/summarize_ncu_cache_metrics.py \
  scripts/analyze_ncu_path_acceptance.py \
  scripts/analyze_matched_control_energy.py \
  scripts/summarize_matched_control_by_factor.py \
  scripts/run_component_regression_sweep.py \
  scripts/run_paired_component_stability.py \
  scripts/audit_component_reliability.py \
  scripts/audit_matched_control_instability.py \
  scripts/audit_a100_ncu_precheck.py \
  scripts/audit_a100_tensor_l2_remediation.py \
  scripts/select_l2_path_configuration.py \
  scripts/select_a100_l2_path_configuration.py \
  scripts/audit_component_goal_readiness.py \
  scripts/build_strict_component_summary.py \
  scripts/audit_strict_component_summary.py \
  scripts/plan_platform_component_experiment.py \
  scripts/audit_documentation_consistency.py \
  scripts/plot_platform_sweep_design.py \
  scripts/plot_dram_reporting_policy.py \
  scripts/build_gpu_component_energy_presentation.py

echo "[readiness] package/gap/dashboard/manifest self-tests"
python3 scripts/preflight_gpu_support.py --self-test
python3 scripts/audit_power_api_measurements.py --self-test
python3 scripts/run_component_regression_sweep.py --self-test
python3 scripts/summarize_ncu_cache_metrics.py --self-test
python3 scripts/analyze_ncu_path_acceptance.py --self-test
python3 scripts/analyze_matched_control_energy.py --self-test
python3 scripts/audit_a100_ncu_precheck.py --self-test
python3 scripts/audit_a100_tensor_l2_remediation.py --self-test
python3 scripts/select_l2_path_configuration.py --self-test
python3 scripts/build_strict_component_summary.py --self-test
python3 scripts/audit_strict_component_summary.py --self-test
python3 scripts/selftest_platform_package_gates.py
bash scripts/selftest_ncu_permission_fallback.sh
python3 scripts/audit_component_goal_readiness.py --self-test
python3 scripts/write_platform_result_manifest.py --self-test
python3 scripts/summarize_platform_package_gaps.py --self-test
python3 scripts/build_platform_intake_dashboard.py --self-test
python3 scripts/audit_documentation_consistency.py --self-test
python3 scripts/plot_platform_sweep_design.py --self-test
python3 scripts/plot_dram_reporting_policy.py --self-test

echo "[readiness] generated command shell syntax"
for profile in a100 v100 h100; do
  shell_path="results/summary/${profile}_component_finalplan_${TAG}_commands.sh"
  if [[ -f "${shell_path}" ]]; then
    bash -n "${shell_path}"
  fi
done

echo "[readiness] active documentation consistency"
python3 scripts/audit_documentation_consistency.py \
  --out-csv "results/summary/documentation_consistency_audit_${READINESS_TAG}.csv" \
  --out-md "results/summary/documentation_consistency_audit_${READINESS_TAG}.md" \
  --fail-on-error

echo "[readiness] platform power readiness"
python3 scripts/audit_platform_power_readiness.py \
  --out-csv "results/summary/platform_power_readiness_audit_${TAG}.csv" \
  --out-md "results/summary/platform_power_readiness_audit_${TAG}.md"

echo "[readiness] external platform manifests, package audits, and gap reports"
for profile in a100 v100 h100; do
  case "${profile}" in
    a100) active_sm="${A100_ACTIVE_SM:-108}" ;;
    v100) active_sm="${V100_ACTIVE_SM:-80}" ;;
    h100) active_sm="${H100_ACTIVE_SM:-132}" ;;
    *) echo "unknown profile: ${profile}" >&2; exit 1 ;;
  esac
  python3 scripts/write_platform_result_manifest.py \
    --target-profile "${profile}" \
    --tag "${TAG}" \
    --expected-active-sm "${active_sm}" \
    --out-csv "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv" \
    --out-md "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.md"
  python3 scripts/audit_platform_result_package.py \
    --target-profile "${profile}" \
    --tag "${TAG}" \
    --expected-active-sm "${active_sm}" \
    --out-csv "results/summary/${profile}_platform_result_package_audit_${TAG}.csv" \
    --out-md "results/summary/${profile}_platform_result_package_audit_${TAG}.md"
  python3 scripts/summarize_platform_package_gaps.py \
    --target-profile "${profile}" \
    --tag "${TAG}" \
    --audit-csv "results/summary/${profile}_platform_result_package_audit_${TAG}.csv" \
    --manifest-csv "results/summary/${profile}_component_finalplan_${TAG}_result_manifest.csv" \
    --out-csv "results/summary/${profile}_platform_result_package_gaps_${TAG}.csv" \
    --out-md "results/summary/${profile}_platform_result_package_gaps_${TAG}.md"
done

echo "[readiness] RTX 3090 strict summary audit"
set +e
python3 scripts/audit_strict_component_summary.py \
  --summary-csv "results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_${TAG}.csv" \
  --expected-power-semantics one_sec_average \
  --require-path-specific-cache-evidence \
  --out-csv "results/summary/rtx3090_current_protocol_reaudit_${READINESS_TAG}.csv" \
  --out-md "results/summary/rtx3090_current_protocol_reaudit_${READINESS_TAG}.md" \
  --fail-on-fail
RTX_AUDIT_RC=$?
set -e
if [[ "${RTX_AUDIT_RC}" -ne 0 ]]; then
  echo "[readiness] RTX 3090 historical result fails the current protocol; continuing to write complete readiness reports" >&2
fi

echo "[readiness] goal readiness"
python3 scripts/audit_component_goal_readiness.py \
  --ncu "${NCU_BIN}" \
  --out-csv "results/summary/component_energy_goal_readiness_audit_${READINESS_TAG}.csv" \
  --out-md "results/summary/component_energy_goal_readiness_audit_${READINESS_TAG}.md"

echo "[readiness] platform intake dashboard"
python3 scripts/build_platform_intake_dashboard.py \
  --tag "${TAG}" \
  --goal-readiness-csv "results/summary/component_energy_goal_readiness_audit_${READINESS_TAG}.csv" \
  --out-csv "results/summary/platform_component_intake_dashboard_${TAG}.csv" \
  --out-md "results/summary/platform_component_intake_dashboard_${TAG}.md"

if [[ "${RUN_GIT_DIFF_CHECK:-1}" == "1" ]]; then
  echo "[readiness] git diff --check"
  git diff --check
fi

echo "[readiness] done"
exit "${RTX_AUDIT_RC}"
