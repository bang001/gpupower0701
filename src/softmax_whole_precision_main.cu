#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <mutex>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <unistd.h>

#include "nvml_energy.hpp"
#include "softmax_whole_precision_config.hpp"
#include "softmax_whole_precision_kernels.cuh"
#include "softmax_whole_precision_result_writer.hpp"

namespace fp16softmax::whole_precision {
namespace {

#define CUDA_CHECK(call)                                                        \
  do {                                                                          \
    const cudaError_t status__ = (call);                                        \
    if (status__ != cudaSuccess) {                                              \
      std::ostringstream error__;                                               \
      error__ << #call << " failed: " << cudaGetErrorString(status__);         \
      throw std::runtime_error(error__.str());                                  \
    }                                                                           \
  } while (0)

using Clock = std::chrono::steady_clock;

struct Options {
  int gpu_id = 0;
  std::string target_profile = "rtx3090";
  std::vector<std::vector<Policy>> schedule;
  std::uint64_t grid_blocks = 16;
  double seconds = 13.0;
  double preheat_seconds = 20.0;
  double idle_seconds = 1.0;
  double trace_sample_ms = 500.0;
  int trace_min_updates = 16;
  float logit_scale = 4.0f;
  std::uint64_t seed = 0x4d595df4d0f33173ull;
  std::string design_id = "manual";
  std::string stage_group = "manual";
  std::string session_order;
  std::string session_id = "whole_precision";
  std::string output = "results/raw/softmax_whole_precision_raw.csv";
  std::string trace_output;
  std::string binary_sha256;
  bool validate_only = false;
  bool dry_run = false;
};

struct DeviceState {
  cudaDeviceProp properties{};
  int gpu_id = -1;
  std::string pci_bus_id;
  std::uint64_t grid_blocks = 0;
  std::uint64_t rows = 0;
  std::size_t element_count = 0;
  half* input_f16 = nullptr;
  float* input_f32 = nullptr;
  half* output_f16 = nullptr;
  float* output_f32 = nullptr;
  std::uint32_t* token_by_block = nullptr;
  int* smid_by_block = nullptr;
  int* sm_counts = nullptr;
  cudaStream_t stream = nullptr;
};

struct SmidCheck {
  bool ok = false;
  int unique = 0;
  int total_blocks = 0;
  int max_blocks_on_sm = 0;
};

struct IdleMeasurement {
  double elapsed_s = 0.0;
  double delta_j = 0.0;
  double power_w = 0.0;
};

struct KernelMeasurement {
  a100fp16::GpuEnergySample before;
  a100fp16::GpuEnergySample after;
  Clock::time_point host_start;
  Clock::time_point host_end;
  double elapsed_s = 0.0;
  double endpoint_delta_j = 0.0;
  double delta_j = 0.0;
  std::vector<a100fp16::GpuEnergyCounterSample> trace;
  int trace_update_count = 0;
  int trace_fit_point_count = 0;
  double trace_power_w = 0.0;
  double trace_r2 = 0.0;
  double trace_rmse_mj = 0.0;
  double trace_max_query_latency_s = 0.0;
  std::string trace_status = "not_run";
  SmidCheck smid;
};

struct ValidationResult {
  std::string id = "not_run";
  // These aggregate with std::max below.  NaN would make every subsequent
  // aggregate NaN and silently defeat the numerical gate.
  double max_abs_error = 0.0;
  double max_row_sum_error = 0.0;
  double max_abs_gate = 0.0;
  double max_row_sum_gate = 0.0;
  bool passed = false;
  std::uint64_t nonfinite_count = 0;
  std::uint64_t underflow_count = 0;
};

double steady_seconds(Clock::time_point point) {
  return std::chrono::duration<double>(point.time_since_epoch()).count();
}

std::uint64_t epoch_milliseconds() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count());
}

