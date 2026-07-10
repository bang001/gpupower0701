# V100 32GB Platform Review

작성일: 2026-07-10

## 결론

현재 V100 실행 package는 GV100/Volta의 SM, L1/shared, L2, FP16 WMMA, NVML
instantaneous-power semantics, `gv100` NCU counter path를 V100 기준으로 분리한다.
그러나 V100은 16 GB와 32 GB HBM2 SKU가 모두 존재하므로, architecture 이름과
compute capability만으로는 “V100 32GB 결과”를 보장할 수 없다. 이 변경부터 V100
reference package는 strict preflight에서 visible device memory가 `30,000 MiB` 이상인지
확인한다. 이 값은 32 GiB HBM2가 process에 거의 전체 보이는지 판별하기 위한 하한이며,
16 GB board나 작은 vGPU partition을 거부한다.

`30,000 MiB`는 capacity check일 뿐 performance/energy normalization 값이 아니다.
NVML이 보고하는 usable memory는 reservation/ECC/driver 상태로 nominal 32 GiB보다 작게
보일 수 있어, 32,768 MiB 동등 비교가 아니라 보수적 하한을 쓴다.

## 외부 사양과 코드 대조

NVIDIA V100 datasheet는 Volta, 640 Tensor Cores, 32 GB/16 GB HBM2, PCIe/SXM2
form factor를 명시한다. PCIe와 SXM2는 datasheet 상 메모리 bandwidth와 최대 board
power가 다르므로, coefficient를 두 form factor 사이의 물리 회로 상수로 합치면 안 된다.
NCU는 2024.3 계열에서 GV100을 지원하지만 최신 release에서는 Volta가 제외되므로,
실제 노드에서 `ncu --list-chips`와 `ncu --query-metrics --chips gv100`을 항상 실행한다.

| 검토 항목 | V100 32GB reference package 값 | 검토 결과 |
|---|---:|---|
| architecture / CUDA | GV100 / `sm_70`, CC 7.0 | profile과 binary preflight에 반영 |
| default visible SMs | 80 SMs | `--active-sm 80`; partition이면 runtime 값으로 plan 재생성 |
| L2 capacity | 6 MiB | L2 CG point: `80 x 64 KiB = 5 MiB` |
| shared allocation | 96 KiB/SM, 96 KiB/block | profile feasibility check에 반영 |
| blocks/SM | 16, 32 | Volta 32-block upper bound 안에서 sweep |
| HBM capacity | 32 GB HBM2 reference | strict preflight: visible `memory.total >= 30,000 MiB` |
| DRAM sanity working set | `80 x 8192 KiB = 640 MiB` | 6 MiB L2를 넘고 32 GB device capacity보다 작음 |
| power numerator | NVML total-energy delta only | `GetPowerUsage` instantaneous fallback은 final coefficient에서 제외 |
| NCU | `gv100` | availability와 counter acceptance는 target node에서 재확인 필요 |

## 32GB가 바꾸는 것과 바꾸지 않는 것

32 GB는 L1/shared, L2, register-file capacity를 바꾸지 않는다. 따라서 cache-path
working-set 좌표는 SKU capacity가 아니라 `SM count x W_SM`, L2 capacity, 그리고 NCU
hit/traffic evidence로 정한다. 이 package의 L2 5 MiB point와 DRAM 640 MiB point는
32 GB의 한계보다 충분히 작다.

반면 PCIe/SXM2 form factor, HBM clock, power limit, temperature, enabled SM count,
MPS/vGPU partition, driver/NVML total-energy availability는 board-level effective
coefficient에 영향을 준다. 따라서 V100 32 GB 결과에는 다음을 함께 기록해야 한다.

- `nvidia-smi`의 GPU name, `memory.total`, power limit, SM/memory clock, driver
- `target_profile=v100`, `sm_70` build, runtime `active_SM`
- total-energy support와 `measurement_scope=gpu_device_total_energy_counter`
- `gv100` NCU metric query, cache hit/access/byte/stall acceptance
- PCIe 또는 SXM2 form factor와 다른 GPU workload 부재

## 실행 원칙

기본 V100 32GB package를 생성하면 planner가 아래 memory gate를 포함한다.

```bash
python3 scripts/plan_platform_component_experiment.py \
  --target-profile v100 --tag "$(date +%Y%m%d)"
bash results/summary/v100_component_finalplan_"$(date +%Y%m%d)"_commands.sh
```

16 GB V100 또는 의도적으로 smaller partition을 시험할 때는 32GB 결과로 보고하지 않고,
별도 tag와 함께 `--min-device-memory-mib 0`으로 package를 생성한다. 이 경우 L1/L2
coordinate는 다시 계산하고 target node NCU evidence를 새로 수집해야 한다.

## 남은 한계

이 저장소에서는 V100 32 GB target node의 실제 NVML/NCU run을 수행하지 않았다. 따라서
이 문서는 static architecture/SKU audit과 실행 gate를 제공하지만, V100 32 GB component
coefficient를 승인하지는 않는다. final coefficient는 해당 node에서 power API audit,
NCU path acceptance, matched-control reliability, strict-summary audit가 모두 통과한 뒤에만
보고한다.

## References

- [NVIDIA V100 Data Sheet (Dec. 2019)](https://images.nvidia.com/content/technologies/volta/pdf/tesla-volta-v100-datasheet.pdf)
- [Nsight Compute 2024.3 GPU Support](https://archive.docs.nvidia.com/nsight-compute/2024.3/ReleaseNotes/topics/gpu-support.html)
