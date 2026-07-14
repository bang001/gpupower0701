# Power-State Stability Audit

This report flags raw energy rows whose average power or endpoint power metadata is inconsistent with peer rows of the same mode and configuration. It is a measurement-quality audit, not an NCU path acceptance report and not a component coefficient report.

- audit CSV: `results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv`

## Status Counts

| status | rows |
|---|---:|
| `caution` | 3 |
| `ok` | 284 |
| `reject` | 73 |

## Reject Reasons

| reason | rows |
|---|---:|
| `avg_power_low_outlier` | 1 |
| `invalid_average_power` | 72 |

## Notes

| note | rows |
|---|---:|
| `temperature_outlier` | 6 |

## Rejected Rows

| mode | W_SM (KiB) | B/SM | LR | avg power (W) | group median (W) | endpoint after ratio | temp (C) | reasons | notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `reg_operand_only` | 1 | 4 | 1 | -72.0228279939 | -88.9180516261 | 0.826181065312 | 39 | invalid_average_power | temperature_outlier |
| `reg_operand_only` | 1 | 4 | 1 | -77.8830458145 | -83.2761918672 | 0.86041568257 | 45 | invalid_average_power | temperature_outlier |
| `reg_operand_only` | 1 | 4 | 1 | -77.2550714482 | -79.156815338 | 0.87899888007 | 44 | invalid_average_power | temperature_outlier |
| `reg_operand_only` | 1 | 4 | 1 | -80.4833682252 | -82.2519616652 | 0.956908344733 | 48 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -80.3340754992 | -80.3340754992 | 0.884951943767 | 47 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -82.8177968258 | -82.8177968258 | 0.965733449985 | 50 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -80.9149198636 | -78.8709928207 | 0.900305139697 | 49 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -87.5949308359 | -83.2673288805 | 0.975229312797 | 51 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -77.5775032455 | -80.8580412829 | 0.954396757971 | 50 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -87.2482595416 | -83.7914734515 | 0.95649875024 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -76.8024905525 | -81.6295546995 | 0.961570389179 | 50 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -85.8147909983 | -83.1679030619 | 0.976587510153 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -76.6328085887 | -79.6708877368 | 0.973211207958 | 51 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -87.4418433126 | -87.4418433126 | 0.971180604688 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -75.5152064872 | -77.7575466033 | 0.972296908008 | 51 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -85.8608564913 | -83.2761918672 | 0.993434104865 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -82.1953266066 | -79.156815338 | 0.97317037542 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -80.2535414988 | -82.2519616652 | 1 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -83.9149497249 | -80.3340754992 | 1.02467364797 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -81.2874202975 | -82.8177968258 | 0.954408476718 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -49.0996449593 | -78.8709928207 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -83.2673288805 | -83.2673288805 | 0.988227792221 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -86.618944206 | -80.8580412829 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -83.7914734515 | -83.7914734515 | 0.964477985003 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -85.3988821127 | -81.6295546995 | 1.03325357683 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -83.1679030619 | -83.1679030619 | 0.955898514024 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -86.2899064606 | -79.6708877368 | 1.04392573989 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -84.5482929789 | -87.4418433126 | 0.952973916325 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -86.8042827587 | -77.7575466033 | 1.03442481275 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -89.7855838978 | -88.9180516261 | 1 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -79.156815338 | -79.156815338 | 1 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -88.3290892042 | -82.2519616652 | 1.02003126832 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -77.6607419942 | -80.3340754992 | 1 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -89.1246374521 | -82.8177968258 | 1.02512880334 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -77.8329821187 | -78.8709928207 | 0.987126919043 | 52 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -82.1996069974 | -83.2673288805 | 1 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -84.9416302713 | -83.7914734515 | 1.00240338396 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -81.6295546995 | -81.6295546995 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -82.2264482099 | -83.1679030619 | 1 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -78.9717274604 | -79.6708877368 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -90.2414202043 | -87.4418433126 | 1 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -77.8333791875 | -77.7575466033 | 0.977290186288 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -88.9180516261 | -88.9180516261 | 0.983483907397 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -83.6601034202 | -83.2761918672 | 1.00434577232 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -82.2519616652 | -82.2519616652 | 0.996873167872 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -83.8911639123 | -80.3340754992 | 1.00851145221 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -82.3294425425 | -82.8177968258 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -86.4542016241 | -78.8709928207 | 1.0168303614 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -84.4344076802 | -83.2673288805 | 1.01628488743 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -88.826321078 | -80.8580412829 | 1.0638152434 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -76.6683349143 | -83.7914734515 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -86.9940191699 | -81.6295546995 | 1.01665120367 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -76.5971704604 | -83.1679030619 | 1.01419083568 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -88.5887575441 | -79.6708877368 | 1.04919485892 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -84.5317706461 | -87.4418433126 | 1.00075468138 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -89.9531464917 | -88.9180516261 | 1.00159984943 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -78.7663236505 | -83.2761918672 | 1 | 53 | invalid_average_power | - |
| `reg_mma` | 1 | 4 | 1 | 151.255489852 | 161.755417422 | 0.99813129827 | 73 | avg_power_low_outlier | - |
| `reg_operand_only` | 1 | 4 | 1 | -0.623680123037 | -79.156815338 | 1.0258070799 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -77.5066634338 | -80.3340754992 | 0.99603117678 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -89.1844466606 | -82.8177968258 | 1.02512880334 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -78.8709928207 | -78.8709928207 | 1.00300371889 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -82.3560888972 | -83.2673288805 | 1.04993378133 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -80.8580412829 | -80.8580412829 | 0.96118353596 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 8 | 1 | -82.990753635 | -83.7914734515 | 1.02230340319 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -91.7665651541 | -83.1679030619 | 1.06856514884 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -79.6708877368 | -79.6708877368 | 0.992071699414 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -89.9802272361 | -87.4418433126 | 1.04631856988 | 55 | invalid_average_power | - |
| `reg_operand_only` | 1 | 16 | 1 | -77.7575466033 | -77.7575466033 | 1 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -87.6783739262 | -88.9180516261 | 1.01063429324 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -83.2761918672 | -83.2761918672 | 1.02423240435 | 54 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -80.4143330574 | -79.156815338 | 1.02118128256 | 53 | invalid_average_power | - |
| `reg_operand_only` | 1 | 4 | 1 | -84.479100806 | -82.2519616652 | 1.05809067813 | 54 | invalid_average_power | - |

## Interpretation

- `reject` rows should not be used as evidence for a stable coefficient until the run is repeated under stable clocks/power state.
- Endpoint power fields are metadata. Final energy numerator still comes from `nvml_total_energy` when the power API audit passes.
- If matched-control rows are negative but this audit has no reject row, the likely issue is weak treatment-control signal rather than an obvious power-state anomaly.
