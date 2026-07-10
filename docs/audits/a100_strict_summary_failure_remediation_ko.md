# A100 Strict Summary 실패 원인과 재실행 설계

작성일: 2026-07-10

## 판정

이 문서가 다루는 A100 실행은 power API audit 2,740/2,740 통과와 NCU sidecar
34개 완료를 달성했지만, strict component coefficient는 생성되지 않았다. 따라서
현재 run은 **측정 인프라는 정상이나 final coefficient evidence가 불충분한 run**으로
분류한다. Tensor, Global L1, L2 값을 final 표에 인용하면 안 된다.

## 관측된 실패와 원인

| 항목 | 관측 | 기존 설계의 문제 | 조치 |
|---|---|---|---|
| Tensor control | `reg_operand_only` HMMA 1,728개, RF와 무관 | `store_matrix_sync` epilogue가 block당 고정 Tensor-like instruction을 만들 수 있는데, gate가 HMMA `> 0`을 무조건 reject | 새 build에서 control의 WMMA store epilogue 제거. Legacy NCU row는 `HMMA/block <= 1` 및 `HMMA/expected_reg_operand_ops <= 1e-5`일 때만 fixed epilogue로 제한 허용 |
| Global L1 | coefficient distribution unstable | `clocked_empty`는 global load kernel의 tile/address/checksum loop와 다름 | `global_addr_only`를 추가해 동일 주소/loop/control flow에서 input load만 제거. final pair를 `global_l1_load_only - global_addr_only`로 변경 |
| L2 capacity mode | normal `l2_load_only`에서 L1 hit가 큼 | normal global load는 L1을 우회하지 않으므로 L2-only proof가 될 수 없음 | `l2_load_only`를 strict path에서 제외. `ld.global.cg` 기반 `l2_cg_load_only`만 final L2 candidate로 사용 |
| A100 L2 working set | `W_SM=256 KiB`, 108 SM = 27 MiB | 40 MiB L2의 68%로 set conflict/background traffic에 민감하고 hit plateau가 보장되지 않음 | final NCU coordinate를 `W_SM=64 KiB`(6.75 MiB total)로 낮추고 `W_SM=128 KiB`를 sweep 보조점으로 사용 |
| DRAM sanity | L2 hit 약 5.5%에서 reject | GPU L2 크기를 무시한 고정 5% cutoff | profile의 `L2 MiB / full working set MiB`로 예상 잔존 L2 hit를 계산하고, A100 8 MiB/SM DRAM stream에는 5.5%를 허용 범위로 해석 |
| strict audit cascade | strict CSV가 없는데 audit이 읽으려 해 `FileNotFoundError` | failure artifact를 생성하지 않는 orchestration | strict builder/reliability failure 후에도 strict audit, package audit, gap report를 작성하도록 변경 |

## 변경된 final measurement pair

| Component | treatment | control | 최종 의미 |
|---|---|---|---|
| Tensor | `reg_mma` | `reg_operand_only` | no-MMA register-fragment control 대비 MMA incremental energy |
| Shared scalar | `shared_scalar_load_only` | `clocked_empty` | shared-memory scalar instruction path |
| Global L1 | `global_l1_load_only` | `global_addr_only` | 같은 global address/tile/repeat loop에서 L1-cached input load가 추가하는 energy |
| L2 | `l2_cg_load_only` | `global_addr_only` | 같은 loop에서 `ld.global.cg` L2-hit load가 추가하는 energy |
| DRAM sanity | `dram_cg_load_only` | `global_addr_only` | 같은 loop에서 streaming CG load가 추가하는 energy. physical HBM energy가 아님 |

`global_addr_only`는 input pointer를 주소값으로만 사용한다. 따라서 address calculation,
tile 선택, repeat loop, checksum instruction은 memory treatment와 맞추되 global input
load는 실행하지 않는다. NCU에서는 global-load L1 byte가 0이고 DRAM byte가 expected input
traffic에 비해 무시할 수 있는지 확인한다. `--verify-smid=1`의 SMID atomic bookkeeping은
L2 sector counter에 보일 수 있으므로 L2 sector 자체를 0으로 요구하지 않는다.

