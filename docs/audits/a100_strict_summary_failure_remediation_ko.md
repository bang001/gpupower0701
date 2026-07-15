# A100 Strict Summary 실패 원인과 재실행 설계

작성일: 2026-07-10, updated 2026-07-14

> 2026-07-14 교정: GA100 source/TEX direct hit와 native lookup hit에 각각 95%를
> 요구했던 규칙은 폐기했다. 현재 기준은
> `docs/methodology/a100_l2_fabric_aware_experiment_design_ko.md`의 source+LTC-fabric
> logical final-service 모델이다. 이 문서의 과거 결과는 fabric counter가 없어 여전히
> 미승인이지만, direct 58-60% 자체를 최종 L2 miss로 해석하지 않는다.
>
> External-memory 경로의 현행 기준은
> `docs/methodology/external_memory_read_path_experiment_design_ko.md`다. 이
> 문서의 `DRAM sanity` 표현과 단일 W8192 조건은 historical remediation
> 맥락으로만 보존하고, 새 실험은 read-only 분모와 architecture-aware W
> sweep을 사용한다.

## 판정

이 문서가 다루는 최초 A100 실행은 power API audit 2,740/2,740 통과와 NCU sidecar
34개 완료를 달성했지만, strict component coefficient는 생성되지 않았다. 후속 재현에서도
Tensor는 RF1/2만 약 0.14-0.30 pJ/FLOP였고 RF4 이상은 `delta_E < 10 J` 또는 음수였으며,
L2 CG 5개 row는 aggregate hit/byte gate에서 모두 reject되었다. 따라서
현재 run은 **측정 인프라는 정상이나 final coefficient evidence가 불충분한 run**으로
분류한다. Tensor, Global L1, L2 값을 final 표에 인용하면 안 된다.

2026-07-13 후속 A100 실행에서는 dual calibration 후 Tensor RF1-16이 모두 양수
0.35-0.54 pJ/FLOP로 계산되었다. 이는 음수 차분 문제의 해소 증거지만, 로컬 저장소에
해당 raw/NCU artifact가 없고 RF별 `HMMA/logical MMA` 선형성 검사를 통과했다는 증거도
없으므로 아직 final로 승인하지 않는다. 이 값과 비교해야 할 현행 RTX 3090 fixed-RF v2
median은 2.2525 pJ/FLOP이며, 과거 0.129-0.146 pJ/FLOP는 kernel/control/pair protocol이
다른 historical auxiliary 결과다. 따라서 A100 값이 RTX보다 2배 높다는 최초 해석은
성립하지 않는다. 같은 실행의 L2 source/TEX direct read hit는
W_SM 16/32/64/128 KiB에서 약 58.5-60.1%였다. 이 값만으로 최종 L2 miss를 판정할 수
없고 당시 `srcunit_ltcfabric` evidence가 없으므로, 결론은 그대로 L2 coefficient
`not identified`다.

## 관측된 실패와 원인

