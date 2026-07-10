# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 224 |
| features used | 12 |
| byte source | static |
| baseline terms | family |
| non-negative constrained fit | True |
| min elapsed filter (s) | 0 |
| exclude negative net energy | False |
| ridge lambda | 1e-09 |
| RMSE (J) | 41.603 |
| relative RMSE (%) | 8.18638 |
| R2 | 0.917802 |

## Coefficients

| feature | source column | estimate | unit | scale | constrained | unconstrained estimate | warning |
|---|---|---:|---|---:|---|---:|---|
| intercept |  | 27.9464 | J | 1 | False | -430.388 |  |
| elapsed_s | elapsed_s | 161.146 | W | 3.29588 | True | 305.117 |  |
| FLOP | FLOP | 0.0552929 | pJ/FLOP | 1.73683e+14 | True | -0.0296221 | unconstrained_negative |
| reg_operand_ops | expected_reg_operand_ops | 0 | pJ/reg-op | 2.91079e+10 | True | -18388 | unconstrained_negative;zero_bound_or_not_identified |
| shared_bytes_static | expected_shared_bytes | 0.204091 | pJ/byte | 1.28797e+13 | True | 0.33484 | static_byte |
| l2_bytes_static | expected_l2_bytes | 3.72737 | pJ/byte | 1.0058e+13 | True | 3.87712 | static_byte |
| dram_bytes_static | expected_dram_bytes | 0 | pJ/byte | 2.78065e+12 | True | -3.41787 | unconstrained_negative;zero_bound_or_not_identified;static_byte |
| store_bytes_static | expected_store_bytes | 14437.9 | pJ/byte | 1.34349e+06 | True | 13453.5 | static_byte |
| baseline_family_register | mode_family | -241.388 | J | 1 | False | 280.55 |  |
| baseline_family_shared | mode_family | 16.0082 | J | 1 | False | -1.49972 |  |
| baseline_family_l2 | mode_family | -8.19627 | J | 1 | False | -30.9021 |  |
| baseline_family_dram | mode_family | 146.565 | J | 1 | False | 142.186 |  |
| baseline_family_store | mode_family | -1784.57 | J | 1 | False | -1683.86 |  |

## Warnings

- static_expected_bytes: memory coefficients are not actual hardware traffic
- family_baseline_terms: physical slopes are identified from within-baseline variation
- non_negative_fit: elapsed and physical coefficients constrained to be >= 0
- active_set_iterations:8

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.

A zero coefficient in the constrained fit means the current matrix does not support a positive independent slope for that term after elapsed and baseline terms are modeled. It is not evidence that the physical component consumes zero energy.