double percentile(std::vector<double> values, double quantile) {
  if (values.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::sort(values.begin(), values.end());
  const double position = quantile * static_cast<double>(values.size() - 1);
  const std::size_t lower = static_cast<std::size_t>(std::floor(position));
  const std::size_t upper = static_cast<std::size_t>(std::ceil(position));
  if (lower == upper) return values[lower];
  return values[lower] + (values[upper] - values[lower]) * (position - lower);
}

double median(std::vector<double> values) { return percentile(std::move(values), 0.5); }

std::vector<std::string> split(const std::string& value, char delimiter) {
  std::vector<std::string> result;
  std::size_t start = 0;
  while (start <= value.size()) {
    const std::size_t end = value.find(delimiter, start);
    const std::size_t length = end == std::string::npos ? value.size() - start
                                                          : end - start;
    const std::string token = value.substr(start, length);
    if (token.empty()) throw std::invalid_argument("empty policy schedule token");
    result.push_back(token);
    if (end == std::string::npos) break;
    start = end + 1;
  }
  return result;
}

std::vector<std::vector<Policy>> parse_schedule(const std::string& value) {
  std::vector<std::vector<Policy>> schedule;
  for (const std::string& block : split(value, ';')) {
    std::vector<Policy> policies;
    for (const std::string& token : split(block, ',')) {
      policies.push_back(policy_from_string(token));
    }
    if (policies.empty()) throw std::invalid_argument("empty schedule block");
    schedule.push_back(std::move(policies));
  }
  return schedule;
}

std::string default_trace_path(const std::string& output) {
  const std::filesystem::path path(output);
  const std::string stem = path.stem().string();
  return (path.parent_path() / (stem + "_energy_trace.csv")).string();
}

void usage(const char* program) {
  std::cout
      << "Usage: " << program << " [options]\n\n"
      << "Whole-Softmax precision options (initial S=512 design):\n"
      << "  --policy <id>                         one policy, one measured role\n"
      << "  --policy-schedule A,B,C;A,C,B;...      persistent ordered policy blocks\n"
      << "  --grid-blocks <n>                      default 16 underfilled CTAs\n"
      << "  --seconds <s>                          per-policy calibrated role duration\n"
      << "  --preheat-seconds <s>                  nominal per-policy preheat (default 20)\n"
      << "  --idle-seconds <s>                     per-role idle baseline\n"
      << "  --energy-trace-sample-ms <ms>          default 500\n"
      << "  --energy-trace-min-updates <n>         default 16\n"
      << "  --target-profile rtx3090|auto\n"
      << "  --design-id <id> --stage-group <id> --session-order <id>\n"
      << "  --session-id <id> --output <csv> --energy-trace-output <csv>\n"
      << "  --binary-sha256 <hex> --validate-only --dry-run\n\n"
      << "Policy IDs:\n";
  for (const Policy policy : {
           Policy::fp32_io_fp32_all, Policy::fp16_io_fp32_all,
           Policy::exp_fp16_scalar, Policy::exp_fp16x2,
           Policy::reduction_fp16_scalar, Policy::reduction_fp16x2,
           Policy::normalization_fp16_scalar, Policy::normalization_fp16x2,
           Policy::fp16_scalar_all, Policy::fp16x2_all}) {
    const auto spec = policy_spec(policy);
    std::cout << "  " << spec.name << " : " << spec.description << "\n";
  }
}

Options parse_options(int argc, char** argv) {
  Options options;
  std::string single_policy;
  std::string schedule;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    const auto value = [&]() -> std::string {
      if (index + 1 >= argc) {
        throw std::invalid_argument("missing value for " + argument);
      }
      return argv[++index];
    };
    if (argument == "--help" || argument == "-h") {
      usage(argv[0]);
      std::exit(0);
    } else if (argument == "--policy") {
      single_policy = value();
    } else if (argument == "--policy-schedule") {
      schedule = value();
    } else if (argument == "--gpu-id") {
      options.gpu_id = std::stoi(value());
    } else if (argument == "--target-profile") {
      options.target_profile = value();
    } else if (argument == "--grid-blocks") {
      options.grid_blocks = std::stoull(value());
    } else if (argument == "--seconds") {
      options.seconds = std::stod(value());
    } else if (argument == "--preheat-seconds") {
      options.preheat_seconds = std::stod(value());
    } else if (argument == "--idle-seconds") {
      options.idle_seconds = std::stod(value());
    } else if (argument == "--energy-trace-sample-ms") {
      options.trace_sample_ms = std::stod(value());
    } else if (argument == "--energy-trace-min-updates") {
      options.trace_min_updates = std::stoi(value());
    } else if (argument == "--logit-scale") {
      options.logit_scale = std::stof(value());
    } else if (argument == "--seed") {
      options.seed = std::stoull(value());
    } else if (argument == "--design-id") {
      options.design_id = value();
    } else if (argument == "--stage-group") {
      options.stage_group = value();
    } else if (argument == "--session-order") {
      options.session_order = value();
    } else if (argument == "--session-id") {
      options.session_id = value();
    } else if (argument == "--output") {
      options.output = value();
    } else if (argument == "--energy-trace-output") {
      options.trace_output = value();
    } else if (argument == "--binary-sha256") {
      options.binary_sha256 = value();
    } else if (argument == "--validate-only") {
      options.validate_only = true;
    } else if (argument == "--dry-run") {
      options.dry_run = true;
    } else {
      throw std::invalid_argument("unknown option: " + argument);
    }
  }
  if (!single_policy.empty() && !schedule.empty()) {
    throw std::invalid_argument("--policy and --policy-schedule are exclusive");
  }
  if (!schedule.empty()) {
    options.schedule = parse_schedule(schedule);
  } else {
    const Policy policy = single_policy.empty()
                              ? Policy::fp32_io_fp32_all
                              : policy_from_string(single_policy);
    options.schedule = {{policy}};
  }
  if (options.target_profile != "rtx3090" && options.target_profile != "auto") {
    throw std::invalid_argument("--target-profile must be rtx3090 or auto");
  }
  if (options.gpu_id < 0 || options.grid_blocks == 0 || options.seconds <= 0.0 ||
      options.preheat_seconds <= 0.0 || options.idle_seconds <= 0.0 ||
      options.trace_sample_ms < 200.0 || options.trace_min_updates < 2 ||
      !(options.logit_scale > 0.0f)) {
    throw std::invalid_argument("invalid whole-precision runtime option");
  }
  if (options.trace_output.empty()) options.trace_output = default_trace_path(options.output);
  if (options.trace_output == options.output) {
    throw std::invalid_argument("trace output must differ from raw output");
  }
  return options;
}

std::vector<Policy> unique_policies(const Options& options) {
  std::vector<Policy> result;
  for (const auto& block : options.schedule) {
    for (const Policy policy : block) {
      if (std::find(result.begin(), result.end(), policy) == result.end()) {
        result.push_back(policy);
      }
    }
  }
  return result;
}

void require_profile(const Options& options, const DeviceState& state,
                     const std::vector<Policy>& policies) {
  if (options.target_profile == "auto") return;
  std::string name = state.properties.name;
  std::transform(name.begin(), name.end(), name.begin(), [](unsigned char value) {
    return static_cast<char>(std::tolower(value));
  });
  if (state.properties.major != 8 || state.properties.minor != 6 ||
      name.find("rtx 3090") == std::string::npos ||
      state.properties.multiProcessorCount != 82) {
    throw std::runtime_error(
        "whole-precision rtx3090 profile requires a full 82-SM NVIDIA GeForce RTX 3090");
  }
  for (const Policy policy : policies) {
    if (query_binary_version(policy) != 86) {
      throw std::runtime_error(
          "whole-precision rtx3090 profile requires sm_86 loaded device code for " +
          std::string(policy_spec(policy).name));
    }
  }
}

