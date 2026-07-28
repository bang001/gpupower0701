#include "softmax_whole_stage_atc_kernels.cuh"

#include <algorithm>
#include <limits>

namespace fp16softmax::whole_stage_atc {
namespace {

constexpr int kWarpsPerBlock = kThreadsPerBlock / 32;
constexpr float kLog2E = 1.4426950408889634f;

__device__ __forceinline__ unsigned read_smid() {
  unsigned smid = 0;
  asm volatile("mov.u32 %0, %%smid;" : "=r"(smid));
  return smid;
}

__device__ __forceinline__ std::uint32_t mix32(std::uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352du;
  value ^= value >> 15;
  value *= 0x846ca68bu;
  return value ^ (value >> 16);
}

__device__ __forceinline__ std::uint32_t observe32(
    std::uint32_t accumulator, std::uint32_t value) {
  // Keep the selected-stage value live with one common integer add in both
  // roles.  The stronger avalanche mix is intentionally deferred until the
  // end of the iteration so observer bookkeeping does not dominate the
  // floating-point stage whose incremental power is being measured.
  return accumulator + value;
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

__device__ __forceinline__ std::uint32_t materialize_shared_u32(
    std::uint32_t value, std::uint32_t* shared_scratch) {
  const std::uint32_t address = static_cast<std::uint32_t>(
      __cvta_generic_to_shared(shared_scratch + threadIdx.x));
  std::uint32_t materialized = 0;
  asm volatile(
      "st.shared.volatile.u32 [%1], %2;\n\t"
      "ld.shared.volatile.u32 %0, [%1];"
      : "=r"(materialized)
      : "r"(address), "r"(value)
      : "memory");
  return materialized;
}

__device__ __forceinline__ int runtime_flag_local(int runtime_flag) {
  int local_flag = 0;
  asm volatile(
      "{\n\t"
      "  .reg .pred local_p;\n\t"
      "  setp.ne.s32 local_p, %1, 0;\n\t"
      "  selp.u32 %0, 1, 0, local_p;\n\t"
      "}"
      : "=r"(local_flag)
      : "r"(runtime_flag)
      : "memory");
  return local_flag;
}

__device__ __forceinline__ float runtime_extra_exp_f32(
    float primary, float materialized_input, int extra_stage_pass) {
  float observed = primary;
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  .reg .f32 extra_scaled;\n\t"
      "  setp.ne.s32 extra_p, %2, 0;\n\t"
      "  @!extra_p bra.uni EXP_F32_DONE;\n\t"
      "  mul.rn.f32 extra_scaled, %1, %3;\n\t"
      "  ex2.approx.ftz.f32 %0, extra_scaled;\n\t"
      "EXP_F32_DONE:\n\t"
      "}"
      : "+f"(observed)
      : "f"(materialized_input), "r"(extra_stage_pass), "f"(kLog2E)
      : "memory");
  return observed;
}

__device__ __forceinline__ half runtime_extra_exp_f16(
    half primary, half materialized_input, int extra_stage_pass) {
  unsigned short observed = __half_as_ushort(primary);
  const unsigned short input_bits = __half_as_ushort(materialized_input);
  const unsigned short log2e_bits =
      __half_as_ushort(__float2half_rn(kLog2E));
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  .reg .f16 extra_scaled;\n\t"
      "  setp.ne.s32 extra_p, %2, 0;\n\t"
      "  @!extra_p bra.uni EXP_F16_DONE;\n\t"
      "  mul.rn.f16 extra_scaled, %1, %3;\n\t"
      "  ex2.approx.f16 %0, extra_scaled;\n\t"
      "EXP_F16_DONE:\n\t"
      "}"
      : "+h"(observed)
      : "h"(input_bits), "r"(extra_stage_pass), "h"(log2e_bits)
      : "memory");
  return __ushort_as_half(observed);
}

__device__ __forceinline__ std::uint32_t runtime_extra_exp_f16x2(
    std::uint32_t primary, std::uint32_t materialized_input,
    int extra_stage_pass) {
  std::uint32_t observed = primary;
  const half2 log2e = __float2half2_rn(kLog2E);
  const std::uint32_t packed_log2e =
      pack_half_bits(__low2half(log2e), __high2half(log2e));
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  .reg .f16x2 extra_scaled;\n\t"
      "  setp.ne.s32 extra_p, %2, 0;\n\t"
      "  @!extra_p bra.uni EXP_F16X2_DONE;\n\t"
      "  mul.rn.f16x2 extra_scaled, %1, %3;\n\t"
      "  ex2.approx.f16x2 %0, extra_scaled;\n\t"
      "EXP_F16X2_DONE:\n\t"
      "}"
      : "+r"(observed)
      : "r"(materialized_input), "r"(extra_stage_pass), "r"(packed_log2e)
      : "memory");
  return observed;
}

