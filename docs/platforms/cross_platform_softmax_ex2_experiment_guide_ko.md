# Cross-platform Softmax EX2 실험 실행 가이드

작성일: 2026-07-27
대상: a100_fp16_softmax_energy의 Operand-rate ATC Softmax EXP2 실험
상태: RTX 3090 결과와 별개인 platform별 재현/확장 경로다. A100은 60-cell energy
수집을 실행할 수 있고, H100도 같은 energy 경로를 실행할 수 있으나 target SASS·NCU
증거 전에는 최종 비교 결과를 주장할 수 없다. V100의 native FP16 EXP2 두 구현은
의도적으로 skip한다.

> 범위 경계: 이 가이드는 `a100_fp16_softmax_energy`의 추가 EX2
> Operand-rate ATC probe만 다룬다. `a100_fp16_softmax_whole_precision_energy`의
> complete-Softmax stage isolation, `pJ/logical output element`, FP16
> reduction/normalization 정책에는 적용되지 않는다. 후자의 현재 검증 범위는 RTX
> 3090 sm86 한 좌표이며, 이 문서로 A100/V100/H100 지원 또는 결과를 주장하지 않는다.

## 1. 비교 대상과 분모

세 조건은 FP16 I/O·FP32 accumulation Softmax 안에서 exponent 경로만 바꾼다.
fp32는 **Tensor Core FP32가 아니라 scalar FP32 __expf baseline**이다.

| implementation | exponent 경로 | 비교에서의 의미 |
|---|---|---|
| fp32 | scalar FP32 __expf | FP32 exponent control/baseline |
| ptx_f16 | ex2.approx.f16 | native scalar FP16 EXP2 path |
| ptx_f16x2 | ex2.approx.f16x2 | native packed two-result FP16 EXP2 path |

공통 주 분모는 pJ/added logical scalar exponent result다. packed PTX 한 명령은 두
logical result를 만들므로 pJ/PTX-op을 공통 분모로 쓰지 않는다. 이 값은
whole-Softmax pJ/element, pure SFU/MUFU energy, 또는 Tensor Core energy가 아니라,
같은 Softmax kernel에서 extra EXP2 probe를 추가했을 때의
**algorithm-effective GPU board-energy increment**다.

native 두 구현은 sm_75+ runtime과 cubin을 모두 요구한다. 지원하지 않는 device에서
fallback 결과를 만들지 않도록 kernel은 native path에 hard failure를 두고 planner는
해당 행을 skipped로 남긴다.

## 2. 플랫폼 지원 및 skip 규칙

| profile | clean build / full-device gate | fp32 | native ptx_f16 / ptx_f16x2 | matrix 행 | 결과 지위 |
|---|---|---|---|---:|---|
| V100 / sm_70 / CC 7.0 | CUDA 12.x, 80 SM V100 | 실행 가능 | **skip**: native_ex2_requires_sm75 | FP32 20 + native skip 40 | FP32-only baseline, 3-way 비교 불가 |
| A100 / sm_80 / CC 8.0 | 108 SM full board, MIG/partition 제외 | 실행 가능 | 실행 가능 | 60 | energy candidate; native target-NCU가 있어야 final |
| H100 / sm_90 / CC 9.0 | 114-SM PCIe 또는 132-SM SXM full board, MIG/partition 제외 | 실행 가능 | 실행 가능 | 60 | **preliminary**; target SASS·NCU 전에는 final 불가 |

실행 가능 profile의 matrix는 다음과 같이 고정한다.

| 요인 | 수준 |
|---|---|
| implementation | fp32, ptx_f16, ptx_f16x2 (V100은 fp32만) |
| CTA grid (grid_blocks) | 16, 32, 48, 64 |
| Softmax S | 128, 256, 512, 1024, 2048 |
| threads/CTA | 256 |
| logit scale / cache | 4.0 / cache_reuse_candidate, default |

CTA 숫자는 **요청 grid의 block 수**다. resident CTA 수나 SM을 꽉 채운 occupancy의
측정값이 아니다. full-device gate는 board total-energy scope를 지키기 위한 것이고,
16–64 CTA는 의도적으로 incremental supply sweep이다.

