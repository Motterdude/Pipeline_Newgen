"""Matplotlib renderers for unitary plots.

Three renderers + visual helpers.  Port of legacy L5944-7900.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..final_table._helpers import _to_float
from ..fuel_colors import fuel_color_map
from .fuel_groups import series_fuel_plot_groups


# ── visual helpers ──────────────────────────────────────────────────

def _normalize_tol_value(v: object) -> float:
    x = _to_float(v, 0.0)
    if not np.isfinite(x):
        return 0.0
    return abs(float(x))


def _add_y_tolerance_guides(
    ax: plt.Axes,
    y_tol_plus: object,
    y_tol_minus: object,
) -> int:
    tp = _normalize_tol_value(y_tol_plus)
    tm = _normalize_tol_value(y_tol_minus)
    n = 0
    if tp > 0:
        ax.axhline(tp, color="red", linestyle="--", linewidth=1.2, label=f"limite +{tp:g}")
        n += 1
    if tm > 0:
        ax.axhline(-tm, color="red", linestyle="--", linewidth=1.2, label=f"limite -{tm:g}")
        n += 1
    return n


def _apply_y_tick_step(ax: plt.Axes, y_tick_step: Optional[float]) -> None:
    step = _to_float(y_tick_step, default=np.nan)
    if not np.isfinite(step) or step <= 0:
        return
    ymin, ymax = ax.get_ylim()
    if not (np.isfinite(ymin) and np.isfinite(ymax)):
        return
    eps = abs(step) * 1e-9
    snapped_min = np.floor((ymin + eps) / step) * step
    snapped_max = np.ceil((ymax - eps) / step) * step
    if not (np.isfinite(snapped_min) and np.isfinite(snapped_max)) or snapped_max <= snapped_min:
        return
    ticks = np.arange(snapped_min, snapped_max + (step * 0.5), step).tolist()
    if not ticks:
        return
    ax.set_yticks(ticks)
    ax.set_ylim(snapped_min, snapped_max)


def _add_xy_value_table(
    ax: plt.Axes,
    rows: List[Tuple[str, object, object]],
    max_rows: int = 12,
) -> None:
    return


def _annotate_points_variants(ax, x: np.ndarray, y: np.ndarray, variant: str) -> None:
    for xi, yi in zip(x, y):
        if not np.isfinite(xi) or not np.isfinite(yi):
            continue
        txt = f"{yi:.2f}"
        if variant == "box":
            ax.text(xi, yi, txt, fontsize=8, ha="left", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="black", lw=0.6))
        elif variant == "tag":
            ax.annotate(txt, xy=(xi, yi), xytext=(6, 6), textcoords="offset points",
                        fontsize=8, ha="left", va="bottom",
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="black", lw=0.6),
                        arrowprops=dict(arrowstyle="->", lw=0.6))
        elif variant == "marker":
            ax.text(xi, yi, txt, fontsize=8, ha="center", va="bottom")
        elif variant == "badge":
            ax.text(xi, yi, txt, fontsize=8, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="black", lw=0.6, alpha=0.75))
        else:
            ax.text(xi, yi, txt, fontsize=8, ha="left", va="bottom")


# ── axis / layout helpers ───────────────────────────────────────────

def _apply_fixed_x(fixed_x: Optional[Tuple[float, float, float]]) -> None:
    if fixed_x is None:
        return
    xmin, xmax, xstep = fixed_x
    plt.xlim(xmin, xmax)
    try:
        ticks = np.arange(xmin, xmax + 1e-12, xstep).tolist()
        plt.xticks(ticks)
    except Exception:
        pass


def _apply_fixed_y(
    fixed_y: Optional[Tuple[float, float, float]],
    fixed_y_limits: Optional[Tuple[float, float]],
) -> None:
    if fixed_y is not None:
        ymin, ymax, ystep = fixed_y
        plt.ylim(ymin, ymax)
        try:
            ticks = np.arange(ymin, ymax + 1e-12, ystep).tolist()
            plt.yticks(ticks)
        except Exception:
            pass
    elif fixed_y_limits is not None:
        ymin, ymax = fixed_y_limits
        plt.ylim(ymin, ymax)


def _apply_fixed_y_ax(
    ax,
    fixed_y: Optional[Tuple[float, float, float]],
    fixed_y_limits: Optional[Tuple[float, float]],
) -> None:
    if fixed_y is not None:
        ymin, ymax, ystep = fixed_y
        ax.set_ylim(ymin, ymax)
        try:
            ticks = np.arange(ymin, ymax + 1e-12, ystep).tolist()
            ax.set_yticks(ticks)
        except Exception:
            pass
    elif fixed_y_limits is not None:
        ymin, ymax = fixed_y_limits
        ax.set_ylim(ymin, ymax)


def _apply_fixed_x_ax(ax, fixed_x: Optional[Tuple[float, float, float]]) -> None:
    if fixed_x is None:
        return
    xmin, xmax, xstep = fixed_x
    ax.set_xlim(xmin, xmax)
    try:
        ticks = np.arange(xmin, xmax + 1e-12, xstep).tolist()
        ax.set_xticks(ticks)
    except Exception:
        pass


# ── renderers ───────────────────────────────────────────────────────

def plot_all_fuels(
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
) -> bool:
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")
    target_dir.mkdir(parents=True, exist_ok=True)

    groups = series_fuel_plot_groups(df, fuels_override=fuels_override, series_col=series_col)
    colors = fuel_colors or fuel_color_map([g[0] or "" for g in groups])

    plt.figure()
    any_curve = False
    legend_entries = 0
    table_rows: List[Tuple[str, object, object]] = []

    for label, d in groups:
        color = colors.get(label or "")
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        if yerr_col:
            d[yerr_col] = pd.to_numeric(d[yerr_col], errors="coerce")
            d = d.dropna(subset=[x_col, y_col, yerr_col]).sort_values(x_col)
        else:
            d = d.dropna(subset=[x_col, y_col]).sort_values(x_col)
        if d.empty:
            continue
        for xi, yi in zip(d[x_col].tolist(), d[y_col].tolist()):
            table_rows.append((label or "", xi, yi))
        any_curve = True
        if yerr_col:
            if label:
                plt.errorbar(d[x_col], d[y_col], yerr=d[yerr_col], fmt="o-", capsize=3, color=color, label=label)
                legend_entries += 1
            else:
                plt.errorbar(d[x_col], d[y_col], yerr=d[yerr_col], fmt="o-", capsize=3, color=color)
        else:
            if label:
                plt.plot(d[x_col], d[y_col], "o-", color=color, label=label)
                legend_entries += 1
            else:
                plt.plot(d[x_col], d[y_col], "o-", color=color)

    if not any_curve:
        plt.close()
        print(f"[WARN] Sem dados para plot {filename}")
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
    _add_xy_value_table(ax, table_rows)
    if legend_entries > 0 or guide_entries > 0:
        plt.legend()
    outpath = target_dir / filename
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"[OK] Salvei {outpath}")
    return True


def plot_all_fuels_xy(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    yerr_col: Optional[str],
    title: str,
    filename: str,
    x_label: str,
    y_label: str,
    fixed_y: Optional[Tuple[float, float, float]] = None,
    fixed_y_limits: Optional[Tuple[float, float]] = None,
    y_tick_step: Optional[float] = None,
    fixed_x: Optional[Tuple[float, float, float]] = None,
    fuels_override: Optional[List[int]] = None,
    series_col: Optional[str] = None,
    plot_dir: Optional[Path] = None,
    y_tol_plus: object = 0.0,
    y_tol_minus: object = 0.0,
    fuel_colors: Optional[Dict[str, str]] = None,
) -> bool:
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")
    target_dir.mkdir(parents=True, exist_ok=True)

    groups = series_fuel_plot_groups(df, fuels_override=fuels_override, series_col=series_col)
    colors = fuel_colors or fuel_color_map([g[0] or "" for g in groups])

    plt.figure()
    any_curve = False
    legend_entries = 0
    table_rows: List[Tuple[str, object, object]] = []

    for label, d in groups:
        color = colors.get(label or "")
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        if yerr_col:
            d[yerr_col] = pd.to_numeric(d[yerr_col], errors="coerce")
            d = d.dropna(subset=[x_col, y_col, yerr_col]).sort_values(x_col)
        else:
            d = d.dropna(subset=[x_col, y_col]).sort_values(x_col)
        if d.empty:
            continue
        for xi, yi in zip(d[x_col].tolist(), d[y_col].tolist()):
            table_rows.append((label or "", xi, yi))
        any_curve = True
        if yerr_col:
            if label:
                plt.errorbar(d[x_col], d[y_col], yerr=d[yerr_col], fmt="o-", capsize=3, color=color, label=label)
                legend_entries += 1
            else:
                plt.errorbar(d[x_col], d[y_col], yerr=d[yerr_col], fmt="o-", capsize=3, color=color)
        else:
            if label:
                plt.plot(d[x_col], d[y_col], "o-", color=color, label=label)
                legend_entries += 1
            else:
                plt.plot(d[x_col], d[y_col], "o-", color=color)

    if not any_curve:
        plt.close()
        print(f"[WARN] Sem dados para plot {filename}")
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
    _add_xy_value_table(ax, table_rows)
    if legend_entries > 0 or guide_entries > 0:
        plt.legend()
    outpath = target_dir / filename
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"[OK] Salvei {outpath}")
    return True


def plot_all_fuels_with_value_labels(
    df: pd.DataFrame,
    y_col: str,
    title: str,
    filename: str,
    y_label: str,
    label_variant: str = "box",
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
) -> bool:
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")
    target_dir.mkdir(parents=True, exist_ok=True)

    groups = series_fuel_plot_groups(df, fuels_override=fuels_override, series_col=series_col)
    colors = fuel_colors or fuel_color_map([g[0] or "" for g in groups])

    fig, ax = plt.subplots()
    any_curve = False
    legend_entries = 0
    table_rows: List[Tuple[str, object, object]] = []

    for label, d in groups:
        color = colors.get(label or "")
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        d = d.dropna(subset=[x_col, y_col]).sort_values(x_col)
        if d.empty:
            continue
        for xi, yi in zip(d[x_col].tolist(), d[y_col].tolist()):
            table_rows.append((label or "", xi, yi))
        any_curve = True
        if label:
            ax.plot(d[x_col], d[y_col], "o-", color=color, label=label)
            legend_entries += 1
        else:
            ax.plot(d[x_col], d[y_col], "o-", color=color)
        x = pd.to_numeric(d[x_col], errors="coerce").values.astype(float)
        y = pd.to_numeric(d[y_col], errors="coerce").values.astype(float)
        _annotate_points_variants(ax, x, y, label_variant)

    if not any_curve:
        plt.close(fig)
        print(f"[WARN] Sem dados para plot {filename}")
        return False

    _apply_fixed_x_ax(ax, fixed_x)
    _apply_fixed_y_ax(ax, fixed_y, fixed_y_limits)

    guide_entries = _add_y_tolerance_guides(ax, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus)
    if fixed_y is None:
        _apply_y_tick_step(ax, y_tick_step)

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    _add_xy_value_table(ax, table_rows)
    if legend_entries > 0 or guide_entries > 0:
        ax.legend()

    outpath = target_dir / filename
    fig.tight_layout()
    fig.savefig(outpath, dpi=220)
    plt.close(fig)
    print(f"[OK] Salvei {outpath}")
    return True


def plot_all_fuels_delta_ref(
    df: pd.DataFrame,
    y_col: str,
    y_col_delta: str,
    yerr_col: Optional[str],
    yerr_col_delta: Optional[str],
    title: str,
    filename: str,
    y_label: str,
    y_label_delta: str,
    ref_fuel: str = "D85B15",
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
) -> bool:
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")
    target_dir.mkdir(parents=True, exist_ok=True)

    has_delta = y_col_delta and y_col_delta in df.columns

    groups = series_fuel_plot_groups(df, fuels_override=fuels_override, series_col=series_col)
    colors = fuel_colors or fuel_color_map([g[0] or "" for g in groups])

    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx() if has_delta else None

    any_curve = False
    lines_all: list = []
    labels_all: list = []

    for label, d in groups:
        color = colors.get(label or "")

        d = d.copy()
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        if yerr_col and yerr_col in d.columns:
            d[yerr_col] = pd.to_numeric(d[yerr_col], errors="coerce")

        drop_cols = [x_col, y_col]
        if yerr_col and yerr_col in d.columns:
            drop_cols.append(yerr_col)
        d = d.dropna(subset=[x_col, y_col]).sort_values(x_col)
        if d.empty:
            continue
        any_curve = True

        if yerr_col and yerr_col in d.columns:
            eb = ax1.errorbar(
                d[x_col], d[y_col], yerr=d[yerr_col],
                fmt="o-", capsize=3, color=color, label=label or "",
            )
            lines_all.append(eb)
        else:
            (ln,) = ax1.plot(d[x_col], d[y_col], "o-", color=color, label=label or "")
            lines_all.append(ln)
        labels_all.append(label or "")

        is_ref = label and label.strip() == ref_fuel
        if has_delta and ax2 is not None and not is_ref:
            d_delta = d.copy()
            d_delta[y_col_delta] = pd.to_numeric(d_delta.get(y_col_delta, pd.NA), errors="coerce")
            d_delta = d_delta.dropna(subset=[y_col_delta])
            if not d_delta.empty:
                delta_label = f"{label} delta" if label else "delta"
                if yerr_col_delta and yerr_col_delta in d_delta.columns:
                    d_delta[yerr_col_delta] = pd.to_numeric(d_delta[yerr_col_delta], errors="coerce")
                    eb2 = ax2.errorbar(
                        d_delta[x_col], d_delta[y_col_delta], yerr=d_delta[yerr_col_delta],
                        fmt="s--", capsize=2, color=color, alpha=0.7, label=delta_label,
                    )
                    lines_all.append(eb2)
                else:
                    (ln2,) = ax2.plot(
                        d_delta[x_col], d_delta[y_col_delta],
                        "s--", color=color, alpha=0.7, label=delta_label,
                    )
                    lines_all.append(ln2)
                labels_all.append(delta_label)

    if not any_curve:
        plt.close(fig)
        print(f"[WARN] Sem dados para plot {filename}")
        return False

    if ax2 is not None:
        ax2.axhline(0.0, color="gray", linestyle=":", linewidth=1.0, alpha=0.6)
        ax2.set_ylabel(y_label_delta)

    _apply_fixed_x_ax(ax1, fixed_x)
    _apply_fixed_y_ax(ax1, fixed_y, fixed_y_limits)

    guide_entries = _add_y_tolerance_guides(ax1, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus)
    if fixed_y is None:
        _apply_y_tick_step(ax1, y_tick_step)

    ax1.set_xlabel(x_label)
    ax1.set_ylabel(y_label)
    ax1.set_title(title)
    ax1.grid(True, which="both", linestyle="--", linewidth=0.5)

    if labels_all:
        ax1.legend(lines_all, labels_all, loc="best", fontsize=8)

    outpath = target_dir / filename
    fig.tight_layout()
    fig.savefig(outpath, dpi=220)
    plt.close(fig)
    print(f"[OK] Salvei {outpath}")
    return True
