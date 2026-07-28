#include "softmax_whole_precision_kernels.cuh"

#include <algorithm>
#include <limits>

// This translation unit deliberately backs only the new endpoint-range
// binary.  The frozen stage-isolation and targeted-confirmation targets keep
// compiling src/softmax_whole_precision_kernels.cu, so their historical S=512
// SASS/binary provenance is not changed by range-specialization work.
namespace fp16softmax::whole_precision {
namespace {

constexpr int kWarpsPerBlock = kThreadsPerBlock / 32;
constexpr float kLog2E = 1.4426950408889634f;

template <Policy>
struct Traits;

#define ENDPOINT_RANGE_TRAITS(ID, IO, EXP, REDUCTION, NORMALIZATION)        \
  template <>                                                                 \
  struct Traits<Policy::ID> {                                                 \
    static constexpr IoImplementation kIo = IoImplementation::IO;            \
    static constexpr StageImplementation kExp = StageImplementation::EXP;    \
    static constexpr StageImplementation kReduction =                         \
        StageImplementation::REDUCTION;                                       \
    static constexpr StageImplementation kNormalization =                     \
        StageImplementation::NORMALIZATION;                                   \
  }

ENDPOINT_RANGE_TRAITS(fp32_io_fp32_all, fp32, fp32, fp32, fp32);
ENDPOINT_RANGE_TRAITS(fp16_scalar_all, fp16, fp16_scalar, fp16_scalar,
                      fp16_scalar);
ENDPOINT_RANGE_TRAITS(fp16x2_all, fp16, fp16x2_packed, fp16x2_packed,
                      fp16x2_packed);

#undef ENDPOINT_RANGE_TRAITS

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

// The packed reduction uses the two independent CTA rows as half2 lanes.  The
// packed exp and normalization paths, by contrast, pack adjacent elements in
// one logical row.  Each thread owns one contiguous chunk below, so element
// pairs are actual neighboring columns rather than two strided columns that
// merely happen to be held by the same thread.  Both mappings are explicit in
// the range protocol and are genuine two-half operations; neither is counted
// as two independent scalar instructions.
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

template <int SoftmaxCols, Policy P>
__global__ void whole_precision_range_softmax_kernel(
    const half* input_f16, const float* input_f32, half* output_f16,
    float* output_f32, std::uint32_t* token_by_block, std::uint64_t iters,
    int* smid_by_block, int* sm_counts, int sm_count_capacity) {
  static_assert(SoftmaxCols % kThreadsPerBlock == 0,
                "range Softmax widths must divide the 256-thread CTA");
  constexpr int kElements = SoftmaxCols / kThreadsPerBlock;
  static_assert(kElements >= 2 && (kElements % 2) == 0,
                "range target preserves adjacent f16x2 pairs per thread");
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

  float f[kRowsPerBlock][kElements];
  half h[kRowsPerBlock][kElements];
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
      for (int element = 0; element < kElements; ++element) {
        const std::size_t index = static_cast<std::size_t>(row) * SoftmaxCols +
            static_cast<std::size_t>(threadIdx.x) * kElements + element;
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
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        float local = f[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = fmaxf(local, f[row_lane][element]);
        }
        row_max_f[row_lane] = block_max_float(local, warp_values);
        row_max_h[row_lane] = __float2half_rn(row_max_f[row_lane]);
      }
    } else if constexpr (kReduction == StageImplementation::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        half local = h[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = __hmax(local, h[row_lane][element]);
        }
        row_max_h[row_lane] = block_max_half(local, scalar_reduce);
        row_max_f[row_lane] = __half2float(row_max_h[row_lane]);
      }
    } else {
      half2 local = __halves2half2(h[0][0], h[1][0]);
#pragma unroll
      for (int element = 1; element < kElements; ++element) {
        local = __hmax2(local, __halves2half2(h[0][element], h[1][element]));
      }
      const half2 result = block_max_half2(local, packed_reduce);
      row_max_h[0] = __low2half(result);
      row_max_h[1] = __high2half(result);
      row_max_f[0] = __half2float(row_max_h[0]);
      row_max_f[1] = __half2float(row_max_h[1]);
    }

