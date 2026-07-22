#!/usr/bin/env python3
"""Merge disjoint NCU validation summaries without hiding their provenance."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path


def merge(
    paths: list[Path],
    *,
    ncu_binary_sha256: str = "",
    ncu_binary_path: str = "",
    ncu_binary_hash_capture: str = "",
    ncu_quiescence_status: str = "",
) -> tuple[list[str], list[dict[str, str]]]:
    fieldnames: list[str] = []
    rows: list[dict[str, str]] = []
    labels: set[str] = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for name in reader.fieldnames or []:
                if name not in fieldnames:
                    fieldnames.append(name)
            for source_row in reader:
                row = dict(source_row)
                label = row.get("label", "").strip()
                if not label:
                    raise ValueError(f"{path}: row without label")
                if label in labels:
                    raise ValueError(
                        f"duplicate NCU label {label!r}; keep gating and diagnostic "
                        "runs in disjoint mode sets"
                    )
                labels.add(label)
                row["ncu_summary_source"] = str(path)
                row["ncu_binary_sha256"] = ncu_binary_sha256
                row["ncu_binary_path"] = ncu_binary_path
                row["ncu_binary_hash_capture"] = ncu_binary_hash_capture
                row["ncu_quiescence_status"] = ncu_quiescence_status
                rows.append(row)
    for name in (
        "ncu_summary_source",
        "ncu_binary_sha256",
        "ncu_binary_path",
        "ncu_binary_hash_capture",
        "ncu_quiescence_status",
    ):
        if name not in fieldnames:
            fieldnames.append(name)
    return fieldnames, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, inputs: list[Path], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write("# Combined NCU Validation Summary\n\n")
        out.write(
            "This canonical table combines disjoint NCU runs. L2 and external-memory "
            "gating rows use the coherent `l2_path_minimal` profile; Tensor, Shared, "
            "and Global-L1 rows use the full diagnostic profile. NCU runs are "
            "validation evidence, not energy rows.\n\n"
        )
        out.write("## Inputs\n\n")
        for source in inputs:
            out.write(f"- `{source}`\n")
        if rows and rows[0].get("ncu_binary_sha256"):
            out.write(
                f"- binary: `{rows[0].get('ncu_binary_path', '')}`\n"
                f"- binary SHA-256: `{rows[0].get('ncu_binary_sha256', '')}`\n"
                f"- hash capture: `{rows[0].get('ncu_binary_hash_capture', '')}`\n"
                f"- NCU quiescence: `{rows[0].get('ncu_quiescence_status', '')}`\n"
            )
        out.write("\n")
        out.write(
            "| label | mode | W_SM (KiB/SM) | blocks/SM | LR | metric profile | "
            "status | L1 path hit (%) | L2 direct/native/logical hit (%) | fabric fraction | conservation | "
            "long scoreboard status | source |\n"
        )
        out.write("|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|\n")
        for row in rows:
            out.write(
                f"| {row.get('label', '')} | {row.get('mode', '')} | "
                f"{row.get('W_SM_KiB', '')} | {row.get('blocks_per_SM', '')} | "
                f"{row.get('load_repeat', '')} | {row.get('ncu_metric_profile', '')} | "
                f"{row.get('status', '')} | {row.get('l1_path_hit_rate_pct', '')} | "
                f"{row.get('l2_path_hit_rate_pct', '')}/"
                f"{row.get('l2_native_read_hit_rate_pct', '')}/"
                f"{row.get('l2_logical_read_hit_rate_pct', '')} | "
                f"{row.get('l2_fabric_read_fraction', '')} | "
                f"{row.get('l2_read_sector_conservation_ratio', '')} | "
                f"{row.get('stall_long_scoreboard_pct', '')} | "
                f"{row.get('ncu_summary_source', '')} |\n"
            )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        full = root / "full.csv"
        minimal = root / "minimal.csv"
        full.write_text(
            "label,mode,ncu_metric_profile,status\n"
            "tensor,reg_mma,full,ok\n",
            encoding="utf-8",
        )
        minimal.write_text(
            "label,mode,ncu_metric_profile,status,l2_path_counter_coherent\n"
            "l2,l2_cg_load_only,l2_path_minimal,ok,1\n",
            encoding="utf-8",
        )
        fields, rows = merge(
            [full, minimal],
            ncu_binary_sha256="abc",
            ncu_binary_path="./build/test",
            ncu_binary_hash_capture="pre_post_collection_verified",
            ncu_quiescence_status="strict_passed",
        )
        assert len(rows) == 2
        assert "l2_path_counter_coherent" in fields
        assert all(row["ncu_summary_source"] for row in rows)
        assert all(row["ncu_binary_sha256"] == "abc" for row in rows)
        assert all(
            row["ncu_binary_hash_capture"] == "pre_post_collection_verified"
            for row in rows
        )
        assert all(row["ncu_quiescence_status"] == "strict_passed" for row in rows)
        try:
            merge([full, full])
        except ValueError as exc:
            assert "duplicate NCU label" in str(exc)
        else:
            raise AssertionError("duplicate labels were not rejected")
    print("NCU summary merge self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--ncu-binary-sha256", default="")
    parser.add_argument("--ncu-binary-path", default="")
    parser.add_argument("--ncu-binary-hash-capture", default="")
    parser.add_argument("--ncu-quiescence-status", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.inputs or not args.out_csv or not args.out_md:
        parser.error("inputs, --out-csv, and --out-md are required")
    inputs = [Path(value) for value in args.inputs]
    fieldnames, rows = merge(
        inputs,
        ncu_binary_sha256=args.ncu_binary_sha256,
        ncu_binary_path=args.ncu_binary_path,
        ncu_binary_hash_capture=args.ncu_binary_hash_capture,
        ncu_quiescence_status=args.ncu_quiescence_status,
    )
    if not rows:
        raise ValueError("NCU summary merge produced no rows")
    write_csv(Path(args.out_csv), fieldnames, rows)
    write_markdown(Path(args.out_md), inputs, rows)
    print(f"merged {len(rows)} NCU rows into {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
