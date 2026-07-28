#!/usr/bin/env python3
"""Bind a passing dynamic NCU audit to a completed stage-ATC run.

The NCU sidecar is instruction evidence only.  This binder verifies its
complete 3-stage capture set, nine control/treatment pairs, summary CSV, exact
frozen-binary identity, and every completed NVML acquisition artifact before
atomically adding one immutable ``ncu_audit`` entry to the run manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "softmax_whole_stage_atc_manifest_v1"
NCU_AUDIT_SCHEMA = "softmax_whole_stage_atc_ncu_audit_v1"
BINARY_CONTRACT_SCHEMA = "softmax_whole_stage_atc_binary_contract_v2"
KERNEL_CONTRACT = "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"
TARGET_PROFILE = "rtx3090"
STAGES = ("exp", "reduction", "normalization")
POLICIES = ("fp32", "fp16_scalar", "fp16x2")
SOFTMAX_COLS = 1024
GRID_BLOCKS = 41
THREADS_PER_BLOCK = 256
ROWS_PER_BLOCK = 2
LAUNCH_COUNT = 18
PAIR_COUNT = 9
CAPTURE_NAMES = ("raw_csv", "ncu_report", "target_stdout", "target_stderr")


class BindingError(RuntimeError):
    """Raised when dynamic evidence cannot be bound without weakening a gate."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BindingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BindingError(f"cannot read {label} JSON {path}: {error}") from error
    require(isinstance(payload, dict), f"{label} must be one JSON object")
    return payload


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), "refusing to write an empty CSV")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(rows[0]), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def require_sha256(value: Any, label: str) -> str:
    text = str(value)
    require(
        len(text) == 64 and all(character in "0123456789abcdef" for character in text),
        f"{label} is not a lowercase SHA-256 digest",
    )
    return text


def relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_manifest_path(value: Any) -> Path:
    require(isinstance(value, str) and bool(value), "manifest artifact path is missing")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def resolve_audit_path(value: Any, audit_path: Path) -> Path:
    require(isinstance(value, str) and bool(value), "audit artifact path is missing")
    path = Path(value)
    require(
        not path.is_absolute(),
        "audit artifact path must be relative to audit.json for portability",
    )
    return (audit_path.parent / path).resolve()


def verify_file_metadata(
    metadata: Any,
    *,
    label: str,
    base: str,
    audit_path: Path | None = None,
    require_bytes: bool = False,
) -> tuple[Path, str, int]:
    require(isinstance(metadata, dict), f"{label} metadata is missing")
    assert isinstance(metadata, dict)
    path = (
        resolve_manifest_path(metadata.get("path"))
        if base == "manifest"
        else resolve_audit_path(metadata.get("path"), audit_path or Path.cwd())
    )
    digest = require_sha256(metadata.get("sha256"), f"{label} sha256")
    require(path.is_file(), f"{label} file is missing: {path}")
    require(sha256_file(path) == digest, f"{label} file hash mismatch")
    byte_count = path.stat().st_size
    if require_bytes:
        try:
            recorded_bytes = int(metadata.get("bytes", -1))
        except (TypeError, ValueError) as error:
            raise BindingError(f"{label} byte count is invalid") from error
        require(recorded_bytes == byte_count, f"{label} byte count mismatch")
    return path, digest, byte_count


def bool_field(value: Any, label: str) -> bool:
    normalized = str(value).strip().lower()
    require(normalized in {"true", "false"}, f"{label} is not true/false")
    return normalized == "true"


