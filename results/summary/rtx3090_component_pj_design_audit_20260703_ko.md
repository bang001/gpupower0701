# RTX 3090 component pJ 설계/계산 오류 감사

작성일: 2026-07-03

## 결론

이전 `rtx3090_component_pj_summary_20260703_report_ko.md`의 “대표 component 계수” 표는 현재 형태로 보고서에 사용하면 안 된다. 값이 큰 이유는 GPU 내부 shared/L1/L2/register가 실제로 그렇게 비싸서가 아니라, 차분 설계와 denominator가 component energy를 분리하지 못했기 때문이다.

특히 `shared_load_only - empty`, `l2_load_only - empty`, `dram_load_only - empty`, `reg_pressure - empty`, `store_only - empty`를 component energy로 채택한 것이 잘못이다. 이 값들은 “커널 전체 dynamic energy를 static expected work로 나눈 값”에 가깝다.

## 즉시 무효 처리해야 할 표 항목

| 기존 표 항목 | 기존 값 | 기존 단위 | 판단 | 이유 |
|---|---:|---|---|---|
| Scalar register pressure | 140.563 | pJ/reg-update | component 값으로 무효 | register file access가 아니라 integer multiply/add/xor, dependency chain, issue/control, loop overhead가 포함된 compound scalar update 비용이다. |
| Small-footprint register pressure | 164.893 | pJ/reg-update | component 값으로 무효 | ptxas footprint 검증에는 의미가 있지만 physical register energy로 해석할 denominator가 아니다. |
| Shared/L1 load path | 54.753 | pJ/byte | component 값으로 무효 | `shared_load_only`가 5.44 s 동안 checksum 연산을 수행하고, `empty`는 0.013 s에 끝난다. 시간/연산 baseline이 맞지 않는다. |
| L2-hit load path | 63.736 | pJ/byte | component 값으로 무효 | L2 byte만 분리된 값이 아니라 WMMA load, checksum, address/control, 긴 실행시간의 active power가 포함된다. |
| DRAM streaming load path | 300.546 | pJ/byte | component 값으로 무효 | DRAM actual byte가 아니라 expected logical byte로 나눴고, 9.56 s load-only 실행시간의 대부분이 포함된다. |
| Global store path | 3880.915 | pJ/byte | component 값으로 무효 | 4-byte store 반복 수로 나눴지만 실제 cache writeback/sector traffic과 다르고, loop/control 및 write-combine/cache 효과가 섞인다. |
| Shared/L2/DRAM MMA incremental | negative | pJ/FLOP | 무효 | `*_mma - *_load_only`가 음수다. load-only control이 MMA kernel보다 무겁다는 직접 증거다. |

## 단위 관련 주의

기존 표의 memory 값은 `pJ/byte`다. bit 기준으로 바꾸면 다음과 같다.

| 항목 | pJ/byte | pJ/bit | 해석 |
|---|---:|---:|---|
| Shared/L1 load path | 54.753 | 6.844 | shared/L1로 보기에는 여전히 과대하다. |
| L2-hit load path | 63.736 | 7.967 | L2 hit가 HBM급 또는 그 이상으로 보이는 것은 비정상이다. |
| DRAM streaming load path | 300.546 | 37.568 | DRAM/HBM actual traffic 검증 없이 physical DRAM pJ/bit로 볼 수 없다. |
| Global store path | 3880.915 | 485.114 | store byte denominator가 physical memory traffic을 대표하지 못한다. |

사용자가 언급한 HBM 약 4.3 pJ/bit 기준과 비교하면, shared/L1과 L2 hit가 6.8~8.0 pJ/bit로 나오는 것은 물리 계층 순서와 맞지 않는다. 이것은 값이 새로운 발견이라는 뜻이 아니라 계산이 component를 잘못 잡았다는 신호다.

## 원인 1: `empty` baseline이 시간 baseline이 아니다

component-pair runner는 reference mode에서 `ITER`를 calibrate한 뒤 같은 `ITER`를 다른 mode에 넣는다. 그러나 `--iters`가 지정되면 각 mode는 같은 시간 동안 실행되지 않는다. raw median elapsed는 다음과 같다.

