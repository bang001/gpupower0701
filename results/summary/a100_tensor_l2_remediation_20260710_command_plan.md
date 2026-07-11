# A100 Tensor/L2 Targeted Remediation Plan

작성일: 2026-07-10

## 목적

이 package는 기존 A100 실행에서 확인된 두 실패만 다시 검증한다.

1. Tensor RF4/8/16의 `delta_E < 10 J` 또는 음수 문제
2. `l2_cg_load_only`의 aggregate L2 hit 70-72% 및 L1/L2 bytes 71-72% 문제

전체 Shared/L1/DRAM package를 대체하지 않는다. 이 실행이 통과하면 수정된 Tensor와 L2
경로를 full A100 package에 합칠 수 있다는 뜻이며, full component summary는 이후 표준
package로 다시 생성해야 한다.

## 핵심 수정

| 문제 | 수정된 실험 조건 | 판정 증거 |
|---|---|---|
| Tensor control의 RF 비례 추가 연산 | 두 kernel에 동일한 dependent integer add와 동일 scalar-store epilogue만 유지; control의 FP32 FMA/checksum/memory 제거 | raw revision marker, control HMMA=0, treatment HMMA>0, spill=0 |
| Tensor mode별 ITER 불일치와 짧은 control | RF별 `reg_mma` 20 s calibration과 `reg_operand_only` 2 s 최소 calibration을 수행하고, 두 ITER 중 큰 값을 두 mode에 동일 적용 | calibration manifest의 두 candidate ITER와 max policy, raw ITER, matched-detail `iter_ratio=1` |
| pair가 반복 경계에서 분리될 가능성 | command 한 개가 아니라 control-treatment 2개를 원자적 pair로 회전 | runner matrix와 matched-detail `pair_start_distance_ms<=30000` |
| `.cg`의 L1 request를 L1 hit로 오인 | global-load lookup hit/miss와 L2 read hit/miss를 path-specific으로 사용 | L1 path hit <=1%, L1 hit/request <=1%, L2 read hit >=95% |
| normal warm-up의 L1 오염 | CG treatment의 warm-up도 `ld.global.cg` 사용 | raw `global_warmup_policy=ld_global_cg` marker |
| 단일 L2 좌표의 우연한 통과 | W16/32/64/128을 모두 검증하고 인접한 두 W의 pJ/bit plateau 요구 | NCU+energy 통과 W 두 개 이상, 상대 차이 <=35% |

## Parameter Sweep

모든 단위와 명령 개수는 다음과 같다.

| 단계 | 고정 조건 | sweep | 1회당 좌표 | 반복/총 행 또는 case |
|---|---|---|---:|---:|
| Tensor calibration | A100, 108 SM, W_SM=2048 KiB, blocks/SM=16 | RF별 treatment target 20 s + control floor 2 s | RF 5개 x calibration 2 modes | 10 calibration commands, raw energy 행 아님 |
| Tensor energy | A100, 108 SM, W_SM=2048 KiB, blocks/SM=16, pair-locked ITER | mode 2개 x RF 1,2,4,8,16 | 10 commands | 7 repeats, 70 raw rows |
| L2 energy | A100, 108 SM, blocks/SM=16, 20 s/mode | mode 2개 x W_SM 16,32,64,128 KiB x LR 4,8,16 | 24 commands | 7 repeats, 168 raw rows |
| Tensor NCU | W_SM=2048 KiB, blocks/SM=16, ITER=100,000 | mode 2개 x RF 1,2,4,8,16 | 10 cases | 10 NCU cases |
| L2 NCU | blocks/SM=16, ITER=100,000 | mode 2개 x W_SM 16,32,64,128 KiB x LR 1,2,4,8,16 | 40 cases | 40 NCU cases |
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
| Tensor NCU | `reg_mma` HMMA>0, `reg_operand_only` HMMA=0, 두 mode local read/write bytes=0 및 spill=0, acceptance pass |
| Tensor energy | 7개 pair 모두 `delta_E>=10 J`, coefficient>0, pair start distance<=30,000 ms, median 0.01-5 pJ/FLOP |
| L2 각 W | LR1/2/4/8/16 treatment/control 모두 accepted; control input L1 request=0 및 DRAM/expected<=0.1%; treatment L1 path hit<=1%, L1 hit/request<=1%, L2 read hit>=95%, DRAM/L2<=2% |
| L2 energy | LR4/8/16별 최소 5 valid repeats, 모든 delta_E>=10 J, positive pJ/bit, exact NCU denominator |
| L2 plateau | 위 조건을 통과한 인접 W 두 개 이상의 median pJ/bit 상대 차이<=35% |

35%는 A100 회로 특성에서 유도한 상수가 아니라, 이 targeted run에서 working-set 변화에
대해 coefficient가 같은 order와 plateau를 보이는지 판정하기 위해 실행 전에 고정한
재현성 tolerance다. 이 기준을 넘으면 더 좋아 보이는 한 점을 선택하지 않고 재실행한다.

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
| NCU acceptance | `results/summary/a100_tensor_l2_remediation_<TAG>_ncu_acceptance.{csv,md}` |
| matched-control | `results/summary/a100_tensor_l2_remediation_<TAG>_matched_control_*` |
| instability audit | `results/summary/a100_tensor_l2_remediation_<TAG>_instability_audit.{csv,md}` |
| final targeted verdict | `results/summary/a100_tensor_l2_remediation_<TAG>_audit.{csv,md}` |