std::uint64_t checked_multiply(std::uint64_t left, std::uint64_t right,
                               const char* label) {
  if (left != 0 && right > std::numeric_limits<std::uint64_t>::max() / left) {
    throw std::overflow_error(std::string("overflow while computing ") + label);
  }
  return left * right;
}

DeviceState create_state(const Options& options, const std::vector<Policy>& policies) {
  DeviceState state;
  state.gpu_id = options.gpu_id;
  state.grid_blocks = options.grid_blocks;
  state.rows = checked_multiply(state.grid_blocks, 2, "allocated rows");
  state.element_count = static_cast<std::size_t>(checked_multiply(
      state.rows, static_cast<std::uint64_t>(kSoftmaxCols), "allocated elements"));
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  CUDA_CHECK(cudaGetDeviceProperties(&state.properties, state.gpu_id));
  char pci_bus_id[32] = {};
  CUDA_CHECK(cudaDeviceGetPCIBusId(pci_bus_id, sizeof(pci_bus_id), state.gpu_id));
  state.pci_bus_id = pci_bus_id;
  require_profile(options, state, policies);
  CUDA_CHECK(cudaStreamCreateWithFlags(&state.stream, cudaStreamNonBlocking));
  CUDA_CHECK(cudaMalloc(&state.input_f16, state.element_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(&state.input_f32, state.element_count * sizeof(float)));
  CUDA_CHECK(cudaMalloc(&state.output_f16, state.element_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(&state.output_f32, state.element_count * sizeof(float)));
  CUDA_CHECK(cudaMalloc(&state.token_by_block,
                        state.grid_blocks * sizeof(std::uint32_t)));
  CUDA_CHECK(cudaMalloc(&state.smid_by_block, state.grid_blocks * sizeof(int)));
  CUDA_CHECK(cudaMalloc(&state.sm_counts,
                        static_cast<std::size_t>(state.properties.multiProcessorCount) *
                            sizeof(int)));
  CUDA_CHECK(launch_init(state.input_f16, state.input_f32, state.element_count,
                         options.logit_scale, options.seed, state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  return state;
}

void destroy_state(DeviceState& state) {
  if (state.token_by_block) cudaFree(state.token_by_block);
  if (state.smid_by_block) cudaFree(state.smid_by_block);
  if (state.sm_counts) cudaFree(state.sm_counts);
  if (state.input_f16) cudaFree(state.input_f16);
  if (state.input_f32) cudaFree(state.input_f32);
  if (state.output_f16) cudaFree(state.output_f16);
  if (state.output_f32) cudaFree(state.output_f32);
  if (state.stream) cudaStreamDestroy(state.stream);
  state = DeviceState{};
}

LaunchConfig make_launch(const DeviceState& state, Policy policy,
                         std::uint64_t iters) {
  LaunchConfig config;
  config.policy = policy;
  config.input_f16 = state.input_f16;
  config.input_f32 = state.input_f32;
  config.output_f16 = state.output_f16;
  config.output_f32 = state.output_f32;
  config.token_by_block = state.token_by_block;
  config.smid_by_block = state.smid_by_block;
  config.sm_counts = state.sm_counts;
  config.sm_count_capacity = state.properties.multiProcessorCount;
  config.grid_blocks = state.grid_blocks;
  config.iters = iters;
  config.stream = state.stream;
  return config;
}

double time_kernel(Policy policy, const DeviceState& state, std::uint64_t iters) {
  cudaEvent_t start = nullptr;
  cudaEvent_t stop = nullptr;
  CUDA_CHECK(cudaEventCreate(&start));
  CUDA_CHECK(cudaEventCreate(&stop));
  try {
    CUDA_CHECK(cudaEventRecord(start, state.stream));
    CUDA_CHECK(launch_kernel(make_launch(state, policy, iters)));
    CUDA_CHECK(cudaEventRecord(stop, state.stream));
    CUDA_CHECK(cudaEventSynchronize(stop));
    float elapsed_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&elapsed_ms, start, stop));
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    return static_cast<double>(elapsed_ms) / 1000.0;
  } catch (...) {
    if (start) cudaEventDestroy(start);
    if (stop) cudaEventDestroy(stop);
    throw;
  }
}

std::uint64_t calibrate_iters(Policy policy, const DeviceState& state,
                              double target_seconds) {
  // A one-iteration launch is far too short to extrapolate reliably: launch
  // setup, cache state, and loop scheduling dominate it.  Grow a trial until
  // the loop itself survives for >=50 ms, then scale that observed duration.
  (void)time_kernel(policy, state, 1);
  constexpr double kMinimumTrialSeconds = 0.050;
  std::uint64_t trial_iters = 1;
  double trial_elapsed_s = 0.0;
  for (int attempt = 0; attempt < 12; ++attempt) {
    trial_elapsed_s = time_kernel(policy, state, trial_iters);
    if (trial_elapsed_s >= kMinimumTrialSeconds) break;
    const double scale = trial_elapsed_s > 1.0e-6
        ? kMinimumTrialSeconds / trial_elapsed_s
        : 64.0;
    const long double next = std::ceil(static_cast<long double>(trial_iters) *
                                       std::min(128.0, std::max(2.0, scale * 1.2)));
    if (next > 1000000000.0L) {
      throw std::runtime_error("whole-precision calibration ITER outside safe range");
    }
    trial_iters = std::max<std::uint64_t>(1, static_cast<std::uint64_t>(next));
  }
  if (!(trial_elapsed_s >= kMinimumTrialSeconds && std::isfinite(trial_elapsed_s))) {
    throw std::runtime_error(
        "whole-precision calibration did not reach the 50 ms loop-survival floor");
  }
  const long double requested = std::ceil(
      static_cast<long double>(trial_iters) * target_seconds / trial_elapsed_s * 1.05L);
  if (requested < 1.0L || requested > 1000000000.0L) {
    throw std::runtime_error("whole-precision calibration ITER outside safe range");
  }
  return static_cast<std::uint64_t>(requested);
}

IdleMeasurement measure_idle(a100fp16::NvmlEnergy& nvml, const DeviceState& state,
                             double seconds) {
  const auto before = nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
  const auto after = nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!before.energy_counter_supported || !after.energy_counter_supported ||
      after.energy_mj < before.energy_mj) {
    throw std::runtime_error("NVML total-energy counter unavailable for idle baseline");
  }
  IdleMeasurement result;
  result.elapsed_s = after.timestamp_s - before.timestamp_s;
  result.delta_j = static_cast<double>(after.energy_mj - before.energy_mj) / 1000.0;
  result.power_w = result.elapsed_s > 0.0 ? result.delta_j / result.elapsed_s : 0.0;
  if (!(result.power_w >= 0.0 && std::isfinite(result.power_w))) {
    throw std::runtime_error("invalid idle power measurement");
  }
  return result;
}

SmidCheck collect_smid(const DeviceState& state) {
  std::vector<int> smids(static_cast<std::size_t>(state.grid_blocks), -1);
  std::vector<int> counts(static_cast<std::size_t>(state.properties.multiProcessorCount), 0);
  CUDA_CHECK(cudaMemcpy(smids.data(), state.smid_by_block,
                        smids.size() * sizeof(int), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(counts.data(), state.sm_counts,
                        counts.size() * sizeof(int), cudaMemcpyDeviceToHost));
  SmidCheck result;
  result.total_blocks = static_cast<int>(smids.size());
  int summed = 0;
  for (const int count : counts) {
    if (count > 0) ++result.unique;
    result.max_blocks_on_sm = std::max(result.max_blocks_on_sm, count);
    summed += count;
  }
  bool in_range = true;
  for (const int smid : smids) {
    if (smid < 0 || smid >= state.properties.multiProcessorCount) in_range = false;
  }
  result.ok = in_range && summed == result.total_blocks && result.unique > 0;
  return result;
}

void fit_energy_trace(KernelMeasurement& measurement, int min_updates) {
  measurement.trace_status = "fail";
  if (measurement.trace.size() < 3) {
    measurement.trace_status = "fail_too_few_samples";
    return;
  }
  std::vector<a100fp16::GpuEnergyCounterSample> changed;
  changed.reserve(measurement.trace.size());
  changed.push_back(measurement.trace.front());
  for (std::size_t index = 0; index < measurement.trace.size(); ++index) {
    measurement.trace_max_query_latency_s = std::max(
        measurement.trace_max_query_latency_s, measurement.trace[index].query_latency_s);
    if (index > 0 && (!measurement.trace[index].energy_counter_supported ||
                      measurement.trace[index].energy_mj <
                          measurement.trace[index - 1].energy_mj)) {
      measurement.trace_status = "fail_nonmonotonic_or_unsupported";
      return;
    }
    if (index > 0 && measurement.trace[index].energy_mj != changed.back().energy_mj) {
      changed.push_back(measurement.trace[index]);
    }
  }
  measurement.trace_update_count = static_cast<int>(changed.size()) - 1;
  if (measurement.trace_update_count < min_updates) {
    measurement.trace_status = "fail_counter_updates_below_gate";
    return;
  }
  std::vector<double> intervals;
  for (std::size_t index = 1; index < changed.size(); ++index) {
    const double interval = changed[index].timestamp_s - changed[index - 1].timestamp_s;
    if (interval > 0.0) intervals.push_back(interval);
  }
  if (intervals.empty()) {
    measurement.trace_status = "fail_counter_interval_missing";
    return;
  }
  const double guard = 2.0 * percentile(intervals, 0.99);
  const double begin = steady_seconds(measurement.host_start) + guard;
  const double end = steady_seconds(measurement.host_end) - guard;
  std::vector<a100fp16::GpuEnergyCounterSample> fit;
  for (const auto& point : changed) {
    if (point.timestamp_s >= begin && point.timestamp_s <= end) fit.push_back(point);
  }
  measurement.trace_fit_point_count = static_cast<int>(fit.size());
  if (measurement.trace_fit_point_count < min_updates) {
    measurement.trace_status = "fail_guarded_fit_points_below_gate";
    return;
  }
  std::vector<double> slopes;
  for (std::size_t left = 0; left < fit.size(); ++left) {
    for (std::size_t right = left + 1; right < fit.size(); ++right) {
      const double dt = fit[right].timestamp_s - fit[left].timestamp_s;
      if (dt > 0.0) {
        slopes.push_back(static_cast<double>(fit[right].energy_mj - fit[left].energy_mj) /
                         dt / 1000.0);
      }
    }
  }
  if (slopes.empty()) {
    measurement.trace_status = "fail_trace_slope_missing";
    return;
  }
  measurement.trace_power_w = median(std::move(slopes));
  const double origin = fit.front().timestamp_s;
  std::vector<double> intercepts;
  for (const auto& point : fit) {
    intercepts.push_back(static_cast<double>(point.energy_mj) -
                         measurement.trace_power_w * 1000.0 *
                             (point.timestamp_s - origin));
  }
  const double intercept = median(std::move(intercepts));
  double mean = 0.0;
  for (const auto& point : fit) mean += static_cast<double>(point.energy_mj);
  mean /= static_cast<double>(fit.size());
  double residual_sum = 0.0;
  double total_sum = 0.0;
  for (const auto& point : fit) {
    const double actual = static_cast<double>(point.energy_mj);
    const double predicted = intercept + measurement.trace_power_w * 1000.0 *
        (point.timestamp_s - origin);
    residual_sum += (actual - predicted) * (actual - predicted);
    total_sum += (actual - mean) * (actual - mean);
  }
  measurement.trace_rmse_mj = std::sqrt(residual_sum / static_cast<double>(fit.size()));
  measurement.trace_r2 = total_sum > 0.0 ? 1.0 - residual_sum / total_sum : 0.0;
  if (!(measurement.trace_power_w > 0.0 && measurement.trace_power_w < 1000.0)) {
    measurement.trace_status = "fail_trace_power_out_of_range";
  } else if (measurement.trace_r2 < 0.98) {
    measurement.trace_status = "fail_trace_linearity_below_gate";
  } else {
    measurement.trace_status = "pass";
  }
}

KernelMeasurement measure_kernel(Policy policy, const DeviceState& state,
                                 a100fp16::NvmlEnergy& nvml,
                                 std::uint64_t iters, const Options& options) {
  KernelMeasurement result;
  result.before = nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!result.before.energy_counter_supported) {
    throw std::runtime_error("NVML total-energy counter unavailable before kernel");
  }
  CUDA_CHECK(cudaMemsetAsync(state.smid_by_block, 0xff,
                             state.grid_blocks * sizeof(int), state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.sm_counts, 0,
                             static_cast<std::size_t>(state.properties.multiProcessorCount) *
                                 sizeof(int), state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));

  std::atomic<bool> done{false};
  std::exception_ptr polling_error;
  std::thread poller([&]() {
    try {
      result.trace.push_back(nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id));
      while (!done.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(std::chrono::duration<double>(
            options.trace_sample_ms / 1000.0));
        result.trace.push_back(nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id));
      }
      result.trace.push_back(nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id));
    } catch (...) {
      polling_error = std::current_exception();
    }
  });

  cudaEvent_t start = nullptr;
  cudaEvent_t stop = nullptr;
  try {
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));
    result.host_start = Clock::now();
    CUDA_CHECK(cudaEventRecord(start, state.stream));
    CUDA_CHECK(launch_kernel(make_launch(state, policy, iters)));
    CUDA_CHECK(cudaEventRecord(stop, state.stream));
    CUDA_CHECK(cudaEventSynchronize(stop));
    result.host_end = Clock::now();
    float elapsed_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&elapsed_ms, start, stop));
    result.elapsed_s = static_cast<double>(elapsed_ms) / 1000.0;
    done.store(true, std::memory_order_release);
    poller.join();
    if (polling_error) std::rethrow_exception(polling_error);
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    start = nullptr;
    stop = nullptr;
  } catch (...) {
    done.store(true, std::memory_order_release);
    if (poller.joinable()) poller.join();
    if (start) cudaEventDestroy(start);
    if (stop) cudaEventDestroy(stop);
    throw;
  }
  result.after = nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!result.after.energy_counter_supported || result.after.energy_mj < result.before.energy_mj) {
    throw std::runtime_error("NVML total-energy counter unavailable after kernel");
  }
  result.endpoint_delta_j =
      static_cast<double>(result.after.energy_mj - result.before.energy_mj) / 1000.0;
  fit_energy_trace(result, options.trace_min_updates);
  result.delta_j = result.trace_status == "pass"
      ? result.trace_power_w * result.elapsed_s
      : result.endpoint_delta_j;
  result.smid = collect_smid(state);
  if (!result.smid.ok) throw std::runtime_error("SMID assignment check failed");
  return result;
}

