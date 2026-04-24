# legacy_pipeline30_anchors

## Role
- map each new feature flag to the current implementation anchor in the legacy monolith
- give the migration a traceable path from new modules back to `nanum_pipeline_30.py` or `nanum_pipeline_29.py`

## Inputs
- feature key
- project root when resolving the sibling legacy workspace

## Outputs
- legacy anchor string
- default sibling path for the current legacy workspace

## Do Not Break
- anchor names should stay readable and grep-friendly
- this file must not import the legacy monolith directly during tests

## Edit Notes
- update anchors whenever code is physically migrated out of the monolith
- if a legacy function is split into multiple new modules, keep the anchor until the old implementation is fully retired

## Quick Test
- run:
  - `python -m unittest discover -s tests -p "test_*.py"`

