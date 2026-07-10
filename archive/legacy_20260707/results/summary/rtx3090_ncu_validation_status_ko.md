# RTX 3090 NCU 검증 상태

## 현재 상태

NCU 실행은 커널 attach까지 성공했지만 GPU performance counter 권한에서 차단됐다.

```text
ERR_NVGPUCTRPERM - The user does not have permission to access NVIDIA GPU Performance Counters
```

`sudo -n /home/bang001/miniforge3/envs/ssc21env/bin/ncu --version`은 성공했다. 하지만 같은 `sudo -n ncu`로 실제 커널 profiling을 실행하면 여전히 `ERR_NVGPUCTRPERM`이 발생했다.

확인된 환경:

- GPU: NVIDIA GeForce RTX 3090
- Windows driver: 591.86
- WSL GPU device: `/dev/dxg` 노출됨
- Linux식 `/dev/nvidia-caps`, `/proc/driver/nvidia-caps`, `/proc/driver/nvidia/params`: 현재 WSL 세션에서는 없음

따라서 현재 차단 지점은 Linux 계정의 sudo 권한이 아니라 Windows/WSL 드라이버 쪽 GPU Performance Counter 접근 설정이다.

따라서 이번 턴에서 실제 NCU stall percentage, Speed of Light percentage, memory throughput percentage는 수집하지 못했다.

## 정적 PTX 검증

`nvcc -arch=sm_86 --ptx src/kernels.cu`로 PTX를 생성해 확인했다.

확인된 패턴:

- `reg_mma_kernel`: `wmma.mma.sync.aligned...` 존재.
- `shared_mma_kernel`: `wmma.load.*.shared.f16` 뒤 `wmma.mma.sync...` 존재.
- `global_mma_kernel`: `wmma.load.*.global.f16` 뒤 `wmma.mma.sync...` 존재.
- PTX 전체에서 `mma.sync` 20회, `wmma` 53회 확인.

즉, 코드 경로 자체는 의도대로 Tensor Core WMMA와 shared/global operand load 경로를 생성한다. 다만 stall 비율과 실제 pipe utilization은 NCU performance counter 권한이 열려야 확정할 수 있다.

## 권한 해제 후 실행할 명령

대표 조건 NCU 검증 스크립트:

```bash
NCU='sudo -n /home/bang001/miniforge3/envs/ssc21env/bin/ncu' bash scripts/run_ncu_validation.sh
```

생성될 파일:

- `results/ncu/rtx3090_validation_20260701/*.ncu-rep`
- `results/ncu/rtx3090_validation_20260701/*_raw_metrics.csv`
- `results/ncu/rtx3090_validation_20260701/*_details.csv`

대표 조건:

| label | mode | W_SM | blocks/SM | kernel |
|---|---|---:|---:|---|
| empty_W64_B16 | empty | 64 KiB | 16 | empty_kernel |
| reg_mma_W2048_B4 | reg_mma | 2048 KiB | 4 | reg_mma_kernel |
| shared_mma_W64_B16 | shared_mma | 64 KiB | 16 | shared_mma_kernel |
| l2_mma_W64_B16 | l2_mma | 64 KiB | 16 | global_mma_kernel |
| dram_mma_W128_B16 | dram_mma | 128 KiB | 16 | global_mma_kernel |

## 봐야 할 항목

NCU 권한이 풀리면 다음을 확인한다.

- Tensor Core utilization: SpeedOfLight / tensor pipe percentage.
- Memory path sanity:
  - `shared_mma`: shared/L1 traffic이 주 경로인지.
  - `l2_mma`: L2 hit/traffic이 DRAM보다 우세한지.
  - `dram_mma`: DRAM throughput과 long scoreboard stall이 증가하는지.
- Stall:
  - `smsp__warp_issue_stalled_*` 계열 비율.
  - 특히 `long_scoreboard`, `short_scoreboard`, `barrier`, `not_selected`, `math_pipe_throttle`.
- Occupancy:
  - achieved occupancy와 theoretical occupancy.
  - `blocks/SM=16`에서 resident block 목표가 실제로 반영되는지.

## 권한 해결 방법

NVIDIA의 `ERR_NVGPUCTRPERM` 문서 기준으로 해결 방법은 둘 중 하나다.

1. NCU를 관리자/root 권한으로 실행.
2. 비관리자 사용자에게 GPU performance counter 접근을 허용.

Windows/WSL 환경에서는 NVIDIA App 또는 NVIDIA Control Panel에서 Developer 설정의 GPU Performance Counters 접근을 모든 사용자에게 허용해야 한다. 설정 변경 후에는 WSL 세션이 기존 드라이버 상태를 잡고 있을 수 있으므로 Windows에서 `wsl --shutdown` 후 WSL을 다시 열어 재시도한다. Linux driver 환경에서는 profiler capability 또는 `NVreg_RestrictProfilingToAdminUsers=0` 설정이 필요하다.
