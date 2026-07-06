# GPU data-movement energy 문헌값 감사

작성일: 2026-07-03

## 결론

사용자가 정리한 문헌값 중 일부는 산술 자체보다 **해석 레벨과 단위가 섞인 것**이
가장 큰 문제다. 특히 아래 세 종류를 한 표에서 직접 비교하면 안 된다.

| 구분 | 의미 | 예 |
|---|---|---|
| Device/circuit energy | HBM stack, SRAM array, wire 같은 회로/소자 관점 | Fine-Grained DRAM의 HBM2 pJ/bit, Horowitz SRAM/DRAM 표 |
| GPU hierarchy transaction path | GPU 내부 hierarchy에서 한 경로로 data가 이동하는 transaction 관점 | L1->RF, L2->L1, DRAM->L2 pJ/bit |
| Our effective coefficient | NVML board energy와 microbenchmark expected traffic으로 나눈 실측 계수 | RTX 3090 `shared_l1_increment`, `dram_streaming_path` |

따라서 최종 보고서에서는 같은 pJ/bit라도 반드시 다음 정보를 같이 적어야 한다.

| 필수 표기 | 이유 |
|---|---|
| GPU/공정/메모리 종류 | K40 GDDR5, RTX 3090 GDDR6X, A100/H100 HBM은 전력 경로가 다르다. |
| 계층 또는 경로 | HBM device access와 DRAM->L2 transaction은 같은 값이 아니다. |
| denominator | bit, byte, 32-bit word, 64-bit access, cache sector, transaction을 혼동하면 8x~64x 오류가 난다. |
| 포함 범위 | cache tag/data, interconnect, controller, register writeback, instruction/control/stall 포함 여부가 달라진다. |
| 측정/모델 방식 | circuit model, simulator model, NVML board-level regression은 서로 다른 근거다. |

## 항목별 감사

| 문헌/자료 | 사용자가 적은 값 | 감사 판단 | 보고서 사용 방식 |
|---|---:|---|---|
| Understanding the Future of Energy Efficiency in Multi-Module GPUs / GPUJoule | Shared->RF 5.32 pJ/bit, L1->RF 5.85 pJ/bit, L2->L1 15.48 pJ/bit, DRAM->L2 30.55 pJ/bit | 원문 표 확인 전에는 정확한 숫자 인용을 보류한다. 값의 크기는 GPU hierarchy transaction path로는 가능하지만, SRAM/HBM device energy처럼 쓰면 잘못이다. 특히 단위가 pJ/bit인지 pJ/word인지 반드시 원문 표에서 재확인해야 한다. | "K40 계층별 transaction-path reference"로만 사용. A100/H100 physical HBM energy 기준값으로 쓰지 않는다. |
| Fine-Grained DRAM | HBM2 full access 3.92-3.97 pJ/bit, activation 1.21 pJ/bit, 내부 movement 2.24 pJ/bit, I/O 0.3 pJ/bit | HBM2 device/access 관점으로 쓰는 것은 타당하다. 다만 activation energy를 pJ/bit로 쓸 때는 row/burst amortization denominator가 필요하다. 이 값은 SM register까지 도달하는 비용이 아니다. | "HBM device lower-level physical reference"로 사용. DRAM->L2 또는 SM load path와 직접 비교하지 않는다. |
| Architecting an Energy-Efficient DRAM System for GPUs | HBM column/datapath 1.5-5.7 pJ/bit | toggle-rate dependent column/datapath energy로 해석해야 한다. full HBM access energy 또는 GPU DRAM path energy로 쓰면 안 된다. | HBM 내부 datapath가 data pattern/toggle에 민감하다는 근거로 사용. |
| Benchmark-driven Models for Energy Analysis and Attribution of GPU-Accelerated Supercomputing | L1/L2/HBM pJ/bit, pJ/FLOP, pJ/Op | DOI는 확인됐지만 현재 접근 가능한 metadata만으로 표 값을 확인하지 못했다. 숫자는 원문 표/PDF 확인 전까지 인용 금지다. | 최신 methodology reference로 사용하고, 수치는 원문 확보 후 별도 표에 반영. |
| Computing's Energy Problem, Horowitz | 8KB SRAM 10 pJ/64b, 32KB SRAM 20 pJ/64b, 1MB SRAM 100 pJ/64b, DRAM 1.3-2.6 nJ/64b | 환산 산술은 맞다. 각각 0.156, 0.313, 1.563, 20.3-40.6 pJ/bit다. 하지만 45nm 기준의 일반 reference이므로 modern GPU cache path coefficient와 직접 비교하면 안 된다. | "data movement is expensive" 배경 근거. GPU별 실측 baseline으로 쓰지 않는다. |
| GPUWattch | GPGPU cycle-level power model | 직접 pJ/bit ground truth라기보다 modeling framework다. | 방법론/모델링 배경. |
| AccelWattch | Volta/Turing/Ampere power model | GPUWattch보다 현대 GPU에 가깝지만, 여전히 calibration/model framework다. | V100/RTX 3090/A100 분석 배경. |
| Analyzing GPU Energy Consumption in Data Movement and Storage | GPU data movement/storage energy model | 방향은 적합하지만 DOI/metadata 외 세부 수치는 확인 필요. | 관련 연구로 인용, 세부 숫자는 원문 확인 후 사용. |

## 가장 의심해야 하는 지점

### 1. GPUJoule 계열 값의 단위

`5.32`, `5.85`, `15.48`, `30.55`를 그대로 쓰려면 원문 표에서 다음을 확인해야 한다.