V100을 CUDA 13 이상으로 build하면 sm_70 toolchain 지원 자체가 없으므로 fp32까지
포함한 V100 package 전체를 skipped: cuda_toolchain_lacks_sm70으로 기록한다.
CUDA 12.x에서 얻은 fp32 20개 cell도 native 40개 skip을 0 pJ로 채우거나
3-implementation 평균으로 표시하지 않는다.

## 3. clean build와 strict profile preflight

platform별 fatbin을 섞지 않는 clean build directory를 사용한다.
CMAKE_CUDA_ARCHITECTURES 기본값은 86이므로 target arch를 명시한다.

~~~bash
# PROFILE=v100|a100|h100, ARCH=70|80|90
# V100은 CUDA 12.x nvcc를 사용한다.
cmake -S . -B "build-$PROFILE" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES="$ARCH"
cmake --build "build-$PROFILE" --target a100_fp16_softmax_energy -j

BINARY="build-$PROFILE/a100_fp16_softmax_energy"
"$BINARY" \
  --gpu-id 0 --target-profile "$PROFILE" --mode full \
  --exp-impl fp32 --softmax-cols 128 \
  --grid-blocks 16 --blocks-per-sm 2 \
  --seconds 7 --idle-measure-seconds 1 \
  --cache-condition cache_reuse_candidate --cache-policy default \
  --logit-scale 4 --dry-run
~~~

dry-run은 GPU 이름/CC, loaded cubin (sm_70/sm_80/sm_90), full SM count를 함께
검증한다. A100/H100 runner는 UUID·PCI identity, MIG, competing CUDA process,
power/clock/thermal state도 batch 전·중·후에 검사하며 --skip-quiescence를 허용하지
않는다. 실패를 --target-profile auto로 우회하지 않는다.

Softmax ATC binary는 NVML GPU/device total-energy counter가 없으면 fail-closed로
중단한다. raw row의 nvml_total_energy_supported=true,
energy_source=nvml_total_energy, measurement_scope=gpu_device_total_energy_counter를
확인한다. GetPowerUsage 적분, H100 module power, GPU memory power로 바꿔서
cross-platform coefficient를 만들지 않는다.

V100은 이 preflight 뒤에도 ptx_f16/ptx_f16x2를 실행하지 않는다. direct binary
호출로 우회해도 native capability gate가 실패해야 정상이다.

## 4. 수치 및 static gate

energy run 전 A100/H100에서는 모든 S와 implementation에 대해 --validate-only를
통과시킨다. native 구현은 CPU FP64 Softmax 비교와 half encoding scalar/packed check를
함께 수행한다.

~~~bash
for IMPL in fp32 ptx_f16 ptx_f16x2; do
  "$BINARY" \
    --gpu-id 0 --target-profile a100 --mode full --exp-impl "$IMPL" \
    --softmax-cols 512 --grid-blocks 16 --blocks-per-sm 2 \
    --seconds 7 --idle-measure-seconds 1 \
    --cache-condition cache_reuse_candidate --cache-policy default \
    --logit-scale 4 --validate-only
done
~~~

A100 final-binary static gate는 각 S에서
scripts/audit_softmax_native_ex2_sass.py를 사용한다. 이 audit은 PTX/SASS
specialization set, native cubin, spill/local traffic, expected opcode structure를
함께 검사한다.

~~~bash
TAG="$(date +%Y%m%d)"
for S in 128 256 512 1024 2048; do
  python3 scripts/audit_softmax_native_ex2_sass.py \
    --binary "$BINARY" --cuobjdump "$(command -v cuobjdump)" \
    --softmax-cols "$S" --expected-cuda-arch 80 \
    --out "results/summary/a100_softmax_ex2_sass_s$S-$TAG.csv"
done
~~~

H100에서는 다음 **명시적 provisional static audit**만 허용한다.

~~~bash
for S in 128 256 512 1024 2048; do
  python3 scripts/audit_softmax_native_ex2_sass.py \
    --binary "$BINARY" --cuobjdump "$(command -v cuobjdump)" \
    --softmax-cols "$S" --expected-cuda-arch 90 \
    --allow-unestablished-sass-lowering \
    --out "results/summary/h100_softmax_ex2_sass_provisional_s$S-$TAG.csv"