| 항목 | 관측 | 기존 설계의 문제 | 조치 |
|---|---|---|---|
| Tensor control NCU | `reg_operand_only` HMMA 1,728개, RF와 무관 | `store_matrix_sync` epilogue가 block당 고정 Tensor-like instruction을 만들 수 있었음 | 두 mode 모두 WMMA store 대신 같은 per-thread 8개 scalar store를 사용. treatment는 accumulator 8개를 저장해 HMMA를 보존하고 control은 sink 값을 저장. control HMMA=0, treatment HMMA>0 요구 |
| Tensor RF4 이상 음수/weak | RF가 커질수록 control energy가 treatment보다 빠르게 증가하고 두 mode의 ITER도 달라짐 | 기존 control loop의 RF 비례 FP32 FMA/checksum과 mode별 duration calibration이 treatment-control work를 다르게 만듦 | RF당 dependent register integer add 1개를 **두 kernel에 공통으로** 넣고 control에서 FP32 FMA/checksum/memory를 제거. 각 RF에서 treatment 20 s와 control 최소 2 s를 각각 calibrate해 두 ITER의 최대값을 두 mode에 같은 `--iters`로 적용, `E_reg_mma - E_reg_operand_only` 직접 차분 |
| RTX 3090 RF2 HMMA 비선형 | runtime reuse loop에서 RF1/4/8/16은 `HMMA/logical MMA=2`였지만 RF2는 3, RF6 probe도 2.333 | GA102가 일부 dynamic loop trip count에서 추가 predicated HMMA issue를 생성해 logical FLOP와 issued HMMA의 비례가 깨짐. RF2의 낮은 TFLOP/s와 높은 pJ/FLOP도 이 현상과 일치 | 정확했던 RF1은 treatment/control 모두 dynamic 경로를 유지하고 RF2/4/8/16은 compile-time fixed-trip `unroll 1` kernel로 dispatch. 수정 후 GA102 one-metric probe에서 다섯 RF 모두 HMMA/logical MMA=2 확인. revision을 `matched_add_scalar_epilogue_fixed_rf_v2`로 갱신하고 모든 v1 energy artifact는 재사용 금지 |
| Global L1 | coefficient distribution unstable | `clocked_empty`는 global load kernel의 tile/address/checksum loop와 다름 | `global_addr_only`를 추가해 동일 주소/loop/control flow에서 input load만 제거. final pair를 `global_l1_load_only - global_addr_only`로 변경 |
| L2 capacity mode | normal `l2_load_only`에서 L1 hit가 큼 | normal global load는 L1을 우회하지 않으므로 L2-only proof가 될 수 없음 | `l2_load_only`를 strict path에서 제외. `ld.global.cg` 기반 `l2_cg_load_only`만 final L2 candidate로 사용 |
| A100 L2 working set | W64에서도 aggregate L2 hit 70.7-72.0%, `L1 bytes/L2 bytes` 71-72% | `.cg` request도 L1TEX를 통과하므로 L1 request bytes를 L1 cache hit bytes로 오해한 gate가 잘못됨. 기존 normal-load warm-up이 L1을 먼저 채우는 혼입 가능성도 있었음 | W16/32/64/128을 sweep하고 L1 actual hit, source L2 lookup, LTC-fabric lookup, DRAM read를 별도 집계. CG warm-up도 `ld.global.cg`로 변경 |
| 후속 A100 L2 source hit | source/TEX hit 58.5-60.1%, native 67-72.5%, L1 bypass 통과 | 첫 partition miss가 fabric의 다른 partition에서 hit할 수 있는데 source/native 각각에 95%를 적용 | 같은 minimal replay에서 `srcunit_ltcfabric` read/hit/miss를 추가하고 logical final hit>=95%, source/fabric 보존, native-model 오차<=2 pp, expected bytes와 DRAM-read gate로 교정 |
| Tensor architecture comparison | A100 0.35-0.54 pJ/FLOP를 RTX 과거 0.129-0.146과 비교해 2배 이상으로 해석 | 과거값은 현행 `fixed_rf_v2`와 kernel/control/pair protocol이 다르다. 현행 RTX median은 2.2525 pJ/FLOP이므로 그 비교는 무효다. 또한 logical WMMA FLOP가 같아도 lowering, clock, board power scope가 다르다. | A100 raw marker, 동일 ITER, RF1-16 `HMMA/logical MMA` 상대 spread<=10%, control HMMA=0, spill/local=0을 먼저 검증한다. 통과 후 같은 v2 RTX 결과와 비교하되 차이를 순수 Tensor 회로 차이로 해석하지 않는다. |
| External-memory effective path | L2 hit 약 5.5%에서 구형 gate reject | GPU L2 크기를 무시한 고정 5% cutoff와 total DRAM byte 분모 | A100 W2048/4096/8192 KiB/SM sweep, final-service L2 hit <=10%, external read/L2 source >=90%, write/read <=1%, `dram__bytes_read.sum` 필수 |
| strict audit cascade | strict CSV가 없는데 audit이 읽으려 해 `FileNotFoundError` | failure artifact를 생성하지 않는 orchestration | strict builder/reliability failure 후에도 strict audit, package audit, gap report를 작성하도록 변경 |
| strict cache evidence schema | 새 path-specific 열을 전역 필수로 두면 기존 RTX 3090 accepted artifact까지 무관하게 실패 | 역사적 aggregate schema와 새 target-node schema의 경계가 없음 | 새 generated package는 strict audit에 `--require-path-specific-cache-evidence`를 사용. 플래그 없는 경로는 기존 RTX artifact 재감사에만 허용 |
| L1 재실행 중 pipeline 중단 | `global_addr_only`, W_SM=16 KiB, blocks/SM=32가 block당 0.5 KiB라 binary exit 2 | Python matrix가 address control을 memory-backed mode로 분류하지 않아 treatment는 skip하면서 control은 실행 | `global_addr_only`를 C++와 같은 memory-backed mode로 분류하고 W16/B32 treatment/control을 모두 제외. 실행 전 모든 valid 좌표를 binary `--dry-run`으로 선검증 |

