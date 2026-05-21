"""Renderer: all iterations overlay (one curve per unique dataset/run)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
if not matplotlib.get_backend():
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..final_table._helpers import _to_float
from .renderers import (
    _apply_fixed_x,
    _apply_fixed_y,
    _add_y_tolerance_guides,
    _apply_y_tick_step,
)

_CAMPAIGN_ABBR = {"baseline": "BL", "aditivado": "ADTV"}
_DIRECTION_ABBR = {"subida": "Sub", "descida": "Des"}

_CAMPAIGN_PALETTES: Dict[str, List[str]] = {
    "baseline": ["#1f77b4", "#4a9fd6", "#7ec8f0", "#a8d9f5"],
    "aditivado": ["#d62728", "#e66060", "#f09090", "#f5b0b0"],
    "": ["#7f7f7f", "#a0a0a0", "#bfbfbf", "#d9d9d9"],
}

_DIRECTION_MARKERS: Dict[str, str] = {
    "subida": "o",
    "descida": "s",
    "": "D",
}


def _derive_series_column(df: pd.DataFrame) -> pd.Series:
    """Derive a series identity column from BaseName."""
    from ..compare_iteracoes.prepare import campaign_from_basename, sentido_from_row
    from ..final_table._source_identity import (
        _basename_source_folder_parts,
        _infer_iteracao_from_folder_parts,
    )

    campaigns = []
    sentidos = []
    iteracoes = []

    for _, row in df.iterrows():
        basename = row.get("BaseName", "")
        campaigns.append(campaign_from_basename(basename))
        sentidos.append(sentido_from_row(row))
        if "Iteracao" in df.columns and pd.notna(row.get("Iteracao")):
            iteracoes.append(int(row["Iteracao"]))
        else:
            parts = _basename_source_folder_parts(basename)
            it = _infer_iteracao_from_folder_parts(parts)
            iteracoes.append(int(it) if pd.notna(it) else 1)

    keys = []
    for c, s, i in zip(campaigns, sentidos, iteracoes):
        keys.append(f"{c}_{s}_{i}")
    return pd.Series(keys, index=df.index)


def _build_series_label(key: str) -> str:
    parts = key.split("_", 2)
    if len(parts) < 3:
        return key
    campaign, direction, iteration = parts[0], parts[1], parts[2]
    c_abbr = _CAMPAIGN_ABBR.get(campaign, campaign.upper()[:4])
    d_abbr = _DIRECTION_ABBR.get(direction, direction.capitalize()[:3])
    return f"{c_abbr} {d_abbr} {iteration}"


def _style_for_series(key: str, iteration_counts: Dict[str, int]) -> Tuple[str, str]:
    parts = key.split("_", 2)
    campaign = parts[0] if len(parts) > 0 else ""
    direction = parts[1] if len(parts) > 1 else ""
    iteration = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    palette = _CAMPAIGN_PALETTES.get(campaign, _CAMPAIGN_PALETTES[""])
    color_idx = (iteration - 1) % len(palette)
    color = palette[color_idx]

    marker = _DIRECTION_MARKERS.get(direction, "D")
    return color, marker


def plot_all_iterations(
    df: pd.DataFrame,
    y_col: str,
    yerr_col: Optional[str],
    title: str,
    filename: str,
    y_label: str,
    fixed_y: Optional[Tuple[float, float, float]] = None,
    fixed_y_limits: Optional[Tuple[float, float]] = None,
    y_tick_step: Optional[float] = None,
    fixed_x: Optional[Tuple[float, float, float]] = None,
    x_col: str = "Load_kW",
    x_label: str = "Power (kW)",
    fuels_override: Optional[List[int]] = None,
    series_col: Optional[str] = None,
    plot_dir: Optional[Path] = None,
    y_tol_plus: object = 0.0,
    y_tol_minus: object = 0.0,
    fuel_colors: Optional[Dict[str, str]] = None,
    return_fig: bool = False,
    style_overrides: Optional[Dict[str, Dict[str, str]]] = None,
) -> Optional[bool]:
    """Plot all iterations overlaid — one curve per unique dataset (campaign+direction+iteration)."""
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")
    if not return_fig:
        target_dir.mkdir(parents=True, exist_ok=True)

    if "BaseName" not in df.columns:
        from .renderers import plot_all_fuels
        return plot_all_fuels(
            df, y_col=y_col, yerr_col=yerr_col, title=title,
            filename=filename, y_label=y_label, fixed_y=fixed_y,
            fixed_y_limits=fixed_y_limits, y_tick_step=y_tick_step,
            fixed_x=fixed_x, x_col=x_col, x_label=x_label,
            fuels_override=fuels_override, series_col=series_col,
            plot_dir=plot_dir, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
            fuel_colors=fuel_colors, return_fig=return_fig,
        )

    work = df.copy()
    work["_series_key"] = _derive_series_column(work)

    iteration_counts: Dict[str, int] = {}
    for key in work["_series_key"].unique():
        parts = key.split("_", 2)
        campaign = parts[0] if parts else ""
        iteration_counts[campaign] = iteration_counts.get(campaign, 0) + 1

    plt.figure(figsize=(10, 6))
    any_curve = False

    for key in sorted(work["_series_key"].unique()):
        group = work[work["_series_key"] == key].copy()
        group[x_col] = pd.to_numeric(group[x_col], errors="coerce")
        group[y_col] = pd.to_numeric(group[y_col], errors="coerce")

        if yerr_col and yerr_col in group.columns:
            group[yerr_col] = pd.to_numeric(group[yerr_col], errors="coerce")
            group = group.dropna(subset=[x_col, y_col, yerr_col]).sort_values(x_col)
        else:
            group = group.dropna(subset=[x_col, y_col]).sort_values(x_col)

        if group.empty:
            continue

        any_curve = True
        if style_overrides and key in style_overrides:
            color = style_overrides[key].get("color", "#888888")
            marker = style_overrides[key].get("marker", "o")
        else:
            color, marker = _style_for_series(key, iteration_counts)
        label = _build_series_label(key)
        fmt = f"{marker}-"

        if yerr_col and yerr_col in group.columns:
            plt.errorbar(
                group[x_col], group[y_col], yerr=group[yerr_col],
                fmt=fmt, capsize=3, color=color, label=label,
                linewidth=1.6, markersize=5.5, picker=5,
            )
        else:
            plt.plot(
                group[x_col], group[y_col], fmt,
                color=color, label=label, linewidth=1.6, markersize=5.5, picker=5,
            )

    if not any_curve:
        plt.close()
        if return_fig:
            return None
        return False

    _apply_fixed_x(fixed_x)
    _apply_fixed_y(fixed_y, fixed_y_limits)

    ax = plt.gca()
    guide_entries = _add_y_tolerance_guides(ax, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus)
    if fixed_y is None:
        _apply_y_tick_step(ax, y_tick_step)

    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend(loc="best", fontsize=9, ncol=2 if any_curve else 1)
    plt.tight_layout()

    if return_fig:
        return plt.gcf()
    outpath = target_dir / filename
    plt.savefig(outpath, dpi=200)
    plt.close()
    return True
