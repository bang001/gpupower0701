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
  const char* architecture_family = "ampere_ga10x";
  const char* chip = "ga102";
  int cuda_arch = 86;
  int compute_major = 8;
  int compute_minor = 6;
  int full_sm_count = 82;
  int max_blocks_per_sm = 16;
  int max_warps_per_sm = 48;
  int max_threads_per_sm = 1536;
  int unified_l1_shared_kib = 128;
  int shared_capacity_per_sm_kib = 100;
  int max_shared_per_block_kib = 99;
  int l2_mib = 6;
  bool supports_l2_persistence = true;
  bool supports_async_copy = true;
  bool supports_tma = false;
  bool supports_clusters = false;
  const char* tensor_modes =
      "fp16_wmma,tf32,bf16,int8,int4,sparsity";
  const char* ncu_chip_alias = "ga102";
  const char* recommended_ncu = "current";
  const char* nvml_power_usage_semantics = "one_sec_average";
};

constexpr HardwareProfile kV100Profile{
    "v100",
    "volta",
    "gv100",
    70,
    7,
    0,
    80,
    32,
    64,
    2048,
    128,
    96,
    96,
    6,
    false,
    false,
    false,
    false,
    "fp16_wmma",
    "gv100",
    "ncu_2024_3_or_2025_1",
    "instant"};
constexpr HardwareProfile kRtx3090Profile{
    "rtx3090",
    "ampere_ga10x",
    "ga102",
    86,
    8,
    6,
    82,
    16,
    48,
    1536,
    128,
    100,
    99,
    6,
    true,
    true,
    false,
    false,
    "fp16_wmma,tf32,bf16,int8,int4,sparsity",
    "ga102",
    "current",
    "one_sec_average"};
constexpr HardwareProfile kA100Profile{
    "a100",
    "ampere_ga100",
    "ga100",
    80,
    8,
    0,
    108,
    32,
    64,
    2048,
    192,
    164,
    163,
    40,
    true,
    true,
    false,
    false,
    "fp16_wmma,tf32,bf16,fp64_tc,int8,int4,binary,sparsity",
    "ga100",
    "current",
    "instant"};
constexpr HardwareProfile kH100Profile{
    "h100",
    "hopper_gh100",
    "gh100",
    90,
    9,
    0,
    132,
    32,
    64,
    2048,
    256,
    228,
    227,
    50,
    true,
    true,
    true,
    true,
    "fp16_wmma,bf16,tf32,fp8,wgmma,tma,int8,int4",
    "gh100",
    "current",
    "one_sec_average"};
constexpr HardwareProfile kDefaultHardwareProfile = kRtx3090Profile;

inline HardwareProfile profile_from_string(const std::string& value) {
  if (value == "v100" || value == "gv100" || value == "sm70") {
    return kV100Profile;
  }
  if (value == "rtx3090" || value == "3090" || value == "sm86") {
    return kRtx3090Profile;
  }
  if (value == "a100" || value == "sm80") {
    return kA100Profile;
  }
  if (value == "h100" || value == "gh100" || value == "sm90") {
    return kH100Profile;
  }
  throw std::invalid_argument("unknown target profile: " + value);
}

inline HardwareProfile profile_from_compute_capability(int major, int minor,
                                                       const std::string& name) {
  if (major == 7 && minor == 0) return kV100Profile;
  if (major == 8 && minor == 0) return kA100Profile;
  if (major == 8 && minor == 6) return kRtx3090Profile;
  if (major == 9 && minor == 0) return kH100Profile;

  if (name.find("V100") != std::string::npos) return kV100Profile;
  if (name.find("A100") != std::string::npos) return kA100Profile;
  if (name.find("H100") != std::string::npos ||
      name.find("H800") != std::string::npos) {
    return kH100Profile;
  }
  if (name.find("RTX 3090") != std::string::npos ||
      name.find("GeForce RTX 3090") != std::string::npos) {
    return kRtx3090Profile;
  }

  std::ostringstream oss;
  oss << "no built-in target profile for compute capability " << major << "."
      << minor << " device '" << name << "'";
  throw std::invalid_argument(oss.str());
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
  clocked_empty,
  reg_fragment_only,
  reg_operand_only,
  reg_mma,
  reg_pressure,
  addr_only,
  global_l1_load_only,
  shared_scalar_load_only,
  shared_load_only,
  shared_mma,
  l2_load_only,
  l2_cg_load_only,
  l2_mma,
  dram_load_only,
  dram_cg_load_only,
  dram_mma,
  store_only,
  store_path,
};

