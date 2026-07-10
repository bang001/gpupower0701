# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 13 |
| features used | 11 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 12.8377 |
| relative RMSE (%) | 7.22284 |
| R2 | 0.787447 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -299.189 | J | 1 | False | -364.667 |  |
| elapsed_s | elapsed_s | 439.328 | W | 1.09191 | True | 496.786 |  |
| shared_bytes_static | expected_shared_bytes | 0 | pJ/byte | 3.83551e+12 | True | -752.117 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| l1_bytes_static | expected_l1_bytes | 17.5891 | pJ/byte | 3.37885e+12 | True | 19.5143 | static_byte;low_positive_variation |
| l2_bytes_static | expected_l2_bytes | 1.87625 | pJ/byte | 3.41692e+12 | True | 5.19182 | static_byte;low_positive_variation |
| dram_bytes_static | expected_dram_bytes | 0 | pJ/byte | 8.96496e+11 | True | -330.512 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 1.34349e+06 | True | 4.7045e+08 | zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | -8.57996 | J | 1 | False | -4.0879 |  |
| baseline_mode_dram_load_only | mode | 36.4616 | J | 1 | False | -296.302 |  |
| baseline_mode_global_l1_load_only | mode | -47.0918 | J | 1 | False | -682.715 |  |
| baseline_mode_l2_load_only | mode | -10.1659 | J | 1 | False | -651.908 |  |
| baseline_mode_shared_load_only | mode | 9.68035 | J | 1 | False | 2265.45 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:4

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
