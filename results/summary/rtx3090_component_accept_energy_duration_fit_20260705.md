# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 30 |
| features used | 10 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 1 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 21.3627 |
| relative RMSE (%) | 3.18645 |
| R2 | 0.839135 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -148.544 | J | 1 | False | -147.835 |  |
| elapsed_s | elapsed_s | 237.497 | W | 3.32475 | True | 237.497 |  |
| shared_bytes_static | expected_shared_bytes | 1.89992 | pJ/byte | 1.99324e+13 | True | 1.89992 | static_byte |
| l1_bytes_static | expected_l1_bytes | 17.3359 | pJ/byte | 1.1331e+13 | True | 17.3359 | static_byte |
| l2_bytes_static | expected_l2_bytes | 92.2144 | pJ/byte | 7.66751e+12 | True | 92.2144 | static_byte |
| dram_bytes_static | expected_dram_bytes | 1293.79 | pJ/byte | 2.88793e+12 | True | 1293.79 | static_byte |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 5248 | True | -1.35081e+08 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_dram_cg_load_only | mode | -3642.83 | J | 1 | False | -3643.53 |  |
| baseline_mode_global_l1_load_only | mode | -197.586 | J | 1 | False | -16.8146 |  |
| baseline_mode_l2_cg_load_only | mode | -643.106 | J | 1 | False | -643.815 |  |
| baseline_mode_shared_scalar_load_only | mode | 1.2181 | J | 1 | False | 1.2181 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:6

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
