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

std::string csv_header() {
  return "run_id,gpu_id,n_gpu_active,mode,W_SM_KiB,blocks_per_SM,"
         "threads_per_block,active_SM,ITER,sweeps,elapsed_s,E_before_mJ,"
         "E_after_mJ,delta_E_J,idle_baseline_J,net_E_J,N_MMA,FLOP,"
         "input_bits,w_block_bytes,tiles_per_block,reuse_factor,"
         "load_repeat,store_repeat,reg_payload_bytes_per_block,"
         "reg_payload_regs_per_thread,reg_payload_bytes_per_sm,"
         "expected_reg_pressure_ops,expected_reg_operand_ops,"
         "expected_shared_bytes,expected_l1_bytes,expected_l2_bytes,"
         "expected_dram_bytes,expected_store_bytes,expected_addr_ops,"
         "pJ_per_FLOP,pJ_per_input_bit,ncu_tensor_inst,ncu_shared_bytes,"
         "ncu_l1_bytes,ncu_l2_bytes,ncu_dram_bytes,ncu_spill_bytes,"
         "smid_histogram_ok,clock_sm_mhz,"
         "clock_mem_mhz,temp_C,profile_name,architecture_family,chip,"
         "compute_capability,sm_count,l2_mib,shared_kib_per_sm,tensor_modes,"
         "energy_source,energy_integration_method,mode_family,"
         "denominator_level,nvml_total_energy_supported,"
         "nvml_power_usage_semantics,nvml_field_power_instant_supported,"
         "nvml_field_power_average_supported,power_before_mw,power_after_mw,"
         "power_sample_count,power_sample_period_ms,driver_version,"
         "nvml_version,notes";
}

void check_existing_header(const std::filesystem::path& path,
                           const std::string& expected_header) {
  if (needs_header(path)) return;
  std::ifstream in(path);
  std::string actual_header;
  std::getline(in, actual_header);
  if (actual_header != expected_header) {
    throw std::runtime_error(
        "output CSV schema does not match current binary; use a new output path: " +
        path.string());
  }
}

}  // namespace

CsvWriter::CsvWriter(std::filesystem::path path) : path_(std::move(path)) {
  if (!path_.parent_path().empty()) {
    std::filesystem::create_directories(path_.parent_path());
  }
}

void CsvWriter::write(const ResultRow& row) {
  const bool emit_header = needs_header(path_);
  const std::string header = csv_header();
  if (!emit_header) {
    check_existing_header(path_, header);
  }
  std::ofstream out(path_, std::ios::app);
  if (!out) {
    throw std::runtime_error("failed to open output CSV: " + path_.string());
  }

  if (emit_header) {
    out << header << '\n';
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
      << row.input_bits << ',' << row.w_block_bytes << ','
      << row.tiles_per_block << ',' << row.reuse_factor << ','
      << row.load_repeat << ',' << row.store_repeat << ','
      << row.reg_payload_bytes_per_block << ','
      << row.reg_payload_regs_per_thread << ','
      << row.reg_payload_bytes_per_sm << ','
      << row.expected_reg_pressure_ops << ','
      << row.expected_reg_operand_ops << ','
      << row.expected_shared_bytes << ',' << row.expected_l1_bytes << ','
      << row.expected_l2_bytes << ','
      << row.expected_dram_bytes << ',' << row.expected_store_bytes << ','
      << row.expected_addr_ops << ',' << row.pJ_per_FLOP << ','
      << row.pJ_per_input_bit << ',' << row.ncu_tensor_inst << ','
      << row.ncu_shared_bytes << ',' << row.ncu_l1_bytes << ','
      << row.ncu_l2_bytes << ','
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
      << csv_escape(row.mode_family) << ','
      << csv_escape(row.denominator_level) << ','
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
