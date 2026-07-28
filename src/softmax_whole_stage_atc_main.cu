#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "nvml_energy.hpp"
#include "softmax_whole_stage_atc_config.hpp"
#include "softmax_whole_stage_atc_kernels.cuh"

namespace fp16softmax::whole_stage_atc {
namespace {

#define CUDA_CHECK(call)                                                       \
  do {                                                                         \
    const cudaError_t status__ = (call);                                       \
    if (status__ != cudaSuccess) {                                             \
      std::ostringstream error__;                                              \
      error__ << #call << " failed: " << cudaGetErrorString(status__);        \
      throw std::runtime_error(error__.str());                                 \
    }                                                                          \
  } while (0)

using SteadyClock = std::chrono::steady_clock;
using SystemClock = std::chrono::system_clock;

constexpr const char* kBinaryContractSchema =
    "softmax_whole_stage_atc_binary_contract_v2";
constexpr const char* kRawSchema = "softmax_whole_stage_atc_raw_v1";
constexpr const char* kTraceSchema = "softmax_whole_stage_atc_trace_v1";
constexpr const char* kExperimentKind =
    "softmax_whole_stage_operand_rate_atc";
constexpr const char* kProtocolRevision =
    "softmax_whole_stage_operand_rate_atc_v2";
constexpr const char* kCalibrationMode =
    "per_stage_policy_treatment_before_common_preheat";
constexpr const char* kPreheatMode = "common_fp32_whole_softmax_v1";

struct Options {
  int gpu_id = 0;
  std::string target_profile = "rtx3090";
  Stage stage = Stage::exp;
  std::vector<Policy> policy_schedule = {
      Policy::fp32, Policy::fp16_scalar, Policy::fp16x2};
  std::vector<Policy> calibration_policy_schedule = {
      Policy::fp32, Policy::fp16_scalar, Policy::fp16x2};
  std::string bracket_schedule = "ctc,tct";
  std::string session_order = "ABC";
  int session_index = 1;
  std::string session_id;
  int softmax_cols = 1024;
  std::uint64_t grid_blocks = 41;
  int threads_per_block = kThreadsPerBlock;
  int rows_per_block = kRowsPerBlock;
  double seconds = 13.0;
  double preheat_seconds = 5.0;
  std::string preheat_mode = kPreheatMode;
  double idle_seconds = 1.0;
  double trace_sample_ms = 250.0;
  int trace_min_updates = 16;
  float logit_scale = kDefaultLogitScale;
  std::uint64_t seed = kDefaultInputSeed;
  std::string schema_version = kRawSchema;
  std::string trace_schema_version = kTraceSchema;
  std::string experiment_kind = kExperimentKind;
  std::string protocol_revision = kProtocolRevision;
  std::string output;
  std::string trace_output;
  std::string binary_sha256;
  bool describe = false;
  bool self_test = false;
  bool validate_only = false;
};

struct DeviceState {
  int gpu_id = 0;
  cudaDeviceProp properties{};
  std::string pci_bus_id;
  std::uint64_t grid_blocks = 0;
  int softmax_cols = 0;
  std::size_t element_count = 0;
  half* input_f16 = nullptr;
  float* input_f32 = nullptr;
  half* output_f16 = nullptr;
  float* output_f32 = nullptr;
  std::uint32_t* sink_by_thread = nullptr;
  int* smid_by_block = nullptr;
  cudaStream_t stream = nullptr;
};

struct IdleMeasurement {
  double elapsed_s = 0.0;
  double delta_j = 0.0;
  double power_w = 0.0;
};

struct EnergyPoint {
  a100fp16::GpuEnergyCounterSample sample;
  bool changed = false;
  bool in_fit_window = false;
};

struct KernelMeasurement {
  a100fp16::GpuEnergySample before;
  a100fp16::GpuEnergySample after;
  std::vector<EnergyPoint> trace;
  SteadyClock::time_point host_start{};
  SteadyClock::time_point host_end{};
  std::int64_t epoch_start_ms = 0;
  std::int64_t epoch_end_ms = 0;
  double elapsed_s = 0.0;
  double endpoint_delta_j = 0.0;
  double delta_j = 0.0;
  double trace_power_w = 0.0;
  double trace_r2 = 0.0;
  int trace_update_count = 0;
  int trace_fit_point_count = 0;
  std::string trace_status = "not_run";
};

struct Placement {
  int total_blocks = 0;
  int unique = 0;
  int max_blocks_on_sm = 0;
  bool ok = false;
};

struct Validation {
  std::string numerical_check_id;
  std::string output_digest;
  std::string control_sink_digest;
  std::string treatment_sink_digest;
  bool output_bit_identical = false;
  bool sink_live = false;
  bool sink_invariant = false;
};

struct Calibration {
  std::uint64_t iters = 0;
  double elapsed_s = 0.0;
};

struct RoleSpec {
  int bracket_index = 0;
  const char* orientation = "";
  int role_index = 0;
  const char* role_position = "";
  const char* variant = "";
  int extra_stage_pass = 0;
};

constexpr RoleSpec kRoles[] = {
    {0, "forward", 0, "control_before", "control", 0},
    {0, "forward", 1, "treatment_middle", "treatment", 1},
    {0, "forward", 2, "control_after", "control", 0},
    {1, "reverse", 0, "treatment_before", "treatment", 1},
    {1, "reverse", 1, "control_middle", "control", 0},
    {1, "reverse", 2, "treatment_after", "treatment", 1},
};

double steady_seconds(SteadyClock::time_point point) {
  return std::chrono::duration<double>(point.time_since_epoch()).count();
}

std::int64_t epoch_milliseconds() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             SystemClock::now().time_since_epoch())
      .count();
}

template <typename T>
T percentile(std::vector<T> values, double q) {
  if (values.empty()) return T{};
  std::sort(values.begin(), values.end());
  const double position = q * static_cast<double>(values.size() - 1);
  const std::size_t lower = static_cast<std::size_t>(std::floor(position));
  const std::size_t upper = static_cast<std::size_t>(std::ceil(position));
  if (lower == upper) return values[lower];
  return static_cast<T>(
      static_cast<double>(values[lower]) +
      (static_cast<double>(values[upper]) -
       static_cast<double>(values[lower])) *
          (position - static_cast<double>(lower)));
}