| 조건 | mode | ITER | median elapsed | median net_E_J |
|---|---|---:|---:|---:|
| W=64 KiB | empty | 3,981,322 | 0.012589 s | -1.555 J |
| W=64 KiB | shared_load_only | 3,981,322 | 5.435882 s | 1169.904 J |
| W=64 KiB | shared_mma | 3,981,322 | 3.351806 s | 518.002 J |
| W=64 KiB | empty | 3,411,304 | 0.010792 s | -1.340 J |
| W=64 KiB | l2_load_only | 3,411,304 | 5.811126 s | 1167.087 J |
| W=64 KiB | l2_mma | 3,411,304 | 3.456112 s | 665.168 J |
| W=8192 KiB | empty | 1,438,005 | 0.007917 s | -1.007 J |
| W=8192 KiB | dram_load_only | 1,438,005 | 9.557519 s | 2321.540 J |
| W=8192 KiB | dram_mma | 1,438,005 | 3.515377 s | 750.910 J |

따라서 `shared_load_only - empty`는 5.44초 커널에서 0.013초 커널을 뺀 값이다. 이 차이는 shared/L1 byte energy가 아니라 긴 실행시간 동안의 active GPU dynamic energy가 대부분이다.

관련 코드: `scripts/analyze_component_pairs.py:47-85`는 `*_load_only - empty`를 직접 pJ/byte로 정의하고, `src/main.cu:735-743`은 static expected byte만 denominator로 기록한다.

## 원인 2: `load_only`가 load-only가 아니다

`shared_load_only_kernel`과 `global_load_only_kernel`은 매 load마다 fragment checksum을 누적한다. 이 checksum은 fragment element 접근, half-to-float 변환, FP add, dependency chain을 만든다.

| 코드 위치 | 문제 | 영향 |
|---|---|---|
| `src/kernels.cu:266-273` | shared load 후 `checksum_fragment(a) + checksum_fragment(b)`를 매번 수행 | shared load energy에 checksum ALU/control 비용이 섞임 |
| `src/kernels.cu:400-412` | global load 후 매번 checksum 누적 | L2/DRAM load energy에 checksum 비용이 섞임 |
| `src/kernels.cu:307-318`, `351-368` | MMA kernel은 load 후 MMA를 수행하고 checksum 처리 구조가 다름 | `*_mma - *_load_only`가 같은 load baseline을 제거하지 못함 |

실제로 `shared_mma - shared_load_only`, `l2_mma - l2_load_only`, `dram_mma - dram_load_only`가 모두 음수로 나왔다. 이는 load-only control이 더 비싸다는 실험적 증거이며, 해당 pair 설계가 component 분리에 실패했다는 뜻이다.

## 원인 3: denominator가 actual hardware traffic이 아니다

현재 expected byte 계산은 다음 식이다.

```text
expected_operand_bytes = active_blocks * ITER * load_repeat * 1024 B
```

이 값은 logical WMMA operand byte다. NCU의 actual L1/L2/DRAM sector/byte counter가 아니다.

| 계층 | 왜 문제가 되는가 | 필요한 검증 |
|---|---|---|
| Shared/L1 | WMMA load instruction, bank behavior, fragment movement, checksum 연산이 함께 있음 | shared/L1 instruction count, sectors/transactions, stall |
| L2 | W=64 KiB가 L2 후보여도 actual L2 hit rate와 L1/L2 sector 수를 확인하지 않음 | L1 hit rate, L2 hit rate, L2 sectors/bytes |
| DRAM | expected logical byte와 actual DRAM byte는 cache linefill, replay, writeback, prefetch에 따라 다름 | DRAM sectors/bytes, L2 miss traffic |
| Store | 4-byte store 반복 수가 physical write traffic과 같지 않음 | L2 write sectors, DRAM write bytes |

즉 `pJ/byte = delta_E / expected_byte`는 “physical SRAM/HBM byte energy”가 아니다.

## 원인 4: register denominator가 register access 수가 아니다

`reg_pressure`의 denominator는 다음 식이다.

```text
expected_reg_pressure_ops = active_blocks * ITER * reuse_factor * 32 threads * payload_regs_per_thread
```

