# NCU Cache Validation Summary

| label | mode | W_SM (KiB) | blocks/SM | Shared accesses | Shared bytes source | Shared bank conflicts | Shared inst | L1 hit (%) | L2 hit (%) | L1 accesses | L2 accesses (sectors) | DRAM accesses (sectors) | Shared bytes | L1 bytes | L2 bytes | DRAM bytes | Tensor HMMA inst | Long SB stall (%) | Short SB stall (%) | Wait stall (%) | Not selected stall (%) | Achieved occupancy (%) | Registers/thread | Static shared/block (bytes) | Dynamic shared/block (bytes) | status | notes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only | 32 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 7.48094e+06 |  | 0 | 0 | 2.3939e+08 |  | 0.00088 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only | 32 | 8 |  |  |  |  |  | 100 | 0 sectors | 0 | 1.87098e+06 |  | 0 | 0 | 5.98715e+07 |  | 0.003372 |  |  |  |  | 34 | 0 | 0 | ok | l2_native_derived_hit_rate_disagree |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only | 32 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 4.1512e+06 |  | 0 | 0 | 1.32838e+08 |  | 0.001684 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | 64 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 7.466e+06 |  | 0 | 0 | 2.38912e+08 |  | 0.000906 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 64 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 1.87699e+06 |  | 0 | 0 | 6.00636e+07 |  | 0.004258 |  |  |  |  | 34 | 0 | 0 | ok |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | 64 | 8 |  |  |  |  |  |  | 0 sectors | 0 | 3.85726e+06 |  | 0 | 0 | 1.23432e+08 |  | 0.00183 |  |  |  |  | 34 | 0 | 0 | ok |  |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only | 32 | 8 |  |  |  |  | 0 | 99.9998 | 3.35872e+10 sectors | 3.35874e+10 | 1.67528e+07 |  | 1.07479e+12 | 1.0748e+12 | 5.3609e+08 |  | 408.389 |  |  |  |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only | 32 | 8 |  |  |  |  | 0 | 99.9974 | 8.3968e+09 sectors | 8.3968e+09 | 4.2711e+06 |  | 2.68698e+11 | 2.68698e+11 | 1.36675e+08 |  | 365.312 |  |  |  |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only | 32 | 8 |  |  |  |  | 0 | 100 | 1.67936e+10 sectors | 1.67936e+10 | 8.36854e+06 |  | 5.37395e+11 | 5.37395e+11 | 2.67793e+08 |  | 393.448 |  |  |  |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 64 | 8 |  |  |  |  | 0 | 99.9995 | 3.35872e+10 sectors | 3.35874e+10 | 1.74218e+07 |  | 1.07479e+12 | 1.0748e+12 | 5.57497e+08 |  | 414.793 |  |  |  |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 64 | 8 |  |  |  |  | 0 | 99.998 | 8.3968e+09 sectors | 8.3968e+09 | 4.45763e+06 |  | 2.68698e+11 | 2.68698e+11 | 1.42644e+08 |  | 371.128 |  |  |  |  | 38 | 0 | 0 | ok |  |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 64 | 8 |  |  |  |  | 0 | 99.9992 | 1.67936e+10 sectors | 1.67938e+10 | 8.82135e+06 |  | 5.37395e+11 | 5.374e+11 | 2.82283e+08 |  | 398.778 |  |  |  |  | 38 | 0 | 0 | ok |  |

## L1/L2 Path-Specific Evidence

`L1 request bytes` are bytes presented to L1TEX; they are not L1 cache-hit bytes. For `.cg`, L1 requests are expected while L1 hit bytes/hit rate should remain near zero. L2 acceptance uses the device-aperture srcunit-TEX read hit/miss sectors when available, then falls back to all srcunit-TEX reads. The native op-read ratio aggregates a broader L2 read population and is a cross-check, not a replacement for the path-specific ratio. On GA100, a first-partition TEX miss can be recovered by an LTC-fabric hit in the other partition; the logical hit and native fabric-model columns preserve that distinction.

