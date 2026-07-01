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
  unsigned int sm_clock_mhz = 0;
  unsigned int mem_clock_mhz = 0;
  unsigned int temp_c = 0;
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
