#include "softmax_kernels.cuh"

#include <limits>
#include <stdexcept>

namespace fp16softmax {
namespace {

constexpr int kWarpsPerBlock = kThreadsPerBlock / 32;

__device__ __forceinline__ unsigned read_smid() {
  unsigned smid = 0;
  asm volatile("mov.u32 %0, %%smid;" : "=r"(smid));
  return smid;
}

__device__ __forceinline__ unsigned read_clock_token() {
  unsigned token = 0;
  asm volatile("mov.u32 %0, %%clock;" : "=r"(token));
  return token;
}

__device__ __forceinline__ float warp_reduce_max(float value) {
  for (int offset = 16; offset > 0; offset /= 2) {
    value = fmaxf(value, __shfl_down_sync(0xffffffffu, value, offset));
  }
  return value;
}

__device__ __forceinline__ float warp_reduce_sum(float value) {
  for (int offset = 16; offset > 0; offset /= 2) {
    value += __shfl_down_sync(0xffffffffu, value, offset);
  }
  return value;
}

__device__ __forceinline__ float block_reduce_max(float value,
                                                    float* warp_values) {
  const int lane = threadIdx.x & 31;
  const int warp = threadIdx.x >> 5;
  value = warp_reduce_max(value);
  if (lane == 0) warp_values[warp] = value;
  __syncthreads();
  value = threadIdx.x < kWarpsPerBlock
              ? warp_values[lane]
              : -std::numeric_limits<float>::infinity();
  if (warp == 0) value = warp_reduce_max(value);
  if (threadIdx.x == 0) warp_values[0] = value;
  __syncthreads();
  return warp_values[0];
}

__device__ __forceinline__ float block_reduce_sum(float value,
                                                    float* warp_values) {
  const int lane = threadIdx.x & 31;
  const int warp = threadIdx.x >> 5;
  value = warp_reduce_sum(value);
  if (lane == 0) warp_values[warp] = value;
  __syncthreads();
  value = threadIdx.x < kWarpsPerBlock ? warp_values[lane] : 0.0f;
  if (warp == 0) value = warp_reduce_sum(value);
  if (threadIdx.x == 0) warp_values[0] = value;
  __syncthreads();
  return warp_values[0];
}

__device__ __forceinline__ half load_half_default(const half* address) {
  // volatile prevents ptxas from hoisting the resident-input load out of the
  // timed outer loop.  The output is volatile for the symmetric store gate.
  const volatile half* volatile_address = address;
  return *volatile_address;
}

__device__ __forceinline__ half load_half_cg(const half* address) {
  unsigned short bits = 0;
  asm volatile("ld.global.cg.u16 %0, [%1];"
               : "=h"(bits)
               : "l"(address));
  return __ushort_as_half(bits);
}

__device__ __forceinline__ float retain_float_conversion(float value) {
  // The I/O control must retain FP16 -> FP32 -> FP16 rather than becoming a
  // raw half copy.  The register constraint is also audited in SASS/NCU.
  asm volatile("" : "+f"(value));
  return value;
}

__device__ __forceinline__ half ptx_ex2_approx_f16(half input) {
  const unsigned short input_bits = __half_as_ushort(input);
  unsigned short output_bits = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16 %0, %1;"
               : "=h"(output_bits)
               : "h"(input_bits));
#else
  // Every registered build targets sm_80 or sm_86.  Returning the input keeps
  // the host compilation pass well formed; runtime/profile gates reject any
  // native-EX2 binary below sm_75 before measurement.
  output_bits = input_bits;
#endif
  return __ushort_as_half(output_bits);
}

__device__ __forceinline__ std::uint32_t pack_half_bits(half low, half high) {
  return static_cast<std::uint32_t>(__half_as_ushort(low)) |
         (static_cast<std::uint32_t>(__half_as_ushort(high)) << 16);
}

__device__ __forceinline__ half unpack_half_low(std::uint32_t packed) {
  return __ushort_as_half(static_cast<unsigned short>(packed & 0xffffu));
}

__device__ __forceinline__ half unpack_half_high(std::uint32_t packed) {
  return __ushort_as_half(static_cast<unsigned short>(packed >> 16));
}

__device__ __forceinline__ std::uint32_t ptx_ex2_approx_f16x2(
    std::uint32_t input_bits) {
  std::uint32_t output_bits = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16x2 %0, %1;"
               : "=r"(output_bits)
               : "r"(input_bits));
#else
  output_bits = input_bits;
#endif
  return output_bits;
}

