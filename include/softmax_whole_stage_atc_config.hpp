#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>

namespace fp16softmax::whole_stage_atc {

constexpr int kThreadsPerBlock = 256;
constexpr int kRowsPerBlock = 2;
constexpr float kDefaultLogitScale = 4.0f;
constexpr std::uint64_t kDefaultInputSeed = 5573589319906701683ull;

constexpr bool supported_softmax_cols(int cols) {
  // Two rows and an even, contiguous per-thread chunk are deliberate.  They
  // make every packed elementwise pass a genuine adjacent f16x2 operation and
  // let the packed reduction use the two independent rows as half2 lanes.
  return cols == 512 || cols == 1024 || cols == 2048 || cols == 4096;
}

constexpr int elements_per_thread(int cols) {
  return supported_softmax_cols(cols) ? cols / kThreadsPerBlock : 0;
}

enum class Stage {
  exp,
  reduction,
  normalization,
};

enum class Policy {
  fp32,
  fp16_scalar,
  fp16x2,
};

inline const char* to_string(Stage value) {
  switch (value) {
    case Stage::exp:
      return "exp";
    case Stage::reduction:
      return "reduction";
    case Stage::normalization:
      return "normalization";
  }
  return "unknown";
}

inline const char* to_string(Policy value) {
  switch (value) {
    case Policy::fp32:
      return "fp32";
    case Policy::fp16_scalar:
      return "fp16_scalar";
    case Policy::fp16x2:
      return "fp16x2";
  }
  return "unknown";
}

inline Stage stage_from_string(const std::string& value) {
  if (value == "exp") return Stage::exp;
  if (value == "reduction" || value == "max_sum") return Stage::reduction;
  if (value == "normalization" || value == "norm") {
    return Stage::normalization;
  }
  throw std::invalid_argument("unknown whole-Softmax ATC stage: " + value);
}

inline Policy policy_from_string(const std::string& value) {
  if (value == "fp32") return Policy::fp32;
  if (value == "fp16_scalar" || value == "scalar_fp16") {
    return Policy::fp16_scalar;
  }
  if (value == "fp16x2" || value == "packed_fp16x2") {
    return Policy::fp16x2;
  }
  throw std::invalid_argument("unknown whole-Softmax ATC policy: " + value);
}

inline const char* policy_description(Policy value) {
  switch (value) {
    case Policy::fp32:
      return "FP32 I/O and FP32 max/sum/exp/normalization";
    case Policy::fp16_scalar:
      return "FP16 I/O and scalar-FP16 max/sum/exp/multiply; row reciprocal lowers through FP32 then rounds to FP16";
    case Policy::fp16x2:
      return "FP16 I/O, adjacent f16x2 exp/multiply, two-row f16x2 reductions, and per-row FP32 reciprocal rounded to FP16";
  }
  return "unknown";
}

inline const char* stage_description(Stage value) {
  switch (value) {
    case Stage::exp:
      return "reuse the primary (x-max), then repeat log2(e) scale and EX2 for every element";
    case Stage::reduction:
      return "one max reduction before exp plus one sum reduction after exp";
    case Stage::normalization:
      return "row-sum reciprocal replicated by every participating thread, then probability multiply for every element";
  }
  return "unknown";
}

// This identifier is emitted in every raw row.  A pair is valid only when the
// control and treatment rows carry this same identifier and differ solely in
// the uniform runtime extra_stage_pass argument.
constexpr const char* kKernelContract =
    "whole_softmax_stage_atc_same_symbol_runtime_flag_v2";

}  // namespace fp16softmax::whole_stage_atc
