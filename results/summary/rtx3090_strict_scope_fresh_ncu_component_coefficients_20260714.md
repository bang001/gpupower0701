# Strict Scope + Fresh NCU Component Coefficients

이 파일은 reliability audit에서 accepted로 판정된 component medians를 보고용 summary로 묶은 것이다. 새 계수를 다시 fitting하지 않으며, power measurement matrix 기준의 GPU/device total-energy delta와 NCU path validation 증거를 함께 기록한다.

- target profile: `rtx3090`
- interpretation: effective board-level microbenchmark coefficient
- not: pure transistor/silicon-level component energy

## Coefficients

| component | median | unit | CI | rows | NCU rows | denominator | confidence | condition |
|---|---:|---|---|---:|---:|---|---|---|
| Tensor MMA incremental | 2.14027815652 | pJ/FLOP | 2.11405120959-2.17044428343 | 75 | 30 | logical_or_expected | medium-high | W_SM=1 KiB; blocks/SM=4,8,16; active_SM=82; RF=1,2,4,8,16; median_elapsed=10.381 s |
| Shared scalar path | 0.713811591343 | pJ/bit | 0.680056491498-0.923269576486 | 15 | 6 | ncu_actual_exact | medium-high | W_SM=64 KiB; blocks/SM=8; active_SM=82; LR=4,8,16; median_elapsed=10.244 s |
| Global L1 hit path | 0.85247325547 | pJ/bit | 0.812534220764-0.888414528309 | 15 | 21 | ncu_actual_exact | medium-high | W_SM=8 KiB; blocks/SM=8; active_SM=82; LR=4,8,16; median_elapsed=11.208 s |
| L2 CG hit path | 9.0784023317 | pJ/bit | 8.93519257269-9.29863220175 | 30 | 24 | ncu_actual_exact | medium-high | W_SM=32 KiB,64 KiB; blocks/SM=8; active_SM=82; LR=4,8,16; median_elapsed=10.936 s |

## Report-Ready Table

이 표는 백서/발표에 바로 옮길 수 있도록 수치, 단위, 실험 pair, NCU 검증 근거, 해석 주의점을 한 줄에 묶은 것이다.

| component | report value | treatment-control pair | NCU validation evidence | interpretation caveat |
|---|---:|---|---|---|
| Tensor MMA incremental | 2.14027815652 pJ/FLOP | `reg_mma - reg_operand_only` | HMMA_inst=65600000/524800000/4198400000; HMMA/logical_MMA=2; Tensor/control_regs_per_thread=28/28/34/16; control_HMMA=0; L1_bytes=0; local_read/write_bytes=0/0; spill_zero_verified=1; spill_read/write=0/0 | Tensor validation uses architecture-local HMMA/logical-MMA linearity, zero-HMMA control, explicit treatment/control register footprints, and zero spill/local traffic. The pJ/FLOP value includes the unmatched Tensor operand/accumulator register path and is not pure Tensor circuitry. |
| Shared scalar path | 0.713811591343 pJ/bit | `shared_scalar_load_only - shared_scalar_addr_only` | shared_bytes=268703000000/537401000000/1.0748e+12; global_L1_bytes=0; DRAM_bytes=60011600/119531000/272850000 | Shared path validation uses shared-memory byte/access counters; global L1/L2 hit-rate fields are background context, not the shared hit rate. |
| Global L1 hit path | 0.85247325547 pJ/bit | `global_l1_load_only - global_addr_only` | L1_path_hit_pct=99.9998/99.9999/99.9999; L1_accesses=8396800000/16793600000/33587200000; L1_request/hit_bytes=268698000000/537395000000/1.07479e+12/268697000000/537395000000/1.07479e+12; DRAM_bytes=75999200/140728000/278439000 | Global-L1 validation uses path-specific global-load lookup hit/miss and request bytes. Aggregate L1 hit rate can include unrelated traffic. |
| L2 CG hit path | 9.0784023317 pJ/bit | `l2_cg_load_only - global_addr_only` | L1_path_hit_pct=0; L1_request/hit_bytes=268698000000/537395000000/1.07479e+12/0; L2_direct/logical_hit_pct=99.9974/99.99935/100/; LTC_fabric_hit/fraction=/; L2_read_hit/miss_sectors=8396720000/16793550000/33587100000/0/152980/218397; L2_read_bytes=268698000000/537397500000/1.0748e+12; DRAM_bytes=136675000/275038000/557497000; DRAM_read_bytes=136675000/271763500/550518000 | An ld.global.cg request still traverses L1TEX, so L1 request bytes are expected. Bypass is shown by near-zero path-specific L1 hit bytes and a high final-service L2 read hit rate; L2 read bytes are the denominator. On GA100/GH100 fabric-aware profiles, final service combines direct-partition and LTC-fabric hits, so those coefficients include partition-fabric traffic; GA102/GV100 direct-path profiles do not use that model. |

