# RTX 3090 Component Energy Iteration Report

작성 시점: 2026-07-05

## 결론 요약

이번 순환 실험에서는 기존의 불안정한 전체 회귀 대신, NCU로 path가 검증된 mode만 energy 분석에 사용했다. 그 결과 memory hierarchy 쪽은 reference order와 대체로 정합하는 값이 나왔고, Tensor Core incremental 값도 B16 조건에서 이전 B4보다 안정화됐다.

Register 값은 아직 pure register-file energy로 주장하면 안 된다. `reg_pressure` 256 B/block은 NCU accepted였지만 scalar integer update, dependency, scheduler/control이 섞인 register-pressure proxy다. 8192 B/block은 ptxas spill-free였음에도 NCU에서 L2/DRAM traffic이 커서 rejected됐다.

## NCU Path Acceptance

대표 acceptance 파일:

- `results/summary/rtx3090_component_sep_ncu_scalarshared_regb16_regpressure256_acceptance_20260705.md`
- `results/ncu/rtx3090_component_sep_ncu_scalarshared_regb16_regpressure256_20260705/ncu_cache_validation_summary.csv`

| mode | component candidate | acceptance | 핵심 검증 지표 | 해석 |
|---|---|---|---|---|
| `reg_mma` | tensor incremental | accepted | HMMA inst 2.624e8, L1 bytes 0, L2 bytes 4.22e7 B, DRAM bytes 3.26e7 B | Tensor path 후보로 사용 |
| `reg_operand_only` | register control | accepted | HMMA inst 0, L1 bytes 0, L2 bytes 4.65e7 B, DRAM bytes 3.65e7 B | `reg_mma`의 no-MMA matched control |
| `reg_pressure` 256 B/block | register pressure | accepted | HMMA inst 0, L1 bytes 0, L2 bytes 3.57e7 B, DRAM bytes 2.75e7 B | 작은 scalar register-pressure proxy로만 사용 |
| `reg_pressure` 8192 B/block | register pressure | rejected | L2 bytes 4.54e8 B, DRAM bytes 3.63e8 B | clean register 결과로 사용 금지 |
| `shared_scalar_load_only` | shared/L1 scalar path | accepted | shared bytes 5.374e11 B, bank conflict 0 | clean shared/L1 scalar load path |
| `shared_load_only` | shared WMMA operand path | rejected | shared bytes는 맞지만 bank conflict high | clean shared component로 사용 금지 |
| `global_l1_load_only` | global L1 hit path | accepted | L1 hit 약 99.999%, L1 bytes 1.075e12 B | L1 hit path 후보 |
| `l2_cg_load_only` | L2 hit path | accepted | L1 hit 약 0%, L2 hit 약 99.93%, DRAM/L2 낮음 | L2 hit path 후보 |
| `l2_load_only` | L2 capacity path | rejected | L1 hit 약 88% | L2-only 결과로 사용 금지 |
| `dram_cg_load_only` | DRAM sanity path | accepted | L1 hit 약 0%, L2 hit 약 0.16%, DRAM bytes 약 5.39e11 B | DRAM streaming sanity path |

## Component Energy Results

Energy result files:

- `results/summary/rtx3090_component_matched_control_b16_summary_20260705.csv`
- `results/summary/rtx3090_component_matched_control_b16_report_20260705.md`
- `results/summary/rtx3090_reg_pressure_b16_summary_20260705.csv`
- `results/summary/rtx3090_register_pressure_263pj_audit_20260705_ko.md`

| component | estimate | unit | min | max | rows used | status | method |
|---|---:|---|---:|---:|---:|---|---|
| Tensor MMA incremental | 0.146 | pJ/FLOP | 0.0349 | 0.271 | 6 | accepted candidate | `reg_mma - reg_operand_only`, B16, power-matched |
| Register pressure 256 B/block | 263.0 | pJ/reg-update | 263.0 | 263.0 | 1 | rejected as register energy | direct division 값. fixed active/control/ALU 포함으로 component 값에서 제외 |
| Register pressure slope, all payloads | 14.5 | pJ/reg-update | 5.14 | 20.4 | 6 | provisional proxy only | power-rate slope. 512/1024 payload NCU 검증 전이므로 final 아님 |
| Shared/L1 scalar path | 0.223 | pJ/bit | 0.0150 | 0.783 | 6 | accepted candidate | `shared_scalar_load_only - clocked_empty` |
| Global L1 hit path | 0.449 | pJ/bit | 0.0201 | 0.502 | 4 | accepted candidate with noise | `global_l1_load_only - clocked_empty` |
| L2 hit path | 0.798 | pJ/bit | 0.547 | 2.539 | 5 | accepted candidate | `l2_cg_load_only - clocked_empty` |
| DRAM streaming path | 4.48 | pJ/bit | 2.13 | 6.04 | 3 | sanity candidate | `dram_cg_load_only - clocked_empty` |

## Rejected Or Limited Results

| item | reason | decision |
|---|---|---|
| Fixed-ITER memory smoke | elapsed가 너무 짧고 net energy 음수가 많았음 | 폐기 |
| Global OLS/NNLS one-shot fit | mode baseline과 byte variation이 얽혀 DRAM coefficient가 reference와 맞지 않게 튐 | 최종값으로 사용 금지 |
| `shared_load_only` | shared bytes는 맞지만 bank conflict가 큼 | clean shared component에서 제외 |
| `l2_load_only` | L1 hit가 높아 L2-only가 아님 | L2 값에서 제외 |
| `reg_mma - reg_operand_only`, B4 | 7개 reuse 중 3개 음수 | B16 결과로 대체 |
| `reg_mma - clocked_empty`, B16 | `clocked_empty` power가 커서 전부 음수 | tensor/register path로 사용 금지 |
| `reg_pressure` 8192 B/block | NCU에서 L2/DRAM traffic 과다 | register clean 결과에서 제외 |
| `reg_pressure` 256 B/block direct 263 pJ/update | 3초 active scalar loop energy를 작은 update count로 나눈 값 | register component energy로 사용 금지 |

## Interpretation

이번 결과는 “effective microbenchmark coefficient”다. NVML board energy, scheduler, issue, dependency, control path가 포함된다. 특히 register direct 값 263 pJ/update는 pure register-file bitcell energy가 아니며, 현재 component result에서 제외해야 한다.

Reference와 비교할 때 RTX 3090 DRAM 4.48 pJ/bit를 HBM2 device-level 3.9 pJ/bit와 직접 정합한다고 쓰면 안 된다. RTX 3090은 GDDR6X 기반이고, 현재 값은 `dram_cg_load_only - clocked_empty`에서 나온 effective streaming-path sanity candidate일 뿐이다. L2 0.80 pJ/bit, L1/shared 0.22-0.45 pJ/bit도 physical SRAM bitcell 값이 아니라 NCU path가 확인된 microbenchmark coefficient 후보로 제한해서 해석한다.

## Next Iteration

| priority | action | reason |
|---:|---|---|
| 1 | memory path repeats를 3회 이상, seconds 5-10으로 확대 | L1/L2 일부 negative row를 줄이고 min/max 신뢰도 개선 |
| 2 | `reg_pressure` payload 256/512/1024 B를 각각 NCU 검증 | register proxy의 유효 payload 범위 확정 |
| 3 | B16 Tensor run repeats 3회 이상 수행 | 1개 negative reuse row 제거 가능성 확인 |
| 4 | A100/V100에서 같은 acceptance-first flow 반복 | architecture별 SM/L1/shared/L2 차이를 반영 |