| label | mode | L1 path hit (%) | L1 aggregate hit (%) | L1 hit source | L1 request bytes | L1 hit bytes | L1 miss bytes | L2 derived read hit (%) | L2 native read hit (%) | Native-derived delta (pp) | L2 aggregate hit (%) | L2 hit source | L2 read hit sectors | L2 read miss sectors | L2 read sectors conservation | L2 miss bytes | DRAM read bytes | DRAM read/L2 miss ratio | L2 read bytes | expected L2 read bytes | observed/expected |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 20.2832 |  |  |  | 0 | 0 |  | 0 | 2.3939e+08 |  | 0 |  |  |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 | 100 | 26.7653 | 73.2347 |  | srcunit_tex_device_read_lookup_hit_miss | 82679 | 0 |  | 0 | 5.98715e+07 |  | 0 |  |  |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 19.46 |  |  |  | 0 | 0 |  | 0 | 1.32838e+08 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 21.1403 |  |  |  | 0 | 0 |  | 0 | 2.38912e+08 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 22.3728 |  |  |  | 0 | 0 |  | 0 | 6.00636e+07 |  | 0 |  |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only |  |  |  | 0 | 0 | 0 |  | 21.4147 |  |  |  | 0 | 0 |  | 0 | 1.23432e+08 |  | 0 |  |  |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 99.9998 | 99.9513 | 0.0484423 |  | srcunit_tex_device_read_lookup_hit_miss | 3.35871e+10 | 83524 | 0.999996 | 2.67277e+06 | 5.30971e+08 | 198.659 | 1.0748e+12 | 1.07479e+12 | 1 |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 99.9974 | 99.9484 | 0.0489787 |  | srcunit_tex_device_read_lookup_hit_miss | 8.39672e+09 | 218397 | 1.00002 | 6.94147e+06 | 1.36675e+08 | 19.6897 | 2.68698e+11 | 2.68698e+11 | 1 |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 100 | 99.95 | 0.04997 |  | srcunit_tex_device_read_lookup_hit_miss | 1.67936e+10 | 0 | 0.999998 | 0 | 2.67793e+08 |  | 5.37395e+11 | 5.37395e+11 | 1 |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 1.07479e+12 | 0 | 1.07479e+12 | 99.9995 | 99.9492 | 0.0503286 |  | srcunit_tex_device_read_lookup_hit_miss | 3.3587e+10 | 167068 | 0.999993 | 5.34618e+06 | 5.50518e+08 | 102.974 | 1.0748e+12 | 1.07479e+12 | 1 |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 2.68698e+11 | 0 | 2.68698e+11 | 99.998 | 99.9478 | 0.0502259 |  | srcunit_tex_device_read_lookup_hit_miss | 8.39673e+09 | 167108 | 1.00001 | 5.34746e+06 | 1.42007e+08 | 26.5559 | 2.68698e+11 | 2.68698e+11 | 1 |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 0 |  | global_load_lookup_hit_miss | 5.37395e+11 | 0 | 5.37395e+11 | 99.9992 | 99.9492 | 0.0499819 |  | srcunit_tex_device_read_lookup_hit_miss | 1.67935e+10 | 138892 | 0.999992 | 4.44454e+06 | 2.75734e+08 | 62.0388 | 5.374e+11 | 5.37395e+11 | 1.00001 |

## External-Memory Read Evidence

These counters validate traffic, not physical HBM/GDDR energy. Strict coefficients use `dram__bytes_read.sum`; total DRAM bytes are never the read-path denominator.

| label | mode | expected global read bytes | L2/source read bytes | source/expected | DRAM read bytes | read source | read/expected | DRAM write bytes | write source | write/read | DRAM read GB/s |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only |  | 0 |  | 2.3939e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.970763 |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only |  | 0 |  | 5.98715e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.920495 |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only |  | 0 |  | 1.32838e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 1.05809 |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only |  | 0 |  | 2.38912e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.970917 |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  | 0 |  | 6.00636e+07 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.924793 |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only |  | 0 |  | 1.23432e+08 | dram__bytes_read.sum |  | 0 | dram__bytes_write.sum | 0 | 0.98844 |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only | 1.07479e+12 | 1.0748e+12 | 1 | 5.30971e+08 | dram__bytes_read.sum | 0.000494022 | 5.11923e+06 | dram__bytes_write.sum | 0.00964127 | 0.993803 |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only | 2.68698e+11 | 2.68698e+11 | 1 | 1.36675e+08 | dram__bytes_read.sum | 0.000508659 | 0 | dram__bytes_write.sum | 0 | 1.00165 |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only | 5.37395e+11 | 5.37395e+11 | 1 | 2.67793e+08 | dram__bytes_read.sum | 0.000498317 | 0 | dram__bytes_write.sum | 0 | 0.999795 |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 1.07479e+12 | 1.0748e+12 | 1 | 5.50518e+08 | dram__bytes_read.sum | 0.00051221 | 6.97882e+06 | dram__bytes_write.sum | 0.0126768 | 1.02858 |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 2.68698e+11 | 2.68698e+11 | 1 | 1.42007e+08 | dram__bytes_read.sum | 0.000528499 | 637696 | dram__bytes_write.sum | 0.00449061 | 1.0477 |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 5.37395e+11 | 5.374e+11 | 1.00001 | 2.75734e+08 | dram__bytes_read.sum | 0.000513094 | 6.54886e+06 | dram__bytes_write.sum | 0.0237506 | 1.0284 |

## L2 Scope And Eviction Diagnostics

