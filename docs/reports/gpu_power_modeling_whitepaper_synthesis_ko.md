# GPU Power Modeling 백서용 종합 정리

작성일: 2026-07-08

이 문서는 현재 저장소에서 유지하는 **active finalplan 기준** 백서 초안이다. 과거 raw sweep, 초기 pair difference, register-pressure 진단처럼 현재 coefficient 산출에 직접 쓰이지 않는 내용은 `archive/legacy_20260707/`로 이동했다. 과거 실험 흐름 전체를 보려면 `archive/legacy_20260707/docs/gpu_power_modeling_whitepaper_synthesis_history_ko.md`를 확인한다.

## 1. 핵심 주장

본 실험은 NVIDIA GPU 내부 회로의 순수 에너지를 직접 측정한 것이 아니다. CUDA microbenchmark를 treatment-control 형태로 실행하고, NVML board-level energy에서 control을 차분한 뒤, NCU counter로 해당 경로가 실제로 사용되었는지 검증하여 **workload-dependent effective board-level energy coefficient**를 추정한다.

따라서 백서에서 사용할 안전한 표현은 다음이다.

```text
NCU로 path가 검증된 board-level effective microbenchmark coefficient
```

피해야 할 표현은 다음이다.

```text
순수 Tensor Core 회로 에너지
순수 L1/L2 SRAM bitcell energy
순수 DRAM/HBM device energy
register file 단독 access energy
```

## 2. 현재 산출값

대상 결과는 RTX 3090 finalplan, 2026-07-08 stability/strict 재측정분을 현재 대표값으로 둔다. 단위가 다르므로 Tensor는 pJ/FLOP, memory path는 pJ/bit로 읽어야 한다.

전력 API 해석을 엄격히 적용하면 기존 대표값 중 일부는 raw CSV에
`measurement_scope` 컬럼이 도입되기 전의 inferred-scope 증거다. 그래서 2026-07-08에
새 binary로 `measurement_scope=gpu_device_total_energy_counter`가 직접 기록되는
strict rerun을 추가 수행했다. 이 strict rerun은 RTX 3090에서
`nvml_total_energy` + `total_energy_mj_delta`만 energy numerator로 쓰고,
`--require-explicit-measurement-scope` audit을 통과한 row만 사용한다. 또한
2026-07-08에 Nsight Compute를 공백 없는 WSL 경로(`/tmp/ncu2025/.../ncu`)로 복사해
fresh NCU sidecar를 다시 수집했고, Tensor/Shared/L1/L2 reliability가 모두
`accepted`임을 확인했다.
Strict summary audit은 189개 check 모두 pass, failure 0, warning 0이다. 여기에는
reliability/detail/power API artifact 정합성뿐 아니라 strict summary가 참조하는
NCU summary artifact의 L1/L2 hit rate, L1/L2/DRAM access count, L1/L2/DRAM byte traffic,
Tensor HMMA instruction, long-scoreboard stall 컬럼과 component-relevant OK mode row
검증이 포함된다. 또한 해당 NCU OK mode row가 strict matched-control detail의
`mode`, `W_SM_KiB`, `blocks_per_SM`, `active_SM`, `reuse_factor`, `load_repeat`,
`store_repeat` 좌표와 일치하는지까지 확인한다.
또한 `ncu_evidence_summary_fields` gate로 strict coefficient table 자체가
path-relevant NCU evidence를 노출하는지 확인한다. Shared scalar path의 global cache
hit-rate counter는 background context이며, shared-memory byte/access evidence를 주
증거로 해석한다.

![Strict measurement-scope coefficients](../assets/component_energy_method/rtx3090_strict_scope_component_coefficients.svg)

![RTX 3090 strict coefficient summary](../assets/component_energy_method/rtx3090_strict_scope_component_coefficients_summary.svg)

![RTX 3090 strict NCU evidence](../assets/component_energy_method/rtx3090_strict_scope_ncu_evidence.svg)

아래 표는 백서 본문에서 우선 인용할 수 있는 report-ready view다. 단위가 다른 Tensor와
memory path는 같은 축에서 크기 비교하지 않는다.

| Component/path | 보고값 | 단위 | 대표 treatment-control | NCU 검증 요지 | 해석 제한 |
|---|---:|---|---|---|---|
| Tensor MMA incremental | 0.129216 | pJ/FLOP | `reg_mma - reg_operand_only` | HMMA instruction 존재, L1 bytes 0 | Tensor transistor-level energy로 단정 금지 |
| Shared scalar path | 0.170590 | pJ/bit | `shared_scalar_load_only - clocked_empty` | shared bytes 1.0748e12, global L1 bytes 0 | global L1/L2 hit-rate는 shared path의 주 증거가 아님 |
| Global L1 hit path | 0.173483 | pJ/bit | `global_l1_load_only - clocked_empty` | L1 hit 99.9995%, L1 bytes 1.07479e12 | global-load L1-hit path의 effective coefficient |
| L2 CG hit path | 1.131073 | pJ/bit | `l2_cg_load_only - clocked_empty` | L1 hit 약 0%, L2 hit 약 99.985% | stall/control 영향이 남아 pure L2 SRAM energy가 아님 |

