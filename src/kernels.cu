#include "kernels.cuh"

#include <mma.h>

namespace a100fp16 {
namespace {

using nvcuda::wmma::accumulator;
using nvcuda::wmma::col_major;
using nvcuda::wmma::fragment;
using nvcuda::wmma::load_matrix_sync;
using nvcuda::wmma::matrix_a;
using nvcuda::wmma::matrix_b;
using nvcuda::wmma::mem_row_major;
using nvcuda::wmma::mma_sync;
using nvcuda::wmma::row_major;
using nvcuda::wmma::store_matrix_sync;

__device__ __forceinline__ unsigned get_smid() {
  unsigned smid;
  asm volatile("mov.u32 %0, %smid;" : "=r"(smid));
  return smid;
}

__device__ __forceinline__ void record_smid(int* smid_by_block,
                                            int* rank_by_block,
                                            int* sm_counts,
                                            int sm_count_capacity) {
  if (threadIdx.x == 0 && smid_by_block && rank_by_block && sm_counts) {
    const unsigned smid = get_smid();
    int rank = -1;
    if (smid < static_cast<unsigned>(sm_count_capacity)) {
      rank = atomicAdd(&sm_counts[smid], 1);
    }
    smid_by_block[blockIdx.x] = static_cast<int>(smid);
    rank_by_block[blockIdx.x] = rank;
  }
  __syncthreads();
}

__device__ __forceinline__ half pattern_half(std::uint64_t i,
                                             std::uint64_t seed) {
  const unsigned v = static_cast<unsigned>((i * 1103515245ull + seed + 12345ull) & 31ull);
  return __float2half_rn(0.03125f * static_cast<float>(v + 1));
}

__device__ __forceinline__ void do_mma(fragment<matrix_a, 16, 16, 16, half, row_major>& a,
                                       fragment<matrix_b, 16, 16, 16, half, col_major>& b,
                                       fragment<accumulator, 16, 16, 16, float>& c) {
  mma_sync(c, a, b, c);
}

__device__ __forceinline__ float checksum_fragment(
    const fragment<matrix_a, 16, 16, 16, half, row_major>& frag) {
  float acc = 0.0f;
  #pragma unroll
  for (int i = 0; i < frag.num_elements; ++i) {
    acc += __half2float(frag.x[i]);
  }
  return acc;
}

__device__ __forceinline__ float checksum_fragment(
    const fragment<matrix_b, 16, 16, 16, half, col_major>& frag) {
  float acc = 0.0f;
  #pragma unroll
  for (int i = 0; i < frag.num_elements; ++i) {
    acc += __half2float(frag.x[i]);
  }
  return acc;
}

__device__ __forceinline__ void consume_float(float value) {
  asm volatile("" : : "f"(value));
}

__device__ __forceinline__ void consume_uint(unsigned value) {
  asm volatile("" : : "r"(value));
}

__device__ __forceinline__ unsigned register_control_step(
    unsigned sink, float a_value, float b_value, float c_value) {
  // One dependent register instruction keeps the RF-scaled loop and fragment
  // operands live without the former FP32 FMA/checksum or any memory access.
  asm volatile("add.u32 %0, %0, 1;"
               : "+r"(sink)
               : "f"(a_value), "f"(b_value), "f"(c_value));
  return sink;
}

__device__ __forceinline__ void compiler_barrier() {
  asm volatile("" ::: "memory");
}

__device__ __forceinline__ std::uint64_t select_tile(std::uint64_t load_index,
                                                     std::uint64_t tiles_per_block,
                                                     std::uint64_t block_id,
                                                     int streaming) {
  std::uint64_t tile = load_index % tiles_per_block;
  if (streaming) {
    tile = (load_index * 1315423911ull + block_id * 17ull) % tiles_per_block;
  }
  return tile;
}

__device__ __forceinline__ std::uint64_t select_physical_block(
    std::uint64_t logical_block, std::uint64_t block_count,
    int logical_blocks_per_sm) {
  if (logical_blocks_per_sm <= 1 || block_count <= 1 ||
      block_count % static_cast<std::uint64_t>(logical_blocks_per_sm) != 0) {
    return logical_block;
  }
  // Transpose [virtual SM][block rank] into [block rank][virtual SM]. This is
  // bijective for every supported grid and dephases power-of-two block strides.
  const std::uint64_t group_count = logical_blocks_per_sm;
  const std::uint64_t group_width = block_count / group_count;
  return (logical_block % group_count) * group_width +
         logical_block / group_count;
}

__global__ void init_half_kernel(half* input, std::size_t half_count,
                                 std::uint64_t seed) {
  const std::size_t tid = blockIdx.x * blockDim.x + threadIdx.x;
  const std::size_t stride = blockDim.x * gridDim.x;
  for (std::size_t i = tid; i < half_count; i += stride) {
    input[i] = pattern_half(i, seed);
  }
}

__global__ void global_warmup_kernel(const half* input, std::size_t half_count,
                                     float* output) {
  float acc = 0.0f;
  const std::size_t tid = blockIdx.x * blockDim.x + threadIdx.x;
  const std::size_t stride = blockDim.x * gridDim.x;
  for (std::size_t i = tid; i < half_count; i += stride) {
    acc += __half2float(input[i]);
  }
  if (output && tid < 1024) {
    output[tid] = acc;
  }
}

__global__ void global_cg_warmup_kernel(const half* input,
                                        std::size_t half_count, float* output) {
  const auto* words = reinterpret_cast<const std::uint32_t*>(input);
  const std::size_t word_count = half_count / 2;
  const std::size_t tid = blockIdx.x * blockDim.x + threadIdx.x;
  const std::size_t stride = blockDim.x * gridDim.x;
  std::uint32_t acc = static_cast<std::uint32_t>(tid + 1) * 2654435761u;
  for (std::size_t i = tid; i < word_count; i += stride) {
    std::uint32_t value;
    asm volatile("ld.global.cg.u32 %0, [%1];" : "=r"(value) : "l"(words + i));
    acc ^= value;
  }
  if (output && tid < 1024) {
    output[tid] = static_cast<float>(acc & 0x00ffffffu);
  }
}

__global__ void empty_kernel(std::uint64_t iters, float* output,
                             int* smid_by_block, int* rank_by_block,
                             int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);
  unsigned sink = static_cast<unsigned>(threadIdx.x ^ blockIdx.x);
  for (std::uint64_t i = 0; i < iters; ++i) {
    asm volatile("add.u32 %0, %0, 1;" : "+r"(sink));
  }
  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>((sink ^ static_cast<unsigned>(iters)) & 0xffffu);
  }
}

