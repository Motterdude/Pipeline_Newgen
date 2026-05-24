"""Preview renderers for compare_iteracoes data.

All functions return a matplotlib Figure (never save to disk).
Designed to be called from PreviewPlotTab for interactive inline rendering.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

_SERIES_MARKERS = ["o", "s", "D", "^", "v", "<", ">", "P", "X", "*", "h", "d"]
_SERIES_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]


def _style_for_index(idx: int) -> Tuple[str, str]:
    marker = _SERIES_MARKERS[idx % len(_SERIES_MARKERS)]
    color = _SERIES_COLORS[idx % len(_SERIES_COLORS)]
    return marker, color


def load_compare_xlsx(path: Path) -> pd.DataFrame:
    """Load compare_iteracoes_metricas_incertezas.xlsx into a DataFrame."""
    df = pd.read_excel(path, engine="calamine")
    if "Load_kW" in df.columns:
        df["Load_kW"] = pd.to_numeric(df["Load_kW"], errors="coerce")
    return df


def available_metrics(df: pd.DataFrame) -> List[str]:
    """Return sorted list of unique Metrica values in the compare DataFrame."""
    if df is None or df.empty or "Metrica" not in df.columns:
        return []
    return sorted(df["Metrica"].dropna().unique().tolist())


def available_comparacoes(df: pd.DataFrame, metrica: Optional[str] = None) -> List[str]:
    """Return sorted list of unique Comparacao values, optionally filtered by metrica."""
    if df is None or df.empty or "Comparacao" not in df.columns:
        return []
    subset = df
    if metrica and "Metrica" in df.columns:
        subset = df[df["Metrica"].eq(metrica)]
    return sorted(subset["Comparacao"].dropna().unique().tolist())


def render_compare_absolute_preview(
    df: pd.DataFrame,
    *,
    metrica: str,
    comparacao: str,
    include_uncertainty: bool = True,
    title: Optional[str] = None,
) -> Optional[Figure]:
    """Render 2-curve absolute comparison (left vs right) for a single metric+pair."""
    import matplotlib.pyplot as plt

    subset = df[df["Metrica"].eq(metrica) & df["Comparacao"].eq(comparacao)].copy()
    if subset.empty:
        return None

    subset = subset.sort_values("Load_kW")
    x = subset["Load_kW"]
    y_left = pd.to_numeric(subset.get("value_left", pd.NA), errors="coerce")
    y_right = pd.to_numeric(subset.get("value_right", pd.NA), errors="coerce")
    u_left = pd.to_numeric(subset.get("U_left", pd.NA), errors="coerce")
    u_right = pd.to_numeric(subset.get("U_right", pd.NA), errors="coerce")

    label_left = subset["label_left"].iloc[0] if "label_left" in subset.columns else "Left"
    label_right = subset["label_right"].iloc[0] if "label_right" in subset.columns else "Right"

    fig, ax = plt.subplots(figsize=(9, 5.5))

    has_left = y_left.notna().any()
    has_right = y_right.notna().any()

    if has_left:
        if include_uncertainty and u_left.notna().any():
            ax.errorbar(x, y_left, yerr=u_left, fmt="o-", capsize=3,
                        linewidth=1.8, markersize=5, color="#1f77b4", label=label_left)
        else:
            ax.plot(x, y_left, "o-", linewidth=1.8, markersize=5, color="#1f77b4", label=label_left)

    if has_right:
        if include_uncertainty and u_right.notna().any():
            ax.errorbar(x, y_right, yerr=u_right, fmt="s-", capsize=3,
                        linewidth=1.8, markersize=5, color="#d62728", label=label_right)
        else:
            ax.plot(x, y_right, "s-", linewidth=1.8, markersize=5, color="#d62728", label=label_right)

    ax.set_xlabel("Carga nominal (kW)")
    y_label = metrica
    if "Incerteza" in subset.columns:
        inc = subset["Incerteza"].iloc[0]
        if inc == "sem":
            y_label += " (sem incerteza)"
    ax.set_ylabel(y_label)
    ax.set_title(title or f"{metrica} — {comparacao}")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def render_compare_delta_preview(
    df: pd.DataFrame,
    *,
    metrica: str,
    comparacao: str,
    include_uncertainty: bool = True,
    title: Optional[str] = None,
) -> Optional[Figure]:
    """Render delta-percentage plot for a single metric+pair."""
    import matplotlib.pyplot as plt

    subset = df[df["Metrica"].eq(metrica) & df["Comparacao"].eq(comparacao)].copy()
    if subset.empty:
        return None

    subset = subset.sort_values("Load_kW")
    x = subset["Load_kW"]
    delta = pd.to_numeric(subset.get("delta_pct", pd.NA), errors="coerce")
    u_delta = pd.to_numeric(subset.get("U_delta_pct", pd.NA), errors="coerce")

    delta_mode = "ratio"
    if "delta_mode" in subset.columns:
        delta_mode = str(subset["delta_mode"].iloc[0]).strip() or "ratio"

    label_right = subset["label_right"].iloc[0] if "label_right" in subset.columns else "Right"
    line_label = f"Delta: {comparacao}"

    fig, ax = plt.subplots(figsize=(9, 5.5))

    if include_uncertainty and u_delta.notna().any():
        ax.errorbar(x, delta, yerr=u_delta, fmt="o-", capsize=3,
                    linewidth=1.8, markersize=5, color="#2ca02c", label=line_label)
    else:
        ax.plot(x, delta, "o-", linewidth=1.8, markersize=5, color="#2ca02c", label=line_label)

    ref_label = "0 pp" if delta_mode == "diff" else "0%"
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label=ref_label)

    ax.set_xlabel("Carga nominal (kW)")
    y_axis_label = "Diferenca (pp)" if delta_mode == "diff" else "Delta percentual (%)"
    ax.set_ylabel(y_axis_label)
    ax.set_title(title or f"Delta — {metrica} — {comparacao}")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best")

    note = f"Negativo = {label_right} menor; Positivo = {label_right} maior"
    fig.text(0.01, 0.01, note, fontsize=8, alpha=0.85)
    fig.tight_layout()
    return fig


def render_compare_all_overlay(
    df: pd.DataFrame,
    *,
    metrica: str,
    include_uncertainty: bool = True,
    title: Optional[str] = None,
    series_filter: Optional[List[str]] = None,
) -> Optional[Figure]:
    """Render ALL series for a metric overlaid on the same graph.

    Extracts unique series labels from the XLSX (both left and right sides)
    and plots each with a distinct marker and color.

    Args:
        series_filter: if provided, only plot series whose label is in this list.
    """
    import matplotlib.pyplot as plt

    subset = df[df["Metrica"].eq(metrica)].copy()
    if subset.empty:
        return None

    series_data: Dict[str, pd.DataFrame] = {}

    for _, row in subset.iterrows():
        load = row.get("Load_kW")
        if pd.isna(load):
            continue

        lbl_left = str(row.get("label_left", "")).strip()
        lbl_right = str(row.get("label_right", "")).strip()
        val_left = row.get("value_left")
        val_right = row.get("value_right")
        u_left = row.get("U_left")
        u_right = row.get("U_right")

        if lbl_left and not pd.isna(val_left):
            if lbl_left not in series_data:
                series_data[lbl_left] = []
            series_data[lbl_left].append({"Load_kW": load, "value": val_left, "U": u_left})

        if lbl_right and not pd.isna(val_right):
            if lbl_right not in series_data:
                series_data[lbl_right] = []
            series_data[lbl_right].append({"Load_kW": load, "value": val_right, "U": u_right})

    if not series_data:
        return None

    if series_filter:
        series_data = {k: v for k, v in series_data.items() if k in series_filter}
        if not series_data:
            return None

    # Deduplicate points per series (same Load_kW may appear in multiple comparison rows)
    clean_series: Dict[str, pd.DataFrame] = {}
    for label, rows_list in series_data.items():
        sdf = pd.DataFrame(rows_list)
        sdf["Load_kW"] = pd.to_numeric(sdf["Load_kW"], errors="coerce")
        sdf["value"] = pd.to_numeric(sdf["value"], errors="coerce")
        sdf["U"] = pd.to_numeric(sdf["U"], errors="coerce")
        sdf = sdf.dropna(subset=["Load_kW", "value"])
        sdf = sdf.groupby("Load_kW", as_index=False).first()
        sdf = sdf.sort_values("Load_kW")
        if not sdf.empty:
            clean_series[label] = sdf

    if not clean_series:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    for idx, (label, sdf) in enumerate(sorted(clean_series.items())):
        marker, color = _style_for_index(idx)
        fmt = f"{marker}-"
        x = sdf["Load_kW"]
        y = sdf["value"]
        u = sdf["U"]

        if include_uncertainty and u.notna().any():
            ax.errorbar(x, y, yerr=u, fmt=fmt, capsize=3,
                        linewidth=1.6, markersize=5.5, color=color, label=label)
        else:
            ax.plot(x, y, fmt, linewidth=1.6, markersize=5.5, color=color, label=label)

    ax.set_xlabel("Carga nominal (kW)")
    ax.set_ylabel(metrica)
    ax.set_title(title or f"{metrica} — Todas as series")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    return fig


def render_compare_delta_all_overlay(
    df: pd.DataFrame,
    *,
    metrica: str,
    include_uncertainty: bool = True,
    title: Optional[str] = None,
    comparacoes_filter: Optional[List[str]] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
) -> Optional[Figure]:
    """Render ALL delta curves for a metric overlaid on the same graph.

    Each comparison pair gets its own curve with distinct marker/color.
    """
    import matplotlib.pyplot as plt

    subset = df[df["Metrica"].eq(metrica)].copy()
    if subset.empty:
        return None

    if comparacoes_filter:
        subset = subset[subset["Comparacao"].isin(comparacoes_filter)]
        if subset.empty:
            return None

    comparacoes = sorted(subset["Comparacao"].dropna().unique().tolist())
    if not comparacoes:
        return None

    delta_mode = "ratio"
    if "delta_mode" in subset.columns:
        dm = subset["delta_mode"].dropna()
        if not dm.empty:
            delta_mode = str(dm.iloc[0]).strip() or "ratio"

    fig, ax = plt.subplots(figsize=(10, 6))

    for idx, comp in enumerate(comparacoes):
        comp_data = subset[subset["Comparacao"].eq(comp)].sort_values("Load_kW")
        if comp_data.empty:
            continue

        marker, color = _style_for_index(idx)
        fmt = f"{marker}-"
        x = comp_data["Load_kW"]
        delta = pd.to_numeric(comp_data["delta_pct"], errors="coerce")
        u_delta = pd.to_numeric(comp_data.get("U_delta_pct", pd.NA), errors="coerce")

        if include_uncertainty and u_delta.notna().any():
            ax.errorbar(x, delta, yerr=u_delta, fmt=fmt, capsize=3,
                        linewidth=1.6, markersize=5.5, color=color, label=comp)
        else:
            ax.plot(x, delta, fmt, linewidth=1.6, markersize=5.5, color=color, label=comp)

    ref_label = "0 pp" if delta_mode == "diff" else "0%"
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label=ref_label)

    default_y_label = "Diferenca (pp)" if delta_mode == "diff" else "Delta percentual (%)"
    ax.set_xlabel(x_label or "Carga nominal (kW)")
    ax.set_ylabel(y_label or default_y_label)
    ax.set_title(title or f"Delta — {metrica}")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    return fig
