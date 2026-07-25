#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cstring>
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
#include "softmax_config.hpp"
#include "softmax_kernels.cuh"
#include "softmax_result_writer.hpp"

namespace fp16softmax {
namespace {

#define CUDA_CHECK(call)                                                        \
  do {                                                                          \
    const cudaError_t status__ = (call);                                        \
    if (status__ != cudaSuccess) {                                              \
      std::ostringstream oss__;                                                 \
      oss__ << #call << " failed: " << cudaGetErrorString(status__);           \
      throw std::runtime_error(oss__.str());                                    \
    }                                                                           \
  } while (0)

using Clock = std::chrono::steady_clock;

struct Options {
  int gpu_id = 0;
  SoftmaxMode mode = SoftmaxMode::full;
  ExpImplementation exp_implementation = ExpImplementation::fp32_expf;
  int softmax_cols = 512;
  int blocks_per_sm = 2;
  // This option never conferred CUDA SM affinity; retain it only so a
  // nonzero request can fail clearly instead of implying a partition.
  int active_sm = 0;
  std::uint64_t grid_blocks = 0;
  double seconds = 5.0;
  double idle_measure_seconds = 1.0;
  std::uint64_t iters = 0;
  int repeats = 1;
  float logit_scale = 4.0f;
  CacheCondition cache_condition = CacheCondition::cache_reuse_candidate;
  CachePolicy cache_policy = CachePolicy::default_cache;
  std::uint64_t row_tiles_per_block = 0;
  std::uint64_t tile_stride = 0;
  bool verify_smid = true;
  bool calibrate_only = false;
  bool validate_only = false;
  bool dry_run = false;
  std::uint64_t seed = 0x4d595df4d0f33173ull;
  std::string output = "results/raw/fp16_softmax_energy_raw.csv";
  std::string target_profile = "rtx3090";
  std::string pair_id;
  std::string role;
  int repeat_index = -1;
  int sequence_index = -1;
  std::string bracket_control;
  int bracket_pairs = 0;
  int bracket_warmup_pairs = 0;
  std::string pair_prefix;
  std::string bracket_idle_policy = "pair_once";
  std::string bracket_order = "ctc";
  bool extra_exp_probe = false;
  bool energy_trace = true;
  double energy_trace_sample_ms = 500.0;
  int energy_trace_min_updates = 8;
  std::string energy_trace_output;
  std::string numerical_check_id = "not_run";
  std::string binary_sha256;
  std::string measurement_purpose = "energy_atc";
};

struct DeviceState {
  cudaDeviceProp prop{};
  int gpu_id = -1;
  std::string cuda_pci_bus_id;
  int cuda_binary_arch = 0;
  int active_sm = 0;
  int sm_count_capacity = 0;
  int occupancy_max_blocks_per_sm = 0;
  std::uint64_t static_single_wave_capacity_blocks = 0;
  std::uint64_t grid_blocks = 0;
  bool explicit_grid_blocks = false;
  std::uint64_t row_tiles_per_block = 1;
  std::uint64_t tile_stride = 1;
  std::uint64_t n_rows = 0;
  std::size_t input_count = 0;
  std::size_t working_set_bytes = 0;
  half* input = nullptr;
  half* output = nullptr;
  std::uint32_t* token_by_block = nullptr;
  int* smid_by_block = nullptr;
  int* sm_counts = nullptr;
  cudaStream_t stream = nullptr;
};

struct ExpPathMetadata {
  std::string compute_dtype;
  std::string exp_input_dtype;
  std::string special_function_path;
  std::string ptx_instruction;
  int results_per_ptx_instruction = 1;
  int sass_mufu_per_ptx_instruction_model = 1;
  std::string sass_lowering_model_status;
  int documented_results_per_sm_cycle = 0;
};

ExpPathMetadata exp_path_metadata(ExpImplementation implementation,
                                  int cuda_major) {
  switch (implementation) {
    case ExpImplementation::fp32_expf:
      return {"fp32", "fp32", "fp32_fast_expf_to_mufu_ex2",
              "ex2.approx.f32", 1, 1,
              "cuda_13_2_ampere_model_requires_final_binary_gate",
              cuda_major == 8 ? 16 : 0};
    case ExpImplementation::ptx_f16:
      return {"fp32_reduce_fp16_ex2", "fp16",
              "direct_inline_ptx_ex2_approx_f16",
              "ex2.approx.f16", 1, 1,
              "cuda_13_2_sm80_sm86_observed_requires_final_binary_gate", 0};
    case ExpImplementation::ptx_f16x2:
      return {"fp32_reduce_fp16x2_ex2", "fp16x2_packed_b32",
              "direct_inline_ptx_ex2_approx_f16x2",
              "ex2.approx.f16x2", 2, 2,
              "cuda_13_2_sm80_sm86_scalarized_requires_final_binary_gate", 0};
  }
  throw std::invalid_argument("unrecognized exponential implementation");
}

struct IdleMeasurement {
  double elapsed_s = 0.0;
  double delta_j = 0.0;
  double power_w = 0.0;
};

struct SmidCheck {
  bool ok = false;
  bool all_blocks_observed = false;
  int unique_sms = 0;
  int total_blocks = 0;
  int max_blocks_on_sm = 0;
  std::string smid_set;
  std::string histogram;
};

struct KernelMeasurement {
  a100fp16::GpuEnergySample before;
  a100fp16::GpuEnergySample after;
  Clock::time_point kernel_start;
  Clock::time_point kernel_end;
  double elapsed_s = 0.0;
  double delta_j = 0.0;
  double endpoint_delta_j = 0.0;
  std::vector<a100fp16::GpuEnergyCounterSample> energy_trace;
  int energy_trace_update_count = 0;
  int energy_trace_fit_point_count = 0;
  double energy_trace_update_interval_p99_s = 0.0;
  double energy_trace_guard_s = 0.0;
  double energy_trace_fit_span_s = 0.0;
  double energy_trace_power_w = 0.0;
  double energy_trace_r2 = 0.0;
  double energy_trace_rmse_mj = 0.0;
  double energy_trace_max_query_latency_s = 0.0;
  double energy_trace_fit_start_s = 0.0;
  double energy_trace_fit_end_s = 0.0;
  std::string energy_trace_status = "not_run";
  std::uint64_t start_epoch_ms = 0;
  std::uint64_t end_epoch_ms = 0;
  SmidCheck smid;
};

struct IterCalibration {
  std::uint64_t resolved_iters = 0;
  std::uint64_t trial_iters = 0;
  double trial_elapsed_s = 0.0;
};

struct BracketMetadata {
  std::string execution_model = "standalone_cuda_context_v1";
  std::string context_id;
  std::string idle_baseline_scope = "per_role";
  double preceding_role_gap_s = -1.0;
  double preceding_counter_gap_delta_j = -1.0;
};

struct PendingEnergyTrace {
  SoftmaxResultRow row;
  KernelMeasurement measurement;
};

double elapsed_seconds(Clock::time_point start, Clock::time_point end) {
  return std::chrono::duration<double>(end - start).count();
}

double steady_seconds(Clock::time_point point) {
  return std::chrono::duration<double>(point.time_since_epoch()).count();
}

double percentile(std::vector<double> values, double quantile) {
  if (values.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::sort(values.begin(), values.end());
  const double position = quantile * static_cast<double>(values.size() - 1);
  const std::size_t lower = static_cast<std::size_t>(std::floor(position));
  const std::size_t upper = static_cast<std::size_t>(std::ceil(position));
  if (lower == upper) return values[lower];
  const double weight = position - static_cast<double>(lower);
  return values[lower] + weight * (values[upper] - values[lower]);
}

double median(std::vector<double> values) {
  return percentile(std::move(values), 0.5);
}

void fit_energy_trace(KernelMeasurement& measurement, const Options& options) {
  measurement.energy_trace_status = "fail";
  if (measurement.energy_trace.size() < 3) {
    measurement.energy_trace_status = "fail_too_few_samples";
    return;
  }

  std::vector<a100fp16::GpuEnergyCounterSample> changes;
  changes.reserve(measurement.energy_trace.size());
  changes.push_back(measurement.energy_trace.front());
  measurement.energy_trace_max_query_latency_s =
      measurement.energy_trace.front().query_latency_s;
  bool monotonic = true;
  for (std::size_t index = 1; index < measurement.energy_trace.size(); ++index) {
    const auto& point = measurement.energy_trace[index];
    const auto& previous = measurement.energy_trace[index - 1];
    measurement.energy_trace_max_query_latency_s = std::max(
        measurement.energy_trace_max_query_latency_s, point.query_latency_s);
    if (!point.energy_counter_supported || point.energy_mj < previous.energy_mj) {
      monotonic = false;
    }
    if (point.energy_mj != changes.back().energy_mj) changes.push_back(point);
  }
  if (!monotonic) {
    measurement.energy_trace_status = "fail_nonmonotonic_or_unsupported";
    return;
  }

  std::vector<double> update_intervals;
  for (std::size_t index = 1; index < changes.size(); ++index) {
    const double interval = changes[index].timestamp_s - changes[index - 1].timestamp_s;
    if (interval > 0.0) update_intervals.push_back(interval);
  }
  measurement.energy_trace_update_count =
      static_cast<int>(changes.size() - 1);
  if (update_intervals.size() < 2) {
    measurement.energy_trace_status = "fail_too_few_counter_updates";
    return;
  }
  measurement.energy_trace_update_interval_p99_s = percentile(update_intervals, 0.99);
  measurement.energy_trace_guard_s =
      2.0 * measurement.energy_trace_update_interval_p99_s;
  const double kernel_start_s = steady_seconds(measurement.kernel_start);
  const double kernel_end_s = steady_seconds(measurement.kernel_end);
  measurement.energy_trace_fit_start_s =
      kernel_start_s + measurement.energy_trace_guard_s;
  measurement.energy_trace_fit_end_s =
      kernel_end_s - measurement.energy_trace_guard_s;

  std::vector<a100fp16::GpuEnergyCounterSample> fit_points;
  for (std::size_t index = 1; index < changes.size(); ++index) {
    const auto& point = changes[index];
    if (point.timestamp_s >= measurement.energy_trace_fit_start_s &&
        point.timestamp_s <= measurement.energy_trace_fit_end_s) {
      fit_points.push_back(point);
    }
  }
  measurement.energy_trace_fit_point_count = static_cast<int>(fit_points.size());
  if (fit_points.size() < 2) {
    measurement.energy_trace_status = "fail_no_guarded_fit_window";
    return;
  }
  measurement.energy_trace_fit_span_s =
      fit_points.back().timestamp_s - fit_points.front().timestamp_s;
  if (measurement.energy_trace_fit_point_count < options.energy_trace_min_updates) {
    measurement.energy_trace_status = "fail_guarded_updates_below_gate";
    return;
  }

  const double origin = fit_points.front().timestamp_s;
  std::vector<double> slopes_w;
  slopes_w.reserve(fit_points.size() * (fit_points.size() - 1) / 2);
  for (std::size_t left = 0; left < fit_points.size(); ++left) {
    for (std::size_t right = left + 1; right < fit_points.size(); ++right) {
      const double dt = fit_points[right].timestamp_s - fit_points[left].timestamp_s;
      if (dt <= 0.0) continue;
      const double de_mj = static_cast<double>(fit_points[right].energy_mj -
                                               fit_points[left].energy_mj);
      slopes_w.push_back(de_mj / dt / 1000.0);
    }
  }
  if (slopes_w.empty()) {
    measurement.energy_trace_status = "fail_trace_slope_missing";
    return;
  }
  const double slope_w = median(std::move(slopes_w));
  const double slope_mj_per_s = slope_w * 1000.0;
  std::vector<double> intercepts_mj;
  intercepts_mj.reserve(fit_points.size());
  for (const auto& point : fit_points) {
    intercepts_mj.push_back(
        static_cast<double>(point.energy_mj) -
        slope_mj_per_s * (point.timestamp_s - origin));
  }
  const double intercept_mj = median(std::move(intercepts_mj));
  double mean_energy_mj = 0.0;
  for (const auto& point : fit_points) mean_energy_mj += point.energy_mj;
  mean_energy_mj /= static_cast<double>(fit_points.size());
  double residual_sum_squares = 0.0;
  double total_sum_squares = 0.0;
  for (const auto& point : fit_points) {
    const double observed = static_cast<double>(point.energy_mj);
    const double predicted = intercept_mj +
        slope_mj_per_s * (point.timestamp_s - origin);
    const double residual = observed - predicted;
    residual_sum_squares += residual * residual;
    const double centered = observed - mean_energy_mj;
    total_sum_squares += centered * centered;
  }
  measurement.energy_trace_power_w = slope_w;
  measurement.energy_trace_rmse_mj = std::sqrt(
      residual_sum_squares / static_cast<double>(fit_points.size()));
  measurement.energy_trace_r2 = total_sum_squares > 0.0
                                    ? 1.0 - residual_sum_squares / total_sum_squares
                                    : 0.0;
  if (!(slope_w > 0.0 && slope_w < 1000.0)) {
    measurement.energy_trace_status = "fail_trace_power_out_of_range";
  } else if (measurement.energy_trace_fit_span_s < 0.5) {
    measurement.energy_trace_status = "fail_trace_fit_span_below_gate";
  } else if (measurement.energy_trace_r2 < 0.98) {
    measurement.energy_trace_status = "fail_trace_linearity_below_gate";
  } else {
    measurement.energy_trace_status = "pass";
  }
}

std::uint64_t epoch_milliseconds() {
  return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count());
}

std::uint64_t checked_multiply(std::uint64_t left, std::uint64_t right,
                               const char* label) {
  if (left != 0 && right > std::numeric_limits<std::uint64_t>::max() / left) {
    throw std::overflow_error(std::string("overflow while computing ") + label);
  }
  return left * right;
}

std::uint64_t ceil_div(std::uint64_t numerator, std::uint64_t denominator) {
  return (numerator + denominator - 1) / denominator;
}

void usage(const char* program) {
  std::cout
      << "Usage: " << program << " --mode full|linear|io [options]\n\n"
      << "Softmax-specific options:\n"
      << "  --softmax-cols 128|256|512|1024|2048|4096 (default 512)\n"
      << "  --exp-impl fp32|ptx_f16|ptx_f16x2    exponential implementation\n"
      << "  --blocks-per-sm <n>                  (default 2)\n"
      << "  --grid-blocks <n>                     explicit CTA grid; 0 derives runtime SM x nominal blocks/SM\n"
      << "  --active-sm 0                         deprecated; CUDA launch cannot pin an SM subset\n"
      << "  --seconds <s>                         full-treatment calibration target\n"
      << "  --iters <n>                           fixed common ITER; bypass calibration\n"
      << "  --cache-condition cache_reuse_candidate|streaming_large_ws\n"
      << "  --cache-policy default|cg              (default default)\n"
      << "  --row-tiles-per-block <n>              0 derives 4x runtime-L2 streaming set\n"
      << "  --tile-stride <n>                      0 chooses a coprime stride\n"
      << "  --logit-scale <x>                      (default 4)\n"
      << "  --idle-measure-seconds <s>             (default 1)\n"
      << "  --calibrate-only | --validate-only | --dry-run\n"
      << "  --pair-id <id> --role <role> --repeat-index <n> --sequence-index <n>\n"
      << "  --bracket-control linear|io --bracket-pairs <n> --pair-prefix <id>\n"
      << "  --bracket-control also accepts probe for same-kernel 1x/2x exp contrast\n"
      << "  --bracket-warmup-pairs <n>             unrecorded continuous brackets\n"
      << "  --bracket-idle-policy pair_once|batch_once|per_role\n"
      << "  --bracket-order ctc|counterbalanced6  probe role order; counterbalanced6="
         " CTC,TCT,TCT,CTC,CTC,TCT\n"
      << "  --extra-exp-probe 0|1                  one additional selected EX2 result per element\n"
      << "  --energy-trace 0|1                     in-kernel total-energy trace (default 1)\n"
      << "  --energy-trace-sample-ms <ms>           default 500; RTX 3090 gate >=200\n"
      << "  --energy-trace-min-updates <n>          default 8 guarded points\n"
      << "  --energy-trace-output <csv>             optional raw counter trace\n"
      << "  --numerical-check-id <id> --binary-sha256 <hex>\n"
      << "  --measurement-purpose energy_atc|resource_sidecar\n"
      << "  --output <csv> --gpu-id <n> --target-profile rtx3090|a100|auto\n";
}

Options parse_options(int argc, char** argv) {
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    const auto value = [&]() -> std::string {
      if (index + 1 >= argc) throw std::invalid_argument("missing value for " + arg);
      return argv[++index];
    };
    if (arg == "--help" || arg == "-h") {
      usage(argv[0]);
      std::exit(0);
    } else if (arg == "--gpu-id") {
      options.gpu_id = std::stoi(value());
    } else if (arg == "--mode") {
      options.mode = mode_from_string(value());
    } else if (arg == "--exp-impl") {
      options.exp_implementation = exp_implementation_from_string(value());
    } else if (arg == "--softmax-cols") {
      options.softmax_cols = std::stoi(value());
    } else if (arg == "--blocks-per-sm") {
      options.blocks_per_sm = std::stoi(value());
    } else if (arg == "--grid-blocks") {
      options.grid_blocks = std::stoull(value());
    } else if (arg == "--active-sm") {
      options.active_sm = std::stoi(value());
    } else if (arg == "--seconds") {
      options.seconds = std::stod(value());
    } else if (arg == "--idle-measure-seconds") {
      options.idle_measure_seconds = std::stod(value());
    } else if (arg == "--iters") {
      options.iters = std::stoull(value());
    } else if (arg == "--repeats") {
      options.repeats = std::stoi(value());
    } else if (arg == "--logit-scale") {
      options.logit_scale = std::stof(value());
    } else if (arg == "--cache-condition") {
      options.cache_condition = cache_condition_from_string(value());
    } else if (arg == "--cache-policy") {
      options.cache_policy = cache_policy_from_string(value());
    } else if (arg == "--row-tiles-per-block") {
      options.row_tiles_per_block = std::stoull(value());
    } else if (arg == "--tile-stride") {
      options.tile_stride = std::stoull(value());
    } else if (arg == "--seed") {
      options.seed = std::stoull(value());
    } else if (arg == "--output") {
      options.output = value();
    } else if (arg == "--target-profile") {
      options.target_profile = value();
    } else if (arg == "--pair-id") {
      options.pair_id = value();
    } else if (arg == "--role") {
      options.role = value();
    } else if (arg == "--repeat-index") {
      options.repeat_index = std::stoi(value());
    } else if (arg == "--sequence-index") {
      options.sequence_index = std::stoi(value());
    } else if (arg == "--bracket-control") {
      options.bracket_control = value();
    } else if (arg == "--bracket-pairs") {
      options.bracket_pairs = std::stoi(value());
    } else if (arg == "--bracket-warmup-pairs") {
      options.bracket_warmup_pairs = std::stoi(value());
    } else if (arg == "--pair-prefix") {
      options.pair_prefix = value();
    } else if (arg == "--bracket-idle-policy") {
      options.bracket_idle_policy = value();
    } else if (arg == "--bracket-order") {
      options.bracket_order = value();
    } else if (arg == "--extra-exp-probe") {
      options.extra_exp_probe = std::stoi(value()) != 0;
    } else if (arg == "--energy-trace") {
      options.energy_trace = std::stoi(value()) != 0;
    } else if (arg == "--energy-trace-sample-ms") {
      options.energy_trace_sample_ms = std::stod(value());
    } else if (arg == "--energy-trace-min-updates") {
      options.energy_trace_min_updates = std::stoi(value());
    } else if (arg == "--energy-trace-output") {
      options.energy_trace_output = value();
    } else if (arg == "--numerical-check-id") {
      options.numerical_check_id = value();
    } else if (arg == "--binary-sha256") {
      options.binary_sha256 = value();
    } else if (arg == "--measurement-purpose") {
      options.measurement_purpose = value();
    } else if (arg == "--verify-smid") {
      options.verify_smid = std::stoi(value()) != 0;
    } else if (arg == "--calibrate-only") {
      options.calibrate_only = true;
    } else if (arg == "--validate-only") {
      options.validate_only = true;
    } else if (arg == "--dry-run") {
      options.dry_run = true;
    } else {
      throw std::invalid_argument("unknown option: " + arg);
    }
  }
  if (!supported_softmax_cols(options.softmax_cols)) {
    throw std::invalid_argument(
        "--softmax-cols must be 128,256,512,1024,2048,4096");
  }
  if (options.mode != SoftmaxMode::full &&
      is_native_f16_ex2(options.exp_implementation)) {
    throw std::invalid_argument(
        "native --exp-impl selections apply only to --mode full");
  }
  if (options.gpu_id < 0 || options.blocks_per_sm <= 0 || options.active_sm < 0 ||
      options.seconds <= 0.0 || options.idle_measure_seconds <= 0.0 ||
      options.repeats <= 0 || options.bracket_pairs < 0 ||
      options.bracket_warmup_pairs < 0 || options.energy_trace_sample_ms <= 0.0 ||
      options.energy_trace_min_updates < 2 ||
      !(options.logit_scale > 0.0f)) {
    throw std::invalid_argument("invalid non-positive runtime option");
  }
  if (options.calibrate_only && options.validate_only) {
    throw std::invalid_argument("--calibrate-only and --validate-only are exclusive");
  }
  if (options.target_profile != "rtx3090" &&
      options.target_profile != "a100" &&
      options.target_profile != "auto") {
    throw std::invalid_argument(
        "--target-profile must be rtx3090, a100, or auto");
  }
  if (options.measurement_purpose != "energy_atc" &&
      options.measurement_purpose != "resource_sidecar") {
    throw std::invalid_argument(
        "--measurement-purpose must be energy_atc or resource_sidecar");
  }
  if (options.energy_trace && options.target_profile == "rtx3090" &&
      options.energy_trace_sample_ms < 200.0) {
    throw std::invalid_argument(
        "RTX 3090/WSL total-energy tracing requires >=200 ms polling; "
        "high-frequency queries undercount the counter");
  }
  if (!options.energy_trace_output.empty() &&
      options.energy_trace_output == options.output) {
    throw std::invalid_argument(
        "--energy-trace-output must differ from --output");
  }
  if (options.active_sm != 0) {
    throw std::invalid_argument(
        "--active-sm cannot select physical SMs; use --grid-blocks for a partial CTA grid");
  }
  const bool bracket_requested = !options.bracket_control.empty() || options.bracket_pairs != 0 ||
                                !options.pair_prefix.empty();
  if (bracket_requested) {
    if (options.bracket_control != "linear" && options.bracket_control != "io" &&
        options.bracket_control != "probe") {
      throw std::invalid_argument(
          "--bracket-control must be linear, io, or probe when bracket mode is used");
    }
    if (options.bracket_pairs <= 0 || options.pair_prefix.empty()) {
      throw std::invalid_argument("bracket mode requires --bracket-pairs > 0 and --pair-prefix");
    }
    if (options.mode != SoftmaxMode::full) {
      throw std::invalid_argument("bracket mode must start with --mode full for full-treatment calibration");
    }
    if (options.repeats != 1) {
      throw std::invalid_argument("--repeats is not used in bracket mode; use --bracket-pairs");
    }
    if (options.bracket_idle_policy != "pair_once" &&
        options.bracket_idle_policy != "batch_once" &&
        options.bracket_idle_policy != "per_role") {
      throw std::invalid_argument(
          "--bracket-idle-policy must be pair_once, batch_once, or per_role");
    }
    if (options.bracket_order != "ctc" &&
        options.bracket_order != "counterbalanced6") {
      throw std::invalid_argument(
          "--bracket-order must be ctc or counterbalanced6");
    }
    if (options.bracket_order == "counterbalanced6" &&
        (options.bracket_control != "probe" || options.bracket_pairs != 6)) {
      throw std::invalid_argument(
          "--bracket-order counterbalanced6 requires --bracket-control probe "
          "and exactly six measured brackets");
    }
    if (options.bracket_order != "ctc" && options.bracket_control != "probe") {
      throw std::invalid_argument(
          "non-ctc bracket order is supported only for the same-kernel probe");
    }
    if (options.bracket_control != "probe" && options.extra_exp_probe) {
      throw std::invalid_argument(
          "--extra-exp-probe is controlled by bracket roles unless --bracket-control probe is used");
    }
    if (is_native_f16_ex2(options.exp_implementation) &&
        options.bracket_control != "probe") {
      throw std::invalid_argument(
          "native FP16 EX2 experiments require --bracket-control probe; "
          "linear/io controls do not execute the selected EX2 path");
    }
  }
  return options;
}

void require_profile_match(const Options& options, const DeviceState& state) {
  if (options.target_profile == "auto") return;
  if (options.target_profile == "rtx3090") {
    if (state.prop.major != 8 || state.prop.minor != 6) {
      throw std::runtime_error("rtx3090 profile requires compute capability 8.6");
    }
    if (state.cuda_binary_arch != 86) {
      throw std::runtime_error(
          "rtx3090 profile requires a native sm_86 softmax cubin; rebuild with "
          "-DCMAKE_CUDA_ARCHITECTURES=86");
    }
    return;
  }
  if (options.target_profile == "a100") {
    std::string gpu_name = state.prop.name;
    std::transform(gpu_name.begin(), gpu_name.end(), gpu_name.begin(),
                   [](unsigned char value) {
                     return static_cast<char>(std::tolower(value));
                   });
    if (state.prop.major != 8 || state.prop.minor != 0 ||
        gpu_name.find("a100") == std::string::npos) {
      throw std::runtime_error(
          "a100 profile requires an NVIDIA A100 compute-capability 8.0 device");
    }
    // A full A100 exposes 108 SMs.  A reduced count is normally a MIG compute
    // instance; the physical-board NVML counter cannot attribute its joules to
    // that slice, so it is invalid for this board-energy estimand.
    constexpr int kFullA100SmCount = 108;
    if (state.prop.multiProcessorCount != kFullA100SmCount) {
      throw std::runtime_error(
          "a100 board-energy profile requires the full 108-SM device; MIG or "
          "another reduced-SM partition is not attributable with the physical "
          "GPU total-energy counter");
    }
    if (state.cuda_binary_arch != 80) {
      throw std::runtime_error(
          "a100 profile requires a native sm_80 softmax cubin; rebuild with "
          "-DCMAKE_CUDA_ARCHITECTURES=80");
    }
    return;
  }
}

std::uint64_t choose_tile_stride(std::uint64_t tiles, std::uint64_t requested) {
  if (tiles <= 1) return 1;
  if (requested != 0) {
    if (requested >= tiles || std::gcd(requested, tiles) != 1) {
      throw std::invalid_argument("tile stride must be less than row tiles and coprime");
    }
    return requested;
  }
  std::uint64_t candidate = 1315423911ull % tiles;
  if (candidate == 0) candidate = 1;
  while (std::gcd(candidate, tiles) != 1) {
    candidate = (candidate + 1) % tiles;
    if (candidate == 0) candidate = 1;
  }
  return candidate;
}

DeviceState create_device_state(const Options& options) {
  DeviceState state;
  state.gpu_id = options.gpu_id;
  CUDA_CHECK(cudaSetDevice(options.gpu_id));
  CUDA_CHECK(cudaGetDeviceProperties(&state.prop, options.gpu_id));
  char pci_bus_id[32] = {};
  CUDA_CHECK(cudaDeviceGetPCIBusId(pci_bus_id, sizeof(pci_bus_id),
                                   options.gpu_id));
  state.cuda_pci_bus_id = pci_bus_id;
  state.cuda_binary_arch = query_softmax_binary_version(
      options.mode, options.softmax_cols, options.cache_policy,
      options.exp_implementation);
  if (state.cuda_binary_arch <= 0) {
    throw std::runtime_error(
        "unable to resolve the loaded Softmax kernel binary architecture");
  }
  require_profile_match(options, state);
  if (is_native_f16_ex2(options.exp_implementation) &&
      (state.cuda_binary_arch < 75 ||
       state.prop.major * 10 + state.prop.minor < 75)) {
    throw std::runtime_error(
        "native FP16 EX2 requires both a sm_75+ cubin and a sm_75+ device");
  }
  state.active_sm = state.prop.multiProcessorCount;
  state.explicit_grid_blocks = options.grid_blocks != 0;
  state.grid_blocks = state.explicit_grid_blocks
                          ? options.grid_blocks
                          : checked_multiply(
                                static_cast<std::uint64_t>(state.active_sm),
                                static_cast<std::uint64_t>(options.blocks_per_sm),
                                "grid blocks");
  if (state.grid_blocks == 0 ||
      state.grid_blocks > static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
    throw std::invalid_argument("--grid-blocks must be between 1 and INT_MAX");
  }
  state.occupancy_max_blocks_per_sm = query_softmax_occupancy_max_blocks_per_sm(
      options.mode, options.softmax_cols, options.cache_policy,
      options.exp_implementation);
  state.static_single_wave_capacity_blocks = checked_multiply(
      static_cast<std::uint64_t>(state.prop.multiProcessorCount),
      static_cast<std::uint64_t>(state.occupancy_max_blocks_per_sm),
      "static single-wave CTA capacity");

  const std::uint64_t bytes_per_row = checked_multiply(
      static_cast<std::uint64_t>(options.softmax_cols), 2ull * sizeof(half),
      "input/output bytes per row");
  if (options.row_tiles_per_block != 0) {
    state.row_tiles_per_block = options.row_tiles_per_block;
  } else if (options.cache_condition == CacheCondition::streaming_large_ws) {
    const std::uint64_t target_working_set =
        std::max<std::uint64_t>(4ull * static_cast<std::uint64_t>(state.prop.l2CacheSize),
                                bytes_per_row);
    const std::uint64_t rows_needed = ceil_div(target_working_set, bytes_per_row);
    state.row_tiles_per_block =
        std::max<std::uint64_t>(2, ceil_div(rows_needed, state.grid_blocks));
  }
  state.tile_stride = choose_tile_stride(state.row_tiles_per_block, options.tile_stride);
  state.n_rows = checked_multiply(state.grid_blocks, state.row_tiles_per_block,
                                  "allocated rows");
  const std::uint64_t input_count_u64 = checked_multiply(
      state.n_rows, static_cast<std::uint64_t>(options.softmax_cols), "input count");
  if (input_count_u64 > std::numeric_limits<std::size_t>::max()) {
    throw std::overflow_error("input allocation exceeds size_t");
  }
  state.input_count = static_cast<std::size_t>(input_count_u64);
  state.working_set_bytes = static_cast<std::size_t>(checked_multiply(
      input_count_u64, 2ull * sizeof(half), "input/output working set"));
  state.sm_count_capacity = std::max(512, state.prop.multiProcessorCount + 64);

  std::size_t free_bytes = 0;
  std::size_t total_bytes = 0;
  CUDA_CHECK(cudaMemGetInfo(&free_bytes, &total_bytes));
  const std::uint64_t metadata_bytes =
      state.grid_blocks * (sizeof(std::uint32_t) + sizeof(int)) +
      static_cast<std::uint64_t>(state.sm_count_capacity) * sizeof(int);
  const std::uint64_t requested_bytes = state.working_set_bytes + metadata_bytes;
  if (requested_bytes > static_cast<std::uint64_t>(0.80 * free_bytes)) {
    throw std::runtime_error("softmax allocation would exceed 80% of free device memory");
  }

  CUDA_CHECK(cudaStreamCreateWithFlags(&state.stream, cudaStreamNonBlocking));
  CUDA_CHECK(cudaMalloc(&state.input, state.input_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(&state.output, state.input_count * sizeof(half)));
  CUDA_CHECK(cudaMalloc(&state.token_by_block,
                        state.grid_blocks * sizeof(std::uint32_t)));
  CUDA_CHECK(cudaMalloc(&state.smid_by_block, state.grid_blocks * sizeof(int)));
  CUDA_CHECK(cudaMalloc(&state.sm_counts,
                        state.sm_count_capacity * sizeof(int)));
  CUDA_CHECK(launch_softmax_init(state.input, state.input_count, options.logit_scale,
                                 options.seed, state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  return state;
}

void destroy_device_state(DeviceState& state) {
  if (state.gpu_id >= 0) cudaSetDevice(state.gpu_id);
  if (state.stream) cudaStreamSynchronize(state.stream);
  if (state.input) cudaFree(state.input);
  if (state.output) cudaFree(state.output);
  if (state.token_by_block) cudaFree(state.token_by_block);
  if (state.smid_by_block) cudaFree(state.smid_by_block);
  if (state.sm_counts) cudaFree(state.sm_counts);
  if (state.stream) cudaStreamDestroy(state.stream);
  state = DeviceState{};
}

SoftmaxLaunchConfig make_launch_config(const Options& options,
                                       const DeviceState& state,
                                       std::uint64_t iters) {
  SoftmaxLaunchConfig config;
  config.mode = options.mode;
  config.exp_implementation = options.exp_implementation;
  config.cache_policy = options.cache_policy;
  config.softmax_cols = options.softmax_cols;
  config.grid_blocks = state.grid_blocks;
  config.iters = iters;
  config.row_tiles_per_block = state.row_tiles_per_block;
  config.tile_stride = state.tile_stride;
  config.streaming = options.cache_condition == CacheCondition::streaming_large_ws;
  config.extra_exp_probe = options.extra_exp_probe;
  config.input = state.input;
  config.output = state.output;
  config.token_by_block = state.token_by_block;
  config.smid_by_block = state.smid_by_block;
  config.sm_counts = state.sm_counts;
  config.sm_count_capacity = state.sm_count_capacity;
  config.stream = state.stream;
  return config;
}

void reset_smid_buffers(const DeviceState& state) {
  CUDA_CHECK(cudaMemsetAsync(state.sm_counts, 0,
                             state.sm_count_capacity * sizeof(int), state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.smid_by_block, 0xff,
                             state.grid_blocks * sizeof(int), state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.token_by_block, 0,
                             state.grid_blocks * sizeof(std::uint32_t), state.stream));
}

double launch_and_time(const Options& options, const DeviceState& state,
                       std::uint64_t iters, bool reset_placement) {
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  if (reset_placement) reset_smid_buffers(state);
  const auto start = Clock::now();
  CUDA_CHECK(launch_softmax_kernel(make_launch_config(options, state, iters)));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  return elapsed_seconds(start, Clock::now());
}

IterCalibration calibrate_iters(const Options& options, const DeviceState& state) {
  if (options.iters != 0) return IterCalibration{options.iters, options.iters, 0.0};
  // JIT and allocator effects are outside the calibration trial used below.
  launch_and_time(options, state, 1, false);
  std::uint64_t trial_iters = 1;
  double trial_elapsed_s = 0.0;
  constexpr double kMinimumCalibrationSeconds = 0.050;
  for (int attempt = 0; attempt < 12; ++attempt) {
    trial_elapsed_s = launch_and_time(options, state, trial_iters, false);
    if (trial_elapsed_s >= kMinimumCalibrationSeconds) break;
    const double scale = trial_elapsed_s > 1.0e-6
                             ? kMinimumCalibrationSeconds / trial_elapsed_s
                             : 64.0;
    const long double next = std::ceil(static_cast<long double>(trial_iters) *
                                       std::min(128.0, std::max(2.0, scale * 1.2)));
    if (next > static_cast<long double>(std::numeric_limits<std::uint64_t>::max())) {
      throw std::runtime_error("softmax ITER calibration overflow");
    }
    trial_iters = std::max<std::uint64_t>(1, static_cast<std::uint64_t>(next));
  }
  if (trial_elapsed_s < kMinimumCalibrationSeconds) {
    throw std::runtime_error("softmax calibration did not reach the 50 ms loop-survival floor");
  }
  const long double estimate = std::ceil(
      static_cast<long double>(trial_iters) * options.seconds / trial_elapsed_s * 1.05L);
  if (estimate > static_cast<long double>(std::numeric_limits<std::uint64_t>::max())) {
    throw std::runtime_error("softmax target ITER overflow");
  }
  return IterCalibration{std::max<std::uint64_t>(1, static_cast<std::uint64_t>(estimate)),
                         trial_iters, trial_elapsed_s};
}

IdleMeasurement measure_idle(a100fp16::NvmlEnergy& nvml,
                             const DeviceState& state,
                             double requested_seconds) {
  const auto before = nvml.sample_by_pci_bus_id(state.cuda_pci_bus_id,
                                                state.gpu_id);
  const auto start = Clock::now();
  std::this_thread::sleep_for(std::chrono::duration<double>(requested_seconds));
  const double elapsed_s = elapsed_seconds(start, Clock::now());
  const auto after = nvml.sample_by_pci_bus_id(state.cuda_pci_bus_id,
                                               state.gpu_id);
  if (!before.energy_counter_supported || !after.energy_counter_supported) {
    throw std::runtime_error("NVML total-energy counter is required for softmax ATC");
  }
  if (after.energy_mj < before.energy_mj || elapsed_s <= 0.0) {
    throw std::runtime_error("invalid idle energy sample");
  }
  const double delta_j = static_cast<double>(after.energy_mj - before.energy_mj) / 1000.0;
  return IdleMeasurement{elapsed_s, delta_j, delta_j / elapsed_s};
}

SmidCheck summarize_smids(const std::vector<int>& smids,
                          int physical_sm_count) {
  if (physical_sm_count <= 0) {
    throw std::invalid_argument("physical SM count must be positive");
  }
  SmidCheck check;
  // PTX defines %smid as an implementation-dependent identifier.  IDs need
  // not be dense and may be greater than multiProcessorCount - 1, so index by
  // the observed value rather than by a physical-SM-sized vector.
  std::map<int, int> counts;
  for (int smid : smids) {
    if (smid < 0) continue;
    ++counts[smid];
    ++check.total_blocks;
  }
  for (const auto& [smid, count] : counts) {
    (void)smid;
    ++check.unique_sms;
    check.max_blocks_on_sm = std::max(check.max_blocks_on_sm, count);
  }
  std::ostringstream set_stream;
  std::ostringstream histogram_stream;
  bool first = true;
  for (const auto& [smid, count] : counts) {
    if (!first) {
      set_stream << '|';
      histogram_stream << '|';
    }
    first = false;
    set_stream << smid;
    histogram_stream << smid << ':' << count;
  }
  check.smid_set = set_stream.str();
  check.histogram = histogram_stream.str();
  check.all_blocks_observed =
      check.total_blocks == static_cast<int>(smids.size());
  const int max_unique = std::min<int>(static_cast<int>(smids.size()),
                                       physical_sm_count);
  // This is a kernel-entry assignment audit.  It deliberately does not claim
  // concurrent residency or a requested physical-SM subset.
  check.ok = check.all_blocks_observed && check.unique_sms >= 1 &&
             check.unique_sms <= max_unique;
  return check;
}

void require_sparse_smid_self_check() {
  const SmidCheck sparse = summarize_smids({0, 2, 5, 7}, 4);
  if (!sparse.ok || !sparse.all_blocks_observed || sparse.unique_sms != 4 ||
      sparse.total_blocks != 4 || sparse.max_blocks_on_sm != 1 ||
      sparse.smid_set != "0|2|5|7" ||
      sparse.histogram != "0:1|2:1|5:1|7:1") {
    throw std::logic_error("sparse SMID aggregation self-check failed");
  }
}

SmidCheck check_smid(const Options& options, const DeviceState& state) {
  if (!options.verify_smid) {
    SmidCheck disabled;
    disabled.ok = true;
    disabled.all_blocks_observed = true;
    disabled.smid_set = "not_checked";
    disabled.histogram = "not_checked";
    return disabled;
  }
  std::vector<int> smids(state.grid_blocks, -1);
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  CUDA_CHECK(cudaMemcpy(smids.data(), state.smid_by_block,
                        smids.size() * sizeof(int), cudaMemcpyDeviceToHost));
  return summarize_smids(smids, state.prop.multiProcessorCount);
}

KernelMeasurement measure_kernel(const Options& options, const DeviceState& state,
                                 a100fp16::NvmlEnergy& nvml,
                                 std::uint64_t iters) {
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  reset_smid_buffers(state);
  // Keep the metadata reset outside the energy window.  It is tiny, but this
  // makes the counter boundaries match the named kernel more faithfully.
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  const auto before_metadata = nvml.sample_by_pci_bus_id(
      state.cuda_pci_bus_id, state.gpu_id);
  const auto counter_before = nvml.sample_energy_counter_by_pci_bus_id(
      state.cuda_pci_bus_id);
  if (!before_metadata.energy_counter_supported ||
      !counter_before.energy_counter_supported) {
    throw std::runtime_error("NVML total-energy counter is required for softmax ATC");
  }
  KernelMeasurement measurement;
  measurement.before = before_metadata;
  measurement.before.energy_mj = counter_before.energy_mj;
  measurement.before.timestamp_s = counter_before.timestamp_s;
  measurement.energy_trace.push_back(counter_before);
  measurement.start_epoch_ms = epoch_milliseconds();
  cudaEvent_t event_start = nullptr;
  cudaEvent_t event_stop = nullptr;
  CUDA_CHECK(cudaEventCreate(&event_start));
  CUDA_CHECK(cudaEventCreate(&event_stop));
  const auto start = Clock::now();
  measurement.kernel_start = start;
  CUDA_CHECK(cudaEventRecord(event_start, state.stream));
  CUDA_CHECK(launch_softmax_kernel(make_launch_config(options, state, iters)));
  CUDA_CHECK(cudaEventRecord(event_stop, state.stream));
  std::mutex sampler_mutex;
  std::condition_variable sampler_wakeup;
  bool stop_sampler = false;
  std::exception_ptr sampler_error;
  std::thread sampler;
  if (options.energy_trace) {
    sampler = std::thread([&]() {
      std::unique_lock<std::mutex> lock(sampler_mutex);
      const auto interval =
          std::chrono::duration<double, std::milli>(options.energy_trace_sample_ms);
      while (!stop_sampler) {
        if (sampler_wakeup.wait_for(lock, interval,
                                    [&]() { return stop_sampler; })) {
          break;
        }
        lock.unlock();
        try {
          measurement.energy_trace.push_back(
              nvml.sample_energy_counter_by_pci_bus_id(state.cuda_pci_bus_id));
        } catch (...) {
          lock.lock();
          sampler_error = std::current_exception();
          stop_sampler = true;
          lock.unlock();
          sampler_wakeup.notify_one();
          return;
        }
        lock.lock();
      }
    });
  }
  const cudaError_t synchronize_status = cudaEventSynchronize(event_stop);
  measurement.kernel_end = Clock::now();
  if (sampler.joinable()) {
    {
      std::lock_guard<std::mutex> lock(sampler_mutex);
      stop_sampler = true;
    }
    sampler_wakeup.notify_one();
    sampler.join();
  }
  CUDA_CHECK(synchronize_status);
  if (sampler_error) std::rethrow_exception(sampler_error);
  float event_elapsed_ms = 0.0f;
  CUDA_CHECK(cudaEventElapsedTime(&event_elapsed_ms, event_start, event_stop));
  measurement.elapsed_s = static_cast<double>(event_elapsed_ms) / 1000.0;
  CUDA_CHECK(cudaEventDestroy(event_start));
  CUDA_CHECK(cudaEventDestroy(event_stop));
  const auto counter_after = nvml.sample_energy_counter_by_pci_bus_id(
      state.cuda_pci_bus_id);
  measurement.energy_trace.push_back(counter_after);
  measurement.end_epoch_ms = measurement.start_epoch_ms +
      static_cast<std::uint64_t>(std::llround(measurement.elapsed_s * 1000.0));
  measurement.after = nvml.sample_by_pci_bus_id(state.cuda_pci_bus_id,
                                                state.gpu_id);
  measurement.after.energy_mj = counter_after.energy_mj;
  measurement.after.timestamp_s = counter_after.timestamp_s;
  if (!measurement.after.energy_counter_supported ||
      !counter_after.energy_counter_supported ||
      counter_after.energy_mj < counter_before.energy_mj) {
    throw std::runtime_error("invalid NVML total-energy kernel sample");
  }
  measurement.endpoint_delta_j =
      static_cast<double>(counter_after.energy_mj - counter_before.energy_mj) / 1000.0;
  if (options.energy_trace) {
    fit_energy_trace(measurement, options);
    measurement.delta_j = measurement.energy_trace_status == "pass"
                              ? measurement.energy_trace_power_w * measurement.elapsed_s
                              : measurement.endpoint_delta_j;
  } else {
    measurement.energy_trace_status = "disabled_endpoint_only";
    measurement.delta_j = measurement.endpoint_delta_j;
  }
  measurement.smid = check_smid(options, state);
  return measurement;
}

std::vector<float> validation_pattern(int cols, int pattern, float scale) {
  std::vector<float> values(cols, 0.0f);
  for (int column = 0; column < cols; ++column) {
    switch (pattern) {
      case 0:
        values[column] = 0.25f;
        break;
      case 1:
        values[column] = (column & 1) ? scale : -scale;
        break;
      case 2:
        values[column] = column == 3 ? 16.0f : -16.0f;
        break;
      default:
        values[column] = column < 2 ? 1.0f - 0.0005f * column
                                    : -2.0f + 0.0003f * (column & 31);
        break;
    }
  }
  return values;
}

void verify_numerics(const Options& options, const DeviceState& state) {
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  std::vector<half> host_input(state.input_count);
  for (std::uint64_t row = 0; row < state.n_rows; ++row) {
    const auto pattern = validation_pattern(options.softmax_cols,
                                            static_cast<int>(row % 4),
                                            options.logit_scale);
    for (int column = 0; column < options.softmax_cols; ++column) {
      host_input[row * options.softmax_cols + column] = __float2half_rn(pattern[column]);
    }
  }
  CUDA_CHECK(cudaMemcpyAsync(state.input, host_input.data(),
                             host_input.size() * sizeof(half), cudaMemcpyHostToDevice,
                             state.stream));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  Options control_options = options;
  control_options.mode = SoftmaxMode::full;
  control_options.extra_exp_probe = false;
  Options treatment_options = control_options;
  treatment_options.extra_exp_probe = true;
  reset_smid_buffers(state);
  CUDA_CHECK(launch_softmax_kernel(make_launch_config(control_options, state, 1)));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  std::vector<half> first_output(state.input_count);
  CUDA_CHECK(cudaMemcpy(first_output.data(), state.output,
                        first_output.size() * sizeof(half), cudaMemcpyDeviceToHost));
  reset_smid_buffers(state);
  CUDA_CHECK(launch_softmax_kernel(make_launch_config(treatment_options, state, 1)));
  CUDA_CHECK(cudaStreamSynchronize(state.stream));
  std::vector<half> second_output(state.input_count);
  CUDA_CHECK(cudaMemcpy(second_output.data(), state.output,
                        second_output.size() * sizeof(half), cudaMemcpyDeviceToHost));

  bool bit_identical = true;
  for (std::size_t index = 0; index < first_output.size(); ++index) {
    if (__half_as_ushort(first_output[index]) != __half_as_ushort(second_output[index])) {
      bit_identical = false;
      break;
    }
  }
  double max_abs_error = 0.0;
  double max_sum_error = 0.0;
  bool finite = true;
  const int checked_blocks = std::min<int>(4, static_cast<int>(state.grid_blocks));
  for (int block = 0; block < checked_blocks; ++block) {
    const std::uint64_t row = static_cast<std::uint64_t>(block) * state.row_tiles_per_block;
    std::vector<long double> reference(options.softmax_cols);
    long double maximum = -std::numeric_limits<long double>::infinity();
    for (int column = 0; column < options.softmax_cols; ++column) {
      maximum = std::max(maximum, static_cast<long double>(__half2float(
          host_input[row * options.softmax_cols + column])));
    }
    long double denominator = 0.0;
    for (int column = 0; column < options.softmax_cols; ++column) {
      reference[column] = std::exp(static_cast<long double>(__half2float(
          host_input[row * options.softmax_cols + column])) - maximum);
      denominator += reference[column];
    }
    double row_sum = 0.0;
    for (int column = 0; column < options.softmax_cols; ++column) {
      const float observed = __half2float(first_output[row * options.softmax_cols + column]);
      finite = finite && std::isfinite(observed);
      row_sum += observed;
      const double expected = static_cast<double>(reference[column] / denominator);
      max_abs_error = std::max(max_abs_error, std::abs(observed - expected));
    }
    max_sum_error = std::max(max_sum_error, std::abs(row_sum - 1.0));
  }
  if (!finite || !bit_identical || max_abs_error > 2.0e-3 || max_sum_error > 2.0e-3) {
    std::ostringstream error;
    error << "numerical validation failed: finite=" << finite
          << " bit_identical=" << bit_identical << " max_abs_error=" << max_abs_error
          << " max_row_sum_error=" << max_sum_error;
    throw std::runtime_error(error.str());
  }
  const char* numerical_check_id =
      is_native_f16_ex2(options.exp_implementation)
          ? "fp16_softmax_cpu_fp64_native_ex2_v1_pass"
          : "fp16_softmax_cpu_fp64_v1_pass";
  std::cout << "numerical_check_id=" << numerical_check_id
            << " exp_impl=" << to_string(options.exp_implementation)
            << " max_abs_error=" << max_abs_error
            << " max_row_sum_error=" << max_sum_error
            << " control_treatment_bit_identical=true\n";
}

void verify_native_ex2_all_encodings(const Options& options,
                                     const DeviceState& state) {
  if (!is_native_f16_ex2(options.exp_implementation)) return;

  // Duplicate each of the 65,536 half encodings into both positions of one
  // pair.  This exercises every bit pattern in both f16x2 lanes while the
  // scalar kernel evaluates the identical ordered input buffer.
  constexpr std::size_t kEncodingCount = 1u << 16;
  constexpr std::size_t kValueCount = 2 * kEncodingCount;
  std::vector<half> host_input(kValueCount);
  for (std::size_t encoding = 0; encoding < kEncodingCount; ++encoding) {
    const auto bits = static_cast<unsigned short>(encoding);
    half value{};
    std::memcpy(&value, &bits, sizeof(bits));
    host_input[2 * encoding] = value;
    host_input[2 * encoding + 1] = value;
  }

  half* device_input = nullptr;
  half* device_scalar = nullptr;
  half* device_packed = nullptr;
  const auto cleanup = [&]() {
    if (device_input) cudaFree(device_input);
    if (device_scalar) cudaFree(device_scalar);
    if (device_packed) cudaFree(device_packed);
  };
  try {
    CUDA_CHECK(cudaMalloc(&device_input, kValueCount * sizeof(half)));
    CUDA_CHECK(cudaMalloc(&device_scalar, kValueCount * sizeof(half)));
    CUDA_CHECK(cudaMalloc(&device_packed, kValueCount * sizeof(half)));
    CUDA_CHECK(cudaMemcpyAsync(device_input, host_input.data(),
                               kValueCount * sizeof(half),
                               cudaMemcpyHostToDevice, state.stream));
    CUDA_CHECK(launch_native_ex2_validation(
        device_input, device_scalar, device_packed, kValueCount, state.stream));
    CUDA_CHECK(cudaStreamSynchronize(state.stream));

    std::vector<half> scalar(kValueCount);
    std::vector<half> packed(kValueCount);
    CUDA_CHECK(cudaMemcpy(scalar.data(), device_scalar,
                          kValueCount * sizeof(half), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(packed.data(), device_packed,
                          kValueCount * sizeof(half), cudaMemcpyDeviceToHost));
    cleanup();
    device_input = nullptr;
    device_scalar = nullptr;
    device_packed = nullptr;

    const auto half_bits = [](half value) {
      unsigned short bits = 0;
      std::memcpy(&bits, &value, sizeof(bits));
      return bits;
    };
    const auto is_nan_bits = [](unsigned short bits) {
      return (bits & 0x7c00u) == 0x7c00u && (bits & 0x03ffu) != 0;
    };
    const auto is_inf_bits = [](unsigned short bits) {
      return (bits & 0x7fffu) == 0x7c00u;
    };

    std::size_t packed_scalar_mismatch_count = 0;
    std::size_t nan_classification_failure_count = 0;
    std::size_t normal_result_count = 0;
    std::size_t subnormal_result_count = 0;
    std::size_t zero_result_count = 0;
    std::size_t infinity_result_count = 0;
    double max_normal_relative_error = 0.0;
    bool corner_cases_ok = true;
    const double minimum_normal = std::ldexp(1.0, -14);
    const double documented_relative_error_bound = std::pow(2.0, -9.9);

    for (std::size_t encoding = 0; encoding < kEncodingCount; ++encoding) {
      const unsigned short input_bits = static_cast<unsigned short>(encoding);
      const unsigned short scalar_low = half_bits(scalar[2 * encoding]);
      const unsigned short scalar_high = half_bits(scalar[2 * encoding + 1]);
      const unsigned short packed_low = half_bits(packed[2 * encoding]);
      const unsigned short packed_high = half_bits(packed[2 * encoding + 1]);
      if (is_nan_bits(input_bits)) {
        if (!is_nan_bits(scalar_low) || !is_nan_bits(scalar_high) ||
            !is_nan_bits(packed_low) || !is_nan_bits(packed_high)) {
          ++nan_classification_failure_count;
        }
        continue;
      }
      if (scalar_low != scalar_high || scalar_low != packed_low ||
          scalar_low != packed_high) {
        ++packed_scalar_mismatch_count;
      }

      const unsigned short magnitude = scalar_low & 0x7fffu;
      if (magnitude == 0) {
        ++zero_result_count;
      } else if ((magnitude & 0x7c00u) == 0) {
        ++subnormal_result_count;
      } else if (is_inf_bits(scalar_low)) {
        ++infinity_result_count;
      } else {
        ++normal_result_count;
      }

      if (!is_inf_bits(input_bits)) {
        const double exact = std::exp2(
            static_cast<double>(__half2float(host_input[2 * encoding])));
        if (exact >= minimum_normal && exact <= 65504.0 &&
            !is_inf_bits(scalar_low)) {
          const double observed = static_cast<double>(
              __half2float(scalar[2 * encoding]));
          max_normal_relative_error = std::max(
              max_normal_relative_error, std::abs(observed - exact) / exact);
        }
      }
    }

    // PTX-defined corner cases.  NaN payload/sign is deliberately not tested.
    corner_cases_ok = corner_cases_ok &&
        half_bits(scalar[2 * 0x0000u]) == 0x3c00u &&
        half_bits(scalar[2 * 0x8000u]) == 0x3c00u &&
        half_bits(scalar[2 * 0xfc00u]) == 0x0000u &&
        half_bits(scalar[2 * 0x7c00u]) == 0x7c00u;

    const double error_slack = 2.0e-7;
    if (packed_scalar_mismatch_count != 0 ||
        nan_classification_failure_count != 0 || !corner_cases_ok ||
        max_normal_relative_error > documented_relative_error_bound + error_slack) {
      std::ostringstream error;
      error << "native EX2 exhaustive validation failed: packed_scalar_mismatch="
            << packed_scalar_mismatch_count
            << " nan_classification_failures="
            << nan_classification_failure_count
            << " corner_cases_ok=" << corner_cases_ok
            << " max_normal_relative_error=" << max_normal_relative_error
            << " documented_bound=" << documented_relative_error_bound;
      throw std::runtime_error(error.str());
    }
    std::cout
        << "native_ex2_validation_id=ptx_ex2_f16_all_encodings_v1_pass"
        << " packed_scalar_bit_mismatch_count="
        << packed_scalar_mismatch_count
        << " nan_classification_failure_count="
        << nan_classification_failure_count
        << " normal_result_count=" << normal_result_count
        << " subnormal_result_count=" << subnormal_result_count
        << " zero_result_count=" << zero_result_count
        << " infinity_result_count=" << infinity_result_count
        << " max_normal_relative_error=" << max_normal_relative_error
        << " documented_relative_error_bound="
        << documented_relative_error_bound
        << " corner_cases_ok=true\n";
  } catch (...) {
    cleanup();
    throw;
  }
}

SoftmaxResultRow make_result_row(const Options& options, const DeviceState& state,
                                 const IdleMeasurement& idle,
                                 const KernelMeasurement& measurement,
                                 std::uint64_t iters, int repeat,
                                 const BracketMetadata& bracket) {
  SoftmaxResultRow row;
  row.run_id = "softmax_" + std::to_string(measurement.start_epoch_ms) + "_" +
               to_string(options.mode) + "_" +
               to_string(options.exp_implementation) + "_r" +
               std::to_string(repeat);
  row.pair_id = options.pair_id;
  row.role = options.role;
  row.repeat = options.repeat_index >= 0 ? options.repeat_index : repeat;
  row.sequence_index = options.sequence_index;
  row.execution_model = bracket.execution_model;
  row.bracket_context_id = bracket.context_id;
  row.idle_baseline_scope = bracket.idle_baseline_scope;
  row.preceding_role_gap_s = bracket.preceding_role_gap_s;
  row.preceding_counter_gap_delta_J = bracket.preceding_counter_gap_delta_j;
  row.gpu_id = state.gpu_id;
  row.cuda_pci_bus_id = state.cuda_pci_bus_id;
  row.cuda_binary_arch = state.cuda_binary_arch;
  row.mode = to_string(options.mode);
  row.extra_exp_probe = options.extra_exp_probe;
  row.operand_delta_per_element = options.extra_exp_probe ? 1 : 0;
  row.softmax_cols = options.softmax_cols;
  row.threads_per_block = kThreadsPerBlock;
  row.rows_per_block = 1;
  row.row_tiles_per_block = state.row_tiles_per_block;
  row.tile_stride = state.tile_stride;
  row.elements_per_thread = elements_per_thread(options.softmax_cols);
  row.active_sm = state.active_sm;
  row.runtime_sm_count = state.prop.multiProcessorCount;
  row.blocks_per_sm = options.blocks_per_sm;
  row.grid_nominal_ctas_per_sm = static_cast<int>(ceil_div(
      state.grid_blocks,
      static_cast<std::uint64_t>(state.prop.multiProcessorCount)));
  row.grid_blocks = state.grid_blocks;
  row.grid_blocks_source = state.explicit_grid_blocks
                               ? "explicit"
                               : "runtime_sm_x_nominal_blocks_per_sm";
  row.sm_residency_claim = "none_kernel_entry_assignment_only";
  if (state.grid_blocks < static_cast<std::uint64_t>(state.prop.multiProcessorCount)) {
    row.grid_experiment_purpose =
        "partial_grid_active_sm_signal_sweep_not_sfu_supply";
  } else if (state.grid_blocks ==
             static_cast<std::uint64_t>(state.prop.multiProcessorCount)) {
    row.grid_experiment_purpose =
        "full_grid_nominal_one_cta_per_sm_no_affinity";
  } else {
    row.grid_experiment_purpose =
        "multi_cta_supply_grid_no_per_sm_affinity";
  }
  row.ITER = iters;
  row.n_rows_allocated = state.n_rows;
  row.n_elements = checked_multiply(
      checked_multiply(state.grid_blocks, iters, "processed block iterations"),
      static_cast<std::uint64_t>(options.softmax_cols), "processed elements");
  const std::uint64_t processed_rows = checked_multiply(state.grid_blocks, iters,
                                                        "processed rows");
  row.scalar_convention_ops =
      3ull * row.n_elements - processed_rows;  // subtract + sum-add + normalize mul
  row.softmax_high_level_ops = 5ull * row.n_elements - processed_rows;
  row.input_dtype = "fp16";
  row.output_dtype = "fp16";
  const ExpPathMetadata exp_metadata =
      exp_path_metadata(options.exp_implementation, state.prop.major);
  row.compute_dtype = exp_metadata.compute_dtype;
  row.exp_impl = to_string(options.exp_implementation);
  row.exp_input_dtype = exp_metadata.exp_input_dtype;
  row.special_function_path = exp_metadata.special_function_path;
  row.exp_ptx_instruction = exp_metadata.ptx_instruction;
  row.exp_results_per_ptx_instruction =
      exp_metadata.results_per_ptx_instruction;
  row.sass_mufu_ex2_per_ptx_instruction_model =
      exp_metadata.sass_mufu_per_ptx_instruction_model;
  row.sass_lowering_model_status =
      exp_metadata.sass_lowering_model_status;
  row.xu_documented_results_per_sm_cycle =
      exp_metadata.documented_results_per_sm_cycle;
  const std::uint64_t cols = static_cast<std::uint64_t>(options.softmax_cols);
  // ptxas retains the reciprocal only for threads whose result is consumed by
  // an output store.  Short rows therefore execute it on S lanes rather than
  // all 256 CTA lanes.
  const std::uint64_t reciprocal_thread_ops =
      std::min<std::uint64_t>(cols, kThreadsPerBlock);
  row.expected_control_ex2_scalar_results_per_cta_iter = cols;
  row.expected_treatment_ex2_scalar_results_per_cta_iter = 2 * cols;
  row.expected_probe_ex2_scalar_results_per_cta_iter = cols;
  const std::uint64_t results_per_ptx = static_cast<std::uint64_t>(
      row.exp_results_per_ptx_instruction);
  row.expected_control_ex2_ptx_instructions_per_cta_iter =
      row.expected_control_ex2_scalar_results_per_cta_iter / results_per_ptx;
  row.expected_treatment_ex2_ptx_instructions_per_cta_iter =
      row.expected_treatment_ex2_scalar_results_per_cta_iter / results_per_ptx;
  row.expected_probe_ex2_ptx_instructions_per_cta_iter =
      row.expected_probe_ex2_scalar_results_per_cta_iter / results_per_ptx;
  const std::uint64_t sass_per_ptx = static_cast<std::uint64_t>(
      row.sass_mufu_ex2_per_ptx_instruction_model);
  const std::uint64_t control_exp_sass_thread_ops = checked_multiply(
      row.expected_control_ex2_ptx_instructions_per_cta_iter, sass_per_ptx,
      "expected control SASS EX2 thread instructions");
  const std::uint64_t treatment_exp_sass_thread_ops = checked_multiply(
      row.expected_treatment_ex2_ptx_instructions_per_cta_iter, sass_per_ptx,
      "expected treatment SASS EX2 thread instructions");
  const std::uint64_t probe_exp_sass_thread_ops = checked_multiply(
      row.expected_probe_ex2_ptx_instructions_per_cta_iter, sass_per_ptx,
      "expected probe SASS EX2 thread instructions");
  const std::uint64_t reciprocal_warp_instructions =
      ceil_div(reciprocal_thread_ops, 32);
  // S=128/256 f16x2 uses one even-lane leader per adjacent lane pair.
  // CUDA 13.2 lowers the packed PTX operation to two scalar F16 MUFU
  // instructions, so each active warp issues two instructions for every
  // logical base/probe pass even though only 16 lanes are predicated on.
  const bool packed_lane_pair_path =
      options.exp_implementation == ExpImplementation::ptx_f16x2 &&
      cols <= kThreadsPerBlock;
  const std::uint64_t exp_warp_thread_divisor =
      packed_lane_pair_path ? 16 : 32;
  row.expected_control_xu_thread_ops_per_cta_iter =
      control_exp_sass_thread_ops + reciprocal_thread_ops;
  row.expected_treatment_xu_thread_ops_per_cta_iter =
      treatment_exp_sass_thread_ops + reciprocal_thread_ops;
  row.expected_probe_xu_thread_ops_per_cta_iter =
      probe_exp_sass_thread_ops;
  row.expected_control_xu_warp_instructions_per_cta_iter =
      ceil_div(control_exp_sass_thread_ops, exp_warp_thread_divisor) +
      reciprocal_warp_instructions;
  row.expected_treatment_xu_warp_instructions_per_cta_iter =
      ceil_div(treatment_exp_sass_thread_ops, exp_warp_thread_divisor) +
      reciprocal_warp_instructions;
  row.expected_probe_xu_warp_instructions_per_cta_iter =
      ceil_div(probe_exp_sass_thread_ops, exp_warp_thread_divisor);
  if (row.xu_documented_results_per_sm_cycle > 0) {
    const std::uint64_t capacity = static_cast<std::uint64_t>(
        row.xu_documented_results_per_sm_cycle);
    row.ideal_control_xu_cycles_per_cta_iter = ceil_div(
        row.expected_control_xu_thread_ops_per_cta_iter, capacity);
    row.ideal_treatment_xu_cycles_per_cta_iter = ceil_div(
        row.expected_treatment_xu_thread_ops_per_cta_iter, capacity);
    row.ideal_probe_xu_cycles_per_cta_iter = ceil_div(
        row.expected_probe_xu_thread_ops_per_cta_iter, capacity);
  }
  row.sfu_regime_evidence_status = is_native_f16_ex2(options.exp_implementation)
      ? (options.target_profile == "a100"
             ? "not_established_native_f16_requires_sm80_runtime_ncu"
             : "not_established_native_f16_requires_sm86_runtime_ncu")
      : (options.target_profile == "a100"
             ? "not_established_requires_sm80_ncu_and_108_216_cta_resource_sidecar"
             : "not_established");
  row.cache_condition = to_string(options.cache_condition);
  row.cache_policy = to_string(options.cache_policy);
  row.logical_input_bytes = row.n_elements * sizeof(half);
  row.logical_output_bytes = row.n_elements * sizeof(half);
  row.working_set_bytes = state.working_set_bytes;
  row.runtime_l2_bytes = state.prop.l2CacheSize;
  // A bracket reuses allocations and context, but each role's compiled kernel
  // can have different register pressure.  Report its own occupancy metadata.
  row.occupancy_max_blocks_per_sm = query_softmax_occupancy_max_blocks_per_sm(
      options.mode, options.softmax_cols, options.cache_policy,
      options.exp_implementation);
  row.occupancy_gate_pass =
      row.occupancy_max_blocks_per_sm >= row.grid_nominal_ctas_per_sm;
  row.static_single_wave_capacity_blocks = checked_multiply(
      static_cast<std::uint64_t>(state.prop.multiProcessorCount),
      static_cast<std::uint64_t>(row.occupancy_max_blocks_per_sm),
      "role static single-wave CTA capacity");
  row.static_single_wave_capacity_gate_pass =
      state.grid_blocks <= row.static_single_wave_capacity_blocks;
  row.smid_histogram_ok = measurement.smid.ok;
  row.smid_all_blocks_observed = measurement.smid.all_blocks_observed;
  row.smid_unique = measurement.smid.unique_sms;
  row.smid_total_blocks = measurement.smid.total_blocks;
  row.smid_max_blocks_on_sm = measurement.smid.max_blocks_on_sm;
  row.smid_coverage_fraction = state.prop.multiProcessorCount > 0
                                   ? static_cast<double>(row.smid_unique) /
                                         state.prop.multiProcessorCount
                                   : std::numeric_limits<double>::quiet_NaN();
  row.smid_assignment_max_blocks_per_sm = measurement.smid.max_blocks_on_sm;
  row.smid_set = measurement.smid.smid_set;
  row.smid_histogram = measurement.smid.histogram;
  row.idle_elapsed_s = idle.elapsed_s;
  row.idle_delta_E_J = idle.delta_j;
  row.idle_power_W = idle.power_w;
  row.elapsed_s = measurement.elapsed_s;
  row.measurement_start_epoch_ms = measurement.start_epoch_ms;
  row.measurement_end_epoch_ms = measurement.end_epoch_ms;
  row.E_before_mJ = measurement.before.energy_mj;
  row.E_after_mJ = measurement.after.energy_mj;
  row.endpoint_delta_E_J = measurement.endpoint_delta_j;
  row.delta_E_J = measurement.delta_j;
  row.energy_trace_sample_count =
      static_cast<int>(measurement.energy_trace.size());
  row.energy_trace_update_count = measurement.energy_trace_update_count;
  row.energy_trace_fit_point_count = measurement.energy_trace_fit_point_count;
  row.energy_trace_update_interval_p99_s =
      measurement.energy_trace_update_interval_p99_s;
  row.energy_trace_guard_s = measurement.energy_trace_guard_s;
  row.energy_trace_fit_span_s = measurement.energy_trace_fit_span_s;
  row.energy_trace_power_W = measurement.energy_trace_power_w;
  row.energy_trace_r2 = measurement.energy_trace_r2;
  row.energy_trace_rmse_mJ = measurement.energy_trace_rmse_mj;
  row.energy_trace_max_query_latency_s =
      measurement.energy_trace_max_query_latency_s;
  row.energy_trace_status = measurement.energy_trace_status;
  row.idle_baseline_J = idle.power_w * measurement.elapsed_s;
  row.net_E_J = row.delta_E_J - row.idle_baseline_J;
  row.full_net_pJ_per_element = row.n_elements > 0
                                     ? row.net_E_J * 1.0e12 / row.n_elements
                                     : std::numeric_limits<double>::quiet_NaN();
  row.clock_sm_before_mhz = measurement.before.sm_clock_mhz;
  row.clock_sm_after_mhz = measurement.after.sm_clock_mhz;
  row.clock_mem_before_mhz = measurement.before.mem_clock_mhz;
  row.clock_mem_after_mhz = measurement.after.mem_clock_mhz;
  row.temp_before_C = measurement.before.temp_c;
  row.temp_after_C = measurement.after.temp_c;
  row.profile_name = options.target_profile;
  row.compute_capability = std::to_string(state.prop.major) + "." +
                           std::to_string(state.prop.minor);
  row.gpu_name = state.prop.name;
  row.nvml_total_energy_supported =
      measurement.before.energy_counter_supported && measurement.after.energy_counter_supported;
  row.energy_source = "nvml_total_energy";
  if (measurement.energy_trace_status == "pass") {
    row.energy_integration_method =
        "nvml_total_energy_interior_theil_sen_rate_x_cuda_elapsed";
  } else if (measurement.energy_trace_status == "disabled_endpoint_only") {
    row.energy_integration_method =
        "nvml_total_energy_endpoint_delta_trace_disabled";
  } else {
    row.energy_integration_method =
        "nvml_total_energy_endpoint_delta_trace_gate_failed";
  }
  row.measurement_scope =
      options.measurement_purpose == "energy_atc"
          ? "gpu_device_total_energy_counter"
          : "resource_sidecar_energy_excluded";
  row.numerical_check_id = options.numerical_check_id;
  row.binary_sha256 = options.binary_sha256;
  std::ostringstream notes;
  notes << "softmax_harness_revision=operand_rate_atc_v6_native_ex2;"
        << "input_generator=splitmix64_uniform_fp16_v1;"
        << "logit_scale=" << options.logit_scale << ";"
        << "streaming="
        << (options.cache_condition == CacheCondition::streaming_large_ws ? 1 : 0)
        << ";row_mapping=block_base_plus_iter_stride_mod_tiles;"
        << "tile_cycle_complete="
        << (std::gcd(state.tile_stride, state.row_tiles_per_block) == 1 ? 1 : 0)
        << ";runtime_l2_bytes=" << state.prop.l2CacheSize << ";"
        << "occupancy_gate_pass=" << (row.occupancy_gate_pass ? 1 : 0) << ";"
        << "smid_histogram_ok=" << (row.smid_histogram_ok ? 1 : 0) << ";"
        << "grid_blocks_source=" << row.grid_blocks_source << ";"
        << "grid_experiment_purpose=" << row.grid_experiment_purpose << ";"
        << "cuda_pci_bus_id=" << row.cuda_pci_bus_id << ";"
        << "cuda_binary_arch=" << row.cuda_binary_arch << ";"
        << "exp_impl=" << row.exp_impl << ";"
        << "exp_input_dtype=" << row.exp_input_dtype << ";"
        << "exp_ptx_instruction=" << row.exp_ptx_instruction << ";"
        << "exp_results_per_ptx_instruction="
        << row.exp_results_per_ptx_instruction << ";"
        << "sass_mufu_ex2_per_ptx_instruction_model="
        << row.sass_mufu_ex2_per_ptx_instruction_model << ";"
        << "special_function_path=" << row.special_function_path << ";"
        << "sfu_regime_evidence_status="
        << row.sfu_regime_evidence_status << ";"
        << "measurement_purpose=" << options.measurement_purpose << ";"
        << "sm_residency_claim=none_kernel_entry_assignment_only;"
        << "static_single_wave_capacity_blocks="
        << row.static_single_wave_capacity_blocks << ";"
        << "smid_all_blocks_observed=" << (row.smid_all_blocks_observed ? 1 : 0)
        << ";"
        << "smid_assignment_is_not_concurrent_residency;"
        << "execution_model=" << row.execution_model << ";"
        << "bracket_context_id=" << row.bracket_context_id << ";"
        << "idle_baseline_scope=" << row.idle_baseline_scope << ";"
        << "preceding_role_gap_s=" << row.preceding_role_gap_s << ";"
        << "preceding_counter_gap_delta_J="
        << row.preceding_counter_gap_delta_J << ";"
        << "extra_exp_probe=" << (row.extra_exp_probe ? 1 : 0) << ";"
        << "energy_trace_status=" << row.energy_trace_status << ";"
        << "exp_sass_gate=not_run;"
        << "ncu_path_gate=not_run;"
        << measurement.before.notes << measurement.after.notes;
  row.notes = notes.str();
  return row;
}

SoftmaxMode bracket_control_mode(const Options& options) {
  if (options.bracket_control == "linear") return SoftmaxMode::linear_control;
  if (options.bracket_control == "io") return SoftmaxMode::io_control;
  return SoftmaxMode::full;
}

std::string bracket_role_name(const Options& options, bool before) {
  return options.bracket_control + (before ? "_before" : "_after");
}

bool inverted_probe_pair(const Options& options, int pair) {
  if (options.bracket_order != "counterbalanced6" || pair < 0) return false;
  // Three adjacent matched orientation blocks: F-R, R-F, F-R.  This makes
  // treatment state and middle position separately identifiable without a
  // second CTA sweep.
  constexpr bool kInverted[6] = {false, true, true, false, false, true};
  return kInverted[pair];
}

std::string bracket_context_id() {
  return "pid_" + std::to_string(static_cast<long long>(::getpid())) +
         "_started_" + std::to_string(epoch_milliseconds());
}

Options make_bracket_role_options(const Options& options,
                                  SoftmaxMode control_mode,
                                  const std::string& pair_id, int pair,
                                  int sequence_index) {
  Options role_options = options;
  const bool probe_contrast = options.bracket_control == "probe";
  const bool inverted_probe =
      probe_contrast && inverted_probe_pair(options, pair);
  const bool treatment = inverted_probe ? sequence_index != 1
                                        : sequence_index == 1;
  role_options.mode = probe_contrast
                          ? SoftmaxMode::full
                          : (treatment ? SoftmaxMode::full : control_mode);
  role_options.extra_exp_probe = probe_contrast && treatment;
  role_options.pair_id = pair_id;
  if (inverted_probe) {
    role_options.role = sequence_index == 0
                            ? "full_before"
                            : (sequence_index == 1 ? "probe_middle"
                                                   : "full_after");
  } else {
    role_options.role = treatment
                            ? "full"
                            : bracket_role_name(options, sequence_index == 0);
  }
  role_options.repeat_index = pair;
  role_options.sequence_index = sequence_index;
  return role_options;
}

std::string csv_escape_local(const std::string& value) {
  if (value.find_first_of(",\"\n\r") == std::string::npos) return value;
  std::string escaped = "\"";
  for (char character : value) {
    if (character == '"') escaped += '"';
    escaped += character;
  }
  escaped += '"';
  return escaped;
}

void write_energy_trace_csv(const std::string& path,
                            const std::vector<PendingEnergyTrace>& pending) {
  if (path.empty() || pending.empty()) return;
  const std::filesystem::path output_path(path);
  if (!output_path.parent_path().empty()) {
    std::filesystem::create_directories(output_path.parent_path());
  }
  constexpr const char* kHeader =
      "run_id,pair_id,role,repeat,sequence_index,sample_index,query_start_s,"
      "query_end_s,query_midpoint_s,query_latency_s,"
      "relative_to_kernel_start_s,energy_mJ,changed_from_previous,in_fit_window";
  const bool emit_header = !std::filesystem::exists(output_path) ||
                           std::filesystem::file_size(output_path) == 0;
  if (!emit_header) {
    std::ifstream input(output_path);
    std::string actual_header;
    std::getline(input, actual_header);
    if (actual_header != kHeader) {
      throw std::runtime_error(
          "energy trace CSV schema differs from this binary; select a new output path");
    }
  }
  std::ofstream output(output_path, std::ios::app);
  if (!output) {
    throw std::runtime_error("unable to open energy trace CSV: " +
                             output_path.string());
  }
  if (emit_header) output << kHeader << '\n';
  output << std::setprecision(12);
  for (const auto& entry : pending) {
    const double kernel_start_s = steady_seconds(entry.measurement.kernel_start);
    for (std::size_t index = 0; index < entry.measurement.energy_trace.size(); ++index) {
      const auto& point = entry.measurement.energy_trace[index];
      const bool changed = index > 0 &&
          point.energy_mj != entry.measurement.energy_trace[index - 1].energy_mj;
      const bool in_fit_window =
          entry.measurement.energy_trace_fit_end_s >
              entry.measurement.energy_trace_fit_start_s &&
          point.timestamp_s >= entry.measurement.energy_trace_fit_start_s &&
          point.timestamp_s <= entry.measurement.energy_trace_fit_end_s;
      output << csv_escape_local(entry.row.run_id) << ','
             << csv_escape_local(entry.row.pair_id) << ','
             << csv_escape_local(entry.row.role) << ',' << entry.row.repeat << ','
             << entry.row.sequence_index << ',' << index << ','
             << point.query_start_s << ',' << point.query_end_s << ','
             << point.timestamp_s << ',' << point.query_latency_s << ','
             << point.timestamp_s - kernel_start_s << ',' << point.energy_mj << ','
             << (changed ? "true" : "false") << ','
             << (in_fit_window ? "true" : "false") << '\n';
    }
  }
}

void run_persistent_bracket(const Options& options, const DeviceState& state,
                            a100fp16::NvmlEnergy& nvml,
                            const IterCalibration& calibration,
                            SoftmaxCsvWriter& writer) {
  const std::string context_id = bracket_context_id();
  const SoftmaxMode control_mode = bracket_control_mode(options);
  std::vector<PendingEnergyTrace> pending;
  pending.reserve(static_cast<std::size_t>(options.bracket_pairs) * 3);
  const IdleMeasurement batch_idle =
      options.bracket_idle_policy == "batch_once"
          ? measure_idle(nvml, state, options.idle_measure_seconds)
          : IdleMeasurement{};

  for (int warmup_pair = 0; warmup_pair < options.bracket_warmup_pairs;
       ++warmup_pair) {
    for (int sequence_index = 0; sequence_index < 3; ++sequence_index) {
      const Options warmup_options = make_bracket_role_options(
          options, control_mode, "warmup", warmup_pair, sequence_index);
      launch_and_time(warmup_options, state, calibration.resolved_iters, false);
    }
  }
  if (options.bracket_warmup_pairs > 0) {
    std::cout << "unrecorded_bracket_warmup_pairs="
              << options.bracket_warmup_pairs << "\n";
  }

  Clock::time_point previous_kernel_end{};
  std::uint64_t previous_counter_after_mj = 0;
  bool have_previous_kernel = false;
  for (int pair = 0; pair < options.bracket_pairs; ++pair) {
    const std::string pair_id = options.pair_prefix + "_p" +
        (pair < 10 ? "0" : "") + std::to_string(pair);
    const IdleMeasurement pair_idle =
        options.bracket_idle_policy == "pair_once"
            ? measure_idle(nvml, state, options.idle_measure_seconds)
            : IdleMeasurement{};
    for (int sequence_index = 0; sequence_index < 3; ++sequence_index) {
      const Options role_options = make_bracket_role_options(
          options, control_mode, pair_id, pair, sequence_index);
      const IdleMeasurement idle =
          options.bracket_idle_policy == "batch_once"
              ? batch_idle
              : (options.bracket_idle_policy == "pair_once"
                     ? pair_idle
                     : measure_idle(nvml, state,
                                    options.idle_measure_seconds));
      KernelMeasurement measurement =
          measure_kernel(role_options, state, nvml, calibration.resolved_iters);
      BracketMetadata bracket;
      bracket.execution_model = options.bracket_order == "counterbalanced6"
                                    ? "persistent_cuda_context_bracket_v3_counterbalanced6"
                                    : "persistent_cuda_context_bracket_v2";
      bracket.context_id = context_id;
      bracket.idle_baseline_scope = options.bracket_idle_policy;
      bracket.preceding_role_gap_s = have_previous_kernel
                                         ? elapsed_seconds(previous_kernel_end,
                                                           measurement.kernel_start)
                                         : -1.0;
      bracket.preceding_counter_gap_delta_j =
          have_previous_kernel &&
                  measurement.before.energy_mj >= previous_counter_after_mj
              ? static_cast<double>(measurement.before.energy_mj -
                                    previous_counter_after_mj) /
                    1000.0
              : -1.0;
      SoftmaxResultRow row = make_result_row(
          role_options, state, idle, measurement, calibration.resolved_iters, pair, bracket);
      previous_kernel_end = measurement.kernel_end;
      previous_counter_after_mj = measurement.after.energy_mj;
      have_previous_kernel = true;
      pending.push_back(PendingEnergyTrace{std::move(row), std::move(measurement)});
    }
  }
  for (const auto& entry : pending) {
    writer.write(entry.row);
    std::cout << "run_id=" << entry.row.run_id << " mode=" << entry.row.mode
              << " pair_id=" << entry.row.pair_id << " role=" << entry.row.role
              << " extra_exp_probe=" << (entry.row.extra_exp_probe ? 1 : 0)
              << " ITER=" << entry.row.ITER
              << " elapsed_s=" << entry.row.elapsed_s
              << " gap_s=" << entry.row.preceding_role_gap_s
              << " trace_power_W=" << entry.row.energy_trace_power_W
              << " trace_status=" << entry.row.energy_trace_status
              << " delta_E_J=" << entry.row.delta_E_J
              << " net_E_J=" << entry.row.net_E_J
              << " smid_ok=" << (entry.row.smid_histogram_ok ? 1 : 0) << "\n";
  }
  write_energy_trace_csv(options.energy_trace_output, pending);
}

void print_dry_run(const Options& options, const DeviceState& state) {
  const ExpPathMetadata exp_metadata =
      exp_path_metadata(options.exp_implementation, state.prop.major);
  const std::uint64_t control_results =
      static_cast<std::uint64_t>(options.softmax_cols);
  const std::uint64_t treatment_results = 2 * control_results;
  const std::uint64_t probe_results = control_results;
  const std::uint64_t results_per_ptx = static_cast<std::uint64_t>(
      exp_metadata.results_per_ptx_instruction);
  const std::uint64_t sass_per_ptx = static_cast<std::uint64_t>(
      exp_metadata.sass_mufu_per_ptx_instruction_model);
  const std::uint64_t control_ptx = control_results / results_per_ptx;
  const std::uint64_t treatment_ptx = treatment_results / results_per_ptx;
  const std::uint64_t probe_ptx = probe_results / results_per_ptx;
  const std::uint64_t reciprocal_thread_ops =
      std::min<std::uint64_t>(control_results, kThreadsPerBlock);
  const std::uint64_t control_xu =
      control_ptx * sass_per_ptx + reciprocal_thread_ops;
  const std::uint64_t treatment_xu =
      treatment_ptx * sass_per_ptx + reciprocal_thread_ops;
  const std::uint64_t probe_xu = probe_ptx * sass_per_ptx;
  std::cout << "gpu_name=" << state.prop.name << "\n"
            << "compute_capability=" << state.prop.major << "." << state.prop.minor
            << "\n"
            << "cuda_pci_bus_id=" << state.cuda_pci_bus_id << "\n"
            << "cuda_binary_arch=" << state.cuda_binary_arch << "\n"
            << "runtime_sm_count=" << state.prop.multiProcessorCount << "\n"
            << "runtime_l2_bytes=" << state.prop.l2CacheSize << "\n"
            << "grid_blocks=" << state.grid_blocks << "\n"
            << "grid_blocks_source="
            << (state.explicit_grid_blocks ? "explicit" : "runtime_sm_x_nominal_blocks_per_sm")
            << "\n"
            << "row_tiles_per_block=" << state.row_tiles_per_block << "\n"
            << "tile_stride=" << state.tile_stride << "\n"
            << "working_set_bytes=" << state.working_set_bytes << "\n"
            << "exp_impl=" << to_string(options.exp_implementation) << "\n"
            << "exp_input_dtype=" << exp_metadata.exp_input_dtype << "\n"
            << "special_function_path=" << exp_metadata.special_function_path
            << "\n"
            << "exp_ptx_instruction=" << exp_metadata.ptx_instruction << "\n"
            << "exp_results_per_ptx_instruction="
            << exp_metadata.results_per_ptx_instruction << "\n"
            << "sass_mufu_ex2_per_ptx_instruction_model="
            << exp_metadata.sass_mufu_per_ptx_instruction_model << "\n"
            << "sass_lowering_model_status="
            << exp_metadata.sass_lowering_model_status << "\n"
            << "expected_control_ex2_scalar_results_per_cta_iter="
            << control_results << "\n"
            << "expected_treatment_ex2_scalar_results_per_cta_iter="
            << treatment_results << "\n"
            << "expected_probe_ex2_scalar_results_per_cta_iter="
            << probe_results << "\n"
            << "expected_control_ex2_ptx_instructions_per_cta_iter="
            << control_ptx << "\n"
            << "expected_treatment_ex2_ptx_instructions_per_cta_iter="
            << treatment_ptx << "\n"
            << "expected_probe_ex2_ptx_instructions_per_cta_iter="
            << probe_ptx << "\n"
            << "xu_documented_results_per_sm_cycle="
            << exp_metadata.documented_results_per_sm_cycle << "\n"
            << "expected_control_xu_thread_ops_per_cta_iter="
            << control_xu << "\n"
            << "expected_treatment_xu_thread_ops_per_cta_iter="
            << treatment_xu << "\n"
            << "expected_probe_xu_thread_ops_per_cta_iter="
            << probe_xu << "\n"
            << "ideal_control_xu_cycles_per_cta_iter="
            << (exp_metadata.documented_results_per_sm_cycle > 0
                    ? ceil_div(control_xu, static_cast<std::uint64_t>(
                                              exp_metadata.documented_results_per_sm_cycle))
                    : 0)
            << "\n"
            << "ideal_treatment_xu_cycles_per_cta_iter="
            << (exp_metadata.documented_results_per_sm_cycle > 0
                    ? ceil_div(treatment_xu, static_cast<std::uint64_t>(
                                                exp_metadata.documented_results_per_sm_cycle))
                    : 0)
            << "\n"
            << "ideal_probe_xu_cycles_per_cta_iter="
            << (exp_metadata.documented_results_per_sm_cycle > 0
                    ? ceil_div(probe_xu, static_cast<std::uint64_t>(
                                            exp_metadata.documented_results_per_sm_cycle))
                    : 0)
            << "\n"
            << "measurement_purpose=" << options.measurement_purpose << "\n"
            << "occupancy_max_blocks_per_sm=" << state.occupancy_max_blocks_per_sm
            << "\n"
            << "static_single_wave_capacity_blocks="
            << state.static_single_wave_capacity_blocks << "\n"
            << "static_single_wave_capacity_gate_pass="
            << (state.grid_blocks <= state.static_single_wave_capacity_blocks ? 1 : 0)
            << "\n"
            << "occupancy_gate_pass="
            << (state.occupancy_max_blocks_per_sm >=
                        static_cast<int>(ceil_div(
                            state.grid_blocks,
                            static_cast<std::uint64_t>(state.prop.multiProcessorCount)))
                    ? 1
                    : 0)
            << "\n"
            << "smid_sparse_id_self_check=pass"
            << "\n";
}

int run(const Options& options) {
  require_sparse_smid_self_check();
  DeviceState state = create_device_state(options);
  try {
    print_dry_run(options, state);
    if (options.dry_run) {
      destroy_device_state(state);
      return 0;
    }
    if (options.validate_only) {
      verify_numerics(options, state);
      verify_native_ex2_all_encodings(options, state);
      destroy_device_state(state);
      return 0;
    }
    const IterCalibration calibration = calibrate_iters(options, state);
    if (options.calibrate_only) {
      std::cout << "calibrated_iters=" << calibration.resolved_iters
                << " trial_iters=" << calibration.trial_iters
                << " trial_elapsed_s=" << calibration.trial_elapsed_s << "\n";
      destroy_device_state(state);
      return 0;
    }
    a100fp16::NvmlEnergy nvml;
    SoftmaxCsvWriter writer(options.output);
    if (options.bracket_pairs > 0) {
      run_persistent_bracket(options, state, nvml, calibration, writer);
      destroy_device_state(state);
      return 0;
    }
    const BracketMetadata standalone{
        "standalone_cuda_context_v1", bracket_context_id(), "per_role", -1.0};
    std::vector<PendingEnergyTrace> pending;
    pending.reserve(static_cast<std::size_t>(options.repeats));
    for (int repeat = 0; repeat < options.repeats; ++repeat) {
      const IdleMeasurement idle =
          measure_idle(nvml, state, options.idle_measure_seconds);
      KernelMeasurement measurement =
          measure_kernel(options, state, nvml, calibration.resolved_iters);
      SoftmaxResultRow row = make_result_row(
          options, state, idle, measurement, calibration.resolved_iters, repeat,
          standalone);
      pending.push_back(PendingEnergyTrace{std::move(row), std::move(measurement)});
    }
    for (const auto& entry : pending) {
      writer.write(entry.row);
      std::cout << "run_id=" << entry.row.run_id << " mode=" << entry.row.mode
                << " extra_exp_probe=" << (entry.row.extra_exp_probe ? 1 : 0)
                << " ITER=" << entry.row.ITER
                << " elapsed_s=" << entry.row.elapsed_s
                << " trace_power_W=" << entry.row.energy_trace_power_W
                << " trace_status=" << entry.row.energy_trace_status
                << " delta_E_J=" << entry.row.delta_E_J
                << " net_E_J=" << entry.row.net_E_J
                << " smid_ok=" << (entry.row.smid_histogram_ok ? 1 : 0)
                << "\n";
    }
    write_energy_trace_csv(options.energy_trace_output, pending);
    destroy_device_state(state);
    return 0;
  } catch (...) {
    destroy_device_state(state);
    throw;
  }
}

}  // namespace
}  // namespace fp16softmax

int main(int argc, char** argv) {
  try {
    return fp16softmax::run(fp16softmax::parse_options(argc, argv));
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
