#pragma once

#include <cstddef>
#include <cstdint>

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include "softmax_whole_precision_config.hpp"

namespace fp16softmax::whole_precision {

struct LaunchConfig {
  Policy policy = Policy::fp32_io_fp32_all;
  const half* input_f16 = nullptr;
  const float* input_f32 = nullptr;
  half* output_f16 = nullptr;
  float* output_f32 = nullptr;
  std::uint32_t* token_by_block = nullptr;
  int* smid_by_block = nullptr;
  int* sm_counts = nullptr;
  int sm_count_capacity = 0;
  std::uint64_t grid_blocks = 1;
  std::uint64_t iters = 1;
  cudaStream_t stream = nullptr;
};

cudaError_t launch_kernel(const LaunchConfig& config);
cudaError_t launch_init(half* input_f16, float* input_f32, std::size_t count,
                        float logit_scale, std::uint64_t seed,
                        cudaStream_t stream);
int query_occupancy_max_blocks_per_sm(Policy policy);
int query_binary_version(Policy policy);

}  // namespace fp16softmax::whole_precision
