#pragma once

#include <stdexcept>
#include <string>

namespace fp16softmax {

constexpr int kThreadsPerBlock = 256;
constexpr int kMaxSoftmaxCols = 4096;

enum class SoftmaxMode {
  full,
  linear_control,
  io_control,
};

// Keep the exponential implementation explicit.  The native PTX variants
// are distinct algorithm implementations, while the runtime probe flag stays
// inside each specialization so control/treatment retain one kernel symbol.
enum class ExpImplementation {
  fp32_expf,
  ptx_f16,
  ptx_f16x2,
};

inline std::string to_string(ExpImplementation implementation) {
  switch (implementation) {
    case ExpImplementation::fp32_expf:
      return "fp32_fast___expf";
    case ExpImplementation::ptx_f16:
      return "ptx_ex2_approx_f16";
    case ExpImplementation::ptx_f16x2:
      return "ptx_ex2_approx_f16x2";
  }
  return "unknown";
}

inline ExpImplementation exp_implementation_from_string(
    const std::string& value) {
  if (value == "fp32" || value == "fp32_expf" ||
      value == "fp32_fast___expf") {
    return ExpImplementation::fp32_expf;
  }
  if (value == "f16" || value == "ptx_f16" ||
      value == "ptx_ex2_approx_f16") {
    return ExpImplementation::ptx_f16;
  }
  if (value == "f16x2" || value == "ptx_f16x2" ||
      value == "ptx_ex2_approx_f16x2") {
    return ExpImplementation::ptx_f16x2;
  }
  throw std::invalid_argument("unknown exponential implementation: " + value);
}

inline bool is_native_f16_ex2(ExpImplementation implementation) {
  return implementation != ExpImplementation::fp32_expf;
}

inline int ptx_ex2_results_per_instruction(
    ExpImplementation implementation) {
  return implementation == ExpImplementation::ptx_f16x2 ? 2 : 1;
}

inline std::string to_string(SoftmaxMode mode) {
  switch (mode) {
    case SoftmaxMode::full:
      return "softmax_full_f16io_f32acc";
    case SoftmaxMode::linear_control:
      return "softmax_linear_control_f16io_f32acc";
    case SoftmaxMode::io_control:
      return "softmax_io_control_f16io";
  }
  return "unknown";
}

inline SoftmaxMode mode_from_string(const std::string& value) {
  if (value == "full" || value == "softmax_full_f16io_f32acc") {
    return SoftmaxMode::full;
  }
  if (value == "linear" || value == "linear_control" ||
      value == "softmax_linear_control_f16io_f32acc") {
    return SoftmaxMode::linear_control;
  }
  if (value == "io" || value == "io_control" ||
      value == "softmax_io_control_f16io") {
    return SoftmaxMode::io_control;
  }
  throw std::invalid_argument("unknown softmax mode: " + value);
}

enum class CacheCondition {
  cache_reuse_candidate,
  streaming_large_ws,
};

inline std::string to_string(CacheCondition condition) {
  switch (condition) {
    case CacheCondition::cache_reuse_candidate:
      return "cache_reuse_candidate";
    case CacheCondition::streaming_large_ws:
      return "streaming_large_ws";
  }
  return "unknown";
}

inline CacheCondition cache_condition_from_string(const std::string& value) {
  if (value == "cache_reuse_candidate" || value == "cache_resident") {
    return CacheCondition::cache_reuse_candidate;
  }
  if (value == "streaming_large_ws" || value == "streaming") {
    return CacheCondition::streaming_large_ws;
  }
  throw std::invalid_argument("unknown cache condition: " + value);
}

enum class CachePolicy {
  default_cache,
  cg,
};

inline std::string to_string(CachePolicy policy) {
  switch (policy) {
    case CachePolicy::default_cache:
      return "default";
    case CachePolicy::cg:
      return "cg";
  }
  return "unknown";
}

inline CachePolicy cache_policy_from_string(const std::string& value) {
  if (value == "default") return CachePolicy::default_cache;
  if (value == "cg") return CachePolicy::cg;
  throw std::invalid_argument("unknown cache policy: " + value);
}

inline bool supported_softmax_cols(int cols) {
  return cols == 128 || cols == 256 || cols == 512 || cols == 1024 ||
         cols == 2048 || cols == 4096;
}

inline int elements_per_thread(int cols) {
  if (!supported_softmax_cols(cols) ||
      (cols > kThreadsPerBlock && cols % kThreadsPerBlock != 0)) {
    throw std::invalid_argument(
        "softmax_cols must be one of 128,256,512,1024,2048,4096");
  }
  return cols <= kThreadsPerBlock ? 1 : cols / kThreadsPerBlock;
}

}  // namespace fp16softmax