하지만 kernel 내부의 한 update는 단순 register read/write가 아니다.

| 코드 위치 | 실제 동작 | 영향 |
|---|---|---|
| `src/kernels.cu:223-229` | integer multiply, add, xor, dependency update, register read/write를 함께 수행 | pJ/reg-update는 register file energy가 아니라 scalar integer pipeline + RF + scheduler 계수 |
| `src/kernels.cu:219-230` | payload register 수가 바뀌면 unroll, instruction mix, occupancy도 바뀜 | payload sweep을 physical RF energy sweep으로 직접 해석할 수 없음 |

따라서 140 pJ/reg-update는 register file access energy로 보면 과대하고, 현재 값은 compound scalar update energy로만 표현해야 한다. 더 엄밀히는 이 항목도 component 표에서 제외하거나, `integer register-pressure kernel coefficient`로 이름을 바꿔야 한다.

## 원인 5: store pair는 동일 kernel 차분이라 component가 아니다

현재 `store_only`와 `store_path`는 둘 다 `store_path_kernel`을 launch한다. 따라서 `store_path - store_only`는 원칙적으로 0에 가까워야 하며, 실제로 음수다. `store_only - empty`도 empty와 실행시간이 맞지 않아 global store pJ/byte로 볼 수 없다.

관련 코드: `src/kernels.cu:422` 이후 store kernel, launch switch에서 `store_only`와 `store_path`가 같은 kernel을 호출한다.

## 원인 6: NCU 검증 없이 cache hierarchy label을 확정했다

문서에는 `Shared/L1`, `L2-hit`, `DRAM streaming`이라고 적었지만, 이번 focused run은 NCU actual counter를 사용하지 않았다. `smid_histogram_ok=true`는 placement 검증일 뿐 cache hit/access 검증이 아니다.

필수 NCU 항목:

| 계층 | 필요한 확인 |
|---|---|
| L1/shared | L1/shared hit rate, request/sector count, shared load transactions |
| L2 | L2 hit rate, L2 read sectors/bytes, L2 miss 비율 |
| DRAM | DRAM read/write sectors/bytes, L2 miss로 인한 DRAM traffic |
| Stall | long scoreboard, memory dependency, issue stall, tensor pipe utilization |

## 수정 방향

| 문제 | 수정안 |
|---|---|
| baseline 시간 불일치 | `empty` 대신 동일 elapsed를 갖는 `matched_control` 또는 회귀식의 `elapsed_s` 항 사용 |
| load-only checksum 과다 | checksum을 최소화하거나 `address_only`, `checksum_only`, `load_to_sink` control을 분리 |
| static expected byte | NCU actual L1/L2/DRAM bytes로 denominator 재계산 |
| register update 해석 | register file energy 대신 scalar register-pressure coefficient로 표기하거나 SASS instruction count로 normalize |
| 음수 MMA incremental | 해당 pair는 invalid 처리하고, load/control이 matching된 새로운 pair 설계 후 재측정 |
| store path | 실제 writeback byte를 NCU로 확인하고 overwrite/cache-hit store와 streaming store를 분리 |

## 문서 수정 원칙

보고서에는 다음처럼 써야 한다.

- 금지: “RTX 3090 shared/L1 energy는 54.753 pJ/byte다.”
- 허용: “현재 flawed load-only microbenchmark에서 `shared_load_only - empty`를 static expected byte로 나누면 54.753 pJ/byte가 나오지만, elapsed mismatch와 checksum overhead 때문에 physical shared/L1 energy로 해석할 수 없다.”
- 금지: “register energy는 140.563 pJ/reg-update다.”
- 허용: “`reg_pressure` 커널의 scalar dependency update 계수는 140.563 pJ/update로 관찰되었지만, 이는 register file access energy가 아니다.”

## 관련 산출물

- Flawed summary: `results/summary/rtx3090_component_pj_summary_20260703_report_ko.md`
- Component pair raw: `results/raw/rtx3090_component_pairs_focus_20260703.csv`
- Component pair summary: `results/summary/rtx3090_component_pairs_focus_20260703_summary.csv`
- Register footprint summary: `results/summary/rtx3090_register_footprint_focus_20260703_summary.csv`
