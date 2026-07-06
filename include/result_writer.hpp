#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace a100fp16 {

struct ResultRow {
  std::string run_id;
  int gpu_id = -1;
  int n_gpu_active = 0;
  std::string mode;
  std::uint64_t W_SM_KiB = 0;
  int blocks_per_SM = 0;
  int threads_per_block = 32;
  int active_SM = 0;
  std::uint64_t ITER = 0;
  std::uint64_t sweeps = 0;
  double elapsed_s = 0.0;
  std::uint64_t E_before_mJ = 0;
  std::uint64_t E_after_mJ = 0;
  double delta_E_J = 0.0;
  double idle_baseline_J = 0.0;
  double net_E_J = 0.0;
  std::uint64_t N_MMA = 0;
  std::uint64_t FLOP = 0;
  std::uint64_t input_bits = 0;
  std::uint64_t w_block_bytes = 0;
  std::uint64_t tiles_per_block = 0;
  std::uint64_t reuse_factor = 1;
  std::uint64_t load_repeat = 1;
  std::uint64_t store_repeat = 1;
  std::uint64_t reg_payload_bytes_per_block = 0;
  std::uint64_t reg_payload_regs_per_thread = 0;
  std::uint64_t reg_payload_bytes_per_sm = 0;
  std::uint64_t expected_reg_pressure_ops = 0;
  std::uint64_t expected_reg_operand_ops = 0;
  std::uint64_t expected_shared_bytes = 0;
  std::uint64_t expected_l1_bytes = 0;
  std::uint64_t expected_l2_bytes = 0;
  std::uint64_t expected_dram_bytes = 0;
  std::uint64_t expected_store_bytes = 0;
  std::uint64_t expected_addr_ops = 0;
  double pJ_per_FLOP = 0.0;
  double pJ_per_input_bit = 0.0;
  std::uint64_t ncu_tensor_inst = 0;
  std::uint64_t ncu_shared_bytes = 0;
  std::uint64_t ncu_l1_bytes = 0;
  std::uint64_t ncu_l2_bytes = 0;
  std::uint64_t ncu_dram_bytes = 0;
  std::uint64_t ncu_spill_bytes = 0;
  bool smid_histogram_ok = false;
  unsigned int clock_sm_mhz = 0;
  unsigned int clock_mem_mhz = 0;
  unsigned int temp_C = 0;
  std::string profile_name;
  std::string architecture_family;
  std::string chip;
  std::string compute_capability;
  int sm_count = 0;
  int l2_mib = 0;
  int unified_l1_shared_kib_per_sm = 0;
  int shared_kib_per_sm = 0;
  std::string tensor_modes;
  std::string energy_source;
  std::string energy_integration_method;
  std::string mode_family;
  std::string denominator_level;
  bool nvml_total_energy_supported = false;
  std::string nvml_power_usage_semantics;
  bool nvml_field_power_instant_supported = false;
  bool nvml_field_power_average_supported = false;
  unsigned int power_before_mw = 0;
  unsigned int power_after_mw = 0;
  unsigned int power_sample_count = 0;
  double power_sample_period_ms = 0.0;
  std::string driver_version;
  std::string nvml_version;
  std::string notes;
};

class CsvWriter {
 public:
  explicit CsvWriter(std::filesystem::path path);
  void write(const ResultRow& row);

 private:
  std::filesystem::path path_;
};

}  // namespace a100fp16
