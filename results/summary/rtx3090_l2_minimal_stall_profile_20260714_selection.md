# RTX3090 L2 Path Configuration Selection

Candidates are evaluated in command-line order using the minimal, counter-coherent L2 metric profile. The selector does not relax the 95% L2 hit gate; it changes blocks/SM, address topology, and then residency policy to isolate the source of the prior low-hit result.

Selected: policy=`normal`, layout=`contiguous`, blocks/SM=`8`.

| policy | layout | blocks/SM | W_SM (KiB/SM) | LR | metric profile | L1 hit (%) | L2 device/TEX/native hit (%) | native gate | delta (pp) | conservation | traffic/expected | DRAM-read/L2-read | DRAM-read/L2-miss | eviction F/N/L (%) | persisting bytes | selected | status | reason |
|---|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| normal | contiguous | 8 | 64 | 4 | l2_path_minimal | 0 | 99.9991/99.9991/99.9451 | required | 0.0539898 | 0.99998 | 1.00002 | 0.000567448075 | 64.7607 | // | 1.17965e+06 | yes | pass | pass |
