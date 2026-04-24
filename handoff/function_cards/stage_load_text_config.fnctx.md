# stage_load_text_config

## Role
- first station of the assembly line: read the configuration bundle (TOML or Excel) into `ctx.bundle`
- corresponds to feature_key `load_text_config`

## Inputs
- `ctx.project_root`, `ctx.config_source`, `ctx.text_config_dir`, `ctx.excel_path`

## Outputs
- `ctx.bundle: ConfigBundle`

## Do Not Break
- must run before any stage that relies on `ctx.bundle` (all of them)
- must not mutate other ctx fields
- exception from `load_pipeline29_config_bundle` must propagate so the runner fails loudly

## Edit Notes
- implementation is a thin wrapper around `config.adapter.load_pipeline29_config_bundle`
- no logic lives here beyond forwarding kwargs

## Quick Test
- `python -m unittest tests.test_runtime_runner`
