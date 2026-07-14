# Memory Path Cross-Architecture Sweep Audit

검토일: 2026-07-14

## 1. 결론

Global L1, Shared, L2, external-memory 실험의 treatment-control 구조는 논리적으로
유효하다. 다만 이전 기본 package에는 **동일 좌표의 NCU treatment/control evidence가
없어 strict analyzer가 버리는 energy 좌표**가 많았다. 이 좌표는 실행시간만 늘리고 final
coefficient에는 기여하지 않았다.

현행 기본 package는 다음 원칙으로 수정했다.

1. Tensor는 utilization을 보기 위한 blocks/SM 세 점과 RF 1/2/4/8/16을 유지한다.
2. Memory path는 architecture별 blocks/SM 한 점만 사용한다.
3. Shared와 Global L1은 architecture anchor W 한 점만 사용한다.
4. L2는 plateau 확인용 W endpoint 두 점을 사용한다.
5. External-memory는 nominal L2보다 큰 low/mid/high W 세 점을 사용한다.
6. 모든 memory energy 좌표는 LR 4/8/16의 exact-coordinate NCU treatment/control을 갖는다.
7. A100과 H100의 L2는 source partition hit가 아니라 LTC-fabric recovery를 포함한 logical
   final service로 판정한다.
8. L2/streaming feasibility는 profile full SM이 아니라 실제 `active_SM * W_SM`으로 계산한다.

이 변경은 새 실험 계획을 교정한 것이다. 과거 coefficient를 자동으로 승인하거나
재계산하지 않는다.

## 2. 측정 대상과 차분

| Component/path | Treatment | Control | 차분에서 남기려는 것 | NCU 필수 증거 |
|---|---|---|---|---|
| Tensor MMA increment | `reg_mma` | `reg_operand_only` | no-MMA WMMA/register loop 위에 추가된 MMA path | treatment HMMA>0, control HMMA=0, spill/local=0, RF 선형성 |
| Shared scalar | `shared_scalar_load_only` | `shared_scalar_addr_only` | 동일 shared allocation/init/index loop 위의 repeated shared reads | shared read bytes/access, 낮은 bank conflict, global/L2/DRAM 오염 없음 |
| Global L1 hit | `global_l1_load_only` | `global_addr_only` | 동일 global address loop 위의 cached global load가 L1에서 끝나는 경로 | path L1 hit>=95%, L1 request/hit bytes, 낮은 L2/DRAM 누출 |
| L2 CG hit | `l2_cg_load_only` | `global_addr_only` | L1 data-cache를 우회한 global read가 L2에서 끝나는 경로 | L1 hit<=1%, final L2 service>=95%, expected L2 bytes, DRAM leakage<=2% |
| External-memory read | `dram_cg_load_only` | `global_addr_only` | L2보다 큰 streaming set의 GPU-device read completion path | direct DRAM read bytes, final L2 hit<=10%, write/read<=1%, traffic conservation |

모든 pair는 같은 W, blocks/SM, active SM, RF/LR와 **동일한 pair-locked ITER**를 사용한다.
분자는 treatment와 control의 idle-subtracted net energy 차이고, memory 분모는 NCU가 같은
좌표에서 측정한 actual bytes다.

### 2.1. 주소 순회와 byte 분모 자가점검

Memory treatment와 `global_addr_only` control은 모두 `load_index = ITER * LR + r`
형태로 동일한 index를 생성한다. 각 load event에서는 32 threads가 32-bit word를
8개씩 처리하므로 logical input은 `32 * 8 * 4 B = 1,024 B`다.

- L1/L2 mode는 `load_index % tiles_per_block`로 working set을 순차 순회한다.
- External-memory mode는 odd stride 1,315,423,911을 이용한 순열로 순회한다.
- 현행 W와 B가 2의 거듭제곱이므로 `tiles_per_block` 또한 2의 거듭제곱이다.
  홀수 stride는 modulo 공간에서 전체 tile을 한 번씩 방문하는 순열을 만든다.
- 따라서 LR 4/8/16은 동일 line을 LR번 고정 재사용하는 설정이 아니라, 한
  ITER 내에서 연속된 1 KiB tile 방문 수를 늘리는 설정이다.
- Treatment/control은 physical-block layout, tile index, streaming 선택, LR, ITER를
  공유한다. Control은 주소를 checksum에 소비하고 treatment만 global load를
  발행한다.

코드의 static expected bytes는
`active_SM * blocks/SM * ITER * LR * 1,024 B`다. 이 값은 트래픽 보존을
검사하는 기준이지 최종 coefficient의 분모가 아니다. 최종 pJ/bit는 같은
좌표의 NCU actual path bytes를 8배한 값으로 나눈다. NCU observed/expected ratio가
gate를 벗어나면 정적 계산이 맞더라도 reject다.