double median(std::vector<double> values) {
  if (values.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::sort(values.begin(), values.end());
  const std::size_t middle = values.size() / 2;
  return values.size() % 2 == 0
             ? 0.5 * (values[middle - 1] + values[middle])
             : values[middle];
}

std::vector<std::string> split(const std::string& value, char delimiter) {
  std::vector<std::string> result;
  std::stringstream stream(value);
  std::string item;
  while (std::getline(stream, item, delimiter)) {
    if (!item.empty()) result.push_back(item);
  }
  return result;
}

std::vector<Policy> parse_policy_list(const std::string& value) {
  std::vector<Policy> result;
  for (const auto& item : split(value, ',')) {
    result.push_back(policy_from_string(item));
  }
  if (result.empty()) throw std::invalid_argument("policy list is empty");
  return result;
}

bool canonical_policy_set(const std::vector<Policy>& policies) {
  if (policies.size() != 3) return false;
  std::set<Policy> observed(policies.begin(), policies.end());
  return observed ==
         std::set<Policy>{
             Policy::fp32, Policy::fp16_scalar, Policy::fp16x2};
}

void describe_contract() {
  std::cout
      << "{"
      << "\"schema_version\":\"" << kBinaryContractSchema << "\","
      << "\"raw_schema_version\":\"" << kRawSchema << "\","
      << "\"trace_schema_version\":\"" << kTraceSchema << "\","
      << "\"persistent_policy_schedule\":true,"
      << "\"persistent_cuda_context\":true,"
      << "\"arbitrary_policy_order\":true,"
      << "\"bracket_schedule\":\"ctc,tct\","
      << "\"rows_per_block\":2,"
      << "\"per_cell_treatment_calibration\":true,"
      << "\"calibration_before_preheat\":true,"
      << "\"calibration_policy_order\":[\"fp32\",\"fp16_scalar\",\"fp16x2\"],"
      << "\"common_preheat_supported\":true,"
      << "\"same_kernel_symbol_control_treatment\":true,"
      << "\"output_equivalence_validation\":true,"
      << "\"treatment_invariant_sink\":true,"
      << "\"symmetric_opaque_stage_inputs\":true,"
      << "\"raw_records_input_generation\":true,"
      << "\"default_input_logit_scale\":" << kDefaultLogitScale << ','
      << "\"default_input_seed\":\"" << kDefaultInputSeed << "\","
      << "\"nvml_total_energy_trace\":true,"
      << "\"stages\":[\"exp\",\"reduction\",\"normalization\"],"
      << "\"policies\":[\"fp32\",\"fp16_scalar\",\"fp16x2\"],"
      << "\"kernel_contract\":\"" << kKernelContract << "\","
      << "\"exp_extra_pass\":\"reuse_primary_subtract+log2e_scale+ex2\","
      << "\"reduction_extra_pass\":\"max_tree+sum_tree\","
      << "\"normalization_extra_pass\":\"row_sum_reciprocal_replicated_per_thread+element_multiply\","
      << "\"normalization_fp16_reciprocal_lowering\":\"f32_rcp_then_round_to_f16\""
      << "}\n";
}

void usage(const char* program) {
  std::cout
      << "Usage: " << program << " [options]\n"
      << "  --describe\n"
      << "  --self-test\n"
      << "  --stage exp|reduction|normalization\n"
      << "  --policy-schedule fp32,fp16_scalar,fp16x2\n"
      << "  --calibration-policy-schedule fp32,fp16_scalar,fp16x2\n"
      << "  --bracket-schedule ctc,tct\n"
      << "  --session-order ABC|BCA|CAB --session-index 1|2|3\n"
      << "  --logit-scale 4.0 --seed 5573589319906701683\n"
      << "  --session-id ID --output RAW.csv --energy-trace-output TRACE.csv\n";
}

Options parse_options(int argc, char** argv) {
  Options options;
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
    } else if (argument == "--describe") {
      options.describe = true;
    } else if (argument == "--self-test") {
      options.self_test = true;
    } else if (argument == "--validate-only") {
      options.validate_only = true;
    } else if (argument == "--gpu-id") {
      options.gpu_id = std::stoi(value());
    } else if (argument == "--target-profile") {
      options.target_profile = value();
    } else if (argument == "--stage") {
      options.stage = stage_from_string(value());
    } else if (argument == "--policy-schedule") {
      options.policy_schedule = parse_policy_list(value());
    } else if (argument == "--calibration-policy-schedule") {
      options.calibration_policy_schedule = parse_policy_list(value());
    } else if (argument == "--bracket-schedule") {
      options.bracket_schedule = value();
    } else if (argument == "--session-order") {
      options.session_order = value();
    } else if (argument == "--session-index") {
      options.session_index = std::stoi(value());
    } else if (argument == "--session-id") {
      options.session_id = value();
    } else if (argument == "--softmax-cols") {
      options.softmax_cols = std::stoi(value());
    } else if (argument == "--grid-blocks") {
      options.grid_blocks = std::stoull(value());
    } else if (argument == "--threads-per-block") {
      options.threads_per_block = std::stoi(value());
    } else if (argument == "--rows-per-block") {
      options.rows_per_block = std::stoi(value());
    } else if (argument == "--seconds") {
      options.seconds = std::stod(value());
    } else if (argument == "--preheat-seconds") {
      options.preheat_seconds = std::stod(value());
    } else if (argument == "--preheat-mode") {
      options.preheat_mode = value();
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
    } else if (argument == "--schema-version") {
      options.schema_version = value();
    } else if (argument == "--trace-schema-version") {
      options.trace_schema_version = value();
    } else if (argument == "--experiment-kind") {
      options.experiment_kind = value();
    } else if (argument == "--protocol-revision") {
      options.protocol_revision = value();
    } else if (argument == "--output") {
      options.output = value();
    } else if (argument == "--energy-trace-output") {
      options.trace_output = value();
    } else if (argument == "--binary-sha256") {
      options.binary_sha256 = value();
    } else {
      throw std::invalid_argument("unknown option: " + argument);
    }
  }
  if (options.describe) return options;
  if (options.gpu_id < 0 || !supported_softmax_cols(options.softmax_cols) ||
      options.grid_blocks == 0 ||
      options.grid_blocks > static_cast<std::uint64_t>(0xffffffffu) ||
      options.threads_per_block != kThreadsPerBlock ||
      options.rows_per_block != kRowsPerBlock || options.seconds <= 0.0 ||
      options.preheat_seconds <= 0.0 || options.idle_seconds <= 0.0 ||
      options.trace_sample_ms < 200.0 || options.trace_min_updates < 2 ||
      !(options.logit_scale > 0.0f)) {
    throw std::invalid_argument("invalid whole-stage ATC runtime option");
  }
  if (!canonical_policy_set(options.policy_schedule)) {
    throw std::invalid_argument(
        "--policy-schedule must contain all three policies exactly once");
  }
  const std::vector<Policy> canonical = {
      Policy::fp32, Policy::fp16_scalar, Policy::fp16x2};
  if (options.calibration_policy_schedule != canonical) {
    throw std::invalid_argument(
        "--calibration-policy-schedule must be fp32,fp16_scalar,fp16x2");
  }
  if (options.bracket_schedule != "ctc,tct" ||
      options.preheat_mode != kPreheatMode) {
    throw std::invalid_argument("bracket or preheat contract mismatch");
  }
  if (options.schema_version != kRawSchema ||
      options.trace_schema_version != kTraceSchema ||
      options.experiment_kind != kExperimentKind ||
      options.protocol_revision != kProtocolRevision) {
    throw std::invalid_argument("schema/experiment/protocol contract mismatch");
  }
  // The binary self-test intentionally needs no acquisition/session metadata.
  // It still passes every geometry, schedule, and schema check above.
  if (options.self_test) return options;
  if (options.target_profile != "rtx3090" ||
      options.session_id.empty() || options.session_index < 1 ||
      options.session_index > 3 ||
      (options.session_order != "ABC" && options.session_order != "BCA" &&
       options.session_order != "CAB")) {
    throw std::invalid_argument("session/profile contract mismatch");
  }
  if (!options.self_test && !options.validate_only &&
      (options.output.empty() || options.trace_output.empty() ||
       options.binary_sha256.empty())) {
    throw std::invalid_argument(
        "acquisition requires output, trace output, and binary SHA-256");
  }
  return options;
}