## A100 재실행 조건

| path | strict NCU coordinate | energy factor | NCU factor | acceptance |
|---|---:|---|---|---|
| Tensor | W_SM 2048 KiB, blocks/SM 16 | RF 1,2,4,8,16 | RF 1,2,4,8,16 | treatment HMMA > 0, spill/local 0, control fixed HMMA only 허용 |
| Shared | W_SM 128 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | shared bytes/access 존재, bank conflict 낮음 |
| Global L1 | W_SM 16 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | L1 hit >= 95%, L2/L1 bytes <= 1% |
| L2 CG | W_SM 64 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | L2 hit >= 95%, L1 bytes/L2 bytes <= 1%, DRAM/L2 bytes <= 2% |
| DRAM sanity | W_SM 8192 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | DRAM bytes > 0, L2 residual hit은 working-set capacity bound 내 |

`W_SM=64 KiB` L2 point의 full-GPU logical working set은 `108 * 64 KiB = 6.75 MiB`다.
이는 40 MiB A100 L2보다 충분히 작다. L1 우회는 working-set 크기가 아니라
`ld.global.cg`와 NCU `L1 bytes / L2 bytes`로 검증한다.

## 실행

새 kernel/control 변경을 반영하려면 기존 A100 binary를 재사용하면 안 된다.

```bash
cmake -S . -B build-a100 -DCMAKE_CUDA_ARCHITECTURES=80
cmake --build build-a100 --clean-first -j
python3 scripts/plan_platform_component_experiment.py --target-profile a100 --tag $(date +%Y%m%d)
NCU_USE_SUDO=1 bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

이 script는 failure가 생겨도 `component_reliability_audit`, strict summary audit,
platform package audit, gap report를 계속 작성한다. `strict summary`가 없으면 audit에는
`summary_artifact_exists=fail`이 남으며, 이것은 coefficient가 final이 아니라는 뜻이다.

## 구현 검증 범위

| 검증 | 결과 | 한계 |
|---|---|---|
| CUDA build | `sm_80` A100 target build 성공 | A100 node runtime execution은 아직 필요 |
| Tensor control NCU smoke | RTX 3090에서 새 `reg_operand_only` HMMA sum = 0 | compiler/NCU version이 다른 A100에서 sidecar 재확인 필요 |
| Address control NCU smoke | RTX 3090에서 `global_addr_only` global-load L1 byte = 0 | SMID atomic 때문에 L2 sector는 0이 아니며, A100에서도 expected-byte 대비 DRAM ratio로 재검증 필요 |
| A100 finalplan dry-run | W_SM 64 KiB, active SM 108에서 6.75 MiB working set과 mode allowed 확인 | 실제 A100 cache hit/energy coefficient는 아직 측정 전 |

따라서 이번 변경은 기존 A100 수치를 final로 만드는 것이 아니라, 기존 run의 실패 원인을
제거한 재실행 가능한 strict design을 제공한다. 새 binary와 새 command package로 A100
energy sweep 및 NCU sidecar를 다시 실행한 뒤에만 coefficient를 보고한다.

## 보고 원칙

- 기존 A100 run의 shared scalar 1.008 pJ/bit는 해당 shared path evidence만 통과한
  provisional observation이다. Tensor/L1/L2 final coefficient와 함께 표에 넣지 않는다.
- `l2_load_only`의 결과는 L2 capacity diagnostic으로만 보고하며 L2-only coefficient로
  변환하지 않는다.
- 새 결과도 NVML board/device total-energy 차분과 NCU path evidence로 얻는 effective
  microbenchmark coefficient다. pure SRAM, Tensor Core, HBM circuit pJ/bit 값이 아니다.
