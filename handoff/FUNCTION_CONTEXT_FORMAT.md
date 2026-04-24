# Function Context Format

## Purpose
`*.fnctx.md` is the low-context operational file for one public function, module entrypoint, or tightly related function cluster.

## Why this exists
- `HANDOFF_MASTER.md` keeps the full narrative and historical detail;
- `*.fnctx.md` keeps only the edit-critical operational facts so AI edits can stay fast and focused.

## File naming
- one file per function or function cluster
- format:
  - `<topic>.fnctx.md`
- examples:
  - `load_sweep_plan.fnctx.md`
  - `feature_flags.fnctx.md`
  - `legacy_pipeline30_anchors.fnctx.md`

## Required sections
- `Role`
  - what the function or module is responsible for
- `Inputs`
  - key parameters, state, files, or environment assumptions
- `Outputs`
  - return value, side effects, files written, or state updated
- `Do Not Break`
  - invariants that must stay true
- `Edit Notes`
  - what is safe to change and what should be migrated elsewhere later
- `Quick Test`
  - one short validation path after editing

## Size target
- ideal size: `20-60` lines
- if it grows too much, split the topic or promote the historical content back to `HANDOFF_MASTER.md`

