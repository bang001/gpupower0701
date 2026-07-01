#pragma once

#include <algorithm>
#include <cstdint>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace a100fp16 {

constexpr int kA100FullSmCount = 108;
constexpr int kThreadsPerBlock = 32;
constexpr int kWarpSize = 32;
constexpr int kMaxBlocksPerSm = 32;
constexpr int kSharedCapacityPerSmKiB = 164;
constexpr int kMaxSharedPerBlockKiB = 163;
constexpr int kLogicalMmaInputBytes = 1024;
constexpr int kLogicalMmaInputBits = 8192;
constexpr int kLogicalMmaFlop = 8192;
constexpr int kA100L2MiB = 40;

inline const std::vector<int>& allowed_blocks_per_sm() {
  static const std::vector<int> values{1, 2, 4, 8, 16, 32};
  return values;
}

inline const std::vector<std::uint64_t>& allowed_w_sm_kib() {
  static const std::vector<std::uint64_t> values{
      1,     2,     4,      8,      16,     32,
      64,    128,   256,    512,    1024,   2048,
      4096,  8192,  16384,  32768,  65536,  131072};
  return values;
}

enum class Mode {
  idle,
  empty,
  reg_mma,
  shared_mma,
  l2_mma,
  dram_mma,
  store_path,
};

inline std::string to_string(Mode mode) {
  switch (mode) {
    case Mode::idle:
      return "idle";
    case Mode::empty:
      return "empty";
    case Mode::reg_mma:
      return "reg_mma";
    case Mode::shared_mma:
      return "shared_mma";
    case Mode::l2_mma:
      return "l2_mma";
    case Mode::dram_mma:
      return "dram_mma";
    case Mode::store_path:
      return "store_path";
  }
  return "unknown";
}

inline Mode mode_from_string(const std::string& value) {
  if (value == "idle") return Mode::idle;
  if (value == "empty") return Mode::empty;
  if (value == "reg_mma") return Mode::reg_mma;
  if (value == "shared_mma") return Mode::shared_mma;
  if (value == "l2_mma") return Mode::l2_mma;
  if (value == "dram_mma") return Mode::dram_mma;
  if (value == "store_path") return Mode::store_path;
  throw std::invalid_argument("unknown mode: " + value);
}

inline bool is_allowed_blocks_per_sm(int blocks_per_sm) {
  const auto& values = allowed_blocks_per_sm();
  return std::find(values.begin(), values.end(), blocks_per_sm) != values.end();
}

inline bool is_allowed_w_sm_kib(std::uint64_t w_sm_kib) {
  const auto& values = allowed_w_sm_kib();
  return std::find(values.begin(), values.end(), w_sm_kib) != values.end();
}

struct Feasibility {
  bool valid = false;
  bool shared_resident = false;
  std::string regime;
  std::string reason;
  double w_block_kib = 0.0;
  std::uint64_t w_block_bytes = 0;
  std::uint64_t tiles_per_block = 0;
  double full108_working_set_mib = 0.0;
};

inline Feasibility classify_feasibility(std::uint64_t w_sm_kib,
                                        int blocks_per_sm) {
  Feasibility f;
  f.full108_working_set_mib =
      static_cast<double>(kA100FullSmCount * w_sm_kib) / 1024.0;

  if (!is_allowed_blocks_per_sm(blocks_per_sm)) {
    f.regime = "invalid_blocks_per_sm";
    f.reason = "blocks_per_SM must be one of 1,2,4,8,16,32";
    return f;
  }
  if (!is_allowed_w_sm_kib(w_sm_kib)) {
    f.regime = "invalid_w_sm";
    f.reason = "W_SM_KiB must be a power-of-two sweep point from 1KiB to 128MiB";
    return f;
  }
  if (blocks_per_sm > kMaxBlocksPerSm) {
    f.regime = "invalid_blocks_per_sm";
    f.reason = "blocks_per_SM exceeds A100 resident block limit";
    return f;
  }
  if (w_sm_kib < static_cast<std::uint64_t>(blocks_per_sm)) {
    f.regime = "invalid_min_tile";
    f.reason = "W_SM_KiB < blocks_per_SM; each warp/block needs a 1KiB logical tile";
    return f;
  }

  f.valid = true;
  f.w_block_kib = static_cast<double>(w_sm_kib) / blocks_per_sm;
  f.w_block_bytes =
      (w_sm_kib * static_cast<std::uint64_t>(1024)) /
      static_cast<std::uint64_t>(blocks_per_sm);
  f.tiles_per_block =
      std::max<std::uint64_t>(1, f.w_block_bytes / kLogicalMmaInputBytes);

  const bool within_sm_capacity =
      (static_cast<double>(w_sm_kib) + blocks_per_sm) <=
      kSharedCapacityPerSmKiB;
  const bool within_block_capacity = f.w_block_kib <= kMaxSharedPerBlockKiB;
  if (within_sm_capacity && within_block_capacity) {
    f.shared_resident = true;
    f.regime = "shared_resident";
    f.reason = "W_SM + B KiB fits A100 shared memory capacity";
    return f;
  }

  if (f.full108_working_set_mib <= kA100L2MiB) {
    f.regime = "l2_candidate";
    f.reason = "shared-resident is impossible, but full-108SM working set is within the nominal A100 L2 size";
    return f;
  }

  f.regime = "dram_mixed_streaming";
  f.reason = "full-108SM working set exceeds the nominal A100 L2 size";
  return f;
}

inline bool mode_allowed_for_feasibility(Mode mode, const Feasibility& f,
                                         std::string* reason) {
  if (mode == Mode::idle) return true;
  if (!f.valid) {
    if (reason) *reason = f.regime + ": " + f.reason;
    return false;
  }
  if (mode == Mode::shared_mma && f.regime != "shared_resident") {
    if (reason) *reason = "shared_mma requires shared_resident";
    return false;
  }
  if (mode == Mode::l2_mma && f.regime != "l2_candidate") {
    if (reason) *reason = "l2_mma requires l2_candidate";
    return false;
  }
  if (mode == Mode::dram_mma && f.regime != "dram_mixed_streaming") {
    if (reason) *reason = "dram_mma requires dram_mixed_streaming";
    return false;
  }
  return true;
}

inline std::string w_sm_label(std::uint64_t w_sm_kib) {
  std::ostringstream oss;
  if (w_sm_kib < 1024) {
    oss << w_sm_kib << " KiB";
  } else {
    oss << (w_sm_kib / 1024) << " MiB";
  }
  return oss.str();
}

}  // namespace a100fp16
