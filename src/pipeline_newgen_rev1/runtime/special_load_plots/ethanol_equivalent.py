"""Ethanol-equivalent consumption plots (overlay + ratio)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def _blend_mask(
    df: pd.DataFrame, *, etoh_pct: float, h2o_pct: float, tol: float = 0.6
) -> pd.Series:
    etoh = pd.to_numeric(df.get("EtOH_pct", pd.Series(pd.NA, index=df.index)), errors="coerce")
    h2o = pd.to_numeric(df.get("H2O_pct", pd.Series(pd.NA, index=df.index)), errors="coerce")
    return (etoh.sub(etoh_pct).abs() <= tol) & (h2o.sub(h2o_pct).abs() <= tol)


_BLEND_SPECS = [
    ("E94H6", 94.0, 6.0),
    ("E75H25", 75.0, 25.0),
    ("E65H35", 65.0, 35.0),
]

_RATIO_SPECS = [
    ("E94H6 / E75H25", 75.0, 25.0),
    ("E94H6 / E65H35", 65.0, 35.0),
]


def plot_ethanol_equivalent_consumption_overlay(
    df: pd.DataFrame, *, plot_dir: Path
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] plot_ethanol_equivalent_consumption_overlay | matplotlib not available; skipping.")
        return None

    x_col = (
        "UPD_Power_Bin_kW" if "UPD_Power_Bin_kW" in df.columns
        else ("UPD_Power_kW" if "UPD_Power_kW" in df.columns else None)
    )
    y_col = "Fuel_E94H6_eq_kg_h"
    if x_col is None or y_col not in df.columns:
        print(f"[WARN] plot_ethanol_equivalent_consumption_overlay | missing columns (x={x_col}, y={y_col in df.columns}); skipping.")
        return None

    plt.figure()
    any_curve = False
    for label, etoh_pct, h2o_pct in _BLEND_SPECS:
        m = _blend_mask(df, etoh_pct=etoh_pct, h2o_pct=h2o_pct)
        d = df[m].copy()
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        d = d.dropna(subset=[x_col, y_col]).sort_values(x_col)
        if d.empty:
            continue
        any_curve = True
        plt.plot(d[x_col], d[y_col], "o-", label=label)

    if not any_curve:
        plt.close()
        return None

    plt.xlabel("Potencia UPD medida (kW, bin 0.1)")
    plt.ylabel("Consumo equivalente E94H6 (kg/h)")
    plt.title("Consumo equivalente de etanol vs potencia UPD (E94H6/E75H25/E65H35)")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    outpath = plot_dir / "consumo_equiv_etanol_vs_upd_power_overlay.png"
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    return outpath


def plot_ethanol_equivalent_ratio(
    df: pd.DataFrame, *, plot_dir: Path
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] plot_ethanol_equivalent_ratio | matplotlib not available; skipping.")
        return None

    y_col = "Fuel_E94H6_eq_kg_h"
    if y_col not in df.columns or "Load_kW" not in df.columns:
        print(f"[WARN] plot_ethanol_equivalent_ratio | missing columns; skipping.")
        return None

    base = df[_blend_mask(df, etoh_pct=94.0, h2o_pct=6.0)].copy()
    base["Load_kW"] = pd.to_numeric(base["Load_kW"], errors="coerce")
    base["UPD_Power_Bin_kW"] = pd.to_numeric(base.get("UPD_Power_Bin_kW", pd.NA), errors="coerce")
    base[y_col] = pd.to_numeric(base[y_col], errors="coerce")
    base = base.dropna(subset=["Load_kW", y_col]).copy()
    if base.empty:
        return None

    plt.figure()
    any_curve = False
    for label, etoh_pct, h2o_pct in _RATIO_SPECS:
        oth = df[_blend_mask(df, etoh_pct=etoh_pct, h2o_pct=h2o_pct)].copy()
        oth["Load_kW"] = pd.to_numeric(oth["Load_kW"], errors="coerce")
        oth[y_col] = pd.to_numeric(oth[y_col], errors="coerce")
        oth = oth.dropna(subset=["Load_kW", y_col]).copy()
        if oth.empty:
            continue

        merged = (
            base[["Load_kW", "UPD_Power_Bin_kW", y_col]]
            .rename(columns={y_col: "cons_eq_e94"})
            .merge(
                oth[["Load_kW", y_col]].rename(columns={y_col: "cons_eq_other"}),
                on="Load_kW",
                how="inner",
            )
        )
        merged["ratio_pct"] = 100.0 * merged["cons_eq_e94"] / merged["cons_eq_other"]
        merged["delta_pct"] = merged["ratio_pct"] - 100.0
        merged = merged.dropna(subset=["delta_pct"]).copy()
        if merged.empty:
            continue

        x = pd.to_numeric(merged["UPD_Power_Bin_kW"], errors="coerce")
        if x.notna().sum() == 0:
            x = pd.to_numeric(merged["Load_kW"], errors="coerce")
        merged = merged.assign(_x=x).dropna(subset=["_x"]).sort_values("_x")
        if merged.empty:
            continue

        any_curve = True
        plt.plot(merged["_x"], merged["delta_pct"], "o-", label=label)

    if not any_curve:
        plt.close()
        return None

    plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label="0% (ref = 100%)")
    plt.xlabel("Potencia UPD medida (kW, bin 0.1)")
    plt.ylabel("Delta percentual de consumo equivalente (%)")
    plt.title("Delta percentual de consumo equivalente (ref=100%)")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    outpath = plot_dir / "consumo_equiv_etanol_ratio_pct_vs_upd_power.png"
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    return outpath
