# Tensor MMA Binary Audit

- profile: `rtx3090`
- binary: `build/a100_fp16_energy_v2`
- verdict: `pass`
- API scope: `wmma::mma_sync m16n16k16 FP16 input / FP32 accumulate`
- expected lowering: architecture-specific `HMMA` compatibility path

Static SASS counts only prove that an opcode exists in a compiled kernel. They do not equal runtime instruction counts. NCU must separately prove HMMA/logical-MMA linearity across RF and zero HMMA in the control.

| RF | treatment HMMA | control HMMA | treatment/control registers/thread | predicated treatment HMMA | control backward branches | WGMMA/TMA | LDG/LDS treatment | local treatment/control | status |
|---:|---:|---:|---|---:|---:|---|---|---|---|
| 1 | 10 | 0 | 34/16 | 0 | 3 | 0/0 | 0/0 | 0/0 | pass |
| 2 | 2 | 0 | 28/16 | 0 | 2 | 0/0 | 0/0 | 0/0 | pass |
| 4 | 2 | 0 | 28/16 | 0 | 2 | 0/0 | 0/0 | 0/0 | pass |
| 8 | 2 | 0 | 28/16 | 0 | 2 | 0/0 | 0/0 | 0/0 | pass |
| 16 | 2 | 0 | 28/16 | 0 | 2 | 0/0 | 0/0 | 0/0 | pass |

## Interpretation

A register-footprint difference is expected in the current implementation: the treatment keeps WMMA operand and accumulator fragments live, while ptxas reduces the no-MMA control. Therefore the measured coefficient is the incremental effective board-level WMMA/HMMA plus its register/scheduler path, not pure Tensor Core circuit energy and not an isolated register coefficient.