done
~~~

이 opt-in은 sm_90 cubin, exact specialization, PTX native EXP2 presence와
spill/local gate를 확인하되, Hopper의 SASS lowering model이 아직 확정되지 않았음을
provisional_pass로 표시한다. allow flag 없이 H100 SASS audit은 fail-closed로
실패해야 정상이다. Ampere의 f16x2 → 두 scalar MUFU.EX2.F16 lowering을 Hopper에
가정하거나 provisional_pass를 final static gate로 승격해서는 안 된다.

V100은 native static audit 대상이 아니다. CUDA 12.x sm_70 fp32 binary를 쓸 수
있을 때에만 fp32 numerical validation을 수행한다.

## 5. 20-second preheat를 포함한 energy matrix

energy와 NCU replay는 분리한다. 아래 runner는 NVML total-energy delta로 energy
raw/trace/manifest를 만들며 NCU를 호출하지 않는다. 한 invocation은 한
implementation × S에 대해 4 CTA cell을 만든다. A100/H100은 15 invocation으로
60 cell을 수집한다. filename에 S가 자동으로 들어가지 않으므로 tag에 implementation과
S를 넣어 overwrite를 막는다.

권장 실행 경로는 새 planner가 만드는 command package다. 이 package는 20개의
`(S, CTA)` macroblock을 hash-ranked 순서로 배치하고, 각 macroblock 안의 implementation
순서를 strata-balanced하게 정한다. 각 cell은 독립 raw/trace/manifest/analysis 파일을
가지므로 중간 실패 뒤에도 어떤 cell이 실행·skip되었는지 명확하다.

~~~bash
# A100: 60 runnable cell
TAG="$(date +%Y%m%d)-a100"
python3 scripts/plan_softmax_cross_platform_ex2.py \
  --target-profile a100 --gpu-id 0 --tag "$TAG"
bash "results/summary/a100_softmax_cross_platform_ex2_${TAG}_commands.sh"

# H100: 같은 60 cell이 실행되지만 결과는 preliminary scope
TAG="$(date +%Y%m%d)-h100"
python3 scripts/plan_softmax_cross_platform_ex2.py \
  --target-profile h100 --gpu-id 0 --tag "$TAG"

# V100/CUDA 12.x: plan에 FP32 20 cell + native 40 explicit skip
TAG="$(date +%Y%m%d)-v100"
python3 scripts/plan_softmax_cross_platform_ex2.py \
  --target-profile v100 --cuda-major 12 --gpu-id 0 --tag "$TAG"
~~~

생성된 shell은 architecture별 build, S별 SASS audit, 20초 preheat, `counterbalanced6`
energy measurement, 그리고 cell별 analyzer를 순차 실행한다. V100 shell은 runtime
`nvcc --version`이 CUDA 13 이상이면 fallback 없이 전체 package를 skip한다. H100 shell은
SM90 SASS audit에 `--allow-unestablished-sass-lowering`를 명시하지만 final claim을
enable하지 않는다.

~~~bash
PROFILE=a100                    # h100으로 바꿔 같은 matrix를 실행 가능
BINARY="build-$PROFILE/a100_fp16_softmax_energy"
RUN_TAG="$(date +%Y%m%d)-$PROFILE-softmax-ex2"
OUT_DIR="results/raw/$RUN_TAG"

for IMPL in fp32 ptx_f16 ptx_f16x2; do
  for S in 128 256 512 1024 2048; do
    python3 scripts/run_softmax_operand_rate_atc.py \
      --binary "$BINARY" --gpu-id 0 --target-profile "$PROFILE" \
      --cross-platform-design --exp-impl "$IMPL" --softmax-cols "$S" \
      --grid-blocks-list 16,32,48,64 --blocks-per-sm 2 \
      --control-mode probe --execution-mode persistent_bracket \
      --pairs 6 --bracket-order counterbalanced6 --bracket-warmup-pairs 1 \
      --logit-scale 4 --conditions cache_reuse_candidate --cache-policy default \
      --preheat-seconds 20 \
      --preheat-actual-min-seconds 16 --preheat-actual-max-seconds 30 \
      --seconds 13 --energy-trace 1 --energy-trace-sample-ms 200 \
      --energy-trace-min-updates 16 \
      --tag "$RUN_TAG-$IMPL-s$S" --out-dir "$OUT_DIR"
  done