template <int Cols, SoftmaxMode Mode, ExpImplementation ExpImpl,
          bool CacheGlobal>
__global__ void softmax_row_kernel(const half* input, half* output,
                                   std::uint32_t* token_by_block,
                                   std::uint64_t iters,
                                   std::uint64_t row_tiles_per_block,
                                   std::uint64_t tile_stride, bool streaming,
                                   bool extra_exp_probe,
                                   int* smid_by_block, int* sm_counts,
                                   int sm_count_capacity) {
  static_assert(Cols <= kMaxSoftmaxCols, "unsupported softmax row width");
  constexpr int kElementsPerThread =
      Cols <= kThreadsPerBlock ? 1 : Cols / kThreadsPerBlock;
  static_assert(Cols % kThreadsPerBlock == 0 || Cols <= kThreadsPerBlock,
                "row width must map to fixed elements/thread");

  const unsigned smid = read_smid();
  if (threadIdx.x == 0) {
    if (smid_by_block) smid_by_block[blockIdx.x] = static_cast<int>(smid);
    if (sm_counts && static_cast<int>(smid) < sm_count_capacity) {
      atomicAdd(sm_counts + smid, 1);
    }
  }

  __shared__ float warp_values[kWarpsPerBlock];
  float values[kElementsPerThread];
  unsigned sink = static_cast<unsigned>(blockIdx.x + 1) * 0x9e3779b9u ^
                  static_cast<unsigned>(threadIdx.x + 17);
  volatile half* volatile_output = output;

  for (std::uint64_t iter = 0; iter < iters; ++iter) {
    const unsigned clock_token = read_clock_token();
    sink ^= clock_token + static_cast<unsigned>(iter);
    const std::uint64_t tile_offset =
        streaming && row_tiles_per_block > 1
            ? ((iter * tile_stride) % row_tiles_per_block)
            : 0;
    const std::uint64_t row = static_cast<std::uint64_t>(blockIdx.x) *
                                  row_tiles_per_block +
                              tile_offset;
    const half* row_input = input + row * Cols;
#pragma unroll
    for (int element = 0; element < kElementsPerThread; ++element) {
      const int column = threadIdx.x + element * kThreadsPerBlock;
      if (column < Cols) {
        const half input_value = CacheGlobal ? load_half_cg(row_input + column)
                                             : load_half_default(row_input + column);
        values[element] = retain_float_conversion(__half2float(input_value));
      } else {
        values[element] = -std::numeric_limits<float>::infinity();
      }
    }

    if constexpr (Mode == SoftmaxMode::io_control) {
#pragma unroll
      for (int element = 0; element < kElementsPerThread; ++element) {
        const int column = threadIdx.x + element * kThreadsPerBlock;
        if (column < Cols) {
          volatile_output[row * Cols + column] = __float2half_rn(values[element]);
        }
      }
    } else {
      float local_max = -std::numeric_limits<float>::infinity();
#pragma unroll
      for (int element = 0; element < kElementsPerThread; ++element) {
        local_max = fmaxf(local_max, values[element]);
      }
      const float row_max = block_reduce_max(local_max, warp_values);

      float local_sum = 0.0f;
      if constexpr (Mode == SoftmaxMode::full &&
                    ExpImpl == ExpImplementation::fp32_expf) {
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          const int column = threadIdx.x + element * kThreadsPerBlock;
          if (column < Cols) {
            values[element] = __expf(values[element] - row_max);
            // The state-matched Operand-rate contrast uses this runtime-unified
            // kernel in both roles.  Both roles compute the normal Softmax;
            // treatment alone evaluates one additional data-dependent __expf
            // and retains it only through the existing token sink.  Keeping the
            // flag runtime (not a template parameter) gives both roles the same
            // kernel symbol, register allocation, shared footprint, and launch
            // occupancy.  Dynamic NCU counters must still prove the extra EX2
            // issue count before the contrast is accepted.
            float probe_input = values[element] + 0x1p-10f;
            asm volatile("" : "+f"(probe_input));
            float probe_value = probe_input;
            if (extra_exp_probe) {
              probe_value = __expf(probe_input);
            }
            asm volatile("" : "+f"(probe_value));
            sink ^= __float_as_uint(probe_value);
            local_sum += values[element];
          } else {
            values[element] = 0.0f;
          }
        }
      } else if constexpr (Mode == SoftmaxMode::full &&
                           ExpImpl == ExpImplementation::ptx_f16) {
        constexpr float kLog2E = 1.4426950408889634f;
        if constexpr (kElementsPerThread >= 2 &&
                      (kElementsPerThread % 2) == 0) {
          // S=512 and larger use the same pair-wise packing/XOR bookkeeping as
          // the f16x2 specialization.  This keeps the scalar-vs-packed
          // diagnostic comparison focused on the PTX instruction form rather
          // than a different number or width of checksum operations.
#pragma unroll
          for (int element = 0; element < kElementsPerThread; element += 2) {
            const half input_low =
                __float2half_rn((values[element] - row_max) * kLog2E);
            const half input_high =
                __float2half_rn((values[element + 1] - row_max) * kLog2E);
            const half output_low = ptx_ex2_approx_f16(input_low);
            const half output_high = ptx_ex2_approx_f16(input_high);
            values[element] = __half2float(output_low);
            values[element + 1] = __half2float(output_high);

            // Probe the same centered-logit operands as the normal Softmax
            // EX2 operations.  asm volatile in the helper plus the live sink
            // prevents folding the extra issues into the main result.
            half probe_low = input_low;
            half probe_high = input_high;
            if (extra_exp_probe) {
              probe_low = ptx_ex2_approx_f16(input_low);
              probe_high = ptx_ex2_approx_f16(input_high);
            }
            sink ^= pack_half_bits(probe_low, probe_high);
            local_sum += values[element] + values[element + 1];
          }
        } else {
#pragma unroll
          for (int element = 0; element < kElementsPerThread; ++element) {
            const int column = threadIdx.x + element * kThreadsPerBlock;
            if (column < Cols) {
              const half exponent_input =
                  __float2half_rn((values[element] - row_max) * kLog2E);
              const half exponent_output = ptx_ex2_approx_f16(exponent_input);
              values[element] = __half2float(exponent_output);
              half probe_output = exponent_input;
              if (extra_exp_probe) {
                probe_output = ptx_ex2_approx_f16(exponent_input);
              }
              sink ^= static_cast<unsigned>(__half_as_ushort(probe_output));
              local_sum += values[element];
            } else {
              values[element] = 0.0f;
            }
          }
        }
      } else if constexpr (Mode == SoftmaxMode::full &&
                           ExpImpl == ExpImplementation::ptx_f16x2) {
        constexpr float kLog2E = 1.4426950408889634f;
        if constexpr (kElementsPerThread == 1) {
          // S=128/256 assign one logical element to each participating
          // thread.  Form one packed operand per adjacent lane pair so the
          // 256-thread CTA and the existing block-reduction structure stay
          // unchanged.  Only the even lane executes EX2; both lanes recover
          // their result from the even lane with a warp shuffle.  Since every
          // supported short row is an even multiple of a warp, a participating
          // lane never pairs with an out-of-row lane.
          static_assert((Cols % 2) == 0,
                        "packed FP16 EX2 requires an even row width");
          const int column = threadIdx.x;
          const int lane = threadIdx.x & 31;
          const bool in_row = column < Cols;
          const half exponent_input =
              in_row ? __float2half_rn((values[0] - row_max) * kLog2E)
                     : __float2half_rn(
                           -std::numeric_limits<float>::infinity());
          const unsigned input_bits =
              static_cast<unsigned>(__half_as_ushort(exponent_input));
          const unsigned partner_bits =
              __shfl_xor_sync(0xffffffffu, input_bits, 1);
          const half partner_input = __ushort_as_half(
              static_cast<unsigned short>(partner_bits));
          const std::uint32_t packed_input =
              pack_half_bits(exponent_input, partner_input);
          // A distinct, data-dependent probe operand prevents ptxas from
          // commoning the optional EX2 with the normal Softmax EX2.  The
          // one-bit perturbation and both shuffles execute in both roles; only
          // the treatment executes the second packed EX2.
          const unsigned probe_input_bits = input_bits ^ 1u;
          const unsigned partner_probe_bits =
              __shfl_xor_sync(0xffffffffu, probe_input_bits, 1);
          const half probe_input = __ushort_as_half(
              static_cast<unsigned short>(probe_input_bits));
          const half partner_probe_input = __ushort_as_half(
              static_cast<unsigned short>(partner_probe_bits));
          const std::uint32_t packed_probe_input =
              pack_half_bits(probe_input, partner_probe_input);
          const bool pair_leader = in_row && (lane & 1) == 0;

          std::uint32_t packed_output = packed_input;
          std::uint32_t probe_output = packed_probe_input;
          if (pair_leader) {
            packed_output = ptx_ex2_approx_f16x2(packed_input);
            if (extra_exp_probe) {
              probe_output = ptx_ex2_approx_f16x2(packed_probe_input);
            }
            sink ^= probe_output;
          }
          const std::uint32_t pair_output = __shfl_sync(
              0xffffffffu, packed_output, lane & ~1);
          if (in_row) {
            values[0] = __half2float(
                (lane & 1) == 0 ? unpack_half_low(pair_output)
                                : unpack_half_high(pair_output));
            local_sum += values[0];
          } else {
            values[0] = 0.0f;
          }
        } else {
          static_assert((kElementsPerThread % 2) == 0,
                        "packed FP16 EX2 requires an even element count/thread");
#pragma unroll
          for (int element = 0; element < kElementsPerThread; element += 2) {
            const half input_low =
                __float2half_rn((values[element] - row_max) * kLog2E);
            const half input_high =
                __float2half_rn((values[element + 1] - row_max) * kLog2E);
            const std::uint32_t packed_output = ptx_ex2_approx_f16x2(
                pack_half_bits(input_low, input_high));
            const half output_low = unpack_half_low(packed_output);
            const half output_high = unpack_half_high(packed_output);
            values[element] = __half2float(output_low);
            values[element + 1] = __half2float(output_high);

            const std::uint32_t probe_input =
                pack_half_bits(input_low, input_high);
            std::uint32_t probe_output = probe_input;
            if (extra_exp_probe) {
              probe_output = ptx_ex2_approx_f16x2(probe_input);
            }
            sink ^= probe_output;
            local_sum += values[element] + values[element + 1];
          }
        }
      } else {
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          const int column = threadIdx.x + element * kThreadsPerBlock;
          if (column < Cols) {
            // At the registered scale range this stays positive while retaining
            // the same max/reduce/reciprocal/normalize control structure.
            values[element] = values[element] - row_max + 17.0f;
            local_sum += values[element];
          } else {
            values[element] = 0.0f;
          }
        }
      }
      const float row_sum = block_reduce_sum(local_sum, warp_values);
      const float inverse_sum = __fdividef(1.0f, row_sum);

#pragma unroll
      for (int element = 0; element < kElementsPerThread; ++element) {
        const int column = threadIdx.x + element * kThreadsPerBlock;
        if (column < Cols) {
          volatile_output[row * Cols + column] =
              __float2half_rn(values[element] * inverse_sum);
        }
      }
    }
    // Make each iteration's clock token a live data dependency without
    // perturbing the probability output used by the numerical check.
    sink = (sink << 5) | (sink >> 27);
  }

  if (threadIdx.x == 0 && token_by_block) {
    token_by_block[blockIdx.x] = sink;
  }
}