std::uint64_t checked_multiply(std::uint64_t left, std::uint64_t right,
                               const char* label) {
  if (left != 0 &&
      right > std::numeric_limits<std::uint64_t>::max() / left) {
    throw std::overflow_error(std::string("overflow computing ") + label);
  }
  return left * right;
}

DeviceState create_state(const Options& options) {
  DeviceState state;
  state.gpu_id = options.gpu_id;
  state.grid_blocks = options.grid_blocks;
  state.softmax_cols = options.softmax_cols;
  state.element_count = static_cast<std::size_t>(checked_multiply(
      checked_multiply(state.grid_blocks, kRowsPerBlock, "rows"),
      static_cast<std::uint64_t>(state.softmax_cols), "elements"));
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  CUDA_CHECK(cudaGetDeviceProperties(&state.properties, state.gpu_id));
  char pci_bus_id[32] = {};
  CUDA_CHECK(cudaDeviceGetPCIBusId(
      pci_bus_id, sizeof(pci_bus_id), state.gpu_id));
  state.pci_bus_id = pci_bus_id;
  CUDA_CHECK(cudaStreamCreateWithFlags(
      &state.stream, cudaStreamNonBlocking));
  CUDA_CHECK(cudaMalloc(
      &state.input_f16, state.element_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(
      &state.input_f32, state.element_count * sizeof(float)));
  CUDA_CHECK(cudaMalloc(
      &state.output_f16, state.element_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(
      &state.output_f32, state.element_count * sizeof(float)));
  CUDA_CHECK(cudaMalloc(
      &state.sink_by_thread,
      state.grid_blocks * kThreadsPerBlock * sizeof(std::uint32_t)));
  CUDA_CHECK(cudaMalloc(
      &state.smid_by_block, state.grid_blocks * sizeof(int)));
  CUDA_CHECK(launch_init(
      state.input_f16, state.input_f32, state.element_count,
      options.logit_scale, options.seed, state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  return state;
}

void destroy_state(DeviceState& state) {
  if (state.smid_by_block) cudaFree(state.smid_by_block);
  if (state.sink_by_thread) cudaFree(state.sink_by_thread);
  if (state.output_f32) cudaFree(state.output_f32);
  if (state.output_f16) cudaFree(state.output_f16);
  if (state.input_f32) cudaFree(state.input_f32);
  if (state.input_f16) cudaFree(state.input_f16);
  if (state.stream) cudaStreamDestroy(state.stream);
  state = DeviceState{};
}

LaunchConfig make_launch(const DeviceState& state, Stage stage, Policy policy,
                         std::uint64_t iters, int extra_stage_pass) {
  LaunchConfig config;
  config.stage = stage;
  config.policy = policy;
  config.input_f16 = state.input_f16;
  config.input_f32 = state.input_f32;
  config.output_f16 = state.output_f16;
  config.output_f32 = state.output_f32;
  config.sink_by_thread = state.sink_by_thread;
  config.smid_by_block = state.smid_by_block;
  config.grid_blocks = state.grid_blocks;
  config.iters = iters;
  config.softmax_cols = state.softmax_cols;
  config.extra_stage_pass = extra_stage_pass;
  config.stream = state.stream;
  return config;
}

double time_kernel(Stage stage, Policy policy, const DeviceState& state,
                   std::uint64_t iters, int extra_stage_pass) {
  cudaEvent_t start = nullptr;
  cudaEvent_t stop = nullptr;
  CUDA_CHECK(cudaEventCreate(&start));
  CUDA_CHECK(cudaEventCreate(&stop));
  try {
    CUDA_CHECK(cudaMemsetAsync(
        state.smid_by_block, 0xff,
        state.grid_blocks * sizeof(int), state.stream));
    CUDA_CHECK(cudaMemsetAsync(
        state.sink_by_thread, 0,
        state.grid_blocks * kThreadsPerBlock * sizeof(std::uint32_t),
        state.stream));
    CUDA_CHECK(cudaEventRecord(start, state.stream));
    CUDA_CHECK(launch_kernel(
        make_launch(state, stage, policy, iters, extra_stage_pass)));
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

Calibration calibrate_treatment(Stage stage, Policy policy,
                                const DeviceState& state,
                                double target_seconds) {
  (void)time_kernel(stage, policy, state, 1, 1);
  constexpr double kMinimumTrialSeconds = 0.050;
  std::uint64_t trial_iters = 1;
  double trial_elapsed = 0.0;
  for (int attempt = 0; attempt < 12; ++attempt) {
    trial_elapsed =
        time_kernel(stage, policy, state, trial_iters, 1);
    if (trial_elapsed >= kMinimumTrialSeconds) break;
    const double factor = trial_elapsed > 1.0e-7
                              ? kMinimumTrialSeconds / trial_elapsed
                              : 64.0;
    const long double next =
        std::ceil(static_cast<long double>(trial_iters) *
                  std::min(128.0, std::max(2.0, factor * 1.2)));
    if (next > 1000000000.0L) {
      throw std::runtime_error("calibrated ITER exceeds safe range");
    }
    trial_iters = static_cast<std::uint64_t>(next);
  }
  if (!(trial_elapsed >= kMinimumTrialSeconds)) {
    throw std::runtime_error("treatment calibration failed 50ms floor");
  }
  std::uint64_t requested = static_cast<std::uint64_t>(std::ceil(
      static_cast<long double>(trial_iters) * target_seconds /
      trial_elapsed * 1.03L));
  requested = std::max<std::uint64_t>(1, requested);
  double final_elapsed =
      time_kernel(stage, policy, state, requested, 1);
  if (final_elapsed < target_seconds * 0.90 ||
      final_elapsed > target_seconds * 1.30) {
    const long double adjusted =
        std::ceil(static_cast<long double>(requested) *
                  target_seconds / final_elapsed * 1.03L);
    if (adjusted < 1.0L || adjusted > 1000000000.0L) {
      throw std::runtime_error("adjusted ITER exceeds safe range");
    }
    requested = static_cast<std::uint64_t>(adjusted);
    final_elapsed =
        time_kernel(stage, policy, state, requested, 1);
  }
  if (!(final_elapsed >= target_seconds * 0.90 &&
        final_elapsed <= target_seconds * 1.30 &&
        std::isfinite(final_elapsed))) {
    throw std::runtime_error(
        "final treatment calibration outside 0.90x-1.30x duration gate");
  }
  return {requested, final_elapsed};
}

std::string digest_bytes(const void* pointer, std::size_t bytes) {
  const auto* data = static_cast<const unsigned char*>(pointer);
  constexpr std::uint64_t seeds[] = {
      0xcbf29ce484222325ull, 0x84222325cbf29ce4ull,
      0x9e3779b97f4a7c15ull, 0xd6e8feb86659fd93ull};
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (std::uint64_t state : seeds) {
    for (std::size_t index = 0; index < bytes; ++index) {
      state ^= static_cast<std::uint64_t>(data[index]);
      state *= 0x100000001b3ull;
      state ^= state >> 29;
    }
    output << std::setw(16) << state;
  }
  return output.str();
}

std::string output_digest(Policy policy, const DeviceState& state) {
  if (policy == Policy::fp32) {
    std::vector<float> output(state.element_count);
    CUDA_CHECK(cudaMemcpy(
        output.data(), state.output_f32,
        output.size() * sizeof(float), cudaMemcpyDeviceToHost));
    return digest_bytes(output.data(), output.size() * sizeof(float));
  }
  std::vector<half> output(state.element_count);
  CUDA_CHECK(cudaMemcpy(
      output.data(), state.output_f16,
      output.size() * sizeof(half), cudaMemcpyDeviceToHost));
  return digest_bytes(output.data(), output.size() * sizeof(half));
}

std::string sink_digest(const DeviceState& state) {
  std::vector<std::uint32_t> sink(
      state.grid_blocks * kThreadsPerBlock);
  CUDA_CHECK(cudaMemcpy(
      sink.data(), state.sink_by_thread,
      sink.size() * sizeof(std::uint32_t), cudaMemcpyDeviceToHost));
  return digest_bytes(sink.data(), sink.size() * sizeof(std::uint32_t));
}

bool sink_has_live_value(const DeviceState& state) {
  std::vector<std::uint32_t> sink(
      state.grid_blocks * kThreadsPerBlock);
  CUDA_CHECK(cudaMemcpy(
      sink.data(), state.sink_by_thread,
      sink.size() * sizeof(std::uint32_t), cudaMemcpyDeviceToHost));
  return std::any_of(
      sink.begin(), sink.end(),
      [](std::uint32_t value) { return value != 0; });
}

std::vector<unsigned char> copy_output_bytes(
    Policy policy, const DeviceState& state) {
  const std::size_t element_bytes =
      policy == Policy::fp32 ? sizeof(float) : sizeof(half);
  std::vector<unsigned char> output(
      state.element_count * element_bytes);
  const void* source = policy == Policy::fp32
                           ? static_cast<const void*>(state.output_f32)
                           : static_cast<const void*>(state.output_f16);
  CUDA_CHECK(cudaMemcpy(
      output.data(), source, output.size(), cudaMemcpyDeviceToHost));
  return output;
}

void validate_row_sums(Policy policy, const DeviceState& state) {
  const std::size_t rows =
      static_cast<std::size_t>(state.grid_blocks) * kRowsPerBlock;
  const double tolerance = policy == Policy::fp32 ? 2.0e-5 : 0.15;
  if (policy == Policy::fp32) {
    std::vector<float> output(state.element_count);
    CUDA_CHECK(cudaMemcpy(
        output.data(), state.output_f32,
        output.size() * sizeof(float), cudaMemcpyDeviceToHost));
    for (std::size_t row = 0; row < std::min<std::size_t>(rows, 4); ++row) {
      double sum = 0.0;
      for (int col = 0; col < state.softmax_cols; ++col) {
        const float value = output[row * state.softmax_cols + col];
        if (!std::isfinite(value)) {
          throw std::runtime_error("nonfinite FP32 primary output");
        }
        sum += value;
      }
      if (std::abs(sum - 1.0) > tolerance) {
        throw std::runtime_error("FP32 primary row-sum validation failed");
      }
    }
  } else {
    std::vector<half> output(state.element_count);
    CUDA_CHECK(cudaMemcpy(
        output.data(), state.output_f16,
        output.size() * sizeof(half), cudaMemcpyDeviceToHost));
    for (std::size_t row = 0; row < std::min<std::size_t>(rows, 4); ++row) {
      double sum = 0.0;
      for (int col = 0; col < state.softmax_cols; ++col) {
        const float value =
            __half2float(output[row * state.softmax_cols + col]);
        if (!std::isfinite(value)) {
          throw std::runtime_error("nonfinite FP16 primary output");
        }
        sum += value;
      }
      if (std::abs(sum - 1.0) > tolerance) {
        throw std::runtime_error("FP16 primary row-sum validation failed");
      }
    }
  }
}

Validation validate_pair(Stage stage, Policy policy,
                         const DeviceState& state) {
  (void)time_kernel(stage, policy, state, 1, 0);
  const auto control_output = copy_output_bytes(policy, state);
  const std::string control_sink = sink_digest(state);
  const bool control_sink_live = sink_has_live_value(state);
  (void)time_kernel(stage, policy, state, 1, 1);
  const auto treatment_output = copy_output_bytes(policy, state);
  const std::string treatment_sink = sink_digest(state);
  const bool treatment_sink_live = sink_has_live_value(state);
  Validation result;
  result.output_bit_identical = control_output == treatment_output;
  result.sink_live = control_sink_live && treatment_sink_live;
  result.sink_invariant = control_sink == treatment_sink;
  result.output_digest =
      digest_bytes(control_output.data(), control_output.size());
  result.control_sink_digest = control_sink;
  result.treatment_sink_digest = treatment_sink;
  if (!result.output_bit_identical || !result.sink_live ||
      !result.sink_invariant) {
    throw std::runtime_error(
        "control/treatment output or treatment-invariant live-sink gate failed");
  }
  validate_row_sums(policy, state);
  result.numerical_check_id =
      std::string("whole_stage_atc_") + to_string(stage) + "_" +
      to_string(policy) + "_bitwise_rowsum_sink_invariant_v2_pass";
  return result;
}

Placement collect_placement(const DeviceState& state) {
  std::vector<int> smids(state.grid_blocks, -1);
  CUDA_CHECK(cudaMemcpy(
      smids.data(), state.smid_by_block,
      smids.size() * sizeof(int), cudaMemcpyDeviceToHost));
  std::map<int, int> counts;
  bool valid = true;
  for (const int smid : smids) {
    if (smid < 0 || smid >= state.properties.multiProcessorCount) {
      valid = false;
    } else {
      ++counts[smid];
    }
  }
  Placement result;
  result.total_blocks = static_cast<int>(smids.size());
  result.unique = static_cast<int>(counts.size());
  for (const auto& [_, count] : counts) {
    result.max_blocks_on_sm =
        std::max(result.max_blocks_on_sm, count);
  }
  const int expected_unique = std::min(
      result.total_blocks, state.properties.multiProcessorCount);
  result.ok = valid && result.unique == expected_unique &&
              (result.total_blocks > state.properties.multiProcessorCount ||
               result.max_blocks_on_sm == 1);
  return result;
}

IdleMeasurement measure_idle(a100fp16::NvmlEnergy& nvml,
                             const DeviceState& state, double seconds) {
  const auto before =
      nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
  const auto after =
      nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!before.energy_counter_supported ||
      !after.energy_counter_supported ||
      after.energy_mj < before.energy_mj) {
    throw std::runtime_error("NVML idle energy counter unavailable");
  }
  IdleMeasurement result;
  result.elapsed_s = after.timestamp_s - before.timestamp_s;
  result.delta_j =
      static_cast<double>(after.energy_mj - before.energy_mj) / 1000.0;
  result.power_w =
      result.elapsed_s > 0.0 ? result.delta_j / result.elapsed_s : 0.0;
  if (!(result.elapsed_s > 0.0 && result.power_w >= 0.0 &&
        std::isfinite(result.power_w))) {
    throw std::runtime_error("invalid idle measurement");
  }
  return result;
}

void fit_energy_trace(KernelMeasurement& measurement, int minimum_points) {
  measurement.trace_status = "fail";
  if (measurement.trace.size() < 3) {
    measurement.trace_status = "fail_too_few_samples";
    return;
  }
  std::vector<std::size_t> changed_indices;
  changed_indices.push_back(0);
  for (std::size_t index = 1; index < measurement.trace.size(); ++index) {
    if (measurement.trace[index].sample.energy_mj <
        measurement.trace[index - 1].sample.energy_mj) {
      measurement.trace_status = "fail_nonmonotonic";
      return;
    }
    measurement.trace[index].changed =
        measurement.trace[index].sample.energy_mj >
        measurement.trace[index - 1].sample.energy_mj;
    if (measurement.trace[index].changed) changed_indices.push_back(index);
  }
  measurement.trace_update_count =
      static_cast<int>(changed_indices.size()) - 1;
  if (measurement.trace_update_count < minimum_points) {
    measurement.trace_status = "fail_updates";
    return;
  }
  std::vector<double> intervals;
  for (std::size_t index = 1; index < changed_indices.size(); ++index) {
    const auto left = changed_indices[index - 1];
    const auto right = changed_indices[index];
    const double interval =
        measurement.trace[right].sample.timestamp_s -
        measurement.trace[left].sample.timestamp_s;
    if (interval > 0.0) intervals.push_back(interval);
  }
  if (intervals.empty()) {
    measurement.trace_status = "fail_intervals";
    return;
  }
  const double guard = 2.0 * percentile(intervals, 0.99);
  const double begin = steady_seconds(measurement.host_start) + guard;
  const double end = steady_seconds(measurement.host_end) - guard;
  std::vector<std::size_t> fit_indices;
  for (const std::size_t index : changed_indices) {
    const double timestamp = measurement.trace[index].sample.timestamp_s;
    if (timestamp >= begin && timestamp <= end) {
      measurement.trace[index].in_fit_window = true;
      fit_indices.push_back(index);
    }
  }
  // Mark unchanged samples in the guarded time window as well.  The trace
  // analyzer later filters them with changed_from_previous.
  for (auto& point : measurement.trace) {
    const double timestamp = point.sample.timestamp_s;
    if (timestamp >= begin && timestamp <= end) {
      point.in_fit_window = true;
    }
  }
  measurement.trace_fit_point_count =
      static_cast<int>(fit_indices.size());
  if (measurement.trace_fit_point_count < minimum_points) {
    measurement.trace_status = "fail_guarded_points";
    return;
  }
  std::vector<double> slopes;
  for (std::size_t left = 0; left < fit_indices.size(); ++left) {
    for (std::size_t right = left + 1;
         right < fit_indices.size(); ++right) {
      const auto& a = measurement.trace[fit_indices[left]].sample;
      const auto& b = measurement.trace[fit_indices[right]].sample;
      const double dt = b.timestamp_s - a.timestamp_s;
      if (dt > 0.0) {
        slopes.push_back(
            static_cast<double>(b.energy_mj - a.energy_mj) /
            dt / 1000.0);
      }
    }
  }
  measurement.trace_power_w = median(std::move(slopes));
  const double origin =
      measurement.trace[fit_indices.front()].sample.timestamp_s;
  std::vector<double> intercepts;
  for (const auto index : fit_indices) {
    const auto& point = measurement.trace[index].sample;
    intercepts.push_back(
        static_cast<double>(point.energy_mj) -
        measurement.trace_power_w * 1000.0 *
            (point.timestamp_s - origin));
  }
  const double intercept = median(std::move(intercepts));
  double mean = 0.0;
  for (const auto index : fit_indices) {
    mean += measurement.trace[index].sample.energy_mj;
  }
  mean /= static_cast<double>(fit_indices.size());
  double residual = 0.0;
  double total = 0.0;
  for (const auto index : fit_indices) {
    const auto& point = measurement.trace[index].sample;
    const double actual = static_cast<double>(point.energy_mj);
    const double predicted =
        intercept + measurement.trace_power_w * 1000.0 *
                        (point.timestamp_s - origin);
    residual += (actual - predicted) * (actual - predicted);
    total += (actual - mean) * (actual - mean);
  }
  measurement.trace_r2 =
      total > 0.0 ? 1.0 - residual / total : 0.0;
  if (!(measurement.trace_power_w > 0.0 &&
        measurement.trace_power_w < 1000.0)) {
    measurement.trace_status = "fail_power";
  } else if (measurement.trace_r2 < 0.98) {
    measurement.trace_status = "fail_r2";
  } else {
    measurement.trace_status = "pass";
  }
}

KernelMeasurement measure_kernel(
    Stage stage, Policy policy, int extra_stage_pass,
    const DeviceState& state, a100fp16::NvmlEnergy& nvml,
    std::uint64_t iters, const Options& options) {
  KernelMeasurement result;
  result.before =
      nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!result.before.energy_counter_supported) {
    throw std::runtime_error("NVML energy counter unavailable");
  }
  CUDA_CHECK(cudaMemsetAsync(
      state.smid_by_block, 0xff,
      state.grid_blocks * sizeof(int), state.stream));
  CUDA_CHECK(cudaMemsetAsync(
      state.sink_by_thread, 0,
      state.grid_blocks * kThreadsPerBlock * sizeof(std::uint32_t),
      state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));

  std::atomic<bool> done{false};
  std::exception_ptr poll_error;
  std::thread poller([&]() {
    try {
      EnergyPoint first;
      first.sample =
          nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id);
      result.trace.push_back(first);
      while (!done.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(std::chrono::duration<double>(
            options.trace_sample_ms / 1000.0));
        EnergyPoint point;
        point.sample =
            nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id);
        result.trace.push_back(point);
      }
      EnergyPoint final;
      final.sample =
          nvml.sample_energy_counter_by_pci_bus_id(state.pci_bus_id);
      result.trace.push_back(final);
    } catch (...) {
      poll_error = std::current_exception();
    }
  });

  cudaEvent_t start = nullptr;
  cudaEvent_t stop = nullptr;
  try {
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));
    result.host_start = SteadyClock::now();
    result.epoch_start_ms = epoch_milliseconds();
    CUDA_CHECK(cudaEventRecord(start, state.stream));
    CUDA_CHECK(launch_kernel(make_launch(
        state, stage, policy, iters, extra_stage_pass)));
    CUDA_CHECK(cudaEventRecord(stop, state.stream));
    CUDA_CHECK(cudaEventSynchronize(stop));
    result.host_end = SteadyClock::now();
    result.epoch_end_ms = epoch_milliseconds();
    float elapsed_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&elapsed_ms, start, stop));
    result.elapsed_s = static_cast<double>(elapsed_ms) / 1000.0;
    done.store(true, std::memory_order_release);
    poller.join();
    if (poll_error) std::rethrow_exception(poll_error);
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
  result.after =
      nvml.sample_by_pci_bus_id(state.pci_bus_id, state.gpu_id);
  if (!result.after.energy_counter_supported ||
      result.after.energy_mj < result.before.energy_mj) {
    throw std::runtime_error("NVML endpoint energy unavailable");
  }
  result.endpoint_delta_j =
      static_cast<double>(
          result.after.energy_mj - result.before.energy_mj) /
      1000.0;
  fit_energy_trace(result, options.trace_min_updates);
  if (result.trace_status != "pass") {
    throw std::runtime_error(
        "unqualified NVML trace: " + result.trace_status);
  }
  result.delta_j = result.trace_power_w * result.elapsed_s;
  return result;
}

