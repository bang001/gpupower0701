#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "config.hpp"
#include "kernels.cuh"
#include "nvml_energy.hpp"
#include "result_writer.hpp"

namespace a100fp16 {
namespace {

#define CUDA_CHECK(call)                                                        \
  do {                                                                          \
    cudaError_t status__ = (call);                                              \
    if (status__ != cudaSuccess) {                                              \
      std::ostringstream oss__;                                                 \
      oss__ << #call << " failed: " << cudaGetErrorString(status__);           \
      throw std::runtime_error(oss__.str());                                    \
    }                                                                           \
  } while (0)

using Clock = std::chrono::steady_clock;

struct Options {
  std::vector<int> gpu_list{0};
  Mode mode = Mode::reg_mma;
  std::uint64_t w_sm_kib = 1;
  int blocks_per_sm = 1;
  HardwareProfile profile = kDefaultHardwareProfile;
  std::string target_profile_arg = kDefaultHardwareProfile.name;
  bool target_profile_auto = false;
  bool active_sm_explicit = false;
  int active_sm = kDefaultHardwareProfile.full_sm_count;
  double seconds = 10.0;
  std::uint64_t iters = 0;
  std::uint64_t reuse_factor = 1;
  std::uint64_t load_repeat = 1;
  std::uint64_t store_repeat = 1;
  int repeats = 5;
  std::filesystem::path output = "results/raw/a100_fp16_energy_v2_raw.csv";
  bool verify_smid = true;
  bool dry_run = false;
};

struct DeviceState {
  int gpu_id = -1;
  int actual_sm = 0;
  cudaStream_t stream = nullptr;
  half* input = nullptr;
  std::size_t input_bytes = 0;
  std::size_t input_half_count = 0;
  float* output = nullptr;
  std::size_t output_float_count = 0;
  int* d_smid = nullptr;
  int* d_rank = nullptr;
  int* d_counts = nullptr;
  int sm_count_capacity = 512;
  std::string notes;
};

struct SmidCheck {
  bool ok = false;
  int unique_sms = 0;
  int total_blocks = 0;
  int max_blocks_on_sm = 0;
  std::string notes;
};

std::vector<int> parse_gpu_list(const std::string& value) {
  std::vector<int> out;
  if (value.empty() || value == "none" || value == "None" || value == "-") {
    return out;
  }
  std::stringstream ss(value);
  std::string item;
  while (std::getline(ss, item, ',')) {
    if (item.empty()) continue;
    out.push_back(std::stoi(item));
  }
  return out;
}

std::string join_ints(const std::vector<int>& values) {
  std::ostringstream oss;
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i) oss << ',';
    oss << values[i];
  }
  return oss.str();
}

bool contains_gpu(const std::vector<int>& gpus, int gpu) {
  return std::find(gpus.begin(), gpus.end(), gpu) != gpus.end();
}

void print_usage(const char* argv0) {
  std::cout
      << "Usage: " << argv0 << " --gpu-list 0[,1,2] --mode MODE [options]\n\n"
      << "Required/primary options:\n"
      << "  --gpu-list <list|none>       CUDA/NVML ids for active GPUs\n"
      << "  --mode idle|empty|reg_fragment_only|reg_operand_only|reg_mma|shared_load_only|shared_mma|l2_load_only|l2_mma|dram_load_only|dram_mma|store_only|store_path\n"
      << "  --w-sm-kib <int>             1..131072 power-of-two KiB sweep point\n"
      << "  --blocks-per-sm <int>        power-of-two up to target resident block limit\n"
      << "  --active-sm <int>            default target full SM count\n"
      << "  --target-profile <name>      auto, rtx3090, v100, a100, h100\n"
      << "  --seconds <float>            target measurement time, default 10\n"
      << "  --iters <int>                bypass calibration if nonzero\n"
      << "  --reuse-factor <int>         MMA repeats per iteration, default 1\n"
      << "  --load-repeat <int>          operand loads per iteration, default 1\n"
      << "  --store-repeat <int>         store writes per iteration for store modes, default 1\n"
      << "  --repeats <int>              default 5\n"
      << "  --output <csv>               default results/raw/a100_fp16_energy_v2_raw.csv\n"
      << "  --verify-smid 0|1            default 1\n"
      << "  --dry-run                    print feasibility and exit\n";
}

