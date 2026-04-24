from __future__ import annotations

from typing import Dict, Iterable

from ...bridges.legacy_pipeline30 import legacy_anchor_for_feature
from ...models import FeatureSpec, normalize_workflow_mode


LOAD_SWEEP_FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        key="load_text_config",
        label="Load text config",
        description="Load the versioned text configuration bundle before any processing step.",
        stage="config",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("load_text_config"),
    ),
    FeatureSpec(
        key="sync_runtime_dirs",
        label="Sync runtime dirs",
        description="Resolve input/output directories and keep runtime path overrides isolated from the old repo.",
        stage="config",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("sync_runtime_dirs"),
    ),
    FeatureSpec(
        key="show_runtime_preflight",
        label="Show runtime preflight",
        description="Display the pipeline30 preflight that inventories inputs and lets the user confirm load or sweep mode.",
        stage="runtime",
        default_by_mode={"load": False, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("show_runtime_preflight"),
        notes="Disabled by default in load mode to preserve the pipeline29 feel.",
    ),
    FeatureSpec(
        key="convert_missing_open_files",
        label="Convert missing .open files",
        description="Offer the KiBox OpenToCSV batch conversion before processing.",
        stage="runtime",
        default_by_mode={"load": False, "sweep": False},
        legacy_anchor=legacy_anchor_for_feature("convert_missing_open_files"),
        notes="Kept opt-in because conversion is slow and should not silently change the flow.",
    ),
    FeatureSpec(
        key="parse_sweep_metadata",
        label="Parse sweep metadata",
        description="Parse sweep variable and value from file names and attach runtime sweep columns.",
        stage="input",
        default_by_mode={"load": False, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("parse_sweep_metadata"),
    ),
    FeatureSpec(
        key="apply_sweep_binning",
        label="Apply sweep binning",
        description="Cluster sweep values into stable bins so close measurements do not split the same target point.",
        stage="processing",
        default_by_mode={"load": False, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("apply_sweep_binning"),
    ),
    FeatureSpec(
        key="prompt_sweep_duplicate_selector",
        label="Prompt duplicate selector",
        description="Open the duplicate selector for fuel x sweep points before plotting or exporting the final dataset.",
        stage="processing",
        default_by_mode={"load": False, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("prompt_sweep_duplicate_selector"),
    ),
    FeatureSpec(
        key="rewrite_plot_axis_to_sweep",
        label="Rewrite plot axis to sweep",
        description="Replace load-based X requests with the configured sweep axis during plotting.",
        stage="plotting",
        default_by_mode={"load": False, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("rewrite_plot_axis_to_sweep"),
        notes="This is the main guardrail that prevents sweep behavior from interfering with the load workflow.",
    ),
    FeatureSpec(
        key="run_time_diagnostics",
        label="Run time diagnostics",
        description="Generate delta-T diagnostics and quality summaries before the main aggregation.",
        stage="diagnostics",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("run_time_diagnostics"),
    ),
    FeatureSpec(
        key="compute_trechos_ponto",
        label="Compute trechos & ponto stats",
        description="Aggregate LabVIEW raw data into window means (trechos) and point-level stats (ponto).",
        stage="processing",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("compute_trechos_ponto"),
    ),
    FeatureSpec(
        key="prepare_upstream_frames",
        label="Prepare upstream frames",
        description="Load fuel properties, aggregate KiBox, and compute MoTeC ponto — upstream data for build_final_table.",
        stage="processing",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("prepare_upstream_frames"),
    ),
    FeatureSpec(
        key="build_final_table",
        label="Build final KPI table",
        description="Aggregate trechos/pontos, merge fuel properties and KiBox/MoTeC, produce the final lv_kpis table.",
        stage="processing",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("build_final_table"),
    ),
    FeatureSpec(
        key="enrich_final_table_audit",
        label="Enrich final table with uncertainty audit",
        description="Add per-measurand uB_res, uB_acc, uc, U, and variance-weighted %uA/%uB contribution columns to lv_kpis_clean.xlsx for auditability (GUM §F.1.2.4).",
        stage="processing",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor="",
        notes="Native-only. No legacy counterpart — produces audit columns on top of what build_final_table wrote.",
    ),
    FeatureSpec(
        key="export_excel",
        label="Export Excel",
        description="Write the final KPI workbook after aggregation.",
        stage="export",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("export_excel"),
    ),
    FeatureSpec(
        key="run_unitary_plots",
        label="Run unitary plots",
        description="Generate the plots configured in the text bundle for each source folder.",
        stage="plotting",
        default_by_mode={"load": True, "sweep": True},
        legacy_anchor=legacy_anchor_for_feature("run_unitary_plots"),
    ),
    FeatureSpec(
        key="run_compare_plots",
        label="Run compare plots",
        description="Generate compare plots for subida/descida groups using the pipeline29 logic.",
        stage="plotting",
        default_by_mode={"load": True, "sweep": False},
        legacy_anchor=legacy_anchor_for_feature("run_compare_plots"),
        notes="Disabled by default in sweep mode because compare expects load-oriented campaigns.",
    ),
    FeatureSpec(
        key="run_compare_iteracoes",
        label="Run compare_iteracoes",
        description="Generate the compare_iteracoes outputs and Excel exports from the pipeline29 branch.",
        stage="plotting",
        default_by_mode={"load": True, "sweep": False},
        legacy_anchor=legacy_anchor_for_feature("run_compare_iteracoes"),
    ),
    FeatureSpec(
        key="run_special_load_plots",
        label="Run special load plots",
        description="Run load-only overlays and special plots such as ethanol equivalent and machine scenario suites.",
        stage="plotting",
        default_by_mode={"load": True, "sweep": False},
        legacy_anchor=legacy_anchor_for_feature("run_special_load_plots"),
    ),
)


def feature_spec_map() -> Dict[str, FeatureSpec]:
    return {spec.key: spec for spec in LOAD_SWEEP_FEATURE_SPECS}


def default_feature_selection(mode: object) -> Dict[str, bool]:
    mode_norm = normalize_workflow_mode(mode)
    return {spec.key: spec.default_enabled(mode_norm) for spec in LOAD_SWEEP_FEATURE_SPECS}


def merge_feature_selection(mode: object, overrides: Dict[str, bool] | None = None) -> Dict[str, bool]:
    merged = default_feature_selection(mode)
    if not overrides:
        return merged
    known_keys = feature_spec_map()
    for key, value in overrides.items():
        if key in known_keys:
            merged[key] = bool(value)
    return merged


def unknown_feature_keys(keys: Iterable[str]) -> list[str]:
    known = feature_spec_map()
    return sorted(key for key in keys if key not in known)

