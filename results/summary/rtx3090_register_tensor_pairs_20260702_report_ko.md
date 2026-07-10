# RTX 3090 register/Tensor Core 분리 실험 결과

## 실험 목적

`reg_mma`에 포함된 Tensor Core MMA 추가 에너지를 더 좁게 보기 위해 `reg_operand_only` control을 함께 실행했다. `reg_operand_only`는 WMMA fragment를 만들고 operand 값을 읽지만 `mma_sync`는 수행하지 않으므로, `reg_mma - reg_operand_only` 차분을 register operand/control 대비 MMA 추가분 후보로 해석한다.

## 실험 조건

| 항목 | 값 | 단위/설명 |
|---|---:|---|
| GPU | RTX 3090 | target profile `rtx3090` |
| active SM | 82 | SM |
| W_SM | 32 | KiB/SM, register modes에서는 실제 register working set이 아니라 좌표 label |
| blocks/SM sweep | 1, 2, 4, 8, 16 | blocks/SM |
| reuse_factor sweep | 1, 2, 4, 8 | 내부 반복 배수 |
| modes | empty, reg_fragment_only, reg_operand_only, reg_mma | register/Tensor Core control set |
| repeats | 3 | 회/좌표/모드 |
| calibration | 1 | 회/좌표, `reg_mma` 기준 ITER 산정 |
| energy source | NVML total energy | board-level total energy counter |

## 파일 및 row 검증

| 파일 | row 수 | 의미 |
|---|---:|---|
| `results/raw/rtx3090_register_tensor_pairs_20260702.csv` | 240 | 원본 measurement rows |
| `results/raw/rtx3090_register_tensor_pairs_20260702_calibration.csv` | 20 | calibration rows |
| `results/raw/rtx3090_register_tensor_pairs_20260702_matrix.csv` | 80 | 실행 matrix rows |
| `results/summary/rtx3090_register_tensor_pairs_20260702_summary.csv` | 80 | pair summary rows |

| 점검 항목 | 결과 |
|---|---|
| mode별 row 수 | empty=60, reg_fragment_only=60, reg_operand_only=60, reg_mma=60 |
| 좌표 수 | 20개, 각 좌표 12행; 불완전 좌표=0개 |
| `smid_histogram_ok` | true=240 |
| energy source | nvml_total_energy=240 |
| NVML total energy supported | true=240 |
| power sample count | min=0, max=0; total energy counter 사용이라 0이 정상 |
| elapsed_s | min=0.183, max=13.745 s |

## NCU counter 재확인

대표 `reg_mma` 조건 1건으로 NCU profiling을 다시 시도했다. 커널 attach는 성공했지만 GPU performance counter 권한에서 `ERR_NVGPUCTRPERM`으로 차단됐다. 따라서 이번 결과에는 stall percentage, Speed of Light percentage, L1/L2 cache hit rate, L1/L2/DRAM access count가 포함되지 않는다.

## register footprint 정정

이 실험의 `W_SM=32 KiB`는 `reg_mma`의 register working set이 아니다. 현재 WMMA `reg_mma`의 실제 compiler-visible footprint는 ptxas 기준으로 `26 registers/thread * 32 threads/block * 4 B = 3,328 B/block`, 즉 약 `3.25 KiB/block`이다. `blocks/SM=16`에서는 약 `52 KiB/SM`이다. 이 값은 `W_SM`을 1 KiB나 256 B로 바꿔도 줄어들지 않는다.

따라서 이 결과는 “32 KiB register working set 실험”이 아니라 “ptxas 26 registers/thread, spill 0인 register-fed WMMA MMA 실험”으로 해석해야 한다. 더 작은 256 B 축은 Tensor Core WMMA `m16n16k16`에는 맞지 않고, 별도의 scalar/register pressure microbenchmark에서 다루는 것이 적절하다.

## 핵심 결과

- `reg_mma_minus_reg_operand`: n=20, median=0.364018 pJ/FLOP, min=-1.55229 pJ/FLOP, max=2.79147 pJ/FLOP
- `reg_mma_minus_empty`: n=20, median=2.6987 pJ/FLOP, min=1.69157 pJ/FLOP, max=7.7953 pJ/FLOP
- `reg_operand_minus_empty`: n=20, median=18373.8 pJ/reg-op, min=12355.1 pJ/reg-op, max=76498.7 pJ/reg-op
- `reg_fragment_minus_empty`: n=20, median=505.894 J, min=102.022 J, max=2451.62 J

### reg_mma - reg_operand_only

MMA 추가분 후보이다. 단위는 pJ/FLOP이다.

| blocks/SM (개/SM) | reuse=1 (pJ/FLOP) | reuse=2 (pJ/FLOP) | reuse=4 (pJ/FLOP) | reuse=8 (pJ/FLOP) |
|---:|---:|---:|---:|---:|
| 1 | -1.552 | 1.124 | 2.791 | 2.125 |
| 2 | -0.381 | 0.370 | 1.530 | 1.116 |
| 4 | -0.020 | 0.217 | 0.828 | 0.407 |
| 8 | 0.158 | 0.274 | 0.358 | 0.154 |
| 16 | 0.390 | 0.229 | 0.384 | 0.175 |

