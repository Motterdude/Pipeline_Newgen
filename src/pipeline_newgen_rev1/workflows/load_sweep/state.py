from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from ...models import normalize_workflow_mode
from .feature_flags import merge_feature_selection


def default_feature_state_path(project_root: Path) -> Path:
    return project_root / "config" / "load_sweep_feature_defaults.json"


def load_feature_state(path: Path, mode: object) -> Dict[str, bool]:
    mode_norm = normalize_workflow_mode(mode)
    if not path.exists():
        return merge_feature_selection(mode_norm)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get(mode_norm, {})
    if not isinstance(raw, dict):
        return merge_feature_selection(mode_norm)
    cleaned = {str(key): bool(value) for key, value in raw.items()}
    return merge_feature_selection(mode_norm, cleaned)


def save_feature_state(path: Path, mode: object, selection: Dict[str, bool]) -> None:
    mode_norm = normalize_workflow_mode(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload[mode_norm] = {str(key): bool(value) for key, value in selection.items()}
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

