# GPU Quiescence Audit

- Date: 2026-07-22T09:45:05+09:00
- GPU index: `0`
- Verdict: `reject`
- Reasons: `memory_util_max_pct=43>25;memory_util_p95_pct=43>10`
- Raw samples: `results/summary/rtx3090_tensor_v3_20260722_pre_run_quiescence.csv`

## Utilization Summary

| metric | value | strict limit | unit |
|---|---:|---:|---|
| GPU utilization max | 1.000 | 10 | % |
| GPU utilization p95 | 1.000 | 5 | % |
| memory-controller utilization max | 43.000 | 25 | % |
| memory-controller utilization p95 | 43.000 | 10 | % |
| frame-buffer memory used min | 1469.000 | not gated | MiB |
| frame-buffer memory used max | 1472.000 | not gated | MiB |
| frame-buffer memory used drift | 3.000 | 128 | MiB |
| board power min-median-max | 10.330 / 13.080 / 17.090 | diagnostic | W |
| visible compute processes | 0 | 0 | process count |

## Process Evidence

No compute process was reported by `nvidia-smi`.

## Interpretation

- `memory.used` is allocated frame-buffer memory, not allocated L2 cache. It is recorded for context but its absolute value is not a rejection gate.
- L2 has no meaningful pre-run hit-rate value. Hit rate is defined by a kernel's requests and must be measured with NCU during that workload.
- Sustained memory-controller utilization or another compute process can evict benchmark cache lines and contaminate board-energy measurements.
- Under WSL/WDDM, Windows graphics processes may not appear in the Linux compute-process list. The utilization time series remains a required gate.
- Passing this audit proves only that the sampled pre-run interval was quiet. It does not prove exclusive ownership for the entire later experiment.