| Component/path | strict median | unit | rows | reliability | 해석 |
|---|---:|---|---:|---|---|
| Tensor MMA incremental | 0.129216 | pJ/FLOP | 6 | `accepted` | RF=8/16 strict 후보. 기존 RF-dependent range 안에 있음 |
| Shared scalar path | 0.170590 | pJ/bit | 6 | `accepted` | LR8-only strict follow-up. LR4/LR8 calibrated 0.161 pJ/bit는 보조 근거 |
| Global L1 hit path | 0.173483 | pJ/bit | 6 | `accepted` | LR4-only follow-up. LR8 weak-signal row를 분리한 accepted strict 후보 |
| L2 CG hit path | 1.131073 | pJ/bit | 6 | `accepted` | strict+fresh NCU 기준에서도 L1보다 큰 L2 coefficient가 유지됨 |

현재 strict final component table은 Tensor/Shared scalar/Global L1/L2 네 row만
허용한다. Register direct/register-pressure와 DRAM streaming은 각각 control/proxy 또는
sanity path이며, final component row로 승격하지 않는다.

상세 strict 결과는
[rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_coefficients_20260708.md)에
따로 고정했다. Fresh NCU reliability audit은
[rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md](../../results/summary/rtx3090_strict_scope_fresh_ncu_component_reliability_audit_20260708.md)에
남겼다. 첫 fresh NCU run은 Tensor `REG_BLOCKS_PER_SM=4`라 strict energy row의
`blocks_per_SM=16`과 맞지 않았고, Tensor는 `REG_BLOCKS_PER_SM=16` sidecar를 추가로
실행해 denominator/path를 맞췄다. Shared는 LR4/LR8 mixed strict row에서
LR4 weak row가 남아 있어 LR8-only accepted follow-up을 현재 strict 후보로 두고,
LR4/LR8 calibrated 0.161 pJ/bit는 method-sensitivity 보조 근거로 둔다. Global L1은
LR8 weak-signal row를 분리하기 위해 LR4-only accepted follow-up을 현재 strict 후보로
둔다. 따라서 새 플랫폼(A100/V100/H100)에서는 strict power API audit뿐 아니라 해당
GPU에서 새로 수집한 NCU sidecar와 같은 counter-schema/coordinate-alignment 검증까지
갖춰야 한다.

| Component/path | 대표 treatment-control pair | median | unit | bootstrap median 95% CI | confidence | 상태 |
|---|---|---:|---|---:|---|---|
| Tensor MMA incremental, RF-dependent | `reg_mma - reg_operand_only` | RF16 0.077, RF8 0.143 | pJ/FLOP | RF-dependent range | medium-high | accepted candidate + fixed-ITER/RF8/RF16 duration auxiliary |
| Shared scalar path | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.152 | pJ/bit | 0.114-0.204 | medium | accepted with caution, targeted Shared rerun |
| Shared scalar path LR4 paired auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.236 | pJ/bit | 0.212-0.297 | medium | LR4 paired 30초 auxiliary, clean high-side evidence |
| Shared scalar path LR8 paired combined auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.177 | pJ/bit | 0.150-0.181 | medium-high | LR8 paired 30초 combined auxiliary, reproduced middle evidence close to primary |
| Shared scalar path LR4 auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.216 | pJ/bit | 0.190-0.235 | medium-high | LR4 30초 auxiliary, method sensitivity |
| Shared scalar path LR16 paired combined auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.064 | pJ/bit | 0.0457-0.104 | medium | LR16 paired 30초 combined auxiliary, lower-side/method sensitivity |
| Shared scalar path LR16 paired 60초 auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.077 | pJ/bit | 0.0420-0.106 | low | LR16 60초 follow-up, lower-side persists but accepted_low_stability only |
| Shared scalar path LR4/LR8/LR16 interleaved auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.145 | pJ/bit | 0.0769-0.188 | medium | interleaved 30초 aggregate, accepted, factor split LR4 0.199/LR8 0.145/LR16 0.0618 |
| Shared scalar path LR4/LR8/LR16 fixed-ITER auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.140 | pJ/bit | 0.0937-0.193 | medium | fixed treatment ITER=17,000,000, bytes 1x/2x/4x, accepted_with_caution |
| Shared scalar path LR16 fixed-ITER focus auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.117 | pJ/bit | 0.109-0.122 | medium | LR16 focus 6/6 valid, accepted, prior weak row not persistent |
| Shared scalar path LR4/LR8 fixed-ITER focus auxiliary | `shared_scalar_load_only - clocked_empty`, W_SM=64 KiB | 0.149 | pJ/bit | 0.124-0.179 | medium-high | LR4/LR8 focus 10/10 valid, accepted, primary 0.152 pJ/bit 지지 |
| Global L1 hit path | `global_l1_load_only - clocked_empty`, W_SM=16 KiB | 0.148 | pJ/bit | 0.143-0.170 | medium-high | accepted, C-T-C paired 30초 combined primary |
| Global L1 hit path duration-scaling auxiliary | `global_l1_load_only - clocked_empty`, W_SM=16 KiB | 0.156 | pJ/bit | 0.130-0.185 | medium-high | slope/duration support, invalid detail 1개 |
| Global L1 hit path 60초 auxiliary | `global_l1_load_only - clocked_empty`, W_SM=16 KiB | 0.119 | pJ/bit | 0.109-0.122 | medium | auxiliary, power-state reject 1개를 pairing 전 제외, primary 대체 아님 |
| Global L1 hit path LR8 paired auxiliary | `global_l1_load_only - clocked_empty`, W_SM=16 KiB | 0.109 | pJ/bit | 0.0879-0.129 | medium | LR8 C-T-C auxiliary, 6/6 valid, method-sensitivity evidence |
| L2 CG hit path | `l2_cg_load_only - clocked_empty`, W_SM=64 KiB | 1.017 | pJ/bit | 0.947-1.071 | medium-high | accepted, C-T-C paired LR4/LR8 30초 combined primary |
| L2 CG hit path targeted mixed-LR auxiliary | `l2_cg_load_only - clocked_empty`, W_SM=64 KiB | 0.978 | pJ/bit | 0.935-1.139 | medium-high | auxiliary, targeted L2 stability rerun, temperature caution metadata |
| L2 CG hit path LR4 paired auxiliary | `l2_cg_load_only - clocked_empty`, W_SM=64 KiB | 1.027 | pJ/bit | 0.984-1.129 | medium | C-T-C paired 30초 auxiliary, clean support |
| L2 CG hit path LR8 paired auxiliary | `l2_cg_load_only - clocked_empty`, W_SM=64 KiB | 0.960 | pJ/bit | 0.898-1.100 | medium | C-T-C paired 30초 auxiliary, clean support |
| L2 CG hit path LR4 non-paired auxiliary | `l2_cg_load_only - clocked_empty`, W_SM=64 KiB | 1.298 | pJ/bit | 1.123-1.338 | medium-high | LR4 30초 auxiliary, drift/order-sensitive high-side evidence |
| DRAM CG streaming path | `dram_cg_load_only - clocked_empty`, W_SM=8192 KiB | 3.542 | pJ/bit | 2.964-4.454 | medium-high | sanity candidate only |