__global__ void clocked_empty_kernel(std::uint64_t iters,
                                     std::uint64_t load_repeat, float* output,
                                     int* smid_by_block, int* rank_by_block,
                                     int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);
  unsigned sink =
      static_cast<unsigned>((blockIdx.x + 1) * 2654435761u + threadIdx.x);
  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      sink ^= static_cast<unsigned>((i + r) & 0xffffffffull);
      asm volatile("add.u32 %0, %0, 17;" : "+r"(sink));
    }
  }
  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>((sink ^ static_cast<unsigned>(iters)) & 0xffffu);
  }
}

template <int FixedReuseFactor>
__global__ void reg_mma_kernel(std::uint64_t iters, float* output,
                               std::uint64_t reuse_factor,
                               int* smid_by_block, int* rank_by_block,
                               int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;

  const float block_scale = 1.0f + static_cast<float>(blockIdx.x & 7) * 0.03125f;
  nvcuda::wmma::fill_fragment(a, __float2half_rn(0.125f * block_scale));
  nvcuda::wmma::fill_fragment(b, __float2half_rn(0.0625f * block_scale));
  nvcuda::wmma::fill_fragment(c, 0.0f);

  const float a_value = __half2float(a.x[0]);
  const float b_value = __half2float(b.x[0]);
  const float c_value = c.x[0];
  unsigned sink = __float_as_uint(a_value) ^ __float_as_uint(b_value) ^
                  __float_as_uint(c_value) ^
                  static_cast<unsigned>(blockIdx.x * blockDim.x + threadIdx.x);

  for (std::uint64_t i = 0; i < iters; ++i) {
    if constexpr (FixedReuseFactor > 0) {
#pragma unroll 1
      for (int r = 0; r < FixedReuseFactor; ++r) {
        do_mma(a, b, c);
        sink = register_control_step(sink, a_value, b_value, c_value);
      }
    } else {
      for (std::uint64_t r = 0; r < reuse_factor; ++r) {
        do_mma(a, b, c);
        sink = register_control_step(sink, a_value, b_value, c_value);
      }
    }
  }

  consume_uint(sink);
  if (output) {
#pragma unroll
    for (int k = 0; k < c.num_elements; ++k) {
      output[blockIdx.x * 256 + threadIdx.x * c.num_elements + k] = c.x[k];
    }
  }
}

