# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 16 |
| features used | 12 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0.5 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 15.5427 |
| relative RMSE (%) | 3.16327 |
| R2 | 0.999567 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -58.8821 | J | 1 | False | -41.7005 |  |
| elapsed_s | elapsed_s | 0 | W | 1.2782 | True | -1443.1 | unconstrained_negative;zero_bound_or_not_identified |
| FLOP | FLOP | 0 | pJ/FLOP | 6.44874e+13 | True | 0.265942 | zero_bound_or_not_identified;low_positive_variation |
| reg_operand_ops | expected_reg_operand_ops | 5658.21 | pJ/reg-op | 7.872e+09 | True | 165966 | low_positive_variation |
| shared_bytes_static | expected_shared_bytes | 45.7937 | pJ/byte | 5.37395e+12 | True | 395.452 | static_byte |
| l2_bytes_static | expected_l2_bytes | 52.4076 | pJ/byte | 5.37395e+12 | True | 488.769 | static_byte |
| dram_bytes_static | expected_dram_bytes | 287.092 | pJ/byte | 4.03046e+12 | True | 2072.64 | static_byte |
| store_bytes_static | expected_store_bytes | 2501.01 | pJ/byte | 1.34349e+06 | True | 42600.6 | static_byte |
| baseline_mode_l2_load_only | mode | 77.7825 | J | 1 | False | 177.45 |  |
| baseline_mode_reg_mma | mode | 74.1813 | J | 1 | False | 75.9732 |  |
| baseline_mode_reg_operand_only | mode | 72.7305 | J | 1 | False | 73.225 |  |
| baseline_mode_shared_load_only | mode | 60.2089 | J | 1 | False | 122.243 |  |
| baseline_mode_store_only | mode | 63.7791 | J | 1 | False | 72.9359 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:10
- large_elapsed_spread: elapsed max/min exceeds 2

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
