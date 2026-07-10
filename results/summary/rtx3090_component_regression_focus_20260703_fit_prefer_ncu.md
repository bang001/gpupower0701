# Component Energy Regression Fit

## Model

`net_E_J = intercept + sum(beta_i * feature_i) + residual`

| item | value |
|---|---:|
| rows used | 224 |
| features used | 7 |
| byte source | prefer-ncu |
| ridge lambda | 1e-09 |
| RMSE (J) | 49.0894 |
| relative RMSE (%) | 9.65951 |
| R2 | 0.885557 |

## Coefficients

| feature | source column | estimate | unit | scale | warning |
|---|---|---:|---|---:|---|
| intercept |  | -309.954 | J | 1 |  |
| elapsed_s | elapsed_s | 273.078 | W | 3.29588 |  |
| FLOP | FLOP | 0.0104633 | pJ/FLOP | 1.73683e+14 |  |
| reg_operand_ops | expected_reg_operand_ops | -9283.41 | pJ/reg-op | 2.91079e+10 | negative_coefficient |
| shared_bytes_static_fallback | expected_shared_bytes | -0.475466 | pJ/byte | 1.28797e+13 | negative_coefficient;static_byte |
| l2_bytes_static_fallback | expected_l2_bytes | 0.764098 | pJ/byte | 1.0058e+13 | static_byte |
| dram_bytes_static_fallback | expected_dram_bytes | 20.6839 | pJ/byte | 2.78065e+12 | static_byte |
| store_bytes_static | expected_store_bytes | -980.541 | pJ/byte | 1.34349e+06 | negative_coefficient;static_byte |

## Warnings

- missing_ncu_actual_bytes

## Interpretation

These coefficients are elapsed-aware microbenchmark coefficients, not physical pure component energies. Static-byte coefficients must not be reported as SRAM/L2/DRAM physical energy without NCU traffic validation.