__global__ void native_ex2_validation_kernel(const half* input,
                                              half* scalar_output,
                                              half* packed_output,
                                              std::size_t count) {
  const std::size_t index =
      static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
  if (index < count) {
    scalar_output[index] = ptx_ex2_approx_f16(input[index]);
  }
  if ((index & 1u) == 0u && index + 1 < count) {
    const std::uint32_t packed = ptx_ex2_approx_f16x2(
        pack_half_bits(input[index], input[index + 1]));
    packed_output[index] = unpack_half_low(packed);
    packed_output[index + 1] = unpack_half_high(packed);
  }
}

__device__ __forceinline__ std::uint64_t splitmix64(std::uint64_t value) {
  value += 0x9e3779b97f4a7c15ull;
  value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ull;
  value = (value ^ (value >> 27)) * 0x94d049bb133111ebull;
  return value ^ (value >> 31);
}

__global__ void init_softmax_input_kernel(half* input, std::size_t count,
                                           float logit_scale,
                                           std::uint64_t seed) {
  const std::size_t tid = static_cast<std::size_t>(blockIdx.x) * blockDim.x +
                          threadIdx.x;
  const std::size_t stride = static_cast<std::size_t>(gridDim.x) * blockDim.x;
  for (std::size_t index = tid; index < count; index += stride) {
    const std::uint64_t bits = splitmix64(seed + index);
    const float unit = static_cast<float>((bits >> 40) & 0xffffffull) /
                       static_cast<float>(0x1000000ull);
    input[index] = __float2half_rn((2.0f * unit - 1.0f) * logit_scale);
  }
}

