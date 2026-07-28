# Whole-Softmax stage Operand-rate ATC analysis

- status: `pass`
- measured roles / cells / bracket effects: 162 / 27 / 54
- primary: active-control ATC ΔpJ/logical Softmax output element for one added stage pass
- idle power: diagnostic only; excluded from every primary numerator
- non-primary diagnostic: same-ITER gross board-energy contrast (idle excluded; never substituted for primary ATC)

| stage | policy | mean ATC ΔpJ/output | SD | descriptive t95 | same-ITER gross ΔE/N | T/C elapsed |
|---|---|---:|---:|---:|---:|---:|
| exp | fp32 | 34.977674 | 127.817661 | [-282.538999, 352.494346] | 28.069735 | 0.998947 |
| exp | fp16_scalar | 16.334661 | 34.846114 | [-70.227884, 102.897206] | 26.940116 | 1.001688 |
| exp | fp16x2 | 12.169395 | 32.095700 | [-67.560743, 91.899534] | 13.958462 | 1.000409 |
| reduction | fp32 | -600.908609 | 103.083016 | [-856.981015, -344.836202] | 1826.390212 | 1.390462 |
| reduction | fp16_scalar | -700.436065 | 116.747517 | [-990.452975, -410.419154] | 3530.892343 | 1.726121 |
| reduction | fp16x2 | -473.433297 | 51.194094 | [-600.606475, -346.260118] | 1423.060434 | 1.442496 |
| normalization | fp32 | 34.630118 | 98.027223 | [-208.883004, 278.143240] | 34.147283 | 0.999917 |
| normalization | fp16_scalar | 47.066995 | 15.391586 | [8.832176, 85.301814] | 45.584849 | 0.999746 |
| normalization | fp16x2 | -52.910441 | 13.889377 | [-87.413566, -18.407315] | -4.698728 | 1.011351 |
