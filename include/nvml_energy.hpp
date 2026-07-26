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

// Lightweight total-energy sample for in-kernel counter tracing.  The full
// sample() call intentionally gathers clocks, temperature, power fields, and
// provenance; polling all of those at millisecond cadence would add needless
// host overhead.  This type reads only the monotonic NVML energy counter and a
// steady-clock timestamp.
struct GpuEnergyCounterSample {
  std::uint64_t energy_mj = 0;
  bool energy_counter_supported = false;
  double query_start_s = 0.0;
  double query_end_s = 0.0;
  double timestamp_s = 0.0;
  double query_latency_s = 0.0;
};

class NvmlEnergy {
 public:
  NvmlEnergy();
  ~NvmlEnergy();

  NvmlEnergy(const NvmlEnergy&) = delete;
  NvmlEnergy& operator=(const NvmlEnergy&) = delete;

  int device_count() const;
  GpuEnergySample sample(int gpu_id) const;
  // CUDA logical ordinals can be remapped by CUDA_VISIBLE_DEVICES and do not
  // necessarily equal NVML physical indices.  Softmax energy measurements use
  // the CUDA device's PCI bus id to bind both APIs to the same physical board.
  GpuEnergySample sample_by_pci_bus_id(const std::string& pci_bus_id,
                                       int cuda_logical_gpu_id) const;
  GpuEnergyCounterSample sample_energy_counter(int gpu_id) const;
  GpuEnergyCounterSample sample_energy_counter_by_pci_bus_id(
      const std::string& pci_bus_id) const;
  std::vector<GpuEnergySample> sample_all() const;

 private:
  int device_count_ = 0;
};

}  // namespace a100fp16