// Host-side launch helper.  It is intentionally separate from the occupancy
// helper below so the same template specializations are visible to both APIs.
template <int Cols, SoftmaxMode Mode, ExpImplementation ExpImpl,
          bool CacheGlobal>
cudaError_t launch_typed_kernel(const SoftmaxLaunchConfig& cfg,
                                std::uint64_t grid_blocks) {
  softmax_row_kernel<Cols, Mode, ExpImpl, CacheGlobal><<<
      static_cast<unsigned>(grid_blocks), kThreadsPerBlock, 0, cfg.stream>>>(
      cfg.input, cfg.output, cfg.token_by_block, cfg.iters,
      cfg.row_tiles_per_block, cfg.tile_stride, cfg.streaming,
      cfg.extra_exp_probe, cfg.smid_by_block, cfg.sm_counts,
      cfg.sm_count_capacity);
  return cudaGetLastError();
}

template <int Cols, SoftmaxMode Mode, ExpImplementation ExpImpl,
          bool CacheGlobal>
int occupancy_typed() {
  int blocks = 0;
  const cudaError_t status = cudaOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks, softmax_row_kernel<Cols, Mode, ExpImpl, CacheGlobal>,
      kThreadsPerBlock, 0);
  if (status != cudaSuccess) return 0;
  return blocks;
}

