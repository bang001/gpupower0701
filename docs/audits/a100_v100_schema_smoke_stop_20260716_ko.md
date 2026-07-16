# A100/V100 schema smoke 중단 감사

작성일: 2026-07-16

## 결론

A100과 V100 모두 `schema_revision_smoke` 이후에서 멈춘 것은 같은
상위 단계에서 종료됐다는 뜻이지, 같은 근본 원인임을 증명하지
않는다. 기존 shell은 아래 세 작업을 하나의 stage로 표시했고
`set -e` 때문에 어느 명령이 nonzero를 반환했는지 명확히 남기지
않았다.

1. `clocked_empty`, `reg_operand_only`, `l2_cg_load_only` 최소 kernel 실행
2. schema/power API/revision marker audit
3. `cuobjdump` 기반 Tensor SASS audit

`schema_smoke.csv`만 보인다는 정보만으로는 위 세 경로 중 어느 것인지
확정할 수 없다. 다만 실제 energy sweep이 시작되지 않은 것은 현재
shell ordering과 `set -e` 동작에 부합한다.

## 도구 경로 판정

| 노드 | `nvcc` | `ncu` | 구조 판정 |
|---|---|---|---|
| A100 | `/usr/local/cuda-13.0/bin/nvcc` | `/usr/local/cuda-13.0/bin/ncu` | `sm_80` 빌드에 타당 |
| V100 | `/usr/local/cuda-12.4/bin/nvcc` | `/usr/local/cuda-12.4/bin/ncu` | `compute_70` 지원을 확인하면 `sm_70` 빌드에 타당 |

Compiler와 NCU는 올바른 조합이다. 하지만 기존 package는 Tensor
binary audit에서 선택한 `nvcc`와 동일한 toolkit의 `cuobjdump`를
명시적으로 전달하지 않았다. PATH에 다른 CUDA 버전의
`cuobjdump`가 있거나 Python 환경의 bundled tool이 먼저 선택되면
빌드 toolkit과 audit toolkit이 달라질 수 있었다.

## 수정 내용

| 수정 | 새 동작 |
|---|---|
| toolkit binding | `NVCC` 실행 파일과 같은 `bin/` 디렉터리의 `cuobjdump`를 우선 선택 |
| explicit override | `CUOBJDUMP=/absolute/path/cuobjdump` 지원 |
| stage split | kernel, power/schema audit, Tensor binary audit를 서로 다른 `PIPELINE_STAGE`로 표시 |
| checked command | 명령 전체, begin/pass/fail, return code를 로그에 표시 |
| global failure trap | smoke 이후를 포함한 모든 처리되지 않은 오류에서 stage, shell line, return code, command를 `PIPELINE_ABORT`로 표시 |
| power reject diagnostics | file, row, mode, reject reason을 stderr에 표시 |
| SASS reject diagnostics | mode, RF, symbol, static-audit reason을 stderr에 표시 |

Strict gate를 느슨하게 변경하지는 않았다. 오래된 binary에
`measurement_scope` 컬럼이 없거나 v6 marker가 없는 경우, 또는 실제
SASS에 HMMA/control runtime loop/spill 조건이 맞지 않는 경우에는 계속
중단되어야 한다.

## 새 로그 판독

| 마지막 stage/label | 의미 | 우선 확인 |
|---|---|---|
| `schema_smoke_kernel_execution` / `schema_*` | 해당 최소 kernel 실행 실패 | 직전 CUDA/NVML error와 `rc` |
| `schema_smoke_power_api_audit` / `schema_power_api_audit` | CSV schema, scope, semantics 또는 revision marker reject | `*_schema_smoke_power_api_audit.csv`의 `reasons` |
| `tensor_binary_static_audit` / `tensor_mma_binary_audit` | `cuobjdump` 실행 또는 Tensor SASS gate 실패 | `*_tensor_mma_binary_audit.csv`의 mode/RF/`reasons` |
| `tensor_energy_sweep` | smoke는 통과했고 실제 calibration/energy 문제 | `*_tensor_pair_calibration.csv` |

## 노드 재실행

각 노드에서 최신 `main`을 받고 기존 binary를 clean rebuild한다.
`src/`, `include/`, audit code가 변경됐으므로 기존 shell/process를 재개하지
않는다.

A100:

```bash
export NVCC=/usr/local/cuda-13.0/bin/nvcc
export CUOBJDUMP=/usr/local/cuda-13.0/bin/cuobjdump
export NCU_BIN=/usr/local/cuda-13.0/bin/ncu
cmake -S . -B build-a100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DCUDAToolkit_ROOT=/usr/local/cuda-13.0 \
  -DCMAKE_CUDA_ARCHITECTURES=80
cmake --build build-a100 --clean-first -j
```

V100:

```bash
export NVCC=/usr/local/cuda-12.4/bin/nvcc
export CUOBJDUMP=/usr/local/cuda-12.4/bin/cuobjdump
export NCU_BIN=/usr/local/cuda-12.4/bin/ncu
"$NVCC" --list-gpu-arch | grep -Fx compute_70
cmake -S . -B build-v100 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DCUDAToolkit_ROOT=/usr/local/cuda-12.4 \
  -DCMAKE_CUDA_ARCHITECTURES=70
cmake --build build-v100 --clean-first -j
```

재생성한 package는 이전 파일과 구분되는 tag를 사용한다.

```bash
set -o pipefail
TAG=20260716_schemafix
# A100은 PROFILE=a100/BUILD_DIR=build-a100,
# V100은 PROFILE=v100/BUILD_DIR=build-v100을 사용한다.
PROFILE=a100
BUILD_DIR=build-a100
python3 scripts/plan_platform_component_experiment.py \
  --target-profile "$PROFILE" \
  --binary "./${BUILD_DIR}/a100_fp16_energy_v2" \
  --ncu "$NCU_BIN" \
  --tag "$TAG"
bash "results/summary/${PROFILE}_component_finalplan_${TAG}_commands.sh" \
  2>&1 | tee "results/summary/${PROFILE}_component_finalplan_${TAG}_run.log"
```

## 추가 증거

새 package가 다시 중단되면 아래 세 가지면 근본 원인을
확정할 수 있다.

1. run log의 마지막 `PIPELINE_COMMAND_FAILED` 또는 `PIPELINE_ABORT` 행과 직전 30행
2. `*_schema_smoke_power_api_audit.csv` (있는 경우)
3. `*_tensor_mma_binary_audit.csv` (있는 경우)

새 정보 없이 두 노드의 근본 원인이 같다고 단정하지 않는다.
