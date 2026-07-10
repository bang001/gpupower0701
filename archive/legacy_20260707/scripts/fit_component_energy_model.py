#!/usr/bin/env python3
"""Fit elapsed-aware component energy models from raw benchmark CSVs."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path
from typing import Any


STATIC_FEATURES = [
    ("elapsed_s", "elapsed_s", "W"),
    ("FLOP", "FLOP", "pJ/FLOP"),
    ("expected_reg_operand_ops", "reg_operand_ops", "pJ/reg-op"),
    ("expected_reg_pressure_ops", "reg_pressure_ops", "pJ/reg-update"),
    ("expected_shared_bytes", "shared_bytes_static", "pJ/byte"),
    ("expected_l1_bytes", "l1_bytes_static", "pJ/byte"),
    ("expected_l2_bytes", "l2_bytes_static", "pJ/byte"),
    ("expected_dram_bytes", "dram_bytes_static", "pJ/byte"),
    ("expected_store_bytes", "store_bytes_static", "pJ/byte"),
]

NCU_FEATURES = [
    ("elapsed_s", "elapsed_s", "W"),
    ("FLOP", "FLOP", "pJ/FLOP"),
    ("expected_reg_operand_ops", "reg_operand_ops", "pJ/reg-op"),
    ("expected_reg_pressure_ops", "reg_pressure_ops", "pJ/reg-update"),
    ("ncu_shared_bytes", "shared_bytes_ncu", "pJ/byte"),
    ("ncu_l1_bytes", "l1_bytes_ncu", "pJ/byte"),
    ("ncu_l2_bytes", "l2_bytes_ncu", "pJ/byte"),
    ("ncu_dram_bytes", "dram_bytes_ncu", "pJ/byte"),
    ("expected_store_bytes", "store_bytes_static", "pJ/byte"),
]


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        out = float(value)
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def is_active_row(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "gpu_active=1" in notes:
        return True
    if "gpu_active=0" in notes:
        return False
    return as_float(row, "n_gpu_active") > 0


def variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pvariance(values)


def median_nonzero_abs(values: list[float]) -> float:
    nonzero = [abs(v) for v in values if abs(v) > 0.0]
    if not nonzero:
        return 1.0
    return statistics.median(nonzero)


def solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(a)
    aug = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1.0e-18:
            raise ValueError("singular normal matrix")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            aug[r] = [v - factor * aug[col][i] for i, v in enumerate(aug[r])]
    return [row[-1] for row in aug]


def fit_scaled_ridge(
    x_rows: list[list[float]],
    y: list[float],
    ridge_lambda: float,
) -> list[float]:
    n = len(x_rows)
    p = len(x_rows[0])
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [0.0 for _ in range(p)]
    for i in range(n):
        row = x_rows[i]
        for j in range(p):
            xty[j] += row[j] * y[i]
            for k in range(p):
                xtx[j][k] += row[j] * row[k]
    for j in range(1, p):
        xtx[j][j] += ridge_lambda
    return solve_linear_system(xtx, xty)


def fit_scaled_coordinate_descent(
    x_rows: list[list[float]],
    y: list[float],
    ridge_lambda: float,
    constrained_nonnegative: list[bool],
    *,
    max_iter: int,
    tolerance: float,
    initial_beta: list[float] | None = None,
) -> tuple[list[float], int]:
    """Solve a small ridge problem with optional beta_j >= 0 constraints."""

    n = len(x_rows)
    p = len(x_rows[0])
    if len(constrained_nonnegative) != p:
        raise ValueError("constraint vector length mismatch")

    x_cols = [[x_rows[i][j] for i in range(n)] for j in range(p)]
    denom = []
    for j, col in enumerate(x_cols):
        penalty = 0.0 if j == 0 else ridge_lambda
        denom.append(sum(v * v for v in col) + penalty)

    if initial_beta and len(initial_beta) == p:
        beta = initial_beta[:]
        for j, is_constrained in enumerate(constrained_nonnegative):
            if is_constrained and beta[j] < 0.0:
                beta[j] = 0.0
    else:
        beta = [0.0 for _ in range(p)]
    residual = [
        y[i] - sum(x_rows[i][j] * beta[j] for j in range(p))
        for i in range(n)
    ]
    completed_iter = 0
    for iteration in range(1, max_iter + 1):
        max_delta = 0.0
        for j, col in enumerate(x_cols):
            old = beta[j]
            if old:
                for i in range(n):
                    residual[i] += col[i] * old

            if denom[j] <= 0.0:
                new = 0.0
            else:
                numerator = sum(col[i] * residual[i] for i in range(n))
                new = numerator / denom[j]
                if constrained_nonnegative[j] and new < 0.0:
                    new = 0.0

            if new:
                for i in range(n):
                    residual[i] -= col[i] * new
            beta[j] = new
            max_delta = max(max_delta, abs(new - old))

        completed_iter = iteration
        beta_scale = max(1.0, max(abs(value) for value in beta))
        if max_delta <= tolerance * beta_scale:
            break

    return beta, completed_iter


def fit_scaled_active_set_nnls(
    x_rows: list[list[float]],
    y: list[float],
    ridge_lambda: float,
    constrained_nonnegative: list[bool],
    *,
    max_iter: int,
    tolerance: float,
) -> tuple[list[float], int]:
    """Solve a mixed unconstrained/non-negative ridge problem by active set."""

    n = len(x_rows)
    p = len(x_rows[0])
    if len(constrained_nonnegative) != p:
        raise ValueError("constraint vector length mismatch")

    constrained = {j for j, value in enumerate(constrained_nonnegative) if value}
    unconstrained = {j for j in range(p) if j not in constrained}
    active: set[int] = set()

    xty_full = [
        sum(x_rows[i][j] * y[i] for i in range(n))
        for j in range(p)
    ]
    grad_tolerance = tolerance * max(1.0, max(abs(v) for v in xty_full))

    def solve_free(free_columns: list[int]) -> list[float]:
        size = len(free_columns)
        a = [[0.0 for _ in range(size)] for _ in range(size)]
        b = [0.0 for _ in range(size)]
        for local_j, global_j in enumerate(free_columns):
            b[local_j] = xty_full[global_j]
            for local_k, global_k in enumerate(free_columns):
                a[local_j][local_k] = sum(
                    x_rows[i][global_j] * x_rows[i][global_k]
                    for i in range(n)
                )
            if global_j != 0:
                a[local_j][local_j] += ridge_lambda
        free_beta = solve_linear_system(a, b)
        beta = [0.0 for _ in range(p)]
        for local_j, global_j in enumerate(free_columns):
            beta[global_j] = free_beta[local_j]
        return beta

    beta = [0.0 for _ in range(p)]
    completed_iter = 0
    for iteration in range(1, max_iter + 1):
        completed_iter = iteration
        free = sorted(unconstrained | active)
        beta = solve_free(free)

        negative_active = [j for j in active if beta[j] < -grad_tolerance]
        if negative_active:
            remove_j = min(negative_active, key=lambda j: beta[j])
            active.remove(remove_j)
            continue
        for j in active:
            if beta[j] < 0.0:
                beta[j] = 0.0

        residual = [
            sum(x_rows[i][j] * beta[j] for j in range(p)) - y[i]
            for i in range(n)
        ]
        violations = []
        for j in sorted(constrained - active):
            gradient = sum(x_rows[i][j] * residual[i] for i in range(n))
            if gradient < -grad_tolerance:
                violations.append((gradient, j))
        if not violations:
            return beta, completed_iter
        _, add_j = min(violations)
        active.add(add_j)

    return beta, completed_iter


def display_value(coefficient: float, unit: str) -> float:
    if unit.startswith("pJ/"):
        return coefficient * 1.0e12
    return coefficient


def read_rows(path: Path, include_placement_failures: bool) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        if not is_active_row(row):
            continue
        if (
            not include_placement_failures
            and row.get("smid_histogram_ok", "").lower() == "false"
        ):
            continue
        if row.get("mode") == "idle":
            continue
        out.append(row)
    return out


def parse_csv_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def apply_mode_filter(
    rows: list[dict[str, str]],
    include_modes: str,
    exclude_modes: str,
) -> list[dict[str, str]]:
    include = parse_csv_set(include_modes)
    exclude = parse_csv_set(exclude_modes)
    out = []
    for row in rows:
        mode = row.get("mode", "")
        if include and mode not in include:
            continue
        if exclude and mode in exclude:
            continue
        out.append(row)
    return out


def apply_quality_filter(
    rows: list[dict[str, str]],
    *,
    min_elapsed_s: float,
    exclude_negative_net_energy: bool,
) -> list[dict[str, str]]:
    out = []
    for row in rows:
        if min_elapsed_s > 0.0 and as_float(row, "elapsed_s") < min_elapsed_s:
            continue
        if exclude_negative_net_energy and as_float(row, "net_E_J") < 0.0:
            continue
        out.append(row)
    return out


def select_feature_specs(byte_source: str) -> list[tuple[str, str, str]]:
    if byte_source == "static":
        return STATIC_FEATURES
    if byte_source == "ncu":
        return NCU_FEATURES
    if byte_source == "prefer-ncu":
        return NCU_FEATURES
    raise ValueError(f"unknown byte source: {byte_source}")


def mode_family(mode: str) -> str:
    if mode in {"empty", "clocked_empty"}:
        return "empty"
    if mode == "addr_only":
        return "address_control"
    if mode.startswith("reg_"):
        return "register"
    if mode.startswith("shared_"):
        return "shared"
    if mode.startswith("global_l1_"):
        return "l1"
    if mode.startswith("l2_"):
        return "l2"
    if mode.startswith("dram_"):
        return "dram"
    if mode.startswith("store_"):
        return "store"
    return "other"


def build_baseline_terms(
    rows: list[dict[str, str]],
    baseline_terms: str,
) -> list[dict[str, Any]]:
    if baseline_terms == "none":
        return []

    if baseline_terms == "mode":
        labels = sorted({row.get("mode", "") for row in rows})
        reference = "empty" if "empty" in labels else labels[0]
        return [
            {
                "source": "mode",
                "name": f"baseline_mode_{label}",
                "unit": "J",
                "values": [
                    1.0 if row.get("mode", "") == label else 0.0 for row in rows
                ],
                "scale": 1.0,
                "constrained": False,
                "term_kind": "baseline",
                "nonzero_modes": label,
                "positive_unique_count": 1,
            }
            for label in labels
            if label != reference
        ]

    if baseline_terms == "family":
        family_order = [
            "empty",
            "address_control",
            "register",
            "shared",
            "l1",
            "l2",
            "dram",
            "store",
            "other",
        ]
        present = {mode_family(row.get("mode", "")) for row in rows}
        labels = [label for label in family_order if label in present]
        reference = "empty" if "empty" in labels else labels[0]
        return [
            {
                "source": "mode_family",
                "name": f"baseline_family_{label}",
                "unit": "J",
                "values": [
                    1.0 if mode_family(row.get("mode", "")) == label else 0.0
                    for row in rows
                ],
                "scale": 1.0,
                "constrained": False,
                "term_kind": "baseline",
                "nonzero_modes": label,
                "positive_unique_count": 1,
            }
            for label in labels
            if label != reference
        ]

    raise ValueError(f"unknown baseline terms: {baseline_terms}")


def positive_unique_count(values: list[float]) -> int:
    return len({round(value, 12) for value in values if value > 0.0})


def nonzero_modes(rows: list[dict[str, str]], values: list[float]) -> str:
    modes = sorted(
        {
            row.get("mode", "")
            for row, value in zip(rows, values)
            if abs(value) > 0.0
        }
    )
    return ",".join(modes)


def write_markdown(
    *,
    path: Path,
    rows_used: int,
    features: list[dict[str, Any]],
    metrics: dict[str, float],
    warnings: list[str],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Component Energy Regression Fit\n\n")
        f.write("## Model\n\n")
        f.write(
            "`net_E_J = intercept + sum(beta_i * feature_i) + residual`\n\n"
        )
        f.write("| item | value |\n")
        f.write("|---|---:|\n")
        f.write(f"| rows used | {rows_used} |\n")
        f.write(f"| features used | {max(0, len(features) - 1)} |\n")
        f.write(f"| byte source | {args.byte_source} |\n")
        f.write(f"| baseline terms | {args.baseline_terms} |\n")
        f.write(f"| non-negative constrained fit | {args.non_negative} |\n")
        f.write(f"| min elapsed filter (s) | {args.min_elapsed_s:g} |\n")
        f.write(
            f"| exclude negative net energy | {args.exclude_negative_net_energy} |\n"
        )
        f.write(f"| ridge lambda | {args.ridge_lambda:g} |\n")
        f.write(f"| RMSE (J) | {metrics['rmse']:.6g} |\n")
        f.write(f"| relative RMSE (%) | {metrics['relative_rmse_pct']:.6g} |\n")
        f.write(f"| R2 | {metrics['r2']:.6g} |\n")
        f.write("\n## Coefficients\n\n")
        f.write(
            "| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |\n"
        )
        f.write("|---|---|---:|---|---:|---|---:|---|\n")
        for row in features:
            unconstrained = row.get("unconstrained_estimate", "")
            unconstrained_text = (
                f"{unconstrained:.6g}" if isinstance(unconstrained, float) else ""
            )
            f.write(
                f"| {row['feature']} | {row['source_column']} | "
                f"{row['estimate']:.6g} | {row['unit']} | "
                f"{row['scale']:.6g} | {row['constrained']} | "
                f"{unconstrained_text} | {row['warning']} |\n"
            )
        f.write("\n## Warnings\n\n")
        if warnings:
            for warning in warnings:
                f.write(f"- {warning}\n")
        else:
            f.write("- none\n")
        f.write("\n## Interpretation\n\n")
        f.write(
            "These coefficients are elapsed-aware microbenchmark coefficients, "
            "not physical pure component energies. Static-byte coefficients must "
            "not be reported as SRAM/L2/DRAM physical energy without NCU traffic "
            "validation.\n"
        )
        if args.non_negative:
            f.write(
                "\nA zero coefficient in the constrained fit means the current "
                "matrix does not support a positive independent slope for that "
                "term after elapsed and baseline terms are modeled. It is not "
                "evidence that the physical component consumes zero energy.\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--out-csv", default="results/summary/component_regression_fit.csv")
    parser.add_argument("--out-md", default="results/summary/component_regression_fit.md")
    parser.add_argument(
        "--byte-source",
        choices=["static", "ncu", "prefer-ncu"],
        default="static",
    )
    parser.add_argument("--ridge-lambda", type=float, default=1.0e-9)
    parser.add_argument("--include-placement-failures", action="store_true")
    parser.add_argument(
        "--baseline-terms",
        choices=["none", "family", "mode"],
        default="none",
        help="Add unconstrained nuisance intercepts by component family or mode.",
    )
    parser.add_argument(
        "--non-negative",
        action="store_true",
        help="Constrain elapsed and physical component terms to beta >= 0.",
    )
    parser.add_argument("--max-iter", type=int, default=20000)
    parser.add_argument("--tolerance", type=float, default=1.0e-10)
    parser.add_argument(
        "--include-modes",
        default="",
        help="Comma-separated mode allow-list before fitting.",
    )
    parser.add_argument(
        "--exclude-modes",
        default="",
        help="Comma-separated mode block-list before fitting.",
    )
    parser.add_argument(
        "--min-elapsed-s",
        type=float,
        default=0.0,
        help="Drop rows with elapsed_s below this threshold.",
    )
    parser.add_argument(
        "--exclude-negative-net-energy",
        action="store_true",
        help="Drop rows where net_E_J is negative after idle subtraction.",
    )
    args = parser.parse_args()

    rows = read_rows(Path(args.csv_path), args.include_placement_failures)
    rows = apply_mode_filter(rows, args.include_modes, args.exclude_modes)
    rows = apply_quality_filter(
        rows,
        min_elapsed_s=args.min_elapsed_s,
        exclude_negative_net_energy=args.exclude_negative_net_energy,
    )
    if not rows:
        raise SystemExit("no usable rows")

    feature_specs = select_feature_specs(args.byte_source)
    y = [as_float(row, "net_E_J") for row in rows]

    selected: list[dict[str, Any]] = []
    for source, name, unit in feature_specs:
        values = [as_float(row, source) for row in rows]
        if args.byte_source == "prefer-ncu" and source.startswith("ncu_"):
            static_source = {
                "ncu_shared_bytes": "expected_shared_bytes",
                "ncu_l1_bytes": "expected_l1_bytes",
                "ncu_l2_bytes": "expected_l2_bytes",
                "ncu_dram_bytes": "expected_dram_bytes",
            }.get(source)
            if static_source and max(values) <= 0.0:
                source = static_source
                name = name.replace("_ncu", "_static_fallback")
                values = [as_float(row, source) for row in rows]
        if max(abs(v) for v in values) <= 0.0:
            continue
        if variance(values) <= 0.0:
            continue
        selected.append(
            {
                "source": source,
                "name": name,
                "unit": unit,
                "values": values,
                "scale": median_nonzero_abs(values),
                "constrained": args.non_negative,
                "term_kind": "physical",
                "nonzero_modes": nonzero_modes(rows, values),
                "positive_unique_count": positive_unique_count(values),
            }
        )

    selected.extend(build_baseline_terms(rows, args.baseline_terms))

    warnings: list[str] = []
    if len(rows) <= len(selected) + 1:
        warnings.append(
            "underdetermined: row count is not larger than intercept + feature count"
        )
    if args.byte_source == "static":
        warnings.append(
            "static_expected_bytes: memory coefficients are not actual hardware traffic"
        )
    if args.byte_source in {"ncu", "prefer-ncu"}:
        ncu_present = any(
            max(as_float(row, col) for row in rows) > 0.0
            for col in [
                "ncu_shared_bytes",
                "ncu_l1_bytes",
                "ncu_l2_bytes",
                "ncu_dram_bytes",
            ]
        )
        if not ncu_present:
            warnings.append("missing_ncu_actual_bytes")
    if args.baseline_terms != "none":
        warnings.append(
            f"{args.baseline_terms}_baseline_terms: physical slopes are identified from within-baseline variation"
        )
    if args.non_negative:
        warnings.append(
            "non_negative_fit: elapsed and physical coefficients constrained to be >= 0"
        )

    x_rows: list[list[float]] = []
    for i in range(len(rows)):
        x_rows.append([1.0] + [item["values"][i] / item["scale"] for item in selected])

    try:
        beta_scaled_probe = fit_scaled_ridge(x_rows, y, args.ridge_lambda)
    except ValueError:
        beta_scaled_probe = []

    if args.non_negative:
        constrained = [False] + [bool(item["constrained"]) for item in selected]
        try:
            beta_scaled, solver_iters = fit_scaled_active_set_nnls(
                x_rows,
                y,
                args.ridge_lambda,
                constrained,
                max_iter=args.max_iter,
                tolerance=args.tolerance,
            )
        except ValueError as exc:
            raise SystemExit(f"fit failed: {exc}") from exc
        warnings.append(f"active_set_iterations:{solver_iters}")
    else:
        try:
            beta_scaled = fit_scaled_ridge(x_rows, y, args.ridge_lambda)
        except ValueError as exc:
            raise SystemExit(f"fit failed: {exc}") from exc

    beta_original = [beta_scaled[0]]
    for scaled, item in zip(beta_scaled[1:], selected):
        beta_original.append(scaled / item["scale"])

    beta_probe_original: list[float | None]
    if beta_scaled_probe:
        beta_probe_original = [beta_scaled_probe[0]]
        for scaled, item in zip(beta_scaled_probe[1:], selected):
            beta_probe_original.append(scaled / item["scale"])
    else:
        beta_probe_original = [None for _ in beta_original]

    predictions = [
        sum(beta_original[j] * ([1.0] + [item["values"][i] for item in selected])[j]
            for j in range(len(beta_original)))
        for i in range(len(rows))
    ]
    residuals = [y[i] - predictions[i] for i in range(len(y))]
    rmse = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    y_mean = statistics.mean(y)
    sst = sum((value - y_mean) ** 2 for value in y)
    sse = sum(r * r for r in residuals)
    r2 = 1.0 - sse / sst if sst > 0.0 else 0.0
    relative_rmse_pct = 100.0 * rmse / max(1.0e-12, abs(y_mean))
    if relative_rmse_pct > 20.0:
        warnings.append("high_residual: relative RMSE exceeds 20%")

    elapsed_values = [as_float(row, "elapsed_s") for row in rows]
    positive_elapsed = [v for v in elapsed_values if v > 0.0]
    if positive_elapsed and max(positive_elapsed) / min(positive_elapsed) > 2.0:
        warnings.append("large_elapsed_spread: elapsed max/min exceeds 2")

    output_rows: list[dict[str, Any]] = [
        {
            "feature": "intercept",
            "source_column": "",
            "coefficient_J_per_unit": beta_original[0],
            "estimate": beta_original[0],
            "unit": "J",
            "scale": 1.0,
            "constrained": False,
            "unconstrained_estimate": (
                beta_probe_original[0]
                if isinstance(beta_probe_original[0], float)
                else ""
            ),
            "nonzero_modes": "",
            "warning": "",
        }
    ]
    for idx, (coeff, item) in enumerate(zip(beta_original[1:], selected), start=1):
        warning_parts = []
        estimate = display_value(coeff, item["unit"])
        unconstrained_estimate = ""
        probe_coeff = beta_probe_original[idx]
        if isinstance(probe_coeff, float):
            unconstrained_estimate = display_value(probe_coeff, item["unit"])
            if item["constrained"] and unconstrained_estimate < 0.0:
                warning_parts.append("unconstrained_negative")
        if item["unit"].startswith("pJ/") and estimate < 0.0:
            warning_parts.append("negative_coefficient")
        if item["constrained"] and abs(estimate) <= 1.0e-18:
            warning_parts.append("zero_bound_or_not_identified")
        if item["source"].startswith("expected_") and "bytes" in item["source"]:
            warning_parts.append("static_byte")
        if (
            item["term_kind"] == "physical"
            and item["positive_unique_count"] < 3
        ):
            warning_parts.append("low_positive_variation")
        output_rows.append(
            {
                "feature": item["name"],
                "source_column": item["source"],
                "coefficient_J_per_unit": coeff,
                "estimate": estimate,
                "unit": item["unit"],
                "scale": item["scale"],
                "constrained": item["constrained"],
                "unconstrained_estimate": unconstrained_estimate,
                "nonzero_modes": item.get("nonzero_modes", ""),
                "warning": ";".join(warning_parts),
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "feature",
                "source_column",
                "coefficient_J_per_unit",
                "estimate",
                "unit",
                "scale",
                "constrained",
                "unconstrained_estimate",
                "nonzero_modes",
                "warning",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    metrics = {
        "rmse": rmse,
        "relative_rmse_pct": relative_rmse_pct,
        "r2": r2,
    }
    write_markdown(
        path=Path(args.out_md),
        rows_used=len(rows),
        features=output_rows,
        metrics=metrics,
        warnings=warnings,
        args=args,
    )

    print(f"wrote csv: {args.out_csv}")
    print(f"wrote markdown: {args.out_md}")
    print(f"rows used: {len(rows)}")
    print(f"features used: {len(selected)}")
    print(f"relative RMSE: {relative_rmse_pct:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