__device__ __forceinline__ float runtime_extra_rcp_f32(
    float primary, float materialized_sum, int extra_stage_pass) {
  float observed = primary;
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  setp.ne.s32 extra_p, %2, 0;\n\t"
      "  @!extra_p bra.uni RCP_F32_DONE;\n\t"
      "  rcp.approx.ftz.f32 %0, %1;\n\t"
      "RCP_F32_DONE:\n\t"
      "}"
      : "+f"(observed)
      : "f"(materialized_sum), "r"(extra_stage_pass)
      : "memory");
  return observed;
}

__device__ __forceinline__ half runtime_extra_rcp_f16(
    half primary, half materialized_sum, int extra_stage_pass) {
  unsigned short observed = __half_as_ushort(primary);
  const unsigned short sum_bits = __half_as_ushort(materialized_sum);
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  .reg .f32 extra_sum_f, extra_inverse_f;\n\t"
      "  setp.ne.s32 extra_p, %2, 0;\n\t"
      "  @!extra_p bra.uni RCP_F16_DONE;\n\t"
      "  cvt.f32.f16 extra_sum_f, %1;\n\t"
      "  rcp.approx.ftz.f32 extra_inverse_f, extra_sum_f;\n\t"
      "  cvt.rn.f16.f32 %0, extra_inverse_f;\n\t"
      "RCP_F16_DONE:\n\t"
      "}"
      : "+h"(observed)
      : "h"(sum_bits), "r"(extra_stage_pass)
      : "memory");
  return __ushort_as_half(observed);
}

__device__ __forceinline__ float runtime_extra_mul_f32(
    float primary, float left, float right, int extra_stage_pass) {
  float observed = primary;
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  setp.ne.s32 extra_p, %3, 0;\n\t"
      "  @!extra_p bra.uni MUL_F32_DONE;\n\t"
      "  mul.rn.f32 %0, %1, %2;\n\t"
      "MUL_F32_DONE:\n\t"
      "}"
      : "+f"(observed)
      : "f"(left), "f"(right), "r"(extra_stage_pass)
      : "memory");
  return observed;
}

__device__ __forceinline__ half runtime_extra_mul_f16(
    half primary, half left, half right, int extra_stage_pass) {
  unsigned short observed = __half_as_ushort(primary);
  const unsigned short left_bits = __half_as_ushort(left);
  const unsigned short right_bits = __half_as_ushort(right);
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  setp.ne.s32 extra_p, %3, 0;\n\t"
      "  @!extra_p bra.uni MUL_F16_DONE;\n\t"
      "  mul.rn.f16 %0, %1, %2;\n\t"
      "MUL_F16_DONE:\n\t"
      "}"
      : "+h"(observed)
      : "h"(left_bits), "h"(right_bits), "r"(extra_stage_pass)
      : "memory");
  return __ushort_as_half(observed);
}

__device__ __forceinline__ std::uint32_t runtime_extra_mul_f16x2(
    std::uint32_t primary, std::uint32_t left, std::uint32_t right,
    int extra_stage_pass) {
  std::uint32_t observed = primary;
  asm volatile(
      "{\n\t"
      "  .reg .pred extra_p;\n\t"
      "  setp.ne.s32 extra_p, %3, 0;\n\t"
      "  @!extra_p bra.uni MUL_F16X2_DONE;\n\t"
      "  mul.rn.f16x2 %0, %1, %2;\n\t"
      "MUL_F16X2_DONE:\n\t"
      "}"
      : "+r"(observed)
      : "r"(left), "r"(right), "r"(extra_stage_pass)
      : "memory");
  return observed;
}

__device__ __forceinline__ float ptx_exp_e_f32(float input) {
  float scaled = 0.0f;
  float output = 0.0f;
  asm volatile("mul.rn.f32 %0, %1, %2;" : "=f"(scaled)
               : "f"(input), "f"(kLog2E));
  asm volatile("ex2.approx.ftz.f32 %0, %1;" : "=f"(output) : "f"(scaled));
  return output;
}

__device__ __forceinline__ float ptx_sub_f32(float left, float right) {
  float result = 0.0f;
  asm volatile("sub.rn.f32 %0, %1, %2;" : "=f"(result)
               : "f"(left), "f"(right));
  return result;
}

__device__ __forceinline__ half ptx_sub_f16(half left, half right) {
  unsigned short result = 0;
  asm volatile("sub.rn.f16 %0, %1, %2;" : "=h"(result)
               : "h"(__half_as_ushort(left)), "h"(__half_as_ushort(right)));
  return __ushort_as_half(result);
}

__device__ __forceinline__ std::uint32_t ptx_sub_f16x2(
    std::uint32_t left, std::uint32_t right) {
  std::uint32_t result = 0;
  asm volatile("sub.rn.f16x2 %0, %1, %2;" : "=r"(result)
               : "r"(left), "r"(right));
  return result;
}

__device__ __forceinline__ half ptx_exp_e_f16(half input) {
  const half scaled = __hmul(input, __float2half_rn(kLog2E));
  unsigned short output = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16 %0, %1;" : "=h"(output)
                                      : "h"(__half_as_ushort(scaled)));