__global__ void reg_fragment_only_kernel(std::uint64_t iters, float* output,
                                         int* smid_by_block,
                                         int* rank_by_block, int* sm_counts,
                                         int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  float checksum = 0.0f;

  const float block_scale = 1.0f + static_cast<float>(blockIdx.x & 7) * 0.03125f;
  for (std::uint64_t i = 0; i < iters; ++i) {
    const float iter_scale =
        block_scale + static_cast<float>(i & 31ull) * 0.0009765625f;
    nvcuda::wmma::fill_fragment(a, __float2half_rn(0.125f * iter_scale));
    nvcuda::wmma::fill_fragment(b, __float2half_rn(0.0625f * iter_scale));
    checksum += checksum_fragment(a) + checksum_fragment(b);
  }

  nvcuda::wmma::fill_fragment(c, checksum);
  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

template <int FixedReuseFactor>
__global__ void reg_operand_only_kernel(std::uint64_t iters, float* output,
                                        std::uint64_t reuse_factor,
                                        int* smid_by_block,
                                        int* rank_by_block, int* sm_counts,
                                        int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;

  const float block_scale = 1.0f + static_cast<float>(blockIdx.x & 7) * 0.03125f;
  nvcuda::wmma::fill_fragment(a, __float2half_rn(0.125f * block_scale));
  nvcuda::wmma::fill_fragment(b, __float2half_rn(0.0625f * block_scale));
  nvcuda::wmma::fill_fragment(c, 0.0f);

  const float a_value = __half2float(a.x[0]);
  const float b_value = __half2float(b.x[0]);
  const float c_value = c.x[0];
  unsigned sink = __float_as_uint(a_value) ^ __float_as_uint(b_value) ^
                  __float_as_uint(c_value) ^
                  static_cast<unsigned>(blockIdx.x * blockDim.x + threadIdx.x);

  for (std::uint64_t i = 0; i < iters; ++i) {
    if constexpr (FixedReuseFactor > 0) {
#pragma unroll 1
      for (int r = 0; r < FixedReuseFactor; ++r) {
        sink = register_control_step(sink, a_value, b_value, c_value);
      }
    } else {
      for (std::uint64_t r = 0; r < reuse_factor; ++r) {
        sink = register_control_step(sink, a_value, b_value, c_value);
      }
    }
  }

  consume_uint(sink);
  if (output) {
#pragma unroll
    for (int k = 0; k < 8; ++k) {
      const unsigned value =
          sink ^ static_cast<unsigned>((k + 1) * 2654435761u);
      output[blockIdx.x * 256 + threadIdx.x * 8 + k] =
          __uint_as_float((value & 0x007fffffu) | 0x3f800000u);
    }
  }
}

template <int PayloadRegsPerThread>
__global__ void reg_pressure_kernel(std::uint64_t iters, float* output,
                                    std::uint64_t reuse_factor,
                                    int* smid_by_block, int* rank_by_block,
                                    int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  unsigned regs[PayloadRegsPerThread];
  unsigned acc =
      static_cast<unsigned>((blockIdx.x + 1) * 1103515245u + threadIdx.x);

  #pragma unroll
  for (int j = 0; j < PayloadRegsPerThread; ++j) {
    regs[j] = acc ^ static_cast<unsigned>((j + 1) * 2654435761u);
  }

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < reuse_factor; ++r) {
      compiler_barrier();
      #pragma unroll
      for (int j = 0; j < PayloadRegsPerThread; ++j) {
        const unsigned mix =
            static_cast<unsigned>((i + r + static_cast<std::uint64_t>(j)) &
                                  0xffffffffull);
        regs[j] = regs[j] * 1664525u + 1013904223u + (acc ^ mix);
        acc ^= regs[j] + static_cast<unsigned>(j * 17 + 3);
      }
      asm volatile("" : "+r"(acc));
    }
  }

  #pragma unroll
  for (int j = 0; j < PayloadRegsPerThread; ++j) {
    acc ^= regs[j] + static_cast<unsigned>(j);
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] = static_cast<float>(acc & 0xffffffu);
  }
}