동일 ITER를 쓰면 no-MMA control은 treatment보다 훨씬 빨리 끝난다. 이것은 두 mode에
서로 다른 ITER를 써도 된다는 뜻이 아니다. Treatment 20 s와 control 최소 2 s를 각각
calibration하고 두 candidate ITER의 최대값을 두 mode에 공통 적용한다. Analyzer는 실제
control elapsed가 1.6 s 이상인지 확인하며, control `net_E_J <=0` 또는 1.6 s 미만은
noise floor 미식별로 reject한다.
두 kernel의 inner loop에는 같은 dependent integer add가 1개씩 있으므로 차분은
`MMA - integer add`가 아니라 공통 add/loop를 상쇄한 MMA increment에 가깝다.

## 변경된 final measurement pair

| Component | treatment | control | 최종 의미 |
|---|---|---|---|
| Tensor | `reg_mma` | `reg_operand_only` | no-MMA register-fragment control 대비 MMA incremental energy |
| Shared scalar | `shared_scalar_load_only` | `shared_scalar_addr_only` | 같은 shared allocation/index loop 대비 shared-memory scalar read path |
| Global L1 | `global_l1_load_only` | `global_addr_only` | 같은 global address/tile/repeat loop에서 L1-cached input load가 추가하는 energy |
| L2 | `l2_cg_load_only` | `global_addr_only` | 같은 loop에서 `ld.global.cg` L2-hit load가 추가하는 energy |
| External-memory read path (effective) | `dram_cg_load_only` | `global_addr_only` | 같은 loop에서 streaming CG load가 추가하는 GPU-device energy. physical HBM energy가 아님 |

`global_addr_only`는 input pointer를 주소값으로만 사용한다. 따라서 address calculation,
tile 선택, repeat loop, checksum instruction은 memory treatment와 맞추되 global input
load는 실행하지 않는다. NCU에서는 global-load L1 request byte가 0이고 DRAM byte가 expected input
traffic에 비해 무시할 수 있는지 확인한다. `--verify-smid=1`의 SMID atomic bookkeeping은
L2 sector counter에 보일 수 있으므로 L2 sector 자체를 0으로 요구하지 않는다.
Address control의 DRAM background 허용치는 expected treatment input의 0.1%다. 입력-load
L1 request는 여전히 정확히 0이어야 한다. 0.1%는 output store, block당 SMID atomic, NCU
replay 배경을 허용하기 위한 상한이며, 0.2% 이상 synthetic control은 reject한다.

## A100 재실행 조건

| path | strict NCU coordinate | energy factor | NCU factor | acceptance |
|---|---:|---|---|---|
| Tensor | W_SM 2048 KiB, blocks/SM 16 | RF 1,2,4,8,16, treatment target 20 s/control floor 2 s의 max ITER를 두 mode에 동일 적용 | RF 1,2,4,8,16 | dual-calibration manifest, control elapsed>=1.6 s, treatment HMMA > 0, control HMMA=0, spill/local 0, pair ITER ratio=1 |
| Shared | W_SM 128 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | shared bytes/access 존재, bank conflict 낮음 |
| Global L1 | W_SM 16 KiB, blocks/SM 16 | LR 4,8,16 | LR 1,2,4,8,16 | path-specific L1 hit >=95%, L1 request/hit bytes 존재, L2 read/L1 request <=1% |
| L2 CG | W_SM 16,32,64,128 KiB, selected blocks/SM 16/8/4/2/1 | LR 4,8,16 | 각 W에서 LR 1,2,4,8,16 | source+LTC-fabric logical final hit>=95%, source/fabric sector 보존=1+/-2%, native-model 오차<=2 pp, observed source bytes/expected=0.95-1.05, L1 path hit<=1%, L1 hit/request<=1%, DRAM-read/source-read<=2% |
| External-memory read path (effective) | W_SM 2048,4096,8192 KiB, blocks/SM 16,32 | LR 4,8,16 | LR 1,4,8,16 | high-entropy input, `dram__bytes_read.sum`, final-service L2 hit <=10%, read/source >=90%, write/read <=1% |

