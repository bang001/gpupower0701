# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| register_control_candidate | 5 | 0 | 0 |
| tensor_increment_candidate | 0 | 0 | 5 |

## Tensor Pair Diagnostics

The HMMA/logical-MMA ratio is allowed to differ by architecture, but must stay stable across RF at each blocks/SM coordinate. Register counts expose the treatment/control footprint mismatch rather than claiming pure Tensor-circuit isolation.

| mode | blocks/SM | RF | HMMA | logical MMA | HMMA/logical | group median | relative spread | control pair | Tensor pipe active (%) | registers/thread | acceptance |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| reg_mma | 4 | 1 | 6.56e+07 | 3.28e+07 | 2 | 4 | 0.5 | accepted | 49.9754 | 34 | rejected |
| reg_mma | 4 | 16 | 2.0992e+09 | 5.248e+08 | 4 | 4 | 0.5 | accepted | 47.1017 | 35 | rejected |
| reg_mma | 4 | 2 | 2.624e+08 | 6.56e+07 | 4 | 4 | 0.5 | accepted | 44.5962 | 35 | rejected |
| reg_mma | 4 | 4 | 5.248e+08 | 1.312e+08 | 4 | 4 | 0.5 | accepted | 45.9589 | 35 | rejected |
| reg_mma | 4 | 8 | 1.0496e+09 | 2.624e+08 | 4 | 4 | 0.5 | accepted | 46.7145 | 35 | rejected |
| reg_operand_only | 4 | 1 | 0 |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 16 | 0 |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 2 | 0 |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 4 | 0 |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 8 | 0 |  |  |  |  |  | 0 | 16 | accepted |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | L2 logical hit (%) | L2 fabric hit (%) | acceptance model | native/model delta (pp) | source/fabric/model coherent | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM write bytes | DRAM-read/L2-read | source/expected | external-read/expected | write/read | memory technology | DRAM read GB/s | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---||---||---||---||---||---||---||---||---||---||---||---||---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma | tensor_increment_candidate | rejected | hmma_per_logical_mma_unstable_across_rf | contiguous |  |  | 8.55196 |  |  |  |  | // | 0 sectors | 0 sectors | 266424 sectors | 0 | 0 | 0 | 0 | 0 | 8.52557e+06 | 0 |  |  |  |  | GDDR6X | 0.00229767 | 8.52557e+06 |  | 1.17965e+06 | 0.090571 |
| reg_mma | tensor_increment_candidate | rejected | hmma_per_logical_mma_unstable_across_rf | contiguous |  |  | 20.2471 |  |  |  |  | // | 0 sectors | 0 sectors | 3.64668e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.16694e+08 | 0 |  |  |  |  | GDDR6X | 0.00104635 | 1.16694e+08 |  | 1.17965e+06 | 0.002362 |
| reg_mma | tensor_increment_candidate | rejected | hmma_per_logical_mma_unstable_across_rf | contiguous |  |  | 15.8127 |  |  |  |  | // | 0 sectors | 0 sectors | 621848 sectors | 0 | 0 | 0 | 0 | 0 | 1.98991e+07 | 0 |  |  |  |  | GDDR6X | 0.00135116 | 1.98991e+07 |  | 1.17965e+06 | 0.027729 |
| reg_mma | tensor_increment_candidate | rejected | hmma_per_logical_mma_unstable_across_rf | contiguous |  |  | 26.5118 |  |  |  |  | // | 0 sectors | 0 sectors | 682688 sectors | 0 | 0 | 0 | 0 | 0 | 2.1846e+07 | 0 |  |  |  |  | GDDR6X | 0.00076438 | 2.1846e+07 |  | 1.17965e+06 | 0.005685 |
| reg_mma | tensor_increment_candidate | rejected | hmma_per_logical_mma_unstable_across_rf | contiguous |  | 0 | 20.208 |  |  |  |  | // | 0 sectors | 0 sectors | 1.77232e+06 sectors | 0 | 0 | 0 | 0 | 1.25235e+06 | 5.67141e+07 | 0 |  |  |  |  | GDDR6X | 0.00100857 | 5.67141e+07 |  | 1.17965e+06 | 0.004496 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 87.0146 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 8.92857e-07 | 3200 |  | 1.17965e+06 | 911.809 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 85.9413 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 8.84956e-07 | 3200 |  | 1.17965e+06 | 556.364 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 81.6235 |  |  |  |  | // | 0 sectors | 0 sectors | 164 sectors | 0 | 0 | 0 | 0 | 0 | 5248 | 0 |  |  |  |  | GDDR6X | 1.50459e-06 | 5248 |  | 1.17965e+06 | 569.418 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 86.6747 |  |  |  |  | // | 0 sectors | 0 sectors | 132 sectors | 0 | 0 | 0 | 0 | 0 | 4224 | 0 |  |  |  |  | GDDR6X | 1.06452e-06 | 4224 |  | 1.17965e+06 | 589.784 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 91.5648 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 9.25926e-07 | 3200 |  | 1.17965e+06 | 562.431 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator. GA100 uses a source-plus-LTC-fabric final-service hit rate; its coefficient therefore includes the workload-dependent partition-fabric cost and is not a pure local L2-SRAM coefficient. External-memory acceptance requires NCU read bytes, conserved global-read requests, at least 90% external-read service, and at most 1% write contamination. Its energy coefficient remains an effective GPU-device path value, not HBM/GDDR cell or package energy.
