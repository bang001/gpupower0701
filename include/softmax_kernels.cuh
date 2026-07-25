#pragma once

#include <cstddef>
#include <cstdint>

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include "softmax_config.hpp"

namespace fp16softmax {

struct SoftmaxLaunchConfig {
  SoftmaxMode mode = SoftmaxMode::full;
  ExpImplementation exp_implementation = ExpImplementation::fp32_expf;
  CachePolicy cache_policy = CachePolicy::default_cache;
  int softmax_cols = 512;
  std::uint64_t grid_blocks = 1;
  std::uint64_t iters = 1;
  std::uint64_t row_tiles_per_block = 1;
  std::uint64_t tile_stride = 1;
  bool streaming = false;
  bool extra_exp_probe = false;
  const half* input = nullptr;
  half* output = nullptr;
  std::uint32_t* token_by_block = nullptr;
  int* smid_by_block = nullptr;
  int* sm_counts = nullptr;
  int sm_count_capacity = 0;
  cudaStream_t stream = nullptr;
};

cudaError_t launch_softmax_kernel(const SoftmaxLaunchConfig& cfg);
cudaError_t launch_softmax_init(half* input, std::size_t count, float logit_scale,
                                std::uint64_t seed, cudaStream_t stream);
int query_softmax_occupancy_max_blocks_per_sm(SoftmaxMode mode, int softmax_cols,
                                               CachePolicy cache_policy,
                                               ExpImplementation exp_implementation =
                                                   ExpImplementation::fp32_expf);
// Returns the architecture of the cubin selected for the exact kernel
// specialization (for example 80 for native sm_80).  An explicit target
// profile rejects a mismatched or PTX-JIT-only artifact.
int query_softmax_binary_version(SoftmaxMode mode, int softmax_cols,
                                 CachePolicy cache_policy,
                                 ExpImplementation exp_implementation =
                                     ExpImplementation::fp32_expf);

// Evaluate every 16-bit input encoding with both PTX forms.  The caller owns
// device buffers of `count` half values; count must be positive and even.
cudaError_t launch_native_ex2_validation(const half* input,
                                         half* scalar_output,
                                         half* packed_output,
                                         std::size_t count,
                                         cudaStream_t stream);

}  // namespace fp16softmax