template <int Cols, SoftmaxMode Mode, ExpImplementation ExpImpl,
          bool CacheGlobal>
int binary_version_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, softmax_row_kernel<Cols, Mode, ExpImpl, CacheGlobal>);
  if (status != cudaSuccess) return 0;
  return attributes.binaryVersion;
}

template <int Cols, bool CacheGlobal>
cudaError_t launch_for_mode(const SoftmaxLaunchConfig& cfg,
                            std::uint64_t grid_blocks) {
  switch (cfg.mode) {
    case SoftmaxMode::full:
      switch (cfg.exp_implementation) {
        case ExpImplementation::fp32_expf:
          return launch_typed_kernel<Cols, SoftmaxMode::full,
                                     ExpImplementation::fp32_expf,
                                     CacheGlobal>(cfg, grid_blocks);
        case ExpImplementation::ptx_f16:
          return launch_typed_kernel<Cols, SoftmaxMode::full,
                                     ExpImplementation::ptx_f16,
                                     CacheGlobal>(cfg, grid_blocks);
        case ExpImplementation::ptx_f16x2:
          return launch_typed_kernel<Cols, SoftmaxMode::full,
                                     ExpImplementation::ptx_f16x2,
                                     CacheGlobal>(cfg, grid_blocks);
      }
      return cudaErrorInvalidValue;
    case SoftmaxMode::linear_control:
      return launch_typed_kernel<Cols, SoftmaxMode::linear_control,
                                 ExpImplementation::fp32_expf, CacheGlobal>(
          cfg, grid_blocks);
    case SoftmaxMode::io_control:
      return launch_typed_kernel<Cols, SoftmaxMode::io_control,
                                 ExpImplementation::fp32_expf, CacheGlobal>(
          cfg, grid_blocks);
  }
  return cudaErrorInvalidValue;
}

