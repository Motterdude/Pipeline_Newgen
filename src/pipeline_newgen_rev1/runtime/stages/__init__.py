"""Stage registry for the load/sweep runtime.

Three-phase pipeline:
  CONFIG_STAGE_ORDER   — resolve bundle, runtime dirs, preflight (always run)
  PROCESSING_STAGE_ORDER — data computation + export (feature-flag gated)
  PLOTTING_STAGE_ORDER — visualization only (feature-flag gated)

The runner iterates each tuple and calls ``STAGE_REGISTRY[key].run(ctx)``
for each enabled key.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ._base import Stage, stage_is_enabled
from .apply_sweep_binning import ApplySweepBinningStage
from .build_final_table import BuildFinalTableStage
from .compute_compare_iteracoes import ComputeCompareIteracoesStage
from .compute_trechos_ponto import ComputeTrechosPontoStage
from .enrich_final_table_audit import EnrichFinalTableAuditStage
from .export_excel import ExportExcelStage
from .load_text_config import LoadTextConfigStage
from .parse_sweep_metadata import ParseSweepMetadataStage
from .plot_compare_iteracoes import PlotCompareIteracoesStage
from .plot_time_diagnostics import PlotTimeDiagnosticsStage
from .prepare_upstream_frames import PrepareUpstreamFramesStage
from .prompt_sweep_duplicate_selector import PromptSweepDuplicateSelectorStage
from .rewrite_plot_axis_to_sweep import RewritePlotAxisToSweepStage
from .run_time_diagnostics import RunTimeDiagnosticsStage
from .run_compare_plots import RunComparePlotsStage
from .run_special_load_plots import RunSpecialLoadPlotsStage
from .run_unitary_plots import RunUnitaryPlotsStage
from .scan_campaign_structure import ScanCampaignStructureStage
from .show_runtime_preflight import ShowRuntimePreflightStage
from .sync_runtime_dirs import SyncRuntimeDirsStage


STAGE_REGISTRY: Dict[str, Stage] = {
    "load_text_config": LoadTextConfigStage(),
    "sync_runtime_dirs": SyncRuntimeDirsStage(),
    "show_runtime_preflight": ShowRuntimePreflightStage(),
    "parse_sweep_metadata": ParseSweepMetadataStage(),
    "run_time_diagnostics": RunTimeDiagnosticsStage(),
    "compute_trechos_ponto": ComputeTrechosPontoStage(),
    "prepare_upstream_frames": PrepareUpstreamFramesStage(),
    "build_final_table": BuildFinalTableStage(),
    "enrich_final_table_audit": EnrichFinalTableAuditStage(),
    "apply_sweep_binning": ApplySweepBinningStage(),
    "prompt_sweep_duplicate_selector": PromptSweepDuplicateSelectorStage(),
    "export_excel": ExportExcelStage(),
    "scan_campaign_structure": ScanCampaignStructureStage(),
    "compute_compare_iteracoes": ComputeCompareIteracoesStage(),
    "rewrite_plot_axis_to_sweep": RewritePlotAxisToSweepStage(),
    "plot_time_diagnostics": PlotTimeDiagnosticsStage(),
    "run_unitary_plots": RunUnitaryPlotsStage(),
    "run_compare_plots": RunComparePlotsStage(),
    "plot_compare_iteracoes": PlotCompareIteracoesStage(),
    "run_special_load_plots": RunSpecialLoadPlotsStage(),
}


# Config stages run before input discovery. These only consume bundle/selection.
CONFIG_STAGE_ORDER: Tuple[str, ...] = (
    "load_text_config",
    "sync_runtime_dirs",
    "show_runtime_preflight",
)

# Processing stages run after input discovery — data computation + export only.
PROCESSING_STAGE_ORDER: Tuple[str, ...] = (
    "parse_sweep_metadata",
    "run_time_diagnostics",
    "compute_trechos_ponto",
    "prepare_upstream_frames",
    "build_final_table",
    "enrich_final_table_audit",
    "apply_sweep_binning",
    "prompt_sweep_duplicate_selector",
    "export_excel",
    "scan_campaign_structure",
    "compute_compare_iteracoes",
    "rewrite_plot_axis_to_sweep",
)

# Plotting stages run after processing — visualization only, no computation.
PLOTTING_STAGE_ORDER: Tuple[str, ...] = (
    "plot_time_diagnostics",
    "run_unitary_plots",
    "run_compare_plots",
    "plot_compare_iteracoes",
    "run_special_load_plots",
)

# Full invocation order (union) — exposed for `show-plan` and tests that assert
# the complete set.
STAGE_PIPELINE_ORDER: Tuple[str, ...] = (
    CONFIG_STAGE_ORDER + PROCESSING_STAGE_ORDER + PLOTTING_STAGE_ORDER
)


def get_stage(feature_key: str) -> Optional[Stage]:
    return STAGE_REGISTRY.get(feature_key)


__all__ = [
    "CONFIG_STAGE_ORDER",
    "PLOTTING_STAGE_ORDER",
    "PROCESSING_STAGE_ORDER",
    "STAGE_PIPELINE_ORDER",
    "STAGE_REGISTRY",
    "Stage",
    "get_stage",
    "stage_is_enabled",
]
