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

__device__ __forceinline__ void compiler_barrier() {
  asm volatile("" ::: "memory");
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

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < reuse_factor; ++r) {
      do_mma(a, b, c);
    }
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
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

  float checksum = 0.0f;
  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < reuse_factor; ++r) {
      compiler_barrier();
      const float operand_sum = __half2float(a.x[0]) + __half2float(b.x[0]);
      checksum = __fmaf_rn(
          checksum, 1.000000119f,
          operand_sum + static_cast<float>((i + r) & 31ull) * 0.0009765625f);
      consume_float(checksum);
    }
  }

  nvcuda::wmma::fill_fragment(c, checksum);
  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
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

__global__ void global_mma_kernel(const half* input, std::uint64_t w_block_bytes,
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

  const std::uint64_t block_half_offset =
      (static_cast<std::uint64_t>(blockIdx.x) * w_block_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      std::uint64_t tile = load_index % tiles_per_block;
      if (streaming) {
        tile = (load_index * 1315423911ull +
                static_cast<std::uint64_t>(blockIdx.x) * 17ull) %
               tiles_per_block;
      }
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

  const std::uint64_t block_half_offset =
      (static_cast<std::uint64_t>(blockIdx.x) * w_block_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;

  for (std::uint64_t i = 0; i < iters; ++i) {
    for (std::uint64_t r = 0; r < load_repeat; ++r) {
      const std::uint64_t load_index = (i * load_repeat) + r;
      std::uint64_t tile = load_index % tiles_per_block;
      if (streaming) {
        tile = (load_index * 1315423911ull +
                static_cast<std::uint64_t>(blockIdx.x) * 17ull) %
               tiles_per_block;
      }
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
  if (mode == Mode::shared_load_only || mode == Mode::shared_mma) {
    cudaError_t err = cudaFuncSetAttribute(
        shared_mma_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
        static_cast<int>(dynamic_smem_bytes));
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(
        shared_load_only_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
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
                                 float* output, cudaStream_t stream) {
  constexpr int block = 256;
  int grid = static_cast<int>((half_count + block - 1) / block);
  grid = grid < 1 ? 1 : (grid > 65535 ? 65535 : grid);
  global_warmup_kernel<<<grid, block, 0, stream>>>(input, half_count, output);
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
    case Mode::reg_mma:
      reg_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::reg_fragment_only:
      reg_fragment_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::reg_operand_only:
      reg_operand_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.reuse_factor, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
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
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 0, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::l2_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters,
          cfg.reuse_factor, cfg.load_repeat, 0, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::dram_load_only:
      global_load_only_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters,
          cfg.load_repeat, 1, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::dram_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters,
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