| 확인 질문 | 잘못되면 생기는 오류 |
|---|---|
| pJ/bit인가, pJ/byte인가, pJ/32-bit word인가? | 8x 또는 32x 오류 |
| transaction 하나가 몇 byte/sector를 의미하는가? | cache-sector 단위와 logical byte 단위가 불일치 |
| L1/shared data array만 포함하는가, tag/control/register writeback까지 포함하는가? | physical SRAM energy와 transaction energy 혼동 |
| K40 GDDR5 기준인가, HBM 가정 모델인가? | A100/H100 HBM 또는 RTX 3090 GDDR6X에 직접 전이하는 오류 |

### 2. HBM2 3.9 pJ/bit와 DRAM->L2 21.1 pJ/bit 비교

두 값은 같은 레벨이 아니다.

| 값 | 레벨 | 포함 가능 범위 |
|---:|---|---|
| 약 3.9 pJ/bit | HBM2 device/access | activation, sense/data movement, interposer I/O 등 HBM stack 내부 중심 |
| 약 21.1 pJ/bit | GPU DRAM->L2 path model | memory controller, link, cache-line transfer, system-level overhead 가능 |

따라서 `21.1 pJ/bit`가 `3.9 pJ/bit`보다 크다고 해서 모순은 아니다. 반대로
`3.9 pJ/bit`를 A100/H100에서 SM이 global load로 소비하는 전체 bit energy로 쓰면
과소평가가 된다.

### 3. Horowitz cache 값과 GPU L1/L2 path 값 비교

Horowitz의 `10 pJ / 64-bit = 0.156 pJ/bit` 같은 값은 회로/접근 primitive의
order-of-magnitude다. GPU에서 `L1->RF 5.85 pJ/bit` 같은 transaction-path 값과
비교하면 30배 이상 차이가 날 수 있다. 이것은 둘 중 하나가 반드시 틀렸다는 뜻이
아니라, denominator와 포함 범위가 다르다는 신호다.

### 4. 우리의 RTX 3090 결과와 문헌값 비교

현재 RTX 3090 결과는 다음처럼 제한해서 읽어야 한다.

| 항목 | 값 | 올바른 해석 |
|---|---:|---|
| Shared/L1 increment | 6.205 pJ/bit | NVML board energy 기반 effective microbenchmark coefficient |
| L2 increment over Shared/L1 | 1.348 pJ/bit | L2 추가분 후보. physical L2 SRAM bit energy가 아님 |
| DRAM increment over L2 | 21.180 pJ/bit | RTX 3090 GDDR6X streaming path effective increment 후보 |
| DRAM streaming cumulative path | 28.733 pJ/bit | path 전체 effective coefficient. HBM2 device 3.9 pJ/bit와 직접 비교 금지 |

이 값은 GPUJoule의 K40 transaction-path 값과 magnitude 비교는 가능하지만, HBM2
device 값 또는 Horowitz SRAM 값과 같은 표에서 "더 크다/작다"로 해석하면 안 된다.

## 보고서에서 사용할 안전한 문장

다음 표현은 사용할 수 있다.

> 문헌값은 회로/device energy, GPU hierarchy transaction energy, board-level
> effective coefficient가 섞여 있으므로 직접 비교하지 않고 계층과 denominator를
> 분리해 해석했다.

다음 표현은 피해야 한다.

> HBM2는 3.9 pJ/bit이므로 A100/H100의 DRAM load path도 3.9 pJ/bit에 가까워야 한다.

다음 표현도 피해야 한다.

> Horowitz의 8KB SRAM 0.156 pJ/bit보다 GPU L1 실측값이 크므로 실험이 틀렸다.

대신 이렇게 써야 한다.

> 본 실험값은 NVML board-level energy와 static traffic denominator에 기반한
> effective path coefficient이며, 순수 SRAM/HBM device energy와 다르다. NCU
> actual L1/L2/DRAM traffic과 stall percentage를 결합해야 물리 계층별 해석을
> 강화할 수 있다.

## 현재 필요한 후속 확인

| 우선순위 | 확인 항목 | 이유 |
|---:|---|---|
| 1 | GPUJoule/Multi-module GPU 원문 표의 단위와 transaction 정의 | `5.32`, `5.85`, `15.48`, `30.55`의 8x/32x 단위 오류 방지 |
| 2 | Fine-Grained DRAM HBM2 breakdown의 denominator | activation pJ/bit가 어떤 row/burst 기준으로 amortize됐는지 확인 |
| 3 | SC 2025 benchmark-driven model의 실제 table 값 | 최신 GPU 수치를 쓰려면 abstract/metadata가 아니라 원문 표가 필요 |
| 4 | 본 실험의 NCU actual traffic join | static expected byte를 actual L1/L2/DRAM byte로 보정 |

## 확인된 DOI

| 문헌 | DOI |
|---|---|
| Understanding the Future of Energy Efficiency in Multi-Module GPUs | https://doi.org/10.1109/HPCA.2019.00063 |
| Fine-grained DRAM | https://doi.org/10.1145/3123939.3124545 |
| Architecting an Energy-Efficient DRAM System for GPUs | https://doi.org/10.1109/HPCA.2017.58 |
| Computing's energy problem | https://doi.org/10.1109/ISSCC.2014.6757323 |
| GPUWattch | https://doi.org/10.1145/2485922.2485964 |
| AccelWattch | https://doi.org/10.1145/3466752.3480063 |
| Benchmark-driven Models for Energy Analysis and Attribution of GPU-Accelerated Supercomputing | https://doi.org/10.1145/3712285.3759815 |
| Analyzing GPU Energy Consumption in Data Movement and Storage | https://doi.org/10.1109/ASAP61560.2024.00038 |