inline std::string to_string(Mode mode) {
  switch (mode) {
    case Mode::idle:
      return "idle";
    case Mode::empty:
      return "empty";
    case Mode::clocked_empty:
      return "clocked_empty";
    case Mode::reg_fragment_only:
      return "reg_fragment_only";
    case Mode::reg_operand_only:
      return "reg_operand_only";
    case Mode::reg_mma:
      return "reg_mma";
    case Mode::reg_pressure:
      return "reg_pressure";
    case Mode::addr_only:
      return "addr_only";
    case Mode::global_l1_load_only:
      return "global_l1_load_only";
    case Mode::shared_scalar_load_only:
      return "shared_scalar_load_only";
    case Mode::shared_load_only:
      return "shared_load_only";
    case Mode::shared_mma:
      return "shared_mma";
    case Mode::l2_load_only:
      return "l2_load_only";
    case Mode::l2_cg_load_only:
      return "l2_cg_load_only";
    case Mode::l2_mma:
      return "l2_mma";
    case Mode::dram_load_only:
      return "dram_load_only";
    case Mode::dram_cg_load_only:
      return "dram_cg_load_only";
    case Mode::dram_mma:
      return "dram_mma";
    case Mode::store_only:
      return "store_only";
    case Mode::store_path:
      return "store_path";
  }
  return "unknown";
}

inline Mode mode_from_string(const std::string& value) {
  if (value == "idle") return Mode::idle;
  if (value == "empty") return Mode::empty;
  if (value == "clocked_empty") return Mode::clocked_empty;
  if (value == "reg_fragment_only") return Mode::reg_fragment_only;
  if (value == "reg_operand_only") return Mode::reg_operand_only;
  if (value == "reg_mma") return Mode::reg_mma;
  if (value == "reg_pressure") return Mode::reg_pressure;
  if (value == "addr_only") return Mode::addr_only;
  if (value == "global_l1_load_only") return Mode::global_l1_load_only;
  if (value == "shared_scalar_load_only") return Mode::shared_scalar_load_only;
  if (value == "shared_load_only") return Mode::shared_load_only;
  if (value == "shared_mma") return Mode::shared_mma;
  if (value == "l2_load_only") return Mode::l2_load_only;
  if (value == "l2_cg_load_only") return Mode::l2_cg_load_only;
  if (value == "l2_mma") return Mode::l2_mma;
  if (value == "dram_load_only") return Mode::dram_load_only;
  if (value == "dram_cg_load_only") return Mode::dram_cg_load_only;
  if (value == "dram_mma") return Mode::dram_mma;
  if (value == "store_only") return Mode::store_only;
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
  bool below_logical_tile = false;
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
  f.valid = true;
  f.w_block_kib = static_cast<double>(w_sm_kib) / blocks_per_sm;
  f.w_block_bytes =
      (w_sm_kib * static_cast<std::uint64_t>(1024)) /
      static_cast<std::uint64_t>(blocks_per_sm);
  f.tiles_per_block =
      std::max<std::uint64_t>(1, f.w_block_bytes / kLogicalMmaInputBytes);
  f.below_logical_tile = w_sm_kib < static_cast<std::uint64_t>(blocks_per_sm);

  if (f.below_logical_tile) {
    f.shared_resident = false;
    f.l2_candidate = false;
    f.dram_candidate = false;
    f.regime = "below_logical_tile";
    f.reason =
        "W_SM_KiB < blocks_per_SM; memory-backed MMA modes would not have a 1KiB logical tile per warp/block";
    return f;
  }

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
  const bool memory_backed =
      mode == Mode::global_l1_load_only ||
      mode == Mode::shared_scalar_load_only ||
      mode == Mode::shared_load_only || mode == Mode::shared_mma ||
      mode == Mode::l2_load_only || mode == Mode::l2_cg_load_only ||
      mode == Mode::l2_mma || mode == Mode::dram_load_only ||
      mode == Mode::dram_cg_load_only || mode == Mode::dram_mma;
  if (f.below_logical_tile && memory_backed) {
    if (reason) *reason = to_string(mode) + " requires at least 1KiB tile per block";
    return false;
  }
  if ((mode == Mode::shared_scalar_load_only ||
       mode == Mode::shared_load_only || mode == Mode::shared_mma) &&
      f.regime != "shared_resident") {
    if (reason) *reason = to_string(mode) + " requires shared_resident";
    return false;
  }
  if (mode == Mode::global_l1_load_only && !f.l2_candidate) {
    if (reason) *reason = to_string(mode) + " requires l2_candidate";
    return false;
  }
  if ((mode == Mode::l2_load_only || mode == Mode::l2_cg_load_only ||
       mode == Mode::l2_mma) &&
      !f.l2_candidate) {
    if (reason) *reason = to_string(mode) + " requires l2_candidate";
    return false;
  }
  if ((mode == Mode::dram_load_only || mode == Mode::dram_cg_load_only ||
       mode == Mode::dram_mma) &&
      !f.dram_candidate) {
    if (reason) *reason = to_string(mode) + " requires dram_mixed_streaming";
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
