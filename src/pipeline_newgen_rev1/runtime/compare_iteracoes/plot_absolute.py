"""Renderer: absolute-value comparison plot (2 curves with optional error bars)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def plot_compare_absolute(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    *,
    value_name: str,
    y_label: str,
    title: str,
    filename: str,
    target_dir: Path,
    label_left: str,
    label_right: str,
    include_uncertainty: bool = True,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"[WARN] plot_compare_absolute | matplotlib not available; skipping {filename}.")
        return None

    if (left_df is None or left_df.empty) and (right_df is None or right_df.empty):
        print(f"[WARN] plot_compare_absolute | no data for {filename}.")
        return None

    plt.figure()
    any_curve = False
    specs = [
        (label_left, left_df, "#1f77b4"),
        (label_right, right_df, "#d62728"),
    ]
    for label, d, color in specs:
        if d is None or d.empty:
            continue
        x = pd.to_numeric(d["Load_kW"], errors="coerce")
        y = pd.to_numeric(d[value_name], errors="coerce")
        yerr = pd.to_numeric(d.get(f"U_{value_name}", pd.NA), errors="coerce")
        p = pd.DataFrame({"x": x, "y": y, "yerr": yerr}).dropna(subset=["x", "y"]).sort_values("x")
        if p.empty:
            continue
        any_curve = True
        if include_uncertainty and p["yerr"].notna().any():
            plt.errorbar(p["x"], p["y"], yerr=p["yerr"], fmt="o-", capsize=3,
                         linewidth=1.8, markersize=4.5, color=color, label=label)
        else:
            plt.plot(p["x"], p["y"], "o-", linewidth=1.8, markersize=4.5, color=color, label=label)

    if not any_curve:
        plt.close()
        return None

    plt.xlabel("Carga nominal (kW)")
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    outpath = target_dir / filename
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    return outpath
