#include "softmax_whole_precision_result_writer.hpp"

#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace fp16softmax::whole_precision {
namespace {

std::string csv_escape(const std::string& value) {
  if (value.find_first_of(",\"\n\r") == std::string::npos) return value;
  std::string escaped{"\""};
  for (const char character : value) {
    if (character == '\"') escaped += '\"';
    escaped += character;
  }
  escaped += '\"';
  return escaped;
}

bool needs_header(const std::filesystem::path& path) {
  return !std::filesystem::exists(path) || std::filesystem::file_size(path) == 0;
}

const char* header() {
  return "schema_version,experiment_kind,protocol_revision,design_id,stage_group,"
         "session_order,run_id,session_id,schedule_id,schedule_block,sequence_index,"
         "policy,role,input_dtype,output_dtype,"
         "exp_stage,reduction_stage,normalization_stage,policy_description,"
         "gpu_id,gpu_name,compute_capability,cuda_pci_bus_id,cuda_binary_arch,"
         "runtime_sm_count,occupancy_max_blocks_per_sm,smid_unique,"
         "smid_total_blocks,smid_max_blocks_on_sm,smid_histogram_ok,"
         "grid_blocks,rows_per_block,softmax_cols,logit_scale,seed,iters,logical_input_elements,"
         "logical_output_elements,physical_input_bytes,physical_output_bytes,"
         "elapsed_s,ns_per_output_element,gelement_per_s,idle_elapsed_s,"
         "idle_delta_E_J,idle_power_W,preheat_requested_s,preheat_actual_s,preheat_policy,"
         "conditioning_mode,conditioning_policy,conditioning_requested_s,"
         "conditioning_actual_s,preparation_order,preparation_policy_order,"
         "validation_before_conditioning,calibration_before_conditioning,"
         "conditioning_calibration,premeasurement_schedule_warmup,"
         "E_before_mJ,E_after_mJ,endpoint_delta_E_J,"
         "delta_E_J,net_E_J,gross_pJ_per_output_element,"
         "net_pJ_per_output_element,energy_trace_sample_count,"
         "energy_trace_update_count,energy_trace_fit_point_count,"
         "energy_trace_power_W,energy_trace_r2,energy_trace_rmse_mJ,"
         "energy_trace_max_query_latency_s,energy_trace_status,energy_source,"
         "measurement_scope,"
         "clock_sm_before_mhz,clock_sm_after_mhz,temp_before_C,temp_after_C,"
         "validation_id,validation_max_abs_error,validation_max_row_sum_error,"
         "validation_max_abs_gate,validation_max_row_sum_gate,validation_pass,"
         "validation_nonfinite_count,validation_underflow_count,binary_sha256,notes";
}

void verify_header(const std::filesystem::path& path) {
  if (needs_header(path)) return;
  std::ifstream input(path);
  std::string actual;
  std::getline(input, actual);
  if (actual != header()) {
    throw std::runtime_error(
        "whole-precision output CSV schema differs; select a new output path");
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
  if (!emit_header) verify_header(path_);
  std::ofstream output(path_, std::ios::app);
  if (!output) {
    throw std::runtime_error("unable to open whole-precision CSV: " +
                             path_.string());
  }
  if (emit_header) output << header() << '\n';
  output << std::setprecision(12)
         << csv_escape(row.schema_version) << ','
         << csv_escape(row.experiment_kind) << ','
         << csv_escape(row.protocol_revision) << ',' << csv_escape(row.design_id)
         << ',' << csv_escape(row.stage_group) << ','
         << csv_escape(row.session_order) << ',' << csv_escape(row.run_id)
         << ',' << csv_escape(row.session_id) << ','
         << csv_escape(row.schedule_id) << ',' << row.schedule_block << ','
         << row.sequence_index << ',' << csv_escape(row.policy) << ','
         << csv_escape(row.role) << ',' << csv_escape(row.input_dtype) << ','
         << csv_escape(row.output_dtype) << ',' << csv_escape(row.exp_stage)
         << ',' << csv_escape(row.reduction_stage) << ','
         << csv_escape(row.normalization_stage) << ','
         << csv_escape(row.policy_description) << ',' << row.gpu_id << ','
         << csv_escape(row.gpu_name) << ','
         << csv_escape(row.compute_capability) << ','
         << csv_escape(row.cuda_pci_bus_id) << ',' << row.cuda_binary_arch
         << ',' << row.runtime_sm_count << ','
         << row.occupancy_max_blocks_per_sm << ',' << row.smid_unique << ','
         << row.smid_total_blocks << ',' << row.smid_max_blocks_on_sm << ','
         << (row.smid_histogram_ok ? "true" : "false") << ','
         << row.grid_blocks << ',' << row.rows_per_block << ','
         << row.softmax_cols << ',' << row.logit_scale << ',' << row.seed << ','
         << row.iters << ','
         << row.logical_input_elements << ',' << row.logical_output_elements
         << ',' << row.physical_input_bytes << ',' << row.physical_output_bytes
         << ',' << row.elapsed_s << ',' << row.ns_per_output_element << ','
         << row.gelement_per_s << ',' << row.idle_elapsed_s << ','
         << row.idle_delta_E_J << ',' << row.idle_power_W << ','
         << row.preheat_requested_s << ',' << row.preheat_actual_s << ','
         << csv_escape(row.preheat_policy) << ','
         << csv_escape(row.conditioning_mode) << ','
         << csv_escape(row.conditioning_policy) << ','
         << row.conditioning_requested_s << ',' << row.conditioning_actual_s << ','
         << csv_escape(row.preparation_order) << ','
         << csv_escape(row.preparation_policy_order) << ','
         << (row.validation_before_conditioning ? "true" : "false") << ','
         << (row.calibration_before_conditioning ? "true" : "false") << ','
         << csv_escape(row.conditioning_calibration) << ','
         << csv_escape(row.premeasurement_schedule_warmup) << ','
         << row.E_before_mJ << ','
         << row.E_after_mJ << ','
         << row.endpoint_delta_E_J << ',' << row.delta_E_J << ','
         << row.net_E_J << ',' << row.gross_pJ_per_output_element << ','
         << row.net_pJ_per_output_element << ','
         << row.energy_trace_sample_count << ','
         << row.energy_trace_update_count << ','
         << row.energy_trace_fit_point_count << ','
         << row.energy_trace_power_W << ',' << row.energy_trace_r2 << ','
         << row.energy_trace_rmse_mJ << ','
         << row.energy_trace_max_query_latency_s << ','
         << csv_escape(row.energy_trace_status) << ','
         << csv_escape(row.energy_source) << ','
         << csv_escape(row.measurement_scope) << ','
         << row.clock_sm_before_mhz << ',' << row.clock_sm_after_mhz << ','
         << row.temp_before_C << ',' << row.temp_after_C << ','
         << csv_escape(row.validation_id) << ','
         << row.validation_max_abs_error << ','
         << row.validation_max_row_sum_error << ','
         << row.validation_max_abs_gate << ','
         << row.validation_max_row_sum_gate << ','
         << (row.validation_pass ? "true" : "false") << ','
         << row.validation_nonfinite_count << ','
         << row.validation_underflow_count << ','
         << csv_escape(row.binary_sha256) << ',' << csv_escape(row.notes)
         << '\n';
}

}  // namespace fp16softmax::whole_precision