__global__ void shared_load_only_kernel(std::uint64_t iters,
                                        std::uint64_t tiles_per_block,
                                        std::uint64_t load_repeat,
                                        float* output, int* smid_by_block,
                                        int* rank_by_block, int* sm_counts,
                                        int sm_count_capacity) {
  extern __shared__ __align__(16) unsigned char smem_raw[];
  half* smem = reinterpret_cast<half*>(smem_raw);
  const std::uint64_t half_count = tiles_per_block * 512ull;

  for (std::uint64_t i = threadIdx.x; i < half_count; i += blockDim.x) {
    smem[i] = pattern_half(i, blockIdx.x + 17ull);
  }
  __syncthreads();

  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  float checksum = 0.0f;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t tile = ((i * load_repeat) + r) % tiles_per_block;
      const half* base = smem + tile * 512ull;
      load_matrix_sync(a, base, 16);
      load_matrix_sync(b, base + 256, 16);
      checksum += checksum_fragment(a) + checksum_fragment(b);
    }
  }

  nvcuda::wmma::fill_fragment(c, checksum);
  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void shared_scalar_load_only_kernel(std::uint64_t iters,
                                               std::uint64_t tiles_per_block,
                                               std::uint64_t load_repeat,
                                               float* output,
                                               int* smid_by_block,
                                               int* rank_by_block,
                                               int* sm_counts,
                                               int sm_count_capacity) {
  extern __shared__ __align__(16) unsigned char smem_raw[];
  auto* smem = reinterpret_cast<std::uint32_t*>(smem_raw);
  const std::uint64_t words_per_tile = kLogicalMmaInputBytes / sizeof(std::uint32_t);
  const std::uint64_t word_count = tiles_per_block * words_per_tile;

  for (std::uint64_t i = threadIdx.x; i < word_count; i += blockDim.x) {
    smem[i] = static_cast<std::uint32_t>(
        (i + 1ull) * 1664525ull + (static_cast<std::uint64_t>(blockIdx.x) + 17ull));
  }
  __syncthreads();

  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  volatile const std::uint32_t* vsmem = smem;
  std::uint32_t checksum =
      static_cast<std::uint32_t>(threadIdx.x + 1) * 2654435761u;
  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t tile = ((i * load_repeat) + r) % tiles_per_block;
      const std::uint64_t base = tile * words_per_tile;
#pragma unroll
      for (int k = 0; k < 8; ++k) {
        const std::uint64_t word_index =
            base + static_cast<std::uint64_t>(threadIdx.x) +
            static_cast<std::uint64_t>(k * kWarpSize);
        checksum ^= vsmem[word_index];
        checksum = checksum * 1664525u + 1013904223u;
      }
    }
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>(checksum & 0x00ffffffu);
  }
}

