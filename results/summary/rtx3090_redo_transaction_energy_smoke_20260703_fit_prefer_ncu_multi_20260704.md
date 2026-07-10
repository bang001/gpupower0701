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
| RMSE (J) | 12.8377 |
| relative RMSE (%) | 7.22286 |
| R2 | 0.787445 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -299.537 | J | 1 | False | -447.51 |  |
| elapsed_s | elapsed_s | 439.645 | W | 1.09191 | True | 577.913 |  |
| shared_bytes_static_fallback | expected_shared_bytes | 0 | pJ/byte | 3.83551e+12 | True | -736.905 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| l1_bytes_ncu | ncu_l1_bytes | 0.537079 | pJ/byte | 1.34006e+13 | True | 1.5266 |  |
| l2_bytes_ncu | ncu_l2_bytes | 0.0203582 | pJ/byte | 7.79601e+09 | True | -0.829323 | unconstrained_negative |
| dram_bytes_ncu | ncu_dram_bytes | 0 | pJ/byte | 5.57272e+09 | True | -2184.75 | unconstrained_negative;zero_bound_or_not_identified |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 1.34349e+06 | True | 1.01033e+09 | zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | -8.55507 | J | 1 | False | -3.45624 |  |
| baseline_mode_dram_load_only | mode | 34.5019 | J | 1 | False | 2601.29 |  |
| baseline_mode_global_l1_load_only | mode | 8.47555 | J | 1 | False | -1352.48 |  |
| baseline_mode_l2_load_only | mode | -11.116 | J | 1 | False | -1376.79 |  |
| baseline_mode_shared_load_only | mode | 9.68357 | J | 1 | False | 1490.67 |  |

## Warnings

- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:8

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
