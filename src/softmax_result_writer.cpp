#include "softmax_result_writer.hpp"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace fp16softmax {
namespace {

std::string csv_escape(const std::string& value) {
  bool quoted = false;
  for (char character : value) {
    if (character == ',' || character == '"' || character == '\n' ||
        character == '\r') {
      quoted = true;
      break;
    }
  }
  if (!quoted) return value;
  std::string result{"\""};
  for (char character : value) {
    if (character == '"') result += '"';
    result += character;
  }
  result += '"';
  return result;
}

bool needs_header(const std::filesystem::path& path) {
  return !std::filesystem::exists(path) || std::filesystem::file_size(path) == 0;
}

const char* header() {
  return "run_id,pair_id,role,repeat,sequence_index,execution_model,"
         "bracket_context_id,idle_baseline_scope,preceding_role_gap_s,"
         "preceding_counter_gap_delta_J,gpu_id,cuda_pci_bus_id,cuda_binary_arch,"
         "mode,extra_exp_probe,"
         "operand_delta_per_element,softmax_cols,"
         "threads_per_block,rows_per_block,row_tiles_per_block,tile_stride,"
         "elements_per_thread,active_SM,runtime_sm_count,blocks_per_sm,"
         "grid_nominal_ctas_per_sm,grid_blocks,grid_blocks_source,"
         "sm_residency_claim,grid_experiment_purpose,ITER,n_rows_allocated,"
         "n_elements,scalar_convention_ops,"
         "softmax_high_level_ops,input_dtype,output_dtype,compute_dtype,exp_impl,"
         "exp_input_dtype,special_function_path,exp_ptx_instruction,"
         "exp_results_per_ptx_instruction,"
         "sass_mufu_ex2_per_ptx_instruction_model,sass_lowering_model_status,"
         "expected_control_ex2_scalar_results_per_cta_iter,"
         "expected_treatment_ex2_scalar_results_per_cta_iter,"
         "expected_probe_ex2_scalar_results_per_cta_iter,"
         "expected_control_ex2_ptx_instructions_per_cta_iter,"
         "expected_treatment_ex2_ptx_instructions_per_cta_iter,"
         "expected_probe_ex2_ptx_instructions_per_cta_iter,"
         "xu_documented_results_per_sm_cycle,"
         "expected_control_xu_thread_ops_per_cta_iter,"
         "expected_treatment_xu_thread_ops_per_cta_iter,"
         "expected_probe_xu_thread_ops_per_cta_iter,"
         "expected_control_xu_warp_instructions_per_cta_iter,"
         "expected_treatment_xu_warp_instructions_per_cta_iter,"
         "expected_probe_xu_warp_instructions_per_cta_iter,"
         "ideal_control_xu_cycles_per_cta_iter,"
         "ideal_treatment_xu_cycles_per_cta_iter,"
         "ideal_probe_xu_cycles_per_cta_iter,sfu_regime_evidence_status,"
         "cache_condition,cache_policy,logical_input_bytes,logical_output_bytes,"
         "working_set_bytes,runtime_l2_bytes,occupancy_max_blocks_per_sm,"
         "occupancy_gate_pass,static_single_wave_capacity_blocks,"
         "static_single_wave_capacity_gate_pass,smid_histogram_ok,"
         "smid_all_blocks_observed,smid_unique,smid_total_blocks,"
         "smid_max_blocks_on_sm,smid_coverage_fraction,"
         "smid_assignment_max_blocks_per_sm,smid_set,smid_histogram,"
         "idle_elapsed_s,idle_delta_E_J,idle_power_W,"
         "elapsed_s,measurement_start_epoch_ms,measurement_end_epoch_ms,"
         "E_before_mJ,E_after_mJ,endpoint_delta_E_J,delta_E_J,"
         "energy_trace_sample_count,energy_trace_update_count,"
         "energy_trace_fit_point_count,energy_trace_update_interval_p99_s,"
         "energy_trace_guard_s,energy_trace_fit_span_s,energy_trace_power_W,"
         "energy_trace_r2,energy_trace_rmse_mJ,energy_trace_max_query_latency_s,"
         "energy_trace_status,idle_baseline_J,net_E_J,"
         "full_net_pJ_per_element,clock_sm_before_mhz,clock_sm_after_mhz,"
         "clock_mem_before_mhz,clock_mem_after_mhz,temp_before_C,temp_after_C,"
         "profile_name,compute_capability,gpu_name,energy_source,"
         "energy_integration_method,measurement_scope,nvml_total_energy_supported,"
         "numerical_check_id,binary_sha256,notes";
}

void verify_header(const std::filesystem::path& path) {
  if (needs_header(path)) return;
  std::ifstream input(path);
  std::string actual;
  std::getline(input, actual);
  if (actual != header()) {
    throw std::runtime_error(
        "softmax output CSV schema differs from this binary; select a new output path");
  }
}

}  // namespace

