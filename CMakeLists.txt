cmake_minimum_required(VERSION 3.24)

project(fp16_energy_v2 LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

set(CMAKE_CUDA_ARCHITECTURES 86 CACHE STRING "CUDA architectures")

find_package(CUDAToolkit REQUIRED)

find_path(NVML_INCLUDE_DIR
  NAMES nvml.h
  PATHS
    "$ENV{CUDA_PATH}/include"
    "$ENV{CONDA_PREFIX}/include"
    "/usr/include"
    "/usr/local/cuda/include"
    "/opt/cuda/include"
)

find_library(NVML_LIBRARY
  NAMES nvidia-ml libnvidia-ml.so.1 nvml nvidia-ml.lib
  PATHS
    "$ENV{CUDA_PATH}/lib/x64"
    "$ENV{CUDA_PATH}/lib64"
    "$ENV{CONDA_PREFIX}/lib"
    "/usr/lib/wsl/lib"
    "/usr/lib/x86_64-linux-gnu"
    "/usr/lib64"
    "/usr/local/cuda/lib64"
    "/opt/cuda/lib64"
)

if(NOT NVML_LIBRARY)
  message(FATAL_ERROR "NVML library was not found. Install the NVIDIA driver development files or set CUDA_PATH.")
endif()

add_executable(a100_fp16_energy_v2
  src/main.cu
  src/kernels.cu
  src/nvml_energy.cpp
  src/result_writer.cpp
)

target_include_directories(a100_fp16_energy_v2 PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_energy_v2 PRIVATE "${NVML_INCLUDE_DIR}")
endif()

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

# Softmax intentionally has a separate binary and CSV schema from the WMMA
# benchmark.  Its 256-thread row kernel and element denominator are not
# compatible with the Tensor-only Mode/ResultRow assumptions above.
add_executable(a100_fp16_softmax_energy
  src/softmax_main.cu
  src/softmax_kernels.cu
  src/softmax_result_writer.cpp
  src/nvml_energy.cpp
)

target_include_directories(a100_fp16_softmax_energy PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_softmax_energy PRIVATE "${NVML_INCLUDE_DIR}")
endif()

target_link_libraries(a100_fp16_softmax_energy PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_options(a100_fp16_softmax_energy PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_softmax_energy PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)

# This is deliberately a sibling of the EX2 operand-rate harness above.  It
# measures complete Softmax policies and has an independent CSV schema, so its
# stage-level precision comparisons cannot be mistaken for EX2-only results.
add_executable(a100_fp16_softmax_whole_precision_energy
  src/softmax_whole_precision_main.cu
  src/softmax_whole_precision_kernels.cu
  src/softmax_whole_precision_result_writer.cpp
  src/nvml_energy.cpp
)

target_include_directories(a100_fp16_softmax_whole_precision_energy PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_softmax_whole_precision_energy PRIVATE
    "${NVML_INCLUDE_DIR}"
  )
endif()

target_link_libraries(a100_fp16_softmax_whole_precision_energy PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_options(a100_fp16_softmax_whole_precision_energy PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_softmax_whole_precision_energy PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)

# Keep the targeted AB/BA confirmation binary distinct from the historical
# stage-isolation target.  Existing raw evidence binds its binary SHA-256 to
# the old executable, so rebuilding this new target must not overwrite it.
add_executable(a100_fp16_softmax_whole_precision_confirmation_energy
  src/softmax_whole_precision_main.cu
  src/softmax_whole_precision_kernels.cu
  src/softmax_whole_precision_result_writer.cpp
  src/nvml_energy.cpp
)

target_include_directories(a100_fp16_softmax_whole_precision_confirmation_energy PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_softmax_whole_precision_confirmation_energy PRIVATE
    "${NVML_INCLUDE_DIR}"
  )
endif()

target_link_libraries(a100_fp16_softmax_whole_precision_confirmation_energy PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_options(a100_fp16_softmax_whole_precision_confirmation_energy PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_softmax_whole_precision_confirmation_energy PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)

# The endpoint-range binary is intentionally distinct from the frozen
# stage-isolation and confirmation binaries.  It compiles only complete
# FP32/scalar-FP16/packed-FP16x2 policies at the small set of range widths,
# which keeps historical S=512 SASS and binary hashes reproducible.
add_executable(a100_fp16_softmax_whole_precision_range_energy
  src/softmax_whole_precision_main.cu
  src/softmax_whole_precision_range_kernels.cu
  src/softmax_whole_precision_result_writer.cpp
  src/nvml_energy.cpp
)

target_include_directories(a100_fp16_softmax_whole_precision_range_energy PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_softmax_whole_precision_range_energy PRIVATE
    "${NVML_INCLUDE_DIR}"
  )
endif()

target_link_libraries(a100_fp16_softmax_whole_precision_range_energy PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_definitions(a100_fp16_softmax_whole_precision_range_energy PRIVATE
  FP16SOFTMAX_WHOLE_PRECISION_RANGE_BUILD=1
)

target_compile_options(a100_fp16_softmax_whole_precision_range_energy PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_softmax_whole_precision_range_energy PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)

# Operand-rate ATC probes for complete-Softmax stages.  Control and treatment
# use the same stage/policy kernel specialization; a uniform runtime flag adds
# exactly one redundant selected-stage pass while preserving primary output.
add_executable(a100_fp16_softmax_whole_stage_atc
  src/softmax_whole_stage_atc_main.cu
  src/softmax_whole_stage_atc_kernels.cu
  src/nvml_energy.cpp
)

target_include_directories(a100_fp16_softmax_whole_stage_atc PRIVATE
  include
)

if(NVML_INCLUDE_DIR)
  target_include_directories(a100_fp16_softmax_whole_stage_atc PRIVATE
    "${NVML_INCLUDE_DIR}"
  )
endif()

target_link_libraries(a100_fp16_softmax_whole_stage_atc PRIVATE
  CUDA::cudart
  "${NVML_LIBRARY}"
)

target_compile_options(a100_fp16_softmax_whole_stage_atc PRIVATE
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
  $<$<COMPILE_LANGUAGE:CUDA>:-lineinfo>
  $<$<COMPILE_LANGUAGE:CUDA>:-Xptxas=-v>
)

set_target_properties(a100_fp16_softmax_whole_stage_atc PROPERTIES
  CUDA_SEPARABLE_COMPILATION OFF
  CUDA_RESOLVE_DEVICE_SYMBOLS ON
)
