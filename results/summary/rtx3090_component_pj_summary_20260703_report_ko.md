# RTX 3090 component별 pJ 요약

> 경고: 이 문서의 기존 "대표값" 표는 component energy로 채택하면 안 된다.
> 후속 감사에서 `empty` baseline 시간 불일치, `load_only` checksum/control overhead,
> static expected byte denominator, NCU actual traffic 미검증 문제가 확인되었다.
> 정정 근거는 `results/summary/rtx3090_component_pj_design_audit_20260703_ko.md`를 참조한다.

## 핵심 표

아래 값은 RTX 3090, active_SM=82, blocks/SM=16, seconds=3, repeats=3 조건의 focused paired run 기준이다. 단위가 다른 항목을 섞지 않도록 register, FLOP, byte 계수를 분리했다.

| component | 차분식 | 조건 | coefficient | 단위 | 사용 여부 | 해석 |
|---|---|---|---:|---|---|---|
| Scalar register pressure | reg_pressure - empty | payload 4096~16384 B/block plateau | 140.563 | pJ/reg-update | 대표값 | pure register가 아니라 scalar register-pressure/control 계수 |
| Small-footprint register pressure | reg_pressure - empty | payload 1024 B/block, ptxas 2432 B/block | 164.893 | pJ/reg-update | 보조값 | 우리가 말한 작은 footprint 후보 |
| Tensor+register path | reg_mma - empty | W=64KiB, W=8192KiB, reuse=4, load=4, store=4 | 1.367 (1.333~1.402) | pJ/FLOP | 대표값 | effective Tensor Core + register operand path |
| Tensor incremental | reg_mma - reg_operand_only | W=64KiB, W=8192KiB, reuse=4, load=4, store=4 | 0.308 (0.280~0.337) | pJ/FLOP | 대표값 | MMA incremental after no-MMA register operand control |
| Register operand control | reg_operand_only - empty | W=64KiB, W=8192KiB, reuse=4, load=4, store=4 | 8673.498 (8626.031~8720.965) | pJ/reg-op | 대표값 | no-MMA fragment/control baseline; denominator is logical reg-op proxy |
| Shared/L1 load path | shared_load_only - empty | W=64KiB, reuse=4, load=4, store=4 | 54.753 | pJ/byte | 대표값 | effective shared/L1 operand load path |
| Shared MMA incremental | shared_mma - shared_load_only | W=64KiB, reuse=4, load=4, store=4 | -3.809 | pJ/FLOP | 보류/invalid | invalid when negative; load-only control is heavier |
| L2-hit load path | l2_load_only - empty | W=64KiB, reuse=4, load=4, store=4 | 63.736 | pJ/byte | 대표값 | effective L2-hit candidate operand load path |
| L2 MMA incremental | l2_mma - l2_load_only | W=64KiB, reuse=4, load=4, store=4 | -3.422 | pJ/FLOP | 보류/invalid | invalid when negative; load-only control is heavier |
| DRAM streaming load path | dram_load_only - empty | W=8192KiB, reuse=4, load=4, store=4 | 300.546 | pJ/byte | 대표값 | effective DRAM streaming operand load path |
| DRAM MMA incremental | dram_mma - dram_load_only | W=8192KiB, reuse=4, load=4, store=4 | -25.406 | pJ/FLOP | 보류/invalid | invalid when negative; load-only control is heavier |
| Global store path | store_only - empty | W=64KiB, W=8192KiB, reuse=4, load=4, store=4 | 3880.915 (3821.904~3939.925) | pJ/byte | 대표값 | effective global store path |
| Store path incremental | store_path - store_only | W=64KiB, W=8192KiB, reuse=4, load=4, store=4 | -436.264 (-441.108~-431.421) | pJ/byte | 보류/invalid | invalid here; same store kernel/noise dominated |

## 읽는 방법

- `pJ/FLOP`는 logical WMMA 기준이다. 1 logical MMA = 8192 FLOP이다.
- `pJ/byte`는 expected operand/store byte 기준이다. NCU actual byte가 아니라 static expected byte다.
- `pJ/reg-update`는 scalar `reg_pressure`의 update 수 기준이다. Tensor Core는 포함하지 않는다.
- 음수로 나온 `*_mma - *_load_only`는 component 값으로 쓰지 않는다. load-only kernel의 checksum/control 비용이 MMA kernel보다 커져 차분식이 깨진 것이다.

## 참고: mode-level effective path pJ/FLOP

아래는 순수 component 분해가 아니라 기존 full sweep에서 mode 전체를 `net_E_J / FLOP`로 나눈 값이다. 경향 설명에는 쓸 수 있지만 component 계수로 쓰면 안 된다.

| mode | median | min | max | 단위 | 비고 |
|---|---:|---:|---:|---|---|
| reg_mma | 0.885 | 0.464 | 2.017 | pJ/FLOP | full sweep mode-level |
| shared_mma | 5.087 | 0.435 | 10.266 | pJ/FLOP | full sweep mode-level |
| l2_mma | 5.824 | 2.178 | 8.870 | pJ/FLOP | full sweep mode-level |
| dram_mma | 35.626 | 12.732 | 60.145 | pJ/FLOP | full sweep mode-level |

## 자가점검

| 항목 | 결과 |
|---|---:|
| component-pair raw rows | 69 |
| component-pair summary rows | 18 |
| SMID histogram ok | 69/69 |
| energy source | nvml_total_energy |
| mode counts | {'empty': 21, 'reg_fragment_only': 6, 'reg_operand_only': 6, 'reg_mma': 6, 'shared_load_only': 3, 'shared_mma': 3, 'l2_load_only': 3, 'l2_mma': 3, 'store_only': 6, 'store_path': 6, 'dram_load_only': 3, 'dram_mma': 3} |

## 결론

현재 데이터로 보고서에 바로 쓸 수 있는 대표 component 계수는 `reg_pressure`, `reg_mma - empty`, `reg_mma - reg_operand_only`, `shared/L2/DRAM load_only - empty`, `store_only - empty`이다. 반대로 `shared_mma - shared_load_only`, `l2_mma - l2_load_only`, `dram_mma - dram_load_only`, `store_path - store_only`는 이번 focused run에서 음수이므로 component pJ로 채택하면 안 된다.

## 산출물

- Component pair raw: `results/raw/rtx3090_component_pairs_focus_20260703.csv`
- Component pair summary: `results/summary/rtx3090_component_pairs_focus_20260703_summary.csv`
- Register footprint summary: `results/summary/rtx3090_register_footprint_focus_20260703_summary.csv`
- Compact component CSV: `results/summary/rtx3090_component_pj_summary_20260703.csv`