Options parse_args(int argc, char** argv) {
  Options opts;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto need_value = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) throw std::invalid_argument(name + " requires a value");
      return argv[++i];
    };

    if (arg == "--help" || arg == "-h") {
      print_usage(argv[0]);
      std::exit(0);
    } else if (arg == "--gpu-list") {
      opts.gpu_list = parse_gpu_list(need_value(arg));
    } else if (arg == "--mode") {
      opts.mode = mode_from_string(need_value(arg));
    } else if (arg == "--w-sm-kib") {
      opts.w_sm_kib = static_cast<std::uint64_t>(std::stoull(need_value(arg)));
    } else if (arg == "--blocks-per-sm") {
      opts.blocks_per_sm = std::stoi(need_value(arg));
    } else if (arg == "--target-profile") {
      opts.target_profile_arg = need_value(arg);
      if (opts.target_profile_arg == "auto") {
        opts.target_profile_auto = true;
      } else {
        opts.target_profile_auto = false;
        opts.profile = profile_from_string(opts.target_profile_arg);
        if (!opts.active_sm_explicit) opts.active_sm = opts.profile.full_sm_count;
      }
    } else if (arg == "--active-sm") {
      opts.active_sm = std::stoi(need_value(arg));
      opts.active_sm_explicit = true;
    } else if (arg == "--seconds") {
      opts.seconds = std::stod(need_value(arg));
    } else if (arg == "--iters") {
      opts.iters = static_cast<std::uint64_t>(std::stoull(need_value(arg)));
    } else if (arg == "--reuse-factor") {
      opts.reuse_factor =
          static_cast<std::uint64_t>(std::stoull(need_value(arg)));
    } else if (arg == "--load-repeat") {
      opts.load_repeat =
          static_cast<std::uint64_t>(std::stoull(need_value(arg)));
    } else if (arg == "--store-repeat") {
      opts.store_repeat =
          static_cast<std::uint64_t>(std::stoull(need_value(arg)));
    } else if (arg == "--repeats") {
      opts.repeats = std::stoi(need_value(arg));
    } else if (arg == "--output") {
      opts.output = need_value(arg);
    } else if (arg == "--verify-smid") {
      opts.verify_smid = std::stoi(need_value(arg)) != 0;
    } else if (arg == "--dry-run") {
      opts.dry_run = true;
    } else {
      throw std::invalid_argument("unknown argument: " + arg);
    }
  }

  if (opts.seconds <= 0.0) throw std::invalid_argument("--seconds must be > 0");
  if (opts.repeats <= 0) throw std::invalid_argument("--repeats must be > 0");
  if (opts.active_sm <= 0) throw std::invalid_argument("--active-sm must be > 0");
  if (opts.reuse_factor == 0) {
    throw std::invalid_argument("--reuse-factor must be > 0");
  }
  if (opts.load_repeat == 0) {
    throw std::invalid_argument("--load-repeat must be > 0");
  }
  if (opts.store_repeat == 0) {
    throw std::invalid_argument("--store-repeat must be > 0");
  }
  return opts;
}

int first_runtime_gpu(const Options& opts) {
  if (!opts.gpu_list.empty()) return opts.gpu_list.front();
  int count = 0;
  CUDA_CHECK(cudaGetDeviceCount(&count));
  if (count <= 0) {
    throw std::runtime_error("no CUDA devices available for --target-profile auto");
  }
  return 0;
}

void resolve_auto_profile(Options& opts) {
  if (!opts.target_profile_auto) return;
  const int gpu = first_runtime_gpu(opts);
  cudaDeviceProp prop{};
  CUDA_CHECK(cudaGetDeviceProperties(&prop, gpu));
  opts.profile =
      profile_from_compute_capability(prop.major, prop.minor, prop.name);
  if (!opts.active_sm_explicit) {
    opts.active_sm = prop.multiProcessorCount;
  }
}

std::string now_token() {
  const auto now = std::chrono::system_clock::now().time_since_epoch();
  return std::to_string(
      std::chrono::duration_cast<std::chrono::milliseconds>(now).count());
}

double elapsed_seconds(Clock::time_point start, Clock::time_point stop) {
  return std::chrono::duration<double>(stop - start).count();
}

void sleep_seconds(double seconds) {
  std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
}

std::uint64_t ceil_div(std::uint64_t a, std::uint64_t b) {
  return b == 0 ? 0 : ((a + b - 1) / b);
}

bool is_mma_mode(Mode mode) {
  return mode == Mode::reg_mma || mode == Mode::shared_mma ||
         mode == Mode::l2_mma || mode == Mode::dram_mma;
}

bool is_register_operand_mode(Mode mode) {
  return mode == Mode::reg_operand_only || mode == Mode::reg_mma;
}

bool is_shared_operand_mode(Mode mode) {
  return mode == Mode::shared_load_only || mode == Mode::shared_mma;
}

bool is_l2_operand_mode(Mode mode) {
  return mode == Mode::l2_load_only || mode == Mode::l2_mma;
}

bool is_dram_operand_mode(Mode mode) {
  return mode == Mode::dram_load_only || mode == Mode::dram_mma;
}