__global__ void shared_mma_kernel(std::uint64_t iters,
                                  std::uint64_t tiles_per_block,
                                  std::uint64_t reuse_factor,
                                  std::uint64_t load_repeat,
                                  float* output, int* smid_by_block,
                                  int* rank_by_block, int* sm_counts,
                                  int sm_count_capacity) {
  extern __shared__ __align__(16) unsigned char smem_raw[];
  half* smem = reinterpret_cast<half*>(smem_raw);
  const std::uint64_t half_count = tiles_per_block * 512ull;

  for (std::uint64_t i = threadIdx.x; i < half_count; i += blockDim.x) {
    smem[i] = pattern_half(i, blockIdx.x + 17ull);
  }
  __syncthreads();

  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  nvcuda::wmma::fill_fragment(c, 0.0f);
  float load_checksum = 0.0f;
  const bool consume_repeated_loads = load_repeat > 1;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t tile = ((i * load_repeat) + r) % tiles_per_block;
      const half* base = smem + tile * 512ull;
      load_matrix_sync(a, base, 16);
      load_matrix_sync(b, base + 256, 16);
      if (consume_repeated_loads) {
        load_checksum += checksum_fragment(a) + checksum_fragment(b);
      }
    }
    for (std::uint64_t r = 0; r < reuse_factor; ++r) {
      do_mma(a, b, c);
    }
  }
  if (consume_repeated_loads) {
    consume_float(load_checksum);
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void global_mma_kernel(const half* input,
                                  std::uint64_t global_block_stride_bytes,
                                  int skew_global_block_layout,
                                  std::uint64_t w_block_bytes,
                                  std::uint64_t tiles_per_block,
                                  std::uint64_t iters,
                                  std::uint64_t reuse_factor,
                                  std::uint64_t load_repeat, int streaming,
                                  float* output, int* smid_by_block,
                                  int* rank_by_block, int* sm_counts,
                                  int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  nvcuda::wmma::fill_fragment(c, 0.0f);
  float load_checksum = 0.0f;
  const bool consume_repeated_loads = load_repeat > 1;

  const std::uint64_t physical_block = select_physical_block(
      blockIdx.x, gridDim.x, skew_global_block_layout);
  const std::uint64_t block_half_offset =
      (physical_block * global_block_stride_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), streaming);
      const half* base = block_base + tile * 512ull;
      load_matrix_sync(a, base, 16);
      load_matrix_sync(b, base + 256, 16);
      if (consume_repeated_loads) {
        load_checksum += checksum_fragment(a) + checksum_fragment(b);
      }
    }
    for (std::uint64_t r = 0; r < reuse_factor; ++r) {
      do_mma(a, b, c);
    }
  }
  if (consume_repeated_loads) {
    consume_float(load_checksum);
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void global_load_only_kernel(const half* input,
                                        std::uint64_t global_block_stride_bytes,
                                        int skew_global_block_layout,
                                        std::uint64_t w_block_bytes,
                                        std::uint64_t tiles_per_block,
                                        std::uint64_t iters,
                                        std::uint64_t load_repeat,
                                        int streaming, float* output,
                                        int* smid_by_block,
                                        int* rank_by_block, int* sm_counts,
                                        int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  float checksum = 0.0f;

  const std::uint64_t physical_block = select_physical_block(
      blockIdx.x, gridDim.x, skew_global_block_layout);
  const std::uint64_t block_half_offset =
      (physical_block * global_block_stride_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), streaming);
      const half* base = block_base + tile * 512ull;
      load_matrix_sync(a, base, 16);
      load_matrix_sync(b, base + 256, 16);
      checksum += checksum_fragment(a) + checksum_fragment(b);
    }
  }

  nvcuda::wmma::fill_fragment(c, checksum);
  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__device__ __forceinline__ std::uint32_t load_global_cg_u32(
    const std::uint32_t* ptr) {
  std::uint32_t value;
  asm volatile("ld.global.cg.u32 %0, [%1];" : "=r"(value) : "l"(ptr));
  return value;
}

__device__ __forceinline__ std::uint32_t load_global_ca_u32(
    const std::uint32_t* ptr) {
  std::uint32_t value;
  asm volatile("ld.global.ca.u32 %0, [%1];" : "=r"(value) : "l"(ptr));
  return value;
}

