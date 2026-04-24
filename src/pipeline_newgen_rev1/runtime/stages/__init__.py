"""Stage registry for the load/sweep runtime.

STAGE_PIPELINE_ORDER declares the invocation order. The runner iterates this
tuple and calls `STAGE_REGISTRY[key].run(ctx)` for each key present.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ...bridges.legacy_runtime import (
    RunCompareIteracoesBridgeStage,
)
from ._base import Stage, stage_is_enabled
from .build_final_table import BuildFinalTableStage
from .compute_trechos_ponto import ComputeTrechosPontoStage
from .enrich_final_table_audit import EnrichFinalTableAuditStage
from .export_excel import ExportExcelStage
from .prepare_upstream_frames import PrepareUpstreamFramesStage
from .load_text_config import LoadTextConfigStage
from .run_time_diagnostics import RunTimeDiagnosticsStage
from .run_unitary_plots import RunUnitaryPlotsStage
from .show_runtime_preflight import ShowRuntimePreflightStage
from .sync_runtime_dirs import SyncRuntimeDirsStage


STAGE_REGISTRY: Dict[str, Stage] = {
    "load_text_config": LoadTextConfigStage(),
    "sync_runtime_dirs": SyncRuntimeDirsStage(),
    "show_runtime_preflight": ShowRuntimePreflightStage(),
    "run_time_diagnostics": RunTimeDiagnosticsStage(),
    "compute_trechos_ponto": ComputeTrechosPontoStage(),
    "prepare_upstream_frames": PrepareUpstreamFramesStage(),
    "build_final_table": BuildFinalTableStage(),
    "enrich_final_table_audit": EnrichFinalTableAuditStage(),
    "export_excel": ExportExcelStage(),
    "run_unitary_plots": RunUnitaryPlotsStage(),
    "run_compare_iteracoes": RunCompareIteracoesBridgeStage(),
}


# Config stages run before input discovery. These only consume bundle/selection.
CONFIG_STAGE_ORDER: Tuple[str, ...] = (
    "load_text_config",
    "sync_runtime_dirs",
    "show_runtime_preflight",
)

# Processing stages run after input discovery and can consume ctx.labview_frames.
PROCESSING_STAGE_ORDER: Tuple[str, ...] = (
    "run_time_diagnostics",
    "compute_trechos_ponto",
    "prepare_upstream_frames",
    "build_final_table",
    "enrich_final_table_audit",
    "export_excel",
    "run_unitary_plots",
    "run_compare_iteracoes",
)

# Full invocation order (union) — exposed for `show-plan` and tests that assert
# the complete set. Runner iterates CONFIG then PROCESSING separately.
STAGE_PIPELINE_ORDER: Tuple[str, ...] = CONFIG_STAGE_ORDER + PROCESSING_STAGE_ORDER


def get_stage(feature_key: str) -> Optional[Stage]:
    return STAGE_REGISTRY.get(feature_key)


__all__ = [
    "STAGE_PIPELINE_ORDER",
    "STAGE_REGISTRY",
    "Stage",
    "get_stage",
    "stage_is_enabled",
]