SoftmaxCsvWriter::SoftmaxCsvWriter(std::filesystem::path path)
    : path_(std::move(path)) {
  if (!path_.parent_path().empty()) {
    std::filesystem::create_directories(path_.parent_path());
  }
}

void SoftmaxCsvWriter::write(const SoftmaxResultRow& row) {
  const bool emit_header = needs_header(path_);
  if (!emit_header) verify_header(path_);
  std::ofstream output(path_, std::ios::app);
  if (!output) {
    throw std::runtime_error("unable to open softmax CSV: " + path_.string());
  }
  if (emit_header) output << header() << '\n';

  output << std::setprecision(12) << csv_escape(row.run_id) << ','
         << csv_escape(row.pair_id) << ',' << csv_escape(row.role) << ','
         << row.repeat << ',' << row.sequence_index << ','
         << csv_escape(row.execution_model) << ','
         << csv_escape(row.bracket_context_id) << ','
         << csv_escape(row.idle_baseline_scope) << ','
         << row.preceding_role_gap_s << ','
         << row.preceding_counter_gap_delta_J << ',' << row.gpu_id << ','
         << csv_escape(row.cuda_pci_bus_id) << ',' << row.cuda_binary_arch << ','
         << csv_escape(row.mode) << ','
         << (row.extra_exp_probe ? "true" : "false") << ','
         << row.operand_delta_per_element << ',' << row.softmax_cols << ','
         << row.threads_per_block << ',' << row.rows_per_block << ','
         << row.row_tiles_per_block << ',' << row.tile_stride << ','
         << row.elements_per_thread << ',' << row.active_sm << ','
         << row.runtime_sm_count << ',' << row.blocks_per_sm << ','
         << row.grid_nominal_ctas_per_sm << ','
         << row.grid_blocks << ',' << csv_escape(row.grid_blocks_source) << ','
         << csv_escape(row.sm_residency_claim) << ','
         << csv_escape(row.grid_experiment_purpose) << ',' << row.ITER << ',' << row.n_rows_allocated
         << ',' << row.n_elements << ',' << row.scalar_convention_ops << ','
         << row.softmax_high_level_ops << ',' << csv_escape(row.input_dtype)
         << ',' << csv_escape(row.output_dtype) << ','
         << csv_escape(row.compute_dtype) << ',' << csv_escape(row.exp_impl)
         << ',' << csv_escape(row.exp_input_dtype) << ','
         << csv_escape(row.special_function_path) << ','
         << csv_escape(row.exp_ptx_instruction) << ','
         << row.exp_results_per_ptx_instruction << ','
         << row.sass_mufu_ex2_per_ptx_instruction_model << ','
         << csv_escape(row.sass_lowering_model_status) << ','
         << row.expected_control_ex2_scalar_results_per_cta_iter << ','
         << row.expected_treatment_ex2_scalar_results_per_cta_iter << ','
         << row.expected_probe_ex2_scalar_results_per_cta_iter << ','
         << row.expected_control_ex2_ptx_instructions_per_cta_iter << ','
         << row.expected_treatment_ex2_ptx_instructions_per_cta_iter << ','
         << row.expected_probe_ex2_ptx_instructions_per_cta_iter << ','
         << row.xu_documented_results_per_sm_cycle << ','
         << row.expected_control_xu_thread_ops_per_cta_iter << ','
         << row.expected_treatment_xu_thread_ops_per_cta_iter << ','
         << row.expected_probe_xu_thread_ops_per_cta_iter << ','
         << row.expected_control_xu_warp_instructions_per_cta_iter << ','
         << row.expected_treatment_xu_warp_instructions_per_cta_iter << ','
         << row.expected_probe_xu_warp_instructions_per_cta_iter << ','
         << row.ideal_control_xu_cycles_per_cta_iter << ','
         << row.ideal_treatment_xu_cycles_per_cta_iter << ','
         << row.ideal_probe_xu_cycles_per_cta_iter << ','
         << csv_escape(row.sfu_regime_evidence_status) << ','
         << csv_escape(row.cache_condition) << ','
         << csv_escape(row.cache_policy) << ',' << row.logical_input_bytes << ','
         << row.logical_output_bytes << ',' << row.working_set_bytes << ','
         << row.runtime_l2_bytes << ',' << row.occupancy_max_blocks_per_sm << ','
         << (row.occupancy_gate_pass ? "true" : "false") << ','
         << row.static_single_wave_capacity_blocks << ','
         << (row.static_single_wave_capacity_gate_pass ? "true" : "false") << ','
         << (row.smid_histogram_ok ? "true" : "false") << ','
         << (row.smid_all_blocks_observed ? "true" : "false") << ','
         << row.smid_unique << ',' << row.smid_total_blocks << ','
         << row.smid_max_blocks_on_sm << ',' << row.smid_coverage_fraction << ','
         << row.smid_assignment_max_blocks_per_sm << ','
         << csv_escape(row.smid_set) << ',' << csv_escape(row.smid_histogram) << ','
         << row.idle_elapsed_s << ','
         << row.idle_delta_E_J << ',' << row.idle_power_W << ',' << row.elapsed_s
         << ',' << row.measurement_start_epoch_ms << ','
         << row.measurement_end_epoch_ms << ',' << row.E_before_mJ << ','
         << row.E_after_mJ << ',' << row.endpoint_delta_E_J << ','
         << row.delta_E_J << ',' << row.energy_trace_sample_count << ','
         << row.energy_trace_update_count << ','
         << row.energy_trace_fit_point_count << ','
         << row.energy_trace_update_interval_p99_s << ','
         << row.energy_trace_guard_s << ',' << row.energy_trace_fit_span_s << ','
         << row.energy_trace_power_W << ',' << row.energy_trace_r2 << ','
         << row.energy_trace_rmse_mJ << ','
         << row.energy_trace_max_query_latency_s << ','
         << csv_escape(row.energy_trace_status) << ',' << row.idle_baseline_J
         << ',' << row.net_E_J << ',' << row.full_net_pJ_per_element << ','
         << row.clock_sm_before_mhz << ',' << row.clock_sm_after_mhz << ','
         << row.clock_mem_before_mhz << ',' << row.clock_mem_after_mhz << ','
         << row.temp_before_C << ',' << row.temp_after_C << ','
         << csv_escape(row.profile_name) << ','
         << csv_escape(row.compute_capability) << ',' << csv_escape(row.gpu_name)
         << ',' << csv_escape(row.energy_source) << ','
         << csv_escape(row.energy_integration_method) << ','
         << csv_escape(row.measurement_scope) << ','
         << (row.nvml_total_energy_supported ? "true" : "false") << ','
         << csv_escape(row.numerical_check_id) << ','
         << csv_escape(row.binary_sha256) << ',' << csv_escape(row.notes) << '\n';
}

}  // namespace fp16softmax
