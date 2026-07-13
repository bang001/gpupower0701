# GPU Power Modeling 실험 결과 상태

갱신일: 2026-07-13

## 현재 결론

현재 저장소에는 **Tensor, Shared, Global L1, L2를 모두 현행 protocol로
재실행한 완전한 RTX 3090 component table은 없다**. 다만 2026-07-13에 Tensor
path는 fixed-RF v2 kernel로 재실행해 power API 70/70, NCU 10/10 및 33개
matched pair gate를 통과했다. Shared/Global L1/L2는 아직 새 전체 package를
실행해야 한다.

### 현행 Tensor fixed-RF v2 결과

| Component/path | 현행 값 | 단위 | pair | 근거 | 상태 |
|---|---:|---|---|---|---|
| Tensor MMA incremental | **2.252501** | pJ/FLOP | `reg_mma - reg_operand_only`, matched ITER | RF1/2/4/8/16, 33 valid pair, NCU treatment/control 10/10 accepted | current standalone Tensor evidence |

RF별 median은 RF1 `1.9754`, RF2 `2.3211`, RF4 `2.2733`, RF8 `2.2525`, RF16
`2.2458 pJ/FLOP`이다. 모든 treatment의 `HMMA/logical MMA=2`, 모든 control의
HMMA=0, local read/write=0이다. 이 값은 board-level effective MMA incremental
coefficient이며 pure Tensor 회로 에너지가 아니다. 상세 조건과 제외 이유는
[`results/summary/rtx3090_tensor_fixedrf_v2_report_20260713_ko.md`](../../results/summary/rtx3090_tensor_fixedrf_v2_report_20260713_ko.md)에
정리했다.

2026-07-08 Global L1/L2 energy pair는 `clocked_empty` control을 사용했고,
`global_addr_only`의 동일 좌표 NCU acceptance와 현행 path-specific counter schema가
없다.

따라서 아래 과거 수치는 현행 final 값으로 인용하지 않는다.

| Component/path | 과거 보고값 | 단위 | 과거 pair | 현행 상태 |
|---|---:|---|---|---|
| Tensor MMA incremental | 0.129216 | pJ/FLOP | `reg_mma - reg_operand_only` | superseded historical; v2와 커널/프로토콜이 다름 |
| Shared scalar path | 0.170590 | pJ/bit | `shared_scalar_load_only - clocked_empty` | historical; 전체 package 재실행 필요 |
| Global L1 hit path | 0.173483 | pJ/bit | `global_l1_load_only - clocked_empty` | provisional; address control 누락 |
| L2 CG hit path | 1.131073 | pJ/bit | `l2_cg_load_only - clocked_empty` | provisional; address control 누락 |
| DRAM cumulative effective path | **26.709-28.409** | pJ/bit | 목표: `dram_cg_load_only - global_addr_only` matched ITER | `provisional_reference_aligned_range`; 현행 raw pair가 없어 strict 실측값 아님 |

DRAM 범위를 제외한 과거 값들은 pure circuit/bitcell energy가 아니라 당시 NVML
total-energy 차분과 NCU treatment-path evidence로 얻은 effective microbenchmark
coefficients였다. DRAM 범위는 최신 보고 정책이며, accepted 측정값이 아니다.

![RTX 3090 DRAM 최신 provisional 보고 범위](../assets/component_energy_method/current_dram_reporting_band.png)

과거 `clocked_empty` DRAM 수치는 pJ/byte에서 pJ/bit로 환산한 산술 자체보다 control
정책이 문제다. 현행 설계는 동일 ITER의 address control을 요구하므로 그 값을 최신
DRAM coefficient로 재사용하지 않는다. 상세 정책은
`results/summary/rtx3090_dram_current_reporting_policy_20260712.md`를 따른다.

