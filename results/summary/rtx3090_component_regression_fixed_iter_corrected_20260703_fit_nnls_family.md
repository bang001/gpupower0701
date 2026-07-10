# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 24 |
| features used | 11 |
| byte source | static |
| baseline terms | family |
| non-negative constrained fit | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 13.4789 |
| relative RMSE (%) | 3.99169 |
| R2 | 0.999567 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | 2.93105 | J | 1 | False | 3.73959 |  |
| elapsed_s | elapsed_s | 0 | W | 0.803036 | True | -8.34039 | unconstrained_negative;zero_bound_or_not_identified |
| FLOP | FLOP | 0 | pJ/FLOP | 3.22437e+13 | True | -0.0171603 | unconstrained_negative;zero_bound_or_not_identified |
| reg_operand_ops | expected_reg_operand_ops | 6990.44 | pJ/reg-op | 3.936e+09 | True | 7924.27 |  |
| shared_bytes_static | expected_shared_bytes | 46.9066 | pJ/byte | 4.03046e+12 | True | 48.9109 | static_byte |
| l2_bytes_static | expected_l2_bytes | 52.6379 | pJ/byte | 4.03046e+12 | True | 55.1663 | static_byte |
| dram_bytes_static | expected_dram_bytes | 287.092 | pJ/byte | 4.03046e+12 | True | 297.412 | static_byte |
| store_bytes_static | expected_store_bytes | 2546 | pJ/byte | 1.34349e+06 | True | 2778.42 | static_byte |
| baseline_family_shared | mode_family | -11.1196 | J | 1 | False | -11.3289 |  |
| baseline_family_l2 | mode_family | 14.0009 | J | 1 | False | 13.8124 |  |
| baseline_family_dram | mode_family | -61.8132 | J | 1 | False | -62.5225 |  |
| baseline_family_store | mode_family | 0.575103 | J | 1 | False | -0.114189 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- family_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:10
- large_elapsed_spread: elapsed max/min exceeds 2

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
