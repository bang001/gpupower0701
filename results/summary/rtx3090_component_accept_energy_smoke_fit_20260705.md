# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 34 |
| features used | 11 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 6.6441 |
| relative RMSE (%) | 9.58258 |
| R2 | 0.996703 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | 6.92013 | J | 1 | False | 6.97157 |  |
| elapsed_s | elapsed_s | 11.3123 | W | 0.174309 | True | 11.3123 |  |
| shared_bytes_static | expected_shared_bytes | 27.2431 | pJ/byte | 1.07479e+12 | True | 27.2431 | static_byte |
| l1_bytes_static | expected_l1_bytes | 50.9515 | pJ/byte | 8.06093e+11 | True | 50.9515 | static_byte |
| l2_bytes_static | expected_l2_bytes | 91.6473 | pJ/byte | 8.06093e+11 | True | 91.6473 | static_byte |
| dram_bytes_static | expected_dram_bytes | 285.736 | pJ/byte | 5.37395e+11 | True | 285.736 | static_byte |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 5248 | True | -9.80278e+06 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | 0.458928 | J | 1 | False | 0.458928 |  |
| baseline_mode_dram_cg_load_only | mode | -37.2644 | J | 1 | False | -37.3159 |  |
| baseline_mode_global_l1_load_only | mode | -13.3223 | J | 1 | False | -0.20386 |  |
| baseline_mode_l2_cg_load_only | mode | -14.5668 | J | 1 | False | -14.6183 |  |
| baseline_mode_shared_scalar_load_only | mode | -17.9262 | J | 1 | False | -17.9262 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:6
- large_elapsed_spread: elapsed max/min exceeds 2

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