과거 전체 표, sweep, 그래프, 해석은
`archive/pre_current_protocol_20260712/docs/gpu_power_modeling_experiment_results_ko.md`에
보존한다. 옛 DRAM 막대가 최신값처럼 보이지 않도록 historical coefficient 그림은
active 결과 문서에서 제거했다.

## 현행 재감사 결과

| Audit | 결과 | 의미 |
|---|---:|---|
| old strict summary current-protocol reaudit | 181 pass, 8 fail | old path-specific schema와 address-control evidence 부족 |
| current goal readiness | 4 fail, 6 missing, 0 warning | RTX 3090 재실행 및 외부 V100/A100/H100 결과 필요 |
| platform implementation readiness | all pass | profile/command package 구현은 정적 기준 통과 |

근거:

- `results/summary/rtx3090_current_protocol_reaudit_20260712.md`
- `results/summary/component_energy_goal_readiness_audit_20260712.md`
- `docs/audits/current_goal_alignment_audit_ko.md`

## 보존된 RTX 3090 NCU 경로 검증 결과

아래 내용은 2026-07-08 factor sidecar와 2026-07-09 **실제 RTX 3090 live
NCU run**에서 얻은 historical path evidence다. 원본 NCU CSV와 `.ncu-rep`가 저장소에
남아 있어 재검산할 수 있으므로, 현행 결과 문서에도 보존한다.

다만 여기서 `accepted`는 **당시 treatment kernel의 경로 판정 기준을 통과했다**는
뜻이다. Global L1/L2/DRAM의 동일 좌표 `global_addr_only` control acceptance까지
요구하는 2026-07-12 현행 protocol의 final coefficient 승인을 뜻하지 않는다.

| 증거 층 | 실행일 | 검증한 내용 | 재사용 가능한 결론 | 재사용하면 안 되는 결론 |
|---|---|---|---|---|
| factor sidecar | 2026-07-08 | RF/LR별 treatment path, hit rate, access/byte traffic, stall | 당시 선택한 kernel이 Tensor/Shared/L1/L2/DRAM 방향으로 동작했는지 | 현행 control gate까지 통과한 최종 pJ/FLOP 또는 pJ/bit |
| live evidence run | 2026-07-09 | 실제 NCU output에서 필수 필드가 채워지는지 | access count, bytes, shared bytes, stall/status counter의 실재와 대표 경로 | 반복 energy run과 결합된 새 coefficient 또는 순수 회로 에너지 |

### NCU 검증 이미지

![RTX 3090 NCU hit-rate, access, byte 및 status 검증](../assets/component_energy_method/ncu_hit_rate_validation.png)

![RTX 3090 live NCU evidence fields](../assets/component_energy_method/ncu_live_evidence_fields.png)

![RTX 3090 NCU path별 byte traffic](../assets/component_energy_method/ncu_path_validation_bytes.png)

첫 그림은 2026-07-08 factor sidecar의 대표 RF/LR=4 row와 reject 예시를 함께
보여준다. 두 번째 그림은 2026-07-09 live run 6개 대표 row에서 요청한 evidence
field가 실제로 채워졌는지를 보여준다. 세 번째 그림은 Shared/L1/L2/DRAM byte
traffic의 크기 차이를 log scale로 비교한다. 이 그림들은 energy coefficient 그래프가
아니며, NCU 경로 증거 시각화다.

### 확인 필드와 단위

| 확인 항목 | NCU 요약 열 | 단위/해석 |
|---|---|---|
| L1 access count | `l1_accesses` | 이 RTX 3090 run에서는 sector. 다른 metric set에서는 request일 수 있어 `l1_access_unit`을 함께 확인 |
| L2 access count | `l2_accesses` | sector |
| DRAM access count | `dram_accesses` | sector |
| Shared traffic | `shared_bytes` | byte (B), SASS shared data byte counter 기반 |
| L1/L2/DRAM traffic | `l1_bytes`, `l2_bytes`, `dram_bytes` | byte (B) |
| Long scoreboard | `stall_long_scoreboard_pct` | `%` 표기의 NCU `per_issue_active` 파생 신호. 단순 시간 점유율이 아님 |
| Path 판정 | `acceptance`, `acceptance_reason` | 당시 path gate의 accepted/rejected와 이유 |
| Evidence 완전성 | `status`, `reason` | 필수 열이 실제 live NCU 결과에 존재하는지 |

