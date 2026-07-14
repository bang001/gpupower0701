# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| register_control_candidate | 5 | 0 | 0 |
| tensor_increment_candidate | 5 | 0 | 0 |

## Tensor Pair Diagnostics

The HMMA/logical-MMA ratio is allowed to differ by architecture, but must stay stable across RF at each blocks/SM coordinate. Register counts expose the treatment/control footprint mismatch rather than claiming pure Tensor-circuit isolation.

| mode | blocks/SM | RF | HMMA | logical MMA | HMMA/logical | FP16-to-FP32 ops | expected FLOP | ops/expected | group median | relative spread | control pair | Tensor pipe active (%) | registers/thread | acceptance |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| reg_mma | 4 | 1 | 6.56e+07 | 3.28e+07 | 2 |  | 2.68698e+11 |  | 2 | 0 | accepted | 47.4384 | 35 | accepted |
| reg_mma | 4 | 16 | 1.0496e+09 | 5.248e+08 | 2 |  | 4.29916e+12 |  | 2 | 0 | accepted | 43.7226 | 30 | accepted |
| reg_mma | 4 | 2 | 1.312e+08 | 6.56e+07 | 2 |  | 5.37395e+11 |  | 2 | 0 | accepted | 39.7471 | 26 | accepted |
| reg_mma | 4 | 4 | 2.624e+08 | 1.312e+08 | 2 |  | 1.07479e+12 |  | 2 | 0 | accepted | 41.9647 | 30 | accepted |
| reg_mma | 4 | 8 | 5.248e+08 | 2.624e+08 | 2 |  | 2.14958e+12 |  | 2 | 0 | accepted | 43.0963 | 30 | accepted |
| reg_operand_only | 4 | 1 | 0 |  |  |  |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 16 | 0 |  |  |  |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 2 | 0 |  |  |  |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 4 | 0 |  |  |  |  |  |  |  |  | 0 | 16 | accepted |
| reg_operand_only | 4 | 8 | 0 |  |  |  |  |  |  |  |  | 0 | 16 | accepted |

| mode | component | acceptance | reason | L2 layout | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | L2 logical hit (%) | L2 fabric hit (%) | acceptance model | native/model delta (pp) | source/fabric/model coherent | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM write bytes | DRAM-read/L2-read | source/expected | external-read/expected | write/read | memory technology | DRAM read GB/s | DRAM bytes | L2 observed/expected | persisting L2 size (bytes) | long SB (%) |
|---||---||---||---||---||---||---||---||---||---||---||---||---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 103.579 |  |  |  |  | // | 0 sectors | 0 sectors | 41668 sectors | 0 | 0 | 0 | 0 | 0 | 1.33338e+06 | 0 |  |  |  |  | GDDR6X | 0.000338877 | 1.33338e+06 |  | 1.17965e+06 | 0.026054 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 20.0829 |  |  |  |  | // | 0 sectors | 0 sectors | 1.95928e+06 sectors | 0 | 0 | 0 | 0 | 0 | 6.26971e+07 | 0 |  |  |  |  | GDDR6X | 0.00103587 | 6.26971e+07 |  | 1.17965e+06 | 0.002065 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 11.5757 |  |  |  |  | // | 0 sectors | 0 sectors | 314512 sectors | 0 | 0 | 0 | 0 | 0 | 1.00644e+07 | 0 |  |  |  |  | GDDR6X | 0.0012186 | 1.00644e+07 |  | 1.17965e+06 | 0.008721 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 19.8401 |  |  |  |  | // | 0 sectors | 0 sectors | 509640 sectors | 0 | 0 | 0 | 0 | 0 | 1.63085e+07 | 0 |  |  |  |  | GDDR6X | 0.00104097 | 1.63085e+07 |  | 1.17965e+06 | 0.004278 |
| reg_mma | tensor_increment_candidate | accepted | pass | contiguous |  |  | 18.7188 |  |  |  |  | // | 0 sectors | 0 sectors | 1.14516e+06 sectors | 0 | 0 | 0 | 0 | 0 | 3.6645e+07 | 0 |  |  |  |  | GDDR6X | 0.00120098 | 3.6645e+07 |  | 1.17965e+06 | 0.002256 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 86.6828 |  |  |  |  | // | 0 sectors | 0 sectors | 3228 sectors | 0 | 0 | 0 | 0 | 0 | 103296 | 0 |  |  |  |  | GDDR6X | 2.90811e-05 | 103296 |  | 1.17965e+06 | 570.384 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 86.9988 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 9.34579e-07 | 3200 |  | 1.17965e+06 | 876.593 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 88.2784 |  |  |  |  | // | 0 sectors | 0 sectors | 212 sectors | 0 | 0 | 0 | 0 | 0 | 6784 | 0 |  |  |  |  | GDDR6X | 1.98131e-06 | 6784 |  | 1.17965e+06 | 556.591 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 79.8441 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 9.34579e-07 | 3200 |  | 1.17965e+06 | 565.643 |
| reg_operand_only | register_control_candidate | accepted | pass | contiguous |  |  | 85.159 |  |  |  |  | // | 0 sectors | 0 sectors | 100 sectors | 0 | 0 | 0 | 0 | 0 | 3200 | 0 |  |  |  |  | GDDR6X | 9.52381e-07 | 3200 |  | 1.17965e+06 | 552.246 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator. GA100 uses a source-plus-LTC-fabric final-service hit rate; its coefficient therefore includes the workload-dependent partition-fabric cost and is not a pure local L2-SRAM coefficient. External-memory acceptance requires NCU read bytes, conserved global-read requests, at least 90% external-read service, and at most 1% write contamination. Its energy coefficient remains an effective GPU-device path value, not HBM/GDDR cell or package energy.
