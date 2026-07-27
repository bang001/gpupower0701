# Targeted confirmation report QA

```json
{
  "ok": true,
  "html": "/tmp/gpupower-main-softmax-20260727/docs/results/rtx3090_softmax_whole_precision_targeted_confirmation_20260727_abba_confirm_v1_report.html",
  "stages": {
    "validation": "passed",
    "package": "passed",
    "verification": "structural_only"
  },
  "browserWarning": {
    "code": "browser_unavailable",
    "message": "No installed Chromium headless-shell executable was found. Set CHROMIUM_EXECUTABLE_PATH (or the legacy PLAYWRIGHT_EXECUTABLE_PATH) or preinstall Chromium headless-shell under PLAYWRIGHT_BROWSERS_PATH; portable tooling never downloads browsers."
  },
  "counts": {
    "blocks": 15,
    "charts": 2,
    "html": 0,
    "metrics": 0,
    "tables": 3
  },
  "sourceDialog": "not_verified",
  "sourceInteraction": "not_verified",
  "viewports": [],
  "timings": {
    "validateAndPackageMs": 79,
    "staticChartExtractionMs": 2.5,
    "structuralVerificationMs": 4.1,
    "totalMs": 83.9
  }
}
```

Chromium이 설치되어 있지 않아 portable HTML의 payload/semantic fallback 구조 검증만 수행됐다. 차트 SVG와 browser-layout 검증은 수행되지 않았다.