    if constexpr (kExp == StageImplementation::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          f[row_lane][element] = __expf(f[row_lane][element] - row_max_f[row_lane]);
          h[row_lane][element] = __float2half_rn(f[row_lane][element]);
        }
      }
    } else if constexpr (kExp == StageImplementation::fp16_scalar) {
      const half log2e = __float2half_rn(kLog2E);
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
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
#pragma unroll
        for (int element = 0; element < kElements; element += 2) {
          const half2 inputs = __hmul2(
              __hsub2(__halves2half2(h[row_lane][element], h[row_lane][element + 1]),
                      __halves2half2(row_max_h[row_lane], row_max_h[row_lane])),
              log2e);
          const std::uint32_t packed = ptx_ex2_approx_f16x2(
              pack_half_bits(__low2half(inputs), __high2half(inputs)));
          h[row_lane][element] = unpack_half_low(packed);
          h[row_lane][element + 1] = unpack_half_high(packed);
          f[row_lane][element] = __half2float(h[row_lane][element]);
          f[row_lane][element + 1] = __half2float(h[row_lane][element + 1]);
        }
      }
    }

    float row_sum_f[kRowsPerBlock] = {};
    half row_sum_h[kRowsPerBlock] = {};
    if constexpr (kReduction == StageImplementation::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        float local = 0.0f;
#pragma unroll
        for (int element = 0; element < kElements; ++element) local += f[row_lane][element];
        row_sum_f[row_lane] = block_sum_float(local, warp_values);
        row_sum_h[row_lane] = __float2half_rn(row_sum_f[row_lane]);
      }
    } else if constexpr (kReduction == StageImplementation::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        half local = h[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = __hadd(local, h[row_lane][element]);
        }
        row_sum_h[row_lane] = block_sum_half(local, scalar_reduce);
        row_sum_f[row_lane] = __half2float(row_sum_h[row_lane]);
      }
    } else {
      half2 local = __halves2half2(h[0][0], h[1][0]);
#pragma unroll
      for (int element = 1; element < kElements; ++element) {
        local = __hadd2(local, __halves2half2(h[0][element], h[1][element]));
      }
      const half2 result = block_sum_half2(local, packed_reduce);
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
        for (int element = 0; element < kElements; ++element) {
          f[row_lane][element] *= inverse;
          h[row_lane][element] = __float2half_rn(f[row_lane][element]);
        }
      }
    } else if constexpr (kNormalization == StageImplementation::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const half inverse = hrcp(row_sum_h[row_lane]);
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          h[row_lane][element] = __hmul(h[row_lane][element], inverse);
          f[row_lane][element] = __half2float(h[row_lane][element]);
        }
      }
    } else {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const half inverse = hrcp(row_sum_h[row_lane]);
#pragma unroll
        for (int element = 0; element < kElements; element += 2) {
          const half2 result = __hmul2(
              __halves2half2(h[row_lane][element], h[row_lane][element + 1]),
              __halves2half2(inverse, inverse));
          h[row_lane][element] = __low2half(result);
          h[row_lane][element + 1] = __high2half(result);
          f[row_lane][element] = __half2float(h[row_lane][element]);
          f[row_lane][element + 1] = __half2float(h[row_lane][element + 1]);
        }
      }
    }

#pragma unroll
    for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
      const std::uint64_t row = first_row + row_lane;
#pragma unroll
      for (int element = 0; element < kElements; ++element) {
        const std::size_t index = static_cast<std::size_t>(row) * SoftmaxCols +
            static_cast<std::size_t>(threadIdx.x) * kElements + element;
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
    const half quantized = __float2half_rn((2.0f * unit - 1.0f) * logit_scale);
    input_f16[current] = quantized;
    input_f32[current] = __half2float(quantized);
  }
}

template <int SoftmaxCols, Policy P>
cudaError_t launch_typed(const LaunchConfig& config) {
  whole_precision_range_softmax_kernel<SoftmaxCols, P><<<
      static_cast<unsigned>(config.grid_blocks), kThreadsPerBlock, 0,
      config.stream>>>(config.input_f16, config.input_f32, config.output_f16,
                       config.output_f32, config.token_by_block, config.iters,
                       config.smid_by_block, config.sm_counts,
                       config.sm_count_capacity);
  return cudaGetLastError();
}

template <int SoftmaxCols, Policy P>
int occupancy_typed() {
  int blocks = 0;
  const cudaError_t status = cudaOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks, whole_precision_range_softmax_kernel<SoftmaxCols, P>,
      kThreadsPerBlock, 0);
  return status == cudaSuccess ? blocks : 0;
}

