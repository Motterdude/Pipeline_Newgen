from __future__ import annotations

from collections import Counter
from typing import Dict, List

from ...models import ExecutionStep, normalize_workflow_mode
from .feature_flags import LOAD_SWEEP_FEATURE_SPECS, merge_feature_selection


STAGE_ORDER = {
    "config": 0,
    "runtime": 1,
    "input": 2,
    "diagnostics": 3,
    "processing": 4,
    "export": 5,
    "plotting": 6,
}


def build_load_sweep_plan(mode: object, selection: Dict[str, bool] | None = None) -> List[ExecutionStep]:
    mode_norm = normalize_workflow_mode(mode)
    merged = merge_feature_selection(mode_norm, selection)
    steps: List[ExecutionStep] = []
    for spec in LOAD_SWEEP_FEATURE_SPECS:
        steps.append(
            ExecutionStep(
                feature_key=spec.key,
                label=spec.label,
                stage=spec.stage,
                description=spec.description,
                enabled=bool(merged.get(spec.key, False)),
                legacy_anchor=spec.legacy_anchor,
                notes=spec.notes,
            )
        )
    steps.sort(key=lambda step: (STAGE_ORDER.get(step.stage, 999), step.label.lower(), step.feature_key))
    return steps


def summarize_plan(steps: List[ExecutionStep]) -> Dict[str, object]:
    stage_counts = Counter(step.stage for step in steps if step.enabled)
    return {
        "total_steps": len(steps),
        "enabled_steps": sum(1 for step in steps if step.enabled),
        "disabled_steps": sum(1 for step in steps if not step.enabled),
        "enabled_stage_counts": dict(sorted(stage_counts.items())),
    }


def plan_as_markdown(steps: List[ExecutionStep]) -> str:
    lines = ["# Load/Sweep Plan", ""]
    current_stage = None
    for step in steps:
        if step.stage != current_stage:
            current_stage = step.stage
            lines.append(f"## {current_stage}")
        marker = "[x]" if step.enabled else "[ ]"
        lines.append(f"- {marker} `{step.feature_key}` - {step.label}")
        lines.append(f"  - {step.description}")
        if step.legacy_anchor:
            lines.append(f"  - Legacy anchor: `{step.legacy_anchor}`")
        if step.notes:
            lines.append(f"  - Notes: {step.notes}")
    return "\n".join(lines).strip() + "\n"
