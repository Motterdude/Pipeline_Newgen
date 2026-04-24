# runtime_runner

## Role
- orchestrate a single run of the load/sweep pipeline as a short loop over `STAGE_PIPELINE_ORDER` plus four private core helpers
- no domain logic lives here — every feature-gated action is a stage in `runtime/stages/`

## Inputs
- `project_root`
- config source and optional config paths
- optional runtime-state path
- optional explicit `process_dir` and `out_dir`
- flags: `use_preflight`, `prompt_runtime_dirs`, `prompt_plot_filter`
- hooks: `_runtime_dirs_prompt_func`, `_plot_filter_prompt_func`

## Outputs
- `RuntimeExecutionResult(summary, summary_json_path, summary_xlsx_path)`
- on-disk artifacts under `<out_dir>/pipeline_newgen_runtime/`:
  - `newgen_runtime_summary.json`
  - `newgen_runtime_summary.xlsx`

## Do Not Break
- public `run_load_sweep(**kwargs)` signature: consumed by `cli.py`, `ui/legacy/pipeline29_config_gui.py` (Save & Run), and `tests/test_runtime_runner.py`
- every field of the returned `summary` dict — tests and the GUI read specific keys
- execution order: `load_text_config` → `sync_runtime_dirs` → `show_runtime_preflight` → `_finalize_runtime_state` → `_discover_and_read_inputs` → `_apply_plot_filter` → `_write_summary_artifacts`
- runtime dirs must respect saved GUI state unless prompting is forced

## Edit Notes
- adding a new feature-gated action = register it in `runtime/stages/` and append its key to `STAGE_PIPELINE_ORDER`; do not add `if`-branches here
- the four private helpers (`_finalize_runtime_state`, `_discover_and_read_inputs`, `_apply_plot_filter`, `_write_summary_artifacts`) are core scaffolding, not feature-gated — they will be promoted to named stages when their feature keys land in the registry
- never add `print`s here; stages may log but the runner stays silent

## Quick Test
- `python -m unittest discover -s tests -p "test_*.py"` (52 tests)
- `PYTHONPATH=src python -m pipeline_newgen_rev1.cli show-plan --mode load`
- `python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir .\config\pipeline29_text --process-dir E:\raw_pyton\raw_NANUM --out-dir E:\out_Nanum_rev2 --json`
