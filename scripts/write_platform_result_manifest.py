#!/usr/bin/env python3
"""Write expected external-platform result manifest.

The manifest is a transfer checklist for A100/V100/H100/RTX3090 runs. It does
not validate results; `audit_platform_result_package.py` performs validation
after files are copied back.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_PATH = SCRIPT_DIR / "audit_platform_result_package.py"

ARTIFACT_PURPOSES = {
    "command_shell": (
        "generated runnable command package",
        "documents the exact finalplan commands used on the target node",
        "platform_command_package",
    ),
    "command_plan": (
        "generated command plan markdown",
        "records target profile, coordinates, power semantics, NCU and audit gates",
        "platform_command_package",
    ),
    "preflight": (
        "node preflight report",
        "proves GPU/profile, NVML, power scope, NCU availability, and binary dry-run",
        "preflight",
    ),
    "raw": (
        "raw energy CSVs",
        "contains explicit total-energy rows, profile metadata, active SM, W_SM, blocks/SM",
        "raw_energy_profile_and_power",
    ),
    "tensor_pair_calibration": (
        "Tensor pair calibration manifest",
        "proves reg_mma-calibrated ITER was applied identically to treatment and control",
        "tensor_pair_calibration_policy",
    ),
    "power_api": (
        "power API audit",
        "proves final rows use nvml_total_energy + total_energy_mj_delta + GPU/device scope",
        "power_api_final_candidate",
    ),
    "power_state": (
        "power-state stability audit",
        "excludes average-power, endpoint-power, clock, and temperature outlier rows",
        "power_state_quality",
    ),
    "ncu_summary": (
        "NCU counter summary",
        "records L1/L2 hit rates, L1/L2/DRAM bytes/access counts, shared bytes, tensor inst, stalls",
        "ncu_summary_quality",
    ),
    "ncu_acceptance": (
        "NCU path acceptance",
        "proves tensor/control/shared/global-L1/L2 candidates use intended paths",
        "ncu_path_acceptance",
    ),
    "matched_summary": (
        "matched-control summary",
        "summarizes treatment-control delta_E and pJ/FLOP or pJ/bit estimates",
        "matched_control_summary",
    ),
    "matched_detail": (
        "matched-control detail",
        "preserves row-level numerator/control pairing, source files, scopes, and denominators",
        "matched_control_detail",
    ),
    "reliability": (
        "component reliability audit",
        "combines power, NCU, and matched-control evidence into accepted/reject component verdicts",
        "component_reliability",
    ),
    "instability": (
        "instability audit",
        "explains weak-signal, negative, or noisy matched-control rows and follow-up conditions",
        "instability_diagnosis",
    ),
    "strict_summary": (
        "strict component coefficient summary",
        "reporting table built only from accepted reliability evidence",
        "strict_summary_policy",
    ),
    "strict_audit": (
        "strict component summary audit",
        (
            "verifies traceability, power matrix policy, NCU denominator, "
            "counter schema, coordinate alignment, hierarchy, and plausibility gates"
        ),
        "strict_summary_audit_clean",
    ),
}

PROFILE_CUDA_ARCH = {
    "rtx3090": "86",
    "v100": "70",
    "a100": "80",
    "h100": "90",
}

PROFILE_BUILD_DIR = {
    "rtx3090": "build",
    "v100": "build-v100",
    "a100": "build-a100",
    "h100": "build-h100",
}

PROFILE_DEFAULT_BINARY = {
    "rtx3090": "./build/a100_fp16_energy_v2",
    "v100": "./build-v100/a100_fp16_energy_v2",
    "a100": "./build-a100/a100_fp16_energy_v2",
    "h100": "./build-h100/a100_fp16_energy_v2",
}


def load_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location("audit_platform_result_package", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flatten_paths(value: Path | list[Path]) -> list[str]:
    if isinstance(value, list):
        return [str(path) for path in value]
    return [str(value)]


def expected_path_set(module: Any, profile: str, tag: str) -> set[str]:
    paths = module.expected_paths(profile, tag)
    out: set[str] = set()
    for value in paths.values():
        out.update(flatten_paths(value))
    return out


def manifest_rows(
    module: Any,
    *,
    profile: str,
    tag: str,
    expected_active_sm: int,
    expected_sm_count: int | None,
) -> list[dict[str, str]]:
    paths = module.expected_paths(profile, tag)
    metadata = module.PROFILE_METADATA[profile]
    semantics = module.PROFILE_POWER_SEMANTICS[profile]
    cuda_arch = PROFILE_CUDA_ARCH[profile]
    build_dir = PROFILE_BUILD_DIR[profile]
    binary = PROFILE_DEFAULT_BINARY[profile]
    rows: list[dict[str, str]] = []
    for key, value in paths.items():
        group, purpose, gate = ARTIFACT_PURPOSES[key]
        for path in flatten_paths(value):
            rows.append(
                {
                    "profile": profile,
                    "tag": tag,
                    "artifact_key": key,
                    "artifact_group": group,
                    "expected_path": path,
                    "purpose": purpose,
                    "validated_by": gate,
                    "target_chip": metadata["chip"],
                    "target_compute_capability": metadata["compute_capability"],
                    "expected_power_semantics": semantics,
                    "expected_active_sm": str(expected_active_sm),
                    "expected_sm_count": (
                        str(expected_sm_count) if expected_sm_count is not None else ""
                    ),
                    "cuda_arch": cuda_arch,
                    "build_dir": build_dir,
                    "binary": binary,
                    "final_numerator_policy": (
                        "nvml_total_energy + total_energy_mj_delta + "
                        "gpu_device_total_energy_counter"
                    ),
                }
            )
    return rows


def self_test(module: Any) -> None:
    for profile in sorted(module.PROFILE_POWER_SEMANTICS):
        tag = "selftest"
        expected_active_sm = int(module.PROFILE_METADATA[profile]["full_sm"])
        rows = manifest_rows(
            module,
            profile=profile,
            tag=tag,
            expected_active_sm=expected_active_sm,
            expected_sm_count=None,
        )
        manifest_paths = {row["expected_path"] for row in rows}
        expected_paths = expected_path_set(module, profile, tag)
        missing = sorted(expected_paths - manifest_paths)
        extra = sorted(manifest_paths - expected_paths)
        if missing or extra:
            raise AssertionError(
                f"{profile}: manifest mismatch missing={missing} extra={extra}"
            )
        if len(rows) != 19:
            raise AssertionError(f"{profile}: expected 19 artifact rows, got {len(rows)}")
        required_groups = {
            "raw energy CSVs",
            "power API audit",
            "NCU counter summary",
            "strict component summary audit",
        }
        groups = {row["artifact_group"] for row in rows}
        absent = sorted(required_groups - groups)
        if absent:
            raise AssertionError(f"{profile}: missing groups={absent}")
        md_path = Path("/tmp") / f"{profile}_manifest_selftest.md"
        write_md(
            md_path,
            rows,
            profile=profile,
            tag=tag,
            expected_active_sm=expected_active_sm,
            expected_sm_count=None,
        )
        text = md_path.read_text(encoding="utf-8")
        required_terms = [
            "Build Requirement",
            f"CMAKE_CUDA_ARCHITECTURES={PROFILE_CUDA_ARCH[profile]}",
            PROFILE_DEFAULT_BINARY[profile],
            "build_platform_intake_dashboard.py",
            "audit_power_api_measurements.py --self-test",
            "build_strict_component_summary.py --self-test",
            "audit_strict_component_summary.py --self-test",
            "audit_component_goal_readiness.py --self-test",
            "NCU counter schema",
            "coordinate alignment",
            "component_energy_goal_readiness_audit_",
            "summarize_platform_package_gaps.py",
            "--tag selftest",
        ]
        missing_terms = [term for term in required_terms if term not in text]
        if missing_terms:
            raise AssertionError(f"{profile}: missing md terms={missing_terms}")
        goal_pos = text.find("scripts/audit_component_goal_readiness.py \\")
        dashboard_pos = text.find("scripts/build_platform_intake_dashboard.py")
        if goal_pos < 0 or dashboard_pos < 0 or dashboard_pos < goal_pos:
            raise AssertionError(
                f"{profile}: dashboard must be listed after goal readiness "
                f"(goal_pos={goal_pos}, dashboard_pos={dashboard_pos})"
            )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile",
        "tag",
        "artifact_key",
        "artifact_group",
        "expected_path",
        "purpose",
        "validated_by",
        "target_chip",
        "target_compute_capability",
        "expected_power_semantics",
        "expected_active_sm",
        "expected_sm_count",
        "cuda_arch",
        "build_dir",
        "binary",
        "final_numerator_policy",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(
    path: Path,
    rows: list[dict[str, str]],
    *,
    profile: str,
    tag: str,
    expected_active_sm: int,
    expected_sm_count: int | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {profile.upper()} External Result Manifest\n\n")
        f.write("This manifest lists files that should be copied back from the target GPU node.\n")
        f.write("It is a transfer checklist, not a validation result. After copying files, run ")
        f.write("`scripts/audit_platform_result_package.py`.\n\n")
        f.write("| item | value |\n|---|---|\n")
        f.write(f"| profile | `{profile}` |\n")
        f.write(f"| tag | `{tag}` |\n")
        f.write(f"| expected active SM | `{expected_active_sm}` |\n")
        f.write(
            "| expected runtime SM count | "
            f"`{expected_sm_count if expected_sm_count is not None else 'not exact-checked'}` |\n"
        )
        f.write(f"| CUDA arch | `{PROFILE_CUDA_ARCH[profile]}` |\n")
        f.write(f"| build directory | `{PROFILE_BUILD_DIR[profile]}` |\n")
        f.write(f"| binary | `{PROFILE_DEFAULT_BINARY[profile]}` |\n")
        f.write(
            "| final numerator policy | "
            "`nvml_total_energy + total_energy_mj_delta + gpu_device_total_energy_counter` |\n\n"
        )
        f.write("## Build Requirement\n\n")
        f.write("Build the profile-specific binary before running the command package. ")
        f.write("The default `build` directory is RTX 3090/sm_86 only; do not reuse it for A100/V100/H100 results.\n\n")
        f.write("```bash\n")
        f.write(
            f"cmake -S . -B {PROFILE_BUILD_DIR[profile]} "
            f"-DCMAKE_CUDA_ARCHITECTURES={PROFILE_CUDA_ARCH[profile]}\n"
        )
        f.write(f"cmake --build {PROFILE_BUILD_DIR[profile]} -j\n")
        f.write("```\n\n")
        f.write("## Copy Checklist\n\n")
        f.write(
            "| artifact group | expected path | purpose | validated by |\n"
            "|---|---|---|---|\n"
        )
        for row in rows:
            f.write(
                f"| {row['artifact_group']} | `{row['expected_path']}` | "
                f"{row['purpose']} | `{row['validated_by']}` |\n"
            )
        f.write("\n## After Copy\n\n")
        f.write("```bash\n")
        f.write("python3 scripts/audit_platform_result_package.py \\\n")
        f.write(f"  --target-profile {profile} \\\n")
        f.write(f"  --tag {tag} \\\n")
        f.write(f"  --expected-active-sm {expected_active_sm} \\\n")
        if expected_sm_count is not None:
            f.write(f"  --expected-sm-count {expected_sm_count} \\\n")
        f.write(
            f"  --out-csv results/summary/{profile}_platform_result_package_audit_{tag}.csv \\\n"
        )
        f.write(
            f"  --out-md results/summary/{profile}_platform_result_package_audit_{tag}.md \\\n"
        )
        f.write("  --fail-on-incomplete\n")
        f.write("```\n")
        f.write("\nIf the package audit reports `missing` or `fail`, generate a gap report:\n\n")
        f.write("```bash\n")
        f.write("python3 scripts/summarize_platform_package_gaps.py \\\n")
        f.write(f"  --target-profile {profile} \\\n")
        f.write(f"  --tag {tag} \\\n")
        f.write(
            f"  --audit-csv results/summary/{profile}_platform_result_package_audit_{tag}.csv \\\n"
        )
        f.write(
            f"  --manifest-csv results/summary/{profile}_component_finalplan_{tag}_result_manifest.csv \\\n"
        )
        f.write(
            f"  --out-csv results/summary/{profile}_platform_result_package_gaps_{tag}.csv \\\n"
        )
        f.write(
            f"  --out-md results/summary/{profile}_platform_result_package_gaps_{tag}.md\n"
        )
        f.write("```\n")
        f.write("\nRefresh the goal readiness audit and cross-platform dashboard:\n\n")
        f.write("```bash\n")
        f.write("python3 scripts/audit_power_api_measurements.py --self-test\n")
        f.write("python3 scripts/build_strict_component_summary.py --self-test\n")
        f.write("python3 scripts/audit_strict_component_summary.py --self-test\n")
        f.write("python3 scripts/audit_component_goal_readiness.py --self-test\n")
        f.write("python3 scripts/audit_component_goal_readiness.py \\\n")
        f.write("  --ncu \"$(command -v ncu || echo ncu)\" \\\n")
        f.write(
            f"  --out-csv results/summary/component_energy_goal_readiness_audit_{tag}.csv \\\n"
        )
        f.write(
            f"  --out-md results/summary/component_energy_goal_readiness_audit_{tag}.md\n"
        )
        f.write("python3 scripts/build_platform_intake_dashboard.py \\\n")
        f.write(f"  --tag {tag} \\\n")
        f.write(
            f"  --out-csv results/summary/platform_component_intake_dashboard_{tag}.csv \\\n"
        )
        f.write(
            f"  --out-md results/summary/platform_component_intake_dashboard_{tag}.md\n"
        )
        f.write("```\n")
        f.write(
            "\nThe strict summary audit must include NCU counter schema and coordinate "
            "alignment checks. A row is not final if the NCU sidecar validates only "
            "the mode name but was captured with different `W_SM`, `blocks/SM`, "
            "`active_SM`, `reuse_factor`, `load_repeat`, or `store_repeat` values.\n"
        )


def main() -> int:
    module = load_audit_module()
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-profile", choices=sorted(module.PROFILE_POWER_SEMANTICS))
    parser.add_argument("--tag")
    parser.add_argument("--expected-active-sm", type=int, default=0)
    parser.add_argument("--expected-sm-count", type=int, default=0)
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test(module)
        print("platform result manifest self-test passed")
        return 0

    if not args.target_profile:
        parser.error("--target-profile is required unless --self-test is used")
    if not args.tag:
        parser.error("--tag is required unless --self-test is used")

    expected_active_sm = args.expected_active_sm or int(
        module.PROFILE_METADATA[args.target_profile]["full_sm"]
    )
    expected_sm_count = args.expected_sm_count or None
    rows = manifest_rows(
        module,
        profile=args.target_profile,
        tag=args.tag,
        expected_active_sm=expected_active_sm,
        expected_sm_count=expected_sm_count,
    )
    out_csv = Path(
        args.out_csv
        or (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_result_manifest.csv"
        )
    )
    out_md = Path(
        args.out_md
        or (
            f"results/summary/{args.target_profile}_component_finalplan_"
            f"{args.tag}_result_manifest.md"
        )
    )
    write_csv(out_csv, rows)
    write_md(
        out_md,
        rows,
        profile=args.target_profile,
        tag=args.tag,
        expected_active_sm=expected_active_sm,
        expected_sm_count=expected_sm_count,
    )
    print(f"wrote {out_csv}")
    print(f"wrote {out_md}")
    print(f"artifacts={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
