# A100 Tensor/L2 Targeted Remediation Plan

작성일: 2026-07-10, updated 2026-07-13

## 목적

이 package는 기존 A100 실행에서 확인된 두 실패만 다시 검증한다.

1. Tensor RF4/8/16의 `delta_E < 10 J` 또는 음수 문제
2. `l2_cg_load_only`의 path-specific L2 read hit가 기준에 미달하는 문제

전체 Shared/L1/DRAM package를 대체하지 않는다. 이 실행이 통과하면 수정된 Tensor와 L2
경로를 full A100 package에 합칠 수 있다는 뜻이며, full component summary는 이후 표준
package로 다시 생성해야 한다.

## 2026-07-13 A100 관측과 판정

| 항목 | 관측 | 판정 | 다음 검증 |
|---|---|---|---|
| Tensor dual calibration v1 | RF1-16 모두 양수, 약 0.35-0.54 pJ/FLOP | **stale/reject**. 음수 차분 문제는 해소됐지만 dynamic RF loop가 교정된 `fixed_rf_v2` marker 이전 결과여서 final로 승격하거나 새 결과와 결합하지 않음 | fixed-RF v2 clean rebuild 후 RF별 `HMMA/logical MMA` 상대 spread <=10%, control HMMA=0, spill/local=0, RF coefficient 상대 range <=75% |
| L2 normal `.cg` | W_SM 16/32/64/128 KiB에서 path-specific L2 read hit 약 58.5-60.1% | **strict reject**. 95% 기준을 충족하지 않으므로 pJ/bit를 보고하지 않음 | NCU application replay + 동일 CG warm-up으로 재검사하고, 실패할 때만 persisting-L2 policy 진단 |

Tensor coefficient는 board-level treatment-control 증분이다. 논리 FLOP 수는 WMMA
`m16n16k16=8192 FLOP`로 계산하지만, 하나의 logical WMMA가 몇 개의 HMMA 계열 SASS로
lowering되는지는 GPU 아키텍처에 따라 다를 수 있다. 따라서 절대 HMMA 수를 RTX 3090과
같게 요구하지 않고, A100 내부에서 RF가 증가할 때 `HMMA/logical MMA`가 일정한지를 먼저
검증한다.

## 핵심 수정

| 문제 | 수정된 실험 조건 | 판정 증거 |
|---|---|---|
| Tensor control의 RF 비례 추가 연산 | 두 kernel에 동일한 dependent integer add와 동일 scalar-store epilogue만 유지; control의 FP32 FMA/checksum/memory 제거 | raw revision marker, control HMMA=0, treatment HMMA>0, spill=0 |
| dynamic reuse loop의 architecture-specific HMMA over-issue | 정확했던 RF1은 dynamic treatment/control을 유지하고 RF2/4/8/16은 compile-time fixed-trip `unroll 1` kernel로 dispatch. 임의 RF는 dynamic fallback | revision `matched_add_scalar_epilogue_fixed_rf_v2`; 각 RF `HMMA/logical MMA` 비율 일정, 상대 spread<=10% |
| Tensor mode별 ITER 불일치와 짧은 control | RF별 `reg_mma` 20 s calibration과 `reg_operand_only` 2 s 최소 calibration을 수행하고, 두 ITER 중 큰 값을 두 mode에 동일 적용 | calibration manifest의 두 candidate ITER와 max policy, raw ITER, matched-detail `iter_ratio=1` |
| pair가 반복 경계에서 분리될 가능성 | command 한 개가 아니라 control-treatment 2개를 원자적 pair로 회전 | runner matrix와 matched-detail `pair_start_distance_ms<=60000`; 20초 idle baseline과 kernel 실행을 포함한 completion timestamp 차이 |
| `.cg`의 L1 request를 L1 hit로 오인 | global-load lookup hit/miss와 L2 read hit/miss를 path-specific으로 사용 | L1 path hit <=1%, L1 hit/request <=1%, L2 read hit >=95% |
| L2 58.5-60.1%를 단일 derived ratio로만 판정 | native op-read hit ratio, lookup hit/miss-derived ratio, total read sector, DRAM read bytes, persisting window 크기를 함께 수집 | derived/native hit 모두 >=95%, 차이 <=2 percentage points, `(hit+miss)/read sectors=1+/-2%`; miss bytes와 DRAM read bytes는 원인 진단에 기록 |
| normal warm-up의 L1 오염 | CG treatment의 warm-up도 `ld.global.cg` 사용 | raw `global_warmup_policy=ld_global_cg` marker |
| NCU kernel replay에서 warm-up cache 상태가 pass마다 재현되지 않음 | `--replay-mode application --cache-control none`으로 각 metric pass마다 application setup과 CG warm-up을 다시 실행 | case manifest의 replay/cache policy와 path-specific hit counter |
| A100 normal L2 residency가 95%에 미달 | W16/W128, LR4를 먼저 normal policy로 진단하고, 실패할 때만 CUDA persisting-L2 access-policy window로 같은 좌표를 재검사 | `l2_policy_selection.{csv,md,env}`; normal 우선, 둘 다 실패하면 긴 sweep 전에 중단 |
| full NCU reject를 energy 후에 발견 | 선택 policy로 Tensor 10 cases와 L2 40 cases를 energy 전에 실행하고 전용 precheck를 hard gate로 사용 | `*_ncu_precheck.{csv,md}`가 pass해야 20 s x 7 repeats energy 시작 |
| 단일 L2 좌표의 우연한 통과 | W16/32/64/128을 모두 검증하고 인접한 두 W의 pJ/bit plateau 요구 | NCU+energy 통과 W 두 개 이상, 상대 차이 <=35% |