bool is_global_operand_mode(Mode mode) {
  return is_l2_operand_mode(mode) || is_dram_operand_mode(mode);
}

bool has_operand_loads(Mode mode) {
  return is_shared_operand_mode(mode) || is_global_operand_mode(mode);
}

bool has_final_matrix_store(Mode mode) {
  return mode == Mode::reg_fragment_only || mode == Mode::reg_operand_only ||
         mode == Mode::reg_mma || mode == Mode::shared_load_only ||
         mode == Mode::shared_mma || mode == Mode::l2_load_only ||
         mode == Mode::l2_mma || mode == Mode::dram_load_only ||
         mode == Mode::dram_mma;
}

bool is_store_loop_mode(Mode mode) {
  return mode == Mode::store_only || mode == Mode::store_path;
}

void print_dry_run(const Options& opts, const Feasibility& f, bool allowed,
                   const std::string& mode_reason) {
  std::cout << "dry_run=true\n";
  std::cout << "mode=" << to_string(opts.mode) << "\n";
  std::cout << "gpu_list=" << join_ints(opts.gpu_list) << "\n";
  std::cout << "target_profile=" << opts.profile.name << "\n";
  std::cout << "architecture_family=" << opts.profile.architecture_family
            << "\n";
  std::cout << "chip=" << opts.profile.chip << "\n";
  std::cout << "cuda_arch=" << opts.profile.cuda_arch << "\n";
  std::cout << "compute_capability=" << opts.profile.compute_major << "."
            << opts.profile.compute_minor << "\n";
  std::cout << "max_blocks_per_SM=" << opts.profile.max_blocks_per_sm << "\n";
  std::cout << "target_l2_MiB=" << opts.profile.l2_mib << "\n";
  std::cout << "target_shared_KiB_per_SM="
            << opts.profile.shared_capacity_per_sm_kib << "\n";
  std::cout << "target_max_shared_KiB_per_block="
            << opts.profile.max_shared_per_block_kib << "\n";
  std::cout << "nvml_power_usage_semantics="
            << opts.profile.nvml_power_usage_semantics << "\n";
  std::cout << "tensor_modes=" << opts.profile.tensor_modes << "\n";
  std::cout << "W_SM_KiB=" << opts.w_sm_kib << "\n";
  std::cout << "W_SM_label=" << w_sm_label(opts.w_sm_kib) << "\n";
  std::cout << "blocks_per_SM=" << opts.blocks_per_sm << "\n";
  std::cout << "threads_per_block=" << kThreadsPerBlock << "\n";
  std::cout << "active_SM=" << opts.active_sm << "\n";
  std::cout << "reuse_factor=" << opts.reuse_factor << "\n";
  std::cout << "load_repeat=" << opts.load_repeat << "\n";
  std::cout << "store_repeat=" << opts.store_repeat << "\n";
  std::cout << "valid_feasibility=" << (f.valid ? "true" : "false") << "\n";
  std::cout << "mode_allowed=" << (allowed ? "true" : "false") << "\n";
  std::cout << "regime=" << f.regime << "\n";
  std::cout << "shared_resident=" << (f.shared_resident ? "true" : "false")
            << "\n";
  std::cout << "l2_candidate=" << (f.l2_candidate ? "true" : "false")
            << "\n";
  std::cout << "dram_candidate=" << (f.dram_candidate ? "true" : "false")
            << "\n";
  std::cout << "reason=" << f.reason << "\n";
  if (!mode_reason.empty()) std::cout << "mode_reason=" << mode_reason << "\n";
  std::cout << "W_block_KiB=" << f.w_block_kib << "\n";
  std::cout << "tiles_per_block=" << f.tiles_per_block << "\n";
  std::cout << "full_gpu_working_set_MiB=" << f.full_gpu_working_set_mib
            << "\n";
}

std::vector<double> energy_delta_j(const std::vector<GpuEnergySample>& before,
                                   const std::vector<GpuEnergySample>& after) {
  std::vector<double> delta(before.size(), 0.0);
  for (std::size_t i = 0; i < before.size() && i < after.size(); ++i) {
    delta[i] =
        (static_cast<double>(after[i].energy_mj) -
         static_cast<double>(before[i].energy_mj)) /
        1000.0;
    if (!(before[i].energy_counter_supported &&
          after[i].energy_counter_supported)) {
      if (!(before[i].power_usage_supported && after[i].power_usage_supported)) {
        throw std::runtime_error(
            "NVML total energy and power usage are both unavailable");
      }
      const double dt = after[i].timestamp_s - before[i].timestamp_s;
      const double avg_power_w =
          (static_cast<double>(before[i].power_mw) +
           static_cast<double>(after[i].power_mw)) /
          2.0e3;
      delta[i] = std::max(0.0, dt * avg_power_w);
    }
  }
  return delta;
}

