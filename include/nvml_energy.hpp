#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace a100fp16 {

struct GpuEnergySample {
  int gpu_id = -1;
  std::uint64_t energy_mj = 0;
  bool energy_counter_supported = false;
  unsigned int power_mw = 0;
  bool power_usage_supported = false;
  bool field_power_instant_supported = false;
  bool field_power_average_supported = false;
  unsigned int field_power_instant_mw = 0;
  unsigned int field_power_average_mw = 0;
  unsigned int sm_clock_mhz = 0;
  unsigned int mem_clock_mhz = 0;
  unsigned int temp_c = 0;
  int compute_major = 0;
  int compute_minor = 0;
  std::string name;
  std::string driver_version;
  std::string nvml_version;
  double timestamp_s = 0.0;
  std::string notes;
};

class NvmlEnergy {
 public:
  NvmlEnergy();
  ~NvmlEnergy();

  NvmlEnergy(const NvmlEnergy&) = delete;
  NvmlEnergy& operator=(const NvmlEnergy&) = delete;

  int device_count() const;
  GpuEnergySample sample(int gpu_id) const;
  std::vector<GpuEnergySample> sample_all() const;

 private:
  int device_count_ = 0;
};

}  // namespace a100fp16
