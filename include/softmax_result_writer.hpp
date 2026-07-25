#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace fp16softmax {

struct SoftmaxResultRow {
  std::string run_id;
  std::string pair_id;
  std::string role;
  int repeat = -1;
  int sequence_index = -1;
  // These fields make a persistent C->F->C bracket auditable instead of
  // relying on an inference from adjacent timestamps.
  std::string execution_model;
  std::string bracket_context_id;
  std::string idle_baseline_scope;
  double preceding_role_gap_s = -1.0;
  double preceding_counter_gap_delta_J = -1.0;
  int gpu_id = -1;
  std::string cuda_pci_bus_id;
  int cuda_binary_arch = 0;
  std::string mode;
  bool extra_exp_probe = false;
  std::uint64_t operand_delta_per_element = 0;
  int softmax_cols = 0;
  int threads_per_block = 0;
  int rows_per_block = 1;
  std::uint64_t row_tiles_per_block = 1;
  std::uint64_t tile_stride = 1;
  int elements_per_thread = 0;
  int active_sm = 0;
  int runtime_sm_count = 0;
  int blocks_per_sm = 0;
  int grid_nominal_ctas_per_sm = 0;
  std::uint64_t grid_blocks = 0;
  std::string grid_blocks_source;
  std::string sm_residency_claim;
  std::string grid_experiment_purpose;
  std::uint64_t ITER = 0;
  std::uint64_t n_rows_allocated = 0;
  std::uint64_t n_elements = 0;
  std::uint64_t scalar_convention_ops = 0;
  std::uint64_t softmax_high_level_ops = 0;
  std::string input_dtype;
  std::string output_dtype;
  std::string compute_dtype;
  std::string exp_impl;
  std::string exp_input_dtype;
  std::string special_function_path;
  std::string exp_ptx_instruction;
  int exp_results_per_ptx_instruction = 0;
  int sass_mufu_ex2_per_ptx_instruction_model = 0;
  std::string sass_lowering_model_status;
  std::uint64_t expected_control_ex2_scalar_results_per_cta_iter = 0;
  std::uint64_t expected_treatment_ex2_scalar_results_per_cta_iter = 0;
  std::uint64_t expected_probe_ex2_scalar_results_per_cta_iter = 0;
  std::uint64_t expected_control_ex2_ptx_instructions_per_cta_iter = 0;
  std::uint64_t expected_treatment_ex2_ptx_instructions_per_cta_iter = 0;
  std::uint64_t expected_probe_ex2_ptx_instructions_per_cta_iter = 0;
  int xu_documented_results_per_sm_cycle = 0;
  std::uint64_t expected_control_xu_thread_ops_per_cta_iter = 0;
  std::uint64_t expected_treatment_xu_thread_ops_per_cta_iter = 0;
  std::uint64_t expected_probe_xu_thread_ops_per_cta_iter = 0;
  std::uint64_t expected_control_xu_warp_instructions_per_cta_iter = 0;
  std::uint64_t expected_treatment_xu_warp_instructions_per_cta_iter = 0;
  std::uint64_t expected_probe_xu_warp_instructions_per_cta_iter = 0;
  std::uint64_t ideal_control_xu_cycles_per_cta_iter = 0;
  std::uint64_t ideal_treatment_xu_cycles_per_cta_iter = 0;
  std::uint64_t ideal_probe_xu_cycles_per_cta_iter = 0;
  std::string sfu_regime_evidence_status;
  std::string cache_condition;
  std::string cache_policy;
  std::uint64_t logical_input_bytes = 0;
  std::uint64_t logical_output_bytes = 0;
  std::uint64_t working_set_bytes = 0;
  std::uint64_t runtime_l2_bytes = 0;
  int occupancy_max_blocks_per_sm = 0;
  bool occupancy_gate_pass = false;
  std::uint64_t static_single_wave_capacity_blocks = 0;
  bool static_single_wave_capacity_gate_pass = false;
  bool smid_histogram_ok = false;
  bool smid_all_blocks_observed = false;
  int smid_unique = 0;
  int smid_total_blocks = 0;
  int smid_max_blocks_on_sm = 0;
  double smid_coverage_fraction = 0.0;
  int smid_assignment_max_blocks_per_sm = 0;
  std::string smid_set;
  std::string smid_histogram;
  double idle_elapsed_s = 0.0;
  double idle_delta_E_J = 0.0;
  double idle_power_W = 0.0;
  double elapsed_s = 0.0;
  std::uint64_t measurement_start_epoch_ms = 0;
  std::uint64_t measurement_end_epoch_ms = 0;
  std::uint64_t E_before_mJ = 0;
  std::uint64_t E_after_mJ = 0;
  double endpoint_delta_E_J = 0.0;
  double delta_E_J = 0.0;
  int energy_trace_sample_count = 0;
  int energy_trace_update_count = 0;
  int energy_trace_fit_point_count = 0;
  double energy_trace_update_interval_p99_s = 0.0;
  double energy_trace_guard_s = 0.0;
  double energy_trace_fit_span_s = 0.0;
  double energy_trace_power_W = 0.0;
  double energy_trace_r2 = 0.0;
  double energy_trace_rmse_mJ = 0.0;
  double energy_trace_max_query_latency_s = 0.0;
  std::string energy_trace_status;
  double idle_baseline_J = 0.0;
  double net_E_J = 0.0;
  double full_net_pJ_per_element = 0.0;
  unsigned int clock_sm_before_mhz = 0;
  unsigned int clock_sm_after_mhz = 0;
  unsigned int clock_mem_before_mhz = 0;
  unsigned int clock_mem_after_mhz = 0;
  unsigned int temp_before_C = 0;
  unsigned int temp_after_C = 0;
  std::string profile_name;
  std::string compute_capability;
  std::string gpu_name;
  std::string energy_source;
  std::string energy_integration_method;
  std::string measurement_scope;
  bool nvml_total_energy_supported = false;
  std::string numerical_check_id;
  std::string binary_sha256;
  std::string notes;
};

class SoftmaxCsvWriter {
 public:
  explicit SoftmaxCsvWriter(std::filesystem::path path);
  void write(const SoftmaxResultRow& row);

 private:
  std::filesystem::path path_;
};

}  // namespace fp16softmax
