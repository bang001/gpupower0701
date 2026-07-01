cmake_minimum_required(VERSION 3.24)

project(a100_fp16_energy_v2 LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

set(CMAKE_CUDA_ARCHITECTURES 80 CACHE STRING "CUDA architectures")

find_package(CUDAToolkit REQUIRED)

find_path(NVML_INCLUDE_DIR
  NAMES nvml.h
  PATHS
    "$ENV{CUDA_PATH}/include"
    "/usr/include"
    "/usr/local/cuda/include"
    "/opt/cuda/include"
)

find_library(NVML_LIBRARY
  NAMES nvidia-ml nvml nvidia-ml.lib
  PATHS
    "$ENV{CUDA_PATH}/lib/x64"
    "$ENV{CUDA_PATH}/lib64"
    "/usr/lib/x86_64-linux-gnu"
    "/usr/lib64"
    "/usr/local/cuda/lib64"
    "/opt/cuda/lib64"
)

if(NOT NVML_INCLUDE_DIR OR NOT NVML_LIBRARY)
  message(FATAL_ERROR "NVML was not found. Install the NVIDIA driver development files or set CUDA_PATH.")
endif()

add_executable(a100_fp16_energy_v2
  src/main.cu
  src/kernels.cu
  src/nvml_energy.cpp
  src/result_writer.cpp
)

target_include_directories(a100_fp16_energy_v2 PRIVATE
  include
  "${NVML_INCLUDE_DIR}"
)

target_link_libraries(a100_fp16_energy_v2 PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_options(a100_fp16_energy_v2 PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_energy_v2 PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)
