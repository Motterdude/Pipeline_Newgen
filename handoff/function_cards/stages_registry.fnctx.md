# stages_registry

## Role
- map `feature_key` → stage instance (`STAGE_REGISTRY`)
- declare invocation order (`STAGE_PIPELINE_ORDER`) so the runner knows which stages to run and in what sequence

## Inputs
- module-level imports of each concrete stage in `runtime/stages/*.py`

## Outputs
- `STAGE_REGISTRY: dict[str, Stage]`
- `STAGE_PIPELINE_ORDER: tuple[str, ...]`
- `get_stage(feature_key) -> Stage | None`
- re-export of `Stage` protocol and `stage_is_enabled` helper

## Do Not Break
- `feature_key` values must match entries in `LOAD_SWEEP_FEATURE_SPECS` exactly
- order in `STAGE_PIPELINE_ORDER` is load-bearing: `load_text_config` must precede `sync_runtime_dirs`, which must precede `show_runtime_preflight`
- registry is append-only during migration: new stage entries are added alongside new `bridges/legacy_runtime.py` entries or new native modules

## Edit Notes
- when a stage is ported from bridge to native, keep its `feature_key` unchanged; only swap the class assigned to that key in `STAGE_REGISTRY`
- do not embed domain logic in this module — only wiring
- when core scaffolding helpers in `runner.py` (discovery, read, summary) are promoted to stages, add their keys to `STAGE_PIPELINE_ORDER` in place of the current helper calls

## Quick Test
- `python -m unittest discover -s tests -p "test_*.py"`
- `PYTHONPATH=src python -m pipeline_newgen_rev1.cli show-plan --mode load`
