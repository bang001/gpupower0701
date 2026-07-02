# RTX 3090 Sweep 1 결과 요약 (blocks/SM sweep)

## 실험 범위

- GPU: RTX 3090 (`profile_name=rtx3090`, GA102, SM=82, L2=6 MiB, compute capability 8.6)
- Sweep 축: `blocks_per_SM = 1, 2, 4, 8, 16`
- 반복: 각 조건 5회
- 측정 시간: 각 실행 약 10초
- 에너지 소스: NVML total energy delta (`energy_source=nvml_total_energy`)
- 원시 결과: `results/raw/rtx3090_sweep1_blocks_fixedw_20260702.csv`
- 요약 CSV: `results/summary/rtx3090_sweep1_blocks_fixedw_20260702_summary.csv`

## 고정 working set 설정

| mode | W_SM (KiB) | 설정 의미 |
|---|---:|---|
| `reg_mma` | 32 | register-fragment MMA 경로의 대표 좌표이다. 실제 shared/L2/DRAM working set을 의미하지 않는다. |
| `shared_mma` | 64 | RTX 3090의 per-SM shared memory 용량 안에 들어가도록 잡은 shared-resident 조건이다. |
| `l2_mma` | 64 | full-GPU working set이 L2 후보 범위 안에 들어가는 조건이다. |
| `dram_mma` | 8192 | full-GPU working set이 L2를 크게 초과하도록 만든 DRAM-dominant 조건이다. |

주의: RTX 3090에서는 이 커널/자원 조건에서 `blocks_per_SM=32`는 유효하지 않아 제외했다.

## 검증 요약

- 원시 측정 행 수: 100개
- 조건 수: 20개
- 각 조건 반복 5회 충족: True
- 모든 행 `smid_histogram_ok=true`: True
- 최대 온도: 84 C

## 중앙값 pJ/FLOP

| mode | W_SM (KiB) | B=1 | B=2 | B=4 | B=8 | B=16 |
|---|---:|---:|---:|---:|---:|---:|
| `reg_mma` | 32 | 7.843 | 4.537 | 3.169 | 2.460 | 2.539 |
| `shared_mma` | 64 | 28.512 | 17.764 | 12.281 | 9.938 | 6.713 |
| `l2_mma` | 64 | 36.908 | 24.069 | 14.739 | 13.314 | 9.194 |
| `dram_mma` | 8192 | 111.449 | 78.365 | 57.406 | 39.133 | 36.567 |

단위: pJ/FLOP.

## 중앙값 net energy

| mode | W_SM (KiB) | B=1 | B=2 | B=4 | B=8 | B=16 |
|---|---:|---:|---:|---:|---:|---:|
| `reg_mma` | 32 | 776.728 | 995.585 | 1386.945 | 1906.424 | 1719.307 |
| `shared_mma` | 64 | 835.204 | 1040.047 | 1449.228 | 2143.310 | 2239.434 |
| `l2_mma` | 64 | 857.140 | 1113.961 | 1393.212 | 1944.072 | 2351.323 |
| `dram_mma` | 8192 | 1156.088 | 1589.341 | 2303.676 | 2576.553 | 2592.307 |

단위: J.

## 중앙값 elapsed time

| mode | W_SM (KiB) | B=1 | B=2 | B=4 | B=8 | B=16 |
|---|---:|---:|---:|---:|---:|---:|
| `reg_mma` | 32 | 9.692 | 10.879 | 10.939 | 11.185 | 10.509 |
| `shared_mma` | 64 | 10.972 | 10.960 | 11.207 | 11.000 | 11.291 |
| `l2_mma` | 64 | 10.826 | 10.793 | 11.101 | 11.131 | 11.265 |
| `dram_mma` | 8192 | 10.971 | 10.998 | 11.156 | 10.997 | 10.899 |

단위: s.

## 해석 메모

- 이번 결과는 에너지 sweep 결과이며, cache hit rate와 L1/L2/DRAM access count는 NCU 프로파일링으로 별도 검증해야 한다.
- `dram_mma`는 의도적으로 `W_SM=8192 KiB`를 사용해 full-GPU working set이 RTX 3090 L2 6 MiB를 크게 초과하도록 구성했다.
- `blocks/SM` sweep은 resident block 수, scheduling pressure, memory pressure가 함께 바뀌므로 결과를 단일 원인으로만 해석하면 안 된다.
- `reg_mma`의 `W_SM=32 KiB`는 표 정렬을 위한 대표 좌표이며 register fragment MMA 자체의 물리적 working set으로 해석하면 안 된다.

## NCU 검증 상태

- NCU 대표 검증은 `B=16`, `DRAM_W_SM_KIB_OVERRIDE=8192` 조건으로 시도했다.
- NCU는 대상 CUDA 프로세스에 연결됐지만 `ERR_NVGPUCTRPERM`으로 GPU performance counter 접근이 거부되어 cache hit rate와 L1/L2/DRAM access count를 수집하지 못했다.
- 따라서 이 보고서의 수치는 NVML 에너지 sweep 결과이며, NCU counter 기반 경로 검증은 NVIDIA performance counter 권한이 열린 뒤 재실행해야 한다.
