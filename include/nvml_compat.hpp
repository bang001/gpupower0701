#pragma once

#if __has_include(<nvml.h>)
#include <nvml.h>
#else

extern "C" {

typedef enum nvmlReturn_enum {
  NVML_SUCCESS = 0,
} nvmlReturn_t;

typedef struct nvmlDevice_st* nvmlDevice_t;

typedef enum nvmlClockType_enum {
  NVML_CLOCK_SM = 1,
  NVML_CLOCK_MEM = 2,
} nvmlClockType_t;

typedef enum nvmlTemperatureSensors_enum {
  NVML_TEMPERATURE_GPU = 0,
} nvmlTemperatureSensors_t;

typedef enum nvmlEnableState_enum {
  NVML_FEATURE_DISABLED = 0,
  NVML_FEATURE_ENABLED = 1,
} nvmlEnableState_t;

nvmlReturn_t nvmlInit_v2(void);
nvmlReturn_t nvmlShutdown(void);
const char* nvmlErrorString(nvmlReturn_t result);
nvmlReturn_t nvmlDeviceGetCount_v2(unsigned int* deviceCount);
nvmlReturn_t nvmlDeviceGetHandleByIndex_v2(unsigned int index,
                                           nvmlDevice_t* device);
nvmlReturn_t nvmlDeviceGetTotalEnergyConsumption(nvmlDevice_t device,
                                                 unsigned long long* energy);
nvmlReturn_t nvmlDeviceGetPowerUsage(nvmlDevice_t device, unsigned int* power);
nvmlReturn_t nvmlDeviceGetClockInfo(nvmlDevice_t device, nvmlClockType_t type,
                                    unsigned int* clock);
nvmlReturn_t nvmlDeviceGetTemperature(nvmlDevice_t device,
                                      nvmlTemperatureSensors_t sensorType,
                                      unsigned int* temp);
nvmlReturn_t nvmlDeviceGetPowerManagementLimit(nvmlDevice_t device,
                                               unsigned int* limit);
nvmlReturn_t nvmlDeviceGetEccMode(nvmlDevice_t device,
                                  nvmlEnableState_t* current,
                                  nvmlEnableState_t* pending);

}  // extern "C"

#endif
