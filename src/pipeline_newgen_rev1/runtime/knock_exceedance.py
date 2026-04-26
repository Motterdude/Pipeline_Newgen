"""Knock exceedance counting from KiBox cycle-by-cycle KPEAK data."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..adapters.kibox_reader import KiboxReadResult, _coerce_numeric_value


_KPEAK_CANDIDATES = ("KPEAK_1", "KPEAK_STAT_1")


def _extract_kpeak_values(kibox_read: KiboxReadResult) -> List[float]:
    col: Optional[str] = None
    for candidate in _KPEAK_CANDIDATES:
        if candidate in kibox_read.columns:
            col = candidate
            break
    if col is None:
        return []

    values: List[float] = []
    for row in kibox_read.rows:
        parsed = _coerce_numeric_value(row.get(col))
        if parsed is not None:
            values.append(parsed)
    return values


def count_kpeak_exceedances(
    kibox_read: KiboxReadResult,
    thresholds_bar: Sequence[float],
) -> Dict[str, object]:
    """Count cycles with KPEAK above each threshold.

    Returns dict with keys like::

        KIBOX_KPEAK_N_cycles          — total valid cycles
        KIBOX_KPEAK_above_3.0bar_n    — absolute count
        KIBOX_KPEAK_above_3.0bar_pct  — percentage (0–100)
    """
    values = _extract_kpeak_values(kibox_read)
    n_total = len(values)

    result: Dict[str, object] = {"KIBOX_KPEAK_N_cycles": n_total}

    for threshold in sorted(thresholds_bar):
        tag = f"{threshold:g}"
        if n_total == 0:
            result[f"KIBOX_KPEAK_above_{tag}bar_n"] = 0
            result[f"KIBOX_KPEAK_above_{tag}bar_pct"] = None
            result[f"KIBOX_KPEAK_above_{tag}bar_ratio"] = "0/0"
        else:
            count = sum(1 for v in values if v > threshold)
            result[f"KIBOX_KPEAK_above_{tag}bar_n"] = count
            result[f"KIBOX_KPEAK_above_{tag}bar_pct"] = round(100.0 * count / n_total, 3)
            result[f"KIBOX_KPEAK_above_{tag}bar_ratio"] = f"{count}/{n_total}"

    return result


def parse_enabled_thresholds(knock_thresholds: Sequence[Dict[str, object]]) -> List[float]:
    """Extract enabled threshold values from the config list."""
    out: List[float] = []
    for row in knock_thresholds:
        enabled = str(row.get("enabled", "1")).strip()
        if enabled not in ("1", "true", "True", "yes"):
            continue
        try:
            out.append(float(str(row.get("threshold_bar", "")).replace(",", ".")))
        except (ValueError, TypeError):
            continue
    return sorted(set(out))
