# bridge_legacy_runtime

## Role
- host the "service window" bridge classes that let the newgen factory call into the frozen legacy monoliths without importing them eagerly
- each bridge class implements `Stage.run(ctx)` and corresponds to exactly one `feature_key` in `LOAD_SWEEP_FEATURE_SPECS`

## Inputs
- `RuntimeContext` (mutated in place)
- at module load: nothing heavy — the frozen monoliths are imported lazily on first use via `_load_legacy_pipeline29()`

## Outputs
- `BuildFinalTableBridgeStage` — reproduces the legacy preparation chain and populates `ctx.final_table` (plus `ctx.ponto`/`fuel_properties`/`kibox_agg`/`motec_ponto`); caches `ctx.legacy_bundle` for downstream bridges
- `ExportExcelBridgeStage` — consumes `ctx.final_table` and writes `<out_dir>/lv_kpis_clean.xlsx`
- `RunUnitaryPlotsBridgeStage` — consumes `ctx.final_table` and `ctx.legacy_bundle.plots_df`; writes PNGs to `<out_dir>/plots/`; populates `ctx.unitary_plot_summary`
- `_try_load_legacy_pipeline29()` — graceful-fallback loader; returns `None` if matplotlib or another `[legacy]` dep is missing
- `_ensure_legacy_bundle(ctx, legacy)` — returns cached or lazily loads the legacy bundle
- future: `RunTimeDiagnosticsBridgeStage`, `RunComparePlotsBridgeStage`, `RunCompareIteracoesBridgeStage`, `RunSpecialLoadPlotsBridgeStage`

## Do Not Break
- `RuntimeContext` is imported under `TYPE_CHECKING` only — do **not** add a runtime import back; it creates a circular with `runtime.stages.__init__`
- bridge stage classes must keep `feature_key` equal to the string from `LOAD_SWEEP_FEATURE_SPECS`
- lazy-import order: `from .. import legacy_monoliths` must run before `importlib.import_module("nanum_pipeline_29")` (the package init inserts the dir on `sys.path`)
- do not add domain logic here — each bridge is a thin wrapper; real work stays in the frozen monoliths until ported

## Edit Notes
- when a station is ported to a native implementation, delete its bridge class from this file, then drop the matching line from `runtime/stages/__init__.py::STAGE_REGISTRY`
- also remove the corresponding entry from `bridges/legacy_pipeline30.py::LEGACY_PIPELINE30_ANCHORS`
- when the last bridge is gone, delete this module and `legacy_monoliths/` together
- keep `_load_legacy_pipeline29()` private — callers should never hold a module reference beyond their `run(ctx)` call

## Quick Test
- `python -m unittest tests.test_bridge_export_excel` (requires `pip install .[legacy]` for the write-path test)
- `python -m unittest discover -s tests -p "test_*.py"`