__global__ void global_ca_load_only_kernel(const half* input,
                                           std::uint64_t global_block_stride_bytes,
                                           int skew_global_block_layout,
                                           std::uint64_t w_block_bytes,
                                           std::uint64_t tiles_per_block,
                                           std::uint64_t iters,
                                           std::uint64_t load_repeat,
                                           float* output,
                                           int* smid_by_block,
                                           int* rank_by_block, int* sm_counts,
                                           int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  const std::uint64_t physical_block = select_physical_block(
      blockIdx.x, gridDim.x, skew_global_block_layout);
  const std::uint64_t block_half_offset =
      (physical_block * global_block_stride_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;
  std::uint32_t checksum =
      static_cast<std::uint32_t>(threadIdx.x + 1) * 2654435761u;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), 0);
      const half* base = block_base + tile * 512ull;
      const auto* words = reinterpret_cast<const std::uint32_t*>(base);
#pragma unroll
      for (int k = 0; k < 8; ++k) {
        const int word_index = static_cast<int>(threadIdx.x) + k * kWarpSize;
        checksum ^= load_global_ca_u32(words + word_index);
        checksum = checksum * 1664525u + 1013904223u;
      }
    }
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>(checksum & 0x00ffffffu);
  }
}

__global__ void global_cg_load_only_kernel(const half* input,
                                           std::uint64_t global_block_stride_bytes,
                                           int skew_global_block_layout,
                                           std::uint64_t w_block_bytes,
                                           std::uint64_t tiles_per_block,
                                           std::uint64_t iters,
                                           std::uint64_t load_repeat,
                                           int streaming, float* output,
                                           int* smid_by_block,
                                           int* rank_by_block, int* sm_counts,
                                           int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  const std::uint64_t physical_block = select_physical_block(
      blockIdx.x, gridDim.x, skew_global_block_layout);
  const std::uint64_t block_half_offset =
      (physical_block * global_block_stride_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;
  std::uint32_t checksum =
      static_cast<std::uint32_t>(threadIdx.x + 1) * 2654435761u;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), streaming);
      const half* base = block_base + tile * 512ull;
      const auto* words = reinterpret_cast<const std::uint32_t*>(base);
#pragma unroll
      for (int k = 0; k < 8; ++k) {
        const int word_index = static_cast<int>(threadIdx.x) + k * kWarpSize;
        checksum ^= load_global_cg_u32(words + word_index);
        checksum = checksum * 1664525u + 1013904223u;
      }
    }
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>(checksum & 0x00ffffffu);
  }
}

__global__ void global_addr_only_kernel(std::uint64_t w_block_bytes,
                                        std::uint64_t tiles_per_block,
                                        std::uint64_t iters,
                                        std::uint64_t load_repeat,
                                        int streaming, float* output,
                                        int* smid_by_block,
                                        int* rank_by_block, int* sm_counts,
                                        int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  std::uint64_t checksum =
      static_cast<std::uint64_t>(threadIdx.x + 1) * 11400714819323198485ull;
  const std::uint64_t block_byte_offset =
      static_cast<std::uint64_t>(blockIdx.x) * w_block_bytes;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), streaming);
      const std::uint64_t byte_offset =
          block_byte_offset + tile * static_cast<std::uint64_t>(kLogicalMmaInputBytes);
      checksum ^= byte_offset + (load_index << 7);
      checksum = checksum * 2862933555777941757ull + 3037000493ull;
      asm volatile("" : "+l"(checksum));
    }
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>(checksum & 0xffffffull);
  }
}

