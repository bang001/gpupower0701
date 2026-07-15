#!/usr/bin/env python3
"""Audit active documentation, profile facts, and archive boundaries."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any


EXPECTED_PROFILES: dict[str, dict[str, Any]] = {
    "rtx3090": {
        "cpp_name": "Rtx3090",
        "cuda_arch": 86,
        "full_sm": 82,
        "max_blocks_per_sm": 16,
        "combined_l1_shared_kib": 128,
        "shared_kib": 100,
        "max_shared_per_block_kib": 99,
        "l2_mib": 6,
        "power_semantics": "one_sec_average",
    },
    "v100": {
        "cpp_name": "V100",
        "cuda_arch": 70,
        "full_sm": 80,
        "max_blocks_per_sm": 32,
        "combined_l1_shared_kib": 128,
        "shared_kib": 96,
        "max_shared_per_block_kib": 96,
        "l2_mib": 6,
        "power_semantics": "instant",
    },
    "a100": {
        "cpp_name": "A100",
        "cuda_arch": 80,
        "full_sm": 108,
        "max_blocks_per_sm": 32,
        "combined_l1_shared_kib": 192,
        "shared_kib": 164,
        "max_shared_per_block_kib": 163,
        "l2_mib": 40,
        "power_semantics": "instant",
    },
    "h100": {
        "cpp_name": "H100",
        "cuda_arch": 90,
        "full_sm": 132,
        "max_blocks_per_sm": 32,
        "combined_l1_shared_kib": 256,
        "shared_kib": 228,
        "max_shared_per_block_kib": 227,
        "l2_mib": 50,
        "power_semantics": "one_sec_average",
    },
}

CANONICAL_FILES = (
    "README.md",
    "SKILL.md",
    "docs/README.md",
    "docs/methodology/howitworks.md",
    "docs/methodology/component_energy_final_experiment_plan_ko.md",
    "docs/methodology/component_energy_method_comparison_ko.md",
    "docs/methodology/ncu_validation_energy_calculation_ko.md",
    "docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md",
    "docs/results/gpu_power_modeling_experiment_results_ko.md",
    "docs/platforms/cross_platform_component_experiment_guide_ko.md",
    "docs/platforms/a100_node_experiment_guide_ko.md",
    "docs/platforms/v100_node_experiment_guide_ko.md",
    "docs/platforms/h100_node_experiment_guide_ko.md",
    "docs/platforms/power_measurement_api_matrix_ko.md",
    "docs/audits/component_energy_self_critique_ko.md",
    "docs/audits/current_goal_alignment_audit_ko.md",
)

FORBIDDEN_ACTIVE_TERMS = {
    "docs/a100_fp16_energy_experiment_design_v2.md": "superseded design path",
    "docs/cross_platform_component_experiment_guide_ko.md": "pre-classification path",
    "docs/component_energy_final_experiment_plan_ko.md": "pre-classification path",
    "docs/component_energy_self_critique_ko.md": "pre-classification path",
    "docs/a100_node_experiment_guide_ko.md": "pre-classification path",
    "docs/v100_node_experiment_guide_ko.md": "pre-classification path",
    "docs/h100_node_experiment_guide_ko.md": "pre-classification path",
}

REQUIRED_POLICY_TERMS = {
    "README.md": (
        "rtx3090_strict_scope_fresh_ncu_component_coefficients_20260714.md",
        "component_energy_goal_readiness_audit_20260715.md",
    ),
    "SKILL.md": (
        "docs/methodology/howitworks.md",
        "docs/platforms/cross_platform_component_experiment_guide_ko.md",
        "--shared-pair-policy",
        "--l2-pair-policy",
        "shared_scalar_addr_only",
    ),
    "docs/methodology/component_energy_method_comparison_ko.md": (
        "Tensor와 모든 memory pair",
        "matched_iters_net_energy",
        "L2 CG - address control",
    ),
    "docs/methodology/howitworks.md": (
        "GA[global_addr_only",
        "GA --> L1[global_l1_load_only",
        "GA --> L2[l2_cg_load_only",
        "GA --> DR[dram_cg_load_only",
        "srcunit_ltcfabric",
        "logical final L2 hit",
    ),
    "docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md": (
        "l2_logical_read_hit_rate_pct",
        "l2_native_vs_fabric_model_hit_delta_pct",
        "Not pure silicon-level energy",
        "W_SM = 16, 128",
    ),
    "docs/results/gpu_power_modeling_experiment_results_ko.md": (
        "180/180 valid",
        "24.949 pJ/bit",
    ),
    "docs/audits/component_energy_self_critique_ko.md": (
        "RTX 3090은 2026-07-14 v5 package",
        "모든 final pair의 matched ITER",
    ),
    "scripts/plan_platform_component_experiment.py": (
        "Shared scalar energy rows use",
        "--shared-pair-policy",
        "--l2-pair-policy",
        "matched-iters",
        "Partition-fabric profiles apply 95% to final service after LTC-fabric recovery",
    ),
    "scripts/run_ncu_validation.sh": (
        "lts__t_sectors_srcunit_ltcfabric_op_read",
        "lts__t_sectors_srcunit_ltcfabric_aperture_device_op_read",
    ),
    "scripts/summarize_ncu_cache_metrics.py": (
        "l2_logical_read_hit_rate_pct",
        "l2_native_vs_fabric_model_hit_delta_pct",
    ),
    "scripts/build_platform_intake_dashboard.py": (
        "historical_local_evidence",
        "historical_pass",
        "--goal-readiness-csv",
        'row["package_status"] == "pass"',
    ),
    "scripts/run_local_readiness_checks.sh": (
        'READINESS_TAG="${READINESS_TAG:-20260715}"',
        '--goal-readiness-csv "results/summary/component_energy_goal_readiness_audit_${READINESS_TAG}.csv"',
    ),
}

FORBIDDEN_POLICY_PATTERNS = (
    re.compile(r"L2 CG hit path[^\n]*elapsed-aware control-power"),
    re.compile(r"Tensor와 DRAM은 동일 ITER"),
    re.compile(r"Shared/Global L1/L2는[^\n]*elapsed-aware"),
    re.compile(r"Shared scalar path[^\n]*elapsed-aware control-power"),
)

CURRENT_TENSOR_REVISION = (
    "matched_runtime_clock_observed_control_fixed_rf_v6"
)
SUPERSEDED_TENSOR_REVISION = (
    "matched_inplace_signflip_fragment_epilogue_fixed_rf_v4"
)
TENSOR_REVISION_FILES = (
    "README.md",
    "src/main.cu",
    "scripts/plan_platform_component_experiment.py",
    "docs/platforms/a100_node_experiment_guide_ko.md",
    "docs/platforms/v100_node_experiment_guide_ko.md",
    "docs/platforms/h100_node_experiment_guide_ko.md",
)

EXPECTED_CPP_MODES = (
    "idle",
    "empty",
    "clocked_empty",
    "reg_fragment_only",
    "reg_operand_only",
    "reg_mma",
    "reg_pressure",
    "addr_only",
    "global_addr_only",
    "global_l1_load_only",
    "shared_scalar_addr_only",
    "shared_scalar_load_only",
    "shared_load_only",
    "shared_mma",
    "l2_load_only",
    "l2_cg_load_only",
    "l2_mma",
    "dram_load_only",
    "dram_cg_load_only",
    "dram_mma",
    "store_only",
    "store_path",
)

PRIMARY_MODES = (
    "clocked_empty",
    "reg_operand_only",
    "reg_mma",
    "global_addr_only",
    "shared_scalar_addr_only",
    "shared_scalar_load_only",
    "global_l1_load_only",
    "l2_cg_load_only",
    "dram_cg_load_only",
)

DIAGNOSTIC_MODES = tuple(
    mode for mode in EXPECTED_CPP_MODES if mode not in PRIMARY_MODES
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_cpp_modes(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"enum\s+class\s+Mode\s*\{(?P<body>.*?)\};", text, re.S)
    if not match:
        raise ValueError(f"Mode enum not found in {path}")
    modes: list[str] = []
    for item in match.group("body").split(","):
        name = item.strip().split("=", 1)[0].strip()
        if name:
            modes.append(name)
    return modes


def add(
    rows: list[dict[str, str]],
    *,
    area: str,
    check: str,
    status: str,
    expected: str,
    actual: str,
    evidence: str,
    action: str = "",
) -> None:
    rows.append(
        {
            "area": area,
            "check": check,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "action": action,
        }
    )


def active_markdown_files(repo: Path) -> list[Path]:
    files = [repo / "README.md", repo / "SKILL.md"]
    files.extend(sorted((repo / "docs").rglob("*.md")))
    return [path for path in files if path.exists()]


def archive_markdown_files(repo: Path) -> list[Path]:
    return sorted((repo / "archive").rglob("*.md"))


def markdown_targets(text: str) -> list[tuple[int, str]]:
    targets: list[tuple[int, str]] = []
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)\n]+)\)", text):
        raw = match.group(1).strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if ' "' in raw:
            raw = raw.split(' "', 1)[0]
        targets.append((text.count("\n", 0, match.start()) + 1, raw))
    return targets


def audit_links(repo: Path, rows: list[dict[str, str]]) -> None:
    broken: list[str] = []
    checked = 0
    for path in active_markdown_files(repo):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line, raw in markdown_targets(text):
            if raw.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = urllib.parse.unquote(raw).split("#", 1)[0]
            if not target:
                continue
            checked += 1
            candidate = Path(target)
            resolved = candidate if candidate.is_absolute() else path.parent / candidate
            if not resolved.exists():
                broken.append(f"{path.relative_to(repo)}:{line}:{raw}")
    add(
        rows,
        area="links",
        check="active_markdown_local_links",
        status="pass" if not broken else "fail",
        expected="all local Markdown links resolve",
        actual=f"checked={checked}" if not broken else ";".join(broken[:20]),
        evidence="README.md;SKILL.md;docs/**/*.md",
        action="repair or archive documents with broken local links",
    )


def audit_archive_links(repo: Path, rows: list[dict[str, str]]) -> None:
    broken: list[str] = []
    checked = 0
    for path in archive_markdown_files(repo):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line, raw in markdown_targets(text):
            if raw.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = urllib.parse.unquote(raw).split("#", 1)[0]
            if not target:
                continue
            checked += 1
            candidate = Path(target)
            resolved = candidate if candidate.is_absolute() else path.parent / candidate
            if not resolved.exists():
                broken.append(f"{path.relative_to(repo)}:{line}:{raw}")
    add(
        rows,
        area="links",
        check="archive_markdown_local_links",
        status="pass" if not broken else "fail",
        expected="all preserved archive Markdown links resolve",
        actual=f"checked={checked}" if not broken else ";".join(broken[:20]),
        evidence="archive/**/*.md",
        action="repair relative links without changing archived experimental claims",
    )


def audit_inventory(repo: Path, rows: list[dict[str, str]]) -> None:
    missing = [path for path in CANONICAL_FILES if not (repo / path).exists()]
    add(
        rows,
        area="inventory",
        check="canonical_active_documents",
        status="pass" if not missing else "fail",
        expected=f"{len(CANONICAL_FILES)} canonical files",
        actual="all present" if not missing else "missing:" + ",".join(missing),
        evidence="docs/README.md",
        action="restore the canonical document or update the documented map",
    )

    superseded_active = repo / "docs/design/a100_fp16_energy_experiment_design_v2.md"
    superseded_archive = (
        repo
        / "archive/superseded_v2_design_20260714/docs/design/"
        "a100_fp16_energy_experiment_design_v2.md"
    )
    ok = not superseded_active.exists() and superseded_archive.exists()
    add(
        rows,
        area="inventory",
        check="superseded_v2_design_archived",
        status="pass" if ok else "fail",
        expected="design absent from active docs and preserved in archive",
        actual=f"active={superseded_active.exists()},archive={superseded_archive.exists()}",
        evidence=f"{superseded_active.relative_to(repo)};{superseded_archive.relative_to(repo)}",
        action="move the superseded v2 design and its assets to the dated archive",
    )


def audit_policy_text(repo: Path, rows: list[dict[str, str]]) -> None:
    active_text_by_path: dict[str, str] = {}
    for path in active_markdown_files(repo):
        active_text_by_path[str(path.relative_to(repo))] = path.read_text(
            encoding="utf-8", errors="replace"
        )

    stale_paths: list[str] = []
    for relative, text in active_text_by_path.items():
        for term, reason in FORBIDDEN_ACTIVE_TERMS.items():
            if term in text:
                stale_paths.append(f"{relative}:{term}:{reason}")
    add(
        rows,
        area="policy",
        check="no_stale_active_document_paths",
        status="pass" if not stale_paths else "fail",
        expected="classified docs paths or explicit archive paths only",
        actual="none" if not stale_paths else ";".join(stale_paths[:20]),
        evidence="README.md;SKILL.md;docs/**/*.md",
        action="replace old root-level docs paths with current classified paths",
    )

    all_active_text = "\n".join(active_text_by_path.values())
    stale_policy = [
        pattern.pattern
        for pattern in FORBIDDEN_POLICY_PATTERNS
        if pattern.search(all_active_text)
    ]
    add(
        rows,
        area="policy",
        check="no_superseded_l2_energy_policy",
        status="pass" if not stale_policy else "fail",
        expected="L2 final rows use equal ITER and direct net-energy subtraction",
        actual="none" if not stale_policy else ";".join(stale_policy),
        evidence="README.md;SKILL.md;docs/**/*.md",
        action="remove duration-scaled L2 final-policy statements",
    )

    revision_missing: list[str] = []
    revision_stale: list[str] = []
    for relative in TENSOR_REVISION_FILES:
        path = repo / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        if CURRENT_TENSOR_REVISION not in text:
            revision_missing.append(relative)
        if SUPERSEDED_TENSOR_REVISION in text:
            revision_stale.append(relative)
    revision_ok = not revision_missing and not revision_stale
    add(
        rows,
        area="policy",
        check="current_tensor_revision_v6",
        status="pass" if revision_ok else "fail",
        expected=(
            f"{CURRENT_TENSOR_REVISION} present and superseded exact v4 marker absent"
        ),
        actual=(
            "all current"
            if revision_ok
            else f"missing={revision_missing};stale={revision_stale}"
        ),
        evidence=";".join(TENSOR_REVISION_FILES),
        action="synchronize source, planner, README, and node guides to Tensor v6",
    )

    for relative, terms in REQUIRED_POLICY_TERMS.items():
        path = repo / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [term for term in terms if term not in text]
        add(
            rows,
            area="policy",
            check=f"required_terms:{relative}",
            status="pass" if not missing else "fail",
            expected=";".join(terms),
            actual="all present" if not missing else "missing:" + ";".join(missing),
            evidence=relative,
            action="synchronize the document with the current generated finalplan",
        )


def parse_cpp_profiles(path: Path) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    parsed: dict[str, dict[str, Any]] = {}
    for profile, expected in EXPECTED_PROFILES.items():
        match = re.search(
            rf"constexpr HardwareProfile k{expected['cpp_name']}Profile\{{(.*?)\}};",
            text,
            re.DOTALL,
        )
        if not match:
            continue
        values = next(csv.reader([match.group(1).replace("\n", " ")], skipinitialspace=True))
        values = [value.strip().strip('"') for value in values]
        if len(values) < 22:
            continue
        parsed[profile] = {
            "cuda_arch": int(values[3]),
            "full_sm": int(values[6]),
            "max_blocks_per_sm": int(values[7]),
            "combined_l1_shared_kib": int(values[10]),
            "shared_kib": int(values[11]),
            "max_shared_per_block_kib": int(values[12]),
            "l2_mib": int(values[13]),
            "power_semantics": values[21],
        }
    return parsed


def audit_profiles(repo: Path, rows: list[dict[str, str]]) -> None:
    scripts_dir = repo / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    sweep = load_module(scripts_dir / "run_sweep.py", "doc_audit_run_sweep")
    plan = load_module(
        scripts_dir / "plan_platform_component_experiment.py", "doc_audit_plan"
    )
    preflight = load_module(
        scripts_dir / "preflight_gpu_support.py", "doc_audit_preflight"
    )
    cpp = parse_cpp_profiles(repo / "include/config.hpp")

    for profile, expected in EXPECTED_PROFILES.items():
        sources: dict[str, dict[str, Any]] = {
            "include/config.hpp": cpp.get(profile, {}),
            "scripts/run_sweep.py": {
                "full_sm": sweep.PROFILES.get(profile, {}).get("full_sm"),
                "max_blocks_per_sm": sweep.PROFILES.get(profile, {}).get(
                    "max_blocks_per_sm"
                ),
                "shared_kib": sweep.PROFILES.get(profile, {}).get(
                    "shared_capacity_per_sm_kib"
                ),
                "max_shared_per_block_kib": sweep.PROFILES.get(profile, {}).get(
                    "max_shared_per_block_kib"
                ),
                "l2_mib": sweep.PROFILES.get(profile, {}).get("l2_mib"),
            },
            "scripts/preflight_gpu_support.py": {
                "cuda_arch": int(preflight.PROFILES.get(profile, {}).get("cuda_arch", -1)),
                "full_sm": preflight.PROFILES.get(profile, {}).get("full_sm"),
                "max_blocks_per_sm": preflight.PROFILES.get(profile, {}).get(
                    "max_blocks_per_sm"
                ),
                "combined_l1_shared_kib": preflight.PROFILES.get(profile, {}).get(
                    "combined_l1_shared_kib"
                ),
                "shared_kib": preflight.PROFILES.get(profile, {}).get("shared_kib"),
                "max_shared_per_block_kib": preflight.PROFILES.get(profile, {}).get(
                    "max_shared_per_block_kib"
                ),
                "l2_mib": preflight.PROFILES.get(profile, {}).get("l2_mib"),
                "power_semantics": preflight.PROFILES.get(profile, {}).get(
                    "power_usage_semantics"
                ),
            },
            "scripts/plan_platform_component_experiment.py": {
                "cuda_arch": int(plan.PROFILES.get(profile, {}).get("cuda_arch", -1)),
                "full_sm": plan.PROFILES.get(profile, {}).get("active_sm"),
                "shared_kib": plan.PROFILES.get(profile, {}).get("shared_capacity_kib"),
                "l2_mib": plan.PROFILES.get(profile, {}).get("l2_mib"),
                "power_semantics": plan.PROFILES.get(profile, {}).get("power_semantics"),
            },
        }
        problems: list[str] = []
        compared = 0
        for source, actual in sources.items():
            if not actual:
                problems.append(f"{source}:profile_missing")
                continue
            for key, value in actual.items():
                if value is None:
                    problems.append(f"{source}:{key}=missing")
                    continue
                compared += 1
                if str(value) != str(expected[key]):
                    problems.append(
                        f"{source}:{key}={value},expected={expected[key]}"
                    )
        add(
            rows,
            area="profiles",
            check=f"{profile}_profile_consistency",
            status="pass" if not problems else "fail",
            expected="C++/sweep/preflight/planner values match canonical profile facts",
            actual=f"compared={compared}" if not problems else ";".join(problems),
            evidence="include/config.hpp;scripts/run_sweep.py;scripts/preflight_gpu_support.py;scripts/plan_platform_component_experiment.py",
            action="update all profile definitions together",
        )


def audit_modes(repo: Path, rows: list[dict[str, str]]) -> None:
    actual = parse_cpp_modes(repo / "include/config.hpp")
    expected = list(EXPECTED_CPP_MODES)
    add(
        rows,
        area="modes",
        check="cpp_mode_inventory",
        status="pass" if actual == expected else "fail",
        expected=",".join(expected),
        actual=",".join(actual),
        evidence="include/config.hpp",
        action="classify any mode addition/removal in README, SKILL, planner, and NCU flow",
    )

    primary_sources = (
        "README.md",
        "SKILL.md",
        "scripts/plan_platform_component_experiment.py",
        "scripts/run_ncu_validation.sh",
    )
    primary_missing: list[str] = []
    for relative in primary_sources:
        text = (repo / relative).read_text(encoding="utf-8", errors="replace")
        for mode in PRIMARY_MODES:
            if mode not in text:
                primary_missing.append(f"{relative}:{mode}")
    add(
        rows,
        area="modes",
        check="primary_mode_integration",
        status="pass" if not primary_missing else "fail",
        expected="all primary modes documented and wired into planner/NCU sidecar",
        actual="complete" if not primary_missing else ";".join(primary_missing),
        evidence=";".join(primary_sources),
        action="keep primary treatment and control modes synchronized",
    )

    diagnostic_sources = ("README.md", "SKILL.md")
    diagnostic_missing: list[str] = []
    for relative in diagnostic_sources:
        text = (repo / relative).read_text(encoding="utf-8", errors="replace")
        for mode in DIAGNOSTIC_MODES:
            if mode not in text:
                diagnostic_missing.append(f"{relative}:{mode}")
    add(
        rows,
        area="modes",
        check="diagnostic_mode_classification",
        status="pass" if not diagnostic_missing else "fail",
        expected="all non-primary C++ modes explicitly classified",
        actual="complete" if not diagnostic_missing else ";".join(diagnostic_missing),
        evidence="README.md;SKILL.md",
        action="classify the mode as support/diagnostic/legacy or promote it through all gates",
    )


def audit_assets(repo: Path, rows: list[dict[str, str]]) -> None:
    asset_root = repo / "docs/assets/component_energy_method"
    searchable = [
        *active_markdown_files(repo),
        *sorted((repo / "scripts").glob("*.py")),
        *sorted((repo / "results/summary").glob("*.md")),
    ]
    texts = {
        path: path.read_text(encoding="utf-8", errors="replace") for path in searchable
    }
    orphaned: list[str] = []
    for asset in sorted(asset_root.glob("*")):
        if not asset.is_file() or asset.name == "README.md":
            continue
        directly_used = any(asset.name in text for text in texts.values())
        sibling_used = any(
            sibling.name != asset.name
            and sibling.stem == asset.stem
            and any(sibling.name in text for text in texts.values())
            for sibling in asset_root.glob(f"{asset.stem}.*")
        )
        if not directly_used and not sibling_used:
            orphaned.append(str(asset.relative_to(repo)))
    add(
        rows,
        area="assets",
        check="active_component_assets_referenced",
        status="pass" if not orphaned else "fail",
        expected="every active asset is referenced directly or is a paired source/render",
        actual="all referenced" if not orphaned else ";".join(orphaned),
        evidence="docs/assets/component_energy_method",
        action="move obsolete figures to the dated pre-current-protocol archive",
    )


def write_outputs(
    rows: list[dict[str, str]], csv_path: Path, md_path: Path
) -> tuple[int, int]:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["area", "check", "status", "expected", "actual", "evidence", "action"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    failures = sum(row["status"] == "fail" for row in rows)
    passes = sum(row["status"] == "pass" for row in rows)
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write("# Documentation Consistency Audit\n\n")
        handle.write(f"- Checks: {len(rows)}\n- Pass: {passes}\n- Fail: {failures}\n\n")
        handle.write("| Area | Check | Status | Actual | Evidence |\n")
        handle.write("|---|---|---|---|---|\n")
        for row in rows:
            actual = row["actual"].replace("|", "\\|").replace("\n", " ")
            handle.write(
                f"| {row['area']} | `{row['check']}` | **{row['status']}** | "
                f"{actual} | `{row['evidence']}` |\n"
            )
        if failures:
            handle.write("\n## Required Actions\n\n")
            for row in rows:
                if row["status"] == "fail":
                    handle.write(f"- `{row['check']}`: {row['action']}\n")
    return passes, failures


def run_audit(repo: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    audit_links(repo, rows)
    audit_archive_links(repo, rows)
    audit_inventory(repo, rows)
    audit_policy_text(repo, rows)
    audit_profiles(repo, rows)
    audit_modes(repo, rows)
    audit_assets(repo, rows)
    return rows


def self_test() -> None:
    sample = "[ok](docs/a.md) ![image](assets/a.png) [web](https://example.com)"
    assert markdown_targets(sample) == [
        (1, "docs/a.md"),
        (1, "assets/a.png"),
        (1, "https://example.com"),
    ]
    with tempfile.TemporaryDirectory(prefix="doc_audit_selftest_") as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "include/config.hpp").write_text(
            'constexpr HardwareProfile kV100Profile{"v100","volta","gv100",70,7,0,80,32,64,2048,128,96,96,6,false,false,false,false,"implemented:fp16_wmma","gv100","gv100_required","instant"};\n'
            'enum class Mode { idle, empty, clocked_empty };\n',
            encoding="utf-8",
        )
        parsed = parse_cpp_profiles(root / "include/config.hpp")
        assert parsed["v100"]["full_sm"] == 80
        assert parsed["v100"]["shared_kib"] == 96
        assert parsed["v100"]["power_semantics"] == "instant"
        assert parse_cpp_modes(root / "include/config.hpp") == [
            "idle",
            "empty",
            "clocked_empty",
        ]
    print("documentation consistency audit self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--out-csv",
        default="results/summary/documentation_consistency_audit_20260714.csv",
    )
    parser.add_argument(
        "--out-md",
        default="results/summary/documentation_consistency_audit_20260714.md",
    )
    parser.add_argument("--fail-on-error", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    repo = Path(args.repo).resolve()
    rows = run_audit(repo)
    passes, failures = write_outputs(rows, Path(args.out_csv), Path(args.out_md))
    print(f"documentation consistency: pass={passes} fail={failures}")
    if failures and args.fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
