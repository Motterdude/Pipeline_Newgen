# runtime_preflight

## Role
- isolate the `pipeline30` runtime preflight into small modules
- scan the process directory, detect sweep candidates, and select `load` or `sweep`

## Inputs
- `process_dir`
- optional initial `RuntimeSelection`
- optional prompt callback
- optional conversion callback

## Outputs
- normalized `RuntimeSelection`
- snapshot summary for:
  - xlsx/csv/open counts
  - missing `.open -> _i.csv`
  - available sweep keys

## Do Not Break
- `load` must remain the safe default when no explicit sweep choice is made
- missing conversions must not be silently ignored when the prompt asks to convert
- the service must re-scan after conversion before returning

## Edit Notes
- scanner logic belongs in `scan.py`
- prompt logic belongs in `prompt.py`
- orchestration loop belongs in `service.py`
- real `.open` conversion now belongs to `adapters/open_to_csv.py`
- keep the prompt returning an action token so tests can still inject a fake convert path when needed
- the runtime executor now calls this service from `Save & Run`
- do not move runtime folder prompting here; that now lives in `runtime/runtime_dirs.py`

## Quick Test
- run:
  - `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli scan-preflight --process-dir . --json`
  - `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir .\config\pipeline29_text --use-preflight --json`
  - `python -m unittest discover -s tests -p "test_*.py"`
