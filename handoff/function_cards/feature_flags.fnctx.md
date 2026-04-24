# feature_flags

## Role
- define the checkbox-driven source of truth for the new `load/sweep` workflow
- keep `load` defaults safe for the legacy `pipeline29` behavior

## Inputs
- workflow mode: `load` or `sweep`
- optional user overrides from JSON or UI

## Outputs
- merged boolean selection map for each workflow feature
- stable ordered registry of feature specs

## Do Not Break
- sweep-only features must stay `False` by default in `load` mode
- compare-related features must stay available in `load` mode
- unknown keys must never crash the merge path

## Edit Notes
- add new features only through the registry
- if a feature is legacy-only, add its anchor in `legacy_pipeline30.py`
- avoid embedding runtime code here; this module should stay declarative

## Quick Test
- run:
  - `python -m unittest discover -s tests -p "test_*.py"`