double run_common_preheat(const DeviceState& state,
                          const Options& options) {
  const Calibration one_second =
      calibrate_treatment(
          Stage::exp, Policy::fp32, state, 1.0);
  double elapsed = 0.0;
  while (elapsed < options.preheat_seconds - 0.15) {
    const double remaining = options.preheat_seconds - elapsed;
    const std::uint64_t chunk =
        remaining < 0.9
            ? std::max<std::uint64_t>(
                  1, static_cast<std::uint64_t>(std::llround(
                         static_cast<long double>(one_second.iters) *
                         remaining)))
            : one_second.iters;
    elapsed += time_kernel(
        Stage::exp, Policy::fp32, state, chunk, 0);
    if (elapsed > options.preheat_seconds * 1.25) break;
  }
  const double tolerance =
      std::max(0.75, options.preheat_seconds * 0.25);
  if (elapsed < options.preheat_seconds - tolerance ||
      elapsed > options.preheat_seconds + tolerance) {
    throw std::runtime_error("common preheat outside duration gate");
  }
  return elapsed;
}

std::string kernel_symbol_name(Stage stage, Policy policy,
                               int softmax_cols) {
  std::ostringstream output;
  output << "whole_softmax_stage_atc_kernel_s" << softmax_cols
         << '_' << to_string(stage) << '_' << to_string(policy);
  return output.str();
}

