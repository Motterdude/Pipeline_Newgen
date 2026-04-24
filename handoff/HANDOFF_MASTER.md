# HANDOFF_MASTER

Date: 2026-04-23
Project: `Pipeline_newgen_rev1`
Target repository: `https://github.com/Motterdude/Pipeline_Newgen`

## Objective
- start the migration from the legacy `pipeline29/pipeline30` codebase into a new repository;
- keep the current `pipeline29` stable and untouched;
- isolate the `pipeline30` `load/sweep` runtime into checkbox-driven features;
- create a documentation model that supports low-context editing with AI.

## What was created
- the new Git repository was cloned locally into:
  - `C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1`
- the first package scaffold now exists under:
  - `src/pipeline_newgen_rev1`
- a new VS Code workspace file exists:
  - `Pipeline_newgen_rev1.code-workspace`

## First technical decision
- the new generation should not start as another numbered monolith like `pipeline31.py`;
- instead, the migration starts by isolating the `pipeline30` `load/sweep` workflow into feature-flagged execution steps.

## Implemented modules
- `models.py`
  - shared data contracts for features and execution steps
- `bridges/legacy_pipeline30.py`
  - mapping from each new feature to the corresponding legacy anchor
- `workflows/load_sweep/feature_flags.py`
  - the source of truth for the new checkbox-driven workflow
- `workflows/load_sweep/state.py`
  - JSON persistence for feature state
- `workflows/load_sweep/orchestrator.py`
  - execution plan builder and summary helpers
- `ui/load_sweep_feature_dialog.py`
  - optional PySide6 checkbox dialog for feature selection
- `ui/runtime_preflight/*`
  - migrated runtime preflight scanner, prompts, and orchestration service
- `config/*`
  - migrated config adapter for text bundle loading, runtime state loading, and optional Excel bootstrap
- `adapters/open_to_csv.py`
  - migrated batch `.open -> .csv` adapter with saved converter path and pipeline naming
- `cli.py`
  - CLI entrypoint for showing the current plan, scanning preflight inputs, converting `.open`, and inspecting config/runtime state

## Operational checkpoint - 2026-04-23
- the operational working copy moved from the temporary clone to:
  - `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen`
- the new repo now carries the runtime assets needed for operation:
  - `config/pipeline29_text`
  - `config/pipeline30_smoke_text`
  - `config/config_incertezas_rev3.xlsx`
  - `config/lhv.csv`
  - `config/rules_consumo.csv`
  - `config/presets/pipeline29_legacy_bundle.json`
- the preserved GUI now saves/loads presets from the repository instead of `%LOCALAPPDATA%`
- `Save & Run` now exits the GUI back into the migrated executor
- the migrated executor now includes:
  - runtime folder chooser
  - runtime preflight
  - plot point filter in `load` mode
  - summary artifact generation under `pipeline_newgen_runtime`

## Real-run debug result - 2026-04-23
- a real `Save & Run` was traced on:
  - `process_dir = E:\raw_pyton\raw_NANUM`
  - `out_dir = E:\out_Nanum_rev2`
- the first real run did execute, but most LabVIEW files failed with:
  - `expected <class 'openpyxl.styles.fills.Fill'>`
- root cause:
  - the migrated LabVIEW reader was using `openpyxl` only
  - the legacy `pipeline30` already had a safer Excel path that preferred `calamine`
- fix applied:
  - `python-calamine` installed
  - `src/pipeline_newgen_rev1/adapters/labview_reader.py` updated to prefer `calamine` and only fall back to `openpyxl`
- post-fix rerun on the same dataset produced:
  - `total_inputs = 133`
  - `labview_files = 76`
  - `kibox_files = 19`
  - `errors = []`
- validation artifact:
  - `E:\out_Nanum_rev2\pipeline_newgen_runtime\newgen_runtime_summary.json`

## New rule for the load/sweep workflow
- `load` mode defaults must preserve the `pipeline29` behavior as much as possible;
- sweep-only features are disabled by default in `load` mode:
  - `show_runtime_preflight`
  - `convert_missing_open_files`
  - `parse_sweep_metadata`
  - `apply_sweep_binning`
  - `prompt_sweep_duplicate_selector`
  - `rewrite_plot_axis_to_sweep`
- compare and load-centric plots remain enabled by default in `load` mode.

## New low-context documentation format
- full narrative handoff stays in `handoff/HANDOFF_MASTER.md`
- operational low-context notes now live in:
  - `handoff/function_cards/*.fnctx.md`
- format reference:
  - `handoff/FUNCTION_CONTEXT_FORMAT.md`

## Validation expected for this slice
- `python -m unittest discover -s tests -p "test_*.py"`
- `Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-plan --mode load`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-plan --mode sweep`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli scan-preflight --process-dir <dir> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli convert-open <file-or-dir> --converter <path> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli inspect-config --config-source text --text-config-dir <dir> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-runtime-state --json`

## Validation status now
- `52` tests passing in the operational repository
- `py_compile` passing across the repository
- real run validated on `E:\raw_pyton\raw_NANUM`

## Next step
- move from the current summary-oriented migrated executor into full processing parity with the legacy runtime:
  - real KPI/output generation
  - final plot generation
  - compare/compare_iteracoes outputs
  - sweep binning and duplicate filtering wired into final outputs
