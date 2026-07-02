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
           "smid_histogram_ok,clock_sm_mhz,clock_mem_mhz,temp_C,"
           "profile_name,architecture_family,chip,compute_capability,sm_count,"
           "l2_mib,shared_kib_per_sm,tensor_modes,energy_source,"
           "energy_integration_method,nvml_total_energy_supported,"
           "nvml_power_usage_semantics,nvml_field_power_instant_supported,"
           "nvml_field_power_average_supported,power_before_mw,power_after_mw,"
           "power_sample_count,power_sample_period_ms,driver_version,"
           "nvml_version,notes\n";
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
      << ',' << csv_escape(row.profile_name)
      << ',' << csv_escape(row.architecture_family)
      << ',' << csv_escape(row.chip)
      << ',' << csv_escape(row.compute_capability)
      << ',' << row.sm_count << ',' << row.l2_mib << ','
      << row.shared_kib_per_sm << ',' << csv_escape(row.tensor_modes) << ','
      << csv_escape(row.energy_source) << ','
      << csv_escape(row.energy_integration_method) << ','
      << (row.nvml_total_energy_supported ? "true" : "false") << ','
      << csv_escape(row.nvml_power_usage_semantics) << ','
      << (row.nvml_field_power_instant_supported ? "true" : "false") << ','
      << (row.nvml_field_power_average_supported ? "true" : "false") << ','
      << row.power_before_mw << ',' << row.power_after_mw << ','
      << row.power_sample_count << ',' << row.power_sample_period_ms << ','
      << csv_escape(row.driver_version) << ','
      << csv_escape(row.nvml_version)
      << ',' << csv_escape(row.notes) << '\n';
}

}  // namespace a100fp16