Global L1 energy sweep의 W/B 목록은 Cartesian 조합을 전부 실행한다는 뜻이 아니다.
block당 최소 1 KiB tile 제약을 적용한 실제 좌표는 다음과 같다.

| Global L1 좌표 | 상태 | 용도 |
|---|---|---|
| W16/B16 | valid | strict NCU W16/B16과 일치하는 최종 우선 좌표 |
| W16/B32 | invalid, 자동 제외 | 0.5 KiB/block이므로 treatment와 control 모두 실행하지 않음 |
| W32/B16 | valid | working-set/block-density 보조점 |
| W32/B32 | valid | B32 diagnostic 보조점 |

따라서 리메디에이션 기준은 계속 **strict W16/B16**이다. B32는 W32와 결합할 때만
유효한 diagnostic이며 strict 좌표를 W16/B32로 바꾼 것이 아니다.

L2 후보의 full-GPU logical working set은 W16/32/64/128에서 각각 약
1.688/3.375/6.75/13.5 MiB다. 모두 40 MiB A100 L2보다 작지만 capacity만으로 L2 hit를
보장하지 않는다. `ld.global.cg`는 L2에 cache하고 L1에는 cache하지 않는 정책이지만 요청은
L1TEX를 통과한다. 따라서 `L1 request bytes ~= L2 read bytes` 자체는 실패가 아니다.
시간 측정 전 cache warm-up도 CG mode에서는 `global_cg_warmup_kernel`로 수행하여
normal `.ca` warm-up이 L1 residency를 만드는 혼입 경로를 제거했다.
실제 우회는 `L1 path hit <=1%`, `L1 hit bytes/request bytes <=1%`로 검증한다.
GA100 final service는 `(source hit + LTC-fabric hit)/source read >=95%`로 판정한다.
source와 fabric의 `(hit+miss)/read`가 각각 0.98-1.02이고, native read-hit와
source+fabric model 차이가 2 percentage points 이하여야 한다. `DRAM read bytes / L2 miss bytes`는 32-byte sector
miss가 더 큰 cache-line transaction을 만들 수 있어 1과 같을 필요는 없지만, 실제 miss가
downstream traffic과 함께 증가하는지를 판별하는 진단값으로 반드시 기록한다.

### NCU replay와 L2 residency 수정

이전 sidecar의 `--replay-mode kernel --cache-control none`은 kernel 입력은 replay할 수 있어도
application이 수행한 cache warm-up을 metric pass마다 다시 실행하지 않는다. cache를 flush하지
않는 설정까지 결합하면 pass별 cache 상태가 동일하다고 보장할 수 없다. 새 package는
`--replay-mode application --cache-control none`을 사용한다. 각 metric pass가 프로그램을
다시 시작하므로 binary 내부의 4회 CG warm-up도 매번 다시 수행된다.

새 package의 실행 순서는 다음과 같다. 후보 순서는 사전 고정하며 logical final-service
95% 기준을 낮춰 통과점을 만들지 않는다.

1. `normal/contiguous/B16,B8,B4,B2,B1`, W16/W128 KiB/SM, LR4를 NCU로 먼저 측정한다.
2. 실패하면 128-byte guard를 둔 block-private region을 virtual grid의 SM-slot/block-rank
   축으로 전치한 `normal/sm_interleaved` layout을 B16, B8, B4 순으로 검사한다.
3. 모든 normal 후보가 실패하면 `persisting/contiguous/B16,B8,B4,B1`과
   `persisting/sm_interleaved/B8,B4`를 검사해 residency 정책 효과를 분리한다.
4. persisting API/metric이 지원되지 않고 모든 normal 후보가 실패했다면 strict L2 결과 없이
   종료한다.
   blocks/SM 감소는 동시 block 주소의 set/slice 집중 여부를 진단하는 축이며 Tensor B16은
   변경하지 않는다.
5. 각 후보는 W16/W128의 treatment/control 네 행이 모두 L1 bypass, source/fabric
   logical final hit 95%, native-model coherence, sector 보존, DRAM-read/source-read,
   observed/expected traffic gate를 통과해야 선택된다.
