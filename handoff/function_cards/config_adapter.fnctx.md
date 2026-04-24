# config_adapter

## Role
- load the migrated `pipeline29/pipeline30` config bundle in the new repo
- keep text config, runtime state, and legacy Excel bootstrap behind one adapter surface

## Inputs
- `project_root`
- optional `text_config_dir`
- optional legacy Excel path
- optional runtime-state JSON path

## Outputs
- `ConfigBundle` with mappings/defaults/reporting/plots data
- `RuntimeState` with input/output dirs and sweep selection
- optional text bundle files written under `config/pipeline29_text`

## Do Not Break
- `auto` config loading must prefer a complete text bundle when it already exists
- runtime-state loading must be tolerant of missing or malformed JSON
- Excel-specific paths must fail with a clear message when `openpyxl` is unavailable

## Edit Notes
- keep text config parsing in stdlib TOML so it stays lightweight
- keep legacy Excel access isolated here until the real runtime adapters stop depending on rev3 sheets
- runtime dir prompting does not belong here; this layer only loads, saves, and normalizes state

## Quick Test
- run:
  - `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-runtime-state --json`
  - `python -m unittest discover -s tests -p "test_*.py"`