void write_trace_csv(const std::string& path, const ResultRow& row,
                     const KernelMeasurement& measurement) {
  const std::filesystem::path output_path(path);
  if (!output_path.parent_path().empty()) {
    std::filesystem::create_directories(output_path.parent_path());
  }
  const bool header_needed = !std::filesystem::exists(output_path) ||
      std::filesystem::file_size(output_path) == 0;
  std::ofstream output(output_path, std::ios::app);
  if (!output) throw std::runtime_error("unable to open whole-precision trace CSV");
  if (header_needed) {
    output << "run_id,policy,schedule_block,sequence_index,sample_index,"
              "query_start_s,query_end_s,query_midpoint_s,query_latency_s,"
              "relative_to_kernel_start_s,energy_mJ\n";
  }
  output << std::setprecision(12);
  const double kernel_start = steady_seconds(measurement.host_start);
  for (std::size_t index = 0; index < measurement.trace.size(); ++index) {
    const auto& sample = measurement.trace[index];
    output << row.run_id << ',' << row.policy << ',' << row.schedule_block << ','
           << row.sequence_index << ',' << index << ',' << sample.query_start_s << ','
           << sample.query_end_s << ',' << sample.timestamp_s << ','
           << sample.query_latency_s << ',' << sample.timestamp_s - kernel_start
           << ',' << sample.energy_mj << '\n';
  }
}

