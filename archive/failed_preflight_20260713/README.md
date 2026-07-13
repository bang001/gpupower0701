# Failed Wrong-Platform Preflight Archive

이 디렉토리는 RTX 3090 로컬 환경에서 A100/V100 strict package를 시험하며 생성된
preflight 실패 보고서를 보존한다.

| Requested profile | 실제 검출 GPU | 판정 |
|---|---|---|
| A100 | RTX 3090 | profile, NCU, CUDA compiler gate 실패 |
| V100 32GB | RTX 3090 | profile, memory, NCU, CUDA compiler, binary dry-run gate 실패 |

이 파일들은 A100/V100 실행 증거가 아니다. strict preflight가 wrong-platform 실행을
차단했다는 진단 기록으로만 사용한다. 활성 `results/summary/`에 두면 target-node 결과로
오해할 수 있어 archive로 이동했다.