template <int Cols, bool CacheGlobal>
int occupancy_for_mode(SoftmaxMode mode,
                       ExpImplementation exp_implementation) {
  switch (mode) {
    case SoftmaxMode::full:
      switch (exp_implementation) {
        case ExpImplementation::fp32_expf:
          return occupancy_typed<Cols, SoftmaxMode::full,
                                 ExpImplementation::fp32_expf, CacheGlobal>();
        case ExpImplementation::ptx_f16:
          return occupancy_typed<Cols, SoftmaxMode::full,
                                 ExpImplementation::ptx_f16, CacheGlobal>();
        case ExpImplementation::ptx_f16x2:
          return occupancy_typed<Cols, SoftmaxMode::full,
                                 ExpImplementation::ptx_f16x2,
                                 CacheGlobal>();
      }
      return 0;
    case SoftmaxMode::linear_control:
      return occupancy_typed<Cols, SoftmaxMode::linear_control,
                             ExpImplementation::fp32_expf, CacheGlobal>();
    case SoftmaxMode::io_control:
      return occupancy_typed<Cols, SoftmaxMode::io_control,
                             ExpImplementation::fp32_expf, CacheGlobal>();
  }
  return 0;
}

template <int Cols, bool CacheGlobal>
int binary_version_for_mode(SoftmaxMode mode,
                            ExpImplementation exp_implementation) {
  switch (mode) {
    case SoftmaxMode::full:
      switch (exp_implementation) {
        case ExpImplementation::fp32_expf:
          return binary_version_typed<Cols, SoftmaxMode::full,
                                      ExpImplementation::fp32_expf,
                                      CacheGlobal>();
        case ExpImplementation::ptx_f16:
          return binary_version_typed<Cols, SoftmaxMode::full,
                                      ExpImplementation::ptx_f16,
                                      CacheGlobal>();
        case ExpImplementation::ptx_f16x2:
          return binary_version_typed<Cols, SoftmaxMode::full,
                                      ExpImplementation::ptx_f16x2,
                                      CacheGlobal>();
      }
      return 0;
    case SoftmaxMode::linear_control:
      return binary_version_typed<Cols, SoftmaxMode::linear_control,
                                  ExpImplementation::fp32_expf, CacheGlobal>();
    case SoftmaxMode::io_control:
      return binary_version_typed<Cols, SoftmaxMode::io_control,
                                  ExpImplementation::fp32_expf, CacheGlobal>();
  }
  return 0;
}

template <bool CacheGlobal>
cudaError_t launch_for_cols(const SoftmaxLaunchConfig& cfg,
                            std::uint64_t grid_blocks) {
  switch (cfg.softmax_cols) {
    case 128:
      return launch_for_mode<128, CacheGlobal>(cfg, grid_blocks);
    case 256:
      return launch_for_mode<256, CacheGlobal>(cfg, grid_blocks);
    case 512:
      return launch_for_mode<512, CacheGlobal>(cfg, grid_blocks);
    case 1024:
      return launch_for_mode<1024, CacheGlobal>(cfg, grid_blocks);
    case 2048:
      return launch_for_mode<2048, CacheGlobal>(cfg, grid_blocks);
    case 4096:
      return launch_for_mode<4096, CacheGlobal>(cfg, grid_blocks);
    default:
      return cudaErrorInvalidValue;
  }
}

template <bool CacheGlobal>
int occupancy_for_cols(SoftmaxMode mode, int cols,
                       ExpImplementation exp_implementation) {
  switch (cols) {
    case 128:
      return occupancy_for_mode<128, CacheGlobal>(mode, exp_implementation);
    case 256:
      return occupancy_for_mode<256, CacheGlobal>(mode, exp_implementation);
    case 512:
      return occupancy_for_mode<512, CacheGlobal>(mode, exp_implementation);
    case 1024:
      return occupancy_for_mode<1024, CacheGlobal>(mode, exp_implementation);
    case 2048:
      return occupancy_for_mode<2048, CacheGlobal>(mode, exp_implementation);
    case 4096:
      return occupancy_for_mode<4096, CacheGlobal>(mode, exp_implementation);
    default:
      return 0;
  }
}