std::vector<double> measure_idle_baseline(NvmlEnergy& nvml, double seconds,
                                          double* elapsed_s) {
  const auto before = nvml.sample_all();
  const auto t0 = Clock::now();
  sleep_seconds(seconds);
  const auto t1 = Clock::now();
  const auto after = nvml.sample_all();
  if (elapsed_s) *elapsed_s = elapsed_seconds(t0, t1);
  return energy_delta_j(before, after);
}

void cleanup_device(DeviceState& state) {
  if (state.gpu_id >= 0) {
    cudaSetDevice(state.gpu_id);
  }
  if (state.input) cudaFree(state.input);
  if (state.output) cudaFree(state.output);
  if (state.d_smid) cudaFree(state.d_smid);
  if (state.d_rank) cudaFree(state.d_rank);
  if (state.d_counts) cudaFree(state.d_counts);
  if (state.stream) cudaStreamDestroy(state.stream);
  state = DeviceState{};
}

void cleanup_all(std::vector<DeviceState>& states) {
  for (auto& state : states) cleanup_device(state);
}

DeviceState setup_device(int gpu_id, const Options& opts,
                         const Feasibility& f) {
  DeviceState state;
  state.gpu_id = gpu_id;
  CUDA_CHECK(cudaSetDevice(gpu_id));

  cudaDeviceProp prop{};
  CUDA_CHECK(cudaGetDeviceProperties(&prop, gpu_id));
  state.actual_sm = prop.multiProcessorCount;
  if (opts.active_sm > state.actual_sm) {
    std::ostringstream oss;
    oss << "--active-sm " << opts.active_sm << " exceeds device " << gpu_id
        << " SM count " << state.actual_sm;
    throw std::runtime_error(oss.str());
  }
  if (!(prop.major == opts.profile.compute_major &&
        prop.minor == opts.profile.compute_minor)) {
    std::ostringstream oss;
    oss << "warning_target_cc_mismatch=device_" << prop.major << "."
        << prop.minor << "_target_" << opts.profile.compute_major << "."
        << opts.profile.compute_minor << ";";
    state.notes += oss.str();
  }
  {
    std::ostringstream oss;
    oss << "runtime_device_name=" << prop.name
        << ";runtime_compute_capability=" << prop.major << "." << prop.minor
        << ";runtime_sm_count=" << prop.multiProcessorCount
        << ";runtime_l2_bytes=" << prop.l2CacheSize
        << ";runtime_shared_mem_per_block_optin_bytes="
        << prop.sharedMemPerBlockOptin << ";";
    state.notes += oss.str();
  }

  CUDA_CHECK(cudaStreamCreateWithFlags(&state.stream, cudaStreamNonBlocking));

  const std::size_t grid_blocks =
      static_cast<std::size_t>(opts.active_sm) * opts.blocks_per_sm;
  state.output_float_count = std::max<std::size_t>(grid_blocks * 256ull, 1024);
  state.sm_count_capacity = std::max(512, state.actual_sm + 64);

  std::size_t requested_bytes =
      state.output_float_count * sizeof(float) +
      grid_blocks * sizeof(int) * 2ull +
      static_cast<std::size_t>(state.sm_count_capacity) * sizeof(int);

  if (is_global_operand_mode(opts.mode)) {
    state.input_bytes =
        static_cast<std::size_t>(opts.active_sm) *
        static_cast<std::size_t>(opts.w_sm_kib) * 1024ull;
    state.input_half_count = state.input_bytes / sizeof(half);
    requested_bytes += state.input_bytes;
  }

  std::size_t free_bytes = 0;
  std::size_t total_bytes = 0;
  CUDA_CHECK(cudaMemGetInfo(&free_bytes, &total_bytes));
  if (requested_bytes > static_cast<std::size_t>(0.90 * free_bytes)) {
    std::ostringstream oss;
    oss << "requested allocation " << requested_bytes
        << " bytes exceeds 90% of currently free memory " << free_bytes
        << " on gpu " << gpu_id;
    throw std::runtime_error(oss.str());
  }

  CUDA_CHECK(cudaMalloc(&state.output,
                        state.output_float_count * sizeof(float)));
  CUDA_CHECK(cudaMalloc(&state.d_smid, grid_blocks * sizeof(int)));
  CUDA_CHECK(cudaMalloc(&state.d_rank, grid_blocks * sizeof(int)));
  CUDA_CHECK(cudaMalloc(&state.d_counts,
                        state.sm_count_capacity * sizeof(int)));

  if (state.input_bytes > 0) {
    CUDA_CHECK(cudaMalloc(&state.input, state.input_bytes));
    CUDA_CHECK(launch_init_half(state.input, state.input_half_count,
                                static_cast<std::uint64_t>(gpu_id + 1) * 911ull,
                                state.stream));
    CUDA_CHECK(cudaStreamSynchronize(state.stream));
  }

  CUDA_CHECK(configure_kernel_attributes(opts.mode,
                                         static_cast<std::size_t>(f.w_block_bytes)));
  return state;
}