const char* raw_header() {
  return
      "schema_version,experiment_kind,protocol_revision,run_id,session_id,"
      "session_index,session_order,session_role_index,stage,policy_position,"
      "policy,cell_id,bracket_index,orientation,role_index,role_id,"
      "role_position,role,variant,kernel_symbol,same_kernel_symbol_status,"
      "softmax_cols,grid_blocks,rows_per_block,threads_per_block,iters,"
      "input_logit_scale,input_seed,"
      "logical_output_elements,elapsed_s,energy_trace_power_W,"
      "energy_trace_status,energy_trace_fit_point_count,energy_trace_r2,"
      "endpoint_delta_E_J,delta_E_J,idle_power_W,idle_elapsed_s,"
      "idle_delta_E_J,preheat_requested_s,preheat_actual_s,gpu_name,gpu_id,"
      "target_profile,compute_capability,cuda_binary_arch,cuda_pci_bus_id,"
      "binary_sha256,numerical_check_id,"
      "control_treatment_output_bit_identical,output_digest,"
      "output_equivalence_status,sink_digest,energy_trace_sample_count,"
      "energy_trace_update_count,energy_source,energy_integration_method,"
      "input_dtype,output_dtype,block_shared_bytes,registers_per_thread,"
      "runtime_sm_count,occupancy_max_blocks_per_sm,"
      "static_single_wave_capacity_blocks,"
      "static_single_wave_capacity_gate_pass,smid_total_blocks,smid_unique,"
      "smid_max_blocks_on_sm,smid_histogram_ok,calibration_mode,"
      "calibration_reference_variant,calibration_elapsed_s,"
      "calibration_iters,calibration_before_preheat,role_target_seconds,"
      "measurement_start_epoch_ms,measurement_end_epoch_ms,E_before_mJ,"
      "E_after_mJ,clock_sm_before_mhz,clock_sm_after_mhz,"
      "clock_mem_before_mhz,clock_mem_after_mhz,temp_before_C,temp_after_C";
}

