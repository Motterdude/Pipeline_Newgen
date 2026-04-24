from __future__ import annotations

from dataclasses import replace
from math import isfinite

from .constants import (
    DEFAULT_SWEEP_BIN_TOL,
    DEFAULT_SWEEP_KEY,
    RUNTIME_AGGREGATION_LOAD,
    RUNTIME_AGGREGATION_SWEEP,
    SWEEP_AXIS_LABELS,
    SWEEP_FILENAME_PATTERNS,
    SWEEP_VALUE_COL,
)
from .models import RuntimeSelection


def _to_text(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object, default: float) -> float:
    try:
        parsed = float(str(value).replace(",", "."))
    except Exception:
        return default
    return parsed


def normalize_runtime_aggregation_mode(value: object) -> str:
    text = _to_text(value).lower()
    if text in {RUNTIME_AGGREGATION_SWEEP, "lambda", "varredura", "sweep_mode"}:
        return RUNTIME_AGGREGATION_SWEEP
    return RUNTIME_AGGREGATION_LOAD


def normalize_sweep_key(value: object) -> str:
    text = _to_text(value).lower()
    if not text:
        return DEFAULT_SWEEP_KEY
    for canonical, _pattern in SWEEP_FILENAME_PATTERNS:
        if text == canonical:
            return canonical
    return text


def normalize_sweep_x_col(value: object) -> str:
    text = _to_text(value)
    return text if text else SWEEP_VALUE_COL


def normalize_sweep_bin_tol(value: object) -> float:
    tol = _to_float(value, DEFAULT_SWEEP_BIN_TOL)
    if not isfinite(tol):
        return DEFAULT_SWEEP_BIN_TOL
    return max(float(tol), 0.0)


def sweep_axis_label(key: object) -> str:
    canonical = normalize_sweep_key(key)
    if not canonical:
        return SWEEP_AXIS_LABELS[DEFAULT_SWEEP_KEY]
    return SWEEP_AXIS_LABELS.get(canonical, canonical.upper())


def normalize_runtime_selection(selection: RuntimeSelection) -> RuntimeSelection:
    return replace(
        selection,
        aggregation_mode=normalize_runtime_aggregation_mode(selection.aggregation_mode),
        sweep_key=normalize_sweep_key(selection.sweep_key),
        sweep_x_col=normalize_sweep_x_col(selection.sweep_x_col),
        sweep_bin_tol=normalize_sweep_bin_tol(selection.sweep_bin_tol),
    )