#else
#if defined(__CUDA_ARCH__)
  asm volatile("trap;");
#endif
#endif
  return __ushort_as_half(output);
}

__device__ __forceinline__ std::uint32_t ptx_exp_e_f16x2(
    std::uint32_t packed_input) {
  const half2 input = __halves2half2(unpack_half_low(packed_input),
                                     unpack_half_high(packed_input));
  const half2 scaled = __hmul2(input, __float2half2_rn(kLog2E));
  std::uint32_t output = 0;
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 750
  asm volatile("ex2.approx.f16x2 %0, %1;" : "=r"(output)
                                          : "r"(pack_half_bits(
                                                __low2half(scaled),
                                                __high2half(scaled))));
#else
#if defined(__CUDA_ARCH__)
  asm volatile("trap;");
#endif
#endif
  return output;
}

__device__ __forceinline__ float ptx_rcp_f32(float value) {
  float result = 0.0f;
  asm volatile("rcp.approx.ftz.f32 %0, %1;" : "=f"(result) : "f"(value));
  return result;
}

__device__ __forceinline__ float ptx_mul_f32(float left, float right) {
  float result = 0.0f;
  asm volatile("mul.rn.f32 %0, %1, %2;" : "=f"(result)
               : "f"(left), "f"(right));
  return result;
}

__device__ __forceinline__ half ptx_rcp_f16(half value) {
  return __float2half_rn(ptx_rcp_f32(__half2float(value)));
}

__device__ __forceinline__ half ptx_mul_f16(half left, half right) {
  unsigned short result = 0;
  asm volatile("mul.rn.f16 %0, %1, %2;" : "=h"(result)
               : "h"(__half_as_ushort(left)), "h"(__half_as_ushort(right)));
  return __ushort_as_half(result);
}

