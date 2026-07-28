#!/usr/bin/env python3
"""Bind a passing whole-Softmax stage ATC static audit to a completed run.

The acquisition runner intentionally does not claim that the added stage pass
survived compilation.  A separate producer inspects the frozen binary and
writes ``<run>/static_audit.json``.  This binder verifies that artifact, its
PTX/SASS/ELF-list captures, the frozen binary, and every raw/trace hash before
atomically adding one immutable ``static_audit`` binding to the manifest.
"""

from __future__ import annotations

import argparse
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
STATIC_AUDIT_SCHEMA = "softmax_whole_stage_atc_static_audit_v2"
TARGET_PROFILE = "rtx3090"
CUDA_ARCH = "86"
KERNEL_CONTRACT = "whole_softmax_stage_atc_same_symbol_runtime_flag_v2"
SPECIALIZATION_COUNT = 9
REQUIRED_CAPTURES = ("ptx", "sass", "list_elf")


class BindingError(RuntimeError):
    """Raised when an audit cannot be bound without weakening provenance."""


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
    if not isinstance(payload, dict):
        raise BindingError(f"{label} must be one JSON object")
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


def resolve_manifest_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise BindingError("manifest artifact path is missing")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise BindingError(
            f"{label}: observed {observed!r}, expected {expected!r}"
        )


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise BindingError(f"{label} is not a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise BindingError(f"{label} is not a SHA-256 hex digest") from error
    return value.lower()


def verify_hashed_file(
    metadata: Any, *, label: str, base_directory: Path | None = None
) -> tuple[Path, str]:
    if not isinstance(metadata, dict):
        raise BindingError(f"{label} metadata is missing")
    value = metadata.get("path")
    if not isinstance(value, str) or not value:
        raise BindingError(f"{label} path is missing")
    path = Path(value)
    if not path.is_absolute():
        path = (
            (base_directory / path).resolve()
            if base_directory is not None
            else (ROOT / path).resolve()
        )
    expected_hash = require_sha256(metadata.get("sha256"), f"{label} sha256")
    if not path.is_file():
        raise BindingError(f"{label} file is missing: {path}")
    require_equal(sha256_file(path), expected_hash, f"{label} file hash")
    return path, expected_hash


def verify_completed_manifest(manifest: dict[str, Any]) -> tuple[Path, str]:
    require_equal(
        manifest.get("schema_version"), MANIFEST_SCHEMA, "manifest schema"
    )
    require_equal(manifest.get("status"), "complete", "manifest status")
    binary_path, binary_sha256 = verify_hashed_file(
        manifest.get("binary"), label="frozen binary"
    )
    verify_hashed_file(manifest.get("runner"), label="frozen runner")

    sessions = manifest.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 9:
        raise BindingError("manifest must contain exactly nine sessions")
    for session in sessions:
        if not isinstance(session, dict):
            raise BindingError("manifest session is malformed")
        session_id = str(session.get("session_id", "<missing>"))
        require_equal(session.get("status"), "complete", f"{session_id} status")
        for path_field, hash_field, label in (
            ("raw_csv", "raw_sha256", "raw"),
            ("energy_trace_csv", "energy_trace_sha256", "trace"),
        ):
            path = resolve_manifest_path(session.get(path_field))
            expected_hash = require_sha256(
                session.get(hash_field), f"{session_id} {label} sha256"
            )
            if not path.is_file():
                raise BindingError(f"{session_id} {label} file is missing: {path}")
            require_equal(
                sha256_file(path),
                expected_hash,
                f"{session_id} {label} file hash",
            )
    return binary_path, binary_sha256


def verify_static_audit(
    audit: dict[str, Any], *, audit_path: Path, binary_sha256: str
) -> dict[str, Any]:
    require_equal(
        audit.get("schema_version"), STATIC_AUDIT_SCHEMA, "static audit schema"
    )
    require_equal(audit.get("status"), "pass", "static audit status")
    require_equal(
        require_sha256(audit.get("binary_sha256"), "static audit binary sha256"),
        binary_sha256,
        "static audit binary binding",
    )
    require_equal(audit.get("target_profile"), TARGET_PROFILE, "target profile")
    require_equal(str(audit.get("cuda_arch")), CUDA_ARCH, "CUDA architecture")
    require_equal(
        audit.get("kernel_contract"), KERNEL_CONTRACT, "kernel contract"
    )
    require_equal(
        audit.get("required_specialization_count"),
        SPECIALIZATION_COUNT,
        "required specialization count",
    )
    require_equal(
        audit.get("observed_specialization_count"),
        SPECIALIZATION_COUNT,
        "observed specialization count",
    )

    checks = audit.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise BindingError("static audit checks must be a non-empty object")
    failed_checks = sorted(
        key for key, value in checks.items() if value != "pass"
    )
    if failed_checks:
        raise BindingError(f"static audit checks did not pass: {failed_checks}")

    captures = audit.get("captures")
    if not isinstance(captures, dict):
        raise BindingError("static audit captures object is missing")
    verified_captures: dict[str, dict[str, str]] = {}
    for name in REQUIRED_CAPTURES:
        path, digest = verify_hashed_file(
            captures.get(name),
            label=f"static audit {name} capture",
            base_directory=audit_path.parent,
        )
        verified_captures[name] = {
            "path": relative_or_absolute(path),
            "sha256": digest,
        }
    return verified_captures


def bind(run_directory: Path, audit_path: Path) -> dict[str, Any]:
    run_directory = run_directory.resolve()
    manifest_path = run_directory / "manifest.json"
    manifest = read_json(manifest_path, "manifest")
    _, binary_sha256 = verify_completed_manifest(manifest)
    audit_path = audit_path.resolve()
    audit = read_json(audit_path, "static audit")
    captures = verify_static_audit(
        audit, audit_path=audit_path, binary_sha256=binary_sha256
    )
    audit_sha256 = sha256_file(audit_path)
    binding = {
        "schema_version": STATIC_AUDIT_SCHEMA,
        "status": "pass",
        "path": relative_or_absolute(audit_path),
        "sha256": audit_sha256,
        "binary_sha256": binary_sha256,
        "captures": captures,
    }

    existing = manifest.get("static_audit")
    if existing is not None:
        if existing == binding:
            return binding
        raise BindingError(
            "manifest already has a different static_audit binding; "
            "the binding is immutable"
        )
    manifest["static_audit"] = binding
    manifest["static_audit_bound_at"] = timestamp()
    atomic_json(manifest_path, manifest)
    return binding


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="stage_atc_binder_") as temporary:
        root = Path(temporary)
        run_directory = root / "run"
        run_directory.mkdir()

        def write(path: Path, payload: bytes) -> dict[str, str]:
            path.write_bytes(payload)
            return {"path": str(path), "sha256": sha256_file(path)}

        binary = write(root / "binary", b"binary")
        runner = write(root / "runner.py", b"runner")
        sessions: list[dict[str, Any]] = []
        for index in range(9):
            raw = write(root / f"raw_{index}.csv", b"raw")
            trace = write(root / f"trace_{index}.csv", b"trace")
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
                "binary": binary,
                "runner": runner,
                "sessions": sessions,
            },
        )

        capture_metadata: dict[str, dict[str, str]] = {}
        for name in REQUIRED_CAPTURES:
            capture_metadata[name] = write(root / f"{name}.txt", name.encode())
        audit_path = run_directory / "static_audit.json"
        atomic_json(
            audit_path,
            {
                "schema_version": STATIC_AUDIT_SCHEMA,
                "status": "pass",
                "binary_sha256": binary["sha256"],
                "target_profile": TARGET_PROFILE,
                "cuda_arch": 86,
                "kernel_contract": KERNEL_CONTRACT,
                "required_specialization_count": SPECIALIZATION_COUNT,
                "observed_specialization_count": SPECIALIZATION_COUNT,
                "checks": {
                    "same_symbol_runtime_flag": "pass",
                    "extra_stage_pass_survives": "pass",
                    "live_sink_dataflow": "pass",
                },
                "captures": capture_metadata,
            },
        )
        first = bind(run_directory, audit_path)
        second = bind(run_directory, audit_path)
        assert first == second
        assert read_json(run_directory / "manifest.json", "manifest")[
            "static_audit"
        ] == first
    print("softmax_whole_stage_atc_static_audit_binder_self_test=pass")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", nargs="?")
    parser.add_argument(
        "--audit",
        help="static audit JSON (default: <run_directory>/static_audit.json)",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not args.run_directory:
        raise BindingError("run_directory is required")
    run_directory = Path(args.run_directory)
    audit_path = (
        Path(args.audit)
        if args.audit
        else run_directory / "static_audit.json"
    )
    binding = bind(run_directory, audit_path)
    print(
        "static_audit_binding=pass "
        f"audit_sha256={binding['sha256']} "
        f"binary_sha256={binding['binary_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as error:  # pragma: no cover - command-line boundary
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
