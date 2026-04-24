# Migration Status

## Scope of this first slice
- create the new repository and VS Code-ready folder structure;
- isolate the `pipeline30` `load/sweep` workflow into a new package;
- model sweep-specific behavior as checkbox-driven feature flags;
- keep the current `pipeline29` behavior protected by default in `load` mode;
- define a low-context handoff format for AI-assisted edits.

## What is implemented
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py`
  - versioned registry of workflow features
  - separate defaults for `load` and `sweep`
- `src/pipeline_newgen_rev1/workflows/load_sweep/state.py`
  - JSON load/save for checkbox selections
- `src/pipeline_newgen_rev1/workflows/load_sweep/orchestrator.py`
  - deterministic execution plan builder
- `src/pipeline_newgen_rev1/ui/load_sweep_feature_dialog.py`
  - optional PySide6 checkbox dialog
- `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py`
  - legacy anchors back to the current monolith
- `src/pipeline_newgen_rev1/ui/runtime_preflight/`
  - migrated `pipeline30` preflight split into:
    - constants
    - models
    - normalization
    - scanner
    - prompt
    - service
- `src/pipeline_newgen_rev1/config/`
  - text config bundle load/save in TOML
  - runtime state load/save for dirs plus sweep selection
  - optional legacy Excel bootstrap and defaults-sheet sync
- `src/pipeline_newgen_rev1/adapters/open_to_csv.py`
  - migrated batch adapter for `.open -> .csv`
  - converter discovery via env/saved path/default candidates
  - pipeline `_i.csv` naming and directory-preserving batch export
- `pipeline_newgen_rev1.cli scan-preflight`
  - non-interactive smoke path for the new preflight scanner
- `pipeline_newgen_rev1.cli convert-open`
  - direct CLI for the migrated `.open -> .csv` adapter
- `pipeline_newgen_rev1.cli inspect-config`
  - smoke path for the migrated config adapter
- `pipeline_newgen_rev1.cli show-runtime-state`
  - inspect the persisted runtime state without opening the legacy UI
- `src/pipeline_newgen_rev1/adapters/input_discovery.py`
  - migrated filename metadata parsing for:
    - source classification (`LABVIEW`, `KIBOX`, `MOTEC`)
    - nominal load in filename
    - fuel composition tokens
    - sweep key/value tokens
- `pipeline_newgen_rev1.cli discover-inputs`
  - inspect the migrated input-discovery summary without opening the legacy runtime
- `src/pipeline_newgen_rev1/adapters/labview_reader.py`
  - migrated first LabVIEW reader slice for:
    - worksheet selection
    - header normalization
    - pressure sentinel cleanup
    - load inference from signal column
    - runtime metadata enrichment per row
- `pipeline_newgen_rev1.cli inspect-labview`
  - inspect the migrated LabVIEW read summary without entering the legacy monolith
- `src/pipeline_newgen_rev1/adapters/motec_reader.py`
  - migrated first MoTeC reader slice for:
    - delimiter sniffing
    - header metadata extraction
    - drop of the units row
    - `Motec_` column prefixing
    - `Motec_Time_Delta_s`
- `pipeline_newgen_rev1.cli inspect-motec`
  - inspect the migrated MoTeC read summary without entering the legacy monolith
- `src/pipeline_newgen_rev1/adapters/kibox_reader.py`
  - migrated first KiBox reader slice for:
    - dynamic header detection
    - robust delimiter sniffing
    - raw `_i.csv` inspection
    - aggregated `KIBOX_*` mean row generation
- `pipeline_newgen_rev1.cli inspect-kibox`
  - inspect the migrated KiBox read summary or the aggregated `KIBOX_*` row
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py`
  - migrated copy of the shared pipeline29/30 GUI into the new repository
  - preserved visual flow and controls while swapping imports to the new package
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_backend.py`
  - compatibility backend that keeps the legacy GUI contract while reading/writing through the migrated config adapter
- `pipeline_newgen_rev1.cli launch-config-gui`
  - opens the migrated legacy GUI from the new repository
- `src/pipeline_newgen_rev1/runtime/runtime_dirs.py`
  - migrated runtime folder chooser with:
    - Windows native folder dialog
    - Tk fallback
    - terminal fallback
    - saved GUI runtime-dir reuse
- `src/pipeline_newgen_rev1/runtime/plot_point_filter.py`
  - migrated plot point filter with:
    - metadata-first selection path
    - dataframe fallback path
    - saved last selection state
    - Qt/Tk fallback behavior matching the legacy tool
- `src/pipeline_newgen_rev1/runtime/runner.py`
  - migrated runtime executor now wired from `Save & Run`
  - current scope:
    - runtime dir selection
    - preflight
    - input discovery
    - LabVIEW/MoTeC/KiBox readers
    - plot point filtering in `load` mode
    - summary artifact generation
- `src/pipeline_newgen_rev1/adapters/labview_reader.py`
  - LabVIEW read path now prefers `python-calamine` and only falls back to `openpyxl`
  - this was required to read the real `raw_NANUM` workbooks that fail in `openpyxl`
- `config/`
  - now carries the operational assets copied from the legacy tool:
    - `pipeline29_text`
    - `pipeline30_smoke_text`
    - `config_incertezas_rev3.xlsx`
    - `lhv.csv`
    - `rules_consumo.csv`
    - `presets/pipeline29_legacy_bundle.json`

## Why this is the right first step
- it creates feature boundaries before moving heavy data-processing code;
- it lets us disable sweep-only features in `load` mode so they do not change the `29` flow;
- it gives us tests that can remain stable while we migrate legacy code behind the new boundaries.

## Operational checkpoint on 2026-04-23
- the operational repository was moved to:
  - `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen`
- `Save & Run` from the preserved GUI now returns into the migrated executor instead of reopening the GUI
- runtime state used in the latest validated run:
  - `process_dir = E:\raw_pyton\raw_NANUM`
  - `out_dir = E:\out_Nanum_rev2`
  - `aggregation_mode = load`
- real dataset validation after the LabVIEW `calamine` fallback fix produced:
  - `total_inputs = 133`
  - `labview_files = 76`
  - `kibox_files = 19`
  - `errors = []`
- output artifacts from that validation are:
  - `E:\out_Nanum_rev2\pipeline_newgen_runtime\newgen_runtime_summary.json`
  - `E:\out_Nanum_rev2\pipeline_newgen_runtime\newgen_runtime_summary.xlsx`

## Current known gap
- the migrated executor is now operational for input discovery, reader validation, runtime-dir prompting, preflight, and plot-point filtering
- the project is still short of full parity with the legacy monolith for:
  - final processed KPI outputs
  - final plot generation
  - full reporting/export behavior

## Next migration targets
1. input discovery:
   - richer schema hints and value normalization for LabVIEW
   - richer schema hints and value normalization for MoTeC
   - richer schema hints and value normalization for KiBox
2. sweep runtime adapters:
   - binning
   - duplicate selector
3. plotting adapters:
   - unitary plots
   - compare plots
   - compare_iteracoes
4. GUI integration follow-up:
   - keep `Save & Run` routed to the migrated executor and remove remaining edge-case regressions
   - replace remaining legacy runtime helper internals with migrated modules where possible
5. processing/output parity:
   - migrate the real end-to-end processing chain behind the current summary executor
   - migrate final plot generation and reporting outputs until they match the legacy tool behavior
