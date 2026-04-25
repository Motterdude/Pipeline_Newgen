"""Bridge stations: wrap functions from the frozen legacy monoliths so they
expose the same `Stage.run(ctx)` contract as native stations.

All four original bridge classes (BuildFinalTableBridgeStage,
RunUnitaryPlotsBridgeStage, RunCompareIteracoesBridgeStage,
ExportExcelBridgeStage) have been replaced by native stages and removed.
The lazy-loader helpers are kept for possible future debugging needs.
"""
from __future__ import annotations

from typing import Any

from .. import legacy_monoliths  # noqa: F401  # triggers sys.path injection


def _load_legacy_pipeline29() -> Any:
    import importlib
    return importlib.import_module("nanum_pipeline_29")


def _try_load_legacy_pipeline29() -> Any:
    try:
        return _load_legacy_pipeline29()
    except ModuleNotFoundError as exc:
        print(f"[INFO] legacy bridge | skipping: {exc.name or exc} not installed")
        return None