void reset_smid_buffers(const Options& opts, DeviceState& state) {
  const std::size_t grid_blocks =
      static_cast<std::size_t>(opts.active_sm) * opts.blocks_per_sm;
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  CUDA_CHECK(cudaMemsetAsync(state.d_counts, 0,
                             state.sm_count_capacity * sizeof(int),
                             state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.d_smid, 0xff, grid_blocks * sizeof(int),
                             state.stream));
  CUDA_CHECK(cudaMemsetAsync(state.d_rank, 0xff, grid_blocks * sizeof(int),
                             state.stream));
}

void warmup_global_inputs(const Options& opts,
                          std::vector<DeviceState>& states) {
  if (!is_global_operand_mode(opts.mode)) return;
  for (auto& state : states) {
    CUDA_CHECK(cudaSetDevice(state.gpu_id));
    CUDA_CHECK(launch_global_warmup(state.input, state.input_half_count,
                                    state.output, state.stream));
  }
  for (auto& state : states) {
    CUDA_CHECK(cudaSetDevice(state.gpu_id));
    CUDA_CHECK(cudaStreamSynchronize(state.stream));
  }
}

double launch_all(const Options& opts, const Feasibility& f,
                  std::vector<DeviceState>& states, std::uint64_t iters,
                  bool warmup_before_timing) {
  if (warmup_before_timing) {
    warmup_global_inputs(opts, states);
  }

  for (auto& state : states) reset_smid_buffers(opts, state);

  const auto t0 = Clock::now();
  for (auto& state : states) {
    CUDA_CHECK(cudaSetDevice(state.gpu_id));
    KernelLaunchConfig cfg;
    cfg.mode = opts.mode;
    cfg.active_sm = opts.active_sm;
    cfg.blocks_per_sm = opts.blocks_per_sm;
    cfg.w_block_bytes = f.w_block_bytes;
    cfg.tiles_per_block = f.tiles_per_block;
    cfg.iters = iters;
    cfg.reuse_factor = opts.reuse_factor;
    cfg.load_repeat = opts.load_repeat;
    cfg.store_repeat = opts.store_repeat;
    cfg.input = state.input;
    cfg.output = state.output;
    cfg.smid_by_block = state.d_smid;
    cfg.rank_by_block = state.d_rank;
    cfg.sm_counts = state.d_counts;
    cfg.sm_count_capacity = state.sm_count_capacity;
    cfg.stream = state.stream;
    CUDA_CHECK(launch_benchmark_kernel(cfg));
  }

  for (auto& state : states) {
    CUDA_CHECK(cudaSetDevice(state.gpu_id));
    CUDA_CHECK(cudaStreamSynchronize(state.stream));
  }
  const auto t1 = Clock::now();
  return elapsed_seconds(t0, t1);
}

std::uint64_t calibrate_iters(const Options& opts, const Feasibility& f,
                              std::vector<DeviceState>& states) {
  if (opts.iters != 0) return opts.iters;

  std::uint64_t trial_iters = 1024;
  double elapsed = 0.0;
  for (int attempt = 0; attempt < 10; ++attempt) {
    elapsed = launch_all(opts, f, states, trial_iters, true);
    if (elapsed >= 0.05) break;
    const double scale = elapsed > 1.0e-6 ? (0.05 / elapsed) : 64.0;
    const double bounded_scale = std::min(128.0, std::max(2.0, scale * 1.2));
    trial_iters = static_cast<std::uint64_t>(
        std::ceil(static_cast<double>(trial_iters) * bounded_scale));
    trial_iters = std::max<std::uint64_t>(trial_iters, 1);
  }

  if (elapsed <= 0.0) {
    throw std::runtime_error("calibration produced zero elapsed time");
  }
  std::uint64_t target_iters = static_cast<std::uint64_t>(
      std::ceil(static_cast<double>(trial_iters) * opts.seconds / elapsed *
                1.10));
  return std::max<std::uint64_t>(target_iters, 1);
}

