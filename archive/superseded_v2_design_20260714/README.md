# Superseded A100 V2 Design Archive

이 디렉토리는 초기 A100 FP16 v2 상세설계와 feasibility matrix/plot을 보존한다.

유효하게 남는 설계 기초:

- one warp/block, 32 threads/block
- logical FP16 `m16n16k16` operation
- 8192 FLOP/op와 A+B 8192 input bits/op
- blocks/SM 및 W_SM sweep의 초기 정의

현행 기준으로 사용하면 안 되는 부분:

- `shared_mma/l2_mma/dram_mma` 누적경로를 primary component로 해석하는 방식
- capacity와 W_SM만으로 L1/L2/DRAM 경로를 확정하는 방식
- 현재 treatment-control, matched-ITER L2/DRAM, exact NCU control acceptance와 package
  audit가 없는 실행 절차

현재 실행은 `docs/methodology/component_energy_final_experiment_plan_ko.md`와
`docs/platforms/cross_platform_component_experiment_guide_ko.md`를 따른다.
