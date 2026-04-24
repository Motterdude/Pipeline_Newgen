"""Stage registry for the load/sweep runtime.

STAGE_PIPELINE_ORDER declares the invocation order. The runner iterates this
tuple and calls `STAGE_REGISTRY[key].run(ctx)` for each key present.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ...bridges.legacy_runtime import (
    BuildFinalTableBridgeStage,
    ExportExcelBridgeStage,
    RunUnitaryPlotsBridgeStage,
)
from ._base import Stage, stage_is_enabled
from .load_text_config import LoadTextConfigStage
from .show_runtime_preflight import ShowRuntimePreflightStage
from .sync_runtime_dirs import SyncRuntimeDirsStage


STAGE_REGISTRY: Dict[str, Stage] = {
    "load_text_config": LoadTextConfigStage(),
    "sync_runtime_dirs": SyncRuntimeDirsStage(),
    "show_runtime_preflight": ShowRuntimePreflightStage(),
    "build_final_table": BuildFinalTableBridgeStage(),
    "export_excel": ExportExcelBridgeStage(),
    "run_unitary_plots": RunUnitaryPlotsBridgeStage(),
}


STAGE_PIPELINE_ORDER: Tuple[str, ...] = (
    "load_text_config",
    "sync_runtime_dirs",
    "show_runtime_preflight",
    "build_final_table",
    "export_excel",
    "run_unitary_plots",
)


def get_stage(feature_key: str) -> Optional[Stage]:
    return STAGE_REGISTRY.get(feature_key)


__all__ = [
    "STAGE_PIPELINE_ORDER",
    "STAGE_REGISTRY",
    "Stage",
    "get_stage",
    "stage_is_enabled",
]