SmidCheck check_smid_histogram(const Options& opts, DeviceState& state) {
  SmidCheck check;
  if (!opts.verify_smid) {
    check.notes = "smid_verification_disabled;";
    return check;
  }

  std::vector<int> counts(state.sm_count_capacity, 0);
  CUDA_CHECK(cudaSetDevice(state.gpu_id));
  CUDA_CHECK(cudaMemcpy(counts.data(), state.d_counts,
                        counts.size() * sizeof(int), cudaMemcpyDeviceToHost));

  int unique_sms = 0;
  int total_blocks = 0;
  int max_blocks = 0;
  bool ok = true;
  for (int count : counts) {
    if (count > 0) {
      ++unique_sms;
      total_blocks += count;
      max_blocks = std::max(max_blocks, count);
      if (count != opts.blocks_per_sm) ok = false;
    }
  }
  const int expected_blocks = opts.active_sm * opts.blocks_per_sm;
  if (unique_sms != opts.active_sm) ok = false;
  if (total_blocks != expected_blocks) ok = false;

  check.ok = ok;
  check.unique_sms = unique_sms;
  check.total_blocks = total_blocks;
  check.max_blocks_on_sm = max_blocks;
  std::ostringstream oss;
  oss << "smid_unique=" << unique_sms << ";smid_total_blocks=" << total_blocks
      << ";smid_max_blocks_on_sm=" << max_blocks << ";";
  check.notes = oss.str();
  return check;
}