## Parameter Sweep

모든 단위와 명령 개수는 다음과 같다.

| 단계 | 고정 조건 | sweep | 1회당 좌표 | 반복/총 행 또는 case |
|---|---|---|---:|---:|
| L2 policy precheck | A100, 108 SM, blocks/SM=16, LR4, application replay, cache-control none, CG warm-up 4회 | normal W_SM 16/128 KiB; 실패 시 persisting에서 동일 W 재검사 | policy당 mode 2개 x W 2개 | normal 4 NCU cases, 필요 시 persisting 4 cases |
| Tensor NCU | W_SM=2048 KiB, blocks/SM=16, ITER=100,000, application replay | mode 2개 x RF 1,2,4,8,16 | 10 cases | 10 NCU cases |
| L2 NCU | blocks/SM=16, ITER=100,000, 선택된 residency policy, CG warm-up 4회 | mode 2개 x W_SM 16,32,64,128 KiB x LR 1,2,4,8,16 | 40 cases | 40 NCU cases |
| Tensor calibration | A100, 108 SM, W_SM=2048 KiB, blocks/SM=16 | RF별 treatment target 20 s + control floor 2 s | RF 5개 x calibration 2 modes | 10 calibration commands, raw energy 행 아님 |
| Tensor energy | A100, 108 SM, W_SM=2048 KiB, blocks/SM=16, pair-locked ITER | mode 2개 x RF 1,2,4,8,16 | 10 commands | 7 repeats, 70 raw rows |
| L2 energy | A100, 108 SM, blocks/SM=16, 20 s/mode | mode 2개 x W_SM 16,32,64,128 KiB x LR 4,8,16 | 24 commands | 7 repeats, 168 raw rows |
| schema/revision smoke | active SM=1, ITER=1 | `clocked_empty`, `reg_operand_only`, `l2_cg_load_only` | 3 commands | 3 raw rows |

`W_SM=2048 KiB`는 Tensor register 용량이 아니다. Tensor mode의 기존 CLI 좌표이며 실제
register footprint는 ptxas 및 NCU registers/thread와 spill counter로 판정한다.

## 실행

기본 실행은 `sm_80` binary를 clean rebuild한다.

```bash
NCU_USE_SUDO=1 bash results/summary/a100_tensor_l2_remediation_20260710_commands.sh
```

관리자가 일반 사용자 performance counter 권한을 허용했다면:

```bash
bash results/summary/a100_tensor_l2_remediation_20260710_commands.sh
```