## 3. Shared와 Global L1을 별도로 보는 이유

두 경로는 일부 GPU에서 같은 unified L1/shared SRAM 용량을 공유할 수 있지만 같은
접근 경로가 아니다.

| 항목 | Shared scalar path | Global L1-hit path |
|---|---|---|
| CUDA address space | explicit shared | global |
| 명령/파이프 | shared load, shared bank/data path | global load, LSU/L1TEX tag/lookup/data path |
| 배치 | software가 shared allocation에 직접 배치 | hardware cache가 global line을 배치 |
| 주요 추가 비용 | shared address/bank routing | global address translation, tag lookup, cache request routing |
| strict denominator | NCU shared read bytes | NCU L1-hit bytes/request evidence |

따라서 두 coefficient가 같아야 한다는 전제는 성립하지 않는다. 같은 SRAM array 일부를
공유하더라도 instruction issue, address translation, tag lookup, banking, routing과 control
overhead가 다르다. 두 값은 각각 **effective access path coefficient**이며 SRAM bitcell의
순수 read energy가 아니다.

## 4. 아키텍처 경계

| Profile | SM | combined L1/shared | CUDA shared allocation | L2 | memory | strict memory B |
|---|---:|---:|---:|---:|---|---:|
| RTX 3090 / GA102 | 82 | 128 KiB/SM | 100 KiB/SM | 6 MiB | GDDR6X | 8 blocks/SM |
| V100 / GV100 | 80 | 128 KiB/SM | 96 KiB/SM | 6 MiB | HBM2 | 32 blocks/SM |
| A100 / GA100 | 108 | 192 KiB/SM | 164 KiB/SM | 40 MiB | HBM2 | 16 blocks/SM |
| H100 SXM5 / GH100 | 132 | 256 KiB/SM | 228 KiB/SM | 50 MiB | HBM3 | 16 blocks/SM |

H100 기본값은 SXM5 planning profile이다. H100 PCIe는 SM 수와 memory subsystem이
다르므로 별도 profile/result label이 필요하다. MIG/vGPU/reduced-SM에서는 runtime
`active_SM`을 사용해 full working set을 다시 계산한다.

근거 문서:

- [NVIDIA Ampere GA102 Architecture Whitepaper](https://www.nvidia.com/content/PDF/nvidia-ampere-ga-102-gpu-architecture-whitepaper-v2.pdf)
- [NVIDIA A100 Tensor Core GPU Architecture Whitepaper](https://images.nvidia.com/aem-dam/en-zz/Solutions/data-center/nvidia-ampere-architecture-whitepaper.pdf)
- [NVIDIA Tesla V100 GPU Architecture Whitepaper](https://images.nvidia.com/content/volta-architecture/pdf/volta-architecture-whitepaper.pdf)
- [NVIDIA H100 Tensor Core GPU Architecture](https://developer.nvidia.com/blog/?p=45555)
- [Nsight Compute Profiling Guide](https://docs.nvidia.com/nsight-compute/2025.3/ProfilingGuide/index.html)

## 5. 발견한 불필요 sweep

아래 수는 이전 기본 profile에서 1 repeat 기준 energy commands와 그중 strict analyzer가
exact-coordinate NCU로 사용할 수 있던 commands다. `제거`는 path가 틀렸다는 뜻이 아니라
**현재 final package에 대응 NCU가 없어 사용할 수 없던 좌표**라는 뜻이다.

| GPU | Path | 이전 energy | exact NCU 사용 가능 | 제거한 commands |
|---|---|---:|---:|---:|
| RTX 3090 | Shared / Global L1 / L2 / External | 24 / 18 / 12 / 48 | 6 / 6 / 6 / 24 | 18 / 12 / 6 / 24 |
| V100 | Shared / Global L1 / L2 / External | 36 / 36 / 12 / 72 | 6 / 6 / 12 / 24 | 30 / 30 / 0 / 48 |
| A100 | Shared / Global L1 / L2 / External | 24 / 18 / 24 / 36 | 6 / 9 / 24 / 18 | 18 / 9 / 0 / 18 |
| H100 | Shared / Global L1 / L2 / External | 24 / 18 / 24 / 36 | 6 / 6 / 6 / 18 | 18 / 12 / 18 / 18 |

과거 NCU의 LR1/LR2도 energy LR에 대응하지 않아 final coefficient에는 쓰이지 않았다.
현행 final NCU는 memory LR 4/8/16만 수집한다. L2 selector는 빠른 경로 선택을 위해 LR4
한 점만 probe하고, 선택 후 final NCU에서 LR4/8/16을 모두 다시 측정한다.

## 6. 현행 strict sweep

| GPU | Tensor B | Memory B | Shared W | Global L1 W | L2 W | External W | Memory LR |
|---|---|---|---:|---:|---:|---:|---|
| RTX 3090 | 4,8,16 | 8 | 64 | 8 | 32,64 | 256,512,2048 | 4,8,16 |
| V100 | 4,16,32 | 32 | 32 | 32 | 32,64 | 256,512,2048 | 4,8,16 |
| A100 | 4,16,32 | 16 | 128 | 16 | 16,128 | 2048,4096,8192 | 4,8,16 |
| H100 SXM5 | 4,16,32 | 16 | 128 | 16 | 64,128 | 2048,4096,8192 | 4,8,16 |

W 단위는 KiB/SM, B 단위는 blocks/SM, LR은 count다. Tensor W는 memory working set이
아니며 CLI placeholder 1 KiB만 사용한다.

| 실행량 | RTX 3090 | V100 | A100 | H100 |
|---|---:|---:|---:|---:|
| Tensor commands/1 repeat | 30 | 30 | 30 | 30 |
| Shared commands/1 repeat | 6 | 6 | 6 | 6 |
| Global L1 commands/1 repeat | 6 | 6 | 6 | 6 |
| L2 commands/1 repeat | 12 | 12 | 12 | 12 |
| External commands/1 repeat | 18 | 18 | 18 | 18 |
| 합계/1 repeat | 72 | 72 | 72 | 72 |
| raw rows at 5 repeats | 360 | 360 | 360 | 360 |
| final NCU cases | 73 | 73 | 73 | 73 |

L2 precheck는 별도다. 최대 case 수는 V100 16, A100 56, H100 24이며 첫 strict-pass
후보에서 종료한다. RTX 3090은 고정 B8을 사용한다.

## 7. 경로별 냉정한 판정

### Shared

동일 dynamic-shared allocation과 address loop를 가진 control을 사용하므로 구조가 맞다.
다만 bank conflict, compiler code shape, initialization traffic을 NCU로 확인하지 않으면
pure shared read로 승인할 수 없다.

### Global L1

normal cached global load와 address-only control의 차분은 타당하다. Warm-up과 L1 hit
95% 이상, 낮은 L2/DRAM leakage가 필수다. W가 작다는 이유만으로 L1이라고 판정하지 않는다.

### L2

`ld.global.cg`는 L1 data caching을 줄이지만 L1TEX request 자체를 없애지 않는다.
따라서 L1 request bytes가 존재하는 것은 정상이고 L1 hit bytes/rate가 낮아야 한다.
GA100/GH100은 partitioned L2이므로 first-partition direct hit만 95% gate로 쓰면 안 된다.
`source hit + ltcfabric hit`의 logical final service, source/fabric conservation, native-model
agreement와 DRAM leakage를 같은 minimal replay에서 검증한다. 필수 fabric metric이 없으면
L2 coefficient를 만들지 않는다.

### External memory

GPU global read가 L2를 물리적으로 건너뛸 수는 없다. 이 path는 큰 working set으로 L2
refill을 유도하고 direct `dram__bytes_read.sum`으로 실제 external traffic을 정규화한다.
결과는 memory device 자체의 pJ/bit가 아니라 controller, interconnect, cache refill,
scheduler와 board baseline을 포함한 GPU-device effective completion-path coefficient다.

## 8. 한계와 재실험 판정

- 두 L2 W endpoint에서 hit, bytes, coefficient plateau가 없으면 중간 W를 별도 discovery
  sweep으로 추가한다. threshold를 낮춰 final 값을 만들지 않는다.
- Shared/Global L1의 한 W anchor는 strict 기본값이다. min/max sensitivity가 필요하면 모든
  추가 W에 treatment/control exact NCU를 함께 생성해야 한다.
- Negative delta, mismatched ITER, missing control acceptance, missing direct traffic bytes는
  모두 reject다. 절댓값이나 non-negative fit으로 보정하지 않는다.
- Global input warm-up은 측정 구간 밖이지만, 현행 코드에서 address control은
  default-cached warm-up, L2/DRAM `.cg` treatment는 `.cg` warm-up을 사용한다. 두 경우
  모두 L2를 precondition하며 measured-kernel bytes는 NCU로 검증하지만, 온도나
  직전 cache state의 작은 비대칭을 완전히 제거했다고 볼 수는 없다. Pair 분산이
  크면 같은 cache operator를 쓰는 pair-specific warm-up을 추가한 후 재측정한다.
- 이 설계는 pure register, SRAM, HBM, PHY transistor-level energy를 직접 측정하지 않는다.
- 실제 coefficient는 새 target-node power API audit, power-state audit, NCU acceptance,
  reliability와 strict summary를 통과한 뒤에만 보고한다.
