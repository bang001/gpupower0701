#!/usr/bin/env python3
"""Repair WSL wall-clock jumps without changing measured energy data.

The CUDA harness measures elapsed time with steady_clock. Older rows sampled
system_clock independently at both interval endpoints, so a Windows/WSL clock
correction could make the epoch interval disagree with the monotonic elapsed
time. This tool preserves each source CSV, anchors the end epoch to the start
epoch plus elapsed_s, and records every metadata change in a manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import tempfile
from pathlib import Path


REQUIRED_COLUMNS = {
    "run_id",
    "elapsed_s",
    "measurement_start_epoch_ms",
    "measurement_end_epoch_ms",
    "notes",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_note(notes: str, note: str) -> str:
    existing = notes if not notes or notes.endswith(";") else notes + ";"
    return existing if f"{note};" in existing else existing + note + ";"


def repair_file(path: Path, backup_dir: Path) -> tuple[list[dict[str, str]], str, str]:
    before_hash = sha256(path)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []
        missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
        if missing:
            raise ValueError(f"{path}: missing columns: {','.join(missing)}")
        rows = list(reader)

    backup_relative = Path(*path.parts[1:]) if path.is_absolute() else path
    backup_path = backup_dir / backup_relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)

    manifest_rows: list[dict[str, str]] = []
    for row_index, row in enumerate(rows, start=2):
        start_ms = int(row["measurement_start_epoch_ms"])
        old_end_ms = int(row["measurement_end_epoch_ms"])
        elapsed_s = float(row["elapsed_s"])
        if start_ms <= 0 or elapsed_s <= 0.0:
            raise ValueError(
                f"{path}:{row_index}: invalid start/elapsed interval metadata"
            )
        new_end_ms = start_ms + round(elapsed_s * 1000.0)
        old_interval_ms = old_end_ms - start_ms
        expected_ms = elapsed_s * 1000.0
        mismatch_ms = old_interval_ms - expected_ms

        row["measurement_end_epoch_ms"] = str(new_end_ms)
        row["notes"] = append_note(
            row["notes"], "measurement_interval_clock=steady_clock_anchored_epoch"
        )
        row["notes"] = append_note(
            row["notes"], "measurement_interval_remediation=wsl_wallclock_v1"
        )
        row["notes"] = append_note(
            row["notes"], f"measurement_end_epoch_ms_original={old_end_ms}"
        )
        manifest_rows.append(
            {
                "input_file": str(path),
                "backup_file": str(backup_path),
                "row_index": str(row_index),
                "run_id": row["run_id"],
                "elapsed_s": row["elapsed_s"],
                "measurement_start_epoch_ms": str(start_ms),
                "measurement_end_epoch_ms_original": str(old_end_ms),
                "measurement_end_epoch_ms_repaired": str(new_end_ms),
                "original_interval_mismatch_ms": f"{mismatch_ms:.6f}",
                "energy_fields_modified": "false",
            }
        )

    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    return manifest_rows, before_hash, sha256(path)


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "raw.csv"
        source.write_text(
            "run_id,elapsed_s,measurement_start_epoch_ms,"
            "measurement_end_epoch_ms,delta_E_J,notes\n"
            "x,10.25,100000,108000,42.5,original=1;\n"
        )
        rows, before_hash, after_hash = repair_file(source, root / "backup")
        assert before_hash != after_hash
        assert rows[0]["measurement_end_epoch_ms_repaired"] == "110250"
        assert rows[0]["energy_fields_modified"] == "false"
        with source.open(newline="") as stream:
            repaired = next(csv.DictReader(stream))
        assert repaired["delta_E_J"] == "42.5"
        assert repaired["measurement_end_epoch_ms"] == "110250"
        assert "wsl_wallclock_v1" in repaired["notes"]
    print("wall-clock interval remediation self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.inputs or args.backup_dir is None or args.manifest is None:
        parser.error("inputs, --backup-dir, and --manifest are required")

    all_rows: list[dict[str, str]] = []
    hashes: list[tuple[Path, str, str]] = []
    for input_path in args.inputs:
        rows, before_hash, after_hash = repair_file(input_path, args.backup_dir)
        all_rows.extend(rows)
        hashes.append((input_path, before_hash, after_hash))
    write_manifest(args.manifest, all_rows)
    for input_path, before_hash, after_hash in hashes:
        print(f"repaired {input_path}: sha256 {before_hash} -> {after_hash}")
    print(f"wrote remediation manifest: {args.manifest} ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