## NCU Evidence Summary

각 값은 strict energy row와 같은 `mode,W_SM,blocks/SM,active_SM,reuse_factor,load_repeat,store_repeat` 좌표에서 수집한 treatment-path NCU row의 `min/median/max` 요약이다. 단일 값이면 하나만 표시한다. Shared scalar와 Tensor row의 global cache hit-rate counter는 path 판정의 주 증거가 아니라 background context이므로 `path evidence`와 함께 읽어야 한다.

### Path-Relevant Evidence

| component | path evidence | caveat |
|---|---|---|
| Tensor MMA incremental | HMMA_inst=65600000/524800000/4198400000; HMMA/logical_MMA=2; Tensor/control_regs_per_thread=28/28/34/16; control_HMMA=0; L1_bytes=0; local_read/write_bytes=0/0; spill_zero_verified=1; spill_read/write=0/0 | Tensor validation uses architecture-local HMMA/logical-MMA linearity, zero-HMMA control, explicit treatment/control register footprints, and zero spill/local traffic. The pJ/FLOP value includes the unmatched Tensor operand/accumulator register path and is not pure Tensor circuitry. |
| Shared scalar path | shared_bytes=268703000000/537401000000/1.0748e+12; global_L1_bytes=0; DRAM_bytes=60011600/119531000/272850000 | Shared path validation uses shared-memory byte/access counters; global L1/L2 hit-rate fields are background context, not the shared hit rate. |
| Global L1 hit path | L1_path_hit_pct=99.9998/99.9999/99.9999; L1_accesses=8396800000/16793600000/33587200000; L1_request/hit_bytes=268698000000/537395000000/1.07479e+12/268697000000/537395000000/1.07479e+12; DRAM_bytes=75999200/140728000/278439000 | Global-L1 validation uses path-specific global-load lookup hit/miss and request bytes. Aggregate L1 hit rate can include unrelated traffic. |
| L2 CG hit path | L1_path_hit_pct=0; L1_request/hit_bytes=268698000000/537395000000/1.07479e+12/0; L2_direct/logical_hit_pct=99.9974/99.99935/100/; LTC_fabric_hit/fraction=/; L2_read_hit/miss_sectors=8396720000/16793550000/33587100000/0/152980/218397; L2_read_bytes=268698000000/537397500000/1.0748e+12; DRAM_bytes=136675000/275038000/557497000; DRAM_read_bytes=136675000/271763500/550518000 | An ld.global.cg request still traverses L1TEX, so L1 request bytes are expected. Bypass is shown by near-zero path-specific L1 hit bytes and a high final-service L2 read hit rate; L2 read bytes are the denominator. On GA100/GH100 fabric-aware profiles, final service combines direct-partition and LTC-fabric hits, so those coefficients include partition-fabric traffic; GA102/GV100 direct-path profiles do not use that model. |

### Raw Counter Context