std::vector<float> validation_stimulus() {
  std::vector<float> values(static_cast<std::size_t>(4 * kSoftmaxCols));
  for (int column = 0; column < kSoftmaxCols; ++column) {
    values[column] = __half2float(__float2half_rn(0.0f));
    values[kSoftmaxCols + column] = __half2float(__float2half_rn(
        column == 0 ? 16.0f : -16.0f));
    values[2 * kSoftmaxCols + column] = __half2float(__float2half_rn(
        0.25f + static_cast<float>(column % 7) * 0x1p-11f));
    const float random = static_cast<float>((column * 37 + 11) % 97) / 12.0f - 4.0f;
    values[3 * kSoftmaxCols + column] =
        __half2float(__float2half_rn(random));
  }
  return values;
}

std::pair<double, double> validation_thresholds(Policy policy) {
  const auto spec = policy_spec(policy);
  const bool all_fp32 = spec.io == IoImplementation::fp32 &&
      spec.exp == StageImplementation::fp32 &&
      spec.reduction == StageImplementation::fp32 &&
      spec.normalization == StageImplementation::fp32;
  const int fp16_stages =
      (spec.exp != StageImplementation::fp32 ? 1 : 0) +
      (spec.reduction != StageImplementation::fp32 ? 1 : 0) +
      (spec.normalization != StageImplementation::fp32 ? 1 : 0);
  if (all_fp32) return {1.0e-5, 1.0e-5};
  if (fp16_stages <= 1) return {5.0e-3, 1.0e-2};
  return {5.0e-2, 1.0e-1};
}