![Final component coefficients](../assets/component_energy_method/final_component_coefficients.svg)

이 결과로 말할 수 있는 것은 “해당 RTX 3090 microbenchmark 조건에서 L1/shared < L2 < DRAM sanity 순서의 effective coefficient가 관찰되었다”는 것이다. 이 값을 모든 GPU 또는 모든 workload에 일반화하면 안 된다.

Tensor는 추가로 RF=8/16 targeted stability rerun을 수행했다. Broad RF=1,2,4,8,16
factor exact-NCU sweep은 median 0.170 pJ/FLOP였지만 confidence가 low였다. RF=8/16만
20초, 6회 반복으로 다시 측정한 결과는 24/24 power API final, 24/24 power-state ok,
12/12 matched-control valid였고 median은 0.107 pJ/FLOP였다. Fixed `ITER=8000000`
보조실험도 수행했고, 20/20 power API final, 20/20 power-state ok,
10/10 matched-control valid였으며 median은 0.146 pJ/FLOP였다.

추가 RF=8 duration-scaling follow-up은 10/20/30초 duration sweep으로 실행했다.
30/30 row가 Power API final candidate였고, matched-control 15/15 row가 valid였으며
median은 0.143 pJ/FLOP였다. Slope 기반 추정도 0.144-0.156 pJ/FLOP에 모였다.
따라서 RF=8 조건의 상단값은 fixed-ITER auxiliary와 정합하지만, RF=16을 섞으면
combined median이 낮아지는 현상이 남아 있다. 이 때문에 Tensor는 여전히 단일
silicon-level 상수가 아니라 workload-dependent range로 보고한다.

추가 RF=16 duration-scaling follow-up도 10/20/30초 duration sweep으로 실행했다.
30/30 row가 Power API final candidate였고, power-state audit도 30/30 ok였으며,
matched-control 15/15 row가 valid였다. Median은 0.077 pJ/FLOP이고 slope 기반
추정은 0.053-0.071 pJ/FLOP였다. 따라서 Tensor는 기존 단일 range보다 더 명확하게
**RF16 lower 약 0.06-0.09 pJ/FLOP, RF8 upper 약 0.14-0.15 pJ/FLOP**로
분리해 보고한다.

