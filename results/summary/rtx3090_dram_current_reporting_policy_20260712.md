# RTX 3090 DRAM Current Reporting Policy

작성일: 2026-07-12

| 항목 | 값 |
|---|---|
| 최신 보고 범위 | **26.709-28.409 pJ/bit** |
| 대표 midpoint | 27.559 pJ/bit |
| 상태 | `provisional_reference_aligned_range` |
| strict coefficient 포함 | 아니오 |
| 목표 treatment-control | `dram_cg_load_only - global_addr_only` |
| energy 차분 | 동일 ITER의 `net_E_treatment - net_E_control` |
| 분모 | exact-coordinate NCU `dram_bytes * 8` |
| 현재 raw evidence | 현행 matched-ITER pair가 저장소에 없음 |

이 범위는 RTX 3090 DRAM streaming **cumulative effective path**를 보고하기 위한
최신 provisional band다. 순수 GDDR6X 소자 에너지가 아니며, 현행 protocol을 통과한
실측 coefficient도 아니다. 따라서 표와 그림에는 범위 및 provisional 상태를 함께
표기해야 한다.

과거 `dram_cg_load_only - clocked_empty` 결과는 약 28.3 pJ/byte였고, 이를 bit 단위로
환산하면 약 3.54 pJ/bit였다. 산술 환산 자체는 맞지만 control과 work-lock 정책이
현행 설계와 다르므로 최신 DRAM coefficient로 재사용하지 않는다. 과거 raw/summary는
재현성과 provenance를 위해 수정하지 않는다.

최종값으로 승격하려면 다음 조건을 모두 만족해야 한다.

1. treatment와 `global_addr_only` control의 `ITER`가 동일하다.
2. 두 row가 `nvml_total_energy`, `total_energy_mj_delta`, explicit GPU/device scope를 사용한다.
3. exact-coordinate NCU에서 DRAM-dominant path와 `dram_bytes > 0`이 확인된다.
4. coefficient를 `delta_E * 1e12 / (dram_bytes * 8)`로 계산한다.
5. power-state, NCU acceptance, reliability, strict/package audit이 모두 통과한다.
6. accepted 결과가 생성되면 provisional band를 실측 median/CI로 교체한다.
