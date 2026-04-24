# stage_show_runtime_preflight

## Role
- show the pipeline30 preflight inventory/confirm dialog when explicitly requested
- update `ctx.selection` with the user's confirmed aggregation mode / sweep parameters
- corresponds to feature_key `show_runtime_preflight`

## Inputs
- `ctx.use_preflight` (gating flag — explicit kwarg from the CLI/GUI)
- `ctx.input_dir`, `ctx.selection`

## Outputs
- updated `ctx.selection` (possibly switched to sweep mode with sweep_key/sweep_x_col/sweep_bin_tol set)

## Do Not Break
- gating stays on `ctx.use_preflight`, **not** on the feature flag default — the flag default is `False` in load / `True` in sweep, but the legacy contract is that the caller decides
- selection updates here must happen before `_finalize_runtime_state` in the runner so the persisted state reflects any mode switch

## Edit Notes
- thin wrapper around `ui.runtime_preflight.choose_runtime_preflight`
- when/if preflight gating moves to the feature flag, also remove the `use_preflight` kwarg from `run_load_sweep`

## Quick Test
- `python -m unittest tests.test_runtime_runner`
