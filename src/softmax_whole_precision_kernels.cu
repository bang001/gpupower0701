#include "softmax_whole_precision_kernels.cuh"

#include <algorithm>
#include <limits>

namespace fp16softmax::whole_precision {
namespace {

constexpr int kWarpsPerBlock = kThreadsPerBlock / 32;
constexpr float kLog2E = 1.4426950408889634f;

template <Policy>
struct Traits;

#define WHOLE_PRECISION_TRAITS(ID, IO, EXP, REDUCTION, NORMALIZATION)       \
  template <>                                                                \
  struct Traits<Policy::ID> {                                                \
    static constexpr IoImplementation kIo = IoImplementation::IO;           \
    static constexpr StageImplementation kExp = StageImplementation::EXP;   \
    static constexpr StageImplementation kReduction =                         \
        StageImplementation::REDUCTION;                                      \
    static constexpr StageImplementation kNormalization =                     \
        StageImplementation::NORMALIZATION;                                  \
  }

WHOLE_PRECISION_TRAITS(fp32_io_fp32_all, fp32, fp32, fp32, fp32);
WHOLE_PRECISION_TRAITS(fp16_io_fp32_all, fp16, fp32, fp32, fp32);
WHOLE_PRECISION_TRAITS(exp_fp16_scalar, fp16, fp16_scalar, fp32, fp32);
WHOLE_PRECISION_TRAITS(exp_fp16x2, fp16, fp16x2_packed, fp32, fp32);
WHOLE_PRECISION_TRAITS(reduction_fp16_scalar, fp16, fp32, fp16_scalar, fp32);
WHOLE_PRECISION_TRAITS(reduction_fp16x2, fp16, fp32, fp16x2_packed, fp32);
WHOLE_PRECISION_TRAITS(normalization_fp16_scalar, fp16, fp32, fp32,
                       fp16_scalar);
WHOLE_PRECISION_TRAITS(normalization_fp16x2, fp16, fp32, fp32, fp16x2_packed);
WHOLE_PRECISION_TRAITS(fp16_scalar_all, fp16, fp16_scalar, fp16_scalar,
                       fp16_scalar);
WHOLE_PRECISION_TRAITS(fp16x2_all, fp16, fp16x2_packed, fp16x2_packed,
                       fp16x2_packed);

#undef WHOLE_PRECISION_TRAITS

__device__ __forceinline__ unsigned read_smid() {
  unsigned smid = 0;
  asm volatile("mov.u32 %0, %%smid;" : "=r"(smid));
  return smid;
}

__device__ __forceinline__ unsigned read_clock_token() {
  unsigned value = 0;
  asm volatile("mov.u32 %0, %%clock;" : "=r"(value));
  return value;
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

__device__ __forceinline__ half ptx_ex2_approx_f16(half input) {
  unsigned short output = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16 %0, %1;" : "=h"(output)
                                      : "h"(__half_as_ushort(input)));
#else
#if defined(__CUDA_ARCH__)
  asm volatile("trap;");
#endif
#endif
  return __ushort_as_half(output);
}

__device__ __forceinline__ std::uint32_t ptx_ex2_approx_f16x2(
    std::uint32_t input) {
  std::uint32_t output = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16x2 %0, %1;" : "=r"(output) : "r"(input));
#else
#if defined(__CUDA_ARCH__)
  asm volatile("trap;");
#endif
#endif
  return output;
}

__device__ __forceinline__ float warp_max(float value) {
  for (int offset = 16; offset > 0; offset >>= 1) {
    value = fmaxf(value, __shfl_down_sync(0xffffffffu, value, offset));
  }
  return value;
}

__device__ __forceinline__ float warp_sum(float value) {
  for (int offset = 16; offset > 0; offset >>= 1) {
    value += __shfl_down_sync(0xffffffffu, value, offset);
  }
  return value;
}

__device__ __forceinline__ float block_max_float(float value,
                                                   float* warp_values) {
  const int lane = threadIdx.x & 31;
  const int warp = threadIdx.x >> 5;
  value = warp_max(value);
  if (lane == 0) warp_values[warp] = value;
  __syncthreads();
  value = threadIdx.x < kWarpsPerBlock
              ? warp_values[lane]
              : -std::numeric_limits<float>::infinity();
  if (warp == 0) value = warp_max(value);
  if (threadIdx.x == 0) warp_values[0] = value;
  __syncthreads();
  const float result = warp_values[0];
  // All threads must consume the broadcast value before a subsequent row's
  // collective can reuse this shared array.
  __syncthreads();
  return result;
}

__device__ __forceinline__ float block_sum_float(float value,
                                                   float* warp_values) {
  const int lane = threadIdx.x & 31;
  const int warp = threadIdx.x >> 5;
  value = warp_sum(value);
  if (lane == 0) warp_values[warp] = value;
  __syncthreads();
  value = threadIdx.x < kWarpsPerBlock ? warp_values[lane] : 0.0f;
  if (warp == 0) value = warp_sum(value);
  if (threadIdx.x == 0) warp_values[0] = value;
  __syncthreads();
  const float result = warp_values[0];
  __syncthreads();
  return result;
}

// The scalar FP16 tree is deliberately explicit.  We do not infer FP16
// accumulation merely from a half register; the companion SASS audit checks
// the final lowering before results are called FP16-accumulation evidence.
__device__ __forceinline__ half block_max_half(half value, half* shared) {
  shared[threadIdx.x] = value;
  __syncthreads();
  for (int stride = kThreadsPerBlock / 2; stride > 0; stride >>= 1) {
    if (threadIdx.x < stride) {
      shared[threadIdx.x] = __hmax(shared[threadIdx.x],
                                   shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half result = shared[0];
  __syncthreads();
  return result;
}

__device__ __forceinline__ half block_sum_half(half value, half* shared) {
  shared[threadIdx.x] = value;
  __syncthreads();
  for (int stride = kThreadsPerBlock / 2; stride > 0; stride >>= 1) {
    if (threadIdx.x < stride) {
      shared[threadIdx.x] = __hadd(shared[threadIdx.x],
                                   shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half result = shared[0];
  __syncthreads();
  return result;
}

// `half2` lanes represent the two independent rows processed by a CTA.  Thus
// hmax2/hadd2 are genuine pairwise reductions, while the policy metadata
// truthfully records that the vector tree is across rows rather than a magic
// horizontal two-element reduction within one row.
__device__ __forceinline__ half2 block_max_half2(half2 value, half2* shared) {
  shared[threadIdx.x] = value;
  __syncthreads();
  for (int stride = kThreadsPerBlock / 2; stride > 0; stride >>= 1) {
    if (threadIdx.x < stride) {
      shared[threadIdx.x] = __hmax2(shared[threadIdx.x],
                                    shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half2 result = shared[0];
  __syncthreads();
  return result;
}

__device__ __forceinline__ half2 block_sum_half2(half2 value, half2* shared) {
  shared[threadIdx.x] = value;
  __syncthreads();
  for (int stride = kThreadsPerBlock / 2; stride > 0; stride >>= 1) {
    if (threadIdx.x < stride) {
      shared[threadIdx.x] = __hadd2(shared[threadIdx.x],
                                    shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half2 result = shared[0];
  __syncthreads();
  return result;
}

template <Policy P>
__global__ void whole_precision_softmax_kernel(
    const half* input_f16, const float* input_f32, half* output_f16,
    float* output_f32, std::uint32_t* token_by_block, std::uint64_t iters,
    int* smid_by_block, int* sm_counts, int sm_count_capacity) {
  constexpr IoImplementation kIo = Traits<P>::kIo;
  constexpr StageImplementation kExp = Traits<P>::kExp;
  constexpr StageImplementation kReduction = Traits<P>::kReduction;
  constexpr StageImplementation kNormalization = Traits<P>::kNormalization;

  const unsigned smid = read_smid();
  if (threadIdx.x == 0) {
    if (smid_by_block) smid_by_block[blockIdx.x] = static_cast<int>(smid);
    if (sm_counts && static_cast<int>(smid) < sm_count_capacity) {
      atomicAdd(sm_counts + smid, 1);
    }
  }

  __shared__ float warp_values[kWarpsPerBlock];
  __shared__ half scalar_reduce[kThreadsPerBlock];
  __shared__ half2 packed_reduce[kThreadsPerBlock];

  float f[kRowsPerBlock][kElementsPerThread];
  half h[kRowsPerBlock][kElementsPerThread];
  unsigned sink = (static_cast<unsigned>(blockIdx.x) + 1u) * 0x9e3779b9u ^
                  (static_cast<unsigned>(threadIdx.x) + 17u);
  const std::uint64_t first_row =
      static_cast<std::uint64_t>(blockIdx.x) * kRowsPerBlock;

  for (std::uint64_t iteration = 0; iteration < iters; ++iteration) {
    sink ^= read_clock_token() + static_cast<unsigned>(iteration);

#pragma unroll
    for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
      const std::uint64_t row = first_row + row_lane;
#pragma unroll
      for (int element = 0; element < kElementsPerThread; ++element) {
        const std::size_t index = static_cast<std::size_t>(row) * kSoftmaxCols +
            threadIdx.x + element * kThreadsPerBlock;
        if constexpr (kIo == IoImplementation::fp32) {
          const volatile float* source = input_f32 + index;
          f[row_lane][element] = *source;
          h[row_lane][element] = __float2half_rn(f[row_lane][element]);
        } else {
          const volatile half* source = input_f16 + index;
          h[row_lane][element] = *source;
          f[row_lane][element] = __half2float(h[row_lane][element]);
        }
      }
    }

    float row_max_f[kRowsPerBlock] = {};
    half row_max_h[kRowsPerBlock] = {};
    if constexpr (kReduction == StageImplementation::fp32) {
      row_max_f[0] = block_max_float(f[0][0] > f[0][1] ? f[0][0] : f[0][1],
                                      warp_values);
      row_max_f[1] = block_max_float(f[1][0] > f[1][1] ? f[1][0] : f[1][1],
                                      warp_values);
      row_max_h[0] = __float2half_rn(row_max_f[0]);
      row_max_h[1] = __float2half_rn(row_max_f[1]);
    } else if constexpr (kReduction == StageImplementation::fp16_scalar) {
      row_max_h[0] = block_max_half(__hmax(h[0][0], h[0][1]), scalar_reduce);
      row_max_h[1] = block_max_half(__hmax(h[1][0], h[1][1]), scalar_reduce);
      row_max_f[0] = __half2float(row_max_h[0]);
      row_max_f[1] = __half2float(row_max_h[1]);
    } else {
      const half2 local_max = __hmax2(
          __halves2half2(h[0][0], h[1][0]),
          __halves2half2(h[0][1], h[1][1]));
      const half2 result = block_max_half2(local_max, packed_reduce);
      row_max_h[0] = __low2half(result);
      row_max_h[1] = __high2half(result);
      row_max_f[0] = __half2float(row_max_h[0]);
      row_max_f[1] = __half2float(row_max_h[1]);
    }

    if constexpr (kExp == StageImplementation::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          f[row_lane][element] = __expf(f[row_lane][element] - row_max_f[row_lane]);
          h[row_lane][element] = __float2half_rn(f[row_lane][element]);
        }
      }
    } else if constexpr (kExp == StageImplementation::fp16_scalar) {
      const half log2e = __float2half_rn(kLog2E);
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          const half exponent_input = __hmul(
              __hsub(h[row_lane][element], row_max_h[row_lane]), log2e);
          h[row_lane][element] = ptx_ex2_approx_f16(exponent_input);
          f[row_lane][element] = __half2float(h[row_lane][element]);
        }
      }
    } else {
      const half2 log2e = __float2half2_rn(kLog2E);
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const half2 inputs = __hmul2(
            __hsub2(__halves2half2(h[row_lane][0], h[row_lane][1]),
                    __halves2half2(row_max_h[row_lane], row_max_h[row_lane])),
            log2e);
        const std::uint32_t packed = ptx_ex2_approx_f16x2(
            pack_half_bits(__low2half(inputs), __high2half(inputs)));
        h[row_lane][0] = unpack_half_low(packed);
        h[row_lane][1] = unpack_half_high(packed);
        f[row_lane][0] = __half2float(h[row_lane][0]);
        f[row_lane][1] = __half2float(h[row_lane][1]);
      }
    }

    float row_sum_f[kRowsPerBlock] = {};
    half row_sum_h[kRowsPerBlock] = {};
    if constexpr (kReduction == StageImplementation::fp32) {
      row_sum_f[0] = block_sum_float(f[0][0] + f[0][1], warp_values);
      row_sum_f[1] = block_sum_float(f[1][0] + f[1][1], warp_values);
      row_sum_h[0] = __float2half_rn(row_sum_f[0]);
      row_sum_h[1] = __float2half_rn(row_sum_f[1]);
    } else if constexpr (kReduction == StageImplementation::fp16_scalar) {
      row_sum_h[0] = block_sum_half(__hadd(h[0][0], h[0][1]), scalar_reduce);
      row_sum_h[1] = block_sum_half(__hadd(h[1][0], h[1][1]), scalar_reduce);
      row_sum_f[0] = __half2float(row_sum_h[0]);
      row_sum_f[1] = __half2float(row_sum_h[1]);
    } else {
      const half2 local_sum = __hadd2(
          __halves2half2(h[0][0], h[1][0]),
          __halves2half2(h[0][1], h[1][1]));
      const half2 result = block_sum_half2(local_sum, packed_reduce);
      row_sum_h[0] = __low2half(result);
      row_sum_h[1] = __high2half(result);
      row_sum_f[0] = __half2float(row_sum_h[0]);
      row_sum_f[1] = __half2float(row_sum_h[1]);
    }

    if constexpr (kNormalization == StageImplementation::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const float inverse = __fdividef(1.0f, row_sum_f[row_lane]);
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          f[row_lane][element] *= inverse;
          h[row_lane][element] = __float2half_rn(f[row_lane][element]);
        }
      }
    } else if constexpr (kNormalization == StageImplementation::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const half inverse = hrcp(row_sum_h[row_lane]);
#pragma unroll
        for (int element = 0; element < kElementsPerThread; ++element) {
          h[row_lane][element] = __hmul(h[row_lane][element], inverse);
          f[row_lane][element] = __half2float(h[row_lane][element]);
        }
      }
    } else {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const half inverse = hrcp(row_sum_h[row_lane]);
        const half2 result = __hmul2(
            __halves2half2(h[row_lane][0], h[row_lane][1]),
            __halves2half2(inverse, inverse));
        h[row_lane][0] = __low2half(result);
        h[row_lane][1] = __high2half(result);
        f[row_lane][0] = __half2float(h[row_lane][0]);
        f[row_lane][1] = __half2float(h[row_lane][1]);
      }
    }

#pragma unroll
    for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
      const std::uint64_t row = first_row + row_lane;
#pragma unroll
      for (int element = 0; element < kElementsPerThread; ++element) {
        const std::size_t index = static_cast<std::size_t>(row) * kSoftmaxCols +
            threadIdx.x + element * kThreadsPerBlock;
        if constexpr (kIo == IoImplementation::fp32) {
          volatile float* target = output_f32 + index;
          *target = f[row_lane][element];
          sink ^= __float_as_uint(f[row_lane][element]);
        } else {
          volatile half* target = output_f16 + index;
          *target = h[row_lane][element];
          sink ^= static_cast<unsigned>(__half_as_ushort(h[row_lane][element]));
        }
      }
    }
    sink = (sink << 5) | (sink >> 27);
  }

  if (threadIdx.x == 0 && token_by_block) token_by_block[blockIdx.x] = sink;
}

__device__ __forceinline__ std::uint64_t splitmix64(std::uint64_t value) {
  value += 0x9e3779b97f4a7c15ull;
  value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ull;
  value = (value ^ (value >> 27)) * 0x94d049bb133111ebull;
  return value ^ (value >> 31);
}

__global__ void init_inputs_kernel(half* input_f16, float* input_f32,
                                   std::size_t count, float logit_scale,
                                   std::uint64_t seed) {
  const std::size_t index = static_cast<std::size_t>(blockIdx.x) * blockDim.x +
      threadIdx.x;
  const std::size_t stride = static_cast<std::size_t>(gridDim.x) * blockDim.x;
  for (std::size_t current = index; current < count; current += stride) {
    const std::uint64_t bits = splitmix64(seed + current);
    const float unit = static_cast<float>((bits >> 40) & 0xffffffull) /
        static_cast<float>(0x1000000ull);
    // The canonical FP32 stimulus is the exactly promoted FP16 value.  This
    // holds the logical logits fixed while intentionally retaining policy I/O
    // bytes as part of end-to-end energy.
    const half quantized = __float2half_rn((2.0f * unit - 1.0f) * logit_scale);
    input_f16[current] = quantized;
    input_f32[current] = __half2float(quantized);
  }
}

template <Policy P>
cudaError_t launch_typed(const LaunchConfig& config) {
  whole_precision_softmax_kernel<P><<<
      static_cast<unsigned>(config.grid_blocks), kThreadsPerBlock, 0,
      config.stream>>>(config.input_f16, config.input_f32, config.output_f16,
                       config.output_f32, config.token_by_block, config.iters,
                       config.smid_by_block, config.sm_counts,
                       config.sm_count_capacity);
  return cudaGetLastError();
}

template <Policy P>
int occupancy_typed() {
  int blocks = 0;
  const cudaError_t status = cudaOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks, whole_precision_softmax_kernel<P>, kThreadsPerBlock, 0);
  return status == cudaSuccess ? blocks : 0;
}

template <Policy P>
int binary_version_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, whole_precision_softmax_kernel<P>);
  return status == cudaSuccess ? attributes.binaryVersion : 0;
}