### reg_mma - empty

기존 방식의 register+operand+MMA 전체 차분이다. 단위는 pJ/FLOP이다.

| blocks/SM (개/SM) | reuse=1 (pJ/FLOP) | reuse=2 (pJ/FLOP) | reuse=4 (pJ/FLOP) | reuse=8 (pJ/FLOP) |
|---:|---:|---:|---:|---:|
| 1 | 7.786 | 7.795 | 6.226 | 4.958 |
| 2 | 4.782 | 4.383 | 3.707 | 2.976 |
| 4 | 3.070 | 2.810 | 2.401 | 1.916 |
| 8 | 2.346 | 2.571 | 1.931 | 1.692 |
| 16 | 2.365 | 2.587 | 1.977 | 1.715 |

### reg_operand_only - empty

MMA 없이 WMMA fragment operand/control 경로를 보는 기준 차분이다. 단위는 pJ/reg-op이다.

| blocks/SM (개/SM) | reuse=1 (pJ/reg-op) | reuse=2 (pJ/reg-op) | reuse=4 (pJ/reg-op) | reuse=8 (pJ/reg-op) |
|---:|---:|---:|---:|---:|
| 1 | 76498.7 | 54648.6 | 28136.8 | 23208.3 |
| 2 | 42292.8 | 32872.3 | 17836.1 | 15238.1 |
| 4 | 25307.4 | 21241.9 | 12883.8 | 12355.1 |
| 8 | 17927.2 | 18820.5 | 12883.8 | 12599.5 |
| 16 | 16178.6 | 19324.2 | 13051.3 | 12612.3 |

### reg_fragment_only - empty

fragment 생성/fill 중심 control 차분이다. denominator가 없어 단위는 J이다.

| blocks/SM (개/SM) | reuse=1 (J) | reuse=2 (J) | reuse=4 (J) | reuse=8 (J) |
|---:|---:|---:|---:|---:|
| 1 | 594.117 | 304.912 | 187.804 | 102.022 |
| 2 | 861.580 | 417.671 | 256.067 | 146.548 |
| 4 | 1386.399 | 632.994 | 392.126 | 217.623 |
| 8 | 2451.620 | 804.928 | 603.305 | 296.399 |
| 16 | 2283.640 | 834.343 | 631.721 | 296.827 |

## 해석

- `reg_mma - reg_operand_only` 중앙값은 0.364 pJ/FLOP이다. 그러나 blocks/SM=1, reuse=1과 blocks/SM=2, reuse=1에서 음수가 나와 저점유/저 reuse 조건은 차분 신호가 control overhead 및 NVML board-level 변동보다 작다고 보는 것이 타당하다.
- blocks/SM >= 8 조건에서는 `reg_mma - reg_operand_only`가 대체로 0.154-0.390 pJ/FLOP 범위에 있어 더 안정적이다. 이 범위를 RTX 3090 register-fed Tensor Core MMA 추가분 후보로 우선 검토할 수 있다.
- `reg_mma - empty`는 1.692-7.795 pJ/FLOP로 더 크다. 여기에는 fragment fill, operand handling, scheduler/control, MMA가 함께 포함되므로 Tensor Core만의 값으로 해석하면 과대 추정될 수 있다.
- `reg_operand_only - empty`는 reuse와 blocks/SM 증가에 따라 대체로 낮아진다. 이는 control/loop overhead가 정규화 denominator 대비 희석되는 효과가 포함된 것으로 보인다.

## 한계

- 이번 실행은 register/Tensor Core 분리 실험이다. shared/L1, L2, DRAM cache hit rate와 access count를 검증하는 NCU sidecar 실행은 GPU performance counter 권한 차단으로 완료하지 못했다.
- NVML total energy는 GPU board-level counter라 SM 내부 unit별 에너지를 직접 측정하지 않는다. 본 결과는 mode 차분을 이용한 유효 에너지 추정이다.
- `empty`와 control mode는 `reg_mma`보다 빨리 끝날 수 있다. 코드가 idle baseline을 elapsed time 기준으로 보정하지만, 짧은 실행에서 잔류 변동이 커질 수 있다.
- 음수 차분은 물리적 음의 에너지가 아니라 measurement/control mismatch 신호로 보고 해당 조건은 안정 구간 후보에서 제외해야 한다.

## 다음 확인

- 동일 구조를 A100/V100/H100에서 반복할 때는 각 GPU의 SM 수, NVML energy/power counter semantics, Tensor Core 지원 타입, NCU counter 지원 여부를 별도 기록한다.
- shared/L1, L2, DRAM 경로는 `scripts/run_ncu_validation.sh`의 cache/access summary와 component pair sweep을 별도로 실행해 이 register/Tensor Core 결과와 병합하는 방식이 적절하다.