`stall_long_scoreboard_pct`는 이름에 `%`가 있지만 active issue당 stall된 warp 수를
정규화한 파생 metric이므로 100을 넘을 수 있다. 예를 들어 L2/DRAM의 864.97와
1784.08을 각각 실행 시간의 864.97%, 1784.08%로 읽으면 안 된다. 여기서는 memory
dependency가 강한 path인지 비교하는 **percent-like stall signal**로만 사용한다.

### 2026-07-08 factor sidecar 대표 결과

아래 표는 RF/LR=4 treatment/control 대표 row다. `l2_cg_load_only`와
`dram_cg_load_only`에서 L1 access가 커도 L1 hit가 거의 0이므로, 그 수는 L1에
데이터가 머물렀다는 뜻이 아니라 L1TEX request-side sector traffic으로 해석한다.

| mode | 좌표 | 당시 acceptance | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses | DRAM accesses | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB signal (%) | field status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `reg_mma` | RF=4 | accepted | 34.9586 | 77.5795 | 0 sectors | 0 sectors | 1.99776e6 sectors | 0 | 0 | 8.02851e7 | 6.39284e7 | 0.010039 | pass |
| `reg_operand_only` | RF=4 | accepted | 31.1890 | 26.0331 | 0 sectors | 9.03367e5 sectors | 3.19101e6 sectors | 0 | 0 | 1.87625e8 | 1.47636e8 | 0.009723 | pass |
| `shared_scalar_load_only` | LR=4 | accepted | 21.0747 | 42.0761 | 0 sectors | 4.14979e6 sectors | 5.72894e6 sectors | 5.37401e11 | 0 | 4.05844e8 | 3.02841e8 | 0.002106 | pass |
| `global_l1_load_only` | LR=4 | accepted | 99.9982 | 66.9942 | 3.35872e10 sectors | 5.66108e6 sectors | 7.19713e6 sectors | 0 | 1.07479e12 | 5.92794e8 | 4.52661e8 | 17.4469 | pass |
| `l2_cg_load_only` | LR=4 | accepted | 0.000006 | 99.8978 | 1.67936e10 sectors | 1.67970e10 sectors | 1.19183e7 sectors | 0 | 5.37395e11 | 5.37997e11 | 5.40672e8 | 867.454 | pass |
| `dram_cg_load_only` | LR=4 | accepted | 0.000006 | 0.104067 | 1.67936e10 sectors | 1.68016e10 sectors | 1.68197e10 sectors | 0 | 5.37395e11 | 5.38836e11 | 5.38608e11 | 1747.88 | pass |

당시 reject된 비교 후보도 path 선정 근거로 남긴다.

| mode | 좌표 | 당시 acceptance | L1 hit (%) | L2 hit (%) | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB signal (%) | reject reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `l2_load_only` | W_SM=64 KiB, B=16 | rejected | 88.3689 | 99.7936 | 0 | 1.07479e12 | 1.25376e11 | 2.95498e8 | 70.7279 | L1 hit가 너무 높아 L2-only 후보가 아님 |
| `shared_load_only` | W_SM=64 KiB, B=16 | rejected | 26.8489 | 57.6059 | 5.37401e11 | 0 | 4.56121e8 | 3.19504e8 | 0.000554 | shared bank conflict 4.1984e9가 검출됨 |

이 두 row는 capacity와 mode 이름만으로 path를 확정할 수 없고, hit/access/byte 및 bank
conflict counter를 함께 봐야 한다는 근거로만 사용한다.

