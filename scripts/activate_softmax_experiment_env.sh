#!/usr/bin/env bash

# Source this file from any checkout location.  It intentionally does not run
# `conda activate`, so it does not rewrite the caller's shell prompt or conda
# stack; only the exact reviewed experiment tools are selected.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "ERROR: source this script instead of executing it:" >&2
  echo "  source scripts/activate_softmax_experiment_env.sh" >&2
  exit 2
fi

_gpupwr_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
GPUPWR_REPO_ROOT="$(cd -- "${_gpupwr_script_dir}/.." && pwd -P)"

GPUPWR_CUDA_ENV="${GPUPWR_CUDA_ENV:-/home/bang001/miniforge3/envs/ssc21env}"
GPUPWR_NCU_BIN="${GPUPWR_NCU_BIN:-/home/bang001/.local/NVIDIA-Nsight-Compute-2026.2.1/ncu}"
GPUPWR_CUOBJDUMP_BIN="${GPUPWR_CUOBJDUMP_BIN:-/home/bang001/miniforge3/lib/python3.12/site-packages/triton/backends/nvidia/bin/cuobjdump}"
GPUPWR_NVIDIA_SMI_BIN="${GPUPWR_NVIDIA_SMI_BIN:-/usr/lib/wsl/lib/nvidia-smi}"
GPUPWR_NVML_LIBRARY="${GPUPWR_NVML_LIBRARY:-/usr/lib/wsl/lib/libnvidia-ml.so.1}"
GPUPWR_NINJA_BIN="${GPUPWR_NINJA_BIN:-/home/bang001/.local/bin/ninja}"
GPUPWR_CMAKE_BIN="${GPUPWR_CMAKE_BIN:-${GPUPWR_CUDA_ENV}/bin/cmake}"
GPUPWR_PYTHON_BIN="${GPUPWR_PYTHON_BIN:-${GPUPWR_CUDA_ENV}/bin/python}"
GPUPWR_NVCC_BIN="${GPUPWR_NVCC_BIN:-${GPUPWR_CUDA_ENV}/bin/nvcc}"

if [[ ! -d "${GPUPWR_REPO_ROOT}/.git" ||
      ! -f "${GPUPWR_REPO_ROOT}/CMakeLists.txt" ]]; then
  echo "ERROR: not a normal GPUPower repository: ${GPUPWR_REPO_ROOT}" >&2
  return 1
fi

for _gpupwr_executable in \
  "${GPUPWR_NVCC_BIN}" \
  "${GPUPWR_CMAKE_BIN}" \
  "${GPUPWR_PYTHON_BIN}" \
  "${GPUPWR_NCU_BIN}" \
  "${GPUPWR_CUOBJDUMP_BIN}" \
  "${GPUPWR_NVIDIA_SMI_BIN}" \
  "${GPUPWR_NINJA_BIN}"; do
  if [[ ! -x "${_gpupwr_executable}" ]]; then
    echo "ERROR: required executable is missing: ${_gpupwr_executable}" >&2
    return 1
  fi
done

if [[ ! -f "${GPUPWR_NVML_LIBRARY}" ]]; then
  echo "ERROR: WSL NVML library is missing: ${GPUPWR_NVML_LIBRARY}" >&2
  return 1
fi

_gpupwr_prepend_path() {
  local directory="$1"
  case ":${PATH:-}:" in
    *":${directory}:"*) ;;
    *) PATH="${directory}${PATH:+:${PATH}}" ;;
  esac
}

_gpupwr_prepend_library_path() {
  local directory="$1"
  case ":${LD_LIBRARY_PATH:-}:" in
    *":${directory}:"*) ;;
    *) LD_LIBRARY_PATH="${directory}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" ;;
  esac
}

_gpupwr_prepend_path "/home/bang001/.local/bin"
_gpupwr_prepend_path "$(dirname -- "${GPUPWR_CUOBJDUMP_BIN}")"
_gpupwr_prepend_path "$(dirname -- "${GPUPWR_NCU_BIN}")"
_gpupwr_prepend_path "${GPUPWR_CUDA_ENV}/bin"
_gpupwr_prepend_path "$(dirname -- "${GPUPWR_NVIDIA_SMI_BIN}")"

_gpupwr_prepend_library_path "${GPUPWR_CUDA_ENV}/targets/x86_64-linux/lib"
_gpupwr_prepend_library_path "/usr/lib/wsl/lib"

NVCC="${GPUPWR_NVCC_BIN}"
CUDACXX="${GPUPWR_NVCC_BIN}"
CUDAToolkit_ROOT="${GPUPWR_CUDA_ENV}"
CUDA_HOME="${GPUPWR_CUDA_ENV}"
CUDA_PATH="${GPUPWR_CUDA_ENV}"
NCU="${GPUPWR_NCU_BIN}"
NCU_BIN="${GPUPWR_NCU_BIN}"
CUOBJDUMP="${GPUPWR_CUOBJDUMP_BIN}"
NVIDIA_SMI="${GPUPWR_NVIDIA_SMI_BIN}"
NVML_LIBRARY="${GPUPWR_NVML_LIBRARY}"

export GPUPWR_REPO_ROOT GPUPWR_CUDA_ENV GPUPWR_NCU_BIN
export GPUPWR_CUOBJDUMP_BIN GPUPWR_NVIDIA_SMI_BIN GPUPWR_NVML_LIBRARY
export GPUPWR_NINJA_BIN GPUPWR_CMAKE_BIN GPUPWR_PYTHON_BIN GPUPWR_NVCC_BIN
export NVCC CUDACXX CUDAToolkit_ROOT CUDA_HOME CUDA_PATH
export NCU NCU_BIN CUOBJDUMP NVIDIA_SMI NVML_LIBRARY
export PATH LD_LIBRARY_PATH

if [[ "${GPUPWR_ENV_QUIET:-0}" != "1" ]]; then
  echo "Softmax experiment environment activated"
  echo "  repository : ${GPUPWR_REPO_ROOT}"
  echo "  CUDA       : ${GPUPWR_CUDA_ENV}"
  echo "  NCU        : ${NCU}"
  echo "  cuobjdump  : ${CUOBJDUMP}"
  echo "  NVML       : ${NVML_LIBRARY}"
fi

unset _gpupwr_script_dir _gpupwr_executable
unset -f _gpupwr_prepend_path _gpupwr_prepend_library_path
