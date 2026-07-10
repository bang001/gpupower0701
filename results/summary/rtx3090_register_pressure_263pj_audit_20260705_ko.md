# RTX 3090 Register Pressure 263 pJ/update Audit

작성 시점: 2026-07-05

## 결론

`reg_pressure` 256 B/block에서 나온 263 pJ/reg-update는 register-file access energy로 보면 안 된다. 값이 큰 이유는 register 자체가 비싸서가 아니라, 현재 계산이 3초 동안의 full-SM scalar integer dependency loop board energy를 작은 logical update count로 나누고 있기 때문이다.

따라서 이 값은 최종 component table에서 `register energy`로 쓰면 안 된다. 최대한 보수적으로 표현해도 `scalar register-pressure/control proxy` 또는 `upper/proxy coefficient`다.

## 현재 계산이 한 일

256 B/block 조건:

| item | value | unit |
|---|---:|---|
| active SM | 82 | SM |
| blocks/SM | 16 | blocks/SM |
| threads/block | 32 | threads |
| payload regs/thread | 2 | 32-bit registers |
| ITER | 27,861,047 | iterations |
| expected updates | 2.339e12 | updates |
| `reg_pressure` elapsed | 2.967 | s |
| `reg_pressure` net energy | 617.832 | J |
| same-ITER `empty` elapsed | 0.0545 | s |
| same-ITER `empty` net energy | 2.474 | J |
| paired delta | 615.358 | J |
| reported coefficient | 263.0 | pJ/update |

계산식 자체는 다음과 같다.

```text
updates = active_SM * blocks/SM * ITER * threads/block * payload_regs/thread
        = 82 * 16 * 27,861,047 * 32 * 2
        = 2.339e12

pJ/update = (617.832 J - 2.474 J) * 1e12 / 2.339e12
          = 263.0 pJ/update
```

문제는 분자가 register-file energy가 아니라는 점이다.

## 왜 너무 크게 나왔는가

| 원인 | 설명 |
|---|---|
| `empty` control 시간이 너무 짧음 | 같은 ITER의 `empty`는 0.054 s, `reg_pressure`는 2.967 s다. control이 fixed active power를 제거하지 못한다. |
| kernel이 register access만 하지 않음 | loop 내부는 multiply/add/xor/dependency update를 수행한다. 즉 integer ALU, scheduler, scoreboard, dependency stall이 포함된다. |
| payload 256 B/block은 분모가 작음 | 2 regs/thread만 update하므로 SM active power가 작은 denominator에 과도하게 실린다. |
| per-update 값이 payload 증가와 함께 감소 | 256B 263 pJ/update에서 8192B 135 pJ/update로 감소한다. 이는 fixed overhead amortization의 증거다. |
| NCU stall이 pure register 실험과 거리가 있음 | 256B NCU에서 wait stall 약 296%, not-selected 약 86%가 관측됐다. |

## 현재 데이터 재해석

payload별 direct division:

| payload (B/block) | regs/thread | power | update rate | direct pJ/update | NCU status |
|---:|---:|---:|---:|---:|---|
| 256 | 2 | 208.3 W | 7.89e11 update/s | 264.1 | accepted |
| 512 | 4 | 211.1 W | 1.07e12 update/s | 197.4 | not yet validated |
| 1024 | 8 | 210.8 W | 1.30e12 update/s | 161.7 | not yet validated |
| 2048 | 16 | 225.1 W | 1.47e12 update/s | 153.1 | not yet validated |
| 4096 | 32 | 216.0 W | 1.58e12 update/s | 137.1 | not yet validated |
| 8192 | 64 | 218.6 W | 1.60e12 update/s | 136.6 | rejected |

`P = intercept + beta * update_rate`로 보면 전체 payload slope는 약 14.5 pJ/update이고 intercept는 약 196 W다. 이 slope도 pure register energy가 아니다. 다만 263 pJ/update의 대부분이 fixed active/control power라는 점은 명확히 보여준다.

## 수정해야 할 해석

| 기존 표현 | 수정 표현 |
|---|---|
| Register pressure 256B/block = 263 pJ/reg-update | 사용 금지 또는 rejected-as-register-energy |
| register = 8.22 pJ/32-bit-update-bit | 사용 금지. physical RF bit energy가 아님 |
| register component result | 아직 미확정. 별도 설계 필요 |

## 개선 실험 설계

| priority | 개선 내용 | 이유 |
|---:|---|---|
| 1 | `reg_pressure`를 direct division이 아니라 power-rate slope로 분석 | fixed active power를 intercept로 분리 |
| 2 | payload 256/512/1024 B/block을 각각 NCU 검증 | accepted payload만 slope에 포함 |
| 3 | `reg_pressure_control` mode 추가 | 같은 duration/loop/control 구조에서 payload register update만 차분 |
| 4 | multiply-heavy update를 제거한 `reg_move_xor` 계열 추가 | integer MUL/IMAD energy가 register proxy에 섞이는 것을 줄임 |
| 5 | NCU scalar instruction counters 추가 | register update count가 아니라 실제 SASS integer instruction count로 normalization |
| 6 | repeats >= 3, seconds 5-10, randomized order | NVML board energy noise와 thermal drift 완화 |

## 최종 판단

263 pJ/reg-update는 너무 큰 값이라는 사용자의 판단이 맞다. 현재 결과는 register component energy로 채택하면 안 된다. 다음 iteration에서는 accepted payload sweep + intercept-aware power-rate regression + same-duration control을 구현한 뒤 register proxy를 다시 산출해야 한다.