template <bool CacheGlobal>
int binary_version_for_cols(SoftmaxMode mode, int cols,
                            ExpImplementation exp_implementation) {
  switch (cols) {
    case 128:
      return binary_version_for_mode<128, CacheGlobal>(mode,
                                                       exp_implementation);
    case 256:
      return binary_version_for_mode<256, CacheGlobal>(mode,
                                                       exp_implementation);
    case 512:
      return binary_version_for_mode<512, CacheGlobal>(mode,
                                                       exp_implementation);
    case 1024:
      return binary_version_for_mode<1024, CacheGlobal>(mode,
                                                        exp_implementation);
    case 2048:
      return binary_version_for_mode<2048, CacheGlobal>(mode,
                                                        exp_implementation);
    case 4096:
      return binary_version_for_mode<4096, CacheGlobal>(mode,
                                                        exp_implementation);
    default:
      return 0;
  }
}

}  // namespace

cudaError_t launch_softmax_kernel(const SoftmaxLaunchConfig& cfg) {
  if (!cfg.input || !cfg.output || cfg.iters == 0 ||
      cfg.row_tiles_per_block == 0 || cfg.grid_blocks == 0 ||
      cfg.grid_blocks > static_cast<std::uint64_t>(0xffffffffu)) {
    return cudaErrorInvalidValue;
  }
  return cfg.cache_policy == CachePolicy::cg
             ? launch_for_cols<true>(cfg, cfg.grid_blocks)
             : launch_for_cols<false>(cfg, cfg.grid_blocks);
}

cudaError_t launch_softmax_init(half* input, std::size_t count, float logit_scale,
                                std::uint64_t seed, cudaStream_t stream) {
  if (!input || count == 0 || !(logit_scale > 0.0f)) {
    return cudaErrorInvalidValue;
  }
  constexpr int kInitThreads = 256;
  const std::size_t blocks = std::min<std::size_t>(
      (count + kInitThreads - 1) / kInitThreads, static_cast<std::size_t>(65535));
  init_softmax_input_kernel<<<static_cast<unsigned>(blocks), kInitThreads, 0,
                              stream>>>(input, count, logit_scale, seed);
  return cudaGetLastError();
}

cudaError_t launch_native_ex2_validation(const half* input,
                                         half* scalar_output,
                                         half* packed_output,
                                         std::size_t count,
                                         cudaStream_t stream) {
  if (!input || !scalar_output || !packed_output || count == 0 ||
      (count & 1u) != 0u) {
    return cudaErrorInvalidValue;
  }
  constexpr int kValidationThreads = 256;
  const std::size_t blocks =
      (count + kValidationThreads - 1) / kValidationThreads;
  native_ex2_validation_kernel<<<static_cast<unsigned>(blocks),
                                 kValidationThreads, 0, stream>>>(
      input, scalar_output, packed_output, count);
  return cudaGetLastError();
}

int query_softmax_occupancy_max_blocks_per_sm(SoftmaxMode mode, int softmax_cols,
                                               CachePolicy cache_policy,
                                               ExpImplementation exp_implementation) {
  return cache_policy == CachePolicy::cg
             ? occupancy_for_cols<true>(mode, softmax_cols,
                                        exp_implementation)
             : occupancy_for_cols<false>(mode, softmax_cols,
                                         exp_implementation);
}

int query_softmax_binary_version(SoftmaxMode mode, int softmax_cols,
                                 CachePolicy cache_policy,
                                 ExpImplementation exp_implementation) {
  return cache_policy == CachePolicy::cg
             ? binary_version_for_cols<true>(mode, softmax_cols,
                                             exp_implementation)
             : binary_version_for_cols<false>(mode, softmax_cols,
                                              exp_implementation);
}

}  // namespace fp16softmax
