"""Knock histogram: KPEAK exceedance distribution curve per fuel."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def compute_kpeak_exceedance(
    kpeak_values: Sequence[float],
    n_points: int = 500,
) -> tuple[np.ndarray, np.ndarray]:
    """Complementary CDF: for each x, P(KPEAK > x) as percentage.

    Returns (x, exceedance_pct) where x goes from 0 to max(KPEAK)*1.02
    and exceedance_pct goes from ~100% down to 0%, monotonically decreasing.
    """
    values = np.sort(np.asarray(kpeak_values, dtype=float))
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return np.array([]), np.array([])
    x = np.linspace(0, float(values[-1]) * 1.02, n_points)
    exceed_count = n - np.searchsorted(values, x, side="right")
    exceedance_pct = 100.0 * exceed_count / n
    return x, exceedance_pct


_FUEL_PREFERRED_ORDER = ["D85B15", "E94H6", "E75H25", "E65H35"]


def _sorted_fuel_labels(labels: Sequence[str]) -> List[str]:
    ordered = [f for f in _FUEL_PREFERRED_ORDER if f in labels]
    extras = sorted(set(labels) - set(ordered))
    return ordered + extras


YScaleMode = Literal["linear", "log10", "log2"]


def plot_knock_histogram(
    data_by_fuel: Dict[str, List[float]],
    output_path: Path,
    title: str = "KPEAK Exceedance Distribution (all fuels)",
    x_label: str = "KPEAK intensity (bar)",
    y_label: str = "Cycles exceeding threshold (%)",
    x_max_override: Optional[float] = None,
    y_scale: YScaleMode = "linear",
    n_points: int = 500,
    fuel_colors: Optional[Dict[str, str]] = None,
) -> Optional[Path]:
    if not data_by_fuel:
        return None

    from .fuel_colors import fuel_color_map
    sorted_labels = _sorted_fuel_labels(list(data_by_fuel.keys()))
    colors = fuel_colors or fuel_color_map(sorted_labels)

    fig, ax = plt.subplots(figsize=(10, 6))
    any_curve = False

    for fuel_label in sorted_labels:
        values = data_by_fuel[fuel_label]
        x, exceedance = compute_kpeak_exceedance(values, n_points=n_points)
        if len(x) == 0:
            continue
        any_curve = True
        color = colors.get(fuel_label)
        ax.plot(x, exceedance, "-", color=color, linewidth=1.8, label=fuel_label)

    if not any_curve:
        plt.close(fig)
        return None

    if y_scale == "log10":
        ax.set_yscale("log", base=10)
        y_label = y_label.replace("(%)", "(%, log10)")
        title = title + " [log10]"
    elif y_scale == "log2":
        ax.set_yscale("log", base=2)
        y_label = y_label.replace("(%)", "(%, log2)")
        title = title + " [log2]"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    if x_max_override and np.isfinite(x_max_override):
        ax.set_xlim(left=0, right=x_max_override)
    else:
        ax.set_xlim(left=0)

    if y_scale == "linear":
        ax.set_ylim(bottom=0, top=105)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    print(f"[OK] Salvei {output_path}")
    return output_path
