#pragma once

#include <algorithm>
#include <cstdint>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace a100fp16 {

constexpr int kThreadsPerBlock = 32;
constexpr int kWarpSize = 32;
constexpr int kLogicalMmaInputBytes = 1024;
constexpr int kLogicalMmaInputBits = 8192;
constexpr int kLogicalMmaFlop = 8192;

struct HardwareProfile {
  const char* name = "rtx3090";
  int cuda_arch = 86;
  int compute_major = 8;
  int compute_minor = 6;
  int full_sm_count = 82;
  int max_blocks_per_sm = 16;
  int shared_capacity_per_sm_kib = 100;
  int max_shared_per_block_kib = 99;
  int l2_mib = 6;
};

constexpr HardwareProfile kRtx3090Profile{
    "rtx3090", 86, 8, 6, 82, 16, 100, 99, 6};
constexpr HardwareProfile kA100Profile{
    "a100", 80, 8, 0, 108, 32, 164, 163, 40};
constexpr HardwareProfile kDefaultHardwareProfile = kRtx3090Profile;

inline HardwareProfile profile_from_string(const std::string& value) {
  if (value == "rtx3090" || value == "3090" || value == "sm86") {
    return kRtx3090Profile;
  }
  if (value == "a100" || value == "sm80") {
    return kA100Profile;
  }
  throw std::invalid_argument("unknown target profile: " + value);
}

inline std::vector<int> allowed_blocks_per_sm(const HardwareProfile& profile) {
  static const std::vector<int> values{1, 2, 4, 8, 16, 32};
  std::vector<int> out;
  for (int value : values) {
    if (value <= profile.max_blocks_per_sm) out.push_back(value);
  }
  return out;
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

inline bool is_allowed_blocks_per_sm(int blocks_per_sm,
                                     const HardwareProfile& profile) {
  const auto values = allowed_blocks_per_sm(profile);
  return std::find(values.begin(), values.end(), blocks_per_sm) != values.end();
}

inline bool is_allowed_w_sm_kib(std::uint64_t w_sm_kib) {
  const auto& values = allowed_w_sm_kib();
  return std::find(values.begin(), values.end(), w_sm_kib) != values.end();
}

struct Feasibility {
  bool valid = false;
  bool shared_resident = false;
  bool l2_candidate = false;
  bool dram_candidate = false;
  std::string regime;
  std::string reason;
  double w_block_kib = 0.0;
  std::uint64_t w_block_bytes = 0;
  std::uint64_t tiles_per_block = 0;
  double full_gpu_working_set_mib = 0.0;
};

inline Feasibility classify_feasibility(std::uint64_t w_sm_kib,
                                        int blocks_per_sm,
                                        const HardwareProfile& profile) {
  Feasibility f;
  f.full_gpu_working_set_mib =
      static_cast<double>(profile.full_sm_count * w_sm_kib) / 1024.0;

  if (!is_allowed_blocks_per_sm(blocks_per_sm, profile)) {
    f.regime = "invalid_blocks_per_sm";
    std::ostringstream oss;
    oss << "blocks_per_SM exceeds " << profile.name
        << " resident block limit " << profile.max_blocks_per_sm;
    f.reason = oss.str();
    return f;
  }
  if (!is_allowed_w_sm_kib(w_sm_kib)) {
    f.regime = "invalid_w_sm";
    f.reason = "W_SM_KiB must be a power-of-two sweep point from 1KiB to 128MiB";
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
      profile.shared_capacity_per_sm_kib;
  const bool within_block_capacity =
      f.w_block_kib <= profile.max_shared_per_block_kib;
  f.shared_resident = within_sm_capacity && within_block_capacity;
  f.l2_candidate = f.full_gpu_working_set_mib <= profile.l2_mib;
  f.dram_candidate = !f.l2_candidate;

  if (f.shared_resident) {
    f.regime = "shared_resident";
    std::ostringstream oss;
    oss << "W_SM + B KiB fits " << profile.name
        << " shared memory capacity";
    if (f.l2_candidate) {
      oss << "; full-GPU working set also fits nominal L2";
    }
    f.reason = oss.str();
    return f;
  }

  if (f.l2_candidate) {
    f.regime = "l2_candidate";
    f.reason =
        "shared-resident is impossible, but full-GPU working set is within the nominal L2 size";
    return f;
  }

  f.regime = "dram_mixed_streaming";
  f.reason = "full-GPU working set exceeds the nominal L2 size";
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
  if (mode == Mode::l2_mma && !f.l2_candidate) {
    if (reason) *reason = "l2_mma requires l2_candidate";
    return false;
  }
  if (mode == Mode::dram_mma && !f.dram_candidate) {
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
