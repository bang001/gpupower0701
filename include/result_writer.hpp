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
  double pJ_per_FLOP = 0.0;
  double pJ_per_input_bit = 0.0;
  std::uint64_t ncu_tensor_inst = 0;
  std::uint64_t ncu_shared_bytes = 0;
  std::uint64_t ncu_l2_bytes = 0;
  std::uint64_t ncu_dram_bytes = 0;
  std::uint64_t ncu_spill_bytes = 0;
  bool smid_histogram_ok = false;
  unsigned int clock_sm_mhz = 0;
  unsigned int clock_mem_mhz = 0;
  unsigned int temp_C = 0;
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