def verify_completed_manifest(manifest: dict[str, Any]) -> tuple[Path, str]:
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "manifest schema mismatch")
    require(manifest.get("status") == "complete", "manifest status must be complete")
    design = manifest.get("design")
    schemas = manifest.get("schemas")
    coordinate = manifest.get("coordinate")
    profile = manifest.get("profile")
    require(
        isinstance(design, dict)
        and design.get("ncu_audit_required_for_headline") is True,
        "manifest does not require the NCU audit for headline results",
    )
    require(
        isinstance(schemas, dict)
        and schemas.get("ncu_audit") == NCU_AUDIT_SCHEMA,
        "manifest NCU audit schema mismatch",
    )
    require(
        isinstance(profile, dict)
        and profile.get("name") == TARGET_PROFILE
        and isinstance(coordinate, dict)
        and coordinate.get("softmax_cols") == SOFTMAX_COLS
        and coordinate.get("grid_blocks") == GRID_BLOCKS
        and coordinate.get("threads_per_block") == THREADS_PER_BLOCK
        and coordinate.get("rows_per_block") == ROWS_PER_BLOCK,
        "manifest target coordinate mismatch",
    )
    binary_path, binary_hash, _ = verify_file_metadata(
        manifest.get("binary"), label="frozen binary", base="manifest"
    )
    verify_file_metadata(manifest.get("runner"), label="frozen runner", base="manifest")
    sessions = manifest.get("sessions")
    require(
        isinstance(sessions, list) and len(sessions) == 9,
        "manifest must contain exactly nine completed sessions",
    )
    session_ids: set[str] = set()
    for session in sessions:
        require(isinstance(session, dict), "manifest session is malformed")
        assert isinstance(session, dict)
        session_id = str(session.get("session_id", "")).strip()
        require(
            bool(session_id) and session_id not in session_ids,
            "manifest session id is empty or duplicated",
        )
        session_ids.add(session_id)
        require(session.get("status") == "complete", f"{session_id} is not complete")
        for path_field, hash_field, label in (
            ("raw_csv", "raw_sha256", "raw"),
            ("energy_trace_csv", "energy_trace_sha256", "trace"),
        ):
            path = resolve_manifest_path(session.get(path_field))
            digest = require_sha256(
                session.get(hash_field), f"{session_id} {label} sha256"
            )
            require(path.is_file(), f"{session_id} {label} file is missing: {path}")
            require(
                sha256_file(path) == digest,
                f"{session_id} {label} file hash mismatch",
            )
    return binary_path, binary_hash