cudaError_t dispatch_launch(Policy policy, const LaunchConfig& config) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return launch_typed<Policy::fp32_io_fp32_all>(config);
    case Policy::fp16_io_fp32_all:
      return launch_typed<Policy::fp16_io_fp32_all>(config);
    case Policy::exp_fp16_scalar:
      return launch_typed<Policy::exp_fp16_scalar>(config);
    case Policy::exp_fp16x2:
      return launch_typed<Policy::exp_fp16x2>(config);
    case Policy::reduction_fp16_scalar:
      return launch_typed<Policy::reduction_fp16_scalar>(config);
    case Policy::reduction_fp16x2:
      return launch_typed<Policy::reduction_fp16x2>(config);
    case Policy::normalization_fp16_scalar:
      return launch_typed<Policy::normalization_fp16_scalar>(config);
    case Policy::normalization_fp16x2:
      return launch_typed<Policy::normalization_fp16x2>(config);
    case Policy::fp16_scalar_all:
      return launch_typed<Policy::fp16_scalar_all>(config);
    case Policy::fp16x2_all:
      return launch_typed<Policy::fp16x2_all>(config);
  }
  return cudaErrorInvalidValue;
}

int dispatch_occupancy(Policy policy) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return occupancy_typed<Policy::fp32_io_fp32_all>();
    case Policy::fp16_io_fp32_all:
      return occupancy_typed<Policy::fp16_io_fp32_all>();
    case Policy::exp_fp16_scalar:
      return occupancy_typed<Policy::exp_fp16_scalar>();
    case Policy::exp_fp16x2:
      return occupancy_typed<Policy::exp_fp16x2>();
    case Policy::reduction_fp16_scalar:
      return occupancy_typed<Policy::reduction_fp16_scalar>();
    case Policy::reduction_fp16x2:
      return occupancy_typed<Policy::reduction_fp16x2>();
    case Policy::normalization_fp16_scalar:
      return occupancy_typed<Policy::normalization_fp16_scalar>();
    case Policy::normalization_fp16x2:
      return occupancy_typed<Policy::normalization_fp16x2>();
    case Policy::fp16_scalar_all:
      return occupancy_typed<Policy::fp16_scalar_all>();
    case Policy::fp16x2_all:
      return occupancy_typed<Policy::fp16x2_all>();
  }
  return 0;
}

