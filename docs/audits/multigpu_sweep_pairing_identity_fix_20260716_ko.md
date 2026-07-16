# Multi-GPU / Sweep Pairing Identity 수정 감사

## 1. 판정

2026-07-16 A100 결과의 큰 `pair_transition_gap_ms`는 단순히 GPU가 느리거나
30,000 ms gate가 너무 짧아서 생긴 문제로만 볼 수 없다. 코드에서 다음 두 가지
실제 충돌 가능성이 확인됐다.

| 결함 | 기존 키 | 충돌 조건 | 영향 |
|---|---|---|---|
| power-state 조인 | `run_id` | 한 실행이 NVML-visible GPU별 행을 기록 | 마지막 inactive GPU 행이 active GPU 0 판정을 덮어쓸 수 있음 |
| treatment/control 그룹 | config 좌표만 | L1/L2/DRAM CSV에 같은 좌표의 `global_addr_only` 존재 | 다른 시간대, 다른 경로 sweep의 control을 nearest control로 선택할 수 있음 |

두 결함 모두 발생 가능한 구조였으며, 첫 번째는 멀티 GPU raw에서 동일 `run_id`가
GPU별로 반복된다는 관찰과 직접 일치한다.

## 2. `gpu_id`의 정확한 의미

`gpu_id`는 repeat/pass index가 아니라 물리 CUDA/NVML GPU index다. GPU 0만
실행한 4-GPU 노드에서도 harness는 보조 관찰을 위해 GPU 0,1,2,3 행을 같은
`run_id`로 쓸 수 있다.

| 열/marker | 의미 |
|---|---|
| `gpu_id=0,1,2,3` | 물리 CUDA/NVML device index |
| `n_gpu_active=1` | 이 run에서 실제 kernel을 실행한 GPU 수 |
| notes의 `gpu_active=1` | 해당 행의 GPU가 active |
| notes의 `gpu_active=0` | 해당 행의 GPU는 관찰만 한 inactive GPU |
| `smid_histogram_ok=false` on inactive row | 정상적으로 kernel 배치 증거가 없음; active row의 실패를 뜻하지 않음 |

## 3. 적용한 수정

1. `audit_power_state_stability.py` 출력에 `sweep_source_id`, `gpu_id`,
   `n_gpu_active`, `gpu_active`를 보존한다.
2. power-state 조인은 `(sweep_source_id, run_id, gpu_id)`만 사용한다.
3. 구형 audit처럼 `gpu_id`가 없거나 복합키가 중복되면 분석을 중단하고 audit
   재생성을 요구한다. 마지막 행 overwrite는 허용하지 않는다.
4. 에너지 `config_key`에 입력 raw CSV의 `sweep_source_id`를 포함한다.
5. NCU acceptance와 byte denominator의 exact key에도
   `tensor/shared/l1/l2/dram` sweep family를 포함한다.
6. matched detail에 `sweep_source_id`, `sweep_family`, `source_file`,
   `control_source_file`을 기록한다.
7. strict summary audit도 동일 복합키로 원본 power-state evidence를 검증한다.
8. binary, broad sweep, component sweep, paired stability runner, finalplan은 GPU가
   별도로 지정되지 않으면 GPU 0을 사용한다. 빈 `--gpu-ids`도 GPU 0으로 정규화한다.

## 4. 회귀 검증 기준

| test | 통과 조건 |
|---|---|
| multi-GPU audit | 같은 `run_id`의 GPU 0 `ok`, GPU 1 `reject`가 각각 유지됨 |
| duplicate identity | 같은 `(source, run_id, gpu_id)` 두 행을 overwrite하지 않고 실패 |
| legacy audit | `gpu_id` 없는 audit을 거부 |
| cross-sweep control | 시간상 다른 sweep control이 더 가까워도 같은 source의 control만 선택 |
| NCU family | 같은 좌표의 `global_addr_only_l1`과 `global_addr_only_dram` exact key가 다름 |
| default GPU | GPU option 생략/빈 값의 생성 command가 GPU 0을 사용 |

## 5. 기존 A100/V100 결과 처리

raw energy 5개 CSV와 NCU 결과 자체를 즉시 폐기할 필요는 없다. 다만 **기존
power-state audit, matched detail/summary, reliability, strict summary는 수정된 키로
재생성하기 전까지 provisional**이다. 먼저 기존 raw로 power-state audit을 다시 만든다.

```bash
PROFILE=a100
TAG=20260716
RAW="results/raw/${PROFILE}_component_finalplan_${TAG}"
SUMMARY="results/summary/${PROFILE}_component_finalplan_${TAG}"

python3 scripts/audit_power_state_stability.py \
  "${RAW}_tensor.csv" "${RAW}_shared.csv" "${RAW}_l1.csv" \
  "${RAW}_l2.csv" "${RAW}_dram.csv" \
  --out-csv "${SUMMARY}_power_state_audit.csv" \
  --out-md "${SUMMARY}_power_state_audit.md"
```

그 다음 기존 generated command의 `Matched-control analysis` 이후 명령을 다시
실행한다. 새 detail CSV에서 모든 행에 대해 다음 조건을 확인한다.

```text
sweep_source_id != ""
source_file == control_source_file
numerator/control gpu_id == requested GPU
pair_transition_gap_ms <= pair_transition_gap_limit_ms
```

수정 후 invalid row가 크게 줄면 기존 89초~2.1M ms gap은 조인/pairing 충돌의
영향이었다고 판정할 수 있다. 여전히 gap이 큰 행은 인접 control 자체가 power-state
reject였거나 실제 프로세스 간 지연이 컸던 별도 사례이므로 개별 로그를 확인한다.

## 6. 남는 한계

- `sweep_source_id`는 결과 bundle을 Linux와 Windows 사이에서 옮길 수 있도록 입력
  파일명으로 정의한다. 따라서 한 분석 호출에 basename이 같은 서로 다른 파일 두 개를
  넣으면 모호성을 허용하지 않고 실패한다.
- 이 수정은 잘못된 조인과 cross-sweep pairing을 제거한다. coefficient의 물리적
  타당성, NCU path acceptance, power 안정성을 자동으로 보증하지는 않는다.
- 다른 repeat의 control로 fallback할 수는 있지만, 동일 sweep/source 안에서만 가능하고
  transition-gap gate를 별도로 통과해야 한다.