__device__ __forceinline__ std::uint32_t ptx_mul_f16x2(
    std::uint32_t left, std::uint32_t right) {
  std::uint32_t result = 0;
  asm volatile("mul.rn.f16x2 %0, %1, %2;" : "=r"(result)
               : "r"(left), "r"(right));
  return result;
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
      shared[threadIdx.x] =
          __hmax(shared[threadIdx.x], shared[threadIdx.x + stride]);
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
      shared[threadIdx.x] =
          __hadd(shared[threadIdx.x], shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half result = shared[0];
  __syncthreads();
  return result;
}

__device__ __forceinline__ half2 block_max_half2(half2 value, half2* shared) {
  shared[threadIdx.x] = value;
  __syncthreads();
  for (int stride = kThreadsPerBlock / 2; stride > 0; stride >>= 1) {
    if (threadIdx.x < stride) {
      shared[threadIdx.x] =
          __hmax2(shared[threadIdx.x], shared[threadIdx.x + stride]);
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
      shared[threadIdx.x] =
          __hadd2(shared[threadIdx.x], shared[threadIdx.x + stride]);
    }
    __syncthreads();
  }
  const half2 result = shared[0];
  __syncthreads();
  return result;
}

template <int SoftmaxCols, Stage SelectedStage, Policy P>
__global__ void whole_softmax_stage_atc_kernel(
    const half* input_f16, const float* input_f32, half* output_f16,
    float* output_f32, std::uint32_t* sink_by_thread, int* smid_by_block,
    std::uint64_t iters, int extra_stage_pass) {
  constexpr int kElements = SoftmaxCols / kThreadsPerBlock;
  static_assert(SoftmaxCols % kThreadsPerBlock == 0,
                "ATC width must divide the 256-thread CTA");
  static_assert(kElements >= 2 && (kElements % 2) == 0,
                "ATC width must preserve adjacent f16x2 pairs per thread");

  if (threadIdx.x == 0 && smid_by_block) {
    smid_by_block[blockIdx.x] = static_cast<int>(read_smid());
  }

  __shared__ float warp_values[kWarpsPerBlock];
  __shared__ half scalar_reduce[kThreadsPerBlock];
  __shared__ half2 packed_reduce[kThreadsPerBlock];
  auto* opaque_stage_scratch =
      reinterpret_cast<std::uint32_t*>(packed_reduce);

  float x_f[kRowsPerBlock][kElements];
  half x_h[kRowsPerBlock][kElements];
  float e_f[kRowsPerBlock][kElements];
  half e_h[kRowsPerBlock][kElements];

  std::uint32_t sink =
      mix32((static_cast<std::uint32_t>(blockIdx.x) + 1u) * 0x9e3779b9u ^
            (static_cast<std::uint32_t>(threadIdx.x) + 17u));
  const std::uint64_t first_row =
      static_cast<std::uint64_t>(blockIdx.x) * kRowsPerBlock;

  for (std::uint64_t iteration = 0; iteration < iters; ++iteration) {
#pragma unroll
    for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
      const std::uint64_t row = first_row + row_lane;
#pragma unroll
      for (int element = 0; element < kElements; ++element) {
        const std::size_t index =
            static_cast<std::size_t>(row) * SoftmaxCols +
            static_cast<std::size_t>(threadIdx.x) * kElements + element;
        if constexpr (P == Policy::fp32) {
          const volatile float* source = input_f32 + index;
          x_f[row_lane][element] = *source;
          x_h[row_lane][element] =
              __float2half_rn(x_f[row_lane][element]);
        } else {
          const volatile half* source = input_f16 + index;
          x_h[row_lane][element] = *source;
          x_f[row_lane][element] =
              __half2float(x_h[row_lane][element]);
        }
      }
    }

    float row_max_f[kRowsPerBlock] = {};
    half row_max_h[kRowsPerBlock] = {};
    if constexpr (P == Policy::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        float local = x_f[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = fmaxf(local, x_f[row_lane][element]);
        }
        row_max_f[row_lane] = block_max_float(local, warp_values);
        row_max_h[row_lane] = __float2half_rn(row_max_f[row_lane]);
      }
    } else if constexpr (P == Policy::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        half local = x_h[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = __hmax(local, x_h[row_lane][element]);
        }
        row_max_h[row_lane] = block_max_half(local, scalar_reduce);
        row_max_f[row_lane] = __half2float(row_max_h[row_lane]);
      }
    } else {
      half2 local = __halves2half2(x_h[0][0], x_h[1][0]);
#pragma unroll
      for (int element = 1; element < kElements; ++element) {
        local =
            __hmax2(local, __halves2half2(x_h[0][element], x_h[1][element]));
      }
      const half2 result = block_max_half2(local, packed_reduce);
      row_max_h[0] = __low2half(result);
      row_max_h[1] = __high2half(result);
      row_max_f[0] = __half2float(row_max_h[0]);
      row_max_f[1] = __half2float(row_max_h[1]);
    }

    if constexpr (SelectedStage == Stage::reduction) {
      float observed_max_f[kRowsPerBlock] = {row_max_f[0], row_max_f[1]};
      half observed_max_h[kRowsPerBlock] = {row_max_h[0], row_max_h[1]};
      const int max_extra_stage_pass =
          runtime_flag_local(extra_stage_pass);
      if (max_extra_stage_pass != 0) {
        if constexpr (P == Policy::fp32) {
#pragma unroll
          for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
            float local = x_f[row_lane][0];
#pragma unroll
            for (int element = 1; element < kElements; ++element) {
              local = fmaxf(local, x_f[row_lane][element]);
            }
            observed_max_f[row_lane] = block_max_float(local, warp_values);
          }
        } else if constexpr (P == Policy::fp16_scalar) {
#pragma unroll
          for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
            half local = x_h[row_lane][0];
#pragma unroll
            for (int element = 1; element < kElements; ++element) {
              local = __hmax(local, x_h[row_lane][element]);
            }
            observed_max_h[row_lane] = block_max_half(local, scalar_reduce);
          }
        } else {
          half2 local = __halves2half2(x_h[0][0], x_h[1][0]);
#pragma unroll
          for (int element = 1; element < kElements; ++element) {
            local = __hmax2(
                local, __halves2half2(x_h[0][element], x_h[1][element]));
          }
          const half2 result = block_max_half2(local, packed_reduce);
          observed_max_h[0] = __low2half(result);
          observed_max_h[1] = __high2half(result);
        }
      }
      if constexpr (P == Policy::fp32) {
        sink = observe32(
            sink, __float_as_uint(observed_max_f[0]) ^
                      __float_as_uint(observed_max_f[1]));
      } else {
        sink = observe32(
            sink, pack_half_bits(observed_max_h[0], observed_max_h[1]));
      }
    }

    if constexpr (P == Policy::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          const float exponent_input =
              ptx_sub_f32(x_f[row_lane][element], row_max_f[row_lane]);
          e_f[row_lane][element] = ptx_exp_e_f32(exponent_input);
          e_h[row_lane][element] =
              __float2half_rn(e_f[row_lane][element]);
          if constexpr (SelectedStage == Stage::exp) {
            const std::uint32_t materialized_bits =
                materialize_shared_u32(
                    __float_as_uint(exponent_input),
                    opaque_stage_scratch);
            sink = observe32(sink, materialized_bits);
            const float observed = runtime_extra_exp_f32(
                e_f[row_lane][element],
                __uint_as_float(materialized_bits), extra_stage_pass);
            sink = observe32(sink, __float_as_uint(observed));
          }
        }
      }
    } else if constexpr (P == Policy::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          const half exponent_input =
              ptx_sub_f16(x_h[row_lane][element], row_max_h[row_lane]);
          e_h[row_lane][element] = ptx_exp_e_f16(exponent_input);
          e_f[row_lane][element] =
              __half2float(e_h[row_lane][element]);
          if constexpr (SelectedStage == Stage::exp) {
            const std::uint32_t materialized_bits =
                materialize_shared_u32(
                    static_cast<std::uint32_t>(
                        __half_as_ushort(exponent_input)),
                    opaque_stage_scratch);
            sink = observe32(sink, materialized_bits);
            const half materialized_input = __ushort_as_half(
                static_cast<unsigned short>(materialized_bits));
            const half observed = runtime_extra_exp_f16(
                e_h[row_lane][element], materialized_input,
                extra_stage_pass);
            sink = observe32(
                sink,
                static_cast<std::uint32_t>(__half_as_ushort(observed)));
          }
        }
      }
    } else {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
#pragma unroll
        for (int element = 0; element < kElements; element += 2) {
          const std::uint32_t packed_values =
              pack_half_bits(x_h[row_lane][element],
                             x_h[row_lane][element + 1]);
          const std::uint32_t packed_max =
              pack_half_bits(row_max_h[row_lane], row_max_h[row_lane]);
          const std::uint32_t packed_input =
              ptx_sub_f16x2(packed_values, packed_max);
          const std::uint32_t primary =
              ptx_exp_e_f16x2(packed_input);
          e_h[row_lane][element] = unpack_half_low(primary);
          e_h[row_lane][element + 1] = unpack_half_high(primary);
          e_f[row_lane][element] =
              __half2float(e_h[row_lane][element]);
          e_f[row_lane][element + 1] =
              __half2float(e_h[row_lane][element + 1]);
          if constexpr (SelectedStage == Stage::exp) {
            const std::uint32_t materialized_input =
                materialize_shared_u32(
                    packed_input, opaque_stage_scratch);
            sink = observe32(sink, materialized_input);
            const std::uint32_t observed = runtime_extra_exp_f16x2(
                primary, materialized_input, extra_stage_pass);
            sink = observe32(sink, observed);
          }
        }
      }
    }

    float row_sum_f[kRowsPerBlock] = {};
    half row_sum_h[kRowsPerBlock] = {};
    if constexpr (P == Policy::fp32) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        float local = 0.0f;
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          local += e_f[row_lane][element];
        }
        row_sum_f[row_lane] = block_sum_float(local, warp_values);
        row_sum_h[row_lane] = __float2half_rn(row_sum_f[row_lane]);
      }
    } else if constexpr (P == Policy::fp16_scalar) {
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        half local = e_h[row_lane][0];
#pragma unroll
        for (int element = 1; element < kElements; ++element) {
          local = __hadd(local, e_h[row_lane][element]);
        }
        row_sum_h[row_lane] = block_sum_half(local, scalar_reduce);
        row_sum_f[row_lane] = __half2float(row_sum_h[row_lane]);
      }
    } else {
      half2 local = __halves2half2(e_h[0][0], e_h[1][0]);
#pragma unroll
      for (int element = 1; element < kElements; ++element) {
        local =
            __hadd2(local, __halves2half2(e_h[0][element], e_h[1][element]));
      }
      const half2 result = block_sum_half2(local, packed_reduce);
      row_sum_h[0] = __low2half(result);
      row_sum_h[1] = __high2half(result);
      row_sum_f[0] = __half2float(row_sum_h[0]);
      row_sum_f[1] = __half2float(row_sum_h[1]);
    }

    if constexpr (SelectedStage == Stage::reduction) {
      float observed_sum_f[kRowsPerBlock] = {row_sum_f[0], row_sum_f[1]};
      half observed_sum_h[kRowsPerBlock] = {row_sum_h[0], row_sum_h[1]};
      const int sum_extra_stage_pass =
          runtime_flag_local(extra_stage_pass);
      if (sum_extra_stage_pass != 0) {
        if constexpr (P == Policy::fp32) {
#pragma unroll
          for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
            float local = 0.0f;
#pragma unroll
            for (int element = 0; element < kElements; ++element) {
              local += e_f[row_lane][element];
            }
            observed_sum_f[row_lane] = block_sum_float(local, warp_values);
          }
        } else if constexpr (P == Policy::fp16_scalar) {
#pragma unroll
          for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
            half local = e_h[row_lane][0];
#pragma unroll
            for (int element = 1; element < kElements; ++element) {
              local = __hadd(local, e_h[row_lane][element]);
            }
            observed_sum_h[row_lane] = block_sum_half(local, scalar_reduce);
          }
        } else {
          half2 local = __halves2half2(e_h[0][0], e_h[1][0]);
#pragma unroll
          for (int element = 1; element < kElements; ++element) {
            local = __hadd2(
                local, __halves2half2(e_h[0][element], e_h[1][element]));
          }
          const half2 result = block_sum_half2(local, packed_reduce);
          observed_sum_h[0] = __low2half(result);
          observed_sum_h[1] = __high2half(result);
        }
      }
      if constexpr (P == Policy::fp32) {
        sink = observe32(
            sink, __float_as_uint(observed_sum_f[0]) ^
                      __float_as_uint(observed_sum_f[1]));
      } else {
        sink = observe32(
            sink, pack_half_bits(observed_sum_h[0], observed_sum_h[1]));
      }
    }

    if constexpr (P == Policy::fp32) {
      float inverse[kRowsPerBlock] = {
          ptx_rcp_f32(row_sum_f[0]), ptx_rcp_f32(row_sum_f[1])};
      float observed_inverse[kRowsPerBlock] = {inverse[0], inverse[1]};
      if constexpr (SelectedStage == Stage::normalization) {
#pragma unroll
        for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
          const std::uint32_t materialized_bits =
              materialize_shared_u32(
                  __float_as_uint(row_sum_f[row_lane]),
                  opaque_stage_scratch);
          sink = observe32(sink, materialized_bits);
          observed_inverse[row_lane] = runtime_extra_rcp_f32(
              inverse[row_lane], __uint_as_float(materialized_bits),
              extra_stage_pass);
          sink = observe32(
              sink, __float_as_uint(observed_inverse[row_lane]));
        }
      }
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const std::uint64_t row = first_row + row_lane;
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          const std::size_t index =
              static_cast<std::size_t>(row) * SoftmaxCols +
              static_cast<std::size_t>(threadIdx.x) * kElements + element;
          const float primary =
              ptx_mul_f32(e_f[row_lane][element], inverse[row_lane]);
          if constexpr (SelectedStage == Stage::normalization) {
            const float observed = runtime_extra_mul_f32(
                primary, e_f[row_lane][element],
                observed_inverse[row_lane], extra_stage_pass);
            sink = observe32(sink, __float_as_uint(observed));
          }
          volatile float* target = output_f32 + index;
          *target = primary;
        }
      }
    } else if constexpr (P == Policy::fp16_scalar) {
      half inverse[kRowsPerBlock] = {
          ptx_rcp_f16(row_sum_h[0]), ptx_rcp_f16(row_sum_h[1])};
      half observed_inverse[kRowsPerBlock] = {inverse[0], inverse[1]};
      if constexpr (SelectedStage == Stage::normalization) {
#pragma unroll
        for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
          const std::uint32_t materialized_bits =
              materialize_shared_u32(
                  static_cast<std::uint32_t>(
                      __half_as_ushort(row_sum_h[row_lane])),
                  opaque_stage_scratch);
          sink = observe32(sink, materialized_bits);
          const half materialized_sum = __ushort_as_half(
              static_cast<unsigned short>(materialized_bits));
          observed_inverse[row_lane] = runtime_extra_rcp_f16(
              inverse[row_lane], materialized_sum, extra_stage_pass);
          sink = observe32(
              sink,
              static_cast<std::uint32_t>(
                  __half_as_ushort(observed_inverse[row_lane])));
        }
      }
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const std::uint64_t row = first_row + row_lane;
#pragma unroll
        for (int element = 0; element < kElements; ++element) {
          const std::size_t index =
              static_cast<std::size_t>(row) * SoftmaxCols +
              static_cast<std::size_t>(threadIdx.x) * kElements + element;
          const half primary =
              ptx_mul_f16(e_h[row_lane][element], inverse[row_lane]);
          if constexpr (SelectedStage == Stage::normalization) {
            const half observed = runtime_extra_mul_f16(
                primary, e_h[row_lane][element],
                observed_inverse[row_lane], extra_stage_pass);
            sink = observe32(
                sink,
                static_cast<std::uint32_t>(__half_as_ushort(observed)));
          }
          volatile half* target = output_f16 + index;
          *target = primary;
        }
      }
    } else {
      half inverse[kRowsPerBlock] = {
          ptx_rcp_f16(row_sum_h[0]), ptx_rcp_f16(row_sum_h[1])};
      half observed_inverse[kRowsPerBlock] = {inverse[0], inverse[1]};
      if constexpr (SelectedStage == Stage::normalization) {
#pragma unroll
        for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
          const std::uint32_t materialized_bits =
              materialize_shared_u32(
                  static_cast<std::uint32_t>(
                      __half_as_ushort(row_sum_h[row_lane])),
                  opaque_stage_scratch);
          sink = observe32(sink, materialized_bits);
          const half materialized_sum = __ushort_as_half(
              static_cast<unsigned short>(materialized_bits));
          observed_inverse[row_lane] = runtime_extra_rcp_f16(
              inverse[row_lane], materialized_sum, extra_stage_pass);
          sink = observe32(
              sink,
              static_cast<std::uint32_t>(
                  __half_as_ushort(observed_inverse[row_lane])));
        }
      }
