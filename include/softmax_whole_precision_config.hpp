#pragma once

#include <stdexcept>
#include <string>

namespace fp16softmax::whole_precision {

// The first whole-Softmax precision experiment intentionally fixes S=512.
// It gives each 256-thread CTA two elements per thread, which makes the
// f16x2 paths real pair operations rather than an even-lane emulation.  Wider
// S/CTA sweeps are a follow-up decision, not part of the initial attribution.
constexpr int kSoftmaxCols = 512;
constexpr int kThreadsPerBlock = 256;
constexpr int kElementsPerThread = kSoftmaxCols / kThreadsPerBlock;
// A CTA processes two independent rows.  This supplies real f16x2 lanes for
// the packed reduction path without changing the logical Softmax row shape.
constexpr int kRowsPerBlock = 2;
static_assert(kElementsPerThread == 2,
              "whole-precision initial kernel assumes two elements/thread");

enum class StageImplementation {
  fp32,
  fp16_scalar,
  fp16x2_packed,
};

enum class IoImplementation {
  fp16,
  fp32,
};

// A policy identifies an end-to-end Softmax implementation.  It is not an
// Operand-rate ATC treatment: every selected policy executes a complete
// max/subtract/exp/sum/normalize Softmax and is normalized by logical output
// elements.
enum class Policy {
  fp32_io_fp32_all,
  fp16_io_fp32_all,
  exp_fp16_scalar,
  exp_fp16x2,
  reduction_fp16_scalar,
  reduction_fp16x2,
  normalization_fp16_scalar,
  normalization_fp16x2,
  fp16_scalar_all,
  fp16x2_all,
};

struct PolicySpec {
  Policy id;
  const char* name;
  IoImplementation io;
  StageImplementation exp;
  StageImplementation reduction;
  StageImplementation normalization;
  const char* description;
};

inline const char* to_string(StageImplementation value) {
  switch (value) {
    case StageImplementation::fp32:
      return "fp32";
    case StageImplementation::fp16_scalar:
      return "fp16_scalar";
    case StageImplementation::fp16x2_packed:
      return "fp16x2_packed";
  }
  return "unknown";
}

inline const char* to_string(IoImplementation value) {
  switch (value) {
    case IoImplementation::fp16:
      return "fp16";
    case IoImplementation::fp32:
      return "fp32";
  }
  return "unknown";
}

inline PolicySpec policy_spec(Policy value) {
  switch (value) {
    case Policy::fp32_io_fp32_all:
      return {value, "fp32_io_fp32_all", IoImplementation::fp32,
              StageImplementation::fp32, StageImplementation::fp32,
              StageImplementation::fp32,
              "FP32 input/output and FP32 exp/reduction/normalization"};
    case Policy::fp16_io_fp32_all:
      return {value, "fp16_io_fp32_all", IoImplementation::fp16,
              StageImplementation::fp32, StageImplementation::fp32,
              StageImplementation::fp32,
              "FP16 input/output with FP32 exp/reduction/normalization"};
    case Policy::exp_fp16_scalar:
      return {value, "exp_fp16_scalar", IoImplementation::fp16,
              StageImplementation::fp16_scalar, StageImplementation::fp32,
              StageImplementation::fp32,
              "scalar FP16 EX2 only; reduction and normalization remain FP32"};
    case Policy::exp_fp16x2:
      return {value, "exp_fp16x2", IoImplementation::fp16,
              StageImplementation::fp16x2_packed, StageImplementation::fp32,
              StageImplementation::fp32,
              "packed FP16x2 EX2 only; reduction and normalization remain FP32"};
    case Policy::reduction_fp16_scalar:
      return {value, "reduction_fp16_scalar", IoImplementation::fp16,
              StageImplementation::fp32, StageImplementation::fp16_scalar,
              StageImplementation::fp32,
              "scalar FP16 max and sum reduction only"};
    case Policy::reduction_fp16x2:
      return {value, "reduction_fp16x2", IoImplementation::fp16,
              StageImplementation::fp32, StageImplementation::fp16x2_packed,
              StageImplementation::fp32,
              "half2 lane-wise max/sum tree across the two independent CTA rows"};
    case Policy::normalization_fp16_scalar:
      return {value, "normalization_fp16_scalar", IoImplementation::fp16,
              StageImplementation::fp32, StageImplementation::fp32,
              StageImplementation::fp16_scalar,
              "FP16-rounded reciprocal (lowered through FP32 RCP) and scalar probability multiply only"};
    case Policy::normalization_fp16x2:
      return {value, "normalization_fp16x2", IoImplementation::fp16,
              StageImplementation::fp32, StageImplementation::fp32,
              StageImplementation::fp16x2_packed,
              "FP16-rounded reciprocal (lowered through FP32 RCP) replicated per pair and half2 probability multiply"};
    case Policy::fp16_scalar_all:
      return {value, "fp16_scalar_all", IoImplementation::fp16,
              StageImplementation::fp16_scalar,
              StageImplementation::fp16_scalar,
              StageImplementation::fp16_scalar,
              "scalar FP16 exp/max/sum/normalization"};
    case Policy::fp16x2_all:
      return {value, "fp16x2_all", IoImplementation::fp16,
              StageImplementation::fp16x2_packed,
              StageImplementation::fp16x2_packed,
              StageImplementation::fp16x2_packed,
              "packed exp/normalization and half2 lane-wise reduction across CTA rows"};
  }
  throw std::invalid_argument("unknown whole-Softmax policy");
}

inline Policy policy_from_string(const std::string& value) {
  for (const Policy candidate : {
           Policy::fp32_io_fp32_all,
           Policy::fp16_io_fp32_all,
           Policy::exp_fp16_scalar,
           Policy::exp_fp16x2,
           Policy::reduction_fp16_scalar,
           Policy::reduction_fp16x2,
           Policy::normalization_fp16_scalar,
           Policy::normalization_fp16x2,
           Policy::fp16_scalar_all,
           Policy::fp16x2_all,
       }) {
    if (value == policy_spec(candidate).name) return candidate;
  }
  throw std::invalid_argument("unknown whole-Softmax policy: " + value);
}

inline bool uses_native_fp16_ex2(Policy policy) {
  const auto spec = policy_spec(policy);
  return spec.exp == StageImplementation::fp16_scalar ||
         spec.exp == StageImplementation::fp16x2_packed;
}

inline bool uses_fp16_reduction(Policy policy) {
  return policy_spec(policy).reduction != StageImplementation::fp32;
}

inline bool uses_fp16_normalization(Policy policy) {
  return policy_spec(policy).normalization != StageImplementation::fp32;
}

}  // namespace fp16softmax::whole_precision