For GA100, `device-path hit` is the first partition lookup, while `logical hit` adds a matching LTC-fabric hit from the other partition. A direct/native disagreement is acceptable only when the explicit fabric counters reproduce the native ratio and DRAM read leakage remains low. This is a transaction model, not permission to relabel arbitrary L2 misses as hits.

| label | device-path hit (%) | all-TEX hit (%) | native op-read hit (%) | logical hit (%) | fabric hit (%) | model-native (%) | native-model delta (pp) | device read/hit/miss sectors | fabric read/hit/miss sectors | fabric/source-miss | fabric fraction | source/fabric/model coherent | DRAM-read/L2-read | eviction F/N/L (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W32_B8_LR16 |  |  | 20.2832 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l2_W32_B8_LR4 | 100 | 100 | 26.7653 |  |  |  |  | 0/82679/0 | // |  |  | // |  | // |
| global_addr_only_l2_W32_B8_LR8 |  |  | 19.46 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l2_W64_B8_LR16 |  |  | 21.1403 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l2_W64_B8_LR4 |  |  | 22.3728 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| global_addr_only_l2_W64_B8_LR8 |  |  | 21.4147 |  |  |  |  | 0/0/0 | // |  |  | // |  | // |
| l2_cg_load_only_W32_B8_LR16 | 99.9998 | 99.9998 | 99.9513 |  |  |  |  | 3.35874e+10/3.35871e+10/83524 | // |  |  | 1// | 0.00049402 | // |
| l2_cg_load_only_W32_B8_LR4 | 99.9974 | 99.9974 | 99.9484 |  |  |  |  | 8.3968e+09/8.39672e+09/216921 | // |  |  | 1// | 0.000508659 | // |
| l2_cg_load_only_W32_B8_LR8 | 100 | 100 | 99.95 |  |  |  |  | 1.67936e+10/1.67936e+10/0 | // |  |  | 1// | 0.000498317 | // |
| l2_cg_load_only_W64_B8_LR16 | 99.9995 | 99.9995 | 99.9492 |  |  |  |  | 3.35874e+10/3.3587e+10/167068 | // |  |  | 1// | 0.000512207 | // |
| l2_cg_load_only_W64_B8_LR4 | 99.998 | 99.998 | 99.9478 |  |  |  |  | 8.3968e+09/8.39673e+09/167108 | // |  |  | 1// | 0.000528499 | // |
| l2_cg_load_only_W64_B8_LR8 | 99.9992 | 99.9992 | 99.9492 |  |  |  |  | 1.67938e+10/1.67935e+10/138892 | // |  |  | 1// | 0.000513089 | // |

## Shared Read/Write Diagnostics

| label | mode | shared read bytes | shared write bytes |
|---|---|---:|---:|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only |  |  |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only |  |  |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only |  |  |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only |  |  |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only |  |  |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only |  |  |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only |  |  |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only |  |  |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only |  |  |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only |  |  |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only |  |  |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only |  |  |

## NCU Replay And Residency Policy

Application replay with cache-control none reruns the program warm-up before each metric pass. Persisting L2 rows additionally require an explicit CUDA access-policy window.

| label | mode | replay | cache control | metric profile | warm-up passes | L2 residency | L2 layout | persisting L2 size (bytes) | SASS inst | expected register ops | SASS/reg-op | HMMA inst | logical MMA | HMMA/logical MMA | FP16-to-FP32 Tensor ops | expected FLOP | ops/expected FLOP | Tensor pipe active (%) | achieved occupancy (%) | launch warp capacity (%) | registers/thread |
|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 34 |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | application | none | l2_path_minimal | 4 | normal | contiguous | 1.17965e+06 |  |  |  |  |  |  |  |  |  |  |  | 33.3333 | 38 |

## Spill And Local-Memory Evidence

Dedicated spill-instruction metrics are not available on every NCU/chip combination. `spill_zero_verified=1` means either the dedicated counters are zero or, for kernels with no intentional local-memory path, both local load/store byte counters are zero.

| label | mode | local read bytes | local write bytes | spill read inst | spill write inst | spill zero verified | evidence source |
|---|---|---:|---:|---:|---:|---:|---|
| global_addr_only_l2_W32_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W32_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W32_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR16 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR4 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| global_addr_only_l2_W64_B8_LR8 | global_addr_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W32_B8_LR16 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W32_B8_LR4 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W32_B8_LR8 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR16 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR4 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |
| l2_cg_load_only_W64_B8_LR8 | l2_cg_load_only | 0 | 0 | 0 | 0 | 1 | local_memory_bytes_zero_inference |

Access count unit: L1 prefers request counters when available; otherwise it falls back to sectors. L2 and DRAM access counts are sector counters. One sector is treated as 32 bytes when byte counters are unavailable. SB means scoreboard.