#pragma unroll
      for (int row_lane = 0; row_lane < kRowsPerBlock; ++row_lane) {
        const std::uint64_t row = first_row + row_lane;
#pragma unroll
        for (int element = 0; element < kElements; element += 2) {
          const std::size_t low_index =
              static_cast<std::size_t>(row) * SoftmaxCols +
              static_cast<std::size_t>(threadIdx.x) * kElements + element;
          const std::uint32_t values =
              pack_half_bits(e_h[row_lane][element],
                             e_h[row_lane][element + 1]);
          const std::uint32_t inv =
              pack_half_bits(inverse[row_lane], inverse[row_lane]);
          const std::uint32_t primary = ptx_mul_f16x2(values, inv);
          if constexpr (SelectedStage == Stage::normalization) {
            const std::uint32_t extra_inv =
                pack_half_bits(observed_inverse[row_lane],
                               observed_inverse[row_lane]);
            const std::uint32_t observed = runtime_extra_mul_f16x2(
                primary, values, extra_inv, extra_stage_pass);
            sink = observe32(sink, observed);
          }
          volatile half* target = output_f16 + low_index;
          target[0] = unpack_half_low(primary);
          target[1] = unpack_half_high(primary);
        }
      }
    }
    sink = mix32(sink ^ static_cast<std::uint32_t>(iteration));
  }

  if (sink_by_thread) {
    const std::size_t sink_index =
        static_cast<std::size_t>(blockIdx.x) * kThreadsPerBlock + threadIdx.x;
    sink_by_thread[sink_index] = sink;
  }
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
  const std::size_t index =
      static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
  const std::size_t stride =
      static_cast<std::size_t>(gridDim.x) * blockDim.x;
  for (std::size_t current = index; current < count; current += stride) {
    const std::uint64_t bits = splitmix64(seed + current);
    const float unit =
        static_cast<float>((bits >> 40) & 0xffffffull) /
        static_cast<float>(0x1000000ull);
    const half quantized =
        __float2half_rn((2.0f * unit - 1.0f) * logit_scale);
    input_f16[current] = quantized;
    input_f32[current] = __half2float(quantized);
  }
}

