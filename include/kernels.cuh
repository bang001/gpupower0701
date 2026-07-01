#pragma once

#include <cstddef>
#include <cstdint>

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include "config.hpp"

namespace a100fp16 {

struct KernelLaunchConfig {
  Mode mode = Mode::empty;
  int active_sm = kDefaultHardwareProfile.full_sm_count;
  int blocks_per_sm = 1;
  std::uint64_t w_block_bytes = kLogicalMmaInputBytes;
  std::uint64_t tiles_per_block = 1;
  std::uint64_t iters = 1;
  half* input = nullptr;
  float* output = nullptr;
  int* smid_by_block = nullptr;
  int* rank_by_block = nullptr;
  int* sm_counts = nullptr;
  int sm_count_capacity = 0;
  cudaStream_t stream = nullptr;
};

cudaError_t configure_kernel_attributes(Mode mode, std::size_t dynamic_smem_bytes);
cudaError_t launch_init_half(half* input, std::size_t half_count,
                             std::uint64_t seed, cudaStream_t stream);
cudaError_t launch_global_warmup(const half* input, std::size_t half_count,
                                 float* output, cudaStream_t stream);
cudaError_t launch_benchmark_kernel(const KernelLaunchConfig& cfg);

}  // namespace a100fp16
