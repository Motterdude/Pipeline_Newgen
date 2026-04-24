# runtime_context

## Role
- carry every piece of mutable state used by the load/sweep runtime as a single object (the "conveyor belt" of the factory)
- let each stage mutate the fields it owns without reaching through `run_load_sweep` locals

## Inputs
- factory `from_kwargs(**kwargs)` mirroring the public `run_load_sweep` signature
- kwargs include: `project_root`, `config_source`, `text_config_dir`, `excel_path`, `state_path`, `process_dir`, `out_dir`, `use_preflight`, `prompt_runtime_dirs`, `prompt_plot_filter`, `runtime_dirs_prompt_func`, `plot_filter_prompt_func`

## Outputs
- a mutable `RuntimeContext` instance pre-populated with invariant kwargs and empty slots for stage-produced fields
- after the full pipeline runs, holds: `bundle`, `state`, `normalized_state`, `input_dir`, `output_dir`, `selection`, `feature_selection`/`enabled_features`, `discovery`, per-source rows, `selected_plot_points`, `errors`, `artifacts_dir`, `summary_*` paths, `summary` dict

## Do Not Break
- field names of the `summary` dict are consumed by tests (`test_runtime_runner.py`) and by the GUI Save & Run bridge
- `from_kwargs` parameter names must match `run_load_sweep` kwargs one-to-one
- `enabled_features` is populated by `SyncRuntimeDirsStage` after the state is loaded; do not query it before that stage runs

## Edit Notes
- new stage fields go here, not on ad-hoc globals
- keep the dataclass mutable (no `frozen=True`) — the whole point is in-place mutation
- reserve new slots with safe defaults (`None`, empty list, empty dict) so partially-executed pipelines still have readable state

## Quick Test
- `python -m unittest discover -s tests -p "test_*.py"`
