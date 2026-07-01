#include "nvml_energy.hpp"

#include "nvml_compat.hpp"

#include <chrono>
#include <sstream>
#include <stdexcept>

namespace a100fp16 {
namespace {

using Clock = std::chrono::steady_clock;

void check_nvml(nvmlReturn_t status, const char* what) {
  if (status != NVML_SUCCESS) {
    std::ostringstream oss;
    oss << what << " failed: " << nvmlErrorString(status);
    throw std::runtime_error(oss.str());
  }
}

double now_seconds() {
  return std::chrono::duration<double>(Clock::now().time_since_epoch()).count();
}

}  // namespace

NvmlEnergy::NvmlEnergy() {
  check_nvml(nvmlInit_v2(), "nvmlInit_v2");
  unsigned int count = 0;
  check_nvml(nvmlDeviceGetCount_v2(&count), "nvmlDeviceGetCount_v2");
  device_count_ = static_cast<int>(count);
}

NvmlEnergy::~NvmlEnergy() { nvmlShutdown(); }

int NvmlEnergy::device_count() const { return device_count_; }

GpuEnergySample NvmlEnergy::sample(int gpu_id) const {
  if (gpu_id < 0 || gpu_id >= device_count_) {
    throw std::out_of_range("NVML gpu_id out of range");
  }

  nvmlDevice_t device{};
  check_nvml(nvmlDeviceGetHandleByIndex_v2(static_cast<unsigned int>(gpu_id),
                                           &device),
             "nvmlDeviceGetHandleByIndex_v2");

  GpuEnergySample sample;
  sample.gpu_id = gpu_id;
  sample.timestamp_s = now_seconds();

  unsigned long long energy_mj = 0;
  std::ostringstream notes;
  nvmlReturn_t status =
      nvmlDeviceGetTotalEnergyConsumption(device, &energy_mj);
  if (status == NVML_SUCCESS) {
    sample.energy_mj = static_cast<std::uint64_t>(energy_mj);
    sample.energy_counter_supported = true;
    notes << "energy_source=nvml_total_energy;";
  } else {
    notes << "energy_counter_unavailable=" << nvmlErrorString(status) << ";"
          << "energy_source=power_trapezoid;";
  }

  unsigned int value = 0;
  status = nvmlDeviceGetPowerUsage(device, &value);
  if (status == NVML_SUCCESS) {
    sample.power_mw = value;
    notes << "power_mw=" << value << ";";
  } else {
    notes << "power_unavailable=" << nvmlErrorString(status) << ";";
  }

  value = 0;
  status = nvmlDeviceGetClockInfo(device, NVML_CLOCK_SM, &value);
  if (status == NVML_SUCCESS) {
    sample.sm_clock_mhz = value;
  } else {
    notes << "sm_clock_unavailable=" << nvmlErrorString(status) << ";";
  }

  value = 0;
  status = nvmlDeviceGetClockInfo(device, NVML_CLOCK_MEM, &value);
  if (status == NVML_SUCCESS) {
    sample.mem_clock_mhz = value;
  } else {
    notes << "mem_clock_unavailable=" << nvmlErrorString(status) << ";";
  }

  value = 0;
  status = nvmlDeviceGetTemperature(device, NVML_TEMPERATURE_GPU, &value);
  if (status == NVML_SUCCESS) {
    sample.temp_c = value;
  } else {
    notes << "temperature_unavailable=" << nvmlErrorString(status) << ";";
  }

  unsigned int power_limit_mw = 0;
  status = nvmlDeviceGetPowerManagementLimit(device, &power_limit_mw);
  if (status == NVML_SUCCESS) {
    notes << "power_limit_mw=" << power_limit_mw << ";";
  } else {
    notes << "power_limit_unavailable=" << nvmlErrorString(status) << ";";
  }

  nvmlEnableState_t ecc_current = NVML_FEATURE_DISABLED;
  nvmlEnableState_t ecc_pending = NVML_FEATURE_DISABLED;
  status = nvmlDeviceGetEccMode(device, &ecc_current, &ecc_pending);
  if (status == NVML_SUCCESS) {
    notes << "ecc_current=" << static_cast<int>(ecc_current)
          << ";ecc_pending=" << static_cast<int>(ecc_pending) << ";";
  } else {
    notes << "ecc_unavailable=" << nvmlErrorString(status) << ";";
  }

  sample.notes = notes.str();
  return sample;
}

std::vector<GpuEnergySample> NvmlEnergy::sample_all() const {
  std::vector<GpuEnergySample> samples;
  samples.reserve(device_count_);
  for (int gpu = 0; gpu < device_count_; ++gpu) {
    samples.push_back(sample(gpu));
  }
  return samples;
}

}  // namespace a100fp16