다른 A100 SKU/MIG 환경에서 visible SM 수가 108이 아니면 preflight 결과에 맞춰 같은 값을
전체 실행에 적용한다.

```bash
ACTIVE_SM=<visible_SM_count> TAG=<run_tag> \
NCU_USE_SUDO=1 bash results/summary/a100_tensor_l2_remediation_20260710_commands.sh
```

## Acceptance

| Component | 필수 조건 |
|---|---|
| Tensor 각 RF | calibration candidate 2개와 max resolved ITER, raw mode별 7행, 동일 ITER, current marker, total-energy/device scope |
| Tensor NCU | `reg_mma` HMMA>0, `reg_operand_only` HMMA=0, 두 mode local read/write bytes=0 및 spill=0, acceptance pass; RF1-16의 `HMMA/logical MMA` 상대 spread<=10% |
| Tensor energy | 7개 pair 모두 `delta_E>=10 J`, coefficient>0, pair timestamp distance<=60,000 ms, median 0.01-5 pJ/FLOP; RF median 상대 range<=75%. 범위가 크면 단일 평균 대신 RF range로 보고 |
| L2 policy precheck | normal W16/W128가 모두 통과하면 normal 선택. 아니면 persisting W16/W128를 검사. 둘 다 실패하면 energy sweep 미실행 |
| Full NCU precheck | Tensor RF 5개와 L2 W x LR 20개 treatment/control이 모두 accepted이고 replay/cache/warm-up/policy metadata 일치. L2는 native/derived hit와 sector conservation까지 일치해야 하며 한 row라도 실패하면 energy sweep 미실행 |
| L2 각 W | application replay/cache-control none/선택 residency/CG warm-up 4회. LR1/2/4/8/16 treatment/control 모두 accepted; control input L1 request=0 및 DRAM/expected<=0.1%; treatment L1 path hit<=1%, L1 hit/request<=1%, derived/native L2 read hit>=95%, 두 값 차이<=2 percentage points, hit+miss/read sectors=1+/-2%, DRAM/L2<=2% |
| L2 energy | LR4/8/16별 최소 5 valid repeats, 모든 delta_E>=10 J, positive pJ/bit, exact NCU denominator |
| L2 plateau | 위 조건을 통과한 인접 W 두 개 이상의 median pJ/bit 상대 차이<=35% |

35%는 A100 회로 특성에서 유도한 상수가 아니라, 이 targeted run에서 working-set 변화에
대해 coefficient가 같은 order와 plateau를 보이는지 판정하기 위해 실행 전에 고정한
재현성 tolerance다. 이 기준을 넘으면 더 좋아 보이는 한 점을 선택하지 않고 재실행한다.

Tensor의 HMMA/logical-MMA 10% 기준은 RF scaling이 실제 instruction scaling으로 lowering되는지
검사하는 엄격한 선형성 gate다. 반면 coefficient RF 상대 range 75%는 board power와
frequency/throughput의 RF 의존성을 허용하는 넓은 stability gate다. 75% 이내라는 사실이
RF-independent pure Tensor energy를 증명하지는 않는다. 0.35-0.54 pJ/FLOP처럼 RF에 따른
차이가 보이면 단일 평균으로 숨기지 않고 min/median/max와 RF별 값을 함께 보고한다.
동일 ITER의 control은 treatment보다 빨리 끝나므로 이 coefficient에는 추가 active time의
scheduler/clock/register-fragment lifetime도 포함된다. 최종 audit의 RF별 treatment TFLOP/s,
treatment/control elapsed time과 net power를 함께 비교하며, GPU 간 차이를 Tensor 회로
차이만으로 해석하지 않는다.

마지막 파일의 `remediation_verdict=pass` 전에는 A100 Tensor/L2 값을 보고하지 않는다.

```text
results/summary/a100_tensor_l2_remediation_<TAG>_audit.md
```

## 해석 주의

- `.cg` 요청은 L1TEX를 통과하므로 `L1 request bytes ~= L2 read bytes`일 수 있다. 이것은
  L1 cache hit의 증거가 아니다.