template <int SoftmaxCols, Stage S, Policy P>
cudaError_t launch_typed(const LaunchConfig& config) {
  whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>
      <<<static_cast<unsigned>(config.grid_blocks), kThreadsPerBlock, 0,
         config.stream>>>(
          config.input_f16, config.input_f32, config.output_f16,
          config.output_f32, config.sink_by_thread, config.smid_by_block,
          config.iters, config.extra_stage_pass);
  return cudaGetLastError();
}

template <int SoftmaxCols, Stage S, Policy P>
int occupancy_typed() {
  int blocks = 0;
  const cudaError_t status = cudaOccupancyMaxActiveBlocksPerMultiprocessor(
      &blocks, whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>,
      kThreadsPerBlock, 0);
  return status == cudaSuccess ? blocks : 0;
}

template <int SoftmaxCols, Stage S, Policy P>
int binary_version_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>);
  return status == cudaSuccess ? attributes.binaryVersion : 0;
}

template <int SoftmaxCols, Stage S, Policy P>
int registers_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>);
  return status == cudaSuccess ? attributes.numRegs : 0;
}

template <int SoftmaxCols, Stage S, Policy P>
std::size_t shared_bytes_typed() {
  cudaFuncAttributes attributes{};
  const cudaError_t status = cudaFuncGetAttributes(
      &attributes, whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>);
  return status == cudaSuccess ? attributes.sharedSizeBytes : 0;
}

