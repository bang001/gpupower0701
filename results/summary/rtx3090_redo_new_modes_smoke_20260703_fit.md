# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 8 |
| features used | 5 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 7.20617 |
| relative RMSE (%) | 39.9342 |
| R2 | 0.446853 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -77.5657 | J | 1 | False | -41.4701 |  |
| elapsed_s | elapsed_s | 395.205 | W | 0.220306 | True | 229.559 |  |
| l1_bytes_static | expected_l1_bytes | 0 | pJ/byte | 6.89948e+11 | True | -189.533 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| store_bytes_static | expected_store_bytes | 9.59866e+06 | pJ/byte | 5248 | True | 1.07348e+08 | static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | 13.6037 | J | 1 | False | 13.4668 |  |
| baseline_mode_global_l1_load_only | mode | 0.000225183 | J | 1 | False | 0.00217469 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:3
- high_residual: relative RMSE exceeds 20%

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
