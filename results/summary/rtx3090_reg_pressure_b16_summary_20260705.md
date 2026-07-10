# Register Footprint Summary

Direct pJ/reg-update values are effective scalar register-pressure coefficients. They are not pure register-file access energy.

| payload (B/block) | ptxas regs/thread | compiler footprint (B/block) | blocks/SM | active_SM (SMs) | reuse | delta_E_J (J) | updates | pressure power (W) | update rate (/s) | direct coefficient (pJ/reg-update) | rows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 256 | 21 | 2688 | 16 | 82 | 1 | 615.358 | 2.33944e+12 | 208.256 | 7.88565e+11 | 263.037 | 1/1 |
| 512 | 22 | 2816 | 16 | 82 | 1 | 690.862 | 3.52056e+12 | 211.136 | 1.06939e+12 | 196.236 | 1/1 |
| 1024 | 19 | 2432 | 16 | 82 | 1 | 702.588 | 4.3225e+12 | 210.814 | 1.30366e+12 | 162.542 | 1/1 |
| 2048 | 31 | 3968 | 16 | 82 | 1 | 759.281 | 4.94522e+12 | 225.07 | 1.47046e+12 | 153.538 | 1/1 |
| 4096 | 44 | 5632 | 16 | 82 | 1 | 721.431 | 5.25083e+12 | 215.994 | 1.57553e+12 | 137.394 | 1/1 |
| 8192 | 76 | 9728 | 16 | 82 | 1 | 724.583 | 5.36731e+12 | 218.598 | 1.59995e+12 | 134.999 | 1/1 |

## Power-Rate Slope

| item | value | unit |
|---|---:|---|
| rows | 6 | rows |
| intercept | 196.099 | W |
| slope | 14.5077 | pJ/reg-update |
| RMSE | 3.78559 | W |
| relative RMSE | 1.76092 | % |

The slope is a better proxy than direct division because the intercept absorbs fixed active/control power. It still includes integer ALU, scheduler, dependency, and issue effects.

## Interpretation Limits

- The same-ITER `empty` row can be much shorter than `reg_pressure`; direct delta therefore does not remove fixed active power.
- `reg_pressure` updates contain scalar integer operations and dependency chains, not isolated register-file reads/writes.