ResultRow make_row(const Options& opts, const Feasibility& f,
                   const std::string& run_id, int gpu_id, int n_gpu_active,
                   bool gpu_active, const GpuEnergySample& before,
                   const GpuEnergySample& after, double elapsed_s,
                   double idle_baseline_j, double delta_j,
                   const SmidCheck& smid_check, std::uint64_t iters,
                   int actual_sm_count, const std::string& extra_notes) {
  ResultRow row;
  row.run_id = run_id;
  row.gpu_id = gpu_id;
  row.n_gpu_active = n_gpu_active;
  row.mode = to_string(opts.mode);
  row.W_SM_KiB = opts.w_sm_kib;
  row.blocks_per_SM = opts.blocks_per_sm;
  row.threads_per_block = kThreadsPerBlock;
  row.active_SM = opts.active_sm;
  row.ITER = iters;
  const std::uint64_t tile_loads_per_block =
      has_operand_loads(opts.mode) ? iters * opts.load_repeat : 0;
  row.sweeps =
      gpu_active && f.tiles_per_block > 0
          ? ceil_div(tile_loads_per_block, f.tiles_per_block)
          : 0;
  row.elapsed_s = elapsed_s;
  row.E_before_mJ = before.energy_mj;
  row.E_after_mJ = after.energy_mj;
  row.delta_E_J = delta_j;
  row.idle_baseline_J = idle_baseline_j;
  row.net_E_J = opts.mode == Mode::idle ? 0.0 : (delta_j - idle_baseline_j);
  row.w_block_bytes = f.w_block_bytes;
  row.tiles_per_block = f.tiles_per_block;
  row.reuse_factor = opts.reuse_factor;
  row.load_repeat = opts.load_repeat;
  row.store_repeat = opts.store_repeat;
  row.smid_histogram_ok = gpu_active && smid_check.ok;
  row.clock_sm_mhz = after.sm_clock_mhz;
  row.clock_mem_mhz = after.mem_clock_mhz;
  row.temp_C = after.temp_c;
  row.profile_name = opts.profile.name;
  row.architecture_family = opts.profile.architecture_family;
  row.chip = opts.profile.chip;
  if (after.compute_major > 0) {
    row.compute_capability =
        std::to_string(after.compute_major) + "." + std::to_string(after.compute_minor);
  } else {
    row.compute_capability =
        std::to_string(opts.profile.compute_major) + "." +
        std::to_string(opts.profile.compute_minor);
  }
  row.sm_count = actual_sm_count > 0 ? actual_sm_count : opts.profile.full_sm_count;
  row.l2_mib = opts.profile.l2_mib;
  row.shared_kib_per_sm = opts.profile.shared_capacity_per_sm_kib;
  row.tensor_modes = opts.profile.tensor_modes;
  row.nvml_total_energy_supported =
      before.energy_counter_supported && after.energy_counter_supported;
  row.energy_source =
      row.nvml_total_energy_supported ? "nvml_total_energy"
                                      : "legacy_get_power_usage_integral";
  row.energy_integration_method =
      row.nvml_total_energy_supported ? "total_energy_mj_delta"
                                      : "endpoint_power_trapezoid";
  row.nvml_power_usage_semantics = opts.profile.nvml_power_usage_semantics;
  row.nvml_field_power_instant_supported =
      before.field_power_instant_supported && after.field_power_instant_supported;
  row.nvml_field_power_average_supported =
      before.field_power_average_supported && after.field_power_average_supported;
  row.power_before_mw = before.power_mw;
  row.power_after_mw = after.power_mw;
  row.power_sample_count = row.nvml_total_energy_supported ? 0 : 2;
  row.power_sample_period_ms =
      row.nvml_total_energy_supported ? 0.0 : elapsed_s * 1000.0;
  row.driver_version = after.driver_version;
  row.nvml_version = after.nvml_version;

  const std::uint64_t active_blocks =
      static_cast<std::uint64_t>(opts.active_sm) *
      static_cast<std::uint64_t>(opts.blocks_per_sm);
  if (gpu_active && is_mma_mode(opts.mode)) {
    row.N_MMA = active_blocks * iters * opts.reuse_factor;
    row.FLOP = row.N_MMA * static_cast<std::uint64_t>(kLogicalMmaFlop);
    row.input_bits =
        row.N_MMA * static_cast<std::uint64_t>(kLogicalMmaInputBits);
    if (row.FLOP > 0) {
      row.pJ_per_FLOP = row.net_E_J * 1.0e12 / row.FLOP;
      row.pJ_per_input_bit = row.net_E_J * 1.0e12 / row.input_bits;
    }
  }
  if (gpu_active) {
    if (is_register_operand_mode(opts.mode)) {
      row.expected_reg_operand_ops =
          active_blocks * iters * opts.reuse_factor;
    }

    const std::uint64_t expected_operand_bytes =
        active_blocks * iters * opts.load_repeat *
        static_cast<std::uint64_t>(kLogicalMmaInputBytes);
    if (is_shared_operand_mode(opts.mode)) {
      row.expected_shared_bytes = expected_operand_bytes;
    } else if (is_l2_operand_mode(opts.mode)) {
      row.expected_l2_bytes = expected_operand_bytes;
    } else if (is_dram_operand_mode(opts.mode)) {
      row.expected_dram_bytes = expected_operand_bytes;
    }

    if (has_final_matrix_store(opts.mode)) {
      row.expected_store_bytes = active_blocks * 256ull * sizeof(float);
    } else if (is_store_loop_mode(opts.mode)) {
      row.expected_store_bytes =
          active_blocks * iters * opts.store_repeat * sizeof(float);
    } else if (opts.mode == Mode::empty) {
      row.expected_store_bytes = active_blocks * sizeof(float);
    }
  }

  std::ostringstream notes;
  notes << "regime=" << f.regime << ";feasibility_reason=" << f.reason
        << ";target_profile=" << opts.profile.name
        << ";architecture_family=" << opts.profile.architecture_family
        << ";chip=" << opts.profile.chip
        << ";target_full_sm=" << opts.profile.full_sm_count
        << ";target_l2_mib=" << opts.profile.l2_mib
        << ";target_shared_kib_per_sm="
        << opts.profile.shared_capacity_per_sm_kib
        << ";target_max_shared_kib_per_block="
        << opts.profile.max_shared_per_block_kib
        << ";nvml_power_usage_semantics="
        << opts.profile.nvml_power_usage_semantics
        << ";tensor_modes=" << opts.profile.tensor_modes
        << ";shared_resident=" << (f.shared_resident ? 1 : 0)
        << ";l2_candidate=" << (f.l2_candidate ? 1 : 0)
        << ";dram_candidate=" << (f.dram_candidate ? 1 : 0)
        << ";row_scope=per_gpu;"
        << "logical_op=warp_m16n16k16;"
        << "wmma_fallback=1;"
        << "reuse_factor=" << opts.reuse_factor
        << ";load_repeat=" << opts.load_repeat
        << ";store_repeat=" << opts.store_repeat
        << ";expected_reg_operand_ops=" << row.expected_reg_operand_ops
        << ";expected_shared_bytes=" << row.expected_shared_bytes
        << ";expected_l2_bytes=" << row.expected_l2_bytes
        << ";expected_dram_bytes=" << row.expected_dram_bytes
        << ";expected_store_bytes=" << row.expected_store_bytes << ";"
        << "gpu_active=" << (gpu_active ? 1 : 0) << ";";
  if (is_shared_operand_mode(opts.mode)) {
    notes << "shared_init_included=1;";
  }
  notes << before.notes << after.notes << smid_check.notes << extra_notes;
  row.notes = notes.str();
  return row;
}

void synchronize_active_devices(const std::vector<DeviceState>& states) {
  for (const auto& state : states) {
    CUDA_CHECK(cudaSetDevice(state.gpu_id));
    CUDA_CHECK(cudaDeviceSynchronize());
  }
}

