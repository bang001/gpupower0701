# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 224 |
| features used | 16 |
| byte source | static |
| baseline terms | mode |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | False |
| ridge lambda | 1e-09 |
| RMSE (J) | 36.6302 |
| relative RMSE (%) | 7.20787 |
| R2 | 0.936277 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | 9.69904 | J | 1 | False | -290.276 |  |
| elapsed_s | elapsed_s | 166.878 | W | 3.29588 | True | 261.105 |  |
| FLOP | FLOP | 0 | pJ/FLOP | 1.73683e+14 | True | -0.313576 | unconstrained_negative;zero_bound_or_not_identified |
| reg_operand_ops | expected_reg_operand_ops | 0 | pJ/reg-op | 2.91079e+10 | True | -10551.3 | unconstrained_negative;zero_bound_or_not_identified |
| shared_bytes_static | expected_shared_bytes | 1.8651 | pJ/byte | 1.28797e+13 | True | 1.22668 | static_byte |
| l2_bytes_static | expected_l2_bytes | 3.7864 | pJ/byte | 1.0058e+13 | True | 2.50911 | static_byte |
| dram_bytes_static | expected_dram_bytes | 0 | pJ/byte | 2.78065e+12 | True | -3.46674 | unconstrained_negative;zero_bound_or_not_identified;static_byte |
| store_bytes_static | expected_store_bytes | 14398.7 | pJ/byte | 1.34349e+06 | True | 13754.4 | static_byte |
| baseline_mode_dram_load_only | mode | 150.567 | J | 1 | False | 148.164 |  |
| baseline_mode_dram_mma | mode | 143.527 | J | 1 | False | 162.073 |  |
| baseline_mode_l2_load_only | mode | -6.26812 | J | 1 | False | -11.5964 |  |
| baseline_mode_l2_mma | mode | -7.5007 | J | 1 | False | 29.8883 |  |
| baseline_mode_reg_mma | mode | -209.878 | J | 1 | False | 143.875 |  |
| baseline_mode_reg_operand_only | mode | -261.337 | J | 1 | False | 41.681 |  |
| baseline_mode_shared_load_only | mode | 33.9117 | J | 1 | False | 27.2599 |  |
| baseline_mode_shared_mma | mode | -50.0618 | J | 1 | False | -8.37994 |  |
| baseline_mode_store_only | mode | -1780.56 | J | 1 | False | -1714.65 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- mode_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:7

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
