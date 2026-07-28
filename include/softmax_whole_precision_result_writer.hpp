#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace fp16softmax::whole_precision {

struct ResultRow {
  std::string schema_version = "softmax_whole_precision_v2";
  std::string experiment_kind = "whole_softmax_precision";
  std::string protocol_revision = "whole_softmax_precision_stage_isolation_v1";
  std::string design_id;
  std::string stage_group;
  std::string session_order;
  std::string run_id;
  std::string session_id;
  std::string schedule_id;
  int schedule_block = -1;
  int sequence_index = -1;
  std::string policy;
  std::string role;
  std::string input_dtype;
  std::string output_dtype;
  std::string exp_stage;
  std::string reduction_stage;
  std::string normalization_stage;
  std::string policy_description;
  int gpu_id = -1;
  std::string gpu_name;
  std::string compute_capability;
  std::string cuda_pci_bus_id;
  int cuda_binary_arch = 0;
  int runtime_sm_count = 0;
  int occupancy_max_blocks_per_sm = 0;
  int smid_unique = 0;
  int smid_total_blocks = 0;
  int smid_max_blocks_on_sm = 0;
  bool smid_histogram_ok = false;
  std::uint64_t grid_blocks = 0;
  int rows_per_block = 0;
  int softmax_cols = 0;
  int threads_per_block = 0;
  int elements_per_thread = 0;
  std::string packed_elementwise_mapping;
  std::uint64_t static_single_wave_capacity_blocks = 0;
  double grid_nominal_ctas_per_sm = 0.0;
  double grid_sm_coverage = 0.0;
  bool static_single_wave_capacity_gate_pass = false;
  std::string range_phase;
  std::string coordinate_id;
  double requested_sm_coverage = 0.0;
  float logit_scale = 0.0f;
  std::uint64_t seed = 0;
  std::uint64_t iters = 0;
  std::uint64_t logical_input_elements = 0;
  std::uint64_t logical_output_elements = 0;
  std::uint64_t physical_input_bytes = 0;
  std::uint64_t physical_output_bytes = 0;
  double elapsed_s = 0.0;
  double ns_per_output_element = 0.0;
  double gelement_per_s = 0.0;
  double idle_elapsed_s = 0.0;
  double idle_delta_E_J = 0.0;
  double idle_power_W = 0.0;
  double preheat_requested_s = 0.0;
  double preheat_actual_s = 0.0;
  std::string preheat_policy;
  // These fields make the pre-measurement state auditable.  The historical
  // stage-isolation flow leaves them at its legacy values; the targeted
  // confirmation flow requires the canonical-common contract below.
  std::string conditioning_mode = "legacy_stage_isolation_v1";
  std::string conditioning_policy;
  double conditioning_requested_s = 0.0;
  double conditioning_actual_s = 0.0;
  std::string preparation_order;
  std::string preparation_policy_order;
  bool validation_before_conditioning = false;
  bool calibration_before_conditioning = false;
  std::string conditioning_calibration;
  std::string premeasurement_schedule_warmup;
  std::uint64_t E_before_mJ = 0;
  std::uint64_t E_after_mJ = 0;
  double endpoint_delta_E_J = 0.0;
  double delta_E_J = 0.0;
  double net_E_J = 0.0;
  double gross_pJ_per_output_element = 0.0;
  double net_pJ_per_output_element = 0.0;
  int energy_trace_sample_count = 0;
  int energy_trace_update_count = 0;
  int energy_trace_fit_point_count = 0;
  double energy_trace_power_W = 0.0;
  double energy_trace_r2 = 0.0;
  double energy_trace_rmse_mJ = 0.0;
  double energy_trace_max_query_latency_s = 0.0;
  std::string energy_trace_status;
  std::string energy_source;
  std::string measurement_scope;
  unsigned int clock_sm_before_mhz = 0;
  unsigned int clock_sm_after_mhz = 0;
  unsigned int temp_before_C = 0;
  unsigned int temp_after_C = 0;
  std::string validation_id;
  double validation_max_abs_error = 0.0;
  double validation_max_row_sum_error = 0.0;
  double validation_max_abs_gate = 0.0;
  double validation_max_row_sum_gate = 0.0;
  bool validation_pass = false;
  std::uint64_t validation_nonfinite_count = 0;
  std::uint64_t validation_underflow_count = 0;
  std::string binary_sha256;
  std::string notes;
};

class CsvWriter {
 public:
  explicit CsvWriter(std::filesystem::path path);
  void write(const ResultRow& row);

 private:
  std::filesystem::path path_;
};

}  // namespace fp16softmax::whole_precision