template <int SoftmaxCols, Policy P>
int binary_version_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, whole_precision_range_softmax_kernel<SoftmaxCols, P>);
  return status == cudaSuccess ? attributes.binaryVersion : 0;
}

template <int SoftmaxCols>
cudaError_t dispatch_launch(Policy policy, const LaunchConfig& config) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return launch_typed<SoftmaxCols, Policy::fp32_io_fp32_all>(config);
    case Policy::fp16_scalar_all:
      return launch_typed<SoftmaxCols, Policy::fp16_scalar_all>(config);
    case Policy::fp16x2_all:
      return launch_typed<SoftmaxCols, Policy::fp16x2_all>(config);
    default:
      return cudaErrorInvalidValue;
  }
}

template <int SoftmaxCols>
int dispatch_occupancy(Policy policy) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return occupancy_typed<SoftmaxCols, Policy::fp32_io_fp32_all>();
    case Policy::fp16_scalar_all:
      return occupancy_typed<SoftmaxCols, Policy::fp16_scalar_all>();
    case Policy::fp16x2_all:
      return occupancy_typed<SoftmaxCols, Policy::fp16x2_all>();
    default:
      return 0;
  }
}

template <int SoftmaxCols>
int dispatch_binary_version(Policy policy) {
  switch (policy) {
    case Policy::fp32_io_fp32_all:
      return binary_version_typed<SoftmaxCols, Policy::fp32_io_fp32_all>();
    case Policy::fp16_scalar_all:
      return binary_version_typed<SoftmaxCols, Policy::fp16_scalar_all>();
    case Policy::fp16x2_all:
      return binary_version_typed<SoftmaxCols, Policy::fp16x2_all>();
    default:
      return 0;
  }
}

cudaError_t dispatch_launch_cols(Policy policy, const LaunchConfig& config) {
  switch (config.softmax_cols) {
    case 512:
      return dispatch_launch<512>(policy, config);
    case 1024:
      return dispatch_launch<1024>(policy, config);
    case 2048:
      return dispatch_launch<2048>(policy, config);
    case 4096:
      return dispatch_launch<4096>(policy, config);
    default:
      return cudaErrorInvalidValue;
  }
}

int dispatch_occupancy_cols(Policy policy, int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_occupancy<512>(policy);
    case 1024:
      return dispatch_occupancy<1024>(policy);
    case 2048:
      return dispatch_occupancy<2048>(policy);
    case 4096:
      return dispatch_occupancy<4096>(policy);
    default:
      return 0;
  }
}

int dispatch_binary_version_cols(Policy policy, int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_binary_version<512>(policy);
    case 1024:
      return dispatch_binary_version<1024>(policy);
    case 2048:
      return dispatch_binary_version<2048>(policy);
    case 4096:
      return dispatch_binary_version<4096>(policy);
    default:
      return 0;
  }
}

}  // namespace

cudaError_t launch_kernel(const LaunchConfig& config) {
  if (!config.input_f16 || !config.input_f32 || !config.output_f16 ||
      !config.output_f32 || config.grid_blocks == 0 || config.iters == 0 ||
      config.grid_blocks > static_cast<std::uint64_t>(0xffffffffu) ||
      !is_range_softmax_cols(config.softmax_cols) ||
      !is_endpoint_policy(config.policy)) {
    return cudaErrorInvalidValue;
  }
  if (uses_native_fp16_ex2(config.policy)) {
    int device = -1;
    cudaDeviceProp properties{};
    cudaError_t status = cudaGetDevice(&device);
    if (status != cudaSuccess) return status;
    status = cudaGetDeviceProperties(&properties, device);
    if (status != cudaSuccess) return status;
    if (properties.major * 10 + properties.minor < 75) return cudaErrorNotSupported;
  }
  return dispatch_launch_cols(config.policy, config);
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

int query_occupancy_max_blocks_per_sm(Policy policy, int softmax_cols) {
  if (!is_range_softmax_cols(softmax_cols) || !is_endpoint_policy(policy)) return 0;
  return dispatch_occupancy_cols(policy, softmax_cols);
}

int query_binary_version(Policy policy, int softmax_cols) {
  if (!is_range_softmax_cols(softmax_cols) || !is_endpoint_policy(policy)) return 0;
  return dispatch_binary_version_cols(policy, softmax_cols);
}

}  // namespace fp16softmax::whole_precision