done
~~~

--cross-platform-design은 A100의 역사적 S=512, 27/54 CTA screen을
**대체하는 새 protocol revision**이다. historical A100 108-CTA confirm을 이
16–64 CTA sweep의 replicate로 취급하거나 두 결과를 pool하지 않는다.

20초 preheat는 standalone full-treatment board conditioning이며 raw ATC numerator에서
제외된다. 16–30 s는 실제 preheat kernel elapsed-time의 fail-closed gate일 뿐
thermal equilibrium의 증명은 아니다. sustained Softmax에서 온도 상승 자체는
허용하지만, throttle/DVFS, power-limit/clock state 변화, competing process, 또는
counter-trace update 부족은 measurement-valid row로 쓰지 않는다. 그런 경우
energy-trace-min-updates를 낮추지 말고 duration 또는 운영 환경을 재설계한다.

V100 fp32 baseline만 수집할 때에는 위 loop의 implementation 축을 fp32 하나로
고정한다. 계획 artifact에는 20 run cell과 native 40 skip cell을 모두 남긴다.

## 6. NCU와 final-claim gate

NCU replay 중 application-side energy/timing은 ATC numerator로 쓰지 않는다. NCU는
selected implementation과 exact CTA/S coordinate에서 dynamic path, denominator,
resource/placement를 검증한다.

| platform | final claim 전에 필요한 추가 증거 | 금지 사항 |
|---|---|---|
| A100 | ga100 target-node NCU metric query, native ptx_f16/ptx_f16x2 control–treatment capture, exact logical-result denominator audit | FP32 XU-only A100 resource sidecar를 native EX2 evidence로 전용 |
| H100 | gh100 metric discovery, native target control–treatment audit, Hopper-target final SASS lowering contract | RTX/A100 metric names·Ampere lowering·FP32 sidecar를 H100 native result에 복사 |

~~~bash
ncu --list-chips
ncu --query-metrics --chips ga100 > results/summary/a100_ncu_metric_inventory.txt
ncu --query-metrics --chips gh100 > results/summary/h100_ncu_metric_inventory.txt
~~~

scripts/audit_softmax_native_ex2_ncu.py는 RTX 3090 (sm_86) 전용이고,
run_softmax_a100_probe_ncu.py/audit_softmax_probe_ncu.py는 FP32 XU resource
sidecar다. 둘 다 H100 native EX2 auditor가 아니며 A100 native EX2의 final
dynamic denominator audit도 대신하지 않는다.

따라서 H100 energy row는 preliminary_pending_sm90_sass_and_native_ncu로 표시한다.
A100 native energy row도 target-native NCU가 없는 동안
candidate_pending_native_target_ncu로만 보고한다. static·numerical·environment·
energy trace·target NCU gate가 모두 통과한 동일 binary SHA/UUID/PCI/S/CTA/cache/scale
package만 platform별 final candidate가 된다.

## 7. 보관과 비교 규칙

각 profile × implementation × S batch에 clean-build log, binary SHA, cuobjdump/SASS
audit, numerical stdout, raw CSV, energy-trace CSV, manifest, preheat CSV, target NCU
capture/audit, report를 함께 보관한다. report에는 exact SKU, toolchain, units,
skipped/excluded cells와 result status를 명시한다.

서로 다른 platform, GPU UUID/PCI, binary SHA, implementation, S, CTA, cache condition,
logit scale을 join하거나 pool하지 않는다. 같은 PTX source나 numerical agreement는
physical SFU throughput/energy의 cross-SKU 동등성 증거가 아니다. V100 skip 행은
0 pJ observation이 아니며 H100 preliminary 행은 A100/RTX final row와 같은 ranking
table에 넣지 않는다.

RTX 3090의 검증된 matrix와 단위/해석은
[FP16 Softmax Operand-rate ATC 설계 및 검증 기록](../../fp16_softmax.md)을 따른다.
이 문서는 다른 GPU에서 안전하게 재현·확장하기 위한 실행 경로이며, target node에서
아직 실행하지 않은 A100/H100의 수치를 주장하지 않는다.