| component | coord rows | metric rows | metric modes | L1 path hit % | L2 read hit % | L1 accesses | L2 accesses | DRAM accesses | shared bytes | shared read bytes | shared write bytes | L1 request bytes | L1 hit bytes | L2 read bytes | DRAM bytes | HMMA inst | HMMA/logical MMA | Tensor/control regs/thread | Tensor pipe active % | achieved occupancy % | launch warp capacity % | long scoreboard % |
|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Tensor MMA incremental | 30 | 15 | reg_mma |  | 100 | 0 | 0/0/218587 | 104312/704588/7832040 | 0 | 0 | 0 | 0 | 0 | 0/0/6994780 | 3337980/22546800/250625000 | 65600000/524800000/4198400000 | 2 | 28/28/34/16 | 38.9013/44.9522/48.5666 | 8.17977/13.9473/23.1075 | 33.3333 | 0.001051/0.007569/0.03333 |
| Shared scalar path | 6 | 3 | shared_scalar_load_only |  | 100 | 0 | 0/0/467539 | 1875360/3735330/8526550 | 268703000000/537401000000/1.0748e+12 | 268698000000/537395000000/1.07479e+12 | 5373950 | 0 | 0 | 0/0/14961200 | 60011600/119531000/272850000 | 0 |  | 26/26 | 0 | 16.6659/16.6659/16.6666 | 22.9167 | 0.000602/0.001231/0.002227 |
| Global L1 hit path | 6 | 3 | global_l1_load_only | 99.9998/99.9999/99.9999 | 0.282692/12.9492/100 | 8396800000/16793600000/33587200000 | 20992 | 2374980/4397760/8701220 | 0 | 0 | 0 | 268698000000/537395000000/1.07479e+12 | 268697000000/537395000000/1.07479e+12 | 671744 | 75999200/140728000/278439000 | 0 |  | 33/34 | 0 | 16.6508/16.6637/16.6665 | 33.3333 | 1.48444/2.04036/2.59079 |
| L2 CG hit path | 12 | 6 | l2_cg_load_only | 0 | 99.9974/99.99935/100 | 8396800000/16793600000/33587200000 | 8396800000/16793700000/33587400000 | 4271100/8594945/17421800 |  |  |  | 268698000000/537395000000/1.07479e+12 | 0 | 268698000000/537397500000/1.0748e+12 | 136675000/275038000/557497000 |  |  | 38/34 |  |  | 33.3333 | 365.312/396.113/414.793 |

## NCU Coordinate Evidence