template <int SoftmaxCols, Stage S, Policy P>
std::uintptr_t symbol_typed() {
  return reinterpret_cast<std::uintptr_t>(
      whole_softmax_stage_atc_kernel<SoftmaxCols, S, P>);
}

#define ATC_DISPATCH_POLICY(ACTION, WIDTH, STAGE_VALUE, CONFIG_OR_EMPTY)       \
  switch (policy) {                                                            \
    case Policy::fp32:                                                         \
      return ACTION<WIDTH, STAGE_VALUE, Policy::fp32> CONFIG_OR_EMPTY;         \
    case Policy::fp16_scalar:                                                  \
      return ACTION<WIDTH, STAGE_VALUE, Policy::fp16_scalar> CONFIG_OR_EMPTY;  \
    case Policy::fp16x2:                                                       \
      return ACTION<WIDTH, STAGE_VALUE, Policy::fp16x2> CONFIG_OR_EMPTY;       \
  }                                                                            \
  break

template <int SoftmaxCols>
cudaError_t dispatch_launch(Stage stage, Policy policy,
                            const LaunchConfig& config) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(launch_typed, SoftmaxCols, Stage::exp, (config));
    case Stage::reduction:
      ATC_DISPATCH_POLICY(launch_typed, SoftmaxCols, Stage::reduction,
                          (config));
    case Stage::normalization:
      ATC_DISPATCH_POLICY(launch_typed, SoftmaxCols, Stage::normalization,
                          (config));
  }
  return cudaErrorInvalidValue;
}

template <int SoftmaxCols>
int dispatch_occupancy(Stage stage, Policy policy) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(occupancy_typed, SoftmaxCols, Stage::exp, ());
    case Stage::reduction:
      ATC_DISPATCH_POLICY(occupancy_typed, SoftmaxCols, Stage::reduction, ());
    case Stage::normalization:
      ATC_DISPATCH_POLICY(occupancy_typed, SoftmaxCols, Stage::normalization,
                          ());
  }
  return 0;
}