int dispatch_binary_version(Policy policy) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return binary_version_typed<Policy::fp32_io_fp32_all>();
    case Policy::fp16_io_fp32_all:
      return binary_version_typed<Policy::fp16_io_fp32_all>();
    case Policy::exp_fp16_scalar:
      return binary_version_typed<Policy::exp_fp16_scalar>();
    case Policy::exp_fp16x2:
      return binary_version_typed<Policy::exp_fp16x2>();
    case Policy::reduction_fp16_scalar:
      return binary_version_typed<Policy::reduction_fp16_scalar>();
    case Policy::reduction_fp16x2:
      return binary_version_typed<Policy::reduction_fp16x2>();
    case Policy::normalization_fp16_scalar:
      return binary_version_typed<Policy::normalization_fp16_scalar>();
    case Policy::normalization_fp16x2:
      return binary_version_typed<Policy::normalization_fp16x2>();
    case Policy::fp16_scalar_all:
      return binary_version_typed<Policy::fp16_scalar_all>();
    case Policy::fp16x2_all:
      return binary_version_typed<Policy::fp16x2_all>();
  }
  return 0;
}

}  // namespace

cudaError_t launch_kernel(const LaunchConfig& config) {
  if (!config.input_f16 || !config.input_f32 || !config.output_f16 ||
      !config.output_f32 || config.grid_blocks == 0 || config.iters == 0 ||
      config.grid_blocks > static_cast<std::uint64_t>(0xffffffffu)) {
    return cudaErrorInvalidValue;
  }
  if (uses_native_fp16_ex2(config.policy)) {
    int device = -1;
    cudaDeviceProp properties{};
    cudaError_t status = cudaGetDevice(&device);
    if (status != cudaSuccess) return status;
    status = cudaGetDeviceProperties(&properties, device);
    if (status != cudaSuccess) return status;
    if (properties.major * 10 + properties.minor < 75) {
      return cudaErrorNotSupported;
    }
  }
  return dispatch_launch(config.policy, config);
}

cudaError_t launch_init(half* input_f16, float* input_f32, std::size_t count,
                        float logit_scale, std::uint64_t seed,
                        cudaStream_t stream) {
  if (!input_f16 || !input_f32 || count == 0 || !(logit_scale > 0.0f)) {
    return cudaErrorInvalidValue;
  }
  constexpr int kInitThreads = 256;
  const std::size_t blocks = std::min<std::size_t>(
      (count + kInitThreads - 1) / kInitThreads,
      static_cast<std::size_t>(65535));
  init_inputs_kernel<<<static_cast<unsigned>(blocks), kInitThreads, 0, stream>>>(
      input_f16, input_f32, count, logit_scale, seed);
  return cudaGetLastError();
}

int query_occupancy_max_blocks_per_sm(Policy policy) {
  return dispatch_occupancy(policy);
}

int query_binary_version(Policy policy) {
  return dispatch_binary_version(policy);
}

}  // namespace fp16softmax::whole_precision
