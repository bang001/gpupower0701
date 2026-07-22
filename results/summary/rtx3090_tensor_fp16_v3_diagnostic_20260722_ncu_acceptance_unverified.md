# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| not_selected | 0 | 0 | 3 |
| register_control_candidate | 9 | 0 | 0 |
| tensor_increment_candidate | 9 | 0 | 0 |

## Tensor Pair Diagnostics

The HMMA/logical-MMA ratio is allowed to differ by architecture, but must stay stable across RF at each blocks/SM coordinate. Register counts expose the treatment/control footprint mismatch rather than claiming pure Tensor-circuit isolation.

| mode | blocks/SM | RF | HMMA | logical MMA | HMMA/logical | FP16-to-FP32 ops | expected FLOP | ops/expected | group median | relative spread | control SASS inst | SASS/reg-op | control pair | Tensor pipe active (%) | registers/thread | acceptance |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| reg_mma | 4 | 1 | 6.56e+07 | 3.28e+07 | 2 | 2.68698e+11 | 2.68698e+11 | 1 | 2 | 0 |  |  | accepted | 26.8752 | 34 | accepted |
| reg_mma | 4 | 16 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 2 | 0 |  |  | accepted | 23.0972 | 28 | accepted |
| reg_mma | 4 | 4 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 2 | 0 |  |  | accepted | 22.5774 | 28 | accepted |
| reg_operand_only | 4 | 1 | 0 |  |  | 0 |  |  |  |  | 1.74282e+08 | 5.31348 |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 16 | 0 |  |  | 0 |  |  |  |  | 4.92002e+09 | 9.37504 |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 4 | 0 |  |  | 0 |  |  |  |  | 1.37762e+09 | 10.5002 |  | 0 | 16 | accepted |
| reg_mma | 8 | 1 | 1.312e+08 | 6.56e+07 | 2 | 5.37395e+11 | 5.37395e+11 | 1 | 2 | 0 |  |  | accepted | 46.3254 | 34 | accepted |
| reg_mma | 8 | 16 | 2.0992e+09 | 1.0496e+09 | 2 | 8.59832e+12 | 8.59832e+12 | 1 | 2 | 0 |  |  | accepted | 42.6849 | 28 | accepted |
| reg_mma | 8 | 4 | 5.248e+08 | 2.624e+08 | 2 | 2.14958e+12 | 2.14958e+12 | 1 | 2 | 0 |  |  | accepted | 41.9887 | 28 | accepted |
| reg_operand_only | 8 | 1 | 0 |  |  | 0 |  |  |  |  | 3.48564e+08 | 5.31348 |  | 0 | 16 | accepted |
| reg_operand_only | 8 | 16 | 0 |  |  | 0 |  |  |  |  | 9.84005e+09 | 9.37505 |  | 0 | 16 | accepted |
| reg_operand_only | 8 | 4 | 0 |  |  | 0 |  |  |  |  | 2.75525e+09 | 10.5002 |  | 0 | 16 | accepted |
| reg_mma | 16 | 1 | 2.624e+08 | 1.312e+08 | 2 | 1.07479e+12 | 1.07479e+12 | 1 | 2 | 0 |  |  | accepted | 44.6389 | 34 | accepted |
| reg_mma | 16 | 16 | 4.1984e+09 | 2.0992e+09 | 2 | 1.71966e+13 | 1.71966e+13 | 1 | 2 | 0 |  |  | accepted | 42.0135 | 28 | accepted |
| reg_mma | 16 | 4 | 1.0496e+09 | 5.248e+08 | 2 | 4.29916e+12 | 4.29916e+12 | 1 | 2 | 0 |  |  | accepted | 42.0996 | 28 | accepted |
| reg_operand_only | 16 | 1 | 0 |  |  | 0 |  |  |  |  | 6.97127e+08 | 5.31347 |  | 0 | 16 | accepted |
| reg_operand_only | 16 | 16 | 0 |  |  | 0 |  |  |  |  | 1.96801e+10 | 9.37505 |  | 0 | 16 | accepted |
| reg_operand_only | 16 | 4 | 0 |  |  | 0 |  |  |  |  | 5.51049e+09 | 10.5002 |  | 0 | 16 | accepted |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | L2 logical hit (%) | L2 fabric hit (%) | acceptance model | native/model delta (pp) | source/fabric/model coherent | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM write bytes | DRAM-read/L2-read | source/expected | external-read/expected | write/read | memory technology | DRAM read GB/s | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---||---||---||---||---||---||---||---||---||---||---||---||---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | contiguous |  |  | 20.7071 |  |  |  |  | // | 0 sectors | 0 sectors | 1.68938e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.406e+07 | 0 |  |  |  |  | GDDR6X | 1.01365 | 5.406e+07 |  | 1.17965e+06 | 0.00215 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 21.2246 |  |  |  |  | 0// | 0 sectors | 156073 sectors | 173136 sectors | 0 | 0 | 0 | 4.99434e+06 | 0 | 487296 | 5.05306e+06 | 0.0975696 |  |  |  | GDDR6X | 0.0610622 | 5.54035e+06 |  | 1.17965e+06 | 0.053965 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 20.8516 |  |  |  |  | // | 0 sectors | 0 sectors | 3.58077e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.14585e+08 | 0 |  |  |  |  | GDDR6X | 1.00021 | 1.14585e+08 |  | 1.17965e+06 | 0.000877 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 28.4798 |  |  |  |  | // | 0 sectors | 0 sectors | 619724 sectors | 0 | 0 | 0 | 0 | 0 | 1.98312e+07 | 0 |  |  |  |  | GDDR6X | 0.682068 | 1.98312e+07 |  | 1.17965e+06 | 0.003405 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 95.0257 |  |  |  |  | // | 0 sectors | 0 sectors | 144 sectors | 0 | 0 | 0 | 0 | 0 | 4608 | 0 |  |  |  |  | GDDR6X | 0.00164914 | 4608 |  | 1.17965e+06 | 0.074362 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 19.7433 |  |  |  |  | // | 0 sectors | 0 sectors | 1.6871e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.39872e+07 | 0 |  |  |  |  | GDDR6X | 1.01638 | 5.39872e+07 |  | 1.17965e+06 | 0.002861 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 14.8257 |  |  |  |  | // | 0 sectors | 0 sectors | 619732 sectors | 0 | 0 | 0 | 0 | 0 | 1.98314e+07 | 0 |  |  |  |  | GDDR6X | 1.42607 | 1.98314e+07 |  | 1.17965e+06 | 0.009351 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | contiguous |  |  | 20.0474 |  |  |  |  | // | 0 sectors | 0 sectors | 1.7528e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.60897e+07 | 0 |  |  |  |  | GDDR6X | 1.00486 | 5.60897e+07 |  | 1.17965e+06 | 0.002726 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 12.4076 |  |  |  |  | // | 0 sectors | 0 sectors | 452724 sectors | 0 | 0 | 0 | 0 | 0 | 1.44872e+07 | 0 |  |  |  |  | GDDR6X | 1.79427 | 1.44872e+07 |  | 1.17965e+06 | 0.026176 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 19.5496 |  |  |  |  | // | 0 sectors | 0 sectors | 4.13326e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.32264e+08 | 0 |  |  |  |  | GDDR6X | 1.05159 | 1.32264e+08 |  | 1.17965e+06 | 0.001157 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 25.282 |  |  |  |  | // | 0 sectors | 0 sectors | 779352 sectors | 0 | 0 | 0 | 0 | 0 | 2.49393e+07 | 0 |  |  |  |  | GDDR6X | 0.775622 | 2.49393e+07 |  | 1.17965e+06 | 0.00454 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 115.487 |  |  |  |  | // | 0 sectors | 0 sectors | 4 sectors | 0 | 0 | 0 | 0 | 0 | 128 | 0 |  |  |  |  | GDDR6X | 4.5453e-05 | 128 |  | 1.17965e+06 | 0.103442 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 19.7186 |  |  |  |  | // | 0 sectors | 0 sectors | 1.86038e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.95322e+07 | 0 |  |  |  |  | GDDR6X | 1.01431 | 5.95322e+07 |  | 1.17965e+06 | 0.00353 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 17.5287 |  |  |  |  | // | 0 sectors | 0 sectors | 619808 sectors | 0 | 0 | 0 | 0 | 0 | 1.98339e+07 | 0 |  |  |  |  | GDDR6X | 1.26785 | 1.98339e+07 |  | 1.17965e+06 | 0.012863 |
| clocked_empty | not_selected | rejected | mode_not_final_component_candidate | contiguous |  |  | 22.4712 |  |  |  |  | // | 0 sectors | 0 sectors | 1.96784e+06 sectors | 0 | 0 | 0 | 0 | 0 | 6.29709e+07 | 0 |  |  |  |  | GDDR6X | 0.959425 | 6.29709e+07 |  | 1.17965e+06 | 0.003208 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 16.7146 |  |  |  |  | // | 0 sectors | 0 sectors | 621128 sectors | 0 | 0 | 0 | 0 | 0 | 1.98761e+07 | 0 |  |  |  |  | GDDR6X | 1.17703 | 1.98761e+07 |  | 1.17965e+06 | 0.027634 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 21.0999 |  |  |  |  | // | 0 sectors | 0 sectors | 8.01563e+06 sectors | 0 | 0 | 0 | 0 | 0 | 2.56455e+08 | 45440 |  |  |  |  | GDDR6X | 1.00363 | 2.565e+08 |  | 1.17965e+06 | 0.001275 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 21.4936 |  |  |  |  | // | 0 sectors | 0 sectors | 1.93098e+06 sectors | 0 | 0 | 0 | 0 | 0 | 6.17894e+07 | 2048 |  |  |  |  | GDDR6X | 0.966954 | 6.17915e+07 |  | 1.17965e+06 | 0.007164 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 103.113 |  |  |  |  | // | 0 sectors | 0 sectors | 0 sectors | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |  | GDDR6X | 0 | 0 |  | 1.17965e+06 | 0.111272 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  | 19.1785 | 27.1674 |  |  |  |  | // | 0 sectors | 0 sectors | 1.96207e+06 sectors | 0 | 0 | 0 | 0 | 2.07813e+07 | 6.15306e+07 | 1.25555e+06 |  |  |  |  | GDDR6X | 0.989861 | 6.27862e+07 |  | 1.17965e+06 | 0.011123 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 20.2173 |  |  |  |  | // | 0 sectors | 0 sectors | 517544 sectors | 0 | 0 | 0 | 0 | 0 | 1.65614e+07 | 0 |  |  |  |  | GDDR6X | 1.02965 | 1.65614e+07 |  | 1.17965e+06 | 0.014262 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator. GA100 uses a source-plus-LTC-fabric final-service hit rate; its coefficient therefore includes the workload-dependent partition-fabric cost and is not a pure local L2-SRAM coefficient. External-memory acceptance requires NCU read bytes, conserved global-read requests, at least 90% external-read service, and at most 1% write contamination. Its energy coefficient remains an effective GPU-device path value, not HBM/GDDR cell or package energy.
