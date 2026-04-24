# open_to_csv_adapter

## Role
- convert KiBox `.open` files into CSV outputs using the external OpenToCSV tool
- keep pipeline naming, tool discovery, and batch execution outside the runtime preflight UI

## Inputs
- a single `.open` file or a directory tree with `.open` files
- optional converter path
- optional output root
- export flags such as `type`, `separator`, and naming mode

## Outputs
- pipeline-style `_i.csv` files when `name_mode="pipeline"`
- persisted converter path under the local app state directory
- per-file `ExportResult` records with stdout/stderr and return code

## Do Not Break
- `pipeline` naming must keep the `<stem>_i.csv` contract
- when converting a directory tree with `output_root`, relative subfolders must be preserved
- the adapter must accept a real `OpenToCSV.exe` and also test-friendly script wrappers passed explicitly

## Edit Notes
- this slice is batch-only; the legacy GUI converter did not move yet
- runtime preflight should call this adapter instead of inventing filenames itself
- keep discovery here so callers do not need to know about env vars or saved settings

## Quick Test
- run:
  - `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli convert-open <file-or-dir> --converter <path> --json`
  - `python -m unittest discover -s tests -p "test_*.py"`
