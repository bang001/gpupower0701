# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 24 |
| features used | 12 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 13.423 |
| relative RMSE (%) | 3.97514 |
| R2 | 0.99957 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -58.8822 | J | 1 | False | -58.7877 |  |
| elapsed_s | elapsed_s | 0 | W | 0.803036 | True | -7.93886 | unconstrained_negative;zero_bound_or_not_identified |
| FLOP | FLOP | 0 | pJ/FLOP | 3.22437e+13 | True | -0.26035 | unconstrained_negative;zero_bound_or_not_identified |
| reg_operand_ops | expected_reg_operand_ops | 6990.44 | pJ/reg-op | 3.936e+09 | True | 8878.8 |  |
| shared_bytes_static | expected_shared_bytes | 46.9066 | pJ/byte | 4.03046e+12 | True | 48.8144 | static_byte |
| l2_bytes_static | expected_l2_bytes | 52.6379 | pJ/byte | 4.03046e+12 | True | 55.0446 | static_byte |
| dram_bytes_static | expected_dram_bytes | 287.092 | pJ/byte | 4.03046e+12 | True | 296.915 | static_byte |
| store_bytes_static | expected_store_bytes | 2546 | pJ/byte | 1.34349e+06 | True | 2767.23 | static_byte |
| baseline_mode_l2_load_only | mode | 75.8141 | J | 1 | False | 76.3098 |  |
| baseline_mode_reg_mma | mode | 63.937 | J | 1 | False | 69.8914 |  |
| baseline_mode_reg_operand_only | mode | 59.6894 | J | 1 | False | 55.0852 |  |
| baseline_mode_shared_load_only | mode | 50.6936 | J | 1 | False | 51.1695 |  |
| baseline_mode_store_only | mode | 62.3883 | J | 1 | False | 62.4073 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:10
- large_elapsed_spread: elapsed max/min exceeds 2

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