def read_summary(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            require(bool(fields), "NCU summary CSV header is missing")
            require(len(fields) == len(set(fields)), "NCU summary CSV header is duplicated")
            required = {
                "schema_version",
                "stage",
                "policy",
                "same_demangled_kernel_symbol",
                "grid_blocks",
                "threads_per_block",
                "control_kernel_name",
                "treatment_kernel_name",
                "global_store_equal",
                "status",
                "failure_reasons",
                "binary_sha256",
                "raw_ncu_csv_sha256",
                "ncu_report_sha256",
                "energy_usable",
            }
            require(required <= set(fields), "NCU summary CSV fields are incomplete")
            rows = list(reader)
    except OSError as error:
        raise BindingError(f"cannot read NCU summary CSV {path}: {error}") from error
    require(len(rows) == PAIR_COUNT, "NCU summary CSV must contain exactly nine rows")
    return rows


def verify_ncu_audit(
    audit: dict[str, Any], *, audit_path: Path, binary_hash: str
) -> tuple[
    dict[str, dict[str, dict[str, Any]]],
    dict[str, Any],
]:
    coordinate = audit.get("coordinate")
    audit_binary = audit.get("binary")
    require(
        audit.get("schema_version") == NCU_AUDIT_SCHEMA
        and audit.get("status") == "pass"
        and audit.get("artifact_path_base") == "audit_json_parent"
        and audit.get("target_profile") == TARGET_PROFILE
        and isinstance(coordinate, dict)
        and coordinate.get("softmax_cols") == SOFTMAX_COLS
        and coordinate.get("grid_blocks") == GRID_BLOCKS
        and coordinate.get("threads_per_block") == THREADS_PER_BLOCK
        and coordinate.get("rows_per_block") == ROWS_PER_BLOCK
        and isinstance(audit_binary, dict)
        and audit_binary.get("sha256") == binary_hash
        and audit.get("launch_count") == LAUNCH_COUNT
        and audit.get("pair_count") == PAIR_COUNT
        and audit.get("energy_usable") is False,
        "NCU audit top-level contract mismatch",
    )
    assert isinstance(audit_binary, dict)
    binary_contract = audit_binary.get("contract")
    require(
        isinstance(binary_contract, dict)
        and binary_contract.get("schema_version") == BINARY_CONTRACT_SCHEMA
        and binary_contract.get("kernel_contract") == KERNEL_CONTRACT
        and binary_contract.get("same_kernel_symbol_control_treatment") is True
        and binary_contract.get("treatment_invariant_sink") is True,
        "NCU audit binary contract mismatch",
    )
    provenance_hash = require_sha256(
        audit.get("provenance_payload_sha256"), "NCU audit provenance payload"
    )
    canonical = dict(audit)
    canonical.pop("provenance_payload_sha256", None)
    canonical_bytes = (
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    require(
        hashlib.sha256(canonical_bytes).hexdigest() == provenance_hash,
        "NCU audit provenance payload hash mismatch",
    )

    launches = audit.get("launches")
    pairs = audit.get("pairs")
    require(
        isinstance(launches, list) and len(launches) == LAUNCH_COUNT,
        "NCU audit launch records are incomplete",
    )
    require(
        isinstance(pairs, list) and len(pairs) == PAIR_COUNT,
        "NCU audit pair records are incomplete",
    )
    expected_pairs = {(stage, policy) for stage in STAGES for policy in POLICIES}
    observed_pairs: set[tuple[str, str]] = set()
    symbols: dict[tuple[str, str], str] = {}
    for pair in pairs:
        require(isinstance(pair, dict), "NCU audit pair record is malformed")
        assert isinstance(pair, dict)
        key = (str(pair.get("stage", "")), str(pair.get("policy", "")))
        require(
            key in expected_pairs and key not in observed_pairs,
            f"NCU audit duplicate or unexpected pair: {key}",
        )
        observed_pairs.add(key)
        checks = pair.get("checks")
        require(
            pair.get("status") == "pass"
            and pair.get("failure_reasons") == []
            and isinstance(checks, dict)
            and bool(checks)
            and all(value is True for value in checks.values()),
            f"NCU audit checks failed for {key}",
        )
        control_symbol = str(pair.get("control_kernel_name", "")).strip()
        treatment_symbol = str(pair.get("treatment_kernel_name", "")).strip()
        require(
            bool(control_symbol)
            and control_symbol == treatment_symbol
            and checks.get("same_demangled_kernel_symbol") is True,
            f"NCU audit same-symbol check failed for {key}",
        )
        require(
            pair.get("grid_blocks") == GRID_BLOCKS
            and pair.get("threads_per_block") == THREADS_PER_BLOCK,
            f"NCU audit launch coordinate mismatch for {key}",
        )
        symbols[key] = control_symbol
    require(observed_pairs == expected_pairs, "NCU audit stage-policy matrix is incomplete")

    captures = audit.get("captures")
    require(
        isinstance(captures, dict) and set(captures) == set(STAGES),
        "NCU audit stage captures are incomplete",
    )
    assert isinstance(captures, dict)
    verified_captures: dict[str, dict[str, dict[str, Any]]] = {}
    for stage in STAGES:
        stage_capture = captures[stage]
        require(
            isinstance(stage_capture, dict) and stage_capture.get("stage") == stage,
            f"NCU audit {stage} capture is malformed",
        )
        assert isinstance(stage_capture, dict)
        verified_captures[stage] = {}
        for name in CAPTURE_NAMES:
            path, digest, byte_count = verify_file_metadata(
                stage_capture.get(name),
                label=f"NCU audit {stage}/{name}",
                base="audit",
                audit_path=audit_path,
                require_bytes=True,
            )
            verified_captures[stage][name] = {
                "path": relative_or_absolute(path),
                "sha256": digest,
                "bytes": byte_count,
            }

    summary_path, summary_hash, summary_bytes = verify_file_metadata(
        audit.get("summary_csv"),
        label="NCU audit summary CSV",
        base="audit",
        audit_path=audit_path,
        require_bytes=True,
    )
    summary_rows = read_summary(summary_path)
    summary_pairs: set[tuple[str, str]] = set()
    for row in summary_rows:
        key = (str(row.get("stage", "")), str(row.get("policy", "")))
        require(
            key in expected_pairs and key not in summary_pairs,
            f"NCU summary duplicate or unexpected pair: {key}",
        )
        summary_pairs.add(key)
        try:
            row_grid = int(str(row.get("grid_blocks", "")))
            row_threads = int(str(row.get("threads_per_block", "")))
        except ValueError as error:
            raise BindingError(f"NCU summary launch coordinate invalid for {key}") from error
        require(
            row.get("schema_version") == NCU_AUDIT_SCHEMA
            and row.get("status") == "pass"
            and row.get("failure_reasons", "") == ""
            and row.get("binary_sha256") == binary_hash
            and bool_field(row.get("same_demangled_kernel_symbol"), "summary symbol")
            and bool_field(row.get("global_store_equal"), "summary global store")
            and not bool_field(row.get("energy_usable"), "summary energy")
            and row_grid == GRID_BLOCKS
            and row_threads == THREADS_PER_BLOCK,
            f"NCU summary gate failed for {key}",
        )
        require(
            row.get("control_kernel_name") == symbols[key]
            and row.get("treatment_kernel_name") == symbols[key]
            and row.get("raw_ncu_csv_sha256")
            == verified_captures[key[0]]["raw_csv"]["sha256"]
            and row.get("ncu_report_sha256")
            == verified_captures[key[0]]["ncu_report"]["sha256"],
            f"NCU summary evidence mismatch for {key}",
        )
    require(summary_pairs == expected_pairs, "NCU summary stage-policy matrix incomplete")
    summary_binding = {
        "path": relative_or_absolute(summary_path),
        "sha256": summary_hash,
        "bytes": summary_bytes,
    }
    return verified_captures, summary_binding


def bind(
    run_directory: Path,
    audit_path: Path,
    *,
    allow_portable_rebind: bool = False,
) -> dict[str, Any]:
    run_directory = run_directory.resolve()
    manifest_path = run_directory / "manifest.json"
    manifest = read_json(manifest_path, "manifest")
    _, binary_hash = verify_completed_manifest(manifest)
    audit_path = audit_path.resolve()
    audit = read_json(audit_path, "NCU audit")
    captures, summary_csv = verify_ncu_audit(
        audit, audit_path=audit_path, binary_hash=binary_hash
    )
    binding = {
        "schema_version": NCU_AUDIT_SCHEMA,
        "status": "pass",
        "path": relative_or_absolute(audit_path),
        "sha256": sha256_file(audit_path),
        "binary_sha256": binary_hash,
        "target_profile": TARGET_PROFILE,
        "coordinate": {
            "softmax_cols": SOFTMAX_COLS,
            "grid_blocks": GRID_BLOCKS,
            "threads_per_block": THREADS_PER_BLOCK,
            "rows_per_block": ROWS_PER_BLOCK,
        },
        "launch_count": LAUNCH_COUNT,
        "pair_count": PAIR_COUNT,
        "energy_usable": False,
        "summary_csv": summary_csv,
        "captures": captures,
    }
    existing = manifest.get("ncu_audit")
    if existing is not None:
        if existing == binding:
            return binding
        if allow_portable_rebind:
            require(
                isinstance(existing, dict),
                "existing ncu_audit binding is malformed",
            )
            assert isinstance(existing, dict)
            old_without_hash = dict(existing)
            new_without_hash = dict(binding)
            old_hash = old_without_hash.pop("sha256", None)
            new_hash = new_without_hash.pop("sha256", None)
            require_sha256(old_hash, "existing ncu_audit sha256")
            require_sha256(new_hash, "replacement ncu_audit sha256")
            require(
                old_without_hash == new_without_hash,
                "portable rebind may change only the audit JSON SHA-256",
            )
            manifest["ncu_audit"] = binding
            manifest["ncu_audit_portability_rebound_at"] = timestamp()
            manifest["ncu_audit_previous_sha256"] = old_hash
            atomic_json(manifest_path, manifest)
            return binding
        raise BindingError(
            "manifest already has a different ncu_audit binding; the binding is immutable"
        )
    manifest["ncu_audit"] = binding
    manifest["ncu_audit_bound_at"] = timestamp()
    atomic_json(manifest_path, manifest)
    return binding


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="stage_atc_ncu_binder_") as temporary:
        root = Path(temporary)
        run_directory = root / "run"
        audit_directory = root / "ncu"
        run_directory.mkdir()
        audit_directory.mkdir()

        def artifact(path: Path, payload: bytes) -> dict[str, Any]:
            path.write_bytes(payload)
            return {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }

        binary = artifact(root / "binary", b"binary")
        runner = artifact(root / "runner.py", b"runner")
        sessions: list[dict[str, Any]] = []
        for index in range(9):
            raw = artifact(root / f"raw_{index}.csv", b"raw")
            trace = artifact(root / f"trace_{index}.csv", b"trace")
            sessions.append(
                {
                    "session_id": f"session_{index}",
                    "status": "complete",
                    "raw_csv": raw["path"],
                    "raw_sha256": raw["sha256"],
                    "energy_trace_csv": trace["path"],
                    "energy_trace_sha256": trace["sha256"],
                }
            )
        atomic_json(
            run_directory / "manifest.json",
            {
                "schema_version": MANIFEST_SCHEMA,
                "status": "complete",
                "profile": {"name": TARGET_PROFILE},
                "coordinate": {
                    "softmax_cols": SOFTMAX_COLS,
                    "grid_blocks": GRID_BLOCKS,
                    "threads_per_block": THREADS_PER_BLOCK,
                    "rows_per_block": ROWS_PER_BLOCK,
                },
                "design": {"ncu_audit_required_for_headline": True},
                "schemas": {"ncu_audit": NCU_AUDIT_SCHEMA},
                "binary": binary,
                "runner": runner,
                "sessions": sessions,
            },
        )

        captures: dict[str, Any] = {}
        for stage in STAGES:
            captures[stage] = {
                "stage": stage,
                **{
                    name: artifact(
                        audit_directory / f"{stage}.{name}",
                        f"{stage}:{name}".encode("utf-8"),
                    )
                    for name in CAPTURE_NAMES
                },
            }
            for metadata in captures[stage].values():
                if isinstance(metadata, dict) and "path" in metadata:
                    metadata["path"] = Path(str(metadata["path"])).name
        pairs: list[dict[str, Any]] = []
        launches: list[dict[str, Any]] = []
        summary_rows: list[dict[str, Any]] = []
        for stage in STAGES:
            for policy in POLICIES:
                symbol = f"whole_softmax_stage_atc_kernel<{stage},{policy}>"
                checks = {
                    "same_demangled_kernel_symbol": True,
                    "exact_instruction_delta": True,
                    "global_store_equal": True,
                }
                pairs.append(
                    {
                        "stage": stage,
                        "policy": policy,
                        "status": "pass",
                        "failure_reasons": [],
                        "checks": checks,
                        "control_kernel_name": symbol,
                        "treatment_kernel_name": symbol,
                        "grid_blocks": GRID_BLOCKS,
                        "threads_per_block": THREADS_PER_BLOCK,
                    }
                )
                launches.extend(
                    [
                        {"stage": stage, "policy": policy, "role": "control"},
                        {"stage": stage, "policy": policy, "role": "treatment"},
                    ]
                )
                summary_rows.append(
                    {
                        "schema_version": NCU_AUDIT_SCHEMA,
                        "stage": stage,
                        "policy": policy,
                        "same_demangled_kernel_symbol": "true",
                        "grid_blocks": GRID_BLOCKS,
                        "threads_per_block": THREADS_PER_BLOCK,
                        "control_kernel_name": symbol,
                        "treatment_kernel_name": symbol,
                        "global_store_equal": "true",
                        "status": "pass",
                        "failure_reasons": "",
                        "binary_sha256": binary["sha256"],
                        "raw_ncu_csv_sha256": captures[stage]["raw_csv"]["sha256"],
                        "ncu_report_sha256": captures[stage]["ncu_report"]["sha256"],
                        "energy_usable": "false",
                    }
                )
        summary_path = audit_directory / "audit.csv"
        atomic_csv(summary_path, summary_rows)
        audit: dict[str, Any] = {
            "schema_version": NCU_AUDIT_SCHEMA,
            "status": "pass",
            "artifact_path_base": "audit_json_parent",
            "target_profile": TARGET_PROFILE,
            "coordinate": {
                "softmax_cols": SOFTMAX_COLS,
                "grid_blocks": GRID_BLOCKS,
                "threads_per_block": THREADS_PER_BLOCK,
                "rows_per_block": ROWS_PER_BLOCK,
            },
            "binary": {
                "sha256": binary["sha256"],
                "contract": {
                    "schema_version": BINARY_CONTRACT_SCHEMA,
                    "kernel_contract": KERNEL_CONTRACT,
                    "same_kernel_symbol_control_treatment": True,
                    "treatment_invariant_sink": True,
                },
            },
            "launch_count": LAUNCH_COUNT,
            "pair_count": PAIR_COUNT,
            "launches": launches,
            "pairs": pairs,
            "captures": captures,
            "summary_csv": artifact(summary_path, summary_path.read_bytes()),
            "energy_usable": False,
        }
        audit["summary_csv"]["path"] = summary_path.name
        canonical = (
            json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        audit["provenance_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
        audit_path = audit_directory / "audit.json"
        atomic_json(audit_path, audit)
        first = bind(run_directory, audit_path)
        second = bind(run_directory, audit_path)
        require(first == second, "idempotent NCU binding changed")

        portable_audit = read_json(audit_path, "portable self-test audit")
        portable_audit["portable_rewrite_note"] = "relative-path migration"
        portable_audit.pop("provenance_payload_sha256")
        canonical = (
            json.dumps(
                portable_audit,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        portable_audit["provenance_payload_sha256"] = hashlib.sha256(
            canonical
        ).hexdigest()
        atomic_json(audit_path, portable_audit)
        try:
            bind(run_directory, audit_path)
        except BindingError as error:
            require(
                "different ncu_audit binding" in str(error),
                "immutable binding rejection reason drifted",
            )
        else:
            raise BindingError("changed audit bypassed immutable binding")
        refreshed = bind(
            run_directory,
            audit_path,
            allow_portable_rebind=True,
        )
        require(
            refreshed["sha256"] == sha256_file(audit_path),
            "portable NCU binding refresh did not bind the new audit",
        )

        raw_capture = audit_directory / captures["exp"]["raw_csv"]["path"]
        raw_capture.write_bytes(raw_capture.read_bytes() + b"tamper")
        try:
            bind(run_directory, audit_path)
        except BindingError as error:
            require("hash mismatch" in str(error), "tamper rejection reason drifted")
        else:
            raise BindingError("tampered NCU capture was not rejected")
    print(
        "softmax_whole_stage_atc_ncu_audit_binder_self_test=pass "
        "scenarios=valid_binding,idempotent_binding,portable_refresh,"
        "tampered_capture_rejection"
    )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", nargs="?")
    parser.add_argument(
        "--audit",
        help="NCU audit JSON (default: <run_directory>/ncu_audit/audit.json)",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--refresh-portable-binding",
        action="store_true",
        help=(
            "replace an existing binding only when the audit SHA is the sole "
            "difference after converting audit-internal paths to relative form"
        ),
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    require(bool(args.run_directory), "run_directory is required")
    run_directory = Path(str(args.run_directory))
    audit_path = (
        Path(args.audit)
        if args.audit
        else run_directory / "ncu_audit" / "audit.json"
    )
    binding = bind(
        run_directory,
        audit_path,
        allow_portable_rebind=args.refresh_portable_binding,
    )
    print(
        "ncu_audit_binding=pass "
        f"audit_sha256={binding['sha256']} "
        f"binary_sha256={binding['binary_sha256']} "
        f"launch_count={binding['launch_count']} "
        f"pair_count={binding['pair_count']} "
        "energy_usable=false"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as error:  # pragma: no cover - command-line boundary
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