Shared/L1은 추가로 targeted stability rerun을 수행했다. Shared scalar path는
20초, 10회 반복에서도 0.152 pJ/bit로 기존 0.151 pJ/bit와 정합했고, valid row가
6/9에서 29/30으로 늘어 current primary가 되었다. 이후 Shared-only duration-scaling
check에서는 15/15 row가 valid였고 ratio median은 0.198 pJ/bit였지만, intercept를
허용한 slope는 0.10-0.12 pJ/bit로 낮았다. 따라서 Shared는 `0.15-0.24 pJ/bit`
수준의 method-sensitive effective coefficient와 LR16 low-side caution으로 표현한다. 추가로 Shared LR=4,
LR=8, LR=16을 각각 control-treatment-control paired 30초로 측정했다. LR4 paired는
6/6 valid, median 0.236 pJ/bit, reliability accepted였다. LR8 paired는 같은 조건을
한 번 더 반복해 combined로 재분석했고 12/12 valid, median 0.177 pJ/bit,
confidence medium-high, reliability accepted였다. LR16 paired는 같은 조건을 한 번 더
반복해 combined로 재분석했고, 11/12 valid, median 0.064 pJ/bit, confidence medium,
reliability accepted_with_caution이었다. Rerun2 단독도 0.086 pJ/bit, 6/6 valid,
reliability accepted였으므로 LR16 low-side는 재현된 것으로 본다. 이는 paired sequence
자체가 값을 낮춘 것이 아니라 LR/control 정책에 따른 high/mid/low method sensitivity가
있음을 보여준다. 같은 LR16 paired 조건을 60초로 늘린 follow-up도 Power API
18/18 final, power-state 18/18 ok였고 median 0.077 pJ/bit를 보였다. 다만
matched-control 5/6 valid, confidence low, reliability accepted_low_stability였으므로
이 값은 lower-bound/method-sensitivity evidence로만 둔다. 이후 LR4/LR8/LR16을
같은 rotated run 안에서 교차 실행한 interleaved 30초 follow-up은 Power API
36/36 final, power-state 36/36 ok, matched-control 12/12 valid, reliability
accepted였고 aggregate median 0.145 pJ/bit를 보였다. Factor별 median은 LR4
0.199 pJ/bit, LR8 0.145 pJ/bit, LR16 0.0618 pJ/bit였다. 따라서 current primary
0.152 pJ/bit는 유지하되, LR split은 별도 실행 시점만의 artefact가 아니라
microbenchmark policy sensitivity로 해석한다.
Fixed-ITER follow-up에서는 treatment ITER를 17,000,000으로 고정해 LR4/LR8/LR16
shared bytes를 약 1x/2x/4x로 벌렸다. 이 run은 Power API 27/27 final,
matched-control 8/9 valid, reliability accepted_with_caution였고 aggregate median
0.140 pJ/bit를 보였다. 따라서 Shared primary 0.152 pJ/bit는 유지하되,
duration-calibrated 구조가 LR split 일부를 키웠다는 점과 LR16 weak-signal caution을
함께 적는다. 이어 LR16만 fixed-ITER로 6 cycles 반복한 focus rerun은 Power API
18/18 final, power-state 18/18 ok, matched-control 6/6 valid, reliability
accepted였고 median 0.117 pJ/bit를 보였다. 따라서 직전 LR16 weak row는 지속적
path failure가 아니라 row-level weak signal로 재분류한다.
LR4/LR8만 fixed-ITER로 5 cycles 반복한 focus rerun은 Power API 30/30 final,
power-state 30/30 ok, matched-control 10/10 valid, reliability accepted였고
aggregate median 0.149 pJ/bit를 보였다. LR4/LR8 split은 0.179/0.142 pJ/bit로
남았지만, primary 0.152 pJ/bit를 직접 지지한다.
Global L1은 targeted median이
0.105 pJ/bit였지만 LR=16에서 negative matched-control row가 4개 남아, 이 sweep은
caution evidence로 둔다. Targeted Global L1 invalid row 중 2개는 power-state audit에서
평균 전력 저하 outlier로 확인되었고, 나머지는 weak signal로 보는 것이 맞다.
추가 duration-scaling check에서는 `load_repeat=4`를 고정하고 10초, 20초, 30초를
비교했으며, median 0.156 pJ/bit, OLS slope 0.147 pJ/bit, Theil-Sen slope
0.149 pJ/bit로 기존 L1 0.150 pJ/bit와 정합했다. 같은 `load_repeat=4` 조건을
30초, 10회 반복으로 다시 실행한 stability rerun도 20/20 Power API final,
20/20 power-state ok였고 median 0.153 pJ/bit를 보였다. 다만 10개 matched row 중
1개가 weak-signal negative row였으므로 duration-scaling은 slope/duration support로
남긴다. 이후 같은 좌표를 60초, 8회 반복으로 늘린 auxiliary check는 Power API
16/16 final이었지만 treatment row 1개가 power-state reject였고, 이를 pairing 전에
제외한 filtered matched-control median은 0.119 pJ/bit로 낮아졌다. 따라서 60초
결과는 primary 대체가 아니라 control/treatment 순서와 thermal/power drift 민감도
evidence로 둔다. 이를 보완하기 위해 추가한 control-treatment-control paired 30초
run 2회를 결합한 결과는 Power API 36/36 final, power-state 36/36 ok,
matched-control 12/12 valid, median 0.148 pJ/bit였다. 이 결과는 L1 primary
range를 지지하며 모든 gate가 깨끗하므로 current Global L1 primary로 승격한다.
drift-sensitive path에는 paired runner가 더 적합하다는 설계 개선점도 확인한다.
그 뒤 같은 paired 구조에서 `load_repeat=8`을 따로 측정한 결과는 Power API
18/18 final, power-state 18/18 ok, matched-control 6/6 valid였고 median은
0.109 pJ/bit였다. 이 값은 LR4 paired 0.148 pJ/bit보다 낮고 60초 auxiliary
0.119 pJ/bit와 가까우므로, Global L1은 `0.15 pJ/bit` 단일 상수보다
`0.11-0.16 pJ/bit` 정도의 method-sensitive effective range로 보고하는 것이
더 정직하다.