const char* trace_header() {
  return
      "schema_version,experiment_kind,protocol_revision,session_id,stage,"
      "policy,cell_id,bracket_index,role_index,role_id,role,variant,run_id,"
      "sample_index,query_start_s,query_end_s,query_midpoint_s,"
      "query_latency_s,relative_to_kernel_start_s,energy_mJ,"
      "changed_from_previous,in_fit_window,binary_sha256";
}

void write_trace_rows(
    std::ofstream& output, const Options& options,
    const std::string& cell_id, const RoleSpec& role,
    const std::string& role_id, const std::string& run_id,
    Policy policy, const KernelMeasurement& measurement) {
  const double kernel_start = steady_seconds(measurement.host_start);
  for (std::size_t index = 0; index < measurement.trace.size(); ++index) {
    const auto& point = measurement.trace[index];
    const auto& sample = point.sample;
    output << options.trace_schema_version << ','
           << options.experiment_kind << ','
           << options.protocol_revision << ','
           << options.session_id << ',' << to_string(options.stage) << ','
           << to_string(policy) << ',' << cell_id << ','
           << role.bracket_index << ',' << role.role_index << ','
           << role_id << ',' << role.variant << ',' << role.variant << ','
           << run_id << ',' << index << ',' << sample.query_start_s << ','
           << sample.query_end_s << ',' << sample.timestamp_s << ','
           << sample.query_latency_s << ','
           << sample.timestamp_s - kernel_start << ','
           << sample.energy_mj << ','
           << (point.changed ? "true" : "false") << ','
           << (point.in_fit_window ? "true" : "false") << ','
           << options.binary_sha256 << '\n';
  }
}

