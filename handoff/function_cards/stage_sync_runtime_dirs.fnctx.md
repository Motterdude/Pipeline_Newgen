# stage_sync_runtime_dirs

## Role
- resolve `input_dir`/`output_dir` honoring saved state, bundle defaults, CLI overrides, and optional prompts
- materialize the feature plan for the current aggregation mode (`ctx.feature_selection` / `ctx.enabled_features`)
- corresponds to feature_key `sync_runtime_dirs`

## Inputs
- `ctx.bundle` (must already be set by `load_text_config`)
- `ctx.state_path_override`, `ctx.process_dir_override`, `ctx.out_dir_override`
- `ctx.prompt_runtime_dirs`, `ctx.runtime_dirs_prompt_func`

## Outputs
- `ctx.resolved_state_path`, `ctx.state`, `ctx.input_dir`, `ctx.output_dir`, `ctx.selection`
- `ctx.feature_selection`, `ctx.enabled_features`

## Do Not Break
- CLI overrides (`process_dir_override`, `out_dir_override`) must win over both saved state and prompt output — preserved from legacy behavior
- does **not** save runtime state here; that is done by `_finalize_runtime_state` in the runner after the preflight stage may have updated `ctx.selection`
- `feature_selection` is computed from the saved state's aggregation mode; if a future preflight changes the mode, the runner is responsible for re-materializing

## Edit Notes
- pure wiring of existing helpers: `load_runtime_state`, `apply_runtime_path_overrides`, `choose_runtime_dirs`, `merge_feature_selection`
- override semantics: kwargs → saved state → bundle defaults
- never inline the save here — it would prevent the preflight stage from updating selection before persistence

## Quick Test
- `python -m unittest tests.test_runtime_runner`