- L1 우회 여부는 `l1_path_hit_rate_pct`와 `l1_hit_bytes/l1_request_bytes`로 판정한다.
- NCU 2026.1.1의 GA100 catalog에는 기존 `sass__inst_executed_register_spilling_*`
  counter가 없을 수 있다. 이 경우 명시적 local-memory를 사용하지 않는 Tensor kernel에서
  `l1tex__t_bytes_pipe_lsu_mem_local_op_ld/st=0`과 ptxas spill 0을 결합해 검증하며,
  summary에는 `spill_zero_verified=1`과
  `spill_evidence_source=local_memory_bytes_zero_inference`가 기록된다.
- 측정값은 NVML board/device total energy를 treatment-control로 차분하고 NCU로 경로를
  검증한 effective coefficient다. Tensor Core 또는 L2 SRAM의 순수 회로 에너지가 아니다.
- 기존 RF1/2 결과와 새 RF4 이상 결과를 섞지 않는다. control과 pair 실행 정책이 바뀌었기
  때문에 RF1-16 전체가 같은 새 package에서 다시 측정되어야 한다.
- normal policy가 통과하면 일반 `.cg` L2-hit effective coefficient다. persisting policy가
  선택되면 CUDA access-policy window와 L2 set-aside가 포함된 **residency-managed L2 path**
  coefficient다. 이를 모든 A100 workload의 기본 L2 energy로 일반화하면 안 된다.
- persisting cache는 line을 절대적으로 고정하는 보장이 아니다. 최종 승인은 여전히 NCU
  path-specific/native L2 hit>=95%와 sector conservation 교차검증이 결정한다. MIG에서는 set-aside가 비활성화될 수 있으므로
  normal도 실패하고 persisting API도 사용할 수 없으면 `none`으로 종료하는 것이 정상이다.
- `--replay-mode kernel --cache-control none`으로 수집한 이전 L2 metric은 warm-up cache
  상태가 metric pass마다 동일하다는 보장이 없다. 새 package는 application replay로
  application과 warm-up을 pass마다 다시 실행한다.
- NCU가 `Running with uncontrolled GPU caches` 경고를 출력하는 것은
  `cache-control none`을 의도적으로 선택했기 때문이다. 경고를 pass로 간주하는 것은 아니며,
  application replay metadata와 각 pass의 in-application warm-up, 최종 L1/L2/DRAM counter
  gate가 모두 통과해야 한다.

## Copy-Back Checklist

실행 후 아래 artifact를 디렉터리 구조 그대로 되가져온다. 최종 audit Markdown 하나만
가져오면 원시 증거를 재검증할 수 없다.

| artifact | 경로 패턴 |
|---|---|
| strict preflight | `results/summary/a100_tensor_l2_remediation_<TAG>_preflight.md` |
| schema/revision audit | `results/summary/a100_tensor_l2_remediation_<TAG>_schema_smoke_power_api_audit.*` |
| Tensor raw/matrix/calibration | `results/raw/a100_tensor_l2_remediation_<TAG>_tensor*.csv` |
| L2 raw/matrix | `results/raw/a100_tensor_l2_remediation_<TAG>_l2*.csv` |
| power audits | `results/summary/a100_tensor_l2_remediation_<TAG>_power_*.{csv,md}` |
| NCU reports and summary | `results/ncu/a100_tensor_l2_remediation_<TAG>/` 전체 |
| L2 policy evidence | `results/summary/a100_tensor_l2_remediation_<TAG>_l2_policy_*` |
| NCU acceptance | `results/summary/a100_tensor_l2_remediation_<TAG>_ncu_acceptance.{csv,md}` |
| pre-energy NCU gate | `results/summary/a100_tensor_l2_remediation_<TAG>_ncu_precheck.{csv,md}` |
| matched-control | `results/summary/a100_tensor_l2_remediation_<TAG>_matched_control_*` |
| instability audit | `results/summary/a100_tensor_l2_remediation_<TAG>_instability_audit.{csv,md}` |
| final targeted verdict | `results/summary/a100_tensor_l2_remediation_<TAG>_audit.{csv,md}` |
