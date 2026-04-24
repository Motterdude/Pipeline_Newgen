# load_sweep_plan

## Role
- build the ordered execution plan for the new `load/sweep` workflow
- translate the checkbox state into explicit enabled and disabled steps

## Inputs
- workflow mode
- optional feature selection overrides

## Outputs
- ordered `ExecutionStep` list
- summary counters for enabled and disabled stages

## Do Not Break
- plan order must stay deterministic
- disabled steps must still appear in the plan so the UI and handoff can show what was intentionally skipped
- the same feature key must map to the same stage and label unless the migration explicitly changes that contract

## Edit Notes
- orchestration belongs here, not inside the UI
- keep heavy processing code out until the corresponding adapter is migrated
- if a step starts calling real code later, keep the feature key unchanged

## Quick Test
- run:
  - `python -m pipeline_newgen_rev1.cli show-plan --mode load`
  - `python -m pipeline_newgen_rev1.cli show-plan --mode sweep`

