#include "result_writer.hpp"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace a100fp16 {
namespace {

std::string csv_escape(const std::string& value) {
  bool needs_quotes = false;
  for (char c : value) {
    if (c == ',' || c == '"' || c == '\n' || c == '\r') {
      needs_quotes = true;
      break;
    }
  }
  if (!needs_quotes) return value;
  std::string escaped = "\"";
  for (char c : value) {
    if (c == '"') escaped += '"';
    escaped += c;
  }
  escaped += '"';
  return escaped;
}

bool needs_header(const std::filesystem::path& path) {
  if (!std::filesystem::exists(path)) return true;
  return std::filesystem::file_size(path) == 0;
}

}  // namespace

CsvWriter::CsvWriter(std::filesystem::path path) : path_(std::move(path)) {
  if (!path_.parent_path().empty()) {
    std::filesystem::create_directories(path_.parent_path());
  }
}

void CsvWriter::write(const ResultRow& row) {
  const bool emit_header = needs_header(path_);
  std::ofstream out(path_, std::ios::app);
  if (!out) {
    throw std::runtime_error("failed to open output CSV: " + path_.string());
  }

  if (emit_header) {
    out << "run_id,gpu_id,n_gpu_active,mode,W_SM_KiB,blocks_per_SM,"
           "threads_per_block,active_SM,ITER,sweeps,elapsed_s,E_before_mJ,"
           "E_after_mJ,delta_E_J,idle_baseline_J,net_E_J,N_MMA,FLOP,"
           "input_bits,pJ_per_FLOP,pJ_per_input_bit,ncu_tensor_inst,"
           "ncu_shared_bytes,ncu_l2_bytes,ncu_dram_bytes,ncu_spill_bytes,"
           "smid_histogram_ok,clock_sm_mhz,clock_mem_mhz,temp_C,notes\n";
  }

  out << std::setprecision(12)
      << csv_escape(row.run_id) << ',' << row.gpu_id << ','
      << row.n_gpu_active << ',' << csv_escape(row.mode) << ','
      << row.W_SM_KiB << ',' << row.blocks_per_SM << ','
      << row.threads_per_block << ',' << row.active_SM << ',' << row.ITER
      << ',' << row.sweeps << ',' << row.elapsed_s << ','
      << row.E_before_mJ << ',' << row.E_after_mJ << ','
      << row.delta_E_J << ',' << row.idle_baseline_J << ','
      << row.net_E_J << ',' << row.N_MMA << ',' << row.FLOP << ','
      << row.input_bits << ',' << row.pJ_per_FLOP << ','
      << row.pJ_per_input_bit << ',' << row.ncu_tensor_inst << ','
      << row.ncu_shared_bytes << ',' << row.ncu_l2_bytes << ','
      << row.ncu_dram_bytes << ',' << row.ncu_spill_bytes << ','
      << (row.smid_histogram_ok ? "true" : "false") << ','
      << row.clock_sm_mhz << ',' << row.clock_mem_mhz << ',' << row.temp_C
      << ',' << csv_escape(row.notes) << '\n';
}

}  // namespace a100fp16