// Address/control counterpart for scalar global load paths. It executes the
// same block/tile/index arithmetic and checksum shape as global_cg_load_only,
// but consumes addresses rather than issuing global-memory loads.
__global__ void global_scalar_addr_only_kernel(
    const half* input, std::uint64_t global_block_stride_bytes,
    int skew_global_block_layout, std::uint64_t w_block_bytes,
    std::uint64_t tiles_per_block, std::uint64_t iters,
    std::uint64_t load_repeat, int streaming, float* output,
    int* smid_by_block, int* rank_by_block, int* sm_counts,
    int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  const std::uint64_t physical_block = select_physical_block(
      blockIdx.x, gridDim.x, skew_global_block_layout);
  const std::uint64_t block_half_offset =
      (physical_block * global_block_stride_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;
  std::uint32_t checksum =
      static_cast<std::uint32_t>(threadIdx.x + 1) * 2654435761u;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      const std::uint64_t tile =
          select_tile(load_index, tiles_per_block,
                      static_cast<std::uint64_t>(blockIdx.x), streaming);
      const half* base = block_base + tile * 512ull;
      const auto* words = reinterpret_cast<const std::uint32_t*>(base);
#pragma unroll
      for (int k = 0; k < 8; ++k) {
        const int word_index = static_cast<int>(threadIdx.x) + k * kWarpSize;
        const auto address = reinterpret_cast<std::uintptr_t>(words + word_index);
        checksum ^= static_cast<std::uint32_t>(address >> 2);
        checksum = checksum * 1664525u + 1013904223u;
      }
    }
  }

  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] =
        static_cast<float>(checksum & 0x00ffffffu);
  }
}

__global__ void store_path_kernel(std::uint64_t iters, float* output,
                                  std::uint64_t store_repeat,
                                  int* smid_by_block, int* rank_by_block,
                                  int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);
  if (!output) return;
  float v = static_cast<float>((blockIdx.x & 31) + 1);
  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < store_repeat; ++r) {
      const std::uint64_t slot =
          static_cast<std::uint64_t>(blockIdx.x) * 256ull +
          (((i * store_repeat) + r) & 255ull);
      output[slot] = v + static_cast<float>((i + r) & 1023ull);
    }
  }
}

}  // namespace

cudaError_t configure_kernel_attributes(Mode mode, std::size_t dynamic_smem_bytes) {
  if (mode == Mode::shared_scalar_load_only ||
      mode == Mode::shared_load_only || mode == Mode::shared_mma) {
    cudaError_t err = cudaFuncSetAttribute(
        shared_mma_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
        static_cast<int>(dynamic_smem_bytes));
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(
        shared_load_only_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
        static_cast<int>(dynamic_smem_bytes));
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(
        shared_scalar_load_only_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
        static_cast<int>(dynamic_smem_bytes));
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(shared_mma_kernel,
                               cudaFuncAttributePreferredSharedMemoryCarveout,
                               cudaSharedmemCarveoutMaxShared);
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(shared_load_only_kernel,
                               cudaFuncAttributePreferredSharedMemoryCarveout,
                               cudaSharedmemCarveoutMaxShared);
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(shared_scalar_load_only_kernel,
                               cudaFuncAttributePreferredSharedMemoryCarveout,
                               cudaSharedmemCarveoutMaxShared);
    if (err != cudaSuccess) return err;
  }
  return cudaSuccess;
}

cudaError_t launch_init_half(half* input, std::size_t half_count,
                             std::uint64_t seed, cudaStream_t stream) {
  constexpr int block = 256;
  int grid = static_cast<int>((half_count + block - 1) / block);
  grid = grid < 1 ? 1 : (grid > 65535 ? 65535 : grid);
  init_half_kernel<<<grid, block, 0, stream>>>(input, half_count, seed);
  return cudaGetLastError();
}

cudaError_t launch_global_warmup(const half* input, std::size_t half_count,
                                 float* output, bool cache_global_only,
                                 cudaStream_t stream) {
  constexpr int block = 256;
  int grid = static_cast<int>((half_count + block - 1) / block);
  grid = grid < 1 ? 1 : (grid > 65535 ? 65535 : grid);
  if (cache_global_only) {
    global_cg_warmup_kernel<<<grid, block, 0, stream>>>(input, half_count, output);
  } else {
    global_warmup_kernel<<<grid, block, 0, stream>>>(input, half_count, output);
  }
  return cudaGetLastError();
}

