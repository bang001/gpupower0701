# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 38 |
| features used | 15 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0.8 |
| exclude negative net energy | True |
| ridge lambda | 1e-09 |
| RMSE (J) | 7.24999 |
| relative RMSE (%) | 4.20438 |
| R2 | 0.970619 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | -187.51 | J | 1 | False | -198.851 |  |
| elapsed_s | elapsed_s | 352.496 | W | 1.09233 | True | 363.112 |  |
| FLOP | FLOP | 2.35143 | pJ/FLOP | 7.36021e+13 | True | 10.8747 |  |
| reg_operand_ops | expected_reg_operand_ops | 0 | pJ/reg-op | 9.79236e+09 | True | -70355.7 | unconstrained_negative;zero_bound_or_not_identified |
| shared_bytes_static | expected_shared_bytes | 20.8475 | pJ/byte | 4.36288e+12 | True | 20.681 | static_byte |
| l1_bytes_static | expected_l1_bytes | 20.6357 | pJ/byte | 3.7398e+12 | True | 20.5616 | static_byte |
| l2_bytes_static | expected_l2_bytes | 0 | pJ/byte | 2.57702e+12 | True | -3.59855 | unconstrained_negative;zero_bound_or_not_identified;static_byte |
| dram_bytes_static | expected_dram_bytes | 0 | pJ/byte | 9.63312e+11 | True | -423.771 | unconstrained_negative;zero_bound_or_not_identified;static_byte;low_positive_variation |
| store_bytes_static | expected_store_bytes | 0 | pJ/byte | 1.34349e+06 | True | 3.93749e+07 | zero_bound_or_not_identified;static_byte;low_positive_variation |
| baseline_mode_clocked_empty | mode | -8.98403 | J | 1 | False | -9.32702 |  |
| baseline_mode_dram_cg_load_only | mode | 32.1817 | J | 1 | False | 440.055 |  |
| baseline_mode_global_l1_load_only | mode | -72.4356 | J | 1 | False | -125.504 |  |
| baseline_mode_l2_cg_load_only | mode | 5.66348 | J | 1 | False | 14.3781 |  |
| baseline_mode_reg_mma | mode | -236.717 | J | 1 | False | -284.702 |  |
| baseline_mode_reg_operand_only | mode | -88.8589 | J | 1 | False | 602.349 |  |
| baseline_mode_shared_load_only | mode | -84.7529 | J | 1 | False | -137.251 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:5

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
