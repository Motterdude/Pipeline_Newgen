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
) -> tuple[np.ndarray, np.ndarray]:
    """Empirical complementary CDF using Weibull plotting positions.

    Returns (x, exceedance_pct) — one point per observation, monotonically
    decreasing, never zero (safe for log scale).
    """
    values = np.sort(np.asarray(kpeak_values, dtype=float))
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return np.array([]), np.array([])
    ranks = np.arange(1, n + 1)
    exceedance_pct = 100.0 * (n - ranks + 1) / (n + 1)
    return values, exceedance_pct


_FUEL_PREFERRED_ORDER = ["D85B15", "E94H6", "E75H25", "E65H35"]


def _sorted_fuel_labels(labels: Sequence[str]) -> List[str]:
    ordered = [f for f in _FUEL_PREFERRED_ORDER if f in labels]
    extras = sorted(set(labels) - set(ordered))
    return ordered + extras


def plot_knock_exceedance_pct(
    data_by_fuel: Dict[str, List[float]],
    output_path: Path,
    title: str = "KPEAK Exceedance Distribution (all fuels)",
    fuel_colors: Optional[Dict[str, str]] = None,
) -> Optional[Path]:
    """Exceedance as percentage (0-100%), linear axes."""
    if not data_by_fuel:
        return None

    from .fuel_colors import fuel_color_map
    sorted_labels = _sorted_fuel_labels(list(data_by_fuel.keys()))
    colors = fuel_colors or fuel_color_map(sorted_labels)

    fig, ax = plt.subplots(figsize=(10, 6))
    any_curve = False

    for fuel_label in sorted_labels:
        values = data_by_fuel[fuel_label]
        x, exceedance = compute_kpeak_exceedance(values)
        if len(x) == 0:
            continue
        any_curve = True
        ax.plot(x, exceedance, "-", color=colors.get(fuel_label),
                linewidth=1.8, label=fuel_label)

    if not any_curve:
        plt.close(fig)
        return None

    ax.set_xlabel("KPEAK intensity (bar)")
    ax.set_ylabel("Cycles exceeding threshold (%)")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=105)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    print(f"[OK] Salvei {output_path}")
    return output_path


CycleScaleMode = Literal["linear", "log2"]


def plot_knock_cycle_count(
    data_by_fuel: Dict[str, List[float]],
    output_path: Path,
    title: str = "KPEAK Exceedance — Cycle Count",
    y_scale: CycleScaleMode = "linear",
    fuel_colors: Optional[Dict[str, str]] = None,
) -> Optional[Path]:
    """Exceedance as absolute cycle count, x from 0-20 bar."""
    if not data_by_fuel:
        return None

    from .fuel_colors import fuel_color_map
    sorted_labels = _sorted_fuel_labels(list(data_by_fuel.keys()))
    colors = fuel_colors or fuel_color_map(sorted_labels)

    fig, ax = plt.subplots(figsize=(10, 6))
    any_curve = False

    for fuel_label in sorted_labels:
        values = data_by_fuel[fuel_label]
        x, exc_pct = compute_kpeak_exceedance(values)
        if len(x) == 0:
            continue
        any_curve = True
        n = len(values)
        cycles = exc_pct * (n + 1) / 100.0
        ax.plot(x, cycles, "-", color=colors.get(fuel_label),
                linewidth=1.8, label=fuel_label)

    if not any_curve:
        plt.close(fig)
        return None

    if y_scale == "log2":
        ax.set_yscale("log", base=2)
        ax.set_ylim(bottom=1, top=256)
        title = title + " [log2]"
    else:
        ax.set_ylim(bottom=0)

    ax.set_xlabel("KPEAK intensity (bar)")
    ax.set_ylabel("Cycles exceeding threshold")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0, right=20)
    ax.set_xticks(np.arange(0, 22, 2))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    print(f"[OK] Salvei {output_path}")
    return output_path


# backward compat alias
plot_knock_histogram = plot_knock_exceedance_pct
