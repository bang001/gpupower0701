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
  for (std::uint64_t i = 0; i < iters; ++i) {
    asm volatile("" : : "l"(i) : "memory");
  }
  if (threadIdx.x == 0 && output) {
    output[blockIdx.x * 256] = static_cast<float>((iters ^ blockIdx.x) & 0xffff);
  }
}

__global__ void reg_mma_kernel(std::uint64_t iters, float* output,
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
    do_mma(a, b, c);
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void shared_mma_kernel(std::uint64_t iters,
                                  std::uint64_t tiles_per_block,
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

  for (std::uint64_t i = 0; i < iters; ++i) {
    const std::uint64_t tile = i % tiles_per_block;
    const half* base = smem + tile * 512ull;
    load_matrix_sync(a, base, 16);
    load_matrix_sync(b, base + 256, 16);
    do_mma(a, b, c);
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void global_mma_kernel(const half* input, std::uint64_t w_block_bytes,
                                  std::uint64_t tiles_per_block,
                                  std::uint64_t iters, int streaming,
                                  float* output, int* smid_by_block,
                                  int* rank_by_block, int* sm_counts,
                                  int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);

  fragment<matrix_a, 16, 16, 16, half, row_major> a;
  fragment<matrix_b, 16, 16, 16, half, col_major> b;
  fragment<accumulator, 16, 16, 16, float> c;
  nvcuda::wmma::fill_fragment(c, 0.0f);

  const std::uint64_t block_half_offset =
      (static_cast<std::uint64_t>(blockIdx.x) * w_block_bytes) / sizeof(half);
  const half* block_base = input + block_half_offset;

  for (std::uint64_t i = 0; i < iters; ++i) {
    std::uint64_t tile = i % tiles_per_block;
    if (streaming) {
      tile = (i * 1315423911ull + static_cast<std::uint64_t>(blockIdx.x) * 17ull) %
             tiles_per_block;
    }
    const half* base = block_base + tile * 512ull;
    load_matrix_sync(a, base, 16);
    load_matrix_sync(b, base + 256, 16);
    do_mma(a, b, c);
  }

  if (output) {
    store_matrix_sync(output + blockIdx.x * 256, c, 16, mem_row_major);
  }
}

__global__ void store_path_kernel(std::uint64_t iters, float* output,
                                  int* smid_by_block, int* rank_by_block,
                                  int* sm_counts, int sm_count_capacity) {
  record_smid(smid_by_block, rank_by_block, sm_counts, sm_count_capacity);
  if (!output) return;
  float v = static_cast<float>((blockIdx.x & 31) + 1);
  for (std::uint64_t i = 0; i < iters; ++i) {
    const std::uint64_t slot =
        static_cast<std::uint64_t>(blockIdx.x) * 256ull + (i & 255ull);
    output[slot] = v + static_cast<float>(i & 1023ull);
  }
}

}  // namespace

cudaError_t configure_kernel_attributes(Mode mode, std::size_t dynamic_smem_bytes) {
  if (mode == Mode::shared_mma) {
    cudaError_t err = cudaFuncSetAttribute(
        shared_mma_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize,
        static_cast<int>(dynamic_smem_bytes));
    if (err != cudaSuccess) return err;
    err = cudaFuncSetAttribute(shared_mma_kernel,
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
          cfg.iters, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::shared_mma:
      shared_mma_kernel<<<grid_dim, block,
                          static_cast<std::size_t>(cfg.w_block_bytes),
                          cfg.stream>>>(
          cfg.iters, cfg.tiles_per_block, cfg.output, cfg.smid_by_block,
          cfg.rank_by_block, cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::l2_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters, 0,
          cfg.output, cfg.smid_by_block, cfg.rank_by_block, cfg.sm_counts,
          cfg.sm_count_capacity);
      break;
    case Mode::dram_mma:
      global_mma_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.input, cfg.w_block_bytes, cfg.tiles_per_block, cfg.iters, 1,
          cfg.output, cfg.smid_by_block, cfg.rank_by_block, cfg.sm_counts,
          cfg.sm_count_capacity);
      break;
    case Mode::store_path:
      store_path_kernel<<<grid_dim, block, 0, cfg.stream>>>(
          cfg.iters, cfg.output, cfg.smid_by_block, cfg.rank_by_block,
          cfg.sm_counts, cfg.sm_count_capacity);
      break;
    case Mode::idle:
      return cudaSuccess;
  }

  return cudaGetLastError();
}

}  // namespace a100fp16