void write_raw_row(
    std::ofstream& output, const Options& options, int session_role_index,
    int policy_position, Policy policy, const std::string& cell_id,
    const RoleSpec& role, const std::string& role_id,
    const std::string& run_id, const DeviceState& state,
    const Calibration& calibration, const Validation& validation,
    const IdleMeasurement& idle, const KernelMeasurement& measurement,
    const Placement& placement, double preheat_actual_s,
    const std::string& measured_output_digest,
    const std::string& measured_sink_digest) {
  const int occupancy = query_occupancy_max_blocks_per_sm(
      options.stage, policy, options.softmax_cols);
  const std::uint64_t capacity =
      checked_multiply(
          static_cast<std::uint64_t>(state.properties.multiProcessorCount),
          static_cast<std::uint64_t>(occupancy), "static capacity");
  const int binary_arch = query_binary_version(
      options.stage, policy, options.softmax_cols);
  const int registers = query_registers_per_thread(
      options.stage, policy, options.softmax_cols);
  const std::size_t shared_bytes = query_static_shared_bytes(
      options.stage, policy, options.softmax_cols);
  const std::uint64_t logical = checked_multiply(
      checked_multiply(
          options.grid_blocks, kRowsPerBlock, "logical rows"),
      checked_multiply(
          calibration.iters,
          static_cast<std::uint64_t>(options.softmax_cols),
          "logical elements per row"),
      "logical output elements");
  const std::string compute_capability =
      std::to_string(state.properties.major) + "." +
      std::to_string(state.properties.minor);
  const char* dtype =
      policy == Policy::fp32 ? "fp32" : "fp16";
  output
      << options.schema_version << ',' << options.experiment_kind << ','
      << options.protocol_revision << ',' << run_id << ','
      << options.session_id << ',' << options.session_index << ','
      << options.session_order << ',' << session_role_index << ','
      << to_string(options.stage) << ',' << policy_position << ','
      << to_string(policy) << ',' << cell_id << ','
      << role.bracket_index << ',' << role.orientation << ','
      << role.role_index << ',' << role_id << ','
      << role.role_position << ',' << role.variant << ','
      << role.variant << ','
      << kernel_symbol_name(
             options.stage, policy, options.softmax_cols)
      << ",pass," << options.softmax_cols << ',' << options.grid_blocks
      << ',' << kRowsPerBlock << ',' << kThreadsPerBlock << ','
      << calibration.iters << ',' << options.logit_scale << ','
      << options.seed << ',' << logical << ','
      << measurement.elapsed_s << ',' << measurement.trace_power_w << ','
      << measurement.trace_status << ','
      << measurement.trace_fit_point_count << ','
      << measurement.trace_r2 << ',' << measurement.endpoint_delta_j << ','
      << measurement.delta_j << ',' << idle.power_w << ','
      << idle.elapsed_s << ',' << idle.delta_j << ','
      << options.preheat_seconds << ',' << preheat_actual_s << ','
      << state.properties.name << ',' << options.gpu_id << ','
      << options.target_profile << ',' << compute_capability << ','
      << binary_arch << ',' << state.pci_bus_id << ','
      << options.binary_sha256 << ','
      << validation.numerical_check_id << ','
      << (validation.output_bit_identical ? "true" : "false") << ','
      << measured_output_digest << ",pass," << measured_sink_digest << ','
      << measurement.trace.size() << ','
      << measurement.trace_update_count
      << ",nvml_total_energy,guarded_interior_theil_sen,"
      << dtype << ',' << dtype << ',' << shared_bytes << ','
      << registers << ',' << state.properties.multiProcessorCount << ','
      << occupancy << ',' << capacity << ','
      << (options.grid_blocks <= capacity ? "true" : "false") << ','
      << placement.total_blocks << ',' << placement.unique << ','
      << placement.max_blocks_on_sm << ','
      << (placement.ok ? "true" : "false") << ','
      << kCalibrationMode << ",treatment," << calibration.elapsed_s << ','
      << calibration.iters << ",true," << options.seconds << ','
      << measurement.epoch_start_ms << ',' << measurement.epoch_end_ms
      << ',' << measurement.before.energy_mj << ','
      << measurement.after.energy_mj << ','
      << measurement.before.sm_clock_mhz << ','
      << measurement.after.sm_clock_mhz << ','
      << measurement.before.mem_clock_mhz << ','
      << measurement.after.mem_clock_mhz << ','
      << measurement.before.temp_c << ',' << measurement.after.temp_c
      << '\n';
}

void require_profile(const Options& options, const DeviceState& state) {
  if (options.target_profile == "rtx3090") {
    if (state.properties.major != 8 || state.properties.minor != 6 ||
        state.properties.multiProcessorCount != 82) {
      throw std::runtime_error(
          "rtx3090 stage-ATC profile requires CC 8.6 and 82 SMs");
    }
  }
  for (const Policy policy : options.policy_schedule) {
    const int occupancy = query_occupancy_max_blocks_per_sm(
        options.stage, policy, options.softmax_cols);
    if (occupancy <= 0) {
      throw std::runtime_error("non-positive kernel occupancy");
    }
    const std::uint64_t capacity =
        static_cast<std::uint64_t>(
            state.properties.multiProcessorCount) *
        static_cast<std::uint64_t>(occupancy);
    if (options.grid_blocks > capacity) {
      throw std::runtime_error("grid exceeds static single-wave capacity");
    }
    if (query_binary_version(
            options.stage, policy, options.softmax_cols) != 86) {
      throw std::runtime_error("stage-ATC binary is not native sm_86");
    }
  }
}

