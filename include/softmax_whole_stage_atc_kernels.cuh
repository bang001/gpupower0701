#pragma once

#include <cstddef>
#include <cstdint>

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include "softmax_whole_stage_atc_config.hpp"

namespace fp16softmax::whole_stage_atc {

struct LaunchConfig {
  Stage stage = Stage::exp;
  Policy policy = Policy::fp32;
  const half* input_f16 = nullptr;
  const float* input_f32 = nullptr;
  half* output_f16 = nullptr;
  float* output_f32 = nullptr;
  std::uint32_t* sink_by_thread = nullptr;
  int* smid_by_block = nullptr;
  std::uint64_t grid_blocks = 1;
  std::uint64_t iters = 1;
  int softmax_cols = 512;
  // Zero is control; one is treatment.  This is a kernel argument, not a
  // template parameter, so both roles launch exactly the same kernel symbol.
  int extra_stage_pass = 0;
  cudaStream_t stream = nullptr;
};

cudaError_t launch_kernel(const LaunchConfig& config);
cudaError_t launch_init(half* input_f16, float* input_f32, std::size_t count,
                        float logit_scale, std::uint64_t seed,
                        cudaStream_t stream);
int query_occupancy_max_blocks_per_sm(Stage stage, Policy policy,
                                      int softmax_cols);
int query_binary_version(Stage stage, Policy policy, int softmax_cols);
int query_registers_per_thread(Stage stage, Policy policy, int softmax_cols);
std::size_t query_static_shared_bytes(Stage stage, Policy policy,
                                      int softmax_cols);
std::uintptr_t query_kernel_symbol_address(Stage stage, Policy policy,
                                           int softmax_cols);

}  // namespace fp16softmax::whole_stage_atc