template <int SoftmaxCols>
int dispatch_binary_version(Stage stage, Policy policy) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(binary_version_typed, SoftmaxCols, Stage::exp, ());
    case Stage::reduction:
      ATC_DISPATCH_POLICY(binary_version_typed, SoftmaxCols, Stage::reduction,
                          ());
    case Stage::normalization:
      ATC_DISPATCH_POLICY(binary_version_typed, SoftmaxCols,
                          Stage::normalization, ());
  }
  return 0;
}

template <int SoftmaxCols>
int dispatch_registers(Stage stage, Policy policy) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(registers_typed, SoftmaxCols, Stage::exp, ());
    case Stage::reduction:
      ATC_DISPATCH_POLICY(registers_typed, SoftmaxCols, Stage::reduction, ());
    case Stage::normalization:
      ATC_DISPATCH_POLICY(registers_typed, SoftmaxCols, Stage::normalization,
                          ());
  }
  return 0;
}

template <int SoftmaxCols>
std::size_t dispatch_shared_bytes(Stage stage, Policy policy) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(shared_bytes_typed, SoftmaxCols, Stage::exp, ());
    case Stage::reduction:
      ATC_DISPATCH_POLICY(shared_bytes_typed, SoftmaxCols, Stage::reduction,
                          ());
    case Stage::normalization:
      ATC_DISPATCH_POLICY(shared_bytes_typed, SoftmaxCols,
                          Stage::normalization, ());
  }
  return 0;
}

template <int SoftmaxCols>
std::uintptr_t dispatch_symbol(Stage stage, Policy policy) {
  switch (stage) {
    case Stage::exp:
      ATC_DISPATCH_POLICY(symbol_typed, SoftmaxCols, Stage::exp, ());
    case Stage::reduction:
      ATC_DISPATCH_POLICY(symbol_typed, SoftmaxCols, Stage::reduction, ());
    case Stage::normalization:
      ATC_DISPATCH_POLICY(symbol_typed, SoftmaxCols, Stage::normalization, ());
  }
  return 0;
}

#undef ATC_DISPATCH_POLICY

}  // namespace

cudaError_t launch_kernel(const LaunchConfig& config) {
  if (!config.input_f16 || !config.input_f32 || !config.output_f16 ||
      !config.output_f32 || !config.sink_by_thread || !config.smid_by_block ||
      config.grid_blocks == 0 || config.iters == 0 ||
      config.grid_blocks > static_cast<std::uint64_t>(0xffffffffu) ||
      !supported_softmax_cols(config.softmax_cols) ||
      (config.extra_stage_pass != 0 && config.extra_stage_pass != 1)) {
    return cudaErrorInvalidValue;
  }
  if (config.policy != Policy::fp32) {
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
  switch (config.softmax_cols) {
    case 512:
      return dispatch_launch<512>(config.stage, config.policy, config);
    case 1024:
      return dispatch_launch<1024>(config.stage, config.policy, config);
    case 2048:
      return dispatch_launch<2048>(config.stage, config.policy, config);
    case 4096:
      return dispatch_launch<4096>(config.stage, config.policy, config);
    default:
      return cudaErrorInvalidValue;
  }
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

int query_occupancy_max_blocks_per_sm(Stage stage, Policy policy,
                                      int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_occupancy<512>(stage, policy);
    case 1024:
      return dispatch_occupancy<1024>(stage, policy);
    case 2048:
      return dispatch_occupancy<2048>(stage, policy);
    case 4096:
      return dispatch_occupancy<4096>(stage, policy);
    default:
      return 0;
  }
}

int query_binary_version(Stage stage, Policy policy, int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_binary_version<512>(stage, policy);
    case 1024:
      return dispatch_binary_version<1024>(stage, policy);
    case 2048:
      return dispatch_binary_version<2048>(stage, policy);
    case 4096:
      return dispatch_binary_version<4096>(stage, policy);
    default:
      return 0;
  }
}

int query_registers_per_thread(Stage stage, Policy policy, int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_registers<512>(stage, policy);
    case 1024:
      return dispatch_registers<1024>(stage, policy);
    case 2048:
      return dispatch_registers<2048>(stage, policy);
    case 4096:
      return dispatch_registers<4096>(stage, policy);
    default:
      return 0;
  }
}

std::size_t query_static_shared_bytes(Stage stage, Policy policy,
                                      int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_shared_bytes<512>(stage, policy);
    case 1024:
      return dispatch_shared_bytes<1024>(stage, policy);
    case 2048:
      return dispatch_shared_bytes<2048>(stage, policy);
    case 4096:
      return dispatch_shared_bytes<4096>(stage, policy);
    default:
      return 0;
  }
}

std::uintptr_t query_kernel_symbol_address(Stage stage, Policy policy,
                                           int softmax_cols) {
  switch (softmax_cols) {
    case 512:
      return dispatch_symbol<512>(stage, policy);
    case 1024:
      return dispatch_symbol<1024>(stage, policy);
    case 2048:
      return dispatch_symbol<2048>(stage, policy);
    case 4096:
      return dispatch_symbol<4096>(stage, policy);
    default:
      return 0;
  }
}

}  // namespace fp16softmax::whole_stage_atc
