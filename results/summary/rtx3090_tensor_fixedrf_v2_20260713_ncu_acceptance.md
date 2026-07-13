# NCU Path Acceptance

Accepted rows are the only rows eligible for final component energy coefficients.

| component | accepted | provisional | rejected |
|---|---:|---:|---:|
| register_control_candidate | 5 | 0 | 0 |
| tensor_increment_candidate | 5 | 0 | 0 |

| mode | component | acceptance | reason | L1 path hit (%) | L2 derived read hit (%) | L2 native read hit (%) | native-derived delta (pp) | L2 sector conservation | L1 accesses | L2 accesses | DRAM accesses | shared bytes | L1 request bytes | L1 hit bytes | L2 read bytes | L2 miss bytes | DRAM read bytes | DRAM bytes | persisting L2 size (bytes) | long SB (%) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reg_mma | tensor_increment_candidate | accepted | pass |  |  | 18.8834 |  |  | 0 sectors | 0 sectors | 622320 sectors | 0 | 0 | 0 | 0 | 0 | 1.99142e+07 | 1.99142e+07 | 1.17965e+06 | 0.040975 |
| reg_mma | tensor_increment_candidate | accepted | pass |  | 34.2104 | 25.5525 | 8.65793 | 7.74192 | 0 sectors | 133902 sectors | 6.95814e+06 sectors | 0 | 0 | 0 | 4.28486e+06 | 2.18244e+07 | 2.22661e+08 | 2.29299e+08 | 1.17965e+06 | 0.002171 |
| reg_mma | tensor_increment_candidate | accepted | pass |  | 100 | 44.8591 | 55.1409 |  | 0 sectors | 0 sectors | 801360 sectors | 0 | 0 | 0 | 0 | 0 | 2.56435e+07 | 2.56435e+07 | 1.17965e+06 | 0.014821 |
| reg_mma | tensor_increment_candidate | accepted | pass |  | 100 | 30.4693 | 69.5307 |  | 0 sectors | 0 sectors | 1.86427e+06 sectors | 0 | 0 | 0 | 0 | 0 | 5.96567e+07 | 5.96567e+07 | 1.17965e+06 | 0.014239 |
| reg_mma | tensor_increment_candidate | accepted | pass |  |  | 21.2795 |  |  | 0 sectors | 0 sectors | 3.73618e+06 sectors | 0 | 0 | 0 | 0 | 0 | 1.19558e+08 | 1.20942e+08 | 1.17965e+06 | 0.01095 |
| reg_operand_only | register_control_candidate | accepted | pass |  |  | 36.1752 |  |  | 0 sectors | 0 sectors | 97356 sectors | 0 | 0 | 0 | 0 | 0 | 3.11539e+06 | 4.04442e+06 | 1.17965e+06 | 0.034879 |
| reg_operand_only | register_control_candidate | accepted | pass |  | 0 | 21.6082 | 21.6082 |  | 0 sectors | 0 sectors | 772124 sectors | 0 | 0 | 0 | 0 | 1.93618e+07 | 2.4708e+07 | 2.4708e+07 | 1.17965e+06 | 0.008326 |
| reg_operand_only | register_control_candidate | accepted | pass |  | 0 | 24.3572 | 24.3572 |  | 0 sectors | 0 sectors | 104268 sectors | 0 | 0 | 0 | 0 | 6.48746e+06 | 3.33658e+06 | 4.44454e+06 | 1.17965e+06 | 0.072287 |
| reg_operand_only | register_control_candidate | accepted | pass |  |  | 32.3658 |  |  | 0 sectors | 0 sectors | 154156 sectors | 0 | 0 | 0 | 0 | 0 | 4.93299e+06 | 5.94304e+06 | 1.17965e+06 | 0.027707 |
| reg_operand_only | register_control_candidate | accepted | pass |  |  | 46.1481 |  |  | 0 sectors | 0 sectors | 136504 sectors | 0 | 0 | 0 | 0 | 0 | 4.36813e+06 | 4.36813e+06 | 1.17965e+06 | 0.039868 |

Cache-path evidence rule: accepted memory-path rows must expose hit-rate evidence and at least the path-relevant byte/access counters. L1 accesses use request counters when available and otherwise fall back to sectors; L2 and DRAM accesses are sector counters. For `.cg`, L1 request bytes are expected because the request traverses L1TEX; bypass is proven by near-zero L1 path hit rate/hit bytes, not by zero L1 request bytes. L2 read bytes are the preferred L2 pJ/bit denominator.