| component | exact NCU coordinates |
|---|---|
| Tensor MMA incremental | `reg_mma:W1:B16:SM82:RF1:LR1:SR1;reg_mma:W1:B16:SM82:RF16:LR1:SR1;reg_mma:W1:B16:SM82:RF2:LR1:SR1;reg_mma:W1:B16:SM82:RF4:LR1:SR1;reg_mma:W1:B16:SM82:RF8:LR1:SR1;reg_mma:W1:B4:SM82:RF1:LR1:SR1;reg_mma:W1:B4:SM82:RF16:LR1:SR1;reg_mma:W1:B4:SM82:RF2:LR1:SR1;reg_mma:W1:B4:SM82:RF4:LR1:SR1;reg_mma:W1:B4:SM82:RF8:LR1:SR1;reg_mma:W1:B8:SM82:RF1:LR1:SR1;reg_mma:W1:B8:SM82:RF16:LR1:SR1;reg_mma:W1:B8:SM82:RF2:LR1:SR1;reg_mma:W1:B8:SM82:RF4:LR1:SR1;reg_mma:W1:B8:SM82:RF8:LR1:SR1;reg_operand_only:W1:B16:SM82:RF1:LR1:SR1;reg_operand_only:W1:B16:SM82:RF16:LR1:SR1;reg_operand_only:W1:B16:SM82:RF2:LR1:SR1;reg_operand_only:W1:B16:SM82:RF4:LR1:SR1;reg_operand_only:W1:B16:SM82:RF8:LR1:SR1;reg_operand_only:W1:B4:SM82:RF1:LR1:SR1;reg_operand_only:W1:B4:SM82:RF16:LR1:SR1;reg_operand_only:W1:B4:SM82:RF2:LR1:SR1;reg_operand_only:W1:B4:SM82:RF4:LR1:SR1;reg_operand_only:W1:B4:SM82:RF8:LR1:SR1;reg_operand_only:W1:B8:SM82:RF1:LR1:SR1;reg_operand_only:W1:B8:SM82:RF16:LR1:SR1;reg_operand_only:W1:B8:SM82:RF2:LR1:SR1;reg_operand_only:W1:B8:SM82:RF4:LR1:SR1;reg_operand_only:W1:B8:SM82:RF8:LR1:SR1` |
| Shared scalar path | `shared_scalar_addr_only:W64:B8:SM82:RF1:LR16:SR1;shared_scalar_addr_only:W64:B8:SM82:RF1:LR4:SR1;shared_scalar_addr_only:W64:B8:SM82:RF1:LR8:SR1;shared_scalar_load_only:W64:B8:SM82:RF1:LR16:SR1;shared_scalar_load_only:W64:B8:SM82:RF1:LR4:SR1;shared_scalar_load_only:W64:B8:SM82:RF1:LR8:SR1` |
| Global L1 hit path | `global_addr_only:W8:B8:SM82:RF1:LR16:SR1;global_addr_only:W8:B8:SM82:RF1:LR4:SR1;global_addr_only:W8:B8:SM82:RF1:LR8:SR1;global_l1_load_only:W8:B8:SM82:RF1:LR16:SR1;global_l1_load_only:W8:B8:SM82:RF1:LR4:SR1;global_l1_load_only:W8:B8:SM82:RF1:LR8:SR1` |
| L2 CG hit path | `global_addr_only:W32:B8:SM82:RF1:LR16:SR1;global_addr_only:W32:B8:SM82:RF1:LR4:SR1;global_addr_only:W32:B8:SM82:RF1:LR8:SR1;global_addr_only:W64:B8:SM82:RF1:LR16:SR1;global_addr_only:W64:B8:SM82:RF1:LR4:SR1;global_addr_only:W64:B8:SM82:RF1:LR8:SR1;l2_cg_load_only:W32:B8:SM82:RF1:LR16:SR1;l2_cg_load_only:W32:B8:SM82:RF1:LR4:SR1;l2_cg_load_only:W32:B8:SM82:RF1:LR8:SR1;l2_cg_load_only:W64:B8:SM82:RF1:LR16:SR1;l2_cg_load_only:W64:B8:SM82:RF1:LR4:SR1;l2_cg_load_only:W64:B8:SM82:RF1:LR8:SR1` |

## Evidence Artifacts

| artifact type | path |
|---|---|
| `matched_summary_artifact` | `results/summary/rtx3090_component_finalplan_20260714_matched_control_summary.csv` |
| `matched_detail_artifact` | `results/summary/rtx3090_component_finalplan_20260714_matched_control_detail.csv` |
| `power_api_audit_artifact` | `results/summary/rtx3090_component_finalplan_20260714_power_api_audit.csv` |
| `power_state_audit_artifact` | `results/summary/rtx3090_component_finalplan_20260714_power_state_audit.csv` |
| `reliability_artifact` | `results/summary/rtx3090_component_finalplan_20260714_component_reliability_audit.csv` |
| `ncu_acceptance_artifact` | `results/summary/rtx3090_component_finalplan_20260714_ncu_acceptance.csv` |
| `ncu_summary_artifact` | `results/ncu/rtx3090_component_finalplan_ncu_factor_20260714/ncu_cache_validation_summary.csv` |
| `instability_artifact` | `results/summary/rtx3090_component_finalplan_20260714_matched_control_instability_audit.csv` |

## Reporting Note

These values are not direct silicon-level Tensor/L1/L2 circuit energy. They are workload-dependent effective coefficients from board-level energy deltas, matched-control subtraction, and NCU counter validation.
