"""Shared fuel-blend color resolution for all plots.

Every renderer should use ``fuel_color_map()`` so that the same fuel
always gets the same color across unitary plots, knock histograms, etc.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_FUEL_COLORS: Dict[str, str] = {
    "D85B15": "#1f77b4",
    "E94H6":  "#ff7f0e",
    "E75H25": "#2ca02c",
    "E65H35": "#d62728",
}

FUEL_COLOR_PREFIX = "FUEL_COLOR_"


def resolve_fuel_color(
    fuel_label: str,
    defaults: Dict[str, str],
) -> Optional[str]:
    key = f"{FUEL_COLOR_PREFIX}{fuel_label}"
    custom = defaults.get(key, "").strip()
    if custom:
        return custom
    return DEFAULT_FUEL_COLORS.get(fuel_label)


def _extract_fuel_part(label: str) -> str:
    if " | " in label:
        return label.rsplit(" | ", 1)[-1].strip()
    return label


def fuel_color_map(
    fuel_labels: Sequence[str],
    defaults: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    defs = defaults or {}
    cmap = plt.cm.tab10
    result: Dict[str, str] = {}
    fallback_idx = 0
    for label in fuel_labels:
        if label in result:
            continue
        fuel_part = _extract_fuel_part(label)
        color = resolve_fuel_color(fuel_part, defs)
        if color:
            result[label] = color
        else:
            rgba = cmap(fallback_idx % 10)
            result[label] = matplotlib.colors.to_hex(rgba)
            fallback_idx += 1
    return result
