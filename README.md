# Pipeline_newgen_rev1

Initial migration scaffold for the next-generation pipeline that will live in `Motterdude/Pipeline_Newgen`.

## Current goal
- keep `pipeline29` behavior stable;
- isolate the `pipeline30` `load/sweep` runtime as a structured workflow;
- add checkbox-driven feature flags so sweep-specific behavior can be enabled or disabled without contaminating the `29`-style flow;
- migrate incrementally with tests.

## Repository layout
- `src/pipeline_newgen_rev1/`
  - package code
- `config/`
  - versioned workflow defaults, legacy config bundles, and presets used by the migrated GUI/runtime
- `handoff/`
  - full handoff plus low-context function cards
- `tests/`
  - smoke and unit tests for the migration scaffold

## First migration slice
- feature registry for `load/sweep`
- per-mode default flags
- JSON persistence for checkbox selections
- execution plan builder
- optional PySide6 checkbox dialog
- legacy anchors pointing back to the current `nanum_pipeline_30.py`

## Open in VS Code
- open the folder `Pipeline_newgen_rev1`
- or open `Pipeline_newgen_rev1.code-workspace`

## Run tests
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Smoke compile
```powershell
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
```

## Show the workflow plan
```powershell
$env:PYTHONPATH='src'
python -m pipeline_newgen_rev1.cli show-plan --mode load
python -m pipeline_newgen_rev1.cli show-plan --mode sweep --json
```

## Inspect migrated config state
```powershell
$env:PYTHONPATH='src'
python -m pipeline_newgen_rev1.cli show-runtime-state --json
python -m pipeline_newgen_rev1.cli inspect-config --config-source text --text-config-dir <existing-text-bundle-dir> --json
```

## Operational config assets
- `config/pipeline29_text/`
  - migrated legacy processing bundle used by the preserved pipeline29/30 GUI
- `config/pipeline30_smoke_text/`
  - smoke/test bundle carried over from the legacy tool
- `config/presets/`
  - JSON presets loaded by the preserved GUI

## Current operational state
- the operational working copy now lives in:
  - `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen`
- the preserved pipeline29/30 GUI is running from the new repo
- `Save & Run` now returns into the migrated executor instead of reopening the GUI
- the migrated executor now includes:
  - runtime folder chooser
  - runtime preflight
  - plot point filter in `load` mode
  - LabVIEW read fallback through `python-calamine` before `openpyxl`
- real dataset validation was run on:
  - input: `E:\raw_pyton\raw_NANUM`
  - output: `E:\out_Nanum_rev2`
  - latest validated summary:
    - `total_inputs = 133`
    - `labview_files = 76`
    - `kibox_files = 19`
    - `errors = []`

## Current limitation
- the migrated runtime is operational for discovery, reading, preflight, runtime-dir prompting, and plot-point filtering
- it is not yet full parity with the legacy monolith for final processing outputs, final plot generation, and end-to-end reporting artifacts

## Inspect discovered inputs and LabVIEW files
```powershell
$env:PYTHONPATH='src'
python -m pipeline_newgen_rev1.cli discover-inputs --process-dir <process-dir> --json
python -m pipeline_newgen_rev1.cli inspect-labview --input <labview.xlsx> --process-root <process-dir> --json
python -m pipeline_newgen_rev1.cli inspect-motec --input <motec_m.csv> --process-root <process-dir> --json
python -m pipeline_newgen_rev1.cli inspect-kibox --input <kibox_i.csv> --process-root <process-dir> --json
python -m pipeline_newgen_rev1.cli inspect-kibox --input <kibox_i.csv> --process-root <process-dir> --aggregate --json
python -m pipeline_newgen_rev1.cli launch-config-gui
python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir <config-dir> --json
```

## Current production-like run
```powershell
cd "C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen"
python -m pipeline_newgen_rev1.cli launch-config-gui

python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir .\config\pipeline29_text --process-dir E:\raw_pyton\raw_NANUM --out-dir E:\out_Nanum_rev2 --json
```

## Convert `.open` files
```powershell
$env:PYTHONPATH='src'
python -m pipeline_newgen_rev1.cli convert-open <file-or-dir> --converter <OpenToCSV-path> --json
```
