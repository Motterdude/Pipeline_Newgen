from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


WORKFLOW_MODES = ("load", "sweep")


def normalize_workflow_mode(mode: object) -> str:
    text = str(mode or "").strip().lower()
    if text not in WORKFLOW_MODES:
        raise ValueError(f"Unsupported workflow mode: {mode!r}")
    return text


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    label: str
    description: str
    stage: str
    default_by_mode: Mapping[str, bool]
    legacy_anchor: str = ""
    notes: str = ""

    def default_enabled(self, mode: object) -> bool:
        mode_norm = normalize_workflow_mode(mode)
        return bool(self.default_by_mode.get(mode_norm, False))


@dataclass(frozen=True)
class ExecutionStep:
    feature_key: str
    label: str
    stage: str
    description: str
    enabled: bool
    legacy_anchor: str = ""
    notes: str = ""