원본 요약은
[factor stability acceptance CSV](../../results/summary/rtx3090_finalplan_ncu_factor_stability_acceptance_20260708.csv)와
[evidence field check](../../results/summary/rtx3090_ncu_evidence_field_check_20260709.md)에
있다. 전체 factor sidecar는 Tensor RF=1,2,4,8,16과 memory LR=4,8,16을 포함한다.

### 2026-07-09 실제 live NCU run

이 run은 coefficient를 다시 계산하기 위한 power 반복 실험이 아니라, 보고서에 쓰는
필드가 실제 NCU output에서 수집되는지 double-check한 실험이다. 공통 조건은 RTX 3090
82 active SM과 blocks/SM=16이며, 각 mode의 상세 좌표는 다음과 같다.

| mode | W_SM (KiB/SM) | ITER (count) | RF (unitless) | LR (count) |
|---|---:|---:|---:|---:|
| `reg_mma` | 2048 | 100,000 | 4 | 1 |
| `reg_operand_only` | 2048 | 100,000 | 4 | 1 |
| `shared_scalar_load_only` | 64 | 100,000 | 1 | 4 |
| `global_l1_load_only` | 16 | 100,000 | 1 | 4 |
| `l2_cg_load_only` | 64 | 100,000 | 1 | 4 |
| `dram_cg_load_only` | 8192 | 100,000 | 1 | 4 |

| mode | 당시 acceptance | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses | DRAM accesses | shared bytes (B) | L1 bytes (B) | L2 bytes (B) | DRAM bytes (B) | long SB signal (%) | live field status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `reg_mma` | accepted | 36.2957 | 32.3856 | 0 sectors | 431,231 sectors | 2.16480e6 sectors | 0 | 0 | 1.20292e8 | 9.38189e7 | 0.010564 | pass |
| `reg_operand_only` | accepted | 31.7291 | 63.2529 | 0 sectors | 427,908 sectors | 2.11342e6 sectors | 0 | 0 | 1.21160e8 | 9.01961e7 | 0.009671 | pass |
| `shared_scalar_load_only` | accepted | 20.8079 | 15.0719 | 0 sectors | 724,793 sectors | 3.04068e6 sectors | 5.37401e11 | 0 | 1.55649e8 | 1.19054e8 | 0.001967 | pass |
| `global_l1_load_only` | accepted | 99.9998 | 57.2715 | 3.35872e10 sectors | 41,984 sectors | 4.38920e6 sectors | 0 | 1.07479e12 | 1.79393e8 | 1.40454e8 | 17.4343 | pass |
| `l2_cg_load_only` | accepted | 0.000007 | 99.9066 | 1.67936e10 sectors | 1.67994e10 sectors | 1.40017e7 sectors | 0 | 5.37395e11 | 5.38188e11 | 7.19515e8 | 864.970 | pass |
| `dram_cg_load_only` | accepted | 0.000007 | 0.038381 | 1.67936e10 sectors | 1.67998e10 sectors | 1.68180e10 sectors | 0 | 5.37395e11 | 5.38663e11 | 5.38470e11 | 1784.08 | pass |

필수 evidence field는 6/6 대표 row에서 모두 `pass`였다. 해석 가능한 핵심은 다음과
같다.

| path | live NCU에서 확인된 사실 | 현재 사용할 때의 제한 |
|---|---|---|
| Tensor treatment/control | `reg_mma`에 HMMA 1.0496e9, `reg_operand_only`에 HMMA 0; 두 mode 모두 당시 spill/local counter 0 | 현행 kernel revision과 treatment-control pair lock으로 재실행 필요 |
| Shared scalar | shared 5.37401e11 B, shared bank conflict 0, global traffic은 shared traffic보다 매우 작음 | Shared SRAM bitcell 단독 에너지가 아니라 scalar shared load path 증거 |
| Global L1 | L1 hit 99.9998%, L1 1.07479e12 B, L2/DRAM leakage는 훨씬 작음 | 당시 energy control이 `clocked_empty`; 현행 `global_addr_only` control 재실행 필요 |
| L2 CG | L1 hit 약 0%, L2 hit 99.9066%, DRAM/L2 bytes 약 0.134% | stall-heavy effective path이며 pure L2 SRAM energy가 아님 |
| DRAM CG | L1/L2 hit가 거의 0%, DRAM 5.38470e11 B | streaming sanity path 증거이며 현행 DRAM coefficient 자체는 아님 |