int run_idle(const Options& opts, NvmlEnergy& nvml) {
  CsvWriter writer(opts.output);
  for (int repeat = 0; repeat < opts.repeats; ++repeat) {
    const auto before = nvml.sample_all();
    const auto t0 = Clock::now();
    sleep_seconds(opts.seconds);
    const auto t1 = Clock::now();
    const auto after = nvml.sample_all();
    const double elapsed = elapsed_seconds(t0, t1);
    const auto delta = energy_delta_j(before, after);
    const std::string run_id =
        "idle_" + now_token() + "_r" + std::to_string(repeat);

    Feasibility f =
        classify_feasibility(opts.w_sm_kib, opts.blocks_per_sm, opts.profile);
    for (int gpu = 0; gpu < nvml.device_count(); ++gpu) {
      const double delta_j = delta.at(gpu);
      SmidCheck smid;
      ResultRow row = make_row(opts, f, run_id, gpu, 0, false, before[gpu],
                               after[gpu], elapsed, delta_j, delta_j, smid, 0,
                               opts.profile.full_sm_count, "idle_measurement=1;");
      writer.write(row);
    }
  }
  return 0;
}

int run_benchmark(const Options& opts, const Feasibility& f, NvmlEnergy& nvml) {
  if (opts.gpu_list.empty()) {
    throw std::invalid_argument("--gpu-list must not be empty for non-idle modes");
  }

  int cuda_count = 0;
  CUDA_CHECK(cudaGetDeviceCount(&cuda_count));
  for (int gpu : opts.gpu_list) {
    if (gpu < 0 || gpu >= cuda_count) {
      throw std::out_of_range("CUDA gpu id out of range: " + std::to_string(gpu));
    }
    if (gpu >= nvml.device_count()) {
      throw std::out_of_range("NVML gpu id out of range: " + std::to_string(gpu));
    }
  }

  std::vector<DeviceState> states;
  states.reserve(opts.gpu_list.size());
  try {
    for (int gpu : opts.gpu_list) {
      states.push_back(setup_device(gpu, opts, f));
    }

    const std::uint64_t iters = calibrate_iters(opts, f, states);
    std::cerr << "ITER=" << iters << "\n";

    double idle_elapsed = 0.0;
    const auto idle_baseline = measure_idle_baseline(nvml, opts.seconds,
                                                     &idle_elapsed);
    CsvWriter writer(opts.output);

    for (int repeat = 0; repeat < opts.repeats; ++repeat) {
      warmup_global_inputs(opts, states);
      synchronize_active_devices(states);

      const auto before = nvml.sample_all();
      const double elapsed =
          launch_all(opts, f, states, iters, false);
      synchronize_active_devices(states);
      const auto after = nvml.sample_all();
      const auto delta = energy_delta_j(before, after);

      std::map<int, SmidCheck> smid_by_gpu;
      for (auto& state : states) {
        smid_by_gpu[state.gpu_id] = check_smid_histogram(opts, state);
      }

      const std::string run_id =
          to_string(opts.mode) + "_" + now_token() + "_r" +
          std::to_string(repeat);
      for (int gpu = 0; gpu < nvml.device_count(); ++gpu) {
        const bool active = contains_gpu(opts.gpu_list, gpu);
        const double baseline_scaled =
            idle_elapsed > 0.0 ? idle_baseline.at(gpu) * elapsed / idle_elapsed
                               : 0.0;
        SmidCheck smid;
        auto it = smid_by_gpu.find(gpu);
        if (it != smid_by_gpu.end()) smid = it->second;
        std::string extra;
        int actual_sm_count = opts.profile.full_sm_count;
        if (active) {
          auto state_it =
              std::find_if(states.begin(), states.end(),
                           [&](const DeviceState& s) { return s.gpu_id == gpu; });
          if (state_it != states.end()) {
            extra += state_it->notes;
            actual_sm_count = state_it->actual_sm;
          }
        }
        ResultRow row =
            make_row(opts, f, run_id, gpu, static_cast<int>(opts.gpu_list.size()),
                     active, before[gpu], after[gpu], elapsed, baseline_scaled,
                     delta.at(gpu), smid, iters, actual_sm_count, extra);
        writer.write(row);
      }
    }
  } catch (...) {
    cleanup_all(states);
    throw;
  }
  cleanup_all(states);
  return 0;
}

}  // namespace
}  // namespace a100fp16

int main(int argc, char** argv) {
  try {
    auto opts = a100fp16::parse_args(argc, argv);
    a100fp16::resolve_auto_profile(opts);
    const auto f =
        a100fp16::classify_feasibility(opts.w_sm_kib, opts.blocks_per_sm,
                                       opts.profile);
    std::string mode_reason;
    const bool allowed =
        a100fp16::mode_allowed_for_feasibility(opts.mode, f, &mode_reason);

    if (opts.dry_run) {
      a100fp16::print_dry_run(opts, f, allowed, mode_reason);
      return 0;
    }

    if (!allowed) {
      std::cerr << "invalid combination: " << mode_reason << "\n";
      return 2;
    }

    a100fp16::NvmlEnergy nvml;
    if (opts.mode == a100fp16::Mode::idle) {
      return a100fp16::run_idle(opts, nvml);
    }
    return a100fp16::run_benchmark(opts, f, nvml);
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
}
