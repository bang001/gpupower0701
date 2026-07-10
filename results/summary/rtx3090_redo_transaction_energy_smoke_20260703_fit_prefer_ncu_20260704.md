# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 13 |
| features used | 11 |
| byte source | prefer-ncu |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 12.8859 |
| relative RMSE (%) | 7.24994 |
| R2 | 0.785849 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -283.035 | J | 1 | False | -436.629 |  |
| elapsed_s | elapsed_s | 424.597 | W | 1.09191 | True | 565.211 |  |
| shared_bytes_static_fallback | expected_shared_bytes | 0 | pJ/byte | 3.83551e+12 | True | -549.833 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| l1_bytes_ncu | ncu_l1_bytes | 0.278028 | pJ/byte | 1.24045e+13 | True | 1.43106 |  |
| l2_bytes_ncu | ncu_l2_bytes | 0 | pJ/byte | 9.42115e+09 | True | -9.1434 | unconstrained_negative;zero_bound_or_not_identified |
| dram_bytes_ncu | ncu_dram_bytes | 0 | pJ/byte | 6.40754e+09 | True | -1884.78 | unconstrained_negative;zero_bound_or_not_identified |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 1.34349e+06 | True | 8.28286e+08 | zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | -9.73159 | J | 1 | False | -0.55015 |  |
| baseline_mode_dram_load_only | mode | 35.3341 | J | 1 | False | 2324.99 |  |
| baseline_mode_global_l1_load_only | mode | 10.2205 | J | 1 | False | -1104.86 |  |
| baseline_mode_l2_load_only | mode | -5.26446 | J | 1 | False | -1116.11 |  |
| baseline_mode_shared_load_only | mode | 9.52776 | J | 1 | False | 1013.13 |  |

## Warnings

- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:5

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
