# RTX 3090 Whole-Softmax precision stage-isolation summary

All manifest, SHA-256, raw-schema, numerical-validation, preheat, trace, SMID, and denominator gates passed.

- Manifest: `results/raw/rtx3090_softmax_whole_precision_stage_isolation_20260727_stageiso_v1/manifest.json`
- Primary unit: net pJ / logical Softmax output element
- Scope: full exp + reduction + normalization design
- Temperature is recorded but not used as a hard rejection gate.

## exp

### Absolute policy result

| policy | n | mean | sample std | median | min | max |
|---|---:|---:|---:|---:|---:|---:|
| fp16_io_fp32_all | 3 | 2453.846501 | 509.671390 | 2341.186557 | 2009.930804 | 3010.422141 |
| exp_fp16_scalar | 3 | 2091.723573 | 242.546552 | 2161.819334 | 1821.848591 | 2291.502795 |
| exp_fp16x2 | 3 | 1941.856827 | 115.845221 | 1953.166003 | 1820.771775 | 2051.632705 |

### Paired delta vs `fp16_io_fp32_all`

Positive delta means that policy consumed more net pJ/output element than the common baseline in the same session.

| policy | n | mean delta | sample std | median delta | min | max |
|---|---:|---:|---:|---:|---:|---:|
| exp_fp16_scalar | 3 | -362.122928 | 309.025486 | -188.082213 | -718.919346 | -179.367224 |
| exp_fp16x2 | 3 | -511.989674 | 549.527461 | -520.414783 | -1057.256139 | 41.701901 |

## reduction

### Absolute policy result

| policy | n | mean | sample std | median | min | max |
|---|---:|---:|---:|---:|---:|---:|
| fp16_io_fp32_all | 3 | 2086.162570 | 124.553741 | 2091.757270 | 1958.905753 | 2207.824686 |
| reduction_fp16_scalar | 3 | 3345.323240 | 782.811240 | 2990.199324 | 2803.018064 | 4242.752332 |
| reduction_fp16x2 | 3 | 2084.381731 | 447.796961 | 2118.028901 | 1620.710276 | 2514.406015 |

### Paired delta vs `fp16_io_fp32_all`

Positive delta means that policy consumed more net pJ/output element than the common baseline in the same session.

| policy | n | mean delta | sample std | median delta | min | max |
|---|---:|---:|---:|---:|---:|---:|
| reduction_fp16_scalar | 3 | 1259.160670 | 900.264321 | 898.442054 | 595.193378 | 2283.846578 |
| reduction_fp16x2 | 3 | -1.780839 | 571.823643 | 26.271631 | -587.114411 | 555.500262 |

## normalization

### Absolute policy result

| policy | n | mean | sample std | median | min | max |
|---|---:|---:|---:|---:|---:|---:|
| fp16_io_fp32_all | 3 | 2158.056462 | 11.963019 | 2156.494988 | 2146.950854 | 2170.723543 |
| normalization_fp16_scalar | 3 | 2515.075418 | 422.436457 | 2336.101922 | 2211.587705 | 2997.536626 |
| normalization_fp16x2 | 3 | 2415.755387 | 405.258604 | 2411.026006 | 2012.882172 | 2823.357984 |

### Paired delta vs `fp16_io_fp32_all`

Positive delta means that policy consumed more net pJ/output element than the common baseline in the same session.

| policy | n | mean delta | sample std | median delta | min | max |
|---|---:|---:|---:|---:|---:|---:|
| normalization_fp16_scalar | 3 | 357.018956 | 422.191522 | 165.378379 | 64.636851 | 841.041637 |
| normalization_fp16x2 | 3 | 257.698925 | 412.389155 | 264.075151 | -157.841371 | 666.862995 |

## Interpretation boundary

These are complete-Softmax implementation-path measurements. They are not EX2 operand-rate ATC values, pure SFU/MUFU circuit energy, or an additive decomposition across stages. Packed reduction uses half2 lanes across two rows before its block tree.