6. 어떤 후보도 통과하지 못하면 coefficient를 계산하지 않고 종료한다.
7. 선택된 policy/layout/blocks-SM으로 L2 `l2_path_minimal` NCU를 실행하고 비-L2 full
   NCU와 row 단위로 merge한 뒤 precheck를 통과시킨
   뒤에만 같은 구성의 energy treatment/control을 실행한다.

persisting이 선택된 결과는 일반 L2 cache의 순수 회로 energy가 아니라
**residency-managed L2 effective path coefficient**다. persisting property도 절대 pinning
보장이 아니므로 logical final-service 95% gate를 완화하지 않는다. MIG에서는 persisting L2 set-aside가
비활성화될 수 있으며, 이때 모든 normal 후보도 실패하면 해당 환경에서 strict L2 결과가 없다는 것이
정직한 결론이다.

설계 근거는 NVIDIA의
[Nsight Compute Profiling Guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html),
[CUDA L2 Cache Control](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/l2-cache-control.html),
[Ampere Tuning Guide](https://docs.nvidia.com/cuda/ampere-tuning-guide/)를 따른다.

### 제기된 L2 가설별 판정

| 가설 | 코드/Counter 검토 | 현재 판정 |
|---|---|---|
| A100에서 `.cg`가 L1을 완전히 우회하지 못함 | PTX 정책상 L2 이하에 cache하며 요청은 L1TEX를 통과한다. 따라서 L1 request는 생기지만 global-load lookup hit는 별개다. RTX local CG target에서 path L1 hit 0%를 확인했다. | aggregate L1 traffic만으로 우회 실패라고 결론 낼 수 없음. A100 path-specific hit/miss로 재판정 |
| 같은 SM의 block/warp가 같은 cache line을 공유 | 기존 block 구간은 겹치지 않지만, `w_block_bytes`가 power-of-two이고 많은 block이 lockstep으로 같은 tile offset을 접근한다. 서로 다른 line이어도 L2 set/slice/partition에 반복 집중될 수 있다. | 동일 line 공유는 아니지만 address-topology conflict는 배제할 수 없다. `sm_interleaved`+128 B guard와 B16/8/4 비교로 진단 |
| `verify_smid` atomic/background가 L1/L2 counter에 혼입 | SMID 기록은 block당 atomic 1회다. aggregate L2에는 보일 수 있지만 path-specific L1 global-load lookup과 workload 규모 대비로 분리한다. control에서도 동일 bookkeeping을 실행한다. | aggregate counter 오염 가능성은 있음. source/fabric exact op-read lookup과 native model을 교차 사용 |
| 58.5-60.1% source hit가 실제 최종 L2 miss임 | 기존에는 source lookup hit/miss만 있어 다른 partition의 recovery를 보지 못했다. 사용자 보고 native 범위는 fabric forwarding 모델과 정합한다. | `srcunit_ltcfabric` hit/miss, logical final hit, native-model, DRAM read를 동시에 수집하기 전에는 실제 residency miss로 확정하지 않음 |
| normal warm-up이 L1 residency를 만듦 | 기존 warm-up은 일반 global load였다. 현재 CG mode는 `global_cg_warmup_kernel`로 교체했다. | 실제 설계 혼입 가능성이 있어 코드로 제거 완료 |
| persisting window가 실제 활성화됨 | 기존 runner는 selector가 요구하는 `launch__persisting_l2_cache_size`를 NCU 기본 metric 목록에 넣지 않았다. 따라서 persisting API 실행 여부와 별개로 counter 증거가 누락될 수 있었다. | metric 요청을 추가했다. target NCU에서 unavailable로 drop되면 persisting 후보는 승인하지 않고 dropped-metric 파일을 근거로 남김 |
| 60% 비율의 분모가 실제 workload traffic과 일치함 | 기존 gate는 hit ratio와 sector 보존성만 봤으며 논리적 expected byte와 observed L2 read byte의 크기를 직접 제한하지 않았다. | `active_SM * blocks/SM * ITER * LR * 1024 B`를 expected로 계산하고 observed/expected 0.95-1.05를 hard gate로 추가 |

## 실행

새 kernel/control 변경을 반영하려면 기존 A100 binary를 재사용하면 안 된다.

아래 2026-07-10 targeted package는 8-candidate/전체 L2 metric bundle을 사용한 당시의
재현용 진단이다. 현재 strict 결과에는 사용하지 않는다. 현재 표준 finalplan은 14개
후보에서 최대 56 precheck cases를 수행하고, 선택 후 L2 `l2_path_minimal` 40 cases와
비-L2 full 39 cases를 분리해 실행한다. 새 A100 측정은
`plan_platform_component_experiment.py`로 같은 날짜 tag의 표준 package를 다시 생성한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile a100 \
  --binary ./build-a100/a100_fp16_energy_v2 \
  --ncu "$(command -v ncu)" \
  --seconds 10 --repeats 5 --tag "$(date +%Y%m%d)"
```

상세 조건은
`results/summary/a100_tensor_l2_remediation_20260710_command_plan.md`를 따른다.
마지막 `a100_tensor_l2_remediation_<TAG>_audit.md`가 pass하기 전에는 수정 성공으로
간주하지 않는다. Targeted pass 후 전체 component summary가 필요하면 아래 표준 package를
다시 실행한다.

```bash
cmake -S . -B build-a100 -DCMAKE_CUDA_ARCHITECTURES=80
cmake --build build-a100 --clean-first -j
python3 scripts/run_component_regression_sweep.py --self-test
python3 scripts/plan_platform_component_experiment.py --target-profile a100 --tag $(date +%Y%m%d)
NCU_USE_SUDO=1 bash results/summary/a100_component_finalplan_$(date +%Y%m%d)_commands.sh
```

중단된 partial CSV에 이어 쓰지 않고 generated package 전체를 다시 실행한다. 시작 단계가
같은 tag의 stale raw/summary/NCU artifact를 `results/archive/..._stale_<timestamp>`로
옮기므로 treatment/control 반복 수와 실행 순서를 새 코드 기준으로 다시 맞출 수 있다.
추가로 package audit은 raw `notes`의
`tensor_pair_kernel_revision=matched_add_scalar_epilogue_fixed_rf_v2`과
`global_warmup_policy=ld_global_cg`를 확인한다. CSV header가 같더라도 marker가 없는
오래된 binary 결과는 승인하지 않는다.

이 script는 failure가 생겨도 `component_reliability_audit`, strict summary audit,
platform package audit, gap report를 계속 작성한다. `strict summary`가 없으면 audit에는
`summary_artifact_exists=fail`이 남으며, 이것은 coefficient가 final이 아니라는 뜻이다.

## 구현 검증 범위

| 검증 | 결과 | 한계 |
|---|---|---|
| 로컬 CUDA build | CUDA 13.2에서 sm_86/sm_80/sm_90 build 모두 성공. fixed-RF v2 sm_80 ptxas `reg_operand_only=22`, `reg_mma=26 registers/thread`, 둘 다 spill 0 | CUDA 13.2는 sm_70을 제거했으므로 V100은 target node CUDA 12.x build가 필요; A100/H100 runtime/clock/power는 대상 노드에서 재확인 |
| Tensor control NCU smoke | RTX 3090, RF4, ITER 100,000에서 control HMMA=0, treatment HMMA=524,800,000; NCU registers/thread=22/26 | GA100 HMMA count와 runtime register count는 A100 sidecar에서 다시 확인 필요 |
| Tensor HMMA/logical-MMA linearity run | RTX 3090 B16, ITER 100,000, application replay에서 RF1/2/4/8/16 treatment `HMMA/logical MMA=2`; 5개 control HMMA=0, local read/write=0, 10/10 acceptance pass | 새 denominator/linearity pipeline 검증이다. A100의 ratio가 반드시 2라는 뜻은 아니며, A100 내부 RF1-16 상대 spread<=10%를 요구 |
| GA100 spill counter 호환 | NCU 2026.1.1 GA100 catalog에는 `sass__inst_executed_register_spilling_*`가 없지만 `l1tex__t_bytes_pipe_lsu_mem_local_op_ld/st`는 지원한다. summarizer는 local bytes=0일 때만 spill 0을 추론하고 source를 기록한다 | A100 sidecar에서 local read/write bytes=0과 sm_80 ptxas spill 0을 함께 확인; local byte가 양수면 reject |
| Tensor pair energy smoke | 최종 scalar epilogue RTX 3090 RF4 1초 run에서 두 mode ITER=3,470,156, control/treatment elapsed=0.412/0.964 s, direct delta=48.57 J, analyzer valid | 단일 짧은 RTX B8 smoke이며 0.651 pJ/FLOP를 A100 또는 final 계수로 인용 금지 |
| 최신 Tensor RF sweep 구조 검증 | RTX 3090 B8, 2 s, 3 repeats에서 새 pair-lock 구현으로 RF1/2/4/8의 12/12 pair가 동일 ITER, `delta_E=101.1-160.6 J`, `0.778-1.400 pJ/FLOP`, pair 시작 간격 3.28-4.27 s로 모두 양수였다. RF16은 treatment가 약 1.97 s인 반면 control이 0.228-0.241 s에 끝나 idle 보정 `net_E=-0.68~-1.91 J`가 되어 analyzer가 세 pair를 생성하지 않았다 | 이 관측이 dual calibration을 추가한 직접 근거다. RF4 이후의 기존 음수 역전은 로컬에서 재현되지 않았지만 이 2 s smoke는 계수가 아니며, A100은 treatment 20 s/control 2 s floor/7 repeats로 RF1-16을 다시 판정 |
| Dual-calibration RF16 구조 검증 | RTX 3090 B8에서 treatment 2 s candidate ITER 1,777,089와 control 1 s floor candidate ITER 8,286,874 중 큰 값을 두 mode에 적용했다. 실제 control은 약 1 s, treatment는 약 9.4 s였고 3/3 pair가 `delta_E=626.9-685.3 J`, `0.880-0.962 pJ/FLOP`, 동일 ITER로 통과했다 | RF16 control noise-floor 누락을 제거하는 runner 동작 증거다. 긴 treatment와 RTX board-level coefficient는 비용/구조 검증용이며 A100 수치로 인용하지 않는다. A100 target에서는 20 s/2 s dual calibration과 7 repeats를 별도로 검증 |
| Fixed-RF v2 20초 energy run | RTX 3090 B16, RF1/2/4/8/16, 7 repeats, treatment 20 s/control 2 s floor. Power API 70/70 final candidate, pair timestamp/power-state filtering 후 33/35 valid, median 2.2525 pJ/FLOP, RF별 median 1.9754-2.3211 pJ/FLOP | 로컬 current-protocol Tensor evidence이지 A100 coefficient가 아니다. 기존 A100 0.35-0.54 v1은 새 kernel marker와 섞지 않아 재사용 금지 |
| Tensor pair policy | mock package에서 duration-scaled Tensor, ITER mismatch, 잘못된 candidate-max calibration, control duration floor 미달을 모두 reject | A100 clean rebuild 후 dual-calibration manifest, raw 동일 ITER, control elapsed>=1.6 s와 control HMMA=0 재확인 필요 |
| L2 counter 의미 | aggregate 71.5%이면서 path-specific L1=0%, L2=99%인 회귀 test는 accept; 실제 path L2=72%는 reject | A100에서 지원되는 정확한 metric alias와 새 NCU sidecar를 재수집해야 함 |
| CG warm-up/L2 로컬 smoke | 최신 sm_80 binary를 RTX 3090 W64/B8/LR4에서 NCU 2026.1.1로 확인. `L1 request bytes=268.698 GB`, `L2 read bytes=268.740 GB`로 aggregate traffic은 거의 같지만 L1 path hit=0%, L1 hit bytes=0, L2 read hit=99.9719%, acceptance pass | aggregate L1/L2 bytes 비율은 L1 hit 판정에 사용할 수 없다는 구현 증거다. A100 40 MiB L2/set mapping은 W16/32/64/128 sidecar로 재확인 필요 |
| application replay/persisting API smoke | RTX 3090 W16/B16/LR4, 5 application replay passes. manifest는 `application/none`, warm-up 4회, persisting을 기록. treatment L1 path hit=0%, derived/native L2 read hit=99.9977%/99.9542%, 차이 0.0435 pp, sector 보존비 1.0, persisting window=4,325,380 B로 acceptance pass | CUDA API, manifest, native/derived counter, summarizer, acceptance 연결 검증이다. RTX 3090 결과이므로 A100 58.5-60.1% 실패를 해결했다는 증거는 아니며 A100 policy/layout/B precheck가 필요 |
| Address-control NCU smoke | 같은 실행의 `global_addr_only`는 L1 input request=0, DRAM/expected path bytes=0.0506%였다. 0.1% bookkeeping/replay 상한에서 pass | target A100에서도 각 W/LR control이 input request=0이고 0.1% 이하인지 확인 필요 |
| 짧은 total-energy smoke | RTX에서 0.28-0.33 s의 control/treatment/L2 실행이 모두 동일한 9.759 J counter delta로 양자화되어 idle 보정 net energy가 음수 | 짧은 run은 coefficient 증거가 아니다. targeted package는 20 s와 `delta_E>=10 J`를 요구 |
| A100 finalplan dry-run | NCU selector가 고른 B 하나에서 W16/32/64/128 L2 energy 24 commands/repeat, L2 dual-calibration 12 coordinates/24 calibration commands, primary NCU 79 cases와 최대 56-case selector precheck 확인 | 실제 A100 cache hit/energy coefficient는 아직 재측정 전; selector가 두 anchor에서 통과하지 않으면 L2 energy 전에 종료하며 독립 non-L2 raw는 보존 |
| A100 L1 matrix regression | W16/B32의 `global_addr_only`, `global_l1_load_only`가 모두 `valid=false`; valid command는 W16/B16, W32/B16, W32/B32만 생성 | 실제 A100 energy 재실행은 target node에서 필요 |
| A100 L2 topology remediation | CUDA 13.2 sm_86 local build 성공. A100 dry-run에서 `sm_interleaved` W16/B4와 W128/B16 treatment/control이 유효하고 물리 stride에 128 B guard가 적용됨. selector/summarizer/acceptance/precheck/final-audit self-test 통과 | 실제 GA100의 set/slice mapping은 공개 세부가 제한적이므로 topology 가설은 A100 NCU 후보 결과로만 채택 또는 기각해야 함 |
| Binary pre-execution gate | unique valid 좌표를 energy 수집 전 `--dry-run`으로 검사 | 예상 밖 binary/profile 불일치는 partial 측정 전 controlled nonzero로 중단 |
| Pair adjacency gate | Tensor 및 Shared/L1/L2/DRAM의 알려진 2-mode pair를 command 단위가 아니라 pair 단위로 회전 | completion 차이를 시작 간격으로 오인하던 gate를 폐기. 새 raw는 exact epoch interval, legacy raw는 `run_id-elapsed_s` 추정으로 `pair_transition_gap_ms<=30000`; target A100 재분석/재실행 필요 |
| Targeted result audit | RF별 dual-calibration max ITER/control duration/HMMA/logical-MMA ratio/spill/delta와 W별 replay/residency/path hit/동일 L2 ITER/energy plateau를 `audit_a100_tensor_l2_remediation.py`가 검사 | synthetic pass, bad max policy, short control, RF4 negative, L2 ITER mismatch, L2 path 72% reject self-test 통과; 새 protocol의 실제 A100 artifact 필요 |

따라서 이번 변경은 기존 A100 수치를 final로 만드는 것이 아니라, 기존 run의 실패 원인을
제거한 재실행 가능한 strict design을 제공한다. 새 binary와 새 command package로 A100
energy sweep 및 NCU sidecar를 다시 실행한 뒤에만 coefficient를 보고한다.

control kernel과 차분 기준이 바뀌었으므로 기존 RF1/2의 0.14-0.30 pJ/FLOP도 그대로
보존하거나 새 RF4 이상 결과와 합치면 안 된다. A100에서는 RF1/2/4/8/16 전체를 새
binary, 동일 ITER policy, 동일 power/NCU gate로 다시 측정해야 한다.

## 보고 원칙

- 기존 A100 run의 shared scalar 1.008 pJ/bit는 해당 shared path evidence만 통과한
  provisional observation이다. Tensor/L1/L2 final coefficient와 함께 표에 넣지 않는다.
- `l2_load_only`의 결과는 L2 capacity diagnostic으로만 보고하며 L2-only coefficient로
  변환하지 않는다.
- 새 결과도 NVML board/device total-energy 차분과 NCU path evidence로 얻는 effective
  microbenchmark coefficient다. pure SRAM, Tensor Core, HBM circuit pJ/bit 값이 아니다.