L2는 먼저 targeted stability rerun을 수행했다. 기존 broad factor exact-NCU
L2 median은 1.138 pJ/bit였고 NCU path는 accepted였지만, broad power-state audit에
small-group caution이 남아 있었다. L2만 `W_SM=64 KiB`, `blocks/SM=16`,
`load_repeat=4/8/16`, 20초, 10회 반복으로 다시 측정한 결과 60/60 power API
final, matched-control 30/30 valid, reliability `accepted`였고 median은
0.978 pJ/bit였다. 새 CI 0.935-1.139 pJ/bit가 기존 1.138 pJ/bit와 겹쳐 방향성은
유지됐지만, power-state audit의 control temperature caution 1개가 추적 metadata로
남았다. 그래서 이 targeted mixed-LR 결과는 primary가 아니라 auxiliary support로
낮춰 둔다.

이후 Shared와 L2에 대해 `load_repeat=4`, 30초, 10회 반복의 단일조건 stability
rerun을 추가했다. Power API는 30/30 final candidate였고, Shared LR4 median은
0.216 pJ/bit, non-paired L2 LR4 median은 1.298 pJ/bit였다. 다만 L2에는
power-state reject/negative row가 1개 있었으므로, 같은 LR4 조건을
control-treatment-control paired 30초로 다시 측정했다. 이 paired run은 Power API
18/18 final, power-state 18/18 ok, matched-control 6/6 valid였고 median은
1.027 pJ/bit였다. 같은 paired 구조의 LR8 follow-up도
Power API 18/18 final, power-state 18/18 ok, matched-control 6/6 valid였고 median은
0.960 pJ/bit였다. NCU sidecar는 L1 hit 0.000003%, L2 hit 99.9368%, L2 bytes
1.07618e12 B, DRAM bytes 1.26191e9 B로 L2-hit dominated path를 확인했다.
기존 non-paired LR4 1.298 pJ/bit는 drift/order-sensitive high-side evidence로
낮춰 해석한다. 최종 current L2 primary는 temperature caution이 없는 LR4/LR8 paired
raw를 결합한 C-T-C paired combined 결과다. 이 결합 분석은 Power API 36/36 final,
power-state 36/36 ok, matched-control 12/12 valid였고 median은 1.017 pJ/bit,
CI는 0.947-1.071 pJ/bit였다.

## 3. 현재 산출값을 만드는 입력

현재 수치 산출에 직접 사용하는 primary artifact는 finalplan energy run, matched-control 분석, NCU acceptance 결과다.