cudaError_t launch_benchmark_kernel(const KernelLaunchConfig& cfg) {
  const int grid = cfg.active_sm * cfg.blocks_per_sm;
  const dim3 block(kThreadsPerBlock, 1, 1);
  const dim3 grid_dim(grid, 1, 1);

  switch (cfg.mode) {
    case Mode::empty:
      empty_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::clocked_empty:
      clocked_empty_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.load_repeat, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::reg_mma:
      switch (cfg.reuse_factor) {
        case 1:
          reg_mma_kernel<0><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 2:
          reg_mma_kernel<2><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 4:
          reg_mma_kernel<4><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 8:
          reg_mma_kernel<8><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 16:
          reg_mma_kernel<16><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        default:
          reg_mma_kernel<0><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
      }
      break;
    case Mode::reg_fragment_only:
      reg_fragment_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::reg_operand_only:
      switch (cfg.reuse_factor) {
        case 1:
          reg_operand_only_kernel<0><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 2:
          reg_operand_only_kernel<2><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 4:
          reg_operand_only_kernel<4><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 8:
          reg_operand_only_kernel<8><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 16:
          reg_operand_only_kernel<16><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        default:
          reg_operand_only_kernel<0><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
      }
      break;
    case Mode::reg_pressure:
      switch (cfg.reg_payload_bytes_per_block) {
        case 256:
          reg_pressure_kernel<2><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 512:
          reg_pressure_kernel<4><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 1024:
          reg_pressure_kernel<8><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 2048:
          reg_pressure_kernel<16><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 4096:
          reg_pressure_kernel<32><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 8192:
          reg_pressure_kernel<64><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        case 16384:
          reg_pressure_kernel<128><<<grid_dim, block, 0, cfg.stream>>>(
              cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
              cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
          break;
        default:
          return cudaErrorInvalidValue;
      }
      break;
    case Mode::addr_only:
      global_addr_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters, cfg.load_repeat,
          cfg.streaming, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::global_addr_only:
      global_scalar_addr_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, cfg.streaming, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::global_l1_load_only:
      global_ca_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::shared_scalar_load_only:
      shared_scalar_load_only_kernel<<<grid_dim, block,
                                       static_cast<std::size_t>(cfg.w_block_bytes),
                                       cfg.stream>>>(
          cfg.iters, cfg.tiles_per_block, cfg.load_repeat, cfg.output,
          cfg.smid_by_block, cfg.rank_by_block, cfg.sm_counts,
          cfg.sm_count_capacity);
      break;
    case Mode::shared_load_only:
      shared_load_only_kernel<<<grid_dim, block,
                                static_cast<std::size_t>(cfg.w_block_bytes),
                                cfg.stream>>>(
          cfg.iters, cfg.tiles_per_block, cfg.load_repeat, cfg.output,
          cfg.smid_by_block, cfg.rank_by_block, cfg.sm_counts,
          cfg.sm_count_capacity);
      break;
    case Mode::shared_mma:
      shared_mma_kernel<<<grid_dim, block,
                          static_cast<std::size_t>(cfg.w_block_bytes),
                          cfg.stream>>>(
          cfg.iters, cfg.tiles_per_block, cfg.reuse_factor, cfg.load_repeat,
          cfg.output, cfg.smid_by_block, cfg.rank_by_block, cfg.sm_counts,
          cfg.sm_count_capacity);
      break;
    case Mode::l2_load_only:
      global_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 0, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::l2_cg_load_only:
      global_cg_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 0, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::l2_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.reuse_factor, cfg.load_repeat, 0, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::dram_load_only:
      global_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 1, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::dram_cg_load_only:
      global_cg_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 1, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::dram_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.global_block_stride_bytes,
          cfg.skew_global_block_layout, cfg.w_block_bytes,
          cfg.tiles_per_block, cfg.iters,
          cfg.reuse_factor, cfg.load_repeat, 1, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::store_only:
      store_path_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.store_repeat, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::store_path:
      store_path_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.store_repeat, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::idle:
      return cudaSuccess;
  }

  return cudaGetLastError();
}

}  // namespace a100fp16
