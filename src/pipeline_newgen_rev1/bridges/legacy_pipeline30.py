from __future__ import annotations

from pathlib import Path
from typing import Dict


DEFAULT_LEGACY_ROOT_NAME = "nanum-pipeline-28-main"


LEGACY_PIPELINE30_ANCHORS: Dict[str, str] = {
    # --- Ported (kept for reference) ---
    # "load_text_config": "nanum_pipeline_30.py::load_pipeline29_config_bundle",
    # "sync_runtime_dirs": "nanum_pipeline_30.py::apply_runtime_path_overrides",
    # "show_runtime_preflight": "nanum_pipeline_30.py::_choose_runtime_preflight",
    # "run_time_diagnostics": "nanum_pipeline_30.py::build_time_diagnostics",
    # "build_final_table": "nanum_pipeline_29.py::build_final_table",
    # "export_excel": "nanum_pipeline_30.py::safe_to_excel",
    # "run_unitary_plots": "nanum_pipeline_30.py::make_plots_from_config_with_summary",
    # "run_compare_plots": "nanum_pipeline_29.py::iter_compare_plot_groups",
    # "run_compare_iteracoes": "nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv",
    # "run_special_load_plots": "nanum_pipeline_30.py::_plot_ethanol_equivalent_*",
    # --- Ported (sweep mode) ---
    # "convert_missing_open_files": "nanum_pipeline_30.py::_run_missing_open_conversion_batch",
    #     ^ Ported as show_runtime_preflight + adapters/input_discovery.py
    # "parse_sweep_metadata": "nanum_pipeline_30.py::parse_meta + _parse_filename_sweep",
    #     ^ Ported as runtime/stages/parse_sweep_metadata.py
    # "apply_sweep_binning": "nanum_pipeline_30.py::_apply_runtime_sweep_binning",
    #     ^ Ported as runtime/sweep_binning.py + runtime/stages/apply_sweep_binning.py
    # "prompt_sweep_duplicate_selector": "nanum_pipeline_30.py::prompt_sweep_duplicate_filter",
    #     ^ Ported as runtime/sweep_duplicate_selector.py + runtime/stages/prompt_sweep_duplicate_selector.py
    # "rewrite_plot_axis_to_sweep": "nanum_pipeline_30.py::_resolve_plot_x_request + _runtime_plot_filename_title",
    #     ^ Ported as runtime/sweep_axis.py + runtime/stages/rewrite_plot_axis_to_sweep.py
}


def default_legacy_root(project_root: Path) -> Path:
    return project_root.parent / DEFAULT_LEGACY_ROOT_NAME


def legacy_anchor_for_feature(feature_key: str) -> str:
    return LEGACY_PIPELINE30_ANCHORS.get(feature_key, "")