Live run의 재검산 경로:

| artifact | 경로와 역할 |
|---|---|
| NCU summary CSV | [ncu_cache_validation_summary.csv](../../results/ncu/rtx3090_ncu_evidence_check_20260709/ncu_cache_validation_summary.csv): live raw metric을 mode별 열로 정규화 |
| NCU path acceptance | [rtx3090_ncu_evidence_check_acceptance_20260709.md](../../results/summary/rtx3090_ncu_evidence_check_acceptance_20260709.md): 당시 path gate 결과 |
| Evidence field audit | [rtx3090_ncu_evidence_live_field_check_20260709.md](../../results/summary/rtx3090_ncu_evidence_live_field_check_20260709.md): 요청 필드 6/6 pass 확인 |
| NCU details/raw metrics | [live NCU directory](../../results/ncu/rtx3090_ncu_evidence_check_20260709/): mode별 `.ncu-rep`, `_details.csv`, `_raw_metrics.csv` |

## RTX 3090 재실행 조건

| Component | modes | energy W_SM (KiB/SM) | energy blocks/SM | strict NCU W/B | sweep |
|---|---|---:|---|---|---|
| Tensor | `reg_operand_only,reg_mma` | 2048 | 8,16 | 2048/8 | RF 1,2,4,8,16 |
| Shared scalar | `clocked_empty,shared_scalar_load_only` | 32,64 | 8,16 | 64/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| Global L1 | `global_addr_only,global_l1_load_only` | 8,16 | 8,16 | 8/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| L2 CG | `global_addr_only,l2_cg_load_only` | 64 | 8,16 | 64/8 | LR 4,8,16; NCU 1,2,4,8,16 |
| DRAM sanity | `global_addr_only,dram_cg_load_only` | 8192 | 8,16 | 8192/8 | LR 4,8,16; NCU 1,4,8,16 |

공통 energy 조건은 target 10 s, 5 repeats다. Tensor와 DRAM은 treatment/control-floor
dual calibration 후 큰 동일 ITER를 두 mode에 적용한다. Final analyzer는
`--require-control-ncu-acceptance`를 사용한다.

실행:

```bash
bash results/summary/rtx3090_component_finalplan_20260712_commands.sh
```

NCU 권한 오류가 있을 때만 NCU 경로를 sudo로 실행한다.

```bash
NCU_USE_SUDO=1 bash results/summary/rtx3090_component_finalplan_20260712_commands.sh
```

상세 명령과 acceptance 기준은
`results/summary/rtx3090_component_finalplan_20260712_command_plan.md`를 따른다.

## Final 인정 조건

1. Power row가 explicit GPU/device total-energy counter scope를 사용한다.
2. Tensor/Shared/Global L1/L2 treatment NCU path가 exact coordinate에서 accepted다.
3. `reg_operand_only`와 `global_addr_only` control도 같은 좌표에서 accepted다.
4. Memory denominator가 `ncu_actual_exact`이고 단위가 표에 기록된다.
5. matched-control, reliability, strict summary, strict summary audit, package audit가
   모두 통과한다.
6. 숫자의 hierarchy가 그럴듯하다는 이유로 실패 gate를 무시하지 않는다.

새 결과가 생성되기 전까지 보고서에는 “RTX 3090 historical/provisional result”라고
표기한다.