| 역할 | 파일 |
|---|---|
| 최종 strict 결과 보고서 | `results/summary/rtx3090_finalplan_stability_strict_report_20260708_ko.md` |
| factor exact-NCU 결과 보고서 | `results/summary/rtx3090_finalplan_stability_factor_exactncu_report_20260708_ko.md` |
| Tensor targeted stability follow-up | `results/summary/rtx3090_tensor_targeted_rf8_rf16_report_20260708_ko.md` |
| Tensor fixed-ITER auxiliary follow-up | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_report_20260708_ko.md` |
| Tensor RF8 duration-scaling follow-up | `results/summary/rtx3090_tensor_rf8_duration_scaling_report_20260708_ko.md` |
| Tensor RF16 duration-scaling follow-up | `results/summary/rtx3090_tensor_rf16_duration_scaling_report_20260708_ko.md` |
| Shared/L1 targeted stability follow-up | `results/summary/rtx3090_targeted_shared_l1_stability_report_20260708_ko.md` |
| Shared duration-scaling check | `results/summary/rtx3090_shared_duration_scaling_report_20260708_ko.md` |
| Shared LR4 paired 30초 auxiliary check | `results/summary/rtx3090_shared_paired_lr4_30s_stability_report_20260708_ko.md` |
| Shared LR8 paired 30초 combined auxiliary check | `results/summary/rtx3090_shared_paired_lr8_30s_combined_report_20260708_ko.md` |
| Shared LR16 paired 30초 combined auxiliary check | `results/summary/rtx3090_shared_paired_lr16_30s_combined_report_20260708_ko.md` |
| Shared LR16 paired 60초 low-stability auxiliary check | `results/summary/rtx3090_shared_paired_lr16_60s_stability_report_20260708_ko.md` |
| Shared LR4/LR8/LR16 interleaved 30초 auxiliary check | `results/summary/rtx3090_shared_interleaved_lr4_lr8_lr16_30s_report_20260708_ko.md` |
| Shared LR4/LR8/LR16 fixed-ITER auxiliary check | `results/summary/rtx3090_shared_fixediter_lr4_lr8_lr16_report_20260708_ko.md` |
| Shared LR16 fixed-ITER focus check | `results/summary/rtx3090_shared_fixediter_lr16_focus_report_20260708_ko.md` |
| Shared LR4/LR8 fixed-ITER focus check | `results/summary/rtx3090_shared_fixediter_lr4_lr8_focus_report_20260708_ko.md` |
| L1 duration-scaling check | `results/summary/rtx3090_l1_duration_scaling_report_20260708_ko.md` |
| L1 30초 stability check | `results/summary/rtx3090_l1_30s_stability_report_20260708_ko.md` |
| L1 60초 stability auxiliary check | `results/summary/rtx3090_l1_60s_stability_report_20260708_ko.md` |
| L1 paired 30초 combined primary check | `results/summary/rtx3090_l1_paired_30s_combined_report_20260708_ko.md` |
| L1 LR8 paired 30초 auxiliary check | `results/summary/rtx3090_l1_paired_lr8_30s_stability_report_20260708_ko.md` |
| Shared/L2 LR4 30초 stability check | `results/summary/rtx3090_shared_l2_30s_stability_report_20260708_ko.md` |
| L2 LR4/LR8 paired 30초 combined primary check | `results/summary/rtx3090_l2_paired_lr4_lr8_30s_combined_report_20260708_ko.md` |
| L2 targeted stability follow-up | `results/summary/rtx3090_targeted_l2_stability_report_20260708_ko.md` |
| L2 LR4 paired 30초 auxiliary check | `results/summary/rtx3090_l2_paired_lr4_30s_stability_report_20260708_ko.md` |
| L2 LR8 paired 30초 auxiliary check | `results/summary/rtx3090_l2_paired_lr8_30s_stability_report_20260708_ko.md` |
| memory matched-control summary | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_summary_20260708.csv` |
| memory matched-control detail | `results/summary/rtx3090_finalplan_stability_factor_exactncu_matched_control_detail_20260708.csv` |
| Tensor targeted matched-control summary | `results/summary/rtx3090_tensor_targeted_rf8_rf16_matched_control_summary_20260708.csv` |
| Tensor targeted matched-control detail | `results/summary/rtx3090_tensor_targeted_rf8_rf16_matched_control_detail_20260708.csv` |
| Tensor fixed-ITER matched-control summary | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_matched_control_summary_20260708.csv` |
| Tensor fixed-ITER matched-control detail | `results/summary/rtx3090_tensor_fixed_iter_rf8_rf16_matched_control_detail_20260708.csv` |
| Tensor RF8 duration-scaling matched-control summary | `results/summary/rtx3090_tensor_rf8_duration_scaling_matched_control_summary_20260708.csv` |
| Tensor RF8 duration-scaling matched-control detail | `results/summary/rtx3090_tensor_rf8_duration_scaling_matched_control_detail_20260708.csv` |
| Tensor RF16 duration-scaling matched-control summary | `results/summary/rtx3090_tensor_rf16_duration_scaling_matched_control_summary_20260708.csv` |
| Tensor RF16 duration-scaling matched-control detail | `results/summary/rtx3090_tensor_rf16_duration_scaling_matched_control_detail_20260708.csv` |
| current reporting coefficient CSV | `results/summary/rtx3090_current_reporting_component_coefficients_20260708.csv` |
| current reporting evidence matrix | `results/summary/rtx3090_current_reporting_evidence_matrix_20260708.md` |
| current primary selection audit | `results/summary/rtx3090_current_primary_selection_audit_20260708_ko.md` |
| NCU acceptance table | `results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv` |
| 결과 SVG 생성 | `scripts/plot_component_method_visuals.py` |

초기 `20260701/20260702` raw sweep 결과는 현재 final coefficient를 직접 계산하는 입력이 아니다. 해당 파일들은 후보 영역 탐색과 실험 히스토리 용도로 `archive/legacy_20260707/results/`에 보관한다.

## 4. 실험 구조

실험 흐름은 아래 순서다.

```text
실험 조건 선택
→ treatment/control kernel 실행
→ NVML board-level energy 측정
→ energy_source / integration method / power semantics gate 확인
→ control energy를 elapsed 기준으로 보정해 차분
→ Tensor는 FLOP, memory는 NCU actual bytes로 정규화
→ pJ/FLOP 또는 pJ/bit 계산
→ NCU hit rate, traffic, stall, HMMA, spill 기준으로 채택/제외
```

차분 계산의 의미는 다음과 같다.

```text
delta_E_J = E_treatment_J - (E_control_J / t_control_s) * t_treatment_s
coefficient = delta_E_J / denominator
```

분자는 control 대비 추가 board-level energy다. 현재 RTX 3090 finalplan 재분석은 `nvml_total_energy`, `total_energy_mj_delta`, `nvml_total_energy_supported=true` row만 사용했다. RTX 3090의 `GetPowerUsage` 의미는 `one_sec_average`지만, 최종 분자는 endpoint power fallback이 아니라 total energy mJ counter 차분이다. 분모는 Tensor에서는 FLOP이고, shared/L1/L2/DRAM에서는 NCU로 보정한 actual bytes 또는 bits다.

## 5. Finalplan Sweep 조건

현재 final coefficient를 얻기 위한 sweep은 아래 조건이다.

| Component | treatment | control | W_SM (KiB) | blocks/SM | active_SM (SM) | sweep parameter | sweep values | seconds (s) | repeats |
|---|---|---|---:|---:|---:|---|---|---:|---:|
| Tensor MMA incremental | `reg_mma` | `reg_operand_only` | 2048 | 16 | 82 | reuse factor | 1, 2, 4, 8, 16 | 5 | 3 |
| Shared scalar path | `shared_scalar_load_only` | `clocked_empty` | 64 | 16 | 82 | load_repeat | 1, 2, 4, 8, 16 | 5 | 3 |
| Global L1 hit path | `global_l1_load_only` | `clocked_empty` | 16, 64 | 16 | 82 | load_repeat | 1, 2, 4, 8, 16 | 5 | 3 |
| L2 CG hit path | `l2_cg_load_only` | `clocked_empty` | 64 | 16 | 82 | load_repeat | 1, 2, 4, 8, 16 | 5 | 3 |
| DRAM CG streaming path | `dram_cg_load_only` | `clocked_empty` | 8192 | 16 | 82 | load_repeat | 1, 4, 16 | 5 | 3 |

![Finalplan sweep conditions](../assets/component_energy_method/finalplan_sweep_design_matrix.svg)

## 6. NCU 검증 기준

NCU는 energy를 직접 측정하지 않는다. NCU의 역할은 treatment kernel이 의도한 path를 실제로 사용했는지 확인하고, memory coefficient의 denominator로 사용할 traffic byte를 제공하는 것이다.

| Path | 주요 확인 항목 | 채택 기준의 의미 |
|---|---|---|
| Tensor | HMMA instruction, spill/local memory | Tensor Core가 실행되고 register spill이 없는지 확인 |
| Shared scalar | shared bytes, bank conflict | shared path traffic이 지배적이고 conflict 오염이 낮은지 확인 |
| Global L1 | L1 hit rate, L1 bytes, L2/DRAM leakage | global load가 L1에서 주로 끝나는지 확인 |
| L2 CG | L1 hit rate near 0, L2 hit rate high | L1을 우회하고 L2 hit path가 지배적인지 확인 |
| DRAM CG | DRAM bytes, L2 hit rate low | streaming traffic이 DRAM까지 내려가는지 확인 |

![NCU hit-rate validation](../assets/component_energy_method/ncu_hit_rate_validation.svg)

![NCU traffic validation](../assets/component_energy_method/ncu_path_validation_bytes.svg)

2026-07-08에 RTX 3090 stability factor set을 직접 포함하는 NCU sidecar를 추가 실행했다.
따라서 현재 대표 결과의 memory path는 `ncu_actual_exact` denominator를 사용한다.

| Path | broad strict median | factor exact-NCU median | 해석 |
|---|---:|---:|---|
| Tensor broad RF sweep | 0.170 pJ/FLOP | 0.169745 pJ/FLOP | 일치하지만 confidence low |
| Shared scalar | 0.151 pJ/bit | targeted 0.152 pJ/bit, interleaved aggregate 0.145 pJ/bit, fixed-ITER aggregate 0.140 pJ/bit, LR16 fixed-ITER focus 0.117 pJ/bit, LR4/LR8 fixed-ITER focus 0.149 pJ/bit, LR4 paired auxiliary 0.236 pJ/bit, LR8 paired combined auxiliary 0.177 pJ/bit, LR4 auxiliary 0.216 pJ/bit, LR16 paired combined auxiliary 0.064 pJ/bit, LR16 60초 auxiliary 0.077 pJ/bit | targeted rerun으로 current primary 갱신, interleaved/fixed-ITER run으로 LR별 method sensitivity 확인 |
| Global L1 | 0.150 pJ/bit | paired 30초 combined primary 0.148 pJ/bit, duration-scaling auxiliary 0.156 pJ/bit, LR8 paired 0.109 pJ/bit, 60초 auxiliary 0.119 pJ/bit | clean paired run을 current primary로 두고 Global L1을 0.11-0.16 pJ/bit method-sensitive range로 병기 |
| L2 CG | 1.138 pJ/bit | paired LR4/LR8 combined primary 1.017 pJ/bit, targeted auxiliary 0.978 pJ/bit, LR8 paired auxiliary 0.960 pJ/bit, LR4 paired auxiliary 1.027 pJ/bit, LR4 non-paired auxiliary 1.298 pJ/bit | temperature caution 없는 paired combined를 current primary로 두고 targeted/LR8/LR4를 support로 병기. non-paired LR4는 high-side drift/order sensitivity evidence |
| DRAM CG | 3.542 pJ/bit | 3.54070 pJ/bit | 일치 |

백서에서는 RTX 3090 memory 대표값으로 power-state와 paired-control gate가 가장 깨끗한 follow-up을 우선 사용한다.
Shared는 targeted rerun의 0.152 pJ/bit, Global L1은 paired 30초 combined의
0.148 pJ/bit, L2는 paired LR4/LR8 30초 combined의 1.017 pJ/bit를 current primary로 둔다.
다만 Global L1 duration-scaling auxiliary 0.156 pJ/bit, LR8 paired auxiliary 0.109 pJ/bit, 60초 auxiliary 0.119 pJ/bit,
Shared LR4 paired auxiliary 0.236 pJ/bit, Shared LR8 paired combined auxiliary 0.177 pJ/bit,
Shared LR4 auxiliary 0.216 pJ/bit, Shared LR16 paired combined auxiliary 0.064 pJ/bit,
Shared LR16 paired 60초 auxiliary 0.077 pJ/bit, Shared interleaved aggregate
0.145 pJ/bit와 factor split LR4 0.199/LR8 0.145/LR16 0.0618 pJ/bit,
Shared fixed-ITER aggregate 0.140 pJ/bit와 factor split LR4 0.154/LR8
0.193/LR16 0.119 pJ/bit, LR16 fixed-ITER focus 0.117 pJ/bit,
LR4/LR8 fixed-ITER focus aggregate 0.149 pJ/bit와 factor split LR4 0.179/LR8 0.142 pJ/bit,
L2 targeted mixed-LR auxiliary 0.978 pJ/bit, L2 LR8 paired auxiliary 0.960 pJ/bit, L2 LR4 paired auxiliary 1.027 pJ/bit,
L2 LR4 non-paired auxiliary 1.298 pJ/bit를 함께 제시해 drift/LR/method sensitivity를
숨기지 않는다.
Tensor는 targeted RF=8/16 follow-up의 0.107 pJ/FLOP를 lower-side candidate로 두고,
fixed-ITER auxiliary의 0.146 pJ/FLOP, RF=8 duration-scaling의 0.143 pJ/FLOP,
RF=16 duration-scaling의 0.077 pJ/FLOP를 함께 보고한다. 따라서 Tensor는 RF-dependent
effective coefficient로 표현한다. 하나의 넓은 범위가 필요하면 0.06-0.15 pJ/FLOP로
쓰되, RF 조건을 반드시 함께 적는다. 단 모든 값은
순수 silicon-level energy가 아니라 board-level effective microbenchmark
coefficient라는 해석 제한을 유지한다.

## 7. 해석상 주의

| 항목 | 안전한 해석 | 금지해야 할 해석 |
|---|---|---|
| Tensor RF16 0.077, RF8 0.143 pJ/FLOP | no-MMA control 대비 FP16 WMMA incremental board-level coefficient의 RF-dependent range. 넓게는 0.06-0.15 pJ/FLOP | Tensor Core transistor-level energy |
| Shared scalar 0.152 pJ/bit | shared scalar instruction path의 effective coefficient | shared memory array 단독 energy |
| Global L1 paired combined 0.148 pJ/bit, duration-scaling 0.156 pJ/bit, 60초 auxiliary 0.119 pJ/bit | NCU상 L1 hit가 확인된 global-load path coefficient와 drift sensitivity | L1 SRAM bitcell energy |
| L2 CG paired combined 1.017 pJ/bit, targeted 0.978 pJ/bit, paired LR8 0.960 pJ/bit, paired LR4 1.027 pJ/bit, non-paired LR4 1.298 pJ/bit | L1 bypass + L2 hit path coefficient와 control-order sensitivity | L2 SRAM array 단독 energy |
| DRAM CG 3.542 pJ/bit | RTX 3090 GDDR6X streaming sanity coefficient | physical DRAM/HBM device energy |

L2와 DRAM 값에는 memory controller, interconnect, scoreboard stall, issue/control overhead가 섞일 수 있다. 특히 DRAM 값은 HBM2 physical access energy 문헌값과 같은 레벨이 아니다.

## 8. Active와 Archive 경계

현재 active 문서와 코드는 finalplan 실험을 기준으로 유지한다.

| 구분 | active | archive |
|---|---|---|
| 문서 | `docs/methodology/howitworks.md`, `docs/results/gpu_power_modeling_experiment_results_ko.md`, `docs/methodology/component_energy_final_experiment_plan_ko.md` | 초기 decomposition/regression/register-pressure 설계 문서 |
| 코드 | `scripts/plan_platform_component_experiment.py`, `scripts/run_component_regression_sweep.py`, `scripts/analyze_ncu_path_acceptance.py`, `scripts/analyze_matched_control_energy.py` | 초기 component pair, old regression, register-footprint runner/analyzer |
| 결과 | finalplan summary/NCU acceptance 결과 | 20260701/20260702 raw sweep, smoke, fixed-W sweep, old NCU validation |
| CUDA 구현 | `include/`, `src/` | 없음. 현재 mode 구현이 active surface |

## 9. 백서에서 필요한 문장

```text
GPU component energy breakdown is estimated from board-level power measurements,
differential CUDA microbenchmarks, and NCU counter validation. The resulting
coefficients represent workload-dependent effective board-level energy, not direct
transistor-level measurements.
```

```text
The archived raw sweeps were used to explore feasible occupancy and working-set
regions. They are not the direct source of the final component coefficients.
```

## 10. 다음 실험 개선

| 우선순위 | 개선 항목 | 이유 |
|---:|---|---|
| 1 | A100/V100/H100에서 같은 factor exact-NCU 절차 실행 | RTX 3090에서는 대표 LR=4 row 한계를 제거했으므로 다른 플랫폼으로 확장 |
| 2 | A100/V100/H100에서 architecture profile별 W_SM 재선정 | L1/shared, L2, HBM, Tensor 구조가 다름 |
| 3 | clock, temperature, power limit, ECC 상태 기록 강화 | board-level coefficient 분산 축소 |
| 4 | L2/DRAM stall-heavy 조건 별도 보고 | pJ/bit에 stall/control 성분이 섞이는 정도 명시 |
| 5 | register file 단독 coefficient는 별도 연구로 분리 | 현재 control proxy만으로 pure RF 분리는 어려움 |