ValidationResult validate_policy(Policy policy, DeviceState& state,
                                 const Options& options) {
  if (state.grid_blocks < 2) {
    throw std::runtime_error("validation requires at least two CTA blocks");
  }
  const std::vector<float> canonical = validation_stimulus();
  std::vector<half> quantized(canonical.size());
  for (std::size_t index = 0; index < canonical.size(); ++index) {
    quantized[index] = __float2half_rn(canonical[index]);
  }
  CUDA_CHECK(cudaMemcpyAsync(state.input_f16, quantized.data(),
                             quantized.size() * sizeof(half), cudaMemcpyHostToDevice,
                             state.stream));
  CUDA_CHECK(cudaMemcpyAsync(state.input_f32, canonical.data(),
                             canonical.size() * sizeof(float), cudaMemcpyHostToDevice,
                             state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.output_f16, 0,
                             canonical.size() * sizeof(half), state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.output_f32, 0,
                             canonical.size() * sizeof(float), state.stream));
  LaunchConfig config = make_launch(state, policy, 1);
  config.grid_blocks = 2;
  CUDA_CHECK(launch_kernel(config));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));

  const auto spec = policy_spec(policy);
  std::vector<float> observed(canonical.size());
  if (spec.io == IoImplementation::fp32) {
    CUDA_CHECK(cudaMemcpy(observed.data(), state.output_f32,
                          observed.size() * sizeof(float), cudaMemcpyDeviceToHost));
  } else {
    std::vector<half> output(observed.size());
    CUDA_CHECK(cudaMemcpy(output.data(), state.output_f16,
                          output.size() * sizeof(half), cudaMemcpyDeviceToHost));
    for (std::size_t index = 0; index < output.size(); ++index) {
      observed[index] = __half2float(output[index]);
    }
  }

  ValidationResult result;
  result.id = "whole_precision_fp64_semantic_input_v1_pass";
  std::vector<double> observed_row_sums;
  observed_row_sums.reserve(4);
  for (int row = 0; row < 4; ++row) {
    const std::size_t begin = static_cast<std::size_t>(row) * kSoftmaxCols;
    const auto max_it = std::max_element(canonical.begin() + begin,
                                         canonical.begin() + begin + kSoftmaxCols);
    const long double row_max = static_cast<long double>(*max_it);
    long double denominator = 0.0L;
    for (int column = 0; column < kSoftmaxCols; ++column) {
      denominator += std::exp(static_cast<long double>(canonical[begin + column]) - row_max);
    }
    double observed_sum = 0.0;
    for (int column = 0; column < kSoftmaxCols; ++column) {
      const double reference = static_cast<double>(
          std::exp(static_cast<long double>(canonical[begin + column]) - row_max) /
          denominator);
      const double actual = observed[begin + column];
      if (!std::isfinite(actual)) ++result.nonfinite_count;
      if (reference > 0.0 && actual == 0.0f) ++result.underflow_count;
      result.max_abs_error = std::max(result.max_abs_error, std::abs(actual - reference));
      observed_sum += actual;
    }
    result.max_row_sum_error = std::max(result.max_row_sum_error,
                                        std::abs(observed_sum - 1.0));
    observed_row_sums.push_back(observed_sum);
  }
  const auto [max_error_gate, row_sum_gate] = validation_thresholds(policy);
  result.max_abs_gate = max_error_gate;
  result.max_row_sum_gate = row_sum_gate;
  if (result.nonfinite_count != 0 || result.max_abs_error > max_error_gate ||
      result.max_row_sum_error > row_sum_gate) {
    std::ostringstream error;
    error << "whole-precision numerical validation failed policy="
          << policy_spec(policy).name << " max_abs_error=" << result.max_abs_error
          << " row_sum_error=" << result.max_row_sum_error
          << " nonfinite=" << result.nonfinite_count
          << " gates=" << max_error_gate << "," << row_sum_gate
          << " observed_row_sums=";
    for (std::size_t index = 0; index < observed_row_sums.size(); ++index) {
      if (index != 0) error << ',';
      error << observed_row_sums[index];
    }
    throw std::runtime_error(error.str());
  }
  result.passed = true;
  CUDA_CHECK(launch_init(state.input_f16, state.input_f32, state.element_count,
                         options.logit_scale, options.seed, state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  return result;
}

double preheat_policy(Policy policy, const DeviceState& state,
                      const Options& options) {
  // One-second chunks keep the requested 20 s preheat close to its contract
  // without the 5 s quantization overshoot of the early implementation.
  const std::uint64_t one_second_iters = calibrate_iters(policy, state, 1.0);
  double elapsed = 0.0;
  while (elapsed < options.preheat_seconds - 0.15) {
    const double remaining = options.preheat_seconds - elapsed;
    const std::uint64_t chunk_iters = remaining < 0.9
        ? std::max<std::uint64_t>(1, static_cast<std::uint64_t>(std::llround(
              static_cast<long double>(one_second_iters) * remaining)))
        : one_second_iters;
    elapsed += time_kernel(policy, state, chunk_iters);
    if (elapsed > 25.0) {
      throw std::runtime_error("whole-precision preheat exceeded 25-second bound");
    }
  }
  if (elapsed < 16.0 || elapsed > 25.0) {
    throw std::runtime_error("whole-precision preheat outside 16-25 second gate");
  }
  return elapsed;
}

ResultRow make_row(const Options& options, const DeviceState& state,
                   Policy policy, const std::string& schedule_id,
                   int schedule_block, int sequence_index,
                   std::uint64_t iters, const IdleMeasurement& idle,
                   const KernelMeasurement& measurement,
                   const ValidationResult& validation,
                   double preheat_actual_s) {
  const auto spec = policy_spec(policy);
  ResultRow row;
  row.design_id = options.design_id;
  row.stage_group = options.stage_group;
  row.session_order = options.session_order;
  row.run_id = "whole_precision_" + std::to_string(epoch_milliseconds()) + "_" +
      spec.name + "_b" + std::to_string(schedule_block) + "_p" +
      std::to_string(sequence_index);
  row.session_id = options.session_id;
  row.schedule_id = schedule_id;
  row.schedule_block = schedule_block;
  row.sequence_index = sequence_index;
  row.policy = spec.name;
  row.role = "whole_softmax";
  row.input_dtype = to_string(spec.io);
  row.output_dtype = to_string(spec.io);
  row.exp_stage = to_string(spec.exp);
  row.reduction_stage = to_string(spec.reduction);
  row.normalization_stage = to_string(spec.normalization);
  row.policy_description = spec.description;
  row.gpu_id = state.gpu_id;
  row.gpu_name = state.properties.name;
  row.compute_capability = std::to_string(state.properties.major) + "." +
      std::to_string(state.properties.minor);
  row.cuda_pci_bus_id = state.pci_bus_id;
  row.cuda_binary_arch = query_binary_version(policy);
  row.runtime_sm_count = state.properties.multiProcessorCount;
  row.occupancy_max_blocks_per_sm = query_occupancy_max_blocks_per_sm(policy);
  row.smid_unique = measurement.smid.unique;
  row.smid_total_blocks = measurement.smid.total_blocks;
  row.smid_max_blocks_on_sm = measurement.smid.max_blocks_on_sm;
  row.smid_histogram_ok = measurement.smid.ok;
  row.grid_blocks = state.grid_blocks;
  row.rows_per_block = kRowsPerBlock;
  row.softmax_cols = kSoftmaxCols;
  row.logit_scale = options.logit_scale;
  row.seed = options.seed;
  row.iters = iters;
  row.logical_input_elements = checked_multiply(
      checked_multiply(state.grid_blocks, kRowsPerBlock, "logical rows"),
      checked_multiply(iters, kSoftmaxCols, "logical elements per row"),
      "logical input elements");
  row.logical_output_elements = row.logical_input_elements;
  const std::uint64_t storage_bytes = spec.io == IoImplementation::fp32 ? 4u : 2u;
  row.physical_input_bytes = row.logical_input_elements * storage_bytes;
  row.physical_output_bytes = row.logical_output_elements * storage_bytes;
  row.elapsed_s = measurement.elapsed_s;
  row.ns_per_output_element = row.logical_output_elements > 0
      ? measurement.elapsed_s * 1.0e9 / row.logical_output_elements
      : std::numeric_limits<double>::quiet_NaN();
  row.gelement_per_s = measurement.elapsed_s > 0.0
      ? static_cast<double>(row.logical_output_elements) / measurement.elapsed_s / 1.0e9
      : std::numeric_limits<double>::quiet_NaN();
  row.idle_elapsed_s = idle.elapsed_s;
  row.idle_delta_E_J = idle.delta_j;
  row.idle_power_W = idle.power_w;
  row.preheat_requested_s = options.preheat_seconds;
  row.preheat_actual_s = preheat_actual_s;
  row.preheat_policy = policy_spec(Policy::fp16_io_fp32_all).name;
  row.E_before_mJ = measurement.before.energy_mj;
  row.E_after_mJ = measurement.after.energy_mj;
  row.endpoint_delta_E_J = measurement.endpoint_delta_j;
  row.delta_E_J = measurement.delta_j;
  row.net_E_J = measurement.delta_j - idle.power_w * measurement.elapsed_s;
  row.gross_pJ_per_output_element = row.logical_output_elements > 0
      ? measurement.delta_j * 1.0e12 / row.logical_output_elements
      : std::numeric_limits<double>::quiet_NaN();
  row.net_pJ_per_output_element = row.logical_output_elements > 0
      ? row.net_E_J * 1.0e12 / row.logical_output_elements
      : std::numeric_limits<double>::quiet_NaN();
  row.energy_trace_sample_count = static_cast<int>(measurement.trace.size());
  row.energy_trace_update_count = measurement.trace_update_count;
  row.energy_trace_fit_point_count = measurement.trace_fit_point_count;
  row.energy_trace_power_W = measurement.trace_power_w;
  row.energy_trace_r2 = measurement.trace_r2;
  row.energy_trace_rmse_mJ = measurement.trace_rmse_mj;
  row.energy_trace_max_query_latency_s = measurement.trace_max_query_latency_s;
  row.energy_trace_status = measurement.trace_status;
  row.energy_source = measurement.trace_status == "pass"
      ? "nvml_total_energy_trace_theil_sen"
      : "nvml_total_energy_endpoint_fallback_unqualified";
  row.measurement_scope = "complete_softmax_forward";
  row.clock_sm_before_mhz = measurement.before.sm_clock_mhz;
  row.clock_sm_after_mhz = measurement.after.sm_clock_mhz;
  row.temp_before_C = measurement.before.temp_c;
  row.temp_after_C = measurement.after.temp_c;
  row.validation_id = validation.id;
  row.validation_max_abs_error = validation.max_abs_error;
  row.validation_max_row_sum_error = validation.max_row_sum_error;
  row.validation_max_abs_gate = validation.max_abs_gate;
  row.validation_max_row_sum_gate = validation.max_row_sum_gate;
  row.validation_pass = validation.passed;
  row.validation_nonfinite_count = validation.nonfinite_count;
  row.validation_underflow_count = validation.underflow_count;
  row.binary_sha256 = options.binary_sha256;
  std::ostringstream notes;
  notes << "harness_revision=whole_softmax_precision_v2;"
        << "canonical_input=fp16_quantized_promoted_to_fp32_v1;"
        << "preheat_policy=fp16_io_fp32_all;"
        << "preheat_actual_s=" << preheat_actual_s << ";"
        << "packed_reduction_semantics=half2_across_two_rows_then_vector_tree;"
        << "metric=net_pJ_per_logical_output_element;"
        << "sfu_attribution=not_claimed;"
        << "temperature_not_hard_fail=" << measurement.before.temp_c << "->"
        << measurement.after.temp_c << ";";
  row.notes = notes.str();
  return row;
}

void print_dry_run(const DeviceState& state, const Options& options,
                   const std::vector<Policy>& policies) {
  std::cout << "gpu_name=" << state.properties.name << "\n"
            << "compute_capability=" << state.properties.major << "."
            << state.properties.minor << "\n"
            << "runtime_sm_count=" << state.properties.multiProcessorCount << "\n"
            << "cuda_pci_bus_id=" << state.pci_bus_id << "\n"
            << "whole_precision_softmax_cols=" << kSoftmaxCols << "\n"
            << "grid_blocks=" << state.grid_blocks << "\n"
            << "rows_per_block=" << kRowsPerBlock << "\n"
            << "logical_input_contract=fp16_quantized_promoted_to_fp32\n";
  for (const Policy policy : policies) {
    const auto spec = policy_spec(policy);
    std::cout << "policy=" << spec.name << " io=" << to_string(spec.io)
              << " exp=" << to_string(spec.exp)
              << " reduction=" << to_string(spec.reduction)
              << " normalization=" << to_string(spec.normalization)
              << " binary_arch=" << query_binary_version(policy)
              << " occupancy_max_blocks_per_sm="
              << query_occupancy_max_blocks_per_sm(policy) << "\n";
  }
  (void)options;
}

int run(const Options& options) {
  const std::vector<Policy> policies = unique_policies(options);
  DeviceState state = create_state(options, policies);
  try {
    print_dry_run(state, options, policies);
    std::map<Policy, ValidationResult> validation;
    for (const Policy policy : policies) {
      validation.emplace(policy, validate_policy(policy, state, options));
      std::cout << "validation_policy=" << policy_spec(policy).name
                << " validation_id=" << validation.at(policy).id
                << " max_abs_error=" << validation.at(policy).max_abs_error
                << " max_row_sum_error=" << validation.at(policy).max_row_sum_error
                << " underflow_count=" << validation.at(policy).underflow_count << "\n";
    }
    if (options.dry_run || options.validate_only) {
      destroy_state(state);
      return 0;
    }
    a100fp16::NvmlEnergy nvml;
    // A fixed baseline establishes the thermal state once per session.  It is
    // deliberately not repeated per policy, which would inject a policy-order
    // dependent thermal workload before measurement.
    const double preheat_actual_s = preheat_policy(
        Policy::fp16_io_fp32_all, state, options);
    std::cout << "preheat_policy=fp16_io_fp32_all preheat_actual_s="
              << preheat_actual_s << "\n";
    std::map<Policy, std::uint64_t> iters;
    for (const Policy policy : policies) {
      iters.emplace(policy, calibrate_iters(policy, state, options.seconds));
      std::cout << "calibration_policy=" << policy_spec(policy).name
                << " iters=" << iters.at(policy) << "\n";
    }
    // One unrecorded policy block stabilizes the same persistent CUDA context
    // without turning warm-up energy into measured roles.  Repeating every
    // Latin block here would add a large, undocumented thermal workload.
    for (const Policy policy : options.schedule.front()) {
      (void)time_kernel(policy, state, iters.at(policy));
    }
    CsvWriter writer(options.output);
    for (std::size_t block_index = 0; block_index < options.schedule.size(); ++block_index) {
      const auto& block = options.schedule[block_index];
      std::ostringstream schedule_id;
      for (std::size_t index = 0; index < block.size(); ++index) {
        if (index != 0) schedule_id << ',';
        schedule_id << policy_spec(block[index]).name;
      }
      for (std::size_t sequence_index = 0; sequence_index < block.size(); ++sequence_index) {
        const Policy policy = block[sequence_index];
        const IdleMeasurement idle = measure_idle(nvml, state, options.idle_seconds);
        const KernelMeasurement measurement = measure_kernel(
            policy, state, nvml, iters.at(policy), options);
        const ResultRow row = make_row(
            options, state, policy, schedule_id.str(), static_cast<int>(block_index),
            static_cast<int>(sequence_index), iters.at(policy), idle, measurement,
            validation.at(policy), preheat_actual_s);
        writer.write(row);
        write_trace_csv(options.trace_output, row, measurement);
        std::cout << "run_id=" << row.run_id << " policy=" << row.policy
                  << " elapsed_s=" << row.elapsed_s
                  << " net_pJ_per_output_element=" << row.net_pJ_per_output_element
                  << " trace_status=" << row.energy_trace_status
                  << " smid_ok=" << (row.smid_histogram_ok ? 1 : 0) << "\n";
      }
    }
    destroy_state(state);
    return 0;
  } catch (...) {
    destroy_state(state);
    throw;
  }
}

}  // namespace

int run_program(int argc, char** argv) {
  return run(parse_options(argc, argv));
}

}  // namespace fp16softmax::whole_precision

int main(int argc, char** argv) {
  try {
    return fp16softmax::whole_precision::run_program(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << "\n";
    return 1;
  }
}