void run_self_test(const Options& parsed) {
  if (std::string(raw_header()).find(
          "iters,input_logit_scale,input_seed,logical_output_elements") ==
      std::string::npos) {
    throw std::runtime_error(
        "self-test raw input-generation provenance fields are missing");
  }
  Options options = parsed;
  options.softmax_cols = 1024;
  options.grid_blocks = 4;
  options.target_profile = "rtx3090";
  DeviceState state = create_state(options);
  try {
    int cells = 0;
    for (const Stage stage :
         {Stage::exp, Stage::reduction, Stage::normalization}) {
      for (const Policy policy :
           {Policy::fp32, Policy::fp16_scalar, Policy::fp16x2}) {
        const Validation validation =
            validate_pair(stage, policy, state);
        if (!validation.output_bit_identical ||
            !validation.sink_live ||
            !validation.sink_invariant ||
            validation.output_digest.empty()) {
          throw std::runtime_error("self-test cell failed");
        }
        const auto control_address = query_kernel_symbol_address(
            stage, policy, options.softmax_cols);
        const auto treatment_address = query_kernel_symbol_address(
            stage, policy, options.softmax_cols);
        if (control_address == 0 ||
            control_address != treatment_address) {
          throw std::runtime_error(
              "self-test same-symbol address gate failed");
        }
        ++cells;
      }
    }
    destroy_state(state);
    std::cout
        << "self_test=pass stage_policy_cells=" << cells
        << " primary_output_bit_identical=1 live_sink_written=1"
        << " treatment_invariant_sink=1"
        << " same_kernel_symbol=1\n";
  } catch (...) {
    destroy_state(state);
    throw;
  }
}

int run(const Options& options) {
  if (options.describe) {
    describe_contract();
    return 0;
  }
  if (options.self_test) {
    run_self_test(options);
    return 0;
  }
  DeviceState state = create_state(options);
  try {
    require_profile(options, state);
    std::map<Policy, Validation> validations;
    for (const Policy policy :
         options.calibration_policy_schedule) {
      validations.emplace(
          policy, validate_pair(options.stage, policy, state));
    }
    if (options.validate_only) {
      destroy_state(state);
      std::cout
          << "validation=pass stage=" << to_string(options.stage)
          << " cells=3 output_bit_identical=1 live_sink_written=1"
          << " treatment_invariant_sink=1\n";
      return 0;
    }

    // Every cell is calibrated from its treatment variant before the one
    // common conditioner.  That cell's ITER is then frozen for all six roles.
    std::map<Policy, Calibration> calibrations;
    for (const Policy policy :
         options.calibration_policy_schedule) {
      calibrations.emplace(
          policy, calibrate_treatment(
                      options.stage, policy, state, options.seconds));
      std::cout
          << "calibration stage=" << to_string(options.stage)
          << " policy=" << to_string(policy)
          << " iters=" << calibrations.at(policy).iters
          << " elapsed_s=" << calibrations.at(policy).elapsed_s
          << '\n';
    }
    const double preheat_actual_s =
        run_common_preheat(state, options);
    std::cout << "preheat_mode=" << options.preheat_mode
              << " preheat_actual_s=" << preheat_actual_s << '\n';

    a100fp16::NvmlEnergy nvml;
    std::ofstream raw(options.output, std::ios::trunc);
    std::ofstream trace(options.trace_output, std::ios::trunc);
    if (!raw || !trace) {
      throw std::runtime_error("unable to create raw/trace CSV");
    }
    raw << raw_header() << '\n';
    trace << trace_header() << '\n';
    raw << std::setprecision(17);
    trace << std::setprecision(17);
    int session_role_index = 0;
    std::map<Policy, std::string> stable_sink_digests;
    for (std::size_t policy_position = 0;
         policy_position < options.policy_schedule.size();
         ++policy_position) {
      const Policy policy =
          options.policy_schedule[policy_position];
      const auto& calibration = calibrations.at(policy);
      const auto& validation = validations.at(policy);
      const std::string cell_id =
          options.session_id + "_" + to_string(options.stage) + "_" +
          to_string(policy);
      for (const RoleSpec& role : kRoles) {
        const std::string role_id =
            cell_id + "_b" + std::to_string(role.bracket_index) +
            "_r" + std::to_string(role.role_index) + "_" +
            role.variant;
        const std::string run_id =
            role_id + "_" + std::to_string(epoch_milliseconds());
        const IdleMeasurement idle =
            measure_idle(nvml, state, options.idle_seconds);
        const KernelMeasurement measurement =
            measure_kernel(
                options.stage, policy, role.extra_stage_pass, state,
                nvml, calibration.iters, options);
        const Placement placement = collect_placement(state);
        if (!placement.ok) {
          throw std::runtime_error("runtime SMID placement gate failed");
        }
        const std::string observed_output_digest =
            output_digest(policy, state);
        if (observed_output_digest != validation.output_digest) {
          throw std::runtime_error(
              "measured role changed primary Softmax output");
        }
        if (!sink_has_live_value(state)) {
          throw std::runtime_error(
              "measured role did not write a live sink value");
        }
        const std::string observed_sink_digest =
            sink_digest(state);
        const auto inserted = stable_sink_digests.emplace(
            policy, observed_sink_digest);
        if (!inserted.second &&
            inserted.first->second != observed_sink_digest) {
          throw std::runtime_error(
              "sink digest is not treatment-invariant");
        }
        write_raw_row(
            raw, options, session_role_index,
            static_cast<int>(policy_position), policy, cell_id, role,
            role_id, run_id, state, calibration, validation, idle,
            measurement, placement, preheat_actual_s,
            observed_output_digest, observed_sink_digest);
        write_trace_rows(
            trace, options, cell_id, role, role_id, run_id, policy,
            measurement);
        raw.flush();
        trace.flush();
        std::cout << "role=" << session_role_index
                  << " stage=" << to_string(options.stage)
                  << " policy=" << to_string(policy)
                  << " variant=" << role.variant
                  << " elapsed_s=" << measurement.elapsed_s
                  << " power_W=" << measurement.trace_power_w << '\n';
        ++session_role_index;
      }
    }
    if (session_role_index != 18) {
      throw std::runtime_error("persistent session did not emit 18 roles");
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

}  // namespace fp16softmax::whole_stage_atc

int main(int argc, char** argv) {
  try {
    return fp16softmax::whole_stage_atc::run_program(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
  }
}
