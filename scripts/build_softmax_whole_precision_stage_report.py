#!/usr/bin/env python3
"""Build the Korean technical report source and canonical HTML artifact input.

This consumes only the fail-closed stage-isolation analysis output and the
matching sm86 SASS audit.  It intentionally does not mix the older EX2
operand-rate ATC metric with complete-Softmax pJ/logical-output-element data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = "20260727_stageiso_v1"
RUN_DIR = ROOT / "results/raw" / f"rtx3090_softmax_whole_precision_stage_isolation_{RUN_TAG}"
RESULT_PREFIX = f"rtx3090_softmax_whole_precision_stage_isolation_{RUN_TAG}"
DEFAULT_OUT_DIR = ROOT / "docs/results"
T95_N3 = 4.30265272991

STAGES = ("exp", "reduction", "normalization")
STAGE_LABELS = {
    "exp": "exp",
    "reduction": "max + sum reduction",
    "normalization": "normalization",
}
POLICIES = {
    "exp": ("fp16_io_fp32_all", "exp_fp16_scalar", "exp_fp16x2"),
    "reduction": (
        "fp16_io_fp32_all",
        "reduction_fp16_scalar",
        "reduction_fp16x2",
    ),
    "normalization": (
        "fp16_io_fp32_all",
        "normalization_fp16_scalar",
        "normalization_fp16x2",
    ),
}
PRECISION_LABEL = {
    "fp16_io_fp32_all": "FP32 stages (FP16 I/O)",
    "exp_fp16_scalar": "scalar FP16",
    "exp_fp16x2": "packed FP16",
    "reduction_fp16_scalar": "scalar FP16",
    "reduction_fp16x2": "packed FP16",
    "normalization_fp16_scalar": "scalar FP16",
    "normalization_fp16x2": "packed FP16",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{field!r} is not numeric in {row}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{field!r} is not finite in {row}")
    return value


def integer(row: dict[str, Any], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{field!r} is not an integer in {row}") from exc


def repo_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def fmt_sci(value: float) -> str:
    return f"{value:.6g}"


def t95(mean: float, sample_std: float, n: int) -> tuple[float, float]:
    if n != 3:
        raise ValueError("the fixed report protocol expects n=3")
    half_width = T95_N3 * sample_std / math.sqrt(n)
    return mean - half_width, mean + half_width


def load_evidence(run_dir: Path, sass_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    analysis_dir = run_dir / "analysis"
    cells = read_csv(analysis_dir / "validated_cells.csv")
    summary = read_csv(analysis_dir / "summary.csv")
    analysis = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    sass = json.loads(sass_path.read_text(encoding="utf-8"))
    if analysis.get("status") != "pass" or analysis.get("validated_cell_count") != 27:
        raise ValueError("analysis input is not a certified 27-cell passing run")
    if analysis.get("schema_version") != "softmax_whole_precision_stage_isolation_analysis_v1":
        raise ValueError("analysis schema is not the certified stage-isolation schema")
    if analysis.get("allow_partial") is not False:
        raise ValueError("report requires a complete, not partial, analyzed run")
    if analysis.get("primary_metric") != "net_pJ_per_logical_output_element":
        raise ValueError("analysis primary metric is not whole-Softmax net pJ/output")
    if analysis.get("interpretation_boundary") != (
        "complete Softmax policy comparison, not EX2 operand-rate ATC or pure SFU/MUFU energy"
    ):
        raise ValueError("analysis interpretation boundary is not the certified whole-Softmax contract")
    analysis_manifest = analysis.get("manifest", {})
    manifest_sha = manifest.get("binary", {}).get("sha256")
    current_manifest_sha = hashlib.sha256(
        (run_dir / "manifest.json").read_bytes()
    ).hexdigest()
    if analysis_manifest.get("sha256") != current_manifest_sha:
        raise ValueError("analysis artifact does not bind to the current manifest SHA-256")
    if analysis_manifest.get("run_tag") != manifest.get("run_tag"):
        raise ValueError("analysis artifact run tag does not match the current manifest")
    if analysis_manifest.get("protocol_revision") != manifest.get("protocol_revision"):
        raise ValueError("analysis artifact protocol revision does not match the current manifest")
    if sass.get("overall", {}).get("pass") is not True:
        raise ValueError("SASS audit did not pass")
    sass_sha = sass.get("binary", {}).get("sha256")
    if not all(isinstance(value, str) and len(value) == 64 for value in (manifest_sha, sass_sha)):
        raise ValueError("manifest or SASS audit has no valid binary SHA-256")
    if manifest_sha.lower() != sass_sha.lower():
        raise ValueError(
            "SASS audit binary SHA-256 does not match the analyzed-run manifest"
        )
    return cells, summary, analysis, sass


def summarize(
    cells: list[dict[str, str]], summary: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    absolute = {
        (row["stage_group"], row["policy"]): row
        for row in summary
        if row["summary_kind"] == "absolute"
    }
    paired = {
        (row["stage_group"], row["policy"]): row
        for row in summary
        if row["summary_kind"] == "paired_delta_vs_baseline"
    }
    if len(absolute) != 9 or len(paired) != 6:
        raise ValueError("unexpected stage-summary cardinality")

    stage_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    stage_results: dict[str, dict[str, Any]] = {}
    for stage_index, stage in enumerate(STAGES, start=1):
        policies = POLICIES[stage]
        result: dict[str, Any] = {"stage": stage, "stage_label": STAGE_LABELS[stage]}
        for policy_index, policy in enumerate(policies, start=1):
            row = absolute[(stage, policy)]
            metric = number(row, "mean_net_pJ_per_logical_output_element")
            sample_std = number(row, "sample_std_net_pJ_per_logical_output_element")
            n = integer(row, "session_count")
            stage_rows.append(
                {
                    "stage_order": stage_index,
                    "stage": stage,
                    "stage_label": STAGE_LABELS[stage],
                    "policy_order": policy_index,
                    "policy": policy,
                    "precision": PRECISION_LABEL[policy],
                    "fresh_sessions": n,
                    "mean_net_pj_per_output": metric,
                    "sample_std_net_pj_per_output": sample_std,
                    "median_net_pj_per_output": number(row, "median_net_pJ_per_logical_output_element"),
                    "min_net_pj_per_output": number(row, "min_net_pJ_per_logical_output_element"),
                    "max_net_pj_per_output": number(row, "max_net_pJ_per_logical_output_element"),
                }
            )
            result[policy] = stage_rows[-1]
        for policy_index, policy in enumerate(policies[1:], start=2):
            row = paired[(stage, policy)]
            average = number(row, "mean_net_pJ_per_logical_output_element")
            sample_std = number(row, "sample_std_net_pJ_per_logical_output_element")
            n = integer(row, "session_count")
            low, high = t95(average, sample_std, n)
            values = []
            for session in (1, 2, 3):
                base = next(
                    item
                    for item in cells
                    if item["stage_group"] == stage
                    and item["policy"] == policies[0]
                    and integer(item, "session_index_within_stage") == session
                )
                treatment = next(
                    item
                    for item in cells
                    if item["stage_group"] == stage
                    and item["policy"] == policy
                    and integer(item, "session_index_within_stage") == session
                )
                values.append(
                    number(treatment, "net_pJ_per_logical_output_element")
                    - number(base, "net_pJ_per_logical_output_element")
                )
            paired_rows.append(
                {
                    "stage_order": stage_index,
                    "stage": stage,
                    "stage_label": STAGE_LABELS[stage],
                    "policy_order": policy_index,
                    "policy": policy,
                    "precision": PRECISION_LABEL[policy],
                    "contrast_label": f"{STAGE_LABELS[stage]} · {PRECISION_LABEL[policy]}",
                    "fresh_sessions": n,
                    "mean_delta_net_pj_per_output": average,
                    "sample_std_delta_net_pj_per_output": sample_std,
                    "t95_low_delta_net_pj_per_output": low,
                    "t95_high_delta_net_pj_per_output": high,
                    "min_delta_net_pj_per_output": min(values),
                    "max_delta_net_pj_per_output": max(values),
                    "negative_session_count": sum(value < 0.0 for value in values),
                    "positive_session_count": sum(value > 0.0 for value in values),
                }
            )
            result[policy] = paired_rows[-1]
        stage_results[stage] = result
    return stage_rows, paired_rows, stage_results


def validation_rows(cells: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(STAGES, start=1):
        for policy_index, policy in enumerate(POLICIES[stage], start=1):
            match = next(item for item in cells if item["stage_group"] == stage and item["policy"] == policy)
            rows.append(
                {
                    "stage_order": stage_index,
                    "stage_label": STAGE_LABELS[stage],
                    "policy_order": policy_index,
                    "policy": policy,
                    "precision": PRECISION_LABEL[policy],
                    "max_abs_error": number(match, "validation_max_abs_error"),
                    "max_row_sum_error": number(match, "validation_max_row_sum_error"),
                    "preheat_actual_s": number(match, "preheat_actual_s"),
                    "trace_r2": number(match, "energy_trace_r2"),
                }
            )
    return rows


def audit_rows(cells: list[dict[str, str]], sass: dict[str, Any]) -> list[dict[str, Any]]:
    preheat = [number(row, "preheat_actual_s") for row in cells]
    trace_r2 = [number(row, "energy_trace_r2") for row in cells]
    temperature = [
        value
        for row in cells
        for value in (number(row, "temperature_start_C"), number(row, "temperature_end_C"))
    ]
    return [
        {
            "check": "evidence binding",
            "coverage": "9 sessions / 27 roles",
            "result": "pass",
            "meaning": "manifest, raw CSV, energy trace, binary hash, runner hash, cyclic schedule, schema and denominator gates all passed",
        },
        {
            "check": "preheat and trace quality",
            "coverage": f"preheat {min(preheat):.3f}–{max(preheat):.3f} s; R² {min(trace_r2):.9f}–{max(trace_r2):.9f}",
            "result": "pass",
            "meaning": "shared FP32-stage baseline preheat is within the 16–25 s gate; qualified Theil–Sen energy traces exceed R²=0.98",
        },
        {
            "check": "placement and numerics",
            "coverage": "27 / 27 roles",
            "result": "pass",
            "meaning": "SMID placement, finite-output, FP64-reference absolute-error and row-sum gates passed",
        },
        {
            "check": "recorded thermal context",
            "coverage": f"{min(temperature):.0f}–{max(temperature):.0f} °C",
            "result": "recorded",
            "meaning": "temperature is recorded context, not a randomized causal adjustment or a hard rejection gate",
        },
        {
            "check": "sm86 code-path audit",
            "coverage": sass["binary"]["sha256"][:12],
            "result": "pass",
            "meaning": "PTX/SASS policy specializations match the scalar/packed reduction and FP16-rounded reciprocal contracts",
        },
    ]


def report_markdown(
    stage_rows: list[dict[str, Any]],
    paired_rows: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    audit: list[dict[str, Any]],
    sass: dict[str, Any],
) -> str:
    stage_map = {(row["stage"], row["policy"]): row for row in stage_rows}
    paired_map = {(row["stage"], row["policy"]): row for row in paired_rows}
    def abs_value(stage: str, index: int) -> float:
        return stage_map[(stage, POLICIES[stage][index])]["mean_net_pj_per_output"]

    def delta(stage: str, index: int) -> dict[str, Any]:
        return paired_map[(stage, POLICIES[stage][index])]

    lines = [
        "# RTX 3090 전체 Softmax 정밀도 단계 분리 분석 (2026-07-27)",
        "",
        "## 기술 요약",
        "",
        "**네, exp·max+sum reduction·normalization을 각각 FP32 / scalar FP16 / packed FP16으로 분리해 측정해야 합니다.** 이 보고서는 그 설계로 실행한 complete-Softmax 결과다. stage 비교에서는 FP16 input/output을 고정하고, 공통 기준 `fp16_io_fp32_all`은 세 compute stage를 FP32로 수행한다. 따라서 수치는 기존 EX2 Operand-rate ATC의 `pJ/added logical exponent result`가 아니라 **`net pJ/logical Softmax output element`** 이며 서로 합산·차감하면 안 된다.",
        "",
        f"S=512, grid=16 CTA, 20 s shared-baseline preheat, 13 s role 조건에서 fresh CUDA-process session 3개를 ABC/CAB/BCA로 교차했다. paired mean은 exp scalar {fmt(delta('exp', 1)['mean_delta_net_pj_per_output'])} pJ/output, exp packed {fmt(delta('exp', 2)['mean_delta_net_pj_per_output'])}; reduction scalar {fmt(delta('reduction', 1)['mean_delta_net_pj_per_output'])}, reduction packed {fmt(delta('reduction', 2)['mean_delta_net_pj_per_output'])}; normalization scalar {fmt(delta('normalization', 1)['mean_delta_net_pj_per_output'])}, normalization packed {fmt(delta('normalization', 2)['mean_delta_net_pj_per_output'])} (모두 baseline 대비)다.",
        "",
        "그러나 **6개의 paired contrast 모두 fresh-session n=3 descriptive t95 interval이 0을 포함한다.** 따라서 현재 데이터는 구현 선택을 확정하는 energy proof가 아니다. 관찰된 방향성은 exp의 낮은 mean, scalar reduction의 높은 mean, packed reduction의 baseline 근접 mean이지만, 이를 순수 functional-unit energy나 보편적 FP16 이득으로 해석하지 않는다.",
        "",
        "## 단계별 결과와 시각 증거",
        "",
        "![stage absolute session spread](../assets/softmax_whole_precision_stage_isolation/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1_absolute_session_spread.png)",
        "",
        "각 값은 complete Softmax 한 출력 원소당 idle-subtracted NVML GPU/device total-energy trace다. raw fresh session 점과 평균/설명적 t95 interval을 함께 표시했으며, 27개 role을 독립 표본으로 pool하지 않았다.",
        "",
        "| 단계 | FP16 I/O + FP32-stage mean | scalar FP16 mean | packed FP16 mean | scalar−기준 | packed−기준 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for stage in STAGES:
        scalar = delta(stage, 1)
        packed = delta(stage, 2)
        lines.append(
            f"| {STAGE_LABELS[stage]} | {fmt(abs_value(stage, 0))} | {fmt(abs_value(stage, 1))} | {fmt(abs_value(stage, 2))} | {fmt(scalar['mean_delta_net_pj_per_output'])} | {fmt(packed['mean_delta_net_pj_per_output'])} |"
        )
    lines.extend(
        [
            "",
            "음수 contrast는 같은 fresh session의 FP32-stage baseline보다 낮게 관측된 net energy를 뜻한다. 기준 mean 자체도 stage group별 independent session 날짜/시간대에 따라 달라질 수 있으므로, stage group 사이 absolute mean을 직접 순위화하지 않는다.",
            "",
            "![paired contrasts](../assets/softmax_whole_precision_stage_isolation/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1_paired_contrasts.png)",
            "",
            "| paired contrast | mean Δ | descriptive t95 | session range | sign (− / +) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in paired_rows:
        lines.append(
            f"| {row['contrast_label']} | {fmt(row['mean_delta_net_pj_per_output'])} | [{fmt(row['t95_low_delta_net_pj_per_output'])}, {fmt(row['t95_high_delta_net_pj_per_output'])}] | [{fmt(row['min_delta_net_pj_per_output'])}, {fmt(row['max_delta_net_pj_per_output'])}] | {row['negative_session_count']} / {row['positive_session_count']} |"
        )
    lines.extend(
        [
            "",
            "`reduction · scalar FP16`은 세 session 모두 양수였지만 n=3 interval은 여전히 0을 포함한다. `exp · scalar FP16`은 세 session 모두 음수였지만 동일하게 interval만으로 개선을 확정할 수 없다. 이 불확실성 표기는 부정 결과가 아니라, 다음 확인 실험의 범위를 제한하기 위한 근거다.",
            "",
            "![within-session paths](../assets/softmax_whole_precision_stage_isolation/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1_within_session_paths.png)",
            "",
            "## 범위·분모·설계",
            "",
            "- GPU: full NVIDIA GeForce RTX 3090, CC 8.6, 82 SM, sm86 binary SHA `" + sass["binary"]["sha256"] + "`.",
            "- fixed kernel shape: S=512, 256 threads/CTA, CTA 16개, CTA당 독립 Softmax row 2개, logit scale=4.",
            "- primary denominator: `Noutput = grid_blocks × rows_per_block × iterations × S`; `net_pJ/output = (Etrace − Pidle × elapsed) × 1e12 / Noutput`.",
            "- trace energy: NVML GPU/device total-energy samples를 Theil–Sen slope로 fit한 qualified trace energy. endpoint fallback row는 분석에서 거부한다.",
            "- schedule: stage group마다 baseline/scalar/packed를 ABC, CAB, BCA로 한 번씩 배치하고, 각 schedule은 새 binary process/CUDA context에서 실행했다.",
            "- preheat: baseline `fp16_io_fp32_all`을 session당 한 번만 20 s 목표로 preheat했다. 그 뒤 각 policy calibration trial과 같은 ABC/CAB/BCA 순서의 unrecorded full-policy warm-up block을 실행한 뒤 measured roles를 시작했다. 이 conditioning energy는 numerator에 넣지 않았다.",
            "- order caveat: ABC/CAB/BCA는 policy position을 한 번씩 회전하지만, pre-measurement conditioning과 measured block의 directed adjacent carryover를 완전 counterbalance하지 않는다. 따라서 order/thermal carryover를 causal effect로 분리하지 않으며 결과를 descriptive로 제한한다.",
            "",
            "`fp16_io_fp32_all`이 primary baseline이며 FP16 I/O와 FP32 exp/reduction/normalization을 고정한다. `fp32_io_fp32_all`은 FP32 I/O까지 바꾸는 separate end-to-end reference라 I/O까지 바뀌므로 이번 27-role stage-isolation primary contrast에는 넣지 않았다. full FP32 / scalar-all / packed-all policy는 validation-only로 의미 검증했지만, stage effect를 더해 all-FP16 energy를 예측하지 않는다.",
            "",
            "## 구현이 실제로 뜻하는 것",
            "",
            "- **exp scalar / packed:** scalar는 `ex2.approx.f16` 4개, packed는 `ex2.approx.f16x2` 2개 PTX op로 각각 두 row×두 element를 처리한다. 이 frozen sm86 build에서는 둘 다 최종 SASS `MUFU.EX2.F16` 4개로 lowering됐다. packed PTX가 하나의 physical two-lane MUFU issue라는 뜻은 아니다.",
            "- **max+sum reduction:** scalar는 scalar PTX `max.f16`/`add.f16` 각각 18개와 16-bit shared tree다. packed는 CTA의 **서로 독립적인 두 row**를 half2의 low/high lane으로 묶어 `max.f16x2`/`add.f16x2` 각각 9개를 수행한다. scalar SASS도 HADD2/HMNMX2 encoding을 쓰지만 `.H0_H0` lane replication이므로 두 independent packed lane과 같다고 부르지 않는다.",
            "- **normalization:** scalar는 FP16 multiply 4개, packed는 half2 multiply 2개다. 두 정책 모두 `hrcp(half)`가 FP16→FP32 `RCP`→FP16 rounding으로 lowering되며 native FP16 reciprocal은 아니다. 따라서 이 stage는 “FP16-rounded reciprocal + scalar/packed probability multiply” 비교다.",
            "",
            "## 정확도·경로·측정 품질",
            "",
            "모든 27 measured role이 manifest/raw/trace hash, exact cyclic order, logical denominator, preheat, qualified trace, SMID, finite-output, FP64 reference gate를 통과했다. max absolute error 범위는 "
            + fmt_sci(min(row["max_abs_error"] for row in validation))
            + "–"
            + fmt_sci(max(row["max_abs_error"] for row in validation))
            + ", row-sum error 범위는 "
            + fmt_sci(min(row["max_row_sum_error"] for row in validation))
            + "–"
            + fmt_sci(max(row["max_row_sum_error"] for row in validation))
            + "였다. dominated-input validation pattern의 tail underflow count는 FP16 output에서 예상되는 기록값이며, non-finite failure는 0이다.",
            "",
            "![quality gates](../assets/softmax_whole_precision_stage_isolation/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1_quality_gates.png)",
            "",
            "| check | coverage | result | meaning |",
            "|---|---|---|---|",
        ]
    )
    for row in audit:
        lines.append(f"| {row['check']} | {row['coverage']} | {row['result']} | {row['meaning']} |")
    lines.extend(
        [
            "",
            "## 한계·불확실성·robustness",
            "",
            "1. n=3 fresh session이라 t95 interval이 넓다. interval은 descriptive diagnostic이며 p-value나 causal effect size로 해석하지 않는다.",
            "2. 이 측정은 RTX 3090 하나, S=512 / CTA=16 하나, logit scale=4 하나의 operating point다. CTA/S sweep, stage interaction full factorial, 다른 GPU generalization은 하지 않았다.",
            "3. stage policy는 complete Softmax path 전체를 실행한다. 차이는 stage를 바꾼 implementation path이므로 pure MUFU/SFU/FP16-ALU circuit energy가 아니다.",
            "4. temperature는 52–58 °C 범위로 기록했지만 randomized treatment가 아니므로 thermal coefficient나 보정 인과변수로 쓰지 않았다.",
            "5. 20 s baseline preheat 뒤 schedule-order calibration과 unrecorded same-order full-policy warm-up이 있었다. position은 회전했지만 directed adjacent carryover는 완전 counterbalance하지 않았으므로, 그 thermal/scheduling effect를 stage effect로 분리할 수 없다.",
            "6. stage contrast를 선형 합산해 `fp16_scalar_all` 또는 `fp16x2_all`의 에너지를 예측하면 안 된다. handoff rounding, data dependency, scheduling, shared-memory layout, compiler lowering interaction이 남는다.",
            "",
            "## 권장 다음 단계",
            "",
            "추가 CTA/S sweep 대신, 판단이 필요한 후보만 같은 S=512/CTA=16 조건에서 별도 confirmation을 한다. 최소 후보는 (a) exp packed vs FP32-stage baseline, (b) scalar reduction vs FP32-stage baseline이다. 각 후보는 두 정책만 fresh process에서 AB/BA로 counterbalance한 3개 이상의 추가 session으로 제한한다. 그 결과가 없으면 현재 implementation 선택은 accuracy/throughput 요구로 결정하고, energy superiority를 주장하지 않는다.",
            "",
            "## 후속 질문",
            "",
            "- fixed-clock 또는 external high-resolution meter가 exp/reduction contrast의 interval을 실제로 줄이는가?",
            "- A100/H100에서 scalar·packed reduction의 PTX/SASS lowering과 board-level direction이 유지되는가?",
            "- numerical tolerance가 더 엄격한 workload에서 FP16 reduction/normalization의 acceptable boundary는 어디인가?",
            "",
            "## 재현 명령",
            "",
            "```bash",
            "source scripts/activate_softmax_experiment_env.sh",
            "python3 scripts/analyze_softmax_whole_precision_stage_isolation.py \\",
            f"  --run-dir results/raw/rtx3090_softmax_whole_precision_stage_isolation_{RUN_TAG}",
            "python3 scripts/plot_softmax_whole_precision_stage_isolation.py \\",
            f"  --run-dir results/raw/rtx3090_softmax_whole_precision_stage_isolation_{RUN_TAG} \\",
            "  --out-dir docs/assets/softmax_whole_precision_stage_isolation",
            "python3 scripts/audit_softmax_whole_precision_sass.py \\",
            "  --binary build-whole-precision-rtx3090/a100_fp16_softmax_whole_precision_energy \\",
            "  --cuobjdump \"$CUOBJDUMP\" --fail-on-unexpected",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def artifact_payload(
    run_dir: Path,
    sass_path: Path,
    stage_rows: list[dict[str, Any]],
    paired_rows: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    audit: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    analysis_path = run_dir / "analysis" / "analysis.json"
    cells_path = run_dir / "analysis" / "validated_cells.csv"
    summary_path = run_dir / "analysis" / "summary.csv"
    manifest_path = run_dir / "manifest.json"
    analysis_source = {
        "id": "analysis",
        "label": "Fail-closed whole-Softmax stage analysis",
        "path": repo_path(summary_path),
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT * FROM read_csv_auto('{repo_path(summary_path)}');",
            "description": "The chart/table source is the analyzer summary CSV. The preceding fail-closed analyzer validates raw/trace/manifest SHA bindings, exact stage schedule, qualified trace, SMID, numerical and denominator gates.",
            "tables_used": [repo_path(analysis_path), repo_path(cells_path), repo_path(summary_path), repo_path(manifest_path)],
            "metric_definitions": [
                "Primary metric = net pJ per logical Softmax output element.",
                "A fresh session is the independent repeat; 27 measured roles are not pooled as 27 independent samples.",
            ],
            "filters": ["RTX 3090", "S=512", "grid CTA=16", "FP16 I/O fixed", "3 fresh sessions per stage-policy"],
        },
    }
    sass_source = {
        "id": "sass",
        "label": "sm86 PTX/SASS path audit",
        "path": repo_path(sass_path),
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT * FROM read_json_auto('{repo_path(sass_path)}');",
            "description": "Audits the compiled sm86 specialization for scalar/packed exp, scalar/packed max+sum reduction, and FP16-rounded reciprocal normalization lowering.",
            "tables_used": [repo_path(sass_path)],
            "metric_definitions": ["Static PTX/SASS instruction counts are path evidence, not energy measurements."],
            "filters": ["native sm86", "whole-Softmax precision kernel", "fixed S=512 / two rows per CTA"],
        },
    }
    sources = [analysis_source, sass_source]
    analysis_quality = audit[:4]
    sass_quality = audit[4:]
    return {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "RTX 3090 전체 Softmax 정밀도 단계 분리 분석",
            "description": "S=512, CTA=16에서 exp·max/sum·normalization을 FP32, scalar FP16, packed FP16으로 분리한 complete-Softmax energy analysis.",
            "generatedAt": analysis["generated_at"],
            "sources": sources,
            "charts": [
                {
                    "id": "stage_energy",
                    "title": "Stage-isolated mean net energy",
                    "subtitle": "Three fresh sessions per policy; FP16 I/O is fixed and values are complete-Softmax net pJ/logical output element.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "How do the FP32-stage, scalar FP16, and packed FP16 paths compare within each isolated stage group?",
                    "rationale": "Grouped discrete bars compare the three complete-path policy means per stage; the detailed table retains n=3 spread.",
                    "comparisonContext": {
                        "baseline": "FP16 I/O + FP32 exp/reduction/normalization within each stage group",
                        "denominator": "one logical Softmax output element",
                        "grain": "stage-policy mean across three fresh sessions",
                        "unit": "net pJ/logical output element",
                    },
                    "dataset": "stage_summary",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "stage_label", "type": "ordinal", "label": "Isolated stage"},
                        "y": {"field": "mean_net_pj_per_output", "type": "quantitative", "label": "Mean net energy", "unit": "pJ/logical output element", "format": "number"},
                        "tooltip": [
                            {"field": "stage_label", "type": "nominal", "label": "Stage"},
                            {"field": "precision", "type": "nominal", "label": "Policy"},
                            {"field": "mean_net_pj_per_output", "type": "quantitative", "label": "Mean", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "sample_std_net_pj_per_output", "type": "quantitative", "label": "Session SD", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "fresh_sessions", "type": "quantitative", "label": "Fresh sessions", "format": "number"},
                        ],
                        "color": {"field": "precision", "type": "nominal", "label": "Precision path"},
                    },
                    "palette": {"kind": "categorical", "name": "whole-softmax-precision"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "bottom"},
                    "referenceLines": [{"axis": "y", "value": 0, "label": "0", "color": "neutral", "lineStyle": "solid"}],
                },
                {
                    "id": "paired_delta",
                    "title": "Paired mean delta versus the FP32-stage baseline",
                    "subtitle": "Negative means lower observed net energy in the same fresh session; n=3 and intervals are descriptive only.",
                    "type": "bar",
                    "intent": "comparison",
                    "question": "What is the session-paired direction and size of each scalar/packed stage contrast?",
                    "rationale": "A signed bar chart centers the six paired mean contrasts on zero while the table preserves session spread and t95 diagnostics.",
                    "comparisonContext": {
                        "baseline": "same-session fp16_io_fp32_all",
                        "denominator": "one logical Softmax output element",
                        "grain": "mean of three session-paired deltas",
                        "unit": "net pJ/logical output element",
                    },
                    "dataset": "paired_contrasts",
                    "sourceId": "analysis",
                    "encodings": {
                        "x": {"field": "contrast_label", "type": "ordinal", "label": "Paired contrast"},
                        "y": {"field": "mean_delta_net_pj_per_output", "type": "quantitative", "label": "Mean paired delta", "unit": "pJ/logical output element", "format": "number"},
                        "tooltip": [
                            {"field": "contrast_label", "type": "nominal", "label": "Contrast"},
                            {"field": "mean_delta_net_pj_per_output", "type": "quantitative", "label": "Mean delta", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "t95_low_delta_net_pj_per_output", "type": "quantitative", "label": "Descriptive t95 low", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "t95_high_delta_net_pj_per_output", "type": "quantitative", "label": "Descriptive t95 high", "unit": "pJ/logical output element", "format": "number"},
                            {"field": "fresh_sessions", "type": "quantitative", "label": "Fresh sessions", "format": "number"},
                        ],
                        "color": {"field": "precision", "type": "nominal", "label": "Precision path"},
                    },
                    "palette": {"kind": "categorical", "name": "whole-softmax-precision"},
                    "labels": {"values": "auto"},
                    "layout": "full",
                    "surface": {"surface": "export", "showControls": False, "viewMode": "both"},
                    "legend": {"position": "bottom"},
                    "referenceLines": [{"axis": "y", "value": 0, "label": "no observed difference", "color": "neutral", "lineStyle": "solid"}],
                },
            ],
            "tables": [
                {
                    "id": "stage_summary_table",
                    "title": "Fresh-session absolute policy summary",
                    "subtitle": "One row is a policy mean across three fresh sessions in one stage group.",
                    "dataset": "stage_summary",
                    "sourceId": "analysis",
                    "defaultSort": {"field": "stage_label", "direction": "asc"},
                    "density": "spacious",
                    "layout": "full",
                    "columns": [
                        {"field": "stage_label", "label": "Stage"},
                        {"field": "precision", "label": "Policy"},
                        {"field": "fresh_sessions", "label": "Fresh sessions", "format": "number"},
                        {"field": "mean_net_pj_per_output", "label": "Mean net pJ/output", "format": "number"},
                        {"field": "sample_std_net_pj_per_output", "label": "Session SD", "format": "number"},
                        {"field": "median_net_pj_per_output", "label": "Median", "format": "number"},
                        {"field": "min_net_pj_per_output", "label": "Min", "format": "number"},
                        {"field": "max_net_pj_per_output", "label": "Max", "format": "number"},
                    ],
                },
                {
                    "id": "paired_contrast_table",
                    "title": "Paired contrast uncertainty",
                    "subtitle": "Every row is three fresh-session paired deltas against the common FP32-stage baseline; t95 is descriptive, not a selection test.",
                    "dataset": "paired_contrasts",
                    "sourceId": "analysis",
                    "defaultSort": {"field": "contrast_label", "direction": "asc"},
                    "density": "spacious",
                    "layout": "full",
                    "columns": [
                        {"field": "contrast_label", "label": "Contrast"},
                        {"field": "mean_delta_net_pj_per_output", "label": "Mean Δ", "format": "number"},
                        {"field": "sample_std_delta_net_pj_per_output", "label": "Session SD", "format": "number"},
                        {"field": "t95_low_delta_net_pj_per_output", "label": "t95 low", "format": "number"},
                        {"field": "t95_high_delta_net_pj_per_output", "label": "t95 high", "format": "number"},
                        {"field": "negative_session_count", "label": "Negative sessions", "format": "number"},
                        {"field": "positive_session_count", "label": "Positive sessions", "format": "number"},
                    ],
                },
                {
                    "id": "quality_table",
                    "title": "Evidence and measurement-quality gates",
                    "subtitle": "All rows are supporting validity evidence; temperature is context rather than a causal adjustment.",
                    "dataset": "analysis_quality",
                    "sourceId": "analysis",
                    "defaultSort": {"field": "check", "direction": "asc"},
                    "density": "spacious",
                    "layout": "full",
                    "columns": [
                        {"field": "check", "label": "Check"},
                        {"field": "coverage", "label": "Coverage"},
                        {"field": "result", "label": "Result"},
                        {"field": "meaning", "label": "Meaning"},
                    ],
                },
                {
                    "id": "sass_audit_table",
                    "title": "sm86 compiled-path audit",
                    "subtitle": "One static code-path audit summary row; it is not a board-energy measurement.",
                    "dataset": "sass_quality",
                    "sourceId": "sass",
                    "defaultSort": {"field": "check", "direction": "asc"},
                    "density": "spacious",
                    "layout": "full",
                    "columns": [
                        {"field": "check", "label": "Check"},
                        {"field": "coverage", "label": "Binary hash"},
                        {"field": "result", "label": "Result"},
                        {"field": "meaning", "label": "Meaning"},
                    ],
                },
            ],
            "blocks": [
                {"id": "title", "type": "markdown", "body": "# RTX 3090 전체 Softmax 정밀도 단계 분리 분석"},
                {
                    "id": "technical_summary",
                    "type": "markdown",
                    "sourceId": "analysis",
                    "body": "## 기술 요약\n\n**exp·max/sum reduction·normalization을 각각 FP32, scalar FP16, packed FP16으로 분리해 complete Softmax를 측정했다.** primary unit은 `net pJ/logical Softmax output element`이며, 기존 EX2 Operand-rate ATC의 `pJ/added logical exponent result`와 다르다. n=3 paired contrast가 모두 descriptive t95 interval에서 0을 포함하므로, 이번 결과는 energy superiority를 확정하지 않는다.",
                },
                {
                    "id": "energy_result_intro",
                    "type": "markdown",
                    "sourceId": "analysis",
                    "body": "## 방향성은 보이나, 선택 결론은 아직 이르다\n\nexp stage의 paired mean은 scalar와 packed 모두 음수였고, scalar reduction은 세 session 모두 양수였다. 반면 packed reduction은 baseline 근처 평균, normalization은 양의 평균과 큰 spread를 보였다. 이들은 제한된 coordinate의 관측이며 pure hardware-unit energy가 아니다.",
                },
                {"id": "stage_energy_block", "type": "chart", "chartId": "stage_energy"},
                {"id": "stage_table_block", "type": "table", "tableId": "stage_summary_table"},
                {
                    "id": "paired_result_intro",
                    "type": "markdown",
                    "sourceId": "analysis",
                    "body": "## paired contrast와 불확실성\n\n같은 fresh CUDA process 안에서 baseline과 treatment를 pairing했고, ABC/CAB/BCA로 position을 정확히 한 번씩 순환했다. 다만 fresh session은 3개뿐이므로 mean과 t95는 다음 confirmation의 범위를 정하는 descriptive 자료다.",
                },
                {"id": "paired_chart_block", "type": "chart", "chartId": "paired_delta"},
                {"id": "paired_table_block", "type": "table", "tableId": "paired_contrast_table"},
                {
                    "id": "scope_definition",
                    "type": "markdown",
                    "sourceId": "analysis",
                    "body": "## 범위·분모·방법\n\nRTX 3090 full 82-SM, sm86, S=512, 256 threads/CTA, grid CTA=16, CTA당 독립 row 2개, logit scale=4를 고정했다. FP16 I/O를 공통으로 두고 지정한 compute stage만 바꿨다. `net pJ/output = (qualified trace energy − idle power × elapsed) × 1e12 / logical output elements`다. 각 role은 약 13 s이고, baseline preheat는 session당 약 20 s다. 그 뒤 schedule-order calibration과 같은 순서의 unrecorded full-policy warm-up이 있으므로, ABC/CAB/BCA는 position만 회전하고 directed carryover를 완전히 counterbalance하지 않는다.",
                },
                {
                    "id": "implementation_definition",
                    "type": "markdown",
                    "sourceId": "sass",
                    "body": "## 컴파일된 scalar/packed path의 의미\n\nexp는 scalar `ex2.approx.f16` 4개와 packed `ex2.approx.f16x2` 2개 PTX를 보였지만, fixed sm86 binary에서 둘 다 `MUFU.EX2.F16` 4개로 lowering됐다. reduction packed는 CTA의 독립 두 row를 half2 lane에 둔 9개 f16x2 max/sum tree이며, scalar는 18개 scalar PTX tree와 H0-lane-replicated SASS이다. normalization은 native FP16 reciprocal이 아니라 FP16-rounded FP32 reciprocal과 scalar/half2 multiply 비교다.",
                },
                {
                    "id": "quality_intro",
                    "type": "markdown",
                    "sourceId": "analysis",
                    "body": "## 수치·trace·placement 품질\n\n27/27 roles가 manifest/hash/schema/denominator, qualified trace, SMID, numerical gate를 통과했다. 온도는 52–58 °C로 기록했지만 hard fail이나 causal adjustment로 사용하지 않았다.",
                },
                {"id": "quality_table_block", "type": "table", "tableId": "quality_table"},
                {"id": "sass_audit_table_block", "type": "table", "tableId": "sass_audit_table"},
                {
                    "id": "limitations",
                    "type": "markdown",
                    "body": "## 한계와 다음 단계\n\n이 결과는 S=512·CTA=16·RTX 3090 한 coordinate에 한정되고, n=3 interval은 넓다. baseline preheat 뒤 same-order calibration/warm-up이 있어 position은 회전했지만 directed carryover는 완전 counterbalance하지 않았다. stage effect를 합산해 all-FP16 policy energy를 예측하거나 cross-GPU / pure unit energy로 일반화하지 않는다. 넓은 sweep 대신 exp packed vs baseline 및 scalar reduction vs baseline만, premeasurement conditioning을 common/fixed로 둔 AB/BA 추가 fresh-session confirmation을 권장한다.",
                },
                {
                    "id": "further_questions",
                    "type": "markdown",
                    "body": "## 후속 질문\n\nfixed-clock 또는 external meter가 interval을 줄이는가? A100/H100에서 같은 PTX/SASS lowering이 유지되는가? workload-specific numerical tolerance가 더 엄격할 때 FP16 reduction/normalization boundary는 어디인가?",
                },
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": analysis["generated_at"],
            "status": "ready",
            "datasets": {
                "stage_summary": stage_rows,
                "paired_contrasts": paired_rows,
                "validation_summary": validation,
                "analysis_quality": analysis_quality,
                "sass_quality": sass_quality,
            },
        },
        "sources": sources,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--sass-audit", type=Path, default=RUN_DIR / "sass_audit.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    sass_path = args.sass_audit.resolve()
    out_dir = args.out_dir.resolve()
    cells, summary, analysis, sass = load_evidence(run_dir, sass_path)
    stage_rows, paired_rows, _stage_results = summarize(cells, summary)
    validation = validation_rows(cells)
    audit = audit_rows(cells, sass)
    markdown = report_markdown(stage_rows, paired_rows, validation, audit, sass)
    artifact = artifact_payload(
        run_dir, sass_path, stage_rows, paired_rows, validation, audit, analysis
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = out_dir / f"{RESULT_PREFIX}_analysis_ko.md"
    artifact_path = out_dir / f"{RESULT_PREFIX}_artifact.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("report_source_status=pass")
    print(f"markdown={markdown_path}")
    print(f"artifact={artifact_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
